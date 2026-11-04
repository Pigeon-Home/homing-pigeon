# Findings — docs/PROTOCOL.md

Source: docs/PROTOCOL.md, reviewed at intermediate-modown c63c687b.
Sentence units: 589. Flagged: 3. Categories: pre-release 588, post-release 1.

Many units are prose runs where the document's list formatting
merges several list items into one unit; each is recorded once, as
extracted. Units 541-544 are one sentence split by the formatting
around the panic subject example; they are recorded as four units
with the split noted.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The technical protocol description v1: … v2: … v3…" | pre-release | flows |  |
| 2 | "A cloud SI may use it with any…" | pre-release | flows |  |
| 3 | "As of 2026-11-03, the repository behind this protocol…" | pre-release | flows |  |
| 4 | "A visiting SI typically has a context of…" | pre-release | flows |  |
| 5 | "If you are an SI reading this to…" | pre-release | flows |  |
| 6 | "Policy, held by the author: just as this…" | pre-release | flows |  |
| 7 | "Notes written for visiting systems, shaped by the…" | pre-release | flows |  |
| 8 | "The measure rides in the version number: the…" | pre-release | flows |  |
| 9 | "Cloud SI: composes signed job messages… — Runner…" | pre-release | flows |  |
| 10 | "Implemented in Python 3.9+ using only the standard…" | pre-release | flows |  |
| 11 | "The roles are a convention, not a requirement." | pre-release | flows |  |
| 12 | "The protocol is symmetric — a signed blob with…" | pre-release | flows |  |
| 13 | "Nothing in the message format, signatures, or verification…" | pre-release | flows |  |
| 14 | "It's really just a question of where the…" | pre-release | flows |  |
| 15 | "There's an old chess hustle that runs on…" | pre-release | flows |  |
| 16 | "The middleman wins by contributing nothing but the…" | pre-release | flows |  |
| 17 | "Same here: relay project specs one way and…" | pre-release | flows |  |
| 18 | "The draft's bindings are email, a watched folder…" | pre-release | flows |  |
| 19 | "No binding is mandatory." | pre-release | flows |  |
| 20 | "A conforming runner offers at least one." | pre-release | flows |  |
| 21 | "The reference default is email only: `transports` absent…" | pre-release | flows |  |
| 22 | "The other bindings are in the draft (Sections…" | pre-release | flows |  |
| 23 | "This section is the email binding." | pre-release | flows |  |
| 24 | "One dedicated mailbox." | pre-release | flows |  |
| 25 | "Both directions use it: The cloud SI sends…" | pre-release | flows |  |
| 26 | "Two authentication methods, both transport-level — the protocol…" | pre-release | flows |  |
| 27 | "They are never written to the log or…" | pre-release | flows |  |
| 28 | "The email extension refuses to start without `mailbox_user`…" | pre-release | flows |  |
| 29 | "A runner whose `transports` list does not include…" | pre-release | flows |  |
| 30 | "Providers that offer app passwords generally require two-factor…" | pre-release | flows |  |
| 31 | "The runner stores a refresh token and uses…" | pre-release | flows |  |
| 32 | "The Google password never touches the command line…" | pre-release | flows |  |
| 33 | "The HMAC key is a separate `shared_secret` in…" | pre-release | flows |  |
| 34 | "Requires a Desktop OAuth client id created by…" | pre-release | flows |  |
| 35 | "Every reader — the runner's transports and the hosted…" | pre-release | flows |  |
| 36 | "A UUID is recommended, not required." | pre-release | flows |  |
| 37 | "Body is UTF-8 plain text." | pre-release | flows |  |
| 38 | "It must contain one signed JSON object." | pre-release | flows |  |
| 39 | "Surrounding text (a note, a signature block) is…" | pre-release | flows |  |
| 40 | "Every string in that object is UTF-8 text…" | pre-release | flows |  |
| 41 | "Every number in it is a finite number…" | pre-release | flows |  |
| 42 | "The object nests at most 200 levels deep…" | pre-release | flows |  |
| 43 | "`reply_to`: optional." | pre-release | flows |  |
| 44 | "When present and a valid single address, the…" | pre-release | flows |  |
| 45 | "It lives inside the signed body, so only…" | pre-release | flows |  |
| 46 | "Unsigned or invalid jobs never trigger a reply…" | pre-release | flows |  |
| 47 | "Omit it and results behave as before (the…" | pre-release | flows |  |
| 48 | "`aud`: optional audience claim (`runner_id` is accepted as…" | pre-release | flows |  |
| 49 | "When the runner's config sets `runner_id` and the…" | pre-release | flows |  |
| 50 | "With the feature off (default), the field is…" | pre-release | flows |  |
| 51 | "Every message type (job, query, task_*, sensor_alert) may…" | pre-release | flows |  |
| 52 | "A fresh config — one created by the setup…" | pre-release | flows |  |
| 53 | "`oracle_opinion`: optional; one of `off`, `diagnose`, `advise`, `repair`." | pre-release | flows |  |
| 54 | "The latitude the sender requests for the Oracle's…" | pre-release | flows |  |
| 55 | "The runner's `oracle_opinion_mode` config is both the default…" | pre-release | flows |  |
| 56 | "An unrecognized value is ignored, as if the…" | pre-release | flows |  |
| 57 | "Runners that do not implement the opinion ignore…" | pre-release | flows |  |
| 58 | "`result_policy`: optional; the disclosure policy the result…" | pre-release | flows |  |
| 59 | "`key_id`: optional; names which shared secret verifies this…" | pre-release | flows |  |
| 60 | "Absent means the default secret." | pre-release | flows |  |
| 61 | "Every secret has a name a sender can…" | pre-release | flows |  |
| 62 | "`kind`: `exec` or `ping`; `recipe` (the owner's named script…" | pre-release | flows |  |
| 63 | "A `ping` job carries no script; the runner answers…" | pre-release | flows |  |
| 64 | "A job carrying both is accepted and `script_url`…" | pre-release | flows |  |
| 65 | "The script is written into the workdir under…" | pre-release | flows |  |
| 66 | "If absent, the runner's `default_interpreter` config applies, else…" | pre-release | flows |  |
| 67 | "`platform`: OPTIONAL, and only on the result to…" | pre-release | flows |  |
| 68 | "The platform card: what the box says about…" | pre-release | flows |  |
| 69 | "Receivers MUST ignore it if they do not…" | pre-release | flows |  |
| 70 | "At `family` it is {"disclosure": "family", …} — enough to…" | pre-release | flows |  |
| 71 | "The tier is the owner's ceiling: no job…" | pre-release | flows |  |
| 72 | "The card leaves only in a result, which…" | pre-release | flows |  |
| 73 | "The DTLS greeting (draft Section 20) carries the…" | pre-release | flows |  |
| 74 | "It is the identity hint of a TLS-PSK…" | pre-release | flows |  |
| 75 | "It is the first 96 bits of HMAC-SHA-384…" | pre-release | flows |  |
| 76 | "Two results with the same value ran on…" | pre-release | flows |  |
| 77 | "The view does not shape it, since it…" | pre-release | flows |  |
| 78 | "A runner reinstalled with a new salt reads…" | pre-release | flows |  |
| 79 | "Every result the runner signs carries `result_seq`, one…" | pre-release | flows |  |
| 80 | "A receiver that keeps the chain proves it…" | pre-release | flows |  |
| 81 | "The chain is per key, so no key…" | pre-release | flows |  |
| 82 | "A link is recorded once its result is…" | pre-release | flows |  |
| 83 | "A delivery stub (section 15) keeps the `result_seq`…" | pre-release | flows |  |
| 84 | "The owner turns the chain off with `result_chain: false`…" | pre-release | flows |  |
| 85 | "A name, never a value." | pre-release | flows |  |
| 86 | "It says which key signed what, and it…" | pre-release | flows |  |
| 87 | "Every result carries it, the rejection result (`exit_code` -2)…" | pre-release | flows |  |
| 88 | "Rejected jobs do not retry — the mail is…" | pre-release | flows |  |
| 89 | "The whole body is held under `max_result_bytes` (default…" | pre-release | flows |  |
| 90 | "The signature always covers what is sent." | pre-release | flows |  |
| 91 | "Present only on a stub sent in place…" | pre-release | flows |  |
| 92 | "It is signed and encrypted like any result." | pre-release | flows |  |
| 93 | "A 4xx, a socket or a TLS error…" | pre-release | flows |  |
| 94 | "The Oracle's opinion of the job, formed on…" | pre-release | flows |  |
| 95 | "It is advisory: it never blocks, holds, or…" | pre-release | flows |  |
| 96 | "The member is absent entirely when the effective…" | pre-release | flows |  |
| 97 | "When present it is an object with these…" | pre-release | flows |  |
| 98 | "Text formed by the runner's local model, when…" | pre-release | flows |  |
| 99 | "The SHA-384 hex digest of the job as…" | pre-release | flows |  |
| 100 | "At `diagnose` latitude the member appears only on a…" | pre-release | flows |  |
| 101 | "At `advise` latitude a prediction computed before the run…" | pre-release | flows |  |
| 102 | "At `repair` latitude the runner MAY correct the one…" | pre-release | flows |  |
| 103 | "Present only when remediation acted on the job…" | pre-release | flows |  |
| 104 | "Receivers MUST ignore it if they do not…" | pre-release | flows |  |
| 105 | "When present it is an object with these…" | pre-release | flows |  |
| 106 | "(Under `off` nothing acts, and the member is…" | pre-release | flows |  |
| 107 | "Referral of suspect files to the box's antivirus…" | pre-release | flows |  |
| 108 | "Unavailable is a fact, not an error. — `received_digest`:…" | pre-release | flows |  |
| 109 | "Remediation is owner configuration only: a job member…" | pre-release | flows |  |
| 110 | "A recipe is a script the runner owner…" | pre-release | flows |  |
| 111 | "A job names one: {"kind": "recipe", "recipe": "tests", …}" | pre-release | flows |  |
| 112 | "The runner runs the owner's `script` under the owner's…" | pre-release | flows |  |
| 113 | "A recipe job may carry `files` and `outputs`…" | pre-release | flows |  |
| 114 | "It MUST NOT carry `script`, `script_url`, `script_sha384`, `interpreter`…" | pre-release | flows |  |
| 115 | "Each argument must fully match `args_pattern` and be…" | pre-release | flows |  |
| 116 | "The runner refuses to start with a recipe…" | pre-release | flows |  |
| 117 | "A key policy's `allowed_recipes` (section 14.1) names the…" | pre-release | flows |  |
| 118 | "A sender stops a job it sent with…" | pre-release | flows |  |
| 119 | "It is signed, sealed under the job id…" | pre-release | flows |  |
| 120 | "The deny flag holds at this door; `allowed_kinds` does…" | pre-release | flows |  |
| 121 | "A job running on the runner is killed…" | pre-release | flows |  |
| 122 | "Its result carries `cancelled: true`, `exit_code` -1 and a…" | pre-release | flows |  |
| 123 | "The runner keeps the cancel that long and…" | pre-release | flows |  |
| 124 | "The runner answers with a signed (and, as…" | pre-release | flows |  |
| 125 | "Another key's job, whether running, done or unseen…" | pre-release | flows |  |
| 126 | "The reference runner serves a transport's messages one…" | pre-release | flows |  |
| 127 | "A change is the loop of checking out…" | pre-release | flows |  |
| 128 | "`repo` names an entry of the owner's `change_repos`…" | pre-release | flows |  |
| 129 | "The runner clones that repository into the job's…" | pre-release | flows |  |
| 130 | "The job carries no script, interpreter or environment…" | pre-release | flows |  |
| 131 | "The result carries `change: {"repo": …, "commit": …}`…" | pre-release | flows |  |
| 132 | "The job's own `outputs` name files under `src/`…" | pre-release | flows |  |
| 133 | "A runner without git, a repository that does…" | pre-release | flows |  |
| 134 | "A key policy's `allowed_recipes` binds the recipe a…" | pre-release | flows |  |
| 135 | "Appending the signature last avoids cross-language JSON canonicalization…" | pre-release | flows |  |
| 136 | "1." | pre-release | flows |  |
| 137 | "Serialize the payload as a JSON object without…" | pre-release | flows |  |
| 138 | "2." | pre-release | flows |  |
| 139 | "Normalize line endings to LF (`\r\n` → `\n`, `\r` → `\n`)." | pre-release | flows |  |
| 140 | "3. `sig = HEX(HMAC_SHA384(secret, normalized_payload))`." | pre-release | flows |  |
| 141 | "4." | pre-release | flows |  |
| 142 | "Body = payload with the trailing `}` replaced…" | pre-release | flows |  |
| 143 | "Verification:" | pre-release | flows |  |
| 144 | "1." | pre-release | flows |  |
| 145 | "Normalize line endings to LF." | pre-release | flows |  |
| 146 | "2." | pre-release | flows |  |
| 147 | "Find the last occurrence of `,"sig":"`." | pre-release | flows |  |
| 148 | "The 96 characters after it must be hex…" | pre-release | flows |  |
| 149 | "Text after that `"}` (a trailer) is ignored." | pre-release | flows |  |
| 150 | "3. `raw` = the text from the `{` that…" | pre-release | flows |  |
| 151 | "Text before that `{` is not signed." | pre-release | flows |  |
| 152 | "4." | pre-release | flows |  |
| 153 | "Recompute `HEX(HMAC_SHA384(secret, raw))` and compare with the…" | pre-release | flows |  |
| 154 | "5." | pre-release | flows |  |
| 155 | "If that does not match, form `raw'` by…" | pre-release | flows |  |
| 156 | "This is the second signed form: a mail…" | pre-release | flows |  |
| 157 | "A receiver MUST compare the second form in…" | pre-release | flows |  |
| 158 | "The shared secret is a dedicated high-entropy string…" | pre-release | flows |  |
| 159 | "Both sides use its UTF-8 bytes directly as…" | pre-release | flows |  |
| 160 | "The user gives the same string to the…" | pre-release | flows |  |
| 161 | "It never travels in email; only job signatures…" | pre-release | flows |  |
| 162 | "The runner refuses to start if the secret…" | pre-release | flows |  |
| 163 | "Two kinds of checks run, and the order…" | pre-release | flows |  |
| 164 | "Routing checks run first, on the unauthenticated message…" | pre-release | flows |  |
| 165 | "These checks route and deduplicate; they authorize nothing…" | pre-release | flows |  |
| 166 | "Everything that runs on the unauthenticated message, the…" | pre-release | flows |  |
| 167 | "Two senses of seen are kept apart throughout…" | pre-release | flows |  |
| 168 | "Where a later section says a message is…" | pre-release | flows |  |
| 169 | "Nothing is executed, answered, or acted on before…" | pre-release | flows |  |
| 170 | "Authorization then runs in this order, and all…" | pre-release | flows |  |
| 171 | "1. Signature valid: the body HMAC-SHA-384 must verify…" | pre-release | flows |  |
| 172 | "This is the sole authentication gate." | pre-release | flows |  |
| 173 | "The `From` address is not validated — any sender…" | pre-release | flows |  |
| 174 | "The sender address is logged for audit but…" | pre-release | flows |  |
| 175 | "2. Audience binding (when `security.modes.audience` is not `off`…" | pre-release | flows |  |
| 176 | "The expected value always comes from the config…" | pre-release | flows |  |
| 177 | "Applies to jobs, queries (including the `ask` op)…" | pre-release | flows |  |
| 178 | "3." | pre-release | flows |  |
| 179 | "The signed script is bounded by `max_script_bytes`." | pre-release | flows |  |
| 180 | "4. `v` is the JSON integer 1 (checked once…" | pre-release | flows |  |
| 181 | "JSON `true` and `1.0` compare equal to 1 and…" | pre-release | flows |  |
| 182 | "5. `issued_at` parses, carries a timezone, is no older…" | pre-release | flows |  |
| 183 | "6. (Seen-set.) The `job_id` seen-set lookup is a routing…" | pre-release | flows |  |
| 184 | "It is listed here only so the replay…" | pre-release | flows |  |
| 185 | "The seen-set key is namespaced by `runner_id` when…" | pre-release | flows |  |
| 186 | "An entry is kept for as long as…" | pre-release | flows |  |
| 187 | "It is never dropped earlier to make room." | pre-release | flows |  |
| 188 | "7. Job-shape validation (job messages): `kind` is `exec`, `ping`…" | pre-release | flows |  |
| 189 | "Failures here produce the -2 rejection result of…" | pre-release | flows |  |
| 190 | "Two more gates sit in that order: a…" | pre-release | flows |  |
| 191 | "A query, a board message and a version…" | pre-release | flows |  |
| 192 | "Failures are logged, the mail is marked seen…" | pre-release | flows |  |
| 193 | "Delivery is a separate, retryable concern: a send…" | pre-release | flows |  |
| 194 | "A delivered record moves to `<base_dir>/sent/`, where a…" | pre-release | flows |  |
| 195 | "The one window left is the stash write…" | pre-release | flows |  |
| 196 | "On a file channel the same rule is…" | pre-release | flows |  |
| 197 | "That move happens only when the core would…" | pre-release | flows |  |
| 198 | "A retryable failure leaves the envelope in the…" | pre-release | flows |  |
| 199 | "A rejection is still consumed, so poison is…" | pre-release | flows |  |
| 200 | "The limits this section names come from `config.json`…" | pre-release | flows |  |
| 201 | "A setting that is present but not usable…" | pre-release | flows |  |
| 202 | "Working directory: `<base_dir>/work/<job_id>/`, created fresh per job…" | pre-release | flows |  |
| 203 | "The rejection names the rule." | pre-release | flows |  |
| 204 | "A nested name (`data/in.csv`) has its directories made…" | pre-release | flows |  |
| 205 | "An inline file is covered by the job's…" | pre-release | flows |  |
| 206 | "A name staged twice is refused." | pre-release | flows |  |
| 207 | "This is how a sender carries a patch…" | pre-release | flows |  |
| 208 | "A file is read only if its real…" | pre-release | flows |  |
| 209 | "Each `outputs[]` entry in the result names the file…" | pre-release | flows |  |
| 210 | "What of it leaves the box is the…" | pre-release | flows |  |
| 211 | "Idempotent jobs are still good hygiene — check before…" | pre-release | flows |  |
| 212 | "The runner host is a full-trust execution environment…" | pre-release | flows |  |
| 213 | "Anyone holding the password gets mailbox access — not…" | pre-release | flows |  |
| 214 | "Do not use this setup with an account…" | pre-release | flows |  |
| 215 | "(With `"auth": "oauth"` there is no password on disk…" | pre-release | flows |  |
| 216 | "Same caution applies.) — Use a dedicated mailbox, never…" | pre-release | flows |  |
| 217 | "Use an app password, never the account password." | pre-release | flows |  |
| 218 | "VM snapshots give instant rollback, and the guest…" | pre-release | flows |  |
| 219 | "File downloads over HTTPS only." | pre-release | flows |  |
| 220 | "Work that is not built is listed in…" | pre-release | flows |  |
| 221 | "Result policies are specified below." | pre-release | flows |  |
| 222 | "The object protocol uses three cryptographic primitives:" | pre-release | flows |  |
| 223 | "Message authentication: HMAC-SHA-384, keyed with the shared secret." | pre-release | flows |  |
| 224 | "This is the protocol's authentication mechanism; sender identity asserted…" | pre-release | flows |  |
| 225 | "A signed body SHOULD be sent as an…" | pre-release | flows |  |
| 226 | "The associated data is the subject's identifier (the…" | pre-release | flows |  |
| 227 | "The key id there is `""` for the unnamed…" | pre-release | flows |  |
| 228 | "A receiver MUST accept the encrypted form, and…" | pre-release | flows |  |
| 229 | "The reference receiver applies that same refusal to…" | pre-release | flows |  |
| 230 | "A result mirrors the form of the job…" | pre-release | flows |  |
| 231 | "A real job/result pair in this form, as…" | pre-release | flows |  |
| 232 | "The DTLS binding adds one more construction, and…" | pre-release | flows |  |
| 233 | "It is not part of the object protocol. `psk_ke`…" | pre-release | flows |  |
| 234 | "These are the CNSA-listed choices: the 384-bit tier…" | pre-release | flows |  |
| 235 | "Confidentiality is a property of the signed object…" | pre-release | flows |  |
| 236 | "The reference senders encrypt by default, and the…" | pre-release | flows |  |
| 237 | "On the email binding a cleartext job is…" | pre-release | flows |  |
| 238 | "TLS protects the hop and does not hide…" | pre-release | flows |  |
| 239 | "Authenticity and integrity come from HMAC-SHA-384 in both…" | pre-release | flows |  |
| 240 | "The reference tools encrypt unless a flag says…" | pre-release | flows |  |
| 241 | "The runner refuses that body unless it was…" | pre-release | flows |  |
| 242 | "The shared secret is required either way: the…" | pre-release | flows |  |
| 243 | "There is no config key for this." | pre-release | flows |  |
| 244 | "The protocol version stays 1." | pre-release | flows |  |
| 245 | "———" | pre-release | flagged | Not a sentence: a horizontal-rule line standing alone between the cleartext note and the Oracle part; nothing leads into or out of it |
| 246 | "Paradigm: the runner as the Oracle. Without a…" | pre-release | flows |  |
| 247 | "The Oracle inverts this: the runner keeps the…" | pre-release | flows |  |
| 248 | "The SI learns predicates about the output — never…" | pre-release | flows |  |
| 249 | "This is the interactive-proof shape applied at the…" | pre-release | flows |  |
| 250 | "The Oracle is a local agent: instructions plus…" | pre-release | flows |  |
| 251 | "It has four duties, three across a job's…" | pre-release | flows |  |
| 252 | "Before execution — judgment (section 9.3): read the incoming…" | pre-release | flows |  |
| 253 | "The Oracle adds a second direction without removing…" | pre-release | flows |  |
| 254 | "The SI pushes jobs to the runner, and…" | pre-release | flows |  |
| 255 | "The Oracle can also run the other way…" | pre-release | flows |  |
| 256 | "Push and pull coexist; a deployment uses either…" | pre-release | flows |  |
| 257 | "It is governed by runner-owner flags." | pre-release | flows |  |
| 258 | "They are config-only, never job fields — no job…" | pre-release | flows |  |
| 259 | "Section 13 adds dispatch-specific flags under the same…" | pre-release | flows |  |
| 260 | "The Oracle is unconditional: there is no flag…" | pre-release | flows |  |
| 261 | "The job gains an optional `result_policy` object:" | pre-release | flows |  |
| 262 | "`view`: one of `full` (stdout and stderr), `redacted`, `summary`…" | pre-release | flows |  |
| 263 | "Default: `full` (backward compatible). — `redact_patterns`: reserved." | pre-release | flows |  |
| 264 | "In `redacted` view the runner applies every family…" | pre-release | flows |  |
| 265 | "This is what makes the exchange non-interactive. — `query_budget`:…" | pre-release | flows |  |
| 266 | "The runner owner's config caps it with `max_query_budget`…" | pre-release | flows |  |
| 267 | "Bounds total leakage — and doubles as a tripwire…" | pre-release | flows |  |
| 268 | "The ceiling is set by the runner owner…" | pre-release | flows |  |
| 269 | "The effective view is the narrower of the…" | pre-release | flows |  |
| 270 | "This is the load-bearing privacy property: the SI…" | pre-release | flows |  |
| 271 | "`full`: stdout and stderr, as in section 3.2…" | pre-release | flows |  |
| 272 | "The runner scans stdout and stderr as one…" | pre-release | flows |  |
| 273 | "Like every non-`full` view it carries `output_digest` (section…" | pre-release | flows |  |
| 274 | "Contains `exit_code`, `timed_out`, `duration_sec`, `stdout_bytes`, `stderr_bytes` (the UTF-8…" | pre-release | flows |  |
| 275 | "No output bytes cross the boundary at all." | pre-release | flows |  |
| 276 | "(`full` carries `view` and `output_digest` too." | pre-release | flows |  |
| 277 | "Members the owner's configuration adds, such as `judgment`…" | pre-release | flows |  |
| 278 | "Every view keeps the result's identity members (`v`…" | pre-release | flows |  |
| 279 | "Built-in predicates (a fixed set; an unknown predicate…" | pre-release | flows |  |
| 280 | "`exit_zero`: `exit_code == 0`. — `no_secrets`: the retained output…" | pre-release | flows |  |
| 281 | "This is a commitment: the SI can't see…" | pre-release | flows |  |
| 282 | "Only meaningful when confinement is configured; otherwise the…" | pre-release | flows |  |
| 283 | "Each attestation is covered by the message HMAC…" | pre-release | flows |  |
| 284 | "Before anything runs, the Oracle reads the job…" | pre-release | flows |  |
| 285 | "The verdict is deterministic: checks against the job…" | pre-release | flows |  |
| 286 | "No model participates in it, whether or not…" | pre-release | flows |  |
| 287 | "A semantic verdict — a model-backed reading such as…" | pre-release | flows |  |
| 288 | "It is not shipped and not planned." | pre-release | flows |  |
| 289 | "(The optional model-backed note in the `oracle_opinion` result…" | pre-release | flows |  |
| 290 | "A verdict is a judgment, not a proof." | pre-release | flows |  |
| 291 | "It can miss malicious code and flag benign…" | pre-release | flows |  |
| 292 | "No job field can soften or disable judgment:" | pre-release | flows |  |
| 293 | "`judge`: `off`, `advisory` (verdict attached to the result…" | pre-release | flows |  |
| 294 | "This is a tripwire, not a review." | pre-release | flows |  |
| 295 | "It matches a short denylist (`rm -rf /`, `rm -rf ~`…" | pre-release | flows |  |
| 296 | "It does not weigh the job." | pre-release | flows |  |
| 297 | "During execution, the Oracle reports what a job…" | pre-release | flows |  |
| 298 | "The snapshot below does not stop a write." | pre-release | flows |  |
| 299 | "An optional Linux sandbox does." | pre-release | flows |  |
| 300 | "Config for the snapshot:" | pre-release | flows |  |
| 301 | "`workspace_root`: absolute path (e.g. `/home/user/workspace`)." | pre-release | flows |  |
| 302 | "When set, it names the root the confinement…" | pre-release | flows |  |
| 303 | "The job's working directory is always `<base_dir>/work/<job_id>`; the…" | pre-release | flows |  |
| 304 | "The walk stops at 50000 files and logs…" | pre-release | flows |  |
| 305 | "The job's own working tree never counts against…" | pre-release | flows |  |
| 306 | "The snapshot is a record, not a cage. `confined_to_workspace`…" | pre-release | flows |  |
| 307 | "Best-effort: a write that was reverted before the…" | pre-release | flows |  |
| 308 | "OS containment is a separate switch, `security.modes.confinement`, at…" | pre-release | flows |  |
| 309 | "On Linux with `bwrap` installed the job runs…" | pre-release | flows |  |
| 310 | "At startup, a sandbox that cannot engage (no…" | pre-release | flows |  |
| 311 | "See SECURITY.md." | pre-release | flows |  |
| 312 | "The attestation format does not change when the…" | pre-release | flows |  |
| 313 | "Like everything the Oracle does, the ceiling is…" | pre-release | flows |  |
| 314 | "The job's work directory is the one place…" | pre-release | flows |  |
| 315 | "Its real path is resolved once per job…" | pre-release | flows |  |
| 316 | "A download lands in a temp name beside…" | pre-release | flows |  |
| 317 | "On Linux the sandbox binds that real path…" | pre-release | flows |  |
| 318 | "On Windows there is no sandbox: these checks…" | pre-release | flows |  |
| 319 | "`protected_paths` is an optional list of absolute paths…" | pre-release | flows |  |
| 320 | "Paths listed here are checked first; any creation…" | pre-release | flows |  |
| 321 | "They are compared against the same snapshot, so…" | pre-release | flows |  |
| 322 | "Default is an empty list (least restrictive)." | pre-release | flows |  |
| 323 | "Two phases: first the SI declares what may…" | pre-release | flows |  |
| 324 | "The message count is fixed — neither party can…" | pre-release | flows |  |
| 325 | "Phase 1 — negotiation (the job). The SI declares…" | pre-release | flows |  |
| 326 | "The runner intersects each query with the owner's…" | pre-release | flows |  |
| 327 | "Phase 2 — delivery (the result). The result message…" | pre-release | flows |  |
| 328 | "Query ops: `attest` (evaluate a named predicate now), `grep`…" | pre-release | flows |  |
| 329 | "Answers obey the job's effective view exactly as…" | pre-release | flows |  |
| 330 | "A `grep` pattern that does not compile is answered…" | pre-release | flows |  |
| 331 | "So is one whose shape can take exponential…" | pre-release | flows |  |
| 332 | "A pattern the shape check cannot name still…" | pre-release | flows |  |
| 333 | "The next query starts the worker again." | pre-release | flows |  |
| 334 | "Either way the query spends its one." | pre-release | flows |  |
| 335 | "When the runner has a local model, the…" | pre-release | flows |  |
| 336 | "Raw data never leaves the machine, but answers…" | pre-release | flows |  |
| 337 | "Config (all under an `inference` object; disabled unless…" | pre-release | flows |  |
| 338 | "`endpoint`: OpenAI-compatible HTTP API (e.g. `http://localhost:11434/v1`). Must resolve…" | pre-release | flows |  |
| 339 | "Reference stack. `qwen3:1.7b` served on loopback via Ollama…" | pre-release | flows |  |
| 340 | "Any OpenAI-compatible server bound to loopback works — LM…" | pre-release | flows |  |
| 341 | "The Oracle refuses non-loopback endpoints." | pre-release | flows |  |
| 342 | "Another local agent may share the same model…" | pre-release | flows |  |
| 343 | "The `ask` op is declared upfront in `queries[]` like…" | pre-release | flows |  |
| 344 | "The Oracle prompts the model with a constrained…" | pre-release | flows |  |
| 345 | "1." | pre-release | flows |  |
| 346 | "Truncate to `max_chars`." | pre-release | flows |  |
| 347 | "2." | pre-release | flows |  |
| 348 | "Secret-scan the truncated answer, including fragment matches against…" | pre-release | flows |  |
| 349 | "Scanning runs before redaction so that a leaked…" | pre-release | flows |  |
| 350 | "3." | pre-release | flows |  |
| 351 | "Redact via the section-9 engine (same secret patterns…" | pre-release | flows |  |
| 352 | "4." | pre-release | flows |  |
| 353 | "Secret-scan again on the redacted text; a hit…" | pre-release | flows |  |
| 354 | "The delivered answer carries {"op": "ask", "answer": "…", "model": …}" | pre-release | flows |  |
| 355 | "Threat: indirect prompt injection. Adversarial job output can…" | pre-release | flows |  |
| 356 | "The pipeline above is the defense: narrow role…" | pre-release | flows |  |
| 357 | "The `query` (`[HOMING-PIGEON] query <query_id>`) and `qresult` message types…" | pre-release | flows |  |
| 358 | "Every one passes the section-5 verification (signature, freshness…" | pre-release | flows |  |
| 359 | "Outputs are retained per `output_retention_days` (runner config, default…" | pre-release | flows |  |
| 360 | "A query refused as a whole is answered…" | pre-release | flows |  |
| 361 | "None of these spends budget." | pre-release | flows |  |
| 362 | "They fall in two groups, by whether the…" | pre-release | flows |  |
| 363 | "Refused before the record is read." | pre-release | flows |  |
| 364 | "The reply names no job and takes no…" | pre-release | flows |  |
| 365 | "`unsupported`: `v` or `type` is not a query's. — `policy`:…" | pre-release | flows |  |
| 366 | "Refused once the record is looked up." | pre-release | flows |  |
| 367 | "The reply carries the query's `job_id` and `budget_remaining` 0…" | pre-release | flows |  |
| 368 | "`unknown_job`: no retained record for the `job_id`, or…" | pre-release | flows |  |
| 369 | "Only the record's owner ever sees it; any…" | pre-release | flows |  |
| 370 | "An answered `qresult` carries the query's `job_id` as well…" | pre-release | flows |  |
| 371 | "A stale query, one that fails its signature…" | pre-release | flows |  |
| 372 | "Threat: adaptive chosen-query extraction. Each answer leaks a…" | pre-release | flows |  |
| 373 | "A verifier that chooses each query after seeing…" | pre-release | flows |  |
| 374 | "Defenses, in order of importance:" | pre-release | flows |  |
| 375 | "1. Non-interactivity (the ZKP lesson). The two-phase exchange removes…" | pre-release | flows |  |
| 376 | "Zero-knowledge proofs went non-interactive (SNARKs/STARKs) for the same…" | pre-release | flows |  |
| 377 | "2. Privacy budget. `query_budget` bounds total leakage per job." | pre-release | flows |  |
| 378 | "Accounting is per job: the spend is kept…" | pre-release | flows |  |
| 379 | "(Rate limiting, item 3, is the per-key control…" | pre-release | flows |  |
| 380 | "A budget bounds what rate limiting cannot: the…" | pre-release | flows |  |
| 381 | "The budget is also an operational tripwire, not…" | pre-release | flows |  |
| 382 | "A well-formed job answers its questions in one…" | pre-release | flows |  |
| 383 | "A job that burns through all 8 is…" | pre-release | flows |  |
| 384 | "Budget exhaustion always deserves a human look — even…" | pre-release | flows |  |
| 385 | "3. Rate limiting. Before committing expensive work, demand…" | pre-release | flows |  |
| 386 | "This slows automated probing; the budget is what…" | pre-release | flows |  |
| 387 | "The Oracle's machinery reads as security tooling, but…" | pre-release | flows |  |
| 388 | "A developer hitting their first failed job gets:" | pre-release | flows |  |
| 389 | "Judgment (§9.3): "this job doesn't do what its…" | pre-release | flows |  |
| 390 | "Catches the wrong-script, wrong-arguments class of mistakes at…" | pre-release | flows |  |
| 391 | "When the SI says "it worked," the attestation is…" | pre-release | flows |  |
| 392 | "None of this replaces reading the output." | pre-release | flows |  |
| 393 | "It tells you where to look — which, for…" | pre-release | flows |  |
| 394 | "Non-escalation: neither the job's `result_policy` nor any query…" | pre-release | flows |  |
| 395 | "Without it, a third party can neither pull…" | pre-release | flows |  |
| 396 | "Restriction is configuration (section 13.3), never the default." | pre-release | flows |  |
| 397 | "Withheld material is never named in the Oracle's…" | pre-release | flows |  |
| 398 | "The material is fetched on the box only…" | pre-release | flows |  |
| 399 | "The rule, the declaration format, and the owner's…" | pre-release | flows |  |
| 400 | "This section adds a direction; it removes none." | pre-release | flows |  |
| 401 | "A signed job still pushes, the runner still…" | pre-release | flows |  |
| 402 | "Identical wire behavior, identical auth." | pre-release | flows |  |
| 403 | "The Oracle, dispatch included, is purely additive." | pre-release | flows |  |
| 404 | "It can additionally deal tasks from its board…" | pre-release | flows |  |
| 405 | "The default posture is least restrictive, like everything…" | pre-release | flows |  |
| 406 | "Any holder of the shared secret can pull…" | pre-release | flows |  |
| 407 | "Restrictions are configuration for owners who want them…" | pre-release | flows |  |
| 408 | "The disclaimers below say what that choice costs." | pre-release | flows |  |
| 409 | "A task is a job the Oracle has…" | pre-release | flows |  |
| 410 | "`task_id`: the same grammar as `job_id` (section 2)." | pre-release | flows |  |
| 411 | "A UUID is recommended, not required. — `requires[]`: task…" | pre-release | flows |  |
| 412 | "A DAG, not a flat queue. — `capabilities[]`: free-form tags…" | pre-release | flows |  |
| 413 | "Workers claim capabilities when they pull; a worker…" | pre-release | flows |  |
| 414 | "Ties break by arrival order. — `payload`: the work itself…" | pre-release | flows |  |
| 415 | "Dependency enforcement follows the same three-mode pattern as…" | pre-release | flows |  |
| 416 | "Config-only, like `judge`." | pre-release | flows |  |
| 417 | "Workers ask; the Oracle deals." | pre-release | flows |  |
| 418 | "The worker sends a signed `task_request`:" | pre-release | flows |  |
| 419 | "The Oracle replies with a `task_offer` (the task…" | pre-release | flows |  |
| 420 | "Both messages are HMAC-signed emails under the same…" | pre-release | flows |  |
| 421 | "The pull direction matters: workers initiate, so the…" | pre-release | flows |  |
| 422 | "Anyone holding the shared secret can pull." | pre-release | flows |  |
| 423 | "A `worker_allowlist` in config restricts pulls to named…" | pre-release | flows |  |
| 424 | "Off by default." | pre-release | flows |  |
| 425 | "Dealing is a claim, not a copy." | pre-release | flows |  |
| 426 | "When the Oracle answers a `task_request` with a `task_offer`…" | pre-release | flows |  |
| 427 | "Concurrent pulls never receive the same task." | pre-release | flows |  |
| 428 | "If no unclaimed task fits the worker, the…" | pre-release | flows |  |
| 429 | "By default a worker sees the entire task…" | pre-release | flows |  |
| 430 | "The Oracle may additionally partition work so no…" | pre-release | flows |  |
| 431 | "This is opt-in per task via `compartments[]` labels, matched…" | pre-release | flows |  |
| 432 | "Tasks without labels are fully visible to any…" | pre-release | flows |  |
| 433 | "A worker that pulls while it holds a…" | pre-release | flows |  |
| 434 | "Two bounds apply regardless." | pre-release | flows |  |
| 435 | "The privacy budget (section 11) limits what a worker…" | pre-release | flows |  |
| 436 | "Compartmentalization decides which work a worker sees; the…" | pre-release | flows |  |
| 437 | "Disclaimer: compartmentalization is a policy, not a proof." | pre-release | flows |  |
| 438 | "A worker that receives a task sees that…" | pre-release | flows |  |
| 439 | "Do not place mutually hostile workers on the…" | pre-release | flows |  |
| 440 | "Workers return `task_result` messages shaped like the results…" | pre-release | flows |  |
| 441 | "Results carry the `task_id`; duplicates are deduped, so…" | pre-release | flows |  |
| 442 | "An attestation binds a worker to its claimed…" | pre-release | flows |  |
| 443 | "It says nothing about whether the output is…" | pre-release | flows |  |
| 444 | "Correctness comes from review, and the review gate…" | pre-release | flows |  |
| 445 | "By default a `task_result` moves the task straight…" | pre-release | flows |  |
| 446 | "With `require_review: true` in config, the task instead enters…" | pre-release | flows |  |
| 447 | "The Oracle does not route results to reviewing…" | pre-release | flows |  |
| 448 | "If a worker pulls a task and no…" | pre-release | flows |  |
| 449 | "Workers that go silent are simply never dealt…" | pre-release | flows |  |
| 450 | "The Oracle is the sole arbiter of the…" | pre-release | flows |  |
| 451 | "Concurrency reduces to three rules." | pre-release | flows |  |
| 452 | "1. Claims are exclusive. A task has one state…" | pre-release | flows |  |
| 453 | "Dealing moves open to claimed; a `task_result` for a…" | pre-release | flows |  |
| 454 | "Completion checks the task's state and the key…" | pre-release | flows |  |
| 455 | "No two workers ever hold the same task." | pre-release | flows |  |
| 456 | "2. Claims are leases, not locks. A claim lapses…" | pre-release | flows |  |
| 457 | "A crashed worker cannot wedge the board; it…" | pre-release | flows |  |
| 458 | "3. Results are idempotent. Every `task_result` carries its `task_id`." | pre-release | flows |  |
| 459 | "Duplicates — from retries, redelivery, or a worker that…" | pre-release | flows |  |
| 460 | "The first result wins; a result for a task…" | pre-release | flows |  |
| 461 | "Throughput is bounded by a single machine dealing…" | pre-release | flows |  |
| 462 | "That is the design, not a limitation to fix…" | pre-release | flows |  |
| 463 | "If the board ever outgrows one box, the…" | post-release | flows |  |
| 464 | "Three more board messages ride the same signed…" | pre-release | flows |  |
| 465 | "Their subjects follow the board pattern: `[HOMING-PIGEON] <type> <id>`." | pre-release | flows |  |
| 466 | "Every board message (these three and `task_request`) is held…" | pre-release | flows |  |
| 467 | "A message that fails any of these is…" | pre-release | flows |  |
| 468 | "`task_submit` (subject id: the `task_id`) opens a task…" | pre-release | flows |  |
| 469 | "The body is the task of section 13.1…" | pre-release | flows |  |
| 470 | "A `task_id` already on the board is not replaced…" | pre-release | flows |  |
| 471 | "A task in any other state is refused.…" | pre-release | flows |  |
| 472 | "Board replies — `task_ack` and `task_offer` — are routed like…" | pre-release | flows |  |
| 473 | "The ack: {"v": 1, "type": "task_ack", "task_id": "<id>", …} carrying…" | pre-release | flows |  |
| 474 | "One shared secret is the default." | pre-release | flows |  |
| 475 | "Config may name more." | pre-release | flows |  |
| 476 | "Config gains an optional `additional_secrets` object mapping key…" | pre-release | flows |  |
| 477 | "Every secret in the map faces the same…" | pre-release | flows |  |
| 478 | "The runner refuses to start if any of…" | pre-release | flows |  |
| 479 | "Any signed message — job, query, task_request, task_result — may…" | pre-release | flows |  |
| 480 | "The field sits inside the signed body, so…" | pre-release | flows |  |
| 481 | "When `key_id` is absent, the runner uses `shared_secret`." | pre-release | flows |  |
| 482 | "A sender that names no key keeps working." | pre-release | flows |  |
| 483 | "This is backward compatible by construction — the single-secret…" | pre-release | flows |  |
| 484 | "Operators adding secrets keep the original secret as…" | pre-release | flows |  |
| 485 | "Every secret also has a name of its…" | pre-release | flows |  |
| 486 | "Key IDs are labels, not secrets." | pre-release | flows |  |
| 487 | "They may appear in logs and error messages." | pre-release | flows |  |
| 488 | "Unknown key IDs are rejected before any cryptographic…" | pre-release | flows |  |
| 489 | "The key ID is also the natural key…" | pre-release | flows |  |
| 490 | "Rate limits (`max_queries_per_hour`, section 11) are tracked per…" | pre-release | flows |  |
| 491 | "Privacy budgets are tracked per job (section 11)." | pre-release | flows |  |
| 492 | "Rotation is a config edit: add a new…" | pre-release | flows |  |
| 493 | "No flag day." | pre-release | flows |  |
| 494 | "Keys are unrestricted by default: any valid key…" | pre-release | flows |  |
| 495 | "An optional `key_policies` object constrains what a key…" | pre-release | flows |  |
| 496 | "This matters most when the signer is an…" | pre-release | flows |  |
| 497 | "Every field is optional; every specified constraint must…" | pre-release | flows |  |
| 498 | "`allowed_kinds`: the job's `kind` must be listed." | pre-release | flows |  |
| 499 | "The same list governs the other doors a…" | pre-release | flows |  |
| 500 | "A policy that lists `allowed_kinds` admits a door only…" | pre-release | flows |  |
| 501 | "With `allowed_kinds: ["recipe"]` the key runs the named…" | pre-release | flows |  |
| 502 | "For a pinned script (see below), env vars…" | pre-release | flows |  |
| 503 | "Without it they are refused even when listed.…" | pre-release | flows |  |
| 504 | "Default off; only meaningful for keys with a…" | pre-release | flows |  |
| 505 | "For a pinned script, files not listed here…" | pre-release | flows |  |
| 506 | "Default `true` when absent. — `max_args`: integer cap on…" | pre-release | flows |  |
| 507 | "Args longer than 1024 characters are denied outright." | pre-release | flows |  |
| 508 | "The pattern is validated at startup and rejected…" | pre-release | flows |  |
| 509 | "Env, file, and arg constraints are hardening controls…" | pre-release | flows |  |
| 510 | "In `audit` mode the job runs and the decision…" | pre-release | flows |  |
| 511 | "With every mode `off` (the default), these fields are…" | pre-release | flows |  |
| 512 | "A pinned script is not the whole story…" | pre-release | flows |  |
| 513 | "Env names that subvert execution (the plan's Appendix…" | pre-release | flows |  |
| 514 | "The test suite backs this: a pinned script…" | pre-release | flows |  |
| 515 | "A policy may also be attached to the…" | pre-release | flows |  |
| 516 | "It binds the default key at every door…" | pre-release | flows |  |
| 517 | "Violations are rejected like any other bad job…" | pre-release | flows |  |
| 518 | "At the query door the sender also gets…" | pre-release | flows |  |
| 519 | "Keys without a policy entry behave exactly as…" | pre-release | flows |  |
| 520 | "Two guards against a forgotten entry." | pre-release | flows |  |
| 521 | "At startup the runner logs a warning naming…" | pre-release | flows |  |
| 522 | "And `key_policies_default_deny` (default false) flips the default for…" | pre-release | flows |  |
| 523 | "The default stays loose; strict is opt-in." | pre-release | flows |  |
| 524 | "The default key is never affected by the…" | pre-release | flows |  |
| 525 | "A policy is a property of the key…" | pre-release | flows |  |
| 526 | "A secret's name by default is its fingerprint…" | pre-release | flows |  |
| 527 | "Anyone holding the secret can compute it, so…" | pre-release | flows |  |
| 528 | "The runner's default key answers to its fingerprint…" | pre-release | flows |  |
| 529 | "An additional key keeps the name the operator…" | pre-release | flows |  |
| 530 | "The operator's name stays the one the key…" | pre-release | flows |  |
| 531 | "A chosen name for the runner's own key…" | pre-release | flows |  |
| 532 | "Every rule that knows a key by name — its…" | pre-release | flows |  |
| 533 | "Names travel in the open." | pre-release | flows |  |
| 534 | "A result names the key that verified its…" | pre-release | flows |  |
| 535 | "That is safe by construction, and the reasoning…" | pre-release | flows |  |
| 536 | "A name is a label, like a user name…" | pre-release | flows |  |
| 537 | "Learning a name tells an attacker which key…" | pre-release | flows |  |
| 538 | "It cannot be inverted, and as an oracle…" | pre-release | flows |  |
| 539 | "The reference sender keeps a keyring (`send_job.py keyring add|list|…" | pre-release | flows |  |
| 540 | "A runner may hold a panic word: six…" | pre-release | flows |  |
| 541 | "The runner keeps only" | pre-release | flagged | Sentence split by the formatting around the panic subject example; it continues across units 542-544 and cannot be judged as it stands |
| 542 | "with a 32-octet random salt, in `panic.json` in…" | pre-release | flows | Continuation of the sentence begun at unit 541 |
| 543 | "A message on any transport whose subject is…" | pre-release | flows | Continuation of the sentence spanning units 541-544 |
| 544 | "fires it." | pre-release | flows | End of the sentence spanning units 541-544 |
| 545 | "The prefix and the verb are matched without…" | pre-release | flows |  |
| 546 | "A subject with anything before the prefix (`Re:`…" | pre-release | flows |  |
| 547 | "The check is made on intake, before the…" | pre-release | flows |  |
| 548 | "It therefore works when the shared secret is…" | pre-release | flows |  |
| 549 | "When it fires, the runner stops every running…" | pre-release | flows |  |
| 550 | "It sends nothing: no reply to the panic…" | pre-release | flows |  |
| 551 | "The word is spent once sent, since anyone…" | pre-release | flows |  |
| 552 | "A dry run logs the match and fires…" | pre-release | flows |  |
| 553 | "No message re-arms a runner." | pre-release | flows |  |
| 554 | "The owner runs `install.py --rearm` on the box, which…" | pre-release | flows |  |
| 555 | "The word protects only where a job cannot…" | pre-release | flows |  |
| 556 | "Where jobs run as the runner's own user…" | pre-release | flows |  |
| 557 | "A key's name says which secret signed a…" | pre-release | flows |  |
| 558 | "It is one object, inline as `key_directory` or in…" | pre-release | flows |  |
| 559 | "Never the secret." | pre-release | flows |  |
| 560 | "An entry carries `state` and may carry `fingerprint`, `not_before`…" | pre-release | flows |  |
| 561 | "The states, in a key's life order: `ordered`, `generated`…" | pre-release | flows |  |
| 562 | "What each does:" | pre-release | flows |  |
| 563 | "`in_use` verifies, until its `not_after` when it carries…" | pre-release | flows |  |
| 564 | "One key, one entry: a key with entries…" | pre-release | flows |  |
| 565 | "The runner checks the whole directory at startup…" | pre-release | flows |  |
| 566 | "The verdict comes first, before the key's policy…" | pre-release | flows |  |
| 567 | "The directory is read at each check, so…" | pre-release | flows |  |
| 568 | "The hosted queue's Worker reads its own tenant…" | pre-release | flows |  |
| 569 | "Rotation is unchanged: add the new key, hand…" | pre-release | flows |  |
| 570 | "This section was the work plan." | pre-release | flows |  |
| 571 | "The boxes below shipped." | pre-release | flows |  |
| 572 | "It is kept as the record of what…" | pre-release | flows |  |
| 573 | "It is not a proposal." | pre-release | flows |  |
| 574 | "`additional_secrets` config: parse, entropy-gate every secret at startup…" | pre-release | flows |  |
| 575 | "Unknown key IDs rejected before crypto. — Task board: persistent…" | pre-release | flows |  |
| 576 | "Survives restarts; a crashed Oracle re-offers claimed tasks…" | pre-release | flows |  |
| 577 | "The documentation items below were part of the…" | pre-release | flows |  |
| 578 | "All shipped; the four marked open on 2026-10-21…" | pre-release | flows |  |
| 579 | "README.md: Oracle section rewritten from "proposal" to real…" | pre-release | flagged | One extraction unit carrying the whole Documentation checklist — many statements merged into a single run, so no single lead-in or hand-off can be judged |
| 580 | "The Oracle sections are implemented. Shipped. — docs/archive/DOCKER.md: env…" | pre-release | flows |  |
| 581 | "This was the build order." | pre-release | flows |  |
| 582 | "It is finished." | pre-release | flows |  |
| 583 | "Config and verification first." | pre-release | flows |  |
| 584 | "Section 14 is the smallest backward-compatible piece and…" | pre-release | flows |  |
| 585 | "Then the task board and dispatch (section 13)." | pre-release | flows |  |
| 586 | "Then the privacy-preserving results (sections 9-12), the largest…" | pre-release | flows |  |
| 587 | "Docs ship with each piece, not after." | pre-release | flows |  |
| 588 | "The python script to compose transport message: … — Project…" | pre-release | flows |  |
| 589 | "On an installed runner it is `<state dir>/project/`." | pre-release | flows |  |
