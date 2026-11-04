# Findings — docs/infrastructure-documents/proofs/stage7-5000.md

Source: docs/infrastructure-documents/proofs/stage7-5000.md, reviewed at main dab6cd3d.
Sentence units: 32. Flagged: 2. Categories: pre-release 32, post-release 0.

The 5,000 rung record: the run itself added to the standing argument, counts matching the earlier rungs, scope restated. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the record of the gate property…" | pre-release | flows |  |
| 2 | "The stage names now follow the ladder one…" | pre-release | flows |  |
| 3 | "`stage6-cap.md` recorded this rung as the same searched…" | pre-release | flows |  |
| 4 | "That argument stands, and this stage does not…" | pre-release | flows |  |
| 5 | "What this stage adds is the run itself…" | pre-release | flows |  |
| 6 | "The bound is a declared interpretation in `Gate.tla`'s…" | pre-release | flows |  |
| 7 | "The copy of the model on `main` keeps…" | pre-release | flows |  |
| 8 | "For this stage's check, a scratch copy of…" | pre-release | flows |  |
| 9 | "The scratch copy was diffed against the tree…" | pre-release | flows |  |
| 10 | "No action, invariant, or message field differs." | pre-release | flows |  |
| 11 | "`Claim.tla` and the remaining configurations are unchanged from…" | pre-release | flows |  |
| 12 | "TLC 2.19, each run exhaustive, on Java 21." | pre-release | flows |  |
| 13 | "Every run starts from 786,432 initial states, and…" | pre-release | flows |  |
| 14 | "The fingerprint collision estimates TLC printed were on…" | pre-release | flows |  |
| 15 | "| Configuration | Invariants | Result at 5,000…" | pre-release | flagged | A table header row — structure, not a sentence |
| 16 | "|---|---|---|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 17 | "| Audience enforce (`GateEnforce.cfg`) | `P1Inv`, `SensorInv`, `AudienceWasRequired`…" | pre-release | flows |  |
| 18 | "| Audience off (`GateDefault.cfg`) | `P1Inv`, `SensorInv` |…" | pre-release | flows |  |
| 19 | "| Audience audit (`GateAudit.cfg`) | `P1Inv`, `SensorInv` |…" | pre-release | flows |  |
| 20 | "| Claim race (`Claim.cfg`) | `AtMostOnce` | holds…" | pre-release | flows |  |
| 21 | "The counts match the 49, 500, and cap…" | pre-release | flows |  |
| 22 | "What the rung changes is the set of…" | pre-release | flows |  |
| 23 | "Both witness configurations were run at this bound,…" | pre-release | flows |  |
| 24 | "`GateWitness.cfg` (`NothingExecutes`, audience enforce) fails with a counterexample…" | pre-release | flows |  |
| 25 | "The strong form still lets a good job…" | pre-release | flows |  |
| 26 | "`GateDefaultWitness.cfg` (`AudienceWasRequired`, audience off) fails with a counterexample…" | pre-release | flows |  |
| 27 | "Clause 4 is still vacuous in the default…" | pre-release | flows |  |
| 28 | "`runner/tests/test_proof_constraints.py` runs 67 tests, all passing, and `runner/tests/test_proof_conformance.py`…" | pre-release | flows |  |
| 29 | "The check changed no runner behaviour and no…" | pre-release | flows |  |
| 30 | "P1(5000) holding says nothing new about the rungs…" | pre-release | flows |  |
| 31 | "The model's scope is otherwise the first rung's…" | pre-release | flows |  |
| 32 | "The standing challenge in `thinking.md` is unchanged by…" | pre-release | flows |  |
