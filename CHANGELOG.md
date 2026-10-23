# Changelog

One section per release, newest first. Entries are compact by
design: the headline changes, the fixes that mattered, and the
facts a reader may need to cite. Git history carries the rest.

## 3.12.52 - 2026-10-22

- **OAuth consent waits for its own callback.** The redirect
  listener ignores a favicon, a stale tab, and any callback
  whose state is not this consent's. A matching code or error
  is what ends the sign-in. The previous tests still expected
  a bare path to finish it as "unknown", which is what turned
  the last main run red on the suite and on Windows.

- **Feed senses carry the format they parse.** Each of the eight
  feed senses (Suricata, Zeek, osquery, Falco, Wazuh, AIDE, Sysmon,
  softflowd) now names an `upstream` in its manifest -- repository,
  ref, pinned commit, and the few files that define the log or
  record it reads -- and `tools/fetch_upstream.py` carries those
  files into `<extension>/upstream/` beside the adapter, licenses
  included. The fetch is a blobless sparse git checkout; the whole
  set is budgeted at 5 MiB (1.2 MiB used) and the build fails past
  it or when a file is stale or hand-edited. New drift tests assert
  the fields each adapter reads are still defined in the source it
  carries. A nightly `upstream-pins` workflow moves the pins, reruns
  those tests, and commits only when they pass. `docs/extensions.md`,
  "Upstream: carrying the format you parse". No change to what the
  runner does; the manifest field is validated and never fetched by
  the agent.

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

- **Every extension brings its own code for the Oracle.** The first
  time the agent loads a sense or starts a transport, it gives the
  Oracle the extension's installed code and fetches, in the
  background, what its optional `sources.json` declares: its
  published source, the upstream project it wraps, the specs it
  speaks. On every box by default, a Pi Light with no model
  included (`extension_sources`). The release job pins every
  declared upstream (`project/EXTENSION-SOURCES.lock.json`) and a
  box refuses bytes that differ. A written disclosure rule decides
  what the Oracle sees: provide by default, withhold when the owner
  (or the author) says so. `--inspect sources`, `--fetch-sources`.
  `docs/extensions.md`, "Sources".
- **pip installs get their transports.** The wheel now carries each
  shipped transport's `extension.json`; the 3.12.50 wheel had none,
  so a pip install discovered no transport at all.
- **Provenance bundles.** Each feed's `upstream.json` keeps its
  upstream's license and pinned commit under
  `<extension>/provenance/<name>/`, verified offline in the build
  (`tools/vendor_upstreams.py`). The folder is `provenance/`, not
  `upstream/`, so the format files' nightly fetch cannot delete it.

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

## 3.12.51 - 2026-10-22

- **Windows Oracle asks no longer get dropped.** The chat
  server listened with a backlog of 5. Eight asks at once
  filled it, Windows aborted the rest (WinError 10053), and
  the send-button test saw 2 answers out of 8. That is the
  failure that turned the 3.12.25 Windows job red. The
  backlog is 32, and a refused localhost socket is retried.
- The other red runs in this stretch were already fixed:
  the unregistered "posix spawn arm" skip (3.12.25), the
  tar exec bit Windows never writes (3.12.27 and 3.12.28),
  and the `file://C:\...` clone URL (3.12.30). The twenty
  tags from 3.12.31 through 3.12.50 were the same code as
  3.12.30 and their tag runs passed.

## 3.12.50 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.49 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.48 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.47 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.46 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.45 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.44 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.43 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.42 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.41 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.40 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.39 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.38 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.37 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.36 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.35 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.34 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.33 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.32 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.31 - 2026-10-22

- Same code as 3.12.30. No change to what the runner does.

## 3.12.30 - 2026-10-22

- **Windows snapshot test.** The shallow-clone check built
  `file://C:\...`, which is not a file URL. It now uses
  `pathlib.Path.as_uri()`, so git gets `file:///C:/...`.
  The module also stays importable when the Windows
  simulator breaks `shutil.which`.
- No change to what the runner does. Mirrors are still on
  3.12.26 until a Windows job passes and the release job
  publishes.

## 3.12.29 - 2026-10-22

- **The Windows job can finish a release again.** The new
  snapshot test required a Unix exec bit. On Windows, `chmod`
  plus `tar.add` never writes that bit, so the suite failed,
  the release job was skipped, and 3.12.27 never reached
  GitLab or SourceForge. The test now writes the bit into the
  tar header, which is what inject is supposed to keep.
- Mirrors are otherwise current through 3.12.26: GitLab
  releases, SourceForge files (Linux, macOS, and Windows
  defaults), and both git mirrors at that tag.

## 3.12.28 - 2026-10-22

- Same code as 3.12.27. No change to what the runner does.

## 3.12.27 - 2026-10-22

- **Every release ships the whole project.** Each install
  archive now carries `project/`: every tracked file at the tag,
  the full git history as `project/.history/homing-pigeon.bundle`,
  and `CI-SNAPSHOT.json` — every workflow with its triggers and
  jobs, the platform each build ran on, and the test results of
  the run that built the release. `PROJECT-SNAPSHOT.md` indexes
  it with links pinned to the commit. The same snapshot ships
  alone as `homing-pigeon-project-<version>.tar.gz`. The release
  job builds it once, after the test job, and adds it to the
  finished archives before `SHA384SUMS`, so the sums and the
  attestation cover it (`tools/make_snapshot.py`).
- **The Oracle can read it.** The installer copies `project/`
  into the state dir (an upgrade replaces it whole), and the
  Oracle's context names it, so the local model can read the
  source, the tests, and the CI that built this release with no
  network. This is the groundwork for the Oracle recommending CI
  changes and unit tests from the environments it fails in.
- **Links.** PROTOCOL.md's Agent Guide, README, INSTALL, RUNBOOK
  and `docs/verification.md` point at the source, the tests, the
  CI workflows, and the snapshot. RUNBOOK no longer states a file
  count for the release.

## 3.12.26 - 2026-10-22

- **CI.** A push runs the plentiful proofs only. macOS,
  Windows, and ARM hosted runners, and the board legs, run
  nightly. Binary jobs start beside the suite. The release
  still waits for the suite and for every artifact. The
  reasoning is `docs/design/ci-runtime.md`. No change to
  what the runner does.

## 3.12.25 - 2026-10-22

- **More boards, same push.** The nightly platform proof now
  covers the userspace a Pi competitor ships: 64-bit Pi OS
  and Armbian, Ubuntu under a Jetson and on Odroid N2, the
  32-bit Ubuntu a PandaBoard and an Odroid XU4 shipped,
  Alpine on those 32-bit boards, and ROS 2 Humble and Jazzy.
  A push does not run them. 32-bit Pi OS, BeagleBone, CHIP,
  and the Tinker Board were already the Debian armv7 leg.
- **The suite is green again.** The relay spawn test skipped
  on Windows with a reason the skip registry had not been
  told about, so the Ubuntu job went red. The reason is
  registered. The Windows arm of that launch is its own test.
- No change to what the runner does.

## 3.12.24 - 2026-10-22

- **Docs reorganized to the common layout.** The root keeps
  README, INSTALL, CHANGELOG, CONTRIBUTING, SECURITY, AGENTS,
  PROTOCOL, and ENTERPRISE. TRANSPORTS, SAFEGUARDS, RUNBOOK,
  and FUTURE moved to `docs/`; design records to
  `docs/design/`; four retired notes and RESEARCHER_IDENT to
  `docs/archive/`. PROTOCOL.md and the IETF drafts did not
  move, so their published URLs still work. Links to the
  four moved root files now need the `docs/` prefix.
- **FAQ: "What can I actually use this for?"** Use cases from a barn Pi to camera traps,
  each tied to the feature and doc that makes it work.
- No change to what the runner does.

## 3.12.23 - 2026-10-22

- **CI.** A red suite is the suite's own exit code again:
  `tee` can no longer hide it. A failure is also a check
  annotation, so the test name and the exception are
  readable without the log. No change to what the runner
  does.

## 3.12.22 - 2026-10-22

- **The release can finish.** GitHub retired the `macos-13`
  runner in December 2025. The Intel macOS build was still
  asking for it, so the release job sat in that queue and
  never published. It now asks for `macos-15-intel`. No
  change to what the runner does.

## 3.12.21 - 2026-10-22

- **Windows build.** The job-claim tests called `os.kill(pid, 0)`
  to find a pid that is not running. On Windows that is
  WinError 87, not "no such process", and it failed
  `build-windows`. The tests ask the process table there, the
  same way the runner does.
- **No runner change.** Coverage on this tree is 96.8%
  statements. The doc tree was reorganized. What the runner
  does is the same as 3.12.20.

## 3.12.20 - 2026-10-21

- **A computer with no Python.** The common one is a Windows
  PC, which does not ship Python. Download the Windows zip
  and run `homing-pigeon.exe`. Do not install Python. The
  binary carries its own interpreter, and so do the Linux
  and macOS binaries. The release proves it: Windows starts
  the exe with Python off `PATH`, and the Linux binary
  starts in a Debian image that has no `python3`. A
  television OS still cannot run this. The board behind the
  screen, if you control it, is the Linux archive, and that
  board does not need Python either.

## 3.12.19 - 2026-10-21

- **Release.** Same code as 3.12.18.

## 3.12.18 - 2026-10-21

- **Release.** Same code as 3.12.17.

## 3.12.17 - 2026-10-21

- **FAQ: the duty of care sits with the SI.** A new entry in
  `docs/FAQs.md` says why the runner does not protect a beginner
  from installing on the wrong computer: the runner is the dumb
  end of the wire, the vendors claim their models act
  responsibly, and the project takes them at their word.

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

## 3.12.16 - 2026-10-21

- **Release.** Same code as 3.12.15.

## 3.12.15 - 2026-10-21

- **Release.** Same code as 3.12.14.

## 3.12.14 - 2026-10-21

- **Release.** Same code as 3.12.13.

## 3.12.13 - 2026-10-21

- **A skipped test has to say why.** Every skip reason in the
  suite is registered with the reason it is legitimate and
  where the test does run. An unused registration fails, and
  a skip hidden behind `if True` is refused. The workflows
  no longer hardcode a test count, and `continue-on-error`
  stays only on the release mutation job, where it is
  documented.

## 3.12.12 - 2026-10-21

- **A television is not a runner.** Tizen, webOS, Roku, and
  Apple TV are refused before any file is copied. So is any
  environment that cannot execute a shell, including an
  Android set whose app cannot exec. Android with a shell
  (a sideloaded terminal) is warned and then installed as
  `display-board`: no model, no service, jobs run as that
  app's user. A USB accelerator is not the computer.
  `--profile display-board` is the no-model install for a
  dedicated Linux board behind a screen.
- **Three more frozen binaries.** Linux ARM64 (no Pi Light
  marker), Windows ARM64, and Intel macOS. Each is built on
  the matching runner. The SourceForge defaults stay Windows
  x64, Linux x64, and Apple Silicon.
- **Enforce mode can see the interpreter.** The sandbox
  binds that interpreter's install prefix read-only, so a
  pyenv, a venv, or a toolcache Python is not missing inside
  the wall. The bind is written into the audit record.
- **Python 3.9 imports again.** Annotations in the installer,
  the mailbox, and setup are lazy, matching the declared
  floor.

## 3.12.11 - 2026-10-21

- **Bash-only scripts are not repaired onto `sh`.** An array,
  a here-string, `declare`, process substitution, or a
  substring expansion means the job stays as sent. A plain
  `#!/bin/bash` script with none of those is still repaired.
  `send_job.py verify` prints one line naming the digest of
  what was received and the first line of what ran.
- **Extension output is in the runner log.** Transport
  extensions relay each line into the same log `--logs`
  tails.
- **The release is proved before it is published.** Repair
  is run on Alpine with no bash, on x86_64 and arm64. A
  skipped proof fails the build. POSIX archives and the
  Docker image are smoked before publish.

## 3.12.10 - 2026-10-21

- **Release.** Same code as 3.12.9. The 3.13.0 tag was
  removed and is not part of this line.

## 3.12.9 - 2026-10-21

- **Code scanning is clear.** Three queries still fired after
  3.12.8, all false positives: clear-text logging of a line
  that does not contain a secret, the fixed Oracle
  classifier pattern, and the DTLS listen address. The
  default suite does not honor a comment on the line, so
  those three are excluded in the CodeQL config. The other
  queries stay on.

## 3.12.8 - 2026-10-21

- **Code scanning.** The open CodeQL alerts were false
  positives: test fixtures, sample sensors that name an empty
  env var and do not print the secret, the result SHA-384
  digest, the job script written so it can run, and operator
  reports that show key ids rather than secret values. Ignore
  rules cover those. The checks stay on for the runner.

## 3.12.7 - 2026-10-21

- **3.12.6 did not publish.** The Windows test job failed the
  live-claim check. That test wrote pid 1 into the claim file.
  Pid 1 is alive on Linux and usually nobody on Windows, so
  Windows treated the claim as dead and took it. The test now
  holds a real second process. The claim rule is unchanged.

## 3.12.6 - 2026-10-21

- **Skip the personal-documents check.**
  `--ignore-personal-documents` on the runner skips the scan
  for that process. The same flag on the installer skips the
  warning and writes it into the service command. The banner
  does not mention the flag. `--help` does.

## 3.12.5 - 2026-10-21

- **Personal-documents warning.** On startup, and before an
  install copies files, the program looks at file and folder
  names in the home Documents, Desktop, and Downloads. A legal,
  tax, or medical name prints a fixed banner: do not install
  here unless you are a proficient system administrator. No
  file is opened, and the name that matched is not recorded.
  Decisions: docs/personal-documents-warning.md.

## 3.12.4 - 2026-10-21

- **3.12.3 did not publish.** Its test job failed: the seen-file
  temp name did not match the Linux pin, and the Windows lock
  import ran on Linux when a test pretended to be Windows.
  Binaries for that tag were not built. This tag is the same
  race fixes, with those two corrected.

## 3.12.3 - 2026-10-21

- **Two runners, one state directory.** A job is claimed on
  disk as well as in memory. `seen.json` is merged, not
  replaced. A crash drops the claim. A live claim leaves the
  mail unseen so the next poll can take it.
- **Channel ack checks the bytes.** A job file rewritten after
  the read stays in the inbox. A same-length rewrite used to
  match the timestamp and get moved to done unread.
- **Version 2 answer slot.** Job ids that differ only past 120
  characters no longer share one question. A second valid
  answer is kept as late context. The first still wins.
- **Board offer returns a copy**, so a later complete cannot
  change the reply being sent.
- **Learning ledger trim replaces the file** instead of
  truncating it under a reader.

## 3.12.2 - 2026-10-21

- **Channel reliability.** A job whose failure is retryable stays
  unseen on the channel instead of being consumed, and a result
  that does not land rolls the seen-set back and leaves the
  envelope. IMAP SEARCH/FETCH are serialized with STORE. The
  security-events trim replaces the file instead of truncating
  it under another writer.
- **Board subcommands encrypt by default**, like `new`.
- **Protocol version 2 questions.** A question stays unseen
  until its answerer reads it, and the answer deadline starts
  at send.
- **Docs bent to shipped behavior.** The 2026-10-20 claims
  audit's 18 spec items are closed, and a 2026-10-21 round bent
  10 more docs, closed the three PROTOCOL.md items PC-01..03,
  and documented 30 previously undocumented knobs.

## 3.12.1 - 2026-10-21

- **Frozen builds include the version 2 module.** The one-file
  executables load `runner.protocol_v2` dynamically, so PyInstaller
  needs it named. The 3.12.0 tag failed that check in CI before
  anything was published. No protocol change.

## 3.12.0 - 2026-10-21

- **Protocol version 2, as messages beside a version 1 job.**
  A runner with `protocol_v2` sends a determination when the
  Oracle does not expect a clean pass, and a deterministic
  Oracle also sends the question it would have asked a local
  model. Any holder of a trusted secret may answer.
  `answer_only` is the laptop that answers and does not
  execute. One answer decides; a late one is context. The
  segments ride the version 1 result and do not change what
  runs. Off unless the operator turns it on. Jobs stay
  version 1.

## 3.11.63 - 2026-10-20

- **Version rev.** No functional change from 3.11.62.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.62 - 2026-10-20

- **Version rev.** No functional change from 3.11.61.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.61 - 2026-10-20

- **Version rev.** No functional change from 3.11.60.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.60 - 2026-10-20

- **Version rev.** No functional change from 3.11.59.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.59 - 2026-10-20

- **Version rev.** No functional change from 3.11.58.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.58 - 2026-10-20

- **Version rev.** No functional change from 3.11.57.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.57 - 2026-10-20

- **Version rev.** No functional change from 3.11.56.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.56 - 2026-10-20

- **Version rev.** No functional change from 3.11.55.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.55 - 2026-10-20

- **Version rev.** No functional change from 3.11.54.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.54 - 2026-10-20

- **Version rev.** No functional change from 3.11.53.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.53 - 2026-10-20

- **Version rev.** No functional change from 3.11.52.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.52 - 2026-10-20

- **Version rev.** No functional change from 3.11.51.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.51 - 2026-10-20

- **Arg-pattern timing test allows a slow Windows runner.**
  The v3.11.50 tag did not publish. `test_long_arg_is_fast`
  measured the whole job, and a loaded runner took 10.5s
  against a 5s ceiling. The main push of the same commit
  passed. The ceiling is 30s. The pattern is still linear.

## 3.11.50 - 2026-10-20

- **Version rev.** No functional change from 3.11.49.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.49 - 2026-10-20

- **Version rev.** No functional change from 3.11.48.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.48 - 2026-10-20

- **Version rev.** No functional change from 3.11.47.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.47 - 2026-10-20

- **Version rev.** No functional change from 3.11.46.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.46 - 2026-10-20

- **Version rev.** No functional change from 3.11.45.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.45 - 2026-10-20

- **Version rev.** No functional change from 3.11.44.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.44 - 2026-10-20

- **Version rev.** No functional change from 3.11.43.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.43 - 2026-10-20

- **Version rev.** No functional change from 3.11.42.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.42 - 2026-10-20

- **Version rev.** No functional change from 3.11.41.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.41 - 2026-10-20

- **Version rev.** No functional change from 3.11.40.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.40 - 2026-10-20

- **Version rev.** No functional change from 3.11.39.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.39 - 2026-10-20

- **Version rev.** No functional change from 3.11.38.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.38 - 2026-10-20

- **Oracle ask tests wait longer on a loaded Windows runner.**
  The v3.11.37 tag published, but its main push failed
  `test_random_questions_all_carry_the_line`: a loopback
  POST to the test server timed out at 5 seconds. The
  client waits 20 now.

## 3.11.37 - 2026-10-20

- **Windows process tree ignores a reused pid.** Toolhelp
  still names the previous owner's children. On the
  v3.11.36 tag a one-line job was charged with 144
  processes, the storm fired, and the env-gate test saw
  that audit line. The main push of the same commit did
  not. A process older than the job is not part of the
  tree. A process that cannot be opened is counted once
  and not walked. That tag did not publish.
- **`--inference-only` honors an in-place oracle_mode flip.**
  A Pi Light box that sets `oracle_mode` to `llm` in
  config.json and re-runs the flag now installs the model
  instead of skipping.
- **Result policy keeps the spec-required members.**

## 3.11.36 - 2026-10-20

- **Version rev.** No functional change from 3.11.35.
  That tag and its main push both finished green,
  Windows and SourceForge included. This tag is the
  next look.

## 3.11.35 - 2026-10-20

- **Version rev.** No functional change from 3.11.34.
  That tag and its main push both finished green,
  Windows and SourceForge included. This tag is the
  next look.

## 3.11.34 - 2026-10-20

- **SourceForge waits for a new file to be indexed.** The
  v3.11.33 upload landed, then the default-download PUT
  got a 404 and the job exited before the git mirror.
  That call now retries for about a minute.

## 3.11.33 - 2026-10-20

- **Version rev.** No functional change from 3.11.32.
  The FUTURE.md note about a USB neural-link peripheral
  landed after that tag, and its main push finished
  green, Windows included. This tag is the next look.

## 3.11.32 - 2026-10-20

- **Version rev.** No functional change from 3.11.31.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.31 - 2026-10-20

- **Version rev.** No functional change from 3.11.30.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.30 - 2026-10-20

- **Version rev.** No functional change from 3.11.29.
  The FUTURE.md edit landed after that tag, and its main
  push finished green, Windows included. This tag is the
  next look.

## 3.11.29 - 2026-10-20

- **Version rev.** No functional change from 3.11.28.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.28 - 2026-10-20

- **Version rev.** No functional change from 3.11.27.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.27 - 2026-10-20

- **Version rev.** No functional change from 3.11.26.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.26 - 2026-10-20

- **Version rev.** No functional change from 3.11.25.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.25 - 2026-10-20

- **Version rev.** No functional change from 3.11.24.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.24 - 2026-10-20

- **RESEARCHER_IDENT.md rides with the mutant tree.** The
  new root doc made the live-docs guard fail stats
  collection: mutmut only copies what also_copy names, and
  the main push of that file died in the test job before
  any build ran. It is on the copy list now.

## 3.11.23 - 2026-10-20

- **Version rev.** No functional change from 3.11.22.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.22 - 2026-10-20

- **Version rev.** No functional change from 3.11.21.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.21 - 2026-10-20

- **Version rev.** No functional change from 3.11.20.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.20 - 2026-10-20

- **Version rev.** No functional change from 3.11.19.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.19 - 2026-10-20

- **Version rev.** No functional change from 3.11.18.
  That tag and its main push both finished green,
  Windows included. This tag is the next look.

## 3.11.18 - 2026-10-20

- **Windows monitor test stamps inside the resource window.**
  The evidence was written before the monitor started, and
  the resource window only looks one second back. On the
  v3.11.17 main push that write took longer, so
  `resource_event` was missing while confinement (five
  seconds of slack) still matched. The tag of the same
  commit was fast enough to publish. The test now stamps
  from the monitor's own start.

## 3.11.17 - 2026-10-20

- **Version rev.** No functional change from 3.11.16.
  That tag published, Windows included. The only red run
  still on the board is v3.11.14, which v3.11.15 already
  fixed. This tag is the next look.

## 3.11.16 - 2026-10-20

- **Version rev.** No functional change from 3.11.15.
  The main run after that cut, including the v2 editor
  note, finished green, Windows included. This tag is the
  next look at the pipeline.

## 3.11.15 - 2026-10-20

- **Windows canary test stops tripping on its own rewrite.**
  The CRLF regression test replaced every `\n`, including the
  one inside an existing `\r\n`, so a file that was already
  CRLF became CR-CR-LF and the watcher correctly called that
  a content change. The v3.11.14 tag run failed build-windows
  on that and did not publish. The test now writes the other
  line ending of the same text.

## 3.11.14 - 2026-10-20

- **Mutation cannot pin a tag run for hours.** The job has
  no functional product change. It now dies at 40 minutes
  instead of the platform default of 6 hours. The v3.11.11
  run measured about 25 minutes; stacked tag runs were
  sitting in_progress long after the mirrors had published.
  Mutation stays a signal: it still cannot fail the publish.

## 3.11.13 - 2026-10-20

- **Version rev.** No functional change from 3.11.12.
  Last cut asked for on top of the one already on the mirrors.

## 3.11.12 - 2026-10-20

- **Version rev.** No functional change from 3.11.11.
  v3.11.11 is already on the mirrors; this cut is the
  rev that was asked for on top of it.

## 3.11.11 - 2026-10-20

- **Windows build can finish.** The guided-fuzz campaign
  compared coverage across two runs in one process. On the
  Windows runner those sets disagreed by four lines inside
  `runner.runner.log`, the minute-rollover branch, which is
  wall-clock gated. The tracer no longer records that
  function, so a campaign's coverage is the parsers again.
  v3.11.10's Windows job failed on this and never published.

## 3.11.10 - 2026-10-20

- **job-fuzz: a sense that fuzzes the jobs this box
  already ran.** A new example sense plus a core one-shot
  door (`--run-variant FILE`): the sense keeps a bounded
  corpus of the runner's retained jobs, mutates them on
  idle cycles only, and runs each variant through the
  runner's own validation and confined execution; findings
  file as Oracle signals (hard failures, divergence from
  the seed's recorded outcome, coverage novelties) and are
  context for future opinions, never a gate on the seed
  job. Variants are mutations of verified jobs, so they
  are never admitted through the job path; the door copies
  an allowlist of job keys and drops everything else. The
  corpus learns: novelty-reaching variants are promoted
  into a distilled tier, splice and dictionary mutators
  widen the neighborhood, relation probes carry an
  expected class and digest, interesting variants are
  minimized before they file, hard failures triage into
  reason buckets, and seeds earn their budget by yield.
- **Windows fixes.** job-fuzz splits its runner command
  per platform (POSIX shlex ate the backslashes out of
  Windows paths, so no campaign could run there), and the
  Pi Light end-to-end test drains the wake gate's brief
  thread before its temp tree comes down. 3.11.9 was
  tagged but never published: its release build failed on
  that cleanup race (WinError 145). This release
  supersedes it.

## 3.11.9 - 2026-10-20

- **Mutation stats can finish.** mutmut's stats pass sets
  `MUTANT_UNDER_TEST=stats` and rewrites the mutated module
  with trampolines that need mutmut's own process. The DTLS
  sidecar inherited that variable, hit
  `validate_shared_secret` on startup, and died with exit 1,
  so `pytest -x` aborted the stats run ("failed to collect
  stats"). Transport children now drop the variable and run
  the original module. A raw docstring in `review.py` also
  drops the invalid-escape SyntaxWarning Python 3.12 printed
  during that job.

## 3.11.8 - 2026-10-20

- **Version rev.** No functional changes from 3.11.7; the
  tree is identical apart from the version constants and
  this entry.

## 3.11.7 - 2026-10-19

- **Strictness batch.** The protocol version field is now
  checked as an integer in the strict sense: JSON `true`
  and `1.0` are refused, as draft Section 9 states. Key
  selection follows draft Section 10: a present `key_id`
  must name a configured secret or the job is refused
  before its MAC is checked; the empty identifier names
  the default secret. Downloads accept `https://` URLs
  only, and a redirect to any other scheme is refused.
  The DTLS transport extension enforces the shared-secret
  entropy floor at its own endpoint and refuses to start
  below it, as the sender already did. Malformed DTLS
  records are logged at WARN instead of dropped silently.
- **Documentation corrections from the claims audit.**
  CONTRIBUTING's chat-privacy account now rests on
  redact-before-write, which is what the code does; two
  parked items -- the `av` detections sense and the
  Windows WFP cage -- are described as not built, which
  they are; and a set of smaller audit fixes lands across
  thirteen documents.
- **Seeded mutation testing.** A scheduled, non-gating
  twin of the release mutation job reruns the security
  module's mutants under a fresh recorded seed each week,
  so order-dependent survivors have nowhere permanent to
  hide. The release job itself is unchanged and stays
  deterministic.

## 3.11.6 - 2026-10-19

- **The cleartext posture, completed.** 3.11.5 refused an
  unencrypted job on the shipped CLI path; the refusal now
  applies at the one acceptance point every channel
  funnels through, so the form decides, not the channel:
  mail, file, NATS, and DTLS deliveries are refused alike,
  with key-policy reject semantics (message marked seen,
  an `auth_rejection` event recorded, the job_id not
  recorded in the seen set). `--allow-cleartext` remains
  the only enable and there is still no configuration
  key; `install.py` can now bake the flag into the
  installed service command like the other run flags, the
  startup log announces it when on, and the diagnose
  harness sends its round-trip job encrypted so it works
  without the flag. The spec text states the posture in
  full: draft Sections 16, 17, and 19.4, PROTOCOL.md
  Section 8, and the configuring doc. The test suite's
  fixtures now send encrypted jobs end to end, which is
  what surfaced the next fix.
- **`reply_to` routing fixed on the email transport
  extension.** The extension read the result's destination
  out of the raw job body, so for encrypted jobs — the
  default form — results fell back to the mailbox instead
  of the job's `reply_to`. The core now states its routing
  decision in a `<ident>.target.txt` sidecar beside the
  channel result (additive at transport contract v1;
  extensions that ignore it behave as before), and the
  extension honors it after re-checking the address
  against the same rule the direct path applies. Found by
  the fixture migration above: cleartext fixtures had
  been masking it.
- **New FAQ entry:** why the one shared secret safely
  keys both the HMAC signature and the job encryption —
  the AES key is an HKDF output, neither construction
  feeds the other, and the stated cost of reuse is that
  a compromised secret opens both.

## 3.11.5 - 2026-10-19

- **Cleartext is a flag, not a mode.** The runner refuses an
  HMAC-signed job that is not encrypted unless it was started
  with `--allow-cleartext`. `send_job.py --cleartext` and
  `send_dtls.py --cleartext` still send that body, and the
  shared secret is still required. There is no config key
  for this. Encrypted jobs are unchanged. Protocol version
  stays 1.

## 3.11.4 - 2026-10-19

- **PROTOCOL.md names the AEAD primitive.** The crypto
  section still claimed "exactly two cryptographic
  primitives" and "the protocol does not encrypt
  payloads" — text from before per-job encryption
  shipped. It now names the third primitive (AES-256-GCM,
  keyed per job by HKDF-SHA-384, the signed `hp_enc`
  envelope, verify-before-decrypt, receiver MUST accept)
  and states the shipped posture: confidentiality is a
  property of the signed object, the reference senders
  encrypt by default, and cleartext is an explicit
  sender choice, never a silent fallback. Documentation
  only; no behavior change.
- **Docs match the draft.** PROTOCOL no longer treats email
  as the whole protocol, no longer calls `job_id` a UUID,
  and no longer says a cleartext job's confidentiality is
  the mail TLS hop. The FAQ, the configuring doc, the
  example config, and the `mail_tls_required: false`
  warning say the same thing: that switch relaxes hop
  verification, and the confidentiality property is the
  envelope. `STYLE.md` is gone; the mutation copy list
  no longer names it. FUTURE.md marks BUILT entries as
  a decision record, not work.

## 3.11.3 - 2026-10-19

- **falco-feed files `Error`-priority rules.** The sense
  named all eight of Falco's priorities but mapped only
  seven; an `Error` alert fell into the malformed bucket
  and was ignored. `Error` now files as `falco_critical`
  (high) — the error-and-above tier — and a test accounts
  for all eight names.
- **Inline `script_sha384` is verified.** `execute_job`
  checked the digest only for `script_url` downloads; an
  inline script carrying `script_sha384` ran unverified.
  The digest of the script's UTF-8 bytes is now checked
  before staging, as PROTOCOL §3.2's −2 class always
  claimed.
- **Documentation consistency pass.** PROTOCOL.md's
  internal contradictions are resolved (the freeze was
  lifted for these deltas): §5 verification is stated
  per message type and names the job-shape checks behind
  the −2 class; the redacted view carries
  `output_digest`; task IDs state their own rule; "seen"
  distinguishes the mail flag from the seen-set; budget
  accounting is per key ID throughout; the confinement
  predicate excludes the runner's own tree. The same
  internal-consistency pass ran over every live document
  — README, INSTALL, RUNBOOK, TRANSPORTS, the security
  docs, `docs/`, the IETF draft (envelope steps now
  select the key before verifying the MAC; the
  SP 800-38D reference cites the right document),
  hardening, and the extension READMEs.

## 3.11.2 - 2026-10-19

- **Coverage report.** Statement coverage on the 3.11.1 tree
  is 94.2% (14436 of 15326), 93.1% with branches, from 3979
  tests. The report is `docs/reports/v3.11.1/coverage.md`.
  No runner behavior changes in this release.

## 3.11.1 - 2026-10-19

- **DTLS key schedule uses the suite's hash.** Suite
  0x1302 fixes SHA-384; the AES change had left the
  handshake hash on SHA-256, with the PSK binder splice
  and the stateless cookie sized for a 32-octet digest.
  Transcript, HKDF schedule, Finished, binder, and cookie
  now ride SHA-384 end to end, pinned by tests including
  the in-test RFC 8446 recomputation.
- **No mandatory binding.** The draft no longer requires
  the email binding: conformance is per binding, an
  implementation offers at least one binding, and email
  is the default by guidance, not by mandate.

## 3.11.0 - 2026-10-19

- **AES-256-GCM.** Per-job encryption is AES-256-GCM (NIST SP
  800-38D). The envelope algorithm id is
  `aes-256-gcm/hkdf-sha384`. The DTLS ciphersuite on the wire
  is TLS_AES_256_GCM_SHA384 (`0x1302`). ChaCha20-Poly1305 is
  gone: a job or result encrypted by 3.10.1 or earlier does
  not decrypt.

## 3.10.1 - 2026-10-19

- **One protocol, version 1.** This release supersedes the
  3.10.0 tree, which was tagged before the no-v2 restructure
  landed. There is no protocol version 2: the DTLS session
  support is a binding of version 1, specified in the same
  IETF draft, and the DTLS greeting's `v` field carries the
  protocol version (1). Per-job AEAD encryption is a
  required capability of version 1 — implementations MUST
  support it, the reference sender encrypts by default, and
  cleartext is sent only by a sender's explicit choice.
- **Conformance is per binding.** The draft now states the
  security requirements as properties: object authentication
  (the signature/MAC) is REQUIRED on every binding and never
  moves to the transport; confidentiality is REQUIRED as a
  property on every binding and may be satisfied by the
  binding itself. On the DTLS binding the session provides
  it, so per-job encryption is OPTIONAL for the sender there
  (receiver support stays REQUIRED everywhere); on email and
  NATS the per-job encryption carries it; on the file binding
  it is local policy. A runner MUST offer the email binding.
- **Pipeline hardening.** The transport and encryption parser
  surfaces were fuzz-campaigned; the Windows surface is now
  simulated locally (path separators, SSL stores) so platform
  failures surface before CI; test-isolation fixes keep the
  suite green under shuffled order and unprivileged runs;
  `jobcrypto` validates key and nonce sizes in its own
  vocabulary; the audit report reads UTC stamps as UTC. The
  ruff gate is green on the whole tree.
- The Windows-surface simulator overlays `windll` even when the
  host already has one — an elevated runner's `IsUserAnAdmin`
  returns 1 — and restores the host objects afterwards.

## 3.10.0 - 2026-10-19

- **Transports are extensions.** The runner core is
  transport-blind: email, the watched folder, and NATS each run
  as a standalone extension program under one contract
  (TRANSPORT_API_VERSION = 1), supervised by the runner over
  per-extension file channels. Email remains the default; a
  3.9.0 config works unchanged; the shared secret is never
  handed to a carrying pipe. Anyone can drop in a transport —
  a valid manifest loads, registered or not.
- **DTLS session binding.** A new `dtls`
  transport extension terminates DTLS 1.3 sessions directly:
  the shared secret as external PSK, `psk_dhe_ke` only
  (forward secrecy is a hard requirement, resumption
  included; `psk_ke` is never offered or accepted),
  connection IDs so NAT rebinding survives, a stateless cookie
  exchange before any large flight. Off until the owner
  enables it — the product's first network-facing inbound
  listener (the loopback local-signal socket and the Oracle
  page predate it). The
  session's first message is the greeting: platform
  information tiered by the responder's own configuration
  (`none` / `family` / `standard` / `full`, default family),
  sent only after authentication. Client: `cloud/send_dtls.py`.
- **Per-job encryption, on by default.** `send_job.py` wraps
  the signed body in an AEAD envelope (AES-256-GCM,
  HKDF-SHA-384 key from the job's selected secret; stdlib-only
  `runner/jobcrypto.py`). The runner verifies the signature
  before decrypting; results mirror the job's form;
  `job_encryption` overrides explicitly; `--cleartext` is the
  deliberate interop escape. Cleartext jobs are still accepted
  and logged as such. No forward secrecy, stated wherever the
  feature is described: a compromised secret exposes every
  recorded encrypted job.
- **Mail TLS, required and forward-secret.** `mail_tls_required`
  (default true): IMAP over implicit TLS, STARTTLS required
  with the peer certificate verified, TLS 1.2 floor — and in
  the required posture TLS 1.2 sessions are pinned to ECDHE
  suites, so the hops are forward-secret as 1.3 is by
  construction. The opt-out relaxes verification only; no
  setting enables cleartext mail.
- **One draft, one version.** The IETF documents
  consolidated into `draft-homing-pigeon-00` (the one
  canonical file): one protocol version, with the email,
  file, NATS, and DTLS bindings in one numbering and one
  reference list — the DTLS work is a binding of version 1,
  not a second version. The short-lived pointer files are
  removed; the -00 file is the document itself. The draft's
  mail binding now requires TLS (MUST, RFC 8314/8996/9325),
  and per-job encryption is a requirement of the protocol,
  not an optional extension.
- FAQs gained the email-binding census and two refusals with
  reasons: no PGP/S/MIME (a cloud SI has a connector, not a
  mail client), and no public-key cryptography in the core
  protocol (no strangers to introduce; symmetric end to end,
  which is also the quantum-resistant posture).
- Windows Oracle chat answers a refused `/ask` (bad token,
  bad origin, oversized body) with that status. The body is
  read first, so the socket is not aborted before the browser
  can see it.

## 3.9.0 - 2026-10-19

- **The Oracle learns from its own calls.** Each opinion is
  frozen before the job runs and scored against the outcome
  in a local learning ledger, written before the result goes
  out. Two lesson channels: verified execution facts, and
  model-formed candidates born uncorroborated, promoted only
  by later corroboration, retired permanently by one
  contradiction. Each job reads the ledger fresh, host- and
  feature-filtered. A lesson authorizes nothing by itself —
  repair still needs the latitude, the mismatch re-verified
  on this job, and the result re-judged. Keys:
  `oracle_learning` (on), `oracle_learning_model` (off),
  `oracle_learning_promote_after` (2).
- README rebuilt as a landing page; the Windows test fixes
  that 3.8.9 needed landed here (POSIX assumptions in the
  coverage pins).

## 3.8.9 - 2026-10-19

Tagged but never published: the Windows build failed
(coverage-pin tests assumed POSIX) and 3.9.0 superseded it
the same night. Content: in-core file and NATS transports
beside email, and the two-gate rule — a credentialed
transport's required authentication counts as a second gate
beside the HMAC signature. Both were re-homed as transport
extensions in 3.10.0.

## 3.8.8 - 2026-10-19

- Fix: opinion predictions attach only under the effective
  latitude, not the job's raw request (claims audit B46).
- SourceForge and GitLab publish as jobs inside the tag build
  instead of separate workflows.
- Claims audit round 2 closed: 196 claims re-inventoried and
  resolved against the tree; satire kept by the maintainer's
  vote.

## 3.8.7 - 2026-10-18

- The Oracle's opinion defaults to `repair`: one certain
  environment mismatch is fixed before the run, re-judged, and
  recorded with the received digest. Owner ceiling `diagnose`
  restores the old behavior exactly.

## 3.8.6 - 2026-10-18

- Fix: `requirements-ci.txt` joins the mutation copy list;
  the 3.8.5 mutation job died in stats collection without it.

## 3.8.5 - 2026-10-18

- **IDS collectors:** eight adapters (Falco, Suricata, Zeek,
  osquery, Sysmon, AIDE, softflowd, Wazuh); osquery is the
  measured install default (~27 MB idle; Zeek ~230 MB, opt-in
  only). Capability-probed: installed is not sensing.
- **Remediation:** jobs that diverge from their opinion
  envelope can be stopped mid-run — deterministic tripwires
  (process storm, credential artifact, confinement escape)
  kill on sight; `remediation_mode: oracle` adds judgment for
  unlisted divergences, abstention recorded, never converted
  to a kill. Quarantine never deletes; AV referral records
  the scanner's own verdict. Default `deterministic`.
- Training Watch joins the extension catalog (24 senses).
- Release pipeline lifts from the OneFuzz audit: SHA-pinned
  actions, default-deny workflow tokens with exact per-job
  grants, BUILD-PROVENANCE.json in every archive, an SPDX SBOM
  among the nine release assets, pinned CI tooling,
  docs/verification.md.
- Fix: `--oracle-opinion` startup exit (string flag in the
  numeric overrides set).

## 3.8.4 - 2026-10-18

- Docs only: the remediation design written in full; STYLE.md
  trimmed; TRANSPORTS.md status note; the front page stops
  selling the lockdown posture as the shipped default.

## 3.8.3 - 2026-10-18

- Two senses: Resource Sentinel (rolling-window rates, not
  samples) and Job Watcher (per-job baselines from `retained/`).
  Catalog: fifteen.

## 3.8.2 - 2026-10-18

- **The Oracle's opinion is built:** a job may request a
  latitude (`off`/`diagnose`/`advise`/`repair`), capped by
  `oracle_opinion_mode`; tier-1 checks are deterministic; a
  repair is never silent and carries `received_digest`.
- **Pi Light:** `oracle_mode: deterministic` — the full
  runner and protocol with no local model — plus the ARM64
  Pi Light archive whose `default_profile` marker selects it.
- `dag_mode: advisory` (PROTOCOL 13.1); thirteen worked senses
  ship as examples; one-process CLI overrides for the runtime
  knobs; counted `-v` verbosity; the invocation line logged
  shell-quoted; designed `--help` on all three front doors.

## 3.8.1 - 2026-10-18

- Docs: the Oracle's-opinion design recorded (FUTURE.md +
  docs/oracle-opinion-design.md). Design only; built in 3.8.2.

## 3.8.0 - 2026-10-18

- **Claims audit:** 106 doc claims inventoried and decided one
  by one; corrections landed across the live docs (external
  facts re-verified, including the Mandiant acquisition and
  the Cloudflare Queues tier figures). PROTOCOL §8 names the
  two primitives actually used and states the protocol does
  not encrypt payloads; §10.1 names qwen3:1.7b the tested
  reference model. ORACLE_DASHBOARD.md removed.

## 3.7.41 - 2026-10-18

- Test fix: the local-signal fixture joins its brief thread
  before temp-dir cleanup (Windows WinError 145).

## 3.7.40 - 2026-10-18

- **Local signals:** same-box senses and extensions deliver
  signed alerts without mail — a watched `local-inbox/` folder
  (~1 s scan) or a loopback socket (port 39271) — through the
  mail path's one ingest core and gates. A high-severity local
  alert can wake the Oracle through a deterministic,
  cooldown-limited gate; the brief is recorded, never acted on
  by the gate itself.

## 3.7.39 - 2026-10-18

- Docs: the README prompt points at the published protocol
  URL (pigeon-home.com/PROTOCOLv1).

## 3.7.38 - 2026-10-18

- **User extensions:** a folder + `extension.json` manifest
  (declared signals, own semver, API version); strict manifest
  validation, undeclared signals refused at ingest, broken
  extensions refused and logged without touching the agent.
- The notable-access line in a retained summary names its own
  job id, so small models stop transplanting it onto neighbors.

## 3.7.37 - 2026-10-18

- Fix: `output_retention_days: 0` means keep-forever on every
  path (the expiry check's `or 7` disagreed with the prune).
- Coverage-guided fuzzing over the parser surfaces joins the
  suite (150 rounds, corpus grows only on new coverage).
- CI: the Windows shard reporter can no longer be crashed by
  its own output (UTF-8 end to end).

## 3.7.36 - 2026-10-18

- Security: the Oracle's log-tail context feed is scrubbed of
  quoted model replies and flagged jobs' logged output —
  runner.log itself keeps everything.
- CI: mutation's repeated in-process suite counts fixed
  (module-cache collision).

## 3.7.35 - 2026-10-18

- Security: a flagged (suspicious-access) job's raw output is
  withheld from the Oracle's context — summary, script, and a
  digest marker instead; the withheld text still feeds the
  reply gate as scan-only. CI: `tools/` joins the mutation
  copy list.

## 3.7.34 - 2026-10-18

- Default model is `qwen3:1.7b`, winner of the full eval
  battery (clean catches, no invention, history and detail).
  `--faster` pulls qwen2.5:3b.
- CI: the Windows suite runs sharded across four workers.

## 3.7.33 - 2026-10-18

- CI: a failed mutation job no longer fails the tag build
  (signal kept; mirrors key off the run conclusion).

## 3.7.32 - 2026-10-18

- Oracle chat: owner instructions dispatch — an action
  request whose first reply is prose-only is re-asked once
  with a directive to call the tool or name the blocker.

## 3.7.31 - 2026-10-18

- The interactive Oracle's charter restored: the owner's
  debugging partner with full hands (the mailbox prompt keeps
  its disclosure boundary; both sides pinned by tests).
- Fix: a job id ending in a newline is rejected (`$` matched
  before it).
- Coverage/mutation reports for 3.7.30 archived (91.8%
  statements; runner/security.py mutation 458/537 killed).

## 3.7.30 - 2026-10-18

- CI: the root manuals join the mutation copy tree (the tag
  job died on a missing INSTALL.md).

## 3.7.29 - 2026-10-18

- The Oracle chat works again in the browser: a raw newline
  inside a JS string had made the page's whole script a
  SyntaxError (Send did nothing); a `node --check` regression
  test now parses the served script. The chat box starts
  empty, loopback Sends without an Origin header reach the
  model, and the no_secrets attestation scans job output
  again (a merge had dropped its binding).

## 3.7.28 - 2026-10-18

- CI: mutation runs on version tags only.

## 3.7.27 - 2026-10-17

- `--faster` pulls qwen2.5:3b (the 1.5B model's Flag321
  verdicts didn't hold across paraphrases).

## 3.7.26 - 2026-10-17

- Protocol: messages use `"v": 1` again (see 3.7.20).

## 3.7.25 - 2026-10-17

- `--oracle-cli`: the terminal Oracle chat on the same ask
  pipeline as the web window.
- Detection: job summaries carry a deterministic "notable:"
  line when a script referenced a credential store or a path
  outside its workspace; artifact scan gains built-in YARA
  rules (hp_cred_dump, hp_reverse_shell) with ATT&CK tags.
- Flag321 field scenario pinned as unit tests (retention and
  context contracts).

## 3.7.24 - 2026-10-17

- Frozen builds ship the whole runner again: the importlib
  loader hid sibling modules from PyInstaller, so one-file
  builds silently omitted them. Every dynamic module is now a
  hidden import on all platforms, guarded by a test; Linux and
  macOS smoke the binaries' `--version`.
- Hardening: state files opened no-follow throughout; path
  containment for retained jobs, sandbox scripts, and the
  Oracle's file tools. Suite: 1,954 tests.
- Dependabot bumps folded in; Docker base python:3.14-slim.

## 3.7.23 - 2026-10-17

- Oracle chat: structured-data dumps and tool-call-shaped
  replies are withheld and re-asked once for plain prose.

## 3.7.22 - 2026-10-17

- Both mirrors carry the full release (archives, wheel,
  sdist, SHA384SUMS); first unattended GitLab publish.

## 3.7.21 - 2026-10-17

- Releases publish to SourceForge (best-effort; GitHub and
  PyPI never wait on it).

## 3.7.20 - 2026-10-17

- Protocol v2 on the wire: messages carry `"v": 2`; v1 is
  rejected unless the operator opts in per process with
  `--allow-protocol-v1`; the 128-bit secret floor is enforced
  on the sender too. PROTOCOL.md and the draft continue to
  specify v1, the specification of record. (3.7.26 returned
  messages to `"v": 1`.)

## 3.7.19 - 2026-10-17

- Debuggable logging: runner.log bounds become config
  (defaults 32 MB × 4), full job stdout/stderr land in the
  log, and an opt-in `oracle.log` keeps full-fidelity
  inference records (~2 GB worst case). Secrets never enter
  either log.

## 3.7.18 - 2026-10-17

- `--diagnose`: a black-box gauntlet against the real
  configured system (config audit, mailbox auth, model
  reachability, a signed round-trip job, an Oracle-context
  audit, acceptance probes, senses snapshot) writing a
  verdict report; the exit code counts failed sections.

## 3.7.17 - 2026-10-16

- The Oracle chat gets a real interface: bubbles, clock
  stamps on every message, elapsed time on the Working
  bubble. Summary questions are answered from the job index
  without tool rounds.

## 3.7.16 - 2026-10-16

- Version-only release moving the checkpoint line.

## 3.7.15 - 2026-10-16

- `--faster` for installer and runner: the 1B model for one
  process or an install, config untouched on a normal upgrade.

## 3.7.14 - 2026-10-16

- The chat cannot stall in silence: a Working indicator with
  elapsed seconds, warm model (keep_alive + background
  warm-up), a per-question wall-clock budget, empty stdin for
  tool commands. Summaries come from a computed job index at
  the head of the context, not the log tail.

## 3.7.13 - 2026-10-16

- Low-profile senses ride the existing watches: ATT&CK labels
  on audit lines, host-log tails, a one-line firewall posture
  diffed against its baseline, post-job artifact scans when a
  scanner is already installed, canary and AV-posture filings.
- runner/detection.py: per-job Sigma/YARA-style evaluation
  with ATT&CK ids and a rolling baseline; advisory only.

## 3.7.12 - 2026-10-16

- Oracle system watch on by default: Windows Event Log tail,
  registry persistence watch (diffed), canary tripwires with
  tokens that never silently re-baseline. (Supersedes the
  unpublished 3.7.11, whose Windows build failed.)

## 3.7.10 - 2026-10-16

- The local chat prompt is separated from the cloud ask
  rules: the operator is at this computer; open the files.
  The mailed ask path keeps its disclosure rules.

## 3.7.9 - 2026-10-16

- Property-based tests (Hypothesis) over the protocol core —
  and a real bug they caught: the signed-body extractor could
  pick a `{` inside a string literal as the object opener and
  reject a valid body. Infinity config values hardened.

## 3.7.8 - 2026-10-16

- Oracle agent: content-embedded tool calls replay as plain
  chat (Ollama rejected fabricated call history); inference
  failures log the endpoint's response body.

## 3.7.7 - 2026-10-16

- PROTOCOL.md ships inside the release binaries; the Oracle's
  prompt points the local model at it on demand.

## 3.7.6 - 2026-10-16

- The Oracle chat page opens with a role statement and a
  pre-filled summary prompt; content-embedded tool calls from
  small local models are detected and executed (known tool
  names only); the system prompt teaches the model the
  project's vocabulary and this box's real state paths.
