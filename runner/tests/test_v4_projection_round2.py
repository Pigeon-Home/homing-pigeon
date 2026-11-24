#!/usr/bin/env python3
"""The propagation hierarchy claims: a second refutation attempt.

docs/infrastructure-documents/proofs/v4-projection-round2-review-2026-11-23.md
records an independent review of the extension email of
23 November 2026 (relayed in ComChat at 8:43 PM): a
universal 2m clause floor, an exact auxiliary price for
plain unit propagation, the minimum clause budget forcing
the linear auxiliary count at width three, one parallel
failed literal pass on the compact selector grid, and a
hierarchy tradeoff over iterated failed literal levels.
This file pins the finite checks of that review, attacks
B1 to B6 of the review page. The constructions are
rebuilt from the statements and from the fixed width
page, in the mask layout of test_v4_projection_width.py:
a_i at i, b_i at m + i, z at 2m, auxiliaries after. A
clause is (pos, neg): masks of the variables appearing
positively and negatively.

B1. Propagation completeness against exact entailment,
under partial assignments that may assign auxiliaries:
the original chain on every partial assignment of all
its variables for m = 1 and m = 2, and for m = 3 on
assignments fixing at least 11 of its 13 variables; the
block chain on every partial assignment of all its
variables for m = 1 to m = 3, and for m = 4 on
assignments fixing at least 7 of its 11 variables. The
cyclic example of the fixed width page is the negative
control: propagation must miss the implied literal.

B2. The selector grid under plain unit propagation on
minimal forbidden patterns: every pattern for m = 2 to
m = 8; at m = 30 and m = 256, the all a, all b and both
alternating patterns and 2,000 patterns drawn at random
with a fixed seed. Propagation must derive no conflict
and no literal at all.

B3. The one round failed literal procedure of the
review page, compared against exact entailment on every
visible partial assignment for m = 1 to m = 4 (22,140
assignments in total), and on the three named cases at
m = 256: a minimal forbidden pattern, a case forcing z,
and a case forcing both bits of one pair false.

B4. The clause floor's finite pins: the witness count
of every negative pair literal pattern a clause can
carry, for m = 1 to m = 5, with maximum exactly
2^(m - 1), attained only at one negated bit in one pair
or one negated bit in each of two pairs; and an
exhaustive subset search over arbitrary CNF clauses of
width at most three over the visible variables alone at
m = 2, no auxiliaries: no encoding with at most 3
clauses, and the block construction's 4 clauses encode.

B5. The equality case of the floor and the auxiliary
price: the block construction at m = 3 to m = 6 has
exactly 2m clauses and m - 2 auxiliaries; and at m = 3,
under each minimal forbidden pattern, the residual
formula over the auxiliaries has a minimal
unsatisfiable core containing a unit clause, and unit
propagation refutes the residual.

B6. The hierarchy arithmetic: the least k with 3 times
the leaf sum sum of binom(k, i) for i from 0 to h at
least m + 1, and the least k the capacity side of the
first review allows, for m = 256 and m = 1,000,000 at
h = 1, 2, 3; and the d = 3 upper bound construction at
width four, rebuilt from the statement, projecting
exactly onto R_m for m = 1 to m = 6.

The arguments are the email's, recorded in the review
page. What is tested is the finite enumeration those
arguments rest on.
"""
import itertools
import math
import os
import random
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
PROOFS = os.path.join(ROOT, "docs", "infrastructure-documents",
                      "proofs")


def _popcnt(x):
    return bin(x).count("1")


def _in_R(vis, m):
    every_pair = all((vis >> i) & 1 or (vis >> (m + i)) & 1
                     for i in range(m))
    z = (vis >> (2 * m)) & 1
    return not (every_pair and not z)


def _satisfies(clauses, bits):
    for pos, neg in clauses:
        if (bits & pos) == 0 and (bits & neg) == neg:
            return False
    return True


def _projection(clauses, nvis, ntot):
    out = set()
    for vis in range(1 << nvis):
        for rest in range(1 << (ntot - nvis)):
            if _satisfies(clauses, vis | (rest << nvis)):
                out.add(vis)
                break
    return out


def _R_set(m):
    return {v for v in range(1 << (2 * m + 1)) if _in_R(v, m)}


# ----------------------------------------------------------------
# Constructions, rebuilt from the statements and from the
# fixed width page.
# ----------------------------------------------------------------

def _block_construction(m):
    """Width three Horn: the first two pairs meet in one
    flag, each later pair advances it, the last pair heads
    z. 2m clauses, max(0, m - 2) flags."""
    def a(i):
        return 1 << i

    def b(i):
        return 1 << (m + i)

    z = 1 << (2 * m)

    def s(j):
        return 1 << (2 * m + j)

    clauses = []
    if m == 1:
        return [(z, a(0)), (z, b(0))], 0
    if m == 2:
        for u in (a(0), b(0)):
            for v in (a(1), b(1)):
                clauses.append((z, u | v))
        return clauses, 0
    for u in (a(0), b(0)):
        for v in (a(1), b(1)):
            clauses.append((s(1), u | v))
    for i in range(2, m):
        prev = s(i - 1)
        head = s(i) if i < m - 1 else z
        clauses.append((head, prev | a(i)))
        clauses.append((head, prev | b(i)))
    return clauses, m - 2


def _chain_construction(m):
    """The landed chain of the projection page."""
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
    return clauses, 2 * m


def _selector_construction(m):
    """Arbitrary CNF width three: 2 groups of n selectors,
    n least with n^2 >= m + 1, an OR chain per group, n^2
    blocking clauses carrying the m pairs and z. Returns
    the clauses, the auxiliary count, n, and the selector
    variable indices of the two groups."""
    n = math.ceil(math.sqrt(m + 1))
    while n * n < m + 1:
        n += 1
    while (n - 1) * (n - 1) >= m + 1:
        n -= 1

    def a(i):
        return 1 << i

    def b(i):
        return 1 << (m + i)

    z = 1 << (2 * m)
    base = 2 * m + 1

    def sel(g, j):
        return 1 << (base + g * n + j)

    def chain(g, j):
        return 1 << (base + 2 * n + g * max(0, n - 3) + (j - 1))

    clauses = []
    for g in range(2):
        if n == 2:
            clauses.append((sel(g, 0) | sel(g, 1), 0))
        elif n == 3:
            clauses.append((sel(g, 0) | sel(g, 1) | sel(g, 2), 0))
        else:
            clauses.append((sel(g, 0) | sel(g, 1) | chain(g, 1), 0))
            for j in range(1, n - 3):
                clauses.append((sel(g, j + 1) | chain(g, j + 1),
                                chain(g, j)))
            clauses.append((sel(g, n - 2) | sel(g, n - 1),
                            chain(g, n - 3)))
    items = [("pair", i) for i in range(m)] + [("z", None)]
    blockers = [(j0, j1) for j0 in range(n) for j1 in range(n)]
    for t, (j0, j1) in enumerate(blockers):
        neg = sel(0, j0) | sel(1, j1)
        if t >= len(items):
            clauses.append((0, neg))
            continue
        kind, i = items[t]
        if kind == "z":
            clauses.append((z, neg))
        else:
            clauses.append((0, neg | a(i)))
            clauses.append((0, neg | b(i)))
    selectors = [base + g * n + j for g in range(2)
                 for j in range(n)]
    return clauses, 2 * n + 2 * max(0, n - 3), n, selectors


def _three_group_construction(m):
    """The d = 3 upper bound construction of the hierarchy
    claim, at width four: three selector groups of n
    selectors each, n least with n^3 >= m + 1, one OR
    clause per group, and one cell per selector triple,
    carrying a pair, z, or nothing (a padding cell)."""
    n = 1
    while n ** 3 < m + 1:
        n += 1

    def a(i):
        return 1 << i

    def b(i):
        return 1 << (m + i)

    z = 1 << (2 * m)
    base = 2 * m + 1

    def sel(g, j):
        return 1 << (base + g * n + j)

    clauses = []
    for g in range(3):
        pos = 0
        for j in range(n):
            pos |= sel(g, j)
        clauses.append((pos, 0))
    items = [("pair", i) for i in range(m)] + [("z", None)]
    triples = [(j0, j1, j2) for j0 in range(n)
               for j1 in range(n) for j2 in range(n)]
    for t, (j0, j1, j2) in enumerate(triples):
        neg = sel(0, j0) | sel(1, j1) | sel(2, j2)
        if t >= len(items):
            clauses.append((0, neg))
            continue
        kind, i = items[t]
        if kind == "z":
            clauses.append((z, neg))
        else:
            clauses.append((0, neg | a(i)))
            clauses.append((0, neg | b(i)))
    return clauses, 3 * n, n


# ----------------------------------------------------------------
# Unit propagation and entailment.
# ----------------------------------------------------------------

def _up(clauses, assigned, value):
    while True:
        changed = False
        for pos, neg in clauses:
            if (value & pos) or (assigned & ~value & neg):
                continue
            un = (pos | neg) & ~assigned
            if un == 0:
                return True, assigned, value
            if un & (un - 1) == 0:
                if un & pos:
                    value |= un
                assigned |= un
                changed = True
        if not changed:
            return False, assigned, value


def _entailment(clauses, assigned, value, ntot):
    free = [j for j in range(ntot) if not (assigned >> j) & 1]
    and_mask = (1 << ntot) - 1
    or_mask = 0
    sat = False
    for combo in range(1 << len(free)):
        bits = value
        for t, j in enumerate(free):
            if (combo >> t) & 1:
                bits |= 1 << j
        if _satisfies(clauses, bits):
            sat = True
            and_mask &= bits
            or_mask |= bits
    if not sat:
        return False, {}
    implied = {}
    for j in range(ntot):
        if (and_mask >> j) & 1:
            implied[j] = 1
        elif not (or_mask >> j) & 1:
            implied[j] = 0
    return True, implied


class _ModelIndex:
    """The satisfying total assignments of a formula, held
    as bitsets over the model list, so entailment under a
    partial assignment is a handful of mask intersections
    even over hundreds of thousands of assignments."""

    def __init__(self, clauses, ntot):
        self.ntot = ntot
        self.models = [bits for bits in range(1 << ntot)
                       if _satisfies(clauses, bits)]
        self.full = (1 << len(self.models)) - 1
        self.is_one = []
        for j in range(ntot):
            mask = 0
            for t, bits in enumerate(self.models):
                if (bits >> j) & 1:
                    mask |= 1 << t
            self.is_one.append(mask)

    def entailment(self, assigned, value):
        mask = self.full
        for j in range(self.ntot):
            if (assigned >> j) & 1:
                if (value >> j) & 1:
                    mask &= self.is_one[j]
                else:
                    mask &= self.full ^ self.is_one[j]
                if mask == 0:
                    return False, {}
        if mask == 0:
            return False, {}
        implied = {}
        for j in range(self.ntot):
            if mask & (self.full ^ self.is_one[j]) == 0:
                implied[j] = 1
            elif mask & self.is_one[j] == 0:
                implied[j] = 0
        return True, implied


def _all_partial(nvars):
    for spec in itertools.product((0, 1, 2), repeat=nvars):
        assigned = 0
        value = 0
        for j, s in enumerate(spec):
            if s:
                assigned |= 1 << j
                if s == 2:
                    value |= 1 << j
        yield assigned, value


def _partial_min_assigned(nvars, min_assigned):
    """Every partial assignment fixing at least min_assigned
    of nvars variables, generated by choosing the free set
    (at most nvars - min_assigned variables) directly."""
    max_free = nvars - min_assigned
    for nfree in range(0, max_free + 1):
        for free in itertools.combinations(range(nvars), nfree):
            free_mask = 0
            for j in free:
                free_mask |= 1 << j
            fixed = [j for j in range(nvars)
                     if not (free_mask >> j) & 1]
            for combo in range(1 << len(fixed)):
                assigned = 0
                value = 0
                for t, j in enumerate(fixed):
                    assigned |= 1 << j
                    if (combo >> t) & 1:
                        value |= 1 << j
                yield assigned, value


def _check_propagation_index(test, clauses, ntot, alphas):
    """Unit propagation against exact entailment from the
    model index, on every variable. Returns the number of
    assignments checked."""
    index = _ModelIndex(clauses, ntot)
    count = 0
    for assigned, value in alphas:
        count += 1
        conflict, a2, v2 = _up(clauses, assigned, value)
        sat, implied = index.entailment(assigned, value)
        test.assertEqual(conflict, not sat,
                         f"alpha=({assigned}, {value})")
        if conflict:
            continue
        for j in range(ntot):
            upval = ((v2 >> j) & 1) if (a2 >> j) & 1 else None
            test.assertEqual(upval, implied.get(j),
                             f"alpha=({assigned}, {value}) "
                             f"var {j}")
    return count


def _pattern_assignment(m, choices):
    """A minimal forbidden pattern: z false, and pair i
    shows its a bit when choices[i] is 0, its b bit when
    choices[i] is 1. All visible variables assigned, no
    auxiliary assigned."""
    assigned = (1 << (2 * m + 1)) - 1
    value = 0
    for i, c in enumerate(choices):
        if c == 0:
            value |= 1 << i
        else:
            value |= 1 << (m + i)
    return assigned, value


def _one_round(clauses, selectors, assigned, value):
    """The one round procedure: probe each selector once
    against the starting partial assignment, collect the
    derived negations, apply them all, and run unit
    propagation once more."""
    derived = 0
    for s in selectors:
        conflict, _, _ = _up(clauses, assigned | (1 << s),
                             value | (1 << s))
        if conflict:
            derived |= 1 << s
    return _up(clauses, assigned | derived, value)


def _visible_entailment(m, assigned, value):
    """Exact entailment of visible literals under a visible
    partial assignment, from the R_m table itself."""
    nvis = 2 * m + 1
    and_mask = (1 << nvis) - 1
    or_mask = 0
    sat = False
    for bits in range(1 << nvis):
        if bits & assigned != value:
            continue
        if _in_R(bits, m):
            sat = True
            and_mask &= bits
            or_mask |= bits
    if not sat:
        return False, {}
    implied = {}
    for j in range(nvis):
        if (and_mask >> j) & 1:
            implied[j] = 1
        elif not (or_mask >> j) & 1:
            implied[j] = 0
    return True, implied


# ----------------------------------------------------------------
# B1. Propagation completeness, auxiliaries assignable.
# ----------------------------------------------------------------

class TestB1Chain(unittest.TestCase):
    def test_chain_full_m1_m2(self):
        total = 0
        for m in (1, 2):
            clauses, naux = _chain_construction(m)
            ntot = 2 * m + 1 + naux
            total += _check_propagation_index(
                self, clauses, ntot, _all_partial(ntot))
        self.assertEqual(total, 243 + 19683)

    def test_chain_m3_deep(self):
        clauses, naux = _chain_construction(3)
        ntot = 7 + naux
        self.assertEqual(ntot, 13)
        count = _check_propagation_index(
            self, clauses, ntot, _partial_min_assigned(ntot, 11))
        self.assertEqual(count, 221184)


class TestB1Block(unittest.TestCase):
    def test_block_full_m1_to_m3(self):
        total = 0
        for m in (1, 2, 3):
            clauses, naux = _block_construction(m)
            ntot = 2 * m + 1 + naux
            total += _check_propagation_index(
                self, clauses, ntot, _all_partial(ntot))
        self.assertEqual(total, 27 + 243 + 6561)

    def test_block_m4_deep(self):
        clauses, naux = _block_construction(4)
        ntot = 9 + naux
        self.assertEqual(ntot, 11)
        count = _check_propagation_index(
            self, clauses, ntot, _partial_min_assigned(ntot, 7))
        self.assertEqual(count, 125952)

    def test_cyclic_example_misses(self):
        # The negative control of the fixed width page,
        # section 5: (a implies b), (a implies c), and
        # (not b or not c) entails not a, and unit
        # propagation under the empty assignment derives
        # nothing. The comparison must register the miss.
        clauses = [(1 << 1, 1 << 0), (1 << 2, 1 << 0),
                   (0, (1 << 1) | (1 << 2))]
        conflict, assigned, _ = _up(clauses, 0, 0)
        self.assertFalse(conflict)
        self.assertEqual(assigned, 0)
        sat, implied = _entailment(clauses, 0, 0, 3)
        self.assertTrue(sat)
        self.assertEqual(implied.get(0), 0)


# ----------------------------------------------------------------
# B2. The grid stalls under plain unit propagation.
# ----------------------------------------------------------------

class TestB2GridStall(unittest.TestCase):
    def _stall(self, clauses, m, choices):
        assigned, value = _pattern_assignment(m, choices)
        conflict, a2, _ = _up(clauses, assigned, value)
        self.assertFalse(conflict, f"m={m} choices={choices}")
        self.assertEqual(a2, assigned,
                         f"m={m} choices={choices}")

    def test_every_pattern_m2_to_m8(self):
        for m in range(2, 9):
            clauses, _, _, _ = _selector_construction(m)
            for choices in itertools.product((0, 1), repeat=m):
                self._stall(clauses, m, choices)

    def test_m30_shapes_and_sample(self):
        m = 30
        clauses, naux, n, _ = _selector_construction(m)
        self.assertEqual(n, 6)
        self.assertEqual(naux, 18)
        shapes = [[0] * m, [1] * m,
                  [i % 2 for i in range(m)],
                  [1 - (i % 2) for i in range(m)]]
        for choices in shapes:
            self._stall(clauses, m, choices)
        rng = random.Random(20261123)
        for _ in range(2000):
            choices = [rng.randrange(2) for _ in range(m)]
            self._stall(clauses, m, choices)

    def test_m256_shapes_and_sample(self):
        m = 256
        clauses, naux, n, _ = _selector_construction(m)
        self.assertEqual(n, 17)
        self.assertEqual(naux, 62)
        self.assertEqual(len(clauses), 575)
        shapes = [[0] * m, [1] * m,
                  [i % 2 for i in range(m)],
                  [1 - (i % 2) for i in range(m)]]
        for choices in shapes:
            self._stall(clauses, m, choices)
        rng = random.Random(20261123)
        for _ in range(2000):
            choices = [rng.randrange(2) for _ in range(m)]
            self._stall(clauses, m, choices)


# ----------------------------------------------------------------
# B3. One failed literal round on the grid.
# ----------------------------------------------------------------

class TestB3OneRound(unittest.TestCase):
    def _compare(self, m, assigned, value):
        clauses, _, _, selectors = _selector_construction(m)
        nvis = 2 * m + 1
        conflict, a2, v2 = _one_round(clauses, selectors,
                                      assigned, value)
        sat, implied = _visible_entailment(m, assigned, value)
        self.assertEqual(conflict, not sat,
                         f"m={m} alpha=({assigned}, {value})")
        if conflict:
            return
        for j in range(nvis):
            upval = ((v2 >> j) & 1) if (a2 >> j) & 1 else None
            self.assertEqual(upval, implied.get(j),
                             f"m={m} alpha=({assigned}, {value}) "
                             f"var {j}")

    def test_all_visible_partials_m1_to_m4(self):
        counts = {}
        for m in range(1, 5):
            nvis = 2 * m + 1
            count = 0
            for assigned, value in _all_partial(nvis):
                count += 1
                self._compare(m, assigned, value)
            counts[m] = count
        self.assertEqual(counts, {1: 27, 2: 243, 3: 2187,
                                  4: 19683})
        self.assertEqual(sum(counts.values()), 22140)

    def test_m256_named_cases(self):
        m = 256
        clauses, _, _, selectors = _selector_construction(m)
        zbit = 1 << (2 * m)
        # A minimal forbidden pattern: the procedure
        # refutes it.
        assigned, value = _pattern_assignment(m, [0] * m)
        conflict, _, _ = _one_round(clauses, selectors,
                                    assigned, value)
        self.assertTrue(conflict)
        # Every pair hit by its a bit, z unassigned: the
        # procedure derives z.
        assigned2 = ((1 << (2 * m)) - 1)
        value2 = (1 << m) - 1
        conflict, a2, v2 = _one_round(clauses, selectors,
                                      assigned2, value2)
        self.assertFalse(conflict)
        self.assertTrue(a2 & zbit)
        self.assertTrue(v2 & zbit)
        # z false, every pair but the first hit by its a
        # bit, the first pair unassigned: the procedure
        # derives both bits of the first pair false.
        assigned3 = ((1 << (2 * m + 1)) - 1) & ~(1 | (1 << m))
        value3 = ((1 << m) - 1) & ~1
        conflict, a3, v3 = _one_round(clauses, selectors,
                                      assigned3, value3)
        self.assertFalse(conflict)
        self.assertTrue(a3 & 1)
        self.assertFalse(v3 & 1)
        self.assertTrue(a3 & (1 << m))
        self.assertFalse(v3 & (1 << m))


# ----------------------------------------------------------------
# B4. The clause floor's finite pins.
# ----------------------------------------------------------------

class TestB4WitnessCounts(unittest.TestCase):
    def _negated_sets(self, m):
        # At most one negated bit per pair, over any subset
        # of pairs.
        sets = []
        for choices in itertools.product((0, 1, 2), repeat=m):
            S = frozenset(
                (i if c == 1 else m + i)
                for i, c in enumerate(choices) if c)
            sets.append(S)
        # The both bits of one pair case, with at most one
        # negated bit in each other pair.
        for p in range(m):
            others = [i for i in range(m) if i != p]
            for choices in itertools.product((0, 1, 2),
                                             repeat=m - 1):
                S = {p, m + p}
                for i, c in zip(others, choices):
                    if c == 1:
                        S.add(i)
                    elif c == 2:
                        S.add(m + i)
                sets.append(frozenset(S))
        return sets

    def _score(self, S, m):
        count = 0
        for pat in itertools.product((0, 1), repeat=m):
            chosen = {i if c == 0 else m + i
                      for i, c in enumerate(pat)}
            if not S <= chosen:
                continue
            for t in range(m):
                if (t if pat[t] == 0 else m + t) in S:
                    count += 1
        return count

    def test_witness_maximum_m1_to_m5(self):
        for m in range(1, 6):
            best = -1
            argmax = []
            for S in self._negated_sets(m):
                score = self._score(S, m)
                if any((p in S) and (m + p in S)
                       for p in range(m)):
                    self.assertEqual(score, 0, (m, S))
                if score > best:
                    best = score
                    argmax = [S]
                elif score == best:
                    argmax.append(S)
            self.assertEqual(best, 2 ** (m - 1), f"m={m}")
            for S in argmax:
                pairs = {x % m for x in S}
                self.assertIn(len(pairs), (1, 2), (m, S))
                self.assertEqual(len(S), len(pairs), (m, S))


class TestB4ExhaustiveArbitraryCNF(unittest.TestCase):
    def _clause_space(self, nvars):
        space = []
        for size in range(0, 4):
            for S in itertools.combinations(range(nvars), size):
                for signs in itertools.product((0, 1),
                                               repeat=size):
                    pos = 0
                    neg = 0
                    for v, s in zip(S, signs):
                        if s:
                            pos |= 1 << v
                        else:
                            neg |= 1 << v
                    space.append((pos, neg))
        return space

    def test_m2_first_encoding_at_four(self):
        m = 2
        nvars = 2 * m + 1
        space = self._clause_space(nvars)
        self.assertEqual(len(space), 131)
        full = (1 << (1 << nvars)) - 1
        sat_masks = []
        for pos, neg in space:
            mask = 0
            for bits in range(1 << nvars):
                if not ((bits & pos) == 0
                        and (bits & neg) == neg):
                    mask |= 1 << bits
            sat_masks.append(mask)
        want = 0
        for v in _R_set(m):
            want |= 1 << v
        for size in range(0, 4):
            for combo in itertools.combinations(
                    range(len(space)), size):
                mask = full
                for c in combo:
                    mask &= sat_masks[c]
                self.assertNotEqual(mask, want,
                                    f"size={size} combo={combo}")
        clauses, naux = _block_construction(m)
        self.assertEqual(naux, 0)
        self.assertEqual(len(clauses), 4)
        self.assertEqual(_projection(clauses, nvars, nvars),
                         _R_set(m))


# ----------------------------------------------------------------
# B5. The equality case and the residual core mechanism.
# ----------------------------------------------------------------

class TestB5EqualityAndMechanism(unittest.TestCase):
    def test_block_counts_m3_to_m6(self):
        for m in range(3, 7):
            clauses, naux = _block_construction(m)
            self.assertEqual(len(clauses), 2 * m, f"m={m}")
            self.assertEqual(naux, m - 2, f"m={m}")

    def _residual(self, clauses, m, assigned, value):
        nvis = 2 * m + 1
        out = []
        for pos, neg in clauses:
            vis_pos = pos & ((1 << nvis) - 1)
            vis_neg = neg & ((1 << nvis) - 1)
            if (value & vis_pos) or \
                    (assigned & ~value & vis_neg):
                continue
            out.append((pos & ~((1 << nvis) - 1),
                        neg & ~((1 << nvis) - 1)))
        return out

    def test_m3_residual_cores(self):
        m = 3
        clauses, naux = _block_construction(m)
        self.assertEqual(naux, 1)
        auxbit = 1 << (2 * m + 1)
        for choices in itertools.product((0, 1), repeat=m):
            assigned, value = _pattern_assignment(m, choices)
            residual = self._residual(clauses, m, assigned,
                                      value)
            # Unit propagation refutes the residual.
            conflict, _, _ = _up(residual, 0, 0)
            self.assertTrue(conflict, f"choices={choices}")
            # A minimal unsatisfiable core containing a
            # unit clause exists.
            found = False
            for size in range(1, len(residual) + 1):
                for core in itertools.combinations(
                        range(len(residual)), size):
                    core_clauses = [residual[c] for c in core]
                    if _satisfies(core_clauses, 0) or \
                            _satisfies(core_clauses, auxbit):
                        continue
                    minimal = True
                    for drop in core:
                        rest = [residual[c] for c in core
                                if c != drop]
                        if not (_satisfies(rest, 0)
                                or _satisfies(rest, auxbit)):
                            minimal = False
                            break
                    if not minimal:
                        continue
                    if any(_popcnt(p) + _popcnt(n) == 1
                           for p, n in core_clauses):
                        found = True
                if found:
                    break
            self.assertTrue(found, f"choices={choices}")


# ----------------------------------------------------------------
# B6. The hierarchy arithmetic and the d = 3 construction.
# ----------------------------------------------------------------

def _leaf_sum(k, h):
    return sum(math.comb(k, i) for i in range(0, h + 1))


def _least_k_leaf(m, h):
    k = 0
    while 3 * _leaf_sum(k, h) < m + 1:
        k += 1
    return k


def _least_k_capacity(m):
    # The capacity side of the first review at w = 3: an
    # exact encoding needs m + 1 <= C(k, 3), and C(k, 3)
    # is at most 2k^2 + 2k + 3 (at most 2^d binom(k, d)
    # clauses of each width d < 3, each contributing
    # 3 - d). The least k this side alone permits:
    k = 0
    while 2 * k * k + 2 * k + 3 < m + 1:
        k += 1
    return k


class TestB6Arithmetic(unittest.TestCase):
    def test_least_k_values(self):
        self.assertEqual(_least_k_leaf(256, 1), 85)
        self.assertEqual(_least_k_leaf(256, 2), 13)
        self.assertEqual(_least_k_leaf(256, 3), 8)
        self.assertEqual(_least_k_leaf(1000000, 1), 333333)
        self.assertEqual(_least_k_leaf(1000000, 2), 816)
        self.assertEqual(_least_k_leaf(1000000, 3), 126)
        self.assertEqual(_least_k_capacity(256), 11)
        self.assertEqual(_least_k_capacity(1000000), 707)

    def test_combined_scaling_exponents(self):
        ratio = math.log(1000000 / 256)
        for h, want in ((1, 1.0), (2, 0.5), (3, 0.5)):
            k1 = max(_least_k_leaf(256, h),
                     _least_k_capacity(256))
            k2 = max(_least_k_leaf(1000000, h),
                     _least_k_capacity(1000000))
            exponent = math.log(k2 / k1) / ratio
            self.assertAlmostEqual(exponent, want, delta=0.03,
                                   msg=f"h={h}")


class TestB6ThreeGroupConstruction(unittest.TestCase):
    def test_projection_and_shape_m1_to_m6(self):
        for m in range(1, 7):
            clauses, naux, n = _three_group_construction(m)
            self.assertEqual(n, 2, f"m={m}")
            self.assertEqual(naux, 6, f"m={m}")
            self.assertEqual(len(clauses), m + 11, f"m={m}")
            for pos, neg in clauses:
                self.assertLessEqual(
                    _popcnt(pos) + _popcnt(neg), 4, f"m={m}")
            got = _projection(clauses, 2 * m + 1,
                              2 * m + 1 + naux)
            self.assertEqual(got, _R_set(m), f"m={m}")
            # One blocking family per selector triple: the
            # clauses whose negative selector part is
            # exactly one triple number between 1 and 2,
            # and no triple carries more than 2 clauses.
            base = 2 * m + 1
            sel_mask = (1 << (base + 3 * n)) - (1 << base)
            per_triple = {}
            for pos, neg in clauses:
                selpart = neg & sel_mask
                if selpart:
                    per_triple[selpart] = \
                        per_triple.get(selpart, 0) + 1
            self.assertEqual(len(per_triple), n ** 3, f"m={m}")
            for selpart, count in per_triple.items():
                self.assertEqual(_popcnt(selpart), 3)
                self.assertLessEqual(count, 2, f"m={m}")


class TestThePage(unittest.TestCase):
    def test_page_states_plan_and_outcome(self):
        with open(os.path.join(
                PROOFS,
                "v4-projection-round2-review-2026-11-23.md"),
                encoding="utf-8") as f:
            page = f.read()
        for needle in ("Suppositions, written before any "
                       "check ran", "## Outcome",
                       "T1.", "T6."):
            self.assertIn(needle, page)


if __name__ == "__main__":
    unittest.main()
