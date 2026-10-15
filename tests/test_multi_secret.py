#!/usr/bin/env python3
"""Multi-secret key_id tests (v3 Piece 1)."""
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

from runner.runner import build_secrets, verify_body_keyed, poll_once, validate_shared_secret
from send_job import sign_payload, verify_body

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
OTHER = "f293c686da58b28fc08f44e13d722e6c0533a94e08c0ae6cb20f2aa1be1a74bf"
SENDER = "runner@example.com"


class MultiSecretTest(unittest.TestCase):
    def test_build_secrets_default(self):
        cfg = {"shared_secret": SECRET}
        s = build_secrets(cfg)
        self.assertEqual(s[""], SECRET)
        self.assertEqual(len(s), 1)

    def test_build_secrets_additional(self):
        cfg = {"shared_secret": SECRET, "additional_secrets": {"worker1": OTHER}}
        s = build_secrets(cfg)
        self.assertEqual(s["worker1"], OTHER)

    def test_build_rejects_weak(self):
        with self.assertRaises(RuntimeError):
            build_secrets({"shared_secret": "short"})

    def test_verify_keyed_default(self):
        payload = {"v": 1, "type": "job", "job_id": "x", "kind": "ping"}
        body = sign_payload(payload, SECRET)
        got, kid = verify_body_keyed(body, {"": SECRET})
        self.assertEqual(kid, "")
        self.assertEqual(got["kind"], "ping")

    def test_verify_keyed_named(self):
        payload = {"v": 1, "type": "job", "job_id": "x", "kind": "ping", "key_id": "worker1"}
        body = sign_payload(payload, OTHER)
        got, kid = verify_body_keyed(body, {"": SECRET, "worker1": OTHER})
        self.assertEqual(kid, "worker1")

    def test_unknown_key_rejected_before_crypto(self):
        payload = {"v": 1, "type": "job", "job_id": "x", "kind": "ping", "key_id": "nope"}
        body = sign_payload(payload, OTHER)
        with self.assertRaises(ValueError) as cm:
            verify_body_keyed(body, {"": SECRET})
        self.assertIn("unknown key_id", str(cm.exception))

    def test_tamper_rejected(self):
        payload = {"v": 1, "type": "job", "job_id": "x", "kind": "ping"}
        body = sign_payload(payload, SECRET).replace('"ping"', '"p1ng"')
        with self.assertRaises(ValueError):
            verify_body_keyed(body, {"": SECRET})


if __name__ == "__main__":
    unittest.main(verbosity=2)
