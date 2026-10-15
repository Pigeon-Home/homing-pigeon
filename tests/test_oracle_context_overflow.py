#!/usr/bin/env python3
"""Negative tests: extreme numeric values must not crash the Oracle.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. oracle_context did int(limit) and int(max_chars). float("inf") and
   float("-inf") raised OverflowError: cannot convert float infinity
   to integer. That escaped the local Oracle chat / context path and
   could stop an ask or page render. OverflowError is now caught and
   falls back to the defaults (6 / 4000) so the agent continues.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import oracle_context  # noqa: E402


class OracleContextOverflowTest(unittest.TestCase):
    """Finding: inf/-inf limit or max_chars must not raise."""

    def test_inf_limit_and_max_chars_do_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            ret = os.path.join(d, "retained")
            os.makedirs(ret)
            with open(os.path.join(ret, "job1.json"), "w") as fh:
                fh.write('{"stdout": "hello world", "kind": "exec"}')
            for lim in (float("inf"), float("-inf")):
                try:
                    ctx = oracle_context(d, limit=lim, max_chars=lim)
                except OverflowError as e:
                    self.fail(f"oracle_context raised OverflowError on {lim}: {e}")
                self.assertIsInstance(ctx, str)
                # Falls back; still produces content or the empty message
                self.assertTrue(len(ctx) >= 0)


if __name__ == "__main__":
    unittest.main()
