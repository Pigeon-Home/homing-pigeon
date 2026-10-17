# Changelog

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
