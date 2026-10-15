#!/usr/bin/env python3
"""Concurrency and deeper negative tests for agent + Oracle.

Goals:
- One bad worker must not prevent other jobs in the same poll from running.
- Extreme bad data from extensions / retained / board must not crash the poll.
- Document findings: current design logs the worker exception and re-raises
  from poll_once, but the main loop catches it and continues the daemon.
  Other concurrent jobs still complete.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import poll_once, handle_mail, Board  # noqa: E402
from cloud.send_job import sign_payload  # noqa: E402

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
    def test_one_worker_raising_does_not_block_sibling_jobs(self):
        """Finding: a raising handle_mail is logged and re-raised after the
        pool drains. Sibling jobs still execute. Daemon loop catches the
        cycle failure and continues."""
        with tempfile.TemporaryDirectory() as d:
            seen = {}
            calls = []
            original = handle_mail

            def tracking(*args, **kwargs):
                # args: cfg, imap, smtp, seq, raw, base_dir, seen, secrets, opts, key_policies
                raw = args[4]
                # crude extract of job_id from subject in raw
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
                with self.assertRaises(RuntimeError):
                    poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                              imap=FakeIMAP(), smtp=MagicMock(),
                              opts=type("O", (), {"dry_run": False, "no_send": True, "workers": 2})())
            self.assertIn("crash", calls)
            self.assertIn("ok", calls)
            # good job should have been processed (seen or at least called)
            self.assertTrue(any("ok" in c for c in calls))

    def test_poisoned_board_concurrent_offers(self):
        """Board with mixed bad task shapes under concurrent access must not crash."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            # poison: list, numbers, None, nested garbage
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
            # concurrent offers
            from concurrent.futures import ThreadPoolExecutor
            def offer():
                return board.offer("worker", ["ok"], "key", {"worker_compartments": {}})
            with ThreadPoolExecutor(4) as ex:
                results = list(ex.map(lambda _: offer(), range(8)))
            # must not raise; some offers may return None or a task
            self.assertTrue(all(r is None or isinstance(r, dict) for r in results))

    def test_extreme_retained_and_query_data(self):
        """Oracle answer path must tolerate extreme / wrong-type retained data."""
        from runner.runner import answer_queries, load_retained
        with tempfile.TemporaryDirectory() as d:
            # write garbage retained
            retained_path = os.path.join(d, "retained", "bad-job.json")
            os.makedirs(os.path.dirname(retained_path), exist_ok=True)
            with open(retained_path, "w") as fh:
                fh.write('{"stdout": null, "stderr": [1,2,3], "exit_code": "nope"}')
            # also a non-json file
            with open(os.path.join(d, "retained", "worse.json"), "w") as fh:
                fh.write("not json at all {{{")
            # queries against a synthetic exec_result with bad types
            exec_result = {"stdout": None, "stderr": 42, "exit_code": "x", "confined": "maybe", "digest": None}
            queries = [
                {"op": "attest", "predicate": "exit_zero"},
                {"op": "grep", "pattern": ".*"},
                {"op": "tail", "lines": "not-int"},
                {"op": "ask", "question": None},
                {"op": "unknown"},
                "not-a-dict",
            ]
            # should not raise
            answers, spent = answer_queries(queries, exec_result, [], 10)
            self.assertIsInstance(answers, list)
            self.assertGreaterEqual(spent, 0)

    def test_sensor_alert_with_extreme_detail(self):
        """Bad detail shapes must be rejected or stored without crashing ingest."""
        from runner import senses as S
        cfg = {"sensors": {"s1": {"enabled": True, "key_id": "k1", "weight": 1}}}
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
            # either rejected cleanly or accepted; never raise
            self.assertTrue(bad is None or isinstance(bad, str))


if __name__ == "__main__":
    unittest.main()
