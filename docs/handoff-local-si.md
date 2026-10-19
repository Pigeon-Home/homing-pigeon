# Handoff: local SI test and transports

Historical note from the `feat/local-si-test` work. The transport
table that used to sit here said Cloudflare, NATS, MQTT, Redis, and
the rest were send-ready. That was wrong then and it is wrong now.
`runner/transports.py` was removed. Email is the only transport in
the runner. See `docs/transports-status.md`. Do not treat "try
Cloudflare tomorrow" as an open task.

## What this is

A local test where a person talks to a **cloud SI** (a Llama), and
that SI sends work to the **Oracle** (a different Llama on the same
machine) through a real transport. The two models do not share a
context.

## How to run it

```
pip install open-webui
python3 runner/runner.py --config config.json --local-test --browser
```

- `--local-test` starts the harness.
- `--browser` opens **Open WebUI**, the chat interface people use
  with a self-hosted Llama. One text box, one send button.
- Open WebUI is pointed at the SI Ollama instance on port **11435**.
- The Oracle stays on its configured endpoint (usually **11434**).
- Send in the chat talks to the SI. Nothing emails the SI's reply
  anywhere: browser mode only opens Open WebUI at the SI instance.
  (A separate harness function, `send_via_email`, sends a signed
  ask job through the real email transport.)

If Open WebUI is not installed, the harness says so and exits. It
does not fall back to a homemade page.

## Two instances

- **SI** — second `ollama serve` with `OLLAMA_HOST=127.0.0.1:11435`.
  This is the chatbot the user talks to.
- **Oracle** — the runner's inference endpoint. Separate process,
  separate port, separate context.

The user never talks to the Oracle or the mailbox directly. They
tell the SI what to do. The SI sends it.

## Testing is email only

The transport this harness exercises is email. The mock SI reads
`config.json` (`smtp_host`, `smtp_port`, `mailbox_user`, password or
OAuth) and sends a signed `[HOMING-PIGEON] job …` message. A runner
polling that mailbox picks it up. Do not add another transport
unless asked.

## Transports

There is no adapter module. Status: `docs/transports-status.md`.

| Transport | State |
|-----------|--------|
| email | implemented, this is what the harness tests |
| cloudflare | not in the runner |
| local_socket, nats, mqtt, redis, durable_objects, postgres | cut on purpose |

## What was removed on purpose

- Direct "ask the Oracle" button. It skipped the SI and called the
  Oracle path in-process. The button is gone from the page, but the
  direct path itself still ships: `runner/local_test.py`'s
  `answer_as_oracle()` / `repl()` run asks in-process. Separately,
  the runner's own Oracle window serves its page at `/` with
  `POST /ask`; only other paths 404.
- Extra buttons. A chatbot has one text box and one send button.
- Homemade chat page. Replaced by Open WebUI.

## Related earlier work already on main

Not part of this branch's unique commits, but context:

- Owner instructions: `--instructions` replaces, `--instructions-add`
  appends. Stored as `owner_instructions`. Included in the Oracle
  system prompt.
- Hard Oracle system prompt in `ASK_SYSTEM`.
- Config hot-reload updates the local model (`update_llama_from_config`).
- Installer can set up Ollama by default; `--no-inference` skips it.
- Privacy budget defaults: `max_query_budget` 8, `output_retention_days` 7.

## Files

- `runner/local_test.py` — the harness
- `docs/local-si-test.md` — how to run it
- `docs/transports-status.md` — transport table
- `docs/handoff-local-si.md` — this file
- `tests/test_local_si.py`, `tests/test_local_si_blast.py`,
  `tests/test_local_si_transport.py`

## Open items left in this note

Unbuilt work is listed in FUTURE.md. These notes are not a queue.

1. A live Cloudflare try was planned and was not done. Queues are
   still not in the runner.
2. Confirm Open WebUI env var `OLLAMA_BASE_URL` is the one that
   build honors, if you run `--local-test --browser`.
3. The chat confirms the send. It does not wait for the result
   email unless someone adds that later.
