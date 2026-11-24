# The one bit join: a refutation attempt on the gluing claims

A fourth email of 23 November 2026, relayed in ComChat
at 9:06 PM, adds a proof idea to the fixed width
projection work recorded in `v4-projection-fixed-width.md`
and reviewed in `v4-projection-width-review-2026-11-23.md`
and `v4-projection-round2-review-2026-11-23.md`. This
page is the same treatment for the new claims: the
supposition and the attack plan, written before any
check ran, and then the record of what the checks
found. I am the reviewer here, not the author of the
claims. The email itself asks for exactly this: the
claims are candidate results for independent checking,
not literature priority claims, and the optimum in the
last claim is posed as open.

The relation throughout is the one on the projection
page: visible variables a_i and b_i for i from 1 to m,
one output z, and R_m holds exactly when z is true or
some pair has both bits false. A CNF is fully
propagation complete, fully PC, when under every
partial assignment to any of its variables, visible or
auxiliary, unit propagation derives a conflict exactly
when the assignment has no satisfying completion, and
derives every literal the whole formula entails under
that assignment.

## The claims under review

1. The gluing lemma. If F and G are fully PC CNFs whose
   variable sets share at most one variable, then the
   conjunction F and G is fully PC. By induction the
   same holds for a sequence of fully PC blocks where
   each new block shares at most one variable with the
   aggregate built so far. No Horn restriction is
   needed.
2. The width three Horn construction of the fixed width
   page, 4 clauses where the first two pairs meet in
   one flag and 2 clauses per later pair advancing the
   flag, is fully PC over all of its variables,
   auxiliaries included, for every m. Its blocks are
   each fully PC, successive blocks share exactly one
   flag, and claim 1 applied repeatedly gives the whole.
   The same is claimed at general width w from 3 up for
   the group construction of the fixed width page: each
   group block is its complete prime implicate CNF,
   neighbouring groups meet through one flag, and the
   construction attaining the minimum auxiliary count
   at fixed w is fully PC.
3. The finite counts. Comparing unit propagation
   against a truth table entailment checker on every
   partial assignment to every variable: width 3,
   m = 1 to 4, 183,978 checks; width 4, m = 1 to 4,
   61,506 checks; width 5, m = 1 to 4, 22,140 checks;
   267,624 checks in total, no disagreement.
4. A smaller grid. An unbalanced selector grid, 13 row
   selectors and 20 column selectors, encodes R_256 in
   ordinary width three CNF with 60 auxiliary variables
   and 545 clauses: 260 blocking clauses, one per row
   and column choice, 256 of them carrying a visible
   pair in 2 clauses each, 1 carrying z, 3 standing
   plain, and 29 group clauses in the two at least one
   selector chains. Within the two group rectangular
   template, 60 auxiliaries is the least count: a grid
   of r rows and c columns with r and c at least 3 uses
   2(r + c) - 6 auxiliaries, covering 257 items forces
   r + c at least 33, and among 33 selector rectangles
   the 13 by 20 shape minimizes the blocker count at
   260.
5. The grid's limit. The grid of claim 4 is not even
   visibly unit refutation complete. Under the visible
   assignment z false and, for every pair, a_i true and
   b_i false, the visible assignment excludes R_256, so
   the encoding is unsatisfiable under it, yet unit
   propagation stalls at once: every surviving blocker
   is a binary clause over selectors and every chain
   clause still has 3 unassigned auxiliary literals, so
   there is no unit clause and nothing is derived.
6. The open question. The least auxiliary count for
   arbitrary width three encodings of R_m that are
   visibly propagation complete, and then again for
   fully PC encodings, is posed as open. Nothing in
   this review closes it.

## Suppositions, written before any check ran

S1. The gluing lemma survives the attack. Random and
structured pairs of fully PC formulas sharing exactly
one variable produce no conjunction that unit
propagation and exact entailment disagree on, and the
hand built edge cases, unit clauses on the shared
variable, a block unsatisfiable on its own, a block
where the shared variable occurs in one polarity only,
agree as well. The negative control is caught: the two
variable XOR formula and the two variable equality
formula are each fully PC, their conjunction shares
two variables, is unsatisfiable, and unit propagation
under the empty assignment derives nothing, so the
checker flags the conjunction as not PC. If the
checker did not flag the control, the attack machinery
would be the thing under suspicion, not the lemma.

S2. Each block of the width three construction is
fully PC on its own variables, and the whole
construction agrees with exact entailment on every
partial assignment of every variable for m = 1 to 4,
with the assignment count coming out at exactly
183,978.

S3. The general width constructions agree the same way
at w = 4 and w = 5 for m = 1 to 4, with counts exactly
61,506 and 22,140, and the three counts sum to exactly
267,624.

S4. The 13 by 20 grid builds with exactly 60 auxiliary
variables and 545 clauses at width at most 3, its
projection is R_256 on every control the email names,
all 256 designated empty pair witnesses, the z true
witness, and all 260 forbidden one row and one column
choices, and the stalling assignment of claim 5 stalls
exactly as described: no conflict, no derived literal,
while a solver confirms the formula under that
assignment is unsatisfiable.

S5. The template arithmetic of claim 4 checks out by
direct enumeration over rectangle shapes: auxiliaries
2(r + c) - 6 for r and c at least 3, r + c at least 33
whenever rc is at least 257, blocker minimum 260 at
13 by 20 among r + c = 33, and shapes with a side of 1
or 2 need at least 129 selectors in the other side.

S6. The literature check finds the separator idea in
neighbouring decomposition and propagation work, as
the email expects, and no exact statement of the one
shared variable gluing lemma for fully PC CNFs in the
sources I can reach. The honest framing either way:
priority unverified, the lemma presented as the
email's candidate argument with this review's finite
evidence beside it, never as an established new
theorem of this project.

## The attack plan

A1. A generic checker first: unit propagation and exact
entailment by model enumeration over bitmasks, validated
on the negative control of S1 and on the cyclic Horn
example of the fixed width page, where the comparison
must register a miss.

A2. Random attack on the lemma: generate fully PC
formulas by construction and by filtering random
formulas through the checker, relabel pairs of them to
share exactly one variable, and compare propagation
against entailment on every partial assignment of the
conjunction. Structured families beside the random
ones: incidence forest Horn formulas, which the fixed
width page shows are fully PC, glued along one shared
variable in chains and stars; prime implicate complete
small formulas; the blocks of claim 2 glued in orders
the construction does not use.

A3. Hand edge cases aimed at the proof sketch: blocks
that force the shared variable under some local
assignment, blocks that leave it free on one side only,
a unit clause on the shared variable, an empty block,
a block unsatisfiable under the empty assignment.

A4. Block by block verification of claim 2, then the
whole constructions at the email's own ranges for
claim 3, counting every partial assignment checked so
the totals can be compared digit for digit.

A5. The grid of claim 4 built from the email's
description, counted, its projection controls run, and
the stalling assignment of claim 5 run through unit
propagation and through a solver, so the stall is
recorded beside an unsatisfiability verdict, never as
a clean win for the smaller count.

A6. A literature search on the gluing lemma and on
composition of propagation complete formulas, recorded
with what it finds, before any wording about novelty.

## Outcome

Left for the runs. This section is written after the
checks, in the same place, with the verdict per claim
and the finite ranges actually checked.
