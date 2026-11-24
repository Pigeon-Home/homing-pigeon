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

The checks ran after the suppositions above were
committed. `runner/tests/test_v4_projection_gluing.py`
holds the finite parts. Verdicts per claim:

Claim 1, the gluing lemma: SURVIVED. The checker was
validated first on the two controls: the XOR and
equality pair, each fully PC over its 9 partial
assignments, whose conjunction it flags at the empty
assignment, and the cyclic Horn example of the fixed
width page, where it registers the missed literal.
Against the lemma itself: 45 pairs of prime implicate
complete formulas over 4 variables, 66 pairs of random
formulas filtered to fully PC, 30 pairs of incidence
forest Horn formulas over 4 and 5 variables, 12 chains
of 3 blocks glued one variable at a time, and 28
gluings of 7 hand built edge bases (a unit clause on
the shared variable, a unit clause against it, an
unsatisfiable block, an empty block, a block with the
shared variable in one polarity, a block forcing it
through a second variable, a block forcing it false)
against verified PC partners: 181 conjunctions, each
compared against exact entailment on every partial
assignment of its 7 or 8 variables. No disagreement
anywhere. One hand built base of mine, (v implies x)
with (not x or not v), turned out not to be PC itself
and was replaced by a verified base; the checker
catching it is part of the evidence the machinery
works. The finite checks do not prove the lemma; the
email's gluing argument stands unrefuted, with its
load bearing step, that a side allowing only one value
of the shared variable would have propagated it,
exercised by the forcing edge cases and never tripped.

Claim 2, full PC of the constructions: SURVIVED at
every finite range the email names. Each block was
verified standalone on all of its partial assignments:
the width three first block (243 assignments), its
middle and last blocks (81 each), the m = 2 form (243),
the width four group of 3 pairs (2,187) and its 1 pair
tail block (81), the width five group of 4 pairs
(19,683) and its 2 pair tail block (729). The whole
constructions follow in claim 3.

Claim 3, the finite counts: REPRODUCED EXACTLY. Width
3, m = 1 to 4: 27, 243, 6,561 and 177,147 partial
assignments, summing to 183,978. Width 4: 27, 243,
2,187 and 59,049, summing to 61,506. Width 5: 27, 243,
2,187 and 19,683, summing to 22,140. Total 267,624,
and propagation agreed with exact entailment on every
single one, auxiliaries included. S2 and S3 hold as
written.

Claim 4, the smaller grid: SURVIVED. The grid built
from the email's description has exactly 60 auxiliary
variables and 545 clauses, every clause of width at
most 3. All 256 designated empty pair witnesses and
the z true witness satisfy it outright; all 260
forbidden one row and one column choices conflict
under unit propagation alone; 4 representative all hit
visible patterns with z false are unsatisfiable under
a solver. The template arithmetic checks by direct
enumeration: 2(r + c) - 6 auxiliaries for r and c at
least 3, r + c at least 33 whenever rc reaches 257,
and among covering rectangles with r + c = 33 the
blocker minimum is 260, attained at 13 by 20. One slip
was mine, not the email's: my first arithmetic test
minimized the blocker count over all 33 selector
rectangles and got 90 at 3 by 30, forgetting the
covering condition the email states; with rc at least
257 imposed, as written, 260 at 13 by 20 is exact.

Claim 5, the grid's limit: CONFIRMED, and recorded
beside claim 4 wherever the grid is stated, including
section 7 of the fixed width page. Under the email's
assignment, z false, every pair a true and b false,
unit propagation derives no literal and no conflict:
the assigned set after propagation is the visible
assignment itself. A solver over the same assignment
returns unsatisfiable. The smaller encoding is exact
and visibly weaker, exactly as the email says.

Claim 6, the open question: LEFT OPEN, as posed. This
review records it in section 7 of the fixed width page
and does not touch it.

The literature check (S6) found the neighbourhood the
email expects and no exact prior statement. Propagation
completeness is Bordeaux and Marques-Silva's notion
(2012); the canonical CNF of all prime implicates is
always PC (Kucera and Savicky, Bounds on the size of
PC and URC formulas, 2020, the paper the email cites);
Kucera and Savicky's propagation complete encodings of
smooth DNNF theories (2019) compose PC encodings over
AND nodes whose variable sets are disjoint, which is
the zero shared variable case with separators in the
satisfying subtrees; Marquis (AAAI 2015) proves a
conjunctive separability property for prime implicate
formulas, a neighbouring decomposition of entailment
across a conjunction. None of these states the one
shared variable gluing lemma for arbitrary fully PC
CNFs. Priority is therefore recorded as unverified:
the lemma may be known under another name, and it is
framed on the fixed width page as the email's
candidate argument with this finite evidence, never as
a new theorem.

Suppositions: S1 through S5 hold as written. S6 holds
in its careful form: neighbouring decomposition work
found, no exact statement found, priority unverified.
