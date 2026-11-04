# Findings — docs/infrastructure-documents/proofs/stage6-rung500.md

Source: docs/infrastructure-documents/proofs/stage6-rung500.md, reviewed at main dab6cd3d.
Sentence units: 39. Flagged: 2. Categories: pre-release 39, post-release 0.

The first raise of the bound, to 500: what the raise changes, the re-runs, the witness counterexamples, and what the rung does not say. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the record of the first raise…" | pre-release | flows |  |
| 2 | "The first rung, P1(49), is `stage2.md`; its checked…" | pre-release | flows |  |
| 3 | "The bound is not a configuration constant and…" | pre-release | flows |  |
| 4 | "`Gate.tla` declares it in its header: every message…" | pre-release | flows |  |
| 5 | "The only length the code's gate measures is…" | pre-release | flows |  |
| 6 | "Raising the bound is therefore a change to…" | pre-release | flows |  |
| 7 | "The header of `Gate.tla` now states the second…" | pre-release | flows |  |
| 8 | "No action, invariant, or message field changed." | pre-release | flows |  |
| 9 | "`Claim.tla` is unchanged; it was re-run as it…" | pre-release | flows |  |
| 10 | "What the raise changes is the claim, not…" | pre-release | flows |  |
| 11 | "`Init` admits the full cross product of the…" | pre-release | flows |  |
| 12 | "What widens is the set of real handlings…" | pre-release | flows |  |
| 13 | "`P1Inv` holding over the searched set is, at…" | pre-release | flows |  |
| 14 | "That argument is the substance of this rung,…" | pre-release | flows |  |
| 15 | "Stage 3 reconciled those features against the code…" | pre-release | flows |  |
| 16 | "A gate input that appears only when scripts…" | pre-release | flows |  |
| 17 | "TLC 2.19 (the `v1.7.4` tools jar), each run…" | pre-release | flows |  |
| 18 | "This pass ran on Java 21; stage 2's…" | pre-release | flows |  |
| 19 | "Before the raise, the unmodified model was re-run…" | pre-release | flows |  |
| 20 | "The fingerprint collision estimates TLC printed were on…" | pre-release | flows |  |
| 21 | "| Configuration | Invariants | Result at 500…" | pre-release | flagged | A table header row — structure, not a sentence |
| 22 | "|---|---|---|---:|---:|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 23 | "| Audience enforce (`GateEnforce.cfg`) | `P1Inv`, `SensorInv`, `AudienceWasRequired`…" | pre-release | flows |  |
| 24 | "| Audience off (`GateDefault.cfg`) | `P1Inv`, `SensorInv` |…" | pre-release | flows |  |
| 25 | "| Audience audit (`GateAudit.cfg`) | `P1Inv`, `SensorInv` |…" | pre-release | flows |  |
| 26 | "| Claim race (`Claim.cfg`) | `AtMostOnce` | holds…" | pre-release | flows |  |
| 27 | "Every run starts from 786,432 initial states, and…" | pre-release | flows |  |
| 28 | "The counts are identical at the two rungs…" | pre-release | flows |  |
| 29 | "The claim that changed is the one the…" | pre-release | flows |  |
| 30 | "Both witness configurations were re-run at this rung,…" | pre-release | flows |  |
| 31 | "`GateWitness.cfg` (`NothingExecutes`, audience enforce) fails with a counterexample…" | pre-release | flows |  |
| 32 | "The strong form still lets a good job…" | pre-release | flows |  |
| 33 | "`GateDefaultWitness.cfg` (`AudienceWasRequired`, audience off) fails with a counterexample…" | pre-release | flows |  |
| 34 | "Clause 4 is still vacuous in the default…" | pre-release | flows |  |
| 35 | "Stage 6's done means the conformance family still…" | pre-release | flows |  |
| 36 | "After the raise, on this branch: `runner/tests/test_proof_constraints.py` runs…" | pre-release | flows |  |
| 37 | "Stage 5 is still open — the rest…" | pre-release | flows |  |
| 38 | "P1(500) holding says nothing about P1(5000) or any…" | pre-release | flows |  |
| 39 | "The model's scope is otherwise the first rung's…" | pre-release | flows |  |
