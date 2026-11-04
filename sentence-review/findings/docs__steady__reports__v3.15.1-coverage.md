# Findings — docs/steady/reports/v3.15.1-coverage.md

Source: docs/steady/reports/v3.15.1-coverage.md, reviewed at main cbb52068.
Sentence units: 65. Flagged: 2. Categories: pre-release 65, post-release 0.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.15.1. The previous…" | pre-release | flows |  |
| 2 | "No new tag was cut for this measurement." | pre-release | flows |  |
| 3 | "It is main at a2e7f037, two commits after…" | pre-release | flows |  |
| 4 | "The gap list is coverage-gaps.md." | pre-release | flows |  |
| 5 | "Measured 2026-11-01 with coverage.py 7.16.2, on Python 3.11." | pre-release | flows |  |
| 6 | "Hypothesis 6.170.3 was installed." | pre-release | flows |  |
| 7 | "CI pins a newer hypothesis and measures on…" | pre-release | flows |  |
| 8 | "8273 tests, 6 failures, 47 skipped." | pre-release | flows |  |
| 9 | "1226 seconds." | pre-release | flows |  |
| 10 | "Four of the failures are this environment, the…" | pre-release | flows |  |
| 11 | "The hostinfo campaign shape exited 127, a command…" | pre-release | flows |  |
| 12 | "The ps probe answered false, because ps is…" | pre-release | flows |  |
| 13 | "Two tests wanted empty output and got a…" | pre-release | flows |  |
| 14 | "The skips are optional tools that are not…" | pre-release | flows |  |
| 15 | "Two failures are the corpus, not a missing…" | pre-release | flows |  |
| 16 | "The local inbox replay of seed `wrong_key` said…" | pre-release | flows |  |
| 17 | "The board reader, replayed twice, did not come…" | pre-release | flows |  |
| 18 | "Both are recorded here and not folded into…" | pre-release | flows |  |
| 19 | "The run used .github/coveragerc: source is runner, tests…" | pre-release | flows |  |
| 20 | "That is the same yardstick as the 3.13.62…" | pre-release | flows |  |
| 21 | "The tree is larger, 33197 statements against 30412." | pre-release | flows |  |
| 22 | "The first pass missed 437 of them, and…" | pre-release | flows |  |
| 23 | "The tests in runner/tests/test_coverage_floor.py walk those arms." | pre-release | flows |  |
| 24 | "The oracle handler runs in its own thread,…" | pre-release | flows |  |
| 25 | "The table counts the suite plus those tests." | pre-release | flows |  |
| 26 | "348 statements are still missed." | pre-release | flows |  |
| 27 | "Every shipped file is above 90 percent." | pre-release | flows |  |
| 28 | "; Covered ; Missed ; Total" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 29 | "Statements ; 99.0% ; 348 ; 33197" | pre-release | flows |  |
| 30 | "Branches ; 96.7% ; 433 ; 13110" | pre-release | flows |  |
| 31 | "Statements and branches ; 98.3% ; ;" | pre-release | flows |  |
| 32 | "The files at 99% and under, by statements:" | pre-release | flows |  |
| 33 | "File ; Covered ; Missed" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 34 | "ops/mail.py ; 92.2% ; 30" | pre-release | flows |  |
| 35 | "transport_extensions/nats/__main__.py ; 92.3% ; 21" | pre-release | flows |  |
| 36 | "ops/cancel.py ; 92.5% ; 12" | pre-release | flows |  |
| 37 | "ops/changes.py ; 92.5% ; 8" | pre-release | flows |  |
| 38 | "wire/verify.py ; 93.7% ; 46" | pre-release | flows |  |
| 39 | "transport_extensions/queues/__main__.py ; 94.5% ; 17" | pre-release | flows |  |
| 40 | "cloud/send_job.py ; 95.5% ; 44" | pre-release | flows |  |
| 41 | "wire/oauth.py ; 96.6% ; 7" | pre-release | flows |  |
| 42 | "transport_extensions/email/__main__.py ; 96.9% ; 5" | pre-release | flows |  |
| 43 | "ops/startup.py ; 96.9% ; 5" | pre-release | flows |  |
| 44 | "wire/platformcard.py ; 97.1% ; 2" | pre-release | flows |  |
| 45 | "transport_extensions/channel.py ; 97.4% ; 4" | pre-release | flows |  |
| 46 | "oracle/opinion.py ; 97.4% ; 8" | pre-release | flows |  |
| 47 | "ops/poll.py ; 97.9% ; 2" | pre-release | flows |  |
| 48 | "transport_extensions/dtls/__main__.py ; 98.1% ; 4" | pre-release | flows |  |
| 49 | "ops/queries.py ; 98.2% ; 8" | pre-release | flows |  |
| 50 | "cloud/send_dtls.py ; 98.3% ; 3" | pre-release | flows |  |
| 51 | "oracle/senses.py ; 98.4% ; 5" | pre-release | flows |  |
| 52 | "hosting/fly.py ; 98.4% ; 1" | pre-release | flows |  |
| 53 | "runner.py ; 98.4% ; 62" | pre-release | flows |  |
| 54 | "ops/exec.py ; 98.5% ; 7" | pre-release | flows |  |
| 55 | "guard/security.py ; 98.5% ; 4" | pre-release | flows |  |
| 56 | "oracle/dri.py ; 99.0% ; 4" | pre-release | flows |  |
| 57 | "runner.py is 98.4% (62 missed of 3946)." | pre-release | flows |  |
| 58 | "In the 3.13.62 report it was 99.7% (10…" | pre-release | flows |  |
| 59 | "The floor is ops/mail.py at 92.2%. ops/oracle_server.py is…" | pre-release | flows |  |
| 60 | "In the 3.13.62 report that file was 93.8%." | pre-release | flows |  |
| 61 | "Statement coverage, 40 cells, one cell is 2.5…" | pre-release | flows |  |
| 62 | "The functions with the most never-executed lines are…" | pre-release | flows |  |
| 63 | "The largest is mail.py:handle_mail, 30 lines, down from…" | pre-release | flows |  |
| 64 | "Next is _in_root_object_at in send_job.py and in verify.py,…" | pre-release | flows |  |
| 65 | "The oracle server's do_GET and do_POST are no…" | pre-release | flows |  |
