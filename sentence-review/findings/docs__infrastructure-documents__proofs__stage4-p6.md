# Findings — docs/infrastructure-documents/proofs/stage4-p6.md

Source: docs/infrastructure-documents/proofs/stage4-p6.md, reviewed at main cbb52068.
Sentence units: 101. Flagged: 1. Categories: pre-release 99, post-release 2.

Units 51 and 63 are the findings' bold labels; each completes in the sentence that follows.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This is the record of P6's pass through…" | pre-release | flows |  |
| 2 | "P6 is the last of stage 4's five…" | pre-release | flows |  |
| 3 | "The statement is in `properties.md` (P6, seven clauses);…" | pre-release | flows |  |
| 4 | "The code read for this stage is the…" | pre-release | flows |  |
| 5 | "The runner files named below are unchanged from…" | pre-release | flows |  |
| 6 | "A setting the owner wrote, which is present…" | pre-release | flows |  |
| 7 | "If it would change who can reach the…" | pre-release | flows |  |
| 8 | "Everything else reads as its documented default, and…" | pre-release | flows |  |
| 9 | "An absent key is the default too, and…" | pre-release | flows |  |
| 10 | "While the process is running, a bad default-class…" | pre-release | flows |  |
| 11 | "A refuse-class key is not in the live-reload…" | pre-release | flows |  |
| 12 | "It is read again at the next start." | pre-release | flows |  |
| 13 | "**Usable, for a number.** `runner/guard/confval.py`, `is_number` (line 40)…" | pre-release | flows |  |
| 14 | "A boolean is never a number, because `bool`…" | pre-release | flows |  |
| 15 | "A non-finite float is not a number." | pre-release | flows |  |
| 16 | "A value outside `[lo, hi]` is unusable, not…" | pre-release | flows |  |
| 17 | "**Named, for the default class.** `runner/guard/defaulted.py`." | pre-release | flows |  |
| 18 | "`NUMERIC` and `ENUM` are the table. `is_defaulted` (line…" | pre-release | flows |  |
| 19 | "**Stopped, for the refuse class.** `runner/ops/main.py` returns 2." | pre-release | flows |  |
| 20 | "A bad size cap comes from `_validate_size_caps` (`runner/runner.py`…" | pre-release | flows |  |
| 21 | "A present `imap_port` or `smtp_port` goes through `runner/wire/mailbox.py`…" | pre-release | flows |  |
| 22 | "The security block is checked just above, lines…" | pre-release | flows |  |
| 23 | "**Live reload.** `runner/ops/attest.py`, `reload_hot_config` (line 87)." | pre-release | flows |  |
| 24 | "For each key in `HOT_KEYS` (`runner/runner.py` line 5045),…" | pre-release | flows |  |
| 25 | "The rest of `defaulted_keys` is handled the same…" | pre-release | flows |  |
| 26 | "A file that cannot be parsed returns without…" | pre-release | flows |  |
| 27 | "The keys this function reads are `HOT_KEYS`, `LIVE_KEYS`,…" | pre-release | flows |  |
| 28 | "Ports, secrets, key policies, and security modes are…" | pre-release | flows |  |
| 29 | "`Decision.tla` is one decision." | pre-release | flows |  |
| 30 | "An attempt is a class (`refuse` or `default`),…" | pre-release | flows |  |
| 31 | "Twelve attempts, which is the whole space." | pre-release | flows |  |
| 32 | "The outcome says whether the process is running,…" | pre-release | flows |  |
| 33 | "The invariant `P6Inv` is the seven clauses, in…" | pre-release | flows |  |
| 34 | "The process is stopped exactly when the class…" | pre-release | flows |  |
| 35 | "A reload never stops it." | pre-release | flows |  |
| 36 | "An unusable default-class value, at either moment, is…" | pre-release | flows |  |
| 37 | "A refuse-class value at reload, usable or not,…" | pre-release | flows |  |
| 38 | "TLC 2.19 (the `v1.7.4` tools jar) on Java…" | pre-release | flows |  |
| 39 | "The run is exhaustive." | pre-release | flows |  |
| 40 | "Twelve initial states, one per attempt." | pre-release | flows |  |
| 41 | "Configuration ; File ; Invariant ; Result ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 42 | "Every class, presence, and moment ; `Decision.cfg` ;…" | pre-release | flows |  |
| 43 | "A stop exists ; `DecisionWitnessStop.cfg` ; `NothingStops` ;…" | pre-release | flows |  |
| 44 | "A named default exists ; `DecisionWitnessDefault.cfg` ; `DefaultStaysUnusable`…" | pre-release | flows |  |
| 45 | "The depth of the main search is 2:…" | pre-release | flows |  |
| 46 | "The stop witness ends at `running = FALSE`,…" | pre-release | flows |  |
| 47 | "The default witness ends at `running = TRUE`,…" | pre-release | flows |  |
| 48 | "No path was found by which a refuse-class…" | pre-release | flows |  |
| 49 | "The default class names its fallback, and an…" | pre-release | flows |  |
| 50 | "One gap between the decision's sentence and the…" | pre-release | flows |  |
| 51 | "**F1." | pre-release | flows |  |
| 52 | "A bad refuse-class value written while running is…" | pre-release | flows |  |
| 53 | "It also never logs it." | pre-release | flows |  |
| 54 | "The safety half holds: the running binding does…" | pre-release | flows |  |
| 55 | "The log half does not happen in this…" | pre-release | flows |  |
| 56 | "Classification: not a counterexample to P6 as stated,…" | pre-release | flows |  |
| 57 | "It is recorded because the decision's own sentence…" | pre-release | flows |  |
| 58 | "No code was changed in this pass." | pre-release | flows |  |
| 59 | "Disposition (findings disposition pass, 1-Nov-2026): fixed on main." | pre-release | flows |  |
| 60 | "The reload path now reads the refuse-class values…" | pre-release | flows |  |
| 61 | "Decision 1 rule 4's log half now happens." | pre-release | flows |  |
| 62 | "Verified first-hand in the disposition pass, with pins…" | pre-release | flows |  |
| 63 | "**F2." | pre-release | flows |  |
| 64 | "A boolean written live for a hot key…" | pre-release | flows |  |
| 65 | "The reload path for `HOT_KEYS` is `_valid_hot` (`runner/runner.py`…" | pre-release | flows |  |
| 66 | "At startup the same value is unusable under…" | pre-release | flows |  |
| 67 | "So the bool rule C26 states for the…" | pre-release | flows |  |
| 68 | "Classification: a divergence between the code and C26…" | pre-release | flows |  |
| 69 | "The model's one "unusable" bit cannot express it,…" | pre-release | flows |  |
| 70 | "The DecisionPins reload test uses a string, so…" | pre-release | flows |  |
| 71 | "No code was changed in this pass; whether…" | post-release | flows |  |
| 72 | "Disposition (findings disposition pass, 1-Nov-2026): fixed on main…" | pre-release | flows |  |
| 73 | "Verified first-hand in the disposition pass, with pins…" | pre-release | flows |  |
| 74 | "The model has one "unusable" bit." | pre-release | flows |  |
| 75 | "Each reader has its own rule for what…" | pre-release | flows |  |
| 76 | "Mailbox `_port` rejects a boolean and a non-number,…" | pre-release | flows |  |
| 77 | "The startup check is whichever reader `main` calls…" | pre-release | flows |  |
| 78 | "The model checks the class, not each reader's…" | pre-release | flows |  |
| 79 | "Job-supplied numbers are not this property." | pre-release | flows |  |
| 80 | "A query's `max_matches` comes from an untrusted sender,…" | pre-release | flows |  |
| 81 | "That is the same `confval` reader and a…" | pre-release | flows |  |
| 82 | "The startup checks that are not a single…" | pre-release | flows |  |
| 83 | "They are refuse-class in the same exit path." | pre-release | flows |  |
| 84 | "The model does not enumerate them; the pins…" | pre-release | flows |  |
| 85 | "A usable refuse-class change written while running is…" | pre-release | flows |  |
| 86 | "Clause 6 says the whole class is outside…" | pre-release | flows |  |
| 87 | "A good new port waits for the next…" | pre-release | flows |  |
| 88 | "Whether the missing log line in F1 should…" | post-release | flows |  |
| 89 | "This stage does not make it." | pre-release | flows |  |
| 90 | "This stage was re-checked first-hand after it landed,…" | pre-release | flows |  |
| 91 | "**The check was re-run.** TLC 2.19 (the `v1.7.4`…" | pre-release | flows |  |
| 92 | "**The code was re-read.** Every site the record…" | pre-release | flows |  |
| 93 | "F1 is confirmed from the code: `reload_hot_config` reads…" | pre-release | flows |  |
| 94 | "The Decision 1 sentence it falls short of…" | pre-release | flows |  |
| 95 | "**One model correction.** As first landed, the model's…" | pre-release | flows |  |
| 96 | "The outcome now puts the whole refuse class…" | pre-release | flows |  |
| 97 | "Re-checked after the correction: the same three results,…" | pre-release | flows |  |
| 98 | "**One new finding.** F2 above, found by running…" | pre-release | flows |  |
| 99 | "**Clause 7 is outside the model's space.** The…" | pre-release | flows |  |
| 100 | "Clause 7 rests on the code read: `reload_hot_config`…" | pre-release | flows |  |
| 101 | "**The pins.** `runner/tests/test_proof_constraints.py` runs 67 tests, all passing,…" | pre-release | flows |  |
