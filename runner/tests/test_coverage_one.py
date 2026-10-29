"""The one coverage command prints one line from a report."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from runner.tools import coverage_one  # noqa: E402


class OneLineTest(unittest.TestCase):
    def test_the_line_names_statements_branches_and_the_gap(self):
        report = {"totals": {
            "num_statements": 100, "missing_lines": 7,
            "num_branches": 40, "missing_branches": 3,
            "percent_covered": 93.0}}
        line = coverage_one.one_line(report)
        self.assertIn("statements 100", line)
        self.assertIn("never executed 7", line)
        self.assertIn("branches 40", line)
        self.assertIn("never taken 3", line)
        self.assertIn("93.0%", line)

    def test_a_report_without_totals_still_prints(self):
        line = coverage_one.one_line({})
        self.assertIn("statements 0", line)
        self.assertIn("0.0%", line)


if __name__ == "__main__":
    unittest.main()
