#!/usr/bin/env python3
"""Negative cases for DRI format_page and evaluate_page_triggers.

Findings: format_page of non-list / non-dict events returns a string
without raising. evaluate_page_triggers with bad dcfg, non-numeric
since/now, and a poisoned events file returns a list without raising.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri  # noqa: E402


class DriFormatAndEvaluateNegative(unittest.TestCase):
    def test_format_page_bad_events(self):
        """Finding: non-list events, non-dict items, missing keys
        produce a string (or empty) without raising."""
        text = dri.format_page(None)
        self.assertIsInstance(text, str)
        text = dri.format_page("not-a-list")
        self.assertIsInstance(text, str)
        text = dri.format_page([None, 5, {"title": "ok"}, {"bad": {1, 2}}])
        self.assertIsInstance(text, str)

    def test_evaluate_bad_inputs(self):
        """Finding: non-dict dcfg, non-numeric since/now, and a
        poisoned security-events.jsonl return a list without raising."""
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "security-events.jsonl"), "w").write("not json\n[1]\n")
            events = dri.evaluate_page_triggers(None, d, "bad", "also-bad")
            self.assertIsInstance(events, list)
            events = dri.evaluate_page_triggers({"triggers": "not-dict"}, d, 0, None)
            self.assertIsInstance(events, list)
            events = dri.evaluate_page_triggers({"enabled": True, "triggers": {}}, d, 0, 1)
            self.assertIsInstance(events, list)


if __name__ == "__main__":
    unittest.main()
