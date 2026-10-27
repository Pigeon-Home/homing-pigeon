See `docs/archive/handoff-local-si.md` for the full handoff (two instances, email-only testing, transports, what was removed).

# Local SI test

## Status — read this first

- `--local-test` (in-process) is the development loop. You play the
  cloud SI; nothing is emailed. See "Run it" below.
- The email harness (next section) exercises the real Transport #1
  path through a mailbox the runner polls.
- `--browser` opens Open WebUI against a second Ollama. It is a
  generic chat skin, not the Oracle page.
- `--diagnose` is the one-shot black-box gauntlet (last section).
  It probes the configured system; it does not fix it.

## The email harness

The mock SI is tested through email. That is Transport #1 and the
only transport this harness exercises. The harness's own local
socket was cut from the code (the runner's shipped loopback
local-signal socket is a different thing — it carries signed
sensor alerts, not jobs); the broker transports are not part of
this test.
See docs/project/future.md.

To run the email test you need a real mailbox in `config.json`
(`smtp_host`, `smtp_port`, `mailbox_user`, password or OAuth) and a
runner polling that same mailbox. The SI sends a signed job. The
runner picks it up, runs it, and emails the result back (to the
mailbox, or to the job's `reply_to` address if one was set).


A development loop for the Oracle. You play the cloud SI. The harness
ensures the local model is up, then each thing you type is an `ask`
sent through the protocol path. The Oracle answers. Nothing is emailed.

This is not a unit test. It is a self-hosted chat against the real
Oracle path, so you can change the system prompt, the owner
instructions, or the model and see the effect immediately.

## Run it

```
python3 runner/runner.py --config config.json --local-test
```

Terminal chat. Type a question. `quit` exits.

```
python3 runner/runner.py --config config.json --local-test --browser
```

Opens **Open WebUI**, the chat interface people use with a self-hosted
Llama. It is pointed at the SI Ollama instance (port 11435), not the
Oracle. Install it once with `pip install open-webui`. The page is a
normal chat: one text box, one send button, conversation history.

## What it needs

- `inference.endpoint` and `inference.model` in `config.json`, and the
  endpoint must be loopback. The installer sets this up unless you
  passed `--no-inference`.
- Ollama (or another OpenAI-compatible server) running on that
  endpoint. The harness starts the daemon if it is down.

## Recursive feedback

Use it while developing the Oracle:

1. Run `--local-test`.
2. Ask something. Read the answer.
3. Edit `owner_instructions` or the hard system prompt.
4. Restart `--local-test` (it holds the config it started with;
   only the polling runner hot-reloads), re-ask and compare.
5. Repeat.

The point is a tight loop between "what the SI would ask" and "what
the Oracle actually says", on one machine, with no mailbox in the way.

## Two instances

`--browser` starts a **second** Ollama process for the SI, on port
11435. The Oracle keeps using its configured endpoint (usually 11434).
Separate process, separate port, separate context.

The page has no mode buttons — it is the plain chat described above,
one text box and one send button. The separation is structural, not
a button: the SI chat runs against the second instance (port 11435),
the Oracle against its configured endpoint. The SI never sees the
Oracle's context, and the Oracle never sees the SI's chat. That is
the point of two instances.

## Transports the mock SI can use

The mock SI reads the same `config.json` as the runner.

- **In-process** — the default. The question is handed to the Oracle
  path directly. No email, no socket. Fastest for a single chat.
- **Email** — `send_via_email` in `runner/ops/local_test.py`, a
  helper the suite drives (no REPL command or flag reaches it),
  builds a signed job and sends it with the runner's SMTP settings
  (`smtp_host`, `smtp_port`, `mailbox_user`, password or OAuth). The
  runner must be polling that mailbox to pick it up, and since the
  helper sends the plain signed body, running `--allow-cleartext`.
  This is the real Transport #1 path.

A loopback-socket option (`127.0.0.1:8766`) was specified in an
earlier revision but never implemented; it was cut. In-process
and email are the two working paths.

## High-throughput local transport — cut

An earlier revision specified a loopback-TCP framing here (4-byte
big-endian length, UTF-8 question, answer back the same way,
`127.0.0.1` only). It was never implemented and was cut. For
volume testing today, use the in-process
path or the real email transport.

## Diagnose mode — the black-box gauntlet

`--local-test` is a development loop. `--diagnose` is the opposite:
a one-shot diagnostic that exercises the **real configured system**
from outside and writes a verdict report.

```
python3 runner/runner.py --config config.json --diagnose
python3 runner/runner.py --config config.json --diagnose --diagnose-timeout 60
```

Start the runner normally first (service or console). `--diagnose`
is a separate process probing the same config, mailbox, model, and
state directory. It does not start daemons or fix anything up; it
measures the system as it is. Sections, in order:

0. **banner** — version, protocol version, config path, state dir,
   runner identity, platform.
1. **config** — required keys present; the shared secret's length
   and estimated entropy (never its value) and whether it passes the
   startup entropy gate; the inference endpoint's loopback check;
   confinement posture.
2. **mailbox** — IMAP connect, login, folder list; SMTP connect
   (nothing is sent by this section).
3. **model** — the configured model is listed by the endpoint, and
   one minimal chat completion is timed (cold latency).
4. **round-trip** — a signed trivial `exec` job (`echo <nonce>`) is
   emailed to the runner's own mailbox; the harness polls for the
   result (default up to 120s, `--diagnose-timeout` to change),
   verifies its signature, and checks the nonce came back with a
   success exit. A no-show is reported as "the runner may not be
   polling", not as a hang.
5. **oracle-context** — the context the chat path builds: size,
   section headers, and the computed Job index lines verbatim.
6. **oracle-probes** — the five acceptance probes through the
   in-process ask path, with full transcripts and per-probe latency
   in the report. Only mechanical flags: an empty or rejected answer
   is a FAIL.
7. **senses** — canary status, registry watch, and event-log (or
   host log) readability, exactly as the Oracle context reports
   them. Unreadable is reported as unreadable, never as clean.

Each section streams one verdict line (`[PASS] model — ...`) as it
completes and is fault-isolated: a section that blows up is a FAIL
for that section, the rest still run. The full report lands in
`harness-report-<UTC timestamp>.txt` in the state dir, and the exit
code is the number of FAIL sections. The shared secret and mailbox
password never appear in the output or the report.
