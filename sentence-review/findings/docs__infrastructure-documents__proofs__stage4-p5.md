# Findings — docs/infrastructure-documents/proofs/stage4-p5.md

Source: docs/infrastructure-documents/proofs/stage4-p5.md, reviewed at main be4b3db4.
Sentence units: 92. Flagged: 1. Categories: pre-release 92, post-release 0.

A stage 4 part 5 record: the P5 replay model, its configurations and witnesses, and what the checker found. The prose runs in the family's standing order and the configuration table sits inside the prose that interprets it. The non-sentence is the table's header row (unit 53); its 3 data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the record of P5's pass through…" | pre-release | flows |  |
| 2 | "P5 is the fourth of stage 4's five…" | pre-release | flows |  |
| 3 | "The statement is in `properties.md` (P5, eleven clauses);…" | pre-release | flows |  |
| 4 | "Stage 2's `Claim.tla` checked the two-handler claim race…" | pre-release | flows |  |
| 5 | "This stage is that owner." | pre-release | flows |  |
| 6 | "The code read for this stage is the…" | pre-release | flows |  |
| 7 | "A job — a job id together with…" | pre-release | flows |  |
| 8 | "The replay cache turns a duplicate away before…" | pre-release | flows |  |
| 9 | "Three edges are priced in the statement rather…" | pre-release | flows |  |
| 10 | "A restart by itself neither grants nor loses…" | pre-release | flows |  |
| 11 | "**The key, and the cache.** A delivery becomes…" | pre-release | flows |  |
| 12 | "The cache is `seen.json` in the state directory,…" | pre-release | flows |  |
| 13 | "It is loaded into memory at startup (`runner/ops/main.py`,…" | pre-release | flows |  |
| 14 | "The horizon an entry is kept for is…" | pre-release | flows |  |
| 15 | "**The first turn-away.** `_early_dispatch` (`runner/runner.py`, line 4653) looks…" | pre-release | flows |  |
| 16 | "No result is sent on this path, and…" | pre-release | flows |  |
| 17 | "**The claim.** In `handle_mail` (`runner/ops/mail.py`, lines 260 to…" | pre-release | flows |  |
| 18 | "Then `_disk_owns` (`runner/ops/misc.py`, line 241) speaks for the…" | pre-release | flows |  |
| 19 | "A live claim file returns not-owned without that…" | pre-release | flows |  |
| 20 | "Otherwise the claim file is created with `O_EXCL`…" | pre-release | flows |  |
| 21 | "The stale rule that governs a claim whose…" | pre-release | flows |  |
| 22 | "The `finally` span (lines 734 to 738) removes…" | pre-release | flows |  |
| 23 | "**The commit.** Execution's result is not sent and…" | pre-release | flows |  |
| 24 | "`commit_and_deliver` (`runner/ops/mail.py`, lines 295 to 318), under `_MAIL_LOCK`,…" | pre-release | flows |  |
| 25 | "A stash that cannot be written raises before…" | pre-release | flows |  |
| 26 | "Rejection results (a cancel honoured, a judge refusal,…" | pre-release | flows |  |
| 27 | "**The resend.** After the claim and before any…" | pre-release | flows |  |
| 28 | "It returns the record only when the record's…" | pre-release | flows |  |
| 29 | "On a match, `handle_mail` (lines 320 to 330)…" | pre-release | flows |  |
| 30 | "On a mismatch it returns no record, and…" | pre-release | flows |  |
| 31 | "The reach of this path is exactly the…" | pre-release | flows |  |
| 32 | "**Delivery, and its window.** A stashed record is…" | pre-release | flows |  |
| 33 | "After `result_stash_retention_sec` (default 86,400) of attempts the record…" | pre-release | flows |  |
| 34 | "From that moment the record is outside the…" | pre-release | flows |  |
| 35 | "Delivery is therefore at-least-once inside the stash window,…" | pre-release | flows |  |
| 36 | "**Aging.** Once per poll (`runner/ops/poll.py`, lines 43 to" | pre-release | flows |  |
| 37 | "the sent records and the retained outputs are…" | pre-release | flows |  |
| 38 | "`output_retention_days` (`_retention_days`, `runner/runner.py`, line 1547: absent or unusable…" | pre-release | flows |  |
| 39 | "The cache's own aging is on its writes…" | pre-release | flows |  |
| 40 | "`Replay.tla` models one job id and two handlings…" | pre-release | flows |  |
| 41 | "A handling moves through the code's own decision…" | pre-release | flows |  |
| 42 | "Against that skeleton stand the four events that…" | pre-release | flows |  |
| 43 | "The claim's space is priced, not assumed away." | pre-release | flows |  |
| 44 | "Executions are counted per digest class; the invariant…" | pre-release | flows |  |
| 45 | "Window events are bounded at one per kind…" | pre-release | flows |  |
| 46 | "The purchase arithmetic is linear — each event…" | pre-release | flows |  |
| 47 | "Two fidelity invariants ride with the claim." | pre-release | flows |  |
| 48 | "`SeenImpliesRecord`: the cache is only ever committed beside…" | pre-release | flows |  |
| 49 | "`DeliveredImpliesRecord`: a delivery exists only for a job…" | pre-release | flows |  |
| 50 | "TLC 2.19 (the `v1.7.4` tools jar) on Java…" | pre-release | flows |  |
| 51 | "Each run is exhaustive inside the bound stated…" | pre-release | flows |  |
| 52 | "Trace output TLC writes beside the model (`*_TTrace_*`,…" | pre-release | flows |  |
| 53 | "Configuration \| File \| Invariants \| Result \|…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 54 | "Full replay shape \| `Replay.cfg` \| `P5Inv`, `SeenImpliesRecord`,…" | pre-release | flows |  |
| 55 | "First-execution witness \| `ReplayWitnessExec.cfg` \| `NothingExecutes` \| fails,…" | pre-release | flows |  |
| 56 | "Resend witness \| `ReplayWitnessResend.cfg` \| `NeverAnswered` \| fails,…" | pre-release | flows |  |
| 57 | "The depth of the main search is 21…" | pre-release | flows |  |
| 58 | "The fingerprint collision estimate TLC printed for the…" | pre-release | flows |  |
| 59 | "The witness runs stop at their counterexamples, so…" | pre-release | flows |  |
| 60 | "The space is small next to the gate…" | pre-release | flows |  |
| 61 | "What the search buys is not breadth of…" | pre-release | flows |  |
| 62 | "To re-run from a bare machine: install a…" | pre-release | flows |  |
| 63 | "`ReplayWitnessExec.cfg` checks `NothingExecutes` — the claim that no…" | pre-release | flows |  |
| 64 | "TLC's counterexample is a handling that arrives, takes…" | pre-release | flows |  |
| 65 | "A model that refused or dropped everything would…" | pre-release | flows |  |
| 66 | "`ReplayWitnessResend.cfg` checks `NeverAnswered` — the claim that no…" | pre-release | flows |  |
| 67 | "Answering happens at exactly one place in the…" | pre-release | flows |  |
| 68 | "No replay path to a second execution was…" | pre-release | flows |  |
| 69 | "The reads behind that verdict are worth naming,…" | pre-release | flows |  |
| 70 | "The cross-process race closes at the claim file,…" | pre-release | flows |  |
| 71 | "An altered body is not a replay path:…" | pre-release | flows |  |
| 72 | "One observation is recorded, in the open:" | pre-release | flows |  |
| 73 | "**O1." | pre-release | flows |  |
| 74 | "The record's digest check is skipped when the…" | pre-release | flows |  |
| 75 | "The direction of the error is toward answering,…" | pre-release | flows |  |
| 76 | "The opinion module is loaded unconditionally in the…" | pre-release | flows |  |
| 77 | "No code was changed in this pass." | pre-release | flows |  |
| 78 | "Arrivals in the model are gate-passing deliveries." | pre-release | flows |  |
| 79 | "A replay that P1 refuses — stale, unsigned,…" | pre-release | flows |  |
| 80 | "In particular the clause 8 argument — the…" | pre-release | flows |  |
| 81 | "The model's claim is one claim state; the…" | pre-release | flows |  |
| 82 | "Stage 3 reconciled them for the race, and…" | pre-release | flows |  |
| 83 | "The one place the composition is load-bearing here…" | pre-release | flows |  |
| 84 | "A crash during a run and a crash…" | pre-release | flows |  |
| 85 | "Whether the first run's side effects completed before…" | pre-release | flows |  |
| 86 | "The claim file's holder test is a pid." | pre-release | flows |  |
| 87 | "A pid recycled by the operating system while…" | pre-release | flows |  |
| 88 | "That is a liveness edge on recovery, recorded…" | pre-release | flows |  |
| 89 | "Delivery's at-least-once half is checked as a mechanism,…" | pre-release | flows |  |
| 90 | "A temporal check that every committed record is…" | pre-release | flows |  |
| 91 | "Other doors that execute work — the board's…" | pre-release | flows |  |
| 92 | "P5 is stated over the job door `handle_mail`…" | pre-release | flows |  |
