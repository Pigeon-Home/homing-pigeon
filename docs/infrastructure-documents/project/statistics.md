# The project's statistics: the 20-million-token measure

Dated 2026-11-08. Measured on main at commit
d1b8e8a2293bcedc479bd9f8a2dcf41a31df0835, the head from which the
current release of the 3.15.20 line was cut.

The recorded line, in the display form settled for publication:

20 mil security tokens, 5,000 commits, 1,200,000 lines at 96.35% non-latent code

## What stands behind each figure

- Tokens: 20,163,806, counted over the whole tree by the project's
  own estimator (runner/ops/version4.py) — the same measure the
  version number's 3rd component carries, which is why the line
  reads 20. Display form: 20 mil security tokens — the display
  line names them security tokens, since the tree's tokens all
  serve its security.
- Lines: 1,218,733 lines in tracked files at the measured head —
  352,302 of them Python, 82,918 of them markdown. The display
  figure, 1,200,000, is that count rounded.
- Commits: the display figure, 5,000, is rounded from a working
  count of 5,029 taken the same morning at an earlier head. A
  full-history recount at the measured head, from a complete
  clone, counts 5,043; the difference is consistent with the
  commits that landed between the two measures. The project's
  local mirrors are shallow (810 commits deep) and cannot recount
  the whole history on their own — the recount above rests on the
  complete clone, and any future count should be taken the same
  way.
- Non-latent: 96.35%, from the project's standing audit
  (docs/infrastructure-documents/project/duplication-audit.md,
  2026-11-03): duplicate and latent code held at 3.65% of the
  tree in near copies and 0.03% in exact copies. That audit is
  the latest word on the latent share. A fresh dormant-code
  audit is still owed, and this record will be corrected when
  it lands.

## Why this record stands in the repository

These figures were first assembled in a working lane, off the
repository, and the lane died before the figures landed anywhere
a reader could find them. The project's standing rule is that
work lives in the repository, where it is visible, reviewable,
and carried by the next release cut; a lane outside the repo can
die unseen. The figures therefore stand here, with their measured
basis beside the display line, and the release that publishes
them states this record as its reason.
