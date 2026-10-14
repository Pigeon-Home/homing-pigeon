#!/usr/bin/env python3
"""
Homing Pigeon — cross-platform runner agent.

Polls a dedicated mailbox for HMAC-signed job emails, executes them, and
emails back signed results. Runs on Linux, macOS, FreeBSD, and Windows.
Python 3.9+, standard library only. See PROTOCOL.md.

Usage:
    python3 runner.py --config config.json [--once]
"""

# HARD SECURITY RULES (read before changing):
#  1. Mailbox auth is one of two things, chosen by "auth" in config.json.
#     "password": a Gmail app password in plaintext. Dedicated throwaway
#     account, fresh box, nothing personal. It is never logged and never
#     put in email bodies, but it IS on disk.
#     "oauth": Thunderbird-style. A browser window signs you in. config.json
#     holds a refresh token, never the Google password. Run
#     homing-pigeon-auth once to get the token.
#  2. The HMAC shared secret is mailbox_password when auth is password
#     (the original model). When auth is oauth it is the separate
#     shared_secret field. Both sides use its UTF-8 bytes as the
#     HMAC-SHA-384 key. The user hands that string to the cloud side.
#  3. The runner ONLY obeys job mail whose From address is the account it is
#     logged into (or the explicit allowed_sender override). Anything else
#     is rejected before signature verification.

import argparse
import base64
import email
import hashlib
import hmac
import imaplib
import json
import os
import re
import shutil
import signal
import smtplib
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SUBJECT_JOB = "[HOMING-PIGEON] job "
SUBJECT_RESULT = "[HOMING-PIGEON] result "
PROTOCOL_VERSION = 1
SEEN_CAP = 2000


# ---------------------------------------------------------------- crypto
def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sign_payload(payload: dict, secret: str) -> str:
    body = _normalize(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    if not body.endswith("}"):
        raise ValueError("payload must serialize to a JSON object")
    sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"),
                   hashlib.sha384).hexdigest()
    return body[:-1] + ',"sig":"' + sig + '"}'


def _extract_signed(norm: str):
    """Pull the signed JSON object out of a body that may have a preamble
    or trailer (connector notes, signatures, blank lines).

    The signed form is a single JSON object whose final `}` was replaced
    by `,"sig":"<96 hex>"}`. We find that tail, then the `{` that opens
    the object, and return (raw_object_with_closing_brace, sig).
    """
    marker = ',"sig":"'
    i = norm.rfind(marker)
    if i < 0:
        raise ValueError("no signature marker found")
    tail = norm[i + len(marker):]
    if len(tail) < 98 or tail[96:98] != '"}' or tail[:96].lower().strip("0123456789abcdef") != "":
        raise ValueError("malformed signature tail")
    sig = tail[:96]
    start = _object_start(norm, i)
    return norm[start:i] + "}", sig


def _object_start(norm: str, sig_at: int) -> int:
    """Index of the `{` that opens the object ending at the sig marker."""
    j = 0
    candidates = []
    while True:
        j = norm.find("{", j, sig_at)
        if j < 0:
            break
        candidates.append(j)
        j += 1
    for start in reversed(candidates):
        if _in_root_object_at(norm, start, sig_at):
            return start
    raise ValueError("no JSON object before signature")


def _in_root_object_at(norm: str, start: int, sig_at: int) -> bool:
    depth = 0
    in_str = False
    escape = False
    for k in range(start, sig_at):
        c = norm[k]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return False
    return depth == 1 and not in_str


def verify_body(body: str, secret: str) -> dict:
    # Trailing whitespace is not signed. Surrounding text is ignored:
    # only the JSON object that ends in the signature is checked.
    norm = _normalize(body).rstrip()
    raw, sig = _extract_signed(norm)
    expect = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"),
                      hashlib.sha384).hexdigest()
    if not hmac.compare_digest(expect, sig.lower()):
        raise ValueError("signature mismatch")
    job = json.loads(raw)
    if not isinstance(job, dict):
        raise ValueError("signed body is not a JSON object")
    return job


class JobRejected(Exception):
    """Validly signed job that can never succeed (poison)."""


# ---------------------------------------------------------------- mail
def _use_oauth(cfg) -> bool:
    return str(cfg.get("auth") or "password").lower() == "oauth"


def _xoauth2_raw(cfg) -> str:
    try:
        from runner.oauth import refresh_access_token, xoauth2_raw
    except ImportError:
        from oauth import refresh_access_token, xoauth2_raw
    return xoauth2_raw(cfg["mailbox_user"], refresh_access_token(cfg))


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


def connect_imap(cfg) -> imaplib.IMAP4_SSL:
    conn = imaplib.IMAP4_SSL(cfg["imap_host"], int(cfg["imap_port"]), timeout=30)
    if _use_oauth(cfg):
        _imap_xoauth2(conn, cfg["mailbox_user"], _xoauth2_raw(cfg))
    else:
        # Password travels inside LOGIN, but only over the TLS session.
        # It is never logged or written anywhere.
        conn.login(cfg["mailbox_user"], cfg["mailbox_password"])
    typ, _ = conn.select("INBOX")
    if typ != "OK":
        raise RuntimeError("IMAP SELECT INBOX failed")
    return conn


def connect_smtp(cfg) -> smtplib.SMTP:
    smtp = smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30)
    smtp.starttls()
    if _use_oauth(cfg):
        # smtplib.auth base64-encodes the return value, and calls the
        # callback with no args for the initial response. Return the raw
        # string. A lambda that requires an argument crashes here.
        raw = _xoauth2_raw(cfg)
        smtp.auth("XOAUTH2", lambda challenge=None: raw)
    else:
        smtp.login(cfg["mailbox_user"], cfg["mailbox_password"])
    return smtp


def fetch_job_mails(imap):
    """Return [(seq, raw_bytes)] for unseen mails with the job subject prefix."""
    # Search broad: the subject regex accepts decorated subjects
    # ("[HOMING-PIGEON] TEST job <id>", "Re: ..."), which do not contain
    # the exact "[HOMING-PIGEON] job" substring. handle_mail filters.
    typ, data = imap.search(None, "UNSEEN", "SUBJECT", '"[HOMING-PIGEON]"')
    if typ != "OK":
        raise RuntimeError("IMAP SEARCH failed")
    mails = []
    for num in (data[0] or b"").split():
        typ, fetched = imap.fetch(num, "(RFC822)")
        if typ != "OK":
            continue
        raw = None
        for part in fetched:
            if isinstance(part, tuple) and len(part) == 2 and isinstance(part[1], bytes):
                raw = part[1]
                break
        if raw is not None:
            mails.append((num.decode("ascii"), raw))
    return mails


def mark_seen(imap, seq):
    # IMAP connections are not thread-safe; serialize STORE.
    with _MAIL_LOCK:
        try:
            imap.store(seq, "+FLAGS", "\\Seen")
        except Exception as e:
            log(f"STORE \\Seen failed for {seq}: {e}", "WARN")


def send_mail(smtp, cfg, subject: str, body: str):
    # SMTP connections are not thread-safe. Always serialize, even if
    # the caller already holds the lock (it is an RLock).
    msg = EmailMessage()
    msg["From"] = cfg["mailbox_user"]
    msg["To"] = cfg["mailbox_user"]
    msg["Subject"] = subject
    msg.set_content(body)
    with _MAIL_LOCK:
        smtp.send_message(msg)


def get_text_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    return msg.get_payload() or ""


# ---------------------------------------------------------------- execution
def platform_interpreter():
    if os.name == "nt":
        return ["powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File"]
    return ["sh"]


def script_filename(interpreter) -> str:
    """Name the staged script so the interpreter will accept -File.

    PowerShell refuses -File on a file without a .ps1 extension. That
    is a permanent failure, not a retry.
    """
    joined = " ".join(interpreter).lower()
    if "powershell" in joined or "pwsh" in joined:
        return "script.ps1"
    if "python" in joined:
        return "script.py"
    return "script"


def kill_tree(proc: subprocess.Popen):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MiB


def download(url: str, dest: str, max_bytes: int = MAX_DOWNLOAD_BYTES):
    # Non-HTTP schemes (file:, ftp:) fail the same way every cycle and
    # can read the local machine. Reject them as poison.
    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        raise JobRejected(f"unsupported url scheme: {url}")
    req = Request(url, headers={"User-Agent": "homing-pigeon/1"})
    try:
        resp = urlopen(req, timeout=120)
    except HTTPError as e:
        # 4xx will not succeed on retry. 5xx may.
        if 400 <= e.code < 500:
            raise JobRejected(f"download rejected by server ({e.code}): {url}")
        raise
    except URLError as e:
        reason = str(e.reason).lower()
        # NXDOMAIN and "no address" never recover. Timeouts and refused
        # connections still propagate as transient.
        permanent = ("name or service not known", "nodename nor servname",
                     "no address associated", "name resolution")
        if any(s in reason for s in permanent):
            raise JobRejected(f"download host does not resolve: {url}")
        raise
    with resp, open(dest, "wb") as f:
        total = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                # Poison, not transient: an over-cap download fails
                # identically on every retry, burning bandwidth each cycle.
                raise JobRejected(
                    f"download exceeded {max_bytes} bytes"
                )
            f.write(chunk)


def sha384_of(path: str) -> str:
    h = hashlib.sha384()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _safe_job_id(job_id: str) -> str:
    """Reject job_ids that could escape the work directory."""
    if not isinstance(job_id, str) or not _SAFE_JOB_ID.match(job_id):
        raise JobRejected(
            "job_id must be 1-128 chars of [A-Za-z0-9._-] "
            "(no slashes or absolute paths)"
        )
    if job_id in (".", ".."):
        # The charset allows dots: ".." collapses work/ to base_dir itself,
        # and then files[].name="config.json" passes the traversal check and
        # overwrites the runner's own config.
        raise JobRejected("job_id must not be '.' or '..'")
    return job_id


def execute_job(cfg, job: dict, base_dir: str) -> dict:
    job_id = _safe_job_id(job.get("job_id", ""))
    work = os.path.join(base_dir, "work", job_id)
    try:
        # A retry must not see files left by a previous attempt.
        if os.path.isdir(work):
            shutil.rmtree(work)
        os.makedirs(work)
    except OSError as e:
        # e.g. Windows reserved names (CON, NUL, ...) or work path blocked
        # by a file: poison, not transient.
        raise JobRejected(f"cannot create work dir: {e}")
    kind = job.get("kind")

    if kind == "ping":
        return {"stdout": "pong", "stderr": "", "exit_code": 0,
                "timed_out": False, "stdout_truncated": False,
                "stderr_truncated": False, "duration_sec": 0.0}

    if kind != "exec":
        raise JobRejected(f"unknown kind: {kind}")

    # --- validate job shape. Anything malformed here is poison (it can
    # never succeed), so reject it instead of letting a TypeError/KeyError
    # escape as transient and retry forever.
    files = job.get("files") or []
    if not isinstance(files, list):
        raise JobRejected("files must be a list")
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get("name"), str) \
                or not isinstance(f.get("url"), str):
            raise JobRejected("each file needs string 'name' and 'url'")
        if "sha384" in f and not isinstance(f["sha384"], str):
            raise JobRejected("file 'sha384' must be a string")
    args = job.get("args") or []
    if not isinstance(args, list):
        raise JobRejected("args must be a list")
    env_in = job.get("env") or {}
    if not isinstance(env_in, dict):
        raise JobRejected("env must be an object")
    script = job.get("script")
    script_url = job.get("script_url")
    if script is not None and not isinstance(script, str):
        raise JobRejected("script must be a string")
    if script_url is not None and not isinstance(script_url, str):
        raise JobRejected("script_url must be a string")
    if job.get("script_sha384") is not None \
            and not isinstance(job["script_sha384"], str):
        raise JobRejected("script_sha384 must be a string")
    try:
        timeout = int(job.get("timeout_sec")
                      or cfg.get("default_timeout_sec", 300))
    except (TypeError, ValueError):
        raise JobRejected("timeout_sec must be a number")
    timeout = min(max(timeout, 1), 3600)

    # --- stage input files
    for f in files:
        dest = os.path.realpath(os.path.join(work, f["name"]))
        prefix = os.path.realpath(work) + os.sep
        if not dest.startswith(prefix):
            raise JobRejected(f"unsafe file name: {f['name']}")
        log(f"downloading {f['url']}")
        try:
            download(f["url"], dest)
        except JobRejected:
            raise  # oversize is poison, not transient
        except Exception as e:
            raise RuntimeError(f"download failed for {f['name']}: {e}")
        if f.get("sha384") and sha384_of(dest).lower() != f["sha384"].lower():
            raise JobRejected(f"SHA384 mismatch for {f['name']}")

    # --- stage script
    # Interpreter is resolved first so the filename matches it.
    # PowerShell -File requires .ps1; a bare "script" is rejected.
    interpreter = job.get("interpreter") or cfg.get("default_interpreter") \
        or platform_interpreter()
    if not isinstance(interpreter, list) or not interpreter or \
            not all(isinstance(x, str) for x in interpreter):
        raise JobRejected("interpreter must be a non-empty list of strings")
    script_path = os.path.join(work, script_filename(interpreter))
    if script_url:
        log(f"downloading script {script_url}")
        try:
            download(script_url, script_path)
        except JobRejected:
            raise  # oversize is poison, not transient
        except Exception as e:
            raise RuntimeError(f"script download failed: {e}")
        if job.get("script_sha384") and \
                sha384_of(script_path).lower() != job["script_sha384"].lower():
            raise JobRejected("script SHA384 mismatch")
    elif script:
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(script)
    else:
        raise JobRejected("exec job requires script or script_url")

    timeout = min(max(timeout, 1), 3600)
    args = [str(a) for a in args]
    env = os.environ.copy()
    for k, v in env_in.items():
        env[str(k)] = str(v)

    max_out = int(cfg.get("max_output_bytes", 100000))
    t0 = time.monotonic()
    try:
        proc = subprocess.Popen(
            [*interpreter, script_path, *args],
            cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, start_new_session=(os.name != "nt"),
        )
    except OSError as e:
        # Missing binary or an unusable interpreter fails the same way
        # every cycle. Treat it as poison so the mail is marked seen
        # instead of retried forever.
        raise JobRejected(f"cannot start interpreter: {e}")
    try:
        outs, errs = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        log(f"job {job['job_id']} timed out after {timeout}s; killing tree", "WARN")
        kill_tree(proc)
        outs, errs = proc.communicate()
        timed_out = True
    duration = round(time.monotonic() - t0, 3)

    stdout = outs.decode("utf-8", errors="replace")
    stderr = errs.decode("utf-8", errors="replace")
    trunc_out, trunc_err = False, False
    if len(stdout) > max_out:
        stdout, trunc_out = stdout[:max_out], True
    if len(stderr) > max_out:
        stderr, trunc_err = stderr[:max_out], True

    return {"stdout": stdout, "stderr": stderr,
            "exit_code": -1 if timed_out else proc.returncode,
            "timed_out": timed_out,
            "stdout_truncated": trunc_out, "stderr_truncated": trunc_err,
            "duration_sec": duration}


# ---------------------------------------------------------------- job handling
def log(msg: str, level: str = "INFO"):
    if level == "DEBUG" and not _VERBOSE:
        return
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [{level}] {msg}"
    # The mail lock also serializes log lines across worker threads.
    with _MAIL_LOCK:
        print(line, flush=True)
        if _LOG_FILE:
            try:
                with open(_LOG_FILE, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except Exception:
                pass


_LOG_FILE = None
_VERBOSE = False

# Concurrency: IMAP/SMTP connections and the seen-set are not
# thread-safe. Worker threads run handle_mail, but every touch of shared
# state goes through _MAIL_LOCK. Only execute_job (subprocess + per-job
# work dirs) actually runs in parallel. _IN_FLIGHT stops two threads
# from executing the same job_id concurrently (duplicate delivery).
_MAIL_LOCK = threading.RLock()
_IN_FLIGHT: set = set()


def _describe_job(job: dict) -> str:
    """One-line summary of what a job would do (for --dry-run)."""
    kind = job.get("kind")
    if kind == "ping":
        return "kind=ping (would reply pong)"
    parts = [f"kind=exec"]
    if job.get("script"):
        parts.append(f"inline script ({len(str(job['script']))} chars)")
    if job.get("script_url"):
        parts.append(f"script_url={job['script_url']}")
    if job.get("interpreter"):
        parts.append(f"interpreter={job['interpreter']}")
    files = job.get("files") or []
    if files:
        parts.append(f"{len(files)} file(s): " +
                     ", ".join(str(f.get("url", "?")) for f in files
                               if isinstance(f, dict)))
    if job.get("args"):
        parts.append(f"args={job['args']}")
    if job.get("timeout_sec"):
        parts.append(f"timeout_sec={job['timeout_sec']}")
    return ", ".join(parts)


def handle_mail(cfg, imap, smtp, seq, raw: bytes, base_dir: str,
                seen: dict, secret: str, allowed_sender: str, opts=None):
    msg = email.message_from_bytes(raw)
    subject = str(msg["Subject"] or "")
    from_header = str(msg["From"] or "")
    log(f"examining seq {seq}: subject={subject!r} from={from_header!r}",
        "DEBUG")

    def reject(why: str):
        log(f"rejecting seq {seq}: {why}", "WARN")
        # Dry-run is fully non-mutating: observe, change nothing.
        if opts is None or not opts.dry_run:
            mark_seen(imap, seq)

    m = re.search(r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)", subject, re.I)
    if not m:
        reject("subject does not match job pattern")
        return
    job_id = m.group(1)

    if job_id in seen:
        if opts is None or not opts.dry_run:
            mark_seen(imap, seq)
        return

    # HARD RULE: only the runner's own account may issue jobs.
    from_addr = parseaddr(from_header)[1].strip()
    if not from_addr or from_addr.lower() != allowed_sender.lower():
        reject(f"sender not allowed (must be {allowed_sender}): {from_header}")
        return

    try:
        job = verify_body(get_text_body(msg), secret)
    except ValueError:
        reject("bad signature")
        return
    if not isinstance(job, dict):
        # verify_body can return any JSON value if the signer hand-crafts
        # one; job.get below would raise AttributeError -> transient retry.
        reject("job body must be a JSON object")
        return
    if job.get("v") != PROTOCOL_VERSION or job.get("type") != "job":
        reject("unsupported version/type")
        return
    if job.get("job_id") != job_id:
        reject("job_id mismatch between subject and body")
        return
    try:
        issued = datetime.fromisoformat(job["issued_at"].replace("Z", "+00:00"))
    except Exception:
        reject("unparseable issued_at")
        return
    # Naive timestamps make the age subtraction raise TypeError, which the
    # outer handler treats as transient and retries forever. Reject instead.
    if issued.tzinfo is None or issued.tzinfo.utcoffset(issued) is None:
        reject("issued_at missing timezone (must be UTC / end with Z)")
        return
    age = (datetime.now(timezone.utc) - issued).total_seconds()
    if age < -300 or age > int(cfg.get("max_job_age_sec", 3600)):
        reject(f"issued_at outside allowed window (age {age:.0f}s)")
        return

    log(f"executing job {job_id} (kind={job.get('kind')})")
    if opts is not None and opts.dry_run:
        # Dry run: fully non-mutating. Verify everything, change nothing:
        # no execution, no result email, no seen updates.
        desc = _describe_job(job)
        log(f"dry-run: would execute job {job_id}: {desc}")
        return
    no_send = opts is not None and opts.no_send

    # Claim the job_id so a duplicate delivery on another worker thread
    # cannot double-execute it. The check-and-add is atomic under the lock.
    with _MAIL_LOCK:
        if job_id in seen or job_id in _IN_FLIGHT:
            mark_seen(imap, seq)
            return
        _IN_FLIGHT.add(job_id)
    try:
        def maybe_send(subject: str, body: str):
            if no_send:
                log(f"no-send: result email suppressed "
                    f"(subject={subject!r}, {len(body)} bytes)")
                return
            send_mail(smtp, cfg, subject, body)

        try:
            r = execute_job(cfg, job, base_dir)
            result = {
                "v": PROTOCOL_VERSION, "type": "result", "job_id": job_id,
                "kind": job.get("kind"),
                "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "exit_code": int(r["exit_code"]), "timed_out": bool(r["timed_out"]),
                "stdout": str(r["stdout"]), "stderr": str(r["stderr"]),
                "stdout_truncated": bool(r["stdout_truncated"]),
                "stderr_truncated": bool(r["stderr_truncated"]),
                "duration_sec": float(r["duration_sec"]),
                "runner": socket.gethostname(),
            }
            with _MAIL_LOCK:
                maybe_send(f"{SUBJECT_RESULT}{job_id}",
                          sign_payload(result, secret))
                log(f"job {job_id} done (exit={r['exit_code']})")
                seen[job_id] = True  # only after the result is safely sent (at-least-once)
                mark_seen(imap, seq)
        except JobRejected as e:
            log(f"job {job_id} rejected: {e}", "WARN")
            try:
                result = {
                    "v": PROTOCOL_VERSION, "type": "result", "job_id": job_id,
                    "kind": job.get("kind"),
                    "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "exit_code": -2, "timed_out": False,
                    "stdout": "", "stderr": f"job rejected: {e}",
                    "stdout_truncated": False, "stderr_truncated": False,
                    "duration_sec": 0.0, "runner": socket.gethostname(),
                }
                with _MAIL_LOCK:
                    maybe_send(f"{SUBJECT_RESULT}{job_id}",
                              sign_payload(result, secret))
                    seen[job_id] = True
                    mark_seen(imap, seq)
            except Exception as e2:
                log(f"could not send rejection result: {e2}", "ERROR")
        except Exception as e:
            # Transient (network, SMTP, ...): leave unseen -> retried next cycle.
            log(f"job {job_id} failed, will retry: {e}", "ERROR")
    finally:
        with _MAIL_LOCK:
            _IN_FLIGHT.discard(job_id)


# ---------------------------------------------------------------- main
def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_seen(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return {str(x): True for x in data} if isinstance(data, list) else {}
    except Exception:
        return {}


def save_seen(path: str, seen: dict):
    keys = list(seen.keys())[-SEEN_CAP:]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(keys, fh)


def _worker_count(cfg, opts) -> int:
    """Concurrent job executions. CLI overrides config; default 1."""
    raw = None
    if opts is not None and getattr(opts, "workers", None) is not None:
        raw = opts.workers
    elif cfg.get("workers") is not None:
        raw = cfg.get("workers")
    if raw is None:
        return 1
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(1, n)


def poll_once(cfg, base_dir: str, seen: dict, seen_path: str,
              imap=None, smtp=None, opts=None):
    """One poll cycle. imap/smtp may be injected (tests)."""
    # Password auth: the HMAC secret is the mailbox password (original model).
    # OAuth auth: the Google password is gone, so the secret is its own field.
    if _use_oauth(cfg):
        secret = cfg.get("shared_secret") or ""
        if not secret:
            raise RuntimeError("config error: shared_secret is required when auth=oauth")
    else:
        secret = cfg["mailbox_password"]
    allowed_sender = cfg.get("allowed_sender") or cfg["mailbox_user"]
    log(f"runner identity: {cfg['mailbox_user']} "
        f"-- accepting jobs only from {allowed_sender}")
    own_imap = imap is None
    own_smtp = smtp is None
    try:
        if own_imap:
            imap = connect_imap(cfg)
        if own_smtp:
            smtp = connect_smtp(cfg)
        try:
            mails = fetch_job_mails(imap)
            log(f"poll: {len(mails)} job mail(s)")
            workers = _worker_count(cfg, opts)
            if workers > 1:
                log(f"executing with {workers} workers", "DEBUG")
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(handle_mail, cfg, imap, smtp, seq, raw,
                                  base_dir, seen, secret, allowed_sender, opts)
                        for seq, raw in mails]
                first_exc = None
                for f in as_completed(futs):
                    exc = f.exception()
                    # handle_mail already deals with expected failures
                    # (rejects, transient retries). A worker raising here
                    # is a bug; surface it like the sequential path did.
                    if exc is not None and first_exc is None:
                        first_exc = exc
                        log(f"worker raised: {exc!r}", "ERROR")
            if len(seen) > SEEN_CAP:
                # save_seen caps the disk copy; keep memory in step.
                for k in list(seen.keys())[:-SEEN_CAP]:
                    del seen[k]
            save_seen(seen_path, seen)
            if first_exc is not None:
                raise first_exc
        finally:
            if own_imap:
                try:
                    imap.logout()
                except Exception:
                    pass
    finally:
        if own_smtp and smtp is not None:
            try:
                smtp.quit()
            except Exception:
                pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Homing Pigeon runner agent")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--once", action="store_true",
                    help="run a single poll cycle, then exit")
    # NOTE: the flag order below is deliberate. Safety-relevant disable
    # flags (--no-oracle, --no-send) are scattered among operational
    # flags so --help does not read as an obvious "turn everything off"
    # menu. The capabilities are all documented; they are just not
    # clustered.
    ap.add_argument("--dry-run", action="store_true",
                    help="verify signatures and print what would run; "
                         "execute nothing, send nothing, change nothing")
    ap.add_argument("--workers", type=int, default=None, metavar="N",
                    help="concurrent job executions (default 1; overrides config)")
    ap.add_argument("--poll-interval", type=int, default=None, metavar="SEC",
                    help="seconds between poll cycles (overrides config)")
    ap.add_argument("--no-oracle", action="store_true",
                    help="disable the Oracle safety layer (overrides config; "
                         "v1 dumb pipe)")
    ap.add_argument("--max-output-bytes", type=int, default=None, metavar="N",
                    help="truncate stdout/stderr beyond N bytes "
                         "(overrides config)")
    ap.add_argument("--no-send", action="store_true",
                    help="execute jobs but do not send result emails "
                         "(results go to the log only)")
    ap.add_argument("--timeout", type=int, default=None, metavar="SEC",
                    help="default per-job timeout in seconds (overrides config)")
    ap.add_argument("--verbose", action="store_true",
                    help="debug logging: log every accept/reject decision")
    ap.add_argument("--pdb", action="store_true",
                    help="drop into pdb on unhandled exceptions")
    args = ap.parse_args()

    if args.workers is not None and args.workers < 1:
        print("error: --workers must be >= 1", file=sys.stderr)
        return 2

    cfg = load_config(args.config)
    if not cfg.get("mailbox_user"):
        print("config error: mailbox_user is required", file=sys.stderr)
        return 2
    if _use_oauth(cfg):
        for key in ("oauth_client_id", "oauth_refresh_token", "shared_secret"):
            if not cfg.get(key):
                print(f"config error: {key} is required when auth=oauth "
                      f"(run homing-pigeon-auth to get the refresh token)",
                      file=sys.stderr)
                return 2
    elif not cfg.get("mailbox_password"):
        print("config error: mailbox_password is required when auth=password",
              file=sys.stderr)
        return 2
    # CLI overrides config.
    if args.poll_interval is not None:
        cfg["poll_interval_sec"] = args.poll_interval
    if args.max_output_bytes is not None:
        cfg["max_output_bytes"] = args.max_output_bytes
    if args.timeout is not None:
        cfg["default_timeout_sec"] = args.timeout
    if args.no_oracle:
        cfg["oracle_enabled"] = False
    global _VERBOSE
    _VERBOSE = args.verbose
    base_dir = cfg.get("base_dir") or os.path.join(os.path.expanduser("~"),
                                                  ".homing-pigeon")
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(os.path.join(base_dir, "work"), exist_ok=True)

    global _LOG_FILE
    _LOG_FILE = os.path.join(base_dir, "runner.log")

    seen_path = os.path.join(base_dir, "seen.json")
    seen = load_seen(seen_path)

    log(f"homing-pigeon starting (base={base_dir}, platform={sys.platform})")
    log(f"flags: dry_run={args.dry_run} no_send={args.no_send} "
        f"no_oracle={args.no_oracle} verbose={args.verbose} pdb={args.pdb} "
        f"once={args.once} workers={_worker_count(cfg, args)}")
    while True:
        try:
            poll_once(cfg, base_dir, seen, seen_path, opts=args)
        except Exception as e:
            log(f"poll cycle failed: {e}", "ERROR")
            if args.pdb:
                import pdb
                pdb.post_mortem(sys.exc_info()[2])
        if args.once:
            break
        time.sleep(int(cfg.get("poll_interval_sec", 20)))
    log("homing-pigeon exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
