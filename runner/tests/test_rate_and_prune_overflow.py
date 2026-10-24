#!/usr/bin/env python3
"""Negative tests: extreme floats must not crash rate limit or prune.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. _query_limit (used by check_rate_limit) did int(max_queries_per_hour).
   float("inf") raised OverflowError and escaped the rate-limit path.
2. prune_retained did int(days). float("inf") raised OverflowError and
   could abort a poll cycle. Both now catch OverflowError and fall
   back so the agent continues.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import check_rate_limit, prune_retained  # noqa: E402


class RateAndPruneOverflowTest(unittest.TestCase):
    """Finding: inf/-inf must not raise in rate limit or prune."""

    def test_inf_rate_limit_does_not_raise(self):
        for v in (float("inf"), float("-inf")):
            try:
                check_rate_limit("k", {"max_queries_per_hour": v})
            except OverflowError as e:
                self.fail(f"rate limit raised on {v}: {e}")

    def test_inf_prune_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            for v in (float("inf"), float("-inf")):
                try:
                    prune_retained(d, v)
                except OverflowError as e:
                    self.fail(f"prune raised on {v}: {e}")


if __name__ == "__main__":
    unittest.main()
