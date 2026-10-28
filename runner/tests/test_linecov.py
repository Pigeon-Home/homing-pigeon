# Agent-Stamp: 70000a51-e296-4b2c-bf5b-ba020e23eb91
"""runner/tools/linecov.py: stdlib line coverage in coverage.py's shape.

A throwaway package with one module and one test is measured. The
report names every statement once, counts a docstring as nothing,
marks the branch the test never takes as missing, totals agree with
the files, and coverage_gaps.py reads the report unchanged. A test
that patches os.path.realpath to raise is measured without the patch
reaching the tool.
"""
import io
import json
import os
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner.tools import coverage_gaps, linecov  # noqa: E402

MODULE = '''\
"""A module docstring is not a statement."""


def picked(n):
    """Nor is a function docstring."""
    if n > 0:
        return "positive"
    return "other"


class Box:
    size = 1
'''

TEST = '''\
import os
import unittest
from unittest import mock

from lcpkg import mod


class T(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(mod.picked(3), "positive")

    def test_realpath_patched_to_raise(self):
        with mock.patch.object(os.path, "realpath",
                               side_effect=ValueError("patched")):
            self.assertEqual(mod.picked(5), "positive")
'''


@unittest.skipUnless(hasattr(sys, "monitoring"),
                     "sys.monitoring needs Python 3.12 or later")
class LinecovTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        pkg = os.path.join(self.td.name, "lcpkg")
        os.makedirs(pkg)
        open(os.path.join(pkg, "__init__.py"), "w").close()
        with open(os.path.join(pkg, "mod.py"), "w", encoding="utf-8") as fh:
            fh.write(MODULE)
        with open(os.path.join(pkg, "test_mod.py"), "w",
                  encoding="utf-8") as fh:
            fh.write(textwrap.dedent(TEST))
        self.out = os.path.join(self.td.name, "cov.json")
        for name in ("lcpkg", "lcpkg.mod", "lcpkg.test_mod"):
            sys.modules.pop(name, None)

    def tearDown(self):
        for name in ("lcpkg", "lcpkg.mod", "lcpkg.test_mod"):
            sys.modules.pop(name, None)
        if self.td.name in sys.path:
            sys.path.remove(self.td.name)
        self.td.cleanup()

    def _run(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = linecov.main(["--out", self.out, "--root", self.td.name,
                               "--source", "lcpkg/mod.py",
                               "--", "lcpkg.test_mod"])
        with open(self.out, encoding="utf-8") as fh:
            return rc, json.load(fh), out.getvalue()

    def test_the_report_has_coverage_py_shape_and_the_right_lines(self):
        rc, rep, shown = self._run()
        self.assertEqual(rc, 0)
        info = rep["files"]["lcpkg/mod.py"]
        # Statements: def picked (4), if (6), return (7), return (8),
        # class Box (11), size (12). Docstrings are not counted.
        self.assertEqual(info["summary"]["num_statements"], 6)
        self.assertEqual(info["missing_lines"], [8])
        self.assertEqual(sorted(info["executed_lines"]), [4, 6, 7, 11, 12])
        self.assertEqual(rep["totals"]["num_statements"], 6)
        self.assertEqual(rep["totals"]["missing_lines"], 1)
        self.assertEqual(rep["totals"]["percent_covered"], 83.33)
        self.assertIn("lcpkg/mod.py", shown)
        self.assertIn("(2 tests)", shown)

    def test_coverage_gaps_reads_the_report_unchanged(self):
        _rc, rep, _ = self._run()
        files, funcs = coverage_gaps.gaps(rep, self.td.name)
        self.assertEqual([f[3] for f in files], ["lcpkg/mod.py"])
        self.assertEqual([(f[3], sorted(f[4])) for f in funcs],
                         [("picked", [8])])

    def test_a_held_coverage_id_falls_back_to_a_free_one(self):
        mon = sys.monitoring
        if mon.get_tool(mon.COVERAGE_ID) is not None:
            self.skipTest("the coverage id is already held by this run")
        mon.use_tool_id(mon.COVERAGE_ID, "someone-else")
        try:
            rc, rep, _ = self._run()
        finally:
            mon.free_tool_id(mon.COVERAGE_ID)
        self.assertEqual(rc, 0)
        self.assertEqual(rep["files"]["lcpkg/mod.py"]["missing_lines"], [8])

    def test_a_source_that_does_not_parse_is_named_not_fatal(self):
        # A measured folder can hold a .py that is not Python (a sample
        # or fixture). The run still writes its report: the file is
        # named under meta.unparsed and left out of the totals.
        bad = os.path.join(self.td.name, "lcpkg", "sample.py")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("def f():\n    pass\n        def g(self): pass\n")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = linecov.main(["--out", self.out, "--root", self.td.name,
                               "--source", "lcpkg",
                               "--", "lcpkg.test_mod"])
        self.assertEqual(rc, 0)
        with open(self.out, encoding="utf-8") as fh:
            rep = json.load(fh)
        self.assertNotIn("lcpkg/sample.py", rep["files"])
        self.assertEqual([u["path"] for u in rep["meta"]["unparsed"]],
                         ["lcpkg/sample.py"])
        self.assertIn("IndentationError", rep["meta"]["unparsed"][0]["error"])
        self.assertEqual(rep["files"]["lcpkg/mod.py"]["missing_lines"], [8])
        self.assertEqual(rep["totals"]["num_statements"],
                         sum(f["summary"]["num_statements"]
                             for f in rep["files"].values()))
        self.assertIn("does not parse: lcpkg/sample.py", err.getvalue())
    def test_a_module_that_skips_at_import_is_one_skip_not_a_crash(self):
        # Discovery turns a module-level SkipTest into a skip; loading
        # by name raised it out of the run (the hypothesis-less box).
        skipper = os.path.join(self.td.name, "lcpkg", "test_skipper.py")
        with open(skipper, "w", encoding="utf-8") as fh:
            fh.write("import unittest\nraise unittest.SkipTest('not here')\n")
        sys.path.insert(0, self.td.name)
        try:
            suite = linecov.load(["lcpkg.test_skipper"])
            result = unittest.TestResult()
            suite.run(result)
        finally:
            sys.path.remove(self.td.name)
            sys.modules.pop("lcpkg.test_skipper", None)
        self.assertEqual(suite.countTestCases(), 1)
        self.assertEqual([r for _t, r in result.skipped], ["not here"])
        self.assertTrue(result.wasSuccessful())

    def test_no_tests_or_an_old_python_is_exit_two(self):
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(linecov.main(["--out", self.out,
                                           "--source", "x.py"]), 2)
        self.assertIn("after --", err.getvalue())


if __name__ == "__main__":
    unittest.main()
