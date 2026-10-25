# Tests for runner/tools/suite_wall_clock.py: `python -m unittest` under a
# clock that names the test it killed.
#
# The 2026-10-23 stall: a test that looped forever held both CI
# suites past 80 minutes, the job had no clock, and the only line
# naming the test was the unfinished one at the end of a log that
# could not be read from the seat doing the diagnosis. The clock
# stops the run at the deadline, prints the running test and the
# main thread's stack, annotates the test under Actions, and exits
# 124. Off the deadline it is unittest, exit status and all.
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOL = os.path.join(REPO, "runner", "tools", "suite_wall_clock.py")
_spec = importlib.util.spec_from_file_location("suite_wall_clock", TOOL)
swc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(swc)

_HANG = (
    "import time, unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_fast(self):\n"
    "        pass\n"
    "    def test_stuck(self):\n"
    "        time.sleep(600)\n"
)
_PASS = (
    "import unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_one(self):\n"
    "        self.assertTrue(True)\n"
)
_FAIL = (
    "import unittest\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_bad(self):\n"
    "        self.fail('red')\n"
)


def _run(folder, minutes, module, actions=False):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("GITHUB_ACTIONS", None)
    if actions:
        env["GITHUB_ACTIONS"] = "true"
    return subprocess.run(
        [sys.executable, TOOL, "--minutes", str(minutes), "--", module, "-v"],
        cwd=folder, capture_output=True, text=True, timeout=120, env=env)


class _Module(unittest.TestCase):
    def _folder(self, name, body):
        d = tempfile.mkdtemp(prefix="hp-wall-clock-")
        with open(os.path.join(d, name + ".py"), "w", encoding="utf-8") as fh:
            fh.write(body)
        return d


class DeadlineTest(_Module):
    def test_a_stuck_test_is_named_and_the_run_exits_124(self):
        d = self._folder("test_wc_hang", _HANG)
        proc = _run(d, 0.05, "test_wc_hang")
        self.assertEqual(proc.returncode, 124, proc.stderr)
        self.assertIn("suite wall clock: 0.05 minutes elapsed", proc.stderr)
        self.assertIn("running test: test_wc_hang.T.test_stuck", proc.stderr)
        # The stack says where it sat, most recent call first.
        self.assertIn("time.sleep(600)", proc.stderr)
        self.assertIn("main thread, most recent call first", proc.stderr)
        # The test before it finished normally.
        # 3.11+ names the method in the parenthesis; 3.9 and 3.10 do not.
        self.assertRegex(proc.stderr,
                         r"test_fast \(test_wc_hang\.T(\.test_fast)?\) \.\.\. ok")
        # Outside Actions nothing is annotated.
        self.assertNotIn("::error", proc.stdout + proc.stderr)

    def test_under_actions_the_stuck_test_is_an_annotation(self):
        d = self._folder("test_wc_hang2", _HANG)
        proc = _run(d, 0.05, "test_wc_hang2", actions=True)
        self.assertEqual(proc.returncode, 124, proc.stderr)
        self.assertIn("::error title=test_wc_hang2.T.test_stuck::"
                      "still running after 0.05 minutes", proc.stdout)


class OffTheDeadlineTest(_Module):
    def test_a_passing_module_is_unittest_green(self):
        d = self._folder("test_wc_pass", _PASS)
        proc = _run(d, 5, "test_wc_pass")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("OK", proc.stderr)
        self.assertNotIn("suite wall clock", proc.stderr)

    def test_a_failing_module_is_unittest_red(self):
        d = self._folder("test_wc_fail", _FAIL)
        proc = _run(d, 5, "test_wc_fail")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("FAILED (failures=1)", proc.stderr)
        self.assertNotIn("suite wall clock", proc.stderr)

    def test_the_discover_shape_is_accepted(self):
        d = self._folder("test_wc_disc", _PASS)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("GITHUB_ACTIONS", None)
        proc = subprocess.run(
            [sys.executable, TOOL, "--minutes", "5", "--", "discover",
             "-s", d, "-t", d, "-p", "test_wc_disc.py"],
            cwd=d, capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Ran 1 test", proc.stderr)


class ContractTest(unittest.TestCase):
    def test_usage_errors(self):
        for argv in (["--minutes", "0", "--", "x"],
                     ["--minutes", "-1", "--", "x"],
                     ["--minutes", "5"],
                     ["--", "x"]):
            with self.assertRaises(SystemExit) as cm, \
                    _quiet_stderr():
                swc.main(argv)
            self.assertEqual(cm.exception.code, 2, argv)

    def test_annotation_names_the_test_and_escapes_the_parser_food(self):
        line = swc.annotation("runner.tests.test_a.T.test_b", 20)
        self.assertTrue(line.startswith(
            "::error title=runner.tests.test_a.T.test_b::"))
        self.assertIn("20 minutes", line)
        self.assertNotIn(",", line.split("::", 2)[2].replace("%2C", ""))
        # No test on the stack: a generic title, never an empty one.
        self.assertTrue(swc.annotation(None, 20).startswith(
            "::error title=suite wall clock::"))

    def test_running_test_finds_the_case_on_the_stack(self):
        found = {}

        class Probe(unittest.TestCase):
            def test_me(self):
                frame = sys._getframe()  # noqa: SLF001 - the point
                found["id"] = swc.running_test(swc._stack_of(frame))

        Probe("test_me").run(unittest.TestResult())
        self.assertTrue(found["id"].endswith("Probe.test_me"), found)
        # A stack with no test on it (a fresh thread's): None, not
        # a guess.
        import threading

        def bare():
            found["none"] = swc.running_test(
                swc._stack_of(sys._getframe()))  # noqa: SLF001

        t = threading.Thread(target=bare)
        t.start()
        t.join()
        self.assertIsNone(found["none"])

    def test_under_actions_reads_the_environment(self):
        self.assertTrue(swc.under_actions({"GITHUB_ACTIONS": "true"}))
        self.assertFalse(swc.under_actions({}))
        self.assertFalse(swc.under_actions({"GITHUB_ACTIONS": "false"}))


class _quiet_stderr:
    def __enter__(self):
        import io
        self._old = sys.stderr
        sys.stderr = io.StringIO()
        return self

    def __exit__(self, *exc):
        sys.stderr = self._old
        return False


if __name__ == "__main__":
    unittest.main(verbosity=2)
