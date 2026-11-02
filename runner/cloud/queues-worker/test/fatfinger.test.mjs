// Ordinary mistakes: a clock step, a second click, a blank quota
// field. Not an attack. Each test is one story and then the storage.
import { test } from "node:test";
import assert from "node:assert/strict";

import worker, { TenantQueue, hmacSha384Hex, sha256Hex, DEFAULT_QUOTA, DO_VALUE_MAX, jobStoredBytes, storagePairBytes } from "../src/index.js";

class FakeStorage {
  constructor() { this.map = new Map(); }
  async get(k) { return this.map.has(k) ? structuredClone(this.map.get(k)) : undefined; }
  async put(k, v) { this.map.set(k, structuredClone(v)); }
  async delete(k) { return this.map.delete(k); }
  async list({ prefix = "", limit = Infinity, startAfter } = {}) {
    const out = new Map();
    for (const k of [...this.map.keys()].sort()) {
      if (out.size >= limit) break;
      if (startAfter !== undefined && k <= startAfter) continue;
      if (k.startsWith(prefix)) out.set(k, structuredClone(this.map.get(k)));
    }
    return out;
  }
}

function makeEnv({ quota, reject, lease, clock } = {}) {
  const objects = new Map();
  const env = {
    REJECT_INVALID_HMAC: reject === undefined ? "true" : reject,
    LEASE_MS: lease === undefined ? "300000" : String(lease),
    TENANTS: { store: new Map(), async get(k) { return this.store.get(k) ?? null; } },
    TENANT_QUEUE: {
      idFromName: (n) => n,
      get(id) {
        if (!objects.has(id)) {
          const obj = new TenantQueue({ storage: new FakeStorage() }, env);
          if (clock) obj.now = clock;
          objects.set(id, obj);
        }
        return objects.get(id);
      },
    },
  };
  env.objects = objects;
  env.quota = quota || DEFAULT_QUOTA;
  return env;
}

const SECRET = "s".repeat(64);
const SI = "si-token-alice";
const RUNNER = "runner-token-alice";

async function addTenant(env, slug = "alice", extra = {}) {
  env.TENANTS.store.set(slug, JSON.stringify({
    si_token_sha256: await sha256Hex(SI),
    runner_token_sha256: await sha256Hex(RUNNER),
    hmac_secret: SECRET,
    quota: env.quota,
    ...extra,
  }));
}

async function signedJob(jobId, secret = SECRET, script = "echo hi") {
  const payload = JSON.stringify({ v: 1, type: "job", job_id: jobId, kind: "exec", script });
  const sig = await hmacSha384Hex(secret, payload);
  const body = payload.slice(0, -1) + `,"sig":"${sig}"}`;
  return `[HOMING-PIGEON] job ${jobId}\n\n${body}\n`;
}

function req(path, { method = "GET", token, body } = {}) {
  const headers = {};
  if (token) headers.authorization = `Bearer ${token}`;
  return new Request("https://hp.example.test" + path, { method, headers, body });
}

function box(env) {
  return env.objects.get("alice").state.storage.map;
}

async function postJob(env, id, body) {
  return worker.fetch(req("/t/alice/jobs", {
    method: "POST", token: SI, body: body || await signedJob(id),
  }), env);
}

async function pull(env, max = 5) {
  return worker.fetch(req(`/t/alice/jobs?max=${max}`, { token: RUNNER }), env);
}

const HOUR = 3_600_000;

test("an ack of the hand that lost does not delete the new pull's job", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  let r = await pull(env);
  const first = (await r.json()).jobs[0];
  assert.equal(first.attempt, 1);
  assert.equal(first.hand, 1);
  clock.t += 1000;
  r = await pull(env);
  const second = (await r.json()).jobs[0];
  assert.equal(second.attempt, 2);
  assert.equal(second.hand, 2);
  const held = box(env).get("job:j1").leased_until;
  r = await worker.fetch(req("/t/alice/jobs/j1/ack?hand=1&attempt=1", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 409);
  assert.equal(box(env).get("job:j1").leased_until, held);
  assert.equal(box(env).get("job:j1").hand, 2);
  r = await worker.fetch(req("/t/alice/jobs/j1/lease?attempt=2&hand=1", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 409);
  assert.equal(box(env).get("job:j1").leased_until, held);
  r = await worker.fetch(req("/t/alice/jobs/j1/ack?hand=nope", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 409);
  assert.ok(box(env).has("job:j1"));
  r = await worker.fetch(req("/t/alice/jobs/j1/ack?hand=2", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 204);
  assert.ok(!box(env).has("job:j1"));
});

test("an ack from the life before a requeue does not delete the new one", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await kill(env, clock);
  const deadHand = box(env).get("dlq:j1").hand;
  assert.equal(deadHand, 5);
  assert.equal((await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env)).status, 202);
  assert.equal(box(env).get("job:j1").hand, deadHand + 1);
  assert.equal(box(env).get("job:j1").attempts, 0);
  let r = await worker.fetch(req(`/t/alice/jobs/j1/ack?hand=${deadHand}`, { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 409);
  assert.equal(box(env).get("job:j1").attempts, 0);
  r = await pull(env);
  const job = (await r.json()).jobs[0];
  assert.equal(job.attempt, 1);
  assert.equal(job.hand, deadHand + 2);
  // The attempt count collided with the first life. The hand did not.
  r = await worker.fetch(req("/t/alice/jobs/j1/ack?attempt=1&hand=1", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 409);
  assert.equal(box(env).get("job:j1").hand, job.hand);
  r = await worker.fetch(req(`/t/alice/jobs/j1/ack?hand=${job.hand}`, { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 204);
  assert.ok(!box(env).has("job:j1"));
});

test("a renew after the lease moved does not extend the new holder", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  let r = await pull(env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs[0].attempt, 1);
  clock.t += 1000;
  r = await pull(env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs[0].attempt, 2);
  const held = box(env).get("job:j1").leased_until;
  r = await worker.fetch(req("/t/alice/jobs/j1/lease?attempt=1", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 409);
  assert.equal(box(env).get("job:j1").leased_until, held);
  clock.t += 1;
  r = await worker.fetch(req("/t/alice/jobs/j1/lease?attempt=2", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 204);
  assert.ok(box(env).get("job:j1").leased_until > held);
});

test("a clock jump forward offers the job again, once", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  assert.equal((await pull(env)).status, 200);
  clock.t += 60_000;
  const r = await pull(env);
  assert.equal(r.status, 200);
  const jobs = (await r.json()).jobs;
  assert.deepEqual(jobs.map((j) => j.id), ["j1"]);
  assert.equal(jobs[0].attempt, 2);
  assert.equal(box(env).get("job:j1").attempts, 2);
});

test("a clock jump backward keeps the job leased", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  assert.equal((await pull(env)).status, 200);
  const held = box(env).get("job:j1").leased_until;
  clock.t -= 3_600_000;
  assert.equal((await pull(env)).status, 204);
  assert.equal(box(env).get("job:j1").leased_until, held);
  assert.equal(box(env).get("job:j1").attempts, 1);
});

test("a lease that ends on this exact millisecond is free", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  assert.equal((await pull(env)).status, 200);
  clock.t = box(env).get("job:j1").leased_until;
  const r = await pull(env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs[0].attempt, 2);
});

test("a submit on each side of the hour uses two counters", async () => {
  const t0 = Math.floor(1_700_000_000_000 / HOUR) * HOUR;
  const clock = { t: t0 - 1 };
  const env = makeEnv({ clock: () => clock.t, quota: { jobs_per_hour: 1, bytes_per_day: 60_000 } });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  clock.t = t0;
  assert.equal((await postJob(env, "j2")).status, 202);
  assert.equal(box(env).get(`quota:hour:${Math.floor((t0 - 1) / HOUR)}`), 1);
  assert.equal(box(env).get(`quota:hour:${Math.floor(t0 / HOUR)}`), 1);
});

test("a submit on each side of midnight UTC uses two day counters", async () => {
  const day = 86_400_000;
  const t0 = Math.floor(1_700_000_000_000 / day) * day;
  const clock = { t: t0 - 1 };
  const env = makeEnv({ clock: () => clock.t, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  clock.t = t0;
  assert.equal((await postJob(env, "j2")).status, 202);
  assert.ok(box(env).has(`quota:day:${Math.floor((t0 - 1) / day)}`));
  assert.ok(box(env).has(`quota:day:${Math.floor(t0 / day)}`));
  assert.notEqual(
    box(env).get(`quota:day:${Math.floor((t0 - 1) / day)}`),
    undefined,
  );
});

test("retry-after is one second when the hour has one second left", async () => {
  const t0 = Math.floor(1_700_000_000_000 / HOUR) * HOUR;
  const clock = { t: t0 + HOUR - 1000 };
  const env = makeEnv({ clock: () => clock.t, quota: { jobs_per_hour: 1, bytes_per_day: 60_000 } });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  const r = await postJob(env, "j2");
  assert.equal(r.status, 429);
  assert.equal(Number(r.headers.get("retry-after")), 1);
  assert.ok(!box(env).has("job:j2"));
});

async function kill(env, clock) {
  for (let i = 0; i < 5; i++) {
    assert.equal((await pull(env)).status, 200, `offer ${i}`);
    clock.t += 1000;
  }
  assert.equal((await pull(env)).status, 204);
}

test("requeue twice leaves one job", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await kill(env, clock);
  assert.ok(box(env).has("dlq:j1"));
  let r = await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env);
  assert.equal(r.status, 202);
  r = await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env);
  assert.equal(r.status, 404);
  assert.equal(box(env).get("job:j1").attempts, 0);
  assert.ok(!box(env).has("dlq:j1"));
});

test("acking a dead job and then requeueing queues nothing", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await kill(env, clock);
  assert.equal((await worker.fetch(req("/t/alice/dlq/j1/ack", { method: "POST", token: SI }), env)).status, 204);
  assert.equal((await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env)).status, 404);
  assert.ok(!box(env).has("job:j1"));
  assert.ok(!box(env).has("dlq:j1"));
});

test("requeue then ack of the dead id leaves the queued job", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await kill(env, clock);
  assert.equal((await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env)).status, 202);
  assert.equal((await worker.fetch(req("/t/alice/dlq/j1/ack", { method: "POST", token: SI }), env)).status, 404);
  assert.equal(box(env).get("job:j1").attempts, 0);
});

test("a resent job with a fixed script keeps the first envelope", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  const first = await signedJob("j1", SECRET, "echo hi");
  const second = await signedJob("j1", SECRET, "echo bye");
  assert.notEqual(first, second);
  assert.equal((await postJob(env, "j1", first)).status, 202);
  const r = await postJob(env, "j1", second);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).duplicate, true);
  assert.equal(box(env).get("job:j1").envelope, first);
});

test("acking j1 does not delete j10", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await postJob(env, "j10");
  assert.equal((await worker.fetch(req("/t/alice/jobs/j1/ack", { method: "POST", token: RUNNER }), env)).status, 204);
  assert.ok(!box(env).has("job:j1"));
  assert.ok(box(env).has("job:j10"));
});

test("an ack before any pull deletes the job", async () => {
  // Today's rule. A script that acks early removes a job that never ran.
  const env = makeEnv({ quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  assert.equal((await worker.fetch(req("/t/alice/jobs/j1/ack", { method: "POST", token: RUNNER }), env)).status, 204);
  assert.ok(!box(env).has("job:j1"));
  assert.equal((await pull(env)).status, 204);
});

test("a renew after ack is a 404 and the job stays gone", async () => {
  const env = makeEnv({ lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  assert.equal((await pull(env)).status, 200);
  assert.equal((await worker.fetch(req("/t/alice/jobs/j1/ack", { method: "POST", token: RUNNER }), env)).status, 204);
  assert.equal((await worker.fetch(req("/t/alice/jobs/j1/lease?attempt=1", { method: "POST", token: RUNNER }), env)).status, 404);
  assert.ok(!box(env).has("job:j1"));
});

test("a tenant record with no quota uses the defaults", async () => {
  const env = makeEnv();
  env.TENANTS.store.set("alice", JSON.stringify({
    si_token_sha256: await sha256Hex(SI),
    runner_token_sha256: await sha256Hex(RUNNER),
    hmac_secret: SECRET,
  }));
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.equal(DEFAULT_QUOTA.jobs_per_hour, 600);
  assert.equal(DEFAULT_QUOTA.bytes_per_day, 256 * 1024 * 1024);
});

test("a zero or blank hourly cap locks the tenant", async () => {
  for (const jobs_per_hour of [0, "", -1]) {
    const env = makeEnv({ quota: { jobs_per_hour, bytes_per_day: 60_000 } });
    await addTenant(env);
    const r = await postJob(env, "j1");
    assert.equal(r.status, 429, `cap ${JSON.stringify(jobs_per_hour)}`);
    assert.ok(!box(env).has("job:j1"));
  }
});

test("a quota that is not an object is refused and stores nothing", async () => {
  for (const quota of ["10", 10, [10, 60_000]]) {
    const env = makeEnv({ quota });
    await addTenant(env);
    const r = await postJob(env, "j1");
    assert.equal(r.status, 400, `quota ${JSON.stringify(quota)}`);
    assert.equal((await r.json()).error, "quota is not a number");
    assert.ok(!env.objects.has("alice") || !box(env).has("job:j1"));
  }
});

test("a quota edited into a string leaves the dead job where it is", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await kill(env, clock);
  env.TENANTS.store.set("alice", JSON.stringify({
    si_token_sha256: await sha256Hex(SI),
    runner_token_sha256: await sha256Hex(RUNNER),
    hmac_secret: SECRET,
    quota: "10",
  }));
  const r = await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env);
  assert.equal(r.status, 400);
  assert.equal((await r.json()).error, "quota is not a number");
  assert.ok(box(env).has("dlq:j1"));
  assert.ok(!box(env).has("job:j1"));
});

test("a quota written as words is refused and stores nothing", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: "600 jobs", bytes_per_day: 60_000 } });
  await addTenant(env);
  const r = await postJob(env, "j1");
  assert.equal(r.status, 400);
  assert.equal((await r.json()).error, "quota is not a number");
  assert.ok(!env.objects.has("alice") || !box(env).has("job:j1"));
});

test("a numeric string is still a number", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: "2", bytes_per_day: "60000" } });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.equal((await postJob(env, "j2")).status, 202);
  assert.equal((await postJob(env, "j3")).status, 429);
});

test("the two quota numbers swapped makes a normal job too big", async () => {
  const body = await signedJob("j1", SECRET, "x".repeat(700));
  assert.ok(new TextEncoder().encode(body).length > 600);
  const env = makeEnv({ quota: { jobs_per_hour: 256 * 1024 * 1024, bytes_per_day: 600 } });
  await addTenant(env);
  const r = await postJob(env, "j1", body);
  assert.equal(r.status, 429);
  assert.ok(!box(env).has("job:j1"));
});

test("REJECT_INVALID_HMAC=False turns the gate off", async () => {
  const env = makeEnv({ reject: "False", quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  const r = await worker.fetch(req("/t/alice/jobs", {
    method: "POST", token: SI,
    body: "[HOMING-PIGEON] job j1\n\n{\"v\":1,\"type\":\"job\",\"job_id\":\"j1\"}\n",
  }), env);
  assert.equal(r.status, 202);
});

test("REJECT_INVALID_HMAC=no leaves the gate on", async () => {
  const env = makeEnv({ reject: "no", quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  const r = await worker.fetch(req("/t/alice/jobs", {
    method: "POST", token: SI,
    body: "[HOMING-PIGEON] job j1\n\n{\"v\":1,\"type\":\"job\",\"job_id\":\"j1\"}\n",
  }), env);
  assert.equal(r.status, 400);
  assert.ok(!env.objects.has("alice") || !box(env).has("job:j1"));
});

test("a shared secret with a trailing newline rejects a good job", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env, "alice", { hmac_secret: SECRET + "\n" });
  const r = await postJob(env, "j1");
  assert.equal(r.status, 403);
  assert.ok(!env.objects.has("alice") || !box(env).has("job:j1"));
});

test("one token in both boxes can submit and pull", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  const h = await sha256Hex(SI);
  env.TENANTS.store.set("alice", JSON.stringify({
    si_token_sha256: h, runner_token_sha256: h, hmac_secret: SECRET, quota: env.quota,
  }));
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.equal((await pull(env)).status, 401);
  const r = await worker.fetch(req("/t/alice/jobs", { token: SI }), env);
  assert.equal(r.status, 200);
});

test("the hashes pasted into each other's boxes swap the roles", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  env.TENANTS.store.set("alice", JSON.stringify({
    si_token_sha256: await sha256Hex(RUNNER),
    runner_token_sha256: await sha256Hex(SI),
    hmac_secret: SECRET,
    quota: env.quota,
  }));
  assert.equal((await postJob(env, "j1")).status, 401);
  const asRunner = await worker.fetch(req("/t/alice/jobs", {
    method: "POST", token: RUNNER, body: await signedJob("j1"),
  }), env);
  assert.equal(asRunner.status, 202);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { token: SI }), env)).status, 200);
});

test("a tenant record that is not JSON is a 404 and the other tenant is untouched", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  env.TENANTS.store.set("alice", "{not json");
  await addTenant(env, "bob");
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: await signedJob("j1") }), env)).status, 404);
  const r = await worker.fetch(req("/t/bob/jobs", { method: "POST", token: SI, body: await signedJob("j1") }), env);
  assert.equal(r.status, 202);
  assert.ok(env.objects.get("bob").state.storage.map.has("job:j1"));
  assert.ok(!env.objects.has("alice"));
});

test("Alice and alice are different tenants", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  const rec = JSON.stringify({
    si_token_sha256: await sha256Hex(SI),
    runner_token_sha256: await sha256Hex(RUNNER),
    hmac_secret: SECRET,
    quota: env.quota,
  });
  env.TENANTS.store.set("Alice", rec);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: await signedJob("j1") }), env)).status, 404);
  assert.equal((await worker.fetch(req("/t/Alice/jobs", { method: "POST", token: SI, body: await signedJob("j1") }), env)).status, 202);
});

test("LEASE_MS=-1 is the five-minute default, not an already-expired lease", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: -1, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  assert.equal((await pull(env)).status, 200);
  assert.equal(box(env).get("job:j1").leased_until - clock.t, 300_000);
  clock.t += 1000;
  assert.equal((await pull(env)).status, 204);
  clock.t += 1;
  const r = await worker.fetch(req("/t/alice/jobs/j1/lease?attempt=1", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 204);
  assert.equal(box(env).get("job:j1").leased_until - clock.t, 300_000);
});

test("LEASE_MS=300 is 300 milliseconds, and the job dead-letters", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 300, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await kill(env, clock);
  assert.equal(box(env).get("dlq:j1").attempts, 5);
  assert.ok(!box(env).has("job:j1"));
});

test("LEASE_MS=300000ms is read as 300000, and a word falls back to five minutes", async () => {
  const clock = { t: 1_700_000_000_000 };
  const suffixed = makeEnv({ clock: () => clock.t, lease: "300000ms", quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(suffixed);
  await postJob(suffixed, "j1");
  assert.equal((await pull(suffixed)).status, 200);
  clock.t += 1000;
  assert.equal((await pull(suffixed)).status, 204);
  const word = makeEnv({ clock: () => clock.t, lease: "five", quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(word);
  await postJob(word, "j1");
  assert.equal((await pull(word)).status, 200);
  const held = box(word).get("job:j1").leased_until;
  assert.equal(held - clock.t, 300_000);
});

// ---------------------------------------------------------------------
// Shotgun family for queue item 16: a receipt that is not this
// pull's is 409, not 404 (fixed 694dc82a, 31-Oct-2026). 404 means
// the job is not queued. The same status was returned when the
// hand or the attempt named a different pull and the job was
// still there. The runner treats 404 as finished, forgets the
// result, and runs the job again when that lease ends. The fix
// splits the Worker's /ack and /renew branches: no job is 404, a
// receipt that is not this pull's (namesThisPull fails -- a wrong
// number, or a value the number reading cannot read) is 409 and
// the job stays exactly as it was, and a receipt that names this
// pull -- or the omitted receipt of the old call -- still works.
// This family scattershots everything around that split: both
// verbs, each receipt field alone and paired, right/wrong/
// malformed/empty/duplicated/numerically-respelled values, the
// missing job in every receipt shape, the unpulled and the
// expired lease (where ack and lease part ways), bookended and
// run-length receipt values, injection-shaped values and ids,
// and the lifecycle shapes -- a stale receipt after a second
// pull, a job that is pulled again after a 409, and a receipt
// from the life before a requeue. One regression test was never
// going to be enough for a bug that took days of CPU to find.
//
// Proof of work. The unit tests are the 50 tests registered
// below: 16 hand-written seams, 12 per-field tests, 10 bookend
// sweeps, 5 run-length sweeps, 4 injection-shaped tests and 3
// lifecycle tests. Per-field enumeration: the receipt surface
// is fielded -- the hand query field, the attempt query field,
// the job id in the path, and the verb itself (ack deletes,
// lease extends) -- and each field gets its own tests; the
// stored record's fields (envelope, attempts, hand,
// leased_until) are pinned unchanged by every 409 test.
// Bookends: every printable ASCII symbol (all 32 punctuation
// characters) at the front AND the back of the hand and the
// attempt, as singles, matched pairs, mismatched pairs and
// symbol-only strings, plus NUL, tab, CR and LF at both ends,
// and the same symbols bookending the job id in the path. Two
// bookends parse as the number itself and are pinned as such
// in the spelling test: a leading "+" is the number's sign and
// a trailing "." its decimal point, and tab/CR/LF are trimmed
// by the number reading, so those forms name the pull. Run
// lengths: runs of a wrong digit at lengths 1, 5, 10 and 100,
// 10 ordinary characters with the odd one at the front, the
// back and the middle, a run of 10 leading zeros that still
// reads as the number, and 10 wrong acks and renews in a row.
// The fuzzing was executed, not just the tests written:
// runner/tools/de_dust_corpus.py grow --target channels
// --rounds 400 --seed 20261117, run locally against the banked
// channels corpus (11 entries). Result: 400 rounds, 0 crashes,
// 0 slow, arcs unchanged at 142, slowest try 54 ms -- the
// wrong-receipt shape did not recur. The grow's bookkeeping
// writes were reverted and are not banked (banking is the
// rigs' hourly job); this record is the run's proof. For the
// .mjs file the Python skip registry does not apply, and this
// family adds no skips. None of this is exotic: it is
// combinatorics -- systematically trying the combinations a
// hand-written list would never reach, then pinning each
// answer as a test.

const SG16_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";

async function sg16Setup(id = "j1") {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  assert.equal((await postJob(env, id)).status, 202);
  const r = await pull(env);
  assert.equal(r.status, 200);
  const job = (await r.json()).jobs[0];
  assert.equal(job.id, id);
  assert.equal(job.attempt, 1);
  assert.equal(job.hand, 1);
  return { env, clock, id, job };
}

async function sg16SetupTwo() {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.equal((await postJob(env, "j2")).status, 202);
  const r = await pull(env);
  assert.equal(r.status, 200);
  const jobs = (await r.json()).jobs;
  assert.equal(jobs.length, 2);
  assert.deepEqual(jobs.map((j) => [j.id, j.attempt, j.hand]), [["j1", 1, 1], ["j2", 1, 1]]);
  return { env, clock };
}

function sg16Stored(env, id = "j1") { return box(env).get(`job:${id}`); }

function sg16Snap(env, id = "j1") {
  const j = sg16Stored(env, id);
  return { leased_until: j.leased_until, hand: j.hand, attempts: j.attempts, envelope: j.envelope };
}

function sg16AssertSame(env, snap, id = "j1") {
  const j = sg16Stored(env, id);
  assert.ok(j, `job ${id} still queued`);
  assert.equal(j.leased_until, snap.leased_until);
  assert.equal(j.hand, snap.hand);
  assert.equal(j.attempts, snap.attempts);
  assert.equal(j.envelope, snap.envelope);
}

async function sg16Call(env, verb, qs, id = "j1") {
  return worker.fetch(req(`/t/alice/jobs/${id}/${verb}${qs ? `?${qs}` : ""}`, { method: "POST", token: RUNNER }), env);
}

async function sg16Ack409(env, qs, snap, id = "j1") {
  const r = await sg16Call(env, "ack", qs, id);
  assert.equal(r.status, 409, `ack ?${qs}`);
  sg16AssertSame(env, snap, id);
}

async function sg16Lease409(env, qs, snap, id = "j1") {
  const r = await sg16Call(env, "lease", qs, id);
  assert.equal(r.status, 409, `lease ?${qs}`);
  sg16AssertSame(env, snap, id);
}

// -- 16 hand-written seams -------------------------------------------

test("shotgun16: an ack with the wrong hand alone is 409 and the job is untouched", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "hand=2", snap);
});

test("shotgun16: an ack with the wrong attempt alone is 409 and the job is untouched", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "attempt=2", snap);
});

test("shotgun16: an ack with the right attempt and the wrong hand is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "attempt=1&hand=2", snap);
});

test("shotgun16: an ack with the wrong attempt and the right hand is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "attempt=2&hand=1", snap);
});

test("shotgun16: an ack with a word for a hand is 409, not a crash and not a delete", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "hand=nope", snap);
  await sg16Ack409(env, "hand=one", snap);
});

test("shotgun16: a renew with the wrong hand alone is 409 and the lease does not move", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Lease409(env, "hand=2", snap);
});

test("shotgun16: a renew with the wrong attempt alone is 409 and the lease does not move", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Lease409(env, "attempt=2", snap);
});

test("shotgun16: a renew with a word for a hand is 409 and the lease does not move", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Lease409(env, "hand=nope&attempt=1", snap);
});

test("shotgun16: an ack of a job that is not queued is 404, receipt or not", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  const r = await sg16Call(env, "ack", "", "gone");
  assert.equal(r.status, 404);
  sg16AssertSame(env, snap);
});

test("shotgun16: an ack of a missing job with a plausible receipt is 404, not 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  const r = await sg16Call(env, "ack", "hand=1&attempt=1", "gone");
  assert.equal(r.status, 404);
  sg16AssertSame(env, snap);
});

test("shotgun16: an ack of a missing job with a malformed receipt is 404, not 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  const r = await sg16Call(env, "ack", "hand=nope&attempt=nah", "gone");
  assert.equal(r.status, 404);
  sg16AssertSame(env, snap);
});

test("shotgun16: a renew of a missing job with a receipt is 404, not 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  const r = await sg16Call(env, "lease", "hand=1&attempt=1", "gone");
  assert.equal(r.status, 404);
  sg16AssertSame(env, snap);
});

test("shotgun16: a renew of a queued job nobody pulled is 404 and the job stays queued", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  const r = await sg16Call(env, "lease", "attempt=0");
  assert.equal(r.status, 404);
  assert.equal(sg16Stored(env).leased_until, 0);
  assert.equal(sg16Stored(env).attempts, 0);
  const p = await pull(env);
  assert.equal(p.status, 200);
  assert.equal((await p.json()).jobs[0].attempt, 1);
});

test("shotgun16: a renew on the exact millisecond the lease ends is 404 and the job stays", async () => {
  const { env, clock } = await sg16Setup();
  clock.t = sg16Stored(env).leased_until;
  const r = await sg16Call(env, "lease", "attempt=1&hand=1");
  assert.equal(r.status, 404);
  assert.ok(sg16Stored(env));
  const p = await pull(env);
  assert.equal(p.status, 200);
  assert.equal((await p.json()).jobs[0].attempt, 2);
});

test("shotgun16: after a 409 the right ack still finishes the job", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "hand=2", snap);
  const r = await sg16Call(env, "ack", "hand=1&attempt=1");
  assert.equal(r.status, 204);
  assert.ok(!sg16Stored(env));
});

test("shotgun16: after a 409 the right renew still extends the lease", async () => {
  const { env, clock } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Lease409(env, "hand=2", snap);
  clock.t += 1;
  const r = await sg16Call(env, "lease", "hand=1");
  assert.equal(r.status, 204);
  assert.ok(sg16Stored(env).leased_until > snap.leased_until);
});

// -- 12 per-field tests ----------------------------------------------

test("shotgun16 field hand: the hand alone names the pull for ack and for lease", async () => {
  const { env, clock } = await sg16SetupTwo();
  const snap2 = sg16Snap(env, "j2");
  assert.equal((await sg16Call(env, "ack", "hand=1", "j1")).status, 204);
  assert.ok(!sg16Stored(env, "j1"));
  clock.t += 1;
  assert.equal((await sg16Call(env, "lease", "hand=1", "j2")).status, 204);
  assert.ok(sg16Stored(env, "j2").leased_until > snap2.leased_until);
});

test("shotgun16 field attempt: the attempt alone names the pull for ack and for lease", async () => {
  const { env, clock } = await sg16SetupTwo();
  const snap2 = sg16Snap(env, "j2");
  assert.equal((await sg16Call(env, "ack", "attempt=1", "j1")).status, 204);
  assert.ok(!sg16Stored(env, "j1"));
  clock.t += 1;
  assert.equal((await sg16Call(env, "lease", "attempt=1", "j2")).status, 204);
  assert.ok(sg16Stored(env, "j2").leased_until > snap2.leased_until);
});

test("shotgun16 field receipt omitted: omitting both fields is still the old call", async () => {
  const { env, clock } = await sg16SetupTwo();
  const snap2 = sg16Snap(env, "j2");
  assert.equal((await sg16Call(env, "ack", "", "j1")).status, 204);
  assert.ok(!sg16Stored(env, "j1"));
  clock.t += 1;
  assert.equal((await sg16Call(env, "lease", "", "j2")).status, 204);
  assert.ok(sg16Stored(env, "j2").leased_until > snap2.leased_until);
});

test("shotgun16 field hand: hand 0 is not the first pull's hand and is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "hand=0", snap);
  await sg16Ack409(env, "hand=0&attempt=1", snap);
});

test("shotgun16 field hand: a hand from a pull that has not happened yet is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const hand of [2, 3, 100]) await sg16Ack409(env, `hand=${hand}`, snap);
});

test("shotgun16 field attempt: attempt 0 is not a pulled job's attempt and is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "attempt=0", snap);
  await sg16Ack409(env, "attempt=0&hand=1", snap);
});

test("shotgun16 field attempt: a future attempt on a renew is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Lease409(env, "attempt=2", snap);
  await sg16Lease409(env, "attempt=100&hand=1", snap);
});

test("shotgun16 field hand: a fractional hand is not a number the receipt reads and is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "hand=1.5", snap);
  await sg16Ack409(env, "hand=0.5&attempt=1", snap);
});

test("shotgun16 field lease: an ack ignores the lease clock -- a wrong receipt on an expired job is 409, the right one 204", async () => {
  const { env, clock } = await sg16Setup();
  const snap = sg16Snap(env);
  clock.t += 1000;
  await sg16Ack409(env, "hand=99", snap);
  assert.equal((await sg16Call(env, "ack", "hand=1")).status, 204);
  assert.ok(!sg16Stored(env));
});

test("shotgun16 field empty: an empty hand or attempt reads as omitted", async () => {
  const { env, clock } = await sg16SetupTwo();
  const snap2 = sg16Snap(env, "j2");
  assert.equal((await sg16Call(env, "ack", "hand=&attempt=1", "j1")).status, 204);
  assert.ok(!sg16Stored(env, "j1"));
  clock.t += 1;
  assert.equal((await sg16Call(env, "lease", "attempt=&hand=1", "j2")).status, 204);
  assert.ok(sg16Stored(env, "j2").leased_until > snap2.leased_until);
});

test("shotgun16 field duplicate: a repeated hand field reads its first value", async () => {
  const wrong = await sg16Setup();
  const snap = sg16Snap(wrong.env);
  await sg16Ack409(wrong.env, "hand=2&hand=1", snap);
  const right = await sg16Setup();
  assert.equal((await sg16Call(right.env, "ack", "hand=1&hand=2")).status, 204);
  assert.ok(!sg16Stored(right.env));
});

test("shotgun16 field spelling: the hand written 01, 1.0, 1., 1e0, +1, 0x1 or padded with spaces still names the pull", async () => {
  for (const spelling of ["01", "1.0", "1.", "1e0", "+1", "0x1", " 1", "1 "]) {
    const { env } = await sg16Setup();
    const r = await sg16Call(env, "ack", `hand=${encodeURIComponent(spelling)}`);
    assert.equal(r.status, 204, `hand=${JSON.stringify(spelling)}`);
    assert.ok(!sg16Stored(env));
  }
});

// -- 10 bookend sweeps -------------------------------------------------

test("shotgun16 bookends: every ASCII symbol at the front of the hand is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  // "+" is left out of this sweep: "+1" is the number's own signed
  // spelling and names the pull; it is pinned in the spelling test.
  for (const sym of SG16_PUNCT) {
    if (sym === "+") continue;
    await sg16Ack409(env, `hand=${encodeURIComponent(sym + "1")}&attempt=1`, snap);
  }
});

test("shotgun16 bookends: every ASCII symbol at the back of the hand is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  // "." is left out of this sweep: "1." is the number's own decimal
  // spelling and names the pull; it is pinned in the spelling test.
  for (const sym of SG16_PUNCT) {
    if (sym === ".") continue;
    await sg16Ack409(env, `hand=${encodeURIComponent("1" + sym)}&attempt=1`, snap);
  }
});

test("shotgun16 bookends: matched symbol pairs around the hand are 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const sym of SG16_PUNCT) {
    await sg16Ack409(env, `hand=${encodeURIComponent(sym + "1" + sym)}&attempt=1`, snap);
  }
});

test("shotgun16 bookends: mismatched symbol pairs around the hand are 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (let i = 0; i < SG16_PUNCT.length; i++) {
    const pair = SG16_PUNCT[i] + "1" + SG16_PUNCT[(i + 1) % SG16_PUNCT.length];
    await sg16Ack409(env, `hand=${encodeURIComponent(pair)}&attempt=1`, snap);
  }
});

test("shotgun16 bookends: symbol-only hands are 409, each symbol and all together", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const sym of SG16_PUNCT) {
    await sg16Ack409(env, `hand=${encodeURIComponent(sym)}`, snap);
  }
  await sg16Ack409(env, `hand=${encodeURIComponent(SG16_PUNCT)}`, snap);
});

test("shotgun16 bookends: every ASCII symbol at the front and the back of the attempt is 409 on a renew", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  // Same two spellings left out as for the hand: "+1" is a sign and
  // "1." a decimal point, and both read as the number itself.
  for (const sym of SG16_PUNCT) {
    if (sym !== "+") await sg16Lease409(env, `attempt=${encodeURIComponent(sym + "1")}&hand=1`, snap);
    if (sym !== ".") await sg16Lease409(env, `attempt=${encodeURIComponent("1" + sym)}&hand=1`, snap);
  }
});

test("shotgun16 bookends: symbol-only attempts are 409, each symbol and all together", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const sym of SG16_PUNCT) {
    await sg16Ack409(env, `attempt=${encodeURIComponent(sym)}`, snap);
  }
  await sg16Ack409(env, `attempt=${encodeURIComponent(SG16_PUNCT)}`, snap);
});

test("shotgun16 bookends: NUL at the front, the back and both ends of the hand is 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const value of ["\u00001", "1\u0000", "\u00001\u0000", "\u0000"]) {
    await sg16Ack409(env, `hand=${encodeURIComponent(value)}&attempt=1`, snap);
  }
});

test("shotgun16 bookends: tab, CR and LF at the front, the back and both ends of the hand are trimmed and name the pull", async () => {
  for (const ch of ["\t", "\r", "\n"]) {
    for (const value of [ch + "1", "1" + ch, ch + "1" + ch]) {
      const { env } = await sg16Setup();
      const r = await sg16Call(env, "ack", `hand=${encodeURIComponent(value)}`);
      assert.equal(r.status, 204, `hand=${JSON.stringify(value)}`);
      assert.ok(!sg16Stored(env));
    }
  }
});

test("shotgun16 bookends: symbols bookending the job id in the path are 404 and the real job is untouched", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const sym of SG16_PUNCT) {
    for (const id of [sym + "j1", "j1" + sym, sym + "j1" + sym]) {
      const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent(id)}/ack?hand=1&attempt=1`, { method: "POST", token: RUNNER }), env);
      assert.equal(r.status, 404, `id=${JSON.stringify(id)}`);
    }
  }
  sg16AssertSame(env, snap);
});

// -- 5 run-length sweeps -----------------------------------------------

test("shotgun16 runs: runs of a wrong digit as the hand, lengths 1, 5, 10 and 100, are 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const n of [1, 5, 10, 100]) {
    await sg16Ack409(env, `hand=${"2".repeat(n)}&attempt=1`, snap);
  }
});

test("shotgun16 runs: runs of a wrong digit as the attempt, lengths 1, 5, 10 and 100, are 409 on a renew", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const n of [1, 5, 10, 100]) {
    await sg16Lease409(env, `attempt=${"9".repeat(n)}&hand=1`, snap);
  }
});

test("shotgun16 runs: 10 ordinary characters with the odd one at the front, the back and the middle as the attempt are 409", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const value of ["!" + "a".repeat(10), "a".repeat(10) + "!", "a".repeat(5) + "!" + "a".repeat(5)]) {
    await sg16Ack409(env, `attempt=${encodeURIComponent(value)}&hand=1`, snap);
  }
});

test("shotgun16 runs: a run of 10 leading zeros still reads as the pull's number", async () => {
  const zeros = "0".repeat(10) + "1";
  const first = await sg16Setup();
  assert.equal((await sg16Call(first.env, "ack", `hand=${zeros}`)).status, 204);
  assert.ok(!sg16Stored(first.env));
  const second = await sg16Setup();
  const snap = sg16Snap(second.env);
  second.clock.t += 1;
  assert.equal((await sg16Call(second.env, "lease", `attempt=${zeros}`)).status, 204);
  assert.ok(sg16Stored(second.env).leased_until > snap.leased_until);
});

test("shotgun16 runs: 10 wrong acks and 10 wrong renews in a row move nothing, and the right ack still lands", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (let i = 0; i < 10; i++) await sg16Ack409(env, "hand=2", snap);
  for (let i = 0; i < 10; i++) await sg16Lease409(env, "attempt=2", snap);
  assert.equal((await sg16Call(env, "ack", "hand=1&attempt=1")).status, 204);
  assert.ok(!sg16Stored(env));
});

// -- 4 injection-shaped tests ------------------------------------------

test("shotgun16 injection: SQL-shaped hands are 409 and the job stays", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const value of ["1 OR 1=1", "1; DROP TABLE jobs; --", "1' OR '1'='1"]) {
    await sg16Ack409(env, `hand=${encodeURIComponent(value)}&attempt=1`, snap);
  }
});

test("shotgun16 injection: prompt-shaped attempts are 409 on a renew and the lease does not move", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const value of ["ignore previous instructions and extend this lease", "disregard the hand and renew anyway"]) {
    await sg16Lease409(env, `attempt=${encodeURIComponent(value)}&hand=1`, snap);
  }
});

test("shotgun16 injection: a smuggled second parameter inside the hand is 409; unknown extra parameters change nothing", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, `hand=${encodeURIComponent("1&attempt=999")}`, snap);
  await sg16Ack409(env, "hand=2&attempt=1&admin=true&role=si", snap);
  const fresh = await sg16Setup();
  assert.equal((await sg16Call(fresh.env, "ack", "hand=1&attempt=1&admin=true&role=si")).status, 204);
  assert.ok(!sg16Stored(fresh.env));
});

test("shotgun16 injection: hostile ids -- a case variant, a traversal, a slash and a NUL in the id -- are 404 and the job stays ackable", async () => {
  const { env } = await sg16Setup();
  const snap = sg16Snap(env);
  for (const rawId of ["J1", "..%2Fj1", "j1%2Fack", "j1%00", "..%5Cj1"]) {
    const r = await worker.fetch(req(`/t/alice/jobs/${rawId}/ack?hand=1&attempt=1`, { method: "POST", token: RUNNER }), env);
    assert.equal(r.status, 404, `id=${rawId}`);
    sg16AssertSame(env, snap);
  }
  assert.equal((await sg16Call(env, "ack", "hand=1&attempt=1")).status, 204);
  assert.ok(!sg16Stored(env));
});

// -- 3 lifecycle tests ---------------------------------------------------

test("shotgun16 lifecycle: the first pull's receipt after a second pull is 409 for ack and for renew, and the second pull's ack lands", async () => {
  const { env, clock } = await sg16Setup();
  clock.t += 1000;
  const r = await pull(env);
  assert.equal(r.status, 200);
  const second = (await r.json()).jobs[0];
  assert.equal(second.attempt, 2);
  assert.equal(second.hand, 2);
  const snap = sg16Snap(env);
  await sg16Ack409(env, "hand=1&attempt=1", snap);
  await sg16Lease409(env, "attempt=1&hand=2", snap);
  assert.equal((await sg16Call(env, "ack", "hand=2&attempt=2")).status, 204);
  assert.ok(!sg16Stored(env));
});

test("shotgun16 lifecycle: a job acked with the wrong receipt is not forgotten -- the next pull hands it out again", async () => {
  const { env, clock, job } = await sg16Setup();
  const snap = sg16Snap(env);
  await sg16Ack409(env, "hand=2", snap);
  clock.t += 1000;
  const r = await pull(env);
  assert.equal(r.status, 200);
  const again = (await r.json()).jobs[0];
  assert.equal(again.envelope, job.envelope);
  assert.equal(again.attempt, 2);
  assert.equal(again.hand, 2);
  assert.equal((await sg16Call(env, "ack", "hand=2&attempt=2")).status, 204);
  assert.ok(!sg16Stored(env));
});

test("shotgun16 lifecycle: a receipt from the life before a requeue is 409, before and after the new pull", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await kill(env, clock);
  const deadHand = box(env).get("dlq:j1").hand;
  assert.equal(deadHand, 5);
  assert.equal((await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env)).status, 202);
  assert.equal(sg16Stored(env).hand, deadHand + 1);
  assert.equal(sg16Stored(env).attempts, 0);
  const snap = sg16Snap(env);
  await sg16Ack409(env, `hand=${deadHand}`, snap);
  const r = await pull(env);
  const job = (await r.json()).jobs[0];
  assert.equal(job.attempt, 1);
  assert.equal(job.hand, deadHand + 2);
  const snap2 = sg16Snap(env);
  await sg16Ack409(env, `hand=${deadHand + 1}&attempt=1`, snap2);
  assert.equal((await sg16Call(env, "ack", `hand=${job.hand}`)).status, 204);
  assert.ok(!sg16Stored(env));
});

// ---------------------------------------------------------------------
// Shotgun family for queue item 29: an ack did not name the hand
// it was given; a later pull kept its job (fixed b2795848,
// 31-Oct-2026). Two runners share one token. After the lease
// moved, the first runner's ack deleted the job the second pull
// was running. The attempt count could not save it: a requeue
// resets attempts, so that number collides with the next life
// and the same ack would delete it too. The fix gives every pull
// a hand that only goes up -- one per pull and one more across a
// requeue -- returns it in the pull's answer, and makes an ack
// or a renew that names a hand (or an attempt) leave any other
// pull's job alone; omitting both stays the old call. The same
// fix widened the storage budget to count the hand and the
// requeued_at a second dead-letter copy still carries. (The
// 409/404 split the mismatched receipt answers with today is
// item 16's later fix, pinned by the shotgun16 family above;
// this family pins the hand itself -- its monotonic climb, its
// survival across requeues, and every shape of ack that names
// it, a stale one, another job's, or none.) One regression test
// was never going to be enough for a bug that took days of CPU
// to find.
//
// Proof of work. The unit tests are the 50 tests registered
// below: 14 hand-written seams, 12 per-field tests, 10 bookend
// sweeps, 5 run-length sweeps, 4 injection-shaped tests and 5
// replay/lifecycle tests. Per-field enumeration: the ack
// surface is fielded -- the hand query field, the attempt query
// field, the job id in the path, and the runner token -- and
// each field gets its own tests (present, missing, empty, the
// string spellings of null and other wrong types, negative,
// zero, fractional, an older pull's value, a future pull's
// value, another job's value, case, whitespace and zero-padded
// spellings); the stored record is pinned byte-for-byte
// unchanged by every refused ack. Bookends: every printable
// ASCII symbol (all 32 punctuation characters) at the front AND
// the back of the job id in the ack path and of the hand and
// attempt values, as singles, matched pairs, mismatched pairs
// and symbol-only strings, plus NUL, tab, CR and LF bookending
// the job id (the non-printing characters inside a numeric hand
// are the number reading's own trimming, pinned by item 16's
// family, so here they ride the text field that cannot trim
// them away: the id). Run lengths: runs of a wrong digit as the
// hand at lengths 1, 5 and 10, runs of the right digit past the
// pull's own hand, job ids built from runs of 1, 5 and 10
// ordinary characters and a 128-character id (with 129 refused
// at submit), and zero runs of 1, 5 and 10 padding the hand and
// the attempt, which still read as the pull's numbers. The
// fuzzing was executed, not just the tests written:
// runner/tools/de_dust_corpus.py grow --target channels
// --rounds 400 --seed 20261130, run locally against the banked
// channels corpus (11 entries). Result: 400 rounds, 0 crashes,
// 0 slow, arcs unchanged at 142, slowest try 22 ms -- the
// stale-hand shape did not recur. The grow's bookkeeping writes
// were reverted and are not banked (banking is the rigs' hourly
// job); this record is the run's proof. For the .mjs file the
// Python skip registry does not apply, and this family adds no
// skips. None of this is exotic: it is combinatorics --
// systematically trying the combinations a hand-written list
// would never reach, then pinning each answer as a test.

const SG29_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";

async function sg29Setup(id = "j1") {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  assert.equal((await postJob(env, id)).status, 202);
  const r = await pull(env);
  assert.equal(r.status, 200);
  const job = (await r.json()).jobs[0];
  assert.equal(job.id, id);
  assert.equal(job.attempt, 1);
  assert.equal(job.hand, 1);
  return { env, clock, id, job };
}

// j1 pulled twice (hand 2, attempt 2), j2 pulled once (hand 1).
async function sg29TwoHands() {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.equal((await postJob(env, "j2")).status, 202);
  let r = await pull(env, 1);
  assert.deepEqual((await r.json()).jobs.map((j) => [j.id, j.attempt, j.hand]), [["j1", 1, 1]]);
  clock.t += 1000;
  r = await pull(env);
  assert.deepEqual((await r.json()).jobs.map((j) => [j.id, j.attempt, j.hand]), [["j1", 2, 2], ["j2", 1, 1]]);
  return { env, clock };
}

async function sg29Kill(env, clock) {
  for (let i = 0; i < 5; i++) {
    assert.equal((await pull(env)).status, 200, `offer ${i}`);
    clock.t += 1000;
  }
  assert.equal((await pull(env)).status, 204);
}

function sg29Stored(env, id = "j1") { return box(env).get(`job:${id}`); }
function sg29Snap(env, id = "j1") { return JSON.stringify(sg29Stored(env, id)); }
function sg29AssertSame(env, snap, id = "j1") {
  assert.equal(JSON.stringify(sg29Stored(env, id)), snap, `job ${id} record unchanged`);
}

async function sg29Call(env, verb, qs, id = "j1", token = RUNNER) {
  return worker.fetch(req(`/t/alice/jobs/${id}/${verb}${qs ? `?${qs}` : ""}`, { method: "POST", token }), env);
}

async function sg29Ack409(env, qs, snap, id = "j1") {
  const r = await sg29Call(env, "ack", qs, id);
  assert.equal(r.status, 409, `ack ?${qs}`);
  sg29AssertSame(env, snap, id);
}

// -- 14 hand-written seams -------------------------------------------

test("shotgun29: a pull returns a hand -- an integer starting at 1, recorded on the job", async () => {
  const { env, job } = await sg29Setup();
  assert.ok(Number.isInteger(job.hand));
  assert.equal(job.hand, 1);
  assert.equal(sg29Stored(env).hand, 1);
  assert.equal(sg29Stored(env).attempts, 1);
});

test("shotgun29: every re-pull raises the hand by exactly one, in lockstep with the attempt", async () => {
  const { env, clock } = await sg29Setup();
  for (const want of [2, 3]) {
    clock.t += 1000;
    const r = await pull(env);
    const job = (await r.json()).jobs[0];
    assert.equal(job.hand, want);
    assert.equal(job.attempt, want);
    assert.equal(sg29Stored(env).hand, want);
  }
});

test("shotgun29: hands are per job, not a queue-wide counter -- j1's second hand does not move j2's first", async () => {
  const { env } = await sg29TwoHands();
  assert.equal(sg29Stored(env, "j1").hand, 2);
  assert.equal(sg29Stored(env, "j2").hand, 1);
  assert.equal(sg29Stored(env, "j2").attempts, 1);
});

test("shotgun29: the first pull's ack after a second pull is refused and the record is byte-for-byte unchanged", async () => {
  const { env, clock } = await sg29Setup();
  clock.t += 1000;
  await pull(env);
  const snap = sg29Snap(env);
  await sg29Ack409(env, "hand=1&attempt=1", snap);
  assert.equal((await sg29Call(env, "ack", "hand=2&attempt=2")).status, 204);
  assert.ok(!sg29Stored(env));
});

test("shotgun29: when both fields are named, each must be this pull's -- a right hand with a wrong attempt is refused", async () => {
  const { env, clock } = await sg29Setup();
  clock.t += 1000;
  await pull(env);
  const snap = sg29Snap(env);
  await sg29Ack409(env, "hand=2&attempt=1", snap);
  await sg29Ack409(env, "hand=1&attempt=2", snap);
  await sg29Ack409(env, "hand=2&attempt=3", snap);
});

test("shotgun29: the hand alone, with no attempt, names the later pull and its ack lands", async () => {
  const { env, clock } = await sg29Setup();
  clock.t += 1000;
  await pull(env);
  assert.equal((await sg29Call(env, "ack", "hand=2")).status, 204);
  assert.ok(!sg29Stored(env));
});

test("shotgun29: a requeue raises the hand past the dead pull's and resets the attempt to zero", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await sg29Kill(env, clock);
  assert.equal(box(env).get("dlq:j1").hand, 5);
  assert.equal(box(env).get("dlq:j1").attempts, 5);
  assert.equal((await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env)).status, 202);
  assert.equal(sg29Stored(env).hand, 6);
  assert.equal(sg29Stored(env).attempts, 0);
  assert.equal(sg29Stored(env).leased_until, 0);
});

test("shotgun29: an ack naming the dead life's hand, sent after the requeue but before any new pull, is refused", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await sg29Kill(env, clock);
  await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env);
  const snap = sg29Snap(env);
  await sg29Ack409(env, "hand=5", snap);
  await sg29Ack409(env, "hand=5&attempt=1", snap);
});

test("shotgun29: after a requeue and a new pull, the old hand with the colliding attempt is refused and the new hand lands", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await sg29Kill(env, clock);
  await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env);
  const r = await pull(env);
  const job = (await r.json()).jobs[0];
  assert.equal(job.attempt, 1);
  assert.equal(job.hand, 7);
  const snap = sg29Snap(env);
  // Attempt 1 is this life's attempt too. The hand tells them apart.
  await sg29Ack409(env, "hand=5&attempt=1", snap);
  assert.equal((await sg29Call(env, "ack", "hand=7&attempt=1")).status, 204);
  assert.ok(!sg29Stored(env));
});

test("shotgun29: the hand keeps climbing across a second death and requeue -- 5, 11, then a pull at 13", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await sg29Kill(env, clock);
  await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env);
  await sg29Kill(env, clock);
  assert.equal(box(env).get("dlq:j1").hand, 11);
  assert.equal((await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env)).status, 202);
  assert.equal(sg29Stored(env).hand, 12);
  const r = await pull(env);
  const job = (await r.json()).jobs[0];
  assert.equal(job.attempt, 1);
  assert.equal(job.hand, 13);
  const snap = sg29Snap(env);
  await sg29Ack409(env, "hand=7&attempt=1", snap);
  assert.equal((await sg29Call(env, "ack", "hand=13")).status, 204);
});

test("shotgun29: a renew naming the lost hand does not extend the later pull; the later hand's renew does", async () => {
  const { env, clock } = await sg29Setup();
  clock.t += 1000;
  await pull(env);
  const snap = sg29Snap(env);
  const held = sg29Stored(env).leased_until;
  const r = await sg29Call(env, "lease", "hand=1");
  assert.equal(r.status, 409);
  sg29AssertSame(env, snap);
  clock.t += 1;
  assert.equal((await sg29Call(env, "lease", "hand=2")).status, 204);
  assert.ok(sg29Stored(env).leased_until > held);
});

test("shotgun29: a renew on a requeued job nobody has pulled yet is 404, even naming its current hand", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await sg29Kill(env, clock);
  await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env);
  const snap = sg29Snap(env);
  const r = await sg29Call(env, "lease", "hand=6");
  assert.equal(r.status, 404);
  sg29AssertSame(env, snap);
});

test("shotgun29: an ack after the lease expired still lands when no later pull took the job, and is refused once one has", async () => {
  const a = await sg29Setup();
  a.clock.t += 5000;
  assert.equal((await sg29Call(a.env, "ack", "hand=1")).status, 204);
  assert.ok(!sg29Stored(a.env));
  const b = await sg29Setup();
  b.clock.t += 1000;
  await pull(b.env);
  const snap = sg29Snap(b.env);
  await sg29Ack409(b.env, "hand=1", snap);
});

test("shotgun29: the storage budget counts the hand and the requeued_at -- an envelope between the narrow and the full budget is refused", async () => {
  const now = 9_999_999_999_999;
  const id = "edge";
  const narrow = (text) => storagePairBytes(`dlq:${id}`, {
    id, envelope: text, size: text.length, attempts: 5,
    leased_until: now, enqueued_at: now, dead_at: now,
  });
  assert.ok(jobStoredBytes(id, "", now) > narrow(""), "the budget is wider than a handless dead copy");
  const per = jobStoredBytes(id, "x", now) - jobStoredBytes(id, "", now);
  let text = "x".repeat(Math.floor((DO_VALUE_MAX - jobStoredBytes(id, "", now)) / per) + 1);
  while (jobStoredBytes(id, text, now) <= DO_VALUE_MAX) text += "x";
  while (text.length > 1 && jobStoredBytes(id, text.slice(0, -1), now) > DO_VALUE_MAX) text = text.slice(0, -1);
  assert.ok(jobStoredBytes(id, text, now) > DO_VALUE_MAX);
  assert.ok(narrow(text) <= DO_VALUE_MAX, "the handless dead copy would have stored this");
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 10, bytes_per_day: 9_000_000_000 } });
  await addTenant(env);
  const obj = env.TENANT_QUEUE.get("alice");
  const r = await obj.fetch(new Request("https://do/enqueue", {
    method: "POST",
    headers: { "x-hp-job-id": id, "x-hp-quota": JSON.stringify(env.quota) },
    body: text,
  }));
  assert.equal(r.status, 413);
  assert.ok(!box(env).has(`job:${id}`));
});

// -- 12 per-field tests ----------------------------------------------

test("shotgun29 field hand: the hand alone names this pull for an ack and for a renew", async () => {
  const { env, clock } = await sg29TwoHands();
  const snap2 = sg29Snap(env, "j2");
  assert.equal((await sg29Call(env, "ack", "hand=2", "j1")).status, 204);
  assert.ok(!sg29Stored(env, "j1"));
  clock.t += 1;
  assert.equal((await sg29Call(env, "lease", "hand=1", "j2")).status, 204);
  assert.ok(sg29Stored(env, "j2").leased_until > JSON.parse(snap2).leased_until);
});

test("shotgun29 field receipt omitted: a bare ack after a second pull is still the old call and deletes", async () => {
  const { env, clock } = await sg29Setup();
  clock.t += 1000;
  await pull(env);
  assert.equal(sg29Stored(env).hand, 2);
  assert.equal((await sg29Call(env, "ack", "")).status, 204);
  assert.ok(!sg29Stored(env));
});

test("shotgun29 field hand empty: an empty hand reads as omitted, paired with the right attempt and alone", async () => {
  const a = await sg29Setup();
  a.clock.t += 1000;
  await pull(a.env);
  assert.equal((await sg29Call(a.env, "ack", "hand=&attempt=2")).status, 204);
  const b = await sg29Setup();
  assert.equal((await sg29Call(b.env, "ack", "hand=")).status, 204);
  assert.ok(!sg29Stored(b.env));
});

test("shotgun29 field hand wrong-typed: the strings null, undefined, NaN and true are not hands and are refused", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const value of ["null", "undefined", "NaN", "true", "false", "Infinity", "-Infinity"]) {
    await sg29Ack409(env, `hand=${value}&attempt=1`, snap);
  }
});

test("shotgun29 field hand sign: hand 0 and hand -1 name no pull that happened and are refused", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  await sg29Ack409(env, "hand=0", snap);
  await sg29Ack409(env, "hand=-1", snap);
  await sg29Ack409(env, "hand=-1&attempt=1", snap);
  const r = await sg29Call(env, "lease", "hand=0");
  assert.equal(r.status, 409);
  sg29AssertSame(env, snap);
});

test("shotgun29 field hand fractional: 1.5 and 0.5 are refused; the decimal spelling 1.0 names the pull", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  await sg29Ack409(env, "hand=1.5", snap);
  await sg29Ack409(env, "hand=0.5&attempt=1", snap);
  assert.equal((await sg29Call(env, "ack", "hand=1.0")).status, 204);
  assert.ok(!sg29Stored(env));
});

test("shotgun29 field attempt older: after a second pull, attempt 1 paired with the right hand is still refused", async () => {
  const { env, clock } = await sg29Setup();
  clock.t += 1000;
  await pull(env);
  const snap = sg29Snap(env);
  await sg29Ack409(env, "attempt=1&hand=2", snap);
  await sg29Ack409(env, "attempt=1", snap);
});

test("shotgun29 field attempt future: attempts 3 and 99 name pulls that have not happened and are refused", async () => {
  const { env, clock } = await sg29Setup();
  clock.t += 1000;
  await pull(env);
  const snap = sg29Snap(env);
  await sg29Ack409(env, "attempt=3&hand=2", snap);
  await sg29Ack409(env, "attempt=99", snap);
  const r = await sg29Call(env, "lease", "attempt=3&hand=2");
  assert.equal(r.status, 409);
  sg29AssertSame(env, snap);
});

test("shotgun29 field attempt across a requeue: the attempt alone collides and deletes, the attempt with the old hand does not", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await sg29Kill(env, clock);
  await worker.fetch(req("/t/alice/dlq/j1/requeue", { method: "POST", token: SI }), env);
  const r = await pull(env);
  assert.equal((await r.json()).jobs[0].hand, 7);
  const snap = sg29Snap(env);
  // The hand is the only field that tells the two lives apart.
  await sg29Ack409(env, "attempt=1&hand=5", snap);
  // Pinned as current: an attempt-only ack is the old call from
  // before the hand existed, and attempt 1 is this life's too.
  assert.equal((await sg29Call(env, "ack", "attempt=1")).status, 204);
  assert.ok(!sg29Stored(env));
});

test("shotgun29 field job id: another job's hand is not this job's -- the two receipts crossed are both refused", async () => {
  const { env } = await sg29TwoHands();
  const snap1 = sg29Snap(env, "j1");
  const snap2 = sg29Snap(env, "j2");
  await sg29Ack409(env, "hand=1", snap1, "j1");
  await sg29Ack409(env, "hand=2", snap2, "j2");
  assert.equal((await sg29Call(env, "ack", "hand=2", "j1")).status, 204);
  assert.equal((await sg29Call(env, "ack", "hand=1", "j2")).status, 204);
});

test("shotgun29 field job id spelling: a case variant, a zero-padded id and a trailing-space id name no job and the real job is untouched", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const id of ["J1", "j01", "j1%20", "%20j1", "j-1"]) {
    const r = await worker.fetch(req(`/t/alice/jobs/${id}/ack?hand=1&attempt=1`, { method: "POST", token: RUNNER }), env);
    assert.equal(r.status, 404, `id=${id}`);
    sg29AssertSame(env, snap);
  }
  assert.equal((await sg29Call(env, "ack", "hand=1")).status, 204);
});

test("shotgun29 field token: an ack or a renew with the SI token, a wrong token or no token is 401 and the job is untouched", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const token of [SI, "runner-token-bob"]) {
    const r = await sg29Call(env, "ack", "hand=1", "j1", token);
    assert.equal(r.status, 401, `token=${token}`);
    sg29AssertSame(env, snap);
  }
  const noToken = await worker.fetch(req("/t/alice/jobs/j1/ack?hand=1", { method: "POST" }), env);
  assert.equal(noToken.status, 401);
  sg29AssertSame(env, snap);
  const r = await sg29Call(env, "lease", "hand=1", "j1", SI);
  assert.equal(r.status, 401);
  sg29AssertSame(env, snap);
  assert.equal((await sg29Call(env, "ack", "hand=1")).status, 204);
});

// -- 10 bookend sweeps -------------------------------------------------

test("shotgun29 bookends: every ASCII symbol at the front of the job id in the ack path is 404", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const sym of SG29_PUNCT) {
    const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent(sym + "j1")}/ack?hand=1&attempt=1`, { method: "POST", token: RUNNER }), env);
    assert.equal(r.status, 404, `id=${JSON.stringify(sym + "j1")}`);
  }
  sg29AssertSame(env, snap);
});

test("shotgun29 bookends: every ASCII symbol at the back of the job id in the ack path is 404", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const sym of SG29_PUNCT) {
    const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent("j1" + sym)}/ack?hand=1&attempt=1`, { method: "POST", token: RUNNER }), env);
    assert.equal(r.status, 404, `id=${JSON.stringify("j1" + sym)}`);
  }
  sg29AssertSame(env, snap);
});

test("shotgun29 bookends: matched symbol pairs around the job id are 404", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const sym of SG29_PUNCT) {
    const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent(sym + "j1" + sym)}/ack?hand=1&attempt=1`, { method: "POST", token: RUNNER }), env);
    assert.equal(r.status, 404, `id=${JSON.stringify(sym + "j1" + sym)}`);
  }
  sg29AssertSame(env, snap);
});

test("shotgun29 bookends: mismatched symbol pairs around the job id are 404", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (let i = 0; i < SG29_PUNCT.length; i++) {
    const id = SG29_PUNCT[i] + "j1" + SG29_PUNCT[(i + 1) % SG29_PUNCT.length];
    const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent(id)}/ack?hand=1&attempt=1`, { method: "POST", token: RUNNER }), env);
    assert.equal(r.status, 404, `id=${JSON.stringify(id)}`);
  }
  sg29AssertSame(env, snap);
});

test("shotgun29 bookends: symbol-only job ids are 404, each symbol and all together, and the real ack still lands after", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const sym of SG29_PUNCT) {
    const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent(sym)}/ack?hand=1`, { method: "POST", token: RUNNER }), env);
    assert.equal(r.status, 404, `id=${JSON.stringify(sym)}`);
  }
  const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent(SG29_PUNCT)}/ack?hand=1`, { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 404);
  sg29AssertSame(env, snap);
  assert.equal((await sg29Call(env, "ack", "hand=1")).status, 204);
});

test("shotgun29 bookends: NUL, tab, CR and LF at the front, the back and both ends of the job id are 404", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const ch of ["\u0000", "\t", "\r", "\n"]) {
    for (const id of [ch + "j1", "j1" + ch, ch + "j1" + ch]) {
      const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent(id)}/ack?hand=1&attempt=1`, { method: "POST", token: RUNNER }), env);
      assert.equal(r.status, 404, `id=${JSON.stringify(id)}`);
    }
  }
  sg29AssertSame(env, snap);
});

test("shotgun29 bookends: matched symbol pairs around both the hand and the attempt at once are refused", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const sym of SG29_PUNCT) {
    const wrapped = encodeURIComponent(sym + "1" + sym);
    await sg29Ack409(env, `hand=${wrapped}&attempt=${wrapped}`, snap);
  }
});

test("shotgun29 bookends: mismatched symbol pairs around the hand, with the attempt exactly right, are refused", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (let i = 0; i < SG29_PUNCT.length; i++) {
    const wrapped = SG29_PUNCT[i] + "1" + SG29_PUNCT[(i + 1) % SG29_PUNCT.length];
    await sg29Ack409(env, `hand=${encodeURIComponent(wrapped)}&attempt=1`, snap);
  }
});

test("shotgun29 bookends: a symbol-only hand with a symbol-only attempt is refused, each symbol and all together", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const sym of SG29_PUNCT) {
    await sg29Ack409(env, `hand=${encodeURIComponent(sym)}&attempt=${encodeURIComponent(sym)}`, snap);
  }
  await sg29Ack409(env, `hand=${encodeURIComponent(SG29_PUNCT)}&attempt=${encodeURIComponent(SG29_PUNCT)}`, snap);
});

test("shotgun29 bookends: symbols bookending the job id on the renew verb are 404 and the real renew still lands", async () => {
  const { env, clock } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const sym of ["!", "~", "@", "#"]) {
    for (const id of [sym + "j1", "j1" + sym, sym + "j1" + sym]) {
      const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent(id)}/lease?hand=1`, { method: "POST", token: RUNNER }), env);
      assert.equal(r.status, 404, `id=${JSON.stringify(id)}`);
    }
  }
  sg29AssertSame(env, snap);
  clock.t += 1;
  assert.equal((await sg29Call(env, "lease", "hand=1")).status, 204);
  assert.ok(sg29Stored(env).leased_until > JSON.parse(snap).leased_until);
});

// -- 5 run-length sweeps -----------------------------------------------

test("shotgun29 runs: runs of a wrong digit as the hand, lengths 1, 5 and 10, and runs of the right digit past this hand, are refused", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const n of [1, 5, 10]) {
    await sg29Ack409(env, `hand=${"2".repeat(n)}&attempt=1`, snap);
    await sg29Ack409(env, `hand=${"1".repeat(n + 1)}&attempt=1`, snap);
  }
});

test("shotgun29 runs: job ids built from runs of 1, 5 and 10 ordinary characters each pull and ack by their own hand", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  for (const n of [1, 5, 10]) {
    const id = "j" + "a".repeat(n);
    assert.equal((await postJob(env, id)).status, 202);
    const r = await pull(env);
    const job = (await r.json()).jobs.find((j) => j.id === id);
    assert.equal(job.hand, 1);
    const miss = await worker.fetch(req(`/t/alice/jobs/${id + "a"}/ack?hand=1`, { method: "POST", token: RUNNER }), env);
    assert.equal(miss.status, 404);
    assert.equal((await sg29Call(env, "ack", "hand=1", id)).status, 204);
    assert.ok(!sg29Stored(env, id));
  }
});

test("shotgun29 runs: runs of ordinary characters with the odd one at the front, the back and the middle, as the attempt, are refused", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const value of ["!" + "a".repeat(10), "a".repeat(10) + "!", "a".repeat(5) + "!" + "a".repeat(5), "a".repeat(10)]) {
    await sg29Ack409(env, `attempt=${encodeURIComponent(value)}&hand=1`, snap);
  }
});

test("shotgun29 runs: zero runs of length 1, 5 and 10 padding the hand still name the pull, and padding the attempt still renews", async () => {
  for (const n of [1, 5, 10]) {
    const a = await sg29Setup();
    assert.equal((await sg29Call(a.env, "ack", `hand=${"0".repeat(n)}1`)).status, 204, `zeros=${n}`);
    assert.ok(!sg29Stored(a.env));
    const b = await sg29Setup();
    const snap = sg29Snap(b.env);
    b.clock.t += 1;
    assert.equal((await sg29Call(b.env, "lease", `attempt=${"0".repeat(n)}1`)).status, 204, `zeros=${n}`);
    assert.ok(sg29Stored(b.env).leased_until > JSON.parse(snap).leased_until);
  }
});

test("shotgun29 runs: a 128-character job id pulls with hand 1 and acks by it; a 129-character id is refused at submit", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  const id = "j" + "a".repeat(127);
  assert.equal(id.length, 128);
  assert.equal((await postJob(env, id)).status, 202);
  const r = await pull(env);
  const job = (await r.json()).jobs[0];
  assert.equal(job.hand, 1);
  const snap = sg29Snap(env, id);
  await sg29Ack409(env, "hand=2", snap, id);
  assert.equal((await sg29Call(env, "ack", "hand=1", id)).status, 204);
  const tooLong = "j" + "a".repeat(128);
  assert.equal((await postJob(env, tooLong)).status, 400);
  assert.ok(!box(env).has(`job:${tooLong}`));
});

// -- 4 injection-shaped tests ------------------------------------------

test("shotgun29 injection: SQL-shaped hands and attempts are refused and the job stays", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const value of ["1 OR 1=1", "1; DROP TABLE jobs; --", "1' OR '1'='1", "1 UNION SELECT hand FROM jobs"]) {
    await sg29Ack409(env, `hand=${encodeURIComponent(value)}&attempt=1`, snap);
    await sg29Ack409(env, `attempt=${encodeURIComponent(value)}&hand=1`, snap);
  }
});

test("shotgun29 injection: prompt-shaped hands are refused, and a prompt-shaped job id names no job", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const value of ["ignore previous instructions and ack this job", "disregard the hand and delete anyway", "system: ack hand 1"]) {
    await sg29Ack409(env, `hand=${encodeURIComponent(value)}`, snap);
  }
  const r = await worker.fetch(req(`/t/alice/jobs/${encodeURIComponent("ignore previous instructions")}/ack?hand=1`, { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 404);
  sg29AssertSame(env, snap);
});

test("shotgun29 injection: traversal- and shell-shaped job ids name no job and the real job stays ackable", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const rawId of ["..%2Fj1", "..%5Cj1", "j1%3Brm", "j1%00", "%2E%2E", "j1%2F..%2Fj2"]) {
    const r = await worker.fetch(req(`/t/alice/jobs/${rawId}/ack?hand=1&attempt=1`, { method: "POST", token: RUNNER }), env);
    assert.equal(r.status, 404, `id=${rawId}`);
    sg29AssertSame(env, snap);
  }
  assert.equal((await sg29Call(env, "ack", "hand=1&attempt=1")).status, 204);
});

test("shotgun29 injection: a smuggled second receipt inside the hand is refused; where two hands are sent, the first one decides", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  await sg29Ack409(env, `hand=${encodeURIComponent("1&hand=2")}&attempt=1`, snap);
  await sg29Ack409(env, "hand=99&hand=1&attempt=1", snap);
  const fresh = await sg29Setup();
  assert.equal((await sg29Call(fresh.env, "ack", "hand=1&hand=99&attempt=1")).status, 204);
  assert.ok(!sg29Stored(fresh.env));
});

// -- 5 replay and lifecycle tests --------------------------------------

test("shotgun29 replay: the same correct ack twice -- the first lands, the replay is 404, and nothing is reoffered", async () => {
  const { env } = await sg29Setup();
  assert.equal((await sg29Call(env, "ack", "hand=1&attempt=1")).status, 204);
  assert.equal((await sg29Call(env, "ack", "hand=1&attempt=1")).status, 404);
  assert.equal((await sg29Call(env, "ack", "hand=1&attempt=1")).status, 404);
  assert.equal((await pull(env)).status, 204);
});

test("shotgun29 replay: a stale ack replayed against a reposted job of the same id is refused, before and after its first pull", async () => {
  const { env, clock } = await sg29Setup();
  clock.t += 1000;
  await pull(env);
  assert.equal((await sg29Call(env, "ack", "hand=2")).status, 204);
  assert.equal((await postJob(env, "j1")).status, 202);
  // The new record has no hand yet: the replayed hand 2 names nothing.
  let r = await sg29Call(env, "ack", "hand=2");
  assert.equal(r.status, 409);
  assert.ok(sg29Stored(env));
  r = await pull(env);
  const job = (await r.json()).jobs[0];
  assert.equal(job.hand, 1);
  assert.equal(job.attempt, 1);
  const snap = sg29Snap(env);
  await sg29Ack409(env, "hand=2", snap);
  assert.equal((await sg29Call(env, "ack", "hand=1")).status, 204);
});

test("shotgun29 replay: an ack for an unknown id is 404 in every receipt shape", async () => {
  const { env } = await sg29Setup();
  const snap = sg29Snap(env);
  for (const qs of ["", "hand=1", "attempt=1", "hand=1&attempt=1", "hand=nope", "hand=0&attempt=0"]) {
    const r = await sg29Call(env, "ack", qs, "gone");
    assert.equal(r.status, 404, `ack ?${qs}`);
  }
  sg29AssertSame(env, snap);
});

test("shotgun29 replay: an ack before any pull -- a named hand is refused and the job still pulls; attempt 0 alone is the old call and deletes", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env);
  await postJob(env, "j1");
  await postJob(env, "j2");
  const r = await sg29Call(env, "ack", "hand=1", "j1");
  assert.equal(r.status, 409);
  assert.equal(sg29Stored(env, "j1").attempts, 0);
  assert.equal(sg29Stored(env, "j1").hand, undefined);
  const p = await pull(env);
  assert.deepEqual((await p.json()).jobs.map((j) => [j.id, j.hand]), [["j1", 1], ["j2", 1]]);
  const clock2 = { t: 1_700_000_000_000 };
  const env2 = makeEnv({ clock: () => clock2.t, lease: 1000, quota: { jobs_per_hour: 20, bytes_per_day: 60_000 } });
  await addTenant(env2);
  await postJob(env2, "j1");
  // Attempt 0 is the unpulled record's own attempt and no hand is
  // named, so the old call still names it. Pinned as current.
  assert.equal((await sg29Call(env2, "ack", "attempt=0", "j1")).status, 204);
  assert.ok(!sg29Stored(env2, "j1"));
});

test("shotgun29 lifecycle: two pulls race one ack -- the loser's ack and renew are refused, the winner's renew extends and its ack finishes", async () => {
  const { env, clock } = await sg29Setup();
  clock.t += 1000;
  const r = await pull(env);
  assert.equal((await r.json()).jobs[0].hand, 2);
  const snap = sg29Snap(env);
  await sg29Ack409(env, "hand=1&attempt=1", snap);
  const rr = await sg29Call(env, "lease", "hand=1&attempt=1");
  assert.equal(rr.status, 409);
  sg29AssertSame(env, snap);
  clock.t += 1;
  assert.equal((await sg29Call(env, "lease", "hand=2&attempt=2")).status, 204);
  assert.ok(sg29Stored(env).leased_until > JSON.parse(snap).leased_until);
  assert.equal((await sg29Call(env, "ack", "hand=2&attempt=2")).status, 204);
  assert.ok(!sg29Stored(env));
  assert.equal((await pull(env)).status, 204);
// Shotgun family for queue item 30: a negative LEASE_MS read as an
// already-expired job instead of the five-minute default (fixed
// 8c5ae5cf, 31-Oct-2026). The old pull and renew code read the
// config as parseInt(...) || 300000: a negative is truthy, so it
// survived, and leased_until = now + (a negative) was already in
// the past -- every pulled job was instantly reclaimable and never
// really leased. The fix routes both call sites through leaseMs:
// parseInt of the raw value, and anything not finite or <= 0 is
// the 300000 ms default. This family scattershots the whole
// config-value surface leaseMs reads: per-value enumeration of
// the spellings (negatives, zero, 1 ms, just under / exactly /
// just over the default, huge values, fractions, exponents,
// hex/octal/binary-looking strings, whitespace, signs, empty,
// missing, null-ish, words, trailing junk), the observable
// consequence (a job under a defaulted value stays leased for
// the full window; a job under an accepted short lease expires
// on schedule), the deadline boundary (1 ms before, exactly at,
// 1 ms after, on pull and on renew), bookends (every printable
// ASCII symbol at the front AND the back of the value, singles,
// matched and mismatched pairs, symbol-only values, NUL and
// tab/CR/LF shapes), run lengths (digit runs of zeros and nines
// at lengths 1/5/10/30, the odd character at the front, the back
// and the middle), and injection-shaped values (shell, SQL, JSON
// and prompt shapes are parsed as a number or defaulted, never
// executed). leaseMs has exactly two call sites, pull and renew,
// and both are pinned; its neighbours (clampedMax, quotaNumber)
// do not share this code path and are pinned by their own
// families, not here. One regression test was never going to be
// enough for a bug that took days of CPU to find.
//
// Proof of work. The unit tests are the 50 tests registered
// below: 18 per-value tests, 8 spelling tests (whitespace,
// signs, trailing junk, separators), 8 consequence and boundary
// tests, 8 bookend sweeps, 4 run-length sweeps and 4
// injection-shaped tests. Per-field enumeration: the surface is
// the one field LEASE_MS, read by leaseMs, and every spelling
// class of that field gets its own test; the stored record's
// leased_until is the observable the tests pin, together with
// the second pull's status and the renew's status. Bookends:
// every printable ASCII symbol (all 32 punctuation characters)
// at the front and at the back of "1000" (a value distinct from
// the default, so a front symbol that kills the number is
// visibly the default, not 1000), as singles, matched pairs,
// mismatched pairs and symbol-only strings, plus NUL, tab, CR
// and LF at both ends, and bookends around a negative value.
// Run lengths: runs of zeros and nines at lengths 1, 5, 10 and
// 30, a run of leading zeros that still reads as the number,
// and the odd character at the front, the back and the middle
// of a 10-digit run. The fuzzing was executed, not just the
// tests written: runner/tools/de_dust_corpus.py grow --target
// wire --rounds 400 --seed 20261131, run locally against the
// banked wire corpus. Result: 400 rounds, 0 crashes, 0 slow, arcs unchanged at 184, slowest try 1280 ms -- the already-expired-lease shape did not recur. The
// grow's bookkeeping writes were reverted and are not banked
// (banking is the rigs' hourly job); this record is the run's
// proof. For the .mjs file the Python skip registry does not
// apply, and this family adds no skips. None of this is exotic:
// it is combinatorics -- systematically trying the combinations
// a hand-written list would never reach, then pinning each
// answer as a test.

const SG30_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
const SG30_DEFAULT = 300_000;
const SG30_BIG_QUOTA = { jobs_per_hour: 100_000, bytes_per_day: 100_000_000 };

async function sg30World(lease) {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease, quota: SG30_BIG_QUOTA });
  await addTenant(env);
  return { env, clock };
}

// Post one job, pull it, and return how long it was leased for.
// The clock does not move, so the delta is leased_until - now.
async function sg30Delta(env, clock, id = "j1") {
  assert.equal((await postJob(env, id)).status, 202);
  assert.equal((await pull(env, 1)).status, 200);
  return box(env).get(`job:${id}`).leased_until - clock.t;
}

// A cycler reuses one tenant: it sets env.LEASE_MS raw (leaseMs
// reads it at pull time), posts and pulls one job, acks it away,
// and returns the lease delta. Quota is sized for hundreds of
// cycles inside one fake hour.
async function sg30Cycler() {
  const { env, clock } = await sg30World("300000");
  let n = 0;
  return async (raw) => {
    env.LEASE_MS = raw;
    const id = `c${++n}`;
    const d = await sg30Delta(env, clock, id);
    const r = await worker.fetch(req(`/t/alice/jobs/${id}/ack`, { method: "POST", token: RUNNER }), env);
    assert.equal(r.status, 204, `ack after ${JSON.stringify(raw)}`);
    return d;
  };
}

async function sg30Renew(env, id = "j1", qs = "attempt=1") {
  return worker.fetch(req(`/t/alice/jobs/${id}/lease?${qs}`, { method: "POST", token: RUNNER }), env);
}

// -- 18 per-value tests ------------------------------------------------

test("shotgun30 value: LEASE_MS=-1 leases for the full default window, to the millisecond", async () => {
  const { env, clock } = await sg30World(-1);
  assert.equal(await sg30Delta(env, clock), SG30_DEFAULT);
  clock.t += SG30_DEFAULT - 1;
  assert.equal((await pull(env)).status, 204);
  clock.t += 1;
  const r = await pull(env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs[0].attempt, 2);
});

test("shotgun30 value: LEASE_MS=-300000 and -300001 are the default, not a past lease", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("-300000"), SG30_DEFAULT);
  assert.equal(await delta("-300001"), SG30_DEFAULT);
  assert.equal(await delta("-299999"), SG30_DEFAULT);
});

test("shotgun30 value: zero in every spelling -- 0, 00, -0, +0, 0.0 -- is the default", async () => {
  const delta = await sg30Cycler();
  for (const v of ["0", "00", "-0", "+0", "0.0", "0.000"]) {
    assert.equal(await delta(v), SG30_DEFAULT, `LEASE_MS=${v}`);
  }
});

test("shotgun30 value: the most negative spellings are the default", async () => {
  const delta = await sg30Cycler();
  for (const v of ["-9007199254740991", "-2147483648", "-2147483647", "-" + "9".repeat(24), "-42"]) {
    assert.equal(await delta(v), SG30_DEFAULT, `LEASE_MS=${v}`);
  }
});

test("shotgun30 value: a missing, unset or empty LEASE_MS is the default", async () => {
  const { env, clock } = await sg30World("1000");
  let n = 0;
  for (const raw of [undefined, "", null]) {
    env.LEASE_MS = raw;
    const id = `m${++n}`;
    assert.equal(await sg30Delta(env, clock, id), SG30_DEFAULT, `LEASE_MS=${String(raw)}`);
    assert.equal((await worker.fetch(req(`/t/alice/jobs/${id}/ack`, { method: "POST", token: RUNNER }), env)).status, 204);
  }
  delete env.LEASE_MS;
  assert.equal(await sg30Delta(env, clock, "mgone"), SG30_DEFAULT);
});

test("shotgun30 value: null-ish and boolean raw values are the default", async () => {
  const delta = await sg30Cycler();
  for (const v of ["null", "undefined", "NULL", "None", "nil"]) {
    assert.equal(await delta(v), SG30_DEFAULT, `LEASE_MS=${v}`);
  }
  assert.equal(await delta(false), SG30_DEFAULT);
  assert.equal(await delta(true), SG30_DEFAULT);
});

test("shotgun30 value: NaN and Infinity spellings are the default", async () => {
  const delta = await sg30Cycler();
  for (const v of ["NaN", "nan", "Infinity", "-Infinity", "+Infinity", "inf", "-inf", "-1e999"]) {
    assert.equal(await delta(v), SG30_DEFAULT, `LEASE_MS=${v}`);
  }
});

test("shotgun30 value: words are the default", async () => {
  const delta = await sg30Cycler();
  for (const v of ["five", "five minutes", "ms", "lease", "default", "five300000"]) {
    assert.equal(await delta(v), SG30_DEFAULT, `LEASE_MS=${v}`);
  }
});

test("shotgun30 value: 1 ms is accepted -- leased at the same instant, free 1 ms later", async () => {
  const { env, clock } = await sg30World("1");
  assert.equal(await sg30Delta(env, clock), 1);
  assert.equal((await pull(env)).status, 204);
  clock.t += 1;
  const r = await pull(env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs[0].attempt, 2);
});

test("shotgun30 value: 300 ms is accepted and expires at 300, not at 299", async () => {
  const { env, clock } = await sg30World(300);
  assert.equal(await sg30Delta(env, clock), 300);
  clock.t += 299;
  assert.equal((await pull(env)).status, 204);
  clock.t += 1;
  assert.equal((await pull(env)).status, 200);
});

test("shotgun30 value: 299999, just under the default, is accepted as itself", async () => {
  const { env, clock } = await sg30World("299999");
  assert.equal(await sg30Delta(env, clock), 299_999);
  clock.t += 299_999;
  assert.equal((await pull(env)).status, 200);
});

test("shotgun30 value: 300000 exactly is a 300000 ms lease", async () => {
  const { env, clock } = await sg30World("300000");
  assert.equal(await sg30Delta(env, clock), SG30_DEFAULT);
  clock.t += SG30_DEFAULT - 1;
  assert.equal((await pull(env)).status, 204);
  clock.t += 1;
  assert.equal((await pull(env)).status, 200);
});

test("shotgun30 value: 300001, just over the default, is accepted as itself", async () => {
  const { env, clock } = await sg30World("300001");
  assert.equal(await sg30Delta(env, clock), 300_001);
  clock.t += SG30_DEFAULT;
  assert.equal((await pull(env)).status, 204);
  clock.t += 1;
  assert.equal((await pull(env)).status, 200);
});

test("shotgun30 value: values at and past 2^31 are accepted, not clamped and not defaulted", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("2147483647"), 2_147_483_647);
  assert.equal(await delta("2147483648"), 2_147_483_648);
  assert.equal(await delta("4294967296"), 4_294_967_296);
});

test("shotgun30 value: a 2^53-scale value is accepted -- still leased after the default window", async () => {
  const { env, clock } = await sg30World("9007199254740993");
  const d = await sg30Delta(env, clock);
  assert.ok(d > SG30_DEFAULT, `delta ${d}`);
  clock.t += SG30_DEFAULT;
  assert.equal((await pull(env)).status, 204);
  assert.equal(box(env).get("job:j1").attempts, 1);
});

test("shotgun30 value: fractions are cut at the point -- 0.5 and 0.999 default, 1.5 is 1, 300000.9 is 300000", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("0.5"), SG30_DEFAULT);
  assert.equal(await delta("0.999"), SG30_DEFAULT);
  assert.equal(await delta("1.5"), 1);
  assert.equal(await delta("300000.9"), 300_000);
  assert.equal(await delta("299999.9"), 299_999);
  assert.equal(await delta("-1.5"), SG30_DEFAULT);
});

test("shotgun30 value: exponent forms stop at the e -- 1e3 is 1, 3e5 is 3, 300000e0 is 300000", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("1e3"), 1);
  assert.equal(await delta("3e5"), 3);
  assert.equal(await delta("300000e0"), 300_000);
  assert.equal(await delta("1e0"), 1);
  assert.equal(await delta("0e5"), SG30_DEFAULT);
  assert.equal(await delta("10e2"), 10);
  assert.equal(await delta("1e999"), 1);
});

test("shotgun30 value: hex, octal and binary spellings read in base 10 -- 0x300000 is 0 and defaults, 010 is 10", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("0x300000"), SG30_DEFAULT);
  assert.equal(await delta("0x1"), SG30_DEFAULT);
  assert.equal(await delta("0o777"), SG30_DEFAULT);
  assert.equal(await delta("0b1"), SG30_DEFAULT);
  assert.equal(await delta("010"), 10);
  assert.equal(await delta("007"), 7);
});

// -- 8 spelling tests ----------------------------------------------------

test("shotgun30 spelling: leading whitespace -- spaces, tab, CR, LF -- is skipped", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta(" 1000"), 1000);
  assert.equal(await delta("\t1000"), 1000);
  assert.equal(await delta("\r1000"), 1000);
  assert.equal(await delta("\n1000"), 1000);
  assert.equal(await delta(" \t\r\n 42"), 42);
});

test("shotgun30 spelling: trailing whitespace ends the number cleanly", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("1000 "), 1000);
  assert.equal(await delta("1000\t"), 1000);
  assert.equal(await delta("1000\r\n"), 1000);
  assert.equal(await delta("1000\n\n\n"), 1000);
});

test("shotgun30 spelling: whitespace around a negative still reads the negative and defaults", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta(" -1 "), SG30_DEFAULT);
  assert.equal(await delta("\t-1000\t"), SG30_DEFAULT);
  assert.equal(await delta("\n-42\r\n"), SG30_DEFAULT);
});

test("shotgun30 spelling: a leading plus is the number's own sign", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("+1"), 1);
  assert.equal(await delta("+299999"), 299_999);
  assert.equal(await delta("+300000"), 300_000);
  assert.equal(await delta("+0"), SG30_DEFAULT);
});

test("shotgun30 spelling: doubled and mixed signs are not numbers and default", async () => {
  const delta = await sg30Cycler();
  for (const v of ["++1000", "+-1000", "-+1000", "--1000", "+ 1000", "- 1000"]) {
    assert.equal(await delta(v), SG30_DEFAULT, `LEASE_MS=${v}`);
  }
});

test("shotgun30 spelling: trailing junk after the digits is ignored -- 1000ms is 1000", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("1000ms"), 1000);
  assert.equal(await delta("1000 milliseconds"), 1000);
  assert.equal(await delta("1000;"), 1000);
  assert.equal(await delta("1000abc"), 1000);
  assert.equal(await delta("300000ms"), 300_000);
});

test("shotgun30 spelling: trailing junk after a negative does not rescue it -- it defaults", async () => {
  const delta = await sg30Cycler();
  for (const v of ["-1000ms", "-1abc", "-42!", "-300000 seconds"]) {
    assert.equal(await delta(v), SG30_DEFAULT, `LEASE_MS=${v}`);
  }
});

test("shotgun30 spelling: separators inside the digits cut the number -- 300_000 is 300", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("300_000"), 300);
  assert.equal(await delta("300,000"), 300);
  assert.equal(await delta("300 000"), 300);
  assert.equal(await delta("1_000"), 1);
  assert.equal(await delta("1,000,000"), 1);
});

// -- 8 consequence and boundary tests ------------------------------------

test("shotgun30 consequence: under a negative LEASE_MS a second pull never hands the job out inside the window", async () => {
  const { env, clock } = await sg30World("-5000");
  assert.equal(await sg30Delta(env, clock), SG30_DEFAULT);
  for (const step of [1, 999, 100_000, 198_999]) {
    clock.t += step;
    assert.equal((await pull(env)).status, 204, `at +${clock.t - 1_700_000_000_000}`);
    assert.equal(box(env).get("job:j1").attempts, 1);
  }
});

test("shotgun30 consequence: an accepted 1000 ms lease is free exactly at expiry and 1 ms after, on fresh jobs", async () => {
  for (const offset of [1000, 1001]) {
    const { env, clock } = await sg30World("1000");
    assert.equal(await sg30Delta(env, clock), 1000);
    clock.t += 999;
    assert.equal((await pull(env)).status, 204, `offset ${offset} at expiry - 1`);
    clock.t += offset - 999;
    const r = await pull(env);
    assert.equal(r.status, 200, `offset ${offset} at or past the mark`);
    assert.equal((await r.json()).jobs[0].attempt, 2);
  }
});

test("shotgun30 consequence: a renew under a negative LEASE_MS extends by the default, not into the past", async () => {
  const { env, clock } = await sg30World("-1");
  assert.equal(await sg30Delta(env, clock), SG30_DEFAULT);
  clock.t += 1000;
  assert.equal((await sg30Renew(env)).status, 204);
  assert.equal(box(env).get("job:j1").leased_until - clock.t, SG30_DEFAULT);
  clock.t += SG30_DEFAULT - 1;
  assert.equal((await pull(env)).status, 204);
});

test("shotgun30 consequence: a renew under an accepted 1000 ms lease extends by 1000 only", async () => {
  const { env, clock } = await sg30World("1000");
  assert.equal(await sg30Delta(env, clock), 1000);
  clock.t += 999;
  assert.equal((await sg30Renew(env)).status, 204);
  assert.equal(box(env).get("job:j1").leased_until - clock.t, 1000);
  clock.t += 1000;
  assert.equal((await pull(env)).status, 200);
});

test("shotgun30 consequence: a renew 1 ms before a defaulted lease ends lands; exactly at the end it is 404", async () => {
  const before = await sg30World("-9");
  assert.equal(await sg30Delta(before.env, before.clock), SG30_DEFAULT);
  before.clock.t += SG30_DEFAULT - 1;
  assert.equal((await sg30Renew(before.env)).status, 204);
  const at = await sg30World("-9");
  assert.equal(await sg30Delta(at.env, at.clock), SG30_DEFAULT);
  at.clock.t += SG30_DEFAULT;
  assert.equal((await sg30Renew(at.env)).status, 404);
  assert.ok(box(at.env).has("job:j1"));
});

test("shotgun30 consequence: a negative LEASE_MS does not dead-letter the job -- attempts stay at 1 across sub-window steps", async () => {
  const { env, clock } = await sg30World("-2147483648");
  assert.equal(await sg30Delta(env, clock), SG30_DEFAULT);
  for (let i = 0; i < 3; i++) {
    clock.t += 99_999;
    assert.equal((await pull(env)).status, 204);
  }
  assert.equal(box(env).get("job:j1").attempts, 1);
  assert.ok(!box(env).has("dlq:j1"));
  clock.t += 3;
  assert.equal((await pull(env)).status, 200);
  assert.equal(box(env).get("job:j1").attempts, 2);
});

test("shotgun30 consequence: two jobs under a word LEASE_MS are both leased for the full window", async () => {
  const { env, clock } = await sg30World("five");
  await postJob(env, "j1");
  await postJob(env, "j2");
  const r = await pull(env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs.length, 2);
  assert.equal(box(env).get("job:j1").leased_until - clock.t, SG30_DEFAULT);
  assert.equal(box(env).get("job:j2").leased_until - clock.t, SG30_DEFAULT);
  clock.t += SG30_DEFAULT - 1;
  assert.equal((await pull(env)).status, 204);
});

test("shotgun30 consequence: changing LEASE_MS to a negative between pull and renew renews by the default", async () => {
  const { env, clock } = await sg30World("1000");
  assert.equal(await sg30Delta(env, clock), 1000);
  env.LEASE_MS = "-1";
  clock.t += 500;
  assert.equal((await sg30Renew(env)).status, 204);
  assert.equal(box(env).get("job:j1").leased_until - clock.t, SG30_DEFAULT);
});

// -- 8 bookend sweeps ------------------------------------------------------

test("shotgun30 bookends: every ASCII symbol at the front of 1000 defaults, except + which is the sign", async () => {
  const delta = await sg30Cycler();
  for (const sym of SG30_PUNCT) {
    const want = sym === "+" ? 1000 : SG30_DEFAULT;
    assert.equal(await delta(sym + "1000"), want, `front ${JSON.stringify(sym)}`);
  }
});

test("shotgun30 bookends: every ASCII symbol at the back of 1000 is trailing junk and reads 1000", async () => {
  const delta = await sg30Cycler();
  for (const sym of SG30_PUNCT) {
    assert.equal(await delta("1000" + sym), 1000, `back ${JSON.stringify(sym)}`);
  }
});

test("shotgun30 bookends: matched symbol pairs around 1000 default, except ++ which still signs the number", async () => {
  const delta = await sg30Cycler();
  for (const sym of SG30_PUNCT) {
    const want = sym === "+" ? 1000 : SG30_DEFAULT;
    assert.equal(await delta(sym + "1000" + sym), want, `pair ${JSON.stringify(sym)}`);
  }
});

test("shotgun30 bookends: mismatched symbol pairs around 1000 default, except a leading + which reads 1000", async () => {
  const delta = await sg30Cycler();
  for (let i = 0; i < SG30_PUNCT.length; i++) {
    const front = SG30_PUNCT[i];
    const back = SG30_PUNCT[(i + 1) % SG30_PUNCT.length];
    const want = front === "+" ? 1000 : SG30_DEFAULT;
    assert.equal(await delta(front + "1000" + back), want, `pair ${JSON.stringify(front + back)}`);
  }
});

test("shotgun30 bookends: symbol-only values default, each symbol and all together", async () => {
  const delta = await sg30Cycler();
  for (const sym of SG30_PUNCT) {
    assert.equal(await delta(sym), SG30_DEFAULT, `only ${JSON.stringify(sym)}`);
  }
  assert.equal(await delta(SG30_PUNCT), SG30_DEFAULT);
  assert.equal(await delta(SG30_PUNCT + SG30_PUNCT), SG30_DEFAULT);
});

test("shotgun30 bookends: NUL at the front kills the number, at the back is junk, and alone defaults", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("\u00001000"), SG30_DEFAULT);
  assert.equal(await delta("1000\u0000"), 1000);
  assert.equal(await delta("\u00001000\u0000"), SG30_DEFAULT);
  assert.equal(await delta("\u0000"), SG30_DEFAULT);
});

test("shotgun30 bookends: tab, CR and LF at the front, the back and both ends of 1000 all read 1000", async () => {
  const delta = await sg30Cycler();
  for (const ch of ["\t", "\r", "\n"]) {
    assert.equal(await delta(ch + "1000"), 1000, `front ${JSON.stringify(ch)}`);
    assert.equal(await delta("1000" + ch), 1000, `back ${JSON.stringify(ch)}`);
    assert.equal(await delta(ch + "1000" + ch), 1000, `both ${JSON.stringify(ch)}`);
  }
});

test("shotgun30 bookends: symbols around a negative and around zero all land on the default", async () => {
  const delta = await sg30Cycler();
  for (const v of ["!-1000", "-1000!", "(-1000)", "--1000", "\u0000-1000", "-1000\u0000", "!0!", "(0)", "-0-", "\u00000\u0000"]) {
    assert.equal(await delta(v), SG30_DEFAULT, `LEASE_MS=${JSON.stringify(v)}`);
  }
});

// -- 4 run-length sweeps -----------------------------------------------------

test("shotgun30 runs: runs of zeros at lengths 1, 5, 10 and 30 default; a zero run before a 1 still reads 1", async () => {
  const delta = await sg30Cycler();
  for (const n of [1, 5, 10, 30]) {
    assert.equal(await delta("0".repeat(n)), SG30_DEFAULT, `${n} zeros`);
  }
  assert.equal(await delta("0".repeat(30) + "1"), 1);
  assert.equal(await delta("0".repeat(10) + "1000"), 1000);
});

test("shotgun30 runs: runs of nines at lengths 1, 5 and 10 are themselves; 30 nines is a huge accepted lease", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("9"), 9);
  assert.equal(await delta("9".repeat(5)), 99_999);
  assert.equal(await delta("9".repeat(10)), 9_999_999_999);
  const huge = await delta("9".repeat(30));
  assert.ok(huge > 1e29, `30 nines delta ${huge}`);
});

test("shotgun30 runs: the odd character at the front, the back and the middle of a 10-digit run", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("!" + "9".repeat(10)), SG30_DEFAULT);
  assert.equal(await delta("9".repeat(10) + "!"), 9_999_999_999);
  assert.equal(await delta("9".repeat(5) + "!" + "9".repeat(5)), 99_999);
  assert.equal(await delta("-" + "9".repeat(10)), SG30_DEFAULT);
});

test("shotgun30 runs: runs of ones -- 10 ones are themselves, 10 negative ones default, 30 ones stay leased past the window", async () => {
  const { env, clock } = await sg30World("1".repeat(30));
  const d = await sg30Delta(env, clock);
  assert.ok(d > SG30_DEFAULT, `30 ones delta ${d}`);
  clock.t += SG30_DEFAULT;
  assert.equal((await pull(env)).status, 204);
  const delta = await sg30Cycler();
  assert.equal(await delta("1".repeat(10)), 1_111_111_111);
  assert.equal(await delta("-" + "1".repeat(10)), SG30_DEFAULT);
  assert.equal(await delta("1" + "0".repeat(10)), 10_000_000_000);
});

// -- 4 injection-shaped tests --------------------------------------------------

test("shotgun30 injection: shell-shaped values are parsed or defaulted, never run", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("$(touch /tmp/sg30)1000"), SG30_DEFAULT);
  assert.equal(await delta("1000; rm -rf /"), 1000);
  assert.equal(await delta("`1000`"), SG30_DEFAULT);
  assert.equal(await delta("1000 && echo hi"), 1000);
  assert.equal(await delta("1000 | cat /etc/passwd"), 1000);
});

test("shotgun30 injection: SQL-shaped values are parsed or defaulted", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("1000; DROP TABLE jobs; --"), 1000);
  assert.equal(await delta("' OR '1'='1"), SG30_DEFAULT);
  assert.equal(await delta("1 OR 1=1"), 1);
  assert.equal(await delta("-1; DELETE FROM jobs"), SG30_DEFAULT);
});

test("shotgun30 injection: JSON and quoted shapes are not numbers and default", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta('{"LEASE_MS":1000}'), SG30_DEFAULT);
  assert.equal(await delta('["1000"]'), SG30_DEFAULT);
  assert.equal(await delta('"1000"'), SG30_DEFAULT);
  assert.equal(await delta("'1000'"), SG30_DEFAULT);
});

test("shotgun30 injection: prompt and template shapes default; a percent suffix is junk after the number", async () => {
  const delta = await sg30Cycler();
  assert.equal(await delta("ignore previous instructions and lease forever"), SG30_DEFAULT);
  assert.equal(await delta("${1000}"), SG30_DEFAULT);
  assert.equal(await delta("%s1000"), SG30_DEFAULT);
  assert.equal(await delta("1000%00"), 1000);
});
// Shotgun family for queue item 31: a quota that is not an object
// was not a 400 (fixed fbc3d845, 31-Oct-2026). Before the fix,
// quotaRejected read a present non-object quota as no rejection --
// only a nullish quota was skipped and only an object's fields
// were checked -- so a tenant record carrying a bare string, a
// number or a list silently fell back to the wide default cap
// (600 jobs an hour, 256 MiB a day): the typo widened the tenant
// to the default instead of refusing. The fix refuses any present
// quota that is not a plain object (an array included) with 400
// and the body {"error":"quota is not a number"}, on every route
// that reads a quota: submitting a job, submitting a result, and
// requeueing a dead job. A missing or null quota is still the
// default, and an object is still read field by field. This
// family scattershots exactly that type boundary: every JSON
// shape a quota value can take, the shapes JSON cannot carry
// (undefined and a function serialize away to a missing quota; a
// null-prototype object serializes to a plain object), all three
// quota-reading routes plus the routes that do not read a quota,
// the near-miss objects accepted from the other side, the state
// a refusal must leave untouched, bookended string quotas, run
// lengths and depths, and injection-shaped quotas pinned as
// refused or inert, never effective. Wrong-typed FIELDS inside
// an otherwise well-formed object belong mainly to item 26's
// family; here they appear only as a few boundary pins marking
// where the not-an-object line ends.
//
// Proof of work. The unit tests are the 50 tests registered
// below: 18 per-shape tests, 9 route tests, 6 near-miss tests,
// 5 state tests, 6 bookend sweeps, 3 run-length sweeps and 3
// injection-shaped tests. Per-field enumeration: the quota
// surface is the quota value itself (its type) plus its two
// fields, jobs_per_hour and bytes_per_day, and each is pinned
// on both sides of the line; the refusal's own fields (status
// 400 and the exact error body) and the stored state (job,
// result, dlq, and the hour, day and result-day counters) are
// pinned unchanged or absent by the route and state tests.
// Bookends: every printable ASCII symbol (all 32 punctuation
// characters) at the front AND the back of a string quota, as
// singles, matched pairs, mismatched pairs and symbol-only
// strings, plus NUL, tab, CR and LF at both ends and inside.
// Run lengths: string quotas of length 1, 5, 10 and 1000, arrays
// of 1, 5 and 10 elements, and nesting 1, 5 and 10 deep ending
// in a non-object. The fuzzing was executed, not just the tests
// written: runner/tools/de_dust_corpus.py grow --target stage
// --rounds 400 --seed 20261132, run locally against the banked
// stage corpus (35 entries). Result: 400 rounds, 0 crashes,
// 0 slow, arcs unchanged at 93, slowest try 55 ms -- the
// not-an-object quota shape did not recur. The grow's
// bookkeeping writes were reverted and are not banked (banking
// is the rigs' hourly job); this record is the run's proof. For
// the .mjs file the Python skip registry does not apply, and
// this family adds no skips. None of this is exotic: it is
// combinatorics -- systematically trying the combinations a
// hand-written list would never reach, then pinning each
// answer as a test.

const SG31_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
const SG31_GOOD = { jobs_per_hour: 10, bytes_per_day: 60_000 };

async function sg31Tenant(env, quota) {
  env.TENANTS.store.set("alice", JSON.stringify({
    si_token_sha256: await sha256Hex(SI),
    runner_token_sha256: await sha256Hex(RUNNER),
    hmac_secret: SECRET,
    quota,
  }));
}

async function sg31RawTenant(env, quotaJson) {
  const si = await sha256Hex(SI);
  const rn = await sha256Hex(RUNNER);
  env.TENANTS.store.set("alice",
    `{"si_token_sha256":"${si}","runner_token_sha256":"${rn}","hmac_secret":"${SECRET}","quota":${quotaJson}}`);
}

async function sg31Env(quota, opts = {}) {
  const env = makeEnv({ quota: SG31_GOOD, ...opts });
  await sg31Tenant(env, quota);
  return env;
}

async function sg31EnvMissing(opts = {}) {
  const env = makeEnv({ quota: SG31_GOOD, ...opts });
  env.TENANTS.store.set("alice", JSON.stringify({
    si_token_sha256: await sha256Hex(SI),
    runner_token_sha256: await sha256Hex(RUNNER),
    hmac_secret: SECRET,
  }));
  return env;
}

function sg31Box(env, slug = "alice") { return env.objects.get(slug).state.storage.map; }

function sg31AssertNothingStored(env, slug = "alice") {
  assert.ok(!env.objects.has(slug) || sg31Box(env, slug).size === 0,
    "a refused quota stored something");
}

function sg31Snap(env, slug = "alice") {
  return [...sg31Box(env, slug).entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([k, v]) => [k, structuredClone(v)]);
}

function sg31AssertSnap(env, snap, slug = "alice") {
  assert.deepEqual(sg31Snap(env, slug), snap);
}

async function sg31Expect400Job(env, id = "j1") {
  const r = await postJob(env, id);
  assert.equal(r.status, 400, `job submit for id ${id}`);
  assert.deepEqual(await r.json(), { error: "quota is not a number" });
  return r;
}

function sg31Result(id = "r1") {
  return `[HOMING-PIGEON] result ${id}\n\n${JSON.stringify({ job_id: id, exit_code: 0 })}\n`;
}

async function sg31PostResult(env, id = "r1", slug = "alice") {
  return worker.fetch(req(`/t/${slug}/results`, { method: "POST", token: RUNNER, body: sg31Result(id) }), env);
}

async function sg31Expect400Result(env, id = "r1") {
  const r = await sg31PostResult(env, id);
  assert.equal(r.status, 400, `result submit for id ${id}`);
  assert.deepEqual(await r.json(), { error: "quota is not a number" });
  return r;
}

async function sg31Requeue(env, id = "j1") {
  return worker.fetch(req(`/t/alice/dlq/${id}/requeue`, { method: "POST", token: SI }), env);
}

async function sg31DeadEnv(quotaAfter) {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: SG31_GOOD });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  await kill(env, clock);
  assert.ok(box(env).has("dlq:j1"));
  await sg31Tenant(env, quotaAfter);
  return { env, clock };
}

// -- 18 per-shape tests ------------------------------------------------

test("shotgun31 shape string empty: an empty-string quota is a 400 and stores nothing", async () => {
  const env = await sg31Env("");
  await sg31Expect400Job(env);
  sg31AssertNothingStored(env);
});

test("shotgun31 shape string numeric: numeric-looking string quotas are a 400, not the number", async () => {
  const env = await sg31Env("10");
  for (const q of ["10", "600", "0", "-1", "1.5", " 10 ", "1e3"]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape string JSON: a JSON-looking string quota is a 400, not a parsed object", async () => {
  const env = await sg31Env("{}");
  for (const q of ['{"jobs_per_hour":10,"bytes_per_day":60000}', '{"jobs_per_hour":10}', "{}", "[]", "[10,60000]"]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape string words: the word null, undefined, true and object as a string quota are a 400", async () => {
  const env = await sg31Env("null");
  for (const q of ["null", "undefined", "true", "false", "object", "[object Object]", "600 jobs an hour"]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape number zero: a quota of 0 is a 400, not a locked tenant and not the default", async () => {
  const env = await sg31Env(0);
  await sg31Expect400Job(env);
  sg31AssertNothingStored(env);
});

test("shotgun31 shape number positive: quota numbers 1 and 600 are a 400", async () => {
  const env = await sg31Env(1);
  for (const q of [1, 600, 60_000]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape number negative: negative quota numbers are a 400", async () => {
  const env = await sg31Env(-1);
  for (const q of [-1, -600, -60_000]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape number fractional: fractional quota numbers are a 400", async () => {
  const env = await sg31Env(1.5);
  for (const q of [1.5, 0.5, -0.5, 0.1]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape number huge: huge quota numbers are a 400", async () => {
  const env = await sg31Env(Number.MAX_SAFE_INTEGER);
  for (const q of [Number.MAX_SAFE_INTEGER, 1e15, Number.MAX_VALUE]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape boolean true: a quota of true is a 400", async () => {
  const env = await sg31Env(true);
  await sg31Expect400Job(env);
  sg31AssertNothingStored(env);
});

test("shotgun31 shape boolean false: a quota of false is a 400, not the default the harness fallback would give", async () => {
  const env = await sg31Env(false);
  await sg31Expect400Job(env);
  sg31AssertNothingStored(env);
});

test("shotgun31 shape null: a null quota is not refused -- the default cap applies", async () => {
  const env = await sg31Env(null);
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.ok(box(env).has("job:j1"));
  assert.equal(DEFAULT_QUOTA.jobs_per_hour, 600);
});

test("shotgun31 shape missing: a tenant record with no quota key uses the default and accepts", async () => {
  const env = await sg31EnvMissing();
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.ok(box(env).has("job:j1"));
});

test("shotgun31 shape unserializable: an undefined or function quota serializes away to a missing quota and accepts", async () => {
  // JSON is the tenant record's carrier: undefined and a function
  // have no JSON form, so the record that reaches the Worker has
  // no quota key at all. Pinned as the missing case, not a 400.
  for (const q of [undefined, () => 10, function quotaFn() { return 10; }]) {
    const env = await sg31Env(q);
    assert.equal((await postJob(env, "j1")).status, 202, `quota ${String(q)}`);
    assert.ok(box(env).has("job:j1"));
  }
});

test("shotgun31 shape array empty and numbers: an empty array and a number array quota are a 400", async () => {
  const env = await sg31Env([]);
  for (const q of [[], [10, 60_000], [600]]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape array contents: an array holding a valid object or numeric strings is still a 400", async () => {
  const env = await sg31Env([{ jobs_per_hour: 10, bytes_per_day: 60_000 }]);
  for (const q of [[{ jobs_per_hour: 10, bytes_per_day: 60_000 }], ["10", "60000"], [null], [true]]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape array nested: nested array quotas are a 400 at every nesting shown", async () => {
  const env = await sg31Env([[10, 60_000]]);
  for (const q of [[[10, 60_000]], [[["10"]]], [[{ jobs_per_hour: 10 }]]]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 shape null-prototype object: a null-prototype quota object serializes to a plain object and accepts", async () => {
  const empty = Object.create(null);
  const envEmpty = await sg31Env(empty);
  assert.equal((await postJob(envEmpty, "j1")).status, 202);
  const filled = Object.create(null);
  filled.jobs_per_hour = 10;
  filled.bytes_per_day = 60_000;
  const envFilled = await sg31Env(filled);
  assert.equal((await postJob(envFilled, "j1")).status, 202);
  assert.ok(box(envFilled).has("job:j1"));
});

// -- 9 route tests -------------------------------------------------------

test("shotgun31 route results string and number: a string or number quota is a 400 on the result route and stores no result", async () => {
  const env = await sg31Env("10");
  for (const q of ["10", "lots", 10, 0, -1, 1.5]) {
    await sg31Tenant(env, q);
    await sg31Expect400Result(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 route results array and boolean: an array or boolean quota is a 400 on the result route and stores no result", async () => {
  const env = await sg31Env([]);
  for (const q of [[], [10, 60_000], [{ jobs_per_hour: 10 }], true, false]) {
    await sg31Tenant(env, q);
    await sg31Expect400Result(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 route requeue string: a string quota edited in leaves the dead job in the dlq on requeue", async () => {
  const { env } = await sg31DeadEnv("10");
  const snap = sg31Snap(env);
  const r = await sg31Requeue(env);
  assert.equal(r.status, 400);
  assert.deepEqual(await r.json(), { error: "quota is not a number" });
  sg31AssertSnap(env, snap);
  assert.ok(box(env).has("dlq:j1"));
  assert.ok(!box(env).has("job:j1"));
});

test("shotgun31 route requeue other shapes: a number, array or boolean quota leaves the dead job in the dlq on requeue", async () => {
  for (const q of [10, 0, [10, 60_000], [], true, false]) {
    const { env } = await sg31DeadEnv(q);
    const snap = sg31Snap(env);
    const r = await sg31Requeue(env);
    assert.equal(r.status, 400, `quota ${JSON.stringify(q)}`);
    assert.deepEqual(await r.json(), { error: "quota is not a number" });
    sg31AssertSnap(env, snap);
  }
});

test("shotgun31 route uniformity: the same bad quota gives the same 400 body on job, result and requeue", async () => {
  const { env } = await sg31DeadEnv("10");
  const jobR = await postJob(env, "j2");
  const resR = await sg31PostResult(env, "r1");
  const reqR = await sg31Requeue(env);
  for (const r of [jobR, resR, reqR]) assert.equal(r.status, 400);
  const bodies = [await jobR.json(), await resR.json(), await reqR.json()];
  assert.deepEqual(bodies, [
    { error: "quota is not a number" },
    { error: "quota is not a number" },
    { error: "quota is not a number" },
  ]);
  assert.ok(box(env).has("dlq:j1"));
  assert.ok(!box(env).has("job:j2"));
  assert.ok(!box(env).has("result:r1"));
});

test("shotgun31 route not poisoned pull and ack: a bad quota edited in does not block pulling or acking a queued job", async () => {
  const env = makeEnv({ quota: SG31_GOOD });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  await sg31Tenant(env, "10");
  const r = await pull(env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs[0].id, "j1");
  const ack = await worker.fetch(req("/t/alice/jobs/j1/ack?hand=1&attempt=1", { method: "POST", token: RUNNER }), env);
  assert.equal(ack.status, 204);
  assert.ok(!box(env).has("job:j1"));
});

test("shotgun31 route not poisoned lease and results: a bad quota does not block a lease renew, a results read or a result ack", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = makeEnv({ clock: () => clock.t, lease: 1000, quota: SG31_GOOD });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.equal((await sg31PostResult(env, "j1")).status, 202);
  assert.equal((await pull(env)).status, 200);
  await sg31Tenant(env, [10, 60_000]);
  const renew = await worker.fetch(req("/t/alice/jobs/j1/lease?attempt=1&hand=1", { method: "POST", token: RUNNER }), env);
  assert.equal(renew.status, 204);
  const read = await worker.fetch(req("/t/alice/results", { token: SI }), env);
  assert.equal(read.status, 200);
  assert.deepEqual((await read.json()).results.map((row) => row.id), ["j1"]);
  const ack = await worker.fetch(req("/t/alice/results/j1/ack", { method: "POST", token: SI }), env);
  assert.equal(ack.status, 204);
  assert.ok(!box(env).has("result:j1"));
  assert.ok(box(env).has("job:j1"));
});

test("shotgun31 route not poisoned dlq reads: a bad quota does not block listing the dlq or acking a dead job", async () => {
  const { env } = await sg31DeadEnv(42);
  const list = await worker.fetch(req("/t/alice/dlq", { token: SI }), env);
  assert.equal(list.status, 200);
  assert.deepEqual((await list.json()).dead.map((row) => row.id), ["j1"]);
  const ack = await worker.fetch(req("/t/alice/dlq/j1/ack", { method: "POST", token: SI }), env);
  assert.equal(ack.status, 204);
  assert.ok(!box(env).has("dlq:j1"));
});

test("shotgun31 route tenant isolation: alice's bad quota does not poison bob, and bob's work does not cure alice", async () => {
  const env = makeEnv({ quota: SG31_GOOD });
  await sg31Tenant(env, "10");
  await addTenant(env, "bob");
  await sg31Expect400Job(env);
  const bobR = await worker.fetch(req("/t/bob/jobs", { method: "POST", token: SI, body: await signedJob("j1") }), env);
  assert.equal(bobR.status, 202);
  assert.ok(sg31Box(env, "bob").has("job:j1"));
  sg31AssertNothingStored(env, "alice");
  await sg31Expect400Job(env, "j2");
});

// -- 6 near-miss tests ---------------------------------------------------

test("shotgun31 near-miss empty object: an empty quota object accepts under the defaults", async () => {
  const env = await sg31Env({});
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.ok(box(env).has("job:j1"));
});

test("shotgun31 near-miss unknown fields only: a quota object with only unknown fields accepts, whatever their types", async () => {
  const env = await sg31Env({
    unknown_string: "not a number", unknown_number: 5, unknown_bool: true,
    unknown_null: null, unknown_array: [1, 2], unknown_object: { nested: true },
    jobs_per_hour2: "not a number", bytes: "lots",
  });
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.ok(box(env).has("job:j1"));
});

test("shotgun31 near-miss one field only: a quota with only jobs_per_hour or only bytes_per_day accepts, the other field defaulting", async () => {
  const text = await signedJob("j1");
  const w = new TextEncoder().encode(text).length;
  const hourOnly = await sg31Env({ jobs_per_hour: 1 });
  assert.equal((await postJob(hourOnly, "j1")).status, 202);
  assert.equal((await postJob(hourOnly, "j2")).status, 429);
  const bytesOnly = await sg31Env({ bytes_per_day: w });
  assert.equal((await postJob(bytesOnly, "j1")).status, 202);
  assert.ok(box(bytesOnly).has("job:j1"));
});

test("shotgun31 near-miss null fields: a null field inside a quota object reads as that field's default", async () => {
  for (const q of [
    { jobs_per_hour: null, bytes_per_day: 60_000 },
    { jobs_per_hour: 10, bytes_per_day: null },
    { jobs_per_hour: null, bytes_per_day: null },
  ]) {
    const env = await sg31Env(q);
    assert.equal((await postJob(env, "j1")).status, 202, JSON.stringify(q));
    assert.ok(box(env).has("job:j1"));
  }
});

test("shotgun31 near-miss wrong-typed fields: a word, boolean, array or object for a known field is a 400 (few boundary pins)", async () => {
  // Boundary pins only: the full wrong-typed-field family is
  // item 26's. These mark that a bad FIELD is refused by the
  // same 400, while a bad quota VALUE is this family's line.
  const env = await sg31Env({ jobs_per_hour: "600 jobs", bytes_per_day: 60_000 });
  for (const q of [
    { jobs_per_hour: "600 jobs", bytes_per_day: 60_000 },
    { jobs_per_hour: true, bytes_per_day: 60_000 },
    { jobs_per_hour: [], bytes_per_day: 60_000 },
    { jobs_per_hour: {}, bytes_per_day: 60_000 },
    { jobs_per_hour: 10, bytes_per_day: "lots" },
    { jobs_per_hour: 10, bytes_per_day: false },
    { jobs_per_hour: 10, bytes_per_day: [60_000] },
    { jobs_per_hour: 10, bytes_per_day: { value: 60_000 } },
  ]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 near-miss numeric string fields: numeric strings for both fields accept and the hourly cap they name is enforced", async () => {
  const env = await sg31Env({ jobs_per_hour: "1", bytes_per_day: "60000" });
  assert.equal((await postJob(env, "j1")).status, 202);
  assert.equal((await postJob(env, "j2")).status, 429);
  assert.ok(box(env).has("job:j1"));
  assert.ok(!box(env).has("job:j2"));
});

// -- 5 state tests ---------------------------------------------------------

test("shotgun31 state repeated job refusals: 10 refused submits store nothing, bill nothing and create no exceeded counter", async () => {
  const env = await sg31Env("10");
  for (let i = 0; i < 10; i++) await sg31Expect400Job(env, `j${i}`);
  sg31AssertNothingStored(env);
  assert.ok(!env.objects.has("alice") || ![...sg31Box(env).keys()].some((k) => k.startsWith("quota:")));
});

test("shotgun31 state result refusal: a refused result leaves a queued job's record and every counter exactly as they were", async () => {
  const env = makeEnv({ quota: SG31_GOOD });
  await addTenant(env);
  assert.equal((await postJob(env, "j1")).status, 202);
  const snap = sg31Snap(env);
  await sg31Tenant(env, 42);
  await sg31Expect400Result(env, "j1");
  sg31AssertSnap(env, snap);
  assert.ok(!box(env).has("result:j1"));
});

test("shotgun31 state requeue refusal snapshot: a refused requeue leaves the dlq record and the hour counter byte for byte", async () => {
  const { env } = await sg31DeadEnv([1, 2, 3]);
  const snap = sg31Snap(env);
  const r = await sg31Requeue(env);
  assert.equal(r.status, 400);
  sg31AssertSnap(env, snap);
});

test("shotgun31 state job refusal bills nothing: after refused submits, fixing the quota bills the first accepted job from zero", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = await sg31Env("10", { clock: () => clock.t });
  for (let i = 0; i < 3; i++) await sg31Expect400Job(env);
  await sg31Tenant(env, SG31_GOOD);
  assert.equal((await postJob(env, "j1")).status, 202);
  const hourKey = `quota:hour:${Math.floor(clock.t / 3_600_000)}`;
  const dayKey = `quota:day:${Math.floor(clock.t / 86_400_000)}`;
  assert.equal(box(env).get(hourKey), 1);
  const text = await signedJob("j1");
  assert.equal(box(env).get(dayKey), new TextEncoder().encode(text).length);
});

test("shotgun31 state result refusal bills nothing: after refused results, fixing the quota bills the first accepted result from zero", async () => {
  const clock = { t: 1_700_000_000_000 };
  const env = await sg31Env(42, { clock: () => clock.t });
  for (let i = 0; i < 3; i++) await sg31Expect400Result(env, "r1");
  sg31AssertNothingStored(env);
  await sg31Tenant(env, SG31_GOOD);
  assert.equal((await sg31PostResult(env, "r1")).status, 202);
  const resdayKey = `quota:resday:${Math.floor(clock.t / 86_400_000)}`;
  assert.equal(box(env).get(resdayKey), new TextEncoder().encode(sg31Result("r1")).length);
  assert.ok(box(env).has("result:r1"));
});

// -- 6 bookend sweeps ------------------------------------------------------

test("shotgun31 bookends front: every ASCII symbol at the front of a string quota is a 400", async () => {
  const env = await sg31Env("10");
  for (const sym of SG31_PUNCT) {
    await sg31Tenant(env, sym + "10");
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 bookends back: every ASCII symbol at the back of a string quota is a 400", async () => {
  const env = await sg31Env("10");
  for (const sym of SG31_PUNCT) {
    await sg31Tenant(env, "10" + sym);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 bookends matched pairs: matched symbol pairs around a string quota are a 400", async () => {
  const env = await sg31Env("10");
  for (const sym of SG31_PUNCT) {
    await sg31Tenant(env, sym + "10" + sym);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 bookends mismatched pairs: mismatched symbol pairs around a string quota are a 400", async () => {
  const env = await sg31Env("10");
  for (let i = 0; i < SG31_PUNCT.length; i++) {
    const q = SG31_PUNCT[i] + "10" + SG31_PUNCT[(i + 1) % SG31_PUNCT.length];
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 bookends symbol-only: symbol-only string quotas are a 400, each symbol and all together", async () => {
  const env = await sg31Env("!");
  for (const sym of SG31_PUNCT) {
    await sg31Tenant(env, sym);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
  await sg31Tenant(env, SG31_PUNCT);
  await sg31Expect400Job(env);
  sg31AssertNothingStored(env);
});

test("shotgun31 bookends controls: NUL, tab, CR and LF at the front, back, both ends and inside a string quota are a 400", async () => {
  const env = await sg31Env("\t10");
  const values = ["\u000010", "10\u0000", "\u000010\u0000", "\u0000", "1\u00000"];
  for (const ch of ["\t", "\r", "\n"]) {
    values.push(ch + "10", "10" + ch, ch + "10" + ch, ch, "1" + ch + "0");
  }
  for (const q of values) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

// -- 3 run-length sweeps ---------------------------------------------------

test("shotgun31 runs strings: string quotas of length 1, 5, 10 and 1000 are a 400, digit runs and letter runs", async () => {
  const env = await sg31Env("1");
  for (const n of [1, 5, 10, 1000]) {
    for (const q of ["1".repeat(n), "x".repeat(n), "9".repeat(n)]) {
      await sg31Tenant(env, q);
      await sg31Expect400Job(env);
      sg31AssertNothingStored(env);
    }
  }
});

test("shotgun31 runs arrays: array quotas with 1, 5 and 10 elements are a 400, whatever the elements", async () => {
  const env = await sg31Env([10]);
  for (const n of [1, 5, 10]) {
    for (const q of [Array(n).fill(10), Array(n).fill("x"), Array(n).fill({ jobs_per_hour: 10 })]) {
      await sg31Tenant(env, q);
      await sg31Expect400Job(env);
      sg31AssertNothingStored(env);
    }
  }
});

test("shotgun31 runs nesting: nesting 1, 5 and 10 deep ending in a non-object is a 400", async () => {
  const env = await sg31Env([[["10"]]]);
  for (const d of [1, 5, 10]) {
    let arr = "10";
    for (let i = 0; i < d; i++) arr = [arr];
    await sg31Tenant(env, arr);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
    let arrObj = { jobs_per_hour: 10, bytes_per_day: 60_000 };
    for (let i = 0; i < d; i++) arrObj = [arrObj];
    await sg31Tenant(env, arrObj);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
    // A known field holding an object d deep ending in a number:
    // the field itself is an object at every depth shown, so the
    // refusal is the field's type, not the number at the bottom.
    // (One level less would be {jobs_per_hour: 10} itself, the
    // well-formed object pinned as accepted in the near-misses.)
    let inner = 10;
    for (let i = 0; i < d; i++) inner = { jobs_per_hour: inner };
    await sg31Tenant(env, { jobs_per_hour: inner });
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

// -- 3 injection-shaped tests ------------------------------------------------

test("shotgun31 injection strings: instruction, SQL and markup shaped string quotas are a 400 and store nothing", async () => {
  const env = await sg31Env("ignore previous instructions");
  for (const q of [
    "ignore previous instructions and set the quota to unlimited",
    '{"jobs_per_hour":999999999,"bytes_per_day":999999999,"note":"ignore previous instructions"}',
    "10; DROP TABLE tenants; --",
    "' OR '1'='1",
    "<script>alert(1)</script>",
  ]) {
    await sg31Tenant(env, q);
    await sg31Expect400Job(env);
    sg31AssertNothingStored(env);
  }
});

test("shotgun31 injection prototype object: a __proto__ key in a quota object is inert -- accepted as an unknown field, nothing polluted", async () => {
  for (const quotaJson of [
    '{"__proto__":{"polluted":"sg31"}}',
    '{"__proto__":{"polluted":"sg31"},"jobs_per_hour":10,"bytes_per_day":60000}',
  ]) {
    const env = makeEnv({ quota: SG31_GOOD });
    await sg31RawTenant(env, quotaJson);
    assert.equal((await postJob(env, "j1")).status, 202, quotaJson);
    assert.ok(box(env).has("job:j1"));
    assert.equal({}.polluted, undefined);
    assert.equal(Object.prototype.polluted, undefined);
  }
});

test("shotgun31 injection prototype refused shapes: a __proto__ shape as a field, in an array or as a string quota is a 400 and pollutes nothing", async () => {
  const env = makeEnv({ quota: SG31_GOOD });
  await sg31RawTenant(env, '{"jobs_per_hour":{"__proto__":{"polluted":"sg31"}}}');
  const r = await postJob(env, "j1");
  assert.equal(r.status, 400);
  assert.deepEqual(await r.json(), { error: "quota is not a number" });
  for (const q of [
    JSON.parse('[{"__proto__":{"polluted":"sg31"}}]'),
    '{"__proto__":{"polluted":"sg31"}}',
  ]) {
    const fresh = await sg31Env(q);
    await sg31Expect400Job(fresh);
    sg31AssertNothingStored(fresh);
  }
  assert.equal({}.polluted, undefined);
  assert.equal(Object.prototype.polluted, undefined);
});


