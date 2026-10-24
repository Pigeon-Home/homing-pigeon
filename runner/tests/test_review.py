#!/usr/bin/env python3
"""Tests for the Oracle's advisory pre-execution review."""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import review as RV  # noqa: E402


def _job(**kw):
    j = {"v": 1, "type": "job", "kind": "exec", "job_id": "j1",
         "script": "print('hi')"}
    j.update(kw)
    return j


def _ids(notes):
    return {n["id"] for n in notes}


class MetadataChecksTest(unittest.TestCase):
    def test_clean_job_no_notes(self):
        r = RV.review_job({}, _job())
        self.assertEqual(r["notes"], [])

    def test_no_script_source(self):
        r = RV.review_job({}, _job(script=None))
        self.assertIn("no_script_source", _ids(r["notes"]))

    def test_script_url_covers(self):
        r = RV.review_job({}, _job(script=None,
                                   script_url="https://x/y.py",
                                   script_sha384="abc"))
        self.assertNotIn("no_script_source", _ids(r["notes"]))
        self.assertNotIn("script_url_no_integrity", _ids(r["notes"]))

    def test_script_url_no_integrity(self):
        r = RV.review_job({}, _job(script=None,
                                   script_url="https://x/y.py"))
        self.assertIn("script_url_no_integrity", _ids(r["notes"]))

    def test_file_no_integrity(self):
        r = RV.review_job({}, _job(files=[{"name": "a.csv",
                                           "url": "https://x/a.csv"}]))
        self.assertIn("file_no_integrity", _ids(r["notes"]))

    def test_file_with_integrity_quiet(self):
        r = RV.review_job({}, _job(files=[{"name": "a.csv",
                                           "url": "https://x/a.csv",
                                           "sha384": "abc"}]))
        self.assertNotIn("file_no_integrity", _ids(r["notes"]))

    def test_absolute_file_name(self):
        r = RV.review_job({}, _job(files=[{"name": "/etc/passwd",
                                           "url": "https://x"}]))
        ids = _ids(r["notes"])
        self.assertIn("absolute_file_name", ids)

    def test_interpreter_not_list(self):
        r = RV.review_job({}, _job(interpreter="python3"))
        self.assertIn("interpreter_not_list", _ids(r["notes"]))

    def test_timeout_clamped(self):
        r = RV.review_job({}, _job(timeout_sec=7200))
        self.assertIn("timeout_clamped", _ids(r["notes"]))
        r2 = RV.review_job({}, _job(timeout_sec=60))
        self.assertNotIn("timeout_clamped", _ids(r2["notes"]))

    def test_shebang_mismatch(self):
        r = RV.review_job({}, _job(script="#!/bin/bash\necho hi"))
        ids = _ids(r["notes"])
        if os.name == "nt":
            self.assertIn("shebang_platform_mismatch", ids)
        else:
            self.assertNotIn("shebang_platform_mismatch", ids)

    def test_reviewed_at_present(self):
        r = RV.review_job({}, _job())
        self.assertIn("reviewed_at", r)


class ContentChecksTest(unittest.TestCase):
    def test_dangling_file_ref(self):
        r = RV.review_job(
            {}, _job(script="open('data.csv').read()"))
        self.assertIn("dangling_file_ref", _ids(r["notes"]))

    def test_staged_file_quiet(self):
        r = RV.review_job(
            {}, _job(script="open('data.csv').read()",
                     files=[{"name": "data.csv", "url": "https://x"}]))
        self.assertNotIn("dangling_file_ref", _ids(r["notes"]))

    def test_extra_pattern(self):
        cfg = {"review_patterns_extra": [
            {"id": "kf-test", "pattern": "os\\.system",
             "note": "os.system is fragile; prefer subprocess",
             "severity": "warn"}]}
        r = RV.review_job(cfg, _job(script="import os\nos.system('ls')"))
        ids = _ids(r["notes"])
        self.assertIn("kf-test", ids)
        note = next(n for n in r["notes"] if n["id"] == "kf-test")
        self.assertEqual(note["tier"], "content")
        self.assertEqual(note["severity"], "warn")

    def test_extra_pattern_no_match_quiet(self):
        cfg = {"review_patterns_extra": [
            {"id": "kf-test", "pattern": "os\\.system",
             "note": "x", "severity": "info"}]}
        r = RV.review_job(cfg, _job(script="print('hi')"))
        self.assertNotIn("kf-test", _ids(r["notes"]))

    def test_bad_pattern_config(self):
        cfg = {"review_patterns_extra": "not-a-list"}
        with self.assertRaises(RuntimeError):
            RV.parse_review_patterns(cfg)
        # review_job itself never raises: surfaces as a note
        r = RV.review_job(cfg, _job())
        self.assertIn("review_config_error", _ids(r["notes"]))

    def test_bad_regex_config(self):
        cfg = {"review_patterns_extra": [
            {"id": "x", "pattern": "(unclosed", "note": "y"}]}
        with self.assertRaises(RuntimeError):
            RV.parse_review_patterns(cfg)

    def test_warns_first(self):
        r = RV.review_job(
            {}, _job(script="open('missing.csv')",
                     script_url="https://x/y.py"))
        sev = [n["severity"] for n in r["notes"]]
        self.assertEqual(sev, sorted(sev, key=lambda s: 0 if s == "warn" else 1))


class HookTest(unittest.TestCase):
    def test_result_carries_review(self):
        # The hook attaches review_job output to results; verify the
        # wiring contract without the mail flow.
        from runner import runner as R
        self.assertIsNotNone(R._review)
        r = R._review.review_job({}, _job(timeout_sec=7200))
        self.assertIn("timeout_clamped", {n["id"] for n in r["notes"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
