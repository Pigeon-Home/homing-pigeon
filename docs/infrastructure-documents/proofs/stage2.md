# Stage 2 — the gate, checked at P1(49)

This is the record of the first model check. The model is
`Gate.tla` and `Claim.tla` in this directory. It follows the
check order in `properties.md` step for step, at the first rung
of the family: every message stands for a handling whose script
has at most 49 characters. The character count is not a state
variable, because the gate does not branch on it. `scriptOver`
is the code's byte cap, which can still refuse a short script
when that cap is set small.

The model is not a proof that `handle_mail` does this. It is a
proof that this statement of the order, inside this bound, has
the property P1 claims. Putting each step beside the code lines
it names is stage 3. A reader who wants the claim the checker
actually searched should read the invariant `P1Inv` in
`Gate.tla`, not this prose.

## What was checked

TLC 2.19 (the `v1.7.4` tools jar) on Java 17. Each run is
exhaustive. The fingerprint collision estimates TLC printed were
on the order of `1e-7`, which is the ordinary bound for a run
of this size and not a gap that was left unsearched.

The message set is every combination of the eighteen booleans
and the three claim states in `Messages`: 786,432 initial
states. Two keys are not two names in that set. A signature
either verified under a secret this runner holds, or it did
not, and an encrypted body whose inner key id differs from its
outer one is the `innerMismatch` bit. A job the extra key's
policy forbids is `policyOk = FALSE`. Naming the keys as a
pair is a later refinement, not a difference the clauses use.

| Configuration | File | Invariants | Result | Generated | Distinct |
|---|---|---|---|---:|---:|
| Audience enforce, cleartext refused | `GateEnforce.cfg` | `P1Inv`, `SensorInv`, `AudienceWasRequired` | holds | 3,095,432 | 2,309,000 |
| Audience off, cleartext refused | `GateDefault.cfg` | `P1Inv`, `SensorInv` | holds | 3,106,576 | 2,320,144 |
| Audience audit, cleartext refused | `GateAudit.cfg` | `P1Inv`, `SensorInv` | holds | 3,106,576 | 2,320,144 |
| Two handlers, one job id | `Claim.cfg` | `AtMostOnce` | holds | 7 | 5 |

The depth of each gate search is 18, one state per step of the
order plus the finished state. The claim race is five distinct
states: both waiting, one or the other having taken the slot,
and both finished. In every finished state at most one handler
has executed.

Enforce has fewer states than the other two because a failed
audience check stops the handling at step 5, and the audit form
spends one extra state to set `noted`.

## The two counterexamples that are supposed to exist

A model that refused every message would satisfy `P1Inv` and
show nothing. Two further runs ask TLC to find a handling that
does execute. Both invariants are expected to fail, and both
did. These are not findings. The configurations that are
supposed to hold are the four in the table above.

`GateWitness.cfg` checks `NothingExecutes` under audience
enforce. TLC's counterexample ends at `outcome = "execute"` for
a message that is signed, encrypted, fresh, within both caps,
addressed to this runner, with a free claim and no cancel. That
is the strong form letting a good job through.

`GateDefaultWitness.cfg` checks `AudienceWasRequired` with the
audience feature off. TLC's counterexample ends at
`outcome = "execute"` with `audienceOk = FALSE` and every other
clause holding. That is clause 4 being vacuous in the default
form, which is what a fresh install runs. The same invariant is
checked for real under enforce, in `GateEnforce.cfg`, and there
it holds: a job for the wrong audience does not execute when
the feature is in enforce mode.

## What this does not say

P1(49) holding says nothing about P1(500) or any higher rung.
The model does not include queries, board mail, version 2 mail,
cancels, or the local-signals path, except as "not a fresh
job", which refuses them. It does not prove the cryptography it
assumes. And it has not yet been reconciled with the lines of
`handle_mail`. That reconciliation is the next stage.
