# Transports: beyond email

> **Status.** Five job transports are implemented, and all
> five are **transport extensions**: standalone programs the
> runner supervises as child processes, selected by the
> `transports` config key (default `["email"]`): **email** (the
> default, and the project's test transport), the **file**
> transport (a watched folder), **core NATS** pub/sub, the
> **queues** transport (the hosted queue: a Cloudflare Worker the
> runner polls over HTTPS, shipped below), and the **DTLS** session
> binding (shipped below; off unless enabled).
> The
> runner core is transport-blind — it imports no transport code
> and talks to each extension through a file channel (job
> envelopes in, result envelopes out; see "Writing a new
> transport"). Everything else below — NATS JetStream, MQTT,
> Redis, Postgres, a real-time Durable Objects pipe — is design
> notes, not implementation, and is listed in docs/project/future.md. (A
> loopback local-signal socket IS also shipped — it carries
> signed `sensor_alert` envelopes from same-box producers, not
> jobs.)

## Yes, email. We know.

Let's get it out of the way: the words "email-driven agent" make a
certain kind of engineer visibly wince. It sounds like a hack — like
we couldn't think of anything better, so we reached for the protocol
grandpa uses.

Here's the thing: email was the right *first* transport, and not by
accident. The runner lives on your machine, behind NAT — for jobs
it can only *poll outward*. (It does bind two loopback-only
listeners: the local-signal socket on 127.0.0.1:39271 and the
Oracle page on 127.0.0.1:11436. Neither is reachable off the box,
and neither carries jobs.) Email gives us a
store-and-forward mailbox reachable from anywhere, with at-least-once
semantics (the IMAP unseen flag), authentication (the HMAC signature
on every message), and zero infrastructure to operate. Every SI on earth can
already reach a mailbox. It was the only transport with all of those
properties on day one.

But — and this is the part that matters — **the protocol was never
about email.** Email is just Transport #1. The signed JSON, the HMAC,
the Oracle, the two-phase query exchange: none of it knows or cares
what pipe it travels through.

## The transport contract

Anything that wants to carry homing-pigeon must provide:

1. **Async store-and-forward.** The SI sends a job and walks away; the
   runner picks it up on its own schedule. No rendezvous, no open
   connections.
2. **Outbound-only polling for jobs.** The runner opens no inbound
   port to the network. It reaches *out* to collect jobs and
   deliver results. (Loopback-only listeners on the same box —
   the signal socket and the Oracle page — are not network ports
   and carry no jobs.) This is non-negotiable — it's what lets
   the runner live behind NAT on a home machine or a Pi. One
   deliberate exception exists, and it does not hide: the DTLS
   session binding (below) is not a store-and-forward transport
   at all — it listens on a UDP port, only when the owner
   enables it. Every transport that polls keeps this rule.
3. **Authenticated sender identity.** The transport must tell the
   runner *who sent this* in a way the runner can verify — the
   equivalent of the HMAC signature check, ideally stronger.
4. **At-least-once delivery.** The runner must be able to say "I
   haven't processed this yet" and see it again — the equivalent of
   leaving a message unseen.
5. **Opaque blobs.** The transport carries the signed JSON and never
   parses it. The cryptography lives above the pipe, not in it.

Meet those five, and you're a transport. Here's the bench.

One thing a transport never has to build: the result stash. The core
writes every result to `<base_dir>/outbox/` and commits the job as
seen before the first send, whatever the pipe (PROTOCOL.md section
5); for a channel transport the "send" is the drop into the
channel's outbox, and a record that never got there goes back out
the same channel on a later poll, named by the transport it came
through. The core's one door out (`maybe_send`) is the seam, so an
extension that speaks the channel contract gets the guarantee for
free.

## Authorization gates

The HMAC signature on the job body is checked by the runner's
core on every transport, after the pipe delivers. Where a
transport has credentials of its own, they are a second,
required gate in front of the signature — not a formality:

- **Email** has one gate: the signature. The mailbox login
  authorizes the runner's *reading*; it says nothing about any
  sender.

  The pipe itself is TLS, as the draft's Transport Binding
  requires: IMAP and SMTP over TLS 1.2 or higher, the peer
  certificate verified. The runner expresses that requirement
  as the `mail_tls_required` config option, required by
  default — IMAP is implicit TLS only, and SMTP's STARTTLS
  runs with a verifying context (a refused upgrade fails the
  connection). Setting `mail_tls_required: false` is an
  explicit escape hatch: STARTTLS is still attempted but the
  certificate is unverified — the posture that predates the
  option — a WARN is logged, and an installation with the
  hatch open does not carry the draft's confidentiality
  posture. In the required posture, TLS 1.2 sessions are
  further restricted to ECDHE cipher suites, so mail-hop
  connections are forward-secret — as TLS 1.3 connections
  are inherently. There is no cleartext mail path in either mode;
  the hatch relaxes verification, never encryption.
- **NATS**, configured in its default posture, has two:
  broker authentication (user/password or token) is required
  before the runner will even start the transport, and the
  signature is checked on every job after that. A deployment
  that sets `transport_nats.allow_unauthenticated: true` gives
  the first gate up — it falls back to the signature as the
  only gate, and the startup log says so.
- **Queues** has two: the Worker refuses a job without the SI's
  bearer token, and with the default `REJECT_INVALID_HMAC` it
  checks the HMAC at the edge under the tenant's shared secret;
  the core checks the signature again after the runner leases
  the job. The runner's own token leases, acks and posts results;
  it cannot submit a job.
- **File** has two: the inbox folder's OS access control —
  only principals the owner grants write access can submit a
  job file at all — and then the signature.
- **DTLS** has two, and a property none of the others have.
  The session is authenticated before any job crosses it —
  the shared secret itself is the session's pre-shared key,
  so the transport's authentication is the same secret doing
  a second job, not a separate credential — and the signature
  is checked on every job inside the session, as always. On
  top of the two gates, the session is confidential with
  perfect forward secrecy (see "DTLS — shipped" below).

That makes a credentialed broker transport, in its default
required-auth posture, the more secure option of the shipped
store-and-forward four: submitting a job must pass transport
authentication AND the signature, where email checks the
signature alone. Email remains the default anyway — it is the
most universal pipe and the project's test transport. Here,
"default" does not mean "most secure".

One more layer rides above every pipe, unchanged: per-job
encryption. `send_job.py` encrypts the signed job body by
default (AES-256-GCM under a key derived from the
shared secret), the core unwraps it after the signature
verifies, and the result mirrors the job's form. A transport
carries the envelope exactly as it carried the cleartext
body — it is an opaque blob either way — so encryption is
identical on email, NATS, file and queues, and no transport code
knows it exists.

---

## Queues — the hosted pipe (built)

If email is the carrier pigeon, the hosted queue is the freight
rail. It is the transport a hosted runner uses when the tenant has
no mailbox to bring (`docs/project/hosting.md`, Phase 2), and the
one we'd recommend to anyone who winces at the word "email."

**What ships.** Three parts, one contract:

- `cloudflare/queues-worker/` — a Cloudflare Worker and one Durable
  Object per tenant. The Worker gates every job at the edge
  (bearer token for the role, then HMAC-SHA-384 under the tenant's
  shared secret, `REJECT_INVALID_HMAC` on by default) and enforces
  the tenant's quota: jobs per hour and bytes per day, a hard 429
  with `Retry-After`. That quota is the spending cap Cloudflare
  itself does not provide. Its unit tests run under node
  (`node --test cloudflare/queues-worker/test/`).
- `runner/transport_extensions/queues/` — the runner-side extension.
  Outbound only: it leases jobs from the Worker, drops them in the
  channel inbox, posts the channel's results back and acks the job
  only once its result has been posted (or the core consumed it
  without one). A malformed or oversize envelope is refused and
  acked so it does not return every lease.
- `send_job.py new --to-queue <url>` — the SI side. The SI token is
  read from `HP_SI_TOKEN` (or `--queue-token-env NAME`), never from
  the command line.

**The contract** (every route under `/t/<tenant>/`, every call with
`Authorization: Bearer <token>`; the envelope is the file transport's
shape, subject line, blank line, signed body):

| Who | Call | Means |
| --- | --- | --- |
| SI | `POST /jobs` | a signed job in; 202 `{"id"}`, 200 `{"duplicate": true}` on a repeat, 403 bad signature, 429 over quota |
| runner | `GET /jobs?max=N` | lease up to N jobs; 200 `{"jobs": [{"id", "envelope", "attempt"}]}` or 204 |
| runner | `POST /jobs/<id>/ack` | the job is finished; 204, or 404 if already gone |
| runner | `POST /results` | a result envelope in; 202 |
| SI | `GET /results?max=N` | results out; 200 `{"results": [...]}` or 204 |
| SI | `POST /results/<id>/ack` | the SI has it; 204 |

A lease lasts `LEASE_MS` (default 300 s); an unacked job is offered
again when it expires, and after five attempts it moves to the
tenant's dead-letter list. Tenant records live in the `TENANTS` KV
namespace (`si_token_sha256`, `runner_token_sha256`, `hmac_secret`,
`quota`), or in the four secrets `TENANT`, `SI_TOKEN`,
`RUNNER_TOKEN`, `HMAC_SECRET` for a one-tenant deployment.

Runner config:

```json
"transports": ["queues"],
"transport_queues": {"url": "https://hp.example.workers.dev/t/alice",
                     "token_env": "HP_RUNNER_TOKEN"}
```

Why it fits so well it feels designed for this (the notes that led here):

- **HTTP polling API.** The runner long-polls over HTTPS — outbound
  only, NAT-indifferent, no IMAP client, no mailbox quirks. The
  polling loop gets *simpler*, not more complex.
- **Retries and dead-letter queues are built in.** Email's at-least-once
  story is "leave the email unseen and hope the flag semantics hold."
  Queues give you redelivery counts, backoff, and a DLQ for poison
  messages as first-class concepts. The delivery guarantees stop
  being something we hand-rolled and start being something we
  inherited.
- **Batches.** The runner can pull up to 100 messages per poll instead
  of walking an inbox one `UNSEEN` at a time. Throughput goes from
  "fine" to "don't think about it."
- **API-token auth gives the queue its own identity story.** Instead of
  relying on the message signature alone, the queue is
  addressed by a token only the SI and the runner hold. The identity
  story gets *better* than email, not just equivalent.
- **It's cheap to the point of irrelevance.** The free plan covers
  10,000 operations a day, and the paid plan includes a
  million operations a month. Your agent would have to be
  extraordinarily busy to cost you anything.
- **Edge presence.** The queue lives milliseconds from wherever the
  SI is, instead of inside one specific provider's datacenter.

The shape of it: two queues, `pigeon-jobs` and `pigeon-results`.
The SI's `send_job` drops a signed blob on `pigeon-jobs`. The runner
polls it, executes, drops the signed result on `pigeon-results`. The
SI polls that. Everything else — the JSON, the signatures, the
Oracle, the two-phase exchange — is byte-identical. You could run
email and Queues *side by side* during migration and the protocol
wouldn't notice.

The pitch, if you need one for the skeptics: *"Email gave us the
protocol. Queues give it a spine."*

---

## NATS (core) — shipped

The NATS transport extension ships a minimal core-NATS
client: hand-rolled on the standard library (in the extension,
`runner/transport_extensions/nats/`), speaking
INFO/CONNECT/SUB/MSG/PUB/PING/PONG. No JetStream, no
clustering, no persistence.

- Jobs arrive on `homing-pigeon.jobs` (config
  `transport_nats.subject`) as the usual envelope: subject
  line, blank line, signed body. Results publish to
  `homing-pigeon.results.<job_id>`
  (`transport_nats.result_subject_prefix`).
- The extension holds one persistent connection: subscribe,
  deliver jobs to the runner's channel as they arrive,
  publish results as they come back. A dead connection is
  re-established with backoff; the runner and the other
  transports never notice.
- Broker authentication is required by default: user/password
  or a token, from the `transport_nats` config keys (which
  win) or the URL userinfo. With no credentials the extension
  refuses to start unless `allow_unauthenticated: true` is
  set — see "Authorization gates" above.
- Core NATS is a dumb pipe: it does not store-and-forward. A
  job published while no runner is subscribed is gone.
  At-least-once rests on the sender re-sending jobs it never
  saw a result for, and on the runner's seen-set refusing to
  run the same job twice.

## NATS JetStream — the purist's choice (design notes)

NATS describes itself as "the connective tissue for distributed
systems," and it is not exaggerating. This is the transport for
people who think a message queue should be a beautiful piece of
infrastructure, not a SaaS billing line.

- **Subject addressing maps onto the protocol like it was drawn for
  it:** `pigeon.jobs.<job_id>`, `pigeon.results.<job_id>`,
  `pigeon.query.<query_id>`. The routing *is* the addressing scheme.
- **JetStream gives you persistence, consumer groups, and ack-based
  redelivery** — the at-least-once contract, done properly, with
  per-consumer replay. The runner is just a durable consumer.
- **Self-host it on the pigeon-coop Pi.** NATS's entire server is a
  single small binary that sips memory. Your always-on Pi becomes
  the message backbone for your whole fleet of runners — and now
  you're running one agent or ten with no per-message bill at all.
- **Microsecond latency** for those who care (you won't notice; the
  jobs take longer than the queueing, but it's nice to know).

The tradeoff: you're operating infrastructure now. If "I run my own
NATS cluster" sounds like a fun weekend, this is your transport. If
it sounds like a pager going off, see Cloudflare Queues.

## File — shipped

The file transport extension is a watched folder pair, for
local harnesses, CI, and SI integrations that share a
filesystem or a sync folder with the runner — no account, no
broker, nothing to sign up for.

- A job is a file dropped in the inbox (default
  `<base_dir>/transport-file/inbox`): first line the subject
  line, blank line, then the signed body — exactly what
  `runner/cloud/send_job.py new ... --to-file <path>` writes.
- The extension processes each file once: after the result
  comes back it moves the job file to a `done/` subfolder —
  never deletes. Results land in the outbox as
  `<job_id>.result.txt`, same envelope shape. A redelivered
  copy of a finished job is acked, not re-executed.
- Refusals mirror the local-inbox discipline: symlinks are
  refused unread, files over 4 MiB are refused unread, and a
  malformed envelope is refused with the reason left in a
  `.refused.txt` note in `done/` — never silently dropped.
- Its first gate is the inbox folder's OS access control:
  only principals the owner grants write access can submit.
  The signature is the second gate (see "Authorization
  gates").

## DTLS — shipped (the session binding)

The DTLS transport extension is not a store-and-forward
transport: it is the DTLS session binding of protocol
version 1 from `docs/ietf/draft-homing-pigeon-00.md` — a direct DTLS 1.3
session between the SI and the runner, specified there and
implemented as a bounded pure-Python profile
(`runner/wire/dtlsproto.py`, stdlib only) in the extension at
`runner/transport_extensions/dtls/`.

- **Off unless enabled, and it listens.** Add `"dtls"` to
  `transports` and the extension binds a UDP port
  (`transport_dtls.port`, default 20220;
  `transport_dtls.bind`, default `0.0.0.0`; either one present
  but not usable is a startup config error, the extension
  refuses to start and names it, because a substituted
  address is not the one the operator configured). This is the one
  shipped transport that opens an inbound port — the
  deliberate exception to the contract's outbound-only rule
  above, taken by the owner's explicit choice.
- **One profile, enforced.** DTLS 1.3, one ciphersuite
  (TLS_AES_256_GCM_SHA384), PSK-only authentication
  with the shared secret as the external PSK (identity
  `homing-pigeon`, or `homing-pigeon:<key_id>` for an
  additional secret). Key exchange is `psk_dhe_ke` only: a
  fresh X25519 ephemeral rides every handshake and every
  resumption, and `psk_ke` is never offered or accepted —
  perfect forward secrecy is a requirement of the profile,
  not a negotiated option. A stateless cookie exchange
  proves the peer's address before the extension keeps any
  state, Connection IDs keep a session alive across a NAT
  rebinding, session resumption uses fresh tickets with
  fresh DHE, and there is no 0-RTT, ever.
- **The greeting.** After the handshake authenticates — never
  before — the runner sends the session's first application
  message: a greeting carrying platform information tiered
  by the runner's `dtls_greeting` config (`none` / `family`,
  the default: OS family only / `standard`: plus OS release
  and Python version / `full`: plus a bounded PATH-tools
  summary). The SI initiates; the runner chooses what it
  discloses; the client cannot widen it. Jobs are accepted
  only after the greeting has been sent.
- **Inside the session**, each message is the same signed
  envelope every other binding carries; the per-job
  encryption extension composes with it unchanged (a
  cleartext job in DTLS and an encrypted job in DTLS are
  both legal). Ack/dedup is still the protocol's seen-set —
  channel security is not delivery. Results return on the
  session; a result that lands after its session is gone is
  logged loudly and acked, and the SI re-asks on a fresh
  session.
- **The client** is `runner/cloud/send_dtls.py`: it signs exactly
  like `send_job.py` (per-job encryption on by default,
  `--cleartext` selects the plain signed form), prints the
  greeting, sends the job, prints the verified result, and
  can persist the resumption ticket between runs. Usage:
  `python3 runner/cloud/send_dtls.py --host <runner> [--port 20220]
  --secret <the-string> [--key-id ID] [--kind ping|exec
  --script-file job.sh --timeout 300] [--job-id ID]
  [--wait 120] [--ticket-file PATH] [--encrypt|--cleartext]`.
  `--wait` is how many seconds to hold the session open for
  the result (default 120); `--ticket-file` stores the
  resumption ticket so the next run resumes (with a fresh
  DHE share, as the profile requires).
- **One supervisor deviation, stated plainly:** the dtls
  extension is the one pipe the supervisor hands the shared
  secret to — because this pipe terminates PSK
  authentication with it. A pipe that merely carries
  envelopes (email, file, NATS) is still never handed a
  secret, and every job that arrives over DTLS still faces
  the core's signature check like any other transport's.

## MQTT — the IoT pick

MQTT is the protocol your smart lightbulbs speak, and that's not an
insult — it's a 25-year-old pub/sub design that does exactly one
thing (move small messages between unreliable endpoints) better
than almost anything else.

- **QoS 1 is at-least-once delivery**, named and standardized. The
  contract's hardest requirement arrives as a checkbox.
- **The footprint is tiny.** Mosquitto (the reference broker) runs
  happily on the same Pi as the runner. The pigeon coop becomes a
  fully self-contained cell: broker, runner, and Oracle, one
  always-on box, zero cloud dependencies beyond the SI itself.
- **Topic structure** mirrors NATS: `pigeon/jobs`, `pigeon/results`.
- **TLS is table stakes**, and every serious broker (Mosquitto,
  EMQX, HiveMQ) supports it.

The vibe: your agent infrastructure has more in common with a
factory floor than a SaaS dashboard, and that's a compliment. This
is the pick for the maximum-sovereignty crowd.

## Redis Streams — the pragmatic pick

You probably already run Redis. Redis Streams turns it into a
perfectly good job queue:

- **Consumer groups with pending-message tracking** — the broker
  *knows* which messages a consumer hasn't acked and can hand them
  back. That's the at-least-once contract with a paper trail.
- **`XREADGROUP` with `BLOCK`** is a long-poll. Outbound-only,
  NAT-friendly, one TCP connection.
- **Upstash (or similar) gives you Redis over HTTPS**, so even the
  connection story can be serverless and outbound-only if you want
  zero infrastructure.

Nobody ever got fired for putting the queue in Redis. It's not
exciting, which is exactly its virtue.

## Postgres — the boring pick (affectionate)

A `jobs` table with a `status` column, polled with
`SELECT ... FOR UPDATE SKIP LOCKED`. Or Supabase/Neon for the hosted
version.

- **You can inspect the entire system with psql.** Debugging a stuck
  job is a SQL query, not a dashboard spelunking expedition.
- **Transactions give you the at-least-once semantics for free:**
  claim the row and process it in one transaction; crash, and the
  row is still `pending`.
- **LISTEN/NOTIFY** (or just short polling) wakes the runner when
  work arrives.

It's not fast, it's not elegant, and it will never surprise you.
Some people — good people — consider that the highest praise
infrastructure can earn.

## Cloudflare Durable Objects — the real-time pick

For those who find polling *philosophically* offensive: a
