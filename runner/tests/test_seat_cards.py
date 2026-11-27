# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Every label on the v1 diagram has a seat card, and every card is whole.

The gap this closes. The diagram in assets/how-it-fits-together-wide.svg
is the project's map of itself: seventeen labeled parts, each a seat a
reader (or a visiting SI asked to think like a component) may need to
speak from. The seat cards in docs/steady/design/seat-cards-v1-diagram.md
describe each part from its own seat. Without a check, the two drift:
a label is renamed on the diagram and its card keeps the old name, a
new part is drawn with no card at all, or a card quietly loses one of
its fields and stops answering the reflexive set.

So this test parses the diagram itself. It reads every text run in
the SVG with its position, rebuilds the phrases the drawing makes
(single runs, runs stacked at one x within a label's line spacing,
and the one pair of runs that share a row and join with a slash),
and asserts that each of the seventeen canonical labels is among
them. It then asserts the design doc carries a level two heading
with exactly that label for each one, no more and no fewer, and that
each card states all seven fields. Two standing facts are pinned by
name: the Oracle's card says it is not Muse, and the card for You
says the seat stands outside the box.
"""

import os
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SVG = os.path.join(ROOT, "assets", "how-it-fits-together-wide.svg")
DOC = os.path.join(ROOT, "docs", "steady", "design", "seat-cards-v1-diagram.md")

# The diagram's labels, verbatim, in the diagram's own order.
LABELS = [
    "You (and the SI you bring)",
    "a job",
    "Transports",
    "The Door",
    "Signature Check",
    "Job Queue",
    "The Runner",
    "Shared-Secret Check",
    "The Cage",
    "The Oracle",
    "Size Guard",
    "The SI's Mind (outside the box)",
    "Runner-to-SI Exchange (v2)",
    "DTLS (v3)",
    "The Work Loop",
    "The Way Back",
    "Reply to Your SI / Signed Result",
]

# The seven fields every card states, in order.
FIELDS = [
    "What it is",
    "Inputs",
    "Outputs",
    "What it can see",
    "What it cannot see",
    "What it trusts and why",
    "What would make it fail honestly",
]


def svg_runs():
    """(x, y, fill, text) for every text element in the diagram."""
    runs = []
    for el in ET.parse(SVG).iter():
        if el.tag.rsplit("}", 1)[-1] != "text":
            continue
        text = "".join(el.itertext()).strip()
        if not text:
            continue
        runs.append((float(el.get("x", 0)), float(el.get("y", 0)),
                     el.get("fill", ""), text))
    return runs


def svg_phrases(runs):
    """The phrases the drawing makes from its runs.

    A label on the sheet is either one run, two runs stacked at the
    same x within a label's line spacing (joined with a space), or
    the pair of runs that share a row at the end of The Way Back
    (joined with a slash). Subtitles join too, into phrases nobody
    claims as labels; the canonical list is what is asserted, so the
    extra phrases cost nothing.
    """
    phrases = {text for _x, _y, _fill, text in runs}
    for x1, y1, _f1, t1 in runs:
        for x2, y2, _f2, t2 in runs:
            if abs(x1 - x2) <= 2 and 0 < y2 - y1 <= 34:
                phrases.add(t1 + " " + t2)
            if y1 == y2 and x2 > x1:
                phrases.add(t1 + " / " + t2)
    return phrases


def doc_cards():
    """label -> card body, from the design doc's level two headings."""
    with open(DOC, encoding="utf-8") as fh:
        text = fh.read()
    cards = {}
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    # parts: [preamble, heading, body, heading, body, ...]
    # Bodies are whitespace folded: the doc wraps its lines, and a
    # phrase that crosses a wrap is still one phrase.
    for i in range(1, len(parts), 2):
        cards[parts[i].strip()] = " ".join(parts[i + 1].split())
    return cards


class SeatCardsTest(unittest.TestCase):

    def test_every_canonical_label_stands_on_the_diagram(self):
        phrases = svg_phrases(svg_runs())
        missing = [label for label in LABELS if label not in phrases]
        self.assertEqual([], missing,
                         "labels not found in the SVG: " + ", ".join(missing))

    def test_no_unlisted_white_label_on_the_diagram(self):
        # The diagram's primary labels are drawn in white. A new white
        # run that no canonical label contains is a part drawn without
        # a card, and this names it until the list and the doc grow.
        # The sheet's own title is white too and is not a component.
        stray = [text for _x, _y, fill, text in svg_runs()
                 if fill == "#ffffff"
                 and text != "Homing Pigeon v1"
                 and not any(text in label for label in LABELS)]
        self.assertEqual([], stray,
                         "white diagram text with no seat card: "
                         + ", ".join(stray))

    def test_every_label_has_a_card_heading(self):
        cards = doc_cards()
        self.assertEqual(sorted(LABELS), sorted(cards),
                         "the doc's card headings are not the diagram's "
                         "labels, exactly")

    def test_every_card_states_all_seven_fields(self):
        cards = doc_cards()
        for label in LABELS:
            body = cards.get(label, "")
            for field in FIELDS:
                self.assertIn("**" + field + ":**", body,
                              label + " is missing its field: " + field)

    def test_the_oracle_card_says_it_is_not_claude(self):
        body = doc_cards().get("The Oracle", "")
        self.assertIn("It is not Muse", body)
        self.assertIn("inside the host boundary", body)

    def test_the_owner_card_places_the_seat_outside_the_box(self):
        body = doc_cards().get("You (and the SI you bring)", "")
        self.assertIn("outside the box", body)
        mind = doc_cards().get("The SI's Mind (outside the box)", "")
        self.assertIn("outside the box", mind)


if __name__ == "__main__":
    unittest.main()
