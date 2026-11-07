#!/usr/bin/env python3
"""Version 3 carriage: one application message is one datagram.

Every record of a message travels in one transfer, so the
carriage's own reassembly (parts in any order, duplicates
idempotent, a lost part completing nothing) is what carries a
message whole. Before this rule the carriage sent one record
per flight mail: a 5 KB job was 5 mails, and if the mailbox
handed them over reversed, or one of them never arrived, the
message was never delivered and every later message on the
session was lost with it. The probe that measured that stands
in docs/infrastructure-documents/proofs.
"""
import os
import random
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.wire import dtls_mailbox, dtlsproto  # noqa: E402
from runner.wire.dtls_mailbox import (  # noqa: E402
    DtlsMailClient, DtlsMailServer, FlightReassembler, FlightPart,
    encode_flight, parse_message)
from runner.tests.test_dtls_email_v3 import (  # noqa: E402
    NOW, SECRET, SID, _mails_to_raw, _pump_mail, _raw_mail)


def _session():
    server = DtlsMailServer(
        dtlsproto.make_secret_lookup(SECRET),
        platform_payload=b'{"disclosure":"none"}')
    client = DtlsMailClient(SECRET, session_id=SID)
    _pump_mail(client, server)
    assert client.state == "established"
    return client, server


def _deliver(server, mails):
    for raw in _mails_to_raw(mails):
        server.receive_raw(raw, NOW)
    return [m[2] for m in server.drain_app_messages()]


class OneMessageOneDatagramTest(unittest.TestCase):
    def test_a_message_of_several_records_is_one_flight_mail(self):
        client, server = _session()
        payload = b"j" * 5000           # 5 records of 1200 octets
        mails = client.send_app_mails(payload)
        self.assertEqual(len(mails), 1)
        parsed = parse_message(_mails_to_raw(mails)[0])
        self.assertEqual(parsed.kind, "dtls")
        self.assertEqual(len(dtlsproto._split_records(parsed.datagram)),
                         5)
        self.assertEqual(_deliver(server, mails), [payload])

    def test_a_large_message_is_one_transfer_in_many_parts(self):
        client, server = _session()
        payload = os.urandom(100 * 1024)
        mails = client.send_app_mails(payload)
        self.assertGreater(len(mails), 3)
        parts = [parse_message(raw).part for raw in _mails_to_raw(mails)]
        self.assertEqual({p.transfer_id for p in parts}, {parts[0].transfer_id})
        self.assertEqual(sorted(p.index for p in parts),
                         list(range(len(mails))))
        self.assertEqual(_deliver(server, mails), [payload])

    def test_parts_reversed_and_duplicated_still_deliver_once(self):
        client, server = _session()
        payload = os.urandom(70 * 1024)
        mails = client.send_app_mails(payload)
        self.assertGreater(len(mails), 2)
        disordered = list(reversed(mails)) + [mails[1], mails[0]]
        self.assertEqual(_deliver(server, disordered), [payload])
        after = client.send_app_mails(b"after")
        self.assertEqual(_deliver(server, after), [b"after"])

    def test_parts_shuffled_still_deliver(self):
        client, server = _session()
        payload = os.urandom(150 * 1024)
        mails = client.send_app_mails(payload)
        shuffled = list(mails)
        random.Random(11).shuffle(shuffled)
        self.assertEqual(_deliver(server, shuffled), [payload])

    def test_a_lost_part_delivers_nothing_and_the_next_message_arrives(self):
        client, server = _session()
        payload = os.urandom(70 * 1024)
        mails = client.send_app_mails(payload)
        self.assertEqual(_deliver(server, mails[:1] + mails[2:]), [])
        after = client.send_app_mails(b"the next message")
        self.assertEqual(_deliver(server, after), [b"the next message"])
        self.assertEqual(server.reassembler.pending, 1)

    def test_messages_mails_interleaved_both_deliver(self):
        client, server = _session()
        one = os.urandom(50 * 1024)
        two = os.urandom(50 * 1024)
        first = client.send_app_mails(one)
        second = client.send_app_mails(two)
        order = []
        for a, b in zip(first, second):
            order.extend([b, a])
        order.extend(first[len(second):] + second[len(first):])
        got = _deliver(server, order)
        self.assertEqual(sorted(got), sorted([one, two]))

    def test_the_server_answers_in_one_datagram_too(self):
        client, server = _session()
        cid = server.established[SID]
        payload = os.urandom(40 * 1024)
        mails = server.send_app_mails(cid, payload)
        self.assertEqual(
            len({parse_message(raw).part.transfer_id
                 for raw in _mails_to_raw(mails)}), 1)
        for raw in reversed(_mails_to_raw(mails)):
            client.receive_raw(raw, NOW)
        self.assertEqual(client.app_messages, [payload])


class CarriageCeilingTest(unittest.TestCase):
    def test_the_ceiling_covers_a_message_at_the_application_cap(self):
        cap = dtlsproto.APP_MESSAGE_MAX
        slice_max = dtlsproto.RECORD_PLAINTEXT_MAX - 1
        records = -(-(cap + 4) // slice_max)
        # Each record: a 10-octet header (first octet, CID length,
        # 4 CID octets, 2 sequence octets, 2 length octets), the
        # flag octet, the content-type octet and a 16-octet tag.
        overhead = records * (10 + 1 + 1 + 16)
        self.assertLessEqual(cap + 4 + overhead,
                             dtls_mailbox.DEFAULT_MAX_DATAGRAM_BYTES)
        parts = -(-(4 * -(-dtls_mailbox.DEFAULT_MAX_DATAGRAM_BYTES // 3))
                  // dtls_mailbox.DEFAULT_CHUNK_CHARS)
        self.assertLessEqual(parts, dtls_mailbox._MAX_PARTS)

    def test_a_datagram_past_the_ceiling_is_refused_whole(self):
        too_big = b"\x2c" * (dtls_mailbox.DEFAULT_MAX_DATAGRAM_BYTES + 1)
        with self.assertRaises(ValueError):
            encode_flight(too_big, SID)
        part = FlightPart(SID, "0" * 16, 0, 2,
                          dtls_mailbox.DEFAULT_MAX_DATAGRAM_BYTES + 1,
                          "0" * 96, b"x")
        self.assertIsNone(FlightReassembler().offer(part, NOW))


class ReassemblyPendingBoundTest(unittest.TestCase):
    def _part(self, transfer, index, count, chunk, total):
        return FlightPart(SID, transfer, index, count, total,
                          "0" * 96, chunk)

    def test_held_bytes_across_transfers_are_bounded(self):
        reasm = FlightReassembler(max_total_bytes=1000,
                                  max_pending_bytes=1500)
        chunk = b"a" * 400
        # Three transfers of two parts each hold 1,200 octets;
        # the fourth pushes past the bound and the oldest goes.
        for n in range(4):
            reasm.offer(self._part("%016x" % n, 0, 2, chunk, 800), NOW)
        self.assertLessEqual(reasm.pending_bytes, 1500)
        self.assertEqual(reasm.pending, 3)
        self.assertIsNone(reasm.offer(
            self._part("%016x" % 0, 1, 2, chunk, 800), NOW))

    def test_the_default_bound_is_two_datagrams(self):
        reasm = FlightReassembler()
        self.assertEqual(reasm.max_pending_bytes,
                         2 * dtls_mailbox.DEFAULT_MAX_DATAGRAM_BYTES)


class MediaTypeTest(unittest.TestCase):
    def test_the_flight_part_is_a_vendor_tree_type(self):
        self.assertEqual(dtls_mailbox.FLIGHT_CONTENT_TYPE,
                         "application/vnd.homing-pigeon.dtls3")
        msg = dtls_mailbox.build_flight_message(
            {"mailbox_user": "r@example.com"},
            dtls_mailbox.flight_subject(SID),
            "HP-DTLS/3 transfer=0123456789abcdef part=0 parts=1 "
            "bytes=1 sha384=" + "0" * 96 + "\nAA==")
        types = [p.get_content_type() for p in msg.walk()]
        self.assertIn("application/vnd.homing-pigeon.dtls3", types)
        self.assertNotIn("application/hp-dtls3", types)


if __name__ == "__main__":
    unittest.main()
