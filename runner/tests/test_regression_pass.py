# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""runner/tools/regression_pass.py: the rig's regression pass, piece by piece.

The reader of a suite run (which ids failed, how many tests ran),
the flake classifier, the ledger line and the Q paragraph, the
state file, and the bisect itself on a throwaway repository with
four commits where the third breaks a test: the pass must name the
third, and must name the commit that added a test when the test
was red from birth.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tools import regression_pass as P  # noqa: E402

SHARD_OUTPUT = """\
shard 0: OK in 3.0s
Ran 120 tests in 2.900s

OK
=== shard 1 FAILED (exit 1) ===
(4.0s)
FAIL: test_a (runner.tests.test_one.OneTest.test_a)
ERROR: test_b (runner.tests.test_one.OneTest.test_b)
ERROR: test_two (unittest.loader._FailedTest.test_two)
FAIL: test_a (runner.tests.test_one.OneTest.test_a)
Ran 40 tests in 3.800s

FAILED (failures=1, errors=2)
FAILED shard(s): 1
"""


class ReaderTest(unittest.TestCase):
    def test_failing_ids_in_order_without_repeats(self):
        self.assertEqual(P.failing_ids(SHARD_OUTPUT),
                         ["runner.tests.test_one.OneTest.test_a",
                          "runner.tests.test_one.OneTest.test_b",
                          "runner.tests.test_two"])

    def test_tests_ran_sums_the_shards(self):
        self.assertEqual(P.tests_ran(SHARD_OUTPUT), 160)
        self.assertEqual(P.tests_ran("nothing"), 0)

    def test_classify(self):
        det, flaky = P.classify({"a": [False, False], "b": [False, True],
                                 "c": [True, True]})
        self.assertEqual(det, ["a"])
        self.assertEqual(flaky, ["b", "c"])

    def test_module_file(self):
        self.assertEqual(P._module_file("runner.tests.test_x.C.test_m"),
                         os.path.join("runner", "tests", "test_x.py"))
        self.assertEqual(P._module_file("runner.tests.test_x"),
                         os.path.join("runner", "tests", "test_x.py"))
        self.assertIsNone(P._module_file("other.thing"))


class LinesTest(unittest.TestCase):
    def test_green_ledger_line(self):
        self.assertEqual(P.ledger_line("abcdef0123", 3261, 125.0, [], [], {}),
                         "regression abcdef01: 3261 tests green in 2m05s")

    def test_red_ledger_line_names_culprits_and_flakes(self):
        line = P.ledger_line("abcdef0123", 3261, 61.0,
                             ["runner.tests.test_x.T.test_a"],
                             ["runner.tests.test_y.T.test_b"],
                             {"runner.tests.test_x.T.test_a":
                              ("0123456789", "break it", 2)})
        self.assertIn("RED", line)
        self.assertIn("1 deterministic: runner.tests.test_x.T.test_a "
                      "(since 01234567)", line)
        self.assertIn("1 flaky: runner.tests.test_y.T.test_b", line)

    def test_q_paragraph_carries_the_reproduce_command(self):
        text = P.q_paragraph("abcdef0123", ["runner.tests.test_x.T.test_a"],
                             ["runner.tests.test_y.T.test_b"],
                             {"runner.tests.test_x.T.test_a":
                              ("0123456789", "break it", 2)}, 3)
        self.assertIn("python -m unittest runner.tests.test_x.T.test_a",
                      text)
        self.assertIn("in 3 of 3 lone runs; red since 01234567 (break it). "
                      "Reproduce", text)
        self.assertNotIn(";.", text)
        self.assertIn("a flake", text)
        self.assertIn("regression_guard.py", text)


class StateTest(unittest.TestCase):
    def test_last_green_and_records(self):
        tmp = tempfile.mkdtemp(prefix="hp-regress-state-")
        self.addCleanup(shutil.rmtree, tmp, True)
        state = P.State(tmp)
        self.assertIsNone(state.last_green())
        state.record_green("a" * 40, 10)
        self.assertEqual(state.last_green()["sha"], "a" * 40)
        self.assertEqual(state.last_green()["tests"], 10)
        path = state.record_run({"sha": "b" * 40, "tests": 10, "exit": 1})
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["exit"], 1)


class BisectTest(unittest.TestCase):
    """Four commits: a passing test, a no-op, the break, a no-op."""

    @classmethod
    def setUpClass(cls):
        try:
            subprocess.run(["git", "--version"], check=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest("git is not on PATH")
        cls.repo = tempfile.mkdtemp(prefix="hp-regress-repo-")
        tests = os.path.join(cls.repo, "runner", "tests")
        os.makedirs(tests)
        for d in (os.path.join(cls.repo, "runner"), tests):
            with open(os.path.join(d, "__init__.py"), "w") as fh:
                fh.write("")
        cls._git("init", "-q")
        cls._git("config", "user.email", "pass@example.com")
        cls._git("config", "user.name", "pass")
        cls._write("value.py", "VALUE = 1\n")
        cls._write("test_bisect_example.py", textwrap.dedent('''\
            import unittest
            from runner.tests.value import VALUE


            class ExampleTest(unittest.TestCase):
                def test_value(self):
                    self.assertEqual(VALUE, 1)
            '''))
        cls.shas = []
        cls._commit("the test passes")
        cls._write("note.txt", "nothing\n")
        cls._commit("a no-op")
        cls._write("value.py", "VALUE = 2\n")
        cls._commit("the break")
        cls._write("note.txt", "nothing again\n")
        cls._commit("another no-op")
        cls._write("test_born_red.py", textwrap.dedent('''\
            import unittest


            class BornRedTest(unittest.TestCase):
                def test_red(self):
                    self.fail("red from birth")
            '''))
        cls._commit("a test born red")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo, ignore_errors=True)

    @classmethod
    def _git(cls, *args):
        subprocess.run(["git"] + list(args), cwd=cls.repo, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @classmethod
    def _write(cls, name, text):
        with open(os.path.join(cls.repo, "runner", "tests", name), "w",
                  encoding="utf-8") as fh:
            fh.write(text)

    @classmethod
    def _commit(cls, subject):
        cls._git("add", "-A")
        cls._git("commit", "-q", "-m", subject)
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cls.repo,
                             stdout=subprocess.PIPE, check=True)
        cls.shas.append(out.stdout.decode().strip())

    def test_the_break_is_named(self):
        ident = "runner.tests.test_bisect_example.ExampleTest.test_value"
        with mock.patch.object(P, "REPO", self.repo):
            self.assertFalse(P.is_red_at(self.shas[0], [ident]))
            self.assertTrue(P.is_red_at(self.shas[3], [ident]))
            sha, subject, steps = P.bisect(self.shas[0], self.shas[3],
                                           [ident])
        self.assertEqual(sha, self.shas[2])
        self.assertEqual(subject, "the break")
        self.assertGreaterEqual(steps, 1)

    def test_a_test_born_red_names_its_own_commit(self):
        ident = "runner.tests.test_born_red.BornRedTest.test_red"
        with mock.patch.object(P, "REPO", self.repo):
            self.assertFalse(P.is_red_at(self.shas[3], [ident]))
            sha, subject, _steps = P.bisect(self.shas[0], self.shas[4],
                                            [ident])
        self.assertEqual(sha, self.shas[4])
        self.assertEqual(subject, "a test born red")

    def test_is_ancestor(self):
        with mock.patch.object(P, "REPO", self.repo):
            self.assertTrue(P.is_ancestor(self.shas[0], self.shas[4]))
            self.assertFalse(P.is_ancestor(self.shas[4], self.shas[0]))

    def test_rerun_classifies_a_deterministic_red(self):
        ident = "runner.tests.test_born_red.BornRedTest.test_red"
        with mock.patch.object(P, "REPO", self.repo):
            results = P.rerun([ident], 2)
        self.assertEqual(results, {ident: [False, False]})


class PassFlowTest(unittest.TestCase):
    """regression_pass with the suite and git faked: the verdicts."""

    def _args(self, tmp):
        import argparse
        return argparse.Namespace(pull=False, jobs=0, repeat=2,
                                  state_dir=tmp, no_bisect=True,
                                  timeout=10)

    def test_green_records_the_head(self):
        tmp = tempfile.mkdtemp(prefix="hp-regress-flow-")
        self.addCleanup(shutil.rmtree, tmp, True)
        lines = []
        with mock.patch.object(P, "git", return_value="c" * 40), \
                mock.patch.object(P, "run_suite",
                                  return_value=(0, "Ran 7 tests in 1s\n\nOK\n")):
            status = P.regression_pass(self._args(tmp), out=lines.append)
        self.assertEqual(status, 0)
        self.assertEqual(P.State(tmp).last_green()["sha"], "c" * 40)
        self.assertTrue(any(l.startswith("regression cccccccc: 7 tests green")
                            for l in lines))

    def test_red_is_classified_and_reported(self):
        tmp = tempfile.mkdtemp(prefix="hp-regress-flow-")
        self.addCleanup(shutil.rmtree, tmp, True)
        lines = []
        red = ("FAIL: test_a (runner.tests.test_x.T.test_a)\n"
               "FAIL: test_b (runner.tests.test_x.T.test_b)\n"
               "Ran 7 tests in 1s\n\nFAILED (failures=2)\n")
        with mock.patch.object(P, "git", return_value="d" * 40), \
                mock.patch.object(P, "run_suite", return_value=(1, red)), \
                mock.patch.object(P, "rerun", return_value={
                    "runner.tests.test_x.T.test_a": [False, False],
                    "runner.tests.test_x.T.test_b": [True, False]}):
            status = P.regression_pass(self._args(tmp), out=lines.append)
        self.assertEqual(status, 1)
        self.assertIsNone(P.State(tmp).last_green())
        ledger = [l for l in lines if l.startswith("regression dddddddd")][0]
        self.assertIn("1 deterministic: runner.tests.test_x.T.test_a", ledger)
        self.assertIn("1 flaky: runner.tests.test_x.T.test_b", ledger)
        self.assertTrue(any("for questions.md" in l for l in lines))

    def test_a_suite_that_did_not_run_is_exit_2(self):
        tmp = tempfile.mkdtemp(prefix="hp-regress-flow-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.object(P, "git", return_value="e" * 40), \
                mock.patch.object(P, "run_suite",
                                  return_value=(2, "error: no tests\n")):
            status = P.regression_pass(self._args(tmp), out=lambda s: None)
        self.assertEqual(status, 2)


if __name__ == "__main__":
    unittest.main()
