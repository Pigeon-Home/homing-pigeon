#!/usr/bin/env python3
"""Tests for the detection gaps filled by runner/detection.py.

Canary tripwires are already covered by test_canary_watch.py and
are not re-tested here.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import detection  # noqa: E402


class DetectionGapsTest(unittest.TestCase):
    def test_rules_match_interpreter_and_script(self):
        job = {"interpreter": "python2", "script": "import base64; eval(x)"}
        hits = detection.evaluate_rules(job)
        ids = {h["rule_id"] for h in hits}
        self.assertIn("suspicious_interpreter", ids)
        self.assertIn("encoded_command", ids)

    def test_plan_budget(self):
        plan = [{"timeout_sec": 30} for _ in range(3)]
        ok, reason = detection.check_plan_budget(plan, {"max_plan_steps": 5})
        self.assertTrue(ok)
        ok, reason = detection.check_plan_budget(plan, {"max_plan_steps": 2})
        self.assertFalse(ok)

    def test_baseline_anomaly(self):
        with tempfile.TemporaryDirectory() as d:
            job = {"kind": "exec"}
            for i in range(12):
                detection.update_baseline(d, job, {"stdout": "x" * 100})
            baseline = detection.update_baseline(d, job, {"stdout": "x" * 100})
            reason = detection.baseline_anomaly(baseline, job, {"stdout": "x" * 5000})
            self.assertEqual(reason, "output_size_anomaly")

    def test_tag_alert(self):
        alert = {"title": "rule hit"}
        tagged = detection.tag_alert(alert, "T1059")
        self.assertEqual(tagged["technique"], "T1059")


if __name__ == "__main__":
    unittest.main()
