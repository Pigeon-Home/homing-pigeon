#!/usr/bin/env python3
"""
Homing Pigeon — cross-platform runner agent.

Polls a dedicated mailbox for HMAC-signed job messages, executes them, and
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
#  2. The HMAC shared secret is a dedicated high-entropy string in the
#     shared_secret field, separate from the mailbox password (which is
#     only a Gmail credential). Both sides use its UTF-8 bytes directly
#     as the HMAC-SHA-384 key — no hashing or derivation, the SI uses it
#     as-is. The user hands that string to the cloud side. The runner
#     refuses to start if the secret is missing or too weak (it must
#     resist offline brute force against captured signed messages).
#  3. The runner obeys any job message bearing a valid HMAC signature,
#     regardless of sender. The signature is the sole authentication
#     gate; the sender address is logged for audit but never trusted.

import ipaddress
import argparse
import base64  # noqa: F401  (re-exported: tests patch it here)
import copy
import email
import hashlib
import hmac
import imaplib  # noqa: F401  (re-exported: tests patch it here)
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import smtplib  # noqa: F401  (re-exported: tests patch it here)
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.message import EmailMessage  # noqa: F401  (re-export)
from email.utils import parseaddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import NoReturn
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

def _load_attr(package, local, attr, default):
    """package.attr, else the sibling import used when this file is __main__.

    `python runner.py` from inside runner/ cannot see the package name.
    One face for that, instead of a copy of the same try at every import.
    """
    import importlib
    for name in (package, local):
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        try:
            return getattr(mod, attr)
        except AttributeError:
            return default
    return default

def _load_mod(package, local, broad=False):
    """Import a sibling module. broad=True also swallows a broken import."""
    import importlib
    try:
        return importlib.import_module(package)
    except ImportError:
        pass
    except Exception:
        if broad:
            return None
        raise
    try:
        return importlib.import_module(local)
    except Exception if broad else ImportError:
        return None


def _required_load_mod(package, local, why=""):
    """_load_mod, or ImportError naming the missing file: the siblings
    nothing can run without."""
    mod = _load_mod(package, local)
    if mod is None:
        raise ImportError("runner/%s.py is missing%s"
                          % (local.replace(".", "/"), why))
    return mod

__version__ = _load_attr("runner._version", "_version", "__version__", "unknown")

class _JobCryptoErrorFallback(ValueError):
    """Fallback when jobcrypto.py is unavailable; never raised."""

JobCryptoError = _load_attr(
    "runner.wire.jobcrypto", "wire.jobcrypto", "JobCryptoError",
    _JobCryptoErrorFallback)

class _OAuthRefreshErrorFallback(RuntimeError):
    """Fallback when oauth.py is unavailable; never raised."""

OAuthRefreshError = _load_attr(
    "runner.wire.oauth", "wire.oauth", "OAuthRefreshError",
    _OAuthRefreshErrorFallback)
_senses = _load_mod("runner.oracle.senses", "oracle.senses")
_extensions = _load_mod("runner.ops.extensions", "ops.extensions")
_review = _load_mod("runner.oracle.review", "oracle.review")
_opinion = _load_mod("runner.oracle.opinion", "oracle.opinion")
_learning = _load_mod("runner.oracle.learning", "oracle.learning")
_remediation = _load_mod("runner.oracle.remediation", "oracle.remediation")
_resources = _load_mod("runner.oracle.resources", "oracle.resources")
_dri = _load_mod("runner.oracle.dri", "oracle.dri")
_detection = _load_mod("runner.oracle.detection", "oracle.detection", broad=True)
_setup = _load_mod("runner.ops.setup", "ops.setup")
_security = _load_mod("runner.guard.security", "guard.security")
_sandbox = _load_mod("runner.guard.sandbox", "guard.sandbox")
_transports = _load_mod("runner.wire.transports", "wire.transports")
_extsources = _load_mod("runner.ops.extsources", "ops.extsources")
_jobcrypto = _load_mod("runner.wire.jobcrypto", "wire.jobcrypto")
_protocol_v2 = _load_mod("runner.wire.protocol_v2", "wire.protocol_v2")
_personal_docs = _load_mod("runner.oracle.personal_docs", "oracle.personal_docs")
_platformcard = _load_mod("runner.wire.platformcard", "wire.platformcard")
_textutil = _load_mod("runner.guard.textutil", "guard.textutil")
# The extension review (Agent-Chat-Stamp
# 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f): the Oracle reads an
# extension against its manifest before the loader's result is
# acted on; see runner/guard/extreview.py.
_extreview = _load_mod("runner.guard.extreview", "guard.extreview")
# The channel helper, for its PermanentDeliveryError (review item 4).
_channel = _load_mod("runner.transport_extensions.channel",
                     "transport_extensions.channel", broad=True)
# Typed config/job value readers (Agent-Stamp
# 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c): the one answer to "is this
# a usable number, and if not what do I use" -- see confval.py for
# the fifty-six documented defaults that motivated it.
_confval = _load_mod("runner.guard.confval", "guard.confval")
_defaulted = _load_mod("runner.guard.defaulted", "guard.defaulted")
# The one atomic writer for state files (Agent-Chat-Stamp
# 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f): runner/guard/atomicio.py.
_atomicio = _required_load_mod("runner.guard.atomicio", "guard.atomicio")
_filenames = _required_load_mod("runner.guard.filenames", "guard.filenames")
_panic = _required_load_mod("runner.guard.panic", "guard.panic")
if _textutil is None:
    raise ImportError("runner/guard/textutil.py is missing")
_as_str = _textutil._as_str
_json_safe = _textutil._json_safe
_fromiso = _textutil._fromiso
_mailbox_lib = _load_mod("runner.wire.mailbox", "wire.mailbox")
if _mailbox_lib is not None:
    # The mailbox client library lives in runner/wire/mailbox.py; the
    # email transport extension owns its lifecycle. These names
    # stay on this module because handle_mail, the harness, and
    # the local SI test address a mailbox-shaped client directly.
    _use_oauth = _mailbox_lib._use_oauth
    _xoauth2_raw = _mailbox_lib._xoauth2_raw
    _imap_xoauth2 = _mailbox_lib._imap_xoauth2
    _port = _mailbox_lib._port
    _host = _mailbox_lib._host
    _mailbox = _mailbox_lib._mailbox
    connect_imap = _mailbox_lib.connect_imap
    connect_smtp = _mailbox_lib.connect_smtp
    fetch_job_mails = _mailbox_lib.fetch_job_mails
    mark_seen = _mailbox_lib.mark_seen
    _send_mail_raw = _mailbox_lib.send_mail

    def send_mail(smtp, cfg, subject, body, to=None):
        """Every message the runner sends. A box the panic word stopped
        sends nothing (Q100): not a result, not an ack, not a resend."""
        if _panic.fired():
            log("panic: send dropped, the box is stopped", "WARN")
            return
        return _send_mail_raw(smtp, cfg, subject, body, to=to)
    _valid_reply_to = _mailbox_lib._valid_reply_to

_SECURITY_EVENTS_LOCK = threading.Lock()
_SECURITY_EVENTS_MAX = 5000

def _valid_base(base_dir) -> bool:
    """True when base_dir is a non-empty string."""
    return isinstance(base_dir, str) and bool(base_dir)

def _safe_open(path, flags, mode=0o600):
    """Open with O_NOFOLLOW and O_BINARY when the platform has them."""
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    return os.open(path, flags, mode)

def _append_security_event(base_dir: str, event: dict) -> None:
    """Append one event to security-events.jsonl (capped). Best effort.

    The poll thread and the local-inbox thread both append. The
    trim used to read the file and then truncate it with no lock,
    so one append could land in the window that the other wipe
    threw away. The lock covers the append and the trim. The trim
    replaces the file instead of truncating it in place, so a
    reader sees the old file or the new one, never a hole.
    """
    if not _valid_base(base_dir):
        return
    path = os.path.join(base_dir, "security-events.jsonl")
    try:
        line = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
    except (TypeError, ValueError):
        return
    with _SECURITY_EVENTS_LOCK:
        try:
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            fd = _safe_open(path, flags, 0o600)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
            _chmod_quiet(path)
            if os.path.islink(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) <= _SECURITY_EVENTS_MAX:
                return
            _atomicio.write_text(path, "".join(lines[-_SECURITY_EVENTS_MAX:]))
        except Exception:
            pass

def _note_resource_event(base_dir, event):
    """Record a resource event. A bad shape is ignored, not fatal.

    The monitor is an extension. A string, a missing resources map,
    or a value that is not a fraction must not skip the mail poll.
    """
    if not event:
        return
    if not isinstance(event, dict) or not isinstance(event.get("resources"), dict):
        log("resource monitor returned an unusable event; ignoring", "WARN")
        return
    bits = []
    for key, val in event["resources"].items():
        try:
            bits.append(f"{key}={float(val):.0%}")
        except (TypeError, ValueError):
            bits.append(f"{key}=?")
    try:
        thr = f"{float(event.get('threshold')):.0%}"
    except (TypeError, ValueError):
        thr = "?"
    try:
        _append_security_event(base_dir, event)
    except Exception as e:
        log(f"resource event was not stored: {e}", "WARN")
    if bits:
        log(f"resource pressure over threshold ({thr}): {', '.join(bits)}", "WARN")

def _report_event_fallback(message: str, level: str = "ERROR") -> None:
    return None

report_event = _load_attr("runner.ops.winlog", "ops.winlog", "report_event", _report_event_fallback)

SUBJECT_JOB = "[HOMING-PIGEON] job "
SUBJECT_RESULT = "[HOMING-PIGEON] result "
PROTOCOL_VERSION = 1

def _version_ok(v) -> bool:
    """True when a message's protocol version may be accepted.

    Only 1 is a protocol version, and the draft (Section 9)
    defines the member as the Integer 1: JSON true and 1.0 are
    equal to 1 under == but they are not the integer, so the
    check is a type check as well as a value check. The
    2026-10-17 bump to 2 changed the integer and nothing else,
    and it was reverted. Replies carry PROTOCOL_VERSION.
    """
    return isinstance(v, int) and not isinstance(v, bool) \
        and v == PROTOCOL_VERSION

# Signing, verification, secrets, key policies, and audience live in
# runner/wire/verify.py (PROTOCOL sections 4, 5, 14). Every name stays
# bound here for callers and tests.
_verify = _required_load_mod("runner.wire.verify", "wire.verify", ': nothing can be verified')
# The subject grammar (Q121): one separator class, the Worker's.
_subject = _required_load_mod("runner.wire.subject", "wire.subject", ': no subject can be read')
_SUBJECT_KIND_RE = re.compile(_subject.pattern_kind("result|job"), re.I)
SEEN_CAP = _verify.SEEN_CAP
_normalize = _verify._normalize
sign_payload = _verify.sign_payload
_extract_signed = _verify._extract_signed
_object_start = _verify._object_start
_in_root_object_at = _verify._in_root_object_at
_strip_controls = _verify._strip_controls
verify_body = _verify.verify_body
_read_secret_file = _verify._read_secret_file
build_secrets = _verify.build_secrets
build_key_policies = _verify.build_key_policies
unrestricted_extra_keys = _verify.unrestricted_extra_keys
check_key_policy = _verify.check_key_policy
DANGEROUS_ENV_NAMES = _verify.DANGEROUS_ENV_NAMES
_estimate_secret_entropy = _verify._estimate_secret_entropy
_secret_pattern_reason = _verify._secret_pattern_reason
validate_shared_secret = _verify.validate_shared_secret
secret_named = _verify.secret_named
key_names = _verify.key_names
is_default_key = _verify.is_default_key
canonical_key_id = _verify.canonical_key_id
policy_for = _verify.policy_for
key_fingerprint = _security.key_fingerprint
_env_name_in = _verify._env_name_in
check_policy_constraints = _verify.check_policy_constraints
check_audience = _verify.check_audience
audience_allows = _verify.audience_allows
_seen_key = _verify._seen_key
verify_body_keyed = _verify.verify_body_keyed
_job_encryption_setting = _verify._job_encryption_setting
_outgoing_result_body = _verify._outgoing_result_body

# Hardening M6: Linux confinement fallback chain. Returns
# (argv, use_host_env, sandboxed). In enforce mode the job runs inside
# bwrap; when bwrap is unavailable (non-Linux, missing binary, build
# failure) it warns loudly, audits the fallback, and runs normally.
# Audit mode runs normally and records what enforce would have done.
def _confinement_argv(cfg, base_dir, job_id, interpreter, script_path,
                      work, args, env):
    normal = ([*interpreter, script_path, *args], True, False)
    if _security is None or _sandbox is None:
        return normal
    mode = _security.sec_mode(cfg, "confinement")
    if mode == "off":
        return normal
    _security.bump_evaluated(base_dir, "confinement")

    def _audit(decision, reason, detail=""):
        try:
            _security.write_audit_entry(
                base_dir, "confinement", decision, reason,
                job_id=str(job_id), detail=str(detail), cfg=cfg,
                mode=mode)
        except Exception:
            pass

    if mode == "audit":
        # Audit records the policy decision, not the environment: what
        # enforce would decide. Availability is an enforce-time concern.
        _audit("would_sandbox", "would_run_sandboxed")
        return normal
    # enforce from here on
    if not _sandbox.sandbox_available():
        log(f"job {job_id}: confinement unavailable on this machine "
            f"({sys.platform}); running unsandboxed", "WARN")
        _audit("fallback", "confinement_unavailable")
        return normal
    # enforce
    notes = []
    try:
        argv = _sandbox.build_bwrap_command(
            cfg, interpreter, os.path.basename(script_path),
            work, args, env, notes=notes)
    except RuntimeError as e:
        log(f"job {job_id}: cannot build sandbox ({e}); "
            f"running unsandboxed", "WARN")
        _audit("fallback", "confinement_build_failed", str(e))
        return normal
    for note in notes:
        log(f"job {job_id}: sandbox: {note}", "INFO")
    _audit("sandboxed", "sandboxed", "; ".join(notes))
    # In the sandbox the env travels via --setenv; Popen inherits.
    return (argv, False, True)

# Hardening M8: run jobs as a different POSIX user. Returns a preexec_fn
# that drops privileges, or None. When a fn is returned the workdir has
# been chown'd to the job user. Root-only; otherwise warns loudly,
# audits the fallback, and runs as the current user.
class _JobUserFace:
    """The syscalls job_user needs. Tests pass a fake; the runner uses this."""

    def euid(self):
        return os.geteuid()

    def getpwnam(self, user):
        import pwd
        return pwd.getpwnam(user)

    def walk(self, path):
        return os.walk(path)

    def chown(self, path, uid, gid):
        os.chown(path, uid, gid)

    def realpath(self, path):
        return os.path.realpath(path)

    def dirname(self, path):
        return os.path.dirname(path)

    def stat(self, path):
        return os.stat(path)

    def chmod(self, path, mode):
        os.chmod(path, mode)

    def setgid(self, gid):
        os.setgid(gid)

    def initgroups(self, name, gid):
        os.initgroups(name, gid)

    def setgroups(self, groups):
        os.setgroups(groups)

    def setuid(self, uid):
        os.setuid(uid)

_remediation_ops = _required_load_mod("runner.ops.remediation_ops", "ops.remediation_ops")
_job_user_preexec = _remediation_ops._job_user_preexec
_job_user_startup_problem = _remediation_ops.job_user_startup_problem
_finish_remediation = _remediation_ops._finish_remediation
_learning_model_candidate = _remediation_ops._learning_model_candidate
_retained_job_summary = _remediation_ops._retained_job_summary


# ---------------------------------------------------------------- oracle (v3 §§9-12)
BUILTIN_REDACT_PATTERNS = {
    "aws_key": r"AKIA[0-9A-Z]{16}",
    "private_key": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    "bearer_token": r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*",
}
VIEW_ORDER = {"attested": 0, "summary": 1, "redacted": 2, "full": 3}

def _redact_patterns(cfg):
    pats = dict(BUILTIN_REDACT_PATTERNS)
    if not isinstance(cfg, dict):
        return pats
    extra = cfg.get("redact_patterns_extra") or {}
    if not isinstance(extra, dict):
        log("redact_patterns_extra is not an object; ignored", "WARN")
        extra = {}
    for name, regex in extra.items():
        try:
            re.compile(regex)
            pats[name] = regex
        except Exception:
            log(f"bad redact pattern {name}: skipped", "WARN")
    return pats

_policy = _required_load_mod("runner.ops.policy", "ops.policy")
apply_result_policy = _policy.apply_result_policy
_sensor_alert_core = _policy._sensor_alert_core
_output_digests = _policy._output_digests


_attest = _required_load_mod("runner.ops.attest", "ops.attest")
build_attestations = _attest.build_attestations
reload_hot_config = _attest.reload_hot_config


# ---------------------------------------------------------------- judgment / confinement / queries (v3 remaining)
def judge_job(cfg, job):
    """Return (verdict, reasons). Only when judge in advisory/enforce."""
    if not isinstance(cfg, dict):
        cfg = {}
    if not isinstance(job, dict):
        job = {}
    mode = cfg.get("judge") or "off"
    if mode not in ("advisory", "enforce"):
        return "pass", []
    reasons = []
    script = job.get("script")
    if not isinstance(script, str):
        script = ""
    for bad in ("rm -rf /", "rm -rf ~", ":(){ :|:& };:", "mkfs"):
        if bad in script:
            reasons.append(f"denylist: {bad}")
    if re.search(r"(?i)\bdd\b[\s\S]{0,200}\bof=/dev/", script):
        reasons.append("denylist: dd of=/dev/")
    url = job.get("script_url")
    if isinstance(url, str) and url and not url.startswith("https://"):
        reasons.append("non-https script_url")
    files = job.get("files")
    if isinstance(files, list):
        for f in files:
            if isinstance(f, dict) and ".." in _as_str(f.get("name", "")):
                reasons.append("path traversal in file name")
    verdict = "fail" if reasons else "pass"
    return verdict, reasons

# runner/ops/helpers.py: loaded the way every sibling is (the package
# name first, the local name when `runner` is this file, not the
# package: an install's `python3 runner.py`, the one-file binaries).
_helpers = _required_load_mod("runner.ops.helpers", "ops.helpers")
snapshot_outside = _helpers.snapshot_outside
append_bounded_log = _helpers.append_bounded_log


def check_protected_paths(before, after, protected):
    """Return list of paths under protected_paths that changed. Always reported."""
    if not isinstance(protected, list):
        return []
    changed = []
    abs_protected = []
    for p in protected:
        if isinstance(p, str) and p:
            abs_protected.append(os.path.abspath(p))
    if not isinstance(before, dict):
        before = {}
    if not isinstance(after, dict):
        after = {}
    all_paths = set(before) | set(after)
    for path in all_paths:
        if not isinstance(path, str):
            continue
        ap = os.path.abspath(path)
        if any(ap == pp or ap.startswith(pp + os.sep) for pp in abs_protected):
            try:
                changed_here = before.get(path) != after.get(path)
            except Exception:
                changed_here = True
            if changed_here:
                changed.append(path)
    return changed

def confinement_violated(before, after):
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    try:
        for path, info in after.items():
            try:
                if path not in before or before[path] != info:
                    return True
            except Exception:
                return True
    except Exception:
        return True
    return False

def query_budget(cfg, job):
    policy = (job or {}).get("result_policy") if isinstance(job, dict) else None
    if not isinstance(cfg, dict):
        cfg = {}
    if not isinstance(policy, dict):
        policy = {}
    # Documented default 8 for anything that is not a usable count;
    # a JSON boolean is not a count (True is not 1 here).
    job_b = _confval.integer(policy.get("query_budget"), 8)
    max_b = _confval.integer(cfg.get("max_query_budget"), 8)
    return max(0, min(job_b, max_b))

_oracle_tools = _required_load_mod("runner.ops.oracle_tools", "ops.oracle_tools")
ASK_SYSTEM = _oracle_tools.ASK_SYSTEM
ASK_AGENT_SYSTEM = _oracle_tools.ASK_AGENT_SYSTEM
_ORACLE_TOOLS = _oracle_tools._ORACLE_TOOLS
_ORACLE_AGENT_MAX_ROUNDS = _oracle_tools._ORACLE_AGENT_MAX_ROUNDS
_ORACLE_AGENT_WALL_CLOCK_SEC = _oracle_tools._ORACLE_AGENT_WALL_CLOCK_SEC
_ORACLE_AGENT_MAX_TOOLS_PER_ROUND = _oracle_tools._ORACLE_AGENT_MAX_TOOLS_PER_ROUND
_ORACLE_AGENT_CONTEXT_CHARS = _oracle_tools._ORACLE_AGENT_CONTEXT_CHARS
_ORACLE_TOOL_NAMES = _oracle_tools._ORACLE_TOOL_NAMES


class _InferenceRedirectRefused(HTTPRedirectHandler):
    """Fail closed: a loopback model must not bounce the prompt elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("inference redirect refused")

def _endpoint_is_loopback(endpoint: str) -> bool:
    """True only for http(s) hosts that are localhost or resolve to loopback."""
    try:
        parsed = urlparse(endpoint)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
        return bool(ip.is_loopback)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, parsed.port or 80)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        ip_s = info[4][0].split("%", 1)[0]  # pyrefly: ignore[missing-attribute]  # sockaddr[0] is str; typeshed models it loosely
        try:
            ip = ipaddress.ip_address(ip_s)
        except ValueError:
            return False
        if not ip.is_loopback:
            return False
    return True

def _oracle_mode(cfg) -> str:
    """Which Oracle this box runs: "deterministic" or "llm" (default).

    Config key oracle_mode. Deterministic is the Pi Light mode: the
    Oracle's duties -- the watch, the wake gate, briefs, answers --
    all run, but no local model is installed or ever called, so
    inference_config returns None and every model path stays dark.
    Briefs and answers are assembled from the box's own records
    instead. Anything but the exact string "deterministic" is the
    default llm mode, where a configured model does the narrating.
    """
    if isinstance(cfg, dict) and cfg.get("oracle_mode") == "deterministic":
        return "deterministic"
    return "llm"

def inference_config(cfg):
    """Return the inference dict when endpoint+model are set and loopback.

    Fail closed: missing fields or a non-loopback host yield None.
    Deterministic Oracle mode (Pi Light) also yields None, even when
    an endpoint is configured: no model is ever called in that mode.
    """
    if _oracle_mode(cfg) == "deterministic":
        return None
    inf = cfg.get("inference") if isinstance(cfg, dict) else None
    if not isinstance(inf, dict):
        return None
    endpoint = inf.get("endpoint")
    model = inf.get("model")
    if not isinstance(endpoint, str) or not isinstance(model, str):
        return None
    endpoint = endpoint.strip()
    model = model.strip()
    if not endpoint or not model:
        return None
    if not _endpoint_is_loopback(endpoint):
        log(f"inference endpoint refused (not loopback): {endpoint}", "WARN")
        return None
    if inf.get("max_answer_chars") is True or inf.get("timeout_sec") is True:
        return None
    try:
        max_chars = int(inf.get("max_answer_chars") or 2000)
        timeout = int(inf.get("timeout_sec") or 180)
    except (TypeError, ValueError, OverflowError):
        return None
    if max_chars < 0 or timeout < 1:
        return None
    return {
        "endpoint": endpoint.rstrip("/"),
        "model": model,
        "max_answer_chars": max_chars,
        "timeout_sec": timeout,
    }

def _as_text(value):
    """Stringify extension data. A value whose text form raises is empty."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""

def redact_text(text, patterns):
    """Apply the section-9 redact engine. Returns (text, families).

    Non-string text is stringified. A pattern map that is not an object
    falls back to the built-in patterns. A broken extension must not
    crash the Oracle.
    """
    if not isinstance(text, str):
        text = _as_text(text)
    if not isinstance(patterns, dict):
        patterns = BUILTIN_REDACT_PATTERNS
    out = text
    families = []
    for name, pat in (patterns or {}).items():
        if not isinstance(pat, str):
            continue
        try:
            if re.search(pat, out):
                label = _as_text(name) or "pattern"
                out = re.sub(pat, "[REDACTED:" + label + "]", out)
                families.append(label)
        except Exception:
            continue
    return out, families

def secret_scan(text, patterns):
    """Return pattern names that hit. Empty means the text is clean."""
    hits = []
    if not isinstance(patterns, dict) or not patterns:
        patterns = BUILTIN_REDACT_PATTERNS
    for name, pat in patterns.items():
        if not isinstance(pat, str):
            continue
        try:
            if re.search(pat, text or ""):
                hits.append(name)
        except Exception:
            continue
    return hits

# A shorter copy of a secret still identifies it. Eight characters is
# enough of an access key or token to be the secret, and short enough
# that ordinary words in a summary rarely collide with key material.
_SECRET_FRAGMENT = 8

def secret_fragment_hit(reply, source, patterns, min_len=_SECRET_FRAGMENT):
    """True when reply contains min_len contiguous characters of a secret
    that the patterns matched in source.

    secret_scan only sees a full pattern match. A model can return the
    first or last slice of a key and miss the pattern. This check
    compares slices of each match in the job output against the reply.
    """
    if not isinstance(reply, str):
        reply = ""
    if not isinstance(source, str):
        source = ""
    if isinstance(min_len, bool):
        min_len = _SECRET_FRAGMENT
    else:
        try:
            min_len = int(min_len)
        except (TypeError, ValueError, OverflowError):
            min_len = _SECRET_FRAGMENT
    if min_len < 1:
        min_len = _SECRET_FRAGMENT
    folded_reply = reply.casefold()
    if len(folded_reply) < min_len:
        return False
    if not isinstance(patterns, dict) or not patterns:
        patterns = BUILTIN_REDACT_PATTERNS
    for _name, pat in patterns.items():
        if not isinstance(pat, str):
            continue
        try:
            found = list(re.finditer(pat, source or ""))
        except re.error:
            continue
        for match in found:
            span = match.group(0).casefold()
            if len(span) < min_len:
                continue
            for i in range(0, len(span) - min_len + 1):
                if span[i:i + min_len] in folded_reply:
                    return True
    return False

def _default_inference_open(req, timeout=60):
    opener = build_opener(_InferenceRedirectRefused)
    return opener.open(req, timeout=timeout)

def ask_model(cfg, question, output_text, max_chars, patterns=None, opener=None, instructions=None):
    """ask_model with the answer-format guard.

    A reply that trips the guard (structured-data dump or a
    tool-call fragment riding in the text) is withheld and the
    question is re-asked once with a plain-sentences instruction.
    If the re-ask also trips and produced an answer, the caller
    gets the mechanical fallback sentence, sanitized like any
    other reply; a rejection from either attempt passes through.
    """
    result = _ask_model_once(cfg, question, output_text, max_chars,
                             patterns, opener, instructions)
    problem = _answer_format_problem(result.get("answer"))
    if not problem:
        return result
    log(f"ask: reply withheld by format guard ({problem}); "
        "re-asking for prose")
    retry = _ask_model_once(cfg,
                            _as_text(question) + "\n\n" + _FORMAT_REASK,
                            output_text, max_chars, patterns, opener,
                            instructions)
    if not _answer_format_problem(retry.get("answer")):
        return retry
    if "answer" not in retry:
        return retry
    log("ask: re-ask also failed the format guard", "WARN")
    pats = patterns if patterns is not None else BUILTIN_REDACT_PATTERNS
    try:
        cap = int(max_chars)
    except (TypeError, ValueError, OverflowError):
        cap = 2000
    model = cfg.get("model") if isinstance(cfg, dict) else ""
    return _sanitize_model_reply(_FORMAT_FALLBACK_ANSWER, cap,
                                 output_text, pats, model or "")

_misc = _required_load_mod("runner.ops.misc", "ops.misc")
_ask_model_once = _misc._ask_model_once
_v2_ingest = _misc._v2_ingest
_disk_owns = _misc._disk_owns
oracle_window = _misc.oracle_window


def _sanitize_model_reply(reply, cap, scan_text, patterns, model):
    """Shared tail for ask_model and ask_model_agent.

    Truncate, secret-scan (a slice of a secret in the context counts),
    redact, scan again. A hit drops the text and returns a rejection.
    """
    reply = reply[:cap]
    # Scan before redaction so a secret is rejected, not rewritten and
    # mailed. A slice of a secret in the context counts too.
    leaked = secret_scan(reply, patterns) or secret_fragment_hit(
        reply, scan_text, patterns)
    if leaked:
        log("ask: reply rejected: sanitization")
        return {"op": "ask", "rejected": "sanitization"}
    redacted, _families = redact_text(reply, patterns)
    if secret_scan(redacted, patterns) or secret_fragment_hit(
            redacted, scan_text, patterns):
        log("ask: reply rejected: sanitization")
        return {"op": "ask", "rejected": "sanitization"}
    log(f"ask: reply {_preview(redacted)!r}")
    return {"op": "ask", "answer": redacted, "model": model, "sanitized": True}

# --- Answer-format guard: a reply that is a structured-data dump or
# carries a tool-call-shaped fragment is not an answer, whatever the
# model intended. Field report, 2026-10-17: on a 2-core laptop the
# 1B model answered a job-status summary by re-serializing the job
# index as JSON, and a follow-up judgment question with corrupted
# JSON ending in a fabricated {"name": "run", "parameters":
# {"command": "psexec ..."}} fragment. Detection is mechanical.
# Parseable whole-reply tool calls never reach here as text:
# _parse_tool_calls routes them first.

_INDEX_FIELD_NAMES = ("job_status", "newest_job_index", "job_ids",
                      "previous_job_details", "total_job_count",
                      "current_job_count")

_FORMAT_FALLBACK_ANSWER = (
    "The local model answered in raw structured data instead of "
    "sentences, twice in a row, so I withheld both replies. Ask "
    "about one specific job, or check the retained job files and "
    "the runner log in the state directory.")

_FORMAT_REASK = (
    "(Your previous reply was raw structured data, not an answer. "
    "Reply in plain sentences only. No JSON, no field names, no "
    "lists of ids, no tool calls.)")

def _answer_format_problem(text):
    """Why a model reply is not a presentable answer, or "".

    Two shapes: a tool-call fragment embedded in the text (a
    parameters/command pair, or a known tool name in a
    name/parameters shape), and a job-index dump (three or more
    quoted index field names with : or =, or a whole-reply JSON
    object carrying two or more of them).
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    if '"parameters"' in text and '"command"' in text:
        return "tool-call fragment (parameters/command)"
    if '"name"' in text and ('"parameters"' in text
                             or '"arguments"' in text):
        for name in _ORACLE_TOOL_NAMES:
            if ('"' + name + '"') in text:
                return "tool-call fragment naming " + name
    hits = [f for f in _INDEX_FIELD_NAMES
            if re.search('"' + f + r'"\s*[:=]', text)]
    if len(hits) >= 3:
        return "job-index dump (" + ", ".join(hits[:3]) + ")"
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            obj = json.loads(stripped)
        except (TypeError, ValueError):
            obj = None
        if isinstance(obj, dict):
            keys = [f for f in _INDEX_FIELD_NAMES if f in obj]
            if len(keys) >= 2:
                return "job-index dump (" + ", ".join(keys[:3]) + ")"
    return ""

def _agent_finish(cfg, messages, reply, cap, scan_text, patterns,
                  model, opener, timeout, tool_rounds):
    """Final-answer gate for ask_model_agent.

    Sanitize the reply; if the format guard trips, re-ask once with
    tools off for plain prose; if that also trips, return the
    mechanical fallback sentence instead of the dump.
    """
    result = _sanitize_model_reply(reply, cap, scan_text, patterns, model)
    problem = _answer_format_problem(result.get("answer"))
    if not problem:
        result["tool_rounds"] = tool_rounds
        return result
    log(f"oracle agent: reply withheld by format guard ({problem}); "
        "re-asking for prose")
    messages.append({"role": "user", "content": _FORMAT_REASK})
    msg = _inference_chat(cfg, messages, None, opener, timeout)
    if isinstance(msg, dict) and msg.get("role") != "error":
        reply2 = msg.get("content")
        if not isinstance(reply2, str):
            reply2 = "" if reply2 is None else str(reply2)
        result2 = _sanitize_model_reply(reply2, cap, scan_text,
                                        patterns, model)
        if not _answer_format_problem(result2.get("answer")):
            result2["tool_rounds"] = tool_rounds
            return result2
        log("oracle agent: re-ask also failed the format guard", "WARN")
    fallback = _sanitize_model_reply(_FORMAT_FALLBACK_ANSWER, cap,
                                     scan_text, patterns, model)
    fallback["tool_rounds"] = tool_rounds
    return fallback

# --- Oracle agent tools: the chat model gets hands, the job path does not.
#
# ask_model (used by mailbox-driven jobs) stays single-shot and
# constrained. ask_model_agent (used only by the interactive --oracle
# chat) runs a tool loop: the local model may read files, list
# directories, write files, and run commands on the box while it works
# through a question. The owner asked for this explicitly: the Oracle
# is the debugging interface, and it needs god-like context.
#
# Load-bearing rails that stay: the chat is loopback-only with a
# session token, tools run as the user who launched --oracle, every
# tool result is bounded, and the final answer goes through the same
# secret scan + redaction as any other model output. One risk is
# stated plainly in the docs: anything the model reads can steer it,
# so a poisoned file could talk it into running something unwise.


# Call IDs minted for content-embedded tool calls (never issued as wire
# tool_calls by the model endpoint).
_CONTENT_CALL_ID_PREFIX = "content-"

# The interactive Oracle's charter (owner's decision, 2026-10-16;
# restored 2026-10-18 after later edits narrowed it to a watcher):
# the owner's local debugging partner, with full hands. ASK_SYSTEM
# above is the other door -- the mailbox query path, where the
# cloud SI asks about job output it must never see raw -- and it
# keeps its disclosure-boundary role on purpose. The shared
# how-to-answer rules (watch sections, the notable: line, never
# invent, never reveal secrets) live in both prompts; the acting
# charter lives only here. runner/tests/test_oracle_charter.py pins it.

def _tool_base_dir(base_dir):
    """State dir for Oracle tool paths, or "" when unknown."""
    if isinstance(base_dir, str) and base_dir:
        return base_dir
    return ""

def _bundled_doc_path(name):
    """Path to a doc file shipped inside the release, or "".

    Frozen (PyInstaller --onefile --add-data): the file is extracted to
    sys._MEIPASS at startup. Source layout: it sits at the repo root.
    Lets the local model read the protocol without the internet.
    """
    if isinstance(name, str) and name:
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", "")
            if isinstance(meipass, str) and meipass:
                p = os.path.join(meipass, "pigeon-docs", name)
                if os.path.isfile(p):
                    return p
        here = os.path.dirname(os.path.abspath(__file__))
        p = os.path.join(os.path.dirname(here), name)
        if os.path.isfile(p):
            return p
    return ""

def _project_snapshot_note(base_dir):
    """One short context block pointing at the shipped project snapshot.

    A release install carries the whole project under <base_dir>/project
    (runner/tools/make_snapshot.py): source, tests, docs, CI workflows, the
    full history as a git bundle, and the build's CI facts. The note
    names the paths so the model can read them with its tools. Returns
    "" when no snapshot is installed. Never raises.
    """
    if not _valid_base(base_dir):
        return ""
    root = os.path.join(base_dir, "project")
    index = os.path.join(root, "PROJECT-SNAPSHOT.md")
    if not os.path.isfile(index):
        return ""
    facts = {}
    try:
        with open(os.path.join(root, "CI-SNAPSHOT.json"),
                  encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            facts = loaded
    except (OSError, ValueError):
        pass
    ver = facts.get("version") if isinstance(facts.get("version"), str) \
        else "unknown"
    commit = facts.get("commit") if isinstance(facts.get("commit"), str) \
        else "unknown"
    lines = ["Homing Pigeon %s, commit %s, ships its whole project in "
             "project/ (read it with your tools; paths are relative to "
             "the state dir):" % (ver, commit[:12]),
             "- project/PROJECT-SNAPSHOT.md: the index, with links",
             "- project/CI-SNAPSHOT.json: the CI workflows, platform "
             "jobs, and the test results of the build that made this "
             "release",
             "- project/runner/, project/tests/, project/.github/"
             "workflows/, project/PROTOCOL.md: source, tests, CI, spec"]
    tests = facts.get("tests")
    if isinstance(tests, dict) and isinstance(tests.get("ran"), int):
        skips = tests.get("skips")
        lines.append("- CI test result: %s tests, %s, %d skipped"
                     % (tests["ran"], tests.get("result") or "?",
                        len(skips) if isinstance(skips, list) else 0))
    return "\n".join(lines)

def _resolve_tool_path(path, base_dir):
    """Relative tool paths resolve against the state dir, so the model
    can say 'runner.log' instead of guessing where the box keeps it."""
    base = _tool_base_dir(base_dir)
    if base and isinstance(path, str) and path and not os.path.isabs(path):
        return os.path.join(base, path)
    return path

def _tool_stays_inside(path, base_dir):
    """When a state dir is known, the real path must stay inside it.

    No state dir means the caller passed an absolute path on purpose.
    """
    base = _tool_base_dir(base_dir)
    if not base:
        return True
    if not isinstance(path, str) or not path or "\x00" in path:
        return False
    try:
        root = os.path.realpath(base)
        dest = os.path.realpath(path)
    except (TypeError, ValueError, OSError):
        return False
    if dest == root:
        return True
    return dest.startswith(root + os.sep)

_WITHHELD_TOOL_ERROR = ("error: withheld from the Oracle by the extension "
                        "sources disclosure rule")

def _withheld_for_tools(base_dir) -> list:
    """Paths the file tools refuse (runner/ops/extsources.py). Never raises."""
    if _extsources is None or not _tool_base_dir(base_dir):
        return []
    try:
        return _extsources.withheld_paths(base_dir)
    except Exception:
        return []

def _tool_withheld(path, base_dir, withheld) -> bool:
    if withheld is None:
        withheld = _withheld_for_tools(base_dir)
    if not withheld or _extsources is None:
        return False
    try:
        return bool(_extsources.is_withheld(path, withheld))
    except Exception:
        return True

_oracle_ops = _required_load_mod("runner.ops.oracle_ops", "ops.oracle_ops")
_oracle_brief = _oracle_ops._oracle_brief
_run_oracle_tool = _oracle_ops._run_oracle_tool


def _wire_tool_arguments(fargs) -> str:
    """Ollama's OpenAI shim unmarshals function.arguments as a string.

    A JSON object in that field is HTTP 400 on the follow-up turn, which
    is the turn after a tool actually ran.
    """
    if isinstance(fargs, str):
        return fargs
    try:
        return json.dumps(fargs if isinstance(fargs, dict) else {})
    except (TypeError, ValueError):
        return "{}"

def _inference_failure_text(exc, timeout=None) -> str:
    text = str(exc).lower()
    if "timed out" in text or "timeout" in text:
        waited = ""
        if isinstance(timeout, int) and not isinstance(timeout, bool) and timeout > 0:
            waited = " after " + str(timeout) + "s"
        return ("The local model timed out" + waited
                + ". Ask again, or raise inference.timeout_sec in config.json.")
    if "400" in text:
        return "The local model rejected the chat request."
    return "The local model did not answer."

def _apply_keep_alive(cfg, payload):
    """Keep the local model loaded between calls.

    Ollama unloads after a few idle minutes, and the next question
    then pays a multi-minute cold start. Explicit config wins; the
    Ollama default port gets a keep-alive without any config
    (docs/oracle/configuring-oracle.md, `keep_alive`). One place for both
    ask paths: the plain ask used to build its payload without this
    and cold-started on the main query-answer path.
    """
    keep_alive = cfg.get("keep_alive") if isinstance(cfg, dict) else None
    endpoint = cfg.get("endpoint") if isinstance(cfg, dict) else None
    if keep_alive is None and isinstance(endpoint, str) and ":11434" in endpoint:
        keep_alive = "30m"
    if keep_alive:
        payload["keep_alive"] = keep_alive

def _inference_timeout(cfg) -> int:
    """The per-question model timeout: timeout_sec, documented default 180."""
    raw = cfg.get("timeout_sec") if isinstance(cfg, dict) else None
    return _confval.integer(raw, 180, lo=1)

def _inference_chat(cfg, messages, tools, opener, timeout):
    """One /chat/completions call. Returns the message dict or an error dict."""
    payload = {"model": cfg.get("model"), "messages": messages}
    if tools:
        payload["tools"] = tools
    endpoint = cfg.get("endpoint")
    _apply_keep_alive(cfg, payload)
    body_bytes = json.dumps(payload).encode("utf-8")
    try:
        roles = ",".join(m.get("role", "?") for m in messages
                         if isinstance(m, dict))
    except Exception:
        roles = "?"
    log(f"inference chat call: {len(messages)} message(s) [{roles}], "
        f"{len(body_bytes)} byte payload, timeout={timeout}s")
    started = time.monotonic()
    req = Request(
        cfg.get("endpoint", "").rstrip("/") + "/chat/completions",
        data=body_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    open_fn = opener or _default_inference_open
    raw_text = None
    try:
        with open_fn(req, timeout=timeout) as resp:
            raw = resp.read(1_000_000)
        raw_text = raw.decode("utf-8", "replace")
        parsed = json.loads(raw.decode("utf-8"))
        msg = parsed["choices"][0]["message"]
        log(f"inference chat call returned in {time.monotonic() - started:.0f}s")
        _oracle_log_exchange(endpoint, cfg.get("model"), payload, started,
                             response=msg, raw=raw_text)
    except HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", "replace")
        except Exception:
            err_body = "?"
        _oracle_log_exchange(endpoint, cfg.get("model"), payload, started,
                             error=f"HTTP {e.code} {e.reason}",
                             error_body=err_body)
        log(f"inference chat call failed: HTTP {e.code} {e.reason}; "
            f"endpoint response body: {err_body[:500]}", "WARN")
        return {"role": "error", "content": _inference_failure_text(e, timeout)}
    except Exception as e:
        _oracle_log_exchange(endpoint, cfg.get("model"), payload, started,
                             error=str(e), raw=raw_text)
        log(f"inference chat call failed after {timeout}s: {e}", "WARN")
        return {"role": "error", "content": _inference_failure_text(e, timeout)}
    return msg if isinstance(msg, dict) else {"content": str(msg)}

def _agent_context_size(messages) -> int:
    total = 0
    for m in messages:
        if not isinstance(m, dict):
            continue
        c = m.get("content")
        if isinstance(c, str):
            total += len(c)
    return total

def _agent_trim(messages):
    """Drop the oldest tool exchange while the context is over budget.

    Keeps the system prompt and the original user question. Tool
    history is expendable; the final answer is what matters.
    """
    if len(messages) <= 3:
        return messages
    # messages[0] is system, messages[1] is the user question.
    # Drop messages[2:4] (oldest assistant tool-call + tool result),
    # one pair at a time.
    trimmed = messages[:2]
    rest = messages[2:]
    while _agent_context_size(trimmed + rest) > _ORACLE_AGENT_CONTEXT_CHARS and len(rest) > 2:
        rest = rest[2:]
    return trimmed + rest

def _parse_tool_calls(msg):
    """Normalize OpenAI-style tool_calls from a chat message.

    Falls back to a content-embedded call: small local models often
    skip native tool_calls and emit {"name": ..., "parameters": {...}}
    as a JSON blob in the message content instead. Without this the
    blob leaks into the chat as the "answer" instead of executing.
    """
    calls = msg.get("tool_calls")
    if isinstance(calls, list) and calls:
        out = []
        for tc in calls[:_ORACLE_AGENT_MAX_TOOLS_PER_ROUND]:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function")
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            raw_args = fn.get("arguments")
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except (TypeError, ValueError):
                    raw_args = {}
            if not isinstance(raw_args, dict):
                raw_args = {}
            call_id = tc.get("id")
            if not isinstance(call_id, str) or not call_id:
                call_id = f"call-{len(out)}"
            out.append((call_id, name if isinstance(name, str) else "", raw_args))
        if out:
            return out
    return _parse_content_tool_call(msg.get("content"))

def _parse_content_tool_call(content):
    """Detect a tool call the model wrote as JSON in its reply text.

    Only the known Oracle tool names qualify; anything else stays a
    plain-text answer. Returns a one-element call list or [].
    """
    if not isinstance(content, str):
        return []
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    candidates = [text]
    if "{" in text:
        brace = text[text.index("{"):text.rindex("}") + 1] if "}" in text else ""
        if brace and brace != text:
            candidates.append(brace)
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except (TypeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        name = obj.get("name")
        if not isinstance(name, str) or name not in _ORACLE_TOOL_NAMES:
            continue
        args = obj.get("parameters")
        if args is None:
            args = obj.get("arguments")
        if not isinstance(args, dict):
            continue
        return [(_CONTENT_CALL_ID_PREFIX + "call-0", name, args)]
    return []

def _unparsed_tool_note(content):
    """Short note when a reply names a tool but is not a parseable call.

    Empty when the reply is an ordinary answer. Used for one log line,
    not for execution.
    """
    if not isinstance(content, str) or '"name"' not in content:
        return ""
    if not any(('"' + name + '"') in content for name in _ORACLE_TOOL_NAMES):
        return ""
    return " ".join(content.split())[:160]

# The action dispatch (owner-approved 2026-10-18). The charter
# gives the interactive Oracle permission to act, but permission
# is not dispatch: a small local model handed an instruction in
# free-text chat may elect to talk about it instead -- the field
# failures were an answer to an unasked question, step-by-step
# instructions for the owner, and prose where an action was
# asked. The cloud SI's requests do not suffer this because they
# enter a structured path (a request becomes a signed job, and
# the job runs). The interactive door gets its equivalent here:
# a deterministic classifier marks an owner message as an action
# or a question, and in ask_model_agent an action's first reply
# MUST be a tool call -- a prose-only reply is returned once with
# a directive to call the tool or name the one blocking thing.
# Questions keep the free path, including the summary fast path.
_ORACLE_ACTION_VERBS = frozenset({
    "launch", "open", "start", "run", "execute", "create", "write",
    "make", "delete", "remove", "change", "set", "install",
    "uninstall", "kill", "stop", "restart", "reboot", "copy",
    "move", "rename", "download", "enable", "disable", "fix",
    "repair", "clean", "clear", "empty", "update", "upgrade",
    "send", "shut", "turn",
})
_ORACLE_REPORT_VERBS = frozenset({
    "give", "show", "tell", "list", "summarize", "summarise",
    "describe", "explain", "report",
})
_ORACLE_POLITE_PREFIXES = (
    "please ", "can you ", "could you ", "would you ",
    "will you ", "i want you to ", "i need you to ",
    "go ahead and ",
)

def _oracle_instruction_kind(text):
    """Classify an owner message as "action" or "question".

    Deterministic and conservative: any sentence whose lead word
    (after a politeness prefix) is an action verb makes the whole
    message an action; report leads (give/show/tell/...) and
    interrogatives stay questions, so the summary fast path and
    ordinary questions are never forced through a tool call.
    """
    if not isinstance(text, str):
        return "question"
    clauses = []
    for sentence in re.split(r"[.!?\n;]+", text.lower()):
        clauses.extend(
            # codeql[py/polynomial-redos]
            re.split(r",?\s+(?:and\s+then|and|then)\s+", sentence))
    for clause in clauses:
        words = clause.split()
        if not words:
            continue
        lead = " ".join(words)
        for prefix in _ORACLE_POLITE_PREFIXES:
            if lead.startswith(prefix):
                lead = lead[len(prefix):]
                words = lead.split()
                break
        if not words:
            continue
        first = words[0].strip(",")
        if first in _ORACLE_REPORT_VERBS:
            continue  # a report clause never dispatches by itself
        if first == "make" and len(words) > 1 and words[1] == "sure":
            continue  # "make sure X" is a verification ask
        if first in _ORACLE_ACTION_VERBS:
            return "action"
    return "question"

_recipes = _required_load_mod("runner.ops.recipes", "ops.recipes")
_cancel = _required_load_mod("runner.ops.cancel", "ops.cancel")
_changes = _required_load_mod("runner.ops.changes", "ops.changes")
_exec = _required_load_mod("runner.ops.exec", "ops.exec")
ask_model_agent = _exec.ask_model_agent
execute_job = _exec.execute_job
_decode_inline = _exec._decode_inline
MAX_OUTPUTS = _exec.MAX_OUTPUTS
DEFAULT_MAX_OUTPUT_FILE_BYTES = _exec.DEFAULT_MAX_OUTPUT_FILE_BYTES
_validate_outputs = _exec._validate_outputs
_max_output_file_bytes = _exec._max_output_file_bytes
_read_output = _exec._read_output
_collect_outputs = _exec._collect_outputs


def _output_blob(exec_result):
    """The job's output as the Oracle reads it for the owner: stdout
    then stderr, a value that is not text in its text form, so a
    record a crash left or a hand wrote still shows what it holds
    (a credential inside a list is scanned, not hidden). The
    queries read the streams by their own rule (Q90): text or
    nothing, since a sender is handed lines, never a value's text
    form."""
    out = exec_result.get("stdout") if isinstance(exec_result, dict) else ""
    err = exec_result.get("stderr") if isinstance(exec_result, dict) else ""
    if not isinstance(out, str):
        out = _as_text(out)
    if not isinstance(err, str):
        err = _as_text(err)
    return out + err

def _raw_lines_allowed(view):
    """grep/tail leak raw lines. Only full and redacted views may return them.

    A view whose equality check raises is not full or redacted.
    """
    if view is None:
        return True
    if not isinstance(view, str):
        return False
    return view in ("full", "redacted", "")

_queries = _required_load_mod("runner.ops.queries", "ops.queries")
answer_queries = _queries.answer_queries
handle_query_mail = _queries.handle_query_mail
query_seen_key = _queries.query_seen_key
_carriable = _queries._carriable
_stream_text = _queries._stream_text
_GREP_DEADLINE = _queries._GREP_DEADLINE
_worker = _queries._worker
_worker_lock = _queries._worker_lock
_query_worker_argv = _queries._query_worker_argv
_stop_worker = _queries._stop_worker
_drop_worker = _queries._drop_worker
_start_worker = _queries._start_worker
_read_line = _queries._read_line
grep_matches = _queries.grep_matches
worker_main = _queries.worker_main


_QUERY_TIMES = {}  # key_id -> list of timestamps
def _write_json(path, obj):
    """Atomic. A bad path or a bad object must not crash the caller.

    The temporary file is created with O_EXCL | O_NOFOLLOW, so a
    symlink planted at the temporary name is not written through.
    The replacement is mode 0600.
    """
    if not isinstance(path, str) or not path:
        return
    try:
        _atomicio.write_json(path, _json_safe(obj), allow_nan=False)
    except (OSError, TypeError, ValueError) as e:
        log(f"json not written to {path}: {e}", "WARN")

def _read_json_dict(path):
    """The dict a JSON file holds, or None: unreadable, malformed, or
    not an object. Never raises."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    return data if isinstance(data, dict) else None

def _query_limit(cfg):
    """Queries allowed per hour. 0 means unlimited.

    A value that is present but not a number is -1: the cap was
    intended and cannot be read, so the caller must refuse the query
    instead of treating the typo as unlimited.
    """
    raw = cfg.get("max_queries_per_hour", 0) if isinstance(cfg, dict) else 0
    if raw is True:
        return -1
    if raw in (None, "", 0, False):
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError, OverflowError):
        return -1

def _live_times(times, now):
    """The slots of the last hour. A time that is not a finite number,
    or lies in the future (a clock set back, a file a crash left),
    is not a slot: it would otherwise count as live for ever and
    hold the sender at the cap."""
    if not isinstance(times, list):
        return []
    live = []
    for t in times:
        try:
            when = float(t)
        except (TypeError, ValueError, OverflowError):
            continue
        if when != when or when in (float("inf"), float("-inf")):
            continue
        if 0 <= now - when < 3600:
            live.append(when)
    return live

_QUERY_LOCK = threading.Lock()

def _read_query_store(path):
    """The on-disk query window, or {}. A symlink is not followed."""
    if not isinstance(path, (str, bytes, os.PathLike)) or not path:
        return {}
    if os.path.islink(path):
        return {}
    if not os.path.exists(path):
        return {}
    return _read_json_dict(path) or {}

def check_rate_limit(key_id, cfg, path=None, peek=False):
    """Return True if under max_queries_per_hour. Zero means unlimited.

    When path is set, the window is on disk so it survives a restart
    and can be read without the runner running. The check and the
    write are one step, so two workers cannot both pass the last slot.
    With peek the answer is the same but no slot is taken and nothing
    is written: a dry run asks whether the sender would pass.
    """
    with _QUERY_LOCK:
        limit = _query_limit(cfg)
        if limit < 0:
            return False
        if limit <= 0:
            return True
        now = time.time()
        if path:
            store = _read_query_store(path)
        else:
            store = _QUERY_TIMES
        if not isinstance(store, dict):
            store = {}
        # A dict key id raises TypeError on get. That stopped the query.
        if not isinstance(key_id, str):
            key_id = ""
        window = _live_times(store.get(key_id, []), now)
        if len(window) >= limit:
            if peek:
                return False
            store[key_id] = window
            if path:
                _write_json(path, store)
            return False
        if peek:
            return True
        window.append(now)
        store[key_id] = window
        if path:
            _write_json(path, store)
        return True

def budget_status(path, cfg):
    if not isinstance(path, (str, bytes, os.PathLike)) or not path:
        return []
    """Per-key spend in the current hour, for the owner to read."""
    limit = _query_limit(cfg)
    store = _read_query_store(path)
    now = time.time()
    out = []
    for key, times in store.items():
        live = _live_times(times, now)
        out.append({"key_id": key, "spent": len(live), "limit": limit})
    return out

def _retention_days(cfg):
    """The output_retention_days window, read once for every reader.

    Absent, None, or unparseable values fall back to 7. An explicit
    0 or negative value is returned as-is and means no expiry: a
    record is never too old, and prune_retained deletes nothing.
    Every reader of the key takes the window from here --
    retained_expired and the prune call in poll_once. (The two once
    disagreed about 0: `int(cfg.get(...) or 7)` swallowed an
    explicit 0 into the 7-day default while prune_retained read 0
    as "prune nothing".)
    """
    if not isinstance(cfg, dict):
        return 7
    raw = cfg.get("output_retention_days")
    if raw is None:
        return 7
    # An explicit 0 or negative number is kept (no expiry, above); a
    # boolean, a non-number, or a number too large to be a day count
    # is the documented 7.
    return _confval.integer(raw, 7, lo=-(10 ** 9), hi=10 ** 9)

# ---------------------------------------------------------------- the outbox
# Execution is at most once per job_id on a runner; delivery is at
# least once. The moment a result is built and signed it is written
# to <base_dir>/outbox/ and the job is recorded as seen -- on disk --
# before the first send is attempted. Delivery is then a separate,
# retryable concern: a stash that never left is resent on later polls
# (result_resend_backoff_sec between attempts, given up after
# result_stash_retention_sec into outbox/failed/ with an audit entry);
# the script is never run twice. A delivered record moves to
# <base_dir>/sent/, where a redelivered copy of the same job (bound to
# its received digest, so a different job under a reused id runs on
# its own) is answered from it; sent records age out with
# output_retention_days (prune_sent). The one window left is the stash
# write itself: a crash between the execution and the record is a
# re-execution, and nothing wider.
OUTBOX_DIRNAME = "outbox"
OUTBOX_FAILED_DIRNAME = "failed"
SENT_DIRNAME = "sent"
RESEND_PASS_CAP = 50

def _record_name(skey):
    return hashlib.sha384(_as_str(skey).encode("utf-8")).hexdigest()[:48] \
        + ".json"

def _sent_path(base_dir, skey):
    return os.path.join(base_dir, SENT_DIRNAME, _record_name(skey))

def _outbox_dir(base_dir):
    return os.path.join(base_dir, OUTBOX_DIRNAME)

def _stash_path(base_dir, skey):
    return os.path.join(_outbox_dir(base_dir), _record_name(skey))

def _ensure_private_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
        _chmod_quiet(path, 0o700)

def _job_digest(job):
    if _opinion is not None:
        return _opinion.received_digest(job)
    return hashlib.sha384(json.dumps(
        {k: v for k, v in (job or {}).items() if k != "sig"},
        sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()

def _stash_retention_sec(cfg):
    return _confval.integer((cfg or {}).get("result_stash_retention_sec"),
                            86400, lo=1)

def _resend_backoff_sec(cfg):
    return _confval.integer((cfg or {}).get("result_resend_backoff_sec"),
                            60, lo=1)

def stash_result(base_dir, skey, job, subject, body, to=None,
                 transport=None, key_id=None, encrypted=False, meta=None):
    """Write the finished, signed (and, when on, encrypted) result to
    the outbox before the first send. Returns True when the record is
    down. A failure to record is logged and False is returned: the
    caller then does not commit the job as seen, so a crash here is
    the one re-execution window, stated in the module comment."""
    if not _valid_base(base_dir):
        return False
    rec = {"skey": _as_str(skey),
           "job_id": _as_str((job or {}).get("job_id")),
           "job_digest": _job_digest(job),
           "subject": subject, "body": body, "to": to,
           "created": time.time(), "attempts": 0, "last_attempt": 0,
           "last_error": None, "transport": transport, "key_id": key_id,
           "encrypted": bool(encrypted), "meta": meta if isinstance(meta, dict) else {},
           "completed_at": datetime.now(timezone.utc).strftime(
               "%Y-%m-%dT%H:%M:%SZ")}
    try:
        _ensure_private_dir(_outbox_dir(base_dir))
        _atomicio.write_json(_stash_path(base_dir, skey), rec)
        return True
    except Exception as e:
        log(f"result not stashed for {rec['job_id']}: {e}", "ERROR")
        return False

def _read_record(path):
    rec = _read_json_dict(path)
    if rec is None or not isinstance(rec.get("body"), str) \
            or not isinstance(rec.get("subject"), str):
        return None
    return rec

def load_stash(base_dir, skey):
    """The waiting record for skey, or None."""
    if not _valid_base(base_dir):
        return None
    return _read_record(_stash_path(base_dir, skey))

def _stash_rewrite(base_dir, skey, rec):
    try:
        _atomicio.write_json(_stash_path(base_dir, skey), rec)
    except Exception as e:
        log(f"outbox record not updated for {rec.get('job_id')}: {e}",
            "WARN")

def _stash_move(base_dir, skey, folder):
    """Move the waiting record into folder (sent/ or outbox/failed/)."""
    src = _stash_path(base_dir, skey)
    try:
        _ensure_private_dir(folder)
        os.replace(src, os.path.join(folder, _record_name(skey)))
        return True
    except OSError as e:
        log(f"outbox record not moved to {os.path.basename(folder)}: {e}",
            "WARN")
        return False

def _delivery_audit(base_dir, decision, reason, job_id, cfg=None):
    if _security is None:
        return
    try:
        _security.write_audit_entry(base_dir, "delivery", decision, reason,
                                    job_id=_as_str(job_id), cfg=cfg)
    except Exception:
        pass

def _stash_fail(base_dir, skey, rec, reason, cfg=None):
    """Give the record up: outbox/failed/, an audit entry, one ERROR."""
    log(f"result {rec.get('job_id')} not delivered: {reason}; "
        f"kept under outbox/{OUTBOX_FAILED_DIRNAME}/", "ERROR")
    _delivery_audit(base_dir, "failed", reason, rec.get("job_id"), cfg)
    _stash_move(base_dir, skey,
                os.path.join(_outbox_dir(base_dir), OUTBOX_FAILED_DIRNAME))

_STASH_GUARDS = {}
_STASH_GUARDS_LOCK = threading.Lock()


def _stash_guard(skey):
    """The lock for one outbox key.

    A delivery and the resend pass can both hold the same record.
    The record leaves the outbox before the send, still inside this
    lock, so the second sender finds it gone.
    """
    key = _as_str(skey)
    with _STASH_GUARDS_LOCK:
        guard = _STASH_GUARDS.get(key)
        if guard is None:
            guard = threading.RLock()
            _STASH_GUARDS[key] = guard
        return guard


def deliver_stash(base_dir, skey, sender, cfg=None, now=None):
    """One delivery attempt of the waiting record for skey.

    sender(subject, body, to) sends the stored bytes. On success the
    record moves to sent/ and the delivery is logged with its attempt
    count; on an exception the record's attempt count, time and error
    are updated and a WARN is logged. Never raises: a delivery
    failure is not a job failure. Returns True when delivered.
    One key is sent by one caller at a time.
    """
    if not _valid_base(base_dir):
        return False
    with _stash_guard(skey):
        return _deliver_stash_held(base_dir, skey, sender, cfg, now)


def _unclaim_stash(base_dir, skey, rec):
    """Put a claimed record back in the outbox. The send did not
    stick. False when the write fails: the record stays in sent/
    and is not sent again."""
    try:
        _ensure_private_dir(_outbox_dir(base_dir))
        _atomicio.write_json(_stash_path(base_dir, skey), rec)
        _unlink_quiet(_sent_path(base_dir, skey))
        return True
    except Exception as e:
        log(f"result {rec.get('job_id')} could not be put back in the "
            f"outbox after a failed send: {e}", "WARN")
        return False


def _deliver_stash_held(base_dir, skey, sender, cfg=None, now=None):
    rec = load_stash(base_dir, skey)
    if rec is None:
        return False
    # Claim the record before the send. A move that fails leaves it
    # in the outbox and this caller does not send; the other caller,
    # waiting on the same lock, then takes it. Sending first and
    # moving after let a failed move on Windows hand the same record
    # to the second caller.
    if not _stash_move(base_dir, skey, os.path.join(base_dir, SENT_DIRNAME)):
        return False
    now = time.time() if now is None else now
    attempt = int(rec.get("attempts") or 0) + 1
    try:
        sender(rec["subject"], rec["body"], rec.get("to"))
    except Exception as e:
        if not _unclaim_stash(base_dir, skey, rec):
            return False
        rec["attempts"] = attempt
        rec["last_attempt"] = now
        rec["last_error"] = _as_text(e)[:500]
        if _is_permanent_smtp(e):
            # Refused for good (review item 4). Once: the streams are
            # dropped and a signed stub says so; the original is kept
            # under work/<job_id>/result.json. A stub refused too is
            # given up.
            if rec.get("stubbed"):
                _stash_fail(base_dir, skey, rec,
                            f"the delivery stub was refused too: {e}", cfg)
                return False
            stub = _stub_body(rec, cfg, e) if cfg is not None else None
            if stub is None:
                _stash_fail(base_dir, skey, rec,
                            f"refused for good ({e}) and no stub could "
                            f"be signed", cfg)
                return False
            _keep_original_result(base_dir, rec, build_secrets(cfg))
            log(f"result {rec.get('job_id')} refused for good ({e}); "
                f"sending the stub, the full output stays under "
                f"work/{rec.get('job_id')}/", "WARN")
            rec["body"] = stub
            rec["stubbed"] = True
            rec["attempts"] = 0
            _stash_rewrite(base_dir, skey, rec)
            return _deliver_stash_held(base_dir, skey, sender, cfg=cfg, now=now)
        _stash_rewrite(base_dir, skey, rec)
        log(f"result {rec.get('job_id')} not delivered (attempt {attempt}): "
            f"{e}; kept in the outbox", "WARN")
        return False
    log(f"result {rec.get('job_id')} delivered (attempt {attempt})"
        + (" as the stub" if rec.get("stubbed") else ""))
    return True

def undeliver_stash(base_dir, skey, reason):
    """A delivery that was counted as done but did not land (a channel
    outbox write that failed after the capture): the record goes back
    from sent/ to the outbox with the failure on it, for the resend
    pass. The job stays seen -- it did execute. Returns True when a
    record was moved back."""
    if not _valid_base(base_dir):
        return False
    src = _sent_path(base_dir, skey)
    rec = _read_record(src)
    if rec is None:
        return False
    # The attempt is counted and the error kept; last_attempt is
    # left alone so the next cycle's pass tries again at once -- the
    # failure was local (a channel outbox write), not a remote server
    # the backoff exists to spare.
    rec["attempts"] = int(rec.get("attempts") or 0) + 1
    rec["last_error"] = _as_text(reason)[:500]
    try:
        _ensure_private_dir(_outbox_dir(base_dir))
        _atomicio.write_json(_stash_path(base_dir, skey), rec)
        _unlink_quiet(src)
    except Exception as e:
        log(f"result {rec.get('job_id')} could not be re-queued: {e}", "WARN")
        return False
    log(f"result {rec.get('job_id')} did not land ({reason}); back in the "
        f"outbox for the resend pass", "WARN")
    return True

def _waiting_records(base_dir):
    """(skey, record) for every waiting outbox record, oldest first."""
    folder = _outbox_dir(base_dir)
    out = []
    try:
        names = os.listdir(folder)
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json"):
            continue
        rec = _read_record(os.path.join(folder, name))
        if rec is None or not isinstance(rec.get("skey"), str):
            continue
        out.append((rec["skey"], rec))
    out.sort(key=lambda item: float(item[1].get("created") or 0))
    return out

def resend_stashed(base_dir, cfg, sender, now=None, limit=RESEND_PASS_CAP):
    """The resend pass, once per poll: every waiting record past its
    backoff is attempted again; one past its retention is given up.
    At most `limit` records a pass, so a backlog never stalls polling.
    Returns {"attempted", "delivered", "failed", "waiting"}."""
    counts = {"attempted": 0, "delivered": 0, "failed": 0, "waiting": 0}
    if not _valid_base(base_dir):
        return counts
    now = time.time() if now is None else now
    backoff = _resend_backoff_sec(cfg)
    retention = _stash_retention_sec(cfg)
    for skey, rec in _waiting_records(base_dir)[:limit]:
        counts["waiting"] += 1
        created = float(rec.get("created") or now)
        send = _record_sender(base_dir, rec, sender)
        if now - created > retention:
            _stash_fail(base_dir, skey, rec,
                        f"not delivered within result_stash_retention_sec "
                        f"({retention}s) after {rec.get('attempts', 0)} "
                        f"attempt(s); last error: {rec.get('last_error')}",
                        cfg)
            counts["failed"] += 1
            counts["waiting"] -= 1
            continue
        if send is None or now - float(rec.get("last_attempt") or 0) < backoff:
            continue
        counts["attempted"] += 1
        if deliver_stash(base_dir, skey, send, cfg=cfg, now=now):
            counts["delivered"] += 1
            counts["waiting"] -= 1
    return counts

def outbox_report(base_dir):
    """{"waiting": [...], "failed": [...]}: job id, age, attempts and
    the last error of each record, for --inspect outbox and the
    startup line."""
    report = {"waiting": [], "failed": []}
    if not _valid_base(base_dir):
        return report
    now = time.time()
    folders = (("waiting", _outbox_dir(base_dir)),
               ("failed", os.path.join(_outbox_dir(base_dir),
                                       OUTBOX_FAILED_DIRNAME)))
    for key, folder in folders:
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for name in names:
            rec = _read_record(os.path.join(folder, name))
            if rec is None:
                continue
            report[key].append({
                "job_id": rec.get("job_id"),
                "age_sec": int(max(0.0, now - float(rec.get("created") or now))),
                "attempts": int(rec.get("attempts") or 0),
                "last_error": rec.get("last_error"),
                "transport": rec.get("transport"),
            })
    return report

def outbox_lines(base_dir):
    """The report as text, one record a line."""
    report = outbox_report(base_dir)
    lines = []
    for key in ("waiting", "failed"):
        rows = report[key]
        lines.append(f"{key}: {len(rows)}")
        for row in rows:
            err = f" -- {row['last_error']}" if row.get("last_error") else ""
            lines.append(f"  {row['job_id']}  age {row['age_sec']}s  "
                         f"attempts {row['attempts']}{err}")
    return lines

# The members a delivery stub keeps when a result body is refused
# for good (review item 4): the identity and verdict of the run,
# never its streams.
_STUB_KEYS = ("v", "type", "job_id", "kind", "key_id", "completed_at",
              "exit_code", "timed_out", "duration_sec", "runner", "review",
              "judgment", "env_fingerprint", "result_seq",
              "prev_result_sha384")

def _result_meta(result):
    if not isinstance(result, dict):
        return {}
    meta = {k: result[k] for k in _STUB_KEYS if k in result}
    if "result_seq" in result:
        # A stub that replaces this result names the link it replaces,
        # so the sender's chain stays whole (PROTOCOL 3.2).
        digest = result_digest(result)
        if digest:
            meta["result_sha384"] = digest
    return meta


# ---- the result chain (PROTOCOL 3.2): each key's results in order
CHAIN_FILE = "result_chain.json"
_CHAIN_LOCK = threading.RLock()


def result_digest(result):
    """SHA-384 over a result's signed JSON, the text the signature
    covers: what a receiver gets back from the body by cutting the
    signature off. None for what cannot be signed."""
    try:
        text = _normalize(json.dumps(_json_safe(result), separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError):
        return None
    return hashlib.sha384(text.encode("utf-8")).hexdigest()


def _chain_state(base_dir):
    path = os.path.join(base_dir, CHAIN_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        # A chain file that cannot be read starts a new chain from one,
        # which a sender reads as a break, never as continuity.
        log(f"{CHAIN_FILE} unreadable; the result chain starts again", "WARN")
        return {}
    return state if isinstance(state, dict) else {}


def chain_link(base_dir, owner):
    """(seq, prev) for the next result signed by `owner`'s key: one
    more than the last sequence this runner committed for that key
    and the digest of that result, or (1, None) for a key's first.
    Call under _CHAIN_LOCK, through chain_commit."""
    if not _valid_base(base_dir) or not isinstance(owner, str):
        return None, None
    entry = _chain_state(base_dir).get(owner)
    if not isinstance(entry, dict):
        return 1, None
    seq = entry.get("seq")
    last = entry.get("last")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1 \
            or not (isinstance(last, str) and len(last) == 96):
        return 1, None
    return seq + 1, last


def chain_commit(base_dir, owner, seq, result):
    """Record a result as the key's newest link, once it is stashed."""
    if not _valid_base(base_dir) or not isinstance(owner, str) \
            or not isinstance(seq, int):
        return
    digest = result_digest(result)
    if digest is None:
        return
    state = _chain_state(base_dir)
    state[owner] = {"seq": seq, "last": digest}
    try:
        _atomicio.write_json(os.path.join(base_dir, CHAIN_FILE), state)
    except OSError as e:
        log(f"result chain not recorded: {e}", "WARN")


def chain_members(cfg, base_dir, owner, result):
    """Set result_seq and prev_result_sha384 on a result about to be
    signed; returns the seq to commit, or None when the chain is off
    (result_chain: false) or cannot be read."""
    if isinstance(cfg, dict) and cfg.get("result_chain") is False:
        return None
    seq, prev = chain_link(base_dir, owner)
    if seq is None:
        return None
    result["result_seq"] = seq
    if prev:
        result["prev_result_sha384"] = prev
    return seq

# ---- the result's size, and what a permanent refusal gets instead
MAX_RESULT_BYTES = 5 * 1024 * 1024   # 5 MiB on the wire; providers allow 10-25 for the whole message
_TAIL_KEEP = 2048

def _max_result_bytes(cfg):
    """max_result_bytes: a non-negative int (0 = unlimited), the
    documented 5 MiB otherwise."""
    raw = (cfg or {}).get("max_result_bytes")
    if raw is None or isinstance(raw, bool) or not isinstance(raw, int) \
            or raw < 0:
        return MAX_RESULT_BYTES
    return raw

def _shrink_stream(text, keep):
    """Head and tail of text, `keep` characters in all, with a marker
    saying how much went. Returns (text, dropped)."""
    text = _as_str(text)
    if keep < 0:
        keep = 0
    if len(text) <= keep:
        return text, 0
    head = keep // 2
    tail = keep - head
    dropped = len(text) - keep
    # A stream is text: the count is characters (Q98 item 19).
    marker = "\n... [%d characters dropped to fit max_result_bytes] ...\n" % dropped
    return text[:head] + marker + (text[-tail:] if tail else ""), dropped

def _fit_result_body(result, secret, encrypt, job_id, key_id, max_bytes):
    """Build the outgoing body; when it is over max_bytes, shrink
    stdout and stderr proportionally (head and tail kept, a marker in
    the middle, the truncated flags set, a result_truncated member
    saying why and how much), rebuild, and try again -- three passes
    at most, the third dropping both streams to their first and last
    2 KiB. The signature always covers what is sent. Returns
    (result, body)."""
    body = _outgoing_result_body(result, secret, encrypt, job_id, key_id)
    if not max_bytes:
        return result, body
    dropped_total = 0
    for attempt in range(3):
        size = len(body.encode("utf-8"))
        if size <= max_bytes:
            break
        out = _as_str(result.get("stdout"))
        err = _as_str(result.get("stderr"))
        streams = len(out) + len(err)
        if attempt < 2 and streams > 0:
            # Everything but the streams stays; the streams get what
            # is left of the budget, less a margin for escaping,
            # base64 and the envelope, split in proportion.
            fixed = max(0, size - streams)
            budget = int((max_bytes - fixed) * 0.6)
            budget = max(budget, 2 * _TAIL_KEEP)
            keep_out = int(budget * len(out) / streams)
            keep_err = budget - keep_out
        else:
            keep_out = keep_err = 2 * _TAIL_KEEP
        result = dict(result)
        result["stdout"], d1 = _shrink_stream(out, keep_out)
        result["stderr"], d2 = _shrink_stream(err, keep_err)
        dropped_total += d1 + d2
        if d1:
            result["stdout_truncated"] = True
        if d2:
            result["stderr_truncated"] = True
        result["result_truncated"] = {"reason": "max_result_bytes",
                                      "dropped": dropped_total}
        body = _outgoing_result_body(result, secret, encrypt, job_id, key_id)
    return result, body

def _is_permanent_smtp(exc):
    """A refusal that will not change on retry: a 5xx SMTP response
    (SMTPSenderRefused, SMTPDataError 552/554 included), every
    recipient refused with 5xx, or a transport's own
    PermanentDeliveryError. Everything else -- 4xx, sockets, TLS,
    timeouts -- is transient."""
    if _channel is not None and isinstance(
            exc, getattr(_channel, "PermanentDeliveryError", ())):
        return True
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [v[0] for v in (exc.recipients or {}).values()
                 if isinstance(v, (tuple, list)) and v]
        return bool(codes) and all(
            isinstance(c, int) and 500 <= c <= 599 for c in codes)
    if isinstance(exc, smtplib.SMTPResponseException):
        code = getattr(exc, "smtp_code", None)
        return isinstance(code, int) and 500 <= code <= 599
    return False

def _stub_result(job_id, original, reason):
    """What is sent when the full result was refused for good: the
    run's identity and verdict, the streams dropped, a delivery_note
    saying why and where the full output is."""
    stub = {k: original[k] for k in _STUB_KEYS
            if isinstance(original, dict) and k in original}
    stub.setdefault("v", PROTOCOL_VERSION)
    stub.setdefault("type", "result")
    stub["job_id"] = job_id
    if isinstance(original, dict) and isinstance(original.get("result_sha384"), str):
        stub["replaces_result_sha384"] = original["result_sha384"]
    stub["stdout"] = ""
    stub["stderr"] = ""
    stub["stdout_truncated"] = True
    stub["stderr_truncated"] = True
    stub["delivery_note"] = (
        "original result refused by the mail server (%s); streams "
        "dropped. Full output is in the runner's job log at work/%s/."
        % (_as_text(reason)[:300], job_id))
    return stub

def _record_payload(rec, secrets):
    """The result dict a stashed body carries: the signed payload,
    decrypted when the record says the body is encrypted. None when
    it cannot be read back (a key no longer configured)."""
    try:
        payload = verify_body_keyed(rec["body"], secrets)
        if isinstance(payload, tuple):
            payload = payload[0]
        if _jobcrypto is not None and _jobcrypto.is_envelope(payload):
            secret = secret_named(secrets, rec.get("key_id") or "")
            if secret is None:
                return None
            inner = _jobcrypto.decrypt_body(payload, secret,
                                            rec.get("job_id"),
                                            rec.get("key_id") or "")
            payload = verify_body(inner, secret)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None

def _keep_original_result(base_dir, rec, secrets):
    """work/<job_id>/result.json: the refused result, kept for the
    operator. Best effort."""
    job_id = rec.get("job_id")
    if not isinstance(job_id, str) or not _SAFE_JOB_ID.match(job_id) \
            or job_id in (".", ".."):
        return False
    payload = _record_payload(rec, secrets)
    if payload is None:
        return False
    folder = os.path.join(base_dir, "work", job_id)
    try:
        os.makedirs(folder, exist_ok=True)
        _atomicio.write_json(os.path.join(folder, "result.json"), payload,
                             indent=1)
        return True
    except Exception as e:
        log(f"result {job_id}: original not kept: {e}", "WARN")
        return False

def _stub_body(rec, cfg, reason):
    """The signed (and, as the original was, encrypted) stub for a
    refused record, or None when the key is gone."""
    secrets = build_secrets(cfg)
    key_id = rec.get("key_id") or ""
    secret = secret_named(secrets, key_id)
    if secret is None:
        return None
    meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
    stub = _stub_result(rec.get("job_id"), meta, reason)
    return _outgoing_result_body(stub, secret, bool(rec.get("encrypted")),
                                 rec.get("job_id"), key_id)

def _sweep_channel_refusals(base_dir, cfg, names):
    """A transport extension that was refused a result for good sets
    it aside under its channel's outbox/failed/ with a
    <stem>.refused.txt (channel.refuse_result). This pass answers each
    one the way a mailbox refusal is answered: the delivered record
    is found by the result's job id, the original is kept under
    work/<job_id>/result.json, a signed stub goes back out the same
    channel, once; a stub refused too is given up with an audit
    entry. The refusal files move to outbox/done/ once the stub
    has gone out, or once the record has been given up. A result
    with no record here stays in failed/: moving it finished the
    job with nothing stored, and the record may arrive on a later
    pass."""
    if _transports is None or not _valid_base(base_dir):
        return 0
    handled = 0
    for name in names or ():
        try:
            paths = _transports.channel_paths(base_dir, name)
        except Exception:
            continue
        failed = os.path.join(paths["outbox"], OUTBOX_FAILED_DIRNAME)
        try:
            notes = sorted(n for n in os.listdir(failed)
                           if n.endswith(".refused.txt"))
        except OSError:
            continue
        for note in notes:
            stem = note[:-len(".refused.txt")]
            result_file = os.path.join(failed, stem + ".result.txt")
            try:
                with open(os.path.join(failed, note), encoding="utf-8") as fh:
                    reason = fh.read().strip()
                with open(result_file, encoding="utf-8") as fh:
                    parsed = _transports.parse_envelope(fh.read())
            except (OSError, ValueError):
                # An extension wrote the pair; bytes that are not
                # UTF-8 (UnicodeDecodeError, a ValueError) are as
                # unreadable as a missing file, and one bad note must
                # not end the sweep every cycle (Q60).
                parsed = None
                reason = "refused"
            job_id = None
            if parsed is not None:
                m = _transports._RESULT_ID_RE.search(parsed[0] or "")
                job_id = m.group(1) if m else None
            if job_id is None and os.path.isfile(result_file):
                # The body did not name a job: no blank line, or not
                # text. The pair is <id>.result.txt beside
                # <id>.refused.txt. Moving it to done here made the
                # queue ack the job with nothing stored. The id in
                # the name is the job the file was refused for.
                job_id = stem
            rec = None
            skey = _seen_key(cfg, job_id) if job_id else None
            if skey:
                rec = _read_record(_sent_path(base_dir, skey))
            if rec is not None and not rec.get("stubbed"):
                stub = _stub_body(rec, cfg, reason)
                if stub is not None:
                    _keep_original_result(base_dir, rec, build_secrets(cfg))
                    try:
                        _transports.write_channel_result(
                            base_dir, name, "", rec["subject"], stub,
                            ident_hint=stem, target=rec.get("to"))
                        rec["stubbed"] = True
                        rec["last_error"] = _as_text(reason)[:500]
                        _atomicio.write_json(_sent_path(base_dir, skey), rec)
                        log(f"result {job_id} refused for good by the "
                            f"{name} transport ({reason}); the stub goes "
                            f"back out, the full output stays under "
                            f"work/{job_id}/", "WARN")
                        _delivery_audit(base_dir, "stubbed", reason, job_id,
                                        cfg)
                    except Exception as e:
                        log(f"result {job_id}: stub not written to the "
                            f"{name} channel: {e}", "WARN")
                        continue
                else:
                    _stash_fail_sent(base_dir, skey, rec,
                                     f"refused for good ({reason}) and no "
                                     f"stub could be signed", cfg)
            elif rec is not None:
                _stash_fail_sent(base_dir, skey, rec,
                                 f"the delivery stub was refused too: "
                                 f"{reason}", cfg)
            else:
                log(f"{name} transport: refused result {stem} has no "
                    f"record here ({reason}); it stays until one "
                    f"does", "WARN")
                if os.path.isfile(result_file):
                    # Moving the pair to done made the queue ack
                    # the job with nothing stored. The record may
                    # not have been written yet. Leave both files.
                    continue
            done = paths["outbox_done"]
            for fname in (note, stem + ".result.txt"):
                src = os.path.join(failed, fname)
                if os.path.exists(src):
                    try:
                        os.makedirs(done, exist_ok=True)
                        os.replace(src, os.path.join(done, fname))
                    except OSError:
                        pass
            handled += 1
    return handled

def _stash_fail_sent(base_dir, skey, rec, reason, cfg=None):
    """Give up a record that had been counted as delivered: it moves
    from sent/ to outbox/failed/ with the audit entry."""
    log(f"result {rec.get('job_id')} not delivered: {reason}; "
        f"kept under outbox/{OUTBOX_FAILED_DIRNAME}/", "ERROR")
    _delivery_audit(base_dir, "failed", reason, rec.get("job_id"), cfg)
    folder = os.path.join(_outbox_dir(base_dir), OUTBOX_FAILED_DIRNAME)
    try:
        _ensure_private_dir(folder)
        rec["last_error"] = _as_text(reason)[:500]
        _atomicio.write_json(os.path.join(folder, _record_name(skey)), rec)
        _unlink_quiet(_sent_path(base_dir, skey))
    except Exception as e:
        log(f"outbox record not moved to failed: {e}", "WARN")

def _record_sender(base_dir, rec, mail_sender):
    """How a waiting record goes out this cycle: a record that came
    through a transport extension's channel goes back out that
    channel's outbox; a mailbox record needs the cycle's mail sender.
    None when neither is available now (the record waits)."""
    name = rec.get("transport")
    if name:
        if _transports is None:
            return None

        def via_channel(subject, body, to):
            _transports.write_channel_result(base_dir, name, "", subject,
                                             body, target=to)
        return via_channel
    return mail_sender

def load_sent_result(base_dir, skey, job):
    """The recorded result for this exact job, or None: the waiting
    outbox record first, then the sent record.

    None when there is no record, when the record is for a job of
    another shape under the same id (the digest differs), or when the
    record cannot be read. Never raises."""
    if not _valid_base(base_dir):
        return None
    rec = _read_record(_stash_path(base_dir, skey)) \
        or _read_record(_sent_path(base_dir, skey))
    if rec is None:
        return None
    digest = _opinion.received_digest(job) if _opinion is not None \
        else None
    if digest is not None and rec.get("job_digest") != digest:
        return None
    return rec


def _prune_dir(base_dir, subdir, days):
    """Delete files in base_dir/subdir older than days."""
    if not _valid_base(base_dir):
        return 0
    try:
        days = int(days)
    except (TypeError, ValueError, OverflowError):
        return 0
    if days <= 0:
        return 0
    d = os.path.join(base_dir, subdir)
    if not os.path.isdir(d):
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for name in os.listdir(d):
        path = os.path.join(d, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except Exception:
            pass
    return removed


def prune_sent(base_dir, days):
    """Delete recorded results older than output_retention_days."""
    return _prune_dir(base_dir, SENT_DIRNAME, days)

def prune_retained(base_dir, days):
    """Delete retained outputs older than output_retention_days."""
    return _prune_dir(base_dir, "retained", days)

_RETAINED_LOCK = threading.RLock()

def save_retained(base_dir, job_id, payload):
    """Persist output for later queries. Unsafe ids are dropped, not written.

    The temp name is created with O_EXCL | O_NOFOLLOW, so a symlink
    planted there is not written through. The file is mode 0600.
    """
    if not _valid_base(base_dir):
        return
    if not isinstance(job_id, str) or not _SAFE_JOB_ID.match(job_id) or job_id in (".", ".."):
        return
    d = os.path.join(base_dir, "retained")
    with _RETAINED_LOCK:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            return
        path = os.path.join(d, f"{job_id}.json")
        try:
            safe = _json_safe(payload) if isinstance(payload, dict) else {}
            _atomicio.write_json(path, safe, allow_nan=False)
        except (TypeError, ValueError, OSError) as e:
            log(f"retained not saved for {job_id}: {e}", "WARN")

def load_retained(base_dir, job_id):
    """Load retained/<job_id>.json. Unsafe or missing ids return None."""
    if not _valid_base(base_dir):
        return None
    if not isinstance(job_id, str) or not _SAFE_JOB_ID.match(job_id) \
            or job_id in (".", ".."):
        return None
    retained = os.path.realpath(os.path.join(base_dir, "retained"))
    stored = os.path.join(retained, f"{job_id}.json")
    if os.path.islink(stored):
        return None
    path = os.path.realpath(stored)
    try:
        if os.path.commonpath([retained, path]) != retained:
            return None
    except ValueError:
        return None
    with _RETAINED_LOCK:
        if not os.path.isfile(path):
            return None
        data = _read_json_dict(path)
    return data

def retained_expired(data, cfg):
    """True when saved_at is older than output_retention_days.

    A window of 0 or less never expires -- 0 is the operator turning
    retention off, and prune_retained agrees (it prunes nothing).
    """
    if not isinstance(data, dict) or not isinstance(cfg, dict):
        return True
    days = _retention_days(cfg)
    if days <= 0:
        return False
    try:
        saved = float(data.get("saved_at") or 0)
    except (TypeError, ValueError, OverflowError):
        return True
    if saved != saved or saved in (float("inf"), float("-inf")):
        return True
    return (time.time() - saved) > days * 86400

# ---------------------------------------------------------------- board (v3 §13)
# The board lives in runner/wire/board.py (the first module carved out of
# this file). The names stay bound here for callers and tests.
_board = _required_load_mod("runner.wire.board", "wire.board", ': the task board (PROTOCOL.md section 13) cannot load')
Board = _board.Board
_BOARD_LOCK = _board.BOARD_LOCK

class JobRejected(Exception):
    """Validly signed job that can never succeed (poison)."""

# ------------------------------------------------- mail handling
# (the IMAP/SMTP client library lives in runner/wire/mailbox.py; the
# email transport extension owns its lifecycle)
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

def _key_name(key_id, secret):
    """The name a result reports for the key that verified a job
    (Q94): the key id the sender used, or, for the unnamed default
    key, the fingerprint it answers to, so an unnamed sender learns
    the name too. Never a value."""
    if isinstance(key_id, str) and key_id:
        return key_id
    try:
        return key_fingerprint(secret)
    except Exception:
        return ""


ENV_SALT_FILE = "env_salt"


def _env_salt(base_dir):
    """The runner's own salt for env_fingerprint: 32 random bytes kept
    in base_dir/env_salt (0600), made once. None when the base is not
    usable; a salt that cannot be read is made again, which reads as
    a changed environment, never as the same one."""
    if not _valid_base(base_dir):
        return None
    path = os.path.join(base_dir, ENV_SALT_FILE)
    for _attempt in (1, 2):
        try:
            with open(path, encoding="ascii") as fh:
                salt = bytes.fromhex(fh.read().strip())
            if len(salt) < 16:
                raise ValueError("salt too short")
            return salt
        except FileNotFoundError:
            pass
        except (OSError, ValueError, UnicodeError):
            try:
                os.remove(path)
            except OSError:
                return None
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        except OSError:
            return None
        salt = os.urandom(32)
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            fh.write(salt.hex() + "\n")
        return salt
    return None


def env_fingerprint(cfg, base_dir):
    """The env_fingerprint every result carries (PROTOCOL 3.2) when
    the owner's pong_platform tier is standard or full, else None. A
    digest, never the list: at standard it names nothing the card at
    that tier does not, and at no tier can the list be read back."""
    if _platformcard is None or not hasattr(_platformcard, "env_fingerprint"):
        return None
    tier, problem = _platformcard.tier_of(cfg, "pong_platform")
    if problem or tier not in ("standard", "full"):
        return None
    salt = _env_salt(base_dir)
    if salt is None:
        return None
    versions = [PROTOCOL_VERSION]
    if _protocol_v2 is not None and _protocol_v2.enabled(cfg):
        versions.append(2)
    try:
        return _platformcard.env_fingerprint(salt, cfg, versions, __version__)
    except Exception:
        return None


def pong_platform(cfg):
    """The platform card a ping's result carries (PROTOCOL 3.2), at
    the owner's `pong_platform` tier, or None at `none` (or when the
    card module is absent). The protocol versions named are the ones
    this runner opens: version 1 always, version 2 when protocol_v2
    is on. The same card, same tiers, as the DTLS greeting."""
    if _platformcard is None:
        return None
    tier, problem = _platformcard.tier_of(cfg, "pong_platform")
    if problem or tier == "none":
        return None
    versions = [PROTOCOL_VERSION]
    if _protocol_v2 is not None and _protocol_v2.enabled(cfg):
        versions.append(2)
    card = _platformcard.build_card(tier, cfg, protocol_versions=versions,
                                    runner_version=__version__)
    if card is not None:
        # The key ids this runner accepts (Q94), names only, never a
        # value: the default key under its fingerprint and every
        # additional key, so a sender whose ping verified knows which
        # names it may sign with (TLS-PSK's identity hint, in effect).
        # The sender already holds one of these keys, or the ping
        # would not have verified.
        try:
            card["key_ids"] = sorted(k for k in build_secrets(cfg) if k)
        except Exception:
            card["key_ids"] = []
    if card is not None and tier == "full" and _defaulted is not None:
        # Decision 1: the settings that read as their default are
        # named, at the tier that already tells the SI the most.
        card["config_defaulted"] = _defaulted.defaulted_keys(cfg)
    return card

def script_filename(interpreter) -> str:
    """Name the staged script so the interpreter will accept -File.

    PowerShell refuses -File on a file without a .ps1 extension. That
    is a permanent failure, not a retry. A value that cannot be
    printed is treated as a generic script.
    """
    parts = interpreter if isinstance(interpreter, (list, tuple)) else [interpreter]
    texts = []
    for part in parts:
        texts.append(part if isinstance(part, str) else _as_str(part))
    joined = " ".join(texts).lower()
    if "powershell" in joined or "pwsh" in joined:
        return "script.ps1"
    if "python" in joined:
        return "script.py"
    return "script"

# The file-name rules live in runner/guard/filenames.py (one rule set,
# refused the same way on every platform); the names stay on this
# module for the suite and the sender.
_WIN_DEVICES = _filenames._WIN_DEVICES
windows_reserved_name = _filenames.windows_reserved_name

def kill_tree(proc: subprocess.Popen, extra_pids=None):
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
    # Remediation's tree kill: processes the monitor sampled in
    # the job's tree that escaped the process group (a detached
    # grandchild that called setsid) still die. Best effort.
    if os.name != "nt" and extra_pids:
        for pid in extra_pids:
            try:
                if pid and int(pid) != proc.pid:
                    os.kill(int(pid), signal.SIGKILL)
            except Exception:
                pass

_panic.set_kill(kill_tree)

MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MiB

class _NoForeignRedirect(HTTPRedirectHandler):
    """A redirect off https is poison: downloads are HTTPS only
    (PROTOCOL Sections 6/7), so a redirect may not downgrade to
    http any more than the original URL may start there. A URL
    that cannot be printed is still a rejection, not a retry."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not isinstance(newurl, str) or not newurl.lower().startswith(
                "https://"):
            shown = _as_text(newurl) or "url"
            raise JobRejected("download redirected off https: " + shown)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def _open_download(req, timeout):
    return build_opener(_NoForeignRedirect).open(req, timeout=timeout)

def download(url: str, dest: str, max_bytes: int = MAX_DOWNLOAD_BYTES):
    # Downloads are HTTPS only (PROTOCOL Sections 6/7, draft
    # Section 11.4): an http URL would fetch the content in the
    # clear on a channel the job's MAC does not cover, and
    # non-HTTP schemes (file:, ftp:) fail the same way every
    # cycle and can read the local machine. Reject them all as
    # poison. Every route here -- files[] entries and
    # script_url alike -- funnels through this one check.
    if not isinstance(url, str) or not url.lower().startswith("https://"):
        raise JobRejected(f"unsupported url scheme: {url}")
    if not isinstance(dest, str) or not dest:
        raise JobRejected("download destination is not a path")
    try:
        max_bytes = int(max_bytes)
    except (TypeError, ValueError, OverflowError):
        max_bytes = MAX_DOWNLOAD_BYTES
    if max_bytes < 1:
        max_bytes = MAX_DOWNLOAD_BYTES
    try:
        req = Request(url, headers={"User-Agent": "homing-pigeon/1"})
        resp = _open_download(req, 120)
    except HTTPError as e:
        # 4xx will not succeed on retry. 5xx may.
        if 400 <= e.code < 500:
            raise JobRejected(f"download rejected by server ({e.code}): {url}")
        raise
    except URLError as e:
        reason = _as_text(getattr(e, "reason", "")).lower()
        # NXDOMAIN and "no address" never recover. Timeouts and refused
        # connections still propagate as transient.
        permanent = ("name or service not known", "nodename nor servname",
                     "no address associated", "name resolution")
        if any(s in reason for s in permanent):
            raise JobRejected(f"download host does not resolve: {url}")
        raise
    except ValueError as e:
        # "Invalid IPv6 URL" and a control character in the URL raise
        # here. They fail the same way every cycle.
        raise JobRejected(f"bad download url: {e}")
    # The bytes land in a temp name beside dest, opened O_EXCL |
    # O_NOFOLLOW (a symlink planted at either name is not written
    # through), the cap is enforced while streaming, and the file is
    # renamed into place whole: a reader never sees a partial
    # download under the staged name (review item 5).
    tmp = _atomicio._temp_name(dest)
    fd = _atomicio._open_new(tmp, 0o600)
    total = 0
    try:
        with resp:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    # Poison, not transient: an over-cap download fails
                    # identically on every retry, burning bandwidth each
                    # cycle. The stream is closed here, the partial file
                    # removed below.
                    raise JobRejected(
                        f"download exceeded {max_bytes} bytes"
                    )
                view = memoryview(chunk)
                while len(view):
                    view = view[os.write(fd, view):]
        os.close(fd)
        fd = None
        os.replace(tmp, dest)
    except BaseException:
        if fd is not None:
            _close_quiet(fd)
        _unlink_quiet(tmp)
        raise

def sha384_of(path: str) -> str:
    """Hash a file. A missing or unreadable file is empty, not a crash."""
    if isinstance(path, os.PathLike):
        try:
            path = os.fspath(path)
        except Exception:
            return ""
    if isinstance(path, bytes):
        path = os.fsdecode(path)
    if not isinstance(path, str) or not path:
        return ""
    h = hashlib.sha384()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except (OSError, TypeError, ValueError):
        return ""
    return h.hexdigest()

_SAFE_JOB_ID = re.compile(r"\A[A-Za-z0-9._-]{1,128}\Z")

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

def validate_file_name(name) -> str:
    """A files[].name, or JobRejected naming the rule it broke.

    The rules are runner/guard/filenames.py's, checked on every
    platform before any download, so a bad name is poison (rejected
    once, never retried) and never costs a fetch. Returns the
    normalized relative path, components joined by '/'.
    """
    try:
        return _filenames.validate_file_name(name)
    except _filenames.BadFileName as e:
        raise JobRejected(str(e))

def _staged_dest(work, name, root=None):
    """Absolute path of a staged file. It must stay inside work.

    An absolute name, `..`, or a symlink that points outside is
    rejected: the real path of the destination must start with the
    real path of work (`root`, computed once per job by the caller
    when given). The parent directories of a nested name are created
    here, after confirming that no existing path component on the
    way is a symlink. Nothing is downloaded.
    """
    if not isinstance(name, str) or not name or "\x00" in name:
        raise JobRejected("unsafe file name: %r" % (name,))
    try:
        if root is None:
            root = os.path.realpath(work)
        dest = os.path.realpath(os.path.join(work, name))
    except (TypeError, ValueError) as e:
        raise JobRejected("unsafe file name: %s" % (e,))
    prefix = root + os.sep
    if not dest.startswith(prefix):
        raise JobRejected("unsafe file name: %s" % (name,))
    # The lexical path, component by component: a symlink already
    # sitting where a parent directory should be is refused before
    # anything is created under it (the real path above resolved it;
    # this is where it is named).
    parts = name.replace("\\", "/").split("/")[:-1]
    cur = work
    for i, part in enumerate(parts):
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            raise JobRejected("workspace integrity: %s is a symlink"
                              % "/".join(parts[:i + 1]))
    parent = os.path.dirname(dest)
    if parent != root:
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            raise JobRejected("cannot create the directory for %s: %s"
                              % (name, e))
    return dest

def _workspace_root(work):
    """The canonical work directory, computed once per job.

    A work directory that is itself a symlink is refused: the staging
    checks and the sandbox bind are of the real path, and a link here
    would make them answer for somewhere else.
    """
    if os.path.islink(work):
        raise JobRejected("workspace integrity: the work directory is a "
                          "symlink")
    return os.path.realpath(work)

def _reparse_point(st):
    """True for a Windows reparse point (a junction as much as a
    symlink); lstat marks them in st_file_attributes, which POSIX
    stat results do not carry."""
    return bool(getattr(st, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))

def _sweep_workspace(work, root, when):
    """Every entry under work is a regular file or directory, not a
    symlink, with its real path under root. Anything else is
    `JobRejected("workspace integrity: ...")` naming the entry and the
    moment (`after staging`, `before execution`): a race between the
    download and the execution, or a script that planted a link, shows
    here and never runs. os.walk does not follow links."""
    prefix = root + os.sep
    for dirpath, dirnames, filenames in os.walk(work, followlinks=False):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            try:
                st = os.lstat(full)
            except OSError as e:
                raise JobRejected("workspace integrity (%s): %s cannot be "
                                  "read: %s" % (when, _rel_work(work, full), e))
            if stat.S_ISLNK(st.st_mode) or _reparse_point(st):
                raise JobRejected("workspace integrity (%s): %s is a symlink"
                                  % (when, _rel_work(work, full)))
            if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):
                raise JobRejected("workspace integrity (%s): %s is not a "
                                  "regular file or directory"
                                  % (when, _rel_work(work, full)))
            if not os.path.realpath(full).startswith(prefix):
                raise JobRejected("workspace integrity (%s): %s resolves "
                                  "outside the work directory"
                                  % (when, _rel_work(work, full)))

def _check_script_path(script_path, root):
    """The staged script is a regular, non-symlink file under root."""
    prefix = root + os.sep
    try:
        st = os.lstat(script_path)
    except OSError as e:
        raise JobRejected("workspace integrity (before execution): the "
                          "script cannot be read: %s" % e)
    if stat.S_ISLNK(st.st_mode) or _reparse_point(st) \
            or not stat.S_ISREG(st.st_mode) \
            or not os.path.realpath(script_path).startswith(prefix):
        raise JobRejected("workspace integrity (before execution): the "
                          "script is not a regular file under the work "
                          "directory")

# ---------------------------------------------------------------- remediation
# The acts are core (docs/design/remediation-design.md): only the runner
# holds the process tree, the workdir, and the result channel.
# runner/oracle/remediation.py holds the policy; the glue below wires
# the live probes in. Everything here is best-effort: a broken
# monitor must never break the job it watches.

def _remediation_audit(base_dir, cfg, st, job_id, decision, div,
                       detail=""):
    if _security is None or _remediation is None:
        return
    try:
        reason = div if isinstance(div, str) else \
            _remediation.divergence_text(div)
        _security.write_audit_entry(
            base_dir, "remediation", decision, reason,
            job_id=str(job_id), detail=str(detail), cfg=cfg,
            mode=st["mode"])
    except Exception:
        pass

def _remediation_event(base_dir, st, job_id, div, act, authority,
                       av_verdict, quarantine_path, digest,
                       envelope_note=""):
    """One security-events record: the DRI channel's copy of the
    story (its `remediation` trigger turns it into a page)."""
    try:
        _append_security_event(base_dir, {
            "type": "remediation",
            "at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "job_id": job_id,
            "mode": st["mode"],
            "authority": authority,
            "divergence": _remediation.divergence_text(div),
            "act": act,
            "av_verdict": av_verdict,
            "quarantine": quarantine_path,
            "envelope": envelope_note,
            "received_digest": digest,
        })
    except Exception:
        pass

def _remediation_ask_fn(cfg, st):
    """The Oracle's judgment call, wired for oracle mode only.

    Returns None when inference is not configured (Pi Light
    included): the monitor then records abstentions and only
    the reflexes act. The call is ask_model with the timeout
    clamped to remediation_oracle_timeout_sec.
    """
    inf = inference_config(cfg)
    if inf is None:
        return None
    bounded = dict(inf)
    try:
        base_timeout = int(inf.get("timeout_sec")
                           or st["oracle_timeout_sec"])
    except (TypeError, ValueError, OverflowError):
        base_timeout = st["oracle_timeout_sec"]
    bounded["timeout_sec"] = min(base_timeout,
                                 st["oracle_timeout_sec"])
    patterns = _redact_patterns(cfg)

    def ask(question, context):
        res = ask_model(bounded, question, context, 400, patterns)
        if not isinstance(res, dict):
            return None
        ans = res.get("answer")
        return ans if isinstance(ans, str) and ans.strip() else None

    return ask

def _start_job_monitor(cfg, st, job_id, proc, work, base_dir,
                       script_path, before_files):
    """Build and start the per-job monitor. None on any failure."""
    if _remediation is None:
        return None
    script_text = ""
    try:
        with open(script_path, "rb") as fh:
            script_text = fh.read(512 * 1024).decode(
                "utf-8", errors="replace")
    except OSError:
        script_text = ""
    declared_paths = []
    if _opinion is not None and script_text:
        try:
            hints = _opinion.script_hints(script_text)
            declared_paths = hints.get("paths") or []
        except Exception:
            declared_paths = []
    script_findings = _script_path_findings(
        script_text, base_dir, job_id) if script_text else []
    declared_cred = [p for p, r in script_findings
                     if r == _remediation.CREDENTIAL_REASON]
    envelope_note = "declared paths: " + (
        ", ".join(declared_paths[:8]) if declared_paths else "none")
    if script_findings:
        envelope_note += "; script findings: " + "; ".join(
            f"{p} ({r})" for p, r in script_findings)

    def alerts_fn(since_iso):
        if _senses is None:
            return []
        try:
            return _senses.load_alerts(base_dir, since=since_iso,
                                       limit=200)
        except Exception:
            return []

    monitor = _remediation.JobMonitor(
        st, job_id, proc.pid, work,
        declared_paths=declared_paths,
        declared_credential_paths=declared_cred,
        initial_files=set((before_files or {}).keys()),
        kill_fn=lambda extra: kill_tree(proc, extra),
        ask_fn=_remediation_ask_fn(cfg, st)
        if st["mode"] == "oracle" else None,
        findings_fn=lambda text: _script_path_findings(
            text, base_dir, job_id),
        alerts_fn=alerts_fn,
        base_dir=base_dir,
        envelope_note=envelope_note)
    monitor.start()
    return monitor


def _remediation_confinement_followup(cfg, job, job_id, base_dir):
    """The escape tripwire at result time.

    The mid-run monitor cannot see writes outside the workdir
    with stdlib-only means; the confinement snapshot in the
    ingest handler can, after the fact. An escape found there
    is handled as what it is -- a tripwire -- with the acts
    that still apply: quarantine, referral, page. Returns the
    result member, or None in off mode / on failure.
    """
    if _remediation is None:
        return None
    st = _remediation.settings(cfg)
    div = _remediation.divergence(
        "confinement_escape",
        "job wrote outside its workspace (post-run confinement "
        "snapshot)")
    digest = _remediation.received_digest(job)
    if st["mode"] == "off":
        _remediation_event(base_dir, st, job_id, div, "none", "none",
                           "unavailable", "", digest)
        _remediation_audit(base_dir, cfg, st, job_id, "observed",
                           div, "mode off: recorded and paged only")
        return None
    work = os.path.join(base_dir, "work", job_id)
    marker = {"job_id": job_id, "mode": st["mode"],
              "authority": "tripwire",
              "divergence": _remediation.divergence_text(div),
              "act": "quarantined", "received_digest": digest}
    qdir = _remediation.quarantine_job(base_dir, job_id, work, marker)
    refer = []
    if qdir:
        qwork = os.path.join(qdir, "work")
        for dirpath, _dirs, names in os.walk(qwork):
            for name in sorted(names):
                path = os.path.join(dirpath, name)
                try:
                    if os.path.getsize(path) <= 1024 * 1024:
                        refer.append(path)
                except OSError:
                    continue
                if len(refer) >= _remediation.AV_MAX_FILES:
                    break
            if len(refer) >= _remediation.AV_MAX_FILES:
                break
    av_verdict, av_detail = _remediation.av_referral(refer)
    member = _remediation.result_member(
        st["mode"], "tripwire", div, "quarantined", av_verdict,
        digest)
    _remediation.enforce_quarantine_bounds(base_dir, st)
    _remediation_audit(
        base_dir, cfg, st, job_id, "acted", div,
        f"act=quarantined authority=tripwire av={av_verdict} "
        f"({av_detail})")
    _remediation_event(base_dir, st, job_id, div, "quarantined",
                       "tripwire", av_verdict, qdir or "", digest)
    log(f"job {job_id}: remediation quarantined "
        f"({_remediation.divergence_text(div)}; authority "
        f"tripwire)", "WARN")
    return member


# ---------------------------------------------------------------- job handling
def _as_int(value, default):
    """An int from a stored value, or default. A boolean is not an int."""
    return _confval.integer(value, default, strings=True)

def _as_float(value, default):
    """A finite float from a stored value, or default."""
    n = _confval.number(value, None, strings=True)
    return default if n is None else float(n)

def _default_timeout_sec(cfg) -> int:
    """The job timeout a job gets when it names none.

    PROTOCOL.md: default 300. A key present as null, a non-numeric
    string, a boolean, or a value under 1 is not a timeout and must
    not reject every timeout-less job (null did) or give them one
    second (true did).
    """
    if not isinstance(cfg, dict):
        return 300
    return _confval.integer(cfg.get("default_timeout_sec"), 300, lo=1)

def _preview(text, n=80) -> str:
    """One line, capped. For the runner log, not for email."""
    if not isinstance(text, str):
        text = _as_str(text)
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 80
    if n < 1:
        n = 80
    line = text.replace("\r", " ").replace("\n", " ").strip()
    if len(line) > n:
        line = line[:n] + "..."
    return line


def log(msg: str, level: str = "INFO"):
    if level == "DEBUG" and not _VERBOSE:
        return
    # A minute budget so a busy inbox cannot flood the console.
    # Verbose is for a person watching: 200/min. Quiet is a service: 50/min.
    # WARN and ERROR always pass. Five jobs a minute is the design point.
    global _LOG_MINUTE, _LOG_COUNT, _LOG_DROPPED
    now = time.time()
    with _MAIL_LOCK:
        if now - _LOG_MINUTE >= 60:
            if _LOG_DROPPED:
                notice = (f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                          f"[INFO] log: {_LOG_DROPPED} line(s) suppressed "
                          f"this minute")
                try:
                    print(notice, flush=True)
                except Exception:
                    pass
                if _LOG_FILE:
                    append_bounded_log(_LOG_FILE, notice,
                                       _LOG_MAX_BYTES, _LOG_BACKUPS)
            _LOG_MINUTE = now
            _LOG_COUNT = 0
            _LOG_DROPPED = 0
        cap = 200 if _VERBOSE else 50
        if level not in ("WARN", "ERROR") and _LOG_COUNT >= cap:
            _LOG_DROPPED += 1
            return
        _LOG_COUNT += 1
        try:
            text = msg if isinstance(msg, str) else str(msg)
        except Exception:
            text = "<unprintable>"
        line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [{level}] {text}"
        # A closed stdout must not kill the runner. The file still gets it.
        try:
            # Operator lines only. Do not pass a secret value to log().
            # codeql[py/clear-text-logging-sensitive-data]
            print(line, flush=True)
        except Exception:
            pass
        if _LOG_FILE:
            append_bounded_log(_LOG_FILE, line,
                               _LOG_MAX_BYTES, _LOG_BACKUPS)

_LOG_FILE = None
if _mailbox_lib is not None:
    _mailbox_lib.set_logger(log)
_VERBOSE = False
_LOG_MINUTE = 0.0
_LOG_COUNT = 0
_LOG_DROPPED = 0
_LOG_WRITE_LOCK = threading.Lock()

# Verbosity is a level, not a switch:
#   0  quiet (--quiet): startup block and job results; DEBUG off,
#      cap 50 lines/min. This is _VERBOSE False, exactly as before.
#   1  the base level: every line the runner has always printed.
#      _VERBOSE True; DEBUG prints; cap 200/min.
#   2  verbose (-v, or "verbose": true in config): the base lines
#      plus vlog() decision lines at the points where the runner
#      decides something -- poll, ingest, the wake gate, the
#      judge, the board.
#   3+ (-vv and beyond): the noisier per-item lines join in.
# _VERBOSE stays the boolean it always was (level >= 1) so log()
# and every existing reader keep their meaning; _VERBOSE_LEVEL
# is the finer grain only vlog() consults.
_VERBOSE_LEVEL = 1

# Cleartext (HMAC-only) job acceptance is a per-process state,
# like verbosity -- and, unlike verbosity, it is set from the
# command line ONLY. There is deliberately no config key: a
# config file must not be able to turn acceptance on, and a hot
# reload must not be able to change it mid-run. main() sets it
# from --allow-cleartext; every other entry point leaves
# the default, which is to refuse.
_ALLOW_CLEARTEXT_JOBS = False

def _set_allow_cleartext_jobs(on) -> None:
    global _ALLOW_CLEARTEXT_JOBS
    _ALLOW_CLEARTEXT_JOBS = bool(on)

def _cleartext_jobs_allowed() -> bool:
    """True only when this process was started with
    --allow-cleartext. The HMAC signature is required
    either way; the flag waives the encryption requirement,
    never authentication."""
    return _ALLOW_CLEARTEXT_JOBS

def _admit_object(body_text, secrets, object_id):
    """Verify a transmitted body and, when it is an envelope,
    the object inside it.

    Returns (obj, key_id, secret, encrypted). An hp_enc
    envelope is verified, decrypted under object_id (the id
    in the subject), and the inner object is verified with
    the same key. A cleartext object comes back with
    encrypted False. The caller decides whether that form
    is allowed. Raises ValueError on a bad signature and
    JobCryptoError on a bad envelope.
    """
    if not isinstance(object_id, str):
        object_id = ""
    payload, key_id = verify_body_keyed(body_text, secrets)
    secret = secret_named(secrets, key_id)
    enc = payload.get("hp_enc") if isinstance(payload, dict) else None
    if not isinstance(enc, dict):
        return payload, key_id, secret, False
    if _jobcrypto is None or not _jobcrypto.is_envelope(payload):
        raise ValueError("malformed encryption envelope")
    inner_text = _jobcrypto.decrypt_body(
        payload, secret, job_id=object_id, key_id=key_id)
    inner, inner_key = verify_body_keyed(inner_text, secrets)
    if inner_key != key_id:
        raise ValueError(
            "encrypted envelope key_id does not match its body")
    return inner, key_id, secret, True

def _seal_reply(reply, secret, object_id, key_id, encrypted):
    """Sign a reply. Encrypt it when the request was encrypted."""
    text = sign_payload(reply, secret)
    if encrypted and _jobcrypto is not None:
        text = _jobcrypto.encrypt_body(
            text, secret, job_id=object_id, key_id=key_id or "",
            sign=sign_payload)
    return text

def _resolve_verbosity(cfg, flag) -> int:
    """The verbosity level for this process.

    The flag wins: --quiet parses to False, -v/--verbose to a
    count (1 for one -v, 2 for -vv). With no flag, the config
    key speaks: "verbose": true is level 2, false is quiet.
    With neither, the base level 1 -- the log the runner has
    always printed.
    """
    if flag is not None:
        return 0 if flag is False else 1 + int(flag)
    if isinstance(cfg, dict) and "verbose" in cfg:
        return 2 if _cfg_flag(cfg.get("verbose")) else 0
    return 1

def _set_verbosity(level) -> None:
    global _VERBOSE, _VERBOSE_LEVEL
    _VERBOSE_LEVEL = level
    _VERBOSE = level >= 1

def vlog(msg: str, level: int = 2) -> None:
    """One verbose decision line, prefixed "verbose:".

    Silent below the current level, so a base-level run's log is
    exactly what it was before verbose had levels. The existing
    lines never change; verbose only adds these.
    """
    if _VERBOSE_LEVEL >= level:
        log(f"verbose: {msg}")

# runner.log bounds, from config (log_max_bytes / log_backups).
# Refreshed at startup by _refresh_log_settings; the defaults here
# keep log() sane for any caller that runs before that.
_LOG_DEFAULT_MAX_BYTES = 33_554_432
_LOG_DEFAULT_BACKUPS = 4
_LOG_MAX_BYTES = _LOG_DEFAULT_MAX_BYTES
_LOG_BACKUPS = _LOG_DEFAULT_BACKUPS

# oracle.log: full-fidelity inference records (request payloads,
# replies, error bodies), gated by the `oracle_log` config key and
# sized by oracle_log_max_bytes / oracle_log_backups. Off by
# default: no file, no records, no behavior change.
_ORACLE_LOG_DEFAULT_MAX_BYTES = 536_870_912
_ORACLE_LOG_DEFAULT_BACKUPS = 4
_ORACLE_LOG_ENABLED = False
_ORACLE_LOG_PATH = None
_ORACLE_LOG_MAX_BYTES = _ORACLE_LOG_DEFAULT_MAX_BYTES
_ORACLE_LOG_BACKUPS = _ORACLE_LOG_DEFAULT_BACKUPS
_ORACLE_LOG_ANNOUNCED = False

def _cfg_size(value, default, hi):
    """A config size/count: invalid falls back, valid clamps to [1, hi].

    Booleans are not sizes. A non-numeric value must never crash the
    runner at startup; it just gets the default.
    """
    if isinstance(value, bool):
        return default
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if n < 1:
        return default
    return min(n, hi)

def _cfg_flag(value) -> bool:
    """An opt-in config boolean (oracle_log). Default off."""
    if value is True or value == 1:
        return True
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "on", "1")
    return False


def _log_bounds(cfg, max_key, max_default, max_cap, bak_key, bak_default):
    """(max_bytes, backups) from config keys or defaults."""
    if not isinstance(cfg, dict):
        cfg = {}
    return (
        _cfg_size(cfg.get(max_key), max_default, max_cap),
        _cfg_size(cfg.get(bak_key), bak_default, 10),
    )


def _log_settings(cfg):
    """(max_bytes, backups) for runner.log."""
    return _log_bounds(cfg, "log_max_bytes", _LOG_DEFAULT_MAX_BYTES, 2**40,
                       "log_backups", _LOG_DEFAULT_BACKUPS)

def _oracle_log_settings(cfg):
    """(max_bytes, backups) for oracle.log."""
    return _log_bounds(cfg, "oracle_log_max_bytes", _ORACLE_LOG_DEFAULT_MAX_BYTES, 2**42,
                       "oracle_log_backups", _ORACLE_LOG_DEFAULT_BACKUPS)

def _refresh_log_settings(cfg, base_dir):
    """Load the log bounds (and the oracle.log switch) from config.

    Called at startup, next to where _LOG_FILE itself is assigned,
    so every later log()/inference/daemon path sees the same values.
    """
    global _LOG_MAX_BYTES, _LOG_BACKUPS
    global _ORACLE_LOG_ENABLED, _ORACLE_LOG_PATH
    global _ORACLE_LOG_MAX_BYTES, _ORACLE_LOG_BACKUPS
    _LOG_MAX_BYTES, _LOG_BACKUPS = _log_settings(cfg)
    _ORACLE_LOG_MAX_BYTES, _ORACLE_LOG_BACKUPS = _oracle_log_settings(cfg)
    if isinstance(cfg, dict) and _cfg_flag(cfg.get("oracle_log")) \
            and isinstance(base_dir, str) and base_dir:
        _ORACLE_LOG_ENABLED = True
        _ORACLE_LOG_PATH = os.path.join(base_dir, "oracle.log")
    else:
        _ORACLE_LOG_ENABLED = False
        _ORACLE_LOG_PATH = None

def _announce_oracle_log():
    """One startup line in runner.log naming oracle.log. Once only."""
    global _ORACLE_LOG_ANNOUNCED
    if _ORACLE_LOG_ENABLED and _ORACLE_LOG_PATH \
            and not _ORACLE_LOG_ANNOUNCED:
        _ORACLE_LOG_ANNOUNCED = True
        log(f"oracle log enabled: full inference records are written "
            f"to {_ORACLE_LOG_PATH}")

def _oracle_log_record(record):
    """Append one full-fidelity inference record to oracle.log.

    Only model traffic is recorded: the request payload and the
    endpoint's reply. The config's shared secret and mailbox
    password are never part of either, so they cannot land here.
    Failures are swallowed: a debug log must not kill the ask path.
    The per-minute INFO cap applies to runner.log only, never here:
    records are written straight through append_bounded_log.
    """
    if not _ORACLE_LOG_ENABLED or not _ORACLE_LOG_PATH:
        return
    try:
        line = json.dumps(record, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return
    append_bounded_log(_ORACLE_LOG_PATH, line,
                       _ORACLE_LOG_MAX_BYTES, _ORACLE_LOG_BACKUPS)

def _oracle_log_exchange(endpoint, model, payload, started,
                         response=None, raw=None, error=None,
                         error_body=None):
    """Record one inference exchange in oracle.log (when enabled)."""
    if not _ORACLE_LOG_ENABLED:
        return
    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endpoint": endpoint,
        "model": model,
        "elapsed_sec": round(time.monotonic() - started, 3),
        "request": payload,
    }
    if response is not None:
        record["response"] = response
    if raw is not None:
        record["response_raw"] = raw
    if error is not None:
        record["error"] = error
    if error_body is not None:
        record["error_body"] = error_body
    _oracle_log_record(record)

def _log_job_output(job_id, kind, stdout, stderr, cfg):
    """Write a job's complete stdout/stderr to runner.log.

    The result email carries a bounded copy; the log keeps the whole
    output so a debugging session can read what the job actually
    said. Redaction still applies (the log never carries cleartext
    secrets, same as the one-line preview in execute_job). Written
    straight through append_bounded_log, not log(): the per-minute
    cap must not drop exactly the record a debugging session needs,
    and a chatty job must not flood the console.
    """
    if not _LOG_FILE:
        return
    patterns = _redact_patterns(cfg)
    out_text, _f1 = redact_text(stdout, patterns)
    err_text, _f2 = redact_text(stderr, patterns)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = (
        f"{stamp} [INFO] job {job_id} (kind={kind}) full output:\n"
        f"--- stdout ---\n{out_text}\n"
        f"--- stderr ---\n{err_text}\n"
        f"--- end of job {job_id} output ---")
    append_bounded_log(_LOG_FILE, record, _LOG_MAX_BYTES, _LOG_BACKUPS)

# Two locks, on purpose. This one covers the seen-set and
# _IN_FLIGHT. mailbox._MAIL_LOCK is a different lock: it
# serializes IMAP SEARCH, FETCH, STORE, and SMTP send on the
# shared connections. The mailbox lock is never held while
# taking this one. A STORE or SEARCH failure is logged after
# the mailbox lock is released, because log() takes this lock.
# _IN_FLIGHT stops two threads executing the same job_id.
# Production mail does not use the worker pool. The channel is
# serviced one envelope at a time. The pool is the injected
# mailbox path (the harness and the local SI test).
_MAIL_LOCK = threading.RLock()
_IN_FLIGHT: set = set()

def _file_label(f):
    """A files[] entry for the Oracle's description: the URL it is
    fetched from, or the inline name and size (the bytes stay out)."""
    if "content_b64" in f:
        raw = f.get("content_b64")
        size = (len(raw) * 3) // 4 if isinstance(raw, str) else 0
        return "inline:" + _as_str(f.get("name", "?")) + f" (~{size} bytes)"
    return _as_str(f.get("url", "?"))


def _describe_job(job: dict) -> str:
    """One-line summary of what a job would do (for --dry-run)."""
    if not isinstance(job, dict):
        return "invalid job"
    kind = job.get("kind")
    if kind == "ping":
        return "kind=ping (would reply pong)"
    if kind == "recipe":
        args = job.get("args")
        shown = [_as_str(a) for a in args] if isinstance(args, list) else []
        return (f"kind=recipe recipe={_as_str(job.get('recipe'))} "
                f"args={shown}")
    parts = ["kind=exec"]
    if job.get("script"):
        parts.append(f"inline script ({len(_as_str(job['script']))} chars)")
    if job.get("script_url"):
        parts.append("script_url=" + _as_str(job["script_url"]))
    if job.get("interpreter"):
        parts.append("interpreter=" + _as_str(job["interpreter"]))
    files = job.get("files") or []
    if isinstance(files, list) and files:
        parts.append(f"{len(files)} file(s): " +
                     ", ".join(_file_label(f) for f in files
                               if isinstance(f, dict)))
    if job.get("args"):
        args = job["args"]
        if isinstance(args, list):
            shown = [_as_str(a) for a in args]
        else:
            shown = _as_str(args)
        parts.append(f"args={shown}")
    if job.get("timeout_sec"):
        parts.append("timeout_sec=" + _as_str(job["timeout_sec"]))
    return ", ".join(parts)

def _issued_at_ok(value, cfg):
    """Return (ok, reason) for a protocol issued_at string."""
    try:
        issued = _fromiso(value)
    except Exception:
        return False, "unparseable issued_at"
    if issued.tzinfo is None or issued.tzinfo.utcoffset(issued) is None:
        return False, "issued_at missing timezone"
    age = (datetime.now(timezone.utc) - issued).total_seconds()
    # Documented default 3600. Zero, a negative number, a boolean, or
    # a non-number would reject every job as stale; none is a window.
    window = _confval.integer(cfg.get("max_job_age_sec"), 3600, lo=1)
    if age < -300 or age > window:
        return False, "issued_at outside allowed window"
    return True, ""

def _mark(imap, seq, opts):
    if opts is None or not opts.dry_run:
        mark_seen(imap, seq)


_startup = _required_load_mod("runner.ops.startup", "ops.startup")
log_startup = _startup.log_startup
handle_board_mail = _startup.handle_board_mail


def _load_reviewed_extensions(cfg, base_dir):
    """The loader's (registry, problems) for the owner's sense
    extensions, with the extension review applied: under `enforce`
    (the default) an extension whose code contradicts its manifest
    is dropped here and its refusal joins `problems`, in the loader's
    own vocabulary. The review is cached per folder until a file in
    it changes, so the alert path pays for a directory listing, not
    a re-read. Raises only what the loader raises."""
    registry, problems = _extensions.load_extensions(
        _extensions.extensions_dir_for(cfg, base_dir))
    if not isinstance(registry, dict):
        registry = {}
    if not isinstance(problems, list):
        problems = []
    if _extreview is not None and registry:
        registry, refusals, _report = _extreview.apply(
            cfg, base_dir, registry, kind="sense", log=log,
            event_sink=lambda ev: _append_security_event(base_dir, ev))
        problems = list(problems) + list(refusals)
    return registry, problems

def _extension_registry(cfg, base_dir) -> dict:
    """Loaded user extensions, keyed by sensor name. Never raises.

    A broken or incompatible extension is refused by the loader, and
    one whose code contradicts its manifest by the extension review
    (runner/guard/extreview.py); either is simply absent here. The
    refusal is read at startup (_report_extensions), not re-litigated
    on the alert path.
    """
    if _extensions is None:
        return {}
    try:
        registry, _problems = _load_reviewed_extensions(cfg, base_dir)
    except Exception:
        return {}
    return registry if isinstance(registry, dict) else {}

def _report_extensions(cfg, base_dir) -> None:
    """Startup report: which user extensions loaded, which were refused."""
    if _extensions is None:
        return
    try:
        registry, problems = _load_reviewed_extensions(cfg, base_dir)
    except Exception as e:
        log(f"extensions: loader failed: {e}", "WARN")
        return
    if not isinstance(registry, dict):
        registry = {}
    for name in sorted(registry):
        m = registry[name]
        if not isinstance(m, dict):
            continue
        caps = m.get("capabilities") or []
        log(f"extension loaded: {m.get('name')} v{m.get('version')} "
            f"(extension API v{m.get('api_version')}, kind "
            f"{m.get('kind')}, {len(m.get('signals') or [])} declared "
            f"signal(s), capabilities: "
            f"{', '.join(caps) if caps else 'none'}) from {m.get('dir')}")
    for problem in problems if isinstance(problems, list) else []:
        log(f"extensions: {problem}", "WARN")

def _extension_review_now(cfg, base_dir) -> dict:
    """Review every extension this agent would load -- the owner's
    senses and every transport the discovery finds -- and return the
    report (`--inspect review`). Reads the folders now; writes
    <base_dir>/extension-review.json as the agent itself would."""
    if _extreview is not None:
        _extreview.forget()
    out = {"mode": _extreview.mode_of(cfg)[0] if _extreview else "off",
           "senses": {}, "transports": {}, "problems": []}
    if _extensions is not None:
        try:
            registry, problems = _extensions.load_extensions(
                _extensions.extensions_dir_for(cfg, base_dir))
        except Exception as e:
            registry, problems = {}, [f"loader failed: {e}"]
        out["problems"].extend(problems if isinstance(problems, list) else [])
        if _extreview is not None and isinstance(registry, dict):
            _reg, refusals, report = _extreview.apply(
                cfg, base_dir, registry, kind="sense")
            out["senses"] = report.get("extensions", {})
            out["problems"].extend(refusals)
    if _transports is not None:
        try:
            _registry, problems = _transports.discover_transport_extensions(
                cfg, base_dir)
            out["problems"].extend(problems)
        except Exception as e:
            out["problems"].append(f"transport discovery failed: {e}")
        if _extreview is not None:
            data = _extreview.last_report(base_dir, "transport") or {}
            out["transports"] = data.get("extensions", {})
    return out

# ---------------------------------------------------------------------------
# Extension sources (runner/ops/extsources.py). The first time this agent
# runs an extension -- loads a sense, starts a transport -- a
# background pass gives the Oracle that extension's own code and the
# upstream sources and specs its sources.json declares, under the
# disclosure rule. The pass repeats on a timer, which is how retries,
# newly dropped-in extensions, and live config edits are picked up;
# work already done is never redone.

_EXTSOURCES_PASS: dict = {"thread": None, "next_due": 0.0, "problem": None,
                          "since": None}
_EXTSOURCES_LOCK = threading.Lock()
# The first pass waits this long after the agent starts, so a
# short-lived process -- one cycle, a run stopped at once, a test
# that drives the loop -- never starts fetching into a state dir
# that is about to go away.
EXTSOURCES_STARTUP_GRACE_SEC = 60

def _model_oracle_configured(cfg) -> bool:
    """Whether a local model runs the Oracle.

    inference_config's answer, without its log line: this is asked
    on a timer, and a refused endpoint is reported elsewhere.
    """
    if not isinstance(cfg, dict) or _oracle_mode(cfg) == "deterministic":
        return False
    inf = cfg.get("inference")
    if not isinstance(inf, dict):
        return False
    endpoint, model = inf.get("endpoint"), inf.get("model")
    if not isinstance(endpoint, str) or not isinstance(model, str) \
            or not endpoint.strip() or not model.strip():
        return False
    return _endpoint_is_loopback(endpoint.strip())

def _extension_source_targets(cfg, base_dir) -> list:
    """Every extension this agent runs: each loaded sense extension
    and each enabled transport that has a loadable extension."""
    out = []
    for name, m in sorted(_extension_registry(cfg, base_dir).items()):
        if isinstance(m, dict) and isinstance(m.get("dir"), str):
            out.append({"kind": "sense", "name": name,
                        "version": m.get("version") or "",
                        "dir": m["dir"],
                        "description": m.get("description") or ""})
    if _transports is not None:
        try:
            enabled = _transports.enabled_transports(cfg)
            registry, _problems = _transports.discover_transport_extensions(
                cfg, base_dir)
        except Exception:
            enabled, registry = [], {}
        for name in enabled:
            m = registry.get(name)
            if isinstance(m, dict) and isinstance(m.get("dir"), str):
                out.append({"kind": "transport", "name": name,
                            "version": m.get("version") or "",
                            "dir": m["dir"],
                            "description": m.get("description") or ""})
    return out

def _extension_sources_policy(cfg, model_oracle=None):
    if _extsources is None:
        return None
    policy = _extsources.owner_policy(
        cfg, _model_oracle_configured(cfg) if model_oracle is None
        else model_oracle)
    if policy.get("problem") != _EXTSOURCES_PASS.get("problem"):
        _EXTSOURCES_PASS["problem"] = policy.get("problem")
        if policy.get("problem"):
            log(policy["problem"] + "; nothing is fetched and every "
                "extension source is withheld from the Oracle until it "
                "is fixed", "WARN")
    return policy

def _extension_sources_pass(cfg, base_dir, force=False, fetcher=None):
    """One provisioning pass, in the calling thread. Never raises."""
    if _extsources is None:
        return None
    try:
        policy = _extension_sources_policy(cfg)
        return _extsources.provision(
            base_dir, _extension_source_targets(cfg, base_dir), policy,
            fetcher=fetcher, log=log, force=force)
    except Exception as e:
        log(f"extension sources: pass failed: {e}", "WARN")
        return None

def _extension_sources_start(now=None) -> None:
    """main() calls this once at startup: the first background pass
    is due EXTSOURCES_STARTUP_GRACE_SEC later."""
    now = time.time() if now is None else now
    with _EXTSOURCES_LOCK:
        _EXTSOURCES_PASS["since"] = now
        _EXTSOURCES_PASS["next_due"] = now + EXTSOURCES_STARTUP_GRACE_SEC

def _extension_sources_tick(cfg, base_dir, now=None, due_now=False) -> bool:
    """Start a background pass when one is due. Never raises.

    Due a minute after startup (_extension_sources_start), every
    PASS_INTERVAL_SEC after, and at once when config.json changes
    (the disclosure rule is live) -- never inside the startup grace,
    and never in a process that did not start the loop. One pass at
    a time; a pass in flight makes the tick a no-op. Returns whether
    a pass was started.
    """
    if _extsources is None or not isinstance(base_dir, str) or not base_dir:
        return False
    now = time.time() if now is None else now
    with _EXTSOURCES_LOCK:
        since = _EXTSOURCES_PASS.get("since")
        if since is None or now < since + EXTSOURCES_STARTUP_GRACE_SEC:
            return False
        th = _EXTSOURCES_PASS.get("thread")
        if th is not None and th.is_alive():
            return False
        if not due_now and now < _EXTSOURCES_PASS["next_due"]:
            return False
        _EXTSOURCES_PASS["next_due"] = now + _extsources.PASS_INTERVAL_SEC
        try:
            snapshot = copy.deepcopy(cfg)
        except Exception:
            snapshot = dict(cfg) if isinstance(cfg, dict) else {}
        th = threading.Thread(target=_extension_sources_pass,
                              args=(snapshot, base_dir),
                              name="extension-sources", daemon=True)
        _EXTSOURCES_PASS["thread"] = th
        th.start()
        return True

def _report_extension_sources(cfg, base_dir) -> None:
    """Startup line: whether extension sources will be fetched."""
    if _extsources is None:
        return
    policy = _extension_sources_policy(cfg)
    if policy is None or not policy.get("valid"):
        return
    overrides = [n for n, o in policy["extensions"].items()
                 if o.get("fetch") is True]
    if policy["enabled"] or overrides:
        log("extension sources: on its first run each extension's code, "
            "and the upstream sources and specs it declares, are fetched "
            "in the background for the Oracle (budget %d MB; index %s/%s)"
            % (policy["max_bytes"] // (1 << 20), _extsources.STATE_DIRNAME,
               _extsources.INDEX_FILE))
    elif policy["fetch"] == "auto":
        log("extension sources: off -- extension_sources is \"auto\" "
            "and no local model runs the Oracle (true fetches anyway)")
    else:
        log("extension sources: off (extension_sources is false)")

def _extension_sources_note(base_dir) -> str:
    """The Oracle's context line for extension sources, or ""."""
    if _extsources is None or not isinstance(base_dir, str) or not base_dir:
        return ""
    try:
        return _extsources.oracle_note(base_dir)
    except Exception:
        return ""

def run_fetch_sources(cfg, args, fetcher=None) -> int:
    """--fetch-sources: one provisioning pass in the foreground.

    Retries what failed without waiting out its backoff and prints
    what happened. Asking counts as wanting it: even "auto" fetches
    here with no local model, and only extension_sources false (or a
    per-extension fetch false) still stops it.
    """
    if _extsources is None:
        print("extension sources: runner/ops/extsources.py is unavailable",
              file=sys.stderr)
        return 1
    base = _base_dir_for(cfg, getattr(args, "config", None))
    policy = _extension_sources_policy(cfg, model_oracle=True)
    if not policy.get("valid"):
        print(policy["problem"], file=sys.stderr)
        return 2
    targets = _extension_source_targets(cfg, base)
    if not any(_extsources.fetch_allowed(policy, t["name"])
               for t in targets):
        print("extension sources: nothing to fetch (no extension runs "
              "here, or extension_sources is false)")
        return 0
    report = _extsources.provision(
        base, targets, policy, fetcher=fetcher,
        log=lambda msg, level="INFO": print(msg), force=True)
    if report.get("busy"):
        print("extension sources: another pass is running; try again "
              "when it finishes", file=sys.stderr)
        return 1
    short = [o for o in report["outcomes"]
             if o["status"] not in ("fetched",)]
    print("extension sources: %d entr%s worked on, %d not complete; "
          "%.1f MB of %d MB used; index: %s"
          % (len(report["outcomes"]),
             "y" if len(report["outcomes"]) == 1 else "ies", len(short),
             report["used_bytes"] / (1 << 20),
             report["budget_bytes"] // (1 << 20),
             os.path.join(_extsources.state_root(base),
                          _extsources.INDEX_FILE)))
    return 1 if short else 0


def _ingest_sensor_alert(cfg, imap, seq, job_id, job, key_id,
                         secrets, opts, base_dir, seen):
    """File a signed sensor alert. Alerts are stored, never executed.

    The signing key must be bound to the sensor it files for
    (sensors.<name>.key_id), and the key's key_policies entry should
    allow only kind "sensor_alert". The sense profile gates what is
    kept; drops are logged, not errors.

    The signature was verified by the caller (handle_mail); the
    validation and filing live in _sensor_alert_core, shared with
    the local delivery path.
    """
    dry = opts is not None and opts.dry_run
    status, why, _record = _sensor_alert_core(
        cfg, job, key_id, base_dir, dry=dry,
        names=key_names(secrets, key_id))
    if status == "dry":
        log(f"dry-run: would ingest sensor alert {job_id} "
            f"({job.get('sensor')}/{job.get('severity', 'info')}: "
            f"{job.get('title')})")
        return
    if status == "config":
        log(f"sensor alert {job_id}: rejected: {why}", "ERROR")
    else:
        log(f"sensor alert {job_id}: {why}")
    if not dry:
        with _MAIL_LOCK:
            seen[_seen_key(cfg, job_id)] = True
            mark_seen(imap, seq)

# ---------------------------------------------------------------------------
# Local signals: same-box delivery for senses and extensions.
#
# A sensor or extension running on the SAME machine as the runner
# delivers its alerts directly instead of mailing them. Two
# front-ends, one ingest core: a producer either drops a signed
# envelope file into <base_dir>/local-inbox/ (the periodic style --
# the producer's own cadence, the watcher scans about once a
# second), or pushes the identical envelope over a loopback TCP
# connection (the direct style -- fire and send, no file). The
# envelope is the extension contract: the same fields, the same
# api_version statement, the same HMAC signature the mail path
# verifies. A transport is replaceable plumbing under that
# contract, never a new contract; an author codes against the
# envelope, not the pipe. Everything after the transport is the
# mail path's chain unchanged (verify_body_keyed, the envelope
# checks, check_key_policy, then _sensor_alert_core). A bad
# signature is a rejection exactly as on the mail path; local
# delivery adds no trust, it removes a mailbox.
#
# A locally filed alert also faces the wake gate: a high or
# critical alert can wake the Oracle, which writes an assessment
# into oracle-briefs.jsonl. The gate is deterministic (severity,
# per-(sensor, signal) cooldown, single flight) so a noisy sense
# cannot keep the model -- and the box -- busy.

LOCAL_INBOX_DIRNAME = "local-inbox"
LOCAL_BRIEFS_FILE = "oracle-briefs.jsonl"
LOCAL_SIGNAL_DEFAULT_PORT = 39271
_LOCAL_ENVELOPE_MAX_BYTES = 262144
_LOCAL_BRIEFS_CAP = 1000
_LOCAL_BRIEFS_KEEP = 500

def _local_signals_enabled(cfg) -> bool:
    """Top-level local_signals switch; default on."""
    if not isinstance(cfg, dict):
        return True
    v = cfg.get("local_signals", True)
    if v is False or v == 0:
        return False
    if isinstance(v, str) and v.strip().lower() in ("false", "no", "off", "0"):
        return False
    return True

def _local_signal_port(cfg) -> int:
    """Loopback listener port; 0 means the listener is off.

    Default LOCAL_SIGNAL_DEFAULT_PORT. False/None/0 turn it off;
    a value that is not a usable port number reads as off, so a
    typo silences the listener instead of binding a surprise port.
    """
    if not isinstance(cfg, dict):
        return LOCAL_SIGNAL_DEFAULT_PORT
    v = cfg.get("local_signal_port", LOCAL_SIGNAL_DEFAULT_PORT)
    if v is None or v is False:
        return 0
    if v is True:
        return LOCAL_SIGNAL_DEFAULT_PORT
    try:
        p = int(v)
    except (TypeError, ValueError, OverflowError):
        return 0
    if p < 0 or p > 65535:
        return 0
    return p

def _local_wake_cooldown(cfg) -> float:
    """Seconds between wakes for one (sensor, signal). Default 900."""
    raw = cfg.get("local_wake_cooldown_sec", 900) \
        if isinstance(cfg, dict) else 900
    return float(_confval.number(raw, 900.0, lo=0))

def _ingest_local_envelope(cfg, base_dir, text, source):
    """Verify and file one locally delivered sensor_alert envelope.

    `source` is the front-end's name ("file" or "socket") and is
    used in log lines only. Returns the stored record, or None.
    Never raises.
    """
    try:
        return _ingest_local_envelope_inner(cfg, base_dir, text, source)
    except Exception as e:  # the front-ends must survive any envelope
        log(f"local signal ({source}): ingest failed: {e}", "WARN")
        return None

def _ingest_local_envelope_inner(cfg, base_dir, text, source):
    def reject(why):
        vlog(f"local signal ({source}): rejected: {why}")
        log(f"local signal ({source}): rejected: {why}", "WARN")
        return None

    if not isinstance(text, str) or not text.strip():
        return reject("empty envelope")
    if len(text.encode("utf-8", "replace")) > _LOCAL_ENVELOPE_MAX_BYTES:
        return reject("envelope too large")
    try:
        secrets = build_secrets(cfg)
        key_policies = build_key_policies(cfg)
    except RuntimeError as e:
        return reject(str(e))
    try:
        job, key_id = verify_body_keyed(text, secrets)
    except ValueError as e:
        log(f"local signal ({source}): rejected: bad signature: {e}",
            "WARN")
        _auth_reject_event(base_dir, "bad_signature", feature="local_signals")
        return None
    job_id = job.get("job_id")
    if not isinstance(job_id, str) or not _SAFE_JOB_ID.match(job_id) \
            or job_id in (".", ".."):
        return reject("job_id missing or not a safe id")
    # The envelope states the extension contract it was written
    # against, and the statement is validated exactly as the
    # manifest's is: newer than this agent provides is refused,
    # older is accepted under the additive-only promise.
    if _extensions is not None:
        refusal = _extensions.api_refusal(
            {"api_version": job.get("api_version")})
        if refusal:
            return reject(f"envelope api_version: {refusal}")
    if job.get("kind") != "sensor_alert":
        return reject(f"kind {job.get('kind')!r} is not sensor_alert; "
                      f"local delivery files alerts only")
    if not _version_ok(job.get("v")) or job.get("type") != "job":
        return reject("unsupported version/type")
    try:
        issued = _fromiso(job["issued_at"])
    except Exception:
        return reject("unparseable issued_at")
    if issued.tzinfo is None or issued.tzinfo.utcoffset(issued) is None:
        return reject("issued_at missing timezone (must be UTC / end with Z)")
    age = (datetime.now(timezone.utc) - issued).total_seconds()
    max_age = _confval.integer(cfg.get("max_job_age_sec"), 3600, lo=1)
    if age < -300 or age > max_age:
        return reject(f"issued_at outside allowed window (age {age:.0f}s)")
    violation = check_key_policy(key_policies, key_id, cfg, job,
                                 secrets=secrets)
    if violation:
        _auth_reject_event(base_dir, "key_policy", feature="local_signals")
        return reject(f"key policy: {violation}")
    status, why, record = _sensor_alert_core(
        cfg, job, key_id, base_dir, extra={"source": "local"},
        names=key_names(secrets, key_id))
    log(f"local sensor alert {job_id} via {source}: {why}")
    vlog(f"local signal ({source}): job {job_id}: {status}: {why}")
    if status == "stored" and record is not None:
        _maybe_wake_oracle(cfg, base_dir, record)
        return record
    return None

# --- the wake gate and the briefing ----------------------------------------

_LOCAL_WAKE_LOCK = threading.Lock()
_LOCAL_WAKE_LAST = {}
_LOCAL_WAKE_INFLIGHT = False

def _wake_gate_decide(cfg, record, now=None) -> bool:
    """True when this locally filed alert may wake the Oracle now.

    Deterministic: severity high or critical, no other briefing in
    flight, and the (sensor, signal) pair has not woken within the
    cooldown. Deciding marks the wake (cooldown starts, flight
    begins); _wake_gate_release ends the flight. Pure state plus
    the injected clock -- tests drive it without threads.
    """
    global _LOCAL_WAKE_INFLIGHT
    if not isinstance(record, dict) or _senses is None:
        return False
    sev = record.get("severity")
    score = _senses.SEVERITY_SCORES.get(sev, 0.0) \
        if isinstance(sev, str) else 0.0
    sensor = record.get("sensor")
    signal = record.get("signal") or record.get("title")
    high = _senses.SEVERITY_SCORES["high"]
    if score < high:
        vlog(f"wake gate: {sensor}/{signal} severity={sev} "
             f"score={score:g} < high {high:g}: no wake")
        return False
    try:
        t = float(time.monotonic() if now is None else now)
    except (TypeError, ValueError, OverflowError):
        t = time.monotonic()
    key = (sensor if isinstance(sensor, str) else "",
           signal if isinstance(signal, str) else "")
    cooldown = _local_wake_cooldown(cfg)
    age = 0.0
    with _LOCAL_WAKE_LOCK:
        if _LOCAL_WAKE_INFLIGHT:
            outcome = "inflight"
        else:
            last = _LOCAL_WAKE_LAST.get(key)
            if last is not None and t - last < cooldown:
                outcome = "cooldown"
                age = t - last
            else:
                _LOCAL_WAKE_LAST[key] = t
                _LOCAL_WAKE_INFLIGHT = True
                outcome = "fire"
    if outcome == "inflight":
        vlog(f"wake gate: {sensor}/{signal}: a briefing is "
             f"already in flight: no wake")
        return False
    if outcome == "cooldown":
        vlog(f"wake gate: {sensor}/{signal} score={score:g}: "
             f"woke {age:.0f}s ago, cooldown is "
             f"{cooldown:.0f}s: no wake")
        return False
    vlog(f"wake gate: {sensor}/{signal} severity={sev} "
         f"score={score:g} >= high {high:g}, cooldown clear: "
         f"waking the Oracle")
    return True

def _wake_gate_release() -> None:
    global _LOCAL_WAKE_INFLIGHT
    with _LOCAL_WAKE_LOCK:
        _LOCAL_WAKE_INFLIGHT = False

def _maybe_wake_oracle(cfg, base_dir, record, now=None) -> bool:
    """Wake the Oracle for one locally filed alert, if the gate allows."""
    if not _wake_gate_decide(cfg, record, now=now):
        return False
    _start_brief_thread(cfg, base_dir, record)
    return True

def _start_brief_thread(cfg, base_dir, record):
    def _go():
        try:
            _oracle_brief(cfg, base_dir, record)
        except Exception:
            pass
        finally:
            _wake_gate_release()

    th = threading.Thread(target=_go, name="oracle-brief", daemon=True)
    th.start()
    return th

_BRIEF_LOCK = threading.Lock()

def _append_brief(base_dir, brief) -> None:
    """Append one brief record to oracle-briefs.jsonl. Best effort."""
    if not _valid_base(base_dir):
        return
    path = os.path.join(base_dir, LOCAL_BRIEFS_FILE)
    try:
        line = json.dumps(_json_safe(brief), ensure_ascii=False,
                          allow_nan=False) + "\n"
    except (TypeError, ValueError):
        return
    with _BRIEF_LOCK:
        try:
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            fd = _safe_open(path, flags, 0o600)
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
            _chmod_quiet(path)
            if os.path.islink(path):
                return
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
            if len(lines) > _LOCAL_BRIEFS_CAP:
                body = "".join(lines[-_LOCAL_BRIEFS_KEEP:]).encode("utf-8")
                fd = os.open(path, os.O_WRONLY | os.O_TRUNC
                             | (os.O_NOFOLLOW if hasattr(os, "O_NOFOLLOW")
                                else 0), 0o600)
                try:
                    os.write(fd, body)
                finally:
                    os.close(fd)
        except OSError:
            pass


# --- front-end 1: the inbox watcher ----------------------------------------

_LOCAL_INBOX_LOCK = threading.Lock()

def _local_inbox_dir(base_dir):
    if not _valid_base(base_dir):
        return ""
    return os.path.join(base_dir, LOCAL_INBOX_DIRNAME)

def _scan_local_inbox(cfg, base_dir) -> int:
    """File every envelope currently in the local inbox.

    Each .json file is read once, handed to the ingest core, and
    removed either way: a rejected envelope is logged there, and a
    file left behind would be re-processed every second forever.
    Non-.json entries are not envelopes and are left alone. Returns
    how many files were handled. Never raises.
    """
    inbox = _local_inbox_dir(base_dir)
    if not inbox:
        return 0
    handled = 0
    with _LOCAL_INBOX_LOCK:
        try:
            names = sorted(os.listdir(inbox))
        except OSError:
            return 0
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(inbox, name)
            if os.path.isdir(path) and not os.path.islink(path):
                # A directory is not an envelope and cannot be
                # removed like one; left alone, like a non-.json
                # entry, rather than handled and logged every scan.
                continue
            try:
                if os.path.islink(path):
                    log(f"local signal (file): {name}: symlink refused",
                        "WARN")
                else:
                    with open(path, "rb") as fh:
                        raw = fh.read(_LOCAL_ENVELOPE_MAX_BYTES + 1)
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        log(f"local signal (file): {name}: envelope is "
                            f"not UTF-8; dropped", "WARN")
                    else:
                        _ingest_local_envelope(cfg, base_dir, text, "file")
            except Exception as e:
                log(f"local signal (file): {name}: failed: {e}", "WARN")
            finally:
                _unlink_quiet(path)
            handled += 1
    if handled:
        vlog(f"local signals: {handled} envelope(s) filed "
             f"from the inbox")
    return handled

# The local front-end threads pace themselves on this event
# rather than time.sleep: the runner's own poll cadence is a
# tested behavior, and a background thread must not show up in it.
_LOCAL_TICK = threading.Event()

def _local_inbox_watcher(cfg, base_dir) -> None:
    """Daemon loop: one inbox scan about once a second.

    Independent of the mail poll on purpose: local delivery is the
    fast path, and its cadence must not inherit the mailbox's.
    Failure-isolated: nothing in here may kill the thread or the
    runner, so every scan is wrapped and the loop always waits.
    """
    while True:
        try:
            if _local_signals_enabled(cfg):
                _scan_local_inbox(cfg, base_dir)
        except Exception:
            pass
        _LOCAL_TICK.wait(1.0)

# --- front-end 2: the loopback listener -------------------------------------

def _local_signal_server(cfg, base_dir):
    """A bound, listening loopback socket, or None. Never raises."""
    port = _local_signal_port(cfg)
    if not port:
        return None
    srv = None
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(16)
        srv.settimeout(1.0)
    except OSError as e:
        log(f"local signals: cannot listen on 127.0.0.1:{port}: {e}",
            "WARN")
        if srv is not None:
            try:
                srv.close()
            except OSError:
                pass
        return None
    return srv

def _handle_local_signal_conn(cfg, base_dir, conn) -> None:
    """Read one envelope from one connection and file it. Never raises."""
    try:
        conn.settimeout(5.0)
    except OSError:
        return
    chunks = []
    total = 0
    while total <= _LOCAL_ENVELOPE_MAX_BYTES:
        try:
            data = conn.recv(65536)
        except socket.timeout:
            break  # the producer went quiet; what arrived is the envelope
        except OSError:
            return
        if not data:
            break
        chunks.append(data)
        total += len(data)
    if total > _LOCAL_ENVELOPE_MAX_BYTES:
        log("local signal (socket): envelope too large; dropped", "WARN")
        return
    if not chunks:
        return
    if not _local_signals_enabled(cfg):
        log("local signal (socket): dropped; local_signals is off",
            "WARN")
        return
    try:
        text = b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError:
        log("local signal (socket): envelope is not UTF-8; dropped",
            "WARN")
        return
    _ingest_local_envelope(cfg, base_dir, text, "socket")

def _serve_local_signals(cfg, base_dir, srv) -> None:
    """Accept loop for the loopback listener. Failure-isolated."""
    while True:
        try:
            conn, _addr = srv.accept()
        except socket.timeout:
            continue
        except OSError:
            _LOCAL_TICK.wait(0.2)
            continue
        try:
            _handle_local_signal_conn(cfg, base_dir, conn)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

def _start_local_signals(cfg, base_dir) -> None:
    """Start the local signal front-ends (daemon threads). Never raises.

    Called once from main() on the runner path. Whether the
    front-ends are on is read from the config as loaded at startup:
    local_signals and local_signal_port are startup settings, like
    the mailbox credentials, not hot keys. The listener socket is
    bound here, synchronously, so a bind failure is one startup
    log line from this thread -- the daemon threads then only
    scan and accept, and write nothing on their idle paths.
    """
    try:
        if not _local_signals_enabled(cfg):
            log("local signals: off (local_signals=false)")
            return
        inbox = _local_inbox_dir(base_dir)
        if inbox:
            try:
                os.makedirs(inbox, exist_ok=True)
            except OSError:
                pass
        port = _local_signal_port(cfg)
        srv = _local_signal_server(cfg, base_dir) if port else None
        threading.Thread(target=_local_inbox_watcher,
                         args=(cfg, base_dir),
                         name="local-inbox", daemon=True).start()
        if srv is not None:
            threading.Thread(target=_serve_local_signals,
                             args=(cfg, base_dir, srv),
                             name="local-signals", daemon=True).start()
        log(f"local signals: on; inbox {inbox or '(none)'} scanned "
            f"every second"
            + (f"; direct push on 127.0.0.1:{port}" if srv is not None
               else "; socket listener off"))
    except Exception as e:
        log(f"local signals: failed to start: {e}", "WARN")

def _opinion_env_facts(cfg, job):
    """Environment facts for the tier-1 opinion checks.

    The interpreter is resolved exactly the way execute_job will
    resolve it (job value, else configured default, else the
    platform default), so the opinion reads the job the box will
    actually run.
    """
    interpreter = job.get("interpreter") or cfg.get("default_interpreter") \
        or platform_interpreter()
    if not isinstance(interpreter, list) or not interpreter \
            or not all(isinstance(x, str) for x in interpreter):
        interpreter = platform_interpreter()
    return _opinion.gather_facts(job, interpreter, platform_interpreter())

def _opinion_model_note(cfg, job):
    """Tier-2 opinion note from the local model, or None.

    Only when the owner opted in (oracle_opinion_model) and
    inference is configured. inference_config is None in
    deterministic Oracle mode, so on a Pi Light box this never
    reaches a model. The caller asks only when tier 1 found
    nothing: the tiers are never blended into one claim.
    """
    if not _opinion.model_enabled(cfg):
        return None
    inf = inference_config(cfg)
    if inf is None:
        return None
    try:
        res = ask_model(
            inf,
            "Will this job succeed on this host? Answer in one or "
            "two plain sentences; if it will fail, say the obvious "
            "reason.",
            _describe_job(job), 400, _redact_patterns(cfg))
    except Exception:
        return None
    if not isinstance(res, dict):
        return None
    text = res.get("answer")
    if not isinstance(text, str) or not text.strip():
        return None
    return text.strip()[:240]

def _learning_fingerprint():
    return _learning.host_fingerprint(
        socket.gethostname(), "nt" if os.name == "nt" else "posix")

def _learning_active(cfg, plan):
    """The self-learning loop runs for a job when the module
    loaded, the owner has not turned it off (oracle_learning),
    and the job's effective opinion latitude is not off."""
    return _learning is not None and plan is not None \
        and bool(plan.get("active")) and plan.get("mode") != "off" \
        and _learning.learning_enabled(cfg)

def _learning_context(cfg, base_dir, facts):
    """Fresh lessons for this job: (relevant, note sentences).

    The ledger is read from disk here, at this job's opinion
    evaluation -- no cached copy, no restart. Any failure
    yields empty context: learning never blocks a job.
    """
    if _learning is None or not _learning.learning_enabled(cfg):
        return None, []
    try:
        state = _learning.load_state(base_dir, cfg)
        relevant = _learning.relevant_lessons(
            state, cfg, _learning_fingerprint(), facts)
        return relevant, _learning.lesson_notes(relevant)
    except Exception as e:
        log(f"oracle learning: context load failed: {e}", "WARN")
        return None, []

def _learning_freeze(cfg, base_dir, job_id, job, plan, facts,
                     relevant):
    """Persist the frozen pre-execution call. Returns the
    frozen record, or None. Never raises: a failed freeze is
    logged and the job proceeds exactly as before."""
    if not _learning_active(cfg, plan):
        return None
    try:
        attach = plan.get("attach") or {}
        verdict = attach.get("verdict")
        if verdict is None and plan.get("checks_run"):
            verdict = _opinion.verdict_of(plan["findings"])
        features = _learning.feature_keys(facts)
        repair = None
        if plan.get("repair_action"):
            repair = {
                "action": plan["repair_action"].get("action"),
                "description": plan["repair_action"].get(
                    "description"),
            }
        record = _learning.prediction_record(
            job_id, _opinion.received_digest(job),
            _learning_fingerprint(), plan["mode"], verdict,
            plan["findings"], features, repair)
        if repair is not None and relevant is not None:
            picked = _learning.lesson_selects(relevant, features)
            if picked is not None:
                record["lesson_selected"] = picked["claim_key"]
        if not _learning.freeze(base_dir, record):
            log(f"oracle learning: prediction freeze failed for "
                f"{job_id}", "WARN")
            return None
        return record
    except Exception as e:
        log(f"oracle learning: freeze failed for {job_id}: {e}",
            "WARN")
        return None

def _learning_reconcile(cfg, base_dir, frozen, job_id, outcome,
                        facts, diag_facts):
    """Score the frozen call against the verified outcome and
    persist what it teaches. Never raises: a learning-write
    failure is logged and the job's result proceeds."""
    if _learning is None or not _learning.learning_enabled(cfg):
        return None
    if frozen is None and diag_facts is None:
        return None
    try:
        features = list((frozen or {}).get("features") or [])
        if not features and diag_facts is not None:
            features = _learning.feature_keys(diag_facts)
        touched = _learning.touched_keys(diag_facts or facts or {})
        record = _learning.reconcile(
            base_dir, cfg, frozen, outcome, features, touched,
            job_id, _learning_fingerprint())
        if record is None:
            log(f"oracle learning: reconcile write failed for "
                f"{job_id}", "WARN")
        return record
    except Exception as e:
        log(f"oracle learning: reconcile failed for {job_id}: {e}",
            "WARN")
        return None


_handlers = _required_load_mod("runner.ops.handlers", "ops.handlers")
oracle_cli = _handlers.oracle_cli
handle_v2_mail = _handlers.handle_v2_mail
run_variant = _handlers.run_variant


def _v2_leave_unseen(ident):
    """Log once that this process will not answer a question.

    The message stays unseen. A later poll will see it again;
    the set is only so that does not log every time.
    """
    if not isinstance(ident, str):
        ident = str(ident)
    if ident in _V2_LEFT_UNSEEN:
        return
    if len(_V2_LEFT_UNSEEN) > 256:
        _V2_LEFT_UNSEEN.clear()
    _V2_LEFT_UNSEEN.add(ident)
    log(f"version 2 question {ident}: this process is "
        f"not an answerer; left unseen")

_V2_LEFT_UNSEEN = set()

def _v2_hand_off(cfg, smtp, base_dir, subject, body, target):
    """Put one version 2 message on the pipe before the wait.

    A transport captures sends and writes the channel only
    after the job returns. That is too late: the answer
    would miss the deadline. Those messages are written to
    the channel now and are not captured, so they are not
    written a second time. A live SMTP, including the test
    double, is sent immediately.

    Returns the outbox paths still waiting for an extension
    to send. An empty list means the message is already on
    the wire.
    """
    paths = []
    if isinstance(smtp, _CaptureSMTP) and _transports is not None:
        try:
            names = _enabled_transports(cfg)
        except Exception as e:
            log(f"version 2 hand-off skipped: {e}", "WARN")
            names = []
        wrote = False
        for name in names:
            try:
                hint = subject.rsplit(" ", 1)[-1]
                path = _transports.write_channel_result(
                    base_dir, name, subject, subject, body,
                    ident_hint=hint, target=target)
                if path:
                    paths.append(path)
                wrote = True
            except Exception as e:
                log(f"version 2 hand-off to {name} failed: {e}",
                    "WARN")
        if wrote:
            return paths
    send_mail(smtp, cfg, subject, body, to=target)
    return []


def _v2_before_execute(cfg, job, op_plan, secret, key_id, encrypted,
                       base_dir, send, pump=None):
    """Send a determination and, on Pi Light, a question.

    ``send`` hands a message to the pipe. ``pump`` files any
    answer that arrives before the deadline. The returned
    segments ride the version 1 result. They do not change
    what runs.
    """
    if _protocol_v2 is None:
        return []
    outbound = _protocol_v2.outbound_for(cfg, job, op_plan)
    segments = []
    question = None
    question_paths = []
    for subj, obj in outbound:
        sent_paths = send(subj, _seal_reply(
            obj, secret, obj["msg_id"], key_id, encrypted))
        if obj.get("type") == "determination":
            segments.append(_protocol_v2.segment(
                "runner", "determination", obj.get("why") or ""))
        elif obj.get("type") == "question":
            question = obj
            if isinstance(sent_paths, (list, tuple)):
                question_paths.extend(
                    p for p in sent_paths if isinstance(p, str) and p)
    if question is not None:
        def still_out(paths=tuple(question_paths)):
            return any(os.path.exists(p) for p in paths)

        segments.extend(_protocol_v2.await_answer(
            base_dir, question, time.time(), pump=pump,
            pending=still_out if question_paths else None))
    return segments

def _auth_reject_event(base_dir, reason, **extra):
    """Record one auth_rejection in security-events.jsonl."""
    event = {
        "type": "auth_rejection",
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reason": reason,
    }
    event.update(extra)
    _append_security_event(base_dir, event)


def _close_quiet(fd):
    """Close fd, swallowing OSError."""
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass


def _unlink_quiet(path):
    """Unlink path, swallowing OSError."""
    try:
        os.unlink(path)
    except OSError:
        pass


def _chmod_quiet(path, mode=0o600):
    """chmod, swallowing OSError."""
    try:
        os.chmod(path, mode)
    except OSError:
        pass

def _verify_and_decrypt(msg, secrets, job_id):
    """Verify and decrypt a job mail.

    Returns (job, key_id, secret, was_encrypted) or raises
    ValueError / JobCryptoError. The caller rejects and records
    the auth_rejection event.
    """
    job, key_id = verify_body_keyed(get_text_body(msg), secrets)
    secret = secret_named(secrets, key_id)
    was_encrypted = False
    if isinstance(job, dict) and isinstance(job.get("hp_enc"), dict):
        if _jobcrypto is None or not _jobcrypto.is_envelope(job):
            raise ValueError("malformed encryption envelope")
        inner_text = _jobcrypto.decrypt_body(
            job, secret, job_id=job_id, key_id=key_id)
        job, inner_key_id = verify_body_keyed(inner_text, secrets)
        if inner_key_id != key_id:
            raise ValueError(
                "encrypted envelope key_id does not match its body")
        secret = secret_named(secrets, key_id)
        was_encrypted = True
    if not isinstance(job, dict):
        raise ValueError("job body must be a JSON object")
    return job, key_id, secret, was_encrypted

_BOUNCE_SUBJECTS = ("undeliverable", "mail delivery failed",
                    "delivery status notification", "returned mail",
                    "undelivered mail returned to sender",
                    "delivery failure", "failure notice")

def _bounce_of(subject, raw):
    """What a delivery status notification refers to ("result <id>",
    "job <id>", or "a message"), or None when the mail is not one.
    A DSN is a multipart/report (report-type delivery-status) message,
    or one whose subject opens the way providers open theirs."""
    text = _as_str(subject).strip().lower()
    is_dsn = any(text.startswith(p) for p in _BOUNCE_SUBJECTS)
    if not is_dsn and isinstance(raw, (bytes, bytearray)):
        try:
            msg = email.message_from_bytes(bytes(raw))
            is_dsn = msg.get_content_type() == "multipart/report" and \
                "delivery-status" in str(msg.get_param("report-type") or "")
        except Exception:
            is_dsn = False
    if not is_dsn:
        return None
    m = _SUBJECT_KIND_RE.search(_as_str(subject))
    return "%s %s" % (m.group(1).lower(), m.group(2)) if m else "a message"

def _early_dispatch(cfg, imap, smtp, seq, raw, subject, secrets, opts,
                    base_dir, seen):
    """Handle non-job mail and already-seen jobs.

    Returns (job_id, skey) when the message is a new job to
    execute, or None when the message was handled and the
    caller should return.
    """
    if _cancel.handle_cancel_mail(cfg, imap, smtp, seq, raw, subject,
                                  secrets, opts, base_dir, seen):
        return None
    if handle_query_mail(cfg, imap, smtp, seq, raw, subject, secrets,
                         opts, base_dir, seen):
        return None
    if "board" in cfg and cfg["board"] is not None:
        if handle_board_mail(cfg, imap, smtp, seq, raw, subject,
                             cfg["board"], secrets, opts, base_dir):
            return None
    if handle_v2_mail(cfg, imap, smtp, seq, raw, subject, secrets, opts,
                      base_dir, seen):
        return None
    bounce = _bounce_of(subject, raw)
    if bounce is not None:
        # A delivery status notification about one of this runner's
        # own messages (review item 4): the provider refused a result
        # after the send was accepted. Said once, marked seen, never
        # parsed as a job -- the quoted original inside it is not a
        # submission.
        log(f"bounce: the mail server returned {bounce}; its result "
            f"was refused after the send (see --inspect outbox)")
        _mark(imap, seq, opts)
        return None
    m = _subject.JOB_ID_RE.search(subject)
    if not m:
        vlog(f"ingest: seq {seq}: skipped; not a job message")
        _mark(imap, seq, opts)
        return None
    if _protocol_v2 is not None and _protocol_v2.answer_only(cfg):
        log(f"answer-only: not executing job {m.group(1)}")
        _mark(imap, seq, opts)
        return None
    job_id = m.group(1)
    skey = _seen_key(cfg, job_id)
    if skey in seen:
        vlog(f"ingest: seq {seq} job {job_id}: skipped; already seen")
        _mark(imap, seq, opts)
        return None
    return job_id, skey

_mail = _required_load_mod("runner.ops.mail", "ops.mail")
handle_mail = _mail.handle_mail


# ---------------------------------------------------------------- main
def _validate_size_caps(cfg):
    """Return an error string for a bad size cap, or None.

    Hardening M1b: max_job_bytes and max_script_bytes must be
    non-negative integers. 0 means unlimited. A missing key is fine.
    """
    if not isinstance(cfg, dict):
        return None
    for key in ("max_job_bytes", "max_script_bytes", "max_result_bytes"):
        cap = cfg.get(key)
        if cap is None:
            continue
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
            return ("%s must be a non-negative integer (got %r)"
                    % (key, cap))
    if _platformcard is not None and "pong_platform" in cfg:
        _tier, problem = _platformcard.tier_of(cfg, "pong_platform")
        if problem:
            return problem
    if _extreview is not None and _extreview.CONFIG_KEY in cfg:
        _mode, problem = _extreview.mode_of(cfg)
        if problem:
            return problem
    problem = _recipes.validate_recipes(cfg) or _changes.validate_repos(cfg)
    if problem:
        return problem
    return None

def load_config(path: str) -> dict:
    """Load a config object. A symlink is not followed."""
    if isinstance(path, str) and path and os.path.islink(path):
        raise RuntimeError("config error: refusing to follow a symlink")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise RuntimeError("config error: config file must be a JSON object")
    return data

_SEEN_FILE_GUARD = threading.RLock()
_CLAIM_STALE_SEC = 86400

def _pid_alive(pid):
    """True when pid is still a process. A dead claim can be taken."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            access = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION
            handle = ctypes.windll.kernel32.OpenProcess(access, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            # 5 is access denied: the process is there.
            return ctypes.windll.kernel32.GetLastError() == 5
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True

def _claim_path(base_dir, skey):
    folder = os.path.join(base_dir, "inflight")
    name = hashlib.sha256(str(skey).encode("utf-8")).hexdigest()
    return folder, os.path.join(folder, name)

def _with_seen_file(path, mutator):
    """Read-modify-write seen.json under a lock other processes see.

    mutator(disk_dict) returns the dict to write. The lock is a
    file lock plus an in-process one, so two runners on the same
    state directory cannot both believe they own a job id.
    """
    if not isinstance(path, str) or not path:
        return {}
    with _SEEN_FILE_GUARD:
        fd = None
        kind = None
        try:
            flags = os.O_CREAT | os.O_RDWR
            fd = os.open(path + ".lock", flags, 0o600)
            try:
                os.lseek(fd, 0, os.SEEK_END)
                if os.lseek(fd, 0, os.SEEK_CUR) == 0:
                    os.write(fd, b"\0")
                os.lseek(fd, 0, os.SEEK_SET)
            except OSError:
                pass
            # fcntl where the platform has it. A Linux test that
            # pretends os.name is "nt" still has fcntl; importing
            # msvcrt there raises and used to fail the poll.
            try:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
                kind = "fcntl"
            except ImportError:
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                kind = "msvcrt"
            disk = load_seen(path, stamped=True)
            updated = mutator(disk if isinstance(disk, dict) else {})
            if not isinstance(updated, dict):
                updated = disk
            kept = _write_seen_kept(path, updated)
            # Callers see the keys, as before; the times stay on disk.
            return {k: True for k in kept}
        except OSError:
            return load_seen(path) if isinstance(path, str) else {}
        finally:
            if fd is not None:
                try:
                    if kind == "msvcrt":
                        import msvcrt
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    elif kind == "fcntl":
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except (OSError, ImportError):
                    pass
                _close_quiet(fd)

# How long a replay-cache entry is kept, in seconds (Q102). Set from
# the config by save_seen's callers; the claim writers that share the
# file use the last value set.
SEEN_KEEP_FLOOR = 86400
_SEEN_KEEP = [SEEN_KEEP_FLOOR]


def seen_keep_sec(cfg):
    """The age past which a replay-cache entry can never match a
    message the door would take: the freshness window plus the
    300-second future bound, and a day at least."""
    window = _confval.integer((cfg or {}).get("max_job_age_sec")
                              if isinstance(cfg, dict) else None,
                              3600, lo=1)
    return max(window + 300, SEEN_KEEP_FLOOR)


def _seen_stamp(value):
    """The time a cache entry was recorded, or None when it carries
    none (a bare True from an older release or from memory)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    # A plausible epoch time only; a small number is a flag, not a time.
    return float(value) if value > 1_000_000_000 else None


def _write_seen_unlocked(path, seen, now=None):
    """Write the cache as {key: recorded_at} (see _write_seen_kept)."""
    _write_seen_kept(path, seen, now)


def _write_seen_kept(path, seen, now=None):
    """Write the cache as {key: recorded_at}. An entry older than the
    keep horizon is dropped; one with no time is stamped now. Returns
    what was written."""
    now = time.time() if now is None else now
    keep = _SEEN_KEEP[0]
    kept = {}
    for key, value in list(seen.items()):
        try:
            text = key if isinstance(key, str) else str(key)
        except Exception:
            continue
        if "\x00" in text:
            continue
        stamp = _seen_stamp(value)
        if stamp is None:
            stamp = now
        if now - stamp > keep:
            continue
        kept[text] = stamp
    if len(kept) > SEEN_CAP:
        log(f"replay cache holds {len(kept)} entries inside the freshness "
            f"window, over the {SEEN_CAP} ceiling; the oldest are dropped",
            "WARN")
        newest = sorted(kept.items(), key=lambda kv: kv[1])[-SEEN_CAP:]
        kept = dict(newest)
    try:
        _atomicio.write_json(path, kept)
    except (OSError, TypeError, ValueError):
        pass
    return kept


def _disk_release(base_dir, skey):
    """Drop this process's claim without recording the job as seen.

    Only the claim whose pid is ours is removed, and only under
    the same file lock as the claim. An unlocked unlink can
    delete a claim a second process just stole.
    """
    if not _valid_base(base_dir):
        return
    seen_path = os.path.join(base_dir, "seen.json")
    _folder, claim = _claim_path(base_dir, skey)

    def mutate(disk):
        try:
            with open(claim, encoding="utf-8") as fh:
                pid = int(fh.readline().strip() or "0")
        except (OSError, ValueError):
            return disk
        if pid != os.getpid():
            return disk
        _unlink_quiet(claim)
        return disk

    _with_seen_file(seen_path, mutate)

def _release_saved_claims(seen_path, seen):
    folder = os.path.join(os.path.dirname(seen_path), "inflight")
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        key = lines[2] if len(lines) > 2 else ""
        if key and isinstance(seen, dict) and seen.get(key):
            _unlink_quiet(path)

def load_seen(path: str, stamped=False) -> dict:
    """Replay cache. A symlink is not followed.

    A missing or unreadable file is an empty cache. Never raises.
    """
    try:
        if not isinstance(path, str) or not path or os.path.islink(path):
            return {}
        # The in-process guard the writer holds (Q124): a reader in
        # another thread no longer has the file open while the
        # writer renames over it. The RLock lets the writer's own
        # read inside _with_seen_file pass. The file lock is the
        # writer's alone; a second process reading is the rename
        # retry's to ride out.
        with _SEEN_FILE_GUARD:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        if isinstance(data, list):
            return {str(x): True for x in data}
        if isinstance(data, dict):
            if stamped:
                # The time each entry was recorded (Q102); an entry
                # without one reads as a bare True.
                return {str(k): (_seen_stamp(v) or True)
                        for k, v in data.items()}
            return {str(k): True for k in data}
        return {}
    except Exception:
        return {}

def save_seen(path: str, seen: dict, keep_sec=None):
    """Write the replay cache, merged with whatever is already there.

    Two runners used to each replace the file with only the keys
    they held in memory, so one wiped the other's. The merge is
    under the same lock as the claim. An entry keeps the time it was
    first recorded, and one older than keep_sec (seen_keep_sec(cfg))
    leaves both the file and this process's copy (Q102).
    """
    if not isinstance(path, str) or not path:
        return
    if not isinstance(seen, dict):
        seen = {}
    if isinstance(keep_sec, (int, float)) and not isinstance(keep_sec, bool) \
            and keep_sec > 0:
        _SEEN_KEEP[0] = max(int(keep_sec), 1)

    def merge(disk):
        if not isinstance(disk, dict):
            disk = {}
        for key, value in seen.items():
            if _seen_stamp(disk.get(key)) is None:
                disk[key] = value
        return disk

    written = _with_seen_file(path, merge)
    if isinstance(written, dict) and written:
        for key in [k for k in seen if k not in written]:
            seen.pop(key, None)
        for key in written:
            seen[key] = True
    _release_saved_claims(path, seen)


class DrainPlan:
    """The life of an ephemeral runner: poll until `jobs` have run or
    `seconds` have passed, whichever comes first. Progress is read
    from the seen-set's growth (one entry per job that ran and whose
    result was sent), so no transport has to report a count."""

    def __init__(self, jobs, seconds, start_seen=0, clock=None):
        self.jobs = max(0, int(jobs or 0))
        self.seconds = max(0, int(seconds or 0))
        self.start_seen = int(start_seen or 0)
        self._clock = clock or time.monotonic
        self.t0 = self._clock()

    def done_jobs(self, seen_size):
        return max(0, int(seen_size) - self.start_seen)

    def more(self, seen_size) -> bool:
        """True while another poll cycle is wanted."""
        if self.jobs and self.done_jobs(seen_size) >= self.jobs:
            return False
        if self.seconds and self._clock() - self.t0 >= self.seconds:
            return False
        return True


def drain_plan(args, seen_size=0):
    """A DrainPlan for --once --drain, or None for a plain --once.

    Unusable values (negative, non-numeric) read as off, Decision 1.
    """
    jobs = _confval.integer(getattr(args, "drain", 0), 0, lo=0) \
        if _confval is not None else 0
    seconds = _confval.integer(getattr(args, "drain_seconds", 0), 0, lo=0) \
        if _confval is not None else 0
    if not getattr(args, "once", False) or (not jobs and not seconds):
        return None
    return DrainPlan(jobs, seconds, seen_size)


HOT_KEYS = ("poll_interval_sec", "workers", "default_timeout_sec",
            "max_output_bytes", "max_job_age_sec",
            "result_stash_retention_sec", "result_resend_backoff_sec")
# The documented default each hot key reads as when a live write is
# not usable (Decision 1, live reload: the default, named in the log,
# no hidden last-good state). workers is 1 unset (_worker_count).
HOT_DEFAULTS = {"poll_interval_sec": 20, "workers": 1,
                "default_timeout_sec": 300, "max_output_bytes": 100000,
                "max_job_age_sec": 3600,
                "result_stash_retention_sec": 86400,
                "result_resend_backoff_sec": 60}
# Strings and objects the Oracle reads live. Not integers, so they do not
# go through _valid_hot. Credentials stay out of this list.
LIVE_KEYS = ("owner_instructions", "inference", "oracle_mode", "verbose",
             "extension_sources")

def _valid_hot(key: str, value):
    """Return the int to store, or None if the value must be rejected."""
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if n < 1:
        return None
    return n


def _worker_count(cfg, opts) -> int:
    """Concurrent job executions. CLI overrides config; default 1."""
    if not isinstance(cfg, dict):
        cfg = {}
    raw = None
    if opts is not None and getattr(opts, "workers", None) is not None:
        raw = opts.workers
    elif cfg.get("workers") is not None:
        raw = cfg.get("workers")
    if raw is None:
        return 1
    try:
        n = int(raw)
    except (TypeError, ValueError, OverflowError):
        return 1
    # A million workers is a config typo, not a thread pool.
    return max(1, min(n, 32))

# --- one-process CLI overrides ----------------------------------------------
#
# Every flag in this table replaces one config value for this
# process only. config.json is never rewritten, and main() pins
# the applied keys so a hot reload of config.json cannot undo a
# flag mid-run. The families mirror the config file's own shape:
# polling and timeouts, freshness and retention, query budgets,
# modes, local signals, and the log bounds.

_tables = _required_load_mod("runner.ops.tables", "ops.tables")
_CLI_OVERRIDES = _tables._CLI_OVERRIDES
_YARA_RULES = _tables._YARA_RULES


# Dests whose value must be a non-negative whole number. The
# readers clamp most of these anyway; rejecting a negative here
# keeps a typo on the command line from becoming a silent edit.
_CLI_OVERRIDE_COUNTS = frozenset(
    dest for dest, _key in _CLI_OVERRIDES
    if dest not in ("max_result_view", "judge", "dag_mode",
                    "oracle_mode", "oracle_opinion",
                    "protocol_v2", "answer_only",
                    "remediation_mode", "require_review",
                    "local_signals", "oracle_log", "transports"))

def _enabled_transports(cfg):
    """Validated transport names for this config (runner-side
    wrapper so a missing transports module degrades to a clear
    error instead of a NameError at poll time)."""
    if _transports is not None:
        return _transports.enabled_transports(cfg)
    raw = cfg.get("transports") if isinstance(cfg, dict) else None
    if raw is None or raw == ["email"] or raw == "email":
        return ["email"]
    raise ValueError("transports module unavailable; only the "
                     "email transport can run")

def apply_cli_overrides(cfg, args) -> list:
    """Apply the one-process CLI overrides to cfg, in place.

    Returns the config keys that were set (main() pins them).
    Raises ValueError on a value that cannot mean anything, so a
    bad flag is a startup error, not a surprise at poll time.
    """
    applied = []
    if not isinstance(cfg, dict):
        return applied
    for dest, key in _CLI_OVERRIDES:
        val = getattr(args, dest, None)
        if val is None:
            continue
        if dest in _CLI_OVERRIDE_COUNTS:
            if not isinstance(val, int) or isinstance(val, bool) \
                    or val < 0:
                raise ValueError(
                    f"--{dest.replace('_', '-')} must be a whole "
                    f"number >= 0 (got {val!r})")
            if dest == "local_signal_port" and val > 65535:
                raise ValueError(
                    "--local-signal-port must be <= 65535 "
                    f"(got {val})")
        cfg[key] = val
        applied.append(key)
    return applied

# Env vars the runner itself uses for credentials. Never leak these into
# job subprocesses: a job can print its environment, and job output goes
# back to the SI.
_SENSITIVE_ENV_PREFIXES = ("PIGEON_",)

def _scrub_env(env: dict) -> dict:
    """Remove the runner's own credential vars from a job's environment.

    Windows env keys are case-insensitive, so pigeon_secret is the
    same variable as PIGEON_SECRET. Match the prefix either way.
    """
    if not isinstance(env, dict):
        return {}
    prefixes = tuple(p.lower() for p in _SENSITIVE_ENV_PREFIXES)
    out = {}
    for k, v in env.items():
        try:
            key = k if isinstance(k, str) else str(k)
        except Exception:
            continue
        if key.lower().startswith(prefixes):
            continue
        out[key] = v
    return out

class _NullIMAP:
    """Stand-in for the mail path's mark_seen calls: a transported
    message has no mailbox flags to set. ``marked`` records that
    the core would have marked the mail seen, which is the signal
    to consume the channel envelope. A retryable failure never
    calls store, so the envelope stays in the inbox."""

    def __init__(self):
        self.marked = False

    def store(self, *args):
        self.marked = True
        return ("OK", [])

class _Outbound(list):
    """Replies from one transported envelope.

    ``consume`` is false when the core left the message unseen.
    ``requeue`` puts the results this attempt stashed back in the
    outbox, so a reply that never reached the channel outbox is
    resent by the next cycle's resend pass; the job itself is not
    run again. ``rollback`` is the channel's call when its ack fails
    after the replies landed: nothing to undo then -- the result is
    in the channel outbox and a re-read of the envelope is a replay
    the seen-set answers -- so it only says so.
    """

    def __init__(self, items, consume, requeue, rollback):
        super().__init__(items)
        self.consume = consume
        self.requeue = requeue
        self.rollback = rollback

class _CaptureSMTP:
    """Stand-in collecting what send_mail would have sent, so a
    transport can carry the results out its own pipe. The To of
    each send is kept alongside the (subject, body): send_mail
    was handed the job's validated reply_to (or nothing), so the
    header is the one place the core's routing decision survives
    into the channel -- a pipe cannot recover it from an
    encrypted job, and never holds the secret to try."""

    def __init__(self, transport=None):
        self.sent = []
        self.targets = []
        self.transport = transport   # the channel the job came through

    def send_message(self, msg):
        body = ""
        try:
            body = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode("utf-8", errors="replace")
        self.sent.append((str(msg["Subject"] or ""), body))
        self.targets.append(str(msg["To"] or ""))

def process_transport_message(cfg, base_dir, seen, secrets,
                              key_policies, subject, body_text,
                              opts=None, transport=None):
    """Run one transported envelope through the mail core.

    The envelope becomes a synthetic RFC822 message and handle_mail
    does everything it does for real mail -- query and board
    dispatch, the signature gate, execution, the result -- with a
    null IMAP and a capturing SMTP standing in for the mailbox.
    Returns the (subject, body, target) messages the core sent:
    target is the job's validated reply_to when the send carried
    one, else None (the send went to the runner's own mailbox,
    which is the channel's default destination anyway). The
    list's ``consume`` flag is false when the core did not mark
    the message seen. The channel must leave that envelope in
    the inbox. ``requeue`` puts the results stashed during this
    attempt back for the resend pass (the job stays seen);
    ``rollback`` is the ack-failure call, which has nothing left
    to undo.
    """
    cap = _CaptureSMTP(transport=transport)
    imap = _NullIMAP()
    before = set(seen) if isinstance(seen, dict) else None
    safe_subject = str(subject).replace("\r", " ").replace("\n", " ")
    raw = ("Subject: " + safe_subject + "\r\n"
           "From: transport\r\n"
           'Content-Type: text/plain; charset="utf-8"\r\n'
           "\r\n" + str(body_text)).encode("utf-8")
    handle_mail(cfg, imap, cap, "transport", raw, base_dir,
                seen, secrets, opts, key_policies)
    mailbox_addr = str(cfg.get("mailbox_user") or "")
    out = []
    for (sent_subject, sent_body), raw_to in zip(cap.sent,
                                                 cap.targets):
        # send_mail's To is the validated reply_to when the job
        # named one and the mailbox itself otherwise; only the
        # former is a routing decision worth handing the pipe.
        target = raw_to if raw_to and raw_to != mailbox_addr \
            else None
        out.append((sent_subject, sent_body, target))
    added = []
    if before is not None:
        added = [key for key in list(seen) if key not in before]

    def requeue(added=list(added)):
        # The job executed and its result is stashed; what did not
        # happen is the drop into the channel outbox. The job stays
        # seen (a copy of the envelope is a replay), and the record
        # goes back to the outbox for the resend pass, which writes
        # it to this transport's channel on the next cycle.
        for key in added:
            undeliver_stash(base_dir, key, "channel outbox write failed")

    def rollback(added=list(added)):
        for key in added:
            log(f"transport ack failed after the result landed; the job "
                f"stays seen and its envelope is a replay next cycle "
                f"({key})", "WARN")

    dry = opts is not None and getattr(opts, "dry_run", False)
    return _Outbound(out, bool(imap.marked) and not dry, requeue, rollback)

def _service_transports(cfg, base_dir, seen, seen_path, names,
                        secrets, key_policies, opts):
    """One cycle for each enabled transport extension's channel,
    in config order. The core is transport-blind: it reads job
    envelopes from each extension's channel inbox, runs them
    through the mail core, and drops the result envelopes in the
    extension's channel outbox. A channel that fails its cycle
    is logged plainly and retried next cycle; one bad pipe never
    fails the others. Dry-run changes nothing: a channel job
    stays in the inbox, exactly as mail stays unseen."""
    dry_run = opts is not None and getattr(opts, "dry_run", False)

    for name in names:
        def process(subject, body_text, name=name):
            return process_transport_message(
                cfg, base_dir, seen, secrets, key_policies,
                subject, body_text, opts, transport=name)

        try:
            count = _transports.service_channel(
                base_dir, name, process, log=log, dry_run=dry_run)
            vlog(f"transports: {name}: {count} message(s)")
        except Exception as e:
            log(f"{name} transport: channel service failed: {e} "
                f"(will retry next cycle)", "WARN")
    # The resend pass: a channel result that never reached its outbox
    # goes back out that channel; a mailbox record waits for a cycle
    # that has a mailbox.
    if not dry_run:
        resend_stashed(base_dir, cfg, None)
        _sweep_channel_refusals(base_dir, cfg, names)
    save_seen(seen_path, seen, keep_sec=seen_keep_sec(cfg))

_poll = _required_load_mod("runner.ops.poll", "ops.poll")
poll_once = _poll.poll_once


def update_llama_from_config(cfg, previous=None):
    """When config changes, keep the local model in sync.

    If the inference model id changed, pull it. Always ensure the
    daemon is up when inference is configured. Owner instructions are
    read live from cfg on the next ask, so a string edit needs no
    extra step here.
    """
    inf = inference_config(cfg)
    if not inf:
        return
    ensure_inference_ready(cfg)
    model = inf.get("model") or ""
    prev_model = ""
    if previous:
        prev = inference_config(previous) or {}
        prev_model = prev.get("model") or ""
    if model and model != prev_model:
        import shutil
        import subprocess
        if shutil.which("ollama"):
            log(f"inference: pulling model {model}")
            try:
                subprocess.run(["ollama", "pull", model], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log(f"inference: model {model} updated")
            except Exception as e:
                log(f"inference: model pull failed: {e}", "WARN")

def daemon_popen_kwargs(windows: bool) -> dict:
    """Popen kwargs for a helper that must outlive this process.

    start_new_session is POSIX-only. On Windows it raises ValueError
    before the process is created.
    """
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if windows:
        detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        kw["creationflags"] = detached | group
    else:
        kw["start_new_session"] = True
    return kw

def _spawn_daemon(argv, log_path=None):
    kw = daemon_popen_kwargs(os.name == "nt")
    fh = None
    if log_path:
        try:
            fh = open(log_path, "ab")
            kw["stdout"] = fh
            kw["stderr"] = fh
        except OSError:
            fh = None
    try:
        return subprocess.Popen(argv, **kw)
    finally:
        # The child holds its own dup of the fd; the parent's copy
        # can close as soon as the process exists.
        if fh is not None:
            fh.close()

def ensure_inference_ready(cfg):
    """If inference is configured, make sure the loopback daemon is up.

    Dials the host and port from the endpoint, including ::1 and a
    non-default port. A daemon that is already listening is left alone.
    """
    inf = inference_config(cfg)
    if not inf:
        return
    parsed = urlparse(inf["endpoint"])
    host = parsed.hostname
    if not host:
        return
    port = parsed.port or 11434
    try:
        socket.create_connection((host, port), timeout=1).close()
        return
    except Exception:
        pass
    import shutil
    if not shutil.which("ollama"):
        log("inference configured but ollama not found", "WARN")
        return
    # With oracle_log on, the daemon's own output goes to oracle.log
    # too (it is part of the Oracle's story); otherwise it stays
    # discarded, exactly as before.
    daemon_log = _ORACLE_LOG_PATH if _ORACLE_LOG_ENABLED else None
    if daemon_log is None and _cfg_flag(cfg.get("oracle_log")):
        daemon_log = os.path.join(_base_dir_for(cfg), "oracle.log")
    try:
        _spawn_daemon(["ollama", "serve"], log_path=daemon_log)
        log("started ollama daemon for inference")
    except Exception as e:
        log(f"could not start ollama: {e}", "WARN")

def _base_dir_for(cfg, cfg_path=None) -> str:
    """State directory for this config.

    An explicit base_dir wins. Otherwise the state lives next to the
    config file, so the same config always resolves to the same state
    no matter which user (or service account) runs it. The historic
    ~/.homing-pigeon default is kept only when no config path is known.
    """
    if isinstance(cfg, dict):
        bd = cfg.get("base_dir")
        if isinstance(bd, str) and bd.strip():
            return bd
    if cfg_path:
        return os.path.dirname(os.path.abspath(cfg_path))
    return os.path.join(os.path.expanduser("~"), ".homing-pigeon")

def run_inspect(cfg, args) -> int:
    """Read local Oracle state. No mailbox, no network, no secrets printed."""
    base = _base_dir_for(cfg, getattr(args, "config", None))
    if args.inspect == "board":
        board = Board(os.path.join(base, "board.json"))
        print(json.dumps({"counts": board.counts(),
                          "tasks": list(board.tasks.values())}, indent=2))
        return 0
    if args.inspect == "outbox":
        # Results executed but not yet delivered, and the ones given
        # up on: job id, age, attempts, last error (review item 1).
        print(json.dumps(outbox_report(base), indent=2))
        return 0
    if args.inspect == "budget":
        path = os.path.join(base, "query_times.json")
        limit = _query_limit(cfg)
        print(json.dumps({"max_queries_per_hour": None if limit < 0 else limit,
                          "keys": budget_status(path, cfg)}, indent=2))
        return 0
    if args.inspect == "sources":
        if _extsources is None:
            print("extension sources: runner/ops/extsources.py is unavailable",
                  file=sys.stderr)
            return 1
        print(json.dumps(_extsources.status(base), indent=2))
        return 0
    if args.inspect == "review":
        if _extreview is None:
            print("extension review: runner/guard/extreview.py is unavailable",
                  file=sys.stderr)
            return 1
        print(json.dumps(_extension_review_now(cfg, base), indent=2))
        return 0
    if args.inspect == "job":
        if not args.job_id:
            print("error: --job-id is required", file=sys.stderr)
            return 2
        data = load_retained(base, args.job_id)
        if not data:
            print("not found", file=sys.stderr)
            return 1
        # patterns are regexes the owner wrote; fine to show. never secrets.
        print(json.dumps(data, indent=2, default=str))
        return 0
    text = sys.stdin.read()
    patterns = _redact_patterns(cfg)
    redacted, families = redact_text(text, patterns)
    print(json.dumps({"families": families, "redacted": redacted}, indent=2))
    return 0

# Keys a fuzz variant may carry into execute_job. Everything
# else in the variant file -- signature material, files,
# script_url, delivery fields -- is dropped here, so a variant
# can never fetch, sign, or send: it is a local script body and
# its shape, nothing more.
_VARIANT_KEYS = ("job_id", "kind", "script", "interpreter",
                 "args", "env", "timeout_sec")
_VARIANT_TIMEOUT_CAP_SEC = 120


def _invocation_line(argv=None) -> str:
    """This process's command line, shell-quoted for copy-paste.

    The runner's argv carries no secrets by design -- the shared
    secret lives in config.json, never in a flag -- so the exact
    invocation is safe to log verbatim, and for a one-liner
    workflow the command that produced a run belongs in its log.
    """
    argv = list(sys.argv if argv is None else argv)
    if not argv:
        return "(unknown invocation)"
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def _is_loopback_ip(host: str) -> bool:
    host = (host or "").split("%", 1)[0].strip("[]")
    if host.lower().startswith("::ffff:"):
        host = host[7:]
    try:
        return bool(ipaddress.ip_address(host).is_loopback)
    except ValueError:
        return False

_REPLY_PREVIEW = re.compile(r"ask: reply '.*'$")
_JOB_FINISHED = re.compile(r"job (\S+) process finished exit=")
_STDOUT_PREVIEW = re.compile(r"stdout='.*'$")
_FULL_OUTPUT_HEAD = re.compile(r"job (\S+) \(kind=.*\) full output:$")


def _flagged_retained(base_dir, limit):
    """(job_id, record) for the newest retained jobs whose script names
    a protected path: the records both withholding channels read.
    Unreadable or shapeless records are skipped."""
    for _mtime, path, job_id in _chosen_retained_rows(base_dir, limit):
        data = _read_json_dict(path)
        if data is None:
            continue
        script = data.get("script") if isinstance(
            data.get("script"), str) else ""
        if script.strip() and _script_path_findings(script, base_dir, job_id):
            yield job_id, data
def _flagged_job_ids(base_dir):
    """Job ids whose retained records carry script-path findings.

    The log tail uses the set to keep a flagged job's logged
    output out of the Oracle's context, the same withholding the
    retained summary applies. A job whose record is gone cannot
    be classified here; retention governs both channels alike.
    """
    ids = set()
    # The tail window is the last 30 lines; a job whose logged
    # output can sit in it is among the newest retained records
    # by a wide margin. 25 is that margin.
    for job_id, _data in _flagged_retained(base_dir, 25):
        ids.add(job_id)
    return ids

_watch = _required_load_mod("runner.ops.watch", "ops.watch")
_eventlog_tail = _watch._eventlog_tail
_registry_watch = _watch._registry_watch
_host_log_tail = _watch._host_log_tail
_scrub_log_tail_lines = _watch._scrub_log_tail_lines


def _runner_log_tail(base_dir, max_chars=2000) -> str:
    """Last lines of the runner log, for the Oracle's context.

    The chat process cannot see the console, and the model must not
    invent log events. Giving it the real tail lets it answer "did
    this happen?" honestly. Bounded; a missing log yields "".
    Quoted reply previews and flagged jobs' logged output are
    scrubbed first (see _scrub_log_tail_lines); the log file
    itself is never altered.
    """
    if not _valid_base(base_dir):
        return ""
    path = os.path.join(base_dir, "runner.log")
    if os.path.islink(path):
        return ""
    if isinstance(max_chars, bool):
        max_chars = 2000
    else:
        try:
            max_chars = int(max_chars)
        except (TypeError, ValueError, OverflowError):
            max_chars = 2000
    if max_chars < 0:
        max_chars = 0
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    if size <= 0:
        return ""
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, size - 4096))
            raw = fh.read()
    except OSError:
        return ""
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if size > 4096 and lines:
        lines = lines[1:]  # partial first line from the seek
    lines = _scrub_log_tail_lines(lines, base_dir)
    tail = "\n".join(lines[-30:]).strip()
    if max_chars < 1:
        return ""
    if len(tail) > max_chars:
        tail = tail[-max_chars:]
    return tail

_EVENTLOG_LEVELS = {0: "LogAlways", 1: "Critical", 2: "Error",
                    3: "Warning", 4: "Info", 5: "Verbose"}

# Security-log event IDs worth surfacing to the Oracle. Small on purpose:
# failed logons, privilege assignment, explicit-credential use, account
# creation, and the audit log being cleared.
_EVENTLOG_AUDIT_IDS = (4625, 4672, 4648, 4720, 1102)
# Audit event to ATT&CK. Only these ids are tagged. A service crash
# is not an attack technique, and inventing one would be the failure
# the watch is supposed to avoid.
_EVENTLOG_ATTACK = {
    4625: "T1110",       # brute force
    4672: "T1078",       # valid accounts, special privileges
    4648: "T1078",       # explicit credentials
    4720: "T1136",       # create account
    1102: "T1070.002",   # clear the audit log
}

_windows = _required_load_mod("runner.ops.windows", "ops.windows")
_wevtutil_query = _windows._wevtutil_query
_reg_attack = _windows._reg_attack
_reg_query = _windows._reg_query


# Registry locations the Oracle watches, read-only. Autorun and
# persistence first: that is what "watch the registry" means on a
# Windows box. Winlogon is bounded to its interesting values below.
_REG_WATCH_KEYS = (
    r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
    r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
    r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
    r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
    r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon",
)
_REG_WATCH_WINLOGON_KEEP = {
    "shell", "userinit", "taskman", "ginadll", "system", "vmApplet",
}
_REG_WATCH_MAX_VALUES = 12
_REG_WATCH_MAX_CHANGES = 15


def _registry_snapshot():
    """Current watch state, or None if the registry cannot be read.

    {key: {name: data_hash}}, plus the service list count and hash.
    The Services key is the canary: it always exists on Windows, so if
    it cannot be read, reg.exe itself is unavailable.
    """
    svc = _reg_query(r"HKLM\SYSTEM\CurrentControlSet\Services")
    if svc is None:
        return None
    snap = {"keys": {}, "services": {"count": 0, "hash": ""}}
    for key in _REG_WATCH_KEYS:
        res = _reg_query(key)
        values = res[0] if res is not None else {}
        if "Winlogon" in key:
            values = {n: v for n, v in values.items()
                      if n.lower() in _REG_WATCH_WINLOGON_KEEP}
        kept = dict(list(values.items())[:_REG_WATCH_MAX_VALUES])
        snap["keys"][key] = {
            n: hashlib.sha1(v.encode("utf-8", "replace")).hexdigest()[:12]
            for n, v in kept.items()
        }
        snap["keys"][key + "\x00raw"] = kept
    names = sorted(svc[1])
    snap["services"] = {
        "count": len(names),
        "hash": hashlib.sha1(
            "\n".join(names).encode("utf-8", "replace")).hexdigest()[:12],
    }
    return snap


def _file_registry_lines(base_dir, lines):
    """File registry diffs. A baseline and a quiet look are not alerts."""
    for line in lines:
        if not isinstance(line, str) or line.startswith("("):
            continue
        attack = ""
        start = line.rfind("[")
        end = line.rfind("]")
        if start >= 0 and end > start:
            attack = line[start + 1:end]
            if not attack.startswith("T"):
                attack = ""
        title = line.split(" = ", 1)[0].strip()[:200]
        _file_watch_alert(
            base_dir, "registry", "high" if attack else "medium",
            title, attack)

# Canary (tripwire) files the Oracle watches, planted by the runner
# itself under base_dir/canaries/. Tempting names, worthless contents:
# anything that reads, edits, or deletes one is the signal.
_CANARY_NAMES = (
    "passwords.txt",
    "backup-codes.txt",
    "api-keys.txt",
)
_CANARY_MARKER = "HOMING-PIGEON CANARY: this file is a tripwire."

def _canary_state(path):
    """sha1[:12] of a canary file's content, line endings normalized.

    The hash is taken over the content with CRLF folded to LF: planting
    writes exact bytes, but a text editor or tool on Windows may
    rewrite the file with CRLF endings, and that translation alone is
    not a trip. None when the file is missing; "?" when it exists but
    cannot be read (an unreadable canary is not a trip). A symlink is
    not followed. Never raises.
    """
    if os.path.islink(path):
        return "?"
    try:
        with open(path, "rb") as fh:
            data = fh.read(65536)
    except FileNotFoundError:
        return None
    except OSError:
        return "?"
    return hashlib.sha1(data.replace(b"\r\n", b"\n")).hexdigest()[:12]

def _plant_canary(path):
    """Write one canary file holding a fresh random token.

    O_EXCL | O_NOFOLLOW: an existing file is left alone, and a symlink
    is not written through. The file is mode 0600. Returns the new
    file's state hash, or None when the write failed. Never raises.
    """
    token = secrets.token_hex(16)
    body = (
        _CANARY_MARKER + "\n"
        "Reading, editing, or deleting this file is reported.\n"
        "canary-token: " + token + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = None
    try:
        fd = os.open(path, flags, 0o600)
        os.write(fd, body)
    except OSError:
        return None
    finally:
        if fd is not None:
            _close_quiet(fd)
    _chmod_quiet(path)
    return _canary_state(path)

def _file_watch_alert(base_dir, sensor, severity, title, attack):
    """Append one local-watch alert. Never raises, never executes.

    These are not mailed in by a sensor daemon. They are the runner
    noticing a canary trip or a firewall flip, written where the
    senses query already reads.
    """
    if _senses is None or not isinstance(base_dir, str) or not base_dir:
        return
    if not isinstance(title, str) or not title.strip():
        return
    try:
        now = _senses._now_iso()
        _senses.store_alert(base_dir, {
            "sensor": sensor,
            "severity": severity,
            "title": title.strip()[:200],
            "detail": {"attack": attack or "", "source": "local-watch"},
            "observed_at": now,
            "received_at": now,
        })
    except Exception:
        return

def _file_artifact_hits(base_dir, job_id, findings):
    """File a YARA or ClamAV hit once, when the job is scanned.

    The title carries the job id so a later job that drops the same
    file still files. At most eight hits. Never raises.
    """
    if not isinstance(findings, list):
        return
    jid = job_id if isinstance(job_id, str) else ""
    filed = 0
    for item in findings:
        if filed >= 8:
            break
        if not isinstance(item, str) or not item.strip():
            continue
        attack = ""
        start = item.rfind("[")
        end = item.rfind("]")
        if start >= 0 and end > start and item[start + 1:end].startswith("T"):
            attack = item[start + 1:end]
        title = item.strip()
        if jid:
            title = jid + ": " + title
        _file_watch_alert(base_dir, "artifact", "high", title[:200], attack)
        filed += 1

def _file_fresh_lines(base_dir, sensor, text):
    """File log lines that carry an ATT&CK id and were not seen before.

    The first look is a baseline: those lines are remembered and not
    filed. A later line with the same text is not filed again. A plain
    error line, with no technique id, is never filed. Never raises.
    """
    if _senses is None or not isinstance(base_dir, str) or not base_dir:
        return
    if not isinstance(text, str):
        text = ""
    path = os.path.join(base_dir, "oracle-logseen.json")
    seen = {}
    if not os.path.islink(path):
        try:
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                seen = loaded
        except Exception:
            seen = {}
    prior = seen.get(sensor)
    first = not isinstance(prior, list)
    known = set(prior) if isinstance(prior, list) else set()
    tagged = []
    for raw in text.splitlines():
        line = raw.strip()
        start = line.rfind("[")
        end = line.rfind("]")
        if start < 0 or end <= start:
            continue
        attack = line[start + 1:end]
        if not attack.startswith("T"):
            continue
        digest = hashlib.sha1(line.encode("utf-8", "replace")).hexdigest()[:16]
        tagged.append((digest, line[:200], attack))
    if first:
        seen[sensor] = [digest for digest, _line, _attack in tagged][-40:]
    else:
        filed = 0
        remembered = list(prior)
        for digest, line, attack in tagged:
            if digest in known or filed >= 8:
                continue
            _file_watch_alert(base_dir, sensor, "high", line, attack)
            remembered.append(digest)
            known.add(digest)
            filed += 1
        seen[sensor] = remembered[-40:]
        if filed == 0 and list(prior) == seen[sensor]:
            return
    try:
        _write_json(path, seen)
    except Exception:
        return

def _local_watch(cfg, base_dir):
    """One cheap look, on the poll, not only when the chat is opened.

    Three canary hashes, one firewall command, one antivirus posture
    check, a short log tail, and on Windows the registry diff. The
    journalctl fallback is skipped here so a box with no log file does
    not spawn a scan every poll. A trip is filed by the watch itself,
    before the page check runs. inference.watch_system=false skips the
    look. Never raises.
    """
    if not _oracle_watch_enabled(cfg):
        return
    if not _valid_base(base_dir):
        return
    for fn in (
            lambda: _canary_watch(base_dir),
            lambda: (_eventlog_tail(base_dir=base_dir)
                     if sys.platform == "win32"
                     else _host_log_tail(base_dir=base_dir, journal=False)),
            lambda: _registry_watch(base_dir) if sys.platform == "win32" else None,
            lambda: _firewall_watch(base_dir),
            lambda: _av_watch(base_dir),
    ):
        try:
            fn()
        except Exception:
            continue

_sensors = _required_load_mod("runner.ops.sensors", "ops.sensors")
_canary_watch = _sensors._canary_watch
_yara_hits = _sensors._yara_hits
recent_chat = _sensors.recent_chat


def _cfg_section_flag(cfg, section, key, default=True) -> bool:
    """Read a boolean flag from cfg[section][key], defaulting to default.

    (Named apart from _cfg_flag(value), the one-argument opt-in reader
    above: the two were briefly one name and the second definition
    shadowed the first, so every oracle_log and verbose read raised.)
    """
    sec = cfg.get(section) if isinstance(cfg, dict) else None
    if not isinstance(sec, dict):
        return default
    v = sec.get(key, default)
    if v is False or v == 0:
        return False
    if isinstance(v, str) and v.strip().lower() in ("false", "no", "off", "0"):
        return False
    return bool(v) if not default else (v is not False and v != 0)


def _oracle_watch_enabled(cfg) -> bool:
    """The Oracle's system watch defaults on."""
    return _cfg_section_flag(cfg, "inference", "watch_system", True)

_AUTH_LOG_PATHS = ("/var/log/auth.log", "/var/log/secure")
_SYS_LOG_PATHS = ("/var/log/syslog", "/var/log/messages", "/var/log/system.log")
_AUTH_LOG_MARKERS = (
    "failed password", "authentication failure", "invalid user",
    "sudo:", "useradd", "usermod", "groupadd",
)
# Same ids as the Windows audit map. A generic error line is not tagged.
_AUTH_LINE_ATTACK = (
    ("failed password", "T1110"),
    ("authentication failure", "T1110"),
    ("invalid user", "T1110"),
    ("sudo:", "T1548.003"),
    ("useradd", "T1136"),
    ("usermod", "T1136"),
    ("groupadd", "T1136"),
)

def _label_auth(line):
    """Append an ATT&CK id when a line is an auth event. Otherwise unchanged."""
    if not isinstance(line, str):
        return line
    low = line.lower()
    for mark, attack in _AUTH_LINE_ATTACK:
        if mark in low:
            tag = "[" + attack + "]"
            if tag not in line:
                return line + " " + tag
            return line
    return line
_SYS_LOG_MARKERS = ("error", "fatal", "fault", "fail")

def _tail_marked(path, markers, max_lines=20):
    """Last matching lines of a log file, or None if it cannot be read.

    Reads at most 4KB from the end. A symlink is not followed.
    Never raises.
    """
    if not isinstance(path, str) or os.path.islink(path):
        return None
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, size - 4096))
            raw = fh.read()
    except OSError:
        return None
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if size > 4096 and lines:
        lines = lines[1:]
    kept = []
    if not isinstance(markers, (list, tuple)):
        return []
    for line in lines:
        low = line.lower()
        if any(isinstance(mark, str) and mark in low for mark in markers):
            kept.append(line.strip()[:240])
    if isinstance(max_lines, bool) or not isinstance(max_lines, int) or max_lines < 1:
        return []
    return kept[-max_lines:]


_firewall = _required_load_mod("runner.ops.firewall", "ops.firewall")
_firewall_posture = _firewall._firewall_posture
# Every name the module defines is reachable here too: the suite
# (and a host) reads and patches them on the runner module.
_parse_netsh_profiles = _firewall._parse_netsh_profiles
_parse_socketfilterfw = _firewall._parse_socketfilterfw
_parse_ufw = _firewall._parse_ufw
_parse_iptables_policy = _firewall._parse_iptables_policy


_av = _required_load_mod("runner.ops.av", "ops.av")
_run_text = _av._run_text
_av_posture = _av._av_posture
_parse_defender_query = _av._parse_defender_query
_clam_sig_line = _av._clam_sig_line


def _read_posture_line(path):
    """Previous posture line, or None. A symlink is not followed."""
    if os.path.islink(path):
        return None
    old = _read_json_dict(path)
    if old is not None and isinstance(old.get("line"), str):
        return old["line"]
    return None

def _posture_watch(base_dir, posture, fname, sensor, attack_id, calm):
    """Posture line, plus whether it changed since the last look.

    The snapshot is the one line, not the ruleset. Unreadable returns
    None and does not overwrite a previous reading. A baseline is not
    an alert; a change files one, `high` when the line carries the
    sensor's ATT&CK id, else `calm`. Never raises.
    """
    line = posture()
    if not isinstance(line, str) or not line:
        return None
    if not _valid_base(base_dir):
        return line
    path = os.path.join(base_dir, fname)
    prev = _read_posture_line(path)
    try:
        _write_json(path, {"line": line, "saved_at": time.time()})
    except Exception:
        pass
    if prev is None:
        return line + " (baseline recorded just now)"
    if prev != line:
        attack = attack_id if attack_id in line else ""
        _file_watch_alert(base_dir, sensor, "high" if attack else calm,
                          line, attack)
        return line + " (changed)"
    return line

def _firewall_watch(base_dir):
    """The firewall posture line, and whether it changed (T1562.004)."""
    return _posture_watch(base_dir, _firewall_posture, "oracle-firewall.json",
                          "firewall", "T1562.004", "medium")

_CLAM_SIG_PATHS = (
    "/var/lib/clamav/daily.cvd",
    "/var/lib/clamav/daily.cld",
)
_AV_STALE_SEC = 7 * 86400


def _av_watch(base_dir):
    """The antivirus posture line, and whether it changed (T1562.001)."""
    return _posture_watch(base_dir, _av_posture, "oracle-av.json",
                          "av", "T1562.001", "info")

_ARTIFACT_MAX_FILES = 40
_ARTIFACT_MAX_BYTES = 1048576
_YARA_ATTACK = {
    "hp_encoded_exec": "T1059",
    "hp_webshell": "T1505.003",
    "hp_cred_dump": "T1003.001",
    "hp_reverse_shell": "T1071",
}

def _artifact_scan_enabled(cfg) -> bool:
    """On unless inference.artifact_scan is explicitly false."""
    return _cfg_section_flag(cfg, "inference", "artifact_scan", True)

def _work_files(work):
    """path -> (size, mtime_ns) for regular files under work."""
    found = {}
    try:
        walker = os.walk(work)
    except OSError:
        return found
    for dirpath, _dirs, filenames in walker:
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            found[path] = (st.st_size, getattr(st, "st_mtime_ns", 0))
    return found

def _rel_work(work, path):
    try:
        rel = os.path.relpath(path, work)
    except ValueError:
        rel = os.path.basename(path)
    return rel.replace("\\", "/")

def _artifact_findings(work, before, cfg):
    """YARA and ClamAV hits on files this job created or changed.

    Advisory. Does not change the exit code. Skips files over 1MB and
    stops after 40 files. YARA is yr (YARA-X) or yara. ClamAV is
    clamdscan only: clamscan reloads the whole database and is not
    used. A missing tool is skipped, not reported as clean. Never raises.
    """
    if not _artifact_scan_enabled(cfg):
        return []
    if not isinstance(before, dict):
        before = {}
    try:
        after = _work_files(work)
    except Exception:
        return []
    targets = []
    for path, meta in sorted(after.items()):
        if before.get(path) == meta:
            continue
        size = meta[0] if meta else 0
        if not isinstance(size, int) or size < 0 or size > _ARTIFACT_MAX_BYTES:
            continue
        targets.append(path)
        if len(targets) >= _ARTIFACT_MAX_FILES:
            break
    if not targets:
        return []
    hits = []
    try:
        hits.extend(_yara_hits(work, targets, cfg))
        hits.extend(_clam_hits(work, targets))
    except Exception:
        return hits
    return hits[:20]

def _yara_rules_text(cfg):
    """Operator rules if inference.yara_rules is a readable file.

    A missing file, an empty file, or a symlink falls back to the
    built-in rules. The symlink is not followed. Never raises.
    """
    inf = cfg.get("inference") if isinstance(cfg, dict) else None
    path = inf.get("yara_rules") if isinstance(inf, dict) else None
    if isinstance(path, str) and path.strip() and not os.path.islink(path):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read(65536)
        except (OSError, UnicodeError):
            text = ""
        if isinstance(text, str) and text.strip():
            return text
    return _YARA_RULES


def _artifact_note(job_id, job, r, key=""):
    """A retained record that carries a scan hit and not the raw output.

    Full-view jobs are not retained. A hit still has to reach the local
    Oracle, so this note is what gets saved in that case. None when
    there is nothing to report.
    """
    scan = r.get("artifact_scan") if isinstance(r, dict) else None
    if not isinstance(scan, list) or not scan:
        return None
    script = ""
    kind = ""
    if isinstance(job, dict):
        kind = job.get("kind") if isinstance(job.get("kind"), str) else ""
        script = _as_str(job.get("script"))[:500]
    return {
        "job_id": job_id,
        "kind": kind,
        "script": script,
        "stdout": "",
        "stderr": "",
        "exit_code": _as_int(r.get("exit_code"), -1),
        "timed_out": bool(r.get("timed_out")),
        "artifact_scan": [str(item)[:200] for item in scan[:20]],
        "saved_at": time.time(),
        # The key the job verified under, as a full record keeps it
        # (Q103 item 1): only that key may query the note.
        "key": key if isinstance(key, str) else "",
    }

def _clam_hits(work, targets):
    binary = shutil.which("clamdscan")
    if not binary:
        return []
    try:
        proc = subprocess.run(
            [binary, "--fdpass", "--no-summary", "--stdout", *targets],
            capture_output=True, text=True, timeout=8)
    except Exception:
        return []
    # 0 clean, 1 findings. Anything else is a dead daemon, not a hit
    # and not a clean bill. Stay quiet.
    if proc.returncode not in (0, 1) or not isinstance(proc.stdout, str):
        return []
    hits = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line.endswith(" FOUND"):
            continue
        body = line[: -len(" FOUND")]
        sig = body.rsplit(": ", 1)[-1][:80]
        path = body.rsplit(": ", 1)[0] if ": " in body else ""
        rel = _rel_work(work, path) if path else "file"
        hits.append("clamav " + sig + " " + rel + " [T1204.002]")
    return hits

def _job_facts(data, job_id):
    """(kind, status, when) for one retained job, as plain facts.

    Shared by the per-job summary and the job index at the top of
    the Oracle context, so the two can never disagree.
    """
    kind = data.get("kind") if isinstance(data.get("kind"), str) else ""
    kind = kind or "kind not recorded"
    if data.get("timed_out"):
        status = "timed out"
    else:
        ec = data.get("exit_code")
        status = f"exit code {ec}" if isinstance(ec, int) else "status unknown"
    when = "time unknown"
    try:
        ts = float(data.get("saved_at") or 0)
        if ts > 0:
            when = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OverflowError):
        pass
    return kind, status, when

# Deterministic sensitive-access findings over a job's script. The
# Flag321 field tests (2026-10-17) showed the Oracle's small local
# models do not reason "this job read a credential file" out of a
# raw script -- both the 1.5B and the 3B missed it, unprompted and
# even when asked pointedly, while quoting the script back. So the
# conclusion-shaped fact is computed here, mechanically, and
# carried in the job's summary as a "notable:" line that both ask
# prompts tell the model to treat as a finding. Advisory only:
# nothing is blocked, refused, or re-judged because of this.
_SENSITIVE_MARKERS = (
    "/etc/shadow", "/etc/gshadow", "/etc/passwd", "/etc/master.passwd",
    ".ssh/", ".aws/", ".gnupg/", ".azure/", ".kube/",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
    ".pem", ".key", "credential", ".env",
    "login data", "keychain", "ntuser.dat", "/root/",
)

# Absolute paths under these prefixes are ordinary system-command
# territory (a binary's own path, device nodes, kernel interfaces)
# and are not findings on their own. Sensitive markers are checked
# first and always win. Everything else absolute -- /tmp, /var,
# /opt, /srv, another job's directory -- is outside the job's own
# workspace, which is the finding.
_ORDINARY_PREFIXES = (
    "/usr/", "/bin/", "/sbin/", "/lib/", "/lib64/", "/proc/",
    "/sys/", "/dev/",
)

_PATH_SPLITTERS = " \t\r\n'\"`;|&<>(){}[]"

_paths = _required_load_mod("runner.ops.paths", "ops.paths")
_script_path_findings = _paths._script_path_findings


def _chosen_retained_rows(base_dir, limit=6):
    """The retained rows a context build would use, newest first.

    Shared by oracle_context (which summarizes them) and
    _withheld_scan_text (which collects what those summaries
    withhold), so the two can never drift apart: the gate watches
    exactly the outputs the context withheld, no more, no fewer.
    """
    rows = []
    if not isinstance(base_dir, str):
        return rows
    d = os.path.join(base_dir or "", "retained")
    if os.path.isdir(d):
        for name in os.listdir(d):
            if not name.endswith(".json"):
                continue
            job_id = name[:-5]
            if not _SAFE_JOB_ID.match(job_id) or job_id in (".", ".."):
                continue
            path = os.path.join(d, name)
            if os.path.islink(path):
                continue
            try:
                rows.append((os.path.getmtime(path), path, job_id))
            except OSError:
                continue
        rows.sort(reverse=True)
    if limit is None:
        n = None
    elif isinstance(limit, bool):
        n = 6
    else:
        try:
            n = int(limit)
        except (TypeError, ValueError, OverflowError):
            n = 6
        if n < 0:
            n = 0
    return rows if n is None else rows[:n]

def _withheld_scan_text(base_dir, limit=6) -> str:
    """Outputs the retained summaries withhold, for the reply gate only.

    A flagged job's output never reaches the model (see
    _retained_job_summary), but the gate's fragment check learns
    its secrets from the text it scans -- remove the output from
    the context and the gate goes blind to that value. This text
    is the compensation: the same outputs, handed to the sanitizer
    as scan-only material. It is never placed in a model message,
    never logged as context, and never returned to a caller of the
    ask functions; it exists so a reply that repeats a pattern-
    shaped secret from a flagged job -- however the model obtained
    it -- is still rejected. Arbitrary short values match no
    pattern and stay unprotectable here; withholding is their
    defense, and it stands.
    """
    blobs = []
    for job_id, data in _flagged_retained(base_dir, limit):
        text = _output_blob(data).strip()
        if text:
            blobs.append(text[:8000])
    return "\n".join(blobs)

def _deterministic_oracle_answer(cfg, base_dir, watch=None) -> str:
    """The Pi Light answer: the box's records, un-narrated.

    In deterministic mode there is no model to read the context, so
    the context itself is the answer -- the job index first, then
    the retained job summaries (notable lines included), the log
    tail, and the watch sections, exactly as oracle_context builds
    them. The header says plainly what the reader is looking at.
    """
    if watch is None:
        watch = _oracle_watch_enabled(cfg)
    ctx = oracle_context(base_dir, watch=watch)
    return ("Deterministic Oracle (Pi Light): no local model runs on "
            "this box, so here is the current record, un-narrated.\n\n"
            + ctx)

def _report_oracle_mode(cfg) -> None:
    """Startup report: one line when the Oracle is deterministic.

    The llm default stays silent -- no new noise on boxes that did
    not choose Pi Light. Mirrors _report_extensions' shape.
    """
    if _oracle_mode(cfg) == "deterministic":
        log("oracle: deterministic mode (Pi Light) -- no local model; "
            "briefs and answers are assembled from the box's records")

_context = _required_load_mod("runner.ops.context", "ops.context")
oracle_context = _context.oracle_context


# The Oracle's HTML page lives in runner/ops/oracle_page.py; loaded
# the way every sibling is, so `python3 runner.py` from an install
# (where `runner` is this file, not the package) and the one-file
# binaries find it too.
_oracle_page_mod = _load_mod("runner.ops.oracle_page", "ops.oracle_page")
oracle_page = _oracle_page_mod.oracle_page if _oracle_page_mod else None
# The argument parser (runner/ops/cli.py), loaded here with the other
# siblings rather than inside main(), so a test that stands in for
# _load_mod during main() does not hand main a parser it did not ask for.
# Every name the module defines is reachable here too: the suite
# (and a host) reads and patches them on the runner module.
_text = _oracle_page_mod._text
_cli = _load_mod("runner.ops.cli", "ops.cli")
# Every name the module defines is reachable here too: the suite
# (and a host) reads and patches them on the runner module.
build_parser = _cli.build_parser
_transports_arg = _cli._transports_arg


_ORACLE_REJECTS = {
    "inference_unconfigured": ("No loopback model is configured. Re-run install.exe "
                               "--inference-only to finish the model setup, or point "
                               "inference.endpoint in config.json at your local "
                               "Ollama server."),
    "inference_error": "The local model did not answer.",
    "sanitization": "The reply was dropped because it repeated protected material.",
    "tool_budget": ("The Oracle kept reaching for tools without answering. "
                    "Try a narrower question."),
}

_ORACLE_CHAT_MAX = 1_048_576

_CHAT_WINDOW_TURNS = 4
_CHAT_WINDOW_CHARS = 2000


def record_oracle_turn(base_dir, cfg, question, ans, event="ask"):
    """One chat line on disk. Secrets are redacted. The file rolls at 1 MiB."""
    if not base_dir or not isinstance(base_dir, str):
        return
    patterns = _redact_patterns(cfg if isinstance(cfg, dict) else {})
    question, _q = redact_text(question if isinstance(question, str) else "", patterns)
    if not isinstance(ans, dict):
        ans = {}
    raw_answer = ans.get("answer") or ""
    if not isinstance(raw_answer, str):
        raw_answer = ""
    answer, _a = redact_text(raw_answer, patterns)
    rejected = ans.get("rejected") or ""
    model = ans.get("model") or ""
    if not isinstance(rejected, str):
        rejected = ""
    if not isinstance(model, str):
        model = ""
    try:
        tool_rounds = int(ans.get("tool_rounds") or 0)
    except (TypeError, ValueError, OverflowError):
        tool_rounds = 0
    detail = ans.get("detail") or ""
    if not isinstance(detail, str):
        detail = ""
    detail, _d = redact_text(detail, patterns)
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event if isinstance(event, str) else "ask",
        "question": question[:2000],
        "answer": answer[:4000],
        "rejected": rejected,
        "detail": detail[:300],
        "model": model,
        "tool_rounds": tool_rounds,
    }
    path = os.path.join(base_dir, "oracle-chat.jsonl")
    append_bounded_log(path, json.dumps(rec, ensure_ascii=False),
                       max_bytes=_ORACLE_CHAT_MAX)

def _oracle_host_ok(handler) -> bool:
    peer = handler.client_address[0] if handler.client_address else ""
    if not _is_loopback_ip(peer):
        return False
    host = (handler.headers.get("Host") or "").split(",")[0].strip()
    hostname = host.rsplit(":", 1)[0].strip("[]").lower()
    if hostname not in ("127.0.0.1", "localhost", "::1"):
        return False
    origin = (handler.headers.get("Origin") or "").strip()
    if not origin:
        return True
    try:
        parsed = urlparse(origin)
    except Exception:
        return False
    return parsed.scheme == "http" and (parsed.hostname or "").lower() in (
        "127.0.0.1", "localhost", "::1")

def _oracle_token_ok(got, token) -> bool:
    """True when the presented chat token matches.

    Both sides are hashed first. CPython's compare_digest walks the
    shorter buffer for the length of the longer one, so a short or
    empty token must not be handed to it raw.
    """
    if not isinstance(got, str) or not isinstance(token, str):
        return False
    return hmac.compare_digest(
        hashlib.sha256(got.encode("utf-8", "replace")).digest(),
        hashlib.sha256(token.encode("utf-8", "replace")).digest())

_oracle_server = _required_load_mod("runner.ops.oracle_server", "ops.oracle_server")
make_oracle_server = _oracle_server.make_oracle_server
# Every name the module defines is reachable here too: the suite
# (and a host) reads and patches them on the runner module.
_OracleServer = _oracle_server._OracleServer


def _warm_oracle_model(inf):
    """One tiny inference call so the first real question is not the
    cold start. Runs on a daemon thread; logs, never raises."""
    t0 = time.monotonic()
    try:
        msg = _inference_chat(
            inf,
            [{"role": "user",
              "content": "Reply with the single word: ok"}],
            None, None, 120)
    except Exception as e:
        log(f"oracle model warm-up failed: {e}", "WARN")
        return
    if isinstance(msg, dict) and msg.get("role") == "error":
        log("oracle model warm-up did not answer: "
            + str(msg.get("content") or ""), "WARN")
    else:
        log(f"oracle model warm-up finished in "
            f"{time.monotonic() - t0:.0f}s")


_main = _required_load_mod("runner.ops.main", "ops.main")
main = _main.main
_config_given = _main._config_given
_installed_config = _main._installed_config


def _run() -> "NoReturn":
    # A frozen exe (PyInstaller) reports an uncaught KeyboardInterrupt as
    # "Failed to execute script", which looks like a crash. Ctrl+C is a
    # normal shutdown: exit quietly.
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__" and len(sys.argv) > 1 \
        and sys.argv[1] == "--query-worker":
    # The grep worker (Q84). The runner re-enters as itself, the
    # same way a frozen exe re-enters for a transport extension,
    # and matches one pattern at a time until the parent kills it.
    from runner.ops.queries import worker_main
    raise SystemExit(worker_main())

if __name__ == "__main__" and len(sys.argv) > 2 \
        and sys.argv[1] == "--transport-extension-module":
    # Frozen-exe dispatch: the supervisor launches first-party
    # transport extensions as [exe, -m, <module>, ...]; a frozen
    # exe has no -m, so it re-enters here and runs the module's
    # main() with the remaining argv.
    import importlib
    _ext_mod = importlib.import_module(sys.argv[2] + ".__main__")
    sys.argv = [sys.argv[2]] + sys.argv[3:]
    raise SystemExit(_ext_mod.main())

if __name__ == "__main__":
    _run()

