# An audit of the version 4 branch, 2026-11-19

The owner asked for an audit of `future/v4-provable-model`.
This page is that audit. What was expected is written first
and pushed before anything was run. The measure and the
conclusions follow it.

## The branch, as the audit met it

Known before any run, from the server:

| | |
|--|--|
| Head at the audit's start | `2542a897d` |
| Where it left main | `8b45d6106`, on 2026-11-19 |
| Commits main does not have | 45: 26 by Claude's seat, 17 by Grok's, 2 by Muse's |
| Commits of main it does not have | 108 |
| Files changed since it left main | 45, with 10,892 lines added and 65 taken out |
| Code changed, outside the tests | 5 files: `runner/ops/mail.py`, `runner/runner.py`, `runner/guard/panic.py`, `runner/oracle/opinion.py`, and the figures in `runner/ops/core.py` |
| Builds of this branch on the server | 0 |

The last row is a finding before any run. The server's
build has never run on this branch. Nothing here has been
built on macOS, or on a real Windows. What follows is 1
machine's word: Linux, 2 cores, the sandbox not engaging.

## What the audit asks

1. Is anything red?
2. Do the proof's own suites hold when they are repeated,
   shuffled and run under the simulated Windows surface?
3. Is a protected name, an address, a key or a token in
   anything the branch adds?
4. Did a line move that must not: the drafts, the owner's
   pages, a default, the constraint inventory?
5. Do the pages agree with each other where they state the
   same figure?
6. Does each change to the code have a finding, a test
   that fails without it, and a second seat's test?
7. Can the branch meet main?

## Suppositions, written before the runs

- **A1. The whole suite.** Supposed: the only reds on this
  machine are the 5 known before. 2 are bench tests this
  machine cannot pass. 3 are hidden import tests that wait
  for a line that stands on main.
- **A2. The proof's suites under the guard.** 16 suites of
  version 4 stand on the branch. Supposed green on all 16,
  with 1 soft note known before: a temp folder that 1 test
  of the ladder's run leaves until the process ends.
- **A3. Names and secrets.** Supposed 0 protected names in
  the 45 commits and in the tree. Supposed 0 addresses,
  hostnames, keys or tokens in the lines the branch adds.
- **A4. The lines that must not move.** Supposed: no change
  under the drafts, none to the owner's 2 pages, none to
  the example configuration, and no default changed. The
  3 changed lines of `PROTOCOL.md` are supposed to be the
  measure's figures and nothing else. The constraint
  inventory is supposed to have 31 rows, as on main.
- **A5. The pages against each other.** Supposed: every
  figure that stands on more than 1 page is the same on
  each. Supposed too: 3 lines or fewer are stale. This seat
  knows of 2 before the run, both its own: the ladder
  page's line that the writer's join is open, and its
  notes' count of pages and suites.
- **A6. The code changes.** 4 findings were closed in code
  on this branch: F12, F13, F14 and F15. Supposed: each
  has its page and a test that fails when the change is
  taken out. Supposed: F15 has a second seat's test, and
  F12, F13 and F14 still wait for theirs.
- **A7. Meeting main.** A trial joining with main, made in
  a scratch copy and thrown away. Supposed: it stops in 6
  files or fewer, each of them a page of figures, the
  forum, or a listing, and none of them code. Supposed:
  with main's lines in place the 3 hidden import tests
  pass.

## The measure

Run on 2026-11-19 on 1 machine: Linux, 2 cores, Python
3.13.18, bash 5.2.21, the sandbox not engaging. While the
audit ran, 2 more commits landed: this page's first part,
and a forum entry by Muse's seat. The counts below are
taken at that head, `86ee51fcc`: 47 commits, 27 by Claude's
seat, 17 by Grok's and 3 by Muse's.

### A1. The whole suite

14,294 tests ran in 1,498 seconds. 273 were skipped and 3
were red.

| Red | Known before | What it is |
|-----|--------------|------------|
| 2 bench tests of the first ping | Yes | They send 2 jobs through a whole runner, and here neither comes back. They were red on this machine before the branch, in this seat's run of 2026-11-18 |
| The check that no page under `docs/` carries a public address | No | It named `v4-at-a-limit.md` |

The third is the audit's first finding. The page cited 3
passages of the shell's standard by their numbers. Each
number is 4 numbers joined by dots, and that is the shape
of an address. None of the 3 is an address. The check has
been red on the branch since the page landed, in commit
`ccf521a59`. The suites this seat ran before each push did
not include it.

The 3 hidden import tests were supposed red. They are
green. The line they wait for was on main before the
branch left it.

### A2. The proof's suites under the guard

The guard ran each of the 16 suites 7 times: once plain, 3
more times the same way, twice shuffled, and once under the
simulated Windows surface. 347 tests, 112 runs, 1,037
seconds.

| Suite | Tests | The guard |
|-------|------:|-----------|
| `test_v4_at_a_bound.py` | 16 | green |
| `test_v4_at_a_limit.py` | 23 | green |
| `test_v4_before_the_mac.py` | 29 | green |
| `test_v4_binding.py` | 21 | green |
| `test_v4_bindings.py` | 53 | green |
| `test_v4_draft.py` | 18 | green |
| `test_v4_general.py` | 43 | green |
| `test_v4_models.py` | 65 | green |
| `test_v4_the_answer.py` | 6 | green |
| `test_v4_the_curve.py` | 10 | green |
| `test_v4_the_folder.py` | 6 | green |
| `test_v4_the_grammar.py` | 7 | green |
| `test_v4_the_join.py` | 5 | green |
| `test_v4_the_ladder.py` | 12 | green |
| `test_v4_the_place.py` | 8, with 3 skipped here | green |
| `test_v4_the_ladder_run.py` | 25 | red in 1 run of 7 |

111 runs were green and 1 was red. In the second of the 3
repeated runs, 1 test failed:
`test_the_ladder_finds_f14_with_nobody_pointing_at_it`. It
asked that the old patterns read more than 1.5, and they
read 1.48. The guard's word for it is a flake.

This is the audit's second finding. The audit's own runs
loaded both cores at the time, and the first thought was
the load. The measure says otherwise. That test climbs
with a budget of half a second, so its ladder stops at
6,765 bytes, where the work that grows with the square is
still mixed with work in proportion. The reading of a mix
moves from climb to climb:

| The machine | The reading, a budget of half a second |
|-------------|----------------------------------------|
| Under load | 1.481, 1.553, 1.622 |
| Quiet | 1.415, 1.701, 1.715 |

The bar of 1.5 sat inside the spread. With a budget of 2
seconds the same ladder climbs to 17,711 bytes and reads
1.76 to 1.88 over 5 climbs, quiet and under load.

The soft note stood as supposed: 1 temp folder, left by 1
test of the same suite until the process ends.

### A3. Names and secrets

The name guard read all 47 commits: each message, each
path and each file. 0 protected names.

The branch adds 11,013 lines. Each was searched:

| Searched for | Found | What they are |
|--------------|------:|---------------|
| A mail address | 28 uses of 8 | Test addresses. 7 are on the domain kept for examples, and 1 is made of single letters |
| A key's shape: a token's prefix, a key's header | 0 | |
| 32 or more characters of hex in a row | 1, used twice | A commit's id |
| 48 or more characters of base64 in a row | 0 | |
| 4 numbers joined by dots | 4 | The 3 passages of A1, and 1 version of this project |
| A link | 2, each used twice | The namespace of a picture's format, and this project's release page |

### A4. The lines that must not move

- 0 files changed under the drafts' folder, 0 of the
  owner's 2 pages, 0 in the example configuration and 0 in
  the server's build files.
- `PROTOCOL.md` changed in 3 lines. All 3 are the measure's
  figures: its date, the count of tokens and the count of
  lines.
- No default changed. The cap on a script stands at
  1,048,576.
- The constraint inventory has 31 rows, C1 to C31, where
  the branch left main, on the branch and on main today.
  The branch did not touch it. A candidate is called C32
  on `v4-before-the-mac.md`, in its index entry and in its
  suite. It is in the inventory at none of the 3.

The gate has 7 new bars. Each is a constant in the code,
with its finding on a proof page. None is a default that a
configuration sets.

| Bar | Value | In | For |
|-----|------:|----|-----|
| `SUBJECT_MAX` | 2,048 | `runner/guard/panic.py` | F13 |
| `ADDRESS_COLON_BAR` | 64 | `runner/ops/mail.py` | F15 |
| `COMMENT_DEPTH_BAR` | 8 | `runner/ops/mail.py` | F15 |
| `LOG_ID_MAX` | 128 | `runner/runner.py` | F12 |
| `LOG_SENDER_MAX` | 254 | `runner/runner.py` | F12 |
| `LOG_SUBJECT_MAX` | 256 | `runner/runner.py` | F12 |
| `LOG_REASON_MAX` | 512 | `runner/runner.py` | F12 |

### A5. The pages against each other

14 figures stand on more than 1 page: 31,460, 19,360,
44,588, 12,544, 1,597, 352 steps, 22 atoms, 13,332, 3,333,
1,048,576, the 2 versions of bash, 74,072,330,493, 16,384
and 2,178,309. Each reads the same wherever it stands.
Every suite of version 4 is named by a page.

4 places did not agree with the tree:

| Where | What it said | What stands |
|-------|--------------|-------------|
| The proofs' index | No entry for `v4-the-motor.md` | The page is on the branch |
| `v4-the-ladder.md`, what comes next | 2 lines: the shell's ladder with confinement on, and the writer's join, were still to run | Both are measured, on `v4-the-place.md` and `v4-the-folder.md`. The shell's 2 bars with confinement on are still to climb |
| `v4-at-a-limit.md`, 1 row of its table | "9 kinds of row", 4 times | "Kind" has meant 1 of the 14 kinds since the join. These 9 are shapes |
| This seat's notes on the token curve | 15 pages and 14 suites | 16 pages and 16 suites, 195,904 tokens. The notes' "about 200,000" stands |

### A6. The code changes

The branch adds 171 lines of code and takes out 18, in 5
files. 9 of the added lines are the measure's figures. The
other 162 close 4 findings. For each, the 4 files were set
back to where the branch left main, and the finding's
tests were run against that:

| Finding | The change | Its page | With the change taken out |
|---------|------------|----------|---------------------------|
| F12 | What 1 refused mail adds to the log is cut at 4 bars | `v4-before-the-mac.md` | 8 of its 8 tests fail |
| F13 | The panic step reads a subject of 2,048 characters at most | `v4-before-the-mac.md` | 5 of its 7 tests fail |
| F14 | The reader of a script's shape takes the white space of 1 line | `v4-at-a-limit.md` | Its class does not end in 150 seconds |
| F15 | A mail whose shape cannot be read is marked, and the gate goes on | `v4-the-ladder.md` | 5 of 5 tests fail in this seat's suite, and 5 of 6 in Grok's |

The 162 lines were read again for this audit, 1 by 1.
The reading raised 1 question. F15's change counts the
colons and the comments of the sender's header as a text.
The mail library returns that header as an object, and not
as a text, when it carries a byte past 127. The gate makes
it a text first. Asked of the real gate with 4 such
headers, 2 of them past a bar: each job ran, each mail was
marked once, and each line was of bounded length. 0
findings from the reading.

Who tested what:

| Finding | Changed by | Tested by a second seat |
|---------|------------|-------------------------|
| F12 | Claude's seat | Not yet |
| F13 | Claude's seat | Not yet. Muse's seat read it as closed in the forum on 2026-11-19 |
| F14 | Claude's seat | Not yet |
| F15 | Grok's seat | Claude's seat: 3 shapes at every seventh count from 40 to 1,100, 0 raises |

26 of the 47 commits change a test module. The 11 by
Claude's seat carry the guard's line. The 15 by Grok's
seat do not. The guard has now run over every suite those
15 touch: A2 is its word.

### A7. Meeting main

Main stands at `69a05c254`, 108 commits past where the
branch left it. A trial joining was made in a scratch copy
and thrown away. Nothing of it was pushed. It stopped in 8
files:

| File | Stops | What meets |
|------|------:|------------|
| `AGENTS.md` | 4 | The measure's figures |
| `PROTOCOL.md` | 1 | The measure's figures |
| `statistics.md` | 6 | The measure's figures |
| `docs/steady/fuzzing.md` | 2 | The measure's figures |
| `runner/ops/core.py` | 1 | The measure's figures, 3 lines |
| `runner/tests/test_core.py` | 1 | The measure's figures, 1 line |
| The proofs' index | 1 | Entries added on both sides |
| The forum | 1 | Entries added on both sides: 986 lines here, 850 on main |

No logic meets. Main has not changed `mail.py`, `panic.py`,
`runner.py` or `opinion.py` since the branch left.

The 6 files of figures were taken from main and measured
again, and the measure ran clean. The index and the forum
were given both sides. On that joined tree:

| What ran | Tests | Result |
|----------|------:|--------|
| Before the measure: the core's figures, the hidden import tests, the doc gates and 8 suites of version 4 | 1,419 | green |
| After the measure: the figure and doc gates again | 129 | green |
| The other 8 suites of version 4, and the address check | 128 | 1 red |
| Main's own check of its gate reader, over its corpus | 1 | green |

The red is the audit's third finding, and it is not red on
the branch. 1 test of the ladder's run counts the readers
the fuzz driver holds: 30. Main's driver has held 31 since
2026-11-19, and the thirty-first is the gate. So that test
turns red on the day the branch meets main. It should. The
measure of L9 climbed 30 readers, and a reader that was not
climbed is what the count is there to catch.

The gate reader was then climbed on the scratch copy, as
the 30 were: from each of its 15 seeds, with 4 units, to
step 24. 60 ladders and 0 raises. At every step the
reader's verdict is its verdict on the seed. It reads 0.51
to 1.00, between flat and in proportion, and its slowest
top step took 0.061 seconds. On that day the count becomes
31, and the measure covers it.

Joined, the count is 31,405,922 tokens. Main's is
31,273,391, so the branch brings 132,531. The rule on
`v4-the-curve.md` would allow 359,973 on that day.

Not run on the joined tree: the whole suite.

## After the measure: the head moved

While the measure was being written, Muse's seat closed F11
on the branch, in commit `af85f1c76`. It is a change to the
gate and to the sender, 49 lines of code in 2 files, and it
came after everything above was measured. So the audit
went on, as that change's second seat.

### What F11's change is

- **In the gate.** A subject's encoded words are decoded
  before the id is read off it. A subject of more than
  2,048 bytes is not handed to the decoder and is read as
  written. That is an eighth bar, `SUBJECT_DECODE_MAX`, in
  `runner/ops/mail.py`.
- **In the sender.** The runner's own mail is built with
  its lines set to 998, so a subject with a long id leaves
  on 1 plain line.
- **Its tests.** 4, in `test_v4_bindings.py`. Its commit
  names no run of a suite and carries no guard line.

### What the second seat ran

| What ran | Result |
|----------|--------|
| The gate's 5 suites on the new head | 158 tests, green |
| The guard on the 3 test modules F11's commit changed | Green: 128 tests, 7 runs of each |
| The whole suite on the new head, with the corrections above | 14,299 tests in 1,417 seconds. 273 skipped. 2 red: the 2 bench tests of A1, and no other |

The decode step was then climbed on the ladder, which is
the test that found F13 in the same decoder. 7 units, each
under a good signature and under a turned signature: 5
kinds of encoded word, half a word, and a plain letter. 14
ladders of 26 steps, to subjects of 0.4 to 4.1 million
bytes.

| Asked at each of the 364 steps | Found |
|--------------------------------|-------|
| The most the decoder was handed | 2,048 characters |
| The slowest arrival with the subject under the bar | 0.0036 seconds |
| The time with the subject over the bar | In proportion to the mail, and none of it in the decoder |
| The mail was decided and marked once | At every step |
| The most 1 mail wrote to the log | 541 characters |

At the bar itself: a subject of 2,047 bytes and of 2,048 is
decoded, and 1 of 2,049 is not. 8 shapes of an encoded
subject were sent after that. Each was marked once. A word
that decodes to another encoded word is decoded once and
not twice.

F11's change holds on the ladder. It has its second seat's
test.

### The fourth finding, from 1 of the 8 shapes

1 shape put a control character where the id stands. The
gate's first line wrote it quoted, as F12 made it. A second
line wrote it as it is.

That line is behind the signature, and F12's measure never
reached it: F12 grew its texts in messages that fail at the
signature. The signature covers the body and not the
subject. So a body this runner's own key signed, sent again
under a subject that names another id, passes the
signature, and is refused only when the 2 ids are set side
by side. In between, with clear text allowed, the gate
wrote 1 line that names the job by the subject's id, whole:

| The subject's id | That line |
|-----------------:|----------:|
| 128 characters | 206 |
| 100,000 characters | 100,078 |
| 100,000 escape characters | 100,078, with each escape as it is |

Who can send it: anyone who holds 1 mail that this runner's
key signed. They need not hold the key. The runner must
have been started with clear text allowed, which is not the
default. The line stands on main too. It is older than the
branch.

So F12 was not wholly closed, and the audit closed the
line: it writes the id as the first line does, 231
characters for an id of 100,000. `v4-before-the-mac.md`
records it, and 2 tests hold it. 1 of them fails on the
code as it was. The 3 suites of the tree that pin an honest
job's line are green: the line is as it was for an honest
id. This change came after the whole suite's second run.
What ran on it is the gate's suites, those 3, the doc
gates and the guard: 1,266 tests, green.

The cause is left for the owner. The 2 ids are set side by
side late: after that line, and after the audience check,
which is handed the subject's id too and writes it into
the security audit when the audience does not match. That
second place was read and not measured. Setting the 2 ids
side by side first would close both. It would also change
the order of the gate's refusals.

## What the audit changed

Each is this seat's own line, and each is in the commit
that carries this measure.

| What | Where | After |
|------|-------|-------|
| The 3 passages are named by their section and their place in it | `v4-at-a-limit.md` | The address check is green: 25 tests |
| The test that flaked decides by the stop, and by a plain script climbed beside the ladder, which the old patterns must exceed 10 times. Measured: 58 to 93 times | `test_v4_the_ladder_run.py` | The guard on that suite is green: 7 runs in 184 seconds with the machine quiet, and 7 more in 456 seconds with both cores loaded |
| The temp folder is removed when its test ends | The same suite | The guard's soft note is gone |
| 1 new test: the 4 headers of A6 | The same suite | 26 tests |
| What the flake taught, as a fourth lesson of the technique: a reading is taken where 1 law has taken over | `v4-the-ladder.md` | |
| The 4 places of A5 | The index, 2 proof pages and the notes | |
| The line behind the signature writes the id at a bounded length, as F12's lines do. 2 new tests | `runner/ops/mail.py`, `test_v4_before_the_mac.py`, and the page of that name | 31 tests. The guard is green on that suite and on the core's |
| The address check joins the suites this seat runs before a push | This seat's practice | |

## Conclusions, against the suppositions

| | Supposed | Found | Held |
|--|---------|-------|------|
| A1 | 5 reds, all known | 3 reds. 2 known. 1 new, and the 3 hidden import tests green | No |
| A2 | Green on all 16, with 1 soft note | 15 green. 1 red in 1 run of 7, and the soft note | No |
| A3 | 0 names, 0 secrets | 0 and 0 | Yes |
| A4 | Nothing moved, 31 rows | Nothing moved, 31 rows. 7 new bars, none a default | Yes |
| A5 | The figures agree, and 3 lines or fewer are stale | The figures agree. 4 places | No, by 1 |
| A6 | Each change has a page and a test that fails without it. F15 has a second seat's test | So | Yes |
| A7 | 6 files or fewer, none of them code | 8 files. 2 are Python files, and what meets in them is figures. 1 test turns red on that day | No |

4 of the 7 did not hold. The branch carried 1 red and 1
flake. Both are in lines this seat wrote, and neither is
in the gate. The gate's 4 changes each stand on a test
that fails without them.

A6 held as it was supposed, and the audit still found F12
short by 1 line. The supposition asked whether each change
has a test that fails without it. It did not ask whether
the finding was closed on every path. The ladder asked
that, on another seat's change.

## What the audit files

These are not changed here. Each is another seat's, or the
owner's.

1. **The server has never built this branch.** Its build
   runs for main, for a release and for a pull request, or
   when it is started by hand. None of the 4 has happened
   for this branch. So nothing here has run on macOS or on
   Windows. This is the largest thing the audit cannot
   say. With this page pushed, the audit starts the build
   by hand on the branch: every suite on Linux, macOS and
   Windows, with nothing published. Its word is added to
   this page when it has spoken. FreeBSD, the confinement
   backends and the range of Python versions have
   workflows of their own, on a schedule for main. They
   are not started here.
2. **F12, F13 and F14 wait for a second seat's test.** They
   are this seat's changes, and a code fix does not reach
   main on its own seat's word. F12's third line, closed
   here, waits with them.
3. **The 2 ids are set side by side late.** This is the
   cause of the fourth finding. To set them first, straight
   after the signature, changes the order of the gate's
   refusals. It is the owner's to say.
4. **The hosted queue's copy of F10's search is open,** at
   the owner's word. The ladder met it again in L9.
5. **The 8 bars are in no reader's page.** `PROTOCOL.md`
   and `SECURITY.md` do not state that a subject of more
   than 2,048 characters is not a panic. A panic subject
   as they describe it is 51 characters, so no reader who
   follows them meets the bar. Whether they should state
   it is the owner's to say.
6. **The guard's line** is missing from the 15 commits of
   A6, and from the commit that closed F11. For Grok's seat
   and for Muse's.
7. **Meeting main is by hand, in 8 files.** The forum's 2
   runs of entries are to be set in order of their dates.
   The count of readers goes from 30 to 31 in the ladder's
   run, with the gate reader's row on the ladder page.
8. **2 candidates have no number,** as intended: the rule
   on `v4-the-curve.md`, and C32.

## What the audit does not say

- It is 1 machine's word. The server's build is the
  second, and it has not spoken.
- The sandbox does not engage here. The suites that need
  it ran their refusal here: under enforce the runner
  answers with a signed refusal, and nothing of the job
  runs. The rows with confinement on are from Grok's
  machine.
- The whole suite was not run on the joined tree.
- The 162 lines that change the gate, and the 49 of F11's
  change, were read 1 by 1. The pages and the tests were
  not: they were checked by the gates, the guard and the
  searches above.
