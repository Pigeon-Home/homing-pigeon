"""Harness pins on the Mac App Store tool's version mapping
and its command line (runner/tools/apple_store.py).

test_apple_store.py pins the planner, the chain and the
rendered plist on well-shaped versions. This file pins what
that file does not reach: the version argument fuzzed with
the bookend family (every ASCII symbol, plus NUL, tab, CR
and LF, front and back), the shapes the mapping normalizes
or refuses at its edges, and the tool's own main() — the
plan and render routes, the --out file, and the usage
errors the workflow depends on.
"""

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "apple_store",
    os.path.join(REPO, "runner", "tools", "apple_store.py"))
apple_store = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apple_store)

VERSION = "3.17.33.1"
SYMBOLS = [chr(c) for c in range(33, 127)
           if not chr(c).isalnum()]


def _full_state():
    return {
        "app_distribution_p12": True,
        "installer_distribution_p12": True,
        "provisioning_profile": True,
        "api_key": True,
        "api_key_id": "ABC123DEFG",
        "api_key_issuer_id": "12345678-1234-1234-1234-1234567890ab",
    }


class VersionBookendTest(unittest.TestCase):
    """A release version is 4 plain integer parts and nothing
    else; any bookend makes it a version this tool refuses
    rather than maps."""

    def test_symbol_bookends_refuse(self):
        for mark in SYMBOLS:
            for candidate in (mark + VERSION, VERSION + mark,
                              mark + VERSION + mark):
                with self.assertRaises(ValueError,
                                       msg=repr(candidate)):
                    apple_store.store_version(candidate)

    def test_edge_bookends_refuse(self):
        for mark in ("\x00", "\t", "\r", "\n", " "):
            for candidate in (mark + VERSION, VERSION + mark,
                              mark + VERSION + mark):
                with self.assertRaises(ValueError,
                                       msg=repr(candidate)):
                    apple_store.store_build(candidate)

    def test_runs_and_symbol_only_versions_refuse(self):
        for candidate in (";" * 10 + VERSION,
                          VERSION + ";" * 10,
                          ";" * 10, "", "\x00", "...."):
            with self.assertRaises(ValueError,
                                   msg=repr(candidate)):
                apple_store.store_version(candidate)

    def test_an_odd_part_anywhere_refuses(self):
        for candidate in ("3.17.33.-1", "3.17.33.+1",
                          "3.17.33. 1", "3.17.33.1a",
                          "3..33.1", "3.17.33.", ".3.17.33.1"):
            with self.assertRaises(ValueError,
                                   msg=repr(candidate)):
                apple_store.store_version(candidate)


class VersionShapeTest(unittest.TestCase):

    def test_leading_zeros_normalize(self):
        self.assertEqual("3.17.33",
                         apple_store.store_version("03.17.33.01"))
        self.assertEqual("33.1",
                         apple_store.store_build("03.17.33.01"))

    def test_wrong_part_counts_refuse(self):
        for candidate in ("3", "3.17", "3.17.33",
                          "3.17.33.1.5", "3.17.33.1.5.9"):
            with self.assertRaises(ValueError,
                                   msg=repr(candidate)):
                apple_store.store_version(candidate)

    def test_non_ascii_digits_normalize_like_ascii(self):
        # int() and str.isdigit() both accept the decimal
        # digits of other scripts, so the mapping takes them
        # and hands back plain ASCII numbers. Pinned as the
        # standing behavior: the store only ever sees the
        # mapped ASCII shape.
        self.assertEqual(
            "3.17.33", apple_store.store_version("٣.17.33.1"))
        self.assertEqual(
            "3.17.33", apple_store.store_version("３.17.33.1"))

    def test_a_non_string_version_is_refused(self):
        # The mapping's contract is ValueError for anything
        # that is not the 4 part number; a value that is not
        # a string at all is refused the same way, never with
        # an AttributeError from deep in the split.
        for candidate in (None, 42, 3.17, ["3.17.33.1"],
                          b"3.17.33.1"):
            with self.assertRaises(ValueError,
                                   msg=repr(candidate)):
                apple_store.store_version(candidate)


class MainTest(unittest.TestCase):
    """The CLI the macOS store workflow runs: a state file
    and a version in, the plan or the rendered plist out,
    0 on a standing plan and 3 on a refusal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = os.path.join(self.tmp.name, "state.json")

    def _write(self, state):
        with open(self.state, "w", encoding="utf-8") as fh:
            json.dump(state, fh)

    def _run(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = apple_store.main(argv)
        return rc, out.getvalue()

    def test_a_full_state_plans_and_exits_0(self):
        self._write(_full_state())
        rc, out = self._run(["--state", self.state,
                             "--version", VERSION])
        self.assertEqual(0, rc)
        self.assertIn("upload version %s" % VERSION, out)
        self.assertIn("altool --upload-app", out)

    def test_a_missing_piece_exits_3_and_prints_no_command(self):
        self._write({})
        rc, out = self._run(["--state", self.state,
                             "--version", VERSION])
        self.assertEqual(3, rc)
        self.assertIn("missing", out)
        self.assertNotIn("altool", out)

    def test_the_render_route_prints_a_plist(self):
        rc, out = self._run(["--render-info-plist",
                             "--version", VERSION])
        self.assertEqual(0, rc)
        self.assertIn("<plist", out)
        self.assertIn("3.17.33", out)

    def test_the_render_route_writes_the_out_file(self):
        target = os.path.join(self.tmp.name, "Info.plist")
        rc, out = self._run(["--render-info-plist",
                             "--version", VERSION,
                             "--out", target])
        self.assertEqual(0, rc)
        self.assertEqual("", out)
        with open(target, encoding="utf-8") as fh:
            self.assertIn("<plist", fh.read())

    def test_render_without_a_version_is_a_usage_error(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                apple_store.main(["--render-info-plist"])
        self.assertEqual(2, caught.exception.code)

    def test_planning_without_state_or_version_is_a_usage_error(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                apple_store.main([])
        self.assertEqual(2, caught.exception.code)

    def test_a_bad_version_on_the_render_route_raises(self):
        with self.assertRaises(ValueError):
            self._run(["--render-info-plist",
                       "--version", ";3.17.33.1;"])


if __name__ == "__main__":
    unittest.main()
