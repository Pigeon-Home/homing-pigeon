"""Tests for runner/oauth.py token exchange error reporting."""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

from runner.oauth import exchange_code


def _http_error(payload: bytes, code: int = 400) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://oauth2.googleapis.com/token", code, "Bad Request", {},
        io.BytesIO(payload))


class ExchangeCodeErrorDescriptionTests(unittest.TestCase):
    def test_error_description_included(self):
        # Google's error_description says WHY; the old message swallowed it
        # and showed only the bare error code.
        body = json.dumps({
            "error": "invalid_request",
            "error_description": "Missing required parameter: code",
        }).encode("utf-8")

        def opener(req, timeout=30):
            raise _http_error(body)

        with self.assertRaises(SystemExit) as ctx:
            exchange_code({"oauth_client_id": "x"}, "code", "verifier",
                          opener=opener)
        msg = str(ctx.exception)
        self.assertIn("invalid_request", msg)
        self.assertIn("Missing required parameter: code", msg)

    def test_description_matching_code_not_duplicated(self):
        body = json.dumps({
            "error": "invalid_grant",
            "error_description": "invalid_grant",
        }).encode("utf-8")

        def opener(req, timeout=30):
            raise _http_error(body)

        with self.assertRaises(SystemExit) as ctx:
            exchange_code({"oauth_client_id": "x"}, "code", "verifier",
                          opener=opener)
        self.assertEqual(str(ctx.exception),
                         "token exchange failed (HTTP 400: invalid_grant)")

    def test_unparseable_body_still_reports(self):
        def opener(req, timeout=30):
            raise _http_error(b"<html>not json</html>")

        with self.assertRaises(SystemExit) as ctx:
            exchange_code({"oauth_client_id": "x"}, "code", "verifier",
                          opener=opener)
        self.assertIn("HTTP 400", str(ctx.exception))


class RefreshAndExchangeShapeTest(unittest.TestCase):
    def test_an_unparseable_refresh_error_still_says_relogin(self):
        from runner.oauth import OAuthRefreshError, refresh_access_token

        with unittest.mock.patch(
                "runner.oauth.urllib.request.urlopen",
                side_effect=_http_error(b"<html>")):
            with self.assertRaises(OAuthRefreshError) as ctx:
                refresh_access_token({
                    "oauth_client_id": "x",
                    "oauth_refresh_token": "r",
                    "oauth_client_secret": "s",
                })
        self.assertIn("Re-run", str(ctx.exception))

    def test_a_refresh_without_a_token_is_refused(self):
        from runner.oauth import OAuthRefreshError, refresh_access_token

        class Resp:
            def __init__(self, body):
                self._body = body
            def read(self):
                return self._body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        with unittest.mock.patch(
                "runner.oauth.urllib.request.urlopen",
                return_value=Resp(b"[]")):
            with self.assertRaises(OAuthRefreshError) as ctx:
                refresh_access_token({
                    "oauth_client_id": "x", "oauth_refresh_token": "r"})
        self.assertIn("non-object", str(ctx.exception))
        with unittest.mock.patch(
                "runner.oauth.urllib.request.urlopen",
                return_value=Resp(b"{}")):
            with self.assertRaises(OAuthRefreshError) as ctx:
                refresh_access_token({
                    "oauth_client_id": "x", "oauth_refresh_token": "r"})
        self.assertIn("access_token", str(ctx.exception))

    def test_an_exchange_that_is_not_an_object_exits(self):
        class Resp:
            def __init__(self, body):
                self._body = body
            def read(self):
                return self._body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        def opener(req, timeout=30):
            return Resp(b"not-json")

        with self.assertRaises(SystemExit) as ctx:
            exchange_code({"oauth_client_id": "x"}, "code", "v", opener=opener)
        self.assertIn("unparseable", str(ctx.exception))

        def opener_list(req, timeout=30):
            return Resp(b"[]")

        with self.assertRaises(SystemExit) as ctx:
            exchange_code({"oauth_client_id": "x", "oauth_client_secret": "s"},
                          "code", "v", opener=opener_list)
        self.assertIn("non-object", str(ctx.exception))

        def opener_empty(req, timeout=30):
            return Resp(b"{}")

        with self.assertRaises(SystemExit) as ctx:
            exchange_code({"oauth_client_id": "x"}, "code", "v",
                          opener=opener_empty)
        self.assertIn("refresh_token", str(ctx.exception))

    def test_a_refresh_returns_the_access_token(self):
        from runner.oauth import refresh_access_token

        class Resp:
            def read(self):
                return b'{"access_token": "ya29.token"}'
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        with mock.patch("runner.oauth.urllib.request.urlopen",
                        return_value=Resp()):
            token = refresh_access_token({
                "oauth_client_id": "x",
                "oauth_refresh_token": "r",
            })
        self.assertEqual(token, "ya29.token")

    def test_a_failed_write_does_not_leave_the_token(self):
        from runner.oauth import store_refresh_token
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            with mock.patch("runner.oauth.os.replace",
                            side_effect=OSError("full")):
                with self.assertRaises(OSError):
                    store_refresh_token(path, {"auth": "password"}, "tok")
            with open(path, encoding="utf-8") as fh:
                self.assertNotIn("tok", fh.read())
            leftovers = [n for n in os.listdir(d) if ".tmp." in n]
            self.assertEqual(leftovers, [])

    def test_main_refuses_a_symlink_and_a_token_with_a_newline(self):
        from runner import oauth
        with tempfile.TemporaryDirectory() as d:
            real = os.path.join(d, "real.json")
            with open(real, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            link = os.path.join(d, "link.json")
            os.symlink(real, link)
            with mock.patch.object(sys, "argv", ["oauth", "--config", link]):
                self.assertEqual(oauth.main(), 2)
            cfg = os.path.join(d, "ok.json")
            with open(cfg, "w", encoding="utf-8") as fh:
                json.dump({"oauth_client_id": "cid"}, fh)
            err = io.StringIO()
            with mock.patch.object(sys, "argv", ["oauth", "--config", cfg]), \
                    mock.patch.object(oauth, "browser_consent",
                                      return_value="bad\ntoken"), \
                    mock.patch.object(sys, "stderr", err):
                self.assertEqual(oauth.main(), 2)
            self.assertIn("config error", err.getvalue())
            with open(cfg, encoding="utf-8") as fh:
                self.assertNotIn("refresh", fh.read())


if __name__ == "__main__":
    unittest.main()
