
- **Runner integrity.** Nothing checks that `runner.py` or the binary
  is unchanged at startup, so a job running as the runner's user can
  patch it. Start with a self-digest logged at start and a WARN when it
  changes; end with a read-only install.

- **Audit log integrity.** `security-events.jsonl` is rewritten past
  5,000 lines and `security-audit.jsonl` has no hash chain, no append-only
  flag and no remote copy, so the watched user can edit history.

- **A cage off Linux.** Only bwrap stops a job; macOS, FreeBSD and
  Windows detect a bad write after it happens. Needed: `sandbox-exec`, a
  jail, a job object with a restricted token. The `job_user` handoff
  already chowns the workdir to that user and opens only the search bit
  on the path above it, so the job reaches its workdir without listing
  the runner's state; what is missing is the cage, not the handoff.

- **Egress control.** A job can `curl` secrets out unless bwrap is in
  enforce mode on Linux. Per-job egress rules, and anything off Linux, do
  not exist. `docs/use/networking.md`.

- **Supply chain.** The installer verifies `SHA384SUMS` and the Sigstore
  attestation itself. Today the release carries both and
  `docs/security/verification.md` gives a person the commands;
  `install.py` checks nothing it downloads, and fetches Ollama with
  `curl | sh`.

- **POSIX ACL warning.** `--posture` reads the Windows DACL and warns
  when Everyone, Users or Guests can read a secret file. On POSIX it
  checks only the mode bits (0600 or a warning) and never reads a POSIX
  ACL, so a `+` entry granting another user read passes as 0600.

- **Credentials encrypted at rest.** `config.json`, or the
  `shared_secret_file` it points at, holds the shared secret in the
  clear, and the mailbox app password or the OAuth refresh token and
  client secret sit beside it the same way.

- **A signing key for the Oracle**, so its opinion can be a signed
  statement from an authenticated party. `docs/oracle/job-review.md`.

- **A firewall ruleset hash**, and a check after each job that its
  network cage held. Only the on/off posture line exists.

- **Post-quantum DTLS.** A hybrid key exchange for the DTLS binding,
  whose X25519 ephemeral is the one quantum-exposed piece (DRU; draft
  Section 22.1).

- **Ed25519 signatures** instead of the shared HMAC secret, so a leaked
  secret is not root. `docs/design/asymmetric-signing-design.md`.

- **An approval gate (M10)**, a human yes before a job runs, for the
  jobs a policy names. `docs/design/approval-gate-design.md`.

- **Board delegation over ping** Ping reply carries the box's open task
  board, so the cloud SI can submit work.
  
- **Other** A distributed ledger for file flow and boards, answers,
  onion, or BitTorrent and/or blockchain execution broker with embed
  wallet link key_id.

- **Cyber "Turret"** for malicious actors/swarms
  
- **An Oracle dashboard** on loopback, to "watch" it think

- **Patch level and disk encryption as senses.**

- **TLS inspection and WAF.** extensions?

