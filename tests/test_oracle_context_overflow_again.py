#!/usr/bin/env python3
"""Negative tests: extreme floats in oracle_context must not crash.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. oracle_context did int(limit) and int(max_chars). float("inf")
   raised OverflowError and escaped the local Oracle context path.
   A poisoned limit from an ask or page could abort the chat.
   OverflowError is now caught and falls back to the defaults.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import oracle_context  # noqa: E402


class OracleContextOverflowAgainTest(unittest.TestCase):
    """Finding: inf/-inf limit or max_chars must not raise."""

    def test_inf_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            ret = os.path.join(d, "retained")
            os.makedirs(ret)
            with open(os.path.join(ret, "job1.json"), "w") as fh:
                fh.write('{"stdout": "hello", "kind": "exec"}')
            for v in (float("inf"), float("-inf")):
                try:
                    ctx = oracle_context(d, limit=v, max_chars=v)
                except OverflowError as e:
                    self.fail(f"oracle_context raised on {v}: {e}")
                self.assertIsInstance(ctx, str)


if __name__ == "__main__":
    unittest.main()
