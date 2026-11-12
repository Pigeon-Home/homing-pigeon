# macOS hardening notes

The runner installs on macOS from the same tree as everywhere
else (`install.py` writes a launchd agent for the runner).
This page is about the one mechanism macOS needed a backend
for: confinement.

## Confinement on macOS

There is no bwrap on macOS, and there is no jail or namespace
to build on: the macOS confinement backend is a Seatbelt
profile, applied per job by `sandbox-exec`, plus a small
launcher shim that applies the spawn resource limits. What it
applies, at `enforce`, is named exactly in every audit and
startup record:

```
macos: seatbelt_profile + no_network + spawn_resource_limits
```

Each job runs under a profile generated for that job: the
profile starts from deny-by-default, lets the job execute and
read the system trees and its interpreter's own install
prefix, lets it read and write only inside its own work
directory, and names no network allow rule at all — the
deny-by-default base is the network denial, and the profile
states a `(deny network*)` line beside it so the record of
the profile says what it does. The memory ceiling is applied
at spawn: the job's command runs under a small launcher shim
(the runner's own interpreter, a few lines) that sets the
data-size resource limit to 512 MiB per process with
`setrlimit` and then `exec`s the job's command, the macOS
shape of the FreeBSD backend's `limits(1)` step, which
macOS has no equivalent of. Only the data-size limit is
set, never the virtual-memory (address-space) limit: the
address space a macOS process maps at startup already
exceeds 512 MiB, and a 512 MiB address-space ceiling made
every confined spawn abort before its first line of job
code in the backend's first live run — the fix for that
failure, and its suppositions and conclusions, stand at
the end of this page. `sandbox-exec` wraps the
shim, so the profile is in force before the shim's first
line runs, and the job never runs a line unconfined. The
profile is generated per job and passed to `sandbox-exec`
as an argument; it is never written to a file.

What this does not provide, plainly:

- App Sandbox is not used. App Sandbox is an entitlement a
  bundled application opts itself into; this runner starts
  arbitrary job interpreters that carry no entitlement, so
  it does not fit the launcher shape. Seatbelt through
  `sandbox-exec` is the mechanism that fits a launcher.
- The profile is not a filesystem namespace. It is a
  mandatory-access profile over the host filesystem the job
  process runs on: paths the profile does not name cannot
  be read, which is stronger than the Windows backend (whose
  confined jobs can read any path their token can read),
  and it is not the FreeBSD jail's separate root — the job
  sees the host's path layout, and the profile, not a
  mount table, is what refuses it.
- The memory ceiling is a per-process resource limit applied
  at spawn (`setrlimit` in the launcher shim), not a
  Seatbelt rule: Seatbelt has no resource-limit operation,
  which is why the shim exists. The record names
  `spawn_resource_limits` for exactly that reason, the same
  naming the FreeBSD backend uses for its `limits(1)` step.
- Seatbelt is Apple's supported mechanism for this shape
  through `sandbox-exec`, and it is also a mechanism Apple
  has marked deprecated as a command-line tool while still
  shipping it and still building App Sandbox on the same
  profile language. The backend probes for the tool at
  startup and refuses when it cannot engage, so a macOS
  release that removes it fails closed here, not open.

At `enforce` the startup gate probes the backend — the tool
present, a generated profile that parses, and a trial spawn
under the full controls that reads a staged file inside its
work directory and writes its output there — and refuses to
start when the probe fails, naming why. A job whose own
confined spawn cannot be created is refused at job time the
same way; there is no path on which a job runs unconfined
under `enforce`.

## The mode a macOS config states

A fresh macOS install writes `security.modes.confinement`
into `config.json` at `audit`, stated in the file — the same
statement it made before this backend existed, kept for the
same reason the Windows and FreeBSD seeds keep theirs: the
installer and the setup wizard write the seed without
running the backend probe on that machine, and stating
`enforce` sight-unseen risks a first-start refusal on a
machine where the profile cannot engage. The operator steps
the mode up to `enforce` deliberately, and the startup gate
then verifies the probe on that machine. At `audit`, jobs
run unconfined and the audit log records what the mode would
have done. `job_user` is not stated down: the POSIX demote
engages on macOS as it does on Linux.

## Supposition, recorded before the build

Recorded 2026-11-11, before the backend was built or run
anywhere, mirroring the records the Windows and FreeBSD
backends carried into their own first tests:

Before this backend, confinement at `enforce` on macOS
refused at startup ("confinement (bwrap) is Linux-only; this
machine is darwin") and the platform seed stated the mode at
`audit` because there was no backend behind it. The
supposition is that, with the backend landed, on the CI
macOS legs (macos-15 and macos-15-intel — there is no Mac in
the project's own fleet, so CI is the field test for this
platform, and the claims below stand only to the strength
that proof gives):

- the startup probe returns None on a host where
  `sandbox-exec` is present and a trial process confined
  under a generated profile can read its staged file and
  write its work directory, and the runner starts with
  confinement at `enforce`;
- each exec job's audit record names exactly "macos:
  seatbelt_profile + no_network + spawn_resource_limits";
- an escape write to a host path outside the work directory
  does not land — the profile names no write allow rule for
  it, so Seatbelt refuses the write;
- an escape read of a host file outside the system trees,
  the interpreter prefix and the work directory does not
  return its contents, for the same reason;
- a job process carries the 512 MiB spawn resource limits
  (its own `getrlimit` reads them back), applied by the
  launcher shim before the job's command is `exec`d;
- a job that tries to open a network connection is refused
  by the profile, which names no network allow rule;
- off macOS, the backend is an import-safe stub whose probe
  always answers a problem string, so a simulated darwin on
  any other host refuses deterministically, exactly as the
  Windows and FreeBSD stubs do on their simulated platforms;
- the seeded posture does not move: a fresh macOS install
  still states `confinement` at `audit` in the file.

Conclusions from the CI proof are recorded in the place
this supposition stands, after the proof runs.

## Conclusions, as they stand (2026-11-11)

The backend landed on 2026-11-11 as described above:
`runner/guard/macos_confine.py`, wired into the confinement
startup gate, the argv gate and the spawn seam, registered
in the core list (the list stands at 136 files, the figures
re-measured over the grown tree), with the support matrix
and the default-posture page stating what it applies.
What is proven, and what is not, as this section stands:

- The off-darwin half of the supposition is proven. The
  contract tests run green on a Linux host: the profile
  writer per field, the launcher shim per field, a
  bookended fuzz family around the profile text, the
  trial-spawn proof's failure naming, the startup gate,
  the argv gate and the spawn seam (which records exactly
  "macos: seatbelt_profile + no_network +
  spawn_resource_limits"), and the seed shape — a fresh
  macOS install still states `confinement` at `audit`.
  The stub half stands as supposed: off darwin the probe
  always answers a problem string, and a simulated darwin
  refuses deterministically.
- The live half has now had CI's word, and the word is
  failure. The live tests run only on the CI macOS legs,
  and they were skipped on the Linux host the contract
  tests ran on, exactly as their skip reasons are
  registered. On the landed tree's build (build run
  43089173541), the test-macos job (job 130770346469)
  completed with a failure verdict at 12:07 PM PST on
  2026-11-11 — minutes after an earlier form of this
  section, written while that job was still in progress,
  had correctly recorded it as still in progress. All
  6 tests in the live class (`LiveBackendTest`) failed.
  The confined spawn aborted with exit -6 and could not
  read its staged file, and that one shape is the root
  of the live failures as they stand.
- What that verdict proves, and what it does not, stated
  exactly. Refuted as landed: the probe-engages point
  (`test_the_probe_engages`) and the point that a spawn
  runs inside the profile
  (`test_a_spawn_runs_inside_the_profile`) — the probe
  did not engage cleanly, and a confined spawn did not
  run inside the profile and read its staged file.
  Unproven, not refuted: the escape write
  (`test_an_escape_write_does_not_land`), the escape
  read (`test_an_escape_read_does_not_return_contents`),
  the network refusal
  (`test_a_network_attempt_is_refused`) and the spawn
  limits (`test_the_spawn_limits_are_carried_by_the_job`)
  produced no evidence either way, because the confined
  spawn aborted before any of them could be exercised.
  Seatbelt was never shown to allow an escape: no escape
  landed, and no refusal was shown either — those points
  simply have no verdict yet.
- The same job carried a separate failure family on the
  darwin host: 4 failures in `test_windows_confine` — a
  fallback name recorded as `macos_confinement_failed`
  where `windows_confinement_failed` was expected, and
  3 failures of the form `TypeError: _spawn() got an
  unexpected keyword argument 'user'`. That is a
  darwin-host seam regression, recorded separately from
  the live verdict above; it is not evidence about the
  Seatbelt profile itself.
- No later head has a completed test-macos verdict as
  this completion stands: the builds after the landed
  tree's build were cancelled (with no test-macos job
  completed) or were still pending, so this failure is
  the only completed live verdict on record.
- The support level therefore does not move up. It
  stands exactly as the support matrix states it —
  Supported, reduced confinement — on the basis stated
  there. The live proof remains open: it closes only
  when a fix has landed and a test-macos job on a head
  carrying that fix completes green. Until then the
  live supposition points stand as this verdict leaves
  them — 2 refuted as landed, 4 unproven — and no field
  proof on project hardware is claimed — there is no
  Mac in the project's own fleet.

## Suppositions for the fix, recorded before the fix

Recorded 2026-11-11, after the failure verdict above and
before any fix was written, from a first-hand read of
`runner/guard/macos_confine.py` and of the spawn seam in
`runner/ops/remediation_ops.py`. Three mechanisms are
supposed, one for each failure shape; the fix that
follows is built to these, and the conclusions section
below is completed against them.

- S1, the live abort (the primary supposition). Every
  confined spawn passes through the launcher shim, and
  the shim sets both `RLIMIT_AS` and `RLIMIT_DATA` to
  512 MiB and then `exec`s the job's command. On macOS a
  process's virtual address space at interpreter startup
  — the dynamic loader, the dyld shared cache and the
  system libraries every process maps before its first
  line of code — already exceeds 512 MiB, on Apple
  silicon by a wide margin. The supposed mechanism is
  therefore not the Seatbelt profile's file rules at
  all: the shim's own interpreter starts under the
  profile and runs (the profile lets it), and the abort
  lands at the next `exec`, when the job's interpreter
  tries to come up under a virtual-memory ceiling
  smaller than its own startup mappings and dies by
  SIGABRT (exit -6) before any job code runs — which is
  why every live test failed with the same shape (no
  output, no DENIED markers, no limits read back) and
  why the escape, network and limits points produced no
  evidence either way. The fix this supposition calls
  for: the shim sets the data-size limit only
  (`RLIMIT_DATA`, the heap ceiling, which macOS enforces
  on a process's data mappings) and leaves the address
  space unlimited; the audit name
  `spawn_resource_limits` stands, and the live limits
  test is re-pinned to read back exactly that — the
  data limit at the ceiling, the address space
  unlimited — plus a live point the landed suite did
  not carry: a job that tries to allocate well past the
  ceiling is refused by it. If a head carrying that fix
  still aborts at -6, S1 is wrong and this record says
  so in advance.
- S2, the staged read and the work write (a latent
  failure behind S1). A macOS work directory lives
  under the temp tree, `/var/folders/...`, and `/var`
  is a firmlink whose canonical form is
  `/private/var`; Seatbelt path filters match the
  canonical path, so a `(subpath "/var/folders/...")`
  rule never matches the file it names. The profile
  writer already carries this knowledge for the system
  trees — `SYSTEM_READ_PATHS` names `/private/etc`
  beside `/etc` for exactly this reason — but the work
  directory and the extra read paths get no such twin,
  so even with S1 fixed the trial's staged read and
  the job's work-directory write would be refused.
  The fix this supposition calls for: the profile
  names the `/private` canonical twin of every
  `/var/...` and `/tmp/...` path it names, on both the
  read line and the write line, deduplicated against
  paths already named. This is deterministically
  testable off macOS — the generated profile text is
  the substrate — and the contract tests pin it.
- S3, the windows seam failures on the darwin host.
  `_confinement_spawn` derives its platform from two
  different signals: Windows from `os.name`, FreeBSD
  and darwin from `sys.platform`. On a Linux or
  Windows host the signals never disagree, but on a
  darwin host the windows tests' simulation (which
  patches `os.name` to `nt`, the signal that seam has
  always used) satisfies the darwin branch at the same
  time, the darwin branch is consulted first, and the
  scripted Windows backend — whose spawn takes no
  `user` argument, because the Windows branch never
  hands one over — is called by the macOS branch with
  `user=`, which is the recorded `TypeError`, and its
  fallback is recorded under the macOS name. The other
  confinement gates (`_confinement_argv`, the startup
  gate) derive every platform from `sys.platform`
  alone. The fix this supposition calls for: the spawn
  seam derives all three platforms from `sys.platform`
  alone (`win32`, `darwin`, `freebsd*`), the same
  single signal as the gates beside it, and the
  windows seam tests complete their simulation by
  patching `sys.platform` as the FreeBSD and macOS
  seam tests already do. On a real host nothing
  changes — a real Windows host answers `win32` to
  both signals — and the Windows and FreeBSD branches'
  behaviour is otherwise untouched.

What is not supposed: that the profile's file or
network posture caused the abort (the shim starts and
runs under the profile; the abort's signature is the
exec'd interpreter's startup), or that Seatbelt allowed
any escape (no escape point was ever exercised). The
fix keeps the fail-closed posture throughout: deny by
default, no network allow rule, writes only inside the
work directory, and a spawn that cannot apply its
controls still refuses the job.

## Conclusions for the fix, as they stand (2026-11-11)

The fix has landed, built to the three suppositions
above, in three parts that match them one for one. The
launcher shim now sets the data-size limit only and
never an address-space limit. The profile writer names
the `/private` canonical twin of every `/var` and
`/tmp` path it names, on the read line and the write
line alike, deduplicated, and the composed spawn argv
builds its profile from the work directory's real path,
so a work directory reached through any alias enters
the profile under the name Seatbelt matches. And the
spawn seam derives all three platforms — Windows,
FreeBSD, darwin — from `sys.platform` alone, the single
signal the confinement gates beside it already used;
the windows seam tests complete their simulation by
patching `sys.platform`, as the FreeBSD and macOS seam
tests already did. The figures were re-measured over
the fix's tree in the landing that followed it. What
each supposition now stands on, stated exactly:

- S1's mechanism is addressed as supposed, and its
  deterministic substrate is proven off darwin: the
  contract tests pin the shim's source to the data-size
  limit alone (no address-space or virtual-memory limit
  name stands in it), and the live limits test is
  re-pinned to read back exactly that — the data limit
  at the ceiling, the address space unlimited — beside a
  new live point the landed suite did not carry, a job
  that tries to allocate 700 MiB past the ceiling and is
  refused by it. Whether the abort is gone is not proven
  here: that is a live fact, and no `test-macos` job on
  a head carrying this fix has completed as this section
  stands. If that verdict still shows exit -6, S1 is
  wrong, exactly as its record said in advance.
- S2 is proven in the substrate it named. The generated
  profile text is deterministic off macOS, and the
  contract tests pin it: a `/var/folders` work directory
  and a `/tmp` work directory each name their
  `/private` twin on both lines, a `/var` read path
  names its twin once, a work directory already in
  canonical form gains no duplicate and no doubled
  `/private`, the `/private/etc` twin the system trees
  already carried is not doubled, and a symlinked work
  directory enters the profile under its real path. The
  live staged read those rules exist to allow is proven
  only by the same outstanding CI verdict.
- S3 is proven off darwin. The seam tests pin both
  directions of the single-signal rule: a `win32`
  platform routes to the Windows backend even when
  `os.name` still answers the host's `posix`, and on a
  darwin platform an `os.name` of `nt` routes nowhere
  but the macOS branch. The windows suite's simulations
  now patch `sys.platform` beside `os.name`, and the
  three confinement suites — macOS, Windows and FreeBSD
  — run green together on a Linux host (159 tests, the
  live macOS class among the skips, under its registered
  reasons), beside the neighbouring batteries (the
  skip registry, the reader-pages guard, the core and
  figure guards after their re-measure). The 4
  darwin-host windows failures' mechanism is removed by
  construction; their confirmation on a darwin host is
  the same outstanding CI verdict, not a claim made
  here.
- The support level does not move. It stands exactly
  as the support matrix states it — Supported, reduced
  confinement. The live proof remains open, and it
  closes only when a `test-macos` job on a head carrying
  this fix completes green; until then the live points
  stand as the failure verdict left them — the probe
  and the confined spawn refuted as originally landed
  and now addressed by a fix whose live word has not
  landed, the escape, network and limits points
  unproven — and no field proof on project hardware is
  claimed: there is no Mac in the project's own fleet.

## The second live verdict (2026-11-11)

The live word has since landed, and it is failure again.
Two `test-macos` jobs on heads carrying the fix above
have completed with failure verdicts (build runs
43101076872 and 43105044003; the newer on the tree this
section's suppositions were written on, its `test-macos`
job completing at 1:53 PM PST on 2026-11-11, on macOS
15.8.2, the arm64 image, under the hosted Python 3.12.10).
All 7 tests in the live class failed, in exactly the
shape of the first verdict: the confined spawn aborted
with exit -6 and produced no output on either stream —
the probe's trial could not read its staged file, the
escape, network and limits points again produced no
evidence either way, and the limits read-back came back
empty. The verdict was read first-hand from the job log
before anything below was supposed.

What that verdict settles about the first fix, stated
exactly: S1 is wrong as a diagnosis of the abort, as its
own record provided in advance ("if a head carrying that
fix still aborts at -6, S1 is wrong"). The data-size-only
shim changed the spawn's limits and the abort did not
move at all, so the address-space limit was not the
mechanism — or not the whole of it. S2's substrate proof
stands (the profile text names the canonical twins it
was built to name), and S3's seam proof stands; neither
was ever exercised live, because the confined process
still dies before any of them can be. One further fact
the log carries: the startup probe — `sandbox-exec`
starting `/usr/bin/true` under an allow-by-default
profile — passes on the same host, so the tool works and
a simply-confined native process starts; the abort lives
in what this backend's own spawn adds on top of that:
its deny-by-default profile, its launcher shim, or the
limit the shim sets. The suppositions below are built to
separate those three, and the fix that follows them
carries a live bisect that names the culprit in the next
verdict if the fix itself misses.

## Suppositions for the second fix, recorded before the fix

Recorded 2026-11-11, after the second verdict above and
before any second fix was written, from a first-hand read
of the failing job log, of `runner/guard/macos_confine.py`
as the first fix left it, and of two outside records of
deny-by-default Seatbelt profiles that do start processes
on current macOS (an independent project's published
allowlist, and a second project's fix for the identical
failure shape on a newer macOS, named below for exactly
what it is: corroboration by analogy, not proof for this
host).

- R2-S1, the root listing (the primary supposition).
  Every process that starts on macOS reads the listing
  of the root directory as it starts, and a process that
  is refused that read is aborted — stopped at start
  with SIGABRT, before it can print anything. That is
  the published shape of this exact failure in the
  second outside record: each process under a Seatbelt
  profile stopped at start with SIGABRT, `/usr/bin/true`
  included, because "the process reads the listing of
  the root directory, and the profile gave `/` only its
  metadata"; the fix there was one line, an allowance
  of `file-read-data` on the literal `/`, which "gives
  the names at the top of the disk" and "nothing below
  them". This backend's profile gives `/` less than
  that: its read line names subpath trees (`/System`,
  `/usr`, and the rest) and no rule names the root
  itself at all, so the root's listing is denied by the
  deny-by-default base. The supposed mechanism fits
  every fact on record: the abort is below the
  interpreter (no output on either stream, no traceback
  a Python-level refusal would print), it is identical
  across both rounds (neither round's profile named the
  root), and the allow-by-default probe passes because
  that profile denies nothing. The fix this supposition
  calls for: the profile carries exactly that one line
  — `(allow file-read-data (literal "/"))` — and no
  subpath grant on `/`, so nothing below the top of the
  disk is readable by it. If a head carrying that line
  still aborts at -6, R2-S1 is wrong and this record
  says so in advance.
- R2-S2, the system startup trees under `/private`.
  Working deny-by-default allowlists name, beside the
  familiar system trees, three `/private` trees this
  backend's profile does not: `/private/var/db/dyld`
  (the dynamic loader's own database, read as every
  process's libraries are bound), `/private/var/db/timezone`
  (the tree `/etc/localtime` points into, read as a
  process learns its timezone), and `/private/var/select`
  (the tool-selection links, which `/bin/sh` reads at
  every start). This backend's `SYSTEM_READ_PATHS` names
  `/private/etc` and nothing else under `/private` — the
  one twin the first backend happened to carry — so all
  three reads fall under the deny-by-default base. A
  refused loader or timezone read at startup is the same
  abort grade as R2-S1's: it lands in the loader or the
  system library, below the interpreter, with nothing
  printed. The fix this supposition calls for: the three
  trees join `SYSTEM_READ_PATHS`, read-only like the
  rest of that set, named once each. Which of R2-S1 and
  R2-S2 carries the abort — either, or both — the next
  live verdict cannot separate if the fix lands both at
  once, and that is accepted plainly: the live bisect
  below separates the profile from the shim, and the two
  profile grants are both minimal, named, system-only
  reads of the kind every working allowlist on record
  carries.
- R2-S3, the standing alternative: the data-size limit
  itself. The 512 MiB `RLIMIT_DATA` the shim sets was
  present in both failing rounds, so it cannot be
  cleared by the round-over-round comparison that
  cleared the address-space limit: if the second
  `exec`'s startup — the loader binding the job
  interpreter under a data ceiling already in force —
  is what aborts, the profile grants above change
  nothing. This round does not act on R2-S3 in the
  production spawn, for one stated reason: round two
  changed only the limits and the abort did not move,
  so the profile is the variable this round changes,
  one variable at a time. Instead the live suite gains
  the bisect that convicts or clears each suspect in a
  single verdict: a spawn under the generated profile
  alone (no shim, no limit), a spawn through the shim
  alone (no profile), and a native binary through the
  full confined chain. If the next verdict still shows
  -6 on the full chain, those three points' pattern
  names which of the profile, the shim's limit, or the
  chain itself is the cause, and this record says so in
  advance.

What is not supposed: that Seatbelt allowed any escape
(no escape point has ever been exercised — the process
dies before them), that the first fix's canonical twins
were wrong (their substrate stands proven, and the
staged file's canonical name was already in the profile
in both rounds), or that the outside records prove
anything about this host (they are the reason these
three mechanisms are supposed first; the CI macOS legs
remain the only field proof this platform has).

## Conclusions for the second fix, against R2-S1 to R2-S3

The second fix has since landed, built to the
suppositions above, and the core figures were
re-measured over its tree in the landing that followed
it. What each supposition now stands on, stated
exactly:

- R2-S1's grant is landed exactly as supposed, and its
  deterministic substrate is proven off darwin: the
  generated profile carries `(allow file-read-data
  (literal "/"))` exactly once and no `(subpath "/")`
  anywhere, pinned by a contract test beside the
  profile writer's other field tests. Whether the
  abort is gone is not proven here: that is a live
  fact, and no `test-macos` job on a head carrying
  this fix has completed as this section stands. If
  that verdict still shows exit -6, R2-S1 is wrong,
  exactly as its record said in advance.
- R2-S2's grant is landed exactly as supposed, and
  its substrate is proven the same way: the three
  trees — `/private/var/db/dyld`,
  `/private/var/db/timezone` and `/private/var/select`
  — stand in `SYSTEM_READ_PATHS` and in the generated
  profile, once each, read-only like the rest of that
  set, pinned by a contract test. Which of R2-S1 and
  R2-S2 carried the abort the next live verdict
  cannot separate, as the suppositions record said
  in advance; both grants are minimal, named,
  system-only reads.
- R2-S3 was not acted on in the production spawn, as
  supposed: the shim and its data-size limit are
  unchanged this round, one variable at a time. The
  live bisect it called for is landed as three live
  points beside the original seven — a native binary
  through the full confined chain, the generated
  profile alone with no shim and no limit, and the
  shim alone with no profile. If the next verdict
  still shows -6 on the full chain, those three
  points' pattern names which of the profile, the
  shim's limit, or the chain itself is the cause.
- The contract proof runs green off darwin: the macOS
  suite runs 78 tests on a Linux host, OK with the
  10 live Seatbelt tests skipped under their
  registered reason (the original 7 and the bisect's
  3), beside the neighbouring confinement suites and
  the figure guards after their re-measure.
- The support level does not move. It stands exactly
  as the support matrix states it — Supported,
  reduced confinement. The live proof remains open,
  and it closes only when a `test-macos` job on a
  head carrying this fix completes green; until then
  the live points stand as the second failure verdict
  left them — the confined spawn refuted twice over,
  the escape, network and limits points unproven —
  and no field proof on project hardware is claimed:
  there is no Mac in the project's own fleet.

## The third live verdict (2026-11-11)

The live word on the second fix has landed, and it is
failure in a new shape. Two `test-macos` jobs on heads
carrying the second fix have completed with failure
verdicts (build run 43118076619 on the figures head
that followed the fix, and build run 43121516173 on
the 3.16.20.5 release head; the newer job's log was
read first-hand before anything below was supposed,
on the macos-15 arm64 image, the hosted framework
Python 3.12). All 10 tests in the live class failed —
the original 7 and the bisect's 3. The shape changed:
no confined spawn aborts at -6 any more. A confined
interpreter now starts far enough to print its own
diagnostic and exit 1: `python: realpath:
/Library/Frameworks/Python.framework/Versions/3.12/bin/:
Operation not permitted`. The probe's failure carries
that line verbatim, the memory-ceiling point's stderr
is exactly that line instead of a `MemoryError`, the
full-chain spawns (the interpreter spawn and the
native binary alike) return 1, the escape and network
points again produce no output (`b''` — the process
dies before them), and the limits read-back is empty.

What that verdict settles about the second fix, stated
exactly. The -6 abort is gone, so R2-S1 and R2-S2 as a
pair were carrying it: the grants they added (the root
listing, the `/private` startup trees) let the loader
finish and the interpreter's own code run — the
process now lives long enough to report what refuses
it. They are incomplete, not wrong: a further startup
need is refused, and it is now visible by name. The
bisect did part of its job and exposed a gap in
itself: the profile alone fails (so the profile still
refuses a startup need), the native binary through
the full chain fails (but that leg launches through
the Python shim, so it shares the interpreter's death
and does not isolate a native start), and the shim
alone — no profile in force at all — also fails at
exit 1, so a second, independent defect sits in the
shim leg; its cause is not in the log, because the
round-2 bisect assertions checked only the return
code and captured no stderr. One correction to how
this verdict is described: the bisect legs are new in
round 2 and have no earlier CI verdict at all — the
failure count rose 7 to 10 because three new points
exist and fail, not because three passing points
regressed; the original 7 fail in a new shape.

## Suppositions for the third fix, recorded before the fix

Recorded 2026-11-11, after the third verdict above
and before any third fix was written, from a
first-hand read of the failing job log and of
`runner/guard/macos_confine.py` and the live suite as
the second fix left them.

- R3-S1, the realpath refusal (the primary
  supposition). At startup the interpreter resolves
  its own install location with `realpath()` — the
  framework interpreter on the CI host resolves
  `/Library/Frameworks/Python.framework/Versions/3.12/bin/`
  — and `realpath()` stats every component of the
  path in turn (the `lstat`/`readlink` family, which
  Seatbelt governs as `file-read-metadata`). The
  profile grants `file-read*` — metadata included —
  on its named subpath trees, so every component
  under `/Library` is covered; but the root itself
  carries only R2-S1's `file-read-data` line, which
  grants the listing and not the stat, so the stat
  of `/` is refused by the deny-by-default base,
  `realpath()` fails with `Operation not permitted`,
  and the interpreter's startup path resolution is
  fatal: it prints exactly the line the log carries
  and exits 1. The general form of the same defect
  reaches further than the root: component-wise stat
  touches every ancestor of an allowed path, and the
  ancestors above a granted prefix are nowhere
  granted — a venv interpreter's `/Users/<name>`
  ancestors, a work directory's `/private`,
  `/private/var` and temp-hash ancestors — so any
  startup (or job) `realpath()` of an allowed path
  can be refused at an ungranted ancestor. The fix
  this supposition calls for: the profile carries
  one `(allow file-read-metadata)` line — metadata
  (existence, type, size, times, symlink targets) on
  any path, and never contents: `file-read-data`
  stays confined to the named trees, so the escape
  points' contents assertions are untouched, and
  the root listing line stands as it is. If a head
  carrying that line still prints the realpath line,
  R3-S1 is wrong and this record says so in advance.
- R3-S2, why the three bisect legs fail. Each leg's
  failure is one of the two defects above wearing
  that leg's shape. The native-binary leg is not a
  native start: the full chain launches every command
  through the shim's interpreter, so the leg dies at
  the shim interpreter's own realpath refusal
  (R3-S1) before `/usr/bin/true` is ever exec'd. The
  profile-alone leg is R3-S1 in its pure form — the
  interpreter driven directly under the generated
  profile, no shim, no limit — and its failure is
  what convicts the profile rather than the chain.
  The shim-alone leg runs with no profile in force,
  so R3-S1 cannot explain it at all: it is the
  evidence for R3-S3. What the profile must allow
  for the interpreter to start while the escape,
  network and spawn-limit assertions still hold is
  therefore exactly: metadata everywhere (R3-S1),
  contents only in the named trees (unchanged), no
  network allow rule (unchanged), and the shim's
  pre-exec limit left standing (R3-S3).
- R3-S3, the shim alone. Two named alternatives, and
  this round's work is built to separate them rather
  than to guess. (a) The shim's own `setrlimit` call
  fails on this host — setting the data-size limit
  to (512 MiB, 512 MiB) asks to raise the hard limit
  above the inherited one, which an unprivileged
  process may not do, and macOS hosts commonly carry
  a small inherited hard data limit — so the shim
  dies by exception at exit 1 before its `exec`. (b)
  The limit, once set, is in force across the second
  `exec` and the framework interpreter's startup
  breaks under it (the loader's or allocator's
  accounting against the data ceiling). The
  production change this round is the same under
  both and weakens nothing: a shim that cannot set
  its limit already refuses the job — that is the
  fail-closed shape — but it must refuse by name, so
  the shim writes a named line to stderr
  (`hp-shim: could not set the data-size limit: ...`)
  and exits 1, instead of dying by a bare exception
  whose text no assertion captured. The live bisect
  then gains the separation: every bisect assertion
  carries the captured stderr in its message, and two
  legs join it — the profile driving a native binary
  directly, with no shim at all (a native start the
  round-2 bisect never isolated), and the shim
  driving a native binary, with no profile. Under
  (a) the shim-to-native leg fails carrying the
  shim's named line; under (b) it passes while the
  shim-to-interpreter leg fails without that line.
  The limit's value and kind do not change this
  round: if (a) is convicted, the ceiling's
  application — not its size — is the next round's
  subject, and the limits point's 512 MiB read-back
  expectation would have to be re-judged against the
  host's inherited hard limit in the open.

A standing risk is recorded, not acted on: the
memory-ceiling live point supposes the data-size
limit governs a 700 MiB `bytearray` allocation on
this platform. If the next verdict shows that point
failing with the allocation completing instead, the
ceiling mechanism — not the profile — is the next
round's subject. What is not supposed: that metadata
is contents (it is not — no byte of any file's data
becomes readable by the metadata line), or that
Seatbelt has allowed any escape (no escape point has
ever been exercised — the process still dies before
them).

## Conclusions for the third fix, against R3-S1 to R3-S3

The third fix has since landed, built to the
suppositions above. Because the fix grew
`runner/guard/macos_confine.py` — a file on the
canonical core list — the core figures stood to be
re-measured over its tree, as the second fix's
landing was. That re-measure has since been carried
on the current head in the 3.16.20.7 release landing
that followed the fix, whose core record states that
its measure also takes up the macOS confinement
growth of `runner/guard` that landed in parallel:
the file itself grew from 756 to 778 lines, the
`runner/guard` part from 5,283 to 5,305, the
as-assembled set stands at 64,050 lines, 57,933 of
them non-blank, zipped to 809,693 bytes, and the
canonical set at 63,168 lines over 136 files, the
runner proper at 7,178 — and the figure check passes
against those facts on that head. No separate
re-measure is owed for this fix beyond that landing.
What each supposition now stands on, stated exactly:

- R3-S1's grant is landed exactly as supposed, and
  its deterministic substrate is proven off darwin:
  the generated profile carries
  `(allow file-read-metadata)` exactly once, metadata
  on any path and never contents, and
  `file-read-data` still stands only on the root's
  literal line, pinned by a contract test beside the
  profile writer's other field tests. Whether the
  realpath refusal is gone is not proven here: that
  is a live fact, and no `test-macos` job on a head
  carrying this fix has completed as this section
  stands. If that verdict still prints the realpath
  line, R3-S1 is wrong, exactly as its record said
  in advance.
- R3-S2's reading is carried into the widened bisect
  exactly as supposed. The round-2 native leg shared
  the shim interpreter's death; the live suite now
  also drives a native binary directly under the
  profile, with no shim anywhere, and drives a
  native binary through the shim, with no profile —
  so a native start is isolated for the first time,
  and the profile-alone and shim-alone interpreter
  legs stand beside them in their pure forms.
- R3-S3's production change is landed exactly as
  supposed, and neither of its two alternatives is
  guessed at: the shim still refuses a job whose
  limit it cannot set — that fail-closed shape
  stands, and the limit's value and kind are
  unchanged — but it now refuses by name, writing
  `hp-shim: could not set the data-size limit: ...`
  to stderr and exiting 1, instead of dying by a
  bare exception no assertion captured. The named
  refusal is pinned in the shim's source and
  executed off darwin against a ceiling too large
  for the platform's limit type, exiting 1 with the
  marker on stderr and never running the job. Every
  bisect assertion now carries the captured stderr,
  and the two new legs join the bisect (12 live
  points in all: the original 7, the round-2
  bisect's 3, and this round's 2), whose pattern in
  the next verdict separates the alternatives:
  under (a) the shim-to-native leg fails carrying
  the shim's named line; under (b) it passes while
  the shim-to-interpreter leg fails without that
  line.
- The contract proof runs green off darwin: the
  macOS suite runs 83 tests on a Linux host, OK with
  the 12 live Seatbelt tests skipped under their
  registered reason, beside the neighbouring
  confinement suites (the three together run 169
  tests, OK with 18 skipped), the figure guards
  after their re-measure, and the skip registry —
  which first flagged, and now registers, the
  Windows skip the release landing added to this
  suite's argv field tests.
- The support level does not move. It stands exactly
  as the support matrix states it — Supported,
  reduced confinement. The live proof remains open,
  and it closes only when a `test-macos` job on a
  head carrying this fix completes green; until then
  the live points stand as the third failure verdict
  left them — every live point failing at exit 1
  with the realpath line, the escape, network and
  limits points unproven because the process dies
  before them — and no field proof on project
  hardware is claimed: there is no Mac in the
  project's own fleet.
