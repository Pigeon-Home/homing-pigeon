"""Job transports: the pipes that carry signed jobs to the runner.

Email is transport #1 and stays the default. This module is the
seam the other pipes hang off: a transport delivers envelopes --
a subject line, a blank line, then the signed body, exactly the
shape cloud/send_job.py prints -- into the runner's one
verification/execution core, and carries the core's result
messages back out. A transport never replaces the signature:
the HMAC on the body is checked by the core on every transport,
after the pipe delivers. Where a pipe has credentials of its
own they count as a first gate, not a formality -- the NATS
transport requires broker authentication by default, and the
file transport's first gate is the inbox folder's OS access
control.

Ships here: the file transport (a watched inbox folder, for
local harnesses, CI, and anything that can share a folder) and a
core-NATS transport (plain pub/sub; no JetStream, no clustering).
The mail transport needs no class -- the runner's IMAP/SMTP path
predates the seam and is wired in runner.py directly.

Stdlib only, like the rest of the runner. This module imports
nothing from runner.py; the runner passes its log function in.
"""

import os
import re
import socket
import time
from urllib.parse import unquote, urlparse

# Every transport name the runner will accept in the `transports`
# config key. Unknown names are a startup error, never a silent
# skip: a typo'd pipe must not look like a quiet cycle.
TRANSPORT_NAMES = ("email", "file", "nats")

DEFAULT_TRANSPORTS = ["email"]

# The file transport refuses job files larger than this, unread.
# It matches the mail path's default max_job_bytes so a job that
# fits one pipe fits the other.
FILE_MAX_BYTES = 4 * 1024 * 1024

_RESULT_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+(?:result|qresult)\s+(\S+)", re.I)
_JOB_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)", re.I)


class TransportError(Exception):
    """A transport failed this cycle; the next cycle retries."""


class _Idle(Exception):
    """The read deadline passed with nothing more to read."""


# Gate notices are logged once per process, not once per poll
# cycle: transports are rebuilt every cycle, and a line repeated
# every 20 seconds would bury the log it is meant to inform.
_NOTICE_LOGGED = set()


def _notice_once(key, log, msg, level="INFO"):
    if key in _NOTICE_LOGGED:
        return
    _NOTICE_LOGGED.add(key)
    log(msg, level)


def _silent_log(msg, level="INFO"):
    pass


def enabled_transports(cfg):
    """The validated transport names for this config.

    `transports` may be a list or a comma-separated string.
    Absent means the default, ["email"]. Raises ValueError on an
    unknown name or a value of the wrong shape -- main() turns
    that into a startup error, and poll_once lets it surface as a
    failed cycle rather than guessing.
    """
    raw = cfg.get("transports") if isinstance(cfg, dict) else None
    if raw is None:
        return list(DEFAULT_TRANSPORTS)
    if isinstance(raw, str):
        names = [p.strip() for p in raw.split(",")]
    elif isinstance(raw, (list, tuple)):
        names = [str(p).strip() for p in raw]
    else:
        raise ValueError(
            f"transports must be a list of names or a "
            f"comma-separated string (got {type(raw).__name__})")
    out = []
    for name in names:
        if not name:
            continue
        if name not in TRANSPORT_NAMES:
            raise ValueError(
                f"unknown transport {name!r}: expected one of "
                f"{', '.join(TRANSPORT_NAMES)}")
        if name not in out:
            out.append(name)
    if not out:
        raise ValueError("transports names no transport")
    return out


def parse_envelope(text):
    """Split an envelope into (subject, body_text), or None.

    The envelope is a subject line, a blank line, then the signed
    body -- the exact shape send_job.py prints. Returns None when
    there is no blank line: without one the two halves cannot be
    told apart, and guessing would hand the core a body whose
    subject the sender never wrote.
    """
    if not isinstance(text, str):
        return None
    text = text.replace("\r\n", "\n")
    head, sep, body = text.partition("\n\n")
    if not sep:
        return None
    return head.strip(), body


def format_envelope(subject, body):
    """The envelope text for a subject and body."""
    return f"{subject}\n\n{body}"


class IncomingMessage:
    """One delivered envelope, plus where its results go.

    reply(subject, body) carries one result message back out the
    pipe. ack() marks the delivery consumed (the file transport
    moves the job file to done/); transports with nothing to ack
    leave it a no-op. `ident` names the delivery in log lines.
    """

    def __init__(self, subject, body, reply, ack=None, ident=""):
        self.subject = subject
        self.body = body
        self._reply = reply
        self._ack = ack
        self.ident = ident

    def reply(self, subject, body):
        self._reply(subject, body)

    def ack(self):
        if self._ack is not None:
            self._ack()


def _config_block(cfg, key):
    block = cfg.get(key) if isinstance(cfg, dict) else None
    return block if isinstance(block, dict) else {}


def _resolve_dir(base_dir, value, default_parts):
    if value:
        path = str(value)
        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)
        return path
    return os.path.join(base_dir, *default_parts)


class FileTransport:
    """Jobs as files in a watched inbox folder.

    Layout under the base dir unless configured otherwise:
    <base_dir>/transport-file/inbox holds job files,
    <base_dir>/transport-file/outbox receives results as
    <job_id>.result.txt, and processed job files move to
    inbox/done -- never deleted, so a run can be audited after
    the fact. A job file is the envelope: first line the subject
    line, a blank line, then the signed body.

    Discipline mirrors the local-signal inbox: symlinks are
    refused unread, files over FILE_MAX_BYTES are refused
    unread, and every file is processed exactly once -- refused
    and malformed files still move to done/, with the reason
    logged, so a poison file cannot wedge the folder.
    """

    name = "file"

    def __init__(self, cfg, base_dir, log=None):
        block = _config_block(cfg, "transport_file")
        self.inbox_dir = _resolve_dir(
            base_dir, block.get("inbox_dir"),
            ("transport-file", "inbox"))
        self.outbox_dir = _resolve_dir(
            base_dir, block.get("outbox_dir"),
            ("transport-file", "outbox"))
        self.done_dir = os.path.join(self.inbox_dir, "done")
        self.log = log or _silent_log

    def fetch(self):
        os.makedirs(self.inbox_dir, exist_ok=True)
        os.makedirs(self.outbox_dir, exist_ok=True)
        os.makedirs(self.done_dir, exist_ok=True)
        out = []
        for name in sorted(os.listdir(self.inbox_dir)):
            if name == "done":
                continue
            path = os.path.join(self.inbox_dir, name)
            # Files and symlinks (refused unread, in _message)
            # are deliveries; directories and anything else are
            # not the transport's business.
            if not os.path.isfile(path) and not os.path.islink(path):
                continue
            out.append(self._message(name, path))
        return out

    def _message(self, name, path):
        state = {"job_id": None}

        def ack():
            try:
                os.replace(path, os.path.join(self.done_dir, name))
            except OSError as e:
                self.log(f"file transport: cannot move {name} "
                         f"to done: {e}", "WARN")

        def refuse(why):
            self.log(f"file transport: {name}: refused: {why}",
                     "WARN")
            return IncomingMessage("", "", lambda s, b: None,
                                   ack=ack, ident=name)

        if os.path.islink(path):
            return refuse("symlink job files are not read")
        try:
            size = os.path.getsize(path)
        except OSError as e:
            return refuse(f"cannot stat: {e}")
        if size > FILE_MAX_BYTES:
            return refuse(f"{size} bytes exceeds the "
                          f"{FILE_MAX_BYTES}-byte cap")
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            return refuse(f"cannot read as UTF-8: {e}")
        parsed = parse_envelope(text)
        if parsed is None:
            return refuse("malformed envelope (no blank line "
                          "between subject and body)")
        subject, body = parsed
        m = _JOB_ID_RE.search(subject)
        state["job_id"] = m.group(1) if m else None

        def reply(rsubject, rbody):
            self._write_result(state["job_id"], rsubject, rbody)

        return IncomingMessage(subject, body, reply, ack=ack,
                               ident=name)

    def _write_result(self, job_id, subject, body):
        rid = None
        m = _RESULT_ID_RE.search(subject or "")
        if m:
            rid = m.group(1)
        if not rid:
            rid = job_id or "unknown"
        rid = re.sub(r"[^A-Za-z0-9._-]", "_", rid)
        base = os.path.join(self.outbox_dir, f"{rid}.result.txt")
        path = base
        n = 2
        while os.path.exists(path):
            path = os.path.join(self.outbox_dir,
                                f"{rid}.result-{n}.txt")
            n += 1
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(format_envelope(subject, body))
            if body and not body.endswith("\n"):
                f.write("\n")
        os.replace(tmp, path)
        self.log(f"file transport: result for {rid} -> "
                 f"{os.path.basename(path)}")

    def close(self):
        pass


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
        parsed = urlparse(url or "nats://127.0.0.1:4222")
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 4222
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
        self.sock.settimeout(remaining)
        try:
            chunk = self.sock.recv(65536)
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
        try:
            self.sock.sendall(data)
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


class NatsTransport:
    """Core-NATS pub/sub: jobs in on one subject, results out on
    <result_subject_prefix>.<job_id>.

    The broker is a dumb pipe with no persistence: a job
    published while no runner is subscribed is gone, exactly
    like a shout in an empty room -- senders who need
    store-and-forward use email or the file transport. What
    at-least-once protection exists comes from the protocol
    layer: the runner's seen-set dedupes redeliveries, and a
    result the sender never saw can be re-requested by
    re-sending the job.

    One connection per poll cycle: connect, subscribe, drain
    what is waiting (until the wire stays quiet for
    drain_idle_sec), hand the messages to the core, publish the
    results over the same connection, disconnect. A connection
    that dies fails the cycle; the next poll reconnects.

    Two gates guard this transport: the broker's own
    authentication (a CONNECT user/password or token, from the
    transport_nats config keys or the URL userinfo, config keys
    winning) and the HMAC body signature the core checks. The
    credentials are required: with none configured the
    transport refuses to start unless
    transport_nats.allow_unauthenticated is explicitly true.
    """

    name = "nats"
    drain_idle_sec = 1.0

    def __init__(self, cfg, base_dir, log=None):
        block = _config_block(cfg, "transport_nats")
        self.url = str(block.get("url") or "nats://127.0.0.1:4222")
        self.subject = str(block.get("subject")
                           or "homing-pigeon.jobs")
        self.result_prefix = str(block.get("result_subject_prefix")
                                 or "homing-pigeon.results")
        self.log = log or _silent_log
        self.client = None
        self._user = block.get("user") or None
        self._password = block.get("password")
        self._token = block.get("token") or None
        parsed = urlparse(self.url)
        has_creds = bool(self._token or self._user
                         or parsed.username or parsed.password)
        allow_unauth = block.get("allow_unauthenticated") is True
        if not has_creds and not allow_unauth:
            raise TransportError(
                "nats transport refuses to start: no broker "
                "credentials configured (set transport_nats "
                "user/password or token, or embed them in the "
                "url) and allow_unauthenticated is not true; "
                "broker authentication is this transport's "
                "first authorization gate")
        if has_creds:
            _notice_once(
                "nats-two-gates", self.log,
                "nats transport: two authorization gates in "
                "force -- broker authentication, then the HMAC "
                "body signature")
        else:
            _notice_once(
                "nats-unauthenticated", self.log,
                "nats transport: allow_unauthenticated is set "
                "and no broker credentials are configured, so "
                "the HMAC body signature is the ONLY "
                "authorization gate on this transport", "WARN")

    def fetch(self):
        self.client = NatsClient(
            self.url, log=self.log, user=self._user,
            password=self._password,
            token=self._token).connect()
        self.client.subscribe(self.subject)
        out = []
        idle_deadline = time.monotonic() + self.drain_idle_sec
        while True:
            try:
                got = self.client.next_message(idle_deadline)
            except TransportError:
                if not out:
                    raise
                self.log("nats transport: connection lost "
                         "mid-drain; keeping what arrived", "WARN")
                break
            if got is None:
                break
            subject, payload = got
            idle_deadline = time.monotonic() + self.drain_idle_sec
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                self.log("nats transport: dropped a non-UTF-8 "
                         "message", "WARN")
                continue
            parsed = parse_envelope(text)
            if parsed is None:
                self.log("nats transport: dropped a malformed "
                         "envelope (no blank line)", "WARN")
                continue
            esubject, ebody = parsed
            out.append(IncomingMessage(
                esubject, ebody,
                reply=self._reply_for(esubject),
                ident=f"nats:{subject}"))
        return out

    def _reply_for(self, job_subject):
        m = _JOB_ID_RE.search(job_subject or "")
        job_id = m.group(1) if m else "unknown"
        target = f"{self.result_prefix}.{job_id}"

        def reply(subject, body):
            if self.client is None:
                raise TransportError("nats: connection closed "
                                     "before the result was sent")
            self.client.publish(
                target, format_envelope(subject, body))

        return reply

    def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None


# Names the runner services itself (the mail path predates the
# seam); every other name builds a transport object here.
_BUILDERS = {"file": FileTransport, "nats": NatsTransport}


def build_transport(name, cfg, base_dir, log=None):
    """A live transport object for a non-email name."""
    cls = _BUILDERS.get(name)
    if cls is None:
        raise ValueError(f"transport {name!r} is not a "
                         f"buildable pipe")
    return cls(cfg, base_dir, log=log)
