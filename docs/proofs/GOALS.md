# Goals and staged plan

This file is the plan for the proof work: what is being built, in
what order, and what done means at each stage. It is written to be
read cold and in full — the reasoning is here, not in any
conversation — so a reviewer who has never seen this branch can
check the plan itself, not just its outputs.

The work lives on the `testing` branch. Nothing here changes the
runner's behaviour; releases continue from `main` exactly as
before, and a stage lands here only when its own definition of
done is met.

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
