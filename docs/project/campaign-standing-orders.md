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

- rules refreshed 2026-10-25 04:24 PDT
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
  clean.
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
  function clean.
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
  shows the function clean.
- A (refill) — `runner/extensions/latency-post/`
  `latency_post.py::main` (7 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LatencyMainDeliveryTest in
  runner/tests/test_latency_post.py: the live branch
  runs when no readings file is given; local delivery
  success writes the state; not set up is exit 2; a
  short delivery is exit 2 with the state unwritten.
  Done when a coverage run shows the function clean.
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
  shows it clean.
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
  function clean.
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
  run shows the function clean.
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
  when a coverage run shows the function clean.
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
  function clean.
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
  run shows only those left.
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
  left.
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
  run shows the function clean.
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
  function clean.
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
  None. Done when a coverage run shows it clean.
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
  closed under the queue-A skip rule.
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
  run shows the function clean.
- A (refill) — `runner/extensions/job-fuzz/job_fuzz.py::`
  `_mut_quote_break` (9 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  QuoteBreakMutatorTest in runner/tests/test_job_fuzz.py
  drives the mutator through the MUTATORS table: one
  quote flips and nothing else moves; a quoteless
  script gains the unterminated echo line. The function
  is fully run under that class locally. Done when a
  coverage run shows it clean.
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
  coverage run shows only that line left.
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
  Done when a coverage run shows the nine clean.
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
