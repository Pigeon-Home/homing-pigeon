#!/usr/bin/env python3
"""Replay bodies captured from the Gmail connector round-trip.

These are the real payloads from docs/connector-roundtrip.md. They lock
in: a happy-path ping verifies and runs, a signature marker inside a
script field does not confuse the verifier, and a preamble (the note we
put above the JSON in the test mail) makes verification fail.
"""

import os
import sys
import tempfile
import unittest
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner.runner import (  # noqa: E402
    execute_job,
    poll_once,
    verify_body,
)

SECRET = "test-shared-secret"

# Exact JSON line from message 1a1380ce30ccfbfb.
HAPPY_PING = (
    '{"v":1,"type":"job","job_id":"c142d598-261a-4000-8a41-b8cb7d28bf38",'
    '"issued_at":"2026-10-14T01:35:25Z","kind":"ping",'
    '"sig":"3e175d607fe637e5ba40bf0e104dd402253cc1a76869de6ef09d921e3dd13f6b68673b1719edf84025a19562fd8c876f"}'
)

# Exact JSON line from message 1a1380e84018aa6a (sig marker inside script).
SIG_IN_SCRIPT = (
    '{"v":1,"type":"job","job_id":"f62b9568-47fe-403e-8124-f9e06d5baed2",'
    '"issued_at":"2026-10-14T01:36:50Z","kind":"exec",'
    '"script":"echo \\",\\"sig\\":\\"deadbeef",'
    '"sig":"8d6722e9b89a96036e68a03c038677fde70cff0573b09f88564549220267b227beeebfcbc6f727285c5727f2ab5f1b61"}'
)

# Exact JSON line from message 1a1380e8aa70b40a (uppercase hex).
UPPER_SIG = (
    '{"v":1,"type":"job","job_id":"4653829a-a53a-44ba-85d5-90d52a73b980",'
    '"issued_at":"2026-10-14T01:36:50Z","kind":"ping",'
    '"sig":"4D75BB2FDBB3B3E966F5571C08D361CB5EE3DE7385412D5B35480E9D75CDEB2D3B222A83E0E81A0B02AE37637547A57B"}'
)

HAPPY_PREAMBLE = (
    "Homing Pigeon connector pipeline test. Safe to ignore or delete.\n\n"
    + HAPPY_PING
    + "\n"
)


class FakeIMAP:
    def __init__(self, mails):
        self.mails = list(mails)
        self.flagged = []

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

    def send_message(self, msg):
        self.sent.append(msg)

    def quit(self):
        pass


class ConnectorCaptureTests(unittest.TestCase):
    def test_happy_ping_verifies(self):
        job = verify_body(HAPPY_PING, SECRET)
        self.assertEqual(job["job_id"], "c142d598-261a-4000-8a41-b8cb7d28bf38")
        self.assertEqual(job["kind"], "ping")

    def test_happy_ping_executes(self):
        job = verify_body(HAPPY_PING, SECRET)
        base = tempfile.mkdtemp(prefix="hp-cap-")
        r = execute_job({"default_timeout_sec": 10}, job, base)
        self.assertEqual(r["exit_code"], 0)
        self.assertEqual(r["stdout"], "pong")

    def test_happy_ping_through_poll(self):
        # Rebuild a runner-legal mail from the captured payload: pure JSON
        # body and a subject the runner accepts.
        job = verify_body(HAPPY_PING, SECRET)
        msg = EmailMessage()
        msg["From"] = "runner@example.com"
        msg["To"] = "runner@example.com"
        msg["Subject"] = "[HOMING-PIGEON] job " + job["job_id"]
        msg.set_content(HAPPY_PING)
        base = tempfile.mkdtemp(prefix="hp-cap-")
        seen = {}
        imap, smtp = FakeIMAP([msg.as_bytes()]), FakeSMTP()
        cfg = {
            "mailbox_user": "runner@example.com",
            "mailbox_password": SECRET,
            "max_job_age_sec": 10**9,  # captured issued_at is in the past
        }
        poll_once(cfg, base, seen, os.path.join(base, "seen.json"),
                  imap=imap, smtp=smtp)
        self.assertEqual(len(smtp.sent), 1)
        result = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "pong")
        self.assertIn(job["job_id"], seen)

    def test_sig_marker_inside_script_still_verifies(self):
        job = verify_body(SIG_IN_SCRIPT, SECRET)
        self.assertEqual(job["job_id"], "f62b9568-47fe-403e-8124-f9e06d5baed2")
        self.assertIn("sig", job["script"])

    def test_uppercase_sig_rejected(self):
        with self.assertRaises(ValueError):
            verify_body(UPPER_SIG, SECRET)

    def test_preamble_breaks_verification(self):
        # The note we put above the JSON in the real test mail is not
        # part of the signed content. Full body_text must not verify.
        with self.assertRaises(ValueError):
            verify_body(HAPPY_PREAMBLE, SECRET)


if __name__ == "__main__":
    unittest.main(verbosity=2)
