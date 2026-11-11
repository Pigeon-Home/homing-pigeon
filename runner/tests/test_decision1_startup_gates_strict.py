#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup: enforce means enforce, the
strict shape.

Split from runner/tests/test_decision1_startup_gates.py
in the Q136 follow-on further split (2026-11-11); the
tests are moved with their assertions unchanged, and
the constructions Q136-GATES2-S5 prescribes are
scripted there. This piece carries StrictShapeTest.
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

from runner import runner as RR  # noqa: E402
from runner.guard.security import FEATURES  # noqa: E402
from runner.ops import remediation_ops as REM  # noqa: E402
from runner.tests.decision1_startup_support import (  # noqa: E402
    _backend_cannot_engage, run_main, scripted_confinement)


class StrictShapeTest(unittest.TestCase):
    """Enforce means enforce on every platform (2026-11-03).

    One test per mode per cannot-enforce condition that can be
    honestly constructed, each through main() itself: the startup
    refuses (exit 2), the refusal names the mode and the key, and
    the runner does not proceed in any degraded form -- the
    --audit-report one-shot argv is passed precisely so that a
    step-down would show up as a successful report (exit 0)
    instead of the refusal. The other gate's mode is set off
    explicitly in each config, so each test names the one mode it
    is about, whichever way unset modes are read.

    The cannot-enforce conditions that exist in the code today:
    confinement is Linux+bwrap only (a non-Linux platform, and a
    Linux host whose sandbox backend cannot engage, are two
    distinct conditions), and job_user's setuid demote is
    POSIX-only. policy_env, policy_files, policy_args and
    audience are pure config checks with no platform condition;
    for them the strict pin is the decision-point negative below,
    which covers every feature.
    """

    def test_confinement_enforce_on_win32_refuses_startup(self):
        with mock.patch.object(
                REM, "_windows_confine",
                lambda backend=None: _backend_cannot_engage()):
            rc, out, err = run_main(
                {"security": {"modes": {"confinement": "enforce",
                                        "job_user": "off"}}},
                ("--audit-report",), platform="win32")
        self.assertEqual(rc, 2, err)
        self.assertIn("security.modes.confinement", err)
        self.assertNotIn("Security audit report", out)

    def test_job_user_enforce_on_win32_refuses_startup(self):
        with mock.patch.object(
                REM, "_windows_confine",
                lambda backend=None: _backend_cannot_engage()):
            rc, out, err = run_main(
                {"security": {"modes": {"job_user": "enforce",
                                        "confinement": "off"},
                              "job_user": {"user": "root"}}},
                ("--audit-report",), platform="win32")
        self.assertEqual(rc, 2, err)
        self.assertIn("security.modes.job_user", err)
        self.assertNotIn("Security audit report", out)

    # The dead-backend construction (Q159). The startup gate
    # routes by the host's platform -- win32, FreeBSD and
    # darwin ask their platform backend's probe, only the
    # Linux branch asks the bwrap seam -- so this test's first
    # shape, which scripted the bwrap seam alone, was never
    # consulted on a Windows or macOS host: the live platform
    # backend engaged, the startup proceeded, and the test
    # failed 0 != 2 on real Windows (and, where the macOS
    # backend's own trial failed, refused with the darwin
    # wording the bwrap assertion could not match). The
    # product refuses correctly on every platform when the
    # backend is dead on the seam that platform consults;
    # the construction now scripts every seam at once through
    # scripted_confinement, with one scripted problem text, so
    # the refusal and the text it carries are the same on any
    # host -- and the assertion on the scripted text is the
    # pass-through pin: a seam the scripting missed answers in
    # its own words (or engages), and the test fails either
    # way instead of silently passing.
    DEAD_BACKEND = "backend cannot engage (scripted dead backend)"

    def test_confinement_enforce_with_a_dead_backend_refuses_startup(self):
        # The analogue of the win32 pair on the host's own
        # platform, constructed through the scripted seams so
        # it constructs on hosts whose sandbox works too: the
        # backend answer is the environment, and an environment
        # that cannot enforce is a refusal on any platform.
        with scripted_confinement(self.DEAD_BACKEND):
            rc, out, err = run_main(
                {"security": {"modes": {"confinement": "enforce",
                                        "job_user": "off"}}},
                ("--audit-report",),
                sandbox_problem=self.DEAD_BACKEND)
        self.assertEqual(rc, 2, err)
        self.assertIn("security.modes.confinement", err)
        self.assertIn(self.DEAD_BACKEND, err)
        self.assertNotIn("Security audit report", out)

    def test_confinement_enforce_dead_backend_refuses_on_each_platform(self):
        # The same construction through each simulated
        # platform shape in turn, so the per-platform routing
        # itself is pinned on any host: whichever branch the
        # platform selects, a dead backend on that branch's
        # seam refuses, naming the mode and carrying the
        # scripted problem through.
        for platform in ("linux", "win32", "darwin", "freebsd14"):
            with self.subTest(platform=platform):
                with scripted_confinement(self.DEAD_BACKEND):
                    rc, out, err = run_main(
                        {"security": {"modes":
                                      {"confinement": "enforce",
                                       "job_user": "off"}}},
                        ("--audit-report",), platform=platform,
                        sandbox_problem=self.DEAD_BACKEND)
                self.assertEqual(rc, 2, err)
                self.assertIn("security.modes.confinement", err)
                self.assertIn(self.DEAD_BACKEND, err)
                self.assertNotIn("Security audit report", out)

    def test_confinement_enforce_live_backend_starts_on_each_platform(self):
        # The control for the pair above, per platform: a
        # backend that can engage on the seam the platform
        # consults lets the same enforce startup proceed to
        # the audit report, so the refusal pins cannot pass
        # by refusing everything.
        for platform in ("linux", "win32", "darwin", "freebsd14"):
            with self.subTest(platform=platform):
                with scripted_confinement(None):
                    rc, out, err = run_main(
                        {"security": {"modes":
                                      {"confinement": "enforce",
                                       "job_user": "off"}}},
                        ("--audit-report",), platform=platform)
                self.assertEqual(rc, 0, err)
                self.assertIn("Security audit report", out)

    def test_all_enforce_on_win32_refuses_and_names_a_mode(self):
        # The locked-down posture as a whole on an incapable
        # platform: whichever gate fires first, the startup is a
        # refusal naming a security mode, never a degraded start.
        with mock.patch.object(
                REM, "_windows_confine",
                lambda backend=None: _backend_cannot_engage()):
            rc, out, err = run_main(
                {"security": {"modes": {f: "enforce" for f in FEATURES},
                              "job_user": {"user": "root"}}},
                ("--audit-report",), platform="win32")
        self.assertEqual(rc, 2, err)
        self.assertIn("config error: security.modes.", err)
        self.assertNotIn("Security audit report", out)

    def test_no_platform_steps_enforce_down_at_the_decision_point(self):
        # The negative, per feature, on both platform shapes:
        # mode resolution is platform-independent (a configured
        # "enforce" reads "enforce" everywhere), and sec_decide at
        # enforce denies -- it never allows the way audit does and
        # never writes audit's would_* entry. A code path that
        # stepped enforce down to audit on an incapable platform
        # would have to pass through this one decision point, and
        # it would fail here.
        S = RR._security
        for feature in FEATURES:
            cfg = {"security": {"modes": {feature: "enforce"}}}
            for platform in ("linux", "win32"):
                with self.subTest(feature=feature, platform=platform):
                    with mock.patch.object(sys, "platform", platform):
                        self.assertEqual(
                            S.sec_mode(cfg, feature), "enforce")
                        with tempfile.TemporaryDirectory() as d:
                            self.assertFalse(S.sec_decide(
                                cfg, d, feature, "violation",
                                {"key_id": "k", "job_id": "j"}))
                            with open(os.path.join(
                                    d, S.AUDIT_FILE)) as fh:
                                lines = fh.readlines()
                            self.assertEqual(len(lines), 1)
                            entry = json.loads(lines[0])
                            self.assertEqual(entry["decision"], "denied")
                            self.assertEqual(entry["mode"], "enforce")

    def test_audit_and_off_are_unchanged_by_the_platform(self):
        # The control pair for the negative above: the step-down
        # pin would be meaningless if every mode denied. Audit
        # still allows and logs would_deny, off still allows
        # silently, on the simulated incapable platform too --
        # those are the operator's explicit choices, not a
        # platform's substitution for enforce.
        S = RR._security
        with mock.patch.object(sys, "platform", "win32"):
            with tempfile.TemporaryDirectory() as d:
                audit_cfg = {"security": {"modes":
                                          {"policy_env": "audit"}}}
                self.assertTrue(S.sec_decide(
                    audit_cfg, d, "policy_env", "violation", {}))
                with open(os.path.join(d, S.AUDIT_FILE)) as fh:
                    entry = json.loads(fh.readline())
                self.assertEqual(entry["decision"], "would_deny")
            with tempfile.TemporaryDirectory() as d:
                off_cfg = {"security": {"modes":
                                        {"policy_env": "off"}}}
                self.assertTrue(S.sec_decide(
                    off_cfg, d, "policy_env", "violation", {}))
                self.assertFalse(os.path.exists(
                    os.path.join(d, S.AUDIT_FILE)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
