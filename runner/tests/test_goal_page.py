#!/usr/bin/env python3
"""The goal page, after the conductor withdrew it.

docs/GOAL.md stood from 2026-11-19 as the page that said what the
project is for and what done means, and AGENTS.md sent every reader
to it first (rule 18). On 2026-11-20 the conductor cut the page to
a single placeholder line himself. The page is his alone, so this
module does not restore it, does not move it, and does not hold
its old form: that form is gone at his word, and a test that kept
holding it would stay red against his own edit.

What this module holds now is the withdrawn state the conductor
left: the page carries no standing form, AGENTS.md records the
withdrawal in its first section and in rule 18 instead of sending
a reader to the page, and the map of where things live no longer
lists the page at the top of docs/. If the conductor stands the
page up again, in this place or in another, this module is
rewritten in the same landing that restores the pointers.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
PAGE = os.path.join(ROOT, "docs", "GOAL.md")
AGENTS = os.path.join(ROOT, "AGENTS.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _flat(text):
    """The text with every run of whitespace folded to one space."""
    return re.sub(r"\s+", " ", text)


def sections(text):
    """{heading: body} for a page's second-level headings, in the
    page's order."""
    out, name = {}, None
    for line in text.split("\n"):
        if line.startswith("## "):
            name = line[3:].strip()
            out[name] = []
        elif name is not None:
            out[name].append(line)
    return {name: "\n".join(body).strip() for name, body in out.items()}


class GoalPageWithdrawn(unittest.TestCase):
    """docs/GOAL.md: withdrawn by the conductor on 2026-11-20."""

    @classmethod
    def setUpClass(cls):
        cls.page = _read(PAGE)
        cls.agents = _read(AGENTS)
        cls.parts = sections(cls.agents)

    def test_the_page_carries_no_standing_form(self):
        self.assertEqual({}, sections(self.page))
        self.assertNotIn("## The goal", self.page)
        self.assertNotIn("## Done means", self.page)
        self.assertEqual([], re.findall(
            r"(?m)^\d+\. \*\*[^*]+\*\*", self.page))

    def test_the_placeholder_is_not_a_page_a_seat_may_build_on(self):
        lines = [line for line in self.page.split("\n") if line.strip()]
        self.assertLessEqual(len(lines), 2)
        self.assertEqual([], re.findall(r"\]\([^)]+\)", self.page))

    def test_agents_first_section_records_the_withdrawal(self):
        names = [name for name in self.parts if name != "Contents"]
        self.assertEqual("The goal page", names[0])
        body = _flat(self.parts[names[0]])
        self.assertIn("conductor", body)
        self.assertIn("withdrew it on 2026-11-20", body)
        self.assertIn("No seat reads it first", body)

    def test_agents_rule_18_records_the_withdrawn_state(self):
        flat = _flat(self.agents)
        self.assertIn("**The goal page", self.agents)
        self.assertIn("withdrawn 2026-11-20", flat)
        self.assertIn("no seat restores, moves, or edits it", flat)
        self.assertIn("now holds the withdrawn state", flat)

    def test_no_live_pointer_in_agents_sends_a_reader_to_the_page(self):
        self.assertNotIn("](docs/GOAL.md)", self.agents)
        self.assertNotIn("(docs/GOAL.md)", self.agents)
        self.assertNotIn("The goal: read this first", self.agents)
        self.assertNotIn("Read it before anything else", self.agents)

    def test_where_things_live_lists_no_goal_page_at_the_top_of_docs(self):
        rows = [line for line in self.agents.split("\n")
                if line.startswith("| `docs/` |")]
        self.assertEqual(1, len(rows))
        self.assertNotIn("GOAL.md", rows[0])


if __name__ == "__main__":
    unittest.main()
