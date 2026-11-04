# Findings — docs/steady/reports/v3.7.30-coverage.md

Source: docs/steady/reports/v3.7.30-coverage.md, reviewed at main cbb52068.
Sentence units: 84. Flagged: 2. Categories: pre-release 84, post-release 0.

Units 6-11 are chart captions and headline figures; the charts are images.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.7.30." | pre-release | flows |  |
| 2 | "The previous measurement is v3.7.22." | pre-release | flows |  |
| 3 | "The next measurement is v3.11.1. No new tag…" | pre-release | flows |  |
| 4 | "The tree measured is `reports/coverage-mutation-3.7.30` at e3d88e4, which…" | pre-release | flows |  |
| 5 | "Python's `$` matches just before a final newline,…" | pre-release | flows |  |
| 6 | "91.8 percent of statements covered" | pre-release | flows |  |
| 7 | "Coverage by file" | pre-release | flows |  |
| 8 | "v3.7.22, then v3.7.30" | pre-release | flows |  |
| 9 | "91.8 percent" | pre-release | flows |  |
| 10 | "Coverage by file, pictured" | pre-release | flows |  |
| 11 | "Then and now, pictured" | pre-release | flows |  |
| 12 | "Measured 2026-10-18 with coverage.py 7.16.2, on Python 3.11.2.…" | pre-release | flows |  |
| 13 | "The package version is 3.7.30." | pre-release | flows |  |
| 14 | "2496 tests, OK, 8 skipped, 196 seconds under…" | pre-release | flows |  |
| 15 | "The eight skips are optional tools that were…" | pre-release | flows |  |
| 16 | "The v3.7.22 run skipped four of the same…" | pre-release | flows |  |
| 17 | "Statements: 9441." | pre-release | flows |  |
| 18 | "Missed: 778." | pre-release | flows |  |
| 19 | "Covered: 91.8%." | pre-release | flows |  |
| 20 | "Branches: 3948." | pre-release | flows |  |
| 21 | "Covered: 3510 (88.9%)." | pre-release | flows |  |
| 22 | "Missing: 438, of which 338 are only partly…" | pre-release | flows |  |
| 23 | "Statement and branch together, the number `coverage report`…" | pre-release | flows |  |
| 24 | "The 91.8% is statement coverage, the same kind…" | pre-release | flows |  |
| 25 | "The October 17 report's "together" figure was 84.4%." | pre-release | flows |  |
| 26 | "This run's together figure is 90.9%." | pre-release | flows |  |
| 27 | "Statement coverage, 40 cells, one cell is 2.5…" | pre-release | flows |  |
| 28 | "By file, lowest first." | pre-release | flows |  |
| 29 | "Forty cells, so the 32nd cell is the…" | pre-release | flows |  |
| 30 | "`runner/__init__.py` and `runner/_version.py` are one statement each and…" | pre-release | flows |  |
| 31 | "They are not on the chart." | pre-release | flows |  |
| 32 | "The v3.7.22 report was 85.5% (8697 statements, 1259…" | pre-release | flows |  |
| 33 | "Covered statements went from 7438 to 8663." | pre-release | flows |  |
| 34 | "The tree grew by 744 statements." | pre-release | flows |  |
| 35 | "Misses fell by 481." | pre-release | flows |  |
| 36 | "Both happened: new code landed, and a lot…" | pre-release | flows |  |
| 37 | "File ; 17 Oct ; Now ; Missed…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 38 | "winlog.py ; 88% ; 88% ; 4" | pre-release | flows |  |
| 39 | "oauth.py ; 91% ; 85% ; 31" | pre-release | flows |  |
| 40 | "install.py ; 75% ; 78% ; 254" | pre-release | flows |  |
| 41 | "setup.py ; 86% ; 84% ; 37" | pre-release | flows |  |
| 42 | "runner.py ; 87% ; 97% ; 152" | pre-release | flows |  |
| 43 | "senses.py ; 94% ; 95% ; 14" | pre-release | flows |  |
| 44 | "review.py ; 98% ; 98% ; 3" | pre-release | flows |  |
| 45 | "dri.py ; 92% ; 91% ; 34" | pre-release | flows |  |
| 46 | "local_test.py ; 90% ; 91% ; 17" | pre-release | flows |  |
| 47 | "resources.py ; 92% ; 93% ; 14" | pre-release | flows |  |
| 48 | "`runner.py` is the move that changes the total." | pre-release | flows |  |
| 49 | "It was about 4842 statements with 636 missed." | pre-release | flows |  |
| 50 | "It is now 5233 statements with 152 missed." | pre-release | flows |  |
| 51 | "`oauth.py` went the other way." | pre-release | flows |  |
| 52 | "It was 91% with 14 missed and is…" | pre-release | flows |  |
| 53 | "The new misses are `refresh_access_token`, `store_refresh_token`, and `main`." | pre-release | flows |  |
| 54 | "`winlog.py` did not move." | pre-release | flows |  |
| 55 | "The four missed lines are still creating the…" | pre-release | flows |  |
| 56 | "File ; 17 Oct ; Now ; Missed…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 57 | "harness.py ; 75% ; 76% ; 108" | pre-release | flows |  |
| 58 | "detection.py ; 76% ; 82% ; 31" | pre-release | flows |  |
| 59 | "posture.py ; 77% ; 79% ; 49" | pre-release | flows |  |
| 60 | "security.py ; 92% ; 94% ; 15" | pre-release | flows |  |
| 61 | "auditreport.py ; 93% ; 93% ; 15" | pre-release | flows |  |
| 62 | "sandbox.py ; 94% ; 100% ; 0" | pre-release | flows |  |
| 63 | "`detection.py` still misses the same 31 lines (plan…" | pre-release | flows |  |
| 64 | "The percent rose because the file grew around…" | pre-release | flows |  |
| 65 | "`harness.py` is still `--diagnose`." | pre-release | flows |  |
| 66 | "The uncovered lines are the sections that talk…" | pre-release | flows |  |
| 67 | "A unit test that opens a real mailbox…" | pre-release | flows |  |
| 68 | "`install.py` is still the largest hole: Ollama download…" | pre-release | flows |  |
| 69 | "Those stay untested until a machine of that…" | pre-release | flows |  |
| 70 | "`posture.py` still misses the Windows file-ACL check and…" | pre-release | flows |  |
| 71 | "Inside `runner.py` the remaining misses are edges, not…" | pre-release | flows |  |
| 72 | "Another line there does not change what a…" | pre-release | flows |  |
| 73 | "`security.py` is the mutation scope." | pre-release | flows |  |
| 74 | "Fifteen statements are still uncovered, in `validate_security_config` and…" | pre-release | flows |  |
| 75 | "Mutation only scores mutants on covered lines." | pre-release | flows |  |
| 76 | "The mutation run is mutation.md: 458 of 537…" | pre-release | flows |  |
| 77 | "From the repo root, with coverage.py installed." | pre-release | flows |  |
| 78 | "It is a measurement tool, not a project…" | pre-release | flows |  |
| 79 | "Install hypothesis first if you want the property…" | pre-release | flows |  |
| 80 | "Expect about three and a half minutes." | pre-release | flows |  |
| 81 | "Do not treat 91.8% as a target." | pre-release | flows |  |
| 82 | "The number moves when the untested platform shells…" | pre-release | flows |  |
| 83 | "The hole that is worth a test is…" | pre-release | flows |  |
| 84 | "It is a diagnose report from a real…" | pre-release | flows |  |
