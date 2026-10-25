# Campaign standing orders

<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->

The campaign runs continuously from this file. It does not wait for
a new batch of questions. When one piece of work closes, the next
comes from the queue below, in order, without asking anyone. The
owner should never have to hand the campaign its next task; if the
campaign is idle, these orders were not followed.

How a campaign is run (the rig, the loop, recording a finding, the
watchdog, the hard rules) is `docs/project/campaign-playbook.md`.
Questions to Claude or the owner go in `docs/use/questions.md`
(AGENTS.md rules 7 and 8). This file says only what to work on next
and when to stop.

## Talking to the owner

During a campaign the owner hears from the campaign in chat only when
he must act: a question in the "When to stop and ask the owner" list
below, worded so he can answer it in one line. No progress reports,
no summaries, no confirmations, no "starting X" or "done with Y".
Progress lives in the ledger at the end of this file and in the
commits; he reads those when he wants them. If he asks for status,
answer in three sentences and go back to work.

## Rule refresh, every hour

Long runs lose context. At least once an hour, and after any restart
or context reset, re-read before taking the next item: this file,
AGENTS.md (rules 7, 8 and 9 above all), the open entries in
`docs/use/questions.md`, and `docs/project/campaign-playbook.md`'s
hard rules. Note the refresh in the ledger as one line
("rules refreshed <time>"). A ledger with no refresh line in the last
hour of activity means this step was skipped.

## The loop

1. Pull main. If the last rule refresh was more than an hour ago, do
   it now (above).
2. Read `docs/use/questions.md`. Anything answered since the last
   pass that changes the campaign's own work (a fix to re-verify, a
   probe to retire, a decision that moves an assertion) comes first.
3. Take the first open item from the queue below. Mark it taken by
   writing one line under it ("taken <date>, <agent stamp>") in the
   same commit as the first test for it.
4. Work it to done (the definition is under each queue). Commit as
   you go; keep main green; check what skipped before calling
   anything green.
5. Mark it done with the commit or run that proves it, and return to
   step 1.

A finding that needs production code is filed as a question for
Claude, in the four-part format, with a failing-by-design test. The
campaign does not wait for the fix: it moves to the next item and
re-verifies when the question is answered.

## When to stop and ask the owner

Only these stop the loop, and only for the item they block. Write
the question in `docs/use/questions.md` addressed to the owner, then
continue with the next item that does not need it.

- A secret: anything that needs a mailbox password, a token or a key
  that must not be in the repository.
- A machine: a real Windows box, a host the VM cannot reach, a device.
  (A GitHub runner is not a machine for this purpose: ask Claude for
  a workflow instead.)
- A decision only the owner can make: what the project promises, what
  is in scope, a security posture.
- Money or an external account.

Nothing else is a reason to stop. "The list is done" is not: the
queue below does not run out (queue D refills it).

## The queue, in order

### A. The coverage map, gap by gap

Source: the latest `coverage` workflow run on main, its
`coverage-Linux` and `coverage-Windows` artifacts (made by
`runner/tools/coverage_gaps.py`). The ranked first seven are closed
(Q11 to Q17).

Next: take the function with the most never-executed lines on either
platform that is not marked taken in the ledger at the end of this
file, and that is not test or tool code. Prefer, at equal size, code
that decides what runs, what leaves the box, or who can reach it.

Skip a gap that exists only because the code cannot apply on that
platform (a Linux-only installer path on the Windows map, a Windows
registry read on the Linux map) when the other platform's map shows
it running. Moving a faked test into an ungated class to color those
lines on the wrong platform adds no protection. Record it in the
ledger as "platform-inapplicable, covered on <the other platform>"
and take the next gap.

Done when the lines run in the full suite on the platform where they
were missing (cite the coverage run) and a test asserts what the docs
say those lines do. A gap that cannot be reached without mocking the
world is filed as a missing-seam question and marked done as filed.

Stop working queue A for the day when the largest remaining gap on
both platforms is under 10 lines; go to B.

### B. Environment axes

Each setting below gets the env-axes treatment: the protection corpus
run once per value on a GitHub runner, the value asserted after it is
set, recorded with every result (`.github/workflows/env-axes.yml` is
the pattern; ask Claude in the questions file to add each axis to it).

1. `kernel.yama.ptrace_scope` at 0, 1, 2 and 3: can a job read the
   runner's memory or attach to it?
2. `fs.protected_symlinks` and `fs.protected_regular` on and off: can
   a job plant a link the runner follows?
3. `hidepid` on `/proc` (0 and 2): can a job see the runner's command
   line and environment?
4. The job_user feature on and off, crossed with each of the above.

Done per axis when both values are green, or the difference is filed
as a finding.

### C. Live paths that need the owner (park until unblocked)

1. The live email capture (Q2, Q11): one real round trip per release
   through the dedicated throwaway mailbox, the messages committed as
   fixtures. Needs the mailbox credentials from the owner, on the
   machine that runs it, never in the repository.
2. Windows as a live target (the plan's open decision 3): the credential
   canary and the job_user equivalents (restricted token, ACLs, job
   objects) on a real Windows runner. Needs the owner's decision that
   Windows is in scope; a GitHub Windows runner is enough to start.

### D. Refill

When A is under its threshold, B is done and C is parked, start a new
hunt from these, one at a time, and add what each finds to queue A's
ledger:

1. Re-run the documented-default hunt against every key added to the
   docs since the defaults registry was last complete.
2. Every claim in SECURITY.md and `docs/security/threat-model.md`:
   one test per claim that would fail if the claim were false, plus
   its negative control.
3. Every example in PROTOCOL.md and AGENTS.md's "Do not emit" table,
   run as written through the runner.
4. The mutation workflow's surviving mutants (`mutation-seeded.yml`):
   each survivor is a missing assertion.

Then return to A: new code since the last pass has made new gaps.

## Ledger

One line per item taken: queue, item, date taken, agent stamp, and
when done, the proving commit or run. Newest first.

- A — `runner/wire/oauth.py::store_refresh_token` (12
  lines never run on Windows, 9 on Linux, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the O_NOFOLLOW
  flag line is platform-inapplicable on Windows and the
  O_BINARY line on Linux (each behind its hasattr guard),
  covered on the other platform.
- A — `runner/extensions/job-fuzz/job_fuzz.py::decide` (12
  lines never run on either platform, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90
- rules refreshed 2026-10-25 03:25 PDT
- rules refreshed 2026-10-25 03:00 PDT
- A — `runner/extensions/pi-health/pi_health.py::`
  `_mem_avail_pct_windows` (14 lines never run on Linux,
  coverage run 40180268696) — platform-inapplicable on Linux
  (a ctypes.windll reader behind its own os.name guard),
  covered on Windows; recorded 2026-10-25.
- A — `runner/ops/posture.py::_check_privileges` (13 lines
  never run on Windows, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  platform-inapplicable on Windows (the POSIX branch sits
  behind the function's os.name guard and its driving test
  is POSIX by construction), covered on Linux; the one
  Linux residual, the root row, is taken with it.
- A — `runner/runner.py::handle_mail` (13 lines never run on
  either platform, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/oracle/dri.py::_save_state` (14 lines never run
  on Windows, 9 on Linux, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/oracle/detection.py::update_baseline` (14 lines
  never run on Windows, 8 on Linux, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run
  40183995594 (main at d2f23bb) leaves only the reset line
  that cannot be reached (the load assigns only a dict or
  the default) and each platform's foreign flag line
  (O_NOFOLLOW on Windows, O_BINARY on Linux), both
  recorded in the test class docstring.
- A — `runner/extensions/resource-sentinel/resource_sentinel.py`
  `::_read_mem_avail_pct` (19 lines never run on Windows,
  coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/runner.py::_with_seen_file` (14 lines never run
  on Linux, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/guard/sandbox.py::startup_problem` (15 lines
  never run on Windows, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  platform-inapplicable on Windows (the bwrap trial sits
  behind the function's own platform guard), covered on
  Linux; the Linux residuals (start failure, the userns
  note) are taken with it.
- A — `runner/extensions/latency-post/latency_post.py::`
  `_read_default_gateway` (17 lines never run on either
  platform, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run
  40183585961 (main at f10a114) shows no never-executed
  lines for this function on either platform.
- A — `runner/cloud/send_job.py::cmd_verify` (17 lines never
  run on either platform, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `runner/ops/extsources.py::_small_parts` (17 lines never
  run on either platform, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `_deliver_local` in five more sense extensions
  (port-watch, log-sentinel, failed-login-watch,
  cert-sentinel, backup-freshness; 18 lines each, never run
  on either platform, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/guard/security.py::validate_security_config` (18
  lines never run on Windows, 7 on Linux, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/extensions/latency-post/latency_post.py::_probe`
  (19 lines never run on either platform, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/extensions/aide-feed/aide_feed.py::main` (20 lines
  never run on Windows, 7 on Linux, coverage run 40180268696) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `runner/ops/install.py::install_files` (20 lines never run
  on Windows, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/extensions/job-fuzz/job_fuzz.py::main` (23 lines
  never run on either platform, coverage run 40180268696) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `runner/extensions/service-watch/service_watch.py::read_live`
  (30 lines never run on either platform, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/ops/install.py::_install_collector_linux` (31 lines
  never run on Windows, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  platform-inapplicable on Windows (a Linux-only installer
  path), covered on Linux; closed under the queue-A skip
  rule, 2026-10-25.
- A — `runner/ops/install.py::_install_falco_linux` (32 lines never
  run on Windows, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  platform-inapplicable on Windows (a Linux-only installer
  path), covered on Linux; closed under the queue-A skip
  rule, 2026-10-25.
