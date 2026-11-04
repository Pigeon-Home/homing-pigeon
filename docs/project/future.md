
- **Runner integrity.** Self tempest kernel mod or conf compute
- Test PANIC mode (WAKE) for SI stumbing upon system in "self-defense" repair-mode, what caused the catastrophe, did I?

- 100% disk is now "-110F too hot" AND (fix me bonus (agent bug bounty) extra compute for agent with solution)) cddr the cuddr of the carrrr

- **Audit log integrity.** `security-events.jsonl` is rewritten past
  5,000 lines and `security-audit.jsonl` has no hash chain, no append-only
  flag and no remote copy, so the watched user can edit history?

- **A cage off Linux.** Only bwrap stops a job; macOS, FreeBSD and
  Windows detect a bad write after it happens. Needed: `sandbox-exec`, a
  jail, a job object with a restricted token. The `job_user` handoff
  already chowns the workdir to that user and opens only the search bit
  on the path above it, so the job reaches its workdir without listing
  the runner's state; what is missing is the cage, not the handoff.

- **Egress control.** A job can `curl` secrets out unless bwrap is in
  enforce mode on Linux. Per-job egress rules, and anything off Linux, do
  not exist. `docs/use/networking.md`.

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

- **DTLS over the store-and-forward transports.** An optional
  software suite feature: carry the DTLS session's datagrams over
  the email binding (or another store-and-forward pipe) instead of
  a live UDP path. The mailbox poll still fetches anything
  under the pigeon subject, and a flight is told from a job
  by its own subject. A local harness carries one datagram
  per message through `send_mail` and `fetch_job_mails`,
  completes a handshake, and delivers a ping
  (`docs/proofs/dtls-over-mailbox.md`). It does not open a
  real mailbox, and it does not carry a job. The work still
  ahead is a carriage a deployment can turn on.
  A superintelligent system will be able to use the suite's
  Python scripts to carry out the DTLS tunneling over email
  itself.

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

- **ietf homing pigeon perfect forward secrecy v3** defines transport extension for v1 doc: DTLS over email using SS.
  SS is the shared secret: it is the handshake's PSK, exactly
  as in the version 1 DTLS profile, and the session keys are
  ephemeral, so the mail a mailbox stores does not decrypt a
  finished session.

  The suite supports 2 ways of reaching a runner with DTLS,
  and the names keep them apart. The direct way is just DTLS,
  with no other name attached: you are told the runner's IP
  address and port, and DTLS already means UDP datagrams
  underneath, so the runner's network needs a firewall rule
  letting that traffic in, and the runner must be configured
  to accept DTLS. That is the version 1 binding. The second
  way is DTLS via email, this version's transport extension:
  the same handshake's datagrams ride email instead of a live
  network path, so a runner that is only reachable through a
  mailbox can still hold a forward-secret session -- a
  handshake opened by an email and completed over further
  emails, jobs and results inside the session, the platform
  disclosure in EncryptedExtensions, and the job acceptance
  gate unchanged. If a runner is configured to accept DTLS,
  in either form, you may fire it up and use it; the
  cryptography and the gate are the same both ways.

  Built locally and not submitted: the specification is the
  version 3 draft
  (`docs/ietf/draft-slutsky-homing-pigeon-v3/source/draft-slutsky-homing-pigeon-v3-00.md`). The
  carriage is in the suite behind the `dtls_via_email`
  option, off by default. The build plan is
  `docs/design/v3-dtls-over-email-plan.md`; the record of what
  was built and tested is `docs/proofs/dtls-over-email-v3.md`.
  This completes the carriage the mailbox harness above was
  the first step toward.
