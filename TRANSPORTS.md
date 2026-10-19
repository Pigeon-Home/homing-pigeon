# Transports: beyond email

> **Status.** Only email is implemented, in `runner/runner.py` directly.
> Anything not built is listed in FUTURE.md: NATS, MQTT, Redis,
> Postgres, Durable Objects, and the local-socket. The sections below
> are design notes, not implementation.

## Yes, email. We know.

Let's get it out of the way: the words "email-driven agent" make a
certain kind of engineer visibly wince. It sounds like a hack — like
we couldn't think of anything better, so we reached for the protocol
grandpa uses.

Here's the thing: email was the right *first* transport, and not by
accident. The runner lives on your machine, behind NAT, with no
inbound ports — it can only *poll outward*. Email gives us a
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
2. **Outbound-only polling.** The runner never opens an inbound port.
   It reaches *out* to collect jobs and deliver results. This is
   non-negotiable — it's what lets the runner live behind NAT on a
   home machine or a Pi.
3. **Authenticated sender identity.** The transport must tell the
   runner *who sent this* in a way the runner can verify — the
   equivalent of the HMAC signature check, ideally stronger.
4. **At-least-once delivery.** The runner must be able to say "I
   haven't processed this yet" and see it again — the equivalent of
   leaving a message unseen.
5. **Opaque blobs.** The transport carries the signed JSON and never
   parses it. The cryptography lives above the pipe, not in it.

Meet those five, and you're a transport. Here's the bench.

---

## Cloudflare Queues ⭐ — the pick

If email is the carrier pigeon, Cloudflare Queues is the freight
rail. This is the transport the protocol *wants* to grow into, and
it's the one we'd recommend to anyone who winces at the word "email."

Why it fits so well it feels designed for this:

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

## NATS JetStream — the purist's choice

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

This is the only transport on the list that isn't poll-based, which
makes it the odd one out — but for interactive back-and-forth with
your SI (the Oracle's `ask` loop, rapid iteration), push
notification is genuinely nicer than a 30-second poll.

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

Only the Email row runs in the runner. The other rows are design
notes. There is no setting that switches the runner onto them.

| Transport | NAT-friendly | Auth story | At-least-once | Self-hostable | Free tier | In the runner |
|---|---|---|---|---|---|---|
| Email | poll | HMAC on the body | Unseen flag | n/a (hosted) | yes | yes, the only one |
| Cloudflare Queues | HTTPS poll | API token | Retries + DLQ | no | yes | no |
| NATS JetStream | yes | NKey/JWT | Consumer acks | tiny binary | self-host | no |
| MQTT | yes | TLS + creds | QoS 1 | Mosquitto | self-host | no |
| Redis Streams | yes | Token/password | Pending list | yes | Upstash | no |
| Postgres | yes | DB creds | Transactions | yes | Neon/Supabase | no |
| Durable Objects | push | Token | Txn storage | no | yes | no |

## Writing a new transport

The protocol is deliberately transport-agnostic. A future transport
would implement three operations and nothing else:

- `send(queue, blob)` — put an opaque signed JSON blob somewhere
- `poll(queue) -> [blob]` — retrieve unprocessed blobs, outbound-only
- `ack(blob_id)` — mark processed (or don't, for redelivery)

The blob would not change. The signatures would not change. The
Oracle would not know the difference. The runner does not load a
transport module today. Email is hardcoded in `runner/runner.py`.
A pull request is how a second pipe would land. There is no plugin
hook.

Result routing travels with the job. A signed job may name where its
result goes — on email that's the `reply_to` field; on a future
transport it would be the equivalent (a reply queue or address inside
the signed blob). The transport never invents a destination: it
delivers where the signed job says, and falls back to the shared
mailbox/queue when the job names nothing.

## Bootstrapping

Email is the only pipe you can turn on today. Get that running (a
dedicated mailbox account), and stop there. What is not built, and
what was cut, is listed in FUTURE.md. There is no config
key that flips the runner onto another pipe. A runbook that says
"install the dependency and switch the transport" will not find that
switch.

## Local socket — cut

An earlier revision specified a loopback-TCP test transport
(`127.0.0.1:8766`, length-prefixed blobs) for the local SI harness.
It was cut along with the other broker transports: it was never
implemented, and the harness tests through the in-process Oracle
path and the real email transport instead. This section is kept as
a record of the cut, not a spec.
