# The thinking behind the proof work

This file holds the reasoning around the proof work: why it is
shaped the way it is, which challenges are still open, and which
rules the work runs under. The records themselves — the
constraint inventory, the property statements, the stage
results — live in the other files in this directory, and this
file links to them rather than repeating them. What belongs
here is the thinking that would otherwise live only in
conversation: the arguments for the shape, the doubts that are
still standing, and the questions nobody has answered yet.

## Why the gate is the first property

Every other property is a statement about jobs that have
already passed through one door, or about the door itself.
Confinement is a claim about an execution; a transport gate is
a claim about what stands in front of the door; key pinning is
a claim about one key at the door; replay is a claim about the
door remembering. A model of any of those, built before the
gate's own model, would have to assume the gate — and an
assumed gate is exactly what this work exists to replace with a
checked one. So the gate comes first, and the order after it
runs outward: what execution may touch, what stands in front
of the gate, the sharpest single-key claim, time, and then the
configuration the whole thing boots from.

## Why a checked model, and not a bigger test suite

A test suite samples behaviour. It runs the jobs someone
thought of, along the paths someone expected, and reports that
nothing went wrong on those runs. That is worth a great deal —
the suite here is large and adversarial — but it cannot say
that no path exists. A model checker, inside a stated bound,
does something different: it explores every state the model can
reach and searches for one that breaks the property. Inside the
bound, the claim is not "nothing went wrong on the runs tried"
but "there is no run, in this space, on which it goes wrong."

The price of that strength is the bound, and the price is paid
in the open: every claim in this work names its property, its
bound, and its assumptions in the same breath, and a claim at
one bound says nothing about any larger one. The conformance
tests in stage 5 exist to keep the two honest against each
other — the model cannot drift from the code while its checks
stay green, because tests drive the real code along the model's
paths.

## Why script size is a character count

The size of a script, for this work, is the number of
characters in its text. Line counts mislead twice over. A
one-liner can be very long — a whole program on a single line
is ordinary, not exotic — and packed or obfuscated text puts
many characters on few lines precisely so that a line count
understates how much script there is. Length of the longest
line misleads the other way. The character count is the one
measure that tracks how much script actually arrived, whatever
shape it arrived in.

For scale: a typical script sent by a cloud SI is on the order
of 500 lines, and a large one about 1000 lines. Neither figure
is a bound this work uses. Lines are how a human reads a
script; characters are what the gate receives. The production
byte caps in the code are untouched by any of this — the
character bound is the model's scope control, not a product
limit, and `constraints.md` records both measures wherever
either is used so the two are never confused.

## The content-independence challenge

The gate model abstracts a script to three things: its
character count, its UTF-8 byte length, and its digest. The
argument for the abstraction is that the gate's decisions never
depend on script content — the check order in `properties.md`
reads the signature, the audience, the sizes, the key's policy;
nowhere does a check branch on what the script says. Stage 3
walked that order against the code line by line and found the
argument holds in the code as written.

The challenge to that abstraction is standing, and it is
recorded here in full rather than smoothed over: an abstraction
argued from a code read is still an argument. Belief of a
stronger kind would come from generating every script a real
shell can actually construct at the bound — from the atomic
operations of bash as a default system build installs it, and
PowerShell likewise — and running those scripts against the
real gate. Not every string: every constructible script.

That enumeration looks like this. A default bash offers a small
grammar: its builtins, the operators that join commands, the
expansions (parameter, command, arithmetic, pathname), the
redirections, quoting in its several forms, command and process
substitution, and the control shapes — conditionals, loops,
functions, grouping. At a bound of 50 characters, the scripts
that grammar can build are finite and tractable: each construct
costs characters, the count caps how many can combine, and the
inventory of atoms is the shell's own, which is small and
listable. The space of all strings at 50 characters is
astronomical and mostly meaningless; the space of constructible
scripts is the grammar, and the grammar is the tractable part.

What the enumeration would prove, that the model does not, is
content-independence demonstrated rather than assumed: every
script the shell can build at the bound, presented to the real
gate, refused or admitted exactly as the model's content-blind
account predicts. It would also exercise what the model
abstracts away entirely — the script as the shell parses it,
not as the gate measures it. The cost is real but bounded at
the first rung: an inventory of the default build's constructs,
a generator over that inventory under the character bound, and
a harness that presents the results to the real gate and
compares outcomes. The cost rises with the bound, which is one
more reason the ladder climbs in steps.

The standing position is recorded honestly. The enumeration is
not a known hole: the check order is content-independent in the
code as read, step by step, in stage 3, and nothing in the
records suggests a content-dependent branch exists. It is a
challenge to verify empirically what is currently verified by
reading — a candidate addition to stage 5, whose whole job is
tying the model to the real code, or a stage of its own. It is
written down so that it gets taken up deliberately, with its
scope chosen, rather than by drift.

It has since been taken up, as its own series alongside the
ladder: the content-independence checks recorded in
`goals.md`, presenting construct-built scripts to the real
gate at the first rung, at 50,000 and 500,000 characters,
and at the production cap. The records are `stage7.md` to
`stage10.md`, under the titles they landed with. Two
limits stood in those records: the scripts were samples
of each construct, not the closure of every nesting, and
the PowerShell half was not run. A first-hand verification
pass over that series ran, and its verdicts stand as
appendices to the four records. That series has since
been redone in full — both shells, every rung, the
5,000-character rung the first series skipped included —
and the redo verified first-hand. The final position is
stated in the next section, and it supersedes the limits
above: the closure is still not enumerated at any bound,
and that is the one limit that stands.

### The final position

This challenge is now closed, and its end state is stated
here in full. The series described above was redone —
both shells, every rung — and the redo was verified
first-hand, every count, length, and gate outcome in its
records reproduced. The records are `content-rung-49.md`,
`content-rung-5000.md`, `content-rung-50000.md`,
`content-rung-500000.md`, and `content-rung-cap.md`.

What carries the proof is the model argument. The gate's
check order reads the signature, the audience, the sizes,
and the key's policy, and no step in it branches on what
a script says. Stage 3 walked that order against the code
line by line, and the model checks hold at every bound on
the ladder up to the production cap. Content-independence
is proven there — by the shape of the code, checked — and
that is where the claim rests.

What the content series adds is demonstration, and its
shape is now exact. At the first rung, 49 characters, the
set is not a sample: it is every combination of the atom
list at the stated depth — every atom kept, every pair
joined by the shell's operators, every triple of the
short atoms — 3,682 bash scripts and 511 PowerShell
scripts, each presented to the real gate and admitted,
the gate's answer never varying with the constructs
inside. (PowerShell's parser rejected 10 of its 521
candidates before the gate saw them; those were excluded,
not refused.) At the higher rungs — 5,000, 50,000, and
500,000 characters — the sets are composed samples, broad
and catalog-cycled, and their records name them as
samples. At the production cap, scripts of exactly
1,048,576 bytes were admitted in both shells and scripts
of 1,048,577 bytes were refused, the refusal naming
`max_script_bytes`.

What remains unproven is the challenge in its widest
form. No rung enumerates the full closure: nesting deeper
than the first rung's stated depth, and combinations
beyond the higher rungs' catalog, were not generated, at
any bound. The scripts were syntax-checked by the real
shells and presented to the real gate, but they were not
executed, so nothing here speaks to what a script does —
only to whether the gate's answer depends on its content,
which is the question the challenge asked.

So the position is this: content-independence is
established by the model argument and the code walk, and
it is demonstrated empirically over an exhaustive
fragment at the smallest rung and over broad samples at
every rung above it, in both shells. It is not
demonstrated by total enumeration, and no record in this
work claims that it is.

## The boundary question

Is there a size at which the answer becomes no? What is known
is structural. Each rung is a separate claim, re-proven at its
own bound; a counterexample found at a higher rung would not
disturb the checked claims below it, which stand stated at
their own bounds until the finding is resolved. Above the
code's own caps — a job of 4 MiB, a script of 1 MiB — the
runner refuses the job before the question of its content
arises, so the family's last rung is the cap itself: at that
bound, as `properties.md` shows, the character claim covers
every script the byte cap can admit, and there is no rung
above it to fail.

The genuinely open part is the middle. Nobody knows in advance
whether some rung on the ladder produces a counterexample. The
ladder's steps are each roughly ten times the last for exactly
that reason: few enough re-proofs to be practical, close
enough together that if a counterexample exists, it appears
near the size where it first matters, not megabytes past it.

## The standing rules of this work

These are the rules the work runs under, stated as its
own, in force until one is revisited in the open with its
reason written down.

- **Rung raises need no separate approval.** The ladder in
  `goals.md` is itself the standing decision; a raise is
  executed and reported with its counts, and a counterexample
  at any rung stops the climb until the finding is resolved.
- **Constraints come from the code, and the code wins.** Every
  value the model uses is harvested from the code as it stands
  and pinned by a test. Where an earlier account and the code
  disagree, the inventory records the code's value and the
  difference.
- **Everything is verified first-hand before it is relied on.**
  Whoever drafted an artifact in this work, its
  claims rest only on what has been re-run and re-read: every
  checker count reproduced, every model clause walked against
  the code it claims to model. The standard the work is held to
  is a defence, end to end, under questioning — so nothing here
  rests on another pass's word, including this file's links,
  which point at records that were each verified the same way.
- **Outside review is advisory.** Review from outside this work
  is read on its merits and incorporated when it is good; it
  does not reorder the stages or substitute for the work's
  own verification pass, which decides what the work claims.

## Compute: use the processors that exist

A model check is compute, and the fleet has compute standing
idle. The configurations of a single property are independent
of one another — the gate's three audience modes, the witness
configurations, the claim model — so they run in parallel
rather than in sequence, as many at once as the machine has
genuinely free. The same applies across properties when stages
overlap.

The honest picture of the fleet: the Germany rig runs its
fuzzing at about half of its 8 cores; San Francisco is kept and
sits idle, its fuzzing stopped; this VM's cores are shared with
the fuzzing grow that runs on it, and they are the constrained
ones — memory here runs close to its floor as well. Today's
checks run where the TLC tooling already is, which is this VM,
and they are sized to what is actually free rather than what
would be convenient. The natural shape, noted as a direction
rather than a claim: the runner itself is the delivery
mechanism this project already trusts, so spreading check work
across the fleet as signed jobs — each rig checking the
configurations it has room for, banking its results the way the
corpus banks — is how this scales when a stage needs more than
one machine. That direction is recorded here; it is not yet
built, and no current claim depends on it.

## Findings and honest limits, gathered

The stage records carry each of these in full; they are
gathered here so the work's whole debt is visible in one
place.

- **The repaired job (stage 3, F2).** The code can execute a
  job the Oracle repaired — a platform interpreter substituted
  after the job was checked — instead of the job byte-for-byte
  as checked. The repaired shape is re-run through the judge
  and the key policy before it executes, so the one clause the
  substitution can touch is re-checked. Stage 5's
  conformance family pins exactly this on the real path
  (`stage5.md`), and the stage's first-hand verification
  confirmed that debt closed.
- **The interpreter-prefix bind (stage 4, P2, F1).** A job's
  interpreter field does change the sandbox's shape: an
  interpreter outside `/usr` gets its own install prefix bound
  read-only so it can run at all. The bind is never shallower
  than two path components, names no job-supplied path, applies
  to the owner's own default interpreter the same way, and is
  written into the audit record. Bounded and disclosed — and
  named a widening in plain words, because it is one.
- **The silent field drop (stage 4, P4, F1).** The key-policy
  builder carries only the fields it recognizes, so a
  misspelled field name in a policy entry — above all the
  pinning field — was absent from the built policy without a
  word. Enforcement is exact for the policy as built; the gap
  was between the entry as written and the policy as built, and
  it sat on the construction side of the fence. Disposition:
  fixed on main — the builder now names every field it does
  not recognise, naming the key and the field. The record is
  in `stage4-p4.md`.
- **The reload naming gap (stage 4, P6, F1).** A bad
  refuse-class value written while the runner was running was
  never named: the reload path never read those keys, so the
  binding was kept and nothing stopped — but no log line said
  the value was bad, where the design rule asks for one.
  Disposition: fixed on main — the reload path now reads the
  refuse-class values for naming only, names a bad one in the
  log at the moment of the write, and still does not apply it
  until the next start. The record is in `stage4-p6.md`.
- **The boolean that becomes 1 (P6 verification, F2).** A
  boolean written live for a hot key was accepted as the number
  1 by the reload path, instead of falling back to its
  documented default and being named, the way the same value
  is treated at startup. Proven by running the function; the
  record is in `stage4-p6.md`. Disposition: fixed on main —
  the reload reader now rejects a boolean outright, so the
  value reads as the documented default and is named.
- **The prefix floor on the parent fallback (stage 5, F1).**
  The two-component floor on the interpreter-prefix bind was
  not enforced on `_install_prefix`'s parent fallback, so an
  interpreter in the root or a top-level directory bound the
  whole tree. Disposition: fixed on main, test first — the
  fallback now enforces the same floor, and such an
  interpreter gets no prefix bind. The record is in
  `stage5.md`. The bind rule itself (P2 F1 above) is the one
  finding accepted rather than fixed, carried as a named
  limit in `docs/security/model-and-proof-testing.md`.
- **The priced replay windows (P5).** At-most-once execution
  holds outside two windows the statement prices in the open:
  a crash between a run and its result being recorded buys at
  most one further run, and the recorded result ageing out
  after seven days does the same.
- **The one assumption.** Everything rests on this: a valid
  signature cannot be forged without the secret. The model
  starts where the cryptography ends, and `readme.md` states
  the full set of assumptions the work carries.

## Where things stand, and what is next

Stages 1 to 4 have landed and been verified first-hand: the
foundation, the gate model at the first rung, the line-by-line
reconciliation, and the five properties P2 to P6, each with its
checked model and its record. The summary document at
`docs/security/model-and-proof-testing.md` describes the model
and the testing for a general reader and points back here.

Stage 5 has landed: a conformance test named for every clause
of P1 to P6, the per-property mutation checks, and a
first-hand verification appendix that re-walked every clause
against `properties.md` and re-ran the family end to end —
248 tests, all passing (`stage5.md`).

Stage 6 has landed: the character ladder closed at the
production cap, and the model widened to the key map, the
other doors, and the transports beside the mail path. The
unbounded-length step remains available and is recorded as
not wanted.

The ladder stages after 6 are named one rung at a time.
Stage 7 has landed: P1 re-checked at the 5,000-character
bound by a run at that bound, its record `stage7-5000.md`,
its counts matching the earlier rungs exactly. Stages 8
(50,000 characters), 9 (500,000), and 10 (the production
cap, 1048576 characters) have landed the same way, each
by a run on a scratch copy at its own bound. The records
are `stage8-50000.md`, `stage9-500000.md`, and
`stage10-1048576.md`. The counts match the earlier rungs.
The same-searched-set argument still explains why. The
runs are what the stages asked for.

The content-independence challenge above has been taken up
as its own series, alongside the ladder, and then redone
in full. The first series presented construct-built scripts
to the real gate at the first rung, at 50,000 and 500,000
characters, and at the production cap; its records are
`stage7.md` to `stage10.md`, under the titles they landed
with, and a first-hand verification pass over it ran, its
verdicts standing as appendices to the four records. The
redo supersedes it: both shells at every rung — the first
rung, 5,000, 50,000, and 500,000 characters, and the
production cap — verified first-hand, with the records in
`content-rung-49.md`, `content-rung-5000.md`,
`content-rung-50000.md`, `content-rung-500000.md`, and
`content-rung-cap.md`. The final position is stated in
full under the challenge above: an exhaustive fragment at
the first rung, broad composed samples at every rung
above it, no full closure enumerated at any bound, and
the scripts presented to the gate, not executed.

What is next: nothing in the staged plan. Every stage in
`goals.md` has landed, every finding has its stated end,
and the final consistency pass has run the full proof
test family on the final tree: 319 tests, none failing —
311 passed outright, and the 8 skipped are the FreeBSD
and macOS shell checks, whose shells are not on the
machine that ran the pass, each with its registered
reason (the 5 PowerShell tests that first skipped for
the same kind of reason were re-run with PowerShell
7.5.4 on the path, and passed). Every widening from
here still goes through the same cycle — state it, model
it, check it, tie it back to the code — and every claim
still names its property, its bound, and its assumptions.
Nothing in this work claims the whole system is proven,
at any stage, and the sum of the claims is exactly the
list of stages and checks marked done — nothing more.
