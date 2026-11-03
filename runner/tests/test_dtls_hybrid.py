"""Tests for the hybrid key exchange: X25519MLKEM768
(RFC 10024, group 4588) in the DTLS engine.

The layout under test, verified first-hand against the
RFC text:

- Client share (section 4.1): the ML-KEM-768 encapsulation
  key (1184 octets) followed by the X25519 share (32) --
  1216 octets, the reverse of the group name's order.
- Server share (section 4.2): the ML-KEM ciphertext (1088)
  followed by the X25519 share -- 1120 octets.
- Shared secret (section 4.3): the ML-KEM secret followed
  by the X25519 secret -- 64 octets into the same key
  schedule the X25519 secret feeds today.

Profile discipline: the group is a profile option on the
engine cores. The version 1 profile (the default) neither
offers nor selects it, and its wire is unchanged; the
version 3 carriage profile (DtlsMailClient/DtlsMailServer)
enables it. The ML-KEM half is pinned separately, against
the NIST ACVP vectors, in test_mlkem.py.
"""

import os
import sys
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.wire import dtls_mailbox, dtlsproto, mlkem  # noqa: E402
from runner.wire.dtls_mailbox import (  # noqa: E402
    DtlsMailClient, DtlsMailServer, encode_flight, parse_message)
from runner.tests.test_dtls import SECRET, _ch_exts, _pump  # noqa: E402
from runner.tests.test_dtls_email_v3 import (  # noqa: E402
    _mails_to_raw, _pump_mail, _raw_mail)

ADDR = ("127.0.0.1", 50001)
NOW = 1000.0
SID = "hybrid-session-1"
HYBRID = dtlsproto.GROUP_X25519MLKEM768


def _pair(client_hybrid, server_hybrid):
    server = dtlsproto.DtlsServerCore(
        secret_lookup=dtlsproto.make_secret_lookup(SECRET),
        hybrid=server_hybrid)
    client = dtlsproto.DtlsClientCore(SECRET, hybrid=client_hybrid)
    _pump(client, server, addr=ADDR, now=NOW)
    return client, server


def _only_session(server):
    sessions = list(server.sessions.values())
    assert len(sessions) == 1
    return sessions[0]


class WireLayoutTest(unittest.TestCase):
    def test_hybrid_client_hello_layout(self):
        client = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
        datagram = client.start(NOW)[0]
        _raw, exts = _ch_exts(datagram)
        groups = exts[dtlsproto.EXT_SUPPORTED_GROUPS]
        self.assertEqual(
            [int.from_bytes(groups[i:i + 2], "big")
             for i in range(2, len(groups), 2)],
            [HYBRID, dtlsproto.GROUP_X25519])
        entries = dtlsproto._key_share_entries(
            exts[dtlsproto.EXT_KEY_SHARE])
        self.assertEqual([g for g, _k in entries],
                         [HYBRID, dtlsproto.GROUP_X25519])
        hyb, plain = entries[0][1], entries[1][1]
        self.assertEqual(
            len(hyb), dtlsproto.HYBRID_CLIENT_SHARE_BYTES)
        self.assertEqual(len(plain), 32)
        # The hybrid share's first 1184 octets are a real
        # ML-KEM-768 encapsulation key (FIPS 203 check), and
        # its last 32 are the client's hybrid X25519 share.
        self.assertTrue(mlkem.encapsulation_key_check(hyb[:1184]))
        self.assertEqual(
            hyb[1184:], dtlsproto.x25519_public(client._eph_hyb))
        self.assertEqual(
            plain, dtlsproto.x25519_public(client._eph))

    def test_version1_client_hello_is_unchanged(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        datagram = client.start(NOW)[0]
        _raw, exts = _ch_exts(datagram)
        self.assertEqual(
            exts[dtlsproto.EXT_SUPPORTED_GROUPS],
            b"\x00\x02" + dtlsproto.GROUP_X25519.to_bytes(2, "big"))
        entries = dtlsproto._key_share_entries(
            exts[dtlsproto.EXT_KEY_SHARE])
        self.assertEqual(entries, [(
            dtlsproto.GROUP_X25519,
            dtlsproto.x25519_public(client._eph))])
        self.assertFalse(client.hybrid_enabled)


class SecretOrderTest(unittest.TestCase):
    """RFC 10024 section 4.3's concatenation order, pinned
    at both ends against the primitives directly."""

    def test_client_hybrid_shared_order(self):
        ek, dk = mlkem.keygen(rng=lambda n: b"\x21" * n)
        server_x_priv = b"\x22" * 32
        secret, ct = mlkem.encaps(ek, rng=lambda n: b"\x23" * n)
        client = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
        client._mlkem_dk = dk
        client._eph_hyb = b"\x24" * 32
        share = ct + dtlsproto.x25519_public(server_x_priv)
        got = client._hybrid_shared(share)
        want = secret + dtlsproto._ecdh(client._eph_hyb,
                                        share[mlkem.CT_BYTES:])
        self.assertEqual(got, want)
        self.assertEqual(len(got), dtlsproto.HYBRID_SECRET_BYTES)
        self.assertEqual(got[:32], secret)

    def test_server_hybrid_answer_order(self):
        ek, dk = mlkem.keygen(rng=lambda n: b"\x31" * n)
        client_x_priv = b"\x32" * 32
        client_share = ek + dtlsproto.x25519_public(client_x_priv)
        core = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            hybrid=True, rng=lambda n: b"\x33" * n)
        session = dtlsproto._ServerSession(core, ADDR)
        share_value, shared = session._hybrid_answer(client_share)
        group = int.from_bytes(share_value[0:2], "big")
        klen = int.from_bytes(share_value[2:4], "big")
        key = share_value[4:4 + klen]
        self.assertEqual(group, HYBRID)
        self.assertEqual(
            klen, dtlsproto.HYBRID_SERVER_SHARE_BYTES)
        mlkem_secret = mlkem.decaps(dk, key[:mlkem.CT_BYTES])
        x_secret = dtlsproto._ecdh(client_x_priv,
                                   key[mlkem.CT_BYTES:])
        self.assertEqual(shared, mlkem_secret + x_secret)


class NegotiationTest(unittest.TestCase):
    def test_hybrid_peers_negotiate_the_hybrid(self):
        client, server = _pair(True, True)
        self.assertEqual(client.state, "established")
        self.assertEqual(client.negotiated_group, HYBRID)
        session = _only_session(server)
        self.assertEqual(session.negotiated_group, HYBRID)
        # Application data crosses on the hybrid session.
        out = client.send_app(b"ping")
        for dg in out:
            server.feed(dg, ADDR, NOW)
        events = [e for e in server.events if e[0] == "app"]
        self.assertEqual(events[0][2], b"ping")

    def test_hybrid_client_v1_server_selects_x25519(self):
        # A hybrid share offered to a version 1 profile
        # server is not selected; the X25519 share is, and
        # the handshake is an ordinary version 1 handshake.
        client, server = _pair(True, False)
        self.assertEqual(client.state, "established")
        self.assertEqual(client.negotiated_group,
                         dtlsproto.GROUP_X25519)
        self.assertEqual(_only_session(server).negotiated_group,
                         dtlsproto.GROUP_X25519)

    def test_v1_client_hybrid_server_selects_x25519(self):
        client, server = _pair(False, True)
        self.assertEqual(client.state, "established")
        self.assertEqual(client.negotiated_group,
                         dtlsproto.GROUP_X25519)
        self.assertEqual(_only_session(server).negotiated_group,
                         dtlsproto.GROUP_X25519)

    def test_hybrid_resumption_stays_hybrid(self):
        client, server = _pair(True, True)
        self.assertIsNotNone(client.ticket)
        resumed = dtlsproto.DtlsClientCore(
            SECRET, ticket=client.ticket, hybrid=True)
        _pump(resumed, server, addr=ADDR, now=NOW)
        self.assertEqual(resumed.state, "established")
        self.assertEqual(resumed.negotiated_group, HYBRID)
        established = [e for e in server.events
                       if e[0] == "established"]
        self.assertTrue(established[-1][2]["resumed"])


class FailClosedTest(unittest.TestCase):
    def _begin(self, core, share_value):
        session = dtlsproto._ServerSession(core, ADDR)
        exts = {
            dtlsproto.EXT_PSK_MODES: bytes(
                [1, dtlsproto.PSK_MODE_DHE_KE]),
            dtlsproto.EXT_KEY_SHARE: share_value,
        }
        out = session.begin(
            b"x" * 80,
            {"suites": [dtlsproto.SUITE_AES256], "exts": exts},
            b"\x11" * dtlsproto.HASH_LEN, b"hrr", NOW)
        return session, out

    def _share_value(self, entries):
        body = b"".join(
            g.to_bytes(2, "big") + len(k).to_bytes(2, "big") + k
            for g, k in entries)
        return len(body).to_bytes(2, "big") + body

    def test_truncated_hybrid_share_is_refused(self):
        core = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            hybrid=True)
        ek, _dk = mlkem.keygen(rng=lambda n: b"\x41" * n)
        share = (ek + b"\x42" * 32)[:-1]     # 1215 octets
        _s, out = self._begin(
            core, self._share_value([(HYBRID, share)]))
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        self.assertEqual(out[0][14],
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)

    def test_hybrid_only_hello_to_v1_server_is_refused(self):
        # A hello whose only share is the hybrid, to a server
        # without the profile option: nothing to select.
        core = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        ek, _dk = mlkem.keygen(rng=lambda n: b"\x43" * n)
        share = ek + b"\x44" * 32
        _s, out = self._begin(
            core, self._share_value([(HYBRID, share)]))
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        self.assertEqual(out[0][14],
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)

    def test_bad_encapsulation_key_fails_the_handshake(self):
        # A client whose (binder-valid) hello carries an ek
        # that fails the FIPS 203 modulus check: the server
        # answers illegal_parameter and keeps no session.
        real_ek, dk = mlkem.keygen(rng=lambda n: b"\x45" * n)
        bad_ek = b"\xff" * (384 * mlkem.K) + real_ek[384 * mlkem.K:]
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            hybrid=True)
        client = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
        with mock.patch.object(
                dtlsproto.mlkem, "keygen",
                return_value=(bad_ek, dk)):
            hello = client.start(NOW)[0]
            hrr = server.feed(hello, ADDR, NOW)[0]
            second = client.feed(hrr, NOW)[0]
            out = server.feed(second, ADDR, NOW)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], dtlsproto.CT_ALERT)
        self.assertEqual(out[0][14],
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)
        self.assertEqual(server.sessions, {})
        self.assertNotEqual(client.state, "established")

    def test_swapped_server_share_halves_fail_closed(self):
        client = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET),
            hybrid=True)
        hello = client.start(NOW)[0]
        hrr = server.feed(hello, ADDR, NOW)[0]
        second = client.feed(hrr, NOW)[0]
        flight = server.feed(second, ADDR, NOW)
        sh = bytearray(flight[0])
        # Swap the first 32 octets of the ML-KEM ciphertext
        # with the trailing X25519 share, in place: the share
        # keeps its size and the transcript its shape, but
        # neither half is what the other side derived from.
        _raw, exts = _ch_exts(bytes(sh))
        share = exts[dtlsproto.EXT_KEY_SHARE]
        # Locate the share value inside the record: it is the
        # extension's value, found by search from the record
        # body onward (the value is 1120 distinctive octets).
        at = bytes(sh).find(share[4:], 13)
        self.assertGreater(at, 0)
        head = bytes(sh[at:at + 32])
        tail = bytes(sh[at + 1088:at + 1120])
        sh[at:at + 32] = tail
        sh[at + 1088:at + 1120] = head
        for dg in [bytes(sh)] + flight[1:]:
            client.feed(dg, NOW)
        # Fail closed, at the record layer: the client's
        # transcript and shared secret no longer match the
        # server's, so the protected flight does not decrypt
        # and the handshake never completes.
        self.assertNotEqual(client.state, "established")
        self.assertFalse(client.finished_received)

    def test_short_and_unoffered_hybrid_server_shares_raise(self):
        client = dtlsproto.DtlsClientCore(SECRET, hybrid=True)
        client._mlkem_dk = mlkem.keygen(
            rng=lambda n: b"\x46" * n)[1]
        client._eph_hyb = b"\x47" * 32
        with self.assertRaises(dtlsproto.DtlsError):
            client._hybrid_shared(b"\x00" * 100)
        plain = dtlsproto.DtlsClientCore(SECRET)
        with self.assertRaises(dtlsproto.DtlsError):
            plain._hybrid_shared(b"\x00" * 1120)


class CarriageTest(unittest.TestCase):
    def test_carriage_enables_the_hybrid_by_default(self):
        server = DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET))
        client = DtlsMailClient(SECRET, session_id=SID)
        self.assertTrue(server.core.hybrid_enabled)
        self.assertTrue(client.core.hybrid_enabled)
        _pump_mail(client, server)
        self.assertEqual(client.state, "established")
        self.assertEqual(client.core.negotiated_group, HYBRID)
        sessions = list(server.core.sessions.values())
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].negotiated_group, HYBRID)

    def test_carriage_handshake_at_small_chunk_sizes(self):
        # The hybrid flights are ~1.2 KB; segmented at the
        # carriage's smallest chunk shapes they still
        # reassemble and the handshake still completes, in
        # both directions.
        server = DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET))
        client = DtlsMailClient(SECRET, session_id=SID)
        pending = client.start_mails(NOW)
        for _ in range(16):
            if not pending:
                break
            responses = []
            for subject, body in pending:
                dg = parse_message(
                    _raw_mail(subject, body)).datagram
                self.assertIsNotNone(dg)
                for raw in _mails_to_raw(encode_flight(
                        dg, SID, max_chunk_chars=96)):
                    responses.extend(server.receive_raw(raw, NOW))
            pending = []
            for subject, body in responses:
                dg = parse_message(
                    _raw_mail(subject, body)).datagram
                self.assertIsNotNone(dg)
                for raw in _mails_to_raw(encode_flight(
                        dg, SID, max_chunk_chars=96)):
                    pending.extend(client.receive_raw(raw, NOW))
        self.assertEqual(client.state, "established")
        self.assertEqual(client.core.negotiated_group, HYBRID)


if __name__ == "__main__":
    unittest.main()
