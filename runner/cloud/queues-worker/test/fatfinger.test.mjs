// Ordinary mistakes: a clock step, a second click, a blank quota
// field. Not an attack. Each test is one story and then the storage.
import { test } from "node:test";
import assert from "node:assert/strict";

import worker, { TenantQueue, hmacSha384Hex, sha256Hex, DEFAULT_QUOTA } from "../src/index.js";

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
