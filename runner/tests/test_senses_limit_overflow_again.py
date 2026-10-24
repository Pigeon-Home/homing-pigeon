#!/usr/bin/env python3
"""Negative tests: extreme floats in senses limit must not crash.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. load_alerts did int(limit). float("inf") raised OverflowError
   and escaped the senses query path under concurrent load.
   A poisoned limit could abort an answer. OverflowError is now
   caught and falls back to the default.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import senses  # noqa: E402


class SensesLimitOverflowAgainTest(unittest.TestCase):
    """Finding: inf/-inf limit must not raise."""

    def test_inf_limit_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            senses.store_alert(d, {
                "sensor": "s", "severity": "high", "title": "t", "detail": {},
            })
            for v in (float("inf"), float("-inf")):
                try:
                    recs = senses.load_alerts(d, limit=v)
                except OverflowError as e:
                    self.fail(f"load_alerts raised on {v}: {e}")
                self.assertIsInstance(recs, list)


if __name__ == "__main__":
    unittest.main()
