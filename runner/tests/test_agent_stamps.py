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


if __name__ == "__main__":
    unittest.main()
