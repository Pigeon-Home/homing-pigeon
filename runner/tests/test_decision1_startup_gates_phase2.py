#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup: the phase-2 startup gates.

Split from runner/tests/test_decision1_startup_gates.py
in the Q136 follow-on further split (2026-11-11); the
tests are moved verbatim, not rewritten. This piece
carries Phase2StartupTest.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.tests.decision1_startup_support import run_main  # noqa: E402


class Phase2StartupTest(unittest.TestCase):
    """Phase 2 of the default-posture work, at the startup gates.

    Audience at enforce with no runner_id joins the refusal
    class: the check has nothing to bind to, so startup refuses
    naming the mode and the missing key, instead of warning once
    and skipping the check for every job. Audit keeps the
    warning. And job_user at enforce with no user named is named
    in the startup record as not engaged -- startup proceeds
    (a user can be named later), but the state is stated, never
    silent.
    """

    def test_audience_enforce_without_runner_id_refuses(self):
        rc, out, err = run_main(
            {"runner_id": None,
             "security": {"modes": {"confinement": "off",
                                    "job_user": "off",
                                    "audience": "enforce"}}},
            ("--audit-report",))
        self.assertEqual(rc, 2, err)
        self.assertIn("security.modes.audience", err)
        self.assertIn("runner_id", err)
        self.assertNotIn("Security audit report", out)

    def test_audience_unset_without_runner_id_refuses(self):
        # An unset audience mode reads enforce, so a config that
        # never mentions audience and names no runner_id refuses
        # the same way -- the default is the refusal's trigger,
        # not an escape from it.
        rc, out, err = run_main(
            {"runner_id": None,
             "security": {"modes": {"confinement": "off",
                                    "job_user": "off"}}},
            ("--audit-report",))
        self.assertEqual(rc, 2, err)
        self.assertIn("security.modes.audience", err)

    def test_audience_enforce_with_runner_id_starts(self):
        rc, out, err = run_main(
            {"security": {"modes": {"confinement": "off",
                                    "job_user": "off",
                                    "audience": "enforce"}}},
            ("--audit-report",))
        self.assertEqual(rc, 0, err)
        self.assertIn("Security audit report", out)

    def test_audience_audit_without_runner_id_warns_and_starts(self):
        rc, out, err = run_main(
            {"runner_id": None,
             "security": {"modes": {"confinement": "off",
                                    "job_user": "off",
                                    "audience": "audit"}}},
            ("--audit-report",))
        self.assertEqual(rc, 0, err)
        self.assertIn("Security audit report", out)
        self.assertIn("no runner_id is configured", out)

    def test_audience_off_without_runner_id_starts_quietly(self):
        rc, out, err = run_main(
            {"runner_id": None,
             "security": {"modes": {"confinement": "off",
                                    "job_user": "off",
                                    "audience": "off"}}},
            ("--audit-report",))
        self.assertEqual(rc, 0, err)
        self.assertIn("Security audit report", out)
        self.assertNotIn("no runner_id is configured", out)

    def test_job_user_enforce_without_a_user_is_named_not_engaged(self):
        rc, out, err = run_main(
            {"security": {"modes": {"confinement": "off",
                                    "job_user": "enforce"}}},
            ("--audit-report",))
        self.assertEqual(rc, 0, err)
        self.assertIn("Security audit report", out)
        self.assertIn("job_user is enforce but", out)
        self.assertIn("not engaged", out)

    def test_job_user_enforce_with_a_user_is_not_named(self):
        # A named user on this host is a startup matter of its
        # own (the Q132 gate: root and resolvability); what this
        # leg pins is only that the not-engaged naming stays off
        # when a user is named. The platform gate is scripted
        # away by running the one-shot on a config whose other
        # gates are off and accepting either startup outcome.
        rc, out, err = run_main(
            {"security": {"modes": {"confinement": "off",
                                    "job_user": "enforce"},
                          "job_user": {"user": "root"}}},
            ("--audit-report",))
        self.assertNotIn("not engaged", out)
        self.assertNotIn("not engaged", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
