"""IPv6 for the DTLS session binding's direct listener.

The owner's shape (2026-11-02): IPv6 is configurable and OFF
by default. Nothing in the config names a switch: the
`transport_dtls.bind` value is the switch. Absent (or an IPv4
value) behaves exactly as it always has -- an AF_INET socket,
0.0.0.0 by default. An IPv6 literal as the bind turns IPv6
on: the listener is an AF_INET6 socket bound to that address,
sessions run with IPv6 peer addresses end to end, and the
cloud sender picks its socket family from the target address
it was given, so an SI told an IPv6 address can speak to the
runner.

Bind is a refuse-class addressing value (Decision 1): a
present bind that is not an IPv4 or IPv6 address is a startup
config error naming the key -- never a substituted address,
never a late socket failure wearing the wrong label.
"""

import importlib
import ipaddress
import json
import os
import socket
import string
import sys
import tempfile
import time
import unittest
import uuid
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner.runner import PROTOCOL_VERSION  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
from runner.wire import dtlsproto  # noqa: E402
import send_dtls  # noqa: E402
from send_job import sign_payload, verify_body  # noqa: E402

dtls_ext = importlib.import_module(
    "runner.transport_extensions.dtls.__main__")

SECRET = "2d2d42b99b668d4bcc0120c172c09e1059cdf4dd94d3422524519e3708937be4"


def _ipv6_loopback():
    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.bind(("::1", 0))
        sock.close()
        return True
    except OSError:
        return False


def _job_envelope(job_id):
    payload = {
        "v": PROTOCOL_VERSION,
        "type": "job",
        "job_id": job_id,
        "issued_at": "2026-11-02T00:00:00Z",
        "kind": "ping",
    }
    return ch.envelope(f"[HOMING-PIGEON] job {job_id}",
                       sign_payload(payload, SECRET))


def _result_envelope(job_id):
    payload = {"job_id": job_id, "stdout": "pong"}
    return ch.envelope(f"[HOMING-PIGEON] result {job_id}",
                       sign_payload(payload, SECRET))


class BindAddressFamilyTest(unittest.TestCase):
    """The parser: what bind_address accepts, what it refuses,
    and the family each accepted value selects."""

    def test_absent_bind_is_the_ipv4_default(self):
        self.assertEqual(dtls_ext.bind_address({}), "0.0.0.0")
        self.assertEqual(dtls_ext.bind_address(None), "0.0.0.0")
        self.assertEqual(dtls_ext.bind_family("0.0.0.0"),
                         socket.AF_INET)

    def test_empty_bind_is_every_ipv4_interface(self):
        self.assertEqual(dtls_ext.bind_address({"bind": ""}),
                         "0.0.0.0")
        self.assertEqual(dtls_ext.bind_address({"bind": "  \t "}),
                         "0.0.0.0")

    def test_an_ipv4_literal_selects_the_ipv4_family(self):
        self.assertEqual(
            dtls_ext.bind_address({"bind": "127.0.0.1"}),
            "127.0.0.1")
        self.assertEqual(dtls_ext.bind_family("127.0.0.1"),
                         socket.AF_INET)

    def test_an_ipv6_wildcard_bind_selects_the_v6_family(self):
        self.assertEqual(dtls_ext.bind_address({"bind": "::"}),
                         "::")
        self.assertEqual(dtls_ext.bind_family("::"),
                         socket.AF_INET6)

    def test_a_specific_ipv6_literal_is_kept_verbatim(self):
        for value in ("::1", "2001:db8::1", "fe80::1"):
            self.assertEqual(
                dtls_ext.bind_address({"bind": value}), value)
            self.assertEqual(dtls_ext.bind_family(value),
                             socket.AF_INET6)

    def test_surrounding_whitespace_is_stripped(self):
        self.assertEqual(
            dtls_ext.bind_address({"bind": "  ::1\t"}), "::1")

    def test_an_unusable_bind_refuses_and_names_the_key(self):
        for value in ("not-an-address", "localhost", "999.1.1.1",
                      "127.0.0.1.5", ":::", "2O220", "1.2.3.4/24",
                      "[::1]", "2001:db8:::1", "12 7.0.0.1"):
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError) as ctx:
                    dtls_ext.bind_address({"bind": value})
                self.assertIn("transport_dtls.bind",
                              str(ctx.exception))

    def test_a_non_string_bind_refuses_and_names_the_key(self):
        for value in (12345, None, True, ["::1"]):
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError) as ctx:
                    dtls_ext.bind_address({"bind": value})
                self.assertIn("transport_dtls.bind",
                              str(ctx.exception))


class BindParserBookendFuzzTest(unittest.TestCase):
    """The bookend sweep over the bind parser: every ASCII
    symbol, plus NUL, tab, CR and LF, at the front, at the
    back, at both, and in runs. A wrapped value either refuses
    with the key named or comes back as exactly the stripped
    value, parseable as an address -- never a different
    address than the operator wrote."""

    BOOKENDS = list(string.punctuation) + ["\x00", "\t", "\r", "\n"]
    BASES = ["127.0.0.1", "0.0.0.0", "::1", "::", "localhost",
             "example", ""]

    def _check(self, wrapped):
        try:
            out = dtls_ext.bind_address({"bind": wrapped})
        except RuntimeError as e:
            self.assertIn("transport_dtls.bind", str(e))
            return
        stripped = wrapped.strip()
        if not stripped:
            # The documented empty bind: every interface.
            self.assertEqual(out, "0.0.0.0")
            return
        ipaddress.ip_address(out)  # must parse, or it had to refuse
        self.assertEqual(out, stripped)

    def test_bookends_front_back_and_both(self):
        for base in self.BASES:
            for mark in self.BOOKENDS:
                for wrapped in (mark + base, base + mark,
                                mark + base + mark):
                    with self.subTest(wrapped=wrapped):
                        self._check(wrapped)

    def test_bookend_runs(self):
        for base in ("127.0.0.1", "::1"):
            for mark in ("\x00", "-", ";", "\t"):
                for wrapped in (mark * 10 + base,
                                base + mark * 10,
                                mark * 5 + base + mark * 5):
                    with self.subTest(wrapped=wrapped):
                        self._check(wrapped)

    def test_symbol_only_strings(self):
        for mark in self.BOOKENDS:
            for wrapped in (mark, mark * 3):
                with self.subTest(wrapped=wrapped):
                    self._check(wrapped)


@unittest.skipUnless(
    _ipv6_loopback(), "IPv6 loopback is not available on this host")
class DtlsPipeIpv6Test(unittest.TestCase):
    """Real pipes on real sockets: the family the listener
    actually opens, and a full session over ::1."""

    def _pipe(self, cfg_over):
        tmp = tempfile.mkdtemp(prefix="hp-dtls-v6-")
        channel = os.path.join(tmp, "channel")
        cfg = {"shared_secret": SECRET, "port": 0}
        cfg.update(cfg_over)
        pipe = dtls_ext.DtlsPipe(cfg, channel)
        self.addCleanup(pipe.sock.close)
        return pipe, channel, pipe.sock.getsockname()[1]

    def _drive(self, pipe, client, sock, pred, timeout=20.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pipe.run_once()
            for dg in client.tick(time.monotonic()):
                sock.send(dg)
            try:
                data = sock.recv(65535)
            except OSError:
                data = None
            if data:
                for dg in client.feed(data, time.monotonic()):
                    sock.send(dg)
            if pred():
                return True
        return pred()

    def _session(self, bind):
        pipe, channel, port = self._pipe({"bind": bind})
        client = dtlsproto.DtlsClientCore(SECRET)
        sock = send_dtls._open_socket("::1", port)
        self.addCleanup(sock.close)
        sock.settimeout(0.05)
        # Same Linux-sandbox accommodation as test_dtls.py's
        # PipeSocketTest: the pipe's socket is connected to its
        # one test peer, or this VM refuses its sends outright.
        if sys.platform.startswith("linux"):
            pipe.sock.connect(sock.getsockname())
        for dg in client.start(time.monotonic()):
            sock.send(dg)
        ok = self._drive(pipe, client, sock,
                         lambda: client.greeting is not None)
        self.assertTrue(ok, "no platform payload from the pipe")
        return pipe, channel, client, sock

    def test_the_default_pipe_is_ipv4(self):
        pipe, _channel, _port = self._pipe({})
        self.assertEqual(pipe.sock.family, socket.AF_INET)
        self.assertEqual(pipe.sock.getsockname()[0], "0.0.0.0")

    def test_an_ipv6_wildcard_pipe_opens_a_v6_socket(self):
        pipe, _channel, _port = self._pipe({"bind": "::"})
        self.assertEqual(pipe.sock.family, socket.AF_INET6)
        self.assertEqual(pipe.sock.getsockname()[0], "::")

    def test_a_specific_ipv6_literal_pipe_binds_it(self):
        pipe, _channel, _port = self._pipe({"bind": "::1"})
        self.assertEqual(pipe.sock.family, socket.AF_INET6)
        self.assertEqual(pipe.sock.getsockname()[0], "::1")

    def test_handshake_job_and_result_over_ipv6_loopback(self):
        pipe, channel, client, sock = self._session("::1")
        self.assertEqual(client.greeting["disclosure"], "family")
        jid = str(uuid.uuid4())
        for dg in client.send_app(
                _job_envelope(jid).encode("utf-8")):
            sock.send(dg)
        job_file = os.path.join(channel, "inbox",
                                f"{jid}.job.txt")
        ok = self._drive(pipe, client, sock,
                         lambda: os.path.exists(job_file))
        self.assertTrue(ok, "the job never reached the channel")
        with open(job_file, encoding="utf-8") as f:
            subject, body = ch.parse_envelope(f.read())
        self.assertIn(jid, subject)
        self.assertEqual(verify_body(body, SECRET)["job_id"], jid)
        with open(os.path.join(channel, "outbox",
                               f"{jid}.result.txt"),
                  "w", encoding="utf-8") as f:
            f.write(_result_envelope(jid) + "\n")
        ok = self._drive(
            pipe, client, sock,
            lambda: len(client.app_messages) >= 1)
        self.assertTrue(ok, "the result never came back")
        subject, body = ch.parse_envelope(
            client.app_messages[0].decode("utf-8"))
        self.assertIn("result", subject)
        self.assertEqual(verify_body(body, SECRET)["stdout"],
                         "pong")


class SenderSocketFamilyTest(unittest.TestCase):
    """send_dtls picks the socket family from the target
    address it was given."""

    def test_an_ipv4_target_gets_an_ipv4_socket(self):
        sock = send_dtls._open_socket("127.0.0.1", 20220)
        self.addCleanup(sock.close)
        self.assertEqual(sock.family, socket.AF_INET)
        self.assertEqual(sock.getpeername(), ("127.0.0.1", 20220))

    @unittest.skipUnless(
        _ipv6_loopback(),
        "IPv6 loopback is not available on this host")
    def test_an_ipv6_target_gets_an_ipv6_socket(self):
        sock = send_dtls._open_socket("::1", 20220)
        self.addCleanup(sock.close)
        self.assertEqual(sock.family, socket.AF_INET6)
        self.assertEqual(sock.getpeername()[0], "::1")
        self.assertEqual(sock.getpeername()[1], 20220)


class ServerCoreIpv6AddressTest(unittest.TestCase):
    """dtlsproto keys sessions and binds cookies by the peer
    address exactly as the socket hands it over; an IPv6
    4-tuple must be a stable, distinct key."""

    def test_addr_bytes_is_stable_and_distinct_for_v6(self):
        one = dtlsproto._addr_bytes(("::1", 20220, 0, 0))
        self.assertEqual(
            one, dtlsproto._addr_bytes(("::1", 20220, 0, 0)))
        self.assertNotEqual(
            one, dtlsproto._addr_bytes(("::1", 20221, 0, 0)))
        self.assertNotEqual(
            one, dtlsproto._addr_bytes(("::2", 20220, 0, 0)))

    def test_addr_bytes_for_ipv4_is_unchanged(self):
        self.assertEqual(
            dtlsproto._addr_bytes(("127.0.0.1", 20220)),
            b"127.0.0.1" + (20220).to_bytes(2, "big"))


class DtlsMainIpv6Test(unittest.TestCase):
    """main()'s visible surface: a bad bind refuses at
    startup with the key named, and the listening line
    brackets an IPv6 bind so the address reads whole."""

    def _cfg_file(self, d, cfg):
        path = os.path.join(d, "runtime.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        return path

    def _main(self, argv):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("HOMING_PIGEON_TRANSPORT_")}
        err = StringIO()
        with mock.patch.dict(os.environ, env, clear=True):
            with redirect_stderr(err):
                rc = dtls_ext.main(argv)
        return rc, err.getvalue()

    def test_a_non_address_bind_refuses_at_startup(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self._cfg_file(
                d, {"shared_secret": SECRET, "port": 0,
                    "bind": "not-an-address"})
            rc, err = self._main(["dtls", d, cfg])
        self.assertEqual(rc, 2)
        self.assertIn("refusing to start", err)
        self.assertIn("transport_dtls.bind", err)

    def _listening_line(self, bind, port):
        class StubPipe:
            def __init__(self, cfg, channel):
                self.bind = bind
                self.port = port

            def run_once(self):
                raise KeyboardInterrupt

        with tempfile.TemporaryDirectory() as d:
            cfg = self._cfg_file(d, {"shared_secret": SECRET,
                                     "port": 0})
            err = StringIO()
            with mock.patch.object(dtls_ext, "DtlsPipe", StubPipe):
                with redirect_stderr(err):
                    with self.assertRaises(KeyboardInterrupt):
                        dtls_ext.main(["dtls", d, cfg])
        return err.getvalue()

    def test_the_listening_line_brackets_an_ipv6_bind(self):
        err = self._listening_line("::1", 20220)
        self.assertIn("listening on udp [::1]:20220", err)

    def test_the_listening_line_for_ipv4_is_unchanged(self):
        err = self._listening_line("127.0.0.1", 20220)
        self.assertIn("listening on udp 127.0.0.1:20220", err)


if __name__ == "__main__":
    unittest.main()
