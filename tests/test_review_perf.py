#!/usr/bin/env python3
"""M1a tests: the bounded filename scan matches the old regex and is fast."""
import os
import random
import sys
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import review as R  # noqa: E402

OLD_RE = R._OLD_FILENAME_RE


def _old_refs(script):
    return {m.group(1) for m in OLD_RE.finditer(script)}


def _new_refs(script):
    return {ref for ref, _ in R._scan_refs(script)}


class DifferentialTest(unittest.TestCase):
    """A few hundred random short strings: old and new flag the same refs."""

    def test_random_strings_match(self):
        rng = random.Random(20261015)
        pieces = ["'", '"', ".", "/", "\\", " ", "a", "Z", "0", "_", "-",
                  ".py", ".sh", ".json", ".txt", ".log", ".yaml", ".yml",
                  ".toml", ".csv", ".ps1", ".js", ".ts", ".sql", "exe",
                  "\u00e9", "\u4e2d", "\n", "\t", "x" * 30, "ab.py"]
        for i in range(500):
            s = "".join(rng.choice(pieces)
                        for _ in range(rng.randint(0, 40)))[:260]
            self.assertEqual(_old_refs(s), _new_refs(s),
                             "mismatch on %r" % s[:80])

    def test_known_cases(self):
        cases = [
            ('open("data.csv")', {"data.csv"}),
            ("x = 'a/b/c.py'", {"a/b/c.py"}),
            ('"C:\\temp\\f.txt"', {"C:\\temp\\f.txt"}),
            ('"noext"', set()),
            ('".py"', set()),
            ('"a.pyb"', set()),
            ('"a" "b.py"', {"b.py"}),
            ('"sp ace.py"', {"sp ace.py"}),
        ]
        for script, expected in cases:
            self.assertEqual(_new_refs(script), expected, script)
            self.assertEqual(_old_refs(script), expected, script)


class TimingTest(unittest.TestCase):
    def test_million_char_unclosed_quote(self):
        job = {"kind": "exec", "script": '"' + "a" * 1000000}
        t0 = time.time()
        R.review_job({}, job)
        dt = time.time() - t0
        self.assertLess(dt, 2.0, "review took %.2fs" % dt)

    def test_million_char_many_literals(self):
        job = {"kind": "exec",
               "script": ('x = "file.py"\n' * 40000)}
        t0 = time.time()
        R.review_job({}, job)
        dt = time.time() - t0
        self.assertLess(dt, 2.0, "review took %.2fs" % dt)


class ScanCapTest(unittest.TestCase):
    def test_truncation_note(self):
        job = {"kind": "exec", "script": "echo hi " + "y" * 70000}
        result = R.review_job({"review_scan_bytes": 100}, job)
        ids = [n["id"] for n in result["notes"]]
        self.assertIn("review_scan_truncated", ids)

    def test_no_truncation_note_when_short(self):
        job = {"kind": "exec", "script": 'open("a.py")'}
        result = R.review_job({}, job)
        ids = [n["id"] for n in result["notes"]]
        self.assertNotIn("review_scan_truncated", ids)

    def test_bad_scan_bytes_falls_back(self):
        self.assertEqual(R._review_scan_bytes({"review_scan_bytes": "x"}),
                         R.DEFAULT_REVIEW_SCAN_BYTES)
        self.assertEqual(R._review_scan_bytes({"review_scan_bytes": -5}),
                         R.DEFAULT_REVIEW_SCAN_BYTES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
