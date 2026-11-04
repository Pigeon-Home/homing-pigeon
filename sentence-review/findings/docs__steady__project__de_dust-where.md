# Findings — docs/steady/project/de_dust-where.md

Source: docs/steady/project/de_dust-where.md, reviewed at main 553181d8.
Sentence units: 47. Flagged: 4. Categories: pre-release 47, post-release 0.

The campaign index: which question lives in which commit, in 2 tables with a short prose frame. The rows flow as index entries; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The working tree was clean when this was…" | pre-release | flows |  |
| 2 | "Everything below is already on `main`." | pre-release | flows |  |
| 3 | "This file is the index." | pre-release | flows |  |
| 4 | "The questions are `docs/seats/questions.md`." | pre-release | flows |  |
| 5 | "The plan is `docs/project/de_dust.md`." | pre-release | flows |  |
| 6 | "The tool is `runner/tools/de_dust_corpus.py`." | pre-release | flows |  |
| 7 | "The corpus is `runner/tests/de_dust/<target>.jsonl`, and `runner/tests/test_de_dust_corpus.py` replays it." | pre-release | flows |  |
| 8 | "| Q | What | Commit |" | pre-release | flagged | A table header row — structure, not a sentence |
| 9 | "|---|------|--------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 10 | "| Q65 | the mail path, the seventh…" | pre-release | flows |  |
| 11 | "| Q66 | the DTLS target | [`4ad13c89b827`](https://github.com/Pigeon-Home/homing-pigeon/commit/4ad13c89b827)…" | pre-release | flows |  |
| 12 | "| Q67 | the board target | [`1db7e3dcd04f`](https://github.com/Pigeon-Home/homing-pigeon/commit/1db7e3dcd04f)…" | pre-release | flows |  |
| 13 | "| Q68 | the channel target | [`286639879108`](https://github.com/Pigeon-Home/homing-pigeon/commit/286639879108)…" | pre-release | flows |  |
| 14 | "| Q69 | the manifest target | [`594e93ab582f`](https://github.com/Pigeon-Home/homing-pigeon/commit/594e93ab582f)…" | pre-release | flows |  |
| 15 | "| Q70 | the sequence contract on `local`…" | pre-release | flows |  |
| 16 | "| Q71 | the corpus agrees on the…" | pre-release | flows |  |
| 17 | "| Q72 | the grammar dictionary from the…" | pre-release | flows |  |
| 18 | "| Q73 | 20,000 rounds under that dictionary…" | pre-release | flows |  |
| 19 | "| Q74 | the posted capture's shape, rebuilt…" | pre-release | flows |  |
| 20 | "| Q75 | one steered grow of the…" | pre-release | flows |  |
| 21 | "| Q76 | the same four again |…" | pre-release | flows |  |
| 22 | "| Q77 | a third grow of the…" | pre-release | flows |  |
| 23 | "| Q78 | a non-finite priority on disk…" | pre-release | flows |  |
| 24 | "| Q79 | a non-finite float under any…" | pre-release | flows |  |
| 25 | "| Q80 | local, the grow the crash…" | pre-release | flows |  |
| 26 | "| Q81 | the two that were still…" | pre-release | flows |  |
| 27 | "| Q82 | local, again | [`59d27db0216b`](https://github.com/Pigeon-Home/homing-pigeon/commit/59d27db0216b) |" | pre-release | flows |  |
| 28 | "| Q83 | local, a third time |…" | pre-release | flows |  |
| 29 | "Q77 through Q83 were checked as ancestors of…" | pre-release | flows |  |
| 30 | "Each id above is that commit." | pre-release | flows |  |
| 31 | "The working tree was clean." | pre-release | flows |  |
| 32 | "Nothing in this table was still waiting on…" | pre-release | flows |  |
| 33 | "Q74 does not copy the capture." | pre-release | flows |  |
| 34 | "The capture stays at `docs/reports/live-2026-10-25/`." | pre-release | flows |  |
| 35 | "The seeds are invented ids under the corpus…" | pre-release | flows |  |
| 36 | "The desk's lane in the same days, under…" | pre-release | flows |  |
| 37 | "| What | Commit |" | pre-release | flagged | A table header row — structure, not a sentence |
| 38 | "|------|--------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 39 | "| the board under the sequence contract (`board_ops`),…" | pre-release | flows |  |
| 40 | "| the channel inbox under the sequence contract…" | pre-release | flows |  |
| 41 | "| the local inbox under the sequence contract…" | pre-release | flows |  |
| 42 | "| the provenance contract on the verifiers; a…" | pre-release | flows |  |
| 43 | "| the generated grammar dictionary (`grammar.json`) | [`01aa1ffe`](https://github.com/Pigeon-Home/homing-pigeon/commit/01aa1ffe)…" | pre-release | flows |  |
| 44 | "| steered grows, the archive, the learning dictionary,…" | pre-release | flows |  |
| 45 | "| the mutation survivors (`runner/tools/de_dust_survivors.py`, `survivors.json`) | [`27837979`](https://github.com/Pigeon-Home/homing-pigeon/commit/27837979)…" | pre-release | flows |  |
| 46 | "| the survivors' seeds, the `secret` target |…" | pre-release | flows |  |
| 47 | "Not started: any further live capture the conductor…" | pre-release | flows |  |
