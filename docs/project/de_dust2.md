# Campaign de_dust2: where the CPU goes, and where it should

<!-- Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587 -->

The campaign is de_dust2 from 29-OCT. I (the audit seat, stamp
`80000aeb`) wrote this file as the strategy review: where the fleet's
CPU went, where it should go, and what I changed. The numbers are
from the run ledger (`runner/tests/de_dust/runs.jsonl`, 2,855
records) as of `56216f2a`. The tool, the corpus directory, the environment variables
and the test keep their `de_dust` names: the corpus carries over and
renaming paths would break the rigs' loops for nothing. Ledger lines,
bank commits and the hourly note say de_dust2 from the switch.

Feedback goes in the forum under the note that announced this file.
After the seats have replied, the audit seat decides, the changes
land in the tool and here, and Muse runs the rigs by the "What the
rigs run" section at the end.

## 1. What the ledger says

**Yield is collapsing while spend grows.** Entries kept per CPU-hour
of grow, fleet-wide, by day:

| day | grow runs | CPU-hours | kept | arcs gained | crashes | kept per CPU-hour |
|---|---|---|---|---|---|---|
| 26-OCT | 301 | 4.5 | 99 | 196 | 1 | 22.06 |
| 27-OCT | 597 | 33.6 | 94 | 190 | 31 | 2.80 |
| 28-OCT | 482 | 35.2 | 65 | 124 | 55 | 1.84 |
| 29-OCT | 1,151 | 86.4 | 61 | 120 | 3 | 0.71 |

Spend rose twenty-fold; yield per hour fell thirty-fold. The last
24 hours filed no new crash; the three crashes the grows hit were
retired ids, which the retired list handled. Nothing is broken. The
corpus (1,534 entries over 22 targets) has saturated the mutators it
has, on the targets they reach, and the fleet is paying full price
for a plateau.

**The CPU goes where the yield is not.** The last 48 hours, per
target (CPU-hours in grows, tries per second, entries kept, arcs
gained, share of tries the reader accepted, kept per CPU-hour):

| target | CPU-h | tries/s | kept | arcs+ | accepted | kept/CPU-h |
|---|---|---|---|---|---|---|
| query | 29.75 | 12 | 3 | 5 | 52% | 0.10 |
| local | 25.08 | 17 | 89 | 178 | 1% | 3.55 |
| board_mail | 22.83 | 16 | 14 | 29 | 21% | 0.61 |
| v2_mail | 19.72 | 17 | 1 | 3 | 12% | 0.05 |
| wire | 10.21 | 44 | 2 | 6 | 51% | 0.20 |
| cloud | 5.22 | 79 | 0 | 0 | 50% | 0 |
| inbox | 4.32 | 95 | 0 | 0 | 76% | 0 |
| queries | 4.04 | 87 | 0 | 0 | 76% | 0 |
| crypto | 1.79 | 236 | 0 | 0 | 4% | 0 |
| local_inbox | 1.73 | 224 | 1 | 1 | 19% | 0.58 |
| board | 1.66 | 204 | 2 | 2 | 35% | 1.20 |
| channels | 1.25 | 225 | 0 | 0 | 41% | 0 |
| board_ops | 1.18 | 316 | 7 | 11 | 70% | 5.94 |
| stash | 0.54 | 438 | 0 | 0 | 19% | 0 |
| mail | 0.36 | 1,064 | 0 | 0 | 44% | 0 |
| collect | 0.29 | 1,204 | 4 | 8 | 26% | 13.82 |
| dtls | 0.16 | 1,835 | 0 | 0 | 32% | 0 |
| manifest | 0.16 | 2,413 | 0 | 0 | 8% | 0 |
| v2 | 0.14 | 2,845 | 0 | 0 | 9% | 0 |
| stage | 0.08 | 2,596 | 12 | 19 | 43% | 152.22 |
| secret | 0.01 | 1,078 | 0 | 0 | 58% | 0 |
| names | 0.01 | 1,129 | 0 | 0 | 31% | 0 |

Four targets took 75% of 130 CPU-hours. `query` alone took 23% and
kept three entries. `stage`, `collect` and `board_ops`, the three
highest-yield targets, together got 1.5 hours. The cause is in the
loop, not in the rigs: every target runs the same `--rounds 20000`,
and a round costs 12 ms on `query` and 0.4 ms on `v2`, so the time
a target gets per cycle differs by a factor of two hundred and the
slow targets own the day. The thin-first order (Q107) fixed which
target a cycle starts at; it did not change how long each one holds
the core.

**Most tries die at the first gate.** `local` accepts 1% of what it
is fed, `crypto` 4%, `manifest` 8%, `v2` 9%. A parent is drawn
uniformly from the corpus, and on `crypto`, `manifest` and `v2`
about three quarters of the corpus is refusal-path keepers (replayed
on `56216f2a`: 23%, 32% and 28% accepted), so most children are
refusals too, and the refusal paths saturated days ago. `steering`
leans on mutators that still find arcs; it does not choose parents,
and with no mutator keeping anything it has nothing to lean on.

**The slowest tries are findings nobody files.** The ledger records
each grow's slowest input: `v2_mail` 10,957 ms, `wire` 8,253 ms,
`cloud` 5,586 ms, `board_mail` 5,140 ms, `queries` 3,668 ms,
`query` 2,798 ms in the last 48 hours, on 16 KB inputs. Q84 (a grep
pattern that ran unbounded) was this class. The tool keeps the
number and the id and files nothing.

**The fleet is oversubscribed and duplicating.** The hourly notes
read Menlo Park at 160-200% of two cores (grow workers, the
survivors loop, the bank, the note, git) and the one-core rigs at
100-124%. Load above cores is context switching, not fuzzing. The
three rigs run the same 22-target cycle on the same merged corpus
with different seeds, so two rigs can spend the same hour on the
same target and each keep an entry for the same new arc; the bank's
union keeps both, so the duplicate work shows in the totals as
growth.

**The repository pays per bank.** 298 bank commits in the last 24
hours, most "0 crashes, 1-2 new runs" and no new entry, each one a
push, a rebase race for every other seat, and a `build.yml` run: 417
runs in the window, 103 completed full matrices (ten jobs, two of
them macOS and one Windows ARM) for commits that changed a JSON-lines
file. Twenty releases were cut in the same 24 hours, most shipping
only corpus entries.

## 2. The proposals

Ranked by expected yield per hour of work. Each names what changes,
who lands it, and how the ledger will show whether it worked.

**P1. Budget time, not rounds.** `grow` takes a per-target slice
(`--slice SECONDS`, default 120 under `--minutes`) and derives each
target's rounds from its measured tries per second over its last
five grows (`rounds = slice × tries_per_second`, clamped to
[400, 50,000]); `--rounds` stays for a fixed grow. Every target then
gets the same wall time per cycle, and a 1-core rig's 55-minute
cycle reaches all 22 targets once instead of holding on the four
slow ones. *Who:* the tool (audit seat). *Measure:* CPU-hours per
target within 2x of each other in the 48-hour table.

**P2. Tilt the slices toward yield, with a floor.** A target's slice
is `base × (1 + k × yield)` where yield is entries kept plus arcs
gained in its last five grows, `k` chosen so the best target gets at
most four slices and no target gets less than one quarter slice;
adding a seed or a mutator to a target resets its history so it
earns a full look again. *Who:* the tool. *Measure:* kept per
CPU-hour, fleet-wide, back above 2 within two days.

**P3. Choose parents by rarity and acceptance, not uniformly.** A
parent's weight is the product of (one over the number of entries
reaching its rarest arc) and (an acceptance factor: on a target
below 20% accepted, accepted parents weigh four times refused
ones). This is the AFL favored-entry rule in two terms. *Who:* the
tool. *Measure:* accepted share on `local`, `crypto`, `manifest`,
`v2` above 20%; arcs gained on those four above zero per day.

**P4. File slowness as a crash class.** A try slower than 50 times
the target's median over the grow, and slower than 500 ms, is a
`slow` crash: shrunk like any other, recorded with the time, filed
as a Q, and carried as an expected failure until the reader is
bounded (Q84's class). The first grow after this lands will file the
six inputs above. *Who:* the tool; the fixes are the desk's.
*Measure:* the `slowest_ms` column of the ledger falling under one
second on every target.

**P5. New surfaces before more rounds on old ones.** Three readers
with recent real bugs or new code and no target: (a) `address`: the
mailbox's `reply_to`, subject and job-id parsing (Q113 was found
through `cloud` by accident, in one of 1,534 entries); (b) `keydir`:
`load_key_directory`, `validate_key_directory`,
`key_directory_verdict` (landed 29-OCT, Q114, unfuzzed); (c) the DTLS
resume path with the ticket's key (Q110) as seeds on the `dtls`
target, which gained no arc in 48 hours. A new target gets the
survivors' lines as seeds on day one. *Who:* targets and seeds are
the desk's lane; the audit seat drafts (b) since it wrote the
reader. *Measure:* arcs gained on the three in their first day.

**P6. Partition the fleet by job, not by seed.** Nuremberg (1 core)
runs the breadth cycle (P1, P2 over all targets). San Francisco
(1 core) runs depth: the four slow targets only, 30-minute slices,
P3 on. Menlo Park (2 cores) runs one breadth worker and one worker
on new surfaces and the survivors instrument on a fixed daily slot,
`--jobs 2` and nothing else beside them. *Who:* Muse, by the
section below. *Measure:* each rig's load within 20% of its cores
in the hourly note, and the three rigs' kept entries not duplicating
(the bank's echo count stays at zero).

**P7. Bank when there is something to bank.** A rig banks when it
holds a kept entry, a crash or a new seed, else once an hour. The
ledger line is unchanged. *Who:* Muse's loop (`rig_bank.sh`).
*Measure:* bank commits per day under 60.

**P8. Corpus-only commits run the corpus replay only.** A push that
touches only `runner/tests/de_dust/**`, the standing orders and the
forum runs the Linux `test` job (which replays the corpus and carries
the crash probes) and skips the macOS, Windows, ARM and packaging
legs; every code, doc or release commit still runs the full matrix,
and the release gate still wants a full green build on its sha.
*Who:* the desk (CI is its lane); the audit seat drafts the
`paths-ignore` shape on request. *Measure:* completed full matrices
per day under 30.

**P9. Release on change, not on bank.** Twenty releases in 24 hours,
most carrying only corpus entries, cost a tag build, a PyPI version,
a mirror push and a FULL STAMP verification each. A release when the
runner changes, or once a day, would carry the same corpus. *Who:*
Grok's train. *Measure:* releases per day.

**P10. Report yield, not load.** The hourly note's first line becomes
entries kept and arcs gained per CPU-hour over the last 24 hours,
fleet-wide and per rig, from the ledger; "CPU on the peg" moves to
the second paragraph. `de_dust_corpus.py stats --yield` prints the
48-hour table above so any seat can read it. *Who:* the tool (the
command), Muse (the note). *Measure:* the note says a number that
moves when the strategy moves.

## 3. What is deliberately not proposed

- Renaming the tool, the directory or the test. The corpus carries
  over, and `de_dust2` is the campaign's name in prose and ledgers.
- Dropping the saturated targets. A target with zero yield keeps a
  quarter slice: a new mutator, a seed or a reader change can revive
  it, and the probe suite still replays its corpus on every leg.
- Running the survivors instrument on every cycle. It is slow and
  its value is in the lines it names; one run a day per rig is
  enough to keep the seed list honest.

## 4. The decision, and what the rigs run

I decided this on 29-OCT after Muse's feedback (the forum,
8:29PM PST). Landed: P1, P2, P3, P4 and P10 in the tool
(`--slice`, the tilt, rarity-and-acceptance parents,
`<target>.slow.jsonl`, `stats --yield`, `--target a,b,c`); P5 as
the `keydir` and `address` targets and the `dtls` core's planted
tickets with resume seeds (the dtls target went from 309 to 628
arcs at seed time); P8 as build.yml's `scope` job and
`runner/tools/ci_scope.py`; P9 as the release rule in the standing
orders. P6 as below, with Muse's two readings taken: "nothing else
beside them" means no other grow work (the note, the banks and the
liveness watch stay), and a single-homed target class is a blind
spot when its rig falls, which the liveness watch reports the hour
it happens.

**P7 is held.** The ten-minute bank cadence on all three rigs is a
standing order from 29-OCT (the bank commits are the status line
Dru reads); P7 would thin it, and P8 takes the CI cost without
touching it. P7 comes back only if the full matrices per day stay
high with the corpus path in place.

What the rigs run, from the post "de_dust2: the rigs switch" in the
forum:

- Nuremberg: `HP_DE_DUST_ARCHIVE=<archive> python
  runner/tools/rig_resources.py -- python
  runner/tools/de_dust_corpus.py grow --minutes 55 --slice 120`
  (all targets, P1, P2 and P3 on by default, `--jobs 1`).
- San Francisco: the same with `--target
  query,local,board_mail,v2_mail --slice 1800`.
- Menlo Park: two grow processes, each `--jobs 1`: one on every
  target but the new three, `--target wire,cloud,v2,crypto,local,stash,mail,board,board_ops,channels,manifest,inbox,local_inbox,secret,queries,names,query,board_mail,v2_mail,stage,collect --slice 120 --minutes 55`,
  and one on `--target keydir,address,dtls,dtls_session,dtls_hostile,race_board,race_stash,race_state --slice 600 --minutes 55`
  (two processes never share a target, since each target owns its
  corpus file); `de_dust_survivors.py` once a day in a fixed slot;
  no other grow work beside them.
- Banks at the ten-minute cadence; the hourly note by
  P10 (`stats --yield` is its first line's source); the ledger
  line, the bank's title and the note say de_dust2.

## 5. Where to read whether it worked

`python runner/tools/de_dust_corpus.py stats --yield --hours 48`:
the CPU-hours column should flatten to within 2x across targets
within a day, kept per CPU-hour should climb back above 2 within
two days, `local`, `crypto`, `manifest` and `v2` should accept more
than a fifth of their tries, the slow column should name the
inputs the ledger already saw, and `keydir`, `address` and `dtls`
should gain arcs on their first day. The hourly note's first line
is the same number for the last 24 hours.

## 6. What the first cycle taught

Written 29-OCT 10:19PM PST, for the seats that come after.

- **The switch paid in twenty minutes.** `dtls`, barren for 48
  hours, kept 17 entries and 75 arcs in two hours once its core
  held tickets; `keydir` crashed on its first grow (Q115, a real
  parity bug in a reader landed that afternoon). A new reader is
  the fuzzer's best hour.
- **The slow class filed what the ledger had carried for two
  days.** 28 records on three targets were one cause: the
  signed-object search in both verifiers walked the brace walk
  once per brace, quadratic in a nest, a day-long hold on the mail
  loop from any unauthenticated 4 MB body (Q116). One backward pass
  over suffix summaries replaced it with the same answers brace for
  brace. A measurement no rule files is not a finding.
- **Echoes come back, dated.** Rigs still on the pre-fix tree
  re-banked 123 of the retired records within the hour. Their
  `head` predates the fix, so they are echoes: `promote` retires a
  slow record that replays fast, the bank keeps a retired id out,
  nobody files one (Q108's rule, extended). A slow record from a
  head past the fix is new and is a Q.
- **Load wears a finding's clothes.** Two records banked at 190%
  load replayed under 250 ms on a quiet box; a try over the bound is
  now confirmed twice, untraced, before it is filed, and a grow
  files its five slowest only.
- **One family, one answer.** Q116, Q117 and Q118 took one fix;
  the filing shape is one Q per target per shape with the family
  named in the first and the others pointed at it.

## 7. Techniques, and how more compute joins

One tool, several techniques, one ledger. A technique is how a
target makes and judges its inputs; the corpus, the slices, the
bank and the yield table are the same for all of them.

- **Mutation, coverage-guided** (every target until 29-OCT): bytes
  or JSON mutated from a corpus, kept when they reach a new arc.
  Finds parser faults, contract breaks, leaks between views.
- **Stateful protocol scripts, in memory** (`dtls_session`): an
  entry is a script, not a message. Two clients and a server run in
  one process with fixed randomness; steps deliver, drop, duplicate,
  flip, cut and reorder the datagrams in flight, move the clock,
  rebind an address, rotate a key, resume a ticket. The invariants
  hold on any script: nothing establishes under a key the server
  does not hold, a resume names a key still in the map, nothing
  half-open outlives the give-up. Deterministic, so a keeper replays
  the same way on every box. Finds state-machine faults the
  one-datagram target cannot reach: the resume path was unreached
  for two days until a session script walked it.
- **Stateful protocol scripts against a hostile peer** (`dtls_hostile`):
  the client driven against a server that does not hold its key. The
  script delivers the keyless server's datagrams and mutates them in
  flight (flip, cut, dup, reorder, drop, inject, tick). The invariant
  is the plain one and the sound one: no key, no session -- whatever
  the server sends, the client never reaches established, never
  surfaces a server message, and raises nothing but `DtlsError`.
  (A byte-flip may be cosmetic or MAC-protected; which is the
  server's to judge, so the target does not re-judge it from
  outside -- it holds the one line that never moves.)
- **Thread interleavings** (`race_board`, `race_stash`, `race_state`):
  an entry is a set of lanes, each a list of operations, run as
  threads under a short switch interval over one shared thing.
  `race_board` runs the board (one completion per task, the file
  equals memory, the counts add up, and no lease instant handed to
  two workers). `race_stash` runs the outbox (a body stashed before
  it is sent, one delivery per stash unless an undeliver sits
  between, every record left behind reads back). `race_state` runs
  the pool's other two files: the seen file (no lost update -- every
  key a thread marked is in the file after the join) and the
  retained store (no torn read -- a record reads back as exactly
  what was written). Not deterministic by nature, so the race
  technique sits out the Windows-surface differential and the
  survivors' kill set; its proof is many schedules with no
  violation, logged run by run.

Keeping the corpus fast: `distill` trims a target's corpus to a
minimal set that still reaches every arc it reaches now (seeds
pinned, then a greedy set cover over the grown entries, the smaller
entry winning a tie). A dry run reports what it would drop and
proves the kept set covers the same arcs; `--write` rewrites the
file and logs a `distill` record. It is a maintenance pass for
whoever owns a lane, not part of a grow, and it skips the race
targets, whose arc sets are not deterministic. On the committed
corpora today it reclaims a handful of entries each (dtls, eight);
the value grows as early entries' arcs are later covered by several
others, so the CI replay does not lengthen with every bank.

Adding a technique is adding a target with a `technique` name and a
check that holds its invariants. Adding a box is adding a lane: a
`grow --minutes --slice --target <list>` with `HP_DE_DUST_RIG=<name>`
in its environment, banking through `rig_bank`. The union merge
tolerates a box that comes and goes, so a laptop, a spare VM in any
region, or a CI minute budget can each carry a lane; the cost of a
one-core VM is a few USD a month, and the whole fleet today is three
of them. The ledger is where everything lands and the only thing
that has to be read.

What the ledger now logs for the next decision: each run record
carries `technique` and `rig`; each cycling grow writes a `plan`
record (what each target was given and why) that `stats --plan`
prints; `stats --yield` prints a row per technique beside the rows
per target, with crash and slow counts. In two days the questions
are: kept per CPU-hour per technique and per rig, whether the race
lanes have logged a violation, whether the session target keeps
finding arcs, and whether the slow column stays quiet from heads
past the fix.

## 8. The slice times the reader

Written 29-OCT 11:10PM PST. Not a change to the lanes, to P7, or to
section 7. The 48-hour yield number is still what says whether the
tilt worked.

A `local` grow on 30-OCT ran 50,000 rounds in 4,856 seconds: 113 ms
a try, against a corpus median of 4.9 ms. Forty-four of those tries
were filed slow, from a head before the brace-walk fix, and they
are retired as echoes. The average is a different fact. A nest does
not slow every try. `check_local` stores a neighbor on every try
and reads the senses file whole, and on a quiet box that is 0.6 ms
with an empty store and about 18 ms at 5,000 lines. The rig keeps
one prior line after the neighbor check, enough for the next
refusal to have a store it must not touch (Q70).

A cycling grow passes the planned seconds as `--budget-sec`. Rounds
stay the estimate. When the estimate was a lie the grow stops at
the time P1 assigned. A fixed `--rounds` grow is unchanged, and the
quarter-slice floor is unchanged: the budget is the tilted slice.

A slow child discounts its parent by a quarter for the rest of that
grow, on the next draw, stacked if the parent keeps producing slow
children, and kept across the 200-try recount. The record is still
filed. The next grow starts even. A stop after a count of dry tries
is not in: it would cut the quarter slice on a fast target and
would not fire on the slow ones.

## 9. The outbox is the other race

Written 30-OCT 12:07AM PST. Not a change to the lanes' cadence, to
P7, or to section 7.

`race_board`'s first records faulted a timeout of 0. That value
reoffers at once, which is what `reoffer_expired` says and what
section 13.6's lease is. The board holds its lock across an offer,
so two workers are not dealt one open task. The checker had written
the holder down after the call returned, and a reoffer that landed
in between made the next legal offer look like a double deal. The
fault is now one `claimed_at` handed to two workers. Q119.

The worker pool's other shared files are the outbox. `race_stash`
runs stash, deliver, a failing send, undeliver and resend on a few
threads over one directory. A body that was sent was stashed. The
same key is not delivered twice unless an undeliver sits between
the two. A second stash after a delivery is the next result, so
the sent copy and the new outbox record both standing is not a
fault. Menlo Park's second process takes `race_stash` beside
`race_board`. Nuremberg already grows every target.

## 10. Hit sets follow the corpus

Written 30-OCT 12:31AM PST. Not a change to the lanes' cadence, to
the slices, or to which targets run.

A grow kept the arcs of every child it tried. The parent draw
reads only the entries still in the corpus, so the discarded
sets were pure weight: about 20 KB of RSS each, and a full slice
is tens of thousands of tries. That is the 366 MB, not the
corpus file. A child now leaves a hit set behind only when it
is kept. Before it mutates, the lane prints how many entries
it loaded, the file's size, and MemAvailable where the kernel
reports it. The floors stay the rigs'. Q120.
