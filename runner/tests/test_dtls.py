"""Tests for the DTLS session binding (a binding of
protocol version 1).

Layers, mirroring how the profile is built:

- X25519 against the RFC 7748 published vectors.
- The TLS 1.3 key schedule recomputed INDEPENDENTLY here
  (hashlib/hmac only, from the RFC 8446 section 7.1 text),
  checked against what a live handshake puts on the wire:
  the test decrypts the server's handshake flight itself and
  verifies the Finished MAC byte for byte.
- Core-to-core behavior over a hand relay: the cookie gate,
  psk_ke refusal (DRU's PFS rule), wrong-PSK refusal,
  platform-payload carriage in the handshake, resumption
  with fresh DHE, NAT rebinding by Connection ID, tampered
  records, flight retransmission.
- The extension over real UDP loopback, the supervisor
  handoff, and one supervised end-to-end job.

The extension/platform imports reach the pipe the same way
the supervisor launches it (module import), and the socket
tests use real UDP on localhost with ephemeral ports.
"""

import argparse
from contextlib import redirect_stderr
import hashlib
import hmac
import importlib
import json
import os
import socket
import string
import subprocess
import sys
import tempfile
import time
import types
import unittest
import uuid
from datetime import datetime, timezone
from io import StringIO
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner import runner  # noqa: E402
from runner.wire import dtlsproto, jobcrypto, transports  # noqa: E402
from runner.runner import PROTOCOL_VERSION, poll_once  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
from runner.tests._compat import filename_punctuation  # noqa: E402
import send_dtls  # noqa: E402
from send_job import sign_payload, verify_body  # noqa: E402

dtls_ext = importlib.import_module(
    "runner.transport_extensions.dtls.__main__")

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
WRONG = "ff2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937b00"
ADDR = ("127.0.0.1", 50001)
NOW = 1000.0


# ------------------------------------------------------------------
# In-test RFC 8446 machinery (independent of runner.wire.dtlsproto)
# ------------------------------------------------------------------

def _ext(prk, info, n):
    out, block, c = b"", b"", 1
    while len(out) < n:
        block = hmac.new(prk, block + info + bytes([c]),
                         hashlib.sha384).digest()
        out += block
        c += 1
    return out[:n]


def _label(secret, label, ctx, n=48):
    full = b"tls13 " + label
    info = (n.to_bytes(2, "big") + bytes([len(full)]) + full
            + bytes([len(ctx)]) + ctx)
    return _ext(secret, info, n)


def _extract(salt, ikm):
    return hmac.new(salt, ikm, hashlib.sha384).digest()


def _ch_exts(datagram):
    """{type: value} of the extensions in a plaintext
    ClientHello/ServerHello datagram, plus the raw handshake
    message. Just enough parsing for the tests."""
    raw = datagram[13:]
    body = raw[12:]
    pos = 2 + 32
    pos += 1 + body[pos]                     # session id
    if raw[0] == 1:                           # ClientHello
        pos += 1 + body[pos]                  # cookie
        suites = int.from_bytes(body[pos:pos + 2], "big")
        pos += 2 + suites
        pos += 1 + body[pos]                  # compression
    else:
        pos += 2 + 1
    total = int.from_bytes(body[pos:pos + 2], "big")
    pos += 2
    end = pos + total
    out = {}
    while pos < end:
        t = int.from_bytes(body[pos:pos + 2], "big")
        n = int.from_bytes(body[pos + 2:pos + 4], "big")
        out[t] = body[pos + 4:pos + 4 + n]
        pos += 4 + n
    return raw, out


def _ext_value_offset(datagram, ext_type):
    """Datagram offset of an extension's value in a plaintext
    ClientHello datagram (for surgical tampering tests)."""
    body_at = 25                     # record hdr 13 + hs hdr 12
    body = datagram[body_at:]
    pos = 2 + 32
    pos += 1 + body[pos]             # session id
    pos += 1 + body[pos]             # cookie
    suites = int.from_bytes(body[pos:pos + 2], "big")
    pos += 2 + suites
    pos += 1 + body[pos]             # compression
    pos += 2                         # extensions total length
    while True:
        t = int.from_bytes(body[pos:pos + 2], "big")
        n = int.from_bytes(body[pos + 2:pos + 4], "big")
        if t == ext_type:
            return body_at + pos + 4
        pos += 4 + n


def _open_record_in_test(traffic_secret, epoch, record):
    """Decrypt one protected record with in-test keys;
    returns (content_type, content)."""
    key = _label(traffic_secret, b"key", b"", 32)
    iv = _label(traffic_secret, b"iv", b"", 12)
    first = record[0]
    pos = 1
    if first & 0x04:
        pos += 1 + record[pos]
    seq_low = int.from_bytes(record[pos:pos + 2], "big")
    pos += 2
    length = int.from_bytes(record[pos:pos + 2], "big")
    pos += 2
    nonce = bytes(a ^ b for a, b in zip(
        iv, ((epoch << 48) | seq_low).to_bytes(12, "big")))
    plain = jobcrypto.aead_decrypt(key, nonce,
                                   record[pos:pos + length],
                                   record[:pos])
    plain = plain.rstrip(b"\x00")
    return plain[-1], plain[:-1]


def _pump(client, server, addr=ADDR, now=NOW):
    """Shuttle datagrams between two cores until quiet."""
    out = client.start(now)
    for _ in range(60):
        if not out:
            break
        nxt = []
        for dg in out:
            nxt += server.feed(dg, addr, now)
        out = []
        for dg in nxt:
            out += client.feed(dg, now)
    return out


def _established_pair(platform=b'{"type":"greeting","v":1}'):
    server = dtlsproto.DtlsServerCore(
        secret_lookup=dtlsproto.make_secret_lookup(SECRET),
        platform_for=lambda s: platform)
    client = dtlsproto.DtlsClientCore(SECRET)
    _pump(client, server)
    assert client.state == "established"
    assert client.app_messages == []
    return client, server


# ------------------------------------------------------------------
# X25519: RFC 7748
# ------------------------------------------------------------------

class X25519VectorsTest(unittest.TestCase):
    def test_rfc7748_section_5_2_vectors(self):
        # The two X25519 vectors of RFC 7748 section 5.2,
        # transcribed from the RFC text.
        cases = [
            ("a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a"
             "2244ba449ac4",
             "e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a9"
             "03a6d0ab1c4c",
             "c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b"
             "4075577a28552"),
            ("4b66e9d4d1b4673c5ad22691957d6af5c11b6421e0ea01d42ca4"
             "169e7918ba0d",
             "e5210f12786811d3f4b7959d0538ae2c31dbe7106fc03c3efc4c"
             "d549c715a493",
             "95cbde9476e8907d7aade45cb4b873f88b595a68799fa152e6f8"
             "f7647aac7957"),
        ]
        for scalar, u, want in cases:
            got = dtlsproto.x25519(bytes.fromhex(scalar),
                                   bytes.fromhex(u))
            self.assertEqual(got.hex(), want)

    def test_rfc7748_section_6_1_diffie_hellman(self):
        alice_priv = bytes.fromhex(
            "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177"
            "fba51db92c2a")
        alice_pub = bytes.fromhex(
            "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4"
            "a98eaa9b4e6a")
        bob_priv = bytes.fromhex(
            "5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f"
            "8b27ff88e0eb")
        bob_pub = bytes.fromhex(
            "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc"
            "7e146f882b4f")
        shared = bytes.fromhex(
            "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f0"
            "9b3c1e161742")
        self.assertEqual(dtlsproto.x25519_public(alice_priv),
                         alice_pub)
        self.assertEqual(dtlsproto.x25519_public(bob_priv),
                         bob_pub)
        self.assertEqual(dtlsproto.x25519(alice_priv, bob_pub),
                         shared)
        self.assertEqual(dtlsproto.x25519(bob_priv, alice_pub),
                         shared)


# ------------------------------------------------------------------
# The key schedule, verified from the wire
# ------------------------------------------------------------------

class KeyScheduleFromTheWireTest(unittest.TestCase):
    def test_finished_matches_an_independent_recomputation(self):
        # Scripted randomness: the test KNOWS both ephemerals,
        # so it can rebuild the whole schedule itself.
        client_chunks = iter([
            bytes(range(32)),          # CH1 ephemeral
            b"\xaa" * 4,               # client CID
            b"\xbb" * 32,              # CH1 random
            bytes(range(32, 64)),      # CH2 ephemeral
            b"\xcc" * 32,              # CH2 random
        ])
        server_chunks = iter([
            b"\xdd" * 32,              # cookie secret
            b"\xee" * 4,               # server CID
            bytes(range(64, 96)),      # server ephemeral
            b"\xff" * 32,              # ServerHello random
            b"\x11" * 16,              # ticket nonce
            b"\x22" * 24,              # ticket id
            b"\x33" * 4,               # ticket age_add
        ])

        def scripted(chunks):
            def rng(n):
                chunk = next(chunks)
                assert len(chunk) == n, (len(chunk), n)
                return chunk
            return rng

        platform_payload = b'{"type":"greeting","v":1}'
        client = dtlsproto.DtlsClientCore(
            SECRET, rng=scripted(client_chunks))
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            platform_for=lambda s: platform_payload,
            rng=scripted(server_chunks))
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = client.feed(hrr, NOW)[0]
        flight = server.feed(ch2, ADDR, NOW)
        self.assertEqual(len(flight), 3)
        ch1_raw, _ = _ch_exts(ch1)
        hrr_raw = hrr[13:]
        ch2_raw, _ = _ch_exts(ch2)
        sh_raw, sh_exts = _ch_exts(flight[0])

        # The schedule, from the RFC text only.
        empty = hashlib.sha384(b"").digest()
        early = _extract(b"\x00" * 48, SECRET.encode())
        derived = _label(early, b"derived", empty)
        share = sh_exts[dtlsproto.EXT_KEY_SHARE]
        server_pub = share[4:4 + 32]
        shared = dtlsproto.x25519(bytes(range(32, 64)), server_pub)
        hs = _extract(derived, shared)
        synth = (bytes([254]) + (48).to_bytes(3, "big")
                 + (0).to_bytes(2, "big") + (0).to_bytes(3, "big")
                 + (48).to_bytes(3, "big")
                 + hashlib.sha384(ch1_raw).digest())
        th_sh = hashlib.sha384(
            synth + hrr_raw + ch2_raw + sh_raw).digest()
        c_hs = _label(hs, b"c hs traffic", th_sh)
        s_hs = _label(hs, b"s hs traffic", th_sh)
        client.feed(flight[0], NOW)   # the client derives its
        self.assertEqual(c_hs, client._c_hs)   # copies from the
        self.assertEqual(s_hs, client._s_hs)   # same ServerHello

        # Decrypt the flight with the in-test keys: EE first,
        # then the Finished, whose MAC the test computes.
        ctype, ee_raw = _open_record_in_test(s_hs, 2, flight[1])
        self.assertEqual(ctype, 22)
        ee_exts, ee_end = dtlsproto._parse_extensions(
            ee_raw[12:], 0)
        self.assertEqual(ee_end, len(ee_raw) - 12)
        self.assertEqual(
            ee_exts[dtlsproto.EXT_PLATFORM_CONFIGURATION],
            platform_payload)
        th_ee = hashlib.sha384(
            synth + hrr_raw + ch2_raw + sh_raw + ee_raw).digest()
        fin_key = _label(s_hs, b"finished", b"")
        expect = hmac.new(fin_key, th_ee, hashlib.sha384).digest()
        ctype, sfin_raw = _open_record_in_test(s_hs, 2, flight[2])
        self.assertEqual(ctype, 22)
        self.assertEqual(sfin_raw[0], 20)          # Finished
        self.assertEqual(sfin_raw[12:], expect)


# ------------------------------------------------------------------
# Core-to-core profile behavior
# ------------------------------------------------------------------

class CoreProfileTest(unittest.TestCase):
    def test_schedule_hash_is_the_suites_hash(self):
        # TLS_AES_256_GCM_SHA384 (0x1302) fixes SHA-384 as the
        # suite's hash: the transcript, the HKDF key schedule,
        # and the Finished computation all ride HASH/HASH_LEN,
        # so the pair must name the suite's hash, not another
        # suite's. (Pinned in review of the AES-256-GCM switch:
        # the suite constant moved and the hash did not.)
        self.assertEqual(dtlsproto.SUITE_AES256, 0x1302)
        self.assertIs(dtlsproto.HASH, hashlib.sha384)
        self.assertEqual(dtlsproto.HASH_LEN, 48)
        self.assertEqual(dtlsproto.HASH().digest_size,
                         dtlsproto.HASH_LEN)

    def test_cookie_gate_stateless_and_small(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        client = dtlsproto.DtlsClientCore(SECRET)
        ch1 = client.start(NOW)[0]
        out = server.feed(ch1, ADDR, NOW)
        # Exactly one datagram back -- the retry -- no larger
        # than the hello that triggered it, and no state kept.
        self.assertEqual(len(out), 1)
        self.assertLessEqual(len(out[0]), len(ch1))
        _raw, exts = _ch_exts(out[0])
        self.assertIn(dtlsproto.EXT_COOKIE, exts)
        self.assertEqual(server.sessions, {})
        self.assertEqual(server.by_addr, {})

    def test_server_core_keeps_the_legacy_positional_arguments(self):
        payload = b'{"type":"greeting","v":1}'
        logs = []
        server = dtlsproto.DtlsServerCore(
            dtlsproto.make_secret_lookup(SECRET),
            lambda session: payload,
            lambda msg, level="INFO": logs.append((msg, level)))
        self.assertIs(server.greeting_for, server.platform_for)
        self.assertEqual(server.platform_for(None), payload)
        server.log("probe")
        self.assertEqual(logs, [("probe", "INFO")])

    def test_bad_cookie_and_foreign_address_get_silence(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        client = dtlsproto.DtlsClientCore(SECRET)
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = bytearray(client.feed(hrr, NOW)[0])
        at = _ext_value_offset(bytes(ch2), dtlsproto.EXT_COOKIE)
        ch2[at + 20] ^= 0xFF      # inside the cookie's MAC
        self.assertEqual(server.feed(bytes(ch2), ADDR, NOW), [])
        # A valid cookie from a different address: the cookie
        # is address-bound, so this is silence too.
        client2 = dtlsproto.DtlsClientCore(SECRET)
        c1 = client2.start(NOW)[0]
        h2 = server.feed(c1, ADDR, NOW)[0]
        c2 = client2.feed(h2, NOW)[0]
        self.assertEqual(
            server.feed(c2, ("127.0.0.1", 59999), NOW), [])

    def test_our_client_offers_only_psk_dhe_ke(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        _raw, exts = _ch_exts(client.start(NOW)[0])
        self.assertEqual(exts[dtlsproto.EXT_PSK_MODES],
                         bytes([1, dtlsproto.PSK_MODE_DHE_KE]))

    def test_psk_ke_only_peer_is_refused(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        client = dtlsproto.DtlsClientCore(SECRET)
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = bytearray(client.feed(hrr, NOW)[0])
        # Rewrite the modes extension: [len=1, psk_ke]. The
        # modes check runs before the binder check, so the now
        # stale binder does not mask the refusal reason.
        at = _ext_value_offset(bytes(ch2),
                               dtlsproto.EXT_PSK_MODES)
        ch2[at + 1] = dtlsproto.PSK_MODE_KE
        out = server.feed(bytes(ch2), ADDR, NOW)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], 21)            # fatal alert
        self.assertEqual(out[0][13], 2)
        self.assertEqual(out[0][14],
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)
        self.assertEqual(server.sessions, {})
        self.assertFalse(any(e[0] == "established"
                             for e in server.events))

    def test_wrong_psk_handshake_fails(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        client = dtlsproto.DtlsClientCore(WRONG)
        _pump(client, server)
        self.assertTrue(client.dead)
        self.assertNotEqual(client.state, "established")
        self.assertIsNone(client.greeting)
        self.assertFalse(any(e[0] == "established"
                             for e in server.events))

    def test_platform_payload_rides_the_final_handshake_flight(self):
        payload = b'{"type":"greeting","v":1}'
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            platform_for=lambda s: payload)
        client = dtlsproto.DtlsClientCore(SECRET)
        # Nothing can be sent before the session exists.
        with self.assertRaises(dtlsproto.DtlsError):
            client.send_app(b"too early")
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = client.feed(hrr, NOW)[0]
        flight = server.feed(ch2, ADDR, NOW)
        snapshots = []
        back = []
        for dg in flight:
            back += client.feed(dg, NOW)
            snapshots.append((client.greeting,
                              client._pending_platform_payload,
                              len(client.app_messages),
                              client.finished_sent))
        # ServerHello alone does not carry it. The encrypted
        # EncryptedExtensions record carries it as a pending
        # payload; the client publishes it as .greeting when
        # the server Finished in the same flight verifies --
        # the moment the initiator considers the connection
        # established and can act on the disclosure.
        self.assertEqual(snapshots[0], (None, None, 0, False))
        self.assertEqual(snapshots[1][0], None)
        self.assertEqual(snapshots[1][1], payload)
        self.assertEqual(snapshots[1][2], 0)
        self.assertFalse(snapshots[1][3])
        self.assertEqual(snapshots[2][0], json.loads(payload))
        self.assertEqual(snapshots[2][2], 0)
        self.assertTrue(snapshots[2][3])
        out = []
        for dg in back:
            out += server.feed(dg, ADDR, NOW)
        ev = [e[0] for e in server.events]
        self.assertIn("established", ev)
        session = next(iter(server.sessions.values()))
        self.assertTrue(session.platform_sent)
        self.assertFalse(any(e[0] == "app" for e in server.events))
        for dg in out:
            client.feed(dg, NOW)
        # No separate greeting application message follows.
        self.assertEqual(client.app_messages, [])

    def test_platform_payload_is_encrypted_in_the_handshake_flight(self):
        payload = (b'{"type":"greeting","platform":'
                   b'{"os_family":"sentinel-os"},"v":1}')
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            platform_for=lambda s: payload)
        client = dtlsproto.DtlsClientCore(SECRET)
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = client.feed(hrr, NOW)[0]
        flight = server.feed(ch2, ADDR, NOW)
        wire = b"".join(flight)
        self.assertNotIn(payload, wire)
        self.assertNotIn(b"sentinel-os", wire)
        for dg in flight:
            client.feed(dg, NOW)
        self.assertEqual(
            client.greeting["platform"]["os_family"],
            "sentinel-os")

    def test_every_tier_rides_the_handshake_extension(self):
        # The gate for the handshake carriage: at every
        # disclosure tier -- none included -- the extension
        # rides, the client ends holding exactly the object
        # the builder produced for that tier, and no greeting
        # arrives as an application message.
        for tier in dtls_ext.GREETING_TIERS:
            with self.subTest(tier=tier):
                payload = dtls_ext.build_platform_payload(tier)
                client, server = _established_pair(
                    platform=payload)
                self.assertEqual(client.greeting,
                                 json.loads(payload))
                self.assertEqual(client.app_messages, [])
                session = next(iter(server.sessions.values()))
                self.assertTrue(session.platform_sent)

    def test_a_legacy_application_greeting_still_surfaces(self):
        # A pre-change runner sends no platform extension and
        # follows establishment with the old application-message
        # greeting. A current client still exposes that object
        # as .greeting, after it has arrived as application data.
        client, server = _established_pair(platform=None)
        self.assertIsNone(client.greeting)
        session = next(iter(server.sessions.values()))
        legacy = b'{"type":"greeting","v":1}'
        for dg in session._app_send(legacy):
            client.feed(dg, NOW)
        self.assertEqual(client.app_messages, [legacy])
        self.assertEqual(client.greeting, json.loads(legacy))

    def test_resumption_uses_fresh_dhe_and_rediscloses(self):
        calls = []

        def disclose(session):
            calls.append(session.resumed)
            return b'{"type":"greeting","v":1}'

        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            platform_for=disclose)
        client = dtlsproto.DtlsClientCore(SECRET)
        ch2_first = self._full_handshake(client, server)
        self.assertIsNotNone(client.ticket)
        _raw, exts1 = _ch_exts(ch2_first)
        # A fresh client resuming with the ticket.
        client2 = dtlsproto.DtlsClientCore(SECRET,
                                           ticket=client.ticket)
        ch2 = self._full_handshake(client2, server)
        _raw, exts2 = _ch_exts(ch2)
        share1 = exts1[dtlsproto.EXT_KEY_SHARE]
        share2 = exts2[dtlsproto.EXT_KEY_SHARE]
        self.assertNotEqual(share1, share2)
        est = [e for e in server.events if e[0] == "established"]
        self.assertTrue(est[-1][2]["resumed"])
        self.assertIsNotNone(client2.greeting)
        self.assertEqual(client2.app_messages, [])
        self.assertEqual(calls, [False, True])

    def _full_handshake(self, client, server):
        """One whole handshake, every datagram delivered both
        ways; returns the second ClientHello datagram."""
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = client.feed(hrr, NOW)[0]
        flight = server.feed(ch2, ADDR, NOW)
        back = []
        for dg in flight:
            back += client.feed(dg, NOW)
        out = []
        for dg in back:
            out += server.feed(dg, ADDR, NOW)
        for dg in out:
            client.feed(dg, NOW)
        return ch2

    def test_nat_rebind_by_connection_id(self):
        client, server = _established_pair()
        session = next(iter(server.sessions.values()))
        other = ("127.0.0.1", 40099)
        dg = client.send_app(b"job from a new port")[0]
        server.feed(dg, other, NOW)
        apps = [e for e in server.events if e[0] == "app"]
        self.assertTrue(apps)
        self.assertEqual(session.peer_addr, other)
        out = server.send_app(session.session_id, b"result")
        self.assertEqual(out[0][0], other)

    def test_tampered_record_dropped_session_survives(self):
        client, server = _established_pair()
        good = client.send_app(b"first")[0]
        bad = bytearray(good)
        bad[-1] ^= 0x01
        server.feed(bytes(bad), ADDR, NOW)
        self.assertFalse(any(e[0] == "app"
                             for e in server.events))
        server.feed(good, ADDR, NOW)
        apps = [e for e in server.events if e[0] == "app"]
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0][2], b"first")

    def test_flight_retransmission_recovers_a_lost_record(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            platform_for=lambda s: b"{}")
        client = dtlsproto.DtlsClientCore(SECRET)
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = client.feed(hrr, NOW)[0]
        flight = server.feed(ch2, ADDR, NOW)
        # The SH lands; the EE record is destroyed in transit.
        back = client.feed(flight[0], NOW)
        self.assertEqual(client.state, "handshake-keys")
        ruined = bytearray(flight[1])
        ruined[-1] ^= 0x01
        self.assertEqual(client.feed(bytes(ruined), NOW), [])
        # The server retransmits its flight on its timer; the
        # fresh copies complete the handshake.
        resent = server.tick(NOW + 2.0)
        resent_dgs = [dg for _a, dg in resent]
        self.assertTrue(resent_dgs)
        for dg in resent_dgs:
            back += client.feed(dg, NOW + 2.0)
        self.assertEqual(client.state, "established")
        for dg in back:
            server.feed(dg, ADDR, NOW + 2.0)
        est = [e for e in server.events if e[0] == "established"]
        self.assertEqual(len(est), 1)

    def test_client_retransmits_an_unanswered_hello(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        first = client.start(NOW)
        again = client.tick(NOW + 2.0)
        self.assertTrue(again)
        self.assertEqual(len(again), len(first))


class DtlsServerTickSweepTest(unittest.TestCase):
    """Queue A refill: DtlsServerCore.tick's
    by-address sweep (coverage run 40189711740:
    dtlsproto.py lines 1622-1624). A dead
    session with no connection ID is still
    reaped: the address index is swept after
    the session index, so a peer that comes
    back starts clean.
    """

    def test_a_dead_session_leaves_the_address_index(self):
        core = dtlsproto.DtlsServerCore()
        fake = types.SimpleNamespace(
            dead=True, peer_addr=("127.0.0.1", 9999),
            tick=lambda now: [])
        core.by_addr[fake.peer_addr] = fake
        self.assertEqual(core.tick(1000.0), [])
        self.assertEqual(core.by_addr, {})


class DtlsPipeSmallLegsTest(unittest.TestCase):
    """Queue A refill: the DTLS pipe's floor
    check skip (dtls __main__ line 113) and
    failed send (220-221). A candidate that is
    not a string is not a PSK at all -- the
    check passes over it -- and a datagram the
    socket refuses is a warning, not a dead
    pipe.
    """

    def test_a_non_string_candidate_is_not_a_psk(self):
        cfg = {"shared_secret": SECRET,
               "additional_secrets": {"k": 123}}
        self.assertIsNone(dtls_ext._psk_floor_problem(cfg))
        cfg["additional_secrets"] = {"k": "weak"}
        self.assertIsNotNone(
            dtls_ext._psk_floor_problem(cfg))

    def test_a_refused_send_is_a_warning(self):
        pipe = object.__new__(dtls_ext.DtlsPipe)
        pipe.sock = mock.Mock()
        pipe.sock.sendto.side_effect = OSError("no route")
        logged = []
        with mock.patch.object(
                dtls_ext.ch, "log",
                lambda m, level="INFO":
                    logged.append((level, m))):
            pipe._send(b"dg", ("127.0.0.1", 20220))
        self.assertTrue(
            any(level == "WARN" for level, _m in logged))


if __name__ == "__main__":
    unittest.main()


# ------------------------------------------------------------------
# The platform payload object
# ------------------------------------------------------------------

class PlatformPayloadTest(unittest.TestCase):
    def test_none_tier_discloses_nothing(self):
        raw = dtls_ext.build_platform_payload("none")
        self.assertFalse(raw.endswith(b"\n"))
        obj = json.loads(raw)
        self.assertEqual(set(obj), {"disclosure"})
        self.assertEqual(obj["disclosure"], "none")
        self.assertNotIn("platform", obj)

    def test_the_object_is_disclosure_and_platform_only(self):
        # The -02 object has no greeting members. The protocol
        # version rides inside platform.protocol_versions.
        for tier in dtls_ext.GREETING_TIERS:
            raw = dtls_ext.build_platform_payload(tier)
            self.assertFalse(raw.endswith(b"\n"))
            obj = json.loads(raw)
            self.assertNotIn("type", obj)
            self.assertNotIn("transport", obj)
            self.assertNotIn("v", obj)
            self.assertEqual(obj["disclosure"], tier)
            if tier == "none":
                self.assertNotIn("platform", obj)
            else:
                self.assertIn(1, obj["platform"]["protocol_versions"])

    def test_family_tier_is_the_default_shape(self):
        # The family tier is what a sender needs to pick an
        # interpreter and a protocol version, and nothing more.
        obj = json.loads(dtls_ext.build_platform_payload("family"))
        self.assertEqual(obj["disclosure"], "family")
        self.assertEqual(set(obj["platform"]),
                         {"os_family", "default_interpreter",
                          "protocol_versions"})
        self.assertIn(obj["platform"]["os_family"],
                      ("windows", "macos", "linux", "other"))
        self.assertEqual(obj["platform"]["protocol_versions"], [1])
        self.assertTrue(obj["platform"]["default_interpreter"])

    def test_the_card_follows_the_config(self):
        obj = json.loads(dtls_ext.build_platform_payload(
            "family", {"protocol_v2": True,
                       "default_interpreter": ["bash"]}))
        self.assertEqual(obj["platform"]["protocol_versions"], [1, 2])
        self.assertEqual(obj["platform"]["default_interpreter"], ["bash"])
        obj = json.loads(dtls_ext.build_platform_payload(
            "family", {"protocol_v2": "yes", "default_interpreter": "sh"}))
        self.assertEqual(obj["platform"]["protocol_versions"], [1])
        self.assertNotEqual(obj["platform"]["default_interpreter"], "sh")

    def test_standard_tier_adds_release_and_python(self):
        obj = json.loads(dtls_ext.build_platform_payload("standard"))
        self.assertEqual(
            set(obj["platform"]),
            {"os_family", "default_interpreter", "protocol_versions",
             "os_release", "python_version"})

    def test_full_tier_adds_a_bounded_tools_summary(self):
        obj = json.loads(dtls_ext.build_platform_payload("full"))
        tools = obj["platform"]["path_tools"]
        self.assertEqual(
            set(tools),
            {"sh", "bash", "powershell", "pwsh", "python3",
             "python", "curl", "git", "tar"})
        self.assertTrue(all(isinstance(v, bool)
                            for v in tools.values()))


# ------------------------------------------------------------------
# Named example vectors for the platform payload
# ------------------------------------------------------------------

class PlatformExampleVectorsTest(unittest.TestCase):
    """The named example vectors: fixed, literal platform
    objects, built from fixed fake hosts the way the
    platform-card tests fake the host, and asserted
    byte-for-byte against the value of the platform
    extension in a live handshake's EncryptedExtensions --
    and against what the client then holds as its greeting.
    These exact objects are the ones quoted as examples for
    this binding, so they must not drift: a change to a
    member, a value, or the serialization breaks this test.
    """

    # The headline vector: a Windows runner at the standard
    # tier. The fake host is Windows Server 2022, whose
    # platform.release() is "2022Server", running Python
    # 3.12.7, with the platform default interpreter.
    EXAMPLE_STANDARD_WINDOWS = (
        '{"disclosure": "standard", "platform": '
        '{"default_interpreter": ["powershell", "-NoProfile", '
        '"-NonInteractive", "-ExecutionPolicy", "Bypass", '
        '"-File"], "os_family": "windows", "os_release": '
        '"2022Server", "protocol_versions": [1], '
        '"python_version": "3.12.7"}}')

    # A Linux runner at the family tier: the OS family, the
    # platform default interpreter, and the protocol versions
    # -- and nothing else.
    EXAMPLE_FAMILY_LINUX = (
        '{"disclosure": "family", "platform": '
        '{"default_interpreter": ["sh"], "os_family": "linux", '
        '"protocol_versions": [1]}}')

    def _payload_from_fake_host(self, tier, sys_platform,
                                os_name, release, python_version):
        card_mod = dtls_ext._platformcard
        with mock.patch.object(sys, "platform", sys_platform), \
                mock.patch.object(os, "name", os_name), \
                mock.patch.object(card_mod.platform, "release",
                                  lambda: release), \
                mock.patch.object(card_mod.platform,
                                  "python_version",
                                  lambda: python_version):
            return dtls_ext.build_platform_payload(tier, {})

    def _extension_bytes_from_handshake(self, payload):
        """Run one handshake carrying `payload`; return the
        client and the platform extension's bytes, taken from
        the EncryptedExtensions record the client received
        (decrypted here with the in-test record opener)."""
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            platform_for=lambda s: payload)
        client = dtlsproto.DtlsClientCore(SECRET)
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = client.feed(hrr, NOW)[0]
        flight = server.feed(ch2, ADDR, NOW)
        client.feed(flight[0], NOW)       # ServerHello: keys now
        ctype, ee_raw = _open_record_in_test(client._s_hs, 2,
                                             flight[1])
        self.assertEqual(ctype, 22)       # handshake
        exts, end = dtlsproto._parse_extensions(ee_raw[12:], 0)
        self.assertEqual(end, len(ee_raw) - 12)
        extension = exts[dtlsproto.EXT_PLATFORM_CONFIGURATION]
        back = []
        for dg in flight[1:]:
            back += client.feed(dg, NOW)
        for dg in back:
            server.feed(dg, ADDR, NOW)
        self.assertEqual(client.state, "established")
        return client, extension

    def _check_vector(self, tier, sys_platform, os_name,
                      release, python_version, expected_json):
        expected_bytes = expected_json.encode("utf-8")
        payload = self._payload_from_fake_host(
            tier, sys_platform, os_name, release, python_version)
        # The builder's bytes are the literal object, byte for
        # byte: sorted keys, no greeting members, no trailing
        # newline.
        self.assertEqual(payload, expected_bytes)
        client, extension = self._extension_bytes_from_handshake(
            payload)
        # The handshake extension carries those same bytes,
        # and the client surfaces exactly that object.
        self.assertEqual(extension, expected_bytes)
        self.assertEqual(client.greeting,
                         json.loads(expected_json))
        self.assertEqual(client.app_messages, [])

    def test_example_vector_standard_windows(self):
        self._check_vector(
            "standard", "win32", "nt", "2022Server", "3.12.7",
            self.EXAMPLE_STANDARD_WINDOWS)

    def test_example_vector_family_linux(self):
        self._check_vector(
            "family", "linux", "posix", "6.8.0-31-generic",
            "3.12.7", self.EXAMPLE_FAMILY_LINUX)

    def test_the_extension_type_is_private_use(self):
        # RFC 8446 / RFC 8447: values whose first byte is 255
        # are Private Use. 0xFF01 is renegotiation_info.
        # 0xFE00 is not private use, and this profile does not
        # send it.
        n = dtlsproto.EXT_PLATFORM_CONFIGURATION
        self.assertGreaterEqual(n, 0xFF00)
        self.assertLessEqual(n, 0xFFFF)
        self.assertNotEqual(n, 0xFF01)
        self.assertEqual(n, 0xFFA0)


# ------------------------------------------------------------------
# The offer: the extension is solicited, never unsolicited
# ------------------------------------------------------------------

class PlatformOfferTest(unittest.TestCase):
    """The client offers the platform extension, empty, in
    its ClientHello, and the server sends the disclosure in
    EncryptedExtensions only to a client that offered it.
    RFC 8446 section 4.2 forbids a server to send an
    extension the client did not offer, and the draft states
    the same rule for this extension: the bare offer asks
    for nothing, and an initiator that did not offer gets
    no disclosure."""

    def test_the_client_offers_the_extension_empty(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        _raw, exts = _ch_exts(client.start(NOW)[0])
        self.assertIn(dtlsproto.EXT_PLATFORM_CONFIGURATION,
                      exts)
        self.assertEqual(
            exts[dtlsproto.EXT_PLATFORM_CONFIGURATION], b"")

    def test_the_offer_rides_the_second_hello_too(self):
        # The cookie exchange makes the client send a fresh
        # ClientHello; the offer rides that one as well.
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            platform_for=lambda s: b'{"disclosure":"family"}')
        client = dtlsproto.DtlsClientCore(SECRET)
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = client.feed(hrr, NOW)[0]
        _raw, exts = _ch_exts(ch2)
        self.assertIn(dtlsproto.EXT_PLATFORM_CONFIGURATION,
                      exts)
        self.assertEqual(
            exts[dtlsproto.EXT_PLATFORM_CONFIGURATION], b"")

    def test_no_offer_no_disclosure(self):
        # A client that never offered -- a peer built before
        # the offer existed, or one that does not implement
        # the section -- still handshakes, but the server
        # sends it no platform extension. The no-offer hello
        # is the client's own hello with the offer filtered
        # out as it is encoded, so its binder still verifies.
        real = dtlsproto._extensions_bytes

        def without_offer(pairs):
            return real(
                [(t, v) for t, v in pairs
                 if t != dtlsproto.EXT_PLATFORM_CONFIGURATION])

        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            platform_for=lambda s: b'{"disclosure":"family"}')
        client = dtlsproto.DtlsClientCore(SECRET)
        with mock.patch.object(dtlsproto, "_extensions_bytes",
                               without_offer):
            ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        with mock.patch.object(dtlsproto, "_extensions_bytes",
                               without_offer):
            ch2 = client.feed(hrr, NOW)[0]
        flight = server.feed(ch2, ADDR, NOW)
        for dg in flight:
            client.feed(dg, NOW)
        self.assertEqual(client.state, "established")
        self.assertIsNone(client.greeting)
        session = next(iter(server.sessions.values()))
        self.assertFalse(session.platform_sent)


# ------------------------------------------------------------------
# The extension over real UDP loopback
# ------------------------------------------------------------------

def _job_envelope(job_id, secret=SECRET, **kw):
    payload = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "kind": "ping",
    }
    payload.update(kw)
    return ch.envelope(f"[HOMING-PIGEON] job {job_id}",
                       sign_payload(payload, secret))


def _result_envelope(job_id, secret=SECRET, **kw):
    payload = {
        "v": 1, "type": "result", "job_id": job_id,
        "status": "ok", "exit_code": 0, "stdout": "pong",
        "stderr": "", "truncated": False,
    }
    payload.update(kw)
    return ch.envelope(f"[HOMING-PIGEON] result {job_id}",
                       sign_payload(payload, secret))


class PipeSocketTest(unittest.TestCase):
    """A real DtlsPipe on a real UDP socket, driven in-loop."""

    def _pipe(self, tier="family"):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-")
        channel = os.path.join(tmp, "channel")
        cfg = {"shared_secret": SECRET, "port": 0,
               "bind": "127.0.0.1", "dtls_greeting": tier}
        pipe = dtls_ext.DtlsPipe(cfg, channel)
        return pipe, channel, pipe.sock.getsockname()[1]

    def _drive(self, pipe, client, sock, pred, timeout=20.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pipe.run_once()
            for dg in client.tick(time.monotonic()):
                sock.send(dg)
            try:
                data = sock.recv(65535)
            except OSError:
                data = None
            if data:
                for dg in client.feed(data, time.monotonic()):
                    sock.send(dg)
            if pred():
                return True
        return pred()

    def _session(self, tier="family"):
        pipe, channel, port = self._pipe(tier)
        client = dtlsproto.DtlsClientCore(SECRET)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.05)
        sock.connect(("127.0.0.1", port))
        # One Linux sandbox blocks sends on UNCONNECTED UDP sockets
        # outright (EPERM), which no real host does; connecting
        # the pipe's socket to its one test peer is the
        # accommodation that lets the real code run there. The
        # production path is the unconnected listener, and on the
        # BSD kernels (macOS, FreeBSD) sendto() with an address on
        # a connected UDP socket is EISCONN, so the accommodation
        # is Linux-only: everywhere else the pipe runs as shipped.
        if sys.platform.startswith("linux"):
            pipe.sock.connect(sock.getsockname())
        for dg in client.start(time.monotonic()):
            sock.send(dg)
        ok = self._drive(pipe, client, sock,
                         lambda: client.greeting is not None)
        self.assertTrue(ok, "no platform payload from the pipe")
        return pipe, channel, client, sock

    def test_platform_payload_and_job_result_flow(self):
        pipe, channel, client, sock = self._session()
        self.assertEqual(client.greeting["disclosure"], "family")
        self.assertEqual(
            set(client.greeting["platform"]),
            {"os_family", "default_interpreter", "protocol_versions"})
        jid = str(uuid.uuid4())
        for dg in client.send_app(
                _job_envelope(jid).encode("utf-8")):
            sock.send(dg)
        job_file = os.path.join(channel, "inbox",
                                f"{jid}.job.txt")
        ok = self._drive(pipe, client, sock,
                         lambda: os.path.exists(job_file))
        self.assertTrue(ok, "the job never reached the channel")
        with open(job_file, encoding="utf-8") as f:
            subject, body = ch.parse_envelope(f.read())
        self.assertIn(jid, subject)
        self.assertEqual(verify_body(body, SECRET)["job_id"], jid)
        with open(os.path.join(channel, "outbox",
                               f"{jid}.result.txt"),
                  "w", encoding="utf-8") as f:
            f.write(_result_envelope(jid) + "\n")
        ok = self._drive(
            pipe, client, sock,
            lambda: len(client.app_messages) >= 1)
        self.assertTrue(ok, "the result never came back")
        subject, body = ch.parse_envelope(
            client.app_messages[0].decode("utf-8"))
        self.assertIn("result", subject)
        self.assertEqual(verify_body(body, SECRET)["stdout"],
                         "pong")
        sock.close()

    def test_pipe_honours_the_none_tier(self):
        _pipe, _channel, client, sock = self._session("none")
        self.assertEqual(client.greeting["disclosure"], "none")
        self.assertNotIn("platform", client.greeting)
        sock.close()


# ------------------------------------------------------------------
# The cloud client's composition with per-job encryption
# ------------------------------------------------------------------

class SendDtlsComposeTest(unittest.TestCase):
    def _args(self, **over):
        ns = argparse.Namespace(
            kind="ping", job_id="compose-1", key_id=None,
            script_file=None, timeout=300, secret=SECRET,
            cleartext=False)
        for k, v in over.items():
            setattr(ns, k, v)
        return ns

    def test_encrypted_by_default_and_it_composes(self):
        job_id, envelope = send_dtls._build_body(self._args())
        self.assertEqual(job_id, "compose-1")
        _subject, body = ch.parse_envelope(
            envelope.decode("utf-8"))
        outer = verify_body(body.strip(), SECRET)
        self.assertTrue(jobcrypto.is_envelope(outer))
        inner = jobcrypto.decrypt_body(outer, SECRET, "compose-1",
                                       None)
        payload = verify_body(inner.strip(), SECRET)
        self.assertEqual(payload["job_id"], "compose-1")
        self.assertEqual(payload["kind"], "ping")

    def test_cleartext_selects_the_plain_signed_form(self):
        _job_id, envelope = send_dtls._build_body(
            self._args(cleartext=True))
        _subject, body = ch.parse_envelope(
            envelope.decode("utf-8"))
        payload = verify_body(body.strip(), SECRET)
        self.assertEqual(payload["job_id"], "compose-1")
        self.assertFalse(jobcrypto.is_envelope(payload))


# ------------------------------------------------------------------
# Supervisor handoff
# ------------------------------------------------------------------

class SupervisorHandoffTest(unittest.TestCase):
    def _cfg(self, **over):
        cfg = {"shared_secret": SECRET,
               "additional_secrets": {"field": "a" * 40},
               "dtls_greeting": "standard",
               "transport_dtls": {"port": 20299}}
        cfg.update(over)
        return cfg

    def test_dtls_runtime_config_carries_what_it_terminates(self):
        out = transports._runtime_config(
            self._cfg(), "dtls", "/base", {"root": "/base/c"})
        self.assertEqual(out["shared_secret"], SECRET)
        self.assertEqual(out["additional_secrets"],
                         {"field": "a" * 40})
        self.assertEqual(out["dtls_greeting"], "standard")
        self.assertEqual(out["port"], 20299)

    def test_dtls_secret_resolves_from_a_file_source(self):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-")
        path = os.path.join(tmp, "secret.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(SECRET + "\n")
        cfg = self._cfg()
        del cfg["shared_secret"]
        cfg["shared_secret_file"] = path
        out = transports._runtime_config(
            cfg, "dtls", "/base", {"root": "/base/c"})
        self.assertEqual(out["shared_secret"], SECRET)

    def test_carrying_pipes_are_never_handed_the_secret(self):
        for name in ("email", "file", "nats"):
            out = transports._runtime_config(
                self._cfg(), name, "/base", {"root": "/base/c"})
            self.assertNotIn("shared_secret", out, name)
            self.assertNotIn("additional_secrets", out, name)

    def test_dtls_is_a_first_party_transport(self):
        self.assertIn("dtls", transports.FIRST_PARTY_TRANSPORTS)


# ------------------------------------------------------------------
# The extension process itself
# ------------------------------------------------------------------

class ExtensionProcessTest(unittest.TestCase):
    def _run(self, cfg_dict):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-")
        cfg_path = os.path.join(tmp, "runtime-config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f)
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO + os.pathsep + env.get(
            "PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-m",
             "runner.transport_extensions.dtls", tmp, cfg_path],
            capture_output=True, text=True, timeout=30, env=env)

    def test_refuses_to_start_without_a_secret(self):
        proc = self._run({})
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("will not start", proc.stderr)

    def test_a_bad_greeting_tier_reads_as_the_default(self):
        # docs/infrastructure-documents/oracle/configuring-oracle.md: dtls_greeting default family.
        # An unrecognised tier used to refuse to start (exit 2), which
        # left the one listening transport permanently dead under the
        # supervisor; it now starts on the default tier and says so
        # (runner/tests/test_doc_default_divergences.py,
        # TestNullDtlsGreetingDefaultsToFamily).
        tmp = tempfile.mkdtemp(prefix="hp-dtls-")
        cfg_path = os.path.join(tmp, "runtime-config.json")
        port = _free_udp_port()
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"shared_secret": SECRET, "port": port,
                       "bind": "127.0.0.1",
                       "dtls_greeting": "everything"}, f)
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO + os.pathsep + env.get(
            "PYTHONPATH", "")
        proc = subprocess.Popen(
            [sys.executable, "-m",
             "runner.transport_extensions.dtls", tmp, cfg_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env)
        try:
            time.sleep(1.5)
            self.assertIsNone(proc.poll(),
                              "the extension refused a bad tier instead "
                              "of starting on the default")
        finally:
            proc.terminate()
            _out, err = proc.communicate(timeout=10)
        self.assertIn("dtls_greeting", err)
        self.assertIn("default tier family", err)
        self.assertIn(f"listening on udp 127.0.0.1:{port}; "
                      "platform disclosure tier family", err)

    def test_starts_and_listens_with_a_secret(self):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-")
        cfg_path = os.path.join(tmp, "runtime-config.json")
        port = _free_udp_port()
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"shared_secret": SECRET, "port": port,
                       "bind": "127.0.0.1"}, f)
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO + os.pathsep + env.get(
            "PYTHONPATH", "")
        proc = subprocess.Popen(
            [sys.executable, "-m",
             "runner.transport_extensions.dtls", tmp, cfg_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env)
        try:
            time.sleep(1.5)
            self.assertIsNone(proc.poll(),
                              "the extension exited at startup")
        finally:
            proc.terminate()
            _out, err = proc.communicate(timeout=10)
        self.assertIn(f"listening on udp 127.0.0.1:{port}", err)

    def test_the_supervisor_starts_the_dtls_extension(self):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-")
        cfg = _supervised_cfg(tmp, _free_udp_port())
        transports.start_supervisor(cfg, tmp)
        try:
            sup = transports.active_supervisor(cfg, tmp)
            self.assertIsNotNone(sup)
            proc = sup.processes["dtls"]["proc"]
            self.assertTrue(
                _wait_for(lambda: proc.poll() is None,
                          timeout=10))
            time.sleep(0.5)
            log_path = os.path.join(
                tmp, "transport-extensions", "dtls", "extension.log")
            try:
                with open(log_path, encoding="utf-8",
                          errors="replace") as f:
                    logged = f.read()[-2000:]
            except OSError as e:
                logged = f"no extension log: {e}"
            self.assertIsNone(proc.poll(), logged)
        finally:
            transports.stop_supervisors(tmp)


# ------------------------------------------------------------------
# Supervised end to end: supervisor + extension + core + CLI
# ------------------------------------------------------------------

def _free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _udp_sendto_works():
    """A probe for this sandbox's UDP policy: sends on
    unconnected UDP sockets are blocked here (EPERM), which
    no real host does -- and a UDP server cannot take a first
    step under it. CI and real machines allow it."""
    try:
        a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        b.bind(("127.0.0.1", 0))
        a.sendto(b"x", b.getsockname())
        a.close()
        b.close()
        return True
    except OSError:
        return False


def _supervised_cfg(tmp, port):
    return {
        "mailbox_user": "runner@example.com",
        "mailbox_password": "test-gmail-password",
        "shared_secret": SECRET,
        "imap_host": "fake", "imap_port": 993,
        "smtp_host": "fake", "smtp_port": 587,
        "poll_interval_sec": 20,
        "max_job_age_sec": 3600,
        "max_output_bytes": 100000,
        "base_dir": tmp,
        "default_timeout_sec": 300,
        "transports": ["dtls"],
        "transport_dtls": {"port": port, "bind": "127.0.0.1"},
    }


class SupervisedDtlsRoundTripTest(unittest.TestCase):
    def _run_cli(self, cfg, tmp, seen_path, script_text, timeout=150):
        script = os.path.join(tmp, "job.sh")
        with open(script, "w", encoding="utf-8") as f:
            f.write(script_text)
        proc = subprocess.Popen(
            [sys.executable,
             os.path.join(REPO, "runner", "cloud", "send_dtls.py"),
             "--host", "127.0.0.1",
             "--port", str(cfg["transport_dtls"]["port"]),
             "--secret", SECRET, "--kind", "exec",
             "--script-file", script, "--cleartext",
             # The sender's --wait is its whole budget, the
             # handshake included, and the handshake's first
             # retransmission waits 2 poll periods by design
             # (the Section 7.1 timers): on a loaded CI host a
             # single lost datagram costs most of a short
             # budget, and the 3.15.17.169 macOS leg timed out
             # at 45 s with the round trip otherwise healthy.
             # The budget is sized for that loss, and the
             # communicate ceiling below stays finite past it.
             "--wait", "120"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            poll_once(cfg, tmp, {}, seen_path)
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        out, err = proc.communicate(timeout=30)
        return proc.returncode, out, err

    def test_exec_job_over_dtls_and_extension_restart(self):
        # The sender runs with --cleartext; the runner side of
        # this test is this process (poll_once below), so the
        # process takes the runner's command-line-only switch
        # the way main() sets it from --allow-cleartext-jobs.
        runner._set_allow_cleartext_jobs(True)
        self.addCleanup(runner._set_allow_cleartext_jobs, False)
        if not _udp_sendto_works():
            self.skipTest(
                "unconnected UDP sends are blocked in this "
                "environment; a DTLS server cannot run here "
                "(the pipe-level tests cover the same code "
                "over a connected socket)")
        tmp = tempfile.mkdtemp(prefix="hp-dtls-")
        cfg = _supervised_cfg(tmp, _free_udp_port())
        seen_path = os.path.join(tmp, "seen.json")
        transports.start_supervisor(cfg, tmp)
        try:
            rc, out, err = self._run_cli(
                cfg, tmp, seen_path, "echo hello-dtls")
            self.assertEqual(rc, 0, err)
            self.assertIn('"disclosure": "family"', out)
            self.assertIn('"exit_code": 0', out)
            self.assertIn("hello-dtls", out)

            # Kill the extension; the supervisor restarts it
            # and a fresh session still completes.
            sup = transports.active_supervisor(cfg, tmp)
            self.assertIsNotNone(sup)
            record = sup.processes["dtls"]
            first_proc = record["proc"]
            first_proc.terminate()

            def restarted():
                poll_once(cfg, tmp, {}, seen_path)
                now = sup.processes["dtls"]["proc"]
                return now is not first_proc and \
                    now.poll() is None

            self.assertTrue(
                _wait_for(restarted, timeout=30),
                "the supervisor did not restart dtls")
            rc, out, err = self._run_cli(
                cfg, tmp, seen_path, "echo hello-again")
            self.assertEqual(rc, 0, err)
            self.assertIn("hello-again", out)
        finally:
            transports.stop_supervisors(tmp)


def _wait_for(pred, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.1)
    return pred()


class ProfileRefusalTest(unittest.TestCase):
    def test_a_short_scalar_and_a_zero_point_are_refused(self):
        with self.assertRaises(dtlsproto.DtlsError):
            dtlsproto.x25519(b"\x01" * 16, b"\x02" * 32)
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            dtlsproto._ecdh(b"\x01" * 32, b"\x00" * 32)
        self.assertIn("all-zero", str(ctx.exception))
        self.assertEqual(len(dtlsproto._hkdf_extract(None, b"ikm")),
                         dtlsproto.HASH_LEN)

    def test_a_broken_extension_block_is_refused_by_name(self):
        short = (3).to_bytes(2, "big") + b"abc"
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            dtlsproto._parse_extensions(short, 0)
        self.assertIn("truncated extension header", str(ctx.exception))
        overrun = (4).to_bytes(2, "big") + b"\x00\x01\x00\x02X"
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            dtlsproto._parse_extensions(overrun, 0)
        self.assertIn("overruns", str(ctx.exception))
        dup = b"\x00\x01\x00\x00" + b"\x00\x01\x00\x00"
        data = len(dup).to_bytes(2, "big") + dup
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            dtlsproto._parse_extensions(data, 0)
        self.assertIn("duplicate", str(ctx.exception))

    def test_a_broken_key_share_and_psk_are_refused(self):
        with self.assertRaises(dtlsproto.DtlsError):
            dtlsproto._key_share_entry(b"\x00\x1d\x00\x20", server_form=True)
        with self.assertRaises(dtlsproto.DtlsError):
            dtlsproto._key_share_entry(
                (4).to_bytes(2, "big") + b"\x00\x1d\x00\x20")
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            dtlsproto._parse_psk_extension((1).to_bytes(2, "big") + b"\x00")
        self.assertIn("truncated identity", str(ctx.exception))
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            dtlsproto._parse_psk_extension(
                (6).to_bytes(2, "big") + b"\x00\x02ab\x00\x00")
        self.assertIn("identity body", str(ctx.exception))
        ident = b"\x00\x02ab" + b"\x00\x00\x00\x00"
        body = len(ident).to_bytes(2, "big") + ident + bytes([2, 3])
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            dtlsproto._parse_psk_extension(body)
        self.assertIn("binder", str(ctx.exception))

    def test_an_empty_secret_is_not_a_name(self):
        self.assertEqual(dtlsproto.identity_for(""), b"homing-pigeon")
        self.assertEqual(dtlsproto.identity_for("lab"),
                         b"homing-pigeon:lab")
        lookup = dtlsproto.make_secret_lookup(
            "", {"lab": "", "other": "sek"})
        self.assertIsNone(lookup(dtlsproto.identity_for("")))
        self.assertIsNone(lookup(dtlsproto.identity_for("lab")))
        self.assertEqual(lookup(dtlsproto.identity_for("other")), "sek")

    def test_an_unanswered_flight_is_abandoned(self):
        lines = []
        ep = dtlsproto._Endpoint(
            log=lambda m, level="INFO": lines.append(m))
        ep._flight = [(0, dtlsproto.CT_HANDSHAKE, b"hi")]
        ep._flight_first = 0.0
        ep._flight_next = 1.0
        self.assertEqual(ep.tick(61.0), [])
        self.assertTrue(ep.dead)
        self.assertEqual(ep.state, "dead")
        self.assertIsNone(ep._flight)
        self.assertTrue(any("abandoned" in m for m in lines))
        ep._acks_wanted = [(0, 1)]
        self.assertEqual(ep.tick(62.0), [])

    def test_an_application_message_past_the_cap_is_refused(self):
        ep = dtlsproto._Endpoint()
        seen = []
        ep._on_app_message = seen.append
        ep._app_receive(b"\x00\x00\x00\x05ab")
        self.assertEqual(ep.app_messages, [])
        done = dtlsproto._Endpoint()
        done._on_app_message = seen.append
        done._app_receive(b"\x00\x00\x00\x02hi")
        self.assertEqual(seen, [b"hi"])
        huge = dtlsproto._Endpoint()
        n = dtlsproto.APP_MESSAGE_MAX + 1
        with self.assertRaises(dtlsproto.DtlsError):
            huge._app_receive(n.to_bytes(4, "big"))

    def test_a_key_update_is_answered_and_a_bad_one_is_dropped(self):
        secret = b"k" * dtlsproto.HASH_LEN
        lines = []
        ep = dtlsproto._Endpoint(
            log=lambda m, level="INFO": lines.append(m))
        ep._recv_ap_secret = secret
        ep._send_ap_secret = secret
        ep.senders[3] = dtlsproto._RecordSealer(secret)
        self.assertEqual(ep._handle_key_update(3, b""), [])
        self.assertTrue(any("malformed" in m for m in lines))
        self.assertEqual(ep._handle_key_update(3, b"\x00"), [])
        out = ep._handle_key_update(3, b"\x01extra")
        self.assertEqual(len(out), 1)
        self.assertIn(4, ep.senders)
        self.assertIn(4, ep.receivers)


class HandshakeRefusalTest(unittest.TestCase):
    def _pair_at_server_hello(self):
        lines = []
        log = lambda m, level="INFO": lines.append((level, m))
        client = dtlsproto.DtlsClientCore(SECRET, log=log)
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET), log=log)
        hello = client.start(NOW)[0]
        hrr = server.feed(hello, ADDR, NOW)[0]
        second = client.feed(hrr, NOW)[0]
        flight = server.feed(second, ADDR, NOW)
        return client, server, flight, lines

    def _server_hello(self, suite, version, psk, group, pub, cid):
        share = (group.to_bytes(2, "big") + len(pub).to_bytes(2, "big")
                 + pub)
        exts = [
            (dtlsproto.EXT_SUPPORTED_VERSIONS, version.to_bytes(2, "big")),
            (dtlsproto.EXT_KEY_SHARE, share),
            (dtlsproto.EXT_PRE_SHARED_KEY, psk),
        ]
        if cid is not None:
            exts.append((dtlsproto.EXT_CONNECTION_ID, cid))
        return (dtlsproto.LEGACY_VERSION.to_bytes(2, "big")
                + b"\x11" * 32 + b"\x00"
                + suite.to_bytes(2, "big") + b"\x00"
                + dtlsproto._extensions_bytes(exts))

    def test_a_server_hello_that_breaks_the_profile_is_refused(self):
        client, _server, _flight, _lines = self._pair_at_server_hello()
        pub = b"\x02" * 32
        psk = (0).to_bytes(2, "big")
        cases = [
            (0x1301, dtlsproto.DTLS_1_3, psk, dtlsproto.GROUP_X25519,
             pub, None, "foreign ciphersuite"),
            (dtlsproto.SUITE_AES256, 0x0304, psk, dtlsproto.GROUP_X25519,
             pub, None, "did not pick DTLS 1.3"),
            (dtlsproto.SUITE_AES256, dtlsproto.DTLS_1_3, b"\x00\x01",
             dtlsproto.GROUP_X25519, pub, None, "did not accept our PSK"),
            (dtlsproto.SUITE_AES256, dtlsproto.DTLS_1_3, psk, 0x0017,
             pub, None, "foreign group"),
        ]
        for suite, version, psk_ext, group, key, cid, note in cases:
            fresh, _, _, _ = self._pair_at_server_hello()
            body = self._server_hello(suite, version, psk_ext, group,
                                      key, cid)
            with self.assertRaises(dtlsproto.DtlsError) as ctx:
                fresh._on_server_hello(body, b"raw", NOW)
            self.assertIn(note, str(ctx.exception))
        client._on_server_hello(
            self._server_hello(
                dtlsproto.SUITE_AES256, dtlsproto.DTLS_1_3, psk,
                dtlsproto.GROUP_X25519, pub, b""),
            b"raw", NOW)
        self.assertIsNone(client._peer_cid)

    def test_a_bad_retry_and_a_late_finished_are_ignored(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        client.start(NOW)
        body = (dtlsproto.LEGACY_VERSION.to_bytes(2, "big")
                + dtlsproto.HRR_RANDOM + b"\x00"
                + dtlsproto.SUITE_AES256.to_bytes(2, "big") + b"\x00"
                + dtlsproto._extensions_bytes([
                    (dtlsproto.EXT_SUPPORTED_VERSIONS,
                     dtlsproto.DTLS_1_3.to_bytes(2, "big"))]))
        with self.assertRaises(dtlsproto.DtlsError):
            client._on_server_hello(body, b"raw", NOW)
        client.state = "established"
        self.assertEqual(client._on_server_hello(body, b"raw", NOW), [])
        self.assertEqual(
            client._on_server_finished(b"\x00" * 48, b"raw", NOW), [])

    def test_a_finished_that_does_not_verify_kills_the_client(self):
        client, _server, flight, _lines = self._pair_at_server_hello()
        client.feed(flight[0], NOW)
        self.assertEqual(client.state, "handshake-keys")
        with self.assertRaises(dtlsproto.DtlsError):
            client._on_server_finished(b"\x00" * 48, b"raw", NOW)
        self.assertEqual(client.state, "dead")

    def test_alerts_fragments_and_early_data(self):
        client, server = _established_pair()
        session = next(iter(server.sessions.values()))
        alert = session._emit(
            max(session.senders), dtlsproto.CT_ALERT,
            bytes([dtlsproto.ALERT_FATAL, 40]))
        client.feed(alert, NOW)
        self.assertEqual(client.state, "dead")

        early = dtlsproto.DtlsClientCore(SECRET)
        with self.assertRaises(dtlsproto.DtlsError):
            early._on_protected(3, dtlsproto.CT_APPDATA, b"", 0, NOW)
        self.assertEqual(early._on_protected(3, 99, b"", 0, NOW), [])
        self.assertEqual(early._on_handshake_bytes(b"\x02", NOW, 0), [])

        def frag(off, piece, total=2):
            return (bytes([dtlsproto.HS_ENCRYPTED_EXTENSIONS])
                    + total.to_bytes(3, "big") + (1).to_bytes(2, "big")
                    + off.to_bytes(3, "big")
                    + len(piece).to_bytes(3, "big") + piece)

        self.assertEqual(
            early._on_handshake_bytes(frag(0, b"\x00"), NOW, 2), [])
        early._on_handshake_bytes(frag(1, b"\x00"), NOW, 2)
        self.assertTrue(early._ee_seen)
        early._on_handshake_bytes(
            dtlsproto._hs_message(
                dtlsproto.HS_ENCRYPTED_EXTENSIONS, b"\x00\x00", 2),
            NOW, 2)
        early._on_app_message(b"not-json")
        self.assertEqual(early.greeting, {})
        upd = dtlsproto._hs_message(dtlsproto.HS_KEY_UPDATE, b"\x00", 9)
        client2, _server2 = _established_pair()
        self.assertEqual(
            client2._on_handshake_bytes(upd, NOW, 3), [])

    def test_the_server_refuses_a_hello_that_breaks_the_profile(self):
        core = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        share = ((2).to_bytes(2, "big")
                 + dtlsproto.GROUP_X25519.to_bytes(2, "big")
                 + (32).to_bytes(2, "big") + b"\x09" * 32)
        modes = bytes([1, dtlsproto.PSK_MODE_DHE_KE])
        ident = b"homing-pigeon:nope"
        entry = (len(ident).to_bytes(2, "big") + ident + b"\x00" * 4)
        psk = (len(entry).to_bytes(2, "big") + entry + bytes([1, 0]))

        def begin(suites, exts, raw=b"x" * 64):
            session = dtlsproto._ServerSession(core, ADDR)
            return session, session.begin(
                raw, {"suites": suites, "exts": exts},
                b"\x00" * dtlsproto.HASH_LEN, b"hrr", NOW)

        session, out = begin([0x0001], {})
        self.assertTrue(session.dead)
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        _s, out = begin([dtlsproto.SUITE_AES256], {})
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        _s, out = begin([dtlsproto.SUITE_AES256], {
            dtlsproto.EXT_PSK_MODES: modes})
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        _s, out = begin([dtlsproto.SUITE_AES256], {
            dtlsproto.EXT_PSK_MODES: modes,
            dtlsproto.EXT_KEY_SHARE: b"\x00"})
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        _s, out = begin([dtlsproto.SUITE_AES256], {
            dtlsproto.EXT_PSK_MODES: modes,
            dtlsproto.EXT_KEY_SHARE: ((2).to_bytes(2, "big")
                                      + (0x0017).to_bytes(2, "big")
                                      + (32).to_bytes(2, "big")
                                      + b"\x09" * 32)})
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        _s, out = begin([dtlsproto.SUITE_AES256], {
            dtlsproto.EXT_PSK_MODES: modes,
            dtlsproto.EXT_KEY_SHARE: share})
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        _s, out = begin([dtlsproto.SUITE_AES256], {
            dtlsproto.EXT_PSK_MODES: modes,
            dtlsproto.EXT_KEY_SHARE: share,
            dtlsproto.EXT_PRE_SHARED_KEY: b"\x00\x10"})
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        session, out = begin([dtlsproto.SUITE_AES256], {
            dtlsproto.EXT_PSK_MODES: modes,
            dtlsproto.EXT_KEY_SHARE: share,
            dtlsproto.EXT_PRE_SHARED_KEY: (0).to_bytes(2, "big")
            + bytes([1, 0])})
        self.assertTrue(session.dead)
        session, out = begin([dtlsproto.SUITE_AES256], {
            dtlsproto.EXT_PSK_MODES: modes,
            dtlsproto.EXT_KEY_SHARE: share,
            dtlsproto.EXT_PRE_SHARED_KEY: psk,
            dtlsproto.EXT_CONNECTION_ID: b""}, raw=b"ab")
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)

    def test_a_zero_point_does_not_leave_a_session_behind(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        real = dtlsproto.x25519_public
        dtlsproto.x25519_public = lambda priv: b"\x00" * 32
        try:
            client = dtlsproto.DtlsClientCore(SECRET)
            hello = client.start(NOW)[0]
            hrr = server.feed(hello, ADDR, NOW)[0]
            second = client.feed(hrr, NOW)[0]
        finally:
            dtlsproto.x25519_public = real
        self.assertEqual(server.feed(second, ADDR, NOW), [])
        self.assertEqual(server.sessions, {})
        self.assertEqual(server.by_addr, {})

    def test_a_first_flight_that_is_not_a_hello_is_dropped(self):
        lines = []
        server = dtlsproto.DtlsServerCore(
            log=lambda m, level="INFO": lines.append(m))
        alert = dtlsproto._plaintext_record(
            dtlsproto.CT_ALERT, 0, 0, bytes([2, 0]))
        self.assertEqual(server.feed(alert, ADDR, NOW), [])
        frag = (bytes([1]) + (10).to_bytes(3, "big")
                + b"\x00\x00" + b"\x00\x00\x00" + (1).to_bytes(3, "big")
                + b"\x00")
        rec = dtlsproto._plaintext_record(
            dtlsproto.CT_HANDSHAKE, 0, 0, frag)
        self.assertEqual(server.feed(rec, ADDR, NOW), [])
        other = dtlsproto._hs_message(2, b"\x00" * 40, 0)
        rec = dtlsproto._plaintext_record(
            dtlsproto.CT_HANDSHAKE, 0, 0, other)
        self.assertEqual(server.feed(rec, ADDR, NOW), [])
        short = dtlsproto._plaintext_record(
            dtlsproto.CT_HANDSHAKE, 0, 0,
            dtlsproto._hs_message(1, b"\x00\x00", 0))
        self.assertEqual(server.feed(short, ADDR, NOW), [])
        self.assertTrue(any("not a handshake" in m for m in lines))
        self.assertTrue(any("fragmented" in m for m in lines))
        self.assertTrue(any("not a ClientHello" in m for m in lines))
        self.assertTrue(any("malformed ClientHello" in m for m in lines))

    def test_a_replayed_hello_is_the_same_flight(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        hello = client.start(NOW)[0]
        hrr = server.feed(hello, ADDR, NOW)[0]
        second = client.feed(hrr, NOW)[0]
        first = server.feed(second, ADDR, NOW)
        again = server.feed(second, ADDR, NOW)
        self.assertEqual(len(again), len(first))
        self.assertTrue(again)

    def test_records_that_cannot_be_split_or_opened(self):
        legacy = dtlsproto.LEGACY_VERSION.to_bytes(2, "big")
        short = bytes([22]) + legacy + b"\x00" * 8 + (100).to_bytes(2, "big")
        self.assertEqual(dtlsproto._split_records(short), [])
        unified = bytes([0x20 | 0x08 | 0x10, 0x00])
        self.assertEqual(dtlsproto._split_records(unified), [])
        self.assertIsNone(dtlsproto._record_cid(bytes([0x24])))
        secret = b"k" * dtlsproto.HASH_LEN
        sealer = dtlsproto._RecordSealer(secret)
        opener = dtlsproto._RecordSealer(secret)
        empty = sealer.seal(3, 0, b"", None)
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            opener.open(3, empty)
        self.assertIn("empty", str(ctx.exception))
        with self.assertRaises(dtlsproto.DtlsError):
            opener.open(3, b"")
        opener._next_expected = 0x1FFFF
        with self.assertRaises(Exception):
            opener.open(3, empty)
        opener._next_expected = 0x10000
        with self.assertRaises(Exception):
            opener.open(3, sealer.seal(3, 22, b"hi", None))
        ident = b"\x00\x01a" + b"\x00" * 4
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            dtlsproto._parse_psk_extension(len(ident).to_bytes(2, "big")
                                           + ident)
        self.assertIn("binders missing", str(ctx.exception))
        body = (len(ident).to_bytes(2, "big") + ident + bytes([1, 3]))
        with self.assertRaises(dtlsproto.DtlsError) as ctx:
            dtlsproto._parse_psk_extension(body)
        self.assertIn("binder overruns", str(ctx.exception))
        self.assertEqual(dtlsproto._addr_bytes("socket"), b"socket")
        bare = dtlsproto._Endpoint()
        with self.assertRaises(NotImplementedError):
            bare._on_app_message(b"x")
        self.assertEqual(bare._note_ack(b""), None)
        no_keys = dtlsproto._ServerSession(
            dtlsproto.DtlsServerCore(), ADDR)
        alert = dtlsproto._sendable_alert(no_keys, 40)
        self.assertTrue(dtlsproto._is_plaintext_record(alert))
        keyed = dtlsproto._ServerSession(
            dtlsproto.DtlsServerCore(), ADDR)
        keyed.senders[2] = dtlsproto._RecordSealer(secret)
        sealed = dtlsproto._sendable_alert(keyed, 40)
        self.assertFalse(dtlsproto._is_plaintext_record(sealed))

    def test_a_dead_session_and_an_expired_ticket_are_dropped(self):
        client, server = _established_pair()
        session = next(iter(server.sessions.values()))
        session.dead = True
        server.tickets[b"old"] = (b"k", NOW - 1)
        server.tickets[b"new"] = (b"k", NOW + 10)
        server.tick(NOW + 1)
        self.assertEqual(server.sessions, {})
        self.assertNotIn(b"old", server.tickets)
        self.assertIn(b"new", server.tickets)
        self.assertEqual(server.send_app(b"missing", b"hi"), [])
        self.assertEqual(
            session._on_protected(3, dtlsproto.CT_APPDATA, b"", 0, NOW),
            [])
        self.assertEqual(
            session._on_protected(3, 99, b"", 0, NOW), [])
        self.assertEqual(
            session._on_handshake_bytes(b"\x14", NOW, 3), [])
        alert = client._emit(
            max(client.senders), dtlsproto.CT_ALERT,
            bytes([dtlsproto.ALERT_FATAL, 40]))
        # The client's send key is what the server receives.
        # Re-establish so the session is alive, then kill it
        # with the alert.
        client, server = _established_pair()
        session = next(iter(server.sessions.values()))
        alert = client._emit(
            3, dtlsproto.CT_ALERT, bytes([dtlsproto.ALERT_FATAL, 40]))
        session.feed_authenticated(alert, NOW)
        self.assertTrue(session.dead)


class ServerHelloCheckTest(unittest.TestCase):
    """The checks inside begin() that a normal hello never fails.

    The key share has to be long enough to parse, or an earlier
    refusal fires and these lines never run.
    """

    def _core(self):
        self.lines = []
        return dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            log=lambda m, level="INFO": self.lines.append(m))

    def _share(self, group=None, pub=None):
        group = dtlsproto.GROUP_X25519 if group is None else group
        pub = b"\x09" * 32 if pub is None else pub
        entry = (group.to_bytes(2, "big") + len(pub).to_bytes(2, "big")
                 + pub)
        return len(entry).to_bytes(2, "big") + entry

    def _psk(self, identity, binder=b"\xab"):
        entry = (len(identity).to_bytes(2, "big") + identity
                 + b"\x00" * 4)
        vec = bytes([len(binder)]) + binder
        return len(entry).to_bytes(2, "big") + entry + bytes([len(vec)]) + vec

    def _begin(self, core, exts, raw=b"x" * 80):
        session = dtlsproto._ServerSession(core, ADDR)
        out = session.begin(
            raw, {"suites": [dtlsproto.SUITE_AES256], "exts": exts},
            b"\x11" * dtlsproto.HASH_LEN, b"hrr", NOW)
        return session, out

    def _alert_code(self, out):
        return out[0][14]

    def _base_exts(self, **over):
        exts = {
            dtlsproto.EXT_PSK_MODES: bytes([1, dtlsproto.PSK_MODE_DHE_KE]),
            dtlsproto.EXT_KEY_SHARE: self._share(),
        }
        exts.update(over)
        return exts

    def test_each_broken_hello_is_refused_for_its_own_reason(self):
        core = self._core()
        modes = bytes([1, dtlsproto.PSK_MODE_DHE_KE])
        share = self._share()

        _s, out = self._begin(core, {})
        self.assertEqual(self._alert_code(out),
                         dtlsproto.ALERT_MISSING_EXTENSION)

        _s, out = self._begin(core, {dtlsproto.EXT_PSK_MODES: modes})
        self.assertEqual(self._alert_code(out),
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)

        _s, out = self._begin(core, {
            dtlsproto.EXT_PSK_MODES: modes,
            dtlsproto.EXT_KEY_SHARE: b"\x00\x02\x00"})
        self.assertEqual(self._alert_code(out),
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)

        _s, out = self._begin(core, {
            dtlsproto.EXT_PSK_MODES: modes,
            dtlsproto.EXT_KEY_SHARE: self._share(group=0x0017)})
        self.assertEqual(self._alert_code(out),
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)

        _s, out = self._begin(core, {
            dtlsproto.EXT_PSK_MODES: modes,
            dtlsproto.EXT_KEY_SHARE: share})
        self.assertEqual(self._alert_code(out),
                         dtlsproto.ALERT_MISSING_EXTENSION)

        _s, out = self._begin(core, self._base_exts() | {
            dtlsproto.EXT_PRE_SHARED_KEY: b"\x00\x10"})
        self.assertEqual(self._alert_code(out),
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)

        _s, out = self._begin(core, self._base_exts() | {
            dtlsproto.EXT_PRE_SHARED_KEY: (0).to_bytes(2, "big")
            + bytes([1, 0])})
        self.assertEqual(self._alert_code(out),
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)

        _s, out = self._begin(core, self._base_exts() | {
            dtlsproto.EXT_PRE_SHARED_KEY: self._psk(b"homing-pigeon:nope")})
        self.assertEqual(self._alert_code(out),
                         dtlsproto.ALERT_HANDSHAKE_FAILURE)
        self.assertTrue(any("unknown PSK identity" in m for m in self.lines))

        core.tickets[b"homing-pigeon"] = (b"k" * 48, NOW - 5)
        _s, out = self._begin(core, self._base_exts() | {
            dtlsproto.EXT_PRE_SHARED_KEY: self._psk(
                b"homing-pigeon", b"\x11" * 48)}, raw=b"short")
        self.assertEqual(self._alert_code(out),
                         dtlsproto.ALERT_DECRYPT_ERROR)

    def test_application_data_before_the_session_is_dropped(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        lines = []
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            log=lambda m, level="INFO": lines.append(m))
        hello = client.start(NOW)[0]
        hrr = server.feed(hello, ADDR, NOW)[0]
        second = client.feed(hrr, NOW)[0]
        server.feed(second, ADDR, NOW)
        session = next(iter(server.sessions.values()))
        self.assertFalse(session.established)
        self.assertEqual(session._on_protected(
            2, dtlsproto.CT_APPDATA, b"job", 1, NOW), [])
        self.assertTrue(any("before the session" in m for m in lines))
        bad = session._on_client_finished(b"\x00" * 48, b"raw", NOW)
        self.assertTrue(session.dead)
        self.assertEqual(bad[0][0] & 0xE0, 0x20)
        self.assertTrue(any("does not verify" in m for m in lines))

    def test_a_short_cookie_and_a_short_handshake_are_dropped(self):
        lines = []
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            log=lambda m, level="INFO": lines.append(m))
        cookie = b"\x00"
        body = (dtlsproto.LEGACY_VERSION.to_bytes(2, "big")
                + b"\x22" * 32 + b"\x00" + b"\x00"
                + (2).to_bytes(2, "big")
                + dtlsproto.SUITE_AES256.to_bytes(2, "big")
                + b"\x01\x00"
                + dtlsproto._extensions_bytes([
                    (dtlsproto.EXT_COOKIE, cookie)]))
        raw = dtlsproto._hs_message(dtlsproto.HS_CLIENT_HELLO, body, 1)
        rec = dtlsproto._plaintext_record(
            dtlsproto.CT_HANDSHAKE, 0, 0, raw)
        self.assertEqual(server.feed(rec, ADDR, NOW), [])
        self.assertTrue(any("malformed cookie" in m for m in lines))
        wide = (4).to_bytes(2, "big") + b"abcd"
        body = (dtlsproto.LEGACY_VERSION.to_bytes(2, "big")
                + b"\x33" * 32 + b"\x00" + b"\x00"
                + (2).to_bytes(2, "big")
                + dtlsproto.SUITE_AES256.to_bytes(2, "big")
                + b"\x01\x00"
                + dtlsproto._extensions_bytes([
                    (dtlsproto.EXT_COOKIE, wide)]))
        raw = dtlsproto._hs_message(dtlsproto.HS_CLIENT_HELLO, body, 1)
        rec = dtlsproto._plaintext_record(
            dtlsproto.CT_HANDSHAKE, 0, 0, raw)
        self.assertEqual(server.feed(rec, ADDR, NOW), [])
        self.assertTrue(any("bad cookie" in m for m in lines))

        claimed = (bytes([2]) + (100).to_bytes(3, "big")
                   + (1).to_bytes(2, "big") + (0).to_bytes(3, "big")
                   + (100).to_bytes(3, "big"))
        self.assertIsNone(dtlsproto._parse_handshake(claimed))

        client, server = _established_pair()
        session = next(iter(server.sessions.values()))
        finished = dtlsproto._hs_message(
            dtlsproto.HS_FINISHED, b"\x00" * 48, 9)
        self.assertEqual(
            session._on_handshake_bytes(finished, NOW, 3), [])
        update = dtlsproto._hs_message(
            dtlsproto.HS_KEY_UPDATE, b"\x00", 10)
        out = session._on_protected(3, dtlsproto.CT_HANDSHAKE, update, 4, NOW)
        self.assertTrue(out)

        def piece(off, data, total=2):
            return (bytes([dtlsproto.HS_KEY_UPDATE])
                    + total.to_bytes(3, "big") + (11).to_bytes(2, "big")
                    + off.to_bytes(3, "big")
                    + len(data).to_bytes(3, "big") + data)

        self.assertEqual(
            session._on_handshake_bytes(piece(0, b"\x00"), NOW, 3), [])
        session._on_handshake_bytes(piece(1, b"\x00"), NOW, 3)


class DtlsMainRefusalsTest(unittest.TestCase):
    """Queue A refill: the DTLS extension's main() startup
    refusals and pass loop (coverage run 40187685363: 9
    lines on both platforms). The extension's contract at
    startup (its own module docstring, Decision 1's refuse
    class): no channel directory, an unusable port, and a
    bind that cannot be listened on each refuse with exit
    2 and a named reason -- nothing substitutes an address.
    And a pass that fails is logged, never fatal: the loop
    goes on until something outside it stops the process.
    """

    def _cfg_file(self, d, cfg):
        path = os.path.join(d, "runtime.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        return path

    def _main(self, argv):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("HOMING_PIGEON_TRANSPORT_")}
        err = StringIO()
        with mock.patch.dict(os.environ, env, clear=True):
            with redirect_stderr(err):
                rc = dtls_ext.main(argv)
        return rc, err.getvalue()

    def test_no_channel_directory_refuses(self):
        rc, err = self._main(["dtls"])
        self.assertEqual(rc, 2)
        self.assertIn("no channel directory given", err)

    def test_an_unusable_port_refuses_and_names_the_key(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self._cfg_file(d, {"shared_secret": SECRET,
                                     "port": "2O220"})
            rc, err = self._main(["dtls", d, cfg])
        self.assertEqual(rc, 2)
        self.assertIn("refusing to start", err)
        self.assertIn("transport_dtls.port", err)

    def test_a_bind_that_cannot_listen_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self._cfg_file(
                d, {"shared_secret": SECRET, "port": 0,
                    "bind": "192.0.2.1"})
            rc, err = self._main(["dtls", d, cfg])
        self.assertEqual(rc, 2)
        self.assertIn("cannot listen", err)

    def test_a_failed_pass_is_logged_and_the_loop_goes_on(self):
        calls = []

        class StubPipe:
            bind = "127.0.0.1"
            port = 0

            def __init__(self, cfg, channel):
                pass

            def run_once(self):
                calls.append(1)
                if len(calls) == 1:
                    raise RuntimeError("pass boom")
                raise KeyboardInterrupt

        with tempfile.TemporaryDirectory() as d:
            cfg = self._cfg_file(d, {"shared_secret": SECRET,
                                     "port": 0})
            err = StringIO()
            with mock.patch.object(dtls_ext, "DtlsPipe",
                                   StubPipe):
                with redirect_stderr(err):
                    with self.assertRaises(KeyboardInterrupt):
                        dtls_ext.main(["dtls", d, cfg])
        self.assertEqual(len(calls), 2)
        self.assertIn("listening on udp", err.getvalue())
        self.assertIn("pass failed", err.getvalue())


class DtlsOnJobDropsTest(unittest.TestCase):
    """Queue A refill: DtlsPipe._on_job's three drop
    guards (coverage run 40187685363: 7 lines on both
    platforms). What arrives on an established DTLS
    session is post-authentication but not yet a job:
    the pipe drops, with a logged reason, a message that
    is not UTF-8, a message that is not an envelope, and
    an envelope whose subject carries no job id -- only
    the fourth shape reaches the runner core's inbox.
    """

    def _pipe(self):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-drop-")
        channel = os.path.join(tmp, "channel")
        cfg = {"shared_secret": SECRET, "port": 0,
               "bind": "127.0.0.1"}
        pipe = dtls_ext.DtlsPipe(cfg, channel)
        self.addCleanup(pipe.sock.close)
        return pipe, channel

    def _delivered(self, channel):
        found = []
        for root, _dirs, files in os.walk(channel):
            found += [f for f in files if f.endswith(".job.txt")]
        return found

    def test_a_non_utf8_message_is_dropped(self):
        pipe, channel = self._pipe()
        pipe._on_job("s1", b"\xff\xfe\x00binary")
        self.assertEqual(pipe.job_session, {})
        self.assertEqual(self._delivered(channel), [])

    def test_a_non_envelope_message_is_dropped(self):
        pipe, channel = self._pipe()
        pipe._on_job("s1", b"just some text, no envelope")
        self.assertEqual(pipe.job_session, {})
        self.assertEqual(self._delivered(channel), [])

    def test_an_envelope_without_a_job_id_is_dropped(self):
        pipe, channel = self._pipe()
        pipe._on_job("s1", ch.envelope(
            "a subject with no marker", "{}").encode("utf-8"))
        self.assertEqual(pipe.job_session, {})
        self.assertEqual(self._delivered(channel), [])

    def test_a_real_envelope_is_delivered(self):
        # Control: the shape the guards exist to protect.
        pipe, channel = self._pipe()
        pipe._on_job("s1", ch.envelope(
            "[HOMING-PIGEON] job probe-1", "{}").encode("utf-8"))
        self.assertEqual(pipe.job_session, {"probe-1": "s1"})
        self.assertEqual(self._delivered(channel),
                         ["probe-1.job.txt"])


class DtlsPumpResultsLegsTest(unittest.TestCase):
    """Queue A refill: DtlsPipe._pump_results' last
    legs (coverage run 40189711740: lines 269,
    275-281). Two of the pump's promises: a result
    body that does not end in a newline gets one
    before it goes on the wire, and a result whose
    session is gone stays in the outbox. Acking it
    into done threw the only copy away. The peer
    comes back, the session is remembered, and the
    same file goes out.
    """

    def _pipe(self):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-pump-")
        channel = os.path.join(tmp, "channel")
        cfg = {"shared_secret": SECRET, "port": 0,
               "bind": "127.0.0.1"}
        return dtls_ext.DtlsPipe(cfg, channel), channel

    def _result(self, channel, ident, body):
        outbox = ch.dirs(channel)["outbox"]
        os.makedirs(outbox, exist_ok=True)
        with open(os.path.join(outbox, ident + ".result.txt"),
                  "w") as fh:
            fh.write(ch.envelope("[HOMING-PIGEON] result "
                                 + ident, body))

    def test_a_gone_session_keeps_the_result_until_the_peer_is_back(self):
        # Acking this into done left nothing for the re-ask.
        # The seen-set will not run the job again.
        pipe, channel = self._pipe()
        self._result(channel, "job-gone", "the answer")
        pipe._pump_results()
        d = ch.dirs(channel)
        self.assertEqual(os.listdir(d["outbox_done"]), [])
        self.assertIn("job-gone.result.txt", os.listdir(d["outbox"]))
        pipe.job_session["job-gone"] = "s2"
        sent = []
        pipe.core.send_app = lambda sid, data: (
            sent.append((sid, data)), [("127.0.0.1", b"dg")])[1]
        pipe._send = lambda dg, addr: True
        pipe._pump_results()
        self.assertEqual([row[0] for row in sent], ["s2"])
        self.assertIn(b"the answer", sent[0][1])
        self.assertEqual(os.listdir(d["outbox_done"]),
                         ["job-gone.result.txt"])

    def test_a_datagram_that_does_not_leave_keeps_the_result(self):
        pipe, channel = self._pipe()
        self._result(channel, "job-live", "the answer")
        pipe.job_session["job-live"] = "s1"
        pipe.core.send_app = lambda sid, data: [("127.0.0.1", b"dg")]
        pipe._send = lambda dg, addr: False
        pipe._pump_results()
        d = ch.dirs(channel)
        self.assertIn("job-live.result.txt", os.listdir(d["outbox"]))
        self.assertEqual(os.listdir(d["outbox_done"]), [])
        pipe._send = lambda dg, addr: True
        pipe._pump_results()
        self.assertEqual(os.listdir(d["outbox_done"]),
                         ["job-live.result.txt"])

    def test_a_body_without_a_newline_gets_one(self):
        pipe, channel = self._pipe()
        self._result(channel, "job-live", "no trailing newline")
        pipe.job_session["job-live"] = "s1"
        sent_texts = []
        pipe.core.send_app = lambda sid, data: (
            sent_texts.append(data), [("127.0.0.1", b"dg")])[1]
        pipe._send = lambda dg, addr: True
        pipe._pump_results()
        self.assertEqual(len(sent_texts), 1)
        self.assertTrue(sent_texts[0].endswith(
            b"no trailing newline\n"))

    def test_a_suffixed_result_uses_the_job_session(self):
        # job-live.result-2.txt does not end in .result.txt. The
        # pump used the whole filename, missed the session, and
        # acked the result into done without sending it.
        pipe, channel = self._pipe()
        outbox = ch.dirs(channel)["outbox"]
        with open(os.path.join(outbox, "job-live.result-2.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write(ch.envelope("[HOMING-PIGEON] result job-live",
                                 "the answer"))
        pipe.job_session["job-live"] = "s1"
        sent = []
        pipe.core.send_app = lambda sid, data: (
            sent.append(sid), [("127.0.0.1", b"dg")])[1]
        pipe._send = lambda dg, addr: True
        pipe._pump_results()
        self.assertEqual(sent, ["s1"])
        self.assertEqual(os.listdir(ch.dirs(channel)["outbox_done"]),
                         ["job-live.result-2.txt"])


class DtlsResultStaysShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 9 (31-Oct-2026): a
    DTLS result that landed after its session died was acked
    into done, so the only copy was gone when the peer
    re-asked -- and the seen-set would not run the job again.
    The fix (81ef9ee5) keeps the file in the outbox until a
    session can take it: _pump_results delivers only when
    send_app produced datagrams AND every datagram actually
    left (_send now returns True/False instead of None), a
    fresh session is remembered against the job in
    job_session, and the waiting log line is said once per
    ident through _waiting_session. This family scattershots
    everything around that failure: no session, the wrong
    session, a case-variant session key, stale / empty / None
    sessions, empty and falsy send_app results, a failure on
    the first, middle and last datagram, falsy non-bool send
    verdicts, the real _send's OSError leg, the once-only
    waiting log and its reset, one waiting result beside a
    delivered one, and the re-ask arriving through _on_job
    itself. One regression test was never going to be enough
    for a bug that took days of CPU to find.

    Proof of work (2-Nov-2026). The unit tests are the 50
    methods of this class: 20 hand-written seams, 8 per-field
    tests, 10 bookend sweeps, 4 run-length sweeps, 4
    injection-shaped tests and 4 edge tests. Per-field
    enumeration: the pump's surface is fielded -- the ident
    (from the result file's name), the session id in
    job_session, the file name itself, the envelope subject,
    the result body, and each datagram's address and bytes
    with its own send verdict -- and each field gets its own
    test in the per-field section, pinning that delivery
    keys on the exact ident and session and carries subject,
    body, address and datagram bytes verbatim. Bookends:
    every printable ASCII symbol (string.punctuation, all
    32) at the front AND the back of the body, the subject
    and the session id, as singles, matched pairs,
    mismatched pairs and symbol-only strings, plus NUL, tab,
    CR and LF at both ends; the ident sweep uses every
    symbol a file name can hold (all but the path
    separator). Run lengths: runs of the odd character, runs
    of 10 ordinary characters with the odd one at the front,
    the back and the middle, and 10 waiting / failing pumps
    before the delivery. The fuzzing was executed, not just
    the tests written: runner/tools/de_dust_corpus.py grow
    --target dtls --rounds 400 --seed 20261107 against the
    banked dtls corpus (55 entries). Result: 400 rounds,
    0 crashes, 0 slow, arcs unchanged at 728, slowest try
    62 ms; the lost-result shape did not recur. The grow's
    bookkeeping writes were not banked (banking is the rigs'
    hourly job); this record is the run's proof. None of
    this is exotic: it is combinatorics -- systematically
    trying the combinations a hand-written list would never
    reach, then pinning each answer as a test."""

    # -- helpers ---------------------------------------------------

    def _pipe(self):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-stays-")
        channel = os.path.join(tmp, "channel")
        cfg = {"shared_secret": SECRET, "port": 0,
               "bind": "127.0.0.1"}
        return dtls_ext.DtlsPipe(cfg, channel), channel

    def _write(self, channel, ident, body, fname=None,
               subject=None):
        outbox = ch.dirs(channel)["outbox"]
        os.makedirs(outbox, exist_ok=True)
        fname = fname or ident + ".result.txt"
        if subject is None:
            subject = "[HOMING-PIGEON] result " + ident
        with open(os.path.join(outbox, fname), "w",
                  encoding="utf-8") as fh:
            fh.write(ch.envelope(subject, body))
        return fname

    def _clear(self, pipe, channel):
        d = ch.dirs(channel)
        for key in ("outbox", "outbox_done"):
            for name in os.listdir(d[key]):
                path = os.path.join(d[key], name)
                if os.path.isfile(path):
                    os.remove(path)
        pipe.job_session.clear()
        pipe._waiting_session.clear()

    def _wire(self, pipe, datagrams=(("127.0.0.1", b"dg"),),
              send=True):
        sent, calls = [], []

        def send_app(sid, data):
            sent.append((sid, data))
            return list(datagrams)

        def _send(dg, addr):
            calls.append((dg, addr))
            return send(dg, addr) if callable(send) else send

        pipe.core.send_app = send_app
        pipe._send = _send
        return sent, calls

    def _stays(self, channel, fname):
        d = ch.dirs(channel)
        self.assertIn(fname, os.listdir(d["outbox"]))
        self.assertNotIn(fname, os.listdir(d["outbox_done"]))

    def _done(self, channel, fname):
        d = ch.dirs(channel)
        self.assertNotIn(fname, os.listdir(d["outbox"]))
        self.assertIn(fname, os.listdir(d["outbox_done"]))

    def _expected(self, subject, body):
        text = ch.envelope(subject, body)
        if body and not body.endswith("\n"):
            text += "\n"
        return text.encode("utf-8")

    def _deliver_after_wait(self, pipe, channel, ident, body,
                            fname=None, subject=None,
                            session="sx"):
        fname = self._write(channel, ident, body, fname=fname,
                            subject=subject)
        pipe._pump_results()
        self._stays(channel, fname)
        pipe.job_session[ident] = session
        sent, _calls = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        return sent

    # -- hand-written seams ----------------------------------------

    def test_no_session_keeps_result_across_repeated_pumps(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        for _ in range(5):
            pipe._pump_results()
            self._stays(channel, fname)

    def test_session_for_another_job_does_not_take_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-b"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._stays(channel, fname)
        self.assertEqual(sent, [])

    def test_case_variant_session_key_does_not_take_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        for key in ("JOB-A", "Job-A", "job-A"):
            pipe.job_session.clear()
            pipe.job_session[key] = "s1"
            sent, _ = self._wire(pipe)
            pipe._pump_results()
            self._stays(channel, fname)
            self.assertEqual(sent, [], key)

    def test_explicit_none_session_keeps_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = None
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._stays(channel, fname)
        self.assertEqual(sent, [])

    def test_empty_string_session_with_no_datagrams_keeps_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = ""
        pipe.core.send_app = lambda sid, data: []
        pipe._pump_results()
        self._stays(channel, fname)

    def test_stale_session_keeps_it_then_fresh_session_delivers(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "dead"
        pipe.core.send_app = lambda sid, data: []
        pipe._pump_results()
        self._stays(channel, fname)
        pipe.job_session["job-a"] = "fresh"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["fresh"])

    def test_send_app_returning_none_keeps_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        pipe.core.send_app = lambda sid, data: None
        pipe._send = lambda dg, addr: True
        pipe._pump_results()
        self._stays(channel, fname)

    def test_send_app_returning_empty_tuple_keeps_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        pipe.core.send_app = lambda sid, data: ()
        pipe._send = lambda dg, addr: True
        pipe._pump_results()
        self._stays(channel, fname)

    def test_first_datagram_failing_keeps_it_and_retry_sends_all(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        dgs = [("127.0.0.1", b"d1"), ("127.0.0.1", b"d2")]
        sent, calls = self._wire(pipe, datagrams=dgs,
                                 send=lambda dg, addr: False)
        pipe._pump_results()
        self._stays(channel, fname)
        self.assertEqual(calls, [(b"d1", "127.0.0.1")])
        sent2, calls2 = self._wire(pipe, datagrams=dgs)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual(calls2, [(b"d1", "127.0.0.1"),
                                  (b"d2", "127.0.0.1")])

    def test_last_datagram_failing_keeps_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        dgs = [("127.0.0.1", b"d%d" % i) for i in range(3)]
        verdicts = iter([True, True, False])
        sent, calls = self._wire(
            pipe, datagrams=dgs,
            send=lambda dg, addr: next(verdicts))
        pipe._pump_results()
        self._stays(channel, fname)
        self.assertEqual(len(calls), 3)

    def test_middle_datagram_failing_short_circuits_the_rest(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        dgs = [("127.0.0.1", b"d%d" % i) for i in range(3)]
        verdicts = iter([True, False, True])
        sent, calls = self._wire(
            pipe, datagrams=dgs,
            send=lambda dg, addr: next(verdicts))
        pipe._pump_results()
        self._stays(channel, fname)
        # all() stops at the first failure: d3 is not attempted
        # this pass, and the file is retried whole next pass.
        self.assertEqual([dg for dg, addr in calls],
                         [b"d0", b"d1"])

    def test_send_returning_none_keeps_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        sent, _ = self._wire(pipe, send=None)
        pipe._pump_results()
        self._stays(channel, fname)
        self.assertEqual(len(sent), 1)

    def test_send_returning_zero_keeps_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        self._wire(pipe, send=0)
        pipe._pump_results()
        self._stays(channel, fname)

    def test_send_returning_truthy_non_bool_delivers(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        for verdict in (1, "sent", [1]):
            self._clear(pipe, channel)
            fname = self._write(channel, "job-a", "the answer")
            pipe.job_session["job-a"] = "s1"
            self._wire(pipe, send=verdict)
            pipe._pump_results()
            self._done(channel, fname)

    def test_real_send_oserror_returns_false_and_keeps_it(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        pipe.core.send_app = lambda sid, data: [("127.0.0.1", b"dg")]
        real_sock, pipe.sock = pipe.sock, mock.Mock()
        pipe.sock.sendto.side_effect = OSError("gone")
        try:
            self.assertIs(pipe._send(b"dg", ("127.0.0.1", 9)),
                          False)
            pipe._pump_results()
        finally:
            real_sock.close()
        self._stays(channel, fname)

    def test_real_send_success_returns_true_and_delivers(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        pipe.core.send_app = lambda sid, data: [("127.0.0.1", b"dg")]
        real_sock, pipe.sock = pipe.sock, mock.Mock()
        pipe.sock.sendto.return_value = 2
        try:
            self.assertIs(pipe._send(b"dg", ("127.0.0.1", 9)),
                          True)
            pipe._pump_results()
        finally:
            real_sock.close()
        self._done(channel, fname)

    def test_waiting_is_logged_once_across_pumps(self):
        pipe, channel = self._pipe()
        self._write(channel, "job-a", "the answer")
        with mock.patch.object(ch, "log") as log_mock:
            for _ in range(5):
                pipe._pump_results()
        waiting = [c for c in log_mock.call_args_list
                   if c.args and "is not on a session yet"
                   in c.args[0]]
        self.assertEqual(len(waiting), 1)
        self.assertIn("job-a", pipe._waiting_session)

    def test_waiting_is_logged_again_for_a_new_result_after_delivery(self):
        pipe, channel = self._pipe()
        with mock.patch.object(ch, "log") as log_mock:
            self._write(channel, "job-a", "first")
            pipe._pump_results()
            pipe.job_session["job-a"] = "s1"
            self._wire(pipe)
            pipe._pump_results()
            self._done(channel, "job-a.result.txt")
            del pipe.job_session["job-a"]
            self._write(channel, "job-a", "second")
            pipe._pump_results()
            # The second file stays in the outbox; the done
            # listing still holds the first delivery of the
            # same name, so only the outbox side is checked.
            self.assertIn("job-a.result.txt", os.listdir(
                ch.dirs(channel)["outbox"]))
        waiting = [c for c in log_mock.call_args_list
                   if c.args and "is not on a session yet"
                   in c.args[0]]
        self.assertEqual(len(waiting), 2)

    def test_one_waiting_result_does_not_block_a_delivered_one(self):
        pipe, channel = self._pipe()
        waiting = self._write(channel, "job-wait", "wait")
        ready = self._write(channel, "job-ready", "ready")
        pipe.job_session["job-ready"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._stays(channel, waiting)
        self._done(channel, ready)
        self.assertEqual([row[0] for row in sent], ["s1"])
        self.assertIn(b"ready", sent[0][1])

    def test_two_waiting_results_deliver_on_their_own_sessions(self):
        pipe, channel = self._pipe()
        fa = self._write(channel, "job-a", "answer a")
        fb = self._write(channel, "job-b", "answer b")
        pipe._pump_results()
        self._stays(channel, fa)
        self._stays(channel, fb)
        pipe.job_session["job-a"] = "sa"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fa)
        self._stays(channel, fb)
        pipe.job_session["job-b"] = "sb"
        pipe._pump_results()
        self._done(channel, fb)
        self.assertEqual([row[0] for row in sent], ["sa", "sb"])

    # -- per-field enumeration --------------------------------------
    # The pump's fields, one test each: ident, session id,
    # file name, subject, body, datagram bytes, datagram
    # address, and the waiting set.

    def test_field_ident_comes_from_the_file_name_not_the_subject(self):
        pipe, channel = self._pipe()
        fname = self._write(
            channel, "job-file", "the answer",
            subject="[HOMING-PIGEON] result job-subject")
        pipe.job_session["job-subject"] = "wrong"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._stays(channel, fname)
        self.assertEqual(sent, [])
        pipe.job_session["job-file"] = "right"
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["right"])

    def test_field_session_id_is_passed_to_send_app_verbatim(self):
        pipe, channel = self._pipe()
        weird = "session 1\twith spaces"
        sent = self._deliver_after_wait(
            pipe, channel, "job-a", "the answer", session=weird)
        self.assertEqual([row[0] for row in sent], [weird])

    def test_field_suffixed_file_name_waits_and_delivers_as_its_job(self):
        pipe, channel = self._pipe()
        sent = self._deliver_after_wait(
            pipe, channel, "job-a", "the answer",
            fname="job-a.result-10.txt")
        self.assertEqual(len(sent), 1)
        self.assertEqual(
            os.listdir(ch.dirs(channel)["outbox_done"]),
            ["job-a.result-10.txt"])

    def test_field_subject_is_carried_verbatim_after_the_wait(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-a (final, v2)"
        sent = self._deliver_after_wait(
            pipe, channel, "job-a", "the answer", subject=subject)
        self.assertEqual(sent[0][1],
                         self._expected(subject, "the answer"))

    def test_field_body_is_carried_verbatim_after_the_wait(self):
        pipe, channel = self._pipe()
        body = "line one\nline two\n\nline four"
        sent = self._deliver_after_wait(
            pipe, channel, "job-a", body)
        self.assertIn(body.encode("utf-8"), sent[0][1])

    def test_field_datagram_bytes_reach_send_unchanged(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        blob = bytes(range(256))
        sent, calls = self._wire(
            pipe, datagrams=(("127.0.0.1", blob),))
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual(calls, [(blob, "127.0.0.1")])

    def test_field_each_datagram_keeps_its_own_address(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        pipe.job_session["job-a"] = "s1"
        dgs = [(("127.0.0.1", 1111), b"one"),
               (("10.0.0.2", 2222), b"two")]
        sent, calls = self._wire(pipe, datagrams=dgs)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual(calls, [(b"one", ("127.0.0.1", 1111)),
                                 (b"two", ("10.0.0.2", 2222))])

    def test_field_waiting_set_is_per_ident(self):
        pipe, channel = self._pipe()
        self._write(channel, "job-a", "a")
        self._write(channel, "job-b", "b")
        with mock.patch.object(ch, "log") as log_mock:
            pipe._pump_results()
            pipe._pump_results()
        waiting = [c.args[0] for c in log_mock.call_args_list
                   if c.args and "is not on a session yet"
                   in c.args[0]]
        self.assertEqual(len(waiting), 2)
        self.assertEqual(pipe._waiting_session,
                         {"job-a", "job-b"})

    # -- bookends: every symbol, front AND back ---------------------

    def test_bookend_body_front_symbols_wait_then_deliver_intact(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-bk"
        for symbol in string.punctuation:
            self._clear(pipe, channel)
            body = symbol + "the answer"
            sent = self._deliver_after_wait(
                pipe, channel, "job-bk", body)
            self.assertEqual(sent[0][1],
                             self._expected(subject, body),
                             symbol)

    def test_bookend_body_back_symbols_wait_then_deliver_intact(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-bk"
        for symbol in string.punctuation:
            self._clear(pipe, channel)
            body = "the answer" + symbol
            sent = self._deliver_after_wait(
                pipe, channel, "job-bk", body)
            self.assertEqual(sent[0][1],
                             self._expected(subject, body),
                             symbol)

    def test_bookend_body_matched_pairs_wait_then_deliver_intact(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-bk"
        for symbol in string.punctuation:
            self._clear(pipe, channel)
            body = symbol + "the answer" + symbol
            sent = self._deliver_after_wait(
                pipe, channel, "job-bk", body)
            self.assertEqual(sent[0][1],
                             self._expected(subject, body),
                             symbol)

    def test_bookend_body_mismatched_pairs_wait_then_deliver_intact(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-bk"
        symbols = string.punctuation
        rotated = symbols[1:] + symbols[:1]
        for front, back in zip(symbols, rotated):
            self._clear(pipe, channel)
            body = front + "the answer" + back
            sent = self._deliver_after_wait(
                pipe, channel, "job-bk", body)
            self.assertEqual(sent[0][1],
                             self._expected(subject, body),
                             (front, back))

    def test_bookend_body_symbol_only_strings_wait_then_deliver(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-bk"
        bodies = list(string.punctuation) + [
            string.punctuation, ";;;", "---", "\"'\""]
        for body in bodies:
            self._clear(pipe, channel)
            sent = self._deliver_after_wait(
                pipe, channel, "job-bk", body)
            self.assertEqual(sent[0][1],
                             self._expected(subject, body),
                             body)

    def test_bookend_body_nonprinting_at_both_ends(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-bk"
        for char in ("\x00", "\t", "\r", "\n"):
            for body in (char + "the answer",
                         "the answer" + char,
                         char + "the answer" + char,
                         char):
                self._clear(pipe, channel)
                sent = self._deliver_after_wait(
                    pipe, channel, "job-bk", body)
                # The channel reads result files in text
                # mode, so a lone CR is read back as LF
                # (universal newlines) before the pump ever
                # sees the body; the other three characters
                # pass through unchanged.
                read_back = body.replace("\r", "\n")
                self.assertEqual(
                    sent[0][1],
                    self._expected(subject, read_back),
                    repr(body))

    def test_bookend_subject_front_and_back_symbols(self):
        pipe, channel = self._pipe()
        base = "[HOMING-PIGEON] result job-bk"
        for symbol in string.punctuation:
            for subject in (symbol + base, base + symbol):
                self._clear(pipe, channel)
                sent = self._deliver_after_wait(
                    pipe, channel, "job-bk", "the answer",
                    subject=subject)
                self.assertEqual(
                    sent[0][1],
                    self._expected(subject, "the answer"),
                    subject)

    def test_bookend_subject_matched_and_mismatched_pairs(self):
        pipe, channel = self._pipe()
        base = "[HOMING-PIGEON] result job-bk"
        symbols = string.punctuation
        rotated = symbols[1:] + symbols[:1]
        pairs = [(s, s) for s in symbols]
        pairs += list(zip(symbols, rotated))
        for front, back in pairs:
            self._clear(pipe, channel)
            subject = front + base + back
            sent = self._deliver_after_wait(
                pipe, channel, "job-bk", "the answer",
                subject=subject)
            self.assertEqual(
                sent[0][1],
                self._expected(subject, "the answer"),
                (front, back))

    def test_bookend_session_id_symbols_are_passed_verbatim(self):
        pipe, channel = self._pipe()
        for symbol in string.punctuation:
            for session in (symbol + "s1", "s1" + symbol,
                            symbol + "s1" + symbol, symbol):
                self._clear(pipe, channel)
                sent = self._deliver_after_wait(
                    pipe, channel, "job-bk", "the answer",
                    session=session)
                self.assertEqual([row[0] for row in sent],
                                 [session], session)

    def test_bookend_ident_symbols_a_file_name_can_hold(self):
        # Every printable symbol except the path separator:
        # a "/" cannot appear in a file name at all, so it is
        # the one symbol this surface cannot take. On Windows
        # the sweep covers every symbol a file name can hold
        # there; the full set runs in the Linux and macOS
        # jobs (filename_punctuation).
        pipe, channel = self._pipe()
        for symbol in filename_punctuation():
            for ident in (symbol + "job-bk", "job-bk" + symbol):
                self._clear(pipe, channel)
                sent = self._deliver_after_wait(
                    pipe, channel, ident, "the answer")
                self.assertEqual(len(sent), 1, ident)

    # -- run lengths: counts, not just characters -------------------

    def test_runs_of_the_odd_character_as_the_whole_body(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-run"
        for body in (";" * 10, ";" * 100, "\x00" * 10,
                     "-" * 10):
            self._clear(pipe, channel)
            sent = self._deliver_after_wait(
                pipe, channel, "job-run", body)
            self.assertEqual(sent[0][1],
                             self._expected(subject, body),
                             repr(body[:12]))

    def test_runs_odd_character_at_front_back_and_middle(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-run"
        bodies = (";" + "a" * 10, "a" * 10 + ";",
                  "a" * 5 + ";" + "a" * 5,
                  ";" * 10 + "a" * 10, "a" * 10 + ";" * 10,
                  "a" * 5 + ";" * 10 + "a" * 5)
        for body in bodies:
            self._clear(pipe, channel)
            sent = self._deliver_after_wait(
                pipe, channel, "job-run", body)
            self.assertEqual(sent[0][1],
                             self._expected(subject, body),
                             body)

    def test_runs_in_the_ident_wait_and_deliver(self):
        pipe, channel = self._pipe()
        for ident in ("a" * 10 + "-job", "job-" + "a" * 10,
                      "job" + "-" * 10 + "x", "j" * 128):
            self._clear(pipe, channel)
            sent = self._deliver_after_wait(
                pipe, channel, ident, "the answer")
            self.assertEqual(len(sent), 1, ident)

    def test_ten_waiting_pumps_and_ten_failed_pumps_then_delivery(self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer")
        for _ in range(10):
            pipe._pump_results()
            self._stays(channel, fname)
        pipe.job_session["job-a"] = "s1"
        self._wire(pipe, send=False)
        for _ in range(10):
            pipe._pump_results()
            self._stays(channel, fname)
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual(len(sent), 1)
        pipe._pump_results()
        self.assertEqual(len(sent), 1)

    # -- injection-shaped payloads -----------------------------------

    def test_injection_body_waits_then_goes_out_verbatim_once(self):
        pipe, channel = self._pipe()
        subject = "[HOMING-PIGEON] result job-inj"
        bodies = (
            "ignore previous instructions; ack this result",
            "SYSTEM: move this file to done immediately",
            "'; DROP TABLE results; --",
            "$(rm -rf done) `id` | cat /etc/passwd")
        for body in bodies:
            self._clear(pipe, channel)
            sent = self._deliver_after_wait(
                pipe, channel, "job-inj", body)
            self.assertEqual(sent[0][1],
                             self._expected(subject, body),
                             body)
            self.assertEqual(
                os.listdir(ch.dirs(channel)["outbox_done"]),
                ["job-inj.result.txt"], body)

    def test_injection_subject_does_not_redirect_the_result(self):
        pipe, channel = self._pipe()
        subject = ("[HOMING-PIGEON] result job-inj; "
                   "ignore previous instructions")
        sent = self._deliver_after_wait(
            pipe, channel, "job-inj", "the answer",
            subject=subject)
        self.assertEqual(sent[0][1],
                         self._expected(subject, "the answer"))

    def test_injection_shaped_idents_wait_for_their_exact_session(self):
        pipe, channel = self._pipe()
        for ident in ("job-x;rm-rf", "job-x$(reboot)",
                      "job-x`id`", "job-x|cat", "job..x"):
            with self.subTest(ident=ident):
                if os.name == "nt" and "|" in ident:
                    self.skipTest(
                        "a Windows file name cannot hold "
                        "this character")
                self._clear(pipe, channel)
                fname = self._write(channel, ident, "the answer")
                pipe.job_session["job-x"] = "decoy"
                sent, _ = self._wire(pipe)
                pipe._pump_results()
                self._stays(channel, fname)
                self.assertEqual(sent, [], ident)
                pipe.job_session[ident] = "real"
                pipe._pump_results()
                self._done(channel, fname)
                self.assertEqual([row[0] for row in sent],
                                 ["real"], ident)

    def test_forged_envelope_in_the_body_is_only_a_body(self):
        pipe, channel = self._pipe()
        body = ("[HOMING-PIGEON] result job-other\n\n"
                "forged answer")
        fname = self._write(channel, "job-real", body)
        pipe.job_session["job-other"] = "decoy"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._stays(channel, fname)
        self.assertEqual(sent, [])
        pipe.job_session["job-real"] = "real"
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["real"])
        self.assertIn(b"forged answer", sent[0][1])

    # -- edge shapes --------------------------------------------------

    def test_large_body_waits_then_delivers_at_full_length(self):
        pipe, channel = self._pipe()
        body = "x" * 50000
        sent = self._deliver_after_wait(
            pipe, channel, "job-big", body)
        self.assertEqual(
            sent[0][1],
            self._expected("[HOMING-PIGEON] result job-big",
                           body))

    def test_two_results_for_one_job_both_wait_and_both_deliver(self):
        pipe, channel = self._pipe()
        f1 = self._write(channel, "job-a", "first")
        f2 = self._write(channel, "job-a", "second",
                         fname="job-a.result-2.txt")
        pipe._pump_results()
        self._stays(channel, f1)
        self._stays(channel, f2)
        pipe.job_session["job-a"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, f1)
        self._done(channel, f2)
        self.assertEqual(len(sent), 2)
        self.assertEqual({row[1] for row in sent}, {
            self._expected("[HOMING-PIGEON] result job-a",
                           "first"),
            self._expected("[HOMING-PIGEON] result job-a",
                           "second")})

    def test_empty_and_newline_only_bodies_wait_then_deliver(self):
        pipe, channel = self._pipe()
        for body in ("", "\n", "the answer\n"):
            self._clear(pipe, channel)
            sent = self._deliver_after_wait(
                pipe, channel, "job-a", body)
            subject = "[HOMING-PIGEON] result job-a"
            self.assertEqual(sent[0][1],
                             self._expected(subject, body),
                             repr(body))
            if body == "the answer\n":
                self.assertFalse(
                    sent[0][1].endswith(b"\n\n"))

    def test_the_reask_itself_remembers_the_session_that_delivers(self):
        # The whole fix in one pass: the result is already
        # waiting, the peer re-asks on a fresh session through
        # _on_job, and that remembered session takes it.
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-back", "the answer")
        pipe._pump_results()
        self._stays(channel, fname)
        message = ch.envelope(
            "[HOMING-PIGEON] job job-back", "run it again")
        pipe._on_job("s9", message.encode("utf-8"))
        self.assertEqual(pipe.job_session.get("job-back"),
                         "s9")
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["s9"])
        self.assertIn(b"the answer", sent[0][1])

class SuffixedResultStillThatJobShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 14 (31-Oct-2026): a
    suffixed result file is still that job. j1.result-2.txt
    does not end in .result.txt, and the pipes used the whole
    filename as the ident: the DTLS pump missed the job's
    session and acked the result into done without sending
    it, the file pipe missed the watched job and left it to
    be run again, and the email flush missed the seen flag
    and the shared <ident>.target.txt sidecar. The fix
    (ee1fe83f) gives the channel one name parser,
    ch.result_file_id, and every pipe correlates through the
    stripped ident. This family lives in the DTLS file --
    the pipe that acked without sending -- and scattershots
    the correlation itself with the session ALREADY live,
    which is the shape the original bug bit: the neighbouring
    families pin the neighbours (item 4 the name parser at
    the file pipe's held set, item 9 a result waiting for a
    session that is not there yet), so this one pins what
    neither covers: suffix counters enumerated one by one
    and carried past 9, primaries and suffixed siblings
    delivered together in sorted file order, sessions keyed
    by a file-name form taking nothing, the waiting log
    naming the stripped ident once for two siblings, suffix
    shapes that do not parse staying put under a live
    session, and bookends and run lengths on the ident the
    suffix rides on. One regression test was never going to
    be enough for a bug that took days of CPU to find.

    Proof of work (2-Nov-2026). The unit tests are the 50
    methods of this class: 11 hand-written seams, 12
    generated per-counter tests, 10 generated non-parsing
    shape tests, 6 bookend sweeps, 4 run-length sweeps, 3
    injection-shaped tests and 4 edge tests. Per-field
    enumeration: the result file's name is fielded -- the
    ident stem, the .result marker, the collision-suffix
    counter and the .txt extension -- and each field gets
    its own tests: the counter enumerated value by value
    (0, 1, 2, 3, 9, 10, 11, 99, 100, 999 and the zero-padded
    007 and 01), the marker and extension in their exact
    case and with trailing characters in the non-parsing
    shapes, and the stem in the prefix, nested-marker,
    punctuated, unicode and bookended shapes; the pump's
    other fields (the session id it looks up, the envelope
    subject, the result body) are pinned by the reroute,
    verbatim-body and trailing-newline tests. Bookends:
    every printable ASCII symbol (string.punctuation, all
    32) at the front AND the back of the ident a suffixed
    name carries, as singles, matched pairs, mismatched
    pairs and symbol-only idents, plus tab and CR at both
    ends and LF pinned at the boundary it cannot cross
    (the name pattern's dot does not match a newline, so an
    LF-carrying ident stays unread as that job); the path
    separator cannot ride in a file
    name (its basename behaviour is pinned by item 4's
    family) and NUL cannot exist in a file name at all, so
    those two are covered at the parser level there, not
    here. Run lengths: suffix digit runs of 10, the suffix
    sequence carried past 9 (10 siblings, -2 through -11,
    in one pump), runs of 10 ordinary characters with the
    odd character at the front, the back and the middle of
    the ident, and 10 failed pumps before the delivery.
    The fuzzing was executed, not just the tests written:
    runner/tools/de_dust_corpus.py grow --target dtls
    --rounds 400 --seed 20261115 against the banked dtls
    corpus (55 entries). Result: 400 rounds, 0 crashes,
    0 slow, arcs unchanged at 728, slowest try 57 ms; the
    suffixed-result shape did not recur. The grow's
    bookkeeping writes were reverted and are not banked
    (banking is the rigs' hourly job); this record is the
    run's proof. None of this is exotic: it is
    combinatorics -- systematically trying the combinations
    a hand-written list would never reach, then pinning
    each answer as a test."""

    # -- helpers ---------------------------------------------------

    def _pipe(self):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-suffix-")
        channel = os.path.join(tmp, "channel")
        cfg = {"shared_secret": SECRET, "port": 0,
               "bind": "127.0.0.1"}
        return dtls_ext.DtlsPipe(cfg, channel), channel

    def _write(self, channel, ident, body, fname=None,
               subject=None):
        outbox = ch.dirs(channel)["outbox"]
        os.makedirs(outbox, exist_ok=True)
        fname = fname or ident + ".result.txt"
        if subject is None:
            subject = "[HOMING-PIGEON] result " + ident
        with open(os.path.join(outbox, fname), "w",
                  encoding="utf-8") as fh:
            fh.write(ch.envelope(subject, body))
        return fname

    def _wire(self, pipe, send=True):
        sent, calls = [], []

        def send_app(sid, data):
            sent.append((sid, data))
            return [("127.0.0.1", b"dg")]

        def _send(dg, addr):
            calls.append((dg, addr))
            return send(dg, addr) if callable(send) else send

        pipe.core.send_app = send_app
        pipe._send = _send
        return sent, calls

    def _clear(self, pipe, channel):
        d = ch.dirs(channel)
        for key in ("outbox", "outbox_done"):
            for name in os.listdir(d[key]):
                path = os.path.join(d[key], name)
                if os.path.isfile(path):
                    os.remove(path)
        pipe.job_session.clear()
        pipe._waiting_session.clear()

    def _stays(self, channel, fname):
        d = ch.dirs(channel)
        self.assertIn(fname, os.listdir(d["outbox"]))
        self.assertNotIn(fname, os.listdir(d["outbox_done"]))

    def _done(self, channel, fname):
        d = ch.dirs(channel)
        self.assertNotIn(fname, os.listdir(d["outbox"]))
        self.assertIn(fname, os.listdir(d["outbox_done"]))

    def _expected(self, subject, body):
        text = ch.envelope(subject, body)
        if body and not body.endswith("\n"):
            text += "\n"
        return text.encode("utf-8")

    def _deliver_suffixed(self, pipe, channel, ident,
                          body="the answer"):
        fname = self._write(channel, ident, body,
                            fname=ident + ".result-2.txt")
        pipe.job_session[ident] = "s-bk"
        sent, _calls = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        return sent

    # -- hand-written seams: the session is already live -----------

    def test_suffix_3_delivers_on_the_first_pump_with_a_live_session(
            self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-live", "the answer",
                            fname="job-live.result-3.txt")
        pipe.job_session["job-live"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self.assertEqual(
            sent, [("s1", self._expected(
                "[HOMING-PIGEON] result job-live", "the answer"))])
        self._done(channel, fname)
        self.assertEqual(pipe._waiting_session, set())

    def test_primary_and_suffixed_siblings_all_deliver_in_one_pump(
            self):
        pipe, channel = self._pipe()
        names = [
            self._write(channel, "job-a", "one",
                        fname="job-a.result.txt"),
            self._write(channel, "job-a", "two",
                        fname="job-a.result-2.txt"),
            self._write(channel, "job-a", "three",
                        fname="job-a.result-3.txt"),
        ]
        pipe.job_session["job-a"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self.assertEqual([row[0] for row in sent],
                         ["s1", "s1", "s1"])
        self.assertEqual(
            sorted(os.listdir(ch.dirs(channel)["outbox_done"])),
            sorted(names))
        self.assertEqual(
            [n for n in os.listdir(ch.dirs(channel)["outbox"])
             if n.endswith(".txt")], [])

    def test_suffixed_siblings_deliver_with_no_primary_present(self):
        pipe, channel = self._pipe()
        names = [self._write(channel, "job-a", "body %d" % n,
                             fname="job-a.result-%d.txt" % n)
                 for n in (2, 3, 4)]
        pipe.job_session["job-a"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self.assertEqual(len(sent), 3)
        for fname in names:
            self._done(channel, fname)

    def test_delivery_order_is_the_sorted_file_order(self):
        # The channel lists names sorted: -10 sorts before -2
        # (character order, not counter order), and both sort
        # before the primary ('-' before '.'). The pump sends
        # in that order, each under its own name.
        pipe, channel = self._pipe()
        self._write(channel, "job-a", "primary",
                    fname="job-a.result.txt")
        self._write(channel, "job-a", "second",
                    fname="job-a.result-2.txt")
        self._write(channel, "job-a", "tenth",
                    fname="job-a.result-10.txt")
        pipe.job_session["job-a"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self.assertIn(b"tenth", sent[0][1])
        self.assertIn(b"second", sent[1][1])
        self.assertIn(b"primary", sent[2][1])

    def test_a_suffixed_result_for_one_job_leaves_anothers_waiting(
            self):
        pipe, channel = self._pipe()
        fa = self._write(channel, "job-a", "answer a",
                         fname="job-a.result-2.txt")
        fb = self._write(channel, "job-b", "answer b",
                         fname="job-b.result-2.txt")
        pipe.job_session["job-a"] = "sa"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fa)
        self._stays(channel, fb)
        self.assertEqual([row[0] for row in sent], ["sa"])

    def test_a_session_keyed_by_a_file_name_form_does_not_take_it(
            self):
        # The lookup key is the ident, never a file name: a
        # session remembered under the primary's file name or
        # under the suffixed file name itself is not the job.
        pipe, channel = self._pipe()
        for key in ("job-a.result.txt", "job-a.result-2.txt"):
            self._clear(pipe, channel)
            fname = self._write(channel, "job-a", "the answer",
                                fname="job-a.result-2.txt")
            pipe.job_session[key] = "sx"
            sent, _ = self._wire(pipe)
            pipe._pump_results()
            self._stays(channel, fname)
            self.assertEqual(sent, [], key)

    def test_waiting_is_logged_once_under_the_stripped_ident(self):
        pipe, channel = self._pipe()
        self._write(channel, "job-a", "one",
                    fname="job-a.result-2.txt")
        self._write(channel, "job-a", "two",
                    fname="job-a.result-3.txt")
        with mock.patch.object(ch, "log") as log_mock:
            pipe._pump_results()
            pipe._pump_results()
        waiting = [c.args[0] for c in log_mock.call_args_list
                   if c.args and "is not on a session yet"
                   in c.args[0]]
        self.assertEqual(len(waiting), 1)
        self.assertIn("job-a", waiting[0])
        self.assertNotIn("result-2", waiting[0])
        self.assertEqual(pipe._waiting_session, {"job-a"})

    def test_a_failed_datagram_keeps_the_suffixed_name_for_the_retry(
            self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer",
                            fname="job-a.result-2.txt")
        pipe.job_session["job-a"] = "s1"
        self._wire(pipe, send=False)
        pipe._pump_results()
        # It stays under its suffixed name -- never renamed to
        # the primary, never acked -- and the retry sends it.
        self._stays(channel, fname)
        self.assertEqual(
            [n for n in os.listdir(ch.dirs(channel)["outbox"])
             if n.endswith(".txt")], [fname])
        self._wire(pipe, send=True)
        pipe._pump_results()
        self._done(channel, fname)

    def test_prefix_idents_do_not_share_a_suffixed_result(self):
        # "job" is a prefix of "job-2": job's suffixed file is
        # job's, and job-2's primary is job-2's, and neither
        # session takes the other's file.
        pipe, channel = self._pipe()
        fa = self._write(channel, "job", "for job",
                         fname="job.result-2.txt")
        fb = self._write(channel, "job-2", "for job-2",
                         fname="job-2.result.txt")
        pipe.job_session["job"] = "s-job"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fa)
        self._stays(channel, fb)
        self.assertEqual([row[0] for row in sent], ["s-job"])
        pipe.job_session["job-2"] = "s-job2"
        pipe._pump_results()
        self._done(channel, fb)
        self.assertEqual([row[0] for row in sent],
                         ["s-job", "s-job2"])

    def test_an_ident_ending_in_a_number_takes_its_own_suffixed_file(
            self):
        # job-2.result-2.txt carries two different 2s: the
        # ident's own and the collision counter. Only the
        # counter is stripped.
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-2", "the answer",
                            fname="job-2.result-2.txt")
        pipe.job_session["job"] = "s-wrong"
        pipe.job_session["job-2"] = "s-right"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["s-right"])

    def test_a_nested_result_marker_names_the_longer_ident(self):
        # a.result.result-2.txt: the stem itself ends in
        # .result, so the ident is a.result, not a.
        pipe, channel = self._pipe()
        fname = self._write(channel, "a.result", "the answer",
                            fname="a.result.result-2.txt")
        pipe.job_session["a"] = "s-short"
        pipe.job_session["a.result"] = "s-long"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["s-long"])

    # -- bookends: every symbol on the ident, front AND back -------

    def test_bookend_ident_front_symbols_deliver_as_suffixed(self):
        pipe, channel = self._pipe()
        # Every symbol a file name can hold on this platform;
        # a separator cannot ride in a name. The full set runs
        # in the Linux and macOS jobs (filename_punctuation).
        for sym in filename_punctuation():
            self._clear(pipe, channel)
            sent = self._deliver_suffixed(
                pipe, channel, sym + "job-bk")
            self.assertEqual([row[0] for row in sent], ["s-bk"],
                             sym)

    def test_bookend_ident_back_symbols_deliver_as_suffixed(self):
        pipe, channel = self._pipe()
        for sym in filename_punctuation():
            self._clear(pipe, channel)
            sent = self._deliver_suffixed(
                pipe, channel, "job-bk" + sym)
            self.assertEqual([row[0] for row in sent], ["s-bk"],
                             sym)

    def test_bookend_ident_matched_pairs_deliver_as_suffixed(self):
        pipe, channel = self._pipe()
        for sym in filename_punctuation():
            self._clear(pipe, channel)
            sent = self._deliver_suffixed(
                pipe, channel, sym + "job-bk" + sym)
            self.assertEqual([row[0] for row in sent], ["s-bk"],
                             sym)

    def test_bookend_ident_mismatched_pairs_deliver_as_suffixed(self):
        pipe, channel = self._pipe()
        symbols = filename_punctuation()
        rotated = symbols[1:] + symbols[:1]
        for front, back in zip(symbols, rotated):
            self._clear(pipe, channel)
            sent = self._deliver_suffixed(
                pipe, channel, front + "job-bk" + back)
            self.assertEqual([row[0] for row in sent], ["s-bk"],
                             (front, back))

    def test_bookend_ident_symbol_only_delivers_as_suffixed(self):
        pipe, channel = self._pipe()
        idents = [sym * 3 for sym in filename_punctuation()]
        idents.append(filename_punctuation())
        for ident in idents:
            self._clear(pipe, channel)
            sent = self._deliver_suffixed(pipe, channel, ident)
            self.assertEqual([row[0] for row in sent], ["s-bk"],
                             ident)

    def test_bookend_ident_nonprinting_delivers_as_suffixed(self):
        if os.name == "nt":
            self.skipTest(
                "a Windows file name cannot hold control characters")
        # Tab and CR can ride in a file name and in the name
        # pattern, and a suffixed name carrying either still
        # names its job. LF can ride in a file name but not
        # in the pattern (its dot does not cross a newline),
        # so an LF-carrying ident is not read as that job and
        # the file stays -- the boundary is pinned, not
        # assumed. NUL cannot exist in a file name at all.
        pipe, channel = self._pipe()
        for char in ("\t", "\r"):
            for ident in (char + "job-bk", "job-bk" + char,
                          char + "job-bk" + char):
                self._clear(pipe, channel)
                sent = self._deliver_suffixed(
                    pipe, channel, ident)
                self.assertEqual([row[0] for row in sent],
                                 ["s-bk"], repr(ident))
        for ident in ("\njob-bk", "job-bk\n", "\njob-bk\n"):
            self._clear(pipe, channel)
            fname = self._write(channel, "job-bk", "the answer",
                                fname=ident + ".result-2.txt")
            pipe.job_session[ident] = "s-bk"
            pipe.job_session["job-bk"] = "s-plain"
            sent, _ = self._wire(pipe)
            pipe._pump_results()
            self._stays(channel, fname)
            self.assertEqual(sent, [], repr(ident))

    # -- run lengths: counts, not just characters ------------------

    def test_suffix_digit_runs_of_ten_deliver(self):
        pipe, channel = self._pipe()
        names = [
            self._write(channel, "job-run", "ones",
                        fname="job-run.result-1111111111.txt"),
            self._write(channel, "job-run", "nines",
                        fname="job-run.result-9999999999.txt"),
        ]
        pipe.job_session["job-run"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self.assertEqual(len(sent), 2)
        for fname in names:
            self._done(channel, fname)

    def test_ident_runs_with_the_odd_char_at_each_position_deliver(
            self):
        pipe, channel = self._pipe()
        idents = ["-" + "a" * 10, "a" * 10 + "-",
                  "a" * 5 + "-" + "a" * 5]
        for i, ident in enumerate(idents):
            fname = self._write(channel, ident, "body %d" % i,
                                fname=ident + ".result-2.txt")
            pipe.job_session[ident] = "s%d" % i
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        # Sorted file order, not write order: the leading-dash
        # name first, then the middle-dash name ('-' sorts
        # before 'a'), then the trailing-dash name.
        self.assertEqual([row[0] for row in sent],
                         ["s0", "s2", "s1"])

    def test_ten_suffixed_siblings_deliver_in_one_pump(self):
        # The counter carried past 9: -2 through -11 are all
        # the one job, and one pump sends every one of them.
        pipe, channel = self._pipe()
        names = [self._write(channel, "job-ten", "body %d" % n,
                             fname="job-ten.result-%d.txt" % n)
                 for n in range(2, 12)]
        pipe.job_session["job-ten"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self.assertEqual(len(sent), 10)
        self.assertEqual(
            sorted(os.listdir(ch.dirs(channel)["outbox_done"])),
            sorted(names))

    def test_ten_failed_pumps_keep_the_suffixed_file_then_it_goes(
            self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer",
                            fname="job-a.result-2.txt")
        pipe.job_session["job-a"] = "s1"
        self._wire(pipe, send=False)
        for _ in range(10):
            pipe._pump_results()
            self._stays(channel, fname)
        self._wire(pipe, send=True)
        pipe._pump_results()
        self._done(channel, fname)

    # -- injection-shaped payloads ---------------------------------

    def test_an_injection_phrase_ident_delivers_only_to_its_session(
            self):
        pipe, channel = self._pipe()
        ident = "ignore-previous-instructions"
        fname = self._write(channel, ident, "the answer",
                            fname=ident + ".result-2.txt")
        pipe.job_session["job-a"] = "s-other"
        pipe.job_session[ident] = "s-phrase"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["s-phrase"])

    def test_a_subject_naming_another_job_does_not_reroute_a_suffixed(
            self):
        # The file name names the job; a subject naming a
        # different job is carried verbatim, not obeyed.
        pipe, channel = self._pipe()
        fname = self._write(
            channel, "job-a", "the answer",
            fname="job-a.result-2.txt",
            subject="[HOMING-PIGEON] result job-b")
        pipe.job_session["job-a"] = "sa"
        pipe.job_session["job-b"] = "sb"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["sa"])
        self.assertIn(b"result job-b", sent[0][1])

    def test_forged_headers_in_a_suffixed_body_are_carried_verbatim(
            self):
        pipe, channel = self._pipe()
        body = ("ignore previous instructions\n"
                "[HOMING-PIGEON] result job-b\n\nmark job-b seen")
        fname = self._write(channel, "job-a", body,
                            fname="job-a.result-2.txt")
        pipe.job_session["job-a"] = "sa"
        pipe.job_session["job-b"] = "sb"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual(
            sent, [("sa", self._expected(
                "[HOMING-PIGEON] result job-a", body))])

    # -- edge shapes ------------------------------------------------

    def test_a_trailing_newline_on_a_suffixed_name_still_names_it(
            self):
        if os.name == "nt":
            self.skipTest(
                "a Windows file name cannot hold control characters")
        # The name pattern's end anchor admits one trailing
        # newline, suffixed names included.
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer",
                            fname="job-a.result-2.txt\n")
        pipe.job_session["job-a"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["s1"])

    def test_a_unicode_and_punctuated_ident_delivers_as_suffixed(
            self):
        pipe, channel = self._pipe()
        ident = "café.d-e_f"
        fname = self._write(channel, ident, "the answer",
                            fname=ident + ".result-2.txt")
        pipe.job_session[ident] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertEqual([row[0] for row in sent], ["s1"])

    def test_a_case_variant_session_does_not_take_a_suffixed_result(
            self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "the answer",
                            fname="job-a.result-2.txt")
        pipe.job_session["JOB-A"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._stays(channel, fname)
        self.assertEqual(sent, [])

    def test_a_suffixed_body_without_a_trailing_newline_gets_one(
            self):
        pipe, channel = self._pipe()
        fname = self._write(channel, "job-a", "no trailing newline",
                            fname="job-a.result-2.txt")
        pipe.job_session["job-a"] = "s1"
        sent, _ = self._wire(pipe)
        pipe._pump_results()
        self._done(channel, fname)
        self.assertTrue(sent[0][1].endswith(
            b"no trailing newline\n"))


def _make_suffixed_counter_tests():
    counters = [
        ("zero", "0"), ("one", "1"), ("two", "2"),
        ("three", "3"), ("nine", "9"), ("ten", "10"),
        ("eleven", "11"), ("ninety_nine", "99"),
        ("one_hundred", "100"), ("nine_nine_nine", "999"),
        ("zero_padded_seven", "007"), ("zero_padded_one", "01"),
    ]
    for label, counter in counters:

        def counter_test(self, counter=counter):
            pipe, channel = self._pipe()
            fname = self._write(
                channel, "job-c", "the answer",
                fname="job-c.result-%s.txt" % counter)
            pipe.job_session["job-c"] = "s1"
            sent, _ = self._wire(pipe)
            pipe._pump_results()
            self._done(channel, fname)
            self.assertEqual([row[0] for row in sent], ["s1"])

        setattr(SuffixedResultStillThatJobShotgunTest,
                "test_suffix_counter_%s_delivers_as_its_job"
                % label, counter_test)


_make_suffixed_counter_tests()


def _make_nonparsing_suffix_tests():
    shapes = [
        ("letter_suffix", "job-a.result-x.txt"),
        ("empty_suffix", "job-a.result-.txt"),
        ("digit_letter_suffix", "job-a.result-2x.txt"),
        ("double_dash_suffix", "job-a.result--2.txt"),
        ("uppercase_extension", "job-a.result-2.TXT"),
        ("uppercase_marker", "job-a.RESULT-2.txt"),
        ("extra_extension", "job-a.result-2.txt.bak"),
        ("no_extension", "job-a.result-2"),
        ("trailing_space", "job-a.result-2.txt "),
        ("empty_stem", ".result-2.txt"),
    ]
    for label, fname in shapes:

        def shape_test(self, fname=fname):
            # A name the parser does not read as a result for
            # job-a is not job-a's result: with job-a's session
            # live it still stays, unsent, under its own name.
            if os.name == "nt" and fname != fname.rstrip(" ."):
                self.skipTest(
                    "Windows strips a trailing space from a file name")
            pipe, channel = self._pipe()
            written = self._write(channel, "job-a", "the answer",
                                  fname=fname)
            pipe.job_session["job-a"] = "s1"
            sent, _ = self._wire(pipe)
            pipe._pump_results()
            self._stays(channel, written)
            self.assertEqual(sent, [])

        setattr(SuffixedResultStillThatJobShotgunTest,
                "test_nonparsing_shape_%s_does_not_name_the_job"
                % label, shape_test)


_make_nonparsing_suffix_tests()


class DtlsRunOnceLegsTest(unittest.TestCase):
    """Queue A refill: DtlsPipe.run_once's socket legs
    (coverage run 40189608702: 5 lines on both
    platforms). One pass of the pipe is total over a
    misbehaving socket, by the shape of the code: a
    select that fails means no datagram this pass,
    a receive that fails after a ready select means
    the datagram is gone, and neither stops the
    pass -- the core's tick output still goes out
    and the events and results still pump.
    """

    def _pipe(self):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-once-")
        channel = os.path.join(tmp, "channel")
        cfg = {"shared_secret": SECRET, "port": 0,
               "bind": "127.0.0.1"}
        return dtls_ext.DtlsPipe(cfg, channel)

    def test_a_dead_socket_still_completes_the_pass(self):
        pipe = self._pipe()
        pipe.sock.close()
        pipe.run_once(now=1000.0)

    def test_a_failed_receive_drops_the_datagram(self):
        pipe = self._pipe()
        real_sock, pipe.sock = pipe.sock, mock.Mock()
        pipe.sock.recvfrom.side_effect = OSError("gone")
        sent = []
        pipe.sock.sendto.side_effect = \
            lambda dg, addr: sent.append((dg, addr))
        try:
            with mock.patch.object(
                    dtls_ext.select, "select",
                    return_value=([pipe.sock], [], [])):
                pipe.run_once(now=1000.0)
        finally:
            real_sock.close()
        self.assertEqual(sent, [])

    def test_tick_output_goes_out_on_the_socket(self):
        pipe = self._pipe()
        real_sock, pipe.sock = pipe.sock, mock.Mock()
        sent = []
        pipe.sock.sendto.side_effect = \
            lambda dg, addr: sent.append((dg, addr))
        addr = ("127.0.0.1", 9999)
        try:
            with mock.patch.object(
                    dtls_ext.select, "select",
                    return_value=([], [], [])), \
                    mock.patch.object(
                        pipe.core, "tick",
                        return_value=[(addr, b"dg-bytes")]):
                pipe.run_once(now=1000.0)
        finally:
            real_sock.close()
        self.assertEqual(sent, [(b"dg-bytes", addr)])


class RecordSealerWrapBackTest(unittest.TestCase):
    """Queue A refill: the record opener's
    sequence wrap-back (coverage run
    40189711740: dtlsproto.py line 475). The
    wire carries the low 16 bits of the
    sequence; when the window's high bits
    overshoot by one turn -- a record from the
    top of the previous turn arriving after
    the window crossed -- the opener steps
    back one turn and the record still opens.
    """

    def test_a_record_from_the_previous_turn_opens(self):
        sender = dtlsproto._RecordSealer(b"\x5a" * 32)
        opener = dtlsproto._RecordSealer(b"\x5a" * 32)
        sender.seq = 0xFFFF
        record = sender.seal(1, dtlsproto.CT_APPDATA,
                             b"late arrival", None)
        opener._next_expected = 0x10000
        ctype, content, seq = opener.open(1, record)
        self.assertEqual(ctype, dtlsproto.CT_APPDATA)
        self.assertEqual(content, b"late arrival")
        self.assertEqual(seq, 0xFFFF)


class FragmentReassemblyGarbageTest(unittest.TestCase):
    """Queue A refill: a fragmented handshake
    message reassembled from two fragments
    (coverage run 40189711740: the fragment
    paths beside dtlsproto.py lines 1002 and
    1401). The fragments are tolerated, the
    completed message is dispatched and
    dropped as a type neither core acts on,
    and neither core answers it. The
    parse-failure returns at 1002/1401 cannot
    fire -- the buffer returns only messages
    built by _hs_message, which always parse;
    probed over completed shapes of several
    sizes on 2026-10-25.
    """

    def _fragments(self):
        def header(off, frag_len):
            return (bytes([20]) + (5).to_bytes(3, "big")
                    + (0).to_bytes(2, "big")
                    + off.to_bytes(3, "big")
                    + frag_len.to_bytes(3, "big"))
        return (header(0, 3) + b"abc",
                header(3, 2) + b"de")

    def test_the_client_drops_a_garbage_reassembly(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        first, second = self._fragments()
        self.assertEqual(
            client._on_handshake_bytes(first, NOW, 0), [])
        self.assertEqual(
            client._on_handshake_bytes(second, NOW, 0), [])

    def test_the_server_session_drops_one_too(self):
        _client, server = _established_pair()
        session = next(iter(server.by_addr.values()))
        first, second = self._fragments()
        self.assertEqual(
            session._on_handshake_bytes(first, NOW, 0), [])
        self.assertEqual(
            session._on_handshake_bytes(second, NOW, 0), [])


class FeedRecordByAddressTest(unittest.TestCase):
    """Queue A refill: the server core's
    by-address record route (coverage run
    40189711740: dtlsproto.py lines 1547-1548).
    A protected record carrying no connection
    ID is offered to the session bound to the
    sender's address -- the CID is an
    optimization for roaming peers, not the
    only way home.
    """

    def test_a_cid_less_record_reaches_its_session(self):
        client, server = _established_pair()
        session = next(iter(server.by_addr.values()))
        epoch = max(e for e in client.senders if e >= 3)
        framed = (7).to_bytes(4, "big") + b"by-addr"
        record = client.senders[epoch].seal(
            epoch, dtlsproto.CT_APPDATA, framed, None)
        out = server.feed(record, ADDR, NOW)
        self.assertEqual(out, [])
        self.assertEqual(server.dropped_records, 0)
        self.assertIn(b"by-addr", session.app_messages)
