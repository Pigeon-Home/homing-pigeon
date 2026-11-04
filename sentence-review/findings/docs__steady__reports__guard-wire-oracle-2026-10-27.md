# Findings — docs/steady/reports/guard-wire-oracle-2026-10-27.md

Source: docs/steady/reports/guard-wire-oracle-2026-10-27.md, reviewed at main cbb52068.
Sentence units: 24. Flagged: 3. Categories: pre-release 24, post-release 0.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Measured on a box with no package index,…" | pre-release | flows |  |
| 2 | "This is the air-gapped bench's view of the…" | pre-release | flows |  |
| 3 | "Lines only, no branches." | pre-release | flows |  |
| 4 | "The data beside this file is the tool's…" | pre-release | flows |  |
| 5 | "Report ; Sources ; Tests" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 6 | "`guard-wire-oracle-2026-10-27-before.json` ; `runner/guard/`, `runner/wire/`, `runner/oracle/` ; every `runner/tests/test_*.py`:…" | pre-release | flows |  |
| 7 | "`guard-wire-oracle-2026-10-27-after.json` ; the same ; 7,325 tests, 49…" | pre-release | flows |  |
| 8 | "The first pass on this box ran 13…" | pre-release | flows |  |
| 9 | "They skip now off CI and still fail…" | pre-release | flows |  |
| 10 | "7,470 statements." | pre-release | flows |  |
| 11 | "Never run: 107 before, 89 after (98.6% to…" | pre-release | flows |  |
| 12 | "Module ; Before ; After" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 13 | "`runner/wire/dtlsproto.py` ; 16 ; 7" | pre-release | flows |  |
| 14 | "`runner/guard/extreview.py` ; 6 ; 1" | pre-release | flows |  |
| 15 | "`runner/oracle/learning.py` ; 5 ; 2" | pre-release | flows |  |
| 16 | "`runner/guard/security.py` ; 6 ; 5" | pre-release | flows |  |
| 17 | "The tests are `runner/tests/test_reader_edges_offline.py` and the DTLS truncation…" | pre-release | flows |  |
| 18 | "Lines ; Why no test is aimed at…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 19 | "`dtlsproto.py:x25519` 186-187 ; the final swap: scalar clamping…" | pre-release | flows |  |
| 20 | "`security.py:_rx_subpatterns` 226, 228 ; the walker handles repeats…" | pre-release | flows |  |
| 21 | "`verify.py` 747-757 ; the fallbacks for a missing…" | pre-release | flows |  |
| 22 | "`verify.py` 147, 217, 264, 291, 322, 912, 957,…" | pre-release | flows |  |
| 23 | "`panic.py` 164, 185, 203, 229, 237, 296 and…" | pre-release | flows |  |
| 24 | "`security.py` 516, `remediation.py` 470, 483, 499, 558 ;…" | pre-release | flows |  |
