# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""The agent stamp record matches the tree.

docs/archive/RESEARCHER_IDENT.md lists every agent stamp and, in its
status table, whether each is active or recycled and who carries a
recycled stamp's roles. This holds that record honest: every stamp
written after a stamp label anywhere in the tracked tree is listed,
every listed stamp has a status row, and every recycled row names an
active successor. Researchers one to three, and five, are recycled,
and the campaigns seat's first stamp was retired for a named one
(AGENTS.md rule 10).
"""
import re
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDENT = ROOT / "docs" / "archive" / "RESEARCHER_IDENT.md"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# The campaigns seat's named stamp (registered 2026-10-27 at the
# conductor's word): a zero block, the seat's name, and hex for the
# rest. It is the one stamp the hex pattern cannot see, so the stamp
# pattern admits this exact form alongside it.
NAMED = r"00000000-muse-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
STAMP = r"(?:%s|%s)" % (NAMED, UUID)
RECYCLED = {
    "10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c",
    "200003d4-e5f6-4a7b-9c8d-0e1f2a3b4c5d",
    "30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a",
    "50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f",
    "58316a92-3c4a-41cb-8a16-8c0c5a871e90",
}


def _rows():
    rows = {}
    for line in IDENT.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|[^|]*\|\s*`(%s)`\s*\|\s*(\w+)\s*\|([^|]*)\|([^|]*)\|" % STAMP, line)
        if m:
            rows[m.group(1)] = (m.group(2), m.group(4))
    return rows


def _tree_stamps():
    """Every stamp written after a stamp label, outside .git and caches."""
    label = re.compile(r"stamp[^0-9a-f\n]{0,12}(%s)" % STAMP, re.I)
    found = set()
    for path in ROOT.rglob("*"):
        parts = path.relative_to(ROOT).parts
        if ".git" in parts or "__pycache__" in parts or "node_modules" in parts:
            continue
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found.update(label.findall(text))
    return found


class AgentStampRecordTest(unittest.TestCase):
    def test_every_listed_stamp_has_a_status(self):
        listed = set(re.findall(r"^(%s)$" % STAMP,
                                IDENT.read_text(encoding="utf-8"), re.M))
        self.assertTrue(listed)
        self.assertEqual(listed, set(_rows()))

    def test_researchers_one_to_three_are_recycled(self):
        rows = _rows()
        for stamp in RECYCLED:
            self.assertEqual(rows[stamp][0], "recycled", stamp)

    def test_each_recycled_role_has_an_active_carrier(self):
        rows = _rows()
        active = {s[:8] for s, (status, _) in rows.items() if status == "active"}
        for stamp, (status, carriers) in rows.items():
            if status != "recycled":
                self.assertEqual(status, "active", stamp)
                continue
            named = set(re.findall(r"`([0-9a-f]{8})`", carriers))
            self.assertTrue(named, stamp)
            self.assertLessEqual(named, active, stamp)

    def test_every_stamp_in_the_tree_is_on_the_record(self):
        found = _tree_stamps()
        self.assertIn("40000e00-1234-4abc-9def-0123456789ab", found)
        self.assertLessEqual(found, set(_rows()))

    def test_agents_md_names_the_recycled_stamps(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for stamp in RECYCLED:
            self.assertIn("`%s`" % stamp[:8], text)


from runner.tools import stamp_audit as SA  # noqa: E402

_T0 = SA.ENFORCED_FROM
_A = "40000e00-1234-4abc-9def-0123456789ab"
_B = "60000b3a-32a6-4847-996f-638cbcb6d854"
_OLD = "50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f"
_KNOWN = {_A: "active", _B: "active", _OLD: "recycled"}


def _c(minutes, stamps, session, sha=None):
    when = _T0 + SA.datetime.timedelta(minutes=minutes)
    return SA.Commit(sha or ("%040x" % (abs(minutes) + 1)), when, "Claude",
                     list(stamps), session, "a commit")


class StampAuditRulesTest(unittest.TestCase):
    """runner/tools/stamp_audit.py: the four rules, on made-up history."""

    def _rules(self, commits):
        _s, violations, history = SA.audit(commits, _KNOWN)
        return sorted(r for _c_, r, _m in violations), history

    def test_one_stamp_one_session_clean(self):
        self.assertEqual(self._rules([_c(1, [_A], "session_a"),
                                      _c(2, [_A], "session_a"),
                                      _c(3, [_B], "session_b")])[0], [])

    def test_a_session_on_the_stamp_s_record_is_the_same_chat(self):
        # The runtime reissued a chat's session id; the record's
        # sessions table names both, and rule 1 reads them as one chat.
        commits = [_c(1, [_A], "session_a"), _c(2, [_A], "session_a2"),
                   _c(3, [_A], "session_a")]
        _s, violations, _h = SA.audit(commits, _KNOWN,
                                      sessions={_A: {"session_a", "session_a2"}})
        self.assertEqual([], violations)
        # A third session not on the row is still a second chat.
        _s, violations, _h = SA.audit(commits + [_c(4, [_A], "session_a3")], _KNOWN,
                                      sessions={_A: {"session_a", "session_a2"}})
        self.assertEqual({"rule 1"}, {r for _c_, r, _m in violations})
        self.assertTrue(violations)
        # And with no row the old rule stands.
        _s, violations, _h = SA.audit(commits, _KNOWN)
        self.assertEqual({"rule 1"}, {r for _c_, r, _m in violations})
        self.assertTrue(violations)

    def test_the_record_s_sessions_table_parses(self):
        rows = SA.sessions_on_record()
        self.assertIn("80000aeb-9c1f-49ad-aeee-fa0855092587", rows)
        self.assertEqual(2, len(rows["80000aeb-9c1f-49ad-aeee-fa0855092587"]))
        for stamp, sessions in rows.items():
            self.assertIn(stamp, SA.record())
            self.assertTrue(all(x.startswith("session_") for x in sessions))

    def test_a_borrowed_stamp_breaks_rule_one_and_two(self):
        rules, _h = self._rules([_c(1, [_A], "session_a"),
                                 _c(2, [_B], "session_b"),
                                 _c(3, [_A], "session_b")])
        self.assertIn("rule 1", rules)
        self.assertIn("rule 2", rules)

    def test_a_recycled_stamp_signs_nothing_new(self):
        self.assertEqual(self._rules([_c(1, [_OLD], "session_x")])[0], ["rule 3"])

    def test_an_unknown_stamp_is_named(self):
        rules, _h = self._rules([_c(1, ["deadbeef-0000-4000-8000-000000000000"], None)])
        self.assertEqual(rules, ["rule 4"])

    def test_a_short_trailer_resolves_to_its_stamp(self):
        self.assertEqual(SA.resolve("40000e00", _KNOWN), _A)
        self.assertIsNone(SA.resolve("4000", _KNOWN))

    def test_history_is_reported_never_failed(self):
        rules, history = self._rules([_c(-10, [_A], "session_a"),
                                      _c(-9, [_A], "session_b"),
                                      _c(-8, [_OLD], "session_c")])
        self.assertEqual(rules, [])
        self.assertTrue(any("40000e00" in m for _r, m in history), history)

    def test_a_seat_without_sessions_is_held_to_rules_three_and_four(self):
        self.assertEqual(self._rules([_c(1, [_A], None), _c(2, [_B], None)])[0], [])

    def test_the_log_parser_reads_trailers_and_the_session(self):
        text = ("a" * 40 + "\x1f2026-10-28T00:00:00+00:00\x1fClaude\x1fsubject\n\n"
                "Agent-Stamp: " + _A + "\n"
                "Claude-Session: https://claude.ai/code/session_01ABC\n\x1e")
        (c,) = SA.parse_log(text)
        self.assertEqual(c.stamps, [_A])
        self.assertEqual(c.session, "session_01ABC")


class StampHistoryTest(unittest.TestCase):
    """The repository's own history holds the rules from ENFORCED_FROM
    on (a shallow clone is held as far as it reaches; the stamp-audit
    workflow reads the whole history)."""

    def test_no_violation_in_the_enforced_window(self):
        if shutil.which("git") is None:
            self.skipTest("git is not on PATH")
        commits = SA.git_log()
        if commits is None:
            self.skipTest("git is not on PATH")
        known = SA.record()
        _s, violations, _h = SA.audit(commits, known,
                                      sessions=SA.sessions_on_record(known=known))
        self.assertEqual([(c.sha[:9], r, m) for c, r, m in violations], [])


if __name__ == "__main__":
    unittest.main()
