#!/usr/bin/env python3
"""Negative tests: extreme floats in query budget must not crash.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. query_budget did int(query_budget) and int(max_query_budget).
   float("inf") raised OverflowError and escaped the budget calculation.
   A poisoned result_policy or config could abort a job instead of
   falling back to the default. OverflowError is now caught.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import query_budget  # noqa: E402


class QueryBudgetOverflowTest(unittest.TestCase):
    """Finding: inf/-inf query budget must not raise."""

    def test_inf_query_budget_does_not_raise(self):
        for v in (float("inf"), float("-inf")):
            try:
                r = query_budget(
                    {"max_query_budget": v},
                    {"result_policy": {"query_budget": v}},
                )
            except OverflowError as e:
                self.fail(f"query_budget raised on {v}: {e}")
            self.assertIsInstance(r, int)
            self.assertGreaterEqual(r, 0)


if __name__ == "__main__":
    unittest.main()
