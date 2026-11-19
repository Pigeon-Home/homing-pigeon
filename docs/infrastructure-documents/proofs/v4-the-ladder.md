# Version 4 on a ladder: a fault becomes a technique

The owner's direction of 2026-11-19, in this seat's words.
A fault that the proof's own measuring turns up is not only
to be repaired. It shows a way of measuring. Make that way
a technique of the proof, and carry the technique through
the whole project, toward the upper limit of the measure:
38 million security tokens.

This page takes the first such technique from finding F14.
It says how the technique came about, what it is, what it
reduces, and what was supposed before it was run.

## The rule

**A fault found in the proof's method is made into a
technique of the proof.** The fault is repaired where it
stands. Then the question is asked that the repair does not
answer: what kind of fault was it, and what measure finds
that kind on purpose, everywhere? The answer is written as
a technique, built, and run through the project.

The proof work has 5 findings so far. Read by kind:

| Finding | What it was | Found by | Its kind |
|---------|-------------|----------|----------|
| F10 | The search for the signed text read the body again from every brace: 15 seconds for 48,000 bytes, in front of the signature | the fuzz data | work that grows faster than the size |
| F11 | An id of 78 to 128 characters is refused when its subject is spelled in encoded words | the fuzz data | 2 spellings of 1 text decide differently |
| F12 | The gate's log lines grew with the message, in front of the signature | a supposition and its measure | a quantity with no bar |
| F13 | The panic step's decoder took time that grows with the square of the subject, in front of the signature | writing the model of the gate's 6 steps | work that grows faster than the size |
| F14 | The reader of a script's shape took time that grows with the square of a run of blank lines | measuring the doors at the upper rungs | work that grows faster than the size |

4 of the 5 are 1 fault seen 4 times: a quantity that the
proof needs to stay under a law, a fixed size or a size in
proportion to the input, and that nothing held to the law.
Each was met by chance, on the way to something else. The
technique on this page is the measure that looks for that
kind on purpose. F11 is of another kind, and its technique
is named at the end and not built here.

## How this came about

1. `v4-at-a-limit.md` wrote the first rung's claim with the
   size left open, and supposed that the 2 doors hold at the
   upper rungs.
2. While those doors were measured, a script of 1,048,576
   line ends went into the gate with a good signature and
   the gate did not come back. That is F14.
3. The first answer was a sweep: 167 units, each repeated to
   1 size, with a clock on the gate. It found the 5 units
   that are a line end, and no other. The reader's 3
   patterns were changed.
4. The owner's direction on hearing this: liken it to the
   Fibonacci series, starting at 0, and use it as a way of
   research. It was first carried as a search for faults at
   growing sizes. The owner set it apart from that. It is a
   technique of the proof: a way to reduce what has to be
   proven, using 3 kinds of data in turn. What the
   constraints already decide. What can be foreseen. And
   what a run shows from the inside, while it runs.
5. What follows is this seat's working out of that
   direction. The 3 kinds of data and the series are the
   owner's. The arithmetic of why the series fits is this
   seat's, and it is set out so it can be attacked.

## The series

0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144 and on. Each
number is the sum of the 2 before it. Step 30 is 832,040 and
step 31 is 1,346,269, so 31 steps pass the cap of 1,048,576.

A ladder on this series has 4 properties that a sweep at 1
size, or a ladder of 50, 500 and 5,000, does not have.

- **It starts where everything can be tried.** Size 0 is the
  empty text. The 2 ones are the 2 units a family is built
  from. Sizes 2, 3 and 5 are small enough to try every text
  there is. The owner's first rung, 50, holds the first 10
  steps.
- **Each step is made of the 2 steps before it.** The text
  at a step is the text of the step before, joined to the
  text of the step before that. So before a step is run,
  there is something to say about it: what its 2 parts did.
- **A quantity in proportion to the size obeys the series'
  own rule.** If a quantity is a fixed amount for each
  character, its value at a step is the sum of its values
  at the 2 steps before. So the forecast for a step is 1
  addition, and the measure at the step, divided by that
  sum, reads the law the quantity follows.
- **It is short.** 31 steps cover every size from 0 to the
  cap, with no size more than 1.62 times the one below it.

**The ratio, by the law a quantity follows.** Write p for
the power: the quantity grows as the size to the power p.
On the series the ratio of a step's value to the sum of the
2 before settles at 1 over (g to the power -p, plus g to
the power -2p), where g is 1.618, the golden ratio.

| The quantity | Power | Ratio on the series |
|--------------|------:|--------------------:|
| is fixed | 0 | 0.50 |
| is in proportion to the size | 1 | 1.00 |
| grows with the square | 2 | 1.89 |
| grows with the cube | 3 | 3.43 |

For a quantity that can be counted exactly there is a
sharper test. If it is so much for each character and a
fixed amount besides, then a step's value, less the 2
values before, is the same number at every step. A square
shows as a difference that grows.

## The 3 kinds of data at a step

- **The data before.** What the constraints and the counts
  decide about this size with nothing run. Is the text
  under the size door? Under the job door? How long is its
  longest pipeline, and how many entries has its list? From
  these the step's outcome is solved: admitted or refused,
  held by the shell or over 1 of its bars.
- **The data ahead.** The forecast for this step, made from
  the 2 steps before it and written down before the step is
  run. For a result, it is the 2 results joined by rule. For
  a quantity, it is the 2 quantities added.
- **The data inside.** What the run shows while it runs, and
  not only how it ends. For a row in the shell: which
  commands ran, from the shell's own trace. For a text in
  the gate: where the time went, reader by reader.

A step where the 3 agree adds nothing new to prove: its
claim is its 2 parts' claims and the joining rule. A step
where the data inside leaves the data ahead is where
something happens that the parts do not explain. The data
before says whether that is a bar beginning to bind. If no
bar explains it, it is a fault.

## What the ladder reduces

A claim about every size is reduced to 3 small ones.

1. **Size 0.** The empty text.
2. **Size 1, twice.** The 2 units.
3. **The join.** If the claim holds for a text x and for a
   text y, it holds for x joined to y.

The first 2 are small enough to try in every case. The
third is the whole weight, and the ladder is how it is
weighed: at each of the 31 steps the join of 2 texts that
were already measured is forecast, and then run.

This is the first rung's induction with 2 parts in place of
1. There, a row is a shorter row and 1 atom more. Here, a
row is 2 shorter rows. What the first form needs of the
shell, premise P-b, the second needs too: what the shell
does with the second part depends on the first part only
through M's state. The ladder does not prove P-b. It asks
it at every step, of parts that are both long.

**M joined by rule.** A row's whole effect on what follows
it can be written as a small table: for each of M's 4
states and each of the 4 joiners that may stand in front of
the row, what the row prints, and the state it leaves. The
table of a joined row is made from the 2 rows' tables with
no walk through the row. That is the data ahead for the
operations, and it is why a step's forecast costs the same
at 5 atoms and at 500,000.

## Where the ladder is run

- **The operations, B2.** Rows built on the series from
  every 2 atoms and every joiner. The data ahead is M's
  table of the joined row. The data inside is the shell's
  output, its status, and its trace of which commands ran.
- **The bars.** The same rows, climbed until the data before
  says a bar binds. This is `v4-at-a-limit.md`'s measure of
  the shell's 2 bars, made again by rule and not by search.
- **The gate's own work.** Every text a sender controls:
  the script, the subject, the sender's address, a note
  above and a note below the signed text. Each is built on
  the series from the 167 units of F14's sweep, and the gate
  is timed at each step, reader by reader. The readers in
  front of the signature are open to anyone. The readers
  behind it are open to a holder of a key.

## Suppositions, written before the measure

Nothing on the ladder was run before these were written.
Known before: F14's 3 figures and its sweep, the bars'
numbers from `v4-at-a-limit.md`, and the gate's code as read.

- **L1. The ratio table.** On made-up quantities that are
  fixed, in proportion, a square and a cube, the ratio at
  steps 20 to 30 is within 0.01 of the table's 4 numbers,
  and the difference test is exact for the first 2.
- **L2. M joins by rule.** For every 2 atoms (484 pairs)
  and each of 5 ways to join (the 4 joiners, and the 4 in
  turn), at every step from 3 to 15: the table of the
  joined row gives the result that M's walk gives. 31,460
  rows of up to 610 atoms, 0 differences. Supposed too: all
  rows, of any length, are of a small number of kinds by
  what they do to M's state, 20 at most.
- **L3. The shell on the ladder.** The same 2,420 families
  at steps 3 to 10, 19,360 rows of up to 55 atoms: the
  shell's output, its status and its trace are the data
  ahead on every row. And 20 families climbed to step 17,
  1,597 atoms: the same.
- **L4. The bars, by rule.** The ladder of colons joined by
  pipes: the data before says M's result up to step 18
  (2,584 commands) and a refusal at step 19 (4,181). The 3
  ladders of colons joined by a semicolon, by `&&` and by
  `||`: M's result up to step 22 (17,711 entries) and the
  end of the shell by a signal at step 23 (28,657). Supposed
  that the runs show exactly this, and that halving between
  the 2 steps finds the grammar's bar where it was found
  before: 3,333 commands.
- **L5. The script in the gate.** Each of the 167 units
  climbed from step 0 to step 30, 832,040 bytes. With F14's
  change in place, every unit's ratio over the steps past
  10,000 bytes is supposed between 0.75 and 1.35: in
  proportion. With the reader's patterns put back as they
  were, the 5 units that are a line end are supposed to
  show a ratio over 1.6, and the forecast is supposed to
  say, before 100,000 bytes, that the next step is over a
  budget of 2 seconds. That is the ladder finding F14 with
  nobody pointing at it.
- **L6. In front of the signature.** The subject, the
  sender's address, and a note above and below the signed
  text, on the same units to step 30. Supposed in
  proportion for all of them, with 1 doubt said here: the
  note above the signed text is searched for the brace that
  opens it, and F10 was in that search. If any reader in
  front of the signature is not in proportion, this seat
  supposes it is there.
- **L7. The exact counts.** The gate's own counts of its
  work, characters parsed and bytes put through the MAC,
  pass the difference test at every step: the same
  difference at each.
- **L8. What the ladder costs.** 1 family through the gate
  from step 0 to step 30 is supposed to take under 5
  seconds where the gate is in proportion.

## A finding on the ladder: F15, a mail the gate has no answer for

**Found by the ladder, climbing the sender's address.** At
step 17 of the ladder of colons, 1,597 of them, the gate did
not return. It raised.

**What was seen before anything here was written.** 3 shapes
of a mail make the gate raise, all in front of the
signature.

| The shape | The most the gate takes | It raises at | The mail is then |
|-----------|------------------------:|-------------:|-----------------:|
| Colons in the sender's address | 988 | 989 | about 1,400 bytes |
| Comments nested in the sender's address, `((( )))` | 495 | 496 | 1,386 bytes |
| Parts nested inside parts | 983 | 984 | 68,943 bytes |

Each is the same error, `RecursionError`. A reader in
Python's mail library calls itself once or twice for each
level, and Python stops a chain of calls at 1,000. The first
2 are raised where the gate reads the sender's address for
its log line. The third is raised by the gate's first
statement, the parse of the mail.

Nothing in the message has been judged when this happens. No
signature has been asked for, so anyone can send it. And
nothing is left behind. The gate marks a message as seen
when it decides, and here it does not decide. The runner
asks the mailbox for unseen mail, so it reads the same
message again at the next poll, and raises again.

5 whole polls were run over a mailbox of 3 mails, the middle
one with 1,200 colons in its sender's address. The 2 good
mails were fetched once each, ran, and were marked. The
middle mail was fetched 5 times and raised 5 times. It was
never marked, and each poll left 1 line in the log: "worker
raised: RecursionError".

The other units in the sender's address, and 7 other shapes
of a mail (parts in a row, headers in a row, a folded
header, a header repeated, senders in a row, the parameters
of a content type, and a body in base64), climbed to step
22, which is 17,711. The gate returned at every step, in
proportion.

**What kind of fault.** Not the kind this page set out for.
The work is small, a thousandth of a second. It is a text
for which the gate has no answer at all. So the 1 quantity
that should be 1 for every message, the number of times the
message is read, has no bar. The ladder met it because the
data inside is everything a run shows, and a raise is a
thing a run shows.

**Suppositions, written before the change and its measure.**

- **J1. The cause is depth and nothing else.** With Python's
  limit on calls raised from 1,000 to 3,000, each bar is
  supposed to move by what its reader spends on a level:
  the colons to about 2,988, the nested comments to about
  1,495, and the nested parts to about 2,983.
- **J2. The change.** A mail whose shape the library cannot
  follow is refused where it stands. For nested parts the
  gate logs 1 line, marks the message and returns. On a box
  stopped by the panic word it leaves the message as it is,
  as it leaves every other. For the address the job goes on,
  because the address is for the log only, and the log's
  line says the sender could not be read. Supposed: after
  the change the 5 polls fetch the middle mail once and mark
  it, no worker raises, and a good job with 1,200 colons in
  its sender's address runs.
- **J3. The ladder again.** With the change, every place and
  every unit of the first climb, and the 10 shapes to step
  22: supposed 0 raises.
