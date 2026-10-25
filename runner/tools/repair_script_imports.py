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

def _runner():
    """The live runner module, looked up at call time.

    `runner.runner` when the suite or a package import loaded it,
    `__main__` when runner.py was started as a script (an install,
    the one-file binaries), where `runner` is the file itself and
    `from runner import runner` raises "'runner' is not a package".
    """
    for name in ("runner.runner", "__main__"):
        m = sys.modules.get(name)
        if m is not None and callable(getattr(m, "_load_mod", None)):
            return m
    from runner import runner as R  # a host that imported us first
    return R
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
    if "def _runner()" not in new:
        if not re.search(r"^import sys$", new, re.M):
            new = re.sub(r"^(import [a-z_]+\n)", r"\1import sys\n", new,
                         count=1, flags=re.M)
        # after the import block
        m = list(re.finditer(r"^(?:import|from) [^\n]+\n", new, re.M))
        at = m[-1].end() if m else 0
        new = new[:at] + _RUNNER_HELPER + new[at:]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)
    return True


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
