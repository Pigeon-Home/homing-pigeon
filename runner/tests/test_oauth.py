"""Tests for runner/wire/oauth.py token exchange error reporting."""
import http.client
import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
from unittest import mock

from runner.wire import oauth
from runner.wire.oauth import exchange_code


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
        from runner.wire.oauth import OAuthRefreshError, refresh_access_token

        with unittest.mock.patch(
                "runner.wire.oauth.urllib.request.urlopen",
                side_effect=_http_error(b"<html>")):
            with self.assertRaises(OAuthRefreshError) as ctx:
                refresh_access_token({
                    "oauth_client_id": "x",
                    "oauth_refresh_token": "r",
                    "oauth_client_secret": "s",
                })
        self.assertIn("Re-run", str(ctx.exception))

    def test_a_refresh_without_a_token_is_refused(self):
        from runner.wire.oauth import OAuthRefreshError, refresh_access_token

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
                "runner.wire.oauth.urllib.request.urlopen",
                return_value=Resp(b"[]")):
            with self.assertRaises(OAuthRefreshError) as ctx:
                refresh_access_token({
                    "oauth_client_id": "x", "oauth_refresh_token": "r"})
        self.assertIn("non-object", str(ctx.exception))
        with unittest.mock.patch(
                "runner.wire.oauth.urllib.request.urlopen",
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
        from runner.wire.oauth import refresh_access_token

        class Resp:
            def read(self):
                return b'{"access_token": "ya29.token"}'
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        with mock.patch("runner.wire.oauth.urllib.request.urlopen",
                        return_value=Resp()):
            token = refresh_access_token({
                "oauth_client_id": "x",
                "oauth_refresh_token": "r",
            })
        self.assertEqual(token, "ya29.token")

    def test_a_failed_write_does_not_leave_the_token(self):
        from runner.wire.oauth import store_refresh_token
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            with mock.patch("runner.wire.oauth.os.replace",
                            side_effect=OSError("full")):
                with self.assertRaises(OSError):
                    store_refresh_token(path, {"auth": "password"}, "tok")
            with open(path, encoding="utf-8") as fh:
                self.assertNotIn("tok", fh.read())
            leftovers = [n for n in os.listdir(d) if ".tmp." in n]
            self.assertEqual(leftovers, [])

    def test_main_refuses_a_symlink_and_a_token_with_a_newline(self):
        from runner.wire import oauth
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


class BrowserConsentLoopTests(unittest.TestCase):
    """The listener behind browser_consent, against the field
    failures of 2026-10-22: the old one-shot listener let the
    first stray hit end the sign-in (the real redirect then had
    nowhere to land), and its stuck accept thread held the port
    so the setup wizard's retry died with "address already in
    use". The consent runs in a thread against a real socket,
    with the browser and the token exchange stubbed out."""

    CFG = {"oauth_client_id": "cid"}

    def _free_port(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def _run_consent(self, port, wait_sec=None, read_timeout=None):
        box = {}
        opened = []

        def fake_open(url, **kwargs):
            opened.append(url)
            return True

        def fake_exchange(cfg, code, verifier, opener=None):
            box["exchanged_code"] = code
            return "refresh-token"

        patches = [
            mock.patch.object(oauth, "REDIRECT_PORT", port),
            mock.patch.object(oauth.webbrowser, "open", fake_open),
            mock.patch.object(oauth, "exchange_code", fake_exchange),
        ]
        if wait_sec is not None:
            patches.append(
                mock.patch.object(oauth, "_CONSENT_WAIT_SEC", wait_sec))
        if read_timeout is not None:
            patches.append(mock.patch.object(
                oauth, "_REQUEST_READ_TIMEOUT_SEC", read_timeout))
        for p in patches:
            p.start()

        def target():
            try:
                box["token"] = oauth.browser_consent(self.CFG)
            except SystemExit as e:
                box["exit"] = str(e)
            finally:
                for p in patches:
                    p.stop()

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        deadline = time.time() + 5
        while not opened and time.time() < deadline:
            thread.join(0.05)
        self.assertTrue(opened, "the browser was never opened")
        state = urllib.parse.parse_qs(
            urllib.parse.urlparse(opened[0]).query)["state"][0]
        return thread, box, state

    def _get(self, port, path):
        last = None
        for _ in range(40):
            conn = http.client.HTTPConnection("127.0.0.1", port,
                                              timeout=5)
            try:
                conn.request("GET", path)
                resp = conn.getresponse()
                resp.read()
                return resp.status
            except ConnectionRefusedError as e:
                last = e
                time.sleep(0.05)
            finally:
                conn.close()
        raise last

    def test_stray_and_stale_hits_do_not_end_the_wait(self):
        port = self._free_port()
        thread, box, state = self._run_consent(port)
        self.assertEqual(self._get(port, "/favicon.ico"), 200)
        self.assertEqual(
            self._get(port, "/?state=stale-state&code=old-code"), 200)
        self.assertTrue(thread.is_alive())
        self.assertEqual(
            self._get(port, f"/?state={state}&code=real-code"), 200)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(box.get("token"), "refresh-token")
        self.assertEqual(box.get("exchanged_code"), "real-code")

    def test_a_stale_error_does_not_end_the_wait(self):
        port = self._free_port()
        thread, box, state = self._run_consent(port)
        self.assertEqual(
            self._get(port, "/?state=other&error=access_denied"), 200)
        self.assertTrue(thread.is_alive())
        self.assertEqual(
            self._get(port, f"/?state={state}&error=access_denied"),
            200)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertIn("access_denied", box.get("exit", ""))

    def test_only_strays_until_the_deadline_frees_the_port(self):
        port = self._free_port()
        thread, box, state = self._run_consent(port, wait_sec=1.5)
        self.assertEqual(self._get(port, "/favicon.ico"), 200)
        self.assertEqual(
            self._get(port, "/?state=stale&code=old-code"), 200)
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertIn("no sign-in code received", box.get("exit", ""))
        # The port must be usable again immediately: the setup
        # wizard's retry is a second consent on the same port.
        server = oauth.HTTPServer(("127.0.0.1", port), oauth._Catch)
        server.server_close()

    def test_back_to_back_consents_reuse_the_port(self):
        port = self._free_port()
        for _ in range(2):
            thread, box, state = self._run_consent(port)
            self.assertEqual(
                self._get(port, f"/?state={state}&code=the-code"),
                200)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(box.get("token"), "refresh-token")

    def test_a_stalled_connection_does_not_block_the_callback(self):
        port = self._free_port()
        thread, box, state = self._run_consent(port, read_timeout=0.5)
        stalled = socket.create_connection(("127.0.0.1", port),
                                           timeout=5)
        try:
            # The stalled connection sends nothing (a browser
            # preconnect). The real callback queues behind it and
            # must still land once the read deadline drops it.
            self.assertEqual(
                self._get(port, f"/?state={state}&code=real-code"),
                200)
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            self.assertEqual(box.get("token"), "refresh-token")
            self.assertEqual(box.get("exchanged_code"), "real-code")
        finally:
            stalled.close()


if __name__ == "__main__":
    unittest.main()
