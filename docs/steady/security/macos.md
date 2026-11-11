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
