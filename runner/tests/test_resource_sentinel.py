#!/usr/bin/env python3
"""Queue A: resource-sentinel's memory reader.

`_read_mem_avail_pct` never ran on Windows (coverage run
40180268696: 19 lines) -- read_live calls it on every
platform, but /proc/meminfo only exists on Linux, so on
Windows the OSError answer was the only line that ever
executed there and the parse itself was never exercised.
Its seam is the one file, scripted here: MemAvailable as a
percent of MemTotal, rounded; either value missing or
unparseable, a zero total, or no file at all answers None
-- the reading is absent, never an error and never a
made-up number.
"""
import importlib.util
import os
import sys
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions",
                           "resource-sentinel")


def _load():
    spec = importlib.util.spec_from_file_location(
        "resource_sentinel_example",
        os.path.join(EXAMPLE_DIR, "resource_sentinel.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RS = _load()

MEMINFO = """MemTotal:        1000000 kB
MemFree:          100000 kB
MemAvailable:     250000 kB
Buffers:           50000 kB
"""


class MemAvailTest(unittest.TestCase):
    def _pct(self, text):
        opener = mock.mock_open(read_data=text)
        with mock.patch("builtins.open", opener):
            return RS._read_mem_avail_pct()

    def test_available_as_a_percent_of_total(self):
        self.assertEqual(self._pct(MEMINFO), 25.0)

    def test_no_available_line_answers_none(self):
        self.assertIsNone(self._pct("MemTotal: 1000000 kB\n"))

    def test_a_zero_total_answers_none(self):
        self.assertIsNone(self._pct(
            "MemTotal: 0 kB\nMemAvailable: 0 kB\n"))

    def test_an_unparseable_value_is_missing_not_fatal(self):
        self.assertIsNone(self._pct(
            "MemTotal: lots kB\nMemAvailable: 250000 kB\n"))
        self.assertIsNone(self._pct(
            "MemTotal: 1000000 kB\nMemAvailable: some kB\n"))

    def test_no_meminfo_answers_none(self):
        with mock.patch("builtins.open",
                        side_effect=OSError("no /proc here")):
            self.assertIsNone(RS._read_mem_avail_pct())

    def test_the_host_answers_none_or_a_percent(self):
        got = RS._read_mem_avail_pct()
        if got is not None:
            self.assertTrue(0.0 <= got <= 100.0)


if __name__ == "__main__":
    unittest.main()
