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
"""
import math
import os
import random
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
