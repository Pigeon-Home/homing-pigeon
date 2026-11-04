# Bravo: the design branch

Design and specification work runs on its own branch, so the live tree
stays steady while designs move as fast as they need to.

## The Bravo team

The design and specification seats are the Bravo team. The Bravo team
maintains the `bravo` branch, reads the whole project, and does its
designing, specification drafting, and prototyping on that branch.

## The rules

1. Design work lands on `bravo`, or on a branch off `bravo`. Nothing
   from the design side lands directly on main.
2. Code fixes, releases, hosting changes, rig changes, and the test
   and coverage legs are carried by the seats that run them live. The
   design side contributes designs and prototypes, not landings.
3. Work crosses from `bravo` to main as a proposal. A proposal states
   what the work is, why it is wanted, the tests that ran on the
   branch, and the risk it carries. The seat that merges it re-tests
   it on the live tree before merging.
4. The questions file (docs/seats/questions.md) stays the shared
   channel. Filings continue as before. The design side reads filings
   as design input and answers design questions on the branch.
5. A direct landing on main from the design side is out of policy. It
   is named in the forum and reviewed before it is trusted.
6. Work already on main stands. Nothing is rewritten.

## Why

The live tree took five steering changes in one afternoon this week.
A moved path broke rig jobs for twenty minutes. A version sat
unreleased for over an hour and was found by eye. One gate — design on
its branch, proposals across, a live seat re-testing before a merge —
ends that class of accident while keeping the design work fast.
