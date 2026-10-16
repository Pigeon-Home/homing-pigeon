#!/usr/bin/env python3
"""Negative tests: extreme floats in retained budget must not crash.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. answer_queries and the retained follow-up path did int(budget) and
   int(spent). float("inf") raised OverflowError and escaped the
   Oracle answer path. A poisoned retained budget could abort a
   follow-up query. OverflowError is now caught.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import answer_queries  # noqa: E402


class RetainedBudgetOverflowTest(unittest.TestCase):
    """Finding: inf/-inf budget must not raise."""

    def test_inf_budget_does_not_raise(self):
        exec_result = {"stdout": "ok", "exit_code": 0}
        for v in (float("inf"), float("-inf")):
            try:
                answers, spent = answer_queries(
                    [{"op": "attest", "predicate": "exit_zero"}],
                    exec_result, {}, v,
                )
            except OverflowError as e:
                self.fail(f"answer_queries raised on {v}: {e}")
            self.assertIsInstance(answers, list)


if __name__ == "__main__":
    unittest.main()
