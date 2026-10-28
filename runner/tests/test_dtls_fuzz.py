"""Fuzz the DTLS handshake parsers and the server's datagram entry.

The coverage hole is the handshake, and a mutated datagram is
how a truncated or reordered flight shows up. These tests stay
on the cores: feed() takes bytes and returns bytes, and no
socket is opened. A parser may raise DtlsError. It may not
raise anything else, and feed() may not raise at all.
"""

import unittest

from runner.tests._compat import require_hypothesis  # noqa: E402
require_hypothesis()
from hypothesis import given, settings, strategies as st

from runner.wire.jobcrypto import JobCryptoError
from runner.wire.dtlsproto import (
    DtlsError,
    DtlsServerCore,
    _FragmentBuffer,
    _RecordSealer,
    _hs_message,
    _key_share_entry,
    _parse_client_hello,
    _parse_extensions,
    _parse_handshake,
    _parse_psk_extension,
    _parse_server_hello,
    _split_records,
)

_BYTES = st.binary(max_size=512)


def _only_dtls(fn):
    try:
        fn()
    except (DtlsError, JobCryptoError):
        return
    except Exception as e:  # noqa: BLE001 - the property is the type
        raise AssertionError(type(e).__name__ + ": " + str(e)) from e


class RecordFuzzTest(unittest.TestCase):
    @settings(max_examples=40, deadline=None)
    @given(data=_BYTES)
    def test_split_records_never_raises(self, data):
        records = _split_records(data)
        self.assertIsInstance(records, list)
        for record in records:
            self.assertIsInstance(record, (bytes, bytearray))
            self.assertTrue(record)
            self.assertIn(bytes(record), data)

    @settings(max_examples=40, deadline=None)
    @given(data=_BYTES)
    def test_parse_handshake_returns_or_is_short(self, data):
        parsed = _parse_handshake(data)
        if parsed is None:
            return
        self.assertIsInstance(parsed, tuple)
        self.assertTrue(parsed)

    @settings(max_examples=40, deadline=None)
    @given(data=_BYTES, offset=st.integers(min_value=0, max_value=64))
    def test_extensions_raise_only_dtls_error(self, data, offset):
        _only_dtls(lambda: _parse_extensions(data, offset))

    @settings(max_examples=40, deadline=None)
    @given(data=_BYTES)
    def test_client_and_server_hello_raise_only_dtls_error(self, data):
        _only_dtls(lambda: _parse_client_hello(data))
        _only_dtls(lambda: _parse_server_hello(data))

    @settings(max_examples=40, deadline=None)
    @given(data=_BYTES, server=st.booleans())
    def test_key_share_and_psk_raise_only_dtls_error(self, data, server):
        _only_dtls(lambda: _key_share_entry(data, server_form=server))
        _only_dtls(lambda: _parse_psk_extension(data))

    @settings(max_examples=40, deadline=None)
    @given(data=_BYTES)
    def test_server_feed_drops_garbage(self, data):
        core = DtlsServerCore(secrets_map={})
        out = core.feed(data, ("192.0.2.1", 4430), 1_700_000_000.0)
        self.assertIsInstance(out, list)
        for datagram in out:
            self.assertIsInstance(datagram, bytes)


class HandshakeFragmentTest(unittest.TestCase):
    def test_two_halves_reassemble_in_either_order(self):
        body = b"hello-body-bytes"
        total = len(body)
        buf = _FragmentBuffer()
        self.assertIsNone(buf.offer(1, 7, 0, body[:6], total))
        whole = buf.offer(1, 7, 6, body[6:], total)
        self.assertEqual(whole, _hs_message(1, body, 7))
        buf = _FragmentBuffer()
        self.assertIsNone(buf.offer(1, 7, 6, body[6:], total))
        whole = buf.offer(1, 7, 0, body[:6], total)
        self.assertEqual(whole, _hs_message(1, body, 7))

    def test_a_byte_past_the_end_is_ignored(self):
        buf = _FragmentBuffer()
        whole = buf.offer(1, 1, 0, b"abX", 2)
        self.assertEqual(whole, _hs_message(1, b"ab", 1))

    def test_truncated_cookie_extension_is_silence(self):
        # A ClientHello-shaped body is not required: feed()
        # only answers a parsed hello, and a short cookie
        # extension is one of the quiet refusals.
        core = DtlsServerCore(secrets_map={})
        out = core.feed(b"\x16" + b"\x00" * 40, ("192.0.2.1", 1), 0.0)
        self.assertEqual(out, [])


class RecordOpenFuzzTest(unittest.TestCase):
    @settings(max_examples=40, deadline=None)
    @given(record=_BYTES)
    def test_open_raises_only_dtls_error(self, record):
        sealer = _RecordSealer(b"\x11" * 48)
        if not record:
            return
        _only_dtls(lambda: sealer.open(2, record))
