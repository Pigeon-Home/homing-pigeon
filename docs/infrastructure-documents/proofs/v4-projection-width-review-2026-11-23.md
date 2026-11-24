# The fixed width projection claims: a refutation attempt

Two emails of 23 November 2026, relayed in ComChat at
7:59 PM and 8:00 PM, follow the projection page with a
harder question: what does the relation cost when every
clause must stay short? The second email asks plainly for
an independent attempt to break its lower bound, naming
the shapes a counterexample would take. This page is my
answer: the supposition and the attack plan, written
before any check ran, and then the record of what the
checks found. I am the reviewer here, not the author of
the claims, and nothing on this page is a result of this
project beyond the review itself.

The relation throughout is the one on the projection
page: visible variables a_i and b_i for i from 1 to m,
one output z, and R_m holds exactly when z is true or
some pair has both bits false. An encoding is a CNF over
the visible variables and k existential auxiliary
variables whose projection onto the visible variables is
exactly R_m, with w bounding the literals in every
clause.

## The claims under review

1. Width three Horn: the minimum auxiliary count is
   max(0, m - 2).
2. At that minimum, the minimum clause count is exactly
   2m, and a construction attaining both bounds also
   derives every implied visible literal by unit
   propagation under any partial visible assignment, or
   derives a contradiction when the assignment excludes
   R_m. The stated examples: m = 1 takes 0 auxiliaries
   and 2 clauses; m = 2 takes 0 and 4; m = 3 takes 1
   and 6; m = 4 takes 2 and 8; m = 6 takes 4 and 12.
3. Horn at width w, any w from 2 up: an exact encoding
   with k auxiliaries exists if and only if
   m <= 1 + (k + 1)(w - 2).
4. Arbitrary CNF at any fixed width w from 3 up: the
   minimum auxiliary count is Theta_w(m^(1 / (w - 1))),
   decided exactly by a capacity: an encoding exists if
   and only if m + 1 <= C(k, w), where C(k, w) is the
   largest sum of (w - width(D)) over the clauses D of a
   minimally unsatisfiable CNF on at most k variables
   with every clause of width at most w. Reported small
   values: the minimally unsatisfiable counts for k = 0,
   1, 2, 3 are 1, 2, 12, 870, and C(k, 3) is 3, 4, 5, 6
   at those k. One concrete case: at m = 256 and width
   three, an ordinary CNF with 62 auxiliaries and 575
   clauses, against at least 254 auxiliaries for any
   width three Horn encoding of the same relation.
5. Width two: for m from 2 up, no existential 2-CNF
   encoding exists at all, Horn or not, at any auxiliary
   count, because satisfying assignments of 2-CNF are
   closed under coordinatewise majority, projection
   preserves that closure, and R_m is not majority
   closed.
6. A propagation extension: the original chain of the
   projection page has a variable and clause incidence
   graph that is a tree, and in any incidence forest,
   unit propagation under a partial assignment that may
   also assign auxiliaries finds every implied literal
   or a conflict. The email reports 84,159 finite checks
   with no disagreement.

## How I worked

Blind first. I took the statements above and rederived
what I could by hand, looking for the step that fails,
before writing any check. The checks are then my own
implementations, built from the statements, not from the
emails' scratch code, which I have not seen. Where a
claim is an argument rather than a finite fact, the
finite checks pin the small cases the argument stands
on and the solver searches try the shapes the argument
says cannot exist.

## What the hand derivation settled, and where it stopped

The auxiliary lower bound rests on one minimal forbidden
pattern: z false, exactly one true bit in each pair. I
checked the load bearing step by hand. A minimal pattern
is excluded by an encoding exactly when forward chaining
from its true bits derives z: the least model of the
encoding together with those inputs either derives z, in
which case no completion with z false exists, or it does
not, in which case the least model itself, completed by
the z false reading, satisfies every constraint clause,
because a completion with z true exists and the least
model sits inside it. So constraint clauses cannot evade
positive propagation, and rules with visible heads cannot
help either: any atom the closure derives sits inside
that same z true completion, whose visible part is the
pattern itself. The occurrence count then goes through
as stated: a proof of z pruned to one productive rule
per head has q heads, needs at least m body occurrences
of chosen pair bits (a proof missing one pair's bit
fires unchanged with that pair empty, where z false is
legal) and at least q - 1 body occurrences of auxiliary
atoms, against at most q(w - 1) body places, giving
m <= (w - 2)q + 1 with q <= k + 1. The clause count at
the minimum rests on tuple injectivity, and that also
survived my hand check: at the minimum every auxiliary
head is used in every pattern's proof, two patterns
sharing one tuple of productive rules would force the
shared rule whose body holds the first pattern's chosen
bit in some pair to fire under the second pattern, which
chose the other bit, and no rule in the tuple has that
visible bit as its head. The arithmetic after that is
AM-GM and 2^(1 / q) >= 1 + (ln 2) / q, landing strictly
above 2q + 1, so the integer count is at least 2q + 2,
which is 2m. The boundary cases m = 1 and m = 2 I
settled directly: at m = 2 with no auxiliaries each of
the 4 patterns needs its own rule with head z, and at
m = 1 the 2 clauses (a_1 implies z) and (b_1 implies z)
are forced in shape.

The width two wall I also rederived: the three witnesses
in the email have coordinatewise majority z false with
every pair hit, for every m from 2 up, and a width two
clause is majority closed by the pigeonhole step on its
at most 2 literals. R_1, by contrast, is majority closed:
two of any three satisfying assignments with z false
have the pair empty, so the majority cannot have both
pair bits true with z false; and (not a_1 or z) and
(not b_1 or z) encode it at width two with no
auxiliaries.

The m = 256 arithmetic I recomputed from the
construction's description: 2 groups of 17 selectors,
17^2 = 289 blocking clauses, 14 chain bits per group,
34 + 28 = 62 auxiliaries, and 289 + 256 + 30 = 575
clauses, with 17 the least n with n^2 >= 257.

One thing my hand work added: the forest condition in
claim 6 is load bearing, not decoration. The Horn
formula (a implies b), (a implies c), and (not b or
not c) entails not a, since a true forces b and c true
against the constraint, yet unit propagation under the
empty assignment derives nothing at all. Its incidence
graph has a cycle: a to the first clause to b to the
constraint to c to the second clause back to a. So a
checker that compares propagation against entailment
must be able to register a miss on this example, or its
agreements elsewhere mean little.

Where the hand work stopped: it does not exclude an
encoding shape my pruning picture fails to imagine, and
it does not by itself recheck the emails' finite
enumerations. Those are what the attacks below are for.

## The attack plan

A1. Solver search for a width three Horn encoding below
the claimed bounds, allowing every Horn clause of width
at most 3 over the visible and auxiliary variables:
definite rules with any head, unit facts, and constraint
clauses. Sizes: m = 3 with 0 auxiliaries and at most 10
clauses; m = 3 with 1 auxiliary and at most 5 clauses;
m = 4 with 1 auxiliary and at most 10 clauses. A found
encoding breaks claim 1 or claim 2 outright. Exhaustion
at these sizes is evidence, not proof.

A2. Exhaustive search over clause subsets at the
smallest sizes: m = 1, 0 auxiliaries, at most 1 clause;
m = 2, 0 auxiliaries, at most 3 clauses. The claims say
nothing works there and the constructions attain 2 and
4 clauses respectively.

A3. The zero auxiliary boundary of claim 3, decided by
enumerating single rule bodies: with no auxiliaries, a
minimal pattern can only be excluded by one rule with
head z whose body sits inside the pattern and meets
every pair, so m <= w - 1 is necessary; I enumerate all
bodies of size at most w - 1 for w = 3, 4, 5 at m = w
and check that none both sits inside some minimal
pattern and meets every pair, and I check the group
construction attains m = w - 1 with 0 auxiliaries.

A4. The constructions, checked by enumeration against
R_m: the width three block construction of claim 2 for
m = 1 to 8, with clause and auxiliary counts read off
the built clauses; the group construction of claim 3 at
the boundary points (w, k) = (3, 1), (4, 0), (4, 1),
(5, 1) with m at 1 + (k + 1)(w - 2); the selector
construction of claim 4 at width three for m = 1 to 8,
with its counts, and the m = 256 counts as pure
arithmetic.

A5. Propagation, compared against exact entailment
computed by enumerating completions: the block
construction on every partial visible assignment for
m = 1 to 4 in full, and for m = 5 on assignments fixing
at least 5 of the 11 visible variables; the original
chain on every partial assignment of all its variables
for m = 1 and 2 in full, and for m = 3 on assignments
fixing at least 8 of its 13 variables; 200 random Horn
formulas whose incidence graph is a forest, on every
partial assignment of their variables; and the cyclic
example above, where propagation must miss the implied
literal not a.

A6. Majority: the 3 witnesses for m = 2 to 7; every
clause of width at most 2 over up to 5 variables checked
majority closed against all triples of its satisfying
assignments; R_1 majority closed by enumeration, with
its width two encoding checked.

A7. Capacity: enumerate the minimally unsatisfiable
CNFs on k variables for k = 0, 1, 2 in full, counting
them and computing C(k, 3); for k = 3, run the same
enumeration inside a stated time box and report what it
reaches. Spot check the exact regime C(k, w) = (w - k)
times 2^k at (k, w) = (1, 2) and (2, 4) from the same
enumerated families.

## Suppositions, written before any check ran

S1. No attack finds a counterexample. Every claim
survives, and the fixed width theorem is then ready to
land beside the projection page, marked as reviewed
here.

S2. A1 finds no encoding at any listed size, and A2
finds none below the claimed minima.

S3. Every A4 projection matches R_m exactly, with the
claimed clause and auxiliary counts read off the built
clauses, including 62 auxiliaries and 575 clauses in
the m = 256 arithmetic.

S4. A5 finds no disagreement anywhere it looks, and the
cyclic example misses exactly as predicted, which shows
the comparison has teeth.

S5. The A6 witnesses check out for m = 2 to 7, every
width at most 2 clause over up to 5 variables is
majority closed, and R_1 is majority closed.

S6. The A7 counts come out 1, 2, 12 for k = 0, 1, 2,
with C(k, 3) = 3, 4, 5. If the k = 3 enumeration
finishes inside its box, its count is 870 and
C(3, 3) = 6.

S7. The boundary algebra of claims 1 and 3 agrees at
every point the attacks touch: the solver sizes in A1
sit strictly below max(0, m - 2) auxiliaries or below
2m clauses at that count, and the A3 boundary falls
exactly at m = w - 1.

## Outcome

Appended below after the runs, with the verdict per
claim and the test module that pins the finite parts:
`runner/tests/test_v4_projection_width.py`.
