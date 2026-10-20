"""The DTLS transport extension: a direct DTLS 1.3 session
binding (a binding of protocol version 1).

Config (handed over by the runner):
    transport_dtls block:
        port    UDP port to listen on (default 20220)
        bind    local address to bind (default "0.0.0.0" --
                this transport LISTENS, unlike the others;
                it is off unless enabled in `transports`)
    dtls_greeting (top-level runner key, handed over for this
    extension): the greeting disclosure tier --
        none / family (default) / standard / full
    shared_secret, additional_secrets: handed over ONLY to
    this extension, because this pipe does not merely carry
    envelopes -- it terminates DTLS-PSK authentication with
    the secret itself. With no secret handed over the
    extension refuses to start: there is nothing to
    authenticate with.

The session profile lives in runner/dtlsproto.py: DTLS 1.3,
one ciphersuite, PSK-only, psk_dhe_ke only (perfect forward
secrecy is enforced, never negotiated away), a stateless
cookie exchange before any state exists, Connection IDs so a
NAT rebinding keeps the session. The handshake authenticates
the peer; the job inside still faces the runner core's HMAC
verification like every other transport's jobs -- channel
security is a second gate, not a replacement, and channel
security is not delivery (ack/dedup stays the protocol's
seen-set, in the core).

After the handshake completes -- post-authentication, never
before -- the runner side sends the session's first
application message: the greeting, tiered by dtls_greeting.
The SI initiates the session; the responder chooses what it
discloses; the client cannot widen it. Jobs are accepted
only on established sessions, which is to say only after the
greeting has been sent.

Results are session-bound: a result that lands after its
session is gone cannot be delivered on it, so it is logged
loudly and acked into done/ -- the SI re-asks on a fresh
session and the protocol's seen-set dedups the repeat.
"""

import json
import os
import platform
import re
import select
import shutil
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from runner import dtlsproto  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402

DEFAULT_PORT = 20220
GREETING_TIERS = ("none", "family", "standard", "full")
_PATH_TOOLS = ("sh", "bash", "powershell", "pwsh", "python3",
               "python", "curl", "git", "tar")
_JOB_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)", re.I)


def _os_family():
    p = sys.platform
    if p.startswith("win"):
        return "windows"
    if p == "darwin":
        return "macos"
    if p.startswith("linux"):
        return "linux"
    return "other"


def build_greeting(tier):
    """The greeting application message for a disclosure tier,
    as bytes. The object always goes out (it is the session's
    first application message at every tier); `tier` decides
    how much platform information rides in it."""
    obj = {"type": "greeting", "transport": "dtls", "v": 1,
           "disclosure": tier}
    if tier != "none":
        plat = {"os_family": _os_family()}
        if tier in ("standard", "full"):
            plat["os_release"] = platform.release()
            plat["python_version"] = platform.python_version()
        if tier == "full":
            plat["path_tools"] = {
                name: bool(shutil.which(name))
                for name in _PATH_TOOLS}
        obj["platform"] = plat
    return (json.dumps(obj, sort_keys=True) + "\n").encode("utf-8")


class DtlsPipe:
    """One UDP listener, one DtlsServerCore, one channel."""

    def __init__(self, cfg, channel_dir):
        self.cfg = cfg
        self.channel = channel_dir
        self.tier = cfg.get("dtls_greeting", "family")
        port = cfg.get("port", DEFAULT_PORT)
        self.port = int(port)
        self.bind = str(cfg.get("bind", "0.0.0.0"))
        lookup = dtlsproto.make_secret_lookup(
            cfg.get("shared_secret"), cfg.get("additional_secrets"))
        self.core = dtlsproto.DtlsServerCore(
            secret_lookup=lookup,
            greeting_for=lambda session: build_greeting(self.tier),
            log=ch.log)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.bind, self.port))
        self.sock.setblocking(False)
        self.job_session = {}        # job ident -> session id

    # -- one pass -----------------------------------------------------

    def run_once(self, now=None):
        now = time.monotonic() if now is None else now
        try:
            ready, _, _ = select.select([self.sock], [], [], 0.1)
        except (OSError, ValueError):
            ready = []
        if ready:
            try:
                data, addr = self.sock.recvfrom(65535)
            except OSError:
                data = None
            if data:
                for dg in self.core.feed(data, addr, now):
                    self._send(dg, addr)
        for addr, dg in self.core.tick(now):
            self._send(dg, addr)
        self._drain_events()
        self._pump_results()

    def _send(self, datagram, addr):
        try:
            self.sock.sendto(datagram, addr)
        except OSError as e:
            ch.log(f"dtls transport: send to {addr} failed: {e}",
                   "WARN")

    def _drain_events(self):
        events, self.core.events = self.core.events, []
        for event in events:
            if event[0] == "established":
                info = event[2]
                ch.log(f"dtls transport: session established "
                       f"with {info.get('addr')} "
                       f"(identity {info.get('identity')!r}, "
                       f"resumed={info.get('resumed')}); greeting "
                       f"sent at tier {self.tier}")
            elif event[0] == "app":
                self._on_job(event[1], event[2])

    def _on_job(self, session_id, message):
        try:
            text = message.decode("utf-8")
        except UnicodeDecodeError:
            ch.log("dtls transport: job message is not UTF-8; "
                   "dropped", "WARN")
            return
        parsed = ch.parse_envelope(text)
        if parsed is None:
            ch.log("dtls transport: job message is not an "
                   "envelope; dropped", "WARN")
            return
        subject, body = parsed
        m = _JOB_ID_RE.search(subject or "")
        ident = m.group(1) if m else None
        if not ident:
            ch.log("dtls transport: job envelope carries no job "
                   "id in its subject; dropped", "WARN")
            return
        ch.deliver_job(self.channel, ident, subject, body)
        self.job_session[ident] = session_id
        ch.log(f"dtls transport: job {ident} delivered to the "
               "runner core")

    def _pump_results(self):
        for fname, subject, body in ch.pending_results(
                self.channel):
            ident = fname[:-len(".result.txt")] \
                if fname.endswith(".result.txt") else fname
            session_id = self.job_session.get(ident)
            text = ch.envelope(subject, body)
            if body and not body.endswith("\n"):
                text += "\n"
            sent = []
            if session_id is not None:
                sent = self.core.send_app(
                    session_id, text.encode("utf-8"))
            if not sent:
                ch.log(f"dtls transport: result for {ident} "
                       "cannot be delivered -- its session is "
                       "gone; acking it into done (the sender "
                       "re-asks on a fresh session and the "
                       "seen-set dedups)", "WARN")
                ch.ack_result(self.channel, fname)
                continue
            for addr, dg in sent:
                self._send(dg, addr)
            ch.ack_result(self.channel, fname)
            ch.log(f"dtls transport: result for {ident} sent")


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    channel_dir, cfg = ch.load_runtime_config(argv)
    if not channel_dir:
        ch.log("dtls transport: no channel directory given",
               "ERROR")
        return 2
    if not cfg.get("shared_secret"):
        ch.log("dtls transport: no shared_secret was handed "
               "over; the shared secret is this transport's "
               "PSK -- there is nothing to authenticate with, "
               "so the extension will not start", "ERROR")
        return 2
    tier = cfg.get("dtls_greeting", "family")
    if not isinstance(tier, str) or tier not in GREETING_TIERS:
        ch.log(f"dtls transport: dtls_greeting must be one of "
               f"{GREETING_TIERS}, not {tier!r}", "ERROR")
        return 2
    try:
        pipe = DtlsPipe(cfg, channel_dir)
    except (OSError, TypeError, ValueError) as e:
        ch.log(f"dtls transport: cannot listen: {e!r}", "ERROR")
        return 2
    ch.log(f"dtls transport: listening on udp "
           f"{pipe.bind}:{pipe.port}; greeting tier {tier}")
    while True:
        try:
            pipe.run_once()
        except Exception as e:  # a session must never kill it
            ch.log(f"dtls transport: pass failed: {e!r}", "ERROR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
