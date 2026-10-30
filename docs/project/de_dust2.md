# Campaign de_dust2: where the CPU goes, and where it should

<!-- Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587 -->

The conductor renamed the campaign on 29-OCT 8:21PM PST ("Change the
name of the campaign to de_dust2") and asked the audit seat the same
hour to analyze the fuzzing strategy, verify the fleet's CPU and
other resources are used effectively, and post suggestions for
feedback before deciding. This file is that analysis, from the run
ledger (`runner/tests/de_dust/runs.jsonl`, 2,855 records) as of
`56216f2a`. The tool, the corpus directory, the environment variables
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

**P9. Release on change, not on bank.** A fact for the conductor,
since the train runs on his signal: twenty releases in 24 hours,
most carrying only corpus entries, cost a tag build, a PyPI version,
a mirror push and a FULL STAMP verification each. A release when the
runner changes, or once a day, would carry the same corpus. *Who:*
the conductor's call; Grok's train. *Measure:* releases per day.

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

Decided by the audit seat on 29-OCT after Muse's feedback (the
forum, 8:29PM PST) and the conductor's "OK, implement everything"
(8:29PM PST). Landed: P1, P2, P3, P4 and P10 in the tool
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

**P7 is held.** Muse's record (the forum, 8:29PM PST) is that the
conductor ordered the ten-minute bank cadence by name for all three
rigs on 29-OCT, because the bank commits are the status he reads;
P7 would thin that cadence, and P8 takes the CI cost without
touching it. P7 comes back only if the full matrices per day stay
high with the corpus path in place, and then as a question to him.

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
  and one on `--target keydir,address,dtls --slice 600 --minutes 55`
  (two processes never share a target, since each target owns its
  corpus file); `de_dust_survivors.py` once a day in a fixed slot;
  no other grow work beside them.
- Banks at the conductor's ten-minute cadence; the hourly note by
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
