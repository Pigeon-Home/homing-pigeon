# Tests for tools/run_tests_parallel.py, the sharded suite runner
# that takes the Windows CI build from ~5 minutes toward ~3.
#
# The sharding math is pinned directly; the runner's contract
# (every discovered test runs exactly once, a failing module
# fails the run, zero discovered tests is an error and never a
# silent green) is pinned against fake packages on disk, driven
# through the same discovery and subprocess paths CI will use.

import importlib.util
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "run_tests_parallel",
    os.path.join(REPO, "tools", "run_tests_parallel.py"))
rtp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rtp)


def _write(root, name, body):
    with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
        fh.write(body)


_PASS = (
    "import unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_one(self):\n"
    "        self.assertTrue(True)\n"
)
_PASS2 = _PASS + (
    "    def test_two(self):\n"
    "        self.assertTrue(True)\n"
)
_FAIL = (
    "import unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_bad(self):\n"
    "        self.assertTrue(False)\n"
)
_BROKEN = "raise RuntimeError('import boom')\n"


class ShardModulesTest(unittest.TestCase):
    COUNTS = {"tests.a": 100, "tests.b": 50, "tests.c": 50,
              "tests.d": 1}

    def test_every_module_exactly_once(self):
        shards = rtp.shard_modules(dict(self.COUNTS), 2)
        flat = [m for shard in shards for m in shard]
        self.assertEqual(sorted(flat), sorted(self.COUNTS))
        self.assertEqual(len(flat), len(set(flat)))

    def test_greedy_balance(self):
        shards = rtp.shard_modules(dict(self.COUNTS), 2)
        loads = sorted(sum(self.COUNTS[m] for m in shard)
                       for shard in shards)
        self.assertEqual(loads, [100, 101])

    def test_deterministic_regardless_of_input_order(self):
        a = rtp.shard_modules(dict(self.COUNTS), 3)
        b = rtp.shard_modules(
            dict(reversed(list(self.COUNTS.items()))), 3)
        self.assertEqual(a, b)
        self.assertEqual(a, rtp.shard_modules(dict(self.COUNTS), 3))

    def test_jobs_clamped_to_module_count(self):
        shards = rtp.shard_modules(dict(self.COUNTS), 99)
        self.assertEqual(len(shards), len(self.COUNTS))

    def test_one_job_one_shard(self):
        shards = rtp.shard_modules(dict(self.COUNTS), 1)
        self.assertEqual(len(shards), 1)
        self.assertEqual(sorted(shards[0]), sorted(self.COUNTS))

    def test_zero_jobs_rejected(self):
        with self.assertRaises(ValueError):
            rtp.shard_modules(dict(self.COUNTS), 0)

    def test_empty_counts_no_shards(self):
        self.assertEqual(rtp.shard_modules({}, 4), [])


class DiscoveryCountsTest(unittest.TestCase):
    def test_counts_and_failed_imports(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS2)
            _write(d, "test_beta.py", _PASS)
            _write(d, "test_broken.py", _BROKEN)
            counts = rtp.module_test_counts(d, d)
        self.assertEqual(counts.get("test_alpha"), 2)
        self.assertEqual(counts.get("test_beta"), 1)
        # The import failure is counted under its own module so a
        # worker reproduces it loudly instead of the module
        # silently vanishing from every shard.
        self.assertEqual(counts.get("test_broken"), 1)


class MainContractTest(unittest.TestCase):
    def test_zero_discovered_is_an_error_not_a_green(self):
        with tempfile.TemporaryDirectory() as d:
            rc = rtp.main(["--start-dir", d, "--top-level-dir", d])
        self.assertEqual(rc, 2)

    def test_passing_modules_return_zero(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS2)
            _write(d, "test_beta.py", _PASS)
            rc = rtp.main(["--jobs", "2", "--top-level-dir", d,
                           "test_alpha", "test_beta"])
        self.assertEqual(rc, 0)

    def test_a_failing_module_fails_the_run(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS)
            _write(d, "test_gamma.py", _FAIL)
            rc = rtp.main(["--jobs", "2", "--top-level-dir", d,
                           "test_alpha", "test_gamma"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
