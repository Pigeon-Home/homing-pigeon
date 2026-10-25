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


class ProcessCountLegsTest(unittest.TestCase):
    """Queue A refill: _read_process_count's
    no-/proc leg (coverage run 40189711740: lines
    144-145). A box whose /proc cannot be listed
    reports None, and the storm signal simply
    never fires there.
    """

    def test_an_unlistable_proc_is_none(self):
        real_listdir = os.listdir

        def refusing(path, *a, **k):
            if path == "/proc":
                raise OSError("no proc")
            return real_listdir(path, *a, **k)

        with mock.patch.object(os, "listdir", refusing):
            self.assertIsNone(RS._read_process_count())
        if os.path.isdir("/proc"):
            self.assertIsInstance(RS._read_process_count(), int)


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


class CpuCountersTest(unittest.TestCase):
    """Queue A: `_read_cpu_counters` never ran on Windows
    (coverage run 40183585961: 12 lines) -- the same
    shape as the memory reader above: read_live calls it
    everywhere, but /proc/stat exists only on Linux, so
    the parse never executed where the file is absent.
    Its contract from the docstring: the aggregate cpu
    line's (total, idle) jiffies, idle counting iowait
    when the kernel reports it; anything malformed or
    absent answers None.
    """

    def _counters(self, text):
        opener = mock.mock_open(read_data=text)
        with mock.patch("builtins.open", opener):
            return RS._read_cpu_counters()

    def test_the_aggregate_line_sums_and_counts_iowait(self):
        stat = ("cpu0 1 1 1 1 1 1 1 1 1 1\n"
                "cpu  100 0 100 800 20 0 5 0 0 0\n"
                "intr 12345\n")
        # Per-core lines are not the aggregate: only the
        # "cpu " line counts. idle = idle + iowait.
        self.assertEqual(self._counters(stat), (1025, 820))

    def test_a_short_line_has_no_iowait_to_count(self):
        self.assertEqual(
            self._counters("cpu 1 2 3 4\n"), (10, 4))

    def test_a_non_numeric_field_answers_none(self):
        self.assertIsNone(
            self._counters("cpu 1 2 lots 4 5\n"))

    def test_a_truncated_line_answers_none(self):
        self.assertIsNone(self._counters("cpu 1 2\n"))

    def test_no_aggregate_line_answers_none(self):
        self.assertIsNone(self._counters(
            "cpu0 1 1 1 1 1 1 1 1 1 1\nintr 9\n"))

    def test_no_stat_file_answers_none(self):
        with mock.patch("builtins.open",
                        side_effect=OSError("no /proc here")):
            self.assertIsNone(RS._read_cpu_counters())

    def test_the_host_answers_none_or_a_pair(self):
        got = RS._read_cpu_counters()
        if got is not None:
            total, idle = got
            self.assertGreater(total, 0)
            self.assertTrue(0 <= idle <= total)


class MainDeliveryLegsTest(unittest.TestCase):
    """Queue A refill: main's live-readings path and
    its two local-delivery refusals (local full-suite
    map at 93998ca: lines 485, 496, 500-503). With no
    --readings the sense reads the live machine; a
    delivery that cannot run, and one that delivers
    fewer than it was handed, are rc 2 with the state
    left unwritten."""

    def _drive(self, d, delivered, argv_extra=()):
        import io
        import json
        import os
        from contextlib import redirect_stderr
        from unittest import mock
        manifest_path = os.path.join(d, "extension.json")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump({"tunables": {}}, fh)
        state_path = os.path.join(d, "state.json")
        err = io.StringIO()
        with mock.patch.object(
                RS, "decide",
                return_value=([{"signal": "disk_full"}], {})), \
                mock.patch.object(
                    RS, "_deliver_local", return_value=delivered), \
                redirect_stderr(err):
            rc = RS.main(["--manifest", manifest_path,
                          "--state", state_path,
                          "--local-dir", d, *argv_extra])
        return rc, err.getvalue(), state_path

    def test_undeliverable_is_rc2(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rc, _err, state_path = self._drive(d, None)
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state_path))

    def test_partial_delivery_is_rc2_and_names_it(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rc, err, state_path = self._drive(d, 0)
            self.assertEqual(rc, 2)
            self.assertIn("1 of 1 alert(s) not delivered", err)
            self.assertFalse(os.path.exists(state_path))

    def test_no_readings_argument_reads_live(self):
        import json
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            manifest_path = os.path.join(d, "extension.json")
            with open(manifest_path, "w",
                      encoding="utf-8") as fh:
                json.dump({"tunables": {}}, fh)
            with mock.patch.object(
                    RS, "read_live",
                    return_value={"now": 1.0}) as live, \
                    mock.patch.object(
                        RS, "decide", return_value=([], {})):
                rc = RS.main(["--manifest", manifest_path,
                              "--state",
                              os.path.join(d, "state.json")])
            self.assertEqual(rc, 0)
            live.assert_called_once()


if __name__ == "__main__":
    unittest.main()
