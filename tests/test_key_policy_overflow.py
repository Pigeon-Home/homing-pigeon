#!/usr/bin/env python3
"""Negative tests: extreme floats in key policy must not crash.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. check_key_policy did int(timeout_sec) and int(max_timeout_sec).
   float("inf") raised OverflowError and escaped the policy gate.
   A poisoned key policy from config or an extension could abort
   a job instead of rejecting it. OverflowError is now caught and
   the check returns a rejection string so the agent continues.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import check_key_policy  # noqa: E402


class KeyPolicyOverflowTest(unittest.TestCase):
    """Finding: inf/-inf in max_timeout_sec must not raise."""

    def test_inf_max_timeout_does_not_raise(self):
        policies = {"k": {"max_timeout_sec": float("inf")}}
        job = {"kind": "exec", "timeout_sec": 30}
        try:
            reason = check_key_policy(policies, "k", {}, job)
        except OverflowError as e:
            self.fail(f"check_key_policy raised: {e}")
        self.assertIsInstance(reason, str)
        self.assertIn("invalid", reason.lower())

    def test_inf_timeout_sec_does_not_raise(self):
        policies = {"k": {"max_timeout_sec": 60}}
        job = {"kind": "exec", "timeout_sec": float("inf")}
        try:
            reason = check_key_policy(policies, "k", {}, job)
        except OverflowError as e:
            self.fail(f"check_key_policy raised: {e}")
        self.assertIsInstance(reason, str)


if __name__ == "__main__":
    unittest.main()
