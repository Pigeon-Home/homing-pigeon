"""The email transport extension: the mailbox is the pipe.

This process owns the mailbox lifecycle -- IMAP connect, poll,
mark-seen, SMTP send -- and nothing else. Job handling stays
in the runner core: a fetched message's (subject, signed body)
crosses the channel as a job envelope, the core verifies and
executes, and the signed result comes back through the channel
for this process to send. The mailbox credentials live in this
extension's runtime config (the runner hands them over from
config.json); the core never opens the mailbox for the poll
loop any more.

Delivery discipline mirrors the pre-extension mail path:
  - a message is marked seen only after its result has been
    sent (or the delivery itself is acked in the channel);
  - a result that cannot be built into a message was not
    sent. It is set aside for the stub. Treating the failure
    as success moved the file and the mail never left;
  - a job whose channel file already sits in the channel's
    done/ was delivered before -- re-offering it would only
    duplicate work the runner already dedupes by seen-set, so
    it is marked seen and not re-delivered;
  - results are sent to the mailbox itself unless the job's
    signed body names a valid reply_to, exactly the routing
    the mail path has always applied. The core states that
    decision in a <ident>.target.txt sidecar beside the result
    (this process cannot read it out of an encrypted job, and
    never holds the secret); the in-body parse below remains
    the fallback for results that arrive without one.
  - a result held for a DTLS session that never returns
    expires: past its age bound (or the count / size bounds
    on held results) it is dropped with a log line, and it is
    never sent as ordinary mail -- dropping is not the
    downgrade the no-downgrade rule forbids. The hold is
    keyed by (session connection id, job ident), never by
    the submitter-chosen job ident alone, and it remembers
    the PSK identity the session authenticated under: the
    result leaves only inside that session, or inside a later
    session under the same identity that carries the same
    job ident again; a job with a held ident from a session
    under another identity is not delivered.
  - the DTLS cookie key is kept beside this channel's own
    state (dtls-cookie.key, owner-readable only), so a
    HelloRetryRequest answered on a later poll still validates
    after this process restarted. It is a secret of the
    responder, never derived from a mail session-id.
"""

import json
import os
import secrets as _secrets
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.dtls import __main__ as _dtls_ext  # noqa: E402
from runner.wire import dtls_mailbox as _dtls_mailbox  # noqa: E402
from runner.wire import dtlsproto as _dtlsproto  # noqa: E402
from runner.wire import mailbox as _mailbox  # noqa: E402
from runner.wire import subject as _subject  # noqa: E402
from runner.guard import confval as _confval  # noqa: E402
from runner.guard import atomicio as _atomicio  # noqa: E402

_mailbox.set_logger(ch.log)

# "Nothing is held for this ident": distinct from a hold whose
# session identity is unknown (None).
_NO_HOLD = object()


def _subject_body(raw):
    """(subject, text body) from one raw RFC822 message -- the
    same extraction the core applies to mail it handles: the
    Subject header, and the first text/plain part's text."""
    import email as _email
    msg = _email.message_from_bytes(raw)
    subject = str(msg["Subject"] or "")
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" \
                    and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    return subject, payload.decode(
                        "utf-8", errors="replace")
        return subject, ""
    payload = msg.get_payload(decode=True)
    if isinstance(payload, bytes):
        return subject, payload.decode("utf-8", errors="replace")
    return subject, msg.get_payload() or ""


def _permanent(exc):
    """A 5xx SMTP response (every recipient refused with 5xx
    included): retrying will not change it."""
    import smtplib
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [v[0] for v in (exc.recipients or {}).values()
                 if isinstance(v, (tuple, list)) and v]
        return bool(codes) and all(
            isinstance(c, int) and 500 <= c <= 599 for c in codes)
    if isinstance(exc, smtplib.SMTPResponseException):
        code = getattr(exc, "smtp_code", None)
        return isinstance(code, int) and 500 <= code <= 599
    return isinstance(exc, ch.PermanentDeliveryError)


def reply_target(body, mailbox_addr):
    """Where a result goes: the job's signed reply_to when it
    validates (the core's own rule, applied to the job object
    parsed out of the body), else the mailbox itself -- exactly
    the routing the mail path has always used. Only a single
    plain address from inside the signed body is honored, so a
    spoofed From header can never steer results."""
    job = None
    text = body or ""
    start = text.find("{")
    if start >= 0:
        try:
            job, _end = json.JSONDecoder().raw_decode(text[start:])
        except ValueError:
            job = None
    rt = _mailbox._valid_reply_to(job)
    return rt if rt else mailbox_addr


class EmailPipe:
    """One connection pair per pass: fetch, deliver, send the
    results that are ready, mark seen what is fully carried."""

    def __init__(self, cfg, channel_dir, imap_factory=None,
                 smtp_factory=None):
        self.cfg = cfg
        self.channel = channel_dir
        self._imap_factory = imap_factory or _mailbox.connect_imap
        self._smtp_factory = smtp_factory or _mailbox.connect_smtp
        self.mailbox_addr = _mailbox._mailbox(cfg)
        self._delivered = {}  # seq -> channel ident
        self._targets = {}    # channel ident -> result address
        # Version 3 carriage (docs/ietf/draft-slutsky-homing-
        # pigeon-v3-00.md): only the literal boolean true enables
        # it. The DTLS server core runs here, in the process that
        # owns the mailbox; the runner core stays the only job
        # gate, and a session's jobs cross the channel as
        # ordinary envelopes under their own job ids.
        self.dtls_enabled = isinstance(cfg, dict) \
            and cfg.get("dtls_via_email") is True
        self._dtls_server = None
        # (DTLS session CID, channel ident) -> the PSK identity
        # the session authenticated under. Keyed by the
        # connection id as well as the ident: a job ident is
        # chosen by the submitter and collides across
        # submitters, so it never keys a hold on its own. The
        # identity is who the hold belongs to: every hold for
        # one ident is the same identity's, and the result
        # leaves only inside a session under that identity.
        self._job_session = {}
        self._waiting_session = set()
        self._result_wait_since = {}  # (CID, ident) -> epoch
        ttl = cfg.get("dtls_result_ttl_sec") \
            if isinstance(cfg, dict) else None
        self._session_result_ttl = (
            float(ttl) if isinstance(ttl, (int, float))
            and not isinstance(ttl, bool) and ttl > 0
            else 7 * 86400.0)
        self._session_result_max_count = 64
        self._session_result_max_bytes = 16 * 1024 * 1024
        if self.dtls_enabled:
            self._load_session_holds()
            self._dtls_server = self._build_dtls_server()

    def _build_dtls_server(self):
        if not self.cfg.get("shared_secret") \
                and not self.cfg.get("additional_secrets"):
            ch.log("email transport: dtls_via_email is on but "
                   "no shared_secret was handed over; the "
                   "shared secret is the DTLS PSK -- there is "
                   "nothing to authenticate with, so DTLS mail "
                   "is refused", "ERROR")
            return None
        tier = _dtls_ext.greeting_tier(self.cfg)
        lookup = _dtls_ext.directory_lookup(
            self.cfg,
            _dtlsproto.make_secret_lookup(
                self.cfg.get("shared_secret"),
                self.cfg.get("additional_secrets")),
            log=ch.log)
        server = _dtls_mailbox.DtlsMailServer(
            secret_lookup=lookup,
            platform_payload=_dtls_ext.build_platform_payload(
                tier, self.cfg),
            log=ch.log)
        key = self._cookie_key()
        if key is not None:
            server.core.cookie_secret = key
        return server

    def _cookie_key(self):
        """The responder's cookie key, kept across restarts of
        this process. On this carriage a HelloRetryRequest is
        answered on a later poll -- an hour later on a slow
        poller, and after a deploy or a crash often enough --
        and a key drawn per process would fail every cookied
        hello that crossed the restart. The key lives beside
        the channel's own state, created once with 32 random
        bytes, owner-readable only, and is never derived from
        anything a message asserts. When the file cannot be
        kept, the per-process key stands and a log line says
        so."""
        path = os.path.join(self.channel, "dtls-cookie.key")
        try:
            with open(path, "rb") as f:
                raw = f.read().strip()
            key = bytes.fromhex(raw.decode("ascii"))
            if len(key) == 32:
                return key
            ch.log("email transport: dtls-cookie.key is not 32 "
                   "bytes; drawing a fresh cookie key", "WARN")
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            ch.log(f"email transport: cannot read dtls-cookie.key "
                   f"({e}); drawing a fresh cookie key", "WARN")
        key = _secrets.token_bytes(32)
        try:
            os.makedirs(self.channel, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                         0o600)
            with os.fdopen(fd, "w", encoding="ascii") as f:
                f.write(key.hex() + "\n")
        except OSError as e:
            ch.log(f"email transport: cannot keep dtls-cookie.key "
                   f"({e}); the cookie key lives for this process "
                   f"only, and a restart abandons attempts in "
                   f"flight", "WARN")
        return key

    # -- version 3 DTLS carriage --------------------------------

    def _send_dtls_mails(self, mails):
        if not mails:
            return
        smtp = self._smtp_factory(self.cfg)
        try:
            for subject, body in mails:
                _mailbox.send_built_message(
                    smtp, _dtls_mailbox.build_flight_message(
                        self.cfg, subject, body))
        finally:
            try:
                smtp.quit()
            except Exception:
                pass

    def _handle_dtls_mail(self, imap, seq, classified):
        """One DTLS-classified message: fed to the DTLS engine,
        never delivered as a job. The message is consumed --
        marked seen -- whether the engine answered, the flight
        is still incomplete, or the input was malformed: it was
        DTLS input or nothing, and failing closed means it is
        never reinterpreted as a job on a later pass."""
        server = self._dtls_server
        if server is None:
            ch.log("email transport: DTLS mail refused; no "
                   "DTLS server is running", "WARN")
        elif classified.session_id is None and classified.kind in (
                "dtls", "dtls-init"):
            # The unaddressed harness shape has no mail
            # session-id. It is a test-harness input, not a
            # flight a deployment mailbox feeds to DTLS.
            ch.log("email transport: unaddressed DTLS mail "
                   "is not a flight on this mailbox; dropped",
                   "WARN")
        else:
            responses = server.receive_classified(
                classified, time.time())
            self._send_dtls_mails(responses)
            self._drain_dtls_apps()
        _mailbox.mark_seen(imap, seq)

    def _dtls_tick(self):
        server = self._dtls_server
        if server is None:
            return
        self._send_dtls_mails(server.tick_mails(time.time()))
        self._drain_dtls_apps()

    def _drain_dtls_apps(self):
        server = self._dtls_server
        if server is None:
            return
        for _hint, cid, message in server.drain_app_messages():
            try:
                text = message.decode("utf-8")
            except UnicodeDecodeError:
                ch.log("email transport: DTLS application "
                       "message is not UTF-8; dropped", "WARN")
                continue
            parsed = ch.parse_envelope(text)
            if parsed is None:
                ch.log("email transport: DTLS application "
                       "message is not an envelope; dropped",
                       "WARN")
                continue
            subject, body = parsed
            m = _subject.JOB_ID_RE.search(subject or "")
            ident = m.group(1) if m else None
            if not ident:
                ch.log("email transport: DTLS application "
                       "message carries no job id in its "
                       "subject; dropped", "WARN")
                continue
            identity = self._session_identity(cid)
            owner = self._hold_owner(ident)
            if owner is not _NO_HOLD and owner != identity:
                # The ident is held for another identity's job.
                # Delivering this one would rewrite that job's
                # inbox file or route that job's result into
                # this session; the hold belongs to the
                # submitter whose job it was.
                ch.log(f"email transport: job {ident} from a "
                       f"DTLS session is an ident another key's "
                       f"session already carries; dropped", "WARN")
                continue
            ch.deliver_job(self.channel, ident, subject, body)
            self._job_session[(cid, ident)] = identity
            self._remember_session_hold(cid, ident, identity)
            ch.log(f"email transport: job {ident} delivered "
                   f"from a DTLS session to the runner core")

    def _session_identity(self, cid):
        """The key identity behind a live session: the PSK
        identity of a full handshake, or the issuing key's
        identity behind a resumed one. None for a session the
        core no longer holds."""
        server = self._dtls_server
        session = server.core.sessions.get(cid) if server else None
        if session is None:
            return None
        issuer = getattr(session, "issuer", None)
        return issuer if issuer is not None \
            else getattr(session, "identity", None)

    def _hold_owner(self, ident):
        """The PSK identity every hold for this ident belongs
        to, or _NO_HOLD when nothing is held for it."""
        for key, identity in self._job_session.items():
            if key[1] == ident:
                return identity
        return _NO_HOLD

    def _safe_ident(self, ident):
        safe = "".join(
            c if (c.isalnum() or c in "._-") else "_"
            for c in str(ident))[:128]
        return safe or "job"

    def _encode_hold_token(self, value):
        if value is None:
            return "none"
        if isinstance(value, (bytes, bytearray)):
            return "b:" + bytes(value).hex()
        return "s:" + str(value)

    def _decode_hold_token(self, text):
        if text == "none":
            return None
        if text.startswith("b:"):
            return bytes.fromhex(text[2:])
        if text.startswith("s:"):
            return text[2:]
        return text

    def _session_hold_path(self, ident, *folders):
        return os.path.join(
            self.channel, *folders,
            self._safe_ident(ident) + ".session.txt")

    def _write_session_hold(self, path, cid, ident, identity, since):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        text = (
            "cid %s\nidentity %s\nsince %s\n"
            % (self._encode_hold_token(cid),
               self._encode_hold_token(identity),
               since))
        _atomicio.write_text(path, text)

    def _read_session_hold(self, path):
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except OSError:
            return None
        fields = {}
        for line in lines:
            key, _sep, value = line.partition(" ")
            fields[key] = value
        if "cid" not in fields or "identity" not in fields:
            return None
        try:
            since = float(fields.get("since") or "0")
        except ValueError:
            since = 0.0
        return (self._decode_hold_token(fields["cid"]),
                self._decode_hold_token(fields["identity"]),
                since)

    def _remember_session_hold(self, cid, ident, identity, since=None):
        """The hold has to outlive this process. The result file
        does; a dictionary does not. A restart that forgot the
        hold sent the result as ordinary mail, which Section 12
        forbids. The sidecar is not a secret: a connection id
        and a key id are routing facts."""
        when = time.time() if since is None else since
        path = self._session_hold_path(ident, "inbox")
        self._write_session_hold(path, cid, ident, identity, when)

    def _load_session_holds(self):
        found = {}
        for folders in (("inbox",), ("inbox", "done"), ("outbox",)):
            directory = os.path.join(self.channel, *folders)
            try:
                names = os.listdir(directory)
            except OSError:
                continue
            for name in names:
                if not name.endswith(".session.txt"):
                    continue
                ident = name[:-len(".session.txt")]
                parsed = self._read_session_hold(
                    os.path.join(directory, name))
                if parsed is None:
                    continue
                # The outbox copy, once a result exists, wins
                # over the inbox copy the delivery wrote.
                if ident not in found or folders == ("outbox",):
                    found[ident] = parsed
        for ident, (cid, identity, since) in found.items():
            self._job_session[(cid, ident)] = identity
            self._result_wait_since.setdefault((cid, ident), since)

    def _retire_session_hold(self, ident):
        """The result left, or it expired. The hold leaves with
        it. A copy left in the inbox would make the next
        process treat a later ordinary result as session-bound,
        or the reverse once the outbox copy was gone."""
        for folders in (("inbox",), ("inbox", "done"), ("outbox",)):
            src = self._session_hold_path(ident, *folders)
            if not os.path.exists(src):
                continue
            dest = os.path.join(
                self.channel, "outbox", "done",
                self._safe_ident(ident) + ".session.txt")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                os.replace(src, dest)
            except OSError as e:
                ch.log(f"email transport: cannot retire the "
                       f"session hold for {ident}: {e}", "WARN")

    def _session_bound(self, ident):
        return any(key[1] == ident for key in self._job_session)

    def _send_result_on_session(self, ident, subject, body):
        """Send one result inside the session that carried its
        job, or inside a later session under the same PSK
        identity that carried the same ident again. False when
        neither exists: the file stays in the outbox (bounded
        by the expiry sweep below), and the result is never
        downgraded to an ordinary mail result and never sent
        into a session under another identity."""
        server = self._dtls_server
        keys = [key for key in self._job_session
                if key[1] == ident]
        if server is None or not keys:
            return False
        owner = self._job_session[keys[0]]
        keys = [key for key in keys
                if self._job_session[key] == owner]
        text = ch.envelope(subject, body)
        if body and not body.endswith("\n"):
            text += "\n"
        for key in keys:
            if self._session_identity(key[0]) != owner:
                continue
            mails = server.send_app_mails(
                key[0], text.encode("utf-8"))
            if mails:
                self._waiting_session.discard(ident)
                self._send_dtls_mails(mails)
                ch.log(f"email transport: result for {ident} "
                       f"sent inside its DTLS session")
                return True
        now = time.time()
        for key in keys:
            self._result_wait_since.setdefault(key, now)
        if ident not in self._waiting_session:
            ch.log(f"email transport: result for {ident} "
                   f"is not on a session yet; it stays "
                   f"until the peer is back", "WARN")
            self._waiting_session.add(ident)
        return False

    def _expire_session_results(self):
        """Drop held session results that outlived their
        bounds: older than the pending-result TTL, or beyond
        the count / total-size bounds on held results (oldest
        first). An expired result is acked into done and
        logged. It is never sent -- expiry is not the
        downgrade Section 12 forbids; sending it as ordinary
        mail would be."""
        if not self.dtls_enabled or not self._job_session:
            return
        now = time.time()
        held = []   # (since, fname, ident, size in bytes)
        for fname, _subject, body in ch.pending_results(
                self.channel):
            ident = ch.result_file_id(fname) or fname
            keys = [key for key in self._job_session
                    if key[1] == ident]
            if not keys:
                continue
            since = min(
                (self._result_wait_since.get(key, now)
                 for key in keys), default=now)
            held.append((since, fname, ident,
                         len((body or "").encode("utf-8"))))
        if not held:
            return
        held.sort()
        doomed = []
        remaining = []
        for since, fname, ident, size in held:
            if now - since > self._session_result_ttl:
                doomed.append((fname, ident, "its age bound"))
            else:
                remaining.append((since, fname, ident, size))
        total = sum(entry[3] for entry in remaining)
        while len(remaining) > self._session_result_max_count \
                or total > self._session_result_max_bytes:
            _since, fname, ident, size = remaining.pop(0)
            doomed.append((fname, ident, "the held-result "
                                        "bounds"))
            total -= size
        if not doomed:
            return
        doomed_idents = {ident for _fname, ident, _why in doomed}
        still = {entry[2] for entry in remaining}
        for fname, ident, why in doomed:
            ch.ack_result(self.channel, fname)
            self._ack_sidecar(ident)
            ch.log(f"email transport: session result for "
                   f"{ident} expired past {why}; dropped, "
                   f"not sent", "WARN")
        # Forget only the holds whose result was just dropped.
        # A hold with no result file yet is a job still in
        # flight; pruning by "not in the surviving files"
        # deleted those and the next flush sent them as
        # ordinary mail.
        for ident in doomed_idents - still:
            for key in list(self._job_session):
                if key[1] == ident:
                    del self._job_session[key]
                    self._result_wait_since.pop(key, None)
            self._waiting_session.discard(ident)
            self._retire_session_hold(ident)

    def pass_once(self):
        imap = self._imap_factory(self.cfg)
        try:
            mails = _mailbox.fetch_job_mails(imap)
            for seq, raw in mails:
                if self.dtls_enabled:
                    classified = _dtls_mailbox.parse_message(raw)
                    if classified.kind in (
                            "dtls", "dtls-init", "dtls-part",
                            "dtls-invalid"):
                        self._handle_dtls_mail(
                            imap, seq, classified)
                        continue
                subject, body = _subject_body(raw)
                ident = f"mail-{seq}"
                done = os.path.join(
                    self.channel, "inbox", "done",
                    ident + ".job.txt")
                if os.path.exists(done):
                    # Already carried once. Mark seen -- unless a
                    # result for it is still in the outbox, including
                    # a suffixed name (mail-1.result-2.txt). That
                    # file does not end in .result.txt, and looking
                    # only for the primary marked the mail seen
                    # while the result was still here.
                    if not self._result_waiting(ident):
                        _mailbox.mark_seen(imap, seq)
                    continue
                ch.deliver_job(self.channel, ident, subject, body)
                self._delivered[seq] = ident
                # The result's destination is decided by the
                # JOB's signed reply_to, which the result body
                # does not carry -- remember it from delivery.
                self._targets[ident] = reply_target(
                    body, self.mailbox_addr)
            if self.dtls_enabled:
                self._dtls_tick()
            self.flush_results(imap)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def _result_waiting(self, ident, ignore=None):
        """True when some result file for this ident is still in
        the outbox. A suffixed name counts. `ignore` is the file
        this pass is already sending."""
        outbox = os.path.join(self.channel, "outbox")
        try:
            names = os.listdir(outbox)
        except OSError:
            return False
        return any(n != ignore and ch.result_file_id(n) == ident
                   for n in names)

    def _sidecar_path(self, ident):
        return os.path.join(self.channel, "outbox",
                            ident + ".target.txt")

    def _sidecar_target(self, ident):
        """The core's routing decision for one result, when it
        left one: the <ident>.target.txt beside the result file
        carries the job's validated reply_to, which an encrypted
        job's envelope does not show this process. The value
        faces the core's own address rule again before it is
        used; anything that does not pass is ignored, never
        honored."""
        try:
            with open(self._sidecar_path(ident),
                      encoding="utf-8") as f:
                raw = f.read().strip()
        except OSError:
            return None
        return _mailbox._valid_reply_to({"reply_to": raw})

    def _ack_sidecar(self, ident):
        """Move a result's sidecar into outbox/done/ beside the
        result itself, mirroring ack_result's lifecycle: acks
        are moves in this channel, and no orphan is left."""
        src = self._sidecar_path(ident)
        if not os.path.exists(src):
            return
        # A sibling result for this ident is still in the outbox.
        # It reads the same sidecar. Moving it now would send that
        # one to the mailbox instead of the address the core named.
        if self._result_waiting(ident):
            return
        try:
            os.replace(src, os.path.join(
                self.channel, "outbox", "done",
                ident + ".target.txt"))
        except OSError as e:
            ch.log(f"email transport: cannot move sidecar for "
                   f"{ident} to done: {e}", "WARN")

    def flush_results(self, imap):
        pending = ch.pending_results(self.channel)
        if not pending:
            return
        smtp = self._smtp_factory(self.cfg)
        try:
            for fname, subject, body in pending:
                ident = ch.result_file_id(fname) or fname
                if self.dtls_enabled \
                        and self._session_bound(ident):
                    # A session's result is session-bound: it
                    # goes out inside the session or it stays.
                    if self._send_result_on_session(
                            ident, subject, body):
                        ch.ack_result(self.channel, fname)
                        self._ack_sidecar(ident)
                        self._retire_session_hold(ident)
                        for key in list(
                                self._result_wait_since):
                            if key[1] == ident:
                                del self._result_wait_since[key]
                    continue
                to = self._sidecar_target(ident)
                waiting = self._result_waiting(ident, ignore=fname)
                if to is None:
                    if waiting:
                        to = self._targets.get(ident, self.mailbox_addr)
                    else:
                        to = self._targets.pop(ident, self.mailbox_addr)
                elif not waiting:
                    self._targets.pop(ident, None)
                try:
                    _mailbox.send_mail(smtp, self.cfg, subject, body,
                                       to=to)
                except Exception as e:
                    if not _permanent(e):
                        raise   # the server, not the message: next pass
                    # Refused for good (552 and the rest of 5xx): this
                    # result is set aside for the runner's stub and the
                    # queue behind it keeps moving (review item 4).
                    ch.refuse_result(self.channel, fname, e)
                    self._ack_sidecar(ident)
                    if self._result_waiting(ident):
                        continue
                    for seq, dident in list(self._delivered.items()):
                        if dident == ident:
                            _mailbox.mark_seen(imap, seq)
                            del self._delivered[seq]
                    continue
                ch.ack_result(self.channel, fname)
                self._ack_sidecar(ident)
                if self._result_waiting(ident):
                    continue
                for seq, dident in list(self._delivered.items()):
                    if dident == ident:
                        _mailbox.mark_seen(imap, seq)
                        del self._delivered[seq]
            self._expire_session_results()
        finally:
            try:
                smtp.quit()
            except Exception:
                pass

    def run(self):
        # FAQ.md: poll_interval_sec default 20. A usable number
        # is floored at 1s; a boolean, a huge integer (once a raw
        # OverflowError out of this loop), infinity or NaN is not an
        # interval and polls at the documented default.
        interval = max(1.0, float(_confval.number(
            self.cfg.get("poll_interval_sec"), 20.0, lo=0)))
        ch.log(f"email transport: polling "
               f"{self.mailbox_addr or 'mailbox'} every "
               f"{interval:.0f}s")
        while True:
            try:
                self.pass_once()
            except Exception as e:  # a dead connection fails the
                # pass; the next pass reconnects. Nothing here
                # may take the runner down with it.
                ch.log(f"email transport: pass failed: {e!r}",
                       "WARN")
            ch.nap(interval)


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    channel_dir, cfg = ch.load_runtime_config(argv)
    if not channel_dir:
        ch.log("email transport: no channel directory given",
               "ERROR")
        return 2
    EmailPipe(cfg, channel_dir).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
