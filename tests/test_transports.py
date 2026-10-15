#!/usr/bin/env python3
"""Transport contract tests. No live network."""
import os
import sys
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import transports as T


class ContractTest(unittest.TestCase):
    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            T.get_transport("nope", {})

    def test_only_email_and_cloudflare(self):
        for name in ("nats", "mqtt", "redis", "postgres", "durable_objects",
                     "local_socket"):
            with self.assertRaises(ValueError):
                T.get_transport(name, {})
        cf = T.get_transport("cloudflare", {})
        self.assertEqual(cf.name, "cloudflare")
        email = T.get_transport("email", {}, runner_mod=object())
        self.assertEqual(email.name, "email")


class EmailTransportTest(unittest.TestCase):
    def test_send_uses_runner(self):
        sent = {}

        class R:
            @staticmethod
            def connect_smtp(cfg):
                return mock.Mock()
            @staticmethod
            def send_mail(smtp, cfg, subject, body):
                sent["subject"] = subject
                sent["body"] = body

        t = T.EmailTransport({}, R)
        t.send("job-1", '{"v":1}')
        self.assertIn("job-1", sent["subject"])
        self.assertEqual(sent["body"], '{"v":1}')


class CloudflareTransportTest(unittest.TestCase):
    def test_missing_token_raises(self):
        t = T.CloudflareQueuesTransport({})
        with self.assertRaises(RuntimeError):
            t.send("q", "blob")

    def test_send_posts_blob(self):
        captured = {}

        class Resp:
            def read(self):
                return b'{"success":true}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def opener(req, timeout=30):
            captured["url"] = req.full_url
            captured["body"] = req.data
            return Resp()

        cfg = {"cf_account_id": "acct", "cf_api_token": "tok", "cf_queue_id": "qid"}
        t = T.CloudflareQueuesTransport(cfg, opener=opener)
        t.send("q", '{"v":1}')
        self.assertIn("/accounts/acct/queues/qid/messages", captured["url"])
        self.assertIn(b"v", captured["body"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
