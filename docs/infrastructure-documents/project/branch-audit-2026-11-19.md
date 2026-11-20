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
