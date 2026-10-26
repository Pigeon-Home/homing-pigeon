// Unit tests for the hosted queue Worker, under node's own test
// runner: `node --test cloudflare/queues-worker/test/`. No wrangler,
// no network: the Durable Object namespace and KV are in-memory
// fakes with the same shapes the runtime hands the Worker.
import { test } from "node:test";
import assert from "node:assert/strict";

import worker, {
  TenantQueue, hmacSha384Hex, sha256Hex, parseEnvelope,
  extractSigAndPayload, jobIdOf, resultIdOf, DEFAULT_QUOTA,
} from "../src/index.js";

class FakeStorage {
  constructor() { this.map = new Map(); }
  async get(k) { return this.map.has(k) ? structuredClone(this.map.get(k)) : undefined; }
  async put(k, v) { this.map.set(k, structuredClone(v)); }
  async delete(k) { return this.map.delete(k); }
  async list({ prefix = "", limit = Infinity } = {}) {
    const out = new Map();
    for (const k of [...this.map.keys()].sort()) {
      if (out.size >= limit) break;
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
    TENANTS: {
      store: new Map(),
      async get(k) { return this.store.get(k) ?? null; },
    },
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

async function signedJob(jobId, secret = SECRET) {
  const payload = JSON.stringify({ v: 1, type: "job", job_id: jobId, kind: "exec", script: "echo hi" });
  const sig = await hmacSha384Hex(secret, payload);
  const body = payload.slice(0, -1) + `,"sig":"${sig}"}`;
  return `[HOMING-PIGEON] job ${jobId}\n\n${body}\n`;
}

function req(path, { method = "GET", token, body, headers = {} } = {}) {
  const h = { ...headers };
  if (token) h.authorization = `Bearer ${token}`;
  return new Request("https://hp.example.test" + path, { method, headers: h, body });
}

test("helpers: envelope, sig splice, ids", async () => {
  const env = await signedJob("j1");
  const p = parseEnvelope(env);
  assert.equal(p.subject, "[HOMING-PIGEON] job j1");
  const ex = extractSigAndPayload(p.body);
  assert.match(ex.sig, /^[0-9a-f]{96}$/);
  assert.equal(JSON.parse(ex.payload).job_id, "j1");
  assert.equal(jobIdOf("[HOMING-PIGEON] job abc"), "abc");
  assert.equal(jobIdOf("[HOMING-PIGEON] v2 job abc"), "abc");
  assert.equal(jobIdOf("hello"), null);
  assert.equal(resultIdOf("[HOMING-PIGEON] result abc"), "abc");
  assert.equal(resultIdOf("[HOMING-PIGEON] qresult abc"), "abc");
  assert.equal(parseEnvelope("no blank line"), null);
  assert.equal(extractSigAndPayload('{"a":1}'), null);
});

test("unknown tenant and routes are 404; health is open", async () => {
  const env = makeEnv();
  assert.equal((await worker.fetch(req("/health"), env)).status, 200);
  assert.equal((await worker.fetch(req("/t/nobody/jobs", { method: "POST", token: SI, body: "x" }), env)).status, 404);
  assert.equal((await worker.fetch(req("/nope"), env)).status, 404);
  await addTenant(env);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "DELETE", token: SI }), env)).status, 405);
});

test("tokens gate each role", async () => {
  const env = makeEnv();
  await addTenant(env);
  const job = await signedJob("j1");
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", body: job }), env)).status, 401);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: RUNNER, body: job }), env)).status, 401);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { token: SI }), env)).status, 401);
  assert.equal((await worker.fetch(req("/t/alice/results", { token: RUNNER }), env)).status, 401);
  assert.equal((await worker.fetch(req("/t/alice/results", { method: "POST", token: SI, body: "x\n\ny" }), env)).status, 401);
});

test("the HMAC gate: bad signature 403, no sig 400, off when disabled", async () => {
  const env = makeEnv();
  await addTenant(env);
  const bad = await signedJob("j1", "wrong-secret");
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: bad }), env)).status, 403);
  const nosig = "[HOMING-PIGEON] job j2\n\n{\"v\":1}\n";
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: nosig }), env)).status, 400);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: "nothing here" }), env)).status, 400);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: "[HOMING-PIGEON] hello\n\n{}" }), env)).status, 400);
  const off = makeEnv({ reject: "false" });
  await addTenant(off);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: bad }), off)).status, 202);
});

test("a tenant without a secret cannot accept jobs while the gate is on", async () => {
  const env = makeEnv();
  await addTenant(env, "alice", { hmac_secret: null });
  const job = await signedJob("j1");
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: job }), env)).status, 500);
});

test("submit, lease, ack, result, read, ack: the whole loop", async () => {
  const env = makeEnv();
  await addTenant(env);
  const job = await signedJob("j1");
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: job }), env);
  assert.equal(r.status, 202);
  assert.deepEqual(await r.json(), { id: "j1" });
  // A duplicate submit is acknowledged, not queued twice.
  r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: job }), env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).duplicate, true);
  // The runner leases it.
  r = await worker.fetch(req("/t/alice/jobs?max=5", { token: RUNNER }), env);
  assert.equal(r.status, 200);
  const pulled = await r.json();
  assert.equal(pulled.jobs.length, 1);
  assert.equal(pulled.jobs[0].id, "j1");
  assert.equal(pulled.jobs[0].envelope, job);
  // Leased: a second pull inside the lease is empty.
  r = await worker.fetch(req("/t/alice/jobs", { token: RUNNER }), env);
  assert.equal(r.status, 204);
  // The result comes back and the job is acked.
  const result = "[HOMING-PIGEON] result j1\n\n{\"exit_code\":0,\"sig\":\"00\"}\n";
  r = await worker.fetch(req("/t/alice/results", { method: "POST", token: RUNNER, body: result }), env);
  assert.equal(r.status, 202);
  r = await worker.fetch(req("/t/alice/jobs/j1/ack", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 204);
  r = await worker.fetch(req("/t/alice/jobs/j1/ack", { method: "POST", token: RUNNER }), env);
  assert.equal(r.status, 404);
  // The SI reads and acks the result.
  r = await worker.fetch(req("/t/alice/results", { token: SI }), env);
  assert.equal(r.status, 200);
  const results = await r.json();
  assert.equal(results.results[0].id, "j1");
  assert.equal(results.results[0].envelope, result);
  r = await worker.fetch(req("/t/alice/results/j1/ack", { method: "POST", token: SI }), env);
  assert.equal(r.status, 204);
  r = await worker.fetch(req("/t/alice/results", { token: SI }), env);
  assert.equal(r.status, 204);
});

test("a lease expires and the job is offered again; five attempts dead-letter it", async () => {
  let now = 1_000_000;
  const env = makeEnv({ lease: 1000, clock: () => now });
  await addTenant(env);
  await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: await signedJob("j1") }), env);
  for (let attempt = 1; attempt <= 5; attempt++) {
    const r = await worker.fetch(req("/t/alice/jobs", { token: RUNNER }), env);
    assert.equal(r.status, 200, `attempt ${attempt}`);
    assert.equal((await r.json()).jobs[0].attempt, attempt);
    now += 2000; // past the lease, nobody acked
  }
  const r = await worker.fetch(req("/t/alice/jobs", { token: RUNNER }), env);
  assert.equal(r.status, 204);
  const storage = env.objects.get("alice").state.storage;
  assert.ok(storage.map.has("dlq:j1"));
  assert.ok(!storage.map.has("job:j1"));
});

test("the quota is a hard stop with a retry hint, and counts only accepted jobs", async () => {
  const env = makeEnv({ quota: { jobs_per_hour: 2, bytes_per_day: 10_000 } });
  await addTenant(env);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: await signedJob("a") }), env)).status, 202);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: await signedJob("b") }), env)).status, 202);
  const r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: await signedJob("c") }), env);
  assert.equal(r.status, 429);
  assert.ok(Number(r.headers.get("retry-after")) > 0);
  assert.equal((await r.json()).jobs_this_hour, 2);
  // Rejected-at-the-gate jobs never count against the quota.
  const tight = makeEnv({ quota: { jobs_per_hour: 1, bytes_per_day: 10_000 } });
  await addTenant(tight);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: await signedJob("x", "bad") }), tight)).status, 403);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: await signedJob("y") }), tight)).status, 202);
  // Bytes per day stops a big envelope even with job count to spare.
  const small = makeEnv({ quota: { jobs_per_hour: 100, bytes_per_day: 100 } });
  await addTenant(small);
  const big = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: SI, body: await signedJob("z") }), small);
  assert.equal(big.status, 429);
});

test("single-tenant env fallback works without KV", async () => {
  const env = makeEnv();
  delete env.TENANTS;
  env.TENANT = "solo";
  env.SI_TOKEN = SI;
  env.RUNNER_TOKEN = RUNNER;
  env.HMAC_SECRET = SECRET;
  assert.equal((await worker.fetch(req("/t/solo/jobs", { method: "POST", token: SI, body: await signedJob("j1") }), env)).status, 202);
  assert.equal((await worker.fetch(req("/t/other/jobs", { method: "POST", token: SI, body: await signedJob("j1") }), env)).status, 404);
});
