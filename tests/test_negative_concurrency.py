#!/usr/bin/env python3
"""Negative concurrency and extension-poison resilience.

Findings documented here (2026-10-15 simulation in virtual environment):

1. Concurrent mixed good/poison mails (ThreadPoolExecutor path):
   One worker raising on a poisoned retained/query or bad board task
   must not prevent other workers from completing, and poll_once must
   not raise for cases already classified as poison/reject.

2. Malformed extension state files (senses.jsonl, dri-state.json,
   resources.json, security-events.jsonl, board.json, retained/*.json,
   query_times.json):
   Empty files, truncated JSON, non-UTF8 bytes, lists where objects
   expected, numeric/string type confusion, and extreme values must
   be ignored or logged, never crash the poll or Oracle answer path.

3. Oracle / confinement / ask paths with poisoned retained output
   (numeric stdout, null fields, wrong-type view/budget) continue
   and redact rather than raise.

4. Sensor alerts with invalid shapes (wrong types, path traversal
   names, non-dict detail) are rejected without execution or crash.

All cases below are expected to pass (graceful). Failures indicate
a real crash path that must be hardened.
"""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri, resources  # noqa: E402
from runner.runner import (  # noqa: E402
    Board,
    _redact_patterns,
    answer_queries,
    poll_once,
    sign_payload,
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
FLAG = "FLAG-CRED-9f3c2a7e1"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _MultiIMAP:
    """Feeds multiple raw messages on successive fetches."""
    def __init__(self, raws):
        self.raws = list(raws)
        self.n = 0

    def search(self, *args):
        ids = [str(i + 1).encode() for i in range(len(self.raws))]
        return "OK", [b" ".join(ids)] if ids else [b""]

    def fetch(self, num, what):
        idx = int(num) - 1
        if 0 <= idx < len(self.raws):
            return "OK", [(b"%d (RFC822)" % int(num), self.raws[idx])]
        return "OK", []

    def store(self, *args, **kwargs):
        return "OK", []


class _SMTP:
    def sendmail(self, *args, **kwargs):
        return None


class _Opts:
    dry_run = False
    no_send = True
    workers = 4


class ConcurrentPoisonTest(unittest.TestCase):
    """Finding: concurrent workers processing mixed poison and good jobs
    must all complete; poll_once returns without raising.
    """

    def test_mixed_poison_and_ping_do_not_crash_poll(self):
        with tempfile.TemporaryDirectory() as d:
            # Poison: numeric task_id on board
            bad_body = sign_payload({
                "v": 1, "type": "task_submit", "issued_at": _now(),
                "task_id": 999, "priority": "high",
            }, SECRET)
            # Good ping
            good_body = sign_payload({
                "v": 1, "type": "job", "job_id": "good-ping",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            # Poison: query against missing/poisoned retained
            q_body = sign_payload({
                "v": 1, "type": "query", "query_id": "q-bad",
                "job_id": "missing", "issued_at": _now(),
                "queries": [{"op": "grep", "pattern": "("}],
            }, SECRET)
            raws = [
                _mail("[HOMING-PIGEON] task_submit b1", bad_body),
                _mail("[HOMING-PIGEON] job good-ping", good_body),
                _mail("[HOMING-PIGEON] query q-bad", q_body),
            ]
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "workers": 4,
            }
            seen = {}
            # Must not raise
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            self.assertIn("good-ping", seen)


class MalformedExtensionStateTest(unittest.TestCase):
    """Finding: poisoned on-disk extension state (wrong types, truncated,
    binary, empty) is ignored; poll and DRI/resources continue.
    """

    def test_empty_truncated_binary_state_files_do_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            # Empty
            open(os.path.join(d, "senses.jsonl"), "w").close()
            open(os.path.join(d, "security-events.jsonl"), "w").close()
            # Truncated JSON
            with open(os.path.join(d, "dri-state.json"), "w") as fh:
                fh.write('{"last_check":')
            # Binary / non-UTF8
            with open(os.path.join(d, "resources.json"), "wb") as fh:
                fh.write(b"\xff\xfe not json")
            # Wrong top-level type
            with open(os.path.join(d, "board.json"), "w") as fh:
                json.dump(["not", "a", "board"], fh)
            # Extreme / wrong types in retained
            os.makedirs(os.path.join(d, "retained"))
            with open(os.path.join(d, "retained", "job-x.json"), "w") as fh:
                json.dump({
                    "stdout": 42, "stderr": None, "view": True,
                    "budget": float("inf"), "spent": "many",
                    "patterns": "not-a-dict", "saved_at": "yesterday",
                }, fh)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "resources": {"enabled": True, "threshold": 0.0},
                "dri": {"enabled": True, "channel": "telegram"},
            }
            # Resource check and DRI must not raise
            event = resources.check_resources(cfg, d)
            self.assertTrue(event is None or isinstance(event, dict))
            with mock.patch.object(dri, "_send", return_value=False):
                dri.maybe_page(cfg, d)
            # A ping still works
            body = sign_payload({
                "v": 1, "type": "job", "job_id": "still-works",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] job still-works", body)
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([raw]), smtp=_SMTP(), opts=_Opts())

    def test_oracle_answers_on_poisoned_retained(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            with open(os.path.join(d, "retained", "job-p.json"), "w") as fh:
                json.dump({
                    "stdout": 12345, "stderr": {"bad": True},
                    "exit_code": "zero", "view": 99, "budget": "lots",
                    "patterns": [1, 2], "saved_at": time.time(),
                }, fh)
            cfg = {"redact_patterns_extra": {"flag": r"FLAG-CRED"}}
            answers, spent = answer_queries(
                [{"op": "grep", "pattern": "x"}, {"op": "attest", "predicate": "exit_zero"}],
                {"stdout": "", "stderr": "", "exit_code": 0},
                _redact_patterns(cfg),
                budget=4,
                cfg=cfg,
                view="attested",
                base_dir=d,
            )
            self.assertIsInstance(answers, list)
            self.assertGreaterEqual(spent, 0)


class SensorShapePoisonTest(unittest.TestCase):
    """Finding: sensor_alert jobs with wrong-type fields or path-like
    names are rejected before store/execute; no crash, no side effects.
    """

    def test_bad_sensor_shapes_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            jobs = [
                {  # wrong types
                    "v": 1, "type": "job", "kind": "sensor_alert",
                    "job_id": "bad-types", "issued_at": _now(),
                    "sensor": 5, "severity": ["high"], "title": None,
                    "detail": "string-detail",
                },
                {  # path traversal
                    "v": 1, "type": "job", "kind": "sensor_alert",
                    "job_id": "trav", "issued_at": _now(),
                    "sensor": "../etc/passwd", "severity": "critical",
                    "title": "x", "detail": FLAG,
                },
            ]
            raws = []
            for j in jobs:
                raws.append(_mail(
                    f"[HOMING-PIGEON] job {j['job_id']}",
                    sign_payload(j, SECRET),
                ))
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "sensors": {
                    "host_ids": {
                        "enabled": True,
                        "key_id": "default",
                        "weight": 1.0,
                    },
                },
            }
            # Must not raise; nothing executed
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            self.assertFalse(os.path.exists(os.path.join(d, "work")))
            # senses.jsonl either missing or contains no FLAG
            path = os.path.join(d, "senses.jsonl")
            if os.path.exists(path):
                with open(path, encoding="utf-8", errors="replace") as fh:
                    self.assertNotIn(FLAG, fh.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)


class OracleAndConfinementPoisonTest(unittest.TestCase):
    """Finding: Oracle answer path, confinement snapshots, and retained
    loads tolerate extreme bad data without raising.
    """

    def test_answer_queries_rejects_non_objects_and_bad_ops(self):
        answers, spent = answer_queries(
            ["not-dict", None, 5, {"op": "unknown_xyz"},
             {"op": "grep", "pattern": None}, {"op": "tail", "n": "lots"}],
            {"stdout": None, "stderr": 1, "exit_code": "x"},
            {}, budget=10, view="attested",
        )
        self.assertIsInstance(answers, list)
        self.assertGreaterEqual(spent, 0)
        # No crash; rejects or empty answers only
        for a in answers:
            self.assertIsInstance(a, dict)

    def test_confinement_snapshot_tolerates_bad_roots(self):
        from runner.runner import snapshot_outside, confinement_violated
        with tempfile.TemporaryDirectory() as d:
            # nonexistent
            before = snapshot_outside(os.path.join(d, "missing"))
            self.assertIsInstance(before, dict)
            # file used as root
            fpath = os.path.join(d, "afile")
            open(fpath, "w").close()
            before = snapshot_outside(fpath)
            self.assertIsInstance(before, dict)
            # empty string
            before = snapshot_outside("")
            self.assertIsInstance(before, dict)
            # confinement check on empties
            self.assertFalse(confinement_violated({}, {}))

    def test_load_retained_poison_returns_none(self):
        from runner.runner import load_retained
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"))
            cases = [
                ("bad", "not json at all"),
                ("list", "[1, 2, 3]"),
                ("null", "null"),
                ("num", "42"),
                ("empty", ""),
                ("trunc", '{"stdout":'),
            ]
            for name, content in cases:
                with open(os.path.join(d, "retained", f"{name}.json"), "w") as fh:
                    fh.write(content)
                self.assertIsNone(load_retained(d, name))

    def test_board_rejects_non_dict_and_bad_offer(self):
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            ok, reason = board.submit("not a dict")
            self.assertFalse(ok)
            ok, reason = board.submit(None)
            self.assertFalse(ok)
            # offer with garbage capabilities
            self.assertIsNone(board.offer("w1", "not-a-list"))
            self.assertIsNone(board.offer("w1", None))
            self.assertIsNone(board.offer("w1", 5))
            # still usable
            ok, reason = board.submit({"task_id": "ok-1", "priority": 1})
            self.assertTrue(ok)


class ConcurrentQueryPoisonTest(unittest.TestCase):
    """Finding: concurrent query mails against missing or poisoned
    retained stores do not raise and do not stop other processing.
    """

    def test_many_bad_queries_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            raws = []
            for i in range(8):
                body = sign_payload({
                    "v": 1, "type": "query", "query_id": f"q{i}",
                    "job_id": f"missing-{i}", "issued_at": _now(),
                    "queries": [
                        {"op": "grep", "pattern": "("},
                        "not-an-object",
                        {"op": "senses", "sensor": 99},
                    ],
                }, SECRET)
                raws.append(_mail(f"[HOMING-PIGEON] query q{i}", body))
            # also a good ping so we confirm the poll still processes
            ping = sign_payload({
                "v": 1, "type": "job", "job_id": "still-alive",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            raws.append(_mail("[HOMING-PIGEON] job still-alive", ping))
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "workers": 4,
                "max_queries_per_hour": 0,
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Opts())
            self.assertIn("still-alive", seen)


class ExtremeExtensionStateTest(unittest.TestCase):
    """Finding: extreme values (NaN-like, huge strings, deeply nested)
    in extension stores are ignored; processing continues.
    """

    def test_extreme_values_in_state_do_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            # huge line in jsonl
            with open(os.path.join(d, "senses.jsonl"), "w") as fh:
                fh.write(json.dumps({"sensor": "x", "detail": "A" * 100000}) + "\n")
                fh.write("not json\n")
                fh.write(json.dumps({"severity": float("nan")}) + "\n")
            # dri with extreme cooldown
            with open(os.path.join(d, "dri-state.json"), "w") as fh:
                json.dump({
                    "last_check": 1e30,
                    "last_page": {"k": -1e9},
                    "pending_digest": [None, "x", 5],
                }, fh)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "resources": {"enabled": True, "threshold": 0.5},
                "dri": {"enabled": True, "channel": "telegram",
                        "cooldown_sec": 0},
            }
            event = resources.check_resources(cfg, d)
            self.assertTrue(event is None or isinstance(event, dict))
            with mock.patch.object(dri, "_send", return_value=False):
                dri.maybe_page(cfg, d)
            # poll still works
            body = sign_payload({
                "v": 1, "type": "job", "job_id": "after-extreme",
                "issued_at": _now(), "kind": "ping",
            }, SECRET)
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP([_mail("[HOMING-PIGEON] job after-extreme", body)]),
                      smtp=_SMTP(), opts=_Opts())
