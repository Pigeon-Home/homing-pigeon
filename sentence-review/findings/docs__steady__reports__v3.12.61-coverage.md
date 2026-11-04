# Findings — docs/steady/reports/v3.12.61-coverage.md

Source: docs/steady/reports/v3.12.61-coverage.md, reviewed at main e2a8e8e2.
Sentence units: 64. Flagged: 4. Categories: pre-release 64, post-release 0.

A generated coverage snapshot for 3.12.61: totals and per-module tables with a short frame. The frame connects; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.12.61." | pre-release | flows |  |
| 2 | "The previous measurement is [v3.12.20](../v3.12.20/coverage.md)." | pre-release | flows |  |
| 3 | "No new tag was cut for this measurement." | pre-release | flows |  |
| 4 | "It is main at 891bbd8." | pre-release | flows |  |
| 5 | "The runner modules sit in `oracle/`, `wire/`, `guard/`,…" | pre-release | flows |  |
| 6 | "Measured 2026-10-24 with coverage.py 7.16.2, on Python 3.11.2." | pre-release | flows |  |
| 7 | "Hypothesis 6.170.3 was installed." | pre-release | flows |  |
| 8 | "CI pins hypothesis 6.170.5." | pre-release | flows |  |
| 9 | "5426 tests, 1 failure, 22 skipped." | pre-release | flows |  |
| 10 | "453 seconds." | pre-release | flows |  |
| 11 | "The failure is `test_all_eight_shapes` variant `hostinfo`: the script…" | pre-release | flows |  |
| 12 | "The other seven shapes passed." | pre-release | flows |  |
| 13 | "The 22 skips are optional tools that were…" | pre-release | flows |  |
| 14 | "| | Covered | Missed | Total |" | pre-release | flagged | A table header row — structure, not a sentence |
| 15 | "|---|---:|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 16 | "| Statements | 95.2% | 932 | 19260…" | pre-release | flows |  |
| 17 | "| Branches | 92.7% | 573 | 7842…" | pre-release | flows |  |
| 18 | "| Statements and branches | 94.4% | |…" | pre-release | flows |  |
| 19 | "`runner/tests/`, `runner/tools/`, and `runner/extensions/` are left out of…" | pre-release | flows |  |
| 20 | "The suite and the CI scripts are the…" | pre-release | flows |  |
| 21 | "The shipped extensions used to live in `extensions/`,…" | pre-release | flows |  |
| 22 | "`runner/cloud/` does count." | pre-release | flows |  |
| 23 | "Without those two files the statement figure is…" | pre-release | flows |  |
| 24 | "The files still under 96%, by statements:" | pre-release | flows |  |
| 25 | "| File | Covered | Missed |" | pre-release | flagged | A table header row — structure, not a sentence |
| 26 | "|---|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 27 | "| cloud/send_dtls.py | 36.6% | 97 |" | pre-release | flows |  |
| 28 | "| cloud/send_job.py | 69.5% | 90 |" | pre-release | flows |  |
| 29 | "| transport_extensions/nats/__main__.py | 79.8% | 46 |" | pre-release | flows |  |
| 30 | "| transport_extensions/dtls/__main__.py | 81.5% | 33 |" | pre-release | flows |  |
| 31 | "| transport_extensions/email/__main__.py | 85.4% | 18 |" | pre-release | flows |  |
| 32 | "| wire/platformcard.py | 88.6% | 5 |" | pre-release | flows |  |
| 33 | "| ops/extsources.py | 90.7% | 129 |" | pre-release | flows |  |
| 34 | "| oracle/resources.py | 92.8% | 14 |" | pre-release | flows |  |
| 35 | "| ops/auditreport.py | 93.5% | 15 |" | pre-release | flows |  |
| 36 | "| guard/security.py | 93.5% | 15 |" | pre-release | flows |  |
| 37 | "| guard/confval.py | 94.0% | 3 |" | pre-release | flows |  |
| 38 | "| wire/mailbox.py | 94.2% | 11 |" | pre-release | flows |  |
| 39 | "| oracle/detection.py | 94.3% | 10 |" | pre-release | flows |  |
| 40 | "| wire/oauth.py | 94.4% | 13 |" | pre-release | flows |  |
| 41 | "| wire/verify.py | 95.0% | 23 |" | pre-release | flows |  |
| 42 | "| oracle/dri.py | 95.1% | 20 |" | pre-release | flows |  |
| 43 | "| wire/board.py | 95.5% | 13 |" | pre-release | flows |  |
| 44 | "| wire/protocol_v2.py | 95.8% | 15 |" | pre-release | flows |  |
| 45 | "| runner.py | 95.8% | 271 |" | pre-release | flows |  |
| 46 | "`runner.py` is 95.8% (271 missed of 6388)." | pre-release | flows |  |
| 47 | "The floor is the two cloud helpers." | pre-release | flows |  |
| 48 | "The transport programs that open a socket or…" | pre-release | flows |  |
| 49 | "Statement coverage, 40 cells, one cell is 2.5…" | pre-release | flows |  |
| 50 | "`runner/__init__.py` and `runner/_version.py` are one or two statements…" | pre-release | flows |  |
| 51 | "So are `harness.py`, `local_test.py`, `posture.py`, and `setup.py`, under…" | pre-release | flows |  |
| 52 | "That report's later figure was 96.8% of 16872…" | pre-release | flows |  |
| 53 | "This tree has 19260 statements and 932 missed." | pre-release | flows |  |
| 54 | "The percent is 95.2." | pre-release | flows |  |
| 55 | "The two cloud helpers were not in that…" | pre-release | flows |  |
| 56 | "They live in the package now, and they…" | pre-release | flows |  |
| 57 | "The rest of the tree is the same…" | pre-release | flows |  |
| 58 | "From the repo root, with coverage.py installed." | pre-release | flows |  |
| 59 | "It is a measurement tool, not a project…" | pre-release | flows |  |
| 60 | "Install hypothesis first if you want the property…" | pre-release | flows |  |
| 61 | "Use Python 3.11 or newer." | pre-release | flows |  |
| 62 | "Expect about eight minutes." | pre-release | flows |  |
| 63 | "The omit is required." | pre-release | flows |  |
| 64 | "The suite now lives inside `runner/`, and a…" | pre-release | flows |  |
