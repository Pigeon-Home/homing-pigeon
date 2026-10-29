# Emergencies: the muster, the DRIs, the postmortem

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

How the seats answer when the conductor calls an emergency. Muse
proposed it in the forum after the first muster, a drill, on
28-OCT, and the seats folded their amendments in under the
conductor's standing instruction to decide what is aimed at him. It
is a working agreement among the seats, kept short on purpose, and
the conductor changes or strikes any line by saying so.

## The call

1. Only the conductor calls a muster, and only the conductor stands
   it down. His stand-down takes effect when he gives it; nothing
   waits on a seat. A seat that relays it says "at the conductor's
   word" and quotes him.
2. The call names the scope when it can. When it does not, the first
   seat to read the situation names what it sees in its muster entry,
   and the rest read that before they act.
3. From the call to the stand-down the rigs hold their bank pushes.
   The hold is the file `docs/use/muster.hold` on main (Q109): the
   seat that relays the call creates it, the seat that relays the
   stand-down deletes it, and while it stands `rig_bank` merges and
   pushes nothing and exits 75, which the rigs' loops read as retry
   next cycle. The grows keep running.
   A bank that lands mid-muster costs every other seat a rebase, and
   the rigs' grows keep running; only the push waits. The hold is the
   file `docs/use/muster.hold`: the seat that relays the call commits
   it, the seat that relays the stand-down deletes it, and while it
   stands on main `rig_bank` merges nothing, pushes nothing and exits
   75, which a rig's loop reads as retry next cycle (Q109). That holds
   when the file arrives in the very commit that refused a bank's push.

## The roll

The roll is the active rows of `docs/archive/RESEARCHER_IDENT.md`,
with Grok. A chat runs only when the conductor opens a turn in it, so
a seat with no live turn cannot hear a call: a seat with no post is
written down as "not reached", never as absent or ready. DRI functions
go to seats that keep a live session. A seat reached later runs the
steps below before anything else.

## Every seat, in this order

1. **Local.** Look, do not remember: what is running on your side,
   what is mid-flight (a watcher, a grow, a release, a push), what is
   uncommitted. Work that is not on main cannot be the cause and
   cannot be part of the fix path, so say whether there is any.
2. **Your last action.** Could it be the cause, or a casualty? Name
   its commit.
3. **Refresh.** Fetch main and read the newest forum entries and the
   status lines.
4. **The situation.** Who has posted, what state main and the build
   are in.
5. **Post.** One entry in `docs/use/.com.chat`: your status line from
   `docs/use/status.txt` as it stands now, then `ready`, then at most
   three sentences: what step 1 found, what step 2 found, and your
   two cents. The status line is the fixed part, so the timeline can
   be read from the entries without prose. Then set your line's word
   to `on:muster` until the stand-down.

A post that only says "ready" tells the conductor who is awake, not
what state anything is in. Steps 1 and 2 matter more than speed.

A muster entry counts from the moment its commit is on main, not
from when it was written. The postmortem reads committer times.

## Who owns what during an emergency

| Function | DRI |
|---|---|
| The repository and production code: declares main's state, owns the fix path | the desk, 40000e00 |
| The rigs: grows, banks, runners; holds or pauses campaign work | Muse |
| The queue and transport plane | hosting, 70000a51 |
| The record: every claim checked against the tree, the timeline kept | audit, 80000aeb |
| Independent confirmation that the trigger has cleared, said in the forum; it never delays a stand-down the conductor gives | Grok |
| The postmortem document | docs, 60000b3a |
| The response reviewed after the fact, and this plan kept current | review, 90000998 |

A DRI that does not answer the muster within five minutes is covered
by the desk, which says so in the forum.

## The close

The postmortem goes into this file, under Postmortems, newest first,
within the day: the timeline in seconds from the repository's
committer times and run records only (the audit seat's), what went
right, what changes (the docs seat writes it). A seat's own account
that cannot be checked against the tree is written down as
unverified, not dropped. A change that touches code or a test is a
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

Every seat that was reached was on main within a minute. Three of
the ten on the roll were not reached: `a0000997`, `b000092f` and
`c0000327` had no live turn when the call went out, and each ran the
steps when the conductor next opened it (the forum, 2026-10-28). Muse wrote its entry at
17:13:50, third, and landed last: its push was rejected once when
its own rig's bank landed in the same seconds, and the rebase and
retry took the rest. That is rule 3 under The call.

What went right: seven seats, one minute, every entry carrying its
stamp, no seat changing code under a call that named nothing.

What changes. None of the rules above existed when the drill ran;
these are what it taught, not marks against the seats that answered
it:

- A "ready" says who is awake, not what state anything is in, so the
  entry now carries the status line and what steps 1 and 2 found.
- A bank that landed mid-muster cost one seat a rebase: rule 3.
- The call named no scope: rule 2.
- Three seats were not reached, since a chat runs only when the
  conductor opens it: the roll section.
- Several seats wrote the plan at once. A decision aimed at the
  conductor is claimed in the forum before it is written.
