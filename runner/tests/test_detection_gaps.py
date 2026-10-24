#!/usr/bin/env python3
"""Tests for the detection gaps filled by runner/oracle/detection.py.

Canary tripwires are already covered by test_canary_watch.py and
are not re-tested here.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.oracle import detection  # noqa: E402


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


class DetectionHookIntegrationTest(unittest.TestCase):
    """Finding: the job-completion hook must record hits and plan budgets."""

    def test_hook_records_hits_and_plan_budget(self):
        # Simulate the hook logic directly (the runner call site is thin).
        from runner.oracle import detection
        job = {
            "interpreter": "python2",
            "script": "eval(x)",
            "plan": [{"timeout_sec": 30}, {"timeout_sec": 30}],
        }
        result = {"stdout": "ok"}
        hits = detection.evaluate_rules(job, result)
        self.assertTrue(hits)
        tagged = [detection.tag_alert(h, h.get("technique")) for h in hits if h.get("technique")]
        self.assertTrue(any("technique" in t for t in tagged))
        allowed, reason = detection.check_plan_budget(job["plan"], {"max_plan_steps": 5})
        self.assertTrue(allowed)
        allowed, reason = detection.check_plan_budget(job["plan"], {"max_plan_steps": 1})
        self.assertFalse(allowed)


class DetectionEdgeTest(unittest.TestCase):
    def test_rules_ignore_a_shape_that_is_not_a_job(self):
        self.assertEqual(detection.evaluate_rules(None), [])
        hits = detection.evaluate_rules(
            {"script": 5, "interpreter": "sh"},
            {"stdout": 5},
            rules=["nope", {"match": "nope"},
                   {"id": "long", "match": {"stdout_len_gt": 0}}])
        self.assertEqual(hits, [])
        hits = detection.evaluate_rules(
            {"script": "echo", "interpreter": "sh"},
            {"stdout": "abcd"},
            rules=[{"id": "long", "title": "t", "technique": "T1",
                    "match": {"stdout_len_gt": 2}}])
        self.assertEqual(hits[0]["rule_id"], "long")

    def test_a_plan_that_is_not_a_list_is_refused(self):
        ok, reason = detection.check_plan_budget("nope", {})
        self.assertFalse(ok)
        self.assertIn("list", reason)
        ok, reason = detection.check_plan_budget(
            [{"timeout_sec": "nope"}, "skip", {"timeout_sec": 700}],
            {"max_plan_steps": "nope", "max_plan_timeout_sec": "nope"})
        self.assertFalse(ok)
        self.assertIn("exceeds", reason)

    def test_a_broken_baseline_file_is_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "detection-baseline.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{")
            base = detection.update_baseline(
                d, {"kind": 5}, {"stdout": 5})
            self.assertEqual(base["kinds"].get("unknown"), 1)
            with open(path, "w", encoding="utf-8") as fh:
                json_text = (
                    '{"kinds": {"exec": "nope"}, "output_sizes": "nope"}')
                fh.write(json_text)
            base = detection.update_baseline(
                d, {"kind": "exec"}, {"stdout": "ab"})
            self.assertEqual(base["kinds"]["exec"], 1)
            self.assertEqual(base["output_sizes"], [2])

    def test_a_baseline_that_cannot_be_written_is_still_returned(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "detection-baseline.json"))
            base = detection.update_baseline(d, {"kind": "exec"}, {"stdout": "a"})
            self.assertEqual(base["kinds"]["exec"], 1)

    def test_anomaly_ignores_junk_and_a_new_kind(self):
        self.assertIsNone(detection.baseline_anomaly("nope", {}, {}))
        sizes = ["x"] + [10] * 10
        self.assertIsNone(detection.baseline_anomaly(
            {"output_sizes": sizes}, {}, {"stdout": "a" * 1000}))
        kinds = {"exec": float("nan"), "ping": True, "ok": 21}
        self.assertEqual(detection.baseline_anomaly(
            {"kinds": kinds}, None, None), "new_job_kind")
        self.assertIsNone(detection.baseline_anomaly(
            {"kinds": {"exec": 21}}, {"kind": "exec"}, None))

    def test_tag_alert_accepts_a_non_object(self):
        tagged = detection.tag_alert(None, "T1041")
        self.assertEqual(tagged, {"technique": "T1041"})
