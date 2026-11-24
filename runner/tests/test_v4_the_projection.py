#!/usr/bin/env python3
"""The projection: a compact Horn chain, an exponential flat boundary.

docs/infrastructure-documents/proofs/v4-the-projection.md
states a construction that arrived in the project's P versus
NP discussion on 23 November 2026, out of the joining solver
experiment on the examples page. This file pins the parts of
it that a finite check can pin.

The system, for a fixed m. Visible variables: pairs a_i, b_i
and one output z. Internal variables: t_i and r_i. Clauses:
a_i implies t_i and b_i implies t_i for each i; t_0 implies
r_0; r_(i-1) and t_i together imply r_i; r_(m-1) implies z.
3m + 1 clauses, width at most 3, each Horn.

1. The projection onto the visible variables is exactly the
   relation R: not (every pair has a true bit and z is
   false). Checked by enumerating every visible assignment
   against every completion of the internal bits, m 1 to 5.
2. The minimally falsifying visible patterns, z false with
   exactly one true bit per pair, number exactly 2^m, m 1
   to 5.
3. The clause lemma: every clause over the visible variables
   that R implies and that some minimal pattern falsifies is
   falsified by exactly one minimal pattern, m 1 to 4. So no
   flat CNF for R has fewer than 2^m clauses at those sizes,
   and the 2^m pattern clauses achieve it exactly.
4. Unit propagation from the visible inputs derives z
   exactly when every pair has a true bit, and the canonical
   completion (t_i the OR of its pair, r_i the running
   conjunction) satisfies every clause, m 1 to 5.

The asymptotic statement, that the flat minimum is 2^m for
every m, is the doc's argument, not tested here. What is
tested is the finite enumeration the argument rests on.
"""
import itertools
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-projection.md")


# ----------------------------------------------------------------
# Variables are bit positions in an integer mask.
#   a_i at i, b_i at m + i, z at 2m,
#   t_i at 2m + 1 + i, r_i at 3m + 1 + i.
# A clause is (pos, neg): two masks of the variables appearing
# positively and negatively. An assignment mask satisfies the
# clause when it sets some positive variable or clears some
# negative one.
# ----------------------------------------------------------------

def _horn_clauses(m):
    def a(i):
        return 1 << i

    def b(i):
        return 1 << (m + i)

    z = 1 << (2 * m)

    def t(i):
        return 1 << (2 * m + 1 + i)

    def r(i):
        return 1 << (3 * m + 1 + i)

    clauses = []
    for i in range(m):
        clauses.append((t(i), a(i)))
        clauses.append((t(i), b(i)))
    clauses.append((r(0), t(0)))
    for i in range(1, m):
        clauses.append((r(i), r(i - 1) | t(i)))
    clauses.append((z, r(m - 1)))
    return clauses


def _satisfies(clauses, bits):
    return all((bits & pos) or (~bits & neg) for pos, neg in clauses)


def _in_relation(vis, m):
    """vis is a mask over the visible positions (a, b, z)."""
    every_pair = all(
        (vis >> i) & 1 or (vis >> (m + i)) & 1 for i in range(m))
    z = (vis >> (2 * m)) & 1
    return not (every_pair and not z)


def _projection(m):
    """The set of visible masks with a satisfying completion."""
    clauses = _horn_clauses(m)
    nvis = 2 * m + 1
    nint = 2 * m
    out = set()
    for vis in range(1 << nvis):
        for rest in range(1 << nint):
            if _satisfies(clauses, vis | (rest << nvis)):
                out.add(vis)
                break
    return out


def _minimal_patterns(m):
    """Visible masks falsifying R, minimal by inclusion."""
    nvis = 2 * m + 1
    falsifying = [v for v in range(1 << nvis)
                  if not _in_relation(v, m)]
    return [v for v in falsifying
            if not any(other != v and other & ~v == 0
                       for other in falsifying)]


class TestTheSystem(unittest.TestCase):
    def test_shape(self):
        for m in range(1, 7):
            clauses = _horn_clauses(m)
            self.assertEqual(len(clauses), 3 * m + 1)
            for pos, neg in clauses:
                width = bin(pos).count("1") + bin(neg).count("1")
                self.assertLessEqual(width, 3)
                # Horn: at most one positive literal.
                self.assertLessEqual(bin(pos).count("1"), 1)


class TestProjection(unittest.TestCase):
    def test_projection_is_exactly_the_relation(self):
        for m in range(1, 6):
            want = {v for v in range(1 << (2 * m + 1))
                    if _in_relation(v, m)}
            self.assertEqual(_projection(m), want, f"m={m}")


class TestMinimalPatterns(unittest.TestCase):
    def test_count_and_shape(self):
        for m in range(1, 6):
            pats = _minimal_patterns(m)
            self.assertEqual(len(pats), 2 ** m, f"m={m}")
            for p in pats:
                self.assertEqual((p >> (2 * m)) & 1, 0)
                for i in range(m):
                    pair = ((p >> i) & 1) + ((p >> (m + i)) & 1)
                    self.assertEqual(pair, 1, f"m={m} pair {i}")


class TestFlatBoundary(unittest.TestCase):
    def test_clause_lemma(self):
        # Every clause over the visible variables that R implies
        # and that some minimal pattern falsifies is falsified by
        # exactly one minimal pattern.
        for m in range(1, 5):
            nvis = 2 * m + 1
            rel = [v for v in range(1 << nvis) if _in_relation(v, m)]
            pats = _minimal_patterns(m)
            hitting = 0
            for spec in itertools.product((0, 1, 2), repeat=nvis):
                if all(s == 0 for s in spec):
                    continue
                pos = sum(1 << j for j, s in enumerate(spec) if s == 1)
                neg = sum(1 << j for j, s in enumerate(spec) if s == 2)

                def falsified(bits, pos=pos, neg=neg):
                    return (bits & pos) == 0 and (bits & neg) == neg

                if any(falsified(v) for v in rel):
                    continue  # not implied by R
                hits = sum(1 for p in pats if falsified(p))
                if hits:
                    hitting += 1
                    self.assertEqual(hits, 1, f"m={m} spec={spec}")
            self.assertGreater(hitting, 0)

    def test_pattern_clauses_achieve_the_bound(self):
        for m in range(1, 5):
            clauses = []
            for p in _minimal_patterns(m):
                pos = 1 << (2 * m)  # positive z
                neg = p  # the negation of each chosen bit
                clauses.append((pos, neg))
            self.assertEqual(len(clauses), 2 ** m)
            for v in range(1 << (2 * m + 1)):
                self.assertEqual(_satisfies(clauses, v),
                                 _in_relation(v, m), f"m={m} v={v}")


class TestPropagation(unittest.TestCase):
    def test_propagation_decides_z(self):
        for m in range(1, 6):
            clauses = _horn_clauses(m)
            for vis in range(1 << (2 * m)):
                known = {j: (vis >> j) & 1 for j in range(2 * m)}
                changed = True
                while changed:
                    changed = False
                    for pos, neg in clauses:
                        lits = [(j, 1) for j in range(4 * m + 1)
                                if (pos >> j) & 1]
                        lits += [(j, 0) for j in range(4 * m + 1)
                                 if (neg >> j) & 1]
                        unassigned = [(j, s) for j, s in lits
                                      if j not in known]
                        falsified = [(j, s) for j, s in lits
                                     if j in known and known[j] != s]
                        if len(unassigned) == 1 and \
                                len(falsified) == len(lits) - 1:
                            j, s = unassigned[0]
                            known[j] = s
                            changed = True
                every_pair = all(
                    (vis >> i) & 1 or (vis >> (m + i)) & 1
                    for i in range(m))
                self.assertEqual(known.get(2 * m) == 1, every_pair,
                                 f"m={m} vis={vis}")

    def test_canonical_completion(self):
        for m in range(1, 6):
            clauses = _horn_clauses(m)
            for vis in range(1 << (2 * m + 1)):
                full = vis
                run = 1
                for i in range(m):
                    t_i = ((vis >> i) & 1) | ((vis >> (m + i)) & 1)
                    if t_i:
                        full |= 1 << (2 * m + 1 + i)
                    run = run & t_i
                    if run:
                        full |= 1 << (3 * m + 1 + i)
                if _in_relation(vis, m):
                    # The completion of the doc: z as the visible
                    # assignment has it; the chain values as built.
                    # Where every pair is hit, R forces z true and
                    # r_m true; elsewhere r_m is false.
                    self.assertTrue(_satisfies(clauses, full),
                                    f"m={m} vis={vis}")


class TestThePage(unittest.TestCase):
    def test_page_states_the_construction(self):
        with open(PAGE, encoding="utf-8") as f:
            text = f.read()
        for needle in ("3m + 1", "2^m", "Dowling and Gallier",
                       "Supposition, written before the tests ran",
                       "test_v4_the_projection.py"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
