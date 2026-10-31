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
it can only *poll outward*. (While polling it binds one
loopback-only listener, the local-signal socket on
127.0.0.1:39271, and none with `local_signal_port` 0; `--oracle`
is a separate, non-polling mode that binds the Oracle page on
127.0.0.1:11436. Neither is reachable off the box, and neither
carries jobs.) Email gives us a
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
   the signal socket while polling, the Oracle page under
   `--oracle` — are not network ports and carry no jobs.) This is non-negotiable — it's what lets
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

- `runner/cloud/queues-worker/` — a Cloudflare Worker and one Durable
  Object per tenant. The Worker gates every job at the edge
  (bearer token for the role, then HMAC-SHA-384 under the tenant's
  shared secret, `REJECT_INVALID_HMAC` on by default) and enforces
  the tenant's quota: jobs per hour and UTF-8 bytes per day, a hard 429
  with `Retry-After`. A missing quota is the default, 600 jobs an hour
  and 256 MiB a day. A quota that is present and not an object of
  numbers (a bare number, a string, a list, or a field that is not a
  number) is a 400, not that default. That quota is the spending cap
  Cloudflare itself does not provide. Its unit tests run under node
  (`node --test runner/cloud/queues-worker/test/worker.test.mjs runner/cloud/queues-worker/test/fuzz.test.mjs runner/cloud/queues-worker/test/fatfinger.test.mjs`).
- `runner/transport_extensions/queues/` — the runner-side extension.
  Outbound only: it leases jobs from the Worker, drops them in the
  channel inbox, posts the channel's results back and acks the job
  only once its result has been posted (or the core consumed it
  without one). The inbox file is the job id, all 128 characters:
  cutting it at 120 put two ids that differed later in one file, and
  the result's name was not the id in the subject, so the output was
  never posted and the job stayed leased. An ack that does not
  succeed leaves the result where it is and the job leased, and the
  next pass tries the ack again. Plain http is the loopback host
  itself, not a URL that only begins with that text, and a redirect
  is not followed: either one would send the bearer token off the
  machine. A second file for the same id, named while the first
  is still waiting, does not replace that result and still acks the
  job. A refused collision name is set aside as that id's
  result, not under the suffixed filename: the sweep reads
  `<id>.result.txt`, and the other name never got a stub, so the
  job stayed leased. A file whose subject names a different job is left where it
  is. A malformed or oversize envelope is refused and
  acked so it does not return every lease.
- `send_job.py new --to-queue <url>` — the SI side. The SI token is
  read from `HP_SI_TOKEN` (or `--queue-token-env NAME`), never from
  the command line.
- `send_job.py results --from-queue <url>` — the SI reads its results
  back: one JSON line per result, verified and, when encrypted, opened
  under the job id in its subject. A page that stopped says `more`,
  and the command reads the next page, so a result that does not
  verify cannot hide the ones after it. `--ack` removes a result only after
  it verified; one that does not verify stays on the queue. Exit 0 when
  every result verified or none was waiting, 1 when any did not, 2 when
  the queue refused the read or a page did not advance.
- Both sides ride out the queue's weather. A read cut short, a
  dropped connection or a timeout is tried again twice, after one and
  three seconds; a read that still cannot finish exits 2 with one plain
  line. A `new --to-queue` post that drops is sent again with the same
  envelope, and the Worker answers a copy of a job it already holds as
  a duplicate, which the sender reports as queued. When every attempt
  drops, the sender says the job may or may not be queued and names
  the `--job-id` to send it again with. An HTTP status is an answer and
  is never retried.
- A watcher reads the exit code, not the output. Exit 0 with "no
  results waiting" is an empty queue: the Worker answers one with a
  204. Exit 2 is unknown and says nothing about the runner, and that
  includes a 200 whose body carries no results list, which the Worker
  never sends. Conclude that a runner has stopped only from reads that
  finished.
- `send_job.py dlq --from-queue <url>` — the dead-letter list: one JSON
  line per dead job, or `--drop ID`, or `--requeue ID`. A page that
  stopped says `more`, and the command reads the next page, so a
  long subject does not hide the rows after it. A requeued job
  is the same signed job, so a runner that already saw it, or holds it
  past its freshness window, refuses it as any replay; send a new job
  for anything older. The queue transport delivers that offer again,
  including to a process that already finished the id. Ignoring it
  would still lease it on every pull until it dead-lettered.

**The contract** (every route under `/t/<tenant>/`, every call with
`Authorization: Bearer <token>`; the envelope is the file transport's
shape, subject line, blank line, signed body):

| Who | Call | Means |
| --- | --- | --- |
| SI | `POST /jobs` | a signed job in; 202 `{"id"}`, 200 `{"duplicate": true}` on a repeat of a live id, 409 naming the dead record when that id is on the dead-letter list, 400 when the id is not 1–128 of `[A-Za-z0-9._-]` (and not `.` or `..`) or the subject's id is not the `job_id` in the signed payload, 403 bad signature, 413 when the stored record (including its dead-letter copy, the hand a pull adds, and the `requeued_at` a later dead copy still carries) would pass the object's 2 MB key-and-value limit, 429 over quota |
| runner | `GET /jobs?max=N` | lease up to N jobs (N clamped to 1..100; a non-number keeps 8; 0 or below is 1), fewer when the envelopes would pass 8 MB; 200 `{"jobs": [{"id", "envelope", "attempt", "hand"}]}` or 204 |
| runner | `POST /jobs/<id>/ack` | the job is finished; 204, or 404 if already gone. `?hand=N` is the hand the pull returned, and `?attempt=N` is that pull's attempt. A later pull has a higher hand, and a requeue bumps the hand too, so the first runner's ack does not delete the job the later pull is running. Omitting both is the old call and deletes whatever is queued under that id |
| runner | `POST /jobs/<id>/lease` | renew the lease on a job still running, each pass, so a job longer than the lease is not offered again or dead-lettered; 204, or 404 when the queue no longer holds it leased. `?attempt=N` names the attempt the pull handed out and `?hand=N` names its hand; a later pull's lease is not extended |
| runner | `POST /results` | a result envelope in; 202, 200 `{"duplicate": true, "sha256"}` when that id is already stored (the first envelope stays, `sha256` is of that envelope, and a copy is not billed again), 400 when the id is not a safe id, the tenant quota is not a number, or the body's `job_id` (a result) or `query_id` (a qresult) is present and is not the id in the subject, 413 over the same 2 MB storage limit, 429 when result bytes for the UTC day would pass `bytes_per_day`. That counter is not the job counter: a day full of jobs still accepts its answers. A body that does not carry the field, including an encrypted envelope, is not refused for this. The queue client acks the job on a 200 only when `sha256` is the body it just sent. A 400 or a 413 is not posted again: the result is set aside and the job stays leased until the stub goes out. A result bigger than the channel's file cap is set aside before it is posted, and that does not ack the job either |
| SI | `GET /results?max=N` | results out (N clamped to 1..100; a non-number keeps 20; 0 or below is 1), fewer than N when the envelopes would pass 8 MB. `more: true` means the page stopped with rows still waiting, and `?after=<id>` (the last id returned; an id that is not safe is ignored) is the next page, so a result that stays unacked cannot hide the ones after it. 200 `{"results": [...]}` or 204 |
| SI | `POST /results/<id>/ack` | the SI has it; 204 |
| SI | `GET /dlq?max=N` | the dead-letter list (N clamped the same way as results): id, attempts, subject and times, no envelope; fewer than N when the subjects would pass 8 MB. `more: true` means the page stopped with rows still waiting, and `?after=<id>` (the last id returned; an id that is not safe is ignored) is the next page, so the rest is read without dropping. 200 `{"dead": [...]}` or 204 |
| SI | `POST /dlq/<id>/ack` | drop a dead job; 204, or 404 |
| SI | `POST /dlq/<id>/requeue` | offer it again with a fresh attempt count, counted against the hourly job quota; 202, 404, 409 when a job with that id is queued, 429 over quota |

A lease lasts `LEASE_MS` milliseconds (default 300000, five minutes).
Zero, a negative, or a word is that default. The value is read with
`parseInt`, so `300` is 300 milliseconds and `300000ms` is 300000.
The runner renews the lease
of every job it is still running on each pass, so a long build keeps
one attempt however long it runs. A job whose lease lapses (the runner
died or lost the network) is offered again, and after five attempts it
moves to the tenant's dead-letter list. Sending that id again is
refused with 409 until the SI drops the dead record or requeues it;
enqueue does not clear the death record and does not bill the
refusal. Tenant records live in the `TENANTS` KV
namespace (`si_token_sha256`, `runner_token_sha256`, `hmac_secret`,
`quota`), or in the four secrets `TENANT`, `SI_TOKEN`,
`RUNNER_TOKEN`, `HMAC_SECRET` for a one-tenant deployment.
A one-tenant deployment of this contract was run on
2026-10-27: a stranger gets 401 on the configured tenant and
404 on any other, and a signed ping came back exit 0 with an
encrypted result. The record, tokens left out, is
`docs/reports/queues-2026-10-27.md`.

Runner config:

```json
"transports": ["queues"],
"transport_queues": {"url": "https://hp.example.workers.dev/t/alice",
                     "token_env": "HP_RUNNER_TOKEN"}
```

`token_env` is for a runner started from a shell that exports the
variable. A runner installed as a system service gets no such
environment, so it carries the token itself as `"token": "..."` in
the same block (the config file is 0600 and already holds the
shared secret). When both are set, a non-empty `token_env` variable
wins and an empty one falls back to `token`.

Why it fits so well it feels designed for this (the notes that led
here; what ships is the contract above, and where a note below
says "queue", the shipped pipe is the Worker's Durable Object):

- **HTTP polling API.** The runner long-polls over HTTPS — outbound
  only, NAT-indifferent, no IMAP client, no mailbox quirks. The
  polling loop gets *simpler*, not more complex.
- **Retries and dead-letter queues.** Email's at-least-once story
  is "leave the email unseen and hope the flag semantics hold."
  The Worker gives each job a lease, an attempt count and, after
  five attempts, the tenant's dead-letter list, as first-class
  concepts the runner reads instead of hand-rolls.
- **Batches.** The runner can pull up to 100 messages per poll instead
  of walking an inbox one `UNSEEN` at a time. Throughput goes from
  "fine" to "don't think about it."
- **API-token auth gives the queue its own identity story.** Instead of
  relying on the message signature alone, the queue is
  addressed by a token only the SI and the runner hold. The identity
  story gets *better* than email, not just equivalent.
- **It's cheap to the point of irrelevance.** A Worker and one
  Durable Object per tenant sit inside Cloudflare's free tier for
  any agent that is not extraordinarily busy; the tenant quota
  (jobs per hour, bytes per day) is the cap on what busy costs.
- **Edge presence.** The queue lives milliseconds from wherever the
  SI is, instead of inside one specific provider's datacenter.

The shape of it: one Durable Object per tenant with a `/jobs` side
and a `/results` side. The SI's `send_job --to-queue` posts a
signed envelope to `/jobs`. The runner leases it, executes, posts
the signed result to `/results`. The SI reads it with
`send_job results --from-queue`. Everything
else — the JSON, the signatures, the Oracle, the two-phase
exchange — is byte-identical. You could run email and the queue
*side by side* during migration and the protocol wouldn't notice.

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
  fresh DHE, and there is no 0-RTT, ever. A resumption ticket
  records the key that authenticated the session it was
  issued on, carried across a resume, and resumes only while
  that key still stands in the runner's key map: a rotated-out
  key is refused at a resume exactly as at a fresh handshake,
  and a ticket that records no key does not resume.
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
  DHE share, as the profile requires); a ticket the runner
  refuses, as after a rotation, is followed by one fresh
  handshake under the key itself, and the file is dropped.
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

For those who find polling *philosophically* offensive: a Durable
Object is a tiny stateful program living on Cloudflare's edge. Model
the mailbox as one.

- The SI `POST`s the signed job to the DO's HTTPS endpoint.
- The runner holds a **WebSocket** to the same DO and gets the job
  *pushed* the moment it lands. No polling interval, no latency
  floor.
- **Transactional storage** inside the DO gives you the
  exactly-once-ish bookkeeping; the runner acks, the DO deletes.

The hosted queue above already runs one Durable Object per tenant;
what this note adds is the push leg, a WebSocket in place of the
runner's lease poll. It would be the only transport on the list
that isn't poll-based, which makes it the odd one out — but for
interactive back-and-forth with your SI (the Oracle's `ask` loop,
rapid iteration), push notification is genuinely nicer than a
30-second poll.

## Honorable mentions

- **nostr relays.** Key-based identity is *philosophically* the
  closest thing here to the protocol's HMAC identity model — your
  keypair *is* you, no accounts, no From headers. Exotic, but the
  shape is right, and relays are dumb pipes that can't read your
  (signed, and optionally encrypted) blobs. One to watch.
- **Webhooks to the SI.** Inverted direction, worth naming: some
  SIs can receive outbound webhooks, which would let the runner
  *push* results instead of the SI polling. Transport #1.5.

---

## Comparison

Email, File, core NATS, DTLS and the hosted Queues run today as
transport extensions, selected by the `transports` config key.
The other rows are design notes.

| Transport | NAT-friendly | Auth story | At-least-once | Self-hostable | Free tier | In the runner |
|---|---|---|---|---|---|---|
| Email | poll | HMAC signature only | Unseen flag | n/a (hosted) | yes | yes, the default |
| File | n/a (local folder) | Folder OS ACL, then HMAC | Process-once + done/ | n/a | n/a | yes |
| NATS (core) | outbound connect | Broker auth (required), then HMAC | Sender resend + seen-set | tiny binary | self-host | yes |
| DTLS | no — listens (opt-in) | PSK session (the shared secret), then HMAC | Sender resend + seen-set | n/a | n/a | yes, off by default |
| Queues (hosted) | HTTPS poll | Bearer token per role, then HMAC at the edge | Lease + ack, five attempts, then dead-letter | your own Worker | Cloudflare's | yes |
| NATS JetStream | yes | NKey/JWT | Consumer acks | tiny binary | self-host | no |
| MQTT | yes | TLS + creds | QoS 1 | Mosquitto | self-host | no |
| Redis Streams | yes | Token/password | Pending list | yes | Upstash | no |
| Postgres | yes | DB creds | Transactions | yes | Neon/Supabase | no |
| Durable Objects (push) | push | Token | Txn storage | no | yes | no |

On gates: a credentialed NATS deployment in its default
required-auth posture is the more secure option over email —
two gates (broker authentication, then the signature) against
email's one (the signature). A deployment with
`allow_unauthenticated: true` is not: it falls back to the
signature as the only gate. The hosted queue has two as well:
the role's bearer token at the edge, then the signature, checked
once by the Worker and again by the core. DTLS stands apart
from the count: its session is authenticated with the shared
secret itself and is confidential with perfect forward secrecy,
and the signature still checks every job inside it. See
"Authorization gates".

## Writing a new transport

The protocol is deliberately transport-agnostic, and transports
are *extensions*: a new transport is a new program, not a
patch to the runner. The contract is versioned at one —
`TRANSPORT_API_VERSION = 1` in `runner/wire/transports.py`.

A transport extension is a folder with an `extension.json`
manifest:

```json
{"name": "smoke", "kind": "transport", "api_version": 1,
 "version": "0.1.0", "publisher": "Your Name",
 "capabilities": ["network"],
 "startup_settle_ms": 0,
 "entry": ["{python}", "smoke.py", "{channel_dir}",
           "{runtime_config}"]}
```

`entry` is the argv the runner launches (tokens `{python}`,
`{extension_dir}`, `{channel_dir}`, `{runtime_config}`,
`{base_dir}`, `{name}` are substituted). `capabilities` says
what the code does -- `network`, `listen`, `subprocess`,
`native` -- and the runner holds the code to it.
`startup_settle_ms` (an integer, 0 to 5000, default 0) is the
pause the runner grants once after a fresh start so a fast
local pipe can deliver what is already waiting before the first
cycle; a network transport declares 0 and never holds the cycle
up. The manifest's identity fields — name, publisher, version —
are carried from day one so a future lockdown has something to
pin; this build has no signature on the code, no allowlist, no
registry check. What it has is the extension review
([docs/extend/extensions.md](extensions.md), "The review"): before
`entry` is launched, the folder is read against the manifest --
every path in `entry` stays inside the folder, every `.py`
compiles, no symlinks, no bidi control characters, nothing that
names the runner's own state files, and every capability the
code uses is declared. Under the default `extension_review:
"enforce"` a folder that fails is refused like a bad manifest and
the runner starts without it; `advisory` loads it and says so.

**Registration is never a permission to run.** Drop the folder
into the runner's extensions directory (default
`<base_dir>/extensions`, or `extensions_dir` in config) and
name it in `transports`: the runner loads and uses it, no
catalog consulted, registered or not. That is deliberate —
test transports, private experiments, and pipes nobody
catalogued are first-class. A folder in the extensions
directory shadows a shipped transport of the same name; the
review says so at every start, with a security event, and a
shadowing drop-in the review refuses is absent rather than
quietly replaced by the shipped one. First-party extensions
ship under `runner/transport_extensions/` and are found the
same way. A manifest declaring any `api_version` other than 1
is refused with a log line; the runner keeps running without
it.

A transport can bring its own sources for the Oracle, exactly
as a sense can: a `sources.json` next to the manifest
([docs/extend/extensions.md](extensions.md), "Sources"), fetched in the
background the first time the transport starts and given to the
Oracle under the disclosure rule. All five shipped transports
declare their own code in the project tree; email, dtls and nats
also declare the specifications they speak — the IMAP, SMTP,
STARTTLS, and message-format RFCs for email, the DTLS 1.3, TLS
1.3, HKDF, and X25519 RFCs for dtls, the NATS client protocol
for nats.

The runner supervises each enabled extension as a child
process: it starts them with the runner, restarts a dead one
with backoff (1s doubling to 30s) and a log line, and stops
them at shutdown. One extension's death never takes the
runner or the other transports down. Each extension is handed
a runtime config file (0600) holding only its own config —
its `transport_<name>` block, and for email the mailbox keys —
never the shared secret, with one exception: the dtls
extension terminates PSK authentication, so it is handed the
secret material it authenticates with (see "DTLS — shipped").
Verification is the core's job, not the pipe's. The extension's
own output lands in `<channel>/extension.log`.

The pipe itself is a pair of directories, the channel, at
`<base_dir>/transport-extensions/<name>/`:

- `inbox/` — job envelopes, extension → runner. An envelope
  is a subject line, a blank line, then the signed body; drop
  it as `<ident>.job.txt`, where `<ident>` is your stable id
  for the job.
- `outbox/` — result envelopes, runner → extension, same
  shape, named `<ident>.result.txt` for the job's ident. When
  the core knows the job's validated `reply_to`, a sidecar
  `<ident>.target.txt` sits beside the result file holding
  that one address, and the extension sends the result there
  instead of its own default destination. A pipe cannot always
  read the address out of the job itself (an encrypted job's
  envelope does not carry it in the clear, and a pipe never
  holds the secret). An extension that does not read the
  sidecar behaves exactly as before; the sidecar is additive
  at contract v1.

Ack is consumption: whichever side has taken a file moves it
into the sibling `done/` directory. The runner moves an inbox
file only when the core would have marked that mail seen. A
result that did not land, or a job the core will retry, stays
in the inbox. A rejection is consumed, so poison is not
retried. The runner services each channel once per poll cycle
and hands every envelope to the same verification/execution
core the mail path uses. The blob does not change between
transports. The signatures do not change. The Oracle does not
know the difference. (v1 ships the file channel only; there is
no socket variant.)

Result routing travels with the job. A signed job may name
where its result goes — on email that's the `reply_to` field,
and the sidecar above carries it to any pipe. Without one, the
result returns over the transport that carried the job in (the
file outbox, the NATS result subject, the queue's `/results`).
The transport never invents a destination.

## Bootstrapping

Email is the pipe to turn on first: get that running (a
dedicated mailbox account). The file transport needs nothing
else — set `transports` to include `file` and drop envelopes
in the inbox. NATS needs a broker you run (or one you already
have) plus credentials for it. The hosted queue needs a Worker
you deploy and a tenant record (`docs/project/hosting.md`). The
`transports` config key (or `--transports` for one process) is
the switch; several transport extensions run side by side, each
supervised by the one runner. What is not built is listed in
docs/project/future.md; what was cut is below.

## Local socket — cut

An earlier revision specified a loopback-TCP test transport
(`127.0.0.1:8766`, length-prefixed blobs) for the local SI harness.
It was cut along with the other broker transports: it was never
implemented, and the harness tests through the in-process Oracle
path and the real email transport instead. This section is kept as
a record of the cut, not a spec.
