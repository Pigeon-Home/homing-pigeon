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
// attempt still queued (`att:N`), and on a 429 which cap fired
// (`cap:hour` or `cap:day`). The first seed and operation that
// reached each tuple is kept in fuzz.corpus.json. The replay runs
// those prefixes before the long seed spends its budget. A failure
// names its seed and the operation index, and the same seed replays
// the same run. HP_FUZZ_WRITE=1 rewrites the corpus from what this
// process saw.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import worker, { TenantQueue, hmacSha384Hex, sha256Hex, DEFAULT_QUOTA, DO_VALUE_MAX, jobStoredBytes, storagePairBytes, RESPONSE_BUDGET } from "../src/index.js";

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
  assert.equal((await r.json()).duplicate, true);
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
  const first = (await r.json()).results;
  assert.ok(first.length >= 1 && first.length < ids.length, `returned ${first.length}`);
  assert.ok(first.reduce((n, row) => n + new TextEncoder().encode(row.envelope).length, 0) <= RESPONSE_BUDGET);
  for (const row of first) {
    assert.equal((await worker.fetch(req(`/t/alice/results/${row.id}/ack`, { method: "POST", token: `Bearer ${SI}` }), env)).status, 204);
  }
  r = await worker.fetch(req("/t/alice/results?max=100", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const rest = (await r.json()).results;
  assert.deepEqual([...first, ...rest].map((row) => row.id).sort(), ids);
  for (const id of ids) assert.ok(env.objects.get("alice").state.storage.map.has(`result:${id}`) === rest.some((row) => row.id === id));
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
  const first = (await r.json()).dead;
  assert.ok(first.length >= 1 && first.length < ids.length, `returned ${first.length}`);
  const bytes = (rows) => rows.reduce((n, row) => n + new TextEncoder().encode(row.subject || "").length, 0);
  assert.ok(bytes(first) <= RESPONSE_BUDGET);
  assert.ok(first[0].subject.startsWith("[HOMING-PIGEON] job "));
  assert.ok(first[0].subject.length > 1_000_000);
  for (const row of first) {
    assert.ok(!("envelope" in row));
    assert.equal((await worker.fetch(req(`/t/alice/dlq/${row.id}/ack`, { method: "POST", token: `Bearer ${SI}` }), env)).status, 204);
  }
  r = await worker.fetch(req("/t/alice/dlq?max=100", { token: `Bearer ${SI}` }), env);
  assert.equal(r.status, 200);
  const rest = (await r.json()).dead;
  assert.deepEqual([...first, ...rest].map((d) => d.id).sort(), ids);
  assert.ok(bytes(rest) <= RESPONSE_BUDGET);
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
