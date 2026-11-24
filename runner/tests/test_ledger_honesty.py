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
3. Every found nothing claim on the live proof shelf
   (no crash, no findings, 0 disagreements, 0 differences,
   found nothing) sits near a stated count or bound, so a
   new unbounded claim of that shape fails here by name.

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
