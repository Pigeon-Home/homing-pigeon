# Handoff: local SI test and transports

Branch: `feat/local-si-test`
For the next Grok chat. This is the state of the work from the
conversation that built it.

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
- Send in the chat talks to the SI. The SI's reply is what gets
  emailed to the Oracle.

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

The transport we exercise is email (Transport #1). The mock SI reads
`config.json` (`smtp_host`, `smtp_port`, `mailbox_user`, password or
OAuth) and sends a signed `[HOMING-PIGEON] job …` message. A runner
polling that mailbox picks it up.

The owner will try Cloudflare tomorrow. Do not add more transport
tests unless asked. Email is the one under test.

## Transports (ready, not all tested)

Code: `runner/transports.py`. Contract: `send`, `poll`, `ack`.
Status: `docs/transports-status.md`.

| Transport | State |
|-----------|--------|
| email | implemented, this is what we test |
| cloudflare | send, poll, ack ready. Config: `cf_account_id`, `cf_api_token`, `cf_queue_id`. Next live try. |
| local_socket | loopback TCP, test harness only |
| nats | send ready (`nats_host`, `nats_port`) |
| mqtt | send ready (`mqtt_host`, `mqtt_port`) |
| redis | send ready (`redis_host`, `redis_port`) |
| durable_objects | send ready (`do_url`, `cf_api_token`) |
| postgres | config-ready (`pg_dsn`); wire protocol not bundled |

## What was removed on purpose

- Direct "ask the Oracle" button. It skipped the SI and called the
  Oracle path in-process. Gone. `/oracle` is 404.
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
- `runner/transports.py` — transport adapters
- `docs/local-si-test.md` — how to run it
- `docs/transports-status.md` — transport table
- `docs/handoff-local-si.md` — this file
- `tests/test_local_si.py`, `tests/test_local_si_blast.py`,
  `tests/test_local_si_transport.py`, `tests/test_transports.py`

## Open items for the next chat

1. Live Cloudflare try (owner said tomorrow).
2. Confirm Open WebUI env var `OLLAMA_BASE_URL` is the one that
   build honors; adjust if the current release uses a different name.
3. Decide whether send-from-chat should wait for the result email
   and show it, or only confirm the send.
