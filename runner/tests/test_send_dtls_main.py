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

    def test_no_flag_means_encrypted(self):
        # --encrypt and --cleartext share one dest; without a pinned
        # default the group's default was the last action registered,
        # and a bare invocation sent cleartext.
        seen = []

        def capture(args):
            seen.append(args.cleartext)
            return None, None

        with mock.patch.object(send_dtls, "_build_body", capture):
            for extra, want in (([], False), (["--encrypt"], False),
                                (["--cleartext"], True)):
                rc, _out, _err = self._main(
                    ["--host", "127.0.0.1", "--secret", SECRET,
                     "--kind", "ping"] + extra)
                self.assertEqual(rc, 2)
        self.assertEqual(seen, [False, False, True])

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


class WaitForLegsTest(unittest.TestCase):
    """Queue A refill: _wait_for's two exits (coverage
    run 40189711740: lines 132 and 134). A session
    whose peer has died answers false at once --
    there is nothing left to wait for; a pump that
    comes back dry hands the last word to the
    predicate, the state the pump just finished
    changing.
    """

    def test_a_dead_peer_ends_the_wait(self):
        client = mock.Mock()
        client.dead = True
        self.assertFalse(send_dtls._wait_for(
            None, client, lambda: False, deadline=0.0))

    def test_a_dry_pump_asks_the_predicate(self):
        client = mock.Mock()
        client.dead = False
        calls = []

        def predicate():
            calls.append(1)
            return len(calls) > 1

        with mock.patch.object(send_dtls, "_pump",
                               return_value=False):
            self.assertTrue(send_dtls._wait_for(
                None, client, predicate, deadline=0.0))


class PumpLegsTest(unittest.TestCase):
    """Queue A: _pump's shrug -- a recv that fails
    mid-handshake (a refused or reset datagram socket)
    is not the pump's end; it keeps driving the client
    core until the deadline, and only the deadline
    makes it report False."""

    class _Core:
        def __init__(self):
            self.fed = []

        def tick(self, now):
            return []

        def feed(self, data, now):
            self.fed.append(data)
            return [b"reply"]

    class _Sock:
        def __init__(self, recv_side_effects):
            self.recv_side_effects = list(recv_side_effects)
            self.sent = []

        def send(self, dg):
            self.sent.append(dg)

        def recv(self, n):
            # The last effect repeats: a dead socket stays dead
            # for as many polls as the deadline allows.
            if len(self.recv_side_effects) > 1:
                effect = self.recv_side_effects.pop(0)
            else:
                effect = self.recv_side_effects[0]
            if isinstance(effect, BaseException):
                raise effect
            return effect

    def _pump(self, sock, core, deadline):
        ready = lambda r, w, x, t: ([sock], [], [])
        with mock.patch.object(send_dtls.select, "select", ready):
            return send_dtls._pump(sock, core, deadline)

    def test_a_failed_recv_is_shrugged_off(self):
        import time as _time
        core = self._Core()
        sock = self._Sock([OSError("connection refused"), b"datagram"])
        got = self._pump(sock, core, _time.monotonic() + 5)
        self.assertTrue(got)
        self.assertEqual(core.fed, [b"datagram"])
        self.assertEqual(sock.sent, [b"reply"])

    def test_a_dead_socket_runs_to_the_deadline(self):
        import time as _time
        core = self._Core()
        sock = self._Sock([OSError("reset")] * 100)
        got = self._pump(sock, core, _time.monotonic() + 0.3)
        self.assertFalse(got)
        self.assertEqual(core.fed, [])


class BuildBodyKeyIdTest(unittest.TestCase):
    """Queue A refill: _build_body's key_id member
    (coverage run 40189711740: line 90). Naming a
    key signs the job under that key id: the
    member rides inside the signed payload, so
    the runner selects the same key to verify.
    """

    def test_a_named_key_rides_in_the_payload(self):
        args = mock.Mock()
        args.job_id = "j-key"
        args.kind = "ping"
        args.key_id = "K2"
        args.script_file = None
        args.timeout = 30
        args.cleartext = True
        args.secret = SECRET
        job_id, envelope = send_dtls._build_body(args)
        self.assertEqual(job_id, "j-key")
        self.assertIn('"key_id":"K2"',
                      envelope.decode("utf-8"))


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


class BuildBodyScriptFileTest(unittest.TestCase):
    """Queue A refill: _build_body's script-file leg
    (local full-suite map at 93998ca: lines 93-94, 98).
    An exec job naming a script file signs the file's
    contents and the caller's timeout, not a placeholder.
    """

    def test_an_exec_job_signs_the_script_file(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            script = os.path.join(d, "job.sh")
            with open(script, "w", encoding="utf-8") as fh:
                fh.write("echo from-file\n")
            args = mock.Mock()
            args.job_id = "j-file"
            args.kind = "exec"
            args.key_id = ""
            args.script_file = script
            args.timeout = 45
            args.cleartext = True
            args.secret = SECRET
            job_id, envelope = send_dtls._build_body(args)
        self.assertEqual(job_id, "j-file")
        body = envelope.decode("utf-8")
        self.assertIn("echo from-file", body)
        self.assertIn('"timeout_sec":45', body.replace(" ", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
