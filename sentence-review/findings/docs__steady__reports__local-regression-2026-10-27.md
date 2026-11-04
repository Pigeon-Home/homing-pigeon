# Findings — docs/steady/reports/local-regression-2026-10-27.md

Source: docs/steady/reports/local-regression-2026-10-27.md, reviewed at main 670cf354.
Sentence units: 31. Flagged: 4. Categories: pre-release 31, post-release 0.

A dated local regression report with 2 tables. The prose connects; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7 -->" | pre-release | flows |  |
| 2 | "The whole suite, every `runner/tests/test_*.py` module, run once…" | pre-release | flows |  |
| 3 | "Lines only, no branches, no child processes." | pre-release | flows |  |
| 4 | "The data beside this file is the tool's…" | pre-release | flows |  |
| 5 | "| Report | Tree | Tests run |…" | pre-release | flagged | A table header row — structure, not a sentence |
| 6 | "|---|---|---:|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 7 | "| `local-regression-before-2026-10-27.json` | `c6c1b73` | 7,308 | 15…" | pre-release | flows |  |
| 8 | "| `local-regression-after-2026-10-27.json` | `06888e0` | 7,360 | 1…" | pre-release | flows |  |
| 9 | "| Scope | Before | After |" | pre-release | flagged | A table header row — structure, not a sentence |
| 10 | "|---|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 11 | "| Shipped code (`runner/` without `tests/` and `tools/`)…" | pre-release | flows |  |
| 12 | "| `runner/tools/stamp_audit.py` | 58.7% | 98.8% (measured on…" | pre-release | flows |  |
| 13 | "The before figure is recounted without `global` and…" | pre-release | flows |  |
| 14 | "Other seats landed edge tests in the same…" | pre-release | flows |  |
| 15 | "`runner/tests/test_script_mode.py` (15 tests)." | pre-release | flows |  |
| 16 | "Every module split out of `runner.py` is loaded…" | pre-release | flows |  |
| 17 | "Each sense, `send_job.py`, `send_dtls.py` and the host CLI…" | pre-release | flows |  |
| 18 | "109 lines that only a by-path run took." | pre-release | flows |  |
| 19 | "`runner/tests/test_refusal_edges.py` (14 tests)." | pre-release | flows |  |
| 20 | "The sender's verifier shape and walk checks, a…" | pre-release | flows |  |
| 21 | "20 lines." | pre-release | flows |  |
| 22 | "`runner/tests/test_stamp_audit_report.py` (12 tests)." | pre-release | flows |  |
| 23 | "The push gate's report, its unstamped count, `main`…" | pre-release | flows |  |
| 24 | "Two fixes to `runner/tools/linecov.py`, each with a test…" | pre-release | flows |  |
| 25 | "A source under a measured folder that does…" | pre-release | flows |  |
| 26 | "It is now listed under `meta.unparsed` and left…" | pre-release | flows |  |
| 27 | "`global` and `nonlocal` compile to no instruction, so…" | pre-release | flows |  |
| 28 | "`runner/ops/exec.py:499`, `script must be a string`: the same…" | pre-release | flows |  |
| 29 | "`runner/ops/extsources.py:289`, `names no path`: every value that would…" | pre-release | flows |  |
| 30 | "The largest remaining gaps in shipped code, from…" | pre-release | flows |  |
| 31 | "In the tools, `de_dust_corpus.py` (638 lines unrun), `repair_script_imports.py`,…" | pre-release | flows |  |
