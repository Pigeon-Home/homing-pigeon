#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Pins for the phase-2 enforce-posture reconciliation.

The reconciliation, in one paragraph: an unstated security mode
keeps defaulting to enforce -- the shipped default is never
silently weakened. What changes is where that default meets the
test and proof harnesses. Harness configs state the posture they
intend (off or audit for the controls a proof is not about)
instead of relying on unstated defaults on machines with no
confinement backend, where the runtime enforce-refusals --
correct on a real deployment -- refuse the harness's own jobs
and startups before the path under test is reached. And the
audience check refuses a job on a genuine runner mismatch only:
a deployment that has named no runner has nothing to bind to,
so absence is not a refusal, while a job addressed to a
different runner than the configured one is refused loudly and
audited at enforce, exactly as phase 2 landed it.

Each behavior change has a pin here:

- the unstated default stays enforce, for every mode;
- a stated mode is returned exactly as stated;
- the audience job-level semantics: absence allowed at any
  mode, genuine mismatch denied and audited at enforce,
  allowed and audit-logged at audit, addressed job allowed;
- the harness fixtures state their modes: the first-run
  scenario config, the remediation execute-job helpers, and
  the platform-proof / minimal-userland poll configs.

A second round (head 8d43f123) applies the same pattern to
what the first round missed:

- the audience startup refusal at enforce (no runner_id
  configured) stays exactly as landed -- pinned through
  main() itself: unstated refuses with exit 2, stated enforce
  with a runner named starts, audit warns and starts;
- the audit-report flag fixture and the protocol-examples
  rig state their modes, so the startup refusal and the
  confinement refusal stop arriving before the paths those
  tests measure (M3.audit_report and ORACLE.latitude in the
  switch roster);
- every CI smoke config -- the build workflow's Windows
  legs, the docker workflow, the shared POSIX smoke script --
  states audience off beside the platform gates it already
  stated off, since a smoke config names no runner_id.

A third round (head 163b15ff) covers what the first two could
not see: the fixtures that only ever failed where no
confinement backend exists at all. On Linux the bwrap
backend engages, and on Windows the Job Objects backend
does, so an unstated confinement mode -- enforce by default
-- never fired there; on Darwin neither backend exists, so
the refusal arrived ahead of the Oracle paths under test
(ORACLE.alphabet and ORACLE.no_widening in the switch
roster) and ahead of the job-user baseline comparison
(M8.drop on the root leg). The fixtures state the platform
gates they are not about -- confinement, job_user and
audience off -- beside the policy modes that are their
subject, and the M8 baseline states its modes through the
same helper as every other run in its file. One pin below
reproduces the backend-less host directly: with the sandbox
reported unavailable, the four roster-named tests and the
M8 baseline run still pass, because a stated off never
reaches the enforce branch that consults availability.
"""
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.guard import security as sec  # noqa: E402
from runner.wire import verify  # noqa: E402

FEATURES = ("confinement", "job_user", "audience")


class UnstatedModeStaysEnforceTest(unittest.TestCase):
    """The default is the reconciliation's fixed point: nothing
    here may weaken it."""

    def test_empty_config_defaults_every_mode_to_enforce(self):
        for feature in FEATURES:
            self.assertEqual(sec.sec_mode({}, feature), "enforce",
                             feature)

    def test_partial_modes_block_still_defaults_the_rest(self):
        cfg = {"security": {"modes": {"judge": "off"}}}
        for feature in FEATURES:
            self.assertEqual(sec.sec_mode(cfg, feature), "enforce",
                             feature)

    def test_stated_mode_is_returned_exactly(self):
        for stated in ("off", "audit", "enforce"):
            cfg = {"security": {"modes": {"confinement": stated}}}
            self.assertEqual(sec.sec_mode(cfg, "confinement"), stated)


class AudienceAbsenceAndMismatchTest(unittest.TestCase):
    """Job-level audience semantics after the reconciliation:
    refusal fires on a genuine mismatch, never on absence."""

    def _audit(self, base):
        path = os.path.join(base, sec.AUDIT_FILE)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def test_no_runner_named_means_no_binding_and_no_refusal(self):
        # The deployment has not named a runner: enforce reads on
        # the mode, but there is nothing to bind a job to, so a
        # job is not refused -- with or without its own aud claim.
        cfg = {"security": {"modes": {"audience": "enforce"}}}
        with tempfile.TemporaryDirectory() as base:
            self.assertIsNone(verify.check_audience(
                cfg, {"aud": "someone-else"}))
            self.assertTrue(verify.audience_allows(
                cfg, base, {"aud": "someone-else"}, "k", "j-abs-1"))
            self.assertTrue(verify.audience_allows(
                cfg, base, {}, "k", "j-abs-2"))
            denied = [e for e in self._audit(base)
                      if e.get("feature") == "audience"
                      and e.get("decision") == "denied"]
            self.assertEqual(denied, [])

    def test_genuine_mismatch_is_denied_and_audited_at_enforce(self):
        cfg = {"runner_id": "runner-a",
               "security": {"modes": {"audience": "enforce"}}}
        with tempfile.TemporaryDirectory() as base:
            self.assertFalse(verify.audience_allows(
                cfg, base, {"aud": "runner-b"}, "k", "j-mis-1"))
            entries = [e for e in self._audit(base)
                       if e.get("feature") == "audience"]
            self.assertTrue(any(
                e.get("decision") == "denied"
                and e.get("reason") == "runner_id_mismatch"
                for e in entries), entries)

    def test_genuine_mismatch_at_audit_proceeds_and_is_logged(self):
        cfg = {"runner_id": "runner-a",
               "security": {"modes": {"audience": "audit"}}}
        with tempfile.TemporaryDirectory() as base:
            self.assertTrue(verify.audience_allows(
                cfg, base, {"aud": "runner-b"}, "k", "j-mis-2"))
            entries = [e for e in self._audit(base)
                       if e.get("feature") == "audience"]
            self.assertTrue(any(
                e.get("decision") == "would_deny" for e in entries),
                entries)

    def test_job_addressed_to_the_configured_runner_is_allowed(self):
        cfg = {"runner_id": "runner-a",
               "security": {"modes": {"audience": "enforce"}}}
        with tempfile.TemporaryDirectory() as base:
            self.assertTrue(verify.audience_allows(
                cfg, base, {"aud": "runner-a"}, "k", "j-ok-1"))


class HarnessConfigsStateTheirModesTest(unittest.TestCase):
    """The harness seam: a proof config names its posture, so the
    runtime refusals meet a stated intent, not an accident of
    omission."""

    def test_first_run_scenario_config_states_audience(self):
        from runner.tests.test_first_run_scenario import (
            SimulationScenarioTest)
        case = SimulationScenarioTest(
            "test_desktop_flag_redacts_on_the_cli")
        cfg = case._protected_config("/tmp/desk", "/tmp/state")
        modes = cfg["security"]["modes"]
        self.assertEqual(modes["audience"], "off")
        self.assertEqual(modes["confinement"], "off")
        self.assertEqual(modes["job_user"], "off")

    def test_remediation_execute_helpers_state_modes(self):
        from runner.tests import test_remediation as tr
        captured = {}

        def fake_execute_job(cfg, job, base):
            captured.update(cfg)
            return {}

        case = tr.ExecuteJobTest("test_benign_job_is_untouched")
        with mock.patch.object(tr.runner, "execute_job",
                               side_effect=fake_execute_job):
            case._run({}, {"job_id": "pin-1", "kind": "exec",
                           "script": "true"})
        modes = captured["security"]["modes"]
        self.assertEqual(modes["confinement"], "off")
        self.assertEqual(modes["job_user"], "off")
        oracle_cfg = tr.ExecuteJobOracleTest(
            "test_oracle_order_kills")._cfg()
        self.assertEqual(
            oracle_cfg["security"]["modes"]["confinement"], "off")
        self.assertEqual(
            oracle_cfg["security"]["modes"]["job_user"], "off")

    def _captured_poll_cfg(self, module, payload):
        captured = {}

        class Captured(Exception):
            pass

        def fake_poll_once(cfg, *a, **kw):
            captured.update(cfg)
            raise Captured()

        with mock.patch.object(module.runner, "poll_once",
                               side_effect=fake_poll_once):
            with self.assertRaises(Captured):
                module._run(payload)
        return captured

    def test_platform_proof_config_states_its_modes(self):
        from runner.tests import test_platform_proof as tp
        from runner.tests import test_oracle_opinion as oo
        payload = oo._exec_payload(
            interpreter=[sys.executable], script="print('x')")
        cfg = self._captured_poll_cfg(tp, payload)
        modes = cfg["security"]["modes"]
        for feature in FEATURES:
            self.assertEqual(modes[feature], "off", feature)

    def test_minimal_userland_config_states_its_modes(self):
        from runner.tests import test_minimal_userland as mu
        from runner.tests import test_oracle_opinion as oo
        payload = oo._exec_payload(
            interpreter=[sys.executable], script="print('x')")
        cfg = self._captured_poll_cfg(mu, payload)
        modes = cfg["security"]["modes"]
        for feature in FEATURES:
            self.assertEqual(modes[feature], "off", feature)

    def test_audit_report_flag_fixture_states_audience(self):
        # The audit-report flag test drives main() itself, so the
        # startup posture gates run before the dispatch. Its
        # fixture states confinement and job_user off; it must
        # state audience off as well, or the phase-2 startup
        # refusal -- correct on a real deployment -- refuses the
        # test's own startup (2 != 0 at head 8d43f123, identical
        # on every platform it ran on).
        import inspect
        from runner.tests.test_audit_report import FlagIntegrationTest
        src = inspect.getsource(FlagIntegrationTest.test_flag_via_main)
        self.assertIn('"audience": "off"', src)

    def test_protocol_examples_rig_states_its_modes(self):
        # The protocol-examples rig exercises the Oracle's
        # do-not-emit table: the interpreter check must be what
        # refuses a missing binary. Unstated modes default to
        # enforce, so on a machine with no confinement backend
        # the confinement refusal arrived first and the measured
        # string never appeared (ORACLE.latitude at 8d43f123).
        from runner.tests.test_protocol_examples import (
            DoNotEmitTableTest)
        case = DoNotEmitTableTest(
            "test_missing_binary_interpreter_is_rejected_below_repair")
        case.setUp()
        try:
            modes = case.cfg["security"]["modes"]
            self.assertEqual(modes["confinement"], "off")
            self.assertEqual(modes["job_user"], "off")
        finally:
            case.tearDown()

    def test_ci_smoke_configs_state_audience(self):
        # Every smoke config in the build and docker workflows
        # and in the shared POSIX smoke script states confinement
        # off; each must state audience off as well. The smoke
        # configs set no runner_id, so an unstated audience reads
        # enforce and the phase-2 startup refusal legitimately
        # refuses the smoke run before it starts -- the build
        # workflow's platform legs failed at exactly this step.
        cases = [
            (os.path.join(REPO, ".github", "workflows", "build.yml"),
             r"'modes':\s*\{([^}]*)\}", "'audience': 'off'", 2),
            (os.path.join(REPO, ".github", "workflows", "docker.yml"),
             r'"modes":\s*\{([^}]*)\}', '"audience": "off"', 1),
            (os.path.join(REPO, "runner", "tools",
                          "smoke_posix_binaries.sh"),
             r'"modes":\s*\{([^}]*)\}', '"audience": "off"', 1),
        ]
        for path, pattern, needle, minimum in cases:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            blocks = re.findall(pattern, text)
            self.assertGreaterEqual(len(blocks), minimum, path)
            for block in blocks:
                self.assertIn("off", block, (path, block))
                self.assertIn(needle, block, (path, block))


class RoundTwoHarnessStatedModesTest(unittest.TestCase):
    """The second round's fixtures, pinned the same way: every
    harness that drives main() or runs a job states the gates
    it is not about, so the phase-2 refusals -- startup and
    job-level alike -- stop arriving before the path under
    test. Where a harness's subject is the all-enforce posture
    itself, the fixture names the runner instead of lowering
    the mode: the audience gate binds to the name."""

    def test_paging_gate_base_states_audience(self):
        from runner.tests.test_decision1_paging_gate import BASE
        self.assertEqual(BASE["security"]["modes"]["audience"],
                         "off")

    def test_coverage_rig_configs_state_audience(self):
        from runner.tests.test_coverage_resolve import _cfg
        self.assertEqual(
            _cfg()["security"]["modes"]["audience"], "off")
        from runner.tests.test_coverage_seams import RunnerMainTest
        self.assertEqual(
            RunnerMainTest._VALID["security"]["modes"]["audience"],
            "off")

    def test_secdoor_valid_twin_states_audience(self):
        from runner.tests.test_secdoor_gate_audit import (
            BAD_MODES, GOOD_MODES)
        self.assertEqual(GOOD_MODES["modes"]["audience"], "off")
        # The malformed twin keeps its bogus value: it is the
        # shape the gate exists to refuse.
        self.assertEqual(BAD_MODES["modes"]["audience"], "bogus")

    def test_require_posture_base_names_the_runner(self):
        from runner.tests.test_require_posture import BASE
        self.assertTrue(BASE["runner_id"])

    def test_main_driving_fixtures_state_audience_off(self):
        # Source pins, in the build-config style: the stanza
        # must be present in each harness fixed in this round.
        files = [
            "test_cli_options.py", "test_oracle_chat.py",
            "test_oracle_cli.py", "test_oracle_tool_mode.py",
            "test_runner_tail.py", "test_coverage_learnings.py",
            "test_defaults_table_hunt.py",
            "test_proof_conformance_p6.py",
        ]
        for name in files:
            path = os.path.join(REPO, "runner", "tests", name)
            with open(path, encoding="utf-8") as fh:
                self.assertIn('"audience": "off"', fh.read(), name)

    def test_job_running_fixtures_state_their_modes(self):
        for name in ("test_protocol_and_edges.py",
                     "test_extension_poison.py"):
            path = os.path.join(REPO, "runner", "tests", name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn('"confinement": "off"', text, name)
            self.assertIn('"job_user": "off"', text, name)

    def test_conformance_refusal_expectation_matches_phase2(self):
        # The p2 confinement chain pins the landed behavior:
        # enforce with no sandbox refuses, on the record --
        # the fallback wording survives only as the audit
        # record's decision name for that refusal.
        path = os.path.join(REPO, "runner", "tests",
                            "test_proof_conformance_p2.py")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(
            "test_enforce_without_a_sandbox_refuses_on_the_record",
            text)
        self.assertIn("confinement_unavailable", text)

    def test_support_matrix_and_registry_follow_the_landings(self):
        # The matrix's job_user line follows the Job Objects
        # landing, and the defaults registry's doc line for
        # max_job_bytes follows the README as it stands.
        path = os.path.join(REPO, "runner", "tests",
                            "test_support_matrix.py")
        with open(path, encoding="utf-8") as fh:
            self.assertIn(
                "Enforce available via a Job Objects backend",
                fh.read())
        from runner.tests.defaults_registry import ROWS
        row = [r for r in ROWS if r["key"] == "max_job_bytes"][0]
        self.assertEqual(row["doc_line"], 438)


class AudienceStartupRefusalStaysLandedTest(unittest.TestCase):
    """Startup posture, phase 2 as landed: audience at enforce
    with no runner_id refuses to start, before any dispatch.
    The reconciliation moves the harnesses, never this refusal:
    a stated off passes the gate, audit warns and passes, and
    enforce with a runner named passes."""

    def _run_main(self, cfg):
        from runner.runner import main
        with tempfile.TemporaryDirectory() as d:
            cfg = dict(cfg, base_dir=d)
            cfg_path = os.path.join(d, "config.json")
            with open(cfg_path, "w") as fh:
                json.dump(cfg, fh)
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(sys, "argv",
                                   ["runner", "--config", cfg_path,
                                    "--audit-report", "--since", "14d"]):
                with redirect_stdout(out), redirect_stderr(err):
                    rc = main()
            return rc, err.getvalue()

    def test_unstated_audience_refuses_startup_without_runner_id(self):
        rc, err = self._run_main({"security": {"modes": {
            "confinement": "off", "job_user": "off"}}})
        self.assertEqual(rc, 2)
        self.assertIn("security.modes.audience is enforce but no "
                      "runner_id is configured", err)

    def test_stated_enforce_audience_with_runner_id_starts(self):
        rc, _ = self._run_main({"runner_id": "pin-runner",
                                "security": {"modes": {
                                    "confinement": "off",
                                    "job_user": "off",
                                    "audience": "enforce"}}})
        self.assertEqual(rc, 0)

    def test_audit_audience_without_runner_id_warns_and_starts(self):
        rc, _ = self._run_main({"security": {"modes": {
            "confinement": "off", "job_user": "off",
            "audience": "audit"}}})
        self.assertEqual(rc, 0)


class RoundThreeBackendLessFixturesTest(unittest.TestCase):
    """Round three: the Oracle alphabet / no-widening fixtures
    and the M8 job-user baseline state the platform gates, so
    a host with no confinement backend (Darwin, in the switch
    roster) stops refusing their jobs ahead of the paths under
    test. The policy modes stay exactly as each fixture states
    them -- they are the subject; the platform gates are not."""

    GATES = ("confinement", "job_user", "audience")

    def test_alphabet_model_fixture_states_the_platform_gates(self):
        from runner.tests.test_oracle_alphabet import model_cfg
        modes = model_cfg("advise")["security"]["modes"]
        for gate in self.GATES:
            self.assertEqual(modes[gate], "off", gate)

    def test_alphabet_policy_fixture_states_gates_beside_policy(self):
        from runner.tests.test_oracle_alphabet import PolicyAxisTest
        case = PolicyAxisTest("test_policy_modes_are_note_proof")
        modes = case._cfg("enforce", False)["security"]["modes"]
        self.assertEqual(modes["policy_env"], "enforce")
        for gate in self.GATES:
            self.assertEqual(modes[gate], "off", gate)

    def test_no_widening_key_fixture_states_the_platform_gates(self):
        from runner.tests.test_oracle_no_widening import key_cfg
        modes = key_cfg()["security"]["modes"]
        for gate in self.GATES:
            self.assertEqual(modes[gate], "off", gate)

    def test_no_widening_denial_fixture_states_confinement(self):
        # The one no-widening test that replaces the security
        # block wholesale states the gates in its own stanza,
        # so its denial is the policy's on every host, never
        # the confinement gate's on a backend-less one.
        import inspect
        from runner.tests.test_oracle_no_widening import (
            NoWideningTest)
        src = inspect.getsource(
            NoWideningTest.test_a_policy_denial_never_reaches_the_opinion)
        for gate in self.GATES:
            self.assertIn('"%s": "off"' % gate, src, gate)

    def test_no_widening_note_fixture_states_the_platform_gates(self):
        # The note test builds its config literally, not
        # through key_cfg; its stanza states the gates too.
        import inspect
        from runner.tests.test_oracle_no_widening import (
            NoWideningTest)
        src = inspect.getsource(
            NoWideningTest.test_a_model_note_never_changes_an_outcome)
        for gate in self.GATES:
            self.assertIn('"%s": "off"' % gate, src, gate)

    def test_job_user_baseline_states_its_modes(self):
        # M8.drop's comparison baseline ran with an empty
        # config: unstated, its own run is refused on a
        # backend-less host before the comparison can start.
        # The baseline states its modes through _ju like every
        # other run in the file.
        path = os.path.join(REPO, "runner", "tests",
                            "test_secret_files_job_user.py")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('_run(_ju("off"), _job("m8-c1"', text)
        self.assertNotIn("_run({}, ", text)

    def test_backend_less_host_still_runs_the_fixtures(self):
        # The Darwin condition, reproduced on any host: the
        # sandbox reports unavailable. The four tests the
        # switch roster named on the macOS legs, plus the M8
        # baseline call shape, must still run their jobs --
        # a stated off never consults availability.
        from runner.tests import test_secret_files_job_user as ju
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for name in (
                "runner.tests.test_oracle_alphabet.AlphabetTest."
                "test_tier1_findings_mean_the_model_is_never_asked",
                "runner.tests.test_oracle_alphabet.PolicyAxisTest."
                "test_policy_modes_are_note_proof",
                "runner.tests.test_oracle_no_widening.NoWideningTest."
                "test_a_model_note_never_changes_an_outcome",
                "runner.tests.test_oracle_no_widening.NoWideningTest."
                "test_a_repair_never_launders_a_policy_denial"):
            suite.addTests(loader.loadTestsFromName(name))
        with mock.patch.object(runner._sandbox, "sandbox_available",
                               return_value=False):
            result = unittest.TextTestRunner(
                stream=io.StringIO()).run(suite)
            baseline, _audit = ju._run(
                ju._ju("off"), ju._job("m8-c1", "print(6 * 7)"))
        self.assertTrue(result.wasSuccessful(),
                        [str(f[0]) for f in
                         result.failures + result.errors])
        self.assertEqual(baseline["exit_code"], 0)
        self.assertEqual(baseline["stdout"].strip(), "42")


if __name__ == "__main__":
    unittest.main(verbosity=2)
