# Future

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 (this edition, 2026-10-25) -->

Ideas worth building, with the reasoning behind each, and the record
of the decisions that shaped the ones already built. The only list of
work that is not built. If one grabs you, the linked design note says
where to start.

Sections are lettered and items numbered so an item can be named in
one breath (C2, F2). Status is per section: A is shipped and kept for
the record, B has a slice built, C through F are not built, G was cut.
An item moves between sections when its status changes; its number
moves with it and the old number is not reused.

## A. Finished, kept for the record

**A1. Per-job encryption, over the existing email binding.** Chosen
direction (DRU, over the DTLS-session alternative): encrypt the job
object itself to the runner, an AEAD under a key derived from the
shared secret, so confidentiality rides every pipe an SI can reach,
with no session, no listener and no new burden on the SI. Honest
scope: end-to-end across store-and-forward hops, which hop TLS never
gives; it does not create a session and has no forward secrecy.
Decisions of record (DRU): specified in the current draft (Section
16) as a protocol requirement, no second document, neither version
axis moves; and encryption is ON by default, with `--cleartext` as
the explicit, never silent, way down for an older runner. Built:
`runner/wire/jobcrypto.py` (AES-256-GCM, HKDF-SHA-384, stdlib only),
`send_job.py` encrypts by default, results mirror the job's form with
`job_encryption` as the override. Live docs describe the shipped
state; this entry is the decision.

**A2. DTLS 1.3 with the shared secret as the external PSK.** A direct
binding of protocol version 1 where the channel gives confidentiality
and authentication and the HMAC becomes defense in depth. An addition,
never a replacement: many SI environments cannot open a UDP socket,
and the SI would have to terminate DTLS itself. Hard requirement
(DRU): perfect forward secrecy, `psk_dhe_ke` only, `psk_ke` never
offered; a DTLS extension without it is not worth building. Built as
the dtls transport extension: `runner/wire/dtlsproto.py` (one
ciphersuite, stateless cookies, Connection IDs), `runner/transport_extensions/dtls/`,
client `runner/cloud/send_dtls.py`, draft Sections 19 to 22. The
follow-on is C13.

**A3. The session's first acknowledgment carries the platform.** The
DTLS session gives a real first message, so the runner greets with
what the SI needs before the first job: OS family at the tightest
posture, versions and PATH tools at the open ones, chosen by the
responder, sent only after authentication. Built with A2: the
`dtls_greeting` tiers (none, family, standard, full), re-run on
resumption, draft Section 20. The same card now rides a ping's result
(B6).

**A4. The Oracle's opinion as a result member.** Built (DRU):
`docs/design/oracle-opinion-design.md`, PROTOCOL 3.1 and 3.2,
`runner/oracle/opinion.py`: diagnose, advise and repair latitudes
under the `oracle_opinion_mode` ceiling, deterministic tier-1 checks,
an optional labeled model note, and the one mechanical repair (absent
interpreter to platform default), re-judged before it runs. What
remains is E1 and C11.

**A5. One declaration, not three.** Resolved 2026-10-22, the day it
was filed: the manifest's `upstream` block is the one declaration.
`fetch_upstream.py` keeps the pinned files for the build and the
drift tests, `extsources.py` hands the same files to the Oracle as
`pinned` under the recorded digests, and a `sources.json` entry says
`"upstream": true` to fetch more. `upstream.json`, the provenance
bundles and `vendor_upstreams.py` were retired. A pin bump touches
one file.

**A6. Job review once bodies are encrypted.** Built:
`runner/oracle/review.py`, and bodies are encrypted by default. The
separate Oracle signing key the same entry asked for is C11.

**A7. The local test chat.** The whole exchange on one box, acting as
the cloud SI in-process and reading the result directly; no mail is
sent. `--local-test`; `docs/archive/handoff-local-si.md`.

**A8. The firewall posture line.** On or off, with the T1562.004
change alert, shipped. The ruleset hash and the cage-held check are
C12.

## B. Partial: a slice is built

**B1. Cloudflare Queues.** The hosted queue ships
(`docs/extend/transports.md`, "Queues"): a Worker and one Durable
Object per tenant at `runner/cloud/queues-worker/`, a bearer token per
role, the HMAC-SHA-384 gate at the edge on by default
(`REJECT_INVALID_HMAC`), a per-tenant quota, the runner's `queues`
transport and `send_job.py --to-queue`. The Cloudflare Queues product
itself and D1 storage remain design notes.

**B2. Mirror** (DRU's coinage, 2026-10-20). The result carries the
Oracle's full decision context home to the cloud SI, and a light
Oracle sends the question it would have asked itself UP, with its
context, the answer returning signed, the local default deciding when
none comes by the deadline. Trust is the design: mirror flows only to
the holder of the shared secret, only when the operator enables it for
that sender, encrypted and bounded like everything else; the general
form lets any component append its signed, provenance-carrying,
seen-once segment to a shared context. Refined the same day (DRU): a
determination travels BEFORE the job executes, as its own message,
triggered by the box's determination not being a clean pass, never by
a request in the job; the cloud SI adapts to the version the endpoint
speaks, falling back to version 1 with no negotiation. Built: the
determination / question / answer slice as protocol version 2,
`runner/wire/protocol_v2.py`, off unless `protocol_v2` is set,
`answer_only` as the laptop mode; the draft is
`docs/ietf/draft-homing-pigeon-v2-00.md`. Not built: the Oracle's full
context on results, extension segment kinds, and the red-team
concentrate (D3).

**B3. Extension sources.** Shipped (`runner/ops/extsources.py`,
`docs/extend/extensions.md` "Sources"). Three follow-ups are not:
verifying an upstream's own release signature (a `.asc` beside the
tarball) where one is published, since today's pin proves the box got
the bytes the build saw, not that the upstream signed them; resolving
the upstream version installed on the box rather than the latest at
build, so the Oracle reads the source that matches the running
daemon; and source cards (names, versions, licenses, never content) in
the `senses` answer, so a cloud SI knows what the box's Oracle can
read.

**B4. Reviewer routing on the task board.** PROTOCOL 13.4 once
described the Oracle dealing a finished `task_result` to a second
worker holding `review` before the human gate; it was not built (spec
corrected 2026-10-21). What ships is the human gate alone:
`require_review` parks the task in `pending_review` until the owner
approves (13.7). Routing to reviewing workers remains an idea.

**B5. Platform metadata for the sender.** A remote agent rarely knows
the box. Built: a `ping` result carries the platform card at the
owner's `pong_platform` tier (PROTOCOL 3.2), so the SI learns the OS
family, the default interpreter and the protocol versions before the
first real job. Not built: the option that attaches full platform
metadata to every result.

**B6. Senses for the box's own posture.** Built as shipped senses:
listening sockets (`port-watch`), the services that should be running
(`service-watch`), and the local canary tripwire (`inference.watch_system`,
on by default). Not built: patch level and disk encryption as senses,
canary credentials that phone home when used elsewhere, a real netmon
collector beyond the softflowd, Zeek and Suricata feeds, and a per-job
DNS log. `docs/extend/senses.md`, `docs/use/networking.md`.

**B7. Accelerator Pis.** Pi Light ships the deterministic Oracle
because current Pis have no neural accelerator worth loading a model
on, so the install downloads nothing. When a Pi generation ships an
integrated NPU, or an AI-HAT-class board is on the box, the same
install flips `oracle_mode` to `llm` and pulls a model. The mode is
config, not architecture: nothing else changes. The hardware side of
this is F1.

## C. Not built: security

The order follows `docs/security/security-gaps.md`: the default
posture is the owner's choice and flipping it closes none of these,
because each is a mechanism that does not yet exist.

**C1. Runner integrity.** Nothing checks that `runner.py` or the
binary is unchanged at startup; a same-user job can patch the runner
and own every later run. The smallest form is a self-digest logged at
start and a WARN when it differs from the last start's; the real form
is a read-only install directory.

**C2. Audit log integrity.** `security-events.jsonl` is rewritten
past 5,000 lines, so the watched principal can edit history;
`security-audit.jsonl` is append-only in the runner's hands but has no
hash chain, no `chattr +a`, and no remote copy.

**C3. A cage off Linux.** bwrap is the only enforcement. On macOS,
FreeBSD and Windows the workspace sweeps detect after the fact. The
real cages are `sandbox-exec`, a jail, and a job object with a
restricted token; the interim is the POSIX ACL (`setfacl`, `chmod +a`)
set at the moment the workdir is chowned for `job_user`, never from
anything in the signed job.

**C4. Egress control.** Exfiltration from inside a job is blocked only
by bwrap in enforce mode. Per-job egress rules, and anything off
Linux, do not exist. `docs/use/networking.md`.

**C5. A policy on the Oracle's own tool calls.** The action log
exists (the oracle log records every tool call); a policy that bounds
what the Oracle may do with its tools does not.
`docs/project/industry-map.md`.

**C6. Supply chain.** Releases ship `SHA384SUMS` and a Sigstore
attestation, but the installer verifies neither, and the Ollama step
is `curl | sh`. Verify the sums on install; pin and hash the Ollama
script.

**C7. The posture report's POSIX ACL warning.** `--posture` warns
about a missing Windows ACL and not about a missing POSIX one.

**C8. Ed25519 signatures instead of the shared HMAC secret**, so a
leaked secret is not root. `docs/design/asymmetric-signing-design.md`.

**C9. An approval gate**: the owner says yes before the job runs.
`docs/design/approval-gate-design.md`.

**C10. Credentials encrypted at rest.** `config.json` holds the
shared secret and the mailbox credential in the clear.

**C11. A separate Oracle signing key**, and the opinion as a signed
statement by the Oracle as an authenticated party in a
confidentiality-on mode. `docs/oracle/job-review.md`.

**C12. A firewall ruleset hash, and a check that a job's network
cage held.** The on/off line is A8. `docs/extend/senses.md`.

**C13. A hybrid post-quantum key exchange for the DTLS profile**
(DRU). The X25519 ephemeral is the binding's one quantum-exposed
element; the core protocol's symmetric constructions are not. Draft
Section 22.1 states the limit; the hybrid exchange is the remedy when
the ecosystem's post-quantum pieces are askable.

## D. Not built: the protocol and the board

**D1. Cloud task-board delegation** (DRU, 2026-10-20). The ping a
sender already spends to learn the box is reachable returns the job
board with the pong, so the cloud SI sees that box's open work and may
submit a task to a board it has just proven it can reach. Same trust
boundary as Mirror: only the holder of the shared secret, only when
the operator enables it for that sender, the view bounded and
encrypted like a result; a ping the operator has not opened stays a
pong. Placement (DRU): NOT a version of the base specification; a
separate IETF draft riding the current protocol, whether or not it
later folds in as a version. The irony is part of the record: the
optimization trusts the cloud SI with fuller control and is also the
more advanced system, designed for more restricted hardware. That is
the industry pattern: build the big chunky crypto and security system
first, then design the lightweight optimized version alongside it.

**D2. Ack messages.** The board's `task_ack` ships (PROTOCOL 13.7)
and a result's attestation is a job's receipt. A receipt that
acknowledges a job before its result does not exist.

**D3. The concentrate, a third extension kind, and its first member,
the red-team concentrate** (DRU coined the kind, 2026-10-20). A sense
observes the box, a transport carries jobs; a concentrate takes
incoming jobs as its material, analyzes them before they run, and
hands back a better opinion than the job's literal text supports. Its
seat is fixed: after signature verification, before the Oracle's
opinion freezes, inside the runner, with no admission power of its
own. The red-team concentrate spends that seat adversarially: it
generates near neighbors of the job (grammar-shaped mutations,
boundary values, reordered and re-typed fields, encodings at the edge
of what the parsers accept), replays them against the deterministic
checkers and the sandbox, and hunts for the variant that flips the
verdict. It returns the opinion revised by the attack, annotated with
the flipping variant or with the searched neighborhood. Every flip
reproduces from an archived seed and the exact variant bytes; a model
may propose variants but a flip counts only when the machinery
replays it. The yield compounds through the Oracle's self-learning:
the near misses that never occur naturally are manufactured before
the fact and filed as first-class learning input. Constraints: the
deterministic tier must do the whole job on Pi Light; the budget is an
operator-tunable cost charged against the job's wait; the kind's
contract (manifest, what it may see, the shape of an annotated
opinion) is unwritten. The gentler sibling that maps a job's mutation
neighborhood without attacking the opinion was sketched in the same
conversation. The job-fuzz sense was chosen ahead of this.

**D4. A distributed ledger for file flow and the work board's answers,
or a transport extension over .onion or BitTorrent.** An idea on the
record, nothing designed.

**D5. An SI that runs a self-improvement project** by watching the
protocol and the software in motion.

## E. Not built: the Oracle, the senses, and paging

**E1. Richer repairs** beyond the one mechanical one in A4.

**E2. A loopback dashboard for the Oracle**: watch it think. Its spec
was removed from the tree; the idea stands. `--oracle` (the loopback
chat page) and `--oracle-cli` are what exists.

**E3. Patch level and disk encryption as senses.** The rest of that
family is B6.

**E4. Signal and WhatsApp paging.** Telegram is the channel that
exists. `docs/oracle/dri-playbook.md`.

**E5. TLS inspection and a WAF.** `docs/use/networking.md`.

**E6. Line-rate network detection, a 24/7 ML pipeline, and adopting
MCP.** `docs/project/industry-map.md`.

## F. Research directions: hardware

**F1. A Pi with an accelerator** is B7's hardware half: when it
exists, the install pulls a model and nothing else changes.

**F2. A neural link, or USB inference stick, for the Pi.** Research
direction, nothing built. The earlier USB inference stick idea is
largely superseded by this; PiEEG-class shields (real EEG/BCI add-ons
on GPIO, research-grade, open source) are the nearest existing thing.

Differentiation angles worth researching:
- Universal USB for any Pi, Zero through 5, not only the Pi 5 PCIe
  path: the older installed base is the market the big kits ignore.
- Not only inference: a fused peripheral (accelerator plus camera,
  mic, IMU, or a light BCI front-end) behind one signed protocol, so
  the host sees one device, not a pile of drivers.
- The Homing Pigeon fit: the peripheral is the local Oracle's muscle.
  A Pi Light gains a small model it can call; Mirror (B2) ships the
  question up when the stick is absent or the model unsure.
- Power and heat on USB 2 versus USB 3; a design useful on USB 2
  (lower TOPS, still better than CPU) wins the installed base.
- Model portability: Coral is locked to TF-Lite; a stick that runs a
  small open set (ONNX, a fixed GGUF class, or a Homing-Pigeon-signed
  model format) reduces lock-in.
- Security: the stick holds no long-term secrets; jobs that need
  inference are signed, results are signed, the stick is a
  coprocessor, not a trust root.

Research fronts to expand: what USB 2 delivers for a small model and
the latency budget for a local decision; a sealed dongle that does
not throttle under continuous inference; a census of pre-Pi-5 boards
that cannot take an M.2 AI kit; the killer demo, GLQuake's equivalent,
which for Homing Pigeon is probably "the box that was silent now has
an opinion"; the regulatory line that appears if the link leans toward
real biosignals; and company shape, the stick alone or the stick plus
a signed model subscription that runs only on it (the Glide-era
lesson: the API and the hardware travel together).

## G. Cut, or decided against

**G1. NATS JetStream, MQTT, Redis Streams, Postgres, and a real-time
Durable Objects pipe.** Cut as job transports; the design notes stay
in `docs/extend/transports.md` for the story. Core NATS pub/sub
shipped as a transport extension (the core has been transport-blind
since 3.10.0), the local-signal socket carries signed `sensor_alert`
envelopes only, and a Durable Object per tenant holds the hosted
queue's state (B1).

**G2. SMS paging.** Decided against (DRU; `runner/oracle/dri.py`).
