# FreeBSD hardening notes

The runner installs on FreeBSD from the same tree as everywhere
else (`install.py` writes a cron `@reboot` entry for the node).
This page is about the one mechanism FreeBSD needed a backend
for: confinement.

## Confinement on FreeBSD

There is no bwrap on FreeBSD, and the FreeBSD confinement
backend is a jail, not a namespace sandbox. Each job runs
inside a jail made for it, and every audit and startup record
names the controls that job's jail carried. The floor every
confined job has is:

```
freebsd: jail + no_network + spawn_resource_limits
```

A record that says more names a control that was applied to
that job. On a host with RACCT enabled, a job with no job user
reads:

```
freebsd: jail + no_network + no_superuser + rctl_resource_limits + spawn_resource_limits
```

The design of record is
`docs/steady/design/freebsd-confinement-design.md`; this page
is what an operator needs from it.

### What a job gets

- **A root that takes no write.** The jail's root is a
  read-only view of a per-job skeleton that holds mount points
  and three small files. Below it, read-only: the host's
  `/usr`, `/usr/local`, `/bin`, `/lib`, `/libexec` and `/sbin`.
  `/dev` is devfs under ruleset 4, the handful of device nodes
  a job needs. Two trees take a write: the job's work
  directory, mounted at `/work`, and a fresh `/tmp`.
- **No network at all**, loopback included: the jail is
  created with `ip4=disable` and `ip6=disable`.
- **A process table of its own.** The host's processes do not
  exist inside the jail, and removing the jail ends every
  process the job left.
- **Root with no privilege** (`no_superuser`). A job with no
  job user is uid 0 inside its jail, and the jail is created
  with `allow.nosuser`: that uid cannot raise a resource
  limit, change a file's owner, or do anything else the
  super-user's privilege grants. It is still root's uid when
  a file's owner is asked for, which is why a job user is
  worth naming (below).
- **No set-user-ID.** Every mount is `nosuid`, so a
  set-user-ID bit on any file a job can reach buys nothing.
- **A per-process memory ceiling** (`spawn_resource_limits`):
  the job's command runs under `limits(1)` with the
  virtual-memory and data-size limits both at 512 MiB. The job
  cannot raise them.
- **A bounded `/tmp`**: 512 MiB. `/tmp` is memory, and a
  scratch tree with no size is a way around every other
  ceiling.
- **Ceilings on the job as a whole**
  (`rctl_resource_limits`), on a host with RACCT enabled: at
  most 256 processes in the jail, and at most 2 GiB of address
  space across all of them together, held by rctl rules.

The jail exists before the job's first process starts (the job
is started inside it with `jexec(8)`), so the job never runs a
line unconfined.

### RACCT

The jail-wide ceilings are rctl rules, and rctl can deny
nothing unless the kernel's resource accounting is on. It is a
boot tunable, off as FreeBSD ships:

```
# /boot/loader.conf
kern.racct.enable=1
```

After a reboot with that line, `rctl_resource_limits` appears
in the record and the two rules are written for every job. On
a host without it the rules are not written and the record
does not name them — the one place a default follows the host.
A ceiling you write yourself does not follow the host:
`job_processes` or `job_memory_bytes` in the config on a host
without RACCT refuses the start and names the tunable.

### Settings

All optional, under `security.confinement`:

```json
"confinement": {
  "extra_ro_binds": [["/opt/data", "/data"]],
  "work_mount": "/work",
  "freebsd": {
    "loopback": false,
    "process_memory_bytes": 536870912,
    "tmp_bytes": 536870912,
    "job_memory_bytes": 2147483648,
    "job_processes": 256
  }
}
```

- `extra_ro_binds` mounts a host directory read-only inside
  the jail, and `work_mount` moves the work directory's mount
  point: the same two keys the Linux sandbox reads. A work
  mount is a directory of its own at the jail root; a bind may
  not land on the root, `/tmp`, `/dev` or the work mount.
- `extra_flags` are bwrap arguments. The jail takes none of
  them: a FreeBSD runner at `enforce` whose config carries any
  refuses to start and names them.
- `freebsd.loopback: true` gives the job a loopback of its
  own, the shape the Linux sandbox has: the jail gets a
  network stack of its own whose only interface is its own
  `lo0`, up at 127.0.0.1. The job can talk to itself and to
  nothing else — the host's 127.0.0.1 is another stack. The
  record names `private_loopback` in place of `no_network`.
  It needs a kernel with VIMAGE, which GENERIC carries.
- The four numbers are the ceilings above. A setting the
  backend does not know is a config error, on every platform.

### The interpreter

An interpreter under the mounted trees runs as it is. One that
lives elsewhere — a pyenv, a venv, `/opt` — gets its own
install prefix mounted read-only at the same path, and the
mount is written into the audit record: the Linux sandbox's
rule, with its floor (never a home directory, never a tree
shallower than two components). An interpreter under `/tmp`,
`/dev` or the work mount is refused: the jail has its own tree
there.

### The job user

When `job_user` is also at `enforce` with a user named, that
user is handed to the spawn and applied at the jail door
(`jexec -u`, resolved in the host's user database): the
POSIX `setuid` demote cannot ride a spawn that replaces the
process creation, so the demote happens at the door instead,
the same shape as the Windows backend's creation-time token.
The job is that user from its first instruction, the `nosuid`
mounts keep it from coming back as root, and the record does
not name `no_superuser` for it — the job_user record names
the demote. On its own (confinement at `audit` or `off`),
`job_user` on FreeBSD is the ordinary POSIX demote, which
engages as it does on Linux.

Name one. The jail cannot be made without root, so a job
with no job user is root's uid inside it — without
privilege, and still the owner of what root owns (below,
under what this does not provide). A fresh install names no
job user.

### Startup, and after a job

At `enforce` the startup gate probes the backend and refuses
to start when the probe fails, naming why. The probe builds
one: a throwaway skeleton and its mounts, a throwaway jail
with a job's parameters, and a trial process inside it that
writes its work mount and `/tmp`, tries to write the jail
root, tries an act that needs privilege, and looks at `/dev`.
A trial that lands a write on the root, keeps a privilege, or
sees the host's devices is a refusal by name; so is a config
that asks for a control the host cannot hold. A job whose own
jail cannot be built is refused at job time the same way.
There is no path on which a job runs unconfined under
`enforce`.

`--posture` on a FreeBSD host prints the same answer without
building anything: the controls a job's jail would carry
there, the RACCT tunable when the jail-wide ceilings are not
engaged, and a warning for anything the startup gate would
refuse on.

When a job ends the backend removes its rctl rules, its jail,
its mounts and its skeleton. Three things stand behind that:

- The skeleton is never removed through a mount. If a mount
  will not let go, the skeleton stays where it is and the
  job's files behind the mount are not touched.
- If the runner itself dies, a watcher that sits beside each
  job removes the job's jail, which ends the job.
- The next runner to start removes what a dead runner left:
  jails, rules, mounts and skeletons whose names carry the
  process id of a runner that is gone.

### What this does not provide

- **Not Capsicum.** Capability mode is entered in-process by
  the confined program itself; the runner starts arbitrary job
  interpreters that know nothing of it, so it does not fit the
  launcher shape. The jail is the boundary instead.
- **Not without root.** Making a jail and mounting into it
  need root: the runner must run as root for the backend to
  engage. The Linux sandbox confines without it.
- **No ownership boundary without a job user.** A job with
  no job user is uid 0 inside its jail. It holds no
  privilege, and it is still the owner of everything root
  owns: a root-only file in a tree the jail shows it is read.
  The tree that matters is `/usr/local/etc`, where packages
  keep their settings and sometimes a secret. On Linux the
  job is the runner's ordinary user and reads what that user
  reads. Set `security.job_user` to a user of the job's own
  and the job reads only what that user can.
- **Home directories inside `/usr`.** A host that keeps them
  in the `/usr` filesystem — `/usr/home` on UFS, the layout
  before FreeBSD 14.0 — shows them to a job, read-only, with
  the rest of `/usr`. Where `/usr/home` is a dataset of its
  own, or homes stand under `/home`, they are not in the
  jail.
- **The per-process ceiling is not a kernel rule.** It is a
  resource limit applied at spawn, and it holds because the
  job has no privilege to raise it. The kernel rules are the
  rctl ones, on a host with RACCT enabled.
- **Memory outside a process.** A shared-memory object a job
  creates and never maps is bounded by neither ceiling. The
  `/tmp` bound closes the largest such door.
- **Disk.** The work directory is on the host's disk and is
  not bounded here. Keep jobs' outputs inside it.
- **No CPU ceiling.**

### What stands behind this page

The backend's logic is tested on every platform against a
host that exists only as its own record. The kernel is tested
where it is real: the `freebsd-confinement` workflow boots
FreeBSD 14.5 and 15.0 guests with RACCT enabled, and 14.5 as
FreeBSD ships, and runs the backend's test module as root in
each — the boundary read from inside a job, the rules, the
loopback, the binds, a runner killed outright, and jobs
through the runner itself. Its first run of this shape
(2026-11-14, run 43578228704) passed whole on 14.5 and 15.0
and left nothing on either guest, and the run that added the
guest without RACCT (run 43578832525) passed on all three.
The record of what was supposed beforehand and what the runs
answered is in the design page.

The project's own FreeBSD node (14.5-RELEASE, RACCT off) ran
the same live classes on 2026-11-14, in a test root with the
production install untouched: 27 of 29 passed, and the two
that need RACCT skipped by name. Its 17-step battery, below,
was of the first backend and has not been run against this
shape.

The mode a fresh install states is tested the same two ways:
with a scripted probe on every platform, and with the real
one on the three hosted guests — the seed asked as root, as
an ordinary user, for a config that asks more than the host
holds, by the installer's own file, and through the wizard,
and a runner started on the seeded config confining its
first job. Their first run (2026-11-14, run 43585328369)
passed on all three and left nothing on any of them. The
node has not run them.

## The mode a FreeBSD config states

A fresh FreeBSD install asks the machine before it writes
`security.modes.confinement`. The installer — and the setup
wizard, when it seeds a config for a runner started with
none — asks the jail backend the startup gate's own question,
with the config it is about to leave on disk: a throwaway
jail is built, the boundary is read from inside it, and all
of it is removed.

- **Where the probe passes, the mode stays at `enforce`.**
  Nothing is written for it. The installer says so, and
  prints what a job's jail carries on that host:

  ```
  platform: security.modes.confinement left at enforce in /root/.homing-pigeon/config.json (the FreeBSD jail backend's probe, asked on this machine as this user, passed; the startup gate asks it again at every start)
  platform: FreeBSD jail backend: freebsd: jail + no_network + no_superuser + spawn_resource_limits
  platform: RACCT is not enabled on this host, so the jail-wide rctl ceilings are not written (kern.racct.enable=1 in /boot/loader.conf and a reboot engage them)
  ```

  From the first start every job runs inside a jail, and the
  startup gate asks the probe again at every start.
- **Where it does not pass, the mode is stated at `audit`**
  in the file, and the line that says so carries the reason
  in the backend's own words. At `audit`, jobs run unconfined
  and the audit log records what the mode would have done.
  Answer the reason, set the mode to `enforce`, and the
  startup gate verifies it at the next start.

The probe asks as whoever runs the installer, and the service
the installer writes — a cron `@reboot` entry — belongs to
that same user, so the runner starts as the identity the
probe ran as. The common reason is therefore the first one:
an install run by an ordinary user states `audit` and says
that creating a jail needs root. Run the installer as root to
have the jail on from the first start.

Three more rules:

- A config that comes in with the install is probed as
  written. Ask for a loopback on a kernel without VIMAGE, or
  for a jail-wide ceiling on a host without RACCT, and that
  is the reason printed.
- A mode the config already states at `audit` or `off` stays
  there, and the machine is not asked. That holds for a later
  run of the installer too: an install that stands at
  `audit` — every FreeBSD install made before 2026-11-14 —
  stays there until its operator sets `enforce`.
- A later run of the installer over a config at `enforce`
  asks again. The mode stays where the probe passes, and is
  stated at `audit`, with the reason, where it no longer
  does.

`job_user` is not stated down: the POSIX demote engages on
FreeBSD as it does on Linux.

## The first backend's field test

What follows is the record of the first backend (2026-11-10):
a jail whose root was the per-job skeleton itself, with the
controls of the floor and nothing else. The shape above
replaced it on 2026-11-14.

### Supposition, recorded before the field test

Recorded 2026-11-10, before the backend's first field test on
the fleet FreeBSD node (FreeBSD 14.5-RELEASE), mirroring the
record the Windows backend carried into its own field test:

Before this backend, confinement at `enforce` on FreeBSD
refused at startup ("confinement (bwrap) is Linux-only; this
machine is freebsd14") and the platform seed stated the mode
at `audit` because there was no backend behind it. The
supposition is that, with the backend landed, on the node:

- the startup probe returns None and the runner starts with
  every security mode at `enforce`;
- each exec job's audit record names exactly "freebsd: jail +
  no_network + spawn_resource_limits";
- an escape write to a host path outside the work mount does
  not land — the path does not exist inside the jail root;
- an escape read of a host file does not return its contents,
  for the same reason (this is stronger than the Windows
  backend, which has no namespace isolation);
- a job that tries to commit 700 MiB is refused by the
  512 MiB spawn limit;
- the rest of the 17-step rig battery (startup, build stamp,
  clock, compute, file write and read inside the workspace,
  attested ping, tampered and wrong-audience refusals, result
  verification, production install untouched) behaves as it
  did in the baseline run at the seeded posture.

### Conclusions from the field test

The field test ran on the fleet node (FreeBSD 14.5-RELEASE)
on 2026-11-10: the full 17-step rig battery at every
security mode `enforce`, superseding the baseline run at
the seeded posture for the confinement steps. Every step
passed, 17 of 17:

- the startup probe engaged and the runner started with
  every security mode at `enforce`;
- each exec job's audit record named exactly "freebsd: jail
  + no_network + spawn_resource_limits";
- the escape write did not land and the escape read did not
  return the host file's contents — the jail root holds
  neither path, which is stronger than the Windows backend's
  outcome, as supposed;
- the 700 MiB job was refused by the 512 MiB spawn limit
  (its interpreter's allocation failed; a live unit test
  asserts the MemoryError, so the refusal is the ceiling's
  and not a job that never started);
- the production install stood untouched throughout —
  config, runner and crontab hashes identical before and
  after, and no process ran under the installed config.

The supposition's shape held. The field test also found 3
defects the local tests had not, each fixed and landed
before the passing run:

- a nullfs mount cycle: `/usr/local` sits on the same
  filesystem as `/usr` on the node, and mounting both was
  refused ("Resource deadlock avoided"). A mount whose
  source lives on the same filesystem as an ancestor
  already mounted is now skipped — the child tree is
  visible through the ancestor's mount; a child that is
  its own filesystem still mounts for real.
- the demoted spawn: `jexec -U` resolves the user in the
  jail's user database, which the skeleton cannot serve;
  the spawn now uses `-u`, resolved in the host's user
  database — the account the job_user seam named. The
  jail root is also traversable by the job user (a
  root-run spawn had masked its 0700 default), and the
  spawn passes the job's working directory (`-d /work`),
  the in-jail form of the host spawn's cwd.
- the loader hints: the dynamic loader's hints live in
  `/var/run` on FreeBSD, and the skeleton had no `/var`;
  binaries linked against `/usr/local` libraries (the
  pkg-installed python3 is the standing case) failed to
  load inside the jail while `/bin` tools ran. The
  skeleton carries a copy of the hints file, nothing
  else of `/var`.

The backend's live unit tests ran on the node itself
(probe, argv translation, in-jail spawn, demote, local
binary, memory ceiling): 6 of 6. As that test stood, the
backend had no rctl rule, no per-job process-count limit
and no loopback; the shape above has all three, and the node
has since run its live classes, not this battery.
