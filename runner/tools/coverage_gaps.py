#!/usr/bin/env python3
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c
"""Turn a coverage.py JSON report into the list of code no test runs.

    python runner/tools/coverage_gaps.py coverage.json --out gaps.md \
        [--title "Linux"] [--annotate] [--top 60]

Coverage percentages say how much ran; this says what did not, by
function, because a function is the unit a test is written against
and the unit a campaign hunt is aimed at. The output is Markdown:

- the totals (statements, branches, percent);
- every shipped module, least covered first;
- the functions with the most never-executed lines, with the line
  ranges, so a finding can name exactly what to make run.

Modules under runner/tests/ and runner/tools/ are not the product
and are left out. Stdlib only, so it runs anywhere the suite runs.

Under GitHub Actions (``--annotate``) the totals and the ten largest
gaps also become ``::notice`` annotations, readable from the run
page when the job log is not.
"""

import argparse
import ast
import json
import os
import sys

_SKIP_PARTS = ("/tests/", "/tools/")


def _rel(path, root):
    path = path.replace("\\", "/")
    root = root.replace("\\", "/").rstrip("/") + "/"
    return path[len(root):] if path.startswith(root) else path


def _ranges(lines):
    """[3, 4, 5, 9] -> '3-5, 9'."""
    out = []
    start = prev = None
    for n in sorted(lines):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(str(start) if start == prev else "%d-%d" % (start, prev))
            start = prev = n
    if start is not None:
        out.append(str(start) if start == prev else "%d-%d" % (start, prev))
    return ", ".join(out)


def _functions(path):
    """(name, first, last, nested ranges) for every def in a file."""
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError, ValueError):
        return []
    found = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                inner = [(c.lineno, c.end_lineno)
                         for c in ast.walk(child)
                         if c is not child and isinstance(
                             c, (ast.FunctionDef, ast.AsyncFunctionDef))]
                found.append((name, child.lineno, child.end_lineno, inner))
                visit(child, name + ".")
            elif isinstance(child, ast.ClassDef):
                visit(child, prefix + child.name + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    return found


def gaps(report, root):
    files = []
    funcs = []
    for path, info in report.get("files", {}).items():
        rel = _rel(path, root)
        if any(part in "/" + rel for part in _SKIP_PARTS):
            continue
        summary = info.get("summary", {})
        missing = set(info.get("missing_lines", []))
        files.append((summary.get("percent_covered", 100.0),
                      summary.get("num_statements", 0),
                      summary.get("missing_lines", 0), rel))
        if not missing:
            continue
        full = path if os.path.isabs(path) else os.path.join(root, path)
        for name, first, last, inner in _functions(full):
            own = set(range(first, last + 1))
            for a, b in inner:
                own -= set(range(a, b + 1))
            missed = own & missing
            if missed:
                funcs.append((len(missed), len(own), rel, name, missed))
    files.sort(key=lambda r: (r[0], -r[1]))
    funcs.sort(key=lambda r: (-r[0], r[2], r[3]))
    return files, funcs


def render(report, files, funcs, title, top):
    totals = report.get("totals", {})
    lines = ["# Coverage gaps: %s" % title, ""]
    lines.append(
        "Statements %d, never executed %d; branches %d, never taken %d; "
        "%.1f%% covered overall (shipped code only: runner/ without "
        "tests/ and tools/)." % (
            totals.get("num_statements", 0), totals.get("missing_lines", 0),
            totals.get("num_branches", 0),
            totals.get("missing_branches", 0),
            totals.get("percent_covered", 0.0)))
    lines += ["", "## Functions with the most never-executed lines", "",
              "Lines counted are the function's own, nested functions "
              "excluded. Each row is a hunt target: a test that makes "
              "these lines run, and asserts what the docs say they do.", "",
              "| Missed | Of | Function | Never-executed lines |",
              "|---:|---:|---|---|"]
    for missed, own, rel, name, lines_missed in funcs[:top]:
        lines.append("| %d | %d | `%s:%s` | %s |" % (
            missed, own, rel, name, _ranges(lines_missed)))
    lines += ["", "## Modules, least covered first", "",
              "| Covered | Statements | Missed | Module |",
              "|---:|---:|---:|---|"]
    for pct, stmts, missed, rel in files:
        if missed:
            lines.append("| %.0f%% | %d | %d | `%s` |" % (
                pct, stmts, missed, rel))
    return "\n".join(lines) + "\n"


def _escape(text):
    return (text.replace("%", "%25").replace("\r", "%0D")
            .replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", help="coverage json report")
    ap.add_argument("--out", required=True, help="markdown file to write")
    ap.add_argument("--title", default="this run")
    ap.add_argument("--root", default=os.getcwd())
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--annotate", action="store_true")
    a = ap.parse_args(argv)
    with open(a.report, encoding="utf-8") as fh:
        report = json.load(fh)
    files, funcs = gaps(report, a.root)
    text = render(report, files, funcs, a.title, a.top)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    if a.annotate:
        t = report.get("totals", {})
        print("::notice title=%s::%.1f%% covered; %d statements never "
              "executed" % (_escape("coverage " + a.title),
                            t.get("percent_covered", 0.0),
                            t.get("missing_lines", 0)))
        for missed, own, rel, name, _l in funcs[:10]:
            print("::notice title=%s::%d of %d lines never executed" % (
                _escape("gap %s: %s:%s" % (a.title, rel, name)), missed, own))
    print("wrote %s: %d modules with gaps, %d functions" % (
        a.out, sum(1 for f in files if f[2]), len(funcs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
