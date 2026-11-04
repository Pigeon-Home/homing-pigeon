# Findings — docs/steady/reports/v3.13.27-coverage.md

Source: docs/steady/reports/v3.13.27-coverage.md, reviewed at main e2a8e8e2.
Sentence units: 85. Flagged: 14. Categories: pre-release 85, post-release 0.

A generated coverage snapshot for 3.13.27: 7 tables with a short frame. The frame connects; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->" | pre-release | flows |  |
| 2 | "This report belongs to package 3.13.27, copied forward…" | pre-release | flows |  |
| 3 | "The narrative below is the baseline edition's, carried…" | pre-release | flows |  |
| 4 | "It began as main at 933dbf4b, the day…" | pre-release | flows |  |
| 5 | "Two measurements, because the measuring box and CI…" | pre-release | flows |  |
| 6 | "**CI, coverage.py** (`coverage.yml`, run 40261270767 on c122691d, 3.13.5;…" | pre-release | flows |  |
| 7 | "| Platform | Covered | Never executed |" | pre-release | flagged | A table header row — structure, not a sentence |
| 8 | "|---|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 9 | "| Linux | 97.9% | 428 statements |" | pre-release | flows |  |
| 10 | "| Windows | 96.8% | 715 statements |" | pre-release | flows |  |
| 11 | "**This report's box, statement coverage** (the stdlib tracer…" | pre-release | flows |  |
| 12 | "| | Covered | Missed | Total |" | pre-release | flagged | A table header row — structure, not a sentence |
| 13 | "|---|---:|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 14 | "| Statements, `runner/` without the shipped extensions |…" | pre-release | flows |  |
| 15 | "| Statements, `runner/` with the extensions | 98.8%…" | pre-release | flows |  |
| 16 | "5023 tests ran in 9 shards." | pre-release | flows |  |
| 17 | "The failures were the hypothesis-backed modules, which this…" | pre-release | flows |  |
| 18 | "| Package | Statements | Covered | Missed…" | pre-release | flagged | A table header row — structure, not a sentence |
| 19 | "|---|---:|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 20 | "| v3.7.22 | 8697 | 85.5% | 1259…" | pre-release | flows |  |
| 21 | "| v3.7.30 | 9441 | 91.8% | 778…" | pre-release | flows |  |
| 22 | "| v3.11.1 | 15326 | 94.2% | 890…" | pre-release | flows |  |
| 23 | "| v3.12.20 | 16872 | 96.8% | 546…" | pre-release | flows |  |
| 24 | "| v3.12.61 | 19260 | 95.2% | 932…" | pre-release | flows |  |
| 25 | "| v3.12.65 | 19369 | 95.4% | 883…" | pre-release | flows |  |
| 26 | "| 3.13.8 (CI, Linux) | about 20400 |…" | pre-release | flows |  |
| 27 | "The package has more than doubled since v3.7.22…" | pre-release | flows |  |
| 28 | "The dip at v3.12.61 was the hosting and…" | pre-release | flows |  |
| 29 | "By area, on this box (statements):" | pre-release | flows |  |
| 30 | "| Area | Statements | Covered |" | pre-release | flagged | A table header row — structure, not a sentence |
| 31 | "|---|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 32 | "| `runner/extensions` | 8085 | 99.4% |" | pre-release | flows |  |
| 33 | "| `runner/ops` | 8051 | 99.5% |" | pre-release | flows |  |
| 34 | "| `runner/runner.py` | 3523 | 98.0% |" | pre-release | flows |  |
| 35 | "| `runner/wire` | 3300 | 98.1% |" | pre-release | flows |  |
| 36 | "| `runner/oracle` | 2793 | 99.5% |" | pre-release | flows |  |
| 37 | "| `runner/guard` | 953 | 99.0% |" | pre-release | flows |  |
| 38 | "| `runner/transport_extensions` | 920 | 98.2% |" | pre-release | flows |  |
| 39 | "| `runner/hosting` | 881 | 89.9% |" | pre-release | flows |  |
| 40 | "| `runner/cloud` | 480 | 97.9% |" | pre-release | flows |  |
| 41 | "The files under 96%:" | pre-release | flows |  |
| 42 | "| File | Covered | Missed | Statements…" | pre-release | flagged | A table header row — structure, not a sentence |
| 43 | "|---|---:|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 44 | "| `hosting/httpdoor.py` | 55.3% | 21 | 47…" | pre-release | flows |  |
| 45 | "| `ops/live.py` | 77.8% | 2 | 9…" | pre-release | flows |  |
| 46 | "| `hosting/cli.py` | 83.3% | 34 | 204…" | pre-release | flows |  |
| 47 | "| `hosting/billing.py` | 92.2% | 13 | 166…" | pre-release | flows |  |
| 48 | "| `ops/oracle_page.py` | 92.9% | 1 | 14…" | pre-release | flows |  |
| 49 | "| `hosting/base.py` | 93.6% | 5 | 78…" | pre-release | flows |  |
| 50 | "| `transport_extensions/queues/__main__.py` | 93.7% | 10 | 158…" | pre-release | flows |  |
| 51 | "| `extensions/pi-health/pi_health.py` | 94.2% | 15 | 260…" | pre-release | flows |  |
| 52 | "| `hosting/inventory.py` | 94.7% | 4 | 75…" | pre-release | flows |  |
| 53 | "| `ops/cli.py` | 94.8% | 5 | 96…" | pre-release | flows |  |
| 54 | "| `hosting/fly.py` | 95.0% | 3 | 60…" | pre-release | flows |  |
| 55 | "| `hosting/hetzner.py` | 95.7% | 2 | 47…" | pre-release | flows |  |
| 56 | "| `ops/startup.py` | 95.8% | 5 | 118…" | pre-release | flows |  |
| 57 | "`runner/hosting` is the one area below 95%, and…" | pre-release | flows |  |
| 58 | "Both are closed in this package (below)." | pre-release | flows |  |
| 59 | "`ops/live.py`'s two lines are the host-imported-first fallback of…" | pre-release | flows |  |
| 60 | "`pi_health.py`'s lines are its Windows memory reader, run…" | pre-release | flows |  |
| 61 | "`runner/tools/coverage_targets.py` reads every gap against the AST and…" | pre-release | flows |  |
| 62 | "On this box, among functions with two or…" | pre-release | flows |  |
| 63 | "| Class | Functions | Meaning, and what…" | pre-release | flagged | A table header row — structure, not a sentence |
| 64 | "|---|---:|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 65 | "| `logic` | 30 | the main flow…" | pre-release | flows |  |
| 66 | "| `guard` | 13 | one early refusal:…" | pre-release | flows |  |
| 67 | "| `except` | 7 | a handler: the…" | pre-release | flows |  |
| 68 | "| `platform` | 2 | the other OS's…" | pre-release | flows |  |
| 69 | "| `shadowed` | 0 | a def rebound…" | pre-release | flows |  |
| 70 | "The largest `logic` gaps after the hosting pair:…" | pre-release | flows |  |
| 71 | "`runner/tests/test_hosting_cli_main.py`: `homing-pigeon-host` through `main()` for every subcommand, and…" | pre-release | flows |  |
| 72 | "`cli.py` goes from 83.3% to the low lines…" | pre-release | flows |  |
| 73 | "`runner/tests/test_hosting_httpdoor.py`: the real `UrllibHttp` against a loopback server:…" | pre-release | flows |  |
| 74 | "It found one defect: a malformed URL raised…" | pre-release | flows |  |
| 75 | "The dead `_transports_arg` in runner.py, which coverage had…" | pre-release | flows |  |
| 76 | "Removed, with a guard (`RunnerHasNoShadowedDefs`) so the shape…" | pre-release | flows |  |
| 77 | "One row per cycle, appended by the campaign…" | pre-release | flows |  |
| 78 | "Statements and branches are coverage.py's on the rig,…" | pre-release | flows |  |
| 79 | "| Cycle | Commit | Statements | Branches…" | pre-release | flagged | A table header row — structure, not a sentence |
| 80 | "|---|---|---:|---:|---:|---:|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 81 | "| 0 (baseline) | 933dbf4b | 97.9% (CI)…" | pre-release | flows |  |
| 82 | "| 1 | db3bcc46 | 99.1% | 97.0%…" | pre-release | flows |  |
| 83 | "| 2 | 57f419d3 | 99.3% | 97.1%…" | pre-release | flows |  |
| 84 | "CI's way, with coverage.py:" | pre-release | flows |  |
| 85 | "With more examples per property test, for a…" | pre-release | flows |  |
