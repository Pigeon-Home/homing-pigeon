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
import math
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


def _split_rows(lines):
    """The rows of a table of the split: (date, where, the whole,
    the run log, everything else)."""
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and re.match(r"^\d{4}-\d{2}-\d{2}$", cells[0]):
            rows.append((cells[0], cells[1]) + tuple(
                int(c.replace(",", "")) for c in cells[2:]))
    return rows


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


class TestGrowthCharts(unittest.TestCase):
    # The 3 growth charts first drew their 4 early points as open
    # circles, implied from line counts. At the owner's word every
    # point is a count and every circle is closed (2026-11-17): a
    # chart that goes back to an open circle, or loses a point its
    # snapshot's table carries, is named here.
    POINTS = {"2026-11-08": 6, "2026-11-15": 8, "2026-11-16": 8}

    def _chart(self, day):
        return _read(os.path.join(
            REPO, "assets", "security-tokens-growth-%s.svg" % day))

    def test_every_point_is_a_closed_circle(self):
        for day, points in sorted(self.POINTS.items()):
            svg = self._chart(day)
            closed = re.findall(
                r'<circle [^>]*r="6\.5" fill="#3987e5"[^>]*/>', svg)
            self.assertEqual(points, len(closed), day)
            # An open circle is the surface's colour ringed in the
            # series colour; none is drawn, in the plot or the key.
            self.assertEqual(
                [], re.findall(r'<circle [^>]*fill="#21050b" '
                               r'stroke="#3987e5"[^>]*/>', svg), day)
            self.assertNotIn("implied", svg, day)

    def test_the_tables_carry_counts_and_nothing_implied(self):
        lines = _read(STATISTICS).splitlines()
        start = lines.index("## The growth of the measure: a snapshot "
                            "as of 2026-11-08")
        end = lines.index(TestThirdSnapshot.KEPT_HEADING)
        rows = [line for line in lines[start:end]
                if re.match(r"^\| \d{4}-\d{2}-\d{2} \|", line)]
        self.assertEqual(6 + 8, len(rows))
        for row in rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            self.assertRegex(cells[3], r"^\d{1,3}(,\d{3})+$", row)
            self.assertTrue(cells[4].startswith("counted from"), row)

    def test_the_three_snapshots_and_the_fourth_carry_one_series(self):
        lines = _read(STATISTICS).splitlines()

        def counts(heading, until):
            start, end = lines.index(heading), lines.index(until)
            found = {}
            for line in lines[start:end]:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) == 5 and re.match(r"^\d{4}-\d{2}-\d{2}$", cells[0]):
                    found[cells[0]] = int(cells[3 if "counted" in cells[4]
                                                else 2].replace(",", ""))
            return found
        second = counts("## The growth of the measure, continued: a second "
                        "snapshot as of 2026-11-15",
                        TestThirdSnapshot.KEPT_HEADING)
        fourth = counts(TestFourthSnapshot.HEADING,
                        TestFifthSnapshot.HEADING)
        self.assertEqual(8, len(second))
        for day, tokens in second.items():
            self.assertEqual(fourth[day], tokens, day)


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
        end = lines.index(TestFifthSnapshot.HEADING)
        return _split_rows(lines[start:end])

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


class TestFifthSnapshot(unittest.TestCase):
    # The fifth snapshot sets the counts of 4 more days against
    # the third snapshot's 2 lines, splits each in 2 as the fourth
    # does, and shows the limit a rule gives each part. Its table
    # is arithmetic a reader can redo, its stated shares are the
    # table's own, and each of its 3 charts carries the figures
    # the table gives. Its charts were drawn again on 2026-11-20:
    # no limit on them is named first. Each is read off the
    # counts by the rule of the curve's page, and
    # test_v4_the_curve holds the record's 3 limits and the
    # charts' lines to the series by day.
    HEADING = ("## The measure against its lines: a fifth snapshot "
               "as of 2026-11-19")
    CHARTS = ("growth", "split", "two-limits")

    def _rows(self):
        lines = _read(STATISTICS).splitlines()
        start = lines.index(self.HEADING)
        end = lines.index("## Where the project stands")
        return _split_rows(lines[start:end])

    def _chart(self, name):
        return _read(os.path.join(
            REPO, "assets", "security-tokens-%s-2026-11-19.svg" % name))

    def test_the_snapshot_stands_once_between_the_fourth_and_the_close(self):
        lines = _read(STATISTICS).splitlines()
        self.assertEqual(1, lines.count(self.HEADING))
        self.assertLess(lines.index(TestFourthSnapshot.HEADING),
                        lines.index(self.HEADING))
        self.assertLess(lines.index(self.HEADING),
                        lines.index("## Where the project stands"))

    def test_its_charts_stand_in_the_tree_and_the_readme_shows_the_closing(
            self):
        text = _read(STATISTICS)
        for name in self.CHARTS:
            asset = "security-tokens-%s-2026-11-19.svg" % name
            self.assertIn(asset, text)
            self.assertTrue(os.path.isfile(
                os.path.join(REPO, "assets", asset)), asset)
        readme = _read(os.path.join(REPO, "README.md"))
        # At the owner's word of 2026-11-20 the front page
        # carries the closing chart at the foot of the
        # statistics record (the 2 lines that close, the gap
        # going to 0) in place of this snapshot's split chart.
        self.assertIn(
            "assets/security-tokens-2-lines-that-close-2026-11-20.svg",
            readme)
        self.assertNotIn("security-tokens-split-2026-11-19.svg", readme)
        self.assertNotIn("security-tokens-split-2026-11-16.svg", readme)

    def test_every_row_s_two_parts_make_its_whole(self):
        rows = self._rows()
        self.assertEqual(["2026-11-16", "2026-11-17", "2026-11-18",
                          "2026-11-19"], [r[0] for r in rows])
        for date, where, total, log, rest in rows:
            self.assertEqual(total, log + rest, "%s at %s" % (date, where))
            self.assertRegex(where, r"^commit [0-9a-f]{10}$")
        for before, after in zip(rows, rows[1:]):
            self.assertLessEqual(before[3], after[3])
            self.assertLess(before[2], after[2])
        # The fourth snapshot's last 2 rows carry the log at
        # 12,240,873, and the first row here still does.
        self.assertEqual(12240873, rows[0][3])

    def test_the_stated_figures_are_the_table_s_own(self):
        rows = {r[0]: r for r in self._rows()}
        text = _read(STATISTICS)
        last = rows["2026-11-19"]
        self.assertIn("The run log holds %s tokens at the last count:\n"
                      "  %.1f%% of the measure."
                      % (format(last[3], ","), 100.0 * last[3] / last[2]), text)
        # Since 2026-11-17 the log is the larger part, and not before.
        self.assertGreater(rows["2026-11-17"][3], rows["2026-11-17"][4])
        self.assertLess(rows["2026-11-16"][3], rows["2026-11-16"][4])
        # Against the fourth snapshot's count of 2026-11-15.
        lines = text.splitlines()
        fourth = {r[0]: r for r in _split_rows(lines[
            lines.index(TestFourthSnapshot.HEADING):
            lines.index(self.HEADING)])}
        was = fourth["2026-11-15"]
        added, log, rest = (last[2] - was[2], last[3] - was[3],
                            last[4] - was[4])
        self.assertIn("added %s tokens, and %s of them, %.1f%%,"
                      % (format(added, ","), format(log, ","),
                         100.0 * log / added), text)
        self.assertIn("Everything else added %s over the same 4 days,\n"
                      "  about %.2f million a day."
                      % (format(rest, ","), rest / 4e6), text)
        # The 2 lines of the third snapshot, on 2026-11-19: 35
        # days from the first count, 4 from the count of
        # 2026-11-15.
        first = fourth["2026-10-15"][2]
        straight = first + (was[2] - first) / 31.0 * 35
        curve = 38e6 - (38e6 - was[2]) * math.exp(-0.055 * 4)
        self.assertIn("| Straight trend | %.1fM | %.1fM | %.1fM |"
                      % (straight / 1e6, last[2] / 1e6,
                         (last[2] - straight) / 1e6), text)
        self.assertIn("| Asymptotic curve | %.1fM | %.1fM | %.1fM |"
                      % (curve / 1e6, last[2] / 1e6,
                         (last[2] - curve) / 1e6), text)
        # The last 4 days' pace, and the day it passes the third
        # snapshot's 38 million: the 6th day after 2026-11-19.
        pace = (last[2] - was[2]) / 4.0
        self.assertEqual("1.21", "%.2f" % (pace / 1e6))
        self.assertIn("The last 4 days added 1.21 million a day, and at\n"
                      "that pace the series passes the third snapshot's 38\n"
                      "million on 2026-11-25.", text)
        self.assertEqual(6, math.ceil((38e6 - last[2]) / pace))

    def test_each_chart_carries_the_table_s_figures(self):
        last = self._rows()[-1]
        split = self._chart("split")
        for stated in ("%.1fM in all" % (last[2] / 1e6),
                       ">%.1fM<" % (last[3] / 1e6),
                       ">%.1fM<" % (last[4] / 1e6),
                       "%d%% of the count" % round(100.0 * last[3] / last[2])):
            self.assertIn(stated, split, stated)
        limits = self._limits()
        growth = self._chart("growth")
        for stated in (">%.1fM<" % (last[2] / 1e6),
                       ">%s<" % limits["The whole"][1],
                       "The limit that follows: %s" % limits["The whole"][1],
                       "by 2 December"):
            self.assertIn(stated, growth, stated)
        limits = self._chart("two-limits")
        for stated in ("the run log: %.1fM," % (last[3] / 1e6),
                       "Everything else: %.1fM." % (last[4] / 1e6)):
            self.assertIn(stated, limits, stated)
        # 1 surface and 1 blue for the counts, as the charts
        # before these.
        for name in self.CHARTS:
            self.assertIn('stroke="#3987e5"', self._chart(name), name)

    def _limits(self):
        # The table of the 3 limits: part -> (where it stands,
        # the limit that follows, as the record writes it).
        lines = _read(STATISTICS).splitlines()
        rows = {}
        for line in lines[lines.index(self.HEADING):
                          lines.index("## Where the project stands")]:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 3 and re.match(r"^\d+\.\dM$", cells[2]):
                rows[cells[0]] = (int(cells[1].replace(",", "")), cells[2])
        return rows

    def test_the_3_limits_stand_on_the_table_s_last_row(self):
        # No limit of this view is named first. The record gives
        # 1 to each part of the last count, and the whole's is
        # the sum of the other 2.
        last = self._rows()[-1]
        limits = self._limits()
        log = "The run log, if it keeps the rule from 2026-11-19"
        self.assertEqual({"Everything else", log, "The whole"}, set(limits))
        self.assertEqual((last[4], last[3], last[2]),
                         (limits["Everything else"][0], limits[log][0],
                          limits["The whole"][0]))
        rest, logs, whole = (float(limits[part][1][:-1])
                             for part in ("Everything else", log,
                                          "The whole"))
        self.assertAlmostEqual(whole, rest + logs, places=6)
        for part in limits:
            self.assertGreater(float(limits[part][1][:-1]) * 1e6,
                               limits[part][0], part)
        # Each chart that draws the 2 parts carries their limits.
        for name in ("growth", "two-limits"):
            for part in ("Everything else", log):
                self.assertIn(">%s<" % limits[part][1], self._chart(name),
                              name)
        # The third snapshot's 38 million is on none of the 3.
        for name in self.CHARTS:
            chart = self._chart(name)
            for first in ("38M", "38 million"):
                self.assertFalse(first in chart,
                                 "%s carries %s" % (name, first))

    def test_the_pace_passes_the_whole_s_limit_by_2_december(self):
        # The dotted line of the growth chart: the last 4 days'
        # pace from the last count. It passes the limit of the
        # whole on the 13th day after 2026-11-19.
        rows = {r[0]: r for r in self._rows()}
        lines = _read(STATISTICS).splitlines()
        fourth = {r[0]: r for r in _split_rows(lines[
            lines.index(TestFourthSnapshot.HEADING):
            lines.index(self.HEADING)])}
        last = rows["2026-11-19"][2]
        pace = (last - fourth["2026-11-15"][2]) / 4.0
        whole = self._limits()["The whole"][1]
        self.assertEqual(13, math.ceil((float(whole[:-1]) * 1e6 - last)
                                       / pace))
        self.assertIn("the series passes %s million by 2026-12-02"
                      % whole[:-1], " ".join(lines))

    CLOSING_CHART = "security-tokens-2-lines-that-close-2026-11-20.svg"

    def test_the_closing_chart_of_20_november_stands_in_the_tree(self):
        # The owner's drawing of 2026-11-20 closes this view:
        # a ceiling for the run log at 21.0 million, closing
        # by 0.61 a week onto the line of everything else at
        # 17.6 million, the gap between the 2 lines closing
        # to 0, and the whole at 35.2 million where they meet.
        # The chart was drawn with numbers by the research
        # zipped in the archive, and it carries the drawing's
        # own figures.
        text = _read(STATISTICS)
        self.assertIn(self.CLOSING_CHART, text)
        path = os.path.join(REPO, "assets", self.CLOSING_CHART)
        self.assertTrue(os.path.isfile(path), self.CLOSING_CHART)
        chart = _read(path)
        for stated in ("21.0M: your red line",
                       "17.6M: your yellow line",
                       "3.39M", "35.2M"):
            self.assertIn(stated, chart, stated)
        lines = text.splitlines()
        section = "\n".join(lines[lines.index(self.HEADING):
                                  lines.index("## Where the project stands")])
        self.assertIn("The gap between the 2 lines is 3,393,230", section)
        self.assertIn("the whole tree at 35.2 million", section)


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

    def test_a_figure_the_page_carries_twice_is_still_named_in_the_list(self):
        # The closing section carries a commits slot of its own.
        # With the list's commits figure restated by hand (the
        # 5,874 that stood there) the name is still on the page,
        # and a presence test over the whole page saw nothing
        # (Q201). The list is read as the list.
        self.assertEqual(2, _read(self.record).count(self._slot("commits")))
        self._rewrite(self._slot("commits"), "5,874")
        self.assertEqual(1, _read(self.record).count(self._slot("commits")))
        self.assertEqual(
            ["statistics.md: the record's own list carries no slot "
             "for commits"], RF.check(self.tmp))

    def test_a_slot_outside_the_list_does_not_stand_in_for_it(self):
        # Every figure the list states, moved out of the list to
        # the foot of the page, still in its slot and still equal
        # to the facts: the page holds all 6 names and the list
        # holds none of them.
        text = _read(self.record)
        moved = []
        for name in RF.RECORD_SLOTS:
            slot = self._slot(name)
            self.assertIn(slot, RF.record_list(text), name)
            moved.append(slot)
        start = text.index(RF.RECORD_LIST_HEADING)
        end = text.index("\n## ", start + 1)
        listed = text[start:end]
        for slot in moved:
            listed = listed.replace(slot, "a figure")
        with open(self.record, "w", encoding="utf-8") as fh:
            fh.write(text[:start] + listed + text[end:]
                     + "\n" + " ".join(moved) + "\n")
        self.assertEqual(
            ["statistics.md: the record's own list carries no slot "
             "for %s" % name for name in RF.RECORD_SLOTS],
            RF.check(self.tmp))

    def test_a_record_without_its_list_is_named(self):
        self._rewrite(RF.RECORD_LIST_HEADING, "## What the figures rest on")
        problems = RF.check(self.tmp)
        self.assertEqual(
            "statistics.md: the record's own list is not found under "
            "its heading (%s)" % RF.RECORD_LIST_HEADING, problems[0])

    def test_the_list_is_the_section_under_its_heading_and_no_more(self):
        text = _read(STATISTICS)
        listed = RF.record_list(text)
        self.assertTrue(listed.startswith(RF.RECORD_LIST_HEADING))
        self.assertIn("- Tokens: ", listed)
        self.assertIn("- Non-latent: ", listed)
        self.assertNotIn("## The facts, machine-readable", listed)
        self.assertNotIn("```json", listed)
        self.assertEqual("", RF.record_list("# a record with no list\n"))

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


class TestClosingSection(unittest.TestCase):
    # The closing section names where each release line stands in
    # the record: no slot holds that prose, and it stood 2
    # releases short of the 3.16 line's end until the changelog
    # was read beside it (Q201). The changelog is the release
    # record, so the sentence answers to it here.
    CHANGELOG = os.path.join(REPO, "docs", "infrastructure-documents",
                             "changelog.md")

    def _sections(self):
        sections, current = {}, None
        for line in _read(self.CHANGELOG).splitlines():
            head = re.match(r"^## (\d+\.\d+\.\d+\.\d+) - ", line)
            if head:
                current = head.group(1)
                sections[current] = []
            elif current:
                sections[current].append(line)
        return sections

    @staticmethod
    def _key(version):
        return tuple(int(part) for part in version.split("."))

    @staticmethod
    def _record_in_one_line():
        # The sentence is read whatever its wrapping.
        return " ".join(_read(STATISTICS).split())

    def test_the_3_16_line_ends_where_the_changelog_ends_it(self):
        line = [v for v in self._sections() if v.startswith("3.16.")]
        last = max(line, key=self._key)
        self.assertIn("The 3.16 line ran to %s," % last,
                      self._record_in_one_line())

    def test_the_3_17_line_s_first_published_release_is_the_changelog_s(self):
        sections = self._sections()
        line = sorted((v for v in sections if v.startswith("3.17.")),
                      key=self._key)
        # A cut that never published says so in the entry of the
        # cut that carried its notes; the first release of the
        # line no later entry says that of is its first published.
        unpublished = set()
        for version in line:
            for text in sections[version]:
                found = re.search(
                    r"((?:\d+\.\d+\.\d+\.\d+(?:,| and)? ?)+)"
                    r"(?:, which)? never published", text)
                if found:
                    unpublished.update(
                        re.findall(r"\d+\.\d+\.\d+\.\d+", found.group(1)))
        first = [v for v in line if v not in unpublished][0]
        self.assertEqual("3.17.26.2", first)
        self.assertIn("the 3.17 line opened on 2026-11-16 with %s as its "
                      "first published release" % first,
                      self._record_in_one_line())


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
