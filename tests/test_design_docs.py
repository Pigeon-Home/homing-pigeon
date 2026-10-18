#!/usr/bin/env python3
"""M9/M10 tests: the design docs exist, are marked unimplemented,
and no code claims otherwise."""
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

DOCS = {
    "docs/asymmetric-signing-design.md": ["ed25519", "public_keys"],
    "docs/approval-gate-design.md": ["--approve", "pending.json"],
}


class DesignDocsTest(unittest.TestCase):
    def test_docs_exist_and_are_marked_design_only(self):
        for name in DOCS:
            path = os.path.join(REPO, name)
            self.assertTrue(os.path.exists(path), name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("Not built. See FUTURE.md.", text, name)

    def test_no_code_implements_them(self):
        # If these ever get implemented, this test should be updated
        # to test the implementation instead.
        for root, _, files in os.walk(os.path.join(REPO, "runner")):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                text = open(os.path.join(root, fn),
                            encoding="utf-8").read()
                self.assertNotIn("policy_module(homing_pigeon", text)
                self.assertNotIn("def verify_ed25519", text)
        # No --approve flag yet.
        sys.path.insert(0, os.path.join(REPO, "runner"))
        import runner as RR
        src = open(RR.__file__, encoding="utf-8").read()
        self.assertNotIn('"--approve"', src)
        self.assertNotIn("'--approve'", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
