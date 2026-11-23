# The rig battery readiness probe: supposition, before the landing

Written 2026-11-22, before any code in this landing was written.
The conclusions section is appended after the tests run, in this
same place, and the change the numbers support follows it.

## What stands

The Windows preview battery kept failing one trio of steps
together: startup, build stamp, and clock. The record of the
diagnosis and the fix stands outside this repository in the rig
harness notes (trio-fix-2026-11-22.md in the falkenstein working
folder), and its measured facts are these. The runner was healthy
on every failing run. On the saturated Germany rig its cold start
took 139.7 to 154.4 seconds to reach the starting line, cold and
warm alike, with and without a Defender exclusion for the test
root. The old driver waited 30 seconds for the log file to exist
and then slept a fixed 6 seconds, so startup failed on a guess,
build stamp failed because its only input is that same log, and
clock failed because its first job sat behind a runner that was
not polling yet. The harness fix replaced the fixed wait with
proven readiness: the starting line carrying the commit under
test, then the file transport watching line, then a probe job
through the real submission path returning a result that meets
the same attestation bar as every battery job, with resubmission
(up to 3 attempts) when a probe envelope never appears. Budget
420 seconds. Clock kept its own 120 second window, unmoved. The
battery then passed all 17 steps twice in a row.

That fix stands only in the harness. Nothing in this repository
carries it, so the next person who rebuilds the driver from the
tree gets the old fixed wait back. This landing is the fix,
carried into the repository own test tooling.

## Where it belongs: the supposition about the shape

S1. The product code has no corresponding fixed wait readiness
path. The runner itself never waits for its own readiness; the
wait lives in whoever starts it and watches it. A search of the
tree for a battery driver or a readiness wait will come back
empty, and the honest home is therefore a tooling module under
runner/tools, beside rig_bank.py and rig_resources.py, with its
tests under runner/tests. If the search does find a product
path, this supposition is wrong and the fix goes there instead.

S2. The readiness decision is pure once its inputs are named:
the log lines, the commit under test, whether the started
process is still alive, and a probe function that submits one
job and reports whether an attested result arrived. A module
shaped that way can be unit tested on any platform, including
this Linux box, with no rig and no PowerShell.

## What the tests will pin

S3. Readiness is never granted by the starting line alone, nor
by the watching line alone, nor by a probe result that fails
the attestation bar. All three stages are required, in order.

S4. A probe envelope that never appears is a transport race,
not a runner verdict: the probe is resubmitted, at most 3
attempts, inside the one overall budget, and readiness fails
when the budget or the attempts run out.

S5. The budget is 420 seconds and the clock job window stays
120 seconds. Both stand as named constants the tests pin, so a
later edit that loosens either one has to change a test on
purpose. No other timeout anywhere is touched by this landing.

S6. If the started process exits, readiness fails at once
rather than burning the budget, and the measured time to
readiness and the probe own latency are reported either way,
the way the harness step detail records ready_in and probe.

## Conclusions

S1 holds. A search of the tree for a battery driver, a
readiness wait, or the harness function names came back empty:
the runner has no readiness path of its own, because the wait
always lived in whoever starts it. The fix therefore lands in
the repository own test tooling, at runner/tools/rig_readiness.py,
beside rig_bank.py and rig_resources.py, with its tests at
runner/tests/test_rig_readiness.py. The rig driver keeps its
PowerShell implementation of the same 3 stages; this module is
the rule stated once, in the tree, in a form any driver can be
checked against.

S2 holds. The decision is implemented as one pure function,
wait_for_readiness, over 4 named inputs: the log text, the
commit under test, a probe function, and an optional liveness
function, with the clock and the sleep injected for the tests.

S3 through S6 hold, pinned by 14 tests, all green. The stages
are required in order and the probe never fires before the
watching line. A probe result that arrives unattested is not
readiness. A missing envelope is resubmitted and stops at 3
attempts, and an attempt that consumes the budget leaves no
room for another. The constants stand at 420 seconds for the
readiness budget, 120 seconds for the clock job window, 3
probe attempts, and 240 seconds for one probe result wait, and
a test pins the function default budget to the named constant.
A dead process fails readiness in about its own exit time
instead of the full budget, and the result carries the measured
time to readiness and the probe latency either way.

The regression guard on the new test file is green on every
check: native, repeat, shuffled, the simulated Windows
surface, leaks, and the registry gates (538 seconds). The
neighbouring rig suites (rig resources, rig bank, and this
one) run 41 tests, all green.

The change the numbers support is the one made: no product
code changed, because no product code held the fault; the
harness rule now stands in the tree with tests, so a driver
rebuilt from the repository carries proven readiness instead
of the fixed wait. The harness proof itself stands as recorded
in the trio notes: all 17 battery steps passed twice in a row
with this readiness shape, production untouched.
