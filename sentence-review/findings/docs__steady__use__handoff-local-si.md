# Findings — docs/steady/use/handoff-local-si.md

Source: docs/steady/use/handoff-local-si.md, reviewed at main cbb52068.
Sentence units: 59. Flagged: 1. Categories: pre-release 59, post-release 0.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Historical note from the `feat/local-si-test` work." | pre-release | flows |  |
| 2 | "A local test where a person talks to…" | pre-release | flows |  |
| 3 | "The two models do not share a context." | pre-release | flows |  |
| 4 | "`--local-test` starts the harness." | pre-release | flows |  |
| 5 | "`--browser` opens **Open WebUI**, the chat interface people…" | pre-release | flows |  |
| 6 | "One text box, one send button." | pre-release | flows |  |
| 7 | "Open WebUI is pointed at the SI Ollama…" | pre-release | flows |  |
| 8 | "The Oracle stays on its configured endpoint (usually…" | pre-release | flows |  |
| 9 | "Send in the chat talks to the SI." | pre-release | flows |  |
| 10 | "Nothing emails the SI's reply anywhere: browser mode…" | pre-release | flows |  |
| 11 | "(A separate harness function, `send_via_email`, sends a signed…" | pre-release | flows |  |
| 12 | "If Open WebUI is not installed, the harness…" | pre-release | flows |  |
| 13 | "It does not fall back to a homemade…" | pre-release | flows |  |
| 14 | "**SI** — second `ollama serve` with `OLLAMA_HOST=127.0.0.1:11435`." | pre-release | flows |  |
| 15 | "This is the chatbot the user talks to." | pre-release | flows |  |
| 16 | "**Oracle** — the runner's inference endpoint." | pre-release | flows |  |
| 17 | "Separate process, separate port, separate context." | pre-release | flows |  |
| 18 | "The user never talks to the Oracle or…" | pre-release | flows |  |
| 19 | "They tell the SI what to do." | pre-release | flows |  |
| 20 | "The SI sends it." | pre-release | flows |  |
| 21 | "The transport this harness exercises is email." | pre-release | flows |  |
| 22 | "The mock SI reads `config.json` (`smtp_host`, `smtp_port`, `mailbox_user`,…" | pre-release | flows |  |
| 23 | "A runner polling that mailbox picks it up." | pre-release | flows |  |
| 24 | "Do not add another transport unless asked." | pre-release | flows |  |
| 25 | "The harness uses no adapter module; in the…" | pre-release | flows |  |
| 26 | "Status: `docs/transports-status.md`." | pre-release | flows |  |
| 27 | "Transport ; State" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 28 | "email ; implemented, this is what the harness…" | pre-release | flows |  |
| 29 | "cloudflare ; not in the runner" | pre-release | flows |  |
| 30 | "nats ; implemented as a transport extension; not…" | pre-release | flows |  |
| 31 | "local_socket, mqtt, redis, durable_objects, postgres ; cut on…" | pre-release | flows |  |
| 32 | "Direct "ask the Oracle" button." | pre-release | flows |  |
| 33 | "It skipped the SI and called the Oracle…" | pre-release | flows |  |
| 34 | "The button is gone from the page, but…" | pre-release | flows |  |
| 35 | "Separately, the runner's own Oracle window serves its…" | pre-release | flows |  |
| 36 | "Extra buttons." | pre-release | flows |  |
| 37 | "A chatbot has one text box and one…" | pre-release | flows |  |
| 38 | "Homemade chat page." | pre-release | flows |  |
| 39 | "Replaced by Open WebUI." | pre-release | flows |  |
| 40 | "Not part of this branch's unique commits, but…" | pre-release | flows |  |
| 41 | "Owner instructions: `--instructions` replaces, `--instructions-add` appends." | pre-release | flows |  |
| 42 | "Stored as `owner_instructions`." | pre-release | flows |  |
| 43 | "Included in the Oracle system prompt." | pre-release | flows |  |
| 44 | "Hard Oracle system prompt in `ASK_SYSTEM`." | pre-release | flows |  |
| 45 | "Config hot-reload updates the local model (`update_llama_from_config`)." | pre-release | flows |  |
| 46 | "Installer can set up Ollama by default; `--no-inference`…" | pre-release | flows |  |
| 47 | "Privacy budget defaults: `max_query_budget` 8, `output_retention_days` 7." | pre-release | flows |  |
| 48 | "`runner/local_test.py` — the harness" | pre-release | flows |  |
| 49 | "`docs/local-si-test.md` — how to run it" | pre-release | flows |  |
| 50 | "`docs/transports-status.md` — transport table" | pre-release | flows |  |
| 51 | "`docs/handoff-local-si.md` — this file" | pre-release | flows |  |
| 52 | "`tests/test_local_si.py`, `tests/test_local_si_blast.py`, `tests/test_local_si_transport.py`" | pre-release | flows |  |
| 53 | "Unbuilt work is listed in FUTURE.md." | pre-release | flows |  |
| 54 | "These notes are not a queue." | pre-release | flows |  |
| 55 | "A live Cloudflare try was planned and was…" | pre-release | flows |  |
| 56 | "Queues are still not in the runner." | pre-release | flows |  |
| 57 | "Open WebUI env var: confirmed — `runner/local_test.py` sets…" | pre-release | flows |  |
| 58 | "The chat confirms the send." | pre-release | flows |  |
| 59 | "It does not wait for the result email…" | pre-release | flows |  |
