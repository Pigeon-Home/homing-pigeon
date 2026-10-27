# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""The hourly query window (PROTOCOL section 11) counts the slots of
the last hour and nothing else (Q88, found by blueMonday's query
target with a window file as a crash left it): a time in the
future -- a clock set back, a poisoned file -- counted as live for
as long as it stayed ahead of the clock and held the sender at the
cap, and a time that is not a finite number counted once. Neither
is a slot now; the rest of the window is read as before."""

import json
import os
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.runner import _live_times, check_rate_limit  # noqa: E402

CFG = {"max_queries_per_hour": 2}


class LiveTimesTest(unittest.TestCase):
    def test_only_finite_times_of_the_last_hour_are_slots(self):
        now = 1_800_000_000.0
        self.assertEqual(
            _live_times([now - 1, now - 3599, now - 3600, now - 7200,
                         now, now + 1, now + 86400, 1.0,
                         float("inf"), float("-inf"), float("nan"),
                         "x", None, [], {}, "1e400", str(now - 2)], now),
            [now - 1, now - 3599, now, now - 2])
        self.assertEqual(_live_times("not a list", now), [])
        self.assertEqual(_live_times(None, now), [])


class WindowFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="hp-window-")
        self.path = os.path.join(self.dir, "query_times.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, times):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"": times}))

    def _stored(self):
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)[""]

    def test_a_future_window_does_not_hold_the_sender_at_the_cap(self):
        self._write([time.time() + 86400] * 4)
        self.assertTrue(check_rate_limit("", CFG, self.path))
        self.assertTrue(check_rate_limit("", CFG, self.path))
        self.assertFalse(check_rate_limit("", CFG, self.path))
        self.assertEqual(len(self._stored()), 2)
        for t in self._stored():
            self.assertLess(t, time.time() + 1)

    def test_a_window_that_is_not_numbers_is_empty(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write('{"": [1e400, -1e400, "soon", null, true, 1.0]}')
        self.assertTrue(check_rate_limit("", CFG, self.path, peek=True))
        self.assertTrue(check_rate_limit("", CFG, self.path))
        self.assertEqual(len(self._stored()), 1)

    def test_a_real_window_still_caps(self):
        self._write([time.time() - 10, time.time() - 20])
        self.assertFalse(check_rate_limit("", CFG, self.path, peek=True))
        self.assertFalse(check_rate_limit("", CFG, self.path))
        self.assertTrue(check_rate_limit("other", CFG, self.path))


if __name__ == "__main__":
    unittest.main()
