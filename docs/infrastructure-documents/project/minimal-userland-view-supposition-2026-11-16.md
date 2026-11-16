# The minimal-userland leg and the attested default: supposition

Written 2026-11-16, before the reproduction below was run. The
conclusions section is appended after the measurement, in this
same place, and the change the numbers support follows it.

## What stands

The minimal-userland workflow (the README badge) has failed every
run since the v3.16.26.2 tag build (2026-11-14 13:15 UTC). Its
last success is the v3.16.25.20 tag build (2026-11-14 04:05 UTC).
The build workflow on main is green over the same span, so the
tree's main suite does not see this failure: the module under
test, runner/tests/test_minimal_userland.py, runs only inside
the .github/docker/minimal-userland image.

The failing run's log (v3.16.26.34 tag build, both architectures)
shows the repair itself working: the oracle opinion repaired the
interpreter to the platform default, the job ran under sh, and
the runner's own log records exit=0 with the expected output.
The two failing tests are the ones that read the delivered
result back and look for that output in its stdout member:

- test_bash_job_is_repaired_and_runs: 'pigeon-42' not found in ''
- test_posix_shaped_job_is_repaired_and_runs: 'coo-Linux' not
  found in ''

The exit code the tests read back is 0. Only the output bytes
are missing.

## The suspect change

Between the last green tag and the first red one, the result-view
default changed: the posture item 6 landing (2026-11-14 08:34
UTC, "the result-view default reads attested everywhere it
stands") made every fallback in runner/ops/policy.py read
attested. Under the attested view, apply_result_policy sets the
result's stdout and stderr to "" and carries attestations
instead; output bytes ride a result only at the full view, and
the full view only when the job asks for it
(result_policy {"view": "full"}) under an owner ceiling
(max_result_view) that allows it.

That landing reconciled the harness fixtures that read their
output back: they ask for the full view explicitly under a full
ceiling (the shape stands in runner/tests/test_runner.py and
runner/tests/security_parity.py, among others). The
minimal-userland fixture was not reconciled: its config states
no ceiling and its jobs ask for no view, so since that landing
its repaired jobs run, exit 0, and deliver a result whose stdout
is blanked by design.

## Supposition

1. Reproducing the leg's substance at the current head — the
   module run with HP_MINIMAL_USERLAND=1 on a PATH with sh but
   no bash and no zsh — fails exactly the same 2 tests, with
   '' for stdout, and passes the other 4.
2. The defect is in the fixture, not the runner: stating the
   full ceiling in the fixture's config and the full view ask
   on its jobs — the reconciled shape the other read-back
   fixtures take — makes all of the module's tests pass with
   no change to runner code.
3. The default holds while it happens: a repaired job in the
   same fixture that asks for no view still delivers exit 0
   with stdout blanked and the attested view named, so the
   fix widens nothing by default.

## Conclusions

(Appended after the measurement.)
