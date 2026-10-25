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
import unittest.mock
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from runner.ops import install as I


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

    def test_facts_that_are_not_a_dict_read_as_no_facts(self):
        # Queue A refill: host_decision's non-dict guard
        # (coverage run 40189711740: line 1652). A caller
        # handing back nothing usable gets the no-facts
        # decision, not a crash.
        decision = I.host_decision(None)
        self.assertEqual(decision, {"case": "other",
                                    "action": "run",
                                    "profile": None, "note": ""})

    def test_docker_with_an_accelerator_notes_both(self):
        # Queue A refill: the docker case's accelerator
        # suffix (line 1693): the note carries the Docker
        # explanation and the accelerator warning.
        decision = I.host_decision(facts(
            in_container=True, accelerators=["coral"]))
        self.assertEqual(decision["case"], "docker")
        self.assertIn("published Linux image", decision["note"])
        self.assertIn("coral", decision["note"])

    def test_arm_board_with_an_accelerator_notes_both(self):
        # Queue A refill: the display-candidate case's
        # accelerator suffix (line 1703).
        decision = I.host_decision(facts(
            machine="armv7l", device_model="Some Board",
            accelerators=["coral"]))
        self.assertEqual(decision["case"], "display-candidate")
        self.assertIn("display-board", decision["note"])
        self.assertIn("coral", decision["note"])

    def test_linux_with_an_accelerator_is_the_linux_case(self):
        # Queue A refill: the plain-Linux-with-accelerator
        # case (lines 1707-1708): the note is exactly the
        # accelerator warning -- the stick is not the
        # runner and will not be used.
        decision = I.host_decision(facts(accelerators=["coral"]))
        self.assertEqual(decision["case"], "linux")
        self.assertEqual(decision["profile"], "password-only")
        self.assertIn("A USB accelerator is attached (coral)",
                      decision["note"])
        self.assertIn("not the runner", decision["note"])

    def test_windows_and_mac_still_run(self):
        for plat in ("win32", "darwin", "freebsd14"):
            decision = I.host_decision(facts(platform=plat, machine="amd64"))
            self.assertEqual(decision["action"], "run", plat)
            self.assertEqual(decision["note"], "")

    def test_televisions_are_refused(self):
        for plat in ("tizen", "webos", "roku", "tvos"):
            decision = I.host_decision(facts(platform=plat))
            self.assertEqual(decision["action"], "refuse", plat)
            self.assertIn("shell", decision["note"])
            self.assertIn("display-board", decision["note"])
            self.assertNotIn("--ignore", decision["note"])

    def test_android_covers_the_tv_sticks(self):
        decision = I.host_decision(facts(platform="android"))
        for name in ("Android TV", "Google TV", "Fire TV", "Shield"):
            self.assertIn(name, decision["note"])

    def test_android_with_a_shell_is_warned_not_refused(self):
        # The owner's call (2026-10-21): the shell decides. A
        # sideloaded terminal environment on an Android set can run
        # a job, so the installer proceeds and states the limits.
        decision = I.host_decision(facts(platform="android",
                                         machine="aarch64"))
        self.assertEqual(decision["action"], "run")
        self.assertEqual(decision["case"], "android")
        self.assertEqual(decision["profile"], "display-board")
        for word in ("no service", "no model", "no sandbox",
                     "display-board", "shell"):
            self.assertIn(word, decision["note"], word)
        self.assertNotIn("will not install", decision["note"])

    def test_android_without_a_shell_is_still_refused(self):
        # A signed TV app with no exec is a television like any other.
        decision = I.host_decision(facts(platform="android",
                                         can_exec=False))
        self.assertEqual(decision["action"], "refuse")
        self.assertEqual(decision["case"], "no-exec")

    def test_android_warning_keeps_the_accelerator_note(self):
        decision = I.host_decision(facts(platform="android",
                                         accelerators=["coral"]))
        self.assertEqual(decision["action"], "run")
        self.assertIn("coral", decision["note"])
        self.assertIn("will not use it", decision["note"])

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

    def _gather(self, files, **kw):
        kw.setdefault("read_text",
                      lambda path: files.get(path, ""))
        kw.setdefault("exists",
                      lambda path: path in files
                      and bool(files[path]))
        kw.setdefault("platform_name", "linux")
        kw.setdefault("machine", "armv7l")
        kw.setdefault("environ", {})
        kw.setdefault("usb_ids", [])
        return I.gather_host_facts(**kw)

    def test_a_marker_file_names_the_platform(self):
        # Queue A refill: gather_host_facts' marker leg
        # (coverage run 40189711740: line 1841) -- a
        # /etc/webos-release file names the platform even
        # when os-release says nothing.
        facts = self._gather({"/etc/webos-release": "x"})
        self.assertEqual(facts["platform"], "webos")

    def test_an_os_release_webos_id_names_the_platform(self):
        # Queue A refill: the identity correction leg
        # (line 1845).
        facts = self._gather(
            {"/etc/os-release": 'NAME="webOS"\nID=webos\n'})
        self.assertEqual(facts["platform"], "webos")

    def test_an_android_environment_names_the_platform(self):
        # Queue A refill: the Android environment leg
        # (line 1848).
        facts = self._gather({}, environ={"ANDROID_ROOT": "/system"})
        self.assertEqual(facts["platform"], "android")

    def test_a_pi_identified_by_cpuinfo_only(self):
        # Queue A refill: the cpuinfo model leg (line
        # 1853) -- no device-tree model, but cpuinfo
        # names the Pi, and the decision follows.
        facts = self._gather({
            "/proc/device-tree/model": "",
            "/proc/cpuinfo": "Model: Raspberry Pi 4 Model B\n",
        })
        self.assertIn("Raspberry Pi", facts["device_model"])
        self.assertEqual(I.host_decision(facts)["case"], "pi")

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


class WarnPersonalDocumentsTest(unittest.TestCase):
    """Queue A refill: _warn_personal_documents'
    fallback (coverage run 40189711740: lines
    2929-2933). The function's own docstring: best
    effort, a missing module must not stop an install.
    When the package import fails it tries the bare
    sibling import, and when that fails too it
    swallows everything and returns.
    """

    def test_a_missing_module_is_swallowed(self):
        import builtins
        real = builtins.__import__

        def guarded(name, g=None, loc=None, fromlist=(), level=0):
            if "personal_docs" in name:
                raise ImportError("no personal_docs here")
            return real(name, g, loc, fromlist, level)

        with unittest.mock.patch("builtins.__import__", guarded):
            self.assertIsNone(I._warn_personal_documents())


class UsbAcceleratorsTest(unittest.TestCase):
    """Queue A refill: _usb_accelerators' probe legs
    (coverage run 40187685363: 6 lines on both
    platforms -- CI machines have no accelerator
    plugged in, so the scan never looped). The scan
    is total: an unlistable sysfs answers none, a
    known vendor id names its kind once, an unknown
    id is not an accelerator.
    """

    def test_an_unlistable_sysfs_answers_none(self):
        with unittest.mock.patch.object(
                os, "listdir", side_effect=OSError("no sysfs")):
            self.assertEqual(I._usb_accelerators(), [])

    def test_known_vendors_name_their_kind_once(self):
        vendors = {"usb1": "18d1\n", "1-2": "03e7",
                   "3-1": "1a6e", "4-1": "ffff"}

        def fake_listdir(path):
            self.assertEqual(path, "/sys/bus/usb/devices")
            return sorted(vendors)

        def fake_read(path):
            name = path.split(os.sep)[-2]
            return vendors[name]

        with unittest.mock.patch.object(
                os, "listdir", fake_listdir), \
                unittest.mock.patch.object(
                I, "_read_text", fake_read):
            self.assertEqual(I._usb_accelerators(),
                             ["ncs", "coral"])


if __name__ == "__main__":
    unittest.main()
