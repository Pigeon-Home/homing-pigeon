#!/usr/bin/env python3
"""Parity tests for the hardening milestones (M0).

Default behavior must not change: no security block, all features
off, and all features audit must produce identical mail outputs.
At M0 no feature calls sec_decide, so the audit log must stay absent.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from tests.security_parity import (  # noqa: E402
    all_audit_block,
    all_off_block,
    build_corpus,
    run_variant,
)


class ParityTest(unittest.TestCase):
    def test_no_block_off_audit_identical(self):
        corpus = build_corpus()
        base = run_variant(None, corpus)
        off = run_variant(all_off_block(), corpus)
        audit = run_variant(all_audit_block(), corpus)
        self.assertEqual(base["sent"], off["sent"])
        self.assertEqual(base["flagged"], off["flagged"])
        self.assertEqual(base["seen"], off["seen"])
        self.assertEqual(off["sent"], audit["sent"])
        self.assertEqual(off["flagged"], audit["flagged"])
        self.assertEqual(off["seen"], audit["seen"])
        # M0: nothing calls sec_decide yet; no audit log may exist.
        self.assertIsNone(base["audit_lines"])
        self.assertIsNone(off["audit_lines"])
        self.assertIsNone(audit["audit_lines"])
        # The corpus actually exercised the runner.
        self.assertTrue(base["sent"], "corpus produced no mail output")
        self.assertIn("parity-01", base["seen"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
