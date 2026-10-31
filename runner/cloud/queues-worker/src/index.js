// Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
// Homing Pigeon hosted queue: the Cloudflare Worker and one Durable
// Object per tenant (docs/extend/transports.md, "Queues").
//
// Roles and routes (every route is /t/<tenant>/...):
//   SI      POST /jobs            signed job envelope in; a dead id is 409
//                                 until the SI acks or requeues it
//   runner  GET  /jobs?max=N      lease up to N jobs      (Bearer runner token)
//   runner  POST /jobs/<id>/lease renew a lease it holds   (a long job)
//   runner  POST /jobs/<id>/ack   job finished. ?hand=N names the pull;
//                                 a later pull's job is left in place
//   runner  POST /results         result envelope in
//   SI      GET  /results?max=N   results out
//   SI      POST /results/<id>/ack
//   SI      GET  /dlq?max=N       the dead-letter list (ids, attempts, subjects)
//   SI      POST /dlq/<id>/ack     drop a dead job
//   SI      POST /dlq/<id>/requeue offer it again, attempts reset (hourly quota)
//
// Gates, in order: the tenant must exist; the bearer token must hash
// to the role's stored hash; a job body must carry a valid HMAC-SHA-384
// under the tenant's shared secret when REJECT_INVALID_HMAC is on
// (default on here, unlike the old boundary-only Worker); and the
// tenant's quota (jobs per hour, bytes per day) must have room.
// Result bytes use that same daily cap on their own counter, so a
// day full of jobs still accepts its answers. The quota is the
// spending cap Cloudflare does not provide: an exceeded tenant gets
// 429 and nothing is stored or billed past it.
//
// Tenant records come from the TENANTS KV namespace
// ({si_token_sha256, runner_token_sha256, hmac_secret, quota}) or,
// for a one-tenant deployment with no KV, from env vars
// TENANT, SI_TOKEN, RUNNER_TOKEN, HMAC_SECRET.

const LEASE_MS_DEFAULT = 300_000;

// Milliseconds, via parseInt: "300000ms" is 300000 and "five" is not
// a number. Zero and negative are the default too. A negative is
// truthy, and using it would expire the job as it was handed out.
function leaseMs(env) {
  const n = parseInt((env && env.LEASE_MS) || "", 10);
  if (!Number.isFinite(n) || n <= 0) return LEASE_MS_DEFAULT;
  return n;
}
const MAX_ATTEMPTS = 5;
// SQLite-backed Durable Object (wrangler new_sqlite_classes): the key
// and the value together cannot exceed 2 MB. The smaller reading of
// that limit. A body under it can still wrap, once stored, past it.
export const DO_VALUE_MAX = 2_000_000;
// One read must not hold more envelope bytes than this. A page of
// full-size records is already most of it. The caller gets the rest
// on the next read.
export const RESPONSE_BUDGET = 8 * 1024 * 1024;
const PAGE = 8;

// A missing or non-numeric max keeps the route's default. Zero and
// negative are one job, not that default: the caller named a count.
export function clampedMax(raw, fallback) {
  const n = parseInt(raw ?? "", 10);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(1, Math.min(100, n));
}

// A blank field is zero, which locks the tenant. A numeric string is
// that number. Anything else is not a number: the worker refuses the
// record, and the object falls back to the default so a bad value
// cannot turn the cap off. A missing quota is the default. A present
// quota that is not an object (a bare number, a string, a list) is
// refused too: the default is a wide cap, and that typo must not
// widen the tenant to it.
export function quotaNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const t = value.trim();
    if (t === "") return 0;
    const n = Number(t);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function quotaRejected(quota) {
  if (quota == null) return false;
  if (typeof quota !== "object" || Array.isArray(quota)) return true;
  for (const key of ["jobs_per_hour", "bytes_per_day"]) {
    if (quota[key] == null) continue;
    if (quotaNumber(quota[key]) == null) return true;
  }
  return false;
}

function takeQuota(value, fallback) {
  if (value == null) return fallback;
  const n = quotaNumber(value);
  return n == null ? fallback : n;
}
export const DEFAULT_QUOTA = { jobs_per_hour: 600, bytes_per_day: 256 * 1024 * 1024 };

const enc = new TextEncoder();

function utf8Length(text) {
  return enc.encode(text).length;
}

// Bytes the runtime will persist: the key plus the JSON value. A pull
// replaces leased_until 0 with a millisecond timestamp and adds a
// hand before the dead-letter copy adds dead_at. A requeue keeps
// requeued_at, so the next dead copy carries both. Budget that
// widest record, or a job that measured as fitting throws on the
// way back to the dead list. A hand only grows, one per pull and
// per requeue, so the budget uses the widest integer JSON keeps exact.
const FAR_MS = 9_999_999_999_999;
const HAND_MAX = Number.MAX_SAFE_INTEGER;
export function storagePairBytes(key, value) {
  return enc.encode(key).length + enc.encode(JSON.stringify(value)).length;
}

export function jobStoredBytes(jobId, text, now) {
  const stamp = Math.max(FAR_MS, Number(now) || 0);
  const size = utf8Length(text);
  const dead = {
    id: jobId, envelope: text, size,
    attempts: MAX_ATTEMPTS, leased_until: stamp, enqueued_at: stamp,
    hand: HAND_MAX, requeued_at: stamp, dead_at: stamp,
  };
  const again = {
    id: jobId, envelope: text, size,
    attempts: 0, leased_until: 0, enqueued_at: stamp,
    hand: HAND_MAX, requeued_at: stamp,
  };
  return Math.max(
    storagePairBytes(`dlq:${jobId}`, dead),
    storagePairBytes(`job:${jobId}`, again),
  );
}

export function resultStoredBytes(id, text, now) {
  return storagePairBytes(`result:${id}`, { id, envelope: text, at: now });
}

function constantTimeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}

function hex(buf) {
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(text) {
  return hex(await crypto.subtle.digest("SHA-256", enc.encode(text)));
}

export async function signatureVerdict(secret, body) {
  // The gate's own answer, and nothing past it: no JSON parse, no
  // nesting limit, no surrogate check. "accept", "no-sig", or
  // "mismatch". A secret that is not text cannot sign.
  if (typeof secret !== "string") return "mismatch";
  const ex = extractSigAndPayload(typeof body === "string" ? body : "");
  if (!ex) return "no-sig";
  let want;
  try {
    want = await hmacSha384Hex(secret, ex.payload);
  } catch {
    return "mismatch";
  }
  return constantTimeEqual(want, ex.sig) ? "accept" : "mismatch";
}

export async function bodyVerdict(secret, text) {
  // What the gate HMACs. An envelope is split first, the same way
  // fetch does; a bare body is the body.
  const parsed = parseEnvelope(typeof text === "string" ? text : "");
  return signatureVerdict(secret, parsed ? parsed.body : text);
}

export async function hmacSha384Hex(secret, payload) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-384" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", key, enc.encode(payload)));
}

// The envelope is a subject line, a blank line, the signed body. The
// signed body ends with ,"sig":"<hex>"} ; the payload is everything
// before the sig member, closed. An hp_enc envelope carries its own
// sig the same way (the envelope is signed as transmitted).
export function parseEnvelope(text) {
  const norm = (text || "").replace(/\r\n/g, "\n");
  const i = norm.indexOf("\n\n");
  if (i < 0) return null;
  return { subject: norm.slice(0, i).trim(), body: norm.slice(i + 2) };
}

// The core's extractor (runner/wire/verify.py, _extract_signed), line
// for line, so the gate queues exactly the jobs the runner will trust.
// The body is normalized the core's way (CRLF and a lone CR to LF, then
// Python's rstrip); the sig member is the last `,"sig":"` followed by
// 96 hex digits and `"}`; the object it closes opens at the newest `{`
// whose text up to the marker is a whole root object that parses as a
// JSON object, the stripped-controls form included, else the newest
// whole-object `{`. A wrong candidate fails the HMAC either way.
const PY_SPACE = /[\t\n\x0b\x0c\r\x1c-\x1f \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/;
const SIG_MARKER = ',"sig":"';

export function normalizeBody(text) {
  return (typeof text === "string" ? text : "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(PY_SPACE, "");
}

export function stripControls(text) {
  return text.replace(/[\x00-\x08\x0a-\x1f]/g, "");
}

function inRootObjectAt(norm, start, sigAt) {
  let depth = 0, inStr = false, escape = false;
  for (let k = start; k < sigAt; k++) {
    const c = norm[k];
    if (inStr) {
      if (escape) escape = false;
      else if (c === "\\") escape = true;
      else if (c === '"') inStr = false;
      continue;
    }
    if (c === '"') inStr = true;
    else if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) return false;
    }
  }
  return depth === 1 && !inStr;
}

// Python's json.loads takes NaN, Infinity and -Infinity; JSON.parse
// does not. The opener search is the core's, so a candidate is read
// with those tokens (outside strings) taken as numbers.
function pyLoads(text) {
  try {
    return JSON.parse(text);
  } catch (e) {
    if (!/NaN|Infinity/.test(text)) throw e;
  }
  let out = "", inStr = false, escape = false;
  for (let k = 0; k < text.length; k++) {
    const c = text[k];
    if (inStr) {
      if (escape) escape = false;
      else if (c === "\\") escape = true;
      else if (c === '"') inStr = false;
      out += c;
      continue;
    }
    if (c === '"') { inStr = true; out += c; continue; }
    if (text.startsWith("-Infinity", k)) { out += "0"; k += 8; continue; }
    if (text.startsWith("Infinity", k)) { out += "0"; k += 7; continue; }
    if (text.startsWith("NaN", k)) { out += "0"; k += 2; continue; }
    out += c;
  }
  return JSON.parse(out);
}

function objectStart(norm, sigAt) {
  let firstWalk = -1;
  for (let start = sigAt - 1; start >= 0; start--) {
    if (norm[start] !== "{") continue;
    if (!inRootObjectAt(norm, start, sigAt)) continue;
    if (firstWalk < 0) firstWalk = start;
    const text = norm.slice(start, sigAt) + "}";
    for (const form of [text, stripControls(text)]) {
      let candidate;
      try {
        candidate = pyLoads(form);
      } catch {
        continue;
      }
      if (candidate !== null && typeof candidate === "object" && !Array.isArray(candidate)) return start;
      break;
    }
  }
  return firstWalk;
}

export function extractSigAndPayload(body) {
  const norm = normalizeBody(body);
  const i = norm.lastIndexOf(SIG_MARKER);
  if (i < 0) return null;
  const tail = norm.slice(i + SIG_MARKER.length);
  if (tail.length < 98 || tail.slice(96, 98) !== '"}' || !/^[0-9a-fA-F]{96}$/.test(tail.slice(0, 96))) return null;
  const start = objectStart(norm, i);
  if (start < 0) return null;
  return { payload: norm.slice(start, i) + "}", sig: tail.slice(0, 96).toLowerCase() };
}

export function jobIdOf(subject) {
  const m = (subject || "").match(/\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)/i);
  return m ? m[1] : null;
}

export function resultIdOf(subject) {
  const m = (subject || "").match(/\[HOMING-PIGEON\](?:\s+\S+)*\s+(?:result|qresult)\s+(\S+)/i);
  return m ? m[1] : null;
}

// The subject grammar (Q121) extracts any non-space token, so it stays
// in step with the runner. The route can only address an id the
// protocol allows: 1 to 128 of [A-Za-z0-9._-], and not "." or "..".
// A slash, or a longer token, is stored under a key the ack path
// cannot name.
export function safeJobId(id) {
  return typeof id === "string"
    && /^[A-Za-z0-9._-]{1,128}$/.test(id)
    && id !== "." && id !== "..";
}

function bodyJobId(body) {
  // The id the runner will trust is the one inside the signed payload,
  // not a second parse of the whole body. Python's parser accepts
  // NaN and Infinity; JSON.parse rejects the body and used to 400 a
  // job the runner would run.
  const ex = extractSigAndPayload(typeof body === "string" ? body : "");
  let obj;
  try { obj = pyLoads(ex ? ex.payload : (body || "")); } catch { return undefined; }
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return undefined;
  return typeof obj.job_id === "string" ? obj.job_id : undefined;
}

async function loadTenant(env, slug) {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(slug)) return null;
  if (env.TENANTS && typeof env.TENANTS.get === "function") {
    const raw = await env.TENANTS.get(slug);
    if (!raw) return null;
    try {
      const rec = JSON.parse(raw);
      return rec && typeof rec === "object" ? { slug, ...rec } : null;
    } catch {
      return null;
    }
  }
  if (env.TENANT && env.TENANT === slug) {
    return {
      slug,
      si_token_sha256: env.SI_TOKEN ? await sha256Hex(env.SI_TOKEN) : null,
      runner_token_sha256: env.RUNNER_TOKEN ? await sha256Hex(env.RUNNER_TOKEN) : null,
      hmac_secret: env.HMAC_SECRET || null,
      quota: DEFAULT_QUOTA,
    };
  }
  return null;
}

async function bearerMatches(request, wantHash) {
  const auth = request.headers.get("authorization") || "";
  const m = auth.match(/^Bearer\s+(\S+)$/i);
  if (!m || !wantHash) return false;
  return constantTimeEqual(await sha256Hex(m[1]), wantHash);
}

function json(status, body, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...extra },
  });
}

// Present and not an integer is a bad receipt. Absent is the old
// call, which does not name a pull.
function namedInt(raw) {
  if (raw == null || raw === "") return undefined;
  const n = Number(raw);
  if (!Number.isInteger(n)) return null;
  return n;
}

// An attempt or a hand that is not this record's does not hold it.
// A hand only goes up, including across a requeue, so the number the
// pull returned cannot name a later life. Omitting both keeps the
// old call.
function namesThisPull(job, url) {
  const attempt = namedInt(url.searchParams.get("attempt"));
  const hand = namedInt(url.searchParams.get("hand"));
  if (attempt === null || hand === null) return false;
  if (attempt !== undefined && attempt !== job.attempts) return false;
  if (hand !== undefined && hand !== job.hand) return false;
  return true;
}

function receiptQuery(url) {
  let extra = "";
  for (const key of ["attempt", "hand"]) {
    const v = url.searchParams.get(key);
    if (v != null && v !== "") extra += `&${key}=${encodeURIComponent(v)}`;
  }
  return extra;
}

function rejectOn(env) {
  const v = (env.REJECT_INVALID_HMAC ?? "true").toString().toLowerCase();
  return !(v === "false" || v === "0" || v === "off");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") return json(200, { ok: true });
    const m = url.pathname.match(/^\/t\/([^/]+)\/(jobs|results|dlq)(?:\/([^/]+)\/(ack|lease|requeue))?\/?$/);
    if (!m) return json(404, { error: "no such route" });
    const [, slug, kind, itemId, verb] = m;
    const ackId = verb === "ack" ? itemId : undefined;
    const leaseId = verb === "lease" ? itemId : undefined;
    if (leaseId && kind !== "jobs") return json(404, { error: "no such route" });
    if (verb === "requeue" && kind !== "dlq") return json(404, { error: "no such route" });
    const tenant = await loadTenant(env, slug);
    if (!tenant) return json(404, { error: "unknown tenant" });
    const stub = env.TENANT_QUEUE.get(env.TENANT_QUEUE.idFromName(slug));
    const forward = (path, init) => stub.fetch(new Request("https://do" + path, init));

    if (kind === "dlq") {
      // The SI's view of the dead-letter list: jobs that ran out of
      // attempts. Read it, drop one, or put one back with a fresh
      // attempt count (counted against the hourly job quota).
      if (!(await bearerMatches(request, tenant.si_token_sha256))) return json(401, { error: "si token" });
      if (request.method === "GET" && !itemId) {
        const max = clampedMax(url.searchParams.get("max"), 20);
        const after = url.searchParams.get("after");
        const tail = after && safeJobId(after) ? `&after=${encodeURIComponent(after)}` : "";
        return forward(`/dlq?max=${max}${tail}`, { method: "POST" });
      }
      if (request.method === "POST" && verb === "ack") {
        return forward(`/dlq-ack?id=${encodeURIComponent(itemId)}`, { method: "POST" });
      }
      if (request.method === "POST" && verb === "requeue") {
        if (quotaRejected(tenant.quota)) return json(400, { error: "quota is not a number" });
        return forward(`/dlq-requeue?id=${encodeURIComponent(itemId)}`, {
          method: "POST", headers: { "x-hp-quota": JSON.stringify(tenant.quota || DEFAULT_QUOTA) },
        });
      }
      return json(405, { error: "method not allowed" });
    }
    if (kind === "jobs" && request.method === "POST" && leaseId) {
      // The runner still holds a job it is running: renew its lease
      // so a long job is not offered again or dead-lettered.
      if (!(await bearerMatches(request, tenant.runner_token_sha256))) return json(401, { error: "runner token" });
      return forward(`/renew?id=${encodeURIComponent(leaseId)}${receiptQuery(url)}`, { method: "POST" });
    }
    if (kind === "jobs" && request.method === "POST" && !ackId) {
      // SI submits a job.
      if (!(await bearerMatches(request, tenant.si_token_sha256))) return json(401, { error: "si token" });
      if (quotaRejected(tenant.quota)) return json(400, { error: "quota is not a number" });
      const text = await request.text();
      if (!text) return json(400, { error: "empty body" });
      if (utf8Length(text) > DO_VALUE_MAX) return json(413, { error: "envelope over the storage limit" });
      const parsed = parseEnvelope(text);
      if (!parsed) return json(400, { error: "malformed envelope: subject, blank line, body" });
      const jobId = jobIdOf(parsed.subject);
      if (!jobId) return json(400, { error: "subject does not name a job" });
      if (!safeJobId(jobId)) return json(400, { error: "job id is not a safe id" });
      if (rejectOn(env)) {
        if (!tenant.hmac_secret) return json(500, { error: "tenant has no hmac_secret" });
        const verdict = await signatureVerdict(tenant.hmac_secret, parsed.body);
        if (verdict === "no-sig") return json(400, { error: "body carries no sig member" });
        if (verdict !== "accept") return json(403, { error: "invalid signature" });
      }
      if (bodyJobId(parsed.body) !== jobId) return json(400, { error: "job_id mismatch between subject and body" });
      return forward("/enqueue", {
        method: "POST",
        headers: { "x-hp-job-id": jobId, "x-hp-quota": JSON.stringify(tenant.quota || DEFAULT_QUOTA) },
        body: text,
      });
    }
    if (kind === "jobs" && request.method === "GET") {
      if (!(await bearerMatches(request, tenant.runner_token_sha256))) return json(401, { error: "runner token" });
      const max = clampedMax(url.searchParams.get("max"), 8);
      return forward(`/pull?max=${max}`, { method: "POST" });
    }
    if (kind === "jobs" && request.method === "POST" && ackId) {
      if (!(await bearerMatches(request, tenant.runner_token_sha256))) return json(401, { error: "runner token" });
      return forward(`/ack?id=${encodeURIComponent(ackId)}${receiptQuery(url)}`, { method: "POST" });
    }
    if (kind === "results" && request.method === "POST" && !ackId) {
      if (!(await bearerMatches(request, tenant.runner_token_sha256))) return json(401, { error: "runner token" });
      if (quotaRejected(tenant.quota)) return json(400, { error: "quota is not a number" });
      const text = await request.text();
      if (utf8Length(text) > DO_VALUE_MAX) return json(413, { error: "envelope over the storage limit" });
      const parsed = parseEnvelope(text);
      if (!parsed) return json(400, { error: "malformed envelope" });
      const rid = resultIdOf(parsed.subject);
      if (!rid) return json(400, { error: "subject does not name a result" });
      if (!safeJobId(rid)) return json(400, { error: "job id is not a safe id" });
      return forward("/result", {
        method: "POST",
        headers: {
          "x-hp-result-id": rid,
          "x-hp-quota": JSON.stringify(tenant.quota || DEFAULT_QUOTA),
        },
        body: text,
      });
    }
    if (kind === "results" && request.method === "GET") {
      if (!(await bearerMatches(request, tenant.si_token_sha256))) return json(401, { error: "si token" });
      const max = clampedMax(url.searchParams.get("max"), 20);
      const after = url.searchParams.get("after");
      const tail = after && safeJobId(after) ? `&after=${encodeURIComponent(after)}` : "";
      return forward(`/results?max=${max}${tail}`, { method: "POST" });
    }
    if (kind === "results" && request.method === "POST" && ackId) {
      if (!(await bearerMatches(request, tenant.si_token_sha256))) return json(401, { error: "si token" });
      return forward(`/results-ack?id=${encodeURIComponent(ackId)}`, { method: "POST" });
    }
    return json(405, { error: "method not allowed" });
  },
};

// One Durable Object per tenant: the job queue, the result box and
// the quota counters, all in one transactional storage.
export class TenantQueue {
  constructor(state, env) {
    this.state = state;
    this.env = env || {};
    this.now = () => Date.now();
  }

  async fetch(request) {
    const url = new URL(request.url);
    const s = this.state.storage;
    const now = this.now();
    if (url.pathname === "/enqueue") {
      const jobId = request.headers.get("x-hp-job-id");
      const quota = JSON.parse(request.headers.get("x-hp-quota") || "{}");
      const text = await request.text();
      const existing = await s.get(`job:${jobId}`);
      if (existing) return json(200, { id: jobId, duplicate: true });
      const dead = await s.get(`dlq:${jobId}`);
      if (dead) {
        return json(409, {
          error: "a job with this id is dead",
          id: jobId,
          attempts: dead.attempts,
          dead_at: dead.dead_at,
        });
      }
      if (jobStoredBytes(jobId, text, now) > DO_VALUE_MAX) {
        return json(413, { error: "envelope over the storage limit" });
      }
      const hourKey = `quota:hour:${Math.floor(now / 3_600_000)}`;
      const dayKey = `quota:day:${Math.floor(now / 86_400_000)}`;
      const jobs = (await s.get(hourKey)) || 0;
      const bytes = (await s.get(dayKey)) || 0;
      const jph = takeQuota(quota.jobs_per_hour, DEFAULT_QUOTA.jobs_per_hour);
      const bpd = takeQuota(quota.bytes_per_day, DEFAULT_QUOTA.bytes_per_day);
      const weight = utf8Length(text);
      if (jobs + 1 > jph || bytes + weight > bpd) {
        await s.put("quota:exceeded", ((await s.get("quota:exceeded")) || 0) + 1);
        const retry = jobs + 1 > jph
          ? 3600 - Math.floor((now % 3_600_000) / 1000)
          : 86400 - Math.floor((now % 86_400_000) / 1000);
        return json(429, { error: "tenant quota exceeded", jobs_this_hour: jobs, bytes_today: bytes }, { "retry-after": String(retry) });
      }
      await s.put(`job:${jobId}`, { id: jobId, envelope: text, size: weight, enqueued_at: now, leased_until: 0, attempts: 0 });
      await s.put(hourKey, jobs + 1);
      await s.put(dayKey, bytes + weight);
      return json(202, { id: jobId });
    }
    if (url.pathname === "/pull") {
      // Page the prefix. One unbounded list() loads every envelope into
      // the object, and the platform will kill that once the queue is
      // larger than memory. A short page is not the end: keep going
      // until a page is empty or the caller has enough.
      const max = clampedMax(url.searchParams.get("max"), 8);
      const lease = leaseMs(this.env);
      const out = [];
      let used = 0;
      let full = false;
      let startAfter;
      for (;;) {
        const page = await s.list({ prefix: "job:", limit: PAGE, startAfter });
        if (page.size === 0) break;
        const prev = startAfter;
        for (const [key, job] of page) {
          startAfter = key;
          if (out.length >= max) break;
          if (job.leased_until > now) continue;
          if (job.attempts >= MAX_ATTEMPTS) {
            await s.put(`dlq:${job.id}`, { ...job, dead_at: now });
            await s.delete(key);
            continue;
          }
          const weight = utf8Length(job.envelope || "");
          if (out.length > 0 && used + weight > RESPONSE_BUDGET) { full = true; break; }
          job.leased_until = now + lease;
          job.attempts += 1;
          job.hand = (job.hand || 0) + 1;
          await s.put(key, job);
          out.push({ id: job.id, envelope: job.envelope, attempt: job.attempts, hand: job.hand });
          used += weight;
        }
        if (out.length >= max || full || startAfter === prev) break;
      }
      return out.length ? json(200, { jobs: out }) : new Response(null, { status: 204 });
    }
    if (url.pathname === "/dlq") {
      // The response carries no envelope, but the subject is the
      // whole text before the blank line, and that can be the
      // envelope. Stop at the same budget as a jobs read. `more`
      // means this page stopped with rows still waiting; `after` is
      // the last id returned, so the next read continues without
      // dropping anything. An after that is not a safe id is ignored.
      const max = clampedMax(url.searchParams.get("max"), 20);
      const after = url.searchParams.get("after");
      const out = [];
      let used = 0;
      let more = false;
      let startAfter = after && safeJobId(after) ? `dlq:${after}` : undefined;
      for (;;) {
        const page = await s.list({ prefix: "dlq:", limit: PAGE, startAfter });
        if (page.size === 0) break;
        const prev = startAfter;
        for (const [key, d] of page) {
          startAfter = key;
          if (out.length >= max) { more = true; break; }
          const subject = (parseEnvelope(d.envelope) || {}).subject || null;
          const weight = utf8Length(subject || "");
          if (out.length > 0 && used + weight > RESPONSE_BUDGET) { more = true; break; }
          out.push({ id: d.id, attempts: d.attempts, size: d.size,
                     enqueued_at: d.enqueued_at, dead_at: d.dead_at,
                     subject });
          used += weight;
        }
        if (more || startAfter === prev) break;
        if (out.length >= max) break;
      }
      // A full page that ended exactly on max has not seen the next
      // key. Look once, so the caller is not told the list ended.
      if (out.length >= max && !more) {
        const peek = await s.list({ prefix: "dlq:", limit: 1, startAfter });
        if (peek.size > 0) more = true;
      }
      if (!out.length) return new Response(null, { status: 204 });
      return json(200, more ? { dead: out, more: true } : { dead: out });
    }
    if (url.pathname === "/dlq-ack") {
      const id = url.searchParams.get("id");
      const had = await s.get(`dlq:${id}`);
      await s.delete(`dlq:${id}`);
      return new Response(null, { status: had ? 204 : 404 });
    }
    if (url.pathname === "/dlq-requeue") {
      const id = url.searchParams.get("id");
      const dead = await s.get(`dlq:${id}`);
      if (!dead) return new Response(null, { status: 404 });
      if (await s.get(`job:${id}`)) return json(409, { error: "a job with this id is queued" });
      const quota = JSON.parse(request.headers.get("x-hp-quota") || "{}");
      const hourKey = `quota:hour:${Math.floor(now / 3_600_000)}`;
      const jobs = (await s.get(hourKey)) || 0;
      const jph = takeQuota(quota.jobs_per_hour, DEFAULT_QUOTA.jobs_per_hour);
      if (jobs + 1 > jph) {
        return json(429, { error: "tenant quota exceeded", jobs_this_hour: jobs },
                    { "retry-after": String(3600 - Math.floor((now % 3_600_000) / 1000)) });
      }
      const { dead_at, ...job } = dead;
      // The hand the last pull was given must not still name this
      // record: nobody holds the requeued job yet.
      await s.put(`job:${id}`, {
        ...job, leased_until: 0, attempts: 0, requeued_at: now,
        hand: (job.hand || 0) + 1,
      });
      await s.delete(`dlq:${id}`);
      await s.put(hourKey, jobs + 1);
      return json(202, { id });
    }
    if (url.pathname === "/renew") {
      const id = url.searchParams.get("id");
      const job = await s.get(`job:${id}`);
      if (!job || !(job.leased_until > now)) return new Response(null, { status: 404 });
      // The attempt and the hand the pull handed out. A later pull
      // has a higher hand, and a requeue bumps it too, so the first
      // runner's renew must not extend that lease.
      if (!namesThisPull(job, url)) return new Response(null, { status: 404 });
      const lease = leaseMs(this.env);
      job.leased_until = now + lease;
      await s.put(`job:${id}`, job);
      return new Response(null, { status: 204 });
    }
    if (url.pathname === "/ack") {
      const id = url.searchParams.get("id");
      const job = await s.get(`job:${id}`);
      // A named hand or attempt that is not this pull's leaves the
      // job. Two runners share a token; the one that lost the lease
      // must not delete the job the later pull is running. Omitting
      // both is the old call and deletes whatever is queued.
      if (!job || !namesThisPull(job, url)) return new Response(null, { status: 404 });
      await s.delete(`job:${id}`);
      return new Response(null, { status: 204 });
    }
    if (url.pathname === "/result") {
      const rid = request.headers.get("x-hp-result-id");
      const text = await request.text();
      // The first result for an id stays, as a repeated job submit does.
      // A later post, including one the SI has not acked yet, must not
      // replace the envelope the SI was shown.
      const existing = await s.get(`result:${rid}`);
      if (existing) return json(200, { id: rid, duplicate: true });
      const record = { id: rid, envelope: text, at: now };
      if (resultStoredBytes(rid, text, now) > DO_VALUE_MAX) {
        return json(413, { error: "envelope over the storage limit" });
      }
      // Results are not jobs, so they do not spend the hourly job
      // cap or the job byte counter. They have the same daily byte
      // cap on their own counter: a day full of jobs still accepts
      // its answers, and a runner token cannot fill the object past
      // that cap. A copy of a result already stored is not billed.
      const quota = JSON.parse(request.headers.get("x-hp-quota") || "{}");
      const dayKey = `quota:resday:${Math.floor(now / 86_400_000)}`;
      const bytes = (await s.get(dayKey)) || 0;
      const bpd = takeQuota(quota.bytes_per_day, DEFAULT_QUOTA.bytes_per_day);
      const weight = utf8Length(text);
      if (bytes + weight > bpd) {
        await s.put("quota:exceeded", ((await s.get("quota:exceeded")) || 0) + 1);
        const retry = 86400 - Math.floor((now % 86_400_000) / 1000);
        return json(429, { error: "tenant quota exceeded", bytes_today: bytes }, { "retry-after": String(retry) });
      }
      await s.put(`result:${rid}`, record);
      await s.put(dayKey, bytes + weight);
      return json(202, { id: rid });
    }
    if (url.pathname === "/results") {
      // One page stops at max or at 8 MB of envelopes. `more` means
      // rows are still waiting. `after` is the last id returned, so
      // the next read continues without acking. A result that does
      // not verify stays, and it must not hide the ones after it.
      // An after that is not a safe id is ignored.
      const max = clampedMax(url.searchParams.get("max"), 20);
      const after = url.searchParams.get("after");
      const out = [];
      let used = 0;
      let more = false;
      let startAfter = after && safeJobId(after) ? `result:${after}` : undefined;
      for (;;) {
        const page = await s.list({ prefix: "result:", limit: PAGE, startAfter });
        if (page.size === 0) break;
        const prev = startAfter;
        for (const [key, row] of page) {
          startAfter = key;
          if (out.length >= max) { more = true; break; }
          const weight = utf8Length(row.envelope || "");
          if (out.length > 0 && used + weight > RESPONSE_BUDGET) { more = true; break; }
          out.push({ id: row.id, envelope: row.envelope, at: row.at });
          used += weight;
        }
        if (more || startAfter === prev) break;
        if (out.length >= max) break;
      }
      if (out.length >= max && !more) {
        const peek = await s.list({ prefix: "result:", limit: 1, startAfter });
        if (peek.size > 0) more = true;
      }
      if (!out.length) return new Response(null, { status: 204 });
      return json(200, more ? { results: out, more: true } : { results: out });
    }
    if (url.pathname === "/results-ack") {
      const id = url.searchParams.get("id");
      const had = await s.get(`result:${id}`);
      await s.delete(`result:${id}`);
      return new Response(null, { status: had ? 204 : 404 });
    }
    return json(404, { error: "no such object route" });
  }
}
