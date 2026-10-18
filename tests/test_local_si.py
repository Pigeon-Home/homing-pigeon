#!/usr/bin/env python3
"""Tests for the local SI harness. No live model."""
import os
import sys
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from runner.local_test import answer_as_oracle, build_ask_job, start_si_instance
from runner.runner import verify_body


SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


class LocalSITest(unittest.TestCase):
    def test_build_ask_job_is_signed(self):
        job = build_ask_job("why did it fail?", SECRET)
        self.assertEqual(job["kind"], "ping")
        self.assertEqual(job["result_policy"]["queries"][0]["op"], "ask")
        # Round-trips through verify.
        body = __import__("json").dumps(job)
        # build returns the parsed signed object; re-verify via the body form
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
        self.assertNotIn("start_new_session", seen.get("kw", {}))
        self.assertIn("creationflags", seen.get("kw", {}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
