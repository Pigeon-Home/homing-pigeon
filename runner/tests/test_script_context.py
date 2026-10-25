"""runner.py runs as a script, not only as a package module.

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

The suite imports `runner.runner` with `runner` the package. An
install runs `python3 ~/.homing-pigeon/runner.py`, and the one-file
binaries run it frozen: there `runner` is this file, not the
package, and `from runner.ops import x` raises "'runner' is not a
package". That is why every sibling is loaded through `_load_mod`
(the package name first, the local name second) and named on every
build line as a hidden import. Two extractions in one afternoon
(2026-10-25) landed with package imports and took the installed
runner and the --help tests down; this test fails them before the
push.
"""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
RUNNER = os.path.join(ROOT, "runner", "runner.py")

_PACKAGE_IMPORT = re.compile(r"^(?:from runner[.\s]|import runner[.\s])",
                             re.M)


class ScriptContextTest(unittest.TestCase):
    def _version(self, cwd):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        return subprocess.run([sys.executable, RUNNER, "--version"],
                              cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True, timeout=120)

    def test_the_runner_starts_from_the_repo_root(self):
        r = self._version(ROOT)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])
        self.assertIn("runner.py", r.stdout)

    def test_the_runner_starts_from_inside_its_own_folder(self):
        # An install's layout: runner.py beside its role folders,
        # no package above it.
        r = self._version(os.path.join(ROOT, "runner"))
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])

    def test_runner_py_has_no_module_level_package_import(self):
        with open(RUNNER, encoding="utf-8") as fh:
            src = fh.read()
        hits = [m.group(0) for m in _PACKAGE_IMPORT.finditer(src)]
        self.assertEqual(
            hits, [],
            "runner.py imports a sibling as a package; load it with "
            "_load_mod(\"runner.<role>.<name>\", \"<role>.<name>\") and "
            "add --hidden-import runner.<role>.<name> to every build "
            "line in .github/workflows/build.yml")

    def test_every_load_mod_module_has_its_hidden_import(self):
        # test_build_config pins this too; here so the extraction
        # that adds a module sees both messages in one run.
        with open(RUNNER, encoding="utf-8") as fh:
            src = fh.read()
        with open(os.path.join(ROOT, ".github", "workflows", "build.yml"),
                  encoding="utf-8") as fh:
            build = fh.read()
        mods = set(re.findall(r'_load_mod\("(runner\.[A-Za-z0-9_.]+)"', src))
        self.assertGreater(len(mods), 20)
        for mod in sorted(mods):
            self.assertIn("--hidden-import " + mod + " ", build, mod)
