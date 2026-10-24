#!/usr/bin/env python3
"""Tests for low-overhead detection helpers.

Covers canary tripwires, Sigma/YARA-style rules, plan budgets,
and the tiny statistical baseline. All designed for SELinux-like
cost: evaluated only at decision points.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import detection  # noqa: E402


class LowOverheadDetectionTest(unittest.TestCase):
    def test_canary_tripwire(self):
        # The detection module's own canary helpers were dropped when
        # the two detection branches were combined: the shipped
        # tripwire is runner._canary_watch (runner-planted, persistent
        # trips, CRLF-safe) and the gaps module defers to it. This test
        # keeps the original intent -- an edit to a planted tripwire
        # file is detected and reported -- against the shipped watch.
        from runner import runner as R
        with tempfile.TemporaryDirectory() as d:
            R._canary_watch(d)  # plants the canaries
            path = os.path.join(d, "canaries", "passwords.txt")
            self.assertTrue(os.path.exists(path))
            # mutate
            with open(path, "a", encoding="utf-8") as f:
                f.write("tampered\n")
            out = R._canary_watch(d)
            self.assertIn("TRIPPED", out)
            self.assertIn("passwords.txt", out)

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
            # extreme output
            reason = detection.baseline_anomaly(baseline, job, {"stdout": "x" * 5000})
            self.assertEqual(reason, "output_size_anomaly")

    def test_tag_alert(self):
        alert = {"title": "canary hit"}
        tagged = detection.tag_alert(alert, "T1070.004")
        self.assertEqual(tagged["technique"], "T1070.004")


if __name__ == "__main__":
    unittest.main()
