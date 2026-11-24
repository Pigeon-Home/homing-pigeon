# The joining solver: prefix extension under a compressor, as a research artifact

The first of the 2 emails of 23 November 2026 that the
completion checklist covers proposed a structured solver:
extend a formula's prefixes variable by variable, keep the
list of live prefixes small with a compressor, and ask what
the compressor has to promise for the procedure to decide
satisfiability. `properties.md` states the conditional
consequence as its Theorem 4, at strength 4, and records
the experiment that was run on small instances the same
day, at strength 1. The checklist's item 23 named what was
missing: the solver as a research artifact, a thing in the
project that embodies the construction, with the equality
family obstruction as its first worked example. This page
is that artifact's write up. The solver stands in
`runner/tools/joining_solver.py`, and
`runner/tests/test_v4_the_joining_solver.py` pins the
finite behaviour this page reports.

Nothing on this page is a result of this project in the
strong sense, and nothing here claims P = NP or P ≠ NP.
Theorem 4 is a conditional: its premise is a compressor
with a stated contract and a polynomial bound, and the
contract is a specification. Naming a live prefix is a
specification; a cheap rule that finds one is the research.

## Supposition, written before the tests ran

The tests were expected to find all of the following.

- The exact compressor, one representative per distinct
  residual function, keeps the contract at every round:
  some prefix in the list before compression can be
  completed to a satisfying assignment exactly when some
  prefix in the list after compression can.
- On a fixed seed batch of 80 random 3-CNF instances on 10
  variables, 40 at 20 clauses and 40 at 43 clauses, the
  exact compressor's verdict agrees with brute force on
  every instance, and the contract holds at every round of
  every run. This is the shape of the experiment
  `properties.md` records, rerun as an artifact with its
  seed named.
- The keep first compressor, which keeps only the first w
  prefixes of the extended list, breaks the contract and
  returns a wrong verdict on satisfiable instances built
  to expose it: the unit clause on the first variable,
  padded with free variables, at w of 1, of 4, and of 16,
  where the round at which the list first passes w entries
  is the round that drops every live prefix.
- On the equality family of the examples page, the CNF
  with one equivalence per pair, the solver's retained
  count under the exact compressor follows the family's
  residual counts: along the grouped order's first block
  the count doubles at every step and stands at exactly
  2^m at the cut, for m from 1 to 4, and under the
  interleaved order the count never passes 3 and reaches
  3 once a pair can die, for m from 2 to 4.

## The construction

Fix a CNF formula over variables 1 to n, and an order of
the variables. A prefix is a partial assignment to an
initial segment of the order. The solver keeps a list of
prefixes, starting with the empty prefix alone, and works
in rounds, 1 round per variable:

1. Extend: replace each prefix in the list by its 2
   extensions, the next variable set to 0 and to 1.
2. Compress: hand the extended list to a compressor, which
   returns a list no longer than the one it was given.
3. Record the round: the sizes before and after, and
   whether the contract, below, held between them.

After the last variable, every prefix in the list is a
complete assignment, and the verdict is satisfiable
exactly when one of them satisfies every clause. A prefix
can be completed when some assignment to the variables
not yet read extends it to a satisfying assignment. The
residual function of a prefix is the function from
completions to truth the prefix leaves behind: 2 prefixes
have the same residual when exactly the same completions
satisfy the formula under each. In this artifact the
residual and completability are computed by exhaustive
search over the unread variables, which is what makes the
artifact an instrument for small instances rather than a
solver for large ones: the contract is checked at every
round, never assumed.

## The compressor contract

A compressor keeps the contract when, at every round, some
prefix in the list before compression can be completed to
a satisfying assignment exactly when some prefix in the
list after compression can. The contract is the whole
premise of Theorem 4, and it is a statement about
completability, not about size: a compressor may keep dead
prefixes and drop live ones only if it never drops the
last live one. A compressor that keeps the contract at
every round gives the right verdict, because completability
is preserved from the empty prefix, which can be completed
exactly when the formula is satisfiable, down to the final
list, whose members can be completed exactly when they
satisfy.

## Two compressors

**The exact compressor** keeps 1 representative of each
distinct residual function in the extended list, first
occurrence winning, order preserved. It keeps the
contract, and the reason is short: 2 prefixes with the
same residual can be completed by exactly the same
assignments, so dropping all but 1 of them never changes
whether some prefix in the list can be completed. The
dead prefixes, whose residual is the empty function, share
1 representative between them. What the exact compressor
does not promise is size: the number of distinct residuals
can be as large as the number of prefixes, and the
equality family below shows a cut where it is exactly
2^m. Computing the residual is the other half of the
price: in this artifact it is exhaustive search, and in
any real solver it is the work the contract hides.

**The keep first compressor**, at a width w, keeps only
the first w prefixes of the extended list, in the order
the extensions were generated, 0 before 1 at every step.
It promises a size and nothing else. When the extended
list holds more than w prefixes and every live prefix sits
past the first w, the kept list has no live prefix at all,
the contract breaks at that round, and no later round
recovers one: extensions of dead prefixes are dead. The
verdict then reads unsatisfiable on a satisfiable formula,
which is the failure the experiment records.

## The conditional theorem

Theorem 4 of `properties.md`, restated. Suppose a
deterministic compressor, running in polynomial time,
reduces the list of retained prefixes of a formula at
every level to at most a polynomial number of prefixes,
and keeps the contract above. Then following the retained
prefixes to complete assignments decides SAT in polynomial
time. The contract is the premise. A proof that a small
list exists gives no bound on the cost of finding it, and
the exact compressor of this page is the standing example:
it keeps the contract at every round, and its list is
exponential at the equality family's grouped cut, and its
residuals are computed by search. Each half of the premise
is easy alone. The research is a compressor with both.

## The equality family obstruction

The examples page, `v4-the-examples.md`, works this family
as its first construction: for m pairs, the relation that
each pair agrees, x_i if and only if y_i. As a CNF it is 2
clauses per pair. Under the grouped order, all the x
variables first and then all the y variables, the residual
count at the cut between the blocks is exactly 2^m: each
assignment to the x block leaves a different set of
completions behind it, because the y block must match it
bit for bit. Under the interleaved order, x_1, y_1, x_2,
y_2 and so on, the count never passes 3, the dead state
included. The solver of this page, run on the family's
CNF, retains exactly those counts under its exact
compressor, and the tests pin them.

The obstruction is about what a size bound can mean. The
same function, the same formula up to clause order, has a
retained list of 2^m under 1 order and of at most 3 under
another. So a polynomial bound on the list is never a
property of the function alone: it is a property of the
function, the order, and the representation the compressor
is allowed to keep. A compressor that could choose the
interleaved order here would still have to find it, on
every input, and charge the finding. This is the first
worked example the checklist asked for, and it is why the
projection page, `v4-the-projection.md`, which grew out of
this experiment, states its lower bound as a bound after
forgetting, against a named representation.

## The experiment, as an artifact

`properties.md` records the run of 23 November 2026: on
the equality family the grouped order's residual state
count peaked at 2^m at the cut for m from 1 to 7, and the
interleaved order never exceeded 3; on 80 random 3-CNF
instances on 10 variables, at clause ratios 2.0 and 4.26,
the exact compressor's verdict agreed with brute force
every time and the contract held in every round; a keep
first compressor at w of 4 and of 16 violated the contract
on most satisfiable instances and returned a wrong verdict
on every instance it violated; and the exact variable
projection law on 2-CNF, the positive control, held on
1,013 exhaustive small cases, which the projection page
now carries. That record stood at strength 1, a finite
record about small instances, and until this page it stood
without an artifact: the run was described, and no code in
the project embodied it.

The artifact reruns the same shapes with its seed named,
and the tests pin the outcomes: the exact compressor's
verdicts and contract on the seeded batch of 80, the keep
first failures at w of 1, of 4, and of 16 on the unit
clause family built to expose them, and the equality
family's counts under both orders. Where the record says
most satisfiable instances, the artifact says something
narrower and checkable: on instances built so that every
live prefix sits past the kept width, the failure is
total, and it happens at the first round whose extended
list passes the width.

## Conclusions against the supposition

(Written after the tests ran.)

Every expectation in the supposition held, at the sizes
the tests name.

- The exact compressor kept the contract at every round
  of every run the tests made: the seeded batch, the unit
  clause family, and the equality family under both
  orders.
- On the seeded batch (seed 20261123; 40 instances at 20
  clauses, 40 at 43, all on 10 variables) the exact
  compressor's verdict agreed with brute force on all 80
  instances, the contract held at every round, and every
  satisfiable verdict carried a witness that satisfies
  its formula. The batch was a real mix: both verdicts
  occurred.
- The keep first compressor failed exactly where the
  supposition put the failure: at w of 1 the contract
  broke at the first round, on the 3 variable instance;
  at w of 4 at the third round, on the 6 variable
  instance; at w of 16 at the fifth round, on the 8
  variable instance. Each time the verdict read
  unsatisfiable on a satisfiable formula, and the exact
  compressor answered the same instances correctly with
  the contract intact.
- On the equality family the retained counts under the
  exact compressor equal the residual counts computed
  from the definition, for m from 1 to 4 under both
  orders: the grouped cut stands at exactly 2^m, and the
  interleaved counts never pass 3 and reach 3 for m from
  2 to 4.

One pin of this page failed on its first run and is
worth recording: the test looked for a phrase of the
conditional theorem in the wrong case, and the
correction was to the test, not to the page. The
mathematics of the supposition needed no correction.

## What this artifact does not establish

- No asymptotic bound. The counts are finite, at the
  sizes the tests name, and the theorem they serve is
  conditional.
- No cheap compressor. The exact compressor pays for its
  contract with exhaustive residuals; the keep first
  compressor pays for its size with the contract.
- No claim about the recorded run beyond its record. The
  artifact reproduces the record's shapes under a named
  seed; it does not re derive the record's own instances,
  which were not kept.
- Nothing about P = NP or its negation, except the
  conditional of Theorem 4, at the strength
  `properties.md` states it.
