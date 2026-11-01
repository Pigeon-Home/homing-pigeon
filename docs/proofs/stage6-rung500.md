# Stage 6 — the first raise: P1 at 500 characters

This is the record of the first raise of the script character
bound: P1 re-proven at the second rung, P1(500) — the nine
clauses of `properties.md` for every handling whose script has
at most 500 characters. The first rung, P1(49), is `stage2.md`;
its checked claim stands at its own bound and is not restated
here.

## How the bound is set, and how it was raised

The bound is not a configuration constant and not a state
variable. `Gate.tla` declares it in its header: every message in
`Messages` stands for a handling whose script has at most B
characters, and the set is already that bound, because the gate
never branches on a script's character count. The only length
the code's gate measures is the script's UTF-8 byte length
(step 7 of the check order, constraint C2), and that is in the
model as the boolean `scriptOver`, ranging over both values at
every rung: a short script is over the cap when the owner has
set a small one, and a 500-character script is under the
default 1 MiB cap, so both directions were already in the
searched set at the first rung.

Raising the bound is therefore a change to the model's declared
interpretation, and to nothing else. The header of `Gate.tla`
now states the second rung, and the comment in
`GateEnforce.cfg` names it. No action, invariant, or message
field changed. `Claim.tla` is unchanged; it was re-run as it
stands.

What the raise changes is the claim, not the search. `Init`
admits the full cross product of the eighteen booleans and the
three claim states at both rungs, and no step of `Next`
branches on anything else, so the graph TLC explores at 500 is
the graph it explored at 49. What widens is the set of real
handlings that graph stands for: at 49 it stood for handlings
with scripts of at most 49 characters; it now stands for
handlings with scripts of at most 500. `P1Inv` holding over the
searched set is, at this rung, P1(500).

That argument is the substance of this rung, and it is stated
plainly so it can be attacked: it rests on the gate's decisions
depending on a script only through the features in `Messages`.
Stage 3 reconciled those features against the code step for
step. A gate input that appears only when scripts grow past
some length between 50 and 500 characters — a check on content,
not on bytes or digest — would break the argument, and none is
in the check order.

## What was checked

TLC 2.19 (the `v1.7.4` tools jar), each run exhaustive. This
pass ran on Java 21; stage 2's runs were on Java 17. Before the
raise, the unmodified model was re-run with this toolchain and
reproduced stage 2's counts exactly on every configuration, so
the comparison below is against a live re-run, not only against
the written record. The fingerprint collision estimates TLC
printed were on the order of `1e-7`, as at the first rung.

| Configuration | Invariants | Result at 500 | Generated | Distinct | At 49 |
|---|---|---|---:|---:|---|
| Audience enforce (`GateEnforce.cfg`) | `P1Inv`, `SensorInv`, `AudienceWasRequired` | holds | 3,095,432 | 2,309,000 | 3,095,432 / 2,309,000 |
| Audience off (`GateDefault.cfg`) | `P1Inv`, `SensorInv` | holds | 3,106,576 | 2,320,144 | 3,106,576 / 2,320,144 |
| Audience audit (`GateAudit.cfg`) | `P1Inv`, `SensorInv` | holds | 3,106,576 | 2,320,144 | 3,106,576 / 2,320,144 |
| Claim race (`Claim.cfg`) | `AtMostOnce` | holds | 7 | 5 | 7 / 5 |

Every run starts from 786,432 initial states, and the depth of
each gate search is 18, as at the first rung. The counts are
identical at the two rungs for the reason given above: the
searched set did not change. The claim that changed is the one
the set stands for.

## The two counterexamples that are supposed to exist

Both witness configurations were re-run at this rung, and both
behave as they did at the first.

`GateWitness.cfg` (`NothingExecutes`, audience enforce) fails
with a counterexample ending at `outcome = "execute"` for a
message that is signed, encrypted, fresh, within both caps,
addressed to this runner, with a free claim and no cancel —
3,095,425 generated, 2,308,999 distinct, the same as at 49.
The strong form still lets a good job through.

`GateDefaultWitness.cfg` (`AudienceWasRequired`, audience off)
fails with a counterexample ending at `outcome = "execute"` with
`audienceOk = FALSE` and every other clause holding —
3,106,561 generated, 2,320,141 distinct, the same as at 49.
Clause 4 is still vacuous in the default form, and still checked
for real under enforce, where it holds.

## The conformance family after the raise

Stage 6's done means the conformance family still passes. After
the raise, on this branch: `runner/tests/test_proof_constraints.py`
runs 67 tests, all passing, and
`runner/tests/test_proof_conformance.py` runs 4 tests, all
passing. Stage 5 is still open — the rest of that family and the
mutation check are stage 5's own record to close — but nothing
the raise touched disturbed the part of the family that exists.

## What this does not say

P1(500) holding says nothing about P1(5000) or any higher rung;
each is re-proven when its turn comes, in the ladder's order.
The model's scope is otherwise the first rung's scope: the mail
path, the surfaces named in stage 2, and the cryptography
assumed, not proven, as `README.md` states.
