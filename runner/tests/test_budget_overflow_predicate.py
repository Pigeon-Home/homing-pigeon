#!/usr/bin/env python3
"""Negative tests: extreme floats in budget must not crash with bad predicates.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. answer_queries did int(budget). float("inf") raised OverflowError
   even when a predicate's equality raised. The budget conversion
   escaped before the predicate guard. OverflowError is now caught
   so a poisoned budget does not stop processing.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import answer_queries  # noqa: E402


class _BadEq:
    def __eq__(self, other):
        raise RuntimeError("eq")
    def __hash__(self):
        return 0


class BudgetOverflowPredicateTest(unittest.TestCase):
    """Finding: inf budget must not raise even with a bad predicate."""

    def test_inf_budget_with_bad_predicate_does_not_raise(self):
        try:
            answers, spent = answer_queries(
                [{"op": "attest", "predicate": _BadEq()}],
                {"stdout": "ok", "exit_code": 0},
                {},
                float("inf"),
            )
        except OverflowError as e:
            self.fail(f"answer_queries raised: {e}")
        self.assertIsInstance(answers, list)


if __name__ == "__main__":
    unittest.main()
