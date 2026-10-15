#!/usr/bin/env python3
"""Additional findings: paths that previously raised on bad extension data
now fail gracefully. Documented after the concurrency-poison suite
showed the raises no longer occur.
"""
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import senses, resources, dri
from runner.runner import answer_queries, build_attestations, _redact_patterns


class MoreGracefulFindings(unittest.TestCase):
    def test_answer_queries_bad_already_spent(self):
        """Finding: already_spent='lots' no longer raises ValueError."""
        answers, spent = answer_queries([], {}, {}, 8, already_spent="lots")
        self.assertIsInstance(answers, list)

    def test_build_attestations_non_dict_query(self):
        """Finding: non-dict query no longer raises AttributeError."""
        atts = build_attestations(["not-a-dict"], {"exit_code": 0, "digest": "x", "patterns": {}})
        self.assertEqual(atts, [])

    def test_gate_alert_bad_profile(self):
        """Finding: non-numeric cooldown_sec / max_per_hour no longer raise."""
        reason = senses.gate_alert({"profile": {"cooldown_sec": "hot"}}, {"title": "t"}, [])
        self.assertIsInstance(reason, (str, type(None)))

    def test_store_alert_non_serializable(self):
        """Finding: non-serializable detail no longer raises TypeError."""
        with tempfile.TemporaryDirectory() as d:
            senses.store_alert(d, {"sensor": "s", "detail": {1, 2}})  # set
            # Must not raise

    def test_senses_load_bad_limit(self):
        """Finding: limit='many' no longer raises ValueError."""
        with tempfile.TemporaryDirectory() as d:
            recs = senses.load_alerts(d, limit="many")
            self.assertIsInstance(recs, list)


if __name__ == "__main__":
    unittest.main()
