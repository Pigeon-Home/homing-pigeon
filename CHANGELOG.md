# Changelog

## 3.7.41 - 2026-10-18

### Tests

- The local-signal fixture joins the oracle-brief thread before
  removing its temp dir. On Windows the brief file was still
  open at cleanup, so a passing test died with WinError 145.
  The cleanup now retries briefly before giving up.

## 3.7.40 - 2026-10-18

### Features

- Local signal delivery for senses and extensions. A sensor or
  extension running on the same machine as the runner no longer
  mails its alerts: it drops a signed envelope into
  `<base_dir>/local-inbox/` (scanned about once a second), or
  pushes the identical envelope over a loopback TCP connection
  (`local_signal_port`, default 39271; 0/false turns the listener
  off; `local_signals: false` turns both front-ends off). One
  ingest core serves every path: the envelope states its
  `api_version` and is validated under the same contract as a
  manifest, the signature, envelope, and key-policy checks are
  the mail path's, and the declared-signal gate applies
  unchanged. Locally filed alerts are stored with
  `source: "local"`. Producer helpers (`build_sensor_alert`,
  `sign_envelope`, `drop_local_signal`, `send_local_signal`)
  live in `runner/extensions.py`; the Lab Results example drives
  both styles via `--local-dir` / `--local-port`. A high or
  critical locally filed alert can wake the Oracle through a
  deterministic gate (per sensor + signal cooldown,
  `local_wake_cooldown_sec`, default 900, single flight in
  progress); the assessment is appended to `oracle-briefs.jsonl`
  and the runner log, with a deterministic note when no local
  model is configured.

## 3.7.39 - 2026-10-18

### Docs

- The README prompt now points at the published protocol,
  `https://pigeon-home.com/PROTOCOLv1`, instead of the blob on
  `main`.

## 3.7.38 - 2026-10-18

### Features

- User extensions. An extension is a folder holding an
  `extension.json` manifest: the sensor name it files as, its own
  semver (the author's number, revved freely), the extension API
  version it was written against, and the declared list of signals
  it may send the Oracle, each with a one-line description. The
  loader validates manifests strictly (unknown fields refused by
  name), enforces the API rule (current loads, newer refused with
  a readable reason, older accepted under an additive-only
  promise), and reports loads and refusals at startup; a broken
  extension is refused and logged and never affects the agent.
  Ingest rejects an undeclared signal (or none) from an
  extension-backed sense; a declared signal is stored with its
  declared description and the extension's version attached, and
  `senses` answers carry a `declared_signals` glossary — the
  declaration is the context the Oracle receives. Extensions live
  in `<base_dir>/extensions` or the `extensions_dir` config key.
  Ships with a lab-results example sense under
  `examples/extensions/lab-results/` and the full walkthrough in
  docs/extensions.md.

### Oracle

- The notable-access line in a retained job's summary names its
  own job. It now reads `notable: SUSPICIOUS ACCESS -- job <id>:
  ...`, and the withheld-output marker binds the same way. Small
  models were transplanting the line onto a neighbouring benign
  job when the only binding was its position under the block
  header.

## 3.7.37 - 2026-10-18

### Security

- `output_retention_days: 0` now means no expiry everywhere. The
  prune path already treated 0 as "keep forever"; the expiry check
  treated an explicit 0 as the 7-day default through `or 7`, so a
  record the prune would keep was reported expired after a week.
  Absent, None, or unparseable still falls back to 7. A negative
  value still never expires and prunes nothing.

### Tests

- A coverage-guided campaign over the parser surfaces. Each
  candidate is exercised under a line tracer scoped to `runner/`,
  and it joins the corpus only when it adds coverage. The in-suite
  run is 150 rounds. Growth past the seeds is required on Linux,
  where it was measured; every platform keeps the construction
  contracts (coverage includes the seeds-only baseline, the corpus
  never drops a seated seed or passes the cap, same seed gives the
  same corpus). The tracer matches a runner path case-insensitively,
  because Windows does not always spell the path the way `abspath`
  does.

### CI

- The Windows sharded-suite reporter can no longer be crashed by
  shard output. Printing a failed shard used to raise
  UnicodeEncodeError on the cp1252 console, the reporting loop
  aborted with a log still open, and tempdir cleanup then died
  with a sharing violation, so the real failure never appeared.
  Shard output is written as UTF-8, a shard is counted failed
  before its log is printed, and cleanup tolerates a directory it
  cannot remove.
- Shard children write UTF-8 on stdio. The reporter reads their
  logs as UTF-8; a Windows child on the ANSI code page either
  failed while printing a character outside that page or delivered
  the dump as backslash escapes. `PYTHONIOENCODING=utf-8` is stdio
  only, so `open()` keeps the locale encoding.
## 3.7.36 - 2026-10-18

### Security

- The runner log tail that enters the Oracle's context no longer
  re-imports quoted material: model reply previews are replaced
  with a marker, and a flagged job's logged output (its stdout
  preview line and its full-output block) is removed from the
  tail. A field re-ask after the withholding change found the
  flag value riding back into the payload inside a quoted
  historical reply in the log tail. runner.log itself keeps
  everything, unchanged -- only the context feed is scrubbed.

### CI

- Mutation can count the sharded suite more than once in one
  process. unittest discover caches an imported module by name,
  and the stats run and the clean run share that process, so
  the second discover of `test_alpha` died with "incorrectly
  imported" on the v3.7.35 tag. Names a count added are dropped
  when the count returns.

## 3.7.35 - 2026-10-18

### Security

- A job carrying a notable (suspicious-access) finding no longer
  has its raw output placed in the Oracle's context: the summary
  carries the finding, the script, and an attestation-shaped
  withheld marker (length and digest) instead. Field tests
  showed small models handing a flagged job's output back on
  request and unprompted, and the reply gate cannot catch an
  arbitrary short value. The withheld outputs still feed the
  reply gate as scan-only watch text -- never shown to the
  model -- so a reply repeating a pattern-shaped secret from a
  flagged job is still rejected. The retained record on disk is
  unchanged, and unflagged jobs keep their output in context.

### CI

- Mutation can collect a baseline again. The sharded-suite
  test imports `tools/run_tests_parallel.py` at load time, and
  mutmut's copy did not include `tools/`, so the v3.7.34 tag
  job died on that missing file before any mutant ran.

## 3.7.34 - 2026-10-18

### Oracle

- The default inference model is now `qwen3:1.7b` (was
  `llama3.2:3b`), chosen by the full model eval battery under
  the project's ranking -- a clean catch with no invented
  findings first, then history and detail accuracy, then
  latency. It was one of only two models with two clean
  catches and no invention, and the only one of the two that
  also passed history and detail. `--faster` still pulls
  `qwen2.5:3b`; the Raspberry Pi profile still pulls
  `llama3.2:1b`; `--inference-model` still wins over both.

### CI

- The Windows suite run is sharded. `tools/run_tests_parallel.py`
  splits the same unittest discover across four workers, each
  test exactly once. The Linux test job stays the serial
  reference run.

## 3.7.33 - 2026-10-18

### CI

- A failed mutation job no longer fails the whole tag build.
  The job still shows failed, so the signal stays, but
  SourceForge and GitLab key off the run conclusion and were
  skipping a release when only mutation was red (v3.7.29).

## 3.7.32 - 2026-10-18

### Oracle

- Instructions now dispatch. A deterministic classifier marks
  an owner message to the interactive Oracle as an action or a
  question; for an action, her first reply must be a tool call --
  a prose-only reply is returned once with a directive to call
  the tool or name the one thing that blocks her. Questions,
  including the summary fast path, keep the free path. The
  charter gave permission; this gives the permission a dispatch
  path, the way a cloud SI request becomes a job.
  tests/test_oracle_charter.py pins the classifier table and the
  re-ask behavior.

## 3.7.31 - 2026-10-18

### Fixes

- A job id that ends in a newline is rejected. The checker used `$`,
  which matches just before a final newline, so `0\n` passed.

### Oracle

- The interactive Oracle's charter is restored: she is the owner's
  local debugging partner, not only a watcher. The agent prompt
  again gives her full hands -- answer questions about the system,
  and carry out the owner's instructions on it, launching programs
  and doing basic operating-system tasks -- under the two rules
  that never moved: never invent an event, never reveal secrets.
  The mailbox query prompt keeps its disclosure-boundary role.
  tests/test_oracle_charter.py pins both sides of the split.
  This landed after v3.7.30 was tagged, so it ships here.

### Docs

- Coverage and mutation reports for the 3.7.30 tree are in
  docs/reports/v3.7.30. Statements 91.8%. Mutation of
  runner/security.py killed 458 of 537 (85.3%).

## 3.7.30 - 2026-10-18

### CI

- Mutation collects a baseline again. The live-doc guard looks for
  the root manuals next to the runner package, and mutmut's copy of
  the tree did not include them, so the tag job died on
  `INSTALL.md not found` before any mutant ran. Those manuals are
  now part of the mutation copy.

## 3.7.29 - 2026-10-18

### Fixes

- The Oracle chat page's script parses again: a raw newline
  inside a JS string made the whole script a SyntaxError, so
  the send handler never attached and pressing Send in the
  browser did nothing. A node --check regression test now
  parses the served script.
- The Oracle chat box starts empty. The example question is a
  placeholder hint, not content: a prefilled box impersonated
  an already-asked question.
- A loopback Send with no Origin header reaches the model.
  Some Windows WebViews omit it, and rejecting it made the
  button look dead while the runner log kept moving. A
  non-loopback Origin is still refused.
- The no_secrets attestation scans the job output again. A
  merge dropped the line that bound that text, so the
  predicate raised NameError instead of scanning.

### Tests

- Negative-simulation batches for concurrency, extension
  poison, result policy, secret scan/redaction, DRI paging,
  platform interpreters, and Windows reserved names (PR #84).

### Docs

- Live docs name Gmail only where it is the concrete fact
  (installer hostnames, the dedicated-account walkthrough,
  the connector's current identity); a guard test holds the
  line. Evergreen procedures use version placeholders instead
  of the current version, guarded likewise.
  *(Audit note, 2026-10-18: the naming policy has since tightened —
  live docs now carry zero mentions of the provider's name; see the
  current guard test.)*
- PROTOCOL.md updates.

## 3.7.28 - 2026-10-18

### CI

- The mutation job runs on version tags only. Branch pushes
  and pull requests skip it.

## 3.7.27 - 2026-10-17

### Install

- `--faster` pulls qwen2.5:3b. The 1.5B model's Flag321
  verdicts did not stay steady across paraphrases; 3b was
  the smallest model whose catch did.

## 3.7.26 - 2026-10-17

### Protocol

- Messages use `"v": 1` again.

## 3.7.25 - 2026-10-17

### Features

- `--oracle-cli`: a terminal Oracle chat on the identical ask
  pipeline as the `--oracle` web window -- same context, same
  reject table, same `oracle-chat.jsonl` record with open/close
  events. Questions are capped at 4000 chars; `/quit`, `/exit`,
  `/help`, EOF, and Ctrl+C end the session; the mailbox setup
  gate is skipped exactly as with `--oracle`. The model warm-up
  is shared by both front ends.

### Detection

- The Oracle's job summaries now carry a "notable:" line when a
  job's script referenced a credential store or a file outside
  the job's own workspace -- a deterministic finding computed from
  the script, after field tests showed small local models miss
  that reasoning even when the script is in front of them. Both
  ask prompts direct the Oracle to name every such job, in
  detail, when asked about malicious or suspicious jobs.
- Artifact scan build-out: the post-job YARA/ClamAV scan gains a
  dedicated cross-platform test suite (it was previously covered
  only inside the Linux-gated tests), and two new built-in YARA
  rules -- `hp_cred_dump` (T1003.001) and `hp_reverse_shell`
  (T1071) -- with a consistency test keeping the shipped rules
  and their ATT&CK tags in agreement. A YARA `error:` line is no
  longer filed as a hit named "error:".

### Tests

- Flag321: the fake-credential field scenario pinned as unit
  tests -- the retention contract (a job is retained for the
  Oracle only when its effective result view is not "full", so a
  "full" ceiling leaves the Oracle answering from the runner-log
  tail) and the context contract (the job index lists every
  retained job; each summary carries the job's script and raw
  local output).

### Docs

- VR.MD is deleted at the owner's word; ORACLE_DASHBOARD.md
  stays. Version nicknames are no longer used for behavior.

## 3.7.24 - 2026-10-17

### Build

- The frozen executables ship the whole runner again. Since the
  import-loader reface, runner.py loads its sibling modules through
  importlib, which PyInstaller's static analysis cannot see, so the
  one-file builds silently omitted them: --version printed
  "unknown", and the senses, review, security, and sandbox modules
  would have degraded without a word. Every dynamically loaded
  module is now a --hidden-import on all three platforms, Linux and
  macOS smoke the built binaries' --version (only Windows did),
  and a guard test keeps the hidden imports in sync with the
  loader.
- Dependency bumps folded in (Dependabot): GitHub Actions
  (setup-python 7, download-artifact 8, action-gh-release 3,
  dependency-review-action 5, docker/login-action 4), and the
  Docker base image moves to python:3.14-slim.

### Hardening

- Linux state files are opened no-follow throughout: a symlink
  planted in place of the config, the canary, the detection
  baseline, the DRI state, the security audit files, retained
  jobs, the replay and board temp files, the OAuth token, the
  install receipt, the systemd unit, posture snapshots, or the
  alert files is refused rather than read or written through.
- Path containment: a retained job id can no longer leave its
  directory, a sandbox script name must be a single path segment,
  and the Oracle's file tools stay inside the state directory.

### Internal

- The import fallback and the job-user privilege drop were refaced
  behind a single loader and a syscall face. The test suite grew
  to 1,954 tests, pinning the Linux confinement, posture, and
  rate-limit decisions; the query-limit contract is pinned as
  documented (a cap that is present but not a number refuses the
  query).

## 3.7.23 - 2026-10-17

### Oracle

- Answer-format guard: a reply that is a structured-data dump
  (the job index re-serialized as JSON, clean or corrupted) or
  that carries a tool-call-shaped fragment is withheld, the
  question is re-asked once for plain prose, and a second
  failure returns a mechanical fallback sentence. Both system
  prompts now state the rule: no JSON, no tool calls as text.

### Inference

- `--faster` now pulls `qwen2.5:1.5b` instead of
  `llama3.2:1b`: better format-following at comparable speed,
  and prose answers generate a fraction of the tokens. The
  raspberry-pi-home profile keeps `llama3.2:1b`.

## 3.7.22 - 2026-10-17

### Distribution

- Both mirrors now carry the full release: the SourceForge and
  GitLab publishers ship every published asset (the three
  install archives, the Python wheel and sdist, and SHA384SUMS).
  This is the first release GitLab receives unattended.

### Documentation

- `AGENTS.md`: one result-location rule, stated consistently —
  results are delivered to the runner's mailbox; the connector
  sees one only when it was addressed there or forwarded.
- `docs/local-si-test.md`: a status block at the top separates
  `--local-test`, the email harness, `--browser`, and
  `--diagnose`, replacing the "email only" opening.
- README links the GitLab and SourceForge mirrors.

## 3.7.21 - 2026-10-17

### Distribution

- Releases now also publish to SourceForge (project
  `homing-pigeon`): the three install archives and SHA384SUMS
  land in the project's file area under the tag, each marked
  as the default download for its OS, and the source is
  mirrored to the project's git repository (main + tags).
  Publishing there is best-effort: the GitHub release and
  PyPI never wait on it.

## 3.7.20 - 2026-10-17

### Protocol v2

- The wire protocol is now version 2. Every message carries
  `"v": 2`, and every reply carries it too. Protocol and
  product versions are separate numbers from here on.
- No backward compatibility by default: a v1 message is
  rejected at the job, query, and board gates. An operator who
  still needs v1 opts in per process with
  `--allow-protocol-v1`; replies stay v2 regardless.
- The shared secret now has a protocol floor of 128 bits of
  entropy, enforced on the runner at startup (as before) and
  now on the sender too: `cloud/send_job.py` refuses to sign
  with a missing, patterned, or weak secret.
- Documentation: the generation idiom is retired (unwritten
  future work takes the single placeholder label v9), and the
  IETF draft gained a statement of purpose and a "Relationship
  to later versions" section. `PROTOCOL.md` and the draft
  continue to specify v1, the specification of record.

## 3.7.19 - 2026-10-17

### Logging that can actually be debugged from

- `runner.log` grows up: it was capped at 2 MB with a single
  backup (~4 MB of history, ever). The bounds are now config
  (`log_max_bytes` / `log_backups`, defaults 32 MB across 4
  rotated files), so a debugging session survives in the log.
- A job's complete stdout and stderr now land in `runner.log`
  before the result email's bounded copy is cut — still
  redacted the way the log has always been, just no longer
  truncated to a one-line preview.
- New opt-in `oracle.log` (config `oracle_log`, off by
  default): full-fidelity inference records — request
  payloads, replies, error bodies verbatim, per-call timings —
  at both inference entry points, plus the Ollama daemon's own
  output when the runner spawns it. Sized for weeks of testing
  (`oracle_log_max_bytes` / `oracle_log_backups`, defaults
  512 MB x 4, ~2 GB worst case). Config secrets never enter
  either log.

## 3.7.18 - 2026-10-17

### A diagnostic harness the operator can run

- New `--diagnose` mode: one command runs a black-box gauntlet
  against the real configured system — the same config, mailbox,
  model, and state dir the live runner uses — and writes a
  verdict report instead of making the operator photograph
  consoles. Eight fault-isolated sections: identity banner,
  config audit (the shared secret is measured against the
  startup entropy gate, its value never printed), mailbox auth,
  model reachability with a timed completion, a signed
  round-trip job through the real email transport with the
  result's signature verified, an audit of the Oracle context
  exactly as the chat builds it (job index quoted verbatim),
  the five Oracle acceptance probes, and a senses snapshot
  that reports unreadable as unreadable, never as clean.
- The full report lands in `harness-report-<timestamp>.txt`
  in the state dir; the exit code is the number of failed
  sections. `--diagnose-timeout SEC` bounds the round-trip
  wait (default 120s).

## 3.7.17 - 2026-10-16

### The Oracle chat gets a real interface

- The chat page is redesigned: a neutral dark chat UI in the
  system sans (the old olive-and-serif theme dated from the first
  --oracle commit and never had a design pass). Real bubbles now:
  the operator's in deep steel blue on the right, the Oracle's in
  dark slate on the left; a subtler role card; an accent Send
  button; the Working bubble's border breathes while the model
  thinks.
- Every bubble carries a clock stamp: the question when it was
  sent, the Working bubble with its start time (still ticking
  elapsed seconds and the current step), and the answer with its
  arrival time and the total wait ("took 2m 12s") — so a slow
  answer can be documented from a screenshot.
- The operator's messages sit on the right, the Oracle's on the
  left, like a normal chat.

### Summary questions stay out of the tools

- Field fix from the testing loop: the model answered summary
  questions correctly from the new job index, but still spent
  extra rounds listing directories first. The chat instructions
  now ban tools outright for summary, count, and status questions
  and ask for each job's time in the answer.

## 3.7.16 - 2026-10-16

- Version-only release: no code changes from 3.7.15. Cut at the
  maintainer's request so the latest-release line moves to a round
  checkpoint of tonight's work — the Oracle stall fixes, the job
  index, the warm-up join, `--faster`, and the CI security checks
  all shipped across 3.7.14 and 3.7.15.

## 3.7.15 - 2026-10-16

### A lighter Llama without the Pi profile
- `install.exe --faster` pulls `llama3.2:1b`, the same model the
  Raspberry Pi profile uses. It does not change protected paths.
  `--inference-model` still wins. On an upgrade it switches the
  model; a normal upgrade still leaves config.json alone.
- `homing-pigeon --faster` uses that model for one process and does
  not rewrite config.json.

## 3.7.14 - 2026-10-16

### The chat shows that the model is working
- A summary is answered from the index already in the prompt. The
  model is no longer told to open every retained file first. One
  file, and only when the question asks for that job's script,
  output, or exit code.
- The page says "Working" as soon as the question is sent. A local
  3B model on a laptop can take a few minutes, and the page used
  to look frozen.
- A finished model call logs how many seconds it took.

### The chat cannot stall in silence
- Tool commands run with an empty stdin, so a command that waits
  for input fails in a second instead of burning its whole timeout
  doing nothing.
- The model stays warm: calls to the local Ollama endpoint carry
  keep_alive, and --oracle warms the model in the background at
  startup, so the first question does not pay the cold start.
- One question has a wall-clock budget (inference
  .agent_wall_clock_sec, default 300 seconds). When it runs out,
  the Oracle answers from what it has already seen instead of
  opening another tool round.
- The prompt ranks run last: never use it to search or read files.
- The page's Working line now counts elapsed seconds and shows
  the current step, fed by a token-gated /status on the same
  loopback server.

### A summary comes from a job index, not the log

- Field report: asked for a summary of the job status, the Oracle
  narrated the runner log tail instead — mailbox authentication
  warnings and startup lines — and never named a job. The context
  it was handed had no index to read back: detailed job blocks
  (script and output), then a noisy log. oracle_context now leads
  with a computed Job index — one line per job: id, kind, result,
  time, newest first — ahead of the detail blocks, where it also
  survives the context size cap. The chat instructions now say a
  summary names jobs from the index, and that the log tail is
  about the runner itself: polls, sign-ins, and startup lines are
  not jobs, and a warning there is not a job failing.

## 3.7.13 - 2026-10-16

### Low-profile senses on the watches that already exist
- ATT&CK labels on the lines the Oracle already sees: Security audit
  ids, autorun and Winlogon changes, a service-list change, and a
  canary trip. A label is not a verdict.
- Linux and macOS get a narrow host-log tail (auth failures and error
  lines from the log files, 4KB from the end). journalctl is only the
  fallback when those files cannot be read, and it is capped. macOS
  does not call `log show`.
- Firewall posture is one line: netsh profile state, `ufw status` or
  the iptables policy lines, or the macOS Application Firewall state.
  No ruleset dump and no packet capture. Unreadable is not "off".
- After an exec job, files that job created or changed are scanned
  only when `yr`, `yara`, or `clamdscan` is already installed. Files
  over 1MB are skipped. `clamscan` is not used. A miss or a missing
  tool adds nothing. A hit is advisory and does not change the exit
  code. Opt out with `inference.artifact_scan=false`.
- Auth-log lines carry the same ATT&CK ids as the Windows audit map
  (a failed password is T1110, sudo is T1548.003, a new account is
  T1136). A plain error line is not labeled.
- The firewall line is diffed against the last reading. A flip says
  "changed". The first look is a baseline. Unreadable does not
  overwrite that baseline.
- A YARA or ClamAV hit is kept for the local Oracle even when the job
  output itself is not retained. The note has the finding, not the
  raw output. `inference.yara_rules` can point at an operator rules
  file. A missing file falls back to the built-in rules.
- A canary trip and a firewall flip are written once into the senses
  store, so a senses query can see them. The same trip is not filed
  again on the next look. Restoring the canary clears that memory.
- A registry change, and a new auth or audit line that carries an
  ATT&CK id, are filed the same way. The first look at a log is a
  baseline and is not an alert. A plain error line is not filed.
- A YARA or ClamAV hit is filed there too, once, with the job id in
  the title. The raw output is still not stored with it.
- The same look runs once per poll, before the page check, so a trip
  is filed even when the chat window is closed. The poll skips the
  journalctl fallback. `inference.watch_system=false` still opts out.
- AV posture is the same shape as the firewall line, and it is not
  a scan. Linux stats the ClamAV daily signature file (stale after
  7 days). Windows asks whether the Defender service is running.
  macOS stays unreadable. A stale or stopped tool is T1562.001, and
  a flip is filed once.
- The local model timeout defaults to 180 seconds, not 60. A cold
  llama3.2:3b on a laptop was dying at the old cap before the first
  token. A config that already says 60 still uses 60. The chat says
  how many seconds it waited.
- Each model call logs the timeout it is using. A reply that names a
  tool but is not valid JSON is one warning, with a short preview.
  The chat log stores the failure detail, redacted, so a timeout is
  visible there and not only as `inference_error`.

### Low-overhead detection after job completion
- A new runner/detection.py evaluates each finished job: tiny
  Sigma/YARA-style rules over the job and its result (unexpected
  interpreter, encoded-command markers, unusually large output),
  recorded on the result as detection_hits with ATT&CK technique
  ids. Advisory only — a hit never changes the job's outcome.
- A tiny rolling baseline (detection-baseline.json in the state
  folder: job-kind counts and recent output sizes) flags extremes
  as detection_anomaly: output over 10x the median once enough
  samples exist, or a brand-new job kind after many jobs.
- A job carrying a multi-step plan gets an explicit budget check
  (plan_budget_ok / plan_budget_reason): step count and summed step
  timeouts against max_plan_steps (default 8) and
  max_plan_timeout_sec (default 600) from the top level of config.
- Canary tripwires stay with _canary_watch; this module defers to
  it. Detection never raises into job handling: an evaluation error
  records nothing.

## 3.7.12 - 2026-10-16

### Oracle system watch, on by default
- On Windows the Oracle's context now includes a tail of the Windows
  Event Log — Critical/Error/Warning from System and Application, plus
  Security audit failures (4625, 4672, 4648, 4720, 1102) — read-only
  via wevtutil, and a registry watch over autorun/persistence values
  (Run/RunOnce in HKLM and HKCU, Winlogon Shell/Userinit) and the
  service list via reg.exe, diffed against a snapshot so only changes
  are reported. A log that cannot be read is reported as unreadable,
  never as clean. Both prompts (mailed ask and local chat) document
  the sections and the anti-fabrication rule covers them.
- Canary tripwires: the runner plants three files with unique tokens
  (passwords.txt, backup-codes.txt, api-keys.txt) in its state folder.
  A canary whose content changes or that goes missing is reported to
  the Oracle by name as TRIPPED, and the trip stays reported until the
  file is restored or the snapshot is cleared — a tripwire never
  silently re-baselines over a trip. Cross-platform.
- Opt out of all three sections with `inference.watch_system=false`
  in config (default true).

### Fixes Windows CI caught before this shipped
- Canary hashes now survive Windows line endings: planting writes
  exact bytes and the state check folds CRLF to LF before hashing.
  The first cut planted in text mode but hashed the LF string, so on
  Windows every canary read as modified forever.
- `oracle_context`'s `max_chars` now caps the whole context, the way
  its contract always said: the Event Log and registry sections were
  appended after the job output had been sliced, with no budget check,
  so on Windows a capped call overran and a non-positive cap returned
  the watch sections instead of "". The job-budget tests pass on
  Windows now, with regression tests that patch the platform so
  Linux CI covers the Windows behavior too.
- The v3.7.11 tag carries the first of these fixes but its Windows
  build failed on the second, so it was never published — no GitHub
  Release, no PyPI upload. This release supersedes it.

## 3.7.10 - 2026-10-16

### Local Oracle chat prompt
- The browser chat no longer inherits the cloud ask rules. Those rules
  told the model never to inspect raw output and to answer only from
  the pasted text, so a small model ignored the files on the box. The
  local chat now has its own instructions: the operator is at this
  computer, open the retained files and the log, and a missing kind
  is "kind not recorded", not a failed job.
- The mailed ask path is unchanged. It still must not reveal raw output.
- Gmail auth recovery is logged at WARN. The per-minute cap drops INFO
  once a process is busy, which hid the recovery line from the mutation
  job's clean pytest run.

## 3.7.9 — 2026-10-16

### Property-based tests + a real signature bug they caught
- New `tests/test_properties.py`: Hypothesis property tests over the
  protocol's pure core -- sign/verify round-trip, tamper rejection,
  wrong-secret rejection, preamble/trailer tolerance, subject-line
  job extraction, job_id charset, and issued_at window boundaries.
  Hypothesis is now installed in the CI test job (test-only; the
  runtime stays stdlib-only).
- The round-trip property caught a genuine bug in `_object_start`:
  when a signed payload contained a `{` inside a string literal (a
  `"{"` key, a script with `{...}` blocks), the extractor could pick
  that brace as the JSON object opener and `verify_body` rejected a
  legitimately signed body. Braces inside string literals are now
  excluded from candidacy, with a fallback to the old order for
  lopsided quotes in the preamble.
- Infinity hardening (Grok): a config value of Infinity no longer kills
  the poll -- hot reload ignores it, and the poll sleep, worker count,
  mail caps, job timeout, retention, and output caps all fall back to
  their defaults instead of raising OverflowError.
- IETF draft: email reframed as the transport binding, not the
  protocol; 13 more property tests (keyed verification, redaction,
  fragment detection, normalization).

## 3.7.8 — 2026-10-16

### Oracle agent: plain-chat replay + real diagnostics
- Content-embedded tool calls no longer fabricate `tool_calls`/`tool`
  history for the next model call. Ollama rejected history referencing
  call IDs it never issued (HTTP 400 on the follow-up call); the
  exchange is now replayed as plain chat (assistant's own words, then
  `Tool '<name>' returned:` as a user message). Native tool_calls keep
  the OpenAI wire format.
- Inference failures now log the endpoint's response body (where the
  real reason lives), plus per-call shape: message roles and payload
  bytes. The agent loop also logs which replay mode it used. No more
  guessing from a bare "HTTP Error 400" line.
- OAuth token exchange failures now include Google's `error_description`
  (the part that says why), not just the bare `invalid_request` code.

## 3.7.7 — 2026-10-16

### Oracle protocol pack
- The Oracle is now framed as the over-the-shoulder administrator
  watching the runner execute jobs on this machine; the prompt explains
  where jobs come from (signed emails in the runner's dedicated mailbox:
  the runner polls, verifies each signature, executes, and emails back
  a signed result).
- PROTOCOL.md now ships inside the release binaries (PyInstaller
  --add-data on Windows, Linux, and macOS) and the Oracle's system
  prompt points the local model at it, so the model reads the protocol
  spec on demand with its file tools. No internet needed: the spec
  travels with the release.

### Verification
- Unit tests in `tests/test_oracle_chat.py`: bundled doc resolution
  (source layout and missing-doc cases), admin framing and protocol
  pointer in the system prompt, build.yml wiring on all three platforms.
- End-to-end: release one-liner on the deployment box; ask the Oracle
  where the protocol reference lives and what a job is.

## 3.7.6 — 2026-10-16

### Oracle chat
- The Oracle page now opens with a pre-filled prompt ("Give me a summary of
  the job status of what you found on this system.") and a short statement
  of the Oracle's role: what it watches, what it can read and run, and that
  nothing leaves the machine.
- Fixed the agent loop leaking raw tool calls into the chat. Small local
  models (llama3.2:3b via Ollama) often emit `{"name": ..., "parameters":
  {...}}` as message text instead of native `tool_calls`; the parser only
  recognized the native shape, so the JSON blob was shown as the "answer"
  instead of executing. Content-embedded calls are now detected (fenced or
  bare), restricted to the known Oracle tool names; native `tool_calls`
  still take precedence.
- The Oracle's system prompt now defines Homing Pigeon vocabulary (what a
  "job" is, retained job files, the runner log) and names this box's real
  state directory, retained folder, and log path, so "job status" questions
  resolve to files instead of guesses. Tool commands run with the state
  directory as the working directory, and relative tool paths resolve
  against it.

### Verification
- Unit tests in `tests/test_oracle_chat.py` capture the learnings:
  content-embedded tool calls (bare and fenced), unknown names staying
  plain text, native calls winning over content, pre-filled page prompt,
  role section, state paths in the system prompt, relative path
  resolution, and the tool working directory.
- End-to-end: release one-liner on the deployment box, Oracle chat
  against the local model answering the pre-filled job-status summary.
