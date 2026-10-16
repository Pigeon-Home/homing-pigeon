See `docs/handoff-local-si.md` for the full handoff (two instances, email-only testing, transports, what was removed).

# Local SI test

## Testing is email only

The mock SI is tested through email. That is Transport #1 and the
only transport this harness exercises. The local socket and the
other broker transports were cut from the code; they are not part
of this test.

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

A loopback-socket option (`127.0.0.1:8766`) was specified in an
earlier revision but never implemented; it was cut with the other
broker transports. In-process and email are the two working paths.

## High-throughput local transport — cut

An earlier revision specified a loopback-TCP framing here (4-byte
big-endian length, UTF-8 question, answer back the same way,
`127.0.0.1` only). It was never implemented and was cut with the
other broker transports. For volume testing today, use the in-process
path or the real email transport.
