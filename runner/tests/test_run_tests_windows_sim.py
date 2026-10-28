# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/run_tests_windows_sim.py: the suite under the Windows
surface.

No test ran a line of it. main is run here over a throwaway test tree.
The tree's own test asserts what the surface promises while it is on
(os.name "nt", sys.platform "win32", TMPDIR at the run's own scratch
directory and temp files still working), so a green run proves the surface was applied
around discovery and the tests; after the run the host identity is
back. A red tree is 1, a tree with no tests is 1 with the reason on
stderr, --describe prints the surface's own description, and a
missing optional stdlib module does not stop the pre-import.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

from runner.tools import run_tests_windows_sim as WS  # noqa: E402

GREEN = """\
    import os
    import sys
    import tempfile
    import unittest

    class UnderTheSurface(unittest.TestCase):
        def test_the_host_reads_as_windows(self):
            self.assertEqual(os.name, "nt")
            self.assertEqual(sys.platform, "win32")

        def test_temp_files_still_work_and_tmpdir_is_the_runs_own(self):
            self.assertIn("hp-winsim-", os.environ["TMPDIR"])
            with tempfile.TemporaryDirectory() as td:
                self.assertTrue(os.path.isdir(td))
    """

RED = """\
    import unittest

    class Broken(unittest.TestCase):
        def test_assumes_posix(self):
            import os
            self.assertEqual(os.name, "posix")
    """


class WindowsSimTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="hp-winsim-test-")
        self.addCleanup(shutil.rmtree, self.td, True)

    def _tree(self, body):
        pkg = os.path.join(self.td, "winsimpkg")
        os.makedirs(pkg)
        open(os.path.join(pkg, "__init__.py"), "w").close()
        if body is not None:
            with open(os.path.join(pkg, "test_winsim_one.py"), "w",
                      encoding="utf-8") as fh:
                fh.write(textwrap.dedent(body))
        return pkg

    def _main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        host = (os.name, sys.platform)
        try:
            with mock.patch.dict(os.environ, {}), \
                    contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                rc = WS.main(argv)
                scratch = os.environ.get("TMPDIR")
        finally:
            for name in [m for m in sys.modules
                         if m == "winsimpkg" or m.startswith("winsimpkg.")]:
                del sys.modules[name]
            if self.td in sys.path:
                sys.path.remove(self.td)
        self.assertEqual((os.name, sys.platform), host)
        if scratch and os.path.basename(scratch).startswith("hp-winsim-"):
            shutil.rmtree(scratch, True)
        return rc, out.getvalue(), err.getvalue(), scratch

    def _run(self, start):
        return self._main(["--start-dir", start, "--top-level", self.td])

    def test_a_green_tree_runs_under_the_surface_and_is_zero(self):
        rc, out, err, scratch = self._run(self._tree(GREEN))
        self.assertEqual(rc, 0, err)
        self.assertIn("windows-sim: 2 tests, 0 failures, 0 errors, "
                      "0 skipped", out)
        self.assertTrue(os.path.basename(scratch).startswith("hp-winsim-"))

    def test_a_red_tree_is_one(self):
        rc, out, err, _scratch = self._run(self._tree(RED))
        self.assertEqual(rc, 1)
        self.assertIn("windows-sim: 1 tests, 1 failures", out)
        self.assertIn("'nt' != 'posix'", err)

    def test_no_tests_is_one_with_the_reason(self):
        rc, out, err, _scratch = self._run(self._tree(None))
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("windows-sim: discovery came up empty", err)

    def test_describe_prints_the_surface(self):
        rc, out, _err, scratch = self._main(["--describe"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), json.loads(json.dumps(
            WS.surface_description())))
        self.assertIsNone(scratch)

    def test_a_missing_optional_module_does_not_stop_the_preimport(self):
        with mock.patch.object(WS, "_PREIMPORT",
                               ("json", "hp_no_such_module_here")):
            WS._preimport_stdlib()
        self.assertNotIn("hp_no_such_module_here", sys.modules)


if __name__ == "__main__":
    unittest.main()
