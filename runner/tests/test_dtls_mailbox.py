#!/usr/bin/env python3
"""DTLS datagrams through the mailbox functions.

Two local endpoints. The client and the server never hand
each other a datagram in memory. Each flight goes through
send_mail into the peer's mailbox, and comes back through
fetch_job_mails. A job sitting in the same box is not a flight.
"""
import os
import sys
import unittest
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.wire import dtlsproto  # noqa: E402
from runner.wire.dtls_mailbox import (  # noqa: E402
    Deposit, LocalMailbox, send_flight, take_flights)

SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)
CFG = {"mailbox_user": "a@example.com"}
ADDR = ("127.0.0.1", 20220)
NOW = 1_700_000_000.0


def _post(box, datagrams):
    smtp = Deposit(box)
    for datagram in datagrams:
        send_flight(smtp, CFG, datagram)


def _pump(client, server, to_server, to_client):
    flight = client.start(NOW)
    for _ in range(60):
        if not flight:
            break
        _post(to_server, flight)
        nxt = []
        for datagram in take_flights(to_server):
            nxt.extend(server.feed(datagram, ADDR, NOW))
        flight = []
        if not nxt:
            break
        _post(to_client, nxt)
        for datagram in take_flights(to_client):
            flight.extend(client.feed(datagram, NOW))
    return client, server


class MailboxCarriageTest(unittest.TestCase):
    def test_a_job_in_the_same_box_is_not_a_flight(self):
        box = LocalMailbox()
        job = EmailMessage()
        job["Subject"] = "[HOMING-PIGEON] job abc"
        job["From"] = "a@example.com"
        job.set_content("{\"type\":\"job\"}")
        box.add(job.as_bytes())
        self.assertEqual(take_flights(box), [])
        self.assertFalse(box.messages[0]["seen"])

    def test_handshake_and_a_ping(self):
        to_server = LocalMailbox()
        to_client = LocalMailbox()
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup(SECRET))
        client = dtlsproto.DtlsClientCore(SECRET)
        _pump(client, server, to_server, to_client)
        self.assertEqual(client.state, "established")
        session = next(iter(server.sessions.values()))
        self.assertTrue(session.established)
        _post(to_server, client.send_app(b"ping"))
        for datagram in take_flights(to_server):
            server.feed(datagram, ADDR, NOW)
        apps = [event for event in server.events if event[0] == "app"]
        self.assertEqual(apps[-1][2], b"ping")
        # The job poll still has nothing that this carriage consumed
        # as a job. The flights were marked seen.
        self.assertEqual(take_flights(to_server), [])


if __name__ == "__main__":
    unittest.main()
