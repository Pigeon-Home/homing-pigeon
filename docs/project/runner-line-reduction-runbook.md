# Runbook: get runner.py under 10,000 lines

Goal: `runner/runner.py` below 10,000 lines, with no behavior
change. Current: 11,205 lines, 303 functions. Target: under
10,000. Gap: about 1,200 lines.

This is extraction, not deletion. Every cut is a helper that
replaces a repeated or oversized block. Tests must stay green.

## Rules

- One extraction per commit. Message: `runner: extract <name>;
  collapse N <what>.`
- No behavior change. If a test fails, the extraction is wrong.
- Do not touch the security decision path except to move it
  verbatim into a helper.
- Run `python3 -m unittest runner.tests.test_security_config
  runner.tests.test_audience runner.tests.test_enforce_races
  runner.tests.test_confinement` after each commit.
- Stop when `wc -l runner/runner.py` is under 10000.

## Already done

- `_valid_base` — 18 base_dir guards
- `_safe_open` — 8 O_NOFOLLOW/O_BINARY open blocks
- `_auth_reject_event` — 11 auth-rejection event writes
- `_verify_and_decrypt` — signature + decrypt in handle_mail

## Phase 1: collapse remaining repeats (about 200 lines)

Search for these and extract a helper when the count is 4 or more.

1. `mark_seen(imap, seq)` guarded by `if opts is None or not
   opts.dry_run` — about 18 sites. Helper:
   `_mark_seen_unless_dry(imap, seq, opts)`.
2. Remaining `_append_security_event` blocks that still write
   the full dict inline (3 left after the auth helper).
3. `os.makedirs(..., exist_ok=True)` + tmp + `os.replace`
   write pattern — appears in save_sent_result and others.
   Helper: `_atomic_write(path, data)`.
4. The `try: x = int(cfg.get(...)) except: x = default`
   pattern. Helper: `_cfg_int(cfg, key, default)`.

Each of these is 3–5 lines at the call site, 1 line after.
Do them in that order.

## Phase 2: split the two giants (about 800 lines)

### handle_mail (636 lines, L6057)

Split into these helpers, in order. Each takes the locals it
needs and returns or raises. handle_mail becomes the caller.

1. `_dispatch_non_job(cfg, imap, smtp, seq, raw, subject,
   secrets, opts, base_dir, seen)` — query, board, v2, not-a-job,
   answer-only, already-seen. Returns True if handled.
2. `_check_job_policy(cfg, job, key_id, job_id, base_dir)` —
   audience, script size, age, env/files/args. Raises ValueError
   with the reject reason.
3. `_execute_and_send(cfg, job, ...)` — the try/finally that
   runs the job, reconciles, and sends the result.

After the split, handle_mail should be under 150 lines.

### main (674 lines, L10506)

Split into:

1. `_parse_args()` — already partly there; finish it.
2. `_load_and_validate_config(path)` — config load, security
   block check, secret load.
3. `_start_services(cfg, opts)` — oracle server, local signals,
   transports.
4. `_poll_loop(cfg, opts)` — the while True.

After the split, main should be under 100 lines.

## Phase 3: medium functions (about 200 lines)

These are over 150 lines and have internal sections that can
move out:

- `execute_job` (249) — extract the confinement setup and the
  result assembly
- `answer_queries` (224) — extract the per-query loop body
- `oracle_page` (203) — extract the HTML builders
- `ask_model_agent` (199) — extract the tool-call loop
- `make_oracle_server` (183) — extract the route handlers

Do these only after Phase 2. Each should drop 30–50 lines.

## Phase 4: stop line

When `wc -l runner/runner.py` prints a number under 10000:

1. Run the full suite: `python3 -m unittest discover -s
   runner/tests -t .`
2. Confirm switch-proofs is green on the tip.
3. Write one line in `docs/use/questions.md` under the newest
   Q: `runner.py is under 10,000 lines (N). No behavior change.
   Applied in: <commit>.`
4. Stop.

## What not to do

- Do not rewrite algorithms.
- Do not merge two functions that have different error
  contracts.
- Do not remove comments that explain a security decision.
- Do not change a log line, a reject reason, or an event
  field name.
- Do not touch files outside `runner/runner.py` for this goal.

## Check

```bash
wc -l runner/runner.py
python3 -m py_compile runner/runner.py
python3 -m unittest runner.tests.test_security_config \
  runner.tests.test_audience runner.tests.test_enforce_races \
  runner.tests.test_confinement
```

Green and under 10000 means done.
