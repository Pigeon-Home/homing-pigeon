"""The extension side of the transport channel (contract v1).

A transport extension process owns its pipe -- a mailbox, a
watched folder, a broker subscription -- and talks to the runner
through one directory pair:

    <channel>/inbox/    job envelopes, extension -> runner
    <channel>/outbox/   result envelopes, runner -> extension

A job envelope is a subject line, a blank line, then the signed
body; a result drops in as <job_id>.result.txt in the same
shape. Ack is consumption: whichever side has taken a file
moves it into the sibling done/ directory, never deletes.

This module is the shared helper for the first-party
extensions; a third-party transport extension needs nothing
from it -- the contract is the directories and the envelope
shape, and an owner can drop in an extension that speaks it in
any language, registered or not.

Stdlib, plus the runner's one atomic writer (guard/atomicio.py):
an envelope lands whole or not at all.
"""

import json
import os
import re
import sys
import time

try:
    from runner.guard import atomicio as _atomicio
except ImportError:
    from guard import atomicio as _atomicio  # type: ignore

FILE_MAX_BYTES = 4 * 1024 * 1024
# j1.result.txt and j1.result-2.txt are both the job j1. The sweep
# reads failed/<id>.result.txt beside <id>.refused.txt.
_RESULT_NAME_RE = re.compile(r"^(.+)\.result(?:-\d+)?\.txt$")


def result_file_id(fname):
    """The ident a result file is named for.

    ``j1.result.txt`` and ``j1.result-2.txt`` are both j1. The
    suffix is only how a second file is kept from clobbering the
    first. A name that is not a result file is None.
    """
    m = _RESULT_NAME_RE.match(os.path.basename(fname or ""))
    return m.group(1) if m else None


class PermanentDeliveryError(Exception):
    """A transport's way of saying a result will never go out as it
    is (the far end refused it for good: a 5xx, an oversize
    rejection). The runner treats it like a permanent SMTP refusal:
    the record is not retried; a signed stub without the streams is
    sent instead, once (review item 4)."""


def log(msg, level="INFO"):
    # A weak-key refusal may name its repeating unit. A strong
    # secret is not passed here.
    # codeql[py/clear-text-logging-sensitive-data]
    print(f"{level}: {msg}", file=sys.stderr, flush=True)


def envelope(subject, body):
    return f"{subject}\n\n{body}"


def parse_envelope(text):
    text = (text or "").replace("\r\n", "\n")
    head, sep, body = text.partition("\n\n")
    if not sep:
        return None
    return head.strip(), body


def load_runtime_config(argv):
    """(channel_dir, config) from the launch arguments.

    The runner launches a transport extension with
    argv = [channel_dir, runtime_config_path] (after the entry's
    own prefix) and sets the HOMING_PIGEON_TRANSPORT_* env vars
    to the same values; either source works, env wins when both
    exist so a hand launch can override.
    """
    channel = os.environ.get("HOMING_PIGEON_TRANSPORT_CHANNEL", "")
    cfg_path = os.environ.get("HOMING_PIGEON_TRANSPORT_CONFIG", "")
    args = [a for a in argv[1:] if not a.startswith("-")]
    if len(args) >= 1 and not channel:
        channel = args[0]
    if len(args) >= 2 and not cfg_path:
        cfg_path = args[1]
    cfg = {}
    if cfg_path:
        try:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError) as e:
            log(f"cannot read runtime config {cfg_path}: {e}",
                "ERROR")
    if not channel:
        channel = cfg.get("channel_dir", "")
    return channel, cfg


def dirs(channel):
    out = {
        "inbox": os.path.join(channel, "inbox"),
        "inbox_done": os.path.join(channel, "inbox", "done"),
        "outbox": os.path.join(channel, "outbox"),
        "outbox_done": os.path.join(channel, "outbox", "done"),
    }
    for path in out.values():
        os.makedirs(path, exist_ok=True)
    return out


def _atomic_write(path, text):
    _atomicio.write_text(path, text)


def deliver_job(channel, ident, subject, body):
    """Drop one job envelope in the runner's inbox. `ident` is
    this transport's stable id for the job (the file
    transport's file name, the broker's reply subject tail, the
    message's own id); the file lands as <ident>.job.txt so a
    redelivery of the same job rewrites the same file."""
    d = dirs(channel)
    # A job id is 1–128 of [A-Za-z0-9._-] (the protocol, and the
    # queue). Keeping 120 made two ids that differed later one
    # file. The result was then named for the short file, not the
    # id in the subject, so it was never posted, and the done-file
    # the core wrote was not the name the ack looks for.
    safe = "".join(c if (c.isalnum() or c in "._-") else "_"
                   for c in str(ident))[:128] or "job"
    path = os.path.join(d["inbox"], safe + ".job.txt")
    text = envelope(subject, body)
    if body and not body.endswith("\n"):
        text += "\n"
    _atomic_write(path, text)
    return path


def pending_results(channel):
    """(fname, subject, body) for each result envelope waiting
    in the outbox."""
    d = dirs(channel)
    out = []
    for fname in sorted(os.listdir(d["outbox"])):
        if fname in ("done", "failed"):
            continue
        path = os.path.join(d["outbox"], fname)
        if os.path.islink(path):
            # Following the link would read some other file, and
            # skipping it made the result invisible, so the queue
            # acked the job with nothing stored.
            if result_file_id(fname):
                refuse_symlink_result(channel, fname)
            continue
        if not os.path.isfile(path):
            continue
        try:
            if os.path.getsize(path) > FILE_MAX_BYTES:
                # Left here, this file is invisible: no transport
                # posts it, and the job it finished stays leased.
                # Set it aside so the runner can answer with a stub.
                refuse_result(
                    channel, fname,
                    f"{os.path.getsize(path)} bytes exceeds the "
                    f"{FILE_MAX_BYTES}-byte cap")
                continue
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            # A result file that is not text will never post. Left
            # here it is invisible, and the queue acks the job as
            # if the core had produced nothing.
            if result_file_id(fname):
                refuse_result(channel, fname,
                              "result file is not UTF-8")
            continue
        except OSError as e:
            # Unreadable (a mode the process cannot open). Left
            # here it is invisible, and the queue acks the job
            # with nothing stored. The owner can still move it
            # aside for the stub.
            if result_file_id(fname):
                refuse_result(
                    channel, fname,
                    "result file could not be read: %s" % e)
            continue
        parsed = parse_envelope(text)
        if parsed is None:
            # Same hole: no blank line, so no transport posts it,
            # and it is not "no result". A sidecar is not a result
            # file and stays where the pipe reads it.
            if result_file_id(fname):
                refuse_result(
                    channel, fname,
                    "malformed envelope (no blank line between "
                    "subject and body)")
            continue
        out.append((fname, parsed[0], parsed[1]))
    return out


def refuse_result(channel, fname, reason):
    """A result the far end refused for good: moved to
    outbox/failed/ beside a <id>.refused.txt that carries the
    reason, so the runner's next pass can answer it with a stub
    and the queue behind it keeps moving. Never raises.

    The sweep opens <id>.result.txt. A collision name
    (j1.result-2.txt) does not end in .result.txt, and leaving
    it under that name meant the sweep never saw the body, wrote
    no stub, and the job stayed leased."""
    d = dirs(channel)
    failed = os.path.join(d["outbox"], "failed")
    named_id = result_file_id(fname)
    stem = named_id or fname
    dest_name = (stem + ".result.txt") if named_id else fname
    try:
        os.makedirs(failed, exist_ok=True)
        os.replace(os.path.join(d["outbox"], fname),
                   os.path.join(failed, dest_name))
        _atomic_write(os.path.join(failed, stem + ".refused.txt"),
                      str(reason).replace("\r", " ").replace("\n", " ")
                      + "\n")
        log(f"result {fname} refused for good: {reason}; set aside under "
            f"outbox/failed/ for the runner's stub", "WARN")
    except OSError as e:
        log(f"cannot set aside refused result {fname}: {e}", "WARN")


def refuse_symlink_result(channel, fname):
    """A result name that is a symlink is not a result. The link
    is removed without being followed, and a real empty file is
    left where the sweep looks, so the job gets a stub instead
    of being acked with nothing stored."""
    d = dirs(channel)
    named_id = result_file_id(fname)
    if not named_id:
        return
    failed = os.path.join(d["outbox"], "failed")
    src = os.path.join(d["outbox"], fname)
    dest = os.path.join(failed, named_id + ".result.txt")
    reason = "result file was a symlink; not followed"
    try:
        os.makedirs(failed, exist_ok=True)
        if not os.path.lexists(dest):
            _atomic_write(dest, "")
        _atomic_write(os.path.join(failed, named_id + ".refused.txt"),
                      reason + "\n")
        os.unlink(src)
    except OSError as e:
        log(f"cannot set aside symlink result {fname}: {e}", "WARN")
        return
    log(f"result {fname} refused for good: {reason}; set aside under "
        f"outbox/failed/ for the runner's stub", "WARN")


def ack_result(channel, fname):
    d = dirs(channel)
    try:
        os.replace(os.path.join(d["outbox"], fname),
                   os.path.join(d["outbox_done"], fname))
    except OSError as e:
        log(f"cannot move result {fname} to done: {e}", "WARN")


def poll_interval(cfg, default=2.0):
    """Seconds between passes: extension_poll_interval_sec, default 2.

    A usable number is clamped to [0.2, 60]. A boolean (true once
    meant a one-second cadence, false the 0.2 floor), a huge
    integer (once a raw OverflowError out of this reader), infinity,
    NaN, or a non-number is not an interval and reads as the default.
    """
    raw = cfg.get("extension_poll_interval_sec", default) \
        if isinstance(cfg, dict) else default
    if isinstance(raw, bool):
        return default
    if isinstance(raw, str):
        try:
            raw = float(raw)
        except ValueError:
            return default
    if not isinstance(raw, (int, float)):
        return default
    try:
        n = float(raw)
    except (OverflowError, ValueError):
        return default
    if n != n or n in (float("inf"), float("-inf")):
        return default
    return max(0.2, min(60.0, n))


def nap(seconds):
    time.sleep(seconds)
