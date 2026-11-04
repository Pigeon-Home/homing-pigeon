# Findings — docs/steady/reports/report.md

Source: docs/steady/reports/report.md, reviewed at main 52f64508.
Sentence units: 55. Flagged: 5. Categories: pre-release 55, post-release 0.

A regression and coverage record from a box with no PyPI: 3 passes, what the red pass actually found, a new stdlib coverage tool, and the before-and-after tables. The narrative chains tightly — every table is introduced by the prose it answers to, and the unreachable-arms list at the end hands its decision to the reader by name. The non-sentences are the stamp comment (unit 1) and the 4 table header rows (units 9, 30, 36, 52); every data row is counted as a unit and flows as a record.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: c0000327-6a7b-42df-81b9-21136287db1c -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "One box with no PyPI ran the whole…" | pre-release | flows |  |
| 3 | "Nothing here needed a package from outside the…" | pre-release | flows |  |
| 4 | "Cores \| 2" | pre-release | flows |  |
| 5 | "Python \| 3.13.18" | pre-release | flows |  |
| 6 | "Packages \| the standard library and pytest; no…" | pre-release | flows |  |
| 7 | "PyPI \| unreachable (the egress refuses it)" | pre-release | flows |  |
| 8 | "The ledger lines are the last four in…" | pre-release | flows |  |
| 9 | "Pass \| Tree \| Verdict" | pre-release | flagged | Table header row, structure rather than a sentence |
| 10 | "1 \| `a2b5e564` as pulled \| red: 13…" | pre-release | flows |  |
| 11 | "2 \| with the fixes below \| green,…" | pre-release | flows |  |
| 12 | "3 \| with the count fix \| green,…" | pre-release | flows |  |
| 13 | "4 \| the same work on main at…" | pre-release | flows |  |
| 14 | "Pass 1 found three things, none of them…" | pre-release | flows |  |
| 15 | "Ten property modules imported hypothesis at the top,…" | pre-release | flows |  |
| 16 | "The suite's older property modules already guard the…" | pre-release | flows |  |
| 17 | "These ten now fall back to `runner/tests/_hypothesis_shim.py`: strategies…" | pre-release | flows |  |
| 18 | "The three seed-hook tests that need hypothesis itself…" | pre-release | flows |  |
| 19 | "`build.yml` and `python-range.yml` install hypothesis and now forbid…" | pre-release | flows |  |
| 20 | "`test_gamma.T.test_bad` is not a suite test." | pre-release | flows |  |
| 21 | "It is the failing fixture `test_parallel_runner` builds in…" | pre-release | flows |  |
| 22 | "A lone re-run of an id that does…" | pre-release | flows |  |
| 23 | "The fixture's output is now captured, and `failing_ids`…" | pre-release | flows |  |
| 24 | "Pass 2 counted 3704 tests of 7409." | pre-release | flows |  |
| 25 | "One shard's interpreter printed three `ResourceWarning` lines after…" | pre-release | flows |  |
| 26 | "The tail is now anchored on the last…" | pre-release | flows |  |
| 27 | "The warnings themselves are still there: a test…" | pre-release | flows |  |
| 28 | "`runner/tools/stdlib_coverage.py` is new: line coverage from `sys.monitoring`, every…" | pre-release | flows |  |
| 29 | "It counts statements, not branches, and misses children…" | pre-release | flows |  |
| 30 | "\| Statements \| Never run \| Covered" | pre-release | flagged | Table header row, structure rather than a sentence |
| 31 | "Before \| 37937 \| 417 \| 98.90%" | pre-release | flows |  |
| 32 | "After \| 37937 \| 322 \| 99.15%" | pre-release | flows |  |
| 33 | "Both runs passed (7416 tests counted, 250 child…" | pre-release | flows |  |
| 34 | "The data is `coverage-before.json` and `coverage-after.json`; the gap…" | pre-release | flows |  |
| 35 | "`runner/tests/test_local_rig_gaps.py` holds 41 deterministic tests for arms that…" | pre-release | flows |  |
| 36 | "File \| Before \| After" | pre-release | flagged | Table header row, structure rather than a sentence |
| 37 | "`extensions/pi-health/pi_health.py` \| 92.3% \| 99.1%" | pre-release | flows |  |
| 38 | "`guard/panic.py` \| 90.2% \| 96.4%" | pre-release | flows |  |
| 39 | "`ops/exec.py` \| 97.0% \| 99.0%" | pre-release | flows |  |
| 40 | "`wire/dtlsproto.py` \| 98.5% \| 99.2%" | pre-release | flows |  |
| 41 | "`cloud/send_job.py` \| 95.4% \| 96.5%" | pre-release | flows |  |
| 42 | "`wire/verify.py` \| 95.4% \| 96.2%" | pre-release | flows |  |
| 43 | "`wire/transports.py` \| 99.0% \| 99.7%" | pre-release | flows |  |
| 44 | "`guard/extreview.py` \| 98.7% \| 99.6%" | pre-release | flows |  |
| 45 | "`guard/sandbox.py` \| 98.8% \| 100.0%" | pre-release | flows |  |
| 46 | "`extensions/softflowd-feed/softflowd_feed.py` \| 99.6% \| 100.0%" | pre-release | flows |  |
| 47 | "`pi_health._mem_avail_pct_windows` had run nowhere: CI's Windows legs do…" | pre-release | flows |  |
| 48 | "It now runs against a stand-in `GlobalMemoryStatusEx` that…" | pre-release | flows |  |
| 49 | "Each of these is guarded by an earlier…" | pre-release | flows |  |
| 50 | "They are not tested, because a test would…" | pre-release | flows |  |
| 51 | "Each is a decision for the conductor: keep…" | pre-release | flows |  |
| 52 | "Where \| Why nothing reaches it" | pre-release | flagged | Table header row, structure rather than a sentence |
| 53 | "`pi_health.py:203-204` \| `int(.., 16)` after a regex that…" | pre-release | flows |  |
| 54 | "`training_watch.py:611-612` \| `float()` after a regex that admits…" | pre-release | flows |  |
| 55 | "`security.py:226, 228` \| `_rx_walk` handles repeats and branches…" | pre-release | flows |  |
