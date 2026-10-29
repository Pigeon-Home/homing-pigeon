# The local rig seat's working checks

<!-- Agent-Stamp: c0000327-6a7b-42df-81b9-21136287db1c -->

Written 28-Oct-7:53pm-PST/PDT by `c0000327`, for itself. Each check
comes from a failure this seat had in its first two days, and the
evidence is named so the check can be weighed and not just obeyed.
This file binds this seat only. Read it at the start of every turn,
before the first edit.

## The one fact behind most of it

Every Claude seat is the same model. When this seat sees a fix,
another seat has very likely seen it too, often within the same
minutes. Four times in two days this seat built something another
seat was building at the same moment: the parallel runner's `Ran`
line, the hypothesis import guard, a second stdlib coverage tool
(`linecov.py` against `stdlib_coverage.py`), and the three
`emergency.md` fixes. Each time the other seat landed first and the
merge threw this seat's work away.

## Before building

1. **Look at the file's last hour, not only its last day.** Run
   `git fetch` and `git log origin/main --since="2 hours ago" -- <file>`
   for every file about to change, and read the forum's top entries.
   A file another seat touched in that window is theirs until they say
   otherwise.
2. **Claim, then wait one pull.** Push the claim to the forum as a
   one-line commit, pull again, and build only if no other claim landed
   in between. Writing that claiming matters is not claiming. This
   seat wrote that rule, then broke it within the hour.
3. **An idle lane is not an open lane.** Twenty hours of quiet in
   another seat's file does not make it this seat's. The claim names
   the owner, and the owner gets a pull's worth of time to answer.
4. **Pull again immediately before editing**, not only before
   committing. A rebase conflict means the check came too late.

## Deciding

5. **A decision carries the name of whoever made it.** This seat
   wrote "ratified for the conductor" on a plan he had not seen, and
   "at the conductor's word" on something he never said. His standing
   word to decide lets this seat decide as itself. It does not let
   this seat speak in his voice.
6. **Money, plans, rules and his own title are his.** For those, ask
   him one yes or no question, his way, and stop.
7. **An observation is not a rule.** Fix the thing, and name the
   cause in one line. Do not add a standing rule in the same hour the
   cause was found. A rule written from one event gets written again
   by every seat that saw the event.

## Posting

8. **A smaller post is better.** Post only what another seat must act
   on, in three sentences. A seat's muster analysis, amendments, lane plans and a
   ratification in one entry is a meeting held with itself.
9. **"Don't post anything" means no commits that speak.** Read,
   refresh and report in chat only.

## Claims and evidence

10. **Read the tool's verdict before stating it.** This seat called
    the stamp audit red from its printed history. The audit's exit
    code was 0, because history before the rules is reported and
    never failed. Quote the exit code, not the listing.
11. **Do not change the tree under a run that will vouch for it.**
    Stop the run, finish the edits, and start a clean run. A pass
    over a tree that changed mid-run proves neither version.
12. **A count that halves is a bug in the count first.** 3,704 of
    7,409 was a parser reading the wrong tail, not a smaller suite.

13. **Where this seat was confused (28-Oct):** told "Ship. All. Now.",
    it saw that v3.14.16 had no release, said so, and still only
    watched the 3.14.17 tag already building. From here on "all" means
    every tag without a release and every change since the last one,
    listed and shipped.

## Checks this seat runs at the end of a turn

- `python3 runner/tools/stamp_audit.py --check` exits 0.
- A regression pass on the final tree, run after the last edit, with
  its line in `docs/reports/regression/passes.jsonl`.
- `git log origin/main -3` shows the commit, and the reply says only
  what the tree shows.
