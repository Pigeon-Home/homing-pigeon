"""Falco Feed: the example sense that tails Falco's JSON alerts.

Pins the Falco Feed example
(extensions/falco-feed/): the manifest through the
real extension loader, the pure parse_event() and
read_new_events() reader plumbing, and the pure decide()
episode machine -- an episode (rule + output_fields digest)
files once, a distinct fields set for the same rule files as
a new episode, the cooldown refiles, and Informational and
Debug alerts are parsed but never filed.

Falco never ran in the measurement sandbox, so every fixture
here is synthetic, built from the documented alert shape.
No live logs anywhere: decide() is driven with fixture event
readings, and the reader is driven with a temp file.
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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "extensions", "falco-feed")
FIXTURE = os.path.join(EXAMPLE_DIR, "fixtures", "falco-alerts.jsonl")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "falco_feed_example", os.path.join(EXAMPLE_DIR, "falco_feed.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FF = _load_example_module()

T0 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc).timestamp()
RULE = "Terminal shell in container"
FIELDS = {"container.id": "abc123", "proc.name": "bash",
          "user.name": "root"}


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _line(ts="2026-10-18T12:00:01.000000000Z", rule=RULE,
          priority="Critical", fields=None, hostname="pi-box"):
    return json.dumps({
        "time": ts, "rule": rule, "priority": priority,
        "output": "an output line",
        "output_fields": FIELDS if fields is None else fields,
        "tags": ["container"], "hostname": hostname})


def _event(ts, rule=RULE, priority="Critical", fields=None):
    return {"ts": ts, "rule": rule, "priority": priority,
            "output": "an output line",
            "output_fields": dict(FIELDS if fields is None else fields),
            "hostname": "pi-box"}


def _readings(events, now=None):
    events = list(events)
    return {"now": events[-1]["ts"] if now is None and events else now,
            "events": events}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "falco_feed")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual([s["name"] for s in clean["signals"]],
                         ["falco_critical", "falco_warning"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        self.assertEqual(clean["tunables"]["log_paths"],
                         ["/var/log/falco/falco.json"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "falco-feed"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("falco_feed", registry)

    def test_manifest_signals_match_the_readme_list(self):
        with open(os.path.join(EXAMPLE_DIR, "README.md"),
                  encoding="utf-8") as fh:
            readme = fh.read()
        for signal in ("falco_critical", "falco_warning"):
            self.assertIn(f"`{signal}`", readme)


class ParseEventTest(unittest.TestCase):
    def test_critical_line_parses_with_its_episode_digest(self):
        ev = FF.parse_event(_line())
        self.assertEqual(ev["rule"], RULE)
        self.assertEqual(ev["priority"], "Critical")
        self.assertEqual(ev["signal"], "falco_critical")
        self.assertEqual(ev["hostname"], "pi-box")
        self.assertEqual(ev["output_fields"], FIELDS)
        # The digest is a function of the fields' content, not
        # of their serialization order.
        shuffled = dict(reversed(list(FIELDS.items())))
        self.assertEqual(FF.parse_event(_line(fields=shuffled))
                         ["fields_digest"], ev["fields_digest"])

    def test_all_critical_family_priorities_map_high(self):
        for priority in ("Emergency", "Alert", "Critical", "Error"):
            ev = FF.parse_event(_line(priority=priority))
            self.assertEqual(ev["signal"], "falco_critical", priority)

    def test_every_documented_priority_is_accounted_for(self):
        # Falco documents eight priority names; each must
        # parse to an event (none may fall into the malformed
        # bucket reserved for names outside the eight).
        for priority in ("Emergency", "Alert", "Critical",
                         "Error", "Warning", "Notice",
                         "Informational", "Debug"):
            self.assertIsNotNone(
                FF.parse_event(_line(priority=priority)), priority)

    def test_warning_and_notice_map_to_the_warning_signal(self):
        for priority in ("Warning", "Notice"):
            ev = FF.parse_event(_line(priority=priority))
            self.assertEqual(ev["signal"], "falco_warning", priority)

    def test_informational_and_debug_parse_but_carry_no_signal(self):
        for priority in ("Informational", "Debug"):
            ev = FF.parse_event(_line(priority=priority))
            self.assertIsNotNone(ev, priority)
            self.assertIsNone(ev["signal"], priority)

    def test_nanosecond_and_offset_timestamps_parse(self):
        ev = FF.parse_event(_line(ts="2026-10-18T12:00:01.5-07:00"))
        self.assertEqual(ev["ts"], datetime(
            2026, 10, 18, 19, 0, 1, 500000,
            tzinfo=timezone.utc).timestamp())
        ev = FF.parse_event(_line(ts="2026-10-18T12:00:01+0000"))
        self.assertEqual(ev["ts"], T0 + 1)

    def test_malformed_lines_answer_none(self):
        bad = ["", "not json", "[1, 2]", "{}",
               _line(rule=""), _line(priority="Severe"),
               _line(ts="yesterday-ish"),
               json.dumps({"rule": RULE, "priority": "Critical"})]
        for line in bad:
            self.assertIsNone(FF.parse_event(line), line)

    def test_synthetic_fixture_parses_five_events(self):
        with open(FIXTURE, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        events = [FF.parse_event(ln) for ln in lines]
        parsed = [ev for ev in events if ev is not None]
        self.assertEqual(len(lines), 6)  # one line is truncated
        self.assertEqual(len(parsed), 5)
        self.assertEqual([ev["signal"] for ev in parsed],
                         ["falco_critical", "falco_warning",
                          "falco_critical", None, "falco_critical"])


class ReaderTest(unittest.TestCase):
    def test_tails_incrementally_and_keeps_missing_offsets(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "falco.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_line() + "\n")
                fh.write(_line(priority="Warning") + "\n")
            events, reader = FF.read_new_events([path], {})
            self.assertEqual(len(events), 2)
            self.assertEqual(reader[path]["offset"],
                             os.path.getsize(path))
            events, reader = FF.read_new_events([path], reader)
            self.assertEqual(events, [])
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(_line(priority="Notice") + "\n")
            events, reader = FF.read_new_events([path], reader)
            self.assertEqual(len(events), 1)
            missing = os.path.join(d, "nope.json")
            kept = {missing: {"inode": 4242, "offset": 99}}
            events, new_reader = FF.read_new_events([missing], kept)
            self.assertEqual(events, [])
            self.assertEqual(new_reader[missing],
                             {"inode": 4242, "offset": 99})

    def test_inode_change_and_shrink_restart_from_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "falco.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_line() + "\n")
            _events, reader = FF.read_new_events([path], {})
            # Rotation: a different file lands at the same path.
            other = os.path.join(d, "falco.json.1")
            with open(other, "w", encoding="utf-8") as fh:
                fh.write(_line(priority="Warning") + "\n")
                fh.write(_line(priority="Notice") + "\n")
            os.replace(other, path)
            events, reader = FF.read_new_events([path], reader)
            self.assertEqual(len(events), 2)
            # Truncation in place: smaller than the saved offset.
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_line(priority="Alert") + "\n")
            events, _reader = FF.read_new_events([path], reader)
            self.assertEqual(len(events), 1)


class DecideTest(unittest.TestCase):
    def decide(self, readings, state=None, manifest=None):
        return FF.decide(readings, manifest or _manifest(),
                         state if state is not None else {})

    def test_critical_files_high_with_key_details(self):
        alerts, state = self.decide(_readings([_event(T0)]))
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "falco_feed")
        self.assertEqual(alert["signal"], "falco_critical")
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["detail"]["rule"], RULE)
        self.assertEqual(alert["detail"]["priority"], "Critical")
        self.assertEqual(alert["detail"]["hostname"], "pi-box")
        self.assertEqual(alert["detail"]["output_fields"], FIELDS)
        self.assertTrue(alert["detail"]["output_fields_digest"])
        self.assertEqual(len(state["episodes"]), 1)

    def test_warning_files_medium(self):
        alerts, _state = self.decide(
            _readings([_event(T0, priority="Notice")]))
        self.assertEqual([(a["signal"], a["severity"]) for a in alerts],
                         [("falco_warning", "medium")])

    def test_parsed_only_priorities_never_file(self):
        events = [_event(T0, priority="Informational"),
                  _event(T0 + 1, priority="Debug")]
        alerts, state = self.decide(_readings(events))
        self.assertEqual(alerts, [])
        self.assertEqual(state["episodes"], {})

    def test_same_episode_files_once_while_steady(self):
        readings = _readings([_event(T0 + i * 10) for i in range(4)])
        alerts, state = self.decide(readings)
        self.assertEqual(len(alerts), 1)
        alerts, _state = self.decide(readings, state=state)
        self.assertEqual(alerts, [])

    def test_new_fields_for_the_same_rule_file_a_new_episode(self):
        other = {"container.id": "def456", "proc.name": "sh",
                 "user.name": "root"}
        events = [_event(T0), _event(T0 + 10, fields=other)]
        alerts, state = self.decide(_readings(events))
        self.assertEqual(len(alerts), 2)
        self.assertEqual(len(state["episodes"]), 2)

    def test_episode_refiles_after_the_cooldown(self):
        alerts, state = self.decide(_readings([_event(T0)]))
        self.assertEqual(len(alerts), 1)
        later = T0 + 3600
        alerts, _state = self.decide(_readings([_event(later)]),
                                     state=state)
        self.assertEqual(len(alerts), 1)

    def test_episode_clears_when_quiet_then_refiles_on_return(self):
        alerts, state = self.decide(_readings([_event(T0)]))
        self.assertEqual(len(alerts), 1)
        alerts, state = self.decide({"now": T0 + 7200, "events": []},
                                    state=state)
        self.assertEqual(alerts, [])
        self.assertEqual(state["episodes"], {})
        alerts, _state = self.decide(_readings([_event(T0 + 7201)]),
                                     state=state)
        self.assertEqual(len(alerts), 1)

    def test_events_are_processed_in_timestamp_order(self):
        other = {"container.id": "def456", "proc.name": "sh",
                 "user.name": "root"}
        events = [_event(T0 + 10, fields=other), _event(T0)]
        alerts, _state = self.decide(_readings(events))
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0]["detail"]["output_fields"], FIELDS)

    def test_reader_subdict_is_preserved_and_ignored(self):
        kept = {"/var/log/falco/falco.json": {"inode": 7, "offset": 42}}
        alerts, new_state = self.decide(_readings([_event(T0)]),
                                        state={"_reader": kept})
        self.assertEqual(len(alerts), 1)
        self.assertEqual(new_state["_reader"], kept)

    def test_unusable_events_are_ignored(self):
        readings = {"now": T0, "events": [
            None, {}, {"ts": "x", "rule": RULE, "priority": "Critical"},
            {"ts": T0, "rule": "", "priority": "Critical"},
            {"ts": T0, "rule": RULE, "priority": "Severe"}]}
        alerts, _state = self.decide(readings)
        self.assertEqual(alerts, [])


class MainTest(unittest.TestCase):
    def test_log_file_fixture_files_three_alerts(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = FF.main(["--log-file", FIXTURE,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["falco_critical", "falco_warning",
                              "falco_critical"])
            self.assertEqual(
                FF.main(["--log-file", os.path.join(d, "missing.json"),
                         "--state", state_path]), 2)
            with open(os.path.join(d, "bad.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("not json")
            self.assertEqual(
                FF.main(["--readings", os.path.join(d, "bad.json"),
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
                rc = FF.main(["--log-file", FIXTURE,
                              "--state", state_path,
                              "--local-dir", d])
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state_path))


if __name__ == "__main__":
    unittest.main()
