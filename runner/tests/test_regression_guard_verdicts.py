# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/regression_guard.py: the verdicts, from scripted runs.

test_regression_guard holds the summary parser, the snapshot diff, the
leak run and two whole guard runs. The decisions in between ran only
inside those child processes, out of line coverage's sight. Here the
one seam, run_python, is scripted, so each check's verdict is held to
the runs it is shown: a repeat run that differs is a flake named with
its run, a shuffled seed that goes red is named with the command that
reproduces it, a Windows count is judged against the --since tree's
(green, a new module, no tree to compare, the same or fewer, more), a
leak run that crashes or prints a line it cannot read says so, and a
red gate is red. A run that outlives its timeout is exit 124 with what
it printed, the baseline checkout cleans up after itself, and main
routes its arguments.
"""
import contextlib
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from runner.tools import regression_guard as RG  # noqa: E402


def ok(n=3, skipped=0):
    tail = " (skipped=%d)" % skipped if skipped else ""
    return "...\nRan %d tests in 0.01s\n\nOK%s\n" % (n, tail)


def red(n=3, failures=1):
    return ("F..\nFAIL: test_x\nRan %d tests in 0.01s\n\nFAILED "
            "(failures=%d)\n" % (n, failures))


def scripted(*answers):
    """run_python answering (rc, out) in turn; records the args."""
    calls = []
    it = iter(answers)

    def fake(args, cwd=RG.ROOT, timeout=1800):
        calls.append((list(args), cwd))
        return next(it)
    return fake, calls


class RunPythonTest(unittest.TestCase):
    def test_a_run_past_its_timeout_is_124_with_what_it_printed(self):
        err = subprocess.TimeoutExpired(["python"], 5, output=b"Ran 1 test")
        with mock.patch.object(RG.subprocess, "run", side_effect=err):
            self.assertEqual(RG.run_python(["-c", "pass"], timeout=5),
                             (124, "Ran 1 test\n[timed out after 5s]\n"))
        err = subprocess.TimeoutExpired(["python"], 7, output=None)
        with mock.patch.object(RG.subprocess, "run", side_effect=err):
            self.assertEqual(RG.run_python(["-c", "pass"], timeout=7)[1],
                             "\n[timed out after 7s]\n")


class RepeatTest(unittest.TestCase):
    def test_no_first_summary_skips(self):
        v = RG.check_repeat("test_x.py", None, 3)
        self.assertFalse(v.ok)
        self.assertIn("native run had no summary", v.note)

    def test_the_same_every_time_is_green(self):
        fake, calls = scripted((0, ok()), (0, ok()), (0, ok()))
        with mock.patch.object(RG, "run_python", fake):
            v = RG.check_repeat("test_x.py", RG.parse_summary(ok()), 3)
        self.assertTrue(v.ok)
        self.assertEqual(v.note, "3 more runs, all the same")
        self.assertEqual(calls[0][0], ["-m", "unittest",
                                       "runner.tests.test_x"])

    def test_a_run_that_differs_is_a_flake_named_by_its_run(self):
        fake, _calls = scripted((0, ok()), (1, red()), (1, red(failures=2)))
        with mock.patch.object(RG, "run_python", fake):
            v = RG.check_repeat("test_x.py", RG.parse_summary(ok()), 3)
        self.assertFalse(v.ok)
        self.assertTrue(v.note.startswith("2 of 3 runs differ from the "
                                          "first (run 2: "), v.note)
        self.assertIn("a flake", v.note)
        self.assertIn("| FAIL: test_x", v.note)


class ShuffledTest(unittest.TestCase):
    def test_every_seed_green(self):
        fake, calls = scripted((0, ok()), (0, ok()))
        with mock.patch.object(RG, "run_python", fake):
            v = RG.check_shuffled("test_x.py", [11, 12])
        self.assertTrue(v.ok)
        self.assertEqual(v.note, "seeds 11, 12: all green")
        self.assertEqual(calls[1][0], ["runner/tools/run_tests_shuffled.py",
                                       "--seed", "12", "--pattern",
                                       "test_x.py"])

    def test_a_red_seed_or_a_bad_exit_names_the_reproduction(self):
        for answers in (((0, ok()), (1, red())), ((0, ok()), (2, ok()))):
            fake, _calls = scripted(*answers)
            with self.subTest(answers=answers), \
                    mock.patch.object(RG, "run_python", fake):
                v = RG.check_shuffled("test_x.py", [11, 12])
            self.assertFalse(v.ok)
            self.assertTrue(v.note.startswith("seed 12 is red"), v.note)
            self.assertIn("run_tests_shuffled.py --seed 12 --pattern "
                          "test_x.py", v.note)


class _Tree:
    """A stand-in for the baseline checkout."""

    def __init__(self, path):
        self.path = path

    def __call__(self, ref):
        self.ref = ref
        return self

    def __enter__(self):
        return self.path

    def __exit__(self, *exc):
        return False


class WindowsTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="hp-guard-test-")
        self.addCleanup(shutil.rmtree, self.td, True)
        os.makedirs(os.path.join(self.td, RG.TESTS))
        open(os.path.join(self.td, RG.TESTS, "test_x.py"), "w").close()

    def _check(self, answers, baseline=True, tree="here"):
        fake, calls = scripted(*answers)
        path = self.td if tree == "here" else tree
        with mock.patch.object(RG, "run_python", fake), \
                mock.patch.object(RG, "Worktree", _Tree(path)):
            v = RG.check_windows("test_x.py", "origin/main", baseline)
        return v, calls

    def test_no_summary_is_red(self):
        v, _ = self._check([(1, "Traceback: boom\n")])
        self.assertFalse(v.ok)
        self.assertIn("simulated surface run had no summary", v.note)

    def test_green_under_the_surface(self):
        v, calls = self._check([(0, ok(4))])
        self.assertTrue(v.ok)
        self.assertEqual(v.note, "4 tests green under the simulated surface")
        self.assertEqual(calls[0][1], RG.ROOT)

    def test_a_new_module_has_nothing_to_compare(self):
        v, _ = self._check([(1, red())], baseline=False)
        self.assertFalse(v.ok)
        self.assertIn("no baseline to compare (a new module)", v.note)

    def test_no_baseline_tree_is_red(self):
        for tree in (None, os.path.join(self.td, "empty")):
            with self.subTest(tree=tree):
                v, _ = self._check([(1, red())], tree=tree)
                self.assertFalse(v.ok)
                self.assertIn("the origin/main tree could not be checked "
                              "out for a baseline", v.note)

    def test_the_same_count_as_the_baseline_is_a_known_artifact(self):
        v, calls = self._check([(1, red(failures=2)), (1, red(failures=2))])
        self.assertTrue(v.ok)
        self.assertEqual(v.note, "2 red under the simulated surface, 2 on "
                                 "origin/main: known artifacts of the surface")
        self.assertEqual(calls[1][1], self.td)

    def test_a_count_that_moved_is_red(self):
        v, _ = self._check([(1, red(failures=3)), (1, red(failures=1))])
        self.assertFalse(v.ok)
        self.assertIn("3 red under the simulated surface against 1 on "
                      "origin/main: the count moved", v.note)


class WorktreeTest(unittest.TestCase):
    def _enter(self, result):
        kw = {"side_effect": result} if isinstance(result, BaseException) \
            else {"return_value": result}
        with mock.patch.object(RG.subprocess, "run", **kw):
            tree = RG.Worktree("origin/main")
            got = tree.__enter__()
            made = tree.path
            self.assertTrue(os.path.isdir(made))
            tree.__exit__(None, None, None)
        self.assertFalse(os.path.exists(made))
        return got, made

    def test_a_checkout_is_its_path_and_is_removed_after(self):
        got, made = self._enter(subprocess.CompletedProcess([], 0))
        self.assertEqual(got, made)

    def test_a_failed_or_impossible_checkout_is_none(self):
        for result in (subprocess.CompletedProcess([], 128),
                       OSError("no git"),
                       subprocess.TimeoutExpired(["git"], 300)):
            with self.subTest(result=result):
                self.assertIsNone(self._enter(result)[0])


class LeaksAndGatesTest(unittest.TestCase):
    def _leaks(self, rc, out):
        fake, calls = scripted((rc, out))
        with mock.patch.object(RG, "run_python", fake):
            return RG.check_leaks("test_x.py"), calls

    def test_a_crashed_leak_run_is_red(self):
        v, calls = self._leaks(2, "Traceback\nImportError: x\n")
        self.assertFalse(v.ok)
        self.assertIn("the leak run crashed", v.note)
        self.assertEqual(calls[0][0][-2:], ["--leaks",
                                            os.path.join(RG.TESTS,
                                                         "test_x.py")])

    def test_a_clean_run_and_an_unreadable_leak_line(self):
        v, _ = self._leaks(0, ok())
        self.assertTrue(v.ok)
        self.assertEqual(v.note, "no global state left behind")
        v, _ = self._leaks(0, ok() + "LEAK {not json\n")
        self.assertTrue(v.ok)
        self.assertIn("0 hard, 1 soft", v.note)
        self.assertIn("?: unparsed: LEAK {not json", v.note)

    def test_gates(self):
        for answer, good in (((0, ok(30)), True), ((1, red()), False),
                             ((0, "no summary"), False)):
            fake, calls = scripted(answer)
            with self.subTest(answer=answer), \
                    mock.patch.object(RG, "run_python", fake):
                v = RG.check_gates()
            self.assertEqual(v.ok, good)
            self.assertEqual(calls[0][0][2:], list(RG.GATES))
        self.assertEqual(RG._tail(""), "")


class MainTest(unittest.TestCase):
    def test_named_modules_go_to_the_guard_by_basename(self):
        with mock.patch.object(RG, "guard", return_value=0) as guard:
            self.assertEqual(RG.main(["runner/tests/test_x.py", "test_y.py",
                                      "--repeat", "1", "--shuffles", "0",
                                      "--no-sim", "--no-leaks",
                                      "--since", "HEAD~2"]), 0)
        guard.assert_called_once_with(["test_x.py", "test_y.py"], "HEAD~2",
                                      1, 0, True, True)

    def test_nothing_changed_says_so_and_is_green(self):
        out = io.StringIO()
        with mock.patch.object(RG, "changed_modules", return_value=[]), \
                contextlib.redirect_stdout(out):
            self.assertEqual(RG.main([]), 0)
        self.assertIn("no test modules changed against origin/main", out.getvalue())

    def test_the_leak_switch_runs_the_module_in_process(self):
        with mock.patch.object(RG, "leak_run", return_value=1) as run:
            self.assertEqual(RG.main(["--leaks", "runner/tests/test_x.py"]), 1)
        run.assert_called_once_with("runner/tests/test_x.py")


if __name__ == "__main__":
    unittest.main()
