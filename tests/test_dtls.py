"""Tests for the DTLS session binding (protocol version 2).

Layers, mirroring how the profile is built:

- X25519 against the RFC 7748 published vectors.
- The TLS 1.3 key schedule recomputed INDEPENDENTLY here
  (hashlib/hmac only, from the RFC 8446 section 7.1 text),
  checked against what a live handshake puts on the wire:
  the test decrypts the server's handshake flight itself and
  verifies the Finished MAC byte for byte.
- Core-to-core behavior over a hand relay: the cookie gate,
  psk_ke refusal (DRU's PFS rule), wrong-PSK refusal,
  greeting ordering, resumption with fresh DHE, NAT
  rebinding by Connection ID, tampered records, flight
  retransmission.
- The extension over real UDP loopback, the supervisor
  handoff, and one supervised end-to-end job.

The extension/greeting imports reach the pipe the same way
the supervisor launches it (module import), and the socket
tests use real UDP on localhost with ephemeral ports.
"""

import argparse
import hashlib
import hmac
import importlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "cloud"))

from runner import dtlsproto, jobcrypto, transports  # noqa: E402
from runner.runner import poll_once  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
import send_dtls  # noqa: E402
from send_job import sign_payload, verify_body  # noqa: E402

dtls_ext = importlib.import_module(
    "runner.transport_extensions.dtls.__main__")

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
WRONG = "ff2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937b00"
ADDR = ("127.0.0.1", 50001)
NOW = 1000.0


# ------------------------------------------------------------------
# In-test RFC 8446 machinery (independent of runner.dtlsproto)
# ------------------------------------------------------------------

def _ext(prk, info, n):
    out, block, c = b"", b"", 1
    while len(out) < n:
        block = hmac.new(prk, block + info + bytes([c]),
                         hashlib.sha256).digest()
        out += block
        c += 1
    return out[:n]


def _label(secret, label, ctx, n=32):
    full = b"tls13 " + label
    info = (n.to_bytes(2, "big") + bytes([len(full)]) + full
            + bytes([len(ctx)]) + ctx)
    return _ext(secret, info, n)


def _extract(salt, ikm):
    return hmac.new(salt, ikm, hashlib.sha256).digest()


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


def _established_pair(greeting=b'{"type":"greeting","v":2}'):
    server = dtlsproto.DtlsServerCore(
        secret_lookup=dtlsproto.make_secret_lookup(SECRET),
        greeting_for=lambda s: greeting)
    client = dtlsproto.DtlsClientCore(SECRET)
    _pump(client, server)
    assert client.state == "established"
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

        client = dtlsproto.DtlsClientCore(
            SECRET, rng=scripted(client_chunks))
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            greeting_for=lambda s: b"{}",
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
        empty = hashlib.sha256(b"").digest()
        early = _extract(b"\x00" * 32, SECRET.encode())
        derived = _label(early, b"derived", empty)
        share = sh_exts[dtlsproto.EXT_KEY_SHARE]
        server_pub = share[4:4 + 32]
        shared = dtlsproto.x25519(bytes(range(32, 64)), server_pub)
        hs = _extract(derived, shared)
        synth = (bytes([254]) + (32).to_bytes(3, "big")
                 + (0).to_bytes(2, "big") + (0).to_bytes(3, "big")
                 + (32).to_bytes(3, "big")
                 + hashlib.sha256(ch1_raw).digest())
        th_sh = hashlib.sha256(
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
        th_ee = hashlib.sha256(
            synth + hrr_raw + ch2_raw + sh_raw + ee_raw).digest()
        fin_key = _label(s_hs, b"finished", b"")
        expect = hmac.new(fin_key, th_ee, hashlib.sha256).digest()
        ctype, sfin_raw = _open_record_in_test(s_hs, 2, flight[2])
        self.assertEqual(ctype, 22)
        self.assertEqual(sfin_raw[0], 20)          # Finished
        self.assertEqual(sfin_raw[12:], expect)


# ------------------------------------------------------------------
# Core-to-core profile behavior
# ------------------------------------------------------------------

class CoreProfileTest(unittest.TestCase):
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

    def test_greeting_only_after_finished(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            greeting_for=lambda s: b'{"type":"greeting","v":2}')
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
            snapshots.append((len(client.app_messages),
                              client.finished_sent))
        # Until our Finished went out: no application message.
        self.assertTrue(all(n == 0 for n, _s in snapshots))
        out = []
        for dg in back:
            out += server.feed(dg, ADDR, NOW)
        ev = [e[0] for e in server.events]
        self.assertIn("established", ev)
        session = next(iter(server.sessions.values()))
        self.assertTrue(session.greeting_sent)
        for dg in out:
            client.feed(dg, NOW)
        # The greeting is the first application message, and it
        # arrived only on a finished session.
        self.assertIsNotNone(client.greeting)
        first = client.app_messages[0]
        self.assertEqual(json.loads(first)["type"], "greeting")

    def test_resumption_uses_fresh_dhe_and_regreets(self):
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            greeting_for=lambda s: b'{"type":"greeting","v":2}')
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
            greeting_for=lambda s: b"{}")
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


if __name__ == "__main__":
    unittest.main()


# ------------------------------------------------------------------
# The greeting object
# ------------------------------------------------------------------

class GreetingTest(unittest.TestCase):
    def test_none_tier_discloses_nothing(self):
        obj = json.loads(dtls_ext.build_greeting("none"))
        self.assertEqual(obj["type"], "greeting")
        self.assertEqual(obj["transport"], "dtls")
        self.assertEqual(obj["v"], 2)
        self.assertEqual(obj["disclosure"], "none")
        self.assertNotIn("platform", obj)

    def test_family_tier_is_the_default_shape(self):
        obj = json.loads(dtls_ext.build_greeting("family"))
        self.assertEqual(obj["disclosure"], "family")
        self.assertEqual(set(obj["platform"]), {"os_family"})
        self.assertIn(obj["platform"]["os_family"],
                      ("windows", "macos", "linux", "other"))

    def test_standard_tier_adds_release_and_python(self):
        obj = json.loads(dtls_ext.build_greeting("standard"))
        self.assertEqual(
            set(obj["platform"]),
            {"os_family", "os_release", "python_version"})

    def test_full_tier_adds_a_bounded_tools_summary(self):
        obj = json.loads(dtls_ext.build_greeting("full"))
        tools = obj["platform"]["path_tools"]
        self.assertEqual(
            set(tools),
            {"sh", "bash", "powershell", "pwsh", "python3",
             "python", "curl", "git", "tar"})
        self.assertTrue(all(isinstance(v, bool)
                            for v in tools.values()))


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
        # This sandbox blocks sends on UNCONNECTED UDP sockets
        # outright (EPERM), which no real host does; connecting
        # the pipe's socket to its one test peer is the
        # accommodation that lets the real code run here. The
        # production path is the unconnected listener.
        pipe.sock.connect(sock.getsockname())
        for dg in client.start(time.monotonic()):
            sock.send(dg)
        ok = self._drive(pipe, client, sock,
                         lambda: client.greeting is not None)
        self.assertTrue(ok, "no greeting from the pipe")
        return pipe, channel, client, sock

    def test_greeting_and_job_result_flow(self):
        pipe, channel, client, sock = self._session()
        self.assertEqual(client.greeting["disclosure"], "family")
        self.assertEqual(
            set(client.greeting["platform"]), {"os_family"})
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
            lambda: len(client.app_messages) >= 2)
        self.assertTrue(ok, "the result never came back")
        subject, body = ch.parse_envelope(
            client.app_messages[1].decode("utf-8"))
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

    def test_refuses_a_bad_greeting_tier(self):
        proc = self._run({"shared_secret": SECRET,
                          "dtls_greeting": "everything"})
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("dtls_greeting", proc.stderr)

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
            self.assertIsNone(proc.poll())
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
    def _run_cli(self, cfg, tmp, seen_path, script_text, timeout=60):
        script = os.path.join(tmp, "job.sh")
        with open(script, "w", encoding="utf-8") as f:
            f.write(script_text)
        proc = subprocess.Popen(
            [sys.executable,
             os.path.join(REPO, "cloud", "send_dtls.py"),
             "--host", "127.0.0.1",
             "--port", str(cfg["transport_dtls"]["port"]),
             "--secret", SECRET, "--kind", "exec",
             "--script-file", script, "--cleartext",
             "--wait", "45"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            poll_once(cfg, tmp, {}, seen_path)
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        out, err = proc.communicate(timeout=10)
        return proc.returncode, out, err

    def test_exec_job_over_dtls_and_extension_restart(self):
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
