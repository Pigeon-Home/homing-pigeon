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

## Fuzzing the pipeline on paper: the failure modes it has shown

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
