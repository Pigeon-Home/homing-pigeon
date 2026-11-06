#!/usr/bin/env python3
"""Optional security controls (hardening M0), on by default.

Every feature has three modes: off, audit, enforce.

- enforce: violations are rejected through the existing reject path.
  This is the default for every feature: a feature a config does not
  set runs at enforce.
- audit: the job proceeds exactly as it would with the feature off,
  but a line is written to security-audit.jsonl describing what
  enforce mode would have decided.
- off: the feature does nothing.

A mode set in config.json always wins over the default; the default
only fills in what a config leaves unset. A mode whose mechanism
cannot engage on this platform (confinement without a sandbox
backend, job_user on Windows) refuses startup at enforce rather
than running weaker than configured. Changing a mode requires a
restart: the config is read once at startup, not re-read each poll
cycle.

Python 3.9 compatible. Standard library only.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import threading
import time

try:
    from runner.guard import atomicio as _atomicio
except ImportError:
    from guard import atomicio as _atomicio  # type: ignore

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

# Tamper-evident audit chain. Every audit record carries "seq" (a
# monotonic integer, its position in the retained log counting any
# unchained legacy records before it) and "chain": the SHA-256 hex
# of the previous record's chain value (its 64 hex characters,
# utf-8) concatenated with the canonical JSON of this record
# without the "chain" field -- json.dumps with sort_keys=True,
# separators=(",", ":"), ensure_ascii=False, encoded utf-8. The
# first record of a fresh log chains from the genesis value,
# SHA-256 of the fixed label below. Rollover carries the head
# across: the first record of the new file chains from the last
# chain value of the rolled file. A log written before chaining
# existed keeps its unchained prefix: the first chained record
# carries "chain_start" naming how many unchained records precede
# it and chains from a genesis derived from that count
# (audit_chain_legacy_prev), so the legacy prefix is reported
# honestly rather than failing verification. On every write the
# chain head (seq + chain) is also recorded in the counts file
# under AUDIT_CHAIN_COUNTS_KEY, so a verifier can detect tail
# truncation while the counts file survives; without that
# checkpoint a chain alone proves integrity only to the end of
# the file. Verification lives in runner.ops.auditreport
# (verify_audit_chain, --audit-verify).
AUDIT_CHAIN_GENESIS_LABEL = b"homing-pigeon security audit chain v1"
AUDIT_CHAIN_GENESIS = hashlib.sha256(AUDIT_CHAIN_GENESIS_LABEL).hexdigest()
AUDIT_CHAIN_COUNTS_KEY = "_audit_chain"


def audit_chain_canonical(record) -> bytes:
    """The canonical bytes a record's chain value covers: the
    record without its "chain" field, as pinned above."""
    body = {k: v for k, v in record.items() if k != "chain"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def audit_chain_next(prev_chain, record) -> str:
    """The chain value for `record` following `prev_chain`."""
    return hashlib.sha256(
        prev_chain.encode("utf-8") + audit_chain_canonical(record)
    ).hexdigest()


def audit_chain_legacy_prev(legacy_count) -> str:
    """The prev value the first chained record after an unchained
    legacy prefix of `legacy_count` records chains from."""
    label = ("homing-pigeon security audit chain v1 legacy start "
             "after %d unchained records" % legacy_count)
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


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


KEY_ID_LABEL = b"homing-pigeon key id v1\n"


def key_fingerprint(secret) -> str:
    """The name a secret carries by default (Q94): `k-` and the first
    eight hex digits of SHA-384 over a fixed label and the secret.

    Anyone holding the secret can compute it, so a sender always has
    a name to give and a runner always has one to list; nothing else
    the key derives (the HMAC over a body, the HKDF of the job key)
    starts from this hash, the label sees to that, and eight hex
    digits of a one-way function over 256 random bits give an
    attacker nothing a signed message does not already (a signed
    message is an oracle for a guessed secret as it is). The name
    is public by design, like a user name; the secret is not.
    """
    if not isinstance(secret, str):
        raise TypeError("secret must be a string")
    digest = hashlib.sha384(KEY_ID_LABEL + secret.encode("utf-8")).hexdigest()
    return "k-" + digest[:8]


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


# ---- a peer's regular expression, before it runs against text the
# same peer wrote (Q84)

try:
    _rx = importlib.import_module("re._parser")   # Python 3.11+
except ImportError:  # 3.9 and 3.10
    _rx = importlib.import_module("sre_parse")

_RX_REPEATS = tuple(
    op for op in (getattr(_rx, name, None)
                  for name in ("MAX_REPEAT", "MIN_REPEAT",
                               "POSSESSIVE_REPEAT"))
    if op is not None)
_RX_GROUPS = tuple(
    op for op in (getattr(_rx, name, None)
                  for name in ("SUBPATTERN", "ATOMIC_GROUP", "ASSERT",
                               "ASSERT_NOT", "GROUPREF_EXISTS"))
    if op is not None)


def _rx_subpatterns(op, av):
    """The subpatterns one parsed item holds, whatever its shape."""
    if op in _RX_REPEATS:
        return [av[2]]
    if op == _rx.BRANCH:
        return list(av[1])
    if op == _rx.GROUPREF_EXISTS:
        return [p for p in av[1:] if p is not None]
    if op in _RX_GROUPS:
        return [av[-1]] if isinstance(av, tuple) else [av]
    return []


def _rx_walk(items, under_repeat):
    """The first reason the parsed pattern can take exponential time,
    or None. `under_repeat` says an enclosing repeat can iterate."""
    for op, av in items:
        if op in _RX_REPEATS:
            iterates = av[1] != 1
            if under_repeat and iterates:
                return "nested repeat"
            found = _rx_walk(av[2], under_repeat or iterates)
            if found:
                return found
        elif op == _rx.BRANCH:
            if under_repeat:
                return "repeated alternation"
            for sub in av[1]:
                found = _rx_walk(sub, under_repeat)
                if found:
                    return found
        else:
            for sub in _rx_subpatterns(op, av):
                found = _rx_walk(sub, under_repeat)
                if found:
                    return found
    return None


def regex_backtracks(pattern) -> str | None:
    """Why a pattern that compiles may still take exponential time on
    text its sender chose, or None when its shape cannot: a repeat
    nested in a repeat that iterates (`(a+)+`, `(\\w+\\s?)*`,
    `(?:a{1,3}){2,}`) or an alternation under one (`(a|aa)+`). Each
    such shape lets the engine split the same text in exponentially
    many ways before it gives up; the plain repeats that remain are
    bounded by the length of the text they run over. A pattern that
    does not parse answers None: the compile step before this one
    is what refuses it."""
    if not isinstance(pattern, str):
        return None
    try:
        parsed = _rx.parse(pattern)
    except Exception:
        return None
    return _rx_walk(parsed, False)


def sec_mode(cfg, feature):
    """Return the effective mode for a feature: off, audit, or enforce.

    A mode set in the config is returned exactly as set. A feature
    the config does not set reads as enforce: the controls are on by
    default, so an absent "security" block, a null one, an empty one,
    and a partial modes block all mean the same thing -- everything
    unset is enforced. Malformed shapes read as off instead: a
    security value, modes value, or mode value of the wrong shape
    never widens enforcement, and validate_security_config refuses
    those same shapes at startup, naming the key.
    """
    if not isinstance(cfg, dict):
        return "off"
    if "security" not in cfg or cfg["security"] is None:
        return "enforce"
    sec = cfg["security"]
    if not isinstance(sec, dict):
        return "off"
    if "modes" not in sec:
        return "enforce"
    modes = sec["modes"]
    if not isinstance(modes, dict):
        return "off"
    if feature not in modes:
        return "enforce"
    mode = modes[feature]
    return mode if mode in MODES else "off"


def effective_modes(cfg):
    """The effective mode of every feature, defaults filled in.

    The posture surface reports this map so the modes in force are
    stated outright, never guessed from which keys a config happens
    to carry.
    """
    return {feature: sec_mode(cfg, feature) for feature in FEATURES}


def require_posture_enabled(cfg):
    """True when the operator pinned the startup posture assertion.

    The flat key wins when present -- the CLI override writes it
    (--require-posture / --no-require-posture), and a flag beats the
    file -- then security.require_posture in the config block. Only
    boolean True pins it; validate_security_config refuses any other
    shape in the block at startup, naming the key.
    """
    if not isinstance(cfg, dict):
        return False
    if "require_posture" in cfg:
        return cfg["require_posture"] is True
    sec = cfg.get("security")
    if isinstance(sec, dict):
        return sec.get("require_posture") is True
    return False


def lowered_features(cfg):
    """The features whose effective mode sits below enforce,
    in FEATURES order."""
    return [feature for feature in FEATURES
            if sec_mode(cfg, feature) != "enforce"]


def require_posture_problem(cfg):
    """Why a require-posture-pinned startup must refuse, or None.

    None when the assertion is unpinned (the default, and startup
    behavior is exactly as it was) and None when every feature is
    at enforce. Otherwise one sentence naming each lowered feature
    and its mode, so the refusal itself says what to raise.
    """
    if not require_posture_enabled(cfg):
        return None
    lowered = lowered_features(cfg)
    if not lowered:
        return None
    return ("require_posture is pinned but security mode(s) sit "
            "below enforce: "
            + ", ".join("%s=%s" % (feature, sec_mode(cfg, feature))
                        for feature in lowered)
            + ". Refusing to start; raise the mode(s) to enforce, "
            "or unset require_posture.")


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
    every feature takes its default (enforce). Call at startup,
    before any job runs.
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
    require_posture = sec.get("require_posture")
    if require_posture is not None \
            and not isinstance(require_posture, bool):
        raise RuntimeError(
            "config error: security.require_posture must be a boolean "
            "(got %r)" % (require_posture,))
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


def _audit_last_line(path):
    """The last non-empty line of a file, as bytes, or None.

    A symlink is not followed. Reads backwards from the end, so
    the common case costs one small chunk, not a full scan.
    """
    if os.path.islink(path):
        return None
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            pos = fh.tell()
            if pos == 0:
                return None
            buf = b""
            while pos > 0:
                step = min(65536, pos)
                pos -= step
                fh.seek(pos)
                buf = fh.read(step) + buf
                body = buf.rstrip(b"\r\n")
                if b"\n" in body or pos == 0:
                    lines = [ln for ln in body.split(b"\n") if ln.strip()]
                    return lines[-1] if lines else None
            return None
    except OSError:
        return None


def _audit_line_count(path):
    """Non-empty lines in a file. A symlink is not followed."""
    if os.path.islink(path):
        return 0
    try:
        with open(path, "rb") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError:
        return 0


def _audit_chain_state(base_dir):
    """(prev_chain, next_seq, chain_start) for the next record.

    chain_start is None except at a legacy transition: the number
    of unchained records already in the retained log, recorded on
    the first chained record so a verifier can reproduce its prev
    value. The tail record decides: the live file first, then the
    rolled file the moment after a rollover, when the live file
    does not exist yet and the head must carry across.
    """
    live = _audit_path(base_dir)
    rolled = os.path.join(base_dir, AUDIT_ROLLED_FILE)
    for path in (live, rolled):
        line = _audit_last_line(path)
        if line is None:
            continue
        try:
            rec = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            rec = None
        if isinstance(rec, dict) and isinstance(rec.get("chain"), str) \
                and isinstance(rec.get("seq"), int) \
                and not isinstance(rec.get("seq"), bool):
            return rec["chain"], rec["seq"] + 1, None
        # An unchained tail: the chain starts after every retained
        # unchained record. This full count runs once, at the
        # transition; chained tails take the tail-read path above.
        legacy = _audit_line_count(rolled) + _audit_line_count(live)
        return audit_chain_legacy_prev(legacy), legacy + 1, legacy
    return AUDIT_CHAIN_GENESIS, 1, None


def _record_chain_head_locked(base_dir, seq, chain):
    """Record the chain head in the counts file. Best effort.

    Same shape as _bump_counts_locked: a symlink at the counts
    path is not read, and the write goes through the atomic
    writer. The lock is the caller's (the entry writer's).
    """
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
        counts[AUDIT_CHAIN_COUNTS_KEY] = {"seq": seq, "chain": chain}
        _atomicio.write_json(path, counts)
    except Exception:
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
        _atomicio.write_json(path, counts)
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
        prev_chain, seq, chain_start = _audit_chain_state(base_dir)
        entry["seq"] = seq
        if chain_start is not None:
            entry["chain_start"] = chain_start
        entry["chain"] = audit_chain_next(prev_chain, entry)
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
        _record_chain_head_locked(base_dir, seq, entry["chain"])
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
