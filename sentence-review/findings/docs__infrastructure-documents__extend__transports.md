# Findings — docs/infrastructure-documents/extend/transports.md

Source: docs/infrastructure-documents/extend/transports.md, reviewed at main 9a2e18d6.
Sentence units: 333. Flagged: 12. Categories: pre-release 281, post-release 52.

The transport guide: the 5 requirements, the shipped transports and their gates, the hosted queue's contract in full, then design notes for transports not built (JetStream, MQTT, Redis, Postgres, push, nostr, webhooks), the comparison table, and the extension contract. The shipped material is pre-release; the design-note sections are post-release sketches. The argument flows section by section; the flags are rules, table structure, labels, and shards.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "**Status.** Five job transports are implemented, and all…" | pre-release | flows |  |
| 2 | "The runner core is transport-blind — it imports…" | pre-release | flows |  |
| 3 | "Everything else below — NATS JetStream, MQTT, Redis,…" | pre-release | flows |  |
| 4 | "Let's get it out of the way: the…" | pre-release | flows |  |
| 5 | "It sounds like a hack — like we…" | pre-release | flows |  |
| 6 | "Here's the thing: email was the right *first*…" | pre-release | flows |  |
| 7 | "The runner lives on your machine, behind NAT…" | pre-release | flows |  |
| 8 | "Neither is reachable off the box, and neither…" | pre-release | flows |  |
| 9 | "Every SI on earth can already reach a…" | pre-release | flows |  |
| 10 | "It was the only transport with all of…" | pre-release | flows |  |
| 11 | "But — and this is the part that…" | pre-release | flows |  |
| 12 | "The signed JSON, the HMAC, the Oracle, the…" | pre-release | flows |  |
| 13 | "Anything that wants to carry homing-pigeon must provide:" | pre-release | flows |  |
| 14 | "**Async store-and-forward.** The SI sends a job and…" | pre-release | flows |  |
| 15 | "No rendezvous, no open connections." | pre-release | flows |  |
| 16 | "**Outbound-only polling for jobs.** The runner opens no…" | pre-release | flows |  |
| 17 | "It reaches *out* to collect jobs and deliver…" | pre-release | flows |  |
| 18 | "One deliberate exception exists, and it does not…" | pre-release | flows |  |
| 19 | "Every transport that polls keeps this rule." | pre-release | flows |  |
| 20 | "**Authenticated sender identity.** The transport must tell the…" | pre-release | flows |  |
| 21 | "**At-least-once delivery.** The runner must be able to…" | pre-release | flows |  |
| 22 | "**Opaque blobs.** The transport carries the signed JSON…" | pre-release | flows |  |
| 23 | "The cryptography lives above the pipe, not in…" | pre-release | flows |  |
| 24 | "Meet those five, and you're a transport." | pre-release | flows |  |
| 25 | "Here's the bench." | pre-release | flows |  |
| 26 | "One thing a transport never has to build:…" | pre-release | flows |  |
| 27 | "The core writes every result to `<base_dir>/outbox/` and…" | pre-release | flows |  |
| 28 | "The core's one door out (`maybe_send`) is the…" | pre-release | flows |  |
| 29 | "The HMAC signature on the job body is…" | pre-release | flows |  |
| 30 | "Where a transport has credentials of its own,…" | pre-release | flows |  |
| 31 | "**Email** has one gate: the signature." | pre-release | flows |  |
| 32 | "The mailbox login authorizes the runner's *reading*; it…" | pre-release | flows |  |
| 33 | "The pipe itself is TLS, as the draft's…" | pre-release | flows |  |
| 34 | "The runner expresses that requirement as the `mail_tls_required`…" | pre-release | flows |  |
| 35 | "Setting `mail_tls_required: false` is an explicit escape hatch:…" | pre-release | flows |  |
| 36 | "In the required posture, TLS 1.2 sessions are…" | pre-release | flows |  |
| 37 | "There is no cleartext mail path in either…" | pre-release | flows |  |
| 38 | "**NATS**, configured in its default posture, has two:…" | pre-release | flows |  |
| 39 | "A deployment that sets `transport_nats.allow_unauthenticated: true` gives the…" | pre-release | flows |  |
| 40 | "**Queues** has two: the Worker refuses a job…" | pre-release | flows |  |
| 41 | "The runner's own token leases, acks and posts…" | pre-release | flows |  |
| 42 | "**File** has two: the inbox folder's OS access…" | pre-release | flows |  |
| 43 | "**DTLS** has two, and a property none of…" | pre-release | flows |  |
| 44 | "The session is authenticated before any job crosses…" | pre-release | flows |  |
| 45 | "On top of the two gates, the session…" | pre-release | flows |  |
| 46 | "That makes a credentialed broker transport, in its…" | pre-release | flows |  |
| 47 | "Email remains the default anyway — it is…" | pre-release | flows |  |
| 48 | "Here, "default" does not mean "most secure"." | pre-release | flows |  |
| 49 | "One more layer rides above every pipe, unchanged:…" | pre-release | flows |  |
| 50 | "`send_job.py` encrypts the signed job body by default…" | pre-release | flows |  |
| 51 | "A transport carries the envelope exactly as it…" | pre-release | flows |  |
| 52 | "---" | pre-release | flagged | A horizontal rule — structure, not a sentence |
| 53 | "If email is the carrier pigeon, the hosted…" | pre-release | flows |  |
| 54 | "It is the transport a hosted runner uses…" | pre-release | flows |  |
| 55 | "**What ships.** Three parts, one contract:" | pre-release | flows |  |
| 56 | "`runner/cloud/queues-worker/` — a Cloudflare Worker and one Durable…" | pre-release | flows |  |
| 57 | "The Worker gates every job at the edge…" | pre-release | flows |  |
| 58 | "A missing quota is the default, 600 jobs…" | pre-release | flows |  |
| 59 | "A quota that is present and not an…" | pre-release | flows |  |
| 60 | "That quota is the spending cap Cloudflare itself…" | pre-release | flows |  |
| 61 | "Its unit tests run under node (`node --test…" | pre-release | flows |  |
| 62 | "`runner/transport_extensions/queues/` — the runner-side extension." | pre-release | flows |  |
| 63 | "Outbound only: it leases jobs from the Worker,…" | pre-release | flows |  |
| 64 | "The inbox file is the job id, all…" | pre-release | flows |  |
| 65 | "An ack that does not succeed leaves the…" | pre-release | flows |  |
| 66 | "Plain http is the loopback host itself, not…" | pre-release | flows |  |
| 67 | "A second file for the same id, named…" | pre-release | flows |  |
| 68 | "A result file that was already in the…" | pre-release | flows |  |
| 69 | "It is posted, and it does not ack…" | pre-release | flows |  |
| 70 | "A refused collision name is set aside as…" | pre-release | flows |  |
| 71 | "A result file that is not UTF-8, or…" | pre-release | flows |  |
| 72 | "The link is not followed." | pre-release | flows |  |
| 73 | "A result name that is still in the…" | pre-release | flows |  |
| 74 | "The sweep still answers it: the id is…" | pre-release | flows |  |
| 75 | "Moving that pair to done without a stub…" | pre-release | flows |  |
| 76 | "A file whose subject names a different job…" | pre-release | flows |  |
| 77 | "A malformed or oversize envelope is refused and…" | pre-release | flows |  |
| 78 | "`send_job.py new --to-queue <url>` — the SI side." | pre-release | flows |  |
| 79 | "The SI token is read from `HP_SI_TOKEN` (or…" | pre-release | flows |  |
| 80 | "`send_job.py results --from-queue <url>` — the SI reads…" | pre-release | flows |  |
| 81 | "A page that stopped says `more`, and the…" | pre-release | flows |  |
| 82 | "`--ack` removes a result only after it verified;…" | pre-release | flows |  |
| 83 | "Exit 0 when every result verified or none…" | pre-release | flows |  |
| 84 | "Both sides ride out the queue's weather." | pre-release | flows |  |
| 85 | "A read cut short, a dropped connection or…" | pre-release | flows |  |
| 86 | "A `new --to-queue` post that drops is sent…" | pre-release | flows |  |
| 87 | "When every attempt drops, the sender says the…" | pre-release | flows |  |
| 88 | "An HTTP status is an answer and is…" | pre-release | flows |  |
| 89 | "A watcher reads the exit code, not the…" | pre-release | flows |  |
| 90 | "Exit 0 with "no results waiting" is an…" | pre-release | flows |  |
| 91 | "Exit 2 is unknown and says nothing about…" | pre-release | flows |  |
| 92 | "Conclude that a runner has stopped only from…" | pre-release | flows |  |
| 93 | "`send_job.py dlq --from-queue <url>` — the dead-letter list:…" | pre-release | flows |  |
| 94 | "A page that stopped says `more`, and the…" | pre-release | flows |  |
| 95 | "A requeued job is the same signed job,…" | pre-release | flows |  |
| 96 | "The queue transport delivers that offer again, including…" | pre-release | flows |  |
| 97 | "Ignoring it would still lease it on every…" | pre-release | flows |  |
| 98 | "**The contract** (every route under `/t/<tenant>/`, every call…" | pre-release | flows |  |
| 99 | "| Who | Call | Means |" | pre-release | flagged | A table header row — structure, not a sentence |
| 100 | "| --- | --- | --- |" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 101 | "| SI | `POST /jobs` | a signed…" | pre-release | flows |  |
| 102 | "`send_job.py` exits 0 on a 200 only when…" | pre-release | flows |  |
| 103 | "A different envelope exits 1 |" | pre-release | flows |  |
| 104 | "| runner | `GET /jobs?max=N` | lease up…" | pre-release | flows |  |
| 105 | "| runner | `POST /jobs/<id>/ack` | the job…" | pre-release | flows |  |
| 106 | "`?hand=N` is the hand the pull returned, and…" | pre-release | flows |  |
| 107 | "A later pull has a higher hand, and…" | pre-release | flows |  |
| 108 | "A receipt that is not this pull's is…" | pre-release | flows |  |
| 109 | "Omitting both is the old call and deletes…" | pre-release | flows |  |
| 110 | "| runner | `POST /jobs/<id>/lease` | renew the…" | pre-release | flows |  |
| 111 | "`?attempt=N` names the attempt the pull handed out…" | pre-release | flows |  |
| 112 | "| runner | `POST /results` | a result…" | pre-release | flows |  |
| 113 | "That counter is not the job counter: a…" | pre-release | flows |  |
| 114 | "A body that does not carry the field,…" | pre-release | flows |  |
| 115 | "The queue client acks the job on a…" | pre-release | flows |  |
| 116 | "A 400 or a 413 is not posted…" | pre-release | flows |  |
| 117 | "A result bigger than the channel's file cap…" | pre-release | flows |  |
| 118 | "| SI | `GET /results?max=N` | results out…" | pre-release | flows |  |
| 119 | "`more: true` means the page stopped with rows…" | pre-release | flows |  |
| 120 | "200 `{"results": [...]}` or 204 |" | pre-release | flows |  |
| 121 | "| SI | `POST /results/<id>/ack` | the SI…" | pre-release | flows |  |
| 122 | "| SI | `GET /dlq?max=N` | the dead-letter…" | pre-release | flows |  |
| 123 | "`more: true` means the page stopped with rows…" | pre-release | flows |  |
| 124 | "200 `{"dead": [...]}` or 204 |" | pre-release | flows |  |
| 125 | "| SI | `POST /dlq/<id>/ack` | drop a…" | pre-release | flows |  |
| 126 | "| SI | `POST /dlq/<id>/requeue` | offer it…" | pre-release | flows |  |
| 127 | "A lease lasts `LEASE_MS` milliseconds (default 300000, five…" | pre-release | flows |  |
| 128 | "Zero, a negative, or a word is that…" | pre-release | flows |  |
| 129 | "The value is read with `parseInt`, so `300`…" | pre-release | flows |  |
| 130 | "The runner renews the lease of every job…" | pre-release | flows |  |
| 131 | "A job whose lease lapses (the runner died…" | pre-release | flows |  |
| 132 | "Sending that id again is refused with 409…" | pre-release | flows |  |
| 133 | "Tenant records live in the `TENANTS` KV namespace…" | pre-release | flows |  |
| 134 | "A one-tenant deployment of this contract was run…" | pre-release | flows |  |
| 135 | "The record, tokens left out, is `docs/reports/queues-2026-10-27.md`." | pre-release | flows |  |
| 136 | "Runner config:" | pre-release | flagged | A label fragment ("Runner config:") standing alone; the config items arrive without a hand-off |
| 137 | "`token_env` is for a runner started from a…" | pre-release | flows |  |
| 138 | "A runner installed as a system service gets…" | pre-release | flows |  |
| 139 | "When both are set, a non-empty `token_env` variable…" | pre-release | flows |  |
| 140 | "Why it fits so well it feels designed…" | pre-release | flagged | A lead-in fragment ("Why it fits so well it feels designed") with no verb; the pitch it heads arrives as separate bold items |
| 141 | "**HTTP polling API.** The runner long-polls over HTTPS…" | pre-release | flows |  |
| 142 | "The polling loop gets *simpler*, not more complex." | pre-release | flows |  |
| 143 | "**Retries and dead-letter queues.** Email's at-least-once story is…" | pre-release | flows |  |
| 144 | "**Batches.** The runner can pull up to 100…" | pre-release | flows |  |
| 145 | "Throughput goes from "fine" to "don't think about…" | pre-release | flows |  |
| 146 | "**API-token auth gives the queue its own identity…" | pre-release | flows |  |
| 147 | "The identity story gets *better* than email, not…" | pre-release | flows |  |
| 148 | "**It's cheap to the point of irrelevance.** A…" | pre-release | flows |  |
| 149 | "**Edge presence.** The queue lives milliseconds from wherever…" | pre-release | flows |  |
| 150 | "The shape of it: one Durable Object per…" | pre-release | flows |  |
| 151 | "The SI's `send_job --to-queue` posts a signed envelope…" | pre-release | flows |  |
| 152 | "The runner leases it, executes, posts the signed…" | pre-release | flows |  |
| 153 | "The SI reads it with `send_job results --from-queue`." | pre-release | flows |  |
| 154 | "Everything else — the JSON, the signatures, the…" | pre-release | flows |  |
| 155 | "You could run email and the queue *side…" | pre-release | flows |  |
| 156 | "The pitch, if you need one for the…" | pre-release | flows |  |
| 157 | "Queues give it a spine."*" | pre-release | flows |  |
| 158 | "---" | pre-release | flagged | A horizontal rule — structure, not a sentence |
| 159 | "The NATS transport extension ships a minimal core-NATS…" | pre-release | flows |  |
| 160 | "No JetStream, no clustering, no persistence." | pre-release | flows |  |
| 161 | "Jobs arrive on `homing-pigeon.jobs` (config `transport_nats.subject`) as the…" | pre-release | flows |  |
| 162 | "Results publish to `homing-pigeon.results.<job_id>` (`transport_nats.result_subject_prefix`)." | pre-release | flows |  |
| 163 | "The extension holds one persistent connection: subscribe, deliver…" | pre-release | flows |  |
| 164 | "The result file moves only after the broker…" | pre-release | flows |  |
| 165 | "A `-ERR`, or no PONG, leaves the file,…" | pre-release | flows |  |
| 166 | "A dead connection is re-established with backoff; the…" | pre-release | flows |  |
| 167 | "Broker authentication is required by default: user/password or…" | pre-release | flows |  |
| 168 | "With no credentials the extension refuses to start…" | pre-release | flows |  |
| 169 | "Core NATS is a dumb pipe: it does…" | pre-release | flows |  |
| 170 | "A job published while no runner is subscribed…" | pre-release | flows |  |
| 171 | "At-least-once rests on the sender re-sending jobs it…" | pre-release | flows |  |
| 172 | "NATS describes itself as "the connective tissue for…" | pre-release | flows |  |
| 173 | "This is the transport for people who think…" | pre-release | flows |  |
| 174 | "**Subject addressing maps onto the protocol like it…" | pre-release | flows |  |
| 175 | "The routing *is* the addressing scheme." | pre-release | flows |  |
| 176 | "**JetStream gives you persistence, consumer groups, and ack-based…" | post-release | flows |  |
| 177 | "The runner is just a durable consumer." | post-release | flows |  |
| 178 | "**Self-host it on the pigeon-coop Pi.** NATS's entire…" | post-release | flows |  |
| 179 | "Your always-on Pi becomes the message backbone for…" | post-release | flows |  |
| 180 | "**Microsecond latency** for those who care (you won't…" | post-release | flows |  |
| 181 | "The tradeoff: you're operating infrastructure now." | post-release | flows |  |
| 182 | "If "I run my own NATS cluster" sounds…" | post-release | flows |  |
| 183 | "If it sounds like a pager going off,…" | post-release | flows |  |
| 184 | "The file transport extension is a watched folder…" | pre-release | flows |  |
| 185 | "A job is a file dropped in the…" | pre-release | flows |  |
| 186 | "The extension processes each file once: after the…" | pre-release | flows |  |
| 187 | "Results land in the outbox as `<job_id>.result.txt`, same…" | pre-release | flows |  |
| 188 | "A redelivered copy of a finished job is…" | pre-release | flows |  |
| 189 | "A result still set aside under the channel's…" | pre-release | flows |  |
| 190 | "Refusals mirror the local-inbox discipline: symlinks are refused…" | pre-release | flows |  |
| 191 | "Its first gate is the inbox folder's OS…" | pre-release | flows |  |
| 192 | "The signature is the second gate (see "Authorization…" | pre-release | flows |  |
| 193 | "The DTLS transport extension is not a store-and-forward…" | pre-release | flows |  |
| 194 | "**Off unless enabled, and it listens.** Add `"dtls"`…" | pre-release | flows |  |
| 195 | "This is the one shipped transport that opens…" | pre-release | flows |  |
| 196 | "**One profile, enforced.** DTLS 1.3, one ciphersuite (TLS_AES_256_GCM_SHA384),…" | pre-release | flows |  |
| 197 | "Key exchange is `psk_dhe_ke` only: a fresh X25519…" | pre-release | flows |  |
| 198 | "A stateless cookie exchange proves the peer's address…" | pre-release | flows |  |
| 199 | "A resumption ticket records the key that authenticated…" | pre-release | flows |  |
| 200 | "**The platform payload.** The server's EncryptedExtensions carries a…" | pre-release | flows |  |
| 201 | "The pattern is lifted from IKEv2's Configuration Payload…" | pre-release | flows |  |
| 202 | "It is encrypted under the handshake traffic keys,…" | pre-release | flows |  |
| 203 | "The client core holds it until the server…" | pre-release | flows |  |
| 204 | "Disclosure is tiered by the runner's `dtls_greeting` config…" | pre-release | flows |  |
| 205 | "At `none`, the extension still rides and carries…" | pre-release | flows |  |
| 206 | "The extension is sent on every fresh handshake…" | pre-release | flows |  |
| 207 | "The SI initiates; the runner chooses what it…" | pre-release | flows |  |
| 208 | "Jobs are ordinary application messages once the session…" | pre-release | flows |  |
| 209 | "A current client still surfaces a pre-change runner's…" | pre-release | flows |  |
| 210 | "**Inside the session**, each message is the same…" | pre-release | flows |  |
| 211 | "Ack/dedup is still the protocol's seen-set — channel…" | pre-release | flows |  |
| 212 | "Results return on the session; a result that…" | pre-release | flows |  |
| 213 | "The SI re-asks on a fresh session, and…" | pre-release | flows |  |
| 214 | "A datagram that does not leave does not…" | pre-release | flows |  |
| 215 | "**The client** is `runner/cloud/send_dtls.py`: it signs exactly like…" | pre-release | flows |  |
| 216 | "Usage: `python3 runner/cloud/send_dtls.py --host <runner> [--port 20220] --secret…" | pre-release | flows |  |
| 217 | "`--wait` is how many seconds to hold the…" | pre-release | flows |  |
| 218 | "**One supervisor deviation, stated plainly:** the dtls extension…" | pre-release | flows |  |
| 219 | "A pipe that merely carries envelopes (email, file,…" | pre-release | flows |  |
| 220 | "**DTLS via email (version 3).** The same session…" | pre-release | flows |  |
| 221 | "It is defined by the local version 3…" | pre-release | flows |  |
| 222 | "A cloud SI may use it with any…" | pre-release | flows |  |
| 223 | "The draft is local — the IETF submission…" | pre-release | flows |  |
| 224 | "MQTT is the protocol your smart lightbulbs speak,…" | post-release | flows |  |
| 225 | "**QoS 1 is at-least-once delivery**, named and standardized." | post-release | flows |  |
| 226 | "The contract's hardest requirement arrives as a checkbox." | post-release | flows |  |
| 227 | "**The footprint is tiny.** Mosquitto (the reference broker)…" | post-release | flows |  |
| 228 | "The pigeon coop becomes a fully self-contained cell:…" | post-release | flows |  |
| 229 | "**Topic structure** mirrors NATS: `pigeon/jobs`, `pigeon/results`." | post-release | flows |  |
| 230 | "**TLS is table stakes**, and every serious broker…" | post-release | flows |  |
| 231 | "The vibe: your agent infrastructure has more in…" | post-release | flows |  |
| 232 | "This is the pick for the maximum-sovereignty crowd." | post-release | flows |  |
| 233 | "You probably already run Redis." | post-release | flows |  |
| 234 | "Redis Streams turns it into a perfectly good…" | post-release | flows |  |
| 235 | "**Consumer groups with pending-message tracking** — the broker…" | post-release | flows |  |
| 236 | "That's the at-least-once contract with a paper trail." | post-release | flows |  |
| 237 | "**`XREADGROUP` with `BLOCK`** is a long-poll." | post-release | flows |  |
| 238 | "Outbound-only, NAT-friendly, one TCP connection." | post-release | flows |  |
| 239 | "**Upstash (or similar) gives you Redis over HTTPS**,…" | post-release | flows |  |
| 240 | "Nobody ever got fired for putting the queue…" | post-release | flows |  |
| 241 | "It's not exciting, which is exactly its virtue." | post-release | flows |  |
| 242 | "A `jobs` table with a `status` column, polled…" | post-release | flows |  |
| 243 | "FOR UPDATE SKIP LOCKED`." | post-release | flagged | A code fragment ("FOR UPDATE SKIP LOCKED`.") split off from the sentence before it by the formatting; the thought arrives in 2 pieces |
| 244 | "Or Supabase/Neon for the hosted version." | post-release | flows |  |
| 245 | "**You can inspect the entire system with psql.**…" | post-release | flows |  |
| 246 | "**Transactions give you the at-least-once semantics for free:**…" | post-release | flows |  |
| 247 | "**LISTEN/NOTIFY** (or just short polling) wakes the runner…" | post-release | flows |  |
| 248 | "It's not fast, it's not elegant, and it…" | post-release | flows |  |
| 249 | "Some people — good people — consider that…" | post-release | flows |  |
| 250 | "For those who find polling *philosophically* offensive: a…" | post-release | flows |  |
| 251 | "Model the mailbox as one." | post-release | flows |  |
| 252 | "The SI `POST`s the signed job to the…" | post-release | flows |  |
| 253 | "The runner holds a **WebSocket** to the same…" | post-release | flows |  |
| 254 | "No polling interval, no latency floor." | post-release | flows |  |
| 255 | "**Transactional storage** inside the DO gives you the…" | post-release | flows |  |
| 256 | "The hosted queue above already runs one Durable…" | post-release | flows |  |
| 257 | "It would be the only transport on the…" | post-release | flows |  |
| 258 | "**nostr relays.** Key-based identity is *philosophically* the closest…" | post-release | flows |  |
| 259 | "Exotic, but the shape is right, and relays…" | post-release | flows |  |
| 260 | "One to watch." | post-release | flows |  |
| 261 | "**Webhooks to the SI.** Inverted direction, worth naming:…" | post-release | flows |  |
| 262 | "Transport #1.5." | post-release | flagged | A fragment verdict ("Transport #1.5."); no sentence shape and no hand-off |
| 263 | "---" | pre-release | flagged | A horizontal rule — structure, not a sentence |
| 264 | "Email, File, core NATS, DTLS and the hosted…" | pre-release | flows |  |
| 265 | "The other rows are design notes." | pre-release | flows |  |
| 266 | "| Transport | NAT-friendly | Auth story |…" | pre-release | flagged | A table header row — structure, not a sentence |
| 267 | "|---|---|---|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 268 | "| Email | poll | HMAC signature only…" | pre-release | flows |  |
| 269 | "| File | n/a (local folder) | Folder…" | pre-release | flows |  |
| 270 | "| NATS (core) | outbound connect | Broker…" | pre-release | flows |  |
| 271 | "| DTLS | no — listens (opt-in) |…" | pre-release | flows |  |
| 272 | "| Queues (hosted) | HTTPS poll | Bearer…" | pre-release | flows |  |
| 273 | "| NATS JetStream | yes | NKey/JWT |…" | post-release | flows |  |
| 274 | "| MQTT | yes | TLS + creds…" | post-release | flows |  |
| 275 | "| Redis Streams | yes | Token/password |…" | post-release | flows |  |
| 276 | "| Postgres | yes | DB creds |…" | post-release | flows |  |
| 277 | "| Durable Objects (push) | push | Token…" | post-release | flows |  |
| 278 | "On gates: a credentialed NATS deployment in its…" | pre-release | flows |  |
| 279 | "A deployment with `allow_unauthenticated: true` is not: it…" | pre-release | flows |  |
| 280 | "The hosted queue has two as well: the…" | pre-release | flows |  |
| 281 | "DTLS stands apart from the count: its session…" | pre-release | flows |  |
| 282 | "See "Authorization gates"." | pre-release | flagged | A bare section pointer ('See "Authorization gates".') after the gates discussion; a fragment with no hand-off |
| 283 | "The protocol is deliberately transport-agnostic, and transports are…" | pre-release | flows |  |
| 284 | "The contract is versioned at one — `TRANSPORT_API_VERSION…" | pre-release | flows |  |
| 285 | "A transport extension is a folder with an…" | pre-release | flows |  |
| 286 | "`entry` is the argv the runner launches (tokens…" | pre-release | flows |  |
| 287 | "`capabilities` says what the code does -- `network`,…" | pre-release | flows |  |
| 288 | "`startup_settle_ms` (an integer, 0 to 5000, default 0)…" | pre-release | flows |  |
| 289 | "The manifest's identity fields — name, publisher, version…" | pre-release | flows |  |
| 290 | "What it has is the extension review ([docs/extend/extensions.md](extensions.md),…" | pre-release | flows |  |
| 291 | "Under the default `extension_review: "enforce"` a folder that…" | pre-release | flows |  |
| 292 | "**Registration is never a permission to run.** Drop…" | pre-release | flows |  |
| 293 | "That is deliberate — test transports, private experiments,…" | pre-release | flows |  |
| 294 | "A folder in the extensions directory shadows a…" | pre-release | flows |  |
| 295 | "First-party extensions ship under `runner/transport_extensions/` and are found…" | pre-release | flows |  |
| 296 | "A manifest declaring any `api_version` other than 1…" | pre-release | flows |  |
| 297 | "A transport can bring its own sources for…" | pre-release | flows |  |
| 298 | "All five shipped transports declare their own code…" | pre-release | flows |  |
| 299 | "The runner supervises each enabled extension as a…" | pre-release | flows |  |
| 300 | "One extension's death never takes the runner or…" | pre-release | flows |  |
| 301 | "Each extension is handed a runtime config file…" | pre-release | flows |  |
| 302 | "Verification is the core's job, not the pipe's." | pre-release | flows |  |
| 303 | "The extension's own output lands in `<channel>/extension.log`." | pre-release | flows |  |
| 304 | "The pipe itself is a pair of directories,…" | pre-release | flows |  |
| 305 | "`inbox/` — job envelopes, extension → runner." | pre-release | flows |  |
| 306 | "An envelope is a subject line, a blank…" | pre-release | flows |  |
| 307 | "`outbox/` — result envelopes, runner → extension, same…" | pre-release | flows |  |
| 308 | "A second result written while that file is…" | pre-release | flows |  |
| 309 | "It is the same ident: the pipe correlates…" | pre-release | flows |  |
| 310 | "When the core knows the job's validated `reply_to`,…" | pre-release | flows |  |
| 311 | "A pipe cannot always read the address out…" | pre-release | flows |  |
| 312 | "An extension that does not read the sidecar…" | pre-release | flows |  |
| 313 | "Ack is consumption: whichever side has taken a…" | pre-release | flows |  |
| 314 | "The runner moves an inbox file only when…" | pre-release | flows |  |
| 315 | "A result that did not land, or a…" | pre-release | flows |  |
| 316 | "A rejection is consumed, so poison is not…" | pre-release | flows |  |
| 317 | "The runner services each channel once per poll…" | pre-release | flows |  |
| 318 | "The blob does not change between transports." | pre-release | flows |  |
| 319 | "The signatures do not change." | pre-release | flows |  |
| 320 | "The Oracle does not know the difference. (v1…" | pre-release | flows |  |
| 321 | "Result routing travels with the job." | pre-release | flows |  |
| 322 | "A signed job may name where its result…" | pre-release | flows |  |
| 323 | "Without one, the result returns over the transport…" | pre-release | flows |  |
| 324 | "The transport never invents a destination." | pre-release | flows |  |
| 325 | "Email is the pipe to turn on first:…" | pre-release | flows |  |
| 326 | "The file transport needs nothing else — set…" | pre-release | flows |  |
| 327 | "NATS needs a broker you run (or one…" | pre-release | flows |  |
| 328 | "The hosted queue needs a Worker you deploy…" | pre-release | flows |  |
| 329 | "The `transports` config key (or `--transports` for one…" | pre-release | flows |  |
| 330 | "What is not built is listed in docs/FUTURE.md;…" | pre-release | flows |  |
| 331 | "An earlier revision specified a loopback-TCP test transport…" | pre-release | flows |  |
| 332 | "It was cut along with the other broker…" | pre-release | flows |  |
| 333 | "This section is kept as a record of…" | pre-release | flows |  |
