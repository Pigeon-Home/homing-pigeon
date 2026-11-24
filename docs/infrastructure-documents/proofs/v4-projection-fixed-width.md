# The projection at fixed width: an exact Horn tradeoff and a capacity law

The projection page holds a Horn chain that carries the
relation R_m in 3m + 1 clauses of width at most 3, and
shows that forgetting its internal bits costs 2^m flat
clauses. Two emails of 23 November 2026, relayed in
ComChat, ask the follow on question: what does the same
relation cost when the width is the constraint, in the
number of auxiliary variables rather than the number of
clauses? This page records the answer they give, with
the statements, the mechanisms, the checked cases, and
the scope of each part labeled as what it is. Like the
projection page, this construction is not a result of
this project, and nothing here claims P = NP or P ≠ NP.

Review status: the claims on this page were reviewed on
23 November 2026 by an independent refutation attempt,
recorded in `v4-projection-width-review-2026-11-23.md`:
the constructions were rebuilt from the statements and
enumerated, the smallest sizes were searched
exhaustively, a solver searched for encodings below the
claimed bounds and found none, and propagation was
compared against exact entailment. No counterexample
was found, and the page is marked as reviewed on that
basis. The review is finite: the general lower bounds
stand on the arguments stated here, not on the
enumerations. `runner/tests/test_v4_projection_width.py`
holds the finite parts. A second review on the same
day, recorded in
`v4-projection-gluing-review-2026-11-23.md`, covers the
gluing claims of a fourth email: see section 7.
`runner/tests/test_v4_projection_gluing.py` holds its
finite parts.

Throughout, R_m is the relation of the projection page:
visible variables a_i and b_i for i from 1 to m and one
output z, holding exactly when z is true or some pair
has both bits false. An encoding is a CNF over the
visible variables and k existential auxiliary variables
whose projection onto the visible variables is exactly
R_m, with w bounding the literals in every clause.

## 1. Width three Horn: the exact tradeoff

For Horn encodings at width at most 3, the minimum
auxiliary count is max(0, m - 2), and at that minimum
the minimum clause count is exactly 2m clauses. The
examples: m = 1 takes 0 auxiliaries and 2 clauses;
m = 2 takes 0 and 4; m = 3 takes 1 and 6; m = 4 takes 2
and 8; m = 6 takes 4 and 12.

The construction attaining both bounds: the first two
pairs meet in one flag, set by 4 rules, one per choice
of a true bit from each pair; each later pair advances
the flag with 2 rules; the last pair heads z instead of
a new flag. The flags are the truth of "every pair so
far is hit", so the projection is R_m by the same
canonical completion argument as the projection page.
The construction also derives every implied visible
literal by unit propagation under any partial visible
assignment, or derives a contradiction when the
assignment excludes R_m; the case split is the one on
the projection page, with the first two pairs handled
by their 4 rules.

The auxiliary lower bound is a counting argument on one
minimal forbidden pattern P: z false, exactly one true
bit in each pair. A minimal pattern is excluded exactly
when forward chaining from its true bits derives z: if
the least model does not derive z, the least model
itself completes P with z false, and if it does, no
completion with z false exists. So constraint clauses
cannot evade positive propagation, and neither can
rules with visible heads, whose derived atoms sit
inside the completion of P with z true. Prune a proof
of z to one productive rule per head: q heads, at
least m body occurrences of chosen pair bits (a proof
missing one pair's bit fires unchanged with that pair
empty, where z false is legal) and at least q - 1 body
occurrences of auxiliary atoms, against at most
q(w - 1) body places at width w. That gives
m <= (w - 2)q + 1 with q <= k + 1, and at w = 3 it
gives k >= m - 2.

The clause lower bound at the minimum counts proof
tuples. At k = m - 2 the width bound forces q = m - 1
in every proof, so every auxiliary head is used in
every pattern's proof. Choose one proof per minimal
pattern and record the tuple of its productive rules,
one per head. Two patterns cannot share a tuple: the
tuple's bodies hold the first pattern's chosen bit in
every pair, and under a second pattern differing in
some pair, the rule holding that bit cannot fire, and
no rule in the tuple has a visible bit as head. Hence
2^m <= r_z times the product of the per head rule
counts, at most (s / (m - 1))^(m - 1) for s clauses by
AM-GM, and s >= 2m follows from 2^(1 / q) >= 1 +
(ln 2) / q with q = m - 1. The boundary cases m = 1
and m = 2 are direct: at m = 2 each of the 4 patterns
needs its own rule with head z.

## 2. Horn at general width

The same counting gives the full Horn picture: at
width w, an exact encoding with k auxiliaries exists
if and only if m <= 1 + (k + 1)(w - 2). The
construction groups the pairs: the first group holds
up to w - 1 pairs, each later group up to w - 2, one
flag per group boundary, the last group heading z.
Equivalently, k >= max(0, ceil((m - 1) / (w - 2)) - 1),
and that auxiliary bound is tight when the clause
count is allowed to vary.

## 3. Arbitrary CNF: the capacity law

For arbitrary CNF at fixed width w from 3 up, the
minimum auxiliary count is Theta_w(m^(1 / (w - 1))).
Behind the asymptotic sits a finite characterization.
Call a CNF minimally unsatisfiable when it is
unsatisfiable and removing any clause makes it
satisfiable, and let C(k, w) be the largest sum of
(w - width(D)) over the clauses D of a minimally
unsatisfiable CNF on at most k variables with every
clause of width at most w. Then an exact width w
encoding of R_m with k auxiliaries exists if and only
if m + 1 <= C(k, w). Necessity restricts the encoding
to one minimal pattern and reads a minimally
unsatisfiable core over the auxiliaries; the landed
flat clause lemma of the projection page forces each
core clause to carry at least m + 1 visible literals
in total. Sufficiency assigns the m pairs and z to the
free literal slots of a core attaining the capacity
and distributes. A clause of width d in such a core is
false on a subcube of dimension k - d, so the
characterization is equivalently about irredundant
covers of a Boolean cube, each clause holding a
private point.

The small values, enumerated in full: the minimally
unsatisfiable counts for k = 0, 1, 2, 3 are 1, 2, 12,
870, and C(k, 3) at those k is 3, 4, 5, 6. The capacity
grows as O_w(k^(w - 1)): at most 2^d times binom(k, d)
clauses of each width d < w contribute, which forces
k = Omega_w(m^(1 / (w - 1))), and the construction
below meets it. One exact regime is reported with the
emails and spot checked in the review: for w >= 2k,
C(k, w) = (w - k) times 2^k, attained by taking one
private point per clause.

The meeting construction at width three: take 2 groups
of n selector variables, n the least integer with
n^2 >= m + 1, require a true selector in each group by
an OR chain, and add all n^2 blocking clauses, one
negative clause per choice of one selector from each
group. Assign each pair and z to its own blocking
clause: a pair replaces its clause D by (D or not a_i)
and (D or not b_i), and z replaces its clause by
(D or z). An empty pair or a true z removes a blocking
clause, whose private selector setting then witnesses
a completion; with neither, every blocking clause
survives in a copy and no witness exists. At m = 256
this uses n = 17, giving 62 auxiliaries and 575
clauses, where every width three Horn encoding of the
same relation needs at least 254 auxiliaries by
section 1. Both languages reach a linear clause count
at width three; what separates them is the auxiliary
count needed to keep the exact boundary.

## 4. The width two wall

At width two the picture closes entirely: for m from 2
up, no existential 2-CNF encoding of R_m exists, Horn
or not, at any auxiliary count. Satisfying assignments
of a 2-CNF are closed under coordinatewise majority,
because a clause of width at most 2 falsified by the
majority would need its at most 2 literals falsified by
2 of the 3 assignments each, and those two sets of
assignments meet in one assignment falsifying the
clause. Projection preserves the closure: take
majorities of the completions. But R_m is not majority
closed: the assignments with z false and the first
pair empty, z false and the second pair empty, and
z true with every pair bit true, have majority z false
with every pair hit. The boundary is exact: R_1 is
majority closed and is encoded at width two by
(not a_1 or z) and (not b_1 or z), with no auxiliaries.

## 5. Propagation in incidence forests

The projection page's chain has one more property the
emails isolate. Its variable and clause incidence
graph is a tree. In any Horn formula whose incidence
graph is a forest, unit propagation under a partial
assignment, one that may also assign auxiliary
variables, finds every implied literal or a conflict:
once propagation settles without conflict, rooting the
forest at any unassigned variable and assigning it
either value extends outward, each clause on the way
met by a fresh variable in its own branch, so no
unassigned literal was forced. The condition is load
bearing. The Horn formula (a implies b), (a implies
c), (not b or not c) entails not a, yet unit
propagation under the empty assignment derives
nothing; its incidence graph has a cycle through a,
the two rules, and the constraint. Forests are where
propagation is complete; a cycle is already enough to
hide an implied literal from it.

## 6. The checked cases

The test module rebuilds all three constructions from
the statements and enumerates their projections
against R_m exactly: the block construction for
m = 1 to 7 with its counts, the group construction at
the boundary points (w, k) = (3, 1), (4, 0), (4, 1),
(5, 1), and the selector construction for m = 1 to 7,
with the m = 256 counts pinned as arithmetic. The zero
auxiliary boundary is decided by enumerating rule
bodies for w = 3, 4, 5. The full clause space at
m = 1 and m = 2 is searched exhaustively over clause
subsets: nothing below 2 and 4 clauses respectively.
The majority witnesses are checked for m = 2 to 7,
every clause of width at most 2 over 5 variables is
checked majority closed, and R_1 is checked majority
closed with its encoding. The minimally unsatisfiable
families are enumerated in full for k = 0 to 3, counts
and capacities as stated, with the exact regime spot
checked at (k, w) = (1, 2) and (2, 4). Propagation is
compared against exact entailment computed by
enumerating completions: the block construction on
every partial visible assignment for m = 1 to 4 and on
the deep assignments at m = 5, the original chain on
every partial assignment of all its variables for
m = 1 and 2 and on the deep assignments at m = 3, 200
random incidence forest Horn formulas on every partial
assignment, and the cyclic example of section 5, where
the comparison must and does register the miss. The
review page records one more attack the test module
does not carry, a solver search over the full width
three Horn clause space that found no encoding at
m = 3 with 0 auxiliaries and at most 10 clauses, none
at m = 3 with 1 auxiliary and at most 5 clauses, and
none at m = 4 with 1 auxiliary and at most 10 clauses,
with the claimed constructions recovered as controls.

The asymptotic statements, the capacity law at general
k, and the lower bounds at general m are the emails'
arguments, stated above. The enumeration pins the
small cases those arguments rest on, and would have
caught a misstated relation, a wrong count, or a
construction that does not project.

## 7. The one bit join and the smaller grid

A fourth email of 23 November 2026 adds a separator
argument to the constructions above, reviewed in
`v4-projection-gluing-review-2026-11-23.md`. The claim:
if two fully propagation complete CNFs share at most
one variable, their conjunction is fully propagation
complete, and so the block construction of section 1
and the group construction of section 2 are fully
propagation complete over all of their variables,
auxiliaries included, because each block is its
complete prime implicate CNF and neighbouring blocks
meet through one flag. The review rebuilt the blocks,
verified each one standalone, and compared propagation
against exact entailment on every partial assignment
of every variable for m = 1 to 4 at widths 3, 4 and 5:
183,978, 61,506 and 22,140 checks, 267,624 in total,
no disagreement, matching the email's counts digit for
digit. The lemma itself was attacked with random and
structured pairs of fully PC formulas glued along one
variable, 181 conjunctions in all, with no
counterexample; the two variable XOR and equality
pair, sharing two variables, stands as the negative
control the checker catches. The lemma's priority is
unverified: composition across disjoint variable sets
is standard in the propagation complete encoding
literature the email cites, and no source the review
could reach states the one shared variable form. It
stands as the email's candidate argument with finite
evidence beside it, not as a new theorem of this
project.

The same email shrinks the selector construction of
section 3: an unbalanced 13 by 20 grid encodes R_256
with 60 auxiliaries and 545 clauses, the least
auxiliary count inside the two group rectangular
template. The smaller count comes with the loss the
email itself names: the grid is not even visibly unit
refutation complete. Under z false with every pair hit
by a true and b false, the encoding is unsatisfiable,
yet unit propagation derives nothing at all, because
every surviving blocker is a binary clause over
selectors and every chain clause keeps 3 unassigned
auxiliary literals. The review verified the counts,
the projection on all 517 of the email's controls, and
the stall, beside a solver verdict of unsatisfiable
under the same assignment. The 60 and 545 numbers are
never to be quoted without that failure beside them.
The least auxiliary count for width three encodings
of R_m that are visibly propagation complete, and then
again for fully propagation complete encodings, is
posed as OPEN; nothing here closes it.

## References

The two source emails of 23 November 2026, relayed in
ComChat: "fixed-width projection theorem and a 62-bit
construction" (7:59 PM) and "an exact width-three Horn
tradeoff and a new 2026 paper" (8:00 PM). A fourth
email the same day, "propagation across one-bit joins
and a smaller 256-pair grid" (8:38 PM), is the source
of section 7. The reviews:
`v4-projection-width-review-2026-11-23.md` and
`v4-projection-gluing-review-2026-11-23.md`. The
projection page: `v4-the-projection.md`.

Krapivin, A., Przybocki, B., and Subercaseaux, B. The
CNF Encoding Complexity of Boolean Functions.
arXiv:2611.05614, submitted 3 November 2026. Cited by
the second email as neighbouring work on encoding size
with auxiliary variables; its model counts clauses in
a nondeterministic RAM with advice setting and does
not subsume the width three Horn statements here. The
review verified the citation exists as stated and did
not review the paper's contents.
https://arxiv.org/abs/2611.05614
