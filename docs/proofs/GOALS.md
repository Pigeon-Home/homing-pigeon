# Goals and staged plan

This file is the plan for the proof work: what is being built, in
what order, and what done means at each stage. It is written to be
read cold and in full — the reasoning is here, not in any
conversation — so a reviewer who has never seen this branch can
check the plan itself, not just its outputs.

The work lives on `main`. It began on a separate `testing`
branch; that branch was merged into `main` in full on
1-Nov-2026 and then closed and deleted, and the proof work
continues on `main` from there. Nothing here changes the
runner's behaviour; releases continue from `main` exactly as
before, and a stage lands only when its own definition of done
is met.

## What is being built, and why in this order

A machine-checkable formal model of Homing Pigeon's security
properties, built one property at a time, starting with the job
acceptance gate. The gate comes first because it is the load-
bearing surface: every other property — confinement, transport
gates, key pinning, replay — is a statement about jobs that have
already passed through one door, or about the door itself. A model
of any later property built before the gate's model would have to
assume the gate, and an assumed gate is the thing this work exists
to replace with a checked one.

The order inside each property is fixed: state it, model it,
check it, tie it back to the code with tests. A property that is
modelled before it is stated precisely cannot be checked — the
checker would be searching for a violation of a sentence nobody
wrote down. A model that is never tied back to the code with tests
can drift from the code while its checks stay green, which is
worse than no model, because it lends the code a claim the code
never earned.

## Decisions already made

These are settled for this work. A later stage may revisit one,
in the open, with the reason written here; none is revisited
silently.

- **Starting point: the acceptance gate, property P1.** The
  reasons are in the section above.
- **Constraints come from the code.** Every value the model uses
  is harvested from the code as it stands (`constraints.md`) and
  pinned by a test. The model never invents a tidier value. Where
  the code and an earlier account differed — the result cap's
  default, the key fingerprint's label — the code won, and the
  difference is recorded in the inventory.
- **Script size is a character count, and the first bound is
  under 50 characters.** Line counts mislead: a one-liner can be
  very long, and obfuscation packs characters onto few lines. The
  production byte caps are untouched; the character bound is the
  model's scope control. Raising it is a stage, not an edit. P1
  is therefore stated as a family over the bound, P1(B) in
  `properties.md`, and the rungs the family climbs are listed in
  stage 6. For scale: a typical script a cloud SI sends is on
  the order of 500 lines, and a large one about 1000 lines — but
  neither figure is a measure the work binds on; the character
  count is.
- **Cryptography is an assumption, not a target.** The model
  treats HMAC-SHA-384 unforgeability and the AES-256-GCM
  construction as axioms, stated in `README.md`. This work checks
  what the runner does with a verified signature; it does not
  re-prove the primitives.
- **The Oracle is out of the model's trusted base.** It advises
  and never blocks, so no property may depend on it. Modelling it
  as a gate would prove a property the system does not have.
- **Plain statements before formal ones.** Each property is first
  written in plain English precisely enough to model, as P1 is in
  `properties.md`. The formal statement must say the same thing as
  the plain one; if they diverge, the plain one is the record of
  intent and the formal one is wrong until they agree.

## Stage 1 — Foundation (this stage)

**Contents.** This directory: `README.md` (goal, honest scope,
assumptions, starting bound), `constraints.md` (the harvested
inventory, C1 to C16, each with its Decision 1 class),
`properties.md` (P1 in full with the code's real check order;
P2 to P6 as named one-line placeholders), this plan, and
`runner/tests/test_proof_constraints.py`, the pinning test.

**Done means:** the four files are on the `testing` branch; every
value in the inventory was read from the code at `6d6288c5` and
the pinning test passes against that code; and the two known
differences from earlier accounts (C3, C7) are recorded in place.

## Stage 2 — A formal model of the gate

**Contents.** A model of `handle_mail`'s gate, following the
check order in `properties.md` step for step, inside the starting
scope: the mail path, two keys, the three audience modes,
cleartext and encrypted arrivals, replayed deliveries, scripts
under 50 characters abstracted to character count, byte length,
and digest.

### The tool: candidates, and the pick

Five candidate tools were weighed for this stage:

- **TLA+ (with the TLC model checker, and Apalache for larger
  state spaces).** A language for state machines and concurrent
  behaviour: states, steps, invariants over traces. The gate is
  exactly that shape — an ordered sequence of checks, a claim
  taken under a lock, two processes racing on one job id. TLC
  exhaustively explores a finite instance and produces a concrete
  counterexample trace when an invariant fails.
- **Lean 4.** A full proof assistant: properties are theorems and
  a checked proof is the strongest artefact any of these tools
  produces. The cost is that everything, including the state
  machine the gate lives in, has to be built as definitions and
  proved by hand-guided tactics; the time to the first checked
  statement about the gate is the longest of the five.
- **Coq (Rocq).** The same proof-assistant class as Lean, with a
  longer history in protocol verification. The same cost applies,
  and the extraction story that once set it apart does not reach
  this Python codebase either.
- **Isabelle/HOL.** Again a proof assistant, strong on structured
  proofs and automation. Same class, same trade.
- **Alloy.** A relational finder: excellent for "is there a shape
  of data that breaks this rule" questions over small scopes, and
  the fastest of the five to a first counterexample. Its bounds
  are structural rather than temporal, which makes ordered,
  stateful claims — the claim under a lock, the stash before the
  send — awkward to state faithfully.

**The pick is TLA+.** The gate's property is a safety claim about
traces of a stateful, partly concurrent system: what must already
have happened before execution, and what must never happen twice.
That is the class of claim TLA+ was built to state and TLC was
built to search, and it searches exhaustively inside a finite
bound — which matches this work's shape exactly: a tiny starting
bound (scripts under 50 characters, two keys, a handful of
deliveries) checked completely beats a large bound checked
sparsely. A counterexample from TLC is a step-by-step trace that
can be laid directly beside the check order in `properties.md`
and beside the code, which is how stage 3 earns its keep. The
proof assistants are not rejected; they are deferred. If a later
stage needs a claim for all bounds rather than a checked bound —
the natural candidate is P5, replay — that stage can lift the
TLA+ model's definitions into a proof assistant with the model's
counterexample history as its guide, instead of starting cold in
the heaviest tool on day one.

**Done means:** the model exists on this branch; every step in it
is annotated with the step of the check order it models; TLC
checks P1, in both its strong (audience `enforce`) and default
forms, over the starting scope, and the checked configurations
and their state counts are recorded with the model.

This stage has landed. The model is `Gate.tla` for the ordered
checks and `Claim.tla` for the one race, at the first rung
P1(49). The configurations, the state counts, and the two
counterexamples that are supposed to exist are in `stage2.md`.
What has not landed, and is stage 3, is the line-by-line
reconciliation of those steps with `handle_mail`.

## Stage 3 — The model checked against the code's order

**Contents.** A step-by-step reconciliation: each model step
against the code lines it claims to model, and each code branch
in `handle_mail`'s gate against the model step that covers it.
Branches the model abstracts away are listed, with the reason the
abstraction is safe for P1 (the sensor branch is the worked
example: it is recorded as reached-through-the-gate and not
modelled further, because it is not script execution). Any
divergence found is resolved in one direction only for stage 3's
purposes: the model moves to the code, or the divergence is filed
as a code finding. The statement in `properties.md` does not move
to meet either of them.

**Done means:** the reconciliation table is on this branch, no
unexplained divergence remains, and every TLC counterexample
trace from stage 2 has been classified — model defect, code
defect, or assumption working as stated — with the resolution
recorded.

This stage has landed. The reconciliation is `stage3.md`:
every step of `Gate.tla` matched to the code location that
performs it, in order; the claim in `Claim.tla` matched to the
in-process half of the code's claim; six gaps (code branches
the model does not represent, each with the reason it is safe
for P1 or the later property it belongs to); and four
findings, none of them a counterexample to P1 — the
encodability check the code runs twice and the model once,
the repaired job the code can execute in place of the job it
checked, two outcomes the code defers where the model refuses,
and the audience clause's configuration precondition. Both
stage 2 witness traces are classified in `stage3.md` as
assumptions working as stated. The model was not edited and
no runner code was changed in this stage; the findings stand
as the record the later stages work from.

## Stage 4 — Each property in turn

**Contents.** P2 to P6, one at a time, each through the same
cycle P1 went through: a full statement in `properties.md` (actors,
order, counterexample shape), the constraints it needs harvested
into `constraints.md` first if they are not already there, the
model extended or a companion model built, and the check run and
recorded. The order is the order in `properties.md`: confinement
(P2), the transport gate (P3), the upgrade key's pinning (P4),
replay (P5), and Decision 1 configuration behaviour (P6). The
order runs from the gate outward — first what execution may
touch, then what stands in front of the gate, then the sharpest
single-key claim, then time, then the configuration the whole
thing boots from.

**Done means, per property:** the full statement, the checked
model, and the recorded result are on this branch. A property
that fails its check is not done; it is a finding, and the stage
stays open on it until the code or the statement is resolved in
the open.

Progress: P2 has landed. The full statement is in
`properties.md`; the constraints it needed are C17 and C18 in
`constraints.md`; the model is `Confine.tla`, checked over the
full field space (580,608 initial states) with two witness
configurations whose expected failures exhibit a narrowing
taking effect and the one bounded widening the statement names
— the read-only bind of an outside-`/usr` interpreter's own
prefix, recorded as finding F1 in `stage4-p2.md`, which is the
stage's record.

P3 has landed. The full statement is in `properties.md` —
nine clauses, stated per transport where the transports
genuinely differ: email has no sender gate and the property
claims none, file's gate is the operating system's, NATS's is
broker authentication waivable only in the open, DTLS's is the
shared secret itself in a second role, and queues' is two
bearer tokens at the hosted edge. The constraints it needed
are C19 and C20 in `constraints.md`. The model is
`TransGate.tla`, a single-decision composition model checked
over the full space (80 initial states: every transport,
signature outcome, and credential outcome, against both
deployment postures), with two witness configurations whose
expected failures exhibit a both-gates acceptance and a
signature-only acceptance on a gateless transport.
`stage4-p3.md` is the record. No bypass was found: no
transport in the code presents a job whose own credential
check failed, was bypassed, or was silently skipped. P4 to P6
remain, in the order above.

P4 has landed. The full statement is in `properties.md` —
twelve clauses: the step speaks for the key that verified,
the key directory's verdict stands in front of the policy,
the policy is the key's and not the name's, and the fences
(kinds, recipes, interpreters, timeout, and the script
pinning) refuse in every posture, while the env, file, and
argument constraints behind the step are mode-gated and are
stated as such. The constraints it needed are C21 (the key
directory's precedence) and C22 (the upgrade key
arrangement) in `constraints.md`. The model is
`KeyPolicy.tla`, a single-decision model of the policy step
checked over the full policy space (24,576 initial states:
every key, job shape, and per-field outcome against every
policy deployment), with two witness configurations whose
expected failures exhibit the pinned key's one permitted
shape being accepted under its arrangement, and the owner's
key running an ordinary job in a pinned deployment.
`stage4-p4.md` is the record. No execution outside a built
policy was found. One construction-side observation is
recorded there: the policy builder carries only the fields
it knows, so a misspelled field name in an entry is absent
from the built policy without a word — the fence enforces
the policy as built, and the gap between the written entry
and the built one is the owner's to see.

P5 has landed. The full statement is in `properties.md` —
eleven clauses over the three disk layers that carry the
guarantee: the replay cache (which turns a duplicate away),
the claim in its in-process and disk halves (with the stale
rule for a dead holder), and the recorded result (which
answers a redelivery that outlives the cache, bound to the
job's received digest). The statement is per job — id plus
digest — so a different job under a reused id runs on its
own once the cache lets the id go, and it prices three
edges: a crash between a run and its record buys one more
run, the record's expiry buys one more, and delivery is
promised only inside the stash window. The constraints it
needed are C23 (the cache's keep horizon, built to outlast
the freshness window, and its cap), C24 (the claim's stale
rule), and C25 (the record's retention and the delivery
window) in `constraints.md`. The model is `Replay.tla` —
two handlings, both digest classes, the claim taken,
deferred, released, and stolen, a crash after a run, and
both retentions expiring, each window event priced at most
once — checked exhaustively (1,792 distinct states), with
two witness configurations whose expected failures exhibit
a first execution and a duplicate answered from the record.
`stage4-p5.md` is the record. No replay path to a second
execution was found outside the priced windows; the one
observation recorded there is that the record's digest
check is skipped when the opinion module is absent, which
errs toward answering rather than executing and so does not
touch the execution claim. P6 has landed. The full statement
is in `properties.md` — seven clauses: an absent key is the
default and is not named, a present usable value is used as
written, an unusable default-class value is the documented
default and is named, an unusable refuse-class value stops
the runner at startup and the error names the setting, a
live reload of an unusable default-class value replaces the
running value and names it, and a refuse-class key is not in
the live-reload set so a later write neither changes the
binding nor stops the process. The constraints it needed are
C26 and C27 in `constraints.md`. The model is `Decision.tla`,
one decision over the twelve attempts (class, presence, and
moment), checked exhaustively (24 distinct states), with two
witness configurations whose expected failures exhibit the
startup stop and the named default. `stage4-p6.md` is the
record. No refuse-class value that is present and unusable
was found to let the runner start, and no live reload was
found to move a refuse-class binding. The one gap recorded
there is that Decision 1's sentence also asks for a log line
when a bad port is written live, and `reload_hot_config`
does not emit one, because it never reads the key. Stage 4's
five properties are checked. Stage 5 has landed; the record
is `stage5.md`.

## Stage 5 — Conformance tests tying the model to the code

**Contents.** For each checked property, a test family in
`runner/tests/` on this branch that drives the real code along
the model's paths: for P1, one test per clause and per refusal
step in the check order, at and either side of each cap, in each
audience mode, with cleartext and encrypted arrivals, and with
replayed deliveries — including the counterexample shapes listed
in `properties.md`, each of which MUST fail to execute. The
pinning test from stage 1 is the first member of this family; the
stage generalises it from values to behaviour. Model traces that
produced counterexamples during stages 2 to 4, once resolved,
become tests too: the trace is the scenario, the code is the
subject.

**Done means:** every clause of every checked property names at
least one conformance test, the family passes on this branch, and
a deliberate one-line change to a gate default or a check's order
in a scratch copy is caught by the family — that last check is
run once per property and its result recorded, because a test
family that cannot catch the change it exists to catch is
decoration.

This stage has landed. `stage5.md` names a test for every
clause of P1 through P6. The new ones, in
`runner/tests/test_proof_conformance.py`, drive `handle_mail`:
the caps at and over the bound, audience enforce and off, a
bad version, type, and job id, a stale and a future stamp, a
forbidden kind, a dry run, an id already seen, a sensor
alert, the panic word, and a good ping that does execute.
The pins from stage 1 and stage 4 cover the clauses whose
code is not the mail path. A one-line scratch-copy change
was caught for each of the six properties, and the copies
were restored. The limits are in `stage5.md`: the file,
DTLS, and queues gates are pinned at the code site rather
than by opening the far end, and delivery's "eventually"
half is not a waited-on transport.

## Stage 6 — Raising the scope, little by little

**Contents.** The bounds raise, one at a time, each raise
re-running every stage it touches:

1. The script character bound — the raising ladder for P1(B)
   in `properties.md`: under 50 characters first, then 500,
   then 5,000, then 50,000, then 500,000, then a bound of
   1048576 characters — the production cap's own number,
   `max_script_bytes` being 1048576 UTF-8 bytes (1 MiB) — where,
   as `properties.md` shows, the character-bound claim covers
   every script the code's byte cap can admit. Each rung is re-proven before the next is
   attempted. The rungs are chosen for proof convenience: each
   is roughly ten times the last, which keeps the number of
   re-proofs small while still catching a counterexample near
   the size where it first appears. They are not derived from
   the code, and they can change; a change to a rung, and the
   reason for it, is recorded here, and every rung already
   checked keeps its claim at its own bound. One further step
   remains available after the cap rung, if a later stage wants
   it: the bound dropped in favour of length as an unbounded
   integer with content fully abstracted — the point where the
   model's claim stops being about a size of script at all.
2. More keys: from two to a small map with per-key policies,
   including a pinning policy (which pulls P4's model into the
   gate's).
3. More surfaces: queries, board mail, version 2 mail, cancels,
   and the local-signals path, each joining the model through the
   same early bound they already face in the code.
4. More transports: the file and DTLS paths beside the mail path,
   which pulls P3 into the main model.

**Done means, per raise:** the raised model is checked, the
conformance family still passes, and the new bound is recorded in
`properties.md` beside the property it widens. A raise that finds
a counterexample stops the raising until the finding is resolved;
the previous bound's checked claim stands in the meantime, stated
at its own bound.

Progress: the four raises have landed.

1. The character ladder is closed at the production cap.
   P1(500) is `stage6-rung500.md`. The rungs at 5,000,
   50,000, and 500,000 characters are the same searched
   set, and P1(1048576) was re-run rather than copied:
   `stage6-cap.md`. The counts match the first rung. The
   unbounded-length step was not taken. The cap already
   covers every script the runner will accept.
2. More keys: `KeysCompose.tla`, three keys, one of them
   pinned. The record is `stage6-keys.md`. A script runs
   only when the rest of the gate passed and that key's
   policy allows the shape.
3. The other doors: `Surfaces.tla`. Cancel, query, board,
   version 2, and the local alert path run no script, and
   a job runs one only after the early bound. The record
   is `stage6-surfaces.md`.
4. File and DTLS beside the mail path: `TransGate.tla`
   already contains them. It was re-run. The record is
   `stage6-transports.md`. The limits from P3 stand.

The conformance family still passes: 85 tests. No runner
behaviour changed. The unbounded-length step remains
available and is recorded as not wanted.

## Stage 7 — Content-independence at the first rung

**Contents.** The challenge `thinking.md` records and does
not close. At scripts of at most 49 characters, list the
constructs a default bash can build, check that bash
accepts each as syntax, and present each to the real gate.
The gate's decision must be the same for every one of them.
A cap refuses by length, and the refusal must not depend
on which construct the text was.

**Done means:** the inventory is in the test, `bash -n`
accepts every script in it, `handle_mail` admits every one
and refuses every one longer than a one-byte cap for the
cap, and the record says what was not enumerated.

This stage has landed. The inventory is twenty-two
scripts. `runner/tests/test_proof_content.py` is the
harness, and `stage7.md` is the record. PowerShell is not
on the machine that ran it, so that half is not claimed.
The scripts are a sample of each construct, not every
nesting that fits in 49 characters, and not every string.

## Stage 8 — Content-independence at 50,000 characters

**Contents.** The same check as stage 7, at the ladder's
50,000-character rung. The scripts are long enough that
the inventory cannot be every construct. It is three
texts of exactly 50,000 characters that bash accepts, and
one of 50,001. The gate admits them. A short cap refuses
the three by the cap, not by the text.

**Done means:** the lengths are exact, `bash -n` accepts
them, `handle_mail` admits them, the short cap names
itself, and the record says that 50,000 is not a code
limit.

This stage has landed. The harness is
`runner/tests/test_proof_content_50k.py`. The record is
`stage8.md`. A script of 50,001 characters is still
admitted, because the code's cap is 1048576 bytes.

## What this plan does not do

- It does not change any runner behaviour. A code defect found by
  this work is filed and fixed through the ordinary route, with
  its failing test first; the fix lands wherever such fixes land,
  and this branch then re-checks its model against the fixed code.
- It does not touch PROTOCOL.md or any Internet-Draft text. If a
  checked property ever earns a place in the specification, that
  is a separate act, with the delta shown and approved on its own.
- It does not claim the whole system is proven, at any stage. Each
  stage's claim names its property, its bound, and its
  assumptions, and the sum of the claims is exactly the list of
  stages marked done — nothing more.
