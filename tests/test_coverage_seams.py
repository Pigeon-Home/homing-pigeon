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


class _Body:
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ExchangeCodeTest(unittest.TestCase):
    def _opener(self, raw, seen):
        def opener(req, timeout=30):
            seen.append((req.data, timeout))
            return _Body(raw)
        return opener

    def test_refresh_token_is_returned(self):
        import urllib.parse
        from runner.oauth import exchange_code

        seen = []
        token = exchange_code(
            {"oauth_client_id": "cid", "oauth_client_secret": "sek"},
            "code", "ver", opener=self._opener(b'{"refresh_token":"rtok"}', seen))
        self.assertEqual(token, "rtok")
        form = urllib.parse.parse_qs(seen[0][0].decode("ascii"))
        self.assertEqual(form["client_secret"], ["sek"])
        self.assertEqual(form["code"], ["code"])
        self.assertEqual(form["code_verifier"], ["ver"])
        self.assertEqual(form["grant_type"], ["authorization_code"])
        self.assertEqual(seen[0][1], 30)

    def test_secret_is_omitted_when_empty(self):
        import urllib.parse
        from runner.oauth import exchange_code

        seen = []
        exchange_code(
            {"oauth_client_id": "cid"},
            "code", "ver", opener=self._opener(b'{"refresh_token":"rtok"}', seen))
        form = urllib.parse.parse_qs(seen[0][0].decode("ascii"))
        self.assertNotIn("client_secret", form)

    def test_http_error_with_bad_json_is_system_exit(self):
        import io
        import urllib.error
        from runner.oauth import TOKEN_URL, exchange_code

        def opener(req, timeout=30):
            raise urllib.error.HTTPError(
                TOKEN_URL, 400, "bad", {}, io.BytesIO(b"not-json"))

        with self.assertRaises(SystemExit):
            exchange_code({"oauth_client_id": "cid"}, "code", "ver", opener=opener)

    def test_a_list_body_is_system_exit(self):
        from runner.oauth import exchange_code

        with self.assertRaises(SystemExit):
            exchange_code(
                {"oauth_client_id": "cid"}, "code", "ver",
                opener=self._opener(b"[1]", []))

    def test_missing_refresh_token_is_system_exit(self):
        from runner.oauth import exchange_code

        with self.assertRaises(SystemExit):
            exchange_code(
                {"oauth_client_id": "cid"}, "code", "ver",
                opener=self._opener(b'{"access_token":"x"}', []))


