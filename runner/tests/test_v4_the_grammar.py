#!/usr/bin/env python3
"""The grammar the rung's induction actually covers.

docs/infrastructure-documents/proofs/v4-the-grammar.md. A script
of the rung is one of 22 atoms, or a script of the rung, one of
4 joiners, and an atom. The induction is a proof for that
grammar. It is not a proof for bash, and it is not a proof for
every string the size door admits. No new constraint.
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

PAGE = os.path.join(MODELS.PROOFS, "v4-the-grammar.md")
ATOMS = BOUND.ATOMS
JOINERS = BOUND.JOINERS

# Not a script of the rung. Each is a thing an atom is
# forbidden to do, or a row that stops before the next atom.
OUTSIDE = (
    "x=1",
    "cd /",
    "echo a > /tmp/x",
    "while true; do :; done",
    "read x",
    "true &&",
)


def cut(script):
    """The one (atoms, joiners) cut of a script of the rung,
    or None when the text is not in the grammar. The atom
    taken is the only one that leaves nothing, or a joiner."""
    atoms, joiners, rest = [], [], script
    while rest:
        matches = [atom for atom in ATOMS
                   if rest == atom or any(
                       rest.startswith(atom + joiner)
                       for joiner in JOINERS)]
        if len(matches) != 1:
            return None
        atom = matches[0]
        atoms.append(atom)
        rest = rest[len(atom):]
        if not rest:
            break
        found = [joiner for joiner in JOINERS
                 if rest.startswith(joiner)]
        if len(found) != 1:
            return None
        joiners.append(found[0])
        rest = rest[len(found[0]):]
        if not rest:
            return None
    if not atoms:
        return None
    return tuple(atoms), tuple(joiners)


class TheGrammar(unittest.TestCase):
    """22 atoms, 4 joiners, and one cut."""

    def test_the_atoms_are_the_22_and_the_joiners_the_4(self):
        self.assertEqual(22, len(ATOMS))
        self.assertEqual(22, len(set(ATOMS)))
        self.assertEqual((" && ", " || ", "; ", " | "), JOINERS)

    def test_an_atom_keeps_no_state(self):
        # The ban, read off the texts. The one redirect is the
        # atom that ends at /dev/null.
        ban = re.compile(
            r"\b(cd|export|exec|read|set|shopt|unset|trap|exit"
            r"|return|eval|source|pushd|popd|alias|declare|local"
            r"|cat|tee)\b|\$\{?[A-Za-z_]+\}?=|[A-Za-z_]=|>>|<")
        for atom in ATOMS:
            self.assertIsNone(ban.search(atom), atom)
            if ">" in atom:
                self.assertTrue(atom.endswith("> /dev/null"), atom)
        self.assertIn("echo a > /dev/null", ATOMS)
        self.assertIn("if true; then echo a; fi", ATOMS)

    def test_one_atom_cannot_start_another(self):
        # Finite, and it covers every length. If a second atom
        # were a way to start the first, or to start the first
        # followed by any joiner, some row would have two cuts.
        for first in ATOMS:
            for other in ATOMS:
                if other == first:
                    continue
                if first.startswith(other):
                    rest = first[len(other):]
                    self.assertFalse(
                        any(rest.startswith(joiner) for joiner in JOINERS),
                        (first, other))
                for joiner in JOINERS:
                    head = first + joiner
                    if not head.startswith(other):
                        continue
                    rest = head[len(other):]
                    self.assertFalse(
                        rest == "" or any(
                            rest.startswith(later) for later in JOINERS),
                        (first, joiner, other))

    def test_every_short_row_cuts_back_to_itself(self):
        for atoms, joiners in BOUND.rows(max_atoms=2):
            script = BOUND.text(atoms, joiners)
            self.assertEqual((atoms, joiners), cut(script), script)

    def test_the_atom_that_holds_a_joiner_is_one_atom(self):
        atom = "if true; then echo a; fi"
        self.assertEqual(((atom,), ()), cut(atom))
        script = BOUND.text(("echo a", atom), ("; ",))
        self.assertEqual((("echo a", atom), ("; ",)), cut(script))
        script = BOUND.text((atom, "echo a > /dev/null"), (" && ",))
        self.assertEqual(
            ((atom, "echo a > /dev/null"), (" && ",)), cut(script))

    def test_outside_the_grammar_does_not_cut(self):
        for script in OUTSIDE:
            self.assertIsNone(cut(script), script)

    def test_the_page_states_the_grammar(self):
        page = MODELS._flat(PAGE)
        for stated in (
                "It adds no constraint.",
                "A script of the rung is an atom, or a script of the rung",
                "It is not a proof for the shell",
                "echo a > /dev/null",
                "if true; then echo a; fi",
                "`x=1`, `cd /`",
                "while true; do :; done",
                "The default cap stays 1,048,576."):
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
