#!/usr/bin/env python3
"""Mint and check cs_office work references ("code names").

A code name is the public handle for a piece of work. It has the form

    hp<marking>-<guid>
    hp<marking>-<guid>-<sub-name>

for example ``hp1-bebd8c71-ecb9-4d68-87aa-c0dc38d118b7-a``.

The marking is a sensitivity level, a single digit 0-3:

    0  public
    1  public with care
    2  private shelf only
    3  case file only

The GUID is a canonical lowercase UUID4 (8-4-4-4-12 hex, version
nibble 4, variant 8/9/a/b). It is random and carries no information:
nothing about the work, its owner, or its date can be read from it.

The optional sub-name names a part of the work under the same
reference: one or more lowercase ``[a-z0-9]`` segments joined by
single dashes (``-a``, ``-corpus``, ``-stage-2``). A sub-name is at
most 32 characters, and a whole reference at most 128 characters.

Parsing is strict. The whole string must be the reference: no
stripping, no surrounding whitespace, no extra characters, no
uppercase, and no other UUID version or variant. Anything else is
malformed, because a reference that is nearly right is a reference
to the wrong shelf.

    python3 runner/tools/codename.py mint [--marking N] [--sub NAME]
    python3 runner/tools/codename.py parse <ref>
    python3 runner/tools/codename.py check <ref>   # exit 0/1

Stdlib only.
"""
import argparse
import re
import sys
import uuid
from typing import NamedTuple

MARKINGS = (0, 1, 2, 3)

SHELF = {
    0: "public",
    1: "public with care",
    2: "private shelf only",
    3: "case file only",
}
# The same mapping under the longer name, for callers that ask for
# the marking names rather than the shelf.
MARKING_NAMES = SHELF

MAX_LENGTH = 128
MAX_SUB_LENGTH = 32

_GUID = (r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}"
         r"-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_SUB = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_REFERENCE = re.compile(r"hp([0-3])-(%s)(?:-(%s))?" % (_GUID, _SUB))
_SUB_ONLY = re.compile(_SUB)


class CodeName(NamedTuple):
    """The parts of a code name: marking, guid, and sub-name."""

    marking: int
    guid: str
    sub: str | None = None

    def __str__(self):
        text = "hp%d-%s" % (self.marking, self.guid)
        if self.sub is not None:
            text += "-" + self.sub
        return text


def _check_marking(marking):
    if isinstance(marking, bool) or not isinstance(marking, int):
        raise TypeError("marking must be an int, not %s"
                        % type(marking).__name__)
    if marking not in MARKINGS:
        raise ValueError("marking must be one of %s, not %r"
                         % (", ".join(str(m) for m in MARKINGS), marking))
    return marking


def _check_sub(sub):
    if sub is None:
        return None
    if not isinstance(sub, str):
        raise TypeError("sub-name must be a str, not %s"
                        % type(sub).__name__)
    if len(sub) > MAX_SUB_LENGTH:
        raise ValueError("sub-name is %d characters; the cap is %d"
                         % (len(sub), MAX_SUB_LENGTH))
    if not _SUB_ONLY.fullmatch(sub):
        raise ValueError("sub-name %r is not lowercase [a-z0-9] segments "
                         "joined by single dashes" % (sub,))
    return sub


def mint(marking=0, sub=None):
    """A new code name as a string, with a fresh random UUID4."""
    marking = _check_marking(marking)
    sub = _check_sub(sub)
    return str(CodeName(marking, str(uuid.uuid4()), sub))


def parse(text):
    """The CodeName for `text`, held to the full strict shape.

    TypeError for non-str input, ValueError for a malformed string.
    """
    if not isinstance(text, str):
        raise TypeError("code name must be a str, not %s"
                        % type(text).__name__)
    if len(text) > MAX_LENGTH:
        raise ValueError("code name is %d characters; the cap is %d"
                         % (len(text), MAX_LENGTH))
    m = _REFERENCE.fullmatch(text)
    if m is None:
        raise ValueError("not a code name: %r" % (text,))
    sub = m.group(3)
    if sub is not None and len(sub) > MAX_SUB_LENGTH:
        raise ValueError("sub-name is %d characters; the cap is %d"
                         % (len(sub), MAX_SUB_LENGTH))
    return CodeName(int(m.group(1)), m.group(2), sub)


def is_valid(text):
    """True only when `parse(text)` would succeed."""
    try:
        parse(text)
    except (TypeError, ValueError):
        return False
    return True


def marking_of(text):
    """The marking (0-3) of a code name; parse's errors propagate."""
    return parse(text).marking


def shelf_of(marking):
    """The shelf name for a marking; TypeError/ValueError if not 0-3."""
    return SHELF[_check_marking(marking)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_mint = sub.add_parser("mint", help="mint a new code name")
    p_mint.add_argument("--marking", type=int, default=0,
                        help="sensitivity level 0-3 (default 0)")
    p_mint.add_argument("--sub", default=None,
                        help="optional sub-name, e.g. corpus or stage-2")
    p_parse = sub.add_parser("parse", help="print the parts of a reference")
    p_parse.add_argument("ref")
    p_check = sub.add_parser("check", help="exit 0 if valid, 1 if not")
    p_check.add_argument("ref")
    args = ap.parse_args(argv)

    if args.cmd == "mint":
        try:
            print(mint(args.marking, args.sub))
        except (TypeError, ValueError) as exc:
            print("codename: %s" % exc, file=sys.stderr)
            return 2
        return 0
    if args.cmd == "parse":
        try:
            name = parse(args.ref)
        except (TypeError, ValueError) as exc:
            print("codename: %s" % exc, file=sys.stderr)
            return 1
        print("marking: %d" % name.marking)
        print("guid: %s" % name.guid)
        print("sub: %s" % (name.sub if name.sub is not None else "none"))
        print("shelf: %s" % shelf_of(name.marking))
        return 0
    # check
    if is_valid(args.ref):
        print("valid")
        return 0
    print("invalid", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
