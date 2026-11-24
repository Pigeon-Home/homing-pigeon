#!/usr/bin/env python3
"""The joining solver: prefix extension under a compressor.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

docs/infrastructure-documents/proofs/v4-the-joining-solver.md
states the construction, and runner/tools/joining_solver.py
is the artifact that embodies it. This file pins the finite
behaviour the page reports, exactly as the page's
supposition states it:

1. The exact compressor keeps the contract at every round,
   and on a fixed seed batch of 80 random 3-CNF instances
   on 10 variables (40 at 20 clauses, 40 at 43) its verdict
   agrees with brute force on every instance.
2. The keep first compressor breaks the contract and
   returns a wrong verdict on the unit clause family built
   to expose it, at widths 1, 4, and 16, at the first round
   whose extended list passes the width.
3. On the equality family of the examples page, the
   solver's retained counts under the exact compressor
   equal the family's residual counts, computed here from
   the definition: grouped order doubling to exactly 2^m
   at the cut, interleaved order never passing 3.

The conditional theorem the construction serves, Theorem 4
of properties.md, is not tested here. What is tested is
the finite record the page reports.
"""
import itertools
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.tools import joining_solver as JS  # noqa: E402

PAGE = os.path.join(
    ROOT, "docs", "infrastructure-documents", "proofs",
    "v4-the-joining-solver.md")
ORDER10 = tuple(range(1, 11))


def _random_3cnf(rng, nvars, nclauses):
    clauses = []
    for _ in range(nclauses):
        chosen = rng.sample(range(1, nvars + 1), 3)
        clauses.append(tuple(
            var if rng.random() < 0.5 else -var
            for var in chosen))
    return tuple(clauses)


class ExactCompressorBatchTest(unittest.TestCase):
    """The seeded batch: verdicts agree with brute force,
    and the contract holds at every round."""

    def test_batch_agrees_and_keeps_the_contract(self):
        rng = random.Random(20261123)
        instances = []
        for _ in range(40):
            instances.append(_random_3cnf(rng, 10, 20))
        for _ in range(40):
            instances.append(_random_3cnf(rng, 10, 43))
        self.assertEqual(len(instances), 80)
        satisfiable = 0
        for clauses in instances:
            result = JS.solve(clauses, ORDER10, JS.exact_compress)
            self.assertEqual(
                result.verdict,
                JS.verdict_brute_force(clauses, ORDER10),
                clauses)
            self.assertTrue(
                all(r.contract for r in result.rounds), clauses)
            if result.verdict:
                satisfiable += 1
                self.assertTrue(JS.satisfies(
                    clauses, ORDER10, result.witness))
        # The batch is a real mix, not a degenerate one.
        self.assertGreater(satisfiable, 0)
        self.assertLess(satisfiable, 80)


class KeepFirstTest(unittest.TestCase):
    """The unit clause on the first variable, padded with
    free variables: every live prefix sits in the second
    half of the extended list, so keep first drops them
    all at the first round whose list passes the width."""

    def _run(self, width, nvars):
        clauses = ((1,),)
        order = tuple(range(1, nvars + 1))
        return clauses, order, JS.solve(
            clauses, order, JS.keep_first(width))

    def test_width_1_breaks_at_the_first_round(self):
        clauses, order, result = self._run(1, 3)
        self.assertTrue(JS.verdict_brute_force(clauses, order))
        self.assertFalse(result.verdict)
        self.assertFalse(result.rounds[0].contract)

    def test_width_4_breaks_at_the_third_round(self):
        clauses, order, result = self._run(4, 6)
        self.assertTrue(JS.verdict_brute_force(clauses, order))
        self.assertFalse(result.verdict)
        self.assertTrue(result.rounds[0].contract)
        self.assertTrue(result.rounds[1].contract)
        self.assertFalse(result.rounds[2].contract)

    def test_width_16_breaks_at_the_fifth_round(self):
        clauses, order, result = self._run(16, 8)
        self.assertTrue(JS.verdict_brute_force(clauses, order))
        self.assertFalse(result.verdict)
        for rnd in result.rounds[:4]:
            self.assertTrue(rnd.contract)
        self.assertFalse(result.rounds[4].contract)

    def test_exact_compressor_survives_the_same_instances(self):
        for width, nvars in ((1, 3), (4, 6), (16, 8)):
            clauses = ((1,),)
            order = tuple(range(1, nvars + 1))
            result = JS.solve(clauses, order, JS.exact_compress)
            self.assertTrue(result.verdict)
            self.assertTrue(
                all(r.contract for r in result.rounds))


def _equality_cnf(m):
    clauses = []
    for i in range(m):
        x = i + 1
        y = m + 1 + i
        clauses.append((-x, y))
        clauses.append((x, -y))
    return tuple(clauses)


def _grouped_order(m):
    return tuple(range(1, 2 * m + 1))


def _interleaved_order(m):
    order = []
    for i in range(m):
        order.append(i + 1)
        order.append(m + 1 + i)
    return tuple(order)


def _true_residual_counts(clauses, order):
    """Distinct residuals at each cut, from the definition:
    a residual is the set of completions of the unread
    variables that satisfy every clause under 1 prefix."""
    counts = []
    for cut in range(len(order) + 1):
        prefix_vars = order[:cut]
        rest = order[cut:]
        seen = set()
        for bits in itertools.product(
                (0, 1), repeat=len(prefix_vars)):
            prefix = dict(zip(prefix_vars, bits))
            completions = set()
            for rbits in itertools.product((0, 1), repeat=len(rest)):
                full = dict(prefix)
                full.update(zip(rest, rbits))
                if all(
                    any(
                        (full[abs(lit)] == 1) == (lit > 0)
                        for lit in clause)
                    for clause in clauses):
                    completions.add(rbits)
            seen.add(frozenset(completions))
        counts.append(len(seen))
    return counts


class EqualityFamilyTest(unittest.TestCase):
    """The solver's retained counts are the family's
    residual counts, under both orders."""

    def test_retained_counts_equal_residual_counts(self):
        for m in (1, 2, 3, 4):
            clauses = _equality_cnf(m)
            for order in (_grouped_order(m), _interleaved_order(m)):
                result = JS.solve(clauses, order, JS.exact_compress)
                retained = [1] + [r.after for r in result.rounds]
                self.assertEqual(
                    retained,
                    _true_residual_counts(clauses, order),
                    (m, order))
                self.assertTrue(result.verdict)
                self.assertTrue(
                    all(r.contract for r in result.rounds))

    def test_grouped_cut_is_two_to_the_m(self):
        for m in (1, 2, 3, 4):
            result = JS.solve(
                _equality_cnf(m), _grouped_order(m),
                JS.exact_compress)
            retained = [1] + [r.after for r in result.rounds]
            self.assertEqual(retained[m], 2 ** m)

    def test_interleaved_never_passes_three(self):
        for m in (1, 2, 3, 4):
            result = JS.solve(
                _equality_cnf(m), _interleaved_order(m),
                JS.exact_compress)
            retained = [1] + [r.after for r in result.rounds]
            self.assertLessEqual(max(retained), 3)
            if m >= 2:
                self.assertEqual(max(retained), 3)


class ResidualKeyTest(unittest.TestCase):

    def test_a_falsified_prefix_has_the_dead_key(self):
        clauses = ((1,), (2,))
        order = (1, 2)
        self.assertEqual(
            JS.residual_key(clauses, order, (0,)), JS.DEAD)

    def test_same_key_same_completions(self):
        clauses = ((1, 2), (-1, 3), (-2, -3))
        order = (1, 2, 3)
        by_key = {}
        for bits in itertools.product((0, 1), repeat=2):
            key = JS.residual_key(clauses, order, bits)
            by_key.setdefault(key, []).append(bits)
        for key, prefixes in by_key.items():
            if key is JS.DEAD:
                continue
            completion_sets = []
            for prefix in prefixes:
                found = set()
                for last in (0, 1):
                    if JS.satisfies(clauses, order, prefix + (last,)):
                        found.add(last)
                completion_sets.append(found)
            for other in completion_sets[1:]:
                self.assertEqual(other, completion_sets[0])


class JoiningSolverPageTest(unittest.TestCase):

    def test_page_names_the_artifact_and_its_supposition(self):
        with open(PAGE, encoding="utf-8") as handle:
            text = handle.read()
        for phrase in (
            "## Supposition, written before the tests ran",
            "runner/tools/joining_solver.py",
            "runner/tests/test_v4_the_joining_solver.py",
            "Theorem 4",
            "The contract is the premise",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
