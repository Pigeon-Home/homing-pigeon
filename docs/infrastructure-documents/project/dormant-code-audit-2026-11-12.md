# Dormant code: the fresh audit, 2026-11-12

This record is the fresh dormant-code audit the statistics
record has owed since the tree grew past the measure its
non-latent figure rests on. The standing figure — non-latent
96.83%, from near copies at 3.17% of the tree and exact
copies at 0.03% — was measured on 2026-11-09
(dormant-code-audit.md) on a tree of 20,435,240 tokens.
The tree now stands at 24,933,926 tokens. The conductor
asked whether the standing limit — duplicate or latent code
under 5% of the tree — still holds after that growth, and
this audit answers with the project's own tool,
`runner/tools/duplication_audit.py`, by the same method the
two standing audits used, so the three measures can be read
against each other: a sliding window of 8 normalized
non-blank, non-comment lines over the Python files for
near-duplicate code; exact copies by file hash over the
whole tree; and a scan for Python files nothing references.

The growth since the 2026-11-09 measure, and its shape:

- **The Q165 test family.** The briefing guard's
  contradiction module (runner/tests/
  test_briefing_contradiction.py) grew by some 70,000 lines
  to 83,208 lines: firing and silent shape lists of 11,745
  entries each, pinning the ledger's separator shapes over
  the whole of Unicode both ways, on the fixture and on the
  shipped layer.
- **The Q167 growth.** The same module grew again by some
  hundreds of lines for the spaced-token families — 273,626
  shapes derived by category and standing — and the guard
  itself grew in runner/ops/briefing.py.
- **The banked corpora.** The Germany bank 65 landing and
  the de_dust campaign records added data files — harvested
  run records, not Python — which grow the tree's line count
  without entering the window measure at all.
- **The denominator.** Tracked lines grew from 1,332,758
  at the 2026-11-09 measure to about 1.49 million.

## Supposition (written before the measurement, 2026-11-12)

The prediction is committed before the measurement exists,
so the record shows what was expected against what is found.

What the Q165 and Q167 families do to the window measure,
reasoned from their shape before any number is run:

- **A shape list is data, not copied code.** Each entry of
  the firing and silent lists is one line carrying one
  shape — a sentence that differs from its neighbours in
  the separator character it pins. A window of 8 normalized
  lines over list data therefore contains 8 distinct
  shapes; it repeats only if the same 8 shapes recur in the
  same order somewhere else, which the lists' construction
  (each shape once per list, firing and silent lists
  differing by construction) does not produce. The lists
  add tens of thousands of lines to the Python denominator
  while adding almost no repeated windows.
- **The scaffolding around the lists does repeat.** The
  test methods that walk the lists share their assertion
  blocks — the same 8-plus lines of subTest, assertEqual
  and findings plumbing, method after method. Those blocks
  are genuine repeated windows, and the module's growth
  carries more of them than any single landing since the
  last audit. This is the one force pushing the near share
  up.
- **The banked corpora push only the denominator.** Data
  files are not Python; the window measure never sees them,
  and their lines dilute every share stated against the
  tree.
- **The deliberate families stand where they stood.** The
  airgap OVERVIEW fixture, the divergence exhibits and the
  feed-extension skeleton — the duplicated mass the standing
  audits priced — did not grow with this quarter's work.

The supposition, stated as numbers to be measured against:

1. **Near-duplicate share of the tree: between 2.6% and
   3.2%, with a point expectation near 2.9%** — a fall from
   3.17%, not a rise. The Q165 module's scaffolding adds
   repeated windows, but the denominator grew by about a
   sixth and the growth's largest single piece is
   per-shape-distinct data. The non-latent figure therefore
   improves toward 97.1%, and the 5% limit holds with more
   room than the 2026-11-09 audit measured.
2. **Exact copies: still at or under 0.1% of the tree,**
   point expectation 0.03%. The vendored license pair
   persists; the banked corpora are distinct records, not
   copies of one another; no code file is an exact copy of
   another code file.
3. **Total latent (near plus exact): under 3.3%** — the
   tree stands well inside its 5% limit after the jump.
4. **Unreferenced Python files: 0.** The layout guard and
   the suite's discovery keep every Python file either
   imported, discovered, or invoked by path.
5. **The composition is unchanged in kind:** tests still
   carry nearly all of the near-duplicate lines, and the
   airgap fixture remains the largest single contributor.
   The Q165 module's scaffolding repetition is real but is
   not the largest contributor.

## Method

As the standing audits state it, operationalized in
`runner/tools/duplication_audit.py` and run by that tool on
the head named in the measurement section below. Shares are
stated against the whole tree's tracked lines and against
the Python lines — the same two denominators the standing
figures carry. The non-latent figure is 100 minus the
near-duplicate share, the standing derivation, with the
exact share stated beside it.

## Measurement

Owed: the measure runs after this supposition stands on
main, and its figures and the conclusions against the
supposition are recorded here in the same place.
