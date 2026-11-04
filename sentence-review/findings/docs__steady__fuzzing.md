# Findings — docs/steady/fuzzing.md

Source: docs/steady/fuzzing.md, reviewed at main f63a7af8.
Sentence units: 248. Flagged: 0. Categories: pre-release 248, post-release 0.

The fuzzing record: the standing rule first (a refusal is a string, a crash is a bug), then the crash shapes found and closed, then the rings — each bad input paired with the next good one still working — and the campaign's standing orders at the end. It is 248 units of uniform declarative prose with no tables, images, or labels; every unit is a full sentence and the chain is the argument itself, finding to fix to next ring. Nothing is flagged.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "The Oracle takes input from sensors, extensions, the…" | pre-release | flows |  |
| 2 | "A refusal is a string." | pre-release | flows |  |
| 3 | "A crash is a bug." | pre-release | flows |  |
| 4 | "The tests that hold that rule are in-memory." | pre-release | flows |  |
| 5 | "They open no socket and they load no…" | pre-release | flows |  |
| 6 | "One shape of crash, over and over: a…" | pre-release | flows |  |
| 7 | "Later, under de_dust2 (29-OCT), a shape no crash…" | pre-release | flows |  |
| 8 | "`_object_start` in both signed-object extractors tried every `{`…" | pre-release | flows |  |
| 9 | "The ledger had carried the symptom as `slowest_ms`…" | pre-release | flows |  |
| 10 | "A measurement without a filing rule finds nothing." | pre-release | flows |  |
| 11 | "`check_key_policy` raised `TypeError` on a key id that…" | pre-release | flows |  |
| 12 | "A key id that is not a string…" | pre-release | flows |  |
| 13 | "`parse_sensors` raised `TypeError` when `severity_floor` was not a…" | pre-release | flows |  |
| 14 | "A config file can carry that." | pre-release | flows |  |
| 15 | "It is now a config error, the same…" | pre-release | flows |  |
| 16 | "`validate_sensor_alert` raised `TypeError` when `severity` was a list." | pre-release | flows |  |
| 17 | "A signed alert can carry that." | pre-release | flows |  |
| 18 | "It is now a refusal, same as any…" | pre-release | flows |  |
| 19 | "`parse_manifest` raised `TypeError` when `kind` was not a…" | pre-release | flows |  |
| 20 | "A non-string kind is now a refusal." | pre-release | flows |  |
| 21 | "The same check was open in three more…" | pre-release | flows |  |
| 22 | "A non-string is a refusal or a config…" | pre-release | flows |  |
| 23 | "`baseline_anomaly` summed `kinds` with `sum()` and then used…" | pre-release | flows |  |
| 24 | "A stored baseline whose counts are not numbers,…" | pre-release | flows |  |
| 25 | "Counts that are not finite numbers are skipped,…" | pre-release | flows |  |
| 26 | "`feature_keys` and `touched_keys` called `.items()` on `tools` and…" | pre-release | flows |  |
| 27 | "A probe that handed back a string or…" | pre-release | flows |  |
| 28 | "Those fields are used only when they have…" | pre-release | flows |  |
| 29 | "Ring 2 has started for sensor alerts." | pre-release | flows |  |
| 30 | "A flipped signature stores no alert." | pre-release | flows |  |
| 31 | "A signed alert whose severity is a list…" | pre-release | flows |  |
| 32 | "The next good alert, in the same directory,…" | pre-release | flows |  |
| 33 | "The same rule holds for a job: a…" | pre-release | flows |  |
| 34 | "A second wrap around an envelope does not…" | pre-release | flows |  |
| 35 | "A key bound to sensor alerts only cannot…" | pre-release | flows |  |
| 36 | "A script over `max_script_bytes` does not run, and…" | pre-release | flows |  |
| 37 | "A flipped query learns nothing from retained output." | pre-release | flows |  |
| 38 | "The next good query of the same output…" | pre-release | flows |  |
| 39 | "That gap is closed." | pre-release | flows |  |
| 40 | "A query and a board message now go…" | pre-release | flows |  |
| 41 | "Cleartext is refused unless the process was started…" | pre-release | flows |  |
| 42 | "An encrypted query is answered, and the answer…" | pre-release | flows |  |
| 43 | "An encrypted submit opens the task." | pre-release | flows |  |
| 44 | "A cleartext submit does not." | pre-release | flows |  |
| 45 | "A job stamped two hours ago, or an…" | pre-release | flows |  |
| 46 | "The window is `max_job_age_sec`, with five minutes of…" | pre-release | flows |  |
| 47 | "The next job stamped now still runs." | pre-release | flows |  |
| 48 | "A file named `../escaped.txt` is not staged and…" | pre-release | flows |  |
| 49 | "The next ordinary job still does." | pre-release | flows |  |
| 50 | "A body whose `job_id` is not the id…" | pre-release | flows |  |
| 51 | "The envelope still decrypts." | pre-release | flows |  |
| 52 | "The ids are what fail." | pre-release | flows |  |
| 53 | "A `reply_to` that is not one address does…" | pre-release | flows |  |
| 54 | "A newline, a comma, or a list falls…" | pre-release | flows |  |
| 55 | "One plain address is honored, because it was…" | pre-release | flows |  |
| 56 | "A job cannot put a `PIGEON_` variable into…" | pre-release | flows |  |
| 57 | "Any other name it sets is still there." | pre-release | flows |  |
| 58 | "The next ordinary job still runs." | pre-release | flows |  |
| 59 | "The same job submitted again does not run…" | pre-release | flows |  |
| 60 | "A different job id still does." | pre-release | flows |  |
| 61 | "An envelope signed with one key, around a…" | pre-release | flows |  |
| 62 | "The next job whose keys agree still does." | pre-release | flows |  |
| 63 | "A job aimed at a different runner, or…" | pre-release | flows |  |
| 64 | "The job that names this runner still does." | pre-release | flows |  |
| 65 | "A `script_url` of `file:` is not fetched, in…" | pre-release | flows |  |
| 66 | "The next ordinary job still does." | pre-release | flows |  |
| 67 | "A null byte in an argument or an…" | pre-release | flows |  |
| 68 | "A null byte in the interpreter is not…" | pre-release | flows |  |
| 69 | "The path is absent, repair is the default,…" | pre-release | flows |  |
| 70 | "The Python script does not run under that…" | pre-release | flows |  |
| 71 | "The next ordinary job still does." | pre-release | flows |  |
| 72 | "A ping that carries a script answers `pong`…" | pre-release | flows |  |
| 73 | "The next exec job still does." | pre-release | flows |  |
| 74 | "A kind the runner does not know (`sh`,…" | pre-release | flows |  |
| 75 | "The next exec job still does." | pre-release | flows |  |
| 76 | "A script that is a number, or a…" | pre-release | flows |  |
| 77 | "The next exec job still does." | pre-release | flows |  |
| 78 | "A `script_sha384` that does not match the script…" | pre-release | flows |  |
| 79 | "The same script with the right hash does." | pre-release | flows |  |
| 80 | "A hash that is a number does not…" | pre-release | flows |  |
| 81 | "The same hash in capitals does, because the…" | pre-release | flows |  |
| 82 | "A timeout of `slow` or a list does…" | pre-release | flows |  |
| 83 | "A timeout of `0` is read as missing,…" | pre-release | flows |  |
| 84 | "Args that are a string or a number…" | pre-release | flows |  |
| 85 | "Args of `0` are read as missing, so…" | pre-release | flows |  |
| 86 | "An env that is a string or a…" | pre-release | flows |  |
| 87 | "An env of `0` is read as missing,…" | pre-release | flows |  |
| 88 | "Files that are a string, or an entry…" | pre-release | flows |  |
| 89 | "Files of `0` are read as missing, so…" | pre-release | flows |  |
| 90 | "An interpreter that is a string or a…" | pre-release | flows |  |
| 91 | "An empty list is read as missing." | pre-release | flows |  |
| 92 | "The platform shell is started, and the Python…" | pre-release | flows |  |
| 93 | "The next job with an interpreter still does." | pre-release | flows |  |
| 94 | "The same query is answered once." | pre-release | flows |  |
| 95 | "The second copy, same seen set, gets nothing…" | pre-release | flows |  |
| 96 | "A second query, different id, after the budget…" | pre-release | flows |  |
| 97 | "The answer says budget." | pre-release | flows |  |
| 98 | "A query aimed at a different job does…" | pre-release | flows |  |
| 99 | "The answer says unknown." | pre-release | flows |  |
| 100 | "The query for this job still does." | pre-release | flows |  |
| 101 | "After `max_queries_per_hour` is spent, the next query is…" | pre-release | flows |  |
| 102 | "An unknown op, even one that carries the…" | pre-release | flows |  |
| 103 | "It does not get the canary." | pre-release | flows |  |
| 104 | "A later grep of this job still does." | pre-release | flows |  |
| 105 | "A pattern that does not compile is `bad_pattern`…" | pre-release | flows |  |
| 106 | "A pattern the shape check lets through, and…" | pre-release | flows |  |
| 107 | "A later good grep still does." | pre-release | flows |  |
| 108 | "A retained view of `summary` or `attested` does…" | pre-release | flows |  |
| 109 | "The answer says policy." | pre-release | flows |  |
| 110 | "`full` still does." | pre-release | flows |  |
| 111 | "`redacted`, with the canary as a pattern, returns…" | pre-release | flows |  |
| 112 | "The pattern the query itself sent is echoed." | pre-release | flows |  |
| 113 | "`full` still returns the canary." | pre-release | flows |  |
| 114 | "A `max_matches` of zero returns no lines, and…" | pre-release | flows |  |
| 115 | "A later grep with the default limit still…" | pre-release | flows |  |
| 116 | "An `ask` whose question says to print the…" | pre-release | flows |  |
| 117 | "The output is not copied into the answer." | pre-release | flows |  |
| 118 | "A later grep still returns the canary." | pre-release | flows |  |
| 119 | "Grep searches stderr as well as stdout." | pre-release | flows |  |
| 120 | "A pattern that matches only stdout does not…" | pre-release | flows |  |
| 121 | "A `queries` value that is not a list,…" | pre-release | flows |  |
| 122 | "The answer is empty." | pre-release | flows |  |
| 123 | "A later grep still returns the canary." | pre-release | flows |  |
| 124 | "A record whose `saved_at` is older than the…" | pre-release | flows |  |
| 125 | "A fresh `saved_at` still does." | pre-release | flows |  |
| 126 | "An open task is not finished by a…" | pre-release | flows |  |
| 127 | "It has to be claimed first." | pre-release | flows |  |
| 128 | "A later submit still opens." | pre-release | flows |  |
| 129 | "A second submit of the same task does…" | pre-release | flows |  |
| 130 | "The first payload stays." | pre-release | flows |  |
| 131 | "A different task still opens." | pre-release | flows |  |
| 132 | "Once a task is claimed, a result finishes…" | pre-release | flows |  |
| 133 | "A later submit still opens." | pre-release | flows |  |
| 134 | "With review required, a result holds the task…" | pre-release | flows |  |
| 135 | "An approval is what marks it done." | pre-release | flows |  |
| 136 | "A worker whose capabilities do not cover the…" | pre-release | flows |  |
| 137 | "The worker who has them does." | pre-release | flows |  |
| 138 | "A worker who is not on `worker_allowlist` does…" | pre-release | flows |  |
| 139 | "The worker who is on the list does." | pre-release | flows |  |
| 140 | "A task in a compartment the worker does…" | pre-release | flows |  |
| 141 | "The worker who shares it claims." | pre-release | flows |  |
| 142 | "A task id with a slash, or longer…" | pre-release | flows |  |
| 143 | "A plain id still opens." | pre-release | flows |  |
| 144 | "With `dag_mode` enforce, a task whose requirement is…" | pre-release | flows |  |
| 145 | "Once that requirement is done, a request claims…" | pre-release | flows |  |
| 146 | "Advisory hands the same shape out, and the…" | pre-release | flows |  |
| 147 | "A higher `priority` is claimed first, even when…" | pre-release | flows |  |
| 148 | "The lower one stays open." | pre-release | flows |  |
| 149 | "A priority of `true` is stored, and it…" | pre-release | flows |  |
| 150 | "A worker who already holds a claim is…" | pre-release | flows |  |
| 151 | "A different worker gets the newer one." | pre-release | flows |  |
| 152 | "Capabilities that are not a list of strings…" | pre-release | flows |  |
| 153 | "A task that omits them still opens." | pre-release | flows |  |
| 154 | "A priority of `"9"` or infinity opens nothing." | pre-release | flows |  |
| 155 | "A priority of `1` still opens." | pre-release | flows |  |
| 156 | "A claim older than `task_timeout` is offered again." | pre-release | flows |  |
| 157 | "The next request takes it, and the previous…" | pre-release | flows |  |
| 158 | "A claim inside `task_timeout` is not taken." | pre-release | flows |  |
| 159 | "A second worker's request leaves it with the…" | pre-release | flows |  |
| 160 | "A task in `pending_review` is not put back…" | pre-release | flows |  |
| 161 | "A later request can take a different open…" | pre-release | flows |  |
| 162 | "A NaN in a result is stored as…" | pre-release | flows |  |
| 163 | "A second result does not replace that null." | pre-release | flows |  |
| 164 | "The fork bomb in [runner/tests/test_flag321_obfuscated.py](../../runner/tests/test_flag321_obfuscated.py) is the pipe…" | pre-release | flows |  |
| 165 | "The judge denies that exact string and allows…" | pre-release | flows |  |
| 166 | "Nothing there is executed." | pre-release | flows |  |
| 167 | "Wrapping either string in "ignore previous instructions" does…" | pre-release | flows |  |
| 168 | "A stub model that obeys, and answers with…" | pre-release | flows |  |
| 169 | "The answer is not handed to a shell." | pre-release | flows |  |
| 170 | "A job-shaped answer with no canary comes back…" | pre-release | flows |  |
| 171 | "The format guard does not treat `{"kind","script"}` as…" | pre-release | flows |  |
| 172 | "The research notes, and where that premise stops,…" | pre-release | flows |  |
| 173 | "A short DTLS record raised `IndexError` inside the…" | pre-release | flows |  |
| 174 | "It now raises `DtlsError`, which the session already…" | pre-release | flows |  |
| 175 | "The crashes were easy because the generator was…" | pre-release | flows |  |
| 176 | "That pass is still worth finishing." | pre-release | flows |  |
| 177 | "It is not the whole surface." | pre-release | flows |  |
| 178 | "Ring 1 is anything already inside the process." | pre-release | flows |  |
| 179 | "The generator builds messy Python values, not just…" | pre-release | flows |  |
| 180 | "The property is: return a reason or `None`,…" | pre-release | flows |  |
| 181 | "This is where those `TypeError`s came from." | pre-release | flows |  |
| 182 | "The functions whose docstring says "never raises" (or…" | pre-release | flows |  |
| 183 | "Some ninety of them live under `runner/`, tests…" | pre-release | flows |  |
| 184 | "Ring 2 starts from a message the runner…" | pre-release | flows |  |
| 185 | "The families are a job, a sensor alert,…" | pre-release | flows |  |
| 186 | "The property is stricter than "it returned." | pre-release | flows |  |
| 187 | "A bad signature stores nothing." | pre-release | flows |  |
| 188 | "A rejected job does not run." | pre-release | flows |  |
| 189 | "A good neighbor in the same poll still…" | pre-release | flows |  |
| 190 | "One poison file does not stick the channel." | pre-release | flows |  |
| 191 | "Ring 3 is the parsers the coverage report…" | pre-release | flows |  |
| 192 | "`dtlsproto.py` wants mutated valid flights, not only random…" | pre-release | flows |  |
| 193 | "de_dust's `dtls` target is that flight (Q66): a…" | pre-release | flows |  |
| 194 | "Then the email, file, and NATS extension programs,…" | pre-release | flows |  |
| 195 | "Still in memory." | pre-release | flows |  |
| 196 | "A live socket is only worth it after…" | pre-release | flows |  |
| 197 | "`learning.py`, the posture collectors, and the model are…" | pre-release | flows |  |
| 198 | "Judgment is downstream of admission, and admission is…" | pre-release | flows |  |
| 199 | "`runner/tests/test_oracle_intake_fuzz.py` — ring 1 for alerts, manifests, key…" | pre-release | flows |  |
| 200 | "The tool named `run` is stubbed." | pre-release | flows |  |
| 201 | "The fuzzer must not grow a shell." | pre-release | flows |  |
| 202 | "`runner/tests/test_dtls_fuzz.py` — ring 3, started: random datagrams and…" | pre-release | flows |  |
| 203 | "`runner/tests/test_properties.py` — the older property tests on the…" | pre-release | flows |  |
| 204 | "Hypothesis is a test-only dependency." | pre-release | flows |  |
| 205 | "CI installs it." | pre-release | flows |  |
| 206 | "A run without it skips nothing in the…" | pre-release | flows |  |
| 207 | "The conductor asked this opinion thrown into the…" | pre-release | flows |  |
| 208 | "It is not a change to the rings…" | pre-release | flows |  |
| 209 | "The full read is the answer to Q65…" | pre-release | flows |  |
| 210 | "The desk applies what it takes." | pre-release | flows |  |
| 211 | "What follows is the part that would change…" | pre-release | flows |  |
| 212 | "In-memory fuzzing is the right tool, and it…" | pre-release | flows |  |
| 213 | "The six de_dust targets are saturated: at 3.13.50…" | pre-release | flows |  |
| 214 | "More rounds there will not find the next…" | pre-release | flows |  |
| 215 | "Ring 1 already found the type crashes." | pre-release | flows |  |
| 216 | "Leave those tests." | pre-release | flows |  |
| 217 | "Stop adding Hypothesis examples on functions that already…" | pre-release | flows |  |
| 218 | "The bounded campaigns (`test_fuzz_surfaces`, `test_fuzz_guided`, `test_fuzz_parsers`, `test_dtls_fuzz`, `test_transport_log_relay_fuzz`)…" | pre-release | flows |  |
| 219 | "Their corpora die with the process." | pre-release | flows |  |
| 220 | "Promote those readers into the one persistent corpus." | pre-release | flows |  |
| 221 | "Do not write a third fuzzer, and do…" | pre-release | flows |  |
| 222 | "The targets that followed, in order, all in…" | pre-release | flows |  |
| 223 | "Mail extraction (`mailbox.py`, `get_text_body`, subject parsing, and the…" | pre-release | flows |  |
| 224 | "This chooses the text the six verifiers see." | pre-release | flows |  |
| 225 | "DTLS record and handshake parse, from a sealed…" | pre-release | flows |  |
| 226 | "Random datagrams stay as the garbage regression only." | pre-release | flows |  |
| 227 | "The task board (`submit`, `offer`, `complete`)." | pre-release | flows |  |
| 228 | "NATS, queues, and file `fetch_channel_messages`." | pre-release | flows |  |
| 229 | "`parse_manifest`." | pre-release | flows |  |
| 230 | "Not next: the model, `learning.py`, posture, the Oracle's…" | pre-release | flows |  |
| 231 | "`build_bwrap_command` as argv, never exec'd, is as far…" | pre-release | flows |  |
| 232 | "Mail and DTLS need their own seeds and…" | pre-release | flows |  |
| 233 | "Brace noise and the text mutators will not…" | pre-release | flows |  |
| 234 | "The six, the board, and manifests keep the…" | pre-release | flows |  |
| 235 | "Two contracts the corpus should add, and replay…" | pre-release | flows |  |
| 236 | "The two verifiers agree." | pre-release | flows |  |
| 237 | "`runner/wire/verify.py` and `runner/cloud/send_job.py` both trust a body and…" | pre-release | flows |  |
| 238 | "A sequence." | pre-release | flows |  |
| 239 | "A bad message stores nothing, and the next…" | pre-release | flows |  |
| 240 | "The paragraphs above hold that for one shape…" | pre-release | flows |  |
| 241 | "The generator should produce the pair." | pre-release | flows |  |
| 242 | "Keep `sys.settrace`." | pre-release | flows |  |
| 243 | "A target with no new arc and no…" | pre-release | flows |  |
| 244 | "Section M's stop, two empty cycles then D4,…" | pre-release | flows |  |
| 245 | "D4 should not take the rig before that." | pre-release | flows |  |
| 246 | "The order that de_dust is the only effort…" | pre-release | flows |  |
| 247 | "No live socket until the new readers stop…" | pre-release | flows |  |
| 248 | "A Platinum percentage is coverage, not a reason…" | pre-release | flows |  |
