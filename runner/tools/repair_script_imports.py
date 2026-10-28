#!/usr/bin/env python3
"""Turn module-level package imports in runner.py into _load_mod
loads, and give every loaded module its hidden import.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

    python3 runner/tools/repair_script_imports.py [--check]

runner.py is run three ways: as `runner.runner` (the suite), as a
script (`python3 ~/.homing-pigeon/runner.py`, where `runner` is the
file and not the package), and frozen (the one-file binaries, where
a module not named as a hidden import is not there). A line like

    from runner.ops.helpers import snapshot_outside, append_bounded_log

works in the first and fails in the other two. This tool rewrites
each such line in place:

    _helpers = _load_mod("runner.ops.helpers", "ops.helpers")
    if _helpers is None:
        raise ImportError("runner/ops/helpers.py is missing")
    snapshot_outside = _helpers.snapshot_outside
    append_bounded_log = _helpers.append_bounded_log

and adds `--hidden-import runner.ops.helpers` to every pyinstaller
line in .github/workflows/build.yml. An extracted module that reaches
back with `from runner import runner as R` inside a function is
rewritten to the live lookup (`R = _runner()`), with the helper added
to that module. --check reports and exits 1 without writing.
runner/tests/test_script_context.py is the guard that fails the push
when a line slipped through.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
RUNNER = os.path.join(ROOT, "runner", "runner.py")
BUILD = os.path.join(ROOT, ".github", "workflows", "build.yml")

_IMPORT = re.compile(
    r"^from (runner\.(?P<role>[a-z_]+)\.(?P<mod>[A-Za-z0-9_]+)) import "
    r"(?P<names>\([^)]*\)|[^\n]+?)\s*(?:#[^\n]*)?$", re.M)
_REACH_BACK = re.compile(r"^(?P<indent>[ \t]+)from runner import runner as R\s*$", re.M)

_RUNNER_HELPER = '''
try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore
'''


def _names(text):
    text = text.strip()
    if text.startswith("("):
        text = text[1:-1]
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if " as " in part:
            src, alias = [p.strip() for p in part.split(" as ", 1)]
        else:
            src = alias = part
        out.append((src, alias))
    return out


def rewrite_runner(src):
    changed = []

    def repl(m):
        full, role, mod = m.group(1), m.group("role"), m.group("mod")
        var = "_" + mod
        lines = [f'{var} = _load_mod("{full}", "{role}.{mod}")',
                 f"if {var} is None:",
                 f'    raise ImportError("runner/{role}/{mod}.py is missing")']
        for name, alias in _names(m.group("names")):
            lines.append(f"{alias} = {var}.{name}")
        changed.append(full)
        return "\n".join(lines)

    return _IMPORT.sub(repl, src), changed


def rewrite_module(path):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    if not _REACH_BACK.search(src):
        return False
    new = _REACH_BACK.sub(lambda m: m.group("indent") + "R = _runner()", src)
    if not _has_runner(new):
        # after the import block
        m = list(re.finditer(r"^(?:import|from) [^\n]+\n", new, re.M))
        at = m[-1].end() if m else 0
        new = new[:at] + _RUNNER_HELPER + new[at:]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)
    return True


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    unknown = [a for a in argv if a != "--check"]
    if unknown:
        # The tool writes in place; a flag it does not know (--help
        # included) must not be read as "go ahead".
        print(__doc__.split("\n\n")[1] if "\n\n" in __doc__ else __doc__,
              file=sys.stderr)
        print(f"unknown argument(s): {' '.join(unknown)}", file=sys.stderr)
        return 2
    check = "--check" in argv
    with open(RUNNER, encoding="utf-8") as fh:
        src = fh.read()
    new, changed = rewrite_runner(src)
    with open(BUILD, encoding="utf-8") as fh:
        build = fh.read()
    mods = set(re.findall(r'_load_mod\("(runner\.[A-Za-z0-9_.]+)"', new))
    missing = sorted(m for m in mods if "--hidden-import " + m + " " not in build)
    reach = []
    for role in ("ops", "wire", "guard", "oracle"):
        d = os.path.join(ROOT, "runner", role)
        for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            p = os.path.join(d, name)
            if name.endswith(".py"):
                with open(p, encoding="utf-8") as fh:
                    if _REACH_BACK.search(fh.read()):
                        reach.append(p)
    if check:
        for c in changed:
            print(f"package import in runner.py: {c}")
        for m in missing:
            print(f"no hidden import in build.yml: {m}")
        for p in reach:
            print(f"reach-back import in {os.path.relpath(p, ROOT)}")
        return 1 if (changed or missing or reach) else 0
    if changed:
        with open(RUNNER, "w", encoding="utf-8") as fh:
            fh.write(new)
        print("rewrote in runner.py: " + ", ".join(changed))
    if missing:
        # Only the runner's own build lines, not the installer's.
        anchor = "--hidden-import runner._version "
        add = "".join("--hidden-import %s " % m for m in missing)
        fixed = []
        for line in build.split("\n"):
            if "--name homing-pigeon runner/runner.py" in line:
                line = line.replace(anchor, anchor + add, 1)
            fixed.append(line)
        build = "\n".join(fixed)
        with open(BUILD, "w", encoding="utf-8") as fh:
            fh.write(build)
        print("hidden imports added: " + ", ".join(missing))
    for p in reach:
        if rewrite_module(p):
            print("reach-back rewritten: " + os.path.relpath(p, ROOT))
    finish_modules()
    return 0


# ---------------------------------------------------------------------------
# The rest of what an extraction leaves behind: stdlib imports it did
# not carry, runner globals used as bare names, sibling calls the suite
# cannot patch, and names the runner module no longer exports.
# ---------------------------------------------------------------------------

_HELPER_MARK = "def _runner()"
_HELPER_RE = re.compile(r"^def _runner\(\)|^    from (?:runner\.)?ops\.live import _runner$", re.M)


def _has_runner(src):
    """True when the module defines _runner or imports the shared one."""
    return bool(_HELPER_RE.search(src))

_CONFVAL_IMPORT = '''try:
    from runner.guard import confval as _confval
except ImportError:  # running from inside runner/ as __main__
    from guard import confval as _confval  # type: ignore
'''
_STDLIB = set(getattr(sys, "stdlib_module_names", ()))


def _undefined(tree):
    import ast
    import builtins
    defined = set(dir(builtins)) | {"__file__", "__name__", "__doc__",
                                    "__spec__", "__package__"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                defined.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            defined.add(node.name)
            args = getattr(node, "args", None)
            if args is not None:
                for arg in args.args + args.kwonlyargs + args.posonlyargs:
                    defined.add(arg.arg)
                if args.vararg:
                    defined.add(args.vararg.arg)
                if args.kwarg:
                    defined.add(args.kwarg.arg)
        elif isinstance(node, ast.Lambda):
            for arg in node.args.args + node.args.kwonlyargs:
                defined.add(arg.arg)
        elif isinstance(node, ast.Name) and isinstance(
                node.ctx, (ast.Store, ast.Del)):
            defined.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            defined.update(node.names)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) \
                and node.id not in defined:
            out.add(node.id)
    return sorted(out)


def _runner_module():
    sys.path.insert(0, ROOT)
    import importlib
    return importlib.import_module("runner.runner")


def _extracted_modules(runner_src):
    """(var, module, path) for every ops module runner.py loads."""
    out = []
    for m in re.finditer(r'^(?P<var>[A-Za-z_][A-Za-z0-9_]*) = (?:_required)?_load_mod\("runner\.ops\.(?P<mod>[A-Za-z0-9_]+)", "ops\.(?P=mod)"[^)\n]*\)', runner_src, re.M):
        path = os.path.join(ROOT, "runner", "ops", m.group("mod") + ".py")
        if os.path.isfile(path):
            out.append((m.group("var"), m.group("mod"), path))
    return out


def finish_modules():
    import ast
    with open(RUNNER, encoding="utf-8") as fh:
        runner_src = fh.read()
    RR = _runner_module()
    touched = []
    for var, mod, path in _extracted_modules(runner_src):
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        before = src
        tree = ast.parse(src)
        defs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name != "_runner"]
        names = _undefined(tree)
        add_imports, globs = [], []
        for n in names:
            if n in ("datetime", "timezone", "timedelta"):
                add_imports.append("from datetime import datetime, timezone, timedelta")
            elif n in _STDLIB:
                add_imports.append("import " + n)
            elif hasattr(RR, n):
                globs.append(n)
        if globs or not _has_runner(src) and (globs or "sys.platform" in src):
            if not _has_runner(src):
                m = list(re.finditer(r"^(?:import|from) [^\n]+\n", src, re.M))
                at = m[-1].end() if m else 0
                src = src[:at] + _RUNNER_HELPER + src[at:]
        for n in globs:
            if n == "_confval":
                # The typed readers are a module of their own; the
                # defaults registry's call-site scan reads them by
                # name, so they are imported, not reached through the
                # runner.
                if "import confval as _confval" not in src:
                    m = list(re.finditer(r"^(?:import|from) [^\n]+\n", src, re.M))
                    at = m[-1].end() if m else 0
                    src = src[:at] + _CONFVAL_IMPORT + src[at:]
                continue
            src = re.sub(r"(?<![\w.])%s\b(?!\s*=[^=])" % re.escape(n),
                         "_runner().%s" % n, src)
        if _has_runner(src):
            for n in defs:
                src = re.sub(r"(?<![\w.])%s\(" % re.escape(n),
                             "_runner().%s(" % n, src)
                src = src.replace("def _runner().%s(" % n, "def %s(" % n)
            src = re.sub(r"(?<![\w.])sys\.platform\b",
                         "_runner().sys.platform", src)
            # the helper's own getattr string, if a rewrite reached it
            src = src.replace('getattr(m, "_runner()._load_mod", None)',
                              'getattr(m, "_load_mod", None)')
        uniq = []
        for a in add_imports:
            if a not in uniq and not re.search("^" + re.escape(a) + "$", src, re.M):
                uniq.append(a)
        if uniq:
            m = re.match(r'(\s*(?:#[^\n]*\n)*\s*(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')\s*\n)', src)
            at = m.end() if m else 0
            src = src[:at] + "\n".join(uniq) + "\n" + src[at:]
        if src != before:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)
            touched.append(mod)
        # re-export every top-level name on the runner module -- for
        # the modules extracted out of runner.py (the ones that reach
        # back through _runner()), never for a sibling that was its
        # own module from the start, and never over a def runner.py
        # still has.
        if not _has_runner(src):
            continue
        runner_defs = set(re.findall(r"^(?:def|class) ([A-Za-z_][A-Za-z0-9_]*)", runner_src, re.M))
        tree = ast.parse(src)
        top = []
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                top.append(n.name)
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        top.append(t.id)
        missing = [n for n in top if n != "_runner" and n not in runner_defs
                   and not re.search(r"^%s = " % re.escape(n), runner_src, re.M)]
        if missing:
            head = re.search(r'^%s = (?:_required)?_load_mod\("runner\.ops\.%s", "ops\.%s"[^)\n]*\)\n' % (re.escape(var), mod, mod), runner_src, re.M)
            end = head.end()
            tail = runner_src[end:]
            bm = re.match(r'(?:if %s is None:\n    raise ImportError\([^\n]+\n)?(?:(?:#[^\n]*\n)|(?:[A-Za-z_][A-Za-z0-9_]* = %s\.[A-Za-z_][A-Za-z0-9_.]*(?: if [^\n]+)?\n))*' % (re.escape(var), re.escape(var)), tail)
            end += bm.end()
            extra = "".join("%s = %s.%s\n" % (n, var, n) for n in missing)
            runner_src = runner_src[:end] + extra + runner_src[end:]
            touched.append(mod + " (re-exports)")
    with open(RUNNER, "w", encoding="utf-8") as fh:
        fh.write(runner_src)
    if touched:
        print("finished: " + ", ".join(touched))


if __name__ == "__main__":
    sys.exit(main())
