# Findings — docs/infrastructure-documents/oracle/configuring-oracle.md

Source: docs/infrastructure-documents/oracle/configuring-oracle.md, reviewed at main cbb52068.
Sentence units: 244. Flagged: 1. Categories: pre-release 239, post-release 5.

The document is a config-key reference: each entry leads with its key name and completes in the sentences that follow; those leads are recorded as flows. Unit 187 is the flag table's header row, flagged; the rows under it are content. Units 241-242 are lead-ins to the code blocks that follow them.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The Oracle is controlled entirely by `config.json`." | pre-release | flows |  |
| 2 | "The dashboard is listed in docs/FUTURE.md. `--oracle` opens…" | post-release | flows |  |
| 3 | "Neither edits these keys, and neither polls the…" | pre-release | flows |  |
| 4 | "Run the runner without `--oracle` (or the installed…" | pre-release | flows |  |
| 5 | "When a dashboard exists, it must be a…" | post-release | flows |  |
| 6 | "An explicit `base_dir` in the config wins." | pre-release | flows |  |
| 7 | "Otherwise the runner keeps its state (retained job…" | pre-release | flows |  |
| 8 | "That way the installed service (which often runs…" | pre-release | flows |  |
| 9 | "If you point two runs at two different…" | pre-release | flows |  |
| 10 | "On a test box (deterministic mode, 2,248 graded…" | pre-release | flows |  |
| 11 | "Its real lines and numbers are in live-examples.md." | pre-release | flows |  |
| 12 | "Everything the dashboard configures must be expressible in…" | post-release | flows |  |
| 13 | "No GUI-only settings, ever." | post-release | flows |  |
| 14 | "The config file remains the source of truth." | pre-release | flows |  |
| 15 | "A key that is absent reads as its…" | pre-release | flows |  |
| 16 | "A key that is present but not usable…" | pre-release | flows |  |
| 17 | "The decision, made 2026-10-23 and recorded in `docs/design/present-but-invalid-config.md`,…" | pre-release | flows |  |
| 18 | "`max_result_view` — the narrowest view the runner will…" | pre-release | flows |  |
| 19 | "A job can request a narrower view; it…" | pre-release | flows |  |
| 20 | "`max_query_budget` — the most queries that may be…" | pre-release | flows |  |
| 21 | "The job's own `query_budget` can only lower this…" | pre-release | flows |  |
| 22 | "`max_queries_per_hour` — rate limit on query follow-ups." | pre-release | flows |  |
| 23 | "Zero means no limit." | pre-release | flows |  |
| 24 | "`output_retention_days` — how long retained outputs are kept…" | pre-release | flows |  |
| 25 | "Default 7." | pre-release | flows |  |
| 26 | "Zero (or negative) keeps them indefinitely: nothing is…" | pre-release | flows |  |
| 27 | "`judge` — `off` (default), `advisory` (attach reasons, still…" | pre-release | flows |  |
| 28 | "`workspace_root` — directory the confinement snapshot treats as…" | pre-release | flows |  |
| 29 | "Empty means the snapshot is unconfigured." | pre-release | flows |  |
| 30 | "That snapshot does not stop a write." | pre-release | flows |  |
| 31 | "Linux bubblewrap is a separate switch, `security.modes.confinement`, at…" | pre-release | flows |  |
| 32 | "See SECURITY.md." | pre-release | flows |  |
| 33 | "`protected_paths` — list of absolute paths the confinement…" | pre-release | flows |  |
| 34 | "Any create/modify/delete under these paths is reported in…" | pre-release | flows |  |
| 35 | "Default empty (least restrictive)." | pre-release | flows |  |
| 36 | "`redact_patterns_extra` — additional named regexes treated as secrets…" | pre-release | flows |  |
| 37 | "Built-in families (`aws_key`, `private_key`, `bearer_token`) are always present." | pre-release | flows |  |
| 38 | "`worker_allowlist` — worker IDs allowed to pull tasks." | pre-release | flows |  |
| 39 | "Empty means any signed worker." | pre-release | flows |  |
| 40 | "`worker_compartments` — map of worker ID to compartment…" | pre-release | flows |  |
| 41 | "A task with compartments is visible only to…" | pre-release | flows |  |
| 42 | "`dag_mode` — `off` (default), `advisory`, or `enforce`." | pre-release | flows |  |
| 43 | "When enforce, a task is offered only after…" | pre-release | flows |  |
| 44 | "When advisory, the task is offered anyway and…" | pre-release | flows |  |
| 45 | "When off, dependencies are listed in the task…" | pre-release | flows |  |
| 46 | "Any other value behaves as `off`." | pre-release | flows |  |
| 47 | "`task_timeout` — seconds before a claimed task is…" | pre-release | flows |  |
| 48 | "Default 86400." | pre-release | flows |  |
| 49 | "`require_review` — when true, completed tasks go to…" | pre-release | flows |  |
| 50 | "`inference` — endpoint and model for the `ask`…" | pre-release | flows |  |
| 51 | "The endpoint must be loopback or the op…" | pre-release | flows |  |
| 52 | "A non-loopback host is refused and `ask` stays…" | pre-release | flows |  |
| 53 | "The installer sets this up by default (Ollama…" | pre-release | flows |  |
| 54 | "The default model is `qwen3:1.7b`." | pre-release | flows |  |
| 55 | "The `pi-light` profile (the Raspberry Pi install) sets…" | pre-release | flows |  |
| 56 | "On the runner, `--faster` uses `qwen2.5:3b` for one…" | pre-release | flows |  |
| 57 | "Sub-keys: `endpoint` (loopback URL, required), `model` (tag, required),…" | pre-release | flows |  |
| 58 | "`oracle_mode` — `llm` (default) or `deterministic`." | pre-release | flows |  |
| 59 | "Deterministic is the Pi Light mode: no local…" | pre-release | flows |  |
| 60 | "The `ask` op stays off in this mode." | pre-release | flows |  |
| 61 | "Read live: editing `config.json` flips the mode without…" | pre-release | flows |  |
| 62 | "`protocol_v2` — default off." | pre-release | flows |  |
| 63 | "When true, a job that is not a…" | pre-release | flows |  |
| 64 | "The answer, from any holder of a trusted…" | pre-release | flows |  |
| 65 | "It does not change what runs. `v2_answer_deadline_sec` is…" | pre-release | flows |  |
| 66 | "`answer_only` — default off." | pre-release | flows |  |
| 67 | "The laptop that thinks for a Pi: answer…" | pre-release | flows |  |
| 68 | "The Pi does not learn a separate role;…" | pre-release | flows |  |
| 69 | "`oracle_opinion_mode` — `off`, `diagnose`, `advise`, or `repair` (default)." | pre-release | flows |  |
| 70 | "The Oracle's opinion on each result (PROTOCOL 3.2):…" | pre-release | flows |  |
| 71 | "This key is both the default latitude for…" | pre-release | flows |  |
| 72 | "The runner flag `--oracle-opinion ` overrides this key…" | pre-release | flows |  |
| 73 | "`oracle_opinion_predict` — `requested` (default), `always`, or `never`." | pre-release | flows |  |
| 74 | "When tier-1 predictions are computed: only when the…" | pre-release | flows |  |
| 75 | "Diagnose needs no prediction and runs on any…" | pre-release | flows |  |
| 76 | "`oracle_opinion_model` — when true and inference is configured,…" | pre-release | flows |  |
| 77 | "Default false." | pre-release | flows |  |
| 78 | "Deterministic `oracle_mode` never calls a model, so tier-1…" | pre-release | flows |  |
| 79 | "`oracle_opinion_repair` — `rejudge` (default) or `refuse`." | pre-release | flows |  |
| 80 | "How a repair is authorized: the repaired job…" | pre-release | flows |  |
| 81 | "`oracle_learning` — the Oracle's self-learning loop (design: `docs/design/oracle-opinion-design.md`)." | pre-release | flows |  |
| 82 | "Every opinion call is frozen before the job…" | pre-release | flows |  |
| 83 | "A lesson never authorizes anything by itself: repairs…" | pre-release | flows |  |
| 84 | "Default `true`; `false` turns the loop off entirely…" | pre-release | flows |  |
| 85 | "At `oracle_opinion_mode` `off`, nothing is recorded or used…" | pre-release | flows |  |
| 86 | "`oracle_learning_model` — the model channel of the learning…" | pre-release | flows |  |
| 87 | "Candidates are hypotheses — labeled uncorroborated wherever they…" | pre-release | flows |  |
| 88 | "Default `false`." | pre-release | flows |  |
| 89 | "Deterministic `oracle_mode` never calls a model, so a…" | pre-release | flows |  |
| 90 | "`oracle_learning_promote_after` — how many verified corroborating outcomes a…" | pre-release | flows |  |
| 91 | "A single verified contradiction retires a candidate as…" | pre-release | flows |  |
| 92 | "Default `2`." | pre-release | flows |  |
| 93 | "`log_max_bytes` — size at which `runner.log` rotates." | pre-release | flows |  |
| 94 | "Default 33554432 (32 MiB)." | pre-release | flows |  |
| 95 | "An invalid value falls back to the default." | pre-release | flows |  |
| 96 | "`log_backups` — rotated `runner.log` files kept (`runner.log.1` ……" | pre-release | flows |  |
| 97 | "Default 4; a value below 1 falls back…" | pre-release | flows |  |
| 98 | "`oracle_log` — when true, every inference exchange is…" | pre-release | flows |  |
| 99 | "A debugging aid; off by default, and no…" | pre-release | flows |  |
| 100 | "`oracle_log_max_bytes` — size at which `oracle.log` rotates." | pre-release | flows |  |
| 101 | "Default 536870912 (512 MiB); with the default backups…" | pre-release | flows |  |
| 102 | "`oracle_log_backups` — rotated `oracle.log` files kept." | pre-release | flows |  |
| 103 | "Default 4; a value below 1 falls back…" | pre-release | flows |  |
| 104 | "`extension_review` — the extension review (docs/extend/extensions.md, "The review"):…" | pre-release | flows |  |
| 105 | "Anything else is a config error at startup." | pre-release | flows |  |
| 106 | "Verdicts are written to `/extension-review.json`; `--inspect review` reads…" | pre-release | flows |  |
| 107 | "`extension_sources` — the code each extension runs, and…" | pre-release | flows |  |
| 108 | "Read live. `--inspect sources` shows the state; `--fetch-sources`…" | pre-release | flows |  |
| 109 | "`verbose` — `true` turns on the verbose decision…" | pre-release | flows |  |
| 110 | "The command line (`-v` / `--quiet`) wins over…" | pre-release | flows |  |
| 111 | "`transports` — the enabled transport extensions: a list…" | pre-release | flows |  |
| 112 | "Every transport is a standalone extension program the…" | pre-release | flows |  |
| 113 | "Default `["email"]` — email is the default transport,…" | pre-release | flows |  |
| 114 | "The runner flag `--transports` replaces the list for…" | pre-release | flows |  |
| 115 | "Any name with a valid transport manifest (api_version…" | pre-release | flows |  |
| 116 | "See docs/extend/transports.md." | pre-release | flows |  |
| 117 | "`transport_file` — the file transport extension's folders: `inbox_dir`,…" | pre-release | flows |  |
| 118 | "Empty means `/transport-file/inbox` and `/transport-file/outbox`; relative paths resolve…" | pre-release | flows |  |
| 119 | "The block is handed to the file extension;…" | pre-release | flows |  |
| 120 | "A job envelope dropped in the inbox is…" | pre-release | flows |  |
| 121 | "The inbox folder's OS access control is this…" | pre-release | flows |  |
| 122 | "`transport_nats` — core NATS, handed to the NATS…" | pre-release | flows |  |
| 123 | "Broker credentials — `user`/`password` or `token`; the config…" | pre-release | flows |  |
| 124 | "Configured in that default posture, it is the…" | pre-release | flows |  |
| 125 | "`job_encryption` — per-job encryption for result bodies (the…" | pre-release | flows |  |
| 126 | "Absent, results mirror the arriving job: an encrypted…" | pre-release | flows |  |
| 127 | "Set explicitly to `true`, every result is encrypted,…" | pre-release | flows |  |
| 128 | "Only the literal boolean `false` encrypts no results." | pre-release | flows |  |
| 129 | "Incoming jobs in clear text are refused by…" | pre-release | flows |  |
| 130 | "Cleartext acceptance is enabled only by the `--allow-cleartext`…" | pre-release | flows |  |
| 131 | "Authentication is unchanged in every posture: the signature…" | pre-release | flows |  |
| 132 | "This key governs result encryption only." | pre-release | flows |  |
| 133 | "Sender side: `send_job.py` encrypts by default and takes…" | pre-release | flows |  |
| 134 | "The construction has no forward secrecy: the key…" | pre-release | flows |  |
| 135 | "`transport_dtls` — the DTLS session binding (a binding…" | pre-release | flows |  |
| 136 | "Both are addressing values, so a value present…" | pre-release | flows |  |
| 137 | "This is the one transport that LISTENS: enabling…" | pre-release | flows |  |
| 138 | "The session's PSK is the shared secret itself…" | pre-release | flows |  |
| 139 | "Key exchange is ephemeral-only (forward secrecy enforced; see…" | pre-release | flows |  |
| 140 | "The client is `runner/cloud/send_dtls.py`." | pre-release | flows |  |
| 141 | "`dtls_greeting` — the DTLS platform disclosure tier: `none`,…" | pre-release | flows |  |
| 142 | "The platform payload rides in the server's EncryptedExtensions…" | pre-release | flows |  |
| 143 | "`mail_tls_required` — the email extension's TLS posture, handed…" | pre-release | flows |  |
| 144 | "The protocol draft's Transport Binding requires IMAP and…" | pre-release | flows |  |
| 145 | "Only the literal boolean `false` opens the escape…" | pre-release | flows |  |
| 146 | "Confidentiality of the object is the envelope, not…" | pre-release | flows |  |
| 147 | "No value of this option enables cleartext mail;…" | pre-release | flows |  |
| 148 | "Config-only, like the other mailbox keys — there…" | pre-release | flows |  |
| 149 | "In the required posture, TLS 1.2 sessions are…" | pre-release | flows |  |
| 150 | "`review_scan_bytes` — how many bytes of the script…" | pre-release | flows |  |
| 151 | "Default 65536." | pre-release | flows |  |
| 152 | "`result_stash_retention_sec` — how long a result that could…" | pre-release | flows |  |
| 153 | "Default 86400." | pre-release | flows |  |
| 154 | "At least 1; hot-reloaded." | pre-release | flows |  |
| 155 | "`result_resend_backoff_sec` — the least time between two delivery…" | pre-release | flows |  |
| 156 | "Default 60." | pre-release | flows |  |
| 157 | "At least 1; hot-reloaded." | pre-release | flows |  |
| 158 | "`max_result_bytes` — the cap on the serialized, encrypted,…" | pre-release | flows |  |
| 159 | "Default 5242880 (5 MiB; providers allow 10 to…" | pre-release | flows |  |
| 160 | "0 means unlimited; a value that is not…" | pre-release | flows |  |
| 161 | "If results stop arriving, `--inspect outbox` shows what…" | pre-release | flows |  |
| 162 | "`max_plan_steps` / `max_plan_timeout_sec` — caps the detection layer…" | pre-release | flows |  |
| 163 | "Advisory, like the rest of that module." | pre-release | flows |  |
| 164 | "`remediation_quarantine_max_jobs` / `remediation_quarantine_max_bytes` — bounds on the quarantine…" | pre-release | flows |  |
| 165 | "The other remediation keys — `remediation_mode`, `remediation_sample_sec`, `remediation_storm_ceiling`,…" | pre-release | flows |  |
| 166 | "`inference` sub-keys beyond the four above: `watch_system` (default…" | pre-release | flows |  |
| 167 | "`resources` — the built-in resource monitor (`runner/oracle/resources.py`), the…" | pre-release | flows |  |
| 168 | "A malformed block is a startup config error." | pre-release | flows |  |
| 169 | "`extension_poll_interval_sec` — inside any `transport_` block: seconds between…" | pre-release | flows |  |
| 170 | "Default 2; a usable number is clamped to…" | pre-release | flows |  |
| 171 | "The block is handed to the extension, so…" | pre-release | flows |  |
| 172 | "`transport_queues` — the hosted queue, handed to the…" | pre-release | flows |  |
| 173 | "The lease length is the Worker's `LEASE_MS`, not…" | pre-release | flows |  |
| 174 | "`recipes` — the owner's named scripts (PROTOCOL.md section…" | pre-release | flows |  |
| 175 | "A `kind: "recipe"` job names one and brings…" | pre-release | flows |  |
| 176 | "A malformed recipe, or a pattern that could…" | pre-release | flows |  |
| 177 | "Default: none." | pre-release | flows |  |
| 178 | "`change_repos` — the repositories a `kind: "change"` job…" | pre-release | flows |  |
| 179 | "A name is 1 to 64 of `A-Z…" | pre-release | flows |  |
| 180 | "Default: none, and a change job is refused." | pre-release | flows |  |
| 181 | "`result_chain` — the per-key result chain (PROTOCOL.md section…" | pre-release | flows |  |
| 182 | "Default true; `false` turns it off." | pre-release | flows |  |
| 183 | "`pong_platform` — the platform card's disclosure tier in…" | pre-release | flows |  |
| 184 | "At `standard` and `full` every result also carries…" | pre-release | flows |  |
| 185 | "Keys documented elsewhere: the mailbox keys (`mailbox_user`, `mailbox_password`,…" | pre-release | flows |  |
| 186 | "Every flag below replaces one config value for…" | pre-release | flows |  |
| 187 | "Flag ; Config key" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 188 | "`--poll-interval SECONDS` ; `poll_interval_sec`" | pre-release | flows |  |
| 189 | "`--timeout SECONDS` ; `default_timeout_sec`" | pre-release | flows |  |
| 190 | "`--max-output-bytes BYTES` ; `max_output_bytes`" | pre-release | flows |  |
| 191 | "`--max-job-age SECONDS` ; `max_job_age_sec`" | pre-release | flows |  |
| 192 | "`--retention-days DAYS` ; `output_retention_days`" | pre-release | flows |  |
| 193 | "`--task-timeout SECONDS` ; `task_timeout`" | pre-release | flows |  |
| 194 | "`--max-query-budget COUNT` ; `max_query_budget`" | pre-release | flows |  |
| 195 | "`--max-queries-per-hour COUNT` ; `max_queries_per_hour`" | pre-release | flows |  |
| 196 | "`--max-result-view MODE` ; `max_result_view`" | pre-release | flows |  |
| 197 | "`--judge MODE` ; `judge`" | pre-release | flows |  |
| 198 | "`--dag-mode MODE` ; `dag_mode`" | pre-release | flows |  |
| 199 | "`--oracle-mode MODE` ; `oracle_mode`" | pre-release | flows |  |
| 200 | "`--protocol-v2` ; `protocol_v2`" | pre-release | flows |  |
| 201 | "`--answer-only` ; `answer_only`" | pre-release | flows |  |
| 202 | "`--require-review` / `--no-require-review` ; `require_review`" | pre-release | flows |  |
| 203 | "`--local-signals` / `--no-local-signals` ; `local_signals`" | pre-release | flows |  |
| 204 | "`--local-signal-port PORT` ; `local_signal_port`" | pre-release | flows |  |
| 205 | "`--wake-cooldown SECONDS` ; `local_wake_cooldown_sec`" | pre-release | flows |  |
| 206 | "`--log-max-bytes BYTES` ; `log_max_bytes`" | pre-release | flows |  |
| 207 | "`--log-backups COUNT` ; `log_backups`" | pre-release | flows |  |
| 208 | "`--oracle-log` / `--no-oracle-log` ; `oracle_log`" | pre-release | flows |  |
| 209 | "`--oracle-log-max-bytes BYTES` ; `oracle_log_max_bytes`" | pre-release | flows |  |
| 210 | "`--oracle-log-backups COUNT` ; `oracle_log_backups`" | pre-release | flows |  |
| 211 | "`--oracle-opinion MODE` ; `oracle_opinion_mode`" | pre-release | flows |  |
| 212 | "`--remediation-mode MODE` ; `remediation_mode`" | pre-release | flows |  |
| 213 | "`--transports LIST` ; `transports`" | pre-release | flows |  |
| 214 | "`-v` / `--quiet` ; `verbose`" | pre-release | flows |  |
| 215 | "`--workers COUNT` and `--faster` are the two older…" | pre-release | flows |  |
| 216 | "A profile is an ordinary config bundle that…" | pre-release | flows |  |
| 217 | "Worked example: a Raspberry Pi running a VS…" | pre-release | flows |  |
| 218 | "The owner wants the Oracle to treat VS…" | pre-release | flows |  |
| 219 | "The result is a normal config file." | pre-release | flows |  |
| 220 | "It can be edited by hand; there is…" | post-release | flows |  |
| 221 | "The installer applies a profile automatically." | pre-release | flows |  |
| 222 | "On a Raspberry Pi it selects `pi-light`; everywhere…" | pre-release | flows |  |
| 223 | "Pass `--profile NAME` to override, or `--no-profile` to…" | pre-release | flows |  |
| 224 | "You can still name one explicitly:" | pre-release | flows |  |
| 225 | "Built-in profiles:" | pre-release | flows |  |
| 226 | "`password-only` — treats password hashes and `password=` style…" | pre-release | flows |  |
| 227 | "Inference stays on the default model, `qwen3:1.7b`." | pre-release | flows |  |
| 228 | "`pi-light` — same password-hash watch, plus `/home/pi/docs/manuals` as…" | pre-release | flows |  |
| 229 | "This is the Pi-specific install: the device tree…" | pre-release | flows |  |
| 230 | "It is the light package — it sets…" | pre-release | flows |  |
| 231 | "Naming `--inference-model` or `--faster` by hand overrides that…" | pre-release | flows |  |
| 232 | "A profile JSON file uses the same keys." | pre-release | flows |  |
| 233 | "Extra redact patterns and worker compartments are merged…" | pre-release | flows |  |
| 234 | "A profile entry wins when the name clashes." | pre-release | flows |  |
| 235 | "Beyond the merged dicts, only a fixed whitelist…" | pre-release | flows |  |
| 236 | "Mailbox credentials and `shared_secret` are never written by…" | pre-release | flows |  |
| 237 | "The runner already honors `redact_patterns_extra`, `protected_paths`, and `max_result_view`…" | pre-release | flows |  |
| 238 | "A plain human-readable string describing this box." | pre-release | flows |  |
| 239 | "It is not a profile." | pre-release | flows |  |
| 240 | "The installer stores it in `config.json` as `owner_instructions`,…" | pre-release | flows |  |
| 241 | "Replace the string:" | pre-release | flows |  |
| 242 | "Append a paragraph:" | pre-release | flows |  |
| 243 | "Re-running the installer with `--instructions` replaces the whole…" | pre-release | flows |  |
| 244 | "Mailbox credentials are untouched." | pre-release | flows |  |
