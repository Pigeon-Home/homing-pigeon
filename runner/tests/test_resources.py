#!/usr/bin/env python3
"""Tests for the built-in resource monitor."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import resources as RS  # noqa: E402


class ParseTest(unittest.TestCase):
    def test_defaults_on(self):
        rcfg = RS.parse_resources({})
        self.assertTrue(rcfg["enabled"])
        self.assertEqual(rcfg["threshold"], 0.95)

    def test_disable(self):
        rcfg = RS.parse_resources({"resources": {"enabled": False}})
        self.assertFalse(rcfg["enabled"])

    def test_bad_threshold(self):
        with self.assertRaises(RuntimeError):
            RS.parse_resources({"resources": {"threshold": 1.5}})
        with self.assertRaises(RuntimeError):
            RS.parse_resources({"resources": {"threshold": 0}})

    def test_bad_shape(self):
        with self.assertRaises(RuntimeError):
            RS.parse_resources({"resources": ["x"]})


class SampleTest(unittest.TestCase):
    def test_disk_fraction(self):
        with tempfile.TemporaryDirectory() as d:
            v = RS._disk_fraction(d)
            self.assertIsNotNone(v)
            self.assertTrue(0 <= v <= 1)

    def test_cpu_needs_two_samples(self):
        # synthetic: deterministic
        v = RS._cpu_percent((100, 1000), (150, 1100))
        self.assertAlmostEqual(v, 0.5)
        self.assertIsNone(RS._cpu_percent(None, (150, 1100)))
        self.assertIsNone(RS._cpu_percent((100, 1000), (100, 1000)))
        # live read shape
        live = RS._read_proc_stat()
        if live is None:
            self.skipTest("no /proc/stat")
        self.assertEqual(len(live), 2)

    def test_mem_fraction(self):
        v = RS._mem_fraction()
        if v is None:
            self.skipTest("no /proc/meminfo")
        self.assertTrue(0 <= v <= 1)


class CheckTest(unittest.TestCase):
    def test_threshold_crossing(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"resources": {"threshold": 0.0001, "cooldown_sec": 0}}
            # tiny threshold: disk (always > 0) trips immediately
            event = RS.check_resources(cfg, d)
            self.assertIsNotNone(event)
            self.assertEqual(event["type"], "resource_pressure")
            self.assertIn("disk", event["resources"])

    def test_cooldown_suppresses(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"resources": {"threshold": 0.0001, "cooldown_sec": 3600}}
            # Pin the samplers: on a loaded box the real CPU reads 1.0
            # on the second call (no baseline the first time, so no
            # cooldown entry yet) and the test flakes.
            with mock.patch.object(RS, "_read_proc_stat",
                                   return_value=(1000, 2000)), \
                 mock.patch.object(RS, "_mem_fraction",
                                   return_value=0.5), \
                 mock.patch.object(RS, "_disk_fraction",
                                   return_value=0.5):
                self.assertIsNotNone(RS.check_resources(cfg, d))
                self.assertIsNone(RS.check_resources(cfg, d))

    def test_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"resources": {"enabled": False, "threshold": 0.0}}
            self.assertIsNone(RS.check_resources(cfg, d))

    def test_high_threshold_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"resources": {"threshold": 1.0, "cooldown_sec": 0}}
            # 1.0 is exclusive: nothing can reach it
            self.assertIsNone(RS.check_resources(cfg, d))

    def test_state_file_written(self):
        with tempfile.TemporaryDirectory() as d:
            RS.check_resources({}, d)
            st = json.load(open(os.path.join(d, "resources.json")))
            self.assertIn("checked_at", st)


if __name__ == "__main__":
    unittest.main(verbosity=2)
