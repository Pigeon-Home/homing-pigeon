"""Zeek Feed: the example sense that tails Zeek logs.

Pins the Zeek Feed example (examples/extensions/zeek-feed/):
the manifest through the real extension loader, the
header-driven TSV parser (headers can reappear mid-file and
reorder the columns; JSON-lines output parses with the same
field names), the read_new_events() reader plumbing with
each file's field list carried in its reader entry, and the
pure decide() episode machine -- a threshold of distinct
first-seen external responders files once, private and
allowlisted responders never count, seen-peer memory is
bounded, and a DNS anomaly files once per (query,
responder).

No live Zeek anywhere: decide() is driven with fixture
event readings, and the reader is driven with temp files
and the shipped fixtures.
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

EXAMPLE_DIR = os.path.join(REPO, "examples", "extensions", "zeek-feed")
FIXTURES = os.path.join(EXAMPLE_DIR, "fixtures")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "zeek_feed_example", os.path.join(EXAMPLE_DIR, "zeek_feed.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ZF = _load_example_module()

T0 = 1792382500.0


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _conn(ts, resp_h, orig_h="192.168.1.20"):
    return {"ts": ts, "kind": "conn", "resp_h": resp_h, "orig_h": orig_h}


def _dns(ts, query, qtype_name="A", resp_h="8.8.8.8"):
    return {
        "ts": ts,
        "kind": "dns",
        "query": query,
        "qtype_name": qtype_name,
        "resp_h": resp_h,
        "orig_h": "192.168.1.20",
    }


def _peer(i):
    # 45.33.32.0/24 is globally routable space; the ipaddress
    # module does not call it private (documentation ranges
    # like 192.0.2.0/24 it does, so they cannot play the
    # external peer in a fixture).
    return f"45.33.32.{i + 1}"


def _peers(ts0, count):
    return [_conn(ts0 + i * 10, _peer(i)) for i in range(count)]


def _readings(events, now=None):
    events = list(events)
    return {
        "now": events[-1]["ts"] if now is None and events else now,
        "events": events,
    }


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "zeek_feed")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            [s["name"] for s in clean["signals"]],
            ["zeek_new_external_peers", "zeek_dns_anomaly"],
        )
        self.assertIn("poll_interval_sec", clean["tunables"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "zeek-feed"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("zeek_feed", registry)


class ParseEventTest(unittest.TestCase):
    def test_fields_header_answers_the_new_field_list(self):
        ev = ZF.parse_event("#fields\tts\tuid\tid.resp_h")
        self.assertEqual(ev, {"kind": "_fields", "fields": ["ts", "uid", "id.resp_h"]})
        self.assertIsNone(ZF.parse_event("#types\ttime\tstring\taddr"))
        self.assertIsNone(ZF.parse_event("#path\tconn"))

    def test_tsv_conn_row_parses_against_the_fields_in_force(self):
        fields = ["ts", "uid", "id.orig_h", "id.resp_h", "proto"]
        ev = ZF.parse_event("1792382500.5\tC1\t192.168.1.20\t45.33.32.1\ttcp", fields)
        self.assertEqual(ev["kind"], "conn")
        self.assertEqual(ev["resp_h"], "45.33.32.1")
        self.assertEqual(ev["ts"], 1792382500.5)

    def test_mid_file_header_change_reorders_the_columns(self):
        # Rotation restates the headers in a different order;
        # the row after it parses against the NEW list, not
        # the one the file started with.
        lines = [
            "#fields\tts\tid.resp_h\tid.orig_h",
            "1000.0\t45.33.32.1\t192.168.1.20",
            "#fields\tts\tid.orig_h\tid.resp_h",
            "1001.0\t192.168.1.21\t45.33.32.2",
        ]
        fields = None
        events = []
        for line in lines:
            ev = ZF.parse_event(line, fields)
            if ev and ev["kind"] == "_fields":
                fields = ev["fields"]
            elif ev:
                events.append(ev)
        self.assertEqual([e["resp_h"] for e in events], ["45.33.32.1", "45.33.32.2"])
        self.assertEqual(events[1]["orig_h"], "192.168.1.21")

    def test_json_line_variant_uses_the_same_field_names(self):
        with open(os.path.join(FIXTURES, "zeek-json.log"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        conn = ZF.parse_event(lines[0])
        self.assertEqual(conn["kind"], "conn")
        self.assertEqual(conn["resp_h"], "93.184.216.34")
        dns = ZF.parse_event(lines[1])
        self.assertEqual(dns["kind"], "dns")
        self.assertEqual(dns["query"], "example.com")
        self.assertEqual(dns["qtype_name"], "A")

    def test_dns_fixture_rows_parse_with_documented_fields(self):
        events, _reader = ZF.read_new_events([os.path.join(FIXTURES, "dns.log")], {})
        self.assertEqual(len(events), 4)
        self.assertTrue(all(e["kind"] == "dns" for e in events))
        self.assertEqual(events[0]["query"], "example.com")
        self.assertEqual(events[2]["qtype_name"], "TXT")

    def test_conn_fixture_rows_parse(self):
        events, _reader = ZF.read_new_events([os.path.join(FIXTURES, "conn.log")], {})
        self.assertEqual(len(events), 2)
        self.assertTrue(all(e["kind"] == "conn" for e in events))
        self.assertTrue(events[0]["resp_h"].startswith("fd8b:"))

    def test_malformed_lines_are_quiet(self):
        fields = ["ts", "id.resp_h"]
        for line in (
            "",
            "not zeek at all",
            "{bad json",
            '{"no_ts": true}',
            "1792382500.5",  # too few columns
            "1792382500.5\t45.33.32.1\textra",  # too many
            "not-a-ts\t45.33.32.1",
        ):
            self.assertIsNone(ZF.parse_event(line, fields), line)
        # A data line before any header has nothing to parse
        # against.
        self.assertIsNone(ZF.parse_event("1792382500.5\t45.33.32.1"))
        self.assertIsNone(ZF.parse_event(None, fields))


class ReaderTest(unittest.TestCase):
    HEADER = "#fields\tts\tid.orig_h\tid.resp_h\n"
    ROW = "%.1f\t192.168.1.20\t45.33.32.%d\n"

    def test_tails_incrementally_and_fields_ride_along(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "conn.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.HEADER)
                fh.write(self.ROW % (1000.0, 1))
            events, reader = ZF.read_new_events([path], {})
            self.assertEqual(len(events), 1)
            self.assertEqual(reader[path]["offset"], os.path.getsize(path))
            self.assertEqual(reader[path]["fields"], ["ts", "id.orig_h", "id.resp_h"])
            events, reader = ZF.read_new_events([path], reader)
            self.assertEqual(events, [])
            # An appended data line carries no header: it only
            # parses because the reader state kept the fields.
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(self.ROW % (1001.0, 2))
            events, reader = ZF.read_new_events([path], reader)
            self.assertEqual([e["resp_h"] for e in events], ["45.33.32.2"])
            # A missing file yields nothing and keeps its entry.
            missing = os.path.join(d, "nope.log")
            kept = {missing: {"inode": 4242, "offset": 99, "fields": ["ts"]}}
            events, new_reader = ZF.read_new_events([missing], kept)
            self.assertEqual(events, [])
            self.assertEqual(
                new_reader[missing], {"inode": 4242, "offset": 99, "fields": ["ts"]}
            )

    def test_shrunk_file_restarts_from_zero_and_rereads_headers(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "conn.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.HEADER)
                fh.write(self.ROW % (1000.0, 1))
                fh.write(self.ROW % (1001.0, 2))
            _events, reader = ZF.read_new_events([path], {})
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.HEADER)
                fh.write(self.ROW % (1002.0, 9))
            events, _reader = ZF.read_new_events([path], reader)
            self.assertEqual([e["resp_h"] for e in events], ["45.33.32.9"])


class DecidePeersTest(unittest.TestCase):
    def decide(self, readings, state=None, manifest=None):
        return ZF.decide(
            readings, manifest or _manifest(), state if state is not None else {}
        )

    def test_threshold_files_once_medium_with_key_details(self):
        alerts, state = self.decide(_readings(_peers(T0, 10)))
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "zeek_feed")
        self.assertEqual(alert["signal"], "zeek_new_external_peers")
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"]["count"], 10)
        self.assertEqual(alert["detail"]["threshold"], 10)
        self.assertEqual(alert["detail"]["window_sec"], 600)
        self.assertEqual(alert["detail"]["peers"], sorted(_peer(i) for i in range(10)))
        self.assertEqual(len(state["seen_peers"]), 10)

    def test_below_threshold_is_quiet(self):
        alerts, _state = self.decide(_readings(_peers(T0, 9)))
        self.assertEqual(alerts, [])

    def test_same_peers_twice_are_not_new_twice(self):
        readings = _readings(_peers(T0, 10))
        alerts, state = self.decide(readings)
        self.assertEqual(len(alerts), 1)
        alerts, _state = self.decide(readings, state=state)
        self.assertEqual(alerts, [])
        # A repeat sighting of one peer plus nine fresh ones
        # is only nine new peers: still quiet.
        events = [_conn(T0 + 500, _peer(0))] + [
            _conn(T0 + 510 + i * 10, _peer(20 + i)) for i in range(9)
        ]
        alerts, _state = self.decide(_readings(events), state=state)
        self.assertEqual(alerts, [])

    def test_refile_needs_a_fresh_batch_of_new_peers(self):
        alerts, state = self.decide(_readings(_peers(T0, 10)))
        self.assertEqual(len(alerts), 1)
        fresh = [_conn(T0 + 1000 + i * 10, _peer(30 + i)) for i in range(10)]
        alerts, _state = self.decide(_readings(fresh), state=state)
        self.assertEqual([a["signal"] for a in alerts], ["zeek_new_external_peers"])

    def test_non_external_responders_never_count(self):
        hosts = [
            "10.0.0.5",
            "192.168.1.1",
            "127.0.0.1",
            "::1",
            "169.254.1.1",
            "fe80::1",
            "224.0.0.1",
            "ff02::1",
            "192.0.2.10",
            "not-an-ip",
            "",
        ]
        events = [_conn(T0 + i * 10, h) for i, h in enumerate(hosts)]
        alerts, state = self.decide(_readings(events))
        self.assertEqual(alerts, [])
        self.assertEqual(state["seen_peers"], [])

    def test_allowlist_exact_and_cidr_never_count(self):
        manifest = _manifest()
        manifest["tunables"]["allowlist"] = ["45.33.32.1", "45.33.33.0/24"]
        events = [_conn(T0, "45.33.32.1"), _conn(T0 + 10, "45.33.33.9")]
        events += _peers(T0 + 20, 9)
        alerts, _state = self.decide(_readings(events), manifest=manifest)
        self.assertEqual(alerts, [])

    def test_sightings_spread_beyond_the_window_never_reach(self):
        events = [_conn(T0 + i * 300, _peer(i)) for i in range(10)]
        alerts, _state = self.decide(_readings(events))
        self.assertEqual(alerts, [])

    def test_seen_peer_memory_is_bounded(self):
        manifest = _manifest()
        manifest["tunables"]["seen_peers_cap"] = 3
        manifest["tunables"]["new_peer_threshold"] = 99
        events = [_conn(T0 + i * 10, _peer(i)) for i in range(6)]
        alerts, state = self.decide(_readings(events), manifest=manifest)
        self.assertEqual(alerts, [])
        self.assertEqual(state["seen_peers"], [_peer(3), _peer(4), _peer(5)])
        # The evicted oldest peer counts as first-seen again:
        # that is the honest price of the bounded memory.
        manifest["tunables"]["new_peer_threshold"] = 1
        alerts, _state = self.decide(
            _readings([_conn(T0 + 100, _peer(0))]), state=state, manifest=manifest
        )
        self.assertEqual([a["signal"] for a in alerts], ["zeek_new_external_peers"])


class DecideDnsTest(unittest.TestCase):
    def decide(self, readings, state=None, manifest=None):
        return ZF.decide(
            readings, manifest or _manifest(), state if state is not None else {}
        )

    def test_long_query_files_medium(self):
        query = "a" * 40 + ".example.com"  # 52 chars, 3 labels
        alerts, _state = self.decide(_readings([_dns(T0, query)]))
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["signal"], "zeek_dns_anomaly")
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"]["reason"], "long_query")
        self.assertEqual(alert["detail"]["query"], query)
        self.assertEqual(alert["detail"]["resp_h"], "8.8.8.8")

    def test_suspicious_qtypes_file(self):
        for qtype in ("TXT", "NULL", "KEY", "ANY"):
            with self.subTest(qtype=qtype):
                alerts, _state = self.decide(
                    _readings([_dns(T0, "notes.example.org", qtype)])
                )
                self.assertEqual(len(alerts), 1)
                self.assertEqual(alerts[0]["detail"]["reason"], "suspicious_qtype")

    def test_many_labels_file(self):
        alerts, _state = self.decide(_readings([_dns(T0, "a.b.c.d.e.example.com")]))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["detail"]["reason"], "many_labels")

    def test_ordinary_queries_are_quiet(self):
        events = [
            _dns(T0, "example.com"),
            _dns(T0 + 1, "www.example.org"),
            _dns(T0 + 2, "a.b.c.example.com"),  # 5 labels
            _dns(T0 + 3, ""),
        ]
        alerts, _state = self.decide(_readings(events))
        self.assertEqual(alerts, [])

    def test_anomaly_files_once_per_query_and_responder(self):
        query = "notes.example.org"
        events = [_dns(T0, query, "TXT"), _dns(T0 + 10, query, "TXT")]
        alerts, state = self.decide(_readings(events))
        self.assertEqual(len(alerts), 1)
        # The same query through a different responder is a
        # new episode and files again.
        events = [_dns(T0 + 20, query, "TXT", resp_h="9.9.9.9")]
        alerts, _state = self.decide(_readings(events), state=state)
        self.assertEqual(len(alerts), 1)

    def test_reader_subdict_is_preserved_and_ignored(self):
        reader = {
            "/opt/zeek/logs/current/conn.log": {
                "inode": 7,
                "offset": 42,
                "fields": ["ts"],
            }
        }
        state = {"seen_peers": [], "new_peers": [], "dns_filed": [], "_reader": reader}
        alerts, new_state = self.decide(
            _readings([_dns(T0, "notes.example.org", "TXT")]), state=state
        )
        self.assertEqual(len(alerts), 1)
        self.assertEqual(new_state["_reader"], reader)

    def test_unusable_events_are_ignored(self):
        readings = {
            "now": T0,
            "events": [
                None,
                {},
                {"ts": "x", "kind": "conn", "resp_h": _peer(0)},
                {"ts": T0, "kind": "http", "resp_h": _peer(0)},
                {"ts": T0, "kind": "conn", "resp_h": ""},
            ],
        }
        alerts, _state = self.decide(readings)
        self.assertEqual(alerts, [])


class MainTest(unittest.TestCase):
    def test_dns_fixture_files_its_three_anomalies(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = ZF.main(
                    [
                        "--log-file",
                        os.path.join(FIXTURES, "dns.log"),
                        "--state",
                        state_path,
                    ]
                )
            self.assertEqual(rc, 0)
            printed = [
                json.loads(ln) for ln in out.getvalue().splitlines() if ln.strip()
            ]
            self.assertEqual([p["signal"] for p in printed], ["zeek_dns_anomaly"] * 3)
            self.assertEqual(
                sorted(p["detail"]["reason"] for p in printed),
                ["long_query", "many_labels", "suspicious_qtype"],
            )
            # A second pass over the same fixture files
            # nothing: the episodes are in the saved state.
            out = io.StringIO()
            with redirect_stdout(out):
                rc = ZF.main(
                    [
                        "--log-file",
                        os.path.join(FIXTURES, "dns.log"),
                        "--state",
                        state_path,
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(
                ZF.main(
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
                ZF.main(
                    ["--readings", os.path.join(d, "bad.json"), "--state", state_path]
                ),
                2,
            )

    def test_live_pass_with_missing_logs_is_a_quiet_rc0(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = _manifest()
            manifest["tunables"]["log_paths"] = [
                os.path.join(d, "conn.log"),
                os.path.join(d, "dns.log"),
            ]
            manifest_path = os.path.join(d, "extension.json")
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            state_path = os.path.join(d, "state.json")
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                rc = ZF.main(["--manifest", manifest_path, "--state", state_path])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")
            with open(state_path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["_reader"], {})

    def _readings_file(self, d):
        path = os.path.join(d, "readings.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(_readings([_dns(T0, "notes.example.org", "TXT")]), fh)
        return path

    def test_local_delivery_drops_a_signed_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            with mock.patch.dict(
                os.environ, {"HOMING_PIGEON_SENSOR_SECRET": "test-secret"}
            ):
                with redirect_stderr(io.StringIO()):
                    rc = ZF.main(
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
            self.assertEqual(envelope["signal"], "zeek_dns_anomaly")
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
                    rc = ZF.main(
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

    def test_conn_fixture_is_quiet_for_ula_peers(self):
        # The captured conn.log peers are IPv6 ULA addresses:
        # real Zeek rows, and by the ipaddress rule not
        # external, so the fixture files nothing.
        with tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = ZF.main(
                    [
                        "--log-file",
                        os.path.join(FIXTURES, "conn.log"),
                        "--state",
                        os.path.join(d, "state.json"),
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
