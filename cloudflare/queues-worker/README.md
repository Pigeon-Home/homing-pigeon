# Cloudflare Queues Worker boundary

Optional edge gate for the Cloudflare Queues transport (design notes in
`docs/extend/transports.md`).

When `REJECT_INVALID_HMAC` is set to `true` (wrangler var or secret), the
Worker rejects any inbound message that fails HMAC-SHA-384 verification
*before* writing to D1 or doing further compute. Invalid jobs never reach
the database or the runner.

Default is off so existing flows are unchanged until the operator turns
the option on.

## Usage

```bash
cd cloudflare/queues-worker
wrangler secret put HMAC_SECRET
wrangler vars set REJECT_INVALID_HMAC true
wrangler deploy
```

The HMAC verification matches the protocol splice used by
`runner/cloud/send_job.py` and the runner core. Full Queues + D1 wiring
is still design notes; this Worker is the boundary gate so the option
can be enabled when the rest of the transport lands.
