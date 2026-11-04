# Findings — docs/infrastructure-documents/proofs/constraints.md

Source: docs/infrastructure-documents/proofs/constraints.md, reviewed at main cbb52068.
Sentence units: 285. Flagged: 1. Categories: pre-release 285, post-release 0.

Each entry leads with its bold field name (Constraint, Value, Where, Class) and completes in the units that follow; the summary table at units 258-285 restates the entries in short form.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Every constraint below was read from the code…" | pre-release | flows |  |
| 2 | "No value here was taken from another document…" | pre-release | flows |  |
| 3 | "Where another document states a different value, the…" | pre-release | flows |  |
| 4 | "Each entry names four things: the constraint, its…" | pre-release | flows |  |
| 5 | "Decision 1 (`docs/design/present-but-invalid-config.md`) splits a present-but-unusable configuration value…" | pre-release | flows |  |
| 6 | "**Refuse class.** The runner MUST refuse to start…" | pre-release | flows |  |
| 7 | "Ports and bind addresses, key policies, the thresholds…" | pre-release | flows |  |
| 8 | "**Default class.** Every other present-but-unusable setting reads as…" | pre-release | flows |  |
| 9 | "Live reload reads a bad value as the…" | pre-release | flows |  |
| 10 | "**Not a configuration setting.** Some constraints are constants…" | pre-release | flows |  |
| 11 | "Those are marked as such: there is no…" | pre-release | flows |  |
| 12 | "Two layers in the code are easy to…" | pre-release | flows |  |
| 13 | "A runtime reader often falls back to a…" | pre-release | flows |  |
| 14 | "The startup validator runs first and is the…" | pre-release | flows |  |
| 15 | "**Constraint:** a raw protocol mail that is marked…" | pre-release | flows |  |
| 16 | "A cap of 0 means unlimited." | pre-release | flows |  |
| 17 | "**Value:** default `4194304` bytes (4 MiB)." | pre-release | flows |  |
| 18 | "**Where:** `runner/ops/mail.py`, `handle_mail`, line 64 — `int(cfg.get("max_job_bytes", 4194304))`,…" | pre-release | flows |  |
| 19 | "The check itself is at lines 67 to…" | pre-release | flows |  |
| 20 | "**Class:** refuse class at startup, with a defensive…" | pre-release | flows |  |
| 21 | "The registry in `runner/tests/defaults_registry.py` records the same row…" | pre-release | flows |  |
| 22 | "**Constraint:** a script inside a signed job body…" | pre-release | flows |  |
| 23 | "The check runs after the signature verifies, because…" | pre-release | flows |  |
| 24 | "A cap of 0 means unlimited." | pre-release | flows |  |
| 25 | "**Value:** default `1048576` bytes (1 MiB)." | pre-release | flows |  |
| 26 | "**Where:** `runner/ops/mail.py`, `handle_mail`, line 147 — `int(cfg.get("max_script_bytes", 1048576))`,…" | pre-release | flows |  |
| 27 | "**Class:** refuse class at startup, on the same…" | pre-release | flows |  |
| 28 | "**Measure note:** the production cap measures UTF-8 **bytes**." | pre-release | flows |  |
| 29 | "The proof work measures **characters** for its own…" | pre-release | flows |  |
| 30 | "The two measures are different things and are…" | pre-release | flows |  |
| 31 | "**Script size in practice:** a typical script a…" | pre-release | flows |  |
| 32 | "Those figures describe what arrives in practice, and…" | pre-release | flows |  |
| 33 | "The binding measure is the script's character count:…" | pre-release | flows |  |
| 34 | "The proof states its gate property as a…" | pre-release | flows |  |
| 35 | "**Constraint:** a result body MUST be fitted to…" | pre-release | flows |  |
| 36 | "The signature always covers what is actually sent." | pre-release | flows |  |
| 37 | "A cap of 0 means unlimited." | pre-release | flows |  |
| 38 | "**Value:** default `5242880` bytes (5 MiB)." | pre-release | flows |  |
| 39 | "The cap is **not** unlimited by default." | pre-release | flows |  |
| 40 | "**Where:** `runner/runner.py`, line 2025 — `MAX_RESULT_BYTES = 5…" | pre-release | flows |  |
| 41 | "**Class:** refuse class at startup, on the same…" | pre-release | flows |  |
| 42 | "The registry row records policy `refuse`, default `5242880`." | pre-release | flows |  |
| 43 | "**Difference from earlier accounts:** an earlier description of…" | pre-release | flows |  |
| 44 | "The code does not say that." | pre-release | flows |  |
| 45 | "Unlimited is reached only by setting the cap…" | pre-release | flows |  |
| 46 | "The default is 5 MiB, and the existing…" | pre-release | flows |  |
| 47 | "The soft spot, as described before, does not…" | pre-release | flows |  |
| 48 | "**Constraint:** a locally delivered envelope (the local-signals path,…" | pre-release | flows |  |
| 49 | "**Value:** `262144` bytes (256 KiB)." | pre-release | flows |  |
| 50 | "A constant, not a configuration key." | pre-release | flows |  |
| 51 | "**Where:** `runner/runner.py`, line 3884 — `_LOCAL_ENVELOPE_MAX_BYTES = 262144`…" | pre-release | flows |  |
| 52 | "**Class:** not a configuration setting." | pre-release | flows |  |
| 53 | "There is no key to present badly; the…" | pre-release | flows |  |
| 54 | "**Constraint:** nothing is executed, answered, or acted on…" | pre-release | flows |  |
| 55 | "The signature on a job body MUST be…" | pre-release | flows |  |
| 56 | "A body with no signature marker, a malformed…" | pre-release | flows |  |
| 57 | "Key selection happens before any MAC is computed:…" | pre-release | flows |  |
| 58 | "**Value:** hash SHA-384; signature 96 lowercase hex characters…" | pre-release | flows |  |
| 59 | "**Where:** `runner/wire/verify.py` — `sign_payload`, line 71, computes `hmac.new(secret.encode("utf-8"),…" | pre-release | flows |  |
| 60 | "**Class:** the signature itself is not a configuration…" | pre-release | flows |  |
| 61 | "The secret behind it is refuse class: see…" | pre-release | flows |  |
| 62 | "**Constraint:** a runner MUST refuse to start with…" | pre-release | flows |  |
| 63 | "Anyone holding one signed message can attack the…" | pre-release | flows |  |
| 64 | "**Value:** estimated entropy at least 128 bits, estimated…" | pre-release | flows |  |
| 65 | "**Where:** `runner/guard/security.py`, `validate_shared_secret`, line 177, re-exported through `runner/wire/verify.py`.…" | pre-release | flows |  |
| 66 | "**Class:** refuse class." | pre-release | flows |  |
| 67 | "Secrets and their floors are named in Decision…" | pre-release | flows |  |
| 68 | "**Constraint:** every secret carries a public name, its…" | pre-release | flows |  |
| 69 | "The fingerprint is a name, not a credential:…" | pre-release | flows |  |
| 70 | "**Value:** `k-` followed by the first 8 hex…" | pre-release | flows |  |
| 71 | "**Where:** `runner/guard/security.py`, line 161 — `KEY_ID_LABEL = b"homing-pigeon…" | pre-release | flows |  |
| 72 | "**Class:** not a configuration setting; a derived name." | pre-release | flows |  |
| 73 | "**Difference from the brief this inventory was built…" | pre-release | flows |  |
| 74 | "The code prepends the label first, deliberately, so…" | pre-release | flows |  |
| 75 | "A model that fingerprints a bare secret models…" | pre-release | flows |  |
| 76 | "**Constraint:** a job whose body is the HMAC-only…" | pre-release | flows |  |
| 77 | "The flag waives the encryption requirement only; the…" | pre-release | flows |  |
| 78 | "There is no configuration key for this: a…" | pre-release | flows |  |
| 79 | "**Value:** default refused." | pre-release | flows |  |
| 80 | "The per-process state `_ALLOW_CLEARTEXT_JOBS` starts as `False`." | pre-release | flows |  |
| 81 | "**Where:** `runner/runner.py`, line 3202 — `_ALLOW_CLEARTEXT_JOBS = False`…" | pre-release | flows |  |
| 82 | "The only setter call in the startup path…" | pre-release | flows |  |
| 83 | "The refusal itself is in `runner/ops/mail.py`, `handle_mail`, lines…" | pre-release | flows |  |
| 84 | "**Class:** not a configuration setting, by design." | pre-release | flows |  |
| 85 | "That absence is the constraint: the decision lives…" | pre-release | flows |  |
| 86 | "**Constraint:** an encrypted job envelope MUST use the…" | pre-release | flows |  |
| 87 | "An envelope naming any other algorithm MUST be…" | pre-release | flows |  |
| 88 | "No partial plaintext escapes a failed decryption." | pre-release | flows |  |
| 89 | "The envelope's signature is verified before decryption is…" | pre-release | flows |  |
| 90 | "**Value:** algorithm string `aes-256-gcm/hkdf-sha384`; AES-256-GCM (NIST SP 800-38D);…" | pre-release | flows |  |
| 91 | "Additional authenticated data binds the envelope to its…" | pre-release | flows |  |
| 92 | "**Where:** `runner/wire/jobcrypto.py` — the construction is stated in…" | pre-release | flows |  |
| 93 | "The DTLS binding reuses the same AEAD in…" | pre-release | flows |  |
| 94 | "**Class:** not a configuration setting." | pre-release | flows |  |
| 95 | "There is no second AEAD to select and…" | pre-release | flows |  |
| 96 | "ChaCha is not present in the construction." | pre-release | flows |  |
| 97 | "**Constraint:** when the audience feature is not `off`…" | pre-release | flows |  |
| 98 | "The expected value always comes from the loaded…" | pre-release | flows |  |
| 99 | "The body claims its audience in the `aud`…" | pre-release | flows |  |
| 100 | "In `enforce` mode a mismatch MUST be refused;…" | pre-release | flows |  |
| 101 | "**Value:** the configured `runner_id` string, an opaque identifier…" | pre-release | flows |  |
| 102 | "It is a deployment value, not a protocol…" | pre-release | flows |  |
| 103 | "The default posture in a fresh configuration is…" | pre-release | flows |  |
| 104 | "**Where:** `runner/wire/verify.py` — `check_audience`, line 1122, states the…" | pre-release | flows |  |
| 105 | "The mail path calls it in `runner/ops/mail.py`, `handle_mail`,…" | pre-release | flows |  |
| 106 | "**Class:** refuse class, as a security mode: a…" | pre-release | flows |  |
| 107 | "The audience decision itself in `enforce` mode refuses…" | pre-release | flows |  |
| 108 | "**Constraint:** each of the six hardening features carries…" | pre-release | flows |  |
| 109 | "A missing security block leaves every feature at…" | pre-release | flows |  |
| 110 | "Changing a mode requires a restart: the configuration…" | pre-release | flows |  |
| 111 | "**Value:** features, in the order the code declares…" | pre-release | flows |  |
| 112 | "Modes — `off`, `audit`, `enforce`." | pre-release | flows |  |
| 113 | "Default for every feature: `enforce`." | pre-release | flows |  |
| 114 | "**Where:** `runner/guard/security.py` — `MODES`, line 39; `FEATURES`, line…" | pre-release | flows |  |
| 115 | "**Class:** refuse class." | pre-release | flows |  |
| 116 | "Security modes are named in Decision 1 itself,…" | pre-release | flows |  |
| 117 | "Two features add their own startup refusals in…" | pre-release | flows |  |
| 118 | "**Constraint:** a job's `issued_at` MUST parse, MUST carry…" | pre-release | flows |  |
| 119 | "A job that fails any part is refused…" | pre-release | flows |  |
| 120 | "**Value:** age cap default `3600` seconds; future bound…" | pre-release | flows |  |
| 121 | "**Where:** `runner/ops/mail.py`, `handle_mail`, lines 163 to 176 —…" | pre-release | flows |  |
| 122 | "**Class:** default class for the age cap itself…" | pre-release | flows |  |
| 123 | "The 300-second bound is a code literal, not…" | pre-release | flows |  |
| 124 | "**Constraint:** a job's `v` MUST be the JSON…" | pre-release | flows |  |
| 125 | "**Value:** `PROTOCOL_VERSION = 1`." | pre-release | flows |  |
| 126 | "**Where:** `runner/runner.py`, line 281, and `_version_ok`, line 283." | pre-release | flows |  |
| 127 | "The checks run in `runner/ops/mail.py`, `handle_mail`, lines 156…" | pre-release | flows |  |
| 128 | "**Class:** not a configuration setting." | pre-release | flows |  |
| 129 | "Protocol version 2 is a configuration-gated overlay on…" | pre-release | flows |  |
| 130 | "**Constraint:** a key with a policy entry may…" | pre-release | flows |  |
| 131 | "When `allowed_script_sha384` is present, a job from that…" | pre-release | flows |  |
| 132 | "Keys without a policy entry are unrestricted unless…" | pre-release | flows |  |
| 133 | "**Value:** the upgrade key on a live deployment…" | pre-release | flows |  |
| 134 | "The digest itself is a deployment value and…" | pre-release | flows |  |
| 135 | "**Where:** `runner/wire/verify.py` — `check_key_policy`, line 878; the script-pinning…" | pre-release | flows |  |
| 136 | "Policy construction (`build_key_policies`) validates the list's shape and…" | pre-release | flows |  |
| 137 | "**Class:** refuse class." | pre-release | flows |  |
| 138 | "Key policies are named in Decision 1 itself;…" | pre-release | flows |  |
| 139 | "**Constraint:** a verified job MUST be executed at…" | pre-release | flows |  |
| 140 | "The result is stashed on disk and the…" | pre-release | flows |  |
| 141 | "A redelivered copy of a job whose result…" | pre-release | flows |  |
| 142 | "**Where:** `runner/ops/mail.py`, `handle_mail` — the claim is taken…" | pre-release | flows |  |
| 143 | "The protocol statement is PROTOCOL.md sections 5 and…" | pre-release | flows |  |
| 144 | "The mechanics this entry abstracts — the cache's…" | pre-release | flows |  |
| 145 | "**Class:** not a configuration setting; an execution semantic." | pre-release | flows |  |
| 146 | "**The named windows, recorded plainly:** the guarantee has…" | pre-release | flows |  |
| 147 | "First, a crash between execution and the stash…" | pre-release | flows |  |
| 148 | "Second, a sent record ages out with `output_retention_days`,…" | pre-release | flows |  |
| 149 | "Inside those edges the guarantee holds; outside them…" | pre-release | flows |  |
| 150 | "**Constraint:** where a transport has credentials of its…" | pre-release | flows |  |
| 151 | "A deployment that waives a transport's own authentication…" | pre-release | flows |  |
| 152 | "**Where:** the pattern is stated where transports are…" | pre-release | flows |  |
| 153 | "The NATS transport is the worked example in…" | pre-release | flows |  |
| 154 | "Email is the honest exception, also stated there:…" | pre-release | flows |  |
| 155 | "**Class:** refuse class in the worked example —…" | pre-release | flows |  |
| 156 | "**Constraint:** a job's `result_policy` may ask for a…" | pre-release | flows |  |
| 157 | "A job MUST NOT be able to raise…" | pre-release | flows |  |
| 158 | "**Value:** views, ordered narrowest first — `attested` (0),…" | pre-release | flows |  |
| 159 | "A requested view that is absent or unrecognised…" | pre-release | flows |  |
| 160 | "The effective view is the requested view when…" | pre-release | flows |  |
| 161 | "Query budget: the job's `query_budget` and the owner's…" | pre-release | flows |  |
| 162 | "**Where:** `runner/runner.py`, line 445 — `VIEW_ORDER = {"attested":…" | pre-release | flows |  |
| 163 | "The raw-line query operations (`grep`, `tail`) are answered…" | pre-release | flows |  |
| 164 | "**Class:** not a configuration setting of its own;…" | pre-release | flows |  |
| 165 | "**Constraint:** when a job runs inside the bubblewrap…" | pre-release | flows |  |
| 166 | "No field in a job names a mount,…" | pre-release | flows |  |
| 167 | "**Value:** the fixed flag set is `DEFAULT_FLAGS` (user,…" | pre-release | flows |  |
| 168 | "**Where:** `runner/guard/sandbox.py` — `WORK_MOUNT`, line 23; `DEFAULT_FLAGS`, lines…" | pre-release | flows |  |
| 169 | "The decision to sandbox at all is `runner/runner.py`,…" | pre-release | flows |  |
| 170 | "**The one job-influenced addition:** the job's `interpreter` field…" | pre-release | flows |  |
| 171 | "When that program resolves outside `/usr`, `interpreter_binds` (`runner/guard/sandbox.py`,…" | pre-release | flows |  |
| 172 | "The rule is uniform (the owner's default interpreter…" | pre-release | flows |  |
| 173 | "A job field therefore can change which interpreter…" | pre-release | flows |  |
| 174 | "**The snapshot side:** what a job is reported…" | pre-release | flows |  |
| 175 | "A query may ask for the `confined_to_workspace` attestation;…" | pre-release | flows |  |
| 176 | "**Class:** the mode and the confinement block are…" | pre-release | flows |  |
| 177 | "**Constraint:** at the hosted queue's edge, a job…" | pre-release | flows |  |
| 178 | "The runner's calls — lease, renew, ack, result…" | pre-release | flows |  |
| 179 | "Tokens are compared by SHA-256 hash against the…" | pre-release | flows |  |
| 180 | "**Value:** the edge signature check, `REJECT_INVALID_HMAC`, is on…" | pre-release | flows |  |
| 181 | "Two distinct tokens exist per tenant: the SI…" | pre-release | flows |  |
| 182 | "Neither token is the shared secret; the edge…" | pre-release | flows |  |
| 183 | "**Where:** `runner/cloud/queues-worker/src/index.js` — `bearerMatches`, line 368 (SHA-256 of…" | pre-release | flows |  |
| 184 | "The runner-token checks are at lines 459 (lease…" | pre-release | flows |  |
| 185 | "The runner-side extension refuses to start with no…" | pre-release | flows |  |
| 186 | "**Class:** refuse class in shape — a missing…" | pre-release | flows |  |
| 187 | "The edge switch itself is a deployment variable…" | pre-release | flows |  |
| 188 | "**Constraint:** each shipped transport's credential gate has a…" | pre-release | flows |  |
| 189 | "A gate that exists MUST be applied before…" | pre-release | flows |  |
| 190 | "**Value, per transport:**" | pre-release | flows |  |
| 191 | "**Email:** no sender gate exists." | pre-release | flows |  |
| 192 | "The mailbox login is the runner's own credential…" | pre-release | flows |  |
| 193 | "**File:** no credential in code." | pre-release | flows |  |
| 194 | "The gate is the inbox directory's OS access…" | pre-release | flows |  |
| 195 | "**NATS:** credentials are required; the waiver is the…" | pre-release | flows |  |
| 196 | "No credentials and no waiver is a refusal…" | pre-release | flows |  |
| 197 | "**DTLS:** no waiver exists." | pre-release | flows |  |
| 198 | "No secret handed over is a refusal to…" | pre-release | flows |  |
| 199 | "The credential is the shared secret itself as…" | pre-release | flows |  |
| 200 | "**Queues:** see C19; both bearer gates are unconditional…" | pre-release | flows |  |
| 201 | "**Where the composition is pinned:** the core hands…" | pre-release | flows |  |
| 202 | "No other pipe ever holds the shared secret,…" | pre-release | flows |  |
| 203 | "**Class:** refuse class where a code refusal exists…" | pre-release | flows |  |
| 204 | "**Constraint:** when a key directory is configured, its…" | pre-release | flows |  |
| 205 | "A key the directory refuses MUST NOT be…" | pre-release | flows |  |
| 206 | "**Where:** `runner/wire/verify.py` — `key_directory_verdict`, line 762; `check_key_policy` takes…" | pre-release | flows |  |
| 207 | "The directory is loaded per check (`load_key_directory`, line…" | pre-release | flows |  |
| 208 | "Startup validation is `validate_key_directory` (line 703): a malformed…" | pre-release | flows |  |
| 209 | "The protocol statement is PROTOCOL.md section 14.4." | pre-release | flows |  |
| 210 | "**Class:** refuse class." | pre-release | flows |  |
| 211 | "A directory that cannot be read or is…" | pre-release | flows |  |
| 212 | "**Constraint:** the standing upgrade arrangement names a key…" | pre-release | flows |  |
| 213 | "Of these fences, kinds, timeout, and the script…" | pre-release | flows |  |
| 214 | "When the staging script changes, its digest in…" | pre-release | flows |  |
| 215 | "**Value:** the arrangement's shape, as written for deployments." | pre-release | flows |  |
| 216 | "The digest value is a deployment value: the…" | pre-release | flows |  |
| 217 | "Each deployment's own configuration carries its digest, beside…" | pre-release | flows |  |
| 218 | "**Where:** `docs/use/sending.md`, the remote upgrade section's "The upgrade…" | pre-release | flows |  |
| 219 | "The kit the arrangement drives is `runner/tools/remote-upgrade/`." | pre-release | flows |  |
| 220 | "**Class:** the arrangement is a deployment's configuration; the…" | pre-release | flows |  |
| 221 | "**Constraint:** a replay-cache entry MUST be kept at…" | pre-release | flows |  |
| 222 | "The horizon is `max(max_job_age_sec + 300, 86400)` seconds…" | pre-release | flows |  |
| 223 | "Entries are written with the time they were…" | pre-release | flows |  |
| 224 | "The cache also has a size ceiling, `SEEN_CAP`,…" | pre-release | flows |  |
| 225 | "**Where:** `runner/runner.py` — `seen_keep_sec` (line 4843) computes the…" | pre-release | flows |  |
| 226 | "**Class:** not a setting of its own; derived…" | pre-release | flows |  |
| 227 | "The cap is the recorded edge: a flood…" | pre-release | flows |  |
| 228 | "Eviction alone does not re-execute — the recorded…" | pre-release | flows |  |
| 229 | "**Constraint:** a claim file whose holder is alive…" | pre-release | flows |  |
| 230 | "A claim whose holder is dead MAY be…" | pre-release | flows |  |
| 231 | "A claim whose holder cannot be read (no…" | pre-release | flows |  |
| 232 | "The claim is a file created with `O_EXCL`…" | pre-release | flows |  |
| 233 | "**Where:** `runner/runner.py` line 4746 is the constant; the…" | pre-release | flows |  |
| 234 | "**Class:** a constant, not a setting." | pre-release | flows |  |
| 235 | "**Constraint:** the recorded result is kept in two…" | pre-release | flows |  |
| 236 | "A waiting record sits in the outbox and…" | pre-release | flows |  |
| 237 | "A delivered record sits in `sent/` and ages…" | pre-release | flows |  |
| 238 | "**Where:** `runner/runner.py` — `_retention_days` (line 1547), `prune_sent` (line…" | pre-release | flows |  |
| 239 | "**Class:** `output_retention_days` and the two stash values are…" | pre-release | flows |  |
| 240 | "**Constraint:** a present-but-unusable value in the default class…" | pre-release | flows |  |
| 241 | "An absent key reads as that default and…" | pre-release | flows |  |
| 242 | "A boolean is never a number." | pre-release | flows |  |
| 243 | "A value outside the key's bounds is unusable,…" | pre-release | flows |  |
| 244 | "**Value:** the table in `runner/guard/defaulted.py`. `poll_interval_sec` defaults to…" | pre-release | flows |  |
| 245 | "The hot-reload twin of the numeric rows is…" | pre-release | flows |  |
| 246 | "**Where:** `runner/guard/confval.py`, `number` (line 78), `integer` (line 94),…" | pre-release | flows |  |
| 247 | "Live reload: `runner/ops/attest.py`, `reload_hot_config`, lines 113 to 136,…" | pre-release | flows |  |
| 248 | "**Class:** default class." | pre-release | flows |  |
| 249 | "This entry is the class itself." | pre-release | flows |  |
| 250 | "**Constraint:** a present-but-unusable value in the refuse class…" | pre-release | flows |  |
| 251 | "The same keys are not in the live-reload…" | pre-release | flows |  |
| 252 | "**Value:** exit code 2 from `runner/ops/main.py` when a…" | pre-release | flows |  |
| 253 | "The live-reload set is `HOT_KEYS` and `LIVE_KEYS` in…" | pre-release | flows |  |
| 254 | "None of those is a port, a bind…" | pre-release | flows |  |
| 255 | "**Where:** `runner/runner.py`, `_validate_size_caps`, line 4707, for `max_job_bytes`, `max_script_bytes`,…" | pre-release | flows |  |
| 256 | "**Class:** refuse class." | pre-release | flows |  |
| 257 | "The defensive runtime readers that still return a…" | pre-release | flows |  |
| 258 | "ID ; Constraint ; Default or value ;…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 259 | "C1 ; `max_job_bytes` ; 4194304 ; refuse (bad…" | pre-release | flows |  |
| 260 | "C2 ; `max_script_bytes` ; 1048576, UTF-8 bytes ;…" | pre-release | flows |  |
| 261 | "C3 ; `max_result_bytes` ; 5242880; 0 is unlimited…" | pre-release | flows |  |
| 262 | "C4 ; `_LOCAL_ENVELOPE_MAX_BYTES` ; 262144, constant ; not…" | pre-release | flows |  |
| 263 | "C5 ; Signature ; HMAC-SHA-384, `compare_digest` ; secret…" | pre-release | flows |  |
| 264 | "C6 ; Secret entropy floor ; 128 bits…" | pre-release | flows |  |
| 265 | "C7 ; Key fingerprint ; `k-` + 8…" | pre-release | flows |  |
| 266 | "C8 ; Cleartext ; refused; `--allow-cleartext` only ;…" | pre-release | flows |  |
| 267 | "C9 ; AEAD ; AES-256-GCM, `aes-256-gcm/hkdf-sha384` ; not…" | pre-release | flows |  |
| 268 | "C10 ; Audience ; configured `runner_id`; `aud` wins…" | pre-release | flows |  |
| 269 | "C11 ; Six security modes ; each `enforce`…" | pre-release | flows |  |
| 270 | "C12 ; `max_job_age_sec` ; 3600; future bound 300…" | pre-release | flows |  |
| 271 | "C13 ; Protocol version ; integer 1 only…" | pre-release | flows |  |
| 272 | "C14 ; Key policies ; per-key; script pin…" | pre-release | flows |  |
| 273 | "C15 ; Execution semantics ; at most once;…" | pre-release | flows |  |
| 274 | "C16 ; Transport credentials ; required where a…" | pre-release | flows |  |
| 275 | "C17 ; Result-policy ceiling ; views attested <…" | pre-release | flows |  |
| 276 | "C18 ; Sandbox shape ; fixed flags; work…" | pre-release | flows |  |
| 277 | "C19 ; Queues edge gates ; SI bearer,…" | pre-release | flows |  |
| 278 | "C20 ; Transport gate postures ; email none;…" | pre-release | flows |  |
| 279 | "C21 ; Key directory precedence ; verdict before…" | pre-release | flows |  |
| 280 | "C22 ; Upgrade key arrangement ; kinds `["exec"]`;…" | pre-release | flows |  |
| 281 | "C23 ; Replay-cache keep horizon ; `max(max_job_age_sec +…" | pre-release | flows |  |
| 282 | "C24 ; Claim stale rule ; live holder…" | pre-release | flows |  |
| 283 | "C25 ; Record retention and delivery window ;…" | pre-release | flows |  |
| 284 | "C26 ; Default-class reader ; unusable reads as…" | pre-release | flows |  |
| 285 | "C27 ; Refuse class at startup ; exit…" | pre-release | flows |  |
