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

## Measurement (2026-11-12)

Measured by `runner/tools/duplication_audit.py` on the tree
at the head this audit's supposition stands on.

- The whole tree is 1,492,915 lines in 1,417 tracked files.
  Python is 465,493 of those lines, in 682 files.
- Near-duplicate Python: 46,329 lines. That is 3.1% of the
  whole tree, and 9.95% of the Python. Tests carry 40,870
  of those lines (2.74% of the tree); production carries
  5,459 (0.37% of the tree).
- Non-latent code: 96.9% — 100 minus the near-duplicate
  share, the standing derivation, with the exact share
  stated beside it.
- Exact copies: 340 lines beyond the first copy, 0.02% of
  the tree — the same groups the standing audits found:
  the 339-line license text vendored in 2 extension
  upstream folders (aide-feed's COPYING, suricata-feed's
  LICENSE), and a 1-line marker file standing in 2 copies
  in a reports folder. Identical empty `__init__.py` files
  add a group that contributes 0 lines. **No code file is
  an exact copy of another code file, anywhere.**
- Unreferenced Python files: 0.
- Generated files: the scan names 1 file,
  docs/steady/reports/ci-health.md — the same snapshot the
  2026-11-09 audit named, a record that declares itself
  generated on its face. No generated code is checked in.
- The largest contributors, in order: the airgap OVERVIEW
  fixture (11,036 repeated lines), the divergence exhibits
  (5,528), and the Q165 briefing-contradiction module
  (2,829).

## Conclusions: the supposition against the numbers

1. **The near-duplicate share — inside the band, above the
   point.** Predicted: a fall to between 2.6% and 3.2%,
   point 2.9%. Measured: 3.1%, a fall from 3.17% as
   supposed in direction, smaller than priced. The error is
   visible in the counts: repeated windows grew faster than
   the supposition allowed — near-duplicate lines rose from
   42,254 to 46,329 (about a tenth) while the tree grew by
   about a sixth — because the Q165 module's scaffolding
   repetition is real mass (2,829 repeated lines in that one
   module, the third-largest contributor in the tree), not
   the negligible residue the shape-list reasoning priced
   it at. The data-list reasoning itself held: the module
   is 83,208 lines and only 2,829 of them repeat, so its
   lists diluted far more than its scaffolding added. The
   non-latent figure improves to 96.9%, and the change the
   numbers support is the correction of the statistics
   record, not any cleanup.
2. **Exact copies — held.** 340 lines, 0.02% of the tree:
   the same line count as both standing audits, diluted by
   the bigger tree, as supposed.
3. **Total latent — held.** Near plus exact is 3.12% of
   the tree, under the supposed 3.3% and well inside the
   standing 5% limit. The limit the conductor asked about
   holds after the jump to 24,933,926 tokens, with 1.88
   points of room on the total.
4. **Unreferenced files — held.** 0, as supposed.
5. **Composition — held in kind.** Tests carry 40,870 of
   the 46,329 near-duplicate lines (88%); the airgap
   fixture remains the largest single contributor; the
   Q165 module stands third, a new name in the top ranks
   but not the largest, exactly the shape supposed.

What this audit changes: statistics.md's facts are
corrected from this record — non-latent 96.9%,
near-duplicate 3.1%, exact 0.02%, audit date 2026-11-12 —
and the figure mentions in AGENTS.md and PROTOCOL.md are
corrected to the same numbers with the same date, wording
untouched. The 2026-11-09 audit (dormant-code-audit.md)
stands as the previous measure; this record supersedes its
figures, not its analysis, and the 2026-11-03 audit
(duplication-audit.md) remains the family-by-family
account.
