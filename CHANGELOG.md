# Changelog

One section per release, newest first. Entries are compact by
design: the headline changes, the fixes that mattered, and the
facts a reader may need to cite. Git history carries the rest.

## 3.10.1 - 2026-10-19

- **One protocol, version 1.** This release supersedes the
  3.10.0 tree, which was tagged before the no-v2 restructure
  landed. There is no protocol version 2: the DTLS session
  support is a binding of version 1, specified in the same
  IETF draft, and the DTLS greeting's `v` field carries the
  protocol version (1). Per-job AEAD encryption is a
  required capability of version 1 — implementations MUST
  support it, the reference sender encrypts by default, and
  cleartext is sent only by a sender's explicit choice.
- **Conformance is per binding.** The draft now states the
  security requirements as properties: object authentication
  (the signature/MAC) is REQUIRED on every binding and never
  moves to the transport; confidentiality is REQUIRED as a
  property on every binding and may be satisfied by the
  binding itself. On the DTLS binding the session provides
  it, so per-job encryption is OPTIONAL for the sender there
  (receiver support stays REQUIRED everywhere); on email and
  NATS the per-job encryption carries it; on the file binding
  it is local policy. A runner MUST offer the email binding.
- **Pipeline hardening.** The transport and encryption parser
  surfaces were fuzz-campaigned; the Windows surface is now
  simulated locally (path separators, SSL stores) so platform
  failures surface before CI; test-isolation fixes keep the
  suite green under shuffled order and unprivileged runs;
  `jobcrypto` validates key and nonce sizes in its own
  vocabulary; the audit report reads UTC stamps as UTC. The
  ruff gate is green on the whole tree.

## 3.10.0 - 2026-10-19

- **Transports are extensions.** The runner core is
  transport-blind: email, the watched folder, and NATS each run
  as a standalone extension program under one contract
  (TRANSPORT_API_VERSION = 1), supervised by the runner over
  per-extension file channels. Email remains the default; a
  3.9.0 config works unchanged; the shared secret is never
  handed to a carrying pipe. Anyone can drop in a transport —
  a valid manifest loads, registered or not.
- **DTLS session binding.** A new `dtls`
  transport extension terminates DTLS 1.3 sessions directly:
  the shared secret as external PSK, `psk_dhe_ke` only
  (forward secrecy is a hard requirement, resumption
  included; `psk_ke` is never offered or accepted),
  connection IDs so NAT rebinding survives, a stateless cookie
  exchange before any large flight. Off until the owner
  enables it — the product's first network-facing inbound
  listener (the loopback local-signal socket and the Oracle
  page predate it). The
  session's first message is the greeting: platform
  information tiered by the responder's own configuration
  (`none` / `family` / `standard` / `full`, default family),
  sent only after authentication. Client: `cloud/send_dtls.py`.
- **Per-job encryption, on by default.** `send_job.py` wraps
  the signed body in an AEAD envelope (ChaCha20-Poly1305,
  HKDF-SHA-384 key from the job's selected secret; stdlib-only
  `runner/jobcrypto.py`). The runner verifies the signature
  before decrypting; results mirror the job's form;
  `job_encryption` overrides explicitly; `--cleartext` is the
  deliberate interop escape. Cleartext jobs are still accepted
  and logged as such. No forward secrecy, stated wherever the
  feature is described: a compromised secret exposes every
  recorded encrypted job.
- **Mail TLS, required and forward-secret.** `mail_tls_required`
  (default true): IMAP over implicit TLS, STARTTLS required
  with the peer certificate verified, TLS 1.2 floor — and in
  the required posture TLS 1.2 sessions are pinned to ECDHE
  suites, so the hops are forward-secret as 1.3 is by
  construction. The opt-out relaxes verification only; no
  setting enables cleartext mail.
- **One draft, one version.** The IETF documents
  consolidated into `draft-homing-pigeon-00` (the one
  canonical file): one protocol version, with the email,
  file, NATS, and DTLS bindings in one numbering and one
  reference list — the DTLS work is a binding of version 1,
  not a second version. The short-lived pointer files are
  removed; the -00 file is the document itself. The draft's
  mail binding now requires TLS (MUST, RFC 8314/8996/9325),
  and per-job encryption is a requirement of the protocol,
  not an optional extension.
- FAQs gained the email-binding census and two refusals with
  reasons: no PGP/S/MIME (a cloud SI has a connector, not a
  mail client), and no public-key cryptography in the core
  protocol (no strangers to introduce; symmetric end to end,
  which is also the quantum-resistant posture).
- Windows Oracle chat answers a refused `/ask` (bad token,
  bad origin, oversized body) with that status. The body is
  read first, so the socket is not aborted before the browser
  can see it.

## 3.9.0 - 2026-10-19

- **The Oracle learns from its own calls.** Each opinion is
  frozen before the job runs and scored against the outcome
  in a local learning ledger, written before the result goes
  out. Two lesson channels: verified execution facts, and
  model-formed candidates born uncorroborated, promoted only
  by later corroboration, retired permanently by one
  contradiction. Each job reads the ledger fresh, host- and
  feature-filtered. A lesson authorizes nothing by itself —
  repair still needs the latitude, the mismatch re-verified
  on this job, and the result re-judged. Keys:
  `oracle_learning` (on), `oracle_learning_model` (off),
  `oracle_learning_promote_after` (2).
- README rebuilt as a landing page; the Windows test fixes
  that 3.8.9 needed landed here (POSIX assumptions in the
  coverage pins).

## 3.8.9 - 2026-10-19

Tagged but never published: the Windows build failed
(coverage-pin tests assumed POSIX) and 3.9.0 superseded it
the same night. Content: in-core file and NATS transports
beside email, and the two-gate rule — a credentialed
transport's required authentication counts as a second gate
beside the HMAC signature. Both were re-homed as transport
extensions in 3.10.0.

## 3.8.8 - 2026-10-19

- Fix: opinion predictions attach only under the effective
  latitude, not the job's raw request (claims audit B46).
- SourceForge and GitLab publish as jobs inside the tag build
  instead of separate workflows.
- Claims audit round 2 closed: 196 claims re-inventoried and
  resolved against the tree; satire kept by the maintainer's
  vote.

## 3.8.7 - 2026-10-18

- The Oracle's opinion defaults to `repair`: one certain
  environment mismatch is fixed before the run, re-judged, and
  recorded with the received digest. Owner ceiling `diagnose`
  restores the old behavior exactly.

## 3.8.6 - 2026-10-18

- Fix: `requirements-ci.txt` joins the mutation copy list;
  the 3.8.5 mutation job died in stats collection without it.

## 3.8.5 - 2026-10-18

- **IDS collectors:** eight adapters (Falco, Suricata, Zeek,
  osquery, Sysmon, AIDE, softflowd, Wazuh); osquery is the
  measured install default (~27 MB idle; Zeek ~230 MB, opt-in
  only). Capability-probed: installed is not sensing.
- **Remediation:** jobs that diverge from their opinion
  envelope can be stopped mid-run — deterministic tripwires
  (process storm, credential artifact, confinement escape)
  kill on sight; `remediation_mode: oracle` adds judgment for
  unlisted divergences, abstention recorded, never converted
  to a kill. Quarantine never deletes; AV referral records
  the scanner's own verdict. Default `deterministic`.
- Training Watch joins the extension catalog (24 senses).
- Release pipeline lifts from the OneFuzz audit: SHA-pinned
  actions, default-deny workflow tokens with exact per-job
  grants, BUILD-PROVENANCE.json in every archive, an SPDX SBOM
  among the nine release assets, pinned CI tooling,
  docs/verification.md.
- Fix: `--oracle-opinion` startup exit (string flag in the
  numeric overrides set).

## 3.8.4 - 2026-10-18

- Docs only: the remediation design written in full; STYLE.md
  trimmed; TRANSPORTS.md status note; the front page stops
  selling the lockdown posture as the shipped default.

## 3.8.3 - 2026-10-18

- Two senses: Resource Sentinel (rolling-window rates, not
  samples) and Job Watcher (per-job baselines from `retained/`).
  Catalog: fifteen.

## 3.8.2 - 2026-10-18

- **The Oracle's opinion is built:** a job may request a
  latitude (`off`/`diagnose`/`advise`/`repair`), capped by
  `oracle_opinion_mode`; tier-1 checks are deterministic; a
  repair is never silent and carries `received_digest`.
- **Pi Light:** `oracle_mode: deterministic` — the full
  runner and protocol with no local model — plus the ARM64
  Pi Light archive whose `default_profile` marker selects it.
- `dag_mode: advisory` (PROTOCOL 13.1); thirteen worked senses
  ship as examples; one-process CLI overrides for the runtime
  knobs; counted `-v` verbosity; the invocation line logged
  shell-quoted; designed `--help` on all three front doors.

## 3.8.1 - 2026-10-18

- Docs: the Oracle's-opinion design recorded (FUTURE.md +
  docs/oracle-opinion-design.md). Design only; built in 3.8.2.

## 3.8.0 - 2026-10-18

- **Claims audit:** 106 doc claims inventoried and decided one
  by one; corrections landed across the live docs (external
  facts re-verified, including the Mandiant acquisition and
  the Cloudflare Queues tier figures). PROTOCOL §8 names the
  two primitives actually used and states the protocol does
  not encrypt payloads; §10.1 names qwen3:1.7b the tested
  reference model. ORACLE_DASHBOARD.md removed.

## 3.7.41 - 2026-10-18

- Test fix: the local-signal fixture joins its brief thread
  before temp-dir cleanup (Windows WinError 145).

## 3.7.40 - 2026-10-18

- **Local signals:** same-box senses and extensions deliver
  signed alerts without mail — a watched `local-inbox/` folder
  (~1 s scan) or a loopback socket (port 39271) — through the
  mail path's one ingest core and gates. A high-severity local
  alert can wake the Oracle through a deterministic,
  cooldown-limited gate; the brief is recorded, never acted on
  by the gate itself.

## 3.7.39 - 2026-10-18

- Docs: the README prompt points at the published protocol
  URL (pigeon-home.com/PROTOCOLv1).

## 3.7.38 - 2026-10-18

- **User extensions:** a folder + `extension.json` manifest
  (declared signals, own semver, API version); strict manifest
  validation, undeclared signals refused at ingest, broken
  extensions refused and logged without touching the agent.
- The notable-access line in a retained summary names its own
  job id, so small models stop transplanting it onto neighbors.

## 3.7.37 - 2026-10-18

- Fix: `output_retention_days: 0` means keep-forever on every
  path (the expiry check's `or 7` disagreed with the prune).
- Coverage-guided fuzzing over the parser surfaces joins the
  suite (150 rounds, corpus grows only on new coverage).
- CI: the Windows shard reporter can no longer be crashed by
  its own output (UTF-8 end to end).

## 3.7.36 - 2026-10-18

- Security: the Oracle's log-tail context feed is scrubbed of
  quoted model replies and flagged jobs' logged output —
  runner.log itself keeps everything.
- CI: mutation's repeated in-process suite counts fixed
  (module-cache collision).

## 3.7.35 - 2026-10-18

- Security: a flagged (suspicious-access) job's raw output is
  withheld from the Oracle's context — summary, script, and a
  digest marker instead; the withheld text still feeds the
  reply gate as scan-only. CI: `tools/` joins the mutation
  copy list.

## 3.7.34 - 2026-10-18

- Default model is `qwen3:1.7b`, winner of the full eval
  battery (clean catches, no invention, history and detail).
  `--faster` pulls qwen2.5:3b.
- CI: the Windows suite runs sharded across four workers.

## 3.7.33 - 2026-10-18

- CI: a failed mutation job no longer fails the tag build
  (signal kept; mirrors key off the run conclusion).

## 3.7.32 - 2026-10-18

- Oracle chat: owner instructions dispatch — an action
  request whose first reply is prose-only is re-asked once
  with a directive to call the tool or name the blocker.

## 3.7.31 - 2026-10-18

- The interactive Oracle's charter restored: the owner's
  debugging partner with full hands (the mailbox prompt keeps
  its disclosure boundary; both sides pinned by tests).
- Fix: a job id ending in a newline is rejected (`$` matched
  before it).
- Coverage/mutation reports for 3.7.30 archived (91.8%
  statements; runner/security.py mutation 458/537 killed).

## 3.7.30 - 2026-10-18

- CI: the root manuals join the mutation copy tree (the tag
  job died on a missing INSTALL.md).

## 3.7.29 - 2026-10-18

- The Oracle chat works again in the browser: a raw newline
  inside a JS string had made the page's whole script a
  SyntaxError (Send did nothing); a `node --check` regression
  test now parses the served script. The chat box starts
  empty, loopback Sends without an Origin header reach the
  model, and the no_secrets attestation scans job output
  again (a merge had dropped its binding).

## 3.7.28 - 2026-10-18

- CI: mutation runs on version tags only.

## 3.7.27 - 2026-10-17

- `--faster` pulls qwen2.5:3b (the 1.5B model's Flag321
  verdicts didn't hold across paraphrases).

## 3.7.26 - 2026-10-17

- Protocol: messages use `"v": 1` again (see 3.7.20).

## 3.7.25 - 2026-10-17

- `--oracle-cli`: the terminal Oracle chat on the same ask
  pipeline as the web window.
- Detection: job summaries carry a deterministic "notable:"
  line when a script referenced a credential store or a path
  outside its workspace; artifact scan gains built-in YARA
  rules (hp_cred_dump, hp_reverse_shell) with ATT&CK tags.
- Flag321 field scenario pinned as unit tests (retention and
  context contracts).

## 3.7.24 - 2026-10-17

- Frozen builds ship the whole runner again: the importlib
  loader hid sibling modules from PyInstaller, so one-file
  builds silently omitted them. Every dynamic module is now a
  hidden import on all platforms, guarded by a test; Linux and
  macOS smoke the binaries' `--version`.
- Hardening: state files opened no-follow throughout; path
  containment for retained jobs, sandbox scripts, and the
  Oracle's file tools. Suite: 1,954 tests.
- Dependabot bumps folded in; Docker base python:3.14-slim.

## 3.7.23 - 2026-10-17

- Oracle chat: structured-data dumps and tool-call-shaped
  replies are withheld and re-asked once for plain prose.

## 3.7.22 - 2026-10-17

- Both mirrors carry the full release (archives, wheel,
  sdist, SHA384SUMS); first unattended GitLab publish.

## 3.7.21 - 2026-10-17

- Releases publish to SourceForge (best-effort; GitHub and
  PyPI never wait on it).

## 3.7.20 - 2026-10-17

- Protocol v2 on the wire: messages carry `"v": 2`; v1 is
  rejected unless the operator opts in per process with
  `--allow-protocol-v1`; the 128-bit secret floor is enforced
  on the sender too. PROTOCOL.md and the draft continue to
  specify v1, the specification of record. (3.7.26 returned
  messages to `"v": 1`.)

## 3.7.19 - 2026-10-17

- Debuggable logging: runner.log bounds become config
  (defaults 32 MB × 4), full job stdout/stderr land in the
  log, and an opt-in `oracle.log` keeps full-fidelity
  inference records (~2 GB worst case). Secrets never enter
  either log.

## 3.7.18 - 2026-10-17

- `--diagnose`: a black-box gauntlet against the real
  configured system (config audit, mailbox auth, model
  reachability, a signed round-trip job, an Oracle-context
  audit, acceptance probes, senses snapshot) writing a
  verdict report; the exit code counts failed sections.

## 3.7.17 - 2026-10-16

- The Oracle chat gets a real interface: bubbles, clock
  stamps on every message, elapsed time on the Working
  bubble. Summary questions are answered from the job index
  without tool rounds.

## 3.7.16 - 2026-10-16

- Version-only release moving the checkpoint line.

## 3.7.15 - 2026-10-16

- `--faster` for installer and runner: the 1B model for one
  process or an install, config untouched on a normal upgrade.

## 3.7.14 - 2026-10-16

- The chat cannot stall in silence: a Working indicator with
  elapsed seconds, warm model (keep_alive + background
  warm-up), a per-question wall-clock budget, empty stdin for
  tool commands. Summaries come from a computed job index at
  the head of the context, not the log tail.

## 3.7.13 - 2026-10-16

- Low-profile senses ride the existing watches: ATT&CK labels
  on audit lines, host-log tails, a one-line firewall posture
  diffed against its baseline, post-job artifact scans when a
  scanner is already installed, canary and AV-posture filings.
- runner/detection.py: per-job Sigma/YARA-style evaluation
  with ATT&CK ids and a rolling baseline; advisory only.

## 3.7.12 - 2026-10-16

- Oracle system watch on by default: Windows Event Log tail,
  registry persistence watch (diffed), canary tripwires with
  tokens that never silently re-baseline. (Supersedes the
  unpublished 3.7.11, whose Windows build failed.)

## 3.7.10 - 2026-10-16

- The local chat prompt is separated from the cloud ask
  rules: the operator is at this computer; open the files.
  The mailed ask path keeps its disclosure rules.

## 3.7.9 - 2026-10-16

- Property-based tests (Hypothesis) over the protocol core —
  and a real bug they caught: the signed-body extractor could
  pick a `{` inside a string literal as the object opener and
  reject a valid body. Infinity config values hardened.

## 3.7.8 - 2026-10-16

- Oracle agent: content-embedded tool calls replay as plain
  chat (Ollama rejected fabricated call history); inference
  failures log the endpoint's response body.

## 3.7.7 - 2026-10-16

- PROTOCOL.md ships inside the release binaries; the Oracle's
  prompt points the local model at it on demand.

## 3.7.6 - 2026-10-16

- The Oracle chat page opens with a role statement and a
  pre-filled summary prompt; content-embedded tool calls from
  small local models are detected and executed (known tool
  names only); the system prompt teaches the model the
  project's vocabulary and this box's real state paths.
