#!/usr/bin/env python3
"""Logging expansion: bigger bounded logs, oracle.log, job output.

Covers the 2026-10-17 logging work:

1. append_bounded_log keeps N backups (path.1 .. path.N, oldest
   dropped); backups=1 reproduces the historic single-backup roll.
2. log_max_bytes / log_backups config keys size runner.log, with
   invalid values falling back to defaults instead of crashing.
3. oracle_log (off by default) records full inference exchanges --
   request payload, reply, tool calls, error bodies verbatim -- in
   oracle.log, sized by oracle_log_max_bytes / oracle_log_backups.
   Config secrets (shared secret, mailbox password) are never part
   of a record: a canary check proves it.
4. A job's complete stdout/stderr lands in runner.log, framed,
   before the result email's bounded copy is truncated.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock
from urllib.error import HTTPError

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402


class _Reply:
    """Minimal stand-in for an inference HTTP response."""

    def __init__(self, body: bytes):
        self._body = body

    def read(self, n=-1):
        return self._body if n is None or n < 0 else self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def _opener_returning(body: bytes):
    def _open(req, timeout=60):
        return _Reply(body)
    return _open


class _GlobalStateGuard(unittest.TestCase):
    """Snapshot and restore the module log globals a test mutates."""

    _KEYS = ("_LOG_FILE", "_LOG_MAX_BYTES", "_LOG_BACKUPS",
             "_LOG_MINUTE", "_LOG_COUNT", "_LOG_DROPPED",
             "_ORACLE_LOG_ENABLED", "_ORACLE_LOG_PATH",
             "_ORACLE_LOG_MAX_BYTES", "_ORACLE_LOG_BACKUPS",
             "_ORACLE_LOG_ANNOUNCED")

    def setUp(self):
        self._saved = {k: getattr(R, k) for k in self._KEYS}
        R._LOG_MINUTE = 0.0
        R._LOG_COUNT = 0
        R._LOG_DROPPED = 0

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(R, k, v)


class RotationTest(unittest.TestCase):
    def test_backups_3_keeps_newest_drops_oldest(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.log")
            for ch in "ABCDE":
                R.append_bounded_log(path, ch * 60,
                                     max_bytes=100, backups=3)
            names = sorted(os.listdir(d))
            self.assertEqual(names,
                             ["x.log", "x.log.1", "x.log.2", "x.log.3"])
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), "E" * 60)
            with open(path + ".3", encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), "B" * 60)
            for name in names:
                with open(os.path.join(d, name), encoding="utf-8") as fh:
                    self.assertNotIn("A" * 60, fh.read())

    def test_backups_1_is_the_old_behavior(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.log")
            for ch in "ABC":
                R.append_bounded_log(path, ch * 60,
                                     max_bytes=100, backups=1)
            self.assertEqual(sorted(os.listdir(d)), ["x.log", "x.log.1"])
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), "C" * 60)
            with open(path + ".1", encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), "B" * 60)

    def test_default_backups_is_one(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.log")
            for ch in "ABC":
                R.append_bounded_log(path, ch * 60, max_bytes=100)
            self.assertEqual(sorted(os.listdir(d)), ["x.log", "x.log.1"])


class SettingsTest(_GlobalStateGuard):
    def test_defaults(self):
        self.assertEqual(R._log_settings({}), (33_554_432, 4))
        self.assertEqual(R._oracle_log_settings({}), (536_870_912, 4))

    def test_invalid_values_fall_back(self):
        bad = {"log_max_bytes": "junk", "log_backups": None}
        self.assertEqual(R._log_settings(bad), (33_554_432, 4))
        self.assertEqual(R._log_settings({"log_max_bytes": -5}),
                         (33_554_432, 4))
        self.assertEqual(R._log_settings({"log_max_bytes": True}),
                         (33_554_432, 4))
        self.assertEqual(R._log_settings({"log_backups": 0}),
                         (33_554_432, 4))
        bad_o = {"oracle_log_max_bytes": object(),
                 "oracle_log_backups": "x"}
        self.assertEqual(R._oracle_log_settings(bad_o), (536_870_912, 4))

    def test_valid_values_and_clamps(self):
        self.assertEqual(
            R._log_settings({"log_max_bytes": 1000, "log_backups": 99}),
            (1000, 10))
        self.assertEqual(
            R._oracle_log_settings({"oracle_log_max_bytes": 2048,
                                    "oracle_log_backups": 2}),
            (2048, 2))

    def test_refresh_wires_runner_log_bounds_into_log(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "runner.log")
            R._LOG_FILE = path
            R._refresh_log_settings(
                {"log_max_bytes": 120, "log_backups": 2}, d)
            buf = io.StringIO()
            with redirect_stdout(buf):
                for i in range(6):
                    R.log(f"line-{i} " + "y" * 40)
            # 120-byte files, 2 backups: rotation must have happened
            # through log() itself, and a .2 must exist (the old
            # single-backup default could never produce one).
            self.assertTrue(os.path.exists(path + ".1"))
            self.assertTrue(os.path.exists(path + ".2"))
            self.assertFalse(os.path.exists(path + ".3"))


class OracleLogTest(_GlobalStateGuard):
    _INF = {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}

    def _enable(self, d, extra=None):
        cfg = {"oracle_log": True}
        if extra:
            cfg.update(extra)
        R._refresh_log_settings(cfg, d)
        self.assertTrue(R._ORACLE_LOG_ENABLED)
        return os.path.join(d, "oracle.log")

    def test_disabled_by_default_writes_no_file(self):
        with tempfile.TemporaryDirectory() as d:
            R._refresh_log_settings({}, d)
            self.assertFalse(R._ORACLE_LOG_ENABLED)
            body = b'{"choices":[{"message":{"content":"hi"}}]}'
            R.ask_model(self._INF, "q?", "out", 2000,
                        opener=_opener_returning(body))
            self.assertFalse(os.path.exists(os.path.join(d, "oracle.log")))

    def test_ask_model_records_request_and_response(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._enable(d)
            body = b'{"choices":[{"message":{"content":"the answer"}}]}'
            ans = R.ask_model(self._INF, "what time?", "job output", 2000,
                              opener=_opener_returning(body))
            self.assertEqual(ans.get("answer"), "the answer")
            with open(path, encoding="utf-8") as fh:
                rec = json.loads(fh.read().strip().splitlines()[-1])
            self.assertEqual(rec["endpoint"], self._INF["endpoint"])
            self.assertEqual(rec["model"], "m")
            self.assertIn("ts", rec)
            self.assertIn("elapsed_sec", rec)
            self.assertEqual(rec["response"], "the answer")
            sent = rec["request"]["messages"]
            self.assertEqual(sent[0]["role"], "system")
            self.assertIn("what time?", sent[1]["content"])
            self.assertIn("job output", sent[1]["content"])

    def test_agent_chat_records_tool_calls_and_args(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._enable(d)
            msg = {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call-1", "type": "function",
                    "function": {"name": "read_file",
                                 "arguments": '{"path": "/etc/hostname"}'},
                }],
            }
            body = json.dumps({"choices": [{"message": msg}]}).encode()
            out = R._inference_chat(
                self._INF,
                [{"role": "user", "content": "read the hostname file"}],
                R._ORACLE_TOOLS, _opener_returning(body), 30)
            self.assertEqual(out["tool_calls"][0]["id"], "call-1")
            with open(path, encoding="utf-8") as fh:
                rec = json.loads(fh.read().strip().splitlines()[-1])
            calls = rec["response"]["tool_calls"]
            self.assertEqual(calls[0]["function"]["name"], "read_file")
            self.assertIn("/etc/hostname",
                          calls[0]["function"]["arguments"])
            self.assertEqual(rec["request"]["messages"][0]["content"],
                             "read the hostname file")

    def test_error_body_recorded_verbatim(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._enable(d)
            err_text = "endpoint exploded: " + "z" * 900

            def _boom(req, timeout=60):
                raise HTTPError("http://127.0.0.1:11434/v1", 500,
                                "Internal", None,
                                io.BytesIO(err_text.encode()))

            out = R._inference_chat(self._INF,
                                    [{"role": "user", "content": "hi"}],
                                    None, _boom, 30)
            self.assertEqual(out.get("role"), "error")
            with open(path, encoding="utf-8") as fh:
                rec = json.loads(fh.read().strip().splitlines()[-1])
            self.assertEqual(rec["error_body"], err_text)
            self.assertIn("HTTP 500", rec["error"])

    def test_canary_secrets_never_recorded(self):
        canary_secret = "CANARY-SHARED-SECRET-0123456789"
        canary_pass = "CANARY-MAILBOX-PASSWORD-0123456789"
        with tempfile.TemporaryDirectory() as d:
            path = self._enable(d, {
                "shared_secret": canary_secret,
                "mailbox_password": canary_pass,
                "inference": dict(self._INF),
            })
            body = b'{"choices":[{"message":{"content":"clean reply"}}]}'
            R.ask_model(self._INF, "q?", "ordinary job output", 2000,
                        opener=_opener_returning(body))
            R._inference_chat(self._INF,
                              [{"role": "user", "content": "hello"}],
                              None, _opener_returning(body), 30)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("clean reply", text)
            self.assertNotIn(canary_secret, text)
            self.assertNotIn(canary_pass, text)
            self.assertNotIn("CANARY", text)


class DaemonOutputTest(_GlobalStateGuard):
    _CFG = {"inference": {"endpoint": "http://127.0.0.1:11434/v1",
                          "model": "m"}}

    def _run_ready(self, d, cfg):
        R._refresh_log_settings(cfg, d)
        captured = {}

        def _fake_popen(argv, **kw):
            captured["argv"] = argv
            captured.update(kw)
            return mock.MagicMock()

        with mock.patch.object(R.socket, "create_connection",
                               side_effect=OSError("down")), \
                mock.patch("shutil.which", return_value="/usr/bin/ollama"), \
                mock.patch.object(R.subprocess, "Popen", _fake_popen):
            with redirect_stdout(io.StringIO()):
                R.ensure_inference_ready(cfg)
        return captured

    def test_daemon_output_discarded_when_oracle_log_off(self):
        with tempfile.TemporaryDirectory() as d:
            cap = self._run_ready(d, dict(self._CFG))
            import subprocess as sp
            self.assertEqual(cap["argv"], ["ollama", "serve"])
            self.assertEqual(cap["stdout"], sp.DEVNULL)
            self.assertEqual(cap["stderr"], sp.DEVNULL)

    def test_daemon_output_goes_to_oracle_log_when_on(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = dict(self._CFG)
            cfg["oracle_log"] = True
            cap = self._run_ready(d, cfg)
            self.assertEqual(cap["argv"], ["ollama", "serve"])
            self.assertEqual(cap["stdout"].name,
                             os.path.join(d, "oracle.log"))
            self.assertEqual(cap["stderr"].name,
                             os.path.join(d, "oracle.log"))


class JobOutputLogTest(_GlobalStateGuard):
    def test_log_job_output_frames_both_streams(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "runner.log")
            R._LOG_FILE = path
            R._log_job_output("job-9", "exec", "hello stdout",
                              "oops stderr", {})
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("job job-9 (kind=exec) full output:", text)
            self.assertIn("--- stdout ---\nhello stdout", text)
            self.assertIn("--- stderr ---\noops stderr", text)
            self.assertIn("--- end of job job-9 output ---", text)

    def test_execute_job_logs_full_output_before_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "runner.log")
            R._LOG_FILE = path
            long_line = "x" * 200
            with redirect_stdout(io.StringIO()):
                result = R.execute_job(
                    {"max_output_bytes": 64},
                    {"job_id": "log-full-1", "kind": "exec",
                     "script": f"echo {long_line}"},
                    d,
                )
            # The result copy is bounded...
            self.assertTrue(result["stdout_truncated"])
            self.assertLessEqual(len(result["stdout"]), 64)
            # ...but runner.log holds the complete line.
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("job log-full-1 (kind=exec) full output:", text)
            self.assertIn(long_line, text)


if __name__ == "__main__":
    unittest.main()
