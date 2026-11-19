# The v4 binding: the general statement

This file is the record of the pass that follows
`v4-working.md`. It answers items 1 and 8 of `docs/FUTURE.md`
together: the proof of the v4 binding, generalized and then
formalized. `docs/FUTURE.md` is the owner's file; this work is
based on it and does not change it.

The 13 properties each have a door of their own: P1 to P6 in
`properties.md`, P7 to P13 in `v4-properties.md`. Each small
model on this shelf holds 1 door, at 1 occasion, and leaves the
rest of the runner out. That is what keeps them small, and it
is what they cannot show: that the doors hold together, over a
whole life, while the world moves between one door and the
next. This pass states that, models it, checks it, and holds it
to the code.

## The general statement

3 terms carry it.

- A **door** guards an **effect**. The effect is a thing the
  runner does that a property is about: it comes up, it reads a
  signed body, it agrees a session, it runs a job, it signs a
  result, it gives up material. The guard is the condition the
  property puts on the effect.
- An **occasion** is the step of the runner's life at which an
  effect happens: the start, a poll, a session, an arrival, a
  spawn, a signing, a guard pass.
- The **world** is what no door owns and anything may move
  between 2 occasions: the configuration file, the secret
  files, whether the confinement backend can engage, the disk,
  and the clock against the freshness window.

> **G.** In every reachable state of a runner's life, every
> effect that has happened passed its door at its own occasion,
> with the guard read off the world as it stood at that step,
> and no door's work has moved the state another door stands
> on.

The 13 properties are the instances of G. The table gives each
its occasion, its effect and its guard, in the order a life
meets them.

| Property | Occasion | Effect | Guard |
|----------|----------|--------|-------|
| P6 | the start | the runner is up | no refuse class value is unusable |
| P13 | the start, every poll, every local arrival | a signed body is read | every key in the map built at that step is at or over the floor |
| P10 | the start, every spawn | a run under `enforce` on a probed platform | the backend engages at that step |
| P9 | a session | a session exists | both ends run the same side of the framing change |
| P8 | a session | X25519 alone is agreed | the hybrid group was not both offered and supported |
| P3 | an arrival on a transport with credentials | the body reaches the gate | the transport's own credentials passed |
| P12 | a local arrival | the body reaches verification | within the local cap, and not a symlink |
| P1 | a handling | a job runs | the 9 clauses, in their order |
| P4 | a handling | a job runs under a key | that key's policy allows it |
| P5 | a handling | a job runs | no earlier run of this job, save across a priced window |
| P2 | a spawn | confinement is applied | never wider than the ceiling, and under `enforce` never absent |
| P11 | a signing | a result body leaves | within the cap, or at its floor and marked |
| P7 | a guard pass | material is given up | the runner's own, in the stated order, on a disk that measures over; the runner goes on, and the protected state stands |

A counterexample to G is a life in which 1 of 2 things
happens, and neither can be seen in a model of 1 door:

- an effect whose guard held when the code looked and did not
  hold when the effect happened, because the code decided at
  another occasion than the effect's;
- an effect that 1 door let through because another door's
  work had moved the state the first stands on.

## The model

`general.tla`, module `General`, is 1 runner life.

The world is 5 variables: `cfgfile`, `secret`, `engage`, `disk`
and `age`. Any of them may move between any 2 steps of the
runner. The runner is `up` or not, `inpoll` or not, with 1 job
in `stage` idle or ran, a replay `cache` that holds the job's
id or not, a `record` that is none, pending or sent, `execs`
and `bought` to count runs and the priced windows used, a
`session`, and `filed` for an alert filed at the local door.

`held` is the ledger: 1 mark for each of the 13 properties,
true at the start. A step that makes an effect leaves, for each
property whose door the effect passed, that property's own
guard read off the world at that step. `General` says every
mark is true. `P1Inv` to `P13Inv` are the 13 marks by name, so
a counterexample names the property it breaks. `AtMostOnce`
states P5 a second way, off the counts and not off the ledger.

The steps, each read from the code it models:

- `Start`: `main` in `runner/ops/main.py`. The configuration,
  the key map and, under `enforce`, the confinement probe.
- `PollBegin`: `poll_once` in `runner/ops/poll.py`, whose first
  act is `build_secrets`. A map that fails the floor raises
  there, before anything is read, and the loop in `main` names
  the failed cycle and goes on.
- `Agree`: the v3 handshake's group selection.
- `Handle`: `handle_mail` in `runner/ops/mail.py`. The gate,
  then the cache, then the record, then the spawn, where
  `_confinement_argv` in `runner/runner.py` asks the backend
  again under `enforce`.
- `Commit`, `StashFails`, `Deliver`: `commit_and_deliver` in
  the same file. The result is fitted and signed, the record
  and the cache are written in 1 span, and a stash that cannot
  be written leaves the job uncommitted.
- `Guard`: `guard_disk` in `runner/oracle/resources.py`.
- `Local`: `_ingest_local_envelope_inner` in
  `runner/runner.py`.
- `Crash`, `CacheLeaves`, `RecordLeaves`, `WorldMoves`: what
  happens to the runner, not what it does.

What the model takes as given, beyond the assumptions of
`readme.md`:

- **A1. The ordinary configuration.** The record's retention
  and the stash window outlast the freshness window, as P5
  clauses 9 and 10 take them to. So the record leaves by age
  only once the job is stale.
- **A2. A job once stale stays stale.** The freshness window
  does not grow during a life. `max_job_age_sec` is a hot key,
  and an owner who raises it reopens ids the cache and the
  guard have let go, as P5 clause 9 says of a retention set
  under the window.
- **A3. 1 job, 1 process, 1 priced window.** The same bytes on
  every delivery. The race of 2 handlings for 1 claim is
  `claim.tla`'s and `replay.tla`'s.

## The 5 seams

A seam is a place where a door could have been built to decide
at another occasion than its effect's, or to move another
door's state. The model has a constant for each. The main
configuration sets it the way the code is. A witness
configuration sets it the other way, and the checker then
breaks the property the seam carries.

| Constant | What the code does | Carries | Witness | Held to the code by |
|----------|--------------------|---------|---------|---------------------|
| `PollRebuilds` | every poll builds the key map; a map that fails the floor ends the poll before anything is read | P13 | `generalwitnesspoll.cfg` | `SeamPoll` |
| `SpawnProbes` | under `enforce` every spawn asks the backend again; the start's answer is not carried | P2, P10 | `generalwitnessspawn.cfg` | `SeamSpawn` |
| `GuardSparesFresh` | the disk guard does not give up a recorded result a redelivery the door would still take could need | P5 | `generalwitnessreap.cfg` | `SeamGuardReplay` |
| `GuardSparesCache` | the disk guard never touches the replay cache or the waiting outbox | P7 | `generalwitnesscache.cfg` | `SeamGuardCache` |
| `LocalFilesOnly` | the local door files alerts and runs nothing | P1, P5 | `generalwitnesslocal.cfg` | `SeamLocal` |

The classes named in the last column are in
`runner/tests/test_v4_general.py`. Each drives the real code
across its seam: the real `poll_once` on a secret file that
goes weak after the start, the real `_confinement_argv` on a
backend that goes away after the start, the real `guard_disk`
and the real `handle_mail` in 1 life, the real guard over a
real cache and a real waiting result, and the real
`_ingest_local_envelope` on a signed script.

The marks at the start, at a session, at the gate's own
clauses and at the signing are decided at the step that makes
them, so in this model they cannot be false. Their doors are
proved in their own models. They stand in this one to place
each door in the life, and that is all this model claims for
them.

## The order of the work

No supposition was written before this pass's measurements.
The project's method asks for one, and this pass does not have
it. What stands in its place is the order in which the work was
done, and the suppositions for the next pass, written now, at
the foot of this file.

1. The code was read at the seams: the start, the poll loop,
   the hot reload, the local door, the spawn gate, the commit,
   the guard's classes, and the store a redelivery is answered
   from.
2. The seam between P5 and P7 was seen in that reading: the
   guard's third class is the store P5 clause 5 answers from. A
   probe on the real code showed finding F8 before the model
   was written.
3. The model was written in Python, with each seam as a switch,
   and searched: 32 initial states, 14,592 distinct states,
   every mark true with the seams as the code should have them,
   and P5 broken with the guard as it stood.
4. `general.tla` was written from the Python text. The
   checker's first run found 4,864 distinct states where the
   search had found 14,592. The difference was a slip in the
   TLA+ text: the session step held `session` unchanged, so no
   session was ever agreed. It was found because the 2 texts
   were written apart and counted apart. With the slip mended
   the checker found 14,592.
5. F8 was closed in the code, and the search, the checker and
   the real code were run again on the files as they stand.

## The search

`runner/tests/test_v4_general.py` holds the model a second
time, apart from the TLA+ file, and searches it breadth first
on every run of the suite.

With the seams as the code has them: 32 initial states, 14,592
distinct states. Every mark is true in every one, and
`AtMostOnce` and `ReadsWhileUp` hold in every one. Read off the
reachable states:

- The job runs 0, 1 or 2 times, and every state with 2 runs
  has used a priced window. A shortest life to a second run
  goes through a crash or a failed stash.
- The guard takes a recorded result only once the job is
  stale, and it does take one.
- A start, a poll and a local arrival each happen only on a
  strong secret.
- Each of the model's 14 steps is taken somewhere.

With each seam the other way, searched whole: 29,184 distinct
states for `PollRebuilds`, 21,312 for `SpawnProbes`, 39,936 for
`GuardSparesFresh`, 26,112 for `GuardSparesCache` and 62,208
for `LocalFilesOnly`. Each breaks the properties its row in the
table names, and no other.

## The checker

Run 2026-11-18 with TLC 2.19 of 08 August 2024, the v1.7.4
tools jar at revision 5a47802, on OpenJDK 21, in this seat's
container. The model was copied to its module's name for the
run, as in `v4-working.md`.

- `general.cfg`: no error. 32 initial states, 14,592 distinct
  states, the search's count. The state graph is 17 deep. The
  configuration names `TypeOK`, `General`, `AtMostOnce`,
  `ReadsWhileUp` and the 13 marks.
- The 5 seam witnesses each violate the invariant they name:
  `generalwitnesspoll.cfg` violates P13Inv,
  `generalwitnessspawn.cfg` violates P10Inv,
  `generalwitnessreap.cfg` violates P5Inv,
  `generalwitnesscache.cfg` violates P7Inv, and
  `generalwitnesslocal.cfg` violates P1Inv.
- The 4 probes each fail, as they must:
  `generalwitnessruns.cfg` violates NothingExecutes,
  `generalwitnesssecond.cfg` violates NoSecondRun,
  `generalwitnessfiled.cfg` violates NoAlertFiled, and
  `generalwitnesshybrid.cfg` violates NoHybridSession.

10 configurations in all: 1 main, 9 witnesses.

## Findings

The numbers continue `v4-search-2.md`'s.

### F8. The disk guard could buy a second run. Closed in the code

P5 clause 5 makes the recorded result the second layer of at
most once: a redelivery that finds the cache without the id is
answered from the record and runs nothing. P5 clause 1 lists
the only windows that buy another run, and clauses 7 to 9 price
them. The disk guard was not among them, and it could do what
they do. Its third class of material is `sent/`, the store that
answer comes from, and it took the oldest file there whatever
its age.

The life, as the checker gives it in `generalwitnessreap.cfg`
and as the real code ran it:

1. The job runs once. Its result is recorded and delivered.
2. The replay cache lets the id go while the job is still
   fresh: at its cap of 200,000 entries, or by a lost cache
   write. Those are 2 of the ways P5 clause 5 names. The
   third, age, cannot fall inside the freshness window (P5
   clause 8).
3. The disk measures at or over 90 percent, and a guard pass
   reaches the recorded results and removes the job's record.
4. The same bytes are delivered again, still inside the
   freshness window. The gate takes them, the cache does not
   know the id, there is no record, and the job runs a second
   time. No crash, no failed stash and no expiry stands between
   the 2 runs.

It needs 3 things at once, and the first of them, the cache
losing an id it should still hold, needs a great many jobs
inside 1 freshness window. It is an edge. It is also a second
run that P5's own words said could not happen.

It is closed in the code, in `guard_disk`. A recorded result
no older than the freshness window and its 300 second future
bound is not material for the guard: it stays. That is
`_guard_replay_window`, read from `max_job_age_sec` as the door
reads it, plus `DISK_GUARD_REPLAY_SKEW_SEC`. The arithmetic,
held by a test: the door takes a job dated from 300 seconds
ahead of the clock to the window behind it, and the record is
written no earlier than the door took the job, so the last
instant a redelivery is still fresh is the record's time plus
300 plus the window. Past that, the guard takes the record as
before, and a redelivery of bytes that old is refused as stale
before it reaches the claim.

What moved with it: 6 of the guard's own tests wrote fresh
recorded results and now write old ones, 5 tests of the rule
joined them in `runner/tests/test_disk_guard.py`, and C28 in
`constraints.md` and in `v4-properties.md` and the guard's
entry in `configuring-oracle.md` state the rule.

The other way to close it was in P5's words: price the guard
as a fourth window. That would have kept the guard as it was
and made the promise smaller. The code was changed instead,
because the promise is the older of the 2 and the guard loses
little: at the defaults, the records of the last 65 minutes.
The choice is the owner's to reverse.

### F9. P12 said the local door was the mail gate. Closed in P12's words

P12 ended: the local path's bound stands in front of the same
gate the mail path faces. The model needed the local door's
clauses exactly, and the code's are fewer. After its bound the
local door builds a key map, verifies the signature, and checks
the contract version, the kind, the version and type, the age
and the key policy, then hands the alert to the 1 ingest both
paths share. It asks no cleartext decision, no audience clause
and no replay cache, all 3 of which a mailed alert passes
first.

Nothing runs through the local door, so P1, which is about a
run, loses nothing. `SeamLocal` holds that: a signed script
that the mail gate runs is turned away at the local door by its
kind. But the sentence claimed more than the code does, and
P12 now says what the door applies and what it does not.
`localgate.tla`'s header carried the same sentence and is
corrected the same way. The checker was run on that file again
as it stands: 96 initial states, 200 distinct states, no
error, and its 2 witnesses violate what they name.

## What this pass does not show

- It is not a refinement proof. The 13 small models are not
  yet shown, by the checker, to be views of this one. Each
  stands on its own run and its own conformance, and this model
  takes each door's inside from them.
- 7 of the 13 marks cannot be false here, as the seams section
  says: those of P3, P4, P6, P8, P9, P11 and P12. This model's
  claim for those 7 properties is their place in the life, no
  more.
- 1 job and 1 process. A second id and a second process are
  not in it.
- The guard's rule for workspaces takes one untouched for 3600
  seconds, and a job runs for at most 3600 seconds: there is
  no margin between the 2 for a job's stopping and its
  collection. This model carries no run length, so that is
  named here and not checked.
- A2 above: a freshness window raised during a life.

## Suppositions for the next pass

Written 2026-11-18, before that pass is begun.

- **N1.** Each of the 6 small v4 models is a view of
  `general.tla`: under a mapping of its variables to this
  model's, every step of `General` is a step of the small model
  or leaves its variables alone. TLC can check that as a
  refinement for `secretfloor.tla`, `probegate.tla` and
  `hybridselect.tla` as they stand. `diskguard.tla`,
  `localgate.tla` and `resultfit.tla` will need this model
  widened first, to carry the guard's 4 classes, the local
  door's forms and sizes, and the body's 3 shapes as state.
- **N2.** A second job id adds no seam. The model with 2 ids
  holds every mark with the same 5 constants and no sixth.
- **N3.** The workspace rule has a life in which a guard pass
  removes the workspace of a job that is still being stopped. A
  model that carries run length will find it, and the real code
  will show it only with a job at the 3600 second bound.

## The second seat's run

Claude's seat left 1 thing for this seat in the forum of
2026-11-18: a second run of the checker, from a second seat,
over `general.cfg` and its 9 witnesses. This section is that
run's record. Its suppositions stand first, written before the
run was made, in the project's way. The first pass of this
file had none, and said so plainly. This pass has them.

- **S1.** `general.cfg` comes back with no error: 32 initial
  states, 14,592 distinct states, the state graph 17 deep.
  The first seat's counts, met exactly.
- **S2.** Each of the 9 witnesses violates the invariant it
  names, and its run stops on that invariant: the poll witness
  on P13Inv, the spawn witness on P10Inv, the reap witness on
  P5Inv, the cache witness on P7Inv, the local witness on
  P1Inv, the runs witness on NothingExecutes, the second
  witness on NoSecondRun, the filed witness on NoAlertFiled,
  and the hybrid witness on NoHybridSession.
- **S3.** `localgate.cfg`, as it stands after F9, comes back
  with no error: 96 initial states, 200 distinct states.

### The run

Run 2026-11-18 with TLC 2.19 of 08 August 2024, the v1.7.4
tools jar at revision 5a47802, on OpenJDK 21, in this seat's
container: the same checker the first seat's record names.
The model files were taken from this branch's head, at the
commit that carries the suppositions above, and copied to
their modules' names for the run, as in `v4-working.md`.

- `general.cfg`: no error. 32 initial states, 145,248 states
  generated, 14,592 distinct states, 0 states left on the
  queue. The state graph is 17 deep.
- The 9 witnesses each violate the invariant they name, and
  each run stops on that invariant: `generalwitnesspoll.cfg`
  violates P13Inv, `generalwitnessspawn.cfg` violates
  P10Inv, `generalwitnessreap.cfg` violates P5Inv,
  `generalwitnesscache.cfg` violates P7Inv,
  `generalwitnesslocal.cfg` violates P1Inv,
  `generalwitnessruns.cfg` violates NothingExecutes,
  `generalwitnesssecond.cfg` violates NoSecondRun,
  `generalwitnessfiled.cfg` violates NoAlertFiled, and
  `generalwitnesshybrid.cfg` violates NoHybridSession.
- `localgate.cfg`: no error. 96 initial states, 200 distinct
  states.

The same 11 configurations were also run with a newer
checker, TLC of 15 November 2026 at revision bc1b506, and it
returned the same verdict and the same count on every one.

### Conclusions against the suppositions

S1 holds as written: the general model's counts from this
seat are the first seat's counts, met exactly. S2 holds as
written: all 9 witnesses violate the invariant they name and
no witness stops on any other. S3 holds as written: the
local gate as it stands after F9 checks at 200 distinct
states with no error. The 2 seats' runs agree on every count
the first seat reported, and nothing in this run moves any
number elsewhere in this file.
