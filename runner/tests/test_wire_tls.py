"""Tests for runner/wire/tls.py, the shared outbound trust store.

The substrate pinned here is deterministic: which CA file the
context is built with under each condition, read off mocks of the
two ways out (the operator's variable, the bundled file) and of
the context builder itself. Live TLS behaviour is not unit
testable and is not claimed here: the frozen build's certificate
check on a clean machine is proven in the frozen form, on the rig,
and that proof stands with the landing that carries this file.
"""
import os
import ssl
import sys
import unittest
import urllib.request
from unittest import mock

from runner.wire import tls


class CafileChoiceTests(unittest.TestCase):
    def test_the_operator_file_wins_over_the_bundle(self):
        with mock.patch.dict(os.environ,
                             {"SSL_CERT_FILE": "/ops/ca.pem"}), \
                mock.patch.object(tls, "_certifi_cafile",
                                  return_value="/bundled/ca.pem"):
            self.assertEqual("/ops/ca.pem", tls.cafile())

    def test_the_bundle_is_used_when_no_operator_file(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(tls, "_certifi_cafile",
                                  return_value="/bundled/ca.pem"):
            self.assertEqual("/bundled/ca.pem", tls.cafile())

    def test_no_file_when_neither_is_available(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(tls, "_certifi_cafile",
                                  return_value=None):
            self.assertIsNone(tls.cafile())

    def test_an_empty_operator_value_reads_as_unset(self):
        with mock.patch.dict(os.environ, {"SSL_CERT_FILE": ""}), \
                mock.patch.object(tls, "_certifi_cafile",
                                  return_value="/bundled/ca.pem"):
            self.assertEqual("/bundled/ca.pem", tls.cafile())


class CertifiProbeTests(unittest.TestCase):
    def test_a_certifi_that_answers_gives_its_file(self):
        fake = mock.Mock()
        fake.where.return_value = os.path.abspath(__file__)
        with mock.patch.dict(sys.modules, {"certifi": fake}):
            self.assertEqual(os.path.abspath(__file__),
                             tls._certifi_cafile())

    def test_a_certifi_pointing_nowhere_reads_as_absent(self):
        fake = mock.Mock()
        fake.where.return_value = "/no/such/bundle.pem"
        with mock.patch.dict(sys.modules, {"certifi": fake}):
            self.assertIsNone(tls._certifi_cafile())

    def test_a_certifi_that_raises_reads_as_absent(self):
        fake = mock.Mock()
        fake.where.side_effect = RuntimeError("broken passenger")
        with mock.patch.dict(sys.modules, {"certifi": fake}):
            self.assertIsNone(tls._certifi_cafile())

    def test_a_missing_certifi_reads_as_absent(self):
        with mock.patch.dict(sys.modules, {"certifi": None}):
            self.assertIsNone(tls._certifi_cafile())


class SslContextTests(unittest.TestCase):
    def test_the_context_is_built_with_the_chosen_file(self):
        sentinel = object()
        with mock.patch.object(tls, "cafile",
                               return_value="/chosen/ca.pem"), \
                mock.patch.object(tls.ssl, "create_default_context",
                                  return_value=sentinel) as build:
            self.assertIs(sentinel, tls.ssl_context())
        build.assert_called_once_with(cafile="/chosen/ca.pem")

    def test_the_context_is_the_platform_default_without_a_file(self):
        sentinel = object()
        with mock.patch.object(tls, "cafile", return_value=None), \
                mock.patch.object(tls.ssl, "create_default_context",
                                  return_value=sentinel) as build:
            self.assertIs(sentinel, tls.ssl_context())
        build.assert_called_once_with()

    def test_a_real_context_verifies(self):
        ctx = tls.ssl_context()
        self.assertIsInstance(ctx, ssl.SSLContext)
        self.assertEqual(ssl.CERT_REQUIRED, ctx.verify_mode)
        self.assertTrue(ctx.check_hostname)


class _Resp:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class OAuthRoutingTests(unittest.TestCase):
    """The two calls that died in the field open through the helper."""

    def test_the_exchange_opens_with_the_shared_context(self):
        from runner.wire import oauth
        sentinel = object()
        seen = {}

        def fake_urlopen(req, timeout=30, context=None):
            seen["context"] = context
            return _Resp(b'{"refresh_token": "tok"}')

        with mock.patch.object(oauth._tls, "ssl_context",
                               return_value=sentinel), \
                mock.patch("runner.wire.oauth.urllib.request.urlopen",
                           fake_urlopen):
            out = oauth.exchange_code({"oauth_client_id": "x"},
                                      "code", "verifier")
        self.assertEqual("tok", out)
        self.assertIs(sentinel, seen["context"])

    def test_the_refresh_opens_with_the_shared_context(self):
        from runner.wire import oauth
        sentinel = object()
        seen = {}

        def fake_urlopen(req, timeout=30, context=None):
            seen["context"] = context
            return _Resp(b'{"access_token": "ya29.tok"}')

        with mock.patch.object(oauth._tls, "ssl_context",
                               return_value=sentinel), \
                mock.patch("runner.wire.oauth.urllib.request.urlopen",
                           fake_urlopen):
            out = oauth.refresh_access_token({
                "oauth_client_id": "x", "oauth_refresh_token": "r"})
        self.assertEqual("ya29.tok", out)
        self.assertIs(sentinel, seen["context"])


class QueueOpenerTests(unittest.TestCase):
    def test_the_queue_opener_carries_a_verifying_context(self):
        from runner.transport_extensions.queues import __main__ as queues
        https = [h for h in queues._TOKEN_OPENER.handlers
                 if isinstance(h, urllib.request.HTTPSHandler)]
        self.assertEqual(1, len(https))
        self.assertIsNotNone(https[0]._context)
        self.assertEqual(ssl.CERT_REQUIRED,
                         https[0]._context.verify_mode)


if __name__ == "__main__":
    unittest.main()
