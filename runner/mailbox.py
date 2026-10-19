#!/usr/bin/env python3
"""Mailbox client library: IMAP/SMTP connections and message IO.

This is the email pipe's shared library. The email transport
extension (runner/transport_extensions/email/) owns the mailbox
lifecycle -- connect, poll, mark seen, send -- and drives these
functions from its own process. The runner core does not poll a
mailbox in its poll loop any more; it re-exports these names
because the diagnostic harness and local SI test still open a
mailbox directly for their own round-trips.

Stdlib only. The module-level `log` is a stderr fallback; the
runner replaces it with its own log at startup, and the email
extension replaces it with its channel log.

TLS posture: the protocol draft's Transport Binding requires
IMAP and SMTP over TLS 1.2 or higher, with the peer certificate
verified. The runner expresses that requirement as the
`mail_tls_required` config option (see mail_tls_required()
below): required by default, with an explicit, logged escape
hatch -- never a cleartext path.
"""

import base64
import imaplib
import re
import smtplib
import ssl
import sys
import threading
from email.message import EmailMessage

_MAIL_LOCK = threading.RLock()


def log(msg, level="INFO"):
    print(f"{level}: {msg}", file=sys.stderr, flush=True)


def set_logger(fn):
    global log
    log = fn


def _load_oauth():
    import importlib
    try:
        return importlib.import_module("runner.oauth")
    except ImportError:
        return importlib.import_module("oauth")


def _use_oauth(cfg) -> bool:
    return str(cfg.get("auth") or "password").lower() == "oauth"


def _xoauth2_raw(cfg) -> str:
    oauth = _load_oauth()
    return oauth.xoauth2_raw(cfg["mailbox_user"], oauth.refresh_access_token(cfg))


def _imap_xoauth2(conn, user: str, raw: str) -> None:
    # Gmail requires the SASL initial response on the AUTHENTICATE line.
    # imaplib.authenticate() sends a bare AUTHENTICATE and waits for a
    # challenge; Gmail answers BAD "Invalid SASL argument". Send it ourselves.
    blob = base64.b64encode(raw.encode("ascii"))
    tag = conn._new_tag()
    conn.send(tag + b" AUTHENTICATE XOAUTH2 " + blob + b"\r\n")
    typ, dat = conn._get_tagged_response(tag)
    if typ != "OK":
        raise imaplib.IMAP4.error("IMAP XOAUTH2 failed: %s %s" % (typ, dat))
    # Bypassed authenticate(), so the state machine still says NONAUTH.
    conn.state = "AUTH"


def _port(cfg, key, default):
    """A missing or non-numeric port is a config error, not a crash."""
    if not isinstance(cfg, dict):
        raise RuntimeError("config error: config is not an object")
    try:
        return int(cfg.get(key, default))
    except (TypeError, ValueError, OverflowError):
        raise RuntimeError("config error: " + key + " must be a number")


def _host(cfg, key):
    """A missing or non-string host is a config error, not a KeyError."""
    if not isinstance(cfg, dict):
        raise RuntimeError("config error: config is not an object")
    host = cfg.get(key)
    if not isinstance(host, str) or not host.strip():
        raise RuntimeError("config error: " + key + " must be a host name")
    host = host.strip()
    if any(c.isspace() or c == "\x00" for c in host):
        raise RuntimeError("config error: " + key + " must not contain whitespace")
    return host


def _mailbox(cfg):
    """A missing user is a config error, not a KeyError mid-poll."""
    if not isinstance(cfg, dict):
        raise RuntimeError("config error: config is not an object")
    user = cfg.get("mailbox_user")
    if not isinstance(user, str) or not user.strip():
        raise RuntimeError("config error: mailbox_user must be set")
    return user.strip()


def mail_tls_required(cfg) -> bool:
    """Whether this installation requires verified TLS on the
    mailbox connections.

    The draft's Transport Binding makes TLS a MUST: IMAP and
    SMTP over TLS 1.2 or higher, the peer certificate verified.
    `mail_tls_required` is that requirement expressed as a
    runner option whose default requires it. Only the literal
    boolean false opens the escape hatch -- the same
    literal-boolean discipline the NATS gate applies with
    `is True`. An absent key, a string "false", 0, or any other
    value keeps the requirement.
    """
    if not isinstance(cfg, dict):
        return True
    return cfg.get("mail_tls_required") is not False


# TLS <= 1.2 suites for the required posture: ephemeral
# Diffie-Hellman key exchange only, AEAD only. TLS 1.3 suites
# are forward-secret by construction and are NOT governed by
# set_ciphers (they ride along untouched); what this string
# pins is the 1.2 floor's key exchange, where static-RSA
# suites would otherwise still be negotiable.
_ECDHE_CIPHERS = (
    "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
    "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
    "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305")

_PFS_PIN_WARNED = False


def _verified_tls_context() -> ssl.SSLContext:
    """A context that actually verifies: the system trust store,
    hostname checking, and a TLS 1.2 floor -- the floor the
    draft states, stated in the code as well. The 1.2 suites
    are pinned to ECDHE key exchange so a required-posture
    session is forward-secret on either protocol version.
    A platform whose OpenSSL rejects the pin keeps the
    default suites instead: the connection never fails over
    the cipher policy, but the shortfall is logged."""
    global _PFS_PIN_WARNED
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.set_ciphers(_ECDHE_CIPHERS)
    except ssl.SSLError as e:
        if not _PFS_PIN_WARNED:
            _PFS_PIN_WARNED = True
            log("could not pin TLS 1.2 cipher suites to ECDHE "
                f"({e}); continuing with the default suites -- "
                "forward secrecy is not guaranteed on TLS 1.2 "
                "mail-hop connections on this platform.", "WARN")
    return ctx


_TLS_HATCH_WARNED = False


def _note_tls_hatch(cfg) -> None:
    """Log, once per process, that the owner opened the hatch.

    The hatch relaxes verification to the posture that predates
    this option (STARTTLS attempted, certificate unverified).
    It must never be silent, and it never adds a cleartext path:
    IMAP stays implicit-TLS and SMTP still upgrades, in both
    modes.
    """
    global _TLS_HATCH_WARNED
    if _TLS_HATCH_WARNED or mail_tls_required(cfg):
        return
    _TLS_HATCH_WARNED = True
    log("mail TLS is not required by owner configuration "
        "(mail_tls_required: false): STARTTLS proceeds without "
        "certificate verification. This installation cannot "
        "claim the draft's confidentiality posture.", "WARN")


def connect_imap(cfg) -> imaplib.IMAP4_SSL:
    _note_tls_hatch(cfg)
    # IMAP is implicit TLS in both modes -- there is no plaintext
    # constructor path. Required mode additionally hands the
    # connection a verifying context with the TLS 1.2 floor
    # instead of the stdlib's unverified default context.
    ctx = _verified_tls_context() if mail_tls_required(cfg) \
        else None
    conn = imaplib.IMAP4_SSL(
        _host(cfg, "imap_host"), _port(cfg, "imap_port", 993),
        ssl_context=ctx, timeout=30)
    user = _mailbox(cfg)
    if _use_oauth(cfg):
        _imap_xoauth2(conn, user, _xoauth2_raw(cfg))
    else:
        # Password travels inside LOGIN, but only over the TLS session.
        # It is never logged or written anywhere.
        password = cfg.get("mailbox_password")
        if not isinstance(password, str):
            raise RuntimeError("config error: mailbox_password must be a string")
        conn.login(user, password)
    typ, _ = conn.select("INBOX")
    if typ != "OK":
        raise RuntimeError("IMAP SELECT INBOX failed")
    return conn


def connect_smtp(cfg) -> smtplib.SMTP:
    _note_tls_hatch(cfg)
    smtp = smtplib.SMTP(
        _host(cfg, "smtp_host"), _port(cfg, "smtp_port", 587),
        timeout=30)
    if mail_tls_required(cfg):
        # A verifying context, not smtplib's default: bare
        # starttls() encrypts but never checks the peer
        # certificate. A refused or unavailable STARTTLS raises
        # here and the connection fails -- required means
        # required, never an opportunistic downgrade.
        smtp.starttls(context=_verified_tls_context())
    else:
        smtp.starttls()
    if _use_oauth(cfg):
        # smtplib.auth base64-encodes the return value, and calls the
        # callback with no args for the initial response. Return the raw
        # string. A lambda that requires an argument crashes here.
        raw = _xoauth2_raw(cfg)
        smtp.auth("XOAUTH2", lambda challenge=None: raw)
    else:
        password = cfg.get("mailbox_password")
        if not isinstance(password, str):
            raise RuntimeError("config error: mailbox_password must be a string")
        smtp.login(_mailbox(cfg), password)
    return smtp


def fetch_job_mails(imap):
    """Return [(seq, raw_bytes)] for unseen mails with the job subject prefix.

    A bad SEARCH or one bad FETCH is skipped. The rest of the poll
    still runs.
    """
    # Search broad: the subject regex accepts decorated subjects
    # ("[HOMING-PIGEON] TEST job <id>", "Re: ..."), which do not contain
    # the exact "[HOMING-PIGEON] job" substring. handle_mail filters.
    try:
        typ, data = imap.search(None, "UNSEEN", "SUBJECT", '"[HOMING-PIGEON]"')
    except Exception as e:
        log(f"IMAP SEARCH failed: {e}", "WARN")
        return []
    if typ != "OK":
        log("IMAP SEARCH failed", "WARN")
        return []
    if not isinstance(data, (list, tuple)) or not data:
        return []
    blob = data[0]
    if blob is None:
        return []
    if isinstance(blob, str):
        blob = blob.encode("ascii", "replace")
    if not isinstance(blob, (bytes, bytearray)):
        log(f"IMAP SEARCH returned {type(blob).__name__}; ignoring", "WARN")
        return []
    mails = []
    for num in blob.split():
        try:
            seq = num.decode("ascii") \
                if isinstance(num, (bytes, bytearray)) else str(num)
        except Exception:
            continue
        try:
            typ, fetched = imap.fetch(num, "(RFC822)")
        except Exception as e:
            log(f"IMAP FETCH {seq} failed: {e}", "WARN")
            continue
        if typ != "OK" or not fetched:
            continue
        raw = None
        try:
            parts = list(fetched)
        except TypeError:
            continue
        for part in parts:
            if isinstance(part, tuple) and len(part) == 2 \
                    and isinstance(part[1], bytes):
                raw = part[1]
                break
        if raw is not None:
            mails.append((seq, raw))
    return mails


def mark_seen(imap, seq):
    # IMAP connections are not thread-safe; serialize STORE.
    with _MAIL_LOCK:
        try:
            imap.store(seq, "+FLAGS", "\\Seen")
        except Exception as e:
            log(f"STORE \\Seen failed for {seq}: {e}", "WARN")


def send_mail(smtp, cfg, subject: str, body: str, to: str | None = None):
    # SMTP connections are not thread-safe. Always serialize, even if
    # the caller already holds the lock (it is an RLock).
    # A newline in a header raises ValueError. That must not retry
    # the job forever.
    msg = EmailMessage()
    try:
        msg["From"] = str(cfg.get("mailbox_user") or "")
        msg["To"] = to or str(cfg.get("mailbox_user") or "")
        msg["Subject"] = str(subject or "").replace("\r", " ").replace("\n", " ")
        msg.set_content("" if body is None else str(body))
    except Exception as e:
        log(f"result message not built: {e}", "WARN")
        return
    with _MAIL_LOCK:
        smtp.send_message(msg)


_REPLY_TO_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _valid_reply_to(job) -> str | None:
    """The job's reply_to address, or None.

    Only a single plain address from inside the *signed* job body is
    honored, so a spoofed From header can never steer results at
    someone. Anything else falls back to the runner's own mailbox.
    """
    rt = job.get("reply_to") if isinstance(job, dict) else None
    if not isinstance(rt, str):
        return None
    rt = rt.strip()
    if len(rt) > 254 or not _REPLY_TO_RE.match(rt):
        return None
    return rt

