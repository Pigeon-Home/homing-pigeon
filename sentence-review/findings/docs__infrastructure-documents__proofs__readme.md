# Findings — docs/infrastructure-documents/proofs/readme.md

Source: docs/infrastructure-documents/proofs/readme.md, reviewed at main 5f76c4b5.
Sentence units: 95. Flagged: 0. Categories: pre-release 95, post-release 0.

The proof directory's own README: what the work is, its honesty rules (tested and reviewed is not proven; the word provably is never used bare), the assumptions carried through every property, the first target, the character-count measure and its ladder, the layers the work grows in, and the file list. Continuous argumentative prose — each paragraph narrows the claim the previous one made — and the closing file list is introduced by the review request it serves. Nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This directory holds the formal proof work for…" | pre-release | flows |  |
| 2 | "It began on the `testing` branch, cut from…" | pre-release | flows |  |
| 3 | "Nothing in this directory changes how the runner…" | pre-release | flows |  |
| 4 | "The work here models the runner that already…" | pre-release | flows |  |
| 5 | "A reader who arrives cold needs nothing outside…" | pre-release | flows |  |
| 6 | "Each claim in these files names the file…" | pre-release | flows |  |
| 7 | "The goal is a machine-checkable formal model of…" | pre-release | flows |  |
| 8 | "The model is built up little by little." | pre-release | flows |  |
| 9 | "One property at a time is stated, modelled,…" | pre-release | flows |  |
| 10 | "The scope then raises: a wider bound, another…" | pre-release | flows |  |
| 11 | "No single step claims more than it checked." | pre-release | flows |  |
| 12 | "Today the security of Homing Pigeon rests on…" | pre-release | flows |  |
| 13 | "The signature is required on every job." | pre-release | flows |  |
| 14 | "Cleartext is refused by default." | pre-release | flows |  |
| 15 | "Size caps bound a job before and after…" | pre-release | flows |  |
| 16 | "Security modes can bind a job to one…" | pre-release | flows |  |
| 17 | "Those are strong, deliberate choices, and the test…" | pre-release | flows |  |
| 18 | "Neither one is a proof that no path…" | pre-release | flows |  |
| 19 | "This work closes that gap property by property." | pre-release | flows |  |
| 20 | "Until a property has a checked model behind…" | pre-release | flows |  |
| 21 | "When a property does get a checked model,…" | pre-release | flows |  |
| 22 | "The word "provably" is never used here without…" | pre-release | flows |  |
| 23 | "A gate model cannot prove its own cryptography." | pre-release | flows |  |
| 24 | "The model treats these as assumptions, stated once…" | pre-release | flows |  |
| 25 | "HMAC-SHA-384 is unforgeable without the shared secret." | pre-release | flows |  |
| 26 | "An attacker who does not hold a secret…" | pre-release | flows |  |
| 27 | "AES-256-GCM, as constructed in `runner/wire/jobcrypto.py`, keeps an encrypted…" | pre-release | flows |  |
| 28 | "The shared secret itself has the entropy the…" | pre-release | flows |  |
| 29 | "The operating system, the Python runtime, and the…" | pre-release | flows |  |
| 30 | "A job that is executed runs with the…" | pre-release | flows |  |
| 31 | "Proving anything about those assumptions belongs to cryptography…" | pre-release | flows |  |
| 32 | "The model starts where they end: given a…" | pre-release | flows |  |
| 33 | "The first target is the job acceptance gate…" | pre-release | flows |  |
| 34 | "It is the smallest surface that carries the…" | pre-release | flows |  |
| 35 | "If something can execute without passing it, no…" | pre-release | flows |  |
| 36 | "The first property, P1 in `properties.md`, is the…" | pre-release | flows |  |
| 37 | "The size of a script, for this proof…" | pre-release | flows |  |
| 38 | "Line counts are not used: a one-liner can…" | pre-release | flows |  |
| 39 | "Character count is the measure that tracks how…" | pre-release | flows |  |
| 40 | "The proof starts at a tiny bound: scripts…" | pre-release | flows |  |
| 41 | "At that bound a model checker can be…" | pre-release | flows |  |
| 42 | "The bound then raises little by little, stage…" | pre-release | flows |  |
| 43 | "In `properties.md` the gate property is written as…" | pre-release | flows |  |
| 44 | "This bound is the proof's starting scope." | pre-release | flows |  |
| 45 | "It is not a product limit." | pre-release | flows |  |
| 46 | "The production caps in the code — a…" | pre-release | flows |  |
| 47 | "The model counts characters to bound its own…" | pre-release | flows |  |
| 48 | "Both measures are recorded wherever either one is…" | pre-release | flows |  |
| 49 | "The work grows in layers, each one resting…" | pre-release | flows |  |
| 50 | "**Constraint inventory.** Every value the gate depends on…" | pre-release | flows |  |
| 51 | "That inventory is `constraints.md`, and a unit test…" | pre-release | flows |  |
| 52 | "**Property statements.** Each property is stated precisely enough…" | pre-release | flows |  |
| 53 | "That is `properties.md`." | pre-release | flows |  |
| 54 | "**Formal model.** The gate is modelled in TLA+,…" | pre-release | flows |  |
| 55 | "That model is `Gate.tla` (the ordered checks) and…" | pre-release | flows |  |
| 56 | "The checker is TLC." | pre-release | flows |  |
| 57 | "What it found at the first rung is…" | pre-release | flows |  |
| 58 | "The tool choice and the rest of the…" | pre-release | flows |  |
| 59 | "**Checked model.** The checker searches the model for…" | pre-release | flows |  |
| 60 | "A counterexample is a finding, not an embarrassment:…" | pre-release | flows |  |
| 61 | "**Conformance tests.** Each checked property gains a test…" | pre-release | flows |  |
| 62 | "**Raised scope.** The bound raises — longer scripts,…" | pre-release | flows |  |
| 63 | "The roof raises little by little, and each…" | pre-release | flows |  |
| 64 | "This work is written to be reviewed cold,…" | pre-release | flows |  |
| 65 | "No context outside these files is needed, and…" | pre-release | flows |  |
| 66 | "The feedback wanted, in order:" | pre-release | flows |  |
| 67 | "**Are the properties the right ones?** P1 through…" | pre-release | flows |  |
| 68 | "Is the gate the right first property?" | pre-release | flows |  |
| 69 | "Is anything the gate's claim silently depends on…" | pre-release | flows |  |
| 70 | "**Is the check order stated as the code…" | pre-release | flows |  |
| 71 | "A step that is out of order, missing,…" | pre-release | flows |  |
| 72 | "**Are any assumptions missing?** The assumptions the model…" | pre-release | flows |  |
| 73 | "If a claim in these files leans on…" | pre-release | flows |  |
| 74 | "An unstated assumption found in review is far…" | pre-release | flows |  |
| 75 | "**Does any constraint value disagree with the code?**…" | pre-release | flows |  |
| 76 | "A value that does not match the code…" | pre-release | flows |  |
| 77 | "A finding is most useful when it points…" | pre-release | flows |  |
| 78 | "`constraints.md` — the constraint inventory harvested from the…" | pre-release | flows |  |
| 79 | "`properties.md` — the property list." | pre-release | flows |  |
| 80 | "P1 through P6 are stated in full." | pre-release | flows |  |
| 81 | "`goals.md` — the staged plan: this foundation first,…" | pre-release | flows |  |
| 82 | "The stage records — `stage2.md`, `stage3.md`, the `stage4-*.md`,…" | pre-release | flows |  |
| 83 | "The content-independence series is recorded in `stage7.md` to…" | pre-release | flows |  |
| 84 | "`content-series-review.md` — the review of the content-independence series…" | pre-release | flows |  |
| 85 | "`content-rung-5000.md` is the 5,000-character piece of that redo,…" | pre-release | flows |  |
| 86 | "`content-rung-49.md` is the first rung, generated." | pre-release | flows |  |
| 87 | "`content-rung-50000.md`, `content-rung-500000.md`, and `content-rung-cap.md` are the rungs above…" | pre-release | flows |  |
| 88 | "The cap record says the series is complete." | pre-release | flows |  |
| 89 | "`content-sh-macos.md` is the same rungs under bash 3.2.57…" | pre-release | flows |  |
| 90 | "`content-sh-freebsd.md` records FreeBSD 15.0's own `/bin/sh -n` on…" | pre-release | flows |  |
| 91 | "The gate was not asked again." | pre-release | flows |  |
| 92 | "`content-sh-freebsd-design.md` is the split: emulate the guest, use…" | pre-release | flows |  |
| 93 | "`thinking.md` — the reasoning behind the work: why…" | pre-release | flows |  |
| 94 | "`runner/tests/test_proof_constraints.py` — the unit test that pins the…" | pre-release | flows |  |
| 95 | "If a declared default changes, this test fails,…" | pre-release | flows |  |
