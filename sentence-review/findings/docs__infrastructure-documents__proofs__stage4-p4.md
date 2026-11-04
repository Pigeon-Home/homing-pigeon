# Findings — docs/infrastructure-documents/proofs/stage4-p4.md

Source: docs/infrastructure-documents/proofs/stage4-p4.md, reviewed at main b65efeed.
Sentence units: 93. Flagged: 2. Categories: pre-release 93, post-release 0.

P4's pass through stage 4: the key-policy step walked clause by clause against the code, the model and its runs, the 2 witness counterexamples explained, and observation F1 with its disposition. Bold lead-ins carry their paragraphs throughout. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the record of P4's pass through…" | pre-release | flows |  |
| 2 | "P4 is the third of stage 4's five…" | pre-release | flows |  |
| 3 | "The statement is in `properties.md` (P4, twelve clauses);…" | pre-release | flows |  |
| 4 | "The code read for this stage is the…" | pre-release | flows |  |
| 5 | "A key with a policy entry can do…" | pre-release | flows |  |
| 6 | "The fences — kinds, recipes, interpreters, timeout, and…" | pre-release | flows |  |
| 7 | "The upgrade key is the arrangement that gives…" | pre-release | flows |  |
| 8 | "**Construction.** `build_key_policies` (`runner/wire/verify.py`, line 485) builds the policy…" | pre-release | flows |  |
| 9 | "The builder runs at startup (`runner/ops/main.py`, line 140,…" | pre-release | flows |  |
| 10 | "Observation F1 below records the one silence in…" | pre-release | flows |  |
| 11 | "**The step, and its order.** `check_key_policy` (`runner/wire/verify.py`, line…" | pre-release | flows |  |
| 12 | "**The key directory first.** Lines 904 to 910…" | pre-release | flows |  |
| 13 | "**The entry.** `policy_for` (line 380) finds the key's…" | pre-release | flows |  |
| 14 | "No entry: the step returns approval, unless `key_policies_default_deny`…" | pre-release | flows |  |
| 15 | "**Kinds** (lines 924 to 929): where `allowed_kinds` is…" | pre-release | flows |  |
| 16 | "**Recipes** (lines 930 to 936): for `recipe` and…" | pre-release | flows |  |
| 17 | "**Interpreters** (lines 938 to 944): the effective interpreter…" | pre-release | flows |  |
| 18 | "Recipe and change jobs are skipped: their interpreter…" | pre-release | flows |  |
| 19 | "**Timeout** (lines 945 to 962): the effective timeout…" | pre-release | flows |  |
| 20 | "**Script pinning** (lines 963 to 982): where `allowed_script_sha384`…" | pre-release | flows |  |
| 21 | "The branch does not run for other kinds." | pre-release | flows |  |
| 22 | "Nothing in the step is mode-gated: these fences…" | pre-release | flows |  |
| 23 | "What is mode-gated sits behind the step (the…" | pre-release | flows |  |
| 24 | "**The job's door, and the doors around it.**…" | pre-release | flows |  |
| 25 | "It runs again on the Oracle-repaired job (line…" | pre-release | flows |  |
| 26 | "The local-signals path runs it too (`runner/runner.py`, line…" | pre-release | flows |  |
| 27 | "The other doors apply the same entry through…" | pre-release | flows |  |
| 28 | "The DTLS extension's PSK lookup applies the directory…" | pre-release | flows |  |
| 29 | "**The recorded negative case, traced.** The live test…" | pre-release | flows |  |
| 30 | "Its path is the one above: the signature…" | pre-release | flows |  |
| 31 | "No other step in the gate could have…" | pre-release | flows |  |
| 32 | "**The mode-gated surround.** Behind the step, `check_policy_constraints` (`runner/wire/verify.py`,…" | pre-release | flows |  |
| 33 | "Clause 11 of the statement carries this in…" | pre-release | flows |  |
| 34 | "The fences the model checks are the unconditional…" | pre-release | flows |  |
| 35 | "`KeyPolicy.tla` is a single-decision model, in the shape…" | pre-release | flows |  |
| 36 | "The attempt record carries the key (the owner's,…" | pre-release | flows |  |
| 37 | "The deployment record carries the policy as the…" | pre-release | flows |  |
| 38 | "The upgrade arrangement is one point of that…" | pre-release | flows |  |
| 39 | "The counts multiply out and match the checker's…" | pre-release | flows |  |
| 40 | "TLC 2.19 (the `v1.7.4` tools jar) on Java…" | pre-release | flows |  |
| 41 | "Each run is exhaustive." | pre-release | flows |  |
| 42 | "Trace output TLC writes beside the model (`*_TTrace_*`,…" | pre-release | flows |  |
| 43 | "| Configuration | File | Invariants | Result…" | pre-release | flagged | A table header row — structure, not a sentence |
| 44 | "|---|---|---|---|---:|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 45 | "| Full policy space | `KeyPolicy.cfg` | `P4Inv`,…" | pre-release | flows |  |
| 46 | "| Pinned-shape witness | `KeyWitnessPinned.cfg` | `PinnedNeverAccepted` |…" | pre-release | flows |  |
| 47 | "| Owner-key witness | `KeyWitnessDefault.cfg` | `DefaultNeverRuns` |…" | pre-release | flows |  |
| 48 | "The depth of the policy search is 2:…" | pre-release | flows |  |
| 49 | "The fingerprint collision estimate TLC printed for the…" | pre-release | flows |  |
| 50 | "The witness runs stop at their counterexamples, so…" | pre-release | flows |  |
| 51 | "`P4Inv` is the security claim over the whole…" | pre-release | flows |  |
| 52 | "`PinBinds` is the pinning core isolated: under a…" | pre-release | flows |  |
| 53 | "`PolicyExact` is the fidelity half: the verdict is…" | pre-release | flows |  |
| 54 | "To re-run from a bare machine: install a…" | pre-release | flows |  |
| 55 | "`KeyWitnessPinned.cfg` checks `PinnedNeverAccepted` — the claim that the…" | pre-release | flows |  |
| 56 | "TLC's counterexample is the upgrade key under its…" | pre-release | flows |  |
| 57 | "The fence has a gate, and the gate…" | pre-release | flows |  |
| 58 | "`KeyWitnessDefault.cfg` checks `DefaultNeverRuns` — the claim that the…" | pre-release | flows |  |
| 59 | "TLC's counterexample is the default key running an…" | pre-release | flows |  |
| 60 | "One key's fence fences that key; the owner's…" | pre-release | flows |  |
| 61 | "No path was found by which a job…" | pre-release | flows |  |
| 62 | "The behaviour pins in `runner/tests/test_proof_constraints.py` (stage 4's additions)…" | pre-release | flows |  |
| 63 | "One construction-side observation is recorded, in the open:" | pre-release | flows |  |
| 64 | "**F1." | pre-release | flows |  |
| 65 | "The policy builder carries only the fields it…" | pre-release | flows |  |
| 66 | "The step then enforces the built policy exactly,…" | pre-release | flows |  |
| 67 | "Classification: not a counterexample to P4 as stated,…" | pre-release | flows |  |
| 68 | "The startup warning the runner does have covers…" | pre-release | flows |  |
| 69 | "No code was changed in this pass." | pre-release | flows |  |
| 70 | "Disposition (findings disposition pass, 1-Nov-2026): fixed on main." | pre-release | flows |  |
| 71 | "The builder now names every field it does…" | pre-release | flows |  |
| 72 | "The unknown field is still not in the…" | pre-release | flows |  |
| 73 | "Verified first-hand in the disposition pass (the builder's…" | pre-release | flows |  |
| 74 | "Acceptance in this model is the policy step's…" | pre-release | flows |  |
| 75 | "Whether the job then executes is P1: the…" | pre-release | flows |  |
| 76 | "The properties compose by position, as P3 composes…" | pre-release | flows |  |
| 77 | "The env, file, and argument surround is mode-gated…" | pre-release | flows |  |
| 78 | "Under `audit`, a pinned script carrying a subverting…" | pre-release | flows |  |
| 79 | "The upgrade arrangement's files fence therefore binds exactly…" | pre-release | flows |  |
| 80 | "The digest fence, which is what keeps the…" | pre-release | flows |  |
| 81 | "A pinning entry without `allowed_kinds` fences scripts and…" | pre-release | flows |  |
| 82 | "The sharp claim for the upgrade key rests…" | pre-release | flows |  |
| 83 | "The owner's own entry — a policy written…" | pre-release | flows |  |
| 84 | "It is not in the model's space: the…" | pre-release | flows |  |
| 85 | "A deployment that fences its owner key is…" | pre-release | flows |  |
| 86 | "The key directory's verdict is a constant across…" | pre-release | flows |  |
| 87 | "A model of the directory would vary the…" | pre-release | flows |  |
| 88 | "Script identity is pinned-or-not." | pre-release | flows |  |
| 89 | "The model does not evaluate SHA-384; that a…" | pre-release | flows |  |
| 90 | "The effective interpreter and the effective timeout are…" | pre-release | flows |  |
| 91 | "How they are computed — the job's own…" | pre-release | flows |  |
| 92 | "Cancellation is not a shape in the model." | pre-release | flows |  |
| 93 | "A cancel executes nothing; its door is exempt…" | pre-release | flows |  |
