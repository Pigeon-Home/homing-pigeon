"""Project Platinum, cycle 1: the DTLS sender's happy path.

Targets from `runner/tools/coverage_targets.py` on the cycle-1
baseline (90445244):

  logic  runner/cloud/send_dtls.py:main (5 missing) -- the
         success tail: a result that verifies is printed, the
         resumption ticket is saved, and main returns 0. The
         failure arms are covered by test_send_dtls_main.py; no
         test had walked a session all the way to a verified
         result.
  logic  runner/cloud/send_dtls.py:_pump (3) -- the tick arm: datagrams
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

from runner.tests._compat import require_hypothesis  # noqa: E402
require_hypothesis()
from hypothesis import given, settings, strategies as st

REPO = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

import send_dtls  # noqa: E402
import send_job  # noqa: E402
from send_job import sign_payload  # noqa: E402
from runner.wire import dtlsproto, jobcrypto, verify as wire_verify  # noqa: E402

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
            # Windows keeps no POSIX mode bits (the stat reads
            # 0o666 there): the file is the proof on every leg,
            # its mode the proof on POSIX.
            if os.name == "posix":
                self.assertEqual(
                    oct(os.stat(ticket).st_mode & 0o777), "0o600")


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


class TwoSignersProbe(unittest.TestCase):
    """Q61: the cloud sender's verifier mis-segmented a signed
    body whose payload carries a `{` inside a nested string
    key plus an escaped quote, and rejected a body the runner's
    signer produced. Filed in `docs/use/questions.md` as Q61;
    the sender's opener search now parses each candidate, as
    the runner's has since Q32. The suite's own witness is
    `test_parser_properties.WireProperties.
    test_two_signers_agree`, which errored whenever hypothesis
    drew this payload.
    """

    def test_a_brace_in_a_nested_key_cross_verifies(self):
        payload = {"v": {"{": None}, "type": '"'}
        body = wire_verify.sign_payload(payload, TESTKEY)
        self.assertEqual(send_job.verify_body(body, TESTKEY), payload)
        other = send_job.sign_payload(payload, TESTKEY)
        self.assertEqual(wire_verify.verify_body(other, TESTKEY),
                         payload)


class CmdNewQueueTest(unittest.TestCase):
    """Cycle 3 target, logic class:
    `runner/cloud/send_job.py:cmd_new` (2) -- the queue's
    refusal: a hosted queue that answers anything but 200/202
    has refused the job, and the command says so and returns 1
    (the queued arm returns 0). `post_to_queue` is the module's
    own function, scripted here; the payload is a plain note so
    no interpreter or script is involved.
    """

    def _args(self, **over):
        import argparse
        args = argparse.Namespace(
            job_id="job-platinum-cmdnew", kind="note", key_id=None,
            aud=None, reply_to=None, script_url=None,
            script_sha384=None, script_file=None, file=None,
            arg=None, env=None, interpreter=None, timeout=None,
            secret=TESTKEY, cleartext=True,
            to_queue="https://queue.example.test/t/x",
            queue_token_env=None)
        for key, value in over.items():
            setattr(args, key, value)
        return args

    @settings(deadline=None)
    @given(status=st.integers(min_value=100, max_value=599))
    def test_the_queues_answer_decides_the_return(self, status):
        with mock.patch.object(
                send_job, "post_to_queue",
                return_value=(status, "scripted answer")):
            rc = send_job.cmd_new(self._args())
        self.assertEqual(rc, 0 if status in (200, 202) else 1)

    def test_to_file_writes_the_envelope_and_returns_0(self):
        # Cycle 4 target, logic class: `cmd_new` (345-350) --
        # with --to-file the envelope that would have been
        # printed is written to the file instead: the subject
        # line, a blank line, the signed body, a final newline.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "job.txt")
            rc = send_job.cmd_new(
                self._args(to_file=path, to_queue=None))
            self.assertEqual(rc, 0)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        self.assertTrue(text.startswith(
            "[HOMING-PIGEON] job job-platinum-cmdnew\n\n"))
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(
            send_job.verify_body(
                text.split("\n\n", 1)[1], TESTKEY)["job_id"],
            "job-platinum-cmdnew")


class PumpAndExtractionTest(unittest.TestCase):
    """Cycle 5 targets, guard class: `send_dtls._pump` (126)
    -- a pump whose deadline passes with nothing arriving
    answers False (the wait is over, nothing was fed); and
    `send_job._object_start` (218) -- a body whose only
    whole-object candidate does not parse is handed on by
    position, so the verifier names the real fault instead
    of the extraction giving up.
    """

    def test_a_pump_with_a_past_deadline_answers_false(self):
        import socket
        import time as time_mod
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", 0))
            client = mock.Mock()
            self.assertFalse(send_dtls._pump(
                sock, client, time_mod.monotonic() - 1.0))
        finally:
            sock.close()

    def test_an_unparseable_candidate_is_handed_on(self):
        norm = '{"a": ,,"sig":"' + "a" * 96 + '"}'
        sig_at = norm.rfind(',"sig":"')
        self.assertEqual(send_job._object_start(norm, sig_at), 0)


class PostToQueueTest(unittest.TestCase):
    """Cycle 2 target, except class:
    `runner/cloud/send_job.py:post_to_queue` (6) -- the
    HTTPError arm: an error answer is a (status, body) pair,
    never an exception, and a body that cannot even be read
    still answers with the status and an empty text. The token
    comes from the environment variable the caller names; the
    opener is the function's own argument.
    """

    TOK = "si" + "-token-for-platinum"

    class _Resp:
        def __init__(self, status, body):
            self.status = status
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return self._body

    def _post(self, opener):
        import send_job
        with mock.patch.dict(os.environ,
                             {"HP_PLATINUM_SI": self.TOK}):
            return send_job.post_to_queue(
                "https://queue.example.test/t/x", "envelope text",
                token_env="HP_PLATINUM_SI", opener=opener)

    def test_a_success_answers_status_and_text(self):
        def opener(req, timeout=None):
            return self._Resp(202, b"queued")
        self.assertEqual(self._post(opener), (202, "queued"))

    @settings(deadline=None)
    @given(code=st.sampled_from([400, 401, 403, 404, 500, 503]),
           body=st.binary(max_size=30))
    def test_an_http_error_answers_status_and_body(self, code, body):
        import io
        import urllib.error

        def opener(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, code, "scripted", {}, io.BytesIO(body))

        status, text = self._post(opener)
        self.assertEqual(status, code)
        self.assertEqual(text, body.decode("utf-8", "replace"))

    def test_an_http_error_with_an_unreadable_body(self):
        import io
        import urllib.error
        err = urllib.error.HTTPError(
            "https://queue.example.test/t/x/jobs", 502, "scripted",
            {}, io.BytesIO(b""))

        def boom():
            raise OSError("the error body is unreadable")
        err.read = boom

        def opener(req, timeout=None):
            raise err

        self.assertEqual(self._post(opener), (502, ""))


if __name__ == "__main__":
    unittest.main()
