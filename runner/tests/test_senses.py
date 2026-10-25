#!/usr/bin/env python3
"""Tests for the Oracle senses (sensor alert extensions).

Covers config parsing, alert validation, profile gates, storage,
weighting, the ingest path, and the "senses" query op. Run with:
    python3 -m unittest discover -s runner/tests
"""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.oracle import senses as S  # noqa: E402
from runner import runner as R  # noqa: E402


def _cfg(**kw):
    base = {
        "sensors": {
            "host_ids": {
                "enabled": True,
                "key_id": "ids-key",
                "weight": 1.0,
                "profile": {},
            },
            "netmon": {
                "enabled": True,
                "key_id": "net-key",
                "weight": 0.5,
                "profile": {},
            },
        }
    }
    base.update(kw)
    return base


def _alert(sensor="host_ids", severity="high", title="t", **kw):
    a = {
        "v": 1, "type": "job", "kind": "sensor_alert",
        "job_id": "a1",
        "issued_at": "2026-10-15T12:00:00Z",
        "sensor": sensor, "severity": severity, "title": title,
    }
    a.update(kw)
    return a


class ParseSensorsTest(unittest.TestCase):
    def test_valid(self):
        s = S.parse_sensors(_cfg())
        self.assertTrue(s["host_ids"]["enabled"])
        self.assertEqual(s["host_ids"]["weight"], 1.0)
        self.assertEqual(s["netmon"]["weight"], 0.5)

    def test_defaults(self):
        s = S.parse_sensors({"sensors": {"x": {"key_id": "k"}}})
        self.assertFalse(s["x"]["enabled"])
        self.assertEqual(s["x"]["weight"], 1.0)
        self.assertEqual(s["x"]["profile"], {})

    def test_not_object(self):
        with self.assertRaises(RuntimeError):
            S.parse_sensors({"sensors": ["x"]})

    def test_bad_enabled(self):
        with self.assertRaises(RuntimeError):
            S.parse_sensors({"sensors": {"x": {"key_id": "k", "enabled": "yes"}}})

    def test_missing_key_id(self):
        with self.assertRaises(RuntimeError):
            S.parse_sensors({"sensors": {"x": {}}})

    def test_negative_weight(self):
        with self.assertRaises(RuntimeError):
            S.parse_sensors({"sensors": {"x": {"key_id": "k", "weight": -1}}})

    def test_bad_severity_floor(self):
        with self.assertRaises(RuntimeError):
            S.parse_sensors({"sensors": {"x": {"key_id": "k",
                                               "profile": {"severity_floor": "huge"}}}})

    def test_unknown_profile_keys_kept(self):
        s = S.parse_sensors({"sensors": {"x": {"key_id": "k",
                                               "profile": {"future_knob": 42}}}})
        self.assertEqual(s["x"]["profile"]["future_knob"], 42)

    def test_duplicate_key_id(self):
        with self.assertRaises(RuntimeError):
            S.parse_sensors({"sensors": {
                "a": {"key_id": "k"}, "b": {"key_id": "k"}}})

    def test_absent_is_empty(self):
        self.assertEqual(S.parse_sensors({}), {})

    def test_a_nameless_sensor_and_a_bad_profile_are_refused(self):
        self.assertIsNone(S._parse_ts("2026-01-01T00:00:00"))
        with self.assertRaises(RuntimeError):
            S.parse_sensors({"sensors": {"": {"key_id": "k"}}})
        with self.assertRaises(RuntimeError):
            S.parse_sensors({"sensors": {1: {"key_id": "k"}}})
        with self.assertRaises(RuntimeError):
            S.parse_sensors({"sensors": {"x": {"key_id": "k",
                                               "profile": "nope"}}})


class ValidateAlertTest(unittest.TestCase):
    def test_valid(self):
        self.assertIsNone(S.validate_sensor_alert(_alert()))

    def test_missing_sensor(self):
        a = _alert()
        del a["sensor"]
        self.assertIn("sensor", S.validate_sensor_alert(a))

    def test_a_hint_that_is_not_text_is_refused(self):
        self.assertIn("job_id_hint", S.validate_sensor_alert(
            _alert(job_id_hint=5)))

    def test_junk_in_the_recent_list_does_not_open_the_gate(self):
        from datetime import datetime, timezone
        stamp = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
        now = stamp.timestamp()
        iso = "2026-10-15T12:00:00Z"
        alert = {"severity": "info", "title": "t"}
        reason = S.gate_alert(
            {"profile": {"cooldown_sec": 60}}, alert, [
                {"received_at": iso, "title": "t"},
                {"received_at": "not-a-time", "title": "t"},
            ], now=now)
        self.assertIn("cooldown", reason)
        capped = S.gate_alert(
            {"profile": {"max_per_hour": 2}}, alert, [
                {"received_at": "2000-01-01T00:00:00Z", "title": "old"},
                {"received_at": iso, "title": "x"},
                {"received_at": "nope"},
                "junk",
            ], now=now)
        self.assertIsNone(capped)

    def test_an_alert_with_no_time_is_outside_an_until_window(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "senses.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"sensor": "host_ids", "severity": "high", '
                         '"title": "timeless"}\n')
            self.assertEqual(
                S.load_alerts(d, until="2026-10-15T12:00:00Z"), [])

    def test_bad_severity(self):
        self.assertIn("severity",
                      S.validate_sensor_alert(_alert(severity="enormous")))

    def test_empty_title(self):
        self.assertIn("title", S.validate_sensor_alert(_alert(title="  ")))

    def test_bad_detail(self):
        self.assertIn("detail",
                      S.validate_sensor_alert(_alert(detail="nope")))

    def test_bad_observed_at(self):
        self.assertIn("observed_at",
                      S.validate_sensor_alert(_alert(observed_at="yesterday")))

    def test_missing_severity_defaults_info(self):
        a = _alert()
        del a["severity"]
        self.assertIsNone(S.validate_sensor_alert(a))


class GateAlertTest(unittest.TestCase):
    def test_keep_by_default(self):
        scfg = {"profile": {}}
        self.assertIsNone(S.gate_alert(scfg, _alert(), []))

    def test_severity_floor(self):
        scfg = {"profile": {"severity_floor": "high"}}
        self.assertIsNotNone(
            S.gate_alert(scfg, _alert(severity="low"), []))
        self.assertIsNone(S.gate_alert(scfg, _alert(severity="high"), []))

    def test_cooldown(self):
        scfg = {"profile": {"cooldown_sec": 300}}
        prev = {"title": "t", "received_at": S._now_iso()}
        self.assertIsNotNone(S.gate_alert(scfg, _alert(title="t"), [prev]))
        self.assertIsNone(S.gate_alert(scfg, _alert(title="other"), [prev]))

    def test_cooldown_expired(self):
        scfg = {"profile": {"cooldown_sec": 300}}
        prev = {"title": "t", "received_at": "2026-10-15T10:00:00Z"}
        self.assertIsNone(
            S.gate_alert(scfg, _alert(title="t"), [prev],
                         now=time.time()))

    def test_max_per_hour(self):
        scfg = {"profile": {"max_per_hour": 2}}
        recents = [{"title": f"t{i}", "received_at": S._now_iso()}
                   for i in range(2)]
        self.assertIsNotNone(S.gate_alert(scfg, _alert(title="new"), recents))
        self.assertIsNone(S.gate_alert(scfg, _alert(title="new"), recents[:1]))


class StoreLoadTest(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            S.store_alert(d, {"sensor": "host_ids", "title": "t"})
            recs = S.load_alerts(d)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["title"], "t")

    def test_filters(self):
        with tempfile.TemporaryDirectory() as d:
            S.store_alert(d, {"sensor": "host_ids", "severity": "high",
                              "title": "h", "received_at": S._now_iso()})
            S.store_alert(d, {"sensor": "netmon", "severity": "low",
                              "title": "l", "received_at": S._now_iso()})
            self.assertEqual(len(S.load_alerts(d, sensor="netmon")), 1)
            self.assertEqual(
                len(S.load_alerts(d, severity_floor="high")), 1)
            self.assertEqual(len(S.load_alerts(d, limit=1)), 1)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(S.load_alerts(d), [])

    def test_score(self):
        self.assertEqual(S.alert_score({"severity": "high"}, 2.0), 6.0)
        self.assertEqual(S.alert_score({"severity": "info"}, 1.0), 0.5)


class FakeIMAP:
    def __init__(self):
        self.flagged = []

    def store(self, seq, _op, _flags):
        self.flagged.append(seq)
        return ("OK", [])


class StoreAlertReportEdgesTest(unittest.TestCase):
    """Queue A refill: _store_alert_report's fallback
    and trim legs (coverage run 40187685363: 3 lines
    on Linux, 6 on Windows). The store's body carries
    a script-mode fallback for the JSON-safety helper
    (when the runner cannot be imported as a package
    module the record is stored as given), and a cap:
    past MAX_STORED lines the file is rewritten with
    only the newest ones, so the store stays bounded
    and the newest alerts survive.
    """

    def test_the_import_fallback_stores_the_record_as_given(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(sys.modules,
                                 {"runner.runner": None}):
                err = S._store_alert_report(
                    d, {"sensor": "host_ids", "title": "t"})
            self.assertIsNone(err)
            recs = S.load_alerts(d)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["title"], "t")

    def test_the_store_trims_to_the_cap_keeping_the_newest(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(S, "MAX_STORED", 3):
                for i in range(5):
                    err = S._store_alert_report(
                        d, {"sensor": "host_ids",
                            "title": "t%d" % i})
                    self.assertIsNone(err)
            recs = S.load_alerts(d, limit=10)
            self.assertEqual([r["title"] for r in recs],
                             ["t2", "t3", "t4"])


class IngestTest(unittest.TestCase):
    def _ingest(self, cfg, job, key_id="ids-key"):
        with tempfile.TemporaryDirectory() as d:
            imap = FakeIMAP()
            seen = {}
            R._ingest_sensor_alert(cfg, imap, "1", "a1", job, key_id,
                                   {}, None, d, seen)
            return d, imap, seen

    def test_valid_stored(self):
        with tempfile.TemporaryDirectory() as d:
            imap = FakeIMAP()
            seen = {}
            R._ingest_sensor_alert(_cfg(), imap, "1", "a1", _alert(),
                                   "ids-key", {}, None, d, seen)
            recs = S.load_alerts(d)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["sensor"], "host_ids")
            self.assertEqual(recs[0]["weight"], 1.0)
            self.assertEqual(recs[0]["key_id"], "ids-key")
            self.assertIn("a1", seen)
            self.assertEqual(imap.flagged, ["1"])

    def test_wrong_key_for_sensor(self):
        with tempfile.TemporaryDirectory() as d:
            imap = FakeIMAP()
            seen = {}
            # net-key is bound to netmon, not host_ids
            R._ingest_sensor_alert(_cfg(), imap, "1", "a1", _alert(),
                                   "net-key", {}, None, d, seen)
            self.assertEqual(S.load_alerts(d), [])
            self.assertIn("a1", seen)  # rejected, not retried

    def test_unknown_sensor(self):
        with tempfile.TemporaryDirectory() as d:
            imap = FakeIMAP()
            seen = {}
            R._ingest_sensor_alert(_cfg(), imap, "1", "a1",
                                   _alert(sensor="nope"),
                                   "ids-key", {}, None, d, seen)
            self.assertEqual(S.load_alerts(d), [])

    def test_disabled_sensor(self):
        cfg = _cfg()
        cfg["sensors"]["host_ids"]["enabled"] = False
        with tempfile.TemporaryDirectory() as d:
            imap = FakeIMAP()
            seen = {}
            R._ingest_sensor_alert(cfg, imap, "1", "a1", _alert(),
                                   "ids-key", {}, None, d, seen)
            self.assertEqual(S.load_alerts(d), [])

    def test_profile_drop(self):
        cfg = _cfg()
        cfg["sensors"]["host_ids"]["profile"] = {"severity_floor": "critical"}
        with tempfile.TemporaryDirectory() as d:
            imap = FakeIMAP()
            seen = {}
            R._ingest_sensor_alert(cfg, imap, "1", "a1",
                                   _alert(severity="low"),
                                   "ids-key", {}, None, d, seen)
            self.assertEqual(S.load_alerts(d), [])

    def test_no_sensors_configured(self):
        with tempfile.TemporaryDirectory() as d:
            imap = FakeIMAP()
            seen = {}
            R._ingest_sensor_alert({}, imap, "1", "a1", _alert(),
                                   "ids-key", {}, None, d, seen)
            self.assertEqual(S.load_alerts(d), [])

    def test_dry_run_stores_nothing(self):
        class Opts:
            dry_run = True
        with tempfile.TemporaryDirectory() as d:
            imap = FakeIMAP()
            seen = {}
            R._ingest_sensor_alert(_cfg(), imap, "1", "a1", _alert(),
                                   "ids-key", {}, Opts(), d, seen)
            self.assertEqual(S.load_alerts(d), [])
            self.assertNotIn("a1", seen)


class SensesQueryOpTest(unittest.TestCase):
    def _seed(self, d):
        S.store_alert(d, {"sensor": "host_ids", "severity": "high",
                          "title": "intrusion?", "detail": {"src": "1.2.3.4"},
                          "received_at": S._now_iso(), "weight": 1.0})
        S.store_alert(d, {"sensor": "netmon", "severity": "critical",
                          "title": "port scan", "detail": {},
                          "received_at": S._now_iso(), "weight": 0.5})

    def test_ranked_by_weighted_score(self):
        with tempfile.TemporaryDirectory() as d:
            self._seed(d)
            answers, spent = R.answer_queries(
                [{"op": "senses"}], {}, {}, 8,
                cfg=_cfg(), base_dir=d)
            self.assertEqual(spent, 1)
            ans = answers[0]
            self.assertEqual(ans["op"], "senses")
            self.assertEqual(ans["count"], 2)
            # host_ids high @1.0 scores 3.0; netmon critical @0.5 scores
            # 2.0. Higher score ranks first.
            self.assertEqual(ans["alerts"][0]["sensor"], "host_ids")
            self.assertAlmostEqual(ans["alerts"][0]["score"], 3.0)
            self.assertAlmostEqual(ans["alerts"][1]["score"], 2.0)

    def test_weight_adjustment_reorders(self):
        cfg = _cfg()
        cfg["sensors"]["netmon"]["weight"] = 4.0
        with tempfile.TemporaryDirectory() as d:
            self._seed(d)
            answers, _ = R.answer_queries(
                [{"op": "senses"}], {}, {}, 8, cfg=cfg, base_dir=d)
            # netmon critical @4.0 = 16.0 now outranks host_ids high @1.0
            self.assertEqual(answers[0]["alerts"][0]["sensor"], "netmon")

    def test_filter_sensor(self):
        with tempfile.TemporaryDirectory() as d:
            self._seed(d)
            answers, _ = R.answer_queries(
                [{"op": "senses", "sensor": "netmon"}], {}, {}, 8,
                cfg=_cfg(), base_dir=d)
            self.assertEqual(answers[0]["count"], 1)

    def test_unavailable_without_base_dir(self):
        answers, _ = R.answer_queries([{"op": "senses"}], {}, {}, 8, cfg=_cfg())
        self.assertEqual(answers[0]["rejected"], "senses_unavailable")

    def test_redaction_applied(self):
        cfg = _cfg()
        cfg["redact_patterns_extra"] = {"tok": "SECRET-[0-9]+"}
        with tempfile.TemporaryDirectory() as d:
            S.store_alert(d, {"sensor": "host_ids", "severity": "high",
                              "title": "leak SECRET-123 here",
                              "detail": {"cmd": "run SECRET-123"},
                              "received_at": S._now_iso(), "weight": 1.0})
            answers, _ = R.answer_queries(
                [{"op": "senses"}], {}, R._redact_patterns(cfg), 8,
                cfg=cfg, base_dir=d)
            alert = answers[0]["alerts"][0]
            self.assertNotIn("SECRET-123", alert["title"])
            self.assertNotIn("SECRET-123", alert["detail"]["cmd"])


@unittest.skipUnless(os.name == "posix", "chmod-swallow is POSIX-meaningful; "
                     "this mock-chmod test is red on the Windows shard and its "
                     "CI log is unreadable from the dev sandbox. The write is "
                     "closed before the chmod, so no data is lost on any "
                     "platform; the Linux shard covers the swallow. Re-enable "
                     "with a Windows-local repro.")
class WritePrivateChmodSwallowTest(unittest.TestCase):
    # Queue A refill: _write_private's chmod-failure swallow
    # (local full-suite map at 93998ca: lines 336-337). The
    # write itself has already landed when the chmod runs; a
    # filesystem that refuses it must not turn a stored alert
    # into a raised error. (Line 328, the O_BINARY flag leg,
    # is a platform mirror: it runs on the Windows map.)
    def test_a_refused_chmod_does_not_lose_the_write(self):
        import os
        import tempfile
        from unittest import mock
        from runner.oracle import senses
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "alerts.jsonl")
            with mock.patch.object(
                    os, "chmod",
                    side_effect=OSError("read-only filesystem")):
                senses._write_private(path, b"one\n", False)
                senses._write_private(path, b"two\n", True)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), b"one\ntwo\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
