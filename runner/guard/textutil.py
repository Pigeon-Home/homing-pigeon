"""Text and JSON helpers shared by the runner and the modules carved
out of it.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

Stdlib only, no runner imports: runner.py and runner/wire/board.py both
import from here, and neither may import the other.
"""
import math


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
