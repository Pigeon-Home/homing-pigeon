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

Measured on 2026-11-25, on this project's own Menlo Park
machine with its standing suite lanes running beside the
measurement (load average between 1 and 16 across the runs,
on 1.5 shared cores), and set against the CI failure above.

The shape read itself, timed directly on a ladder of line
ends: at 610 bytes the old patterns took 118.6 times the CPU
of a plain text of the same size, and the CPU ratio grew with
the size, 196.2 at 987 bytes, 294.1 at 1,597, 523.1 at 2,584,
843.4 at 4,181, 858.7 at 6,765 and 2,465.2 at 10,946. Through
the whole gate at fixed steps, the old patterns took 45.0
times the CPU of a plain script at step 19 (4,181 bytes) and
104.6 times at step 20 (6,765 bytes, the size at which the CI
failure stopped). Against that, the wall ratio in the CI
failure was 6.1. The supposition held for the clock: the work
ratio stands far above 10 on the CPU clock at the very size
where the wall ratio collapsed below it.

The measurement also showed a second effect the supposition
did not state. A climb on the loaded machine stopped the old
patterns at step 15, 610 bytes, on its wall clock forecast,
and at that size the gate's fixed costs still dominate: the
CPU ratio through the gate there was about 3. The stopping
step itself moves with the load, so resting the decision on
the stopping step, on any clock, asks the question at a size
the load chooses. The decision therefore also moved, to
fixed steps whose size is the same on every machine.

The change the numbers support, and the change made in
runner/tests/test_v4_the_ladder_run.py alongside this
conclusion:

1. inside_the_gate now reports both clocks, each at its own
   best of the repeats, and gate_ladder rows carry both.
2. gate_ladder can climb on the CPU clock (a new clock
   argument, defaulting to the wall clock, so every other
   climb in the file is unchanged): the budget and the
   forecast then judge the work of a step, not its waiting.
3. The F14 test's 3 climbs run on the CPU clock, with the
   half second budget read as half a second of work.
4. The 10 times decision is taken at fixed steps 19 and 20
   on the CPU clock, the plain side from the plain climb's
   own rows and the old side from one arrival at each step.
5. A new family, TheLadderWorkOnTheCpuClock, pins the same
   decision at fixed steps through the whole gate, the
   square growth of the shape read itself, the clock property
   the decision rests on (a sleep fills the wall clock and
   leaves the CPU clock near empty), and the CPU reading
   helper's behaviour where the wall ratios have collapsed.
6. The regression guard's repeat check then caught the same
   disease in the gate class's other proportion test,
   test_the_gate_reads_a_script_in_proportion, whose wall
   reading reached 1.42 against its 1.35 bar in a repeat run;
   the unmodified tree failed that test in these conditions
   too (a climb stopped at step 22 by the wall forecast), so
   its climbs run on the CPU clock as well, for the same
   reason: the proportion it asserts is a law of the work.

Verification, all on the loaded machine above: before the
change, the F14 test failed repeatedly in these conditions
(the wall proportion at the stopping step, the good climbs
stopped short of the top by the wall forecast and the wall
budget, at steps 21 to 23). After the change, the F14 test
passed 6 runs out of 6 in the same conditions, and the gate
class together with the new family passed 8 tests out of 8.
The regression guard on this file (1 repeat, 1 shuffle, no
simulator or leak checks, which this machine cannot finish
in reasonable time) reported: native green, 34 tests, 0
failures; shuffled green; gates green, 14 registry tests;
core green; and the repeat check red on the proportion test
named in point 6, which is what point 6 answers. What this
does not claim: the wall clock climbs elsewhere in the file
keep the wall budget semantics they always had, and a
machine loaded far beyond its cores can still move them;
the release gate's own runners are not loaded that way, and
the one assertion that ever failed there is the one fixed
here.
