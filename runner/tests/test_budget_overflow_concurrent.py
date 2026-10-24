#!/usr/bin/env python3
"""Negative tests: extreme floats in budget must not crash under concurrency.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. answer_queries and the retained follow-up path did int(budget)
   and int(spent). float("inf") raised OverflowError under concurrent
   poison queries and escaped the Oracle answer path. OverflowError
   is now caught so processing continues.
"""
import os
import sys
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import answer_queries  # noqa: E402


class BudgetOverflowConcurrentTest(unittest.TestCase):
    """Finding: inf/-inf budget must not raise even under concurrent calls."""

    def test_inf_budget_concurrent_does_not_raise(self):
        errors = []
        def worker():
            for _ in range(10):
                try:
                    answer_queries(
                        [{"op": "attest", "predicate": "exit_zero"}],
                        {"stdout": "ok", "exit_code": 0},
                        {},
                        float("inf"),
                    )
                except OverflowError as e:
                    errors.append(str(e))
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], f"OverflowError escaped: {errors}")


if __name__ == "__main__":
    unittest.main()
