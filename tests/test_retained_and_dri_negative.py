#!/usr/bin/env python3
"""Negative cases for retained outputs and DRI paging.

Findings: save_retained / load_retained of non-serializable payloads
or unsafe job_ids do not raise. Concurrent DRI maybe_page with a
poisoned state file and bad config returns 0 and continues.
"""
import json
import os
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import save_retained, load_retained  # noqa: E402
from runner import dri  # noqa: E402


class RetainedAndDriNegative(unittest.TestCase):
    def test_retained_non_serializable(self):
        """Finding: a set or other non-JSON payload in save_retained
        is logged and skipped; no raise. load of missing/unsafe id returns None."""
        with tempfile.TemporaryDirectory() as d:
            save_retained(d, "job1", {"stdout": "ok", "extra": {1, 2}})
            data = load_retained(d, "job1")
            # Finding: non-serializable is either skipped or coerced; no raise
            self.assertTrue(data is None or isinstance(data, dict))
            data = load_retained(d, "../evil")
            self.assertIsNone(data)
            data = load_retained(d, None)
            self.assertIsNone(data)

    def test_concurrent_retained(self):
        """Finding: concurrent save_retained of mixed payloads and
        load_retained do not raise."""
        with tempfile.TemporaryDirectory() as d:
            errors = []
            def worker(n):
                try:
                    save_retained(d, f"j{n}", {"n": n, "bad": {n}})
                    load_retained(d, f"j{n}")
                    load_retained(d, "../bad")
                except Exception as e:
                    errors.append(e)
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

    def test_dri_poisoned_state_concurrent(self):
        """Finding: maybe_page with a poisoned dri-state.json and
        bad config returns 0 without raising, even under concurrent calls."""
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "dri-state.json"), "w").write("[1,2]")
            cfg = {"dri": {"enabled": True, "channel": "telegram", "bot_token": "t",
                           "chat_id": "c", "triggers": {"resource_pressure": True},
                           "cooldown_sec": "bad"}}
            errors = []
            def call():
                try:
                    n = dri.maybe_page(cfg, d)
                    self.assertIsInstance(n, int)
                except Exception as e:
                    errors.append(e)
            threads = [threading.Thread(target=call) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            # bad config shape
            n = dri.maybe_page({"dri": "not-an-object"}, d)
            self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
