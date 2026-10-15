#!/usr/bin/env python3
"""Additional negative tests from concurrent simulation of the agent and Oracle.

Findings: the agent and Oracle fail gracefully on bad extension data,
concurrent access, and poisoned state files. None of the cases below
stopped processing or raised out of the public entry points.

Documented so future regressions are caught.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri, resources, review, senses  # noqa: E402
from runner.runner import Board, poll_once, answer_queries  # noqa: E402

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"


class ConcurrentPoisonSimulationTest(unittest.TestCase):
    """Finding: concurrent calls against poisoned board, senses, DRI,
    resources, and review do not raise. Processing continues.
    """

    def test_concurrent_poisoned_state_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            # Poison the on-disk stores the extensions read.
            with open(os.path.join(d, "board.json"), "w") as f:
                f.write('{"t1": "not-a-dict", "t2": null, "123": {}}')
            with open(os.path.join(d, "senses.jsonl"), "w") as f:
                f.write("not json\n{\"sensor\": 123}\n{\"severity\": null}\n")
            with open(os.path.join(d, "dri-state.json"), "w") as f:
                f.write('["list"]')
            with open(os.path.join(d, "resources.json"), "w") as f:
                f.write('"string"')
            with open(os.path.join(d, "security-events.jsonl"), "w") as f:
                f.write("{not json}\nnull\n")

            cfg = {
                "mailbox_user": "a@b.c",
                "shared_secret": SECRET,
                "sensors": {"bad": {"enabled": True, "key_id": "k",
                                    "profile": "not-dict"}},
                "dri": {"enabled": True, "triggers": "not-dict"},
                "resources": {"threshold": "lots"},
                "review_patterns_extra": [{"pattern": "("}],
            }
            seen = {}
            seen_path = os.path.join(d, "seen.json")
            errors = []

            def worker(n):
                try:
                    # Mocked mail so the poll does not try the network.
                    poll_once(
                        cfg, d, seen, seen_path,
                        imap=mock.Mock(
                            search=lambda *a: ("OK", [b""]),
                            logout=lambda: None,
                        ),
                        smtp=mock.Mock(quit=lambda: None),
                        opts=type("O", (), {"dry_run": False, "no_send": True})(),
                    )
                    Board(os.path.join(d, "board.json"))
                    senses.load_alerts(d)
                    dri.maybe_page(cfg, d)
                    resources.check_resources(cfg, d)
                    review.review_job(cfg, {"kind": "exec", "script": None,
                                            "files": "bad"})
                except Exception as e:
                    errors.append((n, type(e).__name__, str(e)))

            threads = [threading.Thread(target=worker, args=(i,))
                       for i in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [], f"concurrent poison raised: {errors}")


class AnswerQueriesPoisonTest(unittest.TestCase):
    """Finding: answer_queries tolerates a non-list of queries, non-dict
    items, and bad nested values. It rejects and continues.
    """

    def test_non_list_and_bad_items_do_not_raise(self):
        cases = [
            None,
            "not-a-list",
            123,
            [None, 1, "str", {"op": None}, {"op": "grep", "pattern": "("},
             {"op": "ask", "question": None, "max_chars": "lots"},
             {"op": "senses", "sensor": 99}],
        ]
        for queries in cases:
            try:
                answers, spent = answer_queries(
                    queries, {"stdout": "out", "exit_code": 0},
                    {}, 4, cfg={}, view="full",
                )
                self.assertIsInstance(answers, list)
                self.assertIsInstance(spent, int)
            except Exception as e:
                self.fail(f"answer_queries raised on {queries!r}: {e}")


class BoardConcurrentSaveLoadTest(unittest.TestCase):
    """Finding: Board.load filters non-dict tasks and non-string keys.
    Concurrent save/load with poisoned content does not crash.
    """

    def test_concurrent_board_with_poison(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            errors = []

            def writer():
                try:
                    b = Board(path)
                    b.submit({"task_id": "ok", "kind": "ping"})
                    # Overwrite with poison while others load.
                    with open(path, "w") as f:
                        f.write('{"bad": "string", "also": null}')
                except Exception as e:
                    errors.append(("writer", e))

            def reader():
                try:
                    Board(path)
                except Exception as e:
                    errors.append(("reader", e))

            threads = [threading.Thread(target=writer)]
            threads += [threading.Thread(target=reader) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [], f"board concurrent raised: {errors}")


if __name__ == "__main__":
    unittest.main()
