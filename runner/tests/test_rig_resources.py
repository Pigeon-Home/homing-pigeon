# Tests for runner/tools/rig_resources.py: the one-line resource
# report the campaign ledger carries with every run.
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c

import importlib.util
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "rig_resources", os.path.join(ROOT, "runner", "tools", "rig_resources.py"))
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)


class CountersTest(unittest.TestCase):

    def test_busy_percent_from_jiffies(self):
        # 300 of 400 jiffies were busy between the two samples.
        self.assertAlmostEqual(rr.busy_percent((100, 1000), (400, 1400)), 75.0)
        self.assertIsNone(rr.busy_percent(None, (1, 2)))
        self.assertIsNone(rr.busy_percent((1, 2), (1, 2)))

    def test_hms(self):
        self.assertEqual(rr.hms(5), "5s")
        self.assertEqual(rr.hms(372), "6m12s")
        self.assertEqual(rr.hms(3723), "1h02m03s")

    def test_verdict_bands(self):
        self.assertEqual(rr.verdict(88, 90), "on target")
        self.assertEqual(rr.verdict(69, 90), "under-driven")
        self.assertEqual(rr.verdict(99, 90), "over")
        self.assertEqual(rr.verdict(None, 90), "n/a")


class LineTest(unittest.TestCase):

    def test_the_line_has_every_field_in_order(self):
        line = rr.format_line("2026-10-25T12:00:00Z", 8, 88.4, 372.0,
                              2463.0, 412 * 1024, 61.2, 23.4, 0, 90)
        self.assertEqual(
            line,
            "resources 2026-10-25T12:00:00Z: cores 8 | box cpu 88% | "
            "wall 6m12s | cmd cpu 41m03s = 6.6 cores busy | peak rss 412 MB "
            "| mem used 61% | disk free 23.4 GB | exit 0 | on target")

    def test_missing_counters_read_na_not_zero(self):
        line = rr.format_line("t", 2, None, 1.0, None, None, None, None, None, 90)
        self.assertIn("box cpu n/a", line)
        self.assertIn("cmd -", line)
        self.assertIn("mem used n/a", line)
        self.assertIn("exit -", line)
        self.assertTrue(line.endswith("| n/a"))


class RunTest(unittest.TestCase):

    def test_wraps_a_command_and_passes_its_exit_code(self):
        out = io.StringIO()
        rc = rr.run([sys.executable, "-c", "import sys; sys.exit(3)"], 90, out=out)
        self.assertEqual(rc, 3)
        line = out.getvalue().strip()
        self.assertTrue(line.startswith("resources "), line)
        self.assertIn("| exit 3 |", line)
        self.assertEqual(line.count("|"), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
