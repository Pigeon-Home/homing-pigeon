"""Turn a coverage report into a ranked, classified list of targets.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

Project Platinum's compass (docs/project/campaign-standing-orders.md,
queue P). A coverage number says how much ran; this says what did not
and why, so a fuzzing hour goes to the lines a test can reach.

    python3 runner/tools/coverage_targets.py coverage.json [--root .]
        [--min 3] [--markdown | --json] [--since previous.json]

The input is coverage.py's JSON report (`coverage json`), or the
per-file {path: {statements, covered, missing}} shape. Every function
with `--min` or more missing statements is listed with its missing
lines, its missing branch arcs when the report has them, and a class
read from the AST:

  logic     the missing lines are in the function's main flow: the
            first place to aim a property test or a fuzz seed
  except    every missing line sits in an except handler: reached by
            making the guarded call fail (a bad file, a refused socket)
  guard     one early refusal (`if ...: return / raise / continue`)
            and nothing else: one adversarial input reaches it
  platform  under an `os.name` / `sys.platform` branch or named for a
            platform: covered where it applies, skipped elsewhere
  shadowed  the def is rebound later in its module: dead code, a Q to
            Claude rather than a test

`--since` prints the delta against an earlier report first. Exit 0.
"""
import argparse
import ast
import json
import os
import sys


def load(path):
    """{relpath: {"missing": set, "statements": int, "branches": set}}"""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = {}
    files = data.get("files") if isinstance(data.get("files"), dict) else data
    for name, rec in files.items():
        if not isinstance(rec, dict):
            continue
        missing = set(rec.get("missing_lines") or rec.get("missing") or [])
        if "summary" in rec:
            stmts = rec["summary"].get("num_statements", 0)
        else:
            stmts = rec.get("statements", len(rec.get("executed_lines", [])) + len(missing))
        arcs = {tuple(a) for a in rec.get("missing_branches") or []}
        out[name.replace(os.sep, "/")] = {"missing": missing, "statements": stmts,
                                          "branches": arcs}
    return out


def _platform_name(name):
    low = name.lower()
    return any(t in low for t in ("windows", "win32", "posix", "linux",
                                  "darwin", "macos", "freebsd", "netsh",
                                  "powershell", "systemd", "launchd"))


def _under_platform_test(node, parents):
    for p in parents:
        test = getattr(p, "test", None)
        if test is not None:
            txt = ast.unparse(test)
            if "sys.platform" in txt or "os.name" in txt or "FROZEN" in txt:
                return True
    return False


def classify(fn, missing, parents_of):
    """One of logic / except / guard / platform / shadowed for a def."""
    body_lines = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.stmt) and node is not fn:
            body_lines[node.lineno] = node
    miss = sorted(l for l in missing if l in body_lines)
    if not miss:
        return "logic"
    if _platform_name(fn.name):
        return "platform"
    if all(_under_platform_test(body_lines[l], parents_of[body_lines[l]]) for l in miss):
        return "platform"
    in_except = 0
    for l in miss:
        if any(isinstance(p, ast.ExceptHandler) for p in parents_of[body_lines[l]]):
            in_except += 1
    if in_except == len(miss):
        return "except"
    if len(miss) <= 3:
        nodes = [body_lines[l] for l in miss]
        if all(isinstance(n, (ast.Return, ast.Raise, ast.Continue, ast.Break))
               or (isinstance(n, ast.If) and len(n.body) == 1
                   and isinstance(n.body[0], (ast.Return, ast.Raise, ast.Continue)))
               for n in nodes):
            return "guard"
    return "logic"


def targets(report, root, min_missing=3):
    rows = []
    for rel, rec in report.items():
        path = os.path.join(root, rel)
        if not os.path.isfile(path) or not rec["missing"]:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
        except (OSError, SyntaxError):
            continue
        parents_of = {}
        stack = [(tree, ())]
        while stack:
            node, parents = stack.pop()
            for child in ast.iter_child_nodes(node):
                parents_of[child] = parents + (node,)
                stack.append((child, parents + (node,)))
        rebound = set()
        defs = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                defs[node.name] = node.end_lineno
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id in defs \
                            and node.lineno > defs[t.id]:
                        rebound.add(t.id)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            span = range(fn.lineno, (fn.end_lineno or fn.lineno) + 1)
            miss = sorted(l for l in rec["missing"] if l in span)
            if len(miss) < min_missing:
                continue
            arcs = sorted(a for a in rec["branches"] if a[0] in span)
            kind = "shadowed" if fn.name in rebound and fn in tree.body \
                else classify(fn, miss, parents_of)
            qual = fn.name
            for p in parents_of.get(fn, ()):
                if isinstance(p, ast.ClassDef):
                    qual = p.name + "." + fn.name
            rows.append({"file": rel, "function": qual, "line": fn.lineno,
                         "missing": miss, "missing_branches": arcs,
                         "size": len([n for n in ast.walk(fn) if isinstance(n, ast.stmt)]),
                         "class": kind,
                         "args": [a.arg for a in fn.args.args if a.arg not in ("self", "cls")]})
    order = {"logic": 0, "guard": 1, "except": 2, "shadowed": 3, "platform": 4}
    rows.sort(key=lambda r: (order[r["class"]], -len(r["missing"]), r["file"], r["line"]))
    return rows


def totals(report):
    st = sum(r["statements"] for r in report.values())
    miss = sum(len(r["missing"]) for r in report.values())
    return st, miss


def markdown(rows, report, since=None):
    st, miss = totals(report)
    out = []
    pct = 100.0 * (st - miss) / st if st else 0.0
    line = f"statements {pct:.1f}% covered, {miss} missing of {st}"
    if since is not None:
        st0, miss0 = totals(since)
        pct0 = 100.0 * (st0 - miss0) / st0 if st0 else 0.0
        line += f" ({pct - pct0:+.1f} points, {miss0 - miss:+d} lines closed since the last report)"
    out.append(line)
    out.append("")
    out.append("| class | file:function | missing | branches | args |")
    out.append("|---|---|---:|---:|---|")
    for r in rows:
        lines = ",".join(str(l) for l in r["missing"][:8]) + ("…" if len(r["missing"]) > 8 else "")
        out.append(f"| {r['class']} | `{r['file'].split('runner/', 1)[-1]}:{r['function']}` L{r['line']} "
                   f"| {len(r['missing'])} ({lines}) | {len(r['missing_branches'])} | {', '.join(r['args'])} |")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("report")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--since", default=None)
    args = ap.parse_args(argv)
    report = load(args.report)
    rows = targets(report, args.root, args.min)
    since = load(args.since) if args.since else None
    if args.json:
        st, miss = totals(report)
        json.dump({"statements": st, "missing": miss, "targets": rows}, sys.stdout, indent=1)
    else:
        print(markdown(rows, report, since))
    return 0


if __name__ == "__main__":
    sys.exit(main())
