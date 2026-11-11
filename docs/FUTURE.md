# Future work and local v3 transport notes
- **Runner integrity.** Self tempest kernel mod (conf compute v2 hompo) as a self-hosted confidentially computed fuzzing-As-A-Service platform as a service platform black box dist with no infra

- Test PANIC mode (WAKE) for SI stumbing upon system in "self-defense" repair-mode, what caused the catastrophe, did I?

- 100% disk is now "-110F too hot" AND (fix me bonus (agent bug bounty) extra compute for agent with solution)) cddr the cuddr of the carrrr

- **Audit log integrity.** `security-events.jsonl` is rewritten past
  5,000 lines. `security-audit.jsonl` now carries a tamper-evident hash
  chain (verified by the audit report tool), so an edit to its history
  is detectable; what it still lacks is an append-only flag and a
  remote copy.

- **A cage off Linux.** The FreeBSD jail and the Windows job object
  with a restricted token landed as the confinement backends and were
  field-proven on 2026-11-10; the cage that is still missing is
  macOS's, where a bad write is still only detected after it happens
  and `sandbox-exec` is the named candidate. The `job_user` handoff
  already chowns the workdir to that user and opens only the search bit
  on the path above it, so the job reaches its workdir without listing
  the runner's state; off macOS what was missing was the cage, not the
  handoff, and the cage is now there.

- **Egress control.** On Linux a job can `curl` secrets out unless
  bwrap is in enforce mode; the FreeBSD jail denies a job all network,
  and the Windows backend does not restrict a job's network at all.
  Per-job egress rules do not exist on any platform.
  `docs/steady/networking.md`.

- **POSIX ACL warning.** `--posture` reads the Windows DACL and warns
  when Everyone, Users or Guests can read a secret file. On POSIX it
  checks only the mode bits (0600 or a warning) and never reads a POSIX
  ACL, so a `+` entry granting another user read passes as 0600.

- **A signing key for the Oracle**, so its opinion can be a signed
  statement from an authenticated party. `docs/steady/oracle/job-review.md`.

- **A firewall ruleset hash**, and a check after each job that its
  network cage held. Only the on/off posture line exists.

- **An approval gate (M10)**, a human yes before a job runs, for the
  jobs a policy names. `docs/steady/design/approval-gate-design.md`.

- **Board delegation over ping** Ping reply carries the box's open task
  board, so the cloud SI can submit work ?? Yes, with reverse secret given only to SI? v4
  
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
  `docs/infrastructure-documents/design/v3-dtls-over-email-plan.md`; the record of what
  was built and tested is `docs/infrastructure-documents/proofs/dtls-over-email-v3.md`.
  This completes the carriage the mailbox harness above was
  the first step toward.
