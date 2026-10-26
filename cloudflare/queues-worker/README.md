# The hosted queue: Worker and Durable Object

The Cloudflare side of the `queues` transport (`docs/extend/transports.md`,
"Queues"; `docs/project/hosting.md`, Phase 2). One Worker fronts one
Durable Object per tenant: the tenant's job queue, result box and
quota counters in one transactional store.

Gates, in order: the tenant must exist, the bearer token must hash to
the role's stored hash, a job body must carry a valid HMAC-SHA-384
under the tenant's shared secret (`REJECT_INVALID_HMAC`, on by
default), and the tenant's quota must have room. The quota is the
spending cap Cloudflare does not provide: jobs per hour and bytes per
day, a hard 429 with `Retry-After`, nothing stored or billed past it.

## Deploy

```bash
cd cloudflare/queues-worker
# one tenant, no KV:
wrangler secret put TENANT          # the tenant slug
wrangler secret put SI_TOKEN        # what the SI sends as Bearer
wrangler secret put RUNNER_TOKEN    # what the runner sends as Bearer
wrangler secret put HMAC_SECRET     # the tenant's shared secret
wrangler deploy
```

Many tenants: bind a KV namespace as `TENANTS` and store one record
per slug: `{"si_token_sha256", "runner_token_sha256", "hmac_secret",
"quota": {"jobs_per_hour", "bytes_per_day"}}`. Hashes are SHA-256 hex
of the token.

## Test

```bash
node --test cloudflare/queues-worker/test/
```

No wrangler, no network: the Durable Object namespace and KV are
in-memory fakes with the shapes the runtime hands the Worker.
