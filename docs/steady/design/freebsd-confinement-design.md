# FreeBSD confinement: the jail, specified

Status: design of record, written 2026-11-14 at the owner's
direction, and built the same day
(`runner/guard/freebsd_confine.py`; tests in
`runner/tests/test_freebsd_confine.py`; the hosted live proof
is the `freebsd-confinement` workflow). The build is a
transcription of this text. Where the kernel answered
differently from what this text supposed, the difference is
written in "Suppositions and conclusions" at the end, in the
open.

The mode a fresh install states — the installer asking this
backend's probe before it writes the seed — was added to this
page on 2026-11-14, at the owner's direction, and built the
same day (`runner/ops/install.py`, `runner/ops/setup.py`).
The job user that seed names where it leaves the jail on was
added and built the same day, at the owner's direction, and
so was the account the installer makes for it. The cores a
job's jail is pinned to were added and built on 2026-11-15,
at the owner's direction.

Confinement is the software suite's own, platform by
platform. The protocol documents do not specify it — a
submitter must not assume a sandbox on the far side — so
nothing here changes a message, a field or a document under
`docs/ietf`. This page and
`docs/steady/security/freebsd.md` are where the FreeBSD
shape is written down; `docs/support-matrix.md` carries the
claim.

## Where the first backend stood

The first FreeBSD backend (2026-11-10) put each job in a
jail whose root was a per-job directory, with the host's
system trees mounted read-only, the work directory mounted
writable, a tmpfs at `/tmp`, no network, and a 512 MiB
per-process resource limit applied at spawn. That is a real
boundary, and its field test on the project's own node
passed.

On 2026-11-14 a set of boundary tests was written that reads
the boundary from inside a job, and run against that backend
on hosted FreeBSD 14.5 and 15.0, as root (the
`freebsd-confinement` workflow, run 43574966807). Two of nine
held — the host's processes did not exist inside the jail,
and there was no network. Seven did not, the same seven on
both releases:

| What the job did | What happened |
|---|---|
| Asked for an unlimited address space, then for 700 MiB | Both granted. Root inside a jail holds the privilege to raise a resource limit, so the ceiling was the job's to lift |
| Wrote `/`, `/etc`, `/var/run`; made a directory at the root | All landed. The skeleton was the jail's root, and root owned it |
| Ran a root-owned set-user-ID program from its work directory, as the job user | The program ran as root. The work mount honoured the bit |
| Changed a file's owner | Changed. The job was root with root's privilege, inside the jail |
| Wrote 640 MiB into `/tmp` | All of it landed. The tmpfs had no size, and `/tmp` is memory |
| Finished | The jail's `/dev` stayed mounted and its skeleton stayed on disk, one of each per job |
| Left a process behind and finished | The same mount and skeleton stayed (the job's own files were intact) |

None of this let a job out of its jail. Three of the seven
are ways around a ceiling the record named.

## What the design is for

Two goals, in this order.

1. **Nothing the Linux sandbox gives is missing.** A
   read-only view of the system, one writable work mount, a
   private scratch tree, no network, the operator's read-only
   binds, a work mount the operator can move, the install
   prefix of an interpreter that lives outside the system
   trees, a startup probe that refuses when the mechanism
   cannot engage, and a job that does not outlive its runner.
2. **Where a jail can hold more than a namespace sandbox
   does, it holds it.** A process table of its own, a root
   that takes no write at all, root with no privilege,
   ceilings the job cannot lift, ceilings on the job as a
   whole held by the kernel, a scratch tree that is bounded,
   and a release that ends every process the job left.

The record names what was applied. A control that could not
engage on a host is not named on that host, and a control the
operator asked for by name refuses the start when it cannot
engage.

## The controls

Each job's audit record carries a status string: `freebsd: `
and the names of the controls that job's jail carried, joined
by ` + `, always in the order of this table. The floor is the
first, second and last rows:
`freebsd: jail + no_network + spawn_resource_limits`.

| Name | What it is | When it is named |
|---|---|---|
| `jail` | The job runs in a jail made for it: a read-only root, the mounts below, a process table of its own | Always |
| `no_network` | The jail is created with `ip4=disable` and `ip6=disable`: no network at all, loopback included | Unless the config asks for a loopback |
| `private_loopback` | The jail has a network stack of its own (vnet) whose only interface is its own `lo0`, up at 127.0.0.1 | When `security.confinement.freebsd.loopback` is true |
| `no_superuser` | The jail is created with `allow.nosuser`: uid 0 inside it holds no privilege | When no job user is handed to the spawn |
| `rctl_resource_limits` | rctl rules hold the jail as a whole: a ceiling on its processes and on the address space of all of them together | On a host with RACCT enabled |
| `cpuset_cpu_limit` | The jail is pinned to a set of cores with `cpuset(1)`: every process of the job runs on those cores and on no others | Where a core is held back from the job: a runner with more than one core, unless the config lets a job have them all |
| `spawn_resource_limits` | The job's command runs under `limits(1)` with the virtual-memory and data-size limits at the per-process ceiling | Always |

## The jail's shape

A skeleton is made for each job, in a directory private to
the runner:

```
<base>/          0700, named for the runner's process id
  skel/          the tree the jail sees as its root
  root/          an empty directory: the mount point
```

`skel` holds mount points, copies of the host's `passwd` and
`group` files, and the dynamic loader's hints file. Nothing
is ever mounted inside `skel`. The mounts, in order:

1. `skel` on `root`, **read-only**. This is the jail's root.
   Every path that is not one of the two writable mounts
   below is on a read-only filesystem, whoever the job runs
   as.
2. The host's `/usr`, `/usr/local`, `/bin`, `/lib`,
   `/libexec` and `/sbin`, read-only, each at its own path. A
   tree that lives on its parent's filesystem is already
   there through the parent's mount and is not mounted twice.
3. The operator's `extra_ro_binds`, read-only.
4. The install prefix of the job's interpreter, read-only, at
   its own path, when the interpreter lives outside all of
   the above (below).
5. A tmpfs at `/tmp`, with a size.
6. devfs at `/dev` under ruleset 4, the jail ruleset. The
   backend mounts it itself so that it can unmount it itself.
7. The job's work directory at the work mount, writable.

Every mount but `/dev` is `nosuid`. Two trees take a write
from inside: the work mount and `/tmp`.

The jail is then created on `root` with a name that carries
the runner's process id, `persist`, `enforce_statfs=1`, and
either the network parameters of `no_network` or `vnet=new`.
The job is started inside it with `jexec`, from the work
mount, under `limits(1)`. The jail exists before the job's
first process does.

### The interpreter

The rule is the Linux sandbox's, by the same function
(`sandbox.interpreter_binds`): an interpreter under a mounted
tree or an operator bind needs nothing; one that lives
elsewhere — a pyenv, a venv, `/opt` — gets its install prefix
mounted read-only at the same path, and the mount is written
into the audit record's detail. The floor is the same too:
never a user's home directory, never a tree shallower than
two components. An interpreter no mount can show, or one
under `/tmp`, `/dev` or the work mount (where the jail puts a
tree of its own), refuses the job: the file would not exist
inside.

## Privilege

A job with no job user is uid 0 inside its jail, and the jail
is created with `allow.nosuser`. The number is all the job
keeps. It cannot raise a resource limit, change a file's
owner, change an interface, or do anything else the
super-user's privilege grants; ordinary ownership still
applies, so it reads and writes its own work directory as
before.

Ordinary ownership cuts the other way too. The job is still
the owner of everything root owns, so a root-only file in a
tree the jail shows it is read. On FreeBSD the tree that
matters is `/usr/local/etc`, where packages keep their
settings and sometimes a secret. This is the one thing the
Linux sandbox holds by default that this jail does not: a
Linux job is the runner's ordinary user and reads what that
user reads. A job user closes it, and a fresh install whose
jail goes on names one (below, under the mode a fresh install
states).

A job with a job user (`security.modes.job_user` at `enforce`
with a user named) is demoted at the jail door: `jexec -u`,
resolved in the host's user database. The demote needs the
privilege, so that jail keeps it, and the job is the named
user from its first instruction. `no_superuser` is not named
for such a job; the job_user record is. The `nosuid` mounts
are what keep that user from coming back as root.

## Ceilings

| Ceiling | Default | Held by | Setting |
|---|---|---|---|
| Address space and data size, per process | 512 MiB | `limits(1)` at spawn; the job cannot raise it | `process_memory_bytes` |
| `/tmp` | 512 MiB | The tmpfs's size | `tmp_bytes` |
| Processes in the jail | 256 | rctl `maxproc`, where RACCT is enabled | `job_processes` |
| Address space of every process in the jail together | 2 GiB | rctl `vmemoryuse`, where RACCT is enabled | `job_memory_bytes` |
| Processes of the job user, across the host | 256 | `limits(1)` at the jail door, under a job user; the job cannot raise it | `job_user_processes` |
| Cores the job runs on | All but one of the runner's | `cpuset(1)` on the jail, before the job's first process; the job cannot widen it | `job_cpus` |

RACCT is a boot tunable (`kern.racct.enable=1` in
`/boot/loader.conf`), off as FreeBSD ships. Where it is off
an rctl rule can deny nothing, so the two jail-wide rules are
not written and `rctl_resource_limits` is not named. That is
a default adapting to the host. A setting the operator wrote
does not adapt: `job_processes` or `job_memory_bytes` in the
config on a host without RACCT refuses the start and says
which tunable to set.

The per-process ceiling is a resource limit, not a kernel
rule. It holds because the job has no privilege to raise it.

### The job user's processes

A job that goes in as a job user has one ceiling more, and it
asks nothing of the host. The kernel counts the processes
each user holds, on every FreeBSD, and refuses the fork that
would take a user past the limit the forking process carries.
So the job's command runs under `limits(1)` with that limit
set too (`-u`), after the door, as the job user: 256 unless
the config says otherwise. A limit set there is one the job
cannot raise, because raising it takes privilege and the job
user has none. RACCT has no part in it. The ceiling holds on
a host as FreeBSD ships, with no tunable and no reboot.

The count is the account's, not one job's. Every process the
account holds on the host counts toward it: every job of the
runner running at that moment, in whichever jail, and
anything else that runs as that account. That is the second
reason the installer's account is the jobs' alone. A ceiling
on `nobody` is shared with whatever else `nobody` runs; a
ceiling on `pigeon-jobs` is the jobs' to the last process. A
runner with several workers shares the one ceiling among the
jobs it runs at once, and `job_user_processes` raises it.

An ended process is still counted until its parent collects
it. A job's first process is the runner's own child, so the
release collects it, once the jail is gone, if nothing has
by then: a job that is released holds none of its account's
processes.

A job with no job user gets no such ceiling. It is uid 0, and
uid 0's count is the host's own root processes: a limit there
would be the host's as much as the job's. For that job the
jail's own rule is the only ceiling on processes, where RACCT
is enabled.

The setting follows the rule for a ceiling the operator
wrote. `job_user_processes` in a config that engages no job
user refuses the start, and so does a number above the most
the kernel lets any one user hold on that host
(`kern.maxprocperuid`): the door could not set it. The
default adapts instead. On a host whose own limit is below
256 the ceiling is that limit.

The record's names do not change. The ceiling is one of the
spawn's resource limits (`spawn_resource_limits`), and the
job's audit record carries the number in its detail: `job
user pigeon-jobs held to 256 processes`.

### The job's cores

A job's jail is pinned to a set of cores, and that asks
nothing of the host either. Every jail has a cpuset of its
own, the root of every set a process inside it can hold, and
the kernel schedules a jail's processes on its cores and on
no others, on every FreeBSD. So as soon as a job's jail
stands, before anything runs in it, `cpuset(1)` sets the
jail's cores (`cpuset -l <cores> -j <jail id>`). RACCT has no
part in it: the limit holds on a host as FreeBSD ships, with
no tunable and no reboot.

The set is cut from the cores the runner itself may run on:
all but one of them unless the config says otherwise
(`job_cpus`), and always the highest-numbered ones. The
lowest-numbered core is never a job's. A job that spins on
every core it has, or starts a process for each and spins
them all, uses the cores of its set and leaves that one to
the runner, which is what must notice the job's timeout and
end it, and to the host. On a runner with four cores a job
runs on cores 1, 2 and 3.

The job cannot change the set. A process inside a jail may
narrow the cores it runs on and widen them again as far as
its jail's cpuset, and the kernel refuses a process inside a
jail any change to that jail's own cpuset, whatever the
process's uid. So the limit holds for a job with no job user
as it does for one that has gone through the door.

It is a set of cores, not a share of time. Within its set a
job may run every core flat out for as long as its timeout
lets it. Every job of the runner is pinned to the same set,
so jobs that run at once share those cores; `job_cpus` does
not give each job cores of its own.

`job_cpus` is the most cores a job may run on. A number at or
above the cores the runner has asks for nothing the host does
not already hold, since a job cannot run on more cores than
there are: nothing is pinned and the record names no limit.
That is also how an operator lets jobs have every core. The
default adapts the same way. A runner with one core to run on
has none to hold back, and where the host will not say which
cores the runner has, none is held back and the posture
report says so. A number the operator wrote on a host that
will not say refuses the start. A set that is planned and
cannot be pinned refuses too — the job, or the start when it
is the probe's jail — and the refusal names the setting that
starts a job with no core held back.

The record names the limit where it was applied:
`cpuset_cpu_limit`, after the jail's rctl rules and before
the spawn's limits. The job's audit record carries the cores
in its detail: `job pinned to cpus 1,2,3: 3 of the runner's 4
cores`.

## Network

None by default, loopback included: the jail has no IPv4 and
no IPv6. This is the strongest shape and the smallest surface.

The Linux sandbox gives a job a loopback of its own (bwrap
brings `lo` up in the new network namespace), so a job that
talks to itself over 127.0.0.1 runs there. The FreeBSD
equivalent is a switch: `security.confinement.freebsd.loopback`
creates the jail with a network stack of its own, brings its
`lo0` up at 127.0.0.1 from inside while the jail still holds
the privilege to do it, and then takes the privilege away
before any job process exists. The stack has no other
interface and no route. It is a switch and not the default
because a whole network stack is more kernel for a job to
reach than no sockets at all.

## Configuration

Under `security.confinement`, all optional:

```json
"confinement": {
  "extra_ro_binds": [["/opt/data", "/data"]],
  "work_mount": "/work",
  "freebsd": {
    "loopback": false,
    "process_memory_bytes": 536870912,
    "tmp_bytes": 536870912,
    "job_memory_bytes": 2147483648,
    "job_processes": 256,
    "job_user_processes": 256,
    "job_cpus": 3
  }
}
```

- `extra_ro_binds` and `work_mount` are the keys the Linux
  sandbox reads, honoured here with the same meaning. A work
  mount must be a directory of its own at the jail root; a
  bind may not land on the root, `/tmp`, `/dev` or the work
  mount.
- `extra_flags` are bwrap arguments. This backend can apply
  none of them, and a FreeBSD runner at `enforce` whose config
  carries any refuses to start and names them.
- The `freebsd` block is checked on every platform, so a
  config is right or wrong the same way wherever it is read.
  A setting the backend does not know is an error, not a
  setting ignored.

## The probe

At `enforce` the startup gate asks the backend whether it can
engage, and refuses the start with the backend's own words
when it cannot. The backend answers by building one: a
throwaway skeleton and its mounts, a throwaway jail with a
job's parameters and rules, and a trial process inside it
under the spawn limits. The trial writes its work mount and
its `/tmp`, tries to write the jail root, tries an act that
needs privilege, and looks at `/dev`. A trial that cannot
write the two trees, that lands a write on the root, that
keeps a privilege, or that sees the host's devices (the jail
ruleset not loaded) is a refusal by name. Where the config
asks for a loopback the address is read back; where RACCT is
enabled the rules are. Where a core is held back the trial's
jail is pinned as a job's would be, and the trial reads the
cores it may run on from inside: a set other than the one its
jail was pinned to is a refusal by name. A ceiling on the job
user's processes is asked for the job user the config
engages: the probe's own jail is the one a job with no job
user gets, and a config that names the ceiling and engages no
job user is refused before anything is built.

A passing verdict is kept for the life of the runner process,
for the settings it was run with, so the per-job gate does not
build a throwaway jail beside every job's own. The cheap
checks — root, the base tools, the host trees — run every
time. A particular job's spawn still builds its own jail, and
its failure refuses that job.

## The mode a fresh install states

On Linux a fresh install leaves `security.modes.confinement`
at `enforce`, and the startup gate decides at every start. On
FreeBSD the seed stated the mode at `audit` without asking the
machine: the seed was written blind, and `enforce` written
blind risks a first start that refuses. The seed now asks.

When the installer seeds a fresh config on a FreeBSD host —
and when the setup wizard seeds one for a runner started with
no config — it asks the backend the startup gate's own
question, with the config it is about to leave on disk: the
probe above, a throwaway jail built and the boundary read from
inside it.

- The probe passes: the mode stays at `enforce`. Nothing is
  written for it, as on Linux. The installer says so and
  prints what a job's jail carries on that host. From the
  first start every job runs inside a jail, and the startup
  gate asks again at every start.
- The probe does not pass: the mode is stated at `audit` in
  the file, and the reason is printed in the backend's own
  words. The operator answers the reason and sets the mode to
  `enforce`, and the startup gate then verifies it.

Four rules bound it:

- It asks as whoever runs the installer. The service the
  installer writes is a cron `@reboot` entry in that same
  user's crontab, so the runner starts as the identity the
  probe ran as. Run as root, the probe can pass. Run as an
  ordinary user it cannot — the backend needs root — and the
  seed states `audit` and says that.
- It asks about the config as written. A config that came in
  with the install and asks for a loopback, a bind or a
  ceiling is probed with them, and a setting the host cannot
  hold is the reason printed.
- It moves only a mode that stands at `enforce`. A mode the
  config states at `audit` or `off` is the operator's: it
  stays, and the machine is not asked. On FreeBSD the
  installer takes one path for a first install and for a
  later run over the same config, so the rule holds for both:
  an install that stands at `audit` stays there until its
  operator sets `enforce`, and a config at `enforce` is asked
  again — it stays where the probe passes, and is stated at
  `audit`, with the reason, where it no longer does.
- It is asked only of the machine the seed is written on. A
  caller that names FreeBSD from another host gets the stated
  seed, `audit`, and nothing is built.

What a passing probe leaves open is what Linux leaves open: a
machine that changes between the install and a later start.
The startup gate answers that in both places — it refuses the
start and names why.

### The job user a fresh install names

A jail that goes on with no job user leaves one thing open:
the job is root's uid, and reads what root owns in the trees
it is shown (Privilege, above). So a seed that leaves the
jail on names a job user as well, and the installer makes the
account it names.

**The account.** `pigeon-jobs`, made with `pw useradd` when
the machine has no account of that name: no password, no
login shell (`/usr/sbin/nologin`), no home directory
(`/nonexistent`), and a group of its own. Nothing else runs
as it, so nothing else on the machine owns a job's files or
can reach them as their owner. That is the reason it is not
`nobody`, an account any number of things may share. An
account of that name already on the machine is used as it
stands and is not changed.

**The trial.** Where the probe passed, the config's
`job_user` mode stands at `enforce`, and the config names no
job user, the seed finds or makes the account and then asks
the machine a second question. It runs a throwaway job as
that account inside a jail built as a job's is built under
the config, with one tree more shown in it: a directory
holding a file only root may read. The job must report the
account's uid, write its work mount, be refused the file, and
read the ceiling on its account's processes as the config
sets it, with no way to raise it — the four things a named
job user is for.

- The trial passes: `security.job_user` is written into the
  config, naming the account. From the first start every job
  goes in at the jail door as that account and reads what it
  can read. The installer says so, and the lines it prints
  for a job's jail are the ones for the config as it now
  stands.
- The account cannot be made, or its trial does not pass:
  `nobody` stands in. The same trial is run as `nobody`, and
  where that passes `nobody` is named. The lines say what
  became of the account and why, and an account the seed
  made and could not use is removed again.
- No trial passes: no user is named. The reason is printed,
  and the line says what a job with no job user reads.

**Who makes it.** Only the installer changes the machine.
The setup wizard writes a config and nothing else, so its
seed makes no account: it names `pigeon-jobs` where the
account already stands and `nobody` where it does not, and
says the installer makes the account. Removing the runner
leaves the account in place, as removing a package leaves the
users it made; `pw userdel pigeon-jobs` removes it.

A config that already names a job user keeps it and is not
asked about, and neither is one whose `job_user` mode the
operator has stated at `audit` or `off`.

The rest is the mode's rule. The question is put only to the
machine being seeded, only where the first question was put
and passed, and — on a later run of the installer — only
where no user is named yet. An ordinary user's install names
none and makes no account: with no jail there is no door, and
the demote needs root as the jail does.

### Where the machine is not asked

The seed's questions change the machine they are put to. The
probe builds a jail and removes it, the trial runs a job in
one, and the installer's account stays. That is an install
changing the machine it installs on, and not every run of the
installer or the wizard is one: the test suite drives both on
whatever host it happens to run on, with the steps that
install a service replaced and the seed left as it is. On a
FreeBSD host, as root, with a backend that engages, such a
run is to the seed an install like any other.

So the questions have a switch, and it is in the environment:
`HP_SEED_ASKS_MACHINE`. With `0`, `no`, `off` or `false`
there, the seed asks the machine nothing. It states the
platform's map — `audit` — as it does for a platform it was
only told about, names no job user, makes no account, and
the line that states the mode says the machine was not asked.
Any other word, or none, leaves the questions on: an
operator's install carries no word and is asked.

The environment is the place because it reaches everything
such a run starts. A test process holds more than one copy of
the installer — its test modules load it by package name, by
its own directory and by its file — and some tests start it
as a program. One word in the environment is read by all of
them; a switch on a module would be read by one.

The suite sets the word for itself, in its package, and
leaves a word the environment already carries. The tests of
the questions themselves switch them on by name. A door a
caller hands in — a scripted probe, trial or account — is
asked whatever the word: the switch closes the doors to the
machine, not the tests' own.

An operator may use the word the same way, for an install
that should build nothing and add no user. The config then
stands at `audit` until its operator sets `enforce` and names
a job user, and the startup gate verifies both.

## The release, and what stands behind it

The process object owns the teardown: the jail's rctl rules,
the jail (which ends every process still inside it), the
mounts in reverse order, and the skeleton.

**A skeleton is never removed through a mount.** The release
unmounts — a mount that is busy because the jail is still
letting go of a process is tried again before it is forced —
then reads the mount table, and removes the tree only when
nothing is mounted at or below it. The removal itself stops at
any entry on another filesystem. A skeleton that cannot be
removed whole stays where it is.

**A reaper.** Each job has a watcher: one line of `sh` on the
read end of a pipe whose write end only the runner holds. The
release writes it a word and it exits. If the runner is gone
instead, by any cause, the pipe closes and the watcher removes
the jail, which ends the job. The Linux sandbox's
`--die-with-parent` ends the sandbox's first process; removing
a jail ends all of them.

**A sweep.** A jail and a skeleton carry the process id of the
runner that made them. The first probe of a runner process
removes what a runner that is gone left behind: jails, their
rules, the mounts below their skeletons, the skeletons. A
skeleton from the first backend, whose name carries no
process id, is removed when no jail stands on it. A live
runner's jobs are never touched.

## Beside the Linux sandbox

| | Linux (bwrap) | FreeBSD (this design) |
|---|---|---|
| Needs | An unprivileged user namespace | Root, to make a jail and mount |
| System trees | `/usr` read-only | `/usr`, `/usr/local`, `/bin`, `/lib`, `/libexec`, `/sbin` read-only |
| The root itself | A tmpfs of bwrap's own, which takes writes for the life of the job | Read-only |
| `/tmp` | A tmpfs at the kernel's default size, half the host's memory | A tmpfs at the configured size |
| Home directories | Not visible | Not visible, unless the host keeps them inside the `/usr` filesystem |
| Network | A namespace with a loopback of its own | None; a loopback of its own by a switch |
| Host's processes | Visible through `/proc` (the process namespace is shared) | Not visible |
| Root inside | uid 0 in a user namespace, its capabilities dropped | uid 0 with no privilege, or the job user |
| What a job reads in the trees it is shown | What the runner's own user can read | Under a job user, what that user can read; with none, what root owns as well |
| Set-user-ID programs | Not honoured (no new privileges) | Not honoured (`nosuid` mounts) |
| Memory ceiling, per process | None | 512 MiB, not the job's to raise |
| Ceilings on the whole job | None | The job user's processes, on every host; each jail's processes and address space, where RACCT is enabled |
| Cores a job runs on | Every core the runner may run on | All but one of them, the lowest never a job's, on a runner with more than one; not the job's to widen |
| Operator binds, work mount | Yes | Yes, the same keys |
| Interpreter outside the trees | Its prefix, read-only, recorded | The same rule, the same record |
| Runner gone | The sandbox's command is killed | The jail is removed: every process ends |
| Startup probe | Starts the sandbox once | Builds a jail and reads the boundary from inside |
| A fresh install | `enforce`; the startup gate decides | `enforce` where the installer's probe passes, with an account of the jobs' own made and named as the job user; `audit`, stated with the reason, where it does not |

The Linux column is bwrap as this project starts it
(`DEFAULT_FLAGS` in `runner/guard/sandbox.py`) and
bubblewrap's documented behaviour. The FreeBSD column is what
the live tests read from inside a job. Linux keeps one thing
this design cannot have: it confines without root. The row
on what a job reads follows from it — the runner here is
root, so a job with no job user is root's uid too.

## What it does not do

- It is not Capsicum. Capability mode is entered by a program
  that knows it is being confined; a launcher for arbitrary
  interpreters cannot enter it for them.
- It is not unprivileged. The runner must run as root for the
  backend to engage.
- Without a job user there is no ownership boundary. The job
  holds no privilege and is still the owner of what root
  owns: it reads a root-only file in any tree the jail shows
  it (above, under Privilege). A job user is the remedy. A
  fresh install whose jail goes on makes an account for the
  jobs and names it; a config seeded before that, or one
  whose trials did not pass, names none until its operator
  does.
- Home directories inside `/usr`. A host that keeps them in
  the `/usr` filesystem — `/usr/home` on UFS, the layout
  before FreeBSD 14.0 — shows them read-only with the rest of
  `/usr`. Where `/usr/home` is a dataset of its own, or homes
  stand under `/home`, they are not in the jail.
- The floor that keeps a home directory out of an
  interpreter's mount knows a home by its shape: `/root`, the
  runner's own home, and any directory whose path ends in
  `home/<name>` or `Users/<name>`, reached through a link or
  not. A home kept under another name altogether is not known
  to it, and an interpreter in its `bin` brings that home in,
  read-only.
- The per-process ceiling is not a kernel rule (above).
- A job with no job user has no ceiling on its processes
  where RACCT is not enabled. The job user's ceiling is the
  account's, not one job's: jobs of the account that run at
  once share it. It counts processes, not the threads inside
  one.
- Memory a job holds outside any process's address space — a
  shared-memory object it never maps — is bounded by neither
  ceiling. The `/tmp` bound closes the largest such door.
- The work directory is on the host's disk and is not bounded
  here.
- The limit on cores is a set, not a share of time: within its
  cores a job may run flat out until its timeout. Jobs that
  run at once are pinned to the same set and share it. A
  runner with one core to run on holds none back, and neither
  does one whose host will not say which cores it has.
- The device ruleset is the host's: the backend asks for the
  jail ruleset and the probe refuses a host that has not
  loaded it, but it does not define one.

## Proof

- The backend's logic runs on every platform: everything below
  its public names is written against a host object — the
  commands it runs and the few facts it reads — and the suite
  hands it one that keeps a mount table, a set of jails and a
  list of rules. Build order, the record's names, every
  failure's cleanup, the release's rule about mounts, the
  sweep's rule about live runners and the probe's refusals are
  pinned there.
- The kernel is tested where it is real: the
  `freebsd-confinement` workflow boots three guests — FreeBSD
  14.5 and 15.0 with RACCT enabled, and 14.5 as FreeBSD ships,
  RACCT off — and runs the same module as root in each, the
  live classes included: the boundary read from inside a job,
  the jail-wide rules, the job user's process ceiling with
  RACCT and without, the cores a job reads as its own, cannot
  widen and uses when it spins on all of them, the loopback,
  the binds, the interpreter's prefix, a runner killed
  outright, jobs through the runner itself, with and without
  a job user, and the mode a fresh install states on that
  guest. Weekly and on dispatch.
- The posture report (`--posture`) names, on a FreeBSD host,
  the controls a job's jail would carry there and what would
  refuse the start, without building a jail.
- The project's own node (FreeBSD 14.5-RELEASE, RACCT off) ran
  the module's live classes on 2026-11-14, independently of
  the build, in a test root with the production install
  untouched: every live test passed but the two that need
  RACCT, which skip by name there. The node's 17-step battery
  of 2026-11-10 was of the first backend and has not been run
  against this shape.

## Suppositions and conclusions

Suppositions, recorded 2026-11-14 before the first hosted run
of this shape:

1. A jail takes a read-only nullfs view of the skeleton as its
   root, with the other mounts made below it.
2. `allow.nosuser` is accepted on 14.5 and 15.0, `jexec`
   without a user needs no privilege after it attaches, and a
   job under it cannot raise the limits `limits(1)` set.
3. A `nosuid` work mount stops a set-user-ID program from
   changing the job user's identity.
4. A tmpfs `size` option bounds `/tmp` at the number given.
5. An rctl `maxproc` rule on a jail refuses a fork past the
   number, and a `vmemoryuse` rule refuses an allocation that
   takes the jail's processes together past it while each is
   under its own limit.
6. The rules of a jail can be removed by its name after the
   jail is gone.
7. A vnet jail's `lo0` can be brought up from inside before
   the privilege is taken away, a job inside reaches its own
   listener over it, and the host's 127.0.0.1 is not reachable
   from it.
8. A runner killed outright loses its job: the watcher removes
   the jail, and the next sweep removes the mounts and the
   skeleton.
9. After a job, nothing of it is left on the host: no mount,
   no directory, no jail, no rule.

Conclusions, from the first hosted run of this shape
(2026-11-14, run 43578228704, FreeBSD 14.5-RELEASE and
15.0-RELEASE-p13, RACCT enabled in both): all nine held, on
both releases, on the first run. The module ran whole as root
in each guest — 155 tests, the 5 that exist only off FreeBSD
skipped, the 28 live tests among the rest all passing — and
each guest was read afterwards: no jail mount, no jail, no
skeleton directory, no rctl rule.

Against the table at the top of this page, the same nine
boundary tests that held two of nine on the first backend
hold nine of nine on this one:

| What the job did | What happens now |
|---|---|
| Asked for an unlimited address space, then for 700 MiB | Both refused, as root and as a job user |
| Wrote `/`, `/etc`, `/var/run`; made a directory at the root | All refused; the work mount and `/tmp` took their writes |
| Ran a root-owned set-user-ID program as the job user | It ran as the job user |
| Changed a file's owner | Refused |
| Wrote 640 MiB into `/tmp` | Stopped at the bound |
| Finished | Nothing of the job left on the host |
| Left a process behind and finished | The process ended with the jail; the job's files intact; nothing left |

The live tests of the further controls passed in the same
run: a fork past the jail's process ceiling refused; four
processes each under the per-process ceiling refused the
allocation that took them together past the jail's; a job
with a loopback reached its own listener, not the host's and
not the world, and could not change the interface; an
operator's bind read and not written, a moved work mount
landed in; an interpreter run from a prefix mounted for it,
and noted; a runner killed outright lost its jail within
seconds and the next sweep cleared its mounts, skeleton and
rules; and a job through the runner itself was confined,
recorded with the names above, and its declared output
collected.

The third guest — 14.5 as FreeBSD ships, RACCT off, which is
the state of the project's own node — first ran beside the
other two on the same day (run 43578832525), with a job
through the runner as a job user added to the module. All
three guests passed, 161 tests each. On the guest without
RACCT the two rctl tests skipped, as they are written to; the
record named no rctl control; everything else passed; and
nothing was left on any of the three.

The same day the live classes were run on the project's own
node, on a byte-identical copy of the tree and apart from the
hosted runs: 29 live tests, 27 passing and the two RACCT
tests skipping, with the boundary tests' assertions as they
were written against the first backend. On that host the
record reads `freebsd: jail + no_network + no_superuser +
spawn_resource_limits`, and the ceiling a job cannot lift is
held there by `allow.nosuser` alone.

One thing the run measured that this page had not supposed:
the whole module — every live job among its tests — took
under 8 seconds in a guest, so a jail of this shape costs a
job a fraction of a second to build and remove.

### The seed

Suppositions, recorded 2026-11-14 before the first hosted run
of the seed:

10. On a host where the backend engages, the seed, asked as
    root, leaves the mode at `enforce`, writes nothing for
    it, and names the controls a job's jail carries there; a
    runner started on that config passes the startup gate,
    and its first job is confined and recorded with those
    names.
11. Asked by an ordinary user on the same host, the seed
    states `audit`, and the reason printed names root.
12. A config that asks for the jail-wide ceilings by number
    is seeded at `enforce` on a host with RACCT enabled, and
    at `audit`, naming RACCT, on a host without it.
13. The installer started by its file's path from a source
    tree reaches the backend, and the seed it writes is the
    one the packaged installer writes.
14. The seed's probe leaves nothing on the host: no mount, no
    directory, no jail, no rule.
15. A second run over the same config changes nothing: a
    config the seed left at `enforce` is asked again and
    stays, and a config at `audit` is not asked.

Conclusions, from the first hosted run of the seed
(2026-11-14, run 43585328369, FreeBSD 14.5-RELEASE and
15.0-RELEASE-p13 with RACCT enabled, and 14.5-RELEASE
without): all six held, on all three guests, on the first
run. The module ran whole as root in each — 192 tests, the
six live tests of the seed among them — and each guest was
read afterwards: no jail mount, no jail, no skeleton
directory, no rctl rule.

| What was asked | What the seed did |
|---|---|
| The installer's seed, as root | Left `enforce`, wrote nothing, and printed the names a job's jail carries on that guest |
| A runner on that config | Passed the startup gate; its first job ran at `/work`, was refused a write to the root, and was recorded with the names the seed printed |
| The same seed, as an ordinary user | Stated `audit`; the line said creating a jail needs root |
| A config asking for a jail-wide ceiling by number | `enforce`, with `rctl_resource_limits` named, on the two guests with RACCT; `audit`, naming RACCT and its tunable, on the guest without |
| The installer started by its file's path | The same seed, with nothing of the runner loaded and nothing left loaded |
| The setup wizard's seed | The same answer from the same machine |
| The seed, a second time | Asked again; nothing changed |

The seed's live tests have run on the hosted guests. The
project's own node has not run them.

### What a job reads

Supposition, recorded 2026-11-14 before its first hosted run:

16. A job with no job user reads a root-only file in a tree
    the jail shows it; the same job under a job user is
    refused the file.

Conclusion, from its first hosted run (2026-11-14, run
43588595272, the same three guests): it held on all three. A
job with no job user, uid 0 inside its jail, read a file only
root may read from a tree the jail showed it; the same job
under a job user was refused it. The limit stands as this
page states it, and a job user is what closes it.

### The job user the seed names

Suppositions, recorded 2026-11-14 before the first hosted run
of it:

17. Where the seed leaves the jail on, it names `nobody`: the
    trial job reports `nobody`'s uid, writes its work mount
    and is refused a root-only file; `security.job_user` is
    written, and nothing else in the file changes.
18. A runner started on that config runs its first job as
    `nobody`, confined: the record names no `no_superuser`,
    the job_user record names the demote, a file all may
    read in a tree the jail shows is read, and a root-only
    file beside it is refused.
19. A config that names a job user of its own keeps it, and
    one whose `job_user` mode is stated down names none; no
    trial runs for either. An ordinary user's seed names
    none.
20. A later run over the seeded config changes nothing and
    runs no trial.
21. The trial leaves nothing on the host: no mount, no
    directory, no jail, no rule, and no folder of its own.

Conclusions, from its first hosted run (2026-11-14, run
43592323669, FreeBSD 14.5-RELEASE and 15.0-RELEASE-p13 with
RACCT enabled, and 14.5-RELEASE without): all five held, on
all three guests, on the first run. The module ran whole as
root in each — 218 tests, the nine live tests of the seed
among them — and each guest was read afterwards: no jail
mount, no jail, no skeleton directory, no rctl rule.

| What was asked | What the seed did |
|---|---|
| The installer's seed, as root | Left `enforce` and named `nobody`: one block added to the file, nothing else changed, and the lines printed carried no `no_superuser` |
| A runner on that config | Its first job reported uid 65534 at `/work`, was refused a write to the root and to the tree it was shown, read the file there that all may read, and was refused the root-only file beside it; the job_user record named the demote |
| The trial alone | Passed as `nobody`; refused to run for a user that is uid 0 and for one the machine does not have |
| A config naming a job user of its own | Kept it; no trial ran; the report read the operator's user |
| A config with the `job_user` mode stated down | Named no one; no trial ran |
| The same seed, as an ordinary user | Stated `audit` and named no one |
| A config asking for a jail-wide ceiling by number | Named `nobody` on the two guests with RACCT; `audit` and no user on the guest without |
| The installer started by its file's path | The same seed, the user named, nothing left loaded |
| The setup wizard's seed | The same answer from the same machine, the user named |
| The seed, a second time | Asked the first question again, ran no trial, changed nothing |

The project's own node has not run the seed's live tests.

### The account the installer makes

Suppositions, recorded 2026-11-14 before the first hosted run
of it:

22. On a guest with no such account, the installer's seed
    makes `pigeon-jobs` — no password, a login shell that
    lets no one in, no home directory, a group of its own —
    runs the trial as it, and names it.
23. A runner started on that config runs its first job as
    that account's uid, confined, and the job is refused a
    root-only file in a tree it is shown.
24. A second run finds the account named, makes nothing and
    changes nothing; and a fresh config seeded where the
    account already stands uses it as it is.
25. The wizard's seed makes no account: without the account
    it names `nobody`, and with it `pigeon-jobs`.
26. Where the account cannot be made, `nobody` is named and
    the line says why.
27. An account the seed made and could not use is removed
    again, and `nobody` stands in.
28. Apart from the account, the seed leaves nothing on the
    host.

The tests that make an account run only on a guest that is
thrown away afterwards. On any other host, the project's own
node among them, they skip, and the tests that run there
name a user without making one.

Conclusions, from its first hosted run (2026-11-14, run
43597374538, FreeBSD 14.5-RELEASE and 15.0-RELEASE-p13 with
RACCT enabled, and 14.5-RELEASE without): all seven held, on
all three guests, on the first run. The module ran whole as
root in each — 242 tests, the seven that make an account and
the nine that do not among them — and each guest was read
afterwards: no jail mount, no jail, no skeleton directory, no
rctl rule, and no jobs account.

| What was asked | What happened |
|---|---|
| The installer's seed, on a guest with no such account | Made `pigeon-jobs` — a password field no hash can match, `/usr/sbin/nologin`, `/nonexistent` and no directory there, a group of its own with no one else in it — ran the trial as it, and named it |
| A runner on that config | Its first job ran as the account's uid (1001 on each guest), confined, read the file all may read and was refused the root-only file beside it |
| The seed again, and a fresh config beside it | The second run made nothing, ran no trial and changed nothing; the fresh config used the account as it stood |
| An account of that name made another way first | Used as it stood; not a field of it changed |
| The wizard's seed | Without the account, named `nobody` and made nothing; with it, named `pigeon-jobs` |
| A maker that reports it could not make the account | `nobody` named on its own trial; the line gave the reason |
| An account made, and a trial that refuses it | The account was removed again, and `nobody` stood in on its own trial |
| The installer started by its file's path | Made the account and named it, with nothing of the runner loaded |
| The same seed, handed the finder instead of the maker | Named `nobody`, ran its first job as uid 65534, and added nothing to the user database |

The project's own node has not run these tests, and the seven
that make an account are not to run there.

### The suite on a FreeBSD host

Other modules' tests run the installer's main and the setup
wizard on the host the suite is on. From the release that
first asked the probe, the suite run as root on a FreeBSD
host whose backend engages put the seed's questions to that
host from those tests: the probe's jail, then the door trial,
and, in the two releases that made the account before the
switch stood (both of 2026-11-14), the account — `pw useradd`
reached from a test of another module. The hosted guests ran
this module alone as root, and the hosted suite runs as an
ordinary user, where the probe refuses and nothing is built.
A host where either release's suite was run whole as root may
hold a `pigeon-jobs` account the suite made; `pw userdel -n
pigeon-jobs` removes it.

Suppositions, recorded 2026-11-14 before the first hosted run
of the switch:

29. On a guest, as root, the other modules' tests that reach
    the seed — the installer's main with its service steps
    replaced, the wizard, and the installer's own modules
    with their copies of it — run in a process the suite
    starts, with no word handed down, and leave no jobs
    account and nothing else on the guest.
30. The same installer tests, started with the word on, make
    the account on that guest: the switch is what keeps them
    off the machine. With the word off and handed down, they
    make none.
31. The tests of the questions themselves still ask the
    machine under the suite's word: the sixteen live seed
    tests pass as they did.
32. The posture tests that ask for a clean report read clean
    on a FreeBSD host whose suite is not root. They read red
    on the hosted suite from the release that gave the report
    its FreeBSD line: the report was right to warn there, and
    the tests answered for bwrap alone.

Conclusions, from the first hosted run of the switch
(2026-11-14, run 43607344777, FreeBSD 14.5-RELEASE and
15.0-RELEASE-p13 with RACCT enabled, and 14.5-RELEASE
without): all four held, on all three guests, on the first
run. The module ran whole as root in each — 257 tests — and
each guest was read afterwards: no jail mount, no jail, no
skeleton directory, no rctl rule, and no jobs account.

| What was asked | What happened |
|---|---|
| The other modules' installer and wizard tests, as root, in a process the suite started with no word handed down | More than a hundred tests ran, and left no jobs account and nothing else on the guest |
| The installer's own tests again, with the word on | Made `pigeon-jobs` on each guest: the same tests, to the seed an install of that machine. The account was removed when the test ended |
| The same tests, with the word off and handed down | Made no account |
| The sixteen live seed tests, under the suite's word | Passed as they had: they switch the questions on by name |
| The posture tests, as an ordinary user | All 24 read clean, while the report's own word for that user was the warning that creating a jail needs root |

The hosted suite runs as an ordinary user, and it had read
those six posture tests red: in its whole run on the tag
before the change (run 43601192519) 13,260 tests ran and six
were red, all six these. On its run after the change (run
43607347206) none of them is named red. That run was ended
by its 30-minute clock before the suite's end, so it is not
a whole green run of the suite. The next one was: on the
first tag to carry the change (run 43612998944, the same
day) the suite ran whole, 13,294 tests with 167 skipped by
name, and none was red, the suite's first green run on a
hosted FreeBSD guest. Its clock is 45 minutes from
2026-11-15, and the first run under it (run 43663671470)
was whole and green in 1,969 seconds, past the 1,800 the
clock had stopped a run at. The run after it (run
43666816253) took 1,178 seconds over the same tests.

### The job user's process ceiling

Suppositions, recorded 2026-11-14 before the first hosted run
of the ceiling:

33. A job that goes in as a job user, under a ceiling of 24,
    starts children until the kernel refuses the fork, and
    the refusal is EAGAIN. The account then holds 24
    processes in all: the job's first one and twenty-three
    children. On the guest without RACCT too, where the
    record names no rctl rule.
34. The job reads 24 as both its soft and its hard limit and
    cannot raise either. Below the ceiling the limit is its
    own to move.
35. The count is the account's across jails. With one job of
    the account holding nine processes in its jail, a second
    job in a jail of its own starts fourteen children, not
    twenty-three.
36. A job with no job user carries no such limit: it starts
    forty children on every guest.
37. On the two guests with RACCT a job meets the lower of the
    two ceilings: under a jail rule of 12 it stops below 12,
    and under a jail rule of 48 it stops at the account's 24.
38. An account the installer made, held to 24, holds exactly
    24: nothing else runs as it. The installer's trial job
    reads the default, 256, and the installer's lines state
    it.
39. On a real host the startup probe refuses a config that
    names the ceiling and engages no job user, and one that
    names a number above `kern.maxprocperuid`; at that number
    exactly, the door sets it.
40. Nothing is left: when the jail goes, every process of the
    account goes with it, and each guest ends with no jail,
    no mount, no skeleton directory, no rule and no jobs
    account.

Conclusions, from the ceiling's two hosted runs (run
43655777234 of 2026-11-14 and run 43656341793 of 2026-11-15,
FreeBSD 14.5-RELEASE and 15.0-RELEASE with RACCT enabled, and
14.5-RELEASE without). Seven of the eight held on all three
guests on the first run. The eighth held on the second, after
a change the first run asked for.

| What was asked | What happened |
|---|---|
| A job as a job user, under a ceiling of 24 | Read 24 as its soft and its hard limit, started twenty-three children, and was refused the next fork with EAGAIN — on the guest without RACCT too, where the record named no rctl rule |
| The same job, raising its limit | Refused three ways. Below the ceiling it lowered its limit to 10 and put it back |
| A second job, with a first holding nine processes in another jail | Started fourteen children, not twenty-three: one count across the two jails |
| A job with no job user | Started forty children; no limit had been set on it |
| The jail's rule beside the account's ceiling, on the two guests with RACCT | Under a rule of 12 the job stopped below 12. Under a rule of 48 it stopped at the account's 24 |
| An account the installer made, held to 24 | Held exactly 24. The installer's trial job read 256 back, and the installer's lines stated it |
| A config that cannot have its ceiling | The startup probe refused it by name, both ways. At `kern.maxprocperuid` exactly, the door set the limit |
| What was left | Nothing, on the second run |

Supposition 40 was the one the first run did not bear out as
written. With the first of the two jobs ended and its jail
removed, the account still held one process: that job's own
first process, ended and not yet collected, because the test
had ended the job without collecting it as a runner does. An
ended process is still its user's until its parent collects
it, and those are the processes this ceiling counts. The
release collects the job's first process itself now, once the
jail is gone, and the second run read all eight true: 284
tests as root in each guest, and no jail mount, jail,
skeleton directory, rctl rule or jobs account afterwards.

### The job's cores

Suppositions, recorded 2026-11-15 before the first hosted run
of the pin:

41. Each guest has more than one core, and the test process —
    the runner, to the backend, as root on the host — reads
    every one of them as its own.
42. A job under the default reads as its cores all of the
    runner's but the lowest. The record names
    `cpuset_cpu_limit` and its detail carries the cores. On
    the guest without RACCT too, where the record names no
    rctl rule.
43. Under `job_cpus` of 1, and of each number up to one below
    the runner's own count, a job reads that many cores, the
    highest-numbered. At the runner's own count, and above
    it, a job reads the runner's cores and the record names no
    limit.
44. A job narrows its cores to one of its set and puts them
    back. Asked for every core the runner has, three ways —
    its own process's cores, the set it stands in, a set it
    makes for itself — it is refused each time and reads its
    set unchanged afterwards. As uid 0 inside the jail, and as
    `nobody`.
45. A process the job starts after that has the job's set.
46. A job pinned to one core that spins twice as many
    processes as the guest has cores, for three seconds by
    the clock, uses about three seconds of processor in all:
    one core's worth. The same job with no core held back
    uses more than 1.3 times as much.
47. Two jobs at once read the one set.
48. A job that goes in as a job user is pinned as any other.
49. The startup probe passes with its trial jail pinned: the
    trial reads from inside the cores its jail was given.
    Through the runner itself the job's audit record names
    the limit and carries the cores in its detail.
50. The runner's own cores are what they were after every job,
    and nothing is left: no jail, no mount, no skeleton
    directory, no rule and no jobs account.
