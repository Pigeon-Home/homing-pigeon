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
import json
import os
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
        if mode not in MODES:
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


def _audit_path(base_dir):
    return os.path.join(base_dir, AUDIT_FILE)


def _enforce_bound(base_dir, max_lines):
    """Roll the audit log to .1 when it reaches the bound."""
    path = _audit_path(base_dir)
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
    """Maintain security-audit-counts.json. Best effort."""
    path = os.path.join(base_dir, COUNTS_FILE)
    try:
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
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(counts, fh)
        os.replace(tmp, path)
    except Exception:
        pass


def write_audit_entry(base_dir, feature, decision, reason,
                      key_id="", job_id="", detail="", cfg=None):
    """Append one audit entry. Best effort: never raises into the caller.

    decision is "would_deny" (audit mode) or "denied" (enforce mode).
    Only names, counts, hashes and ids go in entries -- callers must
    never pass secret values, script text, or file contents.
    """
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
        if detail:
            entry["detail"] = detail
        path = _audit_path(base_dir)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # Windows: ACLs come from the parent directory
        _bump_counts(base_dir, feature, decision)
    except Exception:
        pass


def sec_decide(cfg, base_dir, feature, reason, ctx=None):
    """The single decision point for security features.

    Returns "allow" or "deny". In audit mode the job proceeds (returns
    "allow") and a "would_deny" entry is written. In enforce mode a
    "denied" entry is written and the caller must reject through the
    existing reject path. Never raises.
    """
    mode = sec_mode(cfg, feature)
    if mode == "off":
        return "allow"
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
                          cfg=cfg)
        return "allow"
    write_audit_entry(base_dir, feature, "denied", reason,
                      key_id=key_id, job_id=job_id, detail=detail, cfg=cfg)
    return "deny"
