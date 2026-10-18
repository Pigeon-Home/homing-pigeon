#!/usr/bin/env python3
"""Board / dispatcher tests (v3 Piece 2)."""
import json
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "cloud"))

from runner.runner import Board, poll_once
from send_job import sign_payload
from tests.test_runner import SECRET, SENDER, FakeIMAP, FakeSMTP

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
SENDER = "runner@example.com"


class BoardUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "board.json")
        self.b = Board(self.path)

    def test_submit_and_offer(self):
        ok, _ = self.b.submit({"task_id": "t1", "priority": 5, "capabilities": ["py"]})
        self.assertTrue(ok)
        offered = self.b.offer("w1", ["py"])
        self.assertEqual(offered["task_id"], "t1")
        self.assertEqual(offered["state"], "claimed")

    def test_duplicate_rejected(self):
        self.b.submit({"task_id": "t1"})
        ok, reason = self.b.submit({"task_id": "t1"})
        self.assertFalse(ok)
        self.assertIn("duplicate", reason)

    def test_complete_idempotent(self):
        self.b.submit({"task_id": "t1"})
        self.b.offer("w1", [])
        status, _ = self.b.complete("t1", {"ok": True})
        self.assertEqual(status, "done")
        status2, _ = self.b.complete("t1", {"ok": True})
        self.assertEqual(status2, "duplicate")

    def test_priority_order(self):
        self.b.submit({"task_id": "low", "priority": 1})
        self.b.submit({"task_id": "high", "priority": 10})
        offered = self.b.offer("w1", [])
        self.assertEqual(offered["task_id"], "high")

    def test_persistence(self):
        self.b.submit({"task_id": "t1"})
        b2 = Board(self.path)
        self.assertIn("t1", b2.tasks)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class BoardConcurrencyTest(unittest.TestCase):
    def test_simultaneous_offers_are_exclusive(self):
        """N concurrent offer() calls must never return the same task."""
        import threading
        tmp = tempfile.mkdtemp()
        b = Board(os.path.join(tmp, "board.json"))
        for i in range(5):
            b.submit({"task_id": f"t{i}", "priority": 1})
        results = []
        lock = threading.Lock()

        def worker(wid):
            offered = b.offer(wid, [])
            with lock:
                results.append(offered["task_id"] if offered else None)

        threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        claimed = [r for r in results if r is not None]
        self.assertEqual(len(claimed), len(set(claimed)), "duplicate task handed to two workers")
        self.assertEqual(len(claimed), 5)


def _board_mail(subject, payload):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = subject
    msg.set_content(sign_payload(payload, SECRET))
    return msg.as_bytes()


class BoardE2ETest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-board-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "base_dir": self.tmp,
            "workers": 1,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def test_poll_once_submit_request_result_done(self):
        issued = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mails = [
            _board_mail("[HOMING-PIGEON] task_submit t-e2e", {
                "v": 1, "type": "task_submit", "task_id": "t-e2e",
                "issued_at": issued, "priority": 3, "capabilities": ["py"],
                "payload": {"kind": "ping"},
            }),
            _board_mail("[HOMING-PIGEON] task_request w1", {
                "v": 1, "type": "task_request", "issued_at": issued,
                "capabilities": ["py"],
            }),
            _board_mail("[HOMING-PIGEON] task_result t-e2e", {
                "v": 1, "type": "task_result", "issued_at": issued,
                "result": {"ok": True},
            }),
        ]
        smtp = FakeSMTP()
        poll_once(self.cfg, self.tmp, {}, self.seen_path,
                  imap=FakeIMAP(mails), smtp=smtp)
        with open(os.path.join(self.tmp, "board.json"), encoding="utf-8") as fh:
            tasks = json.load(fh)
        self.assertEqual(tasks["t-e2e"]["state"], "done")
        subjects = [m["Subject"] for m in smtp.sent]
        self.assertTrue(any("task_ack t-e2e" in s for s in subjects))
        self.assertTrue(any("task_offer t-e2e" in s for s in subjects))
