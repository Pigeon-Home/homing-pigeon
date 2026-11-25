# Tests for docs/infrastructure-documents/proofs/
# research-loops-review-2026-11-24.md
#
# The ChatGPT research loops relayed on 24 November 2026
# (simulation pair cfc79b1, loops 3414840 and 379cfc6,
# and the fresh collision candidates) make finite claims
# that this file checks with independent implementations:
# the nine point pair graph pruning rule and its small
# rows, the randomized clock estimator algebra and its
# toy calibration, the Horn closure lift and its bad lift
# control, the graph coloring menu identity, the quotient
# certificate method and its negative control, the
# collision counting inequality and the B(10) arithmetic,
# and the selector deletion arithmetic. Every expectation
# here was written down as a supposition on the review
# page before the checks ran.

import itertools
import math
import random
import unittest
from fractions import Fraction

random.seed(20261124)


# ----------------------------------------------------------------
# Nine point pruning: pair graphs, wedges, forced triples.
# ----------------------------------------------------------------

def _graph_stats(n, edges):
    adj = {v: set() for v in range(n)}
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    deg = [len(adj[v]) for v in range(n)]
    wedges = sum(d * (d - 1) // 2 for d in deg)
    triangles = 0
    uncovered = 0
    for tri in itertools.combinations(range(n), 3):
        a, b, c = tri
        e = (b in adj[a]) + (c in adj[a]) + (c in adj[b])
        if e == 3:
            triangles += 1
        if e == 0:
            uncovered += 1
    return wedges, triangles, uncovered


def _all_graphs(n):
    pairs = list(itertools.combinations(range(n), 2))
    for mask in range(1 << len(pairs)):
        yield [pairs[i] for i in range(len(pairs)) if mask >> i & 1]


class TestNinePointPruning(unittest.TestCase):

    def test_wedge_identity_and_triangle_bound_small(self):
        for n in range(3, 7):
            for edges in _all_graphs(n):
                wedges, triangles, uncovered = _graph_stats(n, edges)
                p = len(edges)
                self.assertEqual(
                    uncovered,
                    math.comb(n, 3) - (n - 2) * p + wedges - triangles)
                self.assertLessEqual(3 * triangles, wedges)

    def test_wedge_identity_and_triangle_bound_nine(self):
        pairs = list(itertools.combinations(range(9), 2))
        for _ in range(8000):
            edges = random.sample(pairs, random.randint(0, 20))
            wedges, triangles, uncovered = _graph_stats(9, edges)
            self.assertEqual(
                uncovered, 84 - 7 * len(edges) + wedges - triangles)
            self.assertLessEqual(3 * triangles, wedges)

    def test_min_wedges_at_nine_edges(self):
        # Degree sequences of 9 vertices with degree sum 18:
        # the wedge count is minimized by the all 2 sequence.
        best = [None]

        def rec(v, remaining, cur):
            if v == 8:
                d = remaining
                if d <= 8:
                    s = cur + d * (d - 1) // 2
                    if best[0] is None or s < best[0]:
                        best[0] = s
                return
            for d in range(0, min(8, remaining) + 1):
                rec(v + 1, remaining - d, cur + d * (d - 1) // 2)

        rec(0, 18, 0)
        self.assertEqual(best[0], 9)

    def test_nine_edges_force_total_at_least_45(self):
        # u = 21 + S - t and t <= S/3 and S >= 9 give u >= 27.
        self.assertGreaterEqual(18 + 21 + (2 * 9) // 3, 45)
        pairs = list(itertools.combinations(range(9), 2))
        for _ in range(8000):
            edges = random.sample(pairs, 9)
            _, _, uncovered = _graph_stats(9, edges)
            self.assertGreaterEqual(18 + uncovered, 45)

    def test_nine_edge_bound_is_tight(self):
        edges = [(0, 1), (1, 2), (0, 2), (3, 4), (4, 5),
                 (3, 5), (6, 7), (7, 8), (6, 8)]
        wedges, triangles, uncovered = _graph_stats(9, edges)
        self.assertEqual((wedges, triangles, uncovered), (9, 3, 27))
        self.assertEqual(9 + 9 + uncovered, 45)

    def test_budget_44_forces_nine_pairs(self):
        for p in range(0, 9):
            self.assertGreater(9 + p + max(0, 84 - 7 * p), 44)


def _covered_by_two(fam, target):
    target = set(target)
    if frozenset(target) in fam:
        return True
    for b in fam:
        for c in fam:
            if b and c and b <= target and c <= target \
                    and b | c == target and b != target and c != target:
                return True
    return False


def _random_family(trials_seed):
    rng = random.Random(trials_seed)
    fam = {frozenset([i]) for i in range(9)}
    for s in range(2, 6):
        for comb in itertools.combinations(range(9), s):
            if rng.random() < 0.08:
                fam.add(frozenset(comb))
    return fam


class TestSmallRows(unittest.TestCase):

    def test_triple_row_characterization(self):
        for seed in range(800):
            fam = _random_family(seed)
            for tri in itertools.combinations(range(9), 3):
                char = frozenset(tri) in fam or any(
                    frozenset(pr) in fam
                    for pr in itertools.combinations(tri, 2))
                self.assertEqual(_covered_by_two(fam, tri), char)

    def test_four_set_row_characterization(self):
        matchings = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
        for seed in range(800):
            fam = _random_family(seed + 100000)
            for quad in itertools.combinations(range(9), 4):
                char = frozenset(quad) in fam or any(
                    frozenset(tr) in fam
                    for tr in itertools.combinations(quad, 3))
                if not char:
                    for (a, b) in matchings:
                        p1 = frozenset((quad[a[0]], quad[a[1]]))
                        p2 = frozenset((quad[b[0]], quad[b[1]]))
                        if p1 in fam and p2 in fam:
                            char = True
                self.assertEqual(_covered_by_two(fam, quad), char)


# ----------------------------------------------------------------
# The randomized clock.
# ----------------------------------------------------------------

def _random_tau_dist(rng):
    vals = rng.sample(range(0, 30), rng.randint(1, 6))
    weights = [rng.randint(1, 9) for _ in vals] + [rng.randint(0, 5)]
    total = sum(weights)
    dist = {v: Fraction(w, total) for v, w in zip(vals, weights)}
    if weights[-1]:
        dist[None] = Fraction(weights[-1], total)
    return dist


class TestRandomizedClock(unittest.TestCase):

    def test_expectation_second_moment_tail(self):
        rng = random.Random(7)
        horizon = 10
        for _ in range(300):
            dist = _random_tau_dist(rng)
            z_h = sum(p / (t + 1) for t, p in dist.items()
                      if t is not None and t <= horizon)
            ey = Fraction(0)
            ey2 = Fraction(0)
            for t, p in dist.items():
                if t is None or t > horizon:
                    continue
                ey += p * (t + 1) * Fraction(1, (t + 1) ** 2)
                ey2 += p * (t + 1) ** 2 * Fraction(1, (t + 1) ** 2)
            self.assertEqual(ey, z_h)
            self.assertEqual(
                ey2, sum(p for t, p in dist.items()
                         if t is not None and t <= horizon))
            z = sum(p / (t + 1) for t, p in dist.items() if t is not None)
            self.assertTrue(0 <= z - z_h <= Fraction(1, horizon + 2))
            var = ey2 - z_h * z_h
            self.assertTrue(0 <= var <= 1)

    def test_expected_steps_below_bound(self):
        s = sum(Fraction(1, (t + 1) ** 2) for t in range(1, 2000))
        self.assertLess(s, Fraction(645, 1000))
        self.assertAlmostEqual(
            float(s), math.pi ** 2 / 6 - 1, delta=0.001)

    def test_exact_sampler_identity(self):
        for t in range(1, 60):
            prod = Fraction(1)
            for s in range(0, t):
                prod *= Fraction((s + 1) ** 2, (s + 2) ** 2)
            self.assertEqual(prod, Fraction(1, (t + 1) ** 2))

    def test_detection_clock(self):
        rng = random.Random(11)
        horizon = 12
        for _ in range(200):
            dist = _random_tau_dist(rng)
            z_h = sum(p / (t + 1) for t, p in dist.items()
                      if t is not None and t <= horizon)
            hit = sum(p * Fraction(1, t + 1) for t, p in dist.items()
                      if t is not None and t <= horizon)
            self.assertEqual(hit, z_h)

    def test_anytime_miss_bound(self):
        for r in range(1, 13):
            p = Fraction(1, 2 ** r)
            delta = Fraction(1, 20)
            n = 1
            while (1 - p) ** n >= delta:
                n += 1
            self.assertLess((1 - p) ** n, delta)
            if n > 1:
                self.assertGreaterEqual((1 - p) ** (n - 1), delta)
            if r >= 6:
                self.assertTrue(2.9 < n / (2.0 ** r) < 3.05)

    def test_toy_calibration(self):
        for m in range(0, 7):
            for k in range(0, 4):
                succ = sum(
                    1 for bits in itertools.product([0, 1], repeat=3)
                    if all(bits[i] == 1 for i in range(k)))
                mass = Fraction(succ, 8)
                self.assertEqual(mass, Fraction(1, 2 ** k))
                self.assertEqual(mass * Fraction(1, 4 + m),
                                 mass / (4 + m))


# ----------------------------------------------------------------
# The Horn closure lift.
# ----------------------------------------------------------------

def _horn_closure(clauses, yassign):
    xvars = set()
    for pos, negs in clauses:
        if pos and pos not in yassign:
            xvars.add(pos)
        xvars |= {v for v in negs if v not in yassign}
    simp = []
    for pos, negs in clauses:
        sat = False
        rem_negs = set()
        if pos is not None and pos in yassign and yassign[pos]:
            sat = True
        for v in negs:
            if v in yassign:
                if not yassign[v]:
                    sat = True
            else:
                rem_negs.add(v)
        if sat:
            continue
        newpos = pos
        if pos is not None and pos in yassign:
            newpos = None
        simp.append((newpos, frozenset(rem_negs)))
        if pos is None and not rem_negs:
            return (False, None)
        if newpos is None and not rem_negs and pos is not None:
            return (False, None)
    derived = set()
    changed = True
    while changed:
        changed = False
        for pos, negs in simp:
            if pos is not None and negs <= derived and pos not in derived:
                derived.add(pos)
                changed = True
    for pos, negs in simp:
        if pos is None and negs <= derived:
            return (False, None)
    xassign = {v: (v in derived) for v in xvars}
    full = dict(yassign)
    full.update(xassign)
    for pos, negs in clauses:
        val = (full[pos] if pos else False) or \
            any(not full[v] for v in negs)
        if not val:
            return (False, None)
    return (True, xassign)


def _brute_extendible(clauses, yassign, xvars):
    for bits in itertools.product([False, True], repeat=len(xvars)):
        full = dict(yassign)
        full.update(dict(zip(xvars, bits)))
        if all((full[pos] if pos else False) or
               any(not full[v] for v in negs) for pos, negs in clauses):
            return True
    return False


def _rand_horn(rng, ny, nx, ncl):
    ys = [f"y{i}" for i in range(ny)]
    xs = [f"x{i}" for i in range(nx)]
    allv = ys + xs
    clauses = []
    for _ in range(ncl):
        kind = rng.random()
        if kind < 0.25:
            clauses.append((rng.choice(allv), frozenset()))
        elif kind < 0.7:
            pos = rng.choice(allv)
            negs = frozenset(
                rng.sample(allv, rng.randint(1, min(3, len(allv)))))
            clauses.append((pos, negs - {pos}))
        else:
            clauses.append((None, frozenset(
                rng.sample(allv, rng.randint(1, min(3, len(allv)))))))
    return clauses, ys, xs


class TestHornLift(unittest.TestCase):

    def test_closure_agrees_with_brute_force(self):
        rng = random.Random(23)
        for _ in range(2500):
            clauses, ys, xs = _rand_horn(
                rng, rng.randint(1, 4), rng.randint(1, 7),
                rng.randint(1, 9))
            yassign = {v: rng.random() < 0.5 for v in ys}
            extendible, xassign = _horn_closure(clauses, yassign)
            self.assertEqual(
                extendible, _brute_extendible(clauses, yassign, xs))
            if extendible:
                full = dict(yassign)
                full.update(xassign)
                self.assertTrue(all(
                    (full[pos] if pos else False) or
                    any(not full[v] for v in negs)
                    for pos, negs in clauses))

    def test_bad_lift_is_caught(self):
        clauses = [("x1", frozenset({"y"})), ("x2", frozenset({"x1"}))]

        def sat(full):
            return all((full[pos] if pos else False) or
                       any(not full[v] for v in negs)
                       for pos, negs in clauses)

        found = None
        for yv in [False, True]:
            for x1 in [False, True]:
                for x2 in [False, True]:
                    alt = {"y": yv, "x1": x1, "x2": x2}
                    lift = {"y": yv, "x1": yv, "x2": False}
                    if sat(alt) and not sat(lift):
                        found = (yv, alt, lift)
        self.assertIsNotNone(found)
        self.assertTrue(found[0])
        self.assertEqual(found[1], {"y": True, "x1": True, "x2": True})
        self.assertEqual(found[2], {"y": True, "x1": True, "x2": False})


# ----------------------------------------------------------------
# The graph coloring menu.
# ----------------------------------------------------------------

def _chromatic(n, edges):
    for k in range(0, n + 1):
        for assign in itertools.product(range(k), repeat=n):
            if all(assign[a] != assign[b] for a, b in edges):
                return k
    return n


def _min_menu(n, edges):
    masks = set()
    for row in range(1 << len(edges)):
        mask = 0
        for v in range(n):
            covered = True
            for i, (a, b) in enumerate(edges):
                bit = (row >> i) & 1
                if a == v and bit != 1:
                    covered = False
                if b == v and bit != 0:
                    covered = False
            if covered:
                mask |= (1 << v)
        masks.add(mask)
    full = (1 << n) - 1
    inf = 10 ** 9
    dp = [inf] * (1 << n)
    dp[0] = 0
    for m in range(1 << n):
        for cm in masks:
            nm = m | cm
            if dp[m] + 1 < dp[nm]:
                dp[nm] = dp[m] + 1
    return dp[full]


class TestColoringMenu(unittest.TestCase):

    def test_menu_equals_chromatic_all_small_graphs(self):
        for n in range(1, 6):
            pairs = list(itertools.combinations(range(n), 2))
            for mask in range(1 << len(pairs)):
                edges = [pairs[i] for i in range(len(pairs))
                         if mask >> i & 1]
                self.assertEqual(
                    _min_menu(n, edges), _chromatic(n, edges))

    def test_menu_equals_chromatic_random_larger(self):
        rng = random.Random(31)
        for _ in range(120):
            n = rng.choice([6, 7])
            pairs = list(itertools.combinations(range(n), 2))
            edges = rng.sample(pairs, rng.randint(0, min(11, len(pairs))))
            self.assertEqual(
                _min_menu(n, edges), _chromatic(n, edges))

    def test_identity_relation_width(self):
        for k in range(1, 5):
            masks = {1 << row for row in range(1 << k)}
            full = (1 << (1 << k)) - 1
            dp = {0: 0}
            for _ in range(1 << k):
                ndp = dict(dp)
                for m, c in dp.items():
                    for cm in masks:
                        nm = m | cm
                        if ndp.get(nm, 10 ** 9) > c + 1:
                            ndp[nm] = c + 1
                dp = ndp
            self.assertEqual(dp[full], 1 << k)


# ----------------------------------------------------------------
# The quotient certificate.
# ----------------------------------------------------------------

def _traces(init, trans, maxlen):
    out = {()}
    frontier = {(init, ())}
    for _ in range(maxlen):
        nxt = set()
        for state, trace in frontier:
            for (src, lab), dsts in trans.items():
                if src == state:
                    for d in dsts:
                        nt = trace + (lab,)
                        out.add(nt)
                        nxt.add((d, nt))
        frontier = nxt
        if not frontier:
            break
    return out


def _quotient(classes, trans):
    cls = {}
    for i, c in enumerate(classes):
        for s in c:
            cls[s] = i
    qtrans = {}
    for (s, lab), dsts in trans.items():
        for d in dsts:
            qtrans.setdefault((cls[s], lab), set()).add(cls[d])
    return qtrans, cls


def _stable(classes, trans, obs):
    cls = {}
    for i, c in enumerate(classes):
        for s in c:
            cls[s] = i
    for c in classes:
        if len({obs[s] for s in c}) > 1:
            return False
        labs = {lab for (s, lab) in trans if s in c}
        for lab in labs:
            per = [{cls[d] for d in trans.get((s, lab), set())}
                   for s in c]
            if any(p != per[0] for p in per):
                return False
    return True


class TestQuotientCertificate(unittest.TestCase):

    def test_claim_model_quotient(self):
        trans = {(0, "c"): {1, 2}, (1, "d"): {3}, (2, "d"): {4}}
        obs = {0: (0, 0), 1: (1, 1), 2: (1, 1), 3: (2, 1), 4: (2, 1)}
        classes = [{0}, {1, 2}, {3, 4}]
        self.assertTrue(_stable(classes, trans, obs))
        self.assertEqual([obs[s] for s in [0, 1, 3]],
                         [(0, 0), (1, 1), (2, 1)])
        qtrans, cls = _quotient(classes, trans)
        self.assertEqual(_traces(0, trans, 4), _traces(0, qtrans, 4))

    def test_negative_control(self):
        trans = {("s", "a"): {"q0"}, ("s", "b"): {"q1"},
                 ("q1", "c"): {"r"}}
        obs = {"s": 0, "q0": 1, "q1": 1, "r": 2}
        classes = [{"s"}, {"q0", "q1"}, {"r"}]
        self.assertFalse(_stable(classes, trans, obs))
        qtrans, _ = _quotient(classes, trans)
        self.assertIn(("a", "c"), _traces(0, qtrans, 3))
        self.assertNotIn(("a", "c"), _traces("s", trans, 3))

    def test_refined_partitions_preserve_traces(self):
        rng = random.Random(41)
        for _ in range(150):
            n = 6
            labs = ["a", "b", "c"]
            trans = {}
            for s in range(n):
                for lab in labs:
                    if rng.random() < 0.5:
                        trans[(s, lab)] = {
                            rng.randrange(n)
                            for _ in range(rng.randint(1, 2))}
            obs = {s: rng.randint(0, 2) for s in range(n)}
            part = [set(range(n))]
            while True:
                cls = {}
                for i, c in enumerate(part):
                    for s in c:
                        cls[s] = i
                newpart = []
                changed = False
                for c in part:
                    groups = {}
                    for s in c:
                        sig = (obs[s], tuple(sorted(
                            (lab, tuple(sorted(
                                cls[d] for d in trans.get((s, lab), set()))))
                            for lab in {l for (ss, l) in trans if ss == s})))
                        groups.setdefault(sig, set()).add(s)
                    if len(groups) > 1:
                        changed = True
                    newpart.extend(groups.values())
                part = newpart
                if not changed:
                    break
            self.assertTrue(_stable(part, trans, obs))
            qtrans, cls = _quotient(part, trans)
            self.assertEqual(_traces(0, trans, 5),
                             _traces(cls[0], qtrans, 5))


# ----------------------------------------------------------------
# Collision counting and the B(10) arithmetic.
# ----------------------------------------------------------------

class TestCollisionCounting(unittest.TestCase):

    def test_counting_inequality_random_families(self):
        rng = random.Random(53)
        for _ in range(1500):
            n = 8
            fam = {frozenset([i]) for i in range(n)}
            for s in range(2, 6):
                for comb in itertools.combinations(range(n), s):
                    if rng.random() < 0.1:
                        fam.add(frozenset(comb))
            fam = list(fam)
            b = len(fam)
            total_size = sum(len(a) for a in fam)
            pairs = sum(1 for a in fam if len(a) == 2)
            unions = set(fam)
            for a, bb in itertools.combinations(fam, 2):
                unions.add(a | bb)
            slots = b * (b + 1) // 2
            self.assertLessEqual(
                len(unions), slots - (total_size - n) - pairs)

    def test_b10_arithmetic_given_premise(self):
        self.assertEqual(47 * 48 // 2 - 94 - 12, 1022)
        for b in range(1, 48):
            pmin = max(0, math.ceil((130 - b) / 7))
            if pmin > 45:
                continue
            self.assertLessEqual(b * (b + 1) // 2 - 2 * b - pmin, 1022)


# ----------------------------------------------------------------
# The selector deletion arithmetic.
# ----------------------------------------------------------------

class TestSelectorArithmetic(unittest.TestCase):

    def test_deletion_step_for_all_h(self):
        for h in range(1, 20001):
            n = 4 * h + 1
            e = 4 * h + 3
            self.assertGreater(3 * e, 3 * n)
            val = 1 + Fraction(n - 1 + e - 4, 4)
            self.assertEqual(val, 2 * h + Fraction(3, 4))
            self.assertLess(val, 2 * h + 1)


if __name__ == "__main__":
    unittest.main()
