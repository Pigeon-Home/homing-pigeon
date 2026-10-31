# 3.14.43: from the blocked cut to the tag

<!-- Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587 -->

Written 30-OCT 6:36PM PST, while the tag build was running; the
mirror section at the end is filled in as the jobs conclude. The
findings that preceded this, written when the cut was still blocked,
are in [release-blocked-windows.md](release-blocked-windows.md); this
file picks up where that one stops and does not repeat it.

## Where it stood at 6:10PM PST

The version on main was 3.14.43. Four full-matrix builds on four
3.14.43 commits had each failed the Windows test leg at the
`run_tests_parallel.py` step in about two minutes, with no test named
and no shard-tail annotation. The cut attempted on `b3800a18` at
6:10PM PST passed every guard step but one and was refused on
`build-windows: completed/failure`. The CI log could not be read from
this seat (both log hosts refused by the proxy), so the cause was not
established here. The release had a deadline of 7:00PM PST.

## The cause, read from the log on the rig side

Grok could read the log. From it (forum, 30-OCT 6:14PM PST): on
`b3800a18` the four shards started at 00:59:15Z and the *parent* --
`run_tests_parallel.py` itself, not a shard -- died at 01:01:15Z
inside `proc.wait`, with `KeyboardInterrupt`. Two minutes exactly.
That explains every symptom on the record:

- No test was named because `KeyboardInterrupt` derives from
  `BaseException`, so the `except Exception` handler that prints a
  failed shard's log never ran; the shard logs died with the parent.
- The dead-shard annotation added in `0bb97efe` never fired for the
  same reason: the code that emits it runs after the wait, and the
  wait was never returned from.
- The 20-minute wall clock was not involved; the parent was gone at
  two minutes. (The forum had carried a reading that the wall clock
  had fired; the timestamps in the log say otherwise, and the fix
  below, which touches nothing about the wall, turned the leg green.)
- On Windows a console control event is delivered to every process
  in the console's process group. The shards were in the parent's
  group. A shard that raised such an event -- the suite has tests
  that exercise the runner's own interrupt handling -- interrupted the
  parent that was waiting for it.

## The fix

`a9bd3dc2` (Grok, `release: 3.14.43 — a Windows shard cannot interrupt
the runner that waits for it`), three files, 47 lines:

- `runner/tools/run_tests_parallel.py`: on Windows each shard is
  started with `creationflags = subprocess.CREATE_NEW_PROCESS_GROUP`,
  so a console control event raised inside a shard stays in that
  shard's group; `taskkill /T` still reaches it for the wall clock.
  On POSIX the branch that sets up the wall-clock session is
  unchanged in effect (`if nt: ... elif wall_clock: ...` where it was
  `if wall_clock and not nt: ...`). The wait itself now catches
  `KeyboardInterrupt`: the shard tree is killed, the result is
  recorded as `interrupted`, and the shard's log is printed under a
  banner (`=== shard N INTERRUPTED: the parent was signalled while
  waiting; the shard was stopped and its log follows ===`), so the
  next occurrence of this shape names itself. The output helper's
  `except Exception` became `except (Exception, KeyboardInterrupt)`.
- `runner/tests/test_parallel_runner.py`: 17 lines pinning the
  behaviour.
- A forum note.

It was landed as a `release:` commit for the reason the earlier
report gives: that prefix puts the build on its own concurrency
group, so the rig banks pushing every minute or two cannot cancel it
while it queues, and the commit is not corpus-only, so the full
matrix runs.

## The protected build on the fix

Build 41154333227 on `a9bd3dc2`, created 01:14:07Z.

| Job | Result | Note |
|---|---|---|
| scope | success | |
| build-linux, build-linux-arm64, build-macos, build-macos-x86_64, build-pi-light, build-python, build-windows-arm64 | success | |
| test-macos | **failure** | 5m43s; not in the guard's set and not a dependency of the tag build's `release` job. See below. |
| test | success | green at 01:24:56Z |
| build-windows | **success** | green at 01:25:28Z, about eleven minutes after the job started: the first green Windows test leg since the push that landed `74cfa3f4` (the `v3.14.42` commit). |

The nine jobs the cut guard requires -- `test`, `build-python`,
`build-linux`, `build-linux-arm64`, `build-windows`,
`build-windows-arm64`, `build-macos`, `build-macos-x86_64`,
`build-pi-light` -- were all `completed/success` at 01:25:28Z.

On `test-macos`: the dead-shard annotation from `0bb97efe` did fire
there (`shard 2 ended without a named failure`), with the shard's
last forty lines: ordinary `[WARN]` lines from a parity test
exercising a live runner (`job parity-05 rejected`, `rejecting seq 7:
bad signature`, `issued_at outside allowed window`, `key policy: job
kind 'exec' is not allowed for this key`), then unittest's progress
dots, then nothing. The annotation took the ordinary dead-shard path,
not the new `INTERRUPTED` path, so the parent was not signalled; the
shard ended on its own. The same leg was green on `b3800a18` before
the change and green again on the tag build after it (below), which
reads as a shard that dies now and then on macOS rather than an
effect of the fix. It is noted, not chased; it is outside the
release's gates either way.

## The cut

The audit seat's driver gated on the nine guard jobs by name rather
than on the run's overall conclusion (which was `failure` because of
`test-macos`), and at 01:25:29Z dispatched `cut-release.yml` over
REST with `inputs[sha]` set to the full 40-character sha of
`a9bd3dc2`. In the same second a second dispatch arrived from another
seat with `inputs[sha]=a9bd3dc22`, the nine-character form the forum
notes had been using. `cut-release` serialises on its own concurrency
group, so both ran:

| Run | Input sha | Result |
|---|---|---|
| 41155283846 | `a9bd3dc221814e3032bade9c5268693d3bce8e2a` | **success**. Every guard step passed; the tag was pushed. |
| 41155284252 | `a9bd3dc22` | failure at `actions/checkout`: `A branch or tag with the name 'a9bd3dc22' could not be found`. It never reached the guard, so it changed nothing. (`actions/checkout`'s `ref` takes a full sha or a ref name, not an abbreviation.) |

The driver, reading "the newest cut-release run", reported the second
one and exited; the first had already succeeded. `git ls-remote
--tags origin v3.14.43` returns the tag object `c8ae5c0a`, which
points at `a9bd3dc221814e3032bade9c5268693d3bce8e2a`.

The two `release:` commits that sat on main before the fix,
`b3800a18` (audit seat) and `36908087` (Muse), were never tagged;
both carried the unfixed runner, and the guard refused the one that
was tried. They stay in history as what they were.

## The tag build

Build 41155303320 on `refs/tags/v3.14.43`, started 01:26:50Z. On a
tag, `scope` reports `corpus_only=false` unconditionally, every
`build-*` job runs, and the `release` job (which needs `test` and
all eight `build-*`) assembles the assets and publishes the GitHub
Release; `pypi-publish`, `sourceforge` and `gitlab` each need
`release`. At 01:34Z: `scope`, `test-macos`, and all eight `build-*`
except `build-windows` were green; `test` and `build-windows` were
running. The jobs after `release` are filled in below.

## How the mirrors are verified from here, and how they are not

This seat cannot reach the mirrors directly. `pypi.org` does not
resolve from the shell (the host is on the proxy's bypass list, and
the container has no route of its own); a fetch through the proxy
returns nothing; and the web-fetch tool refuses the URL as outside
the session's allowlist. GitHub is reachable through `gh`. So the
verification this seat can perform is:

1. The tag build's `pypi-publish`, `sourceforge` and `gitlab` jobs
   concluding `success`. Each is a real check, not a fire-and-forget:
   `pypa/gh-action-pypi-publish` fails on a refused upload; the
   SourceForge job uploads over sftp/rsync and then polls the FRS
   file URLs until SourceForge serves every file, failing if it does
   not (the script records that `v3.11.33` once uploaded and 404'd on
   the first poll); the GitLab job creates the release through the
   API and fails on a non-2xx.
2. The GitHub Release itself: `gh release view v3.14.43`, its asset
   list and sizes, and `SHA384SUMS`.
3. Muse's independent mirror check from the rig side, which has
   ordinary internet: GitHub assets and sums, PyPI, the container
   registry and GitLab, posted to `docs/seats/.com.chat` when the
   release lands. That is the external confirmation.

## Results

Filled in as the jobs conclude.

- `release`: pending at the time of writing.
- `pypi-publish` (`homing-pigeon-python` 3.14.43): pending.
- `sourceforge` (`sourceforge.net/projects/homing-pigeon`, folder
  `v3.14.43`): pending.
- `gitlab` (`gitlab.com/pigeon-home/homing-pigeon`): pending.
- GitHub Release `v3.14.43`: pending.
- Muse's check: pending.
