"""Every hardware case the installer will meet.

The CI proofs (Pi Light archive, Alpine with no bash, the
published Docker image) are Linux. These tests simulate the
other machines. A television is refused. A USB accelerator is
not a computer. A Linux board behind a screen is a normal
install, and display-board is the dedicated form of it.
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runner import install as I


def facts(**kw):
    base = {
        "platform": "linux",
        "machine": "x86_64",
        "device_model": "",
        "in_container": False,
        "accelerators": [],
        "can_exec": True,
    }
    base.update(kw)
    return base


class HostDecisionTests(unittest.TestCase):
    def test_pi_runs_pi_light(self):
        decision = I.host_decision(facts(
            machine="aarch64", device_model="Raspberry Pi 5"))
        self.assertEqual(decision["action"], "run")
        self.assertEqual(decision["case"], "pi")
        self.assertEqual(decision["profile"], "pi-light")
        self.assertEqual(decision["note"], "")

    def test_pi_with_an_accelerator_still_installs_no_model(self):
        decision = I.host_decision(facts(
            machine="aarch64", device_model="Raspberry Pi 4",
            accelerators=["coral"]))
        self.assertEqual(decision["action"], "run")
        self.assertEqual(decision["profile"], "pi-light")
        self.assertIn("coral", decision["note"])
        self.assertIn("not the runner", decision["note"])
        self.assertIn("no model", decision["note"])

    def test_ordinary_linux_is_unchanged(self):
        decision = I.host_decision(facts())
        self.assertEqual(decision["action"], "run")
        self.assertEqual(decision["profile"], "password-only")
        self.assertEqual(decision["note"], "")

    def test_docker_is_linux_packaged(self):
        decision = I.host_decision(facts(in_container=True))
        self.assertEqual(decision["action"], "run")
        self.assertEqual(decision["case"], "docker")
        self.assertEqual(decision["profile"], "password-only")
        self.assertIn("published Linux image", decision["note"])
        self.assertIn("minimal-userland", decision["note"])

    def test_arm_board_behind_a_screen_is_linux(self):
        decision = I.host_decision(facts(
            machine="aarch64", device_model="Radxa ROCK 5"))
        self.assertEqual(decision["action"], "run")
        self.assertEqual(decision["case"], "display-candidate")
        self.assertEqual(decision["profile"], "password-only")
        self.assertIn("display-board", decision["note"])
        self.assertIn("not a television", decision["note"])

    def test_windows_and_mac_still_run(self):
        for plat in ("win32", "darwin", "freebsd14"):
            decision = I.host_decision(facts(platform=plat, machine="amd64"))
            self.assertEqual(decision["action"], "run", plat)
            self.assertEqual(decision["note"], "")

    def test_televisions_are_refused(self):
        for plat in ("tizen", "webos", "roku", "tvos", "android"):
            decision = I.host_decision(facts(platform=plat))
            self.assertEqual(decision["action"], "refuse", plat)
            self.assertIn("shell", decision["note"])
            self.assertIn("display-board", decision["note"])
            self.assertNotIn("--ignore", decision["note"])

    def test_android_covers_the_tv_sticks(self):
        decision = I.host_decision(facts(platform="android"))
        for name in ("Android TV", "Google TV", "Fire TV", "Shield"):
            self.assertIn(name, decision["note"])

    def test_an_accelerator_alone_is_refused(self):
        decision = I.host_decision(facts(
            platform="usb", accelerators=["ncs", "hailo"]))
        self.assertEqual(decision["action"], "refuse")
        self.assertEqual(decision["case"], "accelerator")
        self.assertIn("not a computer", decision["note"])
        self.assertIn("ncs", decision["note"])

    def test_a_sandbox_that_cannot_exec_is_refused(self):
        decision = I.host_decision(facts(can_exec=False))
        self.assertEqual(decision["action"], "refuse")
        self.assertEqual(decision["case"], "no-exec")
        self.assertIn("display-board", decision["note"])

    def test_television_plus_accelerator_is_still_a_television(self):
        decision = I.host_decision(facts(
            platform="tizen", accelerators=["coral"]))
        self.assertEqual(decision["case"], "tizen")
        self.assertEqual(decision["action"], "refuse")
        self.assertIn("coral", decision["note"])


class DisplayBoardProfileTests(unittest.TestCase):
    def test_display_board_installs_no_model(self):
        spec = I.BUILTIN_PROFILES["display-board"]
        self.assertEqual(spec["oracle_mode"], "deterministic")
        self.assertEqual(I.profile_oracle_mode("display-board"),
                         "deterministic")
        self.assertTrue(I._pi_light_skip(
            type("A", (), {"inference_model": None, "faster": False})(),
            "display-board"))


class GatherAndGateTests(unittest.TestCase):
    def test_os_release_and_a_usb_id_simulate_a_tizen_set(self):
        files = {
            "/etc/os-release": 'NAME="Tizen"\nID=tizen\n',
            "/proc/device-tree/model": "",
            "/proc/cpuinfo": "",
            "/proc/1/cgroup": "",
        }
        facts = I.gather_host_facts(
            read_text=lambda path: files.get(path, ""),
            exists=lambda path: path in files and bool(files[path]),
            platform_name="linux",
            machine="armv7l",
            environ={},
            usb_ids=["1a6e"],
        )
        self.assertEqual(facts["platform"], "tizen")
        self.assertEqual(facts["accelerators"], ["coral"])
        decision = I.host_decision(facts)
        self.assertEqual(decision["action"], "refuse")

    def test_gate_stops_a_television_and_stays_quiet_on_linux(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = I.host_install_gate(facts(platform="webos"))
        self.assertEqual(code, 2)
        self.assertIn("webOS", buf.getvalue())
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = I.host_install_gate(facts())
        self.assertIsNone(code)
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
