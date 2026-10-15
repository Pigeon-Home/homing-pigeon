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

Known failures are filed in docs/known-failures.md — symptom,
cause, fix, and the pattern the reviewer matches. Every diagnosed
failure makes future reviews smarter.

This module is free of runner imports: the mail flow stays in
runner.py, which calls in here.
"""
import os
import re
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _note(pid, tier, severity, note):
    return {"id": pid, "tier": tier, "severity": severity, "note": note}


_FILENAME_RE = re.compile(
    r"""['"]([^'"]*?[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:py|sh|ps1|json|yaml|yml|toml|csv|txt|log|sql|js|ts))['"]"""
)


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
                if not f.get("sha384"):
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
    except (TypeError, ValueError):
        timeout = 0
    if timeout > 3600:
        notes.append(_note("timeout_clamped", "metadata", "info",
                           f"timeout_sec {timeout} exceeds the 3600s "
                           "maximum: will be clamped"))
    return notes


def _content_notes(job, extra_patterns):
    notes = []
    script = job.get("script")
    if not isinstance(script, str) or not script:
        return notes

    # C1: dangling file references — string literals that look like
    # filenames but are not in the staged files list.
    files = job.get("files") or []
    staged = {f.get("name") for f in files
              if isinstance(f, dict) and isinstance(f.get("name"), str)}
    seen_refs = set()
    for m in _FILENAME_RE.finditer(script):
        ref = m.group(1)
        base = ref.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
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
        notes.extend(_content_notes(job, extra))
    except Exception:
        pass
    # Stable order: warns first, then by id.
    notes.sort(key=lambda n: (0 if n["severity"] == "warn" else 1, n["id"]))
    return {"notes": notes, "reviewed_at": _now_iso()}
