# Notes on limits and bars, 2026-11-19

The owner put a question to this seat on the evening of
19 November, after the notes on the token curve. This page
is the seat's answer. The suppositions below were written
and pushed before anything was measured. The measure and
the conclusions follow them on this page.

## The question, in 4 parts

- **A. A flat line on a chart is a presumption.** A limit
  that is drawn has to be proven.
- **B. The proof may need a rule of the second degree, or
  more limits.** 1 limit or 2? A rule about how the line
  turns, and not only about where it stops?
- **C. The proof may need more constraints.**
- **D. The small case can be solved all the way.** Take
  scripts of at most 100 bytes, and solve what the atomic
  operations are.

He asked for more ideas of this seat's own, and he asked
that an idea that does not hold be thrown away.

## Suppositions

**W1. The test for a limit is of the second degree
already.** `v4-the-curve.md` tests for a limit with 3
counts. I expect that test to be the same as this: the
limit is the last count, plus the last step squared, over
the amount by which the step got shorter. A step is a first
difference. The amount by which it got shorter is a second
difference. I expect the 2 forms to agree to the token on
every row the curve page holds.

**W2. 2 limits, and the third follows.** Everything else
and the run log keep different laws. So each needs a limit
of its own, and the limit of the whole is their sum. On a
count of each day's tree, 15 October to 19 November, with 3
counts 7 days apart that end on 19 November, I expect:
everything else has a limit between 15 and 18 million, and
the run log has none. At a shorter spacing I expect the
test to be unsteady, because a single day's landing can be
as large as a week's step.

**W3. A rule on the steps gives a limit that nobody names
first.** Let each day's allowance be at most r times the
allowance of the day before, with r under 1. Then all the
days to come add at most today's allowance times r over
(1 - r). The limit is a result of the rule. I expect: from
this week's pace, a limit of 38 million needs r near 0.85
a day; and at the record's rate, 0.9465 a day, this week's
pace ends near 52.6 million.

**W4. A curve of the second degree is to be thrown away.**
A parabola has no flat line. Drawn through 3 counts of
everything else, I expect it to peak before 20 November and
to reach 0 before the year ends, which a tree that is added
to does not do.

**W5. Counts cannot prove a limit.** I expect to write 2
curves through the same 3 counts: 1 with a limit, 1 with
none. If so, the proof of a limit is never in the chart. It
is in a rule that is kept, or in a reason why the work is
finite.

**W6. At 100 bytes the whole language of the shell is
present.** Each construct of the shell's grammar has a
shortest script. I expect none to be longer than 25 bytes,
so that a script of 100 bytes holds any 4 of them together.
I expect the 22 atoms and 4 joiners of the machine M to use
fewer than half of the constructs.

**W7. No cap on a script's size is a bar on what a job
uses.** For each of 5 quantities (time, output, processes,
memory, disk) I expect a script of at most 30 bytes that
asks for it without end. If so, the small case is not
solved by listing scripts. It is solved by listing
quantities, each with its bar.

**W8. Some quantities have no bar that the runner sets.**
From reading the code, before any measure: time has a bar
on every system, because a job's own figure is cut to 3,600
seconds. The size of a result has a bar. For processes,
memory and disk the bar is the confinement's, and it
differs by system: the Linux sandbox sets none of the 3.
And the runner reads the whole of a job's output before it
cuts it to the cap. So I expect the runner's own memory to
grow by 2 to 6 bytes for each byte a job writes, on a
ladder that stops at 64 megabytes, and I expect the time
the runner spends after the job has ended to grow in
proportion too.

## How it will be measured

1. **W1:** algebra, then the 2 forms on the curve page's
   rows, in the suite.
2. **W2:** the estimator's rule over the blobs of each
   day's last landing on main, 36 days. The record's own
   rows check the count.
3. **W3, W4, W5:** arithmetic on the record's counts.
4. **W6:** a list of the shell's constructs, each with its
   shortest script. The shell's own syntax check reads each
   1. No script on the list is run.
5. **W7:** the 5 scripts are read by the syntax check and
   are not run. This machine's sandbox does not engage, so
   nothing that asks without end is started here.
6. **W8:** the bars are read from the running code, a
   system at a time. The ladder runs a job that writes a
   fixed number of bytes and stops, through the real
   executor, and reads the runner's memory at its highest.

## The measure

**W1.** The 2 forms are 1 number, to the token, on the
curve page's 4 rows and on 1,000 draws. For everything but
the run log: 14,954,555, plus 3,046,267 squared over
7,246,289. That is 16,235,175. The form has been known
since 1926 as Aitken's delta-squared process.

**W2.** Each day's tree was counted, 36 days. The first day
gives the record's own 447,477, and the 2 rows of the
record that name a commit agree to the token. With 3 counts
7 days apart that end on 19 November: everything else
points at 15.06 million, the run log at no limit, and the
whole at 77.4 million.

Not expected: a week is itself too short a step. At 7 days
apart, everything else gives no limit on 2 of the last 8
days, and from 14.75 to 47.65 million on the other 6. At 10
days apart it stands between 14.6 and 17.0 million on all
8.

Not expected: the reading of the whole climbs as it is
read. At 15 days apart it is 49.84, 71.59, 86.14 and 96.62
million on 16, 17, 18 and 19 November.

**W3.** For a bar at 38 million from this week's pace, r is
0.848. At the record's rate the bar is 52.6 million.

Not expected: everything else keeps such a rule already.
Since its largest 7 days, which ended on 31 October, it has
stayed under a line that falls by 0.61 a week, on each of
19 days. Under that line it never passes 17.6 million. The
run log's largest 7 days ended on 18 November.

**W4.** The parabola through the 3 counts of everything
else peaks late on 17 November, and is at 0 on 18 December.
Through the run log's it rises without end.

**W5.** 2 curves through the same 3 counts, and neither
ever falls: 1 with a limit at 16.2 million, 1 past 38
million within a year.

**W6.** The census has 61 constructs: 50 of POSIX's
grammar and 11 of bash's additions. None needs more than 19
bytes. Any 5 fit in 100 bytes together, and the 6 longest
need 107. The machine M uses 15 of the 61.

**W7.** The 5 scripts are 17, 3, 12, 8 and 5 bytes. The
gate admits all 5 at a bound of 17 bytes. None was run.

**W8.** The bars as the code sets them are on
`v4-the-bars.md`, a system at a time. The ladder: at its
top step, 63,245,986 bytes, the runner held 3.01 bytes of
its own memory for each byte of text, and 4.00 where the
bytes are not text. The time after the job had ended was
0.44 and 1.01 seconds there, and it grew with the bytes.

Not expected: the constraint spec has a row for 1 of these
bars only, and in part. And the FreeBSD backend holds 4
bars that the Linux sandbox does not.

## Conclusions

| Supposition | Held | The measure beside what was expected |
|-------------|------|--------------------------------------|
| W1 | yes | the same to the token |
| W2 | yes, at its edge | 15.06 million, in a range of 15 to 18; a step of 7 days is itself unsteady |
| W3 | yes | 0.848 for near 0.85; 52.6 million |
| W4 | yes | a peak on 17 November for before the 20th; 0 on 18 December |
| W5 | yes | both curves are written |
| W6 | yes, with room | 19 bytes for 25; any 5 for any 4; 15 of 61 |
| W7 | yes, with room | 17 bytes for 30 |
| W8 | yes | 3 and 4 bytes for 2 to 6 |

All 8 held. 5 things were not expected, and they are the
better part of the measure: the week that is too short, the
reading of the whole that climbs, the rule that everything
else already keeps, the constraint spec that is silent on
how much a job may use, and FreeBSD ahead of Linux on the
bars.

## The answer, part by part

**A. A flat line is a presumption. Kept.** A chart can show
a limit and cannot prove 1. What proves it is a rule that
is kept, with something that refuses to pass it, or a
reason why the work is finite.

**B. 2 limits. Kept. The second degree: kept as a test and
as a rule, thrown away as a curve.**

- 1 limit for the whole hides 2 laws. Everything but the
  run log stops near 16 to 18 million by 4 readings. The
  run log has no limit by any reading. With a limit for
  each, the limit of the whole follows as their sum.
- The test for a limit is of the second degree already. A
  rule on the steps gives the limit as a result, so nobody
  has to name it first. A parabola has no flat line.

**C. More constraints. Kept, and it is where the work is.**
The constraint spec bounds what crosses the wire, what a
job may touch and what a result may show. On how much a
job may use it has 1 row, in part. The bars are in the
code, on some systems, and in no constraint.

**D. The small case, solved. Kept, with 1 change.** Solve
the quantities, and not the scripts. At 100 bytes the whole
language is there, so a cap on size solves nothing, and a
list of texts solves nothing. What is solved is the list of
quantities, each with its shortest script and its bar. That
list has no size in it, so it carries from 100 bytes to any
size.

## Thrown away

- A curve of the second degree.
- A proof of a limit from the counts alone.
- A limit read with a step of 7 days.
- A rule on what a day did add: 1 day of nothing ends it.
- A list of the scripts of 100 bytes, and a list of texts
  to refuse.
- 1 limit for the whole.

## Added by this seat

1. **A reading is believed while it stands still.** Read
   the limit again each day. If the reading climbs, it is
   not a limit yet.
2. **A limit is proven where something refuses to pass
   it.** A bar on a job is such a limit. For the count of
   tokens nothing refuses yet.
3. **Every quantity has a row.** The shortest script that
   asks for it without end, and its bar on each system. A
   kernel's own list of resources is the inventory to walk.
4. **P2, said for how much.** The property that holds the
   ceiling on what a job may touch, said again for how much
   a job may use.
5. **Finding F17.** The runner holds all that a job writes.
   It came out of the list of quantities, with nobody
   pointing at it.

## Filed, and not done here

- **F17 was open when this page was pushed.** It is closed
  on the branch since: the rule, its model, the measure and
  what held are on `v4-the-bars.md`. It waits for a second
  seat's test.
- **F18 and F19 are open.** The Oracle's run tool holds all
  that a command writes, and the runner holds the whole
  diff of a change job. Both came out of F17's question,
  asked of the rest of the runner. They are on
  `v4-the-bars.md`, each with its ladder.
- **The log's share of the bar.** A running runner's bar
  follows its log's size: 33,816,576 bytes a stream at the
  default. A smaller share for a job's record changes what
  the log keeps, so it is the owner's to weigh.
- **Rows for the bars in the constraint spec.** The spec
  and its binding are shared pages.
- **The Linux sandbox's 3 missing bars.** They change what
  a default install does, so they are the owner's to weigh.
- **The walk of each kernel's own list.**
- **The curve's rule, asked at a release.** The release
  train is the owner's.
- **The 5 scripts, each stopped at its bar,** inside a
  sandbox that engages. Not on this seat's machine.
