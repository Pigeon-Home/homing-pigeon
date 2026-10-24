#!/usr/bin/env python3
"""Negative cases for confinement snapshot and local inference ask.

Findings: concurrent snapshot_outside with poisoned exclude lists,
non-string workspace roots, and ask_model with non-dict cfg or
non-loopback endpoints must not raise. Processing continues.
"""
import os
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import snapshot_outside, ask_model, check_protected_paths  # noqa: E402


class ConfinementAndAskNegative(unittest.TestCase):
    def test_snapshot_poisoned_exclude_and_root(self):
        """Finding: non-list exclude, non-string entries, and non-dir
        workspace_root return empty snap without raising."""
        snap = snapshot_outside(None, exclude="not-a-list")
        self.assertEqual(snap, {})
        snap = snapshot_outside(123, exclude=[1, None, "ok"])
        self.assertEqual(snap, {})
        with tempfile.TemporaryDirectory() as d:
            snap = snapshot_outside(d, exclude=[None, 5, os.path.join(d, "missing")])
            self.assertIsInstance(snap, dict)

    def test_concurrent_snapshots(self):
        """Finding: concurrent snapshot_outside calls on the same tree
        do not raise even with mixed bad excludes."""
        with tempfile.TemporaryDirectory() as d:
            errors = []
            def worker():
                try:
                    snapshot_outside(d, exclude=[None, "bad", d])
                    snapshot_outside("/tmp", exclude="string")
                except Exception as e:
                    errors.append(e)
            threads = [threading.Thread(target=worker) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

    def test_check_protected_bad_types(self):
        """Finding: non-list protected, non-dict before/after return [] without raising."""
        changed = check_protected_paths(None, "not-dict", "not-list")
        self.assertEqual(changed, [])
        changed = check_protected_paths({"a": 1}, {}, [None, 5, ""])
        self.assertEqual(changed, [])

    def test_ask_model_bad_cfg(self):
        """Finding: non-dict cfg, missing endpoint, non-loopback endpoint
        return a rejected dict without raising."""
        ans = ask_model(None, "q", "out", 100)
        self.assertEqual(ans.get("rejected"), "inference_unconfigured")
        ans = ask_model({"endpoint": "http://evil.com", "model": "m"}, "q", "out", 100)
        self.assertEqual(ans.get("rejected"), "inference_unconfigured")
        ans = ask_model({"endpoint": "http://127.0.0.1:1", "model": "m"}, None, None, "bad")
        self.assertIn("rejected", ans)


if __name__ == "__main__":
    unittest.main()
