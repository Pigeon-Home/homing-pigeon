# Findings — docs/infrastructure-documents/proofs/stage6-surfaces.md

Source: docs/infrastructure-documents/proofs/stage6-surfaces.md, reviewed at main 720110b0.
Sentence units: 37. Flagged: 2. Categories: pre-release 37, post-release 0.

A model record for the 5 doors beside the job door: the claim first, the doors in a table, what the model folds and checks, the results in a second table, then the useful witness explained, then what this record does not re-check, and a first-hand re-check as a closing list. The chain is careful throughout. The 2 tables' header rows (units 4 and 16) are structure and are flagged on that ground alone; their data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Item 3 of the raise." | pre-release | flows |  |
| 2 | "Five doors stand beside the job door." | pre-release | flows |  |
| 3 | "Each already applies an early bound in the…" | pre-release | flows |  |
| 4 | "Door \| Code \| What the model claims" | pre-release | flagged | Table header row, structure rather than a sentence |
| 5 | "job \| `handle_mail` \| A script runs only…" | pre-release | flows |  |
| 6 | "cancel \| `handle_cancel_mail` \| Same admit. No script" | pre-release | flows |  |
| 7 | "query \| `handle_query_mail` \| Same admit, then an…" | pre-release | flows |  |
| 8 | "board \| `handle_board_mail` \| Same admit, then a…" | pre-release | flows |  |
| 9 | "v2 \| `handle_v2_mail` \| The handler's own line:…" | pre-release | flows |  |
| 10 | "local \| `_ingest_local_envelope` \| A same-box alert. Every…" | pre-release | flows |  |
| 11 | "`boundsOk` folds version, type, identity, freshness, audience, and…" | pre-release | flows |  |
| 12 | "Those checks are the per-door code." | pre-release | flows |  |
| 13 | "The model checks the composition the raise asks…" | pre-release | flows |  |
| 14 | "TLC 2.19 on Java 17." | pre-release | flows |  |
| 15 | "Forty-eight attempts." | pre-release | flows |  |
| 16 | "Configuration \| Invariant \| Result \| Generated \|…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 17 | "Every door \| `SurfacesInv` \| holds \| 144…" | pre-release | flows |  |
| 18 | "An admitted job runs \| `NothingRuns` \| fails,…" | pre-release | flows |  |
| 19 | "An admitted cancel runs nothing \| `CancelRuns` \|…" | pre-release | flows |  |
| 20 | "The cancel witness is the useful one." | pre-release | flows |  |
| 21 | "The cancel is admitted, and it still does…" | pre-release | flows |  |
| 22 | "A model that refused every non-job door would…" | pre-release | flows |  |
| 23 | "The witness shows the accept." | pre-release | flows |  |
| 24 | "The board's own at-most-once is still the board's,…" | pre-release | flows |  |
| 25 | "A query's answer is not re-checked here." | pre-release | flows |  |
| 26 | "Version 2's question and answer are not modelled…" | pre-release | flows |  |
| 27 | "The local path's refusal of every kind but…" | pre-release | flows |  |
| 28 | "This record was re-checked first-hand after it landed,…" | pre-release | flows |  |
| 29 | "**The check was re-run.** TLC 2.19 (the `v1.7.4`…" | pre-release | flows |  |
| 30 | "Both witnesses fail as the record says." | pre-release | flows |  |
| 31 | "Their counts, which the table above left blank,…" | pre-release | flows |  |
| 32 | "A completion, not a correction: no number in…" | pre-release | flows |  |
| 33 | "**The code was re-read.** `_early_dispatch` (`runner/runner.py`) offers each…" | pre-release | flows |  |
| 34 | "Each handler runs the admit chain the model…" | pre-release | flows |  |
| 35 | "The one `execute_job` call in `runner/ops/handlers.py` belongs to…" | pre-release | flows |  |
| 36 | "The local path (`_ingest_local_envelope_inner`) requires the signature, uses…" | pre-release | flows |  |
| 37 | "An admitted cancel kills the job or records…" | pre-release | flows |  |
