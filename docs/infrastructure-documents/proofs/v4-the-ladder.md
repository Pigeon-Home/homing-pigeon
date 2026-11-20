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

The proof's findings from F10 on, read by kind. F1 to F9
are the search's, on `v4-search.md`.

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
  cap. Past 13, no size is more than 1.62 times the size
  below it.

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
- **L9. The readers the fuzzers hold.** Written after L1 to
  L8 were measured and before this was run. The fuzz driver
  holds 30 readers to their contracts, with 1,260 seeds, and
  no input it makes is over 16,384 bytes. Each reader is
  climbed on the series from its own seeds to step 24, which
  is 46,368: the growing text is put behind a text the seed
  carries, 1 text at a time, for 4 units (a letter, a line
  end, a quote and a brace). The data inside is the driver's
  own verdict (taken, refused, or a contract broken) and the
  time. Supposed: at least 1 of the 30 is not in proportion
  past the fuzzers' ceiling. 4 of the 6 findings were a
  quantity with no law, and none of the 4 was met by the
  fuzz campaign's own runs. This seat's guess for where: a
  reader that tries a pattern over a sender's text, in the
  names, the queries or the mail path. Supposed too: no
  reader raises past its own refusal. F15's kind has been
  looked for in the gate only.

## Finding F15: a mail the gate has no answer for

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
mail with 1,200 colons in its sender's address. The 2 good
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

## J2, measured

J2 was run. J1 and J3 were not.

A deep address is not given to the library. The gate counts
in one pass, and stops at 64 colons, or 8 comments deep. Past
either bar the log's line says the sender could not be read,
and the job goes on. A good job whose sender is 1,200 colons
ran. Its exit status was 0.

A shape the library cannot follow is the other answer. A mail
of 1,000 parts inside parts makes `message_from_bytes` raise
`RecursionError` on this interpreter. The gate logs one line,
marks the message and returns. It does not run. The same mail
on a box that is already stopped is left where it is, and it
is not marked. The panic word sits in the subject, and a mail
that cannot be read has no subject the gate can see.

Five polls of one job whose sender is 1,200 colons fetched it
once and marked it once. No worker raised.

These bars are far below the raise and far above a real
address. They are a bound in the gate. No new row in the
constraint inventory.

`runner/tests/test_v4_the_answer.py` holds it.

## L1, measured

L1's figures are recorded here.

The series was counted from 0. Step 30 is 832,040. Step 31
is 1,346,269, past the cap, and it was not used.

The ratio of a step to the sum of the 2 before it, at every
step from 20 to 30:

| The quantity | The ratio there | Furthest from the table |
|--------------|----------------:|------------------------:|
| fixed | 0.50, exactly | 0 |
| in proportion to the size | 1, exactly | 0 |
| grows with the square | 1.89443 | 0.00443 from 1.89 |
| grows with the cube | 3.42705 | 0.00295 from 3.43 |

All 4 are within 0.01 of the table's numbers. That is L1's
first sentence, and it holds.

The difference test, a step's value less the 2 values
before it. A fixed 7 has difference -7 at every step from
2 to 30. A quantity of 3 per character and 5 besides has
difference -5 at every such step. Both exact, which is the
second sentence, for the first 2 kinds. A square's
difference grows at every step from 2 to 30: 0, then 2,
then 4, then 12, and on. A cube's grows too.

`runner/tests/test_v4_the_ladder.py` holds these figures.

## L2, measured

L2's figures are recorded here. The shell was not asked.
The gate was not asked.

A row's table has one entry for each of M's 4 states and
each of the 4 joiners that can stand in front of the row.
The entry says what becomes of the output still pending, what
the row itself prints, and the state it leaves. The table of
a joined row is made from the 2 tables. The atoms are not
walked again.

The rows are built from every 2 atoms, 484 pairs. Step 1 is
the first atom and step 2 is the second. The text at a step
is the text of the step before, joined to the text of the
step before that. There are 5 ways to join. 4 of them use
one joiner at every step. The fifth uses the 4 joiners in
turn, `&&` then `||` then `;` then `|`, starting at step 3.

| What was checked | The count |
|------------------|----------:|
| Rows, steps 3 to 15, 484 pairs, 5 ways | 31,460 |
| Differences between the table and M's walk | 0 |
| The longest row, in atoms | 610 |

The 22 atoms are 2 kinds, by what they do to M's state.
21 of them leave status 0 when they run. `false` leaves
status 1. Closing those 2 kinds under every joiner gives
14 kinds, and joining any 2 of the 14 gives one of the 14.
So every row, of any length, is one of the 14. The
supposition said 20 at most. The number is 14.

`runner/tests/test_v4_the_ladder.py` holds these figures.

## L3, measured

L3 was run in the shell, bash 5.2.15. The gate was not
asked. Confinement was not asked. The place is the shell's
own folder and `HOME`, which was set to `/home/pigeon-proof`.

The same 2,420 families as L2, at every step from 3 to 10.
19,360 rows, the longest 55 atoms. For each row, the
shell's output, its status, and the commands that ran.

| What was checked | Differences |
|------------------|------------:|
| The output and the status, against M | 0 |
| The commands that ran, against M | 0 |

The commands are the shell's own trace: a trap on each
command, before it runs. Three atoms trace as more than
their own text, or as a different text. `(echo a)` traces
as `echo a`. `echo $(:)` traces as itself and as `:`.
`if true; then echo a; fi` traces as `true` and as `echo a`.
An atom that M does not run leaves nothing in the trace.

The order of that trace is not a fact of M. The two sides
of a pipe are started together. On one run, 1,169 rows
traced in a different order than the walk, and on the run
before, 1,173. The same commands, in an order the shell
does not promise. The order is not claimed.

20 families were climbed to step 17, which is 1,597 atoms.
They are the first 20: `true` joined to `true`, to `:`, to
`pwd` and to `false`, in each of the 5 ways. The output,
the status and the commands: 0 differences.

`runner/tests/test_v4_the_ladder.py` holds the atoms, every
row of 2 atoms, and these 20 families at step 17. The
19,360 are the measure recorded here.

## The whole ladder, measured

The 3 sections above are Grok's seat's: L1, L2 and L3, run
while this seat ran the whole ladder. Neither seat had the
other's work. What follows is this seat's run.

Run on 2026-11-19 on this seat's machine: 2 cores, bash
5.2.21, Python 3.13.18, a stack of 8 megabytes, and
confinement off, as on `v4-at-a-limit.md`. The suite is
`runner/tests/test_v4_the_ladder_run.py`. Where the whole
measure is larger than what the suite runs each time, both
counts are given.

### L1 and L2, a second time

This seat's L1 gives the same 4 ratios, and an exact
difference of its own: for 7 a character and 495 besides,
the difference is -495 at every step.

This seat's L2 was written apart from Grok's, with another
form for a row's table, and the 2 agree.

| L2 | Grok's run | This seat's run |
|----|-----------:|----------------:|
| Rows, steps 3 to 15 | 31,460 | 31,460 |
| Differences from M's walk | 0 | 0 |
| The longest row, in atoms | 610 | 610 |
| Kinds of row | 14 | 14 |

The suite asks the 2 forms the same question, the join of
every 2 atoms by every joiner entered in every way, 30,976
cases, and they give the same answer in each. It holds this
seat's rows to step 13 on every run: 26,620 rows, 0
differences.

**Every row is 1 of 14 kinds.** A row's kind is what it does
to M's state, for each of the 16 ways into it. The 22 atoms
are of 2 kinds. 2 kinds joined by any joiner give 1 of the
14, in all 784 cases, so no join leaves the 14. This is not
a sample. Every row of any length is an atom or 2 shorter
rows joined, so its kind is 1 of the 14.

A step's forecast does not walk the row. The table of step
30 of a ladder of colons, a row of 832,040 atoms, is made by
28 joins of tables.

### The shell on the ladder, L3

This is L3 a second time, and past it. Grok's L3 above ran
the 19,360 rows in bash 5.2.15, with a trap on each command
for its trace. This seat ran them in bash 5.2.21, with the
shell's own trace option. 2 shells and 2 ways to trace, and
0 differences in each. Both runs count the commands and
claim no order, for the reason Grok's section gives.

bash was run with its trace on, and the trace was counted:
which commands ran, and how many times each. Each atom has a
trace of its own, so the trace says what ran where the
output cannot. `false && : | :; :` prints nothing whatever
runs. Its trace says that the pipeline did not run and the
last colon did.

| What was run in bash | Rows | Differences in output, status or trace |
|----------------------|-----:|---------------------------------------:|
| 2,420 families, steps 3 to 10 | 19,360 | 0 |
| 20 families, steps 11 to 17 | 140 | 0 |
| The join in every case: 14 kinds, 4 joiners, 14 kinds, each of the 16 ways in | 12,544 | 0 |
| The same 12,544, with a probe behind each that reads the state the row leaves | 12,544 | 0 |
| All | 44,588 | 0 |

The longest row is step 17's: 1,597 atoms, 30,682
characters. The suite runs every 11th family, 1,760 rows,
and the 12,544.

### The bars, by rule, L4

| The ladder of colons | The data before says | The run shows |
|----------------------|----------------------|---------------|
| joined by pipes | M's result to step 18, 2,584 commands. Refused at step 19, 4,181 | the same. Halving between the 2 steps: 3,333 read, 3,334 refused |
| joined by `;`, by `&&`, by `\|\|` | M's result to step 22, 17,711 entries. Ended by a signal at step 23, 28,657 | the same on all 3: signal 11 at step 23 |

With the stack at 1 megabyte the second bar is 8 times
nearer. Steps 15 and 16 hold, and step 20 ends.

### The gate, L5 to L8

**The places.** 12, each a text a sender controls. 7 under a
good signature: the script, the subject (a word in it, in
front of it, behind it), the sender's address, a note above
the signed text and a note below it. And 5 with 1 digit of
the signature turned, so all the work is in front of the
signature: the script, the subject, the sender's address,
and the 2 notes.

**The units.** The 167 of F14's sweep, and 15 more outside
the signed text, made of JSON and of encoded words.

**2 climbs.** Every unit to step 24, which is 46,368 bytes
for a unit of 1 byte: 2,139 families. Then 14 units to the
top, 168 families: step 30 for the script, 832,040 bytes,
and step 32 elsewhere, 2,178,309. Units of 2 and 3 bytes
pass a door on the way, and there the data before says so.

| The place | Units | Ratio to step 24, lowest to highest (middle) | Ratio at the top, 14 units |
|-----------|------:|----------------------------------------------|----------------------------|
| The script | 167 | 0.66 to 0.99 (0.82) | 0.93 to 1.07 |
| The script, signature turned | 167 | 0.84 to 1.03 (0.94) | 0.84 to 1.07 |
| The subject, a word in it | 182 | 0.58 to 1.09 (0.72) | 0.95 to 1.01 |
| The subject, in front | 182 | 0.49 to 1.09 (0.61) | 0.83 to 1.01 |
| The subject, behind | 182 | 0.60 to 1.09 (0.75) | 0.81 to 1.00 |
| The sender's address | 182 | 0.61 to 0.98 (0.83) | 0.70 to 1.01 |
| A note above | 182 | 0.50 to 1.60 (0.72) | 0.81 to 1.10 |
| A note below | 182 | 0.46 to 1.06 (0.58) | 0.78 to 1.02 |
| The subject, signature turned | 182 | 0.78 to 1.20 (0.93) | 0.89 to 1.16 |
| The sender's address, signature turned | 167 | 0.81 to 1.19 (0.94) | 0.71 to 1.05 |
| A note above, signature turned | 182 | 0.85 to 1.14 (0.93) | 0.89 to 1.02 |
| A note below, signature turned | 182 | 0.86 to 1.09 (0.93) | 0.91 to 1.01 |

A ratio between 0.5 and 1 is a quantity with a fixed part
that still shows: so much a byte, and an amount besides.
Nothing reads as a square.

The 2 rows of the sender's address were climbed again with
the change that stands in the gate, which is Grok's. The
other 10 rows were climbed with this seat's own change in
its place. The 2 changes read those mails the same way.

3 readings in the table stand out, and each was run again
alone.

- **1.60, a note above.** The unit is `((`, and its top step
  took under a hundredth of a second: the clock's own noise.
  Climbed to step 32 it reads 0.87.
- **1.16, the subject.** A line end in the subject, while a
  second climb shared the machine. Alone it reads 0.99.
- **0.70 and 0.71, the sender's address.** This reading is
  real, and it is not a fault. It is the quote, and it is
  under "What the measure taught the technique" below.

**The slowest arrival under both doors** took 1.4 seconds:
2,178,309 commas in the sender's address, in front of a
signature that fails. In proportion.

**Over a door.** 50 of the 168 ladders pass a door before
the top. A script over the size door is refused by name.
A mail over the job door is refused by name too, in 0.014
to 1.05 seconds. The job door stands behind the mail's
parse, so a mail over the door still costs its parse.

**What the gate did.** At every step of every family it
decided. A good job ran. A turned signature was refused at
the signature. 14 units in the subject take the word job out
of it, and the mail is then not a job: the gate is quiet, as
for any mail that is not this runner's. 1 unit below a good
job makes the gate refuse it: the unit is the signature's
own marker, and the reader takes the last marker in the
body. That refusal is closed. Nothing runs.

**The exact counts, L7.**

| The count | On the ladder |
|-----------|---------------|
| MACs | 2 for a job that runs, 1 for a job refused at the signature. The same at every step |
| Bytes through the MAC | The difference test passes for every unit in every place: so much a byte, and a fixed amount |
| Lines logged | 5 for a job that runs, 2 for a job refused. The same at every step |
| Characters logged | Fixed for the script and the notes: 293, or 139 to 150 refused. For the subject and the sender's address it grows to a bar and stops: 559 at most, 405 refused |
| Characters given to the parser | Not on a line. The difference test fails for all 167 units in the script. Past 5,000 bytes it is in a band, from 2.31 to 3.34 times the mail |

**With F14's patterns put back as they were**, the ladder
stops itself. The 5 units that are white space with a line
end read 1.76 to 1.88. 4 stop at step 21, 21,892 bytes,
because the forecast for the next step is over the budget
of 2 seconds. The fifth, the bare line end, passes the
budget at step 22, 17,711 bytes, in 2.2 to 2.4 seconds. The
same 5 with the patterns that stand now read 0.97 to 1.02
and climb to the top.

**What it cost, L8.** The 168 families to the top took 162
seconds inside the gate. To step 30, which is what was
supposed, the slowest family took 2.8 seconds. To step 32
the slowest, commas in the sender's address, took 3.7.

### The readers the fuzzers hold, L9

**The harness.** For each of the 30 readers: up to 3 of its
own seeds, up to 8 texts in a seed, and 4 units. The growing
text is put behind the seed's text, and the reader is asked
through the driver's own check at each step to 46,368. That
is 1,600 ladders, from 81 seeds and 400 texts, and 1,169
seconds inside the readers. 10 readers were climbed inside
the driver's rig and 20 outside it. The local reader needs
the rig's folder, and it was climbed there.

| What the ladders showed | Readers |
|-------------------------|--------:|
| The time does not rise: a bar on the text stands in front of the work | 14 |
| In proportion, or a fixed part with a part in proportion | 13 |
| A square | 3 |

0 raises in the 1,600.

**The 3 with a square.**

`wire` and `cloud` read 1.55 to 1.88 for 1 unit, the brace,
and near 1 for the other 3. Both readers ask the hosted
queue's Worker for its verdict beside the runner's, and the
time is the Worker's. Asked alone, on a run of braces inside
a text of a signed job:

| Braces | Bytes | The Worker | The runner's reader |
|-------:|------:|-----------:|--------------------:|
| 10,946 | 11,179 | 0.32 s | 0.003 s |
| 28,657 | 28,890 | 1.90 s | 0.008 s |
| 75,025 | 75,258 | 11.59 s | 0.023 s |
| 121,393 | 121,626 | 21.39 s | 0.031 s |

With the signature turned the Worker takes as long, 22.4
seconds at the last row: the work is in front of its MAC.

This is not a new finding. It is the third home of F10's
search, `objectStart` in the Worker, named on
`v4-bindings.md` on 2026-11-18 as the 1 copy left open, at
the owner's word. What is new is that the ladder met it
with nobody pointing at it, and that its law is now
measured: the square. The Worker takes an envelope of up to
2,000,000 bytes. By the square a run of braces that long is
over an hour and a half of work for 1 request, and the
platform's own limit on a request is what ends it. A
request reaches the Worker only behind a tenant's bearer
token.

`secret` reads 1.83 to 1.86 for all 4 units. The check that
refuses a secret made of 1 unit repeated builds the repeat
for every length of unit: 46,368 more characters take 0.13
seconds, and 92,736 take 0.57. The text is a secret's own
holder's: the owner's in the configuration, or a sender's
in the helper. Nobody else can feed it. It is named here
and not changed.

**What was not a fault.**

- 48 ladders in `crypto` and 8 in `queries` broke a rule
  the driver keeps for its own entries: a seed that says
  which text must come back, and a cap of 1,024 on an
  entry's output. The driver said so at the first
  character. These are the harness's, not a reader's.
- `query`, `board_mail` and `v2_mail` are the slowest for
  each byte: about 2 seconds at 46,368 bytes, in
  proportion. They close and open a sealed body, and the
  cipher costs about 5 millionths of a second a byte. So a
  sealed mail at the job door takes about 22 seconds to
  open, behind its envelope's signature.
- 48 ladders in 5 readers first read above 1.35 with a top
  step under a hundredth of a second. Each was climbed on
  to step 30, 832,040 characters. The time did not rise.
  It was the clock's noise.

### Finding F15, J1 to J3

**J1, the cause.** Each bar was found by halving, with
Python's limit on calls at 1,000 and then at 3,000.

| The shape | The most taken, limit 1,000 | Limit 3,000 | Moved by | Calls a level |
|-----------|----------------------------:|------------:|---------:|--------------:|
| Colons in the sender's address | 986 | 2,986 | 2,000 | 1 |
| Comments nested in the sender's address | 494 | 1,494 | 1,000 | 2 |
| Parts nested inside parts | 981 | 2,981 | 2,000 | 1 |

This was measured from a harness 2 calls deeper than the
first figures, which is why each is 1 or 2 lower than 988,
495 and 983.

**The change that stands is Grok's**, and "J2, measured"
above is its record. 2 seats wrote a change for F15 in the
same hour. This seat's put a guard at each place that
raised. Grok's does that for the mail's shape, and for the
address it adds 2 bars of its own in front of the library:
64 colons, and 8 comments deep. Both decide all 3 shapes.
When the 2 met on the branch, this seat dropped its own, so
that the gate has 1 writer, and turned to testing Grok's.

**J2, a second seat's test.** With Grok's change, the same
5 polls over the same mailbox of 3 as before. Each mail was
fetched once and marked, and no worker raised. The middle
mail, a good job with 1,200 colons in its sender's address,
ran, under the line that says its sender could not be read.
Parts nested 1,200 deep and 20,000 deep: 1 line, marked,
nothing kept. Nested 975 deep, the library follows, and the
job runs. Each shape was also asked at every 7th count from
40 to 1,100, with a good signature and with a turned
signature: 0 raises.

**J3, the ladder again.** With Grok's change, the sender's
address was climbed again in both its places, 349 families
to step 24 and 28 to the top, and the 9 shapes of a mail
were climbed to step 22, each with a good signature and
with a turned signature. The tenth shape, colons in the
sender's address, is 1 of the 182 units. 0 raises. Before
that, with this seat's change, all 2,139 families and the
168 to the top: 0 raises.

## Conclusions, against the suppositions

- **L1 stands**, in Grok's run and in this seat's.
- **L2 stands, and the count is sharper, twice over.** 14
  kinds, where 20 at most was supposed, found by 2 seats
  apart. And the 14 are closed under the join, which is
  more than was supposed: it is a statement about every
  row, tried whole.
- **L3 stands**, in Grok's run and in this seat's: 2
  shells, 2 ways to trace. Here, 44,588 rows in bash, 0
  differences in output, status or trace.
- **L4 stands.** Both bars sit at the step the data before
  named, and halving found 3,333 again.
- **L5 stands in both parts, with its lower edge moved.**
  No unit reads above 1.35 with the change. The lowest
  reads 0.66 at step 24, under the 0.75 supposed: the fixed
  part of the gate's work still shows at 46,368 bytes. At
  the top the lowest is 0.93. Without the change the ladder
  stops itself before 22,000 bytes.
- **L6 stands for the time, and this seat's guess of the
  place was wrong.** No reader in front of the signature is
  out of proportion in any of the 12 places. The note above
  the signed text, where this seat looked for trouble,
  reads 0.81 to 1.10 at the top. What the ladder did meet
  in front of the signature was in the sender's address,
  and of another kind: F15.
- **L7 stands in 1 part.** The MAC's bytes pass the
  difference test everywhere. The parser's count does not,
  for any unit in the script. It is in a band, and the band
  is explained below.
- **L8 stands.** To step 30 the slowest family took 2.8
  seconds.
- **L9 stands, by a fault that was already known, and this
  seat's guess of the place was wrong.** 3 of the 30
  readers show a square past the fuzzers' ceiling. 2 of
  them are 1 fault, the open copy of F10's search, met
  again. The third only a secret's holder can feed. The
  readers this seat guessed, the names, the queries and
  the mail path, are in proportion or stand behind a bar.
  And no reader raised.
- **J1 stands, exactly.** Each bar moved by the calls added,
  divided by the calls its reader spends on a level.
- **J2 stands**, in Grok's run and in this seat's test of
  Grok's change.
- **J3 stands.** 0 raises.

## What the measure taught the technique

The technique set out to read 1 thing, the law a quantity
follows. The measure showed 3 things that the first form
could not read, and the audit of the branch showed a
fourth. Each is now part of it.

**1. A run that does not answer is data.** F15 is not work
that grows. It is a text for which the gate had no answer.
The ladder met it because the data inside is everything a
run shows. So at every step the ladder now asks 2 more
things than the time: did the gate decide, and was the
message marked. The count of times a message is read is a
quantity like any other, and its law is the simplest there
is. It is 1.

**2. A law can come in classes.** In the sender's address
the quote reads about 2.2, then 0.55, then 0.7, and round
again.
The cause is the count's parity. With an even count of
quotes the mail library reads them twice, once as words and
once as an address. With an odd count the last quote never
closes, no address is found, and it reads them once. The
library's own count of calls says so: 10 calls a quote when
the count is even, and 4 when it is odd.

| Quotes in the sender's address | Seconds | For each quote |
|-------------------------------:|--------:|---------------:|
| 800,000 | 0.408 | 510 billionths |
| 800,001 | 0.144 | 180 billionths |
| 1,600,000 | 0.835 | 522 billionths |
| 1,600,001 | 0.331 | 207 billionths |

Each class is in proportion. The series shows the 2 classes
by itself, because every third number of the series is even
and the 2 between are odd. A made-up quantity of 10 for an
even size and 4 for an odd size reads 2.50, 0.52 and 0.64 in
turn, which is the shape the gate showed.

So a ratio that runs in a cycle of 3 is read 3 steps apart,
where the series keeps its parity.

| The quantity | Ratio of a step to the step 3 before |
|--------------|-------------------------------------:|
| is fixed | 1.00 |
| is in proportion to the size | 4.24 |
| grows with the square | 17.94 |
| grows with the cube | 76.01 |

The quote reads 3.3 to 4.3 this way, in both classes.

**3. A count can sit in a band.** The reader that looks for
the brace that opens the signed text takes looks of 32
characters, then 128, then 512, 4 times as long each time,
before it reads the text whole. So what the parser is given
is not so much a character. It depends on where the size
falls between 2 looks: least just under a look, most just
over a look. The code as read gives the band. The looks are
from a third of the text to 4 thirds of it, and the text is
then parsed whole twice: from 2 and a third to 3 and a
third times the text. The ladder measured 2.31 to 3.34
times the mail, with the most at 32,838 bytes, just over
the look of 32,768.

`v4-before-the-mac.md` gave the parser's most as 1.42 times
the message. That was the most over its own arrivals, which
grew a note or a subject and left the signed text small. A
message that fails at the signature and whose size is in
its signed text gives the parser 3.30 times its length.
That page's supposed bound, 16 times, stands with room. Its
figure is the smaller of the 2 and is noted there.

A ladder of 50, 500 and 5,000 sees a band at 3 fixed places
and none of them is just over a look. The series' step is
1.618, which is in step with no power of 4, so its sizes
fall on every part of the band. 21 steps leave no gap wider
than 15 hundredths of a look's cycle.

**4. A reading is taken where 1 law has taken over.** It
came from the audit of the branch on 2026-11-19. The ladder
that finds F14 stops by a budget of time, and where it
stops decides what it reads. Below the size where the
square has taken over, the work is a mix: part in
proportion, part with the square. The reading of a mix is
not a law. It moves from climb to climb.

| The same ladder, the old patterns | Stops at | Reads |
|-----------------------------------|---------:|------:|
| A budget of half a second | 6,765 bytes | 1.4 to 1.7, over 6 climbs |
| A budget of 2 seconds | 17,711 bytes | 1.76 to 1.88, over 5 climbs |

A suite asked the first row for more than 1.5. The bar sat
inside the spread. Under the guard it was red in 1 run of
7, with 2 other runs on the same 2 cores, and a quiet
machine read 1.4 once in 3 climbs. The fault was in the
asking and not in the gate. So a suite asks no bar of a
reading taken in a mix. It decides by the stop, and by a
plain text climbed beside the ladder. At the step where the
old patterns stop they have taken 58 to 93 times as long as
the plain text, quiet and under load, and the suite asks
for 10.

## The technique, as any seat can run it

1. **Name the reader and the text.** 1 reader, and 1 text
   that a sender controls.
2. **Name the quantity that must have a law.** The time. A
   count of work. Bytes kept. Lines logged. Times read.
3. **Write the data before.** The doors and the bars on
   that text, as numbers: at which size is it refused, and
   by which rule.
4. **Build the text on the series.** Size 0, then 2 units,
   then each text is the 2 before it, joined.
5. **At each step, write the data ahead, and then run.**
   The forecast is the sum of the 2 quantities before, or
   the 2 results joined by rule. The data inside is what
   the run shows: the answer, the mark, the time, the
   counts, the trace.
6. **Read the step.** A ratio of 0.5 is fixed, 1 is in
   proportion, 1.9 is a square, 3.4 is a cube. An exact
   count has the difference test. A ratio that cycles is
   read 3 steps apart. A count that fails the difference
   test with a ratio near 1 is in a band: find its top.
7. **Where the data inside leaves the data ahead**, ask the
   data before. A bar that begins to bind is the answer the
   constraints already gave. If no bar explains it, it is a
   fault.
8. **A fault is repaired where it stands, and then its kind
   is asked.** That is the rule this page opens with.

The helpers are in the suite: `series`, `ratios`,
`differences`, `gate_ladder`, `reading`, and for the
operations `table_of_row`, `join` and `kinds`.

## The findings, read as techniques

| The kind of fault | Findings | The technique that looks for it on purpose | State |
|-------------------|----------|--------------------------------------------|-------|
| A quantity with no law: work or a log that grows faster than its bar or its size | F10, F12, F13, F14 | The ladder: the ratio and the difference test at every step from 0 | Built, on this page |
| A text with no answer: the gate raises, and the message is read again | F15 | The ladder's data inside, asked at every step: did it decide, was it marked. And shapes on the series, not only texts: nesting, and parts in a row | Built, on this page |
| 2 spellings of 1 text decide differently | F11 | A ladder of spellings: 1 text in each of its spellings, side by side at each step, and the answers compared | Named, not built |
| A twin that did not follow its original: 1 text read by 2 readers, and a repair made in 1 | The third home of F10's search | The ladder run on both twins side by side. The fuzz driver compares the twins' answers. The ladder compares their laws | Met in L9, not built as a rule |

## What is proven, and what is measured

**Proven, by a count that is tried whole.**

- The series' arithmetic: the 4 ratios, and the exact
  difference.
- The 14 kinds are closed under the join. So for M, every
  question about a row of any length is a question about 1
  of 14 kinds entered in 1 of 16 ways. That is 224 cases,
  whatever the size.

**Measured.**

- That the table's result is M's walk: 31,460 rows, by 2
  forms of the table written apart.
- That bash shows the table's result: 44,588 rows, with the
  join tried in every case of kinds, joiners and ways in.
- That the gate's quantities have a law in 12 places, for
  182 units, to 2,178,309 bytes.

**What the claim at every size now rests on.** The first
rung's premises, and nothing that grows.

- **P-a.** The atoms keep no state.
- **P-b.** What the shell does with the second part of a
  row depends on the first part only through M's state. The
  ladder does not prove it. It asks it where it could fail:
  at the join of every 2 kinds, in every way in, 12,544
  rows. A row that broke the claim at some great size would
  have to be made of 2 parts whose kinds were tried, joined
  by a joiner that was tried, entered in a way that was
  tried, and still differ. Then the shell depends on
  something that is not M's state. The bars are exactly
  that, and they are numbers on `v4-at-a-limit.md`.
- **P-c.** The shell has room: the row is under the bars.

A law for the gate's work cannot be proven by a clock. What
proves it is an argument about a reader's loops, and each
of the 4 repairs carries such an argument. What the ladder
does is find where an argument is missing.

## What comes next

- The ladder of spellings, for F11's kind.
- The twins side by side as a rule: the runner's reader and
  the hosted queue's, on the same texts.
- Shapes on the series inside the signed text and inside a
  sealed body, as was done for the mail's own shape.
- The shell's 2 bars, climbed with confinement on. The
  ladder's rows are measured there, on `v4-the-place.md`,
  and the writer's join on `v4-the-folder.md`.
- The join as a model for the checker: 14 kinds, 4 joiners.
- Another seat's test of F14's change, which it waits for
  before it reaches main. F15's change is Grok's, and this
  seat's ladder is its second seat's test.
- Grok's next step for F15's kind: the same sentence for
  every reader in front of the signature. It returns an
  answer on every text, and the message is marked.

## What it does not claim

- Not that a reader in proportion for 182 units in 12
  places is in proportion for every text. The units and the
  places are named so that a missing unit or place can be
  named too.
- For the readers the fuzzers hold, only 4 units and only
  46,368 characters, where the gate had 182 units and the
  top of the ladder.
- Nothing about confinement. It is off on this machine.
- Not the other kinds of message the dispatcher reads
  before their own signature checks.
- No new constraint. Time is measured here, and no bar on
  it is asked for. C1 to C31 stand as they are.
- Not that the ladder replaces the fuzzers. A fuzzer holds
  the size small and varies the shape. The ladder holds the
  shape and climbs the size. Each sees what the other
  cannot.
