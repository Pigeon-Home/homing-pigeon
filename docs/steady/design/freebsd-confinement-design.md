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

RACCT is a boot tunable (`kern.racct.enable=1` in
`/boot/loader.conf`), off as FreeBSD ships. Where it is off
an rctl rule can deny nothing, so the two jail-wide rules are
not written and `rctl_resource_limits` is not named. That is
the one place a default adapts to the host. A setting the
operator wrote does not adapt: `job_processes` or
`job_memory_bytes` in the config on a host without RACCT
refuses the start and says which tunable to set.

The per-process ceiling is a resource limit, not a kernel
rule. It holds because the job has no privilege to raise it.

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
    "job_processes": 256
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
enabled the rules are.

A passing verdict is kept for the life of the runner process,
for the settings it was run with, so the per-job gate does not
build a throwaway jail beside every job's own. The cheap
checks — root, the base tools, the host trees — run every
time. A particular job's spawn still builds its own jail, and
its failure refuses that job.

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
| Home directories | Not visible | Not visible |
| Network | A namespace with a loopback of its own | None; a loopback of its own by a switch |
| Host's processes | Visible through `/proc` (the process namespace is shared) | Not visible |
| Root inside | uid 0 in a user namespace, its capabilities dropped | uid 0 with no privilege, or the job user |
| Set-user-ID programs | Not honoured (no new privileges) | Not honoured (`nosuid` mounts) |
| Memory ceiling, per process | None | 512 MiB, not the job's to raise |
| Ceilings on the whole job | None | Processes and address space, where RACCT is enabled |
| Operator binds, work mount | Yes | Yes, the same keys |
| Interpreter outside the trees | Its prefix, read-only, recorded | The same rule, the same record |
| Runner gone | The sandbox's command is killed | The jail is removed: every process ends |
| Startup probe | Starts the sandbox once | Builds a jail and reads the boundary from inside |

The Linux column is bwrap as this project starts it
(`DEFAULT_FLAGS` in `runner/guard/sandbox.py`) and
bubblewrap's documented behaviour. The FreeBSD column is what
the live tests read from inside a job. Linux keeps one thing
this design cannot have: it confines without root.

## What it does not do

- It is not Capsicum. Capability mode is entered by a program
  that knows it is being confined; a launcher for arbitrary
  interpreters cannot enter it for them.
- It is not unprivileged. The runner must run as root for the
  backend to engage.
- The per-process ceiling is not a kernel rule (above).
- Memory a job holds outside any process's address space — a
  shared-memory object it never maps — is bounded by neither
  ceiling. The `/tmp` bound closes the largest such door.
- The work directory is on the host's disk and is not bounded
  here.
- No CPU ceiling.
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
  the jail-wide rules, the loopback, the binds, the
  interpreter's prefix, a runner killed outright, and jobs
  through the runner itself, with and without a job user.
  Weekly and on dispatch.
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
