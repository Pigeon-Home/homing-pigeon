"""Text and JSON helpers shared by the runner and the modules carved
out of it.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

Stdlib only, no runner imports: runner.py and runner/wire/board.py both
import from here, and neither may import the other.
"""
import math
import re
from datetime import datetime


def _json_safe(value, _seen=None):
    """Replace NaN and Infinity. json.dumps emits them, and they are not JSON.

    A circular object used to recurse until RecursionError. That
    retried the job forever. A repeat is null.
    """
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        if _seen is None:
            _seen = set()
        if id(value) in _seen:
            return None
        _seen.add(id(value))
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            try:
                key = k if isinstance(k, str) else str(k)
            except Exception:
                key = "key"
            out[key] = _json_safe(v, _seen)
        return out
    if isinstance(value, (list, tuple)):
        return [_json_safe(v, _seen) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_json_safe(v, _seen) for v in value]
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", "replace")
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    try:
        return str(value)
    except Exception:
        return None


def _as_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return ""


# fromisoformat before 3.11 takes a fraction of exactly 3 or 6
# digits and an offset only with its colon; 3.11 and later take any
# fraction length and "+0000". These two rewrites make the floor
# Python read issued_at the way the newest one does, so one job is
# not fresh on one box and unparseable on the next.
# (Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab)
_ISO_FRACTION_RE = re.compile(r"(:\d{2})\.(\d+)")
_ISO_OFFSET_RE = re.compile(r"([+-]\d{2})(\d{2})$")


def _fromiso(value):
    """str(value) with "Z" read as UTC -> datetime; ValueError if not ISO."""
    text = str(value).replace("Z", "+00:00")
    text = _ISO_FRACTION_RE.sub(
        lambda m: m.group(1) + "." + (m.group(2) + "000000")[:6],
        text, count=1)
    text = _ISO_OFFSET_RE.sub(r"\1:\2", text)
    return datetime.fromisoformat(text)


def _lone_surrogate(value, _depth=0):
    """True when a parsed JSON value holds an unpaired UTF-16 surrogate.

    json.loads turns the escape "\\ud800" into a str no UTF-8 encoder
    accepts, and a signed body may carry one: a JavaScript SI that
    slices through an emoji emits exactly that. Such a job cannot be
    written to disk, sized or answered, so it is refused at intake
    instead of failing (and being retried) on every poll.
    (Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab)
    """
    if _depth > 200:
        return False
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return True
        return False
    if isinstance(value, dict):
        return any(_lone_surrogate(k, _depth + 1)
                   or _lone_surrogate(v, _depth + 1)
                   for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_lone_surrogate(v, _depth + 1) for v in value)
    return False

