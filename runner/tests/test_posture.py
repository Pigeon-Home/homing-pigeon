#!/usr/bin/env python3
"""M4 tests: --posture exit codes, 0600 checks, secret quality,
unreadable config behavior."""
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

from runner import posture as P  # noqa: E402
from runner import security as S  # noqa: E402

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


def _full_cfg(d):
    """A config that passes every posture check (for tests whose
    subject is something else)."""
    return {"base_dir": d, "shared_secret": STRONG,
            "workspace_root": d,
            "security": {"modes": {"audience": "audit",
                                   "policy_env": "audit",
                                   "policy_files": "audit",
                                   "policy_args": "audit"}}}


class PostureTest(unittest.TestCase):
    def test_all_ok(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            path = _cfg_file(d, cfg, 0o600)
            with mock.patch.object(P.shutil, "which", return_value="/usr/bin/bwrap"):
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
            cfg = {"base_dir": d, "shared_secret": STRONG,
                   "workspace_root": d}
            path = _cfg_file(d, cfg, 0o600)
            rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 1)
        self.assertIn("audience is off (recommended", out)

    def test_loose_key_warns(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            cfg["additional_secrets"] = {"svc": STRONG}
            path = _cfg_file(d, cfg, 0o600)
            with mock.patch.object(P.shutil, "which", return_value="/usr/bin/bwrap"):
                rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 1)
        self.assertIn('key "svc" has no policy entry', out)

    def test_loose_key_ok_with_default_deny(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            cfg["additional_secrets"] = {"svc": STRONG}
            cfg["key_policies_default_deny"] = True
            path = _cfg_file(d, cfg, 0o600)
            with mock.patch.object(P.shutil, "which", return_value="/usr/bin/bwrap"):
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
            with mock.patch.object(P.shutil, "which", return_value="/usr/bin/bwrap"):
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
            with mock.patch.object(P.shutil, "which", return_value="/usr/bin/bwrap"):
                rc, out = _run(cfg, path, d)
        self.assertEqual(rc, 0)
        self.assertIn("policy_env=audit", out)


class WindowsPermsTest(unittest.TestCase):
    """The Windows ACL check maps True/False/None to OK/WARN/WARN."""

    def _results(self, mapped):
        with tempfile.TemporaryDirectory() as d:
            cfg = _full_cfg(d)
            path = _cfg_file(d, cfg, 0o600)
            with mock.patch.object(P.os, "name", "nt"):
                with mock.patch.object(P, "_windows_file_restricted",
                                        return_value=mapped):
                    with mock.patch.object(P.shutil, "which",
                                            return_value="bwrap"):
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
                with mock.patch.object(P.shutil, "which",
                                        return_value="/usr/bin/bwrap"):
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
