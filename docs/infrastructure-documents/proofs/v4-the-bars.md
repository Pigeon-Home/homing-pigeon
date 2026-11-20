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
- **Finding F17, closed on this branch.** The runner held
  all that a job wrote before it cut it: 3 bytes of the
  runner's own memory for each byte written. It holds a
  fixed number of bytes of each stream now, and every
  result is what it was. A job's share of the log is 1
  megabyte for each stream, by the owner's word, so that
  number is 1,310,720 bytes in a running runner.
- **Findings F18 and F19, open.** 2 more readers hold all
  that a process writes: the Oracle's run tool, and the
  reading of a change job's diff.

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
| What the runner holds while the job runs | 1,310,720 bytes of a stream: a job's share of the log and the tail its record leaves out. 400,004 where no log is kept | the same | the same | the same |
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

This section is the finding as it was measured, before the
reader had a bar. The 2 sections after it close it.

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
candidate 2 below. It is closed below.

## Closing F17: the rule, the model, and what is expected

This section was written and pushed before the code was
changed.

**The rule.** The runner holds at most a fixed number of
bytes of each stream of a job, whatever the job writes. And
what a result carries is what it carried before.

**The bar.** For each stream: 4 bytes for each character of
the output cap, and 4 more. A character is at most 4 bytes,
so the first characters up to the cap lie inside the bar,
whatever the bytes are, and the 4 more settle whether the
stream goes on past the cap. Where the runner keeps a log,
its record of a job's output is as large as the log may be,
so the bar is the log's size where that is the larger. It
is no new setting. It follows the 2 settings an owner
already has.

**How it is kept.** The reader reads each stream to its
end, as before. So no job waits on a pipe the runner has
left. Past the bar the reader counts what it reads and lets
it go.

**The model.** `held.tla` is the reader of 1 stream: a job
that writes, a pipe, a reader, and the result. It has a
seam, as `gate.tla` has: with the seam turned, the reader
is the reader as it was. A twin written apart from the
checker counted the model's world first: 295 distinct
states among 665 generated, to a depth of 19. TLC 2.19 then
found the same counts, with the bar and as it was.

| Configuration | The reader | The checker's word |
|---------------|------------|--------------------|
| `heldbar.cfg` | with the bar | 7 invariants hold on all 295 states |
| `heldasitwas.cfg` | as it was | the 6 that are not the bar hold |
| `heldwitnessasitwas.cfg` | as it was, asked for the bar | broken: a job writes 10 and all 10 are held, past a bar of 9 |
| `heldwitnessshortbar.cfg` | a bar of 4 under a cap of 6 | broken: a job writes 5 and its result carries 4 |

The reader as it was breaks the bar on 165 of its 295
states, and breaks nothing else. So the bar is the 1 thing
the change adds. The second witness is why the bar may not
stand under the cap.

**What is expected of the code.**

- **H1. The same result for every job.** On outputs around
  the cap, of plain text, of characters of 2, 3 and 4
  bytes, and of bytes that are not text: the same first
  characters, the same mark of a cut stream, the same exit
  code. I expect no difference on any.
- **H2. The ladder turns flat.** At its top step,
  63,245,986 bytes, the runner held 185,632 kilobytes above
  its base. I expect under 4,000, at every step.
- **H3. The time after the job turns flat.** It was 0.44
  seconds at the top step. I expect under 0.1.
- **H4. A job that its time limit ends** comes back as
  before: marked as timed out, with its first characters
  up to the cap. And the runner stays under the bar while
  it writes.
- **H5. With the log on at its default size,** the bar is
  33,816,576 bytes a stream, and the log's record of a
  stream under the bar is what it was.
- **H6. A stream over the bar** is in the log as what was
  held, less its last 65,536 characters, and the record
  says how many bytes the job wrote. The last characters
  are left out because the bar may cut a secret in 2, and
  the half that is held would not be known for a secret.
- **H7. The other 3 systems.** On macOS and FreeBSD the
  job's process is wrapped, and the wrapper lends it to the
  same reader. The Windows backend reads with a pump of its
  own, which gets a bar of its own. None of the 3 runs on
  this seat's machine. The server's legs are their measure.

## F17 closed: the measure, and what held

**What changed.** The executor read a job's 2 streams with the
standard library's `communicate()`. It reads them with a
reader of its own now: `Held`, in `runner/ops/helpers.py`. The
reader reads as that call reads: in the calling thread on
Linux, macOS and FreeBSD, and by a thread for each stream on
Windows. So it starts no thread where the call started none.
It holds the first bytes of each stream, up to the bar. Past
the bar it counts what it reads and lets it go.

**A running runner's bar is the log's.** A running runner
keeps a log. Its record of a job's output may be as large as
the log, so the log's size sets the bar: 33,816,576 bytes a
stream at the default. The 400,004 bytes of the output cap are
the bar where no log is kept. An owner who wants a lower bar
lowers `log_max_bytes`. That is no new setting.

**The measure.** As for the ladder: 1 job through the real
gate and the real executor, in a runner of its own. The
reading is that runner's memory at its highest, in kilobytes
above a runner whose job wrote nothing. The job writes
63,245,986 bytes, on 1 stream or on each of the 2.

The ladder had 2 kinds of output: text, and bytes that are not
text. This measure has 2 more: each of them behind 1 character
of 4 bytes. The runner turns a stream into text, and 1 such
character makes every character of that text 4 bytes wide in
memory. It is the costliest kind found.

With no log, and the bar at 400,004 bytes:

| The job writes | Before, on 1 stream | Now, on 1 stream | Now, on both streams |
|----------------|--------------------:|-----------------:|---------------------:|
| Text | 185,632 | 500 | 1,280 |
| Bytes that are not text | 246,772 | 1,320 | 2,964 |
| Text behind 1 character of 4 bytes | not measured | 2,164 | 4,840 |
| Not text, behind such a character | not measured | 2,092 | 4,076 |

It is flat. The costliest cell read 4,056 for a job writing
1,346,269 bytes on each stream, and 4,172 for 14,930,352. The
time the runner spends after the job has ended was 0.44
seconds for text, and 1.01 for bytes that are not text. It is
0.007 and 0.011 now.

With a log kept:

| The log's size | The job writes | On 1 stream | On both streams |
|---------------:|----------------|------------:|----------------:|
| 33,554,432, the default | Text | 164,088 | 229,096 |
|  | Bytes that are not text | 328,088 | 415,940 |
|  | Text behind 1 character of 4 bytes | 492,972 | 682,860 |
|  | Not text, behind such a character | 558,480 | 657,300 |
| 2,097,152 | Text | 10,584 | 13,776 |
|  | Bytes that are not text | 21,864 | 26,824 |
|  | Text behind 1 character of 4 bytes | 32,492 | 44,360 |
|  | Not text, behind such a character | 36,476 | 48,720 |

At the default that is 5 to 17 times the bar for 1 stream, and
up to 21 times for both. The runner turns the held bytes into
text, redacts the text and builds the log's record from it,
and each pass holds a copy of its own. It is a fixed figure
all the same. The costliest cell read 674,788 for a job
writing 40,000,000 bytes on each stream, and 673,408 for
200,000,000.

**A job that writes until its time is up.** A job wrote
300,000,000 bytes and then waited for its limit of 3 seconds,
with no log. It came back marked as timed out, and the runner
read 456 kilobytes above its base.

**What held.**

| | Supposed | Found |
|---|----------|-------|
| H1 | No difference on any job | 72 jobs around a cap of 1,000 characters, 5 at the default cap, and 5 with a log kept: 0 differ. Held |
| H2 | Under 4,000 kilobytes at every step | On the ladder's own 2 kinds, at most 1,320. Held. A kind the ladder did not have, text made wide on both streams, reads 4,840: flat, and over the 4,000 |
| H3 | Under 0.1 seconds after the job | 0.007 seconds at the top step. Held |
| H4 | Timed out, with its first characters, and the runner under the bar | So it came back, and the runner read 456 kilobytes. Held |
| H5 | The bar is 33,816,576 bytes with the log at its default, and a record under the bar is what it was | Held |
| H6 | A stream over the bar is recorded without its last 65,536 characters, and the record says what the job wrote | Held. Half a secret at the cut is not written |
| H7 | The other 3 systems | Not measured here: the server's word is under this table. Held, with 1 test of this suite to mend |

**H7, the server's word.** It was asked on the head that
carries the closing, and this paragraph was added when it
came. macOS: the whole suite is green, and so is the
backend's live proof on 2 Macs. FreeBSD: the backend's
live proof is green in 3 guests, with a job through the
runner in its jail. The suite's own leg on FreeBSD was
still running when this was written. Windows: 1 of the 2
legs is green. In the other, 1 test of this suite stopped
at a limit of its own: its helper put 57,692 characters on
a command line, and Windows takes 32,767. The reader's
other tests passed there, by threads. The backend's pumps
held the first part of a live process. And every job the 2
legs run came back. So H7 held, and that 1 test is mended
with the next change.

**4 things were not supposed.**

1. **The log's bar is the bar that counts.** H5 has it as 1
   case among others. It is the bar of every running runner.
   And the runner's memory at its highest is 5 to 21 times
   that bar, as the table shows. Both figures are fixed.
   Neither is small.
2. **The 4 bytes more settle nothing.** The section above says
   they settle whether a stream goes on past the cap. The
   reader's own count settles that: it counts every byte it
   reads, held or let go. The 4 bytes are a margin, and
   nothing rests on them.
3. **A reader made of threads leaves something behind.** The
   reader's first form read each stream by a thread on every
   system. It was set aside before it was pushed. Where
   `communicate()` starts no thread, it would have started 2
   for each job. And a job that is given up would have left a
   thread waiting on a pipe that a left-behind process holds.
   The reader as pushed reads in the calling thread there, and
   closes both pipes when a job is given up.
4. **1 character makes a whole stream wide.** The runner's
   text of a stream holds every character at the width of its
   widest. So with a log kept, plain letters behind 1
   character of 4 bytes cost 3 times what the letters cost
   alone. The ladder had no such kind, and H2 was written for
   the ladder. Every table above has it now.

**Left open.**

- **The log's share of the bar.** A job's record in the log
  could have a bar of its own, under the log's size. That
  changes what the log keeps, so it is the owner's to weigh.
- **The Windows backend's pumps.** They start with the
  process, before the executor can name its bar. So they hold
  at most 67,108,864 bytes of a stream, whatever the log's
  size. With a log set larger than that, a record on that
  backend keeps less of a stream than it did.
- **The reader's threads on Windows.** When a job is given up
  they end at their next read, as the standard library's own
  do.
- **A block longer than the tail.** The log's record of a cut
  stream leaves out its last 65,536 characters. A redaction
  that needs a block's end would still miss a longer block
  that the bar cuts. The output cap cuts a result the same
  way, before this change and after it.
- **The runner's other readers.** The runner starts other
  processes too, and reads what they write with the standard
  library's calls, which hold all of it. Most run a command
  the runner chose: its install's trials, git, its scanners.
  They are not all walked here. 2 were met that read what the
  runner did not choose: findings F18 and F19, below.
- **A second seat's test.** This closing is 1 seat's word.

## The log's share: the rule, and what is expected

This section was written and pushed before the code was
changed. It takes up the first of the things left open
above.

**The owner's word, 20 November.** A job's share of the log
is 1 megabyte for each of its streams.

**The rule.** The log's record of a job carries a stream
whole where the stream is at most 1,048,576 bytes. Of a
longer stream it carries the first 1,048,576 bytes at
least, and the first 1,048,576 characters at most. Where it
leaves some of a stream out, it says that it is the first
part. Where the log itself is smaller than the share, the
log's size is the share, as it was.

**The bar that follows.** The runner holds the share of a
stream, and the tail that the record leaves out: 1,310,720
bytes a stream, where it was 33,816,576. The bar never
stands under what the output cap needs, so a result is
what it was. The share is a constant in the code. It is no
new setting.

**What is expected.**

- **L1. The bar.** 1,310,720 bytes a stream at the default
  log size, and at any log of 1,048,576 bytes or more. For
  a smaller log, what it was.
- **L2. The runner's memory.** For the costliest kind of
  output found, the table above reads 682,860 kilobytes. I
  expect about 35,000, and under 50,000. For plain text on
  1 stream it reads 164,088. I expect under 10,000.
- **L3. Every result is what it was.** The same jobs
  again: 0 differ.
- **L4. A stream of at most 1,048,576 bytes** is in the
  log whole, byte for byte as before.
- **L5. A longer stream** is in the log as its first
  1,048,576 bytes at least and its first 1,048,576
  characters at most. The record says that it is the first
  part, and how many bytes the job wrote. A secret that
  the share's cut falls in is written as its mark, or as
  part of its mark, and never as the secret.
- **L6. What 1 job adds to the log.** A job that wrote
  63,245,986 bytes of text on each stream added 33,554,432
  bytes. I expect 2,097,152, and a frame of under 400.
- **L7. The time after the job,** with the log kept. For
  the costliest kind it was over 1 second. I expect under
  0.2.

## The log's share: the measure, and what held

**What changed.** The log's record of a job carries a stream
whole where the stream is at most 1,048,576 bytes, and the
first part of a longer stream. So the reader's bar is
1,310,720 bytes a stream in a running runner. The share is a
constant, `JOB_LOG_SHARE` in `runner/runner.py`, and no
setting. A log smaller than the share is as it was: its own
size is the share.

**The measure.** The same as above: a job that writes
63,245,986 bytes on 1 stream or on each of the 2, with the log
kept at its default size. The reading is the runner's memory
at its highest, in kilobytes above a runner whose job wrote
nothing.

| The job writes | On 1 stream, before | Now | On both streams, before | Now |
|----------------|--------------------:|----:|------------------------:|----:|
| Text | 164,088 | 4,352 | 229,096 | 9,568 |
| Bytes that are not text | 328,088 | 10,448 | 415,940 | 21,556 |
| Text behind 1 character of 4 bytes | 492,972 | 17,068 | 682,860 | 32,448 |
| Not text, behind such a character | 558,480 | 19,152 | 657,300 | 36,884 |

The most on the table is 36,884, where it was 682,860. It is
flat: text behind 1 character of 4 bytes, on both streams,
read 32,676 for a job writing 1,346,269 bytes on each, 32,520
for 14,930,352, 32,712 for 40,000,000 and 28,880 for
200,000,000.

**What 1 job adds to the log,** in bytes:

| The job writes | On 1 stream | On both streams |
|----------------|------------:|----------------:|
| Text | 1,048,843 | 2,097,426 |
| Bytes that are not text | 3,145,995 | 6,291,730 |
| Text behind 1 character of 4 bytes | 1,048,846 | 2,097,432 |
| Not text, behind such a character | 3,145,996 | 6,291,732 |

Before, each of these 8 was 33,554,432: the log's whole size.
The time the runner spends after the job has ended was 0.43
seconds for text on 1 stream and over 1 second for the
costliest kind. It is 0.018 and 0.071 now.

**What held.**

| | Supposed | Found |
|---|----------|-------|
| L1 | 1,310,720 bytes a stream at the default log size | So. Held |
| L2 | About 35,000 kilobytes for the costliest kind, and under 50,000. Under 10,000 for plain text on 1 stream | 36,884 and 4,352. Held |
| L3 | Every result is what it was | The same 82 jobs: 0 differ. Held |
| L4 | A stream of at most 1,048,576 bytes is in the log whole | Held, at 1,048,575 and at 1,048,576 |
| L5 | Of a longer stream, its first 1,048,576 bytes at least and its first 1,048,576 characters at most. A secret at the cut is written as its mark | Held, for characters of 1, 2, 3 and 4 bytes |
| L6 | A job of text on both streams adds 2,097,152 bytes and a frame of under 400 | 2,097,426: a frame of 274. Held |
| L7 | Under 0.2 seconds after the job, for the costliest kind | 0.071. Held |

**2 things were not supposed.**

1. **A byte that is not text is 3 bytes in the log.** The
   share is counted in characters. The runner writes a byte
   that is not text as a mark of 3 bytes. So a job of such
   bytes adds 3 times as much to the log as a job of text:
   6,291,730 bytes for both streams. L6 was written for text.
2. **A compile hides the next megabytes.** The first measure
   of the share read too low: 1,820 kilobytes for text on 1
   stream, where the table has 4,352. The measured process had
   just compiled a changed module. Such a process starts 6,940
   kilobytes higher and has that much room free inside it, and
   what a job takes out of that room leaves no mark on the
   reading. The readings above were taken with the compiled
   modules cached, so that the measured process compiles
   nothing. A reading above a base is taken that way from here
   on. The large readings of the sections above do not move by
   it, and their small readings were taken with the modules
   cached.

**What this settles above.** The log's share of the bar is
set. And the Windows backend's pumps, which hold 67,108,864
bytes of a stream at most from the first byte, stand far over
the caller's bar now, so a record on that backend keeps what a
record keeps elsewhere.

## Finding F18: the Oracle's run tool reads the same way

F17's question, asked of the rest of the runner: who else
holds all that a process writes? That walk is not done. The
first reader it met that runs a command the runner did not
choose is the Oracle's run tool.

**What is there.** Where a model is set up, the Oracle's chat
may run a command with its run tool. The owner's tool mode
gates the tool, and the default mode allows it. The tool reads
all that the command writes, for up to 120 seconds, and then
keeps the first 8,000 characters. So what it hands back is
bounded, and what it holds on the way is not. The command is
the model's choice, and the code counts the model as untrusted
input.

**The measure.** The tool itself, and a command that writes a
fixed number of bytes and stops. The reading is the memory at
its highest of the process that ran the tool, in kilobytes
above the same process running a command that writes nothing.

| Bytes the command wrote | Held, in kilobytes | For each byte | Held, where the bytes are not text | For each byte |
|------------------------:|-------------------:|--------------:|-----------------------------------:|--------------:|
| 14,930,352 | 29,408 | 2.02 | 58,532 | 4.01 |
| 24,157,817 | 47,412 | 2.01 | 94,460 | 4.00 |
| 39,088,169 | 76,656 | 2.01 | 152,868 | 4.00 |
| 63,245,986 | 123,876 | 2.01 | 246,960 | 4.00 |

The law: 2 bytes held for each byte of text, and 4 for each
byte that is not text. What the tool hands back was 8,022
characters on every row.

A second sitting, with the compiled modules cached, read
the same on 7 of the 8 cells. The first row of text read
43,900: 3 bytes for each byte. The tool lets the pieces of
a stream go before it makes the text, and whether the room
they leave is given back by then is the allocator's to say.
So for text it is 2 bytes for each, or 3.

**Why F17's reader does not close it as it stands.** The tool
joins the 2 streams and strips the white space at both ends,
and only then cuts. A command that opens with more white space
than a bar holds would come back changed. So closing it takes
a choice about what the tool hands back. It is filed, and not
closed here.

## Finding F19: the diff of a change job is held whole

The second reader the same question met. It reads what a job
made.

**What is there.** A change job runs a recipe in a checkout of
a repository the owner has named for it. After the run, the
runner asks git for the diff of the tree against the commit.
It reads all of that diff, and then writes it to the job's
`change.diff`. What the run wrote into the tree is in the
diff. Git has 60 seconds for it. And no bar stands on a job's
own folder, on any system.

**The measure.** The runner's own function, and a tree into
which a fixed number of bytes was written after the commit.
The bytes are random, so git cannot press them small. The
reading is the memory at its highest of the process, in
kilobytes above the same process with nothing written.

| Bytes written into the tree | The diff, in bytes | Held, in kilobytes | For each byte written |
|----------------------------:|-------------------:|-------------------:|----------------------:|
| 14,930,352 | 19,243,277 | 38,192 | 2.62 |
| 24,157,817 | 31,136,139 | 61,940 | 2.63 |
| 39,088,169 | 50,379,194 | 100,060 | 2.62 |
| 63,245,986 | 81,515,114 | 161,980 | 2.62 |

The law: 2.6 bytes held for each byte written. The same
63,245,986 bytes written as zeros made a diff of 79,428 bytes,
and the runner held 1,092 kilobytes. What counts is what git
cannot press.

**What it calls for.** Git can write the diff into the file
itself, and then the runner holds none of it. It is filed, and
not closed here.

## Candidates

These are candidates. They have no number in the
constraint inventory, and they are in no draft.

1. **Every bar has a row.** Each bar on what a job uses is
   a constraint, with its value, its system and its place
   in the code. Where a system has no bar, the row says
   none.
2. **The runner holds at most a fixed number of bytes of
   what a job writes.** Finding F17. The branch's code
   keeps it for a job's 2 streams since the closing above.
   Findings F18 and F19 are the same rule, not yet kept,
   for the Oracle's run tool and for a change job's diff.
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
- A job whose result is not what it was before the reader
  had its bar.
- A job that makes a runner's memory grow with what the job
  writes.
- A quantity that a job can use up and that is on no
  kernel's list.

`runner/tests/test_v4_the_bars.py` holds this page, and
`runner/tests/test_v4_the_held_output.py` holds the closing
of F17.
