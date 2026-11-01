# Stage 4, first property — P2, checked

This is the record of P2's pass through stage 4's cycle: the
full statement, the model, the check, and what the check does
not say. P2 is the first of stage 4's five properties; P3 to P6
remain placeholders in `properties.md`, each to be taken up in
turn. The statement is in `properties.md` (P2, nine clauses);
the constraints it uses are C17 and C18 in `constraints.md`,
harvested from the code for this stage; the model is
`Confine.tla` in this directory.

The code read for this stage is the code at the `testing`
branch tip this stage started from, which is the code at
`6d6288c5` for every file named below.

## The property, in one paragraph

A job that passed the gate executes, and produces a result and
answers. Every quantity that bounds what that execution may
touch and what those results may disclose is computed from the
owner's configuration, from constants in the code, and from
state the runner computes itself. A job's fields enter those
computations only through narrowing rules — the effective view
is the narrower of the job's ask and the owner's ceiling, the
effective query budget the smaller of the two numbers — and
through one bounded, uniform rule: the interpreter the job
names, if it resolves outside `/usr`, has its own install
prefix bound read-only inside the sandbox so it can run. No
job field widens either ceiling, and none disables
confinement.

## Where confinement is computed — the code sites

**The sandbox decision.** `runner/runner.py`,
`_confinement_argv`, line 340. The mode comes from the
configuration alone (`sec_mode(cfg, "confinement")`, line 345,
in `runner/guard/security.py`). `enforce` with a working
mechanism builds the sandbox command; `enforce` without one
logs a warning, writes a `fallback` audit entry, and runs the
job normally; `audit` writes `would_run_sandboxed` and runs
normally; `off` returns the plain argv without looking. The
job is not an input to any of this: the function's parameters
that come from the job are the interpreter, the arguments, and
the environment it will run with — the things being confined,
not the confinement.

**The sandbox shape.** `runner/guard/sandbox.py`,
`build_bwrap_command`, line 213. The confinement block is read
from the configuration by `_confinement_cfg` (line 98) and
validated — a malformed block is a startup refusal. The fixed
flag set is the code constant `DEFAULT_FLAGS` (lines 26 to
39). The job workdir is bound read-write at the work mount
(`WORK_MOUNT`, line 23; default `/work`); no other writable
mount exists in the argv. The owner's `extra_flags` and
`extra_ro_binds` come from the same configuration block.

**The one job-influenced addition.** `interpreter_binds`,
`runner/guard/sandbox.py`, line 187, called from
`build_bwrap_command`: when the interpreter a job names
(`runner/ops/exec.py`, line 497) resolves outside `/usr` and
outside the owner's extra binds, its install prefix — parent
directory, or grandparent when the parent is `bin`, never
shallower than two components — is added as a read-only bind,
and a note naming the bind goes to the caller, which writes it
to the audit record. Finding F1 below records what this means
for the property.

**The watched set and its verdict.** `runner/ops/mail.py`,
lines 427 to 437: `workspace_root` and `protected_paths` are
read from the configuration; the before and after snapshots
come from `snapshot_outside` (`runner/ops/helpers.py`, line
13), which excludes the runner's own `base_dir` — the job's
work tree is inside it, so a job's own files never count
against it; the verdict is `confinement_violated`
(`runner/runner.py`, line 539) over the two snapshots, and
`check_protected_paths` (line 512) reports changes under the
protected paths. No job field is an input to the walk, the
set, or the verdict.

**The result-policy ceiling.** `runner/ops/policy.py`,
`apply_result_policy`, line 19: the requested view (line 33,
defaulting to `full` when absent or unrecognised, lines 41 to
42), the ceiling from the configuration (line 34), and the
narrower-of-the-two rule at line 45, over `VIEW_ORDER`
(`runner/runner.py`, line 445). `runner/runner.py`,
`query_budget`, line 553: the effective budget is the smaller
of the job's and the owner's, each defaulting to 8.
`_redact_patterns` (line 447) builds the pattern set from the
built-ins and the owner's `redact_patterns_extra`; the job's
own `redact_patterns` member is read nowhere in the runner
tree — a search for its reads, and for reads of any
confinement-shaped member (`security`, `confinement`,
`workspace_root`, `protected_paths`, `max_result_view`,
`sandbox`) out of a job, returns nothing, and the pinning test
now holds that line (stage 4's additions to
`runner/tests/test_proof_constraints.py`).

**The answers.** `runner/ops/queries.py`, `answer_queries`,
line 457: every query spends one budget unit in order,
answered or rejected. Attestations are built by
`build_attestations` (`runner/ops/attest.py`, line 16) from
values the runner supplies — the exit code, the output digest,
the confinement verdict above; a predicate the runner does not
have answers `ok: false`, reason `unknown`. The raw-line
operations are gated by `_raw_lines_allowed`
(`runner/runner.py`, line 1391) on the effective view, and
under `redacted` the lines are redacted with the owner's
patterns before they leave.

## The model

`Confine.tla` is a single-decision model, deliberately smaller
than `Gate.tla`: P2 has no check order to follow, it has two
records and a computation. The initial state picks a job
record and a configuration record from the full enumerated
sets; one step computes the outcome exactly as the code sites
above compute it; the invariants state the ceiling claims in
closed form over that outcome.

The job record carries every field the execution and result
paths read that could be shaped like a widening attempt: the
requested view (the four views, absent, or an unrecognised
string), the requested budget (absent, 0, 3, or 10 — under,
at, and over the default cap), the declared query list (every
sequence of length at most two over the four operations the
model distinguishes: the confinement attestation, an unknown
predicate, `grep`, `tail`), a redaction list present or not,
the interpreter inside or outside `/usr`, and
confinement-shaped fields present or not. The configuration
record carries the ceiling (four views), the budget cap (2 or
8), the confinement mode (three), whether the mechanism works,
and the runner-computed confinement outcome (unconfigured,
confined, violated).

The counts multiply out and match the checker's own count,
which is the cross-check that the space searched is the space
described: 4,032 job records (6 × 4 × 21 × 2 × 2 × 2) times 144
configurations (4 × 2 × 3 × 2 × 3) is 580,608 initial states,
exactly the number TLC reports computing.

## What was checked

TLC 2.19 (the `v1.7.4` tools jar) on Java 21, the same tooling
`stage2.md` and `stage3.md` record. Each run is exhaustive.
Trace output TLC writes beside the model (`*_TTrace_*`,
`states/`) is run debris and is removed, not committed.

| Configuration | File | Invariants | Result | Generated | Distinct |
|---|---|---|---|---:|---:|
| Full field space | `ConfineCeiling.cfg` | `P2Inv`, `EffViewExact`, `EffBudgetExact` | holds | 1,741,824 | 1,161,216 |
| Narrowing witness | `ConfineWitnessNarrow.cfg` | `NothingNarrows` | fails, as expected | 580,645 | 580,645 |
| Prefix witness | `ConfineWitnessPrefix.cfg` | `NoPrefixBind` | fails, as expected | 580,912 | 580,912 |

The depth of the ceiling search is 2: the initial records and
the decided outcome. The fingerprint collision estimates TLC
printed were 3.7E-8 optimistic and 9.9E-8 from the actual
fingerprints, the ordinary bound for a run of this size.

`P2Inv` is the security half: the effective view never exceeds
the ceiling, the effective budget never exceeds either side's
number, the pattern set is the owner's, the sandbox decision
and the writable set are functions of the configuration and
the machine alone, the visible set gains at most the
interpreter prefix and only for a sandboxed job whose
interpreter is outside `/usr`, and the answers are the ones
the positional rule produces. `EffViewExact` and
`EffBudgetExact` are the fidelity half: the effective values
are exactly the narrower and the smaller, not merely bounded
by them — a model (or a code path) that answered every job
with the narrowest view would satisfy the security half and
fail these, and the narrowing witness below exhibits the
firing from the other side.

To re-run from a bare machine: install a Java runtime
(Java 17 or later; `apt install openjdk-21-jre-headless` on
this distribution), fetch the TLA+ tools jar for `v1.7.4`
(`tla2tools.jar` from the tlaplus project's release of that
tag) into a tools directory, and from `docs/proofs/` run
`java -cp <tools>/tla2tools.jar tlc2.TLC -config <file>.cfg
Confine.tla` for each of the three configuration files.

## The two counterexamples that are supposed to exist

`ConfineWitnessNarrow.cfg` checks `NothingNarrows` — the claim
that a job's asks never take effect. TLC's counterexample has
ceiling `summary` and budget cap 2, and a job asking for view
`attested` with no budget of its own: the outcome is view
`attested` (narrower than the ceiling the owner set — the
job's ask is the one that ran) and budget 2 (the owner's cap
biting the default 8). The narrowing rules fire in both
directions of the min: the job can pull a value down, the
owner's ceiling can pull the job's ask down, and neither can
push one up.

`ConfineWitnessPrefix.cfg` checks `NoPrefixBind` — the claim
that the visible set never gains the interpreter's prefix.
TLC's counterexample has mode `enforce`, a working mechanism,
and a job whose interpreter is outside `/usr`: the outcome is
sandboxed, with `visibleExtra` the interpreter-prefix bind.
That is F1, exhibited rather than asserted.

## Finding

- **F1. The interpreter field changes the sandbox's visible
  set, by exactly one bounded rule.** PROTOCOL.md section 9.4
  says no job field can widen confinement, and a reader of the
  bare sentence should know the one place a job field moves
  anything: the interpreter a job names can resolve outside
  `/usr`, and the runner then binds that interpreter's own
  install prefix read-only so it can run. The code's own
  comment in `sandbox.py` calls this a widening and insists it
  be reported rather than hidden; this record does the same.
  Classification: inside the property as section 9.4 states
  it, because the ceiling is the sandbox the runner builds and
  the rule is part of that construction — uniform for every
  interpreter including the owner's default, read-only, never
  shallower than two components, never a path the job names,
  and written into the audit record. P2's statement carries
  the rule inside clause 3 rather than claiming a purity the
  code does not have. The residual exposure a stricter reading
  would press on is also recorded: a job can make the prefix
  of an interpreter that already exists on the host readable
  to itself, and the mitigations are that the interpreter must
  exist and resolve, that a key policy (C14) can pin the
  interpreters a key may name, and that every bind is audited.
  No code was changed in this pass, and the model was not
  shaped to hide the rule: it is a variable in the model, a
  clause in the statement, and a witness configuration whose
  expected failure exhibits it.

No other finding came out of the code read. In particular, no
way was found for a job field to widen the view or the budget,
add a writable path, name a mount, set or soften the
confinement verdict, replace the redaction set, or disable
confinement in any mode.

## What this does not say

- The model starts after the gate. Whether a job executes at
  all is P1; P2's claim is over jobs that execute and the
  results built from them.
- Declared query lists are modelled to length two. The code's
  rule is positional and uniform — every query spends one,
  in order — so a longer list is the same rule iterated, but
  the checked claim is stated at the modelled length, and
  raising it is a scope raise like any other.
- The attestation list a result carries under the `attested`
  view is built by the same `build_attestations` from the same
  runner-computed values, without the budget step; the model's
  budget rule models the declared-answers path
  (`answer_queries`), where the budget lives. The attested
  list cannot widen past the attested view itself, which is
  the ceiling-checked quantity, but the distinction is the
  code's and it is recorded here rather than modelled away.
- Answers are modelled as the shapes an answer can take
  (the runner's values, a raw-line answer, a rejection), not
  as output text. What the text contains is the redaction
  machinery's subject, and its patterns are pinned here as
  owner-sourced, not evaluated.
- The confinement outcome is an input the runner computes.
  The model checks what is done with the verdict — that a
  query cannot set it — not how the snapshot walk computes
  it. The walk's own fidelity is conformance-test territory
  (stage 5).
- The `enforce`-with-broken-mechanism states are in the
  space: the model's claim about them is only that no job
  field selects the fallback. At startup, a mechanism that
  cannot engage under `enforce` refuses the runner outright
  (C11); the per-job fallback the model contains is the one
  the code logs and audits. Whether `enforce` should ever
  fall back per job is a Decision 1 question, not P2's, and
  this pass does not move it.
