"""Extracted ops modules read the runner; they never write onto it.

Agent-Chat-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

The 2026-10-25 line-reduction series renamed bare names to `R.name`
by pattern. Where the bare name was a local being bound, the rename
turned it into an attribute store on the shared runner module:
`for R._mtime, path, job_id in chosen:` in context.py, and
`R._posture = R._load_mod(...)` in main.py. (Setting `_LOG_FILE`,
which runner.py did with `global`, is the one intended write.) Nothing raised; every
call quietly overwrote a runner global, which a concurrent thread or
a test's patch would then see. The suite's NameError guard
(test_script_context) cannot catch this shape, so this test does:
any store, delete or augmented assignment whose target is an
attribute of the runner handle (`R.x`, `_runner().x`) in
runner/ops/ fails here.
"""
import ast
import glob
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
OPS = os.path.join(ROOT, "runner", "ops")

_HANDLES = {"R", "_R"}

# Runner state an extracted function is meant to set, as runner.py
# did with `global`: the log file path that log() writes to.
_INTENDED = {"_LOG_FILE"}


def _is_runner_handle(node):
    if isinstance(node, ast.Name) and node.id in _HANDLES:
        return True
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "_runner")


def _runner_writes(source, path):
    found = []
    for node in ast.walk(ast.parse(source, path)):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.ctx, (ast.Store, ast.Del))
                and _is_runner_handle(node.value)
                and node.attr not in _INTENDED):
            found.append(f"{os.path.relpath(path, ROOT)}:{node.lineno} "
                         f"writes runner.{node.attr}")
    return found


class ExtractedModulesDoNotWriteRunner(unittest.TestCase):
    def test_no_ops_module_assigns_onto_the_runner(self):
        offenders = []
        for path in sorted(glob.glob(os.path.join(OPS, "*.py"))):
            with open(path, encoding="utf-8") as fh:
                offenders += _runner_writes(fh.read(), path)
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_every_global_statement_names_a_module_binding(self):
        # The extractions carried `global _LOG_FILE` into modules that
        # never bind it (the write goes to R._LOG_FILE); pyrefly fails
        # the typecheck gate on it (Q55).
        offenders = []
        for path in sorted(glob.glob(os.path.join(OPS, "*.py"))):
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            bound = set()
            for node in tree.body:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                        bound.add(sub.id)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)):
                    bound.add(node.name)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    bound.update((a.asname or a.name).split(".")[0]
                                 for a in node.names)
            for node in ast.walk(tree):
                if isinstance(node, ast.Global):
                    offenders += [f"{os.path.relpath(path, ROOT)}:{node.lineno} "
                                  f"global {n}" for n in node.names
                                  if n not in bound]
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_mangle_shapes_are_detected(self):
        bad = ("def f(chosen):\n"
               "    R = _runner()\n"
               "    for R._mtime, p in chosen:\n"
               "        pass\n"
               "    R._posture = 1\n"
               "    _runner().x += 1\n")
        self.assertEqual(len(_runner_writes(bad, os.path.join(OPS, "x.py"))), 3)
        ok = ("def f(chosen):\n"
              "    R = _runner()\n"
              "    for _mtime, p in chosen:\n"
              "        R.log(p)\n"
              "    _posture = R._load_mod('a', 'b')\n")
        self.assertEqual(_runner_writes(ok, os.path.join(OPS, "y.py")), [])


class RunnerHasNoShadowedDefs(unittest.TestCase):
    def test_no_def_in_runner_py_is_rebound_later(self):
        # An extraction that leaves the original def behind and then
        # binds the name to the module's copy (`_transports_arg =
        # _cli._transports_arg`, 2026-10-25) leaves nineteen dead
        # lines that coverage reports as never executed. The def or
        # the binding, not both.
        path = os.path.join(ROOT, "runner", "runner.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), path)
        ends = {}
        rebound = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                ends[node.name] = node.end_lineno
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id in ends:
                        rebound.append(f"{t.id}: def ends L{ends[t.id]}, "
                                       f"rebound L{node.lineno}")
        self.assertEqual(rebound, [], "\n".join(rebound))


if __name__ == "__main__":
    unittest.main()
