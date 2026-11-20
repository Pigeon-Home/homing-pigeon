------------------------------ MODULE Gate ------------------------------
\* The mail-path acceptance gate, modelled step for step from the
\* check order in properties.md (P1). Each disjunct of Next is
\* annotated with that order's step number.
\*
\* Steps 4 to 8 are the stretch between the signature and
\* freshness. BindFirst is the order that stands: version, type
\* and identity are checked first behind the signature (C13 with
\* its place, finding F16, v4-behind-the-mac.md). Set to FALSE it
\* is the order the code performed until 2026-11-19, with that
\* check last of the 5, and the 2 invariants at the foot of this
\* file break, as they must.
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
\* Cryptography is an assumption (readme.md). `signed` means an
\* HMAC-SHA-384 body verified under a secret this runner holds.
\* `innerMismatch` means an encrypted body whose inner key id is not
\* the outer one. The model does not contain a forgery step.

EXTENDS Integers, Sequences

CONSTANTS AudienceMode, AllowCleartext, BindFirst

\* named: a record names the job (the line for a body in clear
\* text, or the security audit's entry for a wrong audience).
\* read: the gate has acted on a member of the body other than
\* its version, its type and its id.
VARIABLES m, step, outcome, noted, named, read

vars == <<m, step, outcome, noted, named, read>>

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
  /\ named = FALSE
  /\ read = FALSE

\* A finished handling stutters, so TLC does not treat the end as
\* deadlock. The decision never changes once it is made.
Done ==
  /\ step = 99
  /\ UNCHANGED vars

Stop ==
  /\ step' = 99
  /\ outcome' = "refuse"
  /\ UNCHANGED <<m, noted, named, read>>

Pass ==
  /\ step' = step + 1
  /\ UNCHANGED <<m, outcome, noted, named, read>>

\* The 5 checks of the stretch, in the order BindFirst gives.
Stretch ==
  IF BindFirst
  THEN <<"identity", "cleartext", "audience", "encodable", "script">>
  ELSE <<"cleartext", "audience", "encodable", "script", "identity">>

\* Version, type, identity (C13).
Identity ==
  IF ~m.versionOk \/ ~m.typeOk \/ ~m.idOk THEN Stop ELSE Pass

\* The cleartext decision. An unencrypted job that is let through
\* has 1 line in the log, and the line names the job.
Cleartext ==
  IF ~m.encrypted /\ ~AllowCleartext
  THEN Stop
  ELSE IF ~m.encrypted
  THEN /\ named' = TRUE
       /\ step' = step + 1
       /\ UNCHANGED <<m, outcome, noted, read>>
  ELSE Pass

\* Audience. Enforce refuses. Audit records and continues. Off
\* does not look. The check reads the body's audience, and a
\* mismatch that is recorded is recorded under the job's name.
Audience ==
  IF AudienceMode = "enforce" /\ ~m.audienceOk
  THEN /\ step' = 99
       /\ outcome' = "refuse"
       /\ named' = TRUE
       /\ read' = TRUE
       /\ UNCHANGED <<m, noted>>
  ELSE IF AudienceMode = "audit" /\ ~m.audienceOk
  THEN /\ noted' = TRUE
       /\ named' = TRUE
       /\ read' = TRUE
       /\ step' = step + 1
       /\ UNCHANGED <<m, outcome>>
  ELSE /\ read' = TRUE
       /\ step' = step + 1
       /\ UNCHANGED <<m, outcome, noted, named>>

\* Encodability. It reads every text of the body.
Encodable ==
  /\ read' = TRUE
  /\ IF m.surrogate
     THEN /\ step' = 99
          /\ outcome' = "refuse"
          /\ UNCHANGED <<m, noted, named>>
     ELSE /\ step' = step + 1
          /\ UNCHANGED <<m, outcome, noted, named>>

\* Script size bound, in bytes. It reads the body's script.
ScriptBound ==
  /\ read' = TRUE
  /\ IF m.scriptOver
     THEN /\ step' = 99
          /\ outcome' = "refuse"
          /\ UNCHANGED <<m, noted, named>>
     ELSE /\ step' = step + 1
          /\ UNCHANGED <<m, outcome, noted, named>>

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
  \* 4 to 8. The stretch. With BindFirst: 4 version, type,
  \*    identity; 5 cleartext decision; 6 audience; 7
  \*    encodability; 8 script size bound.
  \/ /\ step \in 4..8
     /\ LET check == Stretch[step - 3] IN
          \/ check = "identity" /\ Identity
          \/ check = "cleartext" /\ Cleartext
          \/ check = "audience" /\ Audience
          \/ check = "encodable" /\ Encodable
          \/ check = "script" /\ ScriptBound
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
             /\ UNCHANGED <<m, noted, named, read>>
        ELSE Pass
  \* 13. Advisory review. It sits here and changes no decision.
  \/ /\ step = 13
     /\ Pass
  \* 14. Dry run stops here.
  \/ /\ step = 14
     /\ IF m.dryRun
        THEN /\ step' = 99
             /\ outcome' = "dry"
             /\ UNCHANGED <<m, noted, named, read>>
        ELSE Pass
  \* 15. The claim.
  \/ /\ step = 15
     /\ IF m.claim = "taken"
        THEN Stop
        ELSE IF m.claim = "onRecord"
        THEN /\ step' = 99
             /\ outcome' = "resend"
             /\ UNCHANGED <<m, noted, named, read>>
        ELSE Pass
  \* 16. A cancel recorded before arrival refuses. Otherwise the
  \*     handling executes.
  \/ /\ step = 16
     /\ IF m.cancelled
        THEN Stop
        ELSE /\ step' = 99
             /\ outcome' = "execute"
             /\ UNCHANGED <<m, noted, named, read>>

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

\* Finding F16, the 2 that hold when the gate binds first and
\* break when it does not.
\*
\* A record that names the job names it by the signed id. The
\* subject's id is a stranger's text until step 4 has set it
\* against the body's.
NamedByTheSignedId ==
  named => m.idOk

\* Nothing else in the body is acted on before its version and
\* its type are known to be the 1 the gate reads it as.
OneVersionBeforeTheBody ==
  read => (m.versionOk /\ m.typeOk)

=============================================================================
