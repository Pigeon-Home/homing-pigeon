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


_FAIL_RE = re.compile(r"^(FAIL|ERROR): \S+ \(tests\.")
_EXC_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*Error|[A-Za-z_]*Exception|"
                     r"AssertionError|bwrap|ImportError|ModuleNotFoundError)"
                     r"(: |$)")


def verdict_of(lines):
    """unittest's final verdict line: "OK", "OK (skipped=3)",
    "FAILED (failures=1)" -- the first non-blank line after the
    last "Ran N tests" line. Empty when the log has no summary
    (a suite that died before printing one)."""
    last_ran = None
    for i, raw in enumerate(lines):
        if _RAN_RE.match(raw.rstrip("\r\n")):
            last_ran = i
    if last_ran is None:
        return ""
    for raw in lines[last_ran + 1:]:
        line = raw.rstrip("\r\n").strip()
        if line:
            return line
    return ""


def failures_in(lines):
    """unittest's own failure lines and the exception lines that
    follow them -- the parts of a log worth an annotation.

    Actions keeps ten error annotations per step, so the ten are
    spent on test ids first: every FAIL:/ERROR: line, in log order,
    then exception lines fill what is left. A -v log of a 4,500-test
    suite carries exception text that is not a failure (a fixture
    dumping a deliberately red shard, a test printing the traceback
    it expects), and in log order those used to take the ten slots
    before the real FAIL: lines near the end -- 126 of 137 red
    suite runs over six days named no test in their annotations
    (docs/reports/v3.12.56/ci-failures.md). A log whose verdict is
    OK -- bare, or OK with unittest's parenthetical (skipped=N,
    expected failures=N) -- has no failure to name and gets
    nothing. The verdict is the one unittest prints last, after
    its final "Ran N tests" line; a bare OK earlier in the log is
    fixture output (a passing fake shard's tail, printed by the
    very test that proves the shard runner), and the first CI run
    of this guard was blinded by exactly that.
    """
    if verdict_of(lines).startswith("OK"):
        return []
    fails = []
    excs = []
    seen = set()
    for raw in lines:
        line = raw.rstrip("\r\n")
        if line in seen:
            continue
        if _FAIL_RE.match(line):
            seen.add(line)
            fails.append(line)
        elif _EXC_RE.match(line):
            seen.add(line)
            excs.append(line)
    return (fails + excs)[:10]


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
    ap.add_argument("--annotate", action="store_true",
                    help="also print GitHub ::error:: annotations for "
                         "failing tests, exception lines and verdicts, "
                         "so a leg's reason is readable without its log")
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
    notes = []

    def note(text):
        notes.append(text)
        print(text)

    if args.annotate:
        for line in failures_in(lines):
            print("::error::" + line[:900])

    hits = forbidden(reasons, args.forbid)
    if hits:
        note("\nFORBIDDEN skips -- a proof this box must run did not:")
        for reason, count in hits:
            note("  %4d  %s" % (count, reason))
        rc = 1
    if args.no_skips and reasons:
        note("\nSKIPS are not allowed in this run: a skipped proof "
             "is not a proof.")
        rc = 1
    if args.require_ok:
        ran = [m for m in (_RAN_RE.match(ln) for ln in lines) if m]
        count = int(ran[-1].group(1)) if ran else 0
        # The final verdict, not any OK a fixture printed earlier.
        verdict_ok = verdict_of(lines) == "OK"
        if count <= 0:
            note("\nREQUIRE-OK: no `Ran N tests` line with N > 0 "
                 "(the suite did not run, or discovery found nothing)")
            rc = 1
        if not verdict_ok:
            note("\nREQUIRE-OK: no bare `OK` verdict line")
            rc = 1
    if args.annotate and rc:
        for text in notes:
            print("::error::" + text.strip().replace("\n", " ")[:900])
    return rc


if __name__ == "__main__":
    sys.exit(main())
