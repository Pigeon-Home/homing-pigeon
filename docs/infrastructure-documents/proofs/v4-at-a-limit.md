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
  command, and the output of every command but the last goes
  into the next command.
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
