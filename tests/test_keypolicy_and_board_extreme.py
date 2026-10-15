#!/usr/bin/env python3
"""Extreme negative cases for key policies and Board under concurrency.

Findings: check_key_policy with non-dict policies, non-dict jobs,
and non-list allowed_kinds returns a reason string without raising.
Concurrent Board.submit/offer of malformed tasks (null ids, non-list
capabilities, non-numeric priority) do not raise.
"""
import os
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import check_key_policy, Board  # noqa: E402


class KeyPolicyAndBoardExtreme(unittest.TestCase):
    def test_key_policy_bad_shapes(self):
        """Finding: non-dict policies, non-dict job, non-list allowed_kinds
        return a reason instead of raising."""
        reason = check_key_policy("not-a-dict", "k", {}, {"kind": "exec"})
        self.assertIsInstance(reason, str)
        reason = check_key_policy({}, "k", {}, "not-a-job")
        self.assertIsInstance(reason, str)
        reason = check_key_policy({"k": {"allowed_kinds": "exec"}}, "k", {}, {"kind": "exec"})
        self.assertIsInstance(reason, str)
        reason = check_key_policy({"k": {"allowed_kinds": ["exec"]}}, "k", {}, {"kind": "ping"})
        self.assertIsInstance(reason, str)

    def test_concurrent_board_extreme(self):
        """Finding: concurrent submit of null/bad tasks and offer with
        non-list capabilities do not raise."""
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            errors = []

            def worker(n):
                try:
                    board.submit({"task_id": None, "priority": "bad", "capabilities": 5})
                    board.submit({"task_id": f"t{n}", "capabilities": [1, None], "priority": n})
                    board.offer(f"w{n}", [None, "ok"], f"k{n}")
                    board.offer(f"w{n}", "not-list", f"k{n}")
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            # Board still usable
            ok, msg = board.submit({"task_id": "final", "priority": 1})
            self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
