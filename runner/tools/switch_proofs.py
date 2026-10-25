#!/usr/bin/env python3
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
"""Run the switch-proof roster and name every control without a proof.

    python runner/tools/switch_proofs.py --have linux,bwrap [--root]
        [--out switch-proofs.md] [--annotate] [--list]

The roster (runner/tests/switch_roster.py) says, for each security
control the runner ships, what SECURITY.md promises when the control
is on and which tests prove it. This tool is the continuous half: it
runs those tests on the leg it is given and judges each control.

    proven      every listed test ran and passed on this leg
    FAILED      a listed test failed or errored: the promise broke
    MISSING     a listed test id does not load: the proof was renamed
                or removed without the roster following
    SKIPPED     a listed test skipped on a leg that meets the entry's
                needs: the proof did not run where it should have
    unproven    the entry lists no tests yet (queue S or R work)
    not here    the leg does not meet the entry's needs; not judged

The exit code is 1 on FAILED, MISSING or SKIPPED -- a regression or a
lost proof -- and 0 otherwise. An unproven control is reported, not
failed: the roster is filled by the campaign, and the count of
unproven controls going down is what this workflow is for. Under
--annotate the verdicts become GitHub annotations and the step
summary carries the table, readable when the log is not.

--have names what this leg provides, from the roster's KNOWN_NEEDS
("linux", "bwrap", "root"); --root is shorthand for adding "root"
when the process really is root (it is refused otherwise, so a leg
cannot claim a privilege it does not have).

Stdlib only, so it runs wherever the suite runs.
"""

import argparse
import importlib
import os
import sys
import time
import unittest


def _load_roster(root):
    if root not in sys.path:
        sys.path.insert(0, root)
    mod = importlib.import_module("runner.tests.switch_roster")
    return list(mod.ROSTER), tuple(mod.KNOWN_NEEDS)


def applicable(entry, have):
    """True when the leg provides everything the entry needs."""
    return set(entry.get("needs", ())).issubset(set(have))


class _Result(unittest.TestResult):
    """Per-test outcomes by id, nothing printed."""

    def __init__(self):
        super().__init__()
        self.outcome = {}

    @staticmethod
    def _id(test):
        return test.id()

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcome.setdefault(self._id(test), "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcome[self._id(test)] = "failed: " + _first_line(err)

    def addError(self, test, err):
        super().addError(test, err)
        self.outcome[self._id(test)] = "error: " + _first_line(err)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcome[self._id(test)] = "skipped: " + str(reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.outcome.setdefault(self._id(test), "passed")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcome[self._id(test)] = "failed: unexpected success"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.outcome[self._id(test)] = "failed: " + _first_line(err)


def _first_line(err):
    try:
        return str(err[1]).splitlines()[0][:200]
    except Exception:
        return "?"


def run_roster(roster, have, loader=None, stream=None):
    """Judge every entry. Returns (verdicts, result).

    verdicts: list of (entry, verdict, detail) in roster order, where
    verdict is one of proven / FAILED / MISSING / SKIPPED / unproven /
    not here.
    """
    loader = loader or unittest.defaultTestLoader
    stream = stream or sys.stdout
    judged = [e for e in roster if applicable(e, have)]
    wanted = sorted({t for e in judged for t in e.get("tests", ())})
    suite = unittest.TestSuite()
    missing = {}
    # The run tests each roster id loaded, by their own ids: the
    # entry's outcomes are looked up through this map, never by name
    # prefix, so a class reached through an alias still counts.
    loaded_ids = {}
    for test_id in wanted:
        try:
            loaded = loader.loadTestsFromName(test_id)
        except Exception as exc:  # the id does not import
            missing[test_id] = "%s: %s" % (type(exc).__name__, exc)
            continue
        # unittest wraps an unloadable name in a _FailedTest instead
        # of raising; count it as missing, not as a test that errored.
        failed_load = [t for t in _flatten(loaded)
                       if type(t).__name__ == "_FailedTest"]
        if failed_load or loaded.countTestCases() == 0:
            missing[test_id] = "no such test"
            continue
        loaded_ids[test_id] = {t.id() for t in _flatten(loaded)}
        suite.addTests(loaded)
    print("switch proofs: %d roster entries, %d judged on this leg "
          "(have: %s), %d tests" % (len(roster), len(judged),
                                    ",".join(sorted(have)) or "-",
                                    suite.countTestCases()), file=stream)
    result = _Result()
    started = time.time()
    suite.run(result)
    print("ran %d tests in %.1fs" % (result.testsRun, time.time() - started),
          file=stream)
    verdicts = []
    for entry in roster:
        tests = list(entry.get("tests", ()))
        if not applicable(entry, have):
            verdicts.append((entry, "not here", "needs " + ",".join(
                sorted(set(entry.get("needs", ())) - set(have)))))
            continue
        if not tests:
            verdicts.append((entry, "unproven", "no tests listed"))
            continue
        lost = [t for t in tests if t in missing]
        if lost:
            verdicts.append((entry, "MISSING", "; ".join(
                "%s (%s)" % (t, missing[t]) for t in lost)))
            continue
        own = set().union(*(loaded_ids.get(t, set()) for t in tests))
        mine = {tid: out for tid, out in result.outcome.items() if tid in own}
        bad = sorted(tid for tid, out in mine.items()
                     if out.startswith(("failed", "error")))
        skipped = sorted(tid for tid, out in mine.items()
                         if out.startswith("skipped"))
        if bad:
            verdicts.append((entry, "FAILED", "; ".join(
                "%s: %s" % (t, mine[t]) for t in bad[:3])))
        elif len(skipped) == len(mine) or not mine:
            # Every test the entry lists skipped (or none ran at all):
            # nothing on this leg proved the promise.
            verdicts.append((entry, "SKIPPED", "; ".join(
                "%s: %s" % (t, mine[t]) for t in skipped[:3])
                or "no test of the entry ran"))
        else:
            note = "%d tests passed" % (len(mine) - len(skipped))
            if skipped:
                note += ", %d skipped" % len(skipped)
            verdicts.append((entry, "proven", note))
    return verdicts, result


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


def render(verdicts, have, title):
    counts = {}
    for _e, v, _d in verdicts:
        counts[v] = counts.get(v, 0) + 1
    judged = sum(n for v, n in counts.items() if v != "not here")
    lines = ["# Switch proofs: %s" % title, "",
             "Leg provides: %s. %d controls judged here: %d proven, "
             "%d unproven, %d failed, %d missing, %d skipped; %d not "
             "applicable on this leg." % (
                 ", ".join(sorted(have)) or "nothing beyond the suite",
                 judged, counts.get("proven", 0), counts.get("unproven", 0),
                 counts.get("FAILED", 0), counts.get("MISSING", 0),
                 counts.get("SKIPPED", 0), counts.get("not here", 0)),
             "", "| Control | Verdict | Promise | Detail |",
             "|---|---|---|---|"]
    for entry, verdict, detail in verdicts:
        lines.append("| `%s` | %s | %s | %s |" % (
            entry["id"], verdict, entry.get("promise", "").replace("|", "/"),
            detail.replace("|", "/")))
    lines += ["", "Verdicts: proven = every listed test ran and passed; "
              "unproven = the roster lists no test yet (campaign queue S/R); "
              "FAILED, MISSING and SKIPPED fail the run. The roster is "
              "`runner/tests/switch_roster.py`."]
    return "\n".join(lines) + "\n"


def _escape(text):
    return (text.replace("%", "%25").replace("\r", "%0D")
            .replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C"))


def annotate(verdicts, title):
    level = {"FAILED": "error", "MISSING": "error", "SKIPPED": "error",
             "unproven": "warning"}
    for entry, verdict, detail in verdicts:
        if verdict in level:
            print("::%s title=%s::%s -- %s" % (
                level[verdict], _escape("switch %s %s: %s" % (
                    title, verdict, entry["id"])),
                entry.get("promise", "")[:200], detail[:400]))
    proven = sum(1 for _e, v, _d in verdicts if v == "proven")
    judged = sum(1 for _e, v, _d in verdicts if v != "not here")
    print("::notice title=%s::%d of %d controls proven on this leg" % (
        _escape("switch proofs " + title), proven, judged))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--have", default="",
                    help="comma list of what this leg provides: linux,bwrap,root")
    ap.add_argument("--root", action="store_true",
                    help="add root to --have; refused unless the process is root")
    ap.add_argument("--out", help="markdown report to write")
    ap.add_argument("--title", default="this leg")
    ap.add_argument("--root-dir", default=os.getcwd(),
                    help="the project root (holds runner/)")
    ap.add_argument("--annotate", action="store_true")
    ap.add_argument("--list", action="store_true",
                    help="print the roster and exit")
    a = ap.parse_args(argv)

    roster, known = _load_roster(os.path.abspath(a.root_dir))
    have = {h.strip() for h in a.have.split(",") if h.strip()}
    if a.root:
        if not (hasattr(os, "geteuid") and os.geteuid() == 0):
            print("--root given but this process is not root", file=sys.stderr)
            return 2
        have.add("root")
    unknown = have - set(known)
    if unknown:
        print("unknown --have values: %s (known: %s)" % (
            ",".join(sorted(unknown)), ",".join(known)), file=sys.stderr)
        return 2

    if a.list:
        for entry in roster:
            needs = ",".join(entry.get("needs", ()))
            n = len(entry.get("tests", ()))
            print("%-20s %-18s %s" % (
                entry["id"], ("needs " + needs) if needs else "-",
                ("%d tests" % n) if n else "UNPROVEN"))
        return 0

    verdicts, _result = run_roster(roster, have)
    text = render(verdicts, have, a.title)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    for entry, verdict, detail in verdicts:
        print("%-9s %-20s %s" % (verdict, entry["id"], detail))
    if a.annotate:
        annotate(verdicts, a.title)
    bad = [v for _e, v, _d in verdicts if v in ("FAILED", "MISSING", "SKIPPED")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
