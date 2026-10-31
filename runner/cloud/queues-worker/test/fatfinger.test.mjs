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
  assert.equal(r.status, 404);
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
