------------------------------ MODULE Gate ------------------------------
\* The mail-path acceptance gate, modelled step for step from the
\* check order in properties.md (P1, at commit 6d6288c5). Each
\* disjunct of Next is annotated with that order's step number.
\*
\* This model stands at the production-cap rung, P1(1048576).
\* Every message in Messages stands for a handling whose script
\* has a character count of at most 1048576, which is every
\* script the code's byte cap can admit (constraints.md C2:
\* a character is at least one UTF-8 byte). It was checked at
\* P1(49) (stage2.md) and P1(500) (stage6-rung500.md). The
\* rungs between 500 and the cap are the same searched set;
\* stage6-cap.md records why, and the re-run at this rung.
\* The character count is not a field the gate branches on, so
\* it is not a state variable: the set below is already that
\* bound. scriptOver is the code's byte cap, which can still
\* refuse a short script when the owner has set a small cap.
\*
\* Cryptography is an assumption (README.md). `signed` means an
\* HMAC-SHA-384 body verified under a secret this runner holds.
\* `innerMismatch` means an encrypted body whose inner key id is not
\* the outer one. The model does not contain a forgery step.

EXTENDS Integers

CONSTANTS AudienceMode, AllowCleartext

VARIABLES m, step, outcome, noted

vars == <<m, step, outcome, noted>>

Claim == {"free", "taken", "onRecord"}

Messages == [
  panic:             BOOLEAN,
  rawOver:           BOOLEAN,
  isFreshJob:        BOOLEAN,
  signed:            BOOLEAN,
  innerMismatch:     BOOLEAN,
  encrypted:         BOOLEAN,
  audienceOk:        BOOLEAN,
  surrogate:         BOOLEAN,
  scriptOver:        BOOLEAN,
  versionOk:         BOOLEAN,
  typeOk:            BOOLEAN,
  idOk:              BOOLEAN,
  fresh:             BOOLEAN,
  policyOk:          BOOLEAN,
  constraintDenied:  BOOLEAN,
  sensor:            BOOLEAN,
  dryRun:            BOOLEAN,
  claim:             Claim,
  cancelled:         BOOLEAN
]

Init ==
  /\ m \in Messages
  /\ step = 0
  /\ outcome = "pending"
  /\ noted = FALSE

\* A finished handling stutters, so TLC does not treat the end as
\* deadlock. The decision never changes once it is made.
Done ==
  /\ step = 99
  /\ UNCHANGED vars

Stop ==
  /\ step' = 99
  /\ outcome' = "refuse"
  /\ UNCHANGED <<m, noted>>

Pass ==
  /\ step' = step + 1
  /\ UNCHANGED <<m, outcome, noted>>

\* The clauses an execution must have satisfied. Clause 4 is vacuous
\* unless the audience feature is in enforce mode: that is the
\* weakening properties.md requires the model not to hide.
Clauses ==
  /\ ~m.panic
  /\ ~m.rawOver
  /\ m.isFreshJob
  /\ m.signed
  /\ ~m.innerMismatch
  /\ (m.encrypted \/ AllowCleartext)
  /\ (AudienceMode # "enforce" \/ m.audienceOk)
  /\ ~m.surrogate
  /\ ~m.scriptOver
  /\ m.versionOk
  /\ m.typeOk
  /\ m.idOk
  /\ m.fresh
  /\ m.policyOk
  /\ ~m.constraintDenied
  /\ ~m.sensor
  /\ ~m.dryRun
  /\ m.claim = "free"
  /\ ~m.cancelled

Next ==
  \/ Done
  \* 0. Panic before everything.
  \/ /\ step = 0
     /\ IF m.panic THEN Stop ELSE Pass
  \* 1. Raw size bound.
  \/ /\ step = 1
     /\ IF m.rawOver THEN Stop ELSE Pass
  \* 2. Early dispatch. Anything that is not a fresh job id
  \*    (cancel, query, board, version 2, bounce, no id,
  \*    answer-only, already in the seen set) does not execute.
  \/ /\ step = 2
     /\ IF ~m.isFreshJob THEN Stop ELSE Pass
  \* 3. Verification and decryption.
  \/ /\ step = 3
     /\ IF ~m.signed \/ m.innerMismatch THEN Stop ELSE Pass
  \* 4. Cleartext decision.
  \/ /\ step = 4
     /\ IF ~m.encrypted /\ ~AllowCleartext THEN Stop ELSE Pass
  \* 5. Audience. Enforce refuses. Audit records and continues.
  \*    Off does not look.
  \/ /\ step = 5
     /\ IF AudienceMode = "enforce" /\ ~m.audienceOk
        THEN Stop
        ELSE IF AudienceMode = "audit" /\ ~m.audienceOk
        THEN /\ noted' = TRUE
             /\ step' = step + 1
             /\ UNCHANGED <<m, outcome>>
        ELSE Pass
  \* 6. Encodability.
  \/ /\ step = 6
     /\ IF m.surrogate THEN Stop ELSE Pass
  \* 7. Script size bound, in bytes.
  \/ /\ step = 7
     /\ IF m.scriptOver THEN Stop ELSE Pass
  \* 8. Version, type, identity.
  \/ /\ step = 8
     /\ IF ~m.versionOk \/ ~m.typeOk \/ ~m.idOk THEN Stop ELSE Pass
  \* 9. Freshness.
  \/ /\ step = 9
     /\ IF ~m.fresh THEN Stop ELSE Pass
  \* 10. Key policy.
  \/ /\ step = 10
     /\ IF ~m.policyOk THEN Stop ELSE Pass
  \* 11. Pinned-key constraints, enforce denial.
  \/ /\ step = 11
     /\ IF m.constraintDenied THEN Stop ELSE Pass
  \* 12. Sensor branch. Through the gate, not script execution.
  \/ /\ step = 12
     /\ IF m.sensor
        THEN /\ step' = 99
             /\ outcome' = "sensor"
             /\ UNCHANGED <<m, noted>>
        ELSE Pass
  \* 13. Advisory review. It sits here and changes no decision.
  \/ /\ step = 13
     /\ Pass
  \* 14. Dry run stops here.
  \/ /\ step = 14
     /\ IF m.dryRun
        THEN /\ step' = 99
             /\ outcome' = "dry"
             /\ UNCHANGED <<m, noted>>
        ELSE Pass
  \* 15. The claim.
  \/ /\ step = 15
     /\ IF m.claim = "taken"
        THEN Stop
        ELSE IF m.claim = "onRecord"
        THEN /\ step' = 99
             /\ outcome' = "resend"
             /\ UNCHANGED <<m, noted>>
        ELSE Pass
  \* 16. A cancel recorded before arrival refuses. Otherwise the
  \*     handling executes.
  \/ /\ step = 16
     /\ IF m.cancelled
        THEN Stop
        ELSE /\ step' = 99
             /\ outcome' = "execute"
             /\ UNCHANGED <<m, noted>>

Spec == Init /\ [][Next]_vars

\* P1. Execution implies every clause. A sensor and a dry run and a
\* resend are not execution, and the invariant does not call them one.
P1Inv ==
  outcome = "execute" => Clauses

\* A sensor got there through the checks that precede its branch.
SensorInv ==
  outcome = "sensor" =>
    /\ ~m.panic /\ ~m.rawOver /\ m.isFreshJob
    /\ m.signed /\ ~m.innerMismatch
    /\ (m.encrypted \/ AllowCleartext)
    /\ (AudienceMode # "enforce" \/ m.audienceOk)
    /\ ~m.surrogate /\ ~m.scriptOver
    /\ m.versionOk /\ m.typeOk /\ m.idOk
    /\ m.fresh /\ m.policyOk /\ ~m.constraintDenied
    /\ m.sensor

\* A model that refused every message would satisfy P1Inv and
\* prove nothing. This probe is expected to fail: its counterexample
\* is one handling the gate does execute.
NothingExecutes ==
  outcome # "execute"

\* In the default and audit forms, clause 4 does not block. This
\* probe is expected to fail in those forms and to hold under
\* enforce. A failure here under enforce would be a real finding.
AudienceWasRequired ==
  outcome = "execute" => m.audienceOk

=============================================================================
