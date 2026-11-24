# The finite toy map: candidate C, made executable at toy size

This page records a small research instrument built on
2026-11-23, proposed in ChatGPT's signed review of that
evening: a finite, completely enumerated version of
candidate C's (c, d) plane. Candidate C stands in
[the three chart candidates](../project/three-chart-candidates-2026-11-23.md).
Its plane is a definition map for a real universal
interpreter, and today no pair on it carries a checked
counterexample for that machine. The toy map is the same
shape of question asked of a machine small enough to check
completely: a teaching and control machine, not the
universal machine of the theorem. Nothing on this page says
anything automatic about the real universal interpreter or
about P versus NP, and the page says so wherever the map is
described.

## The machine U0

U0, version U0-1.0, is specified completely in
`runner/tools/toy_map.py`, and the specification is short
enough to state here in full. A program is a finite bit
string. The program bits are read as a candidate assignment:
bit i of the program is the value of variable x_i, and
variables past the end of the program take the value 0. U0
runs a program on a formula clause by clause, in clause
order; each clause check costs exactly 1 step on its step
counter; a falsified clause halts the run at once with no
output; if every clause passes, U0 outputs the candidate
assignment. A run may spend at most a stated step limit, and
a run that would need a step beyond the limit is cut with no
output. Decoding costs no steps. U0 is deterministic.

## The finite domain

The grammar is CNF over exactly 3 variables, x0, x1, x2. A
clause chooses, per variable, absent, positive or negative,
which gives 26 non empty clauses. A formula is a set of
distinct clauses in canonical order, of size 0 to 3. The
encoded length of a formula is n = 2 + 6m bits for m
clauses: a 2 bit clause count header, then 6 bits per
clause, 2 bits per variable. The maximum encoded length is
N = 20. The domain holds every formula of the grammar:
1 + 26 + 325 + 2600 = 2952 formulas, enumerated completely.

Satisfiability is settled independently of U0, by a complete
truth table over the 8 assignments, using a witness
verifier that is a separate code path from U0's own clause
evaluation. Any assignment U0 outputs is verified again by
that verifier before it counts as a witness.

## The candidate A0(c, d)

A0(c, d) mirrors candidate C's A(c, d) with U0 in place of
U. For a formula of encoded length n, the program cap is
floor(c log2(n + 2)) bits and the step budget is (n + 2)^d
steps per program run. Programs are enumerated by length
ascending, then by value ascending, and the search stops at
the first program whose output verifies.

A cell of the grid is in exactly 1 of 3 states. FAIL: a
named satisfiable formula, a named satisfying assignment
for it, and the complete bounded enumeration for that
formula together show A0(c, d) found no witness for it.
Checking a negative result means checking the bounded
enumeration; a satisfying assignment alone does not
establish that no permitted program succeeded. PASS UP TO
N: the entire named domain was checked, and every
satisfiable formula in it got a verified witness. UNKNOWN:
a stated resource limit, here a per cell program budget,
stopped the enumeration before the domain was completely
checked. A timeout is UNKNOWN, never a counterexample. The
cost of the complete enumeration is reported with the map,
not hidden.

## Supposition, written before the enumeration ran

From the definitions alone, before any run, the grid over
c in {0, 1, 2} and d in {0, 1, 2} should come out as a
monotone staircase, for these reasons. A satisfying
assignment a first becomes reachable at program length
equal to the bit length of a, since variables past the
program's end read as 0. A successful run costs exactly m
steps, the clause count, since U0 outputs only after the
last clause passes. So a satisfiable formula defeats
A0(c, d) exactly when every satisfying assignment has bit
length above the cap, or its clause count exceeds the step
budget.

- At c = 0 the cap is 0, only the all zero assignment is
  reachable, and the unit formula (x0) is satisfiable but
  unreachable: FAIL at every d.
- At d = 0 the budget is 1 step, and the 2 clause formula
  (x0) and (x1) is satisfiable but needs 2 steps: FAIL at
  every c.
- At c = 1 the smallest cap over the domain is 2, at the
  empty formula, and every non empty formula has cap at
  least 3, enough for any assignment of 3 variables; with
  d at least 1 the budget is at least n + 2, at least 4,
  above every clause count in the domain: PASS UP TO N at
  (1, 1), (1, 2), (2, 1) and (2, 2).
- The full prediction is therefore FAIL at (0, 0), (1, 0),
  (2, 0), (0, 1) and (0, 2), PASS UP TO N at the other 4
  cells, and UNKNOWN nowhere at a per cell program budget
  of 10,000,000, since no cell's complete work comes
  anywhere near that budget. The total cost should stand
  well under 2,000,000 program runs, because FAIL cells
  stop at their first named counterexample and PASS cells
  stop each formula's search at its first verified witness.

The monotonicity property is part of the supposition, not
an observation added later: for the same formula and the
exact interpreter, increasing either c or d cannot remove
programs or steps, since both caps are non decreasing in
each constant and the enumeration order is fixed. A
counterexample to a stronger pair therefore defeats every
weaker pair, and success at a weaker pair persists at every
stronger pair. The unit tests pin this per formula, not
only on the finished grid.

## The result

<!-- RESULTS: filled from the enumeration record after the run. -->

## Provenance

<!-- PROVENANCE: filled from the enumeration record after the run. -->

## What the toy map does and does not teach

It teaches the quantifier shape honestly, at a size where
every mark on the map is a checked fact: a finite domain
can kill a named pair outright, with a named formula and a
reproducible enumeration, and it can clear a named pair up
to a named size, and neither fact is a theorem about the
infinite family. The staircase is what bounded accumulation
looks like when it is real. It does not teach anything
about the real universal interpreter: U0 is not universal,
its programs are assignments rather than computations, and
no conclusion here transfers to A(c, d) itself, let alone
to P versus NP. The map's value is that it can grow from
actual checks, cell by cell, with its costs on its face.
