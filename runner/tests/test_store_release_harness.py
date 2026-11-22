"""Harness pins on the Snap Store release planner's edges and
its command line (runner/tools/store_release.py).

test_store_release.py pins the planner's stated rules on
well-shaped store state. This file pins what that file does
not reach: every review state the store can hold a revision
in, the newest revision's hold outranking an older approved
one, shapes the store state can actually arrive in (unknown
architectures, a revision with no channel list), the version
argument fuzzed with the bookend family, and the tool's own
main() — the exit codes and printed lines the pipeline step
that carries the plan out depends on.
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
    "store_release",
    os.path.join(REPO, "runner", "tools", "store_release.py"))
store_release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(store_release)

VERSION = "3.17.32.13"


def _rev(revision, arch, version=VERSION, status="Approved",
         channels=()):
    return {"revision": revision, "architecture": arch,
            "version": version, "status": status,
            "channels": list(channels) if channels is not None
            else None}


class HeldStatesTest(unittest.TestCase):
    """Every state in HELD_STATES gets its own test: the set
    is the rule, and a state dropped from it would reopen the
    Releases page fight for exactly that state."""

    def _plan(self, status):
        return store_release.plan_release(
            [_rev(20, "amd64", status=status), _rev(21, "arm64")],
            VERSION)

    def test_review_queued_holds(self):
        plan = self._plan("ReviewQueued")
        self.assertFalse(plan["ok"])
        self.assertEqual([], plan["commands"])
        self.assertIn("ReviewQueued", plan["reason"])

    def test_review_in_progress_holds(self):
        plan = self._plan("ReviewInProgress")
        self.assertFalse(plan["ok"])
        self.assertEqual([], plan["commands"])
        self.assertIn("ReviewInProgress", plan["reason"])

    def test_review_pending_holds(self):
        plan = self._plan("ReviewPending")
        self.assertFalse(plan["ok"])
        self.assertEqual([], plan["commands"])
        self.assertIn("ReviewPending", plan["reason"])

    def test_manual_review_pending_holds(self):
        plan = self._plan("ManualReviewPending")
        self.assertFalse(plan["ok"])
        self.assertEqual([], plan["commands"])
        self.assertIn("ManualReviewPending", plan["reason"])

    def test_the_held_set_is_exactly_the_four_review_states(self):
        self.assertEqual(
            {"ReviewQueued", "ReviewInProgress", "ReviewPending",
             "ManualReviewPending"},
            set(store_release.HELD_STATES))

    def test_a_status_outside_the_held_set_does_not_hold(self):
        # The planner's rule names the review states and no
        # others; any other status on the newest revision is
        # planned like an approved one.
        plan = self._plan("Rejected")
        self.assertTrue(plan["ok"])
        self.assertTrue(plan["commands"])


class NewestRevisionWinsTest(unittest.TestCase):

    def test_a_held_newest_refuses_over_an_approved_older(self):
        # The newest revision per architecture is the one the
        # store would release; an older approved revision
        # standing behind a held newest must not slip out.
        plan = store_release.plan_release(
            [_rev(20, "amd64"),
             _rev(22, "amd64", status="ReviewQueued"),
             _rev(21, "arm64")], VERSION)
        self.assertFalse(plan["ok"])
        self.assertEqual([], plan["commands"])
        self.assertIn("amd64", plan["reason"])

    def test_an_approved_newest_releases_over_a_held_older(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64", status="ReviewQueued"),
             _rev(22, "amd64"),
             _rev(21, "arm64")], VERSION)
        self.assertTrue(plan["ok"])
        self.assertIn(" 22 ", plan["commands"][0])


class StateShapeTest(unittest.TestCase):

    def test_an_unknown_architecture_is_ignored(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64"), _rev(21, "arm64"),
             _rev(99, "riscv64")], VERSION)
        self.assertTrue(plan["ok"])
        self.assertNotIn("99", " ".join(plan["commands"]))

    def test_only_an_unknown_architecture_is_a_missing_arch(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64"), _rev(99, "riscv64")], VERSION)
        self.assertFalse(plan["ok"])
        self.assertIn("arm64", plan["reason"])

    def test_a_revision_with_no_channel_list_releases_fully(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64", channels=None),
             _rev(21, "arm64", channels=None)], VERSION)
        self.assertTrue(plan["ok"])
        self.assertEqual(2, len(plan["commands"]))

    def test_revisions_may_arrive_as_a_generator(self):
        plan = store_release.plan_release(
            iter([_rev(20, "amd64"), _rev(21, "arm64")]), VERSION)
        self.assertTrue(plan["ok"])

    def test_an_empty_channel_target_releases_nothing(self):
        plan = store_release.plan_release(
            [_rev(20, "amd64"), _rev(21, "arm64")], VERSION,
            channels=())
        self.assertTrue(plan["ok"])
        self.assertEqual([], plan["commands"])


class VersionFuzzTest(unittest.TestCase):
    """The version argument is text the caller hands in; the
    bookend family (every ASCII symbol, plus NUL, tab, CR and
    LF, front and back) must never match a standing version,
    so a fuzzed version refuses with no commands."""

    BOOKENDS = [chr(c) for c in range(33, 127)
                if not chr(c).isalnum()] + ["\x00", "\t", "\r",
                                            "\n", " "]

    def test_bookended_versions_refuse(self):
        revisions = [_rev(20, "amd64"), _rev(21, "arm64")]
        for mark in self.BOOKENDS:
            for candidate in (mark + VERSION, VERSION + mark,
                              mark + VERSION + mark,
                              mark * 10 + VERSION,
                              VERSION + mark * 10):
                plan = store_release.plan_release(
                    revisions, candidate)
                self.assertFalse(plan["ok"], repr(candidate))
                self.assertEqual([], plan["commands"],
                                 repr(candidate))

    def test_symbol_only_versions_refuse(self):
        revisions = [_rev(20, "amd64"), _rev(21, "arm64")]
        for candidate in ("", ";", "\x00", ";;;", "\t\r\n"):
            plan = store_release.plan_release(revisions,
                                              candidate)
            self.assertFalse(plan["ok"], repr(candidate))
            self.assertEqual([], plan["commands"],
                             repr(candidate))


class MainTest(unittest.TestCase):
    """The CLI the pipeline runs: a JSON state file in, the
    reason and the commands out, 0 when the plan stands and
    3 when it refuses."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = os.path.join(self.tmp.name, "state.json")

    def _write(self, revisions):
        with open(self.state, "w", encoding="utf-8") as fh:
            json.dump(revisions, fh)

    def _run(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = store_release.main(argv)
        return rc, out.getvalue()

    def test_a_releasable_state_exits_0_and_prints_the_plan(self):
        self._write([_rev(20, "amd64"), _rev(21, "arm64")])
        rc, out = self._run(["--state", self.state,
                             "--version", VERSION])
        self.assertEqual(0, rc)
        lines = out.splitlines()
        self.assertIn(VERSION, lines[0])
        self.assertEqual(
            ["snapcraft release homing-pigeon 20 "
             "latest/stable,latest/edge",
             "snapcraft release homing-pigeon 21 "
             "latest/stable,latest/edge"], lines[1:])

    def test_a_held_state_exits_3_and_prints_no_command(self):
        self._write([_rev(20, "amd64", status="ReviewQueued"),
                     _rev(21, "arm64")])
        rc, out = self._run(["--state", self.state,
                             "--version", VERSION])
        self.assertEqual(3, rc)
        self.assertIn("ReviewQueued", out)
        self.assertNotIn("snapcraft release", out)

    def test_channels_flag_narrows_the_release(self):
        self._write([_rev(20, "amd64"), _rev(21, "arm64")])
        rc, out = self._run(["--state", self.state,
                             "--version", VERSION,
                             "--channels", "latest/edge"])
        self.assertEqual(0, rc)
        self.assertIn("20 latest/edge", out)
        self.assertNotIn("latest/stable", out)

    def test_a_missing_state_argument_is_a_usage_error(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                store_release.main(["--version", VERSION])
        self.assertEqual(2, caught.exception.code)

    def test_a_missing_state_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self._run(["--state",
                       os.path.join(self.tmp.name, "nope.json"),
                       "--version", VERSION])

    def test_a_malformed_state_file_raises(self):
        with open(self.state, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        with self.assertRaises(json.JSONDecodeError):
            self._run(["--state", self.state,
                       "--version", VERSION])


if __name__ == "__main__":
    unittest.main()
