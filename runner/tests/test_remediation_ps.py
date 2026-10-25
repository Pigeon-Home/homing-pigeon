"""The ps-based tree sampler: Darwin and the BSDs see a job's whole
process tree (docs/use/questions.md Q38).

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

Linux reads /proc and Windows the toolhelp snapshot; everywhere
else there is no stdlib route to the process table, so one `ps`
per sample gives pid, parent, resident set and accumulated CPU
time. These tests pin the parsing with a fake ps, the dispatch per
platform, and -- where ps exists, which is every POSIX CI leg --
the sampler against a real tree of children.
"""
import os
import shutil
import subprocess
import sys
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner.oracle import remediation as R  # noqa: E402


class _Done:
    def __init__(self, stdout):
        self.stdout = stdout
        self.returncode = 0


def _fake_ps(text):
    def run(cmd, **kw):
        assert list(cmd) == list(R._PS_ARGS), cmd
        return _Done(text)
    return run


class CpuTimeTest(unittest.TestCase):
    def test_the_three_shapes_ps_prints(self):
        self.assertAlmostEqual(R._cpu_seconds("0:00.05"), 0.05)
        self.assertAlmostEqual(R._cpu_seconds("12:34.56"), 754.56)
        self.assertEqual(R._cpu_seconds("1:02:03"), 3723.0)
        self.assertEqual(R._cpu_seconds("2-01:00:00"), 176400.0)
        self.assertEqual(R._cpu_seconds("00:00:00"), 0.0)

    def test_nonsense_is_none(self):
        self.assertIsNone(R._cpu_seconds("x"))
        self.assertIsNone(R._cpu_seconds(""))
        self.assertIsNone(R._cpu_seconds(None))


class PsTableTest(unittest.TestCase):
    TABLE = (
        "    1     0   1234  0:01.00\n"
        "  100     1   2048  0:00.10\n"
        "  101   100   4096  0:00.20\n"
        "  102   100      -  0:00.30\n"       # rss unreadable
        "  bad   100   4096  0:00.30\n"       # not a pid
        "  103   101   8192  junk\n"          # cpu unreadable
        "short line\n"
    )

    def test_rows_parse_and_bad_cells_degrade(self):
        table = R._ps_table(_fake_ps(self.TABLE))
        self.assertEqual(sorted(table), [1, 100, 101, 102, 103])
        self.assertEqual(table[101], (100, 4096 * 1024, 0.2))
        self.assertEqual(table[102], (100, None, 0.3))
        self.assertEqual(table[103], (101, 8192 * 1024, 0.0))

    def test_a_failing_ps_is_an_empty_table(self):
        def boom(cmd, **kw):
            raise OSError("no ps")
        self.assertEqual(R._ps_table(boom), {})

        def timeout(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, 10)
        self.assertEqual(R._ps_table(timeout), {})
        self.assertEqual(R._ps_table(_fake_ps(None)), {})

    def test_the_sample_is_the_root_and_its_descendants(self):
        sample = R.sample_tree_ps(100, _fake_ps(self.TABLE))
        self.assertEqual(sorted(sample), [100, 101, 102, 103])
        self.assertEqual(sample[101], (0.2, 4096 * 1024))
        self.assertEqual(sample[102], (0.3, None))
        self.assertNotIn(1, sample)

    def test_a_root_ps_does_not_list_is_still_the_root(self):
        sample = R.sample_tree_ps(999, _fake_ps(self.TABLE))
        self.assertEqual(sample, {999: (0.0, None)})
        sample = R.sample_tree_ps(999, _fake_ps(""))
        self.assertEqual(sample, {999: (0.0, None)})


class DispatchTest(unittest.TestCase):
    def test_windows_linux_and_the_rest(self):
        calls = []
        with mock.patch.object(R, "sample_tree_windows",
                               lambda pid: calls.append("windows") or {}), \
                mock.patch.object(R, "sample_tree_posix",
                                  lambda pid: calls.append("posix") or {}), \
                mock.patch.object(R, "sample_tree_ps",
                                  lambda pid: calls.append("ps") or {}):
            with mock.patch.object(R.os, "name", "nt"):
                R.sample_tree(1)
            with mock.patch.object(R.os, "name", "posix"), \
                    mock.patch.object(R.sys, "platform", "linux"), \
                    mock.patch.object(R.os.path, "isdir", lambda p: True):
                R.sample_tree(1)
            with mock.patch.object(R.os, "name", "posix"), \
                    mock.patch.object(R.sys, "platform", "darwin"), \
                    mock.patch.object(R, "_ps_available", lambda: True):
                R.sample_tree(1)
            with mock.patch.object(R.os, "name", "posix"), \
                    mock.patch.object(R.sys, "platform", "freebsd14"), \
                    mock.patch.object(R, "_ps_available", lambda: True):
                R.sample_tree(1)
            with mock.patch.object(R.os, "name", "posix"), \
                    mock.patch.object(R.sys, "platform", "darwin"), \
                    mock.patch.object(R, "_ps_available", lambda: False):
                self.assertEqual(R.sample_tree(7), {7: (0.0, None)})
        self.assertEqual(calls, ["windows", "posix", "ps", "ps"])


@unittest.skipUnless(os.name == "posix" and shutil.which("ps"),
                     "ps and a POSIX shell")
class LivePsTest(unittest.TestCase):
    def test_a_real_tree_of_children_is_seen(self):
        proc = subprocess.Popen(["sh", "-c", "sleep 5 & sleep 5 & wait"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            sample = {}
            while time.monotonic() < deadline:
                sample = R.sample_tree_ps(proc.pid)
                if len(sample) >= 3:
                    break
                time.sleep(0.1)
            self.assertIn(proc.pid, sample)
            self.assertGreaterEqual(len(sample), 3, sample)
            for pid, (cpu, rss) in sample.items():
                self.assertGreaterEqual(cpu, 0.0)
                self.assertTrue(rss is None or rss > 0, (pid, rss))
        finally:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    unittest.main()
