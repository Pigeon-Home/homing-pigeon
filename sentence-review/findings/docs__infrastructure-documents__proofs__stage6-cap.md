# Findings — docs/infrastructure-documents/proofs/stage6-cap.md

Source: docs/infrastructure-documents/proofs/stage6-cap.md, reviewed at main 720110b0.
Sentence units: 51. Flagged: 1. Categories: pre-release 51, post-release 0.

The stage 6 cap record: the argument that the rungs are 1 searched set, the 1 re-run at the production cap, the results table, the road not taken (an unbounded length), and an appended first-hand re-check. The argument chains step by step and the closing verification list re-walks it. The results table's header row (unit 23) is structure and is flagged on that ground alone; its 6 data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "P1(500) is `stage6-rung500.md`." | pre-release | flows |  |
| 2 | "This record is the rest of item 1:…" | pre-release | flows |  |
| 3 | "`stage6-rung500.md` already says the part that matters." | pre-release | flows |  |
| 4 | "The character count is not a state variable." | pre-release | flows |  |
| 5 | "`Init` admits the same cross product at every…" | pre-release | flows |  |
| 6 | "The graph TLC walks at 49, at 500,…" | pre-release | flows |  |
| 7 | "What a rung changes is the set of…" | pre-release | flows |  |
| 8 | "A content check that appeared only after some…" | pre-release | flows |  |
| 9 | "The check order has no such step." | pre-release | flows |  |
| 10 | "Stage 3 matched every gate step to the…" | pre-release | flows |  |
| 11 | "So P1(5000), P1(50000), and P1(500000) are not four…" | pre-release | flows |  |
| 12 | "Copying the table four times and calling each…" | pre-release | flows |  |
| 13 | "They are recorded here as the same checked…" | pre-release | flows |  |
| 14 | "The one that was re-run, rather than copied…" | pre-release | flows |  |
| 15 | "`Gate.tla` now states the bound as 1048576 characters." | pre-release | flows |  |
| 16 | "That number is the production cap's own number." | pre-release | flows |  |
| 17 | "The code's cap is 1048576 UTF-8 bytes (C2)." | pre-release | flows |  |
| 18 | "A character is at least one byte, so…" | pre-release | flows |  |
| 19 | "P1(1048576) covers every script that can pass the…" | pre-release | flows |  |
| 20 | "The two measures stay different measures: characters in…" | pre-release | flows |  |
| 21 | "TLC 2.19 on Java 17, each run exhaustive." | pre-release | flows |  |
| 22 | "The counts match the 500 rung and the…" | pre-release | flows |  |
| 23 | "Configuration \| Invariants \| Result \| Generated \|…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 24 | "Audience enforce \| `P1Inv`, `SensorInv`, `AudienceWasRequired` \| holds…" | pre-release | flows |  |
| 25 | "Audience off \| `P1Inv`, `SensorInv` \| holds \|…" | pre-release | flows |  |
| 26 | "Audience audit \| `P1Inv`, `SensorInv` \| holds \|…" | pre-release | flows |  |
| 27 | "Claim race \| `AtMostOnce` \| holds \| 7…" | pre-release | flows |  |
| 28 | "Witness, enforce \| `NothingExecutes` \| fails, as expected…" | pre-release | flows |  |
| 29 | "Witness, audience off \| `AudienceWasRequired` \| fails, as…" | pre-release | flows |  |
| 30 | "The witnesses are the same two shapes as…" | pre-release | flows |  |
| 31 | "A good job still executes." | pre-release | flows |  |
| 32 | "With the audience feature off, a job still…" | pre-release | flows |  |
| 33 | "The strong form still requires it." | pre-release | flows |  |
| 34 | "One further step is available: drop the bound…" | pre-release | flows |  |
| 35 | "It was not taken." | pre-release | flows |  |
| 36 | "The cap rung already covers every script the…" | pre-release | flows |  |
| 37 | "An unbounded length would be a claim about…" | pre-release | flows |  |
| 38 | "That is a wider claim than the code,…" | pre-release | flows |  |
| 39 | "After this raise, `test_proof_constraints.py` and `test_proof_conformance.py` together run…" | pre-release | flows |  |
| 40 | "The raise changed a comment in `Gate.tla` and…" | pre-release | flows |  |
| 41 | "It changed no runner behaviour." | pre-release | flows |  |
| 42 | "This record was re-checked first-hand after it landed,…" | pre-release | flows |  |
| 43 | "**The check was re-run.** TLC 2.19 (the `v1.7.4`…" | pre-release | flows |  |
| 44 | "Every number in the table above reproduced exactly:…" | pre-release | flows |  |
| 45 | "Each gate run starts from 786,432 initial states." | pre-release | flows |  |
| 46 | "**The code was re-read.** `handle_mail` (`runner/ops/mail.py`) still performs…" | pre-release | flows |  |
| 47 | "No step branches on a script's character count…" | pre-release | flows |  |
| 48 | "The argument this record rests on — the…" | pre-release | flows |  |
| 49 | "**The tests.** The two files named above now…" | pre-release | flows |  |
| 50 | "The 85 in the record was the family's…" | pre-release | flows |  |
| 51 | "Not a correction: a point-in-time count, since overtaken,…" | pre-release | flows |  |
