# Findings — docs/infrastructure-documents/security/model-and-proof-testing.md

Source: docs/infrastructure-documents/security/model-and-proof-testing.md, reviewed at main cbb52068.
Sentence units: 110. Flagged: 0. Categories: pre-release 110, post-release 0.

Units 104-110 are the reading guide: 1 file per unit, each with its one-line description.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Homing Pigeon is a remote code execution tool…" | pre-release | flows |  |
| 2 | "The security model is everything that stands between…" | pre-release | flows |  |
| 3 | "This page states that model in one account,…" | pre-release | flows |  |
| 4 | "The full records live in `docs/proofs/`; this page…" | pre-release | flows |  |
| 5 | "Every job, on every transport, passes one ordered…" | pre-release | flows |  |
| 6 | "The order is part of the model: a…" | pre-release | flows |  |
| 7 | "The raw message is bounded first: a message…" | pre-release | flows |  |
| 8 | "Locally submitted envelopes face their own constant cap…" | pre-release | flows |  |
| 9 | "A signature must verify: HMAC-SHA-384 over the body,…" | pre-release | flows |  |
| 10 | "A key id that names nothing the runner…" | pre-release | flows |  |
| 11 | "If the body is an encryption envelope, it…" | pre-release | flows |  |
| 12 | "Encryption is on by default." | pre-release | flows |  |
| 13 | "A cleartext job executes only in a process…" | pre-release | flows |  |
| 14 | "Where the audience feature is in `enforce` mode…" | pre-release | flows |  |
| 15 | "In `audit` mode a mismatch is recorded; with…" | pre-release | flows |  |
| 16 | "The script must fit `max_script_bytes` (default 1 MiB,…" | pre-release | flows |  |
| 17 | "The body's version, type, and job id must…" | pre-release | flows |  |
| 18 | "The signing key's policy must allow the job…" | pre-release | flows |  |
| 19 | "The job id must not already be claimed." | pre-release | flows |  |
| 20 | "Only a handling that takes the claim proceeds,…" | pre-release | flows |  |
| 21 | "A result is fitted to `max_result_bytes` before it…" | pre-release | flows |  |
| 22 | "The owner holds the default key." | pre-release | flows |  |
| 23 | "Additional named keys each carry a policy entry…" | pre-release | flows |  |
| 24 | "Under a pinning policy a `script_url` job is…" | pre-release | flows |  |
| 25 | "Where a key directory is configured, its verdict…" | pre-release | flows |  |
| 26 | "The same fence stands at the query, board,…" | pre-release | flows |  |
| 27 | "The upgrade key is the worked example: a…" | pre-release | flows |  |
| 28 | "Every other shape signed with that key is…" | pre-release | flows |  |
| 29 | "The core is transport-blind; it performs no transport-credential…" | pre-release | flows |  |
| 30 | "Where a transport has credentials of its own,…" | pre-release | flows |  |
| 31 | "**Email has no sender gate, and none is…" | pre-release | flows |  |
| 32 | "Anyone who can route a message into the…" | pre-release | flows |  |
| 33 | "Email stands on the signature alone, by design." | pre-release | flows |  |
| 34 | "**File** has no credential of its own; who…" | pre-release | flows |  |
| 35 | "**NATS** refuses to start without broker credentials unless…" | pre-release | flows |  |
| 36 | "**DTLS** checks the shared secret itself as the…" | pre-release | flows |  |
| 37 | "**Queues** checks bearer tokens at the hosted edge,…" | pre-release | flows |  |
| 38 | "A deployment that waives a transport's gate —…" | pre-release | flows |  |
| 39 | "A job that has passed the gate may…" | pre-release | flows |  |
| 40 | "Whether the job runs inside the sandbox is…" | pre-release | flows |  |
| 41 | "No field in the job is read by…" | pre-release | flows |  |
| 42 | "Inside the sandbox, the job's writable set is…" | pre-release | flows |  |
| 43 | "The visible set grows by one bounded rule…" | pre-release | flows |  |
| 44 | "The job names no path to bind." | pre-release | flows |  |
| 45 | "The result view a job receives is the…" | pre-release | flows |  |
| 46 | "The query budget is the smaller of the…" | pre-release | flows |  |
| 47 | "The redaction patterns that scan a result are…" | pre-release | flows |  |
| 48 | "Job members named `security`, `confinement`, `workspace_root`, `protected_paths`, `max_result_view`,…" | pre-release | flows |  |
| 49 | "They are inert text, not requests the code…" | pre-release | flows |  |
| 50 | "Execution is at most once per job, where…" | pre-release | flows |  |
| 51 | "Three layers of disk state carry the guarantee,…" | pre-release | flows |  |
| 52 | "The edges are priced, not hidden." | pre-release | flows |  |
| 53 | "A crash between a run and its result…" | pre-release | flows |  |
| 54 | "A delivered record ages out after `output_retention_days` (default…" | pre-release | flows |  |
| 55 | "Outside those windows, replay is answered, never re-run." | pre-release | flows |  |
| 56 | "The owner's configuration is trusted as a statement…" | pre-release | flows |  |
| 57 | "The split is by what a wrong value…" | pre-release | flows |  |
| 58 | "A present-but-invalid value that changes who can reach…" | pre-release | flows |  |
| 59 | "Every other present-but-invalid value reads as its documented…" | pre-release | flows |  |
| 60 | "Live reload follows the same split." | pre-release | flows |  |
| 61 | "A bad default-class value is replaced by the…" | pre-release | flows |  |
| 62 | "Refuse-class keys are not in the live-reload set:…" | pre-release | flows |  |
| 63 | "The model above is a design account." | pre-release | flows |  |
| 64 | "The proof work — on `main`, recorded in…" | pre-release | flows |  |
| 65 | "The method is fixed." | pre-release | flows |  |
| 66 | "First, every value the model depends on is…" | pre-release | flows |  |
| 67 | "Each property is then stated in plain language…" | pre-release | flows |  |
| 68 | "Witness configurations — cases that must be reachable…" | pre-release | flows |  |
| 69 | "The model is then reconciled against the real…" | pre-release | flows |  |
| 70 | "Six properties are stated and checked:" | pre-release | flows |  |
| 71 | "**P1, the acceptance gate.** Checked at the first…" | pre-release | flows |  |
| 72 | "P1 is a family over the bound, P1(B),…" | pre-release | flows |  |
| 73 | "The claim race — two handlers, one job…" | pre-release | flows |  |
| 74 | "**P2, confinement ceilings.** No job field widens what…" | pre-release | flows |  |
| 75 | "**P3, transport gates.** The composition of each transport's…" | pre-release | flows |  |
| 76 | "**P4, key pinning.** A named key can do…" | pre-release | flows |  |
| 77 | "**P5, replay resistance.** At most one execution per…" | pre-release | flows |  |
| 78 | "**P6, refuse or default.** The Decision 1 split,…" | pre-release | flows |  |
| 79 | "Stage 5, the conformance tests, has landed: a…" | pre-release | flows |  |
| 80 | "The stage closes with a first-hand verification appendix:…" | pre-release | flows |  |
| 81 | "Stage 6 raised the scope: the character ladder…" | pre-release | flows |  |
| 82 | "Stage 7 re-checked the gate at the 5,000-character…" | pre-release | flows |  |
| 83 | "Stages 8, 9, and 10 — 50,000 characters,…" | pre-release | flows |  |
| 84 | "The records are `stage8-50000.md`, `stage9-500000.md`, and `stage10-1048576.md`." | pre-release | flows |  |
| 85 | "Alongside the ladder, the content-independence series asks whether…" | pre-release | flows |  |
| 86 | "What carries the proof is the model argument:…" | pre-release | flows |  |
| 87 | "The series demonstrates it empirically." | pre-release | flows |  |
| 88 | "It was redone in full — both bash…" | pre-release | flows |  |
| 89 | "At the first rung the set is an…" | pre-release | flows |  |
| 90 | "At 5,000, 50,000, and 500,000 characters the sets…" | pre-release | flows |  |
| 91 | "At the production cap, scripts of exactly 1,048,576…" | pre-release | flows |  |
| 92 | "No rung enumerates the full closure of every…" | pre-release | flows |  |
| 93 | "The redo's records are `content-rung-49.md`, `content-rung-5000.md`, `content-rung-50000.md`, `content-rung-500000.md`,…" | pre-release | flows |  |
| 94 | "The proof work is finished." | pre-release | flows |  |
| 95 | "A final consistency pass checked that this page,…" | pre-release | flows |  |
| 96 | "**The cryptography is assumed, not proven.** The model…" | pre-release | flows |  |
| 97 | "The model checks what the runner does with…" | pre-release | flows |  |
| 98 | "**The findings are on the record, not smoothed…" | pre-release | flows |  |
| 99 | "P2 records the interpreter-prefix bind inside the property…" | pre-release | flows |  |
| 100 | "**The findings have each been given a stated…" | pre-release | flows |  |
| 101 | "Accepted as stated, and carried here as a…" | pre-release | flows |  |
| 102 | "**The scope starts small and rises.** Each checked…" | pre-release | flows |  |
| 103 | "No claim here is a claim about the…" | pre-release | flows |  |
| 104 | "`docs/proofs/readme.md` — the goal, the assumptions, and how…" | pre-release | flows |  |
| 105 | "`docs/proofs/goals.md` — the staged plan and what done…" | pre-release | flows |  |
| 106 | "`docs/proofs/properties.md` — the six properties in full, with…" | pre-release | flows |  |
| 107 | "`docs/proofs/constraints.md` — the constraint inventory, every value named…" | pre-release | flows |  |
| 108 | "`docs/proofs/stage2.md`, `stage3.md`, `stage4-p2.md` through `stage4-p6.md`, `stage5.md`, the `stage6-*.md`…" | pre-release | flows |  |
| 109 | "The first content-independence series is recorded in `docs/proofs/stage7.md`…" | pre-release | flows |  |
| 110 | "`docs/proofs/thinking.md` — the reasoning behind the work, the…" | pre-release | flows |  |
