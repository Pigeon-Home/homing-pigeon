----------------------------- MODULE Surfaces ----------------------------
\* Stage 6, item 3. The doors beside the job door, each at the
\* early bound the code already applies before that door acts.
\*
\*   job     handle_mail. A script runs only when the early
\*           bound passed: signed, encrypted (cleartext is
\*           refused), and the freshness and identity checks
\*           folded into boundsOk.
\*   cancel  handle_cancel_mail. Same admit, then a cancel.
\*           It runs no script.
\*   query   handle_query_mail. Same admit, then an answer
\*           from a record. It runs no script.
\*   board   handle_board_mail. Same admit, then a task
\*           message. It runs no script.
\*   v2      handle_v2_mail. The handler's own line: never a
\*           job. It runs no script.
\*   local   _ingest_local_envelope. A same-box alert. The
\*           code refuses every kind but sensor_alert, so it
\*           runs no script. The signature is required; the
\*           envelope is not the mail encryption envelope.
\*
\* boundsOk is the shared remainder: version, type matches
\* the door, identity, freshness, audience, and the key
\* policy for that door. Opening each of those is the
\* per-door code. This model checks the composition the
\* raise asks for: a script runs on exactly one door, and
\* only after the early bound.

EXTENDS Integers

Surfaces == {"job", "cancel", "query", "board", "v2", "local"}

Attempts == [
  surface: Surfaces,
  signed: BOOLEAN,
  encrypted: BOOLEAN,
  boundsOk: BOOLEAN
]

Admitted(a) ==
  /\ a.signed
  /\ a.boundsOk
  /\ a.encrypted \/ a.surface = "local"

RunsScript(a) ==
  a.surface = "job" /\ Admitted(a)

VARIABLES a, decided, ran

vars == <<a, decided, ran>>

Init ==
  /\ a \in Attempts
  /\ decided = FALSE
  /\ ran = FALSE

Next ==
  \/ /\ ~decided
     /\ ran' = RunsScript(a)
     /\ decided' = TRUE
     /\ UNCHANGED a
  \/ /\ decided
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* A script runs only for an admitted job. Every other door
\* runs none, including a local alert and a version 2
\* message.
SurfacesInv ==
  decided =>
    /\ ran => a.surface = "job" /\ Admitted(a)
    /\ a.surface # "job" => ~ran

\* Expected to fail: an admitted job does run.
NothingRuns == ~ran \/ ~decided

\* Expected to fail: an admitted cancel does not run a
\* script. The counterexample is the cancel being admitted
\* and still not running, which is the door's behaviour.
CancelRuns ==
  ~(decided /\ a.surface = "cancel" /\ Admitted(a) /\ ~ran)

=============================================================================
