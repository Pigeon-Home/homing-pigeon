# Tests for tools/run_tests_parallel.py, the sharded suite runner
# that takes the Windows CI build from ~5 minutes toward ~3.
#
# The sharding math is pinned directly; the runner's contract
# (every discovered test runs exactly once, a failing module
# fails the run, zero discovered tests is an error and never a
# silent green) is pinned against fake packages on disk, driven
# through the same discovery and subprocess paths CI will use.

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from unittest import mock

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
_FAIL_UNICODE = (
    "import unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_bad(self):\n"
    "        self.fail('boom \\u2713 \\u6f22\\u5b57 \\U0001f389')\n"
)
_PASS_UNICODE = (
    "import unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_one(self):\n"
    "        print('\\u2713 \\u6f22\\u5b57 \\U0001f389')\n"
    "        self.assertTrue(True)\n"
)


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

    def test_a_second_tree_may_reuse_the_module_name(self):
        # Discover caches imports in this process. Two temp trees
        # both named test_alpha must both count; the second must
        # not die with "incorrectly imported".
        with tempfile.TemporaryDirectory() as a:
            _write(a, "test_alpha.py", _PASS)
            first = rtp.module_test_counts(a, a)
        with tempfile.TemporaryDirectory() as b:
            _write(b, "test_alpha.py", _PASS2)
            second = rtp.module_test_counts(b, b)
        self.assertEqual(first.get("test_alpha"), 1)
        self.assertEqual(second.get("test_alpha"), 2)


class _BufferStdout:
    """A stdout whose text layer is cp1252 but whose buffer works.

    The Windows CI console shape. Writing exotic text through the
    text layer raises UnicodeEncodeError, exactly like the real
    console; the raw buffer takes utf-8 bytes fine.
    """

    def __init__(self):
        self.buffer = io.BytesIO()

    def write(self, text):
        text.encode("cp1252")
        return len(text)

    def flush(self):
        pass


class _RaisingStdout:
    """A stdout with no buffer whose write raises on non-cp1252 text."""

    def __init__(self):
        self.written = []

    def write(self, text):
        text.encode("cp1252")
        self.written.append(text)
        return len(text)

    def flush(self):
        pass


class ReporterRobustnessTest(unittest.TestCase):
    """The reporter must survive the output it exists to print.

    The 9d8cdac Windows run: a failed shard's dump carried
    characters cp1252 cannot encode, print() raised
    UnicodeEncodeError, the reporting loop aborted with a shard
    handle still open, and TemporaryDirectory cleanup converted
    that into PermissionError [WinError 32]. Red build, zero
    usable failure detail. These tests pin the three layers of
    the fix: buffer-encoded output, per-shard fault isolation,
    and cleanup that tolerates refusal.
    """

    def test_unencodable_shard_output_is_reported_via_the_buffer(self):
        fake = _BufferStdout()
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS)
            _write(d, "test_gamma.py", _FAIL_UNICODE)
            with contextlib.redirect_stdout(fake):
                rc = rtp.main(["--jobs", "2", "--top-level-dir", d,
                               "test_alpha", "test_gamma"])
        self.assertEqual(rc, 1)
        text = fake.buffer.getvalue().decode("utf-8", "replace")
        # The failure detail survived whole, exotic characters and
        # all, and the run still named the failed shard.
        self.assertIn("boom ✓ 漢字 🎉", text)
        self.assertIn("=== shard 1 FAILED (exit 1) ===", text)
        self.assertIn("FAILED shard(s): 1", text)
        self.assertIn("shard 0: OK", text)

    def test_a_raising_stdout_loses_no_shard_and_no_verdict(self):
        fake = _RaisingStdout()
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS)
            _write(d, "test_gamma.py", _FAIL_UNICODE)
            with contextlib.redirect_stdout(fake):
                rc = rtp.main(["--jobs", "2", "--top-level-dir", d,
                               "test_alpha", "test_gamma"])
        # The exotic dump itself cannot be written to this stream,
        # but the exit code, the passing shard's report, and the
        # failed-shard accounting all survive its failure.
        self.assertEqual(rc, 1)
        written = "".join(fake.written)
        self.assertIn("shard 0: OK", written)
        self.assertIn("could not be printed", written)
        self.assertIn("FAILED shard(s): 1", written)

    def test_unencodable_output_in_a_passing_shard_is_safe(self):
        fake = _BufferStdout()
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS_UNICODE)
            with contextlib.redirect_stdout(fake):
                rc = rtp.main(["--jobs", "1", "--top-level-dir", d,
                               "test_alpha"])
        self.assertEqual(rc, 0)
        text = fake.buffer.getvalue().decode("utf-8", "replace")
        self.assertIn("shard 0: OK", text)

    def test_cleanup_failure_does_not_crash_a_finished_run(self):
        real_td = tempfile.TemporaryDirectory

        class BadCleanup(real_td):
            def cleanup(self):
                if getattr(self, "_raised", False):
                    return super().cleanup()
                self._raised = True
                raise OSError("simulated locked temp directory")

        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS)
            with mock.patch.object(
                    tempfile, "TemporaryDirectory", BadCleanup):
                rc = rtp.main(["--jobs", "1", "--top-level-dir", d,
                               "test_alpha"])
        self.assertEqual(rc, 0)


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
