"""The macOS install finishes whether or not launchd will load the
agent now (docs/seats/questions.md Q39).

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

`launchctl bootstrap gui/<uid>` needs a logged-in GUI session. Over
SSH, in CI, on a headless Mac it exits 5, and over an agent that is
already loaded (an upgrade) it refuses. The agent file is in place
either way and loads at the user's next login, so the install is
complete: an upgrade over a loaded agent restarts it with kickstart,
anything else prints the command to run from a logged-in session.
No launchctl is run here; the commands are captured.
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runner"))

from ops import install as inst  # noqa: E402


class _Done:
    def __init__(self, rc):
        self.returncode = rc


def _bootstrap_fails(cmd, **kw):
    raise subprocess.CalledProcessError(5, cmd)


class LaunchdLoadTest(unittest.TestCase):
    def _load(self, bootstrap, kickstart_rc):
        ran = []

        def fake_run(cmd, **kw):
            ran.append(list(cmd))
            return bootstrap(cmd, **kw)

        def fake_sub(cmd, **kw):
            ran.append(list(cmd))
            if kickstart_rc is None:
                raise OSError("no launchctl")
            return _Done(kickstart_rc)

        out = io.StringIO()
        with mock.patch.object(inst, "run", fake_run), \
                mock.patch.object(inst.subprocess, "run", fake_sub), \
                redirect_stdout(out):
            loaded = inst._launchd_load(501, "/Users/x/Library/LaunchAgents/p.plist")
        return loaded, ran, out.getvalue()

    def test_a_gui_session_loads_it_and_stops_there(self):
        loaded, ran, out = self._load(lambda cmd, **kw: None, 0)
        self.assertTrue(loaded)
        self.assertEqual(ran, [["launchctl", "bootstrap", "gui/501",
                                "/Users/x/Library/LaunchAgents/p.plist"]])
        self.assertNotIn("warning", out)

    def test_an_upgrade_over_a_loaded_agent_restarts_it(self):
        loaded, ran, out = self._load(_bootstrap_fails, 0)
        self.assertTrue(loaded)
        self.assertEqual(ran[1], ["launchctl", "kickstart", "-k",
                                  "gui/501/com.homing-pigeon.runner"])
        self.assertIn("restarted it on the new install", out)
        self.assertNotIn("warning", out)

    def test_a_headless_session_installs_and_says_how_to_load(self):
        loaded, ran, out = self._load(_bootstrap_fails, 113)
        self.assertFalse(loaded)
        self.assertIn("warning: launchctl bootstrap did not load the agent now",
                      out)
        self.assertIn("loads at this user's next login", out)
        self.assertIn("launchctl bootstrap gui/501 "
                      "/Users/x/Library/LaunchAgents/p.plist", out)

    def test_no_launchctl_at_all_is_the_same_warning(self):
        loaded, ran, out = self._load(_bootstrap_fails, None)
        self.assertFalse(loaded)
        self.assertIn("warning:", out)


class InstallMacosTest(unittest.TestCase):
    def test_the_install_completes_with_the_agent_file_in_place(self):
        home = tempfile.mkdtemp(prefix="hp-macos-")
        out = io.StringIO()
        # expanduser reads HOME on POSIX and USERPROFILE on Windows.
        with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}), \
                mock.patch.object(inst, "_posix_uid", return_value=501), \
                mock.patch.object(inst, "run", _bootstrap_fails), \
                mock.patch.object(inst.subprocess, "run",
                                  lambda cmd, **kw: _Done(113)), \
                redirect_stdout(out):
            inst.install_macos("/opt/hp", "/opt/hp/config.json", ("--x",))
        plist = os.path.join(home, "Library", "LaunchAgents",
                             "com.homing-pigeon.runner.plist")
        self.assertTrue(os.path.isfile(plist))
        with open(plist, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("<string>/opt/hp/config.json</string>", text)
        self.assertIn("<string>--x</string>", text)
        self.assertIn("installed: launchd agent at", out.getvalue())
        self.assertIn("(not loaded yet)", out.getvalue())

    def test_a_loaded_agent_reports_loaded(self):
        home = tempfile.mkdtemp(prefix="hp-macos-")
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}), \
                mock.patch.object(inst, "_posix_uid", return_value=501), \
                mock.patch.object(inst, "run", lambda cmd, **kw: None), \
                redirect_stdout(out):
            inst.install_macos("/opt/hp", "/opt/hp/config.json")
        self.assertIn("installed: launchd agent at", out.getvalue())
        self.assertNotIn("not loaded", out.getvalue())


if __name__ == "__main__":
    unittest.main()
