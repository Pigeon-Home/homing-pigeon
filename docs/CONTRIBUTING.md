# Contributing to Homing Pigeon

Thanks for stopping by. This is a small, security-sensitive project —
a tool that runs code on people's machines — so contributions are
welcome but held to a high bar. Here's how to do it well.

## Before you write code

- **Read PROTOCOL.md first.** The wire protocol is the contract. If
  your change alters what goes over the wire, the protocol doc changes
  with it, in the same pull request.
- **Read the security model** (PROTOCOL.md §7 and SECURITY.md). If your
  change touches authentication, signature verification, process
  execution, or credential handling, say so explicitly in your PR
  description so it gets the right scrutiny.

## Ground rules

1. **Standard library only.** The runner and installer ship as frozen
   binaries and must run on machines with nothing installed. No new
   third-party dependencies, ever. If you think you need one, open an
   issue first and make the case.
2. **Cross-platform or it doesn't ship.** Every change must work on
   Linux, macOS, FreeBSD, and Windows. Use `os.name` / `sys.platform`
   branches, and think about what each branch does on the other three.
3. **Tests or it didn't happen.** `python -m unittest discover -s runner/tests -t .`
   must pass. New behavior gets a new test with the fake IMAP/SMTP
   harness in `runner/tests/test_runner.py`.
4. **No secrets in the repo.** Not in code, not in tests, not in docs,
   not in commit messages. Test credentials stay obviously fake
   (`runner@example.com` and friends).

## How to contribute

1. Fork the repo and create a branch with a descriptive name
   (`fix-timeout-race`, `add-heartbeat`, ...).
2. Make your change, add tests, update docs (README, PROTOCOL.md,
   docs/use/runbook.md — whichever your change affects).
3. Run the full suite: `python -m unittest discover -s runner/tests -t . -v`.
4. Open a pull request against `main`. Describe **what** changed,
   **why**, and **what you tested**. If it touches anything listed
   under "Before you write code," flag it in the description.

## Style

- Plain, readable Python. Type hints where they help, not everywhere.
- Comments explain *why*, not *what*. Security-critical code gets
  a comment saying what attack it prevents.
- Keep the security warning in the README loud. PRs that soften it
  will be asked to put it back.

## Reporting bugs

Use the bug report template. Include: platform, Python version (or
which release binary), what you did, what you expected, what happened,
and the relevant log lines. If it's a security issue, **do not** open
a public issue — see SECURITY.md.

---

## Maintainer notes: the `--oracle` flag

### Tagging: bump `pyproject.toml` first

The PyPI publish job uploads `pigeon-home-runner-<version>` taken from
`pyproject.toml`, not from the git tag. v3.4.0 and v3.5.0 both shipped
with the version still at 3.3.0, so both tag builds failed in
`pypi-publish` with "400 File already exists". Before pushing a tag,
bump `version` in `pyproject.toml` to match, commit, then tag. Tags on
this repo are protected by a rule, so a pushed tag cannot be moved —
if the version is wrong, bump again and tag the next patch version.

Bump `runner/_version.py` (`__version__`) in the same commit. Every
CLI reports it via `--version`, and the frozen binaries cannot read
`pyproject.toml` — `runner/tests/test_version.py` fails the build if the two
drift.

Two more files carry the version and move in the same commit:
`runner/ops/install.py` (`__version__`) and the pin in
`runner/tests/test_install_edges.py`. A release commit touches all four.

The release commit's author email is a no-reply address: a
commit under a personal address shows that person's account on
GitHub and counts toward it in the contributors, which a release
commit should not do.


### The looking is the gate

The SI can run the entire release pipeline: implement, test, commit,
push, tag, cut the release, install it, and run it. None of that ships
without the owner's word.

This is not a capability limit. The owner is the final integration
environment: a release proceeds when he has looked at the results and
said so. The Oracle is not forbidden from approving its own releases
— it can, and then it waits anyway, because approval was never the
gate. The looking is the gate.

In practice: no push, tag, or release without his explicit word, and
a tag never lands before the build is green.

The section below is history that bites. It is for the next person
or bot that touches the runner, the installer, or the docs.

### The `--oracle` flag

This note is for the next person or bot that touches the runner.
The name is easy to get backwards. Read this before you edit
`runner/runner.py`, the installer, or the docs.

## Two different flags. Only one of them exists.

There used to be a switch that turned the Oracle off. There is now a
switch that opens a chat window with the Oracle. They are not the
same feature, they do not share code, and the old one is gone.

| Name | What it was | Status |
| --- | --- | --- |
| `oracle_enabled` in `config.json` | When false, the runner skipped the result policy, board mail, and query follow-ups and returned full output. Default was true. | Removed in `8f0719f`. |
| `--no-oracle` on the CLI | The command-line way to set that same off switch. The installer could forward it into the boot service. | Removed in `8f0719f`. |
| `--oracle` on the CLI | Opens a loopback browser chat that asks the local model through the Oracle path. | Added in `15025c7`. This is the flag that exists today. |
| `--oracle-port` | Port for that chat. Default `11436`. Bound to `127.0.0.1` only. | Added with `--oracle`. |

If you find `oracle_enabled=false` in `docs/archive/verify-v31.md`, that file
is an older verification runbook. Those checks describe a flag that
the code no longer reads. Do not reintroduce `oracle_enabled` or
`--no-oracle` to make that runbook pass. The README row for
`--no-oracle` was a leftover of the same removal and has been deleted
so the flag table matches the binary.

## Why `--no-oracle` was removed

Commit `8f0719f` (author ctf-gooo-003, message "v3: the Oracle is
unconditional - remove oracle_enabled flag") on 2026-10-15.

The Oracle had already shipped. A flag that turned it off was
a way to get full output back without the Oracle. That escape hatch was the thing
the project had decided not to keep. The commit deleted:

- the `oracle_enabled` key (it had defaulted to true)
- the `--no-oracle` CLI flag
- the branches in query handling, board mail, and result policy that
  checked the flag and skipped the Oracle
- the key in `runner/config.example.json`
- installer forwarding of `--no-oracle` into the service command
- the docs and tests that asserted the disabled behavior

After that commit the Oracle is not optional. A signed job still goes
through the result policy, the judge, redaction, and the board if
those are configured. There is no config key and no CLI flag that
puts the runner back onto a path that skips the Oracle.

`runner/tests/test_protocol_and_edges.py` still asserts that a generated
unit file does not contain the string `--no-oracle`. That test is a
guard so the installer does not start baking the dead flag into the
service again. Leave the assertion. Do not add the flag back to
satisfy it.

## Why `--oracle` was added

The owner wanted one way, for the rest of the project, to ask the
Oracle on a box what it thinks is going on. They were explicit that
this is not a loopback dashboard. A dashboard page -- job tables,
controls, a frontend over config -- was sketched once in a document
the claims audit later removed from the tree; it remains a later
product idea, not a direction for this flag. Do not grow
`--oracle` into that page.

They had also seen `feat/local-si-test`. That branch opens Open WebUI
against a second Ollama process (the "cloud SI" on port 11435) and
then emails the SI's reply to the Oracle. The owner asked for the
opposite of that: a window that talks to the Oracle directly, with
no second model and no mailbox in the middle. Open WebUI is a
separate program (`pip install open-webui`). It cannot live inside
the PyInstaller onefile binary, and the runner is stdlib only. So
`--oracle` does not start Open WebUI, does not start a second
`ollama serve`, and does not import `local_test.py`.

The chat is a single HTML page served by this process. The operating
system browser opens it. One text box, one Send button. No job
buttons, no config form, no board.

## What the process actually does

Entry point is `main()` in `runner/ops/main.py` (`runner/runner.py`
re-exports it).

1. Parse `--oracle` and `--oracle-port`.
2. Load `config.json`.
3. `--inspect` still wins if both are passed. Inspect reads local
   state and exits — `main` returns there, so steps 4 and 5 never
   run on the `--inspect` path. It does not open the chat.
4. `ensure_inference_ready` and `update_llama_from_config` run, same
   as a normal start, so a missing Ollama daemon can be started and a
   changed model id can be pulled.
5. If `--oracle` is set, `oracle_window` is called and `main` returns
   its exit code. Everything below that line does not run.

That last point is why the window does not need a mailbox: `main`
returns before the poll loop starts, `validate_shared_secret` sits
after the `return`, and the mailbox setup and OAuth gate sit before
it and are skipped for `--oracle` by their guard condition, not by
position. You can open the chat on a config that has inference and
`base_dir` and nothing else. A normal poll (`homing-pigeon` with
no `--oracle`) is unchanged.

## What the chat can see

`oracle_context` builds the model's context from the base dir: the
retained job records (id, kind, script, output), the tail of
`runner.log`, and — by default — the watch sections (canary state,
Windows Event Log, registry diff, host log, Firewall posture,
AV posture). The log tail is what lets the Oracle answer
"did this happen?" instead of inventing log events. `ASK_AGENT_SYSTEM`
(the window's prompt; `ASK_SYSTEM` is the mailbox door's) tells the model to quote from what it was given and to say it cannot
see something when it is not there.

The chat goes further: `ask_model_agent` runs a tool loop, so the
model can call `read_file`, `list_dir`, `write_file`, and `run`
while it works through a question. That is the debugging interface
the owner asked for. The mailbox-driven job path (`answer_queries`
-> `ask_model`) stays single-shot and constrained; only the
interactive chat gets hands. Bounds are mechanical: 10 tool rounds,
4 calls per round, bounded tool output, command timeouts, and a
context trim. The final answer goes through the same secret scan +
redaction as any other model reply. Stated risk: anything the model
reads can steer it, so a poisoned file could talk it into running
something unwise. That is the owner's explicit trade.

`oracle_window` then:

- Rejects a port that is not an integer or is outside 0..65535.
  Exit code 2.
- Sets the process log file to `<base_dir>/runner.log`. `base_dir`
  comes from the config's `base_dir` when set, otherwise the
  directory containing the config file; `~/.homing-pigeon` is the
  fallback only when no config path is known. This matters
  because a normal run assigns `_LOG_FILE` later, and `--oracle`
  returns before that assignment. Without this line the chat would
  log only to the console.
- Binds `127.0.0.1` only, via `make_oracle_server`. The host allowlist
  is `127.0.0.1`, `::1`, and `localhost`. `0.0.0.0` raises `ValueError`
  and the process exits 2. After bind, the socket's own address is
  checked again and a non-loopback address is closed and refused.
  Exit code 1 is any `OSError` from `make_oracle_server` (the port
  already taken is the common one; there is no errno check, so any
  listen failure lands here).
- Prints the URL and the path of `oracle-chat.jsonl`.
- Appends an `open` record to that file.
- Opens the browser after 0.4 seconds. Tests pass `open_browser=False`
  and never call this.
- Blocks on `serve_forever` until Ctrl+C (`KeyboardInterrupt`).
- Appends a `close` record and closes the socket. Exit code 0.

Do not put `--oracle` in the boot service. The call blocks, and it
opens a browser. The scheduled task or systemd unit must keep polling
mail. The window is a second launch of the same executable, beside
the service, reading the same `base_dir`.

## What one question does

`GET /` returns the page. `GET /status` returns the ask-progress
JSON, behind the same host and token checks. Any other GET path
is 404, including a favicon request. The page embeds a session token (`secrets.token_urlsafe`)
as JSON in the script. The token is not put in the URL, so it does
not leak via a query string or a referrer. `<` in that JSON is escaped
so a model name cannot break out of the script tag. The page builds
the transcript with `textContent`, not `innerHTML`, so a model reply
cannot inject HTML.

`POST /ask` is the only write.

- The TCP peer must be a loopback address.
- The `Host` header must be `127.0.0.1`, `localhost`, or `::1`.
- A POST that carries an `Origin` header must name `http://` plus one
  of those hosts; a foreign Origin is refused, so a page on another
  site cannot submit a question to the local port. A POST with no
  `Origin` at all is accepted when the peer is loopback and the token
  matches — some Windows WebViews omit the header, and refusing it
  made Send look dead. GET may omit `Origin` because the browser does
  not send it for a normal navigation.
- `X-Oracle-Token` must match the token from the page.
  `hmac.compare_digest` is used. A missing or wrong token is 403, and
  the body is not answered.
- The body is at most 8000 bytes. The question string is stripped and
  cut at 4000 characters. An empty question returns a fixed sentence
  and is not sent to the model and is not logged as a turn.

The question is then passed to `ask_model_agent`, the agent loop
above. (A signed `ask` query uses the separate single-shot
`ask_model`.) It is not a free chat with a raw Ollama handle.

- The system prompt is `ASK_AGENT_SYSTEM`: the interactive charter —
  answer from evidence, use the tools when the question needs the
  box itself, never invent an event, never reveal secrets.
- `owner_instructions` from config is appended to that system prompt
  when it is a non-empty string. That is how the box is told what to
  protect (for example a Desktop flag treated like a password).
- The "output" is not the raw mailbox. `oracle_context` reads
  `<base_dir>/retained/*.json`, keeps ids that match the safe job-id
  pattern, takes the six newest, and caps each stdout+stderr at 800
  characters and the whole blob at 8000. If nothing is retained, the
  output text is `(no job output retained yet)` and the model is
  supposed to say it cannot answer from the output.
- The endpoint must already be loopback. `inference_config` returns
  none otherwise, and the ask returns `inference_unconfigured`.
  The window still opens. The page says the model is off.
- The reply is truncated to `max_answer_chars`, then secret-scanned.
  A hit returns `rejected: sanitization` and the model text is
  dropped. It is not rewritten and shown. The page displays a fixed
  sentence: "The reply was dropped because it repeated protected
  material."
- Other rejections are also fixed sentences (unconfigured).
  `inference_error` is the exception: when the model supplies a
  `detail`, that text — built from the endpoint's response —
  replaces the fixed sentence (the same override exists in
  `oracle_cli`). The raw exception is not sent to the browser.

The browser keeps the visible transcript, and the chat has a short
memory besides. `recent_chat` reads `oracle-chat.jsonl` back, and the
next ask hands the model the last four `ask` turns — question and
answer each cut to 300 characters, the block capped at 2000 — so a
follow-up question can continue an investigation. What goes back is
only what was written, and what was written was redacted first:
`record_oracle_turn` passes the question, the answer, and the detail
through `redact_text` with the config's patterns before the line is
appended (see "What is written to disk" below). The protection is
redact-before-write. Turns do persist, and the last four do return
to the model, in their redacted form.

## What is written to disk

Commit `945ef68`, after the owner asked for the conversation to be
saved and also warned that an unbounded log will fill a disk.

`record_oracle_turn` appends one JSON line to
`<base_dir>/oracle-chat.jsonl`:

- `ts` in UTC
- `event`: `open`, `ask`, or `close`
- `question` and `answer`, each passed through `redact_text` with the
  config's redact patterns (built-ins plus `redact_patterns_extra`)
  before the write
- `rejected` (the code, such as `sanitization`, or empty)
- `detail`, cut at 300 characters
- `model`
- `tool_rounds`

Question is stored at most 2000 characters. Answer at most 4000.
The session token is not stored. The mailbox password is not stored.
The shared secret is not stored. The retained-job blob that was sent
to the model is not copied into the chat file on every turn. That
blob can be large and it already lives under `retained/`.

The file rolls at 1 MiB (`_ORACLE_CHAT_MAX`). When the next line would
pass that, the file is renamed to `oracle-chat.jsonl.1` and a new
file starts. One backup. The next roll replaces the backup. Worst
case is about 2 MiB for the chat. The write uses `os.open` with mode
`0o600` and `O_APPEND`, under `_LOG_WRITE_LOCK`.

`runner.log` uses the same helper, `append_bounded_log`. Its bounds
are config — `log_max_bytes` / `log_backups`, defaults 32 MiB per
file with 4 backups: the live file plus 4 rotations, about
160 MiB retained in all. Those bounds apply to every run that writes the
process log, not only `--oracle`. The per-minute
console budget is unchanged: verbose drops ordinary lines past 200 a
minute, quiet past 50, and WARN and ERROR still pass. Dropped console
lines are counted, not written. The chat file does not use that
budget. Every ask is kept until the roll. A 403 (bad token, bad
origin) is not written to the chat file, so a scanner cannot fill the
disk by posting.

## The startup crash that showed up in the same work

Commit `88fcfdf`.

`8f0719f` deleted the `oracle_enabled` flag but left one use of a
local name `oracle` inside `log_startup`:

```
if oracle and not cfg.get("workspace_root"):
    log("confinement is off; workspace_root is not set", "WARN")
```

Nothing assigns `oracle` anymore. The first real poll on the Windows
binary (the smoke step in `build.yml`) got through the startup lines
and then died:

```
NameError: name 'oracle' is not defined
```

PyInstaller reported "Failed to execute script runner". The zip was
not uploaded because the smoke step runs before the artifact step.

The fix is the condition that matches the new rule. The Oracle is
always on, so the warning does not depend on a flag:

```
if not cfg.get("workspace_root"):
    log("confinement is off; workspace_root is not set", "WARN")
```

`runner/tests/test_oracle_chat.py` calls `log_startup` with a config that
has no `workspace_root` and asserts it returns and that the warning
is printed. That test is there so the `NameError` cannot come back
quietly.

This crash is not caused by passing `--oracle`. A normal poll hit it.
It was found while the `--oracle` Windows build was smoked. Do not
"fix" it by defining `oracle = cfg.get("oracle_enabled", True)`. That
would bring the removed flag back.

## A workflow change that rode along in `15025c7`

Not part of the chat, but it is in the same commit, so a bisect will
find it here.

`validate_shared_secret` (from `89f1948`) rejects a secret that is a
short unit repeated, or that estimates under 128 bits. The Windows
smoke config used a 64-character hex string made by repeating
`0123456789abcdef`. The new checker exited 2, the smoke step failed,
and no Windows zip was published. The smoke secret was replaced with
a non-repeating 64-character hex string. Do not put a patterned
placeholder back into that workflow.

## Tests that lock the behavior

`runner/tests/test_oracle_chat.py`:

- `make_oracle_server` on `0.0.0.0` raises `ValueError`.
- `oracle_context` reads a retained job and does not follow a path
  outside `retained/`.
- The HTML has no `innerHTML` and uses `textContent`.
- A live loopback server: GET does not contain the mailbox password
  or the shared secret. POST without the token is 403. POST with an
  `Origin` of another host is 403. POST with the token reaches
  `ask_model_agent` with the retained stdout and the owner instructions.
  A question that is itself a flagged secret is answered with
  `sanitization`, and neither the HTTP body nor `oracle-chat.jsonl`
  contains the raw flag.
- `--oracle` on a config with no `mailbox_user` calls `oracle_window`
  and returns 0. It does not die on the mailbox check.
- `log_startup` without `workspace_root` does not raise.
- The chat log redacts before write, and `append_bounded_log` rolls
  to `path.1` instead of growing without a limit.

The model is mocked in these tests. They do not start Ollama and they
do not open a browser.

## What a later change must not do

- Do not add `--no-oracle` or `oracle_enabled` back.
- Do not make `--oracle` mean "disable the Oracle".
- Do not bind the chat on a non-loopback address, and do not add a
  flag that does.
- Do not drop the token check or the `Origin` check. Another site in
  the same browser can reach `127.0.0.1` if you do.
- Do not log the token, the mailbox password, or the shared secret.
- Do not write the model reply to disk before redaction and the
  secret scan.
- Do not feed the on-screen transcript back into the next `ask_model`
  call.
- Do not shell out to Open WebUI from `--oracle`.
- Do not start a second Ollama for this flag. The SI on port 11435
  belongs to the local SI test harness on `feat/local-si-test`, not
  to this flag.
- Do not put `--oracle` in the installed service command.
- Do not turn this page into a dashboard.
- Do not remove the size cap on `oracle-chat.jsonl` or `runner.log`.

## How to run it

```
homing-pigeon --config config.json --oracle
homing-pigeon --config config.json --oracle --oracle-port 11436
```

From a checkout:

```
python3 runner/runner.py --config config.json --oracle
```

Leave that process running. Ctrl+C closes it. The service that polls
mail should already be running as a separate process.
