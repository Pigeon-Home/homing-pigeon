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

One rule of the profile was specified after the rest, the
same day and at the owner's direction: which of the
session's services a job may look up. It is "The session's
services" below, with its own measurements, suppositions
and conclusions.

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
6. A job is not answered by the session's services. It may
   ask the user database who a user is, and nothing else
   there: the clipboard is not a job's to read or to write.

## The controls

The audit record's string is unchanged:

```
macos: seatbelt_profile + no_network + spawn_resource_limits
```

| Control | What it is | Needs |
|---|---|---|
| `seatbelt_profile` | A profile made for the job and applied by `sandbox-exec` before the job's first instruction: deny by default; the system trees and the job interpreter's own readable; the work directory the one tree that takes a write; the user database the one service of the session that answers | `/usr/bin/sandbox-exec` |
| `no_network` | The profile names no network rule and states the denial: no socket leaves the job, loopback included | the profile |
| `spawn_resource_limits` | A ceiling on each job process's address map, set soft and hard by the launcher before the job's command starts | `/bin/sh` |

The record's detail says what one job's launch carried
beyond that: the ceiling, the services the config names
where it names any, and the job user where one was applied.

## The profile

The profile is the first backend's in every rule but one,
the rule on the session's services. It starts from
deny-by-default and allows:

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
- starting processes, reading system settings, and POSIX
  IPC;
- a lookup of the services of the session the profile
  names, and of no other.

It denies every network operation. What the allowance for
processes leaves a job able to see is named under "What it
does not do".

## The session's services

A Mac's programs reach its services by name, through
launchd: the pasteboard, the window server, launch
services, the keychain's and the network configuration's
daemons, and the user database among them. The first
backend's profile let a job look up any of them, and
register a name of its own. What that gave a job was read
from inside one on both hosted Macs on 2026-11-15 (the
`macos-confinement` run 43761537586), under the profile as
it stood and under the same profile with only the user
database named. The two Macs answered alike.

| Asked from inside a job | Every service open | The user database alone |
|---|---|---|
| A mark put on the clipboard outside the job | Read | Not read |
| A write to the clipboard | Landed | Did not land |
| A lookup of the pasteboard | Answered | Refused |
| A name registered in the session | Taken | Refused |
| The network configuration (`scutil --dns`) | Answered | Refused |
| The list of keychains | Answered | Refused |
| The list of disks | Answered | Refused |
| An application opened, a script opened | Refused | Refused |
| A name resolved | Not resolved | Not resolved |
| The host's process list | Listed | Listed |
| The hardware's serial number | Read | Read |

The profile now names the services a job may look up:

```
(allow mach-lookup (global-name "com.apple.system.opendirectoryd.libinfo") (global-name "com.apple.system.opendirectoryd.membership"))
```

Those two are the user database: how a process learns who a
user is and which groups it is in. Every other service is
refused, and so is every other Mach operation: a job
registers no name, and asks for no task port and no host
port. A service is named whole — no pattern and no prefix —
so what a job may look up is a list that can be read.

### What a job's programs ask for

The same run read what the list costs. Thirty-six programs
a job is likely to be were run under the profile with every
service open, with none, and with lists between: the
shell's own tools, `id`, `whoami`, Python, Perl, Ruby,
Node, `git`, `cc`, `make`, `curl`, `openssl`, `sqlite3`,
`zip`, `tar`, `osascript`, and the system's reporting
tools.

| Services named | Programs that behaved as with every service open |
|---|---|
| None | 28 of 36 |
| The user database: its two names, and an older third | 36 of 36 |
| That, and the notification centre | 36 of 36 |
| Those, and the preferences daemons | 36 of 36 |
| Those, and the log daemons | 36 of 36 |
| Those, and the directory helper and the trust daemons | 36 of 36 |

With none named, the eight that differed are the ones that
ask who a user is. `id -un`, `whoami` and `ls -l` printed
the number where the name goes; the lookup raised an error
in Python, Ruby and Node and returned nothing in Perl; and
`defaults` could not read a value out of a system file.
With the user database named, all eight behaved as before.

The programs did ask for more, and the system's log holds
each refusal: the log daemon, the notification centre, the
directory helper, the analytics daemon, the trust agent and
the disk arbitration daemon, and for `osascript`, `curl`
and `java`, launch services, the network configuration's
daemon and the core services daemon. No program of the
thirty-six behaved differently for being refused them, so
none of them is named.

Seven of the thirty-six do not work under the profile at
all, with every service open as with the user database
alone, and for reasons that are not services. `git`, in
both its rows, reads a configuration file in the user's
home, which the profile does not let it read. `cc`, `make`
and `xcrun` look for a toolchain under `/Applications`, a
tree the profile does not name. `java`'s launcher finds no
runtime, and the `sqlite3` first on those Macs' path is one
kept under the user's home.

The older third name was never asked for by any of them, so
the profile names two; that the two are enough is the
build's own supposition, below.

### A service the operator names

```json
"confinement": {
  "macos": {
    "mach_services": ["com.example.service"]
  }
}
```

Where a job's work needs a service, the operator names it.
The names are added to the backend's two; nothing takes
those away. A name is one to 255 letters, digits, dots,
underscores, hyphens and at signs, starting with a letter
or a digit — what launchd takes, and nothing a profile's
syntax could read as its own. At most 64 are named. A name
that is not one, or a list that is not a list, is a config
error and a refusal to start.

The audit record's detail names the services a job's launch
carried by the operator's word, and the posture report
names them and says whether the pasteboard is among them.

A named service is looked up as it is by any program of the
session, and no more is promised of it. The pasteboard
(`com.apple.pasteboard.1`) shows why. Named beside the user
database on both hosted Macs, it answered a job's lookup,
and the system's reader ended 0 — and printed nothing: the
mark on the clipboard came back only with every service
open, and a job's write to the clipboard did not land
either. What a service does for a caller that reaches it and
nothing else of the session is the service's own matter;
the system log names what else a program asked for.

### What the probe asks

The trial asks the pasteboard for the clipboard, with the
system's own reader. It throws away whatever the reader
would print — the trial takes the answer, never the
clipboard — and a start that passes has seen the reader
refused. Where the config names the pasteboard, the answer
is recorded and is not a refusal: that config says the
pasteboard may answer a job, and the posture report repeats
it.
A Mac with no reader, or a session with no pasteboard,
answers nothing: there the question proves nothing, and
there is no clipboard for a job to read.

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
  cannot raise either — unless the job is root. Root may
  raise a hard limit, under a profile as anywhere. A runner
  that is root names a job user, whose jobs are not root.
- A hard limit the launcher inherits is never raised: a
  value above it is clamped to it, and a Mac whose floor
  stands above it refuses the job by name.
- A Mac where no value up to 2^62 bytes is accepted refuses
  the job by name.

It is a ceiling on the address map, not on memory touched,
and it is each process's own. A program that reserves
address space it never uses — a language runtime's heap
reservation is the common case — needs the reservation to
fit. Read on the two hosted Macs through the launcher itself,
by the ceiling, the same on both in both of its hosted runs:

| | 512 MiB | 2 GiB | 8 GiB |
|---|---|---|---|
| `sh`, `python`, `ruby`, `perl`, `git` | start | start | start |
| `node` | does not start | starts | starts |
| `java` | does not start | does not start | starts |

A runtime near the line starts or not by a few mebibytes:
in the measurement taken before the build, `ruby` did not
start at 512 MiB on Apple silicon. An operator whose jobs
run such a runtime names a larger ceiling. What a job has
for its own data is the ceiling less what its own program
maps at its start: the largest buffer a Python job made and
touched under 512 MiB was between 256 MiB and 512 MiB on
Apple silicon, reading by reading, and 512 MiB on Intel.

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
    "process_memory_bytes": 536870912,
    "mach_services": []
  }
}
```

The ceiling, in bytes: a positive integer. And the services
of the session a job may look up beyond the user database,
which "The session's services" specifies; a config that
leaves the list out names none. A
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
the process, one per ceiling and list of services.

1. The config's `macos` block reads.
2. `sandbox-exec` and `/bin/sh` are there.
3. `sandbox-exec` starts a trivially confined process.
4. A trial runs under the full controls — the profile, the
   launcher, the ceiling this config names. It is a shell
   program staged in a work directory of its own, with one
   file beside that directory, outside it. It must read its
   staged file, write its work directory, be refused a
   write beside the directory and a read of the file there,
   say it carries one data-size limit, soft and hard, and
   be refused the clipboard.

Each stage that fails is named. A spawn that confines
nothing does not pass: the trial's own program, run with no
profile, writes outside its work directory and is convicted
by the file it leaves.

The posture report asks the same probe — the trial needs no
privilege and leaves nothing on the host — and says what a
job carries here: the controls, the ceiling with the floor
it stands on, and which of the session's services answer a
job. Where the runner is root and names no
job user, it says the ceiling is set and does not say it
holds, and one line of advice names the remedy.

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
runs a job under it, which is refused the clipboard — and
is answered by it under a config that names the pasteboard
— and the installer, run from a staged copy of the archive
into a home of its own, leaves `enforce` in the config it
writes.

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
| Memory ceiling, per process | None | 512 MiB, not the job's to raise | 512 MiB above a bare process's address map, not the job's to raise unless the job is root |
| Ceilings on the whole job | None | Processes and address space, where RACCT is enabled; the job user's processes on every host | None |
| Cores a job runs on | Not limited | All but one of the runner's | Not limited |
| Operator binds | Yes | Yes | No: the keys name mounts |
| The session's services | Not reachable (no session) | Not reachable | The user database, and what the config names; the clipboard is refused |
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

- It does not hide the host's processes. A job listed
  between 431 and 520 of them on one Mac and about 460 on
  the other. It cannot signal them.
- It does not hide the hardware's properties. The I/O
  registry is not one of the session's services, and a job
  read from it that the Mac's serial number is there.
- It does not vouch for a service the operator names. A
  named service answers a job as it answers any program of
  the session, and what it will do for one is its own
  matter.
- It does not hide that a path exists. Metadata is readable
  everywhere; contents are not.
- It holds no ceiling on a job as a whole, on processor
  time, or on cores.
- It does not hold a job that is root to its ceiling. That
  is a runner run as root with no job user named, which a
  macOS install is not.
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

The session's services are asked by name from inside a job,
and launchd's own answer is the evidence: it gives a caller
whose sandbox does not let it ask one number, and a name
that is merely not there another. The clipboard tests put a
mark of their own on the session's clipboard and put back
the text that was there, so they run where they are asked
for — in the workflow — and are skipped on a Mac where a
person's clipboard is.

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

### Conclusions

Two hosted runs judged the build, both on 2026-11-15. The
first (43687676740, on the landing) answered eleven of the
thirteen as supposed and two differently. The second
(43688324966, on the commit that took those answers) is
green on both Macs: the backend's 214 tests as the ordinary
user and again as root, and the frozen runner's and the
frozen installer's own checks.

1. Held. The probe passes on both Macs as both users.
2. Held, though not to the mebibyte. A job's limit read
   411,256,832 KiB on Apple silicon and 34,654,208 KiB on
   Intel, soft and hard: 512 MiB above floors of 391.7 GiB
   and 32.5 GiB, as in the first run. From one process to
   the next, and from one user to the other, the floor
   moved by up to 7 MiB.
3. Held for a job that is not root, and not for one that
   is. As the ordinary user the raise was refused, through
   the shell and through the call itself. As root with no
   job user, a job's subshell raised its hard limit for the
   asking: root may, under a profile as anywhere. The pages
   now say so, and the posture report says of such a runner
   that the ceiling is set, not that it holds.
4. Held as to the ceiling being met: a 16 MiB buffer fit
   and a 768 MiB one was refused every time, by a
   `MemoryError`. The largest that fit was not always below
   512 MiB: 256, 384, 384 and 512 MiB in four readings on
   Apple silicon, and 512 MiB in each on Intel, where the
   interpreter's own map starts smaller than the shell's.
5. Held. A 2 GiB ceiling moved the limit by 1.5 GiB and
   admitted the 768 MiB buffer.
6. Held on the bash a Mac ships. A job whose environment
   carried a function named `ulimit` in both shapes, and an
   option list that stops a shell running, read a limit set
   soft and hard. The same environment did reach a job that
   was itself a shell, which called the function: the
   hazard is real there, and the flag is what closes it for
   the launcher.
7. Held after one change. The user database's group list
   for `nobody` on those Macs carries -1, which a spawn
   refuses by name; the list now leaves it out. The job
   then said it was `nobody`, wrote its work directory and
   its temporary directory, did not read a file only root
   may read, and could not raise its ceiling.
8. Held, after the same change: the refusal is the job's,
   by name.
9. Held on both Macs as both users.
10. Held.
11. Held. The frozen runner started at `enforce` on both
    Macs; the job through it exited 0, and no file landed
    outside its work directory. Its record reads `confined`,
    `macos: seatbelt_profile + no_network +
    spawn_resource_limits`, with the detail "memory ceiling
    512 MiB above a bare process's address map, soft and
    hard". The record stands in the audit log under the
    state directory's work tree, where a job run by that
    door keeps it.
12. Held. On both Macs the frozen installer printed that
    `security.modes.confinement` was left at `enforce`, with
    the backend's two lines for that Mac, and the config it
    wrote states `enforce`.
13. Held. Every live point of the first backend passes
    under the shell launcher.

Two reaches the profile then left a job were read again in
both runs: a job listed the host's processes, and read from
the clipboard a mark put there outside it. The second is
what "The session's services" closes.

### The session's services: suppositions

Recorded 2026-11-15, after the measuring run (43761537586)
and before the first hosted run of the profile that names
its services. Each is what both hosted Macs are expected to
answer, as the ordinary user and as root, and each is
judged by the `macos-confinement` workflow and by nothing
else.

14. A lookup of the pasteboard from inside a job is refused,
    with the number launchd gives a caller whose sandbox
    does not let it ask (1100). No other service the
    profile does not name answers either: the window server,
    launch services, the network configuration's daemon,
    the security server, the preferences daemon, the
    notification centre, the log daemon, the user
    database's older name, and a name no service has.
15. A job registers no name in the session: the same number.
16. A mark put on the clipboard outside a job is not read
    inside one, by the system's reader or by `osascript`,
    and is still there afterwards; the same reader under
    the same profile with every service open returns it. A
    job's write to the clipboard does not land.
17. The two names are the user database: `id -un` and a
    Python lookup of the user and its group say inside a
    job what they say outside it, and `id -Gn` names the
    same groups. Under the same profile with no service
    named, `id -un` prints the number.
18. Each of the thirty-six programs behaves under the
    profile as it does with every service open.
19. The network configuration, the list of keychains and
    the list of disks, each answered with every service
    open, are not answered under the profile.
20. The probe passes, and its trial was refused the
    clipboard. The same trial through a profile that opens
    every service is convicted by the pasteboard's answer:
    with a mark on the clipboard, and with the clipboard
    empty, where the reader ends 0 with nothing to print.
21. A config that names the pasteboard is answered by it:
    the lookup succeeds, the reader returns the mark, the
    window server is still refused, the probe passes and
    records the clipboard as open, and the posture report
    and the audit detail name the service.
22. As root the session's pasteboard answers outside a job
    as it does for the ordinary user, so every clipboard
    test runs there as well.
23. Through the frozen runner, a job is refused the
    clipboard under the config a release's user starts
    with, and is answered under a config that names the
    pasteboard; the posture report says the clipboard is
    refused, and the audit detail names the service the
    config named.
24. The frozen installer prints, among what a job carries
    on that Mac, that the clipboard is refused.

### The session's services: conclusions

Two hosted runs judged the profile that names its services,
both on 2026-11-15, each on both Macs, as the ordinary user
and as root. The first (43767805935, on the landing)
answered ten of the eleven as supposed and one in part. The
second (43768512227, on the commit that took that answer)
is green: the backend's 263 tests as each user, and the
frozen runner's and the frozen installer's own checks.

14. Held. launchd answered a job's lookup of the pasteboard
    1100, and of every other service named above the same,
    where a process in no job was answered 0. For the name
    no service has, a process in no job was answered 1102
    and a job 1100: the sandbox answers before launchd
    looks.
15. Held: 1100 for a name of the job's own, and a name the
    profile carries was not the job's to register either.
16. Held. The reader ended 1 inside a job, and the mark was
    in nothing it or `osascript` printed. The same reader
    with every service open returned it. The mark was still
    on the clipboard afterwards, and after a job's write.
17. Held. The names matched, and `id -Gn` named the same
    groups inside a job as outside: 17 and 14 of them for
    the ordinary user on the two Macs, 23 and 22 for root.
    With no service named, `id -un` printed 501 for the
    ordinary user. For root it printed `root`, a name the
    system's own password file carries, which a job may
    read.
18. Held: 36 of 36 on both Macs as both users. Thirty of
    them work under the profile. The six that do not —
    `git` in both rows, `cc`, `make`, `xcrun` and `java` —
    do not with every service open either. `sqlite3` works
    where the profile is built for it as the job's own
    program, its install readable.
19. Held: each was answered with every service open, and
    ended 1 under the profile.
20. Held. The trial recorded the clipboard as refused. The
    trial through a profile that opens every service was
    convicted by the pasteboard's answer, with a mark on
    the clipboard and with the clipboard empty, where the
    reader ended 0 with nothing printed.
21. Held in part. Under a config that names the pasteboard
    the lookup was answered 0, the window server was still
    refused, the reader ended 0, the probe passed and
    recorded the clipboard as open, and the report and the
    audit detail named the service. The reader did not
    return the mark: it printed nothing, and a job's write
    to the clipboard did not land. The pages say what was
    read, the report says of a named pasteboard that it
    answers a job, and the setting's example names no real
    service. A name the config names does reach launchd:
    for the name no service has, a job was then answered
    1102, as a process in no job is.
22. Held: no clipboard test was skipped as root on either
    Mac.
23. Held. Through the frozen runner the job ended 0 under
    the config a release's user starts with, and 15 under
    the one that names the pasteboard; the report carried
    the line, and the audit detail the name.
24. Held on both Macs.

What the profile leaves a job was read again in both runs:
a job listed between 424 and 469 of the host's processes,
and read from the I/O registry that the Mac's serial number
is there.
