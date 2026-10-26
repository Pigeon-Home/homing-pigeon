"""Project Platinum, cycle 1: the DTLS sender's happy path.

Targets from `runner/tools/coverage_targets.py` on the cycle-1
baseline (90445244):

  logic  cloud/send_dtls.py:main (5 missing) -- the success tail:
         a result that verifies is printed, the resumption ticket
         is saved, and main returns 0. The failure arms are covered
         by test_send_dtls_main.py; no test had walked a session
         all the way to a verified result.
  logic  cloud/send_dtls.py:_pump (3) -- the tick arm: datagrams
         the client core produces on tick are sent even when
         nothing ever arrives, until the deadline reports False.

The seam is the one the module offers: DtlsClientCore is replaced
with a scripted core (the crypto is dtlsproto's own test suite's
subject), the socket is a real loopback UDP pair, and the result
envelope is built with the real signing/encryption helpers, so
_plain_result verifies it the way a runner's reply would verify.

Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90
"""
import contextlib
import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

import send_dtls  # noqa: E402
from send_job import sign_payload  # noqa: E402
from runner.wire import dtlsproto, jobcrypto  # noqa: E402

TESTKEY = "Platinum" + "Key-7f3a" + "9c1eB8d2" + "F4a6e5C7" + "b9D1a0F2"
JOB_ID = "job-platinum-dtls-1"


def _result_envelope(encrypt):
    result = {"job_id": JOB_ID, "exit_code": 0,
              "stdout": "hello from platinum", "stderr": "",
              "truncated": False}
    body = sign_payload(result, TESTKEY)
    if encrypt:
        body = jobcrypto.encrypt_body(body, TESTKEY, JOB_ID, None,
                                      sign_payload)
    return f"[HOMING-PIGEON] result {JOB_ID}\n\n{body}\n".encode()


class _HappyCore:
    """A client core whose greeting is already there and whose
    first fed datagram surfaces the scripted result."""

    reply = None

    def __init__(self, secret, key_id=None, ticket=None, log=None):
        self.dead = False
        self.app_messages = []
        self.greeting = {"type": "greeting", "v": 1}
        self.ticket = (b"ticket-bytes", b"psk-bytes")

    def start(self, now):
        return [b"hello"]

    def tick(self, now):
        return []

    def send_app(self, envelope):
        return [b"job"]

    def feed(self, data, now):
        if self.reply is not None:
            self.app_messages.append(self.reply)
        return []


class _AnsweringPeer(threading.Thread):
    """Answers the job datagram (the second one sent) once."""

    def __init__(self, sock):
        super().__init__(daemon=True)
        self.sock = sock

    def run(self):
        self.sock.settimeout(10)
        try:
            _hello, addr = self.sock.recvfrom(65535)
            _job, addr = self.sock.recvfrom(65535)
            self.sock.connect(addr)
            self.sock.send(b"reply")
        except OSError:
            pass


def _bound_udp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    return sock, sock.getsockname()[1]


class SendDtlsHappyPathTest(unittest.TestCase):
    def _main(self, argv):
        peer_sock, port = _bound_udp()
        peer = _AnsweringPeer(peer_sock)
        peer.start()
        out, err = io.StringIO(), io.StringIO()
        try:
            with mock.patch.object(dtlsproto, "DtlsClientCore",
                                   _HappyCore), \
                    contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                rc = send_dtls.main(argv + ["--port", str(port)])
        finally:
            peer_sock.close()
        return rc, out.getvalue(), err.getvalue()

    def test_a_verified_cleartext_result_returns_zero(self):
        _HappyCore.reply = _result_envelope(encrypt=False)
        rc, out, _err = self._main(
            ["--host", "127.0.0.1", "--secret", TESTKEY,
             "--job-id", JOB_ID, "--wait", "10"])
        self.assertEqual(rc, 0)
        self.assertIn("hello from platinum", out)
        self.assertIn(f"[HOMING-PIGEON] result {JOB_ID}", out)

    def test_a_verified_encrypted_result_returns_zero(self):
        _HappyCore.reply = _result_envelope(encrypt=True)
        rc, out, _err = self._main(
            ["--host", "127.0.0.1", "--secret", TESTKEY,
             "--job-id", JOB_ID, "--wait", "10"])
        self.assertEqual(rc, 0)
        self.assertIn("hello from platinum", out)

    def test_the_ticket_is_saved_for_the_next_run(self):
        _HappyCore.reply = _result_envelope(encrypt=False)
        with tempfile.TemporaryDirectory() as td:
            ticket = os.path.join(td, "ticket.bin")
            rc, _out, _err = self._main(
                ["--host", "127.0.0.1", "--secret", TESTKEY,
                 "--job-id", JOB_ID, "--wait", "10",
                 "--ticket-file", ticket])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(ticket))
            self.assertEqual(oct(os.stat(ticket).st_mode & 0o777),
                             "0o600")


class PumpTickArmTest(unittest.TestCase):
    class _TickingCore:
        def __init__(self):
            self.ticked = False

        def tick(self, now):
            if self.ticked:
                return []
            self.ticked = True
            return [b"t1", b"t2"]

        def feed(self, data, now):
            return []

    class _RecordingSock:
        def __init__(self):
            self.sent = []

        def send(self, dg):
            self.sent.append(dg)

        def recv(self, n):
            raise OSError("nothing ever arrives")

    def test_tick_datagrams_are_sent_before_the_deadline(self):
        core = self._TickingCore()
        sock = self._RecordingSock()
        never_ready = lambda r, w, x, t: ([], [], [])  # noqa: E731
        with mock.patch.object(send_dtls.select, "select",
                               never_ready):
            got = send_dtls._pump(sock, core,
                                  time.monotonic() + 0.6)
        self.assertFalse(got)
        self.assertEqual(sock.sent, [b"t1", b"t2"])


if __name__ == "__main__":
    unittest.main()
