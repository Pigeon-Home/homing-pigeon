# Version 4 at a limit: the proof with the size left open

The owner's second direction of 2026-11-19, in this seat's
words. Take the proof past 50 characters. Write it so that
it holds up to a limit, and let the limit be a number that
can be moved. A limit is a horizontal bar: a quantity may
reach it and may not pass it.

`v4-at-a-bound.md` proves the claim at the first rung, 50
bytes. This page writes the same claim with the size as a
letter, N. It asks 3 things. Which parts of the proof never
used the size. Which quantities grow with the size. And
which bars a script meets as the size grows, each bar as a
number.

## In short

- **The proof does not use the size.** It is an induction on
  the atoms of a row, and it holds at every N.
- **What the size changes is the room a row needs.** A row
  can meet 6 bars as N grows, and each now has a number.
- **The first bar is at 13,332 characters on this shell**, or
  lower when the path of the job's folder is long. Under it
  the claim holds whole. The owner's rungs of 50, 500 and
  5,000 are under it.
- **Over a bar, no row was seen to get a quiet wrong
  answer.** The exit code is one that M never gives, or the
  result says the job timed out. The output cap is the 1
  bar that is quiet, and the protocol makes it so.
- **1 finding on the way, F14, closed here.** A script of
  blank lines held the gate for a time that grew with the
  square of its size: a quarter of a second at 5,000 bytes,
  14 seconds at 40,000, and by the same square hours at the
  cap.

## The claim, with N in it

N is any whole number from 1 up. The runner's
`max_script_bytes` is set to N. The atoms and the joiners
are the 22 and the 4 of the first rung, and M is the same
machine.

- **B1(N). The door.** A script of at most N bytes passes
  the size door, and a script of N + 1 bytes is refused
  there.
- **B2(N). The operations.** Every row of at most N
  characters has the result M gives it: its exit status and
  its output.
- **B3(N). The answer.** The runner returns that result: the
  exit code, and the digest of the output.
- **B4(N). The evidence.** E(N), the count of the corpus's
  scripts that are at most N bytes.

At N = 50 these are B1 to B4 of the first rung.

B2 and B3 are claimed **under the bars**: for every N at
which no row of the atoms can reach a bar other than the
size door. The bars are below. Over a bar the claim is a
different one: the row does not get a quiet wrong answer.
What it gets is said bar by bar.

## Why the proof holds at every N

The first rung's argument, written as an induction on the
number of atoms in a row. Nothing in it is a size.

- **1 atom.** The row is an atom. There are 22, and each was
  run: the shell gives each the output and the status that
  M's table holds.
- **1 atom more.** Take a row of k atoms that has M's
  result, and add 1 joiner and 1 atom. By premise P-b, what
  the shell does next depends on the row so far through 2
  facts only: the status so far, and whether the pipeline in
  hand is running. Those 2 facts are M's state. There are 4
  states, 4 joiners and 22 atoms, so 352 cases, and each was
  run: in every case the shell does what M's step says. So
  the row of k + 1 atoms has M's result.

So every row has M's result, whatever its length. The size
enters in 1 place: the shell must have the room to run the
row. The standard that the shell follows says the same of
itself. It puts no limit on the size of a command, and
leaves any limit to the system under the shell.

**P-b, said more exactly.** The shell follows 4 passages of
the standard for the shell language (POSIX, Issue 8).

- 2.9.2: a pipeline's status is the status of its last
  command, with the `pipefail` option off as it is unless a
  script sets it, and the output of every command but the
  last goes into the next command.
- 2.9.3.2: lists separated by semicolons run in order, each
  to its end before the next begins.
- 2.9.3.3 and 2.9.3.4: after `&&` the next pipeline runs
  when the status is 0, and after `||` when it is not. The 2
  have equal rank and are read from the left.

bash is not proven to follow them. It is run against them.

**A premise the first rung did not have to say, P-c.** The
shell has the room: the memory, the stack and the processes
that the row needs. At 49 characters no row needs more than
17 commands. At N it is a claim about the shell and the
machine, and it is where a bar can sit.

## What grows with N

M does not. These do. c is the length of the path of the
folder the job runs in, and h is the length of the job's
HOME.

| Quantity | At most, for a row of N characters | A row that reaches it |
|----------|-----------------------------------|-----------------------|
| Rows the atoms build | C(N), counted below | |
| Atoms in a row | (N + 2) / 3, rounded down | `:; :; :` and on |
| Commands in 1 pipeline | (N + 3) / 4, rounded down | `: \| : \| :` and on |
| Characters printed | r × (N + 2) | `pwd; pwd; pwd` and on |

r is the larger of (c + 1) / 5 and (h + 1) / 12. The first
is `pwd` with its semicolon: 5 characters of script print
the path and a line end. The second is `echo $HOME` with
its semicolon.

**Why these hold.** The shortest atom is 1 character and
the shortest joiner is 2, so k atoms need 3k - 2 characters.
The pipe is 3 characters, so k commands in a pipeline need
4k - 3. An atom of length L with the shortest joiner costs
L + 2 characters and prints at most r × (L + 2), a row
prints no more than its atoms would print apart, and a row
of N characters has N + 2 characters to spend this way.

**The count.** Write e(L) for the number of rows of exactly
L characters. A row is an atom, or a shorter row with 1
joiner and 1 atom after it. So e(L) is the number of atoms
of length L, and for each of the 88 pairs of a joiner and
an atom, e of L less the pair's length. C(N) is the sum of
e up to N. This is the first rung's count, and N is not in
it.

## The bars

A bar is a number that a quantity may reach and may not
pass. These are the bars that a row of atoms can meet as N
grows.

| Bar | Its number, by default | Who sets it |
|-----|------------------------|-------------|
| The size door | N, `max_script_bytes` | the specification |
| The job door | 4,194,304 bytes of mail, `max_job_bytes` | the runner's owner |
| The output cap | K: 100,000 characters for each stream, `max_output_bytes` | the runner's owner |
| The time limit | 300 seconds, `default_timeout_sec` | the runner's owner |
| The shell's room | not known before the measure | the shell |
| The machine's room | here, 32,017 processes and 8 megabytes of stack | the system under the shell |

The first 4 are configuration, and each is a horizontal line
at a number. The last 2 are the premise P-c. Nobody wrote
their numbers down, so they are to be found.

**The limit this page looks for.** Call N* the smallest N at
which some row of the atoms can reach a bar other than the
size door. For every N under N*, B2(N) and B3(N) hold whole:
nothing cut, nothing stopped. The owner's bar for the
specification can then be put at any number up to N*, and
the proof is the same proof.

## What was known before the suppositions

Read, and not run.

- The first rung's measure, with the counts at 500 and at
  5,000 characters: 114 digits and 1,139 digits.
- The runner's code. The size door compares the script's
  UTF-8 length with the cap. The output of a job is read to
  its end, decoded, and each stream is then cut to its first
  K characters. The digest is taken after the cut. The time
  limit stops the job's whole process tree.
- `PROTOCOL.md`, 9.1 and 9.2: the digest covers the retained
  output, each stream cut first, and the default view
  carries nothing else that is derived from the output.
- This machine: 2 processors, bash 5.2.21, 32,017 processes
  for a user, a stack of 8 megabytes.
- How bash is built, from its source as this seat remembers
  it and not from a reading today: its grammar reads a whole
  pipeline before it builds it, and its executor walks a
  list by calling itself, once for each command in the row.

## Suppositions, written before the measure

- **G1. The count.** From 500 to 5,000 characters the count
  gains 1,025 digits, 0.2278 of a digit for each character.
  Supposed at that rate: about 11,389 digits at 50,000
  characters, about 113,889 at 500,000 and about 238,842 at
  1,048,576, each within 250 digits. Supposed too: a script
  is 1 row, so the count of rows is the count of scripts.
- **G2. The formulas.** For every N from 1 to 30, over every
  row of at most N characters (3,481,245 rows at 30): the
  most atoms is (N + 2) / 3 rounded down, the most commands
  in 1 pipeline is (N + 3) / 4 rounded down, and the most
  output is never more than r × (N + 2).
- **G3. The shell at every length past 50.** Rows drawn
  evenly from all the rows of 1 exact length: 20 rows at
  every length from 50 to 500, and 1 row at every length
  from 501 to 5,000. 13,520 rows, 0 disagreements with M.
  Every row of up to 3 atoms at any length, 172,326 rows
  with the longest at 80 characters: 0 disagreements. And
  each of M's 352 steps taken as the last step of a row of
  exactly 500, of 5,000 and of 50,000 characters: 1,056
  rows, 0 disagreements.
- **G4. The shell's room.** This seat does not know that
  bash holds every row up to the cap, and supposes that it
  does not. For the row of the most atoms, a bar is supposed
  between 50,000 and 500,000 characters, where the walk of
  the list runs out of stack. For the longest pipeline a
  lower bar is supposed, between 5,000 and 50,000
  characters, where the grammar's own stack ends. Supposed
  of every such stop: it is loud. The shell ends by a
  signal, or with a status that is not M's and words on its
  error stream. M's status with a wrong output is supposed
  never to happen.
- **G5. The runner past 50.** 100 rows drawn evenly at
  exactly 500 characters, and 20 at exactly 5,000, through
  the real gate and the real execution with the size door
  set to that N: the exit code and the digest are M's on
  every one.
- **G6. The output cap.** With a short home, the first N at
  which a row prints more than K characters is supposed to
  be 5 × (K / (c + 1), rounded down) + 3: the row of `pwd`.
  At 1 character less every row's output is whole and the
  digest is M's. At that N the digest is the digest of the
  first K characters of M's output, and the exit code is
  still M's. Supposed from the code: at the default view the
  result does not say that the output was cut, and at the
  full view it does.
- **G7. The 2 doors.** At 50,000, at 500,000 and at
  1,048,576 bytes the size door admits N and refuses N + 1,
  and the bytes decide where a character is wide. A script
  whose text must be escaped is 6 times as long in the mail,
  so it is supposed to meet the job door first: a script of
  control characters is refused there from about 699,000
  bytes, a sixth of the job door's number, and under that
  the size door decides.
- **G8. The time.** Supposed in proportion to N for each
  kind of row, and slowest for the row that starts the most
  processes: pairs of commands with a pipe between them. At
  the cap that row starts about 300,000 processes. At about
  1 thousandth of a second each that is about 300 seconds.
  So the time limit and the cap are supposed to sit close
  together on this machine, and this seat does not suppose
  on which side.

B4(N) needs no supposition. The first rung counted it: 452
scripts at every N from 50 to 3,999, and 453 from 4,000 up.

## The measure

bash 5.2.21 on Linux, with 2 processors and a stack of 8
megabytes. In the shell legs a row is the only line of a
file that bash is given, as the runner gives it a job's
file, or 1 of many rows in a file, each in a subshell of its
own.

**G1. The count.** Each character multiplies the count by
1.6896, which is 0.22778 of a digit.

| N | C(N) is this many digits long |
|--:|------------------------------:|
| 49 | 11: it is 74,072,330,493 |
| 500 | 114 |
| 5,000 | 1,139 |
| 50,000 | 11,389 |
| 500,000 | 113,892 |
| 1,048,576 | 238,848 |

Every script of at most 20 characters, 18,337 of them, cuts
into atoms and joiners in 1 way. 1 atom begins another,
`echo a` in `echo a > /dev/null`, and no joiner can follow
it there.

**G2. The formulas.** Every row of at most 30 characters was
walked, 3,481,245 rows, under 3 settings of the folder and
the home. For every N from 1 to 30 the most atoms, the
longest pipeline and the most output are what the formulas
say. 0 disagreements.

**G3. The shell at every length past 50.**

| Rows run in the real shell | How many | Disagreements with M |
|----------------------------|---------:|---------------------:|
| Drawn evenly at each exact length: 20 at every length from 50 to 500, and 1 at every length from 501 to 5,000 | 13,520 | 0 |
| Every row of up to 3 atoms, at any length | 172,326 | 0 |
| Each of M's 352 steps as the last step of a row of exactly 500, of 5,000 and of 50,000 characters | 1,056 | 0 |

The longest row of 3 atoms is 80 characters, and 7,968 of
those rows are longer than the first rung let them be. The
rows drawn evenly hold from 7 to 863 atoms. The rows of
50,000 characters hold about 8,400.

**G4. The shell's room.** The rows that ask the most of the
shell, each as a file of its own.

| The row | 5,000 | 50,000 | 500,000 | 1,048,576 |
|---------|-------|--------|---------|-----------|
| The most atoms: `:; :; :` | M's result | M's result | signal 11 | signal 11 |
| `: && : && :` | M's result | M's result | signal 11 | signal 11 |
| `false \|\| false` | M's result | M's result | signal 11 | signal 11 |
| The most output: `pwd; pwd` | M's result | M's result | signal 11 | signal 11 |
| Subshells: `(echo a); (echo a)` | M's result | M's result | signal 11 | signal 11 |
| Pairs with a pipe: `: \| :; : \| :` | M's result | M's result | signal 11 | signal 11 |
| 1 pipeline: `: \| : \| :` | M's result | status 2 | status 2 | status 2 |
| Pipelines of 3,332 commands, with semicolons between | M's result | M's result | M's result | M's result |
| Drawn from all 22 atoms and all 4 joiners, in pipelines of 4 to 12 commands | M's result | M's result | M's result | M's result |

The last 2 rows stay inside the shell's 2 bars, and the real
shell ran both to their end at the cap. The first is
1,048,575 characters: 262,164 commands in 79 pipelines. The
second is exactly 1,048,576 characters: 87,515 atoms in
10,959 pipelines, and it takes 349 of M's 352 steps. It
printed 54,671 characters, and they are the characters M
says. So B2 holds at the cap for a row inside the 2 bars.

**The grammar's bar.** bash reads a pipeline of at most
3,333 commands. With a list in front of the pipeline it is
3,332. Over 7 things in front and all 22 atoms as the last
command, it was never under 3,330. The shortest row found
that bash will not read is 13,332 characters: `:; ` and a
pipeline of 3,333 commands. The row of 13,328 characters,
with 3,332, runs and has M's result.

A refused row is refused whole. bash ends with status 2 and
"syntax error near unexpected token" on its error stream,
and nothing of the row runs, not even a command that stands
in front of the pipeline.

The numbers fit a stack of 10,000 symbols in the grammar,
with 3 symbols for each command of a pipeline: 3 × 3,333 is
9,999. That is this seat's reading of the numbers, and not
a reading of the shell's source.

**The stack's bar.** With 8 megabytes of stack, the row of
colons and semicolons was held 20 times of 20 at 26,180
commands (78,538 characters), 12 times of 20 at 26,190, and
0 times of 20 at 26,210 (78,628 characters). The bar is not
sharp, which fits a stack that begins at a different
address on each run.

The numbers fit a walk of the row's list that calls itself
once for each entry of the list, a command or a whole
pipeline, and takes about 320 bytes of the stack each time.
A pipeline's length does not count: a pipeline of 3,330
commands at the head, in the middle or at the end of a list
of 26,000 entries, 91,314 characters in all, was held 6
times of 6.

The lowest row seen to end the shell is 78,486 characters,
a row that begins with `echo $(:)`. Every row tried of at
most 78,426 characters was held.

Over the bar the shell is ended by signal 11. In most runs
nothing had been printed. In some, the first commands of the
row had run and printed before the end.

The bar moves with the stack, so it is the machine's: 13,089
commands at 4 megabytes, 52,410 at 16, and 209,686 at 64.

**The machine's processes.** No row reached a limit on
processes. The shell starts a row's processes one after
another, and each ends at once. To see this bar, 3 short
rows were run as a user who may have 1 process. A command
that needs no process of its own ran. A pipe or a subshell
did not: the shell tried again for 15 seconds, wrote "fork:
Resource temporarily unavailable" on its error stream,
stopped the row there, and ended with status 254.

**Loud, every time.** 298 runs were made at the stack's
edge, on rows whose second part runs in processes of its
own. Each had M's result or was ended by signal 11. None had
M's status with another output.

**What the runner returns over these bars.** Through the
real gate and the real execution: over the grammar's bar the
exit code is 2, and at the full view the error stream holds
the shell's words. Over the stack's bar the exit code is
-11. Over the time limit, set to 1 second for this, the exit
code is -1 and the result says `timed_out`. M's exit codes
are 0 and 1.

**G5. The runner past 50.** 100 rows drawn evenly at
exactly 500 characters with the size door at 500, and 20 at
exactly 5,000 with the door at 5,000. 0 results differ from
M, in exit code or in digest. A row of 501 and a row of
5,001 are refused at the door, which names the constraint.
The runner spent 12 thousandths of a second on a job of 500
characters and 72 thousandths on a job of 5,000.

4 large rows went the same way, drawn from all 22 atoms as
in G4, with the size door at 5,000, at 50,000, at 500,000
and at 1,048,576. The last is exactly 1,048,576 characters.
On all 4 the exit code and the digest are M's. The runner
spent 56 seconds on the last.

**G6. The output cap.** In these runs the path of the job's
folder is 34 characters, so the formula says 14,288: 5 ×
2,857 + 3. The count says the same.

| N | The row of the most output prints | The digest in the result |
|--:|----------------------------------:|--------------------------|
| 14,287 | 99,995 characters | of M's whole output |
| 14,288 | 100,030 characters | of the first 100,000 characters |

The exit code is M's on both rows. At the default view no
member of the result speaks of a cut. At the full view
`stdout_truncated` is true on the second row. With the cap
set to 1,000 the same holds at 142 and 143 characters.

**G7. The 2 doors.** At 50,000, at 500,000 and at 1,048,576
bytes the size door admits N less 1 and N, and refuses N +
1 by name: "script exceeds max_script_bytes (1048577 >
1048576)". Characters of 2, 3 and 4 bytes on each side of
each N: the bytes decided all 18.

A script of control characters is admitted up to 698,986
bytes. At 698,987 the job door refuses the mail: "mail
exceeds max_job_bytes (4194305 > 4194304)". Plain text, line
ends and quotes pass at 1,048,576 bytes. This is for a mail
of 8-bit text, as the suite builds it. The encrypted form
was not measured.

**G8. The time.** Seconds for the row alone in the shell, 1
row at a time.

| N | Pipelines of 3,332 commands | Pairs with a pipe | Subshells |
|--:|----------------------------:|------------------:|----------:|
| 5,000 | 0.21 | 0.29 | 0.16 |
| 20,000 | 1.06 | 1.38 | 0.94 |
| 50,000 | 3.43 | 4.73 | 4.47 |
| 100,000 | 8.47 | 15.85 | 15.46 |
| 200,000 | 23.81 | | |
| 500,000 | 105.02 | | |
| 800,000 | 193.49 | | |
| 1,048,576 | 349.17 | | |

The pairs and the subshells go over the stack's bar at about
183,000 and 262,000 characters. Under it, the pairs row of
180,000 characters took 42.65 seconds and the subshells row
of 250,000 took 82.52. Only the first kind of row is held
all the way to the cap.

Twice the row takes from 2 to 3.5 times as long. Each
process the shell starts is a copy of a shell that holds
the whole row, so 1 process costs more as the row grows:
0.17 thousandths of a second at 5,000 characters, 0.84 at
500,000, and 1.33 at the cap.

So the time limit of 300 seconds is first reached between
800,000 characters and the cap. A row of other atoms can be
far under it at the same size: the row of 87,515 atoms above
took 59 seconds.

**B4(N). The evidence.** E(N) is flat. The corpus's 453
scripts are from 1 to 18 bytes long, but for 1 of 4,000.

| N | E(N) |
|--:|-----:|
| 1 | 3 |
| 5 | 228 |
| 10 | 440 |
| 18 to 3,999 | 452 |
| 4,000 and up | 453 |

## Conclusions against G1 to G8

- **G1 stands.** 11,389 digits at 50,000 characters, as
  supposed. 113,892 and 238,848 at the 2 rungs above, 3 and
  6 digits from the supposed figures. A script is 1 row.
- **G2 stands.** 0 disagreements over 3,481,245 rows.
- **G3 stands.** 0 disagreements on 186,902 rows.
- **G4 stands, in both places.** The pipeline's bar is at
  13,332 characters, inside the supposed 5,000 to 50,000.
  The stack's bar is near 78,500, inside the supposed 50,000
  to 500,000. Every stop that was seen was loud.
- **G5 stands.** 120 of 120, and the 4 large rows.
- **G6 stands.** With the short home of these runs the
  formula is exact, and it was run on both sides of the bar
  at 2 caps. The default view does not say that the output
  was cut, and the full view does. With a long home the
  count can put the bar a few characters lower: 14,285 for
  a path of 34 characters and a home of 80.
- **G7 stands.** The size door holds at the 3 upper rungs,
  and a script of control characters meets the job door
  first from 698,987 bytes.
- **G8 stands in 1 part and not in the other.** The time is
  not in proportion to N: twice the row takes from 2 to 3.5
  times as long. And 1 thousandth of a second for each
  process is 6 times too much for a short row. But the time
  limit and the cap do sit close on this machine. The
  slowest row that the shell holds at the cap takes 349
  seconds, and the limit is 300.

## A finding on the way: F14, a quantity with no bar

Found while the doors were being measured for G7, before
that measure was done. A script of 1,048,576 line ends and
nothing else went into the gate with a good signature, and
the gate did not come back.

**What was seen before anything here was written.** The gate
was timed on a script of blank lines at 3 sizes.

| Blank lines in the script | Seconds in the gate |
|--------------------------:|--------------------:|
| 5,000 | 0.24 |
| 20,000 | 3.65 |
| 80,000 | 54.7 |

4 times the script, 15 times the seconds. A profile at
12,000 lines put 1.38 of its 1.40 seconds in 1 place:
`script_shape` in `runner/oracle/opinion.py`, the reader
that says whether a script looks like PowerShell, bash or
plain shell. 3 of its patterns begin at the start of a line
and then take any white space, and a line end is white
space. So at every blank line the pattern runs on through
all the blank lines after it.

Then 167 units were tried, each repeated to 20,000 bytes as
the whole script: every character from 1 to 126, and 41
short texts. The gate was slow on 5: the line end alone, and
the line end with a space, a tab or a carriage return beside
it. On the other 162 it took under a quarter of a second.

**Where it stands.** Behind the signature and behind the
size door, in front of the execution. It runs for every job
that verifies and asks for a script to be run. The gate
reads the script's hints before it asks whether the opinion
is switched off, so that setting does not skip it. And no
bar covers it: the time limit is the job's, and this is the
gate's own time.

**Suppositions, written before the change and its measure.**

- **H1. The square.** The time on n blank lines is supposed
  to be about 9 billionths of a second times n times n: 14
  seconds at 40,000 lines, 35 minutes at 500,000, and 2.6
  hours at the cap. At the owner's rungs it is supposed
  harmless: nothing to see at 50 and at 500, and a quarter
  of a second at 5,000. Only the figure at 40,000 is to be
  run.
- **H2. The change.** Each of the 3 patterns is to take the
  white space of 1 line and no more. Supposed: the reader
  gives the same answer as before on every script, because a
  match that began some blank lines higher is also a match
  that begins at the start of its own line. And the time on
  blank lines is then in proportion to the script: 1,048,576
  line ends pass the gate in about 1 second.
- **H3. Nothing else in the sweep.** With the change, the
  same 167 units at 20,000 bytes and again at 200,000:
  supposed that no unit takes more than 10 times as long at
  10 times the size.

**The measure.**

Before the change, the gate on blank lines:

| Blank lines | Seconds in the gate |
|------------:|--------------------:|
| 50 | 0.002 |
| 500 | 0.004 |
| 5,000 | 0.22 |
| 40,000 | 14.0 |

The change: in `runner/oracle/opinion.py` the 3 patterns
that began a line with "any white space" now begin it with
"any white space but a line end". Nothing else moved.

The patterns as they were and as they are were both asked on
every text of up to 5 units, from 17 units that include the
line end, 5 other kinds of white space and the words the
patterns look for. That is 1,508,598 texts. The bash pattern
finds 573,043 of them and the export pattern 158,971. 0
answers differ. The corpus's 10 different scripts get the
shape they got before, and the Oracle's own 87 tests pass.

After the change, the gate on blank lines:

| Blank lines | Seconds in the gate |
|------------:|--------------------:|
| 40,000 | 0.031 |
| 200,000 | 0.15 |
| 1,048,576 | 0.80 |

The 167 units again, at 20,000 bytes and at 200,000: the
slowest at 200,000 bytes took 0.43 seconds. From the smaller
size to the larger, 8 units grew by more than 10 times, the
largest by 11.2, and none by more than 12.

**Conclusions.**

- **H1 stands.** 14.0 seconds at 40,000 lines, and a quarter
  of a second at 5,000.
- **H2 stands.** The same answers on 1,508,598 texts, and
  1,048,576 line ends pass the gate in 0.80 seconds.
- **H3 does not stand as worded.** 8 units took a little
  more than 10 times as long at 10 times the size. A square
  would be 100 times. The gate's time is in proportion to
  the script as near as a clock on a shared machine can say.

**What F14 says for the owner's direction.** At 5,000 bytes
this reader's worst case was a quarter of a second, with no
change made. At the cap, by the same square, it was hours.
A size in the specification is a bar under every reader of
the script at once, and that includes the readers nobody
has measured.

`runner/tests/test_v4_at_a_limit.py` holds the change: the
2 forms of the patterns on every text of up to 4 units, and
a script of 1,048,576 line ends through the real gate.

## The claim, with the bars written in

For any N up to the cap, and any row of the atoms of at most
N characters:

1. **The door.** The size door admits the row, and the job
   door is not reached.
2. **The operations.** If no pipeline of the row holds more
   than 3,330 commands, and the row's list holds at most
   26,000 pipelines, the shell reads the row and walks it,
   and the row has M's result. Rows of this kind were run at
   every rung up to the cap.
3. **The answer.** If the row ends inside the time limit,
   the runner returns M's exit status, and the digest of the
   first K characters of M's output.
4. **Or else, loudly.** Where 2 or 3 fails, the result
   cannot be taken for one of M's. The exit code is 2, -11
   or 254, or it is -1 and the result says the job timed
   out. M gives 0 and 1.

The numbers 3,330 and 26,000 are this shell's, with this
stack. The form of the claim is not.

## The limit, as a number

N* is the first N at which a row of the atoms can reach a
bar other than the size door. Each bar has its own first N.

| Bar | The first N at which a row can reach it | What the row gets there |
|-----|-----------------------------------------|-------------------------|
| The output cap | 5 × (K / (c + 1), rounded down) + 3. For a path of 34 characters 14,288, for 60 it is 8,198, for 99 it is 5,003 | the digest covers the first K characters |
| The shell's grammar | 13,332 | refused whole, exit code 2 |
| The shell's stack, at 8 megabytes | about 78,500 | ended by a signal, exit code -11 |
| The time limit, 300 seconds | between 800,000 and 1,048,576 | stopped, exit code -1, `timed_out` |
| The job door | not reached by a row of atoms. 698,987 bytes for a script of control characters | refused in front of the signature, by name |
| The machine's processes | not reached by a row here | stopped, exit code 254 |

So N* is the lower of 13,332 and the output cap's number.
With a path of up to 36 characters it is 13,332. With a
longer path it is the output cap's.

**For every N under N*:** every row of at most N characters
is admitted, runs to its end, in about a second on this
machine, and has M's result. The runner returns M's exit
code and the digest of M's whole output. This is B1(N) to
B3(N) with nothing cut and nothing stopped.

The output cap's formula is for a short home, as in these
runs. With a long home the count gives a number a little
under it. In every case no row of N characters is cut while
r × (N + 2) is at most K.

## The rungs now

| | 50 | 500 | 5,000 | 50,000 | 500,000 | 1,048,576 |
|---|---|---|---|---|---|---|
| Under every bar | yes | yes, with a path of at most 999 characters | yes, with a path of at most 99 characters | no: the grammar and the output cap | no: the stack too | no: the time limit too |
| The door | every length run | every length run | every length run | the edge run | the edge run | the edge run |
| The operations | every step run | 20 rows at each length from 50 | 1 row at each length from 501, and 9 kinds of row | every step at the row's end, and 9 kinds of row | 9 kinds of row | 9 kinds of row |
| The answer | every step, through the runner | 100 rows | 20 rows, and 1 large row | 1 large row | 1 large row | 1 large row |
| Corpus scripts of at most this size | 452 | 452 | 453 | 453 | 453 | 453 |

The owner's 3 rungs are under N*. The 3 rungs above them in
`goals.md` are not, and what a row meets there is now
written down.

## What is proven at any N, and how

Each line says what kind of support it has.

1. **Proven, with no size in it.** Every row has M's result
   where the shell runs it. The induction above carries it,
   on premises P-a, P-b and P-c.
2. **Counted.** C(N), the most atoms, the longest pipeline
   and the most output. This is arithmetic, and every row of
   at most 30 characters agrees with it.
3. **Run, every case, with no size in it.** The 22 atoms,
   M's 352 steps, and every row of up to 3 atoms.
4. **Run, at every length.** Rows drawn evenly at every
   length from 50 to 5,000, and each of the 352 steps at
   the end of a row of 500, of 5,000 and of 50,000
   characters. 186,902 rows past the first rung, with 0
   disagreements.
5. **Measured, each bar as a number.** 2 of the 6 were not
   written down in this tree: the shell's grammar and the
   shell's stack.
6. **Run through the runner.** Rows at 500 and at 5,000
   characters, 4 large rows up to the cap, the output cap on
   both sides, the size door at the 3 upper rungs, and a row
   over each of 4 bars.

What it rests on that it does not prove. That bash follows
the standard's 4 passages on the rows that were not run
(P-b). The bars' numbers on another build of the shell,
another stack or another machine: the suite finds the
grammar's bar again where it runs, and holds the page's
number only for the bash the page names. The signature and
the cipher, as `readme.md` assumes them. And for the runs
through the runner, a run with confinement off.

## What comes next

The first rung's list stands: atoms that write, a fuzz
target for the operations, sizes in the run log, and the
bound in the specification at the owner's order. This page
adds 3.

1. **The output cap has no row in `constraints.md`.** B3
   needs it at every N, and it is a bar like the others. It
   is offered here as a candidate constraint, with its
   formula.
2. **A proven size names its shell.** 2 bars are the
   shell's own. A line in the specification that binds N
   can say which shell the number was measured on, or bind
   the pipeline and the list as well as the size.
3. **The job door for the encrypted form.** The crossing at
   698,987 bytes is for 8-bit text. The encrypted form makes
   a longer mail, and its number is not measured.

## What this page does not claim

- That the real cap should move. Nothing here changes a
  default: `max_script_bytes` stays 1,048,576.
- That the bars' numbers hold on another shell or machine.
- That the 22 atoms are the shell. A wider list is a later
  rung, as on the first rung's page.
- That the default view's silence about a cut is a fault.
  `PROTOCOL.md` states it: that view carries nothing else
  that is derived from the output.
- That a row over a bar is harmless. It is refused, stopped
  or ended, and the result shows which.
