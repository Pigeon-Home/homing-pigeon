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
import time
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock
import shutil

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


def _job_envelope(job_id, encrypt=True, kind="ping", secret=SECRET,
                  key_id="", **extra):
    job = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "kind": kind,
    }
    if key_id:
        job["key_id"] = key_id
    job.update(extra)
    body = sign_payload(job, secret)
    if encrypt:
        body = jobcrypto.encrypt_body(
            body, secret, job_id=job_id, key_id=key_id,
            sign=sign_payload)
    return ("[HOMING-PIGEON] job " + job_id + "\n\n" + body).encode(
        "utf-8")


# A second key, for the sessions that must not share a result.
OPS_SECRET = (
    "a1b2c3d4e5f60718"
    "293a4b5c6d7e8f90"
    "0f1e2d3c4b5a6978"
    "8796a5b4c3d2e1f0"
)


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
        # The duplicate rule is split by phase (DuplicateSplit
        # Test below): a replayed initialization is a handshake
        # datagram, so the saved answer is re-posted rather than
        # the replay being fed to the stack again -- and it
        # still creates no second session and delivers nothing.
        # What is suppressed is the re-processing, not the
        # answer. This test's name predates the split; its
        # original form expected silence, which is now the
        # application-data rule only.
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        raw = _mails_to_raw(client.start_mails(NOW))[0]
        first = server.receive_raw(raw, NOW)
        self.assertTrue(first)
        second = server.receive_raw(raw, NOW)
        self.assertEqual(
            [parse_message(_raw_mail(s, b)).datagram
             for s, b in second],
            [parse_message(_raw_mail(s, b)).datagram
             for s, b in first])
        self.assertEqual(server.core.sessions, {})
        self.assertEqual(server.drain_app_messages(), [])

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
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
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

    def test_a_session_result_expires_instead_of_waiting_forever(
            self):
        self._pump_pipe()
        self.assertEqual(self.client.state, "established")
        envelope = _job_envelope("v3-job-exp")
        self._post_client_mails(self.client.send_app_mails(envelope))
        self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        # The session is gone before the result is flushed, and
        # it never comes back. The result waits -- but not
        # forever: past the pending-result expiry it is dropped
        # (moved to done, logged), never sent as ordinary mail,
        # and its session binding is forgotten.
        self.pipe._dtls_server.core.sessions.clear()
        self.pipe._dtls_server.core.by_addr.clear()
        self.pipe._session_result_ttl = 10.0
        outbox = os.path.join(self.channel, "outbox")
        before = len(self.client_box.messages)
        with mock.patch.object(email_ext.time, "time",
                               return_value=1000.0):
            self.pipe.flush_results(self.runner_box)
        self.assertIn("v3-job-exp.result.txt", os.listdir(outbox))
        with mock.patch.object(email_ext.time, "time",
                               return_value=1011.0):
            self.pipe.flush_results(self.runner_box)
        self.assertNotIn("v3-job-exp.result.txt",
                         os.listdir(outbox))
        self.assertIn("v3-job-exp.result.txt",
                      os.listdir(os.path.join(outbox, "done")))
        self.assertEqual(len(self.client_box.messages), before)
        self.assertFalse(
            any(ident == "v3-job-exp"
                for _cid, ident in self.pipe._job_session))

    def test_held_session_results_are_count_bounded(self):
        self._pump_pipe()
        self.assertEqual(self.client.state, "established")
        for job_id in ("v3-job-cap-a", "v3-job-cap-b"):
            envelope = _job_envelope(job_id)
            self._post_client_mails(
                self.client.send_app_mails(envelope))
            self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 2)
        self.pipe._dtls_server.core.sessions.clear()
        self.pipe._dtls_server.core.by_addr.clear()
        self.pipe._session_result_max_count = 1
        outbox = os.path.join(self.channel, "outbox")
        self.pipe.flush_results(self.runner_box)
        names = set(os.listdir(outbox))
        # The older held result expired; the newer still waits.
        self.assertNotIn("v3-job-cap-a.result.txt", names)
        self.assertIn("v3-job-cap-b.result.txt", names)
        self.assertIn("v3-job-cap-a.result.txt",
                      os.listdir(os.path.join(outbox, "done")))

    def _rebuild_pipe(self):
        """The email process restarted: a fresh EmailPipe on the
        same channel directory and config, nothing carried over
        in memory."""
        self.pipe = email_ext.EmailPipe(
            self.cfg, self.channel,
            imap_factory=lambda cfg: self.runner_box,
            smtp_factory=lambda cfg: Deposit(self.client_box))

    def _drive_to_established(self, client, rounds=6):
        for _ in range(rounds):
            self.pipe.pass_once()
            self._client_receive_all(client)
            server = self.pipe._dtls_server
            if client.state == "established" and any(
                    s.established
                    for s in server.core.sessions.values()):
                break

    def test_a_responder_restart_between_retry_and_cookied_hello_completes(
            self):
        # The store-and-forward cell the datagram binding never
        # had: the HelloRetryRequest goes out, the process
        # restarts before the cookied hello comes back on a
        # later poll, and the attempt still completes because
        # the cookie key was kept beside the channel's state.
        self._post_client_mails(self.client.start_mails(NOW))
        self.pipe.pass_once()          # the retry is sent
        key_path = os.path.join(self.channel, "dtls-cookie.key")
        self.assertTrue(os.path.exists(key_path))
        if os.name == "posix":
            self.assertEqual(os.stat(key_path).st_mode & 0o777, 0o600)
        kept = self.pipe._dtls_server.core.cookie_secret
        self._client_receive_all()     # the cookied hello is posted
        self._rebuild_pipe()           # the process restarted
        self.assertEqual(self.pipe._dtls_server.core.cookie_secret,
                         kept)
        self._drive_to_established(self.client)
        self.assertEqual(self.client.state, "established")
        self.assertTrue(any(
            s.established
            for s in self.pipe._dtls_server.core.sessions.values()))

    def test_without_the_kept_cookie_key_a_restart_abandons_the_attempt(
            self):
        # The control: the same restart with the kept key gone
        # draws a fresh key, the cookied hello fails the cookie
        # check and is ignored, and no session is minted. The
        # ordinary email binding is untouched.
        self._post_client_mails(self.client.start_mails(NOW))
        self.pipe.pass_once()
        self._client_receive_all()
        os.unlink(os.path.join(self.channel, "dtls-cookie.key"))
        self._rebuild_pipe()
        self._drive_to_established(self.client)
        self.assertNotEqual(self.client.state, "established")
        self.assertEqual(self.pipe._dtls_server.core.sessions, {})

    def test_a_result_never_enters_another_keys_session(self):
        # Two keys, one job ident. The default key's session
        # carries the job and dies before the result is
        # flushed. A session under the other key then carries
        # the same ident: the job is not delivered (the hold
        # belongs to the first key), and the held result is not
        # sent into the second key's session.
        self.cfg["additional_secrets"] = {"ops": OPS_SECRET}
        self._rebuild_pipe()
        self._pump_pipe()
        self.assertEqual(self.client.state, "established")
        self._post_client_mails(
            self.client.send_app_mails(_job_envelope("v3-job-shared")))
        self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        self.pipe._dtls_server.core.sessions.clear()
        self.pipe._dtls_server.core.by_addr.clear()
        ops = DtlsMailClient(OPS_SECRET, session_id="v3-session-ops",
                             key_id="ops")
        self._pump_pipe(ops)
        self.assertEqual(ops.state, "established")
        self._post_client_mails(ops.send_app_mails(_job_envelope(
            "v3-job-shared", secret=OPS_SECRET, key_id="ops")))
        self.pipe.pass_once()
        inbox = os.path.join(self.channel, "inbox")
        self.assertNotIn("v3-job-shared.job.txt", os.listdir(inbox))
        before = len(self.client_box.messages)
        self.pipe.flush_results(self.runner_box)
        self.assertEqual(len(self.client_box.messages), before)
        outbox = os.path.join(self.channel, "outbox")
        self.assertIn("v3-job-shared.result.txt", os.listdir(outbox))
        self._client_receive_all(ops)
        self.assertEqual(ops.core.app_messages, [])

    def test_a_same_key_session_carrying_the_ident_again_gets_the_result(
            self):
        # The one way a held result still leaves on this
        # carriage: a later session under the same key carries
        # the same job ident again, and the held result answers
        # it inside that session.
        self._pump_pipe()
        self.assertEqual(self.client.state, "established")
        envelope = _job_envelope("v3-job-again")
        self._post_client_mails(self.client.send_app_mails(envelope))
        self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        self.pipe._dtls_server.core.sessions.clear()
        self.pipe._dtls_server.core.by_addr.clear()
        later = DtlsMailClient(SECRET, session_id="v3-session-again")
        self._pump_pipe(later)
        self.assertEqual(later.state, "established")
        self._post_client_mails(later.send_app_mails(envelope))
        self.pipe.pass_once()
        self.pipe.flush_results(self.runner_box)
        outbox = os.path.join(self.channel, "outbox")
        self.assertNotIn("v3-job-again.result.txt", os.listdir(outbox))
        self._client_receive_all(later)
        self._assert_session_result_ok(later, "v3-job-again")

    def test_the_session_key_does_not_authorize_the_job(self):
        # A session under one key carries a job signed under
        # another. The gate reads the job's own key; the
        # session's key confers nothing on it and takes nothing
        # from it. The job runs, and its result returns inside
        # the session that carried it.
        self.cfg["additional_secrets"] = {"ops": OPS_SECRET}
        self._rebuild_pipe()
        ops = DtlsMailClient(OPS_SECRET, session_id="v3-session-ops",
                             key_id="ops")
        self._pump_pipe(ops)
        self.assertEqual(ops.state, "established")
        self._post_client_mails(
            ops.send_app_mails(_job_envelope("v3-job-crosskey")))
        self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        self.pipe.flush_results(self.runner_box)
        self._client_receive_all(ops)
        self._assert_session_result_ok(ops, "v3-job-crosskey")

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

    def test_an_unaddressed_flight_is_not_fed_on_the_mailbox(self):
        import base64
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        raw = _raw_mail(
            dtls_mailbox.FLIGHT_SUBJECT,
            base64.b64encode(datagram).decode("ascii"))
        self.runner_box.add(raw)
        before = len(self.client_box.messages)
        self.pipe.pass_once()
        self.assertFalse(self.pipe._dtls_server.core.sessions)
        self.assertEqual(len(self.client_box.messages), before)
        self.assertTrue(self.runner_box.messages[0]["seen"])

    def test_a_restart_does_not_downgrade_a_held_session_result(self):
        self._pump_pipe()
        envelope = _job_envelope("v3-job-restart")
        self._post_client_mails(self.client.send_app_mails(envelope))
        self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        self._rebuild_pipe()
        before = len(self.client_box.messages)
        self.pipe.flush_results(self.runner_box)
        self.assertEqual(len(self.client_box.messages), before)
        self.assertIn(
            "v3-job-restart.result.txt",
            os.listdir(os.path.join(self.channel, "outbox")))
        self.assertTrue(self.pipe._session_bound("v3-job-restart"))

    def test_a_restart_keeps_a_hold_for_a_job_still_running(self):
        self._pump_pipe()
        envelope = _job_envelope("v3-job-inflight")
        self._post_client_mails(self.client.send_app_mails(envelope))
        self.pipe.pass_once()
        self._rebuild_pipe()
        self.assertTrue(self.pipe._session_bound("v3-job-inflight"))
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        before = len(self.client_box.messages)
        self.pipe.flush_results(self.runner_box)
        self.assertEqual(len(self.client_box.messages), before)
        self.assertIn(
            "v3-job-inflight.result.txt",
            os.listdir(os.path.join(self.channel, "outbox")))

    def test_expiry_of_one_result_leaves_an_in_flight_hold(self):
        self._pump_pipe()
        self._post_client_mails(
            self.client.send_app_mails(_job_envelope("v3-held-b")))
        self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        # Deliver A without flushing, so B's result is still
        # held when the session dies. A flush while the
        # session is up would send B and hide the bug.
        self.pipe.flush_results = lambda imap: None
        self._post_client_mails(
            self.client.send_app_mails(_job_envelope("v3-held-a")))
        self.pipe.pass_once()
        del self.pipe.flush_results
        self.assertTrue(self.pipe._session_bound("v3-held-a"))
        self.pipe._dtls_server.core.sessions.clear()
        self.pipe._dtls_server.core.by_addr.clear()
        self.pipe._session_result_ttl = 10.0
        for key in list(self.pipe._job_session):
            if key[1] == "v3-held-b":
                self.pipe._result_wait_since[key] = time.time() - 100
        self.pipe.flush_results(self.runner_box)
        self.assertTrue(self.pipe._session_bound("v3-held-a"))
        self.assertFalse(self.pipe._session_bound("v3-held-b"))
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        before = len(self.client_box.messages)
        self.pipe.flush_results(self.runner_box)
        self.assertEqual(len(self.client_box.messages), before)
        self.assertIn(
            "v3-held-a.result.txt",
            os.listdir(os.path.join(self.channel, "outbox")))

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


    def test_two_keys_one_ident_both_sessions_live(self):
        # The combination cell with both sessions live when
        # the result is ready: the default key's session
        # carries the job; a session under the other key
        # carries the same ident and is refused at delivery
        # (the hold belongs to the first key); the result
        # goes inside the carrying session and nowhere else.
        self.cfg["additional_secrets"] = {"ops": OPS_SECRET}
        self._rebuild_pipe()
        self._pump_pipe()
        self.assertEqual(self.client.state, "established")
        ops = DtlsMailClient(OPS_SECRET, session_id="v3-session-ops",
                             key_id="ops")
        self._pump_pipe(ops)
        self.assertEqual(ops.state, "established")
        self._post_client_mails(
            self.client.send_app_mails(_job_envelope("v3-job-both")))
        self.pipe.pass_once()
        self._post_client_mails(ops.send_app_mails(_job_envelope(
            "v3-job-both", secret=OPS_SECRET, key_id="ops")))
        self.pipe.pass_once()
        inbox = os.path.join(self.channel, "inbox")
        names = [n for n in os.listdir(inbox)
                 if n == "v3-job-both.job.txt"]
        self.assertEqual(len(names), 1)
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        self.pipe.flush_results(self.runner_box)
        self._client_receive_all()
        self._assert_session_result_ok(self.client, "v3-job-both")
        self._client_receive_all(ops)
        self.assertEqual(ops.core.app_messages, [])

    def test_a_restored_hold_still_expires(self):
        self._pump_pipe()
        self._post_client_mails(self.client.send_app_mails(
            _job_envelope("v3-job-restore-exp")))
        self.pipe.pass_once()
        executed = []
        self._run_channel_core(executed)
        self.assertEqual(len(executed), 1)
        self._rebuild_pipe()
        self.assertTrue(self.pipe._session_bound("v3-job-restore-exp"))
        # Age the restored wait past the bound, on both clocks
        # the sweep can read, and let it meet the result.
        for key in list(self.pipe._result_wait_since):
            self.pipe._result_wait_since[key] = 0.0
        result_path = os.path.join(
            self.channel, "outbox", "v3-job-restore-exp.result.txt")
        old = time.time() - 100000.0
        os.utime(result_path, (old, old))
        self.pipe._session_result_ttl = 60.0
        before = len(self.client_box.messages)
        self.pipe.flush_results(self.runner_box)
        self.assertEqual(len(self.client_box.messages), before)
        self.assertNotIn(
            "v3-job-restore-exp.result.txt",
            os.listdir(os.path.join(self.channel, "outbox")))
        self.assertFalse(self.pipe._session_bound("v3-job-restore-exp"))

    def test_a_fragmented_first_hello_draws_no_answer(self):
        client = DtlsMailClient(SECRET, session_id="v3-session-frag")
        datagram = client.core.start(NOW)[0]
        hello_len = int.from_bytes(datagram[14:17], "big")
        frag_len = hello_len - 8
        frag = bytearray(datagram[:13 + 12 + frag_len])
        frag[11:13] = (12 + frag_len).to_bytes(2, "big")
        frag[22:25] = frag_len.to_bytes(3, "big")
        subject, body = encode_flight(
            bytes(frag), "v3-session-frag")[0]
        parsed = parse_message(_mime_flight_raw(subject, body))
        self.assertEqual(parsed.kind, "dtls-invalid")
        before = len(self.client_box.messages)
        self._post_client_mails([(subject, body)])
        self.pipe.pass_once()
        self.assertEqual(len(self.client_box.messages), before)
        self.assertEqual(self.pipe._dtls_server.core.sessions, {})

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


class ReassemblyDeadlineTest(unittest.TestCase):
    """The reassembler's idle timer must not be the only bound:
    a sender that drips 1 part just inside the idle window,
    forever, would otherwise hold a transfer slot past any
    bound the specification claims. An absolute deadline runs
    from the first part, and no part refreshes it."""

    def _parts(self, datagram, count_sid=SID):
        mails = encode_flight(
            datagram, count_sid, transfer_id="bbbbbbbbbbbbbbbb",
            max_chunk_chars=64)
        return [parse_message(_raw_mail(s, b)).part
                for s, b in mails]

    def test_a_slow_drip_cannot_hold_a_transfer_past_its_deadline(
            self):
        parts = self._parts(b"z" * 200)
        self.assertGreaterEqual(len(parts), 3)
        reasm = FlightReassembler(ttl_sec=3600)
        self.assertIsNone(reasm.offer(parts[0], NOW))
        # Each later part lands inside the idle window of the
        # one before it, so an idle-only bound never fires --
        # but the span from the first part passes the deadline.
        self.assertIsNone(reasm.offer(parts[1], NOW + 3500))
        out = reasm.offer(parts[2], NOW + 7000)
        self.assertIsNone(out)
        # The expired transfer is gone; the late part started a
        # new, incomplete transfer instead of completing the
        # old one.
        self.assertEqual(reasm.pending, 1)

    def test_a_transfer_completing_inside_its_deadline_completes(
            self):
        datagram = b"z" * 200
        parts = self._parts(datagram)
        reasm = FlightReassembler(ttl_sec=3600)
        out = None
        for index, part in enumerate(parts):
            out = reasm.offer(part, NOW + index * 500) or out
        self.assertEqual(out, datagram)
        self.assertEqual(reasm.pending, 0)


class DuplicateSplitTest(unittest.TestCase):
    """Duplicate handling is split by phase. A bit-identical
    duplicate of a handshake-phase datagram re-posts the last
    outbound flight -- the peer's copy may be the retry that
    repairs a lost answer -- and is never fed to the stack
    again. A duplicate at or after establishment is dropped
    and does nothing."""

    def _server(self):
        return DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')

    def _datagrams(self, mails):
        return [parse_message(_raw_mail(s, b)).datagram
                for s, b in mails]

    def test_a_replayed_initialization_reposts_the_answer(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        raw = _mails_to_raw(client.start_mails(NOW))[0]
        first = server.receive_raw(raw, NOW)
        self.assertTrue(first)
        second = server.receive_raw(raw, NOW)
        # The duplicate is not fed to the stack again; the
        # saved answer flight is re-posted instead, so a lost
        # HelloRetryRequest is repaired by the retry itself.
        self.assertEqual(self._datagrams(second),
                         self._datagrams(first))
        # And the attempt still completes, exactly once.
        follow = []
        for raw in _mails_to_raw(second):
            follow.extend(client.receive_raw(raw, NOW))
        _pump_batches(client, server, follow)
        self.assertEqual(client.state, "established")
        sessions = [s for s in server.core.sessions.values()
                    if s.established]
        self.assertEqual(len(sessions), 1)

    def test_a_replayed_cookied_hello_reposts_the_server_flight(
            self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        answers = []
        for raw in _mails_to_raw(client.start_mails(NOW)):
            answers.extend(server.receive_raw(raw, NOW))
        follow = []
        for raw in _mails_to_raw(answers):
            follow.extend(client.receive_raw(raw, NOW))
        flight = []
        for raw in _mails_to_raw(follow):
            flight.extend(server.receive_raw(raw, NOW))
        self.assertTrue(flight)
        replay = server.receive_raw(_mails_to_raw(follow)[0], NOW)
        self.assertEqual(self._datagrams(replay),
                         self._datagrams(flight))

    def test_a_replayed_hello_retry_reposts_the_cookied_hello(
            self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        answers = []
        for raw in _mails_to_raw(client.start_mails(NOW)):
            answers.extend(server.receive_raw(raw, NOW))
        self.assertTrue(answers)
        follow = client.receive_raw(_mails_to_raw(answers)[0], NOW)
        self.assertTrue(follow)
        again = client.receive_raw(_mails_to_raw(answers)[0], NOW)
        self.assertEqual(self._datagrams(again),
                         self._datagrams(follow))

    def test_a_replayed_app_record_is_dropped_not_reposted(self):
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        _pump_mail(client, server)
        self.assertEqual(client.state, "established")
        raw = _mails_to_raw(client.send_app_mails(b"ping"))[0]
        server.receive_raw(raw, NOW)
        self.assertEqual(server.receive_raw(raw, NOW), [])
        self.assertEqual(
            [a[2] for a in server.drain_app_messages()], [b"ping"])

    def test_a_thousand_copies_of_a_hello_cost_one_repost(self):
        # The amplification cell: an unauthenticated sender who
        # can deposit mail deposits one captured ClientHello a
        # thousand times. The first copy draws the
        # HelloRetryRequest; the second re-posts it once (the
        # retry may be the signal the answer was lost); the
        # other 998 cost nothing. The count of outbound mails
        # is the assertion, not the session's final state.
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        raw = _mails_to_raw(client.start_mails(NOW))[0]
        first = server.receive_raw(raw, NOW)
        self.assertTrue(first)
        sent = []
        for _ in range(1000):
            sent.extend(server.receive_raw(raw, NOW))
        self.assertEqual(len(sent), len(first))
        self.assertEqual(self._datagrams(sent),
                         self._datagrams(first))
        self.assertEqual(server.core.sessions, {})

    def test_a_new_flight_arms_one_more_repost(self):
        # The budget is per generation of the saved flight: once
        # the stack answers the cookied hello with a new flight,
        # a duplicate of that hello draws one re-post of the
        # new flight, and a further copy draws nothing.
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        hello = _mails_to_raw(client.start_mails(NOW))[0]
        answers = server.receive_raw(hello, NOW)
        self.assertTrue(server.receive_raw(hello, NOW))   # 1 re-post
        self.assertEqual(server.receive_raw(hello, NOW), [])
        follow = []
        for raw in _mails_to_raw(answers):
            follow.extend(client.receive_raw(raw, NOW))
        cookied = _mails_to_raw(follow)[0]
        flight = server.receive_raw(cookied, NOW)
        self.assertTrue(flight)
        again = server.receive_raw(cookied, NOW)
        self.assertEqual(self._datagrams(again),
                         self._datagrams(flight))
        self.assertEqual(server.receive_raw(cookied, NOW), [])
        # The old generation stays spent: the first hello buys
        # nothing more either.
        self.assertEqual(server.receive_raw(hello, NOW), [])

    def test_the_initiator_reposts_once_per_generation(self):
        # The same budget on the initiator: a duplicated
        # HelloRetryRequest re-posts the cookied hello once,
        # and a third copy is dropped.
        server = self._server()
        client = DtlsMailClient(SECRET, session_id=SID)
        answers = []
        for raw in _mails_to_raw(client.start_mails(NOW)):
            answers.extend(server.receive_raw(raw, NOW))
        retry = _mails_to_raw(answers)[0]
        follow = client.receive_raw(retry, NOW)
        self.assertTrue(follow)
        again = client.receive_raw(retry, NOW)
        self.assertEqual(self._datagrams(again),
                         self._datagrams(follow))
        self.assertEqual(client.receive_raw(retry, NOW), [])
        self.assertEqual(client.receive_raw(retry, NOW), [])
        # And the attempt still completes, exactly once.
        _pump_batches(client, server, follow)
        self.assertEqual(client.state, "established")
        self.assertEqual(
            len([s for s in server.core.sessions.values()
                 if s.established]), 1)


def _mime_flight_raw(subject, frame_text, extra_text=None,
                     typed=True, cte="base64"):
    """A raw message in the MIME shape: the frame lives in its
    own typed part; anything else in the message -- including a
    provider footer in the text part -- is not the frame."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg["To"] = "runner@example.com"
    msg.set_content(extra_text or "This mail carries a flight.")
    if typed:
        part = EmailMessage()
        part.set_content(frame_text.encode("utf-8"),
                         maintype="application", subtype="hp-dtls3",
                         cte=cte)
        msg.add_attachment(part)
    return msg.as_bytes()


class MimeFrameTest(unittest.TestCase):
    """The frame moves into its own MIME part, so text a
    provider adds around it -- a footer in the text part, a
    banner part -- no longer destroys the flight. The typed
    part, when one is present, is the only frame source: a
    valid frame sitting in the text part does not rescue a
    broken typed part, and nothing about the move weakens the
    fail-closed rule for the naked shape."""

    def test_a_footer_in_the_text_part_no_longer_kills_the_flight(
            self):
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        raw = _mime_flight_raw(
            subject, body,
            extra_text="flight mail\n-- \nProvider footer: this "
                       "message was scanned and found ordinary.")
        parsed = parse_message(raw)
        self.assertEqual(parsed.kind, "dtls-init")
        self.assertEqual(parsed.datagram, datagram)

    def test_a_typed_part_is_the_only_frame_source(self):
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        raw = _mime_flight_raw(subject, "not a frame at all",
                               extra_text=body)
        parsed = parse_message(raw)
        self.assertEqual(parsed.kind, "dtls-invalid")

    def test_a_typed_part_must_be_base64(self):
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        raw = _mime_flight_raw(subject, body, cte="quoted-printable")
        parsed = parse_message(raw)
        self.assertEqual(parsed.kind, "dtls-invalid")

    def test_a_handshake_completes_over_mime_shaped_mail(self):
        server = DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')
        client = DtlsMailClient(SECRET, session_id=SID)

        def mime(mails):
            return [_mime_flight_raw(s, b) for s, b in mails]

        outgoing = client.start_mails(NOW)
        for _ in range(12):
            if not outgoing:
                break
            responses = []
            for raw in mime(outgoing):
                responses.extend(server.receive_raw(raw, NOW))
            outgoing = []
            for raw in mime(responses):
                outgoing.extend(client.receive_raw(raw, NOW))
        self.assertEqual(client.state, "established")
        self.assertEqual(client.greeting, {"disclosure": "none"})


    def test_the_senders_frame_part_is_a_leaf_part(self):
        # The sender this tree ships builds every flight mail
        # with build_flight_message. The frame part it emits
        # is a direct, leaf part of the message: a receiver
        # that reads the message's own parts -- the reading
        # Section 5.2 describes -- finds it there. Wrapped in
        # a message/rfc822 container it would sit one level
        # down, where a gateway that treats the container as
        # an opaque attachment, or a reader that does not
        # descend into one, loses the flight.
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        msg = dtls_mailbox.build_flight_message(CFG, subject, body)

        def walk(part, parent=None):
            yield part, parent
            if part.is_multipart():
                for sub in part.get_payload():
                    yield from walk(sub, part)

        typed = [(part, parent) for part, parent in walk(msg)
                 if part.get_content_type()
                 == dtls_mailbox.FLIGHT_CONTENT_TYPE]
        self.assertEqual(len(typed), 1)
        part, parent = typed[0]
        self.assertIsNotNone(parent)
        self.assertTrue(parent.get_content_type()
                        .startswith("multipart/"))
        self.assertFalse(part.is_multipart())
        self.assertEqual(
            str(part.get("Content-Transfer-Encoding")), "base64")
        parsed = parse_message(msg.as_bytes())
        self.assertEqual(parsed.kind, "dtls-init")
        self.assertEqual(parsed.datagram, datagram)

    def test_a_handshake_completes_over_the_senders_serialization(
            self):
        # Every flight serialized by the production sender --
        # build_flight_message to bytes -- and read back by
        # the production parser, in both directions: the exact
        # bytes the email extension puts on the wire.
        server = DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')
        client = DtlsMailClient(SECRET, session_id=SID)

        def wire(mails):
            return [dtls_mailbox.build_flight_message(
                CFG, s, b).as_bytes() for s, b in mails]

        outgoing = client.start_mails(NOW)
        for _ in range(12):
            if not outgoing:
                break
            responses = []
            for raw in wire(outgoing):
                responses.extend(server.receive_raw(raw, NOW))
            outgoing = []
            for raw in wire(responses):
                outgoing.extend(client.receive_raw(raw, NOW))
        self.assertEqual(client.state, "established")
        self.assertEqual(client.greeting, {"disclosure": "none"})
        self.assertEqual(
            len([s for s in server.core.sessions.values()
                 if s.established]), 1)
        for raw in wire(client.send_app_mails(b"ping")):
            server.receive_raw(raw, NOW)
        self.assertEqual(
            [a[2] for a in server.drain_app_messages()], [b"ping"])

    def test_a_gateway_shaped_flight_still_frames(self):
        # The product of the provider shapes, in 1 message
        # sequence: the frame segmented into small parts, a
        # footer in the text part of every mail, the parts
        # delivered in reverse order, and 1 part delivered
        # twice. The reassembled datagram is the hello, and
        # the answer is the retry a clean delivery draws.
        client = DtlsMailClient(SECRET, session_id=SID)
        first = client.start_mails(NOW)[0]
        datagram = parse_message(_raw_mail(*first)).datagram
        parts = encode_flight(datagram, SID, max_chunk_chars=64)
        self.assertGreater(len(parts), 1)
        control = DtlsMailServer(dtlsproto.make_secret_lookup(SECRET))
        expected = []
        for subject, body in parts:
            expected.extend(control.receive_raw(
                _mime_flight_raw(subject, body), NOW))
        self.assertTrue(expected)
        server = DtlsMailServer(dtlsproto.make_secret_lookup(SECRET))
        mails = [_mime_flight_raw(
            subject, body,
            extra_text="A note for a human.\n\n-- \nGateway footer")
            for subject, body in parts]
        mails.reverse()
        mails.append(mails[0])
        answers = []
        for raw in mails:
            answers.extend(server.receive_raw(raw, NOW))
        # Reassembly delivers the datagram upward exactly
        # once, and only whole: the digest check is what a
        # mangled part would fail, and a failed transfer is
        # never answered. The answer's count matches the
        # clean delivery's, and the client takes the answer
        # as its retry and produces the cookied hello.
        self.assertEqual(len(answers), len(expected))
        follow = []
        for raw in _mails_to_raw(answers):
            follow.extend(client.receive_raw(raw, NOW))
        self.assertTrue(follow)


def _hello_with_early_data(datagram):
    """A copy of one ClientHello datagram with an empty
    early_data extension (42) spliced in just before the
    pre_shared_key extension, all lengths adjusted. The binder
    no longer matches, which is fine: the rejection this
    exercises happens at hello parsing, before any binder is
    looked at."""
    dg = bytearray(datagram)
    assert dtlsproto._is_plaintext_record(bytes(dg))
    pos = 13 + 12                     # record + handshake heads
    pos += 2 + 32                     # version, random
    pos += 1 + dg[pos]                # legacy session id
    pos += 1 + dg[pos]                # legacy cookie
    suites = int.from_bytes(dg[pos:pos + 2], "big")
    pos += 2 + suites                 # cipher suites
    pos += 1 + dg[pos]                # compression methods
    ext_len_at = pos
    ext_total = int.from_bytes(dg[pos:pos + 2], "big")
    pos += 2
    end = pos + ext_total
    psk_at = None
    while pos < end:
        etype = int.from_bytes(dg[pos:pos + 2], "big")
        elen = int.from_bytes(dg[pos + 2:pos + 4], "big")
        if etype == 41:               # pre_shared_key
            psk_at = pos
            break
        pos += 4 + elen
    assert psk_at is not None
    dg[psk_at:psk_at] = b"\x00\x2a\x00\x00"
    dg[ext_len_at:ext_len_at + 2] = (ext_total + 4).to_bytes(
        2, "big")
    for off, size in ((11, 2), (14, 3), (22, 3)):
        value = int.from_bytes(dg[off:off + size], "big") + 4
        dg[off:off + size] = value.to_bytes(size, "big")
    return bytes(dg)


class EarlyDataRejectionTest(unittest.TestCase):
    """There is no 0-RTT on this carriage: a ClientHello that
    carries early data is a malformed flight and is rejected,
    not answered with a retry and not processed with the early
    data skipped."""

    def test_a_hello_offering_early_data_is_rejected(self):
        server = DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        offered = _hello_with_early_data(datagram)
        subject, body = encode_flight(offered, SID)[0]
        self.assertEqual(
            server.receive_raw(_raw_mail(subject, body), NOW), [])
        self.assertEqual(server.core.sessions, {})
        # The same hello without the extension is answered
        # with the stateless retry, as always.
        subject, body = encode_flight(datagram, SID)[0]
        self.assertTrue(
            server.receive_raw(_raw_mail(subject, body), NOW))


    def test_early_data_is_rejected_through_segmentation(self):
        # The rejection is a property of the reassembled
        # datagram, not of the single mail that carries it:
        # the same hello, segmented into parts that each
        # carry 1 reply prefix, is reassembled whole and
        # still rejected -- no retry, no session. The control
        # is the same segmentation and prefixes without the
        # spliced extension, which is answered.
        server = DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        offered = _hello_with_early_data(datagram)
        answers = []
        for subject, body in encode_flight(
                offered, SID, max_chunk_chars=96):
            answers.extend(server.receive_raw(
                _raw_mail("Re: " + subject, body), NOW))
        self.assertEqual(answers, [])
        self.assertEqual(server.core.sessions, {})
        control = DtlsMailServer(
            dtlsproto.make_secret_lookup(SECRET),
            platform_payload=b'{"disclosure":"none"}')
        answers = []
        for subject, body in encode_flight(
                datagram, SID, max_chunk_chars=96):
            answers.extend(control.receive_raw(
                _raw_mail("Re: " + subject, body), NOW))
        self.assertTrue(answers)

class SubjectPrefixTest(unittest.TestCase):
    """At most 1 leading Re: or Fwd:, case-insensitive, and
    only when the remainder is exactly a flight subject. A
    chain, or any other prefix, is not flight mail."""

    def _kind(self, subject):
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        _subject, body = encode_flight(datagram, SID)[0]
        return parse_message(_raw_mail(subject, body)).kind

    def test_one_reply_prefix_still_routes(self):
        subject = flight_subject(SID)
        self.assertEqual(self._kind("Re: " + subject), "dtls-init")
        self.assertEqual(self._kind("Fwd: " + subject), "dtls-init")
        self.assertEqual(self._kind("re: " + subject), "dtls-init")
        self.assertEqual(self._kind("FWD: " + subject), "dtls-init")

    def test_a_prefix_chain_does_not_route(self):
        subject = flight_subject(SID)
        self.assertEqual(
            self._kind("Re: Re: " + subject), "other")
        self.assertEqual(
            self._kind("Re: Fwd: " + subject), "other")

    def test_an_arbitrary_prefix_does_not_route(self):
        subject = flight_subject(SID)
        self.assertEqual(self._kind("FYI " + subject), "other")
        self.assertEqual(
            self._kind("Automatic reply: " + subject), "other")


    def test_one_prefix_on_a_badly_encoded_part_is_invalid(self):
        # The prefix tolerance and the encoding rule compose:
        # 1 reply prefix on a flight whose typed part is
        # quoted-printable still routes to the carriage, and
        # is still invalid there -- the part carries no frame
        # (Section 5.2), so nothing is fed and no session is
        # minted.
        core = dtlsproto.DtlsClientCore(SECRET)
        datagram = core.start(NOW)[0]
        subject, body = encode_flight(datagram, SID)[0]
        raw = _mime_flight_raw("Re: " + subject, body,
                               cte="quoted-printable")
        self.assertEqual(parse_message(raw).kind, "dtls-invalid")
        server = DtlsMailServer(dtlsproto.make_secret_lookup(SECRET))
        self.assertEqual(server.receive_raw(raw, NOW), [])
        self.assertEqual(server.core.sessions, {})

class _RecordingImap:
    """An IMAP double that records the FETCH item string of
    every fetch, in the UID command shape fetch_job_mails
    uses."""

    def __init__(self, raws):
        self.raws = raws
        self.fetch_items = []

    def uid(self, command, *args):
        if command == "SEARCH":
            blob = b" ".join(
                str(i + 1).encode("ascii")
                for i in range(len(self.raws)))
            return "OK", [blob]
        if command == "FETCH":
            self.fetch_items.append(str(args[1]))
            uid = int(args[0])
            raw = self.raws[uid - 1]
            head = ("%d (BODY[] {%d}"
                    % (uid, len(raw))).encode("ascii")
            return "OK", [(head, raw), b")"]
        raise AssertionError(command)


class PeekFetchTest(unittest.TestCase):
    """A fetch used to decide must not mark mail seen: RFC822
    fetches set \\Seen as a side effect, which once starved
    this carriage's own handshake. fetch_job_mails fetches
    with BODY.PEEK[]; marking seen is the consumer's explicit
    act, after consumption."""

    def test_fetches_are_peeks(self):
        raw = _raw_mail("[HOMING-PIGEON] job x", "body")
        imap = _RecordingImap([raw, raw])
        mails = dtls_mailbox.fetch_job_mails(imap)
        self.assertEqual(len(mails), 2)
        self.assertEqual(len(imap.fetch_items), 2)
        for items in imap.fetch_items:
            self.assertIn("BODY.PEEK", items)


if __name__ == "__main__":
    unittest.main()
