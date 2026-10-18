"""Linux process control: the kill signal and the daemon session.

Unit cases, one-field mutations, and a deterministic fuzz.
os.killpg and subprocess.Popen are mocked. Nothing here signals a
real process or starts one.
"""
import os
import random
import signal
import tempfile
import unittest
from unittest import mock

from runner.runner import _spawn_daemon, daemon_popen_kwargs, kill_tree
from runner.install import daemon_popen_kwargs as install_daemon_kwargs


def _proc(pid=42):
    proc = mock.Mock()
    proc.pid = pid
    return proc


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class KillSignalTest(unittest.TestCase):
    def test_linux_sends_sigkill_to_the_group(self):
        proc = _proc(42)
        with mock.patch("runner.runner.os.name", "posix"), \
             mock.patch("runner.runner.os.killpg") as killpg, \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=AssertionError("taskkill")):
            kill_tree(proc)
        killpg.assert_called_once_with(42, signal.SIGKILL)
        self.assertNotEqual(signal.SIGKILL, signal.SIGTERM)
        proc.kill.assert_not_called()

    def test_a_missing_group_falls_back_to_the_process(self):
        proc = _proc(7)
        with mock.patch("runner.runner.os.name", "posix"), \
             mock.patch("runner.runner.os.killpg", side_effect=OSError("no group")), \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=AssertionError("taskkill")):
            kill_tree(proc)
        proc.kill.assert_called_once()

    def test_both_kills_failing_does_not_raise(self):
        proc = _proc(7)
        proc.kill.side_effect = OSError("gone")
        with mock.patch("runner.runner.os.name", "posix"), \
             mock.patch("runner.runner.os.killpg", side_effect=ProcessLookupError("no")):
            kill_tree(proc)


class KillMutations(unittest.TestCase):
    def test_pid_and_platform_mutations(self):
        for pid in (0, -1, None, "42", 1):
            proc = _proc(pid)
            with mock.patch("runner.runner.os.name", "posix"), \
                 mock.patch("runner.runner.os.killpg") as killpg, \
                 mock.patch("runner.runner.subprocess.run",
                            side_effect=AssertionError("taskkill")):
                kill_tree(proc)
            self.assertEqual(killpg.call_args.args[1], signal.SIGKILL)
            self.assertIs(killpg.call_args.args[0], pid)

        proc = _proc(42)
        with mock.patch("runner.runner.os.name", "nt"), \
             mock.patch("runner.runner.os.killpg",
                        side_effect=AssertionError("killpg")), \
             mock.patch("runner.runner.subprocess.run") as run:
            kill_tree(proc)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], ["taskkill", "/PID", "42"])
        self.assertIn("/T", argv)
        self.assertIn("/F", argv)


class DaemonSessionTest(unittest.TestCase):
    def test_posix_kwargs_match_in_both_copies(self):
        for fn in (daemon_popen_kwargs, install_daemon_kwargs):
            kw = fn(False)
            self.assertTrue(kw["start_new_session"])
            self.assertNotIn("creationflags", kw)
            self.assertIs(kw["stdout"].name if hasattr(kw["stdout"], "name") else kw["stdout"],
                          subprocess_devnull())
            self.assertEqual(kw["stdout"], kw["stderr"])

    def test_spawn_does_not_use_a_shell_and_detaches(self):
        with tempfile.TemporaryDirectory() as d:
            log_path = os.path.join(d, "oracle.log")
            with mock.patch("runner.runner.os.name", "posix"), \
                 mock.patch("runner.runner.subprocess.Popen") as popen:
                proc = _spawn_daemon(["ollama", "serve"], log_path=log_path)
            self.assertIs(proc, popen.return_value)
            argv, = popen.call_args.args
            kw = popen.call_args.kwargs
            self.assertEqual(argv, ["ollama", "serve"])
            self.assertNotIsInstance(argv, str)
            self.assertTrue(kw["start_new_session"])
            self.assertNotIn("creationflags", kw)
            self.assertEqual(kw["stdout"].mode, "ab")
            self.assertTrue(kw["stdout"].closed)
            self.assertEqual(kw["stdout"], kw["stderr"])

    def test_a_log_that_cannot_be_opened_stays_on_devnull(self):
        with mock.patch("runner.runner.os.name", "posix"), \
             mock.patch("runner.runner.subprocess.Popen") as popen, \
             mock.patch("builtins.open", side_effect=OSError("busy")):
            _spawn_daemon(["ollama", "serve"], log_path="/no/such/oracle.log")
        kw = popen.call_args.kwargs
        self.assertTrue(kw["start_new_session"])
        self.assertEqual(kw["stdout"], subprocess_devnull())


def subprocess_devnull():
    import subprocess
    return subprocess.DEVNULL


class ProcessFuzzTest(unittest.TestCase):
    def test_random_pids_never_signal_a_real_process(self):
        rng = random.Random(20261017)
        crashes = []
        seen = []

        def killpg(pid, sig):
            seen.append((pid, sig))
            if sig != signal.SIGKILL:
                raise AssertionError(sig)
            if rng.randrange(3) == 0:
                raise OSError("no group")

        with mock.patch("runner.runner.os.killpg", side_effect=killpg), \
             mock.patch("runner.runner.subprocess.run",
                        side_effect=AssertionError("taskkill")), \
             mock.patch("runner.runner.subprocess.Popen") as popen:
            for _ in range(200):
                proc = _proc(rng.choice([0, -1, 1, 42, None, "x", 2 ** 31]))
                if rng.randrange(5) == 0:
                    proc.kill.side_effect = OSError("gone")
                name = rng.choice(["posix", "linux", "darwin"])
                try:
                    with mock.patch("runner.runner.os.name", name):
                        kill_tree(proc)
                        if rng.randrange(4) == 0:
                            _spawn_daemon(
                                rng.choice([
                                    ["ollama", "serve"],
                                    ["ollama"],
                                ]),
                                log_path=None)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
        self.assertEqual(crashes, [])
        self.assertTrue(seen)
        self.assertTrue(all(sig == signal.SIGKILL for _pid, sig in seen))
        for call in popen.call_args_list:
            self.assertEqual(call.args[0][0], "ollama")
            self.assertTrue(call.kwargs["start_new_session"])
            self.assertNotIn("shell", call.kwargs)


if __name__ == "__main__":
    unittest.main()
