# Windows hardening notes

The runner installs on Windows as a Scheduled Task
(`install.py --run-as USER` controls the account). The default is
SYSTEM: it needs no password and just works. This page is for when
you want less privilege than that.

## Running as a dedicated limited account

Create a local user for the runner (no admin rights, password that
doesn't expire), then install with:

```
python runner/ops/install.py --run-as .\pigeon-runner
```

Named (non-SYSTEM) accounts get run level `LIMITED` instead of
`HIGHEST`: least privilege is the point. Well-known service accounts
and gMSA names (ending in `$`) need no password; any other account
makes `schtasks` prompt for its password interactively at install
time.

The account needs:

- **Read/write** on the install directory (the runner, its config,
  and the base dir with the mailbox state, seen cache, and audit
  log all live here by default).
- **Read** on anything jobs are expected to read; **write** only
  where jobs are expected to write. Jobs run as this user, so the
  account is the identity boundary on Windows. There is no
  bwrap/namespace equivalent; the confinement backend described
  below adds its own controls on top of the account when
  `confinement` is at `enforce`.
- **Log on as a batch job** (`SeBatchLogonRight`) if the task fails
  to start; `schtasks` usually grants this when creating the task.

What the limited account loses: binding privileged ports, writing
outside its directories, and (obviously) the `--run-as` equivalent
of `job_user` privilege drops. The M8 `job_user` demote itself is
a POSIX `setuid` mechanism; on Windows the mode instead carries
the Job Object ceiling described below, a resource limit rather
than an account drop, so this account stays the identity boundary.

## File permissions: icacls, not chmod

`os.chmod` cannot set Unix permission bits on Windows. The
`config.json` 0600 story from POSIX ("owner read/write only") is
implemented through the parent directory's ACLs instead: the file
inherits whatever the directory grants.

To lock down `config.json` (which holds the shared secret) for a
dedicated account:

```
icacls config.json /inheritance:r
icacls config.json /grant:r "pigeon-runner:(R,W)" "SYSTEM:(R,W)" "Administrators:(R,W)"
```

`/inheritance:r` removes inherited grants; the second line grants
read/write to exactly the runner account, SYSTEM, and Administrators.
Verify with `icacls config.json`, as no other principal should
appear.

The runner's `--posture` check reports the Windows ACL state
best-effort (it cannot prove a negative the way mode bits can, so an
unreadable ACL is a WARN, never a FAIL).

## Confinement on Windows

There is no bwrap on Windows, and the Windows confinement backend
is not a namespace sandbox. What its floor applies, at
`enforce`, is named exactly in every audit and startup record
for a floor spawn:

```
windows: job_object + restricted_token + low_integrity
```

A job process is created suspended under a restricted token
derived from the runner's own token (every privilege except
SeChangeNotify stripped, the Administrators group disabled) with
the token's mandatory integrity level set to Low, and it is
assigned to a Job Object carrying a per-process memory ceiling
(512 MiB) before it resumes, so the job never runs a line
unconfined. The job's workspace directory is labelled Low
integrity so the job can write its own outputs there. The M2
key-policy constraints (`allowed_env`, `allowed_files`,
`args_pattern`, `max_args`) are platform-independent and apply
as well.

What the floor does not provide, plainly: no filesystem
namespace isolation. A job at the floor can still read any
path its token can read; low integrity stops it writing to
medium- or higher-integrity objects outside its workspace, it
does not hide the filesystem, and it isolates no network. At
`enforce` the startup gate probes the backend (Job Object
creation plus restricted-token creation plus the
integrity-level set) and refuses to start when the probe
fails, naming why.

On top of that floor, an AppContainer control stands since
2026-11-21, where its trial proves on the host. The spawn
derives the container SID from a fixed container name, builds
its security capabilities with no capability SIDs at all (a
container with no network capability has no network), grants
that SID the job's work directory, the ancestors of that
directory at read and execute only, and the read paths a
caller names, points the job's temporary folders at its work
directory, and assigns the Job Object before the process
resumes. A failed AppContainer start revokes the grants it
made. Where that shape engages, the audit and startup record
names a different string, exactly:

```
windows: job_object + appcontainer + no_network
```

The trial asks for the job's own shape before the verdict is
given, because the record on the project's own Windows rig
shows shapes that die at load inside the container
(PowerShell cannot start there, and managed programs die at
load there). A shape the trial cannot prove falls back to
the floor spawn and the floor record, unchanged. The
AppContainer spawn replaces the restricted token control for
the processes it covers; an AppContainer token runs at Low
integrity by construction, so neither control is named twice.

## The two modes a Windows config states

Two security modes name mechanisms whose full form is POSIX:
`security.modes.confinement` (whose sandbox form is the Linux
bwrap backend; FreeBSD's form is its jail backend) and
`security.modes.job_user` (the demote is a POSIX `setuid`). Both
read `enforce` when a config does not state them.

Their Windows stories differ. Confinement has the backend
described above: at `enforce`, startup probes it and each job
runs under the three named controls, or under the
AppContainer shape where its trial proves on that host and
for that job's shape, or is refused. `job_user`
has the narrower one: a Job Object with a per-process memory
ceiling (512 MiB), assigned to each job's process as it starts.
At `enforce`, Windows `job_user` runs with that ceiling, and a
job whose process cannot be assigned is refused rather than run
uncontained. The ceiling is a resource limit, not the demote:
jobs still run as the runner's account under that mode, and no
token drop or integrity-level change stands behind `job_user`
itself, as those controls belong to `confinement`.

A fresh Windows install writes both modes into `config.json` at
`audit`, stated in the file. The reason is the same for both:
the installer and the setup wizard write the seed without
running the backend probe on that machine, and stating `enforce`
sight-unseen risks a first-start refusal on a machine where a
control cannot engage. The operator steps a mode up to `enforce`
deliberately, and the startup gate then verifies the probe on
that machine. A config the first-run setup wizard seeds states
the same two lines the same way, and the wizard says so as it
writes the file. At `audit`, jobs run under the account boundary
above, and the audit log records what the modes would have done.

## Service hardening

The Scheduled Task itself supports no equivalent of the systemd
directives in `docs/steady/security/` (no `NoNewPrivileges`,
`ProtectSystem`, or `PrivateTmp`). The account boundary is the
mechanism; keep the task's "run with highest privileges" box
unchecked (the installer already uses `LIMITED` for named accounts).

## The level's name: a supposition, recorded before measurement (2026-11-21)

The owner has directed that the Windows rows of
`docs/support-matrix.md` be given the treatment the macOS
row was given the same evening: earn the full claim in
code where code is what it rests on, and then let the
name follow the posture. The matrix today names both
Windows rows **Supported, reduced confinement**. What
that name rests on, read from the matrix, from this page
and from the backend (`runner/guard/windows_confine.py`),
is five things:

1. The AppContainer control engages only where its trial
   proves on the host, the trial now including the job's
   own shape; where it does not prove, jobs run at the
   floor, whose reads are not walled and which isolates
   no network.
2. The Job Object's ceilings: the matrix states the per
   process memory ceiling and nothing wider.
3. The verdict the runner acts on: whether the
   AppContainer verdict the gate computes is the verdict
   the spawn seam acts on, in every start shape.
4. `job_user` on Windows is the memory ceiling alone,
   with no account demote behind it.
5. Windows ARM64 carries no field proof; its row follows
   the x86-64 row on a build leg's evidence.

Suppositions, stated so the measurement can prove them
wrong:

- S1. The whole job ceiling is already set in code:
  `_create_job_with_limits` sets
  `JOB_OBJECT_LIMIT_JOB_MEMORY` beside the per process
  flag, with the job memory limit equal to the same
  512 MiB, so a job as a whole is capped, not only each
  process in it. What is missing is the pin: no unit
  test names that flag or that assignment today. The
  measurement is a source reading plus a new pin test,
  and the rig battery's ceiling step beside it.
- S2. No processor ceiling is set: no job time limit, no
  per process time limit, no CPU rate control and no
  process count limit stands in the limit flags. No
  other backend at **Supported** sets a processor time
  ceiling either: the Linux sandbox sets none, the macOS
  launcher sets an address space limit and no time
  limit, and the FreeBSD jail's core limit is a set of
  cores, stated on its own row as not a share of time.
  A processor time ceiling on Windows would need a
  value no config names and would be new policy, not a
  repair. Supposition: it is not closable in this lane,
  and it stays stated in the confinement cell, as the
  macOS row states its own.
- S3. The verdict wiring is already whole: the gate, the
  posture record and the spawn seam consult the one
  cached verdict (the trial and the job shape probe
  together) on the one module instance the loader
  registers under both import names, and a spawn reached
  before any gate call computes the verdict instead of
  reading an empty cache as a floor verdict. The Lane 8
  landing claims exactly this; the measurement is a
  source reading against its tests.
- S4. The floor fallback is by design and stays: a
  missing mechanism falls back to the floor with the
  floor's own record, and a boundary crossing refuses
  outright. What the matrix cell does not state plainly
  today is the floor's network position: the floor
  isolates no network. Accuracy, not code, is what that
  part needs.
- S5. On the head this lane lands, the rig battery's
  confinement steps pass with the audit lines naming
  "windows: job_object + appcontainer + no_network".
  The battery's three timing steps (startup, build
  stamp and clock) have failed before only under rig
  saturation; if they fail on a saturated rig, that is
  recorded as a timing failure under load, never as a
  confinement failure, and the run is repeated on a
  quiet rig before any verdict is drawn from them.

The conclusions go in this same place when the
measurement lands, and the change the numbers support
follows them.

### Conclusions (2026-11-21)

Measured against the suppositions above:

- S1 stands, with one correction to the supposition's
  own wording. The whole job ceiling is set in code:
  `_create_job_with_limits` composes the limit flags
  from the per process memory flag, the job memory flag
  and kill on job close, and sets both limits from the
  caller's byte count (512 MiB by default), through
  `SetInformationJobObject` at the extended limit
  information class. The correction: the JobMemoryLimit
  assignment was already pinned, by the v4 bars record
  in `runner/tests/test_v4_the_bars.py`; what no test
  named was the flag that makes the assignment take
  effect. A source pin family in
  `runner/tests/test_windows_confine.py`
  (JobObjectLimitsSourceTest) now pins the flags, both
  assignments, the extended class call, and that every
  spawn shape (the containment applier, the AppContainer
  spawn, the floor spawn and the job_user spawn) builds
  its job through the one helper.
- S2 stands. No processor ceiling is set: the limits
  body names no job time, per process time, CPU rate or
  process count flag, and the new pin holds that absence
  in the body. The parity reading also stands: the Linux
  sandbox sets no processor ceiling, the macOS launcher
  sets an address space limit only, and the FreeBSD
  jail's core limit is a set of cores. The confinement
  cell of the Windows row states the position plainly.
- S3 stands. The gate, the posture record and the spawn
  seam consult the one cached verdict, the AppContainer
  half of it being the trial and the job shape probe
  together; a spawn reached before any gate call
  computes the verdict rather than reading an empty
  cache as a floor verdict; and the loader registers the
  one module instance under both import names. The Lane
  8 test families pin each leg.
- S4 stands. The floor fallback is by design, and the
  matrix cell now states the floor's network position
  plainly: the floor isolates no network.
- S5 stands in its confinement half, and its timing half
  is recorded as it was measured. On the head this lane
  landed, the rig battery ran twice. In both runs every
  confinement step passed: the gate's refusal shape, the
  workspace write and read, the escape write blocked,
  the escape read refused (outsideReadSucceeded=False,
  the AppContainer shape engaged, not the floor), the
  memory ceiling's refusal, and the audit record naming
  exactly "windows: job_object + appcontainer +
  no_network", with the production install untouched.
  In both runs the timing steps failed under measured
  rig saturation (CPU at 88 to 93 percent with 12 to 14
  python processes from parallel lanes, and a second
  battery running for the same head inside the first
  run's window): startup and build stamp read an empty
  log window while the runner stood alive and its stamp
  stood in the log the report itself prints, and the
  clock job did not arrive inside its window. Those are
  timing failures under load, not confinement failures,
  and no clean 17 of 17 is claimed for this head; a re
  run of the battery on a quiet rig remains the
  outstanding check for those three steps.

### The owner's call on the level's name (2026-11-21)

On 2026-11-21 the owner directed that the Windows rows
of `docs/support-matrix.md` be given the treatment the
macOS row was given the same evening, and that the
AppContainer backend's design record
(`docs/steady/design/windows-appcontainer-design.md`) be
landed with it, reconciled against the build. The rows
now stand at **Supported**. The reasoning is the macOS
reasoning: the name follows the posture. The AppContainer
control has enforced at `enforce` since it landed on
2026-11-21; where its trial cannot prove on a host, the
floor stands with its own record, and a boundary
crossing refuses outright at the gate. What the name
does not do is widen any claim: the rows keep their
shape limits stated in their own cells (the floor
fallback, and at the floor the open reads and the open
network; no processor ceiling in either shape;
`job_user` as the memory ceiling alone; the ARM64 row
resting on its build leg), and the reduced level's
definition in the matrix now records all three
departures, FreeBSD's, macOS's and Windows', each dated.
This note supersedes any sentence in this page or in the
matrix that named the Windows level otherwise; the
earlier text stands as the record of its day.
