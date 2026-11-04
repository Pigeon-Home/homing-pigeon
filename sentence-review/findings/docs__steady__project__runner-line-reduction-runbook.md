# Findings — docs/steady/project/runner-line-reduction-runbook.md

Source: docs/steady/project/runner-line-reduction-runbook.md, reviewed at main 2d76ba7e.
Sentence units: 77. Flagged: 1. Categories: pre-release 77, post-release 0.

The runner line-reduction runbook, status done: the goal and starting point, the extraction rules that still bind any further extraction, the repaired import rules earned from 2 landings that broke the installed runner, and the candidate patterns with their counts. The rules list is the document's spine and each rule is stated with the failure that taught it; the candidates list answers the rule that a repeated block of 4 or more gets a helper. The stamp comment (unit 1) is the only non-sentence.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 (status and the repaired rules)…" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "Status: done." | pre-release | flows |  |
| 3 | "The series of 2026-10-25 took `runner/runner.py` from 11,205…" | pre-release | flows |  |
| 4 | "The phases below are the record of how…" | pre-release | flows |  |
| 5 | "The rules are current and bind any further…" | pre-release | flows |  |
| 6 | "Goal (met): `runner/runner.py` below 10,000 lines, with no…" | pre-release | flows |  |
| 7 | "Starting point: 11,205 lines, 303 functions." | pre-release | flows |  |
| 8 | "This is extraction, not deletion." | pre-release | flows |  |
| 9 | "Every cut is a helper that replaces a…" | pre-release | flows |  |
| 10 | "Tests must stay green." | pre-release | flows |  |
| 11 | "One extraction per commit." | pre-release | flows |  |
| 12 | "Message: `runner: extract <name>; collapse N <what>.`" | pre-release | flows |  |
| 13 | "No behavior change." | pre-release | flows |  |
| 14 | "If a test fails, the extraction is wrong." | pre-release | flows |  |
| 15 | "Do not touch the security decision path except…" | pre-release | flows |  |
| 16 | "Run `python3 -m unittest runner.tests.test_security_config runner.tests.test_audience runner.tests.test_enforce_races runner.tests.test_confinement`…" | pre-release | flows |  |
| 17 | "Stop when `wc -l runner/runner.py` is under 10000." | pre-release | flows |  |
| 18 | "**A module moved out of runner.py is loaded…" | pre-release | flows |  |
| 19 | "The suite imports `runner` as a package, but…" | pre-release | flows |  |
| 20 | "Two extractions on 2026-10-25 landed that way and…" | pre-release | flows |  |
| 21 | "The extracted module's own sibling imports fall back…" | pre-release | flows |  |
| 22 | "**The extracted module reaches the runner at call…" | pre-release | flows |  |
| 23 | "That covers runner globals (`log`, `HOT_KEYS`, `JobRejected`), calls…" | pre-release | flows |  |
| 24 | "It carries its own stdlib imports." | pre-release | flows |  |
| 25 | "It never assigns onto the runner (`R.x =…" | pre-release | flows |  |
| 26 | "**Before each push**: `python3 runner/tools/repair_script_imports.py --check` prints nothing,…" | pre-release | flows |  |
| 27 | "The repair tool without `--check` performs the mechanical…" | pre-release | flows |  |
| 28 | "`_valid_base` — 18 base_dir guards" | pre-release | flows |  |
| 29 | "`_safe_open` — 8 O_NOFOLLOW/O_BINARY open blocks" | pre-release | flows |  |
| 30 | "`_auth_reject_event` — 11 auth-rejection event writes" | pre-release | flows |  |
| 31 | "`_verify_and_decrypt` — signature + decrypt in handle_mail" | pre-release | flows |  |
| 32 | "Search for these and extract a helper when…" | pre-release | flows |  |
| 33 | "`mark_seen(imap, seq)` guarded by `if opts is None…" | pre-release | flows |  |
| 34 | "Helper: `_mark_seen_unless_dry(imap, seq, opts)`." | pre-release | flows |  |
| 35 | "Remaining `_append_security_event` blocks that still write the full…" | pre-release | flows |  |
| 36 | "`os.makedirs(..., exist_ok=True)` + tmp + `os.replace` write pattern…" | pre-release | flows |  |
| 37 | "Helper: `_atomic_write(path, data)`." | pre-release | flows |  |
| 38 | "The `try: x = int(cfg.get(...)) except: x =…" | pre-release | flows |  |
| 39 | "Helper: `_cfg_int(cfg, key, default)`." | pre-release | flows |  |
| 40 | "Each of these is 3–5 lines at the…" | pre-release | flows |  |
| 41 | "Do them in that order." | pre-release | flows |  |
| 42 | "Split into these helpers, in order." | pre-release | flows |  |
| 43 | "Each takes the locals it needs and returns…" | pre-release | flows |  |
| 44 | "handle_mail becomes the caller." | pre-release | flows |  |
| 45 | "`_dispatch_non_job(cfg, imap, smtp, seq, raw, subject, secrets, opts,…" | pre-release | flows |  |
| 46 | "Returns True if handled." | pre-release | flows |  |
| 47 | "`_check_job_policy(cfg, job, key_id, job_id, base_dir)` — audience, script…" | pre-release | flows |  |
| 48 | "Raises ValueError with the reject reason." | pre-release | flows |  |
| 49 | "`_execute_and_send(cfg, job, ...)` — the try/finally that runs…" | pre-release | flows |  |
| 50 | "After the split, handle_mail should be under 150…" | pre-release | flows |  |
| 51 | "Split into:" | pre-release | flows |  |
| 52 | "`_parse_args()` — already partly there; finish it." | pre-release | flows |  |
| 53 | "`_load_and_validate_config(path)` — config load, security block check, secret…" | pre-release | flows |  |
| 54 | "`_start_services(cfg, opts)` — oracle server, local signals, transports." | pre-release | flows |  |
| 55 | "`_poll_loop(cfg, opts)` — the while True." | pre-release | flows |  |
| 56 | "After the split, main should be under 100…" | pre-release | flows |  |
| 57 | "These are over 150 lines and have internal…" | pre-release | flows |  |
| 58 | "`execute_job` (249) — extract the confinement setup and…" | pre-release | flows |  |
| 59 | "`answer_queries` (224) — extract the per-query loop body" | pre-release | flows |  |
| 60 | "`oracle_page` (203) — extract the HTML builders" | pre-release | flows |  |
| 61 | "`ask_model_agent` (199) — extract the tool-call loop" | pre-release | flows |  |
| 62 | "`make_oracle_server` (183) — extract the route handlers" | pre-release | flows |  |
| 63 | "Do these only after Phase 2." | pre-release | flows |  |
| 64 | "Each should drop 30–50 lines." | pre-release | flows |  |
| 65 | "When `wc -l runner/runner.py` prints a number under…" | pre-release | flows |  |
| 66 | "Run the full suite: `python3 -m unittest discover…" | pre-release | flows |  |
| 67 | "Confirm switch-proofs is green on the tip." | pre-release | flows |  |
| 68 | "Write one line in `docs/seats/questions.md` under the newest…" | pre-release | flows |  |
| 69 | "No behavior change." | pre-release | flows |  |
| 70 | "Applied in: <commit>.`" | pre-release | flows |  |
| 71 | "Stop." | pre-release | flows |  |
| 72 | "Do not rewrite algorithms." | pre-release | flows |  |
| 73 | "Do not merge two functions that have different…" | pre-release | flows |  |
| 74 | "Do not remove comments that explain a security…" | pre-release | flows |  |
| 75 | "Do not change a log line, a reject…" | pre-release | flows |  |
| 76 | "Do not touch files outside `runner/runner.py`, the new…" | pre-release | flows |  |
| 77 | "Green, silent and printing the version means the…" | pre-release | flows |  |
