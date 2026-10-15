#!/usr/bin/env python3
"""Negative tests: extreme floats in ask_model must not crash.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. ask_model did int(max_chars). float("inf") raised OverflowError
   and escaped the local inference path. A poisoned max_chars from
   a query or config could abort an ask instead of falling back.
   OverflowError is now caught.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import ask_model  # noqa: E402


class _DummyOpener:
    def __call__(self, req, timeout=60):
        class R:
            def read(self, n):
                return b'{"choices":[{"message":{"content":"ok"}}]}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
        return R()


class AskModelOverflowTest(unittest.TestCase):
    """Finding: inf/-inf max_chars must not raise."""

    def test_inf_max_chars_does_not_raise(self):
        cfg = {"endpoint": "http://127.0.0.1:11434", "model": "m"}
        for v in (float("inf"), float("-inf")):
            try:
                r = ask_model(cfg, "why?", "output", v, opener=_DummyOpener())
            except OverflowError as e:
                self.fail(f"ask_model raised on {v}: {e}")
            self.assertIsInstance(r, dict)
            self.assertEqual(r.get("op"), "ask")


if __name__ == "__main__":
    unittest.main()
