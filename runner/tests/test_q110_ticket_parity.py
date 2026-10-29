# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Q110's fix, pinned from the ticket's side.

A DTLS resumption ticket records the identity of the key that
authenticated the session it was issued on, carried forward across
a resume, so a ticket chain is only ever as alive as the key at its
root. A resume is refused the moment that key leaves the runner's
map, exactly as a fresh handshake naming the key would be, and a
ticket that records no key does not resume. The refused ticket is
spent, housekeeping reads both shapes of table entry, and the
sender, told its ticket is refused, makes one fresh handshake under
the key itself and forgets the ticket.
"""
import os
import socket
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
if os.path.join(REPO, "runner", "cloud") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

import send_dtls  # noqa: E402
from runner.wire import dtlsproto  # noqa: E402

CURRENT = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"
OLD = "9f8e7d6c5b4a39281706f5e4d3c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a"
ADDR = ("127.0.0.1", 50002)
NOW = 1000.0
GREETING = b'{"type":"greeting","v":1}'


def _pump(client, server, now=NOW):
    out = client.start(now)
    for _ in range(60):
        if not out:
            break
        nxt = []
        for dg in out:
            nxt += server.feed(dg, ADDR, now)
        out = []
        for dg in nxt:
            out += client.feed(dg, now)
    return out


def _server(*keys):
    additional = {"old": OLD} if "old" in keys else {}
    return dtlsproto.DtlsServerCore(
        secret_lookup=dtlsproto.make_secret_lookup(
            CURRENT if "current" in keys else "", additional),
        greeting_for=lambda s: GREETING)


def _resumed(server, before):
    return [e for e in server.events[before:]
            if e[0] == "established" and e[2].get("resumed")]


class TicketRecordsItsIssuerTest(unittest.TestCase):

    def test_a_ticket_names_the_key_behind_its_session(self):
        server = _server("current", "old")
        client = dtlsproto.DtlsClientCore(OLD, key_id="old")
        _pump(client, server)
        self.assertEqual("established", client.state)
        ticket_bytes, _psk = client.ticket
        _psk, expiry, issuer = dtlsproto.ticket_fields(server.tickets[ticket_bytes])
        self.assertEqual(dtlsproto.identity_for("old"), issuer)
        self.assertEqual(NOW + dtlsproto.TICKET_LIFETIME, expiry)
        default = dtlsproto.DtlsClientCore(CURRENT)
        _pump(default, server)
        self.assertEqual(dtlsproto.DEFAULT_IDENTITY.encode("utf-8"),
                         dtlsproto.ticket_fields(server.tickets[default.ticket[0]])[2])

    def test_a_ticket_resumes_while_its_key_stands(self):
        server = _server("current", "old")
        first = dtlsproto.DtlsClientCore(OLD, key_id="old")
        _pump(first, server)
        before = len(server.events)
        again = dtlsproto.DtlsClientCore(OLD, ticket=first.ticket)
        _pump(again, server)
        self.assertEqual("established", again.state)
        self.assertEqual(1, len(_resumed(server, before)))
        self.assertNotIn(first.ticket[0], server.tickets)

    def test_a_resumed_session_issues_a_ticket_with_the_same_root(self):
        server = _server("current", "old")
        first = dtlsproto.DtlsClientCore(OLD, key_id="old")
        _pump(first, server)
        again = dtlsproto.DtlsClientCore(OLD, ticket=first.ticket)
        _pump(again, server)
        self.assertIsNotNone(again.ticket)
        self.assertEqual(dtlsproto.identity_for("old"),
                         dtlsproto.ticket_fields(server.tickets[again.ticket[0]])[2])
        # Rotation after two hops: the chain dies with its root.
        server._secret_lookup = dtlsproto.make_secret_lookup(CURRENT)
        before = len(server.events)
        third = dtlsproto.DtlsClientCore(OLD, ticket=again.ticket)
        _pump(third, server)
        self.assertEqual([], _resumed(server, before))
        self.assertTrue(third.dead)


class RefusedResumeTest(unittest.TestCase):

    def test_the_refused_ticket_is_spent_and_the_alert_is_fatal(self):
        server = _server("current", "old")
        first = dtlsproto.DtlsClientCore(OLD, key_id="old")
        _pump(first, server)
        server._secret_lookup = dtlsproto.make_secret_lookup(CURRENT)
        before = len(server.events)
        client = dtlsproto.DtlsClientCore(OLD, ticket=first.ticket)
        _pump(client, server)
        self.assertTrue(client.dead)
        self.assertEqual("dead", client.state)
        self.assertEqual([], [e for e in server.events[before:] if e[0] == "established"])
        self.assertNotIn(first.ticket[0], server.tickets)

    def test_a_fresh_handshake_under_the_standing_key_still_works(self):
        server = _server("current", "old")
        first = dtlsproto.DtlsClientCore(OLD, key_id="old")
        _pump(first, server)
        server._secret_lookup = dtlsproto.make_secret_lookup(CURRENT)
        refused = dtlsproto.DtlsClientCore(OLD, ticket=first.ticket)
        _pump(refused, server)
        fresh = dtlsproto.DtlsClientCore(CURRENT)
        _pump(fresh, server)
        self.assertEqual("established", fresh.state)
        self.assertEqual(dtlsproto.DEFAULT_IDENTITY.encode("utf-8"),
                         dtlsproto.ticket_fields(server.tickets[fresh.ticket[0]])[2])

    def test_housekeeping_reads_both_entry_shapes(self):
        server = _server("current")
        server.tickets[b"a" * 24] = (b"p", NOW - 1)
        server.tickets[b"b" * 24] = (b"p", NOW - 1, dtlsproto.DEFAULT_IDENTITY.encode())
        server.tickets[b"c" * 24] = (b"p", NOW + 1, dtlsproto.DEFAULT_IDENTITY.encode())
        server.tick(NOW)
        self.assertEqual([b"c" * 24], list(server.tickets))
        self.assertEqual((b"p", 5.0, None), dtlsproto.ticket_fields((b"p", 5.0)))


class _ScriptedCore:
    """The client core at the sender's seam: a resume attempt dies
    on arrival (the runner's fatal alert), a fresh handshake has its
    greeting at once."""

    made = []

    def __init__(self, secret, key_id=None, ticket=None, log=None):
        self.ticket_in = ticket
        self.dead = ticket is not None
        self.greeting = None if ticket is not None else {"type": "greeting"}
        self.app_messages = []
        self.ticket = None
        _ScriptedCore.made.append(self)

    def start(self, now):
        return [b"hello"]

    def tick(self, now):
        return []

    def feed(self, data, now):
        return []


class SenderFallsBackTest(unittest.TestCase):

    def setUp(self):
        self.peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.peer.bind(("127.0.0.1", 0))
        self.addCleanup(self.peer.close)
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.ticket_file = os.path.join(self.td.name, "ticket.json")
        send_dtls._save_ticket(self.ticket_file, (b"t" * 24, b"p" * 48))
        self.args = type("A", (), {
            "host": "127.0.0.1", "port": self.peer.getsockname()[1],
            "key_id": None, "ticket_file": self.ticket_file})()
        self.logged = []
        _ScriptedCore.made = []

    def _open(self, ticket):
        from unittest import mock
        with mock.patch.object(dtlsproto, "DtlsClientCore", _ScriptedCore):
            sock, client = send_dtls._open_session(
                self.args, CURRENT, ticket, 9e9,
                lambda m, level="INFO": self.logged.append((level, m)))
        if sock is not None:
            self.addCleanup(sock.close)
        return client

    def test_a_refused_resume_is_followed_by_one_fresh_handshake(self):
        client = self._open((b"t" * 24, b"p" * 48))
        self.assertIsNotNone(client)
        self.assertIsNone(client.ticket_in)
        self.assertEqual([True, False], [c.ticket_in is not None for c in _ScriptedCore.made])
        self.assertFalse(os.path.exists(self.ticket_file))
        self.assertIn(("WARN", "the resumption ticket was refused; a fresh handshake follows"),
                      self.logged)

    def test_without_a_ticket_there_is_one_attempt(self):
        client = self._open(None)
        self.assertIsNotNone(client)
        self.assertEqual(1, len(_ScriptedCore.made))
        self.assertTrue(os.path.exists(self.ticket_file))
        self.assertEqual([], self.logged)


if __name__ == "__main__":
    unittest.main()
