#!/usr/bin/env python3
"""End-to-end tests for homing-pigeon.

Drives the real runner.py code against fake IMAP/SMTP servers: no network,
no Gmail. Run with:  python3 -m unittest discover -s tests
or:                  python3 tests/test_runner.py
"""

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

from runner.runner import poll_once  # noqa: E402
from send_job import sign_payload, verify_body  # noqa: E402

SECRET = "test-shared-secret-string"
SENDER = "runner@example.com"


class FakeIMAP:
    def __init__(self, mails):
        self.mails = mails          # list of raw bytes; index 0 -> seq "1"
        self.flagged = []

    def login(self, u, p):
        assert (u, p) == (SENDER, SECRET)
        return ("OK", [])

    def select(self, box):
        return ("OK", [])

    def search(self, *args):
        nums = b" ".join(str(i + 1).encode() for i in range(len(self.mails)))
        return ("OK", [nums])

    def fetch(self, num, _spec):
        raw = self.mails[int(num) - 1]
        head = f"{num.decode()} (RFC822 {{{len(raw)}}}".encode()
        return ("OK", [(head, raw), b")"])

    def store(self, seq, _op, _flags):
        self.flagged.append(seq)
        return ("OK", [])

    def logout(self):
        return ("OK", [])


class FakeSMTP:
    def __init__(self):
        self.sent = []

    def starttls(self):
        pass

    def login(self, u, p):
        assert (u, p) == (SENDER, SECRET)

    def send_message(self, msg):
        self.sent.append(msg)

    def quit(self):
        pass


def job_payload(job_id, **kw):
    p = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": "ping",
    }
    p.update(kw)
    return p


def job_email(payload, secret=SECRET, sender=SENDER):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = sender
    msg["Subject"] = f"[HOMING-PIGEON] job {payload['job_id']}"
    msg.set_content(sign_payload(payload, secret))
    return msg.as_bytes()


def result_body(sent_msg):
    return sent_msg.get_content()


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-test-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": SECRET,
            "imap_host": "fake", "imap_port": 993,
            "smtp_host": "fake", "smtp_port": 587,
            "poll_interval_sec": 20,
            "max_job_age_sec": 3600,
            "max_output_bytes": 100000,
            "base_dir": self.tmp,
            "default_timeout_sec": 300,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def run_cycle(self, mails):
        imap = FakeIMAP(mails)
        smtp = FakeSMTP()
        seen = {}
        poll_once(self.cfg, self.tmp, seen, self.seen_path,
                  imap=imap, smtp=smtp)
        return imap, smtp, seen

    def test_ping_roundtrip(self):
        jid = str(uuid.uuid4())
        _, smtp, seen = self.run_cycle([job_email(job_payload(jid))])
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn(jid, smtp.sent[0]["Subject"])
        result = verify_body(result_body(smtp.sent[0]), SECRET)
        self.assertEqual(result["type"], "result")
        self.assertEqual(result["stdout"], "pong")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn(jid, seen)

    def test_exec_sh(self):
        jid = str(uuid.uuid4())
        p = job_payload(jid, kind="exec", script="echo hello-from-test",
                        interpreter=["sh"])
        _, smtp, _ = self.run_cycle([job_email(p)])
        result = verify_body(result_body(smtp.sent[0]), SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello-from-test", result["stdout"])

    def test_exec_default_interpreter(self):
        jid = str(uuid.uuid4())
        p = job_payload(jid, kind="exec", script="echo default-ok")
        _, smtp, _ = self.run_cycle([job_email(p)])
        result = verify_body(result_body(smtp.sent[0]), SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("default-ok", result["stdout"])

    def test_timeout_kills_tree(self):
        jid = str(uuid.uuid4())
        p = job_payload(jid, kind="exec", script="sleep 30",
                        interpreter=["sh"], timeout_sec=2)
        _, smtp, _ = self.run_cycle([job_email(p)])
        result = verify_body(result_body(smtp.sent[0]), SECRET)
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["exit_code"], -1)

    def test_poison_job_rejected(self):
        jid = str(uuid.uuid4())
        p = job_payload(jid, kind="definitely-not-a-kind")
        imap, smtp, seen = self.run_cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        result = verify_body(result_body(smtp.sent[0]), SECRET)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("rejected", result["stderr"])
        self.assertIn("1", imap.flagged)   # marked seen, not retried
        self.assertIn(jid, seen)

    def test_path_traversal_rejected(self):
        jid = str(uuid.uuid4())
        p = job_payload(jid, kind="exec", script="echo x",
                        files=[{"name": "../evil", "url": "http://example.invalid/x"}])
        _, smtp, _ = self.run_cycle([job_email(p)])
        result = verify_body(result_body(smtp.sent[0]), SECRET)
        self.assertEqual(result["exit_code"], -2)

    def test_any_sender_accepted_with_valid_signature(self):
        # Sender address is not validated; the HMAC signature is the
        # sole authentication gate.
        jid = str(uuid.uuid4())
        mail = job_email(job_payload(jid), sender="attacker@example.com")
        _, smtp, seen = self.run_cycle([mail])
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn(jid, seen)

    def test_tampered_signature_rejected(self):
        jid = str(uuid.uuid4())
        body = sign_payload(job_payload(jid), SECRET).replace(
            '"kind":"ping"', '"kind":"p1ng"')
        msg = EmailMessage()
        msg["From"] = SENDER
        msg["To"] = SENDER
        msg["Subject"] = f"[HOMING-PIGEON] job {jid}"
        msg.set_content(body)
        _, smtp, _ = self.run_cycle([msg.as_bytes()])
        self.assertEqual(len(smtp.sent), 0)

    def test_replay_seen_set(self):
        jid = str(uuid.uuid4())
        mail = job_email(job_payload(jid))
        imap, smtp, seen = self.run_cycle([mail, mail])
        self.assertEqual(len(smtp.sent), 1)  # executed once


if __name__ == "__main__":
    unittest.main(verbosity=2)
