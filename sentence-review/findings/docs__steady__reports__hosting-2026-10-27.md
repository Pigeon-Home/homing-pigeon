# Findings — docs/steady/reports/hosting-2026-10-27.md

Source: docs/steady/reports/hosting-2026-10-27.md, reviewed at main 670cf354.
Sentence units: 22. Flagged: 4. Categories: pre-release 22, post-release 0.

A dated hosting test report with 2 tables. The prose connects; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 70000a51-e296-4b2c-bf5b-ba020e23eb91 -->" | pre-release | flows |  |
| 2 | "Measured on a box with no package index,…" | pre-release | flows |  |
| 3 | "Lines only, no branches." | pre-release | flows |  |
| 4 | "The data beside this file is the tool's…" | pre-release | flows |  |
| 5 | "| Report | Sources | Tests |" | pre-release | flagged | A table header row — structure, not a sentence |
| 6 | "|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 7 | "| `hosting-2026-10-27.json` | `runner/hosting/`, `runner/transport_extensions/queues/` | the 200…" | pre-release | flows |  |
| 8 | "| `send-job-2026-10-27.json` | `runner/cloud/send_job.py` | every module that…" | pre-release | flows |  |
| 9 | "| Module | Before the edge tests |…" | pre-release | flagged | A table header row — structure, not a sentence |
| 10 | "|---|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 11 | "| `runner/hosting/` (11 modules) | 99.1% overall |…" | pre-release | flows |  |
| 12 | "| `runner/transport_extensions/queues/__main__.py` | 93.5% (11 missed) | 98.8%…" | pre-release | flows |  |
| 13 | "| the queue functions in `send_job.py` (`post_to_queue`, `_queue_call`,…" | pre-release | flows |  |
| 14 | "| `runner/cloud/send_job.py`, whole file, all its tests |…" | pre-release | flows |  |
| 15 | "The 16 tests that closed the queue gaps…" | pre-release | flows |  |
| 16 | "`runner/hosting/cli.py`, 7 lines: the script-mode import fallback (5…" | pre-release | flows |  |
| 17 | "`runner/hosting/fly.py`, 1 line: the `return False` after `raise_for`,…" | pre-release | flows |  |
| 18 | "`runner/transport_extensions/queues/__main__.py`, 2 lines: the `__main__` exit and one…" | pre-release | flows |  |
| 19 | "`runner/cloud/send_job.py`, 46 lines, outside the queue code: the…" | pre-release | flows |  |
| 20 | "They belong to the inline-files and key-name work…" | pre-release | flows |  |
| 21 | "`runner/tools/run_tests_parallel.py`, two shards: 7,174 tests." | pre-release | flows |  |
| 22 | "The failures were the ones this box always…" | pre-release | flows |  |
