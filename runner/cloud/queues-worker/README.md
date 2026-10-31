# The hosted queue: Worker and Durable Object

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

The Cloudflare side of the `queues` transport (`docs/extend/transports.md`,
"Queues"; `docs/project/hosting.md`, Phase 2). One Worker fronts one
Durable Object per tenant: the tenant's job queue, result box and
quota counters in one transactional store.

Gates, in order: the tenant must exist, the bearer token must hash to
the role's stored hash, a job body must carry a valid HMAC-SHA-384
under the tenant's shared secret (`REJECT_INVALID_HMAC`, on by
default), and the tenant's quota must have room. The gate finds the
signed object with the runner's own extractor, ported line for line,
so it queues exactly the signatures the runner accepts; the de_dust
wire target checks the two against each other on every replay. The quota is the
spending cap Cloudflare does not provide: jobs per hour and bytes per
day, a hard 429 with `Retry-After`, nothing stored or billed past it.
The object is SQLite-backed, so a key and its value together cannot
exceed 2 MB. An envelope that would not fit, including the dead-letter
copy with its lease timestamp, the hand a pull adds, and the
`requeued_at` a later dead copy still carries, is a 413 and stores
nothing. A result is held to the same storage limit, and to the
same daily byte cap on its own counter. A day full of jobs still
accepts its answers, and a runner token cannot fill the object
past that cap. A copy of a result already stored is not billed
again. A pull reads the queue a page at a time, so
one read does not load every envelope into the object. A jobs or
results response stops at 8 MB of envelopes. A results page says
`more` when rows are still waiting, and `?after=<id>` reads on
from the last id shown, so a result that stays unacked cannot
hide the ones after it. The dead-letter list is paged the same way.
Its response does not carry the envelope, and it stops at the
same 8 MB counted on subjects. The answer says `more` when rows
are still waiting, and `?after=<id>` reads on from the last id
shown, so the list is not hidden behind a row you have not
dropped. A second result for an id keeps the first envelope, the
same way a repeated job submit does.

## Deploy

```bash
cd runner/cloud/queues-worker
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
of the token. `bytes_per_day` counts UTF-8 bytes, and so does the
size recorded on a job. A quota field that is not a number is a
400, and so is a quota that is present but not an object (a bare
number, a string, a list): that is not the default cap. A missing
quota is the default. Zero, or a blank field, locks the tenant
rather than meaning unlimited.

`homing-pigeon-host queue-tenant --tenant <slug> --worker <url>` mints
one: it writes the tokens and the shared secret to
`~/.homing-pigeon/tenants/<slug>.env` and the KV record to
`<slug>.kv.json`, both 0600, prints nothing secret, and prints the
`wrangler kv key put` and `homing-pigeon-host up --queue` commands
that use them.

## Test

```bash
node --test runner/cloud/queues-worker/test/worker.test.mjs runner/cloud/queues-worker/test/fuzz.test.mjs runner/cloud/queues-worker/test/fatfinger.test.mjs
```

No wrangler, no network: the Durable Object namespace and KV are
in-memory fakes with the shapes the runtime hands the Worker. The
fuzz file replays `test/fuzz.corpus.json`, then one seed of 20,000
operations. Some operations send a pair of requests, in order, so a
seed replays. One pinned test races two pulls. A body over the day
cap, a requeue into a full hour, a qresult, and a second tenant,
are in the mix. A pull's attempt, hand and envelope are checked against
storage, and a verb on the wrong list is a 404. An id the route
cannot name, or a subject id that is not the signed `job_id`, is a
400 and stores nothing.
