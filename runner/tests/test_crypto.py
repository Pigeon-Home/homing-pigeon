#!/usr/bin/env python3
"""Unit tests for the HMAC-SHA-384 sign/verify scheme shared by runner and cloud.

These exercise the pure crypto functions without IMAP/SMTP or subprocess.
"""

import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import sign_payload, verify_body  # noqa: E402


class CryptoTest(unittest.TestCase):
    SECRET = "unit-test-secret-384"

    def test_roundtrip_simple(self):
        payload = {"v": 1, "type": "job", "job_id": "abc-123", "kind": "ping"}
        signed = sign_payload(payload, self.SECRET)
        recovered = verify_body(signed, self.SECRET)
        self.assertEqual(recovered["kind"], "ping")
        self.assertEqual(recovered["job_id"], "abc-123")
        self.assertNotIn("sig", recovered)

    def test_unicode_payload(self):
        payload = {"msg": "héllo 🌍", "n": 42}
        signed = sign_payload(payload, self.SECRET)
        self.assertEqual(verify_body(signed, self.SECRET)["msg"], "héllo 🌍")

    def test_crlf_normalized(self):
        payload = {"a": 1}
        signed = sign_payload(payload, self.SECRET)
        # Simulate mail transport converting to CRLF
        crlf = signed.replace("\n", "\r\n")
        self.assertEqual(verify_body(crlf, self.SECRET)["a"], 1)

    def test_trailing_whitespace_ignored(self):
        payload = {"ok": True}
        signed = sign_payload(payload, self.SECRET) + "\n\n  "
        self.assertTrue(verify_body(signed, self.SECRET)["ok"])

    def test_wrong_secret_rejected(self):
        signed = sign_payload({"x": 1}, self.SECRET)
        with self.assertRaises(ValueError) as cm:
            verify_body(signed, "wrong-secret")
        self.assertIn("signature mismatch", str(cm.exception))

    def test_tampered_body_rejected(self):
        signed = sign_payload({"kind": "ping"}, self.SECRET)
        tampered = signed.replace('"ping"', '"pong"')
        with self.assertRaises(ValueError):
            verify_body(tampered, self.SECRET)

    def test_missing_sig_rejected(self):
        with self.assertRaises(ValueError) as cm:
            verify_body('{"a":1}', self.SECRET)
        self.assertIn("no signature marker", str(cm.exception))

    def test_malformed_sig_tail_rejected(self):
        # Valid structure but bad hex length
        bad = '{"a":1,"sig":"abc"}'
        with self.assertRaises(ValueError) as cm:
            verify_body(bad, self.SECRET)
        self.assertIn("malformed signature tail", str(cm.exception))

    def test_non_object_rejected_on_sign(self):
        # json.dumps of a list does not end with }
        with self.assertRaises(ValueError):
            sign_payload(["not", "an", "object"], self.SECRET)  # type: ignore

    def test_constant_time_compare_used(self):
        # Just confirm that a mismatch raises; we cannot easily observe
        # timing, but the code path uses hmac.compare_digest.
        signed = sign_payload({"k": "v"}, self.SECRET)
        # Flip one hex digit in the signature
        idx = signed.rfind('"sig":"') + 7
        flipped = signed[:idx] + ("0" if signed[idx] != "0" else "1") + signed[idx+1:]
        with self.assertRaises(ValueError):
            verify_body(flipped, self.SECRET)


if __name__ == "__main__":
    unittest.main(verbosity=2)
