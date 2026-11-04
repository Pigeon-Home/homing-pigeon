# Distill, dry run, 30-OCT 10:29PM PST

<!-- Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587 -->

`python3 runner/tools/de_dust_corpus.py distill` with no `--write`, on
main at `main`: for each target, the greedy
set cover that keeps the seeds and the fewest grown entries that
still reach every arc the corpus reaches now, and the proof that the
kept set covers the same arcs. Nothing was written. 21.7 seconds for
all targets.

Every target held every arc; no `DID NOT COVER`. 26 targets
distilled, 1,872 entries to 1,476, 396 dropped.
Skipped by design: race_board, race_stash, race_state, edge_subject (the race targets' arc sets are
not deterministic; the parity target's coverage is in the other
implementation).

| Target | Entries | Would keep | Seeds pinned | Grown kept | Dropped | Arcs held |
|---|---:|---:|---:|---:|---:|---:|
| local | 349 | 25 | 22 | 3 | 324 | 121 |
| v2 | 68 | 57 | 55 | 2 | 11 | 54 |
| manifest | 128 | 119 | 97 | 22 | 9 | 237 |
| board_mail | 99 | 90 | 75 | 15 | 9 | 615 |
| dtls | 51 | 43 | 11 | 32 | 8 | 707 |
| query | 167 | 159 | 139 | 20 | 8 | 876 |
| board_ops | 54 | 47 | 38 | 9 | 7 | 328 |
| dtls_hostile | 38 | 33 | 16 | 17 | 5 | 689 |
| crypto | 73 | 69 | 65 | 4 | 4 | 204 |
| wire | 117 | 114 | 110 | 4 | 3 | 184 |
| collect | 19 | 17 | 15 | 2 | 2 | 65 |
| cloud | 113 | 112 | 110 | 2 | 1 | 185 |
| stash | 31 | 30 | 30 | 0 | 1 | 20 |
| mail | 26 | 25 | 20 | 5 | 1 | 100 |
| board | 26 | 25 | 24 | 1 | 1 | 249 |
| queries | 105 | 104 | 100 | 4 | 1 | 380 |
| keydir | 38 | 37 | 35 | 2 | 1 | 239 |
| channels | 11 | 11 | 11 | 0 | 0 | 142 |
| inbox | 29 | 29 | 29 | 0 | 0 | 207 |
| local_inbox | 23 | 23 | 17 | 6 | 0 | 384 |
| secret | 26 | 26 | 26 | 0 | 0 | 78 |
| names | 84 | 84 | 84 | 0 | 0 | 89 |
| v2_mail | 84 | 84 | 74 | 10 | 0 | 533 |
| stage | 35 | 35 | 23 | 12 | 0 | 93 |
| address | 46 | 46 | 46 | 0 | 0 | 18 |
| dtls_session | 32 | 32 | 21 | 11 | 0 | 1144 |

The write is a corpus change the rigs read: it moves a target's
parent pool, its replay median and slow bound, and its measured rate,
so it moves what a slice spends, most of all on `local`, which
drops from 349 entries to 25. Under the measurement hold (standing
order M.8) it does not land before the lift at 31-OCT 7:00PM PST
without the owner's word, and if it lands the window restarts.
