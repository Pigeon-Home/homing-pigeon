#!/usr/bin/env python3
"""L1 of the ladder: the ratio table, on made-up quantities.

docs/infrastructure-documents/proofs/v4-the-ladder.md. No shell
and no gate. The ratio of a step to the sum of the 2 before
it, at steps 20 to 30, is within 0.01 of the page's 4 numbers.
The difference test is exact for a fixed quantity and for one
in proportion to the size. L2 to L8 are not run here.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
PAGE = os.path.join(
    ROOT, "docs", "infrastructure-documents", "proofs",
    "v4-the-ladder.md")

# Step n is the nth Fibonacci number, from 0.
SERIES = [0, 1]
while len(SERIES) <= 31:
    SERIES.append(SERIES[-1] + SERIES[-2])

TABLE = ((0, 0.50), (1, 1.00), (2, 1.89), (3, 3.43))


def value(power, step, slope=1, aside=0):
    """A made-up quantity. Power 0 is the fixed amount. A slope
    and an aside are the sharper case: so much per character,
    and a fixed amount besides."""
    if power == 0:
        return aside
    return slope * SERIES[step] ** power + aside


def ratio(power, step):
    aside = 1 if power == 0 else 0
    got = value(power, step, aside=aside)
    return got / (value(power, step - 1, aside=aside)
                  + value(power, step - 2, aside=aside))


def difference(power, step, slope=1, aside=0):
    return (value(power, step, slope, aside)
            - value(power, step - 1, slope, aside)
            - value(power, step - 2, slope, aside))


class TheRatioTable(unittest.TestCase):
    """L1, and nothing past it."""

    def test_the_series_reaches_the_cap_at_step_30(self):
        self.assertEqual(832040, SERIES[30])
        self.assertEqual(1346269, SERIES[31])
        self.assertLess(SERIES[30], 1048576)
        self.assertGreater(SERIES[31], 1048576)

    def test_the_ratio_at_steps_20_to_30_is_the_table(self):
        for power, stated in TABLE:
            worst = max(abs(ratio(power, step) - stated)
                        for step in range(20, 31))
            self.assertLess(worst, 0.01, (power, worst))
        self.assertEqual(
            [0.5] * 11, [ratio(0, step) for step in range(20, 31)])
        self.assertEqual(
            [1.0] * 11, [ratio(1, step) for step in range(20, 31)])

    def test_the_difference_is_exact_for_the_first_2(self):
        self.assertEqual(
            {-7}, {difference(0, step, aside=7) for step in range(2, 31)})
        self.assertEqual(
            {-5}, {difference(1, step, slope=3, aside=5)
                   for step in range(2, 31)})
        squares = [difference(2, step) for step in range(2, 31)]
        self.assertEqual([0, 2, 4, 12], squares[:4])
        self.assertTrue(all(b > a for a, b in zip(squares, squares[1:])))

    def test_the_page_records_l1_and_not_the_rest(self):
        with open(PAGE, encoding="utf-8") as handle:
            page = " ".join(handle.read().split())
        for stated in (
                "L1's figures are recorded here.",
                "Step 30 is 832,040.",
                "0.00443 from 1.89",
                "0.00295 from 3.43",
                "difference -7",
                "difference -5",
                "holds these figures."):
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
