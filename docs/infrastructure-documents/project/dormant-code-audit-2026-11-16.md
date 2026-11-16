# Dormant code: the fresh audit, 2026-11-16

This record is the fresh dormant-code audit the conductor
called for on 2026-11-16, reporting the latent figure up
about a point over the last day. The recorded figure it is
read against is the 2026-11-13 audit's
(dormant-code-audit-2026-11-13.md): total latent 3.84% of
the tree. The method is the standing one, operationalized
in `runner/tools/duplication_audit.py`: a sliding window
of 8 normalized non-blank, non-comment lines over the
Python files for near-duplicate code; the templated
measure of AGENTS.md rule 16 over written-out lists;
exact copies by file hash over the whole tree; and a scan
for Python files nothing references. Shares are stated
against the whole tree's tracked lines.

Following the project's standing rule, this record states
its supposition first, committed before the measurement
exists. The measurement and the conclusions stand below
it when the run lands, and any reduction the numbers
support is recorded in the same place.

## The baseline on record

The 2026-11-13 audit, after the Q172 fold: the tree at
1,431,648 lines; near-duplicate Python 46,360 lines,
3.24% of the tree (tests 40,901, production 5,459);
templated lines 9,475, 0.66% of the tree; exact copies
340 lines beyond the first copy, 0.02% of the tree;
total latent 55,027 lines, 3.84% of the tree;
unreferenced Python files 0; generated files checked in
1, the ci-health snapshot. Its largest contributors stood
where the earlier audits left them: the airgap OVERVIEW
fixture at 11,047 near-duplicate lines, the divergence
exhibits at 5,528, the briefing module's scaffolding at
2,829, and the briefing module carrying 5,735 of the
templated lines in the earlier filings' smaller written
lists, which no decision has asked to fold.

## The landing record since the audit

Stated from the commit record, before any measurement:

- Since the 2026-11-13 audit the Python grew by 19,400
  added lines against 2,126 removed, across 103 files.
  The growth is concentrated in the platform confinement
  work: `runner/tests/test_freebsd_confine.py` gained
  6,998 lines, `runner/tests/test_macos_confine.py`
  gained 2,930 and then 1,004 more, and
  `runner/tests/test_windows_confine_fuzz.py` arrived
  with 711. On the production side the new backends
  `runner/guard/freebsd_confine.py` and
  `runner/guard/macos_confine.py` gained 1,683 and 899
  lines, beside the Windows backend they stand next to.
- The last day alone, from the 3.16.26.21 release head
  of 2026-11-15 to the current head, is documentation
  heavy and Python light: the tree grew by about 25,000
  lines, nearly all of it documentation and records,
  while the Python grew by 1,688 added lines against
  120 removed, in 16 files, most of it the macOS
  confinement tests again. Growth outside the Python
  dilutes the latent share, because the denominator
  grows while the numerator stands still. It cannot
  raise the share.

## Supposition (recorded before the measurement)

1. **The total is up, by most of a point.** Total latent
   now stands between 4.3% and 5.0% of the tree, with a
   point expectation near 4.6%: a real rise against the
   recorded 3.84%, at or under the point the conductor
   reported, and at or under the standing 5% limit.
2. **The rise accumulated since the audit, not in the
   last day.** Measured at the 3.16.26.21 head against
   the current head, the move reads a few tenths of a
   point at most, because the last day's landings are
   documentation and records. Measured against the
   2026-11-13 audit, the same figure reads most of the
   point.
3. **The confinement test families supply most of the
   numerator growth.** `test_freebsd_confine.py` and
   `test_macos_confine.py` stand in the top
   near-duplicate ranks, where the 2026-11-13 audit's
   top ranks did not name them, because a confinement
   trial repeats one arrange, act and assert shape per
   field and per shape, and the window measure counts
   both sides of every repetition.
4. **Templated lines rise modestly.** The templated
   share stands under 1.1% of the tree, unless the
   confinement families carry written-out lists at a
   scale the masked-token measure names, in which case
   templated lines supply a large share of the rise
   and the measure names the files that carry them.
5. **Production near-duplicate grows some.** The
   sibling confinement backends repeat the shape the
   Windows backend set: shared trial scaffolding,
   shared posture tables, one backend per platform.
   The production share of the tree rises from 0.38%
   toward 0.5%, by hundreds to a few thousand lines.
6. **The deliberate families hold their counts.** The
   airgap OVERVIEW fixture stands near 11,047 repeated
   lines, the divergence exhibits near 5,528, and the
   feed-extension skeleton and the 3 signers stand
   unchanged in kind, because no landing since the
   audit set out to change them.
7. **The small figures hold.** Exact copies still 340
   lines beyond the first copy; unreferenced Python
   files still 0; generated files still the 1
   ci-health snapshot.

What the numbers would support, stated ahead of them:
reductions only where the repetition is scaffolding. In
the confinement test families, a shared trial helper
inside the tests tree, with the cases kept as data,
follows the precedent the defaults registry set. A
written-out list the templated measure names at scale is
derived when the test runs, under rule 16, the remedy
the Q172 fold applied to the briefing module. The
deliberate families stay as they stand. The production
backends stay, unless their repetition proves to be a
pure helper carrying no platform meaning, because a
platform backend is read on its own by the people who
port the next one.

## Measurement (2026-11-16)

The same tool, run on 4 heads of main: the 2026-11-13
audit's close head, a 2026-11-14 head, the 3.16.26.21
release head of 2026-11-15, and the current head, which
carries this record's supposition as its only change
from the release head before it.

At the current head: the tree stands at 1,499,796 lines
in 1,457 tracked files, the Python at 417,245 lines in
696 files. Near-duplicate Python: 46,614 lines, 3.11% of
the tree, split 40,940 in the tests and 5,674 in
production code. Templated lines: 9,500, 0.63% of the
tree, split 9,033 in the tests and 467 in production.
Exact copies: 340 lines beyond the first copy, 0.02% of
the tree. Total latent: 55,306 lines, 3.69% of the tree.
Unreferenced Python files: 0. Generated files checked
in: 1, the ci-health snapshot.

The series across the span, total latent lines and
share, with the tree's size beside them:

- 2026-11-13, the audit's close head: 55,047 lines,
  3.84%, on a tree of 1,433,138 lines. This re-measure
  validates against the audit's own figures, taken on
  the fold commit a few commits earlier (55,027 lines,
  3.84%), the way the 2026-11-09 audit validated against
  the one before it.
- 2026-11-14: 55,035 lines, 3.76%, on a tree of
  1,462,344 lines.
- 2026-11-15, the 3.16.26.21 head: 55,288 lines, 3.75%,
  on a tree of 1,474,994 lines.
- 2026-11-16, the current head: 55,306 lines, 3.69%, on
  a tree of 1,499,796 lines.

The composition barely moved. The top contributors
stand in the audit's own ranks: the airgap OVERVIEW
fixture at 10,952 repeated lines (11,047 at the audit),
the divergence exhibits at 5,528 (unchanged), the
briefing module at 2,828 near-duplicate lines and 5,735
templated lines (both unchanged), and the defaults
registry at 1,973 templated lines (unchanged). The
confinement families, measured file by file:
`test_freebsd_confine.py`, 7,317 lines, carries 281
near-duplicate lines and 4 templated; `test_macos_confine.py`,
4,142 lines, carries 160 and 2; `test_windows_confine_fuzz.py`,
711 lines, carries 9 and 1; and on the production side
`freebsd_confine.py` carries 27 near-duplicate lines of
its 1,772, `macos_confine.py` 145 and 2 of its 1,586,
and `windows_confine.py` 43 and 19 of its 1,110. Across
the whole span the latent lines moved by 259 net, from
55,047 to 55,306, while the tree grew by 66,658 lines.

## Conclusions

Against the suppositions, in their order:

1. **Missed, on direction.** There is no rise. The
   total stands at 3.69%, down 0.15 points from the
   recorded 3.84%, and under the 5% line with more room
   than the last audit measured.
2. **Half held.** The last day's move is as small as
   supposed, 18 latent lines and 0.06 points down
   between the 3.16.26.21 head and the current head.
   But no rise accumulated before it either: at every
   measured head the share fell, because the numerator
   stood still while the tree grew around it.
3. **Missed.** The confinement test families carry
   about 450 latent lines between them, near 4% of
   their own mass. Their trials vary by field and by
   shape in names, values and assertions, so few
   8-line windows repeat whole. The largest Python
   growth of the span is among the cleanest code the
   measure reads.
4. **Held.** Templated lines stand at 0.63% of the
   tree, under the supposed 1.1%, and flat in lines,
   9,475 at the audit to 9,500 now.
5. **Mostly missed.** Production near-duplicate grew
   by some 200 lines, to 5,674, and its share of the
   tree stands unchanged at 0.38%. The sibling
   backends repeat far less than supposed, 27 to 145
   lines a side, because each backend's body is its
   own platform's calls and tables.
6. **Held.** The deliberate families stand at their
   recorded counts, the fixture down 95 lines, the
   exhibits and the briefing lists exact.
7. **Held, exactly.** Exact copies 340, unreferenced
   Python files 0, generated files 1.

On the rise the conductor reported: at no measured head
in the span does the figure reach the recorded 3.84%
again, and a rise of a point would take some 15,000
latent lines the tree does not contain. Wherever the
reported figure was read, it was not this tree under
this method. The readings this record cannot rule out
are a measure taken on a working tree carrying
uncommitted or untracked copies (run without a git
index, the tool walks what stands on disk, release
bundles and all) and a projection read as a measure.
On main, the figure fell.

On reduction: none is made, and the numbers say why.
Every concentration of latent lines in the tree stands
in a family the standing audit judged deliberate, for
reasons that still hold: the airgap fixture is a frozen
control a repair would destroy; the divergence exhibits
are standalone bug reports; the briefing module's
remaining written lists are pinned expected tables no
decision has asked to fold; the defaults registry is
the data itself; the feed extensions stand alone per
folder by the project's own contract; the 3 signers are
independent implementations on purpose; the vendored
licenses keep their folders self-contained. The growth
areas are clean, and the long tail of ordinary test
boilerplate is the part the standing audit directs be
factored file by file, when a file's own repetition
starts hiding differences, and never by a suite-wide
pass. There is no accidental mass to cut.

The change the numbers support is the statistics
record's correction, made with this audit: total latent
code 3.69% of the tree (near copies 3.11%, templated
lines 0.63%, exact copies 0.02%), non-latent code
96.31%, audit date 2026-11-16, with the figure mentions
in AGENTS.md and PROTOCOL.md corrected to the same
numbers. The latent check stands as it stood, a
warning and never a gate, and the documentation's
language stands unsoftened: the figure it states is
the figure the measure reads.
