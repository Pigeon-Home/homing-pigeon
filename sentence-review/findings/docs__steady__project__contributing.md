# Findings — docs/steady/project/contributing.md

Source: docs/steady/project/contributing.md, reviewed at main cbb52068.
Sentence units: 279. Flagged: 2. Categories: pre-release 278, post-release 1.

The first half is the contributor and release guide; the second half is the maintenance record for the --oracle flag, written as numbered step lists and field lists under their lead-in sentences.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Thanks for stopping by." | pre-release | flows |  |
| 2 | "This is a small, security-sensitive project — a…" | pre-release | flows |  |
| 3 | "Here's how to do it well." | pre-release | flows |  |
| 4 | "**Read PROTOCOL.md first.** The wire protocol is the…" | pre-release | flows |  |
| 5 | "If your change alters what goes over the…" | pre-release | flows |  |
| 6 | "**Read the security model** (PROTOCOL.md §7 and SECURITY.md)." | pre-release | flows |  |
| 7 | "If your change touches authentication, signature verification, process…" | pre-release | flows |  |
| 8 | "**Standard library only.** The runner and installer ship…" | pre-release | flows |  |
| 9 | "No new third-party dependencies, ever." | pre-release | flows |  |
| 10 | "If you think you need one, open an…" | pre-release | flows |  |
| 11 | "**Cross-platform or it doesn't ship.** Every change must…" | pre-release | flows |  |
| 12 | "Use `os.name` / `sys.platform` branches, and think about…" | pre-release | flows |  |
| 13 | "**Tests or it didn't happen.** `python -m unittest…" | pre-release | flows |  |
| 14 | "New behavior gets a new test with the…" | pre-release | flows |  |
| 15 | "**No secrets in the repo.** Not in code,…" | pre-release | flows |  |
| 16 | "Test credentials stay obviously fake (`runner@example.com` and friends)." | pre-release | flows |  |
| 17 | "Fork the repo and create a branch with…" | pre-release | flows |  |
| 18 | "Make your change, add tests, update docs (README,…" | pre-release | flows |  |
| 19 | "Run the full suite: `python -m unittest discover…" | pre-release | flows |  |
| 20 | "Open a pull request against `main`." | pre-release | flows |  |
| 21 | "Describe **what** changed, **why**, and **what you tested**." | pre-release | flows |  |
| 22 | "If it touches anything listed under "Before you…" | pre-release | flows |  |
| 23 | "Plain, readable Python." | pre-release | flows |  |
| 24 | "Type hints where they help, not everywhere." | pre-release | flows |  |
| 25 | "Comments explain *why*, not *what*." | pre-release | flows |  |
| 26 | "Security-critical code gets a comment saying what attack…" | pre-release | flows |  |
| 27 | "Keep the security warning in the README loud." | pre-release | flows |  |
| 28 | "PRs that soften it will be asked to…" | pre-release | flows |  |
| 29 | "Use the bug report template." | pre-release | flows |  |
| 30 | "Include: platform, Python version (or which release binary),…" | pre-release | flows |  |
| 31 | "If it's a security issue, **do not** open…" | pre-release | flows |  |
| 32 | "(horizontal rule)" | pre-release | flagged | Horizontal rule standing alone; structure, not a sentence |
| 33 | "The PyPI publish job uploads `pigeon-home-runner-` taken from…" | pre-release | flows |  |
| 34 | "Before pushing a tag, bump `version` in `pyproject.toml`…" | pre-release | flows |  |
| 35 | "Tags on this repo are protected by a…" | pre-release | flows |  |
| 36 | "Bump `runner/_version.py` (`__version__`) in the same commit." | pre-release | flows |  |
| 37 | "Every CLI reports it via `--version`, and the…" | pre-release | flows |  |
| 38 | "Two more files carry the version and move…" | pre-release | flows |  |
| 39 | "A release commit touches all four." | pre-release | flows |  |
| 40 | "The release commit's author email is a no-reply…" | pre-release | flows |  |
| 41 | "Nothing pushes to this repository by itself." | pre-release | flows |  |
| 42 | "No rig pushes its own output — rigs…" | pre-release | flows |  |
| 43 | "No timer revs, tags, or ships a release." | pre-release | flows |  |
| 44 | "Pushes to `main` are made by the maintainer…" | pre-release | flows |  |
| 45 | "One automatic exception exists, and it is the…" | pre-release | flows |  |
| 46 | "A watch checks `main` every 5 minutes for…" | pre-release | flows |  |
| 47 | "The owner edits documents in bursts — several…" | pre-release | flows |  |
| 48 | "If edits keep arriving for 60 minutes it…" | pre-release | flows |  |
| 49 | "The release carries the whole burst." | pre-release | flows |  |
| 50 | "In practice: after editing a document, the owner…" | pre-release | flows |  |
| 51 | "An agent asked to make a release outside…" | pre-release | flows |  |
| 52 | "A pushed tag never moves; a defect is…" | pre-release | flows |  |
| 53 | "The SI can run the entire release pipeline:…" | pre-release | flows |  |
| 54 | "None of that ships without the owner's word." | pre-release | flows |  |
| 55 | "This is not a capability limit." | pre-release | flows |  |
| 56 | "The owner is the final integration environment: a…" | pre-release | flows |  |
| 57 | "The Oracle is not forbidden from approving its…" | pre-release | flows |  |
| 58 | "The looking is the gate." | pre-release | flows |  |
| 59 | "In practice: no push, tag, or release without…" | pre-release | flows |  |
| 60 | "The section below is history that bites." | pre-release | flows |  |
| 61 | "It is for the next person or bot…" | pre-release | flows |  |
| 62 | "This note is for the next person or…" | pre-release | flows |  |
| 63 | "The name is easy to get backwards." | pre-release | flows |  |
| 64 | "Read this before you edit `runner/runner.py`, the installer,…" | pre-release | flows |  |
| 65 | "There used to be a switch that turned…" | pre-release | flows |  |
| 66 | "There is now a switch that opens a…" | pre-release | flows |  |
| 67 | "They are not the same feature, they do…" | pre-release | flows |  |
| 68 | "Name ; What it was ; Status" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 69 | "`oracle_enabled` in `config.json` ; When false, the runner…" | pre-release | flows |  |
| 70 | "Default was true. ; Removed in `8f0719f`." | pre-release | flows |  |
| 71 | "`--no-oracle` on the CLI ; The command-line way…" | pre-release | flows |  |
| 72 | "The installer could forward it into the boot…" | pre-release | flows |  |
| 73 | "`--oracle` on the CLI ; Opens a loopback…" | pre-release | flows |  |
| 74 | "This is the flag that exists today." | pre-release | flows |  |
| 75 | "`--oracle-port` ; Port for that chat." | pre-release | flows |  |
| 76 | "Default `11436`." | pre-release | flows |  |
| 77 | "Bound to `127.0.0.1` only. ; Added with `--oracle`." | pre-release | flows |  |
| 78 | "If you find `oracle_enabled=false` in `docs/archive/verify-v31.md`, that file…" | pre-release | flows |  |
| 79 | "Those checks describe a flag that the code…" | pre-release | flows |  |
| 80 | "Do not reintroduce `oracle_enabled` or `--no-oracle` to make…" | pre-release | flows |  |
| 81 | "The README row for `--no-oracle` was a leftover…" | pre-release | flows |  |
| 82 | "Commit `8f0719f` (author ctf-gooo-003, message "v3: the Oracle…" | pre-release | flows |  |
| 83 | "The Oracle had already shipped." | pre-release | flows |  |
| 84 | "A flag that turned it off was a…" | pre-release | flows |  |
| 85 | "That escape hatch was the thing the project…" | pre-release | flows |  |
| 86 | "The commit deleted:" | pre-release | flows |  |
| 87 | "the `oracle_enabled` key (it had defaulted to true)" | pre-release | flows |  |
| 88 | "the `--no-oracle` CLI flag" | pre-release | flows |  |
| 89 | "the branches in query handling, board mail, and…" | pre-release | flows |  |
| 90 | "the key in `runner/config.example.json`" | pre-release | flows |  |
| 91 | "installer forwarding of `--no-oracle` into the service command" | pre-release | flows |  |
| 92 | "the docs and tests that asserted the disabled…" | pre-release | flows |  |
| 93 | "After that commit the Oracle is not optional." | pre-release | flows |  |
| 94 | "A signed job still goes through the result…" | pre-release | flows |  |
| 95 | "There is no config key and no CLI…" | pre-release | flows |  |
| 96 | "`runner/tests/test_protocol_and_edges.py` still asserts that a generated unit file…" | pre-release | flows |  |
| 97 | "That test is a guard so the installer…" | pre-release | flows |  |
| 98 | "Leave the assertion." | pre-release | flows |  |
| 99 | "Do not add the flag back to satisfy…" | pre-release | flows |  |
| 100 | "The owner wanted one way, for the rest…" | pre-release | flows |  |
| 101 | "They were explicit that this is not a…" | pre-release | flows |  |
| 102 | "A dashboard page -- job tables, controls, a…" | post-release | flows |  |
| 103 | "Do not grow `--oracle` into that page." | pre-release | flows |  |
| 104 | "They had also seen `feat/local-si-test`." | pre-release | flows |  |
| 105 | "That branch opens Open WebUI against a second…" | pre-release | flows |  |
| 106 | "The owner asked for the opposite of that:…" | pre-release | flows |  |
| 107 | "Open WebUI is a separate program (`pip install…" | pre-release | flows |  |
| 108 | "It cannot live inside the PyInstaller onefile binary,…" | pre-release | flows |  |
| 109 | "So `--oracle` does not start Open WebUI, does…" | pre-release | flows |  |
| 110 | "The chat is a single HTML page served…" | pre-release | flows |  |
| 111 | "The operating system browser opens it." | pre-release | flows |  |
| 112 | "One text box, one Send button." | pre-release | flows |  |
| 113 | "No job buttons, no config form, no board." | pre-release | flows |  |
| 114 | "Entry point is `main()` in `runner/ops/main.py` (`runner/runner.py` re-exports…" | pre-release | flows |  |
| 115 | "Parse `--oracle` and `--oracle-port`." | pre-release | flows |  |
| 116 | "Load `config.json`." | pre-release | flows |  |
| 117 | "`--inspect` still wins if both are passed." | pre-release | flows |  |
| 118 | "Inspect reads local state and exits — `main`…" | pre-release | flows |  |
| 119 | "It does not open the chat." | pre-release | flows |  |
| 120 | "`ensure_inference_ready` and `update_llama_from_config` run, same as a normal…" | pre-release | flows |  |
| 121 | "If `--oracle` is set, `oracle_window` is called and…" | pre-release | flows |  |
| 122 | "Everything below that line does not run." | pre-release | flows |  |
| 123 | "That last point is why the window does…" | pre-release | flows |  |
| 124 | "You can open the chat on a config…" | pre-release | flows |  |
| 125 | "A normal poll (`homing-pigeon` with no `--oracle`) is…" | pre-release | flows |  |
| 126 | "`oracle_context` builds the model's context from the base…" | pre-release | flows |  |
| 127 | "The log tail is what lets the Oracle…" | pre-release | flows |  |
| 128 | "`ASK_AGENT_SYSTEM` (the window's prompt; `ASK_SYSTEM` is the mailbox…" | pre-release | flows |  |
| 129 | "The chat goes further: `ask_model_agent` runs a tool…" | pre-release | flows |  |
| 130 | "That is the debugging interface the owner asked…" | pre-release | flows |  |
| 131 | "The mailbox-driven job path (`answer_queries` -> `ask_model`) stays…" | pre-release | flows |  |
| 132 | "Bounds are mechanical: 10 tool rounds, 4 calls…" | pre-release | flows |  |
| 133 | "The final answer goes through the same secret…" | pre-release | flows |  |
| 134 | "Stated risk: anything the model reads can steer…" | pre-release | flows |  |
| 135 | "That is the owner's explicit trade." | pre-release | flows |  |
| 136 | "`oracle_window` then:" | pre-release | flows |  |
| 137 | "Rejects a port that is not an integer…" | pre-release | flows |  |
| 138 | "Exit code 2." | pre-release | flows |  |
| 139 | "Sets the process log file to `/runner.log`. `base_dir`…" | pre-release | flows |  |
| 140 | "This matters because a normal run assigns `_LOG_FILE`…" | pre-release | flows |  |
| 141 | "Without this line the chat would log only…" | pre-release | flows |  |
| 142 | "Binds `127.0.0.1` only, via `make_oracle_server`." | pre-release | flows |  |
| 143 | "The host allowlist is `127.0.0.1`, `::1`, and `localhost`." | pre-release | flows |  |
| 144 | "`0.0.0.0` raises `ValueError` and the process exits 2." | pre-release | flows |  |
| 145 | "After bind, the socket's own address is checked…" | pre-release | flows |  |
| 146 | "Exit code 1 is any `OSError` from `make_oracle_server`…" | pre-release | flows |  |
| 147 | "Prints the URL and the path of `oracle-chat.jsonl`." | pre-release | flows |  |
| 148 | "Appends an `open` record to that file." | pre-release | flows |  |
| 149 | "Opens the browser after 0.4 seconds." | pre-release | flows |  |
| 150 | "Tests pass `open_browser=False` and never call this." | pre-release | flows |  |
| 151 | "Blocks on `serve_forever` until Ctrl+C (`KeyboardInterrupt`)." | pre-release | flows |  |
| 152 | "Appends a `close` record and closes the socket." | pre-release | flows |  |
| 153 | "Exit code 0." | pre-release | flows |  |
| 154 | "Do not put `--oracle` in the boot service." | pre-release | flows |  |
| 155 | "The call blocks, and it opens a browser." | pre-release | flows |  |
| 156 | "The scheduled task or systemd unit must keep…" | pre-release | flows |  |
| 157 | "The window is a second launch of the…" | pre-release | flows |  |
| 158 | "`GET /` returns the page." | pre-release | flows |  |
| 159 | "`GET /status` returns the ask-progress JSON, behind the…" | pre-release | flows |  |
| 160 | "Any other GET path is 404, including a…" | pre-release | flows |  |
| 161 | "The page embeds a session token (`secrets.token_urlsafe`) as…" | pre-release | flows |  |
| 162 | "The token is not put in the URL,…" | pre-release | flows |  |
| 163 | "The page builds the transcript with `textContent`, not…" | pre-release | flows |  |
| 164 | "`POST /ask` is the only write." | pre-release | flows |  |
| 165 | "The TCP peer must be a loopback address." | pre-release | flows |  |
| 166 | "The `Host` header must be `127.0.0.1`, `localhost`, or…" | pre-release | flows |  |
| 167 | "A POST that carries an `Origin` header must…" | pre-release | flows |  |
| 168 | "A POST with no `Origin` at all is…" | pre-release | flows |  |
| 169 | "GET may omit `Origin` because the browser does…" | pre-release | flows |  |
| 170 | "`X-Oracle-Token` must match the token from the page.…" | pre-release | flows |  |
| 171 | "A missing or wrong token is 403, and…" | pre-release | flows |  |
| 172 | "The body is at most 8000 bytes." | pre-release | flows |  |
| 173 | "The question string is stripped and cut at…" | pre-release | flows |  |
| 174 | "An empty question returns a fixed sentence and…" | pre-release | flows |  |
| 175 | "The question is then passed to `ask_model_agent`, the…" | pre-release | flows |  |
| 176 | "(A signed `ask` query uses the separate single-shot…" | pre-release | flows |  |
| 177 | "It is not a free chat with a…" | pre-release | flows |  |
| 178 | "The system prompt is `ASK_AGENT_SYSTEM`: the interactive charter…" | pre-release | flows |  |
| 179 | "`owner_instructions` from config is appended to that system…" | pre-release | flows |  |
| 180 | "That is how the box is told what…" | pre-release | flows |  |
| 181 | "The "output" is not the raw mailbox. `oracle_context`…" | pre-release | flows |  |
| 182 | "If nothing is retained, the output text is…" | pre-release | flows |  |
| 183 | "The endpoint must already be loopback. `inference_config` returns…" | pre-release | flows |  |
| 184 | "The window still opens." | pre-release | flows |  |
| 185 | "The page says the model is off." | pre-release | flows |  |
| 186 | "The reply is truncated to `max_answer_chars`, then secret-scanned." | pre-release | flows |  |
| 187 | "A hit returns `rejected: sanitization` and the model…" | pre-release | flows |  |
| 188 | "It is not rewritten and shown." | pre-release | flows |  |
| 189 | "The page displays a fixed sentence: "The reply…" | pre-release | flows |  |
| 190 | "Other rejections are also fixed sentences (unconfigured). `inference_error`…" | pre-release | flows |  |
| 191 | "The raw exception is not sent to the…" | pre-release | flows |  |
| 192 | "The browser keeps the visible transcript, and the…" | pre-release | flows |  |
| 193 | "What goes back is only what was written,…" | pre-release | flows |  |
| 194 | "The protection is redact-before-write." | pre-release | flows |  |
| 195 | "Turns do persist, and the last four do…" | pre-release | flows |  |
| 196 | "Commit `945ef68`, after the owner asked for the…" | pre-release | flows |  |
| 197 | "`record_oracle_turn` appends one JSON line to `/oracle-chat.jsonl`:" | pre-release | flows |  |
| 198 | "`ts` in UTC" | pre-release | flows |  |
| 199 | "`event`: `open`, `ask`, or `close`" | pre-release | flows |  |
| 200 | "`question` and `answer`, each passed through `redact_text` with…" | pre-release | flows |  |
| 201 | "`rejected` (the code, such as `sanitization`, or empty)" | pre-release | flows |  |
| 202 | "`detail`, cut at 300 characters" | pre-release | flows |  |
| 203 | "`model`" | pre-release | flows |  |
| 204 | "`tool_rounds`" | pre-release | flows |  |
| 205 | "Question is stored at most 2000 characters." | pre-release | flows |  |
| 206 | "Answer at most 4000." | pre-release | flows |  |
| 207 | "The session token is not stored." | pre-release | flows |  |
| 208 | "The mailbox password is not stored." | pre-release | flows |  |
| 209 | "The shared secret is not stored." | pre-release | flows |  |
| 210 | "The retained-job blob that was sent to the…" | pre-release | flows |  |
| 211 | "That blob can be large and it already…" | pre-release | flows |  |
| 212 | "The file rolls at 1 MiB (`_ORACLE_CHAT_MAX`)." | pre-release | flows |  |
| 213 | "When the next line would pass that, the…" | pre-release | flows |  |
| 214 | "One backup." | pre-release | flows |  |
| 215 | "The next roll replaces the backup." | pre-release | flows |  |
| 216 | "Worst case is about 2 MiB for the…" | pre-release | flows |  |
| 217 | "The write uses `os.open` with mode `0o600` and…" | pre-release | flows |  |
| 218 | "`runner.log` uses the same helper, `append_bounded_log`." | pre-release | flows |  |
| 219 | "Its bounds are config — `log_max_bytes` / `log_backups`,…" | pre-release | flows |  |
| 220 | "Those bounds apply to every run that writes…" | pre-release | flows |  |
| 221 | "The per-minute console budget is unchanged: verbose drops…" | pre-release | flows |  |
| 222 | "Dropped console lines are counted, not written." | pre-release | flows |  |
| 223 | "The chat file does not use that budget." | pre-release | flows |  |
| 224 | "Every ask is kept until the roll." | pre-release | flows |  |
| 225 | "A 403 (bad token, bad origin) is not…" | pre-release | flows |  |
| 226 | "Commit `88fcfdf`." | pre-release | flows |  |
| 227 | "`8f0719f` deleted the `oracle_enabled` flag but left one…" | pre-release | flows |  |
| 228 | "Nothing assigns `oracle` anymore." | pre-release | flows |  |
| 229 | "The first real poll on the Windows binary…" | pre-release | flows |  |
| 230 | "PyInstaller reported "Failed to execute script runner"." | pre-release | flows |  |
| 231 | "The zip was not uploaded because the smoke…" | pre-release | flows |  |
| 232 | "The fix is the condition that matches the…" | pre-release | flows |  |
| 233 | "The Oracle is always on, so the warning…" | pre-release | flows |  |
| 234 | "`runner/tests/test_oracle_chat.py` calls `log_startup` with a config that has…" | pre-release | flows |  |
| 235 | "That test is there so the `NameError` cannot…" | pre-release | flows |  |
| 236 | "This crash is not caused by passing `--oracle`." | pre-release | flows |  |
| 237 | "A normal poll hit it." | pre-release | flows |  |
| 238 | "It was found while the `--oracle` Windows build…" | pre-release | flows |  |
| 239 | "Do not "fix" it by defining `oracle =…" | pre-release | flows |  |
| 240 | "That would bring the removed flag back." | pre-release | flows |  |
| 241 | "Not part of the chat, but it is…" | pre-release | flows |  |
| 242 | "`validate_shared_secret` (from `89f1948`) rejects a secret that is…" | pre-release | flows |  |
| 243 | "The Windows smoke config used a 64-character hex…" | pre-release | flows |  |
| 244 | "The new checker exited 2, the smoke step…" | pre-release | flows |  |
| 245 | "The smoke secret was replaced with a non-repeating…" | pre-release | flows |  |
| 246 | "Do not put a patterned placeholder back into…" | pre-release | flows |  |
| 247 | "`runner/tests/test_oracle_chat.py`:" | pre-release | flows |  |
| 248 | "`make_oracle_server` on `0.0.0.0` raises `ValueError`." | pre-release | flows |  |
| 249 | "`oracle_context` reads a retained job and does not…" | pre-release | flows |  |
| 250 | "The HTML has no `innerHTML` and uses `textContent`." | pre-release | flows |  |
| 251 | "A live loopback server: GET does not contain…" | pre-release | flows |  |
| 252 | "POST without the token is 403." | pre-release | flows |  |
| 253 | "POST with an `Origin` of another host is…" | pre-release | flows |  |
| 254 | "POST with the token reaches `ask_model_agent` with the…" | pre-release | flows |  |
| 255 | "A question that is itself a flagged secret…" | pre-release | flows |  |
| 256 | "`--oracle` on a config with no `mailbox_user` calls…" | pre-release | flows |  |
| 257 | "It does not die on the mailbox check." | pre-release | flows |  |
| 258 | "`log_startup` without `workspace_root` does not raise." | pre-release | flows |  |
| 259 | "The chat log redacts before write, and `append_bounded_log`…" | pre-release | flows |  |
| 260 | "The model is mocked in these tests." | pre-release | flows |  |
| 261 | "They do not start Ollama and they do…" | pre-release | flows |  |
| 262 | "Do not add `--no-oracle` or `oracle_enabled` back." | pre-release | flows |  |
| 263 | "Do not make `--oracle` mean "disable the Oracle"." | pre-release | flows |  |
| 264 | "Do not bind the chat on a non-loopback…" | pre-release | flows |  |
| 265 | "Do not drop the token check or the…" | pre-release | flows |  |
| 266 | "Another site in the same browser can reach…" | pre-release | flows |  |
| 267 | "Do not log the token, the mailbox password,…" | pre-release | flows |  |
| 268 | "Do not write the model reply to disk…" | pre-release | flows |  |
| 269 | "Do not feed the on-screen transcript back into…" | pre-release | flows |  |
| 270 | "Do not shell out to Open WebUI from…" | pre-release | flows |  |
| 271 | "Do not start a second Ollama for this…" | pre-release | flows |  |
| 272 | "The SI on port 11435 belongs to the…" | pre-release | flows |  |
| 273 | "Do not put `--oracle` in the installed service…" | pre-release | flows |  |
| 274 | "Do not turn this page into a dashboard." | pre-release | flows |  |
| 275 | "Do not remove the size cap on `oracle-chat.jsonl`…" | pre-release | flows |  |
| 276 | "From a checkout:" | pre-release | flows |  |
| 277 | "Leave that process running." | pre-release | flows |  |
| 278 | "Ctrl+C closes it." | pre-release | flows |  |
| 279 | "The service that polls mail should already be…" | pre-release | flows |  |
