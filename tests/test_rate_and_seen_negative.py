#!/usr/bin/env python3
"""Negative concurrency cases for rate-limit store and seen file.

Findings: concurrent check_rate_limit with a poisoned query_times.json,
non-string key_ids, and concurrent save_seen of mixed types must not
raise or stop subsequent checks. The poll continues.
"""
import os
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import check_rate_limit, save_seen, load_seen  # noqa: E402


class RateAndSeenNegative(unittest.TestCase):
    def test_rate_limit_poisoned_store(self):
        """Finding: query_times.json that is a list, a string, or invalid
        JSON is treated as empty; check_rate_limit does not raise."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "query_times.json")
            open(path, "w").write("[1, 2, 3]")
            ok = check_rate_limit("k1", {"max_queries_per_hour": 5}, path)
            self.assertTrue(ok)
            open(path, "w").write('"string"')
            ok = check_rate_limit(None, {"max_queries_per_hour": 5}, path)
            self.assertIsInstance(ok, bool)
            open(path, "w").write("{bad")
            ok = check_rate_limit("k2", {"max_queries_per_hour": "lots"}, path)
            self.assertIsInstance(ok, bool)

    def test_concurrent_rate_limit_poison(self):
        """Finding: threads hammering check_rate_limit while another
        rewrites the store with garbage do not raise."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "query_times.json")
            stop = threading.Event()
            errors = []

            def poison():
                while not stop.is_set():
                    try:
                        open(path, "w").write("null\n" if os.path.getsize(path) % 2 == 0 else "[1]")
                    except Exception:
                        pass

            def checker():
                try:
                    for _ in range(20):
                        check_rate_limit("worker", {"max_queries_per_hour": 10}, path)
                except Exception as e:
                    errors.append(e)

            t = threading.Thread(target=poison, daemon=True)
            t.start()
            threads = [threading.Thread(target=checker) for _ in range(4)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            stop.set()
            t.join(timeout=1)
            self.assertEqual(errors, [])

    def test_seen_concurrent_mixed(self):
        """Finding: concurrent save_seen / load_seen of non-dict seen
        maps do not raise; load returns {} on garbage."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            errors = []

            def writer():
                try:
                    save_seen(path, {"a": True, "b": 1})
                    save_seen(path, "not-a-dict")
                    save_seen(path, None)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=writer) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            loaded = load_seen(path)
            self.assertIsInstance(loaded, dict)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
