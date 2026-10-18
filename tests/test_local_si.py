#!/usr/bin/env python3
"""Tests for the local SI harness. No live model.

Critical: on Windows, start_new_session raises ValueError before the
process is created. That used to kill the CLI browser path so the
Oracle window never opened. These tests pin the Windows-safe start
and the "no model up" path so a send cannot hang the CLI.
"""
import os
import sys
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from runner.local_test import (  # noqa: E402
    answer_as_oracle,
    browser_chat,
    build_ask_job,
    start_si_instance,
)
from runner.runner import verify_body  # noqa: E402


SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _cfg():
    return {
        "shared_secret": SECRET,
        "inference": {
            "endpoint": "http://127.0.0.1:11434/v1",
            "model": "llama3.2:3b",
            "max_answer_chars": 200,
            "timeout_sec": 2,
        },
    }


class LocalSITest(unittest.TestCase):
    def test_build_ask_job_is_signed(self):
        job = build_ask_job("why did it fail?", SECRET)
        self.assertEqual(job["kind"], "ping")
        self.assertEqual(job["result_policy"]["queries"][0]["op"], "ask")
        from runner.runner import sign_payload
        signed = sign_payload(
            {k: v for k, v in job.items() if k != "sig"}, SECRET
        )
        got = verify_body(signed, SECRET)
        self.assertEqual(got["result_policy"]["queries"][0]["question"],
                         "why did it fail?")

    def test_unconfigured_rejects(self):
        ans = answer_as_oracle({}, "hello")
        self.assertEqual(ans.get("rejected"), "inference_unconfigured")

    def test_missing_secret_rejects(self):
        ans = answer_as_oracle({"inference": _cfg()["inference"]}, "hello")
        self.assertEqual(ans.get("rejected"), "no shared_secret in config")

    def test_model_down_rejects_quickly_instead_of_hanging(self):
        """A down endpoint must not look like a hung send. Connection
        refused comes back as inference_error in well under the
        timeout, not as a silent wait.
        """
        t0 = time.time()
        ans = answer_as_oracle(_cfg(), "status?")
        self.assertLess(time.time() - t0, 3)
        self.assertEqual(ans.get("rejected"), "inference_error")
        self.assertNotIn("answer", ans)

    def test_hanging_model_is_bounded_by_timeout(self):
        import socket

        class Hang(Exception):
            pass

        def hang(req, timeout=60):
            raise socket.timeout("timed out")

        t0 = time.time()
        with mock.patch("runner.runner._default_inference_open", side_effect=hang):
            ans = answer_as_oracle(_cfg(), "status?")
        self.assertLess(time.time() - t0, 3)
        self.assertEqual(ans.get("rejected"), "inference_error")

    def test_start_si_instance_does_not_use_start_new_session_on_windows(self):
        """Finding: start_si_instance passed start_new_session=True.
        On Windows that raises ValueError before the process is
        created, so the SI never starts and the browser page never
        opens. It now uses the installer's Windows-safe kwargs.
        """
        seen = {}

        def fake_popen(argv, env=None, **kw):
            seen["argv"] = argv
            seen["kw"] = kw
            if kw.get("start_new_session"):
                raise ValueError("start_new_session is not supported on Windows")
            return mock.Mock()

        with mock.patch("runner.local_test._port_up", side_effect=[False, True]), \
             mock.patch("shutil.which", return_value="ollama"), \
             mock.patch("os.name", "nt"), \
             mock.patch("subprocess.Popen", side_effect=fake_popen):
            ok = start_si_instance()
        self.assertTrue(ok)
        self.assertEqual(seen["argv"], ["ollama", "serve"])
        self.assertNotIn("start_new_session", seen.get("kw", {}))
        self.assertIn("creationflags", seen.get("kw", {}))
        self.assertTrue(seen["kw"]["creationflags"])

    def test_posix_still_uses_start_new_session(self):
        seen = {}

        def fake_popen(argv, env=None, **kw):
            seen["kw"] = kw
            return mock.Mock()

        with mock.patch("runner.local_test._port_up", side_effect=[False, True]), \
             mock.patch("shutil.which", return_value="ollama"), \
             mock.patch("os.name", "posix"), \
             mock.patch("subprocess.Popen", side_effect=fake_popen):
            ok = start_si_instance()
        self.assertTrue(ok)
        self.assertTrue(seen["kw"].get("start_new_session"))
        self.assertNotIn("creationflags", seen["kw"])

    def test_already_listening_does_not_spawn(self):
        with mock.patch("runner.local_test._port_up", return_value=True), \
             mock.patch("subprocess.Popen") as popen:
            ok = start_si_instance()
        self.assertTrue(ok)
        popen.assert_not_called()

    def test_missing_ollama_returns_false_and_does_not_raise(self):
        with mock.patch("runner.local_test._port_up", return_value=False), \
             mock.patch("shutil.which", return_value=None):
            ok = start_si_instance()
        self.assertFalse(ok)

    def test_popen_raise_is_caught(self):
        def boom(*a, **k):
            raise OSError("cannot spawn")

        with mock.patch("runner.local_test._port_up", return_value=False), \
             mock.patch("shutil.which", return_value="ollama"), \
             mock.patch("subprocess.Popen", side_effect=boom):
            ok = start_si_instance()
        self.assertFalse(ok)

    def test_windows_valueerror_from_start_new_session_is_caught(self):
        # Belt and braces: even if a future edit puts start_new_session
        # back, the except must turn it into False rather than a crash
        # that kills the CLI before the window opens.
        def boom(*a, **k):
            raise ValueError("start_new_session is not supported on Windows")

        with mock.patch("runner.local_test._port_up", return_value=False), \
             mock.patch("shutil.which", return_value="ollama"), \
             mock.patch("subprocess.Popen", side_effect=boom):
            try:
                ok = start_si_instance()
            except ValueError as e:
                self.fail(f"Windows ValueError escaped start_si_instance: {e}")
        self.assertFalse(ok)

    def test_browser_chat_does_not_open_when_si_fails(self):
        with mock.patch("runner.local_test.start_si_instance", return_value=False), \
             mock.patch("webbrowser.open") as opened:
            code = browser_chat(_cfg())
        self.assertEqual(code, 2)
        opened.assert_not_called()

    def test_browser_chat_does_not_open_without_open_webui(self):
        with mock.patch("runner.local_test.start_si_instance", return_value=True), \
             mock.patch("runner.local_test._open_webui_available", return_value=False), \
             mock.patch("webbrowser.open") as opened:
            code = browser_chat(_cfg())
        self.assertEqual(code, 2)
        opened.assert_not_called()

    def test_si_port_is_not_the_oracle_port(self):
        from runner.local_test import SI_PORT, ORACLE_PORT
        self.assertNotEqual(SI_PORT, ORACLE_PORT)
        self.assertEqual(SI_PORT, 11435)
        self.assertEqual(ORACLE_PORT, 11434)


if __name__ == "__main__":
    unittest.main(verbosity=2)
