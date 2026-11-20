#!/usr/bin/env python3
"""The goal page, held to its form.

docs/GOAL.md is the owner's page, and AGENTS.md sends every
reader to it first (rule 18). Its words are his alone: on
2026-11-20 he replaced the whole page with a single line of
his own, and this module follows his hand the way the pins
follow his edits elsewhere. What a test can still hold is
the form that stands whatever words he puts there: the page
is at docs/GOAL.md, it stays short enough to be read whole,
every file it points at is in the tree, and AGENTS.md points
at the page before anything else.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
PAGE = os.path.join(ROOT, "docs", "GOAL.md")
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
    """docs/GOAL.md: the owner's page, held to its place and size."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PAGE)

    def test_the_page_is_there(self):
        self.assertTrue(os.path.isfile(PAGE))

    def test_the_page_is_short_enough_to_be_read_whole(self):
        self.assertLessEqual(len(self.text.rstrip("\n").split("\n")),
                             LONGEST)

    def test_every_file_the_page_points_at_is_in_the_tree(self):
        for target in _LINK.findall(self.text):
            self.assertTrue(os.path.exists(
                os.path.join(ROOT, "docs", *target.split("/"))), target)

    def test_agents_md_sends_a_reader_to_the_page_first(self):
        parts = sections(_read(AGENTS))
        names = [name for name in parts if name != "Contents"]
        self.assertIn("docs/GOAL.md", parts[names[0]])
        self.assertIn("**The goal page", _read(AGENTS))


if __name__ == "__main__":
    unittest.main()
