#!/usr/bin/env python3
"""Concurrency and bad extension data. The poll and the Oracle keep going.

Findings from the simulation this file locks in:

- A resource event that is a string, an int, or a map of words used to
  raise while formatting the log line. No mail in that cycle was read.
- One worker exception used to fail the whole poll after the other
  workers had already finished, so the cycle was reported as failed.
- ask_model returning None, a string, a list, or raising used to drop
  the chat request. A bad answer must be a JSON error, not a dead socket.
- Concurrent sense alerts share one file. The lines must stay valid JSON.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import senses  # noqa: E402
from runner.runner import (  # noqa: E402
    handle_mail,
    make_oracle_server,
    poll_once,
    sign_payload,
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _IMAP:
    def __init__(self, raws):
        self.raws = list(raws)

    def search(self, *a):
        ids = b" ".join(str(i + 1).encode() for i in range(len(self.raws)))
        return "OK", [ids]

    def fetch(self, n, w):
        return "OK", [(b"x", self.raws[int(n) - 1])]

    def store(self, *a, **k):
        return "OK", []


class _SMTP:
    def send_message(self, *a, **k):
        return None


class _Opts:
    dry_run = False
    no_send = True
    workers = 4


def _pings(n=6):
    out = []
    for i in range(n):
        body = sign_payload({
            "v": 1, "type": "job", "job_id": f"ping-{i}",
            "issued_at": _now(), "kind": "ping",
        }, SECRET)
        out.append(_mail(f"[HOMING-PIGEON] job ping-{i}", body))
    return out


def _cfg():
    return {
        "mailbox_user": "pigeon-test@example.com",
        "shared_secret": SECRET,
        "workers": 4,
    }


class BadExtensionTest(unittest.TestCase):
    def test_bad_resource_events_do_not_skip_mail(self):
        shapes = [
            "hot",
            5,
            {"threshold": "high", "resources": {"cpu": "hot"}},
            {"resources": None, "threshold": 0.9},
        ]
        for shape in shapes:
            with tempfile.TemporaryDirectory() as d:
                seen = {}
                with mock.patch("runner.resources.check_resources",
                                return_value=shape), \
                     mock.patch("runner.dri.maybe_page",
                                side_effect=RuntimeError("pager down")):
                    poll_once(_cfg(), d, seen, os.path.join(d, "seen.json"),
                              imap=_IMAP(_pings()), smtp=_SMTP(), opts=_Opts())
                self.assertEqual(len(seen), 6, shape)

    def test_one_worker_crash_does_not_drop_the_others(self):
        with tempfile.TemporaryDirectory() as d:
            seen = {}

            def boom(cfg, imap, smtp, seq, raw, base_dir, seen_map,
                     secrets, opts=None, key_policies=None):
                if str(seq) == "1":
                    raise RuntimeError("extension blew up")
                return handle_mail(cfg, imap, smtp, seq, raw, base_dir,
                                   seen_map, secrets, opts, key_policies)

            with mock.patch("runner.runner.handle_mail", side_effect=boom):
                poll_once(_cfg(), d, seen, os.path.join(d, "seen.json"),
                          imap=_IMAP(_pings()), smtp=_SMTP(), opts=_Opts())
            self.assertNotIn("ping-0", seen)
            self.assertEqual(len(seen), 5)


class OracleBadAnswerTest(unittest.TestCase):
    def test_concurrent_bad_answers_stay_json(self):
        answers = [
            None,
            "nope",
            ["not", "a", "dict"],
            {"answer": {"nested": True}},
            RuntimeError("model socket died"),
            {"answer": "a job finished"},
        ]

        n = len(answers)
        lock = threading.Lock()

        def fake_ask(*a, **k):
            with lock:
                item = answers.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with tempfile.TemporaryDirectory() as d:
            cfg = _cfg()
            cfg["base_dir"] = d
            cfg["inference"] = {
                "endpoint": "http://127.0.0.1:11434/v1",
                "model": "llama3.2:3b",
            }
            httpd = make_oracle_server(cfg, "127.0.0.1", 0)
            port = httpd.socket.getsockname()[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(httpd.shutdown)
            self.addCleanup(httpd.server_close)
            token = httpd.oracle_token
            barrier = threading.Barrier(len(answers))
            codes = []

            def post():
                barrier.wait()
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/ask",
                    data=json.dumps({"question": "what happened?"}).encode(),
                    headers={
                        "Origin": f"http://127.0.0.1:{port}",
                        "Content-Type": "application/json",
                        "X-Oracle-Token": token,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body = json.loads(resp.read().decode())
                    codes.append((resp.status, body))

            with mock.patch("runner.runner.ask_model", side_effect=fake_ask):
                threads = [threading.Thread(target=post) for _ in answers]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=8)
                    self.assertFalse(t.is_alive())
            self.assertEqual(len(codes), n)
            for status, body in codes:
                self.assertEqual(status, 200)
                self.assertTrue("answer" in body or "rejected" in body)


class SenseStoreTest(unittest.TestCase):
    def test_concurrent_alerts_stay_json(self):
        with tempfile.TemporaryDirectory() as d:
            def write(i):
                senses.store_alert(d, {
                    "sensor": "host-ids", "severity": "info",
                    "title": f"t{i}", "detail": {"n": i},
                })

            threads = [threading.Thread(target=write, args=(i,)) for i in range(40)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            rows = senses.load_alerts(d, limit=100)
            self.assertEqual(len(rows), 40)
            self.assertEqual(len({r["title"] for r in rows}), 40)