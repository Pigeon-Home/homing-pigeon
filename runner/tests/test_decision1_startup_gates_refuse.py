#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup: the mechanism gates in main().

Split from runner/tests/test_decision1_startup_gates.py
in the Q136 follow-on further split (2026-11-11); the
tests are moved with their assertions unchanged, and
the one construction Q136-GATES2-S5 prescribes is
scripted there. This piece carries
RefuseStartupGatesTest.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as RR  # noqa: E402
from runner.guard import sandbox as _sandbox  # noqa: E402
from runner.ops import remediation_ops as REM  # noqa: E402
from runner.tests.decision1_startup_support import (  # noqa: E402
    STRONG_SECRET, _backend_cannot_engage, _backend_stub,
    run_main, scripted_confinement)


class RefuseStartupGatesTest(unittest.TestCase):
    """The two mechanism gates in main(): a security mode at
    enforce whose mechanism cannot engage on this machine is the
    refuse class in its purest form (Q9)."""

    # The dead-backend text this family scripts on every
    # confinement seam at once (scripted_confinement, the
    # Q159 construction): the refusal must carry it through
    # verbatim, so a seam the scripting missed -- answering
    # in its own words, or engaging -- fails the test
    # instead of silently passing it.
    DEAD_BACKEND = "backend cannot engage (scripted dead backend)"

    def test_confinement_enforce_refused_when_sandbox_cannot_engage(self):
        # The skip is keyed to the probe the host's own
        # startup gate consults: bwrap's trial on Linux; on
        # Windows, macOS and FreeBSD the platform backend's
        # probe, asked through the runner's startup gate --
        # bwrap's answer there is only "Linux-only", so the
        # bwrap-keyed skip read "cannot engage" on every
        # macOS host even after the Seatbelt backend
        # engaged (the post-fifth-fix test-macos shape,
        # desk R6-S3).
        if sys.platform == "win32" or sys.platform == "darwin" \
                or sys.platform.startswith("freebsd"):
            engages = RR._confinement_startup_problem(
                {"security": {"modes": {"confinement": "enforce"}}}
            ) is None
        else:
            engages = _sandbox.startup_problem() is None
        if engages:
            self.skipTest("sandbox engages on this machine "
                          "(startup probe)")
        # On a platform-backend host main() consults that
        # backend's probe for confinement, not bwrap's:
        # script every seam the gate can route to, so the
        # condition this test states is the condition
        # constructed on every host (Q136-GATES2-S2, Q159).
        # Left unscripted on a host whose backend engages,
        # no refusal fires and main() proceeds into the poll
        # loop and never returns -- on macOS that was the
        # shard that ended without a named failure once the
        # backend first engaged. job_user is stated off, as
        # in the strict sibling file, so the one gate this
        # test is about is the gate that fires; the
        # --audit-report one-shot means a step-down would
        # show up as a successful report (exit 0) instead
        # of the refusal.
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

    def test_confinement_enforce_refused_on_each_platform_shape(self):
        # The R6-S3 regression family: the same construction
        # through each simulated platform shape in turn,
        # each with its own scripted problem text, so the
        # per-platform routing itself is pinned -- whichever
        # branch the platform selects, the seam it consults
        # is the scripted one, the refusal names the mode,
        # and the text that seam answered is the text the
        # refusal carries. The darwin shape is the one that
        # proceeded into the poll loop before this fix.
        for platform in ("linux", "win32", "darwin", "freebsd14"):
            dead = "backend cannot engage (scripted on %s)" % platform
            with self.subTest(platform=platform):
                with scripted_confinement(dead):
                    rc, out, err = run_main(
                        {"security": {"modes":
                                      {"confinement": "enforce",
                                       "job_user": "off"}}},
                        ("--audit-report",), platform=platform,
                        sandbox_problem=dead)
                self.assertEqual(rc, 2, err)
                self.assertIn("security.modes.confinement", err)
                self.assertIn(dead, err)
                self.assertNotIn("Security audit report", out)

    def test_confinement_enforce_live_backend_starts_on_darwin(self):
        # The control for the family above, on the
        # regression platform: a macOS backend that can
        # engage lets the same enforce startup proceed to
        # the audit report, so the refusal pins cannot pass
        # by refusing everything -- and the shape that once
        # hung in the poll loop now returns.
        with scripted_confinement(None):
            rc, out, err = run_main(
                {"security": {"modes": {"confinement": "enforce",
                                        "job_user": "off"}}},
                ("--audit-report",), platform="darwin")
        self.assertEqual(rc, 0, err)
        self.assertIn("Security audit report", out)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
