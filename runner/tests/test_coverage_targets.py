"""coverage_targets classifies gaps the way the standing orders need.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""
import json
import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.tools import coverage_targets as ct  # noqa: E402

MODULE = textwrap.dedent('''\
    import os
    import sys

    def parse(text):
        parts = text.split(",")
        if not parts:
            return None
        out = []
        for p in parts:
            out.append(p.strip())
        return out

    def read(path):
        try:
            with open(path) as fh:
                return fh.read()
        except OSError:
            return None

    def only_dict(value):
        if not isinstance(value, dict):
            return {}
        return value

    def tick():
        if sys.platform == "win32":
            a = 1
            b = 2
            return a + b
        return 0

    def old(x):
        y = x + 1
        z = y + 1
        return z

    old = parse
    ''')


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.td.name, "runner"))
        with open(os.path.join(self.td.name, "runner", "m.py"), "w") as fh:
            fh.write(MODULE)

    def tearDown(self):
        self.td.cleanup()

    def _rows(self, missing, shape="coverage"):
        if shape == "coverage":
            rep = {"files": {"runner/m.py": {
                "missing_lines": missing, "executed_lines": [1, 2, 4],
                "summary": {"num_statements": 30},
                "missing_branches": [[5, 6]]}}}
        else:
            rep = {"runner/m.py": {"statements": 30, "covered": 30 - len(missing),
                                   "missing": missing}}
        path = os.path.join(self.td.name, "cov.json")
        with open(path, "w") as fh:
            json.dump(rep, fh)
        report = ct.load(path)
        return {r["function"]: r for r in ct.targets(report, self.td.name, 1)}, report

    def test_each_class_is_read_from_the_ast(self):
        rows, _ = self._rows([5, 6, 8, 9, 17, 18, 21, 22, 27, 28, 29, 33, 34, 35])
        self.assertEqual(rows["parse"]["class"], "logic")
        self.assertEqual(rows["read"]["class"], "except")
        self.assertEqual(rows["only_dict"]["class"], "guard")
        self.assertEqual(rows["tick"]["class"], "platform")
        self.assertEqual(rows["old"]["class"], "shadowed")
        self.assertEqual(rows["parse"]["missing_branches"], [(5, 6)])
        self.assertEqual(rows["parse"]["args"], ["text"])

    def test_logic_sorts_first_and_largest_first(self):
        rows, report = self._rows([5, 6, 8, 9, 17, 18, 21, 22])
        order = [r["function"] for r in ct.targets(report, self.td.name, 1)]
        self.assertEqual(order[0], "parse")
        self.assertEqual(order[-1], "read")

    def test_the_per_file_shape_and_the_delta_line(self):
        rows, report = self._rows([5, 6, 8], shape="perfile")
        self.assertEqual(rows["parse"]["missing"], [5, 6, 8])
        _, before = self._rows([5, 6, 8, 9, 17], shape="perfile")
        text = ct.markdown(ct.targets(report, self.td.name, 1), report, since=before)
        self.assertIn("90.0% covered, 3 missing of 30", text)
        self.assertIn("+2 lines closed", text)


if __name__ == "__main__":
    unittest.main()
