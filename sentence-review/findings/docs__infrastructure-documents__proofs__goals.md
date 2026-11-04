# Findings — docs/infrastructure-documents/proofs/goals.md

Source: docs/infrastructure-documents/proofs/goals.md, reviewed at main cbb52068.
Sentence units: 247. Flagged: 0. Categories: pre-release 243, post-release 4.

Each stage section pairs its Contents and Done-means definitions with the landing record that follows them; the definitions are recorded as part of the stage's account.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This file is the plan for the proof…" | pre-release | flows |  |
| 2 | "It is written to be read cold and…" | pre-release | flows |  |
| 3 | "The work lives on `main`." | pre-release | flows |  |
| 4 | "It began on a separate `testing` branch; that…" | pre-release | flows |  |
| 5 | "Nothing here changes the runner's behaviour; releases continue…" | pre-release | flows |  |
| 6 | "A machine-checkable formal model of Homing Pigeon's security…" | pre-release | flows |  |
| 7 | "The gate comes first because it is the…" | pre-release | flows |  |
| 8 | "A model of any later property built before…" | pre-release | flows |  |
| 9 | "The order inside each property is fixed: state…" | pre-release | flows |  |
| 10 | "A property that is modelled before it is…" | pre-release | flows |  |
| 11 | "A model that is never tied back to…" | pre-release | flows |  |
| 12 | "These are settled for this work." | pre-release | flows |  |
| 13 | "A later stage may revisit one, in the…" | pre-release | flows |  |
| 14 | "**Starting point: the acceptance gate, property P1.** The…" | pre-release | flows |  |
| 15 | "**Constraints come from the code.** Every value the…" | pre-release | flows |  |
| 16 | "The model never invents a tidier value." | pre-release | flows |  |
| 17 | "Where the code and an earlier account differed…" | pre-release | flows |  |
| 18 | "**Script size is a character count, and the…" | pre-release | flows |  |
| 19 | "The production byte caps are untouched; the character…" | pre-release | flows |  |
| 20 | "Raising it is a stage, not an edit." | pre-release | flows |  |
| 21 | "P1 is therefore stated as a family over…" | pre-release | flows |  |
| 22 | "For scale: a typical script a cloud SI…" | pre-release | flows |  |
| 23 | "**Cryptography is an assumption, not a target.** The…" | pre-release | flows |  |
| 24 | "This work checks what the runner does with…" | pre-release | flows |  |
| 25 | "**The Oracle is out of the model's trusted…" | pre-release | flows |  |
| 26 | "Modelling it as a gate would prove a…" | pre-release | flows |  |
| 27 | "**Plain statements before formal ones.** Each property is…" | pre-release | flows |  |
| 28 | "The formal statement must say the same thing…" | pre-release | flows |  |
| 29 | "**Contents.** This directory: `readme.md` (goal, honest scope, assumptions,…" | pre-release | flows |  |
| 30 | "**Done means:** the four files are on the…" | pre-release | flows |  |
| 31 | "**Contents.** A model of `handle_mail`'s gate, following the…" | pre-release | flows |  |
| 32 | "Five candidate tools were weighed for this stage:" | pre-release | flows |  |
| 33 | "**TLA+ (with the TLC model checker, and Apalache…" | pre-release | flows |  |
| 34 | "The gate is exactly that shape — an…" | pre-release | flows |  |
| 35 | "TLC exhaustively explores a finite instance and produces…" | pre-release | flows |  |
| 36 | "**Lean 4.** A full proof assistant: properties are…" | pre-release | flows |  |
| 37 | "The cost is that everything, including the state…" | pre-release | flows |  |
| 38 | "**Coq (Rocq).** The same proof-assistant class as Lean,…" | pre-release | flows |  |
| 39 | "The same cost applies, and the extraction story…" | pre-release | flows |  |
| 40 | "**Isabelle/HOL.** Again a proof assistant, strong on structured…" | pre-release | flows |  |
| 41 | "Same class, same trade." | pre-release | flows |  |
| 42 | "**Alloy.** A relational finder: excellent for "is there…" | pre-release | flows |  |
| 43 | "Its bounds are structural rather than temporal, which…" | pre-release | flows |  |
| 44 | "**The pick is TLA+.** The gate's property is…" | pre-release | flows |  |
| 45 | "That is the class of claim TLA+ was…" | pre-release | flows |  |
| 46 | "A counterexample from TLC is a step-by-step trace…" | pre-release | flows |  |
| 47 | "The proof assistants are not rejected; they are…" | post-release | flows |  |
| 48 | "If a later stage needs a claim for…" | post-release | flows |  |
| 49 | "**Done means:** the model exists on this branch;…" | pre-release | flows |  |
| 50 | "This stage has landed." | pre-release | flows |  |
| 51 | "The model is `Gate.tla` for the ordered checks…" | pre-release | flows |  |
| 52 | "The configurations, the state counts, and the two…" | pre-release | flows |  |
| 53 | "What has not landed, and is stage 3,…" | pre-release | flows |  |
| 54 | "**Contents.** A step-by-step reconciliation: each model step against…" | pre-release | flows |  |
| 55 | "Branches the model abstracts away are listed, with…" | pre-release | flows |  |
| 56 | "Any divergence found is resolved in one direction…" | pre-release | flows |  |
| 57 | "The statement in `properties.md` does not move to…" | pre-release | flows |  |
| 58 | "**Done means:** the reconciliation table is on this…" | pre-release | flows |  |
| 59 | "This stage has landed." | pre-release | flows |  |
| 60 | "The reconciliation is `stage3.md`: every step of `Gate.tla`…" | pre-release | flows |  |
| 61 | "Both stage 2 witness traces are classified in…" | pre-release | flows |  |
| 62 | "The model was not edited and no runner…" | pre-release | flows |  |
| 63 | "**Contents.** P2 to P6, one at a time,…" | pre-release | flows |  |
| 64 | "The order is the order in `properties.md`: confinement…" | pre-release | flows |  |
| 65 | "The order runs from the gate outward —…" | pre-release | flows |  |
| 66 | "**Done means, per property:** the full statement, the…" | pre-release | flows |  |
| 67 | "A property that fails its check is not…" | pre-release | flows |  |
| 68 | "Progress: P2 has landed." | pre-release | flows |  |
| 69 | "The full statement is in `properties.md`; the constraints…" | pre-release | flows |  |
| 70 | "P3 has landed." | pre-release | flows |  |
| 71 | "The full statement is in `properties.md` — nine…" | pre-release | flows |  |
| 72 | "The constraints it needed are C19 and C20…" | pre-release | flows |  |
| 73 | "The model is `TransGate.tla`, a single-decision composition model…" | pre-release | flows |  |
| 74 | "No bypass was found: no transport in the…" | pre-release | flows |  |
| 75 | "P4 to P6 remain, in the order above." | pre-release | flows |  |
| 76 | "P4 has landed." | pre-release | flows |  |
| 77 | "The full statement is in `properties.md` — twelve…" | pre-release | flows |  |
| 78 | "The constraints it needed are C21 (the key…" | pre-release | flows |  |
| 79 | "The model is `KeyPolicy.tla`, a single-decision model of…" | pre-release | flows |  |
| 80 | "No execution outside a built policy was found." | pre-release | flows |  |
| 81 | "One construction-side observation is recorded there: the policy…" | pre-release | flows |  |
| 82 | "P5 has landed." | pre-release | flows |  |
| 83 | "The full statement is in `properties.md` — eleven…" | pre-release | flows |  |
| 84 | "The statement is per job — id plus…" | pre-release | flows |  |
| 85 | "The constraints it needed are C23 (the cache's…" | pre-release | flows |  |
| 86 | "The model is `Replay.tla` — two handlings, both…" | pre-release | flows |  |
| 87 | "No replay path to a second execution was…" | pre-release | flows |  |
| 88 | "P6 has landed." | pre-release | flows |  |
| 89 | "The full statement is in `properties.md` — seven…" | pre-release | flows |  |
| 90 | "The constraints it needed are C26 and C27…" | pre-release | flows |  |
| 91 | "The model is `Decision.tla`, one decision over the…" | pre-release | flows |  |
| 92 | "No refuse-class value that is present and unusable…" | pre-release | flows |  |
| 93 | "The one gap recorded there is that Decision…" | pre-release | flows |  |
| 94 | "Stage 4's five properties are checked." | pre-release | flows |  |
| 95 | "Stage 5 has landed; the record is `stage5.md`." | pre-release | flows |  |
| 96 | "**Contents.** For each checked property, a test family…" | pre-release | flows |  |
| 97 | "The pinning test from stage 1 is the…" | pre-release | flows |  |
| 98 | "Model traces that produced counterexamples during stages 2…" | pre-release | flows |  |
| 99 | "**Done means:** every clause of every checked property…" | pre-release | flows |  |
| 100 | "This stage has landed. `stage5.md` names a test…" | pre-release | flows |  |
| 101 | "The new ones, in `runner/tests/test_proof_conformance.py`, drive `handle_mail`: the…" | pre-release | flows |  |
| 102 | "The pins from stage 1 and stage 4…" | pre-release | flows |  |
| 103 | "A one-line scratch-copy change was caught for each…" | pre-release | flows |  |
| 104 | "The limits are in `stage5.md`: the file, DTLS,…" | pre-release | flows |  |
| 105 | "**Contents.** The bounds raise, one at a time,…" | pre-release | flows |  |
| 106 | "The script character bound — the raising ladder…" | pre-release | flows |  |
| 107 | "Each rung is re-proven before the next is…" | pre-release | flows |  |
| 108 | "The rungs are chosen for proof convenience: each…" | pre-release | flows |  |
| 109 | "They are not derived from the code, and…" | pre-release | flows |  |
| 110 | "One further step remains available after the cap…" | post-release | flows |  |
| 111 | "More keys: from two to a small map…" | pre-release | flows |  |
| 112 | "More surfaces: queries, board mail, version 2 mail,…" | pre-release | flows |  |
| 113 | "More transports: the file and DTLS paths beside…" | pre-release | flows |  |
| 114 | "**Done means, per raise:** the raised model is…" | pre-release | flows |  |
| 115 | "A raise that finds a counterexample stops the…" | pre-release | flows |  |
| 116 | "Progress: the four raises have landed." | pre-release | flows |  |
| 117 | "The character ladder is closed at the production…" | pre-release | flows |  |
| 118 | "P1(500) is `stage6-rung500.md`." | pre-release | flows |  |
| 119 | "The rungs at 5,000, 50,000, and 500,000 characters…" | pre-release | flows |  |
| 120 | "The counts match the first rung." | pre-release | flows |  |
| 121 | "The unbounded-length step was not taken." | pre-release | flows |  |
| 122 | "The cap already covers every script the runner…" | pre-release | flows |  |
| 123 | "More keys: `KeysCompose.tla`, three keys, one of them…" | pre-release | flows |  |
| 124 | "The record is `stage6-keys.md`." | pre-release | flows |  |
| 125 | "A script runs only when the rest of…" | pre-release | flows |  |
| 126 | "The other doors: `Surfaces.tla`." | pre-release | flows |  |
| 127 | "Cancel, query, board, version 2, and the local…" | pre-release | flows |  |
| 128 | "The record is `stage6-surfaces.md`." | pre-release | flows |  |
| 129 | "File and DTLS beside the mail path: `TransGate.tla`…" | pre-release | flows |  |
| 130 | "It was re-run." | pre-release | flows |  |
| 131 | "The record is `stage6-transports.md`." | pre-release | flows |  |
| 132 | "The limits from P3 stand." | pre-release | flows |  |
| 133 | "The conformance family still passes: 85 tests." | pre-release | flows |  |
| 134 | "No runner behaviour changed." | pre-release | flows |  |
| 135 | "The unbounded-length step remains available and is recorded…" | pre-release | flows |  |
| 136 | "**Contents.** The job acceptance gate property family P1(B)…" | pre-release | flows |  |
| 137 | "The stage names now follow the ladder one…" | pre-release | flows |  |
| 138 | "Stage 6's section above keeps its own record,…" | pre-release | flows |  |
| 139 | "**The claim.** The same nine gate clauses of…" | pre-release | flows |  |
| 140 | "The bound is a character count, as at…" | pre-release | flows |  |
| 141 | "The production caps are unchanged; the code's script…" | pre-release | flows |  |
| 142 | "**Done means:** the gate model is checked at…" | pre-release | flows |  |
| 143 | "This stage has landed." | pre-release | flows |  |
| 144 | "The check was run at the 5,000 bound…" | pre-release | flows |  |
| 145 | "The counts match the earlier rungs exactly, as…" | pre-release | flows |  |
| 146 | "The record is `stage7-5000.md`." | pre-release | flows |  |
| 147 | "The conformance family still passes: 131 tests across…" | pre-release | flows |  |
| 148 | "No runner behaviour changed." | pre-release | flows |  |
| 149 | "**Contents.** The job acceptance gate property family P1(B)…" | pre-release | flows |  |
| 150 | "Fifty thousand characters is a very large bound…" | pre-release | flows |  |
| 151 | "**The claim.** The same nine gate clauses of…" | pre-release | flows |  |
| 152 | "The bound is a character count, as at…" | pre-release | flows |  |
| 153 | "**Done means:** the gate model is checked at…" | pre-release | flows |  |
| 154 | "This stage has landed." | pre-release | flows |  |
| 155 | "The check was run at the 50,000 bound…" | pre-release | flows |  |
| 156 | "`P1Inv` holds under all three audience modes, the…" | pre-release | flows |  |
| 157 | "The counts match the earlier rungs exactly." | pre-release | flows |  |
| 158 | "The record is `stage8-50000.md`." | pre-release | flows |  |
| 159 | "The conformance family still passes: 253 tests across…" | pre-release | flows |  |
| 160 | "No runner behaviour changed, and no model file…" | pre-release | flows |  |
| 161 | "**Contents.** The job acceptance gate property family P1(B)…" | pre-release | flows |  |
| 162 | "A script of half a million characters is…" | pre-release | flows |  |
| 163 | "**The claim.** The same nine gate clauses of…" | pre-release | flows |  |
| 164 | "The bound is a character count, as at…" | pre-release | flows |  |
| 165 | "**Done means:** the gate model is checked at…" | pre-release | flows |  |
| 166 | "This stage has landed." | pre-release | flows |  |
| 167 | "The check was run at the 500,000 bound…" | pre-release | flows |  |
| 168 | "`P1Inv` holds under all three audience modes, the…" | pre-release | flows |  |
| 169 | "The counts match the earlier rungs exactly." | pre-release | flows |  |
| 170 | "The record is `stage9-500000.md`." | pre-release | flows |  |
| 171 | "The conformance family still passes, the same 253…" | pre-release | flows |  |
| 172 | "No runner behaviour changed, and no model file…" | pre-release | flows |  |
| 173 | "**Contents.** The last rung of the ladder: P1(B)…" | pre-release | flows |  |
| 174 | "At this bound the family's claim covers every…" | pre-release | flows |  |
| 175 | "**The claim.** The same nine gate clauses of…" | pre-release | flows |  |
| 176 | "The production caps are unchanged; this stage's bound…" | pre-release | flows |  |
| 177 | "**Done means:** the gate model is checked at…" | pre-release | flows |  |
| 178 | "This stage has landed." | pre-release | flows |  |
| 179 | "The check was run at the cap bound…" | pre-release | flows |  |
| 180 | "`P1Inv` holds under all three audience modes, the…" | pre-release | flows |  |
| 181 | "The counts match stage 6's cap re-run exactly." | pre-release | flows |  |
| 182 | "The record is `stage10-1048576.md`, which is the model." | pre-release | flows |  |
| 183 | "The content-independence record of the same number remains…" | pre-release | flows |  |
| 184 | "The conformance family still passes, the same 253…" | pre-release | flows |  |
| 185 | "No runner behaviour changed, and no model file…" | pre-release | flows |  |
| 186 | "A note on the headings of the four…" | pre-release | flows |  |
| 187 | "The checks they record landed numbered as stages…" | pre-release | flows |  |
| 188 | "In this plan the stage numbers belong to…" | pre-release | flows |  |
| 189 | "Their contents are unchanged." | pre-release | flows |  |
| 190 | "One state is shared by all four and…" | pre-release | flows |  |
| 191 | "Its verdicts stand as appendices to the four…" | pre-release | flows |  |
| 192 | "The series has since been redone in full…" | pre-release | flows |  |
| 193 | "**Contents.** The challenge `thinking.md` records and does not…" | pre-release | flows |  |
| 194 | "At scripts of at most 49 characters, list…" | pre-release | flows |  |
| 195 | "The gate's decision must be the same for…" | pre-release | flows |  |
| 196 | "A cap refuses by length, and the refusal…" | pre-release | flows |  |
| 197 | "**Done means:** the inventory is in the test,…" | pre-release | flows |  |
| 198 | "This check has landed." | pre-release | flows |  |
| 199 | "The inventory is twenty-two scripts. `runner/tests/test_proof_content.py` is the…" | pre-release | flows |  |
| 200 | "PowerShell is not on the machine that ran…" | pre-release | flows |  |
| 201 | "The scripts are a sample of each construct,…" | pre-release | flows |  |
| 202 | "**Contents.** The same check as the first rung,…" | pre-release | flows |  |
| 203 | "The scripts are long enough that the inventory…" | pre-release | flows |  |
| 204 | "It is three texts of exactly 50,000 characters…" | pre-release | flows |  |
| 205 | "The gate admits them." | pre-release | flows |  |
| 206 | "A short cap refuses the three by the…" | pre-release | flows |  |
| 207 | "**Done means:** the lengths are exact, `bash -n`…" | pre-release | flows |  |
| 208 | "This check has landed." | pre-release | flows |  |
| 209 | "The harness is `runner/tests/test_proof_content_50k.py`." | pre-release | flows |  |
| 210 | "The record is `stage8.md`." | pre-release | flows |  |
| 211 | "A script of 50,001 characters is still admitted,…" | pre-release | flows |  |
| 212 | "**Contents.** The same check as the 50,000-character content…" | pre-release | flows |  |
| 213 | "Three texts of exactly 500,000 characters that bash…" | pre-release | flows |  |
| 214 | "The gate admits them." | pre-release | flows |  |
| 215 | "A short cap refuses the three by the…" | pre-release | flows |  |
| 216 | "**Done means:** the lengths are exact, `bash -n`…" | pre-release | flows |  |
| 217 | "This check has landed." | pre-release | flows |  |
| 218 | "The harness is `runner/tests/test_proof_content_500k.py`." | pre-release | flows |  |
| 219 | "The record is `stage9.md`." | pre-release | flows |  |
| 220 | "A script of 500,001 characters is still admitted." | pre-release | flows |  |
| 221 | "The production cap, 1048576 bytes, was not generated…" | pre-release | flows |  |
| 222 | "**Contents.** The last figure." | pre-release | flows |  |
| 223 | "The code admits a script of exactly 1048576…" | pre-release | flows |  |
| 224 | "The texts on each side of that boundary…" | pre-release | flows |  |
| 225 | "The scripts are ASCII, so the character count…" | pre-release | flows |  |
| 226 | "The check counts bytes." | pre-release | flows |  |
| 227 | "**Done means:** the lengths are exact, `bash -n`…" | pre-release | flows |  |
| 228 | "This check has landed." | pre-release | flows |  |
| 229 | "The harness is `runner/tests/test_proof_content_cap.py`." | pre-release | flows |  |
| 230 | "The record is `stage10.md`." | pre-release | flows |  |
| 231 | "The four sections above are the first series,…" | pre-release | flows |  |
| 232 | "The series was redone in full — both…" | pre-release | flows |  |
| 233 | "Its records are `content-rung-49.md`, `content-rung-5000.md`, `content-rung-50000.md`, `content-rung-500000.md`, and…" | pre-release | flows |  |
| 234 | "The final position, the same in `thinking.md` and…" | pre-release | flows |  |
| 235 | "The redo demonstrates it empirically: at the first…" | pre-release | flows |  |
| 236 | "No rung enumerates the full closure, and no…" | pre-release | flows |  |
| 237 | "Every stage in this plan has landed." | pre-release | flows |  |
| 238 | "The six properties are stated, modelled, and checked;…" | pre-release | flows |  |
| 239 | "The final consistency pass re-ran the full proof…" | pre-release | flows |  |
| 240 | "311 passed outright; the 8 skipped are the…" | pre-release | flows |  |
| 241 | "The sum of the claims is exactly the…" | pre-release | flows |  |
| 242 | "It does not change any runner behaviour." | pre-release | flows |  |
| 243 | "A code defect found by this work is…" | pre-release | flows |  |
| 244 | "It does not touch PROTOCOL.md or any Internet-Draft…" | pre-release | flows |  |
| 245 | "If a checked property ever earns a place…" | post-release | flows |  |
| 246 | "It does not claim the whole system is…" | pre-release | flows |  |
| 247 | "Each stage's claim names its property, its bound,…" | pre-release | flows |  |
