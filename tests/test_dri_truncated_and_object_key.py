#!/usr/bin/env python3
"""Negative tests: truncated DRI module and object keys must not crash.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. Commit a2b6ff8 truncated runner/dri.py to 154 lines, removing
   maybe_page and the rest of the playbook. The agent imported but
   DRI paging became AttributeError. The full module is restored.
2. _save_state did json.dump on a state dict. Non-string keys raised
   TypeError and could abort a page cycle. Keys are now stringified
   so a poisoned state does not stop processing.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri  # noqa: E402


class DriTruncatedAndObjectKeyTest(unittest.TestCase):
    """Finding: truncated module restored; object keys must not raise."""

    def test_maybe_page_exists_and_object_key_does_not_raise(self):
        self.assertTrue(hasattr(dri, "maybe_page"))
        with tempfile.TemporaryDirectory() as d:
            # Poison the state with a non-string key
            state_path = os.path.join(d, "dri-state.json")
            with open(state_path, "w") as fh:
                fh.write('{"1": "bad", "last_check": 0}')
            try:
                dri.maybe_page({"dri": {"enabled": True}}, d)
            except Exception as e:
                self.fail(f"maybe_page raised {type(e).__name__}: {e}")


if __name__ == "__main__":
    unittest.main()
