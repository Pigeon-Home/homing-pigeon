# Dormant code: the fresh audit, 2026-11-13

This record is the dormant-code audit the Q172 landing
owes: the first run of the audit since
`runner/tools/duplication_audit.py` gained the templated
measure AGENTS.md rule 16 names, and the re-measure of the
tree the Q165 fold leaves behind. The standing figure
before this run — non-latent 96.9%, from near copies at
3.1% of the tree and exact copies at 0.02% — was measured
on 2026-11-12 (dormant-code-audit-2026-11-12.md) by a tool
that could not see a templated list: a window of 8 whole
lines over entries that differ in one character never
repeats, so the Q165 lists read as distinct data and
diluted the shares they should have raised.

The owner's decision (Q171, AGENTS.md rule 16) is the
occasion: a list made by repeating one template is derived
when the test runs, and written out it counts as
duplicate. Q172 folds the Q165 lists into a derivation and
gives the audit the measure; this record states what the
measure saw before the fold and what it sees after, so the
fold's effect is a measurement, not an impression.

## Supposition (recorded before the measurement)

The suppositions are Q172's S4 and S5, recorded in the
questions file before any measurement in that lane:

- S4. The templated measure (lines equal once the varying
  token is masked, a masked group standing at the audit's
  own repetition scale of 8), run on the tree before the
  fold, names the Q165 lists in the briefing module — at
  least 70,000 of the module's lines. Run after the fold,
  the module's templated count falls by that mass, and the
  whole tree's templated count stands under 1% of the
  tree's lines.
- S5. The post-fold audit otherwise moves only by the
  smaller denominator: the window near-duplicate share
  rises from 3.1% by a few tenths at most, total latent
  (near plus templated plus exact, overlaps counted once)
  stays well under the standing 5% limit, and the change
  the numbers support is the statistics record's
  correction, not a cleanup.

The measure as built, stated once here because the
numbers below are its numbers: the templated measure
reads the lines of a written-out list — a list, tuple or
set literal of at least 8 elements — over the Python
files. Such a line counts when a group it belongs to,
counted over the tree's literal lines, stands at 8 or
more: either its exact line's own group, or the group of
lines equal to it once one token position is masked.
Single-token lines count only by exact repetition. Lines
outside a written-out list are not this measure's to
name: code that merely resembles other code is the window
measure's ground.

## Measurement

Measured by `runner/tools/duplication_audit.py` on the
tree before the fold (the 3.16.25.4 release head,
42c922bc4, the main head the landing was transplanted
onto) and on the fold's own commit (cd721a269). The
lane's first measure ran on an earlier head; the figures
below are the re-measure on the landing base, taken
first-hand at the landing, and the fold's own figures
(the briefing module's lines and tokens, its templated
count, and the tree's token delta) are unchanged by the
move, as the record below shows.

Before the fold:

- The whole tree is 1,501,662 lines in 1,424 tracked
  files; Python is 469,339 of those lines, in 687 files.
  The tree stands at 25,060,621 tokens.
- Near-duplicate Python: 46,360 lines, 3.09% of the tree
  — tests 40,901, production 5,459.
- Templated lines: 79,949, 5.32% of the tree — tests
  79,496, production 453. Of those, 76,209 stand in the
  briefing-contradiction module alone, of its 83,276
  lines: the Q165 lists, seen at last by the measure
  rule 16 names.
- Exact copies: 340 lines beyond the first copy, 0.02% of
  the tree — the same groups the standing audits found.
- Total latent (near and templated unioned per line,
  plus exact): 125,501 lines, 8.36% of the tree — over
  the standing 5% limit, and the Q165 lists are nearly
  all of the excess.
- Unreferenced Python files: 0. Generated files: 1, the
  ci-health snapshot, as before.

After the fold:

- The whole tree is 1,431,648 lines; Python is 399,325
  lines. The briefing module is 12,949 lines and
  118,979 tokens, down from 83,276 lines and 804,899
  tokens. The tree stands at 24,378,233 tokens.
- Near-duplicate Python: 46,360 lines — the same lines,
  now 3.24% of the smaller tree (tests 40,901,
  production 5,459). The largest contributors stand
  where they stood: the airgap OVERVIEW fixture (11,047),
  the divergence exhibits (5,528), the briefing module's
  scaffolding (2,829).
- Templated lines: 9,475, 0.66% of the tree — tests
  9,022, production 453. The briefing module carries
  5,735 of them: the earlier filings' smaller written
  lists, which no decision has asked to fold. The next
  largest are the defaults registry (1,973) and the
  divergence exhibits (686).
- Exact copies: 340 lines, 0.02% of the tree, unchanged.
- Total latent: 55,027 lines, 3.84% of the tree.
- Unreferenced Python files: 0. Generated files: 1, as
  before.

## Conclusions: the suppositions against the numbers

1. **S4, before the fold — held.** The measure names the
   Q165 lists: 76,209 templated lines in the briefing
   module, over the supposed 70,000. Every list line
   either repeats exactly or differs from its neighbours
   in the one separator token, as supposed.
2. **S4, after the fold — held.** The module's templated
   count falls by 70,474 lines (76,209 to 5,735), and the
   whole tree's templated count stands at 0.66% of the
   tree's lines, under the supposed 1%.
3. **S5 — held.** The near-duplicate share rises only by
   the smaller denominator, 3.09% to 3.24% — 0.15 of a
   point, inside "a few tenths at most". Total latent is
   3.84% of the tree, well under the standing 5% limit.
   The change the numbers support is the statistics
   record's correction, not a cleanup: the one mass over
   the limit was the Q165 lists, and the fold, not a
   sweep, removed it.
4. **What the pre-fold run adds to the record.** Read
   with the templated measure, the tree before the fold
   stood at 8.36% total latent — the 2026-11-12 audit's
   3.12% total was a figure of the window method alone,
   true of what that method sees and incomplete by rule
   16's lights. The 5% limit the conductor asked about on
   2026-11-12 held on the window measure and did not hold
   on the full one; after the fold it holds on both.

What this audit changes: statistics.md's facts are
corrected from this record — total latent 3.84% of the
tree (near 3.24%, templated 0.66%, exact 0.02%, overlaps
counted once), non-latent 96.16%, audit date 2026-11-13 —
and the figure mentions in AGENTS.md and PROTOCOL.md are
corrected to the same numbers with the same date. The
2026-11-12 audit stands as the previous measure; this
record supersedes its figures, not its analysis, and the
2026-11-03 audit (duplication-audit.md) remains the
family-by-family account.
