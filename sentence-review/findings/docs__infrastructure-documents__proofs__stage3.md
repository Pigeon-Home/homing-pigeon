# Findings — docs/infrastructure-documents/proofs/stage3.md

Source: docs/infrastructure-documents/proofs/stage3.md, reviewed at main d3fe3244.
Sentence units: 137. Flagged: 4. Categories: pre-release 137, post-release 0.

The stage 3 reconciliation: every model step of the gate matched to the code, the gaps G1–G6, the findings F1–F4, and the stage 2 counterexample traces re-run and classified. The step table's rows are fragments by design and flow as table entries; only the table structure itself is flagged. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the reconciliation stage 2 deferred: `Gate.tla`…" | pre-release | flows |  |
| 2 | "Each model step is matched to the code…" | pre-release | flows |  |
| 3 | "Each code branch in the gate that the…" | pre-release | flows |  |
| 4 | "Each place where model and code genuinely differ…" | pre-release | flows |  |
| 5 | "The code read for this reconciliation is the…" | pre-release | flows |  |
| 6 | "The gate is `handle_mail` in `runner/ops/mail.py`; the helpers…" | pre-release | flows |  |
| 7 | "Model steps are the numbered disjuncts of `Next`…" | pre-release | flows |  |
| 8 | "Code locations are `handle_mail` unless another file is…" | pre-release | flows |  |
| 9 | "| Model step | What it checks |…" | pre-release | flagged | A table header row — structure, not a sentence |
| 10 | "|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 11 | "| 0." | pre-release | flows |  |
| 12 | "Panic | `panic` stops the handling before everything…" | pre-release | flows |  |
| 13 | "| 1." | pre-release | flows |  |
| 14 | "Raw size | `rawOver` refuses before signature work…" | pre-release | flows |  |
| 15 | "The code applies the cap when the subject…" | pre-release | flows |  |
| 16 | "| 2." | pre-release | flows |  |
| 17 | "Early dispatch | Anything that is not a…" | pre-release | flows |  |
| 18 | "The four non-job kinds and the bounce are…" | pre-release | flows |  |
| 19 | "The seen-set part is the in-memory set only…" | pre-release | flows |  |
| 20 | "| 3." | pre-release | flows |  |
| 21 | "Verification and decryption | `signed` false, or `innerMismatch`,…" | pre-release | flows |  |
| 22 | "| 4." | pre-release | flows |  |
| 23 | "Cleartext | An unencrypted arrival refuses unless the…" | pre-release | flows |  |
| 24 | "| 5." | pre-release | flows |  |
| 25 | "Audience | `enforce` refuses a mismatch; `audit` records…" | pre-release | flows |  |
| 26 | "| 6." | pre-release | flows |  |
| 27 | "Encodability | `surrogate` refuses | `mail.py` lines 138–142:…" | pre-release | flows |  |
| 28 | "| 7." | pre-release | flows |  |
| 29 | "Script size | `scriptOver` (UTF-8 bytes over C2)…" | pre-release | flows |  |
| 30 | "| 8." | pre-release | flows |  |
| 31 | "Version, type, identity | `versionOk`, `typeOk`, `idOk` all…" | pre-release | flows |  |
| 32 | "The code splits this into two rejects (version/type,…" | pre-release | flows |  |
| 33 | "| 9." | pre-release | flows |  |
| 34 | "Freshness | `fresh` false refuses | `mail.py` lines…" | pre-release | flows |  |
| 35 | "| 10." | pre-release | flows |  |
| 36 | "Key policy | `policyOk` false refuses | `mail.py`…" | pre-release | flows |  |
| 37 | "| 11." | pre-release | flows |  |
| 38 | "Pinned-key constraints | An enforce denial (`constraintDenied`) refuses…" | pre-release | flows |  |
| 39 | "The model's bit is the outcome — an…" | pre-release | flows |  |
| 40 | "| 12." | pre-release | flows |  |
| 41 | "Sensor branch | `sensor` leaves the path with…" | pre-release | flows |  |
| 42 | "`SensorInv` in the model lists the checks through…" | pre-release | flows |  |
| 43 | "| 13." | pre-release | flows |  |
| 44 | "Advisory review | A pass step that changes…" | pre-release | flows |  |
| 45 | "| 14." | pre-release | flows |  |
| 46 | "Dry run | `dryRun` ends the handling with…" | pre-release | flows |  |
| 47 | "| 15." | pre-release | flows |  |
| 48 | "The claim | `claim = "taken"` refuses; `"onRecord"`…" | pre-release | flows |  |
| 49 | "| 16." | pre-release | flows |  |
| 50 | "Cancel, then execute | `cancelled` refuses; otherwise the…" | pre-release | flows |  |
| 51 | "The span between them holds three code behaviours…" | pre-release | flows |  |
| 52 | "`Claim.tla` against the code: the model's one slot,…" | pre-release | flows |  |
| 53 | "In one process, the check-and-add is atomic under…" | pre-release | flows |  |
| 54 | "Across processes, `_disk_owns` takes the claim as a…" | pre-release | flows |  |
| 55 | "Two handlers racing one job id in one…" | pre-release | flows |  |
| 56 | "The cross-process half differs in the loser's outcome,…" | pre-release | flows |  |
| 57 | "Each gap below is a branch in the…" | pre-release | flows |  |
| 58 | "For each, the reason it does or does…" | pre-release | flows |  |
| 59 | "A gap that only ever refuses more, or…" | pre-release | flows |  |
| 60 | "**G1." | pre-release | flows |  |
| 61 | "Verification's own early refusals.** Inside `verify_body_keyed`, before any…" | pre-release | flows |  |
| 62 | "The model folds all of this into `signed`:…" | pre-release | flows |  |
| 63 | "Safe for P1: every one of these branches…" | pre-release | flows |  |
| 64 | "**G2." | pre-release | flows |  |
| 65 | "The judge.** Inside step 16's span (`mail.py` lines…" | pre-release | flows |  |
| 66 | "There is no model bit for it." | pre-release | flows |  |
| 67 | "Safe for P1 in the refusing direction —…" | pre-release | flows |  |
| 68 | "**G3." | pre-release | flows |  |
| 69 | "The version 2 before-execution exchange.** Also inside step…" | pre-release | flows |  |
| 70 | "A failure in it is logged and the…" | pre-release | flows |  |
| 71 | "Not represented in the model." | pre-release | flows |  |
| 72 | "Safe for P1 as the code stands: it…" | pre-release | flows |  |
| 73 | "**G4." | pre-release | flows |  |
| 74 | "The claim and record mechanics.** The stale-claim rule,…" | pre-release | flows |  |
| 75 | "Safe for P1's claim — in the digest-mismatch…" | pre-release | flows |  |
| 76 | "**G5." | pre-release | flows |  |
| 77 | "Everything after `execute_job`.** Result fitting to `max_result_bytes` (C3),…" | pre-release | flows |  |
| 78 | "They shape what is delivered, never whether execution…" | pre-release | flows |  |
| 79 | "**G6." | pre-release | flows |  |
| 80 | "`execute_job`'s internals.** Kind dispatch and confinement inside execution…" | pre-release | flows |  |
| 81 | "The model's claim ends where P1's does: at…" | pre-release | flows |  |
| 82 | "A finding is a place where the two…" | pre-release | flows |  |
| 83 | "None of the four below is a counterexample…" | pre-release | flows |  |
| 84 | "Each is recorded plainly, with its classification, and…" | pre-release | flows |  |
| 85 | "**F1." | pre-release | flows |  |
| 86 | "The encodability check runs twice in the code,…" | pre-release | flows |  |
| 87 | "A cleartext body with a surrogate is therefore…" | pre-release | flows |  |
| 88 | "Classification: model simplification, not a code defect and…" | pre-release | flows |  |
| 89 | "The difference is observable only in which refusal…" | pre-release | flows |  |
| 90 | "When the model next moves, it moves to…" | pre-release | flows |  |
| 91 | "**F2." | pre-release | flows |  |
| 92 | "The code can execute a repaired job; the…" | pre-release | flows |  |
| 93 | "Before it runs, the repaired job goes back…" | pre-release | flows |  |
| 94 | "Every other clause speaks of fields the substitution…" | pre-release | flows |  |
| 95 | "Classification: a model gap with a bounded blast…" | pre-release | flows |  |
| 96 | "It is recorded as the reconciliation's most substantive…" | pre-release | flows |  |
| 97 | "**F3." | pre-release | flows |  |
| 98 | "Two outcomes the model calls finished, the code…" | pre-release | flows |  |
| 99 | "When another process holds a live claim, the…" | pre-release | flows |  |
| 100 | "Classification: outcome-label difference, working as the code intends…" | pre-release | flows |  |
| 101 | "The model's labels are the coarser ones; nothing…" | pre-release | flows |  |
| 102 | "**F4." | pre-release | flows |  |
| 103 | "The audience clause has a configuration precondition the…" | pre-release | flows |  |
| 104 | "The model's `audienceOk` bit presumes a configured `runner_id`,…" | pre-release | flows |  |
| 105 | "Classification: assumption working as stated, in both the…" | pre-release | flows |  |
| 106 | "Stage 2 produced exactly two counterexample traces, both…" | pre-release | flows |  |
| 107 | "Stage 3's done criteria require each to be…" | pre-release | flows |  |
| 108 | "**`GateWitness.cfg` — `NothingExecutes` fails under enforce.** The trace…" | pre-release | flows |  |
| 109 | "Read against the code above, that handling executes…" | pre-release | flows |  |
| 110 | "Classification: assumption working as stated." | pre-release | flows |  |
| 111 | "Not a model defect (the model was built…" | pre-release | flows |  |
| 112 | "**`GateDefaultWitness.cfg` — `AudienceWasRequired` fails with the audience feature…" | pre-release | flows |  |
| 113 | "Read against the code: with the mode `off`,…" | pre-release | flows |  |
| 114 | "This is clause 4 in its default, vacuous…" | pre-release | flows |  |
| 115 | "Classification: assumption working as stated." | pre-release | flows |  |
| 116 | "No other counterexample exists from stage 2: the…" | pre-release | flows |  |
| 117 | "There is therefore no trace left unclassified, and…" | pre-release | flows |  |
| 118 | "The model and its recorded results were treated…" | pre-release | flows |  |
| 119 | "Every configuration named in `stage2.md` was therefore re-run…" | pre-release | flows |  |
| 120 | "The one environment difference is the Java runtime:…" | pre-release | flows |  |
| 121 | "The results are identical to the digit, so…" | pre-release | flows |  |
| 122 | "| Configuration | `stage2.md` records | This re-run…" | pre-release | flagged | A table header row — structure, not a sentence |
| 123 | "|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 124 | "| `GateEnforce.cfg` | holds; 3,095,432 generated, 2,309,000 distinct…" | pre-release | flows |  |
| 125 | "| `GateDefault.cfg` | holds; 3,106,576 generated, 2,320,144 distinct…" | pre-release | flows |  |
| 126 | "| `GateAudit.cfg` | holds; 3,106,576 generated, 2,320,144 distinct…" | pre-release | flows |  |
| 127 | "| `Claim.cfg` | holds; 7 generated, 5 distinct…" | pre-release | flows |  |
| 128 | "| `GateWitness.cfg` | `NothingExecutes` fails, as expected |…" | pre-release | flows |  |
| 129 | "| `GateDefaultWitness.cfg` | `AudienceWasRequired` fails, as expected |…" | pre-release | flows |  |
| 130 | "The remaining numeric claims in `stage2.md` were checked…" | pre-release | flows |  |
| 131 | "The explanations in `stage2.md` for the differences between…" | pre-release | flows |  |
| 132 | "The end state of this section is the…" | pre-release | flows |  |
| 133 | "No claim in `stage2.md` is left flagged as…" | pre-release | flows |  |
| 134 | "Every model step in `Gate.tla` matches a code…" | pre-release | flows |  |
| 135 | "Every code branch in `handle_mail`'s gate is either…" | pre-release | flows |  |
| 136 | "The findings do not include a counterexample to…" | pre-release | flows |  |
| 137 | "The model was not edited in this pass…" | pre-release | flows |  |
