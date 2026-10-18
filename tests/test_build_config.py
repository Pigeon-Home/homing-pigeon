"""The frozen builds must actually contain what runner.py loads.

runner.py loads its sibling modules dynamically (``_load_mod`` /
``_load_attr`` with ``importlib.import_module``) so the same file runs
as a package member and as ``__main__`` from inside runner/. Dynamic
imports are invisible to PyInstaller's static analysis: without a
``--hidden-import`` per module, the one-file executables silently ship
without them -- _version most visibly, which made the Windows exe print
"unknown" for --version (CI run 39076097325); the other modules would
have degraded silently. This test keeps build.yml's hidden imports in
sync with every dynamic load in runner.py, and checks that the Linux
and macOS jobs smoke the built binaries' --version like Windows does.
"""

import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _dynamic_runner_modules():
    with open(os.path.join(_root(), "runner", "runner.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    return set(re.findall(
        r'_load_(?:mod|attr)\(\s*"runner\.([A-Za-z0-9_]+)"', src))


def _workflow():
    with open(os.path.join(_root(), ".github", "workflows", "build.yml"),
              encoding="utf-8") as fh:
        return fh.read()


def _job_block(workflow, job):
    m = re.search(r"^  %s:\n(.*?)(?=^  [a-z-]+:|\Z)" % re.escape(job),
                  workflow, re.M | re.S)
    assert m, "no %s job in build.yml" % job
    return m.group(1)


class HiddenImportSyncTest(unittest.TestCase):
    def test_scan_finds_the_dynamic_loads(self):
        # Self-check: if the scan ever matches nothing, the sync test
        # below would pass vacuously. The loader set is in double
        # digits by design (one face per sibling module).
        self.assertGreaterEqual(len(_dynamic_runner_modules()), 10)

    def test_every_dynamic_load_is_a_hidden_import(self):
        workflow = _workflow()
        build_lines = [ln for ln in workflow.splitlines()
                       if "pyinstaller" in ln and "runner/runner.py" in ln]
        self.assertEqual(len(build_lines), 3,
                         "expected one runner build line per OS job")
        for line in build_lines:
            for mod in sorted(_dynamic_runner_modules()):
                self.assertIn("--hidden-import runner.%s" % mod, line,
                              "build line misses hidden import for %s" % mod)


class UnixVersionSmokeTest(unittest.TestCase):
    def test_linux_and_macos_smoke_the_built_version(self):
        workflow = _workflow()
        for job in ("build-linux", "build-macos"):
            block = _job_block(workflow, job)
            self.assertIn("./dist/homing-pigeon --version", block,
                          "%s never runs the built binary" % job)
            self.assertIn("./dist/install --version", block,
                          "%s never runs the built installer" % job)


if __name__ == "__main__":
    unittest.main(verbosity=2)
