# macOS confinement: the profile and its launcher, specified

Status: design of record, written 2026-11-15 at the owner's
direction, and built the same day
(`runner/guard/macos_confine.py`; tests in
`runner/tests/test_macos_confine.py`; the hosted live proof
is the `macos-confinement` workflow). The build is a
transcription of this text. Where the kernel answered
differently from what this text supposed, the difference is
written in "Suppositions and conclusions" at the end, in the
open.

Confinement is the software suite's own, platform by
platform. The protocol documents do not specify it — a
submitter must not assume a sandbox on the far side — so
nothing here changes a message, a field or a document under
`docs/ietf`. This page and `docs/steady/security/macos.md`
are where the macOS shape is written down;
`docs/support-matrix.md` carries the claim.

## Where the backend stood

The backend this design starts from confined a job with a
Seatbelt profile and one resource limit, and its record of
five rounds of fixes stands in
`docs/steady/security/macos.md`. Four things about it were
read on two hosted Macs on 2026-11-15, before anything here
was built (the `macos-confinement` workflow's first run,
43683198505: macOS 15.8.2 on Apple silicon with 3 cores and
7 GiB, and macOS 15.7.9 on Intel with 4 cores and 14 GiB).

- A release's macOS binaries could not engage it. The
  launcher that set the limit was the runner's own
  interpreter, started a second time inside the profile. A
  runner frozen into one file has no interpreter to start:
  it starts itself, unpacks its library into the temporary
  directory, and the profile refuses the load. On both
  Macs the frozen runner at `enforce` refused to start,
  naming a trial process that "could not read its staged
  file", with the loader's own error behind it.
- The memory ceiling held nothing a job would meet. Darwin
  holds a data-size limit against a process's whole address
  map, and refuses a limit below the map's present size. A
  bare process's map is already 391.7 GiB on the Apple
  silicon Mac and 32.5 GiB on the Intel one. The launcher
  answered the refusal by doubling its request until one
  was accepted: the first doubling above those sizes is
  512 GiB and 64 GiB, which left a job 120 GiB and 31 GiB
  to grow into. It set the soft limit alone, so the job
  could lift even that.
- A fresh install stated confinement at `audit`, on every
  Mac, without asking the machine: jobs ran unconfined
  until the operator changed the file.
- Its live tests had run in the whole suite's macOS job
  alone: on Apple silicon, as an ordinary user. They passed
  in that first run on Intel as well, and as root on both.

## What the design is for

1. A release's macOS binaries engage confinement, exactly
   as a runner started from source does.
2. The memory ceiling is a number a job meets, on every
   Mac, and is not the job's to raise.
3. A fresh install leaves confinement at `enforce` where the
   backend's probe passes on that Mac, and says what a job
   carries there; where it does not pass it states `audit`
   and prints the reason.
4. The probe reads the boundary from inside: a start that
   passes it has seen a write and a read outside the work
   directory refused, and a ceiling in force.
5. What a job can still reach is written down, with the run
   that read it.

## The controls

The audit record's string is unchanged:

```
macos: seatbelt_profile + no_network + spawn_resource_limits
```

| Control | What it is | Needs |
|---|---|---|
| `seatbelt_profile` | A profile made for the job and applied by `sandbox-exec` before the job's first instruction: deny by default; the system trees and the job interpreter's own readable; the work directory the one tree that takes a write | `/usr/bin/sandbox-exec` |
| `no_network` | The profile names no network rule and states the denial: no socket leaves the job, loopback included | the profile |
| `spawn_resource_limits` | A ceiling on each job process's address map, set soft and hard by the launcher before the job's command starts | `/bin/sh` |

The record's detail says what one job's launch carried
beyond that: the ceiling, and the job user where one was
applied.

## The profile

The profile is the first backend's, unchanged by this
design. It starts from deny-by-default and allows:

- reading and executing the system trees (`/System`, `/usr`,
  `/Library`, `/bin`, `/sbin`, `/opt`, `/etc` and the
  `/private` startup trees a process reads as it starts)
  and the install prefix of the job's interpreter when that
  stands outside them — never a home directory;
- reading and writing the job's work directory, and nothing
  else of the filesystem;
- the root directory's own listing, and file metadata (that
  a path exists, its size and times, never its contents) on
  any path, which a process needs to resolve the paths it
  is allowed;
- starting processes, reading system settings, and talking
  to the system's services over Mach and POSIX IPC.

It denies every network operation. Two things it gives by
that last allowance are named under "What it does not do".

## The launcher

`sandbox-exec` applies the profile and starts the launcher,
which sets the ceiling and replaces itself with the job's
command. The launcher is the system shell:

```
/usr/bin/sandbox-exec -p <profile> /bin/sh -p -c <text> hp-shim <KiB> <the job's command>
```

The text is a few lines of POSIX shell in the backend
itself. It is passed as an argument, as the profile is:
nothing is staged on disk, and nothing in the chain is the
runner's own interpreter. That is what lets a frozen runner
engage, and it is the whole of why the launcher changed.

Three properties of the text are held by tests:

- It names no command but the shell's own builtins, so
  nothing on the job's `PATH` runs before the job does.
- Every expansion is quoted or arithmetic: a job's
  arguments and environment pass through whole.
- Every limit it tries, it tries in a subshell. A refusal
  ends the subshell; the launcher keeps the limits it had.

`-p` is the shell's privileged mode. A job's environment is
the submitter's, and it reaches the launcher's shell.
`/bin/sh` on a Mac is bash unless the machine's owner
selects another, and bash takes shell functions and an
option list from its environment: a variable there could
stand a function of the submitter's under the name
`ulimit`, or tell the shell to read the launcher and run
none of it. In privileged mode bash takes neither. The
other two shells `/bin/sh` can be set to, dash and zsh,
take neither in any mode and accept the flag.

Between the profile and the job stands a shell, so three
variables in a job's environment are the shell's — `SHLVL`,
`PWD` and `_` — as they are for any job whose interpreter
is `sh`, which is the default.

## The memory ceiling

The kernel refuses a data-size limit below the size of the
asking process's address map, so no fixed number can be the
limit: 512 MiB is refused on every Mac. The launcher
therefore finds the floor first — the smallest value the
kernel accepts from it:

1. It asks for the ceiling itself. On a host with no floor
   above it, that is the limit.
2. Refused, it doubles the value until one is accepted.
3. It halves the gap between the last value refused and the
   first accepted until the gap is one mebibyte. The upper
   end is the floor.

The limit it applies is the floor plus the ceiling, soft
and hard. The ceiling is therefore a distance: how far a
job process's address map may grow past the size a bare
process starts at on that Mac.

- The ceiling is 512 MiB unless the operator names another
  (`process_memory_bytes`, below).
- The hard limit is set as well as the soft one, so the job
  cannot raise either.
- A hard limit the launcher inherits is never raised: a
  value above it is clamped to it, and a Mac whose floor
  stands above it refuses the job by name.
- A Mac where no value up to 2^62 bytes is accepted refuses
  the job by name.

It is a ceiling on the address map, not on memory touched,
and it is each process's own. A program that reserves
address space it never uses — a language runtime's heap
reservation is the common case — needs the reservation to
fit. Read on the two hosted Macs before the build, by the
distance above the floor:

| | 512 MiB | 2 GiB | 8 GiB |
|---|---|---|---|
| `sh`, `python`, `perl`, `git` | start | start | start |
| `ruby` | starts on Intel, not on Apple silicon | starts | starts |
| `node` | does not start | starts | starts |
| `java` | does not start | does not start | starts |

An operator whose jobs run such a runtime names a larger
ceiling. What a job has for its own data is the ceiling less
what its own program maps at its start.

There is no ceiling on a job's processes taken together,
and none on processor time or cores: macOS gives an
unprivileged process no call that holds either.

## The job user

A macOS install runs as its user's own launchd agent, not
as root, and the profile needs no privilege: a job is its
runner's user, kept by the profile from that user's files.
Where an operator does run the runner as root with a job
user named (`security.job_user`), the spawn applies the
user between its fork and the start of `sandbox-exec`: the
whole chain — `sandbox-exec`, the launcher, the job — is
that user's, with the groups the user database gives it.
Nothing inside the profile is root, and no step inside it
needs to be. The directory the spawn makes for the job's
temporary files is handed to that user.

A runner that is not root and is handed a job user refuses
the job. A user the Mac does not have is a refusal.

## Configuration

```json
"confinement": {
  "macos": {
    "process_memory_bytes": 536870912
  }
}
```

One setting: the ceiling, in bytes. A positive integer; a
setting the backend does not know is an error, because a
ceiling an operator misspelled is a ceiling that is not
there. The block is checked on every platform, so a config
is right or wrong the same way wherever it is read.

The keys the Linux sandbox and the FreeBSD jail share —
`work_mount`, `extra_ro_binds`, `extra_flags` — name mounts
and bwrap arguments. There is no mount here; this backend
reads none of them.

## The probe

At `enforce` the startup gate asks the backend, and a job's
own gate asks it again; the verdict is kept for the life of
the process, one per ceiling.

1. The config's `macos` block reads.
2. `sandbox-exec` and `/bin/sh` are there.
3. `sandbox-exec` starts a trivially confined process.
4. A trial runs under the full controls — the profile, the
   launcher, the ceiling this config names. It is a shell
   program staged in a work directory of its own, with one
   file beside that directory, outside it. It must read its
   staged file, write its work directory, be refused a
   write beside the directory and a read of the file there,
   and say it carries one data-size limit, soft and hard.

Each stage that fails is named. A spawn that confines
nothing does not pass: the trial's own program, run with no
profile, writes outside its work directory and is convicted
by the file it leaves.

The posture report asks the same probe — the trial needs no
privilege and leaves nothing on the host — and says what a
job carries here: the controls, and the ceiling with the
floor it stands on.

## The mode a fresh install states

The installer and the setup wizard ask the probe on the Mac
they are seeding, with the config they are about to leave.

- Where it passes, `security.modes.confinement` is left at
  `enforce`, nothing is written for it, and the lines
  printed say so and say what a job carries on that Mac.
  The startup gate asks again at every start.
- Where it does not pass, the mode is stated at `audit` in
  the file, and the line that says so carries the probe's
  reason.
- A mode the config already states below `enforce` is the
  operator's word: it stays, and nothing is asked.

No job user is named on macOS, and no account is made: the
second question a FreeBSD seed asks is the jail's.

A frozen installer carries the backend's one file and loads
it by path; the backend imports nothing of the runner's, so
the file is all it needs. A frozen runner's setup wizard
finds the backend where the runner does.

### Where the machine is not asked

A caller that only names macOS — a test, a report — gets
the stated map, `audit`, and nothing on the host is asked.
Whatever drives the installer or the wizard on a machine it
is not installing sets `HP_SEED_ASKS_MACHINE=0`, as the
test suite does for every host it runs on: the seed then
states `audit` and says the machine was not asked.

## The release binaries

A release's two macOS archives each carry a frozen runner
and a frozen installer. The `macos-confinement` workflow
freezes both on each leg with the build workflow's own
commands, read out of `build.yml`, and asks of them what a
release's user meets: the runner starts at `enforce` and
runs a job under it, and the installer, run from a staged
copy of the archive into a home of its own, leaves
`enforce` in the config it writes.

## Beside the Linux sandbox and the FreeBSD jail

| | Linux (bwrap) | FreeBSD (jail) | macOS (this design) |
|---|---|---|---|
| Needs | An unprivileged user namespace | Root | Nothing: the runner's own user |
| What a job sees of the filesystem | A root of its own with `/usr` read-only | A root of its own with the system directories read-only | The host's own paths; the profile refuses what it does not name |
| Trees that take a write | The work mount, a private `/tmp`, the sandbox's own root | The work mount and a bounded `/tmp` | The work directory, which holds the job's temporary directory |
| Home directories | Not visible | Not visible | Not readable and not listed; that a named path exists can be learned |
| Network | A loopback of its own | None; a loopback of its own by a switch | None |
| Host's processes | Visible | Not visible | Visible; a signal to one is refused |
| Set-user-ID programs | Not honoured | Not honoured | Refused: they do not start |
| Memory ceiling, per process | None | 512 MiB, not the job's to raise | 512 MiB above a bare process's address map, not the job's to raise |
| Ceilings on the whole job | None | Processes and address space, where RACCT is enabled; the job user's processes on every host | None |
| Cores a job runs on | Not limited | All but one of the runner's | Not limited |
| Operator binds | Yes | Yes | No: the keys name mounts |
| The session's services | Not reachable (no session) | Not reachable | Reachable: the clipboard was read from inside a job |
| Startup probe | Starts the sandbox once | Builds a jail and reads the boundary from inside | Runs a trial under the full controls and reads the boundary from inside |
| A fresh install | `enforce`; the startup gate decides | `enforce` where the probe passes, with a job user made and named | `enforce` where the probe passes; `audit`, stated with the reason, where it does not |
| A release's frozen binaries | Engage | None are built | Engage |

The Linux column is bwrap as this project starts it and the
FreeBSD column is its design page's. macOS keeps one thing
the other two do not have: it confines without root and
without a kernel feature an administrator must switch on.
It lacks what a separate root gives: a job sees the host's
path layout, and the names in it.

## What it does not do

- It does not keep a job from the session's services. The
  profile lets a job look up any Mach service, and the
  pasteboard is one: text put on the clipboard outside a
  job was read from inside one on both hosted Macs. A job
  has no network to send it over; its output goes back to
  whoever submitted it.
- It does not hide the host's processes. A job listed 520
  of them on one Mac and 463 on the other. It cannot signal
  them.
- It does not hide that a path exists. Metadata is readable
  everywhere; contents are not.
- It holds no ceiling on a job as a whole, on processor
  time, or on cores.
- It makes no mount: `work_mount` and `extra_ro_binds` name
  nothing here, and a job cannot be shown a tree outside
  the system's and its own.
- It keeps no hold on a job's processes as a group: there
  is no jail to remove and no namespace to close, so nothing
  here ends a process a job has started and left running.
- App Sandbox is not used, and `sandbox-exec` is a tool
  Apple has marked deprecated while still shipping it. The
  probe is what the gate consults: a macOS that removes the
  tool refuses at startup.

## Proof

The backend's test module runs on every platform the suite
runs on: the launcher's text is run against a kernel
scripted in the launcher's own language, where any floor
and any hard limit can be staged, side by side with the
rule written as a function; and against the host's own
kernel on every POSIX leg. The live classes run on a Mac:
in the whole suite's macOS job, and in the
`macos-confinement` workflow on an Apple silicon Mac and an
Intel Mac, as the ordinary user and as root, where the
frozen binaries are asked as well.

## Suppositions and conclusions

Recorded 2026-11-15, after the first run's measurements and
before the build's first hosted run. Each is what the
hosted Macs are expected to answer; each is judged by the
`macos-confinement` workflow and by nothing else.

1. The probe passes on both Macs, as the ordinary user and
   as root, with the launcher a shell.
2. The limit a job carries is one number, soft and hard,
   and it is the ceiling above a floor within one mebibyte
   of what `/bin/sh` read in the first run: 391.7 GiB on
   Apple silicon, 32.5 GiB on Intel.
3. The job cannot raise it: not through the shell, and not
   through the call itself.
4. The ceiling is met: under 512 MiB a Python job's 16 MiB
   buffer fits and a 768 MiB one is refused, by a
   `MemoryError` in the job; the largest that fits is below
   512 MiB.
5. A ceiling of 2 GiB in the config moves the limit by
   1.5 GiB and admits the 768 MiB buffer.
6. A function exported under the name `ulimit` in a job's
   environment, in either shape bash reads, does not lift
   the ceiling, and an option list there does not stop the
   launcher — on the bash a Mac ships.
7. As root with `nobody` named, the job is `nobody` from
   its first process: it says so, writes its work directory
   and its temporary directory, and does not read a file
   only root may read.
8. An ordinary runner handed a job user refuses the job.
9. A set-user-ID program does not start under the profile;
   a signal to a process outside is refused; a job handed
   to launchd is not run.
10. The trial convicts a spawn that confines nothing, on a
    Mac as elsewhere.
11. The frozen runner starts at `enforce` on both Macs and
    runs a job under it: the job finds its work directory
    writable, a write outside it refused, and one data-size
    limit, soft and hard; the audit log names the controls.
12. The frozen installer, run from a staged copy of the
    archive, leaves `security.modes.confinement` at
    `enforce` in the config it writes and prints what a job
    carries on that Mac.
13. The first backend's live points still hold under the
    shell launcher: a spawn inside the profile, an escape
    write and an escape read refused, no network, a native
    binary, the profile alone and the launcher alone.
