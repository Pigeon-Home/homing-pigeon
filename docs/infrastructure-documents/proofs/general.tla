------------------------------ MODULE General ------------------------------
\* The general statement of v4-general.md: one runner life, with
\* every door of P1 to P13 at its own occasion. The 13 small
\* models on this shelf each hold 1 door, at 1 occasion, with the
\* rest of the runner left out. This model leaves the inside of
\* each door to its own model and keeps what they leave out: the
\* order of the occasions in a life, the state 2 doors share, and
\* a world that moves between one occasion and the next.
\*
\* A door guards an effect at an occasion. The occasions, as the
\* code visits them: the start (runner/ops/main.py), a poll
\* (poll_once in runner/ops/poll.py, which builds the key map
\* first), a session, an arrival on the mail path (handle_mail in
\* runner/ops/mail.py), the spawn, the signing and the commit, a
\* disk guard pass (guard_disk in runner/oracle/resources.py),
\* and an arrival at the local door
\* (_ingest_local_envelope_inner in runner/runner.py).
\*
\* The world is 5 variables that no door owns: the configuration
\* file, the key map as it would be built now, whether the
\* confinement backend can engage now, the disk, and the job's
\* age against the freshness window. Any of them may move
\* between any 2 steps. A job once stale stays stale: the window
\* is taken not to grow during a life.
\*
\* held is the ledger. An effect leaves a mark for each property
\* whose door it passed, and the mark is the property's own
\* guard read off the world at that step. General says every
\* mark is true: every effect passed its door at its own
\* occasion.
\*
\* The model follows 1 job, the same bytes on every delivery,
\* and 1 priced window of P5 at most in a life. execs counts its
\* runs and bought the windows used: a crash between a run and
\* its record, or a stash that cannot be written (P5 clause 7).
\* The record and the cache leave as P5 clauses 8 to 10 say: the
\* cache at its cap at any time, the record only once the job is
\* stale, the ordinary configuration those clauses name.
\*
\* 14 constants state what the code does at the seams. The main
\* configuration sets all 14 TRUE. Each has a witness
\* configuration that sets it FALSE, and the checker then breaks
\* the property the seam carries. So every mark of the ledger is
\* one the checker can break, and each by a fact of the code
\* that is named here and held to the code.
\*
\* 5 are seams between doors, 1 for each place where a door could
\* have been built to decide at another occasion than its
\* effect's, or to move another door's state:
\*
\*   PollRebuilds      every poll builds the key map, and a
\*                     poll whose map fails the floor reads
\*                     nothing (P13)
\*   SpawnProbes       under enforce every spawn asks the
\*                     backend again; the start's answer is
\*                     not carried (P2, P10)
\*   GuardSparesFresh  the disk guard does not give up a
\*                     recorded result that a redelivery the
\*                     door would still take could need (P5)
\*   GuardSparesCache  the disk guard never touches the
\*                     replay cache (P7)
\*   LocalFilesOnly    the local door files alerts and runs
\*                     nothing (P1, P5)
\*
\* 9 are the doors' own guards. Each says a door applies its
\* guard at the step that makes its effect. The inside of each
\* guard is proved in its own model: gate.tla, transgate.tla,
\* keypolicy.tla, decision.tla, hybridselect.tla, resultfit.tla
\* and localgate.tla. What stands here is that a life cannot
\* reach the effect around the guard:
\*
\*   GateVerifies      the gate admits an arrival only with its
\*                     signature and the rest of its clauses
\*                     (P1)
\*   GateFresh         the gate admits only a job inside the
\*                     freshness window, which is also what
\*                     bounds a replay (P1, P5)
\*   GatePolicy        the key's policy is asked at the gate
\*                     (P4)
\*   TransportGates    an arrival by a transport that has a
\*                     credential shows it (P3)
\*   StartValidates    a start refuses a configuration it
\*                     cannot use (P6)
\*   PrefersHybrid     a session that can agree the hybrid
\*                     group agrees it (P8)
\*   SameSideOnly      no session is agreed across the framing
\*                     break (P9)
\*   FitMarks          a body that leaves over its cap leaves
\*                     marked (P11)
\*   LocalBounds       the local door bounds an envelope
\*                     before it reads it (P12)
\*
\* This file was run with TLC on 2026-11-18, and the checker
\* found the count the search had predicted. The model it
\* states is searched by runner/tests/test_v4_general.py, which
\* also holds each of the 14 constants to the real code. The
\* counts and the checker's verdicts are in v4-general.md.

EXTENDS Integers

CONSTANTS PollRebuilds, SpawnProbes, GuardSparesFresh, GuardSparesCache,
          LocalFilesOnly, GateVerifies, GateFresh, GatePolicy,
          TransportGates, StartValidates, PrefersHybrid, SameSideOnly,
          FitMarks, LocalBounds

Props == {"P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10",
          "P11", "P12", "P13"}
Doors == {"mail", "transport", "v3"}

VARIABLES mode, cfgfile, secret, engage, disk, age,
          up, inpoll, stage, cache, record, execs, bought, session,
          filed, held

world == <<cfgfile, secret, engage, disk, age>>
vars == <<mode, world, up, inpoll, stage, cache, record, execs, bought,
          session, filed, held>>

Flip(v, a, b) == IF v = a THEN b ELSE a

\* P2 clause 1 and P10: under enforce there is a run only where
\* the backend engages.
Confined == mode = "enforce" => engage

TypeOK ==
  /\ mode \in {"enforce", "audit"}
  /\ cfgfile \in {"usable", "unusable"}
  /\ secret \in {"strong", "weak"}
  /\ engage \in BOOLEAN
  /\ disk \in {"under", "over"}
  /\ age \in {"fresh", "stale"}
  /\ up \in BOOLEAN /\ inpoll \in BOOLEAN
  /\ stage \in {"idle", "ran"}
  /\ cache \in BOOLEAN
  /\ record \in {"none", "pending", "sent"}
  /\ execs \in 0..3 /\ bought \in 0..1
  /\ session \in {"none", "hybrid", "x25519"}
  /\ filed \in BOOLEAN
  /\ held \in [Props -> BOOLEAN]

Init ==
  /\ mode \in {"enforce", "audit"}
  /\ cfgfile \in {"usable", "unusable"}
  /\ secret \in {"strong", "weak"}
  /\ engage \in BOOLEAN
  /\ disk \in {"under", "over"}
  /\ age = "fresh"
  /\ up = FALSE /\ inpoll = FALSE /\ stage = "idle"
  /\ cache = FALSE /\ record = "none"
  /\ execs = 0 /\ bought = 0
  /\ session = "none" /\ filed = FALSE
  /\ held = [p \in Props |-> TRUE]

\* ---- The world moves, between any 2 steps of the runner.

WorldMoves ==
  /\ \/ /\ cfgfile' = Flip(cfgfile, "usable", "unusable")
        /\ UNCHANGED <<secret, engage, disk, age>>
     \/ /\ secret' = Flip(secret, "strong", "weak")
        /\ UNCHANGED <<cfgfile, engage, disk, age>>
     \/ /\ engage' = ~engage
        /\ UNCHANGED <<cfgfile, secret, disk, age>>
     \/ /\ disk' = Flip(disk, "under", "over")
        /\ UNCHANGED <<cfgfile, secret, engage, age>>
     \/ /\ age = "fresh" /\ age' = "stale"
        /\ UNCHANGED <<cfgfile, secret, engage, disk>>
  /\ UNCHANGED <<mode, up, inpoll, stage, cache, record, execs, bought,
                 session, filed, held>>

\* The replay cache lets the id go: at its cap at any time, by
\* age only when the job is stale too (P5 clause 8). The first
\* covers the second.
CacheLeaves ==
  /\ cache /\ cache' = FALSE
  /\ UNCHANGED <<mode, world, up, inpoll, stage, record, execs, bought,
                 session, filed, held>>

\* ---- The start: P6, P13 and P10, on the world as it stands.
\* A start that is refused is no step.

Start ==
  /\ ~up
  /\ StartValidates => cfgfile = "usable"
  /\ secret = "strong" /\ Confined
  /\ up' = TRUE
  /\ held' = [held EXCEPT !["P6"] = @ /\ cfgfile = "usable",
                          !["P13"] = @ /\ secret = "strong",
                          !["P10"] = @ /\ Confined]
  /\ UNCHANGED <<mode, world, inpoll, stage, cache, record, execs, bought,
                 session, filed>>

\* The process dies. What is on disk stays. A death between a
\* run and its record is P5's crash window.
Crash ==
  /\ up
  /\ stage = "ran" => bought = 0
  /\ up' = FALSE /\ inpoll' = FALSE /\ stage' = "idle"
  /\ bought' = IF stage = "ran" THEN 1 ELSE bought
  /\ UNCHANGED <<mode, world, cache, record, execs, session, filed, held>>

\* ---- A poll. It builds the key map before it reads anything,
\* and a map that fails the floor ends the poll there.

PollBegin ==
  /\ up /\ ~inpoll
  /\ PollRebuilds => secret = "strong"
  /\ inpoll' = TRUE
  /\ held' = [held EXCEPT !["P13"] = @ /\ secret = "strong"]
  /\ UNCHANGED <<mode, world, up, stage, cache, record, execs, bought,
                 session, filed>>

PollEnd ==
  /\ inpoll /\ stage = "idle"
  /\ inpoll' = FALSE
  /\ UNCHANGED <<mode, world, up, stage, cache, record, execs, bought,
                 session, filed, held>>

\* ---- A session: P8 and P9. No session is agreed across the
\* framing break.

Agree(offer, support, same) ==
  /\ up
  /\ SameSideOnly => same
  /\ session' = IF offer /\ support /\ PrefersHybrid
                 THEN "hybrid" ELSE "x25519"
  /\ held' = [held EXCEPT
       !["P9"] = @ /\ same,
       !["P8"] = @ /\ ((offer /\ support) => session' = "hybrid")]
  /\ UNCHANGED <<mode, world, up, inpoll, stage, cache, record, execs,
                 bought, filed>>

\* ---- An arrival on the mail path, at the gate: P1, P3 and P4.
\* A refusal at any clause is no step. The gate does not ask
\* which group a session agreed.

Admitted(door, cred, sig, rest, policy) ==
  /\ (door = "transport" /\ TransportGates) => cred
  /\ door = "v3" => session /= "none"
  /\ GateVerifies => (sig /\ rest)
  /\ GatePolicy => policy
  /\ GateFresh => age = "fresh"

\* Past the gate: the cache turns a duplicate away, the record
\* answers a redelivery and runs nothing, and what is left is
\* the spawn, which under enforce asks the backend at that step.
Handle(door, cred, sig, rest, policy) ==
  /\ up /\ inpoll /\ stage = "idle"
  /\ Admitted(door, cred, sig, rest, policy)
  /\ ~cache
  /\ \/ /\ record /= "none"
        /\ cache' = TRUE
        /\ UNCHANGED <<stage, execs, held>>
     \/ /\ record = "none"
        /\ (mode = "enforce" /\ SpawnProbes) => engage
        /\ execs < 3
        /\ stage' = "ran" /\ execs' = execs + 1
        /\ held' = [held EXCEPT
             !["P1"] = @ /\ sig /\ rest /\ age = "fresh",
             !["P3"] = @ /\ (door = "transport" => cred),
             !["P4"] = @ /\ policy,
             !["P5"] = @ /\ execs <= bought,
             !["P2"] = @ /\ Confined,
             !["P10"] = @ /\ Confined]
        /\ UNCHANGED cache
  /\ UNCHANGED <<mode, world, up, inpoll, record, bought, session, filed>>

\* ---- The signing and the commit: P11, and the record and the
\* cache written in 1 span. The streams fit, or are cut to fit,
\* or the body leaves at its floor, marked.

Left(body) == IF body = "floor" THEN "over" ELSE "within"
Marked(body) == body = "cut" \/ (body = "floor" /\ FitMarks)

Commit(body) ==
  /\ up /\ stage = "ran"
  /\ stage' = "idle" /\ record' = "pending" /\ cache' = TRUE
  /\ held' = [held EXCEPT
       !["P11"] = @ /\ (Left(body) = "within" \/ Marked(body))]
  /\ UNCHANGED <<mode, world, up, inpoll, execs, bought, session, filed>>

\* A stash that cannot be written leaves the job uncommitted:
\* the same window as the crash.
StashFails ==
  /\ up /\ stage = "ran" /\ disk = "over" /\ bought = 0
  /\ stage' = "idle" /\ bought' = 1
  /\ UNCHANGED <<mode, world, up, inpoll, cache, record, execs, session,
                 filed, held>>

Deliver ==
  /\ up /\ inpoll /\ record = "pending"
  /\ record' = "sent"
  /\ UNCHANGED <<mode, world, up, inpoll, stage, cache, execs, bought,
                 session, filed, held>>

\* The record ages out, or its delivery is given up: only once
\* the job is stale (P5 clauses 9 and 10).
RecordLeaves ==
  /\ up /\ inpoll /\ record /= "none" /\ age = "stale"
  /\ record' = "none"
  /\ UNCHANGED <<mode, world, up, inpoll, stage, cache, execs, bought,
                 session, filed, held>>

\* ---- A disk guard pass: P7. It acts only on a disk that
\* measures over, it may or may not reach the recorded results,
\* it never takes the waiting outbox, and it never stops the
\* runner.

Guard(reach) ==
  /\ up /\ inpoll /\ disk = "over"
  /\ LET reap == /\ reach /\ record = "sent"
                 /\ GuardSparesFresh => age = "stale"
         kept == IF GuardSparesCache THEN cache ELSE FALSE
     IN /\ record' = IF reap THEN "none" ELSE record
        /\ cache' = kept
        /\ held' = [held EXCEPT !["P7"] = @ /\ kept = cache]
  /\ UNCHANGED <<mode, world, up, inpoll, stage, execs, bought, session,
                 filed>>

\* ---- An arrival at the local door: P12, and P13 again, on a
\* key map of its own built at that step. It files an alert. It
\* applies no cleartext decision, no audience clause and no
\* replay cache, so a run through it would not have passed P1.

Local(form, size, sig, kind, policy) ==
  /\ up
  /\ LocalBounds => (form = "file" /\ size = "within")
  /\ secret = "strong"
  /\ sig /\ policy /\ age = "fresh"
  /\ \/ /\ kind = "alert"
        /\ filed' = TRUE
        /\ held' = [held EXCEPT
             !["P12"] = @ /\ form = "file" /\ size = "within",
             !["P13"] = @ /\ secret = "strong"]
        /\ UNCHANGED <<stage, execs>>
     \/ /\ kind = "script" /\ ~LocalFilesOnly
        /\ stage = "idle" /\ execs < 3
        /\ stage' = "ran" /\ execs' = execs + 1
        /\ held' = [held EXCEPT
             !["P1"] = FALSE,
             !["P5"] = @ /\ execs <= bought,
             !["P12"] = @ /\ form = "file" /\ size = "within",
             !["P13"] = @ /\ secret = "strong"]
        /\ UNCHANGED filed
  /\ UNCHANGED <<mode, world, up, inpoll, cache, record, bought, session>>

Next ==
  \/ WorldMoves
  \/ CacheLeaves
  \/ Start
  \/ Crash
  \/ PollBegin
  \/ PollEnd
  \/ \E offer, support, same \in BOOLEAN : Agree(offer, support, same)
  \/ \E door \in Doors, cred, sig, rest, policy \in BOOLEAN :
       Handle(door, cred, sig, rest, policy)
  \/ \E body \in {"fits", "cut", "floor"} : Commit(body)
  \/ StashFails
  \/ Deliver
  \/ RecordLeaves
  \/ \E reach \in BOOLEAN : Guard(reach)
  \/ \E form \in {"file", "symlink"}, size \in {"within", "over"},
        sig, policy \in BOOLEAN, kind \in {"alert", "script"} :
       Local(form, size, sig, kind, policy)

Spec == Init /\ [][Next]_vars

\* ---- The general statement, and the 13 it holds.

General == \A p \in Props : held[p]

P1Inv == held["P1"]
P2Inv == held["P2"]
P3Inv == held["P3"]
P4Inv == held["P4"]
P5Inv == held["P5"]
P6Inv == held["P6"]
P7Inv == held["P7"]
P8Inv == held["P8"]
P9Inv == held["P9"]
P10Inv == held["P10"]
P11Inv == held["P11"]
P12Inv == held["P12"]
P13Inv == held["P13"]

\* P5 again, read off the counts and not off the ledger: a run
\* past the first is one a priced window bought.
AtMostOnce == execs <= 1 + bought

\* Nothing is read by a runner that is not up, and a run is
\* never left standing across a poll's end.
ReadsWhileUp == (inpoll \/ stage = "ran") => up

\* Witness probes. Each is expected to FAIL; its counterexample
\* is the evidence that the model moves that way.
NothingExecutes == execs = 0
NoSecondRun == execs < 2
NoAlertFiled == ~filed
NoHybridSession == session /= "hybrid"

=============================================================================
