# Local regression pass and line coverage (2026-10-27)

> Compressed summary. The full text is recoverable from git history at commit 1acc3f8516d986d05bf35d956571e45856735513.

2026-10-27: the whole suite in one process under
runner/tools/linecov.py, Python 3.13, two cores. Before (tree
c6c1b73): 7,308 tests, 15 red, all from the box. After (tree
06888e0): 7,360 tests, 1 red — a NATS round-trip whose 25
second wait ran out under the traced run; it passes alone.
Headline: shipped code went from 99.00% (305 of 30,370 unrun)
to 99.51% (148 unrun); runner/tools/stamp_audit.py from 58.7%
to 98.8%.
