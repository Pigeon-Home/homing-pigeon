#!/usr/bin/env python3
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
"""Typed readers for config and job values. One answer to one question.

The VM campaign of 2026-10-22/23 found fifty-six places where a
documented default was promised and the code delivered something
else when the key was present but not a sane number
(tests/test_doc_default_divergences.py). Three shapes covered
fifty of them:

- JSON ``true``/``false`` read as 1 and 0, because ``bool`` is an
  ``int`` in Python and ``int(True)`` is 1. A poll interval of
  ``true`` polled every second; a port of ``false`` was port 0.
- A huge integer (a JSON number with hundreds of digits), ``inf``
  or ``NaN`` reached ``time.sleep``, ``range`` or ``int()`` and
  escaped as OverflowError or ValueError, killing the loop or the
  extension that read it.
- A key present as ``null`` or a non-numeric string was used as
  is, because ``cfg.get(key, default)`` only defaults when the key
  is absent. A ``null`` task timeout wedged claimed tasks forever.

These readers answer "is this a usable number, and if not what do
I use instead" in one place. They never raise on the value. A
boolean is never a number here. A number must be finite. ``lo``
and ``hi`` bound what counts as usable; a value outside them is
not clamped, it is unusable, because the documented default is
what the docs promise for anything that is not a usable value.
Where a module documents a config error instead of a default,
``is_number`` is the gate and the module raises its own error.

Stdlib only, no runner imports, so the transport extensions and
the readers that must stay import-free can share it.
"""

import math

_INF = float("inf")


def is_number(value, lo=None, hi=None):
    """True for a finite int or float (never a bool) within [lo, hi]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        f = float(value)
    except (OverflowError, ValueError):
        return False
    if math.isnan(f) or f in (_INF, -_INF):
        return False
    if lo is not None and f < lo:
        return False
    if hi is not None and f > hi:
        return False
    return True


def _parse(value):
    """A number from a value, or None. Strings are parsed; bools never."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            pass
        try:
            return float(text)
        except ValueError:
            return None
    return None


def number(value, default, lo=None, hi=None, strings=True):
    """A finite number from a config or job value, or ``default``.

    ``strings`` lets a numeric string through (config files written
    by hand often carry "20"); set it False where only a JSON number
    is acceptable. Anything else -- a bool, None, a non-numeric
    string, a non-finite float, an integer too large for a float,
    or a value outside [lo, hi] -- is ``default``.
    """
    n = value if isinstance(value, (int, float)) else (
        _parse(value) if strings else None)
    if n is None or not is_number(n, lo, hi):
        return default
    return n


def integer(value, default, lo=None, hi=None, strings=True):
    """``number`` rounded toward zero to an int, or ``default``."""
    n = number(value, default=None, lo=lo, hi=hi, strings=strings)
    if n is None:
        return default
    return int(n)


def port(value, default):
    """A TCP/UDP port 1..65535 from a config value, or ``default``.

    Port 0 is "pick one for me" to bind(), never a documented
    default, so it is unusable here like any other out-of-range
    value.
    """
    return integer(value, default, lo=1, hi=65535)


def choice(value, choices, default):
    """A string from ``choices``, matched exactly, or ``default``."""
    if isinstance(value, str) and value in choices:
        return value
    return default
