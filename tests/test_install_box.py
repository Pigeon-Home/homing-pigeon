"""The installer's box operations, with the host commands simulated.

Wipe, migrate, the Windows scheduled task, the doctor, and
the Ollama daemon. State dirs are temporary. schtasks,
taskkill, and systemctl are recorded, not run.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runner"))

import install as inst  # noqa: E402


class _Proc:
    def __init__(self, code=0, out=""):
        self.returncode = code
        self.stdout = out
        self.stderr = ""


class WipeMigrateTest(unittest.TestCase):
    def test_windows_state_dirs_include_every_profile(self):
        with tempfile.TemporaryDirectory() as drive:
            alice = os.path.join(drive, "Users", "alice",
                                 ".homing-pigeon")
            os.makedirs(alice)
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.dict(os.environ, {"SystemDrive": drive,
                                                "SystemRoot": drive}):
                found = inst._candidate_state_dirs()
            self.assertIn(alice, found)
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.dict(os.environ, {"SystemDrive": drive}), \
                    mock.patch.object(os, "listdir",
                                      side_effect=OSError("no")):
                inst._candidate_state_dirs()

    def test_wipe_unloads_each_platform_and_deletes_the_dirs(self):
        if os.name == "nt":
            self.skipTest("wipe unload differs on Windows")
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state")
            os.makedirs(state)
            with open(os.path.join(state, "a.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("x")
            quiet = []
            for plat in ("darwin", "linux", "win32"):
                os.makedirs(state, exist_ok=True)
                with mock.patch.object(inst.sys, "platform", plat), \
                        mock.patch.object(
                            inst, "_candidate_state_dirs",
                            return_value=[state]), \
                        mock.patch.object(
                            inst, "_run_quiet",
                            side_effect=lambda c: quiet.append(c)), \
                        mock.patch.object(inst, "_default_home",
                                          return_value=state):
                    self.assertEqual(
                        inst.do_wipe(backup_dir=d, no_backup=True), 0)
            self.assertFalse(os.path.exists(state))
            self.assertIn(
                ["launchctl", "bootout",
                 "gui/%s" % os.getuid(),
                 os.path.expanduser(
                     "~/Library/LaunchAgents/"
                     "com.homing-pigeon.runner.plist")],
                quiet)
            self.assertIn(
                ["systemctl", "--user", "disable", "--now",
                 "homing-pigeon.service"], quiet)
            self.assertIn(
                ["sudo", "-n", "systemctl", "disable", "--now",
                 "homing-pigeon.service"], quiet)
            self.assertIn(
                ["pkill", "-f", "[h]oming-pigeon"], quiet)
            self.assertIn(
                ["taskkill", "/F", "/IM", "homing-pigeon.exe"], quiet)
            self.assertIn(
                ["schtasks", "/Delete", "/TN", "HomingPigeon", "/F"],
                quiet)

    def test_a_backup_that_cannot_be_made_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state")
            os.makedirs(state)
            with mock.patch.object(
                    inst, "_candidate_state_dirs",
                    return_value=[state]), \
                    mock.patch.object(inst, "_run_quiet"), \
                    mock.patch.object(os, "makedirs",
                                      side_effect=OSError("full")):
                self.assertEqual(inst.do_wipe(backup_dir=d), 1)
            self.assertTrue(os.path.isdir(state))
            with mock.patch.object(
                    inst, "_candidate_state_dirs",
                    return_value=[state]), \
                    mock.patch.object(inst, "_run_quiet"), \
                    mock.patch.object(
                        inst, "_backup_dirs_to_zip",
                        side_effect=OSError("zip")):
                self.assertEqual(inst.do_wipe(backup_dir=d), 1)
            self.assertTrue(os.path.isdir(state))

    def test_a_dir_that_will_not_delete_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state")
            os.makedirs(state)
            with mock.patch.object(
                    inst, "_candidate_state_dirs",
                    return_value=[state]), \
                    mock.patch.object(inst, "_run_quiet"), \
                    mock.patch.object(inst.shutil, "rmtree",
                                      side_effect=OSError("busy")):
                self.assertEqual(inst.do_wipe(no_backup=True), 0)
            self.assertTrue(os.path.isdir(state))

    def test_migrate_copies_and_refuses_a_bad_target(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "old")
            os.makedirs(src)
            with open(os.path.join(src, "a.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("a")
            target = os.path.join(d, "new")
            with mock.patch.object(
                    inst, "_candidate_state_dirs",
                    return_value=[src]):
                self.assertEqual(inst.do_migrate(target), 0)
                with open(os.path.join(target, "a.txt"),
                          encoding="utf-8") as fh:
                    self.assertEqual(fh.read(), "a")
                self.assertEqual(inst.do_migrate(target), 0)
            with mock.patch.object(os, "makedirs",
                                  side_effect=OSError("no")):
                self.assertEqual(inst.do_migrate(
                    os.path.join(d, "nope")), 1)

    def test_a_copy_that_fails_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            os.makedirs(src)
            with open(os.path.join(src, "a.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("a")
            dst = os.path.join(d, "dst")
            os.makedirs(dst)
            with open(os.path.join(dst, "a.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write("old")
            copied, skipped = inst._merge_tree(src, dst)
            self.assertEqual((copied, skipped), (0, 1))
            with mock.patch.object(os, "makedirs",
                                  side_effect=OSError("no")):
                copied, skipped = inst._merge_tree(src, os.path.join(
                    d, "missing", "child"))
            self.assertEqual(copied, 0)
            self.assertGreaterEqual(skipped, 1)


class WindowsTaskTest(unittest.TestCase):
    def test_the_task_query_end_and_process_check(self):
        def run(cmd, **_kw):
            if "/End" in cmd:
                return _Proc(0)
            if "/Run" in cmd:
                return _Proc(1)
            if cmd[0] == "tasklist":
                return _Proc(0, "homing-pigeon.exe  12\n")
            if "/V" in cmd:
                return _Proc(0, "Task To Run: C:\\hp\\homing-pigeon.exe\n")
            return _Proc(0)

        with mock.patch.object(inst.subprocess, "run", run):
            self.assertTrue(inst._task_exists())
            self.assertIn("homing-pigeon.exe", inst._task_command())
            self.assertEqual(inst._task_end(), 0)
            self.assertEqual(inst._task_run(), 1)
            self.assertTrue(inst._process_running("homing-pigeon.exe"))
        with mock.patch.object(inst.subprocess, "run",
                               return_value=_Proc(1, "no tasks")):
            self.assertFalse(inst._task_exists())
            self.assertIsNone(inst._task_command())
            self.assertFalse(inst._process_running("homing-pigeon.exe"))

    def test_an_upgrade_stops_the_task_or_warns(self):
        with mock.patch.object(inst.sys, "platform", "linux"):
            inst._stop_task_for_upgrade()
        with mock.patch.object(inst.sys, "platform", "win32"), \
                mock.patch.object(inst, "_task_exists", return_value=True), \
                mock.patch.object(inst, "_task_end", return_value=0), \
                mock.patch.object(inst, "_wait_for_exit",
                                  return_value=True) as waited:
            inst._stop_task_for_upgrade()
        waited.assert_called()
        with mock.patch.object(inst.sys, "platform", "win32"), \
                mock.patch.object(inst, "_task_exists", return_value=True), \
                mock.patch.object(inst, "_task_end", return_value=1):
            inst._stop_task_for_upgrade()
        with mock.patch.object(inst, "_process_running", return_value=True), \
                mock.patch.object(inst.time, "sleep"):
            self.assertFalse(inst._wait_for_exit("homing-pigeon.exe",
                                                 timeout=0))


class DoctorTest(unittest.TestCase):
    def _home(self, root, cfg):
        home = os.path.join(root, "home")
        bind = os.path.join(home, "bin")
        state = os.path.join(home, "state")
        os.makedirs(bind, exist_ok=True)
        os.makedirs(state, exist_ok=True)
        exe = os.path.join(bind, inst.RUNNER_BIN)
        with open(exe, "w", encoding="utf-8") as fh:
            fh.write("bin")
        path = os.path.join(home, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        with open(os.path.join(home, "install-receipt.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"version": "3.9.0", "installed_at": "t",
                       "installed_by": "me"}, fh)
        return home, bind, path, state

    def test_a_windows_home_with_a_task_pointing_elsewhere(self):
        with tempfile.TemporaryDirectory() as root:
            home, bind, cfg, state = self._home(root, {
                "shared_secret": "x" * 64,
                "base_dir": "/somewhere/else",
                "inference": {"endpoint": "http://10.0.0.5:11434/v1"},
            })
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(inst, "_task_exists",
                                      return_value=True), \
                    mock.patch.object(
                        inst, "_task_command",
                        return_value=r"C:\other\homing-pigeon.exe"), \
                    mock.patch.object(
                        inst, "collector_health_rows", return_value=[]):
                code = inst.do_check(home, bind, cfg, state)
            self.assertEqual(code, 0)

    def test_deterministic_mode_and_a_dead_loopback_are_named(self):
        with tempfile.TemporaryDirectory() as root:
            home, bind, cfg, state = self._home(root, {
                "shared_secret": "x" * 64,
                "oracle_mode": "deterministic",
            })
            task = os.path.join(bind, inst.RUNNER_BIN)
            with mock.patch.object(
                    inst, "collector_health_rows", return_value=[
                        ("osquery", "WORKS", "running"),
                        ("falco", "INSTALLED-BUT-CANNOT-RUN", "bpf"),
                        ("zeek", "ABSENT", "not installed")]), \
                    mock.patch.object(inst, "_task_exists",
                                      return_value=True), \
                    mock.patch.object(inst, "_task_command",
                                      return_value=task):
                self.assertEqual(
                    inst.do_check(home, bind, cfg, state), 0)
            home, bind, cfg, state = self._home(root, {
                "shared_secret": "x" * 64,
                "inference": {"endpoint": "http://127.0.0.1:1/v1"},
            })
            task = os.path.join(bind, inst.RUNNER_BIN)
            with mock.patch.object(
                    inst, "collector_health_rows", return_value=[]), \
                    mock.patch.object(inst, "_task_exists",
                                      return_value=True), \
                    mock.patch.object(inst, "_task_command",
                                      return_value=task):
                self.assertEqual(
                    inst.do_check(home, bind, cfg, state), 0)

    def test_a_missing_home_fails_the_check(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(
                    inst, "collector_health_rows", return_value=[]):
                code = inst.do_check(
                    os.path.join(root, "missing"),
                    os.path.join(root, "bin"),
                    os.path.join(root, "no.json"),
                    os.path.join(root, "state"))
            self.assertEqual(code, 1)


class ConsoleAndLogsTest(unittest.TestCase):
    def test_console_stops_runs_and_restarts(self):
        if os.name == "nt":
            self.skipTest("console behavior differs on Windows")
        self.assertEqual(inst.do_console("/h", "/b", "/c"), 2)
        with tempfile.TemporaryDirectory() as home:
            bind = os.path.join(home, "bin")
            os.makedirs(bind)
            exe = os.path.join(bind, inst.RUNNER_BIN)
            cfg = os.path.join(home, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            with mock.patch.object(inst.sys, "platform", "win32"):
                self.assertEqual(inst.do_console(home, bind, cfg), 1)
                with open(exe, "w", encoding="utf-8") as fh:
                    fh.write("bin")
                with mock.patch.object(inst, "_task_exists",
                                       return_value=True), \
                        mock.patch.object(inst, "_task_end"), \
                        mock.patch.object(inst, "_wait_for_exit"), \
                        mock.patch.object(inst, "_process_running",
                                          return_value=True):
                    self.assertEqual(
                        inst.do_console(home, bind, cfg), 1)
                with mock.patch.object(inst, "_task_exists",
                                       return_value=True), \
                        mock.patch.object(inst, "_task_end"), \
                        mock.patch.object(inst, "_wait_for_exit"), \
                        mock.patch.object(inst, "_process_running",
                                          return_value=False), \
                        mock.patch.object(
                            inst.subprocess, "run",
                            side_effect=KeyboardInterrupt), \
                        mock.patch.object(inst, "_task_run",
                                          return_value=1):
                    self.assertEqual(
                        inst.do_console(home, bind, cfg), 1)

    def test_logs_follow_until_interrupted(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("not-json")
            self.assertEqual(inst.do_logs(cfg), 1)
            log = os.path.join(d, "runner.log")
            with open(log, "w", encoding="utf-8") as fh:
                fh.write("one\ntwo\n")

            class _FH:
                n = 0

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def seek(self, *_a):
                    return None

                def readline(self):
                    self.n += 1
                    if self.n == 1:
                        return "three"
                    raise KeyboardInterrupt

            with mock.patch("builtins.open", return_value=_FH()):
                self.assertEqual(inst.do_logs(cfg, follow=True), 0)


class PackageFetchTest(unittest.TestCase):
    def test_a_listing_picks_the_newest_and_an_empty_one_fails(self):
        html = ("falco-0.1.0-x86_64.deb "
                "falco-0.2.0-x86_64.deb")
        with mock.patch.object(inst, "_download",
                               return_value=html.encode()):
            got = inst._newest_from_listing(
                "https://example.test/deb/",
                r"(falco-(\d+\.\d+\.\d+)-x86_64\.deb)")
        self.assertTrue(got.endswith("falco-0.2.0-x86_64.deb"))
        with mock.patch.object(inst, "_download", return_value=b""):
            with self.assertRaises(RuntimeError):
                inst._newest_from_listing(
                    "https://example.test/", r"(nope-(\d+))")

    def test_an_armored_key_is_dearmored(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "k.gpg")
            ran = []

            def gpg(cmd, **kw):
                ran.append(cmd)
                with open(dest, "wb") as fh:
                    fh.write(b"bin")

            with mock.patch.object(
                    inst, "_download",
                    return_value=b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n"), \
                    mock.patch.object(inst.subprocess, "run", gpg):
                self.assertEqual(
                    inst._write_keyring(["https://example.test/k"], dest),
                    dest)
            self.assertIn("--dearmor", ran[0])
            self.assertIn("--batch", ran[0])
            self.assertIn("--yes", ran[0])

    def test_the_apt_repo_line_names_the_keyring(self):
        written = {}

        def opener(path, *a, **k):
            class _F:
                def __enter__(self):
                    return self

                def __exit__(self, *x):
                    return False

                def write(self, text):
                    written[path] = text
            return _F()

        with mock.patch.object(inst, "_write_keyring",
                               return_value="/usr/share/keyrings/z.gpg"), \
                mock.patch.object(inst, "run") as run, \
                mock.patch("builtins.open", opener):
            inst._apt_repo(
                "zeek", "deb [signed-by={keyring}] http://x /",
                ["https://example.test/k"])
        text = written["/etc/apt/sources.list.d/zeek.list"]
        self.assertIn(
            "signed-by=/usr/share/keyrings/zeek-archive-keyring.gpg",
            text)
        self.assertNotIn("{keyring}", text)
        run.assert_called_once_with(["apt-get", "update"])

    def test_ollama_starts_or_reports_why_it_did_not(self):
        with mock.patch.object(inst, "_ollama_up", return_value=True):
            self.assertTrue(inst.ensure_ollama_running())
        with mock.patch.object(inst, "_ollama_up", return_value=False), \
                mock.patch.object(inst, "_ollama_bin", return_value=None):
            self.assertFalse(inst.ensure_ollama_running())
        with mock.patch.object(inst, "_ollama_up", return_value=False), \
                mock.patch.object(inst, "_ollama_bin",
                                  return_value="/usr/bin/ollama"), \
                mock.patch.object(inst.subprocess, "Popen",
                                  side_effect=OSError("no")):
            self.assertFalse(inst.ensure_ollama_running())
        started = mock.Mock()
        with mock.patch.object(inst, "_ollama_up", return_value=False), \
                mock.patch.object(inst, "_ollama_bin",
                                  return_value="/usr/bin/ollama"), \
                mock.patch.object(inst.subprocess, "Popen", started), \
                mock.patch.object(inst.time, "sleep"):
            self.assertFalse(inst.ensure_ollama_running())
        self.assertEqual(started.call_args[0][0],
                         ["/usr/bin/ollama", "serve"])

    def test_windows_winget_installs_ollama(self):
        bins = iter([None, r"C:\Ollama\ollama.exe"])
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            cmds = []
            with mock.patch.object(inst.sys, "platform", "win32"), \
                    mock.patch.object(
                        inst, "_ollama_bin",
                        side_effect=lambda: next(bins)), \
                    mock.patch.object(inst, "_which",
                                      return_value="winget"), \
                    mock.patch.object(
                        inst, "run",
                        side_effect=lambda c, **k: cmds.append(c)), \
                    mock.patch.object(inst, "ensure_ollama_running",
                                      return_value=True):
                self.assertTrue(inst.install_ollama_and_model(
                    cfg, "qwen3:1.7b", False))
            self.assertEqual(cmds[0][0], "winget")
            self.assertEqual(cmds[0][3], "Ollama.Ollama")

    def test_the_bpf_and_service_probes_fail_closed(self):
        with mock.patch.object(inst.subprocess, "run",
                               return_value=_Proc(0, "active\n")):
            self.assertTrue(inst._service_active("osqueryd"))
        with mock.patch.object(inst.subprocess, "run",
                               return_value=_Proc(0, "activating\n")):
            self.assertFalse(inst._service_active("osqueryd"))
        with mock.patch.object(inst.subprocess, "run",
                               side_effect=OSError):
            self.assertFalse(inst._service_active("osqueryd"))
        with mock.patch.object(os, "listdir", return_value=["12", "self"]):
            def opener(path, *a, **k):
                if str(path).endswith("comm"):
                    raise OSError("gone")
                raise OSError(path)
            with mock.patch("builtins.open", opener):
                self.assertFalse(inst._proc_running("zeek"))
        self.assertIsNone(inst._artifact_age("/no/such/feed"))
        with mock.patch.object(inst.time, "time", return_value=0), \
                mock.patch.object(inst.os.path, "getmtime",
                                  return_value=50):
            self.assertEqual(inst._artifact_age("x"), 0.0)
        with mock.patch.object(inst.shutil, "which",
                               side_effect=OSError("win32")):
            self.assertIsNone(inst._which_safe("osqueryd"))
