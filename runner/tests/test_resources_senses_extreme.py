#!/usr/bin/env python3
"""Extreme concurrent negative cases for resources and senses.

Findings: concurrent check_resources with a poisoned resources.json
and bad config does not raise. Concurrent store_alert / load_alerts
while the senses.jsonl is being truncated or rewritten with garbage
do not raise; load returns a list.
"""
import os
import sys
import tempfile
import threading
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import resources, senses  # noqa: E402


class ResourcesSensesExtreme(unittest.TestCase):
    def test_concurrent_resources_poison(self):
        """Finding: concurrent check_resources while the state file
        is rewritten with garbage or non-dict does not raise."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "resources.json")
            open(path, "w").write("null")
            cfg = {"resources": {"enabled": True, "threshold": 0.1, "cooldown_sec": 0}}
            stop = threading.Event()
            errors = []

            def poison():
                while not stop.is_set():
                    try:
                        open(path, "w").write("[1]" if os.path.getsize(path) % 2 == 0 else "not json")
                    except Exception:
                        pass
                    time.sleep(0.001)

            def checker():
                try:
                    for _ in range(20):
                        resources.check_resources(cfg, d)
                        resources.check_resources({"resources": "bad"}, d)
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

    def test_concurrent_senses_truncate(self):
        """Finding: concurrent store_alert and load_alerts while the
        file is truncated or rewritten with partial lines do not raise."""
        with tempfile.TemporaryDirectory() as d:
            stop = threading.Event()
            errors = []

            def poison():
                while not stop.is_set():
                    try:
                        path = senses._path(d)
                        with open(path, "w") as f:
                            f.write('{"sensor":"x"')  # partial
                        with open(path, "a") as f:
                            f.write("\ngarbage\n")
                    except Exception:
                        pass
                    time.sleep(0.001)

            def worker():
                try:
                    for i in range(10):
                        senses.store_alert(d, {"sensor": "s", "title": f"t{i}", "severity": "info"})
                        recs = senses.load_alerts(d, limit=5)
                        self.assertIsInstance(recs, list)
                except Exception as e:
                    errors.append(e)

            t = threading.Thread(target=poison, daemon=True)
            t.start()
            threads = [threading.Thread(target=worker) for _ in range(4)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            stop.set()
            t.join(timeout=1)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
