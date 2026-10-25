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
("rules refreshed <time>"), followed by the hour's resource line
(below). A ledger with no refresh line in the last hour of activity
means this step was skipped.

## Throughput: the rig stays busy, and says what it used

The owner's order (2026-10-25): while a campaign runs, the rig's
CPU is kept at about 90%, and every piece of testing comes with a
resource report. A rig that sits at 10% is waiting on something, and
waiting is not testing.

- Run the suite and the hunts through `runner/tools/rig_resources.py`:
  `python runner/tools/rig_resources.py -- <the command>`. It prints
  one `resources` line from the kernel's counters (the box's CPU
  share over the run, the command's own CPU time and the cores it
  kept busy, peak memory, memory and disk at the end, the exit code,
  and a verdict: `on target`, `under-driven`, `over`). Paste that
  line into the ledger under the item it measured, and the hour's
  line under each "rules refreshed" line.
- To reach the target: run the suite sharded
  (`runner/tools/run_tests_parallel.py --jobs <cores>`), run the
  previous item's verification while writing the next item's test,
  and never wait on a CI run with the rig idle: take the next item
  and come back to the run when it finishes. Hypothesis budgets go up
  when the box is under-driven, not the sleep.
- The rig runs no model, at all. The Oracle under test needs none:
  by design (runner/oracle/opinion.py) the model's only channel
  into an opinion is a text note capped at 240 characters and
  labeled "Model-formed note:", appended to a member the
  deterministic tier already formed; the opinion is not a gate
  and never blocks, holds or approves a job. So the model's whole
  output space is a fixture: mode in {off, diagnose, advise,
  repair}, verdict in {likely_success, likely_failure}, repaired
  in {true, false}, and a note that must be inert whatever it
  says. The Oracle agent's other channel is its tool calls, a
  finite set with their refusals already pinned. Stop any resident
  model server on the rig for the duration (the first resource
  line read 97% memory used on a 2-core box) and paste the
  `resources-top` line with each resource line so the owner sees
  what holds the memory (owner's order, 2026-10-25).
- Two `under-driven` hourly lines in a row is a finding about the
  loop: write in the ledger what the rig was waiting on, then fix
  that. `over` for an hour (the box swapping or the suite timing out)
  means one fewer shard, not a slower loop.
- A test that fails only under load is a finding about the test
  (make it load-tolerant: barriers and outcomes, not sleeps and
  clocks) unless it guards a promise about time; then it is filed
  as a question with the measurement attached.

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

Two rules keep main green while that happens (owner's standing
order, 2026-10-25, after a release was blocked twice in one hour):

- A failing-by-design probe lands under `@unittest.expectedFailure`
  with the question number in a comment above it. It then fails
  quietly until the fix lands and flips to "unexpected success",
  which is red: the fix commit removes the decorator. A red probe
  in the live suite blocks every release behind it; an expected
  failure blocks nothing and is just as much a proof.
- A release window: when the head of main is a commit whose message
  starts with `release:`, hold every push until that commit's build
  has completed (the `build` run on it; about twelve minutes), then
  resume. Three cuts of 3.12.67 were lost to tests that landed in
  that window and went red on Windows. Keep working; stack the
  commits locally and push them together when the window closes.
- A test is not done until the build's Windows shards are green
  for it (the shard annotations name a red test). The fixtures
  that broke there this morning are the same three shapes each
  time: counting `os.stat` calls to catch a path probe (Python
  3.12+ answers `os.path.isfile`/`isdir` in C on Windows, so the
  probe never shows; stub the probe directly), a fake `os.close`
  that does not release the descriptor (Windows then cannot remove
  the file), and a directory or `chmod 000` standing in for an
  unreadable file (neither is unreadable there; a refusing `open`
  is). A scripted binary on PATH needs a POSIX shell: skip the
  class on `nt` with a registered reason. The lint for these
  shapes is `runner/tests/test_windows_portability.py`: run it
  before every push (it is in the suite, so a red Linux run names
  the line); a line that is right for a reason it cannot see
  carries `# portable: <why>`.

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

The owner reset the target on 2026-10-25 (Q24): the campaign exists
to prove that each security control does what SECURITY.md promises
when it is turned on, with the Oracle simulated, and to find the
races on the enforce path. Queues S and R are that work and come
first; A, B and D resume only when S and R have nothing open. A
never-executed line is a refill, not the goal.

### S. The switches, on

The ledger for S and R is in code: `runner/tests/switch_roster.py`
lists every control, its promise and the tests that prove it, and
`.github/workflows/switch-proofs.yml` runs the roster on every push
(a Linux leg with bwrap, a root leg with a second user, a Windows
leg) and names each control proven, unproven, or failed. Take the
first entry whose `tests` list is empty, in roster order; an item
is done when its entry lists tests that run and pass on the leg
where the control applies and the workflow is green. Adding tests
to the roster is this campaign's lane; the controls, promises and
needs change only through the questions file.

One item per control. For each: read its SECURITY.md section and
the config keys it names, list what the suite already pins (the
files below), and write what is missing as end-to-end tests through
the intake and `execute_job`, not through the helper alone. Every
item carries the three modes where the control has them (`off`
allows the case; `audit` runs it and writes the `would_deny` line;
`enforce` denies it and writes `denied`) and a negative control:
the same escape succeeds with the mode off, so a test that passes
for a reason other than the control is caught.

Two owner decisions (2026-10-15) are part of the promise, and a test
that "hardens" past them is wrong: with `confinement: enforce`, a
sandbox that does not work at startup refuses to start (Q9), but a
sandbox that fails after a good start lets the job run unsandboxed
with a WARN line and a `fallback` audit entry; `job_user` without
root does the same (`job_user_needs_root`). Pin those as they are.

1. M1, the size caps: `max_job_bytes`, `max_script_bytes`. Always
   on; over the cap is rejected before anything runs; a non-number
   refuses startup. Have: `test_size_caps.py`.
2. M2, the key policies: `policy_env`, `policy_files`,
   `policy_args`, per pinned key. Have: `test_policy_constraints.py`,
   `test_security_config.py` (the mode trio), `test_flag321_scenarios.py`.
   Missing until shown otherwise: each policy driven through a
   signed job under each mode, with the audit line's `mode` member
   asserted.
3. M3 and M4, `--audit-report` and `--posture`: read-only. Neither
   writes `config.json` or the audit log; the report's counts equal
   the entries written by the M2 and M6 tests above. Have:
   `test_audit_report.py`, `test_posture.py`.
4. M5, `audience`: `enforce` rejects a job whose audience is not
   this `runner_id`; `audit` runs it and records; `off` ignores it.
   Have: `test_audience.py`.
5. M6, `confinement`: `enforce` runs the job inside bwrap with no
   network, no home, `/usr` read-only and the workdir only at
   `/work`; the same escape succeeds with the mode off. Have:
   `test_confinement.py` (`EnforceTest` and its negative control,
   Linux CI only). Missing: each wall as its own case and control
   (network, home, `/usr` write, a path outside `/work`), and the
   after-a-good-start fallback above.
6. M7, the AppArmor, SELinux and systemd templates under
   `docs/security/hardening/`: files only; nothing installs them.
   Prove that they parse and that the runner's paths in them match
   the install layout; file a question if they drift.
7. M8, `job_user` and the secret files: `enforce` drops uid and
   groups (a failed `initgroups` does not keep the runner's groups,
   Q18); the workdir is chowned to the job user; a missing or
   world-readable secret file refuses startup. Have:
   `test_secret_files_job_user.py` (as root, `.github/workflows/job-user.yml`),
   `test_runner_face.py`, `test_credential_canary.py`.
8. M9 and M10 are design documents (asymmetric signing, the approval
   gate); nothing in the runner implements them. Nothing to enable;
   skip, and do not write tests against the design.
9. The Oracle, exhaustively, with no model: the deterministic
   opinion and the judge are driven with fixtures, and the model is
   a loopback fake that returns a chosen element of the alphabet.
   Prove, for every mode x verdict x repaired, under every latitude
   and every key policy mode, that the security decision made above
   the Oracle and the job's outcome are identical to the no-model
   run, and that the note is inert: fuzz it with instructions,
   JSON, approvals, refusals, huge and empty strings, and show it
   lands capped and labeled and changes nothing (roster
   `ORACLE.alphabet`). Prove that `refuse` and `advise` latitude
   refuse what `repair` repairs (AGENTS.md's table), and that every
   tool call the agent's model can emit is read-only or refused
   (roster `ORACLE.tools.alphabet`).

Done per item when each promise in the control's SECURITY.md
section has a test that fails if the promise were false, plus its
negative control, on the platform where the control applies, and
the roster entry lists them (the ledger line names the entry). A
promise the code does not keep is filed as a question for Claude
with the failing-by-design test.

### R. Races on the enforce path

With `workers: 2` (the runner's thread pool), under `enforce`:

1. Two jobs at once: each workdir is chowned to its own job and
   never the other's; two bwrap sandboxes do not share `/work`; the
   audit log receives both decisions, each entry whole.
2. A rollover of `security-audit.jsonl` (`_enforce_bound`) while a
   decision is being written: no entry lost, none split.
3. A replayed job id and a fresh job hitting the seen set together:
   the replay is rejected on both orderings.
4. A `config.json` write during a job: the security block does not
   hot-reload into the running job, and a bad value written live
   leaves the current settings in force (Decision 1).

Done when each race has a test that drives the two sides with a
real second thread and a barrier (not a mock of time), passes
repeatedly, and asserts the security outcome, not only that nothing
crashed (`test_concurrency_poison.py` already covers the crash-free
part and is the pattern for the rig), and the roster entry (R1 to
R4) lists it.

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

- rules refreshed 2026-10-25 06:37 PDT
  resources 2026-10-25T13:37:09Z: cores 2 | box cpu 65% | wall 0s | cmd cpu 0s = 0.7 cores busy | peak rss 29 MB | mem used 97% | disk free 166.4 GB | exit 0 | under-driven
  (scoped verification runs are short by
  construction; the rig idles between takes,
  not inside them. Q23's Answer/Applied-in
  lines are still blank although the deletion
  landed in f4e2378 -- the answerer's
  bookkeeping, noted here.)
- rules refreshed 2026-10-25 07:02 PDT —
  acknowledged, per Q29 (the owner's rule
  relayed by Claude): a failing-by-design
  probe lands under @unittest.expectedFailure
  with its question number in a comment, and
  an item is done only when the build's
  Windows shards are green for it. The three
  Windows fixture shapes are noted (stat-call
  counting, a non-releasing fake close, a
  directory or chmod standing in for an
  unreadable file). Also noted: the release
  window rule — hold pushes while HEAD is a
  `release:` commit whose build has not
  completed. Q30 (a RELEASE_TOKEN secret for
  tag-carried workflow files) stands in the
  questions file for the owner; it blocks
  Claude's release lane, not this queue.
  resources 2026-10-25T14:02:13Z: cores 2 | box cpu 53% | wall 1s | cmd cpu 0s = 0.4 cores busy | peak rss 33 MB | mem used 91% | disk free 166.4 GB | exit 0 | under-driven
  resources-top: hatch 256 MB, python 138 MB, python 12 MB, hatch-execd 7 MB, systemd 5 MB
  (scoped verification runs are short by
  construction; the rig idles between takes,
  not inside them.)
- A (refill) — Windows-hardening of the
  residual legs, same day: Claude's pass
  (382eb3a) made the two kill_tree tests and
  the monitor test true on Windows too (a
  patched POSIX identity with the kills
  recorded, instead of a POSIX `sleep`), and
  had already hardened InstallSmallLegsTest's
  getuid leg. Muse's parallel edits to the
  same tests were dropped in the rebase in
  favor of his.
- A (refill) — event-log tail legs (coverage
  run 40189711740): the Windows event log
  reader's broken-ElementTree return, its
  all-queries-failed return, its event
  formatting with the ATT&CK tag, and its
  character bound — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerResidualLegsTest
  (test_runner_last_edges.py), driven as on
  Windows with the wevtutil seam faked, the
  same pattern as the registry watch. Done
  when a coverage run shows the taken legs
  clean.
- A (refill) — wire and chat-server legs
  (coverage run 40189711740): protocol_v2's
  non-string answer riding empty, the
  oracle token check's non-string refusal,
  the chat server's deterministic page over
  the real loopback server, and the mailbox
  module's default log line — taken
  2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  AwaitAnswerNonStringLegTest
  (test_protocol_v2_messages.py),
  RunnerResidualLegsTest
  (test_runner_last_edges.py),
  MailboxDefaultLogLegTest
  (test_transport_shells.py). Recorded
  without a take: _oracle_instruction_kind's
  post-prefix empty-words return cannot
  fire (the lead is a single-space join of
  nonempty tokens, so a matched polite
  prefix always leaves a word behind); and
  ask_model's answerless-retry return
  cannot fire (a guard-tripping reply
  carries its "answer" key, and an absent
  key reads as None, which the format guard
  passes). Done when a coverage run shows
  the taken legs clean.
- A (refill) — dri, audit-report and
  remediation legs (coverage run
  40189711740): the retained scan's non-JSON
  pass-over, the fused score's stale-alert
  skip, the audit report's no-security-module
  read, and the Windows creation-time
  reader's unreadable-times answer (kernel32
  faked at the seam, so the leg runs on any
  platform) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DriResidualLegsTest (test_dri.py),
  ReadEntriesNoSecurityLegTest
  (test_audit_report.py),
  WinCreatedTicksLegTest
  (test_remediation.py). Done when a coverage
  run shows the taken legs clean.
- A (refill) — job-fuzz mutator legs
  (coverage run 40189711740): the truncate,
  duplicate, drop, null-byte and splice
  mutators' refusals, the dictionary
  builder's non-job seed, and the command
  split on both platform shapes — taken
  2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MutatorRefusalLegsTest (test_job_fuzz.py).
  Recorded without a take: _mut_blank_line's
  refusal cannot fire -- _script_lines is
  str.split, which never returns an empty
  list. Done when a coverage run shows the
  taken legs clean.
- A (refill) — runner.py residual legs
  (coverage run 40189711740): _load_mod both
  failure shapes, the job-user face's
  setgroups, _write_json under the binary
  flag, a payload-less message body, the
  remediation audit's silent return, the
  sensor core's unavailable and config-error
  answers, the ask function's blank answers,
  the opinion note's truncation and refusals,
  the job description's timeout member, the
  query handler's unexpected-error branch,
  kill_tree's extra pids and failed-kill
  swallows, the disk claim guards, save_seen's
  merge over the on-disk key list,
  load_retained's unprovable containment, an
  already-listening inference daemon, the
  monitor's alerts guards, the registry
  watch's snapshot-write swallow, and the
  confinement followup's unmeasurable
  quarantined file — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerResidualLegsTest
  (test_runner_last_edges.py) and
  ConfinementFollowupTest
  (test_remediation.py). Recorded without a
  take: save_seen.merge's not-a-dict reset
  cannot fire (_with_seen_file coerces the
  disk value to a dict before the mutator
  runs); load_retained's containment-mismatch
  return cannot fire through the seam (the
  stored path is built flat under the
  realpath'd retained dir and a symlinked
  file is refused one check earlier);
  ensure_inference_ready's hostless-endpoint
  return cannot fire (inference_config
  already refused every endpoint without a
  hostname). Done when a coverage run shows
  the taken legs clean.
- A (refill) — DTLS record legs (coverage run
  40189711740): the record opener's sequence
  wrap-back, the server core's by-address
  record route, and the fragment-reassembly
  paths — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RecordSealerWrapBackTest,
  FeedRecordByAddressTest,
  FragmentReassemblyGarbageTest
  (test_dtls.py). Recorded without a take:
  the parse-failure returns after fragment
  reassembly (dtlsproto 1002 and 1401) cannot
  fire -- the fragment buffer returns only
  messages built by _hs_message, whose header
  and length always parse; probed over
  completed shapes of several sizes.
  DtlsServerCore.tick's by-address sweep
  (1622-1624), listed on the same map, was
  already taken in 237a9c5 after the map's
  HEAD. Done when a coverage run shows the
  taken legs clean.
- A (refill) — installer legs (coverage run
  40189711740): _posix_uid's no-getuid answer,
  _path_exists' raising check, a fresh config
  with the setup module unimportable under
  both spellings, and the host install gate's
  refusal on the one-home and legacy layouts
  — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  InstallSmallLegsTest (test_install_edges.py).
  Done when a coverage run shows the taken
  legs clean.
- A (refill) — watcher, decoder, pipe and
  baseline legs (coverage run 40189711740):
  job-watcher's empty-history skip, softflowd's
  zero-length template and short IPFIX answers,
  the file transport's main loop pass (jobs and
  results scans, plus a failed pass logged not
  fatal), cert-sentinel's answering TLS target
  — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  EmptyRunsJobLegTest
  (test_job_watcher_main.py),
  DecodeEmptyLegsTest (test_softflowd_feed.py),
  FileMainLoopLegTest
  (test_transport_shells.py),
  ReadLiveTlsTargetLegTest
  (test_cert_sentinel.py). Recorded without a
  take: detection update_baseline line 160
  cannot fire -- the loader assigns the loaded
  value only when it is a dict and the starting
  value is a dict, so the baseline is a dict at
  that line on every path (probed with list,
  string, number and null baseline files under
  the full detection suite; the line stays
  missing while all around it runs); and its
  O_NOFOLLOW / O_BINARY flag bodies (198 / 200)
  are a platform-mirror pair -- each runs only
  where the attribute exists, and each map
  shows the other platform's line covered.
  Done when a coverage run shows the taken
  legs clean.
- A (refill) — feed and watch main legs
  (coverage run 40189711740): zeek-feed's and
  osquery-feed's tunables guards and
  undeliverable answers, crash-watch's and
  airwaves' partial deliveries, airwaves'
  non-object link clean — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MainDeliveryRefusalLegTest
  (test_zeek_feed.py and
  test_osquery_feed.py),
  MainPartialDeliveryLegTest
  (test_crash_watch.py and test_airwaves.py).
  Done when a coverage run shows the taken
  legs clean.
- A (refill) — sense legs (coverage run
  40189711740): service-watch's flap reset and
  partial delivery, sky-watcher's dead-rate
  answer, tripwire's path-part exclusion,
  usb-arrivals' twin collapse, cert-sentinel's
  missing decoder, failed-login's impossible
  ISO date, latency-post's tunables guard —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FlapResetAndPartialDeliveryTest
  (test_service_watch.py),
  TimeToVisibleOmegaLegTest
  (test_sky_watcher.py),
  ExcludedPartMatchLegTest (test_tripwire.py),
  TwinDevicesLegTest (test_usb_arrivals.py),
  ReadCertFileNoDecoderLegTest
  (test_cert_sentinel.py),
  ParseEventBadIsoLegTest
  (test_failed_login_watch.py),
  ReadLiveTunablesLegTest (test_latency_post.py).
  Recorded without a take: sky-watcher
  sun_elevation_deg's hour-angle wrap (231)
  cannot fire -- the true solar time is taken
  mod 1440, so the angle is never below -180.
  Done when a coverage run shows the taken
  legs clean.
- A (refill) — DTLS, OAuth and NATS small legs
  (coverage run 40189711740): the server
  core's by-address tick sweep, the pipe's
  floor-check skip and refused send, the
  consent server's silent error, the token
  store's flag line, the NATS token-only URL,
  closed-server read and ping, and the silent
  default log — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsServerTickSweepTest and
  DtlsPipeSmallLegsTest (test_dtls.py),
  OAuthSmallLegsTest (test_oauth_store.py),
  NatsSmallLegsTest (test_transports.py).
  Recorded without a take: the email pipe's
  _subject_body fallthrough (line 61) cannot
  be produced through the stdlib parser on
  this platform -- every parsed shape decodes
  to bytes; the line guards other parser
  behaviors. Done when a coverage run shows
  the taken legs clean.
- A (refill) — board, platform card, learning,
  review and registry small legs (coverage run
  40189711740): board.set_logger's pair and
  no-op, platform_interpreter's Windows branch,
  tier_of's unset tier, learning._boolish's
  fallthrough, _trim_locked's replacement
  write, parse_review_patterns' bad id,
  confval.port's own line, defaulted_keys'
  non-object guard, and sandbox
  interpreter_binds' relative skip — taken
  2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  BoardSetLoggerLegsTest (test_board.py),
  PlatformCardLegsTest (test_platformcard.py),
  LearningSmallLegsTest (test_oracle_learning.py),
  ReviewPatternIdLegTest (test_review.py),
  ConfvalPortAndDefaultedLegsTest
  (test_defaults_table_hunt.py), and
  InterpreterBindsRelativeLegTest
  (test_confinement.py). Done when a coverage
  run shows them clean.
- A (refill) — extsources small legs, second
  batch (coverage run 40189711740): _regex and
  parse_declaration guards, the https-only
  redirect pass-through, _commit_for's non-SHA
  refusal, _safe_member's portable shapes,
  _strip_top's split answer, load_states'
  unusable names, _entry_line's branch naming,
  is_withheld's plain paths — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ExtsourcesSmallLegs2Test in
  runner/tests/test_extension_sources.py.
  Recorded without a take: _clean_rel_path's
  empty-parts raise (278-279) cannot fire --
  the only values that would empty the parts
  are rejected by the guards above it. Done
  when a coverage run shows the taken legs
  clean.
- A (refill) — send_job and send_dtls guards
  (coverage run 40189711740): the secret pattern
  and presence refusals, sign_payload's
  non-object refusal, _extract_signed's
  malformed tail, _object_start's missing
  object, repair_line's non-object, the board
  commands' reply_to member, and _build_body's
  key_id member — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SendJobGuardLegsTest in
  runner/tests/test_send_job_verify.py and
  BuildBodyKeyIdTest in
  runner/tests/test_send_dtls_main.py. The
  same map's send_dtls main and _pump lines
  are covered locally by the full in-process
  suite (measurement artifact family). Done
  when a coverage run shows the taken legs
  clean.
- A (refill) — protocol_v2 and extensions legs
  (coverage run 40189711740): _remember_other's
  blank answer, store_answer's temp-cleanup
  swallow, _parse_upstream's non-object block,
  send_local_signal's shutdown swallow — taken
  2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RememberOtherLegsTest in
  runner/tests/test_protocol_v2_messages.py
  and UpstreamAndSignalLegsTest in
  runner/tests/test_extensions.py. Recorded
  without takes: should_ask's non-dict guard
  (173-174) cannot fire -- enabled() on the
  line above already requires a dict -- and
  sign_envelope's brace check (441) cannot
  fire -- a serialized object always closes
  with the brace. Done when a coverage run
  shows the taken legs clean.
- A (refill) — wire guards (coverage run
  40189711740): jobcrypto's non-string secret,
  hkdf zero salt, is_envelope non-object and
  encrypt_body non-string refusals, and
  verify.check_policy_constraints' non-string
  arg skip — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  CryptoGuardLegsTest in
  runner/tests/test_jobcrypto.py and
  PolicyArgsSkipLegTest in
  runner/tests/test_v31_verify.py. Recorded
  without takes: verify.audience_allows'
  module-absent return (661-662) is subsumed
  by check_audience's own absent-module guard
  on the same global, and verify_body_keyed's
  non-ValueError wrap (725-726) cannot be
  produced through the signer seam (bodies the
  signer can serialize parse, or fail as
  ValueError, at every probed depth). Done
  when a coverage run shows the taken legs
  clean.
- A (refill) — runner.py legs, sixth batch
  (coverage run 40189711740): oracle_window's
  non-dict config and deterministic banner,
  oracle_cli's mid-turn Ctrl-C, do_POST's
  deterministic answer over a real loopback
  server, and poll_once's supervisor-check
  failure — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs6Test in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — runner.py legs, fifth batch
  (coverage run 40189711740): _v2_leave_unseen's
  non-string id and set cap, _v2_before_execute's
  absent-module return and determination
  segment, run_inspect's sources branch without
  the module — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs5Test in
  runner/tests/test_runner_last_edges.py.
  Recorded without a take: answer_queries'
  second exec_result normalization (2337-2338)
  is unreachable by construction -- the first
  check at 2325-2326 already replaced any
  non-dict with {}. Done when a coverage run
  shows the taken legs clean.
- A (refill) — runner.py legs, fourth batch
  (coverage run 40189711740):
  _ingest_local_envelope's catch-all,
  _local_watch's guard and per-watch swallow,
  _transports_arg's empty refusals, and
  _append_security_event's rollover open under
  the Windows flag line — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs4Test in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — runner.py legs, third batch
  (coverage run 40189711740): _admit_object's
  non-string id, malformed envelope and
  envelope/body key mismatch (real signed
  bodies throughout), _learning_reconcile's
  disabled gates, _learning_model_candidate's
  unparseable reply and failed candidate write,
  _wake_gate_decide's non-record and
  unconvertible clock, _write_seen_unlocked's
  cleanup swallow — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs3Test in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — runner.py fail-soft legs, second
  batch (coverage run 40189711740):
  _extension_source_targets when transport
  discovery raises, _extension_sources_tick's
  guard and deepcopy fallback, _oracle_host_ok
  when urlparse fails, _take_body's negative
  length, update_llama_from_config's failed
  pull — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs2Test in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — runner.py fail-soft legs (coverage
  run 40189711740): the withheld-path helpers
  when the sources module raises, _staged_dest
  when realpath fails, download's transient
  re-raise and bad-URL refusal, save_retained's
  close-failure swallow, _append_brief's write
  swallow, the brief thread's opinion swallow,
  _file_fresh_lines' state-write swallow,
  _tail_marked's vanished file, _extension_registry's
  load failure and _extension_sources_note's
  raise — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegsTest in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — `runner/cloud/send_dtls.py`
  `_wait_for`'s dead-peer and dry-pump exits
  (coverage run 40189711740: lines 132, 134) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  WaitForLegsTest in
  runner/tests/test_send_dtls_main.py. The same
  map's main lines 174-175 are a measurement
  artifact: the full in-process suite covers
  them locally (they are the --kind argument
  declarations, executed by every main call);
  no take. Done when a coverage run shows
  _wait_for clean.
- A (refill) — job-fuzz state caps and quiet legs
  (coverage run 40189711740): the energy, buckets
  and filed caps trimming to the most valuable,
  _load_quiet with no load average to read,
  _prune_archive passing over an unremovable
  file, and _minimize_variant passing over an
  unwritable archive — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  CleanStateCapLegsTest in
  runner/tests/test_job_fuzz.py. Done when a
  coverage run shows them clean.
- A (refill) — `runner/ops/extsources.py` small
  legs (2 lines each never run, coverage run
  40189711740): Fetcher.get_json's not-JSON
  refusal, resolve_github's unresolvable named
  ref and missing default branch, remote_urls'
  archive and unsafe-name shapes, owner_policy's
  bad per-extension overrides,
  manifest_upstream_of's non-path and invalid
  block, _clean_targets' unusable entries —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ExtsourcesSmallLegsTest in
  runner/tests/test_extension_sources.py. Done
  when a coverage run shows them clean.
- A (refill) — four more two-line legs (coverage
  run 40189711740): `sysmon_feed._parse_xml_event`
  broken-inside, `softflowd_feed`
  `_parse_v9_templates` truncated fields,
  `training_watch._run_alive` cannot-run, and the
  NATS client's expired deadline, refused send and
  refused close — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ParseXmlBrokenInsideTest
  (runner/tests/test_sysmon_feed.py),
  DecodeDamageLegsTest (test_softflowd_feed.py),
  RunAliveLegsTest (test_training_watch.py), and
  a case in NatsNextMessageLegsTest
  (test_transports.py). Recorded without a take:
  softflowd decode_datagram's except (401-402)
  sits behind both decoders' length guards;
  dri send_telegram's second dumps failure
  (504-505) cannot fire once both fields are
  text; dri's fused-score excepts and
  training-watch's loss float except sit behind
  helpers that are total by design
  (alert_score sanitizes its weight; the loss
  pattern only captures float-shaped text, and
  float() of an over-range literal is inf, not an
  error). Done when a coverage run shows the
  taken legs clean.
- A (refill) — `runner/guard/confval.py::_parse`
  type legs and `runner/wire/protocol_v2.py::`
  `_other_answers` unsafe-id leg (2 lines each
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ConfvalParseLegsTest in
  runner/tests/test_defaults_table_hunt.py (a
  boolean is never a number; a number passes
  through) and OtherAnswersLegsTest in
  runner/tests/test_protocol_v2_messages.py (an
  unsafe question id reads empty). Recorded
  without a take: dtlsproto.x25519's final
  conditional swap (186-187) is unreachable by
  construction -- the ladder's last processed bit
  is the clamped scalar's bit 0, which clamping
  always clears, so the swap is always false
  (verified by coverage over crafted and RFC
  scalars); transports'
  discover_transport_extensions lines 255/260 are
  continuation lines of the refusal message the
  ManifestContractTest refusal cases already
  assert -- a measurement artifact, not a gap.
  Done when a coverage run shows the taken legs
  clean.
- A (refill) — six two-line legs (coverage run
  40189711740): `job_watcher._record_observation`
  size/timestamp, `personal_docs`
  per-entry stat failure, `board._runner_logger`
  bound/no-op, `opinion._shape_fits` posix and
  unknown shapes, `resource_sentinel`
  `_read_process_count` without /proc, and
  `auditreport._entry_ts` unparsable — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  JobWatcherRecordLegsTest
  (runner/tests/test_watchers.py),
  RunnerLoggerLegsTest (test_board.py),
  ShapeFitsLegsTest (test_oracle_opinion.py),
  ProcessCountLegsTest (test_resource_sentinel.py),
  EntryTsLegsTest (test_audit_report.py), and a
  case in test_personal_docs.py. Done when a
  coverage run shows them clean.
- A (refill) — `log_sentinel._prev_inode` and
  `_compiled_groups`, `training_watch._read_gpu`,
  and the `backup_freshness` / `crash_watch`
  `read_live` mid-scan races (2 lines each never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PrevInodeAndGroupsLegsTest in
  runner/tests/test_log_sentinel.py (a corrupt
  stored inode reads as unknown; an un-compilable
  group is left out), GpuReadLegsTest in
  runner/tests/test_training_watch.py (an
  unparsable nvidia-smi line yields to the next),
  and MidScanVanishTest in
  runner/tests/test_backup_freshness.py and
  runner/tests/test_crash_watch.py (a file gone
  before its stat is passed over). Recorded
  without a take: senses.load_alerts' per-record
  scoring guard (426-427) and pi_health
  _read_throttled's int guard (203-204) are
  unreachable by construction -- the first sits
  behind isinstance checks on plain JSON dicts,
  the second behind a hex-only pattern (base 16
  is exempt from the conversion cap). Done when
  a coverage run shows the taken legs clean.
- Q29 FILED by Muse 2026-10-25 — the Q28 defect
  survives in airwaves' other two signal
  conversions (parse_iw_link ~327, parse_nmcli
  ~230): OverflowError escapes both parsers on a
  huge-digit signal, killing the sense's cycle.
  Two failing-by-design probes in
  runner/tests/test_airwaves.py pin the Q28
  contract (the reading survives, signal None).
  Claude's lane to fix; the probes are the
  verification when it lands. FIXED by Claude
  (both parsers' guards widened — verified in the
  local full-suite run at 9a01d0a: 3,571 tests, 0
  failures). Q29 CLOSED by evidence 2026-10-25.
- A (refill) — `runner/wire/verify.py` fallback
  legs, `runner/guard/sandbox.py::`
  `_userns_restricted` read legs and
  `runner/wire/mailbox.py::_xoauth2_raw` (2 lines
  each never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  VerifyFallbackLegsTest in
  runner/tests/test_blackbox_findings.py (a
  control-inserted body verifies against the
  cleaned form; a body nested past the
  interpreter's limit reports invalid JSON; the
  audience check binds nothing when the security
  layer is absent or the payload is not an
  object), UsernsRestrictedLegsTest in
  runner/tests/test_confinement.py (the sysctl
  read, and its absence read as not restricted),
  and XOAuth2RawTest in
  runner/tests/test_email_pipe_coverage.py.
  Residue: verify_body's and verify_body_keyed's
  non-object guards (lines 191 and 703) are
  unreachable by construction -- the extractor
  only returns brace-balanced spans opening with
  "{", which parse to an object or not at all.
  Done when a coverage run shows the legs clean.
- A (refill) —
  `runner/transport_extensions/dtls/__main__.py::`
  `DtlsPipe._pump_results` delivery legs and
  `runner/extensions/release-drop/release_drop.py`
  `::read_live` mid-scan races (4 lines each never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsPumpResultsLegsTest in
  runner/tests/test_dtls.py (a gone session's
  result is acked into done with the reason
  logged; a body without a trailing newline gets
  one on the wire) and MidScanVanishTest in
  runner/tests/test_release_drop.py (a file gone
  before its stat, or unreadable at its hash, is
  passed over and the pass still answers). Done
  when a coverage run shows both clean.
- A (refill) —
  `runner/transport_extensions/nats/__main__.py::`
  `NatsClient.next_message` control lines and
  `_read_exact` mid-message timeout (4 lines each
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NatsNextMessageLegsTest in
  runner/tests/test_transports.py, over a scripted
  socket: a PING is PONGed and skipped, PONG/+OK
  are skipped, an -ERR raises naming the server's
  text, and a payload that stops mid-message is a
  timeout. Done when a coverage run shows both
  clean.
- A (refill) —
  `runner/extensions/softflowd-feed/softflowd_feed.py`
  `::collect_flows` window and close legs (3 lines
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  CollectFlowsClockTest in
  runner/tests/test_softflowd_feed.py: the pass
  ends when the window closes at the top of the
  loop, and a socket that refuses to close is
  still a quiet empty pass. Done when a coverage
  run shows the function clean.
- A (refill) — `runner/runner.py::`
  `make_oracle_server.Handler.do_POST`
  deterministic leg (3 lines never run, coverage
  run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DeterministicAskTest in
  runner/tests/test_oracle_chat.py: in
  deterministic mode an /ask question is answered
  from the box's records (the Pi Light answer) and
  no model call is attempted. Residue: the
  json.dumps fallback (10141-10142) is unreachable
  by construction -- the payload is rebuilt only
  from isinstance-str-checked values. Done when a
  coverage run shows the leg clean.
- A (refill) — `runner/wire/mailbox.py::send_mail`
  unbuildable leg and `runner/oracle/resources.py`
  `::check_resources` corrupt-state legs (3 lines
  each never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SendMailUnbuildableTest in
  runner/tests/test_email_pipe_coverage.py (a
  newline recipient is logged as not built and
  never sent) and CorruptLastAlertTest in
  runner/tests/test_resources.py (a non-numeric
  last-alert stamp reads as never-alerted; a
  disabled block with a valid threshold returns
  before any state -- the older disabled case
  pairs False with threshold 0.0, which the parser
  refuses first). Done when a coverage run shows
  both clean.
- A (refill) — `runner/wire/platformcard.py::`
  `os_family` non-host legs and
  `runner/ops/extsources.py::load_declaration`
  quiet legs (3 lines each never run, coverage run
  40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  OsFamilyLegsTest in
  runner/tests/test_platformcard.py (win*/darwin/
  unrecognized platform names under a patched
  sys.platform) and LoadDeclarationLegsTest in
  runner/tests/test_extension_sources.py (a
  non-path declares nothing; an unreadable
  declaration file returns its problem). Done when
  a coverage run shows both clean.
- A (refill) — `runner/runner.py::`
  `handle_query_mail` bad-envelope leg (3 lines
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  QueryAudienceTest's broken-envelope case in
  runner/tests/test_audience.py: a query whose
  envelope verifies but cannot be decrypted is
  marked seen, never answered, and does not break
  the poll. Rules refreshed 2026-10-25 05:41 PDT
  (compaction reset; repo AGENTS.md rules 7-9,
  standing orders, open questions re-read). Done
  when a coverage run shows the branch clean.
- A (refill) — `runner/runner.py::`
  `_extension_sources_policy` (4 lines never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ExtensionSourcesPolicyTest in
  runner/tests/test_extension_sources.py: with the
  sources module missing the policy is None, and a
  newly appearing problem is recorded and
  announced exactly once with its consequence.
  Done when a coverage run shows the function
  clean.
- A (refill) — `runner/wire/jobcrypto.py::`
  `decrypt_body` defect legs (3 lines never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DecryptBodyDefectsTest in
  runner/tests/test_jobcrypto.py: a ciphertext
  truncated below its tag and a plaintext that
  decrypts to non-UTF-8 bytes each raise
  JobCryptoError naming the defect. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/guard/defaulted.py::`
  `default_for` and `is_defaulted` enum legs
  (3 lines each never run, coverage run
  40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DefaultedEnumLegsTest in
  runner/tests/test_defaults_table_hunt.py: the
  one enum key's default answers, an unusable
  value for it is defaulted, a usable one is not,
  and an unknown key has no default and is never
  defaulted. Done when a coverage run shows both
  clean.
- A (refill) — `runner/extensions/job-watcher/`
  `job_watcher.py::read_live` listing legs and
  `_clean_state` (4 lines each never run, coverage
  run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  JobWatcherReadLiveTest and JobWatcherCleanStateTest
  drives in runner/tests/test_watchers.py: an
  unlistable store reads empty, an unstattable
  record is skipped, the seen cap keeps the newest
  entries, and misshapen job entries drop or repair.
  Done when a coverage run shows both clean.
- A (refill) — `runner/runner.py::`
  `_serve_local_signals` isolation legs and
  `_report_extension_sources` outcomes (4 lines
  each never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ServeLoopIsolationTest in
  runner/tests/test_local_signals.py (a raising
  handler and a failing close are both swallowed
  and the loop accepts again) and
  ReportExtensionSourcesTest in
  runner/tests/test_extension_sources.py (missing
  module and invalid policy are silent; on and off
  each say their one line). Done when a coverage
  run shows both clean.
- A (refill) — `runner/runner.py::`
  `_release_saved_claims` failure legs (4 lines
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReleaseSavedClaimsEdgesTest in
  runner/tests/test_protocol_v2_messages.py: an
  unreadable claim file (a directory) and a claim
  whose removal fails are both passed over while
  the releasable claim is released and the unseen
  claim is left alone. Done when a coverage run
  shows the function clean.
- A (refill) — `runner/wire/protocol_v2.py::`
  `_publish_answer` race legs (4 lines never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PublishAnswerRaceTest in
  runner/tests/test_protocol_v2_messages.py: a
  slot that vanishes between the lost link and the
  check is retried and won, and a move-aside that
  keeps failing gives up after its attempts with
  the bad file untouched. Done when a coverage run
  shows the function clean.
- A (refill) — `runner/extensions/sky-watcher/`
  `sky_watcher.py::fetch_position` (4 lines never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  one FeedSampleTest drive in
  runner/tests/test_sky_watcher.py with the
  transport faked: the request goes to the given
  URL with the watcher's user agent and the
  documented timeout, and the parsed sample is
  sample_from_feed's. Done when a coverage run
  shows the function clean.
- A (refill) — `runner/ops/install.py::`
  `gather_host_facts` marker legs and
  `_warn_personal_documents` (4 lines each never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  GatherAndGateTests drives in
  runner/tests/test_hostclass.py through the
  function's own probe seams: a marker file and an
  os-release id each name webOS, an Android
  environment names android, and a Pi identified
  by cpuinfo alone still decides as a Pi; and the
  personal-documents warning swallows a missing
  module whole. Done when a coverage run shows
  both clean.
- A (refill) — `runner/ops/install.py::host_decision`
  (4 lines never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — four
  HostDecisionTests drives in
  runner/tests/test_hostclass.py: non-dict facts
  read as no facts; a Docker host with a USB
  accelerator notes both facts; an ARM board with
  one notes both; plain Linux with one is the
  linux case whose note is the accelerator warning
  alone. Done when a coverage run shows the
  function clean.
- A (refill) — `runner/ops/extsources.py::`
  `_local_files` and `_tree_bytes` (4 lines each
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LocalFilesEdgesTest in
  runner/tests/test_extension_sources.py: a symlink
  source yields nothing, the visit budget stops the
  walk mid-tree, an unsizable file is skipped, and
  the byte counter answers 0 for an unsizable
  non-directory and skips an unsizable member.
  Done when a coverage run shows both clean.
- A (refill) — `runner/ops/extsources.py::`
  `extract_archive`'s write() legs (4 lines never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  two ExtractTest drives in
  runner/tests/test_extension_sources.py: a member
  under a symlink planted in the destination is
  skipped by the escape check while its sibling
  extracts (the names themselves are sanitized
  upstream, so the planted link is the check's
  live case), and a member whose target is already
  a directory is counted and skipped. Done when a
  coverage run shows write() clean.
- A (refill) — `runner/ops/extsources.py::`
  `oracle_note` (4 lines never run, coverage run
  40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  OracleNoteEdgesTest in
  runner/tests/test_extension_sources.py: an
  unloadable state store yields the empty note
  (the function never raises), and more provided
  sources than the line budget fold into the
  counted trailer. Done when a coverage run shows
  the function clean.
- A (refill) — `runner/ops/auditreport.py::`
  `_is_dangerous` fallback (4 lines never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DangerousFallbackTest in
  runner/tests/test_audit_report.py: when the
  security module's own check raises, the answer
  falls back to its name list (a listed name in
  any case is dangerous; an unlisted or non-string
  name is not). Done when a coverage run shows
  the function clean.
- A (refill) — `runner/extensions/airwaves/`
  `airwaves.py::parse_iw_scan` conversion guards
  (4 lines never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the
  channel guard pinned passing (a digit string
  past the conversion cap degrades to None), and
  the signal guard became a FINDING, filed as
  Q28: it cannot fire (float() of a digits-only
  match returns inf, never ValueError), and the
  real failure -- int(inf) OverflowError -- escapes
  the parser, read_live, and main's handlers. The
  probe is on main failing by design in the
  four-part format; the item is done as filed.
- A (refill) — `runner/extensions/job-fuzz/`
  `job_fuzz.py::_num`, `_mut_unicode_edge`,
  `_mut_trailing_blank` (4 lines each never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — three
  MutatorTest drives in runner/tests/test_job_fuzz.py:
  the unicode-edge variant appends exactly its edge
  line and nothing else; trailing blanks are the
  seed plus one to three newlines and an empty seed
  declines; the number renderer prints ints as
  themselves, whole floats as ints, fractions
  compactly. Done when a coverage run shows all
  three clean.
- A (refill) — `runner/ops/posture.py::`
  `_windows_file_restricted` deep branches (6 lines
  missing on Windows, none on Linux, coverage run
  40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the full
  drive already existed inside a POSIX-gated test
  whose skip took the ACL leg down on the one
  platform the function exists for;
  WindowsAclBranchesTest in
  runner/tests/test_posture_gaps.py runs the same
  _Api fake with no platform gate: ACL-info failure
  degrades to None, an empty ACL is restricted, six
  ACEs walk the failure/null/type/mask branches to
  the broad-read hit. Done when a coverage run
  shows the six lines run on Windows too.
- A (refill) — the tailing senses' `read_new_events`
  open-failure leg, one 4-line gap in each of seven
  senses (coverage run 40189711740, both
  platforms): zeek-feed, failed-login-watch,
  falco-feed, osquery-feed, suricata-feed,
  sysmon-feed, wazuh-feed — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — one
  test_an_unreadable_file_keeps_its_entry per
  sense's ReaderTest: a path that stats fine but
  cannot be opened (a directory is the
  deterministic stand-in for the stat-then-open
  race) yields no events and keeps its previous
  reader entry, sysmon's partial line included —
  the docstrings' "missing or unreadable" clause,
  whose missing half was already pinned. Done
  when a coverage run shows all seven legs run.
- A (refill) — `runner/wire/transports.py::`
  `service_channel` (4 lines never run, both
  platforms, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  and the take became a FINDING, filed as Q25: the
  never-run lines are the rollback-on-failed-ack
  branch, and they never run because
  IncomingMessage.ack() discards the wrapped ack's
  return, so `acked is False` is unreachable and a
  refused ack never drops the seen-set entry the
  docstring promises. The probe
  (ChannelEdgeTest.test_a_failed_ack_must_roll_
  back_probe in runner/tests/test_transports.py)
  is on main failing by design in the four-part
  format; it goes green when the ack returns its
  result (Claude's lane). The item is done as
  filed; the branch's coverage follows the fix.
- A (refill) — `runner/oracle/remediation.py::`
  `enforce_quarantine_bounds` Windows residue
  (6 lines, coverage run 40189711740; the function
  is fully run on Linux, and the Windows leg's own
  fixtures cannot build these states) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  three QuarantineTest drives in
  runner/tests/test_remediation.py with stubs that
  run on both platforms: an unstatable entry sorts
  as epoch 0 and is archived first; a taken archive
  name suffixes -2, -3 rather than clobbering; a
  failed move stops the pass, keeps the entry, and
  does not raise. Done when a coverage run shows
  the six lines run on Windows too. With it, a
  disposition under the skip rule:
  `sandbox.build_bwrap_command` (6 lines, Windows)
  builds a Linux bubblewrap argv and cannot apply
  on Windows — platform-inapplicable there, covered
  on Linux.
- A (refill) — `runner/runner.py::snapshot_outside`
  realpath fallbacks (4 lines never run, both
  platforms, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SnapshotRealpathFallbackTest in
  runner/tests/test_confinement.py: a realpath
  failure on the workspace, and one on a directory
  mid-walk, each fall back to the absolute path and
  the snapshot still lands (the outside file in,
  the workspace's own files out). Done when a
  coverage run shows the four lines run.
- A (refill) — `runner/ops/auditreport.py` import
  seam (the fallback block, 5 lines never run on
  either platform, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ImportSeamTest in runner/tests/test_audit_report.py:
  with the package import blocked, the script-mode
  sibling answers; with neither importable the
  module still loads and its readers answer empty.
  Done when a coverage run shows the block clean.
  With it, two dispositions under the queue-A skip
  rule, from the same map: `resources._mem_fraction`
  (8 lines, Windows) is the /proc/meminfo body --
  platform-inapplicable on Windows (no /proc there;
  the None return runs), covered on Linux;
  `posture._check_file_perms` (8 lines, Windows) is
  the POSIX stat body behind the function's own
  os.name return -- platform-inapplicable on
  Windows, covered on Linux.
- A (refill) — `runner/extensions/softflowd-feed/`
  `softflowd_feed.py::_flow_from_values` and
  `_parse_ipfix_templates` (5 lines each never run,
  coverage run 40189711740, the newest completed
  run; the CI queue is backlogged a dozen deep, so
  re-ranking works from that map) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DecoderEdgesTest in
  runner/tests/test_softflowd_feed.py: an address
  falls back to its IPv6 field when no IPv4 field
  is present; a flow with only its LAST switched
  stamp anchors both ends on it; a template
  truncated mid-field or mid enterprise number is
  not recorded at all; a variable-length field
  records its template tainted (a clean field is
  the untainted control). Done when a coverage run
  shows both clean.
- rules refreshed 2026-10-25 05:22 PDT, on the
  owner's word ("update your orders"): pulled
  through 6853314. Two answers change the queue.
  Q22 is answered in f4e2378 (release 3.12.66):
  the mutation signal's blindness was mutmut's
  coverage pass dying on the archived probes'
  shared basename, not the stats phase; the fix
  ignores the archive folders for pytest and adds
  a mutation floor that fails a collapsed signal.
  The D4 triage re-runs on the first tag run after
  that release and takes the survivors then; no
  tag exists yet. Q23 is applied in the same
  commit by deletion -- the three uncalled
  _is_number copies are out of aide-feed,
  usb-arrivals and wire-arrivals; the entry's
  Answer line is still blank in the questions
  file, Claude's bookkeeping to finish. S and R
  are filled and await their switch-proofs
  verdicts (6853314 lets a running leg finish
  instead of cancelling it); A and D resume
  behind them.
- Q27 CLOSED by evidence, verified by Muse
  2026-10-25: switch-proofs run 40194182584 (HEAD
  9873ba3, carrying the fb56cfd lock) finished all
  three legs green (25/25, 27/27, 16/16), and the
  Windows leg's report -- downloaded and read by
  Muse, not taken on report -- shows
  R2.audit_rollover PROVEN on the locked writer.
  Grok's Q26 note records the same run.
- Q25, Q27, Q28 ANSWERED AND APPLIED by Claude
  in fb56cfd (release 3.12.67; 3.12.66 was built,
  not tagged -- its content ships in .67). Q25:
  IncomingMessage.ack() returns the result; the
  probe is green (Muse verified locally; Claude
  corrected the probe's outbox count, which had
  counted the outbox's done/ folder -- a test bug,
  owned). Q27: one re-entrant lock per process
  around the audit bound check, append and counts
  bump; Muse's R2 passes locally, and the Windows
  leg of the next finished switch-proofs run is
  the verdict. Q28: the airwaves signal guard now
  catches (OverflowError, ValueError) as proposed;
  the probe is green (Muse verified locally). The
  .67 stamp and the D4 mutation triage both wait
  on the .67 tag.
- S/R VERDICTS, switch-proofs run 40192518684
  (the 3.12.66 release commit; Grok's watch, Q26,
  reported the finish): Linux 25 of 25 proven,
  root 27 of 27, Windows 15 of 16. Queue S is
  DONE: every switch proven on its leg, the four
  walls on Linux, the drops on root, the templates
  and both Oracle entries everywhere they apply.
  Queue R is DONE as proven for R1 (root), R3 and
  R4 (all legs), and DONE AS FILED for
  R2.audit_rollover: failed on Windows -- a
  concurrent audit append lost one entry whole,
  the Windows append-emulation overwrite; filed
  as Q27 with the run's report as evidence. The
  proof stays red on that leg until Claude's fix
  lands; nothing in S or R remains open for the
  campaign to write.
- R — roster R1.two_jobs, R2.audit_rollover,
  R3.seen_set, R4.config_write — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  runner/tests/test_enforce_races.py, every race
  driven with real threads and a barrier and
  asserting the security outcome: two jobs on one
  barrier each keep their own chowned workdir and
  its files (root leg), and two sandboxes share no
  /work with both decisions whole in the audit log
  (bwrap leg); a rollover raced by two writers
  loses and splits no entry over 25 rounds (the
  live and rolled files together hold every id
  exactly once, every line parsing); a replayed id
  is rejected on both orderings around a fresh job
  while two copies of a fresh job run it once; a
  config write plus the real hot reload landing
  provably mid-job moves the hot key only -- the
  security block is the identical object afterwards
  and the next job's gate still denies by the mode
  in force. The roster entries list them. Done
  when the switch-proofs workflow is green with
  all four proven on their legs.
- S — roster ORACLE.no_widening — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NoWideningTest in
  runner/tests/test_oracle_no_widening.py, through
  the real intake with a fake model throughout: a
  policy_env denial in enforce mode lands with the
  opinion machinery armed and the opinion is never
  formed (the gate is upstream of it); a repairable
  job whose repair would move it out of its pinned
  key's allowed_interpreters is refused on
  re-judgment and never runs, and runs repaired
  under a policy that allows the default (control);
  a model note saying "do not run this job" is
  attached to a clean job's result verbatim and the
  job runs exactly as it would have. The roster
  entry lists it. Done when the switch-proofs
  workflow is green with the entry proven.
- S — roster M7.templates — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the
  module already carried TemplateTest (existence,
  complete rendering, path consistency, the
  installer's unit mirrored, --help silent); the
  missing half was the parse: TemplateParseTest in
  runner/tests/test_hardening_templates.py renders
  each template and parses it in its grammar's
  shape (the unit through a real ini parser with
  the ExecStart argv equal to the installer's; the
  AppArmor block balanced with every rule
  comma-terminated and the three grants exact; the
  SELinux module's allows naming only declared
  types), and pins the README's claim that
  install.py never references the templates. The
  roster entry lists both classes. Done when the
  switch-proofs workflow is green with the entry
  proven.
- S — roster M6.wall.network, M6.wall.home,
  M6.wall.usr, M6.wall.work (the four sandbox walls
  as separate cases, each with its mode-off
  control) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  WallNetworkTest, WallHomeTest, WallUsrTest and
  WallWorkTest in runner/tests/test_confinement.py,
  each driving both modes through execute_job: a
  loopback listener reached with the mode off is
  unreachable in the sandbox; the base dir's marker
  is read off and invisible on; a /usr write is
  blocked on and lands off in a scratch tree; the
  workdir sits at /work with the base root and a
  sibling job's workdir unreachable on, read off.
  The four roster entries list them. Done when the
  switch-proofs Linux leg (bwrap) shows all four
  proven.
- rules refreshed 2026-10-25 05:07 PDT (Q24 read
  with the refresh: queues S and R now come first;
  the queue-A item below was already written when
  the reset landed and is closed out here)
- A (refill) — `runner/extensions/job-fuzz/`
  `job_fuzz.py::_scan_retained` (5 lines never run
  on either platform, coverage run 40189608702) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ScanRetainedEdgesTest in
  runner/tests/test_job_fuzz.py: a store that
  cannot be listed reads as empty; names that are
  not seed files are passed over; a seed that
  vanishes between the listing and its stat is
  skipped while its sibling is still read. The
  function is fully run under that class. Done
  when a coverage run shows it clean.
- rules refreshed 2026-10-25 04:48 PDT
- A (refill) — `runner/ops/extsources.py::`
  `pin_declaration` (5 lines never run on either
  platform, coverage run 40189608702) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PinDeclarationProblemsTest in
  runner/tests/test_extension_sources.py: project
  entries are not pinned; a failed archive
  download is an "archive:" problem on an
  otherwise pinned entry; a failed resolution is
  a problem with no resolved block. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/ops/extsources.py::`
  `_acquire_pass_lock` and `extract_archive` (5
  lines each never run on either platform,
  coverage run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PassLockEdgesTest and ExtractMemberEdgesTest in
  runner/tests/test_extension_sources.py: a lock
  whose age cannot be read is retried then given
  up on, not unlinked blind; an unusable root
  answers None; a free root takes the lock.
  Directory entries, zip and tar, are passed over
  uncounted; a member with no readable stream is
  counted skipped; more members than the cap is
  refused outright. Done when a coverage run
  shows both clean.
- A (refill) — `runner/ops/extsources.py::`
  `Fetcher._read_capped` and `Fetcher.download`
  (5 lines each never run on either platform,
  coverage run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FetcherStreamEdgesTest in
  runner/tests/test_extension_sources.py: a body
  past the cap is refused naming the cap; a read
  failing mid-stream is a SourceError naming the
  read, and a download removes its partial file; a
  close that fails is swallowed by both readers.
  Done when a coverage run shows both clean.
- A (refill) — `runner/transport_extensions/dtls/`
  `__main__.py::DtlsPipe.run_once` (5 lines never
  run on either platform, coverage run 40189608702)
  — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsRunOnceLegsTest in runner/tests/test_dtls.py:
  a dead socket still completes the pass; a receive
  that fails after a ready select drops the
  datagram and sends nothing; the core's tick
  output goes out on the socket. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/runner.py::reload_hot_config`
  (5 lines never run on either platform, coverage
  run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReloadHotConfigEdgesTest in
  runner/tests/test_defaults_table_hunt.py: a
  state that is not a dict reads as fresh and the
  reload proceeds; a config file that cannot be
  statted changes nothing; a hot verbose value
  that is neither a bool nor a string is ignored
  and named while a valid sibling key still
  applies. Done when a coverage run shows the
  function clean.
- A (refill) — `runner/runner.py::handle_board_mail`
  (5 lines never run on either platform, coverage
  run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  BoardMailRejectionsTest in
  runner/tests/test_runner_tail.py: an envelope
  sealed for another task id verifies but does not
  open, and is rejected and recorded as an
  encryption failure, with no ack. The remaining
  two lines, the dispatch's "unknown board kind"
  else, are unreachable by construction -- the
  subject gate admits exactly the four kinds the
  dispatch handles -- and the gate is pinned from
  the outside (a kindless subject is not board
  mail at all). Done when a coverage run shows
  only those two lines left.
- A (refill) — `runner/runner.py::`
  `_ingest_local_envelope_inner` (5 lines never run
  on either platform, coverage run 40189608702) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LocalEnvelopeIssuedAtTest in
  runner/tests/test_sense_delivery.py: a config
  whose secrets cannot be built rejects every
  envelope unread; an issued_at that does not
  parse and one that parses without a timezone
  are each rejected and nothing is stored; a zoned
  issued_at is stored (control). Done when a
  coverage run shows the function clean but the
  smaller tail.
- A (refill) — `runner/runner.py::_v2_hand_off` (5
  lines never run on either platform, coverage run
  40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  Version2HandOffFallbacksTest in
  runner/tests/test_cli_options.py: a transport
  list that cannot be read and a channel write
  that fails each degrade to the ordinary send,
  exactly once; a written channel is not sent
  again (control). Done when a coverage run shows
  the function clean.
- A (refill) — `runner/runner.py::_start_job_monitor`
  (5 lines never run on either platform, coverage
  run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  StartJobMonitorFallbacksTest in
  runner/tests/test_remediation_e2e.py: with the
  remediation module absent there is no monitor; an
  unreadable script and an opinion layer whose
  hints fail each still get a monitor, with no
  declared paths. Done when a coverage run shows
  the function clean.
- A (refill) — `runner/wire/board.py::Board.save`
  (5 lines never run on Linux, coverage run
  40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the two
  flag lines are the platform pair (O_BINARY on
  Linux, O_NOFOLLOW on Windows, each covered where
  it applies); the taken lines are the descriptor
  cleanup, pinned in runner/tests/test_board.py: a
  save failing after its tmp opens closes the
  descriptor, removes the tmp, and leaves the
  previous board untouched, and a failing close is
  swallowed the same way. Done when a coverage run
  shows only the platform line left.
- A (refill) — `runner/wire/mailbox.py::_load_oauth`
  (5 of its 6 lines never run on either platform,
  coverage run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LoadOauthSeamTest in runner/tests/test_oauth.py:
  the package import answers first; with it blocked,
  the script-mode fallback module is the one
  returned. Done when a coverage run shows the
  function clean.
- A (refill) — `runner/runner.py::run_variant` (8
  lines never run on either platform, coverage run
  40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunVariantFallbacksTest in
  runner/tests/test_run_variant.py: an unusable
  timeout reads as the cap itself; a variant with
  no job id runs under the default id; a work dir
  that cannot be created is exit 2, named on
  stderr; a failure in the execution path itself
  is an "error" report, never a raise. The function
  is fully run under that module locally. Done
  when a coverage run shows it clean.
- A (refill) — `runner/oracle/senses.py::`
  `_store_alert_report` (3 lines never run on
  Linux, 6 on Windows, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  StoreAlertReportEdgesTest in
  runner/tests/test_senses.py: with the runner
  module unimportable the script-mode fallback
  stores the record as given; past the stored cap
  the file is rewritten keeping the newest alerts.
  Done when a coverage run shows the function
  clean.
- A (refill) — `runner/ops/install.py::`
  `_usb_accelerators` (6 lines never run on either
  platform, coverage run 40187685363; CI machines
  have no accelerator plugged in, so the scan never
  looped) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  UsbAcceleratorsTest in
  runner/tests/test_hostclass.py: an unlistable
  sysfs answers none; known vendor ids name their
  kind once each, in device order, and an unknown
  id is not an accelerator. Done when a coverage
  run shows the function clean.
- A (refill) — `runner/extensions/tripwire/`
  `tripwire.py::read_live` (6 lines never run on
  either platform, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReaderRaceTest in runner/tests/test_tripwire.py:
  a root that raises when probed reads as empty; a
  file that vanishes before its lstat and a file
  that cannot be hashed are each skipped while the
  rest of the tree is read. Done when a coverage
  run shows the function clean but the smaller
  tail.
- A (refill) — `runner/extensions/release-drop/`
  `release_drop.py::main` (6 lines never run on
  either platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MainDeliveryTest in
  runner/tests/test_release_drop.py: a full local
  delivery writes the state and files one envelope;
  delivery not set up is exit 2; a short delivery is
  exit 2 with the state unwritten; an unwritable
  state file is exit 2 with the reason printed.
  Done when a coverage run shows the function
  clean.
- A (refill) — `runner/ops/extsources.py::`
  `_fetch_archive` (6 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FetchArchiveFailuresTest in
  runner/tests/test_extension_sources.py: a spent
  budget refuses before any download (status
  skipped); a download failure passes through as
  itself; an archive that unpacks past the
  extraction cap passes through, unless what is
  left of the budget cut it short, in which case
  the failure is the budget's (status skipped).
  Done when a coverage run shows the function
  clean.
- A (refill) — `runner/ops/extsources.py::Fetcher._open`
  (6 lines never run on either platform, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FetcherOpenEdgesTest in
  runner/tests/test_extension_sources.py: a
  SourceError from the opener passes through
  unchanged; an HTTP error is closed even when
  closing fails, and 403/429 are named as rate
  limiting; a transport OSError becomes "cannot
  fetch". Done when a coverage run shows the
  function clean.
- rules refreshed 2026-10-25 04:24 PDT
- A (refill) — `runner/ops/extsources.py::provision`
  and `_run_pass` (6 lines each never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ProvisionFailureTest in
  runner/tests/test_extension_sources.py: bad
  arguments answer the bare report; an uncreatable
  state root and an unexpected pass failure are
  recorded problems, never raises; an installed-code
  failure is logged and the pass goes on; small-parts
  and archive disk failures fail (or partially fail,
  with files landed) the entry with a "local disk"
  detail; a transient archive is partial and backed
  off. Done when a coverage run shows both clean.
- A (refill) — `runner/ops/extsources.py::is_withheld`
  (6 lines never run on either platform, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  IsWithheldEdgesTest in
  runner/tests/test_extension_sources.py: empty
  inputs are not withheld; an unresolvable path is
  withheld (fail closed); non-string withheld
  entries are skipped; an unresolvable withheld
  entry is compared as given. The function is fully
  run under that class. Done when a coverage run
  shows it clean.
- A (refill) — `runner/runner.py::log_startup` (6
  lines never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LogStartupBlockTest in
  runner/tests/test_personal_docs.py: a tripped
  personal-documents check prints the fixed banner;
  a failing check is swallowed and the start
  proceeds; an inference config prints ask=on;
  additional secrets print as key names only (the
  value asserted absent) with the unrestricted-key
  warning. Done when a coverage run shows the
  function clean.
- A (refill) — `runner/runner.py::handle_v2_mail`
  (6 lines never run on either platform, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  Version2IngestRejectionsTest in
  runner/tests/test_cli_options.py: with the v2
  module unavailable the message is not taken; a
  sealed body that disagrees with its subject is
  rejected and taken; a question the answer builder
  refuses is rejected the same way. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/runner.py::run_fetch_sources`
  (6 lines never run on either platform, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FetchSourcesRefusalsTest in
  runner/tests/test_extension_sources.py: the
  sources module unavailable is exit 1; an invalid
  policy is exit 2 with the problem printed; another
  pass already running is exit 1. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/cloud/send_dtls.py::`
  `_plain_result` and `_load_ticket` (6 lines each
  never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PlainResultAndTicketTest in
  runner/tests/test_send_dtls_main.py: a non-envelope
  result is refused as such; an encrypted result is
  decrypted and its inner signature verified; one
  bound to another job does not decrypt; a saved
  session ticket loads back byte for byte and
  unreadable ones load as none. Done when a coverage
  run shows both clean.
- A (refill) — `runner/ops/posture.py::`
  `_looks_like_placeholder` (7 fallback lines never
  run on Windows, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PlaceholderFallbackTest in
  runner/tests/test_posture_gaps.py: the shared
  check answers through the lazy import; with the
  import unavailable the answer is False, and a
  raising shared check is likewise False. With it,
  queue A's runner.py module-level residue (the
  three missing-sibling ImportError raises and the
  frozen-exe extension re-entry lines, 7 on both
  platforms) is unreachable by construction while
  the package is intact and the build is not frozen;
  recorded here, not chased.
- A (refill) — `runner/extensions/log-sentinel/`
  `log_sentinel.py::read_new_lines` (7 lines never
  run on Windows, coverage run 40187685363; the code
  is platform-neutral, the Windows fixtures were
  not) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReaderGuardsTest in
  runner/tests/test_log_sentinel.py: paths that are
  not a list read as none; non-path entries are
  skipped; a missing file and a file that stats but
  will not open each keep their recorded offset.
  Done when a coverage run shows the function clean
  on both platforms.
- A (refill) — `runner/runner.py::kill_tree` (7 lines
  never run on Windows, 2 on Linux, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the Windows
  residue is the POSIX branch and the POSIX-only
  extra-pids block (platform-inapplicable there,
  covered on Linux); the Linux residue was the
  extra-pids swallow, now pinned in
  runner/tests/test_linux_process.py: an extra pid
  that is already gone is swallowed, and the job's
  own pid and empty entries are never signalled
  through the tail. Done when a coverage run shows
  only the platform pair left.
- A (refill) — `runner/extensions/aide-feed/`
  `aide_feed.py::read_report_file` (7 lines never run
  on Windows, 4 on Linux, coverage run 40187685363)
  — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReaderRaceTest in runner/tests/test_aide_feed.py:
  a non-dict reader state reads fresh; a report that
  stats but will not open (a directory) keeps its
  previous fingerprint; when two reports are new,
  only the one read advances -- the second keeps its
  previous fingerprint and stays new for the next
  pass. Done when a coverage run shows the function
  clean.
- A (refill) — `runner/extensions/job-fuzz/`
  `job_fuzz.py::read_live` (7 lines never run on
  either platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReadLiveCampaignLegsTest in
  runner/tests/test_job_fuzz.py, on the ReadLiveTest
  rig: an unusable records cap reads as the default;
  a reader state without a numeric campaign seed is
  seeded from the clock; an empty pool ends the
  pass; the variant budget breaks both loops; a
  mutator with nothing to mutate is skipped; a box
  that stops being idle mid-pass ends the campaign
  with the outcomes it has. Done when a coverage run
  shows the function clean.
- A (refill) — `runner/extensions/airwaves/`
  `airwaves.py::_run` (7 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunToolTest in runner/tests/test_airwaves.py, the
  interpreter standing in for the scan tools: a
  successful run returns its stdout; a nonzero exit,
  a timeout, and an OSError from the run are each
  None. Done when a coverage run shows the function
  clean. — done: coverage run 40189711740 (main at 8765f81) shows no never-executed lines on either platform.
- A (refill) — `runner/extensions/wazuh-feed/`
  `wazuh_feed.py::main` (7 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  WazuhMainDeliveryTest in
  runner/tests/test_wazuh_feed.py: local delivery
  success writes the state; not set up is exit 2; a
  short delivery is exit 2 with the state unwritten;
  a manifest with non-object tunables reads as the
  defaults. Done when a coverage run shows the
  function clean. — done: coverage run 40189711740 (main at 8765f81) shows no never-executed lines on either platform.
- A (refill) — `runner/extensions/softflowd-feed/`
  `softflowd_feed.py::main` (7 lines never run on
  either platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SoftflowdMainDeliveryTest in
  runner/tests/test_softflowd_feed.py: the live
  collection branch runs when no readings file is
  given; local delivery success writes the state;
  not set up is exit 2; a short delivery is exit 2
  with the state unwritten. Done when a coverage run
  shows the function clean. — done: coverage run 40189711740 (main at 8765f81) shows no never-executed lines on either platform.
- A (refill) — `runner/extensions/latency-post/`
  `latency_post.py::main` (7 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LatencyMainDeliveryTest in
  runner/tests/test_latency_post.py: the live branch
  runs when no readings file is given; local delivery
  success writes the state; not set up is exit 2; a
  short delivery is exit 2 with the state unwritten.
  Done when a coverage run shows the function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/ops/install.py::`
  `install_project_snapshot` (7 lines never run on
  either platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  two tests in InstallAndOracleTest
  (runner/tests/test_make_snapshot.py): stale
  staging/retired dirs from a crashed install are
  swept before the next one; a swap that fails after
  the current snapshot is retired restores it and
  reports False. The function is fully run under
  that class locally. Done when a coverage run
  shows it clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/transport_extensions/nats/`
  `__main__.py::NatsPipe.run` (7 lines never run on
  Linux, 5 on Windows, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NatsPipeRunDropsTest in
  runner/tests/test_transports.py: a non-UTF-8
  message and a malformed envelope from the broker
  are logged and dropped, nothing delivered; a dead
  connection is closed and the loop reconnects with
  backoff. Done when a coverage run shows the
  function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `_is_number` in aide-feed, usb-arrivals
  and wire-arrivals (the whole body, 7 lines each,
  never run on either platform, coverage run
  40187685363) — taken and done as filed 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the helper
  is defined and never called in all three files
  (their tunables are paths, kinds, interfaces and
  a boolean; the one numeric tunable,
  poll_interval_sec, is the supervisor's, not the
  sense's). No behavioral gap; the dead copies are
  filed as Q23 for Claude's lane rather than tested
  against nothing.
- A (refill) — `runner/ops/extsources.py::_parse_entry`
  (7 lines never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DeclarationRefusalsTest in
  runner/tests/test_extension_sources.py, through
  parse_declaration: an entry that is not an object,
  an upstream value not exactly true, a non-bool
  archive on github and url entries, github files
  not a list or listed twice, project paths not a
  list or listed twice -- each refused with a
  ValueError naming the field. Done when a coverage
  run shows the function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/transport_extensions/dtls/`
  `__main__.py::DtlsPipe._on_job` (7 lines never run
  on either platform, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsOnJobDropsTest in runner/tests/test_dtls.py:
  a message that is not UTF-8, not an envelope, or
  an envelope with no job id in its subject is
  dropped and delivers nothing; a real envelope is
  delivered and its session recorded (control). Done
  when a coverage run shows the function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/runner.py::_local_signal_server`
  (8 lines never run on Windows, 2 on Linux, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the one
  existing drive of the refusal block skips on
  Windows (a real occupied port does not fail the
  second bind the same way there), so
  LocalSignalServerRefusalTest in
  runner/tests/test_runner_last_edges.py drives it
  with a bind-failing socket fake, identically on
  every platform: the refusal returns None, the
  half-made socket is closed, and a failing close is
  swallowed. Done when a coverage run shows the
  function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/oracle/resources.py::`
  `_save_state` (8 lines never run on Windows, 7 on
  Linux, coverage run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SaveStateFallbacksTest in
  runner/tests/test_resources.py: a non-dict state
  saves as an empty object; a chmod failure still
  leaves the state written; a write failing after
  the temp file opens closes the descriptor, removes
  the temp, and saves nothing; a failing close in
  cleanup is swallowed. The residue's flag lines
  are the platform pair (O_NOFOLLOW inapplicable on
  Windows, O_BINARY on Linux). Done when a coverage
  run shows only those left. — done: coverage run 40189608702 (main at eef3af8) leaves only each platform's foreign flag line (187 on Linux, 185 on Windows).
- A (refill) — `runner/guard/security.py::_bump_counts`
  (8 lines never run on Windows, 5 on Linux, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  BumpCountsFallbacksTest in
  runner/tests/test_security_config.py: a non-string
  base_dir bumps nothing; a write failing after the
  temp file opens still closes the descriptor (no fd
  leak per audit entry) and counts nothing; a failing
  close is swallowed too. The residue's two flag lines
  are the platform pair (O_NOFOLLOW inapplicable on
  Windows, O_BINARY on Linux), each covered where it
  applies. Done when a coverage run shows only those
  left. — done: coverage run 40189608702 (main at eef3af8) leaves only each platform's foreign flag line (339 on Linux, 337 on Windows).
- A (refill) — `runner/extensions/training-watch/`
  `training_watch.py::_scan_checkpoints` (8 lines
  never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ScanCheckpointsRacesTest in
  runner/tests/test_training_watch.py: the scan's
  three OSError guards (an unlistable run dir scans
  as empty; an unlistable subdir and an entry that
  raises on probe are skipped; a file whose stat
  fails after its isfile check is skipped), each
  driven by the real tree plus one wrapped os call
  raising for exactly one path. Done when a coverage
  run shows the function clean. — coverage run 40189608702 (main at eef3af8) shows the function clean on Linux; on Windows the stat-guard test failed and the map leaves exactly the guard pair unrun, because its drive counted os.stat calls and the platform's isfile does not stat the way the count assumed. The test is re-driven in the commit carrying this note (the probe stubbed for the target, the scan's own stat raising), and the Windows close awaits its verifying run.
- A (refill) — `runner/extensions/sysmon-feed/`
  `sysmon_feed.py::main` (8 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SysmonMainDeliveryTest in
  runner/tests/test_sysmon_feed.py: local delivery
  success writes the state and files one envelope;
  delivery not set up is exit 2; a short delivery is
  exit 2 with the state unwritten, so the next pass
  re-reads; a manifest without tunables runs the live
  defaults. Done when a coverage run shows the
  function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/runner.py::`
  `_extension_sources_pass` (the whole body, 8 lines,
  never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the tick
  tests substitute a fake pass and the wiring tests
  call provision directly, so the real wrapper never
  ran. ExtensionSourcesPassTest in
  runner/tests/test_extension_sources.py: a real pass
  provisions and returns the report; a failing pass
  returns None and never raises; no sources module is
  None. Done when a coverage run shows it clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/transport_extensions/nats/`
  `__main__.py::NatsClient.connect` (9 lines never run
  on either platform, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NatsConnectFailuresTest in
  runner/tests/test_transports.py drives a scripted
  loopback broker: a refused connection, silence
  before INFO, a non-INFO greeting, silence after
  INFO, a server -ERR, and a wrong PONG are each a
  TransportError naming the stage. Done when a
  coverage run shows the function clean but the
  success return the happy path already covers.
  With it, `runner/ops/install.py::`
  `_install_osquery_linux` (11 lines, Windows only in
  the same run) is platform-inapplicable on Windows
  (a Linux-only installer path), covered on Linux;
  closed under the queue-A skip rule. — done: coverage run 40189608702 (main at eef3af8) shows the function clean on Linux; the Windows map leaves the refused-connection except/raise pair (184-185) unrun while the test that can only pass through that raise (test_a_refused_connection_is_named, asserting "cannot connect to") passes on Windows in the same run — a line-attribution residue, recorded as such.
- A (refill) — `runner/transport_extensions/dtls/`
  `__main__.py::main` (9 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsMainRefusalsTest in runner/tests/test_dtls.py:
  no channel directory, an unusable port, and a bind
  that cannot be listened on each refuse with exit 2
  and a named reason (the real port validation and a
  real bind failure drive two of them); a failed pass
  is logged and the loop goes on. Done when a coverage
  run shows the function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/extensions/job-fuzz/job_fuzz.py::`
  `_mut_quote_break` (9 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  QuoteBreakMutatorTest in runner/tests/test_job_fuzz.py
  drives the mutator through the MUTATORS table: one
  quote flips and nothing else moves; a quoteless
  script gains the unterminated echo line. The function
  is fully run under that class locally. Done when a
  coverage run shows it clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/runner.py::execute_job` (9 lines
  never run on Windows, 8 on Linux, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ExecuteJobFallbacksTest in
  runner/tests/test_remediation_e2e.py: a monitor that
  fails to start, a monitor whose stop fails, and a
  remediation close-out that raises each leave the
  job's result untouched; a close-out member is
  attached (that line had never run on Windows). The
  set's last line, the script-write branch's own
  "script must be a string" raise, is unreachable by
  construction -- the input validation above it
  rejects a non-string script first -- and the
  contract is pinned at that live guard. Done when a
  coverage run shows only that line left. — done: coverage run 40189608702 (main at eef3af8) shows only line 3510 left on either platform, the unreachable line recorded above.
- A (refill) — `_deliver_local` in the nine senses the
  Q14 roster never included (airwaves, crash-watch,
  falco-feed, service-watch at 9 lines; osquery-feed
  at 8; pi-health, tripwire, usb-arrivals,
  wire-arrivals at 5; coverage run 40186441596) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — all nine are
  live senses using the roster harness's exact args;
  they were simply never on the list. The roster in
  runner/tests/test_sense_delivery.py now names all
  twenty-eight senses, and under that module alone
  every copy's _deliver_local is fully run locally.
  Done when a coverage run shows the nine clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines for the nine on either platform.
- D — the mutation workflow's surviving mutants as
  missing assertions — taken and done 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the seeded
  workflow has never run in CI; a local run of the
  shipped configuration over runner/guard/security.py
  generated three mutants (write_audit_entry's key_id,
  job_id and detail defaults), all survived, all now
  killed by AuditEntryDefaultsTest in
  runner/tests/test_security_md_claims.py, verified
  against each hand-applied mutant. The run's stats
  mapped tests to that one function only, so the
  signal's narrowness is filed as Q22, not mistaken
  for a clean bill.
- D — PROTOCOL.md's examples and AGENTS.md's "Do not
  emit" table, run as written — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  runner/tests/test_protocol_examples.py: every json
  block in PROTOCOL.md parses, the section 3.1 job
  sketch runs end to end, the 3.2 result sketch
  verifies, and the table's rows pass as written --
  except one divergence, filed as Q21 with the
  failing-by-design MissingBinaryRowProbe: the
  missing-binary row says "Rejected" unqualified, but
  at the default repair latitude the runner repairs
  the interpreter and runs the job (PROTOCOL.md
  section 3.2); the rejection holds at advise latitude
  and is pinned there. Item done when Q21 is decided.
  — done: Q21 decided in 68c69bb (the row and the
  Windows note amended to state the repair; the probe
  replaced by MissingBinaryRowAsAmended in the same
  commit); runner.tests.test_protocol_examples runs
  15 of 15 green.
- D — SECURITY.md and docs/security/threat-model.md,
  one test per claim plus its negative control — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: every behavioral claim in both documents is
  mapped to the test that proves it in
  runner/tests/test_security_md_claims.py; the one gap
  found is pinned there: the security block does not
  hot-reload (a mode change in the file leaves the
  running cfg at its startup mode while a hot key in
  the same write does reload; the same file read at
  startup enables the mode). The rest of both documents
  is policy and process a test cannot falsify.
- B — the four environment axes of queue B (Q20,
  applied in 68c69bb: env-axes.yml gains the sysctl
  job -- ptrace_scope 0-3, protected_symlinks and
  protected_regular off/on, hidepid 0/2, each crossed
  with job_user off/on) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — first run
  40187426146 queued at 68c69bb. Done per axis when
  both values are green, or the difference is filed.
  — done: run 40187426146 completed with all 18 jobs
  green (2 userns legs; 16 sysctl legs: ptrace_scope
  0-3, protected links off/on, hidepid 0/2, each with
  job_user off and on), verified from the run's job
  list; no axis moved the corpus, so no difference to
  file (recorded in Q20, 66e4d0b). The one loose end
  Q20 left in this lane is also closed with this
  commit: the canary module now records the four axes
  in its own AXIS lines beside the userns line, so any
  run of it carries every axis value with its results.
- D — documented-default hunt re-run against every key
  added since the defaults registry was last complete
  (8748b44, Release 3.12.62): no new config keys in
  production code or docs since that commit (the eight
  production commits and the two doc files surveyed);
  the registry guards (6 tests) and the defaults table
  hunt (26 tests) green — taken and done 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/oracle/remediation.py::fix_marker_digest`
  (10 lines never run on Windows, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — with it, the
  same file's `sample_tree_posix` (10, Windows) and the
  Linux branch of `total_memory_bytes` (5, Windows) are
  platform-inapplicable on Windows (POSIX readers behind
  their platform guards), covered on Linux; the Windows
  memory branch's failure leg is taken with the item. —
  coverage run 40186330078 (main at 5c724d9) shows no
  never-executed lines on Linux; the Windows residues
  are the second safe-id gate's return (unreachable by
  construction: load_marker only loads under an
  already-safe id) and the platform-inapplicable POSIX
  lines recorded above. The write-failure except pair
  was still unrun on Windows in that run (the only
  other selective-write leg lives inside an AV test
  that skips on Windows), so one more leg is added
  with this ledger commit and awaits its verifying run.
  — done: coverage run 40187504729 (main at fc72408)
  shows fix_marker_digest clean on Linux and only the
  unreachable second safe-id gate unrun on Windows;
  both suites OK in that run.
- A — `runner/extensions/training-watch/`
  `training_watch.py::main` (10 lines never run on
  Linux, coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage
  run 40186249031 (main at 867e5cf) shows no
  never-executed lines for this function on either
  platform. (That run's Windows suite also carried one
  unrelated failure, test_extension_sources'
  archive-retry expecting "fetched" and getting
  "mismatch", seen once; watched for a repeat in the
  next run before anything is filed. The watched
  failure did not repeat in run 40186330078; watch
  closed, treated as a one-off.)
- A — `runner/extensions/job-watcher/job_watcher.py::`
  `main` (10 lines never run on either platform,
  coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage
  run 40186249031 shows no never-executed lines for
  this function on either platform.
- A — `runner/extensions/job-fuzz/job_fuzz.py::`
  `_record_seed` (10 lines never run on either platform,
  coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage
  run 40186249031 shows no never-executed lines for
  this function on either platform.
- A — `runner/runner.py::main` (11 lines never run on
  Windows, coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — coverage run
  40186249031 leaves one Windows line, the --local-test
  dispatch return; that leg is added with this ledger
  commit and awaits its verifying run. — done: coverage
  run 40187267889 (main at cbd794d) shows no
  never-executed lines for this function on either
  platform. (Both suites in that run carry exactly one
  failure, the Q21 probe failing by design at that
  commit; it was replaced in 68c69bb.)
- A — `runner/extensions/resource-sentinel/`
  `resource_sentinel.py::_read_cpu_counters` (12 lines
  never run on Windows, coverage run 40183585961) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40186249031 shows no
  never-executed lines for this function on either
  platform.
- A — `runner/runner.py::_pid_alive` (11 lines never run
  on Windows, 10 on Linux, coverage run 40183585961) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  each platform's branch is inapplicable on the other
  (the ctypes branch on Linux, the kill tail on
  Windows), covered where it applies; the one line
  missing on both, the Windows branch's failure
  fallback, is taken with it. — done: coverage run
  40186249031 (main at 867e5cf) shows no never-executed
  lines on Linux; the Windows residue is the POSIX
  kill tail, platform-inapplicable there.
- A — `runner/runner.py::_append_security_event` (11
  lines never run on Windows, 3 on Linux, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the flag lines
  are platform pairs (O_NOFOLLOW inapplicable on
  Windows, O_BINARY on Linux, each covered on the other
  platform); the rest is taken with it. — done: coverage
  run 40185658710 (main at 0b295ba) leaves only each
  platform's foreign flag lines (O_NOFOLLOW on Windows,
  O_BINARY on Linux).
- A — `runner/extensions/lab-results/lab_results.py::`
  `_deliver_local` (11 lines never run on either
  platform, coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the template
  sense itself was missing from the delivery roster its
  copies are tested by. — done: coverage run 40185658710
  (main at 0b295ba) shows no never-executed lines for
  this function on either platform.
- A — `runner/extensions/job-fuzz/job_fuzz.py::`
  `_run_one_variant` (11 lines never run on either
  platform, coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage
  run 40185658710 (main at 0b295ba) shows no
  never-executed lines for this function on either
  platform.
- A — `runner/cloud/send_dtls.py::main` (11 lines never
  run on either platform, coverage run 40183585961) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- A — `runner/runner.py::_v2_ingest` (11 lines never run
  on either platform, coverage run 40183585961) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- A — `runner/wire/oauth.py::store_refresh_token` (12
  lines never run on Windows, 9 on Linux, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the O_NOFOLLOW
  flag line is platform-inapplicable on Windows and the
  O_BINARY line on Linux (each behind its hasattr guard),
  covered on the other platform. — done: coverage run 40185441322 shows no never-executed lines on Windows; the Linux residue is the O_BINARY line recorded above.
- A — `runner/extensions/job-fuzz/job_fuzz.py::decide` (12
  lines never run on either platform, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
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
  Linux residual, the root row, is taken with it. — done: coverage run 40185441322 shows no never-executed lines on Linux.
- A — `runner/runner.py::handle_mail` (13 lines never run on
  either platform, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- A — `runner/oracle/dri.py::_save_state` (14 lines never run
  on Windows, 9 on Linux, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 leaves only each platform's foreign flag line (O_NOFOLLOW on Windows, O_BINARY on Linux).
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
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run
  40183995594 shows no never-executed lines for this
  function on either platform.
- A — `runner/runner.py::_with_seen_file` (14 lines never run
  on Linux, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run
  40183995594 shows no never-executed lines on Linux; the
  Windows residue is the fcntl lock/unlock pair,
  platform-inapplicable on Windows (the msvcrt legs run
  there), covered on Linux.
- A — `runner/guard/sandbox.py::startup_problem` (15 lines
  never run on Windows, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  platform-inapplicable on Windows (the bwrap trial sits
  behind the function's own platform guard), covered on
  Linux; the Linux residuals (start failure, the userns
  note) are taken with it — done: coverage run
  40183995594 leaves on Linux only the platform guard's
  own return line.
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
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40186441596 (main at 63e0c80) shows
  no never-executed lines for these five functions on
  either platform, and the nineteen-sense roster is clean
  in the same run; that run's Windows suite is OK, which
  also confirms the four fd-leak error fixes in the same
  commit. Nine non-roster `_deliver_local` copies remain
  (airwaves, crash-watch, falco-feed, osquery-feed,
  pi-health, service-watch, tripwire, usb-arrivals,
  wire-arrivals; 5 to 9 lines each) as residual field.
- A — `runner/guard/security.py::validate_security_config` (18
  lines never run on Windows, 7 on Linux, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 shows no never-executed lines on Linux; the Windows residue is the POSIX pwd block behind its os.name gate, platform-inapplicable there.
- A — `runner/extensions/latency-post/latency_post.py::_probe`
  (19 lines never run on either platform, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- A — `runner/extensions/aide-feed/aide_feed.py::main` (20 lines
  never run on Windows, 7 on Linux, coverage run 40180268696) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `runner/ops/install.py::install_files` (20 lines never run
  on Windows, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 shows no never-executed lines on Linux; the Windows residue is the POSIX binary chmod behind its os.name guard, platform-inapplicable there.
- A — `runner/extensions/job-fuzz/job_fuzz.py::main` (23 lines
  never run on either platform, coverage run 40180268696) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `runner/extensions/service-watch/service_watch.py::read_live`
  (30 lines never run on either platform, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
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
- Finding — full-suite run at 93998ca+ (6,395 tests): the
  Hypothesis property test_preamble_and_trailer_ignored errored on
  a shrunk counterexample (payload {'{': None, '"': []}, preamble
  '"'): a lopsided preamble quote inverts _object_start's string
  tracking and a valid signed job is rejected. Filed as Q32 with
  PreambleBraceInStringTest (4 expectedFailure, 5 pins) —
  58316a92-3c4a-41cb-8a16-8c0c5a871e90, 2026-10-25. The same run's
  one failure was the unregistered kill_tree skip reason from the
  c7a7d18 take; registered in d6f822d.
- A (refill) — `runner/transport_extensions/nats/__main__.py::main`
  (12 lines never run on the local full-suite map at 93998ca) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NatsMainLegsTest in runner/tests/test_transport_shells.py: no
  channel directory answers 2, a pipe whose constructor raises
  TransportError answers 2, and the happy path runs the pipe and
  answers 0. Locally coverage-clean on main's lines. Done when a
  coverage run shows main clean and the build's Windows shards
  are green for it.
- A (refill) — `runner/transport_extensions/dtls/__main__.py::main`
  refusal legs (4 lines never run on the local full-suite map at
  93998ca: the no-shared-secret return, the greeting-tier warning,
  the PSK-floor entry) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — DtlsMainRefusalLegsTest
  in runner/tests/test_transport_shells.py: no secret answers 2,
  a weak PSK answers 2, a pipe that cannot listen answers 2, and
  a bogus greeting tier warns and proceeds at family. Locally
  coverage-clean on the four lines. Done when a coverage run
  shows them clean and the build's Windows shards are green.
  (Same batch: Q32 verified closed — Claude's fix 2b561bc makes
  all four probe shapes verify and the property is green.)
- Stamp — release 3.12.67 (tag at 382eb3a, published
  2026-10-25T14:17Z) FULL stamp by Muse,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90: GitHub release carries
  all eight platform archives plus pi-light, the project
  tarball, wheel and sdist, SHA384SUMS, SBOM and
  BUILD-PROVENANCE; the wheel's and sdist's SHA-384 match the
  sums file; PyPI's 3.12.67 is the latest there and its wheel
  and sdist are byte-identical to the GitHub assets (SHA-256);
  GHCR ghcr.io/pigeon-home/homing-pigeon carries the v3.12.67
  tag and latest at 382eb3a. Tag build's test, typecheck and
  platform builds green; its mutation job still running (the
  D4 triage input).
- A (refill) — `runner/extensions/suricata-feed/suricata_feed.py`
  `::main` tunables guard and local-delivery refusals (lines
  509, 555, 559-562 on the local full-suite map at 93998ca) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MainDeliveryLegsTest in runner/tests/test_suricata_feed.py:
  non-dict tunables read as none, an undeliverable pass is
  rc 2, and a partial delivery is rc 2 naming the shortfall,
  both with the state left unwritten. Locally coverage-clean.
  Done when a coverage run shows them clean and the build's
  Windows shards are green.
- D4 — the .67 tag run's mutation job (40200926906) completed
  FAILED with no tally and no survivors: its stats pass died
  at a script-mode test whose child interpreter re-enters
  mutmut's config resolution inside the copied tree. Filed as
  Q33 for Claude's lane; the triage waits on a completed
  mutation run. — 58316a92-3c4a-41cb-8a16-8c0c5a871e90,
  2026-10-25.
- rules refreshed 2026-10-25 ~08:00 PDT (standing orders,
  AGENTS.md rules 7-9, open questions: Q33 new, Q32 answered,
  Q30 closed in practice; playbook hard rules unchanged).
  resources 2026-10-25T14:26:35Z: cores 2 | box cpu 50% |
  wall 0s | peak rss 12 MB | mem used 97% | disk free
  166.4 GB | under-driven (between scoped takes; the local
  full-suite coverage run finished this hour).
  resources-top: hatch 198 MB, python 12 MB.
- A (refill) — chmod-failure swallows in
  `runner/oracle/senses.py::_write_private` (lines 336-337)
  and `runner/oracle/learning.py::_append` (lines 259-260),
  local full-suite map at 93998ca — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  WritePrivateChmodSwallowTest (test_senses.py) and
  AppendChmodSwallowTest (test_oracle_learning.py): with
  os.chmod refusing, the write and the ledger append still
  land and nothing raises. The O_BINARY flag lines beside
  them (328 / 251) are platform mirrors, covered on the
  Windows map. Locally coverage-clean on the swallows. Done
  when a coverage run shows them clean and the build's
  Windows shards are green.
- A (refill) — `runner/ops/extsources.py` reader legs:
  `_read_json` over-cap and unreadable returns (215,
  217-218), `_scan_local` vanished-file pass-over and cap
  break (1204-1205, 1207), `_installed_record` unhashable
  file left out and in-place stale copy removed (1260-1261,
  1268) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReadJsonRefusalLegsTest, ScanLocalLegsTest and
  InstalledRecordLegsTest in
  runner/tests/test_extension_sources.py. All three
  functions are clean under the module's tests locally.
  Done when a coverage run shows them clean and the
  build's Windows shards are green.
- A (refill) — serial and mutator legs:
  `usb_arrivals.py::_read_serial_devices` empty/repeated
  name pass-over and unresolvable target (146, 151-152),
  and `job_fuzz.py::_mut_oversized_line` applied through
  build_variant (365-367; registered in MUTATORS but never
  applied by a test) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SerialDevicesLegTest (test_usb_arrivals.py) and
  OversizedLineMutatorTest (test_job_fuzz.py). Done when a
  coverage run shows them clean and the build's Windows
  shards are green.
- A (refill) — sender legs: `runner/cloud/send_dtls.py`
  `::_build_body` script-file and timeout members (93-94,
  98) and `runner/cloud/send_job.py::main`'s ValueError
  answer (527-529) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  BuildBodyScriptFileTest (test_send_dtls_main.py) and
  MainValueErrorLegTest (test_send_job_verify.py).
  Recorded without takes on the same map:
  dtlsproto.x25519's final swap (186-187, unreachable by
  construction, already recorded) and
  resources._save_state's O_BINARY flag line (187), a
  platform mirror covered on the Windows map. Done when
  a coverage run shows the taken legs clean and the
  build's Windows shards are green.
- A (refill) — `runner/extensions/cert-sentinel/cert_sentinel.py`
  legs: `_read_tls_target`'s answering endpoint (157-158,
  161) and `main`'s partial local delivery (471, 474-477),
  local full-suite map at 93998ca — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReadTlsTargetSuccessLegTest and MainPartialDeliveryLegTest
  in runner/tests/test_cert_sentinel.py (the earlier
  read_live leg mocked the probe itself, so its success
  lines never ran). Locally coverage-clean on the taken
  lines. Done when a coverage run shows them clean and
  the build's Windows shards are green.
