"""Transport extensions: the contract, discovery, and supervision.

The runner core is transport-blind. Every job transport -- email,
the watched folder, core NATS, and any pipe an owner drops in --
is a standalone extension program living in a folder with an
`extension.json` manifest of kind "transport". The runner never
imports extension code. It discovers enabled transport
extensions, supervises them as child processes, and talks to
them through one file channel per extension under the base dir:

    <base_dir>/transport-extensions/<name>/inbox/
        Job envelopes, extension -> runner. A job envelope is a
        subject line, a blank line, then the signed body -- the
        exact shape runner/cloud/send_job.py prints.
    <base_dir>/transport-extensions/<name>/outbox/
        Result envelopes, runner -> extension, same shape. The
        extension carries each result home over its own pipe.
        When the core knows the job's validated reply_to, a
        sidecar <ident>.target.txt sits beside the result file
        holding that single address: the extension sends the
        result there instead of its own default destination.
        (A pipe cannot always read the address out of the job
        itself -- an encrypted job's envelope does not carry it
        in the clear, and a pipe never holds the secret.) An
        extension that does not read the sidecar behaves exactly
        as before; the sidecar is additive at contract v1.

Ack is consumption: the runner moves a processed job file into
inbox/done/ (never deletes), and an extension moves a delivered
result into outbox/done/. The HMAC signature on the body is
checked by the runner's core for every job on every transport,
after the pipe delivers; a transport's own credentials, where it
has them, are a first gate in front of that check (the NATS
extension requires broker authentication by default).

The contract is versioned at one: TRANSPORT_API_VERSION = 1.
Every transport manifest declares `api_version`; the runner
refuses (logs, skips, keeps running) a transport extension
declaring any other version. There is no negotiation machinery:
one version number, stated in the manifest, checked once.

Registration is for discovery and for a future lockdown to pin;
it is never a permission to run. The loader consults NO catalog
or registry: a folder with a valid transport manifest in the
extensions directory loads and runs, registered or not. The
first-party transports (email, file, nats) ship as extension
folders under runner/transport_extensions/ and are found the
same way; a same-named folder in the owner's extensions
directory wins over the shipped one.

Stdlib only, like the rest of the runner. This module imports
nothing from runner.py; the runner passes its log function in.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid

try:  # package context (runner.wire.transports)
    from runner.ops import extensions as _extensions
except Exception:  # pragma: no cover - sibling context
    try:
        from ..ops import extensions as _extensions  # type: ignore
    except Exception:
        from ops import extensions as _extensions  # type: ignore
try:  # the atomic writer (runner/guard/atomicio.py)
    from runner.guard import atomicio as _atomicio
except Exception:  # pragma: no cover - sibling context
    try:
        from ..guard import atomicio as _atomicio  # type: ignore
    except Exception:
        from guard import atomicio as _atomicio  # type: ignore
try:  # the extension review (runner/guard/extreview.py)
    from runner.guard import extreview as _extreview
except Exception:  # pragma: no cover - sibling context
    try:
        from ..guard import extreview as _extreview  # type: ignore
    except Exception:
        try:
            from guard import extreview as _extreview  # type: ignore
        except Exception:
            _extreview = None

TRANSPORT_API_VERSION = 1

# First-party transport names (also the names a fresh install's
# discovery finds under runner/transport_extensions/). Enabled
# names are NOT limited to these: any valid transport manifest
# in the extensions directory is loadable, registered or not.
FIRST_PARTY_TRANSPORTS = ("email", "file", "nats", "dtls")

DEFAULT_TRANSPORTS = ["email"]

# A channel job file larger than this is refused unread. It
# matches the mail path's default max_job_bytes so a job that
# fits one pipe fits the other.
FILE_MAX_BYTES = 4 * 1024 * 1024

_NAME_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_RESULT_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+(?:result|qresult)\s+(\S+)", re.I)
_JOB_ID_RE = re.compile(
    r"\[HOMING-PIGEON\](?:\s+\S+)*\s+job\s+(\S+)", re.I)


class TransportError(Exception):
    """A transport failed; the runner logs it and carries on."""


def _silent_log(msg, level="INFO"):
    pass


_EXTENSION_LINE_RE = re.compile(
    r"^(INFO|WARN|WARNING|ERROR|DEBUG):[ \t]*(.*)$")


def _extension_line_parts(text):
    """(level, message) for one line of extension output.

    Transport extensions log "LEVEL: message" (see
    transport_extensions/channel.py). A line with that prefix
    keeps its level; WARNING normalizes to the runner log's
    WARN. Anything else -- a traceback frame, a plain print --
    is INFO with the text untouched.
    """
    m = _EXTENSION_LINE_RE.match(text)
    if not m:
        return "INFO", text
    level = m.group(1)
    if level == "WARNING":
        level = "WARN"
    return level, m.group(2)


# ------------------------------------------------------------------
# The envelope
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Configuration: which transport extensions are enabled
# ------------------------------------------------------------------

def enabled_transports(cfg):
    """The enabled transport extension names for this config.

    `transports` may be a list or a comma-separated string.
    Absent means the default, ["email"] -- email is the default
    transport, as the default-enabled transport extension. Names
    are validated for shape only; whether a name has a loadable
    extension is discovery's question (see
    discover_transport_extensions), because an unregistered
    drop-in is a first-class citizen here. Raises ValueError on
    a malformed value.
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
        if not _NAME_RE.match(name):
            raise ValueError(
                f"invalid transport name {name!r}: names are "
                f"letters, digits, '.', '_' or '-', starting with "
                f"a letter or digit")
        if name not in out:
            out.append(name)
    if not out:
        raise ValueError("transports names no transport")
    return out


# ------------------------------------------------------------------
# Discovery: manifests, no catalog, no registry check
# ------------------------------------------------------------------

def _extensions_dir_for(cfg, base_dir):
    raw = cfg.get("extensions_dir") if isinstance(cfg, dict) else None
    if isinstance(raw, str) and raw.strip():
        if os.path.isabs(raw) or not base_dir:
            return raw
        return os.path.join(base_dir, raw)
    if base_dir:
        return os.path.join(base_dir, "extensions")
    return ""


def builtin_transport_roots():
    """Where the shipped first-party transport extensions live."""
    roots = []
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    roots.append(os.path.join(here, "transport_extensions"))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(os.path.join(meipass,
                                  "pigeon-transport-extensions"))
        roots.append(os.path.join(meipass, "transport_extensions"))
    exe = getattr(sys, "executable", "") or ""
    if exe:
        roots.append(os.path.join(
            os.path.dirname(os.path.abspath(exe)),
            "transport_extensions"))
    return roots


def discover_transport_extensions(cfg, base_dir, log=None,
                                  event_sink=None):
    """Find every loadable transport extension, by manifest name.

    Returns (registry, problems): registry maps name -> cleaned
    manifest (plus "dir"). Two roots are scanned: the owner's
    extensions directory FIRST (a same-named drop-in wins over a
    shipped transport), then the shipped first-party folders.
    No catalog or registry is consulted for either root: a valid
    manifest with api_version == TRANSPORT_API_VERSION is
    sufficient. A manifest declaring any other transport API
    version is refused with a readable problem line; the runner
    keeps running without it.

    Every folder then passes the extension review
    (runner/guard/extreview.py) before it is returned: its code is
    held to its manifest -- capabilities declared, `entry` inside
    the folder, no symlinks, nothing that does not compile. Under
    the owner's `enforce` posture a folder with a high finding is
    refused here like a bad manifest; a drop-in that shadows a
    shipped transport is loaded and said out loud. `log` and
    `event_sink` receive the review's lines and security events.
    """
    registry = {}
    problems = []
    roots = []
    user_dir = _extensions_dir_for(cfg, base_dir)
    if user_dir:
        roots.append(user_dir)
    shipped_roots = builtin_transport_roots()
    roots.extend(shipped_roots)
    scanned = []
    for root in roots:
        found, probs = _extensions.load_extensions(
            root, kinds=("transport",))
        for prob in probs:
            problems.append(f"{root}: {prob}")
        usable = {}
        for name, manifest in found.items():
            if manifest.get("api_version") != TRANSPORT_API_VERSION:
                problems.append(
                    f"transport extension {name!r}: refused: it "
                    f"declares transport API "
                    f"v{manifest.get('api_version')}; this runner "
                    f"speaks v{TRANSPORT_API_VERSION}")
                continue
            usable[name] = manifest
        scanned.append((root, usable))
    shipped_names = set()
    for root, usable in scanned:
        if root in shipped_roots:
            shipped_names.update(usable)
    shadows = set()
    for root, usable in scanned:
        if root not in shipped_roots:
            shadows.update(set(usable) & shipped_names)
    for root, usable in scanned:
        for name, manifest in usable.items():
            if name in registry:
                continue  # an earlier root already claimed the name
            registry[name] = manifest
    # One review over the claimed set. A drop-in refused here is
    # absent, and the shipped transport it shadowed does not step
    # in for it: the owner installed the drop-in, and a silent
    # substitution would run a pipe the owner did not pick. The
    # refusal line and the "no loadable transport extension" line
    # say what happened.
    if _extreview is not None and registry:
        try:
            registry, refusals, _report = _extreview.apply(
                cfg, base_dir, registry, kind="transport",
                shipped_dirs=shipped_roots, shadows=shadows,
                log=log, event_sink=event_sink)
            problems.extend(refusals)
        except Exception as e:  # the review never takes the runner down
            if log is not None:
                log(f"extension review failed: {e}", "WARN")
    return registry, problems


# ------------------------------------------------------------------
# The channel: one inbox/outbox pair per extension
# ------------------------------------------------------------------

def channel_root(base_dir, name):
    return os.path.join(base_dir, "transport-extensions", name)


def channel_paths(base_dir, name):
    root = channel_root(base_dir, name)
    return {
        "root": root,
        "inbox": os.path.join(root, "inbox"),
        "inbox_done": os.path.join(root, "inbox", "done"),
        "outbox": os.path.join(root, "outbox"),
        "outbox_done": os.path.join(root, "outbox", "done"),
    }


def ensure_channel_dirs(base_dir, name):
    paths = channel_paths(base_dir, name)
    for key in ("inbox", "inbox_done", "outbox", "outbox_done"):
        os.makedirs(paths[key], exist_ok=True)
    return paths


def _atomic_write(path, text):
    _atomicio.write_text(path, text)


def write_channel_result(base_dir, name, job_subject, subject, body,
                         ident_hint=None, target=None):
    """Drop one result envelope into an extension's outbox.

    The result file is named for the job that produced it: the
    channel ident the extension delivered the job under when
    there is one (the contract's correlation key), else the job
    id parsed from the subjects.

    `target`, when given, is the job's validated reply_to: the
    core's own rule (mailbox._valid_reply_to), applied where the
    job was parsed and the address verified. It is written
    verbatim to a <ident>.target.txt sidecar beside the result
    file; an unvalidated address must never be passed here, and
    none is derived in this module -- transports carry, they do
    not decide."""
    paths = ensure_channel_dirs(base_dir, name)
    rid = None
    if ident_hint:
        rid = str(ident_hint)
    if not rid:
        m = _RESULT_ID_RE.search(subject or "")
        if m:
            rid = m.group(1)
    if not rid:
        m = _JOB_ID_RE.search(job_subject or "")
        rid = m.group(1) if m else "unknown"
    rid = re.sub(r"[^A-Za-z0-9._-]", "_", rid)
    base = os.path.join(paths["outbox"], f"{rid}.result.txt")
    path = base
    n = 2
    while os.path.exists(path):
        path = os.path.join(paths["outbox"], f"{rid}.result-{n}.txt")
        n += 1
    text = format_envelope(subject, body)
    if body and not body.endswith("\n"):
        text += "\n"
    _atomic_write(path, text)
    if isinstance(target, str) and target.strip():
        fname = os.path.basename(path)
        stem = fname[:-len(".result.txt")] \
            if fname.endswith(".result.txt") else fname
        _atomic_write(os.path.join(paths["outbox"],
                                   stem + ".target.txt"),
                      target.strip() + "\n")
    return path


class IncomingMessage:
    """One job envelope delivered through a channel, plus where
    its results go. reply() drops a result envelope in the
    extension's outbox; ack() moves the job file to inbox/done.
    """

    def __init__(self, subject, body, reply, ack=None, ident=""):
        self.subject = subject
        self.body = body
        self._reply = reply
        self._ack = ack
        self.ident = ident

    def reply(self, subject, body, target=None):
        self._reply(subject, body, target)

    def ack(self):
        """Consume the message. Returns what the channel's ack
        returns: False when the channel refused to consume (the
        envelope changed after the read, the move failed), so the
        caller can roll back what it recorded for it (Q25); None
        for a channel with no ack."""
        if self._ack is not None:
            return self._ack()
        return None


def fetch_channel_messages(base_dir, name, log=None):
    """Every job envelope waiting in one extension's channel
    inbox, as IncomingMessages. Refusals mirror the local-inbox
    discipline: symlinks and oversize files are refused unread,
    malformed envelopes are consumed with the reason logged --
    each refusal still returns an ack-only message so a poison
    file cannot wedge the channel."""
    log = log or _silent_log
    paths = ensure_channel_dirs(base_dir, name)
    out = []
    for fname in sorted(os.listdir(paths["inbox"])):
        if fname == "done":
            continue
        path = os.path.join(paths["inbox"], fname)
        if not os.path.isfile(path) and not os.path.islink(path):
            continue

        def ack(path=path, fname=fname):
            try:
                os.replace(path, os.path.join(paths["inbox_done"],
                                              fname))
            except OSError as e:
                log(f"transport {name}: cannot move {fname} to "
                    f"done: {e}", "WARN")

        def refuse(why, fname=fname):
            log(f"transport {name}: {fname}: refused: {why}",
                "WARN")
            return IncomingMessage("", "",
                                   lambda s, b, target=None: None,
                                   ack=ack, ident=fname)

        if os.path.islink(path):
            out.append(refuse("symlink job files are not read"))
            continue
        try:
            with open(path, "rb") as f:
                raw = f.read()
            with open(path, "rb") as f:
                again = f.read()
        except OSError as e:
            out.append(refuse(f"cannot read: {e}"))
            continue
        # A rewrite during the read (same length, same second)
        # does not move mtime_ns. Compare the bytes themselves.
        digest = hashlib.sha256(raw).hexdigest()
        if hashlib.sha256(again).hexdigest() != digest:
            continue
        if len(again) > FILE_MAX_BYTES:
            out.append(refuse(f"{len(again)} bytes exceeds the "
                              f"{FILE_MAX_BYTES}-byte cap"))
            continue
        try:
            text = again.decode("utf-8")
        except UnicodeDecodeError as e:
            out.append(refuse(f"cannot read as UTF-8: {e}"))
            continue
        parsed = parse_envelope(text)
        if parsed is None:
            out.append(refuse("malformed envelope (no blank line "
                              "between subject and body)"))
            continue
        subject, body = parsed
        stem = fname[:-len(".job.txt")] \
            if fname.endswith(".job.txt") else fname

        def ack_read(path=path, fname=fname, digest=digest):
            try:
                with open(path, "rb") as f:
                    now = hashlib.sha256(f.read()).hexdigest()
            except OSError as e:
                log(f"transport {name}: cannot move {fname} to "
                    f"done: {e}", "WARN")
                return False
            if now != digest:
                log(f"transport {name}: {fname} changed after it "
                    f"was read; leaving the new bytes", "WARN")
                return False
            try:
                os.replace(path, os.path.join(paths["inbox_done"],
                                              fname))
            except OSError as e:
                log(f"transport {name}: cannot move {fname} to "
                    f"done: {e}", "WARN")
                return False
            return True

        def reply(rsubject, rbody, target=None,
                  job_subject=subject, stem=stem):
            write_channel_result(base_dir, name, job_subject,
                                 rsubject, rbody, ident_hint=stem,
                                 target=target)

        out.append(IncomingMessage(subject, body, reply, ack=ack_read,
                                   ident=fname))
    return out


def service_channel(base_dir, name, process_message, log=None,
                    dry_run=False):
    """One runner cycle for one extension's channel.

    Hand every waiting envelope to process_message(subject, body).
    The return is a sequence of (subject, body) or
    (subject, body, target) replies. Each reply is written to
    the outbox. A reply may carry the result's validated
    reply_to as its third element; that becomes the target
    sidecar.

    The sequence may set ``consume`` false. The envelope then
    stays in the inbox so the next cycle can retry it. That is
    the mail rule: a result that did not land is not finished.
    A processor that raises is still consumed, so one bad
    callback cannot wedge the channel. If writing a reply
    raises, the envelope is not consumed. ``requeue`` on the
    sequence (``rollback`` when there is no requeue), when
    callable, runs in that case so the result recorded before the
    write is re-queued for the core's resend pass (the job is not
    run again: it is seen). An ack that fails after the replies
    landed calls ``rollback`` (Q25) -- the core's has nothing to
    undo then, since the result is in the outbox and a re-read of
    the envelope is a replay the seen-set answers -- and leaves
    the envelope for the next cycle.

    Dry-run acks nothing. Returns how many envelopes were
    visited, consumed or not.
    """
    log = log or _silent_log
    messages = fetch_channel_messages(base_dir, name, log=log)
    for msg in messages:
        consume = True
        rollback = None
        requeue = None
        try:
            replies = process_message(msg.subject, msg.body)
            if replies is None:
                replies = []
            consume = bool(getattr(replies, "consume", True))
            rollback = getattr(replies, "rollback", None)
            requeue = getattr(replies, "requeue", None) or rollback
            try:
                for reply in replies:
                    rsubject, rbody = reply[0], reply[1]
                    target = reply[2] if len(reply) > 2 else None
                    msg.reply(rsubject, rbody, target=target)
            except Exception as e:
                # The effect did not stick. Leave the envelope
                # where the next cycle will see it.
                log(f"transport {name}: message "
                    f"{msg.ident or '?'} result did not land: "
                    f"{e!r}", "ERROR")
                consume = False
        except Exception as e:
            log(f"transport {name}: message {msg.ident or '?'} "
                f"failed: {e!r}", "ERROR")
        if not consume and callable(requeue):
            try:
                requeue()
            except Exception as e:
                log(f"transport {name}: rollback failed for "
                    f"{msg.ident or '?'}: {e}", "WARN")
        if not dry_run and consume:
            acked = True
            try:
                acked = msg.ack()
            except Exception as e:
                log(f"transport {name}: ack failed for "
                    f"{msg.ident or '?'}: {e}", "WARN")
                acked = False
            if acked is False and callable(rollback):
                try:
                    rollback()
                except Exception as e:
                    log(f"transport {name}: rollback failed for "
                        f"{msg.ident or '?'}: {e}", "WARN")
    return len(messages)


# ------------------------------------------------------------------
# Supervision: enabled transport extensions as child processes
# ------------------------------------------------------------------

_MAILBOX_KEYS = (
    "mailbox_user", "mailbox_password", "imap_host", "imap_port",
    "smtp_host", "smtp_port", "auth", "oauth_client_id",
    "oauth_client_secret", "oauth_refresh_token",
    "mail_tls_required",
)


def _read_secret_file_quiet(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _dtls_secret_material(cfg):
    """The PSK material the dtls extension terminates
    authentication with, resolved from the same sources the
    core's build_secrets() accepts (inline values or secret
    files). The core entropy-validates these values at
    startup; this only resolves them for the handoff. Nothing
    here is ever logged."""
    out = {}
    default = cfg.get("shared_secret")
    if not isinstance(default, str):
        default = ""
    if not default and isinstance(cfg.get("shared_secret_file"),
                                  str):
        default = _read_secret_file_quiet(cfg["shared_secret_file"])
    if default:
        out["shared_secret"] = default
    extra = {}
    inline = cfg.get("additional_secrets")
    if isinstance(inline, dict):
        for kid, sec in inline.items():
            if isinstance(kid, str) and isinstance(sec, str) \
                    and sec:
                extra[kid] = sec
    files = cfg.get("additional_secrets_files")
    if isinstance(files, dict):
        for kid, path in files.items():
            if isinstance(kid, str) and isinstance(path, str) \
                    and kid not in extra:
                sec = _read_secret_file_quiet(path)
                if sec:
                    extra[kid] = sec
    if extra:
        out["additional_secrets"] = extra
    return out


def _runtime_config(cfg, name, base_dir, paths):
    """The config one extension process is handed: its own
    transport block (transport_<name>), the mailbox keys for the
    email extension, and the shared cadence keys. The core's
    other config is NOT handed over: verification is the core's
    job, never a carrying pipe's. Two exceptions are pipes that
    terminate something themselves: the email pipe owns the
    mailbox, so it gets the mailbox keys; the dtls pipe
    terminates DTLS-PSK authentication, so it gets the secret
    material it authenticates with (and the greeting posture).
    A job arriving over dtls still faces the core's signature
    check exactly like any other transport's."""
    out = {
        "name": name,
        "base_dir": base_dir,
        "channel_dir": paths["root"],
        "poll_interval_sec": cfg.get("poll_interval_sec", 20)
        if isinstance(cfg, dict) else 20,
    }
    if isinstance(cfg, dict):
        block = cfg.get(f"transport_{name}")
        if isinstance(block, dict):
            out.update(block)
            out["transport"] = dict(block)
        if name == "email":
            for key in _MAILBOX_KEYS:
                if key in cfg:
                    out[key] = cfg[key]
        if name == "dtls":
            out.update(_dtls_secret_material(cfg))
            # The greeting's platform card names the default
            # interpreter and the protocol versions this runner
            # speaks (runner/wire/platformcard.py), so those two ride too.
            for key in ("dtls_greeting", "default_interpreter",
                        "protocol_v2"):
                if key in cfg:
                    out[key] = cfg[key]
    return out


def _write_runtime_config(paths, payload):
    path = os.path.join(paths["root"], "runtime-config.json")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                     0o600)
    except OSError:
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, indent=1, sort_keys=True))
        return path
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=1, sort_keys=True))
    return path


def _substitute(token, subs):
    out = token
    for key, value in subs.items():
        out = out.replace("{" + key + "}", value)
    return out


class TransportSupervisor:
    """Starts, watches, and restarts the enabled transport
    extension processes for one runner.

    A dead extension is restarted with backoff (1s doubling to
    a 30s cap) and a log line; its death never takes the runner
    or the other transports down -- each extension is its own
    process with its own channel, and every failure here is
    caught, logged, and left for the next check.

    Each child's stdout/stderr goes through a pump thread (one
    per process start): every line is relayed into the runner's
    own log -- "transport <name>: <line>", with a WARN:/ERROR:
    prefix keeping its level -- and appended, timestamped in
    the runner-log style, to the transport's extension.log
    sidecar. The pump always drains the pipe, so a chatty child
    can never block on a full one, and a failing transport is
    visible in runner.log instead of only in the sidecar.
    """

    def __init__(self, cfg, base_dir, log=None, popen=None,
                 clock=None, event_sink=None):
        self.cfg = cfg if isinstance(cfg, dict) else {}
        self.base_dir = base_dir
        self.log = log or _silent_log
        self._popen = popen or subprocess.Popen
        self._clock = clock or time.monotonic
        self.names = enabled_transports(self.cfg)
        self.registry, self.problems = \
            discover_transport_extensions(self.cfg, base_dir,
                                          log=self.log,
                                          event_sink=event_sink)
        self.missing = [n for n in self.names
                        if n not in self.registry]
        self.processes = {}   # name -> record dict
        self.stopped = False

    # -- lifecycle ------------------------------------------------
    def start(self):
        for prob in self.problems:
            self.log(f"transport extensions: {prob}", "WARN")
        for name in self.missing:
            self.log(f"transport {name}: no loadable transport "
                     f"extension found with that name", "ERROR")
        for name in self.names:
            if name in self.registry:
                self._start_one(name)
        return self

    def _start_one(self, name):
        manifest = self.registry[name]
        paths = ensure_channel_dirs(self.base_dir, name)
        config_path = _write_runtime_config(
            paths, _runtime_config(self.cfg, name, self.base_dir,
                                   paths))
        subs = {
            "python": sys.executable,
            "self": sys.executable,
            "extension_dir": manifest["dir"],
            "channel_dir": paths["root"],
            "runtime_config": config_path,
            "base_dir": self.base_dir,
            "name": name,
        }
        argv = [_substitute(str(part), subs)
                for part in manifest["entry"]]
        if getattr(sys, "frozen", False) and len(argv) >= 2 \
                and argv[0] == sys.executable and argv[1] == "-m":
            argv = [sys.executable, "--transport-extension-module",
                    argv[2]] + argv[3:]
        env = dict(os.environ)
        # mutmut's stats run sets MUTANT_UNDER_TEST=stats and rewrites
        # the mutated module with trampolines. A child that inherits
        # the variable takes the stats path, which needs mutmut's
        # in-process context, and dies on the first call (exit 1).
        # The extension is a sidecar. It runs the original code.
        env.pop("MUTANT_UNDER_TEST", None)
        if not getattr(sys, "frozen", False):
            # First-party entries run as `-m runner...`: the
            # package parent must be importable from the child's
            # cwd (the extension folder).
            pkg_parent = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
            existing = env.get("PYTHONPATH", "")
            parts = existing.split(os.pathsep) if existing else []
            if pkg_parent not in parts:
                env["PYTHONPATH"] = os.pathsep.join(
                    [pkg_parent] + parts)
        env["HOMING_PIGEON_TRANSPORT_NAME"] = name
        env["HOMING_PIGEON_TRANSPORT_CHANNEL"] = paths["root"]
        env["HOMING_PIGEON_TRANSPORT_CONFIG"] = config_path
        env["HOMING_PIGEON_BASE_DIR"] = self.base_dir
        log_path = os.path.join(paths["root"], "extension.log")
        rec = {"manifest": manifest, "restarts": 0,
               "next_restart": None, "started": self._clock(),
               "argv": argv, "settled": False, "logfh": None}
        try:
            kw = {"cwd": manifest["dir"], "env": env,
                  "stdin": subprocess.DEVNULL,
                  "stdout": subprocess.PIPE,
                  "stderr": subprocess.STDOUT}
            if os.name == "posix":
                kw["start_new_session"] = True
            elif os.name == "nt":
                kw["creationflags"] = getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            rec["proc"] = self._popen(argv, **kw)
            stream = getattr(rec["proc"], "stdout", None)
            if stream is not None:
                pump = threading.Thread(
                    target=self._pump_extension_log,
                    args=(name, stream, log_path),
                    name=f"transport-{name}-log-pump", daemon=True)
                rec["pump"] = pump
                pump.start()
        except Exception as e:
            self.log(f"transport {name}: cannot start "
                     f"{manifest['entry']}: {e}", "ERROR")
            rec["proc"] = None
            rec["next_restart"] = self._clock() + 1.0
        self.processes[name] = rec
        if rec.get("proc") is not None:
            self.log(f"transport {name}: extension "
                     f"{manifest['name']} v{manifest['version']} "
                     f"by {manifest['publisher']} started "
                     f"(pid {rec['proc'].pid})")
        return rec

    def _pump_extension_log(self, name, stream, log_path):
        """Drain one child's stdout until EOF, line by line.

        Every line is relayed into the runner's log (attributed
        to the transport, level preserved) and appended to the
        transport's extension.log with the runner log's
        timestamp style. The sidecar used to be the child's own
        stdout target; it is now written here so the runner log
        -- the operator's console -- sees transport failures the
        moment they happen, not on the next forensic dig.

        The pump must never stop draining: a child that fills
        its pipe buffer would block forever, so nothing in this
        loop may raise. The handle is opened lazily and closed
        at EOF; if the supervisor's shutdown closed the path's
        handle state mid-drain the write side reopens once. The
        pump deliberately does NOT go through self.log's owner
        for the sidecar -- the file is the unfiltered record;
        the runner log applies its own rate discipline on top.
        """
        fh = None

        def write_sidecar(text):
            nonlocal fh
            stamp = time.strftime("%Y-%m-%d %H:%M:%S",
                                  time.localtime())
            level, message = _extension_line_parts(text)
            if _EXTENSION_LINE_RE.match(text):
                entry = f"{stamp} [{level}] {message}\n"
            else:
                entry = f"{stamp} {text}\n"
            data = entry.encode("utf-8", "replace")
            if fh is None:
                fh = open(log_path, "ab")
            try:
                fh.write(data)
                fh.flush()
            except (OSError, ValueError):
                # Closed under us (shutdown raced the drain):
                # reopen once and retry so the tail is not lost.
                try:
                    fh = open(log_path, "ab")
                    fh.write(data)
                    fh.flush()
                except OSError:
                    fh = None

        try:
            for raw in stream:
                try:
                    line = raw.decode(
                        "utf-8", "replace").rstrip("\r\n")
                    if not line.strip():
                        # Blank lines carry no signal; neither
                        # sink repeats them.
                        continue
                    level, message = _extension_line_parts(line)
                    try:
                        self.log(f"transport {name}: {message}",
                                 level)
                    except Exception:
                        # A broken log call must not stop the
                        # drain or lose the sidecar copy.
                        pass
                    try:
                        write_sidecar(line)
                    except Exception:
                        pass
                except Exception:
                    # A poisoned line never stops the pump.
                    continue
        except Exception:
            # The stream itself broke (the child died hard); the
            # supervisor's check() owns the restart.
            pass
        finally:
            if fh is not None:
                try:
                    fh.close()
                except Exception:
                    pass

    def check(self):
        """Restart whatever died since the last check."""
        if self.stopped:
            return
        now = self._clock()
        for name, rec in list(self.processes.items()):
            proc = rec.get("proc")
            if proc is not None and proc.poll() is None:
                if now - rec["started"] > 60:
                    rec["restarts"] = 0
                continue
            if proc is not None and rec.get("reported") is not proc:
                self.log(f"transport {name}: extension exited "
                         f"(code {proc.poll()}); will restart "
                         f"with backoff", "WARN")
                rec["reported"] = proc
                # extension.log is the pump thread's handle now;
                # it closes when the dead child's pipe hits EOF,
                # after the buffered tail has been drained into
                # both sinks. Nothing to close here.
                backoff = min(30.0, float(2 ** rec["restarts"]))
                rec["next_restart"] = now + backoff
            if rec.get("next_restart") is not None \
                    and now >= rec["next_restart"]:
                rec["restarts"] += 1
                rec["next_restart"] = None
                self._start_one(name)

    def settle(self):
        """After a fresh start, give fast extensions a brief
        moment to deliver what is already waiting (each manifest
        declares its own startup_settle_ms; network transports
        declare 0 and never hold the cycle up). Runs once per
        process start, restarts included."""
        for name, rec in self.processes.items():
            if rec.get("settled"):
                continue
            rec["settled"] = True
            ms = rec["manifest"].get("startup_settle_ms") or 0
            if not ms:
                continue
            paths = channel_paths(self.base_dir, name)
            deadline = time.monotonic() + ms / 1000.0
            while time.monotonic() < deadline:
                try:
                    waiting = [f for f in os.listdir(paths["inbox"])
                               if f != "done"]
                except OSError:
                    waiting = []
                if waiting:
                    break
                time.sleep(0.02)

    def stop(self):
        self.stopped = True
        for name, rec in list(self.processes.items()):
            proc = rec.get("proc")
            try:
                if proc is not None and proc.poll() is None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    if not _wait_down(proc, 3):
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        _wait_down(proc, 1)
            finally:
                # extension.log belongs to the pump thread now.
                # With the child down, its pipe is at EOF and
                # the pump closes the file after draining the
                # tail; give it a bounded moment so the handle
                # is released before stop returns (Windows will
                # not delete the file while it is open). The
                # pump is a daemon: even a join timeout cannot
                # hang shutdown.
                pump = rec.get("pump")
                if pump is not None:
                    pump.join(timeout=3)
            self.processes.pop(name, None)


# One supervisor per (base dir, config signature) in this
# process: main() starts it, poll cycles reuse it, tests start
# and stop their own.
_SLEEP = time.sleep


def _wait_down(proc, seconds):
    """Wait until proc exits, without calling time.sleep by name.

    proc.wait(timeout) polls through time.sleep. Tests replace that
    with a sleep that raises KeyboardInterrupt, which used to abort
    shutdown before extension.log was closed. A saved function is not
    the patched one. Returns False if the process is still alive.
    """
    deadline = time.monotonic() + seconds
    while proc.poll() is None:
        if time.monotonic() >= deadline:
            return False
        _SLEEP(0.05)
    return True


_ACTIVE_SUPERVISORS = {}


def _config_signature(cfg, base_dir):
    if not isinstance(cfg, dict):
        return (base_dir, "")
    keys = {"transports": cfg.get("transports"),
            "extensions_dir": cfg.get("extensions_dir"),
            "poll_interval_sec": cfg.get("poll_interval_sec")}
    for key, value in cfg.items():
        if key.startswith("transport_") or key in _MAILBOX_KEYS:
            keys[key] = value
    enabled = cfg.get("transports")
    if isinstance(enabled, (list, tuple)) and "dtls" in enabled:
        # The dtls pipe authenticates with the secret itself,
        # so a secret or greeting change must restart it.
        for key in ("shared_secret", "shared_secret_file",
                    "additional_secrets", "additional_secrets_files",
                    "dtls_greeting", "default_interpreter", "protocol_v2"):
            if key in cfg:
                keys[key] = cfg[key]
    try:
        blob = json.dumps(keys, sort_keys=True, default=str)
    except (TypeError, ValueError):
        blob = str(sorted(keys))
    return (base_dir, blob)


def start_supervisor(cfg, base_dir, log=None, event_sink=None):
    """Start (or reuse) the supervisor for this config and base
    dir. Returns the TransportSupervisor."""
    key = _config_signature(cfg, base_dir)
    sup = _ACTIVE_SUPERVISORS.get(key)
    if sup is not None and not sup.stopped:
        return sup
    sup = TransportSupervisor(cfg, base_dir, log=log,
                              event_sink=event_sink).start()
    _ACTIVE_SUPERVISORS[key] = sup
    return sup


def active_supervisor(cfg, base_dir):
    """The running supervisor for this config, or None."""
    sup = _ACTIVE_SUPERVISORS.get(_config_signature(cfg, base_dir))
    if sup is not None and not sup.stopped:
        return sup
    return None


def stop_supervisors(base_dir=None):
    """Stop supervised extension processes (shutdown/tests)."""
    for key, sup in list(_ACTIVE_SUPERVISORS.items()):
        if base_dir is not None and key[0] != base_dir:
            continue
        try:
            sup.stop()
        except Exception:
            pass
        del _ACTIVE_SUPERVISORS[key]
