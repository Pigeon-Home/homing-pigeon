# The bars: what a job can use, and what stops it

The owner asked whether the small case can be solved all
the way: scripts of at most 100 bytes, and the atomic
operations they can ask for. This page is the answer for
the shell. It solves the small case, and it says what
solved has to mean.

## In short

- **100 bytes hold the whole language.** This seat's census
  of the shell's grammar has 61 constructs. None needs more
  than 19 bytes, and any 5 of them fit in 100 bytes
  together.
- **So no cap on a script's size is a bar on what a job
  uses.** For each of 5 quantities, a script of at most 17
  bytes asks for it without end.
- **What is solved is the list of quantities, each with its
  bar.** That list is the same at 100 bytes and at
  1,048,576. A bar has no size of script in it.
- **The constraint spec has a row for 1 of these bars, in
  part.** Its 31 constraints bound what crosses the wire,
  what a job may touch and what a result may show. On how
  much a job may use it has C14 alone: a key's policy may
  cap the time that key's jobs ask for.
- **The list has holes.** Time has a bar on every system.
  Processes, memory and disk have bars on some systems, and
  none in the Linux sandbox.
- **Finding F17.** The runner holds all that a job writes
  before it cuts it: 3 bytes of the runner's own memory for
  each byte written. No system sets a bar on that.

## What solved can mean

Solved cannot mean every script. There are 256 to the
power 100 texts of 100 bytes, a number of 241 digits. And
a script of 17 bytes already runs for ever: no reader of
texts can tell, for every script, what it will do.

Solved can mean 2 things. Both are done below.

1. **The language is all there.** Every construct of the
   grammar is present at the bound, alone and together with
   others. Then a longer script brings nothing new in kind.
2. **Every quantity has a row.** A job uses up few things:
   time, output, processes, memory, disk. For each, the
   shortest script that asks for it without end, and the
   bar that stops it. Then the claim that a job stays under
   every bar has no script in it, and so no size.

This is the join once more. In `v4-the-motor.md` a longer
row needed no new proof, because every row is 1 of 14
kinds. Here a longer script needs no new proof, because a
bar does not read the script.

## The whole language is present at 100 bytes

The census follows POSIX's grammar of the shell, section
by section: 50 constructs. It adds 11 of bash's additions.
Each has a script that holds it and does nothing. The
syntax check of bash reads all 61. The syntax check of dash
reads the 50 that are POSIX's. No script on the list is
run.

| Family | Constructs | The longest of their scripts, in bytes | Used by the machine M |
|--------|-----------:|---------------------------------------:|----------------------:|
| Quoting | 3 | 5 | 2 |
| Expansion | 8 | 9 | 3 |
| Redirection | 8 | 6 | 1 |
| Simple command | 2 | 3 | 1 |
| Pipeline | 2 | 3 | 1 |
| List | 4 | 4 | 3 |
| Compound command | 7 | 17 | 2 |
| Function | 1 | 8 | 0 |
| Special built-in | 15 | 10 | 1 |
| Bash's own | 11 | 19 | 1 |
| All | 61 | 19 | 15 |

None needs more than 19 bytes: `for((;;));do :;done`, a
loop of bash's own. In POSIX's grammar the longest is 17:
`while :;do :;done`. The 5 longest, each on a line of its
own, are 91 bytes. So any 5 of them fit in 100 bytes
together. The 6 longest need 107.

**The machine M uses 15 of the 61.** Its 22 atoms and 4
joiners are built of plain commands, the colon, 2 kinds of
quotes, a parameter, a command substitution, arithmetic, a
brace expansion, 1 redirection, a subshell, `if`, and the
4 joiners. M has no loop, no function and no asynchronous
command. Nothing in M repeats. That is why every row of M
ends, and why M's proof could be about the row. What M
leaves out is what asks without end.

## No cap on a script's size is a bar

| Quantity | The shortest script found that asks for it without end | Bytes | How it grows |
|----------|--------------------------------------------------------|------:|--------------|
| Time | `while :;do :;done` | 17 | with the clock |
| Output | `yes` | 3 | with the clock: here, 851 megabytes a second |
| Processes | `f(){ f\|f&};f` | 12 | by doubling |
| Memory | `: $(yes)` | 8 | with what the shell reads: 2.8 bytes held for each byte |
| Disk | `yes>f` | 5 | with the clock |

All 5 together are 45 bytes.

**None of the 5 was run.** This seat's machine has no
sandbox that engages. The syntax checks of bash 5.2.21 and
of dash read each of them, by hand, and that check runs
nothing. The suite hands none of the 5 to a shell. It
shows that each is built only of constructs the census
reads in a form that does nothing.

**2 readings stand behind the table, both of them
bounded.** `yes` into a pipe that takes 200 megabytes and
stops: 851 megabytes a second. And bash holding a
substitution of 5, 10, 20 and 40 megabytes: 2.8 bytes of
the shell's memory for each byte read.

**The gate admits all 5 at a bound of 17 bytes**, and so
at 100, at 5,000 and at the default. C2 is a count of
bytes. It bounds what the gate must hold. It does not
bound what the script asks for.

**A reading of the text is no bar either.** The runner has
an optional reading of a job's text, the judge. The
protocol calls it a judgment and not a proof. It names 1
spelling of the script that forks without end. The 12
bytes above are another spelling, and the judge passes
them. The record says the same of 1 added space, in
`docs/steady/fuzzing.md`. A text has more spellings than a
list can hold. So a bar is set on the quantity, and never
on the text.

## The bars, system by system

Read from the running code on 19 November. The rows of the
confinement are for a runner at `enforce`.

| Quantity | Linux | FreeBSD | macOS | Windows |
|----------|-------|---------|-------|---------|
| Time | 3,600 seconds at most | the same | the same | the same |
| What a result carries | 100,000 characters for each stream | the same | the same | the same |
| What the runner holds while the job runs | no bar | no bar | no bar | no bar |
| Processes | no bar | 256: for a job's user, or for the jail on a host with RACCT | no bar | no bar |
| Memory | no bar | 512 MiB a process; 2 GiB a job on a host with RACCT | 512 MiB a process, above what it starts with | 512 MiB a process, and a job |
| Disk, the job's `/tmp` | no bar of the runner's | 512 MiB | no bar | no bar |
| Disk, the job's own folder | no bar | no bar | no bar | no bar |

4 things this table says.

- **The time bar is the sender's to move.** A job may name
  its own limit, up to 3,600 seconds. The owner's
  `default_timeout_sec`, 300, is used where a job names
  none: a default, and not a ceiling. A key's policy can
  cap that key's jobs (C14). The owner's own key has no
  policy.
- **The Linux sandbox is the barest.** It is a sandbox of
  namespaces. It sets no bar on processes, on memory or on
  the job's folder, and its `/tmp` has the kernel's own
  default. On this table the FreeBSD backend holds 4 bars
  that it does not.
- **C28 is a guard and not a bar.** When the disk is 90%
  full the runner gives up material of its own. It does
  not stop a job that is writing.
- **The constraint spec names 1 of these, in part.** C1 to
  C4 bound a job, a script, a result and a local envelope:
  what crosses the wire. C14 lets a key's policy cap the
  time its jobs ask for. C18 names the sandbox's shape,
  with a `/tmp` of no stated size. The 3,600 seconds, the
  100,000 characters and every ceiling of a confinement are
  in the code and in the manuals, and in no constraint. So
  no property and no model stands on them.

## Finding F17: the runner holds all that a job writes

**What is there.** The executor reads both of a job's
streams to their end, turns each into text, and only then
cuts each to the output cap. So the cap is a bar on what a
result carries. It is no bar on what the runner holds.

**The measure.** A job that writes a fixed number of bytes
and stops, through the real gate and the real executor,
each in a runner of its own. The sizes are steps 20 to 39
of the series. The reading is that runner's memory at its
highest, by the kernel's own high-water mark, above a
runner whose job wrote nothing. The top 4 steps:

| Bytes the job wrote | Held, in kilobytes | For each byte | Held, where the bytes are not text | For each byte |
|--------------------:|-------------------:|--------------:|-----------------------------------:|--------------:|
| 14,930,352 | 43,412 | 2.98 | 58,000 | 3.98 |
| 24,157,817 | 70,488 | 2.99 | 94,240 | 3.99 |
| 39,088,169 | 114,216 | 2.99 | 152,504 | 4.00 |
| 63,245,986 | 185,632 | 3.01 | 246,772 | 4.00 |

The law: 3 bytes held for each byte of text, and 4 for
each byte that is not text. The time the runner spends
after the job has ended grows the same way: 0.44 seconds
at the top step, and 1.01 where the bytes are not text.
The runner's log was off in these runs. With it on, the
runner does more with the same bytes.

**What it comes to.** This is arithmetic. Nothing that
writes without end was started. A writer here wrote 851
megabytes a second. At 3 bytes held for each, the runner
is asked for 2.6 gigabytes of memory a second. A machine
with 8 gigabytes has about 3 seconds. A job that names no
time limit has 300.

**Why the other bars do not stop it.** The bytes are held
by the runner, outside the confinement. A bar on a job's
memory does not count them.

**What it calls for.** A rule, and not a mend only: the
runner holds at most a fixed number of bytes of what a job
writes, on every system, whatever the job writes. It is
candidate 2 below. It is not closed here: this page
changes no running code.

## Candidates

These are candidates. They have no number in the
constraint inventory, and they are in no draft.

1. **Every bar has a row.** Each bar on what a job uses is
   a constraint, with its value, its system and its place
   in the code. Where a system has no bar, the row says
   none.
2. **The runner holds at most a fixed number of bytes of
   what a job writes.** Finding F17.
3. **A bar is set on the quantity, and never on the text.**
4. **P2, said for how much.** P2 holds the ceiling on what
   a job may touch and on what its result may show: the
   owner's configuration and the code's constants set it,
   and a job's fields can narrow it and cannot widen it.
   The same sentence, said for how much a job may use, is
   the claim that has no size in it. Today a job's field
   widens the time, from the owner's 300 seconds up to the
   code's 3,600. It would be proven a system at a time, by
   a job that reaches for each quantity and is stopped at
   its bar, inside a sandbox that engages.

## The list is not closed

The 5 quantities are the ones a short script reaches. A
kernel names more. FreeBSD's `rctl` and Linux's resource
limits each publish a list of their own, with open files,
threads and locked memory on it. The next step is to walk
each kernel's own list, and to give each entry a row: a
bar, or the word none. Until then this page claims its 7
rows and no more.

## What would show this wrong

- A construct of the shell, in POSIX's grammar or among
  bash's additions, whose shortest script is so long that
  some 5 constructs do not fit in 100 bytes.
- A bar in the running code that the table reads as none.
  The suite holds the lines the table was read from.
- A system on which a runner's memory does not grow with
  what its job writes.
- A quantity that a job can use up and that is on no
  kernel's list.

`runner/tests/test_v4_the_bars.py` holds this page.
