"""Tests for the finite toy map (runner/tools/toy_map.py).

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

The map is an executable miniature of candidate C's (c, d)
plane: U0, a tiny deterministic interpreter; a finite CNF
grammar enumerated completely; and the candidate A0(c, d)
checked over the whole domain. These tests pin the U0
specification, the domain's completeness, the 3 cell states,
and the monotonicity property the map exists to show: for
the same formula and the same interpreter, raising c or d
never removes a program or a step.
"""
import hashlib
import itertools
import json
import string
import unittest

from runner.tools import toy_map as TM

FORMULAS = TM.all_formulas()
RECORD = None


def setUpModule():
    global RECORD
    RECORD = TM.run_grid()


def _formula(*clauses):
    return tuple(sorted(clauses))


X0 = ((TM.POSITIVE, TM.ABSENT, TM.ABSENT),)
NOT_X0 = ((TM.NEGATIVE, TM.ABSENT, TM.ABSENT),)
X2 = ((TM.ABSENT, TM.ABSENT, TM.POSITIVE),)
X0_AND_X1 = _formula(
    (TM.POSITIVE, TM.ABSENT, TM.ABSENT),
    (TM.ABSENT, TM.POSITIVE, TM.ABSENT))
CONTRADICTION = _formula(
    (TM.POSITIVE, TM.ABSENT, TM.ABSENT),
    (TM.NEGATIVE, TM.ABSENT, TM.ABSENT))


class TestDomain(unittest.TestCase):
    def test_domain_is_complete_and_counted(self):
        self.assertEqual(len(FORMULAS), 2952)
        self.assertEqual(len(FORMULAS), 1 + 26 + 325 + 2600)
        self.assertEqual(len(set(FORMULAS)), 2952)

    def test_every_formula_within_N(self):
        for formula in FORMULAS:
            self.assertLessEqual(
                TM.encoded_length(formula), TM.MAX_ENCODED_LENGTH)
            self.assertEqual(
                len(TM.encode(formula)), TM.encoded_length(formula))

    def test_clause_universe_is_26(self):
        self.assertEqual(len(TM.all_clauses()), 26)


class TestEncoding(unittest.TestCase):
    def test_round_trip_over_the_whole_domain(self):
        for formula in FORMULAS:
            self.assertEqual(TM.decode(TM.encode(formula)), formula)

    def test_decode_rejects_the_11_code(self):
        with self.assertRaises(ValueError):
            TM.decode("01" + "11" + "0000")

    def test_decode_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            TM.decode("01" + "010000" + "0")
        with self.assertRaises(ValueError):
            TM.decode("01" + "01000")

    def test_decode_rejects_non_binary_and_empty(self):
        for bad in ("", "0", "012", "ab", "01 0000"):
            with self.assertRaises(ValueError):
                TM.decode(bad)

    def test_decode_bookended_encodings_always_rejected(self):
        # The bookend rule: every ASCII symbol, front and back,
        # around a real encoding must never decode.
        good = TM.encode(X0)
        symbols = "".join(
            ch for ch in string.printable if ch not in "01")
        for ch in symbols:
            with self.assertRaises(ValueError):
                TM.decode(ch + good)
            with self.assertRaises(ValueError):
                TM.decode(good + ch)
            with self.assertRaises(ValueError):
                TM.decode(ch + good + ch)
        for edge in ("\x00", "\t", "\r", "\n"):
            with self.assertRaises(ValueError):
                TM.decode(edge + good + edge)

    def test_decode_rejects_unsorted_or_duplicated_clauses(self):
        clause_a = (TM.POSITIVE, TM.ABSENT, TM.ABSENT)
        clause_b = (TM.ABSENT, TM.POSITIVE, TM.ABSENT)
        # Canonical order sorts clause_b before clause_a, so
        # clause_a first is not a legal encoding.
        bits = "10" + TM.encode((clause_a,))[2:] + TM.encode((clause_b,))[2:]
        with self.assertRaises(ValueError):
            TM.decode(bits)
        bits = "10" + TM.encode((clause_a,))[2:] + TM.encode((clause_a,))[2:]
        with self.assertRaises(ValueError):
            TM.decode(bits)


class TestU0AndVerifier(unittest.TestCase):
    def test_verifier_truth_table_known_formulas(self):
        self.assertEqual(TM.satisfying_assignments(()),
                         list(itertools.product((0, 1), repeat=3)))
        self.assertEqual(TM.satisfying_assignments(CONTRADICTION), [])
        self.assertIn((0, 0, 1), TM.satisfying_assignments(X2))
        self.assertNotIn((0, 0, 0), TM.satisfying_assignments(X2))
        self.assertIn((1, 0, 0), TM.satisfying_assignments(X0))
        self.assertIn((0, 0, 0), TM.satisfying_assignments(NOT_X0))

    def test_u0_output_always_verifies_and_matches_truth_table(self):
        # For every formula and every program of length at most
        # 3, with steps enough, U0 returns exactly the decoded
        # assignment when the independent verifier says that
        # assignment satisfies the formula, and returns no
        # output otherwise. Both directions are asserted for
        # every program, with no skip: an earlier shape of this
        # test continued past every None output, and a U0 that
        # never outputs anything passed it untouched.
        for formula in FORMULAS:
            for length in range(4):
                for value in range(2 ** length):
                    output, _ = TM.u0_run(value, length, formula, 99)
                    decoded = tuple(
                        (value >> var) & 1 if var < length else 0
                        for var in range(TM.VARIABLE_COUNT))
                    if TM.verify_witness(formula, decoded):
                        self.assertEqual(output, decoded)
                    else:
                        self.assertIsNone(output)

    def test_u0_step_counter_counts_clause_checks(self):
        output, steps = TM.u0_run(0b011, 3, X0_AND_X1, 99)
        self.assertEqual(output, (1, 1, 0))
        self.assertEqual(steps, 2)
        # A falsified first clause costs exactly 1 step.
        output, steps = TM.u0_run(0, 0, X0_AND_X1, 99)
        self.assertIsNone(output)
        self.assertEqual(steps, 1)

    def test_u0_step_limit_cuts_the_run(self):
        output, steps = TM.u0_run(0b011, 3, X0_AND_X1, 1)
        self.assertIsNone(output)
        self.assertEqual(steps, 1)

    def test_u0_is_deterministic(self):
        for formula in (X0, X2, X0_AND_X1, CONTRADICTION):
            first = TM.u0_run(5, 3, formula, 7)
            for _ in range(5):
                self.assertEqual(TM.u0_run(5, 3, formula, 7), first)


class TestCapsAndBudgets(unittest.TestCase):
    def test_cap_and_budget_values(self):
        # n = 8 for 1 clause: log2(10) is between 3 and 4.
        self.assertEqual(TM.program_cap(X0, 0), 0)
        self.assertEqual(TM.program_cap(X0, 1), 3)
        self.assertEqual(TM.program_cap(X0, 2), 6)
        self.assertEqual(TM.step_budget(X0, 0), 1)
        self.assertEqual(TM.step_budget(X0, 1), 10)
        self.assertEqual(TM.step_budget(X0, 2), 100)

    def test_caps_and_budgets_never_shrink(self):
        for formula in FORMULAS[::53]:
            for c in (0, 1):
                self.assertLessEqual(TM.program_cap(formula, c),
                                     TM.program_cap(formula, c + 1))
            for d in (0, 1):
                self.assertLessEqual(TM.step_budget(formula, d),
                                     TM.step_budget(formula, d + 1))


class TestCandidateSearch(unittest.TestCase):
    def test_finds_the_witness_when_the_pair_permits_it(self):
        result = TM.candidate_search(X2, 1, 1)
        self.assertTrue(result["found"])
        self.assertEqual(result["witness_assignment"], (0, 0, 1))
        self.assertTrue(TM.verify_witness(
            X2, result["witness_assignment"]))

    def test_zero_c_reaches_only_the_all_zero_assignment(self):
        self.assertFalse(TM.candidate_search(X0, 0, 2)["found"])
        self.assertTrue(TM.candidate_search(NOT_X0, 0, 2)["found"])

    def test_zero_d_starves_a_two_clause_formula(self):
        self.assertFalse(TM.candidate_search(X0_AND_X1, 2, 0)["found"])
        self.assertTrue(TM.candidate_search(X0_AND_X1, 2, 1)["found"])

    def test_failed_search_enumerates_every_permitted_program(self):
        result = TM.candidate_search(X0, 0, 2)
        cap = TM.program_cap(X0, 0)
        self.assertEqual(result["programs_run"], 2 ** (cap + 1) - 1)


class TestProgramBudgetEnforcement(unittest.TestCase):
    """The per cell program budget is a hard limit, checked
    before every program. The control is ChatGPT's, from the
    signed reviews of 2026-11-23: (x0) and (x1) at c = 2,
    d = 0 with a per cell budget of 1 reported UNKNOWN after
    511 programs, because the budget was checked only after
    a whole formula's search completed."""

    def test_the_statuses_are_three_and_distinct(self):
        self.assertEqual(len({TM.FOUND, TM.EXHAUSTED, TM.STOPPED}), 3)

    def test_the_control_from_the_review(self):
        cell = TM.evaluate_cell(2, 0, [X0_AND_X1], program_budget=1)
        self.assertEqual(cell["state"], TM.UNKNOWN)
        self.assertEqual(cell["programs_run"], 1)
        cell = TM.evaluate_cell(2, 0, [X0_AND_X1], program_budget=0)
        self.assertEqual(cell["state"], TM.UNKNOWN)
        self.assertEqual(cell["programs_run"], 0)

    def test_allowance_zero_stops_before_any_program(self):
        result = TM.candidate_search(
            X0_AND_X1, 2, 1, program_allowance=0)
        self.assertEqual(result["status"], TM.STOPPED)
        self.assertEqual(result["programs_run"], 0)
        self.assertFalse(result["found"])

    def test_allowance_one_runs_exactly_one_program(self):
        result = TM.candidate_search(
            X0_AND_X1, 2, 1, program_allowance=1)
        self.assertEqual(result["status"], TM.STOPPED)
        self.assertEqual(result["programs_run"], 1)

    def test_exactly_enough_allowance_finds_the_witness(self):
        # The witness (1, 1, 0) is the 7th program in the
        # enumeration order at c = 2, d = 1.
        result = TM.candidate_search(
            X0_AND_X1, 2, 1, program_allowance=7)
        self.assertEqual(result["status"], TM.FOUND)
        self.assertTrue(result["found"])
        self.assertEqual(result["programs_run"], 7)
        self.assertEqual(result["witness_assignment"], (1, 1, 0))

    def test_one_short_of_the_witness_is_stopped_not_exhausted(self):
        result = TM.candidate_search(
            X0_AND_X1, 2, 1, program_allowance=6)
        self.assertEqual(result["status"], TM.STOPPED)
        self.assertEqual(result["programs_run"], 6)
        self.assertFalse(result["found"])

    def test_exhausted_needs_the_whole_enumeration(self):
        # At d = 0 no program can succeed on a 2 clause
        # formula, and the permitted enumeration at c = 2
        # is 511 programs.
        result = TM.candidate_search(
            X0_AND_X1, 2, 0, program_allowance=511)
        self.assertEqual(result["status"], TM.EXHAUSTED)
        self.assertEqual(result["programs_run"], 511)
        result = TM.candidate_search(
            X0_AND_X1, 2, 0, program_allowance=510)
        self.assertEqual(result["status"], TM.STOPPED)
        self.assertEqual(result["programs_run"], 510)

    def test_fail_comes_only_from_a_completed_enumeration(self):
        cell = TM.evaluate_cell(2, 0, [X0_AND_X1], program_budget=511)
        self.assertEqual(cell["state"], TM.FAIL)
        self.assertEqual(cell["programs_run"], 511)
        cell = TM.evaluate_cell(2, 0, [X0_AND_X1], program_budget=510)
        self.assertEqual(cell["state"], TM.UNKNOWN)
        self.assertEqual(cell["programs_run"], 510)

    def test_programs_run_never_pass_the_budget(self):
        for budget in (0, 1, 2, 3, 10, 100, 1000):
            cell = TM.evaluate_cell(2, 2, FORMULAS, program_budget=budget)
            self.assertLessEqual(cell["programs_run"], budget)
            self.assertEqual(cell["state"], TM.UNKNOWN)

    def test_no_allowance_keeps_the_unbounded_behaviour(self):
        result = TM.candidate_search(X0_AND_X1, 2, 1)
        self.assertEqual(result["status"], TM.FOUND)
        self.assertEqual(result["programs_run"], 7)
        result = TM.candidate_search(X0_AND_X1, 2, 0)
        self.assertEqual(result["status"], TM.EXHAUSTED)
        self.assertEqual(result["programs_run"], 511)


class TestGridStates(unittest.TestCase):
    def _cell(self, c, d):
        for cell in RECORD["cells"]:
            if cell["c"] == c and cell["d"] == d:
                return cell
        self.fail("cell missing")

    def test_the_measured_staircase(self):
        expected = {
            (0, 0): TM.FAIL, (1, 0): TM.FAIL, (2, 0): TM.FAIL,
            (0, 1): TM.FAIL, (1, 1): TM.PASS, (2, 1): TM.PASS,
            (0, 2): TM.FAIL, (1, 2): TM.PASS, (2, 2): TM.PASS,
        }
        for pair, state in expected.items():
            self.assertEqual(self._cell(*pair)["state"], state, pair)

    def test_fail_cells_name_a_real_counterexample(self):
        for cell in RECORD["cells"]:
            if cell["state"] != TM.FAIL:
                continue
            counter = cell["counterexample"]
            formula = TM.decode(counter["encoding"])
            self.assertIn(tuple(counter["satisfying_assignment"]),
                          TM.satisfying_assignments(formula))
            # The negative is the enumeration, checked again
            # here in full: no permitted program succeeds.
            again = TM.candidate_search(formula, cell["c"], cell["d"])
            self.assertFalse(again["found"])
            self.assertEqual(again["programs_run"],
                             counter["programs_run_for_formula"])

    def test_pass_cells_checked_satisfiable_formulas(self):
        satisfiable = sum(
            1 for formula in FORMULAS if TM.satisfying_assignments(formula))
        for cell in RECORD["cells"]:
            if cell["state"] == TM.PASS:
                self.assertEqual(cell["formulas_checked"], satisfiable)

    def test_unknown_when_the_budget_stops_the_work(self):
        cell = TM.evaluate_cell(2, 2, FORMULAS, program_budget=10)
        self.assertEqual(cell["state"], TM.UNKNOWN)
        self.assertIsNone(cell["counterexample"])
        self.assertEqual(cell["programs_run"], 10)

    def test_no_unknown_at_the_stated_budget(self):
        for cell in RECORD["cells"]:
            self.assertNotEqual(cell["state"], TM.UNKNOWN)

    def test_states_are_three_and_distinct(self):
        self.assertEqual(len({TM.FAIL, TM.PASS, TM.UNKNOWN}), 3)


class TestMonotonicity(unittest.TestCase):
    PAIRS = [(c, d) for d in TM.GRID_D for c in TM.GRID_C]

    def _weaker(self, a, b):
        return a[0] <= b[0] and a[1] <= b[1] and a != b

    def test_success_persists_upward_per_formula(self):
        sample = FORMULAS[::37] + [X0, X2, X0_AND_X1, CONTRADICTION]
        for formula in sample:
            found = {pair: TM.candidate_search(formula, *pair)["found"]
                     for pair in self.PAIRS}
            for weaker in self.PAIRS:
                for stronger in self.PAIRS:
                    if self._weaker(weaker, stronger) and found[weaker]:
                        self.assertTrue(
                            found[stronger],
                            "%s found at %s but not at %s" % (
                                TM.formula_name(formula), weaker, stronger))

    def test_counterexamples_defeat_every_weaker_pair(self):
        for cell in RECORD["cells"]:
            if cell["state"] != TM.FAIL:
                continue
            formula = TM.decode(cell["counterexample"]["encoding"])
            for pair in self.PAIRS:
                if self._weaker(pair, (cell["c"], cell["d"])):
                    self.assertFalse(
                        TM.candidate_search(formula, *pair)["found"],
                        "%s defeats %s, so it must defeat %s" % (
                            TM.formula_name(formula),
                            (cell["c"], cell["d"]), pair))

    def test_the_cell_staircase_is_monotone(self):
        states = {(cell["c"], cell["d"]): cell["state"]
                  for cell in RECORD["cells"]}
        for weaker in self.PAIRS:
            for stronger in self.PAIRS:
                if not self._weaker(weaker, stronger):
                    continue
                if states[weaker] == TM.PASS:
                    self.assertEqual(states[stronger], TM.PASS)
                if states[stronger] == TM.FAIL:
                    self.assertEqual(states[weaker], TM.FAIL)


class TestProvenanceAndFigure(unittest.TestCase):
    def test_record_carries_the_provenance(self):
        for key in ("u0_version", "grammar", "max_encoded_length_N",
                    "domain_size", "grid_c", "grid_d",
                    "program_cap_rule", "step_budget_rule",
                    "enumeration_rule", "program_budget_per_cell",
                    "witness_verification", "cells",
                    "total_programs_run", "total_steps_used",
                    "data_sha256"):
            self.assertIn(key, RECORD)
        self.assertEqual(RECORD["u0_version"], TM.U0_VERSION)
        self.assertEqual(RECORD["domain_size"], 2952)
        self.assertEqual(
            RECORD["total_programs_run"],
            sum(cell["programs_run"] for cell in RECORD["cells"]))

    def test_data_hash_recomputes(self):
        canonical = json.dumps(
            {key: value for key, value in RECORD.items()
             if key not in ("wall_seconds", "data_sha256")},
            sort_keys=True, default=str)
        self.assertEqual(
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            RECORD["data_sha256"])

    def test_svg_shapes_match_the_states(self):
        svg = TM.render_svg(RECORD)
        states = [cell["state"] for cell in RECORD["cells"]]
        self.assertEqual(svg.count("<circle"), states.count(TM.PASS))
        self.assertEqual(svg.count("<rect x="), states.count(TM.FAIL))
        self.assertEqual(svg.count("M ") >= states.count(TM.FAIL), True)
        self.assertIn(RECORD["data_sha256"], svg)
        self.assertIn("nothing", svg)  # the honesty line is on the figure


if __name__ == "__main__":
    unittest.main()
