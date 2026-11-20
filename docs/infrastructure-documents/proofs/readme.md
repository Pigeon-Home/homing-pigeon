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
  `stage4-*.md`, `stage5.md`, the `stage6-*.md`,
  `stage7-5000.md`, `stage8-50000.md`, `stage9-500000.md`,
  and `stage10-1048576.md` — the checks, the state counts, the
  witnesses, and the findings, stage by stage. The
  content-independence series is recorded in `stage7.md` to
  `stage10.md`, under the titles those records landed with.
- `content-series-review.md` — the review of the
  content-independence series and the redo it asks for: every
  rung in order, both shells, the full construct set, and an
  honest statement of what each rung covers.
  `content-rung-5000.md` is the 5,000-character piece of that
  redo, the rung the earlier series skipped.
  `content-rung-49.md` is the first rung, generated.
  `content-rung-50000.md`, `content-rung-500000.md`, and
  `content-rung-cap.md` are the rungs above it. The cap
  record says the series is complete.
  `content-sh-macos.md` is the same rungs under bash 3.2.57
  in POSIX mode, which is what macOS `/bin/sh` is.
  `content-sh-freebsd.md` records FreeBSD 15.0's own
  `/bin/sh -n` on the rungs. The gate was not asked
  again. `content-sh-freebsd-design.md` is the split:
  emulate the guest, use the real shell, do not
  emulate the gate.
  `content-sh-freebsd-15-2.md` is the 15.2 harness's
  record: the same rungs, parser and execution, aimed
  at FreeBSD 15.2's `/bin/sh` only, with its first run
  recorded as a non-result -- no real FreeBSD shell
  ran it. `content-sh-freebsd-15-2-runbook.md` is the
  bare-machine procedure that produces the real run:
  nothing assumed installed, every tool installed in
  the open.
  `content-rung-verify.md` is the separate first-hand
  verification of the content redo, rung by rung, run
  after the redo landed; its closing section records
  the table complete — no row remains open, the last
  of them the 49-character row on Windows.
- The DTLS records — `dtls-over-mailbox.md` (the
  datagrams carried through the mailbox, proven end to
  end), `dtls-over-email-v3.md` (the version 3 carriage:
  what was built and tested), and
  `dtls-record-layer-and-framing.md` (the record layer
  read against RFC 9147 and the framing work; the
  mixed-version break is ratified as shipped — both
  ends must run the same side of it).
- `hybrid-fuzz-10024.md` — the directed fuzzing record
  for the X25519MLKEM768 hybrid key agreement
  (RFC 10024): suppositions, measurements, and the run
  record.
- `temp-reap.md` — the temp-reaping record: the per-job
  workspace leak, measured first-hand, and the fix.
- `shotgun-queue.md` — the shotgun test queue:
  fuzz-found bugs, newest first, and the test family
  each one gets.
- `thinking.md` — the reasoning behind the work: why the gate
  comes first, why size is a character count, the open
  content-independence challenge, the standing rules, and the
  findings and limits gathered in one place.
- `runner/tests/test_proof_constraints.py` — the unit test that
  pins the harvested constraint values against the code and
  against `constraints.md`. If a declared default changes, this
  test fails, and the inventory must be revisited before the
  model's claims can stand.
- `v4-working.md` — the working record for the v4 binding
  (the first item of `docs/FUTURE.md`): the supposition
  written before the measurement, the harvest at the current
  head, and the conclusions against it.
- `v4-properties.md` — the v4 binding index: every harvested
  constraint, C1 to C31, mapped to the numbered property that
  states it, with the new properties P7 to P13 stated in
  full. `diskguard.tla` is the first model of that work,
  of P7. The checker run for every model on this shelf
  stands recorded in `v4-working.md`, step D. `diskguard.tla`,
  `localgate.tla` and `resultfit.tla` changed after that run,
  when findings were closed, and the checker ran on them
  again, twice, as that record says.
- `v4-search.md`: the first 4 models searched without a
  checker and held to the code. `diskguard.tla`,
  `secretfloor.tla`, the model of P13, `probegate.tla`, the
  model of P10, and `localgate.tla`, the model of P12, each
  with its states counted as the prediction for the TLC run
  and its witness configurations; the real disk guard driven
  down every path its re-measuring allows, the real key map
  built over every standing of 3 keys, the real confinement
  gate asked on every start, the real local doors asked on
  every arrival at the cap, and 6 findings, all closed.
  `runner/tests/test_v4_models.py` is that search and that
  conformance, run with the suite.
- `v4-search-2.md`: the last 2 models searched the same
  way. `hybridselect.tla` (P8) and `resultfit.tla` (P11),
  each with its states counted as the prediction for the
  TLC run and its witness configurations; the real
  selection and the real fitting driven over their
  decision spaces, P9 pinned by reading the documents,
  and finding F7, closed in P11's words. The same suite
  carries these searches and this conformance too.
- `v4-general.md`: the 13 properties as instances of 1
  statement, G, and the record of the pass that states it.
  `general.tla` is the model of G: 1 runner life, every door
  at its own occasion, a world that moves between occasions,
  and 14 constants, 5 for the seams between doors and 9 for
  the doors' own guards, each with a witness configuration,
  so that every one of the 13 marks is one the checker can
  break. Findings F8 and F9 are in that record, both closed.
  `runner/tests/test_v4_general.py` is the model's search
  and its hold on the code at each seam.
- `v4-bindings.md`: the constraint spec. Every constraint,
  C1 to C31, tied in 1 table to the properties that state
  it, the code that enforces it, the tests that pin it and
  the fuzz data that has reached its code, and every
  property tied to its model, its conformance suite and its
  steps in `general.tla`. `v4-bindings.json` is the table
  itself, the registry. The page also records the sizes of
  the entries that reach each constraint, the fuzz corpus
  taken to the real doors and up the sizes to the caps, the
  constraints no fuzz data reaches, finding F10, closed, and
  finding F11, open.
  `runner/tests/test_v4_bindings.py` holds every tie and
  drives the corpus through the doors, and
  `runner/tests/test_opener_cost.py` holds F10's change.
- `v4-before-the-mac.md`: a candidate constraint, C32, and a
  candidate property, P14, for what the gate does with a
  message before its signature verifies, the place where
  findings F10 and F11 both lie. Its suppositions are
  written before the measure, and the measure and its
  conclusions follow them, with findings F12 and F13, both
  closed on the page. `premac.tla` is its model, the gate's
  6 steps as 1 decision, with 6 configurations.
  `runner/tests/test_v4_before_the_mac.py` is the measure,
  the model's search, and the real gate asked on the
  model's arrivals.
- `v4-at-a-bound.md` takes up the owner's direction of
  2026-11-19 at the first rung: a bound on the script as a
  constraint of the specification, and proof at that size.
  It counts what the first rung's 22 atoms build, which is
  74,072,330,493 scripts, gives each its result by a machine
  of 352 steps, and records the real shell asked on 858,319
  of them and the real runner asked on every step, with the
  fuzz data at 50, 500 and 5,000 bytes beside it.
  `runner/tests/test_v4_at_a_bound.py` holds it.
- `v4-at-a-limit.md` writes the same claim with the size
  left open, as a number N: why the proof holds at every N,
  what grows with N, and the bars a row meets as N grows,
  each as a number. On bash 5.2.21 the first bar is at
  13,332 characters, and the owner's rungs of 50, 500 and
  5,000 are under it. Its suppositions are written before
  the measure, and it records finding F14, closed on the
  page. `runner/tests/test_v4_at_a_limit.py` holds it.
- `v4-the-ladder.md` takes a technique of the proof from
  finding F14, by the owner's rule that a fault found in the
  proof's method is made into a technique. Sizes stand on
  the Fibonacci series from 0, and each step has 3 kinds of
  data: what the constraints decide before a run, what the
  2 steps before it forecast, and what the run shows from
  inside. Its suppositions are written before the measure.
  L1, the ratio table, was run, and it holds. L2, the
  join of M's tables, was run, and it holds: 31,460 rows,
  0 differences, and 14 kinds of row where 20 were
  supposed. The shell was not asked. L3 was run in bash
  5.2.15: 19,360 rows, the output, the status and the
  commands that ran, 0 differences. The order of a pipe's
  two sides is not claimed. J2 of finding F15 is in the
  gate: a deep address is unread and the job goes on, and a
  mail whose shape raises is marked once. No new constraint.
- `v4-the-join.md`: the sentence between the two proofs. A
  message that fails C5 never reaches the machine M, and a
  message that passes C5 reaches M only with a script of at
  most N bytes, which is C2. No new constraint. The default
  cap stays 1,048,576.
  `runner/tests/test_v4_the_join.py` holds the sentence.
- `v4-the-grammar.md`: the grammar the induction covers. A
  script of the rung is 1 of 22 atoms, or a script of the
  rung, 1 of 4 joiners, and an atom. The induction is a
  proof for that grammar, not for the shell, and not for
  every string the size door admits. No new constraint.
  `runner/tests/test_v4_the_grammar.py` holds it.
- `v4-the-folder.md`: one atom that writes, `printf x > kept`,
  and it is not one of the 22. Under C18, already defined,
  the job's folder is the only writable mount when
  confinement is enforce. A write to the host's `/tmp` does
  not land there, and the same script with confinement off
  does. Where the sandbox cannot engage, the job is refused.
  `runner/tests/test_v4_the_folder.py` holds it.
- `v4-the-place.md`: where M stands when confinement is on.
  The bound was measured with confinement off, and `pwd`
  then prints the host folder. Under enforce the folder M
  is given is the work mount, `/work`, and `HOME` is the
  `HOME` the runner passes in. All 22 atoms were run, on and
  off. The other 19 do not read the place. Every step of M,
  352 of them, was run under enforce and matches M at
  `/work`. So do 8 rows of 50 characters, 8 of 500 and 4 of
  5,000, drawn from the 22 atoms. No new atom and no new
  constraint.
  `runner/tests/test_v4_the_place.py` holds it.
- `runner/tests/test_v4_binding.py` — the unit tests pinning
  the v4 harvest's values (C28 to C31, and C3, C4, C6) against
  the code and against `v4-properties.md`.
