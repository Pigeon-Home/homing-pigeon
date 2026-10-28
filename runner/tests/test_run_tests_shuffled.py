# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/run_tests_shuffled.py: the suite in a seeded order.

No test ran a line of it. A pollution failure is only useful if the
seed reproduces it, so the shuffle is held to being the same for one
seed and different across seeds, to keeping every case exactly once,
and to keeping each class's cases together so class fixtures run once.
main is run over a throwaway test tree: a green tree is 0 with the
tally line, a red one is 1, and a tree with no tests is 1 with the
reason.
"""
import contextlib
import io
import os
import sys
import tempfile
import textwrap
import unittest

from runner.tools import run_tests_shuffled as SH  # noqa: E402


def _cls(name, n):
    body = {"test_%02d" % i: (lambda self: None) for i in range(n)}
    return type(name, (unittest.TestCase,), body)


def _suite():
    loader = unittest.TestLoader()
    outer = unittest.TestSuite()
    for name, n in (("Alpha", 4), ("Beta", 3), ("Gamma", 5)):
        inner = unittest.TestSuite([loader.loadTestsFromTestCase(_cls(name, n))])
        outer.addTest(inner)
    return outer


def _ids(suite):
    return ["%s.%s" % (type(c).__name__, c._testMethodName)
            for c in SH._flatten(suite)]


class ShuffleTest(unittest.TestCase):
    def test_one_seed_one_order(self):
        self.assertEqual(_ids(SH.shuffled_suite(_suite(), 7)),
                         _ids(SH.shuffled_suite(_suite(), 7)))

    def test_seeds_reorder_and_every_case_runs_once(self):
        base = sorted(_ids(_suite()))
        orders = {tuple(_ids(SH.shuffled_suite(_suite(), s)))
                  for s in range(12)}
        self.assertGreater(len(orders), 1)
        for order in orders:
            self.assertEqual(sorted(order), base)

    def test_a_class_s_cases_stay_together(self):
        for seed in range(12):
            names = [i.split(".")[0] for i in
                     _ids(SH.shuffled_suite(_suite(), seed))]
            runs = [n for i, n in enumerate(names)
                    if i == 0 or names[i - 1] != n]
            self.assertEqual(sorted(runs), ["Alpha", "Beta", "Gamma"], seed)


class MainTest(unittest.TestCase):
    def _tree(self, td, body):
        pkg = os.path.join(td, "shufpkg")
        os.makedirs(pkg)
        open(os.path.join(pkg, "__init__.py"), "w").close()
        with open(os.path.join(pkg, "test_shuf_one.py"), "w",
                  encoding="utf-8") as fh:
            fh.write(textwrap.dedent(body))
        return pkg

    def _main(self, td, start):
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                rc = SH.main(["--seed", "5", "--start-dir", start,
                              "--top-level", td])
        finally:
            for name in [m for m in sys.modules
                         if m == "shufpkg" or m.startswith("shufpkg.")]:
                del sys.modules[name]
            if td in sys.path:
                sys.path.remove(td)
        return rc, out.getvalue(), err.getvalue()

    def test_a_green_tree_is_zero_with_the_tally(self):
        with tempfile.TemporaryDirectory() as td:
            start = self._tree(td, """\
                import unittest
                class T(unittest.TestCase):
                    def test_a(self): pass
                    def test_b(self): pass
                    @unittest.skip("not here")
                    def test_c(self): pass
                """)
            rc, out, _err = self._main(td, start)
        self.assertEqual(rc, 0)
        self.assertIn("shuffle(seed=5): 3 tests, 0 failures, 0 errors, "
                      "1 skipped", out)

    def test_a_red_tree_is_one(self):
        with tempfile.TemporaryDirectory() as td:
            start = self._tree(td, """\
                import unittest
                class T(unittest.TestCase):
                    def test_a(self): self.fail("polluted")
                    def test_b(self): raise RuntimeError("leak")
                """)
            rc, out, err = self._main(td, start)
        self.assertEqual(rc, 1)
        self.assertIn("2 tests, 1 failures, 1 errors", out)
        self.assertIn("polluted", err)

    def test_no_tests_found_is_one_with_the_reason(self):
        with tempfile.TemporaryDirectory() as td:
            empty = os.path.join(td, "shufpkg")
            os.makedirs(empty)
            open(os.path.join(empty, "__init__.py"), "w").close()
            rc, out, _err = self._main(td, empty)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "shuffle: discovery came up empty\n")


if __name__ == "__main__":
    unittest.main()
