// Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
// Homing Pigeon hosted queue: the Cloudflare Worker and one Durable
// Object per tenant (docs/extend/transports.md, "Queues").
//
// Roles and routes (every route is /t/<tenant>/...):
//   SI      POST /jobs            signed job envelope in  (Bearer SI token)
//   runner  GET  /jobs?max=N      lease up to N jobs      (Bearer runner token)
//   runner  POST /jobs/<id>/lease renew a lease it holds   (a long job)
//   runner  POST /jobs/<id>/ack   job finished
//   runner  POST /results         result envelope in
//   SI      GET  /results?max=N   results out
//   SI      POST /results/<id>/ack
//
// Gates, in order: the tenant must exist; the bearer token must hash
// to the role's stored hash; a job body must carry a valid HMAC-SHA-384
// under the tenant's shared secret when REJECT_INVALID_HMAC is on
// (default on here, unlike the old boundary-only Worker); and the
// tenant's quota (jobs per hour, bytes per day) must have room. The
// quota is the spending cap Cloudflare does not provide: an exceeded
// tenant gets 429 and nothing is stored or billed past it.
//
// Tenant records come from the TENANTS KV namespace
// ({si_token_sha256, runner_token_sha256, hmac_secret, quota}) or,
// for a one-tenant deployment with no KV, from env vars
// TENANT, SI_TOKEN, RUNNER_TOKEN, HMAC_SECRET.

const LEASE_MS_DEFAULT = 300_000;
const MAX_ATTEMPTS = 5;
const ENVELOPE_MAX = 4 * 1024 * 1024;
export const DEFAULT_QUOTA = { jobs_per_hour: 600, bytes_per_day: 256 * 1024 * 1024 };

const enc = new TextEncoder();

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

export function extractSigAndPayload(body) {
  const trimmed = body.replace(/\s+$/, "");
  const m = trimmed.match(/,\s*"sig"\s*:\s*"([0-9a-fA-F]+)"\s*\}$/);
  if (!m) return null;
  return { payload: trimmed.slice(0, m.index) + "}", sig: m[1].toLowerCase() };
}

export function jobIdOf(subject) {
  const m = (subject || "").match(/\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)/i);
  return m ? m[1] : null;
}

export function resultIdOf(subject) {
  const m = (subject || "").match(/\[HOMING-PIGEON\](?:\s+\S+)*\s+(?:result|qresult)\s+(\S+)/i);
  return m ? m[1] : null;
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

function rejectOn(env) {
  const v = (env.REJECT_INVALID_HMAC ?? "true").toString().toLowerCase();
  return !(v === "false" || v === "0" || v === "off");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") return json(200, { ok: true });
    const m = url.pathname.match(/^\/t\/([^/]+)\/(jobs|results)(?:\/([^/]+)\/(ack|lease))?\/?$/);
    if (!m) return json(404, { error: "no such route" });
    const [, slug, kind, itemId, verb] = m;
    const ackId = verb === "ack" ? itemId : undefined;
    const leaseId = verb === "lease" ? itemId : undefined;
    if (leaseId && kind !== "jobs") return json(404, { error: "no such route" });
    const tenant = await loadTenant(env, slug);
    if (!tenant) return json(404, { error: "unknown tenant" });
    const stub = env.TENANT_QUEUE.get(env.TENANT_QUEUE.idFromName(slug));
    const forward = (path, init) => stub.fetch(new Request("https://do" + path, init));

    if (kind === "jobs" && request.method === "POST" && leaseId) {
      // The runner still holds a job it is running: renew its lease
      // so a long job is not offered again or dead-lettered.
      if (!(await bearerMatches(request, tenant.runner_token_sha256))) return json(401, { error: "runner token" });
      return forward(`/renew?id=${encodeURIComponent(leaseId)}`, { method: "POST" });
    }
    if (kind === "jobs" && request.method === "POST" && !ackId) {
      // SI submits a job.
      if (!(await bearerMatches(request, tenant.si_token_sha256))) return json(401, { error: "si token" });
      const text = await request.text();
      if (!text) return json(400, { error: "empty body" });
      if (text.length > ENVELOPE_MAX) return json(413, { error: "envelope over 4 MiB" });
      const parsed = parseEnvelope(text);
      if (!parsed) return json(400, { error: "malformed envelope: subject, blank line, body" });
      const jobId = jobIdOf(parsed.subject);
      if (!jobId) return json(400, { error: "subject does not name a job" });
      if (rejectOn(env)) {
        if (!tenant.hmac_secret) return json(500, { error: "tenant has no hmac_secret" });
        const verdict = await signatureVerdict(tenant.hmac_secret, parsed.body);
        if (verdict === "no-sig") return json(400, { error: "body carries no sig member" });
        if (verdict !== "accept") return json(403, { error: "invalid signature" });
      }
      return forward("/enqueue", {
        method: "POST",
        headers: { "x-hp-job-id": jobId, "x-hp-quota": JSON.stringify(tenant.quota || DEFAULT_QUOTA) },
        body: text,
      });
    }
    if (kind === "jobs" && request.method === "GET") {
      if (!(await bearerMatches(request, tenant.runner_token_sha256))) return json(401, { error: "runner token" });
      const max = Math.max(1, Math.min(100, parseInt(url.searchParams.get("max") || "8", 10) || 8));
      return forward(`/pull?max=${max}`, { method: "POST" });
    }
    if (kind === "jobs" && request.method === "POST" && ackId) {
      if (!(await bearerMatches(request, tenant.runner_token_sha256))) return json(401, { error: "runner token" });
      return forward(`/ack?id=${encodeURIComponent(ackId)}`, { method: "POST" });
    }
    if (kind === "results" && request.method === "POST" && !ackId) {
      if (!(await bearerMatches(request, tenant.runner_token_sha256))) return json(401, { error: "runner token" });
      const text = await request.text();
      const parsed = parseEnvelope(text);
      if (!parsed) return json(400, { error: "malformed envelope" });
      const rid = resultIdOf(parsed.subject);
      if (!rid) return json(400, { error: "subject does not name a result" });
      return forward("/result", { method: "POST", headers: { "x-hp-result-id": rid }, body: text });
    }
    if (kind === "results" && request.method === "GET") {
      if (!(await bearerMatches(request, tenant.si_token_sha256))) return json(401, { error: "si token" });
      const max = Math.max(1, Math.min(100, parseInt(url.searchParams.get("max") || "20", 10) || 20));
      return forward(`/results?max=${max}`, { method: "POST" });
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
      const hourKey = `quota:hour:${Math.floor(now / 3_600_000)}`;
      const dayKey = `quota:day:${Math.floor(now / 86_400_000)}`;
      const jobs = (await s.get(hourKey)) || 0;
      const bytes = (await s.get(dayKey)) || 0;
      const jph = quota.jobs_per_hour ?? DEFAULT_QUOTA.jobs_per_hour;
      const bpd = quota.bytes_per_day ?? DEFAULT_QUOTA.bytes_per_day;
      if (jobs + 1 > jph || bytes + text.length > bpd) {
        await s.put("quota:exceeded", ((await s.get("quota:exceeded")) || 0) + 1);
        const retry = jobs + 1 > jph
          ? 3600 - Math.floor((now % 3_600_000) / 1000)
          : 86400 - Math.floor((now % 86_400_000) / 1000);
        return json(429, { error: "tenant quota exceeded", jobs_this_hour: jobs, bytes_today: bytes }, { "retry-after": String(retry) });
      }
      await s.put(`job:${jobId}`, { id: jobId, envelope: text, size: text.length, enqueued_at: now, leased_until: 0, attempts: 0 });
      await s.put(hourKey, jobs + 1);
      await s.put(dayKey, bytes + text.length);
      return json(202, { id: jobId });
    }
    if (url.pathname === "/pull") {
      const max = parseInt(url.searchParams.get("max") || "8", 10);
      const lease = parseInt(this.env.LEASE_MS || "", 10) || LEASE_MS_DEFAULT;
      const all = await s.list({ prefix: "job:" });
      const out = [];
      for (const [key, job] of all) {
        if (out.length >= max) break;
        if (job.leased_until > now) continue;
        if (job.attempts >= MAX_ATTEMPTS) {
          await s.put(`dlq:${job.id}`, { ...job, dead_at: now });
          await s.delete(key);
          continue;
        }
        job.leased_until = now + lease;
        job.attempts += 1;
        await s.put(key, job);
        out.push({ id: job.id, envelope: job.envelope, attempt: job.attempts });
      }
      return out.length ? json(200, { jobs: out }) : new Response(null, { status: 204 });
    }
    if (url.pathname === "/renew") {
      const id = url.searchParams.get("id");
      const job = await s.get(`job:${id}`);
      if (!job || !(job.leased_until > now)) return new Response(null, { status: 404 });
      const lease = parseInt(this.env.LEASE_MS || "", 10) || LEASE_MS_DEFAULT;
      job.leased_until = now + lease;
      await s.put(`job:${id}`, job);
      return new Response(null, { status: 204 });
    }
    if (url.pathname === "/ack") {
      const id = url.searchParams.get("id");
      const had = await s.get(`job:${id}`);
      await s.delete(`job:${id}`);
      return new Response(null, { status: had ? 204 : 404 });
    }
    if (url.pathname === "/result") {
      const rid = request.headers.get("x-hp-result-id");
      const text = await request.text();
      await s.put(`result:${rid}`, { id: rid, envelope: text, at: now });
      return json(202, { id: rid });
    }
    if (url.pathname === "/results") {
      const max = parseInt(url.searchParams.get("max") || "20", 10);
      const all = await s.list({ prefix: "result:", limit: max });
      const out = [];
      for (const [, r] of all) out.push({ id: r.id, envelope: r.envelope, at: r.at });
      return out.length ? json(200, { results: out }) : new Response(null, { status: 204 });
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
