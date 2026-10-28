# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""A signed cancel for a job (PROTOCOL.md section 3.4).

`[HOMING-PIGEON] cancel <job_id>` carries a signed (and, unless the
runner allows cleartext, sealed) object `{"v": 1, "type": "cancel",
"job_id": ..., "issued_at": ...}`. Only the key the job was signed
with may cancel it, under any of its names. What happens depends on
where the job is:

- running here: its process tree is killed the way a timeout kills
  it, and its result carries `cancelled: true`;
- not yet seen: the runner keeps the cancel for as long as a job
  issued before it could still arrive (twice `max_job_age_sec`), and
  a job that arrives in that time is answered as a rejection
  (`exit_code` -2) without running;
- already done: nothing changes.

The sender hears which in a signed `cancel_ack` under the subject
`[HOMING-PIGEON] cancelled <job_id>`, whose `status` is `killed`,
`will_refuse` or `finished`. Another key's job, running, done or not
yet seen, reads as `will_refuse` and is left alone, so a key learns
nothing of which job ids another key ran.
"""
import email
import os
import re
import threading
import time

try:
    from runner.guard import atomicio as _atomicio
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from guard import atomicio as _atomicio  # type: ignore
    from ops.live import _runner  # type: ignore

SUBJECT = re.compile(r"\[HOMING-PIGEON\]\s+cancel\s+(\S+)\s*$", re.I)
JOB_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
CANCELS_FILE = "cancels.json"
ACK_SUBJECT = "[HOMING-PIGEON] cancelled "

_LOCK = threading.Lock()
_RUNNING = {}       # job_id -> {"owner": str, "proc": Popen, "cancelled": bool}


# ---- the jobs running in this process

def register(job_id, owner, proc):
    with _LOCK:
        _RUNNING[job_id] = {"owner": owner, "proc": proc, "cancelled": False}


def unregister(job_id):
    """Forget a finished job; True when it was cancelled while it ran."""
    with _LOCK:
        entry = _RUNNING.pop(job_id, None)
    return bool(entry and entry.get("cancelled"))


def _kill_running(job_id, owner):
    """'killed', or None when this key's job is not running here (a
    job another key runs is not this key's to see)."""
    with _LOCK:
        entry = _RUNNING.get(job_id)
        if entry is None or entry["owner"] != owner:
            return None
        entry["cancelled"] = True
        proc = entry["proc"]
    try:
        _runner().kill_tree(proc)
    except Exception as e:
        _runner().log(f"cancel {job_id}: kill failed: {e}", "WARN")
    return "killed"


# ---- cancels that arrive before their job

def _keep_sec(cfg):
    try:
        age = int((cfg or {}).get("max_job_age_sec") or 3600)
    except (TypeError, ValueError, OverflowError):
        age = 3600
    return 2 * max(age, 1)


def _load(base_dir):
    try:
        import json
        with open(os.path.join(base_dir, CANCELS_FILE), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(base_dir, data):
    try:
        _atomicio.write_json(os.path.join(base_dir, CANCELS_FILE), data)
    except OSError as e:
        _runner().log(f"cancel not kept: {e}", "WARN")


def _pruned(data, cfg, now):
    keep = _keep_sec(cfg)
    out = {}
    for owner, jobs in data.items():
        if not isinstance(owner, str) or not isinstance(jobs, dict):
            continue
        live = {j: t for j, t in jobs.items()
                if isinstance(t, (int, float)) and not isinstance(t, bool)
                and now - t < keep}
        if live:
            out[owner] = live
    return out


def keep_cancel(cfg, base_dir, owner, job_id, now=None):
    now = time.time() if now is None else now
    with _LOCK:
        data = _pruned(_load(base_dir), cfg, now)
        data.setdefault(owner, {})[job_id] = now
        _save(base_dir, data)


def take_cancel(cfg, base_dir, owner, job_id, now=None):
    """True (and the cancel spent) when the job's own key cancelled it
    before it arrived and the cancel is still in its window."""
    now = time.time() if now is None else now
    with _LOCK:
        raw = _load(base_dir)
        data = _pruned(raw, cfg, now)
        hit = job_id in data.get(owner, {})
        if hit:
            del data[owner][job_id]
            if not data[owner]:
                del data[owner]
        if hit or data != raw:
            _save(base_dir, data)
    return hit


# ---- the message

def _finished_by(base_dir, cfg, secrets, job_id, owner, seen):
    R = _runner()
    skey = R._seen_key(cfg, job_id)
    if not (isinstance(seen, dict) and seen.get(skey)):
        return None
    rec = R._read_record(R._sent_path(base_dir, skey))
    if isinstance(rec, dict) and \
            R.canonical_key_id(secrets, rec.get("key_id") or "") == owner:
        return "finished"
    return None


def handle_cancel_mail(cfg, imap, smtp, seq, raw, subject, secrets, opts,
                       base_dir, seen=None):
    """Handle a cancel subject. True when the message was a cancel."""
    R = _runner()
    m = SUBJECT.search(subject or "")
    if not m:
        return False
    job_id = m.group(1)
    if not JOB_ID.match(job_id) or job_id in (".", ".."):
        R.log(f"cancel seq {seq}: not a job id", "WARN")
        R._mark(imap, seq, opts)
        return True
    try:
        body = R.get_text_body(email.message_from_bytes(raw))
        payload, key_id, secret, encrypted = R._admit_object(body, secrets, job_id)
    except Exception as e:
        R.log(f"cancel seq {seq}: not admitted: {e}", "WARN")
        R._mark(imap, seq, opts)
        return True
    if not encrypted and not R._cleartext_jobs_allowed():
        R.log(f"cancel {job_id}: cleartext refused", "WARN")
        R._auth_reject_event(base_dir, "cleartext_not_supported", feature="cancel")
        R._mark(imap, seq, opts)
        return True
    if not R.audience_allows(cfg, base_dir, payload, key_id, job_id):
        R.log(f"cancel seq {seq}: runner_id mismatch", "WARN")
        R._mark(imap, seq, opts)
        return True
    if not R._version_ok(payload.get("v")) or payload.get("type") != "cancel" \
            or payload.get("job_id") != job_id:
        R.log(f"cancel seq {seq}: not a cancel for {job_id}", "WARN")
        R._mark(imap, seq, opts)
        return True
    ok_ts, why = R._issued_at_ok(payload.get("issued_at"), cfg)
    if not ok_ts:
        R.log(f"cancel seq {seq}: {why}", "WARN")
        R._mark(imap, seq, opts)
        return True
    door = R._verify.check_door_policy(cfg, secrets, key_id, "cancel")
    if door:
        R.log(f"cancel seq {seq}: key policy: {door}", "WARN")
        R._mark(imap, seq, opts)
        return True
    owner = R.canonical_key_id(secrets, key_id)
    seen_key = R._seen_key(cfg, f"cancel:{owner}:{job_id}")
    if isinstance(seen, dict) and seen.get(seen_key):
        R._mark(imap, seq, opts)
        return True
    dry = bool(opts is not None and getattr(opts, "dry_run", False))
    if dry:
        R.log(f"cancel {job_id}: dry run, nothing stopped or kept")
        return True
    status = _kill_running(job_id, owner)
    if status is None:
        status = _finished_by(base_dir, cfg, secrets, job_id, owner, seen)
    if status is None:
        keep_cancel(cfg, base_dir, owner, job_id)
        status = "will_refuse"
    R.log(f"cancel {job_id}: {status}", "WARN" if status == "killed" else "INFO")
    if isinstance(seen, dict):
        with R._MAIL_LOCK:
            seen[seen_key] = True
    if not getattr(opts, "no_send", False):
        ack = {"v": R.PROTOCOL_VERSION, "type": "cancel_ack",
               "job_id": job_id, "status": status}
        try:
            R.send_mail(smtp, cfg, ACK_SUBJECT + job_id,
                        R._seal_reply(ack, secret, job_id, key_id, encrypted))
        except Exception as e:
            R.log(f"cancel {job_id}: ack not sent: {e}", "WARN")
    R._mark(imap, seq, opts)
    return True
