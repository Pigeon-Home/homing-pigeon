# Agent-Stamp: c0000327-6a7b-42df-81b9-21136287db1c
"""The local rig's tools: the hypothesis shim and stdlib coverage.

A box with no PyPI runs the whole suite and measures it: property
modules load through runner/tests/_hypothesis_shim.py with only their
@given tests skipped, and runner/tools/stdlib_coverage.py measures
line coverage in coverage.py's JSON shape with the standard library
alone. These pin both, and pin the CI legs that install hypothesis to
forbid the shim's skip, so the shim can never hide a property test
where it must run.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tests import _hypothesis_shim as shim  # noqa: E402
from runner.tools import stdlib_coverage as cov  # noqa: E402


class HypothesisShimTest(unittest.TestCase):
    def test_strategy_expressions_evaluate_at_import(self):
        st = shim.strategies
        built = st.lists(st.dictionaries(st.text(), st.integers()),
                         max_size=3).map(len).filter(bool) | st.none()
        self.assertIs(built, st)

        @st.composite
        def pair(draw):
            return draw(st.integers()), draw(st.integers())

        self.assertIsNotNone(pair())

    def test_given_skips_with_the_forbidden_reason(self):
        class Case(unittest.TestCase):
            @shim.settings(max_examples=5, deadline=None)
            @shim.given(x=shim.strategies.integers())
            def test_prop(self, x):
                raise AssertionError("must not run")

            def test_plain(self):
                pass

        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(Case).run(result)
        self.assertEqual(result.testsRun, 2)
        self.assertEqual([r for _t, r in result.skipped],
                         [shim.SKIP_REASON])
        self.assertFalse(result.failures or result.errors)

    def test_assume_and_settings_are_inert(self):
        self.assertTrue(shim.assume(False))
        fn = lambda: 7  # noqa: E731
        self.assertIs(shim.settings(deadline=None)(fn), fn)

    def test_ci_legs_that_install_hypothesis_forbid_the_skip(self):
        wf = os.path.join(ROOT, ".github", "workflows")
        for name in ("build.yml", "python-range.yml"):
            with open(os.path.join(wf, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("install -c .github/requirements-ci.txt hypothesis",
                          text, name)
            self.assertIn('--forbid "%s"' % shim.SKIP_REASON, text, name)

    def test_the_converted_modules_fall_back_to_the_shim(self):
        tests = os.path.join(ROOT, "runner", "tests")
        for name in sorted(os.listdir(tests)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(tests, name), encoding="utf-8") as fh:
                for line in fh:
                    # A bare top-level hypothesis import fails the whole
                    # module on a box without it; it goes in a try.
                    self.assertFalse(
                        line.startswith(("from hypothesis", "import hypothesis")),
                        "%s imports hypothesis outside a try" % name)


_MONITORING = hasattr(sys, "monitoring")


def _traced():
    """This process is already under stdlib_coverage (a measured run)."""
    return _MONITORING and sys.monitoring.get_tool(cov._TOOL_ID) is not None


@unittest.skipUnless(_MONITORING, "sys.monitoring needs 3.12+")
class StatementsTest(unittest.TestCase):
    def _file(self, text):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, True))
        path = os.path.join(d, "mod.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(textwrap.dedent(text))
        return d, path

    def test_comments_blanks_and_docstring_only_lines_are_not_statements(self):
        _d, path = self._file('''\
            # a comment

            def f(x):
                """doc."""
                return (x +
                        1)
            ''')
        found = cov.statements(path)
        self.assertNotIn(1, found)
        self.assertNotIn(2, found)
        self.assertIn(3, found)
        self.assertIn(5, found)

    def test_an_unparsable_file_has_no_statements(self):
        _d, path = self._file("def (:\n")
        self.assertEqual(cov.statements(path), set())

    def test_untaken_arms_are_the_only_misses(self):
        if _traced():
            self.skipTest("the suite is being measured by stdlib_coverage")
        d, path = self._file('''\
            def f(x):
                if x:
                    return 1
                try:
                    return 2
                except ValueError:
                    return 3
            f(0)
            ''')
        rec = cov.Recorder(d)
        self.assertTrue(rec.start())
        try:
            ns = {}
            with open(path, encoding="utf-8") as fh:
                exec(compile(fh.read(), path, "exec"), ns)
        finally:
            rec.stop()
        key = os.path.abspath(path).replace("\\", "/")
        missed = cov.statements(path) - rec.hits.get(key, set())
        self.assertEqual(missed, {3, 6, 7})

    def test_the_callback_survives_a_patched_os_path(self):
        # test_install_edges patches os.path.abspath to raise while
        # measured code runs; the callback must not call it.
        if _traced():
            self.skipTest("the suite is being measured by stdlib_coverage")
        from unittest import mock
        rec = cov.Recorder(ROOT)
        self.assertTrue(rec.start())
        try:
            with mock.patch.object(os.path, "abspath",
                                   side_effect=OSError("bad")), \
                    mock.patch.object(os, "getcwd",
                                      side_effect=OSError("bad")):
                from runner.guard import textutil
                code = textutil.__loader__.get_code("runner.guard.textutil")
                exec(code, {"__name__": "_measured_textutil"})
        finally:
            rec.stop()
        self.assertTrue(any(k.endswith("runner/guard/textutil.py")
                            for k in rec.hits))

    def test_a_second_recorder_defers_to_the_first(self):
        if _traced():
            self.skipTest("the suite is being measured by stdlib_coverage")
        first = cov.Recorder(ROOT)
        self.assertTrue(first.start())
        try:
            second = cov.Recorder(ROOT)
            self.assertFalse(second.start())
            second.stop()  # a no-op, never frees the first's tool id
        finally:
            first.stop()


@unittest.skipUnless(_MONITORING, "sys.monitoring needs 3.12+")
class ReportShapeTest(unittest.TestCase):
    def test_report_reads_as_coverage_json_for_coverage_gaps(self):
        from runner.tools import coverage_gaps
        src = os.path.join(ROOT, "runner")
        path = os.path.join(src, "guard", "textutil.py")
        rep = cov.report({path: set(cov.statements(path))}, src)
        rel = "runner/guard/textutil.py"
        self.assertEqual(rep["files"][rel]["summary"]["percent_covered"],
                         100.0)
        self.assertFalse(any("/tests/" in k or "/tools/" in k
                             for k in rep["files"]))
        t = rep["totals"]
        self.assertEqual(t["num_statements"],
                         t["covered_lines"] + t["missing_lines"])
        files, _funcs = coverage_gaps.gaps(rep, ROOT)
        self.assertTrue(files)

    def test_a_run_with_a_child_counts_the_childs_lines(self):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, True))
        out = os.path.join(d, "cov.json")
        env = dict(os.environ)
        env.pop("HP_STDLIB_COV_DIR", None)
        env.pop("PYTHONPATH", None)
        env["HP_RIG_CHILD_FIXTURE"] = "1"
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "runner", "tools",
                                          "stdlib_coverage.py"),
             "--subprocess", "--out", out,
             "runner.tests.test_local_rig_tools.ChildFixture"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(out, encoding="utf-8") as fh:
            rep = json.load(fh)
        self.assertGreaterEqual(rep["meta"]["child_processes"], 1)
        self.assertIn("runner/cloud/send_job.py", rep["files"])
        self.assertGreater(
            rep["files"]["runner/cloud/send_job.py"]["summary"]["covered_lines"],
            0)


class ChildFixture(unittest.TestCase):
    """Driven by the test above: send_job.py runs only in a child."""

    def test_child(self):
        if not os.environ.get("HP_RIG_CHILD_FIXTURE"):
            self.skipTest("a fixture for ReportShapeTest")
        subprocess.run([sys.executable, "-c",
                        "import runner.cloud.send_job"],
                       cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
