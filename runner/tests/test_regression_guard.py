# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""runner/tools/regression_guard.py: the pre-push guard's parts.

The guard runs other test modules in subprocesses, so the end-to-end
check here points it at one cheap module; the rest pins the pieces a
wrong verdict would come from: the unittest summary parser, the
module selection from git, the snapshot diff that names a leak, and
the in-process leak run on a module written to leak on purpose.
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

from runner.tools import regression_guard as G  # noqa: E402

OK_REPORT = """\
..s.x
----------------------------------------------------------------------
Ran 5 tests in 0.012s

OK (skipped=1, expected failures=1)
"""
RED_REPORT = """\
.F.E.u
======================================================================
FAIL: test_a (m.T.test_a)
----------------------------------------------------------------------
Ran 6 tests in 1.500s

FAILED (failures=1, errors=1, unexpected successes=1)
"""


class SummaryParserTest(unittest.TestCase):
    def test_ok_with_skips_and_expected_failures(self):
        s = G.parse_summary(OK_REPORT)
        self.assertEqual(s, {"ran": 5, "ok": True, "failures": 0,
                             "errors": 0, "skipped": 1,
                             "expected_failures": 1,
                             "unexpected_successes": 0})
        self.assertEqual(G.red_count(s), 0)

    def test_red_counts_failures_errors_and_unexpected_successes(self):
        s = G.parse_summary(RED_REPORT)
        self.assertFalse(s["ok"])
        self.assertEqual((s["failures"], s["errors"],
                          s["unexpected_successes"]), (1, 1, 1))
        self.assertEqual(G.red_count(s), 3)

    def test_no_summary_is_none_and_red(self):
        self.assertIsNone(G.parse_summary("Traceback (most recent call "
                                          "last):\nImportError: x\n"))
        self.assertEqual(G.red_count(None), 1)

    def test_the_last_summary_wins(self):
        two = OK_REPORT + RED_REPORT
        self.assertEqual(G.parse_summary(two)["ran"], 6)

    def test_module_name(self):
        self.assertEqual(G.module_name("runner/tests/test_x.py"),
                         "runner.tests.test_x")
        self.assertEqual(G.module_name("test_x"), "runner.tests.test_x")


class SnapshotDiffTest(unittest.TestCase):
    def _snap(self):
        return {"os": {"name": "posix", "sep": "/", "linesep": "\n",
                       "O_BINARY": "<absent>"},
                "environ": {"A": "1"}, "cwd": "/w", "umask": 0o22,
                "sys.path": ["/w"], "patches": 0,
                "signals": {"SIGINT": "default"},
                "streams": (1, 2, 3), "socket_timeout": None,
                "threads": [], "modules": 10, "tempdir": ["a"]}

    def test_identical_snapshots_diff_to_nothing(self):
        self.assertEqual(G._diff(self._snap(), self._snap()), [])

    def test_each_kind_of_leak_is_named(self):
        before = self._snap()
        after = self._snap()
        after["os"]["O_BINARY"] = 0
        after["environ"] = {"A": "2", "B": "x"}
        after["cwd"] = "/elsewhere"
        after["patches"] = 2
        after["signals"]["SIGINT"] = "handler"
        after["threads"] = ["worker-1"]
        after["tempdir"] = ["a", "hp-left-behind"]
        whats = [w for w, _d in G._diff(before, after)]
        self.assertEqual(whats, ["os", "signals", "environ", "cwd",
                                 "patches", "threads", "tempdir"])
        hard = [w for w in whats if w in G._HARD_LEAKS]
        self.assertEqual(hard, ["os", "signals", "environ", "cwd",
                                "patches"])

    def test_a_deleted_binary_flag_is_an_os_leak(self):
        before = self._snap()
        before["os"]["O_BINARY"] = 0x8000
        after = self._snap()
        diff = G._diff(before, after)
        self.assertEqual(diff[0][0], "os")
        self.assertIn("O_BINARY", diff[0][1])


class LeakRunTest(unittest.TestCase):
    """The in-process leak run on a module that leaks on purpose."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-guard-leak-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = os.path.join(self.tmp, "test_leaky_example.py")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent('''\
                import os
                import unittest
                from unittest import mock


                class LeakyTest(unittest.TestCase):
                    def test_env_left_behind(self):
                        os.environ["HP_GUARD_LEAK_EXAMPLE"] = "1"

                    def test_patch_never_stopped(self):
                        mock.patch.object(os, "sep", os.sep).start()

                    def test_clean(self):
                        with mock.patch.dict(os.environ, {"X": "1"}):
                            pass
                '''))

    def test_leaks_are_reported_per_test(self):
        rc, out = G.run_python([os.path.join("runner", "tools",
                                             "regression_guard.py"),
                                "--leaks", self.path])
        self.assertEqual(rc, 0, out)
        leaks = [l for l in out.splitlines() if l.startswith("LEAK ")]
        self.assertEqual(len(leaks), 2, out)
        self.assertIn("test_env_left_behind", leaks[0])
        self.assertIn('"what": "environ"', leaks[0])
        self.assertIn("HP_GUARD_LEAK_EXAMPLE", leaks[0])
        self.assertIn("test_patch_never_stopped", leaks[1])
        self.assertIn('"what": "patches"', leaks[1])
        self.assertFalse(any("test_clean" in l for l in leaks))


class SoftLeakRunTest(unittest.TestCase):
    """Q64: the soft reports -- a tempdir and a thread left behind --
    are named by the guard with the test that left them, so a change
    to the snapshot machinery cannot turn the leak check into a
    no-op without a red here."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-guard-soft-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = os.path.join(self.tmp, "test_soft_leaky_example.py")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent('''\
                import tempfile
                import threading
                import time
                import unittest


                class SoftLeakyTest(unittest.TestCase):
                    def test_tempdir_left_behind(self):
                        tempfile.mkdtemp(prefix="hp-guard-soft-leak-")

                    def test_thread_left_running(self):
                        t = threading.Thread(target=time.sleep, args=(3,),
                                             name="hp-guard-soft-thread",
                                             daemon=True)
                        t.start()

                    def test_clean(self):
                        pass
                '''))

    def tearDown(self):
        base = tempfile.gettempdir()
        for name in os.listdir(base):
            if name.startswith("hp-guard-soft-leak-"):
                shutil.rmtree(os.path.join(base, name), ignore_errors=True)

    def test_a_tempdir_and_a_thread_are_named_as_soft_leaks(self):
        rc, out = G.run_python([os.path.join("runner", "tools",
                                             "regression_guard.py"),
                                "--leaks", self.path])
        self.assertEqual(rc, 0, out)
        leaks = [json.loads(l[5:]) for l in out.splitlines()
                 if l.startswith("LEAK ")]
        by_test = {}
        for leak in leaks:
            by_test.setdefault(leak["test"].rsplit(".", 1)[1], []).append(
                leak["what"])
        self.assertEqual(by_test.get("test_tempdir_left_behind"),
                         ["tempdir"], leaks)
        self.assertEqual(by_test.get("test_thread_left_running"),
                         ["threads"], leaks)
        self.assertNotIn("test_clean", by_test)
        for leak in leaks:
            self.assertNotIn(leak["what"], G._HARD_LEAKS)
        detail = [l["detail"] for l in leaks if l["what"] == "threads"][0]
        self.assertIn("hp-guard-soft-thread", detail)

    def test_the_report_splits_hard_from_soft(self):
        with mock.patch.object(G, "run_python", return_value=(0, (
                'LEAK {"test": "m.T.test_a", "what": "tempdir", '
                '"detail": "left behind: [\'x\']"}\n'
                'LEAK {"test": "m.T.test_b", "what": "environ", '
                '"detail": "added [\'K\']"}\n'))):
            verdict = G.check_leaks("test_whatever.py")
        self.assertFalse(verdict.ok)
        self.assertIn("1 hard, 1 soft", verdict.note)
        with mock.patch.object(G, "run_python", return_value=(0, (
                'LEAK {"test": "m.T.test_a", "what": "tempdir", '
                '"detail": "left behind: [\'x\']"}\n'))):
            verdict = G.check_leaks("test_whatever.py")
        self.assertTrue(verdict.ok)
        self.assertIn("0 hard, 1 soft", verdict.note)


class ChangedModulesTest(unittest.TestCase):
    def setUp(self):
        try:
            subprocess.run(["git", "--version"], check=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is not on PATH")
        self.tmp = tempfile.mkdtemp(prefix="hp-guard-git-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.tests = os.path.join(self.tmp, "runner", "tests")
        os.makedirs(self.tests)
        self._git("init", "-q")
        self._git("config", "user.email", "guard@example.com")
        self._git("config", "user.name", "guard")
        self._write("test_old.py")
        self._write("helper.py")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "base")
        self._git("tag", "base")
        self._write("test_old.py", "# changed\n")
        self._write("test_new.py")
        self._write("helper.py", "# changed too\n")
        os.makedirs(os.path.join(self.tests, "archive"))
        self._write(os.path.join("archive", "test_deep.py"))
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "change")
        self._write("test_staged.py")
        self._git("add", "runner/tests/test_staged.py")
        self._write("test_unstaged.py")

    def _git(self, *args):
        subprocess.run(["git"] + list(args), cwd=self.tmp, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _write(self, name, text="import unittest\n"):
        with open(os.path.join(self.tests, name), "w",
                  encoding="utf-8") as fh:
            fh.write(text)

    def test_changed_added_and_untracked_test_modules_only(self):
        got = G.changed_modules("base", cwd=self.tmp)
        self.assertEqual(got, ["test_new.py", "test_old.py",
                               "test_staged.py", "test_unstaged.py"])

    def test_existed_at(self):
        self.assertTrue(G.existed_at("base", "test_old.py", cwd=self.tmp))
        self.assertFalse(G.existed_at("base", "test_new.py", cwd=self.tmp))


class GuardEndToEndTest(unittest.TestCase):
    def test_one_cheap_module_native_plus_gates(self):
        lines = []
        status = G.guard(["test_skip_registry.py"], "origin/main",
                         repeat=0, shuffles=0, no_sim=True, no_leaks=True,
                         out=lines.append)
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertTrue(any(l.startswith("  green native") for l in lines))
        self.assertTrue(any(l.startswith("  green gates") for l in lines))
        self.assertTrue(lines[-1].startswith("regression guard: green"))

    def test_a_red_module_makes_the_guard_red(self):
        tmp = tempfile.mkdtemp(prefix="hp-guard-red-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.object(
                G, "check_native",
                return_value=(G.Verdict("native", False, "fake red"), None)), \
                mock.patch.object(
                    G, "check_gates",
                    return_value=G.Verdict("gates", True, "fake green")):
            lines = []
            status = G.guard(["test_anything.py"], "origin/main", 0, 0,
                             True, True, out=lines.append)
        self.assertEqual(status, 1)
        self.assertTrue(any(l.startswith("  RED   native") for l in lines))


if __name__ == "__main__":
    unittest.main()
