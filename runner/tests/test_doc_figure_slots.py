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

The record's own list of what stands behind each figure
took the same slots on 2026-11-16. Its token, line and
commit figures had been restated by hand at each refresh,
the refresh rewrote the facts and the display line beside
them, and the list read 24,396,328 tokens and 5,874 commits
under a display line of 26 mil and 6,000: the shape this
module was written against, inside the record itself.
RF.RECORD_SLOTS names the figures the list states, and the
check names any of them the list no longer carries in a slot.
"""
import os
import re
import shutil
import tempfile
import unittest
from unittest import mock

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


class TestFourthSnapshot(unittest.TestCase):
    # The fourth snapshot splits each count of the series in 2,
    # the fuzz campaign's run log and everything else, on counts
    # of the tagged trees. Its table is arithmetic a reader can
    # redo, and this pins the part that needs no checkout: every
    # row's 2 parts make its whole, and the series it carries is
    # the one the earlier snapshots follow.
    HEADING = ("## What the measure is made of: a fourth snapshot "
               "as of 2026-11-16")

    def _rows(self):
        lines = _read(STATISTICS).splitlines()
        start = lines.index(self.HEADING)
        end = lines.index("## Where the project stands")
        rows = []
        for line in lines[start:end]:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 5 and re.match(r"^\d{4}-\d{2}-\d{2}$", cells[0]):
                rows.append((cells[0], cells[1]) + tuple(
                    int(c.replace(",", "")) for c in cells[2:]))
        return rows

    def test_the_snapshot_stands_once_between_the_third_and_the_close(self):
        lines = _read(STATISTICS).splitlines()
        self.assertEqual(1, lines.count(self.HEADING))
        self.assertLess(lines.index(TestThirdSnapshot.KEPT_HEADING),
                        lines.index(self.HEADING))
        self.assertLess(lines.index(self.HEADING),
                        lines.index("## Where the project stands"))

    def test_its_chart_stands_in_the_tree(self):
        self.assertIn("security-tokens-split-2026-11-16.svg",
                      _read(STATISTICS))
        self.assertTrue(os.path.isfile(os.path.join(
            REPO, "assets", "security-tokens-split-2026-11-16.svg")))

    def test_every_row_s_two_parts_make_its_whole(self):
        rows = self._rows()
        self.assertEqual(10, len(rows))
        for date, where, total, log, rest in rows:
            self.assertEqual(total, log + rest, "%s at %s" % (date, where))
        self.assertEqual([r[0] for r in rows], sorted(r[0] for r in rows))
        # The log is absent before its first commit and never
        # shrinks after it; the whole grows from row to row.
        self.assertEqual([0, 0, 0, 0], [r[3] for r in rows[:4]])
        for before, after in zip(rows, rows[1:]):
            self.assertLessEqual(before[3], after[3])
            self.assertLess(before[2], after[2])

    def test_the_stated_shares_are_the_table_s_own(self):
        rows = {r[0]: r for r in self._rows()}
        text = _read(STATISTICS)
        last = rows["2026-11-16"]
        self.assertIn("%s tokens at\n  the last count: %.1f%% of the measure"
                      % (format(last[3], ","), 100.0 * last[3] / last[2]), text)
        a, b = rows["2026-11-04"], rows["2026-11-15"]
        self.assertIn("added %s tokens, and %s of them, %.1f%%,"
                      % (format(b[2] - a[2], ","), format(b[3] - a[3], ","),
                         100.0 * (b[3] - a[3]) / (b[2] - a[2])), text)
        self.assertIn("%s to %s," % (format(a[4], ","), format(b[4], ",")),
                      text.replace("\n  ", " "))


class TestRecordSlots(unittest.TestCase):
    """The record's own list answers to its facts, as the
    evergreen docs do: checked in place, and re-filled by the one
    write that rewrites the facts."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-record-slots-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for rel in (RF.STATISTICS_REL,) + tuple(RF.SLOT_FILES):
            dest = os.path.join(self.tmp, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(os.path.join(REPO, rel), dest)
        self.record = os.path.join(self.tmp, RF.STATISTICS_REL)
        self.facts = RF.parse_facts(_read(self.record))

    def _rewrite(self, old, new, count=1):
        text = _read(self.record)
        self.assertIn(old, text)
        with open(self.record, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new, count))

    def _slot(self, name):
        return "<!--hp-fig:%s-->%s<!--/hp-fig-->" % (
            name, RF.renderings(self.facts)[name])

    def test_the_list_carries_every_figure_it_states_in_a_slot(self):
        held = dict(RF.find_slots(_read(STATISTICS)))
        wanted = RF.renderings(RF.parse_facts(_read(STATISTICS)))
        for name in RF.RECORD_SLOTS:
            self.assertEqual(wanted[name], held.get(name), name)

    def test_renderings_carry_the_commit_count_and_the_display_figures(self):
        facts = dict(self.facts, commits=6100, display_commits=6000,
                     display_lines=1500000)
        made = RF.renderings(facts)
        self.assertEqual(("6,100", "6,000", "1,500,000"),
                         (made["commits"], made["display_commits"],
                          made["display_lines"]))

    def test_the_copy_checks_clean(self):
        self.assertEqual([], RF.check(self.tmp))

    def test_a_figure_gone_stale_in_its_slot_is_named(self):
        self._rewrite(self._slot("commits"),
                      "<!--hp-fig:commits-->5,874<!--/hp-fig-->")
        self.assertEqual(
            ["statistics.md: slot commits holds '5,874', the facts say %r"
             % RF.renderings(self.facts)["commits"]],
            RF.check(self.tmp))

    def test_a_figure_restated_by_hand_is_named(self):
        # The shape that stood in the record until 2026-11-16: the
        # figure written into the sentence, with no slot around it.
        self._rewrite(self._slot("lines_tracked"), "1,433,117")
        self.assertEqual(
            ["statistics.md: the record's own list carries no slot "
             "for lines_tracked"], RF.check(self.tmp))

    def test_a_slot_no_rendering_answers_is_named(self):
        self._rewrite(self._slot("tokens_exact"),
                      "<!--hp-fig:tokens_guessed-->26 and a bit<!--/hp-fig-->")
        self.assertEqual(
            ["statistics.md: the record's own list carries no slot "
             "for tokens_exact",
             "statistics.md: unknown figure slot 'tokens_guessed'"],
            RF.check(self.tmp))

    def test_a_fresh_measure_fills_the_record_s_own_slots(self):
        fresh = dict(self.facts, as_of="2026-12-01", commit="a" * 40,
                     tokens=27123456, lines_tracked=1512345, commits=6234,
                     display_commits=6000, display_lines=1500000)
        with mock.patch.object(RF, "measure_facts",
                               lambda root, previous: fresh):
            changed = RF.write(self.tmp)
        self.assertIn(RF.STATISTICS_REL, changed)
        text = _read(self.record)
        for name, value in (("tokens_exact", "27,123,456"),
                            ("tokens_millions", "27"),
                            ("lines_tracked", "1,512,345"),
                            ("display_lines", "1,500,000"),
                            ("commits", "6,234"),
                            ("display_commits", "6,000")):
            self.assertIn("<!--hp-fig:%s-->%s<!--/hp-fig-->" % (name, value),
                          text, name)
        self.assertNotIn(self._slot("tokens_exact"), text)
        self.assertNotIn(self._slot("commits"), text)
        self.assertIn("27 mil security tokens, 6,000 commits", text)
        self.assertIn("Dated 2026-12-01. Measured on main at commit\n" + "a" * 40,
                      text)
        # Dated history beside the slots is not the tool's to move.
        self.assertIn("down to 24,396,328", text)
        self.assertEqual([], RF.check(self.tmp))

    def test_a_write_refuses_a_slot_it_cannot_fill(self):
        self._rewrite(self._slot("tokens_exact"),
                      "<!--hp-fig:tokens_guessed-->26 and a bit<!--/hp-fig-->")
        before = _read(self.record)
        with mock.patch.object(RF, "measure_facts",
                               lambda root, previous: dict(self.facts)):
            with self.assertRaises(ValueError) as caught:
                RF.write(self.tmp)
        self.assertIn("statistics.md: unknown figure slot 'tokens_guessed'",
                      str(caught.exception))
        self.assertEqual(before, _read(self.record))


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
