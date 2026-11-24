#!/usr/bin/env python3
"""The projection at fixed clause width: a refutation attempt.

docs/infrastructure-documents/proofs/v4-projection-width-review-2026-11-23.md
records an independent review of two emailed claims that
follow the projection page: an exact width three Horn
tradeoff (minimum auxiliaries max(0, m - 2), and exactly
2m clauses at that minimum), a fixed width theorem for
Horn and for arbitrary CNF, a width two wall by majority
closure, and a propagation extension for incidence
forests. The claims arrived by email on 23 November 2026
and stand relayed in ComChat; the second email asked for
an attempt to break them. This file pins the finite parts
of the review. The solver search of the review (attack
A1) needs a SAT solver and is recorded in the review page
only; everything here is stdlib enumeration.

Variables are bit positions in an integer mask, in the
layout of test_v4_the_projection.py: a_i at i, b_i at
m + i, z at 2m, auxiliaries after. A clause is (pos, neg):
masks of the variables appearing positively and
negatively.

1. The width three block construction: 2m clauses,
   max(0, m - 2) auxiliaries, projection exactly R_m,
   m 1 to 7. The group construction at the Horn boundary
   m = 1 + (k + 1)(w - 2) for (w, k) = (3, 1), (4, 0),
   (4, 1), (5, 1). The selector construction for arbitrary
   CNF at width three, m 1 to 7, and the m = 256 counts
   (62 auxiliaries, 575 clauses) as pure arithmetic.
2. The zero auxiliary boundary: a rule body meeting
   every pair and sitting inside one minimal pattern
   exists exactly when m <= w - 1, by enumerating bodies.
3. Exhaustive clause subset search: no width three Horn
   encoding of R_1 with fewer than 2 clauses, and none
   of R_2 with fewer than 4, over the full clause space.
4. Majority: the three witnesses for m 2 to 7, every
   clause of width at most 2 over 5 variables majority
   closed, R_1 majority closed with a width two encoding.
5. The capacity values: minimally unsatisfiable counts
   1, 2, 12, 870 for k = 0 to 3, C(k, 3) = 3, 4, 5, 6,
   and the exact regime C(k, w) = (w - k) 2^k at
   (k, w) = (1, 2) and (2, 4).
6. Propagation against exact entailment by completion
   enumeration: the block construction on every partial
   visible assignment for m 1 to 4, and for m = 5 on
   assignments fixing at least 8 of 11 visible variables
   (entailment there by the R_m reduction, cross-checked
   against brute force at m = 4); the original chain on
   every partial assignment of all its variables for
   m = 1 and 2, and for m = 3 on assignments fixing at
   least 12 of 13; 200 random Horn formulas whose
   incidence graph is a forest, on every partial
   assignment; and a cyclic Horn example where
   propagation provably misses an implied literal, so
   the comparison has teeth.

The asymptotic statements are the emails' arguments,
recorded in the review page, not tested here. What is
tested is the finite enumeration those arguments rest
on, and the small cases a counterexample would most
likely inhabit.
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
# Constructions, rebuilt from the emails' descriptions.
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


def _group_construction(m, w, k):
    """Horn width w: first group up to w - 1 pairs, later
    groups up to w - 2, one flag per group boundary."""
    def a(i):
        return 1 << i

    def b(i):
        return 1 << (m + i)

    z = 1 << (2 * m)

    def flag(j):
        return 1 << (2 * m + 1 + j)

    sizes = []
    left = m
    first = True
    while left > 0:
        take = min(left, (w - 1) if first else (w - 2))
        sizes.append(take)
        left -= take
        first = False
    clauses = []
    pair0 = 0
    for g, size in enumerate(sizes):
        head = z if g == len(sizes) - 1 else flag(g)
        prev = flag(g - 1) if g > 0 else 0
        pairs = list(range(pair0, pair0 + size))
        for choice in itertools.product((0, 1), repeat=size):
            body = prev
            for t, i in enumerate(pairs):
                body |= a(i) if choice[t] == 0 else b(i)
            clauses.append((head, body))
        pair0 += size
    return clauses, max(0, len(sizes) - 1)


def _selector_construction(m):
    """Arbitrary CNF width three: 2 groups of n selectors,
    n least with n^2 >= m + 1, an OR chain per group, n^2
    blocking clauses carrying the m pairs and z."""
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
    return clauses, 2 * n + 2 * max(0, n - 3), n


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


def _check_propagation(test, clauses, ntot, alphas, compare):
    for assigned, value in alphas:
        conflict, a2, v2 = _up(clauses, assigned, value)
        sat, implied = _entailment(clauses, assigned, value, ntot)
        test.assertEqual(conflict, not sat,
                         f"alpha=({assigned}, {value})")
        if conflict:
            continue
        for j in compare:
            upval = ((v2 >> j) & 1) if (a2 >> j) & 1 else None
            test.assertEqual(upval, implied.get(j),
                             f"alpha=({assigned}, {value}) "
                             f"var {j}")


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
    for spec in itertools.product((0, 1, 2), repeat=nvars):
        if sum(1 for s in spec if s) < min_assigned:
            continue
        assigned = 0
        value = 0
        for j, s in enumerate(spec):
            if s:
                assigned |= 1 << j
                if s == 2:
                    value |= 1 << j
        yield assigned, value


# ----------------------------------------------------------------
# Tests.
# ----------------------------------------------------------------

class TestBlockConstruction(unittest.TestCase):
    def test_counts_and_projection(self):
        for m in range(1, 8):
            clauses, naux = _block_construction(m)
            self.assertEqual(len(clauses), 2 * m, f"m={m}")
            self.assertEqual(naux, max(0, m - 2), f"m={m}")
            for pos, neg in clauses:
                self.assertLessEqual(_popcnt(pos), 1)
                self.assertLessEqual(
                    _popcnt(pos) + _popcnt(neg), 3)
            got = _projection(clauses, 2 * m + 1,
                              2 * m + 1 + naux)
            self.assertEqual(got, _R_set(m), f"m={m}")


class TestGroupConstruction(unittest.TestCase):
    def test_boundary_points(self):
        for (w, k, m, want) in ((3, 1, 3, 6), (4, 0, 3, 8),
                                (4, 1, 5, 12), (5, 1, 7, 24)):
            clauses, naux = _group_construction(m, w, k)
            self.assertEqual(naux, k, (w, k, m))
            self.assertEqual(len(clauses), want, (w, k, m))
            for pos, neg in clauses:
                self.assertLessEqual(_popcnt(pos), 1)
                self.assertLessEqual(
                    _popcnt(pos) + _popcnt(neg), w)
            got = _projection(clauses, 2 * m + 1,
                              2 * m + 1 + naux)
            self.assertEqual(got, _R_set(m), (w, k, m))


class TestZeroAuxiliaryBoundary(unittest.TestCase):
    def test_rule_bodies(self):
        for w in (3, 4, 5):
            for m, want in ((w, 0), (w - 1, 2 ** (w - 1))):
                good = 0
                for size in range(0, w):
                    for body in itertools.combinations(
                            range(2 * m), size):
                        hits = all(
                            any(x == i or x == m + i
                                for x in body)
                            for i in range(m))
                        one_per = all(
                            sum(1 for x in body
                                if x == i or x == m + i) <= 1
                            for i in range(m))
                        if hits and one_per:
                            good += 1
                self.assertEqual(good, want, (w, m))


class TestExhaustiveSmallSearches(unittest.TestCase):
    def _space(self, nvars):
        clauses = []
        for head in range(nvars):
            others = [v for v in range(nvars) if v != head]
            for size in range(0, 3):
                for body in itertools.combinations(others, size):
                    neg = 0
                    for v in body:
                        neg |= 1 << v
                    clauses.append((1 << head, neg))
        for size in range(0, 4):
            for S in itertools.combinations(range(nvars), size):
                neg = 0
                for v in S:
                    neg |= 1 << v
                clauses.append((0, neg))
        return clauses

    def _first_encoding_size(self, m, max_size):
        nvars = 2 * m + 1
        space = self._space(nvars)
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
        for size in range(0, max_size + 1):
            for combo in itertools.combinations(
                    range(len(space)), size):
                mask = full
                for c in combo:
                    mask &= sat_masks[c]
                if mask == want:
                    return size
        return None

    def test_m1_minimum_is_two(self):
        self.assertEqual(self._first_encoding_size(1, 2), 2)

    def test_m2_nothing_below_four(self):
        self.assertIsNone(self._first_encoding_size(2, 3))


class TestSelectorConstruction(unittest.TestCase):
    def test_counts_and_projection(self):
        for m in range(1, 8):
            clauses, naux, n = _selector_construction(m)
            self.assertEqual(naux, 2 * n + 2 * max(0, n - 3),
                             f"m={m}")
            group_clauses = 2 * (n - 2) if n >= 3 else 2
            self.assertEqual(len(clauses),
                             n * n + m + group_clauses, f"m={m}")
            for pos, neg in clauses:
                self.assertLessEqual(
                    _popcnt(pos) + _popcnt(neg), 3)
            got = _projection(clauses, 2 * m + 1,
                              2 * m + 1 + naux)
            self.assertEqual(got, _R_set(m), f"m={m}")

    def test_m256_arithmetic(self):
        n = math.ceil(math.sqrt(257))
        self.assertEqual(n, 17)
        self.assertLess((n - 1) ** 2, 257)
        self.assertEqual(2 * n + 2 * (n - 3), 62)
        self.assertEqual(n * n + 256 + 2 * (n - 2), 575)


class TestMajority(unittest.TestCase):
    def _majority(self, x, y, z, nvars):
        out = 0
        for j in range(nvars):
            votes = ((x >> j) & 1) + ((y >> j) & 1) \
                + ((z >> j) & 1)
            if votes >= 2:
                out |= 1 << j
        return out

    def test_witnesses(self):
        for m in range(2, 8):
            def vis(zv, empty_pair):
                bits = 0
                for i in range(m):
                    if i == empty_pair:
                        continue
                    bits |= (1 << i) | (1 << (m + i))
                if zv:
                    bits |= 1 << (2 * m)
                return bits

            W1, W2, W3 = vis(0, 0), vis(0, 1), vis(1, None)
            for W in (W1, W2, W3):
                self.assertTrue(_in_R(W, m), (m, W))
            self.assertFalse(
                _in_R(self._majority(W1, W2, W3, 2 * m + 1), m))

    def test_width_two_clauses_are_majority_closed(self):
        nvars = 5
        for spec in itertools.product((0, 1, 2), repeat=nvars):
            if sum(1 for s in spec if s) > 2:
                continue
            pos = sum(1 << j for j, s in enumerate(spec)
                      if s == 1)
            neg = sum(1 << j for j, s in enumerate(spec)
                      if s == 2)
            clause = [(pos, neg)]
            sats = [x for x in range(1 << nvars)
                    if _satisfies(clause, x)]
            for x in sats:
                for y in sats:
                    for z in sats:
                        self.assertTrue(_satisfies(
                            clause,
                            self._majority(x, y, z, nvars)), spec)

    def test_r1_majority_closed_with_width_two_encoding(self):
        rel = [v for v in range(1 << 3) if _in_R(v, 1)]
        for x in rel:
            for y in rel:
                for z in rel:
                    self.assertTrue(
                        _in_R(self._majority(x, y, z, 3), 1))
        enc = [(1 << 2, 1 << 0), (1 << 2, 1 << 1)]
        self.assertEqual(_projection(enc, 3, 3), _R_set(1))


class TestCapacity(unittest.TestCase):
    def _mu_enumeration(self, k):
        points = 1 << k
        full = (1 << points) - 1
        specs = []
        for spec in itertools.product((0, 1, 2), repeat=k):
            mask = full
            width = 0
            for i, s in enumerate(spec):
                if s == 0:
                    continue
                width += 1
                lit = 0
                for p in range(points):
                    bit = (p >> i) & 1
                    if (s == 1 and bit == 0) \
                            or (s == 2 and bit == 1):
                        lit |= 1 << p
                mask &= lit
            specs.append((mask, width))
        found = []
        suffix_or = [0] * (len(specs) + 1)
        for j in range(len(specs) - 1, -1, -1):
            suffix_or[j] = suffix_or[j + 1] | specs[j][0]

        def dfs(start, chosen, or_mask):
            if or_mask == full:
                for t in range(len(chosen)):
                    others = 0
                    for u in range(len(chosen)):
                        if u != t:
                            others |= specs[chosen[u]][0]
                    if specs[chosen[t]][0] & ~others == 0:
                        return
                found.append(list(chosen))
                return
            if len(chosen) == points:
                return
            for idx in range(start, len(specs)):
                if or_mask | suffix_or[idx] != full:
                    break
                dfs(idx + 1, chosen + [idx],
                    or_mask | specs[idx][0])

        dfs(0, [], 0)
        return specs, found

    def test_counts_and_capacities(self):
        want = {0: (1, 3), 1: (2, 4), 2: (12, 5), 3: (870, 6)}
        for k, (count, cap3) in want.items():
            specs, found = self._mu_enumeration(k)
            self.assertEqual(len(found), count, f"k={k}")
            got = max(sum(3 - specs[c][1] for c in chosen)
                      for chosen in found)
            self.assertEqual(got, cap3, f"k={k}")
            if k == 1:
                self.assertEqual(
                    max(sum(2 - specs[c][1] for c in chosen)
                        for chosen in found), (2 - 1) * 2 ** 1)
            if k == 2:
                self.assertEqual(
                    max(sum(4 - specs[c][1] for c in chosen)
                        for chosen in found), (4 - 2) * 2 ** 2)


class TestVisiblePropagation(unittest.TestCase):
    def test_block_full_to_m4(self):
        for m in range(1, 5):
            clauses, naux = _block_construction(m)
            nvis = 2 * m + 1
            _check_propagation(self, clauses, nvis + naux,
                               _all_partial(nvis),
                               list(range(nvis)))

    def test_block_m5_by_relation_reduction(self):
        # Entailment of visible literals under the block
        # construction reduces to the R_m table, because the
        # projection is R_m (TestBlockConstruction). The
        # reduction itself is the brute force comparison at
        # m = 4 above, a different code path to the same
        # entailment.
        m = 5
        clauses, naux = _block_construction(m)
        nvis = 2 * m + 1
        for assigned, value in _partial_min_assigned(nvis, 8):
            conflict, a2, v2 = _up(clauses, assigned, value)
            free_vis = [j for j in range(nvis)
                        if not (assigned >> j) & 1]
            and_mask = (1 << nvis) - 1
            or_mask = 0
            sat = False
            for combo in range(1 << len(free_vis)):
                bits = value
                for t, j in enumerate(free_vis):
                    if (combo >> t) & 1:
                        bits |= 1 << j
                if _in_R(bits, m):
                    sat = True
                    and_mask &= bits
                    or_mask |= bits
            self.assertEqual(conflict, not sat)
            if conflict:
                continue
            for j in range(nvis):
                upval = ((v2 >> j) & 1) if (a2 >> j) & 1 else None
                implied = None
                if (and_mask >> j) & 1:
                    implied = 1
                elif not (or_mask >> j) & 1:
                    implied = 0
                self.assertEqual(upval, implied,
                                 f"alpha=({assigned}, {value}) "
                                 f"var {j}")


class TestForestPropagation(unittest.TestCase):
    def test_chain_full_to_m2(self):
        for m in (1, 2):
            clauses, naux = _chain_construction(m)
            ntot = 2 * m + 1 + naux
            _check_propagation(self, clauses, ntot,
                               _all_partial(ntot),
                               list(range(ntot)))

    def test_chain_m3_deep_assignments(self):
        clauses, naux = _chain_construction(3)
        ntot = 7 + naux
        _check_propagation(self, clauses, ntot,
                           _partial_min_assigned(ntot, 12),
                           list(range(ntot)))

    def _random_forest(self, rng, nvars):
        parent = list(range(nvars))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        clauses = []
        attempts = 0
        while len(clauses) < nvars + 2 and attempts < 200:
            attempts += 1
            width = rng.randint(1, 3)
            vars_ = rng.sample(range(nvars), width)
            roots = [find(v) for v in vars_]
            if len(set(roots)) != len(roots):
                continue
            for v in vars_[1:]:
                parent[find(v)] = find(vars_[0])
            if rng.random() < 0.25:
                pos = 0
                neg = 0
                for v in vars_:
                    neg |= 1 << v
            else:
                pos = 1 << vars_[0]
                neg = 0
                for v in vars_[1:]:
                    neg |= 1 << v
            clauses.append((pos, neg))
        return clauses

    def test_random_forests(self):
        rng = random.Random(20261123)
        for _ in range(200):
            nvars = rng.choice((4, 5))
            clauses = self._random_forest(rng, nvars)
            if not clauses:
                continue
            _check_propagation(self, clauses, nvars,
                               _all_partial(nvars),
                               list(range(nvars)))

    def test_cyclic_example_misses(self):
        # a -> b, a -> c, and (not b or not c): the formula
        # entails not a, and unit propagation under the
        # empty assignment derives nothing. The comparison
        # must register the miss.
        clauses = [(1 << 1, 1 << 0), (1 << 2, 1 << 0),
                   (0, (1 << 1) | (1 << 2))]
        conflict, assigned, _ = _up(clauses, 0, 0)
        self.assertFalse(conflict)
        self.assertEqual(assigned, 0)
        sat, implied = _entailment(clauses, 0, 0, 3)
        self.assertTrue(sat)
        self.assertEqual(implied.get(0), 0)


class TestThePages(unittest.TestCase):
    def test_pages_state_the_claims_and_the_review(self):
        with open(os.path.join(
                PROOFS, "v4-projection-fixed-width.md"),
                encoding="utf-8") as f:
            theorem = f.read()
        for needle in ("max(0, m - 2)", "2m clauses",
                       "Theta_w(m^(1 / (w - 1)))",
                       "majority",
                       "test_v4_projection_width.py",
                       "reviewed"):
            self.assertIn(needle, theorem)
        with open(os.path.join(
                PROOFS,
                "v4-projection-width-review-2026-11-23.md"),
                encoding="utf-8") as f:
            review = f.read()
        for needle in ("Suppositions, written before any "
                       "check ran", "Outcome"):
            self.assertIn(needle, review)


if __name__ == "__main__":
    unittest.main()
