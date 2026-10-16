# Changelog

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
