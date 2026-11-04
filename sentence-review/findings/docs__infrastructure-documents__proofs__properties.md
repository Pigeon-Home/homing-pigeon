# Findings — docs/infrastructure-documents/proofs/properties.md

Source: docs/infrastructure-documents/proofs/properties.md, reviewed at main a2300587.
Sentence units: 375. Flagged: 0. Categories: pre-release 375, post-release 0.

The 6 property statements, P1–P6, each in full form and short form, with their clauses, assumptions, and scope notes. Formal statement prose: clauses are fragments by design inside their numbered lists and connect through the statements that frame them; the short-form lead-ins hand over directly. Nothing is flagged. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This file states the properties the proof work…" | pre-release | flows |  |
| 2 | "P1 is stated in full, precisely enough to…" | pre-release | flows |  |
| 3 | "Constraint identifiers (C1, C2, and so on) refer…" | pre-release | flows |  |
| 4 | "**Sender.** Any party who can place a message…" | pre-release | flows |  |
| 5 | "The sender is untrusted." | pre-release | flows |  |
| 6 | "The sender's address is logged for audit and…" | pre-release | flows |  |
| 7 | "**Attacker.** A sender who holds no shared secret,…" | pre-release | flows |  |
| 8 | "The attacker cannot forge an HMAC-SHA-384 signature under…" | pre-release | flows |  |
| 9 | "**Runner.** The process on the host that polls…" | pre-release | flows |  |
| 10 | "The runner is trusted to run its own…" | pre-release | flows |  |
| 11 | "**Key.** A shared secret in the runner's secret…" | pre-release | flows |  |
| 12 | "A key's policy entry (C14) can narrow what…" | pre-release | flows |  |
| 13 | "Holding a key authorizes exactly what the gate…" | pre-release | flows |  |
| 14 | "**Transport.** The pipe a message arrives on." | pre-release | flows |  |
| 15 | "A transport is untrusted as a carrier, and…" | pre-release | flows |  |
| 16 | "**Oracle.** The runner's reviewer." | pre-release | flows |  |
| 17 | "It reads a job before execution and attaches…" | pre-release | flows |  |
| 18 | "It is advisory by construction: it never blocks…" | pre-release | flows |  |
| 19 | "A property that needed the Oracle to be…" | pre-release | flows |  |
| 20 | "**Configuration.** The owner's `config.json`, loaded once at startup,…" | pre-release | flows |  |
| 21 | "Configuration is trusted as the owner's statement of…" | pre-release | flows |  |
| 22 | "**Execution** means the runner starts the job's script…" | pre-release | flows |  |
| 23 | "Building a result, resending a stashed result, and…" | pre-release | flows |  |
| 24 | "**Character count** of a script means the number…" | pre-release | flows |  |
| 25 | "The production script cap measures UTF-8 bytes instead…" | pre-release | flows |  |
| 26 | "**The starting bound** for P1's first model is…" | pre-release | flows |  |
| 27 | "The bound limits the model's scope, not the…" | pre-release | flows |  |
| 28 | "P1 is stated as a family over this…" | pre-release | flows |  |
| 29 | "For every message handling in the mail path,…" | pre-release | flows |  |
| 30 | "The raw message was within `max_job_bytes` (C1), or…" | pre-release | flows |  |
| 31 | "A signature verified: HMAC-SHA-384 over the message body,…" | pre-release | flows |  |
| 32 | "If the body was an encryption envelope, it…" | pre-release | flows |  |
| 33 | "If the body was not encrypted, the runner…" | pre-release | flows |  |
| 34 | "The audience check passed (C10): where the feature…" | pre-release | flows |  |
| 35 | "The script was within `max_script_bytes` in UTF-8 bytes…" | pre-release | flows |  |
| 36 | "The body's `v` was the integer 1, its…" | pre-release | flows |  |
| 37 | "The job was fresh: `issued_at` parsed, carried a…" | pre-release | flows |  |
| 38 | "The signing key's policy allowed the job (C14),…" | pre-release | flows |  |
| 39 | "The job id was not already claimed: not…" | pre-release | flows |  |
| 40 | "In short form, the property the whole project…" | pre-release | flows |  |
| 41 | "No job executes unless it carries a valid…" | pre-release | flows |  |
| 42 | "The short form is a summary." | pre-release | flows |  |
| 43 | "The nine clauses above are the property." | pre-release | flows |  |
| 44 | "Where they differ, the clauses win." | pre-release | flows |  |
| 45 | "P1 is not one claim but a family…" | pre-release | flows |  |
| 46 | "B is the script character bound." | pre-release | flows |  |
| 47 | "Everything else in the statement — the actors,…" | pre-release | flows |  |
| 48 | "The bound counts characters, not lines and not…" | pre-release | flows |  |
| 49 | "The character count is the measure that tracks…" | pre-release | flows |  |
| 50 | "The family is climbed in stages:" | pre-release | flows |  |
| 51 | "**First rung: P1(49).** Scripts under 50 characters —…" | pre-release | flows |  |
| 52 | "The property MUST be proven at this bound…" | pre-release | flows |  |
| 53 | "**Raised rungs.** The same nine clauses, re-proven at…" | pre-release | flows |  |
| 54 | "The rungs above it are the same searched…" | pre-release | flows |  |
| 55 | "Each of those rungs has also been run…" | pre-release | flows |  |
| 56 | "They are not four additional graphs." | pre-release | flows |  |
| 57 | "The runs are the checks the ladder's stages…" | pre-release | flows |  |
| 58 | "**Last rung: the production cap.** The code's script…" | pre-release | flows |  |
| 59 | "Every script the runner can accept satisfies that…" | pre-release | flows |  |
| 60 | "P1(1048576) therefore covers every script that can pass…" | pre-release | flows |  |
| 61 | "The two measures — characters for the model,…" | pre-release | flows |  |
| 62 | "A checked claim at one rung says nothing…" | pre-release | flows |  |
| 63 | "P1(49) holding does not make P1(500) true; each…" | pre-release | flows |  |
| 64 | "If a higher rung produces a counterexample, the…" | pre-release | flows |  |
| 65 | "Clause 4 is the one place where P1's…" | pre-release | flows |  |
| 66 | "With the audience feature `off` — the default…" | pre-release | flows |  |
| 67 | "With the feature in `audit`, a job for…" | pre-release | flows |  |
| 68 | "Only in `enforce` does the short-form sentence "addressed…" | pre-release | flows |  |
| 69 | "The first model therefore states P1 twice: in…" | pre-release | flows |  |
| 70 | "Both forms are worth checking." | pre-release | flows |  |
| 71 | "The default form is what a fresh install…" | pre-release | flows |  |
| 72 | "The order matters to a model: a check…" | pre-release | flows |  |
| 73 | "The order below is the order in `runner/ops/mail.py`,…" | pre-release | flows |  |
| 74 | "Line numbers are that function's unless another file…" | pre-release | flows |  |
| 75 | "**Panic before everything.** Lines 42 to 58." | pre-release | flows |  |
| 76 | "If the subject carries the panic word, the…" | pre-release | flows |  |
| 77 | "If the box is already stopped, the message…" | pre-release | flows |  |
| 78 | "This step reads only the subject and runs…" | pre-release | flows |  |
| 79 | "**Raw size bound.** Lines 64 to 70 (C1)." | pre-release | flows |  |
| 80 | "An over-cap marked message is refused before any…" | pre-release | flows |  |
| 81 | "Every protocol message the door takes — jobs,…" | pre-release | flows |  |
| 82 | "**Early dispatch and routing.** Line 72 calls `_early_dispatch`…" | pre-release | flows |  |
| 83 | "In order, it handles cancel mail, query mail,…" | pre-release | flows |  |
| 84 | "What returns is a fresh `(job_id, skey)` pair…" | pre-release | flows |  |
| 85 | "**Verification and decryption.** Line 87 calls `_verify_and_decrypt` (`runner/runner.py`,…" | pre-release | flows |  |
| 86 | "The outer body verifies through `verify_body_keyed` (C5, C7)." | pre-release | flows |  |
| 87 | "An `hp_enc` envelope is then decrypted (C9) and…" | pre-release | flows |  |
| 88 | "A bad signature and a bad envelope are…" | pre-release | flows |  |
| 89 | "**Cleartext decision.** Lines 96 to 130 (C8)." | pre-release | flows |  |
| 90 | "An unencrypted job proceeds only when `_cleartext_jobs_allowed()` holds…" | pre-release | flows |  |
| 91 | "**Audience.** Line 132 (C10)." | pre-release | flows |  |
| 92 | "`audience_allows` applies the three-mode decision." | pre-release | flows |  |
| 93 | "An `enforce` mismatch refuses the job as a…" | pre-release | flows |  |
| 94 | "**Encodability.** Lines 138 to 142." | pre-release | flows |  |
| 95 | "A signed body whose text carries an unpaired…" | pre-release | flows |  |
| 96 | "**Script size bound.** Lines 147 to 154 (C2),…" | pre-release | flows |  |
| 97 | "**Version, type, identity.** Lines 156 to 161 (C13):…" | pre-release | flows |  |
| 98 | "**Freshness.** Lines 163 to 176 (C12): `issued_at` parses,…" | pre-release | flows |  |
| 99 | "**Key policy.** Lines 178 to 183 (C14): `check_key_policy`…" | pre-release | flows |  |
| 100 | "**Pinned-key constraints.** Lines 190 to 219 (C11)." | pre-release | flows |  |
| 101 | "Where the key has a policy and any…" | pre-release | flows |  |
| 102 | "**Sensor branch.** A job of kind `sensor_alert` leaves…" | pre-release | flows |  |
| 103 | "It has passed every check above; it is…" | pre-release | flows |  |
| 104 | "**Advisory review.** The Oracle reviews the job and…" | pre-release | flows |  |
| 105 | "It never blocks; a review that raises is…" | pre-release | flows |  |
| 106 | "This step is listed so the model records…" | pre-release | flows |  |
| 107 | "**Dry run stops here.** A dry-run handling verifies…" | pre-release | flows |  |
| 108 | "**The claim.** Lines 260 to 278 (C15)." | pre-release | flows |  |
| 109 | "Under the mail lock, a job id already…" | pre-release | flows |  |
| 110 | "Only a handling that takes the claim proceeds." | pre-release | flows |  |
| 111 | "**The record before the result.** A job whose…" | pre-release | flows |  |
| 112 | "A cancellation recorded before arrival refuses the job." | pre-release | flows |  |
| 113 | "The judge and the Oracle opinion run here;…" | pre-release | flows |  |
| 114 | "Protocol version 2's before-execution exchange also runs inside…" | pre-release | flows |  |
| 115 | "Execution is reachable only at the end of…" | pre-release | flows |  |
| 116 | "Every earlier step can refuse, and a refusal…" | pre-release | flows |  |
| 117 | "A counterexample to P1 is a single concrete…" | pre-release | flows |  |
| 118 | "Any one of these shapes is a counterexample,…" | pre-release | flows |  |
| 119 | "An unsigned job, or a job whose signature…" | pre-release | flows |  |
| 120 | "A job signed under key A executes carrying…" | pre-release | flows |  |
| 121 | "A signature-valid cleartext job executes in a process…" | pre-release | flows |  |
| 122 | "A job whose claimed audience differs from the…" | pre-release | flows |  |
| 123 | "A marked raw message over `max_job_bytes`, or a…" | pre-release | flows |  |
| 124 | "A job with `v` of 2, `true`, or…" | pre-release | flows |  |
| 125 | "A stale job, or one dated more than…" | pre-release | flows |  |
| 126 | "A job its key's policy forbids — a…" | pre-release | flows |  |
| 127 | "The same job id executes twice inside the…" | pre-release | flows |  |
| 128 | "A counterexample found in the model but not…" | pre-release | flows |  |
| 129 | "A counterexample reproducible in the code is a…" | pre-release | flows |  |
| 130 | "Both are findings." | pre-release | flows |  |
| 131 | "Neither is resolved by weakening the statement after…" | pre-release | flows |  |
| 132 | "The first model covers the mail path only,…" | pre-release | flows |  |
| 133 | "Script content is abstracted to what the gate…" | pre-release | flows |  |
| 134 | "Queries, board mail, version 2 mail, cancels, and…" | pre-release | flows |  |
| 135 | "P2 starts where P1 ends: a job has…" | pre-release | flows |  |
| 136 | "The sender of that job may hold a…" | pre-release | flows |  |
| 137 | "P2 is the claim that the ceiling is…" | pre-release | flows |  |
| 138 | "For every execution of a job and every…" | pre-release | flows |  |
| 139 | "**The sandbox decision is the owner's.** Whether the…" | pre-release | flows |  |
| 140 | "No field in the job is read by…" | pre-release | flows |  |
| 141 | "**The writable set cannot grow.** Inside the sandbox,…" | pre-release | flows |  |
| 142 | "No job field adds a writable path." | pre-release | flows |  |
| 143 | "Outside the sandbox — mode `off`, mode `audit`,…" | pre-release | flows |  |
| 144 | "**The visible set grows by one bounded rule…" | pre-release | flows |  |
| 145 | "The job names no path to bind; the…" | pre-release | flows |  |
| 146 | "This clause is stated with the rule inside…" | pre-release | flows |  |
| 147 | "**The watched set and its verdict are the…" | pre-release | flows |  |
| 148 | "The verdict — confined, violated, or unconfigured —…" | pre-release | flows |  |
| 149 | "A job may ask for the `confined_to_workspace` attestation;…" | pre-release | flows |  |
| 150 | "**The disclosure view is the narrower of the…" | pre-release | flows |  |
| 151 | "A requested view that is absent or unrecognised…" | pre-release | flows |  |
| 152 | "No job field produces a view wider than…" | pre-release | flows |  |
| 153 | "**The query budget is the smaller of the…" | pre-release | flows |  |
| 154 | "A job may spend its budget down; it…" | pre-release | flows |  |
| 155 | "**Redaction patterns are the runner's.** The patterns a…" | pre-release | flows |  |
| 156 | "The job's `redact_patterns` member is read nowhere in…" | pre-release | flows |  |
| 157 | "**Query answers carry runner-computed values, gated by the…" | pre-release | flows |  |
| 158 | "The raw-line operations (`grep`, `tail`) are answered only…" | pre-release | flows |  |
| 159 | "Every query spends one unit of the clause…" | pre-release | flows |  |
| 160 | "**Fields named for the settings do nothing.** A…" | pre-release | flows |  |
| 161 | "Disabling confinement from inside a job is not…" | pre-release | flows |  |
| 162 | "In short form:" | pre-release | flows |  |
| 163 | "The ceiling on what execution may touch, and…" | pre-release | flows |  |
| 164 | "A job's fields can narrow what it gets…" | pre-release | flows |  |
| 165 | "They cannot widen either ceiling, and they cannot…" | pre-release | flows |  |
| 166 | "The short form is a summary." | pre-release | flows |  |
| 167 | "The nine clauses above are the property." | pre-release | flows |  |
| 168 | "Where they differ, the clauses win." | pre-release | flows |  |
| 169 | "A counterexample to P2 is a single concrete…" | pre-release | flows |  |
| 170 | "Any one of these shapes is a counterexample:" | pre-release | flows |  |
| 171 | "A result delivered in a view wider than…" | pre-release | flows |  |
| 172 | "More queries answered for a job than the…" | pre-release | flows |  |
| 173 | "A sandboxed job able to write outside its…" | pre-release | flows |  |
| 174 | "A mount in the sandbox of a path…" | pre-release | flows |  |
| 175 | "A `confined_to_workspace` attestation reporting the value the job…" | pre-release | flows |  |
| 176 | "Output leaving unredacted because the job's own `redact_patterns`…" | pre-release | flows |  |
| 177 | "A raw-line answer (`grep` or `tail`) returned under…" | pre-release | flows |  |
| 178 | "The checked model, the configurations, and the witnesses…" | pre-release | flows |  |
| 179 | "P3 stands in front of P1." | pre-release | flows |  |
| 180 | "A message reaches the signature check only by…" | pre-release | flows |  |
| 181 | "Where a transport has credentials of its own,…" | pre-release | flows |  |
| 182 | "Where a transport has none, the signature stands…" | pre-release | flows |  |
| 183 | "The composition is by position, and one fact…" | pre-release | flows |  |
| 184 | "`_service_transports` (`runner/runner.py`, line 5300) services each enabled transport's…" | pre-release | flows |  |
| 185 | "The core performs no transport-credential check and receives…" | pre-release | flows |  |
| 186 | "The clauses below are therefore claims about where…" | pre-release | flows |  |
| 187 | "**The order is fixed.** On every transport that…" | pre-release | flows |  |
| 188 | "A transport-gate failure is not a signature refusal:…" | pre-release | flows |  |
| 189 | "**A valid signature is not sufficient where a…" | pre-release | flows |  |
| 190 | "**The credential gate is not sufficient either.** An…" | pre-release | flows |  |
| 191 | "Passing a pipe's credential check authorizes nothing by…" | pre-release | flows |  |
| 192 | "**Email has no sender gate, and the property…" | pre-release | flows |  |
| 193 | "Anyone who can route a message into the…" | pre-release | flows |  |
| 194 | "If the login fails, the email extension's pass…" | pre-release | flows |  |
| 195 | "Email stands on the signature alone, by design…" | pre-release | flows |  |
| 196 | "**File's gate is the operating system's, held outside…" | pre-release | flows |  |
| 197 | "What decides who may present a file at…" | pre-release | flows |  |
| 198 | "P3's claim for file is therefore an environment…" | pre-release | flows |  |
| 199 | "The runner's code cannot check that condition, and…" | pre-release | flows |  |
| 200 | "**NATS's gate is broker authentication, required unless waived…" | pre-release | flows |  |
| 201 | "With credentials configured, the broker enforces them at…" | pre-release | flows |  |
| 202 | "A publisher faces the broker's same rule: a…" | pre-release | flows |  |
| 203 | "Two conditions bound the claim, and both are…" | pre-release | flows |  |
| 204 | "**DTLS's gate is the shared secret itself, in…" | pre-release | flows |  |
| 205 | "The gate is the handshake in `runner/wire/dtlsproto.py`: the…" | pre-release | flows |  |
| 206 | "Only an established session produces the application-message event…" | pre-release | flows |  |
| 207 | "Resumption PSKs are issued only inside an established…" | pre-release | flows |  |
| 208 | "The two gates are real and ordered, but…" | pre-release | flows |  |
| 209 | "The claim for DTLS is two checks, one…" | pre-release | flows |  |
| 210 | "**Queues' gates are bearer tokens at the hosted…" | pre-release | flows |  |
| 211 | "Job submission requires the SI's token first (line…" | pre-release | flows |  |
| 212 | "The runner's token gates the other direction: lease,…" | pre-release | flows |  |
| 213 | "The edge signature check is a duplicate of…" | pre-release | flows |  |
| 214 | "**A waived gate is a waived property.** Any…" | pre-release | flows |  |
| 215 | "The signature gate of P1 is unaffected by…" | pre-release | flows |  |
| 216 | "In short form:" | pre-release | flows |  |
| 217 | "Where a transport has credentials of its own,…" | pre-release | flows |  |
| 218 | "Where a transport has none — email —…" | pre-release | flows |  |
| 219 | "The short form is a summary." | pre-release | flows |  |
| 220 | "The nine clauses above are the property." | pre-release | flows |  |
| 221 | "Where they differ, the clauses win." | pre-release | flows |  |
| 222 | "A counterexample to P3 is a single concrete…" | pre-release | flows |  |
| 223 | "Any one of these shapes is a counterexample:" | pre-release | flows |  |
| 224 | "A job presented to the core over NATS,…" | pre-release | flows |  |
| 225 | "A queues job enqueued by a submission with…" | pre-release | flows |  |
| 226 | "A DTLS application message delivered to the core…" | pre-release | flows |  |
| 227 | "A NATS message delivered into the channel while…" | pre-release | flows |  |
| 228 | "A file delivered by the file extension that…" | pre-release | flows |  |
| 229 | "The checked model, the configurations, and the witnesses…" | pre-release | flows |  |
| 230 | "P4 is P1's clause 8 taken on its…" | pre-release | flows |  |
| 231 | "One key in particular carries it: the upgrade…" | pre-release | flows |  |
| 232 | "The claim is that the pinning machinery —…" | pre-release | flows |  |
| 233 | "The step this property speaks about is `check_key_policy`…" | pre-release | flows |  |
| 234 | "The policy map it reads is built by…" | pre-release | flows |  |
| 235 | "The other doors — query, board, version 2,…" | pre-release | flows |  |
| 236 | "For every job decided at the policy step,…" | pre-release | flows |  |
| 237 | "**The step speaks for the key that verified.**…" | pre-release | flows |  |
| 238 | "A job MUST NOT be verified under one…" | pre-release | flows |  |
| 239 | "**The key directory speaks first.** Where a directory…" | pre-release | flows |  |
| 240 | "**No entry means unrestricted — with one flag,…" | pre-release | flows |  |
| 241 | "The default key is exempt from that flag…" | pre-release | flows |  |
| 242 | "**The policy is the key's, not the name's.**…" | pre-release | flows |  |
| 243 | "The verdict MUST NOT depend on which of…" | pre-release | flows |  |
| 244 | "**Kinds.** Where `allowed_kinds` is present, the job's kind…" | pre-release | flows |  |
| 245 | "For the upgrade key, whose list is `["exec"]`…" | pre-release | flows |  |
| 246 | "**Recipes and interpreters.** Where `allowed_recipes` is present, a…" | pre-release | flows |  |
| 247 | "Where `allowed_interpreters` is present, the job's effective interpreter…" | pre-release | flows |  |
| 248 | "**Timeout.** Where `max_timeout_sec` is present, the job's effective…" | pre-release | flows |  |
| 249 | "For the upgrade arrangement the cap is 300…" | pre-release | flows |  |
| 250 | "**Script pinning.** Where `allowed_script_sha384` is present and the…" | pre-release | flows |  |
| 251 | "A `script_url` is refused under such a policy…" | pre-release | flows |  |
| 252 | "A missing or non-string script is refused." | pre-release | flows |  |
| 253 | "The branch does not run for other kinds:…" | pre-release | flows |  |
| 254 | "**The fence stands at the other doors.** The…" | pre-release | flows |  |
| 255 | "The cancel door is exempt from the kinds…" | pre-release | flows |  |
| 256 | "For the upgrade key, `["exec"]` names no other…" | pre-release | flows |  |
| 257 | "The key directory also gates the DTLS transport's…" | pre-release | flows |  |
| 258 | "**A repaired job is re-judged.** The one repair…" | pre-release | flows |  |
| 259 | "**The surrounding fences are mode-gated, and the statement…" | pre-release | flows |  |
| 260 | "In particular the upgrade arrangement's `allowed_files` fence (C22)…" | pre-release | flows |  |
| 261 | "Clauses 5 to 8 are not mode-gated: they…" | pre-release | flows |  |
| 262 | "**A malformed policy never reaches the step.** `build_key_policies`…" | pre-release | flows |  |
| 263 | "The map the step reads contains only validated…" | pre-release | flows |  |
| 264 | "In short form:" | pre-release | flows |  |
| 265 | "A key's policy is a fence with that…" | pre-release | flows |  |
| 266 | "The upgrade key's fence admits one shape: an…" | pre-release | flows |  |
| 267 | "Every other shape from that key is refused…" | pre-release | flows |  |
| 268 | "The short form is a summary." | pre-release | flows |  |
| 269 | "The twelve clauses above are the property." | pre-release | flows |  |
| 270 | "Where they differ, the clauses win." | pre-release | flows |  |
| 271 | "A counterexample to P4 is a single concrete…" | pre-release | flows |  |
| 272 | "Any one of these shapes is a counterexample:" | pre-release | flows |  |
| 273 | "An execution job signed with the upgrade key…" | pre-release | flows |  |
| 274 | "An execution job carrying a `script_url`, alone or…" | pre-release | flows |  |
| 275 | "A job of any other kind from the…" | pre-release | flows |  |
| 276 | "A job from a governed key executes with…" | pre-release | flows |  |
| 277 | "An additional key's verdict differs by the name…" | pre-release | flows |  |
| 278 | "A key the directory refuses runs a job…" | pre-release | flows |  |
| 279 | "A query, board, or version 2 message from…" | pre-release | flows |  |
| 280 | "The checked model, the configurations, and the witnesses…" | pre-release | flows |  |
| 281 | "P5 is the property of time and repetition:…" | pre-release | flows |  |
| 282 | "Execution is at most once per job per…" | pre-release | flows |  |
| 283 | "Stage 2's `Claim.tla` checked the narrow core —…" | pre-release | flows |  |
| 284 | "This statement is written from those mechanics as…" | pre-release | flows |  |
| 285 | "A **job**, for this property, is a job…" | pre-release | flows |  |
| 286 | "The distinction carries the property." | pre-release | flows |  |
| 287 | "An attacker replaying captured bytes presents the identical…" | pre-release | flows |  |
| 288 | "A different body under the same id is…" | pre-release | flows |  |
| 289 | "Three layers of state, all on disk in…" | pre-release | flows |  |
| 290 | "**The replay cache** — `seen.json`, keyed by the…" | pre-release | flows |  |
| 291 | "The in-memory set a poll cycle works with…" | pre-release | flows |  |
| 292 | "**The claim** — an in-process half and a…" | pre-release | flows |  |
| 293 | "In one process, the check-and-add under `_MAIL_LOCK` against…" | pre-release | flows |  |
| 294 | "**The record** — the result itself, stashed in…" | pre-release | flows |  |
| 295 | "A redelivery that reaches the record is answered…" | pre-release | flows |  |
| 296 | "For every job delivered to the gate —…" | pre-release | flows |  |
| 297 | "**At most once, per job.** A job MUST…" | pre-release | flows |  |
| 298 | "Two executions of two different jobs that share…" | pre-release | flows |  |
| 299 | "**The cache answers first.** A delivery whose id…" | pre-release | flows |  |
| 300 | "The result the sender is waiting for is…" | pre-release | flows |  |
| 301 | "**One claim, in both halves.** While a handling…" | pre-release | flows |  |
| 302 | "In one process the second handling is skipped…" | pre-release | flows |  |
| 303 | "Across processes the second handling finds the claim…" | pre-release | flows |  |
| 304 | "**A dead holder's claim is stealable, on the…" | pre-release | flows |  |
| 305 | "Stealing a claim never by itself executes anything…" | pre-release | flows |  |
| 306 | "**The record answers the resend.** A delivery that…" | pre-release | flows |  |
| 307 | "This path is reached when the cache no…" | pre-release | flows |  |
| 308 | "**A different job under a reused id runs…" | pre-release | flows |  |
| 309 | "While the cache holds the id, clause 2…" | pre-release | flows |  |
| 310 | "**The crash window, priced.** A crash — or…" | pre-release | flows |  |
| 311 | "A crash after the commit cannot re-execute: the…" | pre-release | flows |  |
| 312 | "This is the one window C15 names, and…" | pre-release | flows |  |
| 313 | "**The cache's window is built to outlast the…" | pre-release | flows |  |
| 314 | "A replay old enough to have left the…" | pre-release | flows |  |
| 315 | "**The record's window, priced.** A delivered record ages…" | pre-release | flows |  |
| 316 | "Once the record is gone and the cache…" | pre-release | flows |  |
| 317 | "A replay of the original bytes cannot reach…" | pre-release | flows |  |
| 318 | "**Delivery is at least once, inside the stash…" | pre-release | flows |  |
| 319 | "After `result_stash_retention_sec` of attempts (default 86,400 seconds) the…" | pre-release | flows |  |
| 320 | "Inside that window the result MUST be delivered…" | pre-release | flows |  |
| 321 | "**Restart changes nothing but the dead claim.** Every…" | pre-release | flows |  |
| 322 | "A runner restarted cleanly between a commit and…" | pre-release | flows |  |
| 323 | "In short form:" | pre-release | flows |  |
| 324 | "A job executes at most once per state…" | pre-release | flows |  |
| 325 | "The replay cache turns a duplicate away; one…" | pre-release | flows |  |
| 326 | "The guarantee has three priced edges: a crash…" | pre-release | flows |  |
| 327 | "Outside those edges, replay is answered, never re-run." | pre-release | flows |  |
| 328 | "The short form is a summary." | pre-release | flows |  |
| 329 | "The eleven clauses above are the property." | pre-release | flows |  |
| 330 | "Where they differ, the clauses win." | pre-release | flows |  |
| 331 | "A counterexample to P5 is a single concrete…" | pre-release | flows |  |
| 332 | "Any one of these shapes is a counterexample:" | pre-release | flows |  |
| 333 | "Two handlings of one job, in one process…" | pre-release | flows |  |
| 334 | "A redelivery is answered by re-running the job…" | pre-release | flows |  |
| 335 | "A redelivery carrying a different job under the…" | pre-release | flows |  |
| 336 | "A claim whose holder is alive is taken…" | pre-release | flows |  |
| 337 | "A restart by itself — no crash between…" | pre-release | flows |  |
| 338 | "The checked model, the configurations, and the witnesses…" | pre-release | flows |  |
| 339 | "`Claim.tla` (stage 2) remains the check of the…" | pre-release | flows |  |
| 340 | "Decision 1 (`docs/design/present-but-invalid-config.md`) splits a setting that is…" | pre-release | flows |  |
| 341 | "P6 is that split, as the code performs…" | pre-release | flows |  |
| 342 | "The actors are the owner, who writes `config.json`,…" | pre-release | flows |  |
| 343 | "No job is involved." | pre-release | flows |  |
| 344 | "A wrong value here is the owner's, not…" | pre-release | flows |  |
| 345 | "For every setting the inventory classifies, the following…" | pre-release | flows |  |
| 346 | "A key that is absent is not a…" | pre-release | flows |  |
| 347 | "It reads as its documented default, and it…" | pre-release | flows |  |
| 348 | "`defaulted.is_defaulted` is false when the value is `None`…" | pre-release | flows |  |
| 349 | "A present usable value is used as written." | pre-release | flows |  |
| 350 | "It is not named." | pre-release | flows |  |
| 351 | "A present unusable value in the default class…" | pre-release | flows |  |
| 352 | "The reader returns the documented default, and the…" | pre-release | flows |  |
| 353 | "A boolean is never a number, a non-finite…" | pre-release | flows |  |
| 354 | "A present unusable value in the refuse class…" | pre-release | flows |  |
| 355 | "The process exits 2." | pre-release | flows |  |
| 356 | "Size caps, mailbox ports, key policies, and the…" | pre-release | flows |  |
| 357 | "A live reload of a default-class value that…" | pre-release | flows |  |
| 358 | "It does not keep a hidden last-good value,…" | pre-release | flows |  |
| 359 | "A refuse-class key is not in the live-reload…" | pre-release | flows |  |
| 360 | "A later write, usable or not, does not…" | pre-release | flows |  |
| 361 | "The process keeps running." | pre-release | flows |  |
| 362 | "The new value is read at the next…" | pre-release | flows |  |
| 363 | "A reload that cannot read the file changes…" | pre-release | flows |  |
| 364 | "In short form: a typo in a tunable…" | pre-release | flows |  |
| 365 | "The runner starts, and reads a job, while…" | pre-release | flows |  |
| 366 | "A default-class setting that is present and unusable…" | pre-release | flows |  |
| 367 | "An absent key is named as if the…" | pre-release | flows |  |
| 368 | "A live reload of an unusable default-class value…" | pre-release | flows |  |
| 369 | "A live reload of a refuse-class value changes…" | pre-release | flows |  |
| 370 | "The checked model is `Decision.tla`." | pre-release | flows |  |
| 371 | "The record is `stage4-p6.md`." | pre-release | flows |  |
| 372 | "Clause 7 is the one clause the model…" | pre-release | flows |  |
| 373 | "Clause 7 is held by the code read…" | pre-release | flows |  |
| 374 | "None remain." | pre-release | flows |  |
| 375 | "P1 through P6 are stated above." | pre-release | flows |  |
