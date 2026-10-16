import io
import json
import os
import tempfile
import unittest
from unittest import mock


class PkceTest(unittest.TestCase):
    def test_challenge_is_s256_of_the_verifier(self):
        import base64
        import hashlib
        from runner.oauth import _pkce

        verifier, challenge = _pkce()
        self.assertIsInstance(verifier, str)
        self.assertIsInstance(challenge, str)
        self.assertTrue(verifier)
        self.assertTrue(challenge)
        self.assertNotEqual(verifier, challenge)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        self.assertEqual(challenge, expected)

    def test_two_calls_do_not_reuse_the_verifier(self):
        from runner.oauth import _pkce

        first, _ = _pkce()
        second, _ = _pkce()
        self.assertNotEqual(first, second)
