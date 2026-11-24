# The propagation hierarchy claims: a second refutation attempt

A third email of 23 November 2026, relayed in ComChat at
8:43 PM, extends the fixed width projection work of the
two earlier emails that day. The first review, recorded
in `v4-projection-width-review-2026-11-23.md`, tried to
break the fixed width claims and found no counterexample.
This page is the same treatment for the extension: the
supposition and the attack plan, written before any check
ran, and then the record of what the checks found. I am
the reviewer here, not the author of the claims, and
nothing on this page is a result of this project beyond
the review itself.

The relation throughout is the one on the projection
page: visible variables a_i and b_i for i from 1 to m,
one output z, and R_m holds exactly when z is true or
some pair has both bits false. An encoding is a CNF over
the visible variables and k existential auxiliary
variables whose projection onto the visible variables is
exactly R_m, with w bounding the literals in every
clause. A minimal forbidden pattern is a visible
assignment with z false and exactly one true bit in each
pair; there are 2^m of them, and each one sits one bit
flip away from allowed assignments.

## The claims under review

1. A universal clause floor. Every existential CNF
   encoding of R_m, at any width and any auxiliary
   count, has at least 2m clauses. The argument counts,
   for each minimal forbidden pattern P and each true
   bit i of P, the pair (P, i): turning bit i off makes
   the pattern allowed, any completion witnessing the
   allowed pattern falsifies the encoding at P, and
   some clause newly fails there and so contains the
   negation of bit i. A clause whose distinct negative
   pair literals number j witnesses at most j times
   2^(m - j) such pairs, at most 2^(m - 1) for every j
   from 1 up, and a clause with both negative literals
   of one pair, or none, witnesses none. There are
   m times 2^m pairs to witness.
2. An exact auxiliary price for plain unit propagation.
   At width w from 2 up with at most k auxiliaries, the
   following are equivalent for R_m: some exact encoding
   has unit propagation refuting even one minimal
   forbidden pattern, and some exact encoding is fully
   propagation complete, including under assumptions on
   auxiliaries. Both hold exactly when
   m <= 1 + (k + 1)(w - 2). Below that budget, every
   exact encoding fails to unit refute every minimal
   forbidden pattern. The lower bound argument takes a
   unit propagation refutation of one pattern, retains
   the final conflict clause and recursively the unit
   reason for each earlier assignment it needs, and
   counts slots: a slice of p clauses has p - 1 assigned
   auxiliary variables, each retained variable occurs at
   least twice in the slice, and the disjunction of the
   slice's visible parts is entailed by R_m and false at
   the pattern, so it mentions z and a selected negative
   bit from every pair, giving m + 1 + 2(p - 1) <= p w.
   The matching construction is the Horn block chain of
   the fixed width page, propagation complete by a
   singleton separator argument between blocks.
3. The minimum clause budget forces the linear
   auxiliary count. At width three, an ordinary CNF
   encoding with exactly 2m clauses has k >= m - 2, the
   same minimum as Horn. Equality in the counting of
   claim 1 forces every clause to carry a negative pair
   literal; under a minimal forbidden pattern every
   residual clause has width at most two; a minimal
   unsatisfiable residual core must contain a unit,
   because an empty residual clause alone would need
   m + 1 visible literals in a width three clause; unit
   propagation must refute that core; and then the
   bound of claim 2 applies.
4. One parallel failed literal pass on the compact
   grid. On the 62 auxiliary selector grid at m = 256
   (the construction of the fixed width page, 575
   clauses), plain unit propagation cannot refute a
   minimal forbidden pattern, but one parallel round of
   failed literal probes on the row and column
   selectors, followed by plain unit propagation,
   derives every visible consequence under any partial
   assignment to visible variables only. The email
   reports checking the one round procedure against the
   projected relation on all 22,140 visible partial
   assignments for one through four pairs, plus three
   cases at 256 pairs: a minimal forbidden pattern, a
   case forcing z, and a case forcing both bits of one
   pair false.
5. A hierarchy tradeoff. Write r_0 for detecting an
   empty clause and r_1 for ordinary unit propagation,
   and let r_(h + 1) close under deriving the opposite
   of any trial literal that r_h refutes. For fixed
   width w from 3 up and fixed level h from 1 up, the
   minimum auxiliary count for an exact encoding that
   refutes the minimal forbidden patterns at level h is
   Theta_(w, h)(m^(1 / min(h, w - 1))), and the same
   exponent lower bound follows from refutation of just
   one minimal forbidden pattern. The lower bound
   represents an r_h refutation as a binary decision
   tree whose leaves number at most the sum of
   binom(k, i) for i from 0 to h, and the leaf clauses'
   visible disjunction needs at least m + 1 literals,
   so m + 1 <= w times that sum; the capacity theorem of
   the first review supplies the independent
   k^(w - 1) side. The upper bound uses
   d = min(h, w - 1) selector groups.
6. New finite check counts. The email reports comparing
   a generic unit propagator against exact model
   completion answers on 245,214 small partial
   assignments to the Horn block chain, including
   assignments to auxiliary variables, with no
   disagreement; the 22,140 count of claim 4; and an
   independent reviewer's 179,577 visible partial
   assignments on additional rectangular grids, also
   with no disagreement. The email suggests three
   controls for this round: a valid short Horn chain
   that propagates under auxiliary assumptions, a
   compact grid where ordinary unit propagation must
   stall, and the same grid passing the single failed
   literal check.

## How I worked

Blind first, as in the first review. I took the
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

Claim 1 I verified in full. Fix a minimal forbidden
pattern P, a true bit i of P, and the allowed pattern
P' that turns bit i off. Take a completion c of the
auxiliaries satisfying the encoding at P'. The same c
falsifies the encoding at P, since P is forbidden. Some
clause is satisfied at (P', c) and falsified at (P, c);
the two assignments differ only in bit i, so that
clause contains the negation of bit i, and every other
literal of it is false at both. For such a clause to be
falsified at P, P must choose the negated bit in every
pair the clause negates: a negated bit P did not choose
is false at P, its negation true, and the clause would
be satisfied. So if the clause negates bits in j
distinct pairs, it witnesses only pairs (P, i) where P
extends those j choices, 2^(m - j) patterns, and i is
one of the j negated bits: at most j times 2^(m - j)
pairs. The ratio of j times 2^(m - j) to 2^(m - 1) is
j over 2^(j - 1), which is 1 at j = 1 and j = 2 and
smaller after, so every clause witnesses at most
2^(m - 1) pairs. A clause negating both bits of one
pair can never be falsified at a minimal pattern, since
the pattern makes one of the two negations true, and a
clause with no negative pair literal witnesses nothing,
since the newly failing clause must contain the
negation of bit i. Every one of the m times 2^m pairs
needs a witness, so the clause count is at least
m times 2^m over 2^(m - 1), which is 2m. The block
construction of the fixed width page attains 2m, so the
floor is exact.

Claim 2's inequality I verified. In a unit propagation
refutation slice of p clauses, the p - 1 reason clauses
each assign a distinct auxiliary variable: the visible
variables are already assigned by the pattern, and a
variable is assigned once, so p - 1 <= k. Each retained
variable occurs at least twice in the original slice,
once as the head of its reason and once with the
opposite sign in the later clause that needed it, by
the way the retention recursion chooses reasons. The
disjunction of the slice's visible parts is entailed by
R_m and false at the pattern, so by the residual core
argument of the first review it carries at least
m + 1 visible literal occurrences counting multiplicity
at least the distinct literals it needs, namely z and
one selected negative bit per pair. Auxiliary literal
occurrences number at least 2(p - 1). Total occurrences
are at most p w. So m + 1 + 2(p - 1) <= p w, hence
m + 1 <= p(w - 2) + 2 <= (k + 1)(w - 2) + 2, which is
the claimed condition. At w = 2 it leaves m <= 1, which
matches the width two wall of the first review: R_1 is
the only relation of the family that width two can
encode at all. The equivalence between refuting one
pattern and full propagation completeness is at the
level of existence within a budget: the block chain
sits in the same budget and is propagation complete by
the separator argument, whose local step I checked: a
block's relation is a disjunction of disjoint variable
terms, a dead term under a partial assignment has a
fixed false literal, choosing one such literal per dead
term yields an empty clause when every term is dead and
forces the last live term's remaining literals when
exactly one term is live, and with two live terms any
free variable takes either value through a live term
avoiding it. Blocks share one flag per edge, so a local
model extends outward across separators. That is an
argument, not a finite fact; the checks pin its small
cases.

Claim 3's mechanism I verified, with one step that
needed unfolding. Equality in claim 1 forces every
clause to witness the maximum 2^(m - 1) pairs, and a
clause with no negative pair literal witnesses none,
so every clause carries one. Under a minimal forbidden
pattern, each clause loses at least that one literal
to falsity, so residual width is at most two. An empty
residual clause would come from a clause whose every
literal is visible and falsified at the pattern; the
residual core argument needs such a clause's visible
part in a disjunction mentioning z and a selected
negative bit from every pair, at least m + 1 literals,
more than width three holds once m is 3 or more, so a
minimal unsatisfiable residual core contains a unit.
Its binary part is satisfiable by minimality, since
the binary part sits inside the core minus its unit
clause. The step the email compresses is that unit
propagation must refute the core: at a consistent
propagation fixed point, every unit of the core has
been consumed, every remaining clause is binary and
mentions no assigned variable (a binary clause
mentioning an assigned variable is satisfied, or has
become a unit, or is falsified, and the fixed point
excludes the last two), and the remaining binary
clauses are a subset of the satisfiable binary part,
whose satisfying assignment restricted to the free
variables combines with the fixed bits to satisfy the
whole core, contradicting unsatisfiability. With that
step unfolded the claim goes through, and claim 2 then
gives k >= m - 2 at width three. The smaller cases
m = 1 and m = 2 need no auxiliaries, as the first
review settled directly.

Claim 4's probe logic I verified against the
construction. A pair cell's two blocking clauses carry
the cell's negative selector literals plus one visible
literal each; when the pair's empty term is dead under
a visible partial assignment, at least one of the
pair's bits is assigned true, and the blocking clause
carrying that bit's negation reduces to the binary
blocker in the two selector literals. The z cell's
clause reduces the same way when z is assigned false,
and a padding cell's blocker is binary from the start.
So every dead cell supplies a binary blocker, and a
selector assumed true against a row of dead cells
forces every column selector false by those blockers,
then contradicts the column group's OR chain: the
selector is false, derivable by one probe. The probes
all start from the same partial assignment, so they
compose in parallel, and after the derived negations a
single propagation pass faces three cases: no live
cell, where a group OR is refuted; one live cell, where
its row and column are the only surviving selectors in
their groups, the OR chains force both, and the cell's
clauses force the rest of its visible term; and several
live cells, whose visible variable sets are disjoint
(the pair terms use disjoint pairs and the z term uses
only z), so no unassigned visible literal is forced.
One more observation the checks will use: the grid has
no clause of width below two, and no clause with fewer
than two selector literals except the OR chain clauses,
which mention selectors only, so under a visible only
assignment unit propagation on the grid derives nothing
at all, at any m. The stall the email reports at
m = 256 is therefore not a large m accident; but the
sharp form of the stall is claim 2's: at budgets where
(k + 1)(w - 2) + 1 < m, no encoding at all can unit
refute a minimal pattern, and the grid at m = 256 has
62 auxiliaries, far below that line.

Claim 5's counting I verified. The leaf bound for an
r_h refutation tree satisfies the recurrence of Pascal's
rule: at each trial one branch closes one level down
and the other continues at the same level, with one
leaf at level 0 or at no remaining variables, giving at
most the sum of binom(k, i) for i from 0 to h leaves.
The leaf clauses form an unsatisfiable residual subset
under the pattern, their visible disjunction needs at
least m + 1 literals by the same residual core
argument, and each leaf clause has at most w literals,
so m + 1 <= w times the leaf sum. For h = 1 the sum is
k + 1 and the bound reads m + 1 <= w(k + 1), weaker
than claim 2's exact count, as the email itself notes;
the hierarchy statement is asymptotic, and its two
sides are the tree bound here and the capacity bound of
the first review. The upper bound's d group grid is a
construction I can rebuild and enumerate at small
sizes.

Where the hand work stopped: it does not recheck the
email's finite enumerations, it does not by itself
exclude a propagation slice shape my retention picture
fails to imagine, and the equivalence in claim 2 and
the induction in claim 5's upper bound are arguments
whose finite content is the constructions and counts.
Those are what the attacks below are for.

## The attack plan

B1. The email's first control. The original chain of
the projection page and the block chain of the fixed
width page, checked for propagation completeness
against exact entailment computed by enumerating
completions, under partial assignments that may assign
auxiliaries as well as visible variables: the chain on
every partial assignment of all its variables for
m = 1 and m = 2, and for m = 3 on assignments fixing at
least 11 of its 13 variables; the block chain on every
partial assignment of all its variables for m = 1 to
m = 3, and for m = 4 on assignments fixing at least 7
of its 11 variables. The cyclic example of the fixed
width page stands as the negative control: propagation
must miss the implied literal there.

B2. The email's second control, in its sharp form. The
selector grid under plain unit propagation, on minimal
forbidden patterns: every pattern for m = 2 to m = 8;
at m = 30, where the grid has 22 auxiliaries and
claim 2 forbids any encoding at that budget from unit
refuting any minimal pattern, a structured and sampled
set of patterns (all a choices, all b choices,
alternating, and 2,000 patterns drawn at random with a
fixed seed); and at m = 256 a set of patterns of the
same shapes. Propagation must derive no conflict in
every case. A conflict anywhere at m = 30 or m = 256
breaks claim 2's lower bound outright.

B3. The email's third control. The one round procedure
of claim 4, implemented from the statement: probe each
of the two groups' selectors once against the starting
partial assignment, collect the derived negations,
apply them all, and run unit propagation once more.
Compare its visible consequences and its conflict
verdict against exact entailment on every visible
partial assignment for m = 1 to m = 4, where the count
of assignments must come out at the email's 22,140, and
on the three named cases at m = 256.

B4. Claim 1's finite pins. The witness count, computed
by brute force over patterns: for m = 1 to m = 5, every
negative pair literal pattern a clause can carry (a
choice of at most one negated bit per pair, over any
subset of pairs, and the both bits of one pair case)
is scored against every (P, i) pair, and the maximum
must be exactly 2^(m - 1). Plus an exhaustive subset
search the first review ran only for Horn clauses:
arbitrary CNF clauses of width at most three over the
visible variables alone, m = 2, no auxiliaries, at most
3 clauses; claim 1 says nothing there reaches the
4 clause floor's underside, and the first encoding
must appear at exactly 4.

B5. Claim 3's finite pins. The equality case: the
block construction at m = 3 to m = 6 has exactly 2m
clauses and m - 2 auxiliaries, already pinned in the
first review and rechecked here as the meeting point
of claims 1 and 3. The mechanism: for the block
construction at m = 3, under each minimal forbidden
pattern, the residual formula over the auxiliaries has
a minimal unsatisfiable core that contains a unit
clause, and unit propagation refutes the residual.

B6. Claim 5's arithmetic and upper bound. The leaf sum
at w = 3: the least k with 3 times the sum of
binom(k, i) for i from 0 to h at least m + 1, computed
for m = 256 and m = 1,000,000 at h = 1, 2, 3, must
scale with exponent 1 at h = 1 and exponent 1/2 at
h = 2 and h = 3, since min(h, w - 1) is 1, 2, 2. The
upper bound construction at d = 3: three selector
groups at width four, rebuilt from the statement,
projection checked exactly against R_m for m = 1 to
m = 6 with its clause and auxiliary counts read off
the built clauses.

## Suppositions, written before any check ran

T1. No attack finds a counterexample. Every claim of
the 8:32 PM email survives in the finite ranges
checked, and the fixed width theorem page's review
status then extends to cover this email, with the
scope stated plainly.

T2. The B4 witness maximum comes out at exactly
2^(m - 1) for m = 1 to m = 5, attained only by clauses
negating one bit in one pair or one bit in each of two
pairs, and the exhaustive arbitrary CNF search at
m = 2 with no auxiliaries finds no encoding below
4 clauses and finds one at 4.

T3. B1 finds no disagreement anywhere it looks, and
the cyclic example misses exactly as predicted. My
assignment counts will differ from the email's 245,214
because the families and ranges differ; I state mine
exactly and claim only the shape matches.

T4. B2 finds the grid stalling under plain unit
propagation on every minimal forbidden pattern tried,
at every m: no conflict, and no derived literal at all
under visible only assignments, since the grid has no
clause that a visible only assignment can reduce to a
unit.

T5. B3 agrees with exact entailment on every visible
partial assignment for m = 1 to m = 4, the assignment
count comes out at exactly 22,140, and the procedure
refutes the minimal pattern, derives z, and derives
both bits of the named pair false in the three
m = 256 cases.

T6. The B6 least k values scale with the predicted
exponents, and the three group construction at width
four projects exactly onto R_m for m = 1 to m = 6 with
counts matching the statement's shape: three groups,
one OR chain per group, one blocking clause per
selector triple, and at most two clauses per used cell.

## Outcome

The runs are done, and this section is their record,
written after the checks as the plan promised. No
attack found a counterexample. Every claim of the
8:32 PM email survives in the finite ranges checked,
and the review status of the fixed width page extends
to this email on that basis, with the scope stated at
the end of this section. The checks stand pinned in
`runner/tests/test_v4_projection_round2.py`.

B1 (claim 2, and the first control of claim 6).
Propagation matched exact entailment everywhere it was
compared, on partial assignments that may assign
auxiliaries as well as visible variables. The original
chain: every partial assignment of all its variables
at m = 1 and m = 2 (243 and 19,683 assignments), and
at m = 3 every assignment fixing at least 11 of its
13 variables (221,184 assignments). The block chain:
every partial assignment of all its variables at
m = 1 to m = 3 (27, 243 and 6,561 assignments), and
at m = 4 every assignment fixing at least 7 of its
11 variables (125,952 assignments). 373,893
assignments in all, and no disagreement. My counts
differ from the email's 245,214 because the families
and ranges differ, as T3 predicted; the shape matches.
The cyclic example of the fixed width page missed its
implied literal exactly as predicted, so the
comparison has teeth. T3 held.

B2 (claim 2's lower bound, the second control). The
selector grid stalled under plain unit propagation on
every minimal forbidden pattern tried: no conflict,
and no derived literal at all. Every pattern at m = 2
to m = 8 (508 patterns in all); at m = 30 the all a,
all b and both alternating patterns and 2,000
patterns drawn at random with a fixed seed; and the
same shapes and sample at m = 256. One correction to
the plan above: the grid as the fixed width page
records it has 18 auxiliaries at m = 30, not 22 as
the plan states. The line claim 2 draws at width
three is k >= m - 2, which is 28 at m = 30, so the
stall the plan predicted is the stall the bound
requires at either count, and the correction does not
touch the verdict. T4 held.

B3 (claim 4, the third control). The one round
procedure, implemented from the statement, agreed
with exact entailment on every visible partial
assignment at m = 1 to m = 4: 27, 243, 2,187 and
19,683 assignments, 22,140 in all, the email's own
count exactly. At m = 256 the procedure refuted the
minimal forbidden pattern, derived z in the case
forcing z, and derived both bits of the named pair
false in the third case. T5 held.

B4 (claim 1). The witness maximum came out at exactly
2^(m - 1) for m = 1 to m = 5, attained only by
clauses negating one bit in one pair or one bit in
each of two pairs, and every pattern negating both
bits of one pair scored 0, as the counting argument
requires. The exhaustive subset search over arbitrary
CNF clauses of width at most three over the visible
variables alone at m = 2 (131 clauses, every subset
of at most 3) found no encoding below the 4 clause
floor, and the block construction's 4 clauses encode
R_2 there, so the first encoding appears at exactly
4. T2 held.

B5 (claim 3). The block construction at m = 3 to
m = 6 has exactly 2m clauses and m - 2 auxiliaries,
rechecked. At m = 3, under each of the 8 minimal
forbidden patterns, the residual formula over the
auxiliaries is the two unit clauses of opposite sign
in the single flag: a minimal unsatisfiable core
containing a unit clause, refuted by unit
propagation, exactly the mechanism claim 3 names.

B6 (claim 5). The leaf sum's least k at w = 3: for
m = 256, k = 85, 13 and 8 at h = 1, 2, 3; for
m = 1,000,000, k = 333,333, 816 and 126. The capacity
side of the first review, the least k with
2k^2 + 2k + 3 at least m + 1, gives 11 and 707. The
combined least k, the larger of the two sides at each
h, runs 85, 13, 11 at m = 256 and 333,333, 816, 707
at m = 1,000,000, scaling with measured exponents
1.000, 0.501 and 0.503 against the predicted 1, 1/2
and 1/2. The leaf sum alone at h = 3 scales with
exponent 1/3 and is not the binding side; the
capacity side binds there, which is what
min(h, w - 1) records. The d = 3 upper bound
construction, three selector groups at width four
rebuilt from the statement, projects exactly onto
R_m for m = 1 to m = 6, with 6 auxiliaries and
m + 11 clauses, one OR clause per group, one
blocking family per selector triple, and at most two
clauses per used cell. T6 held, with the leaf sum
note standing as part of the record.

The verdicts on the suppositions: T1 held, T2 held,
T3 held, T4 held, T5 held, T6 held with the note in
B6. What this review does not do stands as the plan
left it: the arguments are the email's, the checks
are finite, and the ranges above are the whole of
what was checked. Within those ranges the extension
of the fixed width work is, as far as these attacks
reach, exactly as stated.
