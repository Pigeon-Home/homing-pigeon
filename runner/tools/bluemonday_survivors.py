#!/usr/bin/env python3
# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Project blueMonday, the mutation survivors: what the corpus does
not yet pin.

    python runner/tools/bluemonday_survivors.py [--module NAME ...]
        [--limit N] [--seed N] [--timeout SEC] [--no-record]

Every reader the corpus holds to a contract is mutated one small
change at a time -- a comparison flipped, an `and` for an `or`, a
`not` dropped, a constant moved by one, a literal emptied, a return
made None, a raise made pass, a plus made minus -- and the corpus of
every target that reads through that module is replayed against the
mutant. A mutant whose replay answers the same accepted, refused or
crash for every entry has survived: the corpus cannot tell that
reader from the real one, and the survivor's line is the next thing
the campaign has to find an input for (the plan's section 8, step
5). A killed mutant is a line the corpus already pins.

A mutant is put where every reader will meet it: the corpus tool's
own alias, and every reference to the module, to its functions and
to its classes held by any loaded module of the project (the agent
module re-exports readers by name, and a module imports another
under its own alias), each put back after the replay. So the
targets that read through the agent module (local, stash, mail,
local_inbox) are in the kill set too, and a module one target
reads only through another module's import (the pattern bound
under the queries) is told apart as well. Each mutant runs in this
process under an alarm on the platforms that have one, so a mutant
that loops is a timeout, not a hang.

The result is runner/tests/bluemonday/survivors.json, the latest
run, and one line of kind "survivors" in runs.jsonl, the record of
every run. Stdlib only.
"""

import argparse
import ast
import json
import os
import random
import signal
import sys
import time
import types
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tools import bluemonday_corpus as B  # noqa: E402

STAMP = B.STAMP
REPORT = os.path.join(B.CORPUS_DIR, "survivors.json")

# The modules the corpus tool reads directly, by its alias for each.
MODULES = {
    "verify": "V", "send_job": "SJ", "protocol_v2": "P2",
    "jobcrypto": "JC", "transports": "TR", "board": "BD",
    "mailbox": "MB", "dtlsproto": "DT", "extensions": "EX",
    "security": "SEC", "policy": "PO", "queries": "QU",
    "filenames": "FN", "startup": "ST",
}
# Targets whose checker reads through the agent module. The rebinding
# in kill() puts a mutant where the agent module holds the reader
# too, so these are in the kill set; the name stays in the report so
# a reader of an older report knows what the set once left out.
THROUGH_AGENT = set()

_SWAP_CMP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE,
             ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot,
             ast.IsNot: ast.Is}


# ------------------------------------------------------------------
# The mutants
# ------------------------------------------------------------------

def sites(tree, reached=None):
    """Every (node, operator) a mutant can be made at, in source
    order: one small change each. With `reached`, a set of line
    numbers the corpus executes (from the arc maps), only nodes on
    those lines: a mutant of a line the corpus never runs is out of
    scope, not a survivor."""
    out = []
    # Docstrings, the text of a raise, what goes to a log, and the
    # defaults of a signature are prose or plumbing, not the reading
    # of a byte: a mutant of any of them is not a reader the corpus
    # should tell apart.
    prose = set()
    for parent in ast.walk(tree):
        body = getattr(parent, "body", None)
        if isinstance(body, list):
            for stmt in body:
                if (isinstance(stmt, ast.Expr)
                        and isinstance(stmt.value, ast.Constant)
                        and isinstance(stmt.value.value, str)):
                    prose.add(id(stmt.value))
        if isinstance(parent, ast.Raise) or (
                isinstance(parent, ast.Call)
                and _callee(parent).endswith(("log", "vlog", "warn",
                                              "error", "debug", "info"))):
            for node in ast.walk(parent):
                if node is not parent:
                    prose.add(id(node))
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.Lambda)):
            for default in parent.args.defaults + parent.args.kw_defaults:
                if default is not None:
                    for node in ast.walk(default):
                        prose.add(id(node))
    for node in ast.walk(tree):
        if reached is not None and getattr(node, "lineno", None) not in reached:
            continue
        if id(node) in prose:
            continue
        if isinstance(node, ast.Compare) and len(node.ops) == 1 \
                and type(node.ops[0]) in _SWAP_CMP:
            out.append((node, "compare"))
        elif isinstance(node, ast.BoolOp):
            out.append((node, "boolop"))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            out.append((node, "not"))
        elif isinstance(node, ast.Constant):
            v = node.value
            if isinstance(v, bool):
                out.append((node, "bool"))
            elif isinstance(v, int) and 0 <= abs(v) <= 10_000:
                out.append((node, "int+1"))
                out.append((node, "int-1"))
            elif isinstance(v, str) and v and len(v) <= 64:
                out.append((node, "str-empty"))
        elif isinstance(node, ast.Return) and node.value is not None \
                and not (isinstance(node.value, ast.Constant)
                         and node.value.value is None):
            out.append((node, "return-none"))
        elif isinstance(node, ast.Raise):
            out.append((node, "raise-pass"))
        elif isinstance(node, ast.BinOp) and isinstance(node.op,
                                                        (ast.Add, ast.Sub)):
            out.append((node, "add-sub"))
    return [(n, op) for n, op in out if getattr(n, "lineno", None)]


def _callee(call):
    """The name a call is made on: f for f(), x.f for x.f()."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def apply(node, op):
    """Change one node in place for one operator; the caller works on
    a fresh tree for every mutant."""
    if op == "compare":
        node.ops = [_SWAP_CMP[type(node.ops[0])]()]
    elif op == "boolop":
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif op == "not":
        return node.operand
    elif op == "bool":
        node.value = not node.value
    elif op == "int+1":
        node.value = node.value + 1
    elif op == "int-1":
        node.value = node.value - 1
    elif op == "str-empty":
        node.value = ""
    elif op == "return-none":
        node.value = ast.Constant(value=None)
    elif op == "raise-pass":
        return ast.Pass()
    elif op == "add-sub":
        node.op = ast.Sub() if isinstance(node.op, ast.Add) else ast.Add()
    return node


class _Mutator(ast.NodeTransformer):
    def __init__(self, index, op):
        self.index = index
        self.op = op
        self.seen = -1
        self.line = None

    def generic_visit(self, node):
        self.seen += 1
        if self.seen == self.index:
            self.line = node.lineno
            replaced = apply(node, self.op)
            if replaced is not node:
                return ast.copy_location(replaced, node)
            return node
        return super().generic_visit(node)


def mutants(source, limit=None, rng=None, reached=None):
    """[(index, operator, line, mutated source)] for one module's
    source: every site, or `limit` of them chosen by `rng`. The
    index counts the walk order of `sites`, so a mutant is named by
    (index, operator) and reproduces from the same source."""
    tree = ast.parse(source)
    all_sites = sites(tree, reached)
    chosen = list(range(len(all_sites)))
    if limit is not None and limit < len(chosen):
        chosen = sorted((rng or random.Random(0)).sample(chosen, limit))
    out = []
    for i in chosen:
        node, op = all_sites[i]
        fresh = ast.parse(source)
        fresh_sites = sites(fresh, reached)
        target, _op = fresh_sites[i]
        line = target.lineno
        new = apply(target, op)
        if new is not target:
            _replace(fresh, target, new)
        try:
            text = ast.unparse(fresh)
        except Exception:   # a shape unparse cannot write back
            continue
        out.append((i, op, line, text))
    return out


def _replace(tree, old, new):
    """Swap `old` for `new` wherever it hangs in the tree."""
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if value is old:
                setattr(parent, field, new)
                return True
            if isinstance(value, list):
                for k, item in enumerate(value):
                    if item is old:
                        value[k] = new
                        return True
    return False


# ------------------------------------------------------------------
# The kill
# ------------------------------------------------------------------

class Timeout(BaseException):
    """Raised by the alarm. A BaseException, so a checker's own
    `except Exception` (the corpus tool contains every raise of the
    reader it is checking) cannot swallow it and loop on."""


def _alarm(seconds):
    """A SIGALRM-based timeout where the platform has one; a no-op
    elsewhere (the report says which)."""
    if not hasattr(signal, "SIGALRM") or not seconds:
        return None

    def ring(_signum, _frame):
        raise Timeout()
    old = signal.signal(signal.SIGALRM, ring)
    signal.alarm(int(seconds))
    return old


def _disarm(old):
    if old is None:
        return
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old)


def load_mutant(real, text):
    """The mutated module, executed from its source under the real
    module's name and file (so its own imports resolve)."""
    mod = types.ModuleType(real.__name__)
    mod.__file__ = real.__file__
    mod.__package__ = real.__package__
    code = compile(text, real.__file__, "exec")
    exec(code, mod.__dict__)
    return mod


def outcomes(targets, corpora):
    """{target: [(outcome, notes) per entry]} of one replay, no
    tracing: the accepted/refused/crash answer and what the checker
    noted on the way (the key chosen, a digest of what the reader
    returned, each operation's answer), so a mutant that accepts the
    same entries but reads them differently is still told apart."""
    out = {}
    for target in targets:
        res = []
        for entry in corpora[target]:
            try:
                res.append((B.check(target, entry), tuple(B.NOTES)))
            except B.Crash:
                res.append(("crash", ()))
        out[target] = res
    return out


_RUNNER_DIR = os.path.join(ROOT, "runner") + os.sep


def _project_modules():
    """The loaded modules a mutant must reach: every module whose
    file is under the runner's directory, whatever name it was
    imported by (the package's, or a role folder's when the runner
    was started as a script), the corpus tool itself included."""
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        path = getattr(mod, "__file__", None)
        if isinstance(path, str) and os.path.abspath(path).startswith(
                _RUNNER_DIR):
            yield mod


def rebind(real, mutant):
    """Point every reference to the real module -- the module itself,
    and its functions and classes re-exported by name -- held by any
    loaded module of the project at the mutant's, and return the
    undo list for unbind(). A module imports a reader under its own
    alias (`from runner.guard import security as _security`) and the
    agent module re-exports readers by name
    (`answer_queries = _queries.answer_queries`); the mutant has to
    sit in both places to be read."""
    undo = []
    for mod in _project_modules():
        if mod is real or mod is mutant:
            continue
        for attr, value in list(vars(mod).items()):
            if value is real:
                replacement = mutant
            elif (isinstance(value, (types.FunctionType, type))
                    and getattr(value, "__module__", None) == real.__name__
                    and getattr(real, getattr(value, "__name__", ""), None)
                    is value):
                replacement = getattr(mutant, value.__name__, None)
                if replacement is None:
                    continue
            else:
                continue
            undo.append((mod, attr, value))
            try:
                setattr(mod, attr, replacement)
            except (AttributeError, TypeError):
                undo.pop()
    return undo


def unbind(undo):
    for mod, attr, value in reversed(undo):
        try:
            setattr(mod, attr, value)
        except (AttributeError, TypeError):
            pass


def kill(alias, text, targets, corpora, baseline, timeout=20):
    """"killed", "survived", "timeout" or "broken" for one mutant of
    the module behind `alias`, replayed over the corpora of
    `targets` against the baseline outcomes."""
    real = getattr(B, alias)
    try:
        mod = load_mutant(real, text)
    except Exception:
        return "broken"      # the mutant does not even import
    undo = rebind(real, mod)
    setattr(B, alias, mod)
    old = _alarm(timeout)
    try:
        got = B._with_rig(lambda: outcomes(targets, corpora))
    except Timeout:
        return "timeout"
    except Exception:
        return "killed"      # a raise the checker did not expect
    finally:
        _disarm(old)
        setattr(B, alias, real)
        unbind(undo)
    return "killed" if got != baseline else "survived"


def reached_lines(name, targets):
    """The lines of one module's file the corpora of `targets` reach,
    from their committed arc maps (both ends of every arc)."""
    lines = set()
    for target in targets:
        path = B.arcs_path(target)
        try:
            with open(path, encoding="utf-8") as fh:
                rows = json.load(fh).get("arcs") or []
        except (OSError, ValueError):
            continue
        for row in rows:
            if (isinstance(row, list) and len(row) == 3
                    and str(row[0]).endswith("/" + name + ".py")):
                lines.update(int(x) for x in row[1:] if int(x) > 0)
    return lines


def targets_for(name):
    """The corpus targets whose readers include this module's file,
    minus the ones that read it through the agent module."""
    out = []
    for target, spec in B.TARGETS.items():
        if target in THROUGH_AGENT:
            continue
        if any(os.path.basename(f) == name + ".py" for f in spec["files"]):
            out.append(target)
    return out


def run(modules, limit=None, seed=0, timeout=20, out=print):
    """Mutate the modules, replay, and answer the report."""
    rng = random.Random(seed)
    corpora = {t: B.load(B.corpus_path(t)) for t in B.TARGETS}
    report = {"bluemonday": 1, "Agent-Stamp": STAMP, "kind": "survivors",
              "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "head": B.head_sha()[:12], **B._environment(),
              "seed": seed, "limit": limit, "timeout": timeout,
              "alarm": hasattr(signal, "SIGALRM"),
              "through_agent": sorted(THROUGH_AGENT), "modules": {}}
    t0 = time.perf_counter()
    for name in modules:
        alias = MODULES[name]
        real = getattr(B, alias)
        targets = targets_for(name)
        if not targets:
            out(f"{name}: no target reads it directly; skipped")
            continue
        with open(real.__file__, encoding="utf-8") as fh:
            source = fh.read()
        lines = source.splitlines()
        reached = reached_lines(name, targets)
        baseline = B._with_rig(lambda: outcomes(targets, corpora))
        tally = {"killed": 0, "survived": 0, "timeout": 0, "broken": 0}
        survivors = []
        made = mutants(source, limit, rng, reached or None)
        for index, op, line, text in made:
            verdict = kill(alias, text, targets, corpora, baseline, timeout)
            tally[verdict] += 1
            if verdict in ("survived", "timeout"):
                survivors.append({"index": index, "op": op, "line": line,
                                  "verdict": verdict,
                                  "text": lines[line - 1].strip()[:120]
                                  if 0 < line <= len(lines) else ""})
        report["modules"][name] = {
            "file": os.path.relpath(real.__file__, ROOT).replace(os.sep, "/"),
            "targets": targets, "entries": sum(len(corpora[t]) for t in targets),
            "reached_lines": len(reached),
            "mutants": len(made), **tally, "survivors": survivors}
        out(f"{name}: {len(made)} mutants over {targets}: "
            f"{tally['killed']} killed, {tally['survived']} survived, "
            f"{tally['timeout']} timeouts, {tally['broken']} broken")
        for s in survivors[:40]:
            out(f"  survivor {s['op']:12s} line {s['line']:5d}  {s['text']}")
    report["seconds"] = round(time.perf_counter() - t0, 1)
    return report


def write_report(report):
    os.makedirs(B.CORPUS_DIR, exist_ok=True)
    tmp = REPORT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=True, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, REPORT)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--module", action="append", choices=sorted(MODULES),
                    help="a reader to mutate (default: all of them)")
    ap.add_argument("--limit", type=int, default=None,
                    help="mutants per module, sampled by --seed "
                         "(default: every site)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=20,
                    help="seconds a mutant's replay may take (0: none)")
    ap.add_argument("--no-record", action="store_true",
                    help="print only: write neither the report nor the "
                         "run line")
    args = ap.parse_args(argv)
    modules = args.module or sorted(MODULES)
    report = run(modules, args.limit, args.seed, args.timeout)
    survived = sum(m["survived"] + m["timeout"]
                   for m in report["modules"].values())
    total = sum(m["mutants"] for m in report["modules"].values())
    print(f"survivors: {survived} of {total} mutants over "
          f"{len(report['modules'])} module(s) in {report['seconds']}s")
    if not args.no_record:
        write_report(report)
        B.record_run({"kind": "survivors", "when": report["when"],
                      "head": report["head"], "python": report["python"],
                      "platform": report["platform"], "seed": args.seed,
                      "limit": args.limit, "modules": {
                          n: {k: m[k] for k in ("mutants", "killed",
                                                "survived", "timeout",
                                                "broken")}
                          for n, m in report["modules"].items()},
                      "seconds": report["seconds"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
