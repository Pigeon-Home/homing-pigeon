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

Measured 2026-11-16, after the supposition above stood on main.

1. **Supposition 1 stands, exactly.** The leg's substance,
   reproduced at the head the supposition landed on — the
   module run with HP_MINIMAL_USERLAND=1 on a PATH carrying sh
   and no bash and no zsh — failed the same 2 tests on the
   same assertions ('pigeon-42' not found in '', 'coo-Linux'
   not found in ''), and passed the other 4. This machine has
   no docker, so the reproduction ran under a curated PATH
   (sh is dash here, ash in the image; both are the platform
   default the repair moves a job onto, and the module drives
   the same poll_once path either way).
2. **Supposition 2 stands: the defect is the fixture, and the
   fix is the fixture.** The fixture's config now states the
   full ceiling (max_result_view) and its jobs ask for the
   full view (result_policy {"view": "full"}) unless a test
   says otherwise — the reconciled shape the other read-back
   fixtures took when the attested default landed. No runner
   code changed. After the fix the module runs 7 tests, all
   OK, and the workflow's own guard step (skip_guard.py
   --no-skips --require-ok --annotate over the suite output)
   exits 0 with no skips seen.
3. **Supposition 3 stands, and is now pinned.** A new test,
   test_no_view_ask_still_delivers_attested, runs a repaired
   job in the same fixture with no view ask: exit 0, repaired
   true, the result's view reads attested and its stdout is
   blanked. The fixture's ask widens nothing by default; a
   future change that widened the runner's default instead
   of the fixture's ask would fail this test.

Neighbouring suites at the same head: test_oracle_opinion,
test_default_posture and the module's normal-box run together
ran 113 tests, OK; test_enforce_posture_reconciliation, which
reads this fixture's stated config, ran 56 tests, OK.

The hosted leg's own verdict comes at its next dispatch (the
nightly, or the next tag whose tree changed under runner/);
the local green above is the leg's substance run the way the
workflow runs it.
