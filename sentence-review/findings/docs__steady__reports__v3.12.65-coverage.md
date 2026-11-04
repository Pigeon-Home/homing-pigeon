# Findings — docs/steady/reports/v3.12.65-coverage.md

Source: docs/steady/reports/v3.12.65-coverage.md, reviewed at main cbb52068.
Sentence units: 54. Flagged: 2. Categories: pre-release 54, post-release 0.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.12.65." | pre-release | flows |  |
| 2 | "The previous measurement is v3.12.61." | pre-release | flows |  |
| 3 | "No new tag was cut for this measurement." | pre-release | flows |  |
| 4 | "It is main at dd89ba4." | pre-release | flows |  |
| 5 | "The gap list for this package is coverage-gaps.md." | pre-release | flows |  |
| 6 | "Measured 2026-10-25 with coverage.py 7.16.2, on Python 3.11.2.…" | pre-release | flows |  |
| 7 | "CI pins hypothesis 6.170.5. 5740 tests, 3 failures,…" | pre-release | flows |  |
| 8 | "511 seconds." | pre-release | flows |  |
| 9 | "The failures are local to this machine, not…" | pre-release | flows |  |
| 10 | "The skips are optional tools that are not…" | pre-release | flows |  |
| 11 | "; Covered ; Missed ; Total" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 12 | "Statements ; 95.4% ; 883 ; 19369" | pre-release | flows |  |
| 13 | "Branches ; 93.0% ; 551 ; 7898" | pre-release | flows |  |
| 14 | "Statements and branches ; 94.7% ; ;" | pre-release | flows |  |
| 15 | "`runner/tests/`, `runner/tools/`, and `runner/extensions/` are left out of…" | pre-release | flows |  |
| 16 | "The suite and the CI scripts are the…" | pre-release | flows |  |
| 17 | "The shipped extensions still do not count. `runner/cloud/`…" | pre-release | flows |  |
| 18 | "Without those two files the statement figure is…" | pre-release | flows |  |
| 19 | "The files still under 96%, by statements:" | pre-release | flows |  |
| 20 | "File ; Covered ; Missed" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 21 | "cloud/send_dtls.py ; 36.6% ; 97" | pre-release | flows |  |
| 22 | "transport_extensions/nats/__main__.py ; 79.8% ; 46" | pre-release | flows |  |
| 23 | "transport_extensions/dtls/__main__.py ; 81.5% ; 33" | pre-release | flows |  |
| 24 | "cloud/send_job.py ; 82.7% ; 51" | pre-release | flows |  |
| 25 | "guard/defaulted.py ; 87.0% ; 7" | pre-release | flows |  |
| 26 | "wire/platformcard.py ; 88.6% ; 5" | pre-release | flows |  |
| 27 | "ops/extsources.py ; 90.6% ; 132" | pre-release | flows |  |
| 28 | "oracle/resources.py ; 92.8% ; 14" | pre-release | flows |  |
| 29 | "ops/auditreport.py ; 93.5% ; 15" | pre-release | flows |  |
| 30 | "guard/security.py ; 93.5% ; 15" | pre-release | flows |  |
| 31 | "guard/confval.py ; 94.0% ; 3" | pre-release | flows |  |
| 32 | "wire/mailbox.py ; 94.2% ; 11" | pre-release | flows |  |
| 33 | "oracle/detection.py ; 94.3% ; 10" | pre-release | flows |  |
| 34 | "wire/oauth.py ; 94.8% ; 12" | pre-release | flows |  |
| 35 | "wire/verify.py ; 95.0% ; 23" | pre-release | flows |  |
| 36 | "oracle/dri.py ; 95.1% ; 20" | pre-release | flows |  |
| 37 | "wire/board.py ; 95.5% ; 13" | pre-release | flows |  |
| 38 | "guard/sandbox.py ; 95.7% ; 6" | pre-release | flows |  |
| 39 | "runner.py ; 95.8% ; 269" | pre-release | flows |  |
| 40 | "`runner.py` is 95.8% (269 missed of 6412)." | pre-release | flows |  |
| 41 | "The floor is `cloud/send_dtls.py` at 36.6%. `cloud/send_job.py` rose…" | pre-release | flows |  |
| 42 | "The socket and broker programs are still the…" | pre-release | flows |  |
| 43 | "Statement coverage, 40 cells, one cell is 2.5…" | pre-release | flows |  |
| 44 | "`runner/__init__.py` and `runner/_version.py` are fully covered. `harness.py`, `local_test.py`,…" | pre-release | flows |  |
| 45 | "That report was 95.2% of 19260 statements, 932…" | pre-release | flows |  |
| 46 | "This tree has 19369 statements and 883 missed." | pre-release | flows |  |
| 47 | "The statement figure is 95.4%." | pre-release | flows |  |
| 48 | "Statements grew by 109." | pre-release | flows |  |
| 49 | "Misses fell by 49." | pre-release | flows |  |
| 50 | "From the repo root." | pre-release | flows |  |
| 51 | "Use Python 3.11 or newer." | pre-release | flows |  |
| 52 | "Expect about nine minutes." | pre-release | flows |  |
| 53 | "The omit is required." | pre-release | flows |  |
| 54 | "The suite lives inside `runner/`, and a run…" | pre-release | flows |  |
