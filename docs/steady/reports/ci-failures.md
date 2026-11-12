# CI failures: six days of runs, read as a corpus

<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->

This report belongs to package 3.12.56. It answers one question the
owner asked on 2026-10-22: the pipeline has been red or stuck for
days -- is it timing out, and what is taking the longest? The
method is the one the owner named: treat the pipeline as the
system under test, enumerate how it fails from the record rather
than from a hunch, then cut it down to what earns its place.

The corpus is every workflow run GitHub still lists for the window
2026-10-16 00:07Z to 2026-10-23 00:21Z, with every job and step of
each: 1,000 `build` runs (the listing's cap; 1,002 existed), 98
`platform-matrix`, 109 `minimal-userland`, 176 `docker`, 22
`security`. Numbers below are from that record. Job logs could not
be read from where this was written (the log store is a host the
session's proxy refuses), so failing-test names come from check
annotations, which turned out to be part of the problem (finding
5).

## The findings, shortest first

1. **No timer fired.** The pipeline had exactly one explicit job
   timer, `timeout-minutes: 40` on the release-only mutation job,
   and no job came within ten minutes of it: mutation ran 6.4
   minutes at the median, 22.6 at p90, 29.7 at the maximum (310
   runs). Nothing else carries a timer; the helper scripts under
   `tools/` and the suite's own steps have none. Zero jobs ended
   with the conclusion `timed_out`. Whatever has been red was not
   cut short by a clock.

2. **The red is the test suite, and it is red on Windows twice as
   often as on Linux, almost never on both.** Of 800 pushes to
   main, 368 failed. The jobs that failed: `build-windows` 259
   times, `test` (the Linux suite) 137 times, everything else 47
   times combined. On main, 241 runs were red on Windows alone, 125
   on Linux alone, and **2** on both. The Windows failures are
   therefore not the same breakage seen twice; they are a separate
   population -- platform-specific, or flaky only there -- and
   until this release nothing on the run page named them (finding
   5). Red came in streaks: 27 one-run reds fixed by the next push,
   but also streaks of 24, 15, 12 and 10 consecutive red pushes.
   By day, main's red fraction was 27%, 66%, 38%, 60%, 70%, 19%,
   36% (Oct 16 to Oct 22).

3. **The 13-hour stalls were a retired runner label, and they are
   already fixed.** Every `build` and `platform-matrix` run that
   sat for hours (p50 11.7 h, max 16 h) had one job that never got
   a runner: `build-macos-x86_64` and `native-macos-x86_64`, both
   asking for `macos-13`, which GitHub retired. 46 such jobs in
   `build`, 59 in `platform-matrix`; 45 and 59 runs were
   mass-cancelled by hand at 18:19-18:21Z on 2026-10-22, and the
   label moved to `macos-15-intel` the same hour. Since the move
   the job runs in 1-3 minutes (57 of 57). The stall was the
   pipeline's only "it never finishes", and it was a queue, not a
   timeout.

4. **The long pole of a release is mutation, and it does not gate
   the release.** Tag runs took 22-46 minutes; every other job in
   them finished in 1-6 minutes. The 20 tags cut between 21:53Z and
   22:08Z on 2026-10-22 each ran a 17-24 minute mutation job, and
   the runner concurrency they shared stretched the runs to 46
   minutes. The release job itself averages 0.5 minutes. In runner
   minutes over the window, by GitHub's billing weights (Windows
   x2, macOS x10): `build-windows` 36%, `build-macos` 23%, mutation
   16%, `test` 12%, everything else 13%. Most of the macOS share is
   845 one-minute arm64 builds on branch pushes that no one
   downloads.

5. **The annotations meant to name the failing test were spent on
   noise.** `tools/skip_guard.py --annotate` annotated the first
   ten lines in the log that looked like a failure, in log order.
   A `-v` log of a 4,500-test suite carries exception text that is
   not a failure (a fixture dumping a deliberately red shard, a
   test printing the traceback it expects), and those lines come
   before the real `FAIL:` lines near the end. Result: 126 of 137
   red Linux suite runs named no test in their annotations, and
   green runs showed red annotations ("AssertionError: False is not
   true", "BrokenPipeError") from fixture output. The Windows
   shard runner annotated nothing at all; 257 red Windows jobs read
   "Process completed with exit code 1" and nothing more.

6. **Smaller shapes, for completeness.** Eleven runs on 2026-10-16
   and 2026-10-19 failed the smoke step on Linux, macOS and Pi
   Light together (one startup regression each, fixed by the next
   push). Three `typecheck` failures, one `sourceforge`, one
   `build-python`. Queue waits are not a factor anywhere but the
   arm64 runners (p90 5 minutes) and `repair-on-busybox` (p90 6
   minutes). `minimal-userland`, `docker` and `security` are green
   and fast (p50 0.3, 0.7 and 0.2 minutes).

## What this release does about it

Measurement first, by the owner's instruction: no timer anywhere in
the pipeline while the slow and the red are measured, so a run shows
how long it really takes instead of where a guard cut it.

- The mutation job's `timeout-minutes: 40` is removed. It was the
  only one. `tests/test_build_config.py` now pins the experiment:
  the mutation block carries no timer, and no workflow file does.
  The platform ceiling of 360 minutes per job still applies.
- The Linux suite runs with `--durations 25`; the Windows shards
  with `--durations 15`. unittest prints its slowest tests after
  the run, so the suite's long pole is in the log without a
  profiler. Each Windows shard also reports its wall time.
- Under Actions, the Windows shard runner turns every `FAIL:` /
  `ERROR:` line of a failed shard into a `::error` annotation
  naming the test, so finding 2's invisible population gets names
  on the run page from this release on.
- `skip_guard.py --annotate` spends its ten annotations on `FAIL:`
  / `ERROR:` lines first and exception lines after, and annotates
  nothing when the verdict is OK.

Nothing was removed from the pipeline. Every job, step and proof
runs as before.

## Failure modes in the corpus and suite durations

The record above is the seed corpus. These are the mutations of
"a push to main" that have actually turned a run red or stuck, each
with what would catch it earlier:

| Mutation of a run | Seen | Catches it |
|---|---:|---|
| A test passes on Linux and fails on Windows (path, case, encoding, console) | 241 runs | Names on the run page (this release); then a Windows-only failure list to fix from |
| A test fails on Linux only | 125 runs | Already named by the suite; the fix is the next push |
| A runner label GitHub has retired | 105 jobs | A label allowlist test against GitHub's published runner images, or a short `timeout-minutes` on jobs whose runner is scarce (the one timer worth having back) |
| Twenty tags in fifteen minutes | 20 runs | Runner concurrency saturates; see the reduction below |
| A startup regression in the frozen binary | 11 runs | Smoke caught it; the proof is doing its job |
| A `::error` cap spent on fixture noise | 126 runs | Fixed in this release |
| A push that cancels the run before it | 27 runs | Expected: `cancel-in-progress` on branch pushes |

Not seen once in 1,000 runs: a job hitting a timer, a hung
runner, a flaky infrastructure step (checkout, setup-python, pip,
artifact upload). The things that are slow are deterministic and
the things that are red are the code.

For scale, the first `--durations` run of the suite (Linux, Python
3.13, 4,584 tests in 185 s): the slowest test is
`test_policy_constraints.ArgsPatternTimingTest.test_hostile_pattern_rejected_at_parse`
at 39.6 s -- a fifth of the whole run in one deliberate
catastrophic-backtracking probe -- then `test_oracle_ab` at 10.0 s
and two `test_job_fuzz` hanging-runner cases at 5 s each. Nothing
else takes more than 4.3 s. If the suite ever needs to be faster,
that one test is where a fifth of it lives.

## Reducing it to what earns its place

Proposals, not changes; each is one commit when the owner wants it.

1. **Move mutation off the tag path.** It is a signal that cannot
   block a publish, and it is the entire difference between a
   7-minute release and a 40-minute one. `mutation-seeded.yml`
   already exists for a scheduled run and has not run in the
   window. Running mutation nightly on main (or on `workflow_dispatch`)
   gives the same signal, once a day, off the critical path.
2. **Stop building macOS arm64 and Windows arm64 on branch
   pushes.** They are 1-minute builds whose archives are never
   downloaded from a branch run; the release builds them again.
   Gating them on tags saves 23% of billing-weighted minutes and
   changes nothing a release ships. The x86_64 Linux build and the
   Pi Light build are cheap and catch the frozen-binary regressions
   (finding 6); keep them on every push.
3. **Give scarce runners a short timer, deliberately.** Finding 3
   recurs the next time a label retires. A `timeout-minutes: 30` on
   the macOS x86_64 and Windows arm64 jobs would have failed those
   runs in half an hour instead of parking them for sixteen; it is
   the one timer this report argues for, after the measurement ends.
4. **Make the Windows population visible before deciding anything
   else about Windows.** With the names from this release, a week
   of runs will say whether the 241 are a few flaky tests or many
   real ones. Until then no Windows change is worth making.
5. **Leave `test`, `typecheck`, `build-linux`, `build-pi-light`,
   `build-python`, `minimal-userland`, `docker` and `security`
   alone.** They are fast, green when the code is green, and each
   is the only proof of something.

## How to end the experiment

Put `timeout-minutes: 40` back on the mutation job in
`.github/workflows/build.yml` and flip
`tests/test_build_config.py::test_mutation_cannot_hold_a_tag_run_for_hours`
back to asserting it; delete
`test_no_job_in_the_pipeline_carries_a_timer` or scope it to the
jobs that should stay timer-free. Everything else in this release
stays useful after the measurement.

## 2026-11-11 — Windows on the Germany rig: suppositions before the local loop

Four days of release failures (8-Nov to 11-Nov) share one loop:
a Windows failure is found by a GitHub run, a fix is written
against the run's annotations, and the next GitHub run — tens of
minutes later — is the first place the fix is exercised. The
conductor's direction (11-Nov, ~5:30 PM PST) moves the Windows
loop onto the Germany rig (Windows Server 2022, 8 logical
processors, 15.6 GB, Python 3.12.7, MinGit 2.47 — the CI job's
own Python) and reserves GitHub for confirmation. The rig loop
runs the build-windows job's exact test command:

    python runner/tools/run_tests_parallel.py \
      --duration-table runner/tools/windows_durations.json \
      --durations 15 --wall-clock 20 --in-flight 8

Suppositions, recorded before any rig measurement:

- **W1 (the wall is throughput, not shape).** The 1200-second
  shard wall on the 4-core `windows-latest` pool is primarily a
  throughput artifact: packed by the same duration table, every
  shard completes on the rig in under 720 seconds (the table's
  own 12-minute budget). Any shard that exceeds 720 seconds
  locally will trace to named files in the `--durations`
  output, not to the platform in general.
- **W2 (the audience refusal is silent, not absent).** The rig
  battery's wrong-audience-refused step fails with
  `noResult=True` on five consecutive heads while the sibling
  tampered-refused step passes: the wrong-audience job is
  refused (no result is produced) but neither
  `security-audit.jsonl` nor `runner.log` gains the word
  "audience" on Windows — the refusal is recorded through a
  different path or wording than the signature refusal the
  tampered step matches on. Reproducing the step against a rig
  runner instance and reading both files after the drop will
  show which record the refusal actually writes.
- **W3 (gates_strict reproduces locally).** The gates_strict
  dead-backend failure in the CI build-windows job reproduces
  on the rig with the same shape; it is platform behaviour, not
  a CI-runner artifact, so the rig loop can iterate on it.

### Conclusions from the measurement (2026-11-11, rig-local)

Two runs were made. Run 1 is not a measurement: it ran the CI
command with no `--in-flight` cap against the preproof Python,
whose `preproof-tree.pth` put another lane's stale tree on
`sys.path` for every subprocess, and its tally (5 shards OK, 23
failed, 7 of them wall-killed) is root-cause evidence only —
the stale pointer, not the suite. Run 2 is the measurement:
a private copy of that Python with the poisoned `.pth` removed
(its `python312._pth` then had to be pointed at the Run 2 tree
explicitly; the first Run 2 launch failed imports until it
was — the same pointer family, second instance), the
3.16.20.8 tree expanded from a zip (no `.git` in the tree),
and the CI command with `--in-flight 8` added. The rig was
not idle during Run 2: the preview battery and campaign work
ran on it in parallel, and the launch context gave the
shards a terminal on stdin. Absolute rig seconds therefore
do not transfer to CI; the shape and the named tests do.

Run 2 tally, first-hand from the rig's own suite log: 3,710.0
seconds wall for the whole run, exit 1; 12,535 tests from 455
modules in 28 shards packed at 720s (shard 0) and 707s (every
other shard). 9 shards passed (0, 1, 3, 4, 6, 12, 15, 17, 18).
19 failed: 4 wall-killed at 1,200 seconds (5, 13, 14, 20) and
15 out at exit 1 carrying 55 named failing tests. 11,109
tests are counted in the 24 shards that printed a `Ran` line;
the 4 killed shards printed none.

- **W1 — refuted.** The packed loads say every shard should
  take about 707 seconds; the shards' own unittest times say
  otherwise. Shard 1 ran 1,149.2s, shard 2 1,025.4s, shard 6
  1,177.2s, shard 11 1,073.7s, shard 26 1,100.2s, shard 27
  922.8s, shard 25 857.9s, shard 21 838.8s, shard 18 777.4s,
  and 4 more shards never finished inside 1,200s at all. The
  excess traces to named files, as the supposition's own
  escape clause demanded: `test_workspace_isolation`'s two
  property tests alone took 630.9s and 469.0s (the module is
  priced 684.5s in the table), and `test_oracle_alphabet`'s
  notes test took 636.4s with two more at 189.8s and 79.8s
  (module priced 674.0s). The wall is shape at the top of the
  distribution, not platform throughput in general: 15 shards
  ran their whole shard in 700 seconds or less.
- **W2 — refuted in its causal form.** On the measured tree
  the rig battery's wrong-audience-refused step passes —
  twice on 3.16.20.8 in the rig battery record, with the
  detail `noResult=True`, the same detail the failing entries
  on other heads carry. A direct read of the preview runner's
  state after a passing run finds no "audience" in either
  `security-audit.jsonl` or `runner.log`: no such record is
  written on passing runs either. The step's pass and fail do
  not track the presence of an audience record, so the
  silent-refusal mechanism is not what makes the step fail.
- **W3 — refuted.** The gates_strict dead-backend failure
  does not reproduce on the rig. All three Decision 1 gates
  families ran without a named failure: gates_strict (shard
  27 — its one named failure is the git-tree artifact below),
  gates_refuse (shard 16) and gates_phase2 (shard 24).
  `test_macos_confine`, in shard 24, is likewise green on
  the rig. This matches the Q159 fix and its CI clearance;
  the failure was head behaviour, not platform behaviour.

The 4 wall-kills name their tests in the wall clock's own
dump. Shards 5 and 13 died in the same stack: a `poll_once`
registry snapshot waiting on `reg query
HKLM\SYSTEM\CurrentControlSet\Services` through
`runner/ops/windows.py`'s `_reg_query` — shard 5 inside
`test_result_stash`'s never-twice property test, shard 13
inside `test_oracle_no_widening`'s repair test. On this rig
`reg query` is slow, a registry snapshot rides every poll,
and a property test polls many times: death by accumulation,
not by one hang. Shards 14 and 20 died blocked in `input()`:
`test_install_edges`' fresh-config seed test and
`test_install_platforms`' fresh-install test reached
`prompt_yes_no` because stdin was a terminal in the rig
launch — a rig-context shape CI does not present (its stdin
is not a terminal), recorded here so a rig kill in an
install test is read as launch context before it is read
as a product hang. Their remaining tests never ran.

The exit-1 failures sort into four piles:

- **The loopback oracle family — the same family the
  3.16.20.9 tag build failed on shards 8 and 19.** Shard 8:
  `test_oracle_send_contract`'s slow-model test (an error —
  the loopback server did not answer inside the client's
  timeout) and `test_oracle_ab`'s briefs-agree test. Shard
  25: nine failures — eight in `test_oracle_send` (the five
  ask-reachability tests, the slow-model bound, the
  Windows-path ask and the eight-concurrent-asks test) and
  `test_platinum_oracle`'s failed-chat-log ask.
  Shard 19 adds two `test_runner_face` inference tests and
  shard 23 two `test_local_signals` model-pipeline tests.
  These tests pass when the loopback server gets its cycles
  and time out when 8 shards share 8 logical processors with
  other rig work: genuinely load-sensitive, not rig-broken,
  and the local loop reproduces the CI failure family on
  demand — which is what the loop is for.
- **Rig-environment artifacts, not CI-comparable.** The rig
  tree has no `.git` (verified directly), so the tracked-tree
  tests cannot run there: shard 11's two
  `test_gitignore_state_files` tests (git exits 128) and
  shard 27's `test_agent_state_tree_wide` test. Shard 26's
  fourteen `test_oracle_page_script` errors are
  `FileNotFoundError` — the JS checker executable is not on
  the rig's PATH. Shard 19's three `test_confinement`
  BuildCommand errors are `cannot resolve interpreter
  'python3'` in the rig's private-Python PATH shape.
- **The nested-runner family.** Shard 16's eight
  `test_parallel_runner` failures and shard 22's
  `test_windows_durations` table-mode failure share one
  shape: a nested suite run returns 1 where the test expects
  0. The shard output names the return code, not the inner
  cause; isolating it is follow-on work, not claimed here.
- **Singles.** Shard 2 `test_regression_pass`'s
  break-is-named (in a genuinely slow shard, above);
  shard 7 `test_runner_last_edges`' do-post answer and
  `test_temp_reap`'s foreign-name; shard 9 `test_runner`'s
  timeout-kills-tree; shard 10 `test_sense_delivery`'s
  outside-a-clone; shard 11 `test_cancel`'s
  running-job-killed; shard 21 `test_core`'s
  plain-script run; shard 24 `test_platinum_runner`'s
  name-boundary; shard 26 `test_local_rig_tools`' child-lines
  and `test_install_wipe`'s two wipe tests (also the shard's
  two slowest, at 101.4s and 97.3s).

No duration-table change is landed from these numbers, and
the reason is measured, not cautious. The table's own tool
was run against the Run 2 log in a scratch tree: it rewrites
453 of 454 entries from this one log, prices
`test_workspace_isolation` at 1,116.1s and
`test_oracle_alphabet` at 1,017.2s — each a single module
the packer cannot split, so both land as singleton shards
over the 720s budget and the table's `--check` fails — and
it drops `test_de_dust_corpus`'s 720s floor to 327.5s,
erasing a CI measurement with a rig one. Rig seconds are
slower-machine seconds (the full suite took 3,710s at
8-in-flight here; the CI step runs all 28 at once), and the
estimator keeps the largest value it has seen, so a rig
refresh would poison the CI packing in both directions.
The table refresh stays what the tool's drift rule says it
is: an operation on CI build logs. What the rig run does
support is naming the two modules whose honest price
exceeds the whole shard budget — `test_workspace_isolation`
and `test_oracle_alphabet`. No re-price fixes a module that
does not fit in a shard; splitting one of those files is
the shape a fix would take, and that is a desk decision,
not a measurement.

What the local loop proves, plainly: the Germany rig runs
the build-windows suite end to end in about an hour with
every failure named, a single shard re-runs in minutes, and
the loop reproduces — locally, on demand — the slow-model /
inference failure family and the registry-poll accumulation
that the tag builds meet at the wall. CI remains the
verdict on durations; the rig is now the verdict on causes.

**W1 conclusion (measured 2026-11-11, two full local suite
runs on the rig, exact CI command and duration table, head
9faa6b62): refuted as stated.** The wall is not primarily a
CI-pool throughput artifact that a faster box escapes. On the
rig (8 logical processors, the CI job's Python 3.12.7), run 1
finished in 1203.1s with 23 of 28 shards failed (6 at exit 124);
run 2's first 19 shards took 328.5s (shard 0) and otherwise
825-1200s, with exit 124 on shards 5, 13, 14 and exit 1 on
shards 2, 7, 8, 9, 10, 11, 16 -- the passing shards cluster at
the 1200s cap itself (1150.8s, 1150.9s, 1150.9s, 1200.4s,
1200.2s), far over the table's 720s per-shard budget. A single
transport service cycle on this rig takes ~15-17s (W2 segment
timings) against under a second on an idle Linux control: the
suite's thousands of subprocess spawns are intrinsically
expensive on Windows, and the rig's standing load (de-dust
corpus growers) adds to it. The rig therefore cannot certify a
shard set "well under the wall" -- it is slower than the pool
for this suite shape. What the local loop did prove is which
failures are real on Windows (below) versus CI-only, at
minutes-per-iteration instead of one hosted verdict per
landing. The named exit-1 failures across both runs are
concentrated in the oracle send/brief family and in
timing-shaped runner tests (`test_timeout_kills_tree`,
`test_slow_model_still_returns_a_body`), plus singletons in
temp-reap and sense-delivery; they reproduce locally, so they
are head behaviour under Windows timing, not hosted-runner
flakes.

**W3 conclusion: did not reproduce.** No
decision1_startup_gates failure (strict, refuse, or phase2)
appears in either local run's failure lists. That matches the
Q159 verdict recorded earlier the same day: the dead-backend
failure was a test-construction bug (a dead backend scripted
only on the bwrap seam, which win32 and darwin startup routing
never consults), fixed test-first on main; the Windows shard
carrying gates_strict read OK in the Q159 rule-8 re-test.

**W2 conclusion (measured 2026-11-11, Germany rig + Linux
control): the supposition's mechanism is refuted; the refusal is
recorded, but late.** A controlled segment run on the rig
(standalone runner, battery config shape: audience enforce,
runner_id hp-rig-test, file transport, cleartext) serviced a
good ping 15.6s after its drop, the tampered envelope 15.5s
after its drop (bad-signature rejection logged and evented),
and the wrong-audience envelope 17.1s after its drop -- at
which point all three records the battery checks were written:
the log line `rejecting seq transport: security policy
(audience): runner_id mismatch`, the security-events.jsonl
entry `auth_rejection / security_policy / audience`, and the
security-audit.jsonl entry `feature=audience,
decision=denied, reason=runner_id_mismatch`. The identical
sequence on an idle Linux control completed every step in
under a second. The battery step failed on six consecutive
heads because the driver read the files after a fixed
15-second sleep: in the 11-Nov battery run the wrong-audience
envelope was delivered to the channel inbox one second after
the tampered rejection and was still sitting there, unconsumed,
when the driver read the records at +15s and tore the runner
down. One core service cycle on the loaded rig (de-dust
growers, parallel test batches) takes ~15-17 seconds; the
driver now waits for the record (up to 90s, polling) instead of
sleeping a fixed time, for both the tampered and the
wrong-audience steps. The product contract the battery depends
on is pinned in `runner/tests/test_audience_transport_record.py`
(5 tests: all three records on the transport path for both the
`aud` and `runner_id` addressing forms, the correct-audience
control, the tampered sibling's distinguishable record, and
mail-path parity).

Verification (2026-11-11, ~8:05 PM PST): the full rig battery
with the fixed driver, run against the 9faa6b62 tree in a clean
dev folder on the Germany rig, returned VERDICT pass=True --
all 17 steps, wrong-audience-refused passing for the first
time in seven battery heads, production runner untouched.

## Four-day release-failure review — 8–11 Nov 2026

Landed 2026-11-11 from the Germany-rig Windows loop lane. Sources: `ship-state.txt`, the diag folders under `ship-work/`, the desk record, the GitHub Actions API (checked 2026-11-12T01:34Z), and first-hand rig battery evidence gathered the same evening.

Scope note: `ship-state.txt` contains no entries dated 8 Nov. The GitHub
releases list shows 3.15.20.6 / .7 / .9 published early 9 Nov UTC
(8 Nov PST evening) with no failure recorded. The failure record in the
assigned sources effectively opens on 9 Nov after 3.15.20.19, so the
"4 days" below are 9–11 Nov PST plus the 8 Nov evening baseline.

### Bottom line

No release has been published through the normal pipeline since
3.15.20.19. Every 3.16 release that exists (.1, .2, .3) exists only
because the conductor overrode the green-head gate and the lane direct-
published around a failed tag build — in each case missing the
windows-x86_64 archive. Every non-override cut since (.4 tagged;
.5, .6, .7 as release heads on main) failed or stalled. The failures are
not one bug: they are five recurring families (below) that kept
recombining, and most individual fixes worked — each one removed the
failure it aimed at and exposed the next one behind it, while parallel
landings kept cancelling the CI verdicts that would have proved a fix
before the next cut was attempted.

Anchor check against the record:

- Last published release **3.16.20.3, 2026-11-11T09:27:36Z, 12 assets** —
  confirmed (ship-state `last_completed`; GitHub releases list agrees,
  latest non-draft release).
- **3.16.20.4 retired, never published** — confirmed. Tag build
  43003938484 failed in both attempts on build-windows only. One
  correction to the ship-state summary: it records attempt 2 as
  "shards 0 and 4 exit 124"; the diag log
  (`diag-3.16.20.4/build-windows-a2-failed.log`) shows shard 0 FAILED
  exit 124 at 1200.2s and shard 4 FAILED **exit 1** (failures=1) at
  1200.2s. Attempt 1 was shard 0 exit 124 only.
- **3.16.20.5 failed on its own release head** — confirmed. Main build
  43121516173 for release head 072cf965 completed failure at
  2026-11-12T00:00:35Z: test, build-windows, test-macos red; test-leg
  annotations show figure/token mismatch (21038 != 21082 on
  runner/ops) and a README max_job_bytes list diff. Never tagged.
- **3.16.20.6 superseded** — confirmed, with an addition: its main
  build 43125609374 also completed failure on the same three legs
  (test, build-windows, test-macos) before the .7 bump superseded it.
  Never tagged.
- **3.16.20.7 standing, untagged, main build red on test + test-macos**
  — confirmed as of the last ship-state check: build 43129868071 for
  release head 9ae310d4 had its test job complete failure at
  2026-11-12T01:13:29Z and test-macos at 2026-11-12T01:01:40Z, with
  build-windows still in progress; tags at the remote stop at
  v3.16.20.4 and no release exists for .5/.6/.7.

### Timeline of failed / blocked cuts

#### 9 Nov — the last normal ship, then the phase-2 wall

- **3.15.20.19 published 2026-11-09T19:35:45Z, 13 assets** — the last
  pipeline ship. Its own main build 42672130768 failed attempts 1–3
  (18:13–18:46Z) at startup with platform jobs never created — a
  GitHub Actions platform failure, not head-caused; attempt 4 rerun
  completed success 19:13:38Z; tag build 42681498982 green.
- **9 Nov 18:04 PST onward — blocked, repeatedly.** Head batch
  7c6042c2 ("confinement and job_user at enforce refuse the job") and
  3891c7b0 (audience enforce with no runner_id refuses) made
  switch-proofs (42745448644, all 5 legs), minimal-userland
  (42745448728), platform-matrix (42745449077) and the build's
  platform legs fail: harnesses that do not seed the gates were
  refused by the new enforce posture. Hourly and dru-edit lanes
  re-recorded the same block roughly every 5–60 minutes for two days
  (46 ship-state lines dated 9 Nov, 161 dated 10 Nov — most are
  re-checks of the same few heads, not new failures).
- Reconciliation landed in rounds: eef7f0f2 ("tests reconcile suite
  harnesses with phase-2 enforce posture") plus 4ce2af8f / 4393ade4
  cleared minimal-userland and platform-matrix first (head 6697271c,
  runs 42761730875 / 42761730690 success), then switch-proofs
  (42795422581 success on head a4633e6a, 10 Nov 02:04 check) — but the
  build leg stayed red as the Windows and macOS backends landed and
  invalidated the next set of fixtures (see Cause 2).

#### 10 Nov — 3.16.20.1 by override; a day of shard-1

- **3.16.20.1** cut under conductor override with a known figure-slot red.
  Tag build 42813675786 completed failure: test (1 failure —
  ConfinementDecisionFuzzTest, config `{'work_mount': {'extra_flags':
  ['']}}` drew JobRejected where the fuzz contract expects a triple),
  test-macos (missing-config family: InstallMainTest FileNotFoundError
  on config.json; also 2 first_ping BenchTest failures in the
  continuation record), build-windows (confinement parity tests
  expecting refusal now meeting the real Windows Job Object backend).
  Published anyway by direct publish, **2026-11-10T12:54:11Z,
  12 of 13 assets** (windows-x86_64 zip never produced). The
  missing-config defect was real and was fixed on main afterwards
  (2fe83354, 41c55ec2).
- **06:04 block:** head aac5c98e, build 42830383793 failure — the same
  fuzz failure on test, and build-windows **shard 2 exit 124**.
- **14:04 block:** head a0e966e9 — build-windows shard 4 assertion
  (stale win32 job_user refusal test) plus shard 1 at the wall. The
  assertion was fixed test-first in-run (e45bc0ef); the fixed head's
  build 42912027648 then failed build-windows with **no assertion
  failures: shard 1 exit 124 at 1200s**, and a single-job rerun failed
  identically — deterministic, not a flake. The Q136–Q138
  duration-balanced split in that head batch packed shard 1 at 606s;
  its real Windows runtime exceeded 1200s.
- **16:04 block:** after two DocDrift pin fixes in-run (README line
  438→439, ea40208d then f33e6291), build 42933646758 for f33e6291 was
  green on every leg except build-windows: **shard 1 exit 124 again**,
  rerun identical. Shard 1's 89-module set produced no test output
  before the kill; sibling shards finished in 531–663s.
- **19:04 block:** head 88a65585, build 42948790120 — test/test-macos
  2 failures each (DocDrift: 9 PROTOCOL.md rows stale after 67477628
  inserted 13 lines at line 255; posture-stamp announcement suppressed
  by the full-suite 50/min INFO cap in runner.log) and build-windows
  shards 2 and 6 on the same DocDrift failure, **shard 5 exit 124**
  (pre-existing at the previous head too), shard 7 on a confinement
  FallbackTest (AssignProcessToJobObject failed: 5). Fixes landed
  in parallel during the run (8de50fd5 job_user postspawn; 5c065c70
  "re-price the two Windows files whose under-pricing killed
  shard 5").
- **3.16.20.2 claim (19:32) and fix series:** doc-line pins shifted
  +13, posture harness given a fresh log-budget window, core
  re-measure, excluded-runners pin, **Windows durations second
  re-pack (13 shards, 693s packed)**, registry pin follows. Completed
  by conductor-override direct publish **2026-11-11T07:27:35Z, 12 of 13
  assets** — its tag build's build-windows failed on **shard 0 exit
  124** ("its last pricing predates the Q139–Q142 test growth").

#### 11 Nov — .3 by override, .4 burned, re-packs 3–5, macOS lands

- **00:04 block:** version-rot deterministic on the .2 head's
  ancestors — desk.md names standing version 3.16.20.2 at lines 3759
  and 3838; build 42978022907 failure on test / build-windows /
  test-macos from that one test plus its regression-guard wrap.
- **3.16.20.3:** tag build 42987279998 failed on **all 3 attempts
  solely on build-windows shard 0 exit 124** (08:28–08:48Z,
  08:52–09:12Z, 09:15–09:36Z; no failing test in any attempt; shards
  1–12 OK). Direct-published under conductor override
  **2026-11-11T09:27:36Z, 12 assets**, stamp MATCH x11. (The hourly
  lane's `failure_3.16.20.3` line claiming "no release exists" was
  itself corrected in-file: it was written from a stale check after
  the publish had already happened.)
- **3.16.20.4:** figures refresh at fresh measure 20,603,074 tokens;
  release commit cdaabb3e; tag build 43003938484 failed both attempts
  on build-windows only (attempt 1 completed 2026-11-11T10:50Z,
  shard 0 exit 124; attempt 2 completed 11:13Z, shards 0 and 4 —
  see anchor correction above). Every other leg passed both times;
  publish jobs skipped; no release exists. **Retired; number never
  to be reused.** The diag log shows the shape plainly: 12,184 tests
  from 445 modules in 13 shards, packed 687s each against the 720s
  budget / 1200s wall (`diag-3.16.20.4/build-windows-failed.log`).
- **03:04–13:04 hourly blocks — the re-pack verdicts that never
  landed clean:**
  - 04:04: head 86a7dccd, build 43016116636 — shard 0 exit 124 plus
    shards 9/11/12 exit 1 on version-rot. Head 17215122 had already
    proven the same: test green, shard 0 exit 124
    (`diag-head-1721/`).
  - 05:04: **third re-pack landed** (4358d91c; 20 shards × 684s
    packed, new test_v2_consult floor) — but builds 43025436550,
    43025879627, 43026429006 containing it were each **cancelled by
    the next landing** before build-windows could give a verdict.
  - 06:04: the waited-for verdicts arrived, negative: build
    43026648905 (third re-pack head) — **shard 3 exit 124**, plus
    exit-1 shards on version-rot / socket failures; build 43028546019
    — **shard 3 exit 124 identically**. Fourth re-pack landed as the
    new head (8832364c) during the same run.
  - 07:04: fourth re-pack's own head build 43034909285 cancelled;
    first completed build containing it, 43035985891, failed —
    **shard 3 exit 124 again**, plus version-rot shards.
  - 08:04: **fifth re-pack landed** (de8db74e); four builds containing
    it cancelled; the one completed build, 43047662646, failed with
    **8 shards down (0, 13, 18, 20, 21, 22, 24, 26)**, sharded run
    finished in 1200.4s — by now the failure set is no longer a
    single timed-out shard.
  - 09:04–12:04: completed builds 43057662476, 43066279369,
    43068145970, 43073089180, 43075489988, 43087401511 all fail test /
    test-macos / build-windows on the same guard family: version-rot
    (standing version still 3.16.20.4, named in desk.md) +
    regression-guard wrap + oracle-chat/concurrency timeouts, with
    shard 0 exit 124 still present in 43057662476.
  - 13:04: no completed build at all — 43099709468 pending, then
    cancelled when the next landing superseded it; 43100858527
    pending at check time.
- **14:04 block:** head d3b5cfce, build 43105044003 failure on all
  three legs. New material since .4: the **macOS confinement backend
  landed after the .4 cut** (e88c2a90, fix b82870a8). test-macos
  shard 0: **all 7 LiveBackendTest live Seatbelt tests failed**;
  shard 2: **gates_strict dead-backend test** expects "bwrap is not
  installed" but the darwin backend reports its Seatbelt engage
  failure. build-windows: 8 shards failed (3, 8, 14, 15, 16, 22, 23,
  27) — same dead-backend test (rc 0 != 2 on Windows), same
  version-rot, plus oracle concurrency / windows-cli-sim / de-dust
  singles. test (linux): version-rot only (desk.md naming 3.16.20.4
  at lines 5622/12155/12340/12981/13652) plus its guard wrap.
  Logs in `diag-head-1404/`.
- **15:04 hourly monitor:** head 5452979b, build 43118076619 failure
  on the same three legs, but with real movement: **no wall-clock
  kill this run**, and **Q159 cleared the gates_strict dead-backend
  failure** (absent everywhere). Remaining: test — version-rot ×2,
  the decision1 split-family 97-test pin, regression-guard gates;
  test-macos — **all 10 LiveBackendTest tests still failed** after
  the second macOS fix, plus the same trio; build-windows — 25
  distinct failures, ~15 of them the oracle server/chat/concurrency
  family, plus test_macos_confine SandboxArgvFieldTest ×4, doc-rot,
  durations pin. Logs in `diag-head-1504/`.
- **15:28 — .5 override claim** (the conductor's direct order). Release head
  072cf965 (release commit 8a71710b + decision1 pin fix in the same
  commit, shard-5 follow-on 18cde84b, changelog 072cf965). Its main
  build 43121516173 completed failure 2026-11-12T00:00:35Z (above).
  Desk record for that same run: build-windows **shard 7 FAILED exit
  124 at 1201.4s**, shard 5 OK in 839.4s, shard 0 OK in 624.3s, and
  shard 11 failed the shard-5 fix's own bound test (30.14s not < 15).
- **.6 and .7 (16:04–17:19 checks):** .6 release commit dac053eb
  ("pipeline repair after the untagged 3.16.20.5"); build 43125609374
  completed failure, same three legs. Then four .7
  release commits and release head 9ae310d4; build 43129868071 red on
  test + test-macos (above), build-windows unfinished at last check.
  No tags for .5/.6/.7; last_completed stays 3.16.20.3. End-of-window
  GitHub sample (runs list, 2026-11-12T01:03–01:35Z): 6 consecutive
  build runs **cancelled**, each superseded by a new landing within
  minutes — the head is still moving faster than a build completes.

### Recurring root causes

#### 1. The wall-clock kills were mostly hangs, not load — so re-packing kept moving them

The Q136 line treated shard timeouts as a pricing problem: seed split
(10 Nov) packed **5 shards ≈613s** against the 1200s wall; the seed had
priced the suite at 3/5 of its real Windows cost. First re-pack: **8
shards × 655s**. Second re-pack: **13 shards, 693s**. Third: **20
shards × 684s**. Fourth and fifth followed the same day. Shard count
went 5 → 8 → 13 → 20 → 28 across the window, and a shard still died at
the wall in almost every completed build — at shard 2, 1, 1, 5, 0, 0,
3, 3, 0, 21, 5, 7 in successive verdicts.

The desk's own later measurements show why pricing could not fix it:

- **GATES2 (Q136 follow-on):** runs 43073089180 and 43075489988 each
  show shard 21 dying at 1201.4s / 1201.6s with **exactly 7 progress
  dots** — inside `test_decision1_startup_gates`, before any companion
  module started. Mechanism, proven by simulation: a refuse test
  constructs "cannot engage" only through the bwrap probe; on a real
  Windows host whose Job Object backend engages, no refusal fires and
  `main()` — called with no one-shot argv — proceeds into the mailbox
  poll loop and never returns. Two StrictShape win32 tests behind it
  in load order were latent fast failures (rc 0 != 2) that the hang
  had been masking. Fix: split the gates piece along class seams into
  gates_refuse (5 tests, priced 100s), gates_strict (6, 180s),
  gates_phase2 (7, 150s), and script the cannot-engage backend in the
  three named tests. Local cost of the whole piece: ~1s. The wall
  record was a hang record, not a price record.
- **Shard-5 follow-on:** after GATES2, build 43101076872 (head
  9dfc1ba2) killed shard 5 at 1201.7s. The kill dump named
  `test_oracle_cli_ctrl_c`, its main thread inside a
  `subprocess.run` communicate reached through `_firewall_posture`'s
  netsh read. Confirmed mechanism: on Windows, CPython's
  `subprocess.run` answers a timeout by killing the child and calling
  `communicate()` with **no second timeout**; a child leaving its
  pipe held open makes that wait unbounded. Fix: `runner/ops/av.py`
  `_run_text` now drives Popen by hand (bounded first wait, 2s grace
  after kill, pipes abandoned past grace), and test_de_dust_corpus
  was floored at the 720s budget to pack alone — explicitly as
  insurance, not measurement: its supposed 900s+ cost was **not**
  supported (one completed appearance bounded it at 391.5s).
- **Shard-7 follow-on:** on the .5 release head the same ctrl_c test
  killed shard 7 at 1201.4s — this time by race: a background
  oracle-server thread (Thread-442 in the dump) consumed the test's
  counted KeyboardInterrupt, leaving the main loop with no exit,
  re-computing the deterministic answer until the wall. Sibling
  shards completed at 836–853s against ~707s packed (1.19×), so the
  pool was not uniformly slow. Fixes: the interrupt counts only
  main-thread calls, scripted input carries a finite /quit backstop,
  `_reg_query` / `_wevtutil_query` re-seamed onto the bounded
  `_run_text`, and the bound test's own 30s leak (stream.close()
  behind a reader thread) fixed in `_abandon`.

Why the wall moved instead of clearing, in one line per step: every
re-pack redistributed *measured* durations, but a killed shard yields
no durations for the tests it never finished (the estimator's
"killed-shard blind spot", named in the re-pack suppositions), so each
new table was priced from the survivors; meanwhile the actual kills
were single-test hangs whose cost is infinite at any packing, and
fixing the hang in load order exposed the next latent failure behind
it. Suite growth (Q139–Q142, Q157, the macOS backend) added load at
roughly the rate the re-packs removed it.

#### 2. Each new confinement backend invalidated the previous round's test assumptions

Phase-2 enforce (9 Nov) refused jobs on any harness that did not seed
the gates. The reconciliation pattern then repeated per backend:
fixtures written when a platform *had no backend* assert refusal /
fallback; the backend lands; on the real host the backend engages and
the assertion inverts. Instances: switch-roster and M8 fixtures
(rounds 1–4, 9–10 Nov); .1 tag build-windows confinement parity
failures; the stale win32 job_user refusal fixed at e45bc0ef; the
windows_confine seam failures on darwin in the macOS round-1 job
(fallback recorded as `macos_confinement_failed` where
`windows_confinement_failed` was expected; `_spawn() got an unexpected
keyword argument 'user'` ×3); and **gates_strict dead-backend (Q159)**:
the test scripted a dead backend only on the bwrap seam
(`sandbox_problem="bwrap is not installed"`), which win32 and darwin
startup routing never consults — so on Windows the runner correctly
started (rc 0 != 2) and on macOS it refused with the Seatbelt wording
instead of the expected bwrap wording. Q159's measurement cleared the
product (a dead backend on its *own* platform seam refuses correctly
on every platform) and fixed the test to script a dead backend on
every platform seam, with a live-backend control per platform (fix
landed 14:56 PST 11 Nov; family grew 6→8 tests). The rule-8 re-test
on the fix head's completed build 43115883568 confirms it: Windows
shard 27 (the gates_strict shard) reads OK, Linux 8 of 8 ok, and
macOS shard 2's 10 failures are all other tests (the 7 live Seatbelt
tests, the split-family pin, core, doc-rot). By the 15:04 hourly run
the failure was gone from all three legs. The cost was a
full day of red builds for a test-construction bug — because the
failure *looked* like a fail-closed security hole and had to be
disproven platform by platform first.

#### 3. macOS confinement: contract green, live proof failed three rounds

The backend landed 11 Nov (e88c2a90) with contract tests green
off-darwin and the live class skipped off-darwin — CI's test-macos
leg was the only live proof, and it arrived after the landing:

- **Round 1:** build 43089173541, test-macos job 130770346469,
  completed failure 12:07 PST 11 Nov — all 6 LiveBackendTest tests
  failed; confined spawn aborted exit -6 and could not read its
  staged file. (Ship-state's 14:04 head shows the family at 7 tests.)
- **Fix 1** (shim sets data-size limit only; profile names the
  `/private` canonical twin of every /var and /tmp path; spawn seam
  derives platform from `sys.platform` alone) → **round 2: all 7 live
  tests failed with the same exit -6** — the fix's primary
  supposition (512 MiB address-space limit aborting the interpreter)
  stands recorded as wrong.
- **Fix 2** (one `(allow file-read-data (literal "/"))` line; adds
  /private/var/db/dyld, timezone, select trees; 3-point bisect:
  native binary / profile alone / shim alone) → **round 3: failure
  in a new shape** — two test-macos jobs (the figures head's build
  and the .5 release head's build) fail all 10 live tests at exit 1:
  `python: realpath: /Library/Frameworks/Python.framework/...:
  Operation not permitted`. The -6 abort is gone; a further startup
  need is refused by name.
- **Fix 3** (one `(allow file-read-metadata)` line; shim refuses by
  name instead of bare exception; bisect widened to 12 live points)
  has landed and was carried into the .7 release measure; **no
  completed test-macos verdict on a fix-3 head exists in the record
  yet** — the live proof is still owed, and the support level stays
  "Supported, reduced confinement" throughout.

Each round-trip cost hours because the verdict can only come from a
completed hosted build, and (Cause 5) most builds in the window were
cancelled before test-macos completed.

#### 4. Figure / token / doc-pin rot: the guards pin a tree that moves hourly

The suite pins exact figures and line numbers — token counts in
figure slots, registry rows naming README/PROTOCOL line numbers, the
split-family test counts, and a guard forbidding the standing version
string in evergreen docs. Every landing moves those numbers:

- DocDrift pins: README 438→439 (one DRU edit); PROTOCOL.md +13 lines
  (67477628) staling 9 registry rows; later +22 and +2 follows.
- Split-family pin: GATES2 changed gates_strict 6→8 tests and the
  family 97→99; the pin and the .5 release landing raced, and the
  15:04 head still failed `test_the_decision1_split_family_still_
  carries_97_tests` until the release commit itself carried the
  reconciliation.
- Posture stamp: passed in isolation, failed in the full suite —
  runner.log's 50/min INFO cap was already spent by earlier tests.
- **Version-rot is structural:** the desk record writes the standing
  version into an evergreen doc; the guard then fails on every leg
  until the next bump. It alone kept test/test-macos red from the
  .4 tag until the .5 bump (desk.md naming 3.16.20.4, line 5517
  growing to five locations by the 14:04 head), and it fired
  immediately after the .2 publish the same way.
- **Release heads rot before they are tagged:** .5's figures were
  refreshed, then README edits and parallel landings landed on and
  around the release commit; its own main build failed on
  21038 != 21082 figure/token mismatch plus a README max_job_bytes
  diff. A figures refresh is only true of the exact tree it measured;
  any later landing — even docs-only — falsifies it.

#### 5. Head churn cancelled the verdicts that would have cleared fixes

The green-head gate requires a *completed* green build. Main landed
every few minutes through the window (159 commits ahead of .3 by the
17:19 check), and each landing cancels the previous head's runs.
Concretely: all three builds containing the third re-pack were
cancelled before a verdict (05:04 block); the fourth re-pack's own
head build was cancelled (07:04); four of five fifth-re-pack builds
were cancelled (08:04); the 13:04 run found no completed build at
all. Fixes therefore stayed "landed but unproven" for a day or more,
hourly lanes kept re-recording the same blocks, and two ship-state
entries (failure_3.16.20.3; the .2 check line) were written from stale
checks and had to be corrected in-file. The end-of-window API sample
(6 build cancellations in ~30 minutes) shows the pattern still live.

#### 6. Wrong-audience rig battery: the refusal is real, the record is late

The rig battery's wrong-audience-refused step failed on five
consecutive heads in the rig-watch record, and on a sixth head
(9faa6b62, standing version 3.16.20.8) in a battery run watched
first-hand on the Germany rig on 11 Nov: every other step passed,
the step failed with `noResult=True`, and at the moment the driver
checked, neither `runner.log`, `security-audit.jsonl`, nor
`security-events.jsonl` contained the word "audience". The
post-run state shows why the record was missing *at check time*:
the file transport had delivered the wrong-audience envelope to
the channel inbox (`transport-extensions/file/inbox/
t8886a478e8e24b92.job.txt`, written 17:45:21 PST, one second after
the sibling tampered job's bad-signature rejection at 17:45:20),
and the core had not serviced the channel again before the
driver's fixed 15-second sleep expired and the battery tore the
runner down. A control run of the identical sequence on Linux
(same tree, same config shape) rejects the wrong-audience job in
the same second it is serviced: `rejecting seq transport:
security policy (audience): runner_id mismatch` in the log and an
`auth_rejection` / `security_policy` / `audience` entry in
`security-events.jsonl`. The audience gate itself is sound; the
battery step races the core's service cycle under rig load and
reads the files too early. (Rig-side timing measurement and the
driver fix are recorded with the W2 conclusion in the supposition
section above.)

### What would have caught each earlier

- **Wall-clock / hangs:** the kill dump that finally named the
  running test (used in the shard-5 and shard-7 lanes) existed in the
  runner's output from the first kills. Reading the dump before
  re-pricing — plus the identical-dot-count check that convicted
  GATES2 (7 dots, two runs, an hour apart) — separates "hang" from
  "load" in one build instead of five re-packs. A standing rule
  "no re-pack from a build whose killed shard's dump has not been
  read" would have routed .2/.3/.4 straight to the hang fixes.
- **Backend-assumption tests:** the simulated-platform construction
  (script a real-marked backend per platform seam, with a live
  control) is the pattern Q159 and GATES2 both ended at. Running that
  construction in the *backend's own landing* — Windows, FreeBSD,
  macOS each — would have caught the parity, job_user, and
  dead-backend failures in the landing build instead of in tag
  builds and hourly blocks days later.
- **macOS live proof:** the 3-point bisect that round 2 added
  (native / profile alone / shim alone) would have named the round-1
  culprit in one verdict instead of two. Gating the support-level
  claim on a completed live verdict — as the record in fact did —
  worked; gating the *next release cut* on it did not happen (.5 was
  cut by override with all 10 live tests failing).
- **Figure/token rot:** a cut whose figures refresh is not the last
  commit, or that allows any landing between refresh and tag, is
  falsified by construction — .5 is the worked example. Either freeze
  landings for the cut's duration, or make the refresh part of the
  release commit itself. Version-rot specifically: the desk record
  could name the standing version in a form the evergreen guard
  exempts (or the guard could exempt the desk's release-record
  sections), instead of guaranteeing a red main after every publish.
- **Churn:** a short landing freeze (or a merge queue) around verdict
  builds for named fixes — re-packs 3–5 each needed exactly one
  completed build-windows verdict and were denied it by unrelated
  landings. The hourly gate's "completed green build" condition is
  unreachable at the window's landing rate without one.

### Evidence index

- ship-state.txt: `failure_3.16.20.4`, `failure_3.16.20.1`,
  `failure_3.16.20.3` + its correction, `completed_3.16.20.2`,
  `last_completed` (.3), blocked lines 2026-11-09_1804 through
  2026-11-11_1719, `hourly_2026-11-11_1504`, `hourly_2026-11-11_1604`.
- Diag: `diag-3.16.20.4/` (13 shards × 687s packed; shard 0 exit 124;
  attempt-2 shard 4 exit 1), `diag-3.16.20.3/`, `diag-head-1404/`,
  `diag-head-1504/` (97-test pin + version-rot FAIL lines),
  `diag-head-0604/`, `diag-head-0704/`, `diag-head-0904/`,
  `diag-head-1721/`, `diag-3.16.20.5/` (log downloads returned 0-byte
  files — the .5 diagnosis rests on job conclusions/annotations).
- Desk (repo mirror): Q136 answer + first re-pack; re-packs 4–5
  suppositions/conclusions; decision1 file split; GATES2
  suppositions/measurement/conclusions; shard-5 and shard-7
  follow-ons; Q159 gates_strict lane; macOS confinement landing and
  rounds 1–3 verdicts/fixes.
- GitHub API (2026-11-12T01:34Z): releases list (latest published
  v3.16.20.3, 2026-11-11T09:27:36Z, 12 assets); runs list per_page=50
  (01:03–01:35Z window: 6 build runs cancelled, 0 completed).

## 48-hour relief mode — 12 Nov 2026 (owner-approved)

The owner approved a 48-hour relief mode on 2026-11-11 (evening,
PST): the pipeline has spent four days red in the families above,
and the hourly release train is starved less by failures than by
the volume of proof that fires on every push and by verdicts that
never complete. The mode is a window, not a posture change: it
expires 48 hours after it lands, and a build-config test carries
the expiry date so the suite itself goes red until the triggers
are restored.

### Suppositions (written before the change is measured)

- S1: the proof fan-out is the larger half of the per-push CI
  cost. Ten workflows fire on every push to main; the nine proof
  workflows beside build.yml (platform-matrix, python-range,
  switch-proofs, minimal-userland, env-axes, job-user,
  queues-worker, upgrade-proof, freebsd) re-prove settled ground
  on every landing. Moving their push triggers to release tags
  plus a nightly schedule for the window should cut the per-push
  runner load to build.yml alone, and completed build verdicts —
  the thing root cause 5 above says the train is starved of —
  should stop being crowded out by proof runs.
- S2: making the three suite surfaces advisory for the window
  (the Linux `test` job, the macOS `test-macos` job, and the
  suite step inside `build-windows`) lets a cut publish on the
  legs that stay gates — scope, shape, typecheck, the artifact
  legs and the rig battery — with suite reds triaged after
  publish. The risk is named plainly: a genuinely broken tree
  can publish inside the window; the next hourly cut is the fix,
  and the suites still run and still show red on the run page.
- S3: cancelling superseded rolling builds (never release or
  tag builds) trades the 2026-10-23 lesson for the window: at
  the current landing rate the no-cancel queue starves verdicts
  (root cause 5), and an hourly train would rather have the
  newest head's verdict than a finished build of a stale one.
  Release commits keep their own concurrency group and are
  never cancelled, so a cut's own build must still finish.
- S4: the hourly seeded mutation walk (~7 minutes a run, ~336
  runner-minutes over the window) buys nothing the window needs;
  pausing its schedule for 48 hours (dispatch stays) is free
  capacity. The build.yml mutation job is already a
  signal-not-a-block on non-tag dispatch only and does not move.

### Operating instructions for the window (not workflow code)

- The rig watch runs the battery on release candidates only;
  while the San Francisco box is unreachable its probe is cut
  short instead of burning the full SSH timeout each pass.
- The Germany-rig local loop runs targeted shards only, never
  a full-suite run (the W1 measurement above: the rig is slower
  than the CI pool for this suite shape).
- Suite reds inside the window are triaged after publish, in
  the desk's ordinary queue; a red that names a real product
  defect still gets its fix lane, it just does not hold the
  train.

### Conclusions

(Recorded below once the change and its tests land.)

## The 3.16.20.10 cycle: three hours from a red head to a published release, and what each hour was (11 Nov 2026)

The first release published through the pipeline since
3.15.20.19 is 3.16.20.10 (tag build 43152532925: release,
pypi-publish, sourceforge and gitlab all green, 13 assets
with the windows-x86_64 archive, the image pushed as
`v3.16.20.10` and `latest`). Getting there from the red
3.16.20.6 head took three hours of wall time. Where it went,
from the Actions record:

- **Seven full build cycles at 20 to 25 minutes each.** The
  Linux suite ran serially (12,700 tests, 17 to 20 minutes)
  and was the long pole of every build; the Windows leg
  took 12 to 14 once its probe deadlock was fixed. Every
  fix, however small, cost a whole cycle to confirm.
- **Four of those heads went red for reasons that landed
  between cycles**: two desk notes naming the release in
  flight (the version-rot guard), five files cut to a few
  lines by an API edit on main (install.py, pyproject,
  macos_confine.py twice, the changelog, test_low_profile),
  and a probe-runner change that deadlocked every Windows
  poll. None of them were in the head being tested when the
  cycle began.
- **Rolling builds cancelled each other.** With the desk
  landing a note every few minutes, no rolling build
  completed for an hour; only release-prefixed commits,
  which keep their own concurrency group, ever reached a
  verdict.
- **One dead end of my own**: capping the Windows shards at
  8 in flight, which took that leg from 8 minutes past 40
  before the real cause (the probe runner reading nothing
  until the process exited) was read from the kill dumps.
- **Two hand-published releases in the way**: v3.16.20.9 was
  tagged on a head whose tag build was red, so the version
  had to move again before a pipeline cut could run.

What changed in the same evening, so the next cycle is not
this one:

- The Linux suite runs in 4 shards through the parallel
  runner, which now writes the -v log the skip guard and the
  release snapshot read (`--full-log`, one combined verdict
  at the end); expected 6 to 8 minutes instead of 17 to 20.
- A documentation-only push (the desk's notes, the manuals)
  runs the documentation guards in about a minute and none
  of the matrix; pushes whose message starts with `desk:` or
  `docs:` take their own concurrency group and never cancel
  a code build.
- The `shape` job names a file cut to a fraction of itself
  at the commit that did it (3.16.20.8).
- The probe runner drains its pipes while it waits
  (3.16.20.8); the loopback tests carry hang guards instead
  of latency bounds (3.16.20.9 and .10).
- The cut gate reads the build run's own jobs, not check
  runs by name (3.16.20.8).

What still costs a cycle: a desk note that names the
release in flight in a reader-facing guide (desk.md is a
record to the version-rot guard now; the guides are not),
and an edit tool that writes a file's head and drops the
rest, which the `shape` job can only name after the push.

The docs-only scoping ran first on the support-matrix push of 2026-11-12T05:04Z: scope, shape and the docs job, the matrix skipped.

## The 3.16.21.1 and 3.16.21.2 cycles: 35 minutes with one hand step, then 31 with none (11 Nov 2026)

Two cycles ran back to back after the 3.16.20.10 report above,
each read from the hosted record with
`python3 runner/tools/release_train.py clock --version V --since T`
(the `clock` command landed in the second one). Times are UTC;
the minutes column is from the first row.

The 3.16.21.1 cycle, asked for at 06:19:58Z with the release
commit already on main:

```
release commit 8ef9627f                              06:17:22Z             0.0 min
build 43167098786 started                            06:17:27Z    +0.1     0.1 min
asked for                                            06:19:58Z    +2.5     2.6 min
gate green (8 jobs)                                  06:29:51Z    +9.9    12.5 min
cut-release 43168555643: failure at 'the build on this commit is green' 06:30:00Z    +0.1    12.6 min
cut-release 43168597966: failure at 'the build on this commit is green' 06:30:20Z    +0.3    13.0 min
cut-release 43168755640: failure at 'tag'            06:31:37Z    +1.3    14.2 min
tag v3.16.21.1                                       06:37:07Z    +5.5    19.8 min
tag build 43169400192 started                        06:37:13Z    +0.1    19.9 min
build 43167098786 whole: success                     06:38:09Z    +0.9    20.8 min
release published (13 assets)                        06:51:37Z   +13.5    34.2 min
release: success                                     06:51:39Z    +0.0    34.3 min
pypi-publish: success                                06:52:05Z    +0.4    34.7 min
gitlab: success                                      06:52:47Z    +0.7    35.4 min
sourceforge: success                                 06:52:56Z    +0.1    35.6 min
```

Where the 33 minutes from the ask went: 10 waiting for the
gate (build-windows is the long pole, 12 minutes from the
commit; the Linux suite in 8 shards took 10.2 minutes on main
and 5.6 on the tag build); 2 on two dispatches the gate refused
because it read the run's status while the advisory macOS
suite was still running (the gate now judges by the gate jobs
alone); 1 on a third dispatch whose tag step the workflow's
token refused; 5.5 for the tag placed by hand; 14.5 for the
tag build to the release (12 of them build-windows again, 2
the release job) and 1.5 for the three mirrors.

The 3.16.21.2 cycle, run as `prepare` then `cut` with the two
fixes the first tag build exposed:

```
release commit 306a3d69                              06:52:11Z             0.0 min
build 43171155203 started                            06:52:14Z    +0.1     0.1 min
asked for                                            06:52:30Z    +0.3     0.3 min
gate green (8 jobs)                                  07:04:25Z   +11.9    12.2 min
cut-release 43172608949: success                     07:04:45Z    +0.3    12.6 min
tag v3.16.21.2                                       07:05:01Z    +0.3    12.8 min
tag build 43172645703 started                        07:05:03Z    +0.0    12.9 min
build 43171155203 whole: success                     07:12:58Z    +7.9    20.8 min
release published (13 assets)                        07:21:18Z    +8.3    29.1 min
release: success                                     07:21:21Z    +0.1    29.2 min
pypi-publish: success                                07:21:43Z    +0.4    29.5 min
sourceforge: success                                 07:22:41Z    +1.0    30.5 min
gitlab: success                                      07:22:53Z    +0.2    30.7 min
```

No hand step: the gate, the dispatch, the tag and the mirrors
in 31 minutes, of which 24 are the two build-windows legs and
the rest is the release job and the mirrors. Every mirror's own
words were read out of its publish log (PyPI's "View at" line,
SourceForge's file listing and git push, GitLab's uploads and
release, the image tags `v3.16.21.2` and `latest`).

What the first tag build found, and where each went:

- The macOS confinement backend engaged on the CI runners for
  the first time (its fifth fix landed in the 3.16.21.1 tree),
  and two tests whose refusal arms were keyed on bwrap's probe
  -- Linux-only by construction -- failed on a job that ran
  confined: `test_confinement.FallbackTest` and the canary's
  enforce arm. Both now ask the runner's own startup gate on
  Windows, macOS and FreeBSD and accept the backend's
  `confined` row (3.16.21.2). Both macOS legs of switch-proofs
  went red on the tag for the first of them; the roster is
  green again at the fix.
- One macOS shard hit its 20-minute wall in both tag builds
  with a row of dots and no test name. The macOS suite now
  keeps its -v log (`ci-test-log-macos`), and the suppositions
  in the project desk name the test (a startup-refusal test
  that gates on bwrap's probe and, on a host whose backend
  engages, runs on toward the poll loop); its fix is in the
  lane that wrote them. Until it lands, `test-macos` walls at
  20 minutes and holds the tag build run -- not the release,
  which waits on the artifact legs alone -- so the train now
  reads its verdict from the four publish jobs instead of the
  whole run.
- The workflow token's tag rule, read from two cuts: with no
  RELEASE_TOKEN set, the REST path placed v3.16.21.2 while the
  tree's workflows differed from the last tag's, and was
  refused v3.16.21.1 at 06:31Z, when main's head had moved
  past the commit with a newer cut-release.yml. The token tags
  the commit that is main's head; a workflow change landed
  after the release commit is what the refusal names, and the
  train's remedy says so. The secret (Q30) remains the way to
  tag a commit main has moved past.

What this leaves as the cycle's floor: the two build-windows
legs, 12 minutes each, on the gate side and the tag side. A
cycle cannot be shorter than about 28 minutes until that leg
is shorter or the tag build reuses the gate build's artifacts.
