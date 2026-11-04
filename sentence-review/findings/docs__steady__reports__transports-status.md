# Findings — docs/steady/reports/transports-status.md

Source: docs/steady/reports/transports-status.md, reviewed at main ff2ea758.
Sentence units: 15. Flagged: 2. Categories: pre-release 15, post-release 0.

An archived 2026-10-22 status table of the transports, with a short frame and a standing instruction. The table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "**Archived 2026-10-22.** A short status table superseded by…" | pre-release | flows |  |
| 2 | "Transports are extensions in full." | pre-release | flows |  |
| 3 | "The runner core is transport-blind: `runner/transports.py` is the…" | pre-release | flows |  |
| 4 | "The runner never imports extension code; it supervises…" | pre-release | flows |  |
| 5 | "The contract is described in TRANSPORTS.md." | pre-release | flows |  |
| 6 | "Ack is consumption: the runner moves a processed…" | pre-release | flows |  |
| 7 | "| Transport | State |" | pre-release | flagged | A table header row — structure, not a sentence |
| 8 | "|-----------|-------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 9 | "| email | implemented (extension over `runner/mailbox.py`: IMAP…" | pre-release | flows |  |
| 10 | "| file | implemented (watched folder) |" | pre-release | flows |  |
| 11 | "| nats | implemented (core NATS pub/sub; broker…" | pre-release | flows |  |
| 12 | "| dtls | implemented (DTLS session listener; off…" | pre-release | flows |  |
| 13 | "| cloudflare | design notes in TRANSPORTS.md only;…" | pre-release | flows |  |
| 14 | "MQTT, Redis, Postgres, and Durable Objects were cut…" | pre-release | flows |  |
| 15 | "Do not add transports unless asked." | pre-release | flows |  |
