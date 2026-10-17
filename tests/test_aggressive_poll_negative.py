#!/usr/bin/env python3
"""Aggressive concurrent negative simulation of poll_once.

Finding: many workers processing a mix of good jobs, poisoned sensor
alerts, malformed board messages, and concurrent writers to senses/
board/resources/query_times must not crash the cycle. A trailing good
job still produces a result.
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

from runner.runner import poll_once, sign_payload  # noqa: E402

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _MultiIMAP:
    def __init__(self, raws):
        self.raws = list(raws)
        self.seen = set()

    def search(self, *a):
        ids = [str(i + 1).encode() for i in range(len(self.raws)) if i not in self.seen]
        return "OK", [b" ".join(ids)] if ids else [b""]

    def fetch(self, num, what):
        return "OK", [(b"1 (RFC822)", self.raws[int(num) - 1])]

    def store(self, num, *a):
        self.seen.add(int(num) - 1)
        return "OK", []


class _SMTP:
    def __init__(self):
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg.as_bytes() if hasattr(msg, "as_bytes") else b"")


class AggressivePollNegative(unittest.TestCase):
    def test_many_workers_poison_mix(self):
        with tempfile.TemporaryDirectory() as d:
            # Poison stores
            open(os.path.join(d, "senses.jsonl"), "w").write("not-json\n[1]\n")
            open(os.path.join(d, "board.json"), "w").write("[]")
            open(os.path.join(d, "resources.json"), "w").write("null")
            open(os.path.join(d, "query_times.json"), "w").write("{bad")

            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "workers": 8,
                "sensors": {"door": {"enabled": True, "key_id": "k1", "weight": 1.0}},
            }
            raws = []
            # Poisoned alerts and bad jobs
            for i in range(6):
                body = sign_payload({
                    "v": 2, "type": "job", "job_id": f"bad-{i}",
                    "kind": "sensor_alert", "issued_at": _now(),
                    "sensor": "door", "severity": 999, "title": None,
                    "detail": [1, 2],
                }, SECRET)
                raws.append(_mail(f"[HOMING-PIGEON] job bad-{i}", body))
            # Good jobs
            for i in range(3):
                body = sign_payload({
                    "v": 2, "type": "job", "job_id": f"good-{i}",
                    "kind": "exec", "issued_at": _now(),
                    "script": "echo ok",
                }, SECRET)
                raws.append(_mail(f"[HOMING-PIGEON] job good-{i}", body))

            stop = threading.Event()
            def poison():
                while not stop.is_set():
                    try:
                        open(os.path.join(d, "senses.jsonl"), "a").write("garbage\n")
                        open(os.path.join(d, "board.json"), "w").write("[1]")
                    except Exception:
                        pass
                    time.sleep(0.001)
            t = threading.Thread(target=poison, daemon=True)
            t.start()

            imap = _MultiIMAP(raws)
            smtp = _SMTP()
            opts = mock.Mock(dry_run=False, no_send=False)
            try:
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"), imap, smtp, opts)
            finally:
                stop.set()
                t.join(timeout=1)
            # At least one good result
            self.assertTrue(any(b"good-" in m for m in smtp.sent))


if __name__ == "__main__":
    unittest.main()
