# The examples: four constructions beside the join

The join page is one sentence about this runner. This page is
not about the runner. It holds four constructions that
arrived in the project's P versus NP discussion by email on
23 November 2026, and stand relayed in ComChat. Each one is
stated exactly, with its scope named. None of them is a
result of this project, and nothing here claims P = NP or
P ≠ NP. What the project adds is the same discipline it
asks of its own proofs: the statement, the mechanism, the
checked cases, and the argument connecting them, each
labeled as what it is. Four MaxSAT controls followed in
the same day's later emails, checked by their sender in
scratch work and rechecked here; they stand as sections 5
to 8, gathered around section 3, whose two lines they
exercise.

`runner/tests/test_v4_the_examples.py` holds the finite
parts.

## Supposition, written before the tests ran

The tests were expected to find all of the following.

- The grouped cut of the equality family holds 2, then 4,
  then 8 distinct residuals for m = 1, 2, 3.
- The interleaved order never passes 3 residuals at any
  cut, and reaches 3 for m = 2 and m = 3.
- The contraction g to floor(0.61 * g), started at the
  statistics page's 3,393,230, reaches 0 in 30 rounds.
- At S = floor(N / (100 * m)) with N = 2^m, a circuit
  description takes fewer than N bits for every m from 8
  to 24.
- Prefix extension on the smallest case, m = 2 and S = 1,
  returns the lexicographically first hard table. Which
  table that is was not predicted; the test compares the
  extension against brute force instead.
- Tree decomposition elimination on the fixed seed rooted
  tree family agrees with brute force on the optimum and
  on the reconstructed witness, on every instance.
- The odd cycle's minimum cost is 0 at even lengths and 1
  at odd lengths, for lengths 3 to 12, while the per edge
  block sums stay at 0 at every length, and removing any
  one edge's clauses from an odd cycle leaves optimum 0.
- The width 2 path decomposition closes the cycle gap
  with at most 8 enumerated rows per bag and at most n
  bags.
- Merging blocks never lowers the summed lower bound on
  the random weighted instances, and on the odd cycle the
  bound stays at 0 until the final merge.
- The threshold ledger at least halves the gap at every
  step, the lines meet at OPT, and the threshold 0
  question agrees with brute force satisfiability.

## 1. The equality family

Take F = the conjunction of (x_i if and only if y_i), for
i from 1 to m. Fix an order in which variables are read.
After a prefix is fixed, the residual is the set of
completions of the unread variables that satisfy F. Two
prefixes with the same set of completions have the same
residual. Count distinct residuals at a cut.

Read every x before any y. At the cut between the blocks,
each of the 2^m prefixes leaves a different singleton set
of valid y strings: the y string equal to the x string
just read. An explicit decision diagram in this order,
distinguishing exact continuation functions, therefore
holds 2^m states at that cut.

Read the variables in pairs, x_i then y_i. At any cut
there are at most 3 distinct residuals, the dead state
included. A prefix is either already dead, or it owes one
y value for the pair in progress, and that value is 0 or
it is 1. Nothing else about the prefix matters to what
remains.

The family is easy to solve, and the page does not pretend
otherwise. The obstruction is to explicit width, in that
order, with that exact observation. A state can carry a
short symbolic name even when the explicit graph of all
states is large. The lesson the discussion took from it:
preserve existence where existence suffices, and charge
the choice of order and representation to the algorithm
that chose them.

The test enumerates the residual truth tables for m = 1,
2, and 3 under both orders and counts them. The general
claim follows from the satisfying continuations directly;
the enumeration is the checked small case, not the proof.

## 2. The Levin style measure

Fix a universal interpreter U, efficiently simulable, with
the input a binary program p and a formula F. Let n be the
encoded length of F. For satisfiable F, define

L(F) = the minimum, over programs p that output a verified
satisfying assignment, of |p| + ceil(log2(t + 1)),

where t is the number of U steps to that output. The
measure charges both the length of the program and the
logarithm of its running time. The interpreter, the input
format, and the verifier are fixed once. No advice, no
per formula initial tape, and no advance knowledge of the
answer is supplied.

Two conditions on U carry the two directions of what
follows. The enumeration direction rests on the one
already stated: U is efficiently simulable, so the
budget search below runs at polynomial overhead. The
other direction rests on the matching condition: U can
run a standard polynomial time witness finder with
polynomial overhead, so a witness finder, if one
exists, is one fixed program on U, of constant length,
running in polynomially many U steps.

The budget search: for a budget b, try every program of
length l from 0 to b, each for at most 2^(b - l) - 1
steps. At one length there are 2^l programs, so that
length costs under 2^b simulated steps, and the whole
budget costs under (b + 1) * 2^b, plus polynomial overhead
for enumeration, simulation, and verification. Run the
budgets in increasing order and the result is one fixed
deterministic witness search.

Three statements, each a restatement of Levin's universal
search with this measure made explicit, not a new result.

1. If P = NP, a single fixed witness program exists: find
   a witness by fixing variables one at a time, keeping
   satisfiability. Its length is constant and its running
   time polynomial, so L(F) is O(log(n + 2)) on every
   satisfiable formula.
2. If fixed constants a and c give L(F) at most
   a * log2(n + 2) + c for every satisfiable F, the budget
   search at that budget decides SAT in polynomial time,
   and P = NP.
3. To prove the opposite on this route, show the measure
   is unbounded in that sense: for every a and c, some
   satisfiable F has L(F) above a * log2(n + 2) + c. One
   fixed search takes the place of an argument about each
   solver, because it covers every fixed polynomial time
   witness finder at polynomial overhead.

Writing the search is straightforward. Proving or
refuting the bound is the open problem. A finite
collection of formulas, however complete, settles neither
direction: a fixed table fits inside a program, so finite
data can falsify a claimed bound on a family, or suggest
an invariant, and no more.

The test pins the arithmetic: the cost function, the
program count 2^(b + 1) - 1 up to budget b, the step bound
(b + 1) * 2^b, and the inequality behind statement 1, that
a fixed program of length l0 running in at most (n + 2)^d
steps has measure at most l0 + d * log2(n + 2) + 1.

## 3. Improve, the MaxSAT gap closer

Take a formula F in conjunctive normal form with m
clauses. For an assignment a, let V(F, a) be the number of
clauses a makes false, and let OPT(F) be the minimum of
V(F, a) over all assignments. F is satisfiable exactly
when OPT(F) is 0.

Keep two numbers about the same object, OPT(F): a lower
line L and an upper line U, with L at most OPT(F) at most
U. The upper line comes with a concrete assignment. The
lower line asserts that no assignment does better. Start
with any assignment, U its violated count, and L = 0. The
gap is g = U - L.

Improve is one fixed deterministic procedure, running in
time polynomial in the size of F. Given F, a current
assignment a, and a valid L, with g above 0, it returns a
new assignment a' and a new lower bound L' such that, with
U' = V(F, a'),

L at most L' at most OPT(F) at most U' at most U, and
U' - L' at most floor(0.61 * (U - L)).

Both lines stay sound and move inward, and the whole
number gap closes by the stipulated fraction, on every
valid state. All work to maintain the bounds counts
toward Improve's running time.

If such an Improve exists, SAT falls at once. Repeat it
while U is above L. The starting gap is at most m, a fixed
fraction below 1 reaches 0 in O(log(m + 1)) rounds, and
each round is polynomial, so the whole algorithm is
polynomial. When the lines meet, the common value is
OPT(F), and F is satisfiable exactly when it is 0.

The converse is elementary too. If P = NP, the question
whether F has an assignment violating at most k clauses
is in NP, hence in P, and polynomially many such questions
plus the standard self reduction compute OPT(F) and an
optimal assignment in polynomial time. Improve returns
that assignment with L' = U' = OPT(F) in one step, gap 0,
which meets the contraction. So a uniform polynomial time
Improve exists if and only if P = NP. This is a
reformulation, proved both directions with elementary
means, and the page claims nothing more for it.

Two small cases, both pinned by the test.

- F = (x OR y). From x = y = false, U = 1 and L = 0. Set
  x true and U becomes 0. The lines meet at 0, and F is
  satisfiable.
- F = (x) AND (NOT x). Every assignment violates exactly
  1 clause, so the lines meet at 1, and F is
  unsatisfiable.

Where the difficulty hides: the upper line is easy to
check, and the lower line is the hard part. A printed
lower bound is not a certificate; an Improve that simply
asserted L = 1 on a satisfiable formula would be refuted
by the satisfying assignment, and soundness is the whole
obligation. The factor 0.61 is not magic. Any fixed factor
below 1 gives logarithmically many rounds, and in this
formulation even a guaranteed decrease of 1 a round gives
at most m rounds. What is hard is a sound, uniformly
efficient progress rule for every formula and every valid
state. A round that searches an exponential set, or an
oracle that hands over OPT, has hidden the difficulty,
and any result obtained that way stays labeled oracle
aided.

The test pins the contraction arithmetic, including the
30 rounds from the statistics page's starting gap of
3,393,230, and runs a brute force Improve on toy formulas
to check that both lines stay sound and the gap closes.
The brute force stands in for the assumed polynomial
procedure; it demonstrates the bookkeeping, not the
existence.

## 4. From P = NP to a hard truth table

Assume P = NP. This construction turns that assumption
into a circuit lower bound for an explicit language. It
is standard, and it is scoped as such: counting, plus the
assumption making a hard object uniformly findable.

Let m be an input length and N = 2^m. Take
S = floor(N / (100 * m)) gates over a fixed binary Boolean
basis. Describing a circuit of at most S gates, gate by
gate in topological order, each gate by its type and the
indices of its two incoming wires, with the output named
at the end, costs O(S * log(m + S)) bits, with slack at
this choice of S. The at most is carried by the count
itself: a description pads its gate list with unused
gates up to exactly S, or encodes the gate count beside
the gates, so shorter circuits are counted in the same
scheme and add no factor of their own. So the number of
circuits with at most
S gates is less than 2^N, the number of N bit truth
tables. Some table therefore needs more than S gates.

Now find one. Given a full explicit table T, whether a
circuit of at most S gates computes T is in NP relative
to the explicit length N: guess the circuit and check
every row. Under the assumption, its absence is decidable
in polynomial time in N. Given a prefix, whether some
completion passes the hardness test is likewise in NP,
hence in P under the assumption. The query is put to
the assumed procedure in the length of the canvas, not
of the prefix: it hands over unary 1^N, or a length N
canvas with the prefix written on it, so the completion
it guesses is polynomial in its encoded input length
even when the prefix is empty. Extend the prefix bit by
bit, 0 when a hard completion still exists and 1
otherwise, and N queries build the lexicographically
first hard table. The language that, on input x of length
m, builds that table and returns its bit at x lies in
deterministic time 2^O(m) and has circuit complexity
Omega(2^m / m), conditional on P = NP.

The scope, plainly: the language sits in exponential
time, and a contradiction would need a separate upper
bound for the same language in the same circuit model.
What the construction shows is narrower and still worth
having on the page. An algorithmic assumption can make a
hard object uniformly findable, and finding it is what
turns a counting argument into a lower bound for an
explicit language. Williams' transfer theorems, where
faster satisfiability algorithms yield circuit lower
bounds, are the stronger precedent of the same shape.

The test pins the counting for m from 8 to 24 under one
concrete description scheme, 4 bits for the gate type and
two wire indices of ceil(log2(m + S)) bits each, output
named once, and finds the description shorter than N
throughout. It also builds the lexicographically first
hard table for m = 2, S = 1 over a 4 operation basis, by
the same prefix extension, with brute force enumeration
standing in for the assumed polynomial queries, and
checks the result against the full enumeration of hard
tables.

## 5. Tree decomposition elimination, a positive control

Section 3 keeps two lines about one object and asks what a
uniform procedure would have to do to close the gap
between them. This control closes the gap outright, on a
family where the structure is supplied. Take a weighted
formula: each clause carries a positive integer weight,
and the cost of an assignment is the total weight of the
clauses it makes false. OPT is the minimum cost. The
discipline is the one section 3 states, unchanged: the
same formula, the same weights, and the same objective
for both lines, with L at most OPT at most U throughout.

Suppose a tree decomposition of the variable interaction
graph is supplied and checked: a tree of bags of
variables, every clause's variables together in some bag,
and the running intersection property, that the bags
holding any one variable form a connected subtree.
Assign each clause exactly once, to a bag that holds all
of its variables. Then eliminate, bottom up. At each bag,
for each assignment to the bag's separator with its
parent, take the minimum, over the bag assignments that
extend it, of the local violated weight plus the optimal
child costs at their separators. Running intersection
justifies the join: once a separator is fixed, the
subtrees below it share no other variable, so their
cheapest choices combine without interference. Induction
up the tree gives the root optimum, and backtracking the
minimizing choices reconstructs an assignment that scores
it. The elimination supplies both lines at once: the root
value is a lower bound by the induction, and the
reconstructed assignment is an upper bound by direct
scoring, and the two agree.

The running time is 2^(w + 1) times a polynomial in the
input size, where w is the width, the largest bag size
minus 1, and the polynomial charges the bit cost of the
weights along with the counts. With width O(log n) and a
polynomial size supplied decomposition, the whole
computation is polynomial. If a proposed solver has to
discover the decomposition itself, that search is charged
work too; it is not smuggled in as a gift. The method is
standard exact elimination, Dechter's bucket elimination
in another dress, and the page claims nothing more for it
than this: a positive control, a place where the gap
provably closes, against which a proposed gap closer can
be measured.

The test checks the decomposition rather than trusting
it, then runs the elimination on a fixed seed family of
rooted trees with one and two variable weighted clauses,
1 to 8 variables, 800 instances, and compares the optimum
and the reconstructed witness against direct scoring of
every assignment. It also runs the weighted form of
section 3's smallest control, (x) AND (NOT x) with
weights 2 and 3, where every assignment violates exactly
one clause and the lines meet at 2.

## 6. The odd cycle: parity, block sums, and a separator

Take the cycle of n variables where each adjacent pair is
constrained to differ, written as weighted clauses of
weight 1: each edge contributes (x_i OR x_j) and
(NOT x_i OR NOT x_j), so an assignment pays exactly 1 for
each edge whose ends agree and 0 for each edge whose ends
differ. Alternating values satisfy every edge, and an
alternating assignment closes consistently exactly when n
is even. The minimum cost is 0 for even n and 1 for odd
n: on an odd cycle some edge must agree, and an
assignment that alternates until the final edge pays for
that edge alone. The test pins lengths 3 to 12 against
brute force.

Now watch the lower bounds. Give each edge its own block
and minimize each block independently: every block
reaches 0, so the summed lower bound is 0 at every
length, while OPT is 1 at the odd lengths. The bound is
sound and stuck. Stronger, every proper subset of an odd
cycle's clauses is satisfiable: remove one edge and the
path that remains alternates, so no sum over proper
disjoint blocks sees the 1 either. The information the
local bounds lose is the parity, and it is lost exactly
at the join, where the two ends of the chain must agree
about a variable that neither block owns outright.

A small separator recovers it. The path decomposition of
section 5, with bags of 3 variables and width 2, carries
the shared assignments the block sums threw away, and the
elimination closes the gap on this family in linear time:
at most n bags, at most 8 enumerated rows in each. The
test runs it at lengths 3 to 12 and checks the optimum,
the witness, and the row count.

## 7. Block merge monotonicity

Partition the clauses of a weighted formula into blocks,
minimize each block on its own, and add the minima. The
sum is a lower bound on OPT, because any one assignment
pays at least each block's minimum. Merging blocks can
only raise the sum: the merged block is minimized under
one common assignment, where the separate blocks each had
an assignment of their own, so the merged minimum is at
least the sum of the minima it replaces. That is the
whole theorem, and it is short: block sums are sound, and
merging blocks moves L upward or leaves it standing.

The odd cycle shows what the theorem does not give. From
one block per edge to a single block, the bound on an odd
cycle sits at 0 through every merge until the last one,
which closes it at once. Monotonicity promises movement,
never a rate; a contraction claim needs more than it.
What the example tracks, and what any merge based closer
would have to report, is the size of the blocks and
separators involved, the work spent choosing a merge, and
the improvement of L that the merge bought. The test pins
the monotonicity on random weighted instances, with each
merged bound checked against the single block bound,
which is OPT itself, and pins the flat then sudden
profile on the odd cycles of lengths 5, 7, and 9.

## 8. The threshold query

Between the lines of section 3 there is a sharper
question. With integer costs, ask whether an assignment
of cost at most floor((L + U) / 2) exists. A yes answer
is worth anything only with the assignment in hand,
verified by scoring: it lowers U to that assignment's
cost. A correct no answer raises L above the threshold.
Either way the gap at least halves, so logarithmically
many threshold answers close it, and a ledger that
records the cost and the source of every update, which
line moved and on which answer, is what makes the closing
auditable rather than asserted. Certifying MaxSAT already
works in this discipline: the work of Berg and colleagues
logs proof steps in VeriPB, so the lower line travels
with a checkable certificate instead of a claim.

The zero case is the hinge. At threshold 0 the question
is whether a cost 0 assignment exists, which in the
unweighted reading is satisfiability itself. So a
polynomial threshold decider gives a polynomial exact
solver: halve down to OPT, then reconstruct a witness by
fixing variables one at a time and asking again. Under
P = NP the threshold question is in P, because it is in
NP, and the solver exists; that is the same equivalence
section 3 states for Improve, seen from the threshold
side. The test pins the finite part: the halving ledger
on toy formulas and on the cycles, with the source of
every step recorded, the lines meeting at OPT beside a
witness that scores it, and the threshold 0 question
agreeing with brute force satisfiability on random
instances.

## What was found

The run agreed with the supposition on every point.

- Grouped order: the counts along the x block double each
  step, and the cut after the block holds 2, then 4, then
  8 residuals for m = 1, 2, 3, as predicted. Past the cut
  the counts fall again, 5, 3, 2 for m = 3, as the y
  readings retire the pending singletons.
- Interleaved order: the largest count at any cut is 2
  for m = 1 and 3 for m = 2 and m = 3. The bound of 3 is
  met once a pair can die, not merely respected.
- The contraction from 3,393,230 reaches 0 in exactly 30
  rounds of g to floor(0.61 * g), the figure the
  statistics page's thought experiment states.
- The counting: at m = 20, N is 1,048,576 and S is 524,
  and the concrete description takes 12,586 bits, far
  under N. The same holds at every m from 8 to 24.
- Prefix extension at m = 2, S = 1: 9 of the 16 tables
  are computable with at most 1 gate over the test basis,
  and the extension returns (0, 0, 1, 0), the table that
  is 1 only on the assignment (1, 0). Brute force agrees
  it is the lexicographically first of the 7 hard tables.
- Tree elimination: 800 rooted tree instances, 53,272
  assignments scored by the brute force comparison, and
  the optimum and the reconstructed witness agreed with
  direct scoring on every instance. The weighted control
  meets at 2, as stated.
- The odd cycle: minimum cost matched the parity at every
  length from 3 to 12, the per edge block sums stayed at
  0 at every length, and every single edge removal on the
  odd lengths left optimum 0. The width 2 elimination
  closed the same gap with at most 8 rows per bag.
- Block merges: on 200 random weighted instances the
  summed bound never fell under a merge and never passed
  OPT, and on the odd cycles of lengths 5, 7, and 9 it
  sat at 0 until the single block merge closed it at 1.
- The threshold ledger: on the toy formulas and the
  cycles of lengths 3 to 9, every step at least halved
  the gap, every update named its source, and the lines
  met at OPT beside a witness that scores it. At
  threshold 0 the question agreed with brute force
  satisfiability on 100 random instances.
- A correction, recorded on 23 November 2026 from the
  review of these examples after they landed. The test
  helper that computes the small case tables first
  pooled the wires of different partial circuits, which
  computes a depth bound rather than a gate bound: at
  m = 3 and at most 2 gates it reported 164 tables
  against the true 78. The helper now keeps each
  partial circuit's wires together, the 3 input, 2 gate
  case is pinned at 78, and the 0 and 1 gate counts
  stand unchanged. The same review made the two float
  helpers exact: the Levin log term and the contraction
  are integer arithmetic now, each pinned at the edge
  where the float form first errs.

## What this is not

Not a proof of P = NP, and not a proof of its opposite.
Not a claim about the runner, its gate, or its proofs of
itself; the v4 pages keep their own scope, and this page
borrows only their habit of naming it. The constructions
are a meeting place: when a new mechanism is proposed in
the discussion, this page is where its statement can be
set beside these, each with its assumptions on its
face, and checked the same way.
