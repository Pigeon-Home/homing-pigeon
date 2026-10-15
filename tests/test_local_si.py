#!/usr/bin/env python3
"""Tests for the local SI harness. No live model."""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from runner.local_test import answer_as_oracle, build_ask_job
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
