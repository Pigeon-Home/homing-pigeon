#!/usr/bin/env python3
"""Board / dispatcher tests (v3 Piece 2)."""
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

SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
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
