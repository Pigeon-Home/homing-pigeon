# Propagation across one variable joins: a third refutation attempt

A fourth email of 23 November 2026, relayed in ComChat
at 9:06 PM, extends the fixed width projection work
again. The first review, recorded in
`v4-projection-width-review-2026-11-23.md`, tried to
break the fixed width claims and found no
counterexample; the second, in
`v4-projection-round2-review-2026-11-23.md`, took the
same run at the propagation hierarchy extension. This
page is the same treatment for the new material: the
supposition and the attack plan, written before any
check ran, and then the record of what the checks
found. I am the reviewer here, not the author of the
claims, and nothing on this page is a result of this
project beyond the review itself. The email itself
asks for exactly this handling: it presents its
arguments as candidate results for independent
checking, not as literature priority claims, and it
names the sequence it wants, adversarial tests first,
the new constructions landed only with their limits
stated beside them.

The relation throughout is the one on the projection
page: visible variables a_i and b_i for i from 1 to m,
one output z, and R_m holds exactly when z is true or
some pair has both bits false. A CNF is fully
propagation complete, fully PC in what follows, when
under every partial assignment to any of its
variables, visible or auxiliary, unit propagation
either derives a conflict or derives every literal
the formula entails under that assignment.

## The claims under review

1. A separator lemma and a strengthening. If F and G
   are fully PC CNFs whose variable sets share at
   most one variable, then F AND G is fully PC, and
   by induction so is a chain of blocks where each new
   block shares at most one variable with the
   aggregate before it. No Horn restriction is needed.
   Applied to the earlier constructions: the width
   three block construction (m - 2 auxiliaries, 2m
   clauses) is fully PC over all of its variables,
   flags included, and so is the general width w Horn
   group construction that attains the minimum
   auxiliary count at each fixed w from 3 up, with no
   clause minimality claimed for w above 3. The
   mechanism inside each block: the displayed clauses
   of a block are all of its prime implicates, and a
   CNF made of all the prime implicates of a function
   is fully PC. Neighbouring blocks meet in exactly
   one flag.
2. The one variable condition is load bearing. The
   two variable formulas F = (x OR y) AND
   (NOT x OR NOT y), the relation x differs from y,
   and G = (x OR NOT y) AND (NOT x OR y), the relation
   x equals y, are each fully PC, checked over all 9
   partial assignments of their two variables. They
   share both variables. Their conjunction is
   unsatisfiable, yet unit propagation from the empty
   assignment derives nothing: every clause has two
   literals. Two shared variables let the two sides
   disagree about a correlation while agreeing on
   every single variable's possible values.
3. Finite checks reported by the email, from a truth
   table entailment checker and a generic unit
   propagator, over every partial assignment of every
   variable of each constructed formula: width 3,
   m = 1 to 4: 183,978 partial assignments; width 4,
   m = 1 to 4: 61,506; width 5, m = 1 to 4: 22,140;
   267,624 checks in total, no disagreement. Some
   formulas coincide across widths and are counted
   once per width.
4. A smaller grid at m = 256. In the two group
   rectangular template of the selector construction,
   take 13 row selectors and 20 column selectors: 260
   blockers, at least the 257 the items need. The OR
   chain for 13 selectors takes 10 new bits and 11
   clauses; the chain for 20 selectors takes 17 new
   bits and 18 clauses; with the 33 selectors the
   auxiliary count is 60 and the group clauses number
   29. Each pair replaces its blocker D by (D OR
   NOT a_i) and (D OR NOT b_i), the z item replaces
   its blocker by (D OR z), and 3 blockers stand
   unchanged: 260 base blockers, 256 extra pair
   clauses, 29 group clauses, 545 clauses in total,
   every clause of width at most 3, projection exactly
   R_256. Within this template only, 60 auxiliaries
   is the smallest count: for group sizes r and c of
   at least 3 the template uses 2(r + c) - 6
   auxiliaries, rc >= 257 forces r + c >= 33, groups
   of size 1 or 2 need far more, and among 33 selector
   rectangles covering 257 items the 13 by 20 split
   minimizes the blocker count at 260. The email
   states plainly that this is not a global optimum
   for ordinary width three encodings.
5. The catch, stated by the email itself. The smaller
   grid is not even visibly unit refutation complete.
   Under the visible assignment z = 0 with a_i = 1 and
   b_i = 0 for every pair, which violates R_256 and so
   leaves the encoding unsatisfiable, every blocker
   reduces to a binary clause and every OR chain
   clause still has 3 unassigned auxiliary literals:
   no unit clause exists, and unit propagation stops
   at once without finding the contradiction. Against
   it stands the width three Horn chain at 254
   auxiliaries and 512 clauses, exact and, if claim 1
   holds, fully PC. The email poses the least
   auxiliary count for arbitrary width three encodings
   of R_m when visible propagation completeness is
   also required, and again when full PC is required,
   as a question it does not know the answer to.
6. A priority caution, also the email's own. Whether
   the one variable gluing lemma, the general width
   PC observation, or the 13 by 20 example already
   appears in the literature is not established. The
   email names the neighbouring literature: Kucera and
   Savicky on the size of PC and URC formulas and on
   propagation complete encodings, Dechter on
   tractable structures and separators, and a SAT 2026
   paper on cardinality encodings that uses a visible
   variable notion of propagation completeness. The
   review runs its own priority check before anyone
   calls the lemma new, and reports what the
   literature holds either way.

## How I worked

Blind first, as in the earlier reviews. I took the
statements above and rederived what I could by hand,
looking for the step that fails, before writing any
check. The checks are then my own implementations,
built from the statements and from the constructions
as the fixed width page records them, not from the
email's scratch code, which I have not seen. Where a
claim is an argument rather than a finite fact, the
finite checks pin the small cases the argument stands
on and try the shapes the argument says cannot exist.

## What the hand derivation settled, and where it stopped

The gluing argument of claim 1 I verified, and I
record the verification because the attacks below aim
at its exact load bearing steps. Run unit propagation
on F AND G under a partial assignment to a fixed
point, and suppose no conflict arose. Each side,
restricted to the assignment, is satisfiable: if one
side had no model under the assignment, full PC on
that side would have produced a conflict from its own
clauses alone, and propagation on the conjunction
runs those same clauses. Call the shared variable v,
if there is one. If v is assigned at the fixed point,
models of the two sides agree on v by construction
and glue into a model of the conjunction. If v is
unassigned at the fixed point, each side has a model
with v = 0 and a model with v = 1: if one side
allowed only one value of v, that side would entail
that value, and full PC would have derived it,
contradicting the fixed point. So the sides glue at
either value. Now take any variable x local to F,
unassigned at the fixed point, and either value for
it. F has a model giving x that value, since
otherwise F would entail the opposite value and full
PC would have derived it. That model gives v some
value; glue a model of G at the same value of v,
which the two value property supplies when v is
free, and which is automatic when v is assigned or
absent. So both values of x extend to models of the
conjunction, and no literal at x was missed. The
same argument covers variables local to G and the
shared variable itself. The steps that carry weight
are three: local satisfiability from local PC, the
two value property of a free shared variable, and
the gluing of a local model at a prescribed value of
v. A counterexample, if one exists, must break one
of those three steps, and the attacks aim there:
assignments that fix the shared variable, assignments
that fix auxiliaries on both sides at once, and pairs
whose local models correlate through v in ways a
single value cannot summarize.

The prime implicate step inside claim 1 is the
literature's, not the email's invention: the CNF of
all prime implicates of a Boolean function is fully
PC, a standard fact in the Kucera and Savicky work
the email cites. What the email adds is the assertion
that each block's displayed clauses really are all of
its prime implicates. That assertion is finite at
each block size and the attacks check it directly,
block by block, rather than trusting the display.

Claim 2's arithmetic I verified by hand: 3 values per
variable (false, true, unassigned) over 2 variables
gives the 9 partial assignments, and the conjunction
of the two relations is empty because a pair of bits
cannot both differ and agree. That propagation from
the empty assignment sees no unit clause is visible
from the display. What the hand check does not settle
is whether each side is really fully PC over all 9
assignments; that is finite and the attacks pin it.

Claim 3's counts I verified as arithmetic before any
run. The block construction at width 3 has 2m + 1
visible variables and max(0, m - 2) flags, so the
total variable counts at m = 1 to 4 are 3, 5, 8, 11,
and 3^3 + 3^5 + 3^8 + 3^11 is 27 + 243 + 6,561 +
177,147, which is 183,978. The group construction at
width 4 has 0, 0, 0, 1 auxiliaries at m = 1 to 4,
totals 3, 5, 7, 10, and the sum is 27 + 243 + 2,187 +
59,049, which is 61,506. At width 5 the counts are 0
auxiliaries throughout m = 1 to 4, totals 3, 5, 7, 9,
and the sum is 27 + 243 + 2,187 + 19,683, which is
22,140. The email's numbers are at least internally
consistent with the constructions as the fixed width
page records them; whether propagation agrees with
entailment on every one of those assignments is the
finite content, and it is the attacks' main target.

Claim 4's arithmetic I verified: 13 + 20 selectors,
10 + 17 chain bits, 60 auxiliaries; 11 + 18 group
clauses; 260 blockers of which 256 grow a second
clause, so 260 + 256 + 29 = 545 clauses. The
projection argument is the selector argument of the
fixed width page with unequal group sizes, and it
goes through the same way: an empty pair or a true z
retires its blocker, the retired cell's row and
column then witness a completion, and with no retired
cell every blocker survives in a copy while the group
clauses demand a live row and a live column. The
template minimality is the inequality 2(r + c) - 6
with rc >= 257, minimized at r + c = 33, and the
blocker count rc minimized over that line at 13 by
20. Both are finite over a modest rectangle range
and the attacks pin them by enumeration rather than
by trusting the inequality.

Claim 5's stall I verified from the display. Under
the named assignment each pair clause (D OR NOT a_i)
reduces to the binary blocker D itself, since a_i is
true; each (D OR NOT b_i) is satisfied, since b_i is
false; the z clause reduces to its blocker; the 3
standing blockers are binary already; and no OR chain
clause mentions a visible variable, so each keeps its
3 auxiliary literals unassigned. The residual formula
has clauses of width 2 and 3 only, no unit clause, so
unit propagation derives nothing at all, while the
assignment violates R_256 and the encoding, being
exact, has no completion. The stall is real on paper;
the attacks reproduce it on the built construction,
and pair it with a direct unsatisfiability check of
the same assignment so the failure is pinned as a
propagation failure and not a construction error.

Where the hand work stopped: it does not recheck the
email's 267,624 finite comparisons, it does not by
itself exclude a gluing counterexample at sizes
beyond the ones I can hold in my head, and the
priority question is a search question, not a
derivation. Those are what the attacks below are for.

## The attack plan

C1. The lemma, attacked directly. First, the
constructions as instances: the width three block
construction and the width 4 and width 5 group
constructions, rebuilt from the fixed width page,
checked for full PC against exact entailment computed
by a bitset model mask over all total assignments, on
every partial assignment of every variable, flags
included, for m = 1 to 4 at each width. The
assignment counts must come out at the email's
183,978, 61,506, and 22,140 exactly. Second, the
lemma beyond the constructions: random small CNF
pairs whose variable sets share exactly one variable,
each side filtered by an exhaustive full PC check of
its own, the conjunction then checked over every
partial assignment of the joint variable set; chains
of three blocks glued at single variables; the zero
overlap case as a sanity control; and a control with
one side not fully PC (the cyclic Horn example of the
fixed width page, glued at one variable to an
equivalence), where the conjunction must fail full PC
if the hypothesis is really load bearing.

C2. The negative control of claim 2, pinned exactly:
each of F and G fully PC over all 9 partial
assignments of x and y by exhaustive comparison of
propagation against entailment; the conjunction
unsatisfiable by total enumeration; unit propagation
on the conjunction from the empty assignment deriving
no literal and no conflict.

C3. The prime implicate step, block by block. For
every block shape the constructions use at the sizes
under check (the width three first block and advance
blocks, and the group blocks at widths 4 and 5),
enumerate every clause over the block's variables,
decide implicate status and primality against the
block's model set, and compare the prime implicate
set with the displayed clause set exactly.

C4. The grid, built and caught. Build the 13 by 20
construction at m = 256 from the statement. Pin the
counts: 60 auxiliaries, 545 clauses, no clause wider
than 3. Pin the projection on the designated
witnesses: for each of the 256 pairs, an explicit
completion satisfying the whole formula at the
visible assignment with that pair empty, every other
pair hit, and z false; and one for z true with every
pair hit. Pin the forbidden direction by the
structured argument, checked piece by piece: under
the visible assignment with every pair hit and z
false, every one of the 260 blockers is forced as a
clause (each pair contributes a clause reducing to
its blocker, the z cell likewise, the standing
blockers directly), each group's clauses with all of
its selectors false are unsatisfiable over its chain
bits by enumeration, and any model would need a true
row selector and a true column selector, which their
blocker forbids. Then the catch, on the same built
object: unit propagation under the email's named
assignment (z false, a_i true, b_i false for every
pair) derives no conflict and no new literal at all,
while the structured argument shows that same
assignment has no completion.

C5. The template arithmetic, enumerated. For group
sizes r and c from 1 to 40, compute the template's
auxiliary count (selectors plus chain bits, with the
degenerate chains at sizes 1 and 2 counted as the
construction builds them) and its clause count at
257 items, restrict to rectangles with rc >= 257,
and read off the minima: the auxiliary minimum and,
at that minimum, the clause minimum, with the
rectangles attaining them named.

C6. The priority check. Search the literature the
email names and the standard shelves around it
(propagation completeness, knowledge compilation,
constraint decomposition) for a statement of the
singleton overlap gluing lemma: two fully PC formulas
sharing at most one variable having a fully PC
conjunction. Report what the literature does hold,
whether or not the lemma itself is located, and
state the result as a search result with its scope,
never as a proof of novelty.

## Suppositions, written before any check ran

U1. No attack finds a counterexample to the lemma.
The exhaustive construction checks agree with the
email's counts exactly (183,978, 61,506, 22,140, no
disagreement anywhere), and the random pair attack
finds every fully PC pair sharing one variable to
have a fully PC conjunction in the ranges tried.

U2. The negative control behaves exactly as claimed:
both sides fully PC on all 9 assignments, the
conjunction unsatisfiable, propagation from empty
deriving nothing.

U3. Every block's displayed clauses are exactly its
prime implicates at every block shape checked, so
the local step of claim 1 stands on the
literature's prime implicate fact as the email
says.

U4. The grid builds at exactly 60 auxiliaries and
545 clauses; the 257 designated witnesses satisfy
it; the structured forbidden argument closes piece
by piece; and propagation under the named assignment
stalls exactly as claimed, deriving nothing, on an
assignment with no completion.

U5. The template enumeration puts the auxiliary
minimum at 60 and the clause minimum at that point
at 545, attained at 13 by 20 and at 20 by 13, and
nowhere else in the range searched.

U6. The priority search locates no statement of the
singleton overlap gluing lemma in the sources
searched. What it finds instead is the neighbouring
ground: the prime implicate fact, propagation
complete encodings distinguished from visible
variable consistency, and decomposability stated for
disjoint variable sets. The landing will say exactly
that, as a search result, and will not call the
lemma new.

## Outcome

Written after the runs, in the same place, with the
verdict per claim and the finite ranges actually
checked. Every supposition held. No attack found a
counterexample, and the landing this review supports
stands at the end of this section.

Claim 1, the separator lemma and the strengthening:
survives every attack I could build. The exhaustive
construction checks (attack C1, first part) compared
unit propagation against exact entailment from a
bitset model mask on every partial assignment of
every variable, flags included: the width three block
construction at m = 1 to 4 over 183,978 partial
assignments, the width 4 group construction at
m = 1 to 4 over 61,506, and the width 5 group
construction at m = 1 to 4 over 22,140, for 267,624
comparisons in total and no disagreement anywhere.
The counts came out at the email's numbers exactly,
which also pins that the constructions I rebuilt from
the fixed width page are the constructions the email
measured. Beyond the constructions (attack C1, second
part): 120 random pairs of fully PC formulas sharing
exactly one variable, each side the full prime
implicate CNF of a random three variable function and
each side verified fully PC on its own first, every
conjunction fully PC over all 243 partial assignments
of its five variables; 20 random triples glued in
chains at single variables, every full conjunction
fully PC over all 2,187 partial assignments of its
seven variables; the zero overlap case fully PC as a
sanity control. The load bearing control behaved as
the lemma predicts: the cyclic Horn example of the
fixed width page, which is not fully PC, glued at one
variable to a fully PC equivalence, gives a
conjunction that is not fully PC, and propagation
from the empty assignment still derives nothing while
the conjunction entails not a. The hypothesis cannot
be dropped, and where it holds, nothing in these
ranges breaks the conclusion. The lemma itself, as
an all sizes statement, stands on the gluing argument
I verified by hand above; the checks pin its finite
content and the shapes a counterexample would most
likely inhabit.

Claim 2, the negative control: exact. Both the
difference formula and the equality formula are fully
PC over all 9 partial assignments of x and y, by
exhaustive comparison. Their conjunction has no model
among the 4 total assignments, and unit propagation
from the empty assignment derives no literal and no
conflict. Two shared variables really do let the two
sides hide a contradiction from propagation that one
shared variable cannot hide, in this smallest case.

The prime implicate step (attack C3): exact at every
block shape checked. For block sizes 1 to 4 without a
previous flag and sizes 1 to 3 with one, enumerating
every clause over the block's variables and testing
implicate status and primality against the block's
model set gives a prime implicate set equal to the
displayed clause set, clause for clause. The
constructions' clause sets are exactly the unions of
those blocks under relabeling, for the block
construction at m = 1 to 7 and the group construction
at widths 4 and 5 at m = 1 to 7, so the local step of
claim 1 rests on the literature's prime implicate
fact exactly as the email says, at every size where
the constructions under review use it.

Claim 4, the grid: the counts and the projection
stand. Built from the statement, the 13 by 20
construction at m = 256 has exactly 60 auxiliaries
and 545 clauses, no clause wider than 3. Each of the
256 empty pair witnesses and the z witness is an
explicit total assignment the built clauses satisfy.
Each of the 260 designated one hot row and column
choices falsifies the built clauses. The forbidden
direction is pinned by its structured pieces: under
the visible assignment with every pair hit and z
false, each of the 260 blockers is forced as a
residual clause of the built formula; each group's
clauses with all of its selectors false are
unsatisfiable over its chain bits, by enumeration
over all 1,024 row chain and 131,072 column chain
assignments; and a model would need a true row
selector and a true column selector, which their
blocker forbids. So the projection is exactly R_256
on the strength of the email's general argument, with
every finite piece of that argument checked on the
built object.

Claim 5, the catch: reproduced on the built object,
in its sharpest form. Unit propagation under the
email's named assignment (z false, a_i true and b_i
false for every pair) derives no conflict and no new
literal at all: the assignment after propagation is
the assignment before it. The structured argument of
claim 4 shows that same assignment has no completion,
since it is the all hit, z false assignment. The
failure is therefore a propagation failure of an
exact encoding, not a defect of the construction, and
the grid must never be presented without it. The
template arithmetic (attack C5) also holds: over
group sizes 1 to 40 with rc >= 257, the auxiliary
minimum within the two group rectangular template is
60 and the clause minimum at that point is 545,
attained only at 13 by 20 and at 20 by 13.

Claim 6, the priority check (attack C6): I searched
the literature the email names and the shelves around
it, and I did not locate a statement of the singleton
overlap gluing lemma in the sources searched. That is
a search result with a scope, not a proof of novelty,
and nothing in this review calls the lemma new. What
the literature does hold, and what this review rests
on: Kucera and Savicky, "Bounds on the size of PC and
URC formulas" (arXiv:2001.00819, JAIR 69 (2020)),
gives the standard definitions of propagation
completeness and unit refutation completeness, the
fact that the CNF of all prime implicates of a
function is always propagation complete, and a Horn
function characterization of PC formulas. Kucera and
Savicky, "Propagation complete encodings of smooth
DNNF theories" (arXiv:1909.06673, Constraints 27
(2022)), distinguishes full PC over input and
auxiliary variables from domain consistency on the
inputs and builds PC encodings of DNNF theories.
Kucera and Savicky, "Backdoor Decomposable Monotone
Circuits and their Propagation Complete Encodings"
(arXiv:1811.09435, AAAI 2021), treats PC encodings as
a base class and states decomposability for circuits
whose parts have disjoint variable sets. Bordeaux,
Janota, Marques-Silva and Marquis, "On
Unit-Refutation Complete Formulae with Existentially
Quantified Variables" (KR 2012), treats unit
refutation completeness under existential closure.
Marquis, "Compile!" (AAAI 2015), states conjunctive
separability for decomposable conjunctions whose
conjuncts share no variables at all. Dechter's work
on tractable structures is the background for
separators and decomposition, and the SAT 2026
cardinality encodings paper the email cites uses a
visible variable notion of propagation completeness
and notes the term has several variants. The pattern
is consistent: the field states its gluing results at
zero overlap, and the step from zero shared variables
to one is exactly the step the email's lemma takes.
Whether some source I did not reach states it, I
cannot say; the honest sentence is that the lemma was
not located in the sources searched, and the email's
own caution against framing it as a new general
theorem stands.

The landing this review supports, now made on the
fixed width page: the separator lemma recorded with
its scope and its negative control; the full PC
strengthening of the block and group constructions
recorded as reviewed in the ranges above; the 13 by
20 grid recorded only alongside its visible
propagation failure, never as a bare construction;
and the propagation constrained non-Horn optimum
posed as OPEN, in those words, as the email poses it.
`runner/tests/test_v4_projection_round3.py` holds the
finite parts of this review.
