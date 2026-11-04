# Findings — docs/infrastructure-documents/proofs/stage5.md

Source: docs/infrastructure-documents/proofs/stage5.md, reviewed at main b65efeed.
Sentence units: 112. Flagged: 6. Categories: pre-release 112, post-release 0.

The conformance stage record: the test-file table, the clause-by-clause driving of P1–P6, the mutation table, findings and limits, and the per-property verdict table. 3 tables contribute their structure rows as the only flags. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Stage 5 is done on the terms `goals.md`…" | pre-release | flows |  |
| 2 | "Every clause of P1 through P6 names at…" | pre-release | flows |  |
| 3 | "Nothing in the runner's behaviour changed in this…" | pre-release | flows |  |
| 4 | "The stage landed in two passes, and this…" | pre-release | flows |  |
| 5 | "The first pass named a test for every…" | pre-release | flows |  |
| 6 | "The second pass added a behavioural family in…" | pre-release | flows |  |
| 7 | "Where the first pass's pins read code at…" | pre-release | flows |  |
| 8 | "| File | Tests | What it drives…" | pre-release | flagged | A table header row — structure, not a sentence |
| 9 | "|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 10 | "| `runner/tests/test_proof_constraints.py` | 67 | The stage 1…" | pre-release | flows |  |
| 11 | "| `runner/tests/test_proof_conformance.py` | 64 | P1's nine clauses…" | pre-release | flows |  |
| 12 | "| `runner/tests/test_proof_conformance_p2.py` | 27 | P2: the result…" | pre-release | flows |  |
| 13 | "| `runner/tests/test_proof_conformance_p3.py` | 27 | P3: each transport…" | pre-release | flows |  |
| 14 | "| `runner/tests/test_proof_conformance_p4.py` | 38 | P4: the key-policy…" | pre-release | flows |  |
| 15 | "| `runner/tests/test_proof_conformance_p5.py` | 12 | P5: the claim,…" | pre-release | flows |  |
| 16 | "| `runner/tests/test_proof_conformance_p6.py` | 13 | P6: Decision 1…" | pre-release | flows |  |
| 17 | "248 proof tests in all." | pre-release | flows |  |
| 18 | "A few P1 refusal steps also have older…" | pre-release | flows |  |
| 19 | "The clause classes in `test_proof_conformance.py` drive each of…" | pre-release | flows |  |
| 20 | "The claim and record clauses are driven at…" | pre-release | flows |  |
| 21 | "`ResultViewCeilingTest` reads the result a real `handle_mail` run…" | pre-release | flows |  |
| 22 | "`RedactionTest`: the built-in patterns apply under the redacted…" | pre-release | flows |  |
| 23 | "`QueryCeilingTest`: grep answers under the full view and…" | pre-release | flows |  |
| 24 | "`ConfinementChainTest` drives the runner's own `_confinement_argv`: off runs…" | pre-release | flows |  |
| 25 | "`SandboxShapeTest` drives the builder: the workdir is the…" | pre-release | flows |  |
| 26 | "`WatchedSetTest` runs the snapshot and verdict functions over…" | pre-release | flows |  |
| 27 | "The runner-computed attestation (clause 8) is named by…" | pre-release | flows |  |
| 28 | "`FileChainTest` runs the whole chain: a watched inbox,…" | pre-release | flows |  |
| 29 | "A valid envelope executes and its result lands…" | pre-release | flows |  |
| 30 | "`FileRefusalTest` is the file pipe's own edge (clause…" | pre-release | flows |  |
| 31 | "`NatsGateTest` and `NatsBrokerTest` (clauses 6 and 9): the…" | pre-release | flows |  |
| 32 | "`DtlsStartupTest`, `DtlsDirectoryLookupTest`, and `DtlsPipeSocketTest` (clause 7): the extension's…" | pre-release | flows |  |
| 33 | "`QueuesClientTest`, `QueuesStartupTest`, and `QueuesWorkerTest` (clause 8, and the…" | pre-release | flows |  |
| 34 | "`EmailGateTest` (clause 4): a job from an unrelated…" | pre-release | flows |  |
| 35 | "`UpgradeKeyAtTheDoorTest` drives the step where the property lives,…" | pre-release | flows |  |
| 36 | "`DefaultDenyTest` (clause 3): an entry-less key runs without…" | pre-release | flows |  |
| 37 | "`PolicyIsTheKeysNotTheNamesTest` (clauses 1 and 4): the fingerprint name…" | pre-release | flows |  |
| 38 | "`DirectoryFirstTest` (clause 2): a compromised key is refused…" | pre-release | flows |  |
| 39 | "`DoorsTest` (clause 9): the same entry binds the…" | pre-release | flows |  |
| 40 | "`RecipesAndInterpretersTest` (clause 6) drives the step itself for…" | pre-release | flows |  |
| 41 | "`ModeGatedConstraintsTest` (clause 11): under one policy, an unlisted…" | pre-release | flows |  |
| 42 | "`RepairedJobRejudgedTest` is clause 10 and closes the conformance…" | pre-release | flows |  |
| 43 | "`MalformedPolicyTest` (clause 12) covers the builder validations the…" | pre-release | flows |  |
| 44 | "`ReplayDoorTest` drives the layers in the order `handle_mail`…" | pre-release | flows |  |
| 45 | "Clause 1 and 2: the same delivery twice…" | pre-release | flows |  |
| 46 | "Clause 3, the record half: with the cache…" | pre-release | flows |  |
| 47 | "Clause 6: a different job under the same…" | pre-release | flows |  |
| 48 | "Clauses 3 and 4, the claim half: a…" | pre-release | flows |  |
| 49 | "Clause 11: a seen set rebuilt from `seen.json`…" | pre-release | flows |  |
| 50 | "Clause 7, priced: with the stash made to…" | pre-release | flows |  |
| 51 | "`RecordStoreTest` drives the store itself: clauses 5 and…" | pre-release | flows |  |
| 52 | "Clause 9, priced: a record past its retention…" | pre-release | flows |  |
| 53 | "`StartupTest` drives the real `main()` over a real…" | pre-release | flows |  |
| 54 | "`ReloadTest` drives the real reload over a real…" | pre-release | flows |  |
| 55 | "One sub-case is deliberately not pinned: a boolean…" | pre-release | flows |  |
| 56 | "That divergence is on record; this family does…" | pre-release | flows |  |
| 57 | "For each property, a deliberate one-line change was…" | pre-release | flows |  |
| 58 | "Twelve shapes were run in ten runs —…" | pre-release | flows |  |
| 59 | "Every run exited 1: at least one test…" | pre-release | flows |  |
| 60 | "A family that stayed green would have been…" | pre-release | flows |  |
| 61 | "The scratch copies were not committed." | pre-release | flows |  |
| 62 | "| # | Property | The one line…" | pre-release | flagged | A table header row — structure, not a sentence |
| 63 | "|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 64 | "| M1 | P1 | `runner/ops/mail.py`: the freshness…" | pre-release | flows |  |
| 65 | "| M2 | P2 | `runner/ops/policy.py`: the view…" | pre-release | flows |  |
| 66 | "| M3 | P3 | `runner/transport_extensions/nats/__main__.py`: the missing-credential…" | pre-release | flows |  |
| 67 | "| M4 | P4 | `runner/wire/verify.py`: the pinning…" | pre-release | flows |  |
| 68 | "| M5 | P5 | `runner/runner.py`: the record's…" | pre-release | flows |  |
| 69 | "| M6 | P6 | `runner/ops/attest.py`: the reload…" | pre-release | flows |  |
| 70 | "| G1 | P1 | `runner/ops/mail.py`: the cleartext…" | pre-release | flows |  |
| 71 | "| G2 | P2 | `runner/ops/policy.py`: the ceiling…" | pre-release | flows |  |
| 72 | "| G4 | P4 | `runner/wire/verify.py`: the kinds…" | pre-release | flows |  |
| 73 | "| G6 | P6 | `runner/guard/defaulted.py`: a boolean…" | pre-release | flows |  |
| 74 | "The first pass's own runs of its six…" | pre-release | flows |  |
| 75 | "**F1." | pre-release | flows |  |
| 76 | "The interpreter-prefix floor is not enforced on the…" | pre-release | flows |  |
| 77 | "That bound is enforced on the `bin` grandparent…" | pre-release | flows |  |
| 78 | "Measured on the real builder: an interpreter resolved…" | pre-release | flows |  |
| 79 | "`SandboxShapeTest::test_a_root_level_interpreter_binds_the_root` exhibits the current behaviour by name so…" | pre-release | flows |  |
| 80 | "Classification: a widening past the bound F1 discloses,…" | pre-release | flows |  |
| 81 | "What closes it is either the same depth…" | pre-release | flows |  |
| 82 | "No production code changed in this stage; the…" | pre-release | flows |  |
| 83 | "Disposition (findings disposition pass, 1-Nov-2026): fixed on main,…" | pre-release | flows |  |
| 84 | "`_install_prefix` now enforces the floor on the parent…" | pre-release | flows |  |
| 85 | "`SandboxShapeTest::test_a_root_level_interpreter_gets_no_prefix_bind` replaces the exhibit test and pins the…" | pre-release | flows |  |
| 86 | "**The P5 observation, now pinned as behaviour.** Stage…" | pre-release | flows |  |
| 87 | "`RecordStoreTest::test_the_record_check_without_the_opinion_module` exhibits exactly that, by name." | pre-release | flows |  |
| 88 | "The module loads unconditionally in the shipped runner,…" | pre-release | flows |  |
| 89 | "**Limits, stated plainly.** P5's clause 10 is driven…" | pre-release | flows |  |
| 90 | "The DTLS drives are loopback, and the queues…" | pre-release | flows |  |
| 91 | "The content-independence challenge in `thinking.md` (every script at…" | pre-release | flows |  |
| 92 | "On the final tree: `test_proof_constraints.py` 67, `test_proof_conformance.py` 64,…" | pre-release | flows |  |
| 93 | "The mutation runs above were made in a…" | pre-release | flows |  |
| 94 | "After both passes landed, the whole stage was…" | pre-release | flows |  |
| 95 | "The verdict per property:" | pre-release | flows |  |
| 96 | "| Property | Clauses | Verdict |" | pre-release | flagged | A table header row — structure, not a sentence |
| 97 | "|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 98 | "| P1 | 9 of 9 | Every…" | pre-release | flows |  |
| 99 | "| P2 | 9 of 9 | Clauses…" | pre-release | flows |  |
| 100 | "| P3 | 9 of 9 | Behavioural…" | pre-release | flows |  |
| 101 | "| P4 | 12 of 12 | At…" | pre-release | flows |  |
| 102 | "| P5 | 11 of 11 | At…" | pre-release | flows |  |
| 103 | "| P6 | 7 of 7 | Clauses…" | pre-release | flows |  |
| 104 | "One recorded exception inside clause 5's territory: the…" | pre-release | flows |  |
| 105 | "Duplicates between the two passes were judged pair…" | pre-release | flows |  |
| 106 | "One test was dropped as an exact duplicate:…" | pre-release | flows |  |
| 107 | "Every other overlap is either strictly stronger in…" | pre-release | flows |  |
| 108 | "That debt is confirmed closed: both tests were…" | pre-release | flows |  |
| 109 | "The mutation claim was verified the strong way." | pre-release | flows |  |
| 110 | "In a fresh scratch copy of the final…" | pre-release | flows |  |
| 111 | "Each run exited 1, caught by exactly the…" | pre-release | flows |  |
| 112 | "The remaining recorded mutations — P3's and P5's…" | pre-release | flows |  |
