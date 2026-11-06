#!/usr/bin/env python3
"""Section 7.1 of the version 3 draft, made true in the code.

The draft's retransmission paragraph is a recommendation for
this carriage: an implementation SHOULD stretch its
retransmission timers toward the mailbox poll rhythm it
operates on -- the initial retransmission interval SHOULD be
at least 2 of the implementation's mailbox poll periods, and
an attempt SHOULD be given up after about 8 retransmissions.

The sentence-by-sentence review
(docs/infrastructure-documents/design/v3-sentence-review.md,
rows 67 and 68) found the reference
core did neither: its first retransmission interval is 1.0
second whatever the poll period is, and it bounds an attempt
by 60 seconds of wall clock (6 retransmissions), not by
count. The owner's call on the 2 open rows was to stretch
the code to match the draft. These tests pin the stretched
behavior in the mail wrappers and pin that the core's
datagram profile -- 1.0 seconds, doubling to a 16 second
cap, given up after 60 seconds -- is unchanged when no poll
period is handed over.
"""
import os
import sys
import tempfile
import unittest
from email.message import EmailMessage
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.transport_extensions import email as _email_pkg  # noqa: E402
from runner.transport_extensions.email import (  # noqa: E402
    __main__ as email_ext)
from runner.wire import dtls_mailbox, dtlsproto, transports  # noqa: E402
from runner.wire.dtls_mailbox import (  # noqa: E402
    Deposit, DtlsMailClient, DtlsMailServer, LocalMailbox)

SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)
SID = "v3-session-timers"
POLL = 10.0
# With a 10 second poll period the profile's intervals are
# 20, 40, then 80 held: retransmissions land at these offsets
# from the flight, and the attempt dies at the 9th due time.
RETRANSMIT_AT = [20.0, 60.0, 140.0, 220.0, 300.0, 380.0,
                 460.0, 540.0]
GIVE_UP_AT = 620.0


def _raw_mail(subject, body, sender="si@example.com"):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = "runner@example.com"
    msg.set_content(body)
    return msg.as_bytes()


def _mails_to_raw(mails):
    return [_raw_mail(subject, body) for subject, body in mails]


def _pump_mail(client, server, rounds=12):
    """Drive a client and a DtlsMailServer with mail tuples
    only, every mail answered at the same instant."""
    outgoing = client.start_mails(0.0)
    for _ in range(rounds):
        if not outgoing:
            break
        responses = []
        for raw in _mails_to_raw(outgoing):
            responses.extend(server.receive_raw(raw, 0.0))
        outgoing = []
        for raw in _mails_to_raw(responses):
            outgoing.extend(client.receive_raw(raw, 0.0))
    return outgoing


def _client(poll_period_sec=POLL):
    return DtlsMailClient(SECRET, session_id=SID,
                          poll_period_sec=poll_period_sec)


def _server(poll_period_sec=POLL):
    return DtlsMailServer(
        dtlsproto.make_secret_lookup(SECRET),
        platform_payload=b'{"disclosure":"none"}',
        poll_period_sec=poll_period_sec)


class ProfileShapeTest(unittest.TestCase):
    def test_profile_scales_with_the_poll_period(self):
        self.assertEqual(dtlsproto.mail_retransmit_profile(10.0),
                         (20.0, 80.0, None, 8))
        self.assertEqual(dtlsproto.mail_retransmit_profile(20.0),
                         (40.0, 160.0, None, 8))
        self.assertEqual(dtlsproto.mail_retransmit_profile(1.0),
                         (2.0, 8.0, None, 8))

    def test_profile_rejects_a_non_positive_period(self):
        for bad in (0, 0.0, -1, -20.0):
            with self.assertRaises(ValueError):
                dtlsproto.mail_retransmit_profile(bad)

    def test_wrappers_reject_a_non_positive_period(self):
        with self.assertRaises(ValueError):
            _client(poll_period_sec=0)
        with self.assertRaises(ValueError):
            _server(poll_period_sec=-1)


class ClientTimerTest(unittest.TestCase):
    def test_first_retransmission_waits_two_poll_periods(self):
        client = _client()
        self.assertTrue(client.start_mails(0.0))
        self.assertEqual(client.tick_mails(19.9), [])
        self.assertTrue(client.tick_mails(20.0))

    def test_retransmissions_double_then_hold_at_eight_periods(self):
        client = _client()
        client.start_mails(0.0)
        for at in RETRANSMIT_AT:
            self.assertEqual(client.tick_mails(at - 0.1), [],
                             f"early retransmission before {at}")
            self.assertTrue(client.tick_mails(at),
                            f"no retransmission at {at}")

    def test_attempt_is_given_up_after_eight_retransmissions(self):
        client = _client()
        client.start_mails(0.0)
        for at in RETRANSMIT_AT:
            self.assertTrue(client.tick_mails(at))
        self.assertNotEqual(client.state, "dead")
        self.assertEqual(client.tick_mails(GIVE_UP_AT - 0.1), [])
        self.assertNotEqual(client.state, "dead")
        self.assertEqual(client.tick_mails(GIVE_UP_AT), [])
        self.assertEqual(client.state, "dead")
        self.assertEqual(client.tick_mails(GIVE_UP_AT + 1000.0),
                         [])

    def test_a_fresh_flight_restarts_the_count(self):
        # The cookied hello after a HelloRetryRequest is a new
        # flight: the 8-retransmission budget starts over, it
        # does not inherit the first hello's spending.
        client = _client()
        server = _server()
        outgoing = client.start_mails(0.0)
        for at in RETRANSMIT_AT[:3]:
            self.assertTrue(client.tick_mails(at))
        responses = []
        for raw in _mails_to_raw(outgoing):
            responses.extend(server.receive_raw(raw, 300.0))
        follow = []
        for raw in _mails_to_raw(responses):
            follow.extend(client.receive_raw(raw, 300.0))
        self.assertTrue(follow)  # the cookied hello, a new flight
        for at in [300.0 + t for t in RETRANSMIT_AT]:
            self.assertTrue(client.tick_mails(at),
                            f"no retransmission at {at}")
        self.assertEqual(client.tick_mails(300.0 + GIVE_UP_AT),
                         [])
        self.assertEqual(client.state, "dead")


class ServerTimerTest(unittest.TestCase):
    def _server_flight_out(self):
        """A server whose handshake flight has been sent at
        t=0 and whose client then goes silent."""
        client = _client()
        server = _server()
        outgoing = client.start_mails(0.0)
        responses = []
        for raw in _mails_to_raw(outgoing):
            responses.extend(server.receive_raw(raw, 0.0))
        follow = []
        for raw in _mails_to_raw(responses):
            follow.extend(client.receive_raw(raw, 0.0))
        flight = []
        for raw in _mails_to_raw(follow):
            flight.extend(server.receive_raw(raw, 0.0))
        self.assertTrue(flight)
        return server

    def test_server_first_retransmission_waits_two_poll_periods(self):
        server = self._server_flight_out()
        self.assertEqual(server.tick_mails(19.9), [])
        self.assertTrue(server.tick_mails(20.0))

    def test_server_attempt_dies_after_eight_retransmissions(self):
        server = self._server_flight_out()
        sessions = list(server.core.sessions.values())
        self.assertEqual(len(sessions), 1)
        session = sessions[0]
        for at in RETRANSMIT_AT:
            self.assertTrue(server.tick_mails(at),
                            f"no retransmission at {at}")
            self.assertFalse(session.dead)
        self.assertEqual(server.tick_mails(GIVE_UP_AT), [])
        self.assertTrue(session.dead)


class DatagramProfileUnchangedTest(unittest.TestCase):
    """No poll period handed over: the core keeps the
    datagram profile exactly -- first retransmission at 1.0
    second, the attempt bounded by 60 seconds of wall clock,
    however many retransmissions that happens to be."""

    def test_client_without_a_poll_period_retransmits_at_one_second(self):
        client = DtlsMailClient(SECRET, session_id=SID)
        client.start_mails(0.0)
        self.assertEqual(client.tick_mails(0.9), [])
        self.assertTrue(client.tick_mails(1.0))

    def test_client_without_a_poll_period_dies_by_the_clock(self):
        client = DtlsMailClient(SECRET, session_id=SID)
        client.start_mails(0.0)
        # The core's own schedule, as its gap arithmetic makes
        # it: 1, 3, 9, 25, 41, 57 -- 6 retransmissions, then
        # the 60 second bound, not a count, ends the attempt.
        for at in (1.0, 3.0, 9.0, 25.0, 41.0, 57.0):
            self.assertTrue(client.tick_mails(at),
                            f"no retransmission at {at}")
        self.assertNotEqual(client.state, "dead")
        self.assertEqual(client.tick_mails(60.1), [])
        self.assertEqual(client.state, "dead")


class HandshakeStillCompletesTest(unittest.TestCase):
    def test_handshake_and_a_ping_with_the_profile_on(self):
        client = _client()
        server = _server()
        _pump_mail(client, server)
        self.assertEqual(client.state, "established")
        sessions = [s for s in server.core.sessions.values()
                    if s.established]
        self.assertEqual(len(sessions), 1)
        for raw in _mails_to_raw(client.send_app_mails(b"ping")):
            self.assertEqual(server.receive_raw(raw, 0.0), [])
        apps = server.drain_app_messages()
        self.assertEqual([a[2] for a in apps], [b"ping"])


class EmailTransportWiringTest(unittest.TestCase):
    """The production driver: the email transport hands the
    server the poll period it actually polls at, so the
    profile in force on a live runner is the draft's."""

    def _pipe(self, cfg_extra):
        tmp = tempfile.mkdtemp(prefix="hp-timers-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        paths = transports.channel_paths(tmp, "email")
        transports.ensure_channel_dirs(tmp, "email")
        cfg = {
            "mailbox_user": "runner@example.com",
            "shared_secret": SECRET,
            "dtls_via_email": True,
            "dtls_greeting": "none",
            "base_dir": tmp,
        }
        cfg.update(cfg_extra)
        return email_ext.EmailPipe(
            cfg, paths["root"],
            imap_factory=lambda cfg: LocalMailbox(),
            smtp_factory=lambda cfg: Deposit(LocalMailbox()))

    def test_configured_poll_interval_reaches_the_server(self):
        pipe = self._pipe({"poll_interval_sec": 30})
        server = pipe._build_dtls_server()
        self.assertIsNotNone(server)
        self.assertEqual(server.core.retransmit_profile,
                         (60.0, 240.0, None, 8))

    def test_default_poll_interval_reaches_the_server(self):
        pipe = self._pipe({})
        server = pipe._build_dtls_server()
        self.assertIsNotNone(server)
        self.assertEqual(server.core.retransmit_profile,
                         (40.0, 160.0, None, 8))


if __name__ == "__main__":
    unittest.main()
