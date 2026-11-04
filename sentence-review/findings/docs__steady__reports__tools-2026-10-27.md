# Findings — docs/steady/reports/tools-2026-10-27.md

Source: docs/steady/reports/tools-2026-10-27.md, reviewed at main cbb52068.
Sentence units: 27. Flagged: 3. Categories: pre-release 27, post-release 0.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The whole suite, run once in one process…" | pre-release | flows |  |
| 2 | "Each pass ran in its own `git worktree`…" | pre-release | flows |  |
| 3 | "Lines only, no branches, no child processes." | pre-release | flows |  |
| 4 | "The data beside this file is the tool's…" | pre-release | flows |  |
| 5 | "Report ; Tree ; Tests run ; Result" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 6 | "`tools-before-2026-10-27.json` ; `7f2bc42` ; 7,384 ; OK (skipped=49)" | pre-release | flows |  |
| 7 | "`tools-after-2026-10-27.json` ; `0fad737` ; 7,509 ; OK (skipped=49)" | pre-release | flows |  |
| 8 | "Scope ; Before ; After" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 9 | "`runner/tools/` ; 74.6% (2,038 of 8,011 unrun) ;…" | pre-release | flows |  |
| 10 | "Shipped code (`runner/` without `tests/` and `tools/`) ;…" | pre-release | flows |  |
| 11 | "Tool ; Before ; After ; Test" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 12 | "`ci_run_report.py` ; 0% ; 99.5% ; `test_ci_run_report.py`" | pre-release | flows |  |
| 13 | "`mutation_floor.py` ; 0% ; 98.6% ; `test_mutation_floor.py`" | pre-release | flows |  |
| 14 | "`run_tests_shuffled.py` ; 0% ; 97.7% ; `test_run_tests_shuffled.py`" | pre-release | flows |  |
| 15 | "`repair_script_imports.py` ; 0% ; 96.9% ; `test_repair_script_imports.py`" | pre-release | flows |  |
| 16 | "`run_tests_windows_sim.py` ; 0% ; 97.8% ; `test_run_tests_windows_sim.py`" | pre-release | flows |  |
| 17 | "`fetch_upstream.py` ; 47.4% ; 98.7% ; `test_fetch_upstream.py`" | pre-release | flows |  |
| 18 | "`regression_guard.py` ; 54.7% ; 82.2% ; `test_regression_guard_verdicts.py`" | pre-release | flows |  |
| 19 | "`de_dust_survivors.py` ; 67.3% ; 79.9% ; `test_de_dust_survivors_operators.py`" | pre-release | flows |  |
| 20 | "`de_dust_corpus.py` ; 83.2% ; 83.8% ; `test_de_dust_oracles_bite.py`" | pre-release | flows |  |
| 21 | "The `de_dust_corpus.py` gain is small in lines and…" | pre-release | flows |  |
| 22 | "The corpus replay shows the runner meets every…" | pre-release | flows |  |
| 23 | "`ci_run_report.py`: an origin remote that is not on…" | pre-release | flows |  |
| 24 | "It now falls through to the message that…" | pre-release | flows |  |
| 25 | "`de_dust_survivors.py`: two of its ten mutation operators, `and`…" | pre-release | flows |  |
| 26 | "A commit on main carried three merge conflict…" | pre-release | flows |  |
| 27 | "`de_dust_corpus.py` holds most of what is left (612…" | pre-release | flows |  |
