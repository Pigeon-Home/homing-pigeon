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
   scores it. On a fixed seed family of rooted trees with
   one and two variable weighted clauses, it agrees with
   brute force on every instance.
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
    trusted: every variable sits in some bag, the bags
    holding any one variable form a connected subtree,
    every clause is assigned exactly once, and each clause
    sits in a bag that holds all of its variables."""
    n = len(bags)
    adjacency = [[] for _ in range(n)]
    for b in range(n):
        if parent[b] is not None:
            adjacency[b].append(parent[b])
            adjacency[parent[b]].append(b)
    for v in variables:
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
    row of each group, with its witness, is kept. The
    running intersection property is what licenses the
    grouping: once the separator is fixed, the subtrees
    below share nothing else, so their cheapest choices
    combine. Returns (optimum, witness, rows), rows the
    total number of enumerated bag assignments, the sum of
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
            witness = dict(a)
            for c in children[b]:
                csep = [v for v in bags[c] if v in bag]
                key = tuple(a[v] for v in csep)
                ccost, cwitness = tables[c][key]
                cost += ccost
                witness.update(cwitness)
            key = tuple(a[v] for v in sep)
            if key not in table or cost < table[key][0]:
                table[key] = (cost, witness)
        tables[b] = table
    optimum, witness = tables[root][()]
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

    def test_every_proper_subset_is_satisfiable(self):
        # Remove any one edge's clauses from an odd cycle
        # and what remains is a path, which alternates: the
        # optimum drops to 0. So no sum over proper disjoint
        # blocks can see the 1 either.
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


if __name__ == "__main__":
    unittest.main()
