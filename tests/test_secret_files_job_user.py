#!/usr/bin/env python3
"""M8 tests: secret files and job_user."""
import json
import os
import secrets
import sys
import tempfile
import unittest
from unittest import mock

try:
    import pwd
except ImportError:  # Windows has no pwd
    pwd = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import security as S  # noqa: E402
from runner.runner import build_secrets, execute_job  # noqa: E402

STRONG = secrets.token_hex(32)
STRONG2 = secrets.token_hex(32)

if pwd is None:
    HAS_TEST_USER = False
else:
    try:
        pwd.getpwnam("pigeon-test")
        HAS_TEST_USER = True
    except KeyError:
        HAS_TEST_USER = False
IS_ROOT = os.geteuid() == 0 if hasattr(os, "geteuid") else False
POSIX = os.name != "nt"


def _secret_file(d, name, content):
    path = os.path.join(d, name)
    with open(path, "w") as fh:
        fh.write(content)
    return path


class SecretFilesTest(unittest.TestCase):
    def test_shared_secret_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "s", STRONG + "\n")
            secrets = build_secrets({"shared_secret_file": p})
        self.assertEqual(secrets[""], STRONG)

    def test_both_inline_and_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "s", STRONG)
            with self.assertRaises(RuntimeError):
                build_secrets({"shared_secret": STRONG,
                               "shared_secret_file": p})

    def test_missing_file_rejected(self):
        with self.assertRaises(RuntimeError):
            build_secrets(
                {"shared_secret_file": "/nonexistent/secret"})

    def test_empty_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "s", "  \n")
            with self.assertRaises(RuntimeError):
                build_secrets({"shared_secret_file": p})

    def test_weak_file_secret_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "s", "password")
            with self.assertRaises(RuntimeError):
                build_secrets({"shared_secret_file": p})

    def test_additional_secrets_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "k1", STRONG2)
            secrets = build_secrets({
                "shared_secret": STRONG,
                "additional_secrets_files": {"k1": p},
            })
        self.assertEqual(secrets["k1"], STRONG2)
        self.assertEqual(secrets[""], STRONG)

    def test_key_both_inline_and_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = _secret_file(d, "k1", STRONG2)
            with self.assertRaises(RuntimeError):
                build_secrets({
                    "shared_secret": STRONG,
                    "additional_secrets": {"k1": STRONG2},
                    "additional_secrets_files": {"k1": p},
                })

    def test_inline_still_works(self):
        secrets = build_secrets({"shared_secret": STRONG})
        self.assertEqual(secrets[""], STRONG)


def _job(jid, script):
    return {"v": 1, "type": "job", "job_id": jid,
            "issued_at": "2026-10-15T12:00:00Z",
            "kind": "exec", "interpreter": ["python3"],
            "script": script}


def _run(cfg_extra, job):
    tmpdir = tempfile.mkdtemp(prefix="hp-m8-")
    cfg = {"base_dir": tmpdir}
    cfg.update(cfg_extra)
    result = execute_job(cfg, job, tmpdir)
    audit = []
    path = os.path.join(tmpdir, S.AUDIT_FILE)
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                audit.append(json.loads(line))
            except ValueError:
                pass
    return result, audit


def _ju(mode, user="pigeon-test"):
    return {"security": {"modes": {"job_user": mode},
                         "job_user": {"user": user}}}


class JobUserTest(unittest.TestCase):
    def test_off_by_default(self):
        result, audit = _run({}, _job("m8-off", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(audit, [])

    @unittest.skipUnless(POSIX, "job_user audit is POSIX")
    def test_audit_logs_and_runs(self):
        result, audit = _run(
            _ju("audit"), _job("m8-audit", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["feature"], "job_user")
        self.assertEqual(audit[0]["decision"], "would_run_as")
        self.assertEqual(audit[0]["reason"], "would_run_as_user")

    def test_bad_config_rejected(self):
        for bad in ({"user": ""}, {"user": 123}, "pigeon-test",
                    {"user": "no-such-user-zzz"}):
            with self.assertRaises(RuntimeError, msg=str(bad)):
                S.validate_security_config(
                    {"security": {"job_user": bad}})

    @unittest.skipUnless(POSIX, "job_user fallback is POSIX")
    def test_non_root_falls_back(self):
        with mock.patch.object(os, "geteuid", return_value=1000):
            result, audit = _run(
                _ju("enforce"), _job("m8-nr", "print('hi')"))
        self.assertEqual(result["stdout"].strip(), "hi")
        self.assertEqual(audit[0]["decision"], "fallback")
        self.assertEqual(audit[0]["reason"], "job_user_needs_root")

    @unittest.skipUnless(IS_ROOT and HAS_TEST_USER,
                         "needs root and the pigeon-test user")
    def test_enforce_runs_as_job_user(self):
        script = ("import os, pwd\n"
                  "print('uid:', os.getuid())\n"
                  "print('user:', pwd.getpwuid(os.getuid()).pw_name)\n")
        result, audit = _run(_ju("enforce"), _job("m8-enf", script))
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        pw = pwd.getpwnam("pigeon-test")
        self.assertIn("uid: %d" % pw.pw_uid, result["stdout"])
        self.assertIn("user: pigeon-test", result["stdout"])
        self.assertEqual(audit[0]["decision"], "run_as")

    @unittest.skipUnless(IS_ROOT and HAS_TEST_USER,
                         "needs root and the pigeon-test user")
    def test_enforce_result_matches(self):
        script = "print(6 * 7)"
        r1, _ = _run({}, _job("m8-c1", script))
        r2, _ = _run(_ju("enforce"), _job("m8-c2", script))
        self.assertEqual(r1["stdout"], r2["stdout"])
        self.assertEqual(r1["exit_code"], r2["exit_code"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
