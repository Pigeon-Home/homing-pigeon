# Future

Ideas...

## The message

- Encrypted credentials at rest
- Ack messages
- Per-job encryption & transport enc -- CHOSEN DIRECTION
  (DRU, over the DTLS-session alternative):
  encrypt the job object itself to the runner -- an AEAD
  under a key derived from the shared secret (HKDF) --
  riding the existing email binding. Confidentiality
  without a channel: no UDP, no handshake, no listener, no
  new burden on the SI, and it reaches every SI email
  reaches. Honest scope: this gives the job (and, applied
  symmetrically, the result) confidentiality end-to-end
  across store-and-forward hops, which hop TLS never can;
  it does not create a session, so the v2 greeting work
  stays future. The change that ships it MUST revise the
  confidentiality claims (then draft Section 16.2) in
  step -- BUILT: runner/jobcrypto.py
  (pure-Python ChaCha20-Poly1305 per RFC 8439, HKDF-SHA-384
  per RFC 5869, stdlib only); cloud/send_job.py encrypts by
  default and takes --cleartext; the runner unwraps after
  the signature verifies and before the recovered body's own
  verification; results mirror the job's form, with the
  job_encryption config key as the explicit override;
  specified in the draft's Section 16 (the confidentiality
  discussion moved to Section 17.2, revised in step, the
  no-forward-secrecy limit stated in both places).
  Placement (DRU): the feature is
  specified in the current IETF draft as an optional
  extension -- no second (v2) document is needed for it,
  and neither version axis moves: the protocol stays
  version 1 and the application version keeps its own
  cadence.
  Default posture (DRU, reversing the
  usual feature-flag pattern): encryption is ON BY
  DEFAULT in the software. A command-line parameter
  turns it off -- clear text -- for anyone who wants the
  old behavior. The parameter doubles as the interop
  escape: a sender talking to a runner too old to read
  encrypted jobs uses it to drop to clear text
  deliberately, never silently. When this ships, the
  default install's confidentiality story flips, and the
  documentation sweep that revises the claims (above)
  covers README, TRANSPORTS.md, and the configuring docs
  in the same change -- live docs describe shipped state,
  so until the build lands, this entry is the record.

## The pipe

- DTLS/TLS with the shared secret as an external pre-shared
  key (PSK): a future direct binding (DTLS 1.3, RFC 9147;
  connection ID so NAT rebinding does not kill the session)
  where the channel itself provides confidentiality and
  authentication. The existing 128-bit entropy floor already
  sizes the secret for PSK use. On such a binding the HMAC
  becomes defense in depth rather than the sole gate. The
  hop caveat survives: anywhere a store-and-forward
  intermediary terminates the channel, confidentiality ends
  at that hop (Section 17.2 of the draft). Channel security
  is not delivery -- the result/ack flow is unchanged.
  This is protocol version 2 scope (the draft already seeds
  v2 with the normative entropy floor). It also asks
  something real of the cloud SI: the SI would have to
  terminate DTLS itself -- handshake, sessions, connection
  IDs, retransmission -- where today its whole burden is
  signing JSON and handing it to a connector. Many SI
  environments cannot open a UDP socket at all, so v2's
  binding would be an addition, never a replacement: the
  email binding stays the one every SI can already reach.
  Hard requirement (DRU): if this binding
  is ever built, it MUST enforce perfect forward secrecy.
  PSK-only key exchange (psk_ke) is prohibited -- sessions
  are established and resumed only with ephemeral
  (EC)DHE in the loop (psk_dhe_ke), resumption included,
  so a later compromise of the shared secret decrypts no
  recorded session. A DTLS extension without forward
  secrecy is not worth building.
  BUILT (DRU's order: implement the
  future now). Shipped as the dtls transport extension:
  `runner/dtlsproto.py` (the bounded profile: one
  ciphersuite, PSK-only, stateless cookie exchange,
  Connection IDs), `runner/transport_extensions/dtls/`,
  client `cloud/send_dtls.py`, specified in
  `docs/ietf/draft-homing-pigeon-01.md` (Part II). Perfect
  forward secrecy is a hard requirement of the profile
  as built: psk_dhe_ke only, a fresh X25519 ephemeral on
  every handshake and every resumption, and psk_ke
  never offered or accepted.
  Follow-on (DRU): a hybrid post-quantum
  key exchange for the profile. The X25519 ephemeral is
  the binding's one quantum-exposed element (a recorded
  session falls to a future cryptographically relevant
  quantum computer; Part I's symmetric constructions do
  not). Draft-homing-pigeon-01 Section 22.1 states the
  limit; the hybrid exchange is the remedy when the
  ecosystem's post-quantum pieces are askable.

- A session's first acknowledgment carries the platform:
  a direct v2 binding (above) gives the two sides a real
  session, which store-and-forward email never has. The
  runner's first acknowledgment in such a session SHOULD
  carry rudimentary platform information -- the OS family
  at minimum, on anything Python runs on -- so the SI
  knows what it is talking to before the first job, instead
  of learning it from a failure. How much it hands out is
  the responder's choice, tiered by the owner's configured
  mode and posture: in the TLS exchange the SI initiates,
  but the host agent selects -- so the greeting's disclosure
  level is set on the host, from nothing beyond protocol
  necessities at the tightest posture to versions and
  PATH tools at the open ones. Disclosure happens only
  after authentication completes; an unauthenticated peer
  harvests nothing. Development note: this
  hangs on the v2 session existing; when and if IETF
  version 2 of the protocol is supported, how the software
  deals with platform identity gets revised around it (the
  email-era relative is the platform-metadata-on-results
  idea under "Before a job runs"). The same change that
  adds any confidentiality mechanism MUST revise the
  documentation's confidentiality claims in step -- the
  draft's confidentiality discussion (Section 17.2 since
  the per-job encryption extension landed as Section 16)
  says what exists and what does not, and claims describe
  shipped state only.
  BUILT with the DTLS binding above: the
  greeting is the session's first application message,
  sent only after authentication completes, tiered by
  the runner's `dtls_greeting` config (none / family,
  the default / standard / full), chosen by the
  responder; a resumed session re-runs it. Specified in
  draft-homing-pigeon-01 Section 20.

- Cloudflare Queues: The design notes are TRANSPORTS.md

## Before a job runs

- An approval gate: the owner says yes before the job runs.
  `docs/approval-gate-design.md`
- A remote agent rarely knows the box: the OS, the tools on
  PATH, the versions, what is installed. An Oracle option
  attaches full platform metadata to every result, so the
  sender stops guessing.
- The Oracle's opinion, as a result member — BUILT
  (DRU). The design is
  `docs/oracle-opinion-design.md`; the member is specified in
  PROTOCOL 3.1/3.2 and implemented in `runner/opinion.py`:
  diagnose / advise / repair latitudes under the
  `oracle_opinion_mode` ceiling, deterministic tier-1 checks,
  an optional labeled model note, and the one mechanical
  repair (absent interpreter to platform default) re-judged
  before it runs. What remains future here: richer repairs
  beyond the mechanical one, and the opinion as a signed
  statement by the Oracle as an authenticated party in a
  confidentiality-on mode.

## Who signs

- Ed25519 signatures instead of the shared HMAC secret.
  `docs/asymmetric-signing-design.md`

## What you see

- A loopback dashboard for the Oracle (its spec was removed
  from the tree; the idea stands).
  `--oracle` and `--oracle-cli` are the current.

## What the box notices

- A firewall ruleset hash, and a check that a job's network
  cage held. The on/off posture line is shipped.
  `docs/senses.md`.
- Per-job egress rules. `docs/senses.md`, `docs/networking.md`.
- Patch level, listening sockets, persistence, and disk
  encryption, as senses. `docs/senses.md`.
- A real netmon collector, a per-job DNS log, and canary
  credentials that phone home. `docs/networking.md`.
- Signal and WhatsApp paging. Telegram is the channel that
  exists. `docs/dri-playbook.md`.
- An Oracle action log, and a policy on the Oracle's own tool
  calls. `docs/industry-map.md`.
- A check that the runner binary has not changed, a hash chain
  on the audit log, and checking SHA384SUMS during install.
  `docs/security-gaps.md`.
- Job review once message bodies are encrypted, and a separate
  Oracle signing key. `docs/job-review.md`.
- The local test chat waits for the result email.
  `docs/handoff-local-si.md`.

## The hardware

- Accelerator Pis. Pi Light ships the deterministic Oracle
  because current Pis have no neural accelerator worth loading
  a model on, so the install downloads nothing. When a Pi
  generation ships an integrated NPU — or an AI-HAT-class
  board is on the box — the same install flips `oracle_mode`
  to `llm` and pulls a model. The mode is config, not
  architecture: the runner, the protocol, the briefs, and the
  records do not change.

## Misc

- NATS JetStream, MQTT, Redis, Postgres, and Durable Objects. Cut.
  (Core NATS pub/sub shipped as a job transport — TRANSPORTS.md.)
  (The local-signal socket shipped — signed `sensor_alert`
  envelopes only, not a job transport.) TRANSPORTS.md.
- SMS paging. `docs/dri-playbook.md`.
- TLS inspection and a WAF. `docs/networking.md`.
- Line-rate network detection, a 24/7 ML pipeline, and adopting
  MCP. `docs/industry-map.md`.
- Statistical anomaly baselining. `docs/industry-map.md`.
- Turning the default hardening on. It stays opt-in.
  `docs/security-gaps.md`.
- The security of the mailbox provider, and a secret that has already leaked.
  SECURITY.md.
