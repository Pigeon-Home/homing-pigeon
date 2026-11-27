# Mutation selection after the F15 landing: supposition

Written 2026-11-27, before the measurements below were run.
Ship 4.0.37.6 failed at the gate. The hosted run is
46023234083 on the 4.0.37.6 release commit. Three jobs
failed, named test, test-macos and test-windows (1), and
the scope, shape and build jobs all passed.

## What the failed logs show

Each of the three failed jobs carries exactly one failing
test, and it is the same test in all three:
test_the_recorded_selection_is_the_derivation in
runner/tests/test_mutation_oracle.py, in the class
RecordedSelectionPinTest. Its message says the recorded
selection in pyproject.toml has rotted, that the derivation
holds 403 modules, and that the recorded list holds 402.
The first differing element is at position 108, where the
derivation holds runner/tests/test_f15_whole_gate.py and
the recorded list holds runner/tests/test_file_names.py.

## S1

The supposition is that the F15 landing is the cause and
that the F15 code itself is sound. That landing added one
new test file, runner/tests/test_f15_whole_gate.py, and
that file loads the mutated file through its import chain,
so the derivation rightly grew by one module. The recorded
list in pyproject.toml was not regenerated in that landing,
so it still holds the 402 modules from before the landing.
Checked by running the mutation oracle tool in check mode
on this tree and by reading its two direction lists: the
only difference is expected to be that one file, in the
derivation and not in the recorded list, with nothing in
the recorded list that the derivation has dropped.

## S2

If S1 holds, the fix the numbers support is to regenerate
the recorded list properly, which in this case means
inserting that one module at its sorted position in the
list in pyproject.toml, and nothing else. No test is
weakened, no derivation rule is changed, and the F15 code
is untouched. Checked by the pin test itself passing after
the change, and by a family of new tests in
runner/tests/test_mutation_oracle.py that pin this exact
shape: a newly landed loader file belongs in both lists,
at its sorted place, with the counts that follow from it.

## S3

If the check mode output shows any difference beyond that
one file, S1 is wrong in part, and the conclusions will
say so plainly and name every extra difference before any
fix is landed.
