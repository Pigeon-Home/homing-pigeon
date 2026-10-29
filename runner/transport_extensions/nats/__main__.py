"""The NATS transport extension: core NATS pub/sub is the pipe.

Config (transport_nats block, handed over by the runner):
    url                     broker URL (default
                            nats://127.0.0.1:4222); userinfo in
                            the URL is one credential source
    subject                 jobs subject (default
                            homing-pigeon.jobs)
    result_subject_prefix   results go to <prefix>.<job_id>
                            (default homing-pigeon.results)
    user / password / token broker credentials; these config
                            keys win over the URL userinfo
    allow_unauthenticated   literal true opts out of the
                            credential requirement (see below)

The hand-rolled stdlib client below speaks just enough of the
core NATS text protocol: INFO, CONNECT, SUB, MSG, PUB,
PING/PONG. No JetStream, no persistence: a job published while
no runner is subscribed is gone, exactly like a shout in an
empty room -- senders who need store-and-forward use email or
the file transport.

Two gates guard this transport: the broker's own
authentication and the HMAC body signature the runner checks.
The credentials are REQUIRED: with none configured this
extension refuses to start unless allow_unauthenticated is
explicitly true -- broker authentication is this transport's
first authorization gate, which is what makes a
required-auth NATS deployment a more secure option than
email, where the signature is the only sender gate.
"""

import os
import re
import socket
import sys
import time
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from runner.transport_extensions import channel as ch  # noqa: E402


class TransportError(Exception):
    """The broker connection failed; the pipe reconnects."""


class _Idle(Exception):
    """The read deadline passed with nothing more to read."""


def _silent_log(msg, level="INFO"):
    pass


_JOB_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)", re.I)
_RESULT_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+(?:result|qresult)\s+(\S+)",
    re.I)


DEFAULT_PORT = 4222


def url_port(url):
    """The port of a NATS URL: 4222 when the URL names none, the port
    when it is a whole number 1..65535, and a config error otherwise.

    The broker address is the refuse class of
    docs/design/present-but-invalid-config.md: a port typed as
    "2O220" or 99999 must not quietly become 4222, because the
    extension would then talk to a broker the operator never named.
    urlparse's .port raises on both shapes; that ValueError once
    escaped the reconnect loop and killed the extension before its
    first connect, and after that read as the default. Now it is
    named and refused at startup.
    """
    parsed = urlparse(url or "nats://127.0.0.1:%d" % DEFAULT_PORT)
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    host_part = netloc.rsplit("]", 1)[-1] if "]" in netloc else netloc
    if ":" not in host_part:
        return DEFAULT_PORT
    text = host_part.rsplit(":", 1)[1]
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is None or not 1 <= port <= 65535:
        raise RuntimeError(
            "config error: transport_nats.url port must be a whole "
            "number 1..65535, not %r" % (text[:40],))
    return port


class NatsClient:
    """A minimal core-NATS client, hand-rolled on stdlib sockets.

    Speaks just enough of the text protocol: reads the server's
    INFO, sends CONNECT and PING (expecting PONG), SUBscribes,
    reads MSG frames, PUBs, and answers server PINGs with PONG.
    No JetStream, no clustering, no reconnect smarts -- the
    transport fails the cycle and the next poll reconnects.
    """

    def __init__(self, url, log=None, timeout=10.0,
                 user=None, password=None, token=None):
        self.log = log or _silent_log
        parsed = urlparse(url or "nats://127.0.0.1:%d" % DEFAULT_PORT)
        self.host = parsed.hostname or "127.0.0.1"
        # docs/oracle/configuring-oracle.md: default port 4222 when the URL
        # names none; a port present but not usable is a config
        # error (url_port), so no client ever talks to a substituted
        # broker address.
        self.port = url_port(url)
        self._connect_opts = {"verbose": False, "pedantic": False,
                              "name": "homing-pigeon",
                              "lang": "python-stdlib", "version": "1"}
        # Authentication for the CONNECT: explicit credentials
        # (the transport_nats config keys) win over any userinfo
        # embedded in the URL.
        if token:
            self._connect_opts["auth_token"] = str(token)
        elif user:
            self._connect_opts["user"] = str(user)
            self._connect_opts["pass"] = str(password or "")
        elif parsed.password:
            self._connect_opts["user"] = unquote(parsed.username or "")
            self._connect_opts["pass"] = unquote(parsed.password)
        elif parsed.username:
            self._connect_opts["auth_token"] = unquote(parsed.username)
        self.timeout = timeout
        self.sock = None
        self._buf = b""
        self._sid = 0

    # -- line/frame IO ------------------------------------------------
    def _fill(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _Idle()
        # close() may run on another thread (the pipe's stop): the
        # socket is read once, and a closed client is a closed
        # connection, never an AttributeError out of the loop.
        sock = self.sock
        if sock is None:
            raise TransportError("nats: the connection is closed")
        try:
            sock.settimeout(remaining)
            chunk = sock.recv(65536)
        except socket.timeout:
            raise _Idle()
        except OSError as e:
            raise TransportError(f"nats: read failed: {e}")
        if not chunk:
            raise TransportError("nats: server closed the "
                                   "connection")
        self._buf += chunk

    def _readline(self, deadline):
        while b"\r\n" not in self._buf:
            self._fill(deadline)
        line, self._buf = self._buf.split(b"\r\n", 1)
        return line.decode("utf-8", errors="replace")

    def _read_exact(self, n, deadline):
        while len(self._buf) < n:
            try:
                self._fill(deadline)
            except _Idle:
                raise TransportError("nats: timed out "
                                     "mid-message")
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _send(self, data):
        sock = self.sock
        if sock is None:
            raise TransportError("nats: the connection is closed")
        try:
            sock.sendall(data)
        except OSError as e:
            raise TransportError(f"nats: send failed: {e}")

    # -- protocol -----------------------------------------------------
    def connect(self):
        import json as _json
        try:
            self.sock = socket.create_connection(
                (self.host, self.port), timeout=self.timeout)
        except OSError as e:
            raise TransportError(
                f"nats: cannot connect to "
                f"{self.host}:{self.port}: {e}")
        deadline = time.monotonic() + self.timeout
        try:
            line = self._readline(deadline)
        except _Idle:
            raise TransportError("nats: timed out waiting for "
                                   "the server INFO")
        if not line.startswith("INFO "):
            raise TransportError(f"nats: expected INFO, got "
                                 f"{line[:40]!r}")
        self._send(b"CONNECT "
                   + _json.dumps(self._connect_opts).encode()
                   + b"\r\nPING\r\n")
        try:
            line = self._readline(deadline)
        except _Idle:
            raise TransportError("nats: timed out waiting for "
                                   "PONG")
        if line.startswith("-ERR"):
            raise TransportError(f"nats: server error: "
                                 f"{line[5:].strip()}")
        if line != "PONG":
            raise TransportError(f"nats: expected PONG, got "
                                 f"{line[:40]!r}")
        return self

    def subscribe(self, subject):
        self._sid += 1
        self._send(f"SUB {subject} {self._sid}\r\n".encode())
        return self._sid

    def publish(self, subject, payload):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        self._send(f"PUB {subject} {len(payload)}\r\n".encode()
                   + payload + b"\r\n")

    def ping(self):
        self._send(b"PING\r\n")

    def next_message(self, deadline):
        """One MSG frame as (subject, payload_bytes), or None at
        the deadline. PINGs are answered inline; other control
        lines are skipped."""
        while True:
            try:
                line = self._readline(deadline)
            except _Idle:
                return None
            if line == "PING":
                self._send(b"PONG\r\n")
                continue
            if line == "PONG" or line.startswith("+OK"):
                continue
            if line.startswith("-ERR"):
                raise TransportError(f"nats: server error: "
                                     f"{line[5:].strip()}")
            if line.startswith("MSG "):
                parts = line.split(" ")
                # MSG <subject> <sid> [reply-to] <bytes>
                # ASCII digits only: str.isdigit() also takes '²',
                # which int() refuses, and '٣', which it reads as 3.
                if len(parts) not in (4, 5) or not parts[-1].isascii() \
                        or not parts[-1].isdigit():
                    raise TransportError(f"nats: malformed MSG line "
                                         f"{line[:80]!r}")
                size = int(parts[-1])
                raw = self._read_exact(size + 2, deadline)
                return parts[1], raw[:size]
            # Unknown line: not fatal to a minimal client; skip.

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None




class NatsPipe:
    """A persistent broker connection: jobs in on the jobs
    subject, results out on <prefix>.<job_id>, through the
    channel. A dead connection is re-established with backoff;
    nothing here can take the runner down -- worst case this
    process exits and the supervisor restarts it."""

    def __init__(self, cfg, channel_dir, log=None):
        self.log = log or ch.log
        self.url = str(cfg.get("url") or "nats://127.0.0.1:4222")
        self.subject = str(cfg.get("subject")
                           or "homing-pigeon.jobs")
        self.result_prefix = str(
            cfg.get("result_subject_prefix")
            or "homing-pigeon.results")
        self.channel = channel_dir
        self.client = None
        self._running = True
        self._user = cfg.get("user") or None
        self._password = cfg.get("password") or None
        self._token = cfg.get("token") or None
        # The broker address is checked once, here, where main()
        # turns a config error into "refusing to start" and exit 2;
        # the reconnect loop never meets an unusable URL.
        try:
            url_port(self.url)
        except RuntimeError as e:
            raise TransportError(
                "nats transport refuses to start: %s" % e) from None
        parsed = urlparse(self.url)
        has_creds = bool(self._token or self._user
                         or parsed.username or parsed.password)
        allow_unauth = cfg.get("allow_unauthenticated") is True
        if not has_creds and not allow_unauth:
            raise TransportError(
                "nats transport refuses to start: no broker "
                "credentials configured (set transport_nats "
                "user/password or token, or embed them in the "
                "url) and allow_unauthenticated is not true; "
                "broker authentication is this transport's "
                "first authorization gate")
        if has_creds:
            self.log("nats transport: two authorization gates "
                     "in force -- broker authentication, then "
                     "the HMAC body signature")
        else:
            self.log("nats transport: allow_unauthenticated "
                     "is set and no broker credentials are "
                     "configured, so the HMAC body signature "
                     "is the ONLY authorization gate on this "
                     "transport", "WARN")

    def _connect(self):
        self.client = NatsClient(
            self.url, log=self.log, user=self._user,
            password=self._password, token=self._token)
        self.client.connect()
        self.client.subscribe(self.subject)

    def _flush_results(self, client):
        for fname, subject, body in ch.pending_results(
                self.channel):
            m = _RESULT_ID_RE.search(subject or "")
            job_id = m.group(1) if m else "unknown"
            client.publish(
                f"{self.result_prefix}.{job_id}",
                ch.envelope(subject, body))
            ch.ack_result(self.channel, fname)

    def stop(self):
        # Called from another thread. It closes the socket and leaves
        # the client to the loop: the loop is the only one that drops
        # it, so it never reads a client this thread just cleared.
        self._running = False
        client = self.client
        if client is not None:
            client.close()

    def run(self):
        self._running = True
        backoff = 1.0
        while self._running:
            try:
                self._connect()
                backoff = 1.0
                self.log(f"nats transport: subscribed to "
                       f"{self.subject} on {self.url}")
                client = self.client
                while self._running:
                    self._flush_results(client)
                    got = client.next_message(
                        time.monotonic() + 0.5)
                    if got is None:
                        continue
                    _subject, payload = got
                    try:
                        text = payload.decode("utf-8")
                    except UnicodeDecodeError:
                        self.log("nats transport: dropped a "
                                 "non-UTF-8 message", "WARN")
                        continue
                    parsed = ch.parse_envelope(text)
                    if parsed is None:
                        self.log("nats transport: dropped a "
                                 "malformed envelope (no blank "
                                 "line)", "WARN")
                        continue
                    esubject, ebody = parsed
                    m = _JOB_ID_RE.search(esubject)
                    ident = m.group(1) if m else None
                    ch.deliver_job(self.channel,
                                   ident or _subject, esubject,
                                   ebody)
            except TransportError as e:
                if self.client is not None:
                    self.client.close()
                    self.client = None
                if not self._running:
                    break     # stopped: the closed socket is the stop
                self.log(f"nats transport: {e}; reconnecting in "
                       f"{backoff:.0f}s", "WARN")
                ch.nap(backoff)
                backoff = min(30.0, backoff * 2)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    channel_dir, cfg = ch.load_runtime_config(argv)
    if not channel_dir:
        ch.log("nats transport: no channel directory given",
               "ERROR")
        return 2
    try:
        pipe = NatsPipe(cfg, channel_dir)
    except TransportError as e:
        ch.log(str(e), "ERROR")
        return 2
    pipe.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
