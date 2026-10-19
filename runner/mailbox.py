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
"""

import base64
import imaplib
import re
import smtplib
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


def connect_imap(cfg) -> imaplib.IMAP4_SSL:
    conn = imaplib.IMAP4_SSL(
        _host(cfg, "imap_host"), _port(cfg, "imap_port", 993),
        timeout=30)
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
    smtp = smtplib.SMTP(
        _host(cfg, "smtp_host"), _port(cfg, "smtp_port", 587),
        timeout=30)
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

