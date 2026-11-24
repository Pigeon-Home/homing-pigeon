# The projection: a compact Horn chain with an exponential flat boundary

The examples page holds four constructions beside the join.
This page holds a fifth, smaller one, which arrived in the
project's P versus NP discussion by email on 23 November
2026, in the same message that reviewed the three chart
candidates, and stands relayed in ComChat. It grew out of
the joining solver experiment recorded on the examples
page: a satisfiability question that stays cheap while an
intermediate representation is kept, and the price of
forgetting it. Like the four before it, this construction
is not a result of this project, and nothing here claims
P = NP or P ≠ NP. What the project adds is the same
discipline it asks of its own proofs: the statement, the
mechanism, the checked cases, and the argument connecting
them, each labeled as what it is.

`runner/tests/test_v4_the_projection.py` holds the finite
parts.

![One relation, two sizes: the Horn chain and its flat boundary. On the left, the compact Horn chain, pairs feeding t_i, the running conjunction r_i, and r_m forcing z, 3m + 1 clauses of width at most 3. On the right, the flat boundary after the internal bits are forgotten: the least number of plain CNF clauses over the visible variables only, 2, 4, 8, 16, 32 for m = 1 to 5](../../../assets/horn-projection-flat-boundary-2026-11-23.svg)

## Supposition, written before the tests ran

The tests were expected to find all of the following,
exactly as the email stated them.

- The projection of the system below onto its visible
  variables is exactly the relation: if every pair has a
  true bit, z must be true. Checked by enumerating every
  visible assignment against every completion of the
  internal bits, for m up to at least 4.
- With z false, the minimally falsifying visible patterns,
  one true bit chosen from each pair and no other visible
  bit true, number exactly 2^m.
- Every clause over the visible variables that the relation
  implies and that some minimal pattern falsifies is
  falsified by exactly one minimal pattern, so no flat CNF
  for the relation has fewer than 2^m clauses.
- The 2^m pattern clauses, one per choice of one bit from
  each pair, do represent the relation, so the flat minimum
  at the checked sizes is exactly 2^m.
- Unit propagation from the visible inputs derives z
  exactly when every pair has a true bit, and the canonical
  completion, t_i the OR of its pair and r_i the running
  conjunction, satisfies every clause.

## 1. The system

Fix m. The visible variables are the pairs a_i, b_i for i
from 1 to m, and one output z. The internal variables are
t_i and r_i for i from 1 to m. The clauses are Horn rules,
each with at most one positive literal:

- a_i implies t_i, and b_i implies t_i, for each i.
- t_1 implies r_1.
- r_(i-1) and t_i together imply r_i, for i from 2 to m.
- r_m implies z.

That is 3m + 1 clauses, each of width at most 3. The chain
clauses are the only ones of width 3. Horn satisfiability
is decidable in linear time (Dowling and Gallier, 1984),
and here no solver is needed at all: unit propagation from
the visible inputs walks the chain once, because t_i is
forced exactly when its pair has a true bit, r_i is forced
exactly when every pair up to i has a true bit, and z is
forced exactly when r_m is.

## 2. The projection is the stated relation

Existentially eliminate the internal variables: a visible
assignment is in the projection when some completion of
the t_i and r_i satisfies every clause. The claim is that
the projection is exactly the relation R: it is not the
case that every pair has a true bit while z is false.

One direction is forced by propagation. Suppose every pair
has a true bit and z is false. In any completion, each pair
rule forces every t_i true, the chain then forces every
r_i true, and the last rule forces z true, against z false.
So no completion exists, and the assignment is outside the
projection.

The other direction is a construction. Given a visible
assignment that satisfies R, set t_i to the OR of its pair
and r_i to the running conjunction, r_i true exactly when
every pair up to i has a true bit. Every pair rule holds,
because a true a_i or b_i makes t_i true. The chain rules
hold by the definition of the running conjunction. If
every pair has a true bit, then r_m is true, and R gives z
true, so the last rule holds. If some pair has no true bit,
r_m is false and the last rule holds whatever z is. So a
completion exists, and the assignment is in the projection.

## 3. The flat boundary

Now write R as a plain CNF over the visible variables
alone, no internal bits. The claim is that at least 2^m
clauses are needed, and 2^m suffice.

Call a visible assignment a minimal pattern when z is
false, exactly one bit of each pair is true, and no other
visible bit is true. There are 2^m minimal patterns, one
per choice of a bit from each pair. Each falsifies R, and
each is minimal: turning its one true bit in any pair off
leaves that pair empty, and R holds again.

Take any clause C over the visible variables that R
implies, so C is true on every assignment in R, and
suppose some minimal pattern P falsifies C. C must contain
the positive literal z: if it did not, the assignment that
agrees with P on the pairs and sets z true would still
falsify C, and that assignment is in R. C must also contain
a negated chosen bit from every pair: if some pair
contributed no negated literal to C, the assignment that
agrees with P except that both bits of that pair are off,
with z still false, would still falsify C, and that
assignment is in R. So C is falsified only by assignments
with z false and, in every pair, the chosen bit of P true.
Among the minimal patterns only P itself has that shape:
any other minimal pattern differs from P in some pair,
choosing the other bit, and satisfies C there. So C
excludes at most one minimal pattern.

A CNF for R must exclude every minimal pattern, since each
one falsifies R, and each of its clauses excludes at most
one. So it has at least 2^m clauses. The bound is tight:
the 2^m clauses (z, or the negation of the chosen bit of
pair 1, or the negation of the chosen bit of pair 2, and
so on), one per minimal pattern, are each implied by R and
together exclude exactly the assignments outside R.

## 4. The checked cases

The email reported the projection checked directly,
through m = 4. The test in this tree rechecks it and goes
one step further on two of the parts. The projection is
enumerated exactly for m from 1 to 5: every visible
assignment, against every completion of the internal bits,
agrees with R. The minimal patterns are counted and their
shape verified for m from 1 to 5: exactly 2^m, each with z
false and exactly one true bit per pair. The clause lemma
of section 3 is verified by exhaustion for m from 1 to 4:
every clause over the visible variables that R implies and
that some minimal pattern falsifies is falsified by
exactly one minimal pattern, so the flat minimum at those
sizes is exactly 2^m, with the achieving CNF of section 3
checked to represent R exactly. Unit propagation deciding
z, and the canonical completion of section 2 satisfying
every clause, are checked for m from 1 to 5. The counts of
the system itself are pinned: 3m + 1 clauses, width at
most 3, at most one positive literal per clause.

The asymptotic statement, that the flat minimum is 2^m for
every m, is the argument of section 3, not the enumeration.
The enumeration pins the small cases the argument rests
on, and would have caught a misstated relation, a missing
pattern shape, or a clause escaping the lemma.

## 5. What it is a picture of

The relation is easy. Its Horn system is satisfiable in
linear time, and propagation answers the only question the
chain asks. Nothing here is hard to decide. What grows is
a representation: forget the internal bits, insist on
plain CNF over the visible variables, and the same relation
costs 2^m clauses. That is the stress the construction
puts on the proposed compressor of the joining solver
experiment. A compressor that keeps an intermediate
representation, the way this chain keeps t_i and r_i,
carries the relation in 3m + 1 clauses. One that flattens
to the visible variables pays the boundary in full. The
lower bound is about representation size after forgetting,
not about the cost of deciding satisfiability, and the
page does not claim more for it.

## Reference

Dowling, W. F. and Gallier, J. H. Linear-time algorithms
for testing the satisfiability of propositional Horn
formulae. Journal of Logic Programming, 1984.
https://doi.org/10.1016/0743-1066(84)90014-1
