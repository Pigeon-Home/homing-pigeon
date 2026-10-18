"""macOS platform code: the launchd agent and the application firewall.

Unit cases, one-field mutations, and a deterministic fuzz. launchctl
and socketfilterfw are mocked. Nothing here bootstraps an agent.
"""
import os
import plistlib
import random
import tempfile
import unittest
from unittest import mock

from runner.install import do_wipe, install_macos, uninstall_macos
from runner.runner import _firewall_posture, _parse_socketfilterfw


@unittest.skipIf(os.name == "nt",
                 "launchd tests patch os.getuid, which Windows lacks")
class LaunchdTest(unittest.TestCase):
    def test_the_agent_plist_and_the_bootout_use_the_same_name(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "home")
            agents = os.path.join(home, "Library", "LaunchAgents")
            dst = os.path.join(d, "a&b")
            os.makedirs(dst)
            calls = []

            def expand(path):
                return path.replace("~", home, 1)

            with mock.patch("runner.install.run", side_effect=lambda cmd, **k: calls.append(cmd)), \
                 mock.patch("runner.install.os.getuid", return_value=501), \
                 mock.patch("runner.install.os.path.expanduser", side_effect=expand):
                install_macos(dst, os.path.join(dst, "config.json"), ("--dry-run",))
            path = os.path.join(agents, "com.homing-pigeon.runner.plist")
            with open(path, "rb") as fh:
                pl = plistlib.load(fh)
            self.assertEqual(pl["Label"], "com.homing-pigeon.runner")
            self.assertIs(pl["RunAtLoad"], True)
            self.assertIs(pl["KeepAlive"], True)
            args = pl["ProgramArguments"]
            self.assertEqual(args[args.index("--config") + 1],
                             os.path.join(dst, "config.json"))
            self.assertEqual(args[-1], "--dry-run")
            self.assertEqual(pl["StandardOutPath"], os.path.join(dst, "runner.log"))
            self.assertEqual(calls, [["launchctl", "bootstrap", "gui/501", path]])

            calls.clear()
            with mock.patch("runner.install.run", side_effect=lambda cmd, **k: calls.append(cmd)), \
                 mock.patch("runner.install.os.getuid", return_value=501), \
                 mock.patch("runner.install.os.path.expanduser", side_effect=expand):
                uninstall_macos()
            self.assertEqual(calls, [["launchctl", "bootout", "gui/501", path]])
            self.assertFalse(os.path.exists(path))
            with mock.patch("runner.install.run", side_effect=lambda cmd, **k: calls.append(cmd)), \
                 mock.patch("runner.install.os.getuid", return_value=501), \
                 mock.patch("runner.install.os.path.expanduser", side_effect=expand):
                uninstall_macos()

    def test_wipe_unloads_the_installed_plist(self):
        calls = []
        with mock.patch("runner.install.sys.platform", "darwin"), \
             mock.patch("runner.install._kill_runner_processes"), \
             mock.patch("runner.install._candidate_state_dirs", return_value=[]), \
             mock.patch("runner.install._run_quiet", side_effect=calls.append), \
             mock.patch("runner.install.os.getuid", return_value=501):
            self.assertEqual(do_wipe(no_backup=True), 0)
        self.assertEqual(len(calls), 1)
        argv = calls[0]
        self.assertEqual(argv[:3], ["launchctl", "bootout", "gui/501"])
        self.assertTrue(argv[3].endswith("com.homing-pigeon.runner.plist"))
        self.assertFalse(argv[3].endswith("/homing-pigeon.plist"))


class FirewallParseTest(unittest.TestCase):
    def test_state_mutations(self):
        off = _parse_socketfilterfw("Firewall is disabled. (State = 0)")
        on = _parse_socketfilterfw("Firewall is enabled. (State = 1)")
        self.assertIn("=off", off)
        self.assertIn("[T1562.004]", off)
        self.assertIn("=on", on)
        self.assertNotIn("T1562", on)
        self.assertIn("=off", _parse_socketfilterfw("enabled, but State = 0"))
        self.assertIsNone(_parse_socketfilterfw("State = 10"))
        self.assertIsNone(_parse_socketfilterfw("State = 12"))
        self.assertIn("=on", _parse_socketfilterfw("STATE = 1"))
        self.assertIsNone(_parse_socketfilterfw(""))
        self.assertIsNone(_parse_socketfilterfw(None))
        self.assertIsNone(_parse_socketfilterfw(b"enabled"))

    def test_darwin_reads_socketfilterfw_and_not_pfctl(self):
        seen = []

        def fake_run(argv, timeout=5):
            seen.append(argv)
            return "Firewall is disabled. (State = 0)"

        with mock.patch("runner.runner.sys.platform", "darwin"), \
             mock.patch("runner.runner._run_text", side_effect=fake_run):
            line = _firewall_posture()
        self.assertEqual(seen, [[
            "/usr/libexec/ApplicationFirewall/socketfilterfw",
            "--getglobalstate"]])
        self.assertIn("=off", line)
        self.assertNotIn("pfctl", str(seen))


class FirewallParseFuzzTest(unittest.TestCase):
    def test_random_text_is_on_off_or_unreadable(self):
        rng = random.Random(20261017)
        known = {
            None,
            "firewall: macos application-firewall=off [T1562.004]",
            "firewall: macos application-firewall=on",
        }
        crashes = []
        samples = [
            "State = 0", "State = 1", "State = 10", "State = 12",
            "enabled", "disabled", "ENABLED", "", None, b"on",
        ]
        for _ in range(200):
            text = rng.choice(samples)
            if rng.randrange(2) == 0:
                text = "".join(chr(rng.randrange(32, 127))
                               for _ in range(rng.randrange(0, 40)))
            try:
                got = _parse_socketfilterfw(text)
            except Exception as exc:
                crashes.append(type(exc).__name__)
                break
            if got not in known:
                crashes.append(got)
                break
            if text == "State = 10" and got is not None:
                crashes.append(got)
                break
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
