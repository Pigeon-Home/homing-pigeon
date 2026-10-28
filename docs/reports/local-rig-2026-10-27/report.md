# Local rig regression and coverage, 2026-10-27

<!-- Agent-Stamp: c0000327-6a7b-42df-81b9-21136287db1c -->

One box with no PyPI ran the whole suite three times and measured
it twice, on main at `a2b5e564`. Nothing here needed a package from
outside the tree.

## The box

| | |
|---|---|
| Cores | 2 |
| Python | 3.13.18 |
| Packages | the standard library and pytest; no hypothesis, no coverage.py |
| PyPI | unreachable (the egress refuses it) |

## Regression passes

The ledger lines are the last four in
`docs/reports/regression/passes.jsonl`.

| Pass | Tree | Verdict |
|---|---|---|
| 1 | `a2b5e564` as pulled | red: 13 ids that import hypothesis, and `test_gamma.T.test_bad` |
| 2 | with the fixes below | green, recorded as 3704 tests |
| 3 | with the count fix | green, the full suite counted |
| 4 | the same work on main at `0bb0f5f1` | green, 7823 tests |

Pass 1 found three things, none of them a red main.

1. Ten property modules imported hypothesis at the top, so on a box
   without it each failed to load and took its deterministic tests
   down with it. The suite's older property modules already guard
   the import. These ten now fall back to
   `runner/tests/_hypothesis_shim.py`: strategies evaluate to inert
   placeholders, `@given` tests skip as `hypothesis not installed`,
   and every other test in the module runs. The three seed-hook
   tests that need hypothesis itself skip by the same reason.
   `build.yml` and `python-range.yml` install hypothesis and now
   forbid that skip (`skip_guard.py --forbid`), so a property test
   can never go missing there.
2. `test_gamma.T.test_bad` is not a suite test. It is the failing
   fixture `test_parallel_runner` builds in a temp dir, and one test
   let its `FAIL:` line reach the real stdout, where
   `regression_pass.failing_ids` read it as a red. A lone re-run of
   an id that does not exist can only fail, so the pass called it
   deterministic. The fixture's output is now captured, and
   `failing_ids` keeps only `runner.tests.*` ids.
3. Pass 2 counted 3704 tests of 7409. One shard's interpreter
   printed three `ResourceWarning` lines after `OK` (a subprocess
   and two pipes a test left open), which pushed its `Ran` line out
   of the four-line tail `run_tests_parallel.passing_tail` keeps.
   The tail is now anchored on the last `Ran` line. The warnings
   themselves are still there: a test in shard 0 leaves a child
   running.

## Coverage

`runner/tools/stdlib_coverage.py` is new: line coverage from
`sys.monitoring`, every line disabled after its first hit, child
Pythons traced through a `sitecustomize` on `PYTHONPATH`, and the
report written in coverage.py's JSON shape so `coverage_gaps.py`
reads it unchanged. It counts statements, not branches, and misses
children started with a scrubbed environment or ending in
`os._exit`, so it reads at or below coverage.py on the same tree.

| | Statements | Never run | Covered |
|---|---:|---:|---:|
| Before | 37937 | 417 | 98.90% |
| After | 37937 | 322 | 99.15% |

Both runs passed (7416 tests counted, 250 child Pythons traced in
the second). The data is `coverage-before.json` and
`coverage-after.json`; the gap list after is `coverage-gaps.md`.

`runner/tests/test_local_rig_gaps.py` holds 41 deterministic tests
for arms that were never run here, most also on CI's list
(`docs/reports/v3.13.62/coverage-gaps.md`), or reached only by a
random hypothesis example:

| File | Before | After |
|---|---:|---:|
| `extensions/pi-health/pi_health.py` | 92.3% | 99.1% |
| `guard/panic.py` | 90.2% | 96.4% |
| `ops/exec.py` | 97.0% | 99.0% |
| `wire/dtlsproto.py` | 98.5% | 99.2% |
| `cloud/send_job.py` | 95.4% | 96.5% |
| `wire/verify.py` | 95.4% | 96.2% |
| `wire/transports.py` | 99.0% | 99.7% |
| `guard/extreview.py` | 98.7% | 99.6% |
| `guard/sandbox.py` | 98.8% | 100.0% |
| `extensions/softflowd-feed/softflowd_feed.py` | 99.6% | 100.0% |

`pi_health._mem_avail_pct_windows` had run nowhere: CI's Windows
legs do not load the pi-health extension. It now runs against a
stand-in `GlobalMemoryStatusEx` that refuses a struct of the wrong
length, as Windows does.

## Arms no input reaches

Each of these is guarded by an earlier check that makes it
unreachable today. They are not tested, because a test would have
to break the guard to reach them. Each is a decision for the
conductor: keep it as a belt, or remove it.

| Where | Why nothing reaches it |
|---|---|
| `pi_health.py:203-204` | `int(.., 16)` after a regex that admits only hex digits |
| `training_watch.py:611-612` | `float()` after a regex that admits only float literals |
| `security.py:226, 228` | `_rx_walk` handles repeats and branches before it calls `_rx_subpatterns` |

## Reproduce

```bash
python3 runner/tools/regression_pass.py --jobs 2 --no-bisect
python3 runner/tools/stdlib_coverage.py --subprocess --jobs 2 --out coverage.json
python3 runner/tools/coverage_gaps.py coverage.json --out gaps.md
```
