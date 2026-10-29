# Testing

**Watch before you trust.** The runner is fully inspectable — these flags
exist so you can audit everything it would do before it does it:

```bash
python3 runner/runner.py --config config.json --once --dry-run --verbose
# verifies signatures, prints what each job WOULD do, executes nothing,
# sends nothing, changes nothing (mail stays unseen)
```

| Flag | What it does |
|------|--------------|
| `--dry-run` | Verify and describe; execute nothing, send nothing |
| `--workers COUNT` | Concurrent job executions (default 1) |
| `-v`, `--verbose` | Decision lines: every poll, ingest, wake-gate, judge and board call, with reasons. `-vv` adds more; `--quiet` turns them off. Also a config key: `"verbose": true` |
| `--pdb` | Drop into pdb on unhandled exceptions |
| `--no-send` | Execute, but log results instead of emailing them |
| `--once` | Single poll cycle, then exit |
| `--inspect {board,budget,job,outbox,redact,review,sources}` | Read local Oracle state and exit; no mailbox |
| `--audit-report [--since 14d|48h] [--feature NAME] [--key KEY_ID]` | Summarize the security audit log and exit; no mailbox, read-only. `--feature` narrows it to one control's entries, `--key` to one key's |
| `--posture` | Report the runner's security posture (exit 0/1/2) and exit; no mailbox |
| `--run-variant FILE` | Run one locally supplied fuzz variant job from FILE through validation and confined execution, print its outcome as JSON, and exit; no mailbox. The job-fuzz sense's execution door: variants are unsigned local artifacts, admitted only here, never through the job path |
| `--oracle` | Open a loopback chat with the Oracle in your browser. Does not poll mail. Turns are appended to `oracle-chat.jsonl` in the base dir (1 MiB, then one backup). See `docs/CONTRIBUTING.md` (maintainer notes: the `--oracle` flag). |
| `--poll-interval SECONDS`, `--timeout SECONDS`, `--judge MODE`, `--dag-mode MODE`, `--oracle-mode MODE`, … | One-process config overrides: one flag per key, `config.json` untouched, and a flag beats a later config edit. The full map is in `--help` and `docs/oracle/configuring-oracle.md` |

`install.py` accepts the common run flags — `--poll-interval`,
`--timeout`, `--workers`, `--max-output-bytes`, `--dry-run`,
`--verbose` — and bakes them into the installed
service, so the agent on boot runs exactly what you tested:
`python3 runner/ops/install.py --verbose --poll-interval 30`.

```bash
python3 -m unittest discover -s runner/tests -t .
```

The suite drives the real runner code against fake IMAP/SMTP servers:
ping roundtrip, script execution, timeout kill, poison-job rejection,
signature/tamper rejection, any-sender acceptance.

End-to-end without your SI:

1. `python3 runner/cloud/send_job.py new --kind ping --secret <the-string>` → copy the
   subject + body.
2. From any email account, send it to the
   runner mailbox.
3. On the target machine: `python3 runner/runner.py --config config.json --once`.
4. A result message should arrive in the mailbox (or at the job's
   `reply_to` address, if you set one). It arrives as an encrypted
   envelope; decrypt it with `send_job.py verify --job-id`
   (`docs/use/sending.md`) and the result inside says
   `stdout: "pong"`.

## Where the suite runs, and what each platform proves

The runner ships for Linux (x86_64, ARM64, the Pi light build),
macOS (Apple Silicon and Intel) and Windows, and installs on
FreeBSD from the sdist. Every platform that ships is tested on a
real kernel of that platform; the table is what each one proves
and how often. The FreeBSD leg is the one without a green run
yet: its VM step has failed on every run so far, so its row is
the proof it is built to give, not one given.

| Platform | Suite | Switch proofs (the roster) | Built binaries | When |
|---|---|---|---|---|
| Linux (ubuntu-latest) | `test` job, in-process under the wall clock | `linux` leg (bwrap) and `root` leg (a second user): every control | smoked | suite and binaries on every push to main and every tag; the switch proofs on a push that touches `runner/**`, SECURITY.md, the hardening templates or `switch-proofs.yml`, and nightly, never on a tag |
| Windows (windows-latest) | `build-windows` job, sharded over 4 cores | `windows` leg: the platform-neutral controls | smoked | as Linux |
| macOS (macos-14) | `test-macos` job, sharded over 3 cores | `macos` leg and `macos-root` leg (a second user): the POSIX controls, the drop included | smoked (both macOS builds) | as Linux |
| FreeBSD 15 (a VM inside a Linux runner) | as an ordinary user, under the wall clock | as root with a second user: the POSIX controls | not built (sdist install) | weekly, on dispatch, and when `freebsd.yml` changes; no green run yet |

The roster (`runner/tests/switch_roster.py`) says, per control, what
a leg must provide: `posix` (any of the three kernels), `linux`,
`bwrap` (a working sandbox), `root` (a real second user to drop
to). A leg judges only the entries it can; `runner/tools/switch_proofs.py`
reports every control as proven, unproven, or failed, and the
workflow fails when a proof disappears.

What the platforms cannot prove is what the runner does not do
there, by the owner's 2026-10-15 decisions: confinement is bwrap,
Linux only, and on every other kernel a `confinement: enforce` job
runs unsandboxed with a WARN line and a `fallback` audit entry;
`job_user` is a uid change and works on the three POSIX kernels but
has no Windows form. The real cages elsewhere are named in
`docs/security/security-gaps.md` (`sandbox-exec` on macOS, a jail
on FreeBSD, a job object and a restricted token on Windows); none
is implemented, and adding one is a scope decision, not a test.

<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->

## Proofs that need time, history, or a real box

The suite proves a commit on one Python in minutes. These prove what
it cannot:

| Proof | What it proves | When |
|---|---|---|
| `python-range` | the whole suite on the 3.9 floor and on 3.14 | every push |
| `upgrade-proof` | the last release installs, the owner's edits and the state are seeded, this commit upgrades over them, and nothing is lost (`runner/tools/upgrade_proof.py`) | every push; tree-to-itself in the suite |
| `soak` | two hours of the real poll loop on the campaign rig's job mix; fails on growth in memory, the Python heap, file descriptors, threads, unreaped children, a missing result, or an oversized log (`runner/tools/soak.py`) | nightly, on dispatch |
| `hardware` | the suite, the platform proof, the upgrade proof and a soak on the owner's own board | on dispatch |
| `campaign-replay` | every recorded campaign cycle (13,321, in `runner/tests/archive/campaign-*/`) replayed through the executor against what the live cycle recorded; the core cut keeps them out of default discovery, not out of CI | every push |
| `coverage` | the map of code no test runs, on Linux and Windows, by function (`runner/tools/coverage_gaps.py`); a signal, never a gate | every quarter hour on the tip of main, and on dispatch |
| `stamp-audit` | every commit's agent stamp against `docs/archive/RESEARCHER_IDENT.md` over the full history: one stamp one session, one session one stamp, no recycled or unregistered stamp from 2026-10-27 on (`runner/tools/stamp_audit.py`) | every push |
| `test_parser_properties` | every parser that reads input the runner did not write (protocol v2, both verifiers, reply-to, the platform card, extension manifests, `sources.json`, archive extraction, the config readers, the text helpers) held to its contract on generated input; `PROPERTY_ROSTER` names each parser, its promise and its proof, and fails if one loses its test | every push |
| `test_live_capture` | the runner's readers take three days of a real box's files (`docs/reports/live-2026-10-25/`), the scrub holds, and `docs/use/live-examples.md` quotes them exactly | every push |

The live capture is the suite's one corpus from a real deployment:
19,227 jobs, the learning ledger, the security events and the log of
the campaign rig. A change that would not read those files fails
`test_live_capture`; `runner/tools/live_capture.py` prints what the
run came to.

A box with no package index can still measure lines. Two tools do it
with the standard library's `sys.monitoring` (Python 3.12 and later),
both writing coverage.py's JSON shape, which `coverage_gaps.py` reads
unchanged; neither counts branches.

| Tool | For | Child processes |
|---|---|---|
| `runner/tools/linecov.py --out cov.json --source <path> -- <test names>` | a few test modules against the sources they aim at: the loop of writing a test for a gap and seeing it close | not counted |
| `runner/tools/stdlib_coverage.py --subprocess --jobs N --out cov.json` | the whole suite, sharded, against all of `runner/`: the number for a box, comparable run to run | counted when they inherit the suite's environment |
| `runner/tools/coverage_one.py [--jobs N]` | both of the above, then one line: statements, never executed, branches, never taken, percent. The conductor should not have to know which tool | the number |

`docs/reports/coverage/` and `docs/reports/local-rig-2026-10-27/` keep
the reports they have made. On the same tree both read at or below the
coverage.py number in the release reports, never above it.

`linecov.py` leaves out of a count what no run could mark: a `global`
or `nonlocal` line (it compiles to no instruction), and a `.py` under
a measured folder that does not parse, which it names under
`meta.unparsed` instead of losing the report. Its keys use `/` on
every box.

A whole-suite pass takes about twelve minutes on two cores, and main
moves faster than that: run it in a worktree pinned to one commit
(`git worktree add --detach <dir> <sha>`, then the tool from inside
it), so no pull or bank changes a file under the run, and name that
commit in the report.

Running the same proofs locally:

```bash
# the suite, as CI runs it
python3 -m unittest discover -s runner/tests -t .
# sharded, as the Windows and macOS jobs run it
python3 runner/tools/run_tests_parallel.py --jobs 4 --wall-clock 20
# the roster on this box: name what the box provides
python3 runner/tools/switch_proofs.py --have posix,linux,bwrap --out proofs.md
sudo python3 runner/tools/switch_proofs.py --have posix,linux,bwrap --root --out proofs-root.md   # needs a user named pigeon-test
# the fixture shapes that pass here and fail on Windows
python3 -m unittest runner.tests.test_windows_portability
# one regression pass with its ledger line (the rig's hourly pass)
python3 runner/tools/regression_pass.py --jobs 4 --no-bisect
# line coverage with the standard library alone (Python 3.12+), child
# Pythons included, in coverage.py's JSON shape
python3 runner/tools/stdlib_coverage.py --subprocess --jobs 4 --out coverage.json
python3 runner/tools/coverage_gaps.py coverage.json --out gaps.md
```

A box with no PyPI runs all of it. hypothesis is a test-only
dependency: without it a property module loads through
`runner/tests/_hypothesis_shim.py`, its `@given` tests skip with the
reason `hypothesis not installed`, and its deterministic tests run.
A module that is nothing but property tests skips whole instead
(`require_hypothesis()` in `runner/tests/_compat.py`). Neither stands
in under CI (`GITHUB_ACTIONS` or `CI` set): there a missing hypothesis
fails the module at import and the leg goes red, and `build.yml` and
`python-range.yml` also forbid the shim's skip (`skip_guard.py
--forbid`).

Adding a platform leg: copy the nearest job in
`.github/workflows/switch-proofs.yml` (`macos` for a kernel with a
native runner, `freebsd.yml` for one that needs a VM), give
`--have` exactly what that box provides, create the second user
for a root leg, and add the workflow's name to `WORKFLOWS` in
`runner/tests/test_build_config.py` so the pin and permission
guards cover it. A test that only works on one kernel skips the
others with a registered reason (`runner/tests/test_skip_registry.py`);
a control that only exists on one kernel says so in its roster
`needs`.
