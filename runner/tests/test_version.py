"""--version on every CLI, and the version constant never drifts."""

import os
import re
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock


def _repo_version():
    import runner
    root = os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))
    with open(os.path.join(root, "pyproject.toml"), encoding="utf-8") as fh:
        m = re.search(r'^version\s*=\s*"([^"]+)"', fh.read(), re.M)
    assert m, "no version in pyproject.toml"
    return m.group(1)


def _run_version_flag(main, prog):
    buf = StringIO()
    with mock.patch("sys.argv", [prog, "--version"]), redirect_stdout(buf):
        with unittest.TestCase().assertRaises(SystemExit) as cm:
            main()
    return cm.exception.code, buf.getvalue()


class VersionConsistencyTest(unittest.TestCase):
    def test_version_module_matches_pyproject(self):
        from runner import _version
        self.assertEqual(_version.__version__, _repo_version())


class VersionFlagTest(unittest.TestCase):
    def test_runner_version(self):
        from runner.runner import main
        code, out = _run_version_flag(main, "homing-pigeon")
        self.assertEqual(code, 0)
        self.assertIn(_repo_version(), out)

    def test_install_version(self):
        from runner.ops.install import main
        code, out = _run_version_flag(main, "install")
        self.assertEqual(code, 0)
        self.assertIn(_repo_version(), out)

    def test_send_job_version(self):
        from runner.cloud.send_job import main
        code, out = _run_version_flag(main, "send-job")
        self.assertEqual(code, 0)
        self.assertIn(_repo_version(), out)

    def test_oauth_version(self):
        from runner.wire.oauth import main
        code, out = _run_version_flag(main, "oauth")
        self.assertEqual(code, 0)
        self.assertIn(_repo_version(), out)

    def test_runner_startup_logs_version(self):
        # The version must be visible in the logs, not just --version.
        import argparse
        import io
        import tempfile
        from contextlib import redirect_stdout
        from runner.runner import log_startup
        import runner.runner as _r
        # log() rate-limits INFO lines per minute; reset the budget so the
        # startup line is not suppressed by earlier tests in the suite.
        _r._LOG_MINUTE = 0.0
        _r._LOG_COUNT = 0
        _r._LOG_DROPPED = 0
        with tempfile.TemporaryDirectory() as d:
            args = argparse.Namespace(
                verbose=False, workers=None, poll_interval=None,
                max_output_bytes=None, timeout=None,
                dry_run=False, once=False, no_send=False)
            buf = io.StringIO()
            with redirect_stdout(buf):
                log_startup({}, args, d)
            self.assertIn("homing-pigeon " + _repo_version() + " starting",
                          buf.getvalue())


class FrozenPackageImportsTest(unittest.TestCase):
    """The release `install` binary is PyInstaller-built from
    runner/ops/install.py with no --hidden-import list, so it bundles only
    what static imports reach. `import runner` re-exports names that
    runner.runner takes from runner.wire.mailbox, which runner.runner loads
    dynamically; if nothing imports runner.wire.mailbox statically, the
    frozen `import runner` fails (install --version printed 'unknown'
    and the setup wizard was skipped). modulefinder traces static
    imports the way PyInstaller's analysis does."""

    def test_import_runner_statically_reaches_mailbox(self):
        import modulefinder
        import sys
        import runner
        root = os.path.dirname(os.path.dirname(
            os.path.abspath(runner.__file__)))
        # The finder path is the repo root plus the stdlib dirs --
        # NOT site-packages. The runner is stdlib-only, so nothing
        # it statically reaches lives there; and with site-packages
        # on the path the finder wanders into third-party packages
        # and dies on namespace packages whose spec.loader is None
        # (setuptools._vendor: modulefinder raises AttributeError,
        # not a recorded bad module). That crash made this test
        # fail whenever it ran in a clean process (standalone, or
        # a parallel-runner shard) and pass in the monolithic
        # suite only because earlier tests had mutated sys.path
        # first -- the pipeline-hardening pass caught it in a
        # shard, which is the shape CI's Windows job runs.
        rest = [p for p in sys.path
                if os.path.abspath(p or os.curdir) != root
                and "site-packages" not in p
                and "dist-packages" not in p]
        finder = modulefinder.ModuleFinder(path=[root] + rest)
        finder.import_hook("runner")
        for name in ("runner.runner", "runner.wire.mailbox"):
            self.assertIn(name, finder.modules,
                          f"{name} is not statically reachable from "
                          f"`import runner`; a frozen build without a "
                          f"--hidden-import list would not bundle it")


if __name__ == "__main__":
    unittest.main(verbosity=2)
