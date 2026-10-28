#!/usr/bin/env python3
# Agent-Stamp: c0000327-6a7b-42df-81b9-21136287db1c
"""Line coverage of the suite with the standard library alone.

    python runner/tools/stdlib_coverage.py --out coverage.json [--jobs N]
                                           [--source runner] [module ...]

coverage.py is the usual tool, but a box that cannot reach PyPI (an
air-gapped bench, a sandboxed rig, an old interpreter's site-packages
that cannot take a wheel) still has to say what the suite runs. This
records line events with ``sys.monitoring`` (Python 3.12 and later),
disabling each line after its first hit so a hot loop costs nothing,
and writes a JSON report in the shape ``coverage json`` writes, so
``runner/tools/coverage_gaps.py`` reads it unchanged.

A statement is a line that carries a bytecode instruction other than
the frame's own entry (``RESUME``), found by walking every code object
compiled from the file: the same notion of "line that can run" the
interpreter uses, so the report never counts a comment, a blank line
or a continuation line. Branches are not measured (``num_branches``
is 0). Only the suite's own process is traced: code a test runs in a
child interpreter is not counted, so a module driven through a
subprocess reads lower here than under coverage.py with its
subprocess hook. With ``--subprocess`` a ``sitecustomize`` on
``PYTHONPATH`` traces every child Python that inherits the suite's
environment too, each dumping its hits at exit; a child started with
a scrubbed environment, ``-I`` or ``-S``, or ending in ``os._exit``,
is still not counted. Either way the number is a floor, never an
over-count.

With ``--jobs N`` the discovered test modules are sharded across N
child interpreters, each traced the same way, and their executed
lines are merged. Exit status is the suite's: 0 only when every
shard passed.
"""

import argparse
import dis
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

_TOOL_ID = 4  # sys.monitoring.COVERAGE_ID
_SKIP_PARTS = ("/tests/", "/tools/")


def _root():
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _shipped(path, source_dir):
    path = os.path.abspath(path).replace("\\", "/")
    src = source_dir.replace("\\", "/").rstrip("/") + "/"
    if not path.startswith(src) or not path.endswith(".py"):
        return False
    return not any(part in "/" + path[len(src):] for part in _SKIP_PARTS)


def statements(path):
    """Every line in *path* that carries a runnable instruction."""
    try:
        with open(path, encoding="utf-8") as fh:
            code = compile(fh.read(), path, "exec")
    except (OSError, SyntaxError, ValueError, UnicodeDecodeError):
        return set()
    found = set()
    todo = [code]
    while todo:
        co = todo.pop()
        for ins in dis.get_instructions(co):
            if ins.opname in ("RESUME", "CACHE"):
                continue
            line = ins.positions.lineno if ins.positions else None
            if line:
                found.add(line)
        todo.extend(c for c in co.co_consts if hasattr(c, "co_code"))
    return found


class Recorder:
    """Collects (file, line) hits for files under *source_dir*."""

    def __init__(self, source_dir):
        self.source_dir = os.path.abspath(source_dir)
        self._prefix = self.source_dir.replace("\\", "/").rstrip("/") + "/"
        self._cwd = os.getcwd().replace("\\", "/").rstrip("/") + "/"
        self.hits = {}
        self._keep = {}

    # The callback runs inside the code being measured, which may have
    # os or os.path patched to raise (test_install_edges patches
    # os.path.abspath). It calls nothing a test can patch: string and
    # dict operations only, against the source and working directories
    # captured when the recorder was made.
    def _wanted(self, filename):
        keep = self._keep.get(filename)
        if keep is None:
            path = filename.replace("\\", "/")
            if not (path.startswith("/") or path[1:3] == ":/"):
                path = self._cwd + path
            rest = path[len(self._prefix):]
            keep = (path.startswith(self._prefix) and path.endswith(".py")
                    and "/tests/" not in "/" + rest
                    and "/tools/" not in "/" + rest)
            keep = self._keep[filename] = (path if keep else False)
        return keep

    def _line(self, code, line):
        path = self._wanted(code.co_filename)
        if path:
            hits = self.hits.get(path)
            if hits is None:
                hits = self.hits[path] = set()
            hits.add(line)
        return sys.monitoring.DISABLE

    def start(self):
        """Start tracing; False when this process is already traced
        (a shard under --subprocess: its hook dumps the hits)."""
        mon = sys.monitoring
        self.active = mon.get_tool(_TOOL_ID) is None
        if not self.active:
            return False
        mon.use_tool_id(_TOOL_ID, "stdlib_coverage")
        mon.register_callback(_TOOL_ID, mon.events.LINE, self._line)
        mon.set_events(_TOOL_ID, mon.events.LINE)
        return True

    def stop(self):
        if not getattr(self, "active", False):
            return
        self.active = False
        mon = sys.monitoring
        mon.set_events(_TOOL_ID, 0)
        mon.register_callback(_TOOL_ID, mon.events.LINE, None)
        mon.free_tool_id(_TOOL_ID)


def discover_modules(start_dir, top_dir):
    """Module names the suite's discovery would load, in order."""
    suite = unittest.defaultTestLoader.discover(start_dir, top_level_dir=top_dir)
    names = []

    def walk(s):
        for t in s:
            if isinstance(t, unittest.TestSuite):
                walk(t)
            else:
                mod = type(t).__module__
                if mod not in names and mod != "unittest.loader":
                    names.append(mod)

    walk(suite)
    return names


def run_inprocess(modules, source_dir, start_dir, top_dir):
    """Run the suite (or *modules*) traced; return (hits, ok, ran)."""
    rec = Recorder(source_dir)
    rec.start()
    try:
        loader = unittest.defaultTestLoader
        if modules:
            suite = loader.loadTestsFromNames(modules)
        else:
            suite = loader.discover(start_dir, top_level_dir=top_dir)
        runner = unittest.TextTestRunner(stream=sys.stderr, verbosity=0)
        result = runner.run(suite)
    finally:
        rec.stop()
    return rec.hits, result.wasSuccessful(), result.testsRun


def report(hits, source_dir):
    """The coverage.py JSON shape for every shipped file under source."""
    files = {}
    tot_s = tot_m = 0
    norm = {}
    for key, lines in hits.items():
        norm.setdefault(os.path.normcase(os.path.abspath(key)),
                        set()).update(lines)
    for dirpath, dirnames, filenames in os.walk(source_dir):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if not _shipped(path, source_dir):
                continue
            stmts = statements(path)
            if not stmts:
                continue
            ran = norm.get(os.path.normcase(os.path.abspath(path)),
                           set()) & stmts
            missing = sorted(stmts - ran)
            pct = 100.0 * len(ran) / len(stmts)
            files[os.path.relpath(path, _root()).replace("\\", "/")] = {
                "executed_lines": sorted(ran),
                "missing_lines": missing,
                "summary": {
                    "covered_lines": len(ran),
                    "num_statements": len(stmts),
                    "percent_covered": pct,
                    "missing_lines": len(missing),
                    "num_branches": 0,
                },
            }
            tot_s += len(stmts)
            tot_m += len(missing)
    covered = tot_s - tot_m
    return {
        "meta": {"tool": "runner/tools/stdlib_coverage.py",
                 "python": sys.version.split()[0],
                 "branch_coverage": False,
                 "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime())},
        "files": files,
        "totals": {"covered_lines": covered, "num_statements": tot_s,
                   "missing_lines": tot_m,
                   "percent_covered": (100.0 * covered / tot_s) if tot_s else 100.0,
                   "num_branches": 0, "missing_branches": 0},
    }


_SITECUSTOMIZE = r'''
# Written by runner/tools/stdlib_coverage.py --subprocess.
import os, sys
_here = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _here]
sys.modules.pop("sitecustomize", None)
try:
    import sitecustomize  # the interpreter's own, if it has one
except ImportError:
    pass
_out = os.environ.get("HP_STDLIB_COV_DIR")
_tool = os.environ.get("HP_STDLIB_COV_TOOL")
if _out and _tool and hasattr(sys, "monitoring"):
    try:
        import atexit, importlib.util, json
        _spec = importlib.util.spec_from_file_location("_hp_cov", _tool)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _rec = _mod.Recorder(os.environ["HP_STDLIB_COV_SOURCE"])
        _rec.start()
        def _dump():
            try:
                _rec.stop()
                path = os.path.join(_out, "child-%d-%d.json" % (
                    os.getpid(), id(_rec)))
                with open(path, "w") as fh:
                    json.dump({k: sorted(v) for k, v in _rec.hits.items()}, fh)
            except Exception:
                pass
        atexit.register(_dump)
    except Exception:
        pass
'''


def install_child_hook(source_dir):
    """Put the tracing sitecustomize on PYTHONPATH; return the dump dir."""
    base = tempfile.mkdtemp(prefix="stdlib-cov-site-")
    with open(os.path.join(base, "sitecustomize.py"), "w",
              encoding="utf-8") as fh:
        fh.write(_SITECUSTOMIZE)
    dumps = os.path.join(base, "hits")
    os.mkdir(dumps)
    old = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = base + (os.pathsep + old if old else "")
    os.environ["HP_STDLIB_COV_DIR"] = dumps
    os.environ["HP_STDLIB_COV_TOOL"] = os.path.abspath(__file__)
    os.environ["HP_STDLIB_COV_SOURCE"] = source_dir
    return dumps


def collect_child_hits(dumps, hits):
    """Merge every child's dump into *hits*; return the child count."""
    n = 0
    for name in sorted(os.listdir(dumps)):
        try:
            with open(os.path.join(dumps, name), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        n += 1
        for path, lines in data.items():
            hits.setdefault(path, set()).update(lines)
    return n


def _shards(modules, jobs):
    out = [[] for _ in range(jobs)]
    for i, mod in enumerate(modules):
        out[i % jobs].append(mod)
    return [s for s in out if s]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("modules", nargs="*", help="test modules (default: all)")
    ap.add_argument("--out", required=True, help="JSON report to write")
    ap.add_argument("--source", default="runner",
                    help="tree to measure, relative to the repository")
    ap.add_argument("--start-dir", default="runner/tests")
    ap.add_argument("--top-level-dir", default=".")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--subprocess", action="store_true",
                    help="also trace child Pythons that inherit the env")
    ap.add_argument("--hits-only", action="store_true",
                    help=argparse.SUPPRESS)  # a shard's raw output
    a = ap.parse_args(argv)
    if not hasattr(sys, "monitoring"):
        print("stdlib_coverage: needs Python 3.12+ (sys.monitoring)",
              file=sys.stderr)
        return 2
    root = _root()
    os.chdir(root)
    if root not in sys.path:
        sys.path.insert(0, root)
    source_dir = os.path.join(root, a.source)
    dumps = None
    if a.subprocess and not a.hits_only:
        dumps = install_child_hook(source_dir)

    if a.jobs > 1 and not a.hits_only:
        modules = a.modules or discover_modules(a.start_dir, a.top_level_dir)
        if not modules:
            print("stdlib_coverage: discovered no tests", file=sys.stderr)
            return 2
        tmp = tempfile.mkdtemp(prefix="stdlib-cov-")
        procs = []
        for i, shard in enumerate(_shards(modules, a.jobs)):
            part = os.path.join(tmp, "shard-%d.json" % i)
            cmd = [sys.executable, os.path.abspath(__file__), "--hits-only",
                   "--out", part, "--source", a.source] + shard
            procs.append((part, subprocess.Popen(cmd, cwd=root)))
        hits, ok, ran = {}, True, 0
        for part, proc in procs:
            ok = (proc.wait() == 0) and ok
            try:
                with open(part, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                ok = False
                continue
            ran += data.get("tests_run", 0)
            for path, lines in data["hits"].items():
                hits.setdefault(path, set()).update(lines)
    else:
        hits, ok, ran = run_inprocess(a.modules, source_dir, a.start_dir,
                                      a.top_level_dir)
        if a.hits_only:
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump({"tests_run": ran, "ok": ok,
                           "hits": {k: sorted(v) for k, v in hits.items()}},
                          fh)
            return 0 if ok else 1

    children = collect_child_hits(dumps, hits) if dumps else 0
    rep = report(hits, source_dir)
    rep["meta"]["child_processes"] = children
    rep["meta"]["tests_run"] = ran
    rep["meta"]["suite_passed"] = ok
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, sort_keys=True)
        fh.write("\n")
    t = rep["totals"]
    print("stdlib_coverage: %d tests, %.1f%% of %d statements (%d never run)%s"
          % (ran, t["percent_covered"], t["num_statements"],
             t["missing_lines"], "" if ok else "; SUITE FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
