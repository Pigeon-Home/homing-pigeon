"""The corpus honesty rules, held by a test.

Set on 2026-11-23 from ChatGPT's review of the binding
ledger (the 2 emails of that afternoon, relayed in full in
ComChat): any claim drawn from the imagined complete fuzz
corpus must name its positive and negative controls; a
claim of the form searched and found nothing must carry
its bound (the certificate of the search: space, order,
budget); the cost of finding a certificate is charged to
the claim, never treated as free; and a conclusion reached
with oracle aid stays labelled oracle aided wherever it is
repeated, at the strength it was proved at (the 4 strengths:
finite inputs, a scoped corpus with a trusted oracle, a
full oracle, a uniform algorithm).

The 4 rules stand in the ledger itself,
`docs/infrastructure-documents/proofs/properties.md`, under
"The corpus honesty rules". This test holds 3 things:

1. The rules stand in the ledger, all 4, with the label
   phrase the fourth rule prescribes.
2. The one repaired claim on the bindings page (no crash
   stands open in the corpus) still carries its
   certificate beside it: the space, the order, and the
   child cap that bounds the budget.
3. The companion sections of the 2026-11-23 completion
   checklist (items 16, 18 and 19: the conditional
   theorems, the concrete conditional induction, and
   the three formal routes; item 17, the safety
   shortcut, stands beside the squeeze) stand in the
   ledger's closing section, at their proved strengths.
4. Every found nothing claim on the live proof shelf
   (no crash, no findings, 0 disagreements, 0 differences,
   found nothing) sits near a stated count or bound, so a
   new unbounded claim of that shape fails here by name.
5. The replay certificate naming rule (set 2026-11-23
   from the follow-up review of the worked examples)
   stands in the ledger, and the bindings page names
   its fuzz record under it: a replay certificate over
   the kept corpus, a scoped search record over the
   tried space, with the run's dimensions (per child
   size cap, total attempts, execution budget, replay
   availability) recorded separately.

Dated records are not scanned: the stage records and the
archive describe what was true when they were written.
The scan covers the proof pages that state standing
claims: properties.md, v4-bindings.md, v4-at-a-bound.md,
v4-at-a-limit.md, v4-the-ladder.md, v4-the-motor.md,
v4-the-folder.md, v4-the-place.md, hybrid-fuzz-10024.md
and thinking.md.
"""

import os
import re
import unittest


def _root():
    import runner
    return os.path.dirname(os.path.dirname(os.path.abspath(runner.__file__)))


def _read(*parts):
    with open(os.path.join(_root(), *parts), encoding="utf-8") as fh:
        return fh.read()


_PROOFS = ("docs", "infrastructure-documents", "proofs")

_SCANNED = (
    "properties.md",
    "v4-bindings.md",
    "v4-at-a-bound.md",
    "v4-at-a-limit.md",
    "v4-the-ladder.md",
    "v4-the-motor.md",
    "v4-the-folder.md",
    "v4-the-place.md",
    "hybrid-fuzz-10024.md",
    "thinking.md",
)

_CLAIM = re.compile(
    r"no crash stands open|no findings|0 disagreements|"
    r"0 differences|found nothing")

_BOUND = re.compile(
    r"\d[\d,]*\s+(rounds|runs|rows|scripts|inputs|entries|"
    r"states|bytes|families)|\d[\d,]*\s+of\s+\d|cap|budget|"
    r"certificate")


class TheRulesStandTest(unittest.TestCase):
    def test_the_four_rules_stand_in_the_ledger(self):
        text = _read(*_PROOFS, "properties.md")
        self.assertIn("The corpus honesty rules", text)
        for phrase in (
            "1. Controls.",
            "2. Bounded search certificates.",
            "3. The finding cost is charged.",
            "4. Oracle aided conclusions stay labelled.",
            "carries\n   the words oracle aided wherever it is repeated",
            "four strengths above (finite inputs, a scoped",
        ):
            self.assertIn(phrase, text)

    def test_the_taxonomy_the_rules_point_at_stands(self):
        text = _read(*_PROOFS, "properties.md")
        self.assertIn("Assuming future data, at four strengths", text)


class TheRepairedClaimTest(unittest.TestCase):
    def test_no_crash_claim_carries_its_certificate(self):
        text = _read(*_PROOFS, "v4-bindings.md")
        idx = text.find("no\ncrash stands open in it")
        self.assertGreaterEqual(idx, 0)
        window = text[idx:idx + 900]
        for phrase in ("certificate", "the space is",
                       "the order is", "16,384"):
            self.assertIn(phrase, window)

    def test_the_controls_stand_on_the_bindings_page(self):
        text = _read(*_PROOFS, "v4-bindings.md")
        self.assertIn("The positive control is the replay itself", text)
        self.assertIn("The negative controls", text)


class TheCompanionSectionsStandTest(unittest.TestCase):
    """Items 16, 18 and 19 of the 2026-11-23 completion checklist.

    The conditional theorems from the completed corpus,
    the concrete conditional induction, and the three
    formal routes stand in the closing section of
    properties.md, each at its proved strength, and none
    of them reads as proving P = NP or its negation.
    Item 17, the safety shortcut, stands beside the
    squeeze in the same section and is pinned here too.
    """

    def _flat(self):
        text = _read(*_PROOFS, "properties.md")
        return re.sub(r"\s+", " ", text)

    def test_the_section_and_its_parts_stand(self):
        flat = self._flat()
        for phrase in (
            "## Design from the completed corpus, and two companions",
            "Design from the completed corpus, as conditional theorems.",
            "The concrete conditional induction.",
            "The three formal routes.",
            "The safety shortcut. The squeeze is not the only shape",
        ):
            self.assertIn(phrase, flat)

    def test_the_conditional_theorems_carry_their_strengths(self):
        flat = self._flat()
        for phrase in (
            "Theorem 1, at strength 2.",
            "Theorem 2, at strength 4.",
            "Theorem 3, at strength 4.",
            "Theorem 4, at strength 4.",
            "The equivalence is the theorem.",
            "no finite corpus establishes",
        ):
            self.assertIn(phrase, flat)

    def test_the_safety_shortcut_keeps_equality_separate(self):
        flat = self._flat()
        for phrase in (
            "If B sits inside U, and every behaviour in U has the "
            "property, then every behaviour in B has it.",
            "Proving L equal to U is a separate and more expensive "
            "workload",
            "the shortcut does not apply to it",
        ):
            self.assertIn(phrase, flat)

    def test_the_safety_shortcut_boundary_is_narrowed(self):
        flat = self._flat()
        for phrase in (
            "A universal property over pairs of behaviours, for all "
            "t1 and t2 in a set T, R(t1, t2), is carried by the same "
            "inclusion",
            "B paired with B inside U paired with U",
            "The matching behaviour is a witness, and a subset can "
            "drop it",
            "opens a scoped path from this one run rule to "
            "relational proofs",
        ):
            self.assertIn(phrase, flat)

    def test_the_induction_names_relation_and_observation(self):
        flat = self._flat()
        for phrase in (
            "one of the 22 atoms",
            "one of the 4 joiners",
            "The abstract state is a pair: the status so far, "
            "and whether the pipeline in hand is running.",
            "The observation semantics is chosen deliberately",
            "the observation of a run is its output, its exit status, "
            "and the set of commands that ran.",
            "The 352 steps of M are the whole step table.",
            "the premise is named, not proved",
        ):
            self.assertIn(phrase, flat)

    def test_the_three_routes_are_named_with_their_bounds(self):
        flat = self._flat()
        for phrase in (
            "Route 1, parametric induction.",
            "Route 2, bounded exhaustive checking.",
            "Route 3, the ideal teacher.",
            "74,072,330,493, and that count was not exhausted",
            "858,319 scripts",
            "19,360 rows",
            "the conclusion stays labelled oracle aided",
        ):
            self.assertIn(phrase, flat)

    def test_nothing_in_the_section_claims_the_open_problem(self):
        flat = self._flat()
        self.assertIn(
            "None of them proves P = NP, and none of them proves "
            "its negation.",
            flat)


class TheReplayCertificateNamingTest(unittest.TestCase):
    """The naming rule, and the bindings page under it.

    A record earns the name replay certificate only
    when it carries a reproducible candidate stream or
    the retained inputs, the exact build, harness and
    verdict, and an independent way to check
    completeness for the stated claim. The fuzz record
    on the bindings page is named by that rule, and its
    dimensions stand separately.
    """

    def _flat(self, name):
        text = _read(*_PROOFS, name)
        return re.sub(r"\s+", " ", text)

    def test_the_naming_rule_stands_in_the_ledger(self):
        flat = self._flat("properties.md")
        for phrase in (
            "earns the name replay certificate only when it "
            "carries all three of these",
            "a reproducible candidate stream, or the retained "
            "inputs themselves",
            "the exact build, the harness, and the verdict the "
            "search ran under",
            "an independent way to check completeness for the "
            "stated claim",
            "a scoped search record",
            "the per child size cap, the total attempts, the "
            "execution budget",
            "A size cap is not a budget, and a budget is not a "
            "count of attempts.",
        ):
            self.assertIn(phrase, flat)

    def test_the_bindings_record_is_named_under_the_rule(self):
        flat = self._flat("v4-bindings.md")
        for phrase in (
            "As a replay certificate, the record earns the name "
            "over the kept corpus only",
            "the record is a scoped search record, not a replay "
            "certificate",
            "completeness over the tried space rests on the log "
            "alone, with no independent check",
            "The dimensions of the run stand separately.",
            "The per child size cap is 16,384 bytes.",
            "The total attempts are the 651,086,719 inputs, over "
            "the 35,270 grow runs.",
            "Replay is available over the kept corpus, and not "
            "over the tried stream.",
        ):
            self.assertIn(phrase, flat)


class FoundNothingClaimsCarryBoundsTest(unittest.TestCase):
    def test_every_claim_sits_near_a_bound(self):
        failures = []
        for name in _SCANNED:
            text = _read(*_PROOFS, name)
            flat = re.sub(r"\s+", " ", text)
            for match in _CLAIM.finditer(flat):
                lo = max(0, match.start() - 700)
                window = flat[lo:match.end() + 700]
                if not _BOUND.search(window):
                    failures.append(
                        "%s: %r" % (name, flat[match.start():match.end() + 40]))
        self.assertEqual([], failures)


if __name__ == "__main__":
    unittest.main()
