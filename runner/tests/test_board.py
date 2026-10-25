#!/usr/bin/env python3
"""Board / dispatcher tests (v3 Piece 2)."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner.wire import jobcrypto
from runner.runner import Board, poll_once
from send_job import sign_payload
from runner.tests.test_runner import FakeIMAP, FakeSMTP

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

    def test_a_failed_save_closes_its_fd_and_removes_the_tmp(self):
        # Queue A refill: Board.save's cleanup legs
        # (coverage run 40189608702: lines 139-142 on
        # both platforms; the two flag lines beside them
        # are the platform pair). The save's own comment
        # fixes the shape: unique tmp, never written
        # through a symlink. A failure after the tmp is
        # open must not leak the descriptor or leave the
        # tmp behind, and a failing close is swallowed
        # the same way.
        from unittest import mock
        self.b.submit({"task_id": "t1"})
        opened, closed = [], []
        real_open, real_close = os.open, os.close

        def tracking_open(path, flags, mode=0o777, **kw):
            fd = real_open(path, flags, mode, **kw)
            opened.append(fd)
            return fd

        def tracking_close(fd):
            closed.append(fd)
            return real_close(fd)

        def broken_close(fd):
            # close() releases the descriptor even when it reports
            # a failure; so does this fake, or the tmp stays open
            # and Windows refuses to unlink it (build-windows,
            # 2026-10-25).
            closed.append(fd)
            real_close(fd)
            raise OSError("close failed")

        with mock.patch.object(os, "open", tracking_open), \
                mock.patch.object(os, "close", tracking_close), \
                mock.patch.object(
                    os, "fdopen",
                    side_effect=OSError("cannot wrap")):
            self.b.save()
        # Every descriptor opened was closed. As a set: the WARN
        # line's own log file may open and close between the tmp's
        # open and its close, depending on what ran before.
        self.assertEqual(sorted(opened), sorted(closed))
        # Only the board submit() already saved; no tmp
        # is left, and the failed save did not replace it.
        self.assertEqual(os.listdir(self.tmp), ["board.json"])
        self.assertIn("t1", Board(self.path).tasks)

        with mock.patch.object(os, "open", tracking_open), \
                mock.patch.object(os, "close", broken_close), \
                mock.patch.object(
                    os, "fdopen",
                    side_effect=OSError("cannot wrap")):
            self.b.save()
        self.assertEqual(os.listdir(self.tmp), ["board.json"])
        self.assertIn("t1", Board(self.path).tasks)


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
    signed = sign_payload(payload, SECRET)
    ident = subject.rsplit(" ", 1)[-1]
    key_id = payload.get("key_id") if isinstance(payload, dict) else ""
    wire = jobcrypto.encrypt_body(
        signed, SECRET, job_id=ident, key_id=key_id or "",
        sign=sign_payload)
    msg.set_content(wire)
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
        # No reply_to on any of these: every reply goes to the
        # runner's own mailbox.
        self.assertTrue(all(m["To"] == SENDER for m in smtp.sent))

    def test_board_replies_follow_a_signed_reply_to(self):
        # The same routing rule as results (PROTOCOL 3.1 / 13.7): a
        # valid reply_to inside the signed body receives the offer or
        # ack; an invalid one falls back to the runner mailbox.
        issued = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mails = [
            _board_mail("[HOMING-PIGEON] task_submit t-rt", {
                "v": 1, "type": "task_submit", "task_id": "t-rt",
                "issued_at": issued, "capabilities": ["py"],
                "payload": {"kind": "ping"},
                "reply_to": "submitter@example.com",
            }),
            _board_mail("[HOMING-PIGEON] task_request w-rt", {
                "v": 1, "type": "task_request", "issued_at": issued,
                "capabilities": ["py"],
                "reply_to": "worker@example.com",
            }),
            _board_mail("[HOMING-PIGEON] task_result t-rt", {
                "v": 1, "type": "task_result", "issued_at": issued,
                "result": {"ok": True},
                "reply_to": "not an address, and a comma,",
            }),
        ]
        smtp = FakeSMTP()
        poll_once(self.cfg, self.tmp, {}, self.seen_path,
                  imap=FakeIMAP(mails), smtp=smtp)
        pairs = [(m["Subject"], m["To"]) for m in smtp.sent]
        acks = [to for s, to in pairs if "task_ack t-rt" in s]
        offers = [to for s, to in pairs if "task_offer t-rt" in s]
        self.assertEqual(offers, ["worker@example.com"])
        self.assertIn("submitter@example.com", acks)   # the submit ack
        self.assertIn(SENDER, acks)                     # the result ack
