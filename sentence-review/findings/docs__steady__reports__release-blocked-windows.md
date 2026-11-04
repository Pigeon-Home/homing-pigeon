# Findings — docs/steady/reports/release-blocked-windows.md

Source: docs/steady/reports/release-blocked-windows.md, reviewed at main cbb52068.
Sentence units: 87. Flagged: 1. Categories: pre-release 87, post-release 0.

The table's rows are entries; a row split across units belongs to the same row. Units 75-79 are the closing list of unknowns.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Written 30-OCT 6:10PM PST." | pre-release | flows |  |
| 2 | "This is a record of findings, not a…" | pre-release | flows |  |
| 3 | "Nothing in it proposes a change; the open…" | pre-release | flows |  |
| 4 | "What happened next -- the cause read from…" | pre-release | flows |  |
| 5 | "The version on main is 3.14.43 (`pyproject.toml`, `runner/_version.py`,…" | pre-release | flows |  |
| 6 | "No tag `v3.14.43` exists." | pre-release | flows |  |
| 7 | "The cut did not happen because `cut-release.yml`'s guard,…" | pre-release | flows |  |
| 8 | "The failure text is not readable from this…" | pre-release | flows |  |
| 9 | "The last commit with a green `build-windows` is…" | pre-release | flows |  |
| 10 | "These are the mechanics found while trying to…" | pre-release | flows |  |
| 11 | "They are facts about the workflows as they…" | pre-release | flows |  |
| 12 | "**The guard.** `cut-release.yml` fetches the check runs on…" | pre-release | flows |  |
| 13 | "A missing job fails the guard with `no…" | pre-release | flows |  |
| 14 | "**Corpus-only pushes skip the matrix.** `build.yml`'s `scope` job…" | pre-release | flows |  |
| 15 | "When every path matches `CORPUS_ONLY` (`runner/tests/de_dust/*.jsonl`, `docs/project/campaign-standing-orders.md`, `docs/seats/.com.chat`,…" | pre-release | flows |  |
| 16 | "A skipped job leaves no check run." | pre-release | flows |  |
| 17 | "Every rig bank commit and every forum note…" | pre-release | flows |  |
| 18 | "`74cfa3f4` satisfied it on 30-OCT 12:29PM PST because…" | pre-release | flows |  |
| 19 | "**The rolling concurrency group cancels pending builds.** `build.yml`…" | pre-release | flows |  |
| 20 | "GitHub keeps one pending run per group: a…" | pre-release | flows |  |
| 21 | "With rig banks pushing every one to two…" | pre-release | flows |  |
| 22 | "The guard ignores cancelled runs, so those commits…" | pre-release | flows |  |
| 23 | "**A `release:` commit is the designed escape.** A…" | pre-release | flows |  |
| 24 | "The comment at the top of `build.yml` says…" | pre-release | flows |  |
| 25 | "Two such commits were landed today, independently, within…" | pre-release | flows |  |
| 26 | "Both builds ran the full matrix." | pre-release | flows |  |
| 27 | "Cutting from either is safe against the other:…" | pre-release | flows |  |
| 28 | "**Dispatch is REST, not `gh workflow run`.** `gh…" | pre-release | flows |  |
| 29 | "The first watcher of the day found a…" | pre-release | flows |  |
| 30 | "All times UTC from the Actions API; the…" | pre-release | flows |  |
| 31 | "When (UTC) ; Commit ; Run ; What…" | pre-release | flagged | Table header row; structure, not a sentence; the rows under it follow |
| 32 | "19:29:47 ; `74cfa3f4` ; cut-release 41115704235 ; `v3.14.42`…" | pre-release | flows |  |
| 33 | "The last green Windows leg on record." | pre-release | flows |  |
| 34 | "23:42:49 ; `26a5f7d8` ; build 41146079630 ; Version…" | pre-release | flows |  |
| 35 | "Cancelled while pending (rolling group)." | pre-release | flows |  |
| 36 | "23:45:31 ; `4f9fa165` ; build 41146342715 ; Cancelled…" | pre-release | flows |  |
| 37 | "~23:48 ; `48099cd4` ; build 41146721846 ; Cancelled…" | pre-release | flows |  |
| 38 | "23:51:27 ; `3ca0f890` ; build 41146912852 ; The…" | pre-release | flows |  |
| 39 | "The failing step was `python runner/tools/run_tests_parallel.py --jobs 4…" | pre-release | flows |  |
| 40 | "00:31:01 ; `bf934f87` (Grok) ; build 41150588777 ;…" | pre-release | flows |  |
| 41 | "This commit predates `e37fd18e`." | pre-release | flows |  |
| 42 | "00:36:38 ; `e37fd18e` ; build 41151100737 ; The…" | pre-release | flows |  |
| 43 | "Cancelled while pending." | pre-release | flows |  |
| 44 | "00:41:33 ; `1aeaec19` ; build 41151531778 ; A…" | pre-release | flows |  |
| 45 | "00:55:07, 00:55:36 ; `11a3038e` ; cut-release 41152726596, 41152766156…" | pre-release | flows |  |
| 46 | "Guard: `no check run on this commit for:…" | pre-release | flows |  |
| 47 | "~00:57 ; `1aeaec19` ; (watcher) ; The audit…" | pre-release | flows |  |
| 48 | "00:58:28 ; `b3800a18` ; build 41152999571 ; `release:…" | pre-release | flows |  |
| 49 | "Dedicated group. `build-windows` job 124393603434 **failure** in 2m24s…" | pre-release | flows |  |
| 50 | "00:59:00 ; `36908087` (Muse) ; build 41153044427 ;…" | pre-release | flows |  |
| 51 | "01:10:13 ; `b3800a18` ; cut-release 41154000111 ; The…" | pre-release | flows |  |
| 52 | "Guard steps "the version, and that every carrier…" | pre-release | flows |  |
| 53 | "No tag was pushed; `git ls-remote --tags origin…" | pre-release | flows |  |
| 54 | "Three consecutive full-matrix runs on three different 3.14.43…" | pre-release | flows |  |
| 55 | "Between them, every other job in the matrix…" | pre-release | flows |  |
| 56 | "The job's step list (from `gh run view…" | pre-release | flows |  |
| 57 | "The job ran 2m24s." | pre-release | flows |  |
| 58 | "On the Linux leg the same command takes…" | pre-release | flows |  |
| 59 | "The check-run annotations on the job (`check-runs/124393603434/annotations`, reachable)…" | pre-release | flows |  |
| 60 | "The second kind was added to `run_tests_parallel.py` in…" | pre-release | flows |  |
| 61 | "That annotation code is present on `b3800a18` and…" | pre-release | flows |  |
| 62 | "The log itself is not reachable from this…" | pre-release | flows |  |
| 63 | "The repository's Actions settings endpoint (`actions/permissions`) is also…" | pre-release | flows |  |
| 64 | "So the text that would say which test,…" | pre-release | flows |  |
| 65 | "`runner/tools/run_tests_parallel.py` carries, in its own docstring, the record…" | pre-release | flows |  |
| 66 | "That history is noted here as history; whether…" | pre-release | flows |  |
| 67 | "**A thread-raced test.** The first guess was `test_a_stash_logged_after_its_delivery_is_not_a_fault`,…" | pre-release | flows |  |
| 68 | "It was replaced in `e37fd18e` by a deterministic…" | pre-release | flows |  |
| 69 | "The full suite on this seat's Linux box,…" | pre-release | flows |  |
| 70 | "`runner/tools/stamp_audit.py` exits 0 on the tree." | pre-release | flows |  |
| 71 | "Every non-Windows job in the matrix on `b3800a18`…" | pre-release | flows |  |
| 72 | "Non-bank commits from `74cfa3f4` to `d0b517a7`, newest first,…" | pre-release | flows |  |
| 73 | "The code-bearing ones among them, as opposed to…" | pre-release | flows |  |
| 74 | "Which of these, if any, the Windows leg…" | pre-release | flows |  |
| 75 | "Which test, shard, or exception ends the Windows…" | pre-release | flows |  |
| 76 | "Whether the shards die before any test runs,…" | pre-release | flows |  |
| 77 | "Why the dead-shard annotation from `0bb97efe` did not…" | pre-release | flows |  |
| 78 | "The annotations endpoint shows none of its output." | pre-release | flows |  |
| 79 | "Whether the Linux `test` job on `36908087` passes;…" | pre-release | flows |  |
| 80 | "On `b3800a18` it passed." | pre-release | flows |  |
| 81 | "`v3.14.43` is not tagged." | pre-release | flows |  |
| 82 | "No GitHub Release, no PyPI (`pigeon-home-runner`), SourceForge or…" | pre-release | flows |  |
| 83 | "`v3.14.42` remains the latest release on every mirror." | pre-release | flows |  |
| 84 | "Two cut-release attempts on `11a3038e` failed on the…" | pre-release | flows |  |
| 85 | "A third, on `b3800a18` at 30-OCT 6:10PM PST,…" | pre-release | flows |  |
| 86 | "That is the whole of what stands between…" | pre-release | flows |  |
| 87 | "The Linux `test` and `typecheck` jobs on `b3800a18`…" | pre-release | flows |  |
