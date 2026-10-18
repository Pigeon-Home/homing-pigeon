#!/usr/bin/env python3
"""Negative cases for redact_text, secret_scan, and apply_result_policy.

Findings: concurrent redact_text / secret_scan with non-dict patterns,
non-string text, and bad regexes do not raise. apply_result_policy
with non-dict inputs returns a dict without raising.
"""
import os
import sys
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import redact_text, secret_scan, apply_result_policy  # noqa: E402


class RedactAndPolicyNegative(unittest.TestCase):
    def test_redact_bad_inputs(self):
        """Finding: non-string text, non-dict patterns, bad regex
        return (str, list) without raising."""
        text, fams = redact_text(None, None)
        self.assertIsInstance(text, str)
        self.assertIsInstance(fams, list)
        text, fams = redact_text(123, "not-a-dict")
        self.assertIsInstance(text, str)
        text, fams = redact_text("secret=abc", {"bad": "["})  # bad regex
        self.assertIsInstance(text, str)

    def test_concurrent_redact(self):
        """Finding: concurrent redact_text and secret_scan with mixed
        bad patterns do not raise."""
        errors = []
        def worker():
            try:
                for _ in range(10):
                    redact_text("hello", {"x": None, "y": "["})
                    secret_scan(None, {"z": ".*"})
                    secret_scan("data", "not-dict")
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_apply_result_policy_bad(self):
        """Finding: non-dict cfg/job/exec_result return a result dict
        without raising."""
        r = apply_result_policy(None, None, None, None, None)
        self.assertTrue(isinstance(r, (dict, tuple)))
        r = apply_result_policy({"max_result_view": "weird"}, "not-job", {"stdout": 5}, "bad", False)
        self.assertTrue(isinstance(r, (dict, tuple)))


if __name__ == "__main__":
    unittest.main()
