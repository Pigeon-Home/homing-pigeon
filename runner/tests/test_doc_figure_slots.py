"""Headline figures: the evergreen slots answer to the facts.

Settled 2026-11-08, after the dated-mention shape was tried
and critiqued: a hand-restated figure rots even when it is
dated and linked -- AGENTS.md carried "17 million tokens"
from 2026-11-03 while the tree measured 20,163,806, and a
prose-shape guard would only have legalized the next stale
figure in fresher dress. So the evergreen docs no longer
restate the volatile figures. The statistics record
(docs/infrastructure-documents/project/statistics.md) carries
a fenced JSON block, the facts; the marked slots in
AGENTS.md, PROTOCOL.md and docs/steady/fuzzing.md are filled
from it by runner/tools/refresh_figures.py, and this test is
the consistency check: every slot's contents equal the
facts, and the record's display line is the line its own
facts render.

The one value pin here is against the facts file, never
against the live tree -- the facts are the single home the
refresh step rewrites (measure first, statistics write as
the last content commit; the figures cite their measured
commit). Dated prose that discusses a figure as history --
the markdown subset's 2026-11-05 measure, the 2026-11-03
audit's percentages, the core's 2026-11-04 first assembly --
is not slotted and is not this test's business.
"""
import os
import re
import unittest

from runner.tools import refresh_figures as RF

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
STATISTICS = os.path.join(REPO, RF.STATISTICS_REL)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestFactsBlock(unittest.TestCase):
    def test_facts_parse_and_are_complete(self):
        facts = RF.parse_facts(_read(STATISTICS))
        for key in RF.FACT_KEYS:
            self.assertIn(key, facts)
        self.assertRegex(facts["as_of"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(facts["commit"], r"^[0-9a-f]{40}$")
        self.assertGreater(facts["tokens"], 0)

    def test_display_line_is_the_facts_line(self):
        facts = RF.parse_facts(_read(STATISTICS))
        self.assertIn(RF.display_line(facts),
                      _read(STATISTICS).splitlines())

    def test_security_tokens_is_glossed_at_the_record(self):
        # The display line's coinage is the owner's settled
        # naming; the record glosses it once, as the count of
        # the tree's tokens by the project's own estimator, so
        # a cold reader cannot mistake it for credentials.
        self.assertIn(
            "security\n  tokens is this record's name for the "
            "tree's tokens counted\n  by the project's own "
            "estimator", _read(STATISTICS))

    def test_record_names_its_verify_routes(self):
        text = _read(STATISTICS)
        self.assertIn("version4.py measure", text)
        self.assertIn("CI-SNAPSHOT.json", text)
        self.assertIn("PROJECT-SNAPSHOT.md", text)
        self.assertIn("gh attestation verify", text)


class TestThirdSnapshot(unittest.TestCase):
    # Two parallel lanes each landed a third snapshot for
    # 2026-11-16 minutes apart on 2026-11-16; the record keeps
    # exactly one -- the conductor-picked projected view, with
    # its exponential-approach curve and its interactive
    # original beside the record -- and the duplicate logistic
    # view, its section and its 2 assets, stands removed. These
    # tests pin that reconciliation so a second third snapshot
    # cannot land unnoticed again.
    KEPT_HEADING = ("## The growth of the measure, projected: "
                    "a third snapshot as of 2026-11-16")
    DUPLICATE_HEADING = ("## The growth of the measure, "
                         "continued: a third snapshot as of "
                         "2026-11-16")

    def test_exactly_one_third_snapshot_for_2026_11_16(self):
        headings = [line for line in _read(STATISTICS).splitlines()
                    if line.startswith("## ")
                    and "third snapshot as of 2026-11-16" in line]
        self.assertEqual([self.KEPT_HEADING], headings)

    def test_kept_third_snapshot_precedes_where_the_project_stands(self):
        lines = _read(STATISTICS).splitlines()
        self.assertLess(lines.index(self.KEPT_HEADING),
                        lines.index("## Where the project stands"))
        self.assertNotIn(self.DUPLICATE_HEADING, lines)

    def test_kept_snapshot_assets_stand(self):
        text = _read(STATISTICS)
        self.assertIn("security-tokens-growth-2026-11-16.svg", text)
        self.assertTrue(os.path.isfile(os.path.join(
            REPO, "assets", "security-tokens-growth-2026-11-16.svg")))
        self.assertTrue(os.path.isfile(os.path.join(
            os.path.dirname(STATISTICS),
            "security-tokens-asymptotic-view.html")))

    def test_duplicate_snapshot_assets_are_gone(self):
        text = _read(STATISTICS)
        self.assertNotIn("security-tokens-asymptotic-2026-11-16",
                         text)
        for name in ("security-tokens-asymptotic-2026-11-16.svg",
                     "security-tokens-asymptotic-2026-11-16.html"):
            self.assertFalse(
                os.path.exists(os.path.join(REPO, "assets", name)),
                name)


class TestFigureSlots(unittest.TestCase):
    def test_slots_and_display_line_match_the_facts(self):
        self.assertEqual([], RF.check(REPO))

    def test_renderings_carry_the_tracked_line_count(self):
        # The facts' lines_tracked is the whole repository's
        # line count over tracked files; its rendering is the
        # comma-grouped figure, so a slot can carry it.
        facts = RF.parse_facts(_read(STATISTICS))
        self.assertEqual(format(facts["lines_tracked"], ","),
                         RF.renderings(facts)["lines_tracked"])

    def test_protocol_carries_the_line_count_slot(self):
        # PROTOCOL.md's fair warning states the tree's line
        # count as its own statistic, in its own slot, so the
        # refresh step keeps it and a change to it diffs as
        # one line.
        facts = RF.parse_facts(_read(STATISTICS))
        slots = dict(RF.find_slots(
            _read(os.path.join(REPO, "PROTOCOL.md"))))
        self.assertEqual(
            format(facts["lines_tracked"], ","),
            slots.get("lines_tracked"))

    def test_slots_are_present_in_each_evergreen_doc(self):
        facts = RF.parse_facts(_read(STATISTICS))
        wanted = RF.renderings(facts)
        total = 0
        for rel in RF.SLOT_FILES:
            slots = RF.find_slots(_read(os.path.join(REPO, rel)))
            self.assertGreater(len(slots), 0, rel)
            total += len(slots)
            for name, value in slots:
                self.assertIn(name, wanted)
                self.assertEqual(wanted[name], value,
                                 "%s slot %s" % (rel, name))
        self.assertGreater(total, 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
