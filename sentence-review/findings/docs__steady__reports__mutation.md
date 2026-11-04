# Findings — docs/steady/reports/mutation.md

Source: docs/steady/reports/mutation.md, reviewed at main cbb52068.
Sentence units: 59. Flagged: 0. Categories: pre-release 58, post-release 1.

Units 4-5 are figure captions; the figures are images. Units 7-18 are the run's stat list.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "This report belongs to package 3.7.30, measured with…" | pre-release | flows |  |
| 2 | "No new tag was cut." | pre-release | flows |  |
| 3 | "The tree is `reports/coverage-mutation-3.7.30` at e3d88e4." | pre-release | flows |  |
| 4 | "Mutants killed, by function" | pre-release | flows |  |
| 5 | "Mutants killed, pictured" | pre-release | flows |  |
| 6 | "Measured 2026-10-18 with mutmut 3.8.0, the same pin…" | pre-release | flows |  |
| 7 | "Scope is `runner/security.py` only (`only_mutate` in pyproject.toml)." | pre-release | flows |  |
| 8 | "Covered lines only." | pre-release | flows |  |
| 9 | "Four workers." | pre-release | flows |  |
| 10 | "537 mutants, 441 seconds." | pre-release | flows |  |
| 11 | "7.80 mutants per second." | pre-release | flows |  |
| 12 | "Killed: 458." | pre-release | flows |  |
| 13 | "Survived: 79." | pre-release | flows |  |
| 14 | "Score: 85.3%." | pre-release | flows |  |
| 15 | "Timeouts: 0." | pre-release | flows |  |
| 16 | "Suspicious: 0." | pre-release | flows |  |
| 17 | "Skipped: 0." | pre-release | flows |  |
| 18 | "No tests: 0." | pre-release | flows |  |
| 19 | "mutmut exits 0 with survivors." | pre-release | flows |  |
| 20 | "CI treats that the same way: the job…" | pre-release | flows |  |
| 21 | "The tag workflow is the only place this…" | pre-release | flows |  |
| 22 | "Killed share, 40 cells." | pre-release | flows |  |
| 23 | "One cell is 2.5 points." | pre-release | flows |  |
| 24 | "By function." | pre-release | flows |  |
| 25 | "Fully killed functions are one bar." | pre-release | flows |  |
| 26 | "Most of the 79 are wording. mutmut wraps…" | pre-release | flows |  |
| 27 | "The tests check that a weak secret or…" | pre-release | flows |  |
| 28 | "They do not check the sentence." | pre-release | flows |  |
| 29 | "About 30 of the survivors are that wrap,…" | pre-release | flows |  |
| 30 | "Those are not behavior changes a caller can…" | pre-release | flows |  |
| 31 | "A few are equivalent, so a test could…" | pre-release | flows |  |
| 32 | "`alphabet <= 1` changed to `< 1`." | pre-release | flows |  |
| 33 | "A one-character alphabet has `log2(1) == 0`, so…" | pre-release | flows |  |
| 34 | "`modes.get(feature, "off")` changed to `None` or `"OFF"`." | pre-release | flows |  |
| 35 | "Neither is a known mode, and the next…" | pre-release | flows |  |
| 36 | "The repeat check builds one extra copy of…" | pre-release | flows |  |
| 37 | "Both copies are long enough." | pre-release | flows |  |
| 38 | "The slice matches either way." | pre-release | flows |  |
| 39 | "`os.name != "nt"` changed to `!= "NT"`. `os.name`…" | pre-release | flows |  |
| 40 | "The survivors that are real gaps:" | pre-release | flows |  |
| 41 | "`sec_decide` is the low bar, 56 of 88…" | pre-release | flows |  |
| 42 | "The allow/deny return value is tested." | pre-release | flows |  |
| 43 | "The audit line is not." | pre-release | flows |  |
| 44 | "A mutant can drop `key_id`, pass `job_id=None`, or…" | pre-release | flows |  |
| 45 | "A non-dict `ctx` is also untested: forcing the…" | pre-release | flows |  |
| 46 | "`validate_shared_secret` does not pin the 128-bit line. `bits…" | pre-release | flows |  |
| 47 | "No test uses a secret whose estimate is…" | pre-release | flows |  |
| 48 | "The confinement validator can be called with `None`…" | pre-release | flows |  |
| 49 | "Startup still fails; the test does not read…" | pre-release | flows |  |
| 50 | "`_estimate_secret_entropy`, `_bump_counts`, `write_audit_entry`, `_enforce_bound`, and the dangerous environment-name…" | pre-release | flows |  |
| 51 | "The audit writer itself is fully killed (98…" | pre-release | flows |  |
| 52 | "The hole is the caller that fills the…" | pre-release | flows |  |
| 53 | "From the repo root. mutmut is not a…" | pre-release | flows |  |
| 54 | "CI pins 3.8.0." | pre-release | flows |  |
| 55 | "Expect about seven minutes for `runner/security.py`." | pre-release | flows |  |
| 56 | "A wider scope was measured before and rejected…" | pre-release | flows |  |
| 57 | "Do not treat 85.3% as a target." | pre-release | flows |  |
| 58 | "The mutants worth a test are the audit…" | post-release | flows |  |
| 59 | "The `XX` strings are not." | pre-release | flows |  |
