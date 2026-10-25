"""Suricata Feed: the example sense that tails eve.json.

Pins the Suricata Feed example
(runner/extensions/suricata-feed/): the manifest through
the real extension loader, the pure parse_event() and
read_new_events() reader plumbing, and the pure decide()
episode machine -- alert episodes key on signature_id + src
+ dest and carry Suricata's own severity, anomaly episodes
file once per distinct anomaly.event per window, and every
other eve.json event type is traffic that parses to nothing.

The fixture is a trimmed copy of a real captured eve.json
sample (an http event and an anomaly event); the capture
held no alert event, so alert lines are built here to the
documented eve.json alert shape. No live logs anywhere:
decide() is driven with fixture event readings, and the
reader is driven with a temp file.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "suricata-feed")
FIXTURE = os.path.join(EXAMPLE_DIR, "fixtures", "suricata-eve.json")

SRC = "192.0.2.10"
DST = "198.51.100.7"
SIG = "ET SCAN Nmap Scripting Engine User-Agent Detected"
SIG_ID = 2010935


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "suricata_feed_example",
        os.path.join(EXAMPLE_DIR, "suricata_feed.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SF = _load_example_module()

T0 = datetime(2026, 10, 19, 4, 0, 0, tzinfo=timezone.utc).timestamp()


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _alert_line(ts="2026-10-19T04:00:00.000000+0000", severity=1,
                signature_id=SIG_ID, src=SRC, dest=DST, dest_port=80):
    return json.dumps({
        "timestamp": ts, "flow_id": 42, "event_type": "alert",
        "src_ip": src, "src_port": 51234, "dest_ip": dest,
        "dest_port": dest_port, "proto": "TCP",
        "alert": {"action": "allowed", "gid": 1,
                  "signature_id": signature_id, "rev": 3,
                  "signature": SIG,
                  "category": "Attempted Information Leak",
                  "severity": severity}})


def _anomaly_line(ts="2026-10-19T04:00:00.000000+0000",
                  event="UNABLE_TO_MATCH_RESPONSE_TO_REQUEST"):
    return json.dumps({
        "timestamp": ts, "flow_id": 43, "event_type": "anomaly",
        "src_ip": SRC, "src_port": 36310, "dest_ip": DST,
        "dest_port": 3128, "proto": "TCP",
        "anomaly": {"app_proto": "http", "type": "applayer",
                    "event": event, "layer": "proto_parser"}})


def _alert(ts, severity=1, signature_id=SIG_ID, src=SRC, dest=DST,
           dest_port=80):
    return {"ts": ts, "kind": "alert", "signature": SIG,
            "signature_id": signature_id,
            "category": "Attempted Information Leak",
            "alert_severity": severity, "src_ip": src,
            "src_port": 51234, "dest_ip": dest,
            "dest_port": dest_port, "proto": "TCP"}


def _anomaly(ts, event="UNABLE_TO_MATCH_RESPONSE_TO_REQUEST"):
    return {"ts": ts, "kind": "anomaly", "anomaly_type": "applayer",
            "event": event, "layer": "proto_parser", "src_ip": SRC,
            "src_port": 36310, "dest_ip": DST, "dest_port": 3128,
            "proto": "TCP"}


def _readings(events, now=None):
    events = list(events)
    return {"now": events[-1]["ts"] if now is None and events else now,
            "events": events}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "suricata_feed")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual([s["name"] for s in clean["signals"]],
                         ["suricata_alert", "suricata_anomaly"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        self.assertEqual(clean["tunables"]["log_paths"],
                         ["/var/log/suricata/eve.json"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "suricata-feed"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("suricata_feed", registry)

    def test_manifest_signals_match_the_readme_list(self):
        with open(os.path.join(EXAMPLE_DIR, "README.md"),
                  encoding="utf-8") as fh:
            readme = fh.read()
        for signal in ("suricata_alert", "suricata_anomaly"):
            self.assertIn(f"`{signal}`", readme)


class ParseEventTest(unittest.TestCase):
    def test_alert_line_parses_with_its_detection_fields(self):
        ev = SF.parse_event(_alert_line())
        self.assertEqual(ev["kind"], "alert")
        self.assertEqual(ev["signature"], SIG)
        self.assertEqual(ev["signature_id"], SIG_ID)
        self.assertEqual(ev["category"], "Attempted Information Leak")
        self.assertEqual(ev["alert_severity"], 1)
        self.assertEqual(ev["src_ip"], SRC)
        self.assertEqual(ev["dest_ip"], DST)
        self.assertEqual(ev["dest_port"], 80)
        self.assertEqual(ev["proto"], "TCP")
        self.assertEqual(ev["ts"], T0)

    def test_anomaly_line_parses_with_its_event_name(self):
        ev = SF.parse_event(_anomaly_line())
        self.assertEqual(ev["kind"], "anomaly")
        self.assertEqual(ev["event"],
                         "UNABLE_TO_MATCH_RESPONSE_TO_REQUEST")
        self.assertEqual(ev["anomaly_type"], "applayer")
        self.assertEqual(ev["layer"], "proto_parser")

    def test_captured_fixture_http_is_traffic_anomaly_files(self):
        with open(FIXTURE, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIsNone(SF.parse_event(lines[0]))  # http: traffic
        ev = SF.parse_event(lines[1])
        self.assertEqual(ev["kind"], "anomaly")
        self.assertEqual(ev["event"],
                         "UNABLE_TO_MATCH_RESPONSE_TO_REQUEST")
        self.assertEqual(ev["ts"], datetime(
            2026, 10, 19, 3, 59, 36, 585440,
            tzinfo=timezone.utc).timestamp())

    def test_other_event_types_parse_to_nothing(self):
        for event_type in ("http", "tls", "dns", "flow", "fileinfo",
                           "stats", "ssh"):
            line = json.dumps({"timestamp": "2026-10-19T04:00:00+0000",
                               "event_type": event_type,
                               "src_ip": SRC, "dest_ip": DST})
            self.assertIsNone(SF.parse_event(line), event_type)

    def test_malformed_lines_answer_none(self):
        bad = ["", "not json", "[1, 2]", "{}",
               _alert_line(severity=4), _alert_line(severity=0),
               _alert_line(severity=True),
               _alert_line(signature_id="2010935"),
               _alert_line(ts="yesterday-ish"),
               json.dumps({"timestamp": "2026-10-19T04:00:00+0000",
                           "event_type": "alert", "alert": {}}),
               json.dumps({"timestamp": "2026-10-19T04:00:00+0000",
                           "event_type": "anomaly",
                           "anomaly": {"type": "applayer"}})]
        for line in bad:
            self.assertIsNone(SF.parse_event(line), line)


class ReaderTest(unittest.TestCase):
    def test_tails_incrementally_and_keeps_missing_offsets(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "eve.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_alert_line() + "\n")
                fh.write(_anomaly_line() + "\n")
            events, reader = SF.read_new_events([path], {})
            self.assertEqual(len(events), 2)
            self.assertEqual(reader[path]["offset"],
                             os.path.getsize(path))
            events, reader = SF.read_new_events([path], reader)
            self.assertEqual(events, [])
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(_alert_line(severity=2) + "\n")
            events, reader = SF.read_new_events([path], reader)
            self.assertEqual(len(events), 1)
            missing = os.path.join(d, "nope.json")
            kept = {missing: {"inode": 4242, "offset": 99}}
            events, new_reader = SF.read_new_events([missing], kept)
            self.assertEqual(events, [])
            self.assertEqual(new_reader[missing],
                             {"inode": 4242, "offset": 99})

    def test_an_unreadable_file_keeps_its_entry(self):
        # Queue A refill: read_new_events' open-failure leg
        # (coverage run 40189711740: 4 lines; the same leg
        # across the tailing senses). A missing or
        # unreadable file yields no events and keeps its
        # previous entry; a directory stats fine but
        # cannot be opened as a file.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "eve.json")
            os.mkdir(path)
            kept = {path: {"inode": os.stat(path).st_ino,
                           "offset": 0}}
            events, new_reader = SF.read_new_events([path], kept)
            self.assertEqual(events, [])
            self.assertEqual(new_reader[path], kept[path])

    def test_inode_change_and_shrink_restart_from_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "eve.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_alert_line() + "\n")
            _events, reader = SF.read_new_events([path], {})
            other = os.path.join(d, "eve.json.1")
            with open(other, "w", encoding="utf-8") as fh:
                fh.write(_anomaly_line() + "\n")
                fh.write(_alert_line(severity=3) + "\n")
            os.replace(other, path)
            events, reader = SF.read_new_events([path], reader)
            self.assertEqual(len(events), 2)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_anomaly_line() + "\n")
            events, _reader = SF.read_new_events([path], reader)
            self.assertEqual(len(events), 1)


class DecideTest(unittest.TestCase):
    def decide(self, readings, state=None, manifest=None):
        return SF.decide(readings, manifest or _manifest(),
                         state if state is not None else {})

    def test_alert_severity_maps_from_suricata_own_scale(self):
        for sev, want in ((1, "high"), (2, "medium"), (3, "info")):
            alerts, _state = self.decide(
                _readings([_alert(T0, severity=sev)]))
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0]["signal"], "suricata_alert")
            self.assertEqual(alerts[0]["severity"], want, sev)

    def test_alert_detail_carries_the_match(self):
        alerts, _state = self.decide(_readings([_alert(T0)]))
        detail = alerts[0]["detail"]
        self.assertEqual(alerts[0]["sensor"], "suricata_feed")
        self.assertEqual(detail["signature"], SIG)
        self.assertEqual(detail["signature_id"], SIG_ID)
        self.assertEqual(detail["category"],
                         "Attempted Information Leak")
        self.assertEqual(detail["src_ip"], SRC)
        self.assertEqual(detail["dest_ip"], DST)
        self.assertEqual(detail["dest_port"], 80)
        self.assertEqual(detail["proto"], "TCP")

    def test_same_episode_files_once_even_across_ports(self):
        # The episode is signature + src + dest; the port is
        # detail, not identity, so a port change stays quiet.
        events = [_alert(T0), _alert(T0 + 10, dest_port=8080),
                  _alert(T0 + 20)]
        alerts, state = self.decide(_readings(events))
        self.assertEqual(len(alerts), 1)
        alerts, _state = self.decide(_readings(events), state=state)
        self.assertEqual(alerts, [])

    def test_new_signature_or_dest_files_a_new_episode(self):
        events = [_alert(T0), _alert(T0 + 10, signature_id=2020001),
                  _alert(T0 + 20, dest="203.0.113.9")]
        alerts, state = self.decide(_readings(events))
        self.assertEqual(len(alerts), 3)
        self.assertEqual(len(state["episodes"]), 3)

    def test_anomaly_files_medium_once_per_distinct_event(self):
        events = [_anomaly(T0), _anomaly(T0 + 10),
                  _anomaly(T0 + 20, event="INVALID_IP_VERSION")]
        alerts, _state = self.decide(_readings(events))
        self.assertEqual([(a["signal"], a["severity"]) for a in alerts],
                         [("suricata_anomaly", "medium"),
                          ("suricata_anomaly", "medium")])
        self.assertEqual(alerts[0]["detail"]["event"],
                         "UNABLE_TO_MATCH_RESPONSE_TO_REQUEST")
        self.assertEqual(alerts[0]["detail"]["layer"], "proto_parser")

    def test_episode_refiles_after_the_cooldown(self):
        alerts, state = self.decide(_readings([_alert(T0)]))
        self.assertEqual(len(alerts), 1)
        later = T0 + 3600
        alerts, _state = self.decide(_readings([_alert(later)]),
                                     state=state)
        self.assertEqual(len(alerts), 1)

    def test_episode_clears_when_quiet_then_refiles_on_return(self):
        alerts, state = self.decide(_readings([_anomaly(T0)]))
        self.assertEqual(len(alerts), 1)
        alerts, state = self.decide({"now": T0 + 7200, "events": []},
                                    state=state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["episodes"], {})
        alerts, _state = self.decide(_readings([_anomaly(T0 + 7201)]),
                                     state=state)
        self.assertEqual(len(alerts), 1)

    def test_events_are_processed_in_timestamp_order(self):
        events = [_anomaly(T0 + 10), _alert(T0)]
        alerts, _state = self.decide(_readings(events))
        self.assertEqual([a["signal"] for a in alerts],
                         ["suricata_alert", "suricata_anomaly"])

    def test_reader_subdict_is_preserved_and_ignored(self):
        kept = {"/var/log/suricata/eve.json": {"inode": 7, "offset": 42}}
        alerts, new_state = self.decide(_readings([_alert(T0)]),
                                        state={"_reader": kept})
        self.assertEqual(len(alerts), 1)
        self.assertEqual(new_state["_reader"], kept)

    def test_unusable_events_are_ignored(self):
        readings = {"now": T0, "events": [
            None, {}, {"ts": T0, "kind": "flow"},
            {"ts": "x", "kind": "alert", "signature_id": SIG_ID,
             "alert_severity": 1},
            {"ts": T0, "kind": "alert", "signature_id": SIG_ID,
             "alert_severity": 9},
            {"ts": T0, "kind": "anomaly", "event": ""}]}
        alerts, _state = self.decide(readings)
        self.assertEqual(alerts, [])


class MainTest(unittest.TestCase):
    def test_log_file_fixture_files_only_the_anomaly(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = SF.main(["--log-file", FIXTURE,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual(
                [(p["signal"], p["severity"]) for p in printed],
                [("suricata_anomaly", "medium")])
            self.assertEqual(
                SF.main(["--log-file", os.path.join(d, "missing.json"),
                         "--state", state_path]), 2)
            with open(os.path.join(d, "bad.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("not json")
            self.assertEqual(
                SF.main(["--readings", os.path.join(d, "bad.json"),
                         "--state", state_path]), 2)

    def test_failed_local_delivery_leaves_the_state_unwritten(self):
        # No signing secret in the environment: delivery cannot
        # be set up, main returns 2, and the state file is never
        # written -- so the reader offsets cannot have advanced
        # and the next pass re-reads the same lines.
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            env = dict(os.environ)
            env.pop("HOMING_PIGEON_SENSOR_SECRET", None)
            old = os.environ.copy()
            os.environ.clear()
            os.environ.update(env)
            try:
                rc = SF.main(["--log-file", FIXTURE,
                              "--state", state_path,
                              "--local-dir", d])
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state_path))


class MainDeliveryLegsTest(unittest.TestCase):
    """Queue A refill: main's tunables guard and its two
    local-delivery refusals (local full-suite map at 93998ca:
    lines 509, 555, 559-562). A manifest whose tunables are not
    an object reads as no tunables; a delivery that cannot run
    at all, and one that delivers fewer alerts than it was
    handed, are both rc 2 with the state left unwritten so the
    offsets do not advance."""

    def _manifest_path(self, d, tunables):
        manifest = _manifest()
        manifest["tunables"] = tunables
        path = os.path.join(d, "extension.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        return path

    def test_non_dict_tunables_and_undeliverable_is_rc2(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            with mock.patch.object(
                    SF, "_deliver_local", return_value=None), \
                    redirect_stderr(io.StringIO()):
                rc = SF.main([
                    "--manifest", self._manifest_path(d, 42),
                    "--state", state_path,
                    "--log-file", FIXTURE,
                    "--local-dir", d])
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state_path))

    def test_partial_delivery_is_rc2_and_saves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            err = io.StringIO()
            with mock.patch.object(
                    SF, "_deliver_local", return_value=0), \
                    redirect_stderr(err):
                rc = SF.main([
                    "--manifest", self._manifest_path(d, {}),
                    "--state", state_path,
                    "--log-file", FIXTURE,
                    "--local-dir", d])
            self.assertEqual(rc, 2)
            self.assertIn("1 of 1 alert(s) not delivered",
                          err.getvalue())
            self.assertFalse(os.path.exists(state_path))


if __name__ == "__main__":
    unittest.main()
