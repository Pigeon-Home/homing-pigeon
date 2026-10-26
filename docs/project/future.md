
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

- **Supply chain.** Installer verifies `SHA384SUMS` and Sigstore attestation

- **POSIX ACL warning.** `--posture` warns when a Windows ACL is
  missing but not when a POSIX one is.

- **Credentials encrypted at rest.** `config.json` holds the shared
  secret and the mailbox credential in the clear.

- **A signing key for the Oracle**, so its opinion can be a signed
  statement from an authenticated party. `docs/oracle/job-review.md`.

- **A firewall ruleset hash**, and a check after each job that its
  network cage held. Only the on/off posture line exists.

- **Post-quantum DTLS.** A hybrid key exchange for the DTLS binding,
  whose X25519 ephemeral is the one quantum-exposed piece (DRU; draft
  Section 22.1).

- **Ed25519 signatures** instead of the shared HMAC secret, so a leaked
  secret is not root. `docs/design/asymmetric-signing-design.md`.

- **Board delegation over ping** Ping reply carries the box's open task
  board, so the cloud SI can submit work.
  
- **Other** A distributed ledger for file flow and boards, answers,
  onion, or BitTorrent and/or blockchain execution broker with embed
  wallet.
  
- **An Oracle dashboard** on loopback, to "watch" it think

- **Patch level and disk encryption as senses.**

- **TLS inspection and WAF.** sensor extensions
