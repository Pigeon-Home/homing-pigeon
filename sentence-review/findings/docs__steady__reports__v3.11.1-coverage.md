# Findings — docs/steady/reports/v3.11.1-coverage.md

Source: docs/steady/reports/v3.11.1-coverage.md, reviewed at main 8a717fd5.
Sentence units: 98. Flagged: 9. Categories: pre-release 98, post-release 0.

A single-measurement coverage report: the run's numbers as a stat block, the by-file charts, the comparison with the previous measurement, and the holes that remain. The prose chains tightly — every figure is set up by the line before it and used by the line after. The non-sentences are the 6 image lines (units 5 to 10) standing between the provenance lines and the measurement line, and the 3 table header rows (units 40, 59, 71); every data row is counted as a unit and flows as a record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.11.1." | pre-release | flows |  |
| 2 | "The previous measurement is [v3.7.30](../v3.7.30/coverage.md)." | pre-release | flows |  |
| 3 | "No new tag was cut for this measurement." | pre-release | flows |  |
| 4 | "The tree measured is main at 5ada9d3 (`release:…" | pre-release | flows |  |
| 5 | "![94.2 percent of statements covered](overall.png)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 6 | "![Coverage by file](by_file.png)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 7 | "![v3.7.30, then v3.11.1](before_after.png)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 8 | "![94.2 percent](picture-overall.jpg)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 9 | "![Coverage by file, pictured](picture-by-file.jpg)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 10 | "![Then and now, pictured](picture-before-after.jpg)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 11 | "Measured 2026-10-19 with coverage.py 7.16.2, on Python 3.11.2." | pre-release | flows |  |
| 12 | "Hypothesis 6.170.3 was installed, which is what CI…" | pre-release | flows |  |
| 13 | "The package version is 3.11.1." | pre-release | flows |  |
| 14 | "3979 tests, OK, 12 skipped, 236 seconds under…" | pre-release | flows |  |
| 15 | "The skips are optional tools that were not…" | pre-release | flows |  |
| 16 | "Statements: 15326." | pre-release | flows |  |
| 17 | "Missed: 890." | pre-release | flows |  |
| 18 | "Covered: 14436." | pre-release | flows |  |
| 19 | "Covered: 94.2%." | pre-release | flows |  |
| 20 | "Branches: 6212." | pre-release | flows |  |
| 21 | "Covered: 5621 (90.5%)." | pre-release | flows |  |
| 22 | "Missing: 591, of which 477 are only partly…" | pre-release | flows |  |
| 23 | "Statement and branch together, the number `coverage report`…" | pre-release | flows |  |
| 24 | "The 94.2% is statement coverage, the same kind…" | pre-release | flows |  |
| 25 | "That report's together figure was 90.9%." | pre-release | flows |  |
| 26 | "This run's together figure is 93.1%." | pre-release | flows |  |
| 27 | "Statement coverage, 40 cells, one cell is 2.5…" | pre-release | flows |  |
| 28 | "By file, lowest first." | pre-release | flows |  |
| 29 | "Forty cells, so the 32nd cell is the…" | pre-release | flows |  |
| 30 | "`channel.py` is `transport_extensions/channel.py`." | pre-release | flows |  |
| 31 | "The four `ext` rows are the transport extension…" | pre-release | flows |  |
| 32 | "`runner/__init__.py` and `runner/_version.py` are one or two statements…" | pre-release | flows |  |
| 33 | "They are not on the chart." | pre-release | flows |  |
| 34 | "The v3.7.30 report was 91.8% (9441 statements, 778…" | pre-release | flows |  |
| 35 | "Covered statements went from 8663 to 14436." | pre-release | flows |  |
| 36 | "The tree grew by 5885 statements." | pre-release | flows |  |
| 37 | "Misses rose by 112." | pre-release | flows |  |
| 38 | "The percent rose because the new code is…" | pre-release | flows |  |
| 39 | "The holes that were the point of the…" | pre-release | flows |  |
| 40 | "File \| 18 Oct \| Now \| Missed…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 41 | "winlog.py \| 88% \| 88% \| 4" | pre-release | flows |  |
| 42 | "oauth.py \| 85% \| 85% \| 31" | pre-release | flows |  |
| 43 | "install.py \| 78% \| 99.9% \| 1" | pre-release | flows |  |
| 44 | "setup.py \| 84% \| 100% \| 0" | pre-release | flows |  |
| 45 | "runner.py \| 97% \| 97% \| 175" | pre-release | flows |  |
| 46 | "senses.py \| 95% \| 95% \| 15" | pre-release | flows |  |
| 47 | "review.py \| 98% \| 98% \| 3" | pre-release | flows |  |
| 48 | "dri.py \| 91% \| 91% \| 34" | pre-release | flows |  |
| 49 | "local_test.py \| 91% \| 100% \| 0" | pre-release | flows |  |
| 50 | "resources.py \| 93% \| 93% \| 14" | pre-release | flows |  |
| 51 | "`install.py` was the largest hole (254 missed)." | pre-release | flows |  |
| 52 | "One statement remains: the `getuid()` call inside `_posix_uid`,…" | pre-release | flows |  |
| 53 | "`runner.py` grew from 5233 statements and 152 missed…" | pre-release | flows |  |
| 54 | "The percent did not move." | pre-release | flows |  |
| 55 | "`harness.py`, `posture.py`, `local_test.py`, `setup.py`, `remediation.py`, and `sandbox.py` are…" | pre-release | flows |  |
| 56 | "On 18 October the first four were 76%,…" | pre-release | flows |  |
| 57 | "`sandbox.py` was already 100%." | pre-release | flows |  |
| 58 | "`remediation.py` was not in that report." | pre-release | flows |  |
| 59 | "File \| 18 Oct \| Now \| Missed…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 60 | "harness.py \| 76% \| 100% \| 0" | pre-release | flows |  |
| 61 | "detection.py \| 82% \| 82% \| 31" | pre-release | flows |  |
| 62 | "posture.py \| 79% \| 100% \| 0" | pre-release | flows |  |
| 63 | "security.py \| 94% \| 94% \| 15" | pre-release | flows |  |
| 64 | "auditreport.py \| 93% \| 94% \| 15" | pre-release | flows |  |
| 65 | "sandbox.py \| 100% \| 100% \| 0" | pre-release | flows |  |
| 66 | "`detection.py` still misses the same 31 statements." | pre-release | flows |  |
| 67 | "`winlog.py` still misses the four lines that register…" | pre-release | flows |  |
| 68 | "`oauth.py` still misses the refresh and store path…" | pre-release | flows |  |
| 69 | "These files were not in the 18 October…" | pre-release | flows |  |
| 70 | "They are the low end of this chart." | pre-release | flows |  |
| 71 | "File \| Now \| Missed" | pre-release | flagged | Table header row, structure rather than a sentence |
| 72 | "transport_extensions/channel.py \| 68% \| 28" | pre-release | flows |  |
| 73 | "dtls extension \| 69% \| 45" | pre-release | flows |  |
| 74 | "email extension \| 71% \| 30" | pre-release | flows |  |
| 75 | "file extension \| 73% \| 38" | pre-release | flows |  |
| 76 | "nats extension \| 78% \| 47" | pre-release | flows |  |
| 77 | "learning.py \| 82% \| 65" | pre-release | flows |  |
| 78 | "transports.py \| 83% \| 77" | pre-release | flows |  |
| 79 | "dtlsproto.py \| 83% \| 177" | pre-release | flows |  |
| 80 | "extensions.py \| 89% \| 24" | pre-release | flows |  |
| 81 | "mailbox.py \| 94% \| 11" | pre-release | flows |  |
| 82 | "jobcrypto.py \| 96% \| 7" | pre-release | flows |  |
| 83 | "opinion.py \| 99% \| 3" | pre-release | flows |  |
| 84 | "`dtlsproto.py` is the largest new hole: 177 missed…" | pre-release | flows |  |
| 85 | "The extension programs under `transport_extensions/` are the next." | pre-release | flows |  |
| 86 | "They are processes the runner supervises, and a…" | pre-release | flows |  |
| 87 | "`jobcrypto.py` is the AES-256-GCM envelope." | pre-release | flows |  |
| 88 | "Seven statements missed." | pre-release | flows |  |
| 89 | "That is not the hole." | pre-release | flows |  |
| 90 | "From the repo root, with coverage.py installed." | pre-release | flows |  |
| 91 | "It is a measurement tool, not a project…" | pre-release | flows |  |
| 92 | "Install hypothesis first if you want the property…" | pre-release | flows |  |
| 93 | "Use Python 3.11 or newer." | pre-release | flows |  |
| 94 | "`tomllib` and `contextlib.chdir` are not on 3.10, and…" | pre-release | flows |  |
| 95 | "Expect about four minutes." | pre-release | flows |  |
| 96 | "Do not treat 94.2% as a target." | pre-release | flows |  |
| 97 | "The number moves when the untested transport shells…" | pre-release | flows |  |
| 98 | "The hole that is worth a test is…" | pre-release | flows |  |
