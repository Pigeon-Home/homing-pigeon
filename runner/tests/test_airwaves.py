"""Airwaves: the example sense that watches the Wi-Fi neighborhood.

Pins the Airwaves example (runner/extensions/airwaves/) the
way test_sky_watcher.py pins Sky Watcher: the manifest through
the real extension loader, the pure parsers (nmcli's escaped
colons and percentage signal, iw link/scan text, the security
ranking), the neighborhood state machine in decide() against
table-driven fixtures, and one end-to-end run -- producer
replays a baseline then an evil-twin pass into the local
inbox, the real ingest files it, and the high-severity
evil_twin_suspect wakes the gate and files a brief.

No live network and no live hardware anywhere: tests never
actually scan Wi-Fi -- every neighborhood is a fixture dict
or a recorded tool-output string, and subprocess is mocked
where read_live's source selection is exercised.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner.oracle import senses as S  # noqa: E402
from runner.ops import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "airwaves")

DEFAULT_SECRET = "b109f3bbbc244eb82441917ed06d618b" + "9008dd09b3befd1b078a64781ac2f3e5"
AIR_SECRET = "9d4c2b8a6f1e40d3a5b7c9e2f4a6b8d0" + "1c3e5f7a9b2d4f6a8c0e2f4a6b8d0c2e"

NOW = 1792375113.0

HOME = {"bssid": "AA:BB:CC:DD:EE:01", "ssid": "HomeNet", "channel": 6,
        "signal_dbm": -55, "security": "WPA2"}
NEIGHBOR = {"bssid": "AA:BB:CC:DD:EE:09", "ssid": "NeighborNet",
            "channel": 11, "signal_dbm": -78, "security": "WPA2"}
CAFE = {"bssid": "11:22:33:44:55:66", "ssid": "CafeWiFi", "channel": 1,
        "signal_dbm": -70, "security": "WPA2"}


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "airwaves_example", os.path.join(EXAMPLE_DIR, "airwaves.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AW = _load_example_module()


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _readings(scan, link=None, scan_ok=True):
    return {"now": NOW, "scan_ok": scan_ok,
            "scan": [dict(a) for a in scan],
            "link": dict(link) if link else None}


def _home_link(signal=-55, bssid=HOME["bssid"]):
    return {"bssid": bssid, "ssid": "HomeNet", "signal_dbm": signal}


def _learn(scan=(HOME,), link=None, manifest=None):
    _alerts, state = AW.decide(_readings(list(scan), link=link),
                               manifest or _manifest(), {})
    return state


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "airwaves")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["access_point_gone", "evil_twin_suspect",
             "link_degraded", "new_access_point"])
        self.assertEqual(clean["tunables"]["poll_interval_sec"], 300)
        self.assertIs(clean["tunables"]["learn_first_pass"], True)
        self.assertEqual(clean["tunables"]["gone_after_scans"], 3)
        self.assertEqual(clean["tunables"]["link_drop_db"], 10)
        self.assertEqual(clean["tunables"]["iface"], "")

    def test_loads_via_load_extensions_from_a_copied_tree(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "airwaves"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("airwaves", registry)
        self.assertEqual(registry["airwaves"]["version"], "0.1.0")


class ParserTest(unittest.TestCase):
    def test_security_rank_table(self):
        cases = [("", 0), ("--", 0), ("open", 0), ("OPEN", 0),
                 ("WEP", 1), ("wep", 1),
                 ("WPA", 2), ("WPA-PSK", 2), ("PSK", 2),
                 ("WPA2", 3), ("WPA2-PSK", 3), ("WPA1 WPA2", 3),
                 ("WPA3", 4), ("SAE", 4), ("WPA2 WPA3", 4),
                 (None, 0), ("something-else", 0)]
        for text, want in cases:
            with self.subTest(text=text):
                self.assertEqual(AW.security_rank(text), want)

    def test_parse_nmcli_basic_and_percentage_conversion(self):
        text = (r"AA\:BB\:CC\:DD\:EE\:01:HomeNet:6:90:WPA2" + "\n"
                r"11\:22\:33\:44\:55\:66:CafeWiFi:1:40:--" + "\n")
        scan = AW.parse_nmcli(text)
        self.assertEqual(len(scan), 2)
        self.assertEqual(scan[0], {"bssid": "AA:BB:CC:DD:EE:01",
                                   "ssid": "HomeNet", "channel": 6,
                                   "signal_dbm": -55,
                                   "security": "WPA2"})
        self.assertEqual(scan[1]["signal_dbm"], -80)
        self.assertEqual(scan[1]["security"], "--")

    def test_parse_nmcli_escaped_colon_in_ssid(self):
        text = r"AA\:BB\:CC\:DD\:EE\:01:My\:Home\:Net:11:78:WPA2 WPA3" + "\n"
        scan = AW.parse_nmcli(text)
        self.assertEqual(len(scan), 1)
        self.assertEqual(scan[0]["ssid"], "My:Home:Net")
        self.assertEqual(scan[0]["channel"], 11)
        self.assertEqual(scan[0]["signal_dbm"], -61)
        self.assertEqual(scan[0]["security"], "WPA2 WPA3")

    def test_parse_nmcli_junk_lines_are_skipped(self):
        self.assertEqual(AW.parse_nmcli(""), [])
        self.assertEqual(AW.parse_nmcli("not enough fields\n\n"), [])
        self.assertEqual(AW.parse_nmcli(None), [])

    def test_parse_iw_link_connected(self):
        text = ("Connected to aa:bb:cc:dd:ee:01 (on wlan0)\n"
                "\tSSID: HomeNet\n"
                "\tfreq: 2437\n"
                "\tsignal: -55 dBm\n")
        self.assertEqual(AW.parse_iw_link(text),
                         {"bssid": "AA:BB:CC:DD:EE:01",
                          "ssid": "HomeNet", "signal_dbm": -55})

    def test_parse_iw_link_not_connected(self):
        self.assertIsNone(AW.parse_iw_link("Not connected.\n"))
        self.assertIsNone(AW.parse_iw_link(""))
        self.assertIsNone(AW.parse_iw_link(None))

    def test_parse_iw_scan_dump(self):
        text = (
            "BSS aa:bb:cc:dd:ee:01(on wlan0)\n"
            "\tSSID: HomeNet\n"
            "\tDS Parameter set: channel 6\n"
            "\tsignal: -55.00 dBm\n"
            "\tcapability: ESS Privacy ShortSlotTime (0x0411)\n"
            "\tRSN:\t * Version: 1\n"
            "BSS 11:22:33:44:55:66(on wlan0)\n"
            "\tSSID: OpenNet\n"
            "\tprimary channel: 1\n"
            "\tsignal: -80.00 dBm\n"
            "\tcapability: ESS ShortSlotTime (0x0401)\n")
        scan = AW.parse_iw_scan(text)
        self.assertEqual(len(scan), 2)
        self.assertEqual(scan[0]["bssid"], "AA:BB:CC:DD:EE:01")
        self.assertEqual(scan[0]["channel"], 6)
        self.assertEqual(scan[0]["signal_dbm"], -55)
        self.assertEqual(scan[0]["security"], "WPA2")
        self.assertEqual(scan[1]["security"], "--")
        self.assertEqual(AW.parse_iw_scan("no dump here"), [])

    def test_parse_iw_scan_an_unreadable_channel_is_none(self):
        # Queue A refill: the channel conversion's guard
        # (coverage run 40189711740: lines 273-274). A
        # channel number too long to convert (past the
        # interpreter's digit cap) degrades to None and
        # the rest of the entry still parses.
        text = ("BSS aa:bb:cc:dd:ee:01(on wlan0)\n"
                "\tSSID: HomeNet\n"
                "\tDS Parameter set: channel " + "9" * 5000 + "\n"
                "\tsignal: -55.00 dBm\n")
        scan = AW.parse_iw_scan(text)
        self.assertEqual(len(scan), 1)
        self.assertIsNone(scan[0]["channel"])
        self.assertEqual(scan[0]["signal_dbm"], -55)

    def test_parse_iw_link_a_huge_signal_must_be_none_probe(self):
        # FAILING BY DESIGN -- Q29 in docs/use/questions.md.
        #
        # (1) The claim, from parse_iw_link's shape in
        # runner/extensions/airwaves/airwaves.py: a signal
        # value that cannot be converted degrades to None
        # (the except ValueError arm at ~327), exactly the
        # contract Q28 established for parse_iw_scan's
        # signal in the same file.
        # (2) Where stated: that guard, and Q28's answer,
        # which widened the scan guard to (OverflowError,
        # ValueError).
        # (3) What the code does instead: the signal regex
        # admits only digits, float() of a 5000-digit string
        # returns inf, and int(inf) raises OverflowError,
        # which escapes the parser, read_live, and main's
        # (OSError, ValueError) handlers -- one pathological
        # iw link line kills the sense's cycle.
        # (4) This probe asserts the Q28 contract for the
        # link parser. It goes green when the fix lands in
        # Claude's lane; do not edit it to match the escape.
        text = ("Connected to aa:bb:cc:dd:ee:01 (on wlan0)\n"
                "\tSSID: HomeNet\n"
                "\tsignal: " + "9" * 5000 + ".0 dBm\n")
        got = AW.parse_iw_link(text)
        self.assertEqual(got["ssid"], "HomeNet")
        self.assertIsNone(got["signal_dbm"])

    def test_parse_nmcli_a_huge_signal_must_be_none_probe(self):
        # FAILING BY DESIGN -- Q29 in docs/use/questions.md.
        # The same defect at parse_nmcli's signal conversion
        # (~226-231): float() of a huge digit string is inf,
        # int(inf) raises OverflowError past the ValueError
        # guard, and the whole scan is lost instead of the
        # one reading degrading to None. All other parts of
        # the four-part note live on the iw_link probe above
        # and in Q29.
        line = ("AA\\:BB\\:CC\\:DD\\:EE\\:01:HomeNet:6:"
                + "9" * 5000 + ":WPA2")
        scan = AW.parse_nmcli(line)
        self.assertEqual(len(scan), 1)
        self.assertIsNone(scan[0]["signal_dbm"])

    def test_parse_iw_scan_a_huge_signal_must_be_none_probe(self):
        # FAILING BY DESIGN -- Q28 in docs/use/questions.md.
        #
        # (1) The claim, from parse_iw_scan's shape in
        # runner/extensions/airwaves/airwaves.py: a signal
        # value that cannot be converted degrades to None
        # (the except ValueError arm at ~281), the same
        # shape as the channel branch directly above it.
        # (2) Where stated: that guard, and its sibling at
        # the file's line ~106 catching (OverflowError,
        # ValueError) together.
        # (3) What the code does instead: the signal regex
        # admits only digits, so float() cannot raise
        # ValueError on a match -- a huge value converts
        # to inf, and int(inf) in the whole-number check
        # raises OverflowError, which escapes the guard,
        # parse_iw_scan, read_live, and main's
        # (OSError, ValueError) handlers: one pathological
        # scan dump kills the sense's cycle.
        # (4) DO NOT GREEN by editing this test. It goes
        # green when the signal guard catches the
        # conversion failure it means to catch (Claude's
        # lane, Q28).
        text = ("BSS aa:bb:cc:dd:ee:01(on wlan0)\n"
                "\tSSID: HomeNet\n"
                "\tsignal: " + "9" * 5000 + " dBm\n")
        scan = AW.parse_iw_scan(text)
        self.assertEqual(len(scan), 1)
        self.assertIsNone(scan[0]["signal_dbm"])


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.manifest = _manifest()

    def test_learn_pass_absorbs_quietly(self):
        alerts, state = AW.decide(
            _readings([HOME, NEIGHBOR], link=_home_link()),
            self.manifest, {})
        self.assertEqual(alerts, [])
        self.assertTrue(state["learned"])
        self.assertEqual(sorted(state["aps"]),
                         [HOME["bssid"], NEIGHBOR["bssid"]])
        self.assertEqual(state["ssids"]["HomeNet"]["bssids"],
                         [HOME["bssid"]])
        self.assertEqual(state["ssids"]["HomeNet"]["rank"], 3)
        self.assertEqual(state["link"],
                         {"bssid": HOME["bssid"], "signal_ref": -55.0})

    def test_quiet_case_files_nothing(self):
        state = _learn(link=_home_link())
        alerts, _s = AW.decide(_readings([HOME], link=_home_link()),
                               self.manifest, state)
        self.assertEqual(alerts, [])

    def test_no_scan_files_nothing_and_changes_nothing(self):
        state = _learn()
        alerts, new_state = AW.decide(
            _readings([], scan_ok=False), self.manifest, state)
        self.assertEqual(alerts, [])
        self.assertEqual(new_state, state)  # misses did NOT advance
        # And a failed pass before learning does not learn.
        alerts, fresh = AW.decide(_readings([], scan_ok=False),
                                  self.manifest, {})
        self.assertEqual(alerts, [])
        self.assertFalse(fresh["learned"])

    def test_new_access_point_is_medium_with_key_details(self):
        state = _learn()
        alerts, _s = AW.decide(_readings([HOME, CAFE]),
                               self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["new_access_point"])
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "airwaves")
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"]["bssid"], CAFE["bssid"])
        self.assertEqual(alert["detail"]["ssid"], "CafeWiFi")
        self.assertEqual(alert["detail"]["channel"], 1)
        self.assertEqual(alert["detail"]["security"], "WPA2")

    def test_evil_twin_new_bssid_for_known_ssid_is_high(self):
        state = _learn()
        twin = dict(HOME, bssid="AA:BB:CC:DD:EE:02")
        alerts, _s = AW.decide(_readings([HOME, twin]),
                               self.manifest, state)
        # ONLY the evil twin: new_access_point must not also fire.
        self.assertEqual([a["signal"] for a in alerts],
                         ["evil_twin_suspect"])
        alert = alerts[0]
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["detail"]["ssid"], "HomeNet")
        self.assertEqual(alert["detail"]["bssid"], "AA:BB:CC:DD:EE:02")
        self.assertEqual(alert["detail"]["expected"], [HOME["bssid"]])
        self.assertEqual(alert["detail"]["observed"], "WPA2")

    def test_evil_twin_security_downgrade_is_high(self):
        state = _learn()
        weaker = dict(HOME, security="WEP")
        alerts, state = AW.decide(_readings([weaker]),
                                  self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["evil_twin_suspect"])
        alert = alerts[0]
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["detail"]["expected"], "WPA2")
        self.assertEqual(alert["detail"]["observed"], "WEP")
        # The downgrade fired BEFORE the baseline absorbed it:
        # the same weaker reading a second time files nothing.
        alerts, _s = AW.decide(_readings([weaker]),
                               self.manifest, state)
        self.assertEqual(alerts, [])

    def test_access_point_gone_after_enough_missed_scans(self):
        state = _learn(scan=(HOME, NEIGHBOR))
        for want_misses in (1, 2):
            alerts, state = AW.decide(_readings([HOME]),
                                      self.manifest, state)
            self.assertEqual(alerts, [])
            self.assertEqual(state["aps"][NEIGHBOR["bssid"]]["misses"],
                             want_misses)
        alerts, state = AW.decide(_readings([HOME]),
                                  self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["access_point_gone"])
        alert = alerts[0]
        self.assertEqual(alert["severity"], "info")
        self.assertEqual(alert["detail"]["bssid"], NEIGHBOR["bssid"])
        self.assertEqual(alert["detail"]["ssid"], "NeighborNet")
        self.assertEqual(alert["detail"]["scans_missed"], 3)
        self.assertNotIn(NEIGHBOR["bssid"], state["aps"])
        self.assertNotIn("NeighborNet", state["ssids"])
        # A later reappearance is a fresh new_access_point.
        alerts, _s = AW.decide(_readings([HOME, NEIGHBOR]),
                               self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["new_access_point"])

    def test_missed_scans_reset_when_the_ap_returns(self):
        state = _learn(scan=(HOME, NEIGHBOR))
        _a, state = AW.decide(_readings([HOME]), self.manifest, state)
        _a, state = AW.decide(_readings([HOME]), self.manifest, state)
        self.assertEqual(state["aps"][NEIGHBOR["bssid"]]["misses"], 2)
        alerts, state = AW.decide(_readings([HOME, NEIGHBOR]),
                                  self.manifest, state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["aps"][NEIGHBOR["bssid"]]["misses"], 0)

    def test_link_roam_is_medium_link_degraded(self):
        state = _learn(scan=(HOME, NEIGHBOR), link=_home_link())
        roamed = _home_link(bssid=NEIGHBOR["bssid"])
        alerts, state = AW.decide(_readings([HOME, NEIGHBOR], link=roamed),
                                  self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts], ["link_degraded"])
        alert = alerts[0]
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"]["old_bssid"], HOME["bssid"])
        self.assertEqual(alert["detail"]["new_bssid"], NEIGHBOR["bssid"])
        self.assertEqual(state["link"]["bssid"], NEIGHBOR["bssid"])

    def test_link_drop_is_medium_and_ref_resets(self):
        state = _learn(link=_home_link())
        alerts, state = AW.decide(
            _readings([HOME], link=_home_link(signal=-70)),
            self.manifest, state)
        self.assertEqual([a["signal"] for a in alerts], ["link_degraded"])
        self.assertEqual(alerts[0]["detail"]["from_dbm"], -55.0)
        self.assertEqual(alerts[0]["detail"]["to_dbm"], -70.0)
        self.assertEqual(state["link"]["signal_ref"], -70.0)
        # Same weakened reading again: nothing (the ref moved).
        alerts, state = AW.decide(
            _readings([HOME], link=_home_link(signal=-70)),
            self.manifest, state)
        self.assertEqual(alerts, [])

    def test_link_small_dip_and_rise_file_nothing(self):
        state = _learn(link=_home_link())
        alerts, state = AW.decide(
            _readings([HOME], link=_home_link(signal=-60)),
            self.manifest, state)
        self.assertEqual(alerts, [])  # 5 dB dip is under the drop
        alerts, state = AW.decide(
            _readings([HOME], link=_home_link(signal=-48)),
            self.manifest, state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["link"]["signal_ref"], -48.0)  # ref rose

    def test_link_absent_keeps_state_and_files_nothing(self):
        state = _learn(link=_home_link())
        alerts, state = AW.decide(_readings([HOME], link=None),
                                  self.manifest, state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["link"],
                         {"bssid": HOME["bssid"], "signal_ref": -55.0})

    def test_same_readings_twice_files_nothing_second_time(self):
        state = _learn()
        readings = _readings([HOME, CAFE])
        alerts, state = AW.decide(readings, self.manifest, state)
        self.assertEqual(len(alerts), 1)
        alerts, state = AW.decide(readings, self.manifest, state)
        self.assertEqual(alerts, [])

    def test_learn_first_pass_false_files_the_first_pass(self):
        manifest = _manifest()
        manifest["tunables"] = dict(manifest["tunables"],
                                    learn_first_pass=False)
        alerts, state = AW.decide(_readings([HOME]), manifest, {})
        self.assertEqual([a["signal"] for a in alerts],
                         ["new_access_point"])
        self.assertTrue(state["learned"])

    def test_every_signal_at_its_severity(self):
        # One scripted neighborhood walk that fires all four.
        state = _learn(scan=(HOME, NEIGHBOR), link=_home_link())
        twin = dict(HOME, bssid="AA:BB:CC:DD:EE:02")
        weak_link = _home_link(signal=-80)
        alerts, state = AW.decide(
            _readings([HOME, CAFE, twin], link=weak_link),
            self.manifest, state)
        by_signal = {a["signal"]: a["severity"] for a in alerts}
        self.assertEqual(by_signal["new_access_point"], "medium")
        self.assertEqual(by_signal["evil_twin_suspect"], "high")
        self.assertEqual(by_signal["link_degraded"], "medium")
        for _ in range(2):
            _a, state = AW.decide(_readings([HOME]), self.manifest, state)
        alerts, _s = AW.decide(_readings([HOME]), self.manifest, state)
        gone = [a for a in alerts if a["signal"] == "access_point_gone"]
        self.assertTrue(gone)
        self.assertEqual(gone[0]["severity"], "info")


class AirFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(EXAMPLE_DIR,
                        os.path.join(self.ext_root, "airwaves"))
        self.cfg = {
            "shared_secret": DEFAULT_SECRET,
            "additional_secrets": {"air-key": AIR_SECRET},
            "key_policies": {
                "air-key": {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                "airwaves": {"enabled": True, "key_id": "air-key",
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

    def readings_file(self, readings, name="readings.json"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(readings, fh)
        return path

    def run_producer(self, readings, name="readings.json",
                     with_secret=True):
        env = {"HOMING_PIGEON_SENSOR_SECRET": AIR_SECRET} \
            if with_secret else {}
        with unittest.mock.patch.dict(os.environ, env):
            if not with_secret:
                os.environ.pop("HOMING_PIGEON_SENSOR_SECRET", None)
            return AW.main(["--readings",
                            self.readings_file(readings, name),
                            "--local-dir", self.base,
                            "--key-id", "air-key",
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


class ProducerTest(AirFixture):
    def test_print_path_learns_then_files(self):
        path = self.readings_file(_readings([HOME], link=_home_link()))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = AW.main(["--readings", path,
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "")
        path = self.readings_file(_readings([HOME, CAFE]),
                                  name="readings2.json")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = AW.main(["--readings", path,
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        printed = [json.loads(ln) for ln in
                   out.getvalue().splitlines() if ln.strip()]
        self.assertEqual([p["signal"] for p in printed],
                         ["new_access_point"])

    def test_failed_delivery_leaves_the_state_unwritten(self):
        self.assertEqual(
            self.run_producer(_readings([HOME], link=_home_link())), 0)
        self.assertEqual(self.inbox_names(), [])
        os.remove(self.state_path)
        # Re-learn, then a twin pass with no secret: delivery
        # fails, the state stays at the learned baseline, and a
        # working retry still files the twin.
        self.assertEqual(
            self.run_producer(_readings([HOME], link=_home_link())), 0)
        with open(self.state_path, encoding="utf-8") as fh:
            learned_state = fh.read()
        twin = dict(HOME, bssid="AA:BB:CC:DD:EE:02")
        rc = self.run_producer(_readings([HOME, twin]),
                               name="twin.json", with_secret=False)
        self.assertEqual(rc, 2)
        with open(self.state_path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), learned_state)
        rc = self.run_producer(_readings([HOME, twin]),
                               name="twin.json")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 1)

    def test_no_source_available_is_a_quiet_noop(self):
        with unittest.mock.patch.object(AW.shutil, "which",
                                        return_value=None):
            readings = AW.read_live(_manifest())
        self.assertFalse(readings["scan_ok"])
        self.assertEqual(readings["scan"], [])
        self.assertIsNone(readings["link"])
        out = io.StringIO()
        with redirect_stdout(out):
            rc = AW.main(["--readings",
                          self.readings_file(readings),
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "")


class EndToEndTest(AirFixture):
    def test_evil_twin_files_and_wakes_a_brief(self):
        # Pass 1: the baseline neighborhood learns quietly.
        rc = self.run_producer(_readings([HOME], link=_home_link()))
        self.assertEqual(rc, 0)
        self.assertEqual(self.inbox_names(), [])
        # Pass 2: the known SSID appears from a NEW BSSID.
        twin = dict(HOME, bssid="AA:BB:CC:DD:EE:02")
        rc = self.run_producer(
            _readings([HOME, twin], link=_home_link()),
            name="readings2.json")
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.inbox_names()), 1)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 1)
        self.assertEqual(self.inbox_names(), [])
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["sensor"], "airwaves")
        self.assertEqual(rec["source"], "local")
        self.assertEqual(rec["extension"], "airwaves")
        self.assertEqual(rec["extension_version"], "0.1.0")
        self.assertEqual(rec["signal"], "evil_twin_suspect")
        self.assertEqual(rec["severity"], "high")
        declared = {s["name"]: s["description"]
                    for s in _manifest()["signals"]}
        self.assertEqual(rec["signal_description"],
                         declared["evil_twin_suspect"])
        # The high signal wakes the deterministic brief; with no
        # inference configured the brief is the fallback.
        lines = self.wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "evil_twin_suspect")
        self.assertEqual(brief["sensor"], "airwaves")
        self.assertEqual(brief["status"], "no_inference")


class RunToolTest(unittest.TestCase):
    """Queue A refill: _run's execution legs (coverage
    run 40187685363: 7 lines on both platforms; only the
    missing-binary return had ever run). The helper's
    contract is its docstring: a scan tool's stdout on
    success, and None for every failure shape -- a
    nonzero exit, a timeout, an OSError from the run
    itself -- because each means this source has
    nothing to say, never an exception into the sense.
    The interpreter stands in for the scan tools.
    """

    def test_a_successful_run_returns_its_stdout(self):
        self.assertEqual(
            AW._run([sys.executable, "-c", "print('scan-ok')"]),
            "scan-ok\n")

    def test_a_nonzero_exit_is_none(self):
        self.assertIsNone(AW._run(
            [sys.executable, "-c", "import sys; sys.exit(3)"]))

    def test_a_timeout_is_none(self):
        self.assertIsNone(AW._run(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.2))

    def test_an_oserror_from_the_run_is_none(self):
        import subprocess as sp
        with unittest.mock.patch.object(
                sp, "run", side_effect=OSError("cannot fork")):
            self.assertIsNone(AW._run([sys.executable, "-c", "pass"]))


if __name__ == "__main__":
    unittest.main()
