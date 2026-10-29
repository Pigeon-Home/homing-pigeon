# The emergency plan

<!-- Agent-Stamp: 90000998-709f-46f5-b2bc-2c3c5cf8dc6c -->

Adopted 2026-10-28 at the conductor's word ("make decisions"), from
Muse's proposal after the first muster drill and the amendments the
audit seat and the review seat posted under it (`docs/use/.com.chat`,
2026-10-28). The conductor may change any line of it.

## The call

The conductor calls a muster and names its scope. A drill is named a
drill in the call. Only the conductor's word stands a muster down; a
seat that relays the stand-down says "at the conductor's word" in it.

## Every seat, in this order

1. **Local state.** Look, do not remember: what this seat has running
   or mid-flight (a watcher, a grow, a release, a push).
2. **Your last action.** Could it be the cause, or a casualty?
3. **Refresh.** Pull main and read the newest entries in
   `docs/use/.com.chat` and `docs/use/status.txt`.
4. **Read the situation.** Who has posted, and what state they say
   things are in.
5. **Post one entry:** stamp, ready, what step 1 found, what step 2
   found, and your two cents. Then replace your line in
   `docs/use/status.txt` with `on:muster`.

A post that only says "ready" tells the conductor who is awake, not
what state anything is in. Speed matters less than step 1 and 2.

## Who is responsible for what

| Function | Seat |
|---|---|
| The repository and production code: declares main's state, owns the fix path | the desk, `40000e00` |
| The rigs: grows, banks, runners; holds or pauses campaign work | Muse, `00000000-muse` |
| The hosted queue and the transport plane | hosting, `70000a51` |
| The record: every claim checked against the tree, and the timeline | audit, `80000aeb` |
| Independent confirmation the trigger has cleared, before a stand-down is relayed | Grok |
| The postmortem document | docs, `60000b3a` |
| The response reviewed after the fact, and this plan kept current | review, `90000998` |

## The close

A postmortem within the day, in this file's folder or the forum, timed
in seconds from commit times and run records only. A seat's own account
that cannot be checked against the tree is written down as unverified,
not dropped. The review seat reads it and amends this plan.
