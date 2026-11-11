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
  account is the identity boundary on Windows — there is no
  bwrap/namespace equivalent; the confinement backend described
  below adds its own controls on top of the account when
  `confinement` is at `enforce`.
- **Log on as a batch job** (`SeBatchLogonRight`) if the task fails
  to start; `schtasks` usually grants this when creating the task.

What the limited account loses: binding privileged ports, writing
outside its directories, and (obviously) the `--run-as` equivalent
of `job_user` privilege drops — the M8 `job_user` demote itself is
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
Verify with `icacls config.json` — no other principal should appear.

The runner's `--posture` check reports the Windows ACL state
best-effort (it cannot prove a negative the way mode bits can, so an
unreadable ACL is a WARN, never a FAIL).

## Confinement on Windows

There is no bwrap on Windows, and the Windows confinement backend
is not a namespace sandbox. What it applies, at `enforce`, is
named exactly in every audit and startup record:

```
windows: job_object + restricted_token + low_integrity
```

A job process is created suspended under a restricted token
derived from the runner's own token — every privilege except
SeChangeNotify stripped, the Administrators group disabled —
with the token's mandatory integrity level set to Low, and it is
assigned to a Job Object carrying a per-process memory ceiling
(512 MiB) before it resumes, so the job never runs a line
unconfined. The job's workspace directory is labelled Low
integrity so the job can write its own outputs there. The M2
key-policy constraints (`allowed_env`, `allowed_files`,
`args_pattern`, `max_args`) are platform-independent and apply
as well.

What this does not provide, plainly: no filesystem namespace
isolation. A confined job can still read any path its token can
read; low integrity stops it writing to medium- or
higher-integrity objects outside its workspace, it does not
hide the filesystem, and it isolates no network. At `enforce`
the startup gate probes the backend — Job Object creation plus
restricted-token creation plus the integrity-level set — and
refuses to start when the probe fails, naming why. An
AppContainer backend is the future path to confinement parity
with the Linux sandbox; it is not built yet.

## The two modes a Windows config states

Two security modes name mechanisms whose full form is POSIX:
`security.modes.confinement` (whose sandbox form is the Linux
bwrap backend; FreeBSD's form is its jail backend) and
`security.modes.job_user` (the demote is a POSIX `setuid`). Both
read `enforce` when a config does not state them.

Their Windows stories differ. Confinement has the backend
described above: at `enforce`, startup probes it and each job
runs under the three named controls, or is refused. `job_user`
has the narrower one: a Job Object with a per-process memory
ceiling (512 MiB), assigned to each job's process as it starts.
At `enforce`, Windows `job_user` runs with that ceiling, and a
job whose process cannot be assigned is refused rather than run
uncontained. The ceiling is a resource limit, not the demote:
jobs still run as the runner's account under that mode, and no
token drop or integrity-level change stands behind `job_user`
itself — those controls belong to `confinement`.

A fresh Windows install writes both modes into `config.json` at
`audit`, stated in the file. The reason is the same for both:
the installer and the setup wizard write the seed without
running the backend probe on that machine, and stating
`enforce` sight-unseen risks a first-start refusal on a machine
where a control cannot engage — the operator steps a mode up to
`enforce` deliberately, and the startup gate then verifies the
probe on that machine. A config the first-run setup wizard seeds
states the same two lines the same way, and the wizard says so
as it writes the file. At `audit`, jobs run under the account
boundary above, and the audit log records what the modes would
have done.

## Service hardening

The Scheduled Task itself supports no equivalent of the systemd
directives in `docs/steady/security/` (no `NoNewPrivileges`,
`ProtectSystem`, or `PrivateTmp`). The account boundary is the
mechanism; keep the task's "run with highest privileges" box
unchecked (the installer already uses `LIMITED` for named accounts).
