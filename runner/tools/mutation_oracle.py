#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The mutation walk's oracle, derived from the tree (Q170).

    python runner/tools/mutation_oracle.py [--root DIR]
        [--target runner/guard/security.py] [--check] [--json]

The seeded mutation walk (`mutation-seeded.yml`, and the
release-only mutation job in `build.yml`, which shares the
configuration) mutates one file -- `runner/guard/security.py` --
and kills its mutants with a test selection named in
pyproject.toml's `[tool.mutmut]` table
(`pytest_add_cli_args_test_selection`). Until Q170 that selection
was the whole suite, and the walk's baseline (mutmut's stats
pass) died before any mutant ran on tests that measure the tree
the suite stands in: mutmut's copy (`mutants/`) has no git index
and carries the mutated file ballooned with one copy per mutant,
so a tracked-tree scan and a recorded-line-count comparison
cannot hold there. The signal was absent from 2026-10-26.

The selection is therefore the test modules that can kill the
mutants: the modules that *load* the mutated file. This tool
derives that list from the tree so it cannot rot silently:

- every `.py` file under `runner/` is a module (the airgap
  sweep's fixture tree is not part of the suite and is skipped,
  as pyproject's own ignore for the walk already states);
- an edge A -> B stands for every import statement in A --
  top-level or function-level (a lazy import loads the module
  exactly when it matters, e.g. `runner/tools/approvalguard.py`'s
  `_load_security`) -- in both styles this tree uses: the
  `runner.`-prefixed form (`from runner.guard import security`)
  and the bare-package form (`from guard import security`,
  `import send_job`), resolved by module suffix and, for a
  single name, by file basename;
- a name that appears only as data (a file list, a string) is
  not an import and makes no edge: `runner/ops/core.py` names
  `runner/guard/security.py` in its file list, so
  `runner/tests/test_core.py` loads `runner/ops/core.py` and
  nothing more, and is not in the selection;
- a test module is selected when a chain of edges reaches the
  mutated file from it.

`--check` compares the derived list with the selection recorded
in pyproject.toml and exits 1 on any difference, naming both
directions. `runner/tests/test_mutation_oracle.py` recomputes
the derivation in the suite and holds the recorded list to it,
so a module that starts or stops loading the mutated file
turns the suite red until the list is regenerated with this
tool. Stdlib only.
"""

import argparse
import ast
import json
import os
import re
import sys

TARGET = "runner/guard/security.py"
TEST_PREFIX = "runner/tests/test_"
SKIP_DIRS = {"__pycache__"}
SKIP_PREFIXES = ("runner/tests/airgap/",)


def module_name(root, path):
    """The dotted name of the module at `path` under `root`."""
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    if not rel.endswith(".py"):
        return None
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def tree_modules(root):
    """{dotted name: path} for every module under runner/."""
    out = {}
    base = os.path.join(root, "runner")
    for dirpath, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if any(rel.startswith(p) for p in SKIP_PREFIXES):
                continue
            mod = module_name(root, path)
            if mod:
                out[mod] = path
    return out


def _indexes(modules):
    suffix = {}
    basename = {}
    for mod in modules:
        parts = mod.split(".")
        for i in range(len(parts)):
            suffix.setdefault(".".join(parts[i:]), set()).add(mod)
        basename.setdefault(parts[-1], set()).add(mod)
    return suffix, basename


def imports_of(path, mod, modules, suffix, basename):
    """The in-tree modules one file's import statements load.

    Every Import / ImportFrom node in the file, at any depth
    (a function-level import is a load when the function runs).
    A file that does not parse (a fixture specimen) loads
    nothing for this derivation.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError, ValueError):
        return set()
    pkg = mod.rsplit(".", 1)[0] if "." in mod else ""
    out = set()

    def resolve(dotted):
        if not dotted:
            return
        if dotted in modules:
            out.add(dotted)
        elif dotted in suffix:
            out.update(suffix[dotted])
        elif "." not in dotted:
            out.update(basename.get(dotted, ()))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                for i in range(1, len(parts) + 1):
                    dotted = ".".join(parts[:i])
                    if dotted in modules:
                        out.add(dotted)
                    elif dotted in suffix:
                        out.update(suffix[dotted])
                if "." not in alias.name:
                    out.update(basename.get(alias.name, ()))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".") if pkg else []
                if node.level > 1:
                    base = base[:len(base) - (node.level - 1)]
                modpart = ".".join(
                    base + ([node.module] if node.module else []))
            else:
                modpart = node.module or ""
            resolve(modpart)
            for alias in node.names:
                if alias.name != "*":
                    resolve((modpart + "." + alias.name)
                            if modpart else alias.name)
    return out


def import_graph(root):
    """{module: set of in-tree modules it loads} for the tree."""
    modules = tree_modules(root)
    suffix, basename = _indexes(modules)
    return modules, {mod: imports_of(path, mod, modules, suffix,
                                     basename)
                     for mod, path in modules.items()}


def derive(root, target=TARGET):
    """The sorted selection: test-module paths under `root`
    whose import chain reaches `target` (a path under root)."""
    modules, graph = import_graph(root)
    target_mod = module_name(root, os.path.join(root, target))
    if target_mod not in modules:
        raise ValueError("target %s is not a module in %s"
                         % (target, root))
    reverse = {}
    for mod, deps in graph.items():
        for dep in deps:
            reverse.setdefault(dep, set()).add(mod)
    seen = {target_mod}
    stack = [target_mod]
    while stack:
        cur = stack.pop()
        for up in reverse.get(cur, ()):
            if up not in seen:
                seen.add(up)
                stack.append(up)
    paths = []
    for mod in seen:
        rel = os.path.relpath(modules[mod], root).replace(os.sep, "/")
        if rel.startswith(TEST_PREFIX):
            paths.append(rel)
    return sorted(paths)


def recorded_selection(root):
    """The selection recorded in pyproject.toml's [tool.mutmut]
    table (`pytest_add_cli_args_test_selection`), read without
    tomllib so the tool runs on the 3.9 floor too: the table's
    own list literal, comments stripped."""
    with open(os.path.join(root, "pyproject.toml"),
              encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"^pytest_add_cli_args_test_selection\s*=\s*"
                  r"\[(.*?)\]", src, re.M | re.S)
    if not m:
        raise ValueError("no pytest_add_cli_args_test_selection "
                         "list in pyproject.toml")
    body = []
    for line in m.group(1).splitlines():
        out, in_str = [], False
        for ch in line:
            if ch == '"':
                in_str = not in_str
            if ch == "#" and not in_str:
                break
            out.append(ch)
        body.append("".join(out))
    return sorted(re.findall(r'"([^"]+)"', "\n".join(body)))


def check(root, target=TARGET):
    """(derived, recorded, only_derived, only_recorded)."""
    derived = derive(root, target)
    recorded = recorded_selection(root)
    return (derived, recorded,
            [p for p in derived if p not in recorded],
            [p for p in recorded if p not in derived])


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    ap.add_argument("--target", default=TARGET)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when pyproject.toml's recorded "
                         "selection differs from the derivation")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    derived, recorded, only_derived, only_recorded = check(
        root, a.target)
    if a.json:
        print(json.dumps({"derived": derived, "recorded": recorded,
                          "only_derived": only_derived,
                          "only_recorded": only_recorded},
                         indent=1))
    elif a.check:
        for path in only_derived:
            print("in the derivation, not in pyproject.toml: %s"
                  % path)
        for path in only_recorded:
            print("in pyproject.toml, not in the derivation: %s"
                  % path)
        if only_derived or only_recorded:
            print("mutation oracle: the recorded selection has "
                  "rotted; regenerate it with "
                  "runner/tools/mutation_oracle.py")
            return 1
        print("mutation oracle: pyproject.toml's selection is "
              "the derivation (%d modules)" % len(derived))
    else:
        for path in derived:
            print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
