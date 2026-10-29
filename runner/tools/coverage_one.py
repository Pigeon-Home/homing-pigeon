#!/usr/bin/env python3
"""One command for the coverage number.

    python runner/tools/coverage_one.py [--jobs N] [--out-dir DIR]

Runs the standard-library suite coverage and the gaps report, then
prints one line: statements, never executed, branches, never taken,
percent. The conductor should not have to know which tool. The JSON
and the markdown land in the out dir for anyone who wants the detail.

Stdlib only. Python 3.12 or later, like the two tools it calls.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def one_line(report):
    totals = report.get("totals", {})
    return (
        "statements %d, never executed %d; branches %d, never taken %d; "
        "%.1f%% covered" % (
            totals.get("num_statements", 0),
            totals.get("missing_lines", 0),
            totals.get("num_branches", 0),
            totals.get("missing_branches", 0),
            totals.get("percent_covered", 0.0)))


def run(jobs, out_dir, modules):
    os.makedirs(out_dir, exist_ok=True)
    cov = os.path.join(out_dir, "coverage.json")
    gaps = os.path.join(out_dir, "gaps.md")
    cmd = [sys.executable, os.path.join(HERE, "stdlib_coverage.py"),
           "--subprocess", "--jobs", str(jobs), "--out", cov]
    cmd.extend(modules)
    rc = subprocess.call(cmd)
    if rc != 0:
        return rc
    rc = subprocess.call([
        sys.executable, os.path.join(HERE, "coverage_gaps.py"),
        cov, "--out", gaps])
    if rc != 0:
        return rc
    with open(cov, encoding="utf-8") as fh:
        report = json.load(fh)
    print(one_line(report))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out-dir", default="coverage-one")
    ap.add_argument("modules", nargs="*")
    args = ap.parse_args(argv)
    return run(args.jobs, args.out_dir, args.modules)


if __name__ == "__main__":
    sys.exit(main())
