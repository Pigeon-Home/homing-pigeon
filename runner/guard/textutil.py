"""Text and JSON helpers shared by the runner and the modules carved
out of it.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

Stdlib only, no runner imports: runner.py and runner/wire/board.py both
import from here, and neither may import the other.
"""
import json
import math
import re
from datetime import datetime


def _json_safe(value, _seen=None):
    """Replace NaN and Infinity. json.dumps emits them, and they are not JSON.

    A circular object used to recurse until RecursionError. That
    retried the job forever. A cycle is null. An object that merely
    appears twice, under two keys or twice in a list, is written
    twice, which is how JSON reads it back.
    """
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        if _seen is None:
            _seen = set()
        if id(value) in _seen:
            return None
        _seen.add(id(value))
        try:
            if isinstance(value, dict):
                out = {}
                for k, v in value.items():
                    try:
                        key = k if isinstance(k, str) else str(k)
                    except Exception:
                        key = "key"
                    out[key] = _json_safe(v, _seen)
                return out
            return [_json_safe(v, _seen) for v in value]
        finally:
            _seen.discard(id(value))
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


NESTING_LIMIT = 200


def _no_constant(name):
    """json.loads' parse_constant for a signed body: NaN, Infinity
    and -Infinity are Python's extensions, not JSON (RFC 8259), and
    a number the reader cannot carry."""
    raise ValueError(f"signed body carries {name}, which is not JSON")


def _finite_float(text):
    """json.loads' parse_float for a signed body: a number too large
    for a float (1e400 is valid syntax) reads as infinity, which the
    reader cannot carry."""
    value = float(text)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("signed body carries a number that is not finite")
    return value


def _no_duplicate_names(pairs):
    """json.loads' object_pairs_hook for a signed body: a member
    name carried twice in one object is refused, naming the name.
    Without the hook the parser keeps the last value, so two
    readers of one body can disagree about what a name carries --
    a parser differential at a security boundary. The hook sees
    the decoded name, so an escaped spelling of a name already
    present is the same duplicate."""
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("signed body carries duplicate member "
                             f"name {key!r}")
        out[key] = value
    return out


def _check_nesting_first(text):
    """Refuse a signed body whose raw bracket depth passes
    NESTING_LIMIT, before json.loads runs. The bound used to be
    measured only on the parsed value, after the parser had
    already recursed as deep as the body asked; counting first
    means the parser never recurses past the bound. Brackets
    inside a string are text, not containers, and an escaped
    quote does not end the string."""
    if isinstance(text, (bytes, bytearray)):
        text = bytes(text).decode("utf-8", "replace")
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            depth += 1
            if depth > NESTING_LIMIT:
                raise ValueError(
                    f"signed body nests deeper than {NESTING_LIMIT} "
                    "levels")
        elif char in "}]":
            depth -= 1


def loads_signed(text):
    """json.loads for the text of a signed body: the literals NaN and
    Infinity and a number that overflows a float are refused with a
    ValueError that names them, so a body trusts nothing a JSON
    reader elsewhere would not read the same way (Q89). A body the
    parser cannot finish is refused as nested past the bound. A
    duplicate member name in one object is refused, and the raw
    bracket depth is scanned before the parse so a body nested
    past the bound is refused without the parser recursing there
    first."""
    _check_nesting_first(text)
    try:
        return json.loads(text, parse_constant=_no_constant,
                          parse_float=_finite_float,
                          object_pairs_hook=_no_duplicate_names)
    except RecursionError:
        # The parser gave up before the measure below could run: a
        # body it cannot finish is past the bound by any count.
        raise ValueError(f"signed body nests deeper than {NESTING_LIMIT} "
                         "levels") from None


def _nests_deeper_than(value, limit=NESTING_LIMIT):
    """True when a parsed JSON value holds a container more than
    `limit` levels down (the root object is level 1). Counted with
    a stack, not recursion, so a body of any depth is measured
    without a RecursionError; the walks that follow (the lone
    surrogate's, the signer's) are bounded by the same limit."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, dict):
            kids = item.values()
        elif isinstance(item, (list, tuple)):
            kids = item
        else:
            continue
        if depth > limit:
            return True
        for kid in kids:
            if isinstance(kid, (dict, list, tuple)):
                stack.append((kid, depth + 1))
    return False


def _lone_surrogate(value, _depth=0):
    """True when a parsed JSON value holds an unpaired UTF-16 surrogate.

    json.loads turns the escape "\\ud800" into a str no UTF-8 encoder
    accepts, and a signed body may carry one: a JavaScript SI that
    slices through an emoji emits exactly that. Such a job cannot be
    written to disk, sized or answered, so it is refused at intake
    instead of failing (and being retried) on every poll.
    (Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab)
    """
    if _depth > NESTING_LIMIT:
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

