#!/usr/bin/env python3
"""Propagation across one variable joins: a refutation attempt.

docs/infrastructure-documents/proofs/v4-projection-round3-review-2026-11-23.md
records an independent review of a fourth email of
23 November 2026: a separator lemma (two fully
propagation complete CNFs sharing at most one variable
have a fully propagation complete conjunction), the
strengthening of the width three block construction
and the general width Horn group construction to full
propagation completeness over all variables, the
equality and difference counterexample showing the one
variable condition is load bearing, a 13 by 20 selector
grid at m = 256 with 60 auxiliaries and 545 clauses,
and that grid's visible propagation failure. This file
pins the finite parts of the review. Everything here is
stdlib enumeration.

Variables are bit positions in an integer mask, in the
layout of test_v4_projection_width.py: a_i at i, b_i at
m + i, z at 2m, auxiliaries after. A clause is (pos,
neg): masks of the variables appearing positively and
negatively.

1. Full propagation completeness of the block
   construction (width 3) and the group construction
   (widths 4 and 5) against exact entailment computed
   from a bitset model mask, on every partial
   assignment of every variable, m = 1 to 4 at each
   width. The assignment counts are pinned at the
   email's 183,978, 61,506, and 22,140.
2. The separator lemma attacked beyond the
   constructions: pairs of fully propagation complete
   formulas sharing exactly one variable, each side the
   full prime implicate CNF of a random three variable
   function and each side verified fully PC on its own
   first, the conjunction checked on every partial
   assignment; chains of three such blocks glued at
   single variables; the zero overlap case; and a
   control whose first side is not fully PC, where the
   conjunction must fail.
3. The negative control: the difference formula and
   the equality formula over x and y are each fully PC
   over all 9 partial assignments, their conjunction
   is unsatisfiable, and unit propagation from the
   empty assignment derives nothing.
4. Every block shape the constructions use: the
   displayed clauses are exactly the block's prime
   implicates, by enumerating every clause over the
   block's variables; and the constructions' clause
   sets are exactly the unions of those blocks under
   relabeling.
5. The 13 by 20 grid at m = 256: 60 auxiliaries, 545
   clauses, width at most 3; the 256 empty pair
   witnesses and the z witness by explicit completions;
   the 260 designated one hot row and column choices
   falsified; the forbidden direction by its structured
   pieces (every blocker forced under the all hit,
   z false assignment, and each group's clauses
   unsatisfiable with all its selectors false, by
   enumeration over the chain bits); and the catch:
   unit propagation under that same assignment derives
   no conflict and no new literal, on an assignment
   with no completion.
6. The template arithmetic over group sizes 1 to 40:
   within the two group rectangular template, the
   auxiliary minimum at 257 items is 60 and the clause
   minimum there is 545, attained only at 13 by 20 and
   20 by 13.
7. The pages state the review: the fixed width page
   carries the separator lemma, the grid beside its
   propagation failure, and the propagation constrained
   non-Horn optimum posed as OPEN; the review page
   carries its suppositions and its outcome.
"""
import itertools
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


def _R_set(m):
    return {v for v in range(1 << (2 * m + 1)) if _in_R(v, m)}


# ----------------------------------------------------------------
# Constructions, rebuilt from the fixed width page.
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


def _group_sizes(m, w):
    sizes = []
    left = m
    first = True
    while left > 0:
        take = min(left, (w - 1) if first else (w - 2))
        sizes.append(take)
        left -= take
        first = False
    return sizes


def _group_construction(m, w):
    """Horn width w: first group up to w - 1 pairs, later
    groups up to w - 2, one flag per group boundary."""
    def a(i):
        return 1 << i

    def b(i):
        return 1 << (m + i)

    z = 1 << (2 * m)

    def flag(j):
        return 1 << (2 * m + 1 + j)

    clauses = []
    pair0 = 0
    sizes = _group_sizes(m, w)
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


def _block_clauses(size, has_prev):
    """One block in local indices: the previous flag at 0
    when present, then the pairs, then the head. One
    clause per choice of one bit from each pair."""
    base = 1 if has_prev else 0
    head = 1 << (base + 2 * size)
    prev = 1 if has_prev else 0
    clauses = []
    for choice in itertools.product((0, 1), repeat=size):
        body = prev
        for t in range(size):
            body |= 1 << (base + 2 * t + choice[t])
        clauses.append((head, body))
    return clauses, base + 2 * size + 1


def _relabel(clauses, mapping):
    out = []
    for pos, neg in clauses:
        p2 = 0
        n2 = 0
        for local, glob in mapping.items():
            if (pos >> local) & 1:
                p2 |= 1 << glob
            if (neg >> local) & 1:
                n2 |= 1 << glob
        out.append((p2, n2))
    return out


def _block_union(m, w):
    """The construction's clause set rebuilt as a union of
    local blocks, for comparison with the direct build."""
    if w == 3 and m == 1:
        clauses, _ = _block_clauses(1, False)
        return set(_relabel(clauses, {0: 0, 1: 1, 2: 2}))
    out = set()
    if w == 3:
        sizes = [2] + [1] * (m - 2)
    else:
        sizes = _group_sizes(m, w)
    pair0 = 0
    for g, size in enumerate(sizes):
        has_prev = g > 0
        clauses, _ = _block_clauses(size, has_prev)
        base = 1 if has_prev else 0
        mapping = {}
        if has_prev:
            # The previous flag: block construction flags sit
            # at 2m + j with j from 1; group flags at 2m + 1 + j.
            mapping[0] = (2 * m + g) if w == 3 else (2 * m + 1 + g - 1)
        for t in range(size):
            mapping[base + 2 * t] = pair0 + t
            mapping[base + 2 * t + 1] = m + pair0 + t
        if g == len(sizes) - 1:
            head_global = 2 * m
        elif w == 3:
            head_global = 2 * m + g + 1
        else:
            head_global = 2 * m + 1 + g
        mapping[base + 2 * size] = head_global
        out.update(_relabel(clauses, mapping))
        pair0 += size
    return out


# ----------------------------------------------------------------
# Unit propagation.
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


# ----------------------------------------------------------------
# Exact entailment by bitset model mask, and the full PC check.
# ----------------------------------------------------------------

def _var_masks(ntot):
    full = (1 << (1 << ntot)) - 1
    set_mask = []
    clear_mask = []
    for j in range(ntot):
        sm = 0
        for t in range(1 << ntot):
            if (t >> j) & 1:
                sm |= 1 << t
        set_mask.append(sm)
        clear_mask.append(full ^ sm)
    return full, set_mask, clear_mask


def _model_mask(clauses, ntot, set_mask, clear_mask, full):
    mask = full
    for pos, neg in clauses:
        falsified = full
        rest = pos
        j = 0
        while rest:
            if rest & 1:
                falsified &= clear_mask[j]
            rest >>= 1
            j += 1
        rest = neg
        j = 0
        while rest:
            if rest & 1:
                falsified &= set_mask[j]
            rest >>= 1
            j += 1
        mask &= full ^ falsified
    return mask


def _pc_check(clauses, ntot):
    """(ok, count): unit propagation against exact
    entailment on every partial assignment of all ntot
    variables. The recursion carries the extension mask
    down so each node's mask is one AND from its parent."""
    full, set_mask, clear_mask = _var_masks(ntot)
    models = _model_mask(clauses, ntot, set_mask, clear_mask,
                         full)
    state = {"ok": True, "count": 0}

    def walk(j, assigned, value, ext):
        if not state["ok"]:
            return
        if j == ntot:
            state["count"] += 1
            conflict, a2, v2 = _up(clauses, assigned, value)
            if conflict != (ext == 0):
                state["ok"] = False
                return
            if conflict:
                return
            for v in range(ntot):
                upval = ((v2 >> v) & 1) if (a2 >> v) & 1 else None
                if ext & clear_mask[v] == 0:
                    implied = 1
                elif ext & set_mask[v] == 0:
                    implied = 0
                else:
                    implied = None
                if upval != implied:
                    state["ok"] = False
                    return
            return
        walk(j + 1, assigned, value, ext)
        walk(j + 1, assigned | (1 << j), value,
             ext & clear_mask[j])
        walk(j + 1, assigned | (1 << j), value | (1 << j),
             ext & set_mask[j])

    walk(0, 0, 0, models)
    return state["ok"], state["count"]


def _falsified_mask(pos, neg, set_mask, clear_mask, full):
    falsified = full
    rest = pos
    j = 0
    while rest:
        if rest & 1:
            falsified &= clear_mask[j]
        rest >>= 1
        j += 1
    rest = neg
    j = 0
    while rest:
        if rest & 1:
            falsified &= set_mask[j]
        rest >>= 1
        j += 1
    return falsified


def _primes_from_model_mask(models, nvars, set_mask, clear_mask,
                            full):
    implicates = set()
    for spec in itertools.product((0, 1, 2), repeat=nvars):
        pos = 0
        neg = 0
        for j, s in enumerate(spec):
            if s == 1:
                pos |= 1 << j
            elif s == 2:
                neg |= 1 << j
        if pos == 0 and neg == 0:
            continue
        if models & _falsified_mask(pos, neg, set_mask,
                                    clear_mask, full) == 0:
            implicates.add((pos, neg))
    primes = set()
    for pos, neg in implicates:
        prime = True
        for j in range(nvars):
            if (pos >> j) & 1 and \
                    (pos & ~(1 << j), neg) in implicates:
                prime = False
            if (neg >> j) & 1 and \
                    (pos, neg & ~(1 << j)) in implicates:
                prime = False
        if prime:
            primes.add((pos, neg))
    return primes


def _prime_implicates(clauses, nvars):
    full, set_mask, clear_mask = _var_masks(nvars)
    models = _model_mask(clauses, nvars, set_mask, clear_mask,
                         full)
    return _primes_from_model_mask(models, nvars, set_mask,
                                   clear_mask, full)


def _function_cnf(bits_of_models, nvars):
    """The full prime implicate CNF of the function whose
    models are the given bit patterns over nvars."""
    full, set_mask, clear_mask = _var_masks(nvars)
    models = 0
    for bits in bits_of_models:
        models |= 1 << bits
    return sorted(_primes_from_model_mask(
        models, nvars, set_mask, clear_mask, full))


# ----------------------------------------------------------------
# The 13 by 20 grid at m = 256.
# ----------------------------------------------------------------

def _chain_clauses(selectors, chain_bits):
    """The OR chain of the selector construction: n - 2
    clauses and n - 3 chain bits for n from 3 up, one
    clause for n of 1 or 2 and no chain bits."""
    n = len(selectors)
    if n == 1:
        return [(selectors[0], 0)]
    if n == 2:
        return [(selectors[0] | selectors[1], 0)]
    clauses = [(selectors[0] | selectors[1] | chain_bits[0], 0)]
    for j in range(1, n - 3):
        clauses.append((selectors[j + 1] | chain_bits[j],
                        chain_bits[j - 1]))
    clauses.append((selectors[n - 2] | selectors[n - 1],
                    chain_bits[n - 4]))
    return clauses


def _chain_completion(selectors_value, n):
    """Chain bits witnessing the chain clauses for a given
    selector pattern: bit j (0 based, for the bit the
    clauses call t_{j + 1}) is the OR of the selectors
    after index j + 1."""
    bits = []
    for j in range(max(0, n - 3)):
        v = 0
        for t in range(j + 2, n):
            if (selectors_value >> t) & 1:
                v = 1
        bits.append(v)
    return bits


def _grid_construction(r, c, m):
    """Two selector groups of sizes r and c, one blocker
    per cell, pairs and z and padding assigned to cells in
    row major order. Returns (clauses, naux, layout)."""
    def a(i):
        return 1 << i

    def b(i):
        return 1 << (m + i)

    z = 1 << (2 * m)
    base = 2 * m + 1

    def X(i):
        return 1 << (base + i)

    def Y(j):
        return 1 << (base + r + j)

    row_chain_base = base + r + c
    col_chain_base = row_chain_base + max(0, r - 3)

    def rc(j):
        return 1 << (row_chain_base + j)

    def cc(j):
        return 1 << (col_chain_base + j)

    clauses = []
    clauses += _chain_clauses([X(i) for i in range(r)],
                              [rc(j) for j in range(r - 3)])
    clauses += _chain_clauses([Y(j) for j in range(c)],
                              [cc(j) for j in range(c - 3)])
    cells = [(i, j) for i in range(r) for j in range(c)]
    for t, (i, j) in enumerate(cells):
        d = X(i) | Y(j)
        if t < m:
            clauses.append((0, d | a(t)))
            clauses.append((0, d | b(t)))
        elif t == m:
            clauses.append((z, d))
        else:
            clauses.append((0, d))
    naux = (r + c) + max(0, r - 3) + max(0, c - 3)
    layout = {"X": X, "Y": Y, "rc": rc, "cc": cc, "z": z,
              "a": a, "b": b, "cells": cells}
    return clauses, naux, layout


def _grid_witness(r, c, m, layout, empty_pair=None, z_true=False):
    """A total assignment satisfying the grid: the retired
    cell's row and column selected, chains completed by
    the OR tail rule, every other pair hit with a_i."""
    bits = 0
    for i in range(m):
        if empty_pair is not None and i == empty_pair:
            continue
        bits |= layout["a"](i)
    if z_true:
        bits |= layout["z"]
    if empty_pair is not None:
        t = empty_pair
    else:
        t = m
    ci, cj = layout["cells"][t]
    bits |= layout["X"](ci) | layout["Y"](cj)
    sel_r = 1 << ci
    sel_c = 1 << cj
    for j, v in enumerate(_chain_completion(sel_r, r)):
        if v:
            bits |= layout["rc"](j)
    for j, v in enumerate(_chain_completion(sel_c, c)):
        if v:
            bits |= layout["cc"](j)
    return bits


def _group_clauses_count(n):
    return 1 if n <= 2 else n - 2


# ----------------------------------------------------------------
# Tests.
# ----------------------------------------------------------------

class TestConstructionFullPC(unittest.TestCase):
    def _run_width(self, w, want_total):
        total = 0
        for m in range(1, 5):
            if w == 3:
                clauses, naux = _block_construction(m)
            else:
                clauses, naux = _group_construction(m, w)
            ntot = 2 * m + 1 + naux
            ok, count = _pc_check(clauses, ntot)
            self.assertEqual(count, 3 ** ntot, (w, m))
            total += count
            self.assertTrue(ok, (w, m))
        self.assertEqual(total, want_total, w)

    def test_width3_counts_and_full_pc(self):
        self._run_width(3, 183978)

    def test_width4_counts_and_full_pc(self):
        self._run_width(4, 61506)

    def test_width5_counts_and_full_pc(self):
        self._run_width(5, 22140)


class TestGluingAttack(unittest.TestCase):
    def _random_side(self, rng, shared, locals_):
        """The full prime implicate CNF of a random function
        on (shared, locals_), in global indices."""
        nvars = 1 + len(locals_)
        models = [bits for bits in range(1 << nvars)
                  if rng.random() < 0.5]
        if not models or len(models) == (1 << nvars):
            models = [0]
        local_clauses = _function_cnf(models, nvars)
        mapping = {0: shared}
        for t, g in enumerate(locals_):
            mapping[t + 1] = g
        return _relabel(local_clauses, mapping)

    def test_random_pairs_share_one_variable(self):
        rng = random.Random(20261123)
        checked = 0
        attempts = 0
        while checked < 120 and attempts < 400:
            attempts += 1
            f = self._random_side(rng, 0, [1, 2])
            g = self._random_side(rng, 0, [3, 4])
            ok_f = _pc_check_on(f, [0, 1, 2])
            ok_g = _pc_check_on(g, [0, 3, 4])
            if not (ok_f and ok_g):
                continue
            checked += 1
            ok, count = _pc_check(f + g, 5)
            self.assertEqual(count, 3 ** 5)
            self.assertTrue(ok, (f, g))
        self.assertEqual(checked, 120)

    def test_random_triples_glue_in_chains(self):
        rng = random.Random(20261124)
        checked = 0
        attempts = 0
        while checked < 20 and attempts < 200:
            attempts += 1
            # f on {0, 1, 2}; g on {0, 3, 4}, sharing only
            # variable 0 with f and carrying variable 3 as
            # its second link; h on {3, 5, 6}, sharing only
            # variable 3 with the aggregate f AND g.
            f = self._random_side(rng, 0, [1, 2])
            g = self._random_side(rng, 0, [3, 4])
            h = self._random_side(rng, 3, [5, 6])
            if not (_pc_check_on(f, [0, 1, 2])
                    and _pc_check_on(g, [0, 3, 4])
                    and _pc_check_on(h, [3, 5, 6])):
                continue
            checked += 1
            ok, count = _pc_check(f + g + h, 7)
            self.assertEqual(count, 3 ** 7)
            self.assertTrue(ok, (f, g, h))
        self.assertEqual(checked, 20)

    def test_zero_overlap_is_a_sanity_control(self):
        rng = random.Random(20261125)
        f = self._random_side(rng, 0, [1, 2])
        g = self._random_side(rng, 3, [4, 5])
        self.assertTrue(_pc_check_on(f, [0, 1, 2]))
        self.assertTrue(_pc_check_on(g, [3, 4, 5]))
        ok, _ = _pc_check(f + g, 6)
        self.assertTrue(ok)

    def test_a_non_pc_side_breaks_the_conjunction(self):
        # The cyclic example of the fixed width page: a
        # implies b, a implies c, not both b and c. It
        # entails not a and propagation derives nothing.
        f = [(1 << 1, 1 << 0), (1 << 2, 1 << 0),
             (0, (1 << 1) | (1 << 2))]
        # An equivalence on the shared variable c (index 2)
        # and a fresh d (index 3): fully PC on its own.
        g = [(1 << 3, 1 << 2), (1 << 2, 1 << 3)]
        self.assertFalse(_pc_check_on(f, [0, 1, 2]))
        self.assertTrue(_pc_check_on(g, [2, 3]))
        ok, _ = _pc_check(f + g, 4)
        self.assertFalse(ok)
        conflict, assigned, _ = _up(f + g, 0, 0)
        self.assertFalse(conflict)
        self.assertEqual(assigned, 0)


def _pc_check_on(clauses, var_indices):
    """Full PC check of a formula whose variables are the
    given global indices, by relabeling to a compact
    layout and back. Only the verdict is needed."""
    mapping = {g: t for t, g in enumerate(var_indices)}
    compact = []
    for pos, neg in clauses:
        p2 = 0
        n2 = 0
        for g, t in mapping.items():
            if (pos >> g) & 1:
                p2 |= 1 << t
            if (neg >> g) & 1:
                n2 |= 1 << t
        compact.append((p2, n2))
    ok, _ = _pc_check(compact, len(var_indices))
    return ok


class TestNegativeControl(unittest.TestCase):
    def test_equality_and_difference(self):
        x = 1 << 0
        y = 1 << 1
        diff = [(x | y, 0), (0, x | y)]
        equal = [(x, y), (y, x)]
        for side in (diff, equal):
            ok, count = _pc_check(side, 2)
            self.assertEqual(count, 9)
            self.assertTrue(ok)
        both = diff + equal
        models = [bits for bits in range(4)
                  if _satisfies(both, bits)]
        self.assertEqual(models, [])
        conflict, assigned, _ = _up(both, 0, 0)
        self.assertFalse(conflict)
        self.assertEqual(assigned, 0)


class TestBlocksArePrimeImplicateComplete(unittest.TestCase):
    def test_block_shapes(self):
        for size, has_prev in ((1, False), (2, False),
                               (3, False), (4, False),
                               (1, True), (2, True),
                               (3, True)):
            clauses, nvars = _block_clauses(size, has_prev)
            primes = _prime_implicates(clauses, nvars)
            self.assertEqual(primes, set(clauses),
                             (size, has_prev))

    def test_constructions_are_block_unions(self):
        for m in range(1, 8):
            clauses, _ = _block_construction(m)
            self.assertEqual(set(clauses), _block_union(m, 3),
                             m)
        for w in (4, 5):
            for m in range(1, 8):
                clauses, _ = _group_construction(m, w)
                self.assertEqual(set(clauses),
                                 _block_union(m, w), (w, m))


class TestGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r, cls.c, cls.m = 13, 20, 256
        cls.clauses, cls.naux, cls.layout = _grid_construction(
            cls.r, cls.c, cls.m)

    def test_counts_and_width(self):
        self.assertEqual(self.naux, 60)
        self.assertEqual(len(self.clauses), 545)
        for pos, neg in self.clauses:
            self.assertLessEqual(_popcnt(pos) + _popcnt(neg), 3)

    def test_empty_pair_witnesses(self):
        for p in range(self.m):
            bits = _grid_witness(self.r, self.c, self.m,
                                 self.layout, empty_pair=p)
            self.assertTrue(_satisfies(self.clauses, bits), p)

    def test_z_witness(self):
        bits = _grid_witness(self.r, self.c, self.m,
                             self.layout, z_true=True)
        self.assertTrue(_satisfies(self.clauses, bits))

    def test_one_hot_choices_are_falsified(self):
        lay = self.layout
        for t, (ci, cj) in enumerate(lay["cells"]):
            bits = 0
            for i in range(self.m):
                bits |= lay["a"](i)
            bits |= lay["X"](ci) | lay["Y"](cj)
            for j, v in enumerate(
                    _chain_completion(1 << ci, self.r)):
                if v:
                    bits |= lay["rc"](j)
            for j, v in enumerate(
                    _chain_completion(1 << cj, self.c)):
                if v:
                    bits |= lay["cc"](j)
            self.assertFalse(_satisfies(self.clauses, bits), t)

    def _all_hit_assignment(self):
        assigned = 0
        value = 0
        for i in range(self.m):
            assigned |= self.layout["a"](i) | self.layout["b"](i)
            value |= self.layout["a"](i)
        assigned |= self.layout["z"]
        return assigned, value

    def test_every_blocker_is_forced(self):
        assigned, value = self._all_hit_assignment()
        forced = set()
        for pos, neg in self.clauses:
            if (value & pos) or (assigned & ~value & neg):
                continue
            forced.add((pos & ~assigned, neg & ~assigned))
        lay = self.layout
        for (ci, cj) in lay["cells"]:
            self.assertIn((0, lay["X"](ci) | lay["Y"](cj)),
                          forced)

    def test_groups_unsatisfiable_with_selectors_false(self):
        lay = self.layout
        groups = (
            (_chain_clauses([lay["X"](i) for i in range(self.r)],
                            [lay["rc"](j)
                             for j in range(self.r - 3)]),
             [lay["X"](i) for i in range(self.r)],
             [lay["rc"](j) for j in range(self.r - 3)]),
            (_chain_clauses([lay["Y"](j) for j in range(self.c)],
                            [lay["cc"](j)
                             for j in range(self.c - 3)]),
             [lay["Y"](j) for j in range(self.c)],
             [lay["cc"](j) for j in range(self.c - 3)]),
        )
        for clauses, selectors, chain_bits in groups:
            found = False
            for combo in range(1 << len(chain_bits)):
                bits = 0
                for t, cb in enumerate(chain_bits):
                    if (combo >> t) & 1:
                        bits |= cb
                if _satisfies(clauses, bits):
                    found = True
                    break
            self.assertFalse(found)

    def test_propagation_stalls_on_the_named_assignment(self):
        assigned, value = self._all_hit_assignment()
        conflict, a2, _ = _up(self.clauses, assigned, value)
        self.assertFalse(conflict)
        self.assertEqual(a2, assigned)


class TestTemplateArithmetic(unittest.TestCase):
    def test_minimum_within_the_template(self):
        best = None
        attainers = []
        for r in range(1, 41):
            for c in range(1, 41):
                if r * c < 257:
                    continue
                aux = (r + c) + max(0, r - 3) + max(0, c - 3)
                clauses = r * c + 256 + _group_clauses_count(r) \
                    + _group_clauses_count(c)
                key = (aux, clauses)
                if best is None or key < best:
                    best = key
                    attainers = [(r, c)]
                elif key == best:
                    attainers.append((r, c))
        self.assertEqual(best, (60, 545))
        self.assertEqual(sorted(attainers), [(13, 20), (20, 13)])


class TestThePages(unittest.TestCase):
    def test_pages_state_the_round_three_review(self):
        with open(os.path.join(
                PROOFS, "v4-projection-fixed-width.md"),
                encoding="utf-8") as f:
            theorem = f.read()
        for needle in ("separator", "545 clauses", "OPEN",
                       "test_v4_projection_round3.py"):
            self.assertIn(needle, theorem)
        with open(os.path.join(
                PROOFS,
                "v4-projection-round3-review-2026-11-23.md"),
                encoding="utf-8") as f:
            review = f.read()
        for needle in ("Suppositions, written before any "
                       "check ran", "Outcome"):
            self.assertIn(needle, review)


if __name__ == "__main__":
    unittest.main()
