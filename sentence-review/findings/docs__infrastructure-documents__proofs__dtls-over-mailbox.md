# Findings — docs/infrastructure-documents/proofs/dtls-over-mailbox.md

Source: docs/infrastructure-documents/proofs/dtls-over-mailbox.md, reviewed at main cbb52068.
Sentence units: 17. Flagged: 0. Categories: pre-release 17, post-release 0.

A proof record in 3 parts: the carriage and its tests, what was proven, what was not proven. Each sentence hands off to the next, including the short ones; the not-proven list is the deliberate counterweight to the proven list and connects by design. Nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The carriage is `runner/wire/dtls_mailbox.py`." | pre-release | flows |  |
| 2 | "The tests are `runner/tests/test_dtls_mailbox.py`." | pre-release | flows |  |
| 3 | "Both passed here: a job in the box…" | pre-release | flows |  |
| 4 | "Two cores, `DtlsClientCore` and `DtlsServerCore`, never handed each…" | pre-release | flows |  |
| 5 | "Each flight was one email built by `send_mail`:…" | pre-release | flows |  |
| 6 | "The peer read it back with `fetch_job_mails`, which…" | pre-release | flows |  |
| 7 | "A flight was marked seen." | pre-release | flows |  |
| 8 | "A job object in the same box, subject…" | pre-release | flows |  |
| 9 | "The handshake ran to `established` on both sides." | pre-release | flows |  |
| 10 | "The client then sent the application message `ping`." | pre-release | flows |  |
| 11 | "The server recorded that payload." | pre-release | flows |  |
| 12 | "The box is in-process." | pre-release | flows |  |
| 13 | "It answers the UID commands `fetch_job_mails` calls." | pre-release | flows |  |
| 14 | "It is not an IMAP server, and no…" | pre-release | flows |  |
| 15 | "There is no loss, no reorder, and no…" | pre-release | flows |  |
| 16 | "The ping is three bytes, not a job,…" | pre-release | flows |  |
| 17 | "A real mailbox that rejects a long line,…" | pre-release | flows |  |
