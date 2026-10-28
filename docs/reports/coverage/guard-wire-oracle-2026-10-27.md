# Line coverage: guard, wire and oracle (2026-10-27)

<!-- Agent-Stamp: b000092f-e5ef-4e93-bcc6-e35f92ee2ab1 -->

Measured on a box with no package index, so with
`runner/tools/linecov.py` (the standard library's `sys.monitoring`,
Python 3.13) instead of coverage.py, and without `hypothesis`: the ten
property and fuzz modules skip here (`require_hypothesis` in
`runner/tests/_compat.py`). This is the air-gapped bench's view of the
suite. Lines only, no branches. The data beside this file is the
tool's report in coverage.py's JSON shape, and
`runner/tools/coverage_gaps.py` reads it unchanged.

## What was measured

| Report | Sources | Tests |
|---|---|---|
| `guard-wire-oracle-2026-10-27-before.json` | `runner/guard/`, `runner/wire/`, `runner/oracle/` | every `runner/tests/test_*.py`: 7,306 tests, OK, 49 skipped |
| `guard-wire-oracle-2026-10-27-after.json` | the same | 7,325 tests, 49 skipped; the one failure was a skip registry line removed in `045562a` while the pass ran |

The first pass on this box ran 13 reds, every one a module that needs
`hypothesis` and failed at import instead of skipping. They skip now
off CI and still fail under CI.

## Result

7,470 statements. Never run: 107 before, 89 after (98.6% to 98.8%).

| Module | Before | After |
|---|---:|---:|
| `runner/wire/dtlsproto.py` | 16 | 7 |
| `runner/guard/extreview.py` | 6 | 1 |
| `runner/oracle/learning.py` | 5 | 2 |
| `runner/guard/security.py` | 6 | 5 |

The tests are `runner/tests/test_reader_edges_offline.py` and the DTLS
truncation cases in `runner/tests/test_coverage_lane.py`.

## What stays unrun, and why

| Lines | Why no test is aimed at them |
|---|---|
| `dtlsproto.py:x25519` 186-187 | the final swap: scalar clamping clears bit 0, so the last swap is always 0 |
| `security.py:_rx_subpatterns` 226, 228 | the walker handles repeats and alternations before it asks for subpatterns |
| `verify.py` 747-757 | the fallbacks for a missing security module, `pragma: no cover` |
| `verify.py` 147, 217, 264, 291, 322, 912, 957, 986 | checks behind an extractor that only yields objects, a parser that only raises `ValueError`, and fingerprint calls that do not raise on a string |
| `panic.py` 164, 185, 203, 229, 237, 296 and the other `set_logger` lines | `global` statements: linecov counts them, Python runs nothing for them |
| `security.py` 516, `remediation.py` 470, 483, 499, 558 | Windows and PowerShell paths, run in the Windows job |
