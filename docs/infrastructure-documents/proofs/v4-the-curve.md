# The curve: a limit at 38 million

The owner asked for the proof that the count of security
tokens has an upper limit, and said it is easy. It is. It
is the calculus of a limit, and a child can check each
step. This page is that proof, and what the counts say
beside it.

## In short

- **1 rule gives the limit.** Each day the count may grow
  by at most a fixed share of what is left to 38 million.
- **Then the count never passes 38 million.** What is left
  gets smaller by the same factor each day, and it is never
  all gone.
- **It is Newton's law of cooling.** The count nears its
  limit the way a warm thing nears the air of the room.
- **The counts do not keep the rule yet.** The rule allows
  0.36 million on the next day. The last 4 days ran at 1.21
  million a day.
- **What the campaign finds already keeps it.** Its finds
  level off toward a limit near 25,000.

## The picture

![The curve and its limit: security tokens in the tree, counted to 19 November 2026, then the line the rule draws toward 38 million and the line this week's pace draws](../../../assets/security-tokens-limit-2026-11-19.svg)

The points are counts. The flat line is the limit. Right of
19 November nothing is counted yet. The curve is what the
rule draws from the last count. The dotted line is what the
last 4 days' pace draws: it passes the limit by 25 November.

## The claim

Keep 1 rule, and the count of security tokens never passes
38 million. It has a limit. If each day uses what the rule
allows, that limit is 38 million itself.

## The rule

Pick a share. Call it k. It is more than 0 and less than 1.

**On each day, the count may grow by at most k times what
is left to 38 million at the start of that day.**

## The proof

Write G for what is left: 38,000,000 less the count.

**Step 1. Something is always left.** A day's growth is at
most k times G. So at the end of the day, what is left is
at least G less k times G. That is (1 - k) times G. It is
more than 0, because k is less than 1. So if something is
left this morning, something is left tonight. Something was
left on the first morning. So something is left on every
day, and the count is under 38 million on every day.

**Step 2. The count settles.** Let the count not fall, as a
tree that is only added to does not. By step 1 it does not
pass 38 million. A quantity that never falls and never
passes a bar has a limit, at the bar or under it. That is
the first theorem about limits in the calculus.

**Step 3. The limit is 38 million.** Let each day use all
that the rule allows. Then what is left is multiplied by
(1 - k) each day. After n days it is (1 - k) to the power
n, times what was left at the start. A number under 1,
multiplied by itself again and again, goes to 0. So what is
left goes to 0, and the count goes to 38 million. It gets
as near as anyone asks, and it does not arrive.

A share of a half shows it in 1 line. Of 8 left, a day
takes 4, then 2, then 1, then a half. There is always half
of something left.

## It is Newton's law of cooling

Said for every moment and not day by day, the rule is: the
count grows at a rate of k times what is left. Newton wrote
that law for a warm thing in a cool room, where the rate of
cooling is in proportion to how much warmer the thing still
is. Its curve is the same curve:

    count = 38,000,000 - (what was left at the start)
                         x e^(-k x days)

The record drew this curve on 2026-11-16, in the third
snapshot of `statistics.md`, with k at 0.055 a day. Taken
day by day that is a share of 5.35%.

## The numbers, from the last count

The last count is 31,273,283, on main on 19 November. What
is left is 6,726,717. With the record's share:

| Day | Left at the day's start | The day may add | Count at the day's end |
|----:|------------------------:|----------------:|-----------------------:|
| 1 | 6,726,717 | 359,979 | 31,633,262 |
| 2 | 6,366,738 | 340,715 | 31,973,977 |
| 7 | 4,835,996 | 258,798 | 33,422,801 |
| 14 | 3,290,657 | 176,099 | 34,885,442 |
| 30 | 1,364,908 | 73,043 | 36,708,135 |
| 60 | 262,131 | 14,028 | 37,751,897 |

What is left halves every 12.6 days. 1 million is left
after 35 days.

Counted in whole tokens, the rule allows 0 once fewer than
19 are left. So the count stops 18 tokens short of 38
million, after 244 days, and stays there.

## What the counts say now

**The test for a limit.** Take 3 counts the same number of
days apart: A, then B, then C. Under the rule the second
step is shorter than the first by a fixed factor. Call it
r: (C - B) over (B - A). If r is under 1 the curve levels
off, and its limit is C plus (C - B) times r over (1 - r).

**The count of tokens does not level off yet.** Its steps,
from the record's counts and the last count:

| Between the counts of | Added | A day |
|-----------------------|------:|------:|
| 4 and 8 November | 2,302,977 | 0.58 million |
| 8 and 13 November | 4,752,765 | 0.95 million |
| 13 and 15 November | 1,446,541 | 0.72 million |
| 15 and 19 November | 4,822,024 | 1.21 million |

The steps are not getting shorter. The rule allows 0.36
million on the next day, and the last step ran at more than
3 times that.

**What the campaign finds does level off.** The fuzz run
log's finds, new arcs and new entries, summed to each day:

| 3 days, the same number of days apart | Finds by each | The 2 steps | r | The limit |
|---------------------------------------|---------------|-------------|--:|----------:|
| 30 October, 8 November, 17 November | 21,840, 23,214, 23,916 | 1,374 then 702 | 0.51 | 24,649 |
| 4, 11 and 18 November | 22,834, 23,478, 23,988 | 644 then 510 | 0.79 | 25,929 |

By both, what these readers can find has a limit near
25,000, and 23,988 were found by 18 November.

So the knowing levels off and the count does not. The rule
is what ties the count to the knowing.

## Why the rule can be kept

What is still to be added is of 2 kinds.

- **Closed work.** A claim, proven, with its suite. It is
  added once and it is a fixed size. The join is what makes
  it closed: under the machine M every row of any length is
  1 of 14 kinds, so a longer row needs no new proof.
  `v4-the-motor.md` and `v4-the-ladder.md` carry that. A
  sum of finitely many fixed sizes fits under any bar that
  is set above it.
- **Open work.** A record of tries. It grows with the time
  spent, whatever is found. This is the part that breaks
  the rule today. It keeps the rule if it is written by
  what it finds. The finds have a limit, so a record that
  adds so much for each find has a limit too.

A first sum, with each part's source in this seat's notes
on the token curve, in the project folder:

| Part | Tokens |
|------|-------:|
| The last count | 31.27 million |
| The proof still owed: 31 constraints, up to 3 claims each | 1.0 to 2.9 million |
| The run log, at 658 tokens a find, which is its 16,318,670 tokens over its 24,804 finds, from 23,988 finds to the limit of its finds | 0.4 to 1.3 million |
| Together | 32.7 to 35.5 million |

That is under 38 million with room. It leaves out the
growth of the docs, the forum and the other tests, which
this page has not sized.

**The ladder has a limit of its own.** Each step of the
series over the step before goes to 1.618. Growing by a
fixed factor reaches any size in few steps. Step 31 passes
the cap of 1,048,576. Step 38 is 39,088,169, the first step
past 38 million. A claim that joins is carried to a size of
38 million in 38 steps, and not in 38 million.

## The rule, as a line a seat can check

At a release, 3 steps of arithmetic:

1. What was left at the day's start: 38,000,000 less the
   count then.
2. The day's allowance: 0.0535 times that.
3. The day's growth, the count now less the count then, is
   not more than the allowance.

This is a candidate. It has no number in the constraint
inventory and it is in no draft. The share and the ceiling
are the owner's to set.

## What is proven, and what is not

- **Proven:** under the rule, the count is under 38 million
  on every day, it has a limit, and with the allowance used
  the limit is 38 million. The 3 steps above are the whole
  proof. The suite walks them with whole tokens for 5,000
  days at 6 shares, with a day's growth drawn at random
  under the allowance.
- **Not proven, because it is a choice:** that the rule
  will be kept. The counts say it is not kept yet.
- **Not claimed:** that 38 million is the right ceiling. It
  is the owner's goal of 2026-11-16, taken from the
  record's curve.

`runner/tests/test_v4_the_curve.py` holds the arithmetic on
this page.
