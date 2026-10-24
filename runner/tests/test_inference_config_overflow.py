#!/usr/bin/env python3
"""Negative tests: extreme floats in inference config must not crash.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. inference_config did int(max_answer_chars) and int(timeout_sec).
   float("inf") raised OverflowError and escaped config loading.
   A poisoned inference block could prevent the Oracle from starting
   instead of treating inference as unconfigured. OverflowError is
   now caught and the function returns None.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import inference_config  # noqa: E402


class InferenceConfigOverflowTest(unittest.TestCase):
    """Finding: inf/-inf in inference config must not raise."""

    def test_inf_max_answer_chars_does_not_raise(self):
        cfg = {
            "inference": {
                "endpoint": "http://127.0.0.1:11434",
                "model": "m",
                "max_answer_chars": float("inf"),
                "timeout_sec": float("inf"),
            }
        }
        try:
            r = inference_config(cfg)
        except OverflowError as e:
            self.fail(f"inference_config raised: {e}")
        # Falls back to unconfigured
        self.assertIsNone(r)


if __name__ == "__main__":
    unittest.main()
