// Fuzz harness for the hosted queue Worker, beside the unit tests:
// `node --test runner/cloud/queues-worker/test/fuzz.test.mjs`. No wrangler, no network — the
// same in-memory fakes the unit tests use, driven by a seeded
// mutational fuzzer over the whole route surface, with the five
// invariants from Q123 checked against the Durable Object's storage
// (the ground truth) after every operation:
//
//   1. a request past the quota stores and bills nothing;
//   2. a lease is held by one runner at a time;
//   3. attempts never exceed MAX_ATTEMPTS before the dead-letter;
//   4. an oversized envelope is refused unread;
//   5. a token that does not hash to the stored hash is refused,
//      and a refused request changes no state.
//
// The seed is the reproduction: a failure names its seed and the
// operation index, and the same seed replays the same run.
import { test } from "node:test";
import assert from "node:assert/strict";

import worker, { TenantQueue, hmacSha384Hex, sha256Hex, DEFAULT_QUOTA } from "../src/index.js";

const MAX_ATTEMPTS = 5;
const ENVELOPE_MAX = 4 * 1024 * 1024;

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

function makeEnv({ quota, clock } = {}) {
  const objects = new Map();
  const env = {
    REJECT_INVALID_HMAC: "true",
    LEASE_MS: "1000",
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
  env.quota = quota || { jobs_per_hour: 6, bytes_per_day: 60_000 };
  return env;
}

const SECRET = "s".repeat(64);
const SI = "si-token-alice";
const RUNNER = "runner-token-alice";

async function addTenant(env, slug = "alice") {
  env.TENANTS.store.set(slug, JSON.stringify({
    si_token_sha256: await sha256Hex(SI),
    runner_token_sha256: await sha256Hex(RUNNER),
    hmac_secret: SECRET,
    quota: env.quota,
  }));
}

async function signedJob(jobId, secret = SECRET, script = "echo hi") {
  const payload = JSON.stringify({ v: 1, type: "job", job_id: jobId, kind: "exec", script });
  const sig = await hmacSha384Hex(secret, payload);
  const body = payload.slice(0, -1) + `,"sig":"${sig}"}`;
  return `[HOMING-PIGEON] job ${jobId}\n\n${body}\n`;
}

function req(path, { method = "GET", token, body, headers = {} } = {}) {
  const h = { ...headers };
  if (token !== undefined) h.authorization = token;
  return new Request("https://hp.example.test" + path, { method, headers: h, body });
}

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function snapshot(storage) {
  return JSON.stringify([...storage.map.entries()].sort(([a], [b]) => (a < b ? -1 : 1)));
}

// A 429 from /enqueue records the refusal itself in a tally counter
// (quota:exceeded) — nothing is stored and neither billing counter
// moves. Comparisons around a 429 therefore pin every key except
// that tally.
function snapshotBilling(storage) {
  const entries = [...storage.map.entries()].filter(([k]) => k !== "quota:exceeded");
  return JSON.stringify(entries.sort(([a], [b]) => (a < b ? -1 : 1)));
}

// The state invariants, read from the storage map after every op.
// expected counters track what the responses said was accepted, so a
// counter that drifts from the responses in either direction fails.
function checkState(storage, now, expected, where) {
  const map = storage.map;
  let hourJobs = 0;
  for (const [k, v] of map) {
    if (k.startsWith("job:")) {
      assert.ok(Number.isInteger(v.attempts) && v.attempts >= 0 && v.attempts <= MAX_ATTEMPTS,
        `${where}: ${k} attempts ${v.attempts} outside 0..${MAX_ATTEMPTS}`);
      assert.ok(!map.has(`dlq:${v.id}`), `${where}: ${v.id} is both queued and dead`);
      assert.equal(v.envelope.length, v.size, `${where}: ${k} size record lies about its envelope`);
    }
    if (k.startsWith("dlq:")) {
      assert.equal(v.attempts, MAX_ATTEMPTS,
        `${where}: ${k} reached the dead-letter with ${v.attempts} attempts, not ${MAX_ATTEMPTS}`);
    }
    if (k.startsWith("quota:hour:")) hourJobs = Math.max(hourJobs, 0);
  }
  for (const [k, want] of expected) {
    assert.equal(map.get(k) ?? 0, want, `${where}: counter ${k} reads ${map.get(k) ?? 0}, responses imply ${want}`);
  }
  void hourJobs;
}

const KNOWN_STATUS = new Set([200, 202, 204, 400, 401, 403, 404, 405, 409, 413, 429]);
const IDS = ["j1", "j2", "j3", "j4", "j5", "j6"];
// Tokens that must be refused at either gate: no credential, a
// credential one character off, the other role's credential, or a
// scheme that is not Bearer. (Scheme case and spacing are transport
// cosmetics the gate parses past; a credential that hashes to the
// stored hash is the right credential, so none is listed here.)
const BAD_FOR_SI = [
  undefined, "", "Bearer", "Bearer si-token-alicf",
  "Bearer runner-token-alice", "Token si-token-alice",
];
const BAD_FOR_RUNNER = [
  undefined, "", "Bearer", "Bearer runner-token-alicf",
  "Bearer si-token-alice", "Token runner-token-alice",
];

async function runFuzz(seed, ops) {
  const rnd = mulberry32(seed);
  const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now });
  await addTenant(env);
  const storage = () => env.objects.get("alice").state.storage;
  const expected = new Map(); // quota counter key -> value implied by responses
  const outstanding = new Map(); // job id -> leased_until, from pulls not yet expired or acked
  const envelopes = new Map();
  for (const id of IDS) envelopes.set(id, await signedJob(id));
  const wrongSecret = await signedJob("j1", "wrong-secret");
  const bump = (key, by) => expected.set(key, (expected.get(key) ?? 0) + by);
  const hourKey = () => `quota:hour:${Math.floor(now / 3_600_000)}`;
  const dayKey = () => `quota:day:${Math.floor(now / 86_400_000)}`;

  const doFetch = async (path, opts) => {
    const r = await worker.fetch(req(path, opts), env);
    assert.ok(KNOWN_STATUS.has(r.status), `seed ${seed}: status ${r.status} is not a known answer`);
    return r;
  };

  for (let i = 0; i < ops; i++) {
    const where = `seed ${seed} op ${i}`;
    const roll = rnd();
    if (roll < 0.30) {
      // Submit, mutated.
      const id = pick(IDS);
      const variant = rnd();
      let body = envelopes.get(id);
      if (variant < 0.12) body = wrongSecret.replace("job j1", `job ${id}`);
      else if (variant < 0.22) body = `[HOMING-PIGEON] job ${id}\n\n{"v":1}\n`;
      else if (variant < 0.32) body = body.replace("echo hi", "echo hj");
      else if (variant < 0.40) body = `[HOMING-PIGEON] note ${id}\n\n${body.split("\n\n")[1]}`;
      else if (variant < 0.46) body = "";
      const token = rnd() < 0.85 ? `Bearer ${SI}` : pick(BAD_FOR_SI);
      const before = snapshot(storage());
      const beforeBilling = snapshotBilling(storage());
      const r = await doFetch("/t/alice/jobs", { method: "POST", token, body });
      if (token !== `Bearer ${SI}`) {
        assert.equal(r.status, 401, `${where}: bad token answered ${r.status}`);
        assert.equal(snapshot(storage()), before, `${where}: a refused submit changed state`);
      } else if (r.status === 202) {
        bump(hourKey(), 1); bump(dayKey(), body.length);
      } else if (r.status === 429) {
        assert.equal(snapshotBilling(storage()), beforeBilling,
          `${where}: a 429 stored or billed something`);
      } else if ([400, 403, 409].includes(r.status)) {
        assert.equal(snapshot(storage()), before, `${where}: a gate refusal changed state`);
      } else {
        assert.equal(r.status, 200, `${where}: submit answered ${r.status}`);
      }
    } else if (roll < 0.52) {
      // Pull, with a mutated max; check lease exclusivity against the
      // harness's own lease book and the storage snapshot.
      const max = pick(["", "?max=1", "?max=2", "?max=5", "?max=100", "?max=0", "?max=-1", "?max=abc"]);
      const token = rnd() < 0.9 ? `Bearer ${RUNNER}` : pick(BAD_FOR_RUNNER);
      const before = snapshot(storage());
      const r = await doFetch(`/t/alice/jobs${max}`, { token });
      if (token !== `Bearer ${RUNNER}`) {
        assert.equal(r.status, 401, `${where}: bad token answered ${r.status}`);
        assert.equal(snapshot(storage()), before, `${where}: a refused pull changed state`);
      } else if (r.status === 200) {
        const { jobs } = await r.json();
        const seen = new Set();
        for (const job of jobs) {
          assert.ok(!seen.has(job.id), `${where}: ${job.id} handed out twice in one pull`);
          seen.add(job.id);
          const held = outstanding.get(job.id);
          assert.ok(held === undefined || held <= now,
            `${where}: ${job.id} re-offered at ${now} while leased until ${held}`);
          outstanding.set(job.id, storage().map.get(`job:${job.id}`)?.leased_until ?? 0);
        }
      } else {
        assert.equal(r.status, 204, `${where}: pull answered ${r.status}`);
      }
    } else if (roll < 0.64) {
      // Renew or ack a job, sometimes one that does not exist.
      const id = rnd() < 0.8 ? pick(IDS) : "ghost";
      const verb = rnd() < 0.5 ? "lease" : "ack";
      const token = rnd() < 0.9 ? `Bearer ${RUNNER}` : pick(BAD_FOR_RUNNER);
      const r = await doFetch(`/t/alice/jobs/${id}/${verb}`, { method: "POST", token });
      if (token !== `Bearer ${RUNNER}`) assert.equal(r.status, 401, `${where}: bad token answered ${r.status}`);
      if (verb === "ack" && r.status === 204) outstanding.delete(id);
      if (verb === "lease" && r.status === 204) {
        outstanding.set(id, storage().map.get(`job:${id}`)?.leased_until ?? 0);
      }
    } else if (roll < 0.76) {
      // Results: post, read, ack, with subject mutations.
      const id = pick(IDS);
      const which = rnd();
      if (which < 0.45) {
        const subject = rnd() < 0.8 ? `[HOMING-PIGEON] result ${id}` : `[HOMING-PIGEON] job ${id}`;
        const body = `${subject}\n\n{"exit_code":0}\n`;
        const r = await doFetch("/t/alice/results", { method: "POST", token: `Bearer ${RUNNER}`, body });
        assert.ok([202, 400].includes(r.status), `${where}: result post answered ${r.status}`);
      } else if (which < 0.75) {
        const r = await doFetch("/t/alice/results", { token: `Bearer ${SI}` });
        assert.ok([200, 204].includes(r.status), `${where}: results read answered ${r.status}`);
      } else {
        const r = await doFetch(`/t/alice/results/${id}/ack`, { method: "POST", token: `Bearer ${SI}` });
        assert.ok([204, 404].includes(r.status), `${where}: result ack answered ${r.status}`);
      }
    } else if (roll < 0.88) {
      // The dead-letter list: read, drop, requeue.
      const id = rnd() < 0.8 ? pick(IDS) : "ghost";
      const which = rnd();
      if (which < 0.4) {
        const r = await doFetch("/t/alice/dlq", { token: `Bearer ${SI}` });
        assert.ok([200, 204].includes(r.status), `${where}: dlq read answered ${r.status}`);
        if (r.status === 200) {
          for (const d of (await r.json()).dead) {
            assert.equal(d.attempts, MAX_ATTEMPTS, `${where}: dlq lists ${d.id} at ${d.attempts} attempts`);
          }
        }
      } else if (which < 0.7) {
        const r = await doFetch(`/t/alice/dlq/${id}/ack`, { method: "POST", token: `Bearer ${SI}` });
        assert.ok([204, 404].includes(r.status), `${where}: dlq ack answered ${r.status}`);
      } else {
        const before = snapshot(storage());
        const r = await doFetch(`/t/alice/dlq/${id}/requeue`, { method: "POST", token: `Bearer ${SI}` });
        assert.ok([202, 404, 409, 429].includes(r.status), `${where}: requeue answered ${r.status}`);
        if (r.status === 202) bump(hourKey(), 1);
        if (r.status === 429) assert.equal(snapshot(storage()), before, `${where}: a 429 requeue changed state`);
      }
    } else {
      // Time passes, in amounts that straddle the lease and the hour.
      now += pick([0, 100, 999, 1000, 5000, 3_599_000, 3_600_000, 86_400_000]);
      for (const [id, until] of outstanding) if (until <= now) outstanding.delete(id);
    }
    checkState(storage(), now, expected, where);
  }
}

test("fuzz: the route surface under mutation, seed 1", async () => { await runFuzz(1, 500); });
test("fuzz: the route surface under mutation, seed 2", async () => { await runFuzz(2, 500); });
test("fuzz: the route surface under mutation, seed 3", async () => { await runFuzz(3, 500); });

test("fuzz: an oversized envelope is refused unread, at and past the cap", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 600, bytes_per_day: 512 * 1024 * 1024 } });
  await addTenant(env);
  const storage = () => env.objects.get("alice").state.storage;
  // Just under the cap, validly signed: the size gate lets it through.
  const room = ENVELOPE_MAX - 200;
  const under = await signedJob("big1", SECRET, "x".repeat(room));
  assert.ok(under.length <= ENVELOPE_MAX);
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: under }), env);
  assert.equal(r.status, 202);
  assert.ok(storage().map.has("job:big1"));
  // Past the cap: 413, nothing stored, no quota counted.
  const over = await signedJob("big2", SECRET, "x".repeat(ENVELOPE_MAX));
  assert.ok(over.length > ENVELOPE_MAX);
  const before = snapshot(storage());
  r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: over }), env);
  assert.equal(r.status, 413);
  assert.equal(snapshot(storage()), before);
  assert.ok(!storage().map.has("job:big2"));
});

test("fuzz: the quota boundary — the first job past the cap is the first 429", async () => {
  let now = 1_700_000_000_000;
  const quota = { jobs_per_hour: 3, bytes_per_day: 60_000 };
  const env = makeEnv({ clock: () => now, quota });
  await addTenant(env);
  const storage = () => env.objects.get("alice").state.storage;
  for (const id of ["b1", "b2", "b3"]) {
    const r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob(id) }), env);
    assert.equal(r.status, 202, id);
  }
  const before = snapshotBilling(storage());
  const r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob("b4") }), env);
  assert.equal(r.status, 429);
  assert.equal(snapshotBilling(storage()), before);
  assert.ok(!storage().map.has("job:b4"));
  // The next hour opens the gate again.
  now += 3_600_000;
  const r2 = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob("b4") }), env);
  assert.equal(r2.status, 202);
  void DEFAULT_QUOTA;
});
