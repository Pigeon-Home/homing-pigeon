"""Policy, retain, inspect, and Oracle-context edges.

These are the branches a normal poll never takes: a secret file
that is empty, a key policy that refuses the job, a retain write
that fails, and the Windows half of the Oracle context.
"""

import io
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr


class SecretAndPolicyTest(unittest.TestCase):
    def test_a_secret_file_must_exist_and_hold_text(self):
        with self.assertRaises(RuntimeError):
            rr._read_secret_file("", "shared_secret_file")
        with self.assertRaises(RuntimeError):
            rr._read_secret_file("/no/such/secret", "shared_secret_file")
        tmp = tempfile.NamedTemporaryFile("w", delete=False)
        self.addCleanup(os.unlink, tmp.name)
        tmp.write("   \n")
        tmp.close()
        with self.assertRaises(RuntimeError):
            rr._read_secret_file(tmp.name, "shared_secret_file")
        with open(tmp.name, "w", encoding="utf-8") as fh:
            fh.write("  s3cret \n")
        self.assertEqual(
            rr._read_secret_file(tmp.name, "shared_secret_file"), "s3cret")

    def test_a_key_policy_refuses_the_job_it_does_not_allow(self):
        job = {"kind": "exec", "interpreter": ["python3"],
               "timeout_sec": "nope", "script": "print(1)"}
        self.assertIn("invalid key policy map",
                      rr.check_key_policy([], "", {}, job))
        self.assertEqual(rr.check_key_policy({}, "", {}, []), "invalid job")
        self.assertIsNone(rr.check_key_policy({}, "extra", {}, job))
        denied = rr.check_key_policy(
            {}, "extra", {"key_policies_default_deny": True}, job)
        self.assertIn("default_deny", denied)
        self.assertIn("invalid key policy entry",
                      rr.check_key_policy({"k": "nope"}, "k", {}, job))
        reason = rr.check_key_policy(
            {"k": {"allowed_kinds": "exec"}}, "k", {}, job)
        self.assertIn("allowed_kinds", reason)
        reason = rr.check_key_policy(
            {"k": {"allowed_kinds": ["query"]}}, "k", {}, job)
        self.assertIn("not allowed", reason)
        reason = rr.check_key_policy(
            {"k": {"allowed_interpreters": "python"}}, "k", {}, job)
        self.assertIn("interpreter", reason)
        reason = rr.check_key_policy(
            {"k": {"max_timeout_sec": 10}}, "k", {}, job)
        self.assertIn("timeout_sec", reason)
        reason = rr.check_key_policy(
            {"k": {"max_timeout_sec": "nope"}}, "k", {},
            {"kind": "exec", "timeout_sec": 5})
        self.assertIn("max_timeout_sec", reason)
        reason = rr.check_key_policy(
            {"k": {"max_timeout_sec": 1}}, "k", {},
            {"kind": "exec", "timeout_sec": 50})
        self.assertIn("exceeds", reason)
        reason = rr.check_key_policy(
            {"k": {"allowed_script_sha384": ["abc"]}}, "k", {},
            {"kind": "exec", "script_url": "http://x"})
        self.assertIn("inline script", reason)
        reason = rr.check_key_policy(
            {"k": {"allowed_script_sha384": "abc"}}, "k", {},
            {"kind": "exec", "script": "print(1)"})
        self.assertIn("allowed_script_sha384", reason)
        digest = __import__("hashlib").sha384(b"print(1)").hexdigest()
        self.assertIsNone(rr.check_key_policy(
            {"k": {"allowed_script_sha384": [digest]}}, "k", {},
            {"kind": "exec", "script": "print(1)"}))
        reason = rr.check_key_policy(
            {"k": {"allowed_script_sha384": ["nope"]}}, "k", {},
            {"kind": "exec", "script": "print(1)"})
        self.assertIn("allowlist", reason)

    def test_extra_keys_without_a_policy_are_named(self):
        self.assertEqual(rr.unrestricted_extra_keys({
            "additional_secrets": {"other": "x", "": "y", 1: "z"},
            "key_policies": {},
        }), ["other"])
        self.assertEqual(rr.unrestricted_extra_keys({
            "additional_secrets": "nope"}), [])


class RetainAndBoardTest(unittest.TestCase):
    def test_a_failed_retain_write_is_logged_and_cleaned_up(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(rr, "_json_safe",
                               side_effect=TypeError("nan")):
            rr.save_retained(tmp.name, "job-1", {"a": 1})
        retained = os.path.join(tmp.name, "retained")
        self.assertEqual(os.listdir(retained), [])
        rr.save_retained(tmp.name, "job-1", {"a": 1})
        path = os.path.join(retained, "job-1.json")
        with mock.patch.object(rr.os, "chmod", side_effect=OSError("mode")):
            rr.save_retained(tmp.name, "job-1", {"a": 2})
        self.assertTrue(os.path.isfile(path))

    def test_a_failed_board_save_is_logged(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "board.json")
        board = rr.Board(path)
        board.tasks = {"t": {"task_id": "t"}}
        with mock.patch.object(rr.os, "replace", side_effect=OSError("ro")):
            board.save()
        self.assertFalse(os.path.isfile(path))
        board.save()
        with mock.patch.object(rr.os, "chmod", side_effect=OSError("mode")):
            board.save()
        self.assertTrue(os.path.isfile(path))


class InspectAndContextTest(unittest.TestCase):
    def test_inspect_reads_the_board_the_budget_and_a_job(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg = {"base_dir": tmp.name}
        args = types.SimpleNamespace(
            inspect="board", config=None, job_id=None)
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            self.assertEqual(rr.run_inspect(cfg, args), 0)
        self.assertIn("counts", buf.getvalue())
        args.inspect = "budget"
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            self.assertEqual(rr.run_inspect(cfg, args), 0)
        self.assertIn("max_queries_per_hour", buf.getvalue())
        args.inspect = "job"
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            self.assertEqual(rr.run_inspect(cfg, args), 2)
        self.assertIn("--job-id", err.getvalue())
        args.job_id = "missing-job"
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            self.assertEqual(rr.run_inspect(cfg, args), 1)
        rr.save_retained(tmp.name, "job-9", {"stdout": "hi"})
        args.job_id = "job-9"
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            self.assertEqual(rr.run_inspect(cfg, args), 0)
        self.assertIn("hi", buf.getvalue())
        args.inspect = "redact"
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf), \
                mock.patch("sys.stdin", io.StringIO("token sk-abc")):
            self.assertEqual(rr.run_inspect(cfg, args), 0)
        self.assertIn("redacted", buf.getvalue())

    def test_windows_context_says_unreadable_empty_or_present(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(rr.sys, "platform", "win32"), \
                mock.patch.object(rr, "_eventlog_tail", return_value=None), \
                mock.patch.object(rr, "_registry_watch", return_value=None), \
                mock.patch.object(rr, "_canary_watch", return_value=""), \
                mock.patch.object(rr, "_firewall_watch", return_value=None), \
                mock.patch.object(rr, "_av_watch", return_value=None):
            text = rr.oracle_context(tmp.name, watch=True)
        self.assertIn("Event Log: unreadable", text)
        self.assertIn("registry watch: unreadable", text)
        with mock.patch.object(rr.sys, "platform", "win32"), \
                mock.patch.object(rr, "_eventlog_tail", return_value=""), \
                mock.patch.object(rr, "_registry_watch",
                                  return_value="(no changes)"), \
                mock.patch.object(rr, "_canary_watch", return_value="ok"), \
                mock.patch.object(rr, "_firewall_watch",
                                  return_value="fw on"), \
                mock.patch.object(rr, "_av_watch", return_value="av on"):
            text = rr.oracle_context(tmp.name, watch=True, max_chars=True)
        self.assertIn("no Critical", text)
        self.assertIn("no changes", text)
        self.assertIn("Canary watch", text)
        self.assertIn("fw on", text)

    def test_a_host_log_is_unreadable_empty_or_shown(self):
        if sys.platform == "win32":
            self.skipTest("Windows shows registry watch")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for value, needle in ((None, "unreadable"),
                              ("", "no matching"),
                              ("failed password", "failed password")):
            with mock.patch.object(rr, "_host_log_tail", return_value=value), \
                    mock.patch.object(rr, "_canary_watch", return_value=""), \
                    mock.patch.object(rr, "_firewall_watch", return_value=""), \
                    mock.patch.object(rr, "_av_watch", return_value=""):
                text = rr.oracle_context(tmp.name, watch=True)
            self.assertIn(needle, text)

    def test_a_confinement_escape_quarantines_and_caps_the_referral(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        qdir = os.path.join(tmp.name, "q")
        qwork = os.path.join(qdir, "work")
        os.makedirs(qwork)
        for i in range(3):
            open(os.path.join(qwork, f"f{i}.txt"), "w").close()
        open(os.path.join(qwork, "gone.txt"), "w").close()
        real_size = os.path.getsize

        def size(path):
            if path.endswith("gone.txt"):
                raise OSError("gone")
            return real_size(path)

        rem = rr._remediation
        with mock.patch.object(rem, "settings",
                               return_value={"mode": "off"}):
            self.assertIsNone(rr._remediation_confinement_followup(
                {}, {}, "job-1", tmp.name))
        with mock.patch.object(rr, "_remediation", None):
            self.assertIsNone(rr._remediation_confinement_followup(
                {}, {}, "job-1", tmp.name))
        with mock.patch.object(rem, "settings",
                               return_value={"mode": "enforce"}), \
                mock.patch.object(rem, "divergence", return_value={"k": 1}), \
                mock.patch.object(rem, "divergence_text",
                                  return_value="escape"), \
                mock.patch.object(rem, "received_digest", return_value="d"), \
                mock.patch.object(rem, "quarantine_job", return_value=qdir), \
                mock.patch.object(rem, "av_referral",
                                  return_value=("clean", "ok")), \
                mock.patch.object(rem, "result_member",
                                  side_effect=lambda *a: {"act": a[3]}), \
                mock.patch.object(rem, "enforce_quarantine_bounds"), \
                mock.patch.object(rem, "AV_MAX_FILES", 1), \
                mock.patch.object(os.path, "getsize", side_effect=size):
            member = rr._remediation_confinement_followup(
                {}, {}, "job-1", tmp.name)
        self.assertEqual(member["act"], "quarantined")


class LogAndSeenTest(unittest.TestCase):
    def test_oracle_log_records_an_exchange_and_swallows_a_bad_dump(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        try:
            rr._refresh_log_settings({"oracle_log": True}, tmp.name)
            rr._oracle_log_exchange(
                "http://127.0.0.1:9", "m", {"q": 1},
                rr.time.monotonic(), response={"a": 1}, raw="raw",
                error="e", error_body="body")
            path = os.path.join(tmp.name, "oracle.log")
            self.assertTrue(os.path.isfile(path))
            with mock.patch.object(rr.json, "dumps",
                                   side_effect=TypeError("no")):
                rr._oracle_log_record({"x": 1})
        finally:
            rr._refresh_log_settings({}, tmp.name)
            rr._ORACLE_LOG_ANNOUNCED = False

    def test_save_seen_skips_junk_and_survives_a_failed_replace(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "seen.json")

        class Bad:
            def __str__(self):
                raise RuntimeError("no")

        rr.save_seen("", {1: True})
        rr.save_seen(path, {Bad(): True, "a\x00b": True, "ok": True})
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(sorted(json.load(fh)), ["ok"])  # {key: time}, Q102
        with mock.patch.object(rr.os, "chmod", side_effect=OSError("mode")):
            rr.save_seen(path, {"ok": True})
        with mock.patch.object(rr.os, "replace", side_effect=OSError("ro")):
            rr.save_seen(path, {"ok": True, "two": True})
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(sorted(json.load(fh)), ["ok"])  # {key: time}, Q102

    def test_a_transport_name_is_checked_at_startup(self):
        import argparse
        self.assertEqual(rr._transports_arg("file, email"),
                         ["file", "email"])
        # Names are shape-checked only: an unregistered drop-in
        # extension name is valid; discovery decides at start.
        self.assertEqual(rr._transports_arg("nope"), ["nope"])
        with self.assertRaises(argparse.ArgumentTypeError):
            rr._transports_arg("bad name!")
        with self.assertRaises(argparse.ArgumentTypeError):
            rr._transports_arg(" , ")


if __name__ == "__main__":
    unittest.main()
