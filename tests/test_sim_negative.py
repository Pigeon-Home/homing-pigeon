#!/usr/bin/env python3
"""Simulation negative tests: agent + oracle must not crash on bad extension data or concurrency.

These cases were found by feeding poisoned stores and concurrent bad messages
into poll_once / oracle paths. Documented here so regressions are caught.
All must complete without raising; processing of subsequent good jobs continues.
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import (  # noqa: E402
    Board,
    poll_once,
    sign_payload,
    answer_queries,
    _redact_patterns,
)
from runner import senses, resources, dri  # noqa: E402

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _FakeIMAP:
    def __init__(self, raws):
        self.raws = list(raws)
        self.seen = set()

    def search(self, *args):
        ids = [str(i + 1).encode() for i in range(len(self.raws)) if i not in self.seen]
        return "OK", [b" ".join(ids)] if ids else [b""]

    def fetch(self, num, what):
        idx = int(num) - 1
        return "OK", [(b"1 (RFC822)", self.raws[idx])]

    def store(self, num, flags, value):
        self.seen.add(int(num) - 1)
        return "OK", []


class _FakeSMTP:
    def __init__(self):
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg.as_bytes() if hasattr(msg, "as_bytes") else str(msg).encode())
        self.sent.append(msg)


class SimNegativeTest(unittest.TestCase):
    def test_poisoned_stores_do_not_crash_poll(self):
        """Finding: concurrent writers of garbage into senses/resources/board
        must not stop the poll cycle. A good job after the poison still runs.
        """
        with tempfile.TemporaryDirectory() as d:
            # Poison the stores
            open(os.path.join(d, "senses.jsonl"), "w").write("not json\n[1,2]\n{\"bad\":}\n")
            open(os.path.join(d, "resources.json"), "w").write('"string not object"')
            open(os.path.join(d, "board.json"), "w").write("[1, 2, 3]")
            open(os.path.join(d, "query_times.json"), "w").write("null")

            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "base_dir": d,
                "workers": 4,
                "sensors": {"door": {"enabled": True, "key_id": "k1", "weight": 1.0}},
            }
            # Bad sensor alert + good job
            bad_alert = sign_payload({
                "v": 2, "type": "job", "job_id": "bad-alert",
                "kind": "sensor_alert", "issued_at": _now(),
                "sensor": "door", "severity": 999, "title": None,
                "detail": "not a dict",
            }, SECRET)
            good = sign_payload({
                "v": 2, "type": "job", "job_id": "good-1",
                "issued_at": _now(),
                "kind": "exec",
                "script": "echo ok",
            }, SECRET)
            imap = _FakeIMAP([
                _mail("[HOMING-PIGEON] job bad-alert", bad_alert),
                _mail("[HOMING-PIGEON] job good-1", good),
            ])
            smtp = _FakeSMTP()
            opts = mock.Mock(dry_run=False, no_send=False)
            # Must not raise
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"), imap, smtp, opts)
            # Good job should have been processed (result sent)
            self.assertTrue(any(b"good-1" in m for m in smtp.sent))

    def test_concurrent_poison_writers(self):
        """Finding: threads writing garbage while poll_once runs must not crash."""
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "workers": 2,
            }
            stop = threading.Event()

            def poison():
                while not stop.is_set():
                    try:
                        with open(os.path.join(d, "senses.jsonl"), "a") as f:
                            f.write("garbage\n")
                        with open(os.path.join(d, "board.json"), "w") as f:
                            f.write("[]")
                        time.sleep(0.001)
                    except Exception:
                        pass

            t = threading.Thread(target=poison, daemon=True)
            t.start()
            good = sign_payload({
                "v": 2, "type": "job", "job_id": "concurrent-good",
                "issued_at": _now(),
                "kind": "exec",
                "script": "echo survived",
            }, SECRET)
            imap = _FakeIMAP([_mail("[HOMING-PIGEON] job concurrent-good", good)])
            smtp = _FakeSMTP()
            opts = mock.Mock(dry_run=False, no_send=False)
            try:
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"), imap, smtp, opts)
            finally:
                stop.set()
                t.join(timeout=1)
            self.assertTrue(any(b"concurrent-good" in m for m in smtp.sent))

    def test_oracle_answer_queries_with_poisoned_senses(self):
        """Finding: answer_queries 'senses' op must not crash on corrupt store."""
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "senses.jsonl"), "w").write(
                '{"sensor":"x","severity":"high","title":"ok"}\n'
                "not-json\n"
                '{"sensor":null,"severity":[],"detail":[1,2]}\n'
            )
            cfg = {"sensors": {"x": {"enabled": True, "key_id": "k", "weight": 1.0}}}
            answers, spent = answer_queries(
                [{"op": "senses", "sensor": "x"}],
                {"exit_code": 0, "stdout": ""},
                _redact_patterns(cfg),
                10,
                cfg,
                base_dir=d,
            )
            self.assertIsInstance(answers, list)
            self.assertGreaterEqual(spent, 1)

    def test_board_concurrent_bad_tasks(self):
        """Finding: concurrent submit/claim of malformed tasks must not raise."""
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            errors = []

            def worker():
                try:
                    board.submit({"task_id": None, "priority": "bad"})
                    board.submit({"task_id": "ok", "capabilities": [1, 2]})
                    board.offer("w1", [], "k")
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

    def test_resources_and_dri_poison(self):
        """Finding: check_resources and maybe_page tolerate garbage state files."""
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "resources.json"), "w").write("{invalid")
            cfg = {"resources": {"enabled": True, "threshold": 0.5}}
            # Must not raise
            resources.check_resources(cfg, d)
            dri.maybe_page(cfg, d)


if __name__ == "__main__":
    unittest.main()
