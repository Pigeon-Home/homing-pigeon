#!/usr/bin/env python3
"""The Windows one-home redesign: layout, receipt, doctor, console, logs.

Windows-only paths run with sys.platform / os.environ mocked; filesystem
work happens in temp dirs; subprocess is always mocked.
"""
import importlib.util
import io
import json
import os
import socket
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load install.py under a unique module name: no sys.path games, so this
# file can never shadow the runner package for other test modules.
_spec = importlib.util.spec_from_file_location(
    "install_onehome_under_test",
    os.path.join(REPO, "runner", "install.py"))
install = importlib.util.module_from_spec(_spec)
sys.modules["install_onehome_under_test"] = install
_spec.loader.exec_module(install)

from install_onehome_under_test import (  # noqa: E402
    _acl_home,
    _default_home,
    _is_admin,
    _read_receipt,
    _resolve_home,
    _runner_log_path,
    _tail_file,
    _write_receipt,
    do_check,
    do_console,
    do_install_home,
    do_logs,
    do_oracle,
    do_wipe,
    install_files,
)


def _args(**kw):
    base = dict(dir=None, home=None, config=None, shared_secret=None,
                additional_secret=[], profile=None, no_profile=True,
                inference_model=None, no_inference=True, instructions=None,
                instructions_add=None, run_as=None, dry_run=False,
                no_send=False, pdb=False, verbose=True, poll_interval=None,
                max_output_bytes=None, timeout=None, workers=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


def _seed(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class HomePathTest(unittest.TestCase):
    def test_default_home_uses_system_drive(self):
        with mock.patch.dict(os.environ, {"SystemDrive": "D:"}):
            home = _default_home()
        self.assertTrue(home.startswith("D:"))
        self.assertTrue(home.endswith("homing-pigeon"))

    def test_default_home_falls_back_to_c(self):
        env = {k: v for k, v in os.environ.items() if k != "SystemDrive"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(_default_home().startswith("C:"))

    def test_resolve_home_windows_default(self):
        with mock.patch.object(sys, "platform", "win32"):
            home, bin_dir, cfg, state = _resolve_home(_args())
        self.assertTrue(home.endswith("homing-pigeon"))
        self.assertEqual(bin_dir, os.path.join(home, "bin"))
        self.assertEqual(cfg, os.path.join(home, "config.json"))
        self.assertEqual(state, os.path.join(home, "state"))

    def test_resolve_home_explicit_home(self):
        with mock.patch.object(sys, "platform", "win32"):
            home, bin_dir, cfg, state = _resolve_home(
                _args(home="X:\\pigeon"))
        self.assertEqual(bin_dir, os.path.join(home, "bin"))
        self.assertEqual(cfg, os.path.join(home, "config.json"))
        self.assertEqual(state, os.path.join(home, "state"))

    def test_resolve_home_explicit_dir_without_home_is_legacy(self):
        with mock.patch.object(sys, "platform", "win32"):
            self.assertIsNone(_resolve_home(_args(dir="D:\\custom")))

    def test_resolve_home_home_and_dir(self):
        with mock.patch.object(sys, "platform", "win32"):
            home, bin_dir, cfg, state = _resolve_home(
                _args(home="X:\\pigeon", dir="Y:\\bins"))
        self.assertEqual(home, os.path.abspath("X:\\pigeon"))
        self.assertEqual(bin_dir, os.path.abspath("Y:\\bins"))
        self.assertEqual(cfg, os.path.join(home, "config.json"))

    def test_resolve_home_explicit_config_wins(self):
        with mock.patch.object(sys, "platform", "win32"):
            home, _b, cfg, _s = _resolve_home(
                _args(config="Z:\\elsewhere\\c.json"))
        self.assertEqual(cfg, os.path.abspath("Z:\\elsewhere\\c.json"))

    def test_resolve_home_not_windows(self):
        with mock.patch.object(sys, "platform", "linux"):
            self.assertIsNone(_resolve_home(_args()))


class ReceiptTest(unittest.TestCase):
    def test_missing_is_none(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertIsNone(_read_receipt(t))

    def test_corrupt_is_flagged(self):
        with tempfile.TemporaryDirectory() as t:
            _seed(os.path.join(t, "install-receipt.json"), "not json{")
            self.assertEqual(_read_receipt(t), "corrupt")

    def test_write_then_read_fresh(self):
        with tempfile.TemporaryDirectory() as t:
            with mock.patch.dict(os.environ, {"USERNAME": "tester"}):
                _write_receipt(t, fresh=True)
            r = _read_receipt(t)
            self.assertEqual(r["version"], install.__version__)
            self.assertEqual(r["layout_version"], 1)
            self.assertIn("tester", r["installed_by"])
            self.assertIn("installed_at", r)
            self.assertNotIn("upgraded_at", r)

    def test_upgrade_keeps_installed_at(self):
        with tempfile.TemporaryDirectory() as t:
            _write_receipt(t, fresh=True)
            first = _read_receipt(t)
            _write_receipt(t, fresh=False)
            second = _read_receipt(t)
            self.assertEqual(second["installed_at"], first["installed_at"])
            self.assertEqual(second["installed_by"], first["installed_by"])
            self.assertIn("upgraded_at", second)


class InstallFilesTest(unittest.TestCase):
    def _src(self, t):
        src = os.path.join(t, "src")
        for name in ("runner.py", "oauth.py", "winlog.py",
                     "config.example.json"):
            _seed(os.path.join(src, name), '{"example": true}\n')
        return src

    def test_seeds_config_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            src = self._src(t)
            bin_dir = os.path.join(t, "home", "bin")
            cfg = os.path.join(t, "home", "config.json")
            with redirect_stdout(io.StringIO()):
                self.assertTrue(install_files(src, bin_dir, cfg))
            for name in ("runner.py", "oauth.py", "winlog.py"):
                self.assertTrue(os.path.isfile(os.path.join(bin_dir, name)))
            with open(cfg, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {"example": True})
            # A second run leaves an existing config alone.
            _seed(cfg, '{"mine": 1}\n')
            with redirect_stdout(io.StringIO()):
                self.assertTrue(install_files(src, bin_dir, cfg))
            with open(cfg, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {"mine": 1})


class _HomeTree:
    """A fake one-home tree in a temp dir, with a live inference socket."""

    def __init__(self, test):
        self.test = test
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        t = self.tmp.name
        self.home = os.path.join(t, "homing-pigeon")
        self.bin = os.path.join(self.home, "bin")
        self.cfg = os.path.join(self.home, "config.json")
        self.state = os.path.join(self.home, "state")
        os.makedirs(self.bin)
        os.makedirs(self.state)
        _seed(os.path.join(self.bin, install.RUNNER_BIN), "exe")
        _write_receipt(self.home, fresh=True)
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        test.addCleanup(self.srv.close)
        port = self.srv.getsockname()[1]
        _seed(self.cfg, json.dumps({
            "shared_secret": "s" * 64,
            "base_dir": self.state,
            "inference": {"endpoint": f"http://127.0.0.1:{port}/v1"},
        }))


class CheckTest(unittest.TestCase):
    def test_all_pass(self):
        tree = _HomeTree(self)
        buf = io.StringIO()
        with mock.patch.object(install, "_task_exists", return_value=True), \
             mock.patch.object(install, "_task_command",
                               return_value=os.path.join(
                                   tree.bin, install.RUNNER_BIN)), \
             redirect_stdout(buf):
            rc = do_check(tree.home, tree.bin, tree.cfg, tree.state)
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("0 failed", out)
        self.assertIn("PASS", out)
        self.assertNotIn("FAIL", out)

    def test_missing_home_fails(self):
        with tempfile.TemporaryDirectory() as t:
            home = os.path.join(t, "nope")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = do_check(home, os.path.join(home, "bin"),
                              os.path.join(home, "config.json"),
                              os.path.join(home, "state"))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", buf.getvalue())

    def test_missing_task_fails_on_windows(self):
        tree = _HomeTree(self)
        buf = io.StringIO()
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(install, "_task_exists", return_value=False), \
             redirect_stdout(buf):
            rc = do_check(tree.home, tree.bin, tree.cfg, tree.state)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL: scheduled task HomingPigeon", buf.getvalue())

    def test_task_pointing_elsewhere_warns(self):
        tree = _HomeTree(self)
        buf = io.StringIO()
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(install, "_task_exists", return_value=True), \
             mock.patch.object(install, "_task_command",
                               return_value="C:\\other\\homing-pigeon.exe"), \
             redirect_stdout(buf):
            rc = do_check(tree.home, tree.bin, tree.cfg, tree.state)
        self.assertEqual(rc, 0)
        self.assertIn("WARN: scheduled task HomingPigeon", buf.getvalue())

    def test_unconfigured_inference_warns(self):
        tree = _HomeTree(self)
        _seed(tree.cfg, json.dumps({"shared_secret": "s" * 64,
                                    "base_dir": tree.state}))
        buf = io.StringIO()
        with mock.patch.object(install, "_task_exists", return_value=True), \
             mock.patch.object(install, "_task_command",
                               return_value=os.path.join(
                                   tree.bin, install.RUNNER_BIN)), \
             redirect_stdout(buf):
            rc = do_check(tree.home, tree.bin, tree.cfg, tree.state)
        self.assertEqual(rc, 0)
        self.assertIn("WARN: inference", buf.getvalue())


class ConsoleTest(unittest.TestCase):
    def _tree(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        bin_dir = os.path.join(t.name, "bin")
        os.makedirs(bin_dir)
        exe = os.path.join(bin_dir, install.RUNNER_BIN)
        _seed(exe, "exe")
        cfg = os.path.join(t.name, "config.json")
        _seed(cfg, "{}")
        return bin_dir, cfg

    def _mocks(self, task_exists=True, run_side_effect=None):
        # NOTE: keep the patchers (not the started mocks): only the
        # patcher has a working .stop(). Stopping the started mock is a
        # silent no-op that leaks the patch into later tests.
        patches = [
            mock.patch.object(sys, "platform", "win32"),
            mock.patch.object(install, "_task_exists",
                              return_value=task_exists),
            mock.patch.object(install, "_task_end", return_value=0),
            mock.patch.object(install, "_task_run", return_value=0),
            mock.patch.object(install, "_process_running",
                              return_value=False),
            mock.patch.object(install, "_wait_for_exit", return_value=True),
            mock.patch.object(install.subprocess, "run",
                              side_effect=run_side_effect),
        ]
        started = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        return started[1], started[2], started[3], started[6]

    def test_restores_task_after_ctrl_c(self):
        bin_dir, cfg = self._tree()
        _m, _e, m_run, _s = self._mocks(
            run_side_effect=KeyboardInterrupt)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = do_console("home", bin_dir, cfg)
        self.assertEqual(rc, 0)
        m_run.assert_called_once_with()
        self.assertIn("restarting", buf.getvalue())

    def test_aborts_when_agent_wont_stop(self):
        bin_dir, cfg = self._tree()
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(install, "_task_exists", return_value=True), \
             mock.patch.object(install, "_task_end", return_value=0), \
             mock.patch.object(install, "_wait_for_exit", return_value=False), \
             mock.patch.object(install, "_process_running", return_value=True), \
             mock.patch.object(install, "_task_run") as m_run, \
             redirect_stdout(io.StringIO()):
            rc = do_console("home", bin_dir, cfg)
        self.assertEqual(rc, 1)
        m_run.assert_not_called()

    def test_no_task_runs_directly(self):
        bin_dir, cfg = self._tree()
        _m, m_end, m_run, m_sub = self._mocks(
            task_exists=False,
            run_side_effect=[mock.Mock(returncode=0)])
        with redirect_stdout(io.StringIO()):
            rc = do_console("home", bin_dir, cfg)
        self.assertEqual(rc, 0)
        m_end.assert_not_called()
        m_run.assert_not_called()
        m_sub.assert_called_once()

    def test_not_windows(self):
        with mock.patch.object(sys, "platform", "linux"), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(do_console("h", "b", "c"), 2)


class LogsTest(unittest.TestCase):
    def test_tail_file_last_n(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "f.log")
            with open(p, "w", encoding="utf-8") as fh:
                for i in range(100):
                    fh.write(f"line {i}\n")
            tail = _tail_file(p, 10)
            self.assertEqual(len(tail), 10)
            self.assertEqual(tail[0], "line 90")
            self.assertEqual(tail[-1], "line 99")

    def test_tail_file_no_trailing_newline(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "f.log")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("a\nb\nc")
            self.assertEqual(_tail_file(p, 2), ["b", "c"])

    def test_do_logs_missing_file(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = os.path.join(t, "config.json")
            _seed(cfg, "{}")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = do_logs(cfg)
            self.assertEqual(rc, 1)
            self.assertIn("no log file", buf.getvalue())

    def test_do_logs_prints_tail(self):
        with tempfile.TemporaryDirectory() as t:
            state = os.path.join(t, "state")
            os.makedirs(state)
            cfg = os.path.join(t, "config.json")
            _seed(cfg, json.dumps({"base_dir": state}))
            with open(os.path.join(state, "runner.log"), "w",
                      encoding="utf-8") as fh:
                for i in range(60):
                    fh.write(f"log line {i}\n")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = do_logs(cfg, lines=10)
            self.assertEqual(rc, 0)
            out = buf.getvalue().splitlines()
            self.assertEqual(len(out), 10)
            self.assertEqual(out[-1], "log line 59")

    def test_log_path_defaults_next_to_config(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = os.path.join(t, "config.json")
            _seed(cfg, "{}")
            self.assertEqual(_runner_log_path(cfg),
                             os.path.join(t, "runner.log"))


class WipeHomeTest(unittest.TestCase):
    def test_wipe_includes_the_one_home(self):
        with tempfile.TemporaryDirectory() as t:
            home = os.path.join(t, "homing-pigeon")
            os.makedirs(os.path.join(home, "bin"))
            _seed(os.path.join(home, "config.json"), "{}")
            stray = os.path.join(t, "user", ".homing-pigeon")
            os.makedirs(stray)
            _seed(os.path.join(stray, "runner.log"), "x")
            buf = io.StringIO()
            with mock.patch.object(sys, "platform", "win32"), \
                 mock.patch.object(install, "_default_home",
                                   return_value=home), \
                 mock.patch.object(install, "_candidate_state_dirs",
                                   return_value=[stray]), \
                 mock.patch.object(install, "_kill_runner_processes"), \
                 mock.patch.object(install, "_run_quiet"), \
                 redirect_stdout(buf):
                rc = do_wipe(no_backup=True)
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(home))
            self.assertFalse(os.path.exists(stray))
            self.assertIn("one home", buf.getvalue())


class MigrateTargetTest(unittest.TestCase):
    def test_migrate_defaults_to_home_state_on_windows(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(install, "do_migrate", return_value=0) as dm, \
             mock.patch.object(sys, "argv", ["install", "--migrate"]), \
             redirect_stdout(io.StringIO()):
            rc = install.main()
        self.assertEqual(rc, 0)
        dm.assert_called_once()
        target = dm.call_args[0][0]
        self.assertTrue(target.endswith("state"))
        self.assertIn("homing-pigeon", target)


class AclTest(unittest.TestCase):
    def test_builds_icacls_command(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(install.subprocess, "run",
                               return_value=mock.Mock(returncode=0,
                                                      stderr="",
                                                      stdout="")) as mr, \
             redirect_stdout(io.StringIO()):
            self.assertTrue(_acl_home("C:\\homing-pigeon"))
        cmd = mr.call_args[0][0]
        self.assertEqual(cmd[0], "icacls")
        self.assertIn("SYSTEM:(OI)(CI)F", cmd)
        self.assertIn("Administrators:(OI)(CI)F", cmd)

    def test_failure_warns(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(install.subprocess, "run",
                               return_value=mock.Mock(returncode=1,
                                                      stderr="denied",
                                                      stdout="")), \
             redirect_stdout(io.StringIO()) as buf:
            self.assertFalse(_acl_home("C:\\homing-pigeon"))
        self.assertIn("warn", buf.getvalue())

    def test_run_as_account_gets_a_grant(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(install.subprocess, "run",
                               return_value=mock.Mock(returncode=0,
                                                      stderr="",
                                                      stdout="")) as mr, \
             redirect_stdout(io.StringIO()):
            self.assertTrue(_acl_home("C:\\homing-pigeon", run_as="pigeon"))
        cmd = mr.call_args[0][0]
        self.assertIn("pigeon:(OI)(CI)F", cmd)

    def test_system_run_as_adds_no_grant(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(install.subprocess, "run",
                               return_value=mock.Mock(returncode=0,
                                                      stderr="",
                                                      stdout="")) as mr, \
             redirect_stdout(io.StringIO()):
            self.assertTrue(_acl_home("C:\\homing-pigeon", run_as="SYSTEM"))
        cmd = mr.call_args[0][0]
        self.assertEqual(len([a for a in cmd if a == "/grant:r"]), 2)

    def test_is_admin_trivially_true_off_windows(self):
        with mock.patch.object(sys, "platform", "linux"):
            self.assertTrue(_is_admin())


class DoInstallHomeTest(unittest.TestCase):
    def _home(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        home = os.path.join(t.name, "homing-pigeon")
        return home, os.path.join(home, "bin"), \
            os.path.join(home, "config.json"), os.path.join(home, "state")

    def _patch_common(self):
        # Keep the patchers: only the patcher has a working .stop().
        patches = [
            mock.patch.object(install, "_is_admin", return_value=True),
            mock.patch.object(install, "_acl_home", return_value=True),
            mock.patch.object(install, "_setup_fresh_config",
                              return_value=(True, "llama3.2:3b", False)),
            mock.patch.object(install, "install_windows"),
        ]
        started = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        return started[1], started[2], started[3]

    def test_fresh_install_lays_out_the_home(self):
        home, bin_dir, cfg, state = self._home()
        m_acl, m_setup, m_win = self._patch_common()

        def fake_files(src_dir, b, c):
            _seed(c, '{"fresh": true}\n')
            return True

        with mock.patch.object(install, "install_files",
                               side_effect=fake_files), \
             redirect_stdout(io.StringIO()):
            rc = do_install_home(_args(), home, bin_dir, cfg, state, "src")
        self.assertEqual(rc, 0)
        m_acl.assert_called_once_with(home, None)
        m_setup.assert_called_once()
        m_win.assert_called_once()
        # Task points at the home bin with the home config.
        _b, c, _e = m_win.call_args[0][:3]
        self.assertEqual(c, cfg)
        # base_dir pins state inside the home.
        with open(cfg, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["base_dir"], state)
        r = _read_receipt(home)
        self.assertIn("installed_at", r)
        self.assertTrue(os.path.isdir(state))

    def test_upgrade_leaves_config_and_state_alone(self):
        home, bin_dir, cfg, state = self._home()
        _m_acl, m_setup, m_win = self._patch_common()
        os.makedirs(state)
        _write_receipt(home, fresh=True)
        before = {"shared_secret": "s" * 64, "base_dir": state,
                  "owner_instructions": "do not touch"}
        _seed(cfg, json.dumps(before))
        _seed(os.path.join(state, "retained.json"), "precious")
        with mock.patch.object(install, "install_files",
                               return_value=True) as m_files, \
             mock.patch.object(install, "_stop_task_for_upgrade") as m_stop, \
             redirect_stdout(io.StringIO()):
            rc = do_install_home(_args(), home, bin_dir, cfg, state, "src")
        self.assertEqual(rc, 0)
        m_files.assert_called_once()
        m_stop.assert_called_once()
        m_setup.assert_not_called()
        with open(cfg, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), before)
        self.assertTrue(os.path.isfile(os.path.join(state, "retained.json")))
        r = _read_receipt(home)
        self.assertIn("upgraded_at", r)
        self.assertIn("installed_at", r)

    def test_fresh_install_needs_elevation(self):
        home, bin_dir, cfg, state = self._home()
        with mock.patch.object(install, "_is_admin", return_value=False), \
             redirect_stdout(io.StringIO()) as buf:
            rc = do_install_home(_args(), home, bin_dir, cfg, state, "src")
        self.assertEqual(rc, 2)
        self.assertIn("administrator", buf.getvalue())
        self.assertFalse(os.path.exists(home))

    def test_oracle_passthrough(self):
        with tempfile.TemporaryDirectory() as t:
            bin_dir = os.path.join(t, "bin")
            os.makedirs(bin_dir)
            cfg = os.path.join(t, "config.json")
            _seed(cfg, "{}")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(do_oracle(bin_dir, cfg), 1)
            exe = os.path.join(bin_dir, install.RUNNER_BIN)
            _seed(exe, "exe")
            with mock.patch.object(install.subprocess, "run",
                                   return_value=mock.Mock(
                                       returncode=3)) as mr, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(do_oracle(bin_dir, cfg), 3)
            self.assertEqual(mr.call_args[0][0],
                             [exe, "--oracle", "--config", cfg])


if __name__ == "__main__":
    unittest.main()
