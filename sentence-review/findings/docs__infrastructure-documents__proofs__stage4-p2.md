# Findings — docs/infrastructure-documents/proofs/stage4-p2.md

Source: docs/infrastructure-documents/proofs/stage4-p2.md, reviewed at main be4b3db4.
Sentence units: 76. Flagged: 1. Categories: pre-release 76, post-release 0.

A stage 4 part 2 record: the P2 confinement model, its configurations and witnesses, and what the checker found. The prose runs setup, configurations, verdicts in the family's standing order, and the configuration table sits inside the run of prose that interprets it. The non-sentence is the table's header row (unit 36); its 3 data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the record of P2's pass through…" | pre-release | flows |  |
| 2 | "P2 is the first of stage 4's five…" | pre-release | flows |  |
| 3 | "The statement is in `properties.md` (P2, nine clauses);…" | pre-release | flows |  |
| 4 | "The code read for this stage is the…" | pre-release | flows |  |
| 5 | "A job that passed the gate executes, and…" | pre-release | flows |  |
| 6 | "Every quantity that bounds what that execution may…" | pre-release | flows |  |
| 7 | "A job's fields enter those computations only through…" | pre-release | flows |  |
| 8 | "No job field widens either ceiling, and none…" | pre-release | flows |  |
| 9 | "**The sandbox decision.** `runner/runner.py`, `_confinement_argv`, line 340." | pre-release | flows |  |
| 10 | "The mode comes from the configuration alone (`sec_mode(cfg,…" | pre-release | flows |  |
| 11 | "`enforce` with a working mechanism builds the sandbox…" | pre-release | flows |  |
| 12 | "The job is not an input to any…" | pre-release | flows |  |
| 13 | "**The sandbox shape.** `runner/guard/sandbox.py`, `build_bwrap_command`, line 213." | pre-release | flows |  |
| 14 | "The confinement block is read from the configuration…" | pre-release | flows |  |
| 15 | "The fixed flag set is the code constant…" | pre-release | flows |  |
| 16 | "The job workdir is bound read-write at the…" | pre-release | flows |  |
| 17 | "The owner's `extra_flags` and `extra_ro_binds` come from the…" | pre-release | flows |  |
| 18 | "**The one job-influenced addition.** `interpreter_binds`, `runner/guard/sandbox.py`, line 187,…" | pre-release | flows |  |
| 19 | "Finding F1 below records what this means for…" | pre-release | flows |  |
| 20 | "**The watched set and its verdict.** `runner/ops/mail.py`, lines…" | pre-release | flows |  |
| 21 | "No job field is an input to the…" | pre-release | flows |  |
| 22 | "**The result-policy ceiling.** `runner/ops/policy.py`, `apply_result_policy`, line 19: the…" | pre-release | flows |  |
| 23 | "`runner/runner.py`, `query_budget`, line 553: the effective budget is…" | pre-release | flows |  |
| 24 | "`_redact_patterns` (line 447) builds the pattern set from…" | pre-release | flows |  |
| 25 | "**The answers.** `runner/ops/queries.py`, `answer_queries`, line 457: every query…" | pre-release | flows |  |
| 26 | "Attestations are built by `build_attestations` (`runner/ops/attest.py`, line 16)…" | pre-release | flows |  |
| 27 | "The raw-line operations are gated by `_raw_lines_allowed` (`runner/runner.py`,…" | pre-release | flows |  |
| 28 | "`Confine.tla` is a single-decision model, deliberately smaller than…" | pre-release | flows |  |
| 29 | "The initial state picks a job record and…" | pre-release | flows |  |
| 30 | "The job record carries every field the execution…" | pre-release | flows |  |
| 31 | "The configuration record carries the ceiling (four views),…" | pre-release | flows |  |
| 32 | "The counts multiply out and match the checker's…" | pre-release | flows |  |
| 33 | "TLC 2.19 (the `v1.7.4` tools jar) on Java…" | pre-release | flows |  |
| 34 | "Each run is exhaustive." | pre-release | flows |  |
| 35 | "Trace output TLC writes beside the model (`*_TTrace_*`,…" | pre-release | flows |  |
| 36 | "Configuration \| File \| Invariants \| Result \|…" | pre-release | flagged | Table header row, structure rather than a sentence |
| 37 | "Full field space \| `ConfineCeiling.cfg` \| `P2Inv`, `EffViewExact`,…" | pre-release | flows |  |
| 38 | "Narrowing witness \| `ConfineWitnessNarrow.cfg` \| `NothingNarrows` \| fails,…" | pre-release | flows |  |
| 39 | "Prefix witness \| `ConfineWitnessPrefix.cfg` \| `NoPrefixBind` \| fails,…" | pre-release | flows |  |
| 40 | "The depth of the ceiling search is 2:…" | pre-release | flows |  |
| 41 | "The fingerprint collision estimates TLC printed were 3.7E-8…" | pre-release | flows |  |
| 42 | "`P2Inv` is the security half: the effective view…" | pre-release | flows |  |
| 43 | "`EffViewExact` and `EffBudgetExact` are the fidelity half: the…" | pre-release | flows |  |
| 44 | "To re-run from a bare machine: install a…" | pre-release | flows |  |
| 45 | "`ConfineWitnessNarrow.cfg` checks `NothingNarrows` — the claim that a…" | pre-release | flows |  |
| 46 | "TLC's counterexample has ceiling `summary` and budget cap…" | pre-release | flows |  |
| 47 | "The narrowing rules fire in both directions of…" | pre-release | flows |  |
| 48 | "`ConfineWitnessPrefix.cfg` checks `NoPrefixBind` — the claim that the…" | pre-release | flows |  |
| 49 | "TLC's counterexample has mode `enforce`, a working mechanism,…" | pre-release | flows |  |
| 50 | "That is F1, exhibited rather than asserted." | pre-release | flows |  |
| 51 | "**F1." | pre-release | flows |  |
| 52 | "The interpreter field changes the sandbox's visible set,…" | pre-release | flows |  |
| 53 | "The code's own comment in `sandbox.py` calls this…" | pre-release | flows |  |
| 54 | "Classification: inside the property as section 9.4 states…" | pre-release | flows |  |
| 55 | "P2's statement carries the rule inside clause 3…" | pre-release | flows |  |
| 56 | "The residual exposure a stricter reading would press…" | pre-release | flows |  |
| 57 | "No code was changed in this pass, and…" | pre-release | flows |  |
| 58 | "Disposition (findings disposition pass, 1-Nov-2026): accepted, and carried…" | pre-release | flows |  |
| 59 | "The rule stays as clause 3 states it…" | pre-release | flows |  |
| 60 | "The one part of F1's statement the code…" | pre-release | flows |  |
| 61 | "No other finding came out of the code…" | pre-release | flows |  |
| 62 | "In particular, no way was found for a…" | pre-release | flows |  |
| 63 | "The model starts after the gate." | pre-release | flows |  |
| 64 | "Whether a job executes at all is P1;…" | pre-release | flows |  |
| 65 | "Declared query lists are modelled to length two." | pre-release | flows |  |
| 66 | "The code's rule is positional and uniform —…" | pre-release | flows |  |
| 67 | "The attestation list a result carries under the…" | pre-release | flows |  |
| 68 | "The attested list cannot widen past the attested…" | pre-release | flows |  |
| 69 | "Answers are modelled as the shapes an answer…" | pre-release | flows |  |
| 70 | "What the text contains is the redaction machinery's…" | pre-release | flows |  |
| 71 | "The confinement outcome is an input the runner…" | pre-release | flows |  |
| 72 | "The model checks what is done with the…" | pre-release | flows |  |
| 73 | "The walk's own fidelity is conformance-test territory (stage…" | pre-release | flows |  |
| 74 | "The `enforce`-with-broken-mechanism states are in the space: the…" | pre-release | flows |  |
| 75 | "At startup, a mechanism that cannot engage under…" | pre-release | flows |  |
| 76 | "Whether `enforce` should ever fall back per job…" | pre-release | flows |  |
