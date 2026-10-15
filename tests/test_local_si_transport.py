#!/usr/bin/env python3
"""Transport coverage for the mock SI. No live SMTP, no live model."""
import os
import sys
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner"))

import local_test as LT


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


class SocketTransportTest(unittest.TestCase):
    def test_roundtrip(self):
        cfg = {}
        t = LT.LocalSocketTransport(cfg, port=0)
        # bind to ephemeral by using a high port we control
        t.port = 18766
        with mock.patch.object(LT, "answer_as_oracle",
                               return_value={"answer": "pong"}):
            t.start()
            try:
                got = t.send("ping?")
            finally:
                t.stop()
        self.assertEqual(got, "pong")

    def test_reject_roundtrip(self):
        t = LT.LocalSocketTransport({}, port=18767)
        with mock.patch.object(LT, "answer_as_oracle",
                               return_value={"rejected": "inference_unconfigured"}):
            t.start()
            try:
                got = t.send("q")
            finally:
                t.stop()
        self.assertIn("rejected", got)

    def test_loopback_only_bind(self):
        t = LT.LocalSocketTransport({}, port=18768)
        t.start()
        try:
            self.assertEqual(t._sock.getsockname()[0], "127.0.0.1")
        finally:
            t.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)
