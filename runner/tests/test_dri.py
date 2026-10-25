#!/usr/bin/env python3
"""Tests for the DRI playbook trigger evaluation and paging."""
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.oracle import dri as D  # noqa: E402
from runner.tests._compat import lenient_tempdir  # noqa: E402


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

    def test_retained_junk_and_a_page_that_will_not_encode(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            with open(os.path.join(d, "retained", "a.json"),
                      "w", encoding="utf-8") as fh:
                fh.write("{")
            with open(os.path.join(d, "retained", "b.json"),
                      "w", encoding="utf-8") as fh:
                fh.write("[]\n")
            outside = os.path.join(d, "out.json")
            with open(outside, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            os.symlink(outside, os.path.join(d, "retained", "c.json"))
            self.assertEqual(D._recent_retained(d, 0), [])
            self.assertEqual(D._recent_retained(
                os.path.join(d, "missing"), 0), [])

        class Unprintable:
            def __bool__(self):
                return True
            def __str__(self):
                raise RuntimeError("no")

        self.assertFalse(D.send_telegram("token", Unprintable(), "hi"))

    def test_a_chat_id_that_is_not_json_is_printed_instead(self):
        loop = {}
        loop["self"] = loop
        self.assertFalse(D.send_telegram("token", loop, "hi"))

    def test_a_symlink_in_retained_is_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "retained")
            os.makedirs(folder)
            os.symlink("/etc/hostname", os.path.join(folder, "x.json"))
            self.assertEqual(D._recent_retained(d, 0), [])

    def test_a_bad_alert_does_not_stop_the_fused_score(self):
        now = _iso()
        records = [
            "nope",
            {"sensor": ["not-a-key"], "severity": "high",
             "title": "bad", "observed_at": now, "weight": 1.0},
            {"sensor": "host_ids", "severity": "critical",
             "title": "a", "observed_at": now, "weight": 1.0},
            {"sensor": "host_ids", "severity": "critical",
             "title": "b", "observed_at": now, "weight": 1.0},
        ]
        real = D._senses.alert_score

        def score(rec, weight=1.0):
            if isinstance(rec.get("sensor"), list):
                raise TypeError("bad sensor")
            return real(rec, weight)

        dcfg = D.parse_dri(_cfg())
        with mock.patch.object(
                D._senses, "load_alerts", return_value=records), \
                mock.patch.object(D._senses, "alert_score", score):
            evs = D.evaluate_page_triggers(dcfg, "unused", time.time() - 10)
        self.assertEqual(len(evs), 1)
        self.assertIn("host_ids", evs[0]["title"])

    def test_a_page_state_that_is_not_a_map_is_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            D.maybe_page(_cfg(), d, now=1000.0)
            state_path = os.path.join(d, D.STATE_FILE)
            with open(state_path, encoding="utf-8") as fh:
                state = json.load(fh)
            state["last_page"] = ["not-a-map"]
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump(state, fh)
            with mock.patch.object(
                    D, "evaluate_page_triggers",
                    return_value=[None, {"trigger": "sensor_fused_score"}]), \
                    mock.patch.object(D, "_send", return_value=True):
                sent = D.maybe_page(_cfg(), d, now=5000.0)
            self.assertEqual(sent, 1)
            with open(state_path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertIsInstance(saved["last_page"], dict)


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


class SaveStateBranchesTest(unittest.TestCase):
    """Queue A: the write branches of _save_state (coverage
    run 40180268696: 14 lines on Windows, 9 on Linux). The
    DRI state file follows the same staging discipline as
    the detection baseline: only scalar keys and
    JSON-shaped values are promised to disk, the write is
    staged and replaced, and every failure around it --
    chmod, the replace itself, the writer, and the
    cleanup's own close/unlink -- is swallowed so a paging
    decision is never lost to a state file.
    """

    def test_non_scalar_keys_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            D._save_state(d, {("a", "tuple"): 1, None: 2,
                              "s": 3, 4: "int-key", 1.5: True})
            got = D._load_state(d)
            self.assertEqual(got, {"s": 3, "4": "int-key",
                                   "1.5": True})

    def test_an_unserializable_value_is_stringified(self):
        class Odd:
            def __repr__(self):
                return "odd-value"
        with tempfile.TemporaryDirectory() as d:
            D._save_state(d, {"odd": Odd(), "plain": 1})
            got = D._load_state(d)
            self.assertEqual(got["plain"], 1)
            self.assertIn("odd-value", got["odd"])

    def test_a_value_that_cannot_even_be_named_is_skipped(self):
        class Unnameable:
            def __str__(self):
                raise RuntimeError("no name")

            __repr__ = __str__
        with tempfile.TemporaryDirectory() as d:
            D._save_state(d, {"bad": Unnameable(), "plain": 1})
            self.assertEqual(D._load_state(d), {"plain": 1})

    def test_a_failed_chmod_does_not_fail_the_save(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(D.os, "chmod",
                                   side_effect=OSError("refused")):
                D._save_state(d, {"a": 1})
            self.assertEqual(D._load_state(d), {"a": 1})

    def test_a_failed_replace_leaves_no_staging_file(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, D.STATE_FILE))
            D._save_state(d, {"a": 1})
            leftovers = [n for n in os.listdir(d) if ".tmp." in n]
            self.assertEqual(leftovers, [])

    def test_a_failed_writer_closes_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(D.os, "fdopen",
                                   side_effect=OSError("no writer")):
                D._save_state(d, {"a": 1})
            self.assertEqual(os.listdir(d), [])

    def test_the_cleanup_swallows_its_own_failures(self):
        real_unlink = os.unlink
        calls = {"tmp": 0}

        def unlink(path, *a, **kw):
            if ".tmp." in str(path):
                calls["tmp"] += 1
                if calls["tmp"] > 1:
                    raise OSError("staging file stuck")
            return real_unlink(path, *a, **kw)

        # ignore_cleanup_errors: the scripted close failure
        # leaks the staging fd on purpose, and Windows will
        # not unlink a file this process still holds open.
        with lenient_tempdir() as d:
            with mock.patch.object(D.os, "fdopen",
                                   side_effect=OSError("no writer")), \
                    mock.patch.object(D.os, "close",
                                      side_effect=OSError("stuck")), \
                    mock.patch.object(D.os, "unlink",
                                      side_effect=unlink):
                D._save_state(d, {"a": 1})


class DriResidualLegsTest(unittest.TestCase):
    """Queue A refill: dri's residual legs
    (coverage run 40189711740). A retained
    folder holds more than job results -- a
    stray non-JSON file is passed over, not
    parsed. And the fused score's window is a
    window: alerts older than it do not count,
    however heavy they are.
    """

    def test_a_non_json_file_in_retained_is_passed_over(self):
        with tempfile.TemporaryDirectory() as d:
            kept = os.path.join(d, "retained")
            os.makedirs(kept)
            with open(os.path.join(kept, "notes.txt"),
                      "w", encoding="utf-8") as fh:
                fh.write("operator notes, not a result")
            payload = {"job_id": "job1",
                       "saved_at": time.time()}
            with open(os.path.join(kept, "job1.json"),
                      "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            out = D._recent_retained(d, 0)
            self.assertEqual(out, [("job1", payload)])

    def test_stale_alerts_do_not_trip_the_fused_score(self):
        old = _iso(time.time() - 7200)
        records = [
            {"sensor": "host_ids", "severity": "critical",
             "title": "a", "observed_at": old,
             "weight": 1.0},
            {"sensor": "host_ids", "severity": "critical",
             "title": "b", "observed_at": old,
             "weight": 1.0},
        ]
        dcfg = D.parse_dri(_cfg())
        with mock.patch.object(
                D._senses, "load_alerts",
                return_value=records):
            evs = D.evaluate_page_triggers(
                dcfg, "unused", time.time() - 10)
        self.assertEqual(evs, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
