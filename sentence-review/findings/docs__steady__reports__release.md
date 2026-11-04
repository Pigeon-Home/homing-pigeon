# Findings — docs/steady/reports/release.md

Source: docs/steady/reports/release.md, reviewed at main 8696f0cc.
Sentence units: 94. Flagged: 10. Categories: pre-release 94, post-release 0.

A release-night report for 3.14.43: the blocked CI log, the guard jobs, the cut timeline, and the asset table, in 4 tables. 1 markup unit, the tables' structure, and 1 orphaned fragment are the breaks. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587 -->" | pre-release | flagged | An HTML agent-stamp comment standing as the first unit — markup where the document's first sentence should be |
| 2 | "Written 30-OCT 6:36PM PST, while the tag build…" | pre-release | flows |  |
| 3 | "The findings that preceded this, written when the…" | pre-release | flows |  |
| 4 | "The version on main was 3.14.43." | pre-release | flows |  |
| 5 | "Four full-matrix builds on four 3.14.43 commits had…" | pre-release | flows |  |
| 6 | "The cut attempted on `b3800a18` at 6:10PM PST…" | pre-release | flows |  |
| 7 | "The CI log could not be read from…" | pre-release | flows |  |
| 8 | "The release had a deadline of 7:00PM PST." | pre-release | flows |  |
| 9 | "Grok could read the log." | pre-release | flows |  |
| 10 | "From it (forum, 30-OCT 6:14PM PST): on `b3800a18`…" | pre-release | flows |  |
| 11 | "Two minutes exactly." | pre-release | flows |  |
| 12 | "That explains every symptom on the record:" | pre-release | flows |  |
| 13 | "No test was named because `KeyboardInterrupt` derives from…" | pre-release | flows |  |
| 14 | "The dead-shard annotation added in `0bb97efe` never fired…" | pre-release | flows |  |
| 15 | "The 20-minute wall clock was not involved; the…" | pre-release | flows |  |
| 16 | "On Windows a console control event is delivered…" | pre-release | flows |  |
| 17 | "The shards were in the parent's group." | pre-release | flows |  |
| 18 | "A shard that raised such an event --…" | pre-release | flows |  |
| 19 | "`a9bd3dc2` (Grok, `release: 3.14.43 — a Windows shard…" | pre-release | flows |  |
| 20 | "`runner/tools/run_tests_parallel.py`: on Windows each shard is started with…" | pre-release | flows |  |
| 21 | "On POSIX the branch that sets up the…" | pre-release | flows |  |
| 22 | "The wait itself now catches `KeyboardInterrupt`: the shard…" | pre-release | flows |  |
| 23 | "The output helper's `except Exception` became `except (Exception,…" | pre-release | flows |  |
| 24 | "`runner/tests/test_parallel_runner.py`: 17 lines pinning the behaviour." | pre-release | flows |  |
| 25 | "A forum note." | pre-release | flagged | A 3-word fragment ("A forum note.") standing alone in the narrative — the note it gestures at is never carried into a sentence |
| 26 | "It was landed as a `release:` commit for…" | pre-release | flows |  |
| 27 | "Build 41154333227 on `a9bd3dc2`, created 01:14:07Z." | pre-release | flows |  |
| 28 | "| Job | Result | Note |" | pre-release | flagged | A table header row — structure, not a sentence |
| 29 | "|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 30 | "| scope | success | |" | pre-release | flows |  |
| 31 | "| build-linux, build-linux-arm64, build-macos, build-macos-x86_64, build-pi-light, build-python, build-windows-arm64…" | pre-release | flows |  |
| 32 | "| test-macos | **failure** | 5m43s; not in…" | pre-release | flows |  |
| 33 | "See below. |" | pre-release | flows |  |
| 34 | "| test | success | green at 01:24:56Z…" | pre-release | flows |  |
| 35 | "| build-windows | **success** | green at 01:25:28Z,…" | pre-release | flows |  |
| 36 | "The nine jobs the cut guard requires --…" | pre-release | flows |  |
| 37 | "On `test-macos`: the dead-shard annotation from `0bb97efe` did…" | pre-release | flows |  |
| 38 | "The annotation took the ordinary dead-shard path, not…" | pre-release | flows |  |
| 39 | "The same leg was green on `b3800a18` before…" | pre-release | flows |  |
| 40 | "It is noted, not chased; it is outside…" | pre-release | flows |  |
| 41 | "The audit seat's driver gated on the nine…" | pre-release | flows |  |
| 42 | "In the same second a second dispatch arrived…" | pre-release | flows |  |
| 43 | "`cut-release` serialises on its own concurrency group, so…" | pre-release | flows |  |
| 44 | "| Run | Input sha | Result |" | pre-release | flagged | A table header row — structure, not a sentence |
| 45 | "|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 46 | "| 41155283846 | `a9bd3dc221814e3032bade9c5268693d3bce8e2a` | **success**." | pre-release | flows |  |
| 47 | "Every guard step passed; the tag was pushed.…" | pre-release | flows |  |
| 48 | "| 41155284252 | `a9bd3dc22` | failure at `actions/checkout`:…" | pre-release | flows |  |
| 49 | "It never reached the guard, so it changed…" | pre-release | flows |  |
| 50 | "The driver, reading "the newest cut-release run", reported…" | pre-release | flows |  |
| 51 | "`git ls-remote --tags origin v3.14.43` returns the tag…" | pre-release | flows |  |
| 52 | "The two `release:` commits that sat on main…" | pre-release | flows |  |
| 53 | "They stay in history as what they were." | pre-release | flows |  |
| 54 | "Build 41155303320 on `refs/tags/v3.14.43`, started 01:26:50Z." | pre-release | flows |  |
| 55 | "On a tag, `scope` reports `corpus_only=false` unconditionally, every…" | pre-release | flows |  |
| 56 | "At 01:34Z: `scope`, `test-macos`, and all eight `build-*`…" | pre-release | flows |  |
| 57 | "The jobs after `release` are filled in below." | pre-release | flows |  |
| 58 | "This seat cannot reach the mirrors directly." | pre-release | flows |  |
| 59 | "`pypi.org` does not resolve from the shell (the…" | pre-release | flows |  |
| 60 | "GitHub is reachable through `gh`." | pre-release | flows |  |
| 61 | "So the verification this seat can perform is:" | pre-release | flows |  |
| 62 | "The tag build's `pypi-publish`, `sourceforge` and `gitlab` jobs…" | pre-release | flows |  |
| 63 | "Each is a real check, not a fire-and-forget:…" | pre-release | flows |  |
| 64 | "The GitHub Release itself: `gh release view v3.14.43`,…" | pre-release | flows |  |
| 65 | "Muse's independent mirror check from the rig side,…" | pre-release | flows |  |
| 66 | "That is the external confirmation." | pre-release | flows |  |
| 67 | "Tag build 41155303320: `completed/success` at 01:41:44Z (30-OCT 6:41PM…" | pre-release | flows |  |
| 68 | "The deadline was 7:00PM PST." | pre-release | flows |  |
| 69 | "| Step | When (UTC) | Result |" | pre-release | flagged | A table header row — structure, not a sentence |
| 70 | "|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 71 | "| `release` | 01:39:57 published | success." | pre-release | flows |  |
| 72 | "GitHub Release `v3.14.43`, not a draft, not a…" | pre-release | flows |  |
| 73 | "| `pypi-publish` | 01:41:12 | success (PyPI project…" | pre-release | flows |  |
| 74 | "The action fails on a refused upload). |" | pre-release | flows |  |
| 75 | "| `gitlab` | 01:41:44 | success (release created…" | pre-release | flows |  |
| 76 | "| `sourceforge` | 01:41:44 | success (files uploaded…" | pre-release | flows |  |
| 77 | "The release's 13 assets, read over the REST…" | pre-release | flows |  |
| 78 | "| Asset | Bytes |" | pre-release | flagged | A table header row — structure, not a sentence |
| 79 | "|---|---:|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 80 | "| `homing-pigeon-linux-x86_64-3.14.43.tar.gz` | 85,407,988 |" | pre-release | flows |  |
| 81 | "| `homing-pigeon-linux-arm64-3.14.43.tar.gz` | 83,608,730 |" | pre-release | flows |  |
| 82 | "| `homing-pigeon-pi-light-arm64-3.14.43.tar.gz` | 83,611,998 |" | pre-release | flows |  |
| 83 | "| `homing-pigeon-macos-arm64-3.14.43.tar.gz` | 57,821,541 |" | pre-release | flows |  |
| 84 | "| `homing-pigeon-macos-x86_64-3.14.43.tar.gz` | 58,965,139 |" | pre-release | flows |  |
| 85 | "| `homing-pigeon-windows-x86_64-3.14.43.zip` | 60,441,233 |" | pre-release | flows |  |
| 86 | "| `homing-pigeon-windows-arm64-3.14.43.zip` | 59,820,417 |" | pre-release | flows |  |
| 87 | "| `homing-pigeon-project-3.14.43.tar.gz` | 39,091,971 |" | pre-release | flows |  |
| 88 | "| `pigeon_home_runner-3.14.43-py3-none-any.whl` | 555,028 |" | pre-release | flows |  |
| 89 | "| `pigeon_home_runner-3.14.43.tar.gz` | 501,181 |" | pre-release | flows |  |
| 90 | "| `SBOM.spdx.json` | 49,159 |" | pre-release | flows |  |
| 91 | "| `BUILD-PROVENANCE.json` | 305 |" | pre-release | flows |  |
| 92 | "| `SHA384SUMS` | 1,619 |" | pre-release | flows |  |
| 93 | "Muse's independent check from the rig side, posted…" | pre-release | flows |  |
| 94 | "Two seats, two routes, the same answer: 3.14.43…" | pre-release | flows |  |
