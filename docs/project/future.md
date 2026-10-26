# Future

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

- **B. Partial: a slice is built**
  - B1 Cloudflare Queues
  - B2 Mirror
  - B3 Extension sources, three follow-ups
  - B4 Reviewer routing
  - B5 Platform facts on every result
  - B6 More network senses
  - B7 Accelerator Pis
- **C. Not built: security**
  - C1 Runner integrity
  - C2 Audit log integrity
  - C3 A cage off Linux
  - C4 Egress control
  - C5 A policy for the Oracle's own tool calls
  - C6 Supply chain
  - C7 POSIX ACL warning
  - C8 Ed25519 signatures
  - C9 An approval gate
  - C10 Credentials encrypted at rest
  - C11 A signing key for the Oracle
  - C12 A firewall ruleset hash
  - C13 Post-quantum DTLS
- **D. Not built: the protocol and the board**
  - D1 Board delegation over ping
  - D2 Job acknowledgements
  - D3 The concentrate (red-team extension kind)
  - D4 Other pipes
  - D5 A self-improving SI
- **E. Not built: the Oracle, the senses, and paging**
  - E1 Richer repairs
  - E2 An Oracle dashboard
  - E3 Patch level and disk encryption as senses
  - E5 TLS inspection and a WAF
Not built, and nothing else; the finished items' decisions are in
`docs/archive/future-finished-2026-10-25.md`.

## B. Partial: a slice is built

**B1. Cloudflare Queues.** The hosted queue runs on a Worker and a
Durable Object per tenant. Moving it onto the Cloudflare Queues product
with D1 storage is design notes only.

**B2. Mirror.** The result carries the Oracle's full reasoning (signals,
lessons, box state) home to the cloud SI, and a light Oracle can send a
question up and act on the signed answer, or on its local default when
none arrives in time. Only the question-and-answer part exists, as
protocol version 2 (`docs/ietf/draft-homing-pigeon-v2-00.md`). The
full context on results is not built.

**B3. Extension sources, three follow-ups.** Check an upstream's own
release signature where one is published. Fetch the upstream version
installed on the box, not the latest at build. List what the Oracle
can read (names, versions, licenses) in the `senses` answer.

**B4. Reviewer routing.** A finished task goes to a second worker
holding the `review` capability before the owner sees it. Today only
the owner's approval gate exists (`require_review`).

**B5. Platform facts on every result.** A `ping` result already
carries the OS family, default interpreter and protocol versions. An
option to attach full platform metadata to every result does not exist.

**B6. More network senses.** Canary credentials that phone home when
used elsewhere, a per-job DNS log, and a netmon collector of our own.
Listening sockets, running services and local canary files are already
watched.

**B7. Accelerator Pis.** When a Pi ships with an NPU, or an AI HAT is
present, the install should pull a model and switch `oracle_mode` to
`llm`. The switch exists; nothing detects the hardware yet.

## C. Not built: security

Each is a mechanism, so changing the default posture closes none of
them. The order is `docs/security/security-gaps.md`'s.

**C1. Runner integrity.** Nothing checks that `runner.py` or the binary
is unchanged at startup, so a job running as the runner's user can
patch it. Start with a self-digest logged at start and a WARN when it
changes; end with a read-only install.

**C2. Audit log integrity.** `security-events.jsonl` is rewritten past
5,000 lines and `security-audit.jsonl` has no hash chain, no append-only
flag and no remote copy, so the watched user can edit history.

**C3. A cage off Linux.** Only bwrap stops a job; macOS, FreeBSD and
Windows detect a bad write after it happens. Needed: `sandbox-exec`, a
jail, a job object with a restricted token, and in the meantime a POSIX
ACL set when the workdir is handed to `job_user`.

**C4. Egress control.** A job can `curl` secrets out unless bwrap is in
enforce mode on Linux. Per-job egress rules, and anything off Linux, do
not exist. `docs/use/networking.md`.

**C5. A policy for the Oracle's own tool calls.** They are logged but
nothing bounds what the Oracle may do with its tools.

**C6. Supply chain.** The installer verifies neither `SHA384SUMS` nor
the Sigstore attestation, and installs Ollama with `curl | sh`.

**C7. POSIX ACL warning.** `--posture` warns when a Windows ACL is
missing but not when a POSIX one is.

**C8. Ed25519 signatures** instead of the shared HMAC secret, so a leaked
secret is not root. `docs/design/asymmetric-signing-design.md`.

**C9. An approval gate**: the owner says yes before a job runs.
`docs/design/approval-gate-design.md`.

**C10. Credentials encrypted at rest.** `config.json` holds the shared
secret and the mailbox credential in the clear.

**C11. A signing key for the Oracle**, so its opinion can be a signed
statement from an authenticated party. `docs/oracle/job-review.md`.

**C12. A firewall ruleset hash**, and a check after each job that its
network cage held. Only the on/off posture line exists.

**C13. Post-quantum DTLS.** A hybrid key exchange for the DTLS binding,
whose X25519 ephemeral is the one quantum-exposed piece (DRU; draft
Section 22.1).

## D. Not built: the protocol and the board

**D1. Board delegation over ping** (DRU, 2026-10-20). A ping's reply
carries the box's open task board, so the cloud SI can submit work to a
box it has just proven reachable. Only for the secret holder, only when
the operator enables it for that sender, encrypted like a result. To be
written as a separate IETF draft, not a protocol version.

**D2. Job acknowledgements.** A receipt that a job arrived, sent before
its result. Board messages are acknowledged; jobs are not.

**D3. The concentrate, a third extension kind** (DRU, 2026-10-20). A
sense watches the box and a transport carries jobs; a concentrate reads
an incoming verified job before it runs and hands back a better opinion
of it. It never admits or refuses. The first one is the red-team
concentrate: it mutates the job (boundary values, reordered or re-typed
fields, edge encodings), replays the variants against the checkers and
the sandbox, and reports any variant that flips the verdict, reproducibly
from the saved bytes. Those near misses feed the Oracle's learning. The
kind's manifest and contract are unwritten.

**D4. Other pipes.** A distributed ledger for file flow and board
answers, or a transport over .onion or BitTorrent. Idea only.

**D5. A self-improving SI**, running a project to improve the protocol
and the software by watching both in motion. Idea only.

## E. Not built: the Oracle, the senses, and paging

**E1. Richer repairs.** The Oracle fixes one thing today, an absent
interpreter. More mechanical repairs, each stated in the result.

**E2. An Oracle dashboard** on loopback, to watch it think. Only the
chat page (`--oracle`) and the CLI (`--oracle-cli`) exist.

**E3. Patch level and disk encryption as senses.**
`docs/extend/senses.md`.

**E5. TLS inspection and a WAF.** `docs/use/networking.md`.
