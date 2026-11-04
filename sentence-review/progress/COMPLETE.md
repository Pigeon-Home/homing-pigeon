# Sentence review — complete

The sentence-by-sentence review is complete. Every 1 of the 186
in-scope documents in INDEX.md has a findings file in findings/;
coverage was verified from the tree itself at the consolidation,
document by document, with no document missing and no findings
file left over. INDEX.md now stands at done for all 186.

## Totals (counted from the findings files)

| Phase | Documents | Sentence units | Flagged | Pre-release | Post-release |
|---|---|---|---|---|---|
| Phase 1 | 3 | 791 | 12 | 771 | 20 |
| Shard 1 | 61 | 7,136 | 185 | 6,893 | 243 |
| Shard 2 | 61 | 8,831 | 333 | 8,596 | 235 |
| Shard 3 | 61 | 13,028 | 231 | 12,981 | 47 |
| **Total** | **186** | **29,786** | **761** | **29,241** | **545** |

## Genuine prose defects

Of the 761 flagged units, the great majority are structure the
extraction counted as units: table header and separator rows, YAML
front matter and kramdown markers in the drafts, HTML stamp and
source comments, horizontal rules, image and badge lines, section
labels, and sentences split by their source formatting. The
genuine prose defects — the places where the writing itself
breaks — are few:

- docs/ietf/draft-slutsky-homing-pigeon/submitted/draft-slutsky-homing-pigeon-01.md,
  unit 192: a term is missing where the empty backquotes stand.
  The sentence gives the file pattern (`.job.txt`) but the word it
  defines never appears, so the naming rule cannot be followed as
  written. The draft is frozen as submitted; the defect stands in
  the posted text.
- The same draft, unit 574: a fragment sentence — "The transport
  credentials and the HMAC secret, which…" names its subjects and
  makes no statement about them; the unit before does not lead
  into it and it hands nothing to the unit after.
- docs/FUTURE.md, units 1, 2, 3, 17, 18 and 23: the sketch list's
  shorthand — a word run with no sentence in it (unit 1), a shard
  trailing into its own question (2), a garbled run whose idea
  cannot be followed (3), a fragment answering its own question
  (17), a noun run with no verb (18), and a heading shard running
  on into its definition (23).
- docs/infrastructure-documents/project/layout.md, unit 3:
  "The only list." — a fragment whose referent cannot be
  recovered from the entries around it.
- docs/steady/project/hosting.md, units 2 and 46: verb-less
  thesis fragments standing as sentences ("A provisioner, not a
  dispatcher." / "As a feature, not a service.").
- docs/steady/reports/germany-rig-2026-10-28.md, unit 14:
  "1 CPU." — a spec shard standing entirely alone, never carried
  into a sentence.
- docs/steady/reports/release.md, unit 25: "A forum note." — a
  3-word fragment standing alone in the narrative; the note it
  gestures at is never carried into a sentence.
- docs/ietf/notes/trim-02.md, unit 1: a verb-less instruction
  fragment ("Read against…") opening the note, standing before
  its first full sentence.

## How to read these totals

- Segmentation was not identical in every phase. Phase 1 merged
  multi-item list runs into single units where the source
  formatting ran them together (README.md units 15, 25, 144, 146
  and 168–169 are merged runs; the whole Documentation checklist
  of docs/PROTOCOL.md is its unit 579), while the shards counted
  each list item and each table row as its own unit. Two
  sentences also stand recorded as 1 unit where the source runs
  them together (the -01 draft, unit 116). The unit counts are
  therefore close across phases but not segmented identically,
  and the totals should be read with that in mind.
- docs/FUTURE.md's findings header says "Flagged: 6"; its table
  holds 7 flagged rows. The totals above count the tables, so
  the header lines across all 186 findings files sum to 760
  flagged against the tables' 761.
- progress/shard-3.md records docs/steady/seats/questions.md at
  1 flagged unit; its findings file records 77, of which 76 are
  the document's HTML stamp comments. The findings file governs,
  and the totals above follow it.
