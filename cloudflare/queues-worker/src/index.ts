// Cloudflare Worker boundary for Homing Pigeon Queues transport.
//
// Optional gate: when REJECT_INVALID_HMAC is set (env or wrangler var),
// any inbound message that fails HMAC-SHA-384 verification is rejected
// at this boundary. Nothing is written to D1, no further compute runs,
// and the queue message is not acknowledged as valid.
//
// Default is off (false) so existing flows are unchanged until the
// operator turns the option on.
//
// The shared secret is expected in the HMAC_SECRET env var (or binding).
// The body is the raw signed job (or encrypted envelope) exactly as
// send_job.py produces it. Verification matches the protocol: the
// signature is the hex HMAC-SHA-384 of the canonical payload.

interface Env {
  HMAC_SECRET?: string;
  REJECT_INVALID_HMAC?: string;
  DB?: D1Database;
  // Queue binding would go here when the full transport ships.
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) {
    out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return out === 0;
}

async function hmacSha384Hex(secret: string, payload: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-384" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(payload));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function extractSigAndPayload(body: string): { payload: string; sig: string } | null {
  // Minimal extraction matching the protocol splice: the signed body
  // ends with ,"sig":"<hex>"}  (or equivalent). This is a boundary
  // check only; the full parser lives in the runner.
  const m = body.match(/,"sig":"([0-9a-fA-F]+)"\s*\}\s*$/);
  if (!m) return null;
  const sig = m[1];
  const payload = body.slice(0, m.index) + "}";
  return { payload, sig };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "POST") {
      return new Response("method not allowed", { status: 405 });
    }

    const reject = (env.REJECT_INVALID_HMAC || "").toLowerCase() === "true"
      || (env.REJECT_INVALID_HMAC || "") === "1";

    const body = await request.text();
    if (!body) {
      return new Response("empty body", { status: 400 });
    }

    if (reject) {
      const secret = env.HMAC_SECRET;
      if (!secret) {
        return new Response("HMAC_SECRET not configured", { status: 500 });
      }
      const extracted = extractSigAndPayload(body);
      if (!extracted) {
        return new Response("malformed envelope", { status: 400 });
      }
      const expected = await hmacSha384Hex(secret, extracted.payload);
      if (!constantTimeEqual(expected, extracted.sig.toLowerCase())) {
        // Reject at the boundary. Do not write to D1, do not enqueue
        // further work, do not ack as valid.
        return new Response("invalid signature", { status: 403 });
      }
    }

    // Valid (or gate off). In a full Queues transport this is where the
    // message would be written to D1 and/or published to the jobs queue.
    // For now we acknowledge so the option can be turned on without
    // changing the rest of the pipeline.
    if (env.DB) {
      // Placeholder: a real implementation would INSERT only after the
      // gate above has passed.
      // await env.DB.prepare("INSERT INTO jobs (body) VALUES (?)").bind(body).run();
    }

    return new Response("accepted", { status: 202 });
  },
};
