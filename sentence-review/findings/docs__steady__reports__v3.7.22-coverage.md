# Findings — docs/steady/reports/v3.7.22-coverage.md

Source: docs/steady/reports/v3.7.22-coverage.md, reviewed at main 08b61333.
Sentence units: 76. Flagged: 8. Categories: pre-release 76, post-release 0.

An early coverage report: provenance, the stat block, the comparison with the previous measurement, the file tables, and a file-by-file account of what remains uncovered and why. The prose chains — the flat percentage is explained by the tree's growth before the tables, and the closing argument (a diagnose report, not a percentage point) is set up by the harness paragraph. The non-sentences are the 6 image lines (units 5 to 10) and the 2 table header rows (units 29 and 47); every data row is counted as a unit and flows as a record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.7.22." | pre-release | flows |  |
| 2 | "A later measurement is [v3.7.30](../v3.7.30/coverage.md)." | pre-release | flows |  |
| 3 | "The previous measurement is [v3.5.2](../../archive/v3.5.2/coverage.md)." | pre-release | flows |  |
| 4 | "No new tag was cut for this measurement." | pre-release | flows |  |
| 5 | "![85.5 percent of statements covered](overall.png)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 6 | "![Coverage by file](by_file.png)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 7 | "![v3.5.2, then v3.7.22, for the files that report…" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 8 | "![85.5 percent](picture-overall.jpg)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 9 | "![Coverage by file, pictured](picture-by-file.jpg)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 10 | "![Then and now, pictured](picture-before-after.jpg)" | pre-release | flagged | An image line standing where a sentence should be; alt text only, it carries no prose connection between its neighbours |
| 11 | "Measured 2026-10-17 with coverage.py 7.16.2, on main at…" | pre-release | flows |  |
| 12 | "The package version is 3.7.22." | pre-release | flows |  |
| 13 | "1668 tests, OK, 4 skipped, 123 seconds under…" | pre-release | flows |  |
| 14 | "Hypothesis was installed, which is what CI does." | pre-release | flows |  |
| 15 | "The four skips are optional tools that were…" | pre-release | flows |  |
| 16 | "Statements: 8697." | pre-release | flows |  |
| 17 | "Missed: 1259." | pre-release | flows |  |
| 18 | "Covered: 85.5%." | pre-release | flows |  |
| 19 | "Branches: 3596, of which 493 are only partly…" | pre-release | flows |  |
| 20 | "Statement and branch together: 84.4%." | pre-release | flows |  |
| 21 | "The 84.4% is not a drop from 85%." | pre-release | flows |  |
| 22 | "The October 16 report did not count branches." | pre-release | flows |  |
| 23 | "A line can run and still leave one…" | pre-release | flows |  |
| 24 | "The v3.5.2 report, main at c48aece, was 85%…" | pre-release | flows |  |
| 25 | "Covered statements went from 4020 to 7438." | pre-release | flows |  |
| 26 | "The tree grew by about 4000 statements." | pre-release | flows |  |
| 27 | "About 3400 of those are covered and about…" | pre-release | flows |  |
| 28 | "The percentage did not move." | pre-release | flows |  |
| 29 | "File \| 16 Oct \| Now \| Missed…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 30 | "winlog.py \| 32% \| 88% \| 4" | pre-release | flows |  |
| 31 | "oauth.py \| 69% \| 91% \| 14" | pre-release | flows |  |
| 32 | "install.py \| 74% \| 75% \| 269" | pre-release | flows |  |
| 33 | "setup.py \| 85% \| 86% \| 30" | pre-release | flows |  |
| 34 | "runner.py \| 87% \| 87% \| 636" | pre-release | flows |  |
| 35 | "senses.py \| 87% \| 94% \| 15" | pre-release | flows |  |
| 36 | "review.py \| 88% \| 98% \| 3" | pre-release | flows |  |
| 37 | "dri.py \| 90% \| 92% \| 29" | pre-release | flows |  |
| 38 | "local_test.py \| 90% \| 90% \| 18" | pre-release | flows |  |
| 39 | "resources.py \| 91% \| 92% \| 13" | pre-release | flows |  |
| 40 | "`winlog.py` and `oauth.py` were the two worst files…" | pre-release | flows |  |
| 41 | "The event-log path and the token exchange are…" | pre-release | flows |  |
| 42 | "What remains in `winlog.py` is creating the event…" | pre-release | flows |  |
| 43 | "What remains in `oauth.py` is a refresh-token failure." | pre-release | flows |  |
| 44 | "`install.py` and `runner.py` stayed in the same band…" | pre-release | flows |  |
| 45 | "`install.py` was about 440 statements and is now…" | pre-release | flows |  |
| 46 | "`runner.py` was about 2800 statements and is now…" | pre-release | flows |  |
| 47 | "File \| Statements \| Missed \| Cover" | pre-release | flagged | Table header row, structure rather than a sentence |
| 48 | "harness.py \| 444 \| 110 \| 75%" | pre-release | flows |  |
| 49 | "detection.py \| 129 \| 31 \| 76%" | pre-release | flows |  |
| 50 | "posture.py \| 233 \| 54 \| 77%" | pre-release | flows |  |
| 51 | "security.py \| 184 \| 14 \| 92%" | pre-release | flows |  |
| 52 | "auditreport.py \| 223 \| 16 \| 93%" | pre-release | flows |  |
| 53 | "sandbox.py \| 53 \| 3 \| 94%" | pre-release | flows |  |
| 54 | "`runner/__init__.py` and `runner/_version.py` are fully covered." | pre-release | flows |  |
| 55 | "`harness.py` is `--diagnose`." | pre-release | flows |  |
| 56 | "The uncovered lines are the sections that talk…" | pre-release | flows |  |
| 57 | "The in-process probes are covered." | pre-release | flows |  |
| 58 | "A unit test that opens a real mailbox…" | pre-release | flows |  |
| 59 | "A diagnose report from the laptop is the…" | pre-release | flows |  |
| 60 | "Inside `runner.py` the poll library is still the…" | pre-release | flows |  |
| 61 | "The misses that are new in kind are…" | pre-release | flows |  |
| 62 | "Another line in the poll path does not…" | pre-release | flows |  |
| 63 | "`install.py` still leaves out Ollama download and startup,…" | pre-release | flows |  |
| 64 | "The last report said those stay untested until…" | pre-release | flows |  |
| 65 | "That is still the case." | pre-release | flows |  |
| 66 | "Wipe and migrate are only partly covered, and…" | pre-release | flows |  |
| 67 | "`detection.py` misses are the plan budget and the…" | pre-release | flows |  |
| 68 | "`posture.py` misses are the Windows file-ACL check and…" | pre-release | flows |  |
| 69 | "From the repo root, with coverage.py installed." | pre-release | flows |  |
| 70 | "It is a measurement tool, not a project…" | pre-release | flows |  |
| 71 | "Install hypothesis first if you want the property…" | pre-release | flows |  |
| 72 | "Expect about two minutes." | pre-release | flows |  |
| 73 | "Do not treat 85.5% as a target." | pre-release | flows |  |
| 74 | "The number moves when the untested platform shells…" | pre-release | flows |  |
| 75 | "The hole that is worth a test is…" | pre-release | flows |  |
| 76 | "It is a diagnose report from a real…" | pre-release | flows |  |
