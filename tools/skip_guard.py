#!/usr/bin/env python3
# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
"""Fail CI when a proof that must run on this box skipped instead.

A green suite is only as honest as its skips. unittest reports a
skip as `... skipped 'reason'` and the build stays green, so a
missing tool can silently retire the one test that backs a claim
(the bwrap sandbox tests did exactly this: no workflow installed
bwrap, so "the sandbox walls the job in" was never proven in CI).

Usage:
    python tools/skip_guard.py test-output.log --forbid "bwrap not available"

Reads a `unittest -v` log, prints every skip reason with its
count (so the pipeline shows them without anyone scrolling), and
exits 1 if any skip reason contains a forbidden substring. Only
the reasons named with --forbid fail the build; every other skip
is still legitimate (Pi Light has no model, Windows has no bwrap).
"""
import argparse
import re
import sys
from collections import Counter

_SKIP_RE = re.compile(r"\.\.\. skipped ['\"](?P<reason>.*?)['\"]\s*$")
_RAN_RE = re.compile(r"^Ran (\d+) tests? in ")


def skips_in(lines):
    """Counter of skip reasons found in unittest -v output lines."""
    reasons = Counter()
    for line in lines:
        m = _SKIP_RE.search(line.rstrip("\r\n"))
        if m:
            reasons[m.group("reason")] += 1
    return reasons


def forbidden(reasons, needles):
    """The (reason, count) pairs whose reason contains a needle."""
    hits = []
    for reason, count in sorted(reasons.items()):
        if any(n in reason for n in needles):
            hits.append((reason, count))
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("log", help="unittest -v output (- for stdin)")
    ap.add_argument("--forbid", action="append", default=[],
                    metavar="SUBSTRING",
                    help="a skip reason that must not appear; repeatable")
    ap.add_argument("--no-skips", action="store_true",
                    help="any skip at all fails (for a proof that must "
                         "run every test on every box)")
    ap.add_argument("--require-ok", action="store_true",
                    help="the log must show `Ran N tests` with N > 0 "
                         "and a verdict line of exactly OK")
    args = ap.parse_args(argv)

    fh = sys.stdin if args.log == "-" else open(args.log, encoding="utf-8",
                                                errors="replace")
    with fh:
        lines = fh.read().splitlines()
    reasons = skips_in(lines)

    if reasons:
        print("skip reasons seen:")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print("  %4d  %s" % (count, reason))
    else:
        print("skip reasons seen: none")

    rc = 0
    hits = forbidden(reasons, args.forbid)
    if hits:
        print("\nFORBIDDEN skips -- a proof this box must run did not:")
        for reason, count in hits:
            print("  %4d  %s" % (count, reason))
        rc = 1
    if args.no_skips and reasons:
        print("\nSKIPS are not allowed in this run: a skipped proof "
              "is not a proof.")
        rc = 1
    if args.require_ok:
        ran = [m for m in (_RAN_RE.match(l) for l in lines) if m]
        count = int(ran[-1].group(1)) if ran else 0
        verdict_ok = any(l.strip() == "OK" for l in lines)
        if count <= 0:
            print("\nREQUIRE-OK: no `Ran N tests` line with N > 0 "
                  "(the suite did not run, or discovery found nothing)")
            rc = 1
        if not verdict_ok:
            print("\nREQUIRE-OK: no bare `OK` verdict line")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
