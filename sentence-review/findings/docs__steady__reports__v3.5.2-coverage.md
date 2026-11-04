# Findings — docs/steady/reports/v3.5.2-coverage.md

Source: docs/steady/reports/v3.5.2-coverage.md, reviewed at main e2a8e8e2.
Sentence units: 87. Flagged: 8. Categories: pre-release 87, post-release 0.

A generated coverage snapshot for 3.5.2: 4 tables with a short frame. The frame connects; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to release v3.5.2." | pre-release | flows |  |
| 2 | "It was remeasured on 2026-10-17." | pre-release | flows |  |
| 3 | "The current numbers are in [v3.11.1](../../reports/v3.11.1/coverage.md)." | pre-release | flows |  |
| 4 | "The numbers below are that day's measurement, not…" | pre-release | flows |  |
| 5 | "The package version is 3.5.2 and the latest…" | pre-release | flows |  |
| 6 | "Measured on main at c48aece, 14 commits after…" | pre-release | flows |  |
| 7 | "No new tag was cut for this measurement." | pre-release | flows |  |
| 8 | "![85 percent of statements covered](overall.png)" | pre-release | flows |  |
| 9 | "![Coverage by file](by_file.png)" | pre-release | flows |  |
| 10 | "![Before the seam tests, then after](before_after.png)" | pre-release | flows |  |
| 11 | "![85 percent](picture-overall.jpg)" | pre-release | flows |  |
| 12 | "![Coverage by file, pictured](picture-by-file.jpg)" | pre-release | flows |  |
| 13 | "![Before, then after, pictured](picture-before-after.jpg)" | pre-release | flows |  |
| 14 | "Measured 2026-10-16 with coverage.py 7.16.2." | pre-release | flows |  |
| 15 | "1005 tests, OK, 48.0 seconds under coverage." | pre-release | flows |  |
| 16 | "Statements: 4714." | pre-release | flows |  |
| 17 | "Missed: 694." | pre-release | flows |  |
| 18 | "Covered: 85%." | pre-release | flows |  |
| 19 | "`runner/__init__.py` is fully covered." | pre-release | flows |  |
| 20 | "The previous measurement, main @ 2ab5383, was 80%…" | pre-release | flows |  |
| 21 | "The seam tests added the 5 points." | pre-release | flows |  |
| 22 | "They did not touch the poll library, which…" | pre-release | flows |  |
| 23 | "| File | Before | After | Missed…" | pre-release | flagged | A table header row — structure, not a sentence |
| 24 | "|---|---:|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 25 | "| runner/winlog.py | 32% | 32% | 23…" | pre-release | flows |  |
| 26 | "| runner/oauth.py | 43% | 69% | 45…" | pre-release | flows |  |
| 27 | "| runner/install.py | 57% | 74% | 114…" | pre-release | flows |  |
| 28 | "| runner/setup.py | 76% | 85% | 31…" | pre-release | flows |  |
| 29 | "| runner/runner.py | 84% | 87% | 366…" | pre-release | flows |  |
| 30 | "| runner/senses.py | 87% | 87% | 34…" | pre-release | flows |  |
| 31 | "| runner/review.py | 88% | 88% | 14…" | pre-release | flows |  |
| 32 | "| runner/dri.py | 90% | 90% | 35…" | pre-release | flows |  |
| 33 | "| runner/local_test.py | 58% | 90% | 18…" | pre-release | flows |  |
| 34 | "| runner/resources.py | 91% | 91% | 14…" | pre-release | flows |  |
| 35 | "These were the holes a person hits on…" | pre-release | flows |  |
| 36 | "They are no longer empty." | pre-release | flows |  |
| 37 | "| Location | Before | After |" | pre-release | flagged | A table header row — structure, not a sentence |
| 38 | "|---|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 39 | "| install.py `main` | 0% | 75% |" | pre-release | flows |  |
| 40 | "| install.py `ensure_shared_secret` | 0% | covered |" | pre-release | flows |  |
| 41 | "| setup.py `_mailbox_probe` | 0% | covered |" | pre-release | flows |  |
| 42 | "| oauth.py `_pkce` | 0% | covered |" | pre-release | flows |  |
| 43 | "| oauth.py `build_authorize_url`, `exchange_code` | not extracted |…" | pre-release | flows |  |
| 44 | "| runner.py `oracle_window` | 0% | covered |" | pre-release | flows |  |
| 45 | "| runner.py `connect_imap`, `connect_smtp` | 0% | covered…" | pre-release | flows |  |
| 46 | "| local_test.py `answer_as_oracle` | 13% | covered |" | pre-release | flows |  |
| 47 | "| local_test.py `repl` | 0% | covered |" | pre-release | flows |  |
| 48 | "| local_test.py `browser_chat` | 8% | covered without…" | pre-release | flows |  |
| 49 | "`runner.py main` moved from 26% to 36%." | pre-release | flows |  |
| 50 | "The early exits are covered: bad worker count,…" | pre-release | flows |  |
| 51 | "The poll loop itself is still not entered…" | pre-release | flows |  |
| 52 | "These shells talk to the real OS, a…" | pre-release | flows |  |
| 53 | "The seam tests do not import them." | pre-release | flows |  |
| 54 | "| Miss | Cover | Statements | Location…" | pre-release | flagged | A table header row — structure, not a sentence |
| 55 | "|---:|---:|---:|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 56 | "| 22 | 4% | 23 | oauth.py:207…" | pre-release | flows |  |
| 57 | "| 18 | 28% | 25 | winlog.py:34…" | pre-release | flows |  |
| 58 | "| 17 | 6% | 18 | install.py:528…" | pre-release | flows |  |
| 59 | "| 14 | 67% | 43 | install.py:552…" | pre-release | flows |  |
| 60 | "| 14 | 7% | 15 | oauth.py:233…" | pre-release | flows |  |
| 61 | "| 11 | 8% | 12 | install.py:279…" | pre-release | flows |  |
| 62 | "| 9 | 10% | 10 | install.py:487…" | pre-release | flows |  |
| 63 | "| 7 | 12% | 8 | install.py:230…" | pre-release | flows |  |
| 64 | "`browser_consent` still binds `127.0.0.1:8765` and calls `webbrowser.open`." | pre-release | flows |  |
| 65 | "The URL and the token exchange are tested…" | pre-release | flows |  |
| 66 | "The bind is the part that stays out." | pre-release | flows |  |
| 67 | "Windows, FreeBSD, and macOS uninstall paths stay out…" | pre-release | flows |  |
| 68 | "A test that runs those scripts is not…" | pre-release | flows |  |
| 69 | "The poll path was not the gap." | pre-release | flows |  |
| 70 | "It is still in the same band:" | pre-release | flows |  |
| 71 | "| Function | Cover |" | pre-release | flagged | A table header row — structure, not a sentence |
| 72 | "|---|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 73 | "| `handle_mail` | 96% |" | pre-release | flows |  |
| 74 | "| `answer_queries` | 93% |" | pre-release | flows |  |
| 75 | "| `execute_job` | 89% |" | pre-release | flows |  |
| 76 | "| `poll_once` | 85% |" | pre-release | flows |  |
| 77 | "| `dri.py` | 90% |" | pre-release | flows |  |
| 78 | "| `resources.py` | 91% |" | pre-release | flows |  |
| 79 | "| `review.py` | 88% |" | pre-release | flows |  |
| 80 | "| `senses.py` | 87% |" | pre-release | flows |  |
| 81 | "The remaining misses inside those functions are the…" | pre-release | flows |  |
| 82 | "Another line there does not change what happens…" | pre-release | flows |  |
| 83 | "From the repo root, with coverage.py installed." | pre-release | flows |  |
| 84 | "It is a measurement tool, not a project…" | pre-release | flows |  |
| 85 | "Expect about 50 seconds." | pre-release | flows |  |
| 86 | "Do not treat 85% as a target." | pre-release | flows |  |
| 87 | "The number moves when the untested platform shells…" | pre-release | flows |  |
