# Stage 6 — the ladder, closed at the production cap

P1(500) is `stage6-rung500.md`. This record is the rest of
item 1: the rungs at 5,000, 50,000, and 500,000 characters,
and the last rung, P1(1048576).

## Why the remaining rungs are one check

`stage6-rung500.md` already says the part that matters. The
character count is not a state variable. `Init` admits the
same cross product at every bound, and no step of `Next`
branches on a script's length or its text. The graph TLC
walks at 49, at 500, and at the cap is one graph. What a
rung changes is the set of real handlings that graph stands
for.

A content check that appeared only after some length
between 500 and the cap would make the rungs different
machines. The check order has no such step. Stage 3 matched
every gate step to the code, and the only length the code
measures is the UTF-8 byte cap, which is the boolean
`scriptOver` and is already both true and false in the
searched set.

So P1(5000), P1(50000), and P1(500000) are not four new
proofs. Copying the table four times and calling each a
re-proof would pretend a difference the model does not
have. They are recorded here as the same checked claim.
The one that was re-run, rather than copied from the 500
record, is the top of the ladder.

## The re-run at the cap

`Gate.tla` now states the bound as 1048576 characters.
That number is the production cap's own number. The code's
cap is 1048576 UTF-8 bytes (C2). A character is at least
one byte, so every script the runner can accept has a
character count of at most 1048576. P1(1048576) covers
every script that can pass the code's own cap. The two
measures stay different measures: characters in the model,
bytes in the code.

TLC 2.19 on Java 17, each run exhaustive. The counts match
the 500 rung and the 49 rung.

| Configuration | Invariants | Result | Generated | Distinct |
|---|---|---|---:|---:|
| Audience enforce | `P1Inv`, `SensorInv`, `AudienceWasRequired` | holds | 3,095,432 | 2,309,000 |
| Audience off | `P1Inv`, `SensorInv` | holds | 3,106,576 | 2,320,144 |
| Audience audit | `P1Inv`, `SensorInv` | holds | 3,106,576 | 2,320,144 |
| Claim race | `AtMostOnce` | holds | 7 | 5 |
| Witness, enforce | `NothingExecutes` | fails, as expected | 3,095,425 | 2,308,999 |
| Witness, audience off | `AudienceWasRequired` | fails, as expected | 3,106,561 | 2,320,141 |

The witnesses are the same two shapes as at the first rung.
A good job still executes. With the audience feature off,
a job still executes without the audience clause. The
strong form still requires it.

## The step that was not taken

One further step is available: drop the bound and treat
length as an unbounded integer, with the script's content
abstracted away. It was not taken. The cap rung already
covers every script the runner will accept. An unbounded
length would be a claim about scripts the byte cap
refuses. That is a wider claim than the code, and this
stage does not make it.

## The conformance family

After this raise, `test_proof_constraints.py` and
`test_proof_conformance.py` together run 85 tests, all
passing. The raise changed a comment in `Gate.tla` and the
bound it declares. It changed no runner behaviour.

## Verification

This record was re-checked first-hand after it landed, the
same standard stage 3 applied to stage 2: nothing in the
record above was taken on the author's word.

- **The check was re-run.** TLC 2.19 (the `v1.7.4` tools
  jar), on Java 21 rather than the record's 17 — the
  rung-500 record established that the counts do not move
  with the Java version, and none did. Every number in the
  table above reproduced exactly: enforce holds at
  3,095,432 generated, 2,309,000 distinct; off holds at
  3,106,576 / 2,320,144; audit holds at
  3,106,576 / 2,320,144; the claim race holds at 7 / 5;
  the two witnesses fail at 3,095,425 / 2,308,999 and
  3,106,561 / 2,320,141. Each gate run starts from 786,432
  initial states.
- **The code was re-read.** `handle_mail`
  (`runner/ops/mail.py`) still performs the check order
  `Gate.tla` annotates, step for step, and the only length
  it measures is the one at its step 7:
  `len(script.encode("utf-8"))` against
  `max_script_bytes`, default 1048576 (constraint C2). No
  step branches on a script's character count or on its
  text. The argument this record rests on — the rungs are
  one searched set because no length-dependent check
  appears anywhere in the order — is the code's shape on
  current main, not only at the record's commit.
- **The tests.** The two files named above now run 131
  tests (67 constraints, 64 conformance), all passing.
  The 85 in the record was the family's size on the tree
  the record was written on; the conformance file grew
  when stage 5 landed in full after this record. Not a
  correction: a point-in-time count, since overtaken, with
  the claim it supported — the family passes — unchanged.
