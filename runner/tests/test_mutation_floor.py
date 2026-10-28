# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/mutation_floor.py: a mutation run whose signal collapsed
is refused (Q22).

No test ran a line of it. A made-up mutants tree stands in for what
mutmut writes: the stats file and the per-file .meta records. The
reader counts mutants and functions reached, files every exit code
under its status (an unknown one as suspicious, an unreadable record
skipped), the judge names each floor breach, and main prints the tally,
writes the survivors by name, annotates for Actions, and exits 1 only
below the floor.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest

from runner.tools import mutation_floor as MF  # noqa: E402


def _tree(root, stats=True, metas=None, functions=8, tests=12):
    if stats:
        with open(os.path.join(root, "mutmut-stats.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"tests_by_mangled_function_name": dict(
                [("f%d" % i, ["t"]) for i in range(functions)]
                + [("untested", [])]),
                "duration_by_test": {"t%d" % i: 0.1 for i in range(tests)}},
                fh)
    for rel, body in (metas or {}).items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body if isinstance(body, str) else json.dumps(body))


def _codes(prefix, codes):
    return {"exit_code_by_key": {"%s__mutmut_%d" % (prefix, i): c
                                 for i, c in enumerate(codes, 1)}}


class ReadRunTest(unittest.TestCase):
    def test_every_exit_code_lands_under_its_status(self):
        with tempfile.TemporaryDirectory() as td:
            _tree(td, metas={
                "runner/guard/security.py.meta": _codes(
                    "security.x_check", [1, 3, 0, 33, 36, None, 99]),
                "runner/wire/verify.py.meta": _codes("verify.x_v", [1, -9]),
                "runner/broken.py.meta": "{not json",
            })
            run = MF.read_run(td)
        self.assertTrue(run["stats_found"])
        self.assertEqual(run["functions_with_tests"], 8)
        self.assertEqual(run["tests_total"], 12)
        self.assertEqual(run["meta_files"], 3)
        self.assertEqual(run["mutants"], 9)
        self.assertEqual(run["tally"], {"killed": 3, "survived": 1,
                                        "no tests": 1, "timeout": 1,
                                        "not checked": 1, "suspicious": 1,
                                        "segfault": 1})
        self.assertEqual(run["by_status"]["suspicious"],
                         ["security.x_check__mutmut_7"])

    def test_no_stats_and_no_records_is_an_empty_run(self):
        with tempfile.TemporaryDirectory() as td:
            run = MF.read_run(td)
        self.assertEqual(run, {"stats_found": False, "functions_with_tests": 0,
                               "tests_total": 0, "meta_files": 0,
                               "mutants": 0, "tally": {}, "by_status": {}})


class JudgeTest(unittest.TestCase):
    def test_each_breach_is_named(self):
        run = {"stats_found": False, "mutants": 3, "functions_with_tests": 1}
        self.assertEqual(MF.judge(run, 100, 6), [
            "no mutmut-stats.json: the stats phase did not run",
            "3 mutants generated, floor is 100",
            "1 functions reached by tests, floor is 6"])

    def test_a_sound_run_has_no_breach(self):
        run = {"stats_found": True, "mutants": 100, "functions_with_tests": 6}
        self.assertEqual(MF.judge(run, 100, 6), [])


class MainTest(unittest.TestCase):
    def _main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = MF.main(argv)
        return rc, out.getvalue()

    def test_a_collapsed_run_fails_and_says_how_to_reproduce(self):
        with tempfile.TemporaryDirectory() as td:
            _tree(td, functions=1, metas={
                "a.py.meta": _codes("a.f", [0, 0, 1])})
            rc, out = self._main(["--mutants-dir", td, "--annotate"])
        self.assertEqual(rc, 1)
        lines = out.splitlines()
        self.assertEqual(lines[0], "mutation run: 3 mutants in 1 files "
                                   "(killed 1, survived 2); 1 functions "
                                   "reached by 12 tests")
        self.assertEqual(lines[1], "::notice title=mutation::" + lines[0])
        self.assertTrue(lines[2].startswith(
            "MUTATION FLOOR: 3 mutants generated, floor is 100; 1 functions "
            "reached by tests, floor is 6. The signal collapsed"))
        self.assertIn("python -m pytest -x -q runner/tests/", lines[2])
        self.assertTrue(lines[3].startswith(
            "::error title=mutation signal collapsed::"))
        self.assertLessEqual(len(lines[3]),
                             len("::error title=mutation signal collapsed::")
                             + 900)

    def test_a_sound_run_passes_and_lists_survivors_by_status(self):
        with tempfile.TemporaryDirectory() as td:
            _tree(td, metas={
                "a.py.meta": _codes("a.f", [1] * 6 + [0, 36]),
                "b.py.meta": _codes("b.g", [33, 1, 0])})
            surv = os.path.join(td, "survivors.txt")
            rc, out = self._main(["--mutants-dir", td, "--min-mutants", "10",
                                  "--survivors", surv])
            with open(surv, encoding="utf-8") as fh:
                listed = fh.read().splitlines()
        self.assertEqual(rc, 0)
        self.assertEqual(out.count("\n"), 1)
        self.assertIn("11 mutants in 2 files", out)
        self.assertEqual(listed, ["survived\ta.f__mutmut_7",
                                  "survived\tb.g__mutmut_3",
                                  "no tests\tb.g__mutmut_1",
                                  "timeout\ta.f__mutmut_8"])

    def test_an_empty_tree_reads_none(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = self._main(["--mutants-dir", td])
        self.assertEqual(rc, 1)
        self.assertIn("0 mutants in 0 files (none)", out)
        self.assertIn("no mutmut-stats.json", out)


if __name__ == "__main__":
    unittest.main()
