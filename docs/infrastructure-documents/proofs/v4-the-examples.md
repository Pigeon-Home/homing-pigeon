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
labeled as what it is.

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
this choice of S. So the number of circuits with at most
S gates is less than 2^N, the number of N bit truth
tables. Some table therefore needs more than S gates.

Now find one. Given a full explicit table T, whether a
circuit of at most S gates computes T is in NP relative
to the explicit length N: guess the circuit and check
every row. Under the assumption, its absence is decidable
in polynomial time in N. Given a prefix, whether some
completion passes the hardness test is likewise in NP,
hence in P under the assumption. Extend the prefix bit by
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

## What this is not

Not a proof of P = NP, and not a proof of its opposite.
Not a claim about the runner, its gate, or its proofs of
itself; the v4 pages keep their own scope, and this page
borrows only their habit of naming it. The constructions
are a meeting place: when a new mechanism is proposed in
the discussion, this page is where its statement can be
set beside these four, each with its assumptions on its
face, and checked the same way.
