"""Osquery Feed: the example sense that tails osquery results.

Pins the Osquery Feed example
(examples/extensions/osquery-feed/): the manifest through
the real extension loader, the query-name-to-kind mapping
(the light pack's hp_ names and the bare stock names map;
unknown query names are parsed and ignored), the pure
parse_event() and read_new_events() reader plumbing, and the
pure decide() episode machine -- an add files once per
(kind, action, identity), a remove of the same identity is a
new episode fact and files, and it re-arms the add.

No live osquery anywhere: decide() is driven with fixture
event readings, and the reader is driven with temp files and
the shipped fixtures.
"""

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "examples", "extensions", "osquery-feed")
FIXTURES = os.path.join(EXAMPLE_DIR, "fixtures")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "osquery_feed_example", os.path.join(EXAMPLE_DIR, "osquery_feed.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OF = _load_example_module()

T0 = 1792382200


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _line(name="hp_processes", ts=T0, columns=None, action="added"):
    if columns is None:
        columns = {"name": "sshd", "path": "/usr/sbin/sshd", "pid": "812"}
    return json.dumps(
        {
            "name": name,
            "hostIdentifier": "fixture-host",
            "unixTime": ts,
            "columns": columns,
            "action": action,
        }
    )


def _event(name="hp_processes", ts=T0, columns=None, action="added"):
    return OF.parse_event(_line(name, ts, columns, action))


def _readings(events, now=None):
    events = list(events)
    return {
        "now": events[-1]["ts"] if now is None and events else now,
        "events": events,
    }


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "osquery_feed")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            [s["name"] for s in clean["signals"]], ["osquery_added", "osquery_removed"]
        )
        self.assertIn("poll_interval_sec", clean["tunables"])
        self.assertEqual(
            clean["tunables"]["log_paths"], ["/var/log/osquery/osqueryd.results.log"]
        )
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "osquery-feed"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("osquery_feed", registry)


class QueryKindTest(unittest.TestCase):
    def test_light_pack_and_stock_names_map(self):
        for name, kind in (
            ("hp_processes", "process"),
            ("processes", "process"),
            ("hp_users", "user"),
            ("users", "user"),
            ("hp_listening_ports", "listener"),
            ("listening_ports", "listener"),
        ):
            self.assertEqual(OF.query_kind(name), kind, name)

    def test_unknown_names_map_to_none(self):
        for name in ("some_other_pack_query", "osquery_info", "", None):
            self.assertIsNone(OF.query_kind(name), name)


class ParseEventTest(unittest.TestCase):
    def test_process_line_from_the_captured_sample(self):
        with open(
            os.path.join(FIXTURES, "osquery-results.jsonl"), encoding="utf-8"
        ) as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 2)
        ev = OF.parse_event(lines[0])
        self.assertEqual(ev["kind"], "process")
        self.assertEqual(ev["action"], "added")
        self.assertEqual(ev["ts"], 1792382120.0)
        self.assertEqual(
            ev["identity"],
            {"name": "systemd", "path": "/usr/lib/systemd/systemd", "pid": "1"},
        )

    def test_user_and_listener_identities(self):
        ev = _event(
            "hp_users",
            columns={
                "username": "deploy",
                "uid": "1001",
                "gid": "1001",
                "shell": "/bin/bash",
            },
        )
        self.assertEqual(ev["kind"], "user")
        self.assertEqual(
            ev["identity"], {"username": "deploy", "uid": "1001", "gid": "1001"}
        )
        ev = _event(
            "hp_listening_ports",
            columns={
                "port": "8080",
                "protocol": "6",
                "address": "0.0.0.0",
                "pid": "812",
                "family": "2",
            },
        )
        self.assertEqual(ev["kind"], "listener")
        self.assertEqual(
            ev["identity"],
            {"port": "8080", "protocol": "6", "address": "0.0.0.0", "pid": "812"},
        )

    def test_unknown_query_parses_but_is_ignored(self):
        ev = OF.parse_event(_line("some_other_pack_query", columns={"whatever": "x"}))
        self.assertIsNotNone(ev)
        self.assertIsNone(ev["kind"])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "results.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(
                    _line("some_other_pack_query", columns={"whatever": "x"}) + "\n"
                )
                fh.write(_line() + "\n")
            events, _reader = OF.read_new_events([path], {})
        self.assertEqual([e["query"] for e in events], ["hp_processes"])

    def test_malformed_lines_are_quiet(self):
        bad = [
            "",
            "not json",
            "[1, 2]",
            '{"name": "hp_processes"}',
            _line(action="changed"),
            _line(ts="soon"),
            json.dumps(
                {
                    "name": "hp_processes",
                    "unixTime": T0,
                    "columns": ["not", "a", "dict"],
                    "action": "added",
                }
            ),
            json.dumps({"name": "", "unixTime": T0, "columns": {}, "action": "added"}),
        ]
        for line in bad:
            self.assertIsNone(OF.parse_event(line), line)
        self.assertIsNone(OF.parse_event(None))


class ReaderTest(unittest.TestCase):
    def test_tails_incrementally_and_keeps_missing_offsets(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "osqueryd.results.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_line(ts=T0) + "\n")
                fh.write(_line(ts=T0 + 60) + "\n")
            events, reader = OF.read_new_events([path], {})
            self.assertEqual(len(events), 2)
            self.assertEqual(reader[path]["offset"], os.path.getsize(path))
            events, reader = OF.read_new_events([path], reader)
            self.assertEqual(events, [])
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(_line(ts=T0 + 120) + "\n")
            events, reader = OF.read_new_events([path], reader)
            self.assertEqual(len(events), 1)
            missing = os.path.join(d, "nope.log")
            kept = {missing: {"inode": 4242, "offset": 99}}
            events, new_reader = OF.read_new_events([missing], kept)
            self.assertEqual(events, [])
            self.assertEqual(new_reader[missing], {"inode": 4242, "offset": 99})

    def test_shrunk_file_restarts_from_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "osqueryd.results.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_line(ts=T0) + "\n")
                fh.write(_line(ts=T0 + 60) + "\n")
            _events, reader = OF.read_new_events([path], {})
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_line(ts=T0 + 120) + "\n")
            events, _reader = OF.read_new_events([path], reader)
            self.assertEqual(len(events), 1)


class DecideTest(unittest.TestCase):
    def decide(self, readings, state=None, manifest=None):
        return OF.decide(
            readings, manifest or _manifest(), state if state is not None else {}
        )

    def test_process_added_files_info_with_identity_detail(self):
        alerts, _state = self.decide(_readings([_event()]))
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "osquery_feed")
        self.assertEqual(alert["signal"], "osquery_added")
        self.assertEqual(alert["severity"], "info")
        self.assertEqual(alert["detail"]["kind"], "process")
        self.assertEqual(alert["detail"]["name"], "sshd")
        self.assertEqual(alert["detail"]["pid"], "812")
        self.assertEqual(alert["detail"]["path"], "/usr/sbin/sshd")

    def test_user_and_listener_added_file_medium(self):
        user = _event(
            "hp_users", columns={"username": "deploy", "uid": "1001", "gid": "1001"}
        )
        listener = _event(
            "hp_listening_ports",
            ts=T0 + 60,
            columns={
                "port": "8080",
                "protocol": "6",
                "address": "0.0.0.0",
                "pid": "812",
            },
        )
        alerts, _state = self.decide(_readings([user, listener]))
        self.assertEqual([a["severity"] for a in alerts], ["medium", "medium"])
        self.assertEqual(alerts[0]["detail"]["username"], "deploy")
        self.assertEqual(alerts[1]["detail"]["port"], "8080")
        self.assertEqual(alerts[1]["detail"]["protocol"], "6")
        self.assertEqual(alerts[1]["detail"]["address"], "0.0.0.0")

    def test_removed_files_info(self):
        alerts, _state = self.decide(_readings([_event(action="removed")]))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["signal"], "osquery_removed")
        self.assertEqual(alerts[0]["severity"], "info")
        self.assertEqual(alerts[0]["detail"]["kind"], "process")

    def test_same_add_twice_files_once_until_the_remove(self):
        add = _event()
        readings = _readings([add, dict(add, ts=T0 + 60)])
        alerts, state = self.decide(readings)
        self.assertEqual(len(alerts), 1)
        alerts, state = self.decide(_readings([add]), state=state)
        self.assertEqual(alerts, [])
        # The remove is a new episode fact: it files, and it
        # re-arms the add, so the return of the same process
        # files as added again.
        remove = _event(ts=T0 + 120, action="removed")
        alerts, state = self.decide(_readings([remove]), state=state)
        self.assertEqual([a["signal"] for a in alerts], ["osquery_removed"])
        alerts, _state = self.decide(_readings([_event(ts=T0 + 180)]), state=state)
        self.assertEqual([a["signal"] for a in alerts], ["osquery_added"])

    def test_identities_are_distinct_episodes(self):
        one = _event()
        two = _event(
            ts=T0 + 60, columns={"name": "sshd", "path": "/usr/sbin/sshd", "pid": "913"}
        )
        alerts, _state = self.decide(_readings([one, two]))
        self.assertEqual(len(alerts), 2)

    def test_unknown_kind_events_are_quiet(self):
        ev = OF.parse_event(_line("some_other_pack_query", columns={"whatever": "x"}))
        alerts, _state = self.decide(_readings([ev]))
        self.assertEqual(alerts, [])

    def test_hand_built_events_derive_kind_from_query_name(self):
        # A readings fixture that names the query but carries
        # no kind still files, via the same mapping.
        ev = {
            "ts": T0,
            "action": "added",
            "query": "users",
            "columns": {"username": "root", "uid": "0", "gid": "0"},
        }
        alerts, _state = self.decide(_readings([ev]))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["detail"]["kind"], "user")
        self.assertEqual(alerts[0]["severity"], "medium")

    def test_reader_subdict_is_preserved_and_ignored(self):
        path = "/var/log/osquery/osqueryd.results.log"
        state = {"filed": [], "_reader": {path: {"inode": 7, "offset": 42}}}
        alerts, new_state = self.decide(_readings([_event()]), state=state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(new_state["_reader"], {path: {"inode": 7, "offset": 42}})

    def test_unusable_events_are_ignored(self):
        readings = {
            "now": T0,
            "events": [
                None,
                {},
                {"ts": "x", "action": "added", "query": "users"},
                {"ts": T0, "action": "changed", "query": "users"},
                {"ts": T0, "action": "added", "query": "users", "columns": {}},
            ],
        }
        alerts, _state = self.decide(readings)
        self.assertEqual(alerts, [])


class MainTest(unittest.TestCase):
    def test_light_pack_fixture_files_adds_and_the_remove(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = OF.main(
                    [
                        "--log-file",
                        os.path.join(FIXTURES, "light-pack.jsonl"),
                        "--state",
                        state_path,
                    ]
                )
            self.assertEqual(rc, 0)
            printed = [
                json.loads(ln) for ln in out.getvalue().splitlines() if ln.strip()
            ]
            self.assertEqual(
                [(p["signal"], p["detail"]["kind"]) for p in printed],
                [
                    ("osquery_added", "process"),
                    ("osquery_added", "user"),
                    ("osquery_added", "listener"),
                    ("osquery_removed", "listener"),
                ],
            )
            self.assertEqual(
                OF.main(
                    [
                        "--log-file",
                        os.path.join(d, "missing.log"),
                        "--state",
                        state_path,
                    ]
                ),
                2,
            )
            with open(os.path.join(d, "bad.json"), "w", encoding="utf-8") as fh:
                fh.write("not json")
            self.assertEqual(
                OF.main(
                    ["--readings", os.path.join(d, "bad.json"), "--state", state_path]
                ),
                2,
            )

    def test_live_pass_with_missing_logs_is_a_quiet_rc0(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = _manifest()
            manifest["tunables"]["log_paths"] = [
                os.path.join(d, "osqueryd.results.log")
            ]
            manifest_path = os.path.join(d, "extension.json")
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            state_path = os.path.join(d, "state.json")
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                rc = OF.main(["--manifest", manifest_path, "--state", state_path])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")
            with open(state_path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["_reader"], {})

    def _readings_file(self, d):
        path = os.path.join(d, "readings.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                _readings(
                    [
                        _event(
                            "hp_users",
                            columns={
                                "username": "deploy",
                                "uid": "1001",
                                "gid": "1001",
                            },
                        )
                    ]
                ),
                fh,
            )
        return path

    def test_local_delivery_drops_a_signed_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            with mock.patch.dict(
                os.environ, {"HOMING_PIGEON_SENSOR_SECRET": "test-secret"}
            ):
                with redirect_stderr(io.StringIO()):
                    rc = OF.main(
                        [
                            "--readings",
                            self._readings_file(d),
                            "--state",
                            state_path,
                            "--local-dir",
                            d,
                        ]
                    )
            self.assertEqual(rc, 0)
            inbox = os.path.join(d, "local-inbox")
            dropped = os.listdir(inbox)
            self.assertEqual(len(dropped), 1)
            with open(os.path.join(inbox, dropped[0]), encoding="utf-8") as fh:
                envelope = json.loads(fh.read())
            self.assertEqual(envelope["signal"], "osquery_added")
            self.assertIn("sig", envelope)
            self.assertTrue(os.path.exists(state_path))

    def test_failed_delivery_leaves_the_state_unwritten(self):
        with tempfile.TemporaryDirectory() as d:
            # A regular file where the inbox directory belongs
            # makes every drop fail.
            with open(os.path.join(d, "local-inbox"), "w", encoding="utf-8") as fh:
                fh.write("not a directory")
            state_path = os.path.join(d, "state.json")
            with mock.patch.dict(
                os.environ, {"HOMING_PIGEON_SENSOR_SECRET": "test-secret"}
            ):
                with redirect_stderr(io.StringIO()):
                    rc = OF.main(
                        [
                            "--readings",
                            self._readings_file(d),
                            "--state",
                            state_path,
                            "--local-dir",
                            d,
                        ]
                    )
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state_path))

    def test_same_add_fixture_twice_files_once(self):
        with tempfile.TemporaryDirectory() as d:
            log_path = os.path.join(d, "results.log")
            state_path = os.path.join(d, "state.json")
            with open(log_path, "w", encoding="utf-8") as fh:
                fh.write(_line() + "\n")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(
                    OF.main(["--log-file", log_path, "--state", state_path]), 0
                )
            self.assertEqual(len(out.getvalue().splitlines()), 1)
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(
                    OF.main(["--log-file", log_path, "--state", state_path]), 0
                )
            self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
