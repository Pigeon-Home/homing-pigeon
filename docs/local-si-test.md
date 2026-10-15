See `docs/handoff-local-si.md` for the full handoff (two instances, email-only testing, transports, what was removed).

# Local SI test

## Testing is email only

The mock SI is tested through email. That is Transport #1 and the
only transport this harness exercises. The local socket and the
other brokers exist in the tree for later; they are not part of
this test.

To run the email test you need a real mailbox in `config.json`
(`smtp_host`, `smtp_port`, `mailbox_user`, password or OAuth) and a
runner polling that same mailbox. The SI sends a signed job. The
runner picks it up, runs it, and emails the result back.


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
4. The runner hot-reloads config; re-ask and compare.
5. Repeat.

The point is a tight loop between "what the SI would ask" and "what
the Oracle actually says", on one machine, with no mailbox in the way.

## Two instances

`--browser` starts a **second** Ollama process for the SI, on port
11435. The Oracle keeps using its configured endpoint (usually 11434).
Separate process, separate port, separate context.

The page has two buttons:

- **talk to SI** — your message goes to the SI model only.
- **ask the Oracle** — your message is sent through the Oracle path
  to the other model.

The SI never sees the Oracle's context, and the Oracle never sees the
SI's chat. That is the point of two instances.

## Transports the mock SI can use

The mock SI reads the same `config.json` as the runner.

- **In-process** — the default. The question is handed to the Oracle
  path directly. No email, no socket. Fastest for a single chat.
- **Email** — `send email` on the page (or `send_via_email` in code)
  builds a signed job and sends it with the runner's SMTP settings
  (`smtp_host`, `smtp_port`, `mailbox_user`, password or OAuth). The
  runner must be polling that mailbox to pick it up. This is the real
  Transport #1 path.
- **Local socket** — a loopback TCP listener on `127.0.0.1:8766`.
  Length-prefixed signed blobs, one question per connection. No
  broker, no mailbox. This is the high-throughput local option: many
  asks per second on one machine, still two model instances.

Other transports in TRANSPORTS.md (Cloudflare Queues, NATS, MQTT,
Redis, Postgres) are not wired into this harness. The socket path is
the local stand-in when you want volume without a queue service.

## High-throughput local transport

Email is the wrong tool for a tight local loop. A mailbox poll is
seconds; a socket round trip is milliseconds.

The harness speaks a tiny framing: 4-byte big-endian length, then the
UTF-8 question. The listener runs the question through the Oracle
path and writes the answer back the same way. Bind is `127.0.0.1`
only.

Why sockets and not a Unix domain socket: Windows (a supported
platform) does not have the same Unix-socket story, and a loopback
TCP port works everywhere the runner runs. Why not HTTP for this
path: the browser page is already HTTP; the socket path is for
scripted volume, not for a person clicking. See TRANSPORTS.md for
the broker options when the SI is not on the same machine.
