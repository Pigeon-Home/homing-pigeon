# Line coverage: guard, wire and oracle (2026-10-27)

> Compressed summary. The full text is recoverable from git history at commit 1acc3f8516d986d05bf35d956571e45856735513.

2026-10-27, measured with runner/tools/linecov.py on the
air-gapped bench (no hypothesis; the property and fuzz modules
skip here). The whole suite ran: 7,306 tests before, 7,325
after, 49 skipped. Headline: 7,470 statements across
runner/guard/, runner/wire/ and runner/oracle/ — never run 107
before, 89 after: 98.6% to 98.8%.
