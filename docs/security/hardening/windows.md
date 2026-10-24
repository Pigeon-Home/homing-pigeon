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
of `job_user` privilege drops — the M8 `job_user` feature is a
POSIX `setuid` mechanism and does not apply on Windows.

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
not-applicable on Windows rather than warning about it.

## Service hardening

The Scheduled Task itself supports no equivalent of the systemd
directives in `docs/security/hardening/systemd/` (no `NoNewPrivileges`,
`ProtectSystem`, or `PrivateTmp`). The account boundary is the
mechanism; keep the task's "run with highest privileges" box
unchecked (the installer already uses `LIMITED` for named accounts).
