# The non-latent statistic: one name, two definitions

Written 2026-11-23, before any code in this landing was changed.
The conclusions section is appended after the tests run, in this
same place.

## The finding

A review note relayed to the forum on 2026-11-23 (the statistics
pass over the fresh figures) found that the name non-latent
carries two different definitions in two places that are
supposed to agree:

- The statistics record (statistics.md, this folder) states its
  non-latent figure as the complement of the total latent
  figure: the audit of 2026-11-16 gives total latent 3.69% of
  the tree and non-latent 96.31%. The total unions the
  near-duplicate and templated marks per line, counts an
  overlap once, adds the exact-copy lines, and takes all
  tracked tree lines as its denominator.
- The audit tool (runner/tools/duplication_audit.py) returns
  the field non_latent_percent as 100 minus the near-duplicate
  share alone, and its human summary prints that field
  immediately after the total latent line, where a reader
  takes it as the complement of the total. The tool's test
  (runner/tests/test_duplication_audit.py) pins the near-only
  definition explicitly.

The published historical figure is not shown wrong by this:
the statistics refresh keeps the audited 96.31 by hand, under
the total definition. What is wrong is the split itself. One
name, two quantities, and the tool that a fresh audit would be
run with disagrees with the record the audit feeds.

## Supposition, written before the fix

On any tree where exact or templated marks exist outside the
near marks, the two definitions give different numbers, and a
fixture can pin the difference exactly:

- A tree of two identical two-line text files reads tree lines
  4, near-duplicate 0.0%, exact copies 50.0%, total latent
  50.0%, and, under the tool's current code, non_latent_percent
  100.0. After the fix it must read non_latent_percent 50.0,
  the complement of the total, and the near-only quantity must
  still be reported under its own name at 100.0.
- A tree whose only marks are templated (a written-out list at
  the repetition scale, no repeated window anywhere) must show
  the same split: non_latent_percent below 100 by the total,
  the near-only quantity at 100.0.
- On a tree whose latent marks are all near marks, the two
  quantities coincide, which is why the existing whole-measure
  fixture never separated them.

## The resolution, chosen before the code changes

The name non_latent_percent keeps the record's definition:
100 minus total_latent_percent_tree. The statistics record is
the canonical published figure, its facts block already
carries the name with the total meaning, and the tool is the
record's instrument, so the tool is the side that moves.

The near-only quantity is not deleted. It keeps existing under
a precise name of its own, not_near_duplicate_percent_tree:
100 minus near_duplicate_percent_tree, the share of tree lines
the window measure did not mark. The tool's human summary
labels each figure with the definition it carries, so the
non-latent line that follows the total latent line is now the
complement it reads as.

The change of meaning is deliberate and dated here, not
silent. A consumer of the tool's JSON who read
non_latent_percent as the near-only complement should read
not_near_duplicate_percent_tree instead. Inside this tree the
field has no other consumer: the statistics facts carry their
own audited figure, set by hand at each audit, and already use
the total definition; the release train names the tool's path
in a warning string and reads no field from it.

Two smaller items from the same note land with this fix:

- The category percentages in the statistics paragraph (near
  3.11%, templated 0.63%, exact 0.02%) do not sum to the 3.69%
  total, because a line marked by two families is counted once
  in the total. The tool's own summary says overlaps are
  counted once; the public paragraph now says so beside its
  numbers, in the statistics record and where those numbers
  are quoted (AGENTS.md and PROTOCOL.md).
- The headline figure is labeled for what it is: the audit's
  measured tree-line share. The denominator is all tracked
  tree lines; the near and templated detection runs over the
  Python files, and exact copies are counted over tracked
  files. The label stands beside the figure in the statistics
  record's account of it, so the number is not read as
  establishing what share of the code is active or useful.

The dated audit records keep their words. The standing audit
of 2026-11-03 and the dormant-code audits of 2026-11-12 and
2026-11-13 used the near-only reading of their day, before the
templated measure and the union total existed in their present
form; the audit of 2026-11-16 handed the statistics record the
total reading (3.69% total, 96.31% non-latent) that this fix
makes the tool agree with. History is not rewritten to match;
the living surfaces are.

## Conclusions

Appended 2026-11-23, after the tests ran. The supposition
held at every point:

- The exact-copy fixture (two identical two-line text files)
  reads tree lines 4, near-duplicate 0.0%, exact copies
  50.0%, total latent 50.0%, non_latent_percent 50.0, and
  not_near_duplicate_percent_tree 100.0: the two definitions
  separated by the full exact share, as written above before
  the code changed.
- The templated fixture (a 12-line file whose only marks are
  the 10 templated lines of a written-out list) reads total
  latent 83.33%, non_latent_percent 16.67, and
  not_near_duplicate_percent_tree 100.0.
- The whole-measure fixture, whose latent marks are all near
  marks, still reads the two quantities equal, now pinned as
  a coincidence of that fixture rather than as the
  definition.
- The tool's summary now prints "not marked near-duplicate"
  beside the near figures and "non-latent (the complement of
  total latent)" beside the total, and a test pins both
  labels on the exact-copy fixture.

The change the numbers support is the one the resolution
chose: non_latent_percent is the complement of
total_latent_percent_tree in the tool, as it already was in
the record, and the near-only quantity stands under its own
name. The statistics record's account of the figure carries
the overlap note and the tree-line label, and the same note
stands beside the quoted percentages in AGENTS.md and
PROTOCOL.md. The audit module's tests stand at 23, all
passing, 3 of them new with this fix.
