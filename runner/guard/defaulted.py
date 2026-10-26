"""Which present settings read as their documented default.

Decision 1 (docs/design/present-but-invalid-config.md): an unusable
value reads as the documented default, and the runner says so
instead of doing it silently. This module is the one place that
knows which top-level settings are default-class and what usable
means for each; the startup line, the full platform card and the
live reload all ask it.

stdlib only; no I/O. The table mirrors the numeric and enum rows of
runner/tests/defaults_registry.py (a test keeps them in step).
"""
import math

# key -> (default, lo, hi); None bound = open. Values are read by
# confval.number/integer: numeric strings are usable, bools, null,
# non-numeric strings, non-finite and out-of-range numbers are not.
NUMERIC = {
    "task_timeout": (86400, 0, None),
    "default_timeout_sec": (300, 1, None),
    "max_job_age_sec": (3600, 1, None),
    "max_plan_steps": (8, 1, None),
    "max_plan_timeout_sec": (600, 1, None),
    "oracle_learning_promote_after": (2, 1, None),
    "review_scan_bytes": (65536, 1, None),
    "output_retention_days": (7, -1000000000, 1000000000),
    "v2_answer_deadline_sec": (0, None, None),
    "query_budget": (8, None, None),
    "max_query_budget": (8, None, None),
    "local_wake_cooldown_sec": (900, 0, None),
    "max_output_bytes": (100000, 1, None),
    "agent_wall_clock_sec": (300, 1, None),
    "poll_interval_sec": (20, 0, None),
    "result_stash_retention_sec": (86400, 1, None),
    "result_resend_backoff_sec": (60, 1, None),
}
ENUM = {
    "dtls_greeting": ("family", ("none", "family", "standard", "full")),
}


def _parse(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for conv in (int, float):
            try:
                return conv(text)
            except ValueError:
                pass
    return None


def _usable_number(value, lo, hi):
    n = _parse(value)
    if n is None:
        return False
    try:
        f = float(n)
    except (OverflowError, ValueError):
        return False
    if math.isnan(f) or math.isinf(f):
        return False
    return not ((lo is not None and f < lo) or (hi is not None and f > hi))


def default_for(key):
    """The documented default of a default-class key, or None."""
    if key in NUMERIC:
        return NUMERIC[key][0]
    if key in ENUM:
        return ENUM[key][0]
    return None


def is_defaulted(key, value):
    """True when `key` is present with an unusable value.

    Absent (None) is simply unset, not defaulted: the owner wrote
    nothing unusable.
    """
    if value is None:
        return False
    if key in NUMERIC:
        _d, lo, hi = NUMERIC[key]
        return not _usable_number(value, lo, hi)
    if key in ENUM:
        return not (isinstance(value, str) and value in ENUM[key][1])
    return False


def defaulted_keys(cfg):
    """Sorted names of the settings in cfg that read as their default."""
    if not isinstance(cfg, dict):
        return []
    return sorted(k for k in list(NUMERIC) + list(ENUM)
                  if k in cfg and is_defaulted(k, cfg.get(k)))


def summary_line(keys):
    """The startup line, or None when nothing defaulted."""
    if not keys:
        return None
    n = len(keys)
    noun = "setting" if n == 1 else "settings"
    return f"config: {n} {noun} read as their default: {', '.join(keys)}"
