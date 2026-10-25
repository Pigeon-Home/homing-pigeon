#!/usr/bin/env python3
"""Optional, off-by-default security controls (hardening M0).

Every feature has three modes: off, audit, enforce.

- off: the feature does nothing. This is the default for everything.
- audit: the job proceeds exactly as it would with the feature off,
  but a line is written to security-audit.jsonl describing what
  enforce mode would have decided.
- enforce: violations are rejected through the existing reject path.

With no "security" block in config.json the runner behaves exactly
as before. Changing a mode requires a restart: the config is read
once at startup, not re-read each poll cycle.

Python 3.9 compatible. Standard library only.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time

MODES = ("off", "audit", "enforce")

# Features recognized in security.modes. Entries are added as their
# milestone lands; the whole list is accepted from the start so
# config files do not break between milestones.
FEATURES = (
    "policy_env",    # M2: env constraints for pinned keys
    "policy_files",  # M2: file constraints for pinned keys
    "policy_args",   # M2: arg constraints for pinned keys
    "audience",      # M5: audience binding
    "confinement",   # M6: Linux sandbox
    "job_user",      # M8: run jobs as another user
)

DEFAULT_AUDIT_MAX_LINES = 20000
AUDIT_FILE = "security-audit.jsonl"
AUDIT_ROLLED_FILE = "security-audit.jsonl.1"
COUNTS_FILE = "security-audit-counts.json"


# Hardening M2: env names that subvert execution even when the script
# itself is pinned. Compared case-insensitively everywhere (Windows env
# is case-insensitive; on POSIX the uppercase form is the dangerous one,
# and matching it case-insensitively errs toward safety — stricter than
# the plan's case-sensitive-outside-Windows rule, kept deliberately).
# Appendix A of the hardening plan. Prefixes cover the plan's DYLD_* and
# GIT_CONFIG_* wildcards.
DANGEROUS_ENV_NAMES = frozenset({
    # Shell startup files and shell behavior: executed automatically
    # by sh/bash/ksh, or alter parsing of every command.
    "BASH_ENV",
    "ENV",
    "PATH",
    "IFS",
    "SHELLOPTS",
    "BASHOPTS",
    "PS4",
    "PROMPT_COMMAND",
    # Dynamic linker: hijack library loading for any subprocess.
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "LD_AUDIT",
    # Interpreters: auto-executed startup code / module injection.
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONUSERBASE",
    "PERL5LIB",
    "PERL5OPT",
    "PERLLIB",
    "RUBYLIB",
    "RUBYOPT",
    "NODE_OPTIONS",
    "NODE_PATH",
    # JVM: agent injection on every java invocation.
    "JAVA_TOOL_OPTIONS",
    "_JAVA_OPTIONS",
    "CLASSPATH",
    # Tool behavior: command substitution on invocation.
    "GIT_SSH",
    "GIT_SSH_COMMAND",
    "GIT_EXEC_PATH",
    # Windows: command interpreter and module search hijack.
    "COMSPEC",
    "PATHEXT",
    "PSModulePath",
})
DANGEROUS_ENV_PREFIXES = frozenset({
    "DYLD_",
    "GIT_CONFIG_",
})


def is_dangerous_env_name(name) -> bool:
    """True if the env name can subvert execution (plan Appendix A).

    Case-insensitive everywhere: stricter than the plan, deliberate.
    """
    if not isinstance(name, str) or not name:
        return False
    upper = name.upper()
    if upper in DANGEROUS_ENV_NAMES:
        return True
    return any(upper.startswith(p) for p in DANGEROUS_ENV_PREFIXES)


def _estimate_secret_entropy(secret: str) -> float:
    """Rough entropy estimate in bits: length x log2(alphabet size)."""
    if not isinstance(secret, str) or not secret:
        return 0.0
    alphabet = len(set(secret))
    if alphabet <= 1:
        return 0.0
    return len(secret) * math.log2(alphabet)


def _secret_pattern_reason(secret: str) -> str | None:
    """Return a reason if the secret looks hand-patterned, else None.

    The length x log2(alphabet) estimate overrates patterned strings: a
    104-char string cycling a-z estimates at ~490 bits while having
    negligible real entropy. Randomly generated secrets (token_hex,
    token_urlsafe) never trigger this.
    """
    if not isinstance(secret, str):
        return "secret must be a string"
    low = secret.lower()
    placeholders = ("generate", "changeme", "example", "placeholder",
                    "your-secret", "your_secret", "todo", "xxx")
    if any(p in low for p in placeholders):
        return "it looks like an example placeholder value"
    # Fully periodic: the whole string is repeats of a shorter unit
    # ("abcabc...", "passwordpassword", "aaaa...").
    n = len(secret)
    for period in range(1, n // 2 + 1):
        unit = secret[:period]
        if secret == (unit * ((n // period) + 1))[:n]:
            return f"it repeats the {period}-character unit {unit!r}"
    return None


def validate_shared_secret(secret: str) -> None:
    """Refuse to start on a missing or weak shared secret.

    Anyone holding one signed message can brute-force the HMAC key
    offline, so the secret needs real entropy. Raises RuntimeError with
    generation guidance when the secret is missing or too weak.
    """
    hint = ("generate one with: openssl rand -hex 32  "
            "or: python3 -c \"import secrets; print(secrets.token_hex(32))\"")
    if not secret:
        raise RuntimeError(
            "config error: shared_secret is required (a dedicated high-entropy "
            f"secret, separate from the mailbox password). {hint}")
    reason = _secret_pattern_reason(secret)
    if reason is not None:
        raise RuntimeError(
            f"config error: shared_secret is too weak ({reason}). {hint}")
    # Estimated entropy: length x log2(alphabet size). A 64-char hex
    # string (the recommended shape) estimates at 256 bits.
    bits = _estimate_secret_entropy(secret)
    if bits < 128:
        raise RuntimeError(
            f"config error: shared_secret is too weak (~{bits:.0f} bits estimated, "
            f"need at least 128). {hint}")


def sec_mode(cfg, feature):
    """Return the mode for a feature: off, audit, or enforce.

    Anything missing or malformed reads as off. Malformed config is
    rejected at startup by validate_security_config; this stays
    defensive so a bad value can never silently enable enforcement.
    """
    sec = cfg.get("security") if isinstance(cfg, dict) else None
    if not isinstance(sec, dict):
        return "off"
    modes = sec.get("modes")
    if not isinstance(modes, dict):
        return "off"
    mode = modes.get(feature, "off")
    return mode if mode in MODES else "off"


def audit_max_lines(cfg):
    """Bound for the audit log. Default 20000."""
    sec = cfg.get("security") if isinstance(cfg, dict) else None
    if not isinstance(sec, dict):
        return DEFAULT_AUDIT_MAX_LINES
    n = sec.get("audit_max_lines", DEFAULT_AUDIT_MAX_LINES)
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        return DEFAULT_AUDIT_MAX_LINES
    return n


def validate_security_config(cfg):
    """Raise RuntimeError for a malformed security block.

    Names the key and the bad value. A missing block is fine:
    everything stays off. Call at startup, before any job runs.
    """
    if not isinstance(cfg, dict):
        return
    sec = cfg.get("security")
    if sec is None:
        return
    if not isinstance(sec, dict):
        raise RuntimeError(
            "config error: security must be an object, got %s"
            % type(sec).__name__)
    modes = sec.get("modes", {})
    if not isinstance(modes, dict):
        raise RuntimeError(
            "config error: security.modes must be an object, got %s"
            % type(modes).__name__)
    for name, mode in modes.items():
        if name not in FEATURES:
            raise RuntimeError(
                "config error: security.modes.%s is not a known feature"
                % (name,))
        if not isinstance(mode, str) or mode not in MODES:
            raise RuntimeError(
                "config error: security.modes.%s must be one of off, audit, "
                "enforce (got %r)" % (name, mode))
    max_lines = sec.get("audit_max_lines", DEFAULT_AUDIT_MAX_LINES)
    if isinstance(max_lines, bool) or not isinstance(max_lines, int):
        raise RuntimeError(
            "config error: security.audit_max_lines must be an integer "
            "(got %r)" % (max_lines,))
    if max_lines < 1:
        raise RuntimeError(
            "config error: security.audit_max_lines must be at least 1 "
            "(got %r)" % (max_lines,))
    # Hardening M6: validate the confinement block. The sandbox module
    # owns the schema; import lazily to avoid a cycle.
    if "confinement" in sec:
        try:
            from runner.guard import sandbox as _sandbox
        except ImportError:
            try:
                from guard import sandbox as _sandbox
            except ImportError:
                _sandbox = None
        if _sandbox is not None:
            _sandbox._validate_confinement_block(sec["confinement"])
    # Hardening M8: validate the job_user block.
    if "job_user" in sec:
        ju = sec["job_user"]
        if not isinstance(ju, dict) or not isinstance(ju.get("user"), str) \
                or not ju["user"]:
            raise RuntimeError(
                "config error: security.job_user must be an object with "
                "a non-empty string 'user' (got %r)" % (ju,))
        user = ju["user"]
        if any(c in user for c in "/\\\x00:\n\r \t"):
            raise RuntimeError(
                "config error: security.job_user.user %r is not a "
                "username" % (user,))
        if os.name != "nt":
            try:
                import pwd
            except ImportError:
                pwd = None
            if pwd is not None:
                try:
                    pwd.getpwnam(user)
                except (KeyError, ValueError):
                    raise RuntimeError(
                        "config error: security.job_user.user %r does "
                        "not exist" % (user,))


def _audit_path(base_dir):
    return os.path.join(base_dir, AUDIT_FILE)


# One audit writer at a time per process. Appends go through
# O_APPEND, which is one atomic write on POSIX but not on Windows,
# where the C runtime seeks to the end and then writes: two job
# threads (workers > 1) denied in the same moment overwrote each
# other's entry there (switch-proofs, R2, the Windows leg,
# 2026-10-25). The bound's count-then-roll and the counts file's
# read-modify-write raced on every platform: two threads that both
# counted the bound could rename a fresh one-line log over the
# rolled ten-line one. Two runner processes never share a base dir,
# so a process-wide lock is the whole fix; re-entrant because the
# entry writer also bumps the counts.
_AUDIT_LOCK = threading.RLock()


def _enforce_bound(base_dir, max_lines):
    """Roll the audit log to .1 when it reaches the bound.

    A symlink is not followed. Rolling renames the name, it does not
    read or rewrite the target.
    """
    path = _audit_path(base_dir)
    if os.path.islink(path):
        return
    try:
        with open(path, "rb") as fh:
            count = sum(1 for _ in fh)
    except OSError:
        return
    if count >= max_lines:
        try:
            os.replace(path, os.path.join(base_dir, AUDIT_ROLLED_FILE))
        except OSError:
            pass


def _bump_counts(base_dir, feature, decision):
    """Maintain security-audit-counts.json. Best effort.

    The temp name is created with O_EXCL | O_NOFOLLOW. A symlink at
    the counts path is replaced, not written through, and its old
    contents are not used.
    """
    if not isinstance(base_dir, str) or not base_dir:
        return
    with _AUDIT_LOCK:
        _bump_counts_locked(base_dir, feature, decision)


def _bump_counts_locked(base_dir, feature, decision):
    try:
        path = os.path.join(base_dir, COUNTS_FILE)
        counts = {}
        if not os.path.islink(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    counts = json.load(fh)
            except (OSError, ValueError):
                counts = {}
        if not isinstance(counts, dict):
            counts = {}
        feat = counts.get(feature)
        if not isinstance(feat, dict):
            feat = {}
            counts[feature] = feat
        feat[decision] = int(feat.get(decision) or 0) + 1
        tmp = path + ".tmp." + str(os.getpid())
        fd = None
        try:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(tmp, flags, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fd = None
                json.dump(counts, fh)
            os.replace(tmp, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
    except Exception:
        pass


def bump_evaluated(base_dir, feature):
    """Count one evaluation of a security feature. Best effort.

    Called by each feature's evaluation point when the feature is not
    off, so --audit-report can show "jobs evaluated" per feature.
    """
    _bump_counts(base_dir, feature, "evaluated")


def write_audit_entry(base_dir, feature, decision, reason,
                      key_id="", job_id="", detail="", cfg=None,
                      mode=None):
    """Append one audit entry. Best effort: never raises into the caller.

    decision is "would_deny" (audit mode) or "denied" (enforce mode).
    mode is the feature's mode ("audit"/"enforce") at decision time,
    recorded so --audit-report can show it per entry.
    Only names, counts, hashes and ids go in entries -- callers must
    never pass secret values, script text, or file contents.
    """
    if not isinstance(base_dir, str) or not base_dir:
        return
    with _AUDIT_LOCK:
        _write_audit_entry_locked(base_dir, feature, decision, reason,
                                  key_id, job_id, detail, cfg, mode)


def _write_audit_entry_locked(base_dir, feature, decision, reason,
                              key_id, job_id, detail, cfg, mode):
    try:
        max_lines = audit_max_lines(cfg or {})
        _enforce_bound(base_dir, max_lines)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "feature": feature,
            "decision": decision,
            "reason": reason,
            "key_id": key_id,
            "job_id": job_id,
        }
        if mode:
            entry["mode"] = mode
        if detail:
            try:
                if not isinstance(detail, str):
                    detail = str(detail)
            except Exception:
                detail = ""
            if detail:
                entry["detail"] = detail
        path = _audit_path(base_dir)
        line = (json.dumps(entry) + "\n").encode("utf-8")
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
            try:
                if os.path.exists(path) and not os.path.islink(path):
                    os.chmod(path, 0o600)
            except OSError:
                pass
        _bump_counts(base_dir, feature, decision)
    except Exception:
        pass


def sec_decide(cfg, base_dir, feature, reason, ctx=None):
    """The single decision point for security features.

    Returns True when the message may proceed, False when it must be
    rejected. In audit mode the job proceeds (returns True) and a
    "would_deny" entry is written. In enforce mode a "denied" entry is
    written and the caller must reject through the existing reject
    path. Never raises.
    """
    mode = sec_mode(cfg, feature)
    if mode == "off":
        return True
    ctx = ctx if isinstance(ctx, dict) else {}
    # Audit entries carry identifiers only, never secrets. Coerce
    # defensively; a hostile __str__ must not break the poll loop.
    try:
        key_id = str(ctx.get("key_id", ""))
        job_id = str(ctx.get("job_id", ""))
        detail = str(ctx.get("detail", ""))
    except Exception:
        key_id, job_id, detail = "", "", ""
    if mode == "audit":
        write_audit_entry(base_dir, feature, "would_deny", reason,
                          key_id=key_id, job_id=job_id, detail=detail,
                          cfg=cfg, mode=mode)
        return True
    write_audit_entry(base_dir, feature, "denied", reason,
                      key_id=key_id, job_id=job_id, detail=detail, cfg=cfg,
                      mode=mode)
    return False
