#!/usr/bin/env python3
"""Oracle privacy result tests (v3 Piece 3)."""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import apply_result_policy, _redact_patterns, VIEW_ORDER

class OracleTest(unittest.TestCase):
    def test_full_view_default(self):
        cfg = {"oracle_enabled": True, "max_result_view": "full"}
        job = {"job_id": "j1", "kind": "ping"}
        er = {"exit_code": 0, "stdout": "pong", "stderr": "", "timed_out": False, "duration_sec": 0.0}
        result, retain = apply_result_policy(cfg, job, er, _redact_patterns(cfg), False)
        self.assertEqual(result["view"], "full")
        self.assertEqual(result["stdout"], "pong")
        self.assertFalse(retain)

    def test_ceiling_narrows(self):
        cfg = {"oracle_enabled": True, "max_result_view": "summary"}
        job = {"job_id": "j1", "kind": "exec", "result_policy": {"view": "full"}}
        er = {"exit_code": 0, "stdout": "secret", "stderr": "", "timed_out": False, "duration_sec": 0.1}
        result, retain = apply_result_policy(cfg, job, er, _redact_patterns(cfg), False)
        self.assertEqual(result["view"], "summary")
        self.assertNotIn("secret", result.get("stdout", ""))
        self.assertTrue(retain)

    def test_redacted_scrubs(self):
        cfg = {"oracle_enabled": True, "max_result_view": "full"}
        job = {"job_id": "j1", "kind": "exec", "result_policy": {"view": "redacted"}}
        er = {"exit_code": 0, "stdout": "key AKIAIOSFODNN7EXAMPLE found", "stderr": "", "timed_out": False, "duration_sec": 0.1}
        result, _ = apply_result_policy(cfg, job, er, _redact_patterns(cfg), False)
        self.assertEqual(result["view"], "redacted")
        self.assertIn("[REDACTED:aws_key]", result["stdout"])
        self.assertIn("aws_key", result["redacted_families"])

    def test_oracle_disabled_bypasses(self):
        cfg = {"oracle_enabled": False}
        job = {"job_id": "j1", "result_policy": {"view": "attested"}}
        er = {"exit_code": 0, "stdout": "raw", "stderr": "", "timed_out": False, "duration_sec": 0.0}
        result, retain = apply_result_policy(cfg, job, er, {}, False)
        self.assertEqual(result["stdout"], "raw")
        self.assertFalse(retain)


if __name__ == "__main__":
    unittest.main(verbosity=2)
