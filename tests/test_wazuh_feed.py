"""Wazuh Feed: the example sense that tails a manager alerts.json.

Pins the Wazuh Feed example (extensions/wazuh-feed/):
the manifest through the real extension loader, the pure
parse_event() and read_new_events() reader plumbing, and the
pure decide() episode machine -- level 10+ files high,
level 5-9 files medium, levels below 5 never file, and an
episode per (rule id, agent name) files once until it has
been quiet for episode_quiet_sec.

The fixtures are SYNTHETIC, built from the documented
alerts.json shape: no Wazuh manager existed in the
measurement sandbox, so no real alerts.json was captured.
No live manager anywhere: decide() is driven with fixture
event readings, and the reader with a temp file -- including
the teaching case, a missing file that stays quiet forever.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(
    REPO, "extensions", "wazuh-feed")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "wazuh_feed_example",
        os.path.join(EXAMPLE_DIR, "wazuh_feed.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


WZ = _load_example_module()

T0 = datetime(2026, 10, 18, 12, 0, 0,
              tzinfo=timezone.utc).timestamp()


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _line(level=5, rule_id="5710", agent="web-1",
          ts="2026-10-18T12:00:00.000+0000",
          description="sshd: authentication failed.",
          groups=("sshd", "authentication_failed")):
    """One synthetic alerts.json line, from the documented shape."""
    return json.dumps({
        "timestamp": ts,
        "rule": {"id": rule_id, "level": level,
                 "description": description, "groups": list(groups)},
        "agent": {"id": "001", "name": agent},
        "decoder": {"name": "sshd"},
        "data": {"srcip": "192.0.2.10"},
        "full_log": "sshd: authentication failed",
        "location": "/var/log/auth.log"})


def _event(level=5, ts=T0, rule_id="5710", agent="web-1",
           description="sshd: authentication failed.",
           groups=("sshd",)):
    return {"ts": ts, "level": level, "rule_id": rule_id,
            "description": description, "groups": list(groups),
            "agent_name": agent, "agent_id": "001"}


def _readings(events, now=None):
    events = list(events)
    return {"now": events[-1]["ts"] if now is None and events else now,
            "events": events}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "wazuh_feed")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            [s["name"] for s in clean["signals"]],
            ["wazuh_alert_high", "wazuh_alert"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        self.assertEqual(clean["tunables"]["log_paths"],
                         ["/var/ossec/logs/alerts/alerts.json"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "wazuh-feed"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("wazuh_feed", registry)


class ParseEventTest(unittest.TestCase):
    def test_documented_shape_parses(self):
        ev = WZ.parse_event(_line(level=10, rule_id="5715"))
        self.assertEqual(ev["level"], 10)
        self.assertEqual(ev["rule_id"], "5715")
        self.assertEqual(ev["description"],
                         "sshd: authentication failed.")
        self.assertEqual(ev["groups"],
                         ["sshd", "authentication_failed"])
        self.assertEqual(ev["agent_name"], "web-1")
        self.assertEqual(ev["agent_id"], "001")
        self.assertEqual(ev["ts"], T0)

    def test_level_bands_all_parse(self):
        # Banding is decide()'s job; every level parses here,
        # including the below-5 ones that are never filed.
        for level in (0, 3, 5, 9, 10, 15):
            ev = WZ.parse_event(_line(level=level))
            self.assertEqual(ev["level"], level, level)

    def test_unusable_lines_answer_none(self):
        for line in ("", "not json", "[]", "{}",
                     json.dumps({"rule": {"level": 5}}),
                     json.dumps({"rule": {"id": "5710"}}),
                     json.dumps({"rule": {"id": "5710",
                                          "level": "high"}})):
            self.assertIsNone(WZ.parse_event(line), line)


class ReaderTest(unittest.TestCase):
    def test_missing_file_is_a_quiet_noop_forever(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "alerts.json")
            events, reader = WZ.read_new_events([missing], {})
            self.assertEqual(events, [])
            self.assertEqual(reader, {})
            kept = {missing: {"inode": 4242, "offset": 99}}
            for _i in range(3):
                events, reader = WZ.read_new_events([missing], kept)
                self.assertEqual(events, [])
                self.assertEqual(reader[missing],
                                 {"inode": 4242, "offset": 99})

    def test_tails_incrementally(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "alerts.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_line(level=10) + "\n")
                fh.write("not json\n")
                fh.write(_line(level=3) + "\n")
            events, reader = WZ.read_new_events([path], {})
            self.assertEqual([e["level"] for e in events], [10, 3])
            self.assertEqual(reader[path]["offset"],
                             os.path.getsize(path))
            events, reader = WZ.read_new_events([path], reader)
            self.assertEqual(events, [])
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(_line(level=7, rule_id="5710") + "\n")
            events, _reader = WZ.read_new_events([path], reader)
            self.assertEqual([e["level"] for e in events], [7])


class DecideTest(unittest.TestCase):
    def decide(self, readings, state=None, manifest=None):
        return WZ.decide(readings, manifest or _manifest(),
                         state if state is not None else {})

    def test_level_10_and_above_files_high_with_detail(self):
        alerts, _state = self.decide(_readings([_event(level=12)]))
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "wazuh_feed")
        self.assertEqual(alert["signal"], "wazuh_alert_high")
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["detail"]["rule_id"], "5710")
        self.assertEqual(alert["detail"]["description"],
                         "sshd: authentication failed.")
        self.assertEqual(alert["detail"]["groups"], ["sshd"])
        self.assertEqual(alert["detail"]["agent"], "web-1")
        self.assertEqual(alert["detail"]["level"], 12)

    def test_levels_5_to_9_file_medium(self):
        for level in (5, 7, 9):
            alerts, _state = self.decide(
                _readings([_event(level=level)]))
            self.assertEqual([a["signal"] for a in alerts],
                             ["wazuh_alert"], level)
            self.assertEqual(alerts[0]["severity"], "medium")

    def test_levels_below_5_are_parsed_but_never_filed(self):
        for level in (0, 3, 4):
            alerts, state = self.decide(
                _readings([_event(level=level)]))
            self.assertEqual(alerts, [], level)
            self.assertEqual(state["episodes"], {})

    def test_episode_files_once_per_rule_and_agent(self):
        events = [_event(level=10, ts=T0),
                  _event(level=10, ts=T0 + 60),
                  _event(level=10, ts=T0 + 120)]
        alerts, state = self.decide(_readings(events))
        self.assertEqual(len(alerts), 1)
        # And across passes, while the episode is active.
        alerts, _state = self.decide(
            _readings([_event(level=10, ts=T0 + 300)]), state=state)
        self.assertEqual(alerts, [])

    def test_episodes_are_per_agent_and_per_rule(self):
        events = [_event(level=10, agent="web-1"),
                  _event(level=10, agent="db-1"),
                  _event(level=10, rule_id="5715", agent="web-1")]
        alerts, _state = self.decide(_readings(events))
        self.assertEqual(len(alerts), 3)

    def test_episode_rearms_after_the_quiet_period(self):
        alerts, state = self.decide(_readings([_event(level=10)]))
        self.assertEqual(len(alerts), 1)
        later = T0 + 3600  # exactly episode_quiet_sec on
        alerts, _state = self.decide(
            _readings([_event(level=10, ts=later)], now=later),
            state=state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["wazuh_alert_high"])

    def test_reader_subdict_is_preserved_and_ignored(self):
        state = {"episodes": {},
                 "_reader": {"/var/ossec/logs/alerts/alerts.json":
                             {"inode": 7, "offset": 42}}}
        alerts, new_state = self.decide(
            _readings([_event(level=10)]), state=state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(
            new_state["_reader"],
            {"/var/ossec/logs/alerts/alerts.json":
             {"inode": 7, "offset": 42}})

    def test_unusable_events_are_ignored(self):
        readings = {"now": T0, "events": [
            None, {}, {"level": "x", "rule_id": "5710"},
            {"level": 10, "rule_id": ""}]}
        alerts, _state = self.decide(readings)
        self.assertEqual(alerts, [])


class MainTest(unittest.TestCase):
    def test_readings_fixture_files_the_alert(self):
        with tempfile.TemporaryDirectory() as d:
            readings_path = os.path.join(d, "readings.json")
            state_path = os.path.join(d, "state.json")
            with open(readings_path, "w", encoding="utf-8") as fh:
                json.dump(_readings([_event(level=11)]), fh)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = WZ.main(["--readings", readings_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["wazuh_alert_high"])

    def test_missing_alerts_file_is_a_quiet_pass(self):
        # The standalone-agent case at the main() level: the
        # configured file never appears, and the pass is rc 0
        # with no output and no complaint.
        with tempfile.TemporaryDirectory() as d:
            manifest = _manifest()
            manifest["tunables"]["log_paths"] = [
                os.path.join(d, "alerts.json")]
            manifest_path = os.path.join(d, "extension.json")
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = WZ.main(["--manifest", manifest_path,
                              "--state", os.path.join(d, "state.json")])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
