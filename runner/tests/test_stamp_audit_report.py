# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/stamp_audit.py: what the push gate prints and returns.

test_agent_stamps holds the four rules. This holds the rest of the
tool a person reads: the log parser skips a record it cannot read
instead of failing the audit, a box without git (or outside a repo)
is "no history" and exit 2, unstamped commits are counted by author
with the newest, the report names every stamp on the record, every
violation and every history line in plain text and in Markdown, and
--check turns a violation into exit 1 while a clean window is 0.
"""
import contextlib
import datetime
import io
import subprocess
import unittest
from unittest import mock

from runner.tools import stamp_audit as SA  # noqa: E402

_A = "40000e00-1234-4abc-9def-0123456789ab"
_B = "60000b3a-32a6-4847-996f-638cbcb6d854"
_OLD = "50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f"
_KNOWN = {_A: "active", _B: "active", _OLD: "recycled"}
_T0 = SA.ENFORCED_FROM


def _c(minutes, stamps, session, author="Claude", subject="a commit"):
    when = _T0 + datetime.timedelta(minutes=minutes)
    return SA.Commit("%040x" % (abs(minutes) + 7), when, author,
                     list(stamps), session, subject)


def _rec(sha, when, author, body):
    return "%s\x1f%s\x1f%s\x1f%s\x1e" % (sha, when, author, body)


class ParseLogTest(unittest.TestCase):
    def test_a_record_it_cannot_read_is_skipped_not_fatal(self):
        good = _rec("a" * 40, "2026-10-28T01:00:00+00:00", "Claude",
                    "good\n\nAgent-Stamp: %s\n" % _A)
        short = "b" * 40 + "\x1f2026-10-28T01:00:00+00:00\x1fonly three\x1e"
        bad_date = _rec("c" * 40, "yesterday", "Claude", "bad date\n")
        commits = SA.parse_log("\n" + short + bad_date + good + "\n\x1e")
        self.assertEqual([c.sha for c in commits], ["a" * 40])
        self.assertEqual(commits[0].subject, "good")
        self.assertIsNone(commits[0].session)

    def test_more_than_one_trailer_is_kept_in_order(self):
        body = ("two\n\nAgent-Stamp: %s\nAgent-Chat-Stamp: %s\n" % (_A, _B[:8]))
        (c,) = SA.parse_log(_rec("d" * 40, "2026-10-28T01:00:00Z", "Claude",
                                 body))
        self.assertEqual(c.stamps, [_A, _B[:8]])
        self.assertEqual(SA.resolve(c.stamps[1], _KNOWN), _B)


class GitLogTest(unittest.TestCase):
    def test_no_git_binary_is_no_history(self):
        with mock.patch.object(SA.subprocess, "run",
                               side_effect=FileNotFoundError("git")):
            self.assertIsNone(SA.git_log())

    def test_outside_a_repository_is_no_history(self):
        done = subprocess.CompletedProcess(["git"], 128, "",
                                           "fatal: not a git repository")
        with mock.patch.object(SA.subprocess, "run", return_value=done):
            self.assertIsNone(SA.git_log())


class UnstampedTest(unittest.TestCase):
    def test_counted_by_author_with_the_newest(self):
        commits = [_c(1, [], None, author="Muse"),
                   _c(5, [], None, author="Muse"),
                   _c(3, [], None, author="Muse"),
                   _c(2, [_A], "session_a", author="Muse"),
                   _c(4, [], None, author="Grok")]
        out = SA.unstamped(commits)
        self.assertEqual(set(out), {"Muse", "Grok"})
        self.assertEqual(out["Muse"][0], 3)
        self.assertEqual(out["Muse"][1], commits[1].when)
        self.assertEqual(out["Grok"], (1, commits[4].when))


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.commits = [_c(1, [_A], "session_aaaaaa"),
                        _c(2, [_A], "session_aaaaaa"),
                        _c(3, [_OLD], "session_cccccc",
                           subject="tests: a recycled seat signs again"),
                        _c(-5, [_B], "session_bbbbbb"),
                        _c(-4, [_B], "session_dddddd")]
        self.summary, self.violations, self.history = SA.audit(
            self.commits, _KNOWN)

    def test_plain_text_names_stamps_violations_and_history(self):
        text = SA.report(self.summary, self.violations, self.history,
                         _KNOWN, commits=len(self.commits))
        self.assertTrue(text.startswith("Stamp audit\n"))
        self.assertIn("5 commits read; rules enforced from %s"
                      % _T0.isoformat(), text)
        for stamp in _KNOWN:
            self.assertIn(stamp[:8], text)
        self.assertIn("aaaaaa x2", text)
        self.assertIn("- rule 3: ", text)
        self.assertIn("(tests: a recycled seat signs again)", text)
        self.assertIn("stamp 60000b3a was signed from 2 sessions", text)
        self.assertNotIn("Commits with no stamp", text)
        self.assertNotIn("|", text)

    def test_markdown_is_a_table_with_headings(self):
        text = SA.report(self.summary, self.violations, self.history,
                         _KNOWN, markdown=True, commits=5)
        self.assertTrue(text.startswith("# Stamp audit\n"))
        self.assertIn("## Violations (enforced window)", text)
        self.assertIn("| Stamp | Record | Commits | Sessions | First | Last |",
                      text)
        self.assertIn("| `40000e00` | active | 2 | aaaaaa x2 |", text)
        self.assertIn("| `50000c8e` | recycled | 1 |", text)

    def test_a_clean_window_and_no_history_say_none(self):
        summary, violations, history = SA.audit(
            [_c(1, [_A], "session_aaaaaa")], _KNOWN)
        text = SA.report(summary, violations, history, _KNOWN, commits=1)
        self.assertEqual(text.count("- none"), 2)
        self.assertIn("60000b3a  active        0  -..-  -", text)

    def test_unstamped_authors_are_listed_when_asked(self):
        bare = SA.unstamped([_c(1, [], None, author="Grok"),
                             _c(2, [], None, author="Grok"),
                             _c(3, [], None, author="Muse")])
        text = SA.report({}, [], [], _KNOWN, commits=3, bare=bare)
        day = (_T0 + datetime.timedelta(minutes=2)).date().isoformat()
        self.assertIn("Commits with no stamp, by author", text)
        self.assertLess(text.index("- Grok: 2"), text.index("- Muse: 1"))
        self.assertIn("- Grok: 2 (newest %s)" % day, text)


class MainTest(unittest.TestCase):
    def _main(self, argv, commits):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(SA, "git_log", return_value=commits), \
                mock.patch.object(SA, "record", return_value=dict(_KNOWN)), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = SA.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_no_history_is_exit_two(self):
        rc, out, err = self._main([], None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("no git history here", err)

    def test_check_fails_only_on_a_violation(self):
        clean = [_c(1, [_A], "session_aaaaaa")]
        dirty = clean + [_c(2, [_OLD], "session_cccccc")]
        self.assertEqual(self._main(["--check"], clean)[0], 0)
        rc, out, _err = self._main(["--check"], dirty)
        self.assertEqual(rc, 1)
        self.assertIn("- rule 3: ", out)
        self.assertEqual(self._main([], dirty)[0], 0)

    def test_markdown_and_authors_reach_the_report(self):
        commits = [_c(1, [_A], "session_aaaaaa"),
                   _c(2, [], None, author="Grok")]
        rc, out, _err = self._main(["--markdown", "--authors"], commits)
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("# Stamp audit"))
        self.assertIn("## Commits with no stamp, by author", out)
        self.assertIn("- Grok: 1", out)


if __name__ == "__main__":
    unittest.main()
