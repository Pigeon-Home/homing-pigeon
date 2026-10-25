"""USB Arrivals: the example sense that files bus arrivals.

Pins the USB Arrivals example (runner/extensions/usb-arrivals/)
the way test_sky_watcher.py pins Sky Watcher: the manifest
through the real extension loader, the learn/arrive state
machine in decide() against table-driven fixtures, and the
producer's print path. No live hardware anywhere: every
reading is a fixture dict, and read_live is exercised only
for its shape and for a mocked sys.platform.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "usb-arrivals")

NOW = 1792375113.0

KEYBOARD = {"id": "046d:c31c", "kind": "usb",
            "description": "USB Keyboard", "device_class": "03"}
STICK = {"id": "0781:5567", "kind": "usb",
         "description": "Cruzer Blade", "device_class": "08"}
SERIAL_CABLE = {"id": "usb-FTDI_FT232R-if00-port0", "kind": "serial",
                "description": "usb-FTDI_FT232R-if00-port0",
                "device_class": "serial"}


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "usb_arrivals_example", os.path.join(EXAMPLE_DIR, "usb_arrivals.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


UA = _load_example_module()


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _readings(*devices):
    return {"now": NOW, "devices": [dict(d) for d in devices]}


def _learn(*devices, manifest=None):
    _alerts, state = UA.decide(_readings(*devices),
                               manifest or _manifest(), {})
    return state


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "usb_arrivals")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["device_arrived", "storage_arrived"])
        self.assertEqual(clean["tunables"]["poll_interval_sec"], 300)
        self.assertIs(clean["tunables"]["learn_first_pass"], True)
        self.assertEqual(clean["tunables"]["kinds"], ["usb", "serial"])

    def test_loads_via_load_extensions_from_a_copied_tree(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "usb-arrivals"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("usb_arrivals", registry)
        self.assertEqual(registry["usb_arrivals"]["version"], "0.1.0")


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.manifest = _manifest()

    def test_learn_pass_absorbs_quietly(self):
        alerts, state = UA.decide(_readings(KEYBOARD, STICK),
                                  self.manifest, {})
        self.assertEqual(alerts, [])
        self.assertTrue(state["learned"])
        self.assertEqual(sorted(state["seen"]),
                         ["046d:c31c", "0781:5567"])

    def test_quiet_case_files_nothing(self):
        state = _learn(KEYBOARD)
        alerts, _state = UA.decide(_readings(KEYBOARD),
                                   self.manifest, state)
        self.assertEqual(alerts, [])
        alerts, _state = UA.decide(_readings(), self.manifest, state)
        self.assertEqual(alerts, [])
        alerts, _state = UA.decide({}, self.manifest, state)
        self.assertEqual(alerts, [])
        alerts, _state = UA.decide(None, self.manifest, {})
        # An unlearned empty first pass still only learns.
        self.assertEqual(alerts, [])

    def test_device_arrived_is_info_with_key_details(self):
        state = _learn(KEYBOARD)
        alerts, _state = UA.decide(_readings(KEYBOARD, SERIAL_CABLE),
                                   self.manifest, state)
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "usb_arrivals")
        self.assertEqual(alert["signal"], "device_arrived")
        self.assertEqual(alert["severity"], "info")
        self.assertEqual(alert["detail"]["id"], SERIAL_CABLE["id"])
        self.assertEqual(alert["detail"]["kind"], "serial")
        self.assertEqual(alert["detail"]["description"],
                         SERIAL_CABLE["description"])

    def test_storage_arrived_is_medium_and_replaces_device_arrived(self):
        state = _learn(KEYBOARD)
        alerts, _state = UA.decide(_readings(KEYBOARD, STICK),
                                   self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["storage_arrived"])
        alert = alerts[0]
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"]["id"], "0781:5567")
        self.assertEqual(alert["detail"]["kind"], "usb")
        self.assertEqual(alert["detail"]["description"], "Cruzer Blade")
        self.assertEqual(alert["detail"]["device_class"], "08")

    def test_every_signal_fires_table_driven(self):
        cases = [
            (KEYBOARD, "device_arrived", "info"),
            (STICK, "storage_arrived", "medium"),
            (SERIAL_CABLE, "device_arrived", "info"),
        ]
        for device, signal, severity in cases:
            with self.subTest(device=device["id"]):
                state = _learn()
                alerts, _s = UA.decide(_readings(device),
                                       self.manifest, state)
                self.assertEqual([a["signal"] for a in alerts], [signal])
                self.assertEqual(alerts[0]["severity"], severity)
                self.assertEqual(alerts[0]["detail"]["id"], device["id"])

    def test_same_readings_twice_files_nothing_second_time(self):
        state = _learn(KEYBOARD)
        alerts, state = UA.decide(_readings(KEYBOARD, STICK),
                                  self.manifest, state)
        self.assertEqual(len(alerts), 1)
        alerts, state = UA.decide(_readings(KEYBOARD, STICK),
                                  self.manifest, state)
        self.assertEqual(alerts, [])

    def test_departure_is_silent_and_return_refiles(self):
        # The "moved reading" for a bus sense: a device leaves
        # (silently) and comes back -- the return is news again.
        state = _learn(KEYBOARD)
        alerts, state = UA.decide(_readings(KEYBOARD, STICK),
                                  self.manifest, state)
        self.assertEqual(len(alerts), 1)
        alerts, state = UA.decide(_readings(KEYBOARD),
                                  self.manifest, state)
        self.assertEqual(alerts, [])  # departure: no signal at all
        self.assertNotIn("0781:5567", state["seen"])
        alerts, state = UA.decide(_readings(KEYBOARD, STICK),
                                  self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["storage_arrived"])

    def test_learn_first_pass_false_files_the_first_pass(self):
        manifest = _manifest()
        manifest["tunables"] = dict(manifest["tunables"],
                                    learn_first_pass=False)
        alerts, state = UA.decide(_readings(KEYBOARD), manifest, {})
        self.assertEqual([a["signal"] for a in alerts],
                         ["device_arrived"])
        self.assertTrue(state["learned"])

    def test_duplicate_ids_in_one_pass_file_once(self):
        state = _learn(KEYBOARD)
        alerts, _s = UA.decide(_readings(KEYBOARD, STICK, STICK),
                               self.manifest, state)
        self.assertEqual(len(alerts), 1)

    def test_bad_state_and_bad_devices_never_raise(self):
        alerts, state = UA.decide(
            {"now": NOW, "devices": [None, "x", {"kind": "usb"},
                                     {"id": 7}]},
            self.manifest, {"learned": "yes", "seen": []})
        self.assertEqual(alerts, [])
        self.assertTrue(state["learned"])
        alerts, _s = UA.decide(_readings(KEYBOARD), self.manifest,
                               "not a dict")
        self.assertEqual(alerts, [])  # treated as a fresh learn pass

    def test_read_live_shape_and_non_linux_quiet(self):
        with unittest.mock.patch.object(UA.sys, "platform", "win32"):
            readings = UA.read_live(self.manifest)
        self.assertEqual(readings["devices"], [])
        self.assertIn("now", readings)
        # On any platform the live read answers the shape and
        # never raises; entries, when present, carry the fields.
        readings = UA.read_live(self.manifest)
        self.assertIsInstance(readings["devices"], list)
        for dev in readings["devices"]:
            self.assertEqual(sorted(dev),
                             ["description", "device_class", "id", "kind"])


class ProducerTest(unittest.TestCase):
    def test_print_path_and_state_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            readings_path = os.path.join(d, "readings.json")
            with open(readings_path, "w", encoding="utf-8") as fh:
                json.dump(_readings(KEYBOARD), fh)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = UA.main(["--readings", readings_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")  # learn pass
            with open(readings_path, "w", encoding="utf-8") as fh:
                json.dump(_readings(KEYBOARD, STICK), fh)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = UA.main(["--readings", readings_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["storage_arrived"])

    def test_unreadable_readings_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            rc = UA.main(["--readings", os.path.join(d, "nope.json"),
                          "--state", os.path.join(d, "state.json")])
        self.assertEqual(rc, 2)


class TwinDevicesLegTest(unittest.TestCase):
    """Queue A refill: _read_usb_devices' twin
    collapse (coverage run 40189711740: lines
    120-123). Two physical devices with the
    same vendor and product are one entry at
    this level -- the sense says so in its
    docstring, and the second sighting is
    passed over, not appended.
    """

    def test_identical_twins_are_one_entry(self):
        import glob as glob_mod
        import os
        import tempfile
        from unittest import mock as _mock
        with tempfile.TemporaryDirectory() as d:
            dirs = []
            for name in ("1-1", "1-2"):
                dev = os.path.join(d, name)
                os.makedirs(dev)
                for fname, value in (
                        ("idVendor", "046d"),
                        ("idProduct", "c52b"),
                        ("product", "Receiver"),
                        ("manufacturer", "Logitech")):
                    with open(os.path.join(dev, fname),
                              "w") as fh:
                        fh.write(value + "\n")
                dirs.append(dev + "/")
            with _mock.patch.object(
                    glob_mod, "glob", return_value=dirs):
                devices = UA._read_usb_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["id"], "046d:c52b")


if __name__ == "__main__":
    unittest.main()
