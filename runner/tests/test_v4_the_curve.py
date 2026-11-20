#!/usr/bin/env python3
"""The curve: a limit at 38 million.

docs/infrastructure-documents/proofs/v4-the-curve.md proves that
the count of security tokens has an upper limit under 1 rule:
each day the count may grow by at most a fixed share of what is
left to the limit. Then something is always left, the count
settles, and with the allowance used it settles at the limit.
It is Newton's law of cooling, with the count for the
temperature and the limit for the room.

This module walks the 3 steps of the proof with whole tokens,
holds the page's numbers, and holds the test for a limit against
the counts the page names.

It holds the page's second half as well: the test for a limit is
of the second degree, each of the 2 parts of the count has a
limit of its own or has none, a rule on the steps gives a limit
that nobody names first, a curve of the second degree has no
flat line, and counts alone cannot prove a limit.

    python3 runner/tests/test_v4_the_curve.py series

counts each day's tree again, from a complete clone.
"""
import datetime
import math
import os
import random
import subprocess
import sys
import unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-curve.md")
LIMIT = 38000000
LAST_COUNT = 31273283
# The record's curve closes its gap by e^(-0.055) a day.
RATE = 0.055
SHARE = 1 - math.exp(-RATE)

# The counts of the tree the page names: the record's, in
# statistics.md, and the last count, on main on 2026-11-19.
COUNTS = ((4, 17948976), (8, 20251953), (13, 25004718),
          (15, 26451259), (19, 31273283))
# The fuzz run log's finds, summed to each day, counted on
# main on 2026-11-19.
FINDS = {"30 October": 21840, "8 November": 23214, "17 November": 23916,
         "4 November": 22834, "11 November": 23478, "18 November": 23988}

# The 2 parts of the count, 15 days apart: 20 October and
# 4 November in statistics.md, and the count on main on
# 2026-11-19. The run log is 1 file; everything else is the rest.
ELSE = (1615732, 11908288, 14954555)
LOG = (0, 6040688, 16318728)
WHOLE = tuple(rest + log for rest, log in zip(ELSE, LOG))
RUN_LOG = "runner/tests/de_dust/runs.jsonl"
# Each day's tree on main, 15 October to 19 November 2026: the
# last landing of each Pacific day, counted by the estimator's
# rule. `series` below counts them again.
FIRST_DAY = datetime.date(2026, 10, 15)
ELSE_BY_DAY = (
    447477, 565698, 761990, 1299140, 1578886, 1622619, 1741130, 2148426,
    2744612, 3468563, 5677866, 6543136, 7333093, 7522578, 7939344, 8187780,
    9954699, 10767448, 11758196, 11852849, 11790139, 11925734, 12387941,
    12453797, 12693927, 12769459, 12946902, 13503300, 14489248, 13898011,
    14180322, 14519789, 14573363, 14623036, 14859579, 14954760)
LOG_BY_DAY = (
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 378467, 697788, 1361415, 3267883,
    4551869, 5456524, 5691358, 5863146, 6040688, 6040688, 6040688, 6040688,
    7618031, 7618031, 7618031, 7618031, 10551621, 11889816, 12240873,
    12240873, 12240873, 15265975, 15913904, 16318728)
WHOLE_BY_DAY = tuple(rest + log for rest, log
                     in zip(ELSE_BY_DAY, LOG_BY_DAY))


def allowance(left, numerator, denominator):
    """What a day may add, in whole tokens: the share of what
    is left, rounded down."""
    return left * numerator // denominator


def limit_of(first, second, third):
    """The test for a limit, on 3 counts the same number of
    days apart: (the factor the second step is of the first,
    the limit the 3 counts point at). The limit is None when
    the steps do not shrink."""
    factor = (third - second) / (second - first)
    if factor >= 1:
        return factor, None
    return factor, third + (third - second) * factor / (1 - factor)


def second_degree(first, second, third):
    """The same test, written with differences: the last count,
    plus the last step squared, over the amount by which the
    step got shorter. None when the step did not get shorter."""
    step = third - second
    shorter = (second - first) - step
    if shorter <= 0:
        return None
    return third + Fraction(step * step, shorter)


def day(month, number):
    """The place of a day in the series by day."""
    return (datetime.date(2026, month, number) - FIRST_DAY).days


def reading(series, apart, end):
    """The limit that 3 counts `apart` days apart point at, the
    last of them on day `end`, in millions; None when they
    point at none."""
    first, second, third = (series[end - 2 * apart], series[end - apart],
                            series[end])
    if second <= first or third < second:
        return None
    limit = limit_of(first, second, third)[1]
    return None if limit is None else limit / 1e6


def parabola(first, second, third, apart=15):
    """The curve of the second degree through 3 counts `apart`
    days apart: (a, b) of first + b x days + a x days squared."""
    a = Fraction(first - 2 * second + third, 2 * apart * apart)
    b = Fraction(second - first, apart) - apart * a
    return a, b


def series(clone, ref="origin/main"):
    """Count each day's tree again: for each Pacific day, the
    last landing on the first-parent line of `ref` that day or
    before, counted from its blobs by the estimator's rule, with
    no checkout. Yields (day, commit, everything else, the run
    log)."""
    from runner.ops import version4

    def git(*args, **more):
        return subprocess.run(
            ("git", "-C", clone) + args, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True, **more).stdout

    counted = {}

    def tokens(sha, name):
        if sha not in counted:
            data = b""
            extension = os.path.splitext(name)[1].lower()
            if extension not in version4._BINARY_EXTENSIONS:
                data = git("cat-file", "blob", sha)
            if b"\0" in data[:version4._SNIFF_BYTES]:
                data = b""
            counted[sha] = version4.count_text_tokens(
                data.decode("utf-8", "replace"))
        return counted[sha]

    pacific = dict(os.environ, TZ="America/Los_Angeles")
    for place in range(len(ELSE_BY_DAY)):
        today = FIRST_DAY + datetime.timedelta(days=place)
        commit = git(
            "rev-list", "-1", "--first-parent",
            "--before=%s 23:59:59" % today.isoformat(), ref,
            env=pacific).decode("ascii").strip()
        whole = log = 0
        listing = git("ls-tree", "-r", "-z", commit).decode(
            "utf-8", "surrogateescape")
        for entry in listing.split("\0"):
            if not entry:
                continue
            meta, name = entry.split("\t", 1)
            mode, kind, sha = meta.split()
            if kind != "blob" or mode == "120000":
                continue
            count = tokens(sha, name)
            whole += count
            if name == RUN_LOG:
                log = count
        yield today, commit[:10], whole - log, log


class TheLimit(unittest.TestCase):
    """The 3 steps of the proof, walked."""

    def test_step_1_something_is_always_left(self):
        # A day's growth is drawn at random, from 0 to all the
        # rule allows. 6 shares, 5,000 days each, whole tokens.
        draw = random.Random(38)
        for numerator, denominator in ((1, 2), (1, 10), (535, 10000),
                                       (1, 100), (9, 10), (999, 1000)):
            count = LAST_COUNT
            for _day in range(5000):
                left = LIMIT - count
                self.assertGreater(left, 0)
                grown = draw.randint(
                    0, allowance(left, numerator, denominator))
                self.assertLessEqual(grown * denominator, left * numerator)
                count += grown
            self.assertLess(count, LIMIT)

    def test_step_2_the_count_settles_under_the_bar(self):
        # With every allowance used, each day's count is not
        # under the day before's and is under the limit, and
        # a day comes after which it does not move.
        count, days = LAST_COUNT, 0
        while True:
            grown = allowance(LIMIT - count, 535, 10000)
            if grown == 0:
                break
            self.assertLess(count + grown, LIMIT)
            count += grown
            days += 1
        # Fewer than 19 tokens are left, so the rule allows 0.
        self.assertEqual(18, LIMIT - count)
        self.assertEqual(0, allowance(18, 535, 10000))
        self.assertEqual(1, allowance(19, 535, 10000))
        self.assertTrue(240 <= days <= 250, days)

    def test_step_3_what_is_left_goes_to_0(self):
        # What is left is multiplied by the same factor each
        # day, so after n days it is that factor to the power
        # n, times what was left at the start.
        left = start = LIMIT - LAST_COUNT
        for day in range(1, 401):
            left -= SHARE * left
            self.assertAlmostEqual(
                start * (1 - SHARE) ** day, left, delta=1e-6 * start)
        self.assertLess(left, 1)
        # A share of a half: of 8 left, a day takes 4, then 2,
        # then 1, then a half.
        left, taken = 8.0, []
        for _day in range(4):
            taken.append(left / 2)
            left -= left / 2
        self.assertEqual([4, 2, 1, 0.5], taken)
        self.assertGreater(left, 0)

    def test_day_by_day_it_is_the_law_of_cooling(self):
        # count = limit - (left at the start) x e^(-k x days),
        # sampled at the end of each day.
        start = LIMIT - LAST_COUNT
        count = float(LAST_COUNT)
        for day in range(1, 91):
            count += SHARE * (LIMIT - count)
            self.assertAlmostEqual(
                LIMIT - start * math.exp(-RATE * day), count, delta=1e-3)
        self.assertAlmostEqual(0.0535, SHARE, places=4)
        self.assertAlmostEqual(12.6, math.log(2) / RATE, places=1)


class TheNumbers(unittest.TestCase):
    """The page's table, and the test for a limit."""

    def table(self):
        rows, left = {}, float(LIMIT - LAST_COUNT)
        for day in range(1, 61):
            add = SHARE * left
            rows[day] = (round(left), round(add), round(LIMIT - left + add))
            left -= add
        return rows

    def test_the_table_from_the_last_count(self):
        rows = self.table()
        self.assertEqual((6726717, 359979, 31633262), rows[1])
        self.assertEqual((6366738, 340715, 31973977), rows[2])
        self.assertEqual((4835996, 258798, 33422801), rows[7])
        self.assertEqual((3290657, 176099, 34885442), rows[14])
        self.assertEqual((1364908, 73043, 36708135), rows[30])
        self.assertEqual((262131, 14028, 37751897), rows[60])
        # 1 million is left after 35 days.
        self.assertAlmostEqual(
            34.7, math.log((LIMIT - LAST_COUNT) / 1e6) / RATE, places=1)

    def test_the_test_finds_a_limit_that_is_there(self):
        # On a curve made by the rule, 3 counts any same number
        # of days apart give the limit back.
        start = LIMIT - LAST_COUNT

        def on_the_curve(day):
            return LIMIT - start * math.exp(-RATE * day)

        for apart in (1, 5, 9, 30):
            factor, limit = limit_of(
                on_the_curve(0), on_the_curve(apart),
                on_the_curve(2 * apart))
            self.assertAlmostEqual(math.exp(-RATE * apart), factor, places=9)
            self.assertAlmostEqual(LIMIT, limit, delta=1e-3)
        # A straight line has no limit: its steps do not shrink.
        self.assertEqual((1.0, None), limit_of(10, 20, 30))

    def test_the_count_does_not_level_off_yet(self):
        paces = [(later - earlier) / (day - before) / 1e6
                 for (before, earlier), (day, later)
                 in zip(COUNTS, COUNTS[1:])]
        self.assertEqual([0.58, 0.95, 0.72, 1.21],
                         [round(pace, 2) for pace in paces])
        self.assertEqual(
            [2302977, 4752765, 1446541, 4822024],
            [later - earlier for (_b, earlier), (_d, later)
             in zip(COUNTS, COUNTS[1:])])
        # The last step is the longest of the 4, and more than
        # 3 times the next day's allowance.
        self.assertEqual(max(paces), paces[-1])
        self.assertGreater(paces[-1] * 1e6, 3 * 359979)

    def test_what_the_campaign_finds_does_level_off(self):
        factor, limit = limit_of(
            FINDS["30 October"], FINDS["8 November"], FINDS["17 November"])
        self.assertEqual((0.51, 24649), (round(factor, 2), round(limit)))
        factor, limit = limit_of(
            FINDS["4 November"], FINDS["11 November"], FINDS["18 November"])
        self.assertEqual((0.79, 25929), (round(factor, 2), round(limit)))
        # The log's tail, at its own average for a find.
        a_find = 16318670 / 24804
        self.assertEqual(658, round(a_find))
        self.assertEqual(
            ("0.4", "1.3"),
            ("%.1f" % (a_find * (24649 - 23988) / 1e6),
             "%.1f" % (a_find * (25929 - 23988) / 1e6)))

    def test_step_38_of_the_series_is_the_first_past_38_million(self):
        series = [0, 1]
        while series[-1] <= LIMIT:
            series.append(series[-1] + series[-2])
        self.assertEqual((38, 39088169, 24157817),
                         (len(series) - 1, series[38], series[37]))
        self.assertAlmostEqual(1.618, series[38] / series[37], places=3)


class TheSecondDegree(unittest.TestCase):
    """The test for a limit reads how the line turns."""

    def test_the_test_for_a_limit_is_of_the_second_degree(self):
        # The 2 forms are the same number, to the token, on the
        # page's rows and on 1,000 draws.
        rows = [ELSE, WHOLE,
                (FINDS["30 October"], FINDS["8 November"],
                 FINDS["17 November"]),
                (FINDS["4 November"], FINDS["11 November"],
                 FINDS["18 November"])]
        draw = random.Random(1926)
        while len(rows) < 1004:
            first = draw.randint(0, 10 ** 7)
            step = draw.randint(2, 10 ** 7)
            rows.append((first, first + step,
                         first + step + draw.randint(1, step - 1)))
        for first, second, third in rows:
            factor = Fraction(third - second, second - first)
            by_the_factor = third + (third - second) * factor / (1 - factor)
            self.assertEqual(by_the_factor,
                             second_degree(first, second, third))
        self.assertEqual(16235175, round(second_degree(*ELSE)))
        self.assertEqual((3046267, 7246289),
                         (ELSE[2] - ELSE[1],
                          (ELSE[1] - ELSE[0]) - (ELSE[2] - ELSE[1])))
        self.assertEqual(90276565, round(second_degree(*WHOLE)))
        # The run log's step got longer: no limit.
        self.assertIsNone(second_degree(*LOG))
        self.assertEqual(4237352, (LOG[2] - LOG[1]) - (LOG[1] - LOG[0]))

    def test_2_limits_and_the_third_follows(self):
        self.assertEqual((1615732, 17948976, 31273283), WHOLE)
        factor, limit = limit_of(*ELSE)
        self.assertEqual(("0.30", "16.2"),
                         ("%.2f" % factor, "%.1f" % (limit / 1e6)))
        factor, limit = limit_of(*LOG)
        self.assertEqual(("1.70", None), ("%.2f" % factor, limit))
        factor, limit = limit_of(*WHOLE)
        self.assertEqual(("0.82", "90.3"),
                         ("%.2f" % factor, "%.1f" % (limit / 1e6)))
        # What is left for the log under 38 million, if everything
        # else stops between 16 and 18 million.
        self.assertEqual((22, 20), (38 - 16, 38 - 18))
        self.assertEqual("16.3", "%.1f" % (LOG[2] / 1e6))

    def test_the_series_by_day(self):
        self.assertEqual((36, 36), (len(ELSE_BY_DAY), len(LOG_BY_DAY)))
        self.assertEqual(35, day(11, 19))
        # The record's own counts: the first release, and the 2
        # rows of the record that name a commit agree to the
        # token when `series` is run on them.
        self.assertEqual(447477, WHOLE_BY_DAY[0])
        self.assertEqual((6040688, 12240873, 16318728),
                         (LOG_BY_DAY[day(11, 4)], LOG_BY_DAY[day(11, 15)],
                          LOG_BY_DAY[day(11, 19)]))
        self.assertEqual(31273488, WHOLE_BY_DAY[-1])
        # Everything else fell on 2 days: a tree is not only
        # added to.
        fell = [place for place in range(1, 36)
                if ELSE_BY_DAY[place] < ELSE_BY_DAY[place - 1]]
        self.assertEqual([day(11, 4), day(11, 13)], fell)

    def test_at_7_days_the_2_parts_keep_different_laws(self):
        end = day(11, 19)
        self.assertEqual("15.06", "%.2f" % reading(ELSE_BY_DAY, 7, end))
        self.assertIsNone(reading(LOG_BY_DAY, 7, end))
        self.assertEqual("77.4", "%.1f" % reading(WHOLE_BY_DAY, 7, end))

    def test_a_reading_is_believed_while_it_stands_still(self):
        last_8 = range(day(11, 12), day(11, 19) + 1)
        # Everything else, 10 days apart: within 2.4 million on
        # each of the last 8 days.
        at_10 = [reading(ELSE_BY_DAY, 10, end) for end in last_8]
        self.assertEqual(
            ["15.68", "14.56", "15.72", "16.93", "16.24", "16.33",
             "16.67", "16.95"], ["%.2f" % limit for limit in at_10])
        self.assertLess(max(at_10) - min(at_10), 2.4)
        # 7 days apart it does not stand still: none on 2 of the
        # 8 days, and from 14.75 to 47.65 on the others.
        at_7 = [reading(ELSE_BY_DAY, 7, end) for end in last_8]
        self.assertEqual(2, at_7.count(None))
        self.assertEqual(
            ("14.75", "47.65"),
            ("%.2f" % min(x for x in at_7 if x),
             "%.2f" % max(x for x in at_7 if x)))
        # The run log: none at 15 days on any of the last 6 days,
        # none at 10 days on the last 7, none at 7 on the last 7.
        self.assertEqual([None] * 6, [reading(LOG_BY_DAY, 15, end)
                                      for end in range(30, 36)])
        self.assertEqual([None] * 7, [reading(LOG_BY_DAY, 10, end)
                                      for end in range(29, 36)])
        self.assertEqual([None] * 7, [reading(LOG_BY_DAY, 7, end)
                                      for end in range(29, 36)])
        # The whole, 15 days apart: higher each day.
        whole = [reading(WHOLE_BY_DAY, 15, end) for end in range(32, 36)]
        self.assertEqual(["49.84", "71.59", "86.14", "96.62"],
                         ["%.2f" % limit for limit in whole])

    def test_a_curve_of_the_second_degree_has_no_flat_line(self):
        # Through everything else's 3 counts it peaks on
        # 18 November and is at 0 on 18 December.
        a, b = parabola(*ELSE)
        self.assertLess(a, 0)
        peak = -b / (2 * a)
        self.assertEqual("28.8", "%.1f" % peak)
        top = ELSE[0] + b * peak + a * peak * peak
        self.assertEqual(14977518, round(top))
        gone = (-float(b) - math.sqrt(float(b * b - 4 * a * ELSE[0]))) \
            / (2 * float(a))
        self.assertEqual("59.3", "%.1f" % gone)
        start = datetime.date(2026, 10, 20)
        self.assertEqual(
            (datetime.date(2026, 11, 17), datetime.date(2026, 12, 18)),
            (start + datetime.timedelta(days=28),
             start + datetime.timedelta(days=59)))
        # Through the run log's 3 counts it rises without end.
        a, b = parabola(*LOG)
        self.assertGreater(a, 0)
        self.assertEqual("49.6", "%.1f" % (
            float(LOG[0] + b * 60 + a * 3600) / 1e6))

    def test_counts_cannot_prove_a_limit(self):
        # 2 curves through the same 3 counts of everything else.
        # Neither ever falls. The first has a limit. The second
        # passes every bar.
        first, second, third = ELSE
        factor, limit = limit_of(first, second, third)

        def with_a_limit(days):
            return limit - (limit - first) * factor ** (days / 15)

        def with_none(days):
            return with_a_limit(days) + days * (days - 15) * (days - 30)

        def walk_of(curve):
            return [curve(days) for days in range(0, 3651)]

        for curve in (with_a_limit, with_none):
            for days, count in ((0, first), (15, second), (30, third)):
                self.assertAlmostEqual(count, curve(days), delta=1e-3)
            walk = walk_of(curve)
            self.assertTrue(all(later >= earlier for earlier, later
                                in zip(walk, walk[1:])))
        self.assertLess(with_a_limit(300), limit)
        self.assertLessEqual(max(walk_of(with_a_limit)), limit)
        self.assertGreater(with_none(365), LIMIT)
        self.assertGreater(with_none(3650), 1000 * LIMIT)
        # And the run log's 3 counts, which point at no limit,
        # lie on a curve that has 1: a log that is written no
        # more after the third count.
        self.assertIsNone(limit_of(*LOG)[1])
        stopped = [LOG[0], LOG[1], LOG[2]] + [LOG[2]] * 100
        self.assertEqual(LOG[2], max(stopped))


class TheRuleOnTheSteps(unittest.TestCase):
    """Each day's allowance is at most a fixed share of the
    allowance of the day before. Then the limit is a result."""

    def test_all_the_days_to_come_add_less_than_a_fixed_amount(self):
        # The day before the first was allowed S. Day n is
        # allowed S x r^n. What a day adds is drawn at random
        # under its allowance, in whole tokens.
        draw = random.Random(38)
        for numerator, denominator in ((1, 2), (61, 100), (848, 1000),
                                       (9465, 10000)):
            share = Fraction(numerator, denominator)
            before = 1205506
            bound = before * share / (1 - share)
            allowed, added, total = Fraction(before), 0, 0
            for _day in range(1, 2001):
                allowed *= share
                total += allowed
                added += draw.randint(0, int(allowed))
                self.assertLess(added, bound)
                self.assertLess(total, bound)
            # With every allowance used the sum comes as near
            # the bound as anyone asks.
            self.assertLess(bound - total, 1)

    def test_a_day_of_nothing_closes_no_door(self):
        # The allowance falls by the share whatever is added. A
        # rule on what was added would allow 0 for ever after a
        # day of 0.
        share = Fraction(61, 100)
        allowed = [1000 * share ** n for n in range(1, 6)]
        self.assertTrue(all(amount > 0 for amount in allowed))
        added = [610, 0]
        self.assertEqual(0, share * added[-1])

    def test_for_38_million_from_this_week_s_pace(self):
        pace = Fraction(4822024, 4)
        left = LIMIT - LAST_COUNT
        share = left / (pace + left)
        self.assertEqual(left, pace * share / (1 - share))
        self.assertEqual("0.848", "%.3f" % share)
        # At the record's rate the same pace ends near 52.6
        # million.
        rate = math.exp(-RATE)
        self.assertEqual("0.9465", "%.4f" % rate)
        self.assertEqual("52.6", "%.1f" % (
            (LAST_COUNT + float(pace) * rate / (1 - rate)) / 1e6))

    def test_the_first_rule_with_all_used_keeps_this_rule(self):
        # Under the first rule with every allowance used, each
        # day's step is (1 - k) times the step before, and the
        # steps sum to what was left.
        left = float(LIMIT - LAST_COUNT)
        steps = []
        for _day in range(400):
            steps.append(SHARE * left)
            left -= steps[-1]
        for earlier, later in zip(steps, steps[1:50]):
            self.assertAlmostEqual(1 - SHARE, later / earlier, places=9)
        self.assertAlmostEqual(LIMIT - LAST_COUNT,
                               steps[0] / SHARE, delta=1e-3)

    def test_everything_else_has_kept_it_since_its_largest_week(self):
        week = {end: ELSE_BY_DAY[end] - ELSE_BY_DAY[end - 7]
                for end in range(7, 36)}
        top = max(week, key=week.get)
        self.assertEqual((day(10, 31), 6486136), (top, week[top]))
        # On each of the 19 days since, the 7 days that end
        # there added less than a line that falls by 0.61 a week.
        for end in range(top + 1, 36):
            self.assertLess(week[end],
                            week[top] * 0.61 ** ((end - top) / 7), end)
        self.assertEqual(19, 35 - top)
        least = max((week[end] / week[top]) ** (7 / (end - top))
                    for end in range(top + 1, 36))
        self.assertEqual("0.602", "%.3f" % least)
        # Under that line, the weeks to come add less than 2.7
        # million, and everything else never passes 17.6 million.
        this_week = week[top] * 0.61 ** ((35 - top) / 7)
        to_come = this_week * 0.61 / (1 - 0.61)
        self.assertEqual(("1.70", "2.65", "17.6"),
                         ("%.2f" % (this_week / 1e6), "%.2f" % (to_come / 1e6),
                          "%.1f" % ((ELSE_BY_DAY[-1] + to_come) / 1e6)))
        self.assertEqual(465512, week[35])

    def test_the_run_log_has_not(self):
        week = {end: LOG_BY_DAY[end] - LOG_BY_DAY[end - 7]
                for end in range(7, 36)}
        top = max(week, key=week.get)
        self.assertEqual((day(11, 18), 8295873), (top, week[top]))


class ThePageRecordsTheProof(unittest.TestCase):
    """The figures this module holds are the page's."""

    def test_the_page_states_the_rule_the_proof_and_the_numbers(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "the count may grow by at most k times what is left to 38 "
                "million at the start of that day",
                "**Step 1. Something is always left.**",
                "**Step 2. The count settles.**",
                "**Step 3. The limit is 38 million.**",
                "Newton's law of cooling",
                "| 1 | 6,726,717 | 359,979 | 31,633,262 |",
                "| 60 | 262,131 | 14,028 | 37,751,897 |",
                "What is left halves every 12.6 days.",
                "stops 18 tokens short of 38 million, after 244 days",
                "| 15 and 19 November | 4,822,024 | 1.21 million |",
                "| 0.51 | 24,649 |",
                "| 0.79 | 25,929 |",
                "Step 38 is 39,088,169",
                "This is a candidate."):
            self.assertIn(stated, page, stated)

    def test_the_page_states_the_second_half(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "Aitken's delta-squared process",
                "the last step is 3,046,267, and it is 7,246,289 shorter",
                "14,954,555 plus 1,280,620. That is 16,235,175.",
                "| Everything else | 1,615,732 | 11,908,288 | 14,954,555 "
                "| 0.30 | 16.2 million |",
                "| The run log | 0 | 6,040,688 | 16,318,728 | 1.70 | none |",
                "| The whole | 1,615,732 | 17,948,976 | 31,273,283 | 0.82 "
                "| 90.3 million |",
                "| 3 counts, 10 days apart, on each of the last 8 days "
                "| 14.6 to 17.0 million |",
                "| 19 November | 16.95 million | 96.62 million |",
                "| 16 November | 16.24 million | 49.84 million |",
                "from 14.75 to 47.65 million",
                "**Each day's allowance is at most r times the allowance of "
                "the day before, with r under 1.**",
                "r is 0.848",
                "the bar is 52.6 million",
                "ended on 31 October: 6,486,136",
                "The least r that holds is 0.602",
                "it never passes 17.6 million",
                "ended on 18 November: 8,295,873",
                "peaks late on 17 November at 14,977,518",
                "49.6 million for the log alone by 19 December",
                "So a chart can show a limit. It cannot prove 1."):
            self.assertIn(stated, page, stated)
        # 16.0 to 17.9: the last count of everything else plus
        # the 1.0 to 2.9 million of proof still owed.
        self.assertEqual(("16.0", "17.9"),
                         ("%.1f" % ((ELSE[2] + 1.0e6) / 1e6),
                          "%.1f" % ((ELSE[2] + 2.9e6) / 1e6)))
        self.assertEqual("1,280,620", "{:,}".format(
            round(second_degree(*ELSE)) - ELSE[2]))
        self.assertEqual(47, round(96.62 - 49.84))


if __name__ == "__main__":
    if sys.argv[1:2] == ["series"]:
        for today, commit, rest, log in series(ROOT, *sys.argv[2:3]):
            print(today.isoformat(), commit, rest, log)
    else:
        unittest.main()
