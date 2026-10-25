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

from runner.oracle import resources as RS  # noqa: E402


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


class SaveStateFallbacksTest(unittest.TestCase):
    """Queue A refill: the resource monitor's state-save
    fallbacks (coverage run 40187685363: the non-dict
    state line unrun on Windows; the chmod swallow and
    the failure-cleanup lines unrun on both). The
    sampler's contract, from the function's own
    comments: a value that cannot be stored must not
    stop the sample, and the save is best-effort -- a
    chmod failure still leaves the state written, and
    a write failing after the temp file opens closes
    the descriptor, removes the temp, and raises
    nothing. The two flag lines in the residue are the
    platform pair (O_NOFOLLOW inapplicable on Windows,
    O_BINARY on Linux), each covered where it applies.
    """

    def _saved(self, d):
        with open(os.path.join(d, RS.STATE_FILE),
                  encoding="utf-8") as fh:
            return json.load(fh)

    def test_a_non_dict_state_saves_an_empty_object(self):
        with tempfile.TemporaryDirectory() as d:
            RS._save_state(d, ["not", "a", "dict"])
            self.assertEqual(self._saved(d), {})

    def test_a_chmod_failure_still_saves(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    os, "chmod",
                    side_effect=OSError("no chmod")):
                RS._save_state(d, {"cpu": 12.5})
            self.assertEqual(self._saved(d), {"cpu": 12.5})

    def test_an_fdopen_failure_cleans_up_and_saves_nothing(self):
        opened, closed = [], []
        real_open, real_close = os.open, os.close

        def tracking_open(path, flags, mode=0o777):
            fd = real_open(path, flags, mode)
            opened.append(fd)
            return fd

        def tracking_close(fd):
            closed.append(fd)
            return real_close(fd)

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(os, "open", tracking_open), \
                    mock.patch.object(os, "close",
                                      tracking_close), \
                    mock.patch.object(
                        os, "fdopen",
                        side_effect=OSError("cannot wrap")):
                RS._save_state(d, {"cpu": 12.5})
            self.assertFalse(os.path.exists(
                os.path.join(d, RS.STATE_FILE)))
            self.assertEqual(
                [n for n in os.listdir(d)
                 if n.startswith(RS.STATE_FILE)], [])
        self.assertEqual(len(opened), 1)
        self.assertEqual(closed, opened)

    def test_a_close_failure_during_cleanup_is_swallowed(self):
        real_close = os.close

        def raising_close(fd):
            real_close(fd)
            raise OSError("close says no")

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(os, "close",
                                   raising_close), \
                    mock.patch.object(
                        os, "fdopen",
                        side_effect=OSError("cannot wrap")):
                RS._save_state(d, {"cpu": 12.5})
            self.assertFalse(os.path.exists(
                os.path.join(d, RS.STATE_FILE)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
