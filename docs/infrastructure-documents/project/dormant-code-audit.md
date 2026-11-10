# Dormant code: the fresh audit, 2026-11-09

This record is the fresh dormant-code audit the statistics
record has owed since the 2026-11-03 duplication audit
(duplication-audit.md). It re-measures the tree with the same
method that audit used, so the two measures can be read
against each other: a sliding window of 8 normalized
non-blank, non-comment lines over the Python files for
near-duplicate code; exact copies by file hash over the
whole tree; and a scan for Python files nothing references.
The measured commit is
4111ac4659145c8a6f4d2829ade2b1a35b9bdc24, the head of main
when this audit was opened.

The method now has a tool of its own in the tree,
`runner/tools/duplication_audit.py`, so the next audit runs
the measure instead of reconstructing it. The 2026-11-03
audit's output was preserved as prose; this one is preserved
as prose over a tool any reader can re-run on any checkout.

## Supposition (written before the measurement, 2026-11-09)

The prediction is committed before the measurement exists,
so the record shows what was expected against what is found.

The 2026-11-03 baseline: near-duplicate code 41,782 lines,
3.65% of a tree of 1,145,913 lines (12.76% of its 327,510
Python lines); exact copies 340 lines beyond the first copy,
0.03% of the tree; 0 unreferenced Python files; 0 generated
files checked in. The non-latent figure the statistics
record carries, 96.35%, is 100 minus the near-duplicate
share, with the exact share stated beside it.

Since that audit the tree has grown by about a sixth in
tracked lines and the Python by about a tenth, and the
growth's shape matters more than its size:

- **Test growth outruns production growth, and test code is
  where the repetition lives.** The work since 2026-11-03 is
  test-heavy by design — per-field test families and the
  variation families that stand around a found bug repeat
  their scaffolding by the hundred, and the divergence
  exhibits (family 2 of the standing audit) keep their
  self-contained shape as they grow. The near-duplicate
  share of the tree is therefore expected to rise.
- **The deliberate families persist.** The airgap OVERVIEW
  fixture (family 1) is frozen by design; the feed-extension
  skeleton (family 3) still stands in parallel copies; the
  3 signers (family 4) still mirror each other on purpose.
  Nothing since 2026-11-03 removed a family, and one remedy
  the standing audit recommends — a kept-in-step guard over
  the feed skeleton — reduces drift risk, not line count.
- **Production code grew more carefully than the tests.**
  The Oracle briefing work, the approval guard, and the
  release gate landed as new modules more than as copies,
  so the production near-duplicate share is expected to
  hold near its 0.43%-of-tree mark.

The supposition, stated as numbers to be measured against:

1. **Near-duplicate share of the tree: between 3.6% and
   4.3%, with a point expectation near 3.9%.** The
   non-latent figure therefore lands near 96.1% — a small
   move down from 96.35%, not up, driven by test-side
   growth. The standing limit (duplicate or latent code
   under 5% of the tree) holds.
2. **Exact copies: still at or under 0.1% of the tree.**
   The vendored license pair persists; refreshed upstream
   pins may add further vendored license text, so the line
   count beyond the first copy may grow past 340 while the
   share stays negligible. No code file is an exact copy of
   another code file.
3. **Unreferenced Python files: 0.** The layout guard and
   the suite's discovery keep every Python file either
   imported, discovered, or invoked by path.
4. **The composition is unchanged in kind:** the airgap
   fixture and the divergence exhibits remain the two
   largest contributors, and the feed extensions remain the
   family where a copy can silently become wrong behavior.

## Method

As the 2026-11-03 audit states its method, operationalized
in `runner/tools/duplication_audit.py`:

- **Near-duplicate.** For each tracked Python file, the
  lines are normalized — surrounding whitespace stripped,
  blank lines and comment lines dropped — and every window
  of 8 consecutive normalized lines is taken. A window that
  occurs at 2 or more distinct positions anywhere in the
  tree's Python (a second file, or a second place in the
  same file) is a repeated window, and every line position
  it covers counts once as a near-duplicate line. The
  method counts both sides of a repetition and misses
  clones shorter than 8 lines or heavily renamed, so the
  figure is an upper bound, as the standing audit reads it.
- **Exact copies.** Tracked files are grouped by content
  hash; in a group of 2 or more identical files, the lines
  of every copy past the first count as exact-copy lines.
- **Unreferenced files.** A tracked Python file counts as
  referenced when its module name or its path is named by
  another tracked file, or when it stands where the suite's
  discovery reaches it (runner/tests/). What the scan names
  is reported as it stands, with each name's disposition
  read by hand before the count is called.
- **Denominators.** Shares are stated against the whole
  tree's tracked lines and, where the standing audit states
  them, against the Python lines — the same two denominators
  the 2026-11-03 figures carry.
- **Generated files.** Files whose opening lines carry a
  generated marker ("generated by", "automatically
  generated", "do not edit") are counted and named; the
  standing audit found none checked in.

The measurement and its conclusions are added to this
record by the commit that runs the tool, in the section
below.
