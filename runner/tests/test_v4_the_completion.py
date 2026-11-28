#!/usr/bin/env python3
"""The hypothetical completion theorem, held by a test.

docs/infrastructure-documents/proofs/v4-the-completion.md
states the completion theorem for B2 and B3 conditionally,
piloted on B2 and B3 at one frozen grammar and environment,
with a premise ledger of 19 rows, each labelled proved,
checked, tested, assumed, or open. This file pins the parts
of that page a finite check can pin:

1. The ledger holds 19 rows, each with exactly one label
   from the five the page defines, in the counts the page
   supposes: 1 proved, 4 checked, 7 tested, 3 assumed,
   4 open.
2. The frozen counts the theorem uses agree with the
   shelf: 22 atoms, 4 joiners, and 352 steps of M.
3. The theorem section names ledger rows, the page carries
   its disclaimer about P versus NP, and the page never
   uses the string the shelf forbids or an em dash.
4. The readme entry for the page names its scope, its
   assumptions, and this test file.
5. The bindings page carries the corpus controls
   completion: the positive control on a closed class, and
   the cost of finding the certificate charged to the
   claim.

The theorem itself is not tested here, and the doc says
so. What is tested is the ledger's shape and the counts.
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tests import test_v4_at_a_bound as BOUND  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-completion.md")
README = os.path.join(MODELS.PROOFS, "readme.md")
BINDINGS = os.path.join(MODELS.PROOFS, "v4-bindings.md")

LABELS = ("proved", "checked", "tested", "assumed", "open")
EXPECTED_COUNTS = {"proved": 1, "checked": 4, "tested": 7,
                   "assumed": 3, "open": 4}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _ledger_rows(text):
    rows = []
    for line in text.splitlines():
        match = re.match(r"\| (L\d+) \| (.*?) \| (\w+) \|", line)
        if match:
            rows.append((match.group(1), match.group(3)))
    return rows


class LedgerShapeTest(unittest.TestCase):
    def test_the_ledger_holds_19_rows_with_the_supposed_labels(self):
        rows = _ledger_rows(_read(PAGE))
        self.assertEqual(19, len(rows))
        self.assertEqual(["L%d" % n for n in range(1, 20)],
                         [row for row, _label in rows])
        counts = {}
        for _row, label in rows:
            self.assertIn(label, LABELS)
            counts[label] = counts.get(label, 0) + 1
        self.assertEqual(EXPECTED_COUNTS, counts)

    def test_every_open_and_assumed_row_is_named_as_such(self):
        text = _read(PAGE)
        self.assertIn("3 rows stand assumed", text)
        self.assertIn("4 stand open", text)


class FrozenCountsTest(unittest.TestCase):
    def test_the_frozen_counts_agree_with_the_shelf(self):
        self.assertEqual(22, len(BOUND.ATOMS))
        self.assertEqual(4, len(BOUND.JOINERS))
        self.assertEqual(352, 4 * 4 * 22)
        text = _read(PAGE)
        for phrase in ("22 atoms", "4 joiners", "352",
                       "74,072,330,493", "bash 5.2.21",
                       "at most 49 characters"):
            self.assertIn(phrase, text)


class ConditionalWordingTest(unittest.TestCase):
    def test_the_theorem_names_its_premises(self):
        text = _read(PAGE)
        start = text.index("## The theorem, stated conditionally")
        end = text.index("## The four strengths")
        section = text[start:end]
        for row in ("L1", "L5", "L10", "L11", "L15", "L19"):
            self.assertIn(row, section)
        self.assertIn("**B2, conditional.**", section)
        self.assertIn("**B3, conditional.**", section)
        self.assertIn("**The hypothetical completion.**", section)

    def test_the_page_claims_nothing_about_p_versus_np(self):
        text = _read(PAGE)
        self.assertIn("Nothing on this page states or", text)
        self.assertIn("implies a proved result about P versus NP", text)
        self.assertNotIn("P = NP is proved", text)
        self.assertNotIn("P ≠ NP is proved", text)

    def test_the_page_keeps_the_house_rules(self):
        text = _read(PAGE)
        self.assertNotIn("FINAL", text)
        self.assertNotIn("—", text)
        self.assertNotIn("–", text)

    def test_the_four_strengths_stand_named(self):
        text = _read(PAGE)
        for phrase in ("Strength 1 is finite inputs",
                       "Strength 2", "a scoped corpus with a trusted oracle",
                       "Strength 3 is a full", "Strength 4 is a uniform algorithm",
                       "stands at strength 1, and at no higher strength",
                       "No premise proved, checked, tested,"):
            self.assertIn(phrase, text)


class ReadmeEntryTest(unittest.TestCase):
    def test_the_readme_names_scope_assumptions_and_this_test(self):
        text = _read(README)
        idx = text.index("`v4-the-completion.md`")
        window = text[idx:idx + 1200]
        for phrase in ("hypothetical completion",
                       "premise ledger of 19 rows",
                       "runner/tests/test_v4_the_completion.py",
                       "strength 1"):
            self.assertIn(phrase, window)


class BindingsControlsCompletionTest(unittest.TestCase):
    def test_the_positive_control_stands_on_a_closed_class(self):
        text = _read(BINDINGS)
        self.assertIn("The positive control stands on a closed class", text)
        self.assertIn("2,664 entries", text)

    def test_the_finding_cost_is_charged_on_the_bindings_page(self):
        text = _read(BINDINGS)
        self.assertIn("the cost of finding the", text)
        self.assertIn("35,270 grow runs", text)
        self.assertIn("651,086,719 inputs", text)
        self.assertIn("That search is the price of the no", text)


if __name__ == "__main__":
    unittest.main()
