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
#  1. The Gmail app password lives in PLAINTEXT in config.json -- the user's
#     explicit choice (dedicated throwaway account, fresh box, nothing
#     personal). It is never logged and never put in email bodies, but it IS
#     on disk. Do not use this setup with an account you care about.
#  2. The HMAC shared secret IS that same password string. Both sides use
#     its UTF-8 bytes directly as the HMAC-SHA-384 key. The user hands the
#     string to the cloud side separately when they want jobs sent.
#  3. The runner ONLY obeys job mail whose From address is the account it is
#     logged into (or the explicit allowed_sender override). Anything else
#     is rejected before signature verification.

import argparse
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
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
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
def connect_imap(cfg) -> imaplib.IMAP4_SSL:
    # NOTE: the password travels inside the LOGIN command, but only over the
    # TLS session below. It is never logged or written anywhere.
    conn = imaplib.IMAP4_SSL(cfg["imap_host"], int(cfg["imap_port"]), timeout=30)
    conn.login(cfg["mailbox_user"], cfg["mailbox_password"])
    typ, _ = conn.select("INBOX")
    if typ != "OK":
        raise RuntimeError("IMAP SELECT INBOX failed")
    return conn


def connect_smtp(cfg) -> smtplib.SMTP:
    smtp = smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30)
    smtp.starttls()
    smtp.login(cfg["mailbox_user"], cfg["mailbox_password"])
    return smtp


def fetch_job_mails(imap):
    """Return [(seq, raw_bytes)] for unseen mails with the job subject prefix."""
    typ, data = imap.search(None, "UNSEEN", "SUBJECT", f'"{SUBJECT_JOB.strip()}"')
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
    try:
        imap.store(seq, "+FLAGS", "\\Seen")
    except Exception as e:
        log(f"STORE \\Seen failed for {seq}: {e}", "WARN")


def send_mail(smtp, cfg, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = cfg["mailbox_user"]
    msg["To"] = cfg["mailbox_user"]
    msg["Subject"] = subject
    msg.set_content(body)
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
    req = Request(url, headers={"User-Agent": "homing-pigeon/1"})
    with urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        total = 0
        while True:
            chunk = r.read(65536)
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
        os.makedirs(work, exist_ok=True)
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
    script_path = os.path.join(work, "script")
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

    interpreter = job.get("interpreter") or cfg.get("default_interpreter") \
        or platform_interpreter()
    # A bare string is iterated as characters by the * unpack below
    # ("sh" -> ["s", "h", ...]), which fails and gets retried forever.
    if not isinstance(interpreter, list) or not interpreter or \
            not all(isinstance(x, str) for x in interpreter):
        raise JobRejected("interpreter must be a non-empty list of strings")
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
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [{level}] {msg}"
    print(line, flush=True)
    if _LOG_FILE:
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass


_LOG_FILE = None


def handle_mail(cfg, imap, smtp, seq, raw: bytes, base_dir: str,
                seen: dict, secret: str, allowed_sender: str):
    msg = email.message_from_bytes(raw)
    subject = str(msg["Subject"] or "")
    from_header = str(msg["From"] or "")

    def reject(why: str):
        log(f"rejecting seq {seq}: {why}", "WARN")
        mark_seen(imap, seq)

    m = re.search(r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)", subject, re.I)
    if not m:
        reject("subject does not match job pattern")
        return
    job_id = m.group(1)

    if job_id in seen:
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
        send_mail(smtp, cfg, f"{SUBJECT_RESULT}{job_id}",
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
            send_mail(smtp, cfg, f"{SUBJECT_RESULT}{job_id}",
                      sign_payload(result, secret))
            seen[job_id] = True
            mark_seen(imap, seq)
        except Exception as e2:
            log(f"could not send rejection result: {e2}", "ERROR")
    except Exception as e:
        # Transient (network, SMTP, ...): leave unseen -> retried next cycle.
        log(f"job {job_id} failed, will retry: {e}", "ERROR")


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


def poll_once(cfg, base_dir: str, seen: dict, seen_path: str,
              imap=None, smtp=None):
    """One poll cycle. imap/smtp may be injected (tests)."""
    secret = cfg["mailbox_password"]  # the HMAC secret IS this string
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
            for seq, raw in mails:
                handle_mail(cfg, imap, smtp, seq, raw, base_dir,
                            seen, secret, allowed_sender)
            if len(seen) > SEEN_CAP:
                # save_seen caps the disk copy; keep memory in step.
                for k in list(seen.keys())[:-SEEN_CAP]:
                    del seen[k]
            save_seen(seen_path, seen)
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
    args = ap.parse_args()

    cfg = load_config(args.config)
    for key in ("mailbox_user", "mailbox_password"):
        if not cfg.get(key):
            print(f"config error: {key} is required (plaintext, your choice)",
                  file=sys.stderr)
            return 2
    base_dir = cfg.get("base_dir") or os.path.join(os.path.expanduser("~"),
                                                  ".homing-pigeon")
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(os.path.join(base_dir, "work"), exist_ok=True)

    global _LOG_FILE
    _LOG_FILE = os.path.join(base_dir, "runner.log")

    seen_path = os.path.join(base_dir, "seen.json")
    seen = load_seen(seen_path)

    log(f"homing-pigeon starting (base={base_dir}, platform={sys.platform})")
    while True:
        try:
            poll_once(cfg, base_dir, seen, seen_path)
        except Exception as e:
            log(f"poll cycle failed: {e}", "ERROR")
        if args.once:
            break
        time.sleep(int(cfg.get("poll_interval_sec", 20)))
    log("homing-pigeon exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
