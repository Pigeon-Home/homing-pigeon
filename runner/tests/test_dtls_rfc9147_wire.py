#!/usr/bin/env python3
"""The DTLS record layer against RFC 9147, and the application
framing against the losses and reorderings DTLS permits.

What these tests pin, and why each exists:

- Record number encryption (RFC 9147 Section 4.2.3). The profile
  the Internet-Drafts describe is DTLS 1.3 per RFC 9147, and a
  conforming stack encrypts the record sequence number in every
  protected record's header. Before this family landed, the
  sequence number rode the wire in the clear, so no conforming
  stack could have opened a record this code sealed. The
  opener here is written from the RFC, not from the module.
- The ACK message (RFC 9147 Section 7, Appendix A.1): a
  RecordNumber is a uint64 epoch and a uint64 sequence number.
  The earlier encoding was 2 and 6 octets.
- The anti-replay window (RFC 9147 Section 4.5.1): a record that
  authenticates but was already accepted, or has fallen behind
  the window, is dropped. There was no window before, so a
  replayed application record was appended to the stream.
- The external PSK is derived from the shared secret, not the
  secret itself, so the job-signing key never enters the TLS
  key schedule.
- Application messages survive reordering and loss. DTLS gives
  application data no order and no reliability (RFC 9147
  Section 11); the earlier framing concatenated records in
  arrival order, so a 5 KB message delivered with its records
  reversed was never delivered and every later message on the
  session was lost with it. The probe that found that stands
  in the record under docs/infrastructure-documents/proofs.
"""
import hashlib
import hmac
import os
import random
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.wire import dtlsproto, jobcrypto  # noqa: E402
from runner.tests.test_dtls import (  # noqa: E402
    ADDR, NOW, SECRET, _established_pair, _label,
    _open_record_in_test)


def _rfc9147_open(traffic_secret, epoch, record):
    """One more opener written from the RFC text, kept here so
    this module stands on its own: unmask the sequence number
    with AES-ECB under the "sn" key over the first 16 ciphertext
    octets, rebuild the additional data with the plaintext
    sequence number, decrypt. Returns (content_type, content,
    seq_low)."""
    key = _label(traffic_secret, b"key", b"", 32)
    iv = _label(traffic_secret, b"iv", b"", 12)
    sn_key = _label(traffic_secret, b"sn", b"", 32)
    first = record[0]
    pos = 1
    if first & 0x04:
        pos += 1 + record[pos]
    seq_at = pos
    width = 2 if first & 0x10 else 1
    pos += width
    if first & 0x08:
        length = int.from_bytes(record[pos:pos + 2], "big")
        pos += 2
    else:
        length = len(record) - pos
    body = record[pos:pos + length]
    mask = jobcrypto._aes_encrypt_block(
        body[:16], jobcrypto._aes256_expand(sn_key))
    plain_seq = bytes(a ^ b for a, b in zip(
        record[seq_at:seq_at + width], mask))
    aad = record[:seq_at] + plain_seq + record[seq_at + width:pos]
    seq = int.from_bytes(plain_seq, "big")
    nonce = bytes(a ^ b for a, b in zip(
        iv, ((epoch << 48) | seq).to_bytes(12, "big")))
    plain = jobcrypto.aead_decrypt(key, nonce, body, aad)
    plain = plain.rstrip(b"\x00")
    return plain[-1], plain[:-1], seq


def _app_records(client, server, payload):
    """The datagrams (one record each) of one application
    message from the client, and the server session."""
    records = client.send_app(payload)
    session = next(iter(server.sessions.values()))
    return records, session


class RecordNumberEncryptionTest(unittest.TestCase):
    def test_the_wire_sequence_number_is_masked(self):
        secret = b"\x42" * 48
        sealer = dtlsproto._RecordSealer(secret)
        wire_seqs = set()
        for _ in range(8):
            record = sealer.seal(3, dtlsproto.CT_APPDATA,
                                 b"x" * 40, b"\x01\x02\x03\x04")
            # header: first octet, cid length, 4 cid octets, then
            # the 16-bit sequence field, then the length field
            wire_seqs.add(record[6:8])
        # Eight records sealed under sequence numbers 0..7 carry
        # eight different masked fields, none of them the
        # plaintext number (a 2^-16 chance each, under the AES
        # mask, that one would coincide; eight in a row is not
        # a flake).
        self.assertEqual(len(wire_seqs), 8)
        plain = {n.to_bytes(2, "big") for n in range(8)}
        self.assertNotEqual(wire_seqs, plain)

    def test_a_sealed_record_opens_under_an_rfc_9147_opener(self):
        secret = b"\x24" * 48
        sealer = dtlsproto._RecordSealer(secret)
        for n in range(5):
            record = sealer.seal(3, dtlsproto.CT_APPDATA,
                                 b"payload %d" % n, b"\xaa\xbb\xcc\xdd")
            ctype, content, seq = _rfc9147_open(secret, 3, record)
            self.assertEqual((ctype, content, seq),
                             (dtlsproto.CT_APPDATA,
                              b"payload %d" % n, n))

    def test_the_opener_unmasks_what_the_sealer_masked(self):
        secret = b"\x99" * 48
        tx = dtlsproto._RecordSealer(secret)
        rx = dtlsproto._RecordSealer(secret)
        for n in range(3):
            record = tx.seal(2, dtlsproto.CT_HANDSHAKE, b"hs", None)
            self.assertEqual(rx.open(2, record),
                             (dtlsproto.CT_HANDSHAKE, b"hs", n))

    def test_a_tampered_masked_sequence_fails_authentication(self):
        secret = b"\x77" * 48
        tx = dtlsproto._RecordSealer(secret)
        rx = dtlsproto._RecordSealer(secret)
        record = bytearray(tx.seal(3, dtlsproto.CT_APPDATA, b"q", None))
        record[1] ^= 0x01            # the masked sequence field
        with self.assertRaises(Exception):
            rx.open(3, bytes(record))

    def test_the_sn_key_follows_the_rfc_label(self):
        secret = b"\x13" * 48
        sealer = dtlsproto._RecordSealer(secret)
        self.assertEqual(sealer.sn_key, _label(secret, b"sn", b"", 32))
        self.assertNotEqual(sealer.sn_key, sealer.key)

    def test_a_live_handshake_flight_opens_under_the_rfc_opener(self):
        client, server = _established_pair()
        # The server's NewSessionTicket, sealed in epoch 3 under
        # the server application traffic secret.
        session = next(iter(server.sessions.values()))
        secret = session._send_ap_secret
        records = session.app_send(b"\x00" * 0)  # an empty message
        for record in records:
            ctype, content, seq = _rfc9147_open(secret, 3, record)
            self.assertEqual(ctype, dtlsproto.CT_APPDATA)
            self.assertEqual(content[0], dtlsproto.APP_FLAG_FIRST)


class AckEncodingTest(unittest.TestCase):
    def test_an_ack_carries_uint64_record_numbers(self):
        ep = dtlsproto._Endpoint()
        secret = b"\x55" * 48
        ep.senders[2] = dtlsproto._RecordSealer(secret)
        ep._acks_wanted = [(2, 7), (2, 9)]
        record = ep._send_ack()[0]
        ctype, content, _seq = _rfc9147_open(secret, 2, record)
        self.assertEqual(ctype, dtlsproto.CT_ACK)
        self.assertEqual(len(content), 2 + 2 * 16)
        self.assertEqual(int.from_bytes(content[:2], "big"), 32)
        self.assertEqual(content[2:18],
                         (2).to_bytes(8, "big") + (7).to_bytes(8, "big"))
        self.assertEqual(content[18:34],
                         (2).to_bytes(8, "big") + (9).to_bytes(8, "big"))
        self.assertEqual(dtlsproto._Endpoint.parse_ack(content),
                         [(2, 7), (2, 9)])

    def test_the_old_8_octet_entries_are_not_an_ack(self):
        old = (16).to_bytes(2, "big") + \
            (2).to_bytes(2, "big") + (7).to_bytes(6, "big") + \
            (2).to_bytes(2, "big") + (9).to_bytes(6, "big")
        # 16 octets of body: one well-formed uint64 pair in
        # length, but these are two of the old entries; the
        # parser reads them as one RecordNumber, which is the
        # RFC's reading, and that is exactly why the old
        # encoding could not interoperate.
        parsed = dtlsproto._Endpoint.parse_ack(old)
        self.assertEqual(parsed, [(int.from_bytes(
            (2).to_bytes(2, "big") + (7).to_bytes(6, "big"), "big"),
            int.from_bytes(
            (2).to_bytes(2, "big") + (9).to_bytes(6, "big"), "big"))])
        self.assertIsNone(dtlsproto._Endpoint.parse_ack(
            (8).to_bytes(2, "big") + b"\x00" * 8))
        self.assertIsNone(dtlsproto._Endpoint.parse_ack(b"\x00"))

    def test_a_malformed_ack_does_not_end_retransmission(self):
        ep = dtlsproto._Endpoint()
        ep._flight = [(0, dtlsproto.CT_HANDSHAKE, b"hi")]
        ep._note_ack((8).to_bytes(2, "big") + b"\x00" * 8)
        self.assertIsNotNone(ep._flight)
        ep._note_ack((16).to_bytes(2, "big") + b"\x00" * 16)
        self.assertIsNone(ep._flight)


class ReplayWindowTest(unittest.TestCase):
    def test_a_replayed_record_is_dropped_after_it_authenticates(self):
        secret = b"\x31" * 48
        tx = dtlsproto._RecordSealer(secret)
        rx = dtlsproto._RecordSealer(secret)
        record = tx.seal(3, dtlsproto.CT_APPDATA, b"once", None)
        self.assertEqual(rx.open(3, record)[1], b"once")
        with self.assertRaises(dtlsproto.DtlsReplay):
            rx.open(3, record)
        # A forgery does not touch the window: the next genuine
        # record still opens.
        forged = bytearray(record)
        forged[-1] ^= 0x01
        with self.assertRaises(Exception):
            rx.open(3, bytes(forged))
        self.assertEqual(rx.open(3, tx.seal(
            3, dtlsproto.CT_APPDATA, b"twice", None))[1], b"twice")

    def test_reordered_records_all_open_once(self):
        secret = b"\x32" * 48
        tx = dtlsproto._RecordSealer(secret)
        rx = dtlsproto._RecordSealer(secret)
        records = [tx.seal(3, dtlsproto.CT_APPDATA, bytes([n]), None)
                   for n in range(6)]
        order = [5, 0, 3, 1, 4, 2]
        for n in order:
            self.assertEqual(rx.open(3, records[n])[2], n)
        for n in order:
            with self.assertRaises(dtlsproto.DtlsReplay):
                rx.open(3, records[n])
        for n in range(6):
            self.assertTrue(rx.seen(n))

    def test_a_record_behind_the_window_is_dropped(self):
        secret = b"\x33" * 48
        rx = dtlsproto._RecordSealer(secret)
        rx._accept_seq(dtlsproto.RECORD_REPLAY_WINDOW + 3)
        with self.assertRaisesRegex(dtlsproto.DtlsReplay, "older"):
            rx._accept_seq(0)
        self.assertFalse(rx.seen(0))
        # Just inside the window the sequence number is accepted,
        # once.
        rx._accept_seq(4)
        self.assertTrue(rx.seen(4))
        with self.assertRaisesRegex(dtlsproto.DtlsReplay, "replayed"):
            rx._accept_seq(4)

    def test_a_record_too_old_to_reconstruct_cannot_open(self):
        # The wire carries 16 bits of the sequence number and the
        # receiver reads the closest candidate (RFC 9147 Section
        # 4.2.2), so a record 2^15 or more behind the newest is
        # unreadable whatever the window says: the window is
        # sized to that edge, not past it.
        secret = b"\x35" * 48
        tx = dtlsproto._RecordSealer(secret)
        rx = dtlsproto._RecordSealer(secret)
        early = tx.seal(3, dtlsproto.CT_APPDATA, b"early", None)
        tx.seq = dtlsproto.RECORD_REPLAY_WINDOW + 1
        rx._next_expected = tx.seq
        late = tx.seal(3, dtlsproto.CT_APPDATA, b"late", None)
        self.assertEqual(rx.open(3, late)[1], b"late")
        with self.assertRaises(Exception):
            rx.open(3, early)

    def test_a_record_inside_the_window_still_opens(self):
        secret = b"\x34" * 48
        tx = dtlsproto._RecordSealer(secret)
        rx = dtlsproto._RecordSealer(secret)
        early = tx.seal(3, dtlsproto.CT_APPDATA, b"early", None)
        tx.seq = dtlsproto.RECORD_REPLAY_WINDOW - 1
        rx._next_expected = tx.seq
        late = tx.seal(3, dtlsproto.CT_APPDATA, b"late", None)
        self.assertEqual(rx.open(3, late)[1], b"late")
        self.assertEqual(rx.open(3, early)[1], b"early")

    def test_a_replayed_application_record_is_dropped_by_a_session(self):
        client, server = _established_pair()
        records, session = _app_records(client, server, b"one message")
        self.assertEqual(len(records), 1)
        server.feed(records[0], ADDR, NOW)
        self.assertEqual(session.app_messages, [b"one message"])
        server.feed(records[0], ADDR, NOW)
        self.assertEqual(session.app_messages, [b"one message"])
        self.assertEqual(session.replayed_records, 1)
        # And the client side drops a replayed server record too.
        out = server.send_app(session.session_id, b"from the server")
        client.feed(out[0][1], NOW)
        client.feed(out[0][1], NOW)
        self.assertEqual(client.app_messages, [b"from the server"])
        self.assertEqual(client.replayed_records, 1)


class DerivedPskTest(unittest.TestCase):
    def test_the_psk_is_hkdf_over_the_secret_with_the_profile_label(self):
        prk = hmac.new(b"\x00" * 48, SECRET.encode("utf-8"),
                       hashlib.sha384).digest()
        expect = hmac.new(prk, dtlsproto.PSK_INFO + b"\x01",
                          hashlib.sha384).digest()
        self.assertEqual(dtlsproto.psk_from_secret(SECRET), expect)
        self.assertEqual(len(expect), 48)
        self.assertNotEqual(expect, SECRET.encode("utf-8"))
        self.assertEqual(dtlsproto.psk_from_secret(""), b"")
        self.assertEqual(dtlsproto.psk_from_secret(None), b"")

    def test_both_ends_derive_the_same_psk_and_establish(self):
        client, server = _established_pair()
        session = next(iter(server.sessions.values()))
        self.assertEqual(client._psk, dtlsproto.psk_from_secret(SECRET))
        self.assertTrue(session.established)

    def test_a_peer_offering_the_raw_secret_as_psk_is_refused(self):
        # A client that puts the shared secret's own octets in the
        # TLS key schedule (what an earlier version did) no longer
        # matches the responder's derived PSK: its binder fails.
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        client = dtlsproto.DtlsClientCore(SECRET)
        client._psk = SECRET.encode("utf-8")
        ch1 = client.start(NOW)[0]
        hrr = server.feed(ch1, ADDR, NOW)[0]
        ch2 = client.feed(hrr, NOW)[0]
        flight = server.feed(ch2, ADDR, NOW)
        self.assertEqual(len(flight), 1)
        self.assertTrue(dtlsproto._is_plaintext_record(flight[0]))
        self.assertEqual(flight[0][0], dtlsproto.CT_ALERT)
        self.assertEqual(server.sessions, {})


class ApplicationFramingTest(unittest.TestCase):
    def test_a_message_spans_records_each_with_its_flag(self):
        client, server = _established_pair()
        payload = b"m" * 5000
        records, session = _app_records(client, server, payload)
        self.assertEqual(len(records), 5)
        secret = client._send_ap_secret
        flags = []
        for record in records:
            ctype, content, _seq = _rfc9147_open(secret, 3, record)
            self.assertEqual(ctype, dtlsproto.CT_APPDATA)
            flags.append(content[0])
            self.assertLessEqual(len(content), dtlsproto.RECORD_PLAINTEXT_MAX)
        self.assertEqual(flags, [dtlsproto.APP_FLAG_FIRST]
                         + [dtlsproto.APP_FLAG_MORE] * 4)

    def test_records_delivered_reversed_still_make_the_message(self):
        client, server = _established_pair()
        payload = bytes(range(256)) * 20          # 5120 octets
        records, session = _app_records(client, server, payload)
        for record in reversed(records):
            server.feed(record, ADDR, NOW)
        self.assertEqual(session.app_messages, [payload])
        after, _ = _app_records(client, server, b"after")
        server.feed(after[0], ADDR, NOW)
        self.assertEqual(session.app_messages, [payload, b"after"])

    def test_records_delivered_shuffled_still_make_the_message(self):
        client, server = _established_pair()
        payload = os.urandom(30000)
        records, session = _app_records(client, server, payload)
        self.assertGreater(len(records), 20)
        shuffled = list(records)
        random.Random(7).shuffle(shuffled)
        for record in shuffled:
            server.feed(record, ADDR, NOW)
        self.assertEqual(session.app_messages, [payload])

    def test_a_lost_record_drops_the_message_whole_and_the_next_arrives(self):
        client, server = _established_pair()
        payload = b"l" * 5000
        records, session = _app_records(client, server, payload)
        for record in records[:2] + records[3:]:
            server.feed(record, ADDR, NOW)
        self.assertEqual(session.app_messages, [])
        # No head-of-line blocking: the next message is whole and
        # is delivered while the earlier one still waits for its
        # missing record.
        after, _ = _app_records(client, server, b"after the hole")
        for record in after:
            server.feed(record, ADDR, NOW)
        self.assertEqual(session.app_messages, [b"after the hole"])
        self.assertEqual(len(session._app_pending), 1)
        # Once the missing record has fallen behind the replay
        # window it can never be accepted, so the message is
        # dropped whole, counted, and nothing of it is delivered.
        far = next(iter(session._app_pending)) \
            + dtlsproto.RECORD_REPLAY_WINDOW + 5
        session._app_receive(
            bytes([dtlsproto.APP_FLAG_FIRST]) + (3).to_bytes(4, "big")
            + b"far", far)
        self.assertEqual(session.app_messages,
                         [b"after the hole", b"far"])
        self.assertEqual(session._app_pending, {})
        self.assertEqual(session.app_dropped, 1)

    def test_a_continuation_arriving_before_its_first_record_is_held(self):
        client, server = _established_pair()
        payload = b"c" * 3000
        records, session = _app_records(client, server, payload)
        self.assertEqual(len(records), 3)
        server.feed(records[2], ADDR, NOW)
        server.feed(records[1], ADDR, NOW)
        self.assertEqual(session.app_messages, [])
        self.assertEqual(len(session._app_orphans), 2)
        server.feed(records[0], ADDR, NOW)
        self.assertEqual(session.app_messages, [payload])
        self.assertEqual(session._app_orphans, {})
        self.assertEqual(session._app_held_bytes, 0)

    def test_two_messages_interleaved_both_deliver(self):
        client, server = _established_pair()
        first, session = _app_records(client, server, b"A" * 2500)
        second, _ = _app_records(client, server, b"B" * 2500)
        order = [second[1], first[0], second[2], first[2], second[0],
                 first[1]]
        for record in order:
            server.feed(record, ADDR, NOW)
        self.assertEqual(sorted(session.app_messages),
                         [b"A" * 2500, b"B" * 2500])

    def test_the_client_reassembles_the_servers_message_too(self):
        client, server = _established_pair()
        session = next(iter(server.sessions.values()))
        payload = b"s" * 4000
        out = server.send_app(session.session_id, payload)
        for _addr, record in reversed(out):
            client.feed(record, NOW)
        self.assertEqual(client.app_messages, [payload])

    def test_held_bytes_stay_under_the_bound(self):
        ep = dtlsproto._Endpoint()
        ep._on_app_message = lambda m: None
        huge = dtlsproto.APP_MESSAGE_MAX
        chunk = b"z" * (dtlsproto.RECORD_PLAINTEXT_MAX - 1)
        # Three partial messages, each claiming the maximum, each
        # holding a few records: the bound is on held bytes, not
        # claimed ones, so three small partials are fine.
        for start in (0, 100, 200):
            ep._app_receive(bytes([dtlsproto.APP_FLAG_FIRST])
                            + huge.to_bytes(4, "big") + chunk, start)
            for k in range(1, 3):
                ep._app_receive(bytes([dtlsproto.APP_FLAG_MORE]) + chunk,
                                start + k)
        self.assertEqual(len(ep._app_pending), 3)
        self.assertLessEqual(ep._app_held_bytes,
                             dtlsproto.APP_PENDING_MAX_BYTES)
        # Orphans past the bound are shed oldest first.
        ep._app_held_bytes = dtlsproto.APP_PENDING_MAX_BYTES
        ep._app_receive(bytes([dtlsproto.APP_FLAG_MORE]) + chunk, 900)
        self.assertLessEqual(ep._app_held_bytes,
                             dtlsproto.APP_PENDING_MAX_BYTES)
        self.assertLess(len(ep._app_pending), 3)


if __name__ == "__main__":
    unittest.main()
