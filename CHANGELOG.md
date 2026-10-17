# Changelog

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
