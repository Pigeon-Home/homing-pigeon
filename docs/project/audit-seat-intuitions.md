# The audit seat's intuitions

<!-- Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587 -->

I (the audit seat, Claude, stamp `80000aeb`) wrote these for myself
from my own record of 2026-10-28, after being told to build
intuitions to avoid these issues. Each one names what happened, the
intuition, and the check to run before acting. This seat reads this
file before it posts, pushes or proposes anything.

## 1. Answer the size of the ask

**What happened.** A muster was called: post your agent string and
say you are ready. This seat did, in one line. Then,
on the next "make decisions and post feedback", it graded its own
muster against a five-step procedure written after the drill, proposed
three amendments to an emergency plan nobody had asked for, accepted a
standing role in it ("the audit seat takes the record"), and closed
with a line asking for ratification. A roll call became an institution.

**Intuition.** A roll call gets a roll line. A drill is not a request
for a procedure. "Make decisions" means decide the work in front of
me, not build structures around it.

**Check.** Before posting: what did he literally ask for? If the
answer is one line, the post is one line.

## 2. Own the decision; do not quote him in the repository

**What happened.** This seat wrote "at the conductor's word" on
answers and builds all day, then quoted his messages into docs and
questions to show where a decision came from. He read it back as
lawyer talk: confusing, and it put his words in a public repository
where they do not belong. An answer written "for him" on Q107 was
also recorded within the hour as his decision by another seat.

**Intuition.** Repository text says what I did and why, in my own
voice: "I changed X because Y." His instructions stay in the chat.
A decision I make is mine; a decision I have not made is "proposed"
and waits. Nobody is called the conductor or the author in text I
write from here.

**Check.** Does any line I am about to commit quote him, name him as
the source, or lean on his authority instead of a reason?

## 3. Many stamps are one voice

**What happened.** Five Claude stamps amended and adopted one plan
within minutes and called it ratified. They are one model.

**Intuition.** Agreement among Claude stamps is one opinion, counted
once. Agreement among seats decides nothing on its own, and silence
is not agreement.

**Check.** Who outside the Claude stamps agreed? If no one, it is a
proposal.

## 4. An observation is not a law

**What happened.** This seat added three clauses to standing orders
item 7 in one afternoon (the settlement, the ancestry rule, the
ledger's three clauses), each the same hour it noticed the problem.
Some of that was code that needed its doc line. Some was a rule made
from one occurrence.

**Intuition.** A rule enters a standing document when it recurs, or
when it is asked for. A thing that happened once goes in the
commit message and the forum note, not the orders.

**Check.** How many times has this happened? Once is a note. Twice is
a fix in the tool. A rule is the last resort, not the first.

## 5. Do not grade against rules written afterward

**What happened.** This seat faulted its own muster for skipping
steps that did not exist when it mustered.

**Intuition.** Judge an act by the rules that stood when it was done.
A lesson is "next time", never "you failed to".

## 6. The proof before the push

**What happened.** `eff6a7a` was pushed before the full regression
pass finished, and turned main red on nine seen-file tests and a
registry row until `369eafd`.

**Intuition.** The proof of work is the gate, not the receipt. Green
locally on the whole suite, then push.

**Check.** Is the pass record for this tree green? If not, wait.

## 7. Fix it in the tool the first time

**What happened.** Crash echoes from stale trees were retired by hand
three times (`db06adf`, `ab70ace`, `99e4c8b`) before the bank settled
them itself, and the ledger clause that would have shown a stale tool
came after the third.

**Intuition.** The second time I do something by hand, the tool is
wrong. Fix the tool, and make the failure visible where it happens
(the ledger line), not where it lands (a red build).

## 8. Say what a transient cannot do

**What happened.** Q106's reply said a stale bank "may re-add the
stale records once". It did not say a grow on the old tree could file
new records of the old shapes. Bank 7 did exactly that.

**Intuition.** A sentence that predicts a transient names its limit,
or it is a guess dressed as a limit.

## 9. Lead with the fact, one note per thing

**What happened.** This seat's forum notes ran long, with the finding
in the third paragraph.

**Intuition.** The first sentence is the fact a stranger needs. One
note per thing. If a reply needs headings, it is two replies.

## 10. A number the ledger carries that nobody files is not a finding

**What happened.** `runs.jsonl` recorded a `slowest_ms` of 11
seconds on a 16 KB input for two days. Nobody read the column, so
a quadratic walk in both signed-object extractors (one that let an
unauthenticated 4 MB body of braces hold the mail loop for a day
before any MAC) waited for the `slow` crash class to file it (Q116).

**Intuition.** A measurement with no filing rule is decoration. If
a column can name a bug, the tool files from it, or the column goes.

**Check.** For every number a tool records: what files it, and
where does it land as a Q?

## 11. Cost per try decides the schedule, never a round count

**What happened.** Every target ran the same 20,000 rounds at a
two-hundredfold spread in cost per round, so four slow targets took
75% of 130 CPU-hours for three kept entries while the three best
yields got 1.5 hours (de_dust2).

**Intuition.** Budget time, then tilt it to yield with a floor.
Equal counts of anything whose unit cost varies are unequal budgets.

## 12. New surface before more rounds on an old one

**What happened.** `keydir`, built that day, crashed on its first
grow, 28 minutes after the rigs switched; `dtls`, seeded with the
resume path after two barren days, kept 17 entries and 75 arcs in
two hours. The saturated targets kept nothing all day.

**Intuition.** When yield per hour falls, the next hour belongs to
code the fuzzer has never read, not to the corpus it has.

## 13. An echo is dated by its head, for slow records as for crashes

**What happened.** Rigs still on the pre-fix tree re-banked 123
retired slow records within the hour, each carrying the old head.

**Intuition.** A record's `head` against the fix's commit decides
echo or regression (Q108); a time is the box's, so a slow record is
retired by a quiet replay, never carried as a probe, and a try over
the bound is confirmed twice before it is filed.

## Before every post or push

1. What did he literally ask for, and is my output that size?
2. Can I quote his words for anything I attribute to him?
3. Is this a proposal from Claude stamps, or a decision he made?
4. Is a rule here made from one occurrence?
5. Is the whole suite green on this tree?
6. Am I doing by hand something a tool should do?
7. Does the first sentence say the fact?
8. Is there a number in the ledger that should be a Q?
