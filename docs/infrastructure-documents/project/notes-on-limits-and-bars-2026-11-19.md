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
