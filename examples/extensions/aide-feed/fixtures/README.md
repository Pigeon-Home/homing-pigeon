# AIDE Feed fixtures

- `aide-check.txt` — a **trimmed copy of a real captured
  AIDE check report** (AIDE 0.18.6, scoped config, measured
  2026-10-19): the header, summary, Added and Changed
  sections, and one detailed-change block are verbatim;
  the database-attributes tail and the measurement
  harness's own run line were cut to keep the fixture
  small. One added entry, one changed entry, no removed
  entries.
- `aide-no-differences.txt` — a crafted no-differences
  report in the same format, for the quiet path: AIDE's
  "found no differences" summary with zero entries in
  every class.
