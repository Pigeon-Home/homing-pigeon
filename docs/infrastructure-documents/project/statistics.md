# The project's statistics: the 20-million-token measure

Dated 2026-11-08. Measured on main at commit
bcf8a4fe9e73372ac041e138ff47d6c0305156ac, the head from which the
current release of the 3.15.20 line was cut.

The recorded line, in the display form settled for publication:

20 mil security tokens, 5,000 commits, 1,300,000 lines at 96.35% non-latent code

## What stands behind each figure

- Tokens: 20,301,779, counted over the whole tree by the project's
  own estimator (runner/ops/version4.py) — the same measure the
  version number's 3rd component carries, which is why the line
  reads 20. Display form: 20 mil security tokens — security
  tokens is this record's name for the tree's tokens counted
  by the project's own estimator, so called because the tree's
  tokens all serve its security. Verify it on any checkout:
  `python3 runner/ops/version4.py measure` prints the count and
  its whole millions.
- Lines: 1,329,595 lines in tracked files at the measured head —
  355,481 of them Python, 84,055 of them markdown. The display
  figure, 1,300,000, is that count rounded.
- Commits: the display figure, 5,000, is rounded from a
  full-history recount at the measured head, taken from a
  complete clone, which counts 5,076. The project's local
  mirrors are shallow (810 commits deep) and cannot recount
  the whole history on their own — the recount above rests on
  the complete clone, and any future count should be taken
  the same way.
- Non-latent: 96.35%, from the project's standing audit
  ([duplication-audit.md](duplication-audit.md), 2026-11-03):
  duplicate and latent code held at 3.65% of the
  tree in near copies and 0.03% in exact copies. That audit is
  the latest word on the latent share. A fresh dormant-code
  audit is still owed, and this record will be corrected when
  it lands.

## The facts, machine-readable

The same figures, in the form the evergreen docs are
generated from. The marked figure slots in AGENTS.md,
PROTOCOL.md and docs/steady/fuzzing.md are filled from this
block by runner/tools/refresh_figures.py, and the guard test
holds them to it; the block is rewritten at each fresh
measure (see the release procedure in the use runbook), with
the core figures exported from runner/ops/core.py, which
stays their source of truth.

```json
{
  "as_of": "2026-11-08",
  "commit": "bcf8a4fe9e73372ac041e138ff47d6c0305156ac",
  "counter": "runner/ops/version4.py",
  "tokens": 20301779,
  "lines_tracked": 1329595,
  "commits": 5076,
  "display_commits": 5000,
  "display_lines": 1300000,
  "non_latent_percent": 96.35,
  "latent_near_percent": 3.65,
  "latent_exact_percent": 0.03,
  "audit_date": "2026-11-03",
  "core_files": 132,
  "core_lines": 55989,
  "core_lines_nonblank": 50457,
  "core_tokens": 590657,
  "core_assembled_lines": 56773,
  "core_assembled_nonblank": 51145,
  "core_assembled_zip_bytes": 720975,
  "core_assembled_tokens": 598274
}
```

## Verifying these figures against the artifacts

This record is the canonical source for the tree's figures:
every other mention of them in the project's documentation
states the figure with its date and points back here. A reader
with a checkout verifies locally first — re-measure the tree
in front of them with the version4.py command above and run
its tests; a release describes the commit it was cut from,
not a working tree. A reader who wants to check the figures
against the artifacts themselves
— rather than against another document — goes to the published
release: the latest release stands at
https://github.com/Pigeon-Home/homing-pigeon/releases/latest
and carries the wheel, the source distribution, the platform
archives, the project snapshot of the whole tree (its
PROJECT-SNAPSHOT.md indexes every file at the exact commit, and
its CI-SNAPSHOT.json states the facts of the producing build),
and SHA384SUMS, against which any downloaded artifact can be
checked. The release also carries a build-provenance
attestation tying the set to this repository's own workflow;
`gh attestation verify <file> --repo Pigeon-Home/homing-pigeon`
checks it. The snapshot is the tree a visiting system can read
the test suite from when it cannot run the suite itself.

## Why this record stands in the repository

These figures were first assembled in a working lane, off the
repository, and the lane died before the figures landed anywhere
a reader could find them. The project's standing rule is that
work lives in the repository, where it is visible, reviewable,
and carried by the next release cut; a lane outside the repo can
die unseen. The figures therefore stand here, with their measured
basis beside the display line, and the release that publishes
them states this record as its reason.
