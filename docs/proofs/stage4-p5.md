# Stage 4, fourth property — P5, checked

This is the record of P5's pass through stage 4's cycle: the
full statement, the model, the check, and what the check does
not say. P5 is the fourth of stage 4's five properties; P6
remains a placeholder in `properties.md`, to be taken up in
turn. The statement is in `properties.md` (P5, eleven
clauses); the constraints it uses are C15 from stage 1 and
C23, C24, and C25, harvested from the code for this stage, in
`constraints.md`; the model is `Replay.tla` in this
directory. Stage 2's `Claim.tla` checked the two-handler
claim race at the centre of this property in isolation, and
stage 3 reconciled that race against the code and recorded
the mechanics around it — the stale-claim rule, the
`_IN_FLIGHT` lifecycle, the resend's digest condition — as a
gap (its G4) that a later property would own. This stage is
that owner.

The code read for this stage is the code at the `testing`
branch tip this stage started from, which is the code at
`6d6288c5` for every file named below.

## The property, in one paragraph

A job — a job id together with the SHA-384 digest of the job
as received — executes at most once per runner state
directory, and its result is delivered at least once. The
replay cache turns a duplicate away before anything else can
happen to it; one claim, taken in-process under the mail
lock and on disk under the seen-file lock, keeps two
handlings of the id from running it; and a redelivery that
arrives after the cache has let the id go is answered from
the recorded result, bound to the job's own digest, and runs
nothing. Three edges are priced in the statement rather than
hidden from it: a crash (a restart is the same event) between
a run and its record buys at most one further run; the
record ageing out buys at most one further run of a fresh
job under the id; and delivery is promised only inside the
stash window, after which a given-up record leaves the set a
redelivery is answered from while the execution guarantee
stands. A restart by itself neither grants nor loses an
execution, because every layer is disk state.

## Where the guarantee is kept — the code sites

**The key, and the cache.** A delivery becomes a seen key
through `_seen_key` (`runner/wire/verify.py`, line 1165):
the job id, namespaced by the configured `runner_id` when
there is one, so entries written before a `runner_id` was
first set do not collide with later ones. The cache is
`seen.json` in the state directory, entries stamped with
their recording time. It is loaded into memory at startup
(`runner/ops/main.py`, line 308) and on the channel path
(`runner/ops/handlers.py`, line 207), and every write merges
with the file under the seen-file lock (`save_seen`,
`runner/runner.py`, line 4972, over `_with_seen_file`,
line 4781), so two processes sharing a state directory hold
one cache between them, not two that wipe each other. The
horizon an entry is kept for is C23.

**The first turn-away.** `_early_dispatch`
(`runner/runner.py`, line 4653) looks the key up in the
in-memory cache before the message is treated as a job at
all (lines 4719 to 4723): a hit marks the mail seen and ends
the handling. No result is sent on this path, and none is
needed from it — the original result is the outbox's
responsibility (below).

**The claim.** In `handle_mail` (`runner/ops/mail.py`,
lines 260 to 278), under `_MAIL_LOCK`: a key in the cache or
in `_IN_FLIGHT` is skipped and the mail marked seen. Then
`_disk_owns` (`runner/ops/misc.py`, line 241) speaks for the
disk half, inside `_with_seen_file`: a key already in the
on-disk cache returns not-owned and is recorded in the
in-memory cache on the way out, and the handling marks the
mail seen and ends (lines 266 to 271). A live claim file
returns not-owned without that record, and the handling
leaves the message unseen (lines 272 to 278) — deferred, so
a crash in the holding process can be recovered by a later
poll instead of the job being dropped; this is the
cross-process half of stage 3's finding F3, an outcome-label
difference that touches delivery, never execution. Otherwise
the claim file is created with `O_EXCL` (line 294), carrying
pid, time, and key, and the handling proceeds with the key
added to `_IN_FLIGHT`. The stale rule that governs a claim
whose holder is gone is C24: a live pid is never stealable
at any age; a dead pid is stealable at once; an unreadable
pid only once the file is `_CLAIM_STALE_SEC` (86,400
seconds) old. The `finally` span (lines 734 to 738) removes
the key from `_IN_FLIGHT`, and releases the disk claim —
`_disk_release` (`runner/runner.py`, line 4900), which drops
only the caller's own claim, under the same lock — whenever
the key was not committed to the cache, so a transient
failure before execution leaves the id claimable by the
retry its message will get.

**The commit.** Execution's result is not sent and then
recorded; it is recorded and then sent. `commit_and_deliver`
(`runner/ops/mail.py`, lines 295 to 318), under `_MAIL_LOCK`,
stashes the signed result in the outbox, commits any chain
link, sets the key in the in-memory cache, writes the cache
to disk, marks the mail seen, and only then delivers from
the stash. A stash that cannot be written raises before any
commit: the job stays uncommitted and the next poll runs it
again — the code's own comment calls this "the one window,
and the only one", and clause 7 of the statement prices it
as such. Rejection results (a cancel honoured, a judge
refusal, a refused repair) travel the same stash-then-commit
path, so a refused job is also executed at most once and its
refusal delivered under the same discipline.

**The resend.** After the claim and before any execution,
`load_sent_result` (`runner/runner.py`, line 2326) looks for
the id's record: the waiting outbox record first, then the
sent record. It returns the record only when the record's
stored digest equals the received digest of the job now in
hand (`received_digest`, `runner/oracle/opinion.py`,
line 130 — every member of the job but `sig`, canonical
JSON, SHA-384). On a match, `handle_mail` (lines 320 to 330)
sends the recorded subject and body, commits the key as
seen, marks the mail, and returns: answered, not executed.
On a mismatch it returns no record, and the handling
proceeds to execute the job it carries — a different job
under a reused id runs on its own (clause 6). The reach of
this path is exactly the gap between the two retentions:
the cache no longer holds the id (its horizon passed, its
entry was evicted at the cap, or its write was lost) while
the record still stands.

**Delivery, and its window.** A stashed record is delivered
by `deliver_stash` (`runner/runner.py`, line 1718) at commit
time and by `resend_stashed` (line 1849) on later polls, at
most `RESEND_PASS_CAP` (50) records per pass, with
`result_resend_backoff_sec` (default 60) between a record's
attempts. After `result_stash_retention_sec` (default
86,400) of attempts the record is given up: `_stash_fail`
moves it to `outbox/failed/`, writes a delivery audit entry,
and logs one ERROR. From that moment the record is outside
the set the resend reads — `load_sent_result` names the
outbox and `sent/` and no third folder — while the cache
entry committed with the stash still stands and still turns
duplicates away. Delivery is therefore at-least-once inside
the stash window, and after it the execution half of the
property is untouched and the delivery half is no longer
claimed (C25, clause 10).

**Aging.** Once per poll (`runner/ops/poll.py`, lines 43 to
44) the sent records and the retained outputs are pruned at
`output_retention_days` (`_retention_days`,
`runner/runner.py`, line 1547: absent or unusable reads as
7; an explicit 0 or negative means no expiry, kept as-is).
The cache's own aging is on its writes (C23): the horizon is
computed from `max_job_age_sec`, so raising the freshness
window raises the cache's keep with it, and the floor of one
day covers the default freshness of one hour with room the
statement relies on in clause 8.

## The model

`Replay.tla` models one job id and two handlings of it,
with the disk state explicit: the cache (`seen`), the
record and its digest class, the claim (free, held by a
named handling, or dead — a claim file whose holder is
gone), and the in-flight span folded into the claim's held
states, as stage 3 found the two halves compose. A handling
moves through the code's own decision points: arrival at
the claim (P1's steps before it are abstracted — this
property composes with P1 by position, and an arrival here
is a gate-passing delivery); the claim step, which turns a
seen id away, defers or drops a held one, and takes a free
or dead one; the record decision, which resends on a digest
match and runs on a mismatch or an absence; the run and its
commit as one step, because the code puts no decision
between the stash and the cache commit that another
handling could interpose on; and the release of an untaken
path in the finally span. Against that skeleton stand the
four events that are not handlings: a crash (or restart)
between a run and its record, a death after the claim, the
cache entry expiring while the record stands, and the
record expiring after it.

The claim's space is priced, not assumed away. Executions
are counted per digest class; the invariant `P5Inv` allows
each class one execution, plus one per window event that
buys one for it: a crash after that class's run, the
record's expiry for either class, and — for the other class
only — the cache's expiry while the record stood, which is
the one event that lets a different job under the id reach
its own first run. Window events are bounded at one per
kind (one crash per class, one expiry per layer). The
purchase arithmetic is linear — each event buys at most
one — so a second event of a kind would repeat a shape
already exhibited at a larger count, not a new one; the
bound is stated here because the check's exhaustiveness
holds inside it.

Two fidelity invariants ride with the claim.
`SeenImpliesRecord`: the cache is only ever committed
beside a record — the stash is written first, in the same
locked span, and the resend path commits an id whose record
already stands — so no state has a seen id with nothing
behind it. `DeliveredImpliesRecord`: a delivery exists only
for a job that was recorded, and the record's later expiry
does not un-deliver it.

## What was checked

TLC 2.19 (the `v1.7.4` tools jar) on Java 21, the same
tooling `stage2.md` and the earlier stage 4 records use.
Each run is exhaustive inside the bound stated above. Trace
output TLC writes beside the model (`*_TTrace_*`, `states/`)
is run debris and is removed, not committed.

| Configuration | File | Invariants | Result | Generated | Distinct |
|---|---|---|---|---:|---:|
| Full replay shape | `Replay.cfg` | `P5Inv`, `SeenImpliesRecord`, `DeliveredImpliesRecord` | holds | 6,705 | 1,792 |
| First-execution witness | `ReplayWitnessExec.cfg` | `NothingExecutes` | fails, as expected | 96 | 58 |
| Resend witness | `ReplayWitnessResend.cfg` | `NeverAnswered` | fails, as expected | 840 | 328 |

The depth of the main search is 21 — arrival, claim,
decision, run, and the window events, interleaved for two
handlings, with room for a full second life of the id after
its record expires. The fingerprint collision estimate TLC
printed for the main run was 4.8E-13 optimistic. The witness
runs stop at their counterexamples, so their counts are the
states searched up to the exhibited trace.

The space is small next to the gate model's millions, and
the reason is the shape of the claim: there is one initial
state, two handlings, and two digest classes, and everything
the property turns on is the order in which a handful of
disk facts change. What the search buys is not breadth of
inputs — P1 owns the inputs — but every interleaving of
those changes: both race orders at the claim, the steal
before and after a record exists, the crash at each point it
can fall, and each expiry in each position the retentions
allow.

To re-run from a bare machine: install a Java runtime
(Java 17 or later; `apt install openjdk-21-jre-headless` on
this distribution), fetch the TLA+ tools jar for `v1.7.4`
(`tla2tools.jar` from the tlaplus project's release of that
tag) into a tools directory, and from `docs/proofs/` run
`java -cp <tools>/tla2tools.jar tlc2.TLC -config <file>.cfg
Replay.tla` for each of the three configuration files.

## The two counterexamples that are supposed to exist

`ReplayWitnessExec.cfg` checks `NothingExecutes` — the
claim that no delivery of either shape ever runs. TLC's
counterexample is a handling that arrives, takes a free
claim, finds no record, and executes, at depth 5. A model
that refused or dropped everything would satisfy `P5Inv`
and show nothing; this is the evidence that the state space
contains the first execution the property exists to bound.

`ReplayWitnessResend.cfg` checks `NeverAnswered` — the
claim that no duplicate is ever answered from the record.
Answering happens at exactly one place in the model, the
resend branch of the record decision, which requires a
standing record and no cache entry; TLC's counterexample is
therefore forced through it, and it is the clause 5 trace at
depth 10: a run commits its record, the cache entry ages
out while the record stands, the same job is delivered
again, takes the claim, and is answered from the record
with its execution count still at one.

## Findings

No replay path to a second execution was found outside the
windows the statement prices. The reads behind that verdict
are worth naming, in the order a replay would meet them: a
captured job replayed inside its freshness window meets the
cache, in memory or on disk, and is turned away; replayed
across a restart it meets the same cache reloaded; replayed
after the cache's horizon it is refused as stale at P1
step 9 before the claim is reached, because the horizon is
built from the freshness window; replayed in the narrow
band where the cache has let go and freshness still holds —
an evicted entry, a lost cache write — it meets the record,
and the digest binds the answer to its own bytes. The
cross-process race closes at the claim file, taken under
the same file lock as the cache writes, and the in-process
race at the check-and-add under the mail lock; stage 2
checked the narrow form of the second, and this stage's
model checks both halves composed. An altered body is not a
replay path: without the secret its signature fails at
P1 step 3; with the secret it is the key holder's own new
job, and clause 6 — not silence — governs it, including the
point that it cannot run at all while the cache holds the
id, and cannot be answered with the first job's result once
it does.

One observation is recorded, in the open:

- **O1. The record's digest check is skipped when the
  opinion module is absent.** `load_sent_result` computes
  the digest to compare through the opinion module
  (`_opinion.received_digest`) and, when that module is
  `None`, compares nothing: the record under the id is
  returned for any job the claim lets through. The direction
  of the error is toward answering, never toward executing —
  a different job under a reused id, in the band where the
  cache has let the id go, would be sent the first job's
  recorded result instead of running — so P5's execution
  claim is untouched, and the stash side is unaffected (the
  digest written at commit time has its own fallback
  computation in `_job_digest`). The opinion module is
  loaded unconditionally in the runner's module table, so
  the `None` case is a degraded-startup corner rather than
  a deployment shape; it is recorded because clause 5's
  binding — the answer is the job's own result or none —
  rests on the comparison, and in that corner the comparison
  does not happen. No code was changed in this pass.

## What this does not say

- Arrivals in the model are gate-passing deliveries. A
  replay that P1 refuses — stale, unsigned, over a cap —
  never reaches the claim, and this property does not
  re-check P1's steps; the properties compose by position,
  as P4 composes with P1. In particular the clause 8
  argument — the cache outlasts freshness — is an argument
  about two code values (C12 and C23), pinned in the test,
  not a model state.
- The model's claim is one claim state; the code's is two
  mechanisms. Stage 3 reconciled them for the race, and this
  model inherits that reconciliation: the in-process
  check-and-add and the disk claim compose to the held/free
  distinction the invariant turns on. The one place the
  composition is load-bearing here is the steal: only the
  disk half can be stolen, and only when its holder is gone,
  which is why the model's dead claim arises from a crash
  and never from a live handling's pause.
- A crash during a run and a crash between the run and its
  stash are one event in the model, because the record
  cannot distinguish them and the property cannot either:
  both leave a run the sender saw no result for and no
  record behind. Whether the first run's side effects
  completed before the crash is the job's own concern — the
  runner's guarantee is about its executions, and a script
  that must survive being started twice across a crash must
  be written for it, as PROTOCOL.md's execution semantics
  already say of the window.
- The claim file's holder test is a pid. A pid recycled by
  the operating system while an unrelated process holds it
  makes a dead holder's claim read as live, and the steal
  waits — for that process to exit, with no age limit on a
  readable pid (C24). That is a liveness edge on recovery,
  recorded here because this stage read the rule closely; it
  cannot produce an execution, only delay one, and the
  deferred message is left unseen meanwhile, not dropped.
- Delivery's at-least-once half is checked as a mechanism,
  not modelled as a liveness property: the stash-before-send
  ordering, the resend pass, and the give-up point are code
  facts stated in clause 10 and C25, and the model's
  `delivered` marker records that a commit is the point
  after which delivery is the outbox's retryable concern.
  A temporal check that every committed record is eventually
  delivered inside its window would need the poll cycle and
  the transport in the model; neither is this property's
  shape.
- Other doors that execute work — the board's task claims,
  the local-signals path — have their own claim and
  completion machinery and are not this model. P5 is stated
  over the job door `handle_mail` serves, which is every
  transport's path for jobs; the board's at-most-once is a
  claim of PROTOCOL.md section 13 with its own record, and
  nothing here is stated about it.
