#!/usr/bin/env python3
"""Tests for the detection gaps filled by runner/oracle/detection.py.

Canary tripwires are already covered by test_canary_watch.py and
are not re-tested here.
"""
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.oracle import detection  # noqa: E402
from runner.tests._compat import lenient_tempdir  # noqa: E402


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


class UpdateBaselineBranchesTest(unittest.TestCase):
    """Queue A: the defensive branches of update_baseline
    (coverage run 40180268696: 14 lines on Windows, 8 on
    Linux). The baseline file is the box's own record and
    may be absent, corrupt, oddly shaped, or a symlink;
    the update must still answer the current baseline,
    count the kind, keep only integer size samples, and
    leave no staging file behind when the write fails.
    One branch is not chased: the not-a-dict reset after
    the load (the load only ever assigns a dict or the
    default), which is unreachable by construction.
    """

    def _seed(self, d, obj):
        path = os.path.join(d, "detection-baseline.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path

    def test_a_bad_base_dir_answers_empty(self):
        self.assertEqual(detection.update_baseline("", {"kind": "exec"}), {})
        self.assertEqual(detection.update_baseline(None, {"kind": "exec"}), {})

    def test_a_non_dict_kinds_member_is_reset(self):
        with tempfile.TemporaryDirectory() as d:
            self._seed(d, {"kinds": "not-a-dict", "output_sizes": [],
                           "updated": 0})
            got = detection.update_baseline(d, {"kind": "exec"})
            self.assertEqual(got["kinds"], {"exec": 1})

    def test_junk_size_samples_are_dropped_ints_kept(self):
        with tempfile.TemporaryDirectory() as d:
            self._seed(d, {"kinds": {}, "output_sizes": [10, "big", None, 20],
                           "updated": 0})
            got = detection.update_baseline(
                d, {"kind": "exec"}, {"stdout": "x" * 30})
            self.assertEqual(got["output_sizes"], [10, 20, 30])

    def test_a_non_list_sizes_member_starts_over(self):
        with tempfile.TemporaryDirectory() as d:
            self._seed(d, {"kinds": {}, "output_sizes": "not-a-list",
                           "updated": 0})
            got = detection.update_baseline(
                d, {"kind": "exec"}, {"stdout": "abcd"})
            self.assertEqual(got["output_sizes"], [4])

    def test_a_symlink_baseline_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target.json")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"kinds": {"exec": 99}}')
            path = os.path.join(d, "detection-baseline.json")
            os.symlink(target, path)
            got = detection.update_baseline(d, {"kind": "ping"})
            self.assertEqual(got["kinds"], {"ping": 1})
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), '{"kinds": {"exec": 99}}')
            self.assertFalse(os.path.islink(path))

    def test_a_failed_replace_keeps_the_answer_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "detection-baseline.json")
            os.makedirs(path)
            got = detection.update_baseline(d, {"kind": "exec"})
            self.assertEqual(got["kinds"], {"exec": 1})
            leftovers = [n for n in os.listdir(d) if ".tmp." in n]
            self.assertEqual(leftovers, [])

    def test_a_failed_chmod_does_not_fail_the_update(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    detection.os, "chmod",
                    side_effect=OSError("mode refused")):
                got = detection.update_baseline(d, {"kind": "exec"})
            self.assertEqual(got["kinds"], {"exec": 1})
            self.assertTrue(os.path.isfile(
                os.path.join(d, "detection-baseline.json")))

    def test_the_cleanup_swallows_its_own_failures(self):
        from unittest import mock
        real_unlink = os.unlink
        calls = {"tmp": 0}

        def unlink(path, *a, **kw):
            if ".tmp." in str(path):
                calls["tmp"] += 1
                if calls["tmp"] > 1:
                    raise OSError("staging file stuck")
            return real_unlink(path, *a, **kw)

        # ignore_cleanup_errors: the scripted close failure
        # leaks the staging fd on purpose, and Windows will
        # not unlink a file this process still holds open.
        with lenient_tempdir() as d:
            with mock.patch.object(detection.os, "fdopen",
                                   side_effect=OSError("no writer")), \
                    mock.patch.object(detection.os, "close",
                                      side_effect=OSError("stuck fd")), \
                    mock.patch.object(detection.os, "unlink",
                                      side_effect=unlink):
                got = detection.update_baseline(d, {"kind": "exec"})
            self.assertEqual(got["kinds"], {"exec": 1})

    def test_a_failed_open_closes_the_fd_and_cleans_up(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(detection.os, "fdopen",
                                   side_effect=OSError("no writer")):
                got = detection.update_baseline(d, {"kind": "exec"})
            self.assertEqual(got["kinds"], {"exec": 1})
            leftovers = [n for n in os.listdir(d) if ".tmp." in n]
            self.assertEqual(leftovers, [])

if __name__ == "__main__":
    unittest.main()
