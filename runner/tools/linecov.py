#!/usr/bin/env python3
# Agent-Stamp: 70000a51-e296-4b2c-bf5b-ba020e23eb91
"""Line coverage with the standard library alone (sys.monitoring).

    python runner/tools/linecov.py --out cov.json \
        --source runner/hosting --source runner/cloud/send_job.py \
        -- runner.tests.test_hosting_cli_main runner.tests.test_transport_queues

The CI coverage job uses coverage.py. A box that cannot install it (no
package index, an air-gapped rig) can still measure what a set of
tests runs: this tool runs unittest under sys.monitoring (Python 3.12
and later), records every line executed in the named sources, and
writes a report in the shape coverage.py's `json` command writes
(`files.<path>.executed_lines`, `missing_lines`, `summary`, and
`totals`), so `runner/tools/coverage_gaps.py` reads it unchanged.

Statements are counted from the AST: every statement node, with
docstrings left out and a `def` or `class` counted on its first line
(it runs at import). It does not measure branches. Child processes are
not measured. The exit code is the test run's: 0 when every test
passed.
"""
import argparse
import ast
import json
import os
import sys
import unittest


def statements(path):
    """The line numbers of the statements in a source file."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            continue
        lines.add(node.lineno)
    return lines


def sources(paths, root):
    out = []
    for p in paths:
        full = os.path.realpath(os.path.join(root, p))
        if os.path.isdir(full):
            for dirpath, dirnames, filenames in os.walk(full):
                dirnames[:] = sorted(d for d in dirnames
                                     if d != "__pycache__")
                out += [os.path.join(dirpath, f) for f in sorted(filenames)
                        if f.endswith(".py")]
        elif full.endswith(".py") and os.path.isfile(full):
            out.append(full)
    return sorted(set(out))


def report(files, hits, root):
    rep = {"meta": {"tool": "runner/tools/linecov.py", "branches": False},
           "files": {}, "totals": {}}
    total_s = total_m = 0
    for f in files:
        stmts = statements(f)
        ran = hits.get(f, set()) & stmts
        missing = sorted(stmts - ran)
        n, m = len(stmts), len(missing)
        total_s += n
        total_m += m
        rep["files"][os.path.relpath(f, root)] = {
            "executed_lines": sorted(ran),
            "missing_lines": missing,
            "summary": {"num_statements": n, "missing_lines": m,
                        "covered_lines": n - m,
                        "percent_covered": round(100.0 * (n - m) / n, 2)
                        if n else 100.0}}
    rep["totals"] = {"num_statements": total_s, "missing_lines": total_m,
                     "covered_lines": total_s - total_m,
                     "num_branches": 0, "missing_branches": 0,
                     "percent_covered": round(
                         100.0 * (total_s - total_m) / total_s, 2)
                     if total_s else 100.0}
    return rep


def run(tests, files):
    """Run the tests with line events on; return (hits, result)."""
    mon = sys.monitoring
    # The coverage id first; when another tool holds it (coverage.py
    # measuring this very run), any free id works the same.
    tool = next((i for i in (mon.COVERAGE_ID, 4, 3, 1)
                 if mon.get_tool(i) is None), None)
    if tool is None:
        raise RuntimeError("no free sys.monitoring tool id")
    targets = set(files)
    hits = {f: set() for f in files}
    # The tests under measurement patch os.path freely; the callback
    # uses its own references, resolved once per file name, so a
    # patched realpath never runs inside it.
    realpath = os.path.realpath
    resolved = {}

    def on_line(code, line):
        name = code.co_filename
        real = resolved.get(name)
        if real is None:
            try:
                real = realpath(name) if name else ""
            except Exception:
                real = ""
            resolved[name] = real
        if real in targets:
            hits[real].add(line)
            return None
        return mon.DISABLE

    mon.use_tool_id(tool, "homing-pigeon-linecov")
    try:
        mon.register_callback(tool, mon.events.LINE, on_line)
        mon.set_events(tool, mon.events.LINE)
        suite = unittest.defaultTestLoader.loadTestsFromNames(tests)
        result = unittest.TextTestRunner(stream=sys.stderr,
                                         verbosity=0).run(suite)
    finally:
        mon.set_events(tool, 0)
        mon.register_callback(tool, mon.events.LINE, None)
        mon.free_tool_id(tool)
    return hits, result


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    tests = []
    if "--" in argv:
        i = argv.index("--")
        argv, tests = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(
        prog="linecov.py",
        description="Line coverage of named sources under a set of "
                    "unittest names, with the standard library only.")
    ap.add_argument("--out", required=True, metavar="JSON")
    ap.add_argument("--source", action="append", required=True,
                    metavar="PATH", help="a file or folder to measure "
                                         "(repeatable)")
    ap.add_argument("--root", default=os.getcwd())
    args = ap.parse_args(argv)
    if not hasattr(sys, "monitoring"):
        print("linecov.py needs Python 3.12 or later (sys.monitoring)",
              file=sys.stderr)
        return 2
    if not tests:
        print("give the tests after --", file=sys.stderr)
        return 2
    root = os.path.realpath(args.root)
    if root not in sys.path:
        sys.path.insert(0, root)
    files = sources(args.source, root)
    hits, result = run(tests, files)
    rep = report(files, hits, root)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, sort_keys=True)
        fh.write("\n")
    for rel, info in sorted(rep["files"].items()):
        s = info["summary"]
        print(f"{s['percent_covered']:6.1f}%  {s['num_statements']:5d} "
              f"stmts  {s['missing_lines']:4d} miss  {rel}")
    t = rep["totals"]
    print(f"{t['percent_covered']:6.1f}%  {t['num_statements']:5d} stmts  "
          f"{t['missing_lines']:4d} miss  total ({result.testsRun} tests)")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
