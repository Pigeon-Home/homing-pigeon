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
        from runner.install import main
        code, out = _run_version_flag(main, "install")
        self.assertEqual(code, 0)
        self.assertIn(_repo_version(), out)

    def test_send_job_version(self):
        from cloud.send_job import main
        code, out = _run_version_flag(main, "send-job")
        self.assertEqual(code, 0)
        self.assertIn(_repo_version(), out)

    def test_oauth_version(self):
        from runner.oauth import main
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
