"""Each install environment, with the package commands simulated.

No apt, no brew, no schtasks, no launchctl. The commands are
recorded. Files that would land in /etc are recorded too.
A user systemd unit and a launchd agent land in a fake home.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runner"))

import install as inst  # noqa: E402


def _args(**kw):
    return mock.Mock(**kw)


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
            with mock.patch.dict(os.environ, {"HOME": home}), \
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
        with self.assertRaises(ValueError):
            inst.install_linux("/opt/hp", "/c", False, ["ok\nbad"])

    def test_macos_agent_bootstraps_the_gui_domain(self):
        pkg = _Pkg()
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, {"HOME": home}), \
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
        with tempfile.TemporaryDirectory() as src, \
                tempfile.TemporaryDirectory() as dst:
            for name in ("homing-pigeon", "install",
                         "config.example.json"):
                with open(os.path.join(src, name), "w",
                          encoding="utf-8") as fh:
                    fh.write("{}\n")
            cfg = os.path.join(dst, "config.json")
            with mock.patch.object(inst, "FROZEN", True):
                self.assertTrue(inst.install_files(src, dst, cfg))
                self.assertTrue(os.path.isfile(
                    os.path.join(dst, "homing-pigeon")))
                self.assertTrue(os.path.isfile(cfg))
                self.assertFalse(inst.install_files(
                    os.path.join(src, "missing"), dst, cfg))


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
        apt.assert_called_once_with(["osquery"])
        repo.assert_called_once()
        self.assertIn("/etc/osquery/osquery.conf", pkg.files)
        self.assertIn(
            ["systemctl", "enable", "--now", "osqueryd.service"],
            pkg.cmds)

    def test_falco_apt_env_routes_json_when_a_unit_exists(self):
        pkg = _Pkg()
        with mock.patch.object(inst, "_apt_repo"), \
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
        drop = "/etc/systemd/system/falco.service.d/10-homing-pigeon.conf"
        self.assertIn("json_output=true", pkg.files[drop][0])

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

        with mock.patch.object(inst, "_apt_install", apt), \
                mock.patch.object(inst, "_apt_repo", repo), \
                mock.patch.object(inst, "run", pkg.run), \
                mock.patch.object(inst, "_os_release_version",
                                  return_value="24.04"), \
                mock.patch.object(inst.os, "makedirs", pkg.makedirs), \
                mock.patch.object(inst, "_write_text", pkg.write_text), \
                mock.patch.object(inst.os.path, "isfile",
                                  return_value=True), \
                mock.patch.object(inst.os, "replace"):
            sur = inst._install_collector_linux("suricata", _args())
            zeek = inst._install_collector_linux("zeek", _args())
            self.assertEqual(seen["repo"][0], "zeek")
            self.assertIn("xUbuntu_24.04", seen["repo"][1])
            aide = inst._install_collector_linux("aide", _args())
            flow = inst._install_collector_linux("softflowd", _args())
        self.assertIn("suricata", sur)
        self.assertIn("zeek", zeek)
        self.assertIn("aide", aide)
        self.assertIn("/etc/cron.daily/homing-pigeon-aide", pkg.files)
        self.assertIn("softflowd", flow)
        self.assertIn(
            ["systemctl", "enable", "--now", "suricata"], pkg.cmds)
        self.assertIn(["aide", "--init"], pkg.cmds)

    def test_sysmon_and_wazuh_use_their_vendor_packages(self):
        pkg = _Pkg()
        with mock.patch.object(inst, "_download", return_value=b"deb"), \
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
        apt.assert_any_call(["sysmonforlinux"])
        self.assertIn("10.0.0.8", wazuh)
        repo.assert_called()
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
        self.assertEqual(pkg.cmds[0][:3], ["winget", "install", "--id"])
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
