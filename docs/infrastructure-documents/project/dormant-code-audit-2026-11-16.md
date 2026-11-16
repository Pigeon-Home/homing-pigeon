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
