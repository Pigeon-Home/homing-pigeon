#!/usr/bin/env python3
"""Negative tests: non-iterable queries and concurrent extension poison.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. answer_queries assumed queries was a list (or falsy). A truthy
   non-iterable (int, bool True, float, custom object) raised
   TypeError: 'int' object is not iterable (or 'bool' object is not
   iterable). That exception escaped the Oracle answer path and could
   stop processing of the job or follow-up. Non-list queries are now
   treated as empty so the agent never crashes and continues.

2. Concurrent Board submit/offer/load with mixed good and invalid
   tasks, and concurrent senses store/load with poisoned alerts, must
   not raise. Workers share state; a failure in one must not abort
   the others or the poll cycle.

3. answer_queries with mixed good and completely malformed query
   objects (None, int, set, bytes) continues, spends budget, and
   returns answers without raising.
"""
import os
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.oracle import senses  # noqa: E402
from runner.runner import (  # noqa: E402
    Board,
    answer_queries,
    _redact_patterns,
)


class NonIterableQueriesTest(unittest.TestCase):
    """Finding: non-list queries must not raise and stop the Oracle."""

    def test_non_list_queries_do_not_raise(self):
        exec_result = {"stdout": "ok", "stderr": "", "exit_code": 0}
        poisons = [
            123,
            True,
            3.14,
            object(),
            {"not": "a list"},
            set(),
            b"bytes",
            None,  # already handled, but confirm
        ]
        for q in poisons:
            try:
                answers, spent = answer_queries(
                    q, exec_result, {}, 8, cfg={}
                )
            except Exception as e:
                self.fail(f"answer_queries raised {type(e).__name__}: {e} on {q!r}")
            self.assertIsInstance(answers, list)
            self.assertGreaterEqual(spent, 0)

    def test_mixed_good_and_poison_queries_continue(self):
        queries = [
            {"op": "attest", "predicate": "exit_zero"},
            999,  # poison
            {"op": "grep", "pattern": "ok"},
            None,
            {"op": "unknown"},
            True,
        ]
        exec_result = {"stdout": "ok\nline2", "stderr": "", "exit_code": 0}
        answers, spent = answer_queries(
            queries, exec_result, _redact_patterns({}), 10, cfg={}
        )
        self.assertEqual(spent, 6)
        self.assertEqual(len(answers), 6)
        # First one answered
        self.assertEqual(answers[0].get("op"), "attest")
        # Poisons rejected
        self.assertIn("rejected", answers[1])
        self.assertIn("rejected", answers[3])
        self.assertIn("rejected", answers[5])


class ConcurrentExtensionPoisonTest(unittest.TestCase):
    """Finding: concurrent extension state mutations with poison must not crash."""

    def test_concurrent_board_submit_and_offer(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            board = Board(path)
            errors = []

            def worker(n):
                try:
                    for i in range(30):
                        # Mix valid and invalid
                        board.submit({"task_id": f"w{n}-{i}", "priority": i})
                        board.submit({"task_id": None, "priority": "bad"})  # invalid
                        board.submit({"task_id": f"w{n}-x{i}", "requires": "not-a-list"})
                        board.offer(f"worker{n}", ["cap"])
                        board.load()  # concurrent reload
                except Exception as e:
                    errors.append((n, type(e).__name__, str(e)))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [], f"board concurrent raised: {errors}")

    def test_concurrent_senses_store_and_load_poison(self):
        with tempfile.TemporaryDirectory() as d:
            errors = []

            def writer():
                for i in range(40):
                    try:
                        # Good
                        senses.store_alert(d, {
                            "sensor": "s", "severity": "high",
                            "title": f"good-{i}", "detail": {"n": i},
                        })
                        # Poison shapes
                        senses.store_alert(d, {
                            "sensor": None, "severity": 99,
                            "title": "", "detail": ["not", "dict"],
                        })
                        senses.store_alert(d, "not a dict")
                    except Exception as e:
                        errors.append(("writer", type(e).__name__, str(e)))

            def reader():
                for _ in range(40):
                    try:
                        recs = senses.load_alerts(d)
                        self.assertIsInstance(recs, list)
                        # Score garbage
                        for r in recs[:5]:
                            senses.alert_score(r, "not-float")
                            senses.alert_score(None, 1.0)
                    except Exception as e:
                        errors.append(("reader", type(e).__name__, str(e)))

            ts = [
                threading.Thread(target=writer),
                threading.Thread(target=reader),
                threading.Thread(target=reader),
            ]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertEqual(errors, [], f"senses concurrent raised: {errors}")


if __name__ == "__main__":
    unittest.main()
