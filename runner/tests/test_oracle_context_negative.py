#!/usr/bin/env python3
"""Negative cases for oracle_context under concurrent poisoned retained files.

Finding: oracle_context with non-string base_dir, bad limit/max_chars,
and concurrent readers while files are being rewritten with garbage
or non-JSON does not raise. It returns a string (empty or partial).
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import oracle_context  # noqa: E402


class OracleContextNegative(unittest.TestCase):
    def test_bad_args(self):
        """Finding: non-string base_dir, non-int limit/max_chars return
        a string without raising."""
        self.assertEqual(oracle_context(None), "")
        self.assertEqual(oracle_context(123), "")
        with tempfile.TemporaryDirectory() as d:
            ctx = oracle_context(d, limit="lots", max_chars=None)
            self.assertIsInstance(ctx, str)
            ctx = oracle_context(d, limit=-5, max_chars="bad")
            self.assertIsInstance(ctx, str)

    def test_concurrent_poisoned_retained(self):
        """Finding: concurrent oracle_context while threads rewrite
        retained/*.json with garbage or non-JSON do not raise."""
        with tempfile.TemporaryDirectory() as d:
            ret = os.path.join(d, "retained")
            os.makedirs(ret)
            for i in range(5):
                with open(os.path.join(ret, f"job{i}.json"), "w") as f:
                    json.dump({"stdout": f"out{i}"}, f)
            stop = threading.Event()
            errors = []

            def poison():
                while not stop.is_set():
                    try:
                        with open(os.path.join(ret, "job0.json"), "w") as f:
                            f.write("not json" if os.path.getsize(os.path.join(ret, "job0.json")) % 2 == 0 else "[1]")
                        with open(os.path.join(ret, "bad..id.json"), "w") as f:
                            f.write("{}")
                    except Exception:
                        pass
                    time.sleep(0.001)

            def reader():
                try:
                    for _ in range(15):
                        ctx = oracle_context(d, limit=3, max_chars=100)
                        self.assertIsInstance(ctx, str)
                except Exception as e:
                    errors.append(e)

            t = threading.Thread(target=poison, daemon=True)
            t.start()
            threads = [threading.Thread(target=reader) for _ in range(4)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            stop.set()
            t.join(timeout=1)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
