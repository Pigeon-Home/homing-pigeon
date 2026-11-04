# Findings — docs/steady/reports/2026-10-27.md

Source: docs/steady/reports/2026-10-27.md, reviewed at main 670cf354.
Sentence units: 22. Flagged: 2. Categories: pre-release 22, post-release 0.

A dated stamp census: a short frame and the stamp table. The prose connects; the table structure is the only flag. All pre-release, a record of its date.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The first run of `runner/tools/stamp_audit.py`, the day the…" | pre-release | flows |  |
| 2 | "Kept as the baseline; the stamp-audit workflow writes…" | pre-release | flows |  |
| 3 | "<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab --> 2764 commits read; rules…" | pre-release | flows |  |
| 4 | "| Stamp | Record | Commits | Sessions…" | pre-release | flagged | A table header row — structure, not a sentence |
| 5 | "|---|---|---:|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 6 | "| `10000c2a` | recycled | 71 | gieBDp…" | pre-release | flows |  |
| 7 | "| `200003d4` | recycled | 10 | mxBQgG…" | pre-release | flows |  |
| 8 | "| `30000f1a` | recycled | 18 | AUmNoV…" | pre-release | flows |  |
| 9 | "| `40000e00` | active | 43 | 47XoUD…" | pre-release | flows |  |
| 10 | "| `50000c8e` | recycled | 224 | TXoDmE…" | pre-release | flows |  |
| 11 | "| `58316a92` | recycled | 464 | (no…" | pre-release | flows |  |
| 12 | "| `60000b3a` | active | 72 | aRRHEB…" | pre-release | flows |  |
| 13 | "| `70000a51` | active | 1 | aRRHEB…" | pre-release | flows |  |
| 14 | "| `00000000` | active | 1 | (no…" | pre-release | flows |  |
| 15 | "none" | pre-release | flows |  |
| 16 | "rule 1: stamp 40000e00 was signed from 2…" | pre-release | flows |  |
| 17 | "rule 1: stamp 50000c8e was signed from 2…" | pre-release | flows |  |
| 18 | "rule 1: stamp 60000b3a was signed from 2…" | pre-release | flows |  |
| 19 | "rule 2: session session_01QXEbJ9s1GFbAw6kKaRRHEB signed as 40000e00, 50000c8e,…" | pre-release | flows |  |
| 20 | "One Claude Code session, `session_01QXEbJ9s1GFbAw6kKaRRHEB`, signed as four…" | pre-release | flows |  |
| 21 | "Each of the three earlier stamps was held…" | pre-release | flows |  |
| 22 | "From the enforced moment on, `70000a51` is that…" | pre-release | flows |  |
