# The November research loops: a checked review and re-evaluation

On 24 November 2026 a long run of ChatGPT research
arrived by email and was relayed into ComChat: the
simulation pair at head cfc79b1, the research loop at
3414840, the research loop at 379cfc6, the fresh CI
reviews, and a set of collision and counting
candidates for the weak two union basis problem. The
conductor directed me to research and expand the
ideas in those emails and to implement what holds.
This page is that work. It also re-evaluates the
claims checked in the three refutation rounds of 23
November and in the candidate bounds work, against
everything the new emails say, because the new
emails build on that earlier work and in one place
restate its status.

I am the reviewer here, not the author of the claims
under review. ChatGPT's own entries carry their
caveats in ComChat, and several of them say plainly
that no search ran. Where a claim is a paper argument
with a cited literature step, I say so and check only
what computation can check: the arithmetic, the
finite cases, and the controls. Where a claim is
finite and checkable, I check it with an independent
implementation whose only shared assumption with the
email is the statement itself.

## Triage

Every concrete claim or implementable idea in the
batches, ranked by how checkable it is and what it is
worth to the proof program.

Tier 1, finite and checked in this pass.

1. The nine point pruning rule (loop 3414840, basis
   entry). For a pair graph G on nine points with p
   edges, degree sum S counting wedges and t counting
   triangles, the number u of three sets containing
   no selected pair is exactly 84 minus 7p plus S
   minus t. A weak 2 basis at budget 44 forces p at
   least 9 from the triple count alone, and p equal
   to 9 forces a total of at least 45, so p at least
   10 in any budget 44 family. The same entry gives
   exact small rows: a three set is covered exactly
   when it is selected or contains a selected pair,
   and a four set is covered exactly when it is
   selected, contains a selected triple, or contains
   two disjoint selected pairs.
2. The randomized clock estimator (simulation pair,
   part 2). A clock C with survival Pr(C at least t)
   equal to 1 over (t plus 1) squared, the estimator
   Y equal to tau plus 1 on a verified hit by both
   the clock and a horizon H and zero otherwise, has
   expectation equal to the truncated discounted mass
   Z_H, second moment equal to Pr(tau at most H), and
   expected charged steps at most the sum of
   1 over (t plus 1) squared, below 0.645. The tail
   beyond H costs at most 1 over (H plus 2). The
   clock has an exact sampler whose conditional
   advance probabilities are ((t plus 1) over
   (t plus 2)) squared. The companion detection clock
   and the anytime miss bound U_N equal to
   1 minus delta to the power 1 over N come with it.
   The toy calibration: three fair bits, a success
   costing 3 plus m steps, formulas pinning k bits
   give mass 2 to the minus k and Z equal to that
   mass over (4 plus m).
3. The Horn closure lift (loop 3414840, lift entry).
   For a Horn CNF, least forward closure under a
   fixed visible input decides extendibility and
   constructs a witness, so the summary Q and the
   lift L are both polynomial here, and the two
   refutation obligations F(y,x) and not Q(y), and
   Q(y) and not F(y,L(y)), are both unsatisfiable.
   A lift that drops an intermediate atom is caught
   by the diagnostic search F(y,x) and not F(y,L(y)).
4. The graph coloring menu (loop 3414840, menu and
   coloring entries). For the Horn relation built
   from a graph G, with at most one visible flag set
   and one hidden bit per edge, the minimum static
   menu size is exactly the chromatic number of G.
   Beside it, the identity relation F(y,x) given by
   x equal to y has menu width exactly 2 to the
   power of the number of visible bits, with a
   trivial lift.
5. The quotient certificate method (loop 379cfc6,
   quotient entry). A partition of a finite labeled
   transition system is an exact quotient when
   grouped states agree on observations and, for
   every label, on the set of successor classes.
   Then quotient traces and concrete traces agree.
   The five state claim model quotients to three
   classes with observation chain (0,0), (1,1),
   (2,1). The negative control: two states in one
   class, one reached by a and one by b, with c
   enabled only at the second, gives an abstract
   a then c path with no concrete trace.
6. The collision candidate B(10) at least 48 (fresh
   candidates entry). Two disjoint classes of
   redundant representations, the containment pairs
   and the singleton pairs, give the counting bound
   2 to the n minus 1 at most b(b plus 1) over 2
   minus (I minus n) minus p. With the forced triple
   count and one premise carried from an earlier
   email (a target tail count giving I at least
   2b minus n plus 20 at n equal to 10), the
   arithmetic is said to exclude every b at most 47.

Tier 2, paper arguments with checkable arithmetic.

7. The leading selector gap (loop 3414840, selector
   entry; loop 379cfc6, bracket entry). A candidate
   exact total of 31h plus 15 in the ordinary edge
   leading selector scope, resting on a deletion
   argument in the triple layer: if the triple
   hypergraph H on n equal to 4h plus 1 points has
   e(H) equal to 4h plus 3, then some vertex has
   triple degree at least 4, and one deletion step
   of the cited transversal bound contradicts the
   transversal lower bound 2h plus 1, so e(H) is at
   least 4h plus 4. The bracket entry pushes a
   stronger finish in a doubled scope, 31h plus 40,
   by the same charging method. Both rest on cited
   stability and transversal results and on case
   analysis that computation alone cannot settle.
8. The Candidate C transfer across sizes (loop
   379cfc6, padding entry). A conditional wrapper
   argument: canonical padding moves a witnessed
   defeat across a window of lengths at logarithmic
   extra program cost. The wrapper arithmetic is
   checkable as bookkeeping; the transfer itself is
   a conditional theorem shape, not a finite claim,
   and its premises name an encoding this project
   has not fixed. Left as a paper item.
9. The OBDD singleton support normalization
   (simulation pair, part 1, section 2). A proposed
   normalization of the y suffix of an ordered
   diagram, with mask accounting. The email itself
   assigns it to a paper and pencil lane until the
   node accounting lemma is agreed. Left open.

Tier 3, engineering observations, noted not checked
here: the CI artifact upload order, the queued seed
replacement risk, the mutation floor status list
omitting interrupted mutants, and the coverage job
that can show green over a failed suite. These are
source readings against pinned heads, plausible on
their face, and they belong to the CI lane rather
than to this proof review. The nine point budget 44
decision itself, and the reported finite lower bound
of 45 for nine points, remain open: the simulation
email itself names the 45 claim a replay target, and
nothing in this pass settles it.

## Suppositions, written before the checks ran

S1. The wedge identity for u holds on every graph,
    and the p equal to 9 layer is tight: three
    disjoint triangles give a total of exactly 45,
    so the pruning rule excludes p at most 9 and
    nothing stronger at that layer.
S2. The small row characterizations for three sets
    and four sets hold on arbitrary families with
    forced singletons, with no missing case: in
    particular the pair plus triple overlap case
    reduces to the triple case because singletons
    are forced.
S3. The clock algebra is exact as stated, including
    the step bound below 0.645, and the toy
    calibration values match full enumeration of the
    eight assignments for every clause count m from
    0 to 6 and every pin count k from 0 to 3.
S4. Least closure agrees with brute force
    extendibility on random Horn formulas, and the
    deliberately bad lift is caught with the exact
    counterexample the email predicts in shape: a
    visible input, a valid alternative assignment,
    and a lift output that fails.
S5. Minimum menu size equals the chromatic number
    on every graph up to five vertices and on random
    larger graphs, computed by two independent
    methods (row enumeration for the menu, coloring
    search for the chromatic number), and the
    identity control needs exactly 2 to the k rows.
S6. The stability condition is exactly the dividing
    line in the quotient method: stable partitions
    have identical concrete and quotient trace
    languages, and the negative control partition is
    unstable and exhibits the spurious a then c
    trace.
S7. The collision inequality holds on random
    families as a pure counting statement, and the
    B(10) arithmetic excludes b at most 47 given the
    stated premise. The premise itself, the target
    tail count, is not rederived in this pass, so
    the verdict will be arithmetic held, premise
    carried.
S8. The selector deletion arithmetic is exact for
    every h: 3 times (4h plus 3) exceeds 3 times
    (4h plus 1), and the deletion bound evaluates to
    2h plus three quarters, so an integer transversal
    number is at most 2h, contradicting 2h plus 1.
S9. Re-evaluation: the verdicts of rounds 1 to 3
    still pass at the current head, and nothing in
    the new emails contradicts them. The candidate
    bounds work is restated by the new emails with
    baseline 40 at most B9 at most 46, which matches
    the project record of a checked hand bound of
    40. The selector candidate of tier 2 extends the
    earlier open gap; it does not supersede any
    checked verdict, because its own entry asks for
    independent review of its case arguments.

## What the checks found

Conclusions, in the same order as the suppositions.
The checks live in
`runner/tests/test_research_loops_review.py`. Two
failures appeared during the runs, and both were in
my checker, not in the claims: the first version of
the Horn closure test let the fixed visible variables
into the witness variable set and overwrote a fixed
value during verification, and the first version of
the anytime bound test demanded the asymptotic
planning ratio at small radii where the ceiling in
the exact count still dominates. Both were fixed and
the affected sections rerun clean. I record them
because a review that hides its own tooling failures
cannot be trusted about anyone else's.

S1 held, with the tightness confirmed exactly. The
wedge identity u equal to 84 minus 7p plus S minus t
held on every graph up to six vertices (33,864
graphs) and on 8,000 random graphs on nine points,
and 3t at most S held everywhere. The wedge minimum
at p equal to 9 is exactly 9, attained by the all 2
degree sequence, and three disjoint triangles give
S equal to 9, t equal to 3, u equal to 27, and a
total of exactly 45. So the p equal to 9 layer of
the budget 44 problem sits exactly at 45: the
counting in the email is sharp there, and no
stronger exclusion at that layer can come from this
count alone. On 8,000 random nine edge graphs the
total never fell below 47; the extremal shape is
the disjoint triangles, as the argument suggests.
Verdict: the pruning rule p at least 10 at budget
44 holds, and its boundary case is tight.

S2 held. On 800 random families with forced
singletons, the three set row and the four set row
characterizations matched a direct two member union
search on every target. The pair plus triple
overlap case indeed reduces to the triple case:
with singletons forced, a selected triple inside a
four set already covers it with the missing
singleton, so the only pair only case is the
disjoint matching. Verdict: both rows are exact as
stated, and they are safe to build encodings on.

S3 held in full, in exact rational arithmetic. For
300 random finishing time distributions the
estimator's expectation equaled Z_H exactly, its
second moment equaled Pr(tau at most H) exactly,
and the truncation tail sat inside 1 over (H plus
2). The expected step sum up to horizon 2,000 is
0.644434 and still rising toward pi squared over 6
minus 1, below the stated 0.645 bound. The exact
sampler's product identity held for every t up to
59. The detection clock's hit probability equaled
Z_H exactly on 200 random distributions. The toy
calibration matched enumeration of all eight
assignments for every m from 0 to 6 and every k
from 0 to 3: mass 2 to the minus k, Z equal to the
mass over (4 plus m). One expansion of my own,
checked the same way: the variance of the estimator
is exactly Pr(tau at most H) minus Z_H squared, so
it lies in the unit interval, which is what makes
the stated Chebyshev batch size of 16 over epsilon
squared give failure probability at most a quarter
per batch. That identity is mine, not the email's,
and it is labelled as such here. Verdict: the clock
algebra, the sampler, the detection variant, and
the calibration all hold as stated, inside the
declared step convention.

S4 held. Least closure agreed with brute force
extendibility on 2,500 random Horn formulas with up
to four visible and seven hidden variables, and
where it said extendible its constructed assignment
satisfied the formula, so both refutation
obligations of the email are empty on every
instance tried: no feasible input is excluded by Q,
and L never fails where Q accepts. The bad lift
control behaved as the email predicts: dropping the
second atom of a two step Horn chain is caught by
the diagnostic search, which returns the visible
input true, the valid alternative assignment with
both atoms true, and the lift output that fails.
Verdict: the Horn positive control is exactly as
claimed, constructively.

S5 held. Minimum menu size, computed by enumerating
every hidden row and solving the cover exactly,
equaled the chromatic number, computed by an
independent coloring search, on every graph up to
five vertices (1,099 graphs) and on 120 random
sparse graphs on six and seven vertices. The
identity relation needed exactly 2 to the k rows
for k up to 4, with its trivial lift beside it, so
the pair of controls really does separate static
menu width from lift cost in both directions.
Verdict: the coloring menu identity holds on the
full small range, and the construction's clauses
are Horn as claimed.

S6 held. The claim model's five states quotient to
the three declared classes: the partition is
stable, the observation chain is (0,0), (1,1),
(2,1), and the quotient trace language equals the
concrete one, namely the empty trace, c, and c then
d. The negative control partition is unstable, and
its quotient contains the spurious trace a then c
while the concrete system does not, exactly the
failure the email says the checker must reject or
split. On 150 random transition systems, partitions
refined to stability always preserved the trace
language up to length five. That last check is my
expansion of the method into a procedure: refine
until stable, then the quotient certificate is
mechanical. Verdict: the method and both controls
hold as stated.

S7 held as scoped. The collision inequality held
on 1,500 random families as a pure counting
statement: distinct unions of at most two members
never exceeded b(b plus 1) over 2 minus (I minus n)
minus p. The B(10) arithmetic also held: at b equal
to 47 the forced triple count gives p at least 12,
and the bound evaluates to 1,022 against the needed
1,023, and the same evaluation stays at most 1,022
for every b up to 47 given the premise. The premise
is the one carried item: an earlier email's target
tail count giving I at least 2b minus n plus 20 at
n equal to 10, which this pass did not rederive.
Verdict: arithmetic held, premise carried. B(10) at
least 48 stands as a candidate whose counting is
sound and whose one external premise is named, not
as a checked result of this project yet.

S8 held as arithmetic. For every h up to 20,000,
3 times (4h plus 3) exceeds 3 times (4h plus 1), so
a vertex of triple degree at least 4 exists, and
the deletion bound 1 plus (n minus 1 plus e minus
d) over 4 at those values equals 2h plus three
quarters exactly, so an integer transversal number
under that bound is at most 2h, against the claimed
lower bound of 2h plus 1. What computation cannot
check is the two cited inputs: the transversal
bound in the form the email applies it, and the
lower bound tau(H) at least 2h plus 1 from the
landed suffix argument, together with the p equal
to 1 and p equal to 2 case analysis of the selector
entry and the stronger bracket finish of 31h plus
40. Verdict: the deletion step is exact; the
candidate totals 31h plus 15 and 31h plus 40 remain
paper candidates, now with their arithmetic spine
verified and their case analysis still awaiting a
human grade read.

## Re-evaluation of the earlier rounds

The re-run first. At the current head, the test
suites that pin the first three refutation rounds
and the finite map ran together: the fixed width
suite, the round 2 suite, the gluing suite, the
round 3 suite, and the finite map suite, 129 tests
in all, all passing. The verdicts of 23 November
stand unchanged on the code that carries them:
held.

The comparison against the new emails, claim by
claim where the two bodies of work touch:

1. Fixed width and propagation (rounds 1 and 2).
   The new emails do not revisit the fixed width
   claims, and nothing in them contradicts the
   round 1 and round 2 verdicts. The simulation
   email's OBDD normalization proposal is a new
   lane in the same territory, explicitly paper
   only, and it neither uses nor challenges the
   checked counts. Status: held, untouched.
2. The gluing lemma (round 3). The lift entry says
   the Horn closure result survives gluing when the
   glued formula remains Horn, regardless of the
   flat visible CNF size. That is consistent with
   the round 3 verdict, and narrower: round 3
   proved propagation completeness of the
   conjunction, while the lift entry claims a
   polynomial evaluator and lift for the Horn case,
   which this pass verified directly on random
   instances. Status: held, and extended in the
   Horn direction by tier 1 item 3.
3. The candidate bounds for nine and ten points.
   The new emails restate the nine point baseline
   as 40 at most B9 at most 46. That matches the
   project record: the checked hand bound of 40
   relayed on 24 November superseded the earlier
   39, and the upper bound of 46 is the standing
   construction. The pruning rule of tier 1 item 1
   is new and sharpens the search inside budget 44
   without moving either bound. The reported finite
   lower bound of 45 remains what the simulation
   email itself calls it, a replay target: not
   checked, not contradicted, still open. The ten
   point side gains the tier 1 item 6 candidate,
   B(10) at least 48, with its premise named.
   Status: the 40 bound held and unchanged; the 45
   claim still open; one new candidate added.
4. The selector gap. The earlier work left the
   leading selector total open between the landed
   bounds. The selector entry proposes 31h plus 15
   and the bracket entry proposes a stronger finish
   at 31h plus 40 in its scope. Neither supersedes
   a checked verdict, because neither side had one:
   the gap was open and stays open, now with two
   candidate totals, a verified arithmetic spine
   for the deletion step, and a named case analysis
   awaiting review. Status: open, advanced on
   paper only.
5. The squeeze and the statistics page. The
   quotient entry gives the statistics page's
   squeeze picture a finite certificate method and
   checks out on its tiny model. It does not change
   any figure or claim on that page, and it warns
   itself against reading model closure as code
   conformance. Status: new method, no earlier
   claim affected.

Nothing in the last 24 hours of email overturns a
verdict this project has banked. Two earlier open
items gained candidate answers on paper, one open
decision (budget 44 for nine points) gained a sharp
pruning rule, and one earlier restatement risk is
worth naming: the simulation email's phrase "the
reported finite at least 45 claim" could be misread
as a project result. It is not one, and this page
records it as an open replay target so the
distinction survives.

## Scope

Everything checked here is finite or is exact
algebra over a declared finite model. The pruning
rule is a statement about pair graphs on nine
points. The clock results are statements about the
declared step convention, with host side costs
outside the charged model, exactly as the email
declares. The menu results are about static menus
of constant rows; they say nothing about dynamic
policies whose candidates depend on the visible
input. Nothing on this page is a theorem about the
real machine, and the open items of tier 2 and the
budget 44 decision stay open until their own
arguments are checked.
