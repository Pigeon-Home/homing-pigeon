# Findings — PROTOCOL.md

Source: PROTOCOL.md, reviewed at main 128027b5.
Sentence units: 736. Flagged: 2. Categories: pre-release 736, post-release 0.

The root protocol manual: the fair warning, the Agent Guide, and the full v1 specification with its bindings, object field definitions, security modes, and the DTLS binding. Field definitions are fragments by the manual's design and flow as entries; the prose connects throughout. 1 rule line and 1 bare cross-reference are the breaks. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The technical protocol description v1: `docs/ietf/draft-slutsky-homing-pigeon/source/draft-homing-pigeon-00.md`" | pre-release | flows |  |
| 2 | "The technical protocol description v2: `docs/ietf/draft-slutsky-homing-pigeon-v2/source/draft-homing-pigeon-v2-00.md`" | pre-release | flows |  |
| 3 | "The technical protocol description v3 (local, unsubmitted): https://github.com/Pigeon-Home/homing-pigeon/blob/main/docs/ietf/draft-slutsky-homing-pigeon-v3/source/draft-slutsky-homing-pigeon-v3-00.md…" | pre-release | flows |  |
| 4 | "A cloud SI may use it with any…" | pre-release | flows |  |
| 5 | "Internet-Draft v1 on the IETF datatracker: https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon/" | pre-release | flows |  |
| 6 | "Internet-Draft v2 on the IETF datatracker: https://datatracker.ietf.org/doc/draft-slutsky-homing-pigeon-v2/" | pre-release | flows |  |
| 7 | "Internet-Draft status (posted, sent, waiting on): `docs/ietf/STATUS.md`" | pre-release | flows |  |
| 8 | "As of 2026-11-03, the repository behind this protocol…" | pre-release | flows |  |
| 9 | "A visiting SI typically has a context of…" | pre-release | flows |  |
| 10 | "If you are an SI reading this to…" | pre-release | flows |  |
| 11 | "Policy, held by the author: just as this…" | pre-release | flows |  |
| 12 | "Notes written for visiting systems, shaped by the…" | pre-release | flows |  |
| 13 | "The measure rides in the version number: the…" | pre-release | flows |  |
| 14 | "**Cloud SI:** composes signed job messages, uploads large…" | pre-release | flows |  |
| 15 | "**Runner (Linux/macOS/FreeBSD/Windows):** polls a dedicated mailbox, verifies and…" | pre-release | flows |  |
| 16 | "Implemented in Python 3.9+ using only the standard…" | pre-release | flows |  |
| 17 | "The roles are a convention, not a requirement." | pre-release | flows |  |
| 18 | "The protocol is symmetric — a signed blob…" | pre-release | flows |  |
| 19 | "Nothing in the message format, signatures, or verification…" | pre-release | flows |  |
| 20 | "It's really just a question of where the…" | pre-release | flows |  |
| 21 | "There's an old chess hustle that runs on…" | pre-release | flows |  |
| 22 | "The middleman wins by contributing nothing but the…" | pre-release | flows |  |
| 23 | "Same here: relay project specs one way and…" | pre-release | flows |  |
| 24 | "The draft's bindings are email, a watched folder,…" | pre-release | flows |  |
| 25 | "No binding is mandatory." | pre-release | flows |  |
| 26 | "A conforming runner offers at least one." | pre-release | flows |  |
| 27 | "The reference default is email only: `transports` absent…" | pre-release | flows |  |
| 28 | "The other bindings are in the draft (Sections…" | pre-release | flows |  |
| 29 | "This section is the email binding." | pre-release | flows |  |
| 30 | "One dedicated mailbox." | pre-release | flows |  |
| 31 | "Both directions use it: The cloud SI sends…" | pre-release | flows |  |
| 32 | "Runner access: IMAP (read, port 993) + SMTP…" | pre-release | flows |  |
| 33 | "Two authentication methods, both transport-level — the protocol…" | pre-release | flows |  |
| 34 | "**Password** (default): mailbox username + app password from…" | pre-release | flows |  |
| 35 | "They are never written to the log or…" | pre-release | flows |  |
| 36 | "The email extension refuses to start without `mailbox_user`,…" | pre-release | flows |  |
| 37 | "A runner whose `transports` list does not include…" | pre-release | flows |  |
| 38 | "Providers that offer app passwords generally require two-factor…" | pre-release | flows |  |
| 39 | "**OAuth** (`"auth": "oauth"`): Thunderbird-style browser sign-in (PKCE +…" | pre-release | flows |  |
| 40 | "The runner stores a refresh token and uses…" | pre-release | flows |  |
| 41 | "The Google password never touches the command line…" | pre-release | flows |  |
| 42 | "The HMAC key is a separate `shared_secret` in…" | pre-release | flows |  |
| 43 | "Requires a Desktop OAuth client id created by…" | pre-release | flows |  |
| 44 | "Subject lines (exact prefixes):" | pre-release | flows |  |
| 45 | "Job: contains `[HOMING-PIGEON]` then `job <job_id>` (a word…" | pre-release | flows |  |
| 46 | "Result: `[HOMING-PIGEON] result <job_id>`" | pre-release | flows |  |
| 47 | "Query: `[HOMING-PIGEON] query <query_id>` (section 10.1), answered under…" | pre-release | flows |  |
| 48 | "Board (section 13.7): `task_submit`, `task_request`, `task_result` and `task_approve`,…" | pre-release | flows |  |
| 49 | "The words of a subject are separated by…" | pre-release | flows |  |
| 50 | "Every reader -- the runner's transports and the…" | pre-release | flows |  |
| 51 | "Version 2 (`docs/ietf/draft-slutsky-homing-pigeon-v2/source/draft-homing-pigeon-v2-00.md`): `determination`, `question` and `answer <msg_id>`" | pre-release | flows |  |
| 52 | "`<job_id>` is 1–128 characters from `[A-Za-z0-9._-]`, and it…" | pre-release | flows |  |
| 53 | "A UUID is recommended, not required." | pre-release | flows |  |
| 54 | "Body is UTF-8 plain text." | pre-release | flows |  |
| 55 | "It must contain one signed JSON object." | pre-release | flows |  |
| 56 | "Surrounding text (a note, a signature block) is…" | pre-release | flows |  |
| 57 | "Every string in that object is UTF-8 text:…" | pre-release | flows |  |
| 58 | "Every number in it is a finite number:…" | pre-release | flows |  |
| 59 | "The object nests at most 200 levels deep,…" | pre-release | flows |  |
| 60 | "Every message ends with a `sig` field holding…" | pre-release | flows |  |
| 61 | "`reply_to`: optional." | pre-release | flows |  |
| 62 | "When present and a valid single address, the…" | pre-release | flows |  |
| 63 | "It lives *inside the signed body*, so only…" | pre-release | flows |  |
| 64 | "Unsigned or invalid jobs never trigger a reply…" | pre-release | flows |  |
| 65 | "Omit it and results behave as before (the…" | pre-release | flows |  |
| 66 | "`aud`: optional audience claim (`runner_id` is accepted as…" | pre-release | flows |  |
| 67 | "When the runner's config sets `runner_id` and the…" | pre-release | flows |  |
| 68 | "With the feature off (default), the field is…" | pre-release | flows |  |
| 69 | "Every message type (job, query, task_*, sensor_alert) may…" | pre-release | flows |  |
| 70 | "A **fresh config** — one created by the…" | pre-release | flows |  |
| 71 | "`oracle_opinion`: optional; one of `off`, `diagnose`, `advise`, `repair`." | pre-release | flows |  |
| 72 | "The latitude the sender requests for the Oracle's…" | pre-release | flows |  |
| 73 | "The runner's `oracle_opinion_mode` config is both the default…" | pre-release | flows |  |
| 74 | "An unrecognized value is ignored, as if the…" | pre-release | flows |  |
| 75 | "Runners that do not implement the opinion ignore…" | pre-release | flows |  |
| 76 | "`result_policy`: optional; the disclosure policy the result is…" | pre-release | flows |  |
| 77 | "`key_id`: optional; names which shared secret verifies this…" | pre-release | flows |  |
| 78 | "Absent means the default secret." | pre-release | flows |  |
| 79 | "Every secret has a name a sender can…" | pre-release | flows |  |
| 80 | "`kind`: `exec` or `ping`; `recipe` (the owner's named…" | pre-release | flows |  |
| 81 | "A `ping` job carries no script; the runner…" | pre-release | flows |  |
| 82 | "For `exec`, at least one of `script` /…" | pre-release | flows |  |
| 83 | "A job carrying both is accepted and `script_url`…" | pre-release | flows |  |
| 84 | "`timeout_sec`: default the runner's `default_timeout_sec` (300); a value…" | pre-release | flows |  |
| 85 | "`interpreter`: optional list whose first element is the…" | pre-release | flows |  |
| 86 | "`["pwsh", "-File"]` or `["bash"]`." | pre-release | flows |  |
| 87 | "The script is written into the workdir under…" | pre-release | flows |  |
| 88 | "If absent, the runner's `default_interpreter` config applies, else…" | pre-release | flows |  |
| 89 | "Unknown fields must be ignored (forward compatibility)." | pre-release | flows |  |
| 90 | "`platform`: OPTIONAL, and only on the result to…" | pre-release | flows |  |
| 91 | "The platform card: what the box says about…" | pre-release | flows |  |
| 92 | "Receivers MUST ignore it if they do not…" | pre-release | flows |  |
| 93 | "At `family` it is `{"disclosure": "family", "os_family": "windows"|"macos"|…" | pre-release | flows |  |
| 94 | "`standard` adds `os_release`, `python_version`, and `runner_version`; `full` adds…" | pre-release | flows |  |
| 95 | "`none` sends the bare pong." | pre-release | flows |  |
| 96 | "The tier is the owner's ceiling: no job…" | pre-release | flows |  |
| 97 | "The card leaves only in a result, which…" | pre-release | flows |  |
| 98 | "The DTLS greeting (draft Section 20) carries the…" | pre-release | flows |  |
| 99 | "`protocol_versions` is also how a sender discovers that…" | pre-release | flows |  |
| 100 | "`key_ids` (every tier that sends a card) lists…" | pre-release | flows |  |
| 101 | "It is the identity hint of a TLS-PSK…" | pre-release | flows |  |
| 102 | "`env_fingerprint`: OPTIONAL." | pre-release | flows |  |
| 103 | "`e-` and 24 lowercase hex digits, carried on…" | pre-release | flows |  |
| 104 | "It is the first 96 bits of HMAC-SHA-384,…" | pre-release | flows |  |
| 105 | "Two results with the same value ran on…" | pre-release | flows |  |
| 106 | "The view does not shape it, since it…" | pre-release | flows |  |
| 107 | "A runner reinstalled with a new salt reads…" | pre-release | flows |  |
| 108 | "`result_seq` and `prev_result_sha384`: the result chain." | pre-release | flows |  |
| 109 | "Every result the runner signs carries `result_seq`, one…" | pre-release | flows |  |
| 110 | "A receiver that keeps the chain proves it…" | pre-release | flows |  |
| 111 | "The chain is per key, so no key…" | pre-release | flows |  |
| 112 | "A link is recorded once its result is…" | pre-release | flows |  |
| 113 | "A delivery stub (section 15) keeps the `result_seq`…" | pre-release | flows |  |
| 114 | "The owner turns the chain off with `result_chain:…" | pre-release | flows |  |
| 115 | "`send_job.py verify --chain FILE` keeps the receiver's side…" | pre-release | flows |  |
| 116 | "`key_id`: the name of the key that verified…" | pre-release | flows |  |
| 117 | "A name, never a value." | pre-release | flows |  |
| 118 | "It says which key signed what, and it…" | pre-release | flows |  |
| 119 | "Every result carries it, the rejection result (`exit_code`…" | pre-release | flows |  |
| 120 | "`timed_out: true` implies the process tree was killed;…" | pre-release | flows |  |
| 121 | "`exit_code` -2 means the job was rejected before…" | pre-release | flows |  |
| 122 | "Rejected jobs do not retry — the mail…" | pre-release | flows |  |
| 123 | "`outputs[]`: present when the job named `outputs` (section…" | pre-release | flows |  |
| 124 | "`answers[]` / `attestations[]`: `answers` is present when the…" | pre-release | flows |  |
| 125 | "`stdout`/`stderr` are truncated at a configurable limit on…" | pre-release | flows |  |
| 126 | "The whole body is held under `max_result_bytes` (default…" | pre-release | flows |  |
| 127 | "[N characters dropped to fit max_result_bytes] ...` marker…" | pre-release | flows |  |
| 128 | "The signature always covers what is sent." | pre-release | flows |  |
| 129 | "`delivery_note`: OPTIONAL." | pre-release | flows |  |
| 130 | "Present only on a stub sent in place…" | pre-release | flows |  |
| 131 | "It is signed and encrypted like any result." | pre-release | flows |  |
| 132 | "A 4xx, a socket or a TLS error…" | pre-release | flows |  |
| 133 | "`oracle_opinion`: OPTIONAL." | pre-release | flows |  |
| 134 | "The Oracle's opinion of the job, formed on…" | pre-release | flows |  |
| 135 | "It is advisory: it never blocks, holds, or…" | pre-release | flows |  |
| 136 | "The member is absent entirely when the effective…" | pre-release | flows |  |
| 137 | "When present it is an object with these…" | pre-release | flows |  |
| 138 | "`mode`: the effective latitude the opinion was formed…" | pre-release | flows |  |
| 139 | "`verdict`: `likely_success` (a prediction that the environment fits…" | pre-release | flows |  |
| 140 | "`note`: a short human-readable statement of the basis,…" | pre-release | flows |  |
| 141 | "Text formed by the runner's local model, when…" | pre-release | flows |  |
| 142 | "`repaired`: present only at `repair` latitude when a…" | pre-release | flows |  |
| 143 | "`received_digest`: present whenever `repaired` is present." | pre-release | flows |  |
| 144 | "The SHA-384 hex digest of the job as…" | pre-release | flows |  |
| 145 | "At `diagnose` latitude the member appears only on…" | pre-release | flows |  |
| 146 | "At `advise` latitude a prediction computed before the…" | pre-release | flows |  |
| 147 | "At `repair` latitude the runner MAY correct the…" | pre-release | flows |  |
| 148 | "`remediation`: OPTIONAL." | pre-release | flows |  |
| 149 | "Present only when remediation acted on the job…" | pre-release | flows |  |
| 150 | "Receivers MUST ignore it if they do not…" | pre-release | flows |  |
| 151 | "When present it is an object with these…" | pre-release | flows |  |
| 152 | "`mode`: the runner's `remediation_mode` the act was taken…" | pre-release | flows |  |
| 153 | "`authority`: `tripwire` (a deterministic tripwire from the closed…" | pre-release | flows |  |
| 154 | "`divergence`: a short string naming what was observed…" | pre-release | flows |  |
| 155 | "`act`: `killed` (the job's process tree was killed)…" | pre-release | flows |  |
| 156 | "Referral of suspect files to the box's antivirus…" | pre-release | flows |  |
| 157 | "`av_verdict`: the antivirus's own verdict on the referred…" | pre-release | flows |  |
| 158 | "Unavailable is a fact, not an error." | pre-release | flows |  |
| 159 | "`received_digest`: the SHA-384 hex digest of the job…" | pre-release | flows |  |
| 160 | "Remediation is owner configuration only: a job member…" | pre-release | flows |  |
| 161 | "A recipe is a script the runner owner…" | pre-release | flows |  |
| 162 | "A job names one: `{"kind": "recipe", "recipe": "tests",…" | pre-release | flows |  |
| 163 | "The runner runs the owner's `script` under the…" | pre-release | flows |  |
| 164 | "A recipe job may carry `files` and `outputs`…" | pre-release | flows |  |
| 165 | "It MUST NOT carry `script`, `script_url`, `script_sha384`, `interpreter`…" | pre-release | flows |  |
| 166 | "Each argument must fully match `args_pattern` and be…" | pre-release | flows |  |
| 167 | "The runner refuses to start with a recipe…" | pre-release | flows |  |
| 168 | "A key policy's `allowed_recipes` (section 14.1) names the…" | pre-release | flows |  |
| 169 | "A sender stops a job it sent with…" | pre-release | flows |  |
| 170 | "It is signed, sealed under the job id…" | pre-release | flows |  |
| 171 | "The deny flag holds at this door; `allowed_kinds`…" | pre-release | flows |  |
| 172 | "A job running on the runner is killed…" | pre-release | flows |  |
| 173 | "Its result carries `cancelled: true`, `exit_code` -1 and…" | pre-release | flows |  |
| 174 | "A job the runner has not seen is…" | pre-release | flows |  |
| 175 | "The runner keeps the cancel that long and…" | pre-release | flows |  |
| 176 | "A finished job is left as it is." | pre-release | flows |  |
| 177 | "The runner answers with a signed (and, as…" | pre-release | flows |  |
| 178 | "Another key's job, whether running, done or unseen,…" | pre-release | flows |  |
| 179 | "The reference runner serves a transport's messages one…" | pre-release | flows |  |
| 180 | "`send_job.py cancel --job-id ID` builds the message." | pre-release | flows |  |
| 181 | "A change is the loop of checking out…" | pre-release | flows |  |
| 182 | "`repo` names an entry of the owner's `change_repos`…" | pre-release | flows |  |
| 183 | "The runner clones that repository into the job's…" | pre-release | flows |  |
| 184 | "The job carries no script, interpreter or environment,…" | pre-release | flows |  |
| 185 | "The result carries `change: {"repo": ..., "commit": <the…" | pre-release | flows |  |
| 186 | "The job's own `outputs` name files under `src/`…" | pre-release | flows |  |
| 187 | "A runner without git, a repository that does…" | pre-release | flows |  |
| 188 | "A key policy's `allowed_recipes` binds the recipe a…" | pre-release | flows |  |
| 189 | "`send_job.py new --kind change --repo NAME --commit REF…" | pre-release | flows |  |
| 190 | "Appending the signature last avoids cross-language JSON canonicalization…" | pre-release | flows |  |
| 191 | "Serialize the payload as a JSON object **without**…" | pre-release | flows |  |
| 192 | "Normalize line endings to LF (`\r\n` → `\n`,…" | pre-release | flows |  |
| 193 | "`sig = HEX(HMAC_SHA384(secret, normalized_payload))`." | pre-release | flows |  |
| 194 | "Body = payload with the trailing `}` replaced…" | pre-release | flows |  |
| 195 | "Verification:" | pre-release | flows |  |
| 196 | "Normalize line endings to LF." | pre-release | flows |  |
| 197 | "Find the **last** occurrence of `,"sig":"`." | pre-release | flows |  |
| 198 | "The 96 characters after it must be hex…" | pre-release | flows |  |
| 199 | "Text after that `"}` (a trailer) is ignored." | pre-release | flows |  |
| 200 | "`raw` = the text from the `{` that…" | pre-release | flows |  |
| 201 | "Text before that `{` is not signed." | pre-release | flows |  |
| 202 | "Recompute `HEX(HMAC_SHA384(secret, raw))` and compare with the presented…" | pre-release | flows |  |
| 203 | "If that does not match, form `raw'` by…" | pre-release | flows |  |
| 204 | "This is the second signed form: a mail…" | pre-release | flows |  |
| 205 | "A receiver MUST compare the second form in…" | pre-release | flows |  |
| 206 | "The shared secret is a dedicated high-entropy string…" | pre-release | flows |  |
| 207 | "Both sides use its UTF-8 bytes directly as…" | pre-release | flows |  |
| 208 | "The user gives the same string to the…" | pre-release | flows |  |
| 209 | "It never travels in email; only job signatures…" | pre-release | flows |  |
| 210 | "The runner refuses to start if the secret…" | pre-release | flows |  |
| 211 | "Two kinds of checks run, and the order…" | pre-release | flows |  |
| 212 | "Routing checks run first, on the unauthenticated message:…" | pre-release | flows |  |
| 213 | "These checks route and deduplicate; they authorize nothing,…" | pre-release | flows |  |
| 214 | "Everything that runs on the unauthenticated message, the…" | pre-release | flows |  |
| 215 | "Two senses of *seen* are kept apart throughout:…" | pre-release | flows |  |
| 216 | "Where a later section says a message is…" | pre-release | flows |  |
| 217 | "Nothing is executed, answered, or acted on before…" | pre-release | flows |  |
| 218 | "Authorization then runs in this order, and all…" | pre-release | flows |  |
| 219 | "**Signature valid:** the body HMAC-SHA-384 must verify against…" | pre-release | flows |  |
| 220 | "This is the sole authentication gate." | pre-release | flows |  |
| 221 | "The `From` address is not validated — any…" | pre-release | flows |  |
| 222 | "The sender address is logged for audit but…" | pre-release | flows |  |
| 223 | "**Audience binding** (when `security.modes.audience` is not `off` and…" | pre-release | flows |  |
| 224 | "The expected value always comes from the config…" | pre-release | flows |  |
| 225 | "Applies to jobs, queries (including the `ask` op),…" | pre-release | flows |  |
| 226 | "The signed script is bounded by `max_script_bytes`." | pre-release | flows |  |
| 227 | "`v` is the JSON integer 1 (checked once…" | pre-release | flows |  |
| 228 | "JSON `true` and `1.0` compare equal to 1…" | pre-release | flows |  |
| 229 | "`type` is the message type the subject announces;…" | pre-release | flows |  |
| 230 | "`issued_at` parses, carries a timezone, is no older…" | pre-release | flows |  |
| 231 | "*(Seen-set.)* The `job_id` seen-set lookup is a routing…" | pre-release | flows |  |
| 232 | "It is listed here only so the replay…" | pre-release | flows |  |
| 233 | "The seen-set key is namespaced by `runner_id` when…" | pre-release | flows |  |
| 234 | "An entry is kept for as long as…" | pre-release | flows |  |
| 235 | "It is never dropped earlier to make room." | pre-release | flows |  |
| 236 | "**Job-shape validation** (job messages): `kind` is `exec`, `ping`,…" | pre-release | flows |  |
| 237 | "Failures here produce the -2 rejection result of…" | pre-release | flows |  |
| 238 | "Two more gates sit in that order: a…" | pre-release | flows |  |
| 239 | "A query, a board message and a version…" | pre-release | flows |  |
| 240 | "Failures are logged, the mail is marked seen,…" | pre-release | flows |  |
| 241 | "Delivery is a separate, retryable concern: a send…" | pre-release | flows |  |
| 242 | "A delivered record moves to `<base_dir>/sent/`, where a…" | pre-release | flows |  |
| 243 | "The one window left is the stash write…" | pre-release | flows |  |
| 244 | "`--inspect outbox` lists the waiting and the given-up…" | pre-release | flows |  |
| 245 | "On a file channel the same rule is…" | pre-release | flows |  |
| 246 | "That move happens only when the core would…" | pre-release | flows |  |
| 247 | "A retryable failure leaves the envelope in the…" | pre-release | flows |  |
| 248 | "A rejection is still consumed, so poison is…" | pre-release | flows |  |
| 249 | "The limits this section names come from `config.json`,…" | pre-release | flows |  |
| 250 | "A setting that is present but not usable…" | pre-release | flows |  |
| 251 | "Working directory: `<base_dir>/work/<job_id>/`, created fresh per job." | pre-release | flows |  |
| 252 | "`files[]` are downloaded over HTTPS into the work…" | pre-release | flows |  |
| 253 | "`name` is a relative path under it, checked…" | pre-release | flows |  |
| 254 | "The rejection names the rule." | pre-release | flows |  |
| 255 | "A nested name (`data/in.csv`) has its directories made…" | pre-release | flows |  |
| 256 | "`sha384` is verified when present." | pre-release | flows |  |
| 257 | "A `files[]` entry carries exactly one source: `url`…" | pre-release | flows |  |
| 258 | "An inline file is covered by the job's…" | pre-release | flows |  |
| 259 | "A name staged twice is refused." | pre-release | flows |  |
| 260 | "This is how a sender carries a patch…" | pre-release | flows |  |
| 261 | "`outputs` (optional): up to 8 distinct names, by…" | pre-release | flows |  |
| 262 | "A file is read only if its real…" | pre-release | flows |  |
| 263 | "Each `outputs[]` entry in the result names the…" | pre-release | flows |  |
| 264 | "What of it leaves the box is the…" | pre-release | flows |  |
| 265 | "`send_job.py verify --outputs-dir DIR` writes the files out,…" | pre-release | flows |  |
| 266 | "The script runs as `<interpreter...> script <args...>` (see…" | pre-release | flows |  |
| 267 | "On timeout the whole process tree is killed…" | pre-release | flows |  |
| 268 | "**A job runs at most once per `job_id`…" | pre-release | flows |  |
| 269 | "Idempotent jobs are still good hygiene -- check…" | pre-release | flows |  |
| 270 | "The runner host is a **full-trust execution environment**:…" | pre-release | flows |  |
| 271 | "This deployment deliberately stores the mailbox app password…" | pre-release | flows |  |
| 272 | "Anyone holding the password gets mailbox access —…" | pre-release | flows |  |
| 273 | "Do not use this setup with an account…" | pre-release | flows |  |
| 274 | "Same caution applies.)" | pre-release | flows |  |
| 275 | "Use a dedicated mailbox, never a personal inbox." | pre-release | flows |  |
| 276 | "Use an app password, never the account password." | pre-release | flows |  |
| 277 | "Recommended deployment: run the runner inside a Linux…" | pre-release | flows |  |
| 278 | "VM snapshots give instant rollback, and the guest…" | pre-release | flows |  |
| 279 | "IMAP/SMTP over TLS (993/587)." | pre-release | flows |  |
| 280 | "File downloads over HTTPS only." | pre-release | flows |  |
| 281 | "Work that is not built is listed in…" | pre-release | flows |  |
| 282 | "Result policies are specified below." | pre-release | flows |  |
| 283 | "The object protocol uses three cryptographic primitives:" | pre-release | flows |  |
| 284 | "**Message authentication:** HMAC-SHA-384, keyed with the shared secret." | pre-release | flows |  |
| 285 | "This is the protocol's authentication mechanism; sender identity…" | pre-release | flows |  |
| 286 | "**Hashing:** SHA-384, used for file and script integrity…" | pre-release | flows |  |
| 287 | "**Payload encryption:** AES-256-GCM (AEAD), keyed per message by…" | pre-release | flows |  |
| 288 | "A signed body SHOULD be sent as an…" | pre-release | flows |  |
| 289 | "The associated data is the subject's identifier (the…" | pre-release | flows |  |
| 290 | "The key id there is `""` for the…" | pre-release | flows |  |
| 291 | "A receiver MUST accept the encrypted form, and…" | pre-release | flows |  |
| 292 | "The reference receiver applies that same refusal to…" | pre-release | flows |  |
| 293 | "A result mirrors the form of the job…" | pre-release | flows |  |
| 294 | "A real job/result pair in this form, as…" | pre-release | flows |  |
| 295 | "The DTLS binding adds one more construction, and…" | pre-release | flows |  |
| 296 | "It is not part of the object protocol." | pre-release | flows |  |
| 297 | "`psk_ke` is forbidden." | pre-release | flows |  |
| 298 | "These are the CNSA-listed choices: the 384-bit tier…" | pre-release | flows |  |
| 299 | "Confidentiality is a property of the signed object,…" | pre-release | flows |  |
| 300 | "The reference senders encrypt by default, and the…" | pre-release | flows |  |
| 301 | "On the email binding a cleartext job is…" | pre-release | flows |  |
| 302 | "TLS protects the hop and does not hide…" | pre-release | flows |  |
| 303 | "Authenticity and integrity come from HMAC-SHA-384 in both…" | pre-release | flows |  |
| 304 | "The reference tools encrypt unless a flag says…" | pre-release | flows |  |
| 305 | "`send_job.py --cleartext` and `send_dtls.py --cleartext` send the HMAC-signed…" | pre-release | flows |  |
| 306 | "The runner refuses that body unless it was…" | pre-release | flows |  |
| 307 | "The shared secret is required either way: the…" | pre-release | flows |  |
| 308 | "There is no config key for this." | pre-release | flows |  |
| 309 | "The protocol version stays 1." | pre-release | flows |  |
| 310 | "---" | pre-release | flagged | A standalone horizontal-rule line — structure standing where a sentence should be |
| 311 | "**Paradigm: the runner as the Oracle.** Without a…" | pre-release | flows |  |
| 312 | "The Oracle inverts this: the runner keeps the…" | pre-release | flows |  |
| 313 | "The SI learns predicates about the output —…" | pre-release | flows |  |
| 314 | "This is the interactive-proof shape applied at the…" | pre-release | flows |  |
| 315 | "The **Oracle** is a local agent: instructions plus…" | pre-release | flows |  |
| 316 | "It has four duties, three across a job's…" | pre-release | flows |  |
| 317 | "**Before execution — judgment** (section 9.3): read the…" | pre-release | flows |  |
| 318 | "**During execution — confinement** (section 9.4): bound what…" | pre-release | flows |  |
| 319 | "**After execution — reporting** (sections 9, 10): enforce…" | pre-release | flows |  |
| 320 | "**Before jobs exist — dispatch** (section 13): hold…" | pre-release | flows |  |
| 321 | "The Oracle adds a second direction without removing…" | pre-release | flows |  |
| 322 | "The SI pushes jobs to the runner, and…" | pre-release | flows |  |
| 323 | "The Oracle can also run the other way:…" | pre-release | flows |  |
| 324 | "Push and pull coexist; a deployment uses either…" | pre-release | flows |  |
| 325 | "It is governed by runner-owner flags." | pre-release | flows |  |
| 326 | "They are config-only, never job fields — no…" | pre-release | flows |  |
| 327 | "Section 13 adds dispatch-specific flags under the same…" | pre-release | flows |  |
| 328 | "The Oracle is unconditional: there is no flag…" | pre-release | flows |  |
| 329 | "`result_policy` is always honored, results are shaped by…" | pre-release | flows |  |
| 330 | "The job gains an optional `result_policy` object:" | pre-release | flows |  |
| 331 | "`view`: one of `full` (stdout and stderr), `redacted`,…" | pre-release | flows |  |
| 332 | "Default: `full` (backward compatible)." | pre-release | flows |  |
| 333 | "`redact_patterns`: reserved." | pre-release | flows |  |
| 334 | "In `redacted` view the runner applies every family…" | pre-release | flows |  |
| 335 | "`queries`: **all** questions the SI will ever ask…" | pre-release | flows |  |
| 336 | "This is what makes the exchange non-interactive." | pre-release | flows |  |
| 337 | "`query_budget`: maximum queries answerable for this job (default…" | pre-release | flows |  |
| 338 | "The runner owner's config caps it with `max_query_budget`…" | pre-release | flows |  |
| 339 | "Bounds total leakage — and doubles as a…" | pre-release | flows |  |
| 340 | "**The ceiling is set by the runner owner,…" | pre-release | flows |  |
| 341 | "The effective view is the *narrower* of the…" | pre-release | flows |  |
| 342 | "This is the load-bearing privacy property: the SI…" | pre-release | flows |  |
| 343 | "`full`: stdout and stderr, as in section 3.2." | pre-release | flows |  |
| 344 | "`redacted`: the output with every `redact_patterns` match replaced…" | pre-release | flows |  |
| 345 | "The runner scans stdout and stderr as one…" | pre-release | flows |  |
| 346 | "Like every non-`full` view it carries `output_digest` (section…" | pre-release | flows |  |
| 347 | "`summary`: no raw output." | pre-release | flows |  |
| 348 | "Contains `exit_code`, `timed_out`, `duration_sec`, `stdout_bytes`, `stderr_bytes` (the UTF-8…" | pre-release | flows |  |
| 349 | "`attested`: the common members (`exit_code`, `timed_out`, `duration_sec`, `output_digest`),…" | pre-release | flows |  |
| 350 | "No output bytes cross the boundary at all.…" | pre-release | flows |  |
| 351 | "Members the owner's configuration adds, such as `judgment`,…" | pre-release | flows |  |
| 352 | "Every view keeps the result's identity members (`v`,…" | pre-release | flows |  |
| 353 | "Built-in predicates (a fixed set; an unknown predicate…" | pre-release | flows |  |
| 354 | "`exit_zero`: `exit_code == 0`." | pre-release | flows |  |
| 355 | "`no_secrets`: the retained output was scanned against the…" | pre-release | flows |  |
| 356 | "`patterns_sha384` binds *which* pattern set ran, so the…" | pre-release | flows |  |
| 357 | "`output_digest`: SHA-384 of the retained output (each stream…" | pre-release | flows |  |
| 358 | "This is a **commitment**: the SI can't see…" | pre-release | flows |  |
| 359 | "`confined_to_workspace`: the job created or modified no file…" | pre-release | flows |  |
| 360 | "Only meaningful when confinement is configured; otherwise the…" | pre-release | flows |  |
| 361 | "Each attestation is covered by the message HMAC…" | pre-release | flows |  |
| 362 | "Before anything runs, the Oracle reads the job…" | pre-release | flows |  |
| 363 | "The verdict is deterministic: checks against the job…" | pre-release | flows |  |
| 364 | "No model participates in it, whether or not…" | pre-release | flows |  |
| 365 | "*A semantic verdict — a model-backed reading such…" | pre-release | flows |  |
| 366 | "It is not shipped and not planned. (The…" | pre-release | flows |  |
| 367 | "A verdict is a judgment, not a proof." | pre-release | flows |  |
| 368 | "It can miss malicious code and flag benign…" | pre-release | flows |  |
| 369 | "No job field can soften or disable judgment:" | pre-release | flows |  |
| 370 | "`judge`: `off`, `advisory` (verdict attached to the result,…" | pre-release | flows |  |
| 371 | "This is a tripwire, not a review." | pre-release | flows |  |
| 372 | "It matches a short denylist (`rm -rf /`,…" | pre-release | flows |  |
| 373 | "It does not weigh the job." | pre-release | flows |  |
| 374 | "During execution, the Oracle reports what a job…" | pre-release | flows |  |
| 375 | "The snapshot below does not stop a write." | pre-release | flows |  |
| 376 | "An optional Linux sandbox does." | pre-release | flows |  |
| 377 | "Config for the snapshot:" | pre-release | flows |  |
| 378 | "`workspace_root`: absolute path (e.g." | pre-release | flows |  |
| 379 | "`/home/user/workspace`)." | pre-release | flows |  |
| 380 | "When set, it names the root the confinement…" | pre-release | flows |  |
| 381 | "The job's working directory is always `<base_dir>/work/<job_id>`; the…" | pre-release | flows |  |
| 382 | "The walk stops at 50000 files and logs…" | pre-release | flows |  |
| 383 | "The job's own working tree never counts against…" | pre-release | flows |  |
| 384 | "The snapshot is a record, not a cage." | pre-release | flows |  |
| 385 | "`confined_to_workspace` means no file outside `workspace_root`, within its…" | pre-release | flows |  |
| 386 | "Best-effort: a write that was reverted before the…" | pre-release | flows |  |
| 387 | "OS containment is a separate switch, `security.modes.confinement`, at…" | pre-release | flows |  |
| 388 | "On Linux with `bwrap` installed the job runs…" | pre-release | flows |  |
| 389 | "At startup, a sandbox that cannot engage (no…" | pre-release | flows |  |
| 390 | "`audit` mode runs normally and records `would_run_sandboxed`." | pre-release | flows |  |
| 391 | "See SECURITY.md." | pre-release | flagged | A bare cross-reference ("See SECURITY.md.") standing as its own unit in the prose — a pointer, not a sentence |
| 392 | "The attestation format does not change when the…" | pre-release | flows |  |
| 393 | "Like everything the Oracle does, the ceiling is…" | pre-release | flows |  |
| 394 | "The job's work directory is the one place…" | pre-release | flows |  |
| 395 | "Its real path is resolved once per job…" | pre-release | flows |  |
| 396 | "A download lands in a temp name beside…" | pre-release | flows |  |
| 397 | "On Linux the sandbox binds that real path,…" | pre-release | flows |  |
| 398 | "On Windows there is no sandbox: these checks…" | pre-release | flows |  |
| 399 | "`protected_paths` is an optional list of absolute paths…" | pre-release | flows |  |
| 400 | "Paths listed here are checked first; any creation,…" | pre-release | flows |  |
| 401 | "They are compared against the same snapshot, so…" | pre-release | flows |  |
| 402 | "Default is an empty list (least restrictive)." | pre-release | flows |  |
| 403 | "Two phases: first the SI declares *what may…" | pre-release | flows |  |
| 404 | "The message count is fixed — neither party…" | pre-release | flows |  |
| 405 | "**Phase 1 — negotiation (the job).** The SI…" | pre-release | flows |  |
| 406 | "The runner intersects each query with the owner's…" | pre-release | flows |  |
| 407 | "**Phase 2 — delivery (the result).** The result…" | pre-release | flows |  |
| 408 | "Query ops: `attest` (evaluate a named predicate now),…" | pre-release | flows |  |
| 409 | "Answers obey the job's effective view exactly as…" | pre-release | flows |  |
| 410 | "A `grep` pattern that does not compile is…" | pre-release | flows |  |
| 411 | "So is one whose shape can take exponential…" | pre-release | flows |  |
| 412 | "A pattern the shape check cannot name still…" | pre-release | flows |  |
| 413 | "The next query starts the worker again." | pre-release | flows |  |
| 414 | "Either way the query spends its one." | pre-release | flows |  |
| 415 | "When the runner has a local model, the…" | pre-release | flows |  |
| 416 | "Raw data never leaves the machine, but answers…" | pre-release | flows |  |
| 417 | "Config (all under an `inference` object; disabled unless…" | pre-release | flows |  |
| 418 | "`endpoint`: OpenAI-compatible HTTP API (e.g." | pre-release | flows |  |
| 419 | "`http://localhost:11434/v1`). **Must resolve to loopback** — the Oracle…" | pre-release | flows |  |
| 420 | "`model`: model id, e.g." | pre-release | flows |  |
| 421 | "`"qwen3:1.7b"`." | pre-release | flows |  |
| 422 | "`max_answer_chars` (default 2000), `timeout_sec` (default 180)." | pre-release | flows |  |
| 423 | "**Reference stack.** `qwen3:1.7b` served on loopback via Ollama…" | pre-release | flows |  |
| 424 | "Any OpenAI-compatible server bound to loopback works —…" | pre-release | flows |  |
| 425 | "The Oracle refuses non-loopback endpoints." | pre-release | flows |  |
| 426 | "Another local agent may share the same model…" | pre-release | flows |  |
| 427 | "The `ask` op is declared upfront in `queries[]`…" | pre-release | flows |  |
| 428 | "The Oracle prompts the model with a constrained…" | pre-release | flows |  |
| 429 | "Truncate to `max_chars`." | pre-release | flows |  |
| 430 | "Secret-scan the truncated answer, including fragment matches against…" | pre-release | flows |  |
| 431 | "Scanning runs before redaction so that a leaked…" | pre-release | flows |  |
| 432 | "Redact via the section-9 engine (same secret patterns…" | pre-release | flows |  |
| 433 | "Secret-scan again on the redacted text; a hit…" | pre-release | flows |  |
| 434 | "The delivered answer carries `{"op": "ask", "answer": "...",…" | pre-release | flows |  |
| 435 | "**Threat: indirect prompt injection.** Adversarial job output can…" | pre-release | flows |  |
| 436 | "The pipeline above is the defense: narrow role,…" | pre-release | flows |  |
| 437 | "The `query` (`[HOMING-PIGEON] query <query_id>`) and `qresult` message…" | pre-release | flows |  |
| 438 | "Every one passes the section-5 verification (signature, freshness,…" | pre-release | flows |  |
| 439 | "Outputs are retained per `output_retention_days` (runner config, default…" | pre-release | flows |  |
| 440 | "A query refused as a whole is answered…" | pre-release | flows |  |
| 441 | "None of these spends budget." | pre-release | flows |  |
| 442 | "They fall in two groups, by whether the…" | pre-release | flows |  |
| 443 | "Refused before the record is read." | pre-release | flows |  |
| 444 | "The reply names no job and takes no…" | pre-release | flows |  |
| 445 | "`unsupported`: `v` or `type` is not a query's." | pre-release | flows |  |
| 446 | "`policy`: the key's door policy (section 14.1) does…" | pre-release | flows |  |
| 447 | "`rate_limit`: the sender's key is over its hourly…" | pre-release | flows |  |
| 448 | "Refused once the record is looked up." | pre-release | flows |  |
| 449 | "The reply carries the query's `job_id` and `budget_remaining`…" | pre-release | flows |  |
| 450 | "`unknown_job`: no retained record for the `job_id`, or…" | pre-release | flows |  |
| 451 | "`expired`: the record is past `output_retention_days`." | pre-release | flows |  |
| 452 | "Only the record's owner ever sees it; any…" | pre-release | flows |  |
| 453 | "`query_error`: the record could not be read." | pre-release | flows |  |
| 454 | "An answered `qresult` carries the query's `job_id` as…" | pre-release | flows |  |
| 455 | "A stale query, one that fails its signature,…" | pre-release | flows |  |
| 456 | "**Threat: adaptive chosen-query extraction.** Each answer leaks a…" | pre-release | flows |  |
| 457 | "A verifier that chooses each query *after seeing…" | pre-release | flows |  |
| 458 | "Defenses, in order of importance:" | pre-release | flows |  |
| 459 | "**Non-interactivity (the ZKP lesson).** The two-phase exchange removes…" | pre-release | flows |  |
| 460 | "Zero-knowledge proofs went non-interactive (SNARKs/STARKs) for the same…" | pre-release | flows |  |
| 461 | "**Privacy budget.** `query_budget` bounds *total* leakage per job." | pre-release | flows |  |
| 462 | "Accounting is per job: the spend is kept…" | pre-release | flows |  |
| 463 | "A budget bounds what rate limiting cannot: the…" | pre-release | flows |  |
| 464 | "The budget is also an operational tripwire, not…" | pre-release | flows |  |
| 465 | "A well-formed job answers its questions in one…" | pre-release | flows |  |
| 466 | "A job that burns through all 8 is…" | pre-release | flows |  |
| 467 | "Budget exhaustion always deserves a human look —…" | pre-release | flows |  |
| 468 | "**Rate limiting.** Before committing expensive work, demand proof…" | pre-release | flows |  |
| 469 | "This slows automated probing; the budget is what…" | pre-release | flows |  |
| 470 | "The Oracle's machinery reads as security tooling, but…" | pre-release | flows |  |
| 471 | "A developer hitting their first failed job gets:" | pre-release | flows |  |
| 472 | "**Judgment (§9.3):** "this job doesn't do what its…" | pre-release | flows |  |
| 473 | "Catches the wrong-script, wrong-arguments class of mistakes at…" | pre-release | flows |  |
| 474 | "**Confinement attestation (§9.4):** "did this job touch anything…" | pre-release | flows |  |
| 475 | "**Attestations (§9.2):** signed claims — exit code, no…" | pre-release | flows |  |
| 476 | "When the SI says "it worked," the attestation…" | pre-release | flows |  |
| 477 | "**Budget exhaustion (§11):** "this job needed 8 questions…" | pre-release | flows |  |
| 478 | "**`ask` (§10.1):** "why did the tests fail?" —…" | pre-release | flows |  |
| 479 | "None of this replaces reading the output." | pre-release | flows |  |
| 480 | "It tells you *where to look* — which,…" | pre-release | flows |  |
| 481 | "**Non-escalation:** neither the job's `result_policy` nor any query…" | pre-release | flows |  |
| 482 | "**Commitment binding:** `output_digest` in every non-`full` view ties…" | pre-release | flows |  |
| 483 | "**Bounded extraction:** single-round declaration + privacy budget +…" | pre-release | flows |  |
| 484 | "**Same transport trust as any other message:** queries…" | pre-release | flows |  |
| 485 | "**Data lifetime:** retained outputs age out per config;…" | pre-release | flows |  |
| 486 | "**Worker authentication:** task requests and results are HMAC-signed…" | pre-release | flows |  |
| 487 | "Without it, a third party can neither pull…" | pre-release | flows |  |
| 488 | "**Compartmentalization is opt-in:** by default a pulling worker…" | pre-release | flows |  |
| 489 | "Restriction is configuration (section 13.3), never the default." | pre-release | flows |  |
| 490 | "**Review is the correctness anchor:** attestations bind workers…" | pre-release | flows |  |
| 491 | "**Extension sources follow a disclosure rule:** the code…" | pre-release | flows |  |
| 492 | "Withheld material is never named in the Oracle's…" | pre-release | flows |  |
| 493 | "The material is fetched on the box only…" | pre-release | flows |  |
| 494 | "The rule, the declaration format, and the owner's…" | pre-release | flows |  |
| 495 | "This section adds a direction; it removes none." | pre-release | flows |  |
| 496 | "A signed job still pushes, the runner still…" | pre-release | flows |  |
| 497 | "Identical wire behavior, identical auth." | pre-release | flows |  |
| 498 | "The Oracle, dispatch included, is purely additive." | pre-release | flows |  |
| 499 | "It can additionally deal tasks from its board…" | pre-release | flows |  |
| 500 | "The default posture is least restrictive, like everything…" | pre-release | flows |  |
| 501 | "Any holder of the shared secret can pull…" | pre-release | flows |  |
| 502 | "Restrictions are configuration for owners who want them,…" | pre-release | flows |  |
| 503 | "The disclaimers below say what that choice costs." | pre-release | flows |  |
| 504 | "A task is a job the Oracle has…" | pre-release | flows |  |
| 505 | "`task_id`: the same grammar as `job_id` (section 2)." | pre-release | flows |  |
| 506 | "A UUID is recommended, not required." | pre-release | flows |  |
| 507 | "`requires[]`: task IDs that should complete first." | pre-release | flows |  |
| 508 | "A DAG, not a flat queue." | pre-release | flows |  |
| 509 | "`capabilities[]`: free-form tags (`code`, `review`, `prose`) describing what…" | pre-release | flows |  |
| 510 | "Workers claim capabilities when they pull; a worker…" | pre-release | flows |  |
| 511 | "`priority`: higher first." | pre-release | flows |  |
| 512 | "Ties break by arrival order." | pre-release | flows |  |
| 513 | "`payload`: the work itself, usually a job body…" | pre-release | flows |  |
| 514 | "Dependency enforcement follows the same three-mode pattern as…" | pre-release | flows |  |
| 515 | "Config-only, like `judge`." | pre-release | flows |  |
| 516 | "Workers ask; the Oracle deals." | pre-release | flows |  |
| 517 | "The worker sends a signed `task_request`:" | pre-release | flows |  |
| 518 | "The Oracle replies with a `task_offer` (the task…" | pre-release | flows |  |
| 519 | "Both messages are HMAC-signed emails under the same…" | pre-release | flows |  |
| 520 | "The pull direction matters: workers initiate, so the…" | pre-release | flows |  |
| 521 | "Anyone holding the shared secret can pull." | pre-release | flows |  |
| 522 | "A `worker_allowlist` in config restricts pulls to named…" | pre-release | flows |  |
| 523 | "Off by default." | pre-release | flows |  |
| 524 | "Dealing is a claim, not a copy." | pre-release | flows |  |
| 525 | "When the Oracle answers a `task_request` with a…" | pre-release | flows |  |
| 526 | "Concurrent pulls never receive the same task." | pre-release | flows |  |
| 527 | "If no unclaimed task fits the worker, the…" | pre-release | flows |  |
| 528 | "By default a worker sees the entire task…" | pre-release | flows |  |
| 529 | "The Oracle may additionally partition work so no…" | pre-release | flows |  |
| 530 | "This is opt-in per task via `compartments[]` labels,…" | pre-release | flows |  |
| 531 | "Tasks without labels are fully visible to any…" | pre-release | flows |  |
| 532 | "A worker that pulls while it holds a…" | pre-release | flows |  |
| 533 | "Two bounds apply regardless." | pre-release | flows |  |
| 534 | "The privacy budget (section 11) limits what a…" | pre-release | flows |  |
| 535 | "Compartmentalization decides *which* work a worker sees; the…" | pre-release | flows |  |
| 536 | "Disclaimer: compartmentalization is a policy, not a proof." | pre-release | flows |  |
| 537 | "A worker that receives a task sees that…" | pre-release | flows |  |
| 538 | "Do not place mutually hostile workers on the…" | pre-release | flows |  |
| 539 | "Workers return `task_result` messages shaped like the results…" | pre-release | flows |  |
| 540 | "Results carry the `task_id`; duplicates are deduped, so…" | pre-release | flows |  |
| 541 | "An attestation binds a worker to its claimed…" | pre-release | flows |  |
| 542 | "It says nothing about whether the output is…" | pre-release | flows |  |
| 543 | "Correctness comes from review, and the review gate…" | pre-release | flows |  |
| 544 | "By default a `task_result` moves the task straight…" | pre-release | flows |  |
| 545 | "With `require_review: true` in config, the task instead…" | pre-release | flows |  |
| 546 | "The Oracle does not route results to reviewing…" | pre-release | flows |  |
| 547 | "If a worker pulls a task and no…" | pre-release | flows |  |
| 548 | "Workers that go silent are simply never dealt…" | pre-release | flows |  |
| 549 | "The Oracle is the sole arbiter of the…" | pre-release | flows |  |
| 550 | "Concurrency reduces to three rules." | pre-release | flows |  |
| 551 | "**Claims are exclusive.** A task has one state:…" | pre-release | flows |  |
| 552 | "Dealing moves open to claimed; a `task_result` for…" | pre-release | flows |  |
| 553 | "Completion checks the task's state and the key…" | pre-release | flows |  |
| 554 | "No two workers ever hold the same task." | pre-release | flows |  |
| 555 | "**Claims are leases, not locks.** A claim lapses…" | pre-release | flows |  |
| 556 | "A crashed worker cannot wedge the board; it…" | pre-release | flows |  |
| 557 | "**Results are idempotent.** Every `task_result` carries its `task_id`." | pre-release | flows |  |
| 558 | "Duplicates — from retries, redelivery, or a worker…" | pre-release | flows |  |
| 559 | "The first result wins; a result for a…" | pre-release | flows |  |
| 560 | "Throughput is bounded by a single machine dealing…" | pre-release | flows |  |
| 561 | "That is the design, not a limitation to…" | pre-release | flows |  |
| 562 | "If the board ever outgrows one box, the…" | pre-release | flows |  |
| 563 | "Three more board messages ride the same signed,…" | pre-release | flows |  |
| 564 | "Their subjects follow the board pattern: `[HOMING-PIGEON] <type>…" | pre-release | flows |  |
| 565 | "Every board message (these three and `task_request`) is…" | pre-release | flows |  |
| 566 | "A message that fails any of these is…" | pre-release | flows |  |
| 567 | "`task_submit` (subject id: the `task_id`) opens a task…" | pre-release | flows |  |
| 568 | "The body is the task of section 13.1…" | pre-release | flows |  |
| 569 | "A `task_id` already on the board is not…" | pre-release | flows |  |
| 570 | "`runner/cloud/send_job.py task-submit` composes one." | pre-release | flows |  |
| 571 | "`task_approve` (subject id: the `task_id`) is the human…" | pre-release | flows |  |
| 572 | "A task in any other state is refused." | pre-release | flows |  |
| 573 | "`task_ack` is the Oracle's reply to `task_submit`, `task_result`,…" | pre-release | flows |  |
| 574 | "Board replies — `task_ack` and `task_offer` — are…" | pre-release | flows |  |
| 575 | "The ack: `{"v": 1, "type": "task_ack", "task_id": "<id>",…" | pre-release | flows |  |
| 576 | "`task_request` is answered by `task_offer`, or by `task_offer`…" | pre-release | flows |  |
| 577 | "One shared secret is the default." | pre-release | flows |  |
| 578 | "Config may name more." | pre-release | flows |  |
| 579 | "Config gains an optional `additional_secrets` object mapping key…" | pre-release | flows |  |
| 580 | "Every secret in the map faces the same…" | pre-release | flows |  |
| 581 | "The runner refuses to start if any of…" | pre-release | flows |  |
| 582 | "Any signed message — job, query, task_request, task_result…" | pre-release | flows |  |
| 583 | "The field sits inside the signed body, so…" | pre-release | flows |  |
| 584 | "When `key_id` is absent, the runner uses `shared_secret`." | pre-release | flows |  |
| 585 | "A sender that names no key keeps working." | pre-release | flows |  |
| 586 | "This is backward compatible by construction — the…" | pre-release | flows |  |
| 587 | "Operators adding secrets keep the original secret as…" | pre-release | flows |  |
| 588 | "Every secret also has a name of its…" | pre-release | flows |  |
| 589 | "Key IDs are labels, not secrets." | pre-release | flows |  |
| 590 | "They may appear in logs and error messages." | pre-release | flows |  |
| 591 | "Unknown key IDs are rejected before any cryptographic…" | pre-release | flows |  |
| 592 | "The key ID is also the natural key…" | pre-release | flows |  |
| 593 | "Rate limits (`max_queries_per_hour`, section 11) are tracked per…" | pre-release | flows |  |
| 594 | "Privacy budgets are tracked per job (section 11)." | pre-release | flows |  |
| 595 | "Rotation is a config edit: add a new…" | pre-release | flows |  |
| 596 | "No flag day." | pre-release | flows |  |
| 597 | "Keys are unrestricted by default: any valid key…" | pre-release | flows |  |
| 598 | "An optional `key_policies` object constrains what a key…" | pre-release | flows |  |
| 599 | "This matters most when the signer is an…" | pre-release | flows |  |
| 600 | "Every field is optional; every specified constraint must…" | pre-release | flows |  |
| 601 | "`allowed_kinds`: the job's `kind` must be listed." | pre-release | flows |  |
| 602 | "The same list governs the other doors a…" | pre-release | flows |  |
| 603 | "A policy that lists `allowed_kinds` admits a door…" | pre-release | flows |  |
| 604 | "`key_policies_default_deny` refuses an additional key with no entry…" | pre-release | flows |  |
| 605 | "`allowed_interpreters`: the job's effective interpreter (its own, or…" | pre-release | flows |  |
| 606 | "`max_timeout_sec`: the job's effective timeout must not exceed…" | pre-release | flows |  |
| 607 | "`allowed_recipes`: a `recipe` or `change` job's `recipe` must…" | pre-release | flows |  |
| 608 | "With `allowed_kinds: ["recipe"]` the key runs the named…" | pre-release | flows |  |
| 609 | "`allowed_interpreters` does not bind a recipe job, whose…" | pre-release | flows |  |
| 610 | "`allowed_script_sha384`: for `exec` jobs, the inline `script`'s SHA-384…" | pre-release | flows |  |
| 611 | "`script_url` jobs are rejected under such a policy…" | pre-release | flows |  |
| 612 | "`allowed_env`: only the listed env var names may…" | pre-release | flows |  |
| 613 | "For a pinned script (see below), env vars…" | pre-release | flows |  |
| 614 | "`denied_env`: the listed env var names may never…" | pre-release | flows |  |
| 615 | "`allow_dangerous_env`: when boolean `true`, dangerous env names (plan…" | pre-release | flows |  |
| 616 | "Without it they are refused even when listed." | pre-release | flows |  |
| 617 | "Default off; only meaningful for keys with a…" | pre-release | flows |  |
| 618 | "`allowed_files`: only the listed file names may be…" | pre-release | flows |  |
| 619 | "For a pinned script, files not listed here…" | pre-release | flows |  |
| 620 | "`allow_file_urls`: when `false`, any `files` entry carrying a…" | pre-release | flows |  |
| 621 | "Default `true` when absent." | pre-release | flows |  |
| 622 | "`max_args`: integer cap on the number of args…" | pre-release | flows |  |
| 623 | "`args_pattern`: every arg must fully match this regex." | pre-release | flows |  |
| 624 | "Args longer than 1024 characters are denied outright." | pre-release | flows |  |
| 625 | "The pattern is validated at startup and rejected…" | pre-release | flows |  |
| 626 | "Env, file, and arg constraints are hardening controls…" | pre-release | flows |  |
| 627 | "In `audit` mode the job runs and the…" | pre-release | flows |  |
| 628 | "With every mode `off` (the default), these fields…" | pre-release | flows |  |
| 629 | "A pinned script is not the whole story:…" | pre-release | flows |  |
| 630 | "Env names that subvert execution (the plan's Appendix…" | pre-release | flows |  |
| 631 | "The test suite backs this: a pinned script…" | pre-release | flows |  |
| 632 | "A policy may also be attached to the…" | pre-release | flows |  |
| 633 | "It binds the default key at every door,…" | pre-release | flows |  |
| 634 | "Violations are rejected like any other bad job:…" | pre-release | flows |  |
| 635 | "At the query door the sender also gets…" | pre-release | flows |  |
| 636 | "Keys without a policy entry behave exactly as…" | pre-release | flows |  |
| 637 | "Two guards against a forgotten entry." | pre-release | flows |  |
| 638 | "At startup the runner logs a warning naming…" | pre-release | flows |  |
| 639 | "And `key_policies_default_deny` (default false) flips the default for…" | pre-release | flows |  |
| 640 | "The default stays loose; strict is opt-in." | pre-release | flows |  |
| 641 | "The default key is never affected by the…" | pre-release | flows |  |
| 642 | "A policy is a property of the key,…" | pre-release | flows |  |
| 643 | "A secret's name by default is its **fingerprint**:…" | pre-release | flows |  |
| 644 | "Anyone holding the secret can compute it, so…" | pre-release | flows |  |
| 645 | "The runner's default key answers to its fingerprint…" | pre-release | flows |  |
| 646 | "An additional key keeps the name the operator…" | pre-release | flows |  |
| 647 | "The operator's name stays the one the key…" | pre-release | flows |  |
| 648 | "A chosen name for the runner's own key…" | pre-release | flows |  |
| 649 | "Every rule that knows a key by name…" | pre-release | flows |  |
| 650 | "Names travel in the open." | pre-release | flows |  |
| 651 | "A result names the key that verified its…" | pre-release | flows |  |
| 652 | "That is safe by construction, and the reasoning…" | pre-release | flows |  |
| 653 | "A name is a label, like a user…" | pre-release | flows |  |
| 654 | "Learning a name tells an attacker which key…" | pre-release | flows |  |
| 655 | "The fingerprint is eight hex digits (32 bits)…" | pre-release | flows |  |
| 656 | "It cannot be inverted, and as an oracle…" | pre-release | flows |  |
| 657 | "The label (`homing-pigeon key id v1\n`) separates this…" | pre-release | flows |  |
| 658 | "Nothing a runner publishes about a key is…" | pre-release | flows |  |
| 659 | "`key_ids` leaves only in a result, which answers…" | pre-release | flows |  |
| 660 | "The reference sender keeps a keyring (`send_job.py keyring…" | pre-release | flows |  |
| 661 | "`--key-id ""` sends the unnamed form senders used…" | pre-release | flows |  |
| 662 | "A runner may hold a **panic word**: six…" | pre-release | flows |  |
| 663 | "The runner keeps only" | pre-release | flows |  |
| 664 | "with a 32-octet random salt, in `panic.json` in…" | pre-release | flows |  |
| 665 | "`word` is the six words in lower case…" | pre-release | flows |  |
| 666 | "A message on any transport whose subject is…" | pre-release | flows |  |
| 667 | "fires it." | pre-release | flows |  |
| 668 | "The prefix and the verb are matched without…" | pre-release | flows |  |
| 669 | "A subject with anything before the prefix (`Re:`,…" | pre-release | flows |  |
| 670 | "The check is made on intake, before the…" | pre-release | flows |  |
| 671 | "It therefore works when the shared secret is…" | pre-release | flows |  |
| 672 | "When it fires, the runner stops every running…" | pre-release | flows |  |
| 673 | "It sends nothing: no reply to the panic,…" | pre-release | flows |  |
| 674 | "The word is spent once sent, since anyone…" | pre-release | flows |  |
| 675 | "A dry run logs the match and fires…" | pre-release | flows |  |
| 676 | "No message re-arms a runner." | pre-release | flows |  |
| 677 | "The owner runs `install.py --rearm` on the box,…" | pre-release | flows |  |
| 678 | "The word protects only where a job cannot…" | pre-release | flows |  |
| 679 | "Where jobs run as the runner's own user,…" | pre-release | flows |  |
| 680 | "`install.py --check` says which case a box is…" | pre-release | flows |  |
| 681 | "A key's name says which secret signed a…" | pre-release | flows |  |
| 682 | "It is one object, inline as `key_directory` or…" | pre-release | flows |  |
| 683 | "Never the secret." | pre-release | flows |  |
| 684 | "An entry carries `state` and may carry `fingerprint`,…" | pre-release | flows |  |
| 685 | "The states, in a key's life order: `ordered`,…" | pre-release | flows |  |
| 686 | "What each does:" | pre-release | flows |  |
| 687 | "`in_use` verifies, until its `not_after` when it carries…" | pre-release | flows |  |
| 688 | "`superseded` verifies until its `not_after`, which is the…" | pre-release | flows |  |
| 689 | "Every other state is refused, and `compromised` is…" | pre-release | flows |  |
| 690 | "A key with no entry is refused: a…" | pre-release | flows |  |
| 691 | "One key, one entry: a key with entries…" | pre-release | flows |  |
| 692 | "An entry that carries `fingerprint` must carry the…" | pre-release | flows |  |
| 693 | "The runner checks the whole directory at startup…" | pre-release | flows |  |
| 694 | "The verdict comes first, before the key's policy…" | pre-release | flows |  |
| 695 | "The directory is read at each check, so…" | pre-release | flows |  |
| 696 | "The hosted queue's Worker reads its own tenant…" | pre-release | flows |  |
| 697 | "Rotation is unchanged: add the new key, hand…" | pre-release | flows |  |
| 698 | "This section was the work plan." | pre-release | flows |  |
| 699 | "The boxes below shipped." | pre-release | flows |  |
| 700 | "It is kept as the record of what…" | pre-release | flows |  |
| 701 | "It is not a proposal." | pre-release | flows |  |
| 702 | "`additional_secrets` config: parse, entropy-gate every secret at startup,…" | pre-release | flows |  |
| 703 | "`key_id` verification: every signed message type (job, query,…" | pre-release | flows |  |
| 704 | "Unknown key IDs rejected before crypto." | pre-release | flows |  |
| 705 | "Task board: persistent task states (open, claimed, done)…" | pre-release | flows |  |
| 706 | "Survives restarts; a crashed Oracle re-offers claimed tasks…" | pre-release | flows |  |
| 707 | "`task_request` / `task_offer` / `empty` handling per section…" | pre-release | flows |  |
| 708 | "`task_result` intake with dedup per 13.6." | pre-release | flows |  |
| 709 | "`dag_mode` (off/advisory/enforce), `worker_allowlist`, `compartments` / `worker_compartments`, `require_review`, `task_timeout`:…" | pre-release | flows |  |
| 710 | "Per-key-ID rate limits and per-job privacy budgets (section…" | pre-release | flows |  |
| 711 | "`install.py`: generate additional secrets on request (`--additional-secret <key-id>`)…" | pre-release | flows |  |
| 712 | "Tests: multi-secret verification, key_id fallback, claim exclusivity under…" | pre-release | flows |  |
| 713 | "The documentation items below were part of the…" | pre-release | flows |  |
| 714 | "All shipped; the four marked open on 2026-10-21…" | pre-release | flows |  |
| 715 | "README.md: Oracle section rewritten from "proposal" to real;…" | pre-release | flows |  |
| 716 | "INSTALL.md / docs/use/runbook.md: `additional_secrets` config walkthrough (INSTALL.md step…" | pre-release | flows |  |
| 717 | "AGENTS.md: how a worker SI pulls tasks, claims…" | pre-release | flows |  |
| 718 | "SECURITY.md: multi-secret threat notes (key ID is a…" | pre-release | flows |  |
| 719 | "docs/security/safeguards.md: operational guidance for running a board (timeouts,…" | pre-release | flows |  |
| 720 | "PROTOCOL.md: this file." | pre-release | flows |  |
| 721 | "The Oracle sections are implemented. *Shipped.*" | pre-release | flows |  |
| 722 | "docs/archive/DOCKER.md: env vars for additional secrets, if supported.…" | pre-release | flows |  |
| 723 | "This was the build order." | pre-release | flows |  |
| 724 | "It is finished." | pre-release | flows |  |
| 725 | "Config and verification first." | pre-release | flows |  |
| 726 | "Section 14 is the smallest backward-compatible piece and…" | pre-release | flows |  |
| 727 | "Then the task board and dispatch (section 13)." | pre-release | flows |  |
| 728 | "Then the privacy-preserving results (sections 9-12), the largest…" | pre-release | flows |  |
| 729 | "Docs ship with each piece, not after." | pre-release | flows |  |
| 730 | "The python script to compose transport message: https://github.com/Pigeon-Home/homing-pigeon/blob/main/runner/cloud/send_job.py" | pre-release | flows |  |
| 731 | "Project context: https://github.com/Pigeon-Home/homing-pigeon/blob/main/AGENTS.md" | pre-release | flows |  |
| 732 | "The source: https://github.com/Pigeon-Home/homing-pigeon/tree/main/runner" | pre-release | flows |  |
| 733 | "The test suite: https://github.com/Pigeon-Home/homing-pigeon/tree/main/runner/tests" | pre-release | flows |  |
| 734 | "The CI pipeline (every workflow): https://github.com/Pigeon-Home/homing-pigeon/tree/main/.github/workflows" | pre-release | flows |  |
| 735 | "The whole project as a snapshot (every file,…" | pre-release | flows |  |
| 736 | "On an installed runner it is `<state dir>/project/`." | pre-release | flows |  |
