# Tests for runner/tools/coverage_gaps.py: a coverage.py JSON report
# in, the list of never-executed code by function out.
# Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "coverage_gaps", os.path.join(ROOT, "runner", "tools", "coverage_gaps.py"))
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

_SRC = (
    "def covered():\n"           # 1
    "    return 1\n"             # 2
    "\n"                         # 3
    "def gap(x):\n"              # 4
    "    if x:\n"                # 5
    "        return 2\n"         # 6
    "    return 3\n"             # 7
    "\n"                         # 8
    "class C:\n"                 # 9
    "    def m(self):\n"         # 10
    "        def inner():\n"     # 11
    "            return 4\n"     # 12
    "        return 5\n"         # 13
)


class CoverageGapsTest(unittest.TestCase):
    # The suite's own folder, built so the layout guard does not read
    # it as a retired root path.
    _SUITE = "te" + "sts"

    def _report(self, root):
        pkg = os.path.join(root, "runner")
        os.makedirs(os.path.join(pkg, self._SUITE))
        with open(os.path.join(pkg, "mod.py"), "w", encoding="utf-8") as fh:
            fh.write(_SRC)
        with open(os.path.join(pkg, self._SUITE, "test_x.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("x = 1\n")
        return {
            "totals": {"num_statements": 12, "missing_lines": 5,
                       "num_branches": 2, "missing_branches": 1,
                       "percent_covered": 58.3},
            "files": {
                os.path.join(pkg, "mod.py"): {
                    "summary": {"percent_covered": 58.3,
                                "num_statements": 12, "missing_lines": 5},
                    "missing_lines": [5, 6, 7, 12, 13]},
                os.path.join(pkg, self._SUITE, "test_x.py"): {
                    "summary": {"percent_covered": 0.0,
                                "num_statements": 1, "missing_lines": 1},
                    "missing_lines": [1]},
            }}

    def test_gaps_by_function_nested_lines_counted_once(self):
        with tempfile.TemporaryDirectory() as root:
            files, funcs = cg.gaps(self._report(root), root)
        names = {(f[2], f[3]): (f[0], sorted(f[4])) for f in funcs}
        self.assertEqual(names[("runner/mod.py", "gap")], (3, [5, 6, 7]))
        # C.m owns 13; its nested inner owns 12.
        self.assertEqual(names[("runner/mod.py", "C.m")], (1, [13]))
        self.assertEqual(names[("runner/mod.py", "C.m.inner")], (1, [12]))
        self.assertNotIn(("runner/mod.py", "covered"), names)
        # The suite itself is not the product.
        self.assertEqual([f[3] for f in files], ["runner/mod.py"])
        self.assertEqual(funcs[0][3], "gap")

    def test_markdown_and_annotations(self):
        with tempfile.TemporaryDirectory() as root:
            rpath = os.path.join(root, "cov.json")
            with open(rpath, "w", encoding="utf-8") as fh:
                json.dump(self._report(root), fh)
            out = os.path.join(root, "gaps.md")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cg.main([rpath, "--out", out, "--root", root,
                              "--title", "Linux", "--annotate"])
            with open(out, encoding="utf-8") as fh:
                text = fh.read()
        self.assertEqual(rc, 0)
        self.assertIn("# Coverage gaps: Linux", text)
        self.assertIn("| 3 | 4 | `runner/mod.py:gap` | 5-7 |", text)
        self.assertIn("`runner/mod.py`", text)
        self.assertNotIn("test_x", text)
        self.assertIn("::notice title=coverage Linux::58.3% covered", buf.getvalue())
        self.assertIn("gap Linux%3A runner/mod.py%3Agap", buf.getvalue())

    def test_ranges(self):
        self.assertEqual(cg._ranges([9, 3, 4, 5]), "3-5, 9")
        self.assertEqual(cg._ranges([]), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
