#!/usr/bin/env python3
"""Version 3: DTLS via email, through the production mail shape.

The carriage under test is runner/wire/dtls_mailbox.py grown past
the local harness, plus the email transport extension's routing:
a DTLS mail is recognized by the mail parser, fed only to the DTLS
server core, and application data from an established session is
delivered to the runner core as an ordinary envelope, so the job
acceptance gate (handle_mail, through process_transport_message
and the channel) decides whether anything runs. Results return
inside the same session.

The mailboxes here are the in-process LocalMailbox the harness
already used: it speaks the UID commands fetch_job_mails calls,
and the email extension polls it exactly the way it polls a real
IMAP connection.
"""
import hashlib
import os
import string
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.runner import sign_payload  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.email import (  # noqa: E402
    __main__ as email_ext)
from runner.wire import dtls_mailbox, dtlsproto, jobcrypto  # noqa: E402
from runner.wire import transports  # noqa: E402
from runner.wire.dtls_mailbox import (  # noqa: E402
    Deposit, DtlsMailClient, DtlsMailServer, FlightReassembler,
    LocalMailbox, encode_flight, flight_subject, parse_message)
from runner.tests.test_dtls import (  # noqa: E402
    _ch_exts, _ext_value_offset)

SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)
WRONG = (
    "ffffffffffffffff"
    "ffffffffffffffff"
    "ffffffffffffffff"
    "ffffffffffffffff"
)
NOW = 1_700_000_000.0
CFG = {"mailbox_user": "runner@example.com"}
SID = "v3-session-1"


def _raw_mail(subject, body, sender="si@example.com"):
    msg = EmailMessage()
    try:
        msg["Subject"] = subject
    except ValueError:
        # A subject carrying line breaks cannot be set as a
        # header value; that is exactly the shape the fuzz
        # corpus feeds the parser, so build the raw message
        # by hand and let the breaks land where they land.
        head = ("Subject: " + subject + "\nFrom: " + sender
                + "\nTo: runner@example.com\n"
                + "Content-Type: text/plain; charset=utf-8\n\n")
        return (head + body).encode("utf-8", "replace")
    msg["From"] = sender
    msg["To"] = "runner@example.com"
    msg.set_content(body)
    return msg.as_bytes()


def _mails_to_raw(mails):
    return [_raw_mail(subject, body) for subject, body in mails]


def _pump_mail(client, server, rounds=12):
    """Drive a client and a DtlsMailServer with mail tuples only."""
    outgoing = client.start_mails(NOW)
    for _ in range(rounds):
        if not outgoing:
            break
        responses = []
        for raw in _mails_to_raw(outgoing):
            responses.extend(server.receive_raw(raw, NOW))
        outgoing = []
        for raw in _mails_to_raw(responses):
            outgoing.extend(client.receive_raw(raw, NOW))
    return outgoing


def _pump_batches(client, server, outgoing, rounds=12):
    """The _pump_mail loop, starting from a batch the caller
    already holds (a retransmission, a recovered flight)."""
    for _ in range(rounds):
        if not outgoing:
            break
        responses = []
        for raw in _mails_to_raw(outgoing):
            responses.extend(server.receive_raw(raw, NOW))
        outgoing = []
        for raw in _mails_to_raw(responses):
            outgoing.extend(client.receive_raw(raw, NOW))
    return outgoing


def _job_envelope(job_id, encrypt=True, kind="ping", **extra):
    job = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "kind": kind,
    }
    job.update(extra)
    body = sign_payload(job, SECRET)
    if encrypt:
        body = jobcrypto.encrypt_body(
            body, SECRET, job_id=job_id, key_id="", sign=sign_payload)
    return ("[HOMING-PIGEON] job " + job_id + "\n\n" + body).encode(
        "utf-8")


class ParserRoutingTest(unittest.TestCase):
    def test_a_v3_client_hello_mail_is_an_initialization(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        datagram = client.start(NOW)[0]
        mails = encode_flight(datagram, SID)
        self.assertEqual(len(mails), 1)
        subject, body = mails[0]
        self.assertEqual(subject, flight_subject(SID))
        parsed = parse_message(_raw_mail(subject, body))
        self.assertEqual(parsed.kind, "dtls-init")
        self.assertEqual(parsed.session_id, SID)
        self.assertEqual(parsed.datagram, datagram)

    def test_a_protected_record_mail_is_dtls_not_initialization(self):
        server = DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')
        client = DtlsMailClient(SECRET, session_id=SID)
        _pump_mail(client, server)
        self.assertEqual(client.state, "established")
        record_mails = client.send_app_mails(b"ping")
        parsed = parse_message(_mails_to_raw(record_mails)[0])
        self.assertEqual(parsed.kind, "dtls")
        self.assertEqual(parsed.session_id, SID)
        self.assertIsNotNone(parsed.datagram)

    def test_an_ordinary_job_mail_is_a_job(self):
        raw = _raw_mail("[HOMING-PIGEON] job abc-1", "signed-body")
        parsed = parse_message(raw)
        self.assertEqual(parsed.kind, "job")

    def test_an_ordinary_result_mail_is_not_dtls(self):
        raw = _raw_mail("[HOMING-PIGEON] result abc-1", "signed-body")
        parsed = parse_message(raw)
        self.assertEqual(parsed.kind, "other")

    def test_a_v3_subject_with_a_bad_body_fails_closed(self):
        raw = _raw_mail(flight_subject(SID), "not a flight body!")
        parsed = parse_message(raw)
        self.assertEqual(parsed.kind, "dtls-invalid")
        self.assertIsNone(parsed.datagram)

    def test_a_v3_subject_with_garbage_datagram_fails_closed(self):
        import base64
        body = (
            "HP-DTLS/3 transfer=0123456789abcdef part=0 parts=1 "
            "bytes=4 sha384=" + hashlib.sha384(b"junk").hexdigest()
            + "\n" + base64.b64encode(b"junk").decode("ascii"))
        parsed = parse_message(_raw_mail(flight_subject(SID), body))
        self.assertEqual(parsed.kind, "dtls-invalid")

    def test_the_legacy_flight_shape_still_parses(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        datagram = client.start(NOW)[0]
        import base64
        raw = _raw_mail(
            dtls_mailbox.FLIGHT_SUBJECT,
            base64.b64encode(datagram).decode("ascii"))
        self.assertEqual(
            dtls_mailbox.classify(raw), ("flight", datagram))
        parsed = parse_message(raw)
        self.assertIn(parsed.kind, ("dtls", "dtls-init"))
        self.assertEqual(parsed.datagram, datagram)

    def test_a_bad_subject_session_id_fails_closed(self):
        raw = _raw_mail("[HOMING-PIGEON] dtls ../evil", "AAAA")
        parsed = parse_message(raw)
        self.assertEqual(parsed.kind, "dtls-invalid")


class SegmentationTest(unittest.TestCase):
    def test_parts_reassemble_out_of_order_with_duplicates(self):
        datagram = bytes(range(256)) * 3
        mails = encode_flight(
            datagram, SID, transfer_id="0123456789abcdef",
            max_chunk_chars=64)
        self.assertGreater(len(mails), 2)
        parts = []
        for subject, body in mails:
            parsed = parse_message(_raw_mail(subject, body))
            self.assertEqual(parsed.kind, "dtls-part")
            parts.append(parsed.part)
        reasm = FlightReassembler()
        out = None
        for part in reversed(parts):
            got = reasm.offer(part, NOW)
            if got is not None:
                out = got
            else:
                # A duplicate part is idempotent, never an error,
                # and never completes the transfer a second time.
                self.assertIsNone(reasm.offer(part, NOW))
        self.assertEqual(out, datagram)

    def test_a_tampered_part_never_reassembles(self):
        datagram = b"x" * 200
        mails = encode_flight(
            datagram, SID, transfer_id="fedcba9876543210",
            max_chunk_chars=64)
        parts = [parse_message(_raw_mail(s, b)).part
                 for s, b in mails]
        first = parts[0]
        chunk = bytearray(first.chunk)
        chunk[0] ^= 0x01
        parts[0] = first._replace(chunk=bytes(chunk))
        reasm = FlightReassembler()
        out = None
        for part in parts:
            out = reasm.offer(part, NOW) or out
        self.assertIsNone(out)

    def test_reassembly_state_expires(self):
        datagram = b"y" * 200
        mails = encode_flight(
            datagram, SID, transfer_id="aaaaaaaaaaaaaaaa",
            max_chunk_chars=64)
        parts = [parse_message(_raw_mail(s, b)).part
                 for s, b in mails]
        reasm = FlightReassembler(ttl_sec=10)
        self.assertIsNone(reasm.offer(parts[0], NOW))
        out = None
        for part in parts[1:]:
            out = reasm.offer(part, NOW + 11) or out
        self.assertIsNone(out)
        self.assertEqual(reasm.pending, 1)


class MailSessionTest(unittest.TestCase):
    def _server(self):
        return DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')

    def test_handshake_platform_and_a_ping(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        _pump_mail(client, server)
        self.assertEqual(client.state, "established")
        self.assertEqual(client.greeting, {"disclosure": "none"})
        sessions = [s for s in server.core.sessions.values()
                    if s.established]
        self.assertEqual(len(sessions), 1)
        for raw in _mails_to_raw(client.send_app_mails(b"ping")):
            self.assertEqual(server.receive_raw(raw, NOW), [])
        apps = server.drain_app_messages()
        self.assertEqual([a[2] for a in apps], [b"ping"])
        self.assertEqual(apps[0][0], SID)

    def test_a_wrong_secret_handshake_never_establishes(self):
        server = self._server()
        client = DtlsMailClient(WRONG, session_id=SID)
        _pump_mail(client, server)
        self.assertNotEqual(client.state, "established")
        self.assertFalse(
            any(s.established for s in server.core.sessions.values()))
        self.assertEqual(server.drain_app_messages(), [])

    def test_a_replayed_initialization_mail_is_suppressed(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        raw = _mails_to_raw(client.start_mails(NOW))[0]
        first = server.receive_raw(raw, NOW)
        self.assertTrue(first)
        self.assertEqual(server.receive_raw(raw, NOW), [])

    def test_a_replayed_app_record_mail_is_suppressed(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        _pump_mail(client, server)
        raw = _mails_to_raw(client.send_app_mails(b"ping"))[0]
        server.receive_raw(raw, NOW)
        self.assertEqual(server.receive_raw(raw, NOW), [])
        self.assertEqual(
            [a[2] for a in server.drain_app_messages()], [b"ping"])

    def test_a_tampered_server_flight_is_refused(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        responses = []
        for raw in _mails_to_raw(client.start_mails(NOW)):
            responses.extend(server.receive_raw(raw, NOW))
        # The first server mail is the HelloRetryRequest; answer it,
        # then tamper with the real server flight.
        follow = []
        for raw in _mails_to_raw(responses):
            follow.extend(client.receive_raw(raw, NOW))
        flight = []
        for raw in _mails_to_raw(follow):
            flight.extend(server.receive_raw(raw, NOW))
        self.assertTrue(flight)
        subject, body = flight[0]
        parsed = parse_message(_raw_mail(subject, body))
        tampered = bytearray(parsed.datagram)
        tampered[-1] ^= 0x01
        bad = encode_flight(bytes(tampered), SID,
                            transfer_id="1111111111111111")
        for raw in _mails_to_raw(bad):
            client.receive_raw(raw, NOW)
        self.assertNotEqual(client.state, "established")

    def test_a_record_from_one_session_is_not_the_others(self):
        server = self._server()
        alice = DtlsMailClient(SECRET, session_id="session-a")
        bob = DtlsMailClient(SECRET, session_id="session-b")
        _pump_mail(alice, server)
        _pump_mail(bob, server)
        self.assertEqual(alice.state, "established")
        self.assertEqual(bob.state, "established")
        record = alice.send_app_mails(b"for alice only")
        self.assertEqual(len(record), 1)
        subject, body = record[0]
        relabeled = _raw_mail(flight_subject("session-b"), body)
        self.assertEqual(server.receive_raw(relabeled, NOW), [])
        self.assertEqual(server.drain_app_messages(), [])
        for raw in _mails_to_raw(record):
            server.receive_raw(raw, NOW)
        self.assertEqual(
            [a[2] for a in server.drain_app_messages()],
            [b"for alice only"])

    def test_a_job_envelope_in_dtls_clothing_goes_nowhere(self):
        # A downgrade attempt: a job object carried as if it
        # were a flight, without any session. It is not a DTLS
        # record, so it is dropped as DTLS input -- and it is
        # never reinterpreted as a job on this path either.
        import base64
        server = self._server()
        envelope = _job_envelope("sneak-1")
        for raw in _mails_to_raw(encode_flight(envelope, SID)):
            self.assertEqual(server.receive_raw(raw, NOW), [])
        legacy = _raw_mail(
            dtls_mailbox.FLIGHT_SUBJECT,
            base64.b64encode(envelope).decode("ascii"))
        self.assertEqual(server.receive_raw(legacy, NOW), [])
        self.assertFalse(server.core.sessions)
        self.assertEqual(server.drain_app_messages(), [])

    def test_the_client_retransmits_an_unanswered_flight(self):
        client = DtlsMailClient(SECRET, session_id=SID)
        first = client.start_mails(NOW)
        self.assertTrue(first)
        again = client.tick_mails(NOW + 2.0)
        self.assertTrue(again)
        self.assertTrue(
            all(s == flight_subject(SID) for s, _b in again))


class ResumptionOverMailTest(unittest.TestCase):
    """Resumption over the mail carriage: the profile's rule --
    a fresh ephemeral share on every handshake, psk_ke never
    offered and never accepted -- must hold over mail exactly
    as it holds on the datagram binding (the engine's own
    resumption test in test_dtls.py is the shape mirrored
    here). The mail session-id of a resumed session is a new
    carriage label; what resumes is the DTLS session, by its
    ticket."""

    def _server(self, calls):
        def disclose(session):
            calls.append(session.resumed)
            return b'{"disclosure":"none"}'
        return DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET), platform_for=disclose)

    def _pump_recording(self, client, server, now=NOW):
        """_pump_mail that also returns every (kind, datagram)
        the client sent, in order."""
        sent = []

        def harvest(mails):
            for raw in _mails_to_raw(mails):
                parsed = parse_message(raw)
                if parsed.datagram is not None:
                    sent.append((parsed.kind, parsed.datagram))

        outgoing = client.start_mails(now)
        for _ in range(12):
            if not outgoing:
                break
            harvest(outgoing)
            responses = []
            for raw in _mails_to_raw(outgoing):
                responses.extend(server.receive_raw(raw, now))
            outgoing = []
            for raw in _mails_to_raw(responses):
                outgoing.extend(client.receive_raw(raw, now))
        return sent

    @staticmethod
    def _cookied_hello(sent):
        hellos = [d for kind, d in sent if kind == "dtls-init"]
        return hellos[-1]

    def _established_client(self, server, session_id=SID):
        client = DtlsMailClient(SECRET, session_id=session_id)
        self._pump_recording(client, server)
        self.assertEqual(client.state, "established")
        self.assertIsNotNone(client.core.ticket)
        return client

    def test_resumption_over_mail_fresh_share_and_redisclosure(self):
        calls = []
        server = self._server(calls)
        first = DtlsMailClient(SECRET, session_id="v3-resume-1")
        sent1 = self._pump_recording(first, server)
        self.assertEqual(first.state, "established")
        self.assertIsNotNone(first.core.ticket)
        resumed = DtlsMailClient(
            SECRET, session_id="v3-resume-2",
            ticket=first.core.ticket)
        sent2 = self._pump_recording(resumed, server)
        self.assertEqual(resumed.state, "established")
        _raw, exts1 = _ch_exts(self._cookied_hello(sent1))
        _raw, exts2 = _ch_exts(self._cookied_hello(sent2))
        # The resumed offer carries psk_dhe_ke and only
        # psk_dhe_ke, exactly as a fresh offer does.
        self.assertEqual(exts2[dtlsproto.EXT_PSK_MODES],
                         bytes([1, dtlsproto.PSK_MODE_DHE_KE]))
        # A fresh ephemeral share rides the resumed handshake:
        # the share is not the first handshake's share.
        self.assertNotEqual(exts1[dtlsproto.EXT_KEY_SHARE],
                            exts2[dtlsproto.EXT_KEY_SHARE])
        # The server saw one fresh session and one resumed
        # session, and re-disclosed the platform payload on
        # the resumed one.
        self.assertEqual(calls, [False, True])
        self.assertEqual(resumed.greeting, {"disclosure": "none"})
        self.assertEqual(resumed.core.app_messages, [])
        # Application data crosses on the resumed session.
        for raw in _mails_to_raw(resumed.send_app_mails(
                b"ping after resume")):
            server.receive_raw(raw, NOW)
        apps = server.drain_app_messages()
        self.assertEqual([a[2] for a in apps], [b"ping after resume"])
        self.assertEqual(apps[0][0], "v3-resume-2")

    def test_a_ticket_resumes_only_once_over_mail(self):
        calls = []
        server = self._server(calls)
        first = self._established_client(server, "v3-once-1")
        ticket = first.core.ticket
        second = DtlsMailClient(
            SECRET, session_id="v3-once-2", ticket=ticket)
        self._pump_recording(second, server)
        self.assertEqual(second.state, "established")
        self.assertEqual(calls, [False, True])
        # The ticket was consumed by the first resumption:
        # a third client holding the same pair is refused.
        third = DtlsMailClient(
            SECRET, session_id="v3-once-3", ticket=ticket)
        self._pump_recording(third, server)
        self.assertNotEqual(third.state, "established")
        self.assertEqual(calls, [False, True])
        established = [s for s in server.core.sessions.values()
                       if s.established]
        self.assertEqual(len(established), 2)

    def test_a_ticket_with_a_corrupted_psk_is_refused_over_mail(self):
        calls = []
        server = self._server(calls)
        first = self._established_client(server, "v3-corrupt-1")
        identity, psk = first.core.ticket
        bad_psk = bytes([psk[0] ^ 0x01]) + psk[1:]
        client = DtlsMailClient(
            SECRET, session_id="v3-corrupt-2",
            ticket=(identity, bad_psk))
        self._pump_recording(client, server)
        self.assertNotEqual(client.state, "established")
        self.assertEqual(calls, [False])
        self.assertEqual(server.drain_app_messages(), [])

    def test_an_expired_ticket_is_refused_over_mail(self):
        calls = []
        server = self._server(calls)
        first = self._established_client(server, "v3-stale-1")
        later = NOW + dtlsproto.TICKET_LIFETIME + 100
        client = DtlsMailClient(
            SECRET, session_id="v3-stale-2",
            ticket=first.core.ticket)
        self._pump_recording(client, server, now=later)
        self.assertNotEqual(client.state, "established")
        self.assertEqual(calls, [False])

    def test_psk_ke_only_offer_over_mail_is_refused(self):
        calls = []
        server = self._server(calls)
        client = DtlsMailClient(SECRET, session_id=SID)
        responses = []
        for raw in _mails_to_raw(client.start_mails(NOW)):
            responses.extend(server.receive_raw(raw, NOW))
        follow = []
        for raw in _mails_to_raw(responses):
            follow.extend(client.receive_raw(raw, NOW))
        self.assertTrue(follow)
        parsed = parse_message(_mails_to_raw(follow)[0])
        ch2 = bytearray(parsed.datagram)
        # Rewrite the modes extension: [len=1, psk_ke]. The
        # modes check runs before the binder check, so the
        # now stale binder does not mask the refusal reason --
        # the same surgery as the datagram test.
        at = _ext_value_offset(bytes(ch2), dtlsproto.EXT_PSK_MODES)
        ch2[at + 1] = dtlsproto.PSK_MODE_KE
        bad = encode_flight(bytes(ch2), SID,
                            transfer_id="2222222222222222")
        out = []
        for raw in _mails_to_raw(bad):
            out.extend(server.receive_raw(raw, NOW))
        self.assertTrue(out)
        alert = parse_message(_mails_to_raw(out)[0])
        self.assertEqual(alert.kind, "dtls")
        self.assertEqual(alert.datagram[0], 21)       # alert record
        self.assertEqual(alert.datagram[13], 2)      # fatal
        self.assertEqual(alert.datagram[14],
                         dtlsproto.ALERT_ILLEGAL_PARAMETER)
        for raw in _mails_to_raw(out):
            client.receive_raw(raw, NOW)
        self.assertNotEqual(client.state, "established")
        self.assertEqual(server.core.sessions, {})
        self.assertEqual(calls, [])


class LossAndProviderShapeTest(unittest.TestCase):
    """Store-and-forward shapes a live provider produces: mail
    is lost and the sender retries, parts arrive out of order,
    and the provider rewrites what it carries (a Re: prefix, a
    line wrap, a footer, a subject suffix). In every case the
    carriage either delivers correctly or fails closed; a DTLS
    flight is never reinterpreted as a job."""

    def _server(self):
        return DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')

    def _drive_to_cookied_hello(self, client, server):
        """(hello-retry mails, cookied-hello mails)."""
        responses = []
        for raw in _mails_to_raw(client.start_mails(NOW)):
            responses.extend(server.receive_raw(raw, NOW))
        follow = []
        for raw in _mails_to_raw(responses):
            follow.extend(client.receive_raw(raw, NOW))
        return responses, follow

    # -- loss, with sender retry ------------------------------

    def test_a_lost_first_hello_is_retried_by_the_client(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        dropped = client.start_mails(NOW)
        self.assertTrue(dropped)          # never delivered
        retry = client.tick_mails(NOW + 2.0)
        self.assertTrue(retry)
        _pump_batches(client, server, retry)
        self.assertEqual(client.state, "established")
        self.assertEqual(client.greeting, {"disclosure": "none"})

    def test_a_lost_cookied_hello_is_retried_by_the_client(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        _hrr, cookied = self._drive_to_cookied_hello(client, server)
        self.assertTrue(cookied)          # never delivered
        retry = client.tick_mails(NOW + 2.0)
        self.assertTrue(retry)
        _pump_batches(client, server, retry)
        self.assertEqual(client.state, "established")

    def test_a_lost_server_flight_is_retried_by_the_server(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        _hrr, cookied = self._drive_to_cookied_hello(client, server)
        flight = []
        for raw in _mails_to_raw(cookied):
            flight.extend(server.receive_raw(raw, NOW))
        self.assertTrue(flight)           # never delivered
        resent = server.tick_mails(NOW + 2.0)
        self.assertTrue(resent)
        follow = []
        for raw in _mails_to_raw(resent):
            follow.extend(client.receive_raw(raw, NOW))
        _pump_batches(client, server, follow)
        self.assertEqual(client.state, "established")
        self.assertTrue(any(
            s.established for s in server.core.sessions.values()))

    def test_a_lost_finished_is_retried_by_the_client(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        _hrr, cookied = self._drive_to_cookied_hello(client, server)
        flight = []
        for raw in _mails_to_raw(cookied):
            flight.extend(server.receive_raw(raw, NOW))
        finished = []
        for raw in _mails_to_raw(flight):
            finished.extend(client.receive_raw(raw, NOW))
        self.assertTrue(finished)         # never delivered
        self.assertFalse(any(
            s.established for s in server.core.sessions.values()))
        retry = client.tick_mails(NOW + 2.0)
        self.assertTrue(retry)
        for raw in _mails_to_raw(retry):
            server.receive_raw(raw, NOW)
        self.assertTrue(any(
            s.established for s in server.core.sessions.values()))

    def test_a_lost_hello_retry_is_reanswered_and_recovers(self):
        # The asymmetric loss: the request arrived and its
        # answer was lost. Recovery still works, because a
        # retransmitted hello is not a bit-exact replay: the
        # record sequence number advances, so the carriage's
        # duplicate suppression (which stops the same mail
        # delivered twice, bit for bit) does not eat it, and
        # the stateless cookie issuer simply answers again.
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        hrr = []
        for raw in _mails_to_raw(client.start_mails(NOW)):
            hrr.extend(server.receive_raw(raw, NOW))
        self.assertTrue(hrr)              # never delivered
        retry = client.tick_mails(NOW + 2.0)
        self.assertTrue(retry)
        answered = []
        for raw in _mails_to_raw(retry):
            answered.extend(server.receive_raw(raw, NOW + 2.0))
        self.assertTrue(answered)         # a fresh HelloRetryRequest
        follow = []
        for raw in _mails_to_raw(answered):
            follow.extend(client.receive_raw(raw, NOW + 2.0))
        _pump_batches(client, server, follow)
        self.assertEqual(client.state, "established")
        self.assertEqual(client.greeting, {"disclosure": "none"})

    def test_a_lost_ticket_mail_costs_the_ticket_not_the_session(
            self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        _hrr, cookied = self._drive_to_cookied_hello(client, server)
        flight = []
        for raw in _mails_to_raw(cookied):
            flight.extend(server.receive_raw(raw, NOW))
        finished = []
        for raw in _mails_to_raw(flight):
            finished.extend(client.receive_raw(raw, NOW))
        ticket_mails = []
        for raw in _mails_to_raw(finished):
            ticket_mails.extend(server.receive_raw(raw, NOW))
        self.assertTrue(ticket_mails)     # never delivered
        self.assertEqual(client.state, "established")
        self.assertIsNone(client.core.ticket)
        for raw in _mails_to_raw(client.send_app_mails(b"ping")):
            server.receive_raw(raw, NOW)
        self.assertEqual(
            [a[2] for a in server.drain_app_messages()], [b"ping"])

    # -- out-of-order parts ------------------------------------

    def test_no_answer_until_the_last_part_lands(self):
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        mails = encode_flight(datagram, SID,
                              transfer_id="3333333333333333",
                              max_chunk_chars=64)
        self.assertGreater(len(mails), 2)
        server = self._server()
        parts = [_raw_mail(s, b) for s, b in reversed(mails)]
        for raw in parts[:-1]:
            self.assertEqual(server.receive_raw(raw, NOW), [])
        answer = server.receive_raw(parts[-1], NOW)
        self.assertTrue(answer)           # the HelloRetryRequest

    def test_a_handshake_with_every_flight_segmented_and_reversed(
            self):
        counter = [0]

        def scramble(mails):
            out = []
            for subject, body in mails:
                parsed = parse_message(_raw_mail(subject, body))
                if parsed.datagram is None:
                    out.append((subject, body))
                    continue
                parts = encode_flight(
                    parsed.datagram, parsed.session_id,
                    transfer_id="%016x" % counter[0],
                    max_chunk_chars=48)
                counter[0] += 1
                out.extend(reversed(parts))
            return out

        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        outgoing = scramble(client.start_mails(NOW))
        for _ in range(12):
            if not outgoing:
                break
            responses = []
            for raw in _mails_to_raw(outgoing):
                responses.extend(server.receive_raw(raw, NOW))
            outgoing = []
            for raw in _mails_to_raw(scramble(responses)):
                outgoing.extend(client.receive_raw(raw, NOW))
            outgoing = scramble(outgoing)
        self.assertEqual(client.state, "established")
        self.assertEqual(client.greeting, {"disclosure": "none"})
        record = scramble(client.send_app_mails(b"ping"))
        for raw in _mails_to_raw(record):
            server.receive_raw(raw, NOW)
        self.assertEqual(
            [a[2] for a in server.drain_app_messages()], [b"ping"])

    # -- provider rewriting -------------------------------------

    def test_a_reply_prefixed_subject_still_routes(self):
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        parsed = parse_message(_raw_mail("Re: " + subject, body))
        self.assertEqual(parsed.kind, "dtls-init")
        self.assertEqual(parsed.session_id, SID)
        self.assertEqual(parsed.datagram, datagram)
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        outgoing = [("Re: " + s, b)
                    for s, b in client.start_mails(NOW)]
        for _ in range(12):
            if not outgoing:
                break
            responses = []
            for raw in _mails_to_raw(outgoing):
                responses.extend(server.receive_raw(raw, NOW))
            outgoing = []
            for raw in _mails_to_raw(responses):
                outgoing.extend(
                    ("Re: " + s, b)
                    for s, b in client.receive_raw(raw, NOW))
        self.assertEqual(client.state, "established")
        self.assertEqual(client.greeting, {"disclosure": "none"})

    def test_a_line_wrapped_body_still_parses(self):
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        head, _nl, chunk = body.partition("\n")
        wrapped = head + "\r\n" + "\r\n".join(
            chunk[i:i + 76] for i in range(0, len(chunk), 76)) + "\r\n"
        parsed = parse_message(_raw_mail(subject, wrapped))
        self.assertEqual(parsed.kind, "dtls-init")
        self.assertEqual(parsed.datagram, datagram)

    def test_a_provider_footer_breaks_the_flight_closed(self):
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        raw = _raw_mail(subject,
                        body + "\n\n-- \nSent from my phone\n")
        parsed = parse_message(raw)
        self.assertEqual(parsed.kind, "dtls-invalid")
        self.assertIsNone(parsed.datagram)
        server = self._server()
        self.assertEqual(server.receive_raw(raw, NOW), [])
        self.assertFalse(server.core.sessions)
        self.assertEqual(server.drain_app_messages(), [])

    def test_a_subject_suffix_breaks_the_flight_closed(self):
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        raw = _raw_mail(subject + " [EXTERNAL]", body)
        parsed = parse_message(raw)
        self.assertEqual(parsed.kind, "dtls-invalid")
        server = self._server()
        self.assertEqual(server.receive_raw(raw, NOW), [])
        self.assertFalse(server.core.sessions)


class EmailPipeIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-v3-")
        self.paths = transports.channel_paths(self.tmp, "email")
        transports.ensure_channel_dirs(self.tmp, "email")
        self.channel = self.paths["root"]
        self.cfg = {
            "mailbox_user": "runner@example.com",
            "shared_secret": SECRET,
            "dtls_via_email": True,
            "dtls_greeting": "none",
            "oracle_opinion_mode": "off",
            "base_dir": self.tmp,
        }
        self.runner_box = LocalMailbox()
        self.client_box = LocalMailbox()
        self.pipe = email_ext.EmailPipe(
            self.cfg, self.channel,
            imap_factory=lambda cfg: self.runner_box,
            smtp_factory=lambda cfg: Deposit(self.client_box))
        self.client = DtlsMailClient(SECRET, session_id=SID)

    def _client_receive_all(self, client=None):
        client = client or self.client
        for message in list(self.client_box.messages):
            if message["seen"]:
                continue
            message["seen"] = True
            follow = client.receive_raw(message["raw"], NOW)
            if follow:
                # The client's answers (its cookied hello, its
                # Finished) are mail too: post them to the
                # runner's box for the next pass.
                self._post_client_mails(follow)

    def _post_client_mails(self, mails):
        smtp = Deposit(self.runner_box)
        for subject, body in mails:
            dtls_mailbox.send_mail(
                smtp, CFG, subject, body, to="runner@example.com")

    def _pump_pipe(self, client=None, rounds=10):
        client = client or self.client
        self._post_client_mails(client.start_mails(NOW))
        for _ in range(rounds):
            self.pipe.pass_once()
            self._client_receive_all(client)
            server = self.pipe._dtls_server
            if client.state == "established" and server and any(
                    s.established
                    and s.peer_addr == "email:" + client.session_id
                    for s in server.core.sessions.values()):
                break

    def _assert_session_result_ok(self, client, job_id):
        """The client's newest application message is the
        session-carried result for job_id, signed, and (when
        enveloped) decrypting to a result with exit code 0."""
        self.assertTrue(client.core.app_messages)
        result_text = client.core.app_messages[-1].decode("utf-8")
        head, _sep, body = result_text.partition("\n\n")
        self.assertIn("result " + job_id, head)
        payload = runner.verify_body(body.strip(), SECRET)
        if jobcrypto.is_envelope(payload):
            inner = jobcrypto.decrypt_body(
                payload, SECRET, job_id,
                payload.get("key_id") or "")
            payload = runner.verify_body(inner.strip(), SECRET)
        self.assertEqual(payload["type"], "result")
        self.assertEqual(payload["exit_code"], 0)

    def _run_channel_core(self, executed):
        cfg = dict(self.cfg)
        seen = {}
        secrets = runner.build_secrets(cfg)

        def fake_execute(*args, **kwargs):
            job = args[1] if len(args) > 1 else kwargs.get("job")
            executed.append(job)
            return {"exit_code": 0, "stdout": "pong", "stderr": "",
                    "timed_out": False, "duration_sec": 0.0}

        def process(subject, body):
            return runner.process_transport_message(
                cfg, self.tmp, seen, secrets, {}, subject, body,
                opts=Namespace(dry_run=False, no_send=False),
                transport="email")

        with mock.patch.object(runner, "execute_job", fake_execute):
            transports.service_channel(
                self.tmp, "email", process, log=lambda *a: None)
        return seen

    def test_handshake_and_a_signed_job_round_trip(self):
        self._pump_pipe()
        self.assertEqual(self.client.state, "established")
        self.assertEqual(self.client.greeting, {"disclosure": "none"})
        envelope = _job_envelope("v3-job-1")
        self._post_client_mails(self.client.send_app_mails(envelope))
        self.pipe.pass_once()
        inbox = os.path.join(self.channel, "inbox")
        names = [n for n in os.listdir(inbox)
                 if n.endswith(".job.txt")]
        self.assertEqual(names, ["v3-job-1.job.txt"])
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        self.pipe.flush_results(self.runner_box)
        dtls_mails = [m for m in self.client_box.messages
                      if not m["seen"]]
        self.assertTrue(dtls_mails)
        for message in dtls_mails:
            parsed = parse_message(message["raw"])
            self.assertIn(parsed.kind, ("dtls", "dtls-part"))
        self._client_receive_all()
        self.assertTrue(self.client.core.app_messages)
        result_text = self.client.core.app_messages[-1].decode(
            "utf-8")
        head, _sep, body = result_text.partition("\n\n")
        self.assertIn("result v3-job-1", head)
        payload = runner.verify_body(body.strip(), SECRET)
        if jobcrypto.is_envelope(payload):
            inner = jobcrypto.decrypt_body(
                payload, SECRET, "v3-job-1",
                payload.get("key_id") or "")
            payload = runner.verify_body(inner.strip(), SECRET)
        self.assertEqual(payload["type"], "result")
        self.assertEqual(payload["exit_code"], 0)

    def test_a_session_result_is_never_downgraded_to_plain_mail(
            self):
        self._pump_pipe()
        self.assertEqual(self.client.state, "established")
        envelope = _job_envelope("v3-job-held")
        self._post_client_mails(self.client.send_app_mails(envelope))
        self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        # The session is gone before the result is flushed.
        self.pipe._dtls_server.core.sessions.clear()
        self.pipe._dtls_server.core.by_addr.clear()
        before = len(self.client_box.messages)
        self.pipe.flush_results(self.runner_box)
        # Nothing arrived anywhere: the result was not sent as
        # an ordinary mail result, and its file is still in the
        # outbox waiting for a fresh session.
        self.assertEqual(len(self.client_box.messages), before)
        outbox = os.path.join(self.channel, "outbox")
        self.assertIn("v3-job-held.result.txt",
                      os.listdir(outbox))

    def test_a_cleartext_job_inside_a_session_is_refused(self):
        self._pump_pipe()
        self.assertEqual(self.client.state, "established")
        envelope = _job_envelope("v3-job-clear", encrypt=False)
        self._post_client_mails(self.client.send_app_mails(envelope))
        self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(executed, [])
        self.pipe.flush_results(self.runner_box)
        self.assertEqual(self.client.core.app_messages, [])

    def test_an_ordinary_job_is_delivered_as_a_job_not_dtls(self):
        from runner.tests.test_runner import job_email, job_payload
        raw = job_email(job_payload("plain-1"))
        self.runner_box.add(raw)
        self.pipe.pass_once()
        inbox = os.path.join(self.channel, "inbox")
        names = [n for n in os.listdir(inbox)
                 if n.endswith(".job.txt")]
        # The pipe keys delivery on the IMAP UID, as it always
        # has: the harness box offers UID commands, so the
        # ident is mail-u<uid>.
        self.assertEqual(names, ["mail-u1.job.txt"])
        server = self.pipe._dtls_server
        self.assertFalse(server.core.sessions)

    def test_resumption_over_the_pipe(self):
        self._pump_pipe()
        self.assertEqual(self.client.state, "established")
        ticket = self.client.core.ticket
        self.assertIsNotNone(ticket)
        client2 = DtlsMailClient(
            SECRET, session_id="v3-session-2", ticket=ticket)
        self._pump_pipe(client2)
        self.assertEqual(client2.state, "established")
        self.assertEqual(client2.greeting, {"disclosure": "none"})
        server = self.pipe._dtls_server
        resumed = [s for s in server.core.sessions.values()
                   if s.peer_addr == "email:v3-session-2"]
        self.assertEqual(len(resumed), 1)
        self.assertTrue(resumed[0].resumed)
        # A real signed job crosses inside the resumed session
        # and its result returns inside it.
        envelope = _job_envelope("v3-job-resumed")
        self._post_client_mails(client2.send_app_mails(envelope))
        self.pipe.pass_once()
        inbox = os.path.join(self.channel, "inbox")
        names = [n for n in os.listdir(inbox)
                 if n.endswith(".job.txt")]
        self.assertEqual(names, ["v3-job-resumed.job.txt"])
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        self.pipe.flush_results(self.runner_box)
        self._client_receive_all(client2)
        self._assert_session_result_ok(client2, "v3-job-resumed")

    def test_a_provider_rewritten_dtls_mail_delivers_no_job(self):
        # A flight a provider appended its footer to: invalid
        # as DTLS input, consumed as DTLS input, and never
        # reinterpreted as a job on this or any later pass.
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        raw = _raw_mail(subject,
                        body + "\n\n-- \nSent from my phone\n")
        uid = self.runner_box.add(raw)
        self.pipe.pass_once()
        message = [m for m in self.runner_box.messages
                   if m["uid"] == uid][0]
        self.assertTrue(message["seen"])
        inbox = os.path.join(self.channel, "inbox")
        names = [n for n in os.listdir(inbox)
                 if n.endswith(".job.txt")]
        self.assertEqual(names, [])
        self.assertFalse(self.pipe._dtls_server.core.sessions)

    def test_a_malformed_dtls_mail_is_consumed_and_delivers_nothing(
            self):
        raw = _raw_mail(flight_subject(SID), "garbage body, no header")
        uid = self.runner_box.add(raw)
        self.pipe.pass_once()
        message = [m for m in self.runner_box.messages
                   if m["uid"] == uid][0]
        self.assertTrue(message["seen"])
        inbox = os.path.join(self.channel, "inbox")
        names = [n for n in os.listdir(inbox)
                 if n.endswith(".job.txt")]
        self.assertEqual(names, [])
        self.assertFalse(self.pipe._dtls_server.core.sessions)


class ParserFuzzTest(unittest.TestCase):
    """Bookend doctrine: every ASCII symbol, plus NUL, tab, CR and
    LF, at the front and the back, in runs, and in the middle. The
    parser must never raise, and a wrapped or mutated input must
    never establish a session or produce an application message."""

    def _corpus(self, payload):
        symbols = string.punctuation + "\x00\t\r\n"
        cases = []
        for symbol in symbols:
            cases.append(symbol + payload + symbol)
            cases.append(symbol * 10 + payload)
            cases.append(payload + symbol * 10)
            mid = len(payload) // 2
            cases.append(payload[:mid] + symbol * 10 + payload[mid:])
            cases.append(symbol * 10)
        return cases

    def test_wrapped_subjects_and_bodies_fail_closed(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        datagram = client.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        server = DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')
        checked = 0
        for wrapped in self._corpus(subject):
            raw = _raw_mail(wrapped, body)
            parsed = parse_message(raw)
            self.assertIn(parsed.kind, (
                "dtls", "dtls-init", "dtls-part", "dtls-invalid",
                "job", "other"))
            checked += 1
        for wrapped in self._corpus(body):
            raw = _raw_mail(subject, wrapped)
            parsed = parse_message(raw)
            server.receive_raw(raw, NOW)
            checked += 1
        self.assertGreater(checked, 300)
        self.assertFalse(
            any(s.established for s in server.core.sessions.values()))
        self.assertEqual(server.drain_app_messages(), [])

    def test_wrapped_raw_mails_never_raise(self):
        client = dtlsproto.DtlsClientCore(SECRET)
        datagram = client.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        raw = _raw_mail(subject, body)
        for wrapped in self._corpus(raw.decode("utf-8", "replace")):
            parsed = parse_message(
                wrapped.encode("utf-8", "replace"))
            self.assertIn(parsed.kind, (
                "dtls", "dtls-init", "dtls-part", "dtls-invalid",
                "job", "other"))


if __name__ == "__main__":
    unittest.main()
