# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The build stamp: a packaged tree names its source commit.

runner/_build.py carries __build__, written by
runner/tools/build_stamp.py at packaging time and "unknown" in a
plain checkout. The startup log prints the version alone when
the stamp is unknown, and " (build <commit>)" beside it when a
build stamped the tree -- so a log reader can tell at a glance
which code is executing, and the runner never shells out to git
at runtime to find out.
"""
import argparse
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import runner.runner as rr
from runner.tools import build_stamp as BS


def _startup_lines(build):
    rr._LOG_MINUTE = 0.0
    rr._LOG_COUNT = 0
    rr._LOG_DROPPED = 0
    with tempfile.TemporaryDirectory() as d:
        args = argparse.Namespace(
            verbose=False, workers=None, poll_interval=None,
            max_output_bytes=None, timeout=None,
            dry_run=False, once=False, no_send=False)
        buf = io.StringIO()
        with mock.patch.object(rr, "__build__", build), \
                redirect_stdout(buf):
            rr.log_startup({}, args, d)
        return buf.getvalue()


class StartupLineTest(unittest.TestCase):
    def test_unknown_stamp_prints_the_version_alone(self):
        out = _startup_lines("unknown")
        self.assertIn("homing-pigeon %s starting" % rr.__version__, out)
        self.assertNotIn("(build", out)

    def test_a_missing_stamp_prints_the_version_alone(self):
        out = _startup_lines(None)
        self.assertIn("homing-pigeon %s starting" % rr.__version__, out)
        self.assertNotIn("(build", out)

    def test_a_stamped_build_names_its_commit_on_both_lines(self):
        out = _startup_lines("c0ba079d1234")
        self.assertIn(
            "homing-pigeon %s (build c0ba079d1234) starting"
            % rr.__version__, out)
        self.assertIn(
            "homing-pigeon %s (build c0ba079d1234) invocation:"
            % rr.__version__, out)


class StampModuleTest(unittest.TestCase):
    def test_the_checkout_stamp_is_unknown(self):
        from runner import _build
        self.assertEqual(_build.__build__, "unknown")
        self.assertEqual(rr.__build__, _build.__build__)


class WriteStampTest(unittest.TestCase):
    def test_the_tool_writes_a_readable_stamp(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "runner"))
            path = BS.write_build_stamp(d, "6697271c3b7a")
            self.assertTrue(path.endswith(os.path.join(
                "runner", "_build.py")))
            ns = {}
            with open(path, encoding="utf-8") as fh:
                exec(fh.read(), ns)
            self.assertEqual(ns["__build__"], "6697271c3b7a")

    def test_the_tool_refuses_a_non_commit_value(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "runner"))
            for bad in ("", "unknown", "not hex!", "ABCDEF1", "abc"):
                with self.assertRaises(ValueError, msg=bad):
                    BS.write_build_stamp(d, bad)

    def test_the_tool_refuses_a_tree_without_a_runner(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                BS.write_build_stamp(d, "6697271c")


if __name__ == "__main__":
    unittest.main()
