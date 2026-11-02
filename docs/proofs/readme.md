# Formal proof work

This directory holds the formal proof work for Homing Pigeon. It
began on the `testing` branch, cut from release 3.15.28 at commit
`6d6288c5`; that branch was merged into `main` in full on
1-Nov-2026 and then closed and deleted, and the work lives on
`main` now. Nothing in this directory changes how the runner
behaves. The work here models the runner that already exists,
checks the model, and ties the model back to tests.

A reader who arrives cold needs nothing outside this directory and
the code it points at. Each claim in these files names the file and
function it was read from, so the claim can be checked without
taking anyone's word for it.

## The goal

The goal is a machine-checkable formal model of the protocol's
security properties: a model precise enough that a checker can
search it for a counterexample, and honest enough that the gap
between the model and the code is written down rather than assumed
away.

The model is built up little by little. One property at a time is
stated, modelled, checked, and tied back to the code with tests.
The scope then raises: a wider bound, another property, another
surface. No single step claims more than it checked.

## The honest scope statement

Today the security of Homing Pigeon rests on design choices that
are tested and reviewed, not on formal proof. The signature is
required on every job. Cleartext is refused by default. Size caps
bound a job before and after its signature is checked. Security
modes can bind a job to one runner, confine it, and pin what a key
may run. Those are strong, deliberate choices, and the test suite
exercises them heavily — but a test suite samples behaviour, and a
review is a human argument. Neither one is a proof that no path
through the gate lets a job run when it should not.

This work closes that gap property by property. Until a property
has a checked model behind it, the correct statement about it is
the one in the paragraph above: tested and reviewed, not proven.
When a property does get a checked model, the claim changes for
that property only, and only inside the model's stated assumptions
and bounds. The word "provably" is never used here without naming
the property, the bound, and the assumptions in the same breath.

## What the model assumes, and what it does not prove

A gate model cannot prove its own cryptography. The model treats
these as assumptions, stated once and carried through every
property:

- HMAC-SHA-384 is unforgeable without the shared secret. An
  attacker who does not hold a secret cannot produce a body that
  verifies under it, except with negligible probability.
- AES-256-GCM, as constructed in `runner/wire/jobcrypto.py`, keeps
  an encrypted body confidential and unmodified under a key the
  attacker does not hold.
- The shared secret itself has the entropy the startup check
  demands (see `constraints.md`), and the box that holds it is not
  already compromised.
- The operating system, the Python runtime, and the hardware do
  what their own specifications say. A job that is executed runs
  with the full trust of the runner host; confinement is a separate
  property (P2), not part of the gate.

Proving anything about those assumptions belongs to cryptography
and to other people's checked work. The model starts where they
end: given a signature that verifies, what does the runner do?

## Where the work starts: the door

The first target is the job acceptance gate — the door itself. It
is the smallest surface that carries the whole security claim: if
nothing executes without passing the gate, then every later
property has a single place to stand. If something can execute
without passing it, no later property matters.

The first property, P1 in `properties.md`, is the gate property:
no job executes unless it carries a valid HMAC signature under
the shared secret, is addressed to this runner's audience, is
within the size caps the code already declares, and is not
cleartext, cleartext being refused by default.

### The starting bound: scripts under 50 characters

The size of a script, for this proof work, is its character
count — the number of characters in the script text. Line counts
are not used: a one-liner can be very long, and packed or
obfuscated text puts many characters on few lines, so lines and
line length both mislead. Character count is the measure that
tracks how much script there actually is.

The proof starts at a tiny bound: scripts with a character count
under 50 — that is, 49 characters or fewer. At that bound a model
checker can be exhaustive about the shapes a script's length and
position can take, and the gate's decisions do not depend on
script content beyond the checks the code performs. The bound
then raises little by little, stage by stage, as `goals.md` sets
out. In `properties.md` the gate property is written as a family
over the bound, P1(B) for a bound of B characters; the first rung
is P1(49), and the last is the production cap itself.

This bound is the proof's starting scope. It is not a product
limit. The production caps in the code — a script up to 1 MiB of
UTF-8 bytes — stay exactly as they are, and `constraints.md`
records them as they stand. The model counts characters to bound
its own scope; the code caps bytes to bound a real job. Both
measures are recorded wherever either one is used, so the two are
never confused.

## How the layers grow

The work grows in layers, each one resting on the last:

1. **Constraint inventory.** Every value the gate depends on is
   harvested from the code as it stands — not invented, not taken
   from other documents. That inventory is `constraints.md`, and a
   unit test pins it, so a silent change to a declared default
   fails a test instead of quietly changing what the proof is
   about.
2. **Property statements.** Each property is stated precisely
   enough to model: the actors, the exact order the code performs
   its checks, and what a counterexample would look like. That is
   `properties.md`.
3. **Formal model.** The gate is modelled in TLA+, following the
   check order from layer 2 exactly. That model is `Gate.tla`
   (the ordered checks) and `Claim.tla` (two handlers racing the
   claim). The checker is TLC. What it found at the first rung
   is `stage2.md`. The tool choice and the rest of the plan are
   in `goals.md`.
4. **Checked model.** The checker searches the model for a
   counterexample to each stated property, inside the stated
   bound. A counterexample is a finding, not an embarrassment: it
   either exposes a real path in the code, or it exposes a place
   where the model drifted from the code, and either way the next
   step is to fix the drift or the code and check again.
5. **Conformance tests.** Each checked property gains a test
   family in `runner/tests/` that drives the real code along the
   model's paths, so the model and the code cannot drift apart
   silently afterwards.
6. **Raised scope.** The bound raises — longer scripts, then more
   keys, more transports, more message kinds — and the cycle
   repeats. The roof raises little by little, and each raise is a
   new checked claim, not a bigger adjective on an old one.

## How to review this

This work is written to be reviewed cold, by a reader who has
nothing but this directory and the code it points at. No context
outside these files is needed, and none should be assumed: if a
claim here cannot be checked from what is written here plus the
code at `6d6288c5`, that gap is itself a review finding.

The feedback wanted, in order:

- **Are the properties the right ones?** P1 through P6 are
  stated in full in `properties.md`.
  Is the gate the right first property? Is anything the gate's
  claim silently depends on missing from the list — a property
  that ought to be stated, in this order or at all?
- **Is the check order stated as the code performs it?**
  `properties.md` records the order step by step from
  `runner/ops/mail.py`, `handle_mail`, and the helpers it calls.
  A step that is out of order, missing, or not in the code — or
  a branch in the code that no step covers — is a finding
  against the statement, and it matters: an order stated wrong
  here becomes a model built wrong in the next stage.
- **Are any assumptions missing?** The assumptions the model
  rests on are listed above, in "What the model assumes". If a
  claim in these files leans on something not listed there —
  about the runtime, a transport, the clock, the filesystem —
  name it. An unstated assumption found in review is far cheaper
  than one found by a counterexample later.
- **Does any constraint value disagree with the code?** Every
  value in `constraints.md` names the file and function it was
  read from. A value that does not match the code at `6d6288c5`
  is a finding against the inventory, and the inventory — not
  the code — is what gets corrected, unless the code itself is
  the defect, in which case saying so, with the lines, is the
  most useful review there is.

A finding is most useful when it points at the file and the line
— in these documents or in the code — that it is about.

## The files

- `constraints.md` — the constraint inventory harvested from the
  code — begun at `6d6288c5` and extended as later stages
  harvested theirs — with the exact value, the declaring file and
  function, and the refuse-or-default class of each constraint.
- `properties.md` — the property list. P1 through P6 are
  stated in full.
- `goals.md` — the staged plan: this foundation first, then the
  model, then each property, then the conformance tests, with the
  scope raising between stages.
- The stage records — `stage2.md`, `stage3.md`, the
  `stage4-*.md`, `stage5.md`, the `stage6-*.md`, and
  `stage7-5000.md` — the checks, the state counts, the
  witnesses, and the findings, stage by stage. The
  content-independence series is recorded in `stage7.md` to
  `stage10.md`, under the titles those records landed with.
- `content-series-review.md` — the review of the
  content-independence series and the redo it asks for: every
  rung in order, both shells, the full construct set, and an
  honest statement of what each rung covers.
- `thinking.md` — the reasoning behind the work: why the gate
  comes first, why size is a character count, the open
  content-independence challenge, the standing rules, and the
  findings and limits gathered in one place.
- `runner/tests/test_proof_constraints.py` — the unit test that
  pins the harvested constraint values against the code and
  against `constraints.md`. If a declared default changes, this
  test fails, and the inventory must be revisited before the
  model's claims can stand.
