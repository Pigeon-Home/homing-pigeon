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
"""
import json
import os
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
