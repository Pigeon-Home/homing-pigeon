# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/repair_script_imports.py: package imports into loads.

No test ran a line of it, and it rewrites runner.py, the build workflow
and the extracted modules in place. Here every write runs against a
throwaway tree with the tool's paths pointed at it: a package import
becomes a `_load_mod` with its names bound, a missing hidden import is
added to the runner's own pyinstaller line only, a reach-back import
becomes the live lookup with its helper, and an extracted module gets
the stdlib imports it lost, its runner names reached through
`_runner()`, and its new names re-exported from runner.py. `--check`
reports and writes nothing; on this tree it finds nothing to report.
"""
import ast
import contextlib
import io
import os
import tempfile
import textwrap
import types
import unittest
from unittest import mock

from runner.tools import repair_script_imports as RS  # noqa: E402


class NamesTest(unittest.TestCase):
    def test_plain_aliased_and_parenthesized(self):
        self.assertEqual(RS._names(" a, b as c ,"), [("a", "a"), ("b", "c")])
        self.assertEqual(RS._names("(x,\n    y as z)"),
                         [("x", "x"), ("y", "z")])


class RewriteRunnerTest(unittest.TestCase):
    def test_a_package_import_becomes_a_load_with_its_names(self):
        src = textwrap.dedent("""\
            import os
            from runner.ops.helpers import snapshot_outside, append_bounded_log as abl  # why
            from runner.guard.filenames import (
                validate_file_name,
            )
            def f():
                from runner.ops.inner import nope
            """)
        new, changed = RS.rewrite_runner(src)
        self.assertEqual(changed, ["runner.ops.helpers",
                                   "runner.guard.filenames"])
        self.assertIn(textwrap.dedent("""\
            _helpers = _load_mod("runner.ops.helpers", "ops.helpers")
            if _helpers is None:
                raise ImportError("runner/ops/helpers.py is missing")
            snapshot_outside = _helpers.snapshot_outside
            abl = _helpers.append_bounded_log
            """), new)
        self.assertIn("validate_file_name = _filenames.validate_file_name",
                      new)
        self.assertIn("    from runner.ops.inner import nope", new)
        ast.parse(new)

    def test_nothing_to_rewrite_is_unchanged(self):
        src = "import os\n_x = _load_mod('runner.ops.x', 'ops.x')\n"
        self.assertEqual(RS.rewrite_runner(src), (src, []))


class RewriteModuleTest(unittest.TestCase):
    def _write(self, td, body):
        path = os.path.join(td, "mod.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent(body))
        return path

    def test_a_reach_back_becomes_the_live_lookup_with_its_helper(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, """\
                import os
                import sys

                def f():
                    from runner import runner as R
                    return R.log
                """)
            self.assertTrue(RS.rewrite_module(path))
            with open(path, encoding="utf-8") as fh:
                new = fh.read()
        self.assertIn("    R = _runner()\n", new)
        self.assertNotIn("from runner import runner as R", new)
        self.assertTrue(RS._has_runner(new))
        self.assertLess(new.index("import sys"), new.index("from ops.live"))
        ast.parse(new)

    def test_a_module_with_the_helper_keeps_one_copy(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, "def _runner():\n    return None\n"
                                   "def f():\n"
                                   "    from runner import runner as R\n")
            self.assertTrue(RS.rewrite_module(path))
            with open(path, encoding="utf-8") as fh:
                new = fh.read()
        self.assertNotIn("ops.live", new)
        self.assertIn("    R = _runner()", new)

    def test_no_reach_back_is_left_alone(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._write(td, "from runner import runner as R\n")
            self.assertFalse(RS.rewrite_module(path))


class UndefinedTest(unittest.TestCase):
    def test_only_the_names_nothing_binds(self):
        tree = ast.parse(textwrap.dedent("""\
            import os.path
            from x import y as z
            G = 1
            def f(a, *args, b=0, **kw):
                global H
                try:
                    pass
                except ValueError as e:
                    del a
                g = lambda q, *, r=1: q + r
                return json.dumps(z, os, G, H, e, args, kw, b, missing_one)
            class C:
                pass
            async def af(p, /):
                return C, f, p
            """))
        self.assertEqual(RS._undefined(tree), ["json", "missing_one"])


def _tree(td):
    """A throwaway tree: runner.py loading one extracted module, the
    module itself, and a build workflow with the runner's own line
    and the installer's."""
    os.makedirs(os.path.join(td, "runner", "ops"))
    os.makedirs(os.path.join(td, ".github", "workflows"))
    runner = os.path.join(td, "runner", "runner.py")
    with open(runner, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent("""\
            import os
            from runner.wire.board import post_task as post
            _extr = _load_mod("runner.ops.extr", "ops.extr")
            if _extr is None:
                raise ImportError("runner/ops/extr.py is missing")
            first = _extr.first

            def log(msg):
                return msg
            """))
    with open(os.path.join(td, "runner", "ops", "extr.py"), "w",
              encoding="utf-8") as fh:
        fh.write(textwrap.dedent('''\
            """An extracted module."""
            import os

            LIMIT = 3


            def first(x):
                return json.dumps(second(x)) + log(_STATE)


            def second(x):
                stamp = datetime.now()
                return [x, stamp, sys.platform, _confval]
            '''))
    build = os.path.join(td, ".github", "workflows", "build.yml")
    with open(build, "w", encoding="utf-8") as fh:
        fh.write("run: pyinstaller --hidden-import runner._version "
                 "--name homing-pigeon runner/runner.py\n"
                 "run: pyinstaller --hidden-import runner._version "
                 "--name homing-pigeon-install runner/ops/install.py\n")
    return runner, build


class MainTest(unittest.TestCase):
    def _paths(self, td):
        runner, build = _tree(td)
        return [mock.patch.object(RS, "ROOT", td),
                mock.patch.object(RS, "RUNNER", runner),
                mock.patch.object(RS, "BUILD", build)], runner, build

    def test_check_reports_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            patches, runner, build = self._paths(td)
            with open(os.path.join(td, "runner", "ops", "back.py"), "w",
                      encoding="utf-8") as fh:
                fh.write("def f():\n    from runner import runner as R\n")
            before = {p: open(p, encoding="utf-8").read()
                      for p in (runner, build)}
            out = io.StringIO()
            with contextlib.ExitStack() as st:
                for p in patches:
                    st.enter_context(p)
                st.enter_context(contextlib.redirect_stdout(out))
                rc = RS.main(["--check"])
            for p, text in before.items():
                self.assertEqual(open(p, encoding="utf-8").read(), text)
        self.assertEqual(rc, 1)
        self.assertEqual(out.getvalue().splitlines(), [
            "package import in runner.py: runner.wire.board",
            "no hidden import in build.yml: runner.ops.extr",
            "no hidden import in build.yml: runner.wire.board",
            "reach-back import in " + os.path.join("runner", "ops", "back.py")])

    def test_a_repair_rewrites_the_runner_build_and_module(self):
        fake = types.SimpleNamespace(log=None, _STATE=None, _confval=None)
        with tempfile.TemporaryDirectory() as td:
            patches, runner, build = self._paths(td)
            out = io.StringIO()
            with contextlib.ExitStack() as st:
                for p in patches:
                    st.enter_context(p)
                st.enter_context(mock.patch.object(
                    RS, "_runner_module", return_value=fake))
                st.enter_context(contextlib.redirect_stdout(out))
                rc = RS.main([])
            with open(runner, encoding="utf-8") as fh:
                rsrc = fh.read()
            with open(build, encoding="utf-8") as fh:
                bsrc = fh.read().splitlines()
            with open(os.path.join(td, "runner", "ops", "extr.py"),
                      encoding="utf-8") as fh:
                msrc = fh.read()
        self.assertEqual(rc, 0)
        said = out.getvalue()
        self.assertIn("rewrote in runner.py: runner.wire.board", said)
        self.assertIn("hidden imports added: runner.ops.extr, "
                      "runner.wire.board", said)
        self.assertIn("finished: extr, extr (re-exports)", said)
        # runner.py: the import is a load, and the module's new names
        # are re-exported beside its load.
        self.assertIn('_board = _load_mod("runner.wire.board", "wire.board")',
                      rsrc)
        self.assertIn("post = _board.post_task", rsrc)
        self.assertIn("first = _extr.first\nLIMIT = _extr.LIMIT\n"
                      "second = _extr.second\n", rsrc)
        ast.parse(rsrc)
        # build.yml: the runner's own line only.
        self.assertIn("--hidden-import runner._version --hidden-import "
                      "runner.ops.extr --hidden-import runner.wire.board "
                      "--name homing-pigeon runner/runner.py", bsrc[0])
        self.assertNotIn("runner.ops.extr", bsrc[1])
        # the module: stdlib imports after the docstring, the live
        # lookup, runner names and sibling calls through it, and the
        # typed readers imported rather than reached.
        self.assertTrue(msrc.startswith('"""An extracted module."""\n'
                                        "from datetime import datetime, "
                                        "timezone, timedelta\nimport json\n"
                                        "import sys\n"))
        self.assertIn("from ops.live import _runner", msrc)
        self.assertIn("from guard import confval as _confval", msrc)
        self.assertIn("_runner().log(_runner()._STATE)", msrc)
        self.assertIn("json.dumps(_runner().second(x))", msrc)
        self.assertIn("def second(x):", msrc)
        self.assertIn("_runner().sys.platform", msrc)
        ast.parse(msrc)

    def test_a_clean_tree_finishes_without_a_word(self):
        fake = types.SimpleNamespace()
        with tempfile.TemporaryDirectory() as td:
            patches, runner, _build = self._paths(td)
            with open(runner, "w", encoding="utf-8") as fh:
                fh.write("_none = _load_mod(\"runner.ops.gone\", \"ops.gone\")\n")
            out = io.StringIO()
            with contextlib.ExitStack() as st:
                for p in patches:
                    st.enter_context(p)
                st.enter_context(mock.patch.object(
                    RS, "_runner_module", return_value=fake))
                st.enter_context(contextlib.redirect_stdout(out))
                RS.finish_modules()
        self.assertEqual(out.getvalue(), "")


class ThisTreeTest(unittest.TestCase):
    def test_check_finds_nothing_to_repair_here(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = RS.main(["--check"])
        self.assertEqual((rc, out.getvalue()), (0, ""))

    def test_every_extracted_module_runner_py_loads_exists(self):
        with open(RS.RUNNER, encoding="utf-8") as fh:
            found = RS._extracted_modules(fh.read())
        self.assertGreaterEqual(len(found), 10)
        for var, mod, path in found:
            self.assertTrue(os.path.isfile(path), path)
            self.assertTrue(var.startswith("_"), var)


if __name__ == "__main__":
    unittest.main()
