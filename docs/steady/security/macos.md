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
virtual-memory and data-size resource limits to 512 MiB per
process with `setrlimit` and then `exec`s the job's command,
the macOS shape of the FreeBSD backend's `limits(1)` step,
which macOS has no equivalent of. `sandbox-exec` wraps the
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
