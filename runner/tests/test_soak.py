# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""The soak harness: a short real run, and its judge on known shapes.

runner/tools/soak.py runs poll_once against an in-memory mailbox
for as long as it is told and fails on growth. soak.yml runs it for
two hours on a schedule; here it runs long enough to prove the
harness drives real jobs, and the judge is pinned on samples whose
answer is known.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _load_tool():
    path = os.path.join(ROOT, "runner", "tools", "soak.py")
    spec = importlib.util.spec_from_file_location("soak_tool", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SOAK = _load_tool()


def _rows(n, **grow):
    rows = []
    for i in range(n):
        row = {"cycle": i + 1, "jobs": 3 * (i + 1), "sent": 3,
               "rss_mb": 30.0, "fds": 4, "threads": 1, "children": 0,
               "state_bytes": 1000 * i, "state_files": i,
               "log_bytes": 1000}
        for key, per_cycle in grow.items():
            row[key] = row[key] + per_cycle * i
        rows.append(row)
    return rows


class JudgeTest(unittest.TestCase):
    def test_flat_is_ok(self):
        self.assertEqual(SOAK.judge(_rows(100), jobs_per_cycle=3), [])

    def test_state_growth_is_not_judged(self):
        self.assertEqual(SOAK.judge(_rows(100, state_bytes=5000),
                                    jobs_per_cycle=3), [])

    def test_each_kind_of_growth_is_named(self):
        cases = {"rss_mb": (0.5, "resident memory"),
                 "fds": (1, "file descriptors"),
                 "threads": (1, "threads")}
        for key, (per_cycle, words) in cases.items():
            with self.subTest(key=key):
                failures = SOAK.judge(_rows(100, **{key: per_cycle}),
                                      jobs_per_cycle=3)
                self.assertTrue(any(words in f for f in failures), failures)

    def test_an_unreaped_child_and_a_missing_result(self):
        rows = _rows(50)
        rows[-1]["children"] = 1
        rows[10]["sent"] = 2
        failures = SOAK.judge(rows, jobs_per_cycle=3)
        self.assertTrue(any("not reaped" in f for f in failures), failures)
        self.assertTrue(any("fewer results" in f for f in failures), failures)

    def test_a_log_past_its_rotation_cap(self):
        rows = _rows(50)
        rows[20]["log_bytes"] = SOAK.LOG_CAP * (SOAK.LOG_BACKUPS + 2)
        self.assertTrue(any("runner.log" in f
                            for f in SOAK.judge(rows, jobs_per_cycle=3)))

    def test_too_short_to_judge(self):
        self.assertTrue(SOAK.judge(_rows(3), jobs_per_cycle=3))


@unittest.skipIf(os.name == "nt", "exec jobs run sh; the soak's own leg is Linux")
class ShortSoakTest(unittest.TestCase):
    def test_thirty_cycles_run_real_jobs_and_nothing_grows(self):
        base = tempfile.mkdtemp(prefix="hp-soak-test-")
        saved = (SOAK.R._LOG_FILE, SOAK.R._LOG_MAX_BYTES,
                 SOAK.R._LOG_BACKUPS)
        try:
            samples, growth = SOAK.run(cycles=30, jobs_per_cycle=3,
                                       base=base)
        finally:
            (SOAK.R._LOG_FILE, SOAK.R._LOG_MAX_BYTES,
             SOAK.R._LOG_BACKUPS) = saved
            shutil.rmtree(base, ignore_errors=True)
        self.assertEqual(len(samples), 30)
        self.assertEqual({r["sent"] for r in samples}, {3})
        self.assertGreater(growth, 0)  # results really were retained
        # Memory is judged only by the long run: 30 cycles is warm-up.
        self.assertEqual(SOAK.judge(samples, rss_mb=float("inf"),
                                    jobs_per_cycle=3), [])


if __name__ == "__main__":
    unittest.main()
