# Tests for docs/infrastructure-documents/proofs/
# v4-projection-gluing-review-2026-11-23.md
#
# The fourth projection email of 23 November 2026 claims a
# gluing lemma (two fully propagation complete CNFs sharing
# at most one variable have a fully propagation complete
# conjunction), full propagation completeness of the width
# three and general width Horn constructions over all of
# their variables, exact finite check counts of 183,978,
# 61,506 and 22,140 (267,624 in total), and a 13 by 20
# selector grid encoding R_256 in 60 auxiliaries and 545
# clauses that is not visibly unit refutation complete.
# These tests are the independent attack: a generic
# propagation versus entailment checker validated on two
# controls that must register misses, random and structured
# attempts to break the lemma, block by block and whole
# construction checks at the email's own counts, and the
# grid built and recorded together with its stall.

import itertools
import os
import random
import unittest

PROOFS = os.path.join(
    os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))),
    "docs", "infrastructure-documents", "proofs")


# ----------------------------------------------------------------
# Basic machinery. Clauses are (pos, neg) bitmask pairs: a
# clause is falsified by a total assignment exactly when no
# pos bit is set and every neg bit is set.
# ----------------------------------------------------------------

def _satisfies(clauses, bits):
    for pos, neg in clauses:
        if (bits & pos) == 0 and (bits & neg) == neg:
            return False
    return True


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


def _pc_failures(clauses, nvars, assignments=None):
    """Compare unit propagation against exact entailment,
    the entailment computed from the model set as bitmasks.
    Returns (failures, checked): each failure is
    (assigned, value, kind) with kind "conflict" or the
    index of a variable whose implied value propagation
    missed or invented."""
    models = [bits for bits in range(1 << nvars)
              if _satisfies(clauses, bits)]
    nmask = (1 << len(models)) - 1
    posmask = [0] * nvars
    for idx, bits in enumerate(models):
        rest = bits
        while rest:
            low = rest & (-rest)
            posmask[low.bit_length() - 1] |= 1 << idx
            rest ^= low
    negmask = [nmask ^ posmask[j] for j in range(nvars)]
    if assignments is None:
        assignments = _all_partial(nvars)
    failures = []
    checked = 0
    for assigned, value in assignments:
        checked += 1
        live = nmask
        rest = assigned
        while rest:
            low = rest & (-rest)
            j = low.bit_length() - 1
            live &= posmask[j] if (value >> j) & 1 else negmask[j]
            rest ^= low
        sat = live != 0
        conflict, a2, v2 = _up(clauses, assigned, value)
        if conflict != (not sat):
            failures.append((assigned, value, "conflict"))
            continue
        if not sat:
            continue
        for j in range(nvars):
            if (assigned >> j) & 1:
                continue
            if live & negmask[j] == 0:
                implied = 1
            elif live & posmask[j] == 0:
                implied = 0
            else:
                implied = None
            seen = ((v2 >> j) & 1) if (a2 >> j) & 1 else None
            if seen != implied:
                failures.append((assigned, value, j))
    return failures, checked


def _is_pc(clauses, nvars):
    failures, _ = _pc_failures(clauses, nvars)
    return not failures


# ----------------------------------------------------------------
# Constructions, rebuilt from the emails' descriptions (the
# same shapes as test_v4_projection_width.py, restated here
# so this module stands alone).
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


def _remap(clauses, bit_order):
    """Rebuild clauses over fresh variable indices:
    bit_order lists the source bit positions in the order
    they take as new variables 0, 1, 2, ..."""
    out = []
    for pos, neg in clauses:
        npos = 0
        nneg = 0
        for new, old in enumerate(bit_order):
            if (pos >> old) & 1:
                npos |= 1 << new
            if (neg >> old) & 1:
                nneg |= 1 << new
        out.append((npos, nneg))
    return out


def _glue(f_clauses, f_nvars, g_clauses, g_vars, shared_g,
          shared_f):
    """Relabel G so its variable shared_g lands on F's
    variable shared_f and every other G variable takes a
    fresh index above all of F's variables. g_vars is the
    list of G's variable indices."""
    mapping = {}
    fresh = f_nvars
    for v in g_vars:
        if v == shared_g:
            mapping[v] = shared_f
        else:
            mapping[v] = fresh
            fresh += 1
    out = list(f_clauses)
    for pos, neg in g_clauses:
        npos = 0
        nneg = 0
        for src, dst in mapping.items():
            if (pos >> src) & 1:
                npos |= 1 << dst
            if (neg >> src) & 1:
                nneg |= 1 << dst
        out.append((npos, nneg))
    return out, fresh


# ----------------------------------------------------------------
# The checker must catch what is not propagation complete.
# ----------------------------------------------------------------

class TestControls(unittest.TestCase):
    def test_xor_equality_pair_is_the_negative_control(self):
        # F: x differs from y. G: x equals y. Each is fully
        # PC over its 9 partial assignments; the conjunction
        # shares both variables, is unsatisfiable, and unit
        # propagation under the empty assignment derives
        # nothing. The checker must flag the conjunction.
        x, y = 1 << 0, 1 << 1
        f = [(x | y, 0), (0, x | y)]
        g = [(x, y), (y, x)]
        for formula in (f, g):
            failures, checked = _pc_failures(formula, 2)
            self.assertEqual(checked, 9)
            self.assertEqual(failures, [])
        failures, _ = _pc_failures(f + g, 2)
        self.assertTrue(failures)
        self.assertIn((0, 0, "conflict"), failures)

    def test_cyclic_horn_example_registers_a_miss(self):
        # (a implies b), (a implies c), (not b or not c)
        # entails not a; propagation under the empty
        # assignment derives nothing.
        clauses = [(1 << 1, 1 << 0), (1 << 2, 1 << 0),
                   (0, (1 << 1) | (1 << 2))]
        failures, _ = _pc_failures(clauses, 3)
        self.assertIn((0, 0, 0), failures)


# ----------------------------------------------------------------
# The gluing attack.
# ----------------------------------------------------------------

def _prime_implicates(models, nvars):
    """Every prime implicate of the function whose models
    are the given total assignments. The canonical CNF of
    all prime implicates is the standard fully PC form."""
    modelset = set(models)
    clauses = []
    for spec in itertools.product((0, 1, 2), repeat=nvars):
        pos = 0
        neg = 0
        for j, s in enumerate(spec):
            if s == 1:
                neg |= 1 << j
            elif s == 2:
                pos |= 1 << j
        if pos == 0 and neg == 0:
            continue

        def falsified_by(bits, p=pos, n=neg):
            return (bits & p) == 0 and (bits & n) == n

        if any(falsified_by(b) for b in modelset):
            continue
        prime = True
        rest = pos | neg
        while rest:
            low = rest & (-rest)
            p2 = pos & ~low
            n2 = neg & ~low
            if not any((b & p2) == 0 and (b & n2) == n2
                       for b in modelset):
                prime = False
                break
            rest ^= low
        if prime:
            clauses.append((pos, neg))
    return clauses


def _random_pc_by_implicates(rng, nvars, tries=40):
    for _ in range(tries):
        size = rng.randint(2, (1 << nvars) - 2)
        models = rng.sample(range(1 << nvars), size)
        clauses = _prime_implicates(models, nvars)
        if 0 < len(clauses) <= 60:
            return clauses
    return None


def _random_pc_by_filter(rng, nvars, tries=300):
    for _ in range(tries):
        clauses = []
        for _ in range(rng.randint(1, 7)):
            width = rng.randint(1, 3)
            vars_ = rng.sample(range(nvars), width)
            pos = 0
            neg = 0
            for v in vars_:
                if rng.random() < 0.5:
                    pos |= 1 << v
                else:
                    neg |= 1 << v
            clauses.append((pos, neg))
        if _is_pc(clauses, nvars):
            return clauses
    return None


def _random_forest_horn(rng, nvars):
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
            neg = 0
            for v in vars_:
                neg |= 1 << v
            clauses.append((0, neg))
        else:
            pos = 1 << vars_[0]
            neg = 0
            for v in vars_[1:]:
                neg |= 1 << v
            clauses.append((pos, neg))
    return clauses


class TestGluingAttack(unittest.TestCase):
    def test_random_pairs_share_one_variable(self):
        rng = random.Random(20261124)
        tested = 0
        checked = 0
        pools = []
        for _ in range(10):
            f = _random_pc_by_implicates(rng, 4)
            if f is not None:
                pools.append(f)
        self.assertGreaterEqual(len(pools), 6)
        for f in pools:
            self.assertTrue(_is_pc(f, 4))
        for i in range(len(pools)):
            for j in range(i + 1, len(pools)):
                sf = rng.randrange(4)
                sg = rng.randrange(4)
                both, nvars = _glue(pools[i], 4, pools[j],
                                    list(range(4)), sg, sf)
                self.assertEqual(nvars, 7)
                failures, count = _pc_failures(both, nvars)
                checked += count
                tested += 1
                self.assertEqual(failures, [],
                                 f"pair {i},{j} shared "
                                 f"{sf},{sg}: {failures[:1]}")
        self.assertGreaterEqual(tested, 15)
        self.assertGreater(checked, 0)

    def test_filtered_pairs_share_one_variable(self):
        rng = random.Random(20261125)
        pool = []
        for _ in range(12):
            f = _random_pc_by_filter(rng, 4)
            if f is not None:
                pool.append(f)
        self.assertGreaterEqual(len(pool), 6)
        tested = 0
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                sf = rng.randrange(4)
                sg = rng.randrange(4)
                both, nvars = _glue(pool[i], 4, pool[j],
                                    list(range(4)), sg, sf)
                failures, _ = _pc_failures(both, nvars)
                tested += 1
                self.assertEqual(failures, [],
                                 f"pair {i},{j}: {failures[:1]}")
        self.assertGreaterEqual(tested, 15)

    def test_forest_horn_pairs_and_chains(self):
        rng = random.Random(20261126)
        tested = 0
        for _ in range(30):
            f = _random_forest_horn(rng, 4)
            g = _random_forest_horn(rng, 5)
            if not f or not g:
                continue
            self.assertTrue(_is_pc(f, 4))
            self.assertTrue(_is_pc(g, 5))
            sf = rng.randrange(4)
            sg = rng.randrange(5)
            both, nvars = _glue(f, 4, g, list(range(5)), sg, sf)
            self.assertEqual(nvars, 8)
            failures, _ = _pc_failures(both, nvars)
            tested += 1
            self.assertEqual(failures, [],
                             f"forest pair: {failures[:1]}")
        self.assertGreaterEqual(tested, 20)

    def test_three_block_chains(self):
        rng = random.Random(20261127)
        tested = 0
        for _ in range(12):
            blocks = []
            ok = True
            for _ in range(3):
                f = _random_pc_by_implicates(rng, 3)
                if f is None:
                    ok = False
                    break
                blocks.append(f)
            if not ok:
                continue
            both, nvars = _glue(blocks[0], 3, blocks[1],
                                list(range(3)),
                                rng.randrange(3), rng.randrange(3))
            self.assertEqual(nvars, 5)
            failures, _ = _pc_failures(both, nvars)
            self.assertEqual(failures, [])
            third_at = rng.randrange(nvars)
            both, nvars = _glue(both, nvars, blocks[2],
                                list(range(3)),
                                rng.randrange(3), third_at)
            self.assertEqual(nvars, 7)
            failures, _ = _pc_failures(both, nvars)
            tested += 1
            self.assertEqual(failures, [],
                             f"chain: {failures[:1]}")
        self.assertGreaterEqual(tested, 6)

    def test_edge_cases_at_the_shared_variable(self):
        v, x, y = 1 << 0, 1 << 1, 1 << 2
        # Each base formula is verified fully PC by the
        # checker before it is glued.
        edge = [
            ([(v, 0)], 2),                    # unit on v
            ([(0, v)], 2),                    # unit on not v
            ([(v, 0), (0, v)], 1),            # unsatisfiable
            ([], 1),                          # empty block
            ([(v | x, 0)], 2),                # v in one polarity
            ([(v, x), (x, 0)], 2),            # v forced via x
            ([(x, v), (0, v)], 2),            # v forced false
        ]
        rng = random.Random(20261128)
        partners = []
        for _ in range(4):
            g = _random_pc_by_implicates(rng, 3)
            if g is not None:
                partners.append(g)
        self.assertTrue(partners)
        for clauses, nvars in edge:
            self.assertTrue(_is_pc(clauses, nvars),
                            f"edge base not PC: {clauses}")
            for g in partners:
                self.assertTrue(_is_pc(g, 3))
                both, total = _glue(clauses, nvars, g,
                                    list(range(3)),
                                    rng.randrange(3), 0)
                failures, _ = _pc_failures(both, total)
                self.assertEqual(failures, [],
                                 f"edge {clauses}: "
                                 f"{failures[:1]}")


# ----------------------------------------------------------------
# Blocks and whole constructions: the email's own counts.
# ----------------------------------------------------------------

class TestBlocks(unittest.TestCase):
    def test_width_three_blocks_standalone(self):
        m3, _ = _block_construction(3)
        first = _remap(m3[:4], [0, 3, 1, 4, 7])
        failures, checked = _pc_failures(first, 5)
        self.assertEqual(checked, 243)
        self.assertEqual(failures, [])
        m4, _ = _block_construction(4)
        middle = _remap(m4[4:6], [9, 2, 6, 10])
        failures, checked = _pc_failures(middle, 4)
        self.assertEqual(checked, 81)
        self.assertEqual(failures, [])
        last = _remap(m4[6:8], [10, 3, 7, 8])
        failures, checked = _pc_failures(last, 4)
        self.assertEqual(checked, 81)
        self.assertEqual(failures, [])
        m2, _ = _block_construction(2)
        failures, checked = _pc_failures(m2, 5)
        self.assertEqual(checked, 243)
        self.assertEqual(failures, [])

    def test_general_width_blocks_standalone(self):
        g3, _ = _group_construction(3, 4)
        failures, checked = _pc_failures(g3, 7)
        self.assertEqual(checked, 2187)
        self.assertEqual(failures, [])
        g4, _ = _group_construction(4, 4)
        tail = _remap(g4[8:], [9, 3, 7, 8])
        failures, checked = _pc_failures(tail, 4)
        self.assertEqual(checked, 81)
        self.assertEqual(failures, [])
        g5, _ = _group_construction(4, 5)
        failures, checked = _pc_failures(g5, 9)
        self.assertEqual(checked, 19683)
        self.assertEqual(failures, [])
        g6, _ = _group_construction(6, 5)
        tail = _remap(g6[16:], [13, 4, 10, 5, 11, 12])
        failures, checked = _pc_failures(tail, 6)
        self.assertEqual(checked, 729)
        self.assertEqual(failures, [])


class TestConstructionCounts(unittest.TestCase):
    def test_width_three_full_counts(self):
        total = 0
        for m, want in ((1, 27), (2, 243), (3, 6561),
                        (4, 177147)):
            clauses, naux = _block_construction(m)
            ntot = 2 * m + 1 + naux
            failures, checked = _pc_failures(clauses, ntot)
            self.assertEqual(checked, want, f"m={m}")
            self.assertEqual(failures, [], f"m={m}")
            total += checked
        self.assertEqual(total, 183978)

    def test_width_four_full_counts(self):
        total = 0
        for m, want in ((1, 27), (2, 243), (3, 2187),
                        (4, 59049)):
            clauses, naux = _group_construction(m, 4)
            ntot = 2 * m + 1 + naux
            failures, checked = _pc_failures(clauses, ntot)
            self.assertEqual(checked, want, f"m={m}")
            self.assertEqual(failures, [], f"m={m}")
            total += checked
        self.assertEqual(total, 61506)

    def test_width_five_full_counts(self):
        total = 0
        for m, want in ((1, 27), (2, 243), (3, 2187),
                        (4, 19683)):
            clauses, naux = _group_construction(m, 5)
            ntot = 2 * m + 1 + naux
            failures, checked = _pc_failures(clauses, ntot)
            self.assertEqual(checked, want, f"m={m}")
            self.assertEqual(failures, [], f"m={m}")
            total += checked
        self.assertEqual(total, 22140)

    def test_grand_total(self):
        self.assertEqual(183978 + 61506 + 22140, 267624)


# ----------------------------------------------------------------
# The 13 by 20 grid, recorded with its propagation failure.
# ----------------------------------------------------------------

GRID_M = 256
GRID_R = 13
GRID_C = 20


def _grid_layout():
    """Variable indices: a_i at i, b_i at 256 + i, z at
    512, row selectors X at 513.., column selectors Y,
    then the row chain bits and the column chain bits."""
    def a(i):
        return i

    def b(i):
        return GRID_M + i

    z = 2 * GRID_M
    x0 = 2 * GRID_M + 1

    def xs(i):
        return x0 + i

    def ys(j):
        return x0 + GRID_R + j

    def xchain(j):
        return x0 + GRID_R + GRID_C + (j - 1)

    def ychain(j):
        return x0 + GRID_R + GRID_C + (GRID_R - 3) + (j - 1)

    ntot = x0 + GRID_R + GRID_C + (GRID_R - 3) + (GRID_C - 3)
    return a, b, z, xs, ys, xchain, ychain, ntot


def _or_chain(selectors, chainbit):
    """The standard width three at least one chain over
    n selectors: n - 3 chain bits, n - 2 clauses."""
    n = len(selectors)
    s = [1 << v for v in selectors]
    clauses = [(s[0] | s[1] | (1 << chainbit(1)), 0)]
    for j in range(1, n - 3):
        clauses.append((s[j + 1] | (1 << chainbit(j + 1)),
                        1 << chainbit(j)))
    clauses.append((s[n - 2] | s[n - 1], 1 << chainbit(n - 3)))
    return clauses


def _grid_construction():
    a, b, z, xs, ys, xchain, ychain, ntot = _grid_layout()
    clauses = []
    clauses += _or_chain([xs(i) for i in range(GRID_R)], xchain)
    clauses += _or_chain([ys(j) for j in range(GRID_C)], ychain)
    cells = [(i, j) for i in range(GRID_R) for j in range(GRID_C)]
    for t, (i, j) in enumerate(cells):
        neg = (1 << xs(i)) | (1 << ys(j))
        if t < GRID_M:
            clauses.append((0, neg | (1 << a(t))))
            clauses.append((0, neg | (1 << b(t))))
        elif t == GRID_M:
            clauses.append((1 << z, neg))
        else:
            clauses.append((0, neg))
    return clauses, ntot


def _chain_values(n, chosen):
    """Chain bit values (as a dict bit index to 0 or 1)
    satisfying the at least one chain when the single
    chosen selector, 0 based index chosen, is the true
    one: bit j is set exactly when 1 <= j <= chosen - 1."""
    return {j: 1 if 1 <= j <= chosen - 1 else 0
            for j in range(1, n - 2)}


def _grid_witness(empty_pair):
    """A total assignment satisfying the grid: either the
    named pair is empty and every other pair is hit with
    a true and b false (empty_pair in 0..255), or every
    pair is hit and z is true (empty_pair is None). The
    chosen cell's row and column selectors are the true
    ones."""
    a, b, z, xs, ys, xchain, ychain, ntot = _grid_layout()
    if empty_pair is None:
        cell = GRID_M
    else:
        cell = empty_pair
    r, c = divmod(cell, GRID_C)
    value = 0
    for i in range(GRID_M):
        if i != empty_pair:
            value |= 1 << a(i)
    if empty_pair is None:
        value |= 1 << z
    value |= 1 << xs(r)
    value |= 1 << ys(c)
    for j, bit in _chain_values(GRID_R, r).items():
        if bit:
            value |= 1 << xchain(j)
    for j, bit in _chain_values(GRID_C, c).items():
        if bit:
            value |= 1 << ychain(j)
    return value


def _dpll(clauses, assigned, value, branch_vars):
    conflict, a2, v2 = _up(clauses, assigned, value)
    if conflict:
        return False
    for var in branch_vars:
        if not (a2 >> var) & 1:
            rest = [w for w in branch_vars if w != var]
            return (_dpll(clauses, a2 | (1 << var), v2,
                          rest)
                    or _dpll(clauses, a2 | (1 << var),
                             v2 | (1 << var), rest))
    return True


class TestGrid(unittest.TestCase):
    def test_counts_and_width(self):
        clauses, ntot = _grid_construction()
        self.assertEqual(len(clauses), 545)
        self.assertEqual(ntot - (2 * GRID_M + 1), 60)
        for pos, neg in clauses:
            self.assertLessEqual(
                bin(pos | neg).count("1"), 3)

    def test_empty_pair_witnesses(self):
        clauses, _ = _grid_construction()
        for p in range(GRID_M):
            self.assertTrue(
                _satisfies(clauses, _grid_witness(p)),
                f"empty pair {p}")

    def test_z_witness(self):
        clauses, _ = _grid_construction()
        self.assertTrue(
            _satisfies(clauses, _grid_witness(None)))

    def test_forbidden_selector_choices(self):
        clauses, _ = _grid_construction()
        a, b, z, xs, ys, _, _, _ = _grid_layout()
        assigned = 0
        value = 0
        for i in range(GRID_M):
            assigned |= (1 << a(i)) | (1 << b(i))
            value |= 1 << a(i)
        assigned |= 1 << z
        for i in range(GRID_R):
            for j in range(GRID_C):
                a2 = assigned | (1 << xs(i)) | (1 << ys(j))
                v2 = value | (1 << xs(i)) | (1 << ys(j))
                conflict, _, _ = _up(clauses, a2, v2)
                self.assertTrue(conflict, f"cell {i},{j}")

    def test_stalling_assignment_stalls_and_is_unsat(self):
        clauses, ntot = _grid_construction()
        a, b, z, xs, ys, xchain, ychain, _ = _grid_layout()
        assigned = 0
        value = 0
        for i in range(GRID_M):
            assigned |= (1 << a(i)) | (1 << b(i))
            value |= 1 << a(i)
        assigned |= 1 << z
        conflict, a2, _ = _up(clauses, assigned, value)
        self.assertFalse(conflict)
        self.assertEqual(a2, assigned)
        branch = ([xs(i) for i in range(GRID_R)]
                  + [ys(j) for j in range(GRID_C)]
                  + [xchain(j) for j in range(1, GRID_R - 2)]
                  + [ychain(j) for j in range(1, GRID_C - 2)])
        self.assertFalse(
            _dpll(clauses, assigned, value, branch))

    def test_all_hit_patterns_are_unsat(self):
        clauses, _ = _grid_construction()
        a, b, z, xs, ys, xchain, ychain, _ = _grid_layout()
        branch = ([xs(i) for i in range(GRID_R)]
                  + [ys(j) for j in range(GRID_C)]
                  + [xchain(j) for j in range(1, GRID_R - 2)]
                  + [ychain(j) for j in range(1, GRID_C - 2)])
        patterns = [
            lambda i: (1, 0),
            lambda i: (0, 1),
            lambda i: (1, 1),
            lambda i: (1, 0) if i % 2 == 0 else (0, 1),
        ]
        for pick in patterns:
            assigned = 0
            value = 0
            for i in range(GRID_M):
                assigned |= (1 << a(i)) | (1 << b(i))
                av, bv = pick(i)
                if av:
                    value |= 1 << a(i)
                if bv:
                    value |= 1 << b(i)
            assigned |= 1 << z
            self.assertFalse(
                _dpll(clauses, assigned, value, branch))

    def test_template_arithmetic(self):
        def aux(r, c):
            return (r + c) + max(0, r - 3) + max(0, c - 3)

        for r in range(3, 41):
            for c in range(3, 41):
                self.assertEqual(aux(r, c), 2 * (r + c) - 6)
        self.assertEqual(
            min(r + c for r in range(1, 300)
                for c in range(1, 300) if r * c >= 257), 33)
        shapes = [(r, 33 - r) for r in range(3, 31)
                  if r * (33 - r) >= 257]
        self.assertEqual(min(r * c for r, c in shapes), 260)
        self.assertIn((13, 20),
                      [(r, c) for r, c in shapes
                       if r * c == 260])
        self.assertEqual(aux(13, 20), 60)
        self.assertGreaterEqual(
            min(c for c in range(1, 400) if 2 * c >= 257),
            129)


class TestThePages(unittest.TestCase):
    def test_pages_state_the_review(self):
        with open(os.path.join(
                PROOFS, "v4-projection-gluing-review-2026-11-23.md"),
                encoding="utf-8") as f:
            review = f.read()
        for needle in ("Suppositions, written before any "
                       "check ran", "Outcome", "267,624",
                       "gluing lemma"):
            self.assertIn(needle, review)
        with open(os.path.join(
                PROOFS, "v4-projection-fixed-width.md"),
                encoding="utf-8") as f:
            page = f.read()
        for needle in ("13 by 20", "545 clauses",
                       "refutation complete", "OPEN"):
            self.assertIn(needle, page)


if __name__ == "__main__":
    unittest.main()
