# Emergencies: the muster, the DRIs, the postmortem

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

How the seats answer when the conductor calls an emergency. Muse
proposed the plan in the forum on 2026-10-28 after the first muster,
which was a drill; this file is the plan as decided, at the
conductor's word to the docs seat to decide what is aimed at him,
with the seats' amendments folded in. The conductor can change any
line by saying so.

## The call

1. Only the conductor calls a muster, and only the conductor stands
   it down. A seat that relays a stand-down quotes his word and the
   time he gave it.
2. The call names the scope when it can. When it does not, the first
   seat to read the situation names what it sees in its muster entry,
   and the rest read that before they act.
3. From the call to the stand-down the rigs hold their bank pushes.
   A bank that lands mid-muster costs every other seat a rebase, and
   the rigs' grows keep running; only the push waits.

## Every seat, in this order

1. **Local.** What is running on your side, what is mid-flight, what
   is uncommitted.
2. **Your last action.** Could it be the cause, or a casualty? Name
   its commit.
3. **Refresh.** Fetch main and read the newest forum entries and the
   status lines.
4. **The situation.** Who has posted, what state main and the build
   are in.
5. **Post.** One entry in `docs/use/.com.chat`: your status line from
   `docs/use/status.txt` as it stands now, then `ready`, then your two
   cents in at most three sentences. The status line is the fixed
   part, so the timeline can be read from the entries without prose.

A muster entry counts from the moment its commit is on main, not
from when it was written. The postmortem reads committer times.

## Who owns what during an emergency

| Function | DRI |
|---|---|
| The repository and production code: declares main's state, owns the fix path | the desk, 40000e00 |
| The rigs: grows, banks, runners; holds or pauses campaign work | Muse |
| The queue and transport plane | hosting, 70000a51 |
| The record: every claim checked against the tree, the timeline kept | audit, 80000aeb |
| Independent confirmation that the trigger has cleared, before a stand-down is relayed | Grok |
| The postmortem document | docs, 60000b3a |
| The response reviewed after the fact | review, 90000998 |

A DRI that does not answer the muster within five minutes is covered
by the desk, which says so in the forum.

## The close

The postmortem goes into this file, under Postmortems, newest first,
within the day: the timeline in seconds from the repository's
committer times (the audit seat's), what went right, what changes
(the docs seat writes it). A change that touches code or a test is a
Q, not a line here.

## Postmortems

### 2026-10-28, the first muster (a drill)

The call went out over the agent chats at 17:13:19 PDT. Committer
times on main:

| Time | +s | Seat |
|---|---:|---|
| 17:13:43 | 24 | Muse's Germany rig banks (de_dust 55) |
| 17:13:45 | 26 | Grok, ready |
| 17:13:48 | 29 | audit, 80000aeb |
| 17:13:53 | 34 | hosting, 70000a51 |
| 17:13:58 | 39 | docs, 60000b3a |
| 17:14:03 | 44 | review, 90000998 |
| 17:14:06 | 47 | the desk, 40000e00 |
| 17:14:17 | 58 | Muse, ready |
| 17:14:43 | 84 | Grok relays the stand-down: a drill |

Every seat was on main within a minute. Muse wrote its entry at
17:13:50, third, and landed last: its push was rejected once when
its own rig's bank landed in the same seconds, and the rebase and
retry took the rest. That is rule 3 under The call.

What went right: seven seats, one minute, every entry carrying its
stamp, no seat changing code under a call that named nothing.

What changes:

- **The order of steps.** Muse's own reading is that it skipped steps
  1 and 2. So did the docs seat: it refreshed, checked for
  uncommitted work and posted, and it read only the top entry before
  posting, so step 4 was thin, and it never asked whether its last
  push could be the cause. Every seat posted "ready" without saying
  what it saw. The five steps above, with the status line as the
  fixed part of the entry, are the fix.
- **The stand-down.** Grok relayed it at +84s without quoting the
  conductor's word. It was right, and the rule now asks for the quote,
  because a stand-down is the one message that must not be a guess.
- **Banking during a muster.** Rule 3.
- **No scope.** The call said "emergency" and nothing else. Rule 2
  gives the first seat to read the situation the job of naming what
  it sees.
