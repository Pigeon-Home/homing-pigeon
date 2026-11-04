# Findings — docs/steady/reports/v3.13.62-coverage.md

Source: docs/steady/reports/v3.13.62-coverage.md, reviewed at main 08b61333.
Sentence units: 44. Flagged: 2. Categories: pre-release 44, post-release 0.

A single-measurement coverage report in the family's stat-block shape: provenance, the run, the yardstick warning (this edition counts the extensions, the earlier one did not), the summary tables, and the floor files. The prose chains — the 99.5% is explicitly fenced off from the earlier 95.4% before any table is read. The non-sentences are the 2 table header rows (units 20 and 25); every data row is counted as a unit and flows as a record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.13.62." | pre-release | flows |  |
| 2 | "The previous measurement in the tree is [v3.12.65](../v3.12.65/coverage.md)." | pre-release | flows |  |
| 3 | "No new tag was cut for this measurement." | pre-release | flows |  |
| 4 | "It is main at 13d4aacf9446." | pre-release | flows |  |
| 5 | "The gap list is [coverage-gaps.md](coverage-gaps.md)." | pre-release | flows |  |
| 6 | "Measured 2026-10-26 with coverage.py 7.16.2, on Python 3.10.22." | pre-release | flows |  |
| 7 | "Hypothesis 6.168.5 was installed." | pre-release | flows |  |
| 8 | "CI pins hypothesis 6.170.5 and measures on Python…" | pre-release | flows |  |
| 9 | "7194 tests, 2 failures, 28 skipped." | pre-release | flows |  |
| 10 | "939 seconds." | pre-release | flows |  |
| 11 | "The two failures are this environment, not a…" | pre-release | flows |  |
| 12 | "The hostinfo campaign shape exited 127, a command…" | pre-release | flows |  |
| 13 | "The ps probe answered false, because ps is…" | pre-release | flows |  |
| 14 | "The skips are optional tools that are not…" | pre-release | flows |  |
| 15 | "The run used .github/coveragerc: source is runner, tests…" | pre-release | flows |  |
| 16 | "That is the CI measurement." | pre-release | flows |  |
| 17 | "The 3.12.65 report left extensions out and counted…" | pre-release | flows |  |
| 18 | "This one counts extensions, and the tree is…" | pre-release | flows |  |
| 19 | "99.5% is not the same yardstick as 95.4%." | pre-release | flows |  |
| 20 | "\| Covered \| Missed \| Total" | pre-release | flagged | Table header row, structure rather than a sentence |
| 21 | "Statements \| 99.5% \| 143 \| 30412" | pre-release | flows |  |
| 22 | "Branches \| 97.4% \| 311 \| 12026" | pre-release | flows |  |
| 23 | "Statements and branches \| 98.9% \| \|" | pre-release | flows |  |
| 24 | "The files at 99% and under, by statements:" | pre-release | flows |  |
| 25 | "File \| Covered \| Missed" | pre-release | flagged | Table header row, structure rather than a sentence |
| 26 | "cloud/send_job.py \| 93.8% \| 23" | pre-release | flows |  |
| 27 | "extensions/pi-health/pi_health.py \| 93.8% \| 17" | pre-release | flows |  |
| 28 | "ops/cli.py \| 96.0% \| 4" | pre-release | flows |  |
| 29 | "hosting/cli.py \| 96.2% \| 8" | pre-release | flows |  |
| 30 | "ops/startup.py \| 98.4% \| 2" | pre-release | flows |  |
| 31 | "hosting/fly.py \| 98.4% \| 1" | pre-release | flows |  |
| 32 | "wire/oauth.py \| 98.5% \| 3" | pre-release | flows |  |
| 33 | "ops/oracle_server.py \| 98.7% \| 2" | pre-release | flows |  |
| 34 | "wire/verify.py \| 98.7% \| 6" | pre-release | flows |  |
| 35 | "guard/security.py \| 98.9% \| 3" | pre-release | flows |  |
| 36 | "oracle/dri.py \| 99.0% \| 4" | pre-release | flows |  |
| 37 | "runner.py is 99.7% (10 missed of 3702)." | pre-release | flows |  |
| 38 | "The floor is cloud/send_job.py and extensions/pi-health/pi_health.py, both 93.8%." | pre-release | flows |  |
| 39 | "cloud/send_dtls.py is 100.0% (0 missed of 154)." | pre-release | flows |  |
| 40 | "In the 3.12.65 report that file was the…" | pre-release | flows |  |
| 41 | "Statement coverage, 40 cells, one cell is 2.5…" | pre-release | flows |  |
| 42 | "The functions with the most never-executed lines are…" | pre-release | flows |  |
| 43 | "The largest is pi_health.py:_mem_avail_pct_windows, 14 lines, the Windows…" | pre-release | flows |  |
| 44 | "The rest of the list is one or…" | pre-release | flows |  |
