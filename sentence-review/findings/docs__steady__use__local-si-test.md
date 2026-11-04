# Findings — docs/steady/use/local-si-test.md

Source: docs/steady/use/local-si-test.md, reviewed at main cbb52068.
Sentence units: 78. Flagged: 0. Categories: pre-release 78, post-release 0.

Unit 41's sentence wraps across a line break in the source (the port number stands at the wrap); it is recorded whole.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "See `docs/archive/handoff-local-si.md` for the full handoff (two instances,…" | pre-release | flows |  |
| 2 | "`--local-test` (in-process) is the development loop." | pre-release | flows |  |
| 3 | "You play the cloud SI; nothing is emailed." | pre-release | flows |  |
| 4 | "See "Run it" below." | pre-release | flows |  |
| 5 | "The email harness (next section) exercises the real…" | pre-release | flows |  |
| 6 | "`--browser` opens Open WebUI against a second Ollama." | pre-release | flows |  |
| 7 | "It is a generic chat skin, not the…" | pre-release | flows |  |
| 8 | "`--diagnose` is the one-shot black-box gauntlet (last section)." | pre-release | flows |  |
| 9 | "It probes the configured system; it does not…" | pre-release | flows |  |
| 10 | "The mock SI is tested through email." | pre-release | flows |  |
| 11 | "That is Transport #1 and the only transport…" | pre-release | flows |  |
| 12 | "The harness's own local socket was cut from…" | pre-release | flows |  |
| 13 | "To run the email test you need a…" | pre-release | flows |  |
| 14 | "The SI sends a signed job." | pre-release | flows |  |
| 15 | "The runner picks it up, runs it, and…" | pre-release | flows |  |
| 16 | "A development loop for the Oracle." | pre-release | flows |  |
| 17 | "You play the cloud SI." | pre-release | flows |  |
| 18 | "The harness ensures the local model is up,…" | pre-release | flows |  |
| 19 | "The Oracle answers." | pre-release | flows |  |
| 20 | "Nothing is emailed." | pre-release | flows |  |
| 21 | "This is not a unit test." | pre-release | flows |  |
| 22 | "It is a self-hosted chat against the real…" | pre-release | flows |  |
| 23 | "Terminal chat." | pre-release | flows |  |
| 24 | "Type a question. `quit` exits." | pre-release | flows |  |
| 25 | "Opens **Open WebUI**, the chat interface people use…" | pre-release | flows |  |
| 26 | "It is pointed at the SI Ollama instance…" | pre-release | flows |  |
| 27 | "Install it once with `pip install open-webui`." | pre-release | flows |  |
| 28 | "The page is a normal chat: one text…" | pre-release | flows |  |
| 29 | "`inference.endpoint` and `inference.model` in `config.json`, and the endpoint…" | pre-release | flows |  |
| 30 | "The installer sets this up unless you passed…" | pre-release | flows |  |
| 31 | "Ollama (or another OpenAI-compatible server) running on that…" | pre-release | flows |  |
| 32 | "The harness starts the daemon if it is…" | pre-release | flows |  |
| 33 | "Use it while developing the Oracle:" | pre-release | flows |  |
| 34 | "Run `--local-test`." | pre-release | flows |  |
| 35 | "Ask something." | pre-release | flows |  |
| 36 | "Read the answer." | pre-release | flows |  |
| 37 | "Edit `owner_instructions` or the hard system prompt." | pre-release | flows |  |
| 38 | "Restart `--local-test` (it holds the config it started…" | pre-release | flows |  |
| 39 | "Repeat." | pre-release | flows |  |
| 40 | "The point is a tight loop between "what…" | pre-release | flows |  |
| 41 | "`--browser` starts a **second** Ollama process for the…" | pre-release | flows |  |
| 42 | "The Oracle keeps using its configured endpoint (usually…" | pre-release | flows |  |
| 43 | "Separate process, separate port, separate context." | pre-release | flows |  |
| 44 | "The page has no mode buttons — it…" | pre-release | flows |  |
| 45 | "The separation is structural, not a button: the…" | pre-release | flows |  |
| 46 | "The SI never sees the Oracle's context, and…" | pre-release | flows |  |
| 47 | "That is the point of two instances." | pre-release | flows |  |
| 48 | "The mock SI reads the same `config.json` as…" | pre-release | flows |  |
| 49 | "**In-process** — the default." | pre-release | flows |  |
| 50 | "The question is handed to the Oracle path…" | pre-release | flows |  |
| 51 | "No email, no socket." | pre-release | flows |  |
| 52 | "Fastest for a single chat." | pre-release | flows |  |
| 53 | "**Email** — `send_via_email` in `runner/ops/local_test.py`, a helper the…" | pre-release | flows |  |
| 54 | "The runner must be polling that mailbox to…" | pre-release | flows |  |
| 55 | "This is the real Transport #1 path." | pre-release | flows |  |
| 56 | "A loopback-socket option (`127.0.0.1:8766`) was specified in an…" | pre-release | flows |  |
| 57 | "In-process and email are the two working paths." | pre-release | flows |  |
| 58 | "An earlier revision specified a loopback-TCP framing here…" | pre-release | flows |  |
| 59 | "It was never implemented and was cut." | pre-release | flows |  |
| 60 | "For volume testing today, use the in-process path…" | pre-release | flows |  |
| 61 | "`--local-test` is a development loop. `--diagnose` is the…" | pre-release | flows |  |
| 62 | "Start the runner normally first (service or console).…" | pre-release | flows |  |
| 63 | "It does not start daemons or fix anything…" | pre-release | flows |  |
| 64 | "Sections, in order:" | pre-release | flows |  |
| 65 | "**banner** — version, protocol version, config path, state…" | pre-release | flows |  |
| 66 | "**config** — required keys present; the shared secret's…" | pre-release | flows |  |
| 67 | "**mailbox** — IMAP connect, login, folder list; SMTP…" | pre-release | flows |  |
| 68 | "**model** — the configured model is listed by…" | pre-release | flows |  |
| 69 | "**round-trip** — a signed trivial `exec` job (`echo…" | pre-release | flows |  |
| 70 | "A no-show is reported as "the runner may…" | pre-release | flows |  |
| 71 | "**oracle-context** — the context the chat path builds:…" | pre-release | flows |  |
| 72 | "**oracle-probes** — the five acceptance probes through the…" | pre-release | flows |  |
| 73 | "Only mechanical flags: an empty or rejected answer…" | pre-release | flows |  |
| 74 | "**senses** — canary status, registry watch, and event-log…" | pre-release | flows |  |
| 75 | "Unreadable is reported as unreadable, never as clean." | pre-release | flows |  |
| 76 | "Each section streams one verdict line (`[PASS] model…" | pre-release | flows |  |
| 77 | "The full report lands in `harness-report-.txt` in the…" | pre-release | flows |  |
| 78 | "The shared secret and mailbox password never appear…" | pre-release | flows |  |
