#!/usr/bin/env python3
"""The extension review: the Oracle reads an extension against its
manifest before the runner loads it.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

An extension is a folder of code the owner dropped in, with a
manifest that says what it is. Nothing signs the code. Until it
does, the manifest is the owner's statement and this module checks
the code against it, every time the folder is read, before the
loader hands the manifest to anything that would act on it: the
sense ingest path (which trusts the manifest's signal list) and the
transport supervisor (which executes the manifest's `entry` with a
runtime config that carries secrets).

The review is deterministic and stdlib-only; it needs no model. The
Oracle's model-side reading of extension code (the sources pass,
runner/ops/extsources.py) is unchanged and complementary: that one
reads for meaning, this one checks the statement.

What it finds, and how hard:

  high  -- refused under `enforce`:
    symlink               a symlink inside the folder (the loader
                          already refuses a symlinked manifest; this
                          covers everything else)
    syntax                a .py file that does not compile
    unreviewed            a code file too large or not UTF-8, so it
                          could not be read
    text.control          bidi or zero-width control characters in a
                          code file or the manifest (Trojan Source)
    capability.undeclared code that listens, reaches the network,
                          spawns processes or loads native code while
                          the manifest's `capabilities` does not say so
    state.reference       code that names the runner's own state --
                          config.json, seen.json, board.json, the
                          security events, the sent-result records --
                          which no extension has business reading
    entry.outside         a transport `entry` that escapes the
                          extension folder
  warn  -- logged, never refused:
    signal.undeclared     a signal filed in code that the manifest
                          does not declare (ingest refuses it anyway)
    shadow                a transport in the owner's extensions
                          directory that shadows a shipped one, which
                          is allowed and must be loud
    dynamic               exec/eval/__import__ at run time, the
                          Oracle's cue to read closely
  note  -- in the report only:
    signal.unused         a declared signal the code never files
    capability.unused     a declared capability the code never uses
    entry.program         an entry whose program is outside the
                          folder (an interpreter, shipped code)

The owner picks the posture with `extension_review` in config.json:
`enforce` (default) refuses an extension with a high finding the way
the loader refuses a bad manifest -- one log line with the reason
and the remedy, a security event, the agent keeps running without
it; `advisory` loads everything and logs what it found; `off` skips
the review. Everything the review concluded is written to
<base_dir>/extension-review.json and shown by `--inspect review`.

The manifest's `capabilities` list (extension API 1, optional) takes
these words: `network` (the extension opens connections), `listen`
(it accepts them), `subprocess` (it runs programs), `native` (it
loads native code). Declare what the code does; the review holds
the code to it.

Free of runner imports: runner.py and runner/wire/transports.py
call in here.
"""
import ast
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone

CONFIG_KEY = "extension_review"
MODES = ("off", "advisory", "enforce")
DEFAULT_MODE = "enforce"
REPORT_FILE = "extension-review.json"

# The vocabulary of the manifest's `capabilities` list; the loader
# (runner/ops/extensions.py) validates it, this module holds the code
# to it.
CAPABILITIES = ("network", "listen", "subprocess", "native")

# A code file larger than this is not read; a sense is a few
# hundred lines, a transport a few thousand.
MAX_CODE_BYTES = 2 * 1024 * 1024
# Files walked per extension before the review gives up on it.
MAX_FILES = 4000

CODE_SUFFIXES = (".py", ".pyw", ".sh", ".bash", ".zsh", ".ps1", ".bat",
                 ".cmd", ".js", ".mjs", ".rb", ".pl")
_PY_SUFFIXES = (".py", ".pyw")
_SHELL_SUFFIXES = (".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd")
MANIFEST_FILE = "extension.json"
_TEXT_ALSO = (MANIFEST_FILE, "sources.json")

# --- capability markers ---------------------------------------------------
# Imports are read from the AST (exact), call shapes from the source
# text (a regex, generous on purpose: a false positive costs the
# author one word in the manifest, a false negative costs the owner).
_NETWORK_MODULES = frozenset({
    "socket", "ssl", "smtplib", "imaplib", "poplib", "ftplib",
    "telnetlib", "nntplib", "smtpd", "http.client", "urllib.request",
    "xmlrpc.client", "requests", "httpx", "aiohttp", "urllib3",
    "paramiko", "asyncssh", "nats", "websocket", "websockets", "pika",
    "redis", "psycopg2", "psycopg", "pymysql", "pymongo", "boto3",
    "botocore", "pycurl", "dns", "ldap3", "grpc", "kafka",
    "paho", "zmq",
    # The runner's own network-facing libraries, which a shipped
    # transport reaches the mailbox and the token endpoint through.
    # runner.ops.extensions is not here: its loopback delivery is the
    # sense contract itself, not a capability a sense takes on.
    "runner.wire.mailbox", "runner.wire.oauth",
})
_LISTEN_MODULES = frozenset({
    "socketserver", "http.server", "wsgiref", "xmlrpc.server",
    "aiohttp.web", "flask", "fastapi", "uvicorn", "gunicorn",
    "tornado", "bottle", "cherrypy", "twisted", "waitress",
    "hypercorn", "starlette",
})
_SUBPROCESS_MODULES = frozenset({
    "subprocess", "pty", "pexpect", "sh", "plumbum", "commands",
})
_NATIVE_MODULES = frozenset({"ctypes", "_ctypes", "cffi"})

_NETWORK_CALLS = re.compile(
    r"(?:\burllib\.request\b|\burlopen\s*\(|\bcreate_connection\s*\(|"
    r"\bopen_connection\s*\(|\bgetaddrinfo\s*\(|\bsendto\s*\(|"
    r"\.connect(?:_ex)?\s*\()")
_LISTEN_CALLS = re.compile(
    r"(?:\.bind\s*\(|\.listen\s*\(|\bstart_server\s*\(|"
    r"\bcreate_server\s*\(|\bcreate_datagram_endpoint\s*\(|"
    r"\bserve_forever\s*\()")
_SUBPROCESS_CALLS = re.compile(
    r"\bos\s*\.\s*(?:system|popen|exec[lv]p?e?|spawn[lv]p?e?|fork|"
    r"forkpty|posix_spawnp?|startfile)\s*\(")
_NATIVE_CALLS = re.compile(r"\bctypes\s*\.")
# exec(, eval(, __import__( as free calls. The lookbehind is what
# keeps ast.literal_eval( and any attribute call (obj.eval() out:
# a word character or a dot before the name is not this pattern.
_DYNAMIC_CALLS = re.compile(
    r"(?<![\w.])(?:exec|eval|__import__)\s*\(|\bimportlib\.import_module\s*\(")
_SHELL_NETWORK = re.compile(
    r"(?<![\w-])(?:curl|wget|ncat|netcat|socat|ssh|scp|sftp|rsync|"
    r"telnet|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)(?![\w-])"
    r"|\bopenssl\s+s_client\b|\bSystem\.Net\.")

# The runner's own state. No extension reads these: a sense drops
# envelopes into the local inbox and a transport reads the runtime
# config it is handed, nothing else of the runner's. The file names
# are the distinctive ones (a bare config.json is anyone's).
_STATE_REFERENCE = re.compile(
    r"(?<![\w.-])(?:seen\.json|board\.json|security-events\.jsonl|"
    r"query_times\.json|extension-review\.json)(?![\w-])")
# The mailbox and key material live in the runner's config. A
# transport may be handed some of it (dtls authenticates the PSK,
# email opens the mailbox), so this check is for senses, which the
# runner never hands a secret: a sense signs with the key the owner
# gave it directly.
_SENSE_SECRET_REFERENCE = re.compile(
    r"(?<![\w.])(?:mailbox_password|additional_secrets|"
    r"oauth_client_secret|oauth_refresh_token)(?![\w])")

# Bidi overrides and isolates, zero-width characters, the BOM
# mid-file. CVE-2021-42574 and friends.
_CONTROL_CHARS = re.compile(
    "[‪-‮⁦-⁩​-‏⁠⁡⁢"
    "⁣⁤﻿­]")

# How a sense names the signal it files: `"signal": "name"` in a
# dict literal, `signal="name"` as a keyword, `signal = "name"`.
_SIGNAL_IN_CODE = re.compile(
    r"""(?<![\w])signal["']?\s*[:=]\s*["']([A-Za-z0-9][A-Za-z0-9._-]*)["']""")

_LOCK = threading.Lock()
_CACHE = {}          # folder -> (fingerprint, result)
_CACHE_CAP = 256
_LAST_REPORT = {}    # kind -> the dict last written for that kind


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Owner posture
# ---------------------------------------------------------------------------

def mode_of(cfg):
    """(mode, problem). The posture the owner set with
    `extension_review`, or the default. `problem` is a readable
    config error when the value is not one of the modes; a security
    mode is refused when wrong rather than defaulted (Decision 1)."""
    if not isinstance(cfg, dict) or CONFIG_KEY not in cfg:
        return DEFAULT_MODE, None
    raw = cfg.get(CONFIG_KEY)
    if raw is True:
        return "enforce", None
    if raw is False:
        return "off", None
    if isinstance(raw, str) and raw.strip().lower() in MODES:
        return raw.strip().lower(), None
    return DEFAULT_MODE, (
        f"{CONFIG_KEY} must be one of {', '.join(repr(m) for m in MODES)} "
        f"(got {raw!r})")


# ---------------------------------------------------------------------------
# Reading one folder
# ---------------------------------------------------------------------------

def _finding(code, severity, detail, path="", line=0):
    f = {"code": code, "severity": severity, "detail": detail}
    if path:
        f["path"] = path
    if line:
        f["line"] = line
    return f


def _walk(folder):
    """Every entry under folder as (relpath, abspath, is_dir, is_link),
    sorted, __pycache__ skipped, symlinked directories not entered.
    The second value is True when the walk hit MAX_FILES."""
    out = []
    truncated = False
    for root, dirs, files in os.walk(folder, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        rel_root = os.path.relpath(root, folder)
        rel_root = "" if rel_root == "." else rel_root
        for d in list(dirs):
            p = os.path.join(root, d)
            rel = os.path.join(rel_root, d) if rel_root else d
            out.append((rel, p, True, os.path.islink(p)))
            if os.path.islink(p):
                dirs.remove(d)
        for name in sorted(files):
            p = os.path.join(root, name)
            rel = os.path.join(rel_root, name) if rel_root else name
            out.append((rel, p, False, os.path.islink(p)))
        if len(out) > MAX_FILES:
            truncated = True
            break
    return out, truncated


def fingerprint(folder):
    """What the review's cache keys on: every path's size and mtime.
    None when the folder cannot be read."""
    try:
        entries, truncated = _walk(folder)
    except OSError:
        return None
    sig = []
    for rel, p, is_dir, is_link in entries:
        try:
            st = os.lstat(p)
            sig.append((rel, is_dir, is_link, st.st_size, st.st_mtime_ns))
        except OSError:
            sig.append((rel, is_dir, is_link, -1, -1))
    return (tuple(sig), truncated)


def _module_names(tree):
    """Top-level and dotted names imported by a parsed module."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and not node.level:
                names.add(node.module)
                for alias in node.names:
                    names.add(f"{node.module}.{alias.name}")
    return names


def _matches(names, table):
    hit = set()
    for name in names:
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            prefix = ".".join(parts[:i])
            if prefix in table:
                hit.add(prefix)
    return hit


def _line_of(text, match):
    return text.count("\n", 0, match.start()) + 1


def _read_code(path):
    """(text, problem). problem names why the file was not read."""
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return None, f"cannot stat: {e}"
    if size > MAX_CODE_BYTES:
        return None, f"{size} bytes, more than the {MAX_CODE_BYTES} the review reads"
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_CODE_BYTES + 1)
    except OSError as e:
        return None, f"cannot read: {e}"
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError as e:
        return None, f"not UTF-8 (byte {e.start})"


def _scan_python(rel, text, observed, findings, signals_in_code):
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as e:
        findings.append(_finding(
            "syntax", "high",
            f"does not compile: {e.msg}", rel, e.lineno or 0))
        tree = None
    except (ValueError, RecursionError, MemoryError) as e:
        # Python 3.9 to 3.11 raise ValueError for a NUL byte in the
        # source and RecursionError (or MemoryError) for nesting past
        # the parser's depth; 3.12 turned those into SyntaxError.
        # The floor is 3.9, so this arm is live there (Q42).
        findings.append(_finding(
            "syntax", "high", f"does not parse: {e}", rel))
        tree = None
    if tree is not None:
        names = _module_names(tree)
        for cap, table in (("network", _NETWORK_MODULES),
                           ("listen", _LISTEN_MODULES),
                           ("subprocess", _SUBPROCESS_MODULES),
                           ("native", _NATIVE_MODULES)):
            for mod in sorted(_matches(names, table)):
                observed.setdefault(cap, []).append(f"{rel}: import {mod}")
    for cap, rx in (("network", _NETWORK_CALLS),
                    ("listen", _LISTEN_CALLS),
                    ("subprocess", _SUBPROCESS_CALLS),
                    ("native", _NATIVE_CALLS)):
        m = rx.search(text)
        if m:
            observed.setdefault(cap, []).append(
                f"{rel}:{_line_of(text, m)}: {m.group(0).strip()}")
    m = _DYNAMIC_CALLS.search(text)
    if m:
        findings.append(_finding(
            "dynamic", "warn",
            f"evaluates code at run time: {m.group(0).strip()}",
            rel, _line_of(text, m)))
    for m in _SIGNAL_IN_CODE.finditer(text):
        signals_in_code.setdefault(m.group(1), (rel, _line_of(text, m)))


def _scan_shell(rel, text, observed):
    m = _SHELL_NETWORK.search(text)
    if m:
        observed.setdefault("network", []).append(
            f"{rel}:{_line_of(text, m)}: {m.group(0).strip()}")


def _scan_common(rel, text, findings, is_code, kind):
    m = _CONTROL_CHARS.search(text)
    if m:
        findings.append(_finding(
            "text.control", "high",
            f"contains U+{ord(m.group(0)):04X}, a bidi or zero-width "
            f"control character", rel, _line_of(text, m)))
    if is_code:
        m = _STATE_REFERENCE.search(text)
        if m is None and kind == "sense":
            m = _SENSE_SECRET_REFERENCE.search(text)
        if m:
            findings.append(_finding(
                "state.reference", "high",
                f"names the runner's own state: {m.group(0)}",
                rel, _line_of(text, m)))


def _under(path, folder):
    try:
        rp = os.path.realpath(path)
        rf = os.path.realpath(folder)
    except (OSError, ValueError):
        return False
    rp = os.path.normcase(rp)
    rf = os.path.normcase(rf)
    return rp == rf or rp.startswith(rf.rstrip(os.sep) + os.sep)


def _review_entry(manifest, folder, findings, shipped):
    """A transport's `entry` argv: every path it names stays in the
    folder (the child's working directory). Substitution tokens are
    resolved the way the supervisor resolves them."""
    entry = manifest.get("entry")
    if not isinstance(entry, list) or not entry:
        return
    subs = {"{python}": sys.executable, "{self}": sys.executable,
            "{extension_dir}": folder, "{channel_dir}": "",
            "{runtime_config}": "", "{base_dir}": "", "{name}": ""}
    for i, part in enumerate(entry):
        if not isinstance(part, str):
            continue
        raw = part
        for tok, val in subs.items():
            part = part.replace(tok, val)
        if "{extension_dir}" in raw:
            target = part
            if not _under(target, folder):
                findings.append(_finding(
                    "entry.outside", "high",
                    f"entry[{i}] {raw!r} resolves outside the extension "
                    f"folder", MANIFEST_FILE))
            continue
        if raw in ("{python}", "{self}"):
            continue
        if i >= 1 and entry[i - 1] == "-m":
            if not shipped and part.startswith("runner."):
                findings.append(_finding(
                    "entry.program", "note",
                    f"entry runs shipped code: {part}", MANIFEST_FILE))
            continue
        norm = part.replace("\\", "/")
        if ".." in norm.split("/"):
            findings.append(_finding(
                "entry.outside", "high",
                f"entry[{i}] {raw!r} steps out of the extension folder "
                f"with '..'", MANIFEST_FILE))
            continue
        if os.path.isabs(part):
            if _under(part, folder):
                continue
            if i == 0:
                findings.append(_finding(
                    "entry.program", "note",
                    f"entry's program is outside the extension folder: "
                    f"{part}", MANIFEST_FILE))
            elif os.path.exists(part):
                findings.append(_finding(
                    "entry.outside", "high",
                    f"entry[{i}] {raw!r} names a path outside the "
                    f"extension folder", MANIFEST_FILE))


def review_folder(manifest, folder, *, shipped=False, shadows=None):
    """Review one extension folder against its cleaned manifest.

    Returns a result dict: {"findings": [...], "capabilities":
    {"declared": [...], "observed": {cap: [where, ...]}}}.
    Never raises on extension data.
    """
    findings = []
    observed = {}
    signals_in_code = {}
    declared_caps = list(manifest.get("capabilities") or [])
    kind = manifest.get("kind")
    try:
        entries, truncated = _walk(folder)
    except OSError as e:
        findings.append(_finding("unreviewed", "high",
                                 f"folder cannot be walked: {e}"))
        entries, truncated = [], False
    if truncated:
        findings.append(_finding(
            "unreviewed", "high",
            f"more than {MAX_FILES} entries; the review stopped"))
    for rel, path, is_dir, is_link in entries:
        if is_link:
            findings.append(_finding(
                "symlink", "high", "a symlink inside the extension folder",
                rel))
            continue
        if is_dir:
            continue
        lower = rel.lower()
        base = os.path.basename(rel)
        is_code = lower.endswith(CODE_SUFFIXES)
        if not is_code and base not in _TEXT_ALSO:
            continue
        text, problem = _read_code(path)
        if text is None:
            findings.append(_finding("unreviewed", "high",
                                     f"not reviewed: {problem}", rel))
            continue
        _scan_common(rel, text, findings, is_code, kind)
        if lower.endswith(_PY_SUFFIXES):
            _scan_python(rel, text, observed, findings, signals_in_code)
        elif lower.endswith(_SHELL_SUFFIXES):
            _scan_shell(rel, text, observed)
    for cap in CAPABILITIES:
        where = observed.get(cap) or []
        if where and cap not in declared_caps:
            findings.append(_finding(
                "capability.undeclared", "high",
                f"the code uses {cap} ({where[0]}) and the manifest does "
                f"not declare it; add \"capabilities\": "
                f"{json.dumps(sorted(set(declared_caps) | {cap}))} to "
                f"{MANIFEST_FILE} if that is intended",
                where[0].split(":")[0]))
        elif cap in declared_caps and not where:
            findings.append(_finding(
                "capability.unused", "note",
                f"the manifest declares {cap}; the review saw no use of it"))
    if kind == "sense":
        declared_signals = [s.get("name") for s in manifest.get("signals") or []
                            if isinstance(s, dict)]
        for sig, (rel, line) in sorted(signals_in_code.items()):
            if sig not in declared_signals:
                findings.append(_finding(
                    "signal.undeclared", "warn",
                    f"files signal {sig!r}, which the manifest does not "
                    f"declare; ingest will refuse it", rel, line))
        for sig in declared_signals:
            if sig not in signals_in_code:
                findings.append(_finding(
                    "signal.unused", "note",
                    f"declared signal {sig!r} is not filed anywhere the "
                    f"review can see"))
    if kind == "transport":
        _review_entry(manifest, folder, findings, shipped)
        if shadows and manifest.get("name") in shadows:
            findings.append(_finding(
                "shadow", "warn",
                f"shadows the shipped transport {manifest.get('name')!r}; "
                f"this folder runs instead of it", MANIFEST_FILE))
    order = {"high": 0, "warn": 1, "note": 2}
    findings.sort(key=lambda f: (order.get(f["severity"], 3), f["code"],
                                 f.get("path", ""), f.get("line", 0)))
    return {"findings": findings,
            "capabilities": {"declared": sorted(declared_caps),
                             "observed": {k: sorted(v) for k, v in
                                          sorted(observed.items())}}}


def _cached_review(manifest, folder, **kw):
    """(result, fresh). The review is recomputed when any file in
    the folder changed; `fresh` says whether it was."""
    fp = fingerprint(folder)
    key = os.path.normcase(os.path.abspath(folder)) if isinstance(folder, str) else folder
    with _LOCK:
        hit = _CACHE.get(key)
        if hit is not None and hit[0] == fp and fp is not None:
            return hit[1], False
    result = review_folder(manifest, folder, **kw)
    with _LOCK:
        if len(_CACHE) >= _CACHE_CAP:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = (fp, result)
    return result, True


def forget(folder=None):
    """Drop the review cache (tests; a folder when given)."""
    with _LOCK:
        if folder is None:
            _CACHE.clear()
        else:
            _CACHE.pop(os.path.normcase(os.path.abspath(folder)), None)


def verdict(result, mode):
    """"loaded", "refused", or "off" for one result under a mode."""
    if mode == "off":
        return "off"
    if mode == "enforce" and any(
            f.get("severity") == "high" for f in result.get("findings", [])):
        return "refused"
    return "loaded"


# ---------------------------------------------------------------------------
# The gate: applied to a loader's registry
# ---------------------------------------------------------------------------

def apply(cfg, base_dir, registry, *, kind, shipped_dirs=(), shadows=None,
          log=None, event_sink=None):
    """Review every extension in `registry` (name -> cleaned manifest
    with "dir") and return (registry, problems, report).

    Under `enforce` an extension with a high finding is dropped from
    the registry and a problem line (the loader's own refusal
    vocabulary) is appended, so the caller treats it exactly like a
    bad manifest. Under `advisory` nothing is dropped. Under `off`
    nothing is read. `log(msg, level)` receives one line per finding
    the first time a folder is reviewed; `event_sink(event)` receives
    a security event per refusal and per shadow. Never raises on
    extension data.
    """
    mode, _problem = mode_of(cfg)
    problems = []
    if mode == "off" or not isinstance(registry, dict):
        return registry, problems, {"mode": mode, "extensions": {}}
    out = {}
    report = {}
    shipped_norm = [os.path.normcase(os.path.realpath(d)) for d in shipped_dirs
                    if isinstance(d, str) and d]
    for name in sorted(registry):
        manifest = registry[name]
        folder = manifest.get("dir") if isinstance(manifest, dict) else None
        if not isinstance(folder, str) or not folder:
            out[name] = manifest
            continue
        shipped = any(_under(folder, d) for d in shipped_norm)
        try:
            result, fresh = _cached_review(manifest, folder, shipped=shipped,
                                           shadows=shadows)
        except Exception as e:  # extension data must not abort the agent
            result = {"findings": [_finding("unreviewed", "high",
                                            f"the review failed: {e}")],
                      "capabilities": {"declared": [], "observed": {}}}
            fresh = True
        decision = verdict(result, mode)
        entry = {"kind": kind, "version": manifest.get("version"),
                 "dir": folder, "verdict": decision,
                 "findings": result["findings"],
                 "capabilities": result["capabilities"]}
        report[name] = entry
        high = [f for f in result["findings"] if f["severity"] == "high"]
        if fresh and log is not None:
            for f in result["findings"]:
                if f["severity"] == "note":
                    continue
                where = f.get("path", "")
                if f.get("line"):
                    where += f":{f['line']}"
                log(f"extension review: {kind} {name!r}: {f['code']}"
                    f"{' (' + where + ')' if where else ''}: {f['detail']}",
                    "WARN" if f["severity"] in ("high", "warn") else "INFO")
        if decision == "refused":
            summary = "; ".join(
                f"{f['code']}" + (f" ({f['path']})" if f.get("path") else "")
                for f in high[:4])
            problems.append(
                f"{kind} extension {name!r} ({folder}): refused by the "
                f"extension review: {summary}; fix the finding or set "
                f"{CONFIG_KEY} to \"advisory\" in config.json to load it "
                f"anyway")
            if fresh and event_sink is not None:
                _emit(event_sink, {
                    "type": "extension_refused", "at": _now_iso(),
                    "kind": kind, "name": name, "dir": folder,
                    "findings": [f["code"] for f in high]})
            continue
        if fresh and event_sink is not None and any(
                f["code"] == "shadow" for f in result["findings"]):
            _emit(event_sink, {
                "type": "extension_shadow", "at": _now_iso(),
                "kind": kind, "name": name, "dir": folder})
        out[name] = manifest
    full = {"mode": mode, "extensions": report}
    _record(base_dir, kind, full)
    return out, problems, full


def _emit(sink, event):
    try:
        sink(event)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

def report_path(base_dir):
    return os.path.join(base_dir, REPORT_FILE) if isinstance(base_dir, str) \
        and base_dir else ""


def _record(base_dir, kind, full):
    """Merge this kind's verdicts into <base_dir>/extension-review.json.
    Written only when they changed since the last write."""
    path = report_path(base_dir)
    if not path:
        return
    with _LOCK:
        if _LAST_REPORT.get((path, kind)) == full:
            return
        _LAST_REPORT[(path, kind)] = full
        data = load_report(base_dir) or {}   # a dict or None, never else
        data["mode"] = full.get("mode")
        data["reviewed_at"] = _now_iso()
        data[f"{kind}s"] = full.get("extensions", {})
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def last_report(base_dir, kind):
    """The verdicts `apply` last produced for this base dir and kind
    in this process (the report as data, whether or not the file
    could be written), or None."""
    with _LOCK:
        return _LAST_REPORT.get((report_path(base_dir), kind))


def load_report(base_dir):
    """The last written report, or None."""
    path = report_path(base_dir)
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
