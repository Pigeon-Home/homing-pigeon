# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""A grep query's pattern runs against text its sender wrote, and the
engine cannot be interrupted mid-match (Q84). The shapes that can
take exponential time -- a repeat nested in a repeat that iterates,
an alternation under a repeat -- are refused before they run, with
the shape named; the rest of the list still answers."""

import os
import re
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.guard import security as SEC  # noqa: E402
from runner.ops.queries import answer_queries  # noqa: E402

REFUSED = {
    r"(a+)+$": "nested repeat",
    r"(\w+\s?)*x": "nested repeat",
    r"(?:a{1,3}){2,}": "nested repeat",
    r"(?:a{3}){2}": "nested repeat",
    r"(.*)*": "nested repeat",
    r"(?:x*y*)+": "nested repeat",
    r"(ab+)+": "nested repeat",
    r"(?:(?=a+)b)+": "nested repeat",
    r"(?>a+)+": "nested repeat",
    r"(a)(?(1)a+|b)+": "nested repeat",
    r"(a|aa)+$": "repeated alternation",
    r"(?:error|warn)+": "repeated alternation",
    r"(?:ab|cd){2}": "repeated alternation",
}

ACCEPTED = (
    r"ERROR",
    r"^\s*\d+\s+passed",
    r"error.*timeout.*retry",
    r"(?:error|warn)",
    r"(?=a+)b+",
    r"(?P<n>ab?)+",
    r"(a?)+",
    r"(a+)?",
    r"a{3}",
    r"(a)\1+",
    r"x*y*z*",
    r".*.*.*.*x",
    r"[A-Z]+: .+",
    r"\bFAIL(?:ED)?\b",
    r"(?:a|b|c){2}",   # single characters: the parser makes a class of them
)


class RegexBacktracksTest(unittest.TestCase):
    def test_the_exponential_shapes_are_named(self):
        for pattern, shape in REFUSED.items():
            re.compile(pattern)   # every one compiles: the engine would run it
            self.assertEqual(SEC.regex_backtracks(pattern), shape, pattern)

    def test_plain_repeats_pass(self):
        for pattern in ACCEPTED:
            re.compile(pattern)
            self.assertIsNone(SEC.regex_backtracks(pattern), pattern)

    def test_what_does_not_parse_is_left_to_the_compile_step(self):
        for pattern in ("(", "[", "a{2,1}", "(?(1)a+|b)+", "*"):
            with self.assertRaises(re.error):
                re.compile(pattern)
            self.assertIsNone(SEC.regex_backtracks(pattern), pattern)
        self.assertIsNone(SEC.regex_backtracks(None))
        self.assertIsNone(SEC.regex_backtracks(b"(a+)+"))
        self.assertIsNone(SEC.regex_backtracks(["(a+)+"]))

    def test_a_refused_shape_is_the_one_that_hangs(self):
        """The measurement behind the rule: the nested shape doubles
        its time for every two characters of hostile text (0.3 s at
        22 of them on the desk's box, a day at 40), where the plain
        repeat beside it answers at once on the same line."""
        line = "a" * 22 + "!"
        t0 = time.monotonic()
        self.assertIsNone(re.search(r"(a+)+$", line))
        nested = time.monotonic() - t0
        t0 = time.monotonic()
        self.assertIsNone(re.search(r"a+$", line))
        plain = time.monotonic() - t0
        self.assertGreater(nested, 0.02)
        self.assertLess(plain, 0.02)


class GrepRefusalTest(unittest.TestCase):
    def _answers(self, queries, view="full", stdout="a" * 40 + "!\nERROR x"):
        return answer_queries(queries, {"stdout": stdout, "stderr": ""},
                              {}, 8, cfg={}, view=view)

    def test_a_nested_repeat_is_refused_before_it_runs(self):
        t0 = time.monotonic()
        answers, spent = self._answers([
            {"op": "grep", "pattern": r"(a+)+$"},
            {"op": "grep", "pattern": r"(a|aa)+$"},
            {"op": "grep", "pattern": "ERROR"},
            {"op": "tail", "lines": 1},
        ])
        self.assertLess(time.monotonic() - t0, 2.0)
        self.assertEqual(spent, 4)
        self.assertEqual(answers[0], {"op": "grep", "rejected": "bad_pattern",
                                      "reason": "nested repeat"})
        self.assertEqual(answers[1], {"op": "grep", "rejected": "bad_pattern",
                                      "reason": "repeated alternation"})
        self.assertEqual(answers[2]["matches"], ["ERROR x"])
        self.assertEqual(answers[3]["lines"], ["ERROR x"])

    def test_a_pattern_that_does_not_compile_names_no_shape(self):
        answers, _spent = self._answers([{"op": "grep", "pattern": "("}])
        self.assertEqual(answers, [{"op": "grep", "rejected": "bad_pattern"}])

    def test_the_refusal_holds_under_every_view_that_runs_grep(self):
        for view in ("full", "redacted"):
            answers, _spent = self._answers(
                [{"op": "grep", "pattern": r"(a+)+$"}], view=view)
            self.assertEqual(answers[0]["rejected"], "bad_pattern", view)
            self.assertEqual(answers[0]["reason"], "nested repeat", view)
        # Views that never run grep refuse it as policy, as before.
        answers, _spent = self._answers(
            [{"op": "grep", "pattern": r"(a+)+$"}], view="attested")
        self.assertEqual(answers, [{"op": "grep", "rejected": "policy"}])

    def test_the_budget_still_counts_a_refused_pattern(self):
        answers, spent = answer_queries(
            [{"op": "grep", "pattern": r"(a+)+$"},
             {"op": "grep", "pattern": "a"}],
            {"stdout": "a", "stderr": ""}, {}, 1, cfg={})
        self.assertEqual(spent, 2)
        self.assertEqual(answers[0]["rejected"], "bad_pattern")
        self.assertEqual(answers[1], {"rejected": "budget"})


if __name__ == "__main__":
    unittest.main()
