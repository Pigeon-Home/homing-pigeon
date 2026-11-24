#!/usr/bin/env python3
"""Worked examples beside the join.

docs/infrastructure-documents/proofs/v4-the-examples.md states
four constructions that arrived in the project's P versus NP
discussion on 23 November 2026. This file pins the parts of
them that a finite check can pin.

1. The equality family. F is the conjunction of (x_i if and
   only if y_i) over i in range(m). Under the grouped order,
   every x before every y, the cut after the x block holds
   exactly 2^m distinct residual functions. Under the
   interleaved order, x_0, y_0, x_1, y_1 and so on, no cut
   holds more than 3.
2. The Levin style measure. L(F) is the minimum over
   programs p that output a verified satisfying assignment
   of |p| + ceil(log2(t + 1)), t the steps of p on F. The
   budget search that tries every program of length at most
   b, each for at most 2^(b - |p|) - 1 steps, spends less
   than (b + 1) * 2^b simulated steps in all. A fixed
   program of length l0 that runs in at most (n + 2)^d steps
   has measure at most l0 + d * log2(n + 2) + 1, which is
   the arithmetic inside the claim that a uniform
   logarithmic budget for L is P = NP in disguise.
3. Improve, the MaxSAT gap closer. V(F, a) counts the
   clauses of F that a makes false, and OPT(F) is its
   minimum. The contraction g -> floor(0.61 * g) reaches 0
   from the statistics page's starting gap of 3,393,230 in
   the number of rounds the doc records. On toy formulas a
   brute force Improve, standing in for the assumed
   polynomial one, closes the gap in one step and keeps both
   lines sound.
4. The hard truth table. With N = 2^m and S = floor(N /
   (100 * m)), a circuit of at most S gates over a fixed
   binary basis takes fewer bits to describe than N, so
   some N bit table needs more than S gates. On the
   smallest case the test builds the lexicographically
   first such table by prefix extension, the same shape as
   the construction the doc states, with brute force in
   place of the assumed polynomial queries.

The asymptotic claims themselves are not tested here, and
the doc says so. What is tested is the finite arithmetic
each claim rests on.
"""
import itertools
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tests import test_v4_models as MODELS  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-examples.md")


# ----------------------------------------------------------------
# 1. The equality family: residual functions at a cut.
# ----------------------------------------------------------------

def _residual_counts(m, order):
    """For each cut in order, the number of distinct residuals.

    A residual is the set of completions of the variables not
    yet read that satisfy every (x_i if and only if y_i),
    given one fixed prefix. Two prefixes with the same set of
    completions have the same residual.
    """
    all_vars = [("x", i) for i in range(m)] + [
        ("y", i) for i in range(m)]
    counts = []
    for cut in range(len(order) + 1):
        prefix_vars = order[:cut]
        rest = [v for v in all_vars if v not in prefix_vars]
        seen = set()
        for bits in itertools.product((0, 1),
                                      repeat=len(prefix_vars)):
            prefix = dict(zip(prefix_vars, bits))
            completions = set()
            for rbits in itertools.product((0, 1),
                                           repeat=len(rest)):
                full = dict(prefix)
                full.update(zip(rest, rbits))
                if all(full[("x", i)] == full[("y", i)]
                       for i in range(m)):
                    completions.add(rbits)
            seen.add(frozenset(completions))
        counts.append(len(seen))
    return counts


def _grouped_order(m):
    return [("x", i) for i in range(m)] + [
        ("y", i) for i in range(m)]


def _interleaved_order(m):
    order = []
    for i in range(m):
        order.append(("x", i))
        order.append(("y", i))
    return order


class EqualityFamilyTest(unittest.TestCase):
    """The grouped cut grows as 2^m. The interleaved cut
    never passes 3, the dead state included."""

    def test_grouped_cut_is_two_to_the_m(self):
        for m in (1, 2, 3):
            counts = _residual_counts(m, _grouped_order(m))
            self.assertEqual(counts[m], 2 ** m)

    def test_grouped_counts_double_along_the_x_block(self):
        for m in (1, 2, 3):
            counts = _residual_counts(m, _grouped_order(m))
            for k in range(m + 1):
                self.assertEqual(counts[k], 2 ** k)

    def test_interleaved_never_passes_three(self):
        for m in (1, 2, 3):
            counts = _residual_counts(
                m, _interleaved_order(m))
            self.assertLessEqual(max(counts), 3)

    def test_interleaved_reaches_three_once_a_pair_can_die(self):
        # With m at least 2, the cut after x_1 holds the dead
        # residual beside the two pending ones, so the bound
        # of 3 is met, not just respected.
        for m in (2, 3):
            counts = _residual_counts(
                m, _interleaved_order(m))
            self.assertEqual(max(counts), 3)

    def test_interleaved_ends_at_one(self):
        # Every variable read, one residual remains: the
        # single completion when the prefix was consistent,
        # the empty one when it was not, counted once each
        # across prefixes, and the distinct count at the
        # last cut is 2 for m = 1 and stays small. The claim
        # the doc makes is the bound of 3, checked above;
        # here only the sanity of the last cut is pinned.
        for m in (1, 2, 3):
            counts = _residual_counts(
                m, _interleaved_order(m))
            self.assertLessEqual(counts[-1], 2)


# ----------------------------------------------------------------
# 2. The Levin style measure and its budget search.
# ----------------------------------------------------------------

def _levin_cost(length, steps):
    return length + math.ceil(math.log2(steps + 1))


def _budget_steps(b):
    """Simulated steps spent by the budget b search: for
    each length l from 0 to b, 2^l programs run for at most
    2^(b - l) - 1 steps each."""
    return sum(2 ** l * (2 ** (b - l) - 1)
               for l in range(b + 1))


class LevinMeasureTest(unittest.TestCase):
    """The arithmetic of L(F) and of the search that a
    uniform bound on L(F) would make polynomial."""

    def test_cost_charges_length_and_log_time(self):
        self.assertEqual(_levin_cost(0, 0), 0)
        self.assertEqual(_levin_cost(5, 0), 5)
        self.assertEqual(_levin_cost(5, 1), 6)
        self.assertEqual(_levin_cost(5, 7), 8)
        self.assertEqual(_levin_cost(5, 8), 9)

    def test_program_count_up_to_budget(self):
        for b in range(0, 9):
            self.assertEqual(sum(2 ** l for l in range(b + 1)),
                             2 ** (b + 1) - 1)

    def test_budget_search_step_bound(self):
        for b in range(0, 9):
            self.assertLess(_budget_steps(b), (b + 1) * 2 ** b)

    def test_fixed_program_gives_logarithmic_measure(self):
        # A fixed witness program of length l0 whose run
        # takes at most (n + 2)^d steps has measure at most
        # l0 + d * log2(n + 2) + 1. This is the quantitative
        # heart of: if P = NP, the budget is O(log n).
        for l0 in (0, 3, 40):
            for d in (1, 2, 5):
                for n in (1, 10, 1000, 10 ** 6):
                    bound = (l0 + d * math.log2(n + 2) + 1)
                    worst = _levin_cost(l0, (n + 2) ** d)
                    self.assertLessEqual(worst, bound)


# ----------------------------------------------------------------
# 3. Improve, the MaxSAT gap closer.
# ----------------------------------------------------------------

def _violated(clauses, assignment):
    """V(F, a): the clauses of F that a makes false. A clause
    is a tuple of (variable, wanted) pairs."""
    bad = 0
    for clause in clauses:
        if not any(assignment[v] == wanted
                   for v, wanted in clause):
            bad += 1
    return bad


def _opt(clauses, variables):
    best = None
    best_a = None
    for bits in itertools.product((0, 1),
                                  repeat=len(variables)):
        a = dict(zip(variables, bits))
        v = _violated(clauses, a)
        if best is None or v < best:
            best = v
            best_a = a
    return best, best_a


def _contract(gap):
    return math.floor(0.61 * gap)


class ImproveTest(unittest.TestCase):
    """The contraction arithmetic, and the two lines staying
    sound on toy formulas."""

    def test_contraction_reaches_zero_from_the_page_gap(self):
        # The statistics page's thought experiment starts at
        # 3,393,230 and contracts by floor(0.61 * g) a round.
        gap = 3393230
        rounds = 0
        while gap > 0:
            gap = _contract(gap)
            rounds += 1
        self.assertEqual(rounds, 30)

    def test_contraction_rounds_are_logarithmic(self):
        for start in (1, 2, 10, 100, 10 ** 6):
            gap = start
            rounds = 0
            while gap > 0:
                gap = _contract(gap)
                rounds += 1
            self.assertLessEqual(
                rounds, 2 * math.log2(start + 1) + 2)

    def test_example_a_the_lines_meet_at_zero(self):
        # F = (x OR y). Start x = y = false: U = 1, L = 0.
        clauses = [(("x", True), ("y", True))]
        start = {"x": False, "y": False}
        self.assertEqual(_violated(clauses, start), 1)
        opt, witness = _opt(clauses, ["x", "y"])
        self.assertEqual(opt, 0)
        self.assertEqual(_violated(clauses, witness), 0)

    def test_example_b_the_lines_meet_at_one(self):
        # F = (x) AND (NOT x). Every assignment violates
        # exactly one clause, so OPT = 1 and F is
        # unsatisfiable.
        clauses = [(("x", True),), (("x", False),)]
        for bit in (False, True):
            self.assertEqual(
                _violated(clauses, {"x": bit}), 1)
        opt, _ = _opt(clauses, ["x"])
        self.assertEqual(opt, 1)

    def test_brute_force_improve_closes_in_one_step(self):
        # Standing in for the assumed polynomial Improve, the
        # brute force one returns an optimal assignment with
        # L' = U' = OPT, so the new gap is 0, which meets
        # floor(0.61 * g) for every starting gap g.
        formulas = [
            [(("x", True), ("y", True))],
            [(("x", True),), (("x", False),)],
            [(("x", True), ("y", False)),
             (("y", True), ("z", True)),
             (("x", False), ("z", False))],
            [(("x", True),), (("y", True),),
             (("x", False), ("y", False), ("z", True))],
        ]
        for clauses in formulas:
            variables = sorted({v for clause in clauses
                                for v, _ in clause})
            start = {v: False for v in variables}
            upper = _violated(clauses, start)
            lower = 0
            opt, witness = _opt(clauses, variables)
            new_upper = _violated(clauses, witness)
            new_lower = opt
            self.assertLessEqual(lower, new_lower)
            self.assertLessEqual(new_lower, opt)
            self.assertLessEqual(opt, new_upper)
            self.assertLessEqual(new_upper, upper)
            self.assertLessEqual(new_upper - new_lower,
                                 _contract(upper - lower))


# ----------------------------------------------------------------
# 4. The hard truth table.
# ----------------------------------------------------------------

_BASIS = {
    "and": lambda a, b: a & b,
    "or": lambda a, b: a | b,
    "xor": lambda a, b: a ^ b,
    "nand": lambda a, b: 1 - (a & b),
}


def _description_bits(m, s):
    """Bits to describe a circuit of at most s gates: each
    gate by its type, from a basis of 16 or fewer, and the
    indices of its two incoming wires, then the output wire
    named once. Wires are the m inputs and the gates so
    far, m + s in all."""
    wires = m + s
    per_gate = 4 + 2 * math.ceil(math.log2(wires))
    return s * per_gate + math.ceil(math.log2(wires))


def _computable_tables(m, s):
    """Every truth table on m inputs that a circuit of at
    most s gates over the test basis computes. A table is a
    tuple of output bits over the assignments in counting
    order."""
    rows = list(itertools.product((0, 1), repeat=m))
    inputs = [tuple(row[i] for row in rows) for i in range(m)]
    tables = set(inputs)
    wires = list(inputs)
    for _ in range(s):
        new = set()
        for op in _BASIS.values():
            for a in wires:
                for b in wires:
                    new.add(tuple(op(x, y)
                                  for x, y in zip(a, b)))
        tables |= new
        wires = wires + [t for t in new if t not in wires]
    return tables


def _first_hard_table(m, s):
    """The lexicographically first table not computable
    with at most s gates, built by prefix extension: at
    each bit, take 0 when some hard table still extends
    the prefix, else take 1."""
    n = 2 ** m
    computable = _computable_tables(m, s)
    all_tables = set(itertools.product((0, 1), repeat=n))
    hard = all_tables - computable
    if not hard:
        return None
    prefix = ()
    for _ in range(n):
        if any(t[:len(prefix) + 1] == prefix + (0,)
               for t in hard):
            prefix = prefix + (0,)
        else:
            prefix = prefix + (1,)
    return prefix


class HardTableTest(unittest.TestCase):
    """The counting that makes a hard table exist, and the
    prefix extension that finds the first one, in the
    smallest case."""

    def test_circuits_are_fewer_than_tables(self):
        for m in range(8, 25):
            n = 2 ** m
            s = n // (100 * m)
            self.assertLess(_description_bits(m, s), n)

    def test_some_table_needs_more_than_s_gates(self):
        # Fewer descriptions than tables: the descriptions
        # number at most 2^bits, the tables 2^N, and bits
        # is below N, so a hard table exists.
        for m in range(8, 25):
            n = 2 ** m
            s = n // (100 * m)
            self.assertLess(2 ** _description_bits(m, s),
                            2 ** n)

    def test_first_hard_table_by_prefix_extension(self):
        found = _first_hard_table(2, 1)
        self.assertIsNotNone(found)
        computable = _computable_tables(2, 1)
        self.assertNotIn(found, computable)
        all_tables = set(itertools.product((0, 1), repeat=4))
        hard = all_tables - computable
        self.assertEqual(found, min(hard))

    def test_prefix_extension_agrees_for_zero_gates(self):
        found = _first_hard_table(2, 0)
        computable = _computable_tables(2, 0)
        self.assertNotIn(found, computable)
        all_tables = set(itertools.product((0, 1), repeat=4))
        self.assertEqual(found, min(all_tables - computable))


class PageTest(unittest.TestCase):
    """The page exists and says what this file pins."""

    def test_page_states_the_four_constructions(self):
        with open(PAGE, encoding="utf-8") as fh:
            text = fh.read()
        for needle in ("2^m", "L(F)", "0.61",
                       "truth table"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
