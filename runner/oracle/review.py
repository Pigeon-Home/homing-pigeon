#!/usr/bin/env python3
"""Oracle pre-execution review (advisory).

The Oracle inspects each job as it comes in and attaches notes about
likely failures — not policy violations (that is the judge's job),
but correctness: things that will probably make the job fail or
behave unexpectedly. The review is advisory only: the job runs
regardless, because the Oracle can be wrong. The notes travel with
the result so the failure-handling path sees what the Oracle
predicted.

Two tiers, designed for the coming transport confidentiality (v4):

- Tier "metadata" needs no content access: job shape, declared
  files, timeouts, interpreter form. It works even when job bodies
  are encrypted.
- Tier "content" reads the script text: known-failure patterns and
  static checks. Under future confidentiality it needs the decrypt
  credential the runner already holds — no new man-in-the-middle,
  the Oracle reads what the runner legitimately decrypted.

The output is an authenticated opinion, not a new signature scheme:
notes ride in the already-HMAC-signed result message, bound to the
job_id. A dedicated Oracle signing key is the v4 upgrade path.

Known failures are filed in docs/archive/known-failures.md — symptom,
cause, fix, and the pattern the reviewer matches. Every diagnosed
failure makes future reviews smarter.

This module is free of runner imports: the mail flow stays in
runner.py, which calls in here.
"""
import os
import re

try:
    from runner.guard import confval as _confval
except ImportError:
    from guard import confval as _confval  # type: ignore
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _note(pid, tier, severity, note):
    return {"id": pid, "tier": tier, "severity": severity, "note": note}


_FILENAME_RE = re.compile(
    r"""['"]([^'"]*?[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:py|sh|ps1|json|yaml|yml|toml|csv|txt|log|sql|js|ts))['"]"""
)
# Kept for the differential test in runner/tests/test_review_perf.py, which
# pins the new scan below to the old pattern's behavior.
_OLD_FILENAME_RE = _FILENAME_RE

# Bounded filename-literal scan (hardening M1a). _FILENAME_RE nests
# quantifiers over overlapping character classes, which backtracks
# catastrophically on long scripts (~29s for 160KB). The scan below
# walks quote positions exactly like the old regex engine did: at
# each quote the span runs to the next quote (either type); a span
# that fails the checks consumes nothing, so pairing is identical.
# Each span is checked in linear time.
_EXTS = ("py", "sh", "ps1", "json", "yaml", "yml", "toml", "csv", "txt",
         "log", "sql", "js", "ts")
_QUOTE_RE = re.compile(r"""['\"]""")
_NAME = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")
_NAMECHARS = _NAME | frozenset(".-")

DEFAULT_REVIEW_SCAN_BYTES = 65536


def _has_filename_tail(stem):
    r"""True iff some suffix of stem matches [A-Za-z0-9_][A-Za-z0-9_.\-]*.

    Linear reverse walk. Exactly mirrors the old regex's inner
    constraint: a name character followed only by name characters,
    dots, or dashes.
    """
    ok = True  # every char to the right is a name char
    for ch in reversed(stem):
        if ch in _NAMECHARS:
            if ch in _NAME and ok:
                return True
        else:
            ok = False
    return False


def _scan_refs(text):
    """Yield (ref, base) for quoted literals that look like filenames.

    Exactly mirrors _FILENAME_RE: at each quote the span runs to the
    next quote (either type); the span must end with a dotted
    extension from _EXTS and its stem must have a filename tail (a
    name character followed only by name characters, dots, dashes).
    A span that fails the checks consumes nothing, so quote pairing
    is identical to the old pattern.
    """
    quotes = [m.start() for m in _QUOTE_RE.finditer(text)]
    i = 0
    while i + 1 < len(quotes):
        p, q = quotes[i], quotes[i + 1]
        lit = text[p + 1:q]
        ref = None
        if lit:
            for ext in _EXTS:
                suffix = "." + ext
                if lit.endswith(suffix) \
                        and _has_filename_tail(lit[:-len(suffix)]):
                    ref = lit
                    break
        if ref is None:
            i += 1  # no match here; try the next quote
            continue
        base = ref.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        yield ref, base
        i += 2  # matched: continue after the closing quote


def parse_review_patterns(cfg):
    """Validate cfg["review_patterns_extra"]. Returns a clean list.

    Each entry: {"id": str, "pattern": regex, "note": str,
    "severity": "info"|"warn"}. Raises RuntimeError on config error.
    """
    raw = cfg.get("review_patterns_extra") or []
    if not isinstance(raw, list):
        raise RuntimeError(
            "config error: review_patterns_extra must be a list")
    out = []
    for i, p in enumerate(raw):
        where = f"config error: review_patterns_extra[{i}]"
        if not isinstance(p, dict):
            raise RuntimeError(where + " must be an object")
        pid = p.get("id") or f"extra-{i}"
        if not isinstance(pid, str) or not pid:
            raise RuntimeError(where + ".id must be a non-empty string")
        pattern = p.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise RuntimeError(where + ".pattern must be a non-empty string")
        try:
            cre = re.compile(pattern)
        except re.error as e:
            raise RuntimeError(where + f".pattern is not a valid regex: {e}")
        note = p.get("note")
        if not isinstance(note, str) or not note:
            raise RuntimeError(where + ".note must be a non-empty string")
        severity = p.get("severity", "info")
        if severity not in ("info", "warn"):
            raise RuntimeError(where + '.severity must be "info" or "warn"')
        out.append({"id": pid, "pattern": cre, "note": note,
                    "severity": severity})
    return out


def _metadata_notes(job):
    notes = []
    script = job.get("script")
    script_url = job.get("script_url")

    # M1: nothing to run.
    if not script and not script_url:
        notes.append(_note("no_script_source", "metadata", "warn",
                           "no script or script_url: nothing to run"))

    # M2/M3: unverified downloads.
    if isinstance(script_url, str) and script_url \
            and not job.get("script_sha384"):
        notes.append(_note("script_url_no_integrity", "metadata", "info",
                           "script_url without script_sha384: "
                           "download is unverified"))
    files = job.get("files") or []
    if isinstance(files, list):
        staged = set()
        for f in files:
            if not isinstance(f, dict):
                continue
            name = f.get("name")
            if isinstance(name, str):
                staged.add(name)
                # An inline file is covered by the job's own signature.
                if not f.get("sha384") and "content_b64" not in f:
                    notes.append(_note(
                        "file_no_integrity", "metadata", "info",
                        f"file {name!r} without sha384: "
                        "download is unverified"))
                # M4: absolute paths can never stage inside the work dir.
                if os.path.isabs(name):
                    notes.append(_note(
                        "absolute_file_name", "metadata", "warn",
                        f"file {name!r} is absolute: "
                        "will be rejected as an unsafe file name"))

    # M5: interpreter must be a list.
    interp = job.get("interpreter")
    if interp is not None and not isinstance(interp, list):
        notes.append(_note("interpreter_not_list", "metadata", "warn",
                           "interpreter should be a list "
                           "[executable, args...]: will be rejected"))

    # M6: shebang vs platform.
    if isinstance(script, str) and script.startswith("#!"):
        first = script.splitlines()[0]
        is_win = os.name == "nt"
        if ("/bin/bash" in first or "/bin/sh" in first) and is_win:
            notes.append(_note(
                "shebang_platform_mismatch", "metadata", "warn",
                f"shebang {first!r} on Windows: likely to fail"))
        if ("powershell" in first.lower()) and not is_win:
            notes.append(_note(
                "shebang_platform_mismatch", "metadata", "warn",
                f"shebang {first!r} on non-Windows: likely to fail"))

    # M7: timeout clamp.
    try:
        timeout = int(job.get("timeout_sec") or 0)
    except (TypeError, ValueError, OverflowError):
        timeout = 0
    if timeout > 3600:
        notes.append(_note("timeout_clamped", "metadata", "info",
                           f"timeout_sec {timeout} exceeds the 3600s "
                           "maximum: will be clamped"))
    return notes


def _review_scan_bytes(cfg):
    """Bytes of script the reviewer scans for filename references."""
    if not isinstance(cfg, dict):
        return DEFAULT_REVIEW_SCAN_BYTES
    # A boolean is not a byte count: true once scanned one byte.
    return _confval.integer(cfg.get("review_scan_bytes"),
                            DEFAULT_REVIEW_SCAN_BYTES, lo=1)


def _content_notes(job, extra_patterns, scan_bytes=None):
    notes = []
    script = job.get("script")
    if not isinstance(script, str) or not script:
        return notes

    # C1: dangling file references — string literals that look like
    # filenames but are not in the staged files list. The scan is
    # bounded; truncation is reported, never silent.
    if scan_bytes is None:
        scan_bytes = DEFAULT_REVIEW_SCAN_BYTES
    truncated = len(script) > scan_bytes
    files = job.get("files") or []
    staged = {f.get("name") for f in files
              if isinstance(f, dict) and isinstance(f.get("name"), str)}
    seen_refs = set()
    for ref, base in _scan_refs(script[:scan_bytes]):
        if base in seen_refs:
            continue
        seen_refs.add(base)
        if base not in staged and ref not in staged:
            notes.append(_note(
                "dangling_file_ref", "content", "warn",
                f"script references {ref!r} which is not in files[]: "
                "likely to fail at runtime"))
        if len(notes) >= 5:
            break
    if truncated:
        notes.append(_note(
            "review_scan_truncated", "metadata", "info",
            f"script longer than review_scan_bytes ({scan_bytes}): "
            "filename scan covered the first part only"))

    # C2: operator-defined known-failure patterns.
    for p in extra_patterns:
        if p["pattern"].search(script):
            notes.append(_note(p["id"], "content", p["severity"], p["note"]))
    return notes


def review_job(cfg, job):
    """Advisory pre-execution review. Returns {"notes", "reviewed_at"}.

    Never raises for a malformed job — a review that crashes is
    worse than no review. Config errors in review_patterns_extra
    are reported as a note, not raised.
    """
    notes = []
    try:
        notes.extend(_metadata_notes(job))
    except Exception:
        pass
    try:
        extra = parse_review_patterns(cfg)
    except RuntimeError as e:
        return {"notes": [_note("review_config_error", "metadata", "warn",
                                str(e))],
                "reviewed_at": _now_iso()}
    except Exception:
        extra = []
    try:
        notes.extend(_content_notes(job, extra, _review_scan_bytes(cfg)))
    except Exception:
        pass
    # Stable order: warns first, then by id.
    notes.sort(key=lambda n: (0 if n["severity"] == "warn" else 1, n["id"]))
    return {"notes": notes, "reviewed_at": _now_iso()}
