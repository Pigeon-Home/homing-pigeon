#!/usr/bin/env python3
"""The goal page, held to its form.

docs/steady/GOAL.md says what the project is for and what done
means, and AGENTS.md sends every reader to it first (rule 18).
The page is the owner's, so this module holds its form and not
its words: the page is there, it is short, it states 1 goal
and numbered lines for done, each line for done has a place
that says how far it is, every file the page points at is in
the tree, and AGENTS.md points at the page before anything
else.

Why the form stands as it does. The page stood at
docs/GOAL.md until 2026-11-20, when the owner replaced it
there with a single placeholder line as a signal that a move
he had asked for had not happened. A cleanup followed the
placeholder and shrank this module to the placeholder's form,
and a later landing that day held the page as withdrawn and
this module with it. The owner then said the placeholder
was a signal and not his settled page, and directed the move
he had asked for. The page stands whole again, on the steady
shelf, with its words as they stood before the placeholder,
and this module holds the whole page's form at its new home.
Link targets are read the way GitHub reads them, from the
page's own folder.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
PAGE = os.path.join(ROOT, "docs", "steady", "GOAL.md")
AGENTS = os.path.join(ROOT, "AGENTS.md")
# A page that every seat reads first stays short enough to be
# read whole.
LONGEST = 60
_LINK = re.compile(r"\]\(([^)#]+)\)")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


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


class GoalPage(unittest.TestCase):
    """docs/steady/GOAL.md: 1 goal, and what done means."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PAGE)
        cls.parts = sections(cls.text)
        cls.done = re.findall(r"(?m)^(\d+)\. \*\*([^*]+)\*\*",
                              cls.parts.get("Done means", ""))

    def test_the_page_is_there(self):
        self.assertTrue(os.path.isfile(PAGE))

    def test_the_page_is_short_enough_to_be_read_whole(self):
        self.assertLessEqual(len(self.text.rstrip("\n").split("\n")),
                             LONGEST)

    def test_it_states_the_goal_before_anything_else(self):
        self.assertEqual("The goal", next(iter(self.parts)))
        self.assertTrue(self.parts["The goal"])

    def test_done_is_a_numbered_list_with_no_gap(self):
        self.assertGreaterEqual(len(self.done), 1)
        self.assertEqual([str(n) for n in range(1, len(self.done) + 1)],
                         [number for number, _name in self.done])

    def test_every_line_for_done_has_a_place_that_says_how_far_it_is(self):
        rows = [line for line in self.text.split("\n")
                if line.startswith("| ") and _LINK.search(line)]
        self.assertEqual(len(self.done), len(rows))
        for (_number, name), row in zip(self.done, rows):
            self.assertIn(name.strip().rstrip("."), row)

    def test_every_file_the_page_points_at_is_in_the_tree(self):
        targets = _LINK.findall(self.text)
        self.assertTrue(targets)
        for target in targets:
            self.assertTrue(os.path.exists(os.path.normpath(
                os.path.join(os.path.dirname(PAGE), target))), target)

    def test_agents_md_sends_a_reader_to_the_page_first(self):
        parts = sections(_read(AGENTS))
        names = [name for name in parts if name != "Contents"]
        self.assertIn("docs/steady/GOAL.md", parts[names[0]])
        self.assertIn("**The goal page", _read(AGENTS))


if __name__ == "__main__":
    unittest.main()
