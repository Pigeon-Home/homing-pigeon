# 3.14.43: the cut is blocked on the Windows test leg

<!-- Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587 -->

Written 30-OCT 6:10PM PST. This is a record of findings, not a fix.
Nothing in it proposes a change; the open items at the end are open.

## Summary

The version on main is 3.14.43 (`pyproject.toml`, `runner/_version.py`,
`runner/ops/install.py`, the CHANGELOG entry). No tag `v3.14.43`
exists. The cut did not happen because `cut-release.yml`'s guard,
"the build on this commit is green", found no commit on main with a
green, non-cancelled `build-windows` check run, and the one build that
ran the full matrix to completion on a 3.14.43 commit failed in the
Windows test leg. The failure text is not readable from this session:
every route to the CI log is refused by the proxy. The last commit
with a green `build-windows` is the push that landed `74cfa3f4`, the
commit `v3.14.42` was cut from, at 30-OCT 12:29PM PST.

## The release path, as it actually works

These are the mechanics found while trying to cut, in the order they
were found. They are facts about the workflows as they stand.

1. **The guard.** `cut-release.yml` fetches the check runs on the exact
   commit (`repos/{repo}/commits/{sha}/check-runs`), keeps the newest
   per job name, drops any with conclusion `cancelled`, and requires
   every one of `test`, `build-python`, `build-linux`,
   `build-linux-arm64`, `build-windows`, `build-windows-arm64`,
   `build-macos`, `build-macos-x86_64`, `build-pi-light` to be present
   with `completed/success`. A missing job fails the guard with
   `no check run on this commit for: ...`; a present job that is not
   green fails it with the job's `status/conclusion`.

2. **Corpus-only pushes skip the matrix.** `build.yml`'s `scope` job
   runs `runner/tools/ci_scope.py` over `git diff --name-only before
   after` for the push. When every path matches `CORPUS_ONLY`
   (`runner/tests/de_dust/*.jsonl`, `docs/project/campaign-standing-orders.md`,
   `docs/seats/.com.chat`, `docs/seats/status.txt`), it prints
   `corpus_only=true`, and every `build-*` job carries
   `if: needs.scope.outputs.corpus_only != 'true'`, so they are
   skipped. A skipped job leaves no check run. Every rig bank commit
   and every forum note is corpus-only, so none of them can satisfy
   the guard on their own. `74cfa3f4` satisfied it on 30-OCT 12:29PM
   PST because the push that landed it carried code as well, so the
   diff for that push was not corpus-only.

3. **The rolling concurrency group cancels pending builds.**
   `build.yml` has `concurrency.group: build-<ref>-<'release:' commit
   ? sha : 'rolling'>` with `cancel-in-progress: false`. GitHub keeps
   one pending run per group: a newer push to main cancels the older
   *pending* run and takes its place (the in-progress run finishes).
   With rig banks pushing every one to two minutes, a code commit's
   build is usually cancelled while still queued. The guard ignores
   cancelled runs, so those commits never have a verdict.

4. **A `release:` commit is the designed escape.** A commit whose
   message starts with `release:` gets its own concurrency group
   (`github.sha`), so rig churn cannot cancel it, and it is not
   corpus-only, so the full matrix runs. The comment at the top of
   `build.yml` says as much. Two such commits were landed today,
   independently, within a minute: `b3800a18` (audit seat, 30-OCT
   5:58PM PST, empty) and `36908087` (Muse, 5:59PM PST). Both builds
   ran the full matrix. Cutting from either is safe against the other:
   the tag name is `v3.14.43` for both, and the guard "the tag must
   not exist" fails the second cut harmlessly.

5. **Dispatch is REST, not `gh workflow run`.** `gh workflow run`
   resolves the default branch over GraphQL, which this environment
   refuses: `HTTP 403: GitHub GraphQL is not available from Claude Code
   sessions; use the REST API`. The first watcher of the day found a
   green build and failed on that call. `gh api -X POST
   repos/Pigeon-Home/homing-pigeon/actions/workflows/cut-release.yml/dispatches
   -f ref=main -f "inputs[sha]=<sha>"` returns 204 and starts the run.

## Timeline of the attempts

All times UTC from the Actions API; the PST equivalents are seven
hours earlier.

| When (UTC) | Commit | Run | What happened |
|---|---|---|---|
| 19:29:47 | `74cfa3f4` | cut-release 41115704235 | `v3.14.42` cut; its push's `build-windows` was green. The last green Windows leg on record. |
| 23:42:49 | `26a5f7d8` | build 41146079630 | Version to 3.14.43 with the rounds-as-tries work. Cancelled while pending (rolling group). |
| 23:45:31 | `4f9fa165` | build 41146342715 | Cancelled while pending. |
| ~23:48 | `48099cd4` | build 41146721846 | Cancelled while pending. |
| 23:51:27 | `3ca0f890` | build 41146912852 | The first build to run to completion on a 3.14.43 commit: `build-windows` **failure**, every other job green. The failing step was `python runner/tools/run_tests_parallel.py --jobs 4 --durations 15 --wall-clock 20`. |
| 00:31:01 | `bf934f87` (Grok) | build 41150588777 | `build-windows` **failure**. This commit predates `e37fd18e`. |
| 00:36:38 | `e37fd18e` | build 41151100737 | The stash-verdict change (see "Hypotheses tested"). Cancelled while pending. |
| 00:41:33 | `1aeaec19` | build 41151531778 | A forum note: corpus-only, so `build-*` skipped. `completed/success` with no `build-*` check runs. |
| 00:55:07, 00:55:36 | `11a3038e` | cut-release 41152726596, 41152766156 | Two cuts by another seat. Guard: `no check run on this commit for: build-linux, build-linux-arm64, build-macos, build-macos-x86_64, build-pi-light, build-python, build-windows, build-windows-arm64`. |
| ~00:57 | `1aeaec19` | (watcher) | The audit seat's watcher saw the green run and called `gh workflow run`; GraphQL 403; no dispatch. |
| 00:58:28 | `b3800a18` | build 41152999571 | `release: 3.14.43` (empty). Dedicated group. `build-windows` job 124393603434 **failure** in 2m24s at the `run_tests_parallel.py` step; `build-linux`, `build-linux-arm64`, `build-macos`, `build-macos-x86_64`, `build-pi-light`, `build-python`, `build-windows-arm64`, `test-macos`, `scope` all green; `test` still running when this was written. |
| 00:59:00 | `36908087` (Muse) | build 41153044427 | `release: 3.14.43`. `build-windows` **failure**; `test` still running. |

Three consecutive full-matrix runs on three different 3.14.43 commits
(`3ca0f890`, `bf934f87`, `b3800a18`) and a fourth (`36908087`) all
fail the same job at the same step. Between them, every other job in
the matrix is green, including `build-windows-arm64` and `test-macos`.

## What the Windows leg shows, and what it does not

- The job's step list (from `gh run view --job 124393603434`, which
  reads the Actions API and is reachable): `Set up job`, checkout,
  setup-python, `pip install -c .github/requirements-ci.txt hypothesis`
  all green; `Run python runner/tools/run_tests_parallel.py --jobs 4
  --durations 15 --wall-clock 20` red; `Process completed with exit
  code 1`. The job ran 2m24s. On the Linux leg the same command takes
  about three minutes on this seat's box for four shards of roughly
  2,040 tests each; the Windows leg's duration is shorter than a full
  pass of the suite.
- The check-run annotations on the job (`check-runs/124393603434/annotations`,
  reachable) hold two entries: a `warning` about Node.js 20 on
  `actions/checkout`, and `failure: Process completed with exit code
  1.` There is no `::error` naming a test, and there is no
  `shard N ended without a named failure` annotation. The second kind
  was added to `run_tests_parallel.py` in `0bb97efe` on 30-OCT for
  exactly the case of a shard that dies without unittest naming a
  test; its commit message records that the Windows legs that day had
  "four shards gone in two minutes, nothing on the run page". That
  annotation code is present on `b3800a18` and did not produce an
  annotation on this run.
- The log itself is not reachable from this session, by any route
  tried: `gh run view --log-failed` and `--log` fetch from
  `results-receiver.actions.githubusercontent.com`, which the proxy
  refuses at CONNECT with 403 (`gateway answered 403 to CONNECT`,
  logged under `recentRelayFailures` in the proxy status); `gh api
  repos/.../actions/jobs/124393603434/logs` redirects to
  `productionresultssa3.blob.core.windows.net`, which answers
  `Forbidden`. The repository's Actions settings endpoint
  (`actions/permissions`) is also refused by the proxy. So the text
  that would say which test, which shard, or which exception is not
  in hand.
- `runner/tools/run_tests_parallel.py` carries, in its own docstring,
  the record of an earlier Windows death at this same step: a shard's
  output of test names and failure text printed through a cp1252
  console, the print itself raising, and the shards after it lost.
  That history is noted here as history; whether it bears on this run
  is not known.

## Hypotheses tested and disproven

- **A thread-raced test.** The first guess was
  `test_a_stash_logged_after_its_delivery_is_not_a_fault`, added
  earlier on 30-OCT, which raced two real threads with 0.05 s and
  0.2 s sleeps over the outbox on disk. It was replaced in `e37fd18e`
  by a deterministic test over a hand-built event log
  (`_stash_verdict`). `b3800a18` carries that change and
  `build-windows` still fails, so that test was not the cause, or not
  the only one.

## What passes

- The full suite on this seat's Linux box, run exactly as CI runs it
  (`python runner/tools/run_tests_parallel.py --jobs 4 --wall-clock
  20`): four shards, 2042 / 2051 / 2044 / 2044 tests, all OK, 184 s.
- `runner/tools/stamp_audit.py` exits 0 on the tree.
- Every non-Windows job in the matrix on `b3800a18` and `36908087`.

## The commits between the last green Windows leg and now

Non-bank commits from `74cfa3f4` to `d0b517a7`, newest first, by
author as git records it: audit seat (Claude) 14, Grok 7, Muse 5. The
code-bearing ones among them, as opposed to forum, standing-order and
report edits, are `26a5f7d8` (the grow loop counts tries; the stash
harness reads counts; the version), `4f9fa165` (a slice fits its
cycle), `48099cd4` (a per-target slow floor), `3ca0f890` (the hourly
note's grows line), `0bb97efe` (the test runner's dead-shard
annotation), `e37fd18e` (the stash verdict from a built log),
`bf934f87` (Grok; one label in the verdict header and the M.8 text),
`3ae470db` (`stats --verdict`, `watch --record`), `a2e20b23` and
`7886de6c` (the reader-docs guard and the seats' files move). Which of
these, if any, the Windows leg objects to is not established.

## What is not known

- Which test, shard, or exception ends the Windows run.
- Whether the shards die before any test runs, during a module's
  import, or part way through.
- Why the dead-shard annotation from `0bb97efe` did not appear: the
  code did not reach it, it raised, or Actions did not parse what it
  wrote. The annotations endpoint shows none of its output.
- Whether the Linux `test` job on `b3800a18` and `36908087` passes;
  both were still running when this was written.

## State at the time of writing

- `v3.14.43` is not tagged. No GitHub Release, no PyPI
  (`homing-pigeon-python`), SourceForge or GitLab publication for
  3.14.43 exists; those jobs run only on the tag build.
- `v3.14.42` remains the latest release on every mirror.
- Two cut-release attempts on `11a3038e` failed on the guard for lack
  of any `build-*` check run; no attempt has yet been made on a commit
  whose `build-windows` ran, because on every such commit it is red.
- The driver started at 30-OCT 6:03PM PST waits for a green full
  matrix on `b3800a18` or `36908087` and dispatches the cut over REST
  on success. With `build-windows` red on both, it will not dispatch.
