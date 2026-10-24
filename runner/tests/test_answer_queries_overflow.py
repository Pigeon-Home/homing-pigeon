#!/usr/bin/env python3
"""Negative tests: extreme floats must not crash the Oracle answer path.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. answer_queries did int(budget), int(already_spent), int(max_matches),
   int(lines), and int(max_chars). float("inf") and float("-inf") raised
   OverflowError. A poisoned query or budget from an extension escaped
   the Oracle answer path and could stop processing. OverflowError is
   now caught and falls back to the safe defaults so the agent continues.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import answer_queries  # noqa: E402


class AnswerQueriesOverflowTest(unittest.TestCase):
    """Finding: inf/-inf budget or per-query limits must not raise."""

    def test_inf_budget_does_not_raise(self):
        exec_result = {"stdout": "ok", "stderr": "", "exit_code": 0}
        for b in (float("inf"), float("-inf")):
            try:
                answers, spent = answer_queries(
                    [{"op": "attest", "predicate": "exit_zero"}],
                    exec_result, {}, b,
                )
            except OverflowError as e:
                self.fail(f"budget {b} raised OverflowError: {e}")
            self.assertIsInstance(answers, list)

    def test_inf_max_matches_and_lines_do_not_raise(self):
        exec_result = {"stdout": "line1\nline2\nok", "stderr": "", "exit_code": 0}
        queries = [
            {"op": "grep", "pattern": "line", "max_matches": float("inf")},
            {"op": "tail", "lines": float("inf")},
            {"op": "grep", "pattern": "x", "max_matches": float("-inf")},
        ]
        try:
            answers, spent = answer_queries(queries, exec_result, {}, 10)
        except OverflowError as e:
            self.fail(f"query limit raised OverflowError: {e}")
        self.assertEqual(len(answers), 3)


if __name__ == "__main__":
    unittest.main()
