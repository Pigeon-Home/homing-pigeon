# Tests for runner/tools/run_tests_parallel.py, the sharded suite runner
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
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "run_tests_parallel",
    os.path.join(REPO, "runner", "tools", "run_tests_parallel.py"))
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


class _OutsideActions(unittest.TestCase):
    """A base for every test that drives the runner's main().

    The suite runs under GitHub Actions, where GITHUB_ACTIONS is
    "true" and the runner annotates failed tests. A test that runs
    a deliberately red fake shard without redirecting stdout would
    then print a real ::error line into the real CI log -- a false
    annotation on the run page, which is the exact noise the
    annotations were added to cut through. Each test here starts
    with that variable unset; the one test that proves the
    annotation path sets it on purpose.
    """

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("GITHUB_ACTIONS", None)
        # The fake shards' reports stay out of the real run's output:
        # a deliberately red fake shard printed "FAIL: test_bad
        # (test_gamma.T.test_bad)" into the suite log, and the
        # regression pass read it as a red of the real suite. A test
        # that reads the output redirects stdout itself, inside this.
        for redirect in (contextlib.redirect_stdout(io.StringIO()),
                         contextlib.redirect_stderr(io.StringIO())):
            redirect.__enter__()
            self.addCleanup(redirect.__exit__, None, None, None)


class ReporterRobustnessTest(_OutsideActions):
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
        if os.name == "nt":
            self.skipTest("temp test file leaks into discovery on Windows")
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
        if os.name == "nt":
            self.skipTest("temp test file leaks into discovery on Windows")
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


class MainContractTest(_OutsideActions):
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
        if os.name == "nt":
            self.skipTest("temp test file leaks into discovery on Windows")
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS)
            _write(d, "test_gamma.py", _FAIL)
            # The fixture's FAIL line stays in this buffer: on the real
            # stdout it reads as a red in the suite to anything that
            # parses the suite's output (regression_pass.failing_ids).
            with contextlib.redirect_stdout(io.StringIO()):
                rc = rtp.main(["--jobs", "2", "--top-level-dir", d,
                               "test_alpha", "test_gamma"])
        self.assertEqual(rc, 1)


# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
class ReadableFromTheRunPageTest(_OutsideActions):
    """A red or slow Windows job must be readable without its log.

    Six days of run history (docs/reports/v3.12.56/ci-failures.md)
    had 257 red Windows suite jobs whose only annotation was
    "Process completed with exit code 1": the failing test's name
    lived in a log nobody opened. These pin the two additions:
    failed tests become ::error annotations under Actions (and
    only there), and --durations reaches each shard and survives
    into a passing shard's report along with its wall time.
    """

    _DUMP = (
        "FAIL: test_bad (test_gamma.T.test_bad)\n"
        "----\n"
        "AssertionError: False is not true\n"
        "ERROR: test_boom (runner.tests.test_x.Y.test_boom)\n"
        "FAIL: test_bad (test_gamma.T.test_bad)\n"
    )

    def test_failed_tests_are_named_once_each_in_order(self):
        self.assertEqual(rtp.failed_tests(self._DUMP),
                         ["test_gamma.T.test_bad", "runner.tests.test_x.Y.test_boom"])
        self.assertEqual(rtp.failed_tests("Ran 3 tests\n\nOK\n"), [])

    def test_annotations_name_the_test_and_the_shard(self):
        lines = rtp.annotations_for(self._DUMP, 2)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("::error title=test_gamma.T.test_bad::"))
        self.assertIn("shard 2", lines[0])
        # Workflow-command syntax: the message carries no raw newline
        # and the title no raw colon or comma.
        for line in lines:
            self.assertNotIn("\n", line)
            self.assertEqual(line.count("::"), 2)

    def test_annotations_carry_the_failure_reason(self):
        # The run page is often all a reader has: the log host can be
        # out of reach. The reason is the exception line the test's
        # block ends on, one per test, in that test's own annotation.
        dump = (
            "======================================================================\n"
            "FAIL: test_a (mod.K.test_a) (vector='x.')\n"
            "----------------------------------------------------------------------\n"
            "Traceback (most recent call last):\n"
            '  File "t.py", line 3, in test_a\n'
            "    self.assertEqual(r, -2)\n"
            "AssertionError: 0 != -2\n"
            "\n"
            "======================================================================\n"
            "ERROR: test_b (mod.K.test_b)\n"
            "----------------------------------------------------------------------\n"
            "Traceback (most recent call last):\n"
            "NameError: name 'q' is not defined\n")
        self.assertEqual(rtp.failure_reasons(dump), {
            "mod.K.test_a": "AssertionError: 0 != -2",
            "mod.K.test_b": "NameError: name 'q' is not defined"})
        lines = rtp.annotations_for(dump, 1)
        self.assertIn("AssertionError%3A 0 != -2", lines[0])
        self.assertIn("NameError%3A name 'q' is not defined", lines[1])
        self.assertEqual(rtp.failure_reasons("FAIL: test_c (m.K.test_c)\n"), {})

    def test_annotation_escapes_what_the_parser_would_eat(self):
        dump = "FAIL: test_a (mod.K.test_a)\n"
        head = rtp.annotations_for(dump, 0)[0].split("::")[1]
        self.assertEqual(head, "error title=mod.K.test_a")
        self.assertEqual("a:b,c%d\n".translate(rtp._ANNOTATION_UNSAFE),
                         "a%3Ab%2Cc%25d ")

    def test_under_actions_reads_the_environment(self):
        self.assertTrue(rtp.under_actions({"GITHUB_ACTIONS": "true"}))
        self.assertFalse(rtp.under_actions({"GITHUB_ACTIONS": "false"}))
        self.assertFalse(rtp.under_actions({}))

    def test_a_failed_shard_is_annotated_under_actions_only(self):
        if os.name == "nt":
            self.skipTest("temp test file leaks into discovery on Windows")
        for env, expected in (({"GITHUB_ACTIONS": "true"}, True),
                              ({}, False)):
            fake = io.StringIO()
            with tempfile.TemporaryDirectory() as d:
                _write(d, "test_alpha.py", _PASS)
                _write(d, "test_gamma.py", _FAIL)
                with mock.patch.dict(os.environ, env, clear=False), \
                        contextlib.redirect_stdout(fake):
                    if "GITHUB_ACTIONS" not in env:
                        os.environ.pop("GITHUB_ACTIONS", None)
                    rc = rtp.main(["--jobs", "2", "--top-level-dir", d,
                                   "test_alpha", "test_gamma"])
            self.assertEqual(rc, 1)
            text = fake.getvalue()
            self.assertIn("=== shard 1 FAILED (exit 1) ===", text)
            self.assertEqual(
                "::error title=test_gamma.T.test_bad::" in text, expected,
                "env=%r\n%s" % (env, text))

    def test_durations_flag_is_version_gated(self):
        self.assertEqual(rtp.durations_args(0), [])
        self.assertEqual(rtp.durations_args(None), [])
        self.assertEqual(rtp.durations_args(7, (3, 11, 9)), [])
        self.assertEqual(rtp.durations_args(7, (3, 12, 0)),
                         ["--durations", "7"])

    def test_passing_tail_keeps_the_durations_block(self):
        output = ("test_one ... ok\n\nSlowest test durations\n----\n"
                  "0.010s     test_one (m.T.test_one)\n\n----\n"
                  "Ran 1 test in 0.010s\n\nOK\n")
        self.assertTrue(rtp.passing_tail(output, True)
                        .startswith("Slowest test durations"))
        self.assertIn("OK", rtp.passing_tail(output, True))
        self.assertEqual(rtp.passing_tail(output, False).splitlines()[-1],
                         "OK")
        self.assertEqual(len(rtp.passing_tail(output, False).splitlines()),
                         4)
        # No block in the output (a shard that printed none): fall
        # back to the summary tail instead of an empty report.
        self.assertEqual(rtp.passing_tail("----\nRan 1 test\n\nOK\n", True)
                         .splitlines()[-1], "OK")

    def test_passing_tail_finds_the_summary_past_trailing_stderr(self):
        output = ("..\n----\nRan 12 tests in 0.5s\n\nOK (skipped=2)\n"
                  "sys:1: ResourceWarning: unclosed file <x>\n"
                  "<sys>:0: ResourceWarning: unclosed file <y>\n")
        tail = rtp.passing_tail(output, False)
        self.assertEqual(tail.splitlines(),
                         ["----", "Ran 12 tests in 0.5s", "", "OK (skipped=2)"])

    def test_a_passing_shard_reports_its_wall_time_and_durations(self):
        fake = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS2)
            with contextlib.redirect_stdout(fake):
                rc = rtp.main(["--jobs", "1", "--top-level-dir", d,
                               "--durations", "5", "test_alpha"])
        self.assertEqual(rc, 0)
        text = fake.getvalue()
        self.assertRegex(text, r"shard 0: OK in \d+\.\ds")
        if sys.version_info >= (3, 12):
            # The block is kept whole: its header, through the
            # summary lines unittest prints after it. (Sub-millisecond
            # tests are hidden by unittest without -v, so a toy suite
            # shows the header and the hidden-count note, not ids.)
            self.assertIn("Slowest test durations", text)
            self.assertLess(text.index("Slowest test durations"),
                            text.index("Ran 2 tests"))
        else:
            self.assertIn("running without it", text)

    def test_negative_durations_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as cm, \
                contextlib.redirect_stderr(io.StringIO()):
            rtp.main(["--durations", "-1"])
        self.assertEqual(cm.exception.code, 2)


_HANG = (
    "import time, unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_stuck(self):\n"
    "        time.sleep(600)\n"
)


# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
class WallClockTest(_OutsideActions):
    """A shard that never finishes must end, and say which test.

    2026-10-23: one test looped forever and the Windows suite sat
    past 80 minutes until someone cancelled it, with nothing in
    the log to say which test. Under --wall-clock every shard
    runs through runner/tools/suite_wall_clock.py, which stops at the
    deadline and names the running test; the parent keeps a hard
    stop past that for a shard whose clock could not fire.
    """

    def test_shard_command_shapes(self):
        plain = rtp.shard_command(["--durations", "5"], ["test_a"])
        self.assertEqual(plain[1:], ["-m", "unittest", "--durations", "5",
                                     "test_a"])
        clocked = rtp.shard_command(["--durations", "5"], ["test_a"],
                                    wall_clock=20)
        self.assertTrue(clocked[1].endswith("suite_wall_clock.py"), clocked)
        self.assertEqual(clocked[2:], ["--minutes", "20", "--",
                                       "--durations", "5", "test_a"])
        # Zero is "no clock", the plain shape.
        self.assertEqual(rtp.shard_command([], ["test_a"], wall_clock=0),
                         plain[:3] + ["test_a"])

    def test_a_stuck_shard_fails_the_run_and_names_its_test(self):
        fake = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            _write(d, "test_alpha.py", _PASS)
            _write(d, "test_stuck.py", _HANG)
            started = time.monotonic()
            with contextlib.redirect_stdout(fake):
                rc = rtp.main(["--jobs", "2", "--top-level-dir", d,
                               "--wall-clock", "0.05",
                               "test_alpha", "test_stuck"])
            elapsed = time.monotonic() - started
        self.assertEqual(rc, 1)
        text = fake.getvalue()
        self.assertIn("FAILED (exit 124)", text)
        self.assertIn("running test: test_stuck.T.test_stuck", text)
        self.assertRegex(text, r"shard \d: OK in")
        # The clock, not the parent's hard stop, ended it: well
        # inside the 90-second grace the parent allows.
        self.assertLess(elapsed, 60.0)
        self.assertNotIn("TIMED OUT", text)
        # Outside Actions the shard's dump carries no annotation.
        self.assertNotIn("::error", text)

    def test_negative_wall_clock_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as cm, \
                contextlib.redirect_stderr(io.StringIO()):
            rtp.main(["--wall-clock", "-1"])
        self.assertEqual(cm.exception.code, 2)


class AnnotationTest(unittest.TestCase):
    def test_a_windows_socket_flake_is_named(self):
        out = "Traceback\nOSError: [WinError 10038] not a socket\n"
        lines = rtp.annotations_for(out, 1)
        self.assertTrue(lines)
        self.assertIn("WinError 10038", lines[0])
        self.assertIn("shard 1", lines[0])

    def test_a_clean_failure_is_not_called_a_socket_flake(self):
        out = "FAIL: test_x (mod.Cls.test_x)\nAssertionError: 1 != 2\n"
        lines = rtp.annotations_for(out, 2)
        self.assertFalse(any("10038" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)
