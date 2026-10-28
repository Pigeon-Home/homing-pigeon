# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/de_dust_survivors.py: every mutation operator, and the
tool's record.

test_de_dust_survivors runs mutants against the corpus. Two of the ten
operators (an `and` turned `or`, a boolean flipped) never ran there,
because the readers it samples reach none of those sites. A mutant the
tool cannot write is a line the campaign believes is pinned when it
was never tried, so each operator is held here to making exactly its
one change and writing valid source. The arc maps it narrows by, the
report it writes and main's routing are held too.
"""
import ast
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from runner.tools import de_dust_survivors as SV  # noqa: E402

SOURCE = (
    "def f(a, b, s):\n"                    # 1
    "    if a < b and not s:\n"            # 2
    "        return a + 1\n"               # 3
    "    flag = True\n"                    # 4
    "    name = 'reader'\n"                # 5
    "    if flag:\n"                       # 6
    "        raise ValueError('no')\n"     # 7
    "    return b - 2\n"                   # 8
)


def _by_op(made):
    out = {}
    for _i, op, line, text in made:
        out.setdefault(op, []).append((line, text))
    return out


class OperatorTest(unittest.TestCase):
    def setUp(self):
        self.made = SV.mutants(SOURCE)
        self.ops = _by_op(self.made)

    def test_every_operator_has_a_site_here(self):
        self.assertEqual(set(self.ops), {
            "compare", "boolop", "not", "bool", "int+1", "int-1",
            "str-empty", "return-none", "raise-pass", "add-sub"})

    def test_each_mutant_is_valid_source_and_differs(self):
        base = ast.dump(ast.parse(SOURCE))
        for _i, op, _line, text in self.made:
            with self.subTest(op=op):
                self.assertNotEqual(ast.dump(ast.parse(text)), base)

    def _one(self, op, line):
        texts = [t for ln, t in self.ops[op] if ln == line]
        self.assertTrue(texts, (op, line, self.ops[op]))
        return texts[0]

    def test_and_becomes_or(self):
        self.assertIn("if a < b or not s:", self._one("boolop", 2))

    def test_a_boolean_is_flipped(self):
        self.assertIn("flag = False", self._one("bool", 4))

    def test_the_other_eight_make_their_one_change(self):
        cases = (("compare", 2, "if a <= b and"),
                 ("not", 2, "if a < b and s:"),
                 ("int+1", 3, "return a + 2"),
                 ("int-1", 8, "return b - 1"),
                 ("str-empty", 5, "name = ''"),
                 ("return-none", 3, "        return None"),
                 ("raise-pass", 7, "        pass"),
                 ("add-sub", 8, "return b + 2"))
        for op, line, want in cases:
            with self.subTest(op=op):
                self.assertIn(want, self._one(op, line))

    def test_a_raise_message_is_prose_not_a_site(self):
        self.assertNotIn(7, [ln for ln, _t in self.ops["str-empty"]])

    def test_a_sample_reproduces_from_its_seed(self):
        import random
        a = SV.mutants(SOURCE, limit=4, rng=random.Random(5))
        b = SV.mutants(SOURCE, limit=4, rng=random.Random(5))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 4)

    def test_replace_reports_a_node_it_cannot_find(self):
        tree = ast.parse(SOURCE)
        self.assertFalse(SV._replace(tree, ast.Pass(), ast.Pass()))

    def test_callee_of_a_call_on_a_call_is_unnamed(self):
        call = ast.parse("f()()").body[0].value
        self.assertEqual(SV._callee(call), "")


class ReachedLinesTest(unittest.TestCase):
    def test_both_ends_of_each_arc_into_the_module(self):
        with tempfile.TemporaryDirectory() as td:
            good = os.path.join(td, "a.json")
            with open(good, "w", encoding="utf-8") as fh:
                json.dump({"arcs": [["runner/wire/verify.py", 10, 12],
                                    ["runner/wire/verify.py", -1, 5],
                                    ["runner/wire/other.py", 7, 8],
                                    ["short", 1]]}, fh)
            bad = os.path.join(td, "b.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            paths = {"t1": good, "t2": bad, "t3": os.path.join(td, "none")}
            with mock.patch.object(SV.B, "arcs_path", paths.get):
                self.assertEqual(SV.reached_lines("verify",
                                                  ["t1", "t2", "t3"]),
                                 {5, 10, 12})


class RecordTest(unittest.TestCase):
    def test_the_report_is_written_whole_and_sorted(self):
        td = tempfile.mkdtemp(prefix="hp-survivors-test-")
        self.addCleanup(shutil.rmtree, td, True)
        report = os.path.join(td, "corpus", "survivors.json")
        with mock.patch.object(SV.B, "CORPUS_DIR", os.path.dirname(report)), \
                mock.patch.object(SV, "REPORT", report):
            SV.write_report({"z": 1, "a": {"b": 2}})
        with open(report, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(json.loads(text), {"a": {"b": 2}, "z": 1})
        self.assertLess(text.index('"a"'), text.index('"z"'))
        self.assertTrue(text.endswith("}\n"))
        self.assertFalse(os.path.exists(report + ".tmp"))

    def _report(self):
        return {"when": "2026-10-27T00:00:00Z", "head": "abc", "python": "3.13",
                "platform": "linux", "seconds": 1.5, "modules": {
                    "verify": {"mutants": 10, "killed": 7, "survived": 2,
                               "timeout": 1, "broken": 0, "survivors": []}}}

    def test_main_prints_the_tally_and_records_unless_told_not_to(self):
        out = io.StringIO()
        with mock.patch.object(SV, "run", return_value=self._report()) as run, \
                mock.patch.object(SV, "write_report") as write, \
                mock.patch.object(SV.B, "record_run") as rec, \
                contextlib.redirect_stdout(out):
            self.assertEqual(SV.main(["--module", "verify", "--limit", "10",
                                      "--seed", "3", "--timeout", "0"]), 0)
        run.assert_called_once_with(["verify"], 10, 3, 0)
        self.assertEqual(out.getvalue(), "survivors: 3 of 10 mutants over 1 "
                                         "module(s) in 1.5s\n")
        write.assert_called_once()
        line = rec.call_args[0][0]
        self.assertEqual(line["kind"], "survivors")
        self.assertEqual(line["modules"], {"verify": {
            "mutants": 10, "killed": 7, "survived": 2, "timeout": 1,
            "broken": 0}})
        with mock.patch.object(SV, "run", return_value=self._report()) as run, \
                mock.patch.object(SV, "write_report") as write, \
                mock.patch.object(SV.B, "record_run") as rec, \
                contextlib.redirect_stdout(io.StringIO()):
            SV.main(["--no-record"])
        self.assertEqual(run.call_args[0][0], sorted(SV.MODULES))
        write.assert_not_called()
        rec.assert_not_called()


if __name__ == "__main__":
    unittest.main()
