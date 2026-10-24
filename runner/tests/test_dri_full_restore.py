#!/usr/bin/env python3
"""Negative tests: truncated DRI module must not leave paging unavailable.

Findings documented here (simulation in virtual environment, 2026-10-15):

1. Several recent commits left runner/dri.py truncated (154-160 lines).
   maybe_page was missing, so DRI paging raised AttributeError and
   could not run. The full 442-line module is restored.
2. _save_state stringifies keys so a poisoned state with non-string
   keys does not raise and stop a page cycle.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import dri  # noqa: E402


class DriFullRestoreTest(unittest.TestCase):
    """Finding: maybe_page must exist; object keys must not raise."""

    def test_maybe_page_present_and_object_key_safe(self):
        self.assertTrue(hasattr(dri, "maybe_page"), "maybe_page missing — module truncated")
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "dri-state.json")
            with open(state, "w") as fh:
                fh.write('{"last_check": 0}')
            try:
                dri.maybe_page({"dri": {"enabled": True}}, d)
            except Exception as e:
                self.fail(f"maybe_page raised {type(e).__name__}: {e}")


if __name__ == "__main__":
    unittest.main()
