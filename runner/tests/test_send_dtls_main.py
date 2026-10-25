#!/usr/bin/env python3
"""Queue A: `send_dtls.main`'s failure exits (coverage run
40183585961: 11 lines on both platforms -- every one of
them an exit the happy-path tests never take).

The sender's contract is its exit codes: 2 when the job
cannot even be built (a refused secret is the strictness
suite's case; here, an exec with no script file), 4 when
the handshake fails or the session dies, 3 when the
result never comes, 5 when a result arrives that does
not verify -- printed raw, so the operator sees exactly
what came back, but never trusted. The handshake-failure
case is a real silent UDP port; the session cases script
the client core at the module's own seam and answer it
over a real loopback socket, so the pump, the waits and
the printing all run for real.
"""
import contextlib
import io
import os
import socket
import sys
import threading
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

import send_dtls  # noqa: E402
from send_job import sign_payload  # noqa: E402
from runner.wire import dtlsproto, jobcrypto  # noqa: E402

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"


class _FakeCore:
    """The client core with the crypto scripted out: the
    greeting is already there, feed() surfaces the
    scripted reply (or dies), and nothing else moves."""

    reply = None
    die_on_start = False

    def __init__(self, secret, key_id=None, ticket=None,
                 log=None):
        self.dead = False
        self.app_messages = []
        self.greeting = {"type": "greeting", "v": 1}
        self.ticket = None

    def start(self, now):
        if self.die_on_start:
            raise dtlsproto.DtlsError("scripted session failure")
        return [b"hello"]

    def tick(self, now):
        return []

    def send_app(self, envelope):
        return [b"job"]

    def feed(self, data, now):
        if self.reply is not None:
            self.app_messages.append(self.reply)
        return []


class _Peer(threading.Thread):
    """A UDP peer that waits for the job datagram (the
    second one: the handshake flight goes first) and
    answers it with one junk datagram."""

    def __init__(self, sock):
        super().__init__(daemon=True)
        self.sock = sock
        self.addr = None

    def run(self):
        self.sock.settimeout(10)
        try:
            _hello, addr = self.sock.recvfrom(65535)
            _job, self.addr = self.sock.recvfrom(65535)
            # Answer on a connected socket: an unconnected
            # sendto is refused outright on some hosts
            # (this VM's egress policy answers EPERM),
            # while the connected form is the one the
            # sender itself uses.
            self.sock.connect(self.addr)
            self.sock.send(b"junk")
        except OSError:
            pass


def _bound_udp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    return sock, sock.getsockname()[1]


class SendDtlsMainFailuresTest(unittest.TestCase):
    def _main(self, argv, core=None):
        out, err = io.StringIO(), io.StringIO()
        ctx = contextlib.ExitStack()
        if core is not None:
            ctx.enter_context(mock.patch.object(
                dtlsproto, "DtlsClientCore", core))
        with ctx, contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = send_dtls.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_an_exec_without_a_script_file_is_refused(self):
        rc, _out, err = self._main(
            ["--host", "127.0.0.1", "--secret", SECRET,
             "--kind", "exec"])
        self.assertEqual(rc, 2)
        self.assertIn("--script-file", err)

    def test_a_silent_peer_fails_the_handshake(self):
        sock, port = _bound_udp()
        sock.close()  # the port is real; nothing listens
        rc, _out, err = self._main(
            ["--host", "127.0.0.1", "--port", str(port),
             "--secret", SECRET, "--wait", "0.3"])
        self.assertEqual(rc, 4)
        self.assertIn("handshake failed or timed out", err)

    def test_a_result_that_never_comes_times_out(self):
        peer_sock, port = _bound_udp()
        try:
            rc, _out, err = self._main(
                ["--host", "127.0.0.1", "--port", str(port),
                 "--secret", SECRET, "--wait", "0.3"],
                core=_FakeCore)
        finally:
            peer_sock.close()
        self.assertEqual(rc, 3)
        self.assertIn("timed out waiting for the result", err)

    def test_an_unverifiable_result_is_printed_and_refused(self):
        class Core(_FakeCore):
            reply = b"result 1\n\nthis is not a signed body"

        peer_sock, port = _bound_udp()
        peer = _Peer(peer_sock)
        peer.start()
        try:
            rc, out, err = self._main(
                ["--host", "127.0.0.1", "--port", str(port),
                 "--secret", SECRET, "--wait", "5"],
                core=Core)
        finally:
            peer_sock.close()
            peer.join(timeout=5)
        self.assertEqual(rc, 5)
        self.assertIn("does not verify", err)
        self.assertIn("this is not a signed body", out)

    def test_a_session_error_is_reported(self):
        class Core(_FakeCore):
            die_on_start = True

        _sock, port = _bound_udp()
        _sock.close()
        rc, _out, err = self._main(
            ["--host", "127.0.0.1", "--port", str(port),
             "--secret", SECRET, "--wait", "0.3"],
            core=Core)
        self.assertEqual(rc, 4)
        self.assertIn("DTLS session failed", err)


class PlainResultAndTicketTest(unittest.TestCase):
    """Queue A refill: _plain_result's envelope and
    decryption legs and _load_ticket's whole body
    (coverage run 40187685363: 6 lines each, both
    platforms). The sender-side contract: a result that
    is not an envelope is refused as such; a result
    mirroring an encrypted job is decrypted and its
    inner signature verified before anything in it is
    trusted, and one bound to a different job does not
    decrypt. A session ticket on disk loads back byte
    for byte; anything unreadable or malformed loads
    as no ticket, so the handshake starts fresh.
    """

    JOB = "job-1"

    def _result(self, **kw):
        obj = {"v": 1, "type": "result", "job_id": self.JOB,
               "status": "ok", "exit_code": 0, "stdout": "pong",
               "stderr": "", "truncated": False}
        obj.update(kw)
        return obj

    def test_a_non_envelope_result_is_refused_as_such(self):
        got, err = send_dtls._plain_result(
            "just text, no envelope", SECRET, self.JOB, "")
        self.assertIsNone(got)
        self.assertIn("not an envelope", err)

    def test_an_encrypted_result_is_decrypted_and_verified(self):
        inner = sign_payload(self._result(), SECRET)
        body = jobcrypto.encrypt_body(
            inner, SECRET, self.JOB, "", sign_payload)
        got, err = send_dtls._plain_result(
            "[HOMING-PIGEON] result job-1\n\n" + body,
            SECRET, self.JOB, "")
        self.assertIsNone(err)
        head, payload = got
        self.assertEqual(head, "[HOMING-PIGEON] result job-1")
        self.assertEqual(payload["stdout"], "pong")

    def test_a_result_bound_to_another_job_does_not_decrypt(self):
        inner = sign_payload(self._result(), SECRET)
        body = jobcrypto.encrypt_body(
            inner, SECRET, "other-job", "", sign_payload)
        got, err = send_dtls._plain_result(
            "subject\n\n" + body, SECRET, self.JOB, "")
        self.assertIsNone(got)
        self.assertIn("does not decrypt", err)

    def test_a_saved_ticket_loads_back(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ticket.json")
            send_dtls._save_ticket(path, (b"ticket-bytes",
                                          b"psk-bytes"))
            self.assertEqual(send_dtls._load_ticket(path),
                             (b"ticket-bytes", b"psk-bytes"))

    def test_unreadable_tickets_load_as_none(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(send_dtls._load_ticket(
                os.path.join(d, "missing.json")))
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("not json")
            self.assertIsNone(send_dtls._load_ticket(bad))
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write('{"ticket": 5}')
            self.assertIsNone(send_dtls._load_ticket(bad))


if __name__ == "__main__":
    unittest.main(verbosity=2)
