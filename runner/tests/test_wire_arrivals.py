"""Wire Arrivals: the example sense that files LAN neighbor events.

Pins the Wire Arrivals example (runner/extensions/wire-arrivals/)
the way test_sky_watcher.py pins Sky Watcher: the manifest through
the real extension loader, the baseline / new-neighbor / mac-moved
state machine across scripted neighbor tables (decide() is pure,
so every case is a fixture), the table parsers, and one end-to-end
run -- the producer learns a baseline quietly into the local inbox
path, then a fixture where one known IP moved to new hardware
files mac_moved through the real ingest, and the high signal
wakes the deterministic brief.

No live network and no live hardware anywhere: neighbor tables
are synthetic fixtures, and the end-to-end config has no
inference, so the wake brief is the deterministic fallback.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner import senses as S  # noqa: E402
from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "wire-arrivals")

DEFAULT_SECRET = "b109f3bbbc244eb82441917ed06d618b" + "9008dd09b3befd1b078a64781ac2f3e5"
WIRE_SECRET = "5c8e2a7f1b4d49a0e6c3f8b2d7a1e405" + "9f0b3c6d8e2a5f7b1c4d9e0a3f6b8c2d"

NOW = 1_700_000_000.0

MAC_A = "aa:bb:cc:dd:ee:01"
MAC_B = "aa:bb:cc:dd:ee:02"
MAC_C = "aa:bb:cc:dd:ee:03"


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "wire_arrivals_example",
        os.path.join(EXAMPLE_DIR, "wire_arrivals.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


WA = _load_example_module()


def _manifest(**tunables):
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    if tunables:
        manifest["tunables"] = dict(manifest["tunables"], **tunables)
    return manifest


def _neighbor(ip, mac, iface="eth0"):
    return {"ip": ip, "mac": mac, "iface": iface}


def _readings(*neighbors):
    return {"now": NOW, "neighbors": list(neighbors)}


def _run(neighbors, state=None, manifest=None):
    return WA.decide(_readings(*neighbors), manifest or _manifest(),
                     state if state is not None else {})


BASE_TABLE = [_neighbor("192.168.1.1", MAC_A),
              _neighbor("192.168.1.20", MAC_B)]


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "wire_arrivals")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["mac_moved", "new_neighbor"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "wire-arrivals"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("wire_arrivals", registry)
        self.assertEqual(registry["wire_arrivals"]["version"], "0.1.0")


class DecideTest(unittest.TestCase):
    def test_first_pass_learns_quietly(self):
        alerts, state = _run(BASE_TABLE)
        self.assertEqual(alerts, [])
        self.assertTrue(state["learned"])
        self.assertEqual(state["ips"], {"192.168.1.1": MAC_A,
                                        "192.168.1.20": MAC_B})
        self.assertEqual(state["macs"][MAC_A]["ips"], ["192.168.1.1"])

    def test_first_pass_files_when_learning_is_off(self):
        manifest = _manifest(learn_first_pass=False)
        alerts, state = _run(BASE_TABLE, manifest=manifest)
        self.assertEqual(
            [(a["signal"], a["severity"]) for a in alerts],
            [("new_neighbor", "medium"), ("new_neighbor", "medium")])
        self.assertTrue(state["learned"])

    def test_new_neighbor_after_baseline(self):
        _a, state = _run(BASE_TABLE)
        table = BASE_TABLE + [_neighbor("192.168.1.30", MAC_C, "wlan0")]
        alerts, state = _run(table, state=state)
        self.assertEqual([(a["signal"], a["severity"]) for a in alerts],
                         [("new_neighbor", "medium")])
        self.assertEqual(alerts[0]["sensor"], "wire_arrivals")
        self.assertEqual(alerts[0]["detail"],
                         {"ip": "192.168.1.30", "mac": MAC_C,
                          "iface": "wlan0"})
        # The same table again files nothing: state absorbed it.
        alerts, _s = _run(table, state=state)
        self.assertEqual(alerts, [])

    def test_mac_moved_files_only_the_stronger_tell(self):
        _a, state = _run(BASE_TABLE)
        moved = [_neighbor("192.168.1.1", MAC_C),
                 _neighbor("192.168.1.20", MAC_B)]
        alerts, state = _run(moved, state=state)
        self.assertEqual([(a["signal"], a["severity"]) for a in alerts],
                         [("mac_moved", "high")])
        self.assertEqual(alerts[0]["detail"],
                         {"ip": "192.168.1.1", "old_mac": MAC_A,
                          "new_mac": MAC_C, "iface": "eth0"})
        # The new MAC is absorbed even though it filed no
        # new_neighbor of its own.
        self.assertEqual(state["ips"]["192.168.1.1"], MAC_C)
        self.assertIn(MAC_C, state["macs"])
        self.assertEqual(state["macs"][MAC_C]["ips"], ["192.168.1.1"])
        # And the moved table, repeated, is quiet.
        alerts, state = _run(moved, state=state)
        self.assertEqual(alerts, [])
        # Moving back is a fresh move and files again.
        alerts, _s = _run(BASE_TABLE, state=state)
        self.assertEqual([a["signal"] for a in alerts], ["mac_moved"])
        self.assertEqual(alerts[0]["detail"]["old_mac"], MAC_C)
        self.assertEqual(alerts[0]["detail"]["new_mac"], MAC_A)

    def test_quiet_when_the_table_matches_state(self):
        _a, state = _run(BASE_TABLE)
        alerts, state = _run(list(BASE_TABLE), state=state)
        self.assertEqual(alerts, [])
        alerts, _s = _run(list(BASE_TABLE), state=state)
        self.assertEqual(alerts, [])

    def test_new_ip_under_a_known_mac_is_silent(self):
        _a, state = _run(BASE_TABLE)
        table = BASE_TABLE + [_neighbor("192.168.1.21", MAC_B)]
        alerts, state = _run(table, state=state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["ips"]["192.168.1.21"], MAC_B)
        self.assertEqual(state["macs"][MAC_B]["ips"],
                         ["192.168.1.20", "192.168.1.21"])

    def test_macs_are_normalized_lowercase(self):
        manifest = _manifest(learn_first_pass=False)
        alerts, state = _run([_neighbor("192.168.1.9", MAC_A.upper())],
                             manifest=manifest)
        self.assertEqual(alerts[0]["detail"]["mac"], MAC_A)
        self.assertIn(MAC_A, state["macs"])

    def test_bad_state_and_bad_records_are_cleaned(self):
        alerts, state = WA.decide(
            {"now": NOW, "neighbors": [{"ip": "10.0.0.1"}, "junk", {}]},
            _manifest(), {"learned": "yes", "macs": [], "ips": None})
        self.assertEqual(alerts, [])
        self.assertEqual(state["macs"], {})
        self.assertEqual(state["ips"], {})


class ParserTest(unittest.TestCase):
    def test_proc_net_arp_skips_header_and_zero_mac(self):
        text = (
            "IP address       HW type     Flags       HW address"
            "            Mask     Device\n"
            "192.168.1.1      0x1         0x2         AA:BB:CC:DD:EE:01"
            "     *        eth0\n"
            "192.168.1.99     0x1         0x0         00:00:00:00:00:00"
            "     *        eth0\n")
        self.assertEqual(WA._parse_proc_net_arp(text),
                         [{"ip": "192.168.1.1", "mac": MAC_A,
                           "iface": "eth0"}])

    def test_ip_neigh_shape(self):
        text = ("192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:01 REACHABLE\n"
                "192.168.1.50 dev eth0 FAILED\n")
        self.assertEqual(WA._parse_ip_neigh(text),
                         [{"ip": "192.168.1.1", "mac": MAC_A,
                           "iface": "eth0"}])

    def test_arp_a_shape(self):
        text = "? (192.168.1.1) at aa:bb:cc:dd:ee:01 [ether] on eth0\n"
        self.assertEqual(WA._parse_arp_a(text),
                         [{"ip": "192.168.1.1", "mac": MAC_A,
                           "iface": "eth0"}])


class WireFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(EXAMPLE_DIR,
                        os.path.join(self.ext_root, "wire-arrivals"))
        self.cfg = {
            "shared_secret": DEFAULT_SECRET,
            "additional_secrets": {"wire-key": WIRE_SECRET},
            "key_policies": {
                "wire-key": {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                "wire_arrivals": {"enabled": True, "key_id": "wire-key",
                                  "weight": 1.0, "profile": {}},
            },
            "extensions_dir": self.ext_root,
        }
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)
        self.state_path = os.path.join(self._tmp.name, "state.json")

    def tearDown(self):
        for th in threading.enumerate():
            if th.name == "oracle-brief":
                th.join(timeout=5)
        last = None
        for _ in range(20):
            try:
                self._tmp.cleanup()
                return
            except OSError as exc:
                last = exc
                time.sleep(0.05)
        if last is not None:
            raise last

    # -- helpers ------------------------------------------------------
    def readings_file(self, neighbors, name="readings.json"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(_readings(*neighbors), fh)
        return path

    def run_producer(self, neighbors, name="readings.json"):
        with unittest.mock.patch.dict(
                os.environ,
                {"HOMING_PIGEON_SENSOR_SECRET": WIRE_SECRET}):
            return WA.main(["--readings",
                            self.readings_file(neighbors, name),
                            "--local-dir", self.base,
                            "--key-id", "wire-key",
                            "--state", self.state_path])

    def inbox_names(self):
        inbox = os.path.join(self.base, "local-inbox")
        if not os.path.isdir(inbox):
            return []
        return sorted(os.listdir(inbox))

    def brief_lines(self):
        path = os.path.join(self.base, "oracle-briefs.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [ln for ln in fh.read().splitlines() if ln.strip()]

    def wait_briefs(self, n, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            lines = self.brief_lines()
            if len(lines) >= n:
                return lines
            time.sleep(0.05)
        self.fail(f"expected {n} brief(s), got {self.brief_lines()}")


class EndToEndTest(WireFixture):
    def test_moved_mac_files_and_wakes_a_brief(self):
        # Pass 1: the baseline fixture learns quietly.
        rc = self.run_producer(BASE_TABLE, name="baseline.json")
        self.assertEqual(rc, 0)
        self.assertEqual(self.inbox_names(), [])
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 0)
        self.assertEqual(S.load_alerts(self.base), [])
        with open(self.state_path, encoding="utf-8") as fh:
            self.assertTrue(json.load(fh)["learned"])

        # Pass 2: one known IP now answers from new hardware.
        moved = [_neighbor("192.168.1.1", MAC_C),
                 _neighbor("192.168.1.20", MAC_B)]
        rc = self.run_producer(moved, name="moved.json")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 1)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 1)
        self.assertEqual(self.inbox_names(), [])
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["sensor"], "wire_arrivals")
        self.assertEqual(rec["source"], "local")
        self.assertEqual(rec["extension"], "wire_arrivals")
        self.assertEqual(rec["extension_version"], "0.1.0")
        self.assertEqual(rec["signal"], "mac_moved")
        self.assertEqual(rec["severity"], "high")
        declared = {s["name"]: s["description"]
                    for s in _manifest()["signals"]}
        self.assertEqual(rec["signal_description"],
                         declared["mac_moved"])
        # The high signal wakes; with no inference configured
        # the brief is the deterministic fallback.
        lines = self.wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "mac_moved")
        self.assertEqual(brief["sensor"], "wire_arrivals")
        self.assertEqual(brief["status"], "no_inference")


if __name__ == "__main__":
    unittest.main()
