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


class InferenceConfigPassthroughTest(unittest.TestCase):
    """Q-new-12: agent_wall_clock_sec and keep_alive are documented
    inference keys (configuring-oracle.md) read downstream from the
    normalized dict, so inference_config must pass them through
    when present, and must not fabricate them when absent."""

    def _cfg(self, **extra):
        inf = {"endpoint": "http://127.0.0.1:11434", "model": "m"}
        inf.update(extra)
        return {"inference": inf}

    def test_both_keys_present_are_passed_through(self):
        r = inference_config(self._cfg(agent_wall_clock_sec=123,
                                       keep_alive="15m"))
        self.assertIsNotNone(r)
        self.assertEqual(r["agent_wall_clock_sec"], 123)
        self.assertEqual(r["keep_alive"], "15m")

    def test_absent_keys_are_not_fabricated(self):
        r = inference_config(self._cfg())
        self.assertIsNotNone(r)
        self.assertNotIn("agent_wall_clock_sec", r)
        self.assertNotIn("keep_alive", r)

    def test_each_key_passes_through_on_its_own(self):
        r = inference_config(self._cfg(agent_wall_clock_sec=45))
        self.assertEqual(r["agent_wall_clock_sec"], 45)
        self.assertNotIn("keep_alive", r)
        r = inference_config(self._cfg(keep_alive="5m"))
        self.assertEqual(r["keep_alive"], "5m")
        self.assertNotIn("agent_wall_clock_sec", r)

    def test_fail_closed_behaviour_unchanged_with_both_keys(self):
        # A non-loopback endpoint is still refused, keys or not.
        cfg = self._cfg(agent_wall_clock_sec=123, keep_alive="15m")
        cfg["inference"]["endpoint"] = "http://192.0.2.1:11434"
        self.assertIsNone(inference_config(cfg))
        # Missing model still yields None.
        cfg = self._cfg(agent_wall_clock_sec=123, keep_alive="15m")
        del cfg["inference"]["model"]
        self.assertIsNone(inference_config(cfg))


if __name__ == "__main__":
    unittest.main()
