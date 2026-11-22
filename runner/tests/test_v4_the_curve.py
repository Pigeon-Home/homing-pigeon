#!/usr/bin/env python3
"""The curve: limits that follow from a rule.

docs/infrastructure-documents/proofs/v4-the-curve.md proves that
the count of security tokens has an upper limit under 1 rule:
each day the count may grow by at most a fixed share of what is
left to a limit L. Then something is always left, the count
settles, and with the allowance used it settles at L. It is
Newton's law of cooling, with the count for the temperature and
the limit for the room.

The page names no limit first. Its limits follow from a rule on
the steps that the counts have kept: each 7 days add less than a
line that falls by 0.61 a week from the largest 7 days. This
module reads each limit off the series by day, holds what each
coming week may add, and holds what the page says of 38 million,
the first number it carried.

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

PAGE = os.path.join(ROOT, "docs", "infrastructure-documents", "proofs",
                    "v4-the-curve.md")


def _flat(path):
    """A page as 1 line: its words, 1 space apart."""
    with open(path, encoding="utf-8") as handle:
        return " ".join(handle.read().split())


# The first number the page carried: a goal named before the
# counts were read. No limit of the page is named first now.
FIRST_NUMBER = 38000000
# What a line falls by in a week: the least number of 2 digits
# that everything but the run log has kept since its largest
# 7 days.
A_WEEK = 0.61
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


def by_the_rule(series, share=A_WEEK):
    """The rule on the steps, read off a series by day: (the
    day its largest 7 days ended, the line on the last day,
    what the weeks to come add under, the limit). The line
    falls by `share` a week from the largest 7 days."""
    last = len(series) - 1
    week = {end: series[end] - series[end - 7]
            for end in range(7, last + 1)}
    top = max(week, key=week.get)
    now = week[top] * share ** ((last - top) / 7)
    come = now * share / (1 - share)
    return top, now, come, series[-1] + come


def may_add(series, weeks, share=A_WEEK):
    """What each of the coming `weeks` weeks may add under the
    line, in whole tokens: the line at the week's end, rounded
    down."""
    now = by_the_rule(series, share)[1]
    return [int(now * share ** week) for week in range(1, weeks + 1)]


def stands_at_most(series, weeks, share=A_WEEK):
    """Where a series stands at most `weeks` weeks after its
    last count, with every week's allowance used."""
    return series[-1] + sum(may_add(series, weeks, share))


def lines():
    """(where it stands, its limit) for everything else, for
    the run log if it keeps the rule, and for the whole."""
    rest = (ELSE_BY_DAY[-1], math.ceil(by_the_rule(ELSE_BY_DAY)[3]))
    log = (LOG_BY_DAY[-1], math.ceil(by_the_rule(LOG_BY_DAY)[3]))
    return [rest, log, (rest[0] + log[0], rest[1] + log[1])]


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
    """The 3 steps of the proof, walked. The proof asks nothing
    of the limit, so it is walked at 3: the limit of everything
    but the run log, the limit of the whole, and the first
    number."""

    def limits(self):
        (rest, limit), _log, (whole, both) = lines()
        return ((rest, limit), (whole, both), (LAST_COUNT, FIRST_NUMBER))

    def test_step_1_something_is_always_left(self):
        # A day's growth is drawn at random, from 0 to all the
        # rule allows. 6 shares, 5,000 days each, whole tokens.
        draw = random.Random(38)
        for start, limit in self.limits():
            for numerator, denominator in ((1, 2), (1, 10), (535, 10000),
                                           (1, 100), (9, 10), (999, 1000)):
                count = start
                for _day in range(5000):
                    left = limit - count
                    self.assertGreater(left, 0)
                    grown = draw.randint(
                        0, allowance(left, numerator, denominator))
                    self.assertLessEqual(grown * denominator,
                                         left * numerator)
                    count += grown
                self.assertLess(count, limit)

    def test_step_2_the_count_settles_under_the_bar(self):
        # With every allowance used, each day's count is not
        # under the day before's and is under the limit, and
        # a day comes after which it does not move.
        for start, limit in self.limits():
            count, days = start, 0
            while True:
                grown = allowance(limit - count, 535, 10000)
                if grown == 0:
                    break
                self.assertLess(count + grown, limit)
                count += grown
                days += 1
            # Fewer than 19 tokens are left, so the rule allows 0.
            self.assertEqual(18, limit - count)
            self.assertTrue(200 <= days <= 300, days)
        self.assertEqual(0, allowance(18, 535, 10000))
        self.assertEqual(1, allowance(19, 535, 10000))

    def test_step_3_what_is_left_goes_to_0(self):
        # What is left is multiplied by the same factor each
        # day, so after n days it is that factor to the power
        # n, times what was left at the start.
        for begin, limit in self.limits():
            left = start = limit - begin
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
        for begin, limit in self.limits():
            start = limit - begin
            count = float(begin)
            for day in range(1, 91):
                count += SHARE * (limit - count)
                self.assertAlmostEqual(
                    limit - start * math.exp(-RATE * day), count, delta=1e-3)
        self.assertAlmostEqual(0.0535, SHARE, places=4)
        self.assertAlmostEqual(12.6, math.log(2) / RATE, places=1)
        # The rule of the 3 lines, said for every moment: what
        # is left is multiplied by 0.61 each week, and halves
        # every 9.8 days.
        self.assertEqual(
            "9.8", "%.1f" % (7 * math.log(2) / -math.log(A_WEEK)))


class TheNumbers(unittest.TestCase):
    """The page's tables, and the test for a limit."""

    WEEKS = ("26 November", "3 December", "10 December", "17 December",
             "24 December", "31 December")

    def test_the_3_lines(self):
        top, now, come, limit = by_the_rule(ELSE_BY_DAY)
        self.assertEqual((day(10, 31), 1695547, 2652010, 17606770),
                         (top, round(now), math.ceil(come),
                          math.ceil(limit)))
        top, now, come, limit = by_the_rule(LOG_BY_DAY)
        self.assertEqual((day(11, 18), 7730275, 12090943, 28409671),
                         (top, round(now), math.ceil(come),
                          math.ceil(limit)))
        self.assertEqual([(14954760, 17606770), (16318728, 28409671),
                          (31273488, 46016441)], lines())
        self.assertEqual(14742953, 2652010 + 12090943)
        self.assertEqual(("17.6", "28.4", "46.0"), tuple(
            "%.1f" % (limit / 1e6) for _stands, limit in lines()))

    def test_what_each_coming_week_may_add(self):
        # The page's table, in whole tokens: what a week may
        # add is the line at the week's end, rounded down.
        rest, log = may_add(ELSE_BY_DAY, 6), may_add(LOG_BY_DAY, 6)
        self.assertEqual(
            [1034283, 630913, 384857, 234762, 143205, 87355], rest)
        self.assertEqual(
            [4715467, 2876435, 1754625, 1070321, 652896, 398266], log)
        self.assertEqual(
            [15989043, 16619956, 17004813, 17239575, 17382780, 17470135],
            [stands_at_most(ELSE_BY_DAY, week) for week in range(1, 7)])
        self.assertEqual(
            [21034195, 23910630, 25665255, 26735576, 27388472, 27786738],
            [stands_at_most(LOG_BY_DAY, week) for week in range(1, 7)])
        self.assertEqual(
            [37023238, 40530586, 42670068, 43975151, 44771252, 45256873],
            [stands_at_most(ELSE_BY_DAY, week)
             + stands_at_most(LOG_BY_DAY, week) for week in range(1, 7)])
        # The 6 weeks end on the page's 6 days.
        ends = [FIRST_DAY + datetime.timedelta(days=day(11, 19) + 7 * week)
                for week in range(1, 7)]
        self.assertEqual(list(self.WEEKS), [
            "%d %s" % (end.day, end.strftime("%B")) for end in ends])
        # However many weeks are walked, a line stays under its
        # limit.
        for series, (_stands, limit) in zip((ELSE_BY_DAY, LOG_BY_DAY),
                                            lines()):
            for weeks in (1, 6, 60, 600):
                self.assertLess(stands_at_most(series, weeks), limit)

    def test_with_every_allowance_used_it_is_the_first_rule(self):
        # What is left to the limit at each week's start, and
        # it is multiplied by 0.61 each week.
        limit = lines()[0][1]
        left = [limit - stands_at_most(ELSE_BY_DAY, week)
                for week in range(0, 8)]
        self.assertEqual(
            [2652010, 1617727, 986814, 601957, 367195, 223990], left[:6])
        for earlier, later in zip(left, left[1:]):
            self.assertAlmostEqual(A_WEEK, later / earlier, places=4)
        # Under 100,000 is left after 7 weeks, and not after 6.
        self.assertGreater(left[6], 100000)
        self.assertLess(left[7], 100000)
        # In whole tokens the line allows 0 from the 30th week,
        # and the count stops 16 tokens short of the limit.
        weeks = may_add(ELSE_BY_DAY, 40)
        self.assertEqual(29, weeks.index(0))
        self.assertEqual(16, limit - stands_at_most(ELSE_BY_DAY, 40))

    def test_on_a_day_between_the_line_alone_allows_more(self):
        # A day that is `between` days after a week's end stands
        # on the count 7 days before it, plus its own 7 days and
        # every 7 days after: each under the line of its day.
        _top, now, _come, limit = by_the_rule(ELSE_BY_DAY)
        last = len(ELSE_BY_DAY) - 1
        bars = [ELSE_BY_DAY[last + between - 7]
                + now * A_WEEK ** (between / 7) / (1 - A_WEEK)
                for between in range(1, 7)]
        self.assertEqual(18037368, math.ceil(max(bars)))
        self.assertEqual(3, 1 + bars.index(max(bars)))
        self.assertTrue(all(bar > limit for bar in bars))
        self.assertLess(max(bars), 18.1e6)
        # 60 weeks walked under the line alone, a count for each
        # day: what its 7 days add is drawn at random under the
        # line, and then is all the line allows.
        draw = random.Random(1961)
        for used in (False, True):
            count = list(ELSE_BY_DAY)
            for place in range(last + 1, last + 1 + 7 * 60):
                line = int(now * A_WEEK ** ((place - last) / 7))
                count.append(count[place - 7]
                             + (line if used else draw.randint(0, line)))
            for place in range(last + 1, len(count)):
                between = (place - last) % 7
                if between == 0:
                    self.assertLess(count[place], limit)
                else:
                    self.assertLess(count[place], bars[between - 1])
        # With all used, the third day after a week's end comes
        # within 100 tokens of its bar, and passes the limit.
        self.assertLess(bars[2] - count[last + 3 + 7 * 59], 100)
        self.assertGreater(count[last + 3 + 7 * 59], limit)
        # If the count does not fall, a day between is not above
        # the week's end that follows it, which is under the
        # limit. Everything else fell on 2 of its 35 days.
        self.assertEqual(2, sum(1 for place in range(1, last + 1)
                                if ELSE_BY_DAY[place]
                                < ELSE_BY_DAY[place - 1]))

    def test_if_r_were_another_number(self):
        rows = {}
        for share in (0.61, 0.65, 0.70, 0.80):
            rest = by_the_rule(ELSE_BY_DAY, share)[3]
            log = by_the_rule(LOG_BY_DAY, share)[3]
            rows[share] = tuple("%.1f" % (count / 1e6)
                                for count in (rest, log, rest + log))
        self.assertEqual({0.61: ("17.6", "28.4", "46.0"),
                          0.65: ("18.7", "30.8", "49.5"),
                          0.70: ("20.7", "34.7", "55.4"),
                          0.80: ("29.1", "48.5", "77.6")}, rows)
        # With r under 0.602 the counts of everything else have
        # passed the line; at 0.61 and above they have not.
        week = {end: ELSE_BY_DAY[end] - ELSE_BY_DAY[end - 7]
                for end in range(7, 36)}
        top = max(week, key=week.get)

        def kept(share):
            return all(week[end] < week[top] * share ** ((end - top) / 7)
                       for end in range(top + 1, 36))

        self.assertEqual([False, False, True, True, True, True],
                         [kept(share) for share in
                          (0.60, 0.602, 0.61, 0.65, 0.70, 0.80)])

    def test_the_test_finds_a_limit_that_is_there(self):
        # On a curve made by the rule, 3 counts any same number
        # of days apart give the limit back.
        stands, limit = lines()[0]
        start, rate = limit - stands, -math.log(A_WEEK) / 7

        def on_the_curve(day):
            return limit - start * math.exp(-rate * day)

        for apart in (1, 5, 9, 30):
            factor, found = limit_of(
                on_the_curve(0), on_the_curve(apart),
                on_the_curve(2 * apart))
            self.assertAlmostEqual(math.exp(-rate * apart), factor, places=9)
            self.assertAlmostEqual(limit, found, delta=1e-3)
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
        # The last step is the longest of the 4, and above what
        # the rule allows the whole in the 7 days to 26 November.
        self.assertEqual(max(paces), paces[-1])
        week = may_add(ELSE_BY_DAY, 1)[0] + may_add(LOG_BY_DAY, 1)[0]
        self.assertEqual((5749750, "0.82"), (week, "%.2f" % (week / 7e6)))
        self.assertGreater(paces[-1] * 7e6, week)

    def test_what_the_campaign_finds_does_level_off(self):
        factor, limit = limit_of(
            FINDS["30 October"], FINDS["8 November"], FINDS["17 November"])
        self.assertEqual((0.51, 24649), (round(factor, 2), round(limit)))
        factor, limit = limit_of(
            FINDS["4 November"], FINDS["11 November"], FINDS["18 November"])
        self.assertEqual((0.79, 25929), (round(factor, 2), round(limit)))
        # The log's tail, at its own average for a find, against
        # what the rule gives each line.
        a_find = 16318670 / 24804
        self.assertEqual(658, round(a_find))
        self.assertEqual(
            ("0.4", "1.3"),
            ("%.1f" % (a_find * (24649 - 23988) / 1e6),
             "%.1f" % (a_find * (25929 - 23988) / 1e6)))
        rest, log = by_the_rule(ELSE_BY_DAY)[2], by_the_rule(LOG_BY_DAY)[2]
        self.assertEqual(("2.65", "12.09"),
                         ("%.2f" % (rest / 1e6), "%.2f" % (log / 1e6)))
        # The proof still owed, 1.0 to 2.9 million, fits under
        # the rule at its lower end and not at its upper.
        self.assertTrue(1.0e6 < rest < 2.9e6)

    def test_step_39_of_the_series_is_the_first_past_46_million(self):
        whole = lines()[2][1]
        series = [0, 1]
        while series[-1] <= whole:
            series.append(series[-1] + series[-2])
        self.assertEqual((39, 63245986, 39088169),
                         (len(series) - 1, series[39], series[38]))
        self.assertAlmostEqual(1.618, series[39] / series[38], places=3)
        # Step 31 is the first past the cap of 1,048,576.
        self.assertTrue(series[30] < 1048576 < series[31])


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
        # A limit for each line gives the limit of the whole.
        (_rest, rest), (_log, log), (_whole, whole) = lines()
        self.assertEqual((46016441, 46016441),
                         (whole, 17606770 + 28409671))
        self.assertEqual(whole, rest + log)
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
        whole = lines()[2][1]
        self.assertGreater(with_none(365), whole)
        self.assertGreater(with_none(3650), 1000 * whole)
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

    def test_the_first_rule_with_all_used_keeps_this_rule(self):
        # Under the first rule with every allowance used, each
        # day's step is (1 - k) times the step before, and the
        # steps sum to what was left.
        for stands, limit in lines() + [(LAST_COUNT, FIRST_NUMBER)]:
            left = float(limit - stands)
            steps = []
            for _day in range(400):
                steps.append(SHARE * left)
                left -= steps[-1]
            for earlier, later in zip(steps, steps[1:50]):
                self.assertAlmostEqual(1 - SHARE, later / earlier, places=9)
            self.assertAlmostEqual(limit - stands,
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
                            week[top] * A_WEEK ** ((end - top) / 7), end)
        self.assertEqual(19, 35 - top)
        least = max((week[end] / week[top]) ** (7 / (end - top))
                    for end in range(top + 1, 36))
        self.assertEqual("0.602", "%.3f" % least)
        # 0.61 is the next number of 2 digits above the least.
        self.assertEqual(61, math.ceil(least * 100))
        # Under that line, the weeks that end 7, 14, 21 days on
        # add under 2,652,010, and at each of those week's ends
        # everything else stands under 17,606,770.
        found, this_week, to_come, limit = by_the_rule(ELSE_BY_DAY)
        self.assertEqual(top, found)
        self.assertEqual(("1.70", "2.65", "17.6"),
                         ("%.2f" % (this_week / 1e6),
                          "%.2f" % (to_come / 1e6), "%.1f" % (limit / 1e6)))
        self.assertEqual((2652010, 17606770),
                         (math.ceil(to_come), math.ceil(limit)))
        self.assertEqual(465512, week[35])

    def test_the_run_log_has_not(self):
        week = {end: LOG_BY_DAY[end] - LOG_BY_DAY[end - 7]
                for end in range(7, 36)}
        top = max(week, key=week.get)
        self.assertEqual((day(11, 18), 8295873), (top, week[top]))
        # 1 day has passed since its top. The 7 days that end on
        # it are under the line, and 1 day is not a rule kept.
        self.assertEqual(1, 35 - top)
        self.assertEqual(5767107, week[35])
        self.assertLess(week[35], by_the_rule(LOG_BY_DAY)[1])


class TheFirstNumber(unittest.TestCase):
    """38 million: the goal of 2026-11-16, named before the
    counts were read. What the counts say of it."""

    def test_at_the_last_4_days_pace_it_is_passed_on_25_november(self):
        pace = Fraction(4822024, 4)
        self.assertEqual("1.21", "%.2f" % (pace / 1e6))
        days = (FIRST_NUMBER - LAST_COUNT) / pace
        self.assertEqual("5.58", "%.2f" % days)
        last = datetime.date(2026, 11, 19)
        self.assertEqual(
            datetime.date(2026, 11, 25),
            last + datetime.timedelta(days=math.ceil(days)))
        # And the whole's limit by the rule, 46,016,441, at the
        # same pace: by 2 December.
        days = (lines()[2][1] - LAST_COUNT) / pace
        self.assertEqual(
            datetime.date(2026, 12, 2),
            last + datetime.timedelta(days=math.ceil(days)))

    def test_what_38_million_takes_from_that_pace(self):
        pace = Fraction(4822024, 4)
        left = FIRST_NUMBER - LAST_COUNT
        share = left / (pace + left)
        self.assertEqual(left, pace * share / (1 - share))
        self.assertEqual("0.848", "%.3f" % share)
        self.assertEqual(15, round(100 * (1 - share)))
        # At the record's rate the same pace ends near 52.6
        # million.
        rate = math.exp(-RATE)
        self.assertEqual("0.9465", "%.4f" % rate)
        self.assertEqual("52.6", "%.1f" % (
            (LAST_COUNT + float(pace) * rate / (1 - rate)) / 1e6))

    def test_the_rule_of_the_3_lines_does_not_keep_it(self):
        # The whole may stand under 38 million on 26 November
        # and over it on 3 December.
        at = [stands_at_most(ELSE_BY_DAY, week)
              + stands_at_most(LOG_BY_DAY, week) for week in (1, 2)]
        self.assertEqual([37023238, 40530586], at)
        self.assertTrue(at[0] < FIRST_NUMBER < at[1])
        self.assertGreater(lines()[2][1], FIRST_NUMBER)

    def test_the_proof_holds_for_it_as_for_any_number(self):
        # With the record's share, in whole tokens, the count
        # stops 18 tokens short of 38 million after 244 days.
        count, days = LAST_COUNT, 0
        while allowance(FIRST_NUMBER - count, 535, 10000):
            count += allowance(FIRST_NUMBER - count, 535, 10000)
            days += 1
        self.assertEqual((18, 244), (FIRST_NUMBER - count, days))


class ThePageRecordsTheProof(unittest.TestCase):
    """The figures this module holds are the page's."""

    def test_the_page_states_where_the_numbers_come_from(self):
        page = _flat(PAGE)
        for stated in (
                "# The curve: limits that follow from a rule",
                "no limit on this page is named first",
                "line on a day = top x r^(days since the top / 7)",
                "The least r that holds is 0.602, and 0.61 is the next "
                "number of 2 digits above it.",
                "| Everything else | 14,954,760 | 6,486,136, ended 31 October "
                "| 1,695,547 | 2,652,010 | 17,606,770 |",
                "| The run log, if it keeps the rule from 19 November "
                "| 16,318,728 | 8,295,873, ended 18 November | 7,730,275 "
                "| 12,090,943 | 28,409,671 |",
                "| The whole | 31,273,488 | | | 14,742,953 | 46,016,441 |",
                "| 26 November | 1,034,283 | 15,989,043 | 4,715,467 "
                "| 21,034,195 | 37,023,238 |",
                "| 3 December | 630,913 | 16,619,956 | 2,876,435 "
                "| 23,910,630 | 40,530,586 |",
                "| 10 December | 384,857 | 17,004,813 | 1,754,625 "
                "| 25,665,255 | 42,670,068 |",
                "| 17 December | 234,762 | 17,239,575 | 1,070,321 "
                "| 26,735,576 | 43,975,151 |",
                "| 24 December | 143,205 | 17,382,780 | 652,896 "
                "| 27,388,472 | 44,771,252 |",
                "| 31 December | 87,355 | 17,470,135 | 398,266 "
                "| 27,786,738 | 45,256,873 |",
                "If the 7 days ending on 26 November add more than 1,034,283 "
                "to everything but the run log, the rule is broken",
                "| 0.61, the least of 2 digits the counts have kept "
                "| 17.6 million | 28.4 million | 46.0 million |",
                "| 0.65 | 18.7 million | 30.8 million | 49.5 million |",
                "| 0.70 | 20.7 million | 34.7 million | 55.4 million |",
                "| 0.80 | 29.1 million | 48.5 million | 77.6 million |",
                "With r under 0.602, the counts of everything else have "
                "already passed the line."):
            self.assertIn(stated, page, stated)

    def test_the_page_states_what_it_says_of_38_million(self):
        page = _flat(PAGE)
        for stated in (
                "The first number this page carried was 38 million.",
                "**The first number here was 38 million.**",
                "the whole passes 38 million on 25 November",
                "r is 0.848 a day",
                "the whole stops near 52.6 million",
                "may stand at 37,023,238 on 26 November and at 40,530,586 "
                "on 3 December",
                "no chart carries it",
                "It holds for 17,606,770, for 38 million, and for any "
                "number above the count."):
            self.assertIn(stated, page, stated)
        # The page's 2 pictures stand in the tree, and neither
        # carries the first number.
        for name in ("limit", "two-limits"):
            asset = "assets/security-tokens-%s-2026-11-19.svg" % name
            self.assertIn(asset, page)
            with open(os.path.join(ROOT, *asset.split("/")),
                      encoding="utf-8") as chart:
                drawn = chart.read()
            for first in ("38M", "38 million", "38,000,000"):
                self.assertFalse(first in drawn,
                                 "%s carries %s" % (asset, first))

    def test_the_page_states_the_rule_the_proof_and_the_numbers(self):
        page = _flat(PAGE)
        for stated in (
                "the count may grow by at most k times what is left to L "
                "at the start of that day",
                "**Step 1. Something is always left.**",
                "**Step 2. The count settles.**",
                "**Step 3. The limit is L.**",
                "Newton's law of cooling",
                "| 26 November | 2,652,010 | 1,034,283 | 15,989,043 |",
                "| 3 December | 1,617,727 | 630,913 | 16,619,956 |",
                "| 10 December | 986,814 | 384,857 | 17,004,813 |",
                "| 17 December | 601,957 | 234,762 | 17,239,575 |",
                "| 24 December | 367,195 | 143,205 | 17,382,780 |",
                "| 31 December | 223,990 | 87,355 | 17,470,135 |",
                "What is left halves every 9.8 days.",
                "Under 100,000 is left after 7 weeks.",
                "That is the 30th week. So the count stops 16 tokens short "
                "of 17,606,770",
                "The largest of the 6 bars is 18,037,368, 3 days after a "
                "week's end.",
                "The count has fallen on 2 days.",
                "| 15 and 19 November | 4,822,024 | 1.21 million |",
                "The rule allows the whole 5,749,750 in the 7 days to "
                "26 November. That is 0.82 million a day",
                "| 0.51 | 24,649 |",
                "| 0.79 | 25,929 |",
                "| 1.0 to 2.9 million | 2.65 million |",
                "| 0.4 to 1.3 million | 12.09 million |",
                "Step 39 is 63,245,986",
                "This is a candidate."):
            self.assertIn(stated, page, stated)

    def test_the_page_states_the_second_half(self):
        page = _flat(PAGE)
        for stated in (
                "Aitken's delta-squared process",
                "the last step is 3,046,267, and it is 7,246,289 shorter",
                "14,954,555 plus 1,280,620. That is 16,235,175.",
                "| Everything else | 1,615,732 | 11,908,288 | 14,954,555 "
                "| 0.30 | 16.2 million |",
                "| The run log | 0 | 6,040,688 | 16,318,728 | 1.70 | none |",
                "| The whole | 1,615,732 | 17,948,976 | 31,273,283 | 0.82 "
                "| 90.3 million |",
                "17,606,770 plus 28,409,671 is 46,016,441.",
                "| 3 counts, 10 days apart, on each of the last 8 days "
                "| 14.6 to 17.0 million |",
                "| 19 November | 16.95 million | 96.62 million |",
                "| 16 November | 16.24 million | 49.84 million |",
                "from 14.75 to 47.65 million",
                "**Each day's allowance is at most r times the allowance of "
                "the day before, with r under 1.**",
                "S is the line on 19 November, and r is 0.61.",
                "ended on 31 October: 6,486,136",
                "The least r that holds is 0.602",
                "add under 2,652,010, and at each of those week's ends it "
                "stands under 17,606,770",
                "ended on 18 November: 8,295,873",
                "The 7 days ending on 19 November added 5,767,107",
                "peaks late on 17 November at 14,977,518",
                "49.6 million for the log alone by 19 December",
                "It passes 46 million within a year",
                "So a chart can show a limit. It cannot prove 1."):
            self.assertIn(stated, page, stated)
        # The sentence the page once carried, that everything
        # else never passes 17.6 million, held at week's ends
        # alone. It is gone.
        self.assertNotIn("never passes 17.6 million", page)
        # 16.0 to 17.9: the last count of everything else plus
        # the 1.0 to 2.9 million of proof still owed.
        self.assertEqual(("16.0", "17.9"),
                         ("%.1f" % ((ELSE[2] + 1.0e6) / 1e6),
                          "%.1f" % ((ELSE[2] + 2.9e6) / 1e6)))
        self.assertEqual("1,280,620", "{:,}".format(
            round(second_degree(*ELSE)) - ELSE[2]))
        self.assertEqual(47, round(96.62 - 49.84))


class TheRecordAndTheChartsCarryTheLines(unittest.TestCase):
    """The fifth snapshot of the statistics record and the charts
    of 19 November carry the 3 limits this module reads off the
    counts. Nothing on them is named first."""

    RECORD = os.path.join(ROOT, "docs", "infrastructure-documents",
                          "project", "statistics.md")

    def chart(self, name):
        with open(os.path.join(
                ROOT, "assets", "security-tokens-%s-2026-11-19.svg" % name),
                encoding="utf-8") as handle:
            return handle.read()

    def test_the_record_states_the_3_limits(self):
        with open(self.RECORD, encoding="utf-8") as handle:
            record = handle.read()
        (rest, rest_limit), (log, log_limit), (whole, whole_limit) = lines()
        for stated in (
                "| Everything else | %s | %.1fM |"
                % (format(rest, ","), rest_limit / 1e6),
                "| The run log, if it keeps the rule from 2026-11-19 "
                "| %s | %.1fM |" % (format(log, ","), log_limit / 1e6),
                "| The whole | %s | %.1fM |"
                % (format(whole, ","), whole_limit / 1e6),
                "a line that falls by %s a week" % A_WEEK):
            self.assertIn(stated, record, stated)

    def test_each_line_a_chart_draws_ends_where_the_rule_puts_it(self):
        def drawn(count, top):
            # A count as the charts place it: 320 units of height
            # for `top` tokens, to 1 place, as the charts are
            # written.
            placed = "%.1f" % (424 - 320 * count / top)
            return placed[:-2] if placed.endswith(".0") else placed

        (rest, rest_limit), (log, log_limit), (whole, whole_limit) = lines()
        # On 2026-12-31 a line stands at its limit, less what is
        # left after 6 weeks.
        for name, stands, limit, top in (
                ("growth", whole, whole_limit, 60e6),
                ("limit", whole, whole_limit, 50e6)):
            end = limit - (limit - stands) * A_WEEK ** 6
            self.assertIn('<circle cx="704" cy="%s" r="3.5"'
                          % drawn(end, top), self.chart(name), name)
        # The 2 limits chart was drawn again on 2026-11-21,
        # counted to that day at the 3.17.32.12 head
        # (everything else 15,331,349, the run log
        # 16,740,539), so its 2 lines start from that count
        # and end at the axis edge on their paths, 40 days
        # on, at the limits the rule gave that day:
        # 17,634,068 and 27,239,005.
        two = self.chart("two-limits")
        for stands, limit in ((15331349, 17634068),
                              (16740539, 27239005)):
            end = limit - (limit - stands) * A_WEEK ** (40 / 7.0)
            self.assertIn("L 704 %s" % drawn(end, 30e6), two,
                          "two-limits")
        # The flat line of the whole stands at the limit itself.
        for name, top in (("growth", 60e6), ("limit", 50e6)):
            self.assertIn(
                "M 80 %s L 704 %s" % ((drawn(whole_limit, top),) * 2),
                self.chart(name), name)
        # Each chart says its limits as the page does. The
        # 2 limits chart says the run log's as the rule gave
        # it on 2026-11-21, 27.2M (see above).
        for name, said in (("growth", ("46.0M", "17.6M", "28.4M")),
                           ("two-limits", ("17.6M", "27.2M")),
                           ("limit", ("46.0 million",))):
            for limit in said:
                self.assertIn(limit, self.chart(name), name)


if __name__ == "__main__":
    if sys.argv[1:2] == ["series"]:
        for today, commit, rest, log in series(ROOT, *sys.argv[2:3]):
            print(today.isoformat(), commit, rest, log)
    else:
        unittest.main()
