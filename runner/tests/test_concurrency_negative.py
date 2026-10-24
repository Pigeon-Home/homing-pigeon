#!/usr/bin/env python3
"""Concurrency and extreme negative tests for agent + Oracle.

Findings (2026-10-15):

- A raising handle_mail is logged ("worker raised") but does NOT
  re-raise from poll_once. Sibling jobs still run. Cycle completes.

- Poisoned board data under concurrent offer() does not crash.

- Extreme / wrong-type query payloads do not crash answer_queries.

- Extreme sensor-alert detail shapes are rejected or accepted cleanly.

- load_alerts returns [] on a non-UTF-8 senses.jsonl instead of
  raising UnicodeDecodeError (corrupt store cannot stop processing).
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import poll_once, handle_mail, Board, answer_queries  # noqa: E402
from runner.cloud.send_job import sign_payload  # noqa: E402

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _job_email(job_id, kind="ping", **extra):
    payload = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": _now(), "kind": kind,
    }
    payload.update(extra)
    msg = EmailMessage()
    msg["Subject"] = f"[HOMING-PIGEON] job {job_id}"
    msg["From"] = "si@example.com"
    msg.set_content(sign_payload(payload, SECRET))
    return msg.as_bytes()


class ConcurrencyNegativeTest(unittest.TestCase):
    def test_one_worker_raising_does_not_stop_the_poll(self):
        """Finding: a raising handle_mail is logged and swallowed.
        poll_once returns. Sibling jobs still execute."""
        with tempfile.TemporaryDirectory() as d:
            seen = {}
            calls = []
            original = handle_mail

            def tracking(*args, **kwargs):
                raw = args[4]
                text = raw.decode("utf-8", errors="replace")
                if "job crash-me" in text:
                    calls.append("crash")
                    raise RuntimeError("injected crash")
                calls.append("ok")
                return original(*args, **kwargs)

            class FakeIMAP:
                def search(self, *a):
                    return "OK", [b"1 2"]
                def fetch(self, num, spec):
                    n = int(num)
                    if n == 1:
                        raw = _job_email("crash-me")
                    else:
                        raw = _job_email("good-one")
                    return "OK", [(b"1 (RFC822)", raw)]
                def store(self, *a):
                    return "OK", []
                def logout(self):
                    return "OK", []

            cfg = {
                "mailbox_user": "t@example.com",
                "mailbox_password": "x",
                "shared_secret": SECRET,
                "workers": 2,
            }
            with patch("runner.runner.handle_mail", tracking):
                poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                          imap=FakeIMAP(), smtp=MagicMock(),
                          opts=type("O", (), {"dry_run": False, "no_send": True, "workers": 2})())
            self.assertIn("crash", calls)
            self.assertIn("ok", calls)

    def test_poisoned_board_concurrent_offers(self):
        """Board with mixed bad task shapes under concurrent access must not crash."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            bad = {
                "tasks": {
                    "1": "not-a-dict",
                    "2": {"task_id": 123, "state": "open", "capabilities": "not-list"},
                    "3": {"task_id": "good", "state": "open", "capabilities": [1, None, "ok"]},
                    "4": None,
                }
            }
            with open(path, "w") as fh:
                json.dump(bad, fh)
            board = Board(path)
            from concurrent.futures import ThreadPoolExecutor
            def offer():
                return board.offer("worker", ["ok"], "key", {"worker_compartments": {}})
            with ThreadPoolExecutor(4) as ex:
                results = list(ex.map(lambda _: offer(), range(8)))
            self.assertTrue(all(r is None or isinstance(r, dict) for r in results))

    def test_extreme_query_data(self):
        """Oracle answer path must tolerate extreme / wrong-type data."""
        exec_result = {"stdout": None, "stderr": 42, "exit_code": "x",
                       "confined": "maybe", "digest": None}
        queries = [
            {"op": "attest", "predicate": "exit_zero"},
            {"op": "grep", "pattern": ".*"},
            {"op": "tail", "lines": "not-int"},
            {"op": "ask", "question": None},
            {"op": "unknown"},
            "not-a-dict",
        ]
        answers, spent = answer_queries(queries, exec_result, [], 10)
        self.assertIsInstance(answers, list)
        self.assertGreaterEqual(spent, 0)

    def test_sensor_alert_extreme_detail(self):
        """Bad detail shapes must be rejected or accepted without raising."""
        from runner.oracle import senses as S
        extremes = [
            {"detail": None},
            {"detail": "string-not-object"},
            {"detail": [1, 2, 3]},
            {"detail": {"nested": {"deep": "x" * 10000}}},
            {"detail": {"binaryish": "\x00\x01\x02"}},
        ]
        for extra in extremes:
            job = {
                "v": 1, "type": "job", "kind": "sensor_alert",
                "job_id": "a", "issued_at": _now(),
                "sensor": "s1", "severity": "info", "title": "t",
            }
            job.update(extra)
            bad = S.validate_sensor_alert(job)
            self.assertTrue(bad is None or isinstance(bad, str))

    def test_load_alerts_survives_non_utf8_store(self):
        """Finding: load_alerts returns [] on non-UTF-8 senses.jsonl
        instead of raising UnicodeDecodeError."""
        from runner.oracle import senses as S
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "senses.jsonl")
            with open(path, "wb") as f:
                f.write(b"\xff\xfe corrupt\n{\"ok\":1}\n")
            alerts = S.load_alerts(d)
            self.assertEqual(alerts, [])


if __name__ == "__main__":
    unittest.main()
