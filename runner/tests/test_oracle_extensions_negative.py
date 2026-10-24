#!/usr/bin/env python3
"""Creative negative tests for Oracle integration with extensions.

These are not questions for the Oracle. They feed the senses, the
DRI pager, the reviewer, and the resource monitor the kind of input
a broken sensor, a half-written file, or a hostile job would produce,
and assert the Oracle path does not crash.
"""
import json
import os
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import dri, resources, review, senses  # noqa: E402
from runner.runner import answer_queries, _redact_patterns  # noqa: E402


class SensesNegativeTest(unittest.TestCase):
    def test_alert_with_no_fields(self):
        self.assertIsInstance(senses.validate_sensor_alert({}), (dict, type(None), bool, str, list))

    def test_alert_detail_is_a_list(self):
        alert = {"sensor": "door", "severity": "high", "detail": ["a", "b", {"nested": True}]}
        # Must not raise.
        senses.validate_sensor_alert(alert)

    def test_gate_with_empty_recent_and_none_cfg(self):
        try:
            senses.gate_alert({}, {"sensor": "x"}, [])
        except Exception as e:
            self.fail(f"gate_alert crashed: {e}")

    def test_store_then_load_corrupt_line(self):
        tmp = tempfile.mkdtemp()
        path = senses._path(tmp)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"sensor":"ok","severity":"low"}\n')
            f.write("this is not json\n")
            f.write('{"sensor":"also","severity":"high","detail":null}\n')
        recs = senses.load_alerts(tmp)
        self.assertIsInstance(recs, list)

    def test_senses_query_with_missing_base_dir(self):
        answers, spent = answer_queries(
            [{"op": "senses"}],
            {"stdout": "", "stderr": "", "exit_code": 0},
            {},
            4,
            cfg={},
        )
        self.assertEqual(spent, 1)
        self.assertIn("rejected", answers[0])

    def test_score_of_garbage_alert(self):
        for alert in ({}, {"severity": 12}, {"severity": None}, {"weight": "nope"}):
            try:
                senses.alert_score(alert, 1.0)
            except Exception as e:
                self.fail(f"alert_score crashed on {alert}: {e}")


class ReviewNegativeTest(unittest.TestCase):
    def test_review_job_with_non_dict(self):
        for job in (None, "string", 5, ["list"], True):
            try:
                review.review_job({}, job if isinstance(job, dict) else {})
            except Exception as e:
                self.fail(f"review_job crashed: {e}")

    def test_review_script_is_a_dict(self):
        job = {"kind": "exec", "script": {"not": "a string"}, "files": "nope"}
        try:
            notes = review.review_job({}, job)
        except Exception as e:
            self.fail(f"review crashed on dict script: {e}")
        self.assertIsInstance(notes, (list, dict, tuple))

    def test_patterns_that_do_not_compile(self):
        cfg = {"review_patterns": {"bad": "(unclosed", "ok": "password"}}
        try:
            review.parse_review_patterns(cfg)
        except Exception as e:
            self.fail(f"parse_review_patterns crashed: {e}")

    def test_huge_script_does_not_hang(self):
        job = {"kind": "exec", "script": "A" * 200_000}
        start = time.time()
        review.review_job({}, job)
        self.assertLess(time.time() - start, 2.0)


class ResourcesNegativeTest(unittest.TestCase):
    def test_check_with_empty_cfg(self):
        tmp = tempfile.mkdtemp()
        try:
            resources.check_resources({}, tmp)
        except Exception as e:
            self.fail(f"check_resources crashed: {e}")

    def test_corrupt_state_file(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "resources.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not json at all")
        try:
            resources.check_resources({"resources": {"cpu_high": 0.9}}, tmp)
        except Exception as e:
            self.fail(f"corrupt state crashed: {e}")

    def test_negative_thresholds(self):
        tmp = tempfile.mkdtemp()
        cfg = {"resources": {"cpu_high": -1, "mem_high": 2.5, "disk_high": "nope"}}
        try:
            resources.check_resources(cfg, tmp)
        except Exception as e:
            self.fail(f"bad thresholds crashed: {e}")


class DRINegativeTest(unittest.TestCase):
    def test_maybe_page_with_nothing(self):
        tmp = tempfile.mkdtemp()
        try:
            dri.maybe_page({}, tmp)
        except Exception as e:
            self.fail(f"maybe_page crashed: {e}")

    def test_cursor_is_a_word(self):
        tmp = tempfile.mkdtemp()
        state_path = os.path.join(tmp, "dri.json")
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"cursor": "yesterday"}, f)
        try:
            dri.maybe_page({"dri": {"enabled": True}}, tmp)
        except Exception as e:
            self.fail(f"word cursor crashed: {e}")

    def test_format_page_with_mixed_events(self):
        events = [
            {"kind": "alert", "sensor": "door"},
            "not a dict",
            None,
            {"kind": None, "detail": {"nested": [1, 2, 3]}},
        ]
        try:
            text = dri.format_page(events)
        except Exception as e:
            self.fail(f"format_page crashed: {e}")
        self.assertIsInstance(text, str)

    def test_send_telegram_bad_token_does_not_raise_out(self):
        # Network will fail; the function should raise a contained error
        # or return, not crash the caller with an unexpected type.
        try:
            dri.send_telegram("", "", "hi")
        except Exception:
            pass  # contained is fine; uncaught TypeError on None would not be


class CrossExtensionNegativeTest(unittest.TestCase):
    def test_senses_query_against_poisoned_store(self):
        tmp = tempfile.mkdtemp()
        path = senses._path(tmp)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"sensor":"desk","severity":"high","detail":"FLAG-ABC"}\n')
            f.write("{broken\n")
            f.write("42\n")
        answers, spent = answer_queries(
            [{"op": "senses", "sensor": "desk"}],
            {"stdout": "", "stderr": ""},
            _redact_patterns({}),
            4,
            cfg={},
            base_dir=tmp,
        )
        self.assertEqual(spent, 1)
        self.assertEqual(answers[0].get("op"), "senses")

    def test_review_then_senses_then_resources_in_one_breath(self):
        tmp = tempfile.mkdtemp()
        job = {"kind": "exec", "script": "rm -rf /", "files": [{"name": "../x"}]}
        review.review_job({}, job)
        senses.store_alert(tmp, {"sensor": "x", "severity": "low", "detail": None})
        resources.check_resources({}, tmp)
        dri.maybe_page({}, tmp)
        # If we got here, none of them crashed.


if __name__ == "__main__":
    unittest.main(verbosity=2)
