#!/usr/bin/env python3
"""M4 tests: --posture exit codes, 0600 checks, secret quality,
unreadable config behavior."""
import contextlib
import io
import json
import os
import secrets
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import posture as P  # noqa: E402
from runner.guard import security as S  # noqa: E402

STRONG = secrets.token_hex(32)


def _cfg_file(d, cfg, mode=0o600):
    path = os.path.join(d, "config.json")
    with open(path, "w") as fh:
        json.dump(cfg, fh)
    os.chmod(path, mode)
    return path


def _run(cfg, cfg_path, base_dir):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = P.main(cfg, cfg_path, base_dir)
    return rc, buf.getvalue()


@contextlib.contextmanager
def _backend_present():
    """The host's confinement backend, answered present, for
    tests whose subject is something else. The report asks a
    different backend on each platform -- bwrap on the path on
    Linux, the jail backend's own lines on FreeBSD -- and each
    answers for the host the suite happens to run on: a Linux
    host without bwrap, or a FreeBSD host whose suite is not
    root, reads a WARN there, as it should. Both seams are
    answered here, so a test that asks for a clean report gets
    one on every host."""
    with mock.patch.object(P.shutil, "which", return_value="/usr/bin/bwrap"), \
            mock.patch.object(P, "_freebsd_confinement_lines",
                              return_value=[("OK", "FreeBSD jail backend: answered present")]):
        yield


def _full_cfg(d):
    """A config that passes every posture check (for tests whose
    subject is something else)."""
    return {"base_dir": d, "shared_secret": STRONG,
            "workspace_root": d,
            "security": {"modes": {"audience": "audit",
                                   "policy_env": "audit",
                                   "policy_files": "audit",
                                   "policy_args": "audit",
                                   # Stated off: unset, these
                                   # read enforce under the
                                   # lockdown default and main()
                                   # refuses this host before the
                                   # posture dispatch.
                                   "confinement": "off",
                                   "job_user": "off"}}}


class PostureTest(unittest.TestCase):
    def test_all_ok(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            path = _cfg_file(d, cfg, 0o600)
            with _backend_present():
                rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 0)
        self.assertIn("[OK  ]", out)

    def test_workspace_root_unset_warns(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "shared_secret": STRONG}
            path = _cfg_file(d, cfg, 0o600)
            rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 1)
        self.assertIn("workspace_root unset", out)

    def test_recommended_features_off_warn(self):
        with tempfile.TemporaryDirectory() as d:
            # The modes are stated off: unset, they read
            # enforce under the lockdown default and there is
            # no off warning to assert on.
            cfg = {"base_dir": d, "shared_secret": STRONG,
                   "workspace_root": d,
                   "security": {"modes": {
                       "policy_env": "off", "policy_files": "off",
                       "policy_args": "off", "audience": "off",
                       "confinement": "off", "job_user": "off"}}}
            path = _cfg_file(d, cfg, 0o600)
            rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 1)
        self.assertIn("audience is off (recommended", out)

    def test_loose_key_warns(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            cfg["additional_secrets"] = {"svc": STRONG}
            path = _cfg_file(d, cfg, 0o600)
            with _backend_present():
                rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 1)
        self.assertIn('key "svc" has no policy entry', out)

    def test_loose_key_ok_with_default_deny(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            cfg["additional_secrets"] = {"svc": STRONG}
            cfg["key_policies_default_deny"] = True
            path = _cfg_file(d, cfg, 0o600)
            with _backend_present():
                rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 0)

    def test_bwrap_missing_warns(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            path = _cfg_file(d, cfg, 0o600)
            with mock.patch.object(P.shutil, "which", return_value=None):
                with mock.patch.object(P.sys, "platform", "linux"):
                    rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 1)
        self.assertIn("bwrap not installed", out)

    def test_privileges_reported(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "shared_secret": STRONG}
            path = _cfg_file(d, cfg, 0o600)
            _, out = _run(cfg, path, d)
        self.assertIn("privileges", out)

    @unittest.skipUnless(os.name != "nt", "Unix mode bits")
    def test_loose_config_perms_warn(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "shared_secret": STRONG}
            path = _cfg_file(d, cfg, 0o644)
            rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 1)
        self.assertIn("0644 (expected 0600)", out)

    def test_weak_secret_fail(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "shared_secret": "password"}
            path = _cfg_file(d, cfg, 0o600)
            rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 2)
        self.assertIn("[FAIL]", out)

    def test_placeholder_secret_fail(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d,
                   "shared_secret": "changeme-generate-your-secret-here"}
            path = _cfg_file(d, cfg, 0o600)
            rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 2)
        self.assertIn("placeholder", out)

    def test_weak_additional_secret_fail(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d, "shared_secret": STRONG,
                   "additional_secrets": {"k": "abc"}}
            path = _cfg_file(d, cfg, 0o600)
            rc, _ = _run(cfg, path, d)
        self.assertEqual(rc, 2)

    @unittest.skipUnless(os.name != "nt", "Unix mode bits")
    def test_audit_file_perms(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            path = _cfg_file(d, cfg, 0o600)
            audit = os.path.join(d, S.AUDIT_FILE)
            open(audit, "w").write("{}\n")
            os.chmod(audit, 0o600)
            with _backend_present():
                rc, _ = _run(cfg, path, d)
            self.assertEqual(rc, 0)
            os.chmod(audit, 0o644)
            rc, out = _run(cfg, path, d)
            self.assertEqual(rc, 1)
            self.assertIn("security-audit.jsonl", out)

    def test_unreadable_config_path_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = _run({}, os.path.join(d, "nope.json"), d)
        self.assertEqual(rc, 2)
        self.assertIn("cannot read config", out)

    def test_missing_base_dir_fail(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": os.path.join(d, "gone"),
                   "shared_secret": STRONG}
            path = _cfg_file(d, cfg, 0o600)
            rc, out = _run(cfg, path, os.path.join(d, "gone"))
        self.assertEqual(rc, 2)
        self.assertIn("does not exist", out)

    def test_modes_summarized(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            path = _cfg_file(d, cfg, 0o600)
            with _backend_present():
                rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 0)
        self.assertIn("policy_env=audit", out)

    def test_job_user_enforce_without_a_user_is_named_not_engaged(self):
        # Phase 2 of the default-posture work: the posture report
        # names a job_user mode that reads enforce while engaging
        # nothing, as a WARN -- enforce never silently means
        # nothing. A named user, and any lower mode, stay unnamed.
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            cfg["security"]["modes"]["job_user"] = "enforce"
            path = _cfg_file(d, cfg, 0o600)
            with _backend_present():
                rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 1)  # a WARN is present, no FAIL
        self.assertIn("job_user is enforce but no", out)
        self.assertIn("not engaged", out)
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            cfg["security"]["modes"]["job_user"] = "enforce"
            cfg["security"]["job_user"] = {"user": "pigeon-jobs"}
            path = _cfg_file(d, cfg, 0o600)
            with _backend_present():
                rc, out = _run(cfg, path, d)
        self.assertNotIn("not engaged", out)


class BackendOfTheHostTest(unittest.TestCase):
    """A clean report is clean on every host the suite runs on.

    The hosted FreeBSD suite runs as an ordinary user, where the
    jail backend cannot engage and the report says so. A test
    that asks for a clean report answers for the backend
    (_backend_present); the report's own word for such a host
    is pinned here beside it. The subject is the confinement
    line alone, so these read the same on every surface."""

    REFUSED = ("FreeBSD jail backend cannot engage: creating a jail "
               "needs root; the runner is not running as root; "
               "confinement in enforce mode would refuse to start")

    def _confinement(self, platform, lines=None):
        """The all-OK config's confinement lines on `platform`,
        as (level, text). `lines` is what the jail backend says
        of the host; None is the backend answered present."""
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            path = _cfg_file(d, cfg, 0o600)
            with contextlib.ExitStack() as stack:
                stack.enter_context(_backend_present())
                stack.enter_context(
                    mock.patch.object(P.sys, "platform", platform))
                if lines is not None:
                    stack.enter_context(mock.patch.object(
                        P, "_freebsd_confinement_lines",
                        return_value=lines))
                results = P.build_posture(cfg, path, d)
        return [(level, text) for level, subject, text in results
                if subject == "confinement"]

    def test_the_confinement_line_is_ok_where_the_backend_is_present(self):
        for platform in ("linux", "freebsd14.5", "freebsd15.0"):
            lines = self._confinement(platform)
            self.assertEqual([level for level, _text in lines], ["OK"],
                             (platform, lines))
        self.assertEqual(
            self._confinement("freebsd14.5"),
            [("OK", "FreeBSD jail backend: answered present")])

    def test_a_freebsd_host_whose_backend_cannot_engage_reads_a_warning(self):
        # the suite as an ordinary user on FreeBSD: the report is
        # right to warn, and exit 1 is the warning's
        lines = self._confinement("freebsd14.5", [("WARN", self.REFUSED)])
        self.assertEqual(lines, [("WARN", self.REFUSED)])
        self.assertEqual(P.exit_code_for(
            [(level, "confinement", text) for level, text in lines]), 1)
        # the same host is not asked on Linux, whatever it would say
        lines = self._confinement("linux", [("WARN", self.REFUSED)])
        self.assertEqual([level for level, _text in lines], ["OK"])
        self.assertNotIn(self.REFUSED, [text for _level, text in lines])

    def test_no_test_here_answers_for_bwrap_alone(self):
        # a clean report asked with bwrap answered and the jail
        # backend left to the host is the shape that reads red on
        # a FreeBSD host whose suite is not root; _backend_present
        # answers both
        with open(os.path.join(REPO, "runner", "tests", "test_posture.py"),
                  encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        alone = [n for n, line in enumerate(lines, 1)
                 if line.strip().startswith("with mock.patch.object(P.shutil,")
                 and line.rstrip().endswith('bwrap"):')]
        self.assertEqual(alone, [])
        self.assertGreaterEqual(
            sum(1 for line in lines if line.strip() == "with _backend_present():"), 9)


class WindowsPermsTest(unittest.TestCase):
    """The Windows ACL check maps True/False/None to OK/WARN/WARN."""

    def _results(self, mapped):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            path = _cfg_file(d, cfg, 0o600)
            with mock.patch.object(P.os, "name", "nt"):
                with mock.patch.object(P, "_windows_file_restricted",
                                        return_value=mapped):
                    with _backend_present():
                        return P.build_posture(cfg, path, d)

    def test_restricted_ok(self):
        levels = [r[0] for r in self._results(True)]
        self.assertIn("OK", levels)
        self.assertNotIn("WARN", levels)

    def test_broad_read_warn(self):
        res = self._results(False)
        warns = [r for r in res if r[0] == "WARN"]
        self.assertTrue(any("Everyone" in r[2] for r in warns))
        self.assertEqual(P.exit_code_for(res), 1)

    def test_unknown_warn(self):
        res = self._results(None)
        warns = [r for r in res if r[0] == "WARN"]
        self.assertTrue(any("could not evaluate" in r[2] for r in warns))


class FlagIntegrationTest(unittest.TestCase):
    def test_flag_via_main(self):
        from runner.runner import main
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            cfg_path = _cfg_file(d, cfg, 0o600)
            buf = io.StringIO()
            with mock.patch.object(sys, "argv", ["runner", "--config",
                                                 cfg_path, "--posture"]):
                with _backend_present():
                    with redirect_stdout(buf):
                        rc = main()
            self.assertEqual(rc, 0)
            self.assertIn("Security posture", buf.getvalue())

    def test_flag_missing_config_exits_2(self):
        from runner.runner import main
        with mock.patch.object(sys, "argv", ["runner", "--config",
                                             "/nonexistent/hp.json",
                                             "--posture"]):
            with redirect_stdout(io.StringIO()):
                rc = main()
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
