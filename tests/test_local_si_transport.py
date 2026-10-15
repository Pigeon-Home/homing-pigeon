#!/usr/bin/env python3
"""Transport coverage for the mock SI. No live SMTP, no live model."""
import os
import sys
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import local_test as LT


class EmailTransportTest(unittest.TestCase):
    def test_no_secret(self):
        self.assertIn("shared_secret", LT.send_via_email({}, "q"))

    def test_sends_with_config(self):
        cfg = {
            "shared_secret": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "smtp_host": "smtp.example",
            "smtp_port": 587,
            "mailbox_user": "a@b.c",
        }
        sent = {}

        class FakeSMTP:
            def quit(self):
                sent["quit"] = True

        def connect(c):
            sent["cfg"] = c
            return FakeSMTP()

        def send_mail(smtp, c, subject, body):
            sent["subject"] = subject
            sent["body"] = body

        with mock.patch.object(LT.R, "connect_smtp", side_effect=connect), \
             mock.patch.object(LT.R, "send_mail", side_effect=send_mail):
            status = LT.send_via_email(cfg, "why?")
        self.assertIn("emailed job", status)
        self.assertIn("[HOMING-PIGEON] job", sent["subject"])
        self.assertIn("why?", sent["body"])
        self.assertTrue(sent["quit"])

    def test_smtp_failure_is_reported(self):
        cfg = {"shared_secret": "x" * 64}
        with mock.patch.object(LT.R, "connect_smtp", side_effect=OSError("down")):
            status = LT.send_via_email(cfg, "q")
        self.assertIn("email send failed", status)



if __name__ == "__main__":
    unittest.main(verbosity=2)
