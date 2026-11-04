# Findings — docs/steady/reports/first-ping-readme.md

Source: docs/steady/reports/first-ping-readme.md, reviewed at main cbb52068.
Sentence units: 12. Flagged: 3. Categories: pre-release 12, post-release 0.

A timing record: what the first-ping round trip costs, the budget that explains the cost, and the runs table. The prose chain is tight — the budget paragraph spends the seconds the opening paragraph counts. 2 units are not sentences: the stamp comment at the top (unit 1) and the fragment that opens the document (unit 2); the runs table's header row (unit 10) is structure, flagged on the same ground as the other records in this pass. The 2 data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "How long the README's first prompt takes to…" | pre-release | flagged | Fragment with no verb; it names the topic but does not lead into the first real sentence as a sentence |
| 3 | "Every row is one batch from `runner/tools/first_ping.py`, kept…" | pre-release | flows |  |
| 4 | "`bench` rows are the runner's own leg on…" | pre-release | flows |  |
| 5 | "`live` rows are the whole round trip timed…" | pre-release | flows |  |
| 6 | "An email round trip is the provider's delivery…" | pre-release | flows |  |
| 7 | "The poll wait is the large term: 0…" | pre-release | flows |  |
| 8 | "The runner's work is milliseconds (the `bench` rows),…" | pre-release | flows |  |
| 9 | "A box that must hold the 30 seconds…" | pre-release | flows |  |
| 10 | "When (UTC) \| Mode \| Provider \| Kind…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 11 | "2026-10-28T01:38:22Z \| bench \| in-memory \| ping \|…" | pre-release | flows |  |
| 12 | "2026-10-28T01:38:23Z \| bench \| in-memory \| exec \|…" | pre-release | flows |  |
