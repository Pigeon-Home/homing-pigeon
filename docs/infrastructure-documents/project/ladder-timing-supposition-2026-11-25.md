# The ladder timing proportion: supposition

Written 2026-11-25, before the measurement below was run. The
conclusions section is appended after the measurement, in this
same place, and the change the numbers support follows it.

## What stands

On 2026-11-25 the main build for release 3.18.35.19 failed on
one job only, test-windows (1), on one test only:
test_the_ladder_finds_f14_with_nobody_pointing_at_it in
runner/tests/test_v4_the_ladder_run.py. The failing line asks
that the old reader patterns, at the step where their own
forecast stops the climb, have taken more than 10 times as long
inside the gate as a plain script at the same step. The numbers
in the failure: 0.44140870000001087 not greater than
0.7265439999991941, a ratio of about 6.1 where the test asks
for more than 10. A rerun of the failed jobs on 2026-11-25
passed, and the release range in flight touches no ladder code
at all. The same timing proportion shape spent releases in the
3.18.34 line earlier in November 2026 (the numbers 12, 14, 15,
16, 17 and 18 of that line), so a green rerun is not a fix: the
assertion itself is the suspect.

## How the number is made today

inside_the_gate times one arrival with time.perf_counter, the
wall clock, and keeps the best of 3 arrivals. gate_ladder
carries that wall time in each row as its inside figure, and
the failing assertion compares one such wall figure for the
old patterns against one such wall figure for the plain script,
each the best of a small number of arrivals at one step.

## The supposition

The work the old patterns do at that step is real and large:
the test's own comment records ratios of 58 to 93, measured
quiet and under load, at the time the comment was written. What
the wall clock adds on top of the work is waiting: time when
this process holds no core because the machine's cores are all
busy with the other shards and suites running beside it.
Waiting is roughly additive. It lands on both sides of the
comparison, and it is proportionally far larger for the plain
script, whose true work at that step is small, than for the
old patterns, whose true work is large. So under sustained
load the wall ratio is squeezed toward 1, not because the work
shrank but because the waiting grew, and a fixed bar of 10 on
the wall ratio fails whenever the waiting at that moment is
large enough. The failure ratio of about 6.1, against recorded
quiet ratios of 58 to 93, is the shape this supposition
predicts.

Process CPU time, time.process_time in Python, counts only the
time this process spent running, on the core, in user and
system mode. It does not count waiting. The supposition is
therefore testable: measure the same arrivals both ways, wall
and CPU, quiet and under load, and the CPU ratio at the
stopping step will stand well above 10 in the same runs where
the wall ratio falls below it, while the CPU ratio and the
wall ratio agree, roughly, when the machine is quiet.

## The decision rule, stated before the measurement

If the CPU ratio holds above 10 with a wide margin in runs
where the wall ratio collapses, the fix the numbers support
is to carry CPU time through the gate ladder rows beside the
wall time, and to rest the 10 times comparison, which is a
claim about work, on the CPU figure. The wall figure keeps
the job it is suited for: the climb's budget, which is a
claim about how long a climb may take, in wall time, before
it stops. If the CPU ratio collapses too, this supposition
is wrong, no such change is made, and the hunt moves to the
counts the gate itself reports.

## Conclusions

(Appended after the measurement.)
