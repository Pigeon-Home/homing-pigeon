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
  account *is* the sandbox boundary on Windows — there is no
  bwrap/namespace equivalent.
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

There is no bwrap on Windows, so the M6 `confinement` feature has no
backend here. The equivalent containment is the limited account
above plus the M2 key-policy constraints (`allowed_env`,
`allowed_files`, `args_pattern`, `max_args`), which are
platform-independent. `--posture` reports confinement as
not-applicable on Windows rather than warning about it. The Job
Object ceiling described under `job_user` below is not a
confinement backend: it limits one job process's memory and
isolates neither files nor network.

## The two modes a Windows config states

Two security modes name mechanisms whose full form is POSIX:
`security.modes.confinement` (the bwrap sandbox is Linux-only) and
`security.modes.job_user` (the demote is a POSIX `setuid`). Both
read `enforce` when a config does not state them.

Their Windows stories differ. Confinement has no backend here at
all, so at `enforce` startup refuses, because a mode whose
mechanism cannot engage would otherwise promise what it cannot
do. `job_user` has one: a Job Object with a per-process memory
ceiling (512 MiB), assigned to each job's process as it starts.
At `enforce`, Windows `job_user` runs with that ceiling, and a
job whose process cannot be assigned is refused rather than run
uncontained. The ceiling is a resource limit, not the demote:
jobs still run as the runner's account, and no token drop or
integrity-level change stands behind the mode.

A fresh Windows install writes both modes into `config.json` at
`audit`, stated in the file: for confinement because its
mechanism cannot engage here, and for `job_user` because the Job
Object backend is a first, deliberately narrow step — stating
`enforce` by hand is how an operator chooses it. A config the
first-run setup wizard seeds states the same two lines the same
way, and the wizard says so as it writes the file. At `audit`,
jobs run under the account boundary above, and the audit log
records what the modes would have done. A hand-written config
should state the same two lines; leaving confinement unstated
leaves the first start at its refusal, with the refusal naming
the mode.

## Service hardening

The Scheduled Task itself supports no equivalent of the systemd
directives in `docs/steady/security/` (no `NoNewPrivileges`,
`ProtectSystem`, or `PrivateTmp`). The account boundary is the
mechanism; keep the task's "run with highest privileges" box
unchecked (the installer already uses `LIMITED` for named accounts).
