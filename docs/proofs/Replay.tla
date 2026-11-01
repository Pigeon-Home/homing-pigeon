----------------------------- MODULE Replay ------------------------------
\* P5, replay and at-most-once, modelled in full. One job id,
\* two handlings, and the disk state the code keeps for the id:
\* the replay cache (the seen set), the recorded result (the
\* outbox stash, then the sent record), and the claim file.
\* Claim.tla checked the two handlers' race for the slot in
\* isolation; this model is the whole shape the replay property
\* speaks about -- deliver, execute, redeliver -- including the
\* resend's digest match, the stealing of a dead holder's
\* claim, a restart, and the two retentions expiring.
\*
\* A handling stands for one gate-passing delivery of the id
\* reaching the claim (step 15 of P1's order; the steps before
\* it are P1's, and the properties compose by position). The
\* body a delivery carries enters only as its digest class:
\* "same" is the job as first sent -- the only shape a replay
\* of captured bytes can have, because the digest covers every
\* member of the job but the signature, so altered bytes are a
\* different digest -- and "other" is a different job under the
\* same id, a shape only the key holder's own fresh signature
\* can present. Execution counts are kept per shape: the
\* property is per job, and a different job under a reused id
\* is a different job.
\*
\* The windows are state, not commentary. A crash (or a
\* restart) between a run and its record sets crashCount for
\* the shape that ran. The seen entry ageing out while the
\* record remains sets seenGone. The record ageing out sets
\* recordGone. The invariant prices each window exactly once,
\* which is the statement in properties.md: inside the windows
\* named there and no others, a shape executes at most once,
\* and each window event buys at most one further execution.
\* Window events are bounded at one per kind (one crash per
\* shape, one expiry per layer): the purchase arithmetic is
\* linear, so one event of each kind exhibits every shape a
\* second event would only repeat at a larger count.

EXTENDS Integers

Handlers == {1, 2}
Shapes == {"same", "other"}
HName == [h \in Handlers |-> IF h = 1 THEN "one" ELSE "two"]
            \* claim values are all strings: a handler's name,
            \* "free", or "dead"

VARIABLES
  pc,       \* per handler: "idle", "claim", "go", "run"
  shape,    \* per handler: the digest class of its delivery
  claim,    \* "free", a handler, or "dead" (a claim file whose
            \* holder is gone, stealable under the stale rule)
  seen,     \* the replay cache holds the id (seen.json)
  record,   \* the recorded result's digest class, or "none"
  execCount,
  crashCount,
  seenGone,
  recordGone,
  answered,
  delivered

vars == <<pc, shape, claim, seen, record, execCount, crashCount,
          seenGone, recordGone, answered, delivered>>

Init ==
  /\ pc = [h \in Handlers |-> "idle"]
  /\ shape = [h \in Handlers |-> "same"]
  /\ claim = "free"
  /\ seen = FALSE
  /\ record = "none"
  /\ execCount = [s \in Shapes |-> 0]
  /\ crashCount = [s \in Shapes |-> 0]
  /\ seenGone = FALSE
  /\ recordGone = FALSE
  /\ answered = FALSE
  /\ delivered = FALSE

\* A gate-passing delivery of the id reaches the claim.
Arrive(h, s) ==
  /\ pc[h] = "idle"
  /\ shape' = [shape EXCEPT ![h] = s]
  /\ pc' = [pc EXCEPT ![h] = "claim"]
  /\ UNCHANGED <<claim, seen, record, execCount, crashCount,
                 seenGone, recordGone, answered, delivered>>

\* The claim step, under the lock and the seen file. A seen id
\* ends the handling: the copy is done, and nothing is sent by
\* this handling -- the result it would duplicate is the
\* outbox's to deliver. A live claim held by the other handling
\* ends it the same way for the claim: deferred or dropped, in
\* neither case executed. A free claim, or a dead holder's, is
\* taken (the dead one is the stale-claim steal).
ClaimStep(h) ==
  /\ pc[h] = "claim"
  /\ \/ /\ seen
        /\ pc' = [pc EXCEPT ![h] = "idle"]
        /\ UNCHANGED <<claim, seen, record, execCount,
                       crashCount, seenGone, recordGone,
                       answered, delivered, shape>>
     \/ /\ ~seen
        /\ claim \in {HName[h], "free", "dead"}
        /\ claim' = HName[h]
        /\ pc' = [pc EXCEPT ![h] = "go"]
        /\ UNCHANGED <<seen, record, execCount, crashCount,
                       seenGone, recordGone, answered,
                       delivered, shape>>
     \/ /\ ~seen
        /\ claim \notin {HName[h], "free", "dead"}
        /\ pc' = [pc EXCEPT ![h] = "idle"]
        /\ UNCHANGED <<claim, seen, record, execCount,
                       crashCount, seenGone, recordGone,
                       answered, delivered, shape>>

\* Holding the claim, with no seen entry: the record decides.
\* A record for this exact job -- the digest matches -- is
\* resent, the id is committed as seen, and nothing runs. A
\* record for a different job under this id, or no record,
\* sends the handling to execution: a different job under a
\* reused id runs on its own.
DecideStep(h) ==
  /\ pc[h] = "go"
  /\ claim = HName[h]
  /\ \/ /\ record = shape[h]
        /\ answered' = TRUE
        /\ seen' = TRUE
        /\ claim' = "free"
        /\ pc' = [pc EXCEPT ![h] = "idle"]
        /\ UNCHANGED <<record, execCount, crashCount, seenGone,
                       recordGone, delivered, shape>>
     \/ /\ record # shape[h]
        /\ pc' = [pc EXCEPT ![h] = "run"]
        /\ UNCHANGED <<claim, seen, record, execCount,
                       crashCount, seenGone, recordGone,
                       answered, delivered, shape>>

\* The run, and the commit that follows it in the code with no
\* step between: the result is stashed and the id committed as
\* seen before the first send is attempted, so delivery is
\* recorded with the commit -- the outbox's retries are its
\* own concern, inside the stash window the statement names.
FinishRun(h) ==
  /\ pc[h] = "run"
  /\ execCount[shape[h]] < 2
  /\ execCount' = [execCount EXCEPT ![shape[h]] = @ + 1]
  /\ record' = shape[h]
  /\ seen' = TRUE
  /\ delivered' = TRUE
  /\ claim' = "free"
  /\ pc' = [pc EXCEPT ![h] = "idle"]
  /\ UNCHANGED <<crashCount, seenGone, recordGone, answered,
                 shape>>

\* The one window the code names: the process dies -- a crash,
\* or a restart, which is the same event from the record's
\* side -- after the run and before the stash, or during the
\* run, which no record distinguishes from it. The run counts;
\* no record exists; the claim file is left to a dead holder.
CrashRun(h) ==
  /\ pc[h] = "run"
  /\ execCount[shape[h]] < 2
  /\ crashCount[shape[h]] = 0
  /\ execCount' = [execCount EXCEPT ![shape[h]] = @ + 1]
  /\ crashCount' = [crashCount EXCEPT ![shape[h]] = 1]
  /\ claim' = "dead"
  /\ pc' = [pc EXCEPT ![h] = "idle"]
  /\ UNCHANGED <<seen, record, seenGone, recordGone, answered,
                 delivered, shape>>

\* Death after the claim and before any run: nothing executed,
\* and the claim is stealable. No window is bought -- a later
\* execution is the first.
CrashClaim(h) ==
  /\ pc[h] = "go"
  /\ claim = HName[h]
  /\ claim' = "dead"
  /\ pc' = [pc EXCEPT ![h] = "idle"]
  /\ UNCHANGED <<seen, record, execCount, crashCount, seenGone,
                 recordGone, answered, delivered, shape>>

\* A transient failure before execution releases the claim in
\* the finally span, without a record and without a run; the
\* delivery is retried on a later poll.
ReleaseClaim(h) ==
  /\ pc[h] = "go"
  /\ claim = HName[h]
  /\ claim' = "free"
  /\ pc' = [pc EXCEPT ![h] = "idle"]
  /\ UNCHANGED <<seen, record, execCount, crashCount, seenGone,
                 recordGone, answered, delivered, shape>>

\* The seen entry ages out (or is evicted at the cache's cap)
\* while the record remains. The resend path now stands
\* between a same-shape redelivery and any re-execution; a
\* different shape is no longer dropped at the cache and runs
\* on its own, which is the one purchase this event makes.
SeenExpire ==
  /\ seen
  /\ record # "none"
  /\ ~seenGone
  /\ seen' = FALSE
  /\ seenGone' = TRUE
  /\ UNCHANGED <<pc, shape, claim, record, execCount,
                 crashCount, recordGone, answered, delivered>>

\* The record ages out, after the seen entry: both layers are
\* gone, and the id is a new id to the runner. One further
\* execution of either shape is the purchase.
RecordExpire ==
  /\ record # "none"
  /\ ~seen
  /\ ~recordGone
  /\ record' = "none"
  /\ recordGone' = TRUE
  /\ UNCHANGED <<pc, shape, claim, seen, execCount, crashCount,
                 seenGone, answered, delivered>>

Next ==
  \/ \E h \in Handlers, s \in Shapes : Arrive(h, s)
  \/ \E h \in Handlers : ClaimStep(h)
  \/ \E h \in Handlers : DecideStep(h)
  \/ \E h \in Handlers : FinishRun(h)
  \/ \E h \in Handlers : CrashRun(h)
  \/ \E h \in Handlers : CrashClaim(h)
  \/ \E h \in Handlers : ReleaseClaim(h)
  \/ SeenExpire
  \/ RecordExpire
  \/ /\ \A h \in Handlers : pc[h] = "idle"
     /\ UNCHANGED vars

Spec == Init /\ [][Next]_vars

\* The property. Each shape executes at most once, plus one
\* further execution for each window event that buys one: a
\* crash after that shape's run, the record's expiry (either
\* shape), and -- for the other shape only -- the seen entry's
\* expiry while the record stood, which lets a different job
\* under the id past the cache to its own first run.
P5Inv ==
  /\ execCount["same"] <= 1 + crashCount["same"]
                            + (IF recordGone THEN 1 ELSE 0)
  /\ execCount["other"] <= 1 + crashCount["other"]
                            + (IF recordGone THEN 1 ELSE 0)
                            + (IF seenGone THEN 1 ELSE 0)

\* The seen set is only ever committed beside a record: the
\* stash is written first, in the same locked span, and the
\* resend path commits an id whose record already stands.
SeenImpliesRecord == seen => record # "none"

\* A result is delivered only for a job that was recorded;
\* the record's later expiry does not un-deliver it.
DeliveredImpliesRecord == delivered => record # "none" \/ recordGone

\* Witness probes. Both are expected to FAIL; their
\* counterexamples are the evidence the discipline requires.
\* NothingExecutes says no delivery of either shape ever runs
\* -- its counterexample is forced to be a first execution.
NothingExecutes ==
  execCount["same"] = 0 /\ execCount["other"] = 0

\* NeverAnswered says no duplicate is ever answered from the
\* record. Answering happens at one place in the model, the
\* resend branch of DecideStep, which requires a standing
\* record and no seen entry -- so its counterexample is
\* forced to be that shape: a run, a record, the seen entry
\* gone, and the same job delivered again and answered from
\* the record without a second run.
NeverAnswered == ~answered

=============================================================================
