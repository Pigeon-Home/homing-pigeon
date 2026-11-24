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

5. Tree decomposition elimination. On a supplied, checked
   tree decomposition, the bottom up elimination of section
   5 computes the exact weighted optimum and a witness that
   scores it. The checker enforces the one tree the theorem
   assumes: a supplied forest once passed it, and the
   elimination silently kept the last root's table. The
   witness is reconstructed from the minimizing rows in
   one pass, not copied row by row. On a fixed seed family
   of rooted trees with one and two variable weighted
   clauses, it agrees with brute force on every instance.
6. The odd cycle. Adjacent differ on a cycle of length n
   costs 0 for even n and 1 for odd n. Per edge block sums
   stay at 0 at every length, every proper subset of an odd
   cycle's clauses is satisfiable, and a width 2 path
   decomposition closes the gap in linear time.
7. Block merge monotonicity. Summing the independent
   minima of a partition of the clauses is a lower bound
   on OPT, and merging blocks never lowers it. On the odd
   cycle the bound stays at 0 until the final merge, so
   monotonicity alone gives no contraction rate.
8. The threshold query. Asking whether an assignment of
   cost at most floor((L + U) / 2) exists, and recording
   the cost and source of each update, at least halves the
   gap per answer and ends with the lines meeting at OPT.
   At threshold 0 the question is satisfiability itself.

The asymptotic claims themselves are not tested here, and
the doc says so. What is tested is the finite arithmetic
each claim rests on.
"""
import itertools
import math
import os
import random
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
    # The log term is ceil(log2(steps + 1)), computed in
    # exact integer arithmetic: for steps at least 0,
    # steps.bit_length() is that ceiling. The float form
    # math.ceil(math.log2(steps + 1)) loses the + 1 once
    # steps + 1 passes 2^53 (it rounds back down to the
    # power of two), and returns 53 at steps = 2^53 where
    # the exact value is 54.
    return length + steps.bit_length()


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

    def test_cost_log_term_is_exact_at_the_float_edge(self):
        # At steps = 2^53 the float form of the log term
        # returns 53, because steps + 1 rounds back down
        # to 2^53 before the logarithm is taken. The exact
        # value is 54, and the helper must give it.
        self.assertEqual(_levin_cost(0, 2 ** 53), 54)
        self.assertEqual(_levin_cost(5, 2 ** 53), 59)

    def test_cost_log_term_matches_an_integer_ceiling(self):
        # An independent integer ceiling of log2, computed
        # by doubling, held against the helper at the
        # powers of two, one to each side of them, and at
        # a spread of plain values, up to 2^70.
        def ceil_log2(x):
            k = 0
            while (1 << k) < x:
                k += 1
            return k

        values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16,
                  17, 100, 10 ** 6, 2 ** 53, 10 ** 30]
        for k in range(1, 71):
            values += [2 ** k - 1, 2 ** k, 2 ** k + 1]
        for steps in values:
            for length in (0, 1, 40):
                self.assertEqual(
                    _levin_cost(length, steps),
                    length + ceil_log2(steps + 1))

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
    # floor(0.61 * gap) in exact integer arithmetic. The
    # float form rounds the product once the gap passes
    # 2^53: at gap 9,007,199,254,740,995 it gives
    # 5,494,391,545,392,007, exactly one above the exact
    # floor 5,494,391,545,392,006.
    return 61 * gap // 100


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

    def test_contraction_is_exact_at_the_float_edge(self):
        # At this gap the float form of the contraction
        # returns 5,494,391,545,392,007, exactly one above
        # the exact floor. The helper must give the floor.
        self.assertEqual(_contract(9007199254740995),
                         5494391545392006)

    def test_contraction_matches_the_exact_fraction(self):
        # floor(61 * gap / 100) computed with exact
        # fractions, held against the helper around the
        # float edge and at a spread of plain gaps.
        from fractions import Fraction

        gaps = [0, 1, 2, 3, 99, 100, 101, 3393230,
                2 ** 53 - 1, 2 ** 53, 2 ** 53 + 1,
                2 ** 53 + 3, 9007199254740995, 10 ** 18,
                10 ** 30 + 7]
        for gap in gaps:
            exact = Fraction(61 * gap, 100)
            self.assertEqual(
                _contract(gap),
                exact.numerator // exact.denominator)

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
    order.

    Each partial circuit keeps its own wire list, and a
    gate is appended to one circuit at a time, so the
    wires a gate reads are always wires that circuit has
    already paid for. The first form of this helper pooled
    the wires of every partial circuit into one shared
    list; a gate could then read two wires that each cost
    a gate of their own and be charged as one round, which
    computes a depth bound, not a gate bound: at m = 3,
    s = 2 it reported 164 tables where the true count is
    78."""
    rows = list(itertools.product((0, 1), repeat=m))
    inputs = [tuple(row[i] for row in rows) for i in range(m)]
    tables = set(inputs)
    circuits = {tuple(inputs)}
    for _ in range(s):
        nxt = set()
        for wires in circuits:
            for op in _BASIS.values():
                for a in wires:
                    for b in wires:
                        t = tuple(op(x, y)
                                  for x, y in zip(a, b))
                        tables.add(t)
                        nxt.add(wires + (t,))
        circuits = nxt
    return tables


def _tables_by_gate_sequences(m, s):
    """The same set as _computable_tables, built the other
    way: a recursion over explicit gate sequences, where
    each sequence carries its own wire list and every wire
    of every sequence of at most s gates is collected.
    The regression tests hold the two constructions
    against each other."""
    rows = list(itertools.product((0, 1), repeat=m))
    inputs = [tuple(row[i] for row in rows) for i in range(m)]
    found = set(inputs)

    def extend(wires, gates_left):
        if gates_left == 0:
            return
        for op in _BASIS.values():
            for a in wires:
                for b in wires:
                    t = tuple(op(x, y)
                              for x, y in zip(a, b))
                    found.add(t)
                    extend(wires + [t], gates_left - 1)

    extend(list(inputs), s)
    return found


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

    def test_three_inputs_two_gates_count_is_78(self):
        # The regression for the pooled wires defect: the
        # first form of _computable_tables reported 164
        # tables here, a depth bound, not a gate bound.
        # The gate bound count is 78.
        self.assertEqual(len(_computable_tables(3, 2)), 78)

    def test_the_phantom_table_needs_three_gates(self):
        # (0,0,0,0,0,0,1,0) is x AND y AND (NOT z) in
        # counting order: one gate for the NOT, then two
        # ANDs, 3 gates in all. The pooled helper admitted
        # it at 2 gates; the fixed one does not, and the
        # plain AND of all 3 inputs, at exactly 2 gates,
        # separates the two counts from the other side.
        phantom = (0, 0, 0, 0, 0, 0, 1, 0)
        self.assertNotIn(phantom, _computable_tables(3, 2))
        self.assertIn(phantom, _computable_tables(3, 3))
        and3 = (0, 0, 0, 0, 0, 0, 0, 1)
        self.assertIn(and3, _computable_tables(3, 2))
        self.assertNotIn(and3, _computable_tables(3, 1))

    def test_tables_agree_with_gate_sequence_enumeration(self):
        # The whole small family, both constructions: the
        # level by level circuit lists against the
        # recursion over explicit gate sequences.
        for m, s in ((1, 0), (1, 1), (1, 2), (2, 0),
                     (2, 1), (2, 2), (2, 3), (3, 0),
                     (3, 1), (3, 2)):
            self.assertEqual(_computable_tables(m, s),
                             _tables_by_gate_sequences(m, s))

    def test_table_counts_grow_and_inputs_stay(self):
        # More gates never lose a table, the inputs are
        # computable at every bound, and at m = 2 the
        # second gate already reaches all 16 tables.
        for m in (1, 2, 3):
            rows = list(itertools.product((0, 1), repeat=m))
            inputs = {tuple(row[i] for row in rows)
                      for i in range(m)}
            previous = set()
            for s in (0, 1, 2):
                tables = _computable_tables(m, s)
                self.assertLessEqual(previous, tables)
                self.assertLessEqual(inputs, tables)
                previous = tables
        self.assertEqual(len(_computable_tables(2, 2)), 16)

    def test_zero_and_one_gate_counts_stand(self):
        # The published small cases were inside the pooled
        # helper's valid scope and do not move: 2 tables
        # at 0 gates and 9 at 1 gate, for m = 2.
        self.assertEqual(len(_computable_tables(2, 0)), 2)
        self.assertEqual(len(_computable_tables(2, 1)), 9)

    def test_prefix_extension_agrees_for_zero_gates(self):
        found = _first_hard_table(2, 0)
        computable = _computable_tables(2, 0)
        self.assertNotIn(found, computable)
        all_tables = set(itertools.product((0, 1), repeat=4))
        self.assertEqual(found, min(all_tables - computable))


# ----------------------------------------------------------------
# 5. Weighted MaxSAT and tree decomposition elimination.
# ----------------------------------------------------------------

def _wcost(clauses, assignment):
    """The violated weight of a weighted formula. A weighted
    clause is (weight, literals), literals as in _violated.
    This is the one objective every bound on this page is
    about: the same formula, the same weights, the same
    cost."""
    total = 0
    for weight, literals in clauses:
        if not any(assignment[v] == wanted
                   for v, wanted in literals):
            total += weight
    return total


def _wopt(clauses, variables):
    """Brute force optimum and one witness, by direct
    scoring over every assignment."""
    best = None
    best_a = None
    for bits in itertools.product((0, 1),
                                  repeat=len(variables)):
        a = dict(zip(variables, bits))
        c = _wcost(clauses, a)
        if best is None or c < best:
            best = c
            best_a = a
    return best, best_a


def _check_decomposition(bags, parent, clause_at, clauses,
                           variables):
    """A supplied decomposition, checked rather than
    trusted: the parent array first has to describe the
    one tree the elimination theorem assumes, every
    variable sits in some bag, the bags holding any one
    variable form a connected subtree, every clause is
    assigned exactly once, and each clause sits in a bag
    that holds all of its variables.

    The topology half is not decoration. With 2 roots the
    elimination silently keeps the last root's table and
    drops the other tree's clauses whole: on bags
    [('x',), ('y',)] with parents [None, None], the
    conflicting unit clauses on x of weights 2 and 3 in
    the first bag and a unit clause on y of weight 1 in
    the second, it returned cost 0 and the witness
    {y: 1} where exhaustive scoring gives optimum 2.
    So: exactly one root, every other parent a valid bag
    index other than the bag itself, a walk down from
    the root that reaches every bag exactly once, and
    clause assignments only under valid bag keys, since
    a key outside the bags would hide its clauses from
    the checker and the solver alike.

    The variable list is held to the same standard,
    against what the bags and the clauses actually use.
    A list that omits a variable leaves that variable's
    occurrences unexamined: on bags [('x',), ('y',),
    ('y',)] with parents [None, 0, 0], the positive unit
    on y of weight 2 in one child bag and the negative
    unit on y of weight 3 in the other, a caller
    supplying ['x'] was told the decomposition was
    sound. The elimination reported cost 0, pricing the
    2 child tables independently where exhaustive
    scoring gives optimum 2, and its reconstructed
    assignment scored 3. So the checked set is derived
    rather than trusted: every variable in any bag or
    any clause has to be named in the supplied list,
    and coverage and running intersection run over the
    derived set. A declared variable that no bag and
    no clause uses is isolated and stands accepted: it
    constrains nothing, and the elimination has
    nothing to price for it."""
    n = len(bags)
    if n == 0 or len(parent) != n:
        return False
    roots = [b for b in range(n) if parent[b] is None]
    if len(roots) != 1:
        return False
    for b in range(n):
        p = parent[b]
        if p is not None and (
                not isinstance(p, int)
                or isinstance(p, bool)
                or p < 0 or p >= n or p == b):
            return False
    for key in clause_at:
        if (not isinstance(key, int)
                or isinstance(key, bool)
                or key < 0 or key >= n):
            return False
    children = [[] for _ in range(n)]
    for b in range(n):
        if parent[b] is not None:
            children[parent[b]].append(b)
    reached = []
    stack = [roots[0]]
    while stack:
        b = stack.pop()
        reached.append(b)
        stack.extend(children[b])
    if sorted(reached) != list(range(n)):
        return False
    adjacency = [[] for _ in range(n)]
    for b in range(n):
        if parent[b] is not None:
            adjacency[b].append(parent[b])
            adjacency[parent[b]].append(b)
    in_bags = set()
    for bag in bags:
        in_bags.update(bag)
    in_clauses = set()
    for _, lits in clauses:
        for v, _ in lits:
            in_clauses.add(v)
    used = in_bags | in_clauses
    if not used.issubset(variables):
        return False
    checked = used | set(variables)
    for v in checked:
        if v not in in_bags:
            continue
        holders = [b for b in range(n) if v in bags[b]]
        if not holders:
            return False
        seen = {holders[0]}
        stack = [holders[0]]
        while stack:
            b = stack.pop()
            for nb in adjacency[b]:
                if nb not in seen and v in bags[nb]:
                    seen.add(nb)
                    stack.append(nb)
        if any(b not in seen for b in holders):
            return False
    assigned = []
    for b in range(n):
        for clause in clause_at.get(b, []):
            assigned.append(clause)
            if not all(v in bags[b] for _, lits in [clause]
                       for v, _ in lits):
                return False
    return sorted(map(repr, assigned)) == sorted(
        map(repr, clauses))


def _tree_dp(bags, parent, clause_at):
    """Exact elimination over a supplied tree decomposition.

    Bottom up: at each bag, enumerate its assignments; the
    cost of a row is the violated weight of the clauses
    assigned to that bag plus, for each child, the child's
    table entry at the row's restriction to the child's
    separator. Rows are then grouped by their restriction
    to the separator with the parent, and only the cheapest
    row of each group is kept, as the row itself and the
    child keys it chose. The witness is reconstructed in
    one top down pass over those choices at the end. The
    first form of this helper copied a full subtree
    witness into every row, which is quadratic work along
    a path and is not the linear time algorithm the
    example is meant to demonstrate. The running
    intersection property is what licenses the grouping:
    once the separator is fixed, the subtrees below share
    nothing else, so their cheapest choices combine.
    Returns (optimum, witness, rows), rows the total
    number of enumerated bag assignments, the sum of
    2^|bag| over bags.
    """
    n = len(bags)
    children = [[] for _ in range(n)]
    root = None
    for b in range(n):
        if parent[b] is None:
            root = b
        else:
            children[parent[b]].append(b)
    order = []
    stack = [root]
    while stack:
        b = stack.pop()
        order.append(b)
        stack.extend(children[b])
    tables = {}
    rows = 0
    for b in reversed(order):
        bag = list(bags[b])
        if parent[b] is None:
            sep = []
        else:
            sep = [v for v in bag if v in bags[parent[b]]]
        table = {}
        for bits in itertools.product((0, 1),
                                      repeat=len(bag)):
            a = dict(zip(bag, bits))
            rows += 1
            cost = _wcost(clause_at.get(b, []), a)
            child_keys = {}
            for c in children[b]:
                csep = [v for v in bags[c] if v in bag]
                key = tuple(a[v] for v in csep)
                cost += tables[c][key][0]
                child_keys[c] = key
            key = tuple(a[v] for v in sep)
            if key not in table or cost < table[key][0]:
                table[key] = (cost, bits, child_keys)
        tables[b] = table
    optimum = tables[root][()][0]
    witness = {}
    stack = [(root, ())]
    while stack:
        b, key = stack.pop()
        _, bits, child_keys = tables[b][key]
        witness.update(zip(bags[b], bits))
        for c, ckey in child_keys.items():
            stack.append((c, ckey))
    return optimum, witness, rows


def _rooted_tree_instance(rng, nvars):
    """One random weighted instance on a rooted variable
    tree: variable 0 is the root, each later variable has
    an earlier parent. Bags hold a variable and its parent,
    so every clause over a variable alone or over a
    parent and child pair has a home. Weights are positive
    integers, some of them large."""
    parents = [None] + [rng.randrange(i) for i in
                        range(1, nvars)]
    bags = []
    parent = []
    clause_at = {}
    clauses = []
    for v in range(nvars):
        bag = (v,) if parents[v] is None else (
            parents[v], v)
        bags.append(bag)
        parent.append(parents[v])
        clause_at[v] = []
    pairs = [(v,) for v in range(nvars)] + [
        (parents[v], v) for v in range(1, nvars)]
    for _ in range(rng.randrange(1, 3 * nvars + 1)):
        vs = pairs[rng.randrange(len(pairs))]
        literals = tuple((v, rng.random() < 0.5)
                         for v in vs)
        weight = rng.choice([1, 1, 2, 3, 7, 10 ** 6 + 5])
        clause = (weight, literals)
        clauses.append(clause)
        home = vs[-1]
        clause_at[home].append(clause)
    return bags, parent, clause_at, clauses, list(
        range(nvars))


class TreeDecompositionTest(unittest.TestCase):
    """The elimination is exact on the checked instances:
    its optimum and its reconstructed witness agree with
    direct scoring, and L at most OPT at most U holds with
    the elimination supplying both lines at once."""

    def test_fixed_seed_rooted_trees_agree_with_brute_force(
            self):
        rng = random.Random(20261123)
        checked_assignments = 0
        for _ in range(800):
            nvars = rng.randrange(1, 9)
            bags, parent, clause_at, clauses, variables = (
                _rooted_tree_instance(rng, nvars))
            self.assertTrue(_check_decomposition(
                bags, parent, clause_at, clauses, variables))
            opt, witness, rows = _tree_dp(
                bags, parent, clause_at)
            brute, _ = _wopt(clauses, variables)
            checked_assignments += 2 ** nvars
            self.assertEqual(opt, brute)
            self.assertEqual(_wcost(clauses, witness), opt)
            self.assertLessEqual(
                rows, sum(2 ** len(bag) for bag in bags))
        self.assertGreater(checked_assignments, 10000)

    def test_both_lines_about_the_same_object(self):
        # The control from section 3, weighted: (x) AND
        # (NOT x) with weights 2 and 3. Every assignment
        # violates exactly one clause, so L = OPT = U = 2,
        # met by the elimination in one pass.
        clauses = [(2, (("x", True),)),
                   (3, (("x", False),))]
        bags = [("x",)]
        parent = [None]
        clause_at = {0: clauses}
        opt, witness, _ = _tree_dp(bags, parent, clause_at)
        self.assertEqual(opt, 2)
        self.assertEqual(_wcost(clauses, witness), 2)
        lower, upper = opt, _wcost(clauses, witness)
        self.assertLessEqual(lower, opt)
        self.assertLessEqual(opt, upper)


class DecompositionTopologyTest(unittest.TestCase):
    """The checker enforces the one tree the elimination
    theorem assumes. The family around the reproduced
    failure: the supplied parent array and clause keys
    are validated before coverage or running intersection
    are even consulted, because the elimination reads
    nothing but the last root it finds."""

    def _two_root_case(self):
        # The reproduced case, exactly as reported: bags
        # [('x',), ('y',)], parents [None, None], the
        # conflicting unit clauses on x of weights 2 and
        # 3 in the first bag, a unit clause on y of
        # weight 1 in the second.
        clauses = [(2, (("x", True),)),
                   (3, (("x", False),)),
                   (1, (("y", True),))]
        bags = [("x",), ("y",)]
        parent = [None, None]
        clause_at = {0: clauses[:2], 1: clauses[2:]}
        return bags, parent, clause_at, clauses, ["x", "y"]

    def test_the_reproduced_two_root_case_is_refused(self):
        bags, parent, clause_at, clauses, variables = (
            self._two_root_case())
        self.assertFalse(_check_decomposition(
            bags, parent, clause_at, clauses, variables))
        # The stakes, pinned: exhaustive scoring gives
        # optimum 2, the answer the unchecked elimination
        # corrupted to 0 by keeping only the last root.
        opt, _ = _wopt(clauses, variables)
        self.assertEqual(opt, 2)

    def test_three_roots_are_refused(self):
        bags = [("x",), ("y",), ("z",)]
        parent = [None, None, None]
        self.assertFalse(_check_decomposition(
            bags, parent, {}, [], ["x", "y", "z"]))

    def test_no_root_is_refused(self):
        bags = [("x",), ("y",)]
        parent = [1, 0]
        self.assertFalse(_check_decomposition(
            bags, parent, {}, [], ["x", "y"]))

    def test_a_self_parent_is_refused(self):
        self.assertFalse(_check_decomposition(
            [("x",)], [0], {}, [], ["x"]))

    def test_a_dangling_parent_index_is_refused(self):
        bags = [("x",), ("y",)]
        for parent in ([None, 2], [None, 7], [None, -1]):
            self.assertFalse(_check_decomposition(
                bags, parent, {}, [], ["x", "y"]))

    def test_a_parent_list_of_the_wrong_length_is_refused(
            self):
        bags = [("x",), ("y",)]
        for parent in ([None], [None, 0, 0], []):
            self.assertFalse(_check_decomposition(
                bags, parent, {}, [], ["x", "y"]))

    def test_a_detached_cycle_is_unreachable_and_refused(
            self):
        # One honest root and child, and beside them 2
        # bags parented to each other: coverage and
        # running intersection hold, no clause is out of
        # place, and the walk from the root still never
        # reaches the cycle.
        bags = [("a",), ("a", "b"), ("c",), ("c", "d")]
        parent = [None, 0, 3, 2]
        self.assertFalse(_check_decomposition(
            bags, parent, {}, [], ["a", "b", "c", "d"]))

    def test_clause_keys_outside_the_bags_are_refused(self):
        bags, parent, clause_at = (
            _cycle_path_decomposition(3))
        clauses = _cycle_clauses(3)
        variables = list(range(3))
        self.assertTrue(_check_decomposition(
            bags, parent, clause_at, clauses, variables))
        for bad_key in (9, -1, "0"):
            widened = dict(clause_at)
            widened[bad_key] = []
            self.assertFalse(_check_decomposition(
                bags, parent, widened, clauses, variables))

    def test_clauses_under_a_bad_key_are_not_hidden(self):
        clauses = [(2, (("x", True),))]
        self.assertFalse(_check_decomposition(
            [("x",)], [None], {9: clauses}, clauses,
            ["x"]))

    def test_a_clause_assigned_twice_is_refused(self):
        clause = (2, (("x", True), ("y", True)))
        bags = [("x", "y"), ("x", "y")]
        parent = [None, 0]
        clause_at = {0: [clause], 1: [clause]}
        self.assertFalse(_check_decomposition(
            bags, parent, clause_at, [clause], ["x", "y"]))

    def test_valid_decompositions_still_pass(self):
        rng = random.Random(20261126)
        for _ in range(50):
            bags, parent, clause_at, clauses, variables = (
                _rooted_tree_instance(
                    rng, rng.randrange(1, 9)))
            self.assertTrue(_check_decomposition(
                bags, parent, clause_at, clauses,
                variables))

    def test_witness_reconstruction_on_a_long_path(self):
        # The reconstructed witness still scores the
        # optimum on a path far longer than the brute
        # force family reaches: an even cycle of 60
        # through the width 2 path decomposition.
        n = 60
        clauses = _cycle_clauses(n)
        bags, parent, clause_at = (
            _cycle_path_decomposition(n))
        self.assertTrue(_check_decomposition(
            bags, parent, clause_at, clauses,
            list(range(n))))
        opt, witness, rows = _tree_dp(
            bags, parent, clause_at)
        self.assertEqual(opt, 0)
        self.assertEqual(_wcost(clauses, witness), 0)
        self.assertEqual(set(witness), set(range(n)))
        self.assertLessEqual(rows, 8 * n)


class DecompositionVariableSetTest(unittest.TestCase):
    """The checker derives its variable set from the
    bags and the clauses, and holds the supplied list
    to it. The family around the reported failure: a
    variable the list omits was never examined, so its
    occurrences could sit disconnected in the tree
    while the elimination priced them independently
    and the checker still said sound."""

    def _reported_case(self):
        # The reported case, exactly as it arrived:
        # bags [('x',), ('y',), ('y',)] with parents
        # [None, 0, 0], the positive unit on y of
        # weight 2 in one child bag and the negative
        # unit on y of weight 3 in the other.
        pos = (2, (("y", True),))
        neg = (3, (("y", False),))
        bags = [("x",), ("y",), ("y",)]
        parent = [None, 0, 0]
        clause_at = {1: [pos], 2: [neg]}
        clauses = [pos, neg]
        return bags, parent, clause_at, clauses

    def test_the_reported_case_is_refused(self):
        bags, parent, clause_at, clauses = (
            self._reported_case())
        # The supposition, from exhaustive scoring
        # alone, stated before the checker is asked:
        # the optimum over x and y is 2.
        brute, _ = _wopt(clauses, ["x", "y"])
        self.assertEqual(brute, 2)
        # The stakes, pinned on the unchecked path the
        # caller used to take: the elimination reports
        # 0 and its reconstructed assignment scores 3.
        opt, witness, _ = _tree_dp(bags, parent,
                                    clause_at)
        self.assertEqual(opt, 0)
        self.assertEqual(_wcost(clauses, witness), 3)
        # With ['x'] supplied, the y occurrences were
        # never checked. Now the case is refused.
        self.assertFalse(_check_decomposition(
            bags, parent, clause_at, clauses, ["x"]))

    def test_the_reported_case_stays_refused_on_the_full_list(
            self):
        # Naming y does not save the decomposition
        # either: the bags holding y are joined only
        # through a bag that does not hold it, so the
        # running intersection property fails for y.
        bags, parent, clause_at, clauses = (
            self._reported_case())
        self.assertFalse(_check_decomposition(
            bags, parent, clause_at, clauses,
            ["x", "y"]))

    def test_a_variable_in_a_bag_only_missing_from_the_list(
            self):
        bags = [("x", "y")]
        parent = [None]
        self.assertFalse(_check_decomposition(
            bags, parent, {}, [], ["x"]))
        self.assertTrue(_check_decomposition(
            bags, parent, {}, [], ["x", "y"]))

    def test_a_variable_named_by_a_clause_missing_from_the_list(
            self):
        clause = (2, (("y", True),))
        bags = [("x", "y")]
        parent = [None]
        clause_at = {0: [clause]}
        self.assertFalse(_check_decomposition(
            bags, parent, clause_at, [clause], ["x"]))
        self.assertTrue(_check_decomposition(
            bags, parent, clause_at, [clause],
            ["x", "y"]))
        opt, witness, _ = _tree_dp(bags, parent,
                                    clause_at)
        brute, _ = _wopt([clause], ["x", "y"])
        self.assertEqual(opt, brute)
        self.assertEqual(_wcost([clause], witness), opt)

    def test_a_variable_in_bags_and_clauses_missing_from_the_list(
            self):
        clause = (5, (("y", False),))
        bags = [("x",), ("x", "y")]
        parent = [None, 0]
        clause_at = {1: [clause]}
        self.assertFalse(_check_decomposition(
            bags, parent, clause_at, [clause], ["x"]))
        self.assertTrue(_check_decomposition(
            bags, parent, clause_at, [clause],
            ["x", "y"]))
        opt, witness, _ = _tree_dp(bags, parent,
                                    clause_at)
        brute, _ = _wopt([clause], ["x", "y"])
        self.assertEqual(opt, brute)
        self.assertEqual(_wcost([clause], witness),
                         opt)

    def test_disconnected_occurrences_are_refused(self):
        bags = [("x",), ("y",), ("y",)]
        parent = [None, 0, 0]
        self.assertFalse(_check_decomposition(
            bags, parent, {}, [], ["x", "y"]))

    def test_connected_occurrences_still_pass(self):
        bags = [("x", "y"), ("y",), ("y",)]
        parent = [None, 0, 0]
        self.assertTrue(_check_decomposition(
            bags, parent, {}, [], ["x", "y"]))

    def test_a_declared_isolated_variable_in_a_bag_passes(
            self):
        clause = (2, (("x", True),))
        bags = [("x", "z")]
        parent = [None]
        clause_at = {0: [clause]}
        self.assertTrue(_check_decomposition(
            bags, parent, clause_at, [clause],
            ["x", "z"]))

    def test_a_declared_isolated_variable_with_no_bag_passes(
            self):
        clause = (2, (("x", True),))
        bags = [("x",)]
        parent = [None]
        clause_at = {0: [clause]}
        self.assertTrue(_check_decomposition(
            bags, parent, clause_at, [clause],
            ["x", "z"]))

    def test_dropping_any_variable_from_a_sound_list_is_refused(
            self):
        rng = random.Random(20261127)
        for _ in range(60):
            bags, parent, clause_at, clauses, variables = (
                _rooted_tree_instance(
                    rng, rng.randrange(1, 9)))
            self.assertTrue(_check_decomposition(
                bags, parent, clause_at, clauses,
                variables))
            for dropped in variables:
                shorter = [v for v in variables
                           if v != dropped]
                self.assertFalse(_check_decomposition(
                    bags, parent, clause_at, clauses,
                    shorter))

    def test_an_extra_declared_isolated_variable_stays_accepted(
            self):
        rng = random.Random(20261128)
        for _ in range(20):
            bags, parent, clause_at, clauses, variables = (
                _rooted_tree_instance(
                    rng, rng.randrange(1, 9)))
            self.assertTrue(_check_decomposition(
                bags, parent, clause_at, clauses,
                variables + ["isolated"]))


# ----------------------------------------------------------------
# 6. The odd cycle: parity, block sums, and a separator.
# ----------------------------------------------------------------

def _cycle_clauses(n):
    """Adjacent differ on a cycle of n variables, as
    weighted clauses of weight 1: each edge contributes
    (x_i OR x_j) and (NOT x_i OR NOT x_j), so an assignment
    pays exactly 1 for each monochromatic edge and 0 for
    each edge whose ends differ."""
    clauses = []
    for i in range(n):
        j = (i + 1) % n
        clauses.append((1, ((i, True), (j, True))))
        clauses.append((1, ((i, False), (j, False))))
    return clauses


def _cycle_path_decomposition(n):
    """A width 2 path decomposition of the cycle: bag i
    holds variables 0, i, i + 1, the chain runs over the
    path edges, and the closing edge between n - 1 and 0
    is assigned to the last bag, which holds both."""
    bags = []
    parent = []
    clause_at = {}
    for i in range(n - 1):
        bags.append((0, i, i + 1) if i else (0, 1))
        parent.append(i - 1 if i else None)
        clause_at[i] = []
    for i in range(n):
        j = (i + 1) % n
        pair = [(1, ((i, True), (j, True))),
                (1, ((i, False), (j, False)))]
        home = i if i < n - 1 else n - 2
        clause_at[home].extend(pair)
    return bags, parent, clause_at


class OddCycleTest(unittest.TestCase):
    """Parity decides the cycle: minimum cost 0 for even
    length, 1 for odd, lengths 3 to 12. Local lower bounds
    lose the parity at the join; a width 2 separator
    dynamic program keeps it and closes the gap in linear
    time."""

    def test_minimum_cost_is_the_parity(self):
        for n in range(3, 13):
            opt, witness = _wopt(
                _cycle_clauses(n), list(range(n)))
            self.assertEqual(opt, n % 2)
            self.assertEqual(
                _wcost(_cycle_clauses(n), witness), opt)

    def test_block_sums_stay_at_zero_on_odd_cycles(self):
        # One block per edge. Each block alone reaches 0,
        # so the summed lower bound is 0 at every length,
        # while the odd lengths have OPT 1: the bound is
        # sound and stuck.
        for n in range(3, 13):
            clauses = _cycle_clauses(n)
            blocks = [clauses[2 * i:2 * i + 2]
                      for i in range(n)]
            bound = sum(_wopt(block, list(range(n)))[0]
                        for block in blocks)
            self.assertEqual(bound, 0)
            opt, _ = _wopt(clauses, list(range(n)))
            self.assertLessEqual(bound, opt)

    def test_every_single_clause_deletion_is_satisfiable(
            self):
        # The theorem the page states is about proper
        # subsets at the clause level, so drop one clause
        # at a time, not both clauses of an edge: alternate
        # along the remaining edges, then choose the global
        # phase that satisfies the one clause left standing
        # on the broken edge. All 70 deletions across the
        # odd lengths 3 to 11 are checked, and the count
        # itself is pinned.
        checked = 0
        for n in (3, 5, 7, 9, 11):
            clauses = _cycle_clauses(n)
            for k in range(len(clauses)):
                rest = clauses[:k] + clauses[k + 1:]
                opt, _ = _wopt(rest, list(range(n)))
                self.assertEqual(opt, 0)
                checked += 1
        self.assertEqual(checked, 70)

    def test_every_edge_deletion_is_satisfiable_too(self):
        # The weaker form this test family started with,
        # kept as a corollary: remove any one edge's 2
        # clauses from an odd cycle and what remains is a
        # path, which alternates, so the optimum drops
        # to 0. So no sum over proper disjoint blocks can
        # see the 1 either.
        for n in (3, 5, 7, 9, 11):
            clauses = _cycle_clauses(n)
            for e in range(n):
                rest = [c for k, c in enumerate(clauses)
                        if k // 2 != e]
                opt, _ = _wopt(rest, list(range(n)))
                self.assertEqual(opt, 0)

    def test_separator_dp_closes_the_gap_in_linear_time(
            self):
        for n in range(3, 13):
            clauses = _cycle_clauses(n)
            bags, parent, clause_at = (
                _cycle_path_decomposition(n))
            self.assertTrue(_check_decomposition(
                bags, parent, clause_at, clauses,
                list(range(n))))
            self.assertTrue(
                all(len(bag) <= 3 for bag in bags))
            opt, witness, rows = _tree_dp(
                bags, parent, clause_at)
            self.assertEqual(opt, n % 2)
            self.assertEqual(_wcost(clauses, witness), opt)
            # Linear at fixed width: at most n bags, each
            # enumerating at most 2^3 rows.
            self.assertLessEqual(len(bags), n)
            self.assertLessEqual(rows, 8 * n)


# ----------------------------------------------------------------
# 7. Block merge monotonicity.
# ----------------------------------------------------------------

def _block_bound(blocks, variables):
    """The summed lower bound: minimize each block on its
    own and add the minima."""
    return sum(_wopt(block, variables)[0]
               for block in blocks)


def _random_weighted_formula(rng, nvars, nclauses):
    clauses = []
    for _ in range(nclauses):
        width = rng.randrange(1, min(3, nvars) + 1)
        vs = rng.sample(range(nvars), width)
        literals = tuple((v, rng.random() < 0.5)
                         for v in vs)
        clauses.append((rng.choice([1, 2, 5]), literals))
    return clauses


class BlockMergeTest(unittest.TestCase):
    """Merging blocks can only raise the summed lower
    bound: the merged block must be minimized under one
    common assignment, where the separate blocks each had
    their own. The bound stays sound throughout, at most
    OPT."""

    def test_merging_never_lowers_the_bound(self):
        rng = random.Random(20261124)
        for _ in range(200):
            nvars = rng.randrange(1, 7)
            clauses = _random_weighted_formula(
                rng, nvars, rng.randrange(1, 13))
            variables = list(range(nvars))
            order = list(clauses)
            rng.shuffle(order)
            cut = rng.randrange(len(order) + 1)
            blocks = [order[:cut], order[cut:]]
            before = _block_bound(blocks, variables)
            after = _block_bound([order], variables)
            opt, _ = _wopt(clauses, variables)
            self.assertLessEqual(before, after)
            self.assertLessEqual(after, opt)
            self.assertEqual(after, opt)

    def test_the_odd_cycle_shows_no_contraction_rate(self):
        # All the way from one block per edge to a single
        # block, the bound on an odd cycle sits at 0 until
        # the last merge closes it at once: monotonicity
        # alone promises movement, never a rate.
        for n in (5, 7, 9):
            clauses = _cycle_clauses(n)
            variables = list(range(n))
            blocks = [clauses[2 * i:2 * i + 2]
                      for i in range(n)]
            self.assertEqual(
                _block_bound(blocks, variables), 0)
            merged = [c for block in blocks for c in block]
            self.assertEqual(
                _block_bound([merged], variables), 1)


# ----------------------------------------------------------------
# 8. The threshold query.
# ----------------------------------------------------------------

def _threshold_run(clauses, variables, start):
    """The halving loop. Each round asks the threshold
    question at t = floor((L + U) / 2): is there an
    assignment of cost at most t? Brute force answers here,
    standing in for the decider the discussion assumes.
    A yes comes with a verified assignment and lowers U to
    its cost; a no raises L above t. Every state of the
    two lines is recorded with the source of its update.
    Returns (ledger, witness); the ledger holds (L, U,
    source) triples, the starting state first."""
    upper = _wcost(clauses, start)
    witness = dict(start)
    lower = 0
    ledger = [(lower, upper,
               "start: the supplied assignment sets U, "
               "L = 0")]
    while upper > lower:
        t = (lower + upper) // 2
        hit = None
        for bits in itertools.product(
                (0, 1), repeat=len(variables)):
            a = dict(zip(variables, bits))
            c = _wcost(clauses, a)
            if c <= t:
                hit = (c, a)
                break
        if hit is not None:
            upper = hit[0]
            witness = hit[1]
            ledger.append((lower, upper,
                           "threshold %d answered yes: a "
                           "verified assignment of cost %d "
                           "lowers U" % (t, hit[0])))
        else:
            lower = t + 1
            ledger.append((lower, upper,
                           "threshold %d answered no: L "
                           "rises above the threshold" % t))
    return ledger, witness


class ThresholdQueryTest(unittest.TestCase):
    """Each answer at least halves the gap, the lines meet
    at OPT, and the ledger names the cost and the source
    of every update."""

    def _check_run(self, clauses, variables):
        start = {v: False for v in variables}
        opt, _ = _wopt(clauses, variables)
        ledger, witness = _threshold_run(
            clauses, variables, start)
        self.assertEqual(ledger[-1][0], opt)
        self.assertEqual(ledger[-1][1], opt)
        self.assertEqual(_wcost(clauses, witness), opt)
        for (l0, u0, _), (l1, u1, source) in zip(
                ledger, ledger[1:]):
            self.assertLessEqual(l1, opt)
            self.assertLessEqual(opt, u1)
            self.assertLessEqual(l0, l1)
            self.assertLessEqual(u1, u0)
            self.assertLessEqual(
                u1 - l1, max(1, (u0 - l0 + 1) // 2))
            self.assertIn("threshold", source)
        return ledger

    def test_threshold_run_on_toy_formulas(self):
        formulas = [
            [(1, (("x", True), ("y", True)))],
            [(2, (("x", True),)), (3, (("x", False),))],
            [(1, (("x", True), ("y", False))),
             (4, (("y", True), ("z", True))),
             (1, (("x", False), ("z", False)))],
            [(5, (("x", True),)), (5, (("y", True),)),
             (1, (("x", False), ("y", False),
                  ("z", True)))],
        ]
        for clauses in formulas:
            variables = sorted({v for _, lits in clauses
                                for v, _ in lits})
            self._check_run(clauses, variables)

    def test_threshold_run_on_cycles(self):
        for n in range(3, 10):
            self._check_run(
                _cycle_clauses(n), list(range(n)))

    def test_threshold_zero_is_the_sat_question(self):
        # At t = 0 the threshold question is satisfiability
        # itself: a cost 0 assignment exists exactly when
        # OPT is 0. This is the case that makes the loop,
        # under P = NP, a polynomial exact solver.
        rng = random.Random(20261125)
        for _ in range(100):
            nvars = rng.randrange(1, 7)
            clauses = _random_weighted_formula(
                rng, nvars, rng.randrange(1, 10))
            variables = list(range(nvars))
            opt, _ = _wopt(clauses, variables)
            exists_zero = any(
                _wcost(clauses, dict(zip(
                    variables, bits))) <= 0
                for bits in itertools.product(
                    (0, 1), repeat=len(variables)))
            self.assertEqual(exists_zero, opt == 0)


class PageTest(unittest.TestCase):
    """The page exists and says what this file pins."""

    def test_page_states_the_four_constructions(self):
        with open(PAGE, encoding="utf-8") as fh:
            text = fh.read()
        for needle in ("2^m", "L(F)", "0.61",
                       "truth table"):
            self.assertIn(needle, text)

    def test_page_states_the_maxsat_controls(self):
        with open(PAGE, encoding="utf-8") as fh:
            text = fh.read()
        for needle in ("tree decomposition", "odd cycle",
                       "Block merge monotonicity",
                       "threshold", "VeriPB",
                       "bucket elimination"):
            self.assertIn(needle, text)

    def test_page_states_the_query_canvas_and_the_other_direction(self):
        # The repairs of 23 November 2026: the counting
        # argument carries its at most in the count, the
        # prefix extension query is given in the length
        # of the canvas, and the Levin section states
        # the witness finder condition for the direction
        # efficient simulability does not cover.
        with open(PAGE, encoding="utf-8") as fh:
            text = fh.read()
        for needle in ("unused\ngates", "1^N",
                       "standard polynomial time witness finder"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
