"""The finite toy map: an executable, fully enumerated miniature
of candidate C's (c, d) plane.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

Candidate C (docs/infrastructure-documents/project/
three-chart-candidates-2026-11-23.md) defines, for a universal
interpreter U, the machine A(c, d): enumerate every U program
of length at most c log2(n + 2), run each on the formula for at
most (n + 2)^d steps, and verify any satisfying assignment
produced. This module builds the finite version of that idea
as a research instrument. The interpreter here is U0, a tiny
deterministic teaching and control machine. It is NOT the
universal machine of the theorem, and nothing this module
computes says anything automatic about the real universal
interpreter or about P versus NP. What it does give is a
small domain where every claim on the map is backed by a
complete, reproducible enumeration whose cost is reported.

U0, version U0-1.0, specified completely:

- A program is a finite bit string. Program bits are read as
  a candidate assignment: bit i of the program is the value
  of variable x_i, and variables past the end of the program
  take the value 0.
- U0 runs a program on a formula clause by clause, in the
  formula's clause order. Each clause check costs exactly 1
  step on U0's step counter. If a clause is falsified by the
  candidate assignment, U0 halts at once with no output. If
  every clause passes, U0 outputs the candidate assignment.
- A run may spend at most a stated step limit. A run that
  would need a step beyond the limit is cut, with no output.
  Decoding a program costs no steps. U0 is deterministic:
  same program, same formula, same limit, same result.

The formula grammar, specified completely:

- Formulas are CNF over exactly 3 variables, x0, x1, x2.
- A clause is a choice, per variable, of absent, positive or
  negative: 3 codes per variable, 26 non empty clauses.
- A formula is a set of distinct clauses in canonical
  (sorted) order, of size 0 to 3. The empty formula is
  satisfiable by every assignment and needs 0 steps.
- The encoded length of a formula is n = 2 + 6m bits, where
  m is the clause count: a 2 bit clause count header, then
  6 bits per clause, 2 bits per variable (00 absent, 01
  positive, 10 negative; 11 never occurs). The maximum
  encoded length is N = 20. The domain holds every formula
  of the grammar: 1 + 26 + 325 + 2600 = 2952 formulas,
  enumerated completely by this module.

Satisfiability of each formula is settled independently of
U0 by a complete truth table over the 8 assignments, using
the witness verifier below, which is a separate code path
from U0's own clause evaluation. Any assignment U0 outputs
is verified again by that verifier before it counts.

The candidate A0(c, d) mirrors A(c, d) with U0 in place of U:

- Program cap: floor(c * log2(n + 2)) bits.
- Step budget: (n + 2)^d steps per program run.
- Enumeration order: program length ascending, then program
  value ascending. The search stops at the first program
  whose output verifies.

Cell states, over the whole named domain:

- FAIL: a named satisfiable formula, a named satisfying
  assignment for it, and the complete bounded enumeration
  together show A0(c, d) found no witness for that formula.
  Checking this negative means checking the enumeration;
  the satisfying assignment alone does not establish it.
- PASS UP TO N: every satisfiable formula in the domain was
  checked and A0(c, d) found a verified witness for each.
- UNKNOWN: a stated resource limit (a per cell program
  budget) stopped the enumeration before the domain was
  completely checked. A timeout or a budget stop is UNKNOWN,
  never a counterexample.

Monotonicity, the property the map exists to show: for the
same formula and the same interpreter, raising c or d never
removes a program or a step, because both caps are
non decreasing in each constant and the enumeration order is
fixed. So a counterexample at a stronger pair defeats every
weaker pair, and a success at a weaker pair persists at
every stronger pair. The grid is a discrete monotone
staircase, with UNKNOWN cells where work is incomplete.
"""

import hashlib
import itertools
import json
import math
import time

U0_VERSION = "U0-1.0"
VARIABLE_COUNT = 3
MAX_CLAUSES = 3
MAX_ENCODED_LENGTH = 20  # N: 2 + 6 * MAX_CLAUSES
GRID_C = (0, 1, 2)
GRID_D = (0, 1, 2)
DEFAULT_PROGRAM_BUDGET = 10_000_000

FAIL = "FAIL"
PASS = "PASS UP TO N"
UNKNOWN = "UNKNOWN"

# Clause literal codes.
ABSENT = 0
POSITIVE = 1
NEGATIVE = 2


def all_clauses():
    """Every non empty clause of the grammar, in canonical order."""
    clauses = []
    for codes in itertools.product(
            (ABSENT, POSITIVE, NEGATIVE), repeat=VARIABLE_COUNT):
        if any(code != ABSENT for code in codes):
            clauses.append(codes)
    return clauses


def all_formulas():
    """Every formula of the grammar, enumerated completely.

    A formula is a tuple of distinct clauses in canonical
    order, of size 0 to MAX_CLAUSES.
    """
    clauses = all_clauses()
    formulas = []
    for size in range(MAX_CLAUSES + 1):
        for combo in itertools.combinations(clauses, size):
            formulas.append(combo)
    return formulas


def encoded_length(formula):
    """The encoded length n of a formula, in bits."""
    return 2 + 6 * len(formula)


def encode(formula):
    """The complete binary encoding of a formula, as a string
    of 0 and 1 characters: a 2 bit clause count header, then
    6 bits per clause, 2 bits per variable."""
    parts = [format(len(formula), "02b")]
    code_bits = {ABSENT: "00", POSITIVE: "01", NEGATIVE: "10"}
    for clause in formula:
        for code in clause:
            parts.append(code_bits[code])
    return "".join(parts)


def decode(bits):
    """The inverse of encode. Raises ValueError on any string
    that is not the encoding of a formula of the grammar."""
    if not isinstance(bits, str) or any(ch not in "01" for ch in bits):
        raise ValueError("encoding must be a string of 0 and 1")
    if len(bits) < 2:
        raise ValueError("encoding too short for the header")
    count = int(bits[:2], 2)
    if count > MAX_CLAUSES:
        raise ValueError("clause count outside the grammar")
    if len(bits) != 2 + 6 * count:
        raise ValueError("encoding length does not match its header")
    bit_codes = {"00": ABSENT, "01": POSITIVE, "10": NEGATIVE}
    clauses = []
    pos = 2
    for _ in range(count):
        clause = []
        for _ in range(VARIABLE_COUNT):
            pair = bits[pos:pos + 2]
            pos += 2
            if pair not in bit_codes:
                raise ValueError("literal code 11 never occurs")
            clause.append(bit_codes[pair])
        clause = tuple(clause)
        if all(code == ABSENT for code in clause):
            raise ValueError("the empty clause is outside the grammar")
        clauses.append(clause)
    if clauses != sorted(clauses) or len(set(clauses)) != len(clauses):
        raise ValueError("clauses must be distinct and in canonical order")
    return tuple(clauses)


def clause_falsified(clause, assignment):
    """U0's own clause evaluation: a clause is falsified when
    every literal in it is false under the assignment."""
    for var, code in enumerate(clause):
        if code == POSITIVE and assignment[var] == 1:
            return False
        if code == NEGATIVE and assignment[var] == 0:
            return False
    return True


def u0_run(program_value, program_length, formula, step_limit):
    """Run U0 on one program. Returns (output, steps_used),
    where output is the candidate assignment tuple if U0
    produced one within the step limit, else None."""
    assignment = tuple(
        (program_value >> var) & 1 if var < program_length else 0
        for var in range(VARIABLE_COUNT))
    steps = 0
    for clause in formula:
        if steps >= step_limit:
            return None, steps
        steps += 1
        if clause_falsified(clause, assignment):
            return None, steps
    return assignment, steps


def verify_witness(formula, assignment):
    """The independent witness verifier. A clause is satisfied
    when at least one of its literals is true; a formula is
    satisfied when every clause is satisfied. This is a
    separate code path from U0's falsification check."""
    if len(assignment) != VARIABLE_COUNT:
        return False
    if any(value not in (0, 1) for value in assignment):
        return False
    for clause in formula:
        satisfied = any(
            (code == POSITIVE and assignment[var] == 1) or
            (code == NEGATIVE and assignment[var] == 0)
            for var, code in enumerate(clause)
            if code != ABSENT)
        if not satisfied:
            return False
    return True


def satisfying_assignments(formula):
    """The complete truth table check: every assignment of the
    3 variables that satisfies the formula, by the verifier."""
    return [assignment
            for assignment in itertools.product((0, 1), repeat=VARIABLE_COUNT)
            if verify_witness(formula, assignment)]


def program_cap(formula, c):
    """The program length cap of A0(c, d) for this formula."""
    n = encoded_length(formula)
    return math.floor(c * math.log2(n + 2))


def step_budget(formula, d):
    """The per program step budget of A0(c, d) for this formula."""
    n = encoded_length(formula)
    return (n + 2) ** d


def candidate_search(formula, c, d):
    """A0(c, d) on one formula: enumerate the permitted
    programs in the stated order, run each under the step
    budget, and stop at the first whose output verifies.
    Returns a dict with the outcome and the exact cost."""
    cap = program_cap(formula, c)
    budget = step_budget(formula, d)
    programs_run = 0
    steps_used = 0
    for length in range(cap + 1):
        for value in range(2 ** length):
            programs_run += 1
            output, steps = u0_run(value, length, formula, budget)
            steps_used += steps
            if output is not None and verify_witness(formula, output):
                return {"found": True, "programs_run": programs_run,
                        "steps_used": steps_used,
                        "witness_program_length": length,
                        "witness_program_value": value,
                        "witness_assignment": output}
    return {"found": False, "programs_run": programs_run,
            "steps_used": steps_used, "witness_program_length": None,
            "witness_program_value": None, "witness_assignment": None}


def formula_name(formula):
    """A short human readable name for a formula."""
    if not formula:
        return "(empty formula)"
    names = []
    for clause in formula:
        literals = []
        for var, code in enumerate(clause):
            if code == POSITIVE:
                literals.append("x%d" % var)
            elif code == NEGATIVE:
                literals.append("~x%d" % var)
        names.append("(" + " | ".join(literals) + ")")
    return " & ".join(names)


def evaluate_cell(c, d, formulas, program_budget=DEFAULT_PROGRAM_BUDGET):
    """Evaluate one grid cell over the whole domain.

    Returns a dict with the cell state and its evidence. The
    program budget is the cell's resource limit: if the
    cumulative programs run would pass it before the domain
    is completely checked, the cell is UNKNOWN.
    """
    programs_total = 0
    steps_total = 0
    checked = 0
    for formula in formulas:
        witnesses = satisfying_assignments(formula)
        if not witnesses:
            continue
        result = candidate_search(formula, c, d)
        programs_total += result["programs_run"]
        steps_total += result["steps_used"]
        checked += 1
        if programs_total > program_budget:
            return {"c": c, "d": d, "state": UNKNOWN,
                    "reason": "program budget %d passed after %d "
                              "satisfiable formulas" % (program_budget, checked),
                    "programs_run": programs_total,
                    "steps_used": steps_total,
                    "formulas_checked": checked,
                    "counterexample": None}
        if not result["found"]:
            return {"c": c, "d": d, "state": FAIL,
                    "reason": "complete bounded enumeration found "
                              "no witness for a satisfiable formula",
                    "programs_run": programs_total,
                    "steps_used": steps_total,
                    "formulas_checked": checked,
                    "counterexample": {
                        "formula": formula_name(formula),
                        "encoding": encode(formula),
                        "satisfying_assignment": witnesses[0],
                        "programs_run_for_formula": result["programs_run"],
                        "steps_used_for_formula": result["steps_used"]}}
    return {"c": c, "d": d, "state": PASS,
            "reason": "every satisfiable formula in the domain "
                      "was checked and a verified witness found",
            "programs_run": programs_total,
            "steps_used": steps_total,
            "formulas_checked": checked,
            "counterexample": None}


def run_grid(program_budget=DEFAULT_PROGRAM_BUDGET):
    """Run the whole grid and build the provenance record."""
    formulas = all_formulas()
    started = time.perf_counter()
    cells = [evaluate_cell(c, d, formulas, program_budget)
             for d in GRID_D for c in GRID_C]
    elapsed = time.perf_counter() - started
    record = {
        "u0_version": U0_VERSION,
        "grammar": "CNF over x0, x1, x2; clauses are per variable "
                   "absent, positive or negative; formulas are sets "
                   "of at most %d distinct clauses in canonical "
                   "order" % MAX_CLAUSES,
        "max_encoded_length_N": MAX_ENCODED_LENGTH,
        "domain_size": len(formulas),
        "grid_c": list(GRID_C),
        "grid_d": list(GRID_D),
        "program_cap_rule": "floor(c * log2(n + 2)) bits",
        "step_budget_rule": "(n + 2)^d steps per program run",
        "enumeration_rule": "program length ascending, then "
                            "program value ascending; stop at "
                            "the first verified witness",
        "program_budget_per_cell": program_budget,
        "witness_verification": "independent verifier, complete "
                                "truth table over the 8 assignments",
        "cells": cells,
        "total_programs_run": sum(cell["programs_run"] for cell in cells),
        "total_steps_used": sum(cell["steps_used"] for cell in cells),
        "wall_seconds": round(elapsed, 3),
    }
    canonical = json.dumps(
        {key: value for key, value in record.items()
         if key != "wall_seconds"},
        sort_keys=True, default=str)
    record["data_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")).hexdigest()
    return record


def render_svg(record):
    """Render the grid figure from the actual enumeration
    record. The 3 states differ in shape as well as colour:
    PASS UP TO N is a circle, FAIL is a square carrying an X,
    UNKNOWN is a triangle."""
    cell_w, cell_h = 150, 110
    left, top = 90, 120
    width = left + cell_w * len(record["grid_c"]) + 30
    height = top + cell_h * len(record["grid_d"]) + 120
    by_pair = {(cell["c"], cell["d"]): cell for cell in record["cells"]}
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" '
        'height="%d" viewBox="0 0 %d %d">' % (width, height, width, height),
        "<title>The finite toy map: A0(c, d) over the complete "
        "domain of %d formulas, N = %d</title>" % (
            record["domain_size"], record["max_encoded_length_N"]),
        "<desc>Each cell is one fixed pair (c, d), classified by "
        "complete bounded enumeration under U0 %s. Circle: PASS "
        "UP TO N. Square with an X: FAIL, a checked "
        "counterexample. Triangle: UNKNOWN, work incomplete. "
        "Data sha256 %s.</desc>" % (
            record["u0_version"], record["data_sha256"]),
        '<rect width="%d" height="%d" fill="#101418"/>' % (width, height),
        '<text x="%d" y="40" fill="#f2f2f2" font-size="19" '
        'font-family="sans-serif">The finite toy map: A0(c, d), '
        'completely enumerated</text>' % left,
        '<text x="%d" y="64" fill="#c8c8c8" font-size="12.5" '
        'font-family="sans-serif">U0 %s, %d formulas, encoded '
        'length at most %d bits. Shapes carry the state, colour '
        'only repeats it.</text>' % (
            left, record["u0_version"], record["domain_size"],
            record["max_encoded_length_N"]),
        '<text x="%d" y="%d" fill="#f2f2f2" font-size="13" '
        'font-family="sans-serif">c, the program length '
        'constant, increasing right</text>' % (left, top - 28),
    ]
    for row, d in enumerate(record["grid_d"]):
        y = top + row * cell_h
        parts.append(
            '<text x="30" y="%d" fill="#f2f2f2" font-size="14" '
            'font-family="sans-serif">d = %d</text>' % (y + cell_h // 2, d))
        for col, c in enumerate(record["grid_c"]):
            x = left + col * cell_w
            cell = by_pair[(c, d)]
            cx, cy = x + cell_w // 2, y + cell_h // 2 - 8
            if cell["state"] == PASS:
                parts.append(
                    '<circle cx="%d" cy="%d" r="26" fill="#2e7d32"/>' % (cx, cy))
                label = "PASS UP TO N"
            elif cell["state"] == FAIL:
                parts.append(
                    '<rect x="%d" y="%d" width="52" height="52" '
                    'fill="#8e2f2f"/>' % (cx - 26, cy - 26))
                parts.append(
                    '<path d="M %d %d L %d %d M %d %d L %d %d" '
                    'stroke="#ffffff" stroke-width="3"/>' % (
                        cx - 16, cy - 16, cx + 16, cy + 16,
                        cx + 16, cy - 16, cx - 16, cy + 16))
                label = "FAIL"
            else:
                parts.append(
                    '<path d="M %d %d L %d %d L %d %d Z" '
                    'fill="#b8860b"/>' % (cx, cy - 28, cx - 28, cy + 24,
                                          cx + 28, cy + 24))
                label = "UNKNOWN"
            parts.append(
                '<text x="%d" y="%d" fill="#f2f2f2" font-size="12" '
                'text-anchor="middle" font-family="sans-serif">'
                "(%d, %d) %s</text>" % (cx, y + cell_h - 18, c, d, label))
            parts.append(
                '<text x="%d" y="%d" fill="#9a9a9a" font-size="10" '
                'text-anchor="middle" font-family="sans-serif">'
                "%d programs</text>" % (cx, y + cell_h - 4,
                                        cell["programs_run"]))
    legend_y = top + cell_h * len(record["grid_d"]) + 34
    parts.append(
        '<text x="%d" y="%d" fill="#c8c8c8" font-size="12" '
        'font-family="sans-serif">Total cost of the complete '
        'enumeration: %d programs run, %d steps. A timeout or a '
        'budget stop is UNKNOWN, never a counterexample.</text>' % (
            left, legend_y, record["total_programs_run"],
            record["total_steps_used"]))
    parts.append(
        '<text x="%d" y="%d" fill="#c8c8c8" font-size="12" '
        'font-family="sans-serif">The toy map says nothing '
        'automatic about the real universal interpreter or P '
        'versus NP.</text>' % (left, legend_y + 22))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    record = run_grid()
    svg = render_svg(record)
    if argv:
        with open(argv[0], "w", encoding="utf-8") as fh:
            fh.write(svg)
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, default=str)
    print(json.dumps(
        {"states": {("%d,%d" % (cell["c"], cell["d"])): cell["state"]
                    for cell in record["cells"]},
         "total_programs_run": record["total_programs_run"],
         "total_steps_used": record["total_steps_used"],
         "wall_seconds": record["wall_seconds"],
         "data_sha256": record["data_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
