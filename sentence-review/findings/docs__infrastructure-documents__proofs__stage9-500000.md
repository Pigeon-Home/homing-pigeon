# Findings — docs/infrastructure-documents/proofs/stage9-500000.md

Source: docs/infrastructure-documents/proofs/stage9-500000.md, reviewed at main cbb52068.
Sentence units: 31. Flagged: 1. Categories: pre-release 31, post-release 0.

A model-checking record at the 500,000-character bound: what the stage is, how the bound was set, the results table, the 2 witnesses that are supposed to fail, the conformance family after, and a closing section on what the result does not say. The chain is deliberate — each section answers the previous section's question. The results table's header row (unit 14) is structure and is flagged on that ground alone; its 4 data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the record of the gate property…" | pre-release | flows |  |
| 2 | "The stage was defined and not run." | pre-release | flows |  |
| 3 | "This is its own run." | pre-release | flows |  |
| 4 | "The character count is not a state variable,…" | pre-release | flows |  |
| 5 | "The argument is the one `stage6-cap.md` gives, and…" | pre-release | flows |  |
| 6 | "What this stage adds is the run at…" | pre-release | flows |  |
| 7 | "A scratch copy of `Gate.tla` declares P1(500000) in…" | pre-release | flows |  |
| 8 | "Diffed against the tree copy, the difference is…" | pre-release | flows |  |
| 9 | "No action, invariant, or message field differs." | pre-release | flows |  |
| 10 | "The tree copy stays at the production-cap declaration,…" | pre-release | flows |  |
| 11 | "`Claim.tla` is unchanged." | pre-release | flows |  |
| 12 | "TLC 2.19, each run exhaustive, on Java 17." | pre-release | flows |  |
| 13 | "Every run starts from 786,432 initial states, and…" | pre-release | flows |  |
| 14 | "Configuration \| Invariants \| Result at 500,000 \|…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 15 | "Audience enforce \| `P1Inv`, `SensorInv`, `AudienceWasRequired` \| holds…" | pre-release | flows |  |
| 16 | "Audience off \| `P1Inv`, `SensorInv` \| holds \|…" | pre-release | flows |  |
| 17 | "Audience audit \| `P1Inv`, `SensorInv` \| holds \|…" | pre-release | flows |  |
| 18 | "Claim race \| `AtMostOnce` \| holds \| 7…" | pre-release | flows |  |
| 19 | "The counts match the earlier rungs exactly." | pre-release | flows |  |
| 20 | "`P1Inv` holding over that set is, at this…" | pre-release | flows |  |
| 21 | "`GateWitness.cfg` fails as it should: a good job…" | pre-release | flows |  |
| 22 | "3,095,425 generated, 2,308,999 distinct." | pre-release | flows |  |
| 23 | "`GateDefaultWitness.cfg` fails as it should: with the audience…" | pre-release | flows |  |
| 24 | "3,106,561 generated, 2,320,141 distinct." | pre-release | flows |  |
| 25 | "Under enforce, clause 4 holds." | pre-release | flows |  |
| 26 | "The constraints module, the conformance module, and the…" | pre-release | flows |  |
| 27 | "`test_skip_registry.py` runs 5, all passing." | pre-release | flows |  |
| 28 | "No runner behaviour changed, and no model file…" | pre-release | flows |  |
| 29 | "P1(500000) holding says nothing new about the cap…" | pre-release | flows |  |
| 30 | "A script of half a million characters is…" | pre-release | flows |  |
| 31 | "The content-independence series is a different artefact." | pre-release | flows |  |
