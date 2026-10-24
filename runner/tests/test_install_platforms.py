"""Each install environment, with the package commands simulated.

No apt, no brew, no schtasks, no launchctl. The commands are
recorded. Files that would land in /etc are recorded too.
A user systemd unit and a launchd agent land in a fake home.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runner"))

from ops import install as inst  # noqa: E402


def _args(**kw):
    return mock.Mock(**kw)


def _home_env(home):
    return {"HOME": home, "USERPROFILE": home}


def _linux():
    """Run main() down the Linux branch on any host platform."""
    return mock.patch.object(inst.sys, "platform", "linux")


class _Pkg:
    """A simulated package environment. Records commands and files."""

    def __init__(self):
        self.cmds = []
        self.files = {}
        self.dirs = []

    def run(self, cmd, **_kw):
        self.cmds.append(list(cmd))

    def write_text(self, path, text, mode=0o644):
        self.files[path] = (text, mode)

    def makedirs(self, path, exist_ok=False):
        self.dirs.append(path)


class ServiceEnvTest(unittest.TestCase):
    def test_linux_user_unit_lands_in_the_home(self):
        pkg = _Pkg()
        with tempfile.TemporaryDirectory() as home:
            # HOME for posixpath.expanduser, USERPROFILE for ntpath's,
            # so the unit lands in the fake home on every platform.
            with mock.patch.dict(os.environ, _home_env(home)), \
                    mock.patch.object(inst, "run", pkg.run):
                inst.install_linux(
                    "/opt/hp", "/opt/hp/config.json", False,
                    ["--quiet"])
                path = os.path.join(
                    home, ".config", "systemd", "user",
                    "homing-pigeon.service")
                with open(path, encoding="utf-8") as fh:
                    unit = fh.read()
                inst.uninstall_linux(False)
            self.assertFalse(os.path.exists(path))
        self.assertIn("default.target", unit)
        self.assertIn("--quiet", unit)
        self.assertIn("runner.py", unit)
        self.assertIn("Restart=always", unit)
        self.assertIn("RestartSec=10", unit)
        self.assertIn("After=network-online.target", unit)
        self.assertIn("Wants=network-online.target", unit)
        self.assertIn(
            ["systemctl", "--user", "enable", "--now",
             "homing-pigeon.service"], pkg.cmds)

    def test_linux_system_unit_is_the_multi_user_target(self):
        pkg = _Pkg()
        removed = []
        with mock.patch.object(inst, "run", pkg.run), \
                mock.patch.object(inst, "_write_text", pkg.write_text), \
                mock.patch.object(os, "remove", removed.append):
            inst.install_linux("/opt/hp", "/opt/hp/c.json", True)
            inst.uninstall_linux(True)
        path = "/etc/systemd/system/homing-pigeon.service"
        self.assertIn("multi-user.target", pkg.files[path][0])
        self.assertEqual(removed, [path])
        self.assertIn(
            ["systemctl", "enable", "--now", "homing-pigeon.service"],
            pkg.cmds)

    def test_a_newline_in_an_extra_arg_is_refused(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, _home_env(home)):
                for bad in ("ok\nbad", "ok\rbad", "ok\x00bad"):
                    with self.assertRaises(ValueError):
                        inst.install_linux("/opt/hp", "/c", False, [bad])

    def test_macos_agent_bootstraps_the_gui_domain(self):
        pkg = _Pkg()
        with tempfile.TemporaryDirectory() as home:
            # os.getuid does not exist on Windows; create=True lets
            # the launchd path run there too.
            with mock.patch.dict(os.environ, _home_env(home)), \
                    mock.patch.object(os, "getuid", create=True,
                                      return_value=501), \
                    mock.patch.object(inst, "run", pkg.run):
                inst.install_macos("/opt/hp", "/opt/hp/c.json",
                                   ["--quiet"])
                path = os.path.join(
                    home, "Library", "LaunchAgents",
                    "com.homing-pigeon.runner.plist")
                with open(path, encoding="utf-8") as fh:
                    plist = fh.read()
                inst.uninstall_macos()
            self.assertFalse(os.path.exists(path))
        self.assertIn("--quiet", plist)
        self.assertIn("com.homing-pigeon.runner", plist)
        self.assertIn("<key>RunAtLoad</key><true/>", plist)
        self.assertIn("<key>KeepAlive</key><true/>", plist)
        self.assertEqual(pkg.cmds[0][0], "launchctl")
        self.assertEqual(pkg.cmds[0][1], "bootstrap")
        self.assertEqual(pkg.cmds[1][1], "bootout")

    def test_freebsd_crontab_is_added_once_and_removed(self):
        state = {"listing": ""}

        def fake(cmd, **kw):
            class _P:
                returncode = 0
                stdout = state["listing"]

                def check_returncode(self):
                    return None
            if cmd == ["crontab", "-l"]:
                return _P()
            state["listing"] = kw.get("input") or ""
            return _P()

        with mock.patch.object(inst.subprocess, "run", fake):
            inst.install_freebsd(
                "/opt/homing-pigeon", "/opt/homing-pigeon/c.json",
                ["--quiet"])
            inst.install_freebsd(
                "/opt/homing-pigeon", "/opt/homing-pigeon/c.json")
            self.assertEqual(state["listing"].count("@reboot"), 1)
            self.assertTrue(state["listing"].startswith("@reboot "))
            self.assertIn("/opt/homing-pigeon/c.json", state["listing"])
            self.assertIn("--quiet", state["listing"])
            inst.uninstall_freebsd()
        self.assertNotIn("homing-pigeon", state["listing"])

    def test_windows_task_level_follows_the_account(self):
        pkg = _Pkg()
        with mock.patch.object(inst, "run", pkg.run):
            inst.install_windows(
                r"C:\hp", r"C:\hp\config.json", ["--quiet"], "pigeon")
            inst.install_windows(
                r"C:\hp", r"C:\hp\config.json", (), "SYSTEM")
            inst.install_windows(
                r"C:\hp", r"C:\hp\config.json", (),
                r"NT AUTHORITY\SYSTEM")
            inst.uninstall_windows()
        limited = pkg.cmds[0]
        self.assertEqual(limited[limited.index("/RL") + 1], "LIMITED")
        self.assertEqual(limited[limited.index("/RU") + 1], "pigeon")
        self.assertEqual(limited[limited.index("/SC") + 1], "ONSTART")
        self.assertEqual(limited[-1], "/F")
        self.assertEqual(
            pkg.cmds[1],
            ["schtasks", "/Run", "/TN", "HomingPigeon"])
        self.assertIn("--quiet", limited[limited.index("/TR") + 1])
        self.assertEqual(
            pkg.cmds[2][pkg.cmds[2].index("/RL") + 1], "HIGHEST")
        self.assertEqual(
            pkg.cmds[4][pkg.cmds[4].index("/RL") + 1], "HIGHEST")
        self.assertEqual(
            pkg.cmds[-1],
            ["schtasks", "/Delete", "/TN", "HomingPigeon", "/F"])


class FrozenEnvTest(unittest.TestCase):
    def test_a_frozen_tree_copies_the_binaries_and_seeds_config(self):
        if os.name == "nt":
            self.skipTest("frozen tree layout differs on Windows")
        with tempfile.TemporaryDirectory() as src, \
                tempfile.TemporaryDirectory() as dst:
            # The frozen names follow the host: homing-pigeon.exe
            # and install.exe on Windows.
            installer = "install.exe" if os.name == "nt" else "install"
            for name in (inst.RUNNER_BIN, installer,
                         "config.example.json"):
                with open(os.path.join(src, name), "w",
                          encoding="utf-8") as fh:
                    fh.write("{}\n")
            cfg = os.path.join(dst, "config.json")
            with mock.patch.object(inst, "FROZEN", True):
                self.assertTrue(inst.install_files(src, dst, cfg))
                self.assertTrue(os.path.isfile(
                    os.path.join(dst, inst.RUNNER_BIN)))
                self.assertTrue(os.path.isfile(cfg))
                self.assertFalse(inst.install_files(
                    os.path.join(src, "missing"), dst, cfg))


@unittest.skipIf(sys.platform == "win32", "POSIX installer path")
class LinuxPackageEnvTest(unittest.TestCase):
    def test_osquery_apt_env_writes_the_light_pack(self):
        pkg = _Pkg()
        with mock.patch.object(inst, "_apt_repo") as repo, \
                mock.patch.object(inst, "_apt_install") as apt, \
                mock.patch.object(inst, "_write_text", pkg.write_text), \
                mock.patch.object(inst, "run", pkg.run), \
                mock.patch.object(inst.os, "makedirs", pkg.makedirs):
            line = inst._install_osquery_linux()
        self.assertIn("light pack", line)
        self.assertIn("/var/log/osquery/osqueryd.results.log", line)
        apt.assert_called_once_with(["osquery"])
        repo.assert_called_once()
        self.assertIn("pkg.osquerypackages.com/deb deb main",
                      repo.call_args[0][1])
        self.assertIn(
            "https://pkg.osquerypackages.com/deb/pubkey.gpg",
            repo.call_args[0][2])
        self.assertIn("/etc/osquery/osquery.conf", pkg.files)
        self.assertIn(
            ["systemctl", "enable", "--now", "osqueryd.service"],
            pkg.cmds)
        with mock.patch.object(inst.shutil, "which", return_value=None):
            self.assertEqual(inst._osquery_binary(),
                             "/opt/osquery/bin/osqueryd")

    def test_falco_apt_env_routes_json_when_a_unit_exists(self):
        pkg = _Pkg()
        with mock.patch.object(inst, "_apt_repo") as repo, \
                mock.patch.object(inst, "_apt_install"), \
                mock.patch.object(inst, "_write_text", pkg.write_text), \
                mock.patch.object(inst, "run", pkg.run), \
                mock.patch.object(inst.os, "makedirs", pkg.makedirs), \
                mock.patch("glob.glob",
                           return_value=[
                               "/lib/systemd/system/falco.service"]):
            line = inst._install_falco_linux()
        self.assertIn("vendor apt repo", line)
        self.assertIn(inst.FALCO_ALERTS_LOG, line)
        self.assertIn("download.falco.org/packages/deb stable main",
                      repo.call_args[0][1])
        drop = os.path.join(
            "/etc/systemd/system/falco.service.d",
            "10-homing-pigeon.conf")
        text = pkg.files[drop][0]
        self.assertIn("ExecStart=\n", text)
        self.assertIn("json_output=true", text)
        self.assertIn("file_output.enabled=true", text)
        self.assertIn("file_output.filename=" + inst.FALCO_ALERTS_LOG, text)
        self.assertIn("stdout_output.enabled=false", text)

    def test_a_falco_drop_in_dir_is_not_the_unit(self):
        pkg = _Pkg()
        with mock.patch.object(inst, "_apt_repo"), \
                mock.patch.object(inst, "_apt_install"), \
                mock.patch.object(inst, "_write_text", pkg.write_text), \
                mock.patch.object(inst, "run", pkg.run), \
                mock.patch.object(inst.os, "makedirs", pkg.makedirs), \
                mock.patch("glob.glob", return_value=[
                    "/lib/systemd/system/falco.service.d"]):
            line = inst._install_falco_linux()
        self.assertNotIn("JSON alerts routed", line)
        self.assertEqual(pkg.files, {})

    def test_falco_falls_back_to_the_vendor_deb(self):
        pkg = _Pkg()

        def run(cmd, **_kw):
            pkg.cmds.append(list(cmd))
            if cmd[:2] == ["dpkg", "-i"] and pkg.cmds.count(list(cmd)) == 1:
                raise RuntimeError("deps")

        with mock.patch.object(
                inst, "_apt_repo", side_effect=RuntimeError("cdn")), \
                mock.patch.object(
                    inst, "_newest_from_listing",
                    return_value="https://example.test/"
                    "falco-0.1.0-x86_64.deb"), \
                mock.patch.object(inst, "_download", return_value=b"deb"), \
                mock.patch.object(inst, "run", run), \
                mock.patch.object(inst.os, "makedirs"), \
                mock.patch("glob.glob", return_value=[]):
            line = inst._install_falco_linux()
        self.assertIn("vendor .deb", line)
        self.assertIn(["apt-get", "install", "-f", "-y"], pkg.cmds)
        self.assertEqual(
            sum(1 for c in pkg.cmds if c[:2] == ["dpkg", "-i"]), 2)

    def test_the_apt_collectors_each_get_their_package(self):
        pkg = _Pkg()
        seen = {}

        def apt(packages):
            seen["apt"] = packages

        def repo(name, line, urls):
            seen["repo"] = (name, line, urls)

        replaced = []

        def replace(src, dst):
            replaced.append((src, dst))

        with mock.patch.object(inst, "_apt_install", apt), \
                mock.patch.object(inst, "_apt_repo", repo), \
                mock.patch.object(inst, "run", pkg.run), \
                mock.patch.object(inst, "_os_release_version",
                                  return_value="24.04"), \
                mock.patch.object(inst.os, "makedirs", pkg.makedirs), \
                mock.patch.object(inst, "_write_text", pkg.write_text), \
                mock.patch.object(inst.os.path, "isfile",
                                  return_value=True), \
                mock.patch.object(inst.os, "replace", replace):
            sur = inst._install_collector_linux("suricata", _args())
            zeek = inst._install_collector_linux("zeek", _args())
            self.assertEqual(seen["repo"][0], "zeek")
            self.assertIn("xUbuntu_24.04", seen["repo"][1])
            aide = inst._install_collector_linux("aide", _args())
            flow = inst._install_collector_linux("softflowd", _args())
        self.assertIn("/var/log/suricata/eve.json", sur)
        self.assertIn("/opt/zeek/bin/zeek", zeek)
        self.assertIn("daily check", aide)
        self.assertIn("127.0.0.1:2055", flow)
        self.assertEqual(
            pkg.files["/etc/cron.daily/homing-pigeon-aide"][1], 0o755)
        self.assertEqual(replaced[0][1], "/var/lib/aide/aide.db.gz")
        self.assertIn(
            ["systemctl", "enable", "--now", "suricata"], pkg.cmds)
        self.assertIn(["aide", "--init"], pkg.cmds)

    def test_sysmon_and_wazuh_use_their_vendor_packages(self):
        pkg = _Pkg()
        downloaded = []

        def download(url):
            downloaded.append(url)
            return b"deb"

        with mock.patch.object(inst, "_download", download), \
                mock.patch.object(inst, "_os_release_version",
                                  return_value="24.04"), \
                mock.patch.object(inst, "_apt_install") as apt, \
                mock.patch.object(inst, "_apt_repo") as repo, \
                mock.patch.object(inst, "run", pkg.run), \
                mock.patch.object(inst.subprocess, "run", pkg.run):
            sysmon = inst._install_collector_linux("sysmon", _args())
            wazuh = inst._install_collector_linux(
                "wazuh", _args(wazuh_manager="10.0.0.8"))
        self.assertIn("Microsoft", sysmon)
        self.assertIn("/config/ubuntu/24.04/", downloaded[0])
        self.assertIn(["apt-get", "update"], pkg.cmds)
        apt.assert_any_call(["sysmonforlinux"])
        self.assertIn("10.0.0.8", wazuh)
        self.assertIn("packages.wazuh.com/4.x/apt/",
                      repo.call_args[0][1])
        self.assertTrue(any(
            c[:4] == ["apt-get", "install", "-y", "wazuh-agent"]
            for c in pkg.cmds))

    def test_an_unknown_collector_is_named_and_not_installed(self):
        self.assertIn(
            "unknown",
            inst._install_collector_linux("not-a-collector", _args()))


class DarwinPackageEnvTest(unittest.TestCase):
    def test_osquery_brew_env_writes_the_pack_and_bootstraps(self):
        pkg = _Pkg()
        launched = []

        def which(name):
            return "/usr/local/bin/brew" if name == "brew" else None

        def isfile(path):
            return path.endswith("com.osquery.osqueryd.plist")

        def sub(cmd, **_kw):
            launched.append(list(cmd))

        with mock.patch.object(inst.shutil, "which", which), \
                mock.patch.object(inst, "run", pkg.run), \
                mock.patch.object(inst.os, "makedirs", pkg.makedirs), \
                mock.patch.object(inst, "_write_text", pkg.write_text), \
                mock.patch.object(inst.os.path, "isfile", isfile), \
                mock.patch.object(inst.subprocess, "run", sub):
            line = inst._install_collector_darwin("osquery", _args())
        self.assertIn("light pack", line)
        self.assertEqual(
            pkg.cmds[0][:3], ["brew", "install", "--cask"])
        self.assertIn("/var/osquery/osquery.conf", pkg.files)
        self.assertEqual(launched[0][0], "launchctl")
        self.assertEqual(launched[0][1], "bootout")
        self.assertEqual(launched[0][2], "system")

    def test_no_brew_and_no_channel_are_reported(self):
        with mock.patch.object(inst.shutil, "which", return_value=None):
            line = inst._install_collector_darwin("osquery", _args())
        self.assertIn("no Homebrew", line)
        line = inst._install_collector_darwin("sysmon", _args())
        self.assertIn("does not fetch", line)
        line = inst._install_collector_darwin("zeek", _args())
        self.assertIn("no first-class macOS", line)


class WindowsPackageEnvTest(unittest.TestCase):
    def test_osquery_winget_env_writes_beside_the_install(self):
        pkg = _Pkg()

        def which(name):
            return r"C:\winget.exe" if name == "winget" else None

        with mock.patch.object(inst.shutil, "which", which), \
                mock.patch.object(inst, "run", pkg.run), \
                mock.patch.object(inst.os.path, "isdir", return_value=True), \
                mock.patch.object(inst, "_write_text", pkg.write_text), \
                mock.patch.object(inst.subprocess, "run", pkg.run):
            line = inst._install_collector_windows("osquery", _args())
        self.assertIn("light pack", line)
        self.assertEqual(pkg.cmds[0][:4],
                         ["winget", "install", "--id", "osquery.osquery"])
        self.assertTrue(any(
            "Restart-Service osqueryd" in " ".join(c) for c in pkg.cmds))
        home = r"C:\Program Files\osquery"
        self.assertIn(os.path.join(home, "osquery.conf"), pkg.files)

    def test_no_winget_is_reported_and_sysmon_is_not_fetched(self):
        with mock.patch.object(inst.shutil, "which", return_value=None):
            line = inst._install_collector_windows("osquery", _args())
        self.assertIn("no winget", line)
        line = inst._install_collector_windows("sysmon", _args())
        self.assertIn("does not fetch", line)
        line = inst._install_collector_windows("zeek", _args())
        self.assertIn("no Windows install channel", line)

    def test_wazuh_msi_is_fetched_and_handed_to_msiexec(self):
        pkg = _Pkg()
        with mock.patch.object(
                inst, "_newest_from_listing",
                return_value="https://example.test/"
                "wazuh-agent-4.9.0-1.msi"), \
                mock.patch.object(inst, "_download",
                                  return_value=b"msi"), \
                mock.patch.object(inst, "run", pkg.run):
            line = inst._install_collector_windows(
                "wazuh", _args(wazuh_manager="10.0.0.8"))
        self.assertIn("10.0.0.8", line)
        self.assertEqual(pkg.cmds[0][0], "msiexec")
        self.assertEqual(pkg.cmds[0][3], "/q")
        self.assertIn("WAZUH_MANAGER=10.0.0.8", pkg.cmds[0])


class OtherPlatformTest(unittest.TestCase):
    def test_a_platform_without_a_channel_is_a_line(self):
        with mock.patch.object(inst.sys, "platform", "freebsd"):
            lines = inst.install_collectors(
                ["osquery"], _args(wazuh_manager=None))
        self.assertEqual(len(lines), 1)
        self.assertIn("no install channel", lines[0])

    def test_the_apt_key_and_release_version_are_read(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "keyring.gpg")
            with mock.patch.object(inst, "_download",
                                  return_value=b"not-armored"):
                got = inst._write_keyring(
                    ["https://example.test/a", "https://example.test/b"],
                    dest)
            self.assertEqual(got, dest)
            with open(dest, "rb") as fh:
                self.assertEqual(fh.read(), b"not-armored")
        with mock.patch("builtins.open", side_effect=OSError):
            self.assertEqual(inst._os_release_version(), "")


def _argv(*args):
    return mock.patch.object(sys, "argv", ["install.py", *args])


class MainDispatchTest(unittest.TestCase):
    def test_uninstall_follows_the_platform(self):
        cases = (
            ("linux", "uninstall_linux"),
            ("darwin", "uninstall_macos"),
            ("win32", "uninstall_windows"),
            ("freebsd14", "uninstall_freebsd"),
        )
        for plat, name in cases:
            with mock.patch.object(inst.sys, "platform", plat), \
                    mock.patch.object(inst, name) as fn, \
                    _argv("--uninstall"):
                self.assertEqual(inst.main(), 0)
            fn.assert_called()
        with mock.patch.object(inst.sys, "platform", "haiku"), \
                _argv("--uninstall"):
            self.assertEqual(inst.main(), 2)

    def test_wipe_and_migrate_return_the_helper(self):
        with mock.patch.object(inst, "do_wipe", return_value=3) as wipe, \
                _argv("--wipe", "--no-backup"):
            self.assertEqual(inst.main(), 3)
        wipe.assert_called()
        with mock.patch.object(inst, "do_migrate", return_value=4) as mig, \
                _argv("--migrate"):
            self.assertEqual(inst.main(), 4)
        mig.assert_called()

    def test_the_one_home_commands_refuse_on_linux(self):
        with _linux():
            for flag in ("--check", "--console", "--oracle"):
                with _argv(flag):
                    self.assertEqual(inst.main(), 2)
            with _argv("--follow"):
                self.assertEqual(inst.main(), 2)

    def test_windows_home_dispatches_each_command(self):
        with tempfile.TemporaryDirectory() as home:
            cfg = os.path.join(home, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            with mock.patch.object(inst.sys, "platform", "win32"):
                with mock.patch.object(inst, "do_check", return_value=0), \
                        _argv("--home", home, "--check"):
                    self.assertEqual(inst.main(), 0)
                with mock.patch.object(inst, "do_console", return_value=0), \
                        _argv("--home", home, "--console"):
                    self.assertEqual(inst.main(), 0)
                with mock.patch.object(inst, "do_logs", return_value=0), \
                        _argv("--home", home, "--logs"):
                    self.assertEqual(inst.main(), 0)
                with mock.patch.object(inst, "do_oracle", return_value=0), \
                        _argv("--home", home, "--oracle"):
                    self.assertEqual(inst.main(), 0)
                with _argv("--home", home, "--follow"):
                    self.assertEqual(inst.main(), 2)
                with mock.patch.object(
                        inst, "install_ollama_and_model",
                        return_value=True), \
                        _argv("--home", home, "--inference-only",
                              "--no-profile"):
                    self.assertEqual(inst.main(), 0)
                with mock.patch.object(
                        inst, "install_collectors",
                        return_value=["ok"]) as cols, \
                        _argv("--home", home, "--collector", "osquery"):
                    self.assertEqual(inst.main(), 0)
                cols.assert_called()
                with mock.patch.object(inst, "do_install_home",
                                       return_value=0) as home_install, \
                        _argv("--home", home):
                    self.assertEqual(inst.main(), 0)
                home_install.assert_called()

    def test_a_fresh_linux_install_bakes_the_flags(self):
        with tempfile.TemporaryDirectory() as dst:
            with _linux(), \
                    mock.patch.object(inst, "install_linux") as linux, \
                    mock.patch.object(
                        inst, "install_ollama_and_model",
                        return_value=True), \
                    _argv("--dir", dst, "--no-profile", "--no-collector",
                          "--quiet", "--poll-interval", "30",
                          "--workers", "2", "--dry-run", "--pdb",
                          "--no-send", "--timeout", "15",
                          "--max-output-bytes", "1000",
                          "--instructions", "be kind"):
                self.assertEqual(inst.main(), 0)
            extra = linux.call_args[0][3]
            for flag in ("--quiet", "--poll-interval", "30",
                         "--workers", "2", "--dry-run", "--pdb",
                         "--no-send", "--timeout", "15",
                         "--max-output-bytes", "1000"):
                self.assertIn(flag, extra)
            cfg = os.path.join(dst, "config.json")
            with open(cfg, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["owner_instructions"], "be kind")
            self.assertGreaterEqual(len(data["shared_secret"]), 64)

    def test_pi_light_installs_no_model_and_no_collector(self):
        with tempfile.TemporaryDirectory() as dst:
            with _linux(), \
                    mock.patch.object(inst, "install_linux"), \
                    mock.patch.object(
                        inst, "install_ollama_and_model") as ollama, \
                    _argv("--dir", dst, "--profile", "pi-light"):
                self.assertEqual(inst.main(), 0)
            ollama.assert_not_called()

    def test_an_existing_config_only_installs_the_named_collector(self):
        with tempfile.TemporaryDirectory() as dst:
            cfg = os.path.join(dst, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            with _linux(), \
                    mock.patch.object(inst, "install_collectors",
                                      return_value=["ok"]) as cols, \
                    _argv("--dir", dst, "--collector", "aide"):
                self.assertEqual(inst.main(), 0)
            cols.assert_called()

    def test_inference_only_reports_ready_or_not(self):
        with tempfile.TemporaryDirectory() as dst:
            with _linux(), \
                    mock.patch.object(
                        inst, "install_ollama_and_model",
                        return_value=False), \
                    _argv("--dir", dst, "--inference-only",
                          "--no-profile"):
                self.assertEqual(inst.main(), 0)
            with _linux(), \
                    _argv("--dir", dst, "--inference-only",
                          "--profile", "pi-light"):
                self.assertEqual(inst.main(), 0)

    def test_a_failed_copy_stops_the_install(self):
        with _linux(), \
                mock.patch.object(inst, "install_files", return_value=False), \
                _argv("--dir", "/tmp/does-not-matter-hp"):
            self.assertEqual(inst.main(), 1)

    def test_an_unknown_platform_copies_and_says_start_by_hand(self):
        with tempfile.TemporaryDirectory() as dst:
            with mock.patch.object(inst.sys, "platform", "haiku"), \
                    mock.patch.object(
                        inst, "install_ollama_and_model",
                        return_value=False), \
                    _argv("--dir", dst, "--no-inference",
                          "--no-profile", "--no-collector"):
                self.assertEqual(inst.main(), 0)


class SecretAndOllamaEnvTest(unittest.TestCase):
    def test_a_weak_or_patterned_secret_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write('{"shared_secret": "changeme"}\n')
            with self.assertRaises(SystemExit) as caught:
                inst.ensure_shared_secret(cfg, "abc" * 50)
            self.assertEqual(caught.exception.code, 2)
            with open(cfg, encoding="utf-8") as fh:
                before = fh.read()
            # Not a repeat and not a placeholder word, but under
            # 128 bits. The pattern check must not be what refuses it.
            with self.assertRaises(SystemExit) as caught:
                inst.ensure_shared_secret(cfg, "abcdefghij0123456789")
            self.assertEqual(caught.exception.code, 2)
            with self.assertRaises(SystemExit):
                inst.ensure_shared_secret(
                    cfg, "please-generate-a-real-secret-value-now")
            tail = "9f3a7c1e8b2d4f6a0c5e7b1d3"
            for word in ("example", "placeholder", "your-secret",
                         "your_secret", "todo", "xxx", "TODO"):
                with self.assertRaises(SystemExit):
                    inst.ensure_shared_secret(
                        cfg, f"owner-{word}-value-{tail}")
            with open(cfg, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), before)
            inst.ensure_shared_secret(cfg, None)
            with open(cfg, encoding="utf-8") as fh:
                first = json.load(fh)["shared_secret"]
            inst.ensure_shared_secret(cfg, None)
            with open(cfg, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["shared_secret"], first)
            with self.assertRaises(SystemExit):
                inst.store_additional_secret(cfg, "bad id")
            inst.store_additional_secret(cfg, "si.1")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write('{"additional_secrets": []}\n')
            with self.assertRaises(SystemExit):
                inst.store_additional_secret(cfg, "si.1")

    def test_instructions_replace_append_and_refuse_a_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            inst.set_instructions(cfg, "   ", False)
            self.assertFalse(os.path.exists(cfg))
            inst.set_instructions(cfg, "one", False)
            inst.set_instructions(cfg, "two", True)
            with open(cfg, encoding="utf-8") as fh:
                text = json.load(fh)["owner_instructions"]
            self.assertEqual(text, "one\n\ntwo")
            link = os.path.join(d, "link.json")
            os.symlink(cfg, link)
            with self.assertRaises(OSError):
                inst.set_instructions(link, "nope", False)

    def test_each_ollama_package_env(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            bins = iter([None, "/usr/bin/ollama"])
            with mock.patch.object(inst, "_ollama_bin",
                                   side_effect=lambda: next(bins)), \
                    mock.patch.object(inst, "run") as run, \
                    mock.patch.object(inst, "ensure_ollama_running",
                                      return_value=True), \
                    mock.patch.object(inst.sys, "platform", "linux"):
                self.assertTrue(inst.install_ollama_and_model(
                    cfg, "qwen3:1.7b", False))
            self.assertIn("curl", " ".join(run.call_args_list[0].args[0]))
            with open(cfg, encoding="utf-8") as fh:
                self.assertEqual(
                    json.load(fh)["inference"]["model"], "qwen3:1.7b")

            with mock.patch.object(inst, "_ollama_bin", return_value=None), \
                    mock.patch.object(inst, "_which", return_value=None), \
                    mock.patch.object(inst.sys, "platform", "darwin"):
                self.assertFalse(inst.install_ollama_and_model(
                    cfg, "m", False))
            seen = []

            def brew(cmd, **_k):
                seen.append(list(cmd))
                raise RuntimeError("brew")

            with mock.patch.object(inst, "_ollama_bin", return_value=None), \
                    mock.patch.object(inst, "_which",
                                      return_value="/usr/bin/brew"), \
                    mock.patch.object(inst, "run", brew), \
                    mock.patch.object(inst.sys, "platform", "darwin"):
                self.assertFalse(inst.install_ollama_and_model(
                    cfg, "m", False))
            self.assertEqual(seen, [["brew", "install", "ollama"]])
            with mock.patch.object(inst, "_ollama_bin", return_value=None), \
                    mock.patch.object(inst, "_which", return_value=None), \
                    mock.patch.object(inst.sys, "platform", "win32"):
                self.assertFalse(inst.install_ollama_and_model(
                    cfg, "m", False))
            with mock.patch.object(inst, "_ollama_bin", return_value=None), \
                    mock.patch.object(inst.sys, "platform", "haiku"):
                self.assertFalse(inst.install_ollama_and_model(
                    cfg, "m", False))

    def test_the_bpf_probe_answers_or_declines(self):
        answer = inst._bpf_loadable()
        self.assertIn(answer, (True, False, None))
        with mock.patch.object(inst.sys, "platform", "haiku"):
            self.assertIsNone(inst._bpf_loadable())

