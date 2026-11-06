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
// A seeded operation that sends two requests runs them in issue
// order, so the same seed replays. The pinned test is the one that
// races two pulls. The fake applies the Durable Object input gate:
// one object fetch runs at a time, because this handler only awaits
// storage once it has the body. A job id in both answers is a failure.
//
// A tuple is the route, the status, and what the storage showed:
// the key prefixes, whether a job is leased (`held`), the highest
// attempt still queued (`att:N`), the result byte counter
// (`quota:resday`, separate from the job day), and on a 429 which
// cap fired (`cap:hour` or `cap:day`). The first seed and operation that
// reached each tuple is kept in fuzz.corpus.json. The replay runs
// those prefixes before the long seed spends its budget. A failure
// names its seed and the operation index, and the same seed replays
// the same run. HP_FUZZ_WRITE=1 rewrites the corpus from what this
// process saw.
import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import worker, { TenantQueue, hmacSha384Hex, sha256Hex, DEFAULT_QUOTA, DO_VALUE_MAX, jobStoredBytes, storagePairBytes, RESPONSE_BUDGET, clampedMax } from "../src/index.js";

const MAX_ATTEMPTS = 5;
const LONG_OPS = 20_000;
const CORPUS_PATH = join(dirname(fileURLToPath(import.meta.url)), "fuzz.corpus.json");

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

// One object fetch at a time. A real Durable Object does not deliver
// the next request while this one is waiting on storage, and this
// object's handler does not await anything else after that. Without
// the gate the fake's Map would interleave two pulls and report a
// double lease the runtime does not have.
function withInputGate(fetchFn) {
  let tail = Promise.resolve();
  return (request) => {
    const run = tail.then(() => fetchFn(request));
    tail = run.then(() => {}, () => {});
    return run;
  };
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
          obj.fetch = withInputGate(obj.fetch.bind(obj));
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
const BOB_SECRET = "b".repeat(64);
const BOB_SI = "si-token-bob";
const BOB_RUNNER = "runner-token-bob";

async function addTenant(env, slug = "alice", creds = {}) {
  const si = creds.si || SI;
  const runnerTok = creds.runner || RUNNER;
  const secret = creds.secret || SECRET;
  env.TENANTS.store.set(slug, JSON.stringify({
    si_token_sha256: await sha256Hex(si),
    runner_token_sha256: await sha256Hex(runnerTok),
    hmac_secret: secret,
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
      assert.equal(new TextEncoder().encode(v.envelope).length, v.size, `${where}: ${k} size record lies about its envelope`);
      if (v.leased_until > now) {
        assert.ok(Number.isInteger(v.hand) && v.hand >= 1, `${where}: leased ${k} has no hand`);
      }
    }
    if (k.startsWith("dlq:")) {
      assert.equal(v.attempts, MAX_ATTEMPTS,
        `${where}: ${k} reached the dead-letter with ${v.attempts} attempts, not ${MAX_ATTEMPTS}`);
      assert.ok(Number.isInteger(v.hand) && v.hand >= 1, `${where}: ${k} hand ${v.hand}`);
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
  "Bearer " + "q".repeat(SI.length),
];
const BAD_FOR_RUNNER = [
  undefined, "", "Bearer", "Bearer runner-token-alicf",
  "Bearer si-token-alice", "Token runner-token-alice",
  "Bearer " + "q".repeat(RUNNER.length),
];

function keyPrefixes(box, now = 0, extra = []) {
  const names = new Set();
  let maxAtt = -1;
  let held = false;
  for (const [k, v] of box.map) {
    if (k.startsWith("quota:hour:")) names.add("quota:hour");
    else if (k.startsWith("quota:day:")) names.add("quota:day");
    else if (k.startsWith("quota:resday:")) names.add("quota:resday");
    else if (k.startsWith("quota:")) names.add(k);
    else names.add(k.split(":")[0]);
    if (k.startsWith("job:") && v && typeof v === "object") {
      if (typeof v.attempts === "number" && v.attempts > maxAtt) maxAtt = v.attempts;
      if (v.leased_until > now) held = true;
    }
  }
  if (maxAtt >= 0) names.add("att:" + maxAtt);
  if (held) names.add("held");
  for (const e of extra) names.add(e);
  return [...names].sort();
}

function routeOf(method, path) {
  if (path === "/health") return `${method} /health`;
  const bare = path.split("?")[0];
  const m = bare.match(/^\/t\/([^/]+)\/(jobs|results|dlq)(?:\/[^/]+\/(ack|lease|requeue))?\/?$/);
  if (!m) return `${method} ${bare}`;
  const slug = m[1] === "alice" || m[1] === "bob" ? ":slug" : ":other";
  const tail = m[3] ? `/${m[2]}/:id/${m[3]}` : `/${m[2]}`;
  const query = path.includes("?") ? "?max" : "";
  return `${method} /t/${slug}${tail}${query}`;
}

function tupleOf(route, status, keys) {
  return JSON.stringify([route, status, keys || []]);
}

function loadCorpus() {
  const data = JSON.parse(readFileSync(CORPUS_PATH, "utf8"));
  if (!data || !Array.isArray(data.entries)) throw new Error("fuzz corpus has no entries");
  return data;
}

function writeCorpus(entries) {
  const body = {
    fuzz: 1,
    entries: entries.slice().sort((a, b) => tupleOf(a.route, a.status, a.keys)
      .localeCompare(tupleOf(b.route, b.status, b.keys))),
  };
  writeFileSync(CORPUS_PATH, JSON.stringify(body, null, 1) + "\n");
}

export async function runFuzz(seed, ops) {
  const rnd = mulberry32(seed);
  const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now });
  await addTenant(env);
  await addTenant(env, "bob", { si: BOB_SI, runner: BOB_RUNNER, secret: BOB_SECRET });
  env.TENANT_QUEUE.get("alice");
  const storage = () => env.objects.get("alice").state.storage;
  const bobStorage = () => env.objects.get("bob") && env.objects.get("bob").state.storage;
  const expected = new Map(); // quota counter key -> value implied by responses
  const outstanding = new Map(); // job id -> leased_until, from pulls not yet expired or acked
  const envelopes = new Map();
  for (const id of IDS) envelopes.set(id, await signedJob(id));
  const wrongSecret = await signedJob("j1", "wrong-secret");
  // Bigger than the day cap, smaller than the storage refusal. Signed,
  // so it reaches the quota check. The hour cap is what used to hide it.
  const fat = await signedJob("fat1", SECRET, "x".repeat(env.quota.bytes_per_day));
  assert.ok(fat.length > env.quota.bytes_per_day && fat.length < DO_VALUE_MAX);
  const bobEnvelopes = new Map();
  for (const id of ["b1", "b2"]) bobEnvelopes.set(id, await signedJob(id, BOB_SECRET));
  const bump = (key, by) => expected.set(key, (expected.get(key) ?? 0) + by);
  const hourKey = () => `quota:hour:${Math.floor(now / 3_600_000)}`;
  const dayKey = () => `quota:day:${Math.floor(now / 86_400_000)}`;
  const seenAt = new Map();

  const doFetch = async (method, path, opts) => {
    const r = await worker.fetch(req(path, { method, ...opts }), env);
    assert.ok(KNOWN_STATUS.has(r.status), `seed ${seed}: ${method} ${path} status ${r.status} is not a known answer`);
    const extra = [];
    if (r.status === 429) {
      let jobs = 0;
      try { jobs = (await r.clone().json()).jobs_this_hour ?? 0; } catch { /* not json */ }
      const jph = env.quota.jobs_per_hour ?? DEFAULT_QUOTA.jobs_per_hour;
      extra.push(jobs + 1 > jph ? "cap:hour" : "cap:day");
    }
    const slug = (path.split("?")[0].match(/^\/t\/([^/]+)/) || [])[1];
    const obj = slug && env.objects.get(slug);
    const box = obj ? obj.state.storage : storage();
    const tuple = tupleOf(routeOf(method, path), r.status, keyPrefixes(box, now, extra));
    return { r, tuple };
  };

  const note = (i, tuple) => {
    let set = seenAt.get(i);
    if (!set) seenAt.set(i, set = new Set());
    set.add(tuple);
  };

  const syncOutstanding = () => {
    outstanding.clear();
    for (const [k, v] of storage().map) {
      if (k.startsWith("job:") && v.leased_until > now) outstanding.set(v.id, v.leased_until);
    }
  };

  const readJobs = async (r) => {
    if (r.status !== 200) return [];
    const { jobs } = await r.json();
    return jobs;
  };

  const checkPull = (jobs, book, box, where) => {
    const seen = new Set();
    for (const job of jobs) {
      assert.ok(!seen.has(job.id), `${where}: ${job.id} handed out twice in one pull`);
      seen.add(job.id);
      const held = book.get(job.id);
      assert.ok(held === undefined || held <= now,
        `${where}: ${job.id} re-offered at ${now} while leased until ${held}`);
      const stored = box.map.get(`job:${job.id}`);
      assert.ok(stored, `${where}: pull handed ${job.id}, which is not queued`);
      assert.equal(stored.attempts, job.attempt, `${where}: ${job.id} attempt ${job.attempt} but storage says ${stored && stored.attempts}`);
      assert.equal(stored.hand, job.hand, `${where}: ${job.id} hand ${job.hand} but storage says ${stored && stored.hand}`);
      assert.equal(stored.envelope, job.envelope, `${where}: ${job.id} envelope does not match storage`);
      assert.ok(stored.leased_until > now, `${where}: ${job.id} handed out with no live lease`);
      assert.ok(job.attempt >= 1 && job.attempt <= MAX_ATTEMPTS, `${where}: ${job.id} attempt ${job.attempt}`);
      assert.ok(Number.isInteger(job.hand) && job.hand >= 1, `${where}: ${job.id} hand ${job.hand}`);
    }
  };

  for (let i = 0; i < ops; i++) {
    const where = `seed ${seed} op ${i}`;
    const roll = rnd();
    if (roll < 0.24) {
      const id = (outstanding.size && rnd() < 0.35) ? pick([...outstanding.keys()]) : pick(IDS);
      const variant = rnd();
      let body = envelopes.get(id);
      let path = "/t/alice/jobs";
      let token = rnd() < 0.85 ? `Bearer ${SI}` : pick(BAD_FOR_SI);
      let shaped = "";
      if (variant < 0.10) body = wrongSecret.replace("job j1", `job ${id}`);
      else if (variant < 0.18) body = `[HOMING-PIGEON] job ${id}\n\n{"v":1}\n`;
      else if (variant < 0.26) body = body.replace("echo hi", "echo hj");
      else if (variant < 0.34) body = `[HOMING-PIGEON] note ${id}\n\n${body.split("\n\n")[1]}`;
      else if (variant < 0.42) body = "";
      else if (variant < 0.50) body = body.slice(0, 1 + Math.floor(rnd() * 24));
      else if (variant < 0.58) path = "/t/nobody/jobs";
      else if (variant < 0.70) body = fat;
      else if (variant < 0.78) {
        body = body.replace(/\[HOMING-PIGEON\] job \S+/, "[HOMING-PIGEON] job other");
        shaped = "mismatch";
      } else if (variant < 0.86) {
        body = body.replace(/\[HOMING-PIGEON\] job \S+/, "[HOMING-PIGEON] job a/b");
        shaped = "unsafe";
      }
      const before = snapshot(storage());
      const beforeBilling = snapshotBilling(storage());
      const { r, tuple } = await doFetch("POST", path, { token, body });
      note(i, tuple);
      if (path !== "/t/alice/jobs") {
        assert.equal(r.status, 404, `${where}: unknown tenant answered ${r.status}`);
        assert.equal(snapshot(storage()), before, `${where}: an unknown tenant changed state`);
      } else if (token !== `Bearer ${SI}`) {
        assert.equal(r.status, 401, `${where}: bad token answered ${r.status}`);
        assert.equal(snapshot(storage()), before, `${where}: a refused submit changed state`);
      } else if (shaped) {
        assert.equal(r.status, 400, `${where}: a ${shaped} id answered ${r.status}`);
        assert.equal(snapshot(storage()), before, `${where}: a ${shaped} id changed state`);
      } else if (r.status === 202) {
        bump(hourKey(), 1); bump(dayKey(), new TextEncoder().encode(body).length);
      } else if (r.status === 429) {
        assert.equal(snapshotBilling(storage()), beforeBilling,
          `${where}: a 429 stored or billed something`);
      } else if ([400, 403, 409].includes(r.status)) {
        assert.equal(snapshot(storage()), before, `${where}: a gate refusal changed state`);
      } else {
        assert.equal(r.status, 200, `${where}: submit answered ${r.status}`);
      }
    } else if (roll < 0.40) {
      const max = pick(["", "?max=1", "?max=2", "?max=5", "?max=100", "?max=0", "?max=-1", "?max=abc"]);
      const token = rnd() < 0.9 ? `Bearer ${RUNNER}` : pick(BAD_FOR_RUNNER);
      const before = snapshot(storage());
      const book = new Map(outstanding);
      const { r, tuple } = await doFetch("GET", `/t/alice/jobs${max}`, { token });
      note(i, tuple);
      if (token !== `Bearer ${RUNNER}`) {
        assert.equal(r.status, 401, `${where}: bad token answered ${r.status}`);
        assert.equal(snapshot(storage()), before, `${where}: a refused pull changed state`);
      } else if (r.status === 200) {
        const jobs = await readJobs(r);
        checkPull(jobs, book, storage(), where);
        const bob = bobStorage();
        for (const job of jobs) {
          assert.ok(!(bob && bob.map.has(`job:${job.id}`)),
            `${where}: alice was handed ${job.id}, which bob holds`);
        }
        syncOutstanding();
      } else {
        assert.equal(r.status, 204, `${where}: pull answered ${r.status}`);
      }
    } else if (roll < 0.52) {
      // Two requests, in issue order. Promise.all would let the two
      // token hashes finish in either order, and the seed would not
      // replay. The pinned test is the one that races them.
      const kind = pick(["pull-pull", "pull-ack", "submit-submit"]);
      const book = new Map(outstanding);
      if (kind === "pull-pull") {
        const max = () => pick(["?max=1", "?max=2", "?max=5", ""]);
        const token = () => (rnd() < 0.85 ? `Bearer ${RUNNER}` : pick(BAD_FOR_RUNNER));
        const t1 = token();
        const t2 = token();
        const p1 = `/t/alice/jobs${max()}`;
        const p2 = `/t/alice/jobs${max()}`;
        const a = await doFetch("GET", p1, { token: t1 });
        note(i, a.tuple);
        const jobs = [];
        if (t1 === `Bearer ${RUNNER}` && a.r.status === 200) {
          const list = await readJobs(a.r);
          checkPull(list, book, storage(), where);
          jobs.push(list);
        } else if (t1 !== `Bearer ${RUNNER}`) assert.equal(a.r.status, 401, `${where}: bad token answered ${a.r.status}`);
        const b = await doFetch("GET", p2, { token: t2 });
        note(i, b.tuple);
        if (t2 === `Bearer ${RUNNER}` && b.r.status === 200) {
          const list = await readJobs(b.r);
          checkPull(list, book, storage(), where);
          jobs.push(list);
        } else if (t2 !== `Bearer ${RUNNER}`) assert.equal(b.r.status, 401, `${where}: bad token answered ${b.r.status}`);
        const ids = jobs.flat().map((j) => j.id);
        assert.equal(new Set(ids).size, ids.length, `${where}: ${ids} leased to both pulls`);
        syncOutstanding();
      } else if (kind === "pull-ack") {
        const id = rnd() < 0.8 ? pick(IDS) : "ghost";
        const pull = await doFetch("GET", "/t/alice/jobs?max=5", { token: `Bearer ${RUNNER}` });
        note(i, pull.tuple);
        const jobs = pull.r.status === 200 ? await readJobs(pull.r) : [];
        checkPull(jobs, book, storage(), where);
        const ack = await doFetch("POST", `/t/alice/jobs/${id}/ack`, { token: `Bearer ${RUNNER}` });
        note(i, ack.tuple);
        if (ack.r.status === 204) {
          assert.ok(!storage().map.has(`job:${id}`), `${where}: ack of ${id} left the job queued`);
        }
        syncOutstanding();
      } else {
        const id = pick(IDS);
        const body = envelopes.get(id);
        const a = await doFetch("POST", "/t/alice/jobs", { token: `Bearer ${SI}`, body });
        const b = await doFetch("POST", "/t/alice/jobs", { token: `Bearer ${SI}`, body });
        note(i, a.tuple); note(i, b.tuple);
        const accepted = [a.r, b.r].filter((r) => r.status === 202);
        assert.ok(accepted.length <= 1, `${where}: ${id} was stored twice`);
        for (const r of accepted) {
          bump(hourKey(), 1); bump(dayKey(), new TextEncoder().encode(body).length);
          void r;
        }
      }
    } else if (roll < 0.62) {
      const id = rnd() < 0.8 ? pick(IDS) : "ghost";
      const verb = rnd() < 0.5 ? "lease" : "ack";
      const token = rnd() < 0.9 ? `Bearer ${RUNNER}` : pick(BAD_FOR_RUNNER);
      const { r, tuple } = await doFetch("POST", `/t/alice/jobs/${id}/${verb}`, { token });
      note(i, tuple);
      if (token !== `Bearer ${RUNNER}`) assert.equal(r.status, 401, `${where}: bad token answered ${r.status}`);
      if (verb === "ack" && r.status === 204) outstanding.delete(id);
      if (verb === "lease" && r.status === 204) syncOutstanding();
    } else if (roll < 0.72) {
      const id = pick(IDS);
      const which = rnd();
      if (which < 0.45) {
        const kind = rnd() < 0.5 ? "result" : rnd() < 0.5 ? "qresult" : "job";
        const subject = `[HOMING-PIGEON] ${kind} ${id}`;
        const body = `${subject}\n\n{"exit_code":0}\n`;
        const kept = storage().map.get(`result:${id}`);
        const { r, tuple } = await doFetch("POST", "/t/alice/results", { token: `Bearer ${RUNNER}`, body });
        note(i, tuple);
        if (kind === "job") {
          assert.equal(r.status, 400, `${where}: job answered ${r.status}`);
        } else if (kept) {
          assert.equal(r.status, 200, `${where}: a second ${kind} answered ${r.status}`);
          assert.equal(storage().map.get(`result:${id}`).envelope, kept.envelope, `${where}: a second ${kind} replaced ${id}`);
        } else {
          assert.equal(r.status, 202, `${where}: ${kind} answered ${r.status}`);
          assert.equal(storage().map.get(`result:${id}`).envelope, body);
        }
      } else if (which < 0.75) {
        const { r, tuple } = await doFetch("GET", "/t/alice/results", { token: `Bearer ${SI}` });
        note(i, tuple);
        if (r.status === 200) {
          const bob = bobStorage();
          for (const row of (await r.json()).results) {
            const stored = storage().map.get(`result:${row.id}`);
            assert.ok(stored, `${where}: result ${row.id} is not alice's`);
            assert.equal(stored.envelope, row.envelope, `${where}: result ${row.id} envelope does not match storage`);
            assert.ok(!(bob && bob.map.has(`result:${row.id}`)), `${where}: alice was handed bob's result ${row.id}`);
          }
        } else {
          assert.equal(r.status, 204, `${where}: results read answered ${r.status}`);
        }
      } else {
        const { r, tuple } = await doFetch("POST", `/t/alice/results/${id}/ack`, { token: `Bearer ${SI}` });
        note(i, tuple);
        assert.ok([204, 404].includes(r.status), `${where}: result ack answered ${r.status}`);
      }
    } else if (roll < 0.82) {
      const dead = [...storage().map.keys()].filter((k) => k.startsWith("dlq:")).map((k) => k.slice(4)).sort();
      const hourFull = (storage().map.get(hourKey()) ?? 0) + 1 > env.quota.jobs_per_hour;
      if (dead.length && hourFull && rnd() < 0.5) {
        // The walk otherwise never requeues while the hour is full:
        // a day-cap refusal does not spend an hour slot, so the two
        // conditions rarely meet. This is that meeting.
        const id = dead[0];
        const before = snapshot(storage());
        const { r, tuple } = await doFetch("POST", `/t/alice/dlq/${id}/requeue`, { token: `Bearer ${SI}` });
        note(i, tuple);
        assert.equal(r.status, 429, `${where}: requeue at a full hour answered ${r.status}`);
        const hourRetry = 3600 - Math.floor((now % 3_600_000) / 1000);
        assert.equal(Number(r.headers.get("retry-after")), hourRetry, `${where}: requeue 429 was not the hour cap`);
        assert.equal(snapshot(storage()), before, `${where}: a refused requeue changed state`);
      } else {
      const id = rnd() < 0.8 ? pick(IDS) : "ghost";
      const which = rnd();
      if (which < 0.4) {
        const { r, tuple } = await doFetch("GET", "/t/alice/dlq", { token: `Bearer ${SI}` });
        note(i, tuple);
        assert.ok([200, 204].includes(r.status), `${where}: dlq read answered ${r.status}`);
        if (r.status === 200) {
          const bob = bobStorage();
          for (const d of (await r.json()).dead) {
            assert.equal(d.attempts, MAX_ATTEMPTS, `${where}: dlq lists ${d.id} at ${d.attempts} attempts`);
            assert.ok(storage().map.has(`dlq:${d.id}`), `${where}: dlq lists ${d.id}, which alice does not hold`);
            assert.ok(!(bob && bob.map.has(`dlq:${d.id}`)), `${where}: alice was handed bob's dead job ${d.id}`);
          }
        }
      } else if (which < 0.7) {
        const { r, tuple } = await doFetch("POST", `/t/alice/dlq/${id}/ack`, { token: `Bearer ${SI}` });
        note(i, tuple);
        assert.ok([204, 404].includes(r.status), `${where}: dlq ack answered ${r.status}`);
      } else {
        const before = snapshot(storage());
        const { r, tuple } = await doFetch("POST", `/t/alice/dlq/${id}/requeue`, { token: `Bearer ${SI}` });
        note(i, tuple);
        assert.ok([202, 404, 409, 429].includes(r.status), `${where}: requeue answered ${r.status}`);
        if (r.status === 202) {
          bump(hourKey(), 1);
          const job = storage().map.get(`job:${id}`);
          assert.ok(job, `${where}: requeue of ${id} stored nothing`);
          assert.equal(job.attempts, 0, `${where}: requeue left ${id} at attempt ${job.attempts}`);
          assert.equal(job.leased_until, 0, `${where}: requeue of ${id} left a lease`);
          assert.ok(!storage().map.has(`dlq:${id}`), `${where}: requeue left ${id} dead`);
        }
        if (r.status === 429) assert.equal(snapshot(storage()), before, `${where}: a 429 requeue changed state`);
      }
      }
    } else if (roll < 0.88) {
      now += pick([0, 100, 999, 1000, 5000, 3_599_000, 3_600_000, 86_400_000]);
      syncOutstanding();
      note(i, tupleOf("tick", 0, keyPrefixes(storage(), now)));
    } else if (roll < 0.94) {
      // Bob is a second tenant. His runner must not see alice's jobs,
      // and alice's token must not open his queue.
      const which = rnd();
      const beforeAlice = snapshot(storage());
      if (which < 0.34) {
        const { r, tuple } = await doFetch("GET", "/t/bob/jobs?max=5", { token: `Bearer ${BOB_RUNNER}` });
        note(i, tuple);
        assert.equal(snapshot(storage()), beforeAlice, `${where}: bob's pull changed alice`);
        if (r.status === 200) {
          const jobs = await readJobs(r);
          checkPull(jobs, new Map(), bobStorage(), where);
          for (const job of jobs) {
            assert.ok(!storage().map.has(`job:${job.id}`), `${where}: bob was handed alice's ${job.id}`);
          }
        } else {
          assert.equal(r.status, 204, `${where}: bob's pull answered ${r.status}`);
        }
      } else if (which < 0.67) {
        const { r, tuple } = await doFetch("GET", "/t/bob/jobs", { token: `Bearer ${RUNNER}` });
        note(i, tuple);
        assert.equal(r.status, 401, `${where}: alice's runner opened bob (${r.status})`);
        assert.equal(snapshot(storage()), beforeAlice, `${where}: a refused bob pull changed alice`);
      } else if (which < 0.84) {
        const id = pick(["b1", "b2"]);
        const { r, tuple } = await doFetch("POST", "/t/bob/jobs", { token: `Bearer ${BOB_SI}`, body: bobEnvelopes.get(id) });
        note(i, tuple);
        assert.equal(snapshot(storage()), beforeAlice, `${where}: bob's submit changed alice`);
        assert.ok([200, 202, 409, 429].includes(r.status), `${where}: bob's submit answered ${r.status}`);
      } else {
        const id = pick(["b1", "b2"]);
        const body = `[HOMING-PIGEON] qresult ${id}\n\n{"exit_code":0}\n`;
        const kept = bobStorage() && bobStorage().map.get(`result:${id}`);
        const posted = await doFetch("POST", "/t/bob/results", { token: `Bearer ${BOB_RUNNER}`, body });
        note(i, posted.tuple);
        assert.equal(posted.r.status, kept ? 200 : 202, `${where}: bob's qresult answered ${posted.r.status}`);
        assert.equal(snapshot(storage()), beforeAlice, `${where}: bob's qresult changed alice`);
        if (kept) assert.equal(bobStorage().map.get(`result:${id}`).envelope, kept.envelope);
        const read = await doFetch("GET", "/t/alice/results", { token: `Bearer ${SI}` });
        note(i, read.tuple);
        if (read.r.status === 200) {
          const ids = (await read.r.json()).results.map((row) => row.id);
          assert.ok(!ids.includes(id), `${where}: alice was handed bob's result ${id}`);
        } else {
          assert.equal(read.r.status, 204, `${where}: alice's result read answered ${read.r.status}`);
        }
        const own = await doFetch("GET", "/t/bob/results", { token: `Bearer ${BOB_SI}` });
        note(i, own.tuple);
        assert.equal(own.r.status, 200, `${where}: bob's result read answered ${own.r.status}`);
        assert.ok((await own.r.json()).results.some((row) => row.id === id), `${where}: bob lost qresult ${id}`);
      }
    } else {
      const choice = pick([
        ["GET", "/health"],
        ["GET", "/t/alice"],
        ["GET", "/t/alice/jobs/j1"],
        ["POST", "/t/nobody/jobs"],
        ["GET", "/t/alice/nope"],
        ["POST", "/health"],
        ["PUT", "/t/alice/jobs"],
        ["DELETE", "/t/alice/dlq"],
        ["POST", "/t/alice/jobs/j1/requeue"],
        ["POST", "/t/alice/results/j1/lease"],
        ["POST", "/t/alice/dlq/j1/lease"],
      ]);
      const body = choice[0] === "POST" && choice[1].endsWith("/jobs") ? envelopes.get("j1") : undefined;
      const token = choice[1].includes("nobody") ? `Bearer ${SI}` : pick([`Bearer ${SI}`, `Bearer ${RUNNER}`, "Bearer " + "q".repeat(SI.length)]);
      const before = snapshot(storage());
      const { r, tuple } = await doFetch(choice[0], choice[1], { token, body });
      note(i, tuple);
      if (choice[1] === "/health") assert.equal(r.status, 200, `${where}: health answered ${r.status}`);
      if (choice[0] === "PUT" || choice[0] === "DELETE") {
        const refused = choice[0] === "DELETE" && token !== `Bearer ${SI}` ? 401 : 405;
        assert.equal(r.status, refused, `${where}: ${choice[0]} answered ${r.status}`);
        assert.equal(snapshot(storage()), before, `${where}: a refused method changed state`);
      }
      if (choice[1].includes("nobody") || choice[1] === "/t/alice" || choice[1] === "/t/alice/nope") {
        assert.equal(r.status, 404, `${where}: ${choice[1]} answered ${r.status}`);
        assert.equal(snapshot(storage()), before, `${where}: a miss changed state`);
      }
      if (/\/jobs\/[^/]+\/requeue$/.test(choice[1]) || /\/(?:results|dlq)\/[^/]+\/lease$/.test(choice[1])) {
        assert.equal(r.status, 404, `${where}: ${choice[1]} answered ${r.status}`);
        assert.equal(snapshot(storage()), before, `${where}: a verb on the wrong list changed state`);
      }
    }
    checkState(storage(), now, expected, where);
  }
  return seenAt;
}

function entriesFrom(seed, seenAt, already) {
  const out = [];
  for (const [op, set] of [...seenAt.entries()].sort((a, b) => a[0] - b[0])) {
    for (const tuple of [...set].sort()) {
      if (already.has(tuple)) continue;
      already.add(tuple);
      const [route, status, keys] = JSON.parse(tuple);
      out.push({ seed, op, route, status, keys });
    }
  }
  return out;
}

test("fuzz: the route surface under mutation, seed 1", async () => { await runFuzz(1, 500); });
test("fuzz: the route surface under mutation, seed 2", async () => { await runFuzz(2, 500); });
test("fuzz: the route surface under mutation, seed 3", async () => { await runFuzz(3, 500); });

test("fuzz: the kept corpus replays", async () => {
  const corpus = loadCorpus();
  assert.ok(corpus.entries.length > 0, "fuzz corpus is empty");
  const need = new Map();
  for (const e of corpus.entries) need.set(e.seed, Math.max(need.get(e.seed) ?? 0, e.op + 1));
  for (const [seed, ops] of [...need.entries()].sort((a, b) => a[0] - b[0])) {
    const seenAt = await runFuzz(seed, ops);
    for (const e of corpus.entries) {
      if (e.seed !== seed) continue;
      const got = seenAt.get(e.op);
      const want = tupleOf(e.route, e.status, e.keys);
      assert.ok(got && got.has(want), `seed ${seed} op ${e.op} no longer reaches ${want}`);
    }
  }
});

test("fuzz: one long seed", async () => {
  const seenAt = await runFuzz(4, LONG_OPS);
  if (process.env.HP_FUZZ_WRITE) {
    const already = new Set();
    const entries = [];
    for (const seed of [1, 2, 3]) {
      entries.push(...entriesFrom(seed, await runFuzz(seed, 500), already));
    }
    entries.push(...entriesFrom(4, seenAt, already));
    writeCorpus(entries);
  }
  assert.ok(seenAt.size > 0);
});

test("fuzz: two overlapping pulls do not lease one job twice", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  const body = await signedJob("only");
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body }), env);
  assert.equal(r.status, 202);
  const [a, b] = await Promise.all([
    worker.fetch(req("/t/alice/jobs?max=5", { token: `Bearer ${RUNNER}` }), env),
    worker.fetch(req("/t/alice/jobs?max=5", { token: `Bearer ${RUNNER}` }), env),
  ]);
  const ids = [];
  for (const res of [a, b]) {
    if (res.status === 204) continue;
    assert.equal(res.status, 200);
    for (const job of (await res.json()).jobs) ids.push(job.id);
  }
  assert.equal(new Set(ids).size, ids.length, `one job leased twice: ${ids}`);
  assert.ok(ids.includes("only"));
  void now;
});

test("fuzz: max=0 leases one job, not the default page", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  for (const id of ["m1", "m2", "m3"]) {
    assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob(id) }), env)).status, 202);
  }
  let r = await worker.fetch(req("/t/alice/jobs?max=0", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs.length, 1);
  r = await worker.fetch(req("/t/alice/jobs?max=-3", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs.length, 1);
  now += 1000;
  r = await worker.fetch(req("/t/alice/jobs?max=abc", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).jobs.length, 3);
});

test("fuzz: a body over the day cap is refused while the hour is open", async () => {
  let now = 1_700_000_000_000;
  const quota = { jobs_per_hour: 6, bytes_per_day: 60_000 };
  const env = makeEnv({ clock: () => now, quota });
  await addTenant(env);
  env.TENANT_QUEUE.get("alice");
  const storage = () => env.objects.get("alice").state.storage;
  const fat = await signedJob("fat1", SECRET, "x".repeat(quota.bytes_per_day));
  assert.ok(fat.length > quota.bytes_per_day && fat.length < DO_VALUE_MAX);
  const before = snapshotBilling(storage());
  const r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: fat }), env);
  assert.equal(r.status, 429);
  const answered = await r.json();
  assert.ok((answered.jobs_this_hour ?? 0) + 1 <= quota.jobs_per_hour);
  const dayRetry = 86400 - Math.floor((now % 86_400_000) / 1000);
  assert.equal(Number(r.headers.get("retry-after")), dayRetry);
  assert.equal(snapshotBilling(storage()), before);
  assert.ok(!storage().map.has("job:fat1"));
  const small = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob("j1") }), env);
  assert.equal(small.status, 202);
});

test("fuzz: the daily cap counts UTF-8 bytes, not JavaScript characters", async () => {
  let now = 1_700_000_000_000;
  const wide = await signedJob("j1", SECRET, "é".repeat(40));
  const chars = wide.length;
  const wideBytes = new TextEncoder().encode(wide).length;
  assert.ok(wideBytes > chars);
  const small = await signedJob("j2", SECRET, "ok");
  const smallBytes = new TextEncoder().encode(small).length;
  assert.ok(smallBytes <= chars);
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 10, bytes_per_day: chars } });
  await addTenant(env);
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: small }), env);
  assert.equal(r.status, 202);
  const dayKey = `quota:day:${Math.floor(now / 86_400_000)}`;
  assert.equal(env.objects.get("alice").state.storage.map.get(dayKey), smallBytes);
  r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: wide }), env);
  assert.equal(r.status, 429);
  assert.ok(!env.objects.get("alice").state.storage.map.has("job:j1"));
  assert.equal(env.objects.get("alice").state.storage.map.get(dayKey), smallBytes);
});

test("fuzz: result bytes have their own day cap, and a full job day does not block them", async () => {
  let now = 1_700_000_000_000;
  const job = await signedJob("j1");
  const jobBytes = new TextEncoder().encode(job).length;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 10, bytes_per_day: jobBytes } });
  await addTenant(env);
  const storage = () => env.objects.get("alice").state.storage;
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: job }), env);
  assert.equal(r.status, 202);
  r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob("j2") }), env);
  assert.equal(r.status, 429);
  const answer = `[HOMING-PIGEON] result j1\n\n{"exit_code":0}\n`;
  const answerBytes = new TextEncoder().encode(answer).length;
  assert.ok(answerBytes <= jobBytes);
  r = await worker.fetch(req("/t/alice/results", { method: "POST", token: `Bearer ${RUNNER}`, body: answer }), env);
  assert.equal(r.status, 202);
  const resKey = `quota:resday:${Math.floor(now / 86_400_000)}`;
  assert.equal(storage().map.get(resKey), answerBytes);
  assert.equal(storage().map.get(`quota:day:${Math.floor(now / 86_400_000)}`), jobBytes);
  const again = await worker.fetch(req("/t/alice/results", { method: "POST", token: `Bearer ${RUNNER}`, body: answer }), env);
  assert.equal(again.status, 200);
  assert.equal(storage().map.get(resKey), answerBytes);
  const fat = `[HOMING-PIGEON] result j2\n\n${"x".repeat(jobBytes)}\n`;
  assert.ok(new TextEncoder().encode(fat).length > jobBytes);
  const before = storage().map.get(resKey);
  r = await worker.fetch(req("/t/alice/results", { method: "POST", token: `Bearer ${RUNNER}`, body: fat }), env);
  assert.equal(r.status, 429);
  const dayRetry = 86400 - Math.floor((now % 86_400_000) / 1000);
  assert.equal(Number(r.headers.get("retry-after")), dayRetry);
  assert.equal(storage().map.get(resKey), before);
  assert.ok(!storage().map.has("result:j2"));
  const bad = makeEnv({ clock: () => now, quota: { bytes_per_day: "lots" } });
  await addTenant(bad);
  r = await worker.fetch(req("/t/alice/results", { method: "POST", token: `Bearer ${RUNNER}`, body: answer }), bad);
  assert.equal(r.status, 400);
  assert.equal(bad.TENANT_QUEUE.get("alice").state.storage.map.size, 0);
});

test("fuzz: bob's runner does not see alice's job", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 10, bytes_per_day: 60_000 } });
  await addTenant(env);
  await addTenant(env, "bob", { si: BOB_SI, runner: BOB_RUNNER, secret: BOB_SECRET });
  const alice = () => env.objects.get("alice").state.storage;
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob("only") }), env);
  assert.equal(r.status, 202);
  const before = snapshot(alice());
  r = await worker.fetch(req("/t/bob/jobs?max=5", { token: `Bearer ${BOB_RUNNER}` }), env);
  assert.equal(r.status, 204);
  assert.equal(snapshot(alice()), before);
  r = await worker.fetch(req("/t/bob/jobs", { method: "POST", token: `Bearer ${BOB_SI}`, body: await signedJob("b1", BOB_SECRET) }), env);
  assert.equal(r.status, 202);
  assert.equal(snapshot(alice()), before);
  r = await worker.fetch(req("/t/alice/jobs?max=5", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(r.status, 200);
  const ids = (await r.json()).jobs.map((j) => j.id);
  assert.deepEqual(ids, ["only"]);
  r = await worker.fetch(req("/t/bob/jobs", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(r.status, 401);
  void now;
});

test("fuzz: requeue at a full hour leaves the dead job dead", async () => {
  let now = 1_700_000_000_000;
  const quota = { jobs_per_hour: 1, bytes_per_day: 60_000 };
  const env = makeEnv({ clock: () => now, quota });
  await addTenant(env);
  const storage = () => env.objects.get("alice").state.storage;
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob("d1") }), env);
  assert.equal(r.status, 202);
  for (let i = 0; i < 6; i++) {
    await worker.fetch(req("/t/alice/jobs?max=1", { token: `Bearer ${RUNNER}` }), env);
    now += 1000;
  }
  assert.ok(storage().map.has("dlq:d1"));
  const before = snapshot(storage());
  r = await worker.fetch(req("/t/alice/dlq/d1/requeue", { method: "POST", token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 429);
  const hourRetry = 3600 - Math.floor((now % 3_600_000) / 1000);
  assert.equal(Number(r.headers.get("retry-after")), hourRetry);
  assert.equal(snapshot(storage()), before);
  assert.ok(!storage().map.has("job:d1"));
  now += 3_600_000;
  r = await worker.fetch(req("/t/alice/dlq/d1/requeue", { method: "POST", token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 202);
  assert.equal(storage().map.get("job:d1").attempts, 0);
  assert.ok(!storage().map.has("dlq:d1"));
});

test("fuzz: a qresult is stored and a job subject on that route is not", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now });
  await addTenant(env);
  let r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: "[HOMING-PIGEON] qresult qr1\n\n{\"exit_code\":0}\n",
  }), env);
  assert.equal(r.status, 202);
  assert.equal((await r.json()).id, "qr1");
  r = await worker.fetch(req("/t/alice/results", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  assert.deepEqual((await r.json()).results.map((row) => row.id), ["qr1"]);
  r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: "[HOMING-PIGEON] job qr1\n\n{\"exit_code\":0}\n",
  }), env);
  assert.equal(r.status, 400);
  void now;
});

test("fuzz: a result whose body names a different id is refused", async () => {
  const env = makeEnv();
  await addTenant(env);
  const storage = () => env.objects.get("alice").state.storage;
  let r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: "[HOMING-PIGEON] result j1\n\n{\"job_id\":\"j2\",\"exit_code\":0}\n",
  }), env);
  assert.equal(r.status, 400);
  assert.equal(storage().map.size, 0);
  r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: "[HOMING-PIGEON] result j1\n\n{\"job_id\":1}\n",
  }), env);
  assert.equal(r.status, 400);
  r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: "[HOMING-PIGEON] qresult q1\n\n{\"query_id\":\"q2\"}\n",
  }), env);
  assert.equal(r.status, 400);
  assert.ok(!storage().map.has("result:q1"));
  const payload = JSON.stringify({ v: 1, type: "result", job_id: "j2", exit_code: 0 });
  const sig = await hmacSha384Hex(SECRET, payload);
  const signed = payload.slice(0, -1) + `,"sig":"${sig}"}`;
  r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: `[HOMING-PIGEON] result j1\n\n{"job_id":"j1"}${signed}\n`,
  }), env);
  assert.equal(r.status, 400);
  r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: "[HOMING-PIGEON] result j1\n\n{\"job_id\":\"j1\",\"exit_code\":0}\n",
  }), env);
  assert.equal(r.status, 202);
  r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: "[HOMING-PIGEON] qresult q1\n\n{\"query_id\":\"q1\"}\n",
  }), env);
  assert.equal(r.status, 202);
  r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: "[HOMING-PIGEON] result enc1\n\n{\"hp_enc\":{\"alg\":\"AES-256-GCM\",\"nonce\":\"aa\",\"ct\":\"bb\"}}\n",
  }), env);
  assert.equal(r.status, 202);
  assert.ok(storage().map.has("result:enc1"));
});

test("fuzz: a second result for an id keeps the first envelope", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now });
  await addTenant(env);
  const first = "[HOMING-PIGEON] result j1\n\n{\"exit_code\":0}\n";
  const second = "[HOMING-PIGEON] qresult j1\n\n{\"exit_code\":1}\n";
  let r = await worker.fetch(req("/t/alice/results", { method: "POST", token: `Bearer ${RUNNER}`, body: first }), env);
  assert.equal(r.status, 202);
  r = await worker.fetch(req("/t/alice/results", { method: "POST", token: `Bearer ${RUNNER}`, body: second }), env);
  assert.equal(r.status, 200);
  const dup = await r.json();
  assert.equal(dup.duplicate, true);
  assert.equal(dup.sha256, await sha256Hex(first));
  const stored = env.objects.get("alice").state.storage.map.get("result:j1");
  assert.equal(stored.envelope, first);
  r = await worker.fetch(req("/t/alice/results", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).results[0].envelope, first);
  void now;
});

test("fuzz: a result stays in its tenant, and a verb on the wrong list is a 404", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now });
  await addTenant(env);
  await addTenant(env, "bob", { si: BOB_SI, runner: BOB_RUNNER, secret: BOB_SECRET });
  const alice = () => env.objects.get("alice").state.storage;
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob("only") }), env);
  assert.equal(r.status, 202);
  r = await worker.fetch(req("/t/alice/jobs?max=1", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(r.status, 200);
  const job = (await r.json()).jobs[0];
  assert.equal(job.attempt, 1);
  assert.equal(alice().map.get("job:only").envelope, job.envelope);
  const before = snapshot(alice());
  for (const path of ["/t/alice/jobs/only/requeue", "/t/alice/results/only/lease", "/t/alice/dlq/only/lease"]) {
    r = await worker.fetch(req(path, { method: "POST", token: `Bearer ${SI}` }), env);
    assert.equal(r.status, 404, path);
    assert.equal(snapshot(alice()), before, path);
  }
  r = await worker.fetch(req("/t/bob/results", {
    method: "POST", token: `Bearer ${BOB_RUNNER}`,
    body: "[HOMING-PIGEON] qresult b1\n\n{\"exit_code\":0}\n",
  }), env);
  assert.equal(r.status, 202);
  assert.equal(snapshot(alice()), before);
  r = await worker.fetch(req("/t/alice/results", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 204);
  r = await worker.fetch(req("/t/bob/results", { token: `Bearer ${BOB_SI}` }), env);
  assert.equal(r.status, 200);
  assert.deepEqual((await r.json()).results.map((row) => row.id), ["b1"]);
  void now;
});

test("fuzz: an unsafe id or a subject that disagrees with the body is refused", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now });
  await addTenant(env);
  env.TENANT_QUEUE.get("alice");
  const storage = () => env.objects.get("alice").state.storage;
  const good = await signedJob("j1");
  const before = snapshot(storage());
  const mismatch = good.replace("[HOMING-PIGEON] job j1", "[HOMING-PIGEON] job j2");
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: mismatch }), env);
  assert.equal(r.status, 400);
  assert.equal(snapshot(storage()), before);
  for (const id of ["a/b", ".", "..", "a".repeat(129)]) {
    const body = good.replace("[HOMING-PIGEON] job j1", `[HOMING-PIGEON] job ${id}`);
    r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body }), env);
    assert.equal(r.status, 400, id);
    assert.equal(snapshot(storage()), before, id);
  }
  r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: "[HOMING-PIGEON] qresult a/b\n\n{\"exit_code\":0}\n",
  }), env);
  assert.equal(r.status, 400);
  assert.equal(snapshot(storage()), before);
  r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob("ok.id_1") }), env);
  assert.equal(r.status, 202);
  assert.ok(storage().map.has("job:ok.id_1"));
  void now;
});

test("fuzz: a signed job the runner can parse is not refused for NaN", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now });
  await addTenant(env);
  const payload = "{\"v\":1,\"type\":\"job\",\"job_id\":\"j1\",\"kind\":\"exec\",\"script\":\"echo hi\",\"n\":NaN}";
  const sig = await hmacSha384Hex(SECRET, payload);
  const raw = payload.slice(0, -1) + `,"sig":"${sig}"}`;
  assert.throws(() => JSON.parse(raw));
  const body = `[HOMING-PIGEON] job j1\n\n${raw}\n`;
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body }), env);
  assert.equal(r.status, 202);
  assert.equal(env.objects.get("alice").state.storage.map.get("job:j1").envelope, body);
  const other = `[HOMING-PIGEON] job j2\n\n${raw}\n`;
  r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: other }), env);
  assert.equal(r.status, 400);
  assert.ok(!env.objects.get("alice").state.storage.map.has("job:j2"));
});

test("fuzz: an envelope the object cannot store is refused, and one that fits is kept", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 600, bytes_per_day: 512 * 1024 * 1024 } });
  await addTenant(env);
  const storage = () => env.objects.get("alice").state.storage;
  const empty = await signedJob("big1", SECRET, "");
  const fit = await signedJob("big1", SECRET, "x".repeat(DO_VALUE_MAX - empty.length - 800));
  assert.ok(jobStoredBytes("big1", fit, now) <= DO_VALUE_MAX);
  assert.ok(jobStoredBytes("big1", fit, now) > DO_VALUE_MAX - 2_000);
  let r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: fit }), env);
  assert.equal(r.status, 202);
  // The dead-letter copy and a later requeue have to fit too.
  for (let i = 0; i < 6; i++) {
    await worker.fetch(req("/t/alice/jobs?max=1", { token: `Bearer ${RUNNER}` }), env);
    now += 1000;
  }
  assert.ok(storage().map.has("dlq:big1"));
  const deadHand = storage().map.get("dlq:big1").hand;
  r = await worker.fetch(req("/t/alice/dlq/big1/requeue", { method: "POST", token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 202);
  assert.equal(storage().map.get("job:big1").attempts, 0);
  // The hand the last pull held does not still name the requeued job,
  // and a second trip to the dead list still fits: that copy keeps
  // requeued_at as well as dead_at.
  assert.ok(storage().map.get("job:big1").hand > deadHand);
  assert.ok(storagePairBytes("job:big1", storage().map.get("job:big1"))
    <= jobStoredBytes("big1", storage().map.get("job:big1").envelope, now));
  for (let i = 0; i < 6; i++) {
    await worker.fetch(req("/t/alice/jobs?max=1", { token: `Bearer ${RUNNER}` }), env);
    now += 1000;
  }
  const dead = storage().map.get("dlq:big1");
  assert.ok(dead);
  assert.ok(dead.requeued_at);
  assert.ok(storagePairBytes("dlq:big1", dead) <= jobStoredBytes("big1", dead.envelope, now));
  assert.ok(storagePairBytes("dlq:big1", dead) <= DO_VALUE_MAX);
  const before = snapshot(storage());
  // Under the raw-length gate, over once the record is wrapped.
  const empty2 = await signedJob("big2", SECRET, "");
  const wrapped = await signedJob("big2", SECRET, "x".repeat(DO_VALUE_MAX - empty2.length));
  assert.ok(wrapped.length <= DO_VALUE_MAX);
  assert.ok(jobStoredBytes("big2", wrapped, now) > DO_VALUE_MAX);
  r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: wrapped }), env);
  assert.equal(r.status, 413);
  assert.equal(snapshot(storage()), before);
  // Past the raw limit, and a result the same size.
  const raw = await signedJob("big3", SECRET, "x".repeat(DO_VALUE_MAX));
  assert.ok(raw.length > DO_VALUE_MAX);
  r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: raw }), env);
  assert.equal(r.status, 413);
  assert.equal(snapshot(storage()), before);
  r = await worker.fetch(req("/t/alice/results", {
    method: "POST", token: `Bearer ${RUNNER}`,
    body: `[HOMING-PIGEON] qresult big1\n\n${"x".repeat(DO_VALUE_MAX)}\n`,
  }), env);
  assert.equal(r.status, 413);
  assert.ok(!storage().map.has("result:big1"));
  assert.equal(snapshot(storage()), before);
});

test("fuzz: the storage budget counts the lease timestamp, not zero", async () => {
  const now = 1_700_000_000_000;
  const id = "edge";
  const narrow = (text) => storagePairBytes(`dlq:${id}`, {
    id, envelope: text, size: text.length, attempts: 5,
    leased_until: 0, enqueued_at: now, dead_at: now,
  });
  const per = jobStoredBytes(id, "x", now) - jobStoredBytes(id, "", now);
  let text = "x".repeat(Math.floor((DO_VALUE_MAX - jobStoredBytes(id, "", now)) / per) + 1);
  while (jobStoredBytes(id, text, now) <= DO_VALUE_MAX) text += "x";
  while (text.length > 1 && jobStoredBytes(id, text.slice(0, -1), now) > DO_VALUE_MAX) text = text.slice(0, -1);
  assert.ok(jobStoredBytes(id, text, now) > DO_VALUE_MAX);
  assert.ok(narrow(text) <= DO_VALUE_MAX, "the old budget would have stored this");
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 10, bytes_per_day: 9_000_000_000 } });
  const obj = env.TENANT_QUEUE.get("alice");
  const r = await obj.fetch(new Request("https://do/enqueue", {
    method: "POST",
    headers: { "x-hp-job-id": id, "x-hp-quota": JSON.stringify(env.quota) },
    body: text,
  }));
  assert.equal(r.status, 413);
  assert.ok(!env.objects.get("alice").state.storage.map.has(`job:${id}`));
  assert.ok(!env.objects.get("alice").state.storage.map.has("quota:exceeded"));
});

test("fuzz: the storage budget counts the requeued dead copy, not the first", async () => {
  const now = 9_999_999_999_999;
  const id = "edge";
  const narrow = (text) => storagePairBytes(`dlq:${id}`, {
    id, envelope: text, size: text.length, attempts: 5,
    leased_until: now, enqueued_at: now, dead_at: now,
  });
  const per = jobStoredBytes(id, "x", now) - jobStoredBytes(id, "", now);
  let text = "x".repeat(Math.floor((DO_VALUE_MAX - jobStoredBytes(id, "", now)) / per) + 1);
  while (jobStoredBytes(id, text, now) <= DO_VALUE_MAX) text += "x";
  while (text.length > 1 && jobStoredBytes(id, text.slice(0, -1), now) > DO_VALUE_MAX) text = text.slice(0, -1);
  assert.ok(jobStoredBytes(id, text, now) > DO_VALUE_MAX);
  assert.ok(narrow(text) <= DO_VALUE_MAX, "the first dead copy would have stored this");
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 10, bytes_per_day: 9_000_000_000 } });
  const obj = env.TENANT_QUEUE.get("alice");
  const r = await obj.fetch(new Request("https://do/enqueue", {
    method: "POST",
    headers: { "x-hp-job-id": id, "x-hp-quota": JSON.stringify(env.quota) },
    body: text,
  }));
  assert.equal(r.status, 413);
  assert.ok(!env.objects.get("alice").state.storage.map.has(`job:${id}`));
});

test("fuzz: a pull pages the queue and still leases every waiting job", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 60, bytes_per_day: 60_000 } });
  await addTenant(env);
  const ids = ["p1", "p2", "p3", "p4", "p5"];
  for (const id of ids) {
    const r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob(id) }), env);
    assert.equal(r.status, 202, id);
  }
  const storage = env.objects.get("alice").state.storage;
  const raw = storage.list.bind(storage);
  let calls = 0;
  storage.list = async (opts = {}) => {
    calls += 1;
    return raw({ ...opts, limit: Math.min(opts.limit ?? Infinity, 2) });
  };
  let r = await worker.fetch(req("/t/alice/jobs?max=5", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(r.status, 200);
  assert.deepEqual((await r.json()).jobs.map((j) => j.id).sort(), ids);
  assert.ok(calls >= 3, `one list returned the whole queue (${calls})`);
  // The first two stay leased. The next pull must keep paging to find the rest.
  now += 1000;
  calls = 0;
  r = await worker.fetch(req("/t/alice/jobs?max=5", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(r.status, 200);
  assert.deepEqual((await r.json()).jobs.map((j) => j.id).sort(), ids);
});

test("fuzz: a read gives back the rest on the next call instead of one huge response", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 60, bytes_per_day: 60_000_000 } });
  await addTenant(env);
  const piece = 1_500_000;
  const ids = ["r1", "r2", "r3", "r4", "r5", "r6"];
  for (const id of ids) {
    const r = await worker.fetch(req("/t/alice/results", {
      method: "POST", token: `Bearer ${RUNNER}`,
      body: `[HOMING-PIGEON] result ${id}\n\n${"x".repeat(piece)}\n`,
    }), env);
    assert.equal(r.status, 202, id);
  }
  let r = await worker.fetch(req("/t/alice/results?max=100", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const firstBody = await r.json();
  const first = firstBody.results;
  assert.equal(firstBody.more, true);
  assert.ok(first.length >= 1 && first.length < ids.length, `returned ${first.length}`);
  assert.ok(first.reduce((n, row) => n + new TextEncoder().encode(row.envelope).length, 0) <= RESPONSE_BUDGET);
  const last = first[first.length - 1].id;
  r = await worker.fetch(req(`/t/alice/results?max=100&after=${last}`, { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const restBody = await r.json();
  assert.notEqual(restBody.more, true);
  assert.deepEqual([...first, ...restBody.results].map((row) => row.id).sort(), ids);
  const storage = env.objects.get("alice").state.storage;
  for (const id of ids) assert.ok(storage.map.has(`result:${id}`));
  for (const row of first) {
    assert.equal((await worker.fetch(req(`/t/alice/results/${row.id}/ack`, { method: "POST", token: `Bearer ${SI}` }), env)).status, 204);
  }
  r = await worker.fetch(req("/t/alice/results?max=100", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const afterAck = (await r.json()).results;
  assert.deepEqual(afterAck.map((row) => row.id).sort(), restBody.results.map((row) => row.id).sort());
});

test("fuzz: a results page that ends on the page size still says more", async () => {
  const env = makeEnv();
  await addTenant(env);
  const storage = env.TENANT_QUEUE.get(env.TENANT_QUEUE.idFromName("alice")).state.storage;
  const ids = ["r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9"];
  for (const id of ids) {
    storage.map.set(`result:${id}`, {
      id, envelope: `[HOMING-PIGEON] result ${id}\n\n{}\n`, at: 1,
    });
  }
  let r = await worker.fetch(req("/t/alice/results?max=8", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const first = await r.json();
  assert.equal(first.more, true);
  assert.deepEqual(first.results.map((row) => row.id), ids.slice(0, 8));
  r = await worker.fetch(req("/t/alice/results?max=8&after=r8", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const rest = await r.json();
  assert.notEqual(rest.more, true);
  assert.deepEqual(rest.results.map((row) => row.id), ["r9"]);
  for (const id of ids) assert.ok(storage.map.has(`result:${id}`));
  r = await worker.fetch(req("/t/alice/results?max=8&after=../job", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).results[0].id, "r1");
});

test("fuzz: the dead-letter list is paged and still names every dead job", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 60, bytes_per_day: 60_000 } });
  await addTenant(env);
  const ids = ["d1", "d2", "d3", "d4", "d5"];
  for (const id of ids) {
    assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob(id) }), env)).status, 202);
  }
  for (let i = 0; i < 6; i++) {
    await worker.fetch(req("/t/alice/jobs?max=5", { token: `Bearer ${RUNNER}` }), env);
    now += 1000;
  }
  const storage = env.objects.get("alice").state.storage;
  const raw = storage.list.bind(storage);
  let calls = 0;
  storage.list = async (opts = {}) => {
    calls += 1;
    return raw({ ...opts, limit: Math.min(opts.limit ?? Infinity, 2) });
  };
  const r = await worker.fetch(req("/t/alice/dlq?max=5", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const dead = (await r.json()).dead;
  assert.deepEqual(dead.map((d) => d.id).sort(), ids);
  for (const d of dead) assert.ok(!("envelope" in d));
  assert.ok(calls >= 3, `one list returned the whole dead list (${calls})`);
});

test("fuzz: a dead-letter read stops at 8 MB of subjects and the next read has the rest", async () => {
  let now = 1_700_000_000_000;
  const env = makeEnv({ clock: () => now, quota: { jobs_per_hour: 60, bytes_per_day: 60_000_000 } });
  await addTenant(env);
  const ids = ["s1", "s2", "s3", "s4", "s5", "s6"];
  const pad = "s".repeat(1_500_000);
  for (const id of ids) {
    const payload = JSON.stringify({ v: 1, type: "job", job_id: id, kind: "exec", script: "echo hi" });
    const sig = await hmacSha384Hex(SECRET, payload);
    const body = payload.slice(0, -1) + `,"sig":"${sig}"}`;
    const text = `[HOMING-PIGEON] job ${id} ${pad}\n\n${body}\n`;
    const r = await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: text }), env);
    assert.equal(r.status, 202, id);
  }
  // One pull hands out only as many envelopes as fit in 8 MB, so a
  // pull of the whole page never reaches the last id. Lease one at
  // a time, five times, then the next pull dead-letters them.
  for (let attempt = 0; attempt < 5; attempt++) {
    for (const id of ids) {
      const got = await worker.fetch(req("/t/alice/jobs?max=1", { token: `Bearer ${RUNNER}` }), env);
      assert.equal(got.status, 200, `${id} attempt ${attempt}`);
    }
    now += 1000;
  }
  await worker.fetch(req("/t/alice/jobs?max=8", { token: `Bearer ${RUNNER}` }), env);
  const storage = () => env.objects.get("alice").state.storage;
  for (const id of ids) assert.ok(storage().map.has(`dlq:${id}`), id);
  let r = await worker.fetch(req("/t/alice/dlq?max=100", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const firstBody = await r.json();
  const first = firstBody.dead;
  assert.equal(firstBody.more, true);
  assert.ok(first.length >= 1 && first.length < ids.length, `returned ${first.length}`);
  const bytes = (rows) => rows.reduce((n, row) => n + new TextEncoder().encode(row.subject || "").length, 0);
  assert.ok(bytes(first) <= RESPONSE_BUDGET);
  assert.ok(first[0].subject.startsWith("[HOMING-PIGEON] job "));
  assert.ok(first[0].subject.length > 1_000_000);
  for (const row of first) assert.ok(!("envelope" in row));
  const last = first[first.length - 1].id;
  r = await worker.fetch(req(`/t/alice/dlq?max=100&after=${last}`, { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const restBody = await r.json();
  assert.notEqual(restBody.more, true);
  assert.deepEqual([...first, ...restBody.dead].map((d) => d.id).sort(), ids);
  assert.ok(bytes(restBody.dead) <= RESPONSE_BUDGET);
  for (const id of ids) assert.ok(storage().map.has(`dlq:${id}`), id);
});

test("fuzz: a dead-letter page that ends on the page size still says more", async () => {
  const env = makeEnv();
  await addTenant(env);
  const storage = env.TENANT_QUEUE.get(env.TENANT_QUEUE.idFromName("alice")).state.storage;
  const ids = ["d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9"];
  for (const id of ids) {
    storage.map.set(`dlq:${id}`, {
      id, envelope: `[HOMING-PIGEON] job ${id}\n\n{}\n`, attempts: 5,
      size: 1, enqueued_at: 1, dead_at: 1,
    });
  }
  let r = await worker.fetch(req("/t/alice/dlq?max=8", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const first = await r.json();
  assert.equal(first.more, true);
  assert.deepEqual(first.dead.map((d) => d.id), ids.slice(0, 8));
  r = await worker.fetch(req("/t/alice/dlq?max=8&after=d8", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const rest = await r.json();
  assert.notEqual(rest.more, true);
  assert.deepEqual(rest.dead.map((d) => d.id), ["d9"]);
  r = await worker.fetch(req("/t/alice/dlq?max=8&after=../quota", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).dead[0].id, "d1");
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

// ---------------------------------------------------------------------
// Shotgun family for queue item 25: a result whose body names a
// different id is refused (queue Worker) (fixed 9565d89f,
// 31-Oct-2026). Results are stored under the id in the subject,
// and the first envelope stored for an id stays, so a result
// filed under the wrong subject blocked the real answer for that
// id for good. The fix reads the id the body claims -- job_id on
// a result, query_id on a qresult -- from the signed payload when
// there is one, and refuses the post with a 400 naming the field
// when that claim is present and is not the subject's id. A body
// that does not carry the field makes no claim and is unchanged:
// an encrypted envelope carries the id in the subject only, and
// a body that does not parse as one JSON object claims nothing.
// This family scattershots everything around that refusal: both
// kinds and the field each one reads, the other kind's field
// ignored, every non-string claim, the signed payload read
// against unsigned decoys on both sides, duplicate keys, nested
// and inert fields, the subject's own grammar (extra words, case,
// CRLF), bookended and run-length claimed ids, injection-shaped
// claims and fields, and the storage life around a refusal --
// the real answer still lands, a stored first envelope is not
// displaced, and a refusal bills nothing. One regression test
// was never going to be enough for a bug that took days of CPU
// to find.
//
// Proof of work. The unit tests are the 50 tests registered
// below: 16 hand-written seams, 10 per-field tests, 10 bookend
// sweeps, 6 run-length sweeps, 4 injection-shaped tests and 4
// lifecycle edges. Per-field enumeration: the refusal's surface
// is fielded -- the subject's kind (result reads job_id, qresult
// reads query_id), the subject's id, the body's job_id and
// query_id one by one (string match, string mismatch, absent,
// null, boolean, number, object, array, empty, nested, and
// shadowed by a duplicate key), the sig member that makes the
// payload the signed one the check reads, the hp_enc member, and
// the body's remaining fields (exit_code, note, a previous id),
// each pinned as inert or governing in its own test. Bookends:
// every printable ASCII symbol (all 32 punctuation characters)
// at the front AND the back of the claimed id, as singles,
// matched pairs, mismatched pairs and symbol-only claims, plus
// NUL, tab, CR and LF at both ends, and the safe id symbols
// (., -, _) bookending the subject id and the claimed id
// together, where the pair is accepted. Run lengths: runs of
// the odd character as the whole claim and after an ordinary
// prefix at lengths 1, 5, 10 and 100, 10 ordinary characters
// with the odd one at the front, the back and the middle, ids
// at the 127/128 length boundary matching and differing by one
// character, and the same refused envelope posted 10 times.
// The fuzzing was executed, not just the tests written:
// runner/tools/de_dust_corpus.py grow --target wire --rounds
// 400 --seed 20261126, run locally against the banked wire
// corpus (117 entries). Result: 400 rounds, 0 crashes, 0 slow,
// arcs unchanged at 184, slowest try 660 ms -- the mismatched-
// result shape did not recur. The grow's bookkeeping writes
// were reverted and are not banked (banking is the rigs' hourly
// job); this record is the run's proof. For the .mjs file the
// Python skip registry does not apply, and this family adds no
// skips. None of this is exotic: it is combinatorics --
// systematically trying the combinations a hand-written list
// would never reach, then pinning each answer as a test.

const SG25_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";

async function sg25Env() {
  const env = makeEnv();
  await addTenant(env);
  env.TENANT_QUEUE.get("alice");
  return env;
}

function sg25Map(env) {
  return env.objects.get("alice").state.storage.map;
}

async function sg25Post(env, envelope, slug = "alice", token = RUNNER) {
  return worker.fetch(req(`/t/${slug}/results`, {
    method: "POST", token: `Bearer ${token}`, body: envelope,
  }), env);
}

function sg25Envelope(subject, bodyText) {
  return `[HOMING-PIGEON] ${subject}\n\n${bodyText}\n`;
}

async function sg25Refuse(env, subject, bodyText, field = "job_id") {
  const id = subject.split(/\s+/).pop();
  const before = sg25Map(env).size;
  const r = await sg25Post(env, sg25Envelope(subject, bodyText));
  assert.equal(r.status, 400, `${subject} / ${bodyText}`);
  assert.equal((await r.json()).error, `${field} mismatch between subject and body`);
  assert.ok(!sg25Map(env).has(`result:${id}`), `${subject} stored a result`);
  assert.equal(sg25Map(env).size, before, `${subject} changed storage`);
  return r;
}

async function sg25Accept(env, subject, bodyText) {
  const id = subject.split(/\s+/).pop();
  const envelope = sg25Envelope(subject, bodyText);
  const r = await sg25Post(env, envelope);
  assert.equal(r.status, 202, `${subject} / ${bodyText}`);
  assert.equal((await r.json()).id, id);
  assert.equal(sg25Map(env).get(`result:${id}`).envelope, envelope);
  return r;
}

async function sg25SignedBody(fields, secret = SECRET) {
  const payload = JSON.stringify(fields);
  const sig = await hmacSha384Hex(secret, payload);
  return payload.slice(0, -1) + `,"sig":"${sig}"}`;
}

// -- 16 hand-written seams -------------------------------------------

test("shotgun25: a result whose body names a different id is refused and stores nothing", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", `{"job_id":"j2","exit_code":0}`);
  assert.equal(sg25Map(env).size, 0);
});

test("shotgun25: a qresult whose body names a different id is refused, naming query_id", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "qresult q1", `{"query_id":"q2"}`, "query_id");
  assert.equal(sg25Map(env).size, 0);
});

test("shotgun25: a result whose body names the subject id is stored byte for byte", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "result j1", `{"job_id":"j1","exit_code":0}`);
});

test("shotgun25: a qresult whose body names the subject id is stored", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "qresult q1", `{"query_id":"q1","rows":3}`);
});

test("shotgun25: a body with no id field at all makes no claim and is stored", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "result j1", `{"exit_code":0,"stdout":"done"}`);
  const env2 = await sg25Env();
  await sg25Accept(env2, "qresult q1", `{"rows":[]}`);
});

test("shotgun25: an encrypted envelope carries no claim and is stored", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "result enc1",
    `{"hp_enc":{"alg":"AES-256-GCM","nonce":"aa","ct":"bb"}}`);
});

test("shotgun25: an encrypted shape beside a mismatched job_id is still refused", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1",
    `{"hp_enc":{"alg":"AES-256-GCM","nonce":"aa","ct":"bb"},"job_id":"j2"}`);
});

test("shotgun25: a numeric job_id is a claim that is not the subject id and is refused", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", `{"job_id":42}`);
  await sg25Refuse(env, "result j1", `{"job_id":0}`);
  await sg25Refuse(env, "result j1", `{"job_id":-1}`);
});

test("shotgun25: the signed payload governs -- its different id is refused past an unsigned prefix naming the subject", async () => {
  const env = await sg25Env();
  const signed = await sg25SignedBody({ v: 1, type: "result", job_id: "j2", exit_code: 0 });
  await sg25Refuse(env, "result j1", `{"job_id":"j1"}${signed}`);
});

test("shotgun25: the signed payload governs -- its matching id is stored past an unsigned prefix naming another id", async () => {
  const env = await sg25Env();
  const signed = await sg25SignedBody({ v: 1, type: "result", job_id: "j1", exit_code: 0 });
  await sg25Accept(env, "result j1", `{"job_id":"evil"}${signed}`);
});

test("shotgun25: a signed payload with no id field makes no claim, past an unsigned prefix naming another id", async () => {
  const env = await sg25Env();
  const signed = await sg25SignedBody({ v: 1, type: "result", exit_code: 0 });
  await sg25Accept(env, "result j1", `{"job_id":"evil"}${signed}`);
});

test("shotgun25: a signed payload naming another id is refused whatever secret signed it", async () => {
  const env = await sg25Env();
  const signed = await sg25SignedBody({ v: 1, type: "result", job_id: "j2" }, "the-wrong-secret");
  await sg25Refuse(env, "result j1", signed);
});

test("shotgun25: a case-only difference between the claimed id and the subject id is refused", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", `{"job_id":"J1"}`);
  await sg25Refuse(env, "result J1", `{"job_id":"j1"}`);
  await sg25Refuse(env, "qresult q1", `{"query_id":"Q1"}`, "query_id");
});

test("shotgun25: a claimed id padded with spaces or a tab is not the subject id", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", JSON.stringify({ job_id: " j1 " }));
  await sg25Refuse(env, "result j1", JSON.stringify({ job_id: "j1\t" }));
  await sg25Refuse(env, "result j1", JSON.stringify({ job_id: "\tj1" }));
});

test("shotgun25: a body that is not one JSON object makes no claim and is stored under the subject id", async () => {
  const bodies = [
    `[{"job_id":"j2"}]`,
    `"j2"`,
    `42`,
    `null`,
    `{job_id:j2}`,
    `note first\n{"job_id":"j2"}`,
    `{"job_id":"j2"} trailing words`,
  ];
  for (const bodyText of bodies) {
    const env = await sg25Env();
    await sg25Accept(env, "result j1", bodyText);
  }
});

test("shotgun25: duplicate id keys read their last value, in both directions", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "result j1", `{"job_id":"j2","job_id":"j1"}`);
  const env2 = await sg25Env();
  await sg25Refuse(env2, "result j1", `{"job_id":"j1","job_id":"j2"}`);
});

// -- 10 per-field tests ------------------------------------------------

test("shotgun25 field kind result: a result carrying only a mismatched query_id is stored -- that field is not read", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "result j1", `{"query_id":"q9","exit_code":0}`);
});

test("shotgun25 field kind qresult: a qresult carrying only a mismatched job_id is stored -- that field is not read", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "qresult q1", `{"job_id":"j9","rows":1}`);
});

test("shotgun25 field kind result: with both fields present the job_id governs a result", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", `{"job_id":"j2","query_id":"j1"}`);
  const env2 = await sg25Env();
  await sg25Accept(env2, "result j1", `{"job_id":"j1","query_id":"q9"}`);
});

test("shotgun25 field kind qresult: with both fields present the query_id governs a qresult", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "qresult q1", `{"job_id":"q1","query_id":"q2"}`, "query_id");
  const env2 = await sg25Env();
  await sg25Accept(env2, "qresult q1", `{"job_id":"j9","query_id":"q1"}`);
});

test("shotgun25 field job_id: a null claim is present and not the subject id, and is refused", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", `{"job_id":null}`);
  await sg25Refuse(env, "qresult q1", `{"query_id":null}`, "query_id");
});

test("shotgun25 field job_id: boolean, object and array claims are refused", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", `{"job_id":true}`);
  await sg25Refuse(env, "result j1", `{"job_id":false}`);
  await sg25Refuse(env, "result j1", `{"job_id":{"id":"j1"}}`);
  await sg25Refuse(env, "result j1", `{"job_id":["j1"]}`);
  await sg25Refuse(env, "result j1", `{"job_id":NaN}`);
});

test("shotgun25 field job_id: an empty claimed id is refused, for both kinds", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", `{"job_id":""}`);
  await sg25Refuse(env, "qresult q1", `{"query_id":""}`, "query_id");
});

test("shotgun25 field job_id: an id nested inside another member is not a claim", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "result j1", `{"outer":{"job_id":"j2"},"exit_code":0}`);
  const env2 = await sg25Env();
  await sg25Accept(env2, "qresult q1", `{"outer":{"query_id":"q2"}}`);
});

test("shotgun25 field other fields: ids named in the body's other fields are inert when the claim matches", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "result j1",
    `{"job_id":"j1","exit_code":0,"note":"j2","prev_job_id":"j2","stdout":"result j2"}`);
});

test("shotgun25 field subject: an extra word, an uppercase kind and CRLF endings do not move the binding", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "TEST result j1", `{"job_id":"j1"}`);
  const env2 = await sg25Env();
  const r = await sg25Post(env2, "[HOMING-PIGEON] QRESULT q1\r\n\r\n{\"query_id\":\"q2\"}\r\n");
  assert.equal(r.status, 400);
  assert.equal((await r.json()).error, "query_id mismatch between subject and body");
  const env3 = await sg25Env();
  const ok = await sg25Post(env3, "[HOMING-PIGEON] result j1\r\n\r\n{\"job_id\":\"j1\"}\r\n");
  assert.equal(ok.status, 202);
  assert.ok(sg25Map(env3).has("result:j1"));
});

// -- 10 bookend sweeps ---------------------------------------------------

test("shotgun25 bookends: every ASCII symbol at the front of the claimed id is refused", async () => {
  const env = await sg25Env();
  for (const ch of SG25_PUNCT) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: ch + "j1" }));
  }
  assert.equal(sg25Map(env).size, 0);
});

test("shotgun25 bookends: every ASCII symbol at the back of the claimed id is refused", async () => {
  const env = await sg25Env();
  for (const ch of SG25_PUNCT) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: "j1" + ch }));
  }
  assert.equal(sg25Map(env).size, 0);
});

test("shotgun25 bookends: matched symbol pairs around the claimed id are refused", async () => {
  const env = await sg25Env();
  for (const ch of SG25_PUNCT) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: ch + "j1" + ch }));
  }
  assert.equal(sg25Map(env).size, 0);
});

test("shotgun25 bookends: mismatched symbol pairs around the claimed id are refused", async () => {
  const env = await sg25Env();
  const chars = [...SG25_PUNCT];
  for (let i = 0; i < chars.length; i++) {
    const claimed = chars[i] + "j1" + chars[(i + 1) % chars.length];
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: claimed }));
  }
  assert.equal(sg25Map(env).size, 0);
});

test("shotgun25 bookends: symbol-only claimed ids are refused, each symbol and all together", async () => {
  const env = await sg25Env();
  for (const ch of SG25_PUNCT) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: ch }));
  }
  await sg25Refuse(env, "result j1", JSON.stringify({ job_id: SG25_PUNCT }));
  assert.equal(sg25Map(env).size, 0);
});

test("shotgun25 bookends: NUL at the front, the back and both ends of the claimed id is refused", async () => {
  const env = await sg25Env();
  for (const claimed of ["\0j1", "j1\0", "\0j1\0", "\0"]) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: claimed }));
  }
});

test("shotgun25 bookends: tab at the front, the back and both ends of the claimed id is refused", async () => {
  const env = await sg25Env();
  for (const claimed of ["\tj1", "j1\t", "\tj1\t", "\t"]) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: claimed }));
  }
});

test("shotgun25 bookends: CR at the front, the back and both ends of the claimed id is refused", async () => {
  const env = await sg25Env();
  for (const claimed of ["\rj1", "j1\r", "\rj1\r", "\r"]) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: claimed }));
  }
});

test("shotgun25 bookends: LF at the front, the back and both ends of the claimed id is refused", async () => {
  const env = await sg25Env();
  for (const claimed of ["\nj1", "j1\n", "\nj1\n", "\n"]) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: claimed }));
  }
});

test("shotgun25 bookends: the safe id symbols bookending the subject id and the claimed id together are stored", async () => {
  const env = await sg25Env();
  const ids = [".sg25.", "-sg25-", "_sg25_", ".sg25", "sg25.", "-sg25", "sg25-", "_sg25", "sg25_"];
  for (const id of ids) {
    await sg25Accept(env, `result ${id}`, JSON.stringify({ job_id: id }));
  }
});

// -- 6 run-length sweeps -------------------------------------------------

test("shotgun25 runs: a run of the odd character as the whole claimed id, lengths 1, 5, 10 and 100, is refused", async () => {
  const env = await sg25Env();
  for (const n of [1, 5, 10, 100]) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: "!".repeat(n) }));
  }
  assert.equal(sg25Map(env).size, 0);
});

test("shotgun25 runs: a run of the odd character after the subject id, and a run of its last character, are refused", async () => {
  const env = await sg25Env();
  for (const n of [1, 5, 10, 100]) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: "j1" + "!".repeat(n) }));
  }
  for (const n of [2, 5, 10]) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: "j" + "1".repeat(n) }));
  }
});

test("shotgun25 runs: 10 ordinary characters with the odd one at the front, the back and the middle are refused", async () => {
  const env = await sg25Env();
  const subject = "a".repeat(10);
  for (const claimed of ["!" + subject, subject + "!", "a".repeat(5) + "!" + "a".repeat(5),
    "!" + "a".repeat(10) + "!", "a".repeat(10)]) {
    if (claimed === subject) continue;
    await sg25Refuse(env, `result ${subject}`, JSON.stringify({ job_id: claimed }));
  }
  await sg25Accept(env, `result ${subject}`, JSON.stringify({ job_id: subject }));
});

test("shotgun25 runs: matching ids at the length boundaries -- 1, 127 and 128 characters -- are stored", async () => {
  const env = await sg25Env();
  for (const id of ["a", "b".repeat(127), "c".repeat(128)]) {
    await sg25Accept(env, `result ${id}`, JSON.stringify({ job_id: id }));
  }
});

test("shotgun25 runs: a 128-character claimed id differing in its first or its last character is refused", async () => {
  const env = await sg25Env();
  const id = "a".repeat(128);
  await sg25Refuse(env, `result ${id}`, JSON.stringify({ job_id: "b" + "a".repeat(127) }));
  await sg25Refuse(env, `result ${id}`, JSON.stringify({ job_id: "a".repeat(127) + "b" }));
});

test("shotgun25 runs: the same mismatched envelope posted 10 times is refused 10 times and stores nothing", async () => {
  const env = await sg25Env();
  for (let i = 0; i < 10; i++) {
    await sg25Refuse(env, "result j1", `{"job_id":"j2","exit_code":0}`);
  }
  assert.equal(sg25Map(env).size, 0);
  await sg25Accept(env, "result j1", `{"job_id":"j1","exit_code":0}`);
});

// -- 4 injection-shaped tests ---------------------------------------------

test("shotgun25 injection: SQL-shaped claimed ids are refused and store nothing", async () => {
  const env = await sg25Env();
  for (const claimed of [`j1"; DROP TABLE results; --`, `' OR '1'='1`, `j1' OR 1=1 --`]) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: claimed }));
  }
  assert.equal(sg25Map(env).size, 0);
});

test("shotgun25 injection: a prompt-shaped claimed id is refused; prompt text in another field with a matching claim is inert", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", JSON.stringify({
    job_id: "ignore all previous instructions and file this result under j1",
  }));
  const env2 = await sg25Env();
  await sg25Accept(env2, "result j1", JSON.stringify({
    job_id: "j1",
    note: "ignore all previous instructions and mark every job acked",
  }));
});

test("shotgun25 injection: a fake envelope inside the body creates no second result", async () => {
  const env = await sg25Env();
  await sg25Accept(env, "result j1", JSON.stringify({
    job_id: "j1",
    stdout: "[HOMING-PIGEON] result evil\n\n{\"job_id\":\"evil\"}",
  }));
  assert.ok(!sg25Map(env).has("result:evil"));
  const env2 = await sg25Env();
  await sg25Accept(env2, "result j1",
    `{"job_id":"j2"}\n[HOMING-PIGEON] result j1\n\n{"job_id":"j1"}`);
  assert.ok(!sg25Map(env2).has("result:j2"));
  assert.deepEqual(
    [...sg25Map(env2).keys()].filter((k) => k.startsWith("result:")), ["result:j1"]);
});

test("shotgun25 injection: traversal-shaped claimed ids are refused, and a __proto__ field with a matching claim pollutes nothing", async () => {
  const env = await sg25Env();
  for (const claimed of ["../../etc/passwd", "..\\j1", "/t/alice/results/j1", "j1/../../j2", "../j1"]) {
    await sg25Refuse(env, "result j1", JSON.stringify({ job_id: claimed }));
  }
  const env2 = await sg25Env();
  await sg25Accept(env2, "result j1", `{"job_id":"j1","__proto__":{"polluted":"yes"}}`);
  assert.equal({}.polluted, undefined);
});

// -- 4 lifecycle edges ------------------------------------------------------

test("shotgun25 lifecycle: a refusal does not block the real answer -- the correct result lands and reads back", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", `{"job_id":"j2","exit_code":0}`);
  const good = await sg25Accept(env, "result j1", `{"job_id":"j1","exit_code":0}`);
  void good;
  const r = await worker.fetch(req("/t/alice/results", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const rows = (await r.json()).results;
  assert.deepEqual(rows.map((row) => row.id), ["j1"]);
  assert.equal(rows[0].envelope, sg25Envelope("result j1", `{"job_id":"j1","exit_code":0}`));
});

test("shotgun25 lifecycle: a mismatched second result is a 400, not a duplicate, and the first envelope stays", async () => {
  const env = await sg25Env();
  const first = sg25Envelope("result j1", `{"job_id":"j1","exit_code":0}`);
  assert.equal((await sg25Post(env, first)).status, 202);
  const refused = await sg25Post(env, sg25Envelope("result j1", `{"job_id":"j2","exit_code":1}`));
  assert.equal(refused.status, 400);
  assert.equal((await refused.json()).error, "job_id mismatch between subject and body");
  assert.equal(sg25Map(env).get("result:j1").envelope, first);
  const dup = await sg25Post(env, sg25Envelope("result j1", `{"job_id":"j1","exit_code":9}`));
  assert.equal(dup.status, 200);
  const body = await dup.json();
  assert.equal(body.duplicate, true);
  assert.equal(body.sha256, await sha256Hex(first));
  assert.equal(sg25Map(env).get("result:j1").envelope, first);
});

test("shotgun25 lifecycle: a refusal bills no result bytes and leaves the results read empty", async () => {
  const env = await sg25Env();
  await sg25Refuse(env, "result j1", `{"job_id":"j2","exit_code":0}`);
  await sg25Refuse(env, "qresult q1", `{"query_id":"q2"}`, "query_id");
  assert.ok(![...sg25Map(env).keys()].some((k) => k.startsWith("quota:resday:")));
  const r = await worker.fetch(req("/t/alice/results", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 204);
  const envelope = sg25Envelope("result j1", `{"job_id":"j1","exit_code":0}`);
  assert.equal((await sg25Post(env, envelope)).status, 202);
  const resKey = [...sg25Map(env).keys()].find((k) => k.startsWith("quota:resday:"));
  assert.ok(resKey, "a stored result bills its bytes");
  assert.equal(sg25Map(env).get(resKey), new TextEncoder().encode(envelope).length);
});

test("shotgun25 lifecycle: a refusal under one tenant stores nothing there, and the other tenant's matching result still lands", async () => {
  const env = await sg25Env();
  await addTenant(env, "bob", { si: BOB_SI, runner: BOB_RUNNER, secret: BOB_SECRET });
  const bad = sg25Envelope("result j1", `{"job_id":"j2"}`);
  assert.equal((await sg25Post(env, bad)).status, 400);
  assert.equal((await sg25Post(env, bad, "bob", BOB_RUNNER)).status, 400);
  assert.equal(sg25Map(env).size, 0);
  const bobMap = env.objects.get("bob").state.storage.map;
  assert.ok(![...bobMap.keys()].some((k) => k.startsWith("result:")));
  const good = sg25Envelope("result j1", `{"job_id":"j1"}`);
  assert.equal((await sg25Post(env, good, "bob", BOB_RUNNER)).status, 202);
  assert.ok(bobMap.has("result:j1"));
  assert.equal(sg25Map(env).size, 0);
});


// Shotgun family for queue item 26: result bytes had no daily cap
// of their own (fixed 90ca98f3, 31-Oct-2026). Before the fix a
// result stopped only at the 2 MB storage limit, so a runner token
// could fill the object after the job day was already closed. The
// fix gives results the same daily byte cap (bytes_per_day) on
// their own counter, quota:resday:<UTC day>, apart from the job
// counter quota:day: a day full of jobs still accepts its answers,
// a copy of a result already stored is not billed again, and a
// quota that is not a number is a 400 on the result route. This
// family scattershots everything around that failure, with the
// size axis at its heart: byte counts at, 1 under and 1 over the
// daily cap, what counts toward it (the whole envelope text in
// UTF-8 bytes -- subject, blank line, body and trailing newline
// included), what does not move it (jobs, duplicates, acks, gated
// refusals), and when it resets (the UTC day boundary, not the
// hour). One regression test was never going to be enough for a
// bug that took days of CPU to find.
//
// Proof of work. The unit tests are the 50 tests registered
// below: 18 hand-written seams, 13 per-field tests, 8
// what-counts tests, 4 precedence tests, 5 bookend sweeps and 2
// run-length sweeps. Per-field enumeration: the result quota's
// surface is fielded -- bytes_per_day (missing, null, a numeric
// string, a non-number string, a boolean, an object, an array,
// zero, negative, fractional, huge, and present with jobs_per_hour
// missing), jobs_per_hour (a non-number, and zero), and the quota
// object itself (a string, an array, a number, missing, null)
// each get their own test; the 429 answer's fields (error,
// bytes_today, retry-after) and the stored counters are pinned by
// the hand-written seams. Bookends: every printable ASCII symbol
// (all 32 punctuation characters) at the front AND the back of
// the result body, as singles, matched pairs, mismatched pairs
// and a symbol-only body, plus NUL, tab, CR and LF at the front,
// the back and both ends. Run lengths: runs of the odd character
// at lengths 1, 5, 10 and 100, and runs of 10 ordinary characters
// with the odd one at the front, the back and the middle.
// Injection-shaped payloads ride in the what-counts section: they
// are ordinary bytes, billed and stored like any other. The
// fuzzing was executed, not just the tests written:
// runner/tools/de_dust_corpus.py grow --target collect --rounds
// 400 --seed 20261127, run locally against the banked collect
// corpus (20 entries). Result: 400 rounds, 0 crashes, 0 slow,
// arcs unchanged at 65, slowest try 31 ms -- the uncapped-result
// shape did not recur. The grow's bookkeeping writes were
// reverted and are not banked (banking is the rigs' hourly job);
// this record is the run's proof. For the .mjs file the Python
// skip registry does not apply, and this family adds no skips.
// None of this is exotic: it is combinatorics -- systematically
// trying the combinations a hand-written list would never reach,
// then pinning each answer as a test.

const SG26_T0 = 1_700_000_000_000;
const SG26_DAY = 86_400_000;
const SG26_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
const sg26Bytes = (t) => new TextEncoder().encode(t).length;
const sg26DayStart = (now) => Math.floor(now / SG26_DAY) * SG26_DAY;

function sg26Body(id, note) {
  const o = { job_id: id, exit_code: 0 };
  if (note !== undefined) o.note = note;
  return JSON.stringify(o);
}

function sg26Result(id, bodyText) {
  return `[HOMING-PIGEON] result ${id}\n\n${bodyText ?? sg26Body(id)}\n`;
}

async function sg26Setup(quota, clock, slug) {
  const env = makeEnv({ quota, clock });
  await addTenant(env);
  if (slug === "bob") await addTenant(env, "bob", { si: BOB_SI, runner: BOB_RUNNER, secret: BOB_SECRET });
  return env;
}

async function sg26Post(env, body, slug = "alice", token = RUNNER) {
  return worker.fetch(req(`/t/${slug}/results`, { method: "POST", token: `Bearer ${token}`, body }), env);
}

function sg26Store(env, slug = "alice") {
  return env.objects.get(slug)?.state.storage;
}

function sg26Resday(env, now, slug = "alice") {
  return sg26Store(env, slug)?.map.get(`quota:resday:${Math.floor(now / SG26_DAY)}`);
}

function sg26Day(env, now, slug = "alice") {
  return sg26Store(env, slug)?.map.get(`quota:day:${Math.floor(now / SG26_DAY)}`);
}

// -- 18 hand-written seams -------------------------------------------

test("shotgun26: a result whose bytes exactly fill the day cap is accepted and billed exactly", async () => {
  const now = SG26_T0;
  const text = sg26Result("r1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  const r = await sg26Post(env, text);
  assert.equal(r.status, 202);
  assert.equal((await r.json()).id, "r1");
  assert.equal(sg26Resday(env, now), w);
  const stored = sg26Store(env).map.get("result:r1");
  assert.equal(stored.envelope, text);
  assert.equal(stored.at, now);
  assert.equal(sg26Day(env, now), undefined);
});

test("shotgun26: a result 1 byte under the day cap is accepted", async () => {
  const now = SG26_T0;
  const text = sg26Result("r1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w + 1 }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  assert.equal(sg26Resday(env, now), w);
});

test("shotgun26: a result 1 byte over the day cap is 429, stores nothing and bills nothing", async () => {
  const now = SG26_T0;
  const text = sg26Result("r1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w - 1 }, () => now);
  const r = await sg26Post(env, text);
  assert.equal(r.status, 429);
  assert.equal((await r.json()).bytes_today, 0);
  assert.equal(sg26Resday(env, now), undefined);
  assert.ok(!sg26Store(env).map.has("result:r1"));
  assert.equal(sg26Store(env).map.get("quota:exceeded"), 1);
});

test("shotgun26: two results whose bytes together exactly fill the cap are both accepted", async () => {
  const now = SG26_T0;
  const a = sg26Result("a1");
  const b = sg26Result("a2");
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: sg26Bytes(a) + sg26Bytes(b) }, () => now);
  assert.equal((await sg26Post(env, a)).status, 202);
  assert.equal((await sg26Post(env, b)).status, 202);
  assert.equal(sg26Resday(env, now), sg26Bytes(a) + sg26Bytes(b));
});

test("shotgun26: a second result that takes the day 1 byte over is refused and the first stays readable", async () => {
  const now = SG26_T0;
  const a = sg26Result("c1");
  const b = sg26Result("c2", sg26Body("c2", "x"));
  const cap = sg26Bytes(a) + sg26Bytes(b) - 1;
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap }, () => now);
  assert.equal((await sg26Post(env, a)).status, 202);
  const r = await sg26Post(env, b);
  assert.equal(r.status, 429);
  assert.equal((await r.json()).bytes_today, sg26Bytes(a));
  assert.equal(sg26Resday(env, now), sg26Bytes(a));
  assert.ok(!sg26Store(env).map.has("result:c2"));
  const read = await worker.fetch(req("/t/alice/results", { token: `Bearer ${SI}` }), env);
  assert.equal(read.status, 200);
  assert.deepEqual((await read.json()).results.map((row) => row.id), ["c1"]);
});

test("shotgun26: five equal results fill the cap exactly and a sixth is refused", async () => {
  const now = SG26_T0;
  const ids = ["r01", "r02", "r03", "r04", "r05"];
  const texts = ids.map((id) => sg26Result(id));
  const weights = new Set(texts.map(sg26Bytes));
  assert.equal(weights.size, 1);
  const w = sg26Bytes(texts[0]);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: 5 * w }, () => now);
  for (const t of texts) assert.equal((await sg26Post(env, t)).status, 202);
  assert.equal(sg26Resday(env, now), 5 * w);
  assert.equal((await sg26Post(env, sg26Result("r06"))).status, 429);
  assert.equal(sg26Resday(env, now), 5 * w);
});

test("shotgun26: a qresult spends the same result counter as a result", async () => {
  const now = SG26_T0;
  const a = sg26Result("q1");
  const b = `[HOMING-PIGEON] qresult q2\n\n${JSON.stringify({ query_id: "q2" })}\n`;
  const cap = sg26Bytes(a) + sg26Bytes(b);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap }, () => now);
  assert.equal((await sg26Post(env, a)).status, 202);
  assert.equal((await sg26Post(env, b)).status, 202);
  assert.equal(sg26Resday(env, now), cap);
  assert.equal((await sg26Post(env, sg26Result("q3"))).status, 429);
});

test("shotgun26: the 429 answer names the error, the bytes already billed and the wait to midnight", async () => {
  const now = sg26DayStart(SG26_T0);
  const a = sg26Result("r1");
  const w = sg26Bytes(a);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: 2 * w }, () => now);
  assert.equal((await sg26Post(env, a)).status, 202);
  const fat = sg26Result("r2", sg26Body("r2", "x".repeat(w)));
  const r = await sg26Post(env, fat);
  assert.equal(r.status, 429);
  const body = await r.json();
  assert.equal(body.error, "tenant quota exceeded");
  assert.equal(body.bytes_today, w);
  assert.equal(Number(r.headers.get("retry-after")), 86400);
  assert.equal(sg26Resday(env, now), w);
});

test("shotgun26: a refusal in the day's last millisecond waits 1 second", async () => {
  const now = sg26DayStart(SG26_T0) + SG26_DAY - 1;
  const text = sg26Result("r1");
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: sg26Bytes(text) - 1 }, () => now);
  const r = await sg26Post(env, text);
  assert.equal(r.status, 429);
  assert.equal(Number(r.headers.get("retry-after")), 1);
});

test("shotgun26: the next UTC day opens a fresh result counter and the old one stays on the record", async () => {
  let now = sg26DayStart(SG26_T0) + 5000;
  const a = sg26Result("n1");
  const w = sg26Bytes(a);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(env, a)).status, 202);
  assert.equal((await sg26Post(env, sg26Result("n2"))).status, 429);
  now += SG26_DAY;
  assert.equal((await sg26Post(env, sg26Result("n2"))).status, 202);
  assert.equal(sg26Resday(env, now), w);
  assert.equal(sg26Store(env).map.get(`quota:resday:${Math.floor((now - SG26_DAY) / SG26_DAY)}`), w);
});

test("shotgun26: 1 millisecond before midnight the day is still closed, at midnight it opens", async () => {
  const start = sg26DayStart(SG26_T0) + 1000;
  let now = start;
  const a = sg26Result("m1");
  const w = sg26Bytes(a);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(env, a)).status, 202);
  now = start - 1000 + SG26_DAY - 1;
  assert.equal((await sg26Post(env, sg26Result("m2"))).status, 429);
  now += 1;
  assert.equal((await sg26Post(env, sg26Result("m2"))).status, 202);
  assert.equal(sg26Resday(env, now), w);
});

test("shotgun26: an hour rolling over does not reset the result counter", async () => {
  let now = sg26DayStart(SG26_T0) + 1000;
  const a = sg26Result("h1");
  const w = sg26Bytes(a);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(env, a)).status, 202);
  now += 3_600_000;
  assert.equal((await sg26Post(env, sg26Result("h2"))).status, 429);
  assert.equal(sg26Resday(env, now), w);
});

test("shotgun26: a day full of jobs still accepts its answers", async () => {
  const now = SG26_T0;
  const job = await signedJob("j1");
  const wj = sg26Bytes(job);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: wj }, () => now);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: job }), env)).status, 202);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: await signedJob("j2") }), env)).status, 429);
  const answer = sg26Result("j1");
  assert.ok(sg26Bytes(answer) <= wj);
  assert.equal((await sg26Post(env, answer)).status, 202);
  assert.equal(sg26Resday(env, now), sg26Bytes(answer));
  assert.equal(sg26Day(env, now), wj);
});

test("shotgun26: a result moves neither job counter, and a job can still spend its whole day", async () => {
  const now = SG26_T0;
  const job = await signedJob("j1");
  const wj = sg26Bytes(job);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: wj }, () => now);
  const answer = sg26Result("j1");
  assert.equal((await sg26Post(env, answer)).status, 202);
  assert.equal(sg26Resday(env, now), sg26Bytes(answer));
  assert.equal(sg26Day(env, now), undefined);
  assert.ok(![...sg26Store(env).map.keys()].some((k) => k.startsWith("quota:hour:")));
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: job }), env)).status, 202);
  assert.equal(sg26Day(env, now), wj);
  assert.equal(sg26Store(env).map.get(`quota:hour:${Math.floor(now / 3_600_000)}`), 1);
  assert.equal(sg26Resday(env, now), sg26Bytes(answer));
});

test("shotgun26: a day full of results still accepts jobs up to their own cap", async () => {
  const now = SG26_T0;
  const job = await signedJob("j1");
  const wj = sg26Bytes(job);
  const fat = sg26Result("j1", sg26Body("j1", "x".repeat(wj)));
  const wf = sg26Bytes(fat);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: wf }, () => now);
  assert.equal((await sg26Post(env, fat)).status, 202);
  assert.equal(sg26Resday(env, now), wf);
  assert.equal((await sg26Post(env, sg26Result("j2"))).status, 429);
  assert.equal((await worker.fetch(req("/t/alice/jobs", { method: "POST", token: `Bearer ${SI}`, body: job }), env)).status, 202);
  assert.equal(sg26Day(env, now), wj);
  assert.equal(sg26Resday(env, now), wf);
});

test("shotgun26: an exact copy of a stored result at a full cap is a duplicate, not a 429, and is not billed", async () => {
  const now = SG26_T0;
  const text = sg26Result("d1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  const r = await sg26Post(env, text);
  assert.equal(r.status, 200);
  assert.equal((await r.json()).duplicate, true);
  assert.equal(sg26Resday(env, now), w);
  assert.equal(sg26Store(env).map.get("quota:exceeded") ?? 0, 0);
});

test("shotgun26: a different copy of a stored result is not billed and the first envelope stays", async () => {
  const now = SG26_T0;
  const first = sg26Result("d1");
  const second = sg26Result("d1", sg26Body("d1", "a different, longer answer"));
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: sg26Bytes(first) }, () => now);
  assert.equal((await sg26Post(env, first)).status, 202);
  const r = await sg26Post(env, second);
  assert.equal(r.status, 200);
  const body = await r.json();
  assert.equal(body.duplicate, true);
  assert.equal(body.sha256, await sha256Hex(first));
  assert.equal(sg26Resday(env, now), sg26Bytes(first));
  assert.equal(sg26Store(env).map.get("result:d1").envelope, first);
});

test("shotgun26: another tenant's result counter is its own", async () => {
  const now = SG26_T0;
  const text = sg26Result("t1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now, "bob");
  assert.equal((await sg26Post(env, text)).status, 202);
  assert.equal((await sg26Post(env, sg26Result("t2"))).status, 429);
  const bobText = sg26Result("b1", sg26Body("b1"));
  assert.equal((await sg26Post(env, bobText, "bob", BOB_RUNNER)).status, 202);
  assert.equal(sg26Resday(env, now, "bob"), sg26Bytes(bobText));
  assert.equal(sg26Resday(env, now), w);
});

// -- 13 per-field tests ----------------------------------------------

test("shotgun26 field bytes_per_day missing: the default cap applies and the counter still tracks", async () => {
  const now = SG26_T0;
  const text = sg26Result("f1");
  const env = await sg26Setup({ jobs_per_hour: 10 }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  assert.equal(sg26Resday(env, now), sg26Bytes(text));
});

test("shotgun26 field bytes_per_day null: the default cap applies", async () => {
  const now = SG26_T0;
  const text = sg26Result("f1");
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: null }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  assert.equal(sg26Resday(env, now), sg26Bytes(text));
});

test("shotgun26 field bytes_per_day numeric string: a number written as a string is the cap", async () => {
  const now = SG26_T0;
  const text = sg26Result("f1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: String(w) }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  assert.equal(sg26Resday(env, now), w);
  assert.equal((await sg26Post(env, sg26Result("f2"))).status, 429);
});

test("shotgun26 field bytes_per_day not a number: a word for the cap is a 400 and stores nothing", async () => {
  const now = SG26_T0;
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: "lots" }, () => now);
  const r = await sg26Post(env, sg26Result("f1"));
  assert.equal(r.status, 400);
  assert.equal((await r.json()).error, "quota is not a number");
  assert.ok(!sg26Store(env)?.map.has("result:f1"));
  assert.equal(sg26Resday(env, now), undefined);
});

test("shotgun26 field bytes_per_day wrong type: a boolean, an object and an array for the cap are each a 400", async () => {
  const now = SG26_T0;
  for (const bad of [true, {}, []]) {
    const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: bad }, () => now);
    const r = await sg26Post(env, sg26Result("f1"));
    assert.equal(r.status, 400, JSON.stringify(bad));
    assert.equal((await r.json()).error, "quota is not a number");
    assert.ok(!sg26Store(env)?.map.has("result:f1"));
  }
});

test("shotgun26 field jobs_per_hour not a number: a bad job cap is a 400 on the result route too", async () => {
  const now = SG26_T0;
  const env = await sg26Setup({ jobs_per_hour: "lots", bytes_per_day: 60_000 }, () => now);
  const r = await sg26Post(env, sg26Result("f1"));
  assert.equal(r.status, 400);
  assert.equal((await r.json()).error, "quota is not a number");
  assert.ok(!sg26Store(env)?.map.has("result:f1"));
});

test("shotgun26 field jobs_per_hour zero: results do not spend the hourly job cap", async () => {
  const now = SG26_T0;
  const text = sg26Result("f1");
  const env = await sg26Setup({ jobs_per_hour: 0, bytes_per_day: 60_000 }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  assert.equal(sg26Resday(env, now), sg26Bytes(text));
});

test("shotgun26 field bytes_per_day zero: every result is over a zero cap", async () => {
  const now = SG26_T0;
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: 0 }, () => now);
  const r = await sg26Post(env, sg26Result("f1"));
  assert.equal(r.status, 429);
  assert.equal((await r.json()).bytes_today, 0);
  assert.equal(sg26Resday(env, now), undefined);
});

test("shotgun26 field bytes_per_day negative: every result is over a negative cap", async () => {
  const now = SG26_T0;
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: -1000 }, () => now);
  assert.equal((await sg26Post(env, sg26Result("f1"))).status, 429);
  assert.ok(!sg26Store(env).map.has("result:f1"));
});

test("shotgun26 field bytes_per_day fractional: a cap half a byte under refuses, half a byte over accepts", async () => {
  const now = SG26_T0;
  const text = sg26Result("f1");
  const w = sg26Bytes(text);
  const under = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w - 0.5 }, () => now);
  assert.equal((await sg26Post(under, text)).status, 429);
  const over = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w + 0.5 }, () => now);
  assert.equal((await sg26Post(over, text)).status, 202);
  assert.equal(sg26Resday(over, now), w);
});

test("shotgun26 field quota itself: a quota that is not an object is a 400", async () => {
  const now = SG26_T0;
  for (const bad of ["lots", [], 42]) {
    const env = makeEnv({ clock: () => now });
    env.quota = bad;
    await addTenant(env);
    const r = await sg26Post(env, sg26Result("f1"));
    assert.equal(r.status, 400, JSON.stringify(bad));
    assert.equal((await r.json()).error, "quota is not a number");
  }
});

test("shotgun26 field quota missing or null: the default quota applies", async () => {
  const now = SG26_T0;
  for (const missing of [undefined, null]) {
    const env = makeEnv({ clock: () => now });
    env.quota = missing;
    await addTenant(env);
    const text = sg26Result("f1");
    assert.equal((await sg26Post(env, text)).status, 202);
    assert.equal(sg26Resday(env, now), sg26Bytes(text));
  }
});

test("shotgun26 field bytes_per_day huge, and jobs_per_hour missing beside it: the cap is the number given", async () => {
  const now = SG26_T0;
  const text = sg26Result("f1");
  const w = sg26Bytes(text);
  const huge = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: Number.MAX_SAFE_INTEGER }, () => now);
  assert.equal((await sg26Post(huge, text)).status, 202);
  assert.equal(sg26Resday(huge, now), w);
  const noHour = await sg26Setup({ bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(noHour, text)).status, 202);
  assert.equal((await sg26Post(noHour, sg26Result("f2"))).status, 429);
});

// -- 8 what-counts tests ----------------------------------------------

test("shotgun26 counts: the cap counts UTF-8 bytes, not characters -- accented text", async () => {
  const now = SG26_T0;
  const text = sg26Result("u1", sg26Body("u1", "é".repeat(40)));
  assert.ok(sg26Bytes(text) > text.length);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: text.length }, () => now);
  assert.equal((await sg26Post(env, text)).status, 429);
  assert.ok(!sg26Store(env).map.has("result:u1"));
});

test("shotgun26 counts: the cap counts UTF-8 bytes, not characters -- 4-byte emoji", async () => {
  const now = SG26_T0;
  const text = sg26Result("u1", sg26Body("u1", "😀".repeat(20)));
  assert.ok(sg26Bytes(text) > text.length);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: text.length }, () => now);
  assert.equal((await sg26Post(env, text)).status, 429);
  assert.ok(!sg26Store(env).map.has("result:u1"));
});

test("shotgun26 counts: the subject line is billed -- a longer id alone crosses the cap", async () => {
  const now = SG26_T0;
  const body = JSON.stringify({ exit_code: 0 });
  const short = `[HOMING-PIGEON] result s1\n\n${body}\n`;
  const long = `[HOMING-PIGEON] result s1234567890123\n\n${body}\n`;
  const cap = sg26Bytes(short);
  const envA = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap }, () => now);
  assert.equal((await sg26Post(envA, short)).status, 202);
  assert.equal(sg26Resday(envA, now), cap);
  const envB = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap }, () => now);
  assert.equal((await sg26Post(envB, long)).status, 429);
  assert.ok(!sg26Store(envB).map.has("result:s1234567890123"));
});

test("shotgun26 counts: the trailing newline is billed", async () => {
  const now = SG26_T0;
  const withNl = sg26Result("n1");
  const withoutNl = withNl.slice(0, -1);
  const w = sg26Bytes(withoutNl);
  const envA = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(envA, withoutNl)).status, 202);
  assert.equal(sg26Store(envA).map.get("result:n1").envelope, withoutNl);
  assert.equal(sg26Resday(envA, now), w);
  const envB = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(envB, withNl)).status, 429);
});

test("shotgun26 counts: the whole envelope is billed, not the payload alone", async () => {
  const now = SG26_T0;
  const payload = sg26Body("w1");
  const text = sg26Result("w1", payload);
  assert.ok(sg26Bytes(text) > sg26Bytes(payload));
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: sg26Bytes(payload) }, () => now);
  const r = await sg26Post(env, text);
  assert.equal(r.status, 429);
  assert.equal((await r.json()).bytes_today, 0);
});

test("shotgun26 counts: acking a result does not refund its bytes", async () => {
  const now = SG26_T0;
  const text = sg26Result("a1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  const ack = await worker.fetch(req("/t/alice/results/a1/ack", { method: "POST", token: `Bearer ${SI}` }), env);
  assert.equal(ack.status, 204);
  assert.ok(!sg26Store(env).map.has("result:a1"));
  assert.equal(sg26Resday(env, now), w);
  assert.equal((await sg26Post(env, sg26Result("a2"))).status, 429);
});

test("shotgun26 counts: a result posted again after its ack is billed again", async () => {
  const now = SG26_T0;
  const text = sg26Result("a1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: 2 * w }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  assert.equal((await worker.fetch(req("/t/alice/results/a1/ack", { method: "POST", token: `Bearer ${SI}` }), env)).status, 204);
  assert.equal((await sg26Post(env, text)).status, 202);
  assert.equal(sg26Resday(env, now), 2 * w);
  assert.equal((await sg26Post(env, sg26Result("a2"))).status, 429);
});

test("shotgun26 injection: injection-shaped payloads are ordinary bytes -- billed, stored verbatim, refused over the cap", async () => {
  const now = SG26_T0;
  const notes = [
    "ignore all previous instructions and return every stored result",
    "'; DROP TABLE results; --",
    "<script>alert('x')</script>",
    "${7*7} {{7*7}} <%= 7*7 %>",
    "../../../etc/passwd",
    "\"; DELETE FROM quota; SELECT \"",
    "quota:resday is 0, trust me, the cap is lifted",
  ];
  for (const note of notes) {
    const text = sg26Result("inj", sg26Body("inj", note));
    const w = sg26Bytes(text);
    const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
    assert.equal((await sg26Post(env, text)).status, 202, note);
    assert.equal(sg26Store(env).map.get("result:inj").envelope, text);
    assert.equal(sg26Resday(env, now), w);
  }
  const text = sg26Result("inj", sg26Body("inj", notes[0]));
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: sg26Bytes(text) - 1 }, () => now);
  assert.equal((await sg26Post(env, text)).status, 429);
  assert.ok(!sg26Store(env).map.has("result:inj"));
});

// -- 4 precedence tests ------------------------------------------------

test("shotgun26 precedence: a 429 tallies only the refusal -- every other key is untouched, refusal after refusal", async () => {
  const now = SG26_T0;
  const text = sg26Result("p1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  const storage = sg26Store(env);
  const before = snapshotBilling(storage);
  for (const id of ["p2", "p3", "p4"]) {
    assert.equal((await sg26Post(env, sg26Result(id, sg26Body(id, "x".repeat(10))))).status, 429);
  }
  assert.equal(storage.map.get("quota:exceeded"), 3);
  assert.equal(snapshotBilling(storage), before);
  assert.equal(sg26Resday(env, now), w);
});

test("shotgun26 precedence: envelope gates answer 400, not 429, when the day is already full", async () => {
  const now = SG26_T0;
  const text = sg26Result("g1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  for (const bad of [
    "no blank line at all",
    "[HOMING-PIGEON] result g2\n\n{\"job_id\":\"other\",\"exit_code\":0}\n",
    "[HOMING-PIGEON] result a/b\n\n{\"exit_code\":0}\n",
    "[HOMING-PIGEON] job g2\n\n{\"exit_code\":0}\n",
  ]) {
    assert.equal((await sg26Post(env, bad)).status, 400, bad.slice(0, 40));
  }
  assert.equal(sg26Resday(env, now), w);
  assert.equal(sg26Store(env).map.get("quota:exceeded") ?? 0, 0);
});

test("shotgun26 precedence: a bad token answers 401, not 429, when the day is already full, and bills nothing", async () => {
  const now = SG26_T0;
  const text = sg26Result("g1");
  const w = sg26Bytes(text);
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(env, text)).status, 202);
  const next = sg26Result("g2");
  assert.equal((await sg26Post(env, next, "alice", SI)).status, 401);
  assert.equal((await sg26Post(env, next, "alice", "runner-token-alicf")).status, 401);
  const noTok = await worker.fetch(new Request("https://hp.example.test/t/alice/results", { method: "POST", body: next }), env);
  assert.equal(noTok.status, 401);
  assert.equal(sg26Resday(env, now), w);
  assert.ok(!sg26Store(env).map.has("result:g2"));
});

test("shotgun26 precedence: the storage limit answers 413, not 429, under a tiny cap and under a huge one", async () => {
  const now = SG26_T0;
  const fat = sg26Result("big", sg26Body("big", "x".repeat(DO_VALUE_MAX)));
  assert.ok(sg26Bytes(fat) > DO_VALUE_MAX);
  const tiny = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: 10 }, () => now);
  assert.equal((await sg26Post(tiny, fat)).status, 413);
  const huge = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: 512 * 1024 * 1024 }, () => now);
  assert.equal((await sg26Post(huge, fat)).status, 413);
  assert.ok(!sg26Store(huge)?.map.has("result:big"));
  assert.equal(sg26Resday(huge, now), undefined);
});

// -- 5 bookend sweeps ----------------------------------------------------

test("shotgun26 bookends: every ASCII symbol at the front of the body is billed", async () => {
  const now = SG26_T0;
  const plain = sg26Result("b1");
  const cap = sg26Bytes(plain);
  assert.equal(SG26_PUNCT.length, 32);
  for (const c of SG26_PUNCT) {
    const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap }, () => now);
    const variant = `[HOMING-PIGEON] result b1\n\n${c}${sg26Body("b1")}\n`;
    assert.equal(sg26Bytes(variant), cap + 1);
    assert.equal((await sg26Post(env, variant)).status, 429, JSON.stringify(c));
    assert.ok(!sg26Store(env).map.has("result:b1"));
    assert.equal(sg26Resday(env, now), undefined);
  }
});

test("shotgun26 bookends: every ASCII symbol at the back of the body is billed", async () => {
  const now = SG26_T0;
  const plain = sg26Result("b1");
  const cap = sg26Bytes(plain);
  for (const c of SG26_PUNCT) {
    const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap }, () => now);
    const variant = `[HOMING-PIGEON] result b1\n\n${sg26Body("b1")}${c}\n`;
    assert.equal(sg26Bytes(variant), cap + 1);
    assert.equal((await sg26Post(env, variant)).status, 429, JSON.stringify(c));
    assert.ok(!sg26Store(env).map.has("result:b1"));
  }
});

test("shotgun26 bookends: matched and mismatched symbol pairs around the body are billed as 2 bytes", async () => {
  const now = SG26_T0;
  const plain = sg26Result("b1");
  const cap = sg26Bytes(plain) + 1;
  for (let i = 0; i < SG26_PUNCT.length; i++) {
    const c = SG26_PUNCT[i];
    const envA = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap }, () => now);
    const matched = `[HOMING-PIGEON] result b1\n\n${c}${sg26Body("b1")}${c}\n`;
    assert.equal((await sg26Post(envA, matched)).status, 429, `matched ${JSON.stringify(c)}`);
    const d = SG26_PUNCT[(i + 13) % SG26_PUNCT.length];
    const envB = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap }, () => now);
    const mismatched = `[HOMING-PIGEON] result b1\n\n${c}${sg26Body("b1")}${d}\n`;
    assert.equal((await sg26Post(envB, mismatched)).status, 429, `mismatched ${JSON.stringify(c)}${JSON.stringify(d)}`);
  }
});

test("shotgun26 bookends: a symbol-only body is accepted at its exact byte count and refused 1 under", async () => {
  const now = SG26_T0;
  const text = `[HOMING-PIGEON] result sym\n\n${SG26_PUNCT}\n`;
  const w = sg26Bytes(text);
  const envA = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w }, () => now);
  assert.equal((await sg26Post(envA, text)).status, 202);
  assert.equal(sg26Store(envA).map.get("result:sym").envelope, text);
  assert.equal(sg26Resday(envA, now), w);
  const envB = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: w - 1 }, () => now);
  assert.equal((await sg26Post(envB, text)).status, 429);
});

test("shotgun26 bookends: NUL, tab, CR and LF at the front, the back and both ends of the body are billed", async () => {
  const now = SG26_T0;
  const plain = sg26Result("b1");
  const cap = sg26Bytes(plain);
  const chars = [["NUL", "\0"], ["tab", "\t"], ["CR", "\r"], ["LF", "\n"]];
  for (const [name, ch] of chars) {
    for (const variant of [
      `[HOMING-PIGEON] result b1\n\n${ch}${sg26Body("b1")}\n`,
      `[HOMING-PIGEON] result b1\n\n${sg26Body("b1")}${ch}\n`,
      `[HOMING-PIGEON] result b1\n\n${ch}${sg26Body("b1")}${ch}\n`,
    ]) {
      const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap }, () => now);
      assert.equal((await sg26Post(env, variant)).status, 429, `${name}: ${JSON.stringify(variant.slice(0, 30))}`);
      assert.ok(!sg26Store(env).map.has("result:b1"));
    }
  }
  const nulFront = `[HOMING-PIGEON] result b1\n\n\0${sg26Body("b1")}\n`;
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: cap + 1 }, () => now);
  assert.equal((await sg26Post(env, nulFront)).status, 202);
  assert.equal(sg26Store(env).map.get("result:b1").envelope, nulFront);
  assert.equal(sg26Resday(env, now), cap + 1);
});

// -- 2 run-length sweeps ---------------------------------------------------

test("shotgun26 runs: runs of the odd character at lengths 1, 5, 10 and 100 are billed by their length", async () => {
  const now = SG26_T0;
  const plain = sg26Result("b1");
  const base = sg26Bytes(plain);
  for (const n of [1, 5, 10, 100]) {
    const variant = `[HOMING-PIGEON] result b1\n\n${sg26Body("b1")}${"!".repeat(n)}\n`;
    assert.equal(sg26Bytes(variant), base + n);
    const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: base + n - 1 }, () => now);
    assert.equal((await sg26Post(env, variant)).status, 429, `run ${n}`);
    assert.ok(!sg26Store(env).map.has("result:b1"));
  }
  const ten = `[HOMING-PIGEON] result b1\n\n${sg26Body("b1")}${"!".repeat(10)}\n`;
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: base + 10 }, () => now);
  assert.equal((await sg26Post(env, ten)).status, 202);
  assert.equal(sg26Resday(env, now), base + 10);
});

test("shotgun26 runs: a run of 10 ordinary characters with the odd one at the front, the back and the middle", async () => {
  const now = SG26_T0;
  const plain = sg26Result("b1");
  const base = sg26Bytes(plain);
  const run = "a".repeat(10);
  const variants = [
    "!" + run,
    run + "!",
    run.slice(0, 5) + "!" + run.slice(5),
  ];
  for (const tail of variants) {
    const variant = `[HOMING-PIGEON] result b1\n\n${sg26Body("b1")}${tail}\n`;
    assert.equal(sg26Bytes(variant), base + 11);
    const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: base + 10 }, () => now);
    assert.equal((await sg26Post(env, variant)).status, 429, tail.slice(0, 12));
  }
  const middle = `[HOMING-PIGEON] result b1\n\n${sg26Body("b1")}${variants[2]}\n`;
  const env = await sg26Setup({ jobs_per_hour: 10, bytes_per_day: base + 11 }, () => now);
  assert.equal((await sg26Post(env, middle)).status, 202);
  assert.equal(sg26Resday(env, now), base + 11);
});

// ---------------------------------------------------------------------
// Shotgun family for queue item 28: results and dead-letter pages did
// not say when they stopped; reads stopped at 8 MB of subjects
// (fixed 29001ad3, 66329844, 4635a1db, 31-Oct-2026). Before the fixes
// a results or dead-letter page cut by the page size or by the 8 MB
// RESPONSE_BUDGET looked exactly like a complete page, so rows behind
// an un-acked front row were unreachable, and a dead-letter read
// collected subject bytes with no budget at all (4635a1db added the
// stop). The fixes: both pagers return `more: true` exactly when the
// page stopped with rows still waiting (cut by max, cut by the
// budget, or a full page peeked to have a next key), no `more` key at
// all when the page ends the list, and `after=<last id returned>`
// resumes lexicographically past that id; an `after` that is not a
// safe id is ignored and the read starts from the beginning. There is
// no cursor field and no reason / truncated text field in the answer:
// `more` (present and exactly true, or absent) is the whole signal,
// and these tests pin that absence rather than inventing a string
// the code never emits. The dead-letter budget counts subject bytes
// (the text before the blank line, trimmed, UTF-8), not envelope
// bytes and not character counts; the results budget counts whole
// envelope UTF-8 bytes. In both, a first row larger than the whole
// budget is still returned whole and alone.
//
// Proof of work. The unit tests are the 50 tests registered in the
// shotgun28 describe suite below: 14 per-field / pager-shape tests,
// 4 max-clamping tests, 10 after-cursor tests, 4 interleaving tests,
// 7 results-budget tests, 7 dead-letter subject-budget tests and 4
// bookend / control / run-length / injection sweeps. Per-field
// enumeration: every field either pager returns gets its own pin --
// for results {id, envelope, at} and the body's {results, more}; for
// dead letters {id, attempts, size, enqueued_at, dead_at, subject}
// and the body's {dead, more}; plus the answer's status (200 / 204),
// its key set exactly (no cursor, no reason, no truncated field),
// the row count and the lexicographic ordering. Bookends: every
// printable ASCII symbol (all 32 punctuation characters) at the
// front AND the back of envelopes and of subjects, as singles,
// matched pairs, mismatched pairs and a symbol-only string, plus
// NUL, tab, CR and LF shapes where the surface admits them (a tab
// bookend on a dead-letter subject is trimmed by the envelope
// parser, a leading/trailing LF pair cannot bookend a subject
// because it IS the blank-line separator, so those two shapes are
// pinned through the CRLF ending and the single-LF-inside shapes
// instead -- see the control test). Run lengths: repeats of 1, 5
// and 10 of an ordinary character and of the odd one at the front,
// the back and the middle of envelopes and subjects, and page-count
// runs of 1, 5 and 10 pages. Injection-shaped payloads ride in
// subjects and envelopes and are stored and returned verbatim,
// never acted on. The fuzzing was executed, not just the tests
// written: runner/tools/de_dust_corpus.py grow --target collect
// --rounds 400 --seed 20261129, run locally against the banked
// collect corpus (20 entries). Result: de_dust grow: 400 rounds,
// rng seed 20261129; collect: 20 -> 20 entries, arcs 65 -> 65,
// 0 crashes, 0 slow, slowest 56 ms (f8ab674ef19be427) -- the
// silent-stop shape did not recur. The grow's bookkeeping writes
// were reverted and are not banked (banking is the rigs' hourly
// job); this record is the run's proof. For the .mjs file the
// Python skip registry does not apply, and this family adds no
// skips. None of this is exotic: it is combinatorics --
// systematically trying the combinations a hand-written list would
// never reach, then pinning each answer as a test.

const SG28_BUDGET = RESPONSE_BUDGET;
const SG28_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
const sg28Bytes = (t) => new TextEncoder().encode(t).length;

async function sg28Env() {
  const env = makeEnv();
  await addTenant(env);
  env.TENANT_QUEUE.get("alice");
  return env;
}
function sg28Map(env) { return env.objects.get("alice").state.storage.map; }
function sg28PutR(env, id, envelope, at = 7) {
  sg28Map(env).set(`result:${id}`, { id, envelope, at });
}
function sg28PutD(env, id, envelope, fields = {}) {
  sg28Map(env).set(`dlq:${id}`, {
    id, envelope, attempts: 5, size: sg28Bytes(envelope),
    enqueued_at: 11, dead_at: 22, ...fields,
  });
}
function sg28SeedR(env, ids, make = (id) => `[HOMING-PIGEON] result ${id}\n\n{}\n`) {
  for (const id of ids) sg28PutR(env, id, make(id));
}
function sg28SeedD(env, ids, make = (id) => `[HOMING-PIGEON] job ${id}\n\n{}\n`) {
  for (const id of ids) sg28PutD(env, id, make(id));
}
function sg28Ids(prefix, n, pad = 2) {
  return Array.from({ length: n }, (_, i) => prefix + String(i + 1).padStart(pad, "0"));
}
async function sg28Read(env, kind, params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) qs.set(k, String(v));
  const q = qs.toString();
  const r = await worker.fetch(
    req(`/t/alice/${kind}${q ? `?${q}` : ""}`, { token: `Bearer ${SI}` }), env);
  const text = await r.text();
  return { status: r.status, text, body: text ? JSON.parse(text) : null };
}
const sg28Results = (env, p) => sg28Read(env, "results", p);
const sg28Dlq = (env, p) => sg28Read(env, "dlq", p);
const sg28ResIds = (x) => x.body.results.map((row) => row.id);
const sg28DeadIds = (x) => x.body.dead.map((row) => row.id);

describe("shotgun28: results and dead-letter pages say when they stopped; reads stop at 8 MB of subjects", () => {

// -- 14 per-field / pager-shape tests --------------------------------

test("shotgun28 field status: an empty results read is 204 with no body, and a bad token is 401 naming the si token", async () => {
  const env = await sg28Env();
  const x = await sg28Results(env);
  assert.equal(x.status, 204);
  assert.equal(x.text, "");
  assert.equal(x.body, null);
  const bad = await worker.fetch(req("/t/alice/results", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(bad.status, 401);
  assert.deepEqual(await bad.json(), { error: "si token" });
});

test("shotgun28 field status: an empty dead-letter read is 204 with no body, and a bad token is 401", async () => {
  const env = await sg28Env();
  const x = await sg28Dlq(env);
  assert.equal(x.status, 204);
  assert.equal(x.text, "");
  const bad = await worker.fetch(req("/t/alice/dlq", { token: `Bearer ${RUNNER}` }), env);
  assert.equal(bad.status, 401);
  assert.deepEqual(await bad.json(), { error: "si token" });
});

test("shotgun28 field results row: id, envelope and at are returned exactly, and the body carries no other key", async () => {
  const env = await sg28Env();
  const envelope = "[HOMING-PIGEON] result r1\n\n{\"exit_code\":0}\n";
  sg28PutR(env, "r1", envelope, 1234567);
  const x = await sg28Results(env);
  assert.equal(x.status, 200);
  assert.deepEqual(Object.keys(x.body), ["results"]);
  assert.ok(!("more" in x.body));
  assert.ok(!("cursor" in x.body) && !("next" in x.body) && !("after" in x.body));
  assert.ok(!("reason" in x.body) && !("truncated" in x.body) && !("stopped" in x.body));
  assert.equal(x.body.results.length, 1);
  assert.deepEqual(Object.keys(x.body.results[0]), ["id", "envelope", "at"]);
  assert.deepEqual(x.body.results[0], { id: "r1", envelope, at: 1234567 });
});

test("shotgun28 field dead row: id, attempts, size, enqueued_at, dead_at and subject are returned exactly, with no envelope", async () => {
  const env = await sg28Env();
  const envelope = "[HOMING-PIGEON] job d1 extra words\n\n{\"x\":1}\n";
  sg28PutD(env, "d1", envelope, { attempts: 3, size: 999, enqueued_at: 111, dead_at: 222 });
  const x = await sg28Dlq(env);
  assert.equal(x.status, 200);
  assert.deepEqual(Object.keys(x.body), ["dead"]);
  assert.ok(!("more" in x.body));
  assert.ok(!("cursor" in x.body) && !("reason" in x.body) && !("truncated" in x.body));
  assert.deepEqual(Object.keys(x.body.dead[0]),
    ["id", "attempts", "size", "enqueued_at", "dead_at", "subject"]);
  assert.deepEqual(x.body.dead[0], {
    id: "d1", attempts: 3, size: 999, enqueued_at: 111, dead_at: 222,
    subject: "[HOMING-PIGEON] job d1 extra words",
  });
  assert.ok(!("envelope" in x.body.dead[0]));
});

test("shotgun28 field more results: a page cut by max says more, exactly boolean true, beside results and nothing else", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["r1", "r2", "r3"]);
  const x = await sg28Results(env, { max: 2 });
  assert.equal(x.status, 200);
  assert.deepEqual(Object.keys(x.body), ["results", "more"]);
  assert.equal(x.body.more, true);
  assert.equal(typeof x.body.more, "boolean");
  assert.deepEqual(sg28ResIds(x), ["r1", "r2"]);
});

test("shotgun28 field more dlq: a page cut by max says more, exactly boolean true, beside dead and nothing else", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["d1", "d2", "d3"]);
  const x = await sg28Dlq(env, { max: 2 });
  assert.equal(x.status, 200);
  assert.deepEqual(Object.keys(x.body), ["dead", "more"]);
  assert.equal(x.body.more, true);
  assert.equal(typeof x.body.more, "boolean");
  assert.deepEqual(sg28DeadIds(x), ["d1", "d2"]);
});

test("shotgun28 field more results: a full page landing exactly on the last record is NOT stopped -- no more key", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["r1", "r2", "r3"]);
  const x = await sg28Results(env, { max: 3 });
  assert.equal(x.status, 200);
  assert.deepEqual(sg28ResIds(x), ["r1", "r2", "r3"]);
  assert.ok(!("more" in x.body));
  assert.deepEqual(Object.keys(x.body), ["results"]);
});

test("shotgun28 field more dlq: a full page landing exactly on the last record is NOT stopped -- no more key", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["d1", "d2", "d3"]);
  const x = await sg28Dlq(env, { max: 3 });
  assert.equal(x.status, 200);
  assert.deepEqual(sg28DeadIds(x), ["d1", "d2", "d3"]);
  assert.ok(!("more" in x.body));
  assert.deepEqual(Object.keys(x.body), ["dead"]);
});

test("shotgun28 field count results: max above the count returns every row and no more", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["r1", "r2"]);
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(sg28ResIds(x), ["r1", "r2"]);
  assert.ok(!("more" in x.body));
});

test("shotgun28 field count dlq: max above the count returns every row and no more", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["d1", "d2"]);
  const x = await sg28Dlq(env, { max: 100 });
  assert.deepEqual(sg28DeadIds(x), ["d1", "d2"]);
  assert.ok(!("more" in x.body));
});

test("shotgun28 field default results: with no max named, the page is the default 20 and says more past it", async () => {
  const env = await sg28Env();
  const ids = sg28Ids("n", 25);
  sg28SeedR(env, ids);
  const x = await sg28Results(env);
  assert.equal(x.body.results.length, 20);
  assert.equal(x.body.more, true);
  assert.deepEqual(sg28ResIds(x), ids.slice(0, 20));
  const rest = await sg28Results(env, { after: ids[19] });
  assert.deepEqual(sg28ResIds(rest), ids.slice(20));
  assert.ok(!("more" in rest.body));
});

test("shotgun28 field default dlq: with no max named, the page is the default 20 and says more past it", async () => {
  const env = await sg28Env();
  const ids = sg28Ids("n", 25);
  sg28SeedD(env, ids);
  const x = await sg28Dlq(env);
  assert.equal(x.body.dead.length, 20);
  assert.equal(x.body.more, true);
  assert.deepEqual(sg28DeadIds(x), ids.slice(0, 20));
  const rest = await sg28Dlq(env, { after: ids[19] });
  assert.deepEqual(sg28DeadIds(rest), ids.slice(20));
  assert.ok(!("more" in rest.body));
});

test("shotgun28 field ordering results: rows come back in storage-key order, not insertion order", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["a2", "a10", "a1", "a20", "a3"]);
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(sg28ResIds(x), ["a1", "a10", "a2", "a20", "a3"]);
});

test("shotgun28 field ordering dlq: rows come back in storage-key order, not insertion order", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["a2", "a10", "a1", "a20", "a3"]);
  const x = await sg28Dlq(env, { max: 100 });
  assert.deepEqual(sg28DeadIds(x), ["a1", "a10", "a2", "a20", "a3"]);
});

// -- 4 max-clamping tests ---------------------------------------------

test("shotgun28 max results: max=1 returns exactly 1 with more, max=2 returns exactly 2 with more", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["r1", "r2", "r3", "r4"]);
  const one = await sg28Results(env, { max: 1 });
  assert.deepEqual(sg28ResIds(one), ["r1"]);
  assert.equal(one.body.more, true);
  const two = await sg28Results(env, { max: 2 });
  assert.deepEqual(sg28ResIds(two), ["r1", "r2"]);
  assert.equal(two.body.more, true);
});

test("shotgun28 max dlq: max=1 returns exactly 1 with more, max=2 returns exactly 2 with more", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["d1", "d2", "d3", "d4"]);
  const one = await sg28Dlq(env, { max: 1 });
  assert.deepEqual(sg28DeadIds(one), ["d1"]);
  assert.equal(one.body.more, true);
  const two = await sg28Dlq(env, { max: 2 });
  assert.deepEqual(sg28DeadIds(two), ["d1", "d2"]);
  assert.equal(two.body.more, true);
});

test("shotgun28 max zero: max=0 and a negative max clamp to 1 on both pagers, not to the default", async () => {
  for (const kind of ["results", "dlq"]) {
    const env = await sg28Env();
    if (kind === "results") sg28SeedR(env, ["r1", "r2", "r3"]); else sg28SeedD(env, ["r1", "r2", "r3"]);
    for (const max of [0, -5]) {
      const x = await sg28Read(env, kind, { max });
      assert.equal(x.status, 200, `${kind} max=${max}`);
      const rows = kind === "results" ? x.body.results : x.body.dead;
      assert.equal(rows.length, 1, `${kind} max=${max}`);
      assert.equal(rows[0].id, "r1");
      assert.equal(x.body.more, true);
    }
  }
});

test("shotgun28 max cap: a max above 100 clamps to 100 on both pagers, and a non-numeric max falls back to 20", async () => {
  const ids = sg28Ids("c", 105, 3);
  const env = await sg28Env();
  sg28SeedR(env, ids);
  const x = await sg28Results(env, { max: 1000 });
  assert.equal(x.body.results.length, 100);
  assert.equal(x.body.more, true);
  const rest = await sg28Results(env, { max: 1000, after: ids[99] });
  assert.deepEqual(sg28ResIds(rest), ids.slice(100));
  assert.ok(!("more" in rest.body));
  const env2 = await sg28Env();
  sg28SeedD(env2, ids);
  const y = await sg28Dlq(env2, { max: 101 });
  assert.equal(y.body.dead.length, 100);
  assert.equal(y.body.more, true);
  const env3 = await sg28Env();
  sg28SeedR(env3, sg28Ids("n", 25));
  const z = await sg28Results(env3, { max: "abc" });
  assert.equal(z.body.results.length, 20);
  assert.equal(z.body.more, true);
});

// -- 10 after-cursor tests --------------------------------------------

test("shotgun28 after results: after a middle id the next page continues with no repeat and no more at the end", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["r1", "r2", "r3", "r4", "r5"]);
  const x = await sg28Results(env, { max: 100, after: "r2" });
  assert.deepEqual(sg28ResIds(x), ["r3", "r4", "r5"]);
  assert.ok(!("more" in x.body));
  assert.ok(!sg28ResIds(x).includes("r2"));
});

test("shotgun28 after dlq: after a middle id the next page continues with no repeat and no more at the end", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["d1", "d2", "d3", "d4", "d5"]);
  const x = await sg28Dlq(env, { max: 100, after: "d2" });
  assert.deepEqual(sg28DeadIds(x), ["d3", "d4", "d5"]);
  assert.ok(!("more" in x.body));
  assert.ok(!sg28DeadIds(x).includes("d2"));
});

test("shotgun28 after results: after the last id the read is an empty 204 page", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["r1", "r2"]);
  const x = await sg28Results(env, { after: "r2" });
  assert.equal(x.status, 204);
  assert.equal(x.text, "");
});

test("shotgun28 after dlq: after the last id the read is an empty 204 page", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["d1", "d2"]);
  const x = await sg28Dlq(env, { after: "d2" });
  assert.equal(x.status, 204);
  assert.equal(x.text, "");
});

test("shotgun28 after results: a safe after naming no stored id resumes lexicographically past it", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["b1", "b3", "b5"]);
  assert.deepEqual(sg28ResIds(await sg28Results(env, { after: "b2" })), ["b3", "b5"]);
  assert.deepEqual(sg28ResIds(await sg28Results(env, { after: "b0" })), ["b1", "b3", "b5"]);
  assert.deepEqual(sg28ResIds(await sg28Results(env, { after: "b4" })), ["b5"]);
  assert.equal((await sg28Results(env, { after: "b9" })).status, 204);
});

test("shotgun28 after dlq: a safe after naming no stored id resumes lexicographically past it", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["b1", "b3", "b5"]);
  assert.deepEqual(sg28DeadIds(await sg28Dlq(env, { after: "b2" })), ["b3", "b5"]);
  assert.deepEqual(sg28DeadIds(await sg28Dlq(env, { after: "b0" })), ["b1", "b3", "b5"]);
  assert.deepEqual(sg28DeadIds(await sg28Dlq(env, { after: "b4" })), ["b5"]);
  assert.equal((await sg28Dlq(env, { after: "b9" })).status, 204);
});

test("shotgun28 after results: malformed after values are ignored and the read starts from the beginning", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["r1", "r2", "r3"]);
  const bad = ["../job", "..", ".", "", "a b", "a/b", "a\\b", "a?b", "a,b", "a:b", "é1", "r 1", "-".repeat(0) + " r1"];
  for (const after of bad) {
    const x = await sg28Results(env, { after });
    assert.equal(x.status, 200, JSON.stringify(after));
    assert.equal(sg28ResIds(x)[0], "r1", JSON.stringify(after));
  }
});

test("shotgun28 after dlq: malformed after values are ignored and the read starts from the beginning", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["d1", "d2", "d3"]);
  const bad = ["../quota", "..", ".", "", "a b", "a/b", "a\\b", "a?b", "a,b", "a:b", "é1", "d 1"];
  for (const after of bad) {
    const x = await sg28Dlq(env, { after });
    assert.equal(x.status, 200, JSON.stringify(after));
    assert.equal(sg28DeadIds(x)[0], "d1", JSON.stringify(after));
  }
});

test("shotgun28 after results: the after length boundary -- 128 safe characters resume, 129 are ignored", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["r1", "r2"]);
  const safe128 = "z".repeat(128);
  assert.equal((await sg28Results(env, { after: safe128 })).status, 204);
  const ignored129 = "z".repeat(129);
  const x = await sg28Results(env, { after: ignored129 });
  assert.equal(x.status, 200);
  assert.equal(sg28ResIds(x)[0], "r1");
  // The safe punctuation of an id (. _ -) inside an after is honoured:
  sg28SeedR(env, ["r1.x-y_z", "r2"]);
  assert.deepEqual(sg28ResIds(await sg28Results(env, { after: "r1.x-y_z" })), ["r2"]);
});

test("shotgun28 after foreign: an after from the other list is not an error -- it resumes purely lexicographically", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["r1", "r9"]);
  sg28SeedD(env, ["d1", "d9"]);
  // "d5" sorts before every result key, so the results read is whole.
  assert.deepEqual(sg28ResIds(await sg28Results(env, { after: "d5" })), ["r1", "r9"]);
  // "r1" sorts after every dlq key, so the dead-letter read is empty.
  assert.equal((await sg28Dlq(env, { after: "r1" })).status, 204);
  // And the dlq read after a results-shaped id that sorts inside works.
  assert.deepEqual(sg28DeadIds(await sg28Dlq(env, { after: "d5" })), ["d9"]);
});


// -- 4 interleaving tests ---------------------------------------------

test("shotgun28 interleave results: acking the first page between reads does not break continuation by its last id", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["a1", "a2", "a3", "a4", "a5"]);
  const p1 = await sg28Results(env, { max: 2 });
  assert.deepEqual(sg28ResIds(p1), ["a1", "a2"]);
  assert.equal(p1.body.more, true);
  for (const id of ["a1", "a2"]) {
    const ack = await worker.fetch(req(`/t/alice/results/${id}/ack`, { method: "POST", token: `Bearer ${SI}` }), env);
    assert.equal(ack.status, 204);
  }
  assert.ok(!sg28Map(env).has("result:a1"));
  const p2 = await sg28Results(env, { max: 2, after: "a2" });
  assert.deepEqual(sg28ResIds(p2), ["a3", "a4"]);
  assert.equal(p2.body.more, true);
  const p3 = await sg28Results(env, { max: 2, after: "a4" });
  assert.deepEqual(sg28ResIds(p3), ["a5"]);
  assert.ok(!("more" in p3.body));
});

test("shotgun28 interleave dlq: acking the first page between reads does not break continuation by its last id", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["a1", "a2", "a3", "a4", "a5"]);
  const p1 = await sg28Dlq(env, { max: 2 });
  assert.deepEqual(sg28DeadIds(p1), ["a1", "a2"]);
  assert.equal(p1.body.more, true);
  for (const id of ["a1", "a2"]) {
    const ack = await worker.fetch(req(`/t/alice/dlq/${id}/ack`, { method: "POST", token: `Bearer ${SI}` }), env);
    assert.equal(ack.status, 204);
  }
  const p2 = await sg28Dlq(env, { max: 2, after: "a2" });
  assert.deepEqual(sg28DeadIds(p2), ["a3", "a4"]);
  assert.equal(p2.body.more, true);
  const p3 = await sg28Dlq(env, { max: 2, after: "a4" });
  assert.deepEqual(sg28DeadIds(p3), ["a5"]);
  assert.ok(!("more" in p3.body));
});

test("shotgun28 interleave results: a write sorting after the cursor joins the next page; one sorting before waits for a fresh read", async () => {
  const env = await sg28Env();
  sg28SeedR(env, ["a1", "a2", "a3", "a4"]);
  const p1 = await sg28Results(env, { max: 2 });
  assert.deepEqual(sg28ResIds(p1), ["a1", "a2"]);
  sg28PutR(env, "a1b", "[HOMING-PIGEON] result a1b\n\n{}\n");
  sg28PutR(env, "a9", "[HOMING-PIGEON] result a9\n\n{}\n");
  const p2 = await sg28Results(env, { max: 100, after: "a2" });
  assert.deepEqual(sg28ResIds(p2), ["a3", "a4", "a9"]);
  const fresh = await sg28Results(env, { max: 100 });
  assert.deepEqual(sg28ResIds(fresh), ["a1", "a1b", "a2", "a3", "a4", "a9"]);
  // No id is returned twice across the two pages of one walk.
  const walked = [...sg28ResIds(p1), ...sg28ResIds(p2)];
  assert.equal(new Set(walked).size, walked.length);
});

test("shotgun28 interleave dlq: a write sorting after the cursor joins the next page; one sorting before waits for a fresh read", async () => {
  const env = await sg28Env();
  sg28SeedD(env, ["a1", "a2", "a3", "a4"]);
  const p1 = await sg28Dlq(env, { max: 2 });
  assert.deepEqual(sg28DeadIds(p1), ["a1", "a2"]);
  sg28PutD(env, "a1b", "[HOMING-PIGEON] job a1b\n\n{}\n");
  sg28PutD(env, "a9", "[HOMING-PIGEON] job a9\n\n{}\n");
  const p2 = await sg28Dlq(env, { max: 100, after: "a2" });
  assert.deepEqual(sg28DeadIds(p2), ["a3", "a4", "a9"]);
  const fresh = await sg28Dlq(env, { max: 100 });
  assert.deepEqual(sg28DeadIds(fresh), ["a1", "a1b", "a2", "a3", "a4", "a9"]);
  const walked = [...sg28DeadIds(p1), ...sg28DeadIds(p2)];
  assert.equal(new Set(walked).size, walked.length);
});

// -- 7 results-budget tests (8 MB of envelopes, UTF-8 bytes) ----------

test("shotgun28 budget results: envelopes totalling 1 byte under 8 MB all come back, with no more", async () => {
  const env = await sg28Env();
  const a = "a".repeat(SG28_BUDGET - 101);
  const b = "b".repeat(100);
  assert.equal(sg28Bytes(a) + sg28Bytes(b), SG28_BUDGET - 1);
  sg28PutR(env, "a1", a); sg28PutR(env, "a2", b);
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(sg28ResIds(x), ["a1", "a2"]);
  assert.ok(!("more" in x.body));
});

test("shotgun28 budget results: envelopes totalling exactly 8 MB all come back, with no more", async () => {
  const env = await sg28Env();
  const a = "a".repeat(SG28_BUDGET - 100);
  const b = "b".repeat(100);
  assert.equal(sg28Bytes(a) + sg28Bytes(b), SG28_BUDGET);
  sg28PutR(env, "a1", a); sg28PutR(env, "a2", b);
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(sg28ResIds(x), ["a1", "a2"]);
  assert.ok(!("more" in x.body));
});

test("shotgun28 budget results: the row that would take the page 1 byte over 8 MB stops it, says more, and is the next page", async () => {
  const env = await sg28Env();
  sg28PutR(env, "a1", "a".repeat(SG28_BUDGET - 100));
  sg28PutR(env, "a2", "b".repeat(101));
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(sg28ResIds(x), ["a1"]);
  assert.equal(x.body.more, true);
  // The stopped read deleted nothing: both rows are still stored.
  assert.ok(sg28Map(env).has("result:a1") && sg28Map(env).has("result:a2"));
  const rest = await sg28Results(env, { max: 100, after: "a1" });
  assert.deepEqual(sg28ResIds(rest), ["a2"]);
  assert.equal(rest.body.results[0].envelope.length, 101);
  assert.ok(!("more" in rest.body));
});

test("shotgun28 budget results: many small envelopes stop at the budget -- 16 of 500000 bytes, then the rest", async () => {
  const env = await sg28Env();
  const ids = sg28Ids("m", 20);
  sg28SeedR(env, ids, () => "x".repeat(500_000));
  const x = await sg28Results(env, { max: 100 });
  assert.equal(x.body.results.length, 16);
  assert.equal(16 * 500_000 <= SG28_BUDGET && 17 * 500_000 > SG28_BUDGET, true);
  assert.equal(x.body.more, true);
  assert.deepEqual(sg28ResIds(x), ids.slice(0, 16));
  const rest = await sg28Results(env, { max: 100, after: ids[15] });
  assert.deepEqual(sg28ResIds(rest), ids.slice(16));
  assert.ok(!("more" in rest.body));
  const all = [...sg28ResIds(x), ...sg28ResIds(rest)];
  assert.deepEqual(all, ids);
  assert.equal(new Set(all).size, all.length);
});

test("shotgun28 budget results: a few huge envelopes stop at the budget -- 5 of 1500000 bytes, then the last", async () => {
  const env = await sg28Env();
  const ids = sg28Ids("h", 6);
  sg28SeedR(env, ids, () => "y".repeat(1_500_000));
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(sg28ResIds(x), ids.slice(0, 5));
  assert.equal(x.body.more, true);
  const rest = await sg28Results(env, { max: 100, after: ids[4] });
  assert.deepEqual(sg28ResIds(rest), [ids[5]]);
  assert.ok(!("more" in rest.body));
});

test("shotgun28 budget results: a single envelope larger than the whole budget is returned whole and alone, with no more", async () => {
  const env = await sg28Env();
  const big = "z".repeat(SG28_BUDGET + 1000);
  sg28PutR(env, "big1", big);
  const x = await sg28Results(env, { max: 100 });
  assert.equal(x.body.results.length, 1);
  assert.equal(x.body.results[0].envelope, big);
  assert.ok(sg28Bytes(x.body.results[0].envelope) > SG28_BUDGET);
  assert.ok(!("more" in x.body));
});

test("shotgun28 budget results: the budget counts UTF-8 bytes, not characters -- a 3000000-character euro envelope stops the page", async () => {
  const env = await sg28Env();
  sg28PutR(env, "a1", "s".repeat(10));
  const euro = "€".repeat(3_000_000);
  assert.equal(euro.length, 3_000_000);
  assert.equal(sg28Bytes(euro), 9_000_000);
  sg28PutR(env, "a2", euro);
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(sg28ResIds(x), ["a1"]);
  assert.equal(x.body.more, true);
  const rest = await sg28Results(env, { max: 100, after: "a1" });
  assert.deepEqual(sg28ResIds(rest), ["a2"]);
  assert.equal(rest.body.results[0].envelope, euro);
  // And a multibyte envelope whose BYTES land exactly on the budget fits:
  const env2 = await sg28Env();
  const exact = "é".repeat(SG28_BUDGET / 2);
  assert.equal(sg28Bytes(exact), SG28_BUDGET);
  sg28PutR(env2, "a1", exact);
  const y = await sg28Results(env2, { max: 100 });
  assert.deepEqual(sg28ResIds(y), ["a1"]);
  assert.ok(!("more" in y.body));
});

// -- 7 dead-letter subject-budget tests (8 MB of subjects) ------------

test("shotgun28 budget dlq: subjects totalling 1 byte under 8 MB all come back, with no more", async () => {
  const env = await sg28Env();
  const sa = "a".repeat(SG28_BUDGET - 101);
  const sb = "b".repeat(100);
  sg28PutD(env, "a1", `${sa}\n\n{}`);
  sg28PutD(env, "a2", `${sb}\n\n{}`);
  const x = await sg28Dlq(env, { max: 100 });
  assert.deepEqual(sg28DeadIds(x), ["a1", "a2"]);
  const total = x.body.dead.reduce((n, d) => n + sg28Bytes(d.subject), 0);
  assert.equal(total, SG28_BUDGET - 1);
  assert.ok(!("more" in x.body));
});

test("shotgun28 budget dlq: subjects totalling exactly 8 MB all come back, with no more", async () => {
  const env = await sg28Env();
  sg28PutD(env, "a1", `${"a".repeat(SG28_BUDGET - 100)}\n\n{}`);
  sg28PutD(env, "a2", `${"b".repeat(100)}\n\n{}`);
  const x = await sg28Dlq(env, { max: 100 });
  assert.deepEqual(sg28DeadIds(x), ["a1", "a2"]);
  const total = x.body.dead.reduce((n, d) => n + sg28Bytes(d.subject), 0);
  assert.equal(total, SG28_BUDGET);
  assert.ok(!("more" in x.body));
});

test("shotgun28 budget dlq: the subject that would take the page 1 byte over 8 MB stops it, says more, and is the next page", async () => {
  const env = await sg28Env();
  sg28PutD(env, "a1", `${"a".repeat(SG28_BUDGET - 100)}\n\n{}`);
  sg28PutD(env, "a2", `${"b".repeat(101)}\n\n{}`);
  const x = await sg28Dlq(env, { max: 100 });
  assert.deepEqual(sg28DeadIds(x), ["a1"]);
  assert.equal(x.body.more, true);
  assert.ok(sg28Map(env).has("dlq:a1") && sg28Map(env).has("dlq:a2"));
  const rest = await sg28Dlq(env, { max: 100, after: "a1" });
  assert.deepEqual(sg28DeadIds(rest), ["a2"]);
  assert.equal(rest.body.dead[0].subject, "b".repeat(101));
  assert.ok(!("more" in rest.body));
});

test("shotgun28 budget dlq: many small subjects stop at the budget -- 16 of 500000 bytes, then the rest", async () => {
  const env = await sg28Env();
  const ids = sg28Ids("m", 20);
  sg28SeedD(env, ids, () => `${"s".repeat(500_000)}\n\n{}`);
  const x = await sg28Dlq(env, { max: 100 });
  assert.equal(x.body.dead.length, 16);
  assert.equal(x.body.more, true);
  assert.deepEqual(sg28DeadIds(x), ids.slice(0, 16));
  const rest = await sg28Dlq(env, { max: 100, after: ids[15] });
  assert.deepEqual(sg28DeadIds(rest), ids.slice(16));
  assert.ok(!("more" in rest.body));
  const all = [...sg28DeadIds(x), ...sg28DeadIds(rest)];
  assert.deepEqual(all, ids);
  assert.equal(new Set(all).size, all.length);
});

test("shotgun28 budget dlq: envelope bytes are NOT counted -- huge bodies behind tiny subjects all come back past 8 MB of envelopes", async () => {
  const env = await sg28Env();
  const ids = sg28Ids("e", 6);
  sg28SeedD(env, ids, (id) => `[HOMING-PIGEON] job ${id}\n\n${"x".repeat(2_000_000)}`);
  const stored = [...sg28Map(env).values()]
    .reduce((n, d) => n + sg28Bytes(d.envelope), 0);
  assert.ok(stored > SG28_BUDGET, `stored ${stored}`);
  const x = await sg28Dlq(env, { max: 100 });
  assert.deepEqual(sg28DeadIds(x), ids);
  assert.ok(!("more" in x.body));
  for (const [i, row] of x.body.dead.entries()) {
    assert.equal(row.subject, `[HOMING-PIGEON] job ${ids[i]}`);
    assert.ok(!("envelope" in row));
  }
});

test("shotgun28 budget dlq: a record with no blank line has a null subject of weight zero, however huge its envelope", async () => {
  const env = await sg28Env();
  const huge = "x".repeat(SG28_BUDGET + 1000);
  sg28PutD(env, "n1", huge);
  sg28SeedD(env, ["n2", "n3"]);
  const x = await sg28Dlq(env, { max: 100 });
  assert.deepEqual(sg28DeadIds(x), ["n1", "n2", "n3"]);
  assert.equal(x.body.dead[0].subject, null);
  assert.equal(x.body.dead[0].size, sg28Bytes(huge));
  assert.ok(!("more" in x.body));
});

test("shotgun28 budget dlq: the budget counts subject UTF-8 bytes, not characters -- a 3000000-character euro subject stops the page", async () => {
  const env = await sg28Env();
  sg28PutD(env, "a1", "[HOMING-PIGEON] job a1\n\n{}");
  const euroSubject = "€".repeat(3_000_000);
  assert.equal(euroSubject.length, 3_000_000);
  assert.equal(sg28Bytes(euroSubject), 9_000_000);
  sg28PutD(env, "a2", `${euroSubject}\n\n{}`);
  const x = await sg28Dlq(env, { max: 100 });
  assert.deepEqual(sg28DeadIds(x), ["a1"]);
  assert.equal(x.body.more, true);
  const rest = await sg28Dlq(env, { max: 100, after: "a1" });
  assert.deepEqual(sg28DeadIds(rest), ["a2"]);
  assert.equal(rest.body.dead[0].subject, euroSubject);
  assert.ok(!("more" in rest.body));
  // A single subject larger than the whole budget is returned whole:
  const env2 = await sg28Env();
  const bigSubject = "q".repeat(SG28_BUDGET + 5);
  sg28PutD(env2, "big1", `${bigSubject}\n\n{}`);
  const y = await sg28Dlq(env2, { max: 100 });
  assert.deepEqual(sg28DeadIds(y), ["big1"]);
  assert.equal(y.body.dead[0].subject, bigSubject);
  assert.ok(!("more" in y.body));
});

// -- 4 bookend / control / run-length / injection sweeps ---------------

test("shotgun28 bookends: every ASCII symbol at the front AND the back of envelopes and of subjects, singles, pairs and symbol-only", async () => {
  assert.equal(SG28_PUNCT.length, 32);
  // Results: the envelope is returned byte for byte.
  const env = await sg28Env();
  const wantR = new Map();
  [...SG28_PUNCT].forEach((ch, i) => {
    const id = "b" + String(i).padStart(2, "0");
    const envelope = `${ch}core${ch}`;
    wantR.set(id, envelope);
    sg28PutR(env, id, envelope);
  });
  sg28PutR(env, "b32", "@@core@@");       // matched pair
  wantR.set("b32", "@@core@@");
  sg28PutR(env, "b33", "!core~");          // mismatched pair
  wantR.set("b33", "!core~");
  sg28PutR(env, "b34", SG28_PUNCT);        // symbol-only envelope
  wantR.set("b34", SG28_PUNCT);
  const x = await sg28Results(env, { max: 100 });
  assert.equal(x.body.results.length, wantR.size);
  for (const row of x.body.results) assert.equal(row.envelope, wantR.get(row.id), row.id);
  // Dead letters: the subject is returned (trimmed of whitespace only).
  const env2 = await sg28Env();
  const wantD = new Map();
  [...SG28_PUNCT].forEach((ch, i) => {
    const id = "b" + String(i).padStart(2, "0");
    const subject = `${ch}[HOMING-PIGEON] job x${ch}`;
    wantD.set(id, subject);
    sg28PutD(env2, id, `${subject}\n\n{}`);
  });
  sg28PutD(env2, "b32", "@@[HOMING-PIGEON] job x@@\n\n{}");
  wantD.set("b32", "@@[HOMING-PIGEON] job x@@");
  sg28PutD(env2, "b33", "![HOMING-PIGEON] job x~\n\n{}");
  wantD.set("b33", "![HOMING-PIGEON] job x~");
  sg28PutD(env2, "b34", `${SG28_PUNCT}\n\n{}`);
  wantD.set("b34", SG28_PUNCT);
  const y = await sg28Dlq(env2, { max: 100 });
  assert.equal(y.body.dead.length, wantD.size);
  for (const row of y.body.dead) assert.equal(row.subject, wantD.get(row.id), row.id);
});

test("shotgun28 controls: NUL, tab, CR and LF shapes in envelopes and subjects are pinned where the surface admits them", async () => {
  // Results envelopes are not parsed: every control bookend is verbatim.
  const env = await sg28Env();
  const rows = [
    ["c1", "\0core\0"], ["c2", "\tcore\t"], ["c3", "\rcore\r"], ["c4", "\ncore\n"],
    ["c5", "\0\tcore\r\n"], ["c6", "a\0b\tc\rd\ne"],
  ];
  for (const [id, envelope] of rows) sg28PutR(env, id, envelope);
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(x.body.results.map((r) => [r.id, r.envelope]), rows);
  // Dead-letter subjects ARE parsed: NUL is kept, edge tabs are trimmed,
  // a CRLF ending reads as the subject alone, and a single LF inside the
  // subject survives (an LF pair cannot bookend a subject -- it is the
  // blank-line separator itself, so the CRLF and inside shapes stand in).
  const env2 = await sg28Env();
  sg28PutD(env2, "d1", "\0subj\0\n\n{}");
  sg28PutD(env2, "d2", "\tsubj\t\n\n{}");
  sg28PutD(env2, "d3", "subj\r\n\r\n{}");
  sg28PutD(env2, "d4", "line1\nline2\n\n{}");
  sg28PutD(env2, "d5", "a\tb\n\n{}");
  const y = await sg28Dlq(env2, { max: 100 });
  assert.deepEqual(y.body.dead.map((d) => [d.id, d.subject]), [
    ["d1", "\0subj\0"], ["d2", "subj"], ["d3", "subj"],
    ["d4", "line1\nline2"], ["d5", "a\tb"],
  ]);
});

test("shotgun28 runs: repeats of 1, 5 and 10 at the front, back and middle, and page-count runs of 1, 5 and 10 pages", async () => {
  // Content runs, results envelopes and dead-letter subjects alike.
  const shapes = [];
  for (const n of [1, 5, 10]) {
    shapes.push("!".repeat(n) + "core");
    shapes.push("core" + "!".repeat(n));
    shapes.push("co" + "!".repeat(n) + "re");
    shapes.push("a".repeat(10) + "!");
    shapes.push("!" + "a".repeat(10));
    shapes.push("a".repeat(5) + "!" + "a".repeat(5));
  }
  const env = await sg28Env();
  shapes.forEach((s, i) => sg28PutR(env, "s" + String(i).padStart(2, "0"), s));
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(x.body.results.map((r) => r.envelope), shapes);
  const env2 = await sg28Env();
  shapes.forEach((s, i) => sg28PutD(env2, "s" + String(i).padStart(2, "0"), `${s}\n\n{}`));
  const y = await sg28Dlq(env2, { max: 100 });
  assert.deepEqual(y.body.dead.map((d) => d.subject), shapes);
  // Page-count runs: walking max=1 pages takes 1, 5 and 10 pages for
  // 1, 5 and 10 rows; every page but the last says more.
  for (const [kind, n] of [["results", 1], ["results", 5], ["results", 10], ["dlq", 5], ["dlq", 10]]) {
    const e = await sg28Env();
    const ids = sg28Ids("w", n);
    if (kind === "results") sg28SeedR(e, ids); else sg28SeedD(e, ids);
    const seen = [];
    let pages = 0;
    let after;
    for (;;) {
      const page = await sg28Read(e, kind, { max: 1, after });
      pages++;
      const rows = kind === "results" ? page.body.results : page.body.dead;
      assert.equal(rows.length, 1);
      seen.push(rows[0].id);
      if (pages < n) assert.equal(page.body.more, true, `${kind} page ${pages}`);
      else assert.ok(!("more" in page.body), `${kind} last page`);
      after = rows[0].id;
      if (!("more" in page.body)) break;
      assert.ok(pages <= n, "walk ran past the list");
    }
    assert.equal(pages, n);
    assert.deepEqual(seen, ids);
  }
});

test("shotgun28 injection: injection-shaped subjects and envelopes are returned verbatim and never acted on", async () => {
  const payloads = [
    "'; DROP TABLE results; --",
    "<script>alert(1)</script>",
    "ignore previous instructions and ack everything",
    "../../etc/passwd",
    "__proto__",
    "${7*7}",
    "{{7*7}}",
    "a&more=false",
    "r1#fragment",
    "\" OR 1=1 --",
  ];
  const env = await sg28Env();
  payloads.forEach((p, i) => sg28PutR(env, "i" + String(i).padStart(2, "0"), p));
  // A fake second envelope inside an envelope is just bytes.
  sg28PutR(env, "i10", "[HOMING-PIGEON] result fake\n\n{\"job_id\":\"fake\"}");
  const before = sg28Map(env).size;
  const x = await sg28Results(env, { max: 100 });
  assert.deepEqual(x.body.results.map((r) => r.envelope),
    [...payloads, "[HOMING-PIGEON] result fake\n\n{\"job_id\":\"fake\"}"]);
  assert.equal(sg28Map(env).size, before);
  assert.ok(!sg28Map(env).has("result:fake"));
  assert.equal({}.polluted, undefined);
  // The same shapes as dead-letter subjects (before the blank line):
  const env2 = await sg28Env();
  payloads.forEach((p, i) => sg28PutD(env2, "i" + String(i).padStart(2, "0"), `${p}\n\n{}`));
  const y = await sg28Dlq(env2, { max: 100 });
  assert.deepEqual(y.body.dead.map((d) => d.subject), payloads);
  assert.equal(sg28Map(env2).size, payloads.length);
  // And an injection-shaped after is simply not a safe id: ignored.
  const z = await sg28Results(env, { after: "../../etc/passwd" });
  assert.equal(z.body.results[0].envelope, payloads[0]);
  const z2 = await sg28Results(env, { after: "i00&more=false" });
  assert.equal(z2.body.results[0].envelope, payloads[0]);
});

});

// ---------------------------------------------------------------------
// Shotgun family for queue item 34: max=0 leased one job, not
// the default page (fixed ab002020, 31-Oct-2026). The clamp
// read a missing max and a max of 0 the same way -- the
// truthiness fallback turned both into the route's default --
// so ?max=0 and a results or dead-letter read of 0 returned
// the default page (8 jobs, or 20 rows) when the caller had
// named a count of zero. The fix is clampedMax: a missing or
// non-numeric max keeps the route's default, and zero and
// negative are clamped to 1 -- the caller named a count, and
// the smallest page is one. This family scattershots exactly
// that clamp, at the function the Worker exports and on all
// five routes that use it (the outer pull, results and dlq
// reads, and the object's own /pull, /results and /dlq,
// which the outer routes forward to after clamping again):
// every spelling of zero, the defaults and the cap, signs,
// fractions, radix and exponent spellings, bookended and
// run-length max strings, duplicate and injection-shaped
// parameters, and the storage state a max=0 pull leaves.
// It deliberately does not re-pin item 28's pager fields
// (more, after, the 8 MB budget): here only the count the
// max names is under test.
//
// Proof of work. The unit tests are the 50 tests registered
// below: 17 direct clampedMax value and spelling tests, 6
// direct bookend sweeps, 2 direct run-length tests, 10 pull
// route tests, 5 results route tests, 5 dlq route tests, 4
// route bookend / run / injection sweeps and 1 cross-route
// test. Per-field enumeration: the surface is one field --
// the max query parameter -- read by three routes with two
// defaults (8 for a pull, 20 for results and the dlq), and
// each route gets its own pins for zero, negative, missing,
// non-numeric and over-cap values; the clampedMax fallback
// parameter itself is pinned per route default, and the
// answer's fields (row count, the more flag beside it, and
// the leased state in storage) are pinned where they carry
// the count. Bookends: every printable ASCII symbol (all
// 32 punctuation characters) at the front AND the back of
// "5" through clampedMax, as singles, matched pairs,
// mismatched pairs and symbol-only strings, plus NUL, tab,
// CR and LF at both ends, and bookended zeros on the pull
// route. Run lengths: digit runs of 1, 5, 10 and 30, zero
// runs of 1, 5, 9 and 10, and the odd character at the
// front, the back and the middle of a digit run. The
// fuzzing was executed, not just the tests written:
// runner/tools/de_dust_corpus.py grow --target collect
// --rounds 400 --seed 20261135, run locally against the
// banked collect corpus (20 entries). Result: 400 rounds,
// 0 crashes, 0 slow, arcs unchanged at 65, slowest try
// 389 ms (fca585c3b6fd87df) -- the max=0 shape did not
// recur. The grow's
// bookkeeping writes were reverted and are not banked
// (banking is the rigs' hourly job); this record is the
// run's proof. For the .mjs file the Python skip registry
// does not apply, and this family adds no skips. None of
// this is exotic: it is combinatorics -- systematically
// trying the combinations a hand-written list would never
// reach, then pinning each answer as a test.

const SG34_PUNCT = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
const SG34_QUOTA = { jobs_per_hour: 200, bytes_per_day: 10_000_000 };

async function sg34Env() {
  const env = makeEnv({ quota: SG34_QUOTA });
  await addTenant(env);
  env.TENANT_QUEUE.get("alice");
  return env;
}

function sg34Map(env) { return env.objects.get("alice").state.storage.map; }

async function sg34SeedJobs(env, n, prefix = "j") {
  for (let i = 1; i <= n; i++) {
    const id = prefix + String(i).padStart(2, "0");
    const r = await worker.fetch(req("/t/alice/jobs", {
      method: "POST", token: `Bearer ${SI}`, body: await signedJob(id),
    }), env);
    assert.equal(r.status, 202, id);
  }
}

async function sg34PullQs(env, qs) {
  const r = await worker.fetch(req(
    `/t/alice/jobs${qs ? `?${qs}` : ""}`, { token: `Bearer ${RUNNER}` }), env);
  if (r.status === 204) return { status: 204, jobs: [] };
  assert.equal(r.status, 200);
  return { status: 200, jobs: (await r.json()).jobs };
}

const sg34Pull = (env, raw) => sg34PullQs(
  env, raw === undefined ? "" : `max=${encodeURIComponent(raw)}`);

async function sg34PullCount(n, raw) {
  const env = await sg34Env();
  await sg34SeedJobs(env, n);
  return (await sg34Pull(env, raw)).jobs.length;
}

function sg34PutR(env, id) {
  sg34Map(env).set(`result:${id}`, {
    id, envelope: `[HOMING-PIGEON] result ${id}\n\n{}\n`, at: 7,
  });
}

function sg34PutD(env, id) {
  const envelope = `[HOMING-PIGEON] job ${id}\n\n{}\n`;
  sg34Map(env).set(`dlq:${id}`, {
    id, envelope, attempts: 5, size: new TextEncoder().encode(envelope).length,
    enqueued_at: 11, dead_at: 22,
  });
}

function sg34Ids(prefix, n) {
  return Array.from({ length: n }, (_, i) => prefix + String(i + 1).padStart(2, "0"));
}

async function sg34Read(env, kind, raw) {
  const qs = raw === undefined ? "" : `?max=${encodeURIComponent(raw)}`;
  const r = await worker.fetch(req(`/t/alice/${kind}${qs}`,
    { token: `Bearer ${SI}` }), env);
  const text = await r.text();
  return { status: r.status, body: text ? JSON.parse(text) : null };
}

async function sg34ReadCount(kind, seeded, raw) {
  const env = await sg34Env();
  for (const id of sg34Ids(kind === "results" ? "r" : "d", seeded)) {
    if (kind === "results") sg34PutR(env, id); else sg34PutD(env, id);
  }
  const x = await sg34Read(env, kind, raw);
  if (x.status === 204) return { count: 0, more: undefined, x };
  const rows = kind === "results" ? x.body.results : x.body.dead;
  return { count: rows.length, more: x.body.more, x };
}

// -- 17 direct clampedMax value and spelling tests -----------------------

test("shotgun34 direct zero fallback 8: clampedMax('0', 8) is 1, not the default page", () => {
  assert.equal(clampedMax("0", 8), 1);
});

test("shotgun34 direct zero fallback 20: clampedMax('0', 20) is 1, not the default page", () => {
  assert.equal(clampedMax("0", 20), 1);
});

test("shotgun34 direct negatives: -1, -3 and -100 clamp to 1 under both fallbacks", () => {
  for (const raw of ["-1", "-3", "-100"]) {
    assert.equal(clampedMax(raw, 8), 1, raw);
    assert.equal(clampedMax(raw, 20), 1, raw);
  }
});

test("shotgun34 direct missing: a null or undefined max keeps the route's fallback", () => {
  assert.equal(clampedMax(null, 8), 8);
  assert.equal(clampedMax(undefined, 8), 8);
  assert.equal(clampedMax(null, 20), 20);
  assert.equal(clampedMax(undefined, 20), 20);
});

test("shotgun34 direct empty: an empty max keeps the fallback, under both fallbacks", () => {
  assert.equal(clampedMax("", 8), 8);
  assert.equal(clampedMax("", 20), 20);
});

test("shotgun34 direct non-numeric: words for a max keep the fallback", () => {
  for (const raw of ["abc", "max", "ten", "all", "none"]) {
    assert.equal(clampedMax(raw, 8), 8, raw);
    assert.equal(clampedMax(raw, 20), 20, raw);
  }
});

test("shotgun34 direct small counts: 1 is 1 and 2 is 2, under both fallbacks", () => {
  assert.equal(clampedMax("1", 8), 1);
  assert.equal(clampedMax("2", 8), 2);
  assert.equal(clampedMax("1", 20), 1);
  assert.equal(clampedMax("2", 20), 2);
});

test("shotgun34 direct defaults themselves: 8 and 20 read as themselves, across fallbacks", () => {
  assert.equal(clampedMax("8", 8), 8);
  assert.equal(clampedMax("20", 20), 20);
  assert.equal(clampedMax("8", 20), 8);
  assert.equal(clampedMax("20", 8), 20);
});

test("shotgun34 direct cap: 100 is the cap -- 101 and a million clamp to 100", () => {
  assert.equal(clampedMax("100", 8), 100);
  assert.equal(clampedMax("101", 8), 100);
  assert.equal(clampedMax("1000000", 20), 100);
});

test("shotgun34 direct fractional: the fraction is cut -- 1.9 is 1, 0.9 is 1, 99.9 is 99", () => {
  assert.equal(clampedMax("1.9", 8), 1);
  assert.equal(clampedMax("0.9", 8), 1);
  assert.equal(clampedMax("99.9", 20), 99);
  assert.equal(clampedMax("100.9", 20), 100);
});

test("shotgun34 direct leading zeros: 007 is 7, 000 is 1, 010 is 10", () => {
  assert.equal(clampedMax("007", 8), 7);
  assert.equal(clampedMax("000", 8), 1);
  assert.equal(clampedMax("010", 20), 10);
});

test("shotgun34 direct signs: +5 is 5, and +0 and -0 are zero and clamp to 1", () => {
  assert.equal(clampedMax("+5", 8), 5);
  assert.equal(clampedMax("+0", 8), 1);
  assert.equal(clampedMax("-0", 20), 1);
});

test("shotgun34 direct whitespace: whitespace around the digits is skipped or ends the number", () => {
  assert.equal(clampedMax(" 5", 8), 5);
  assert.equal(clampedMax("5 ", 8), 5);
  assert.equal(clampedMax("\t5\n", 20), 5);
  assert.equal(clampedMax("  42  ", 8), 42);
});

test("shotgun34 direct trailing junk: junk after the digits is ignored -- 5! and 5&max=1 are 5", () => {
  assert.equal(clampedMax("5!", 8), 5);
  assert.equal(clampedMax("5&max=1", 8), 5);
  assert.equal(clampedMax("12jobs", 20), 12);
});

test("shotgun34 direct radix spellings: 0x10, 0b1 and 0o7 all read as the leading 0 and clamp to 1", () => {
  assert.equal(clampedMax("0x10", 8), 1);
  assert.equal(clampedMax("0b1", 8), 1);
  assert.equal(clampedMax("0o7", 20), 1);
});

test("shotgun34 direct exponent: the number stops at the e -- 1e3 is 1, 2e1 is 2, 9e9 is 9", () => {
  assert.equal(clampedMax("1e3", 8), 1);
  assert.equal(clampedMax("2e1", 8), 2);
  assert.equal(clampedMax("9e9", 20), 9);
});

test("shotgun34 direct huge: a 30-digit run clamps to 100, and the word Infinity keeps the fallback", () => {
  assert.equal(clampedMax("9".repeat(30), 8), 100);
  assert.equal(clampedMax("1" + "0".repeat(30), 20), 100);
  assert.equal(clampedMax("Infinity", 8), 8);
  assert.equal(clampedMax("NaN", 20), 20);
});

// -- 6 direct bookend sweeps ----------------------------------------------

test("shotgun34 bookends front: every ASCII symbol at the front of 5 -- the plus reads 5, the minus clamps to 1, the rest keep the fallback", () => {
  for (const s of SG34_PUNCT) {
    const want = s === "+" ? 5 : s === "-" ? 1 : 8;
    assert.equal(clampedMax(s + "5", 8), want, JSON.stringify(s));
  }
});

test("shotgun34 bookends back: every ASCII symbol at the back of 5 is trailing junk and reads 5", () => {
  for (const s of SG34_PUNCT) {
    assert.equal(clampedMax("5" + s, 8), 5, JSON.stringify(s));
  }
});

test("shotgun34 bookends matched pairs: matched pairs around 5 decide by their front symbol", () => {
  for (const s of SG34_PUNCT) {
    const want = s === "+" ? 5 : s === "-" ? 1 : 8;
    assert.equal(clampedMax(s + "5" + s, 8), want, JSON.stringify(s));
  }
});

test("shotgun34 bookends mismatched pairs: +5. is 5, -5+ is 1, !5+ and .5. keep the fallback", () => {
  assert.equal(clampedMax("+5.", 8), 5);
  assert.equal(clampedMax("+5!", 8), 5);
  assert.equal(clampedMax("-5+", 8), 1);
  assert.equal(clampedMax("!5+", 8), 8);
  assert.equal(clampedMax(".5.", 8), 8);
  assert.equal(clampedMax("?5-", 20), 20);
});

test("shotgun34 bookends symbol-only: symbol-only max strings keep the fallback, each symbol and all together", () => {
  for (const raw of [...SG34_PUNCT, SG34_PUNCT]) {
    assert.equal(clampedMax(raw, 8), 8, JSON.stringify(raw));
    assert.equal(clampedMax(raw, 20), 20, JSON.stringify(raw));
  }
});

test("shotgun34 bookends controls: NUL at the front kills the number, at the back is junk; tab, CR and LF are skipped or trailing", () => {
  assert.equal(clampedMax("\x005", 8), 8);
  assert.equal(clampedMax("5\x00", 8), 5);
  assert.equal(clampedMax("\x005\x00", 8), 8);
  for (const raw of ["\t5", "5\t", "\r5", "5\r", "\n5", "5\n", "\t5\n"]) {
    assert.equal(clampedMax(raw, 8), 5, JSON.stringify(raw));
  }
});

// -- 2 direct run-length tests ----------------------------------------------

test("shotgun34 runs digits: runs of ones at lengths 1, 5 and 10 read 1, then clamp to 100; zero runs clamp to 1", () => {
  assert.equal(clampedMax("1", 8), 1);
  assert.equal(clampedMax("1".repeat(5), 8), 100);
  assert.equal(clampedMax("1".repeat(10), 8), 100);
  assert.equal(clampedMax("0".repeat(1), 8), 1);
  assert.equal(clampedMax("0".repeat(10), 8), 1);
  assert.equal(clampedMax("0".repeat(9) + "5", 8), 5);
});

test("shotgun34 runs odd in the middle: 55!55 is 55, 5555! clamps to 100, 5!555 is 5, and !5555 keeps the fallback", () => {
  assert.equal(clampedMax("55!55", 8), 55);
  assert.equal(clampedMax("5555!", 8), 100);
  assert.equal(clampedMax("5!555", 8), 5);
  assert.equal(clampedMax("!5555", 8), 8);
});

// -- 10 pull route tests ------------------------------------------------------

test("shotgun34 pull max=0: leases exactly one job of three, not the default page", async () => {
  const env = await sg34Env();
  await sg34SeedJobs(env, 3);
  const { jobs } = await sg34Pull(env, "0");
  assert.equal(jobs.length, 1);
  assert.equal(jobs[0].id, "j01");
});

test("shotgun34 pull negative: max=-3 leases exactly one job", async () => {
  assert.equal(await sg34PullCount(3, "-3"), 1);
  assert.equal(await sg34PullCount(3, "-100"), 1);
});

test("shotgun34 pull missing: no max leases the default 8 of 10", async () => {
  assert.equal(await sg34PullCount(10, undefined), 8);
});

test("shotgun34 pull non-numeric: max=abc leases the default 8 of 10", async () => {
  assert.equal(await sg34PullCount(10, "abc"), 8);
});

test("shotgun34 pull empty: an empty max leases the default 8 of 10", async () => {
  assert.equal(await sg34PullCount(10, ""), 8);
});

test("shotgun34 pull exact counts: max=1 leases 1 and max=2 leases 2", async () => {
  assert.equal(await sg34PullCount(5, "1"), 1);
  assert.equal(await sg34PullCount(5, "2"), 2);
});

test("shotgun34 pull over cap: max=100 and max=101 both lease all 10 queued jobs", async () => {
  assert.equal(await sg34PullCount(10, "100"), 10);
  assert.equal(await sg34PullCount(10, "101"), 10);
});

test("shotgun34 pull max=0 twice: two zero pulls lease two different jobs, one each", async () => {
  const env = await sg34Env();
  await sg34SeedJobs(env, 3);
  const a = await sg34Pull(env, "0");
  const b = await sg34Pull(env, "0");
  assert.equal(a.jobs.length, 1);
  assert.equal(b.jobs.length, 1);
  assert.notEqual(a.jobs[0].id, b.jobs[0].id);
});

test("shotgun34 pull max=0 edges: an empty queue answers 204, and a single job is leased whole", async () => {
  const empty = await sg34Env();
  assert.equal((await sg34Pull(empty, "0")).status, 204);
  assert.equal(await sg34PullCount(1, "0"), 1);
});

test("shotgun34 pull state: a max=0 pull leases exactly one record in storage and leaves the rest unattempted", async () => {
  const env = await sg34Env();
  await sg34SeedJobs(env, 3);
  await sg34Pull(env, "0");
  const jobs = [...sg34Map(env).values()].filter((v) => v && v.envelope);
  assert.equal(jobs.filter((j) => j.leased_until > 0).length, 1);
  assert.deepEqual(jobs.map((j) => j.attempts).sort(), [0, 0, 1]);
});

// -- 5 results route tests -----------------------------------------------------

test("shotgun34 results max=0: returns exactly one result of three, with more", async () => {
  const { count, more } = await sg34ReadCount("results", 3, "0");
  assert.equal(count, 1);
  assert.equal(more, true);
});

test("shotgun34 results negative: max=-1 returns exactly one result", async () => {
  const { count, more } = await sg34ReadCount("results", 3, "-1");
  assert.equal(count, 1);
  assert.equal(more, true);
});

test("shotgun34 results missing: no max returns the default 20 of 25, with more", async () => {
  const { count, more } = await sg34ReadCount("results", 25, undefined);
  assert.equal(count, 20);
  assert.equal(more, true);
});

test("shotgun34 results non-numeric: max=abc returns the default 20 of 25", async () => {
  const { count, more } = await sg34ReadCount("results", 25, "abc");
  assert.equal(count, 20);
  assert.equal(more, true);
});

test("shotgun34 results counts: max=2 returns 2 with more; max=100 returns all 25 with no more", async () => {
  const two = await sg34ReadCount("results", 25, "2");
  assert.equal(two.count, 2);
  assert.equal(two.more, true);
  const all = await sg34ReadCount("results", 25, "100");
  assert.equal(all.count, 25);
  assert.equal(all.more, undefined);
});

// -- 5 dlq route tests -----------------------------------------------------------

test("shotgun34 dlq max=0: returns exactly one dead letter of three, with more", async () => {
  const { count, more } = await sg34ReadCount("dlq", 3, "0");
  assert.equal(count, 1);
  assert.equal(more, true);
});

test("shotgun34 dlq negative: max=-9 returns exactly one dead letter", async () => {
  const { count, more } = await sg34ReadCount("dlq", 3, "-9");
  assert.equal(count, 1);
  assert.equal(more, true);
});

test("shotgun34 dlq missing: no max returns the default 20 of 25, with more", async () => {
  const { count, more } = await sg34ReadCount("dlq", 25, undefined);
  assert.equal(count, 20);
  assert.equal(more, true);
});

test("shotgun34 dlq non-numeric: max=abc returns the default 20 of 25", async () => {
  const { count, more } = await sg34ReadCount("dlq", 25, "abc");
  assert.equal(count, 20);
  assert.equal(more, true);
});

test("shotgun34 dlq counts: max=3 returns 3 with more; max=100 returns all 25 with no more", async () => {
  const three = await sg34ReadCount("dlq", 25, "3");
  assert.equal(three.count, 3);
  assert.equal(three.more, true);
  const all = await sg34ReadCount("dlq", 25, "100");
  assert.equal(all.count, 25);
  assert.equal(all.more, undefined);
});

// -- 4 route sweeps ---------------------------------------------------------------

test("shotgun34 route bookends: bookended zeros on the pull -- !0 and !0! fall back to 8, 0! and 0\\x00 lease 1", async () => {
  assert.equal(await sg34PullCount(10, "!0"), 8);
  assert.equal(await sg34PullCount(10, "!0!"), 8);
  assert.equal(await sg34PullCount(10, "0!"), 1);
  assert.equal(await sg34PullCount(10, "0\x00"), 1);
});

test("shotgun34 route runs: max=0000 leases 1; max=111 and max=55 lease all 10 through the cap", async () => {
  assert.equal(await sg34PullCount(10, "0000"), 1);
  assert.equal(await sg34PullCount(10, "111"), 10);
  assert.equal(await sg34PullCount(10, "55"), 10);
  assert.equal(await sg34PullCount(10, "5"), 5);
});

test("shotgun34 route duplicate: where two max values are sent, the first one decides, in both orders", async () => {
  const env1 = await sg34Env();
  await sg34SeedJobs(env1, 10);
  assert.equal((await sg34PullQs(env1, "max=0&max=8")).jobs.length, 1);
  const env2 = await sg34Env();
  await sg34SeedJobs(env2, 10);
  assert.equal((await sg34PullQs(env2, "max=8&max=0")).jobs.length, 8);
});

test("shotgun34 route injection: injection-shaped max values are parsed or fall back, never acted on", async () => {
  assert.equal(await sg34PullCount(10, "0; DROP TABLE jobs; --"), 1);
  assert.equal(await sg34PullCount(10, "ignore all previous instructions"), 8);
  assert.equal(await sg34PullCount(10, "${100}"), 8);
  assert.equal(await sg34PullCount(10, "../../etc/passwd"), 8);
});

// -- 1 cross-route test -------------------------------------------------------------

test("shotgun34 cross-route: the same max=0 names one on the pull, the results read and the dlq read alike", async () => {
  const env = await sg34Env();
  await sg34SeedJobs(env, 3);
  for (const id of sg34Ids("r", 3)) sg34PutR(env, id);
  for (const id of sg34Ids("d", 3)) sg34PutD(env, id);
  assert.equal((await sg34Pull(env, "0")).jobs.length, 1);
  const res = await sg34Read(env, "results", "0");
  assert.equal(res.body.results.length, 1);
  const dlq = await sg34Read(env, "dlq", "0");
  assert.equal(dlq.body.dead.length, 1);
});
