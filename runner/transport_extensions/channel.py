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

Stdlib only.
"""

import json
import os
import sys
import time
import uuid

FILE_MAX_BYTES = 4 * 1024 * 1024


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
    tmp = path + ".tmp-" + uuid.uuid4().hex[:8]
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def deliver_job(channel, ident, subject, body):
    """Drop one job envelope in the runner's inbox. `ident` is
    this transport's stable id for the job (the file
    transport's file name, the broker's reply subject tail, the
    message's own id); the file lands as <ident>.job.txt so a
    redelivery of the same job rewrites the same file."""
    d = dirs(channel)
    safe = "".join(c if (c.isalnum() or c in "._-") else "_"
                   for c in str(ident))[:120] or "job"
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
        if fname == "done":
            continue
        path = os.path.join(d["outbox"], fname)
        if not os.path.isfile(path) or os.path.islink(path):
            continue
        try:
            if os.path.getsize(path) > FILE_MAX_BYTES:
                continue
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        parsed = parse_envelope(text)
        if parsed is None:
            continue
        out.append((fname, parsed[0], parsed[1]))
    return out


def ack_result(channel, fname):
    d = dirs(channel)
    try:
        os.replace(os.path.join(d["outbox"], fname),
                   os.path.join(d["outbox_done"], fname))
    except OSError as e:
        log(f"cannot move result {fname} to done: {e}", "WARN")


def poll_interval(cfg, default=2.0):
    raw = cfg.get("extension_poll_interval_sec", default)
    try:
        return max(0.2, min(60.0, float(raw)))
    except (TypeError, ValueError):
        return default


def nap(seconds):
    time.sleep(seconds)
