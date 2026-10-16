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


class AuthorizeUrlTest(unittest.TestCase):
    def test_url_carries_the_pkce_and_offline_params(self):
        import urllib.parse
        from runner.oauth import AUTH_URL, REDIRECT_URI, SCOPE, build_authorize_url

        url = build_authorize_url(
            {"oauth_client_id": "cid"}, "ver", "chal", "st")
        self.assertTrue(url.startswith(AUTH_URL + "?"))
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(query["client_id"], ["cid"])
        self.assertEqual(query["redirect_uri"], [REDIRECT_URI])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["scope"], [SCOPE])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent"])
        self.assertEqual(query["code_challenge"], ["chal"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["state"], ["st"])

    def test_a_second_state_is_not_the_first(self):
        import urllib.parse
        from runner.oauth import build_authorize_url

        first = build_authorize_url({}, "ver", "chal", "one")
        second = build_authorize_url({}, "ver", "chal", "two")
        q1 = urllib.parse.parse_qs(
            urllib.parse.urlparse(first).query, keep_blank_values=True)
        q2 = urllib.parse.parse_qs(urllib.parse.urlparse(second).query)
        self.assertEqual(q1["state"], ["one"])
        self.assertEqual(q2["state"], ["two"])
        self.assertEqual(q1["client_id"], [""])

