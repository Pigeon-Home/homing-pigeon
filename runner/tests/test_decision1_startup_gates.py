#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup: the mechanism gates, the strict
shape, and the phase-2 startup gates.

Split from runner/tests/test_decision1_startup.py in
the Q136 follow-on file split (2026-11-11); the tests
are moved verbatim, not rewritten. This piece carries
RefuseStartupGatesTest, StrictShapeTest and
Phase2StartupTest.
"""
import os
import sys
import json
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as RR  # noqa: E402
from runner.guard import sandbox as _sandbox  # noqa: E402
from runner.guard.security import FEATURES  # noqa: E402
from runner.ops import remediation_ops as REM  # noqa: E402
from runner.tests.decision1_startup_support import (  # noqa: E402
    STRONG_SECRET, _backend_cannot_engage, _backend_stub,
    run_main)


class RefuseStartupGatesTest(unittest.TestCase):
    """The two mechanism gates in main(): a security mode at
    enforce whose mechanism cannot engage on this machine is the
    refuse class in its purest form (Q9)."""

    def test_confinement_enforce_refused_when_sandbox_cannot_engage(self):
        if _sandbox.startup_problem() is None:
            self.skipTest("sandbox engages on this machine "
                          "(startup probe)")
        rc, _out, err = run_main(
            {"security": {"modes": {"confinement": "enforce"}}})
        self.assertEqual(rc, 2, err)
        self.assertIn("confinement", err)

    def test_job_user_enforce_gate_names_job_user_on_windows(self):
        cfg = {"security": {"modes": {"job_user": "enforce"}}}
        with mock.patch.object(
                REM, "_windows_confine",
                lambda backend=None: _backend_stub()):
            problem = RR._job_user_startup_problem(cfg, platform="win32")
        self.assertIsNotNone(problem)
        self.assertIn("job_user", problem)
        # The same config on a POSIX platform has no such problem:
        # the demote exists there.
        self.assertIsNone(
            RR._job_user_startup_problem(cfg, platform="linux"))
        # And with the mode off there is nothing to gate anywhere.
        off = {"security": {"modes": {"job_user": "off"}}}
        self.assertIsNone(
            RR._job_user_startup_problem(off, platform="win32"))

    def test_job_user_nonexistent_user_refused_at_startup(self):
        if os.name == "nt":
            self.skipTest("POSIX only")
        rc, _out, err = run_main(
            {"security": {"job_user": {"user": "hp-no-such-user-zz9"}}})
        self.assertEqual(rc, 2, err)
        self.assertIn("job_user", err)

    def test_job_user_enforce_refused_at_startup_when_not_root(self):
        # Q132: a POSIX runner that is not root cannot apply the
        # demote at all, so enforce refuses at startup rather than
        # starting and falling back per job. A root process can
        # demote, so the refusal cannot fire for one; the gate's
        # branches are pinned at the function in
        # test_security_config.
        if os.name == "nt":
            self.skipTest("POSIX only")
        if os.geteuid() == 0:
            self.skipTest(
                "the job_user root refusal needs a non-root process")
        import pwd
        user = pwd.getpwuid(os.geteuid()).pw_name
        rc, _out, err = run_main({"security": {
            "modes": {"confinement": "off", "job_user": "enforce"},
            "job_user": {"user": user}}})
        self.assertEqual(rc, 2, err)
        self.assertIn("job_user", err)
        self.assertIn("root", err)

    def test_world_readable_secret_file_refused_at_startup(self):
        # The written M8 rule (Q131, 2026-11-06): a missing or
        # world-readable secret file refuses startup. The missing
        # half already refused; the world-readable half is the
        # same class -- a wrong value about what the runner
        # protects -- so it refuses through main() itself, exit
        # 2, naming the key and the reason on stderr.
        if os.name == "nt":
            self.skipTest("POSIX only")
        tmpdir = tempfile.mkdtemp(prefix="hp-d1-secret-")
        path = os.path.join(tmpdir, "secret")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(STRONG_SECRET + "\n")
        os.chmod(path, 0o644)
        rc, _out, err = run_main(
            {"shared_secret": "", "shared_secret_file": path})
        self.assertEqual(rc, 2, err)
        self.assertIn("shared_secret_file", err)
        self.assertIn("world-readable", err)


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

    def test_confinement_enforce_with_a_dead_backend_refuses_startup(self):
        # The Linux-side analogue of the win32 pair, constructed
        # through the scripted startup_problem so it constructs on
        # hosts whose sandbox works too: the backend answer is the
        # environment, and an environment that cannot enforce is a
        # refusal on any platform.
        rc, out, err = run_main(
            {"security": {"modes": {"confinement": "enforce",
                                    "job_user": "off"}}},
            ("--audit-report",),
            sandbox_problem="bwrap is not installed (not found on PATH)")
        self.assertEqual(rc, 2, err)
        self.assertIn("security.modes.confinement", err)
        self.assertIn("bwrap is not installed", err)
        self.assertNotIn("Security audit report", out)

    def test_all_enforce_on_win32_refuses_and_names_a_mode(self):
        # The locked-down posture as a whole on an incapable
        # platform: whichever gate fires first, the startup is a
        # refusal naming a security mode, never a degraded start.
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
