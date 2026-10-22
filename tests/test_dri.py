#!/usr/bin/env python3
"""Tests for the DRI playbook trigger evaluation and paging."""
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri as D  # noqa: E402


def _cfg(**kw):
    base = {"dri": {
        "enabled": True,
        "channel": "telegram",
        "telegram_bot_token": "tok",
        "telegram_chat_id": "chat",
        "triggers": {
            "sensor_fused_score": {"threshold": 6.0, "window_sec": 600},
            "confinement_violation": True,
            "judge_block": True,
            "key_probe": {"threshold": 2, "window_sec": 3600},
            "resource_pressure": True,
        },
        "cooldown_sec": 3600,
        "digest_window_sec": 0,
    }}
    base["dri"].update(kw)
    return base


def _iso(ts=None):
    import datetime
    dt = datetime.datetime.fromtimestamp(
        time.time() if ts is None else ts, datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_jsonl(path, records):
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class ParseTest(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertFalse(D.parse_dri({})["enabled"])

    def test_bad_channel(self):
        with self.assertRaises(RuntimeError):
            D.parse_dri({"dri": {"channel": "sms"}})

    def test_bad_triggers(self):
        with self.assertRaises(RuntimeError):
            D.parse_dri({"dri": {"triggers": ["x"]}})

    def test_partial_triggers(self):
        d = D.parse_dri({"dri": {"triggers": {"judge_block": True}}})
        self.assertIn("judge_block", d["triggers"])
        self.assertNotIn("key_probe", d["triggers"])

    def test_numbers_that_are_not_numbers_are_refused(self):
        with self.assertRaises(RuntimeError):
            D.parse_dri({"dri": {"enabled": "yes"}})
        with self.assertRaises(RuntimeError):
            D.parse_dri({"dri": {"triggers": {"sensor_fused_score": "high"}}})
        with self.assertRaises(RuntimeError):
            D.parse_dri({"dri": {"triggers": {
                "sensor_fused_score": {"threshold": "high"}}}})
        with self.assertRaises(RuntimeError):
            D.parse_dri({"dri": {"triggers": {"key_probe": "lots"}}})
        with self.assertRaises(RuntimeError):
            D.parse_dri({"dri": {"triggers": {
                "key_probe": {"threshold": "lots"}}}})
        with self.assertRaises(RuntimeError):
            D.parse_dri({"dri": {"cooldown_sec": "soon"}})
        with self.assertRaises(RuntimeError):
            D.parse_dri({"dri": {"cooldown_sec": float("inf")}})
        self.assertIsNone(D._to_ts("2026-10-22T00:00:00"))
        self.assertIsNone(D._to_ts("not-a-time"))


class SensorTriggerTest(unittest.TestCase):
    def test_fused_score_trips(self):
        with tempfile.TemporaryDirectory() as d:
            now = _iso()
            _write_jsonl(os.path.join(d, "senses.jsonl"), [
                {"sensor": "host_ids", "severity": "critical",
                 "title": "a", "received_at": now, "weight": 1.0,
                 "observed_at": now},
                {"sensor": "host_ids", "severity": "high",
                 "title": "b", "received_at": now, "weight": 1.0,
                 "observed_at": now},
            ])
            dcfg = D.parse_dri(_cfg())
            evs = D.evaluate_page_triggers(dcfg, d, time.time() - 10)
            self.assertEqual(len(evs), 1)
            self.assertEqual(evs[0]["trigger"], "sensor_fused_score")

    def test_fused_score_below_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            now = _iso()
            _write_jsonl(os.path.join(d, "senses.jsonl"), [
                {"sensor": "host_ids", "severity": "low",
                 "title": "a", "received_at": now, "weight": 1.0,
                 "observed_at": now},
            ])
            dcfg = D.parse_dri(_cfg())
            evs = D.evaluate_page_triggers(dcfg, d, time.time() - 10)
            self.assertEqual(evs, [])


class RetainedTriggerTest(unittest.TestCase):
    def _retained(self, d, payload):
        rd = os.path.join(d, "retained")
        os.makedirs(rd, exist_ok=True)
        payload = dict(payload)
        payload.setdefault("saved_at", time.time())
        with open(os.path.join(rd, "j1.json"), "w") as f:
            json.dump(payload, f)

    def test_confinement_violation(self):
        with tempfile.TemporaryDirectory() as d:
            self._retained(d, {"job_id": "j1", "confined": False})
            dcfg = D.parse_dri(_cfg())
            evs = D.evaluate_page_triggers(dcfg, d, time.time() - 10)
            self.assertEqual(len(evs), 1)
            self.assertEqual(evs[0]["trigger"], "confinement_violation")

    def test_confined_ok_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            self._retained(d, {"job_id": "j1", "confined": True})
            dcfg = D.parse_dri(_cfg())
            evs = D.evaluate_page_triggers(dcfg, d, time.time() - 10)
            self.assertEqual(evs, [])

    def test_judge_block(self):
        with tempfile.TemporaryDirectory() as d:
            self._retained(d, {"job_id": "j1", "confined": True,
                               "stderr": "job rejected: judge blocked: denylist"})
            dcfg = D.parse_dri(_cfg())
            evs = D.evaluate_page_triggers(dcfg, d, time.time() - 10)
            self.assertTrue(any(e["trigger"] == "judge_block" for e in evs))


class EventTriggerTest(unittest.TestCase):
    def test_key_probe(self):
        with tempfile.TemporaryDirectory() as d:
            _write_jsonl(os.path.join(d, "security-events.jsonl"), [
                {"type": "auth_rejection", "at": _iso(), "reason": "bad_signature"},
                {"type": "auth_rejection", "at": _iso(), "reason": "key_policy"},
            ])
            dcfg = D.parse_dri(_cfg())
            evs = D.evaluate_page_triggers(dcfg, d, time.time() - 10)
            self.assertTrue(any(e["trigger"] == "key_probe" for e in evs))

    def test_key_probe_below_threshold_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            _write_jsonl(os.path.join(d, "security-events.jsonl"), [
                {"type": "auth_rejection", "at": _iso(), "reason": "bad_signature"},
            ])
            dcfg = D.parse_dri(_cfg())
            evs = D.evaluate_page_triggers(dcfg, d, time.time() - 10)
            self.assertFalse(any(e["trigger"] == "key_probe" for e in evs))

    def test_resource_pressure(self):
        with tempfile.TemporaryDirectory() as d:
            _write_jsonl(os.path.join(d, "security-events.jsonl"), [
                {"type": "resource_pressure", "at": _iso(),
                 "threshold": 0.95, "resources": {"cpu": 0.97}},
            ])
            dcfg = D.parse_dri(_cfg())
            evs = D.evaluate_page_triggers(dcfg, d, time.time() - 10)
            self.assertTrue(any(e["trigger"] == "resource_pressure"
                                for e in evs))


class MaybePageTest(unittest.TestCase):
    def test_disabled_sends_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = _cfg(enabled=False)
            with mock.patch.object(D, "send_telegram") as st:
                self.assertEqual(D.maybe_page(cfg, d), 0)
                st.assert_not_called()

    def test_first_run_no_ancient_history(self):
        with tempfile.TemporaryDirectory() as d:
            _write_jsonl(os.path.join(d, "security-events.jsonl"), [
                {"type": "resource_pressure", "at": "2020-01-01T00:00:00Z",
                 "threshold": 0.95, "resources": {"cpu": 0.97}},
            ])
            with mock.patch.object(D, "send_telegram") as st:
                self.assertEqual(D.maybe_page(_cfg(), d), 0)
                st.assert_not_called()

    def test_page_sent(self):
        with tempfile.TemporaryDirectory() as d:
            # first call sets baseline; the event arrives after
            D.maybe_page(_cfg(), d)
            _write_jsonl(os.path.join(d, "security-events.jsonl"), [
                {"type": "resource_pressure", "at": _iso(),
                 "threshold": 0.95, "resources": {"cpu": 0.97}},
            ])
            with mock.patch.object(D, "send_telegram",
                                   return_value=True) as st:
                sent = D.maybe_page(_cfg(), d)
                self.assertEqual(sent, 1)
                st.assert_called_once()
                text = st.call_args[0][2]
                self.assertIn("homing-pigeon", text)
                self.assertIn("took no action", text)

    def test_cooldown_suppresses_second_page(self):
        with tempfile.TemporaryDirectory() as d:
            # baseline first; the event arrives after
            D.maybe_page(_cfg(), d)
            _write_jsonl(os.path.join(d, "security-events.jsonl"), [
                {"type": "resource_pressure", "at": _iso(),
                 "threshold": 0.95, "resources": {"cpu": 0.97}},
            ])
            with mock.patch.object(D, "send_telegram",
                                   return_value=True) as st:
                self.assertEqual(D.maybe_page(_cfg(), d), 1)
                # same trigger still in cooldown
                self.assertEqual(D.maybe_page(_cfg(), d), 0)
                self.assertEqual(st.call_count, 1)

    def test_send_failure_keeps_pending(self):
        with tempfile.TemporaryDirectory() as d:
            # baseline first; the event arrives after
            D.maybe_page(_cfg(), d)
            _write_jsonl(os.path.join(d, "security-events.jsonl"), [
                {"type": "resource_pressure", "at": _iso(),
                 "threshold": 0.95, "resources": {"cpu": 0.97}},
            ])
            with mock.patch.object(D, "send_telegram",
                                   return_value=False):
                self.assertEqual(D.maybe_page(_cfg(), d), 0)
            # still pending: next cycle retries the send
            with mock.patch.object(D, "send_telegram",
                                   return_value=True) as st:
                self.assertEqual(D.maybe_page(_cfg(), d), 1)
                st.assert_called_once()


class FormatTest(unittest.TestCase):
    def test_format(self):
        text = D.format_page([{
            "trigger": "x", "title": "t", "detail": "d",
            "signals": ["s1"]}])
        self.assertIn("homing-pigeon: t", text)
        self.assertIn("s1", text)
        self.assertIn("took no action", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
