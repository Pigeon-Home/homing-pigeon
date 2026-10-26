
- **Runner integrity.** Nothing checks that `runner.py` or the binary
  is unchanged at startup, so a job running as the runner's user can
  patch it. Start with a self-digest logged at start and a WARN when it
  changes; end with a read-only install.

- **Audit log integrity.** `security-events.jsonl` is rewritten past
  5,000 lines and `security-audit.jsonl` has no hash chain, no append-only
  flag and no remote copy, so the watched user can edit history.

- **A cage off Linux.** Only bwrap stops a job; macOS, FreeBSD and
  Windows detect a bad write after it happens. Needed: `sandbox-exec`, a
  jail, a job object with a restricted token, and in the meantime a POSIX
  ACL set when the workdir is handed to `job_user`.

- **Egress control.** A job can `curl` secrets out unless bwrap is in
  enforce mode on Linux. Per-job egress rules, and anything off Linux, do
  not exist. `docs/use/networking.md`.

- **A policy for the Oracle's own tool calls.** They are logged but
  nothing bounds what the Oracle may do with its tools.

- **Supply chain.** The installer verifies neither `SHA384SUMS` nor
  the Sigstore attestation, and installs Ollama with `curl | sh`.

- **POSIX ACL warning.** `--posture` warns when a Windows ACL is
  missing but not when a POSIX one is.

- **Ed25519 signatures** instead of the shared HMAC secret, so a leaked
  secret is not root. `docs/design/asymmetric-signing-design.md`.

- **An approval gate**: the owner says yes before a job runs.
  `docs/design/approval-gate-design.md`.

- **Credentials encrypted at rest.** `config.json` holds the shared
  secret and the mailbox credential in the clear.

- **A signing key for the Oracle**, so its opinion can be a signed
  statement from an authenticated party. `docs/oracle/job-review.md`.

- **A firewall ruleset hash**, and a check after each job that its
  network cage held. Only the on/off posture line exists.

- **Post-quantum DTLS.** A hybrid key exchange for the DTLS binding,
  whose X25519 ephemeral is the one quantum-exposed piece (DRU; draft
  Section 22.1).

## Not built for runner job task board

- **Board delegation over ping** (DRU, 2026-10-20). A ping's reply
  carries the box's open task board, so the cloud SI can submit work to a
  box it has just proven reachable. Only for the secret holder, only when
  the operator enables it for that sender, encrypted like a result. To be
  written as a separate IETF draft, not a protocol version.

- **Other pipes.** A distributed ledger for file flow and board
  answers, or a transport over .onion or BitTorrent.

## Not built: the Oracle, the senses, and paging

- **Richer repairs.** The Oracle fixes one thing today, an absent
  interpreter. More mechanical repairs, each stated in the result.

- **An Oracle dashboard** on loopback, to watch it think. Only the
  chat page (`--oracle`) and the CLI (`--oracle-cli`) exist.

- **Patch level and disk encryption as senses.**
  `docs/extend/senses.md`.

- **TLS inspection and a WAF.** `docs/use/networking.md`.
