# Windows confinement: the AppContainer backend, specified

Status: design of record, written 2026-11-21 at the
owner's direction, and built the same day
(`runner/guard/windows_confine.py`; tests in
`runner/tests/test_windows_confine.py` and
`runner/tests/test_windows_appcontainer.py`; the field
proof is the project's own Windows rig battery). The
build followed this text closely; where it differs, the
build is what runs and the section "Where the build
differs from this text" says so. Where a question could
only be settled on a real Windows host, this page stated
the supposition first and named the measurement that
settles it, in "Suppositions for the Germany rig" at the
end, and the conclusions the rig returned stand in that
section.

Confinement is the software suite's own, platform by
platform. The protocol documents do not specify it, so
nothing here changes a message, a field or a document
under `docs/ietf`. This page and
`docs/steady/security/windows.md` are where the Windows
AppContainer shape is written down;
`docs/support-matrix.md` carries the claim, and its
Windows rows stand at **Supported** since the owner's
call of 2026-11-21.

## Where the Windows backend stands

The shipped backend is `runner/guard/windows_confine.py`.
Its record, named exactly in every audit and startup
record, is the floor:

```
windows: job_object + restricted_token + low_integrity
```

A job process is created suspended with
`CreateProcessAsUserW` under a restricted token derived
from the runner's own token, with the token's mandatory
integrity level set to Low, and is assigned to a Job
Object carrying a per process memory ceiling of 512 MiB
before it resumes. The module states plainly what that
floor is not: it is not a sandbox in the Linux sense.
There is no filesystem read isolation. A confined job can
still read any path its token can read. Low integrity
stops a job writing to medium or higher integrity objects
outside its workspace, and never stops it reading out.
The module named AppContainer as the future path to
confinement parity on Windows. This page is that path,
specified, and the build of it stands in the module
today.

Two recorded conclusions bind this design and are not
reopened by it.

1. The field test on the Germany rig on 2026-11-10,
   as an unelevated standard user, found the shipped spawn
   working confined there: confined jobs read their staged
   scripts and wrote their work directories in both
   staging shapes, over repeated clean runs.
2. The only hard denial that test produced came from the
   label side of the floor. A staged file itself labelled
   Low was refused by PowerShell under the default
   execution policy, a Low labelled script being treated
   as untrusted. A spawn that left its work directory
   unlabelled read its script and could not write its
   outputs. The trial probe in the shipped module is the
   fix that stands: staging is granted to a group the
   confined token holds, and no staged script is labelled.

AppContainer answers the first limit and must not
recreate the second. Its access check is a discretionary
access control list check, not an integrity label check,
and section "Filesystem access" below states how
that lesson applies differently here.

## Where the build differs from this text

This page was written before the build, and the build
followed it closely. The differences that stand are
these, and in each the build is what runs:

1. The Job Object carries one more limit than the spawn
   section's first step names: beside the per process
   memory ceiling and kill on job close, the flags set
   the job memory limit, so the job as a whole is capped
   at the same 512 MiB. No processor ceiling stands in
   the flags (no time limit, no rate control, no process
   count limit), as no backend at **Supported** sets one.
2. The grant set is wider in two measured directions and
   narrower in one. The spawn grants the ancestors of
   the work directory and of each read path at read and
   execute, because the job's shell must be able to walk
   to the directory it was granted; those ancestor
   entries carry no inheritance, because an inheritable
   entry on an ancestor silently widens into a grant on
   everything under it. The spawn grants the target
   program's own directory on every spawn, because a
   container that cannot read the program's directory
   cannot map its image or the libraries beside it. And
   the spawn grants the container SID read only access
   to the creating process's window station and desktop,
   because programs that initialize against them (the
   USER32 load set; PowerShell and whoami the measured
   cases) die at DLL initialization without it: the job
   still has no desktop to use, and neither mask carries
   a create, write, switch, screen or clipboard right.
3. The verdict is two halves, not one: the trial, and a
   job shape probe that runs the job interpreter's own
   argv shape inside the container. A container that
   works for the trial's interpreter but cannot run the
   job's has not proved the control for the work this
   runner does; the verdict names that, and the floor
   stands.
4. The trial's checks as built are the staged read, the
   work write, the outside read refused, the outside
   write refused, the network refused (a loopback
   attempt), and the token read as an AppContainer
   token, from inside where the staged program reports
   it and otherwise from the parent side. The temp write
   and ceiling allocation stages of section "The probe"
   are not separate trial stages in the build: the spawn
   points `TEMP` and `TMP` at the work directory the
   write check already covers, and the ceiling is
   exercised by the rig battery beside the trial.
5. The profile's display name and description as built
   are both "Homing Pigeon runner", where the lifecycle
   section below says the display name is the container
   name; the build's words stand. And the creation
   outcome is read by name before any SID is derived: a
   failed creation refuses the derivation rather than
   deriving a SID for a profile that does not stand.
6. Two lifecycle pieces are designed here and not built:
   the startup sweep for grants a dead runner left, and
   profile deletion at uninstall. The build revokes a
   job's grants at its end and a failed spawn's grants
   before the failure travels (a leaked grant on an
   interpreter tree breaks the floor's own library
   loads, measured on the rig), and nothing in the
   runner calls `DeleteAppContainerProfile`. Grants
   left standing by a runner that was killed are not
   swept by this build.
7. The choice of shape at job time: the spawn seam falls
   back to the floor spawn if the AppContainer spawn
   itself fails at job time, the process then carrying
   the floor's record, rather than refusing the job. The
   probe still makes the standing choice, and a verdict
   that reads a boundary crossing still refuses outright
   at the gate.

## What the design is for

1. A confined job on Windows can read only what the
   design grants it: its work directory, the staged files
   of its own job, the interpreter it runs and the system
   trees a regular AppContainer may read. A read of
   anything else the runner's account can read is refused.
   That is the read isolation the floor does not have.
2. A confined job has no network at all, as the Linux
   sandbox and the FreeBSD jail and the macOS profile
   already give their jobs. The floor isolates no network.
3. The Job Object ceiling and its suspended creation
   discipline carry over unchanged: a job never runs a
   line before its controls are in place, and the memory
   ceiling is the same 512 MiB per process.
4. On a host where AppContainer cannot engage, the floor
   stands untouched, with its own trial and its own record
   string. No record ever names a control that was not
   applied to that job.
5. A host where neither shape can work confined refuses
   at startup, by name, as the floor already does.

## The controls

Where AppContainer engages, each job's audit record
carries this string and nothing stronger:

```
windows: job_object + appcontainer + no_network
```

The order is fixed: the resource control first, the
identity and filesystem control second, the network
control last, as the FreeBSD record orders its own.

| Name | What it is | When it is named |
|---|---|---|
| `job_object` | The existing Job Object with the per process memory ceiling of 512 MiB and the job memory limit at the same 512 MiB, so the job as a whole is capped, assigned while the process is suspended, with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` as the floor already sets | Always, in both shapes |
| `appcontainer` | The job process runs in an AppContainer whose package SID is derived from the runner's container name, with an empty capability list, at the Low integrity level an AppContainer token carries, reaching the filesystem only through the grants of section "Filesystem access" | Only where the AppContainer trial of section "The probe" passed on that host and that job was spawned through it |
| `no_network` | The container holds no network capability at all: no `internetClient`, no `internetClientServer` and no `privateNetworkClientServer` capability SID is in its token, so it can access no network | Only beside `appcontainer`, and only where the trial read a network refusal from inside |

Two names of the floor are deliberately absent from this
string, and the absence is a claim.

1. `restricted_token` is not named. The AppContainer spawn
   does not create a process under a token the backend
   built with `CreateRestrictedToken`. It creates a
   process with `CreateProcessW` and an attribute list,
   and the system builds the container token. Naming the
   old control for a step that did not happen would be
   the exact drift the floor's own naming rule forbids.
   Whether the container token also holds every property
   of the restricted token is a supposition for the rig,
   stated below, and until it is answered the record
   promises the container, not the restriction list.
2. `low_integrity` is not named separately. Microsoft
   states that AppContainers run with a Low integrity
   level. The level is a property of the container token,
   not a label the backend sets with
   `SetTokenInformation`, so it rides inside the
   `appcontainer` name and is not counted twice.

The record's detail for an AppContainer job says what one
job's launch carried beyond the string: the container
name, that the capability count was zero, the work
directory grant that was made for that job, and the
interpreter prefix grant where one was made. The posture
report names which of the two Windows shapes a host
engages, in the same words as the audit string.

### Less Privileged AppContainer is not used

Microsoft documents a narrower form, Less Privileged
AppContainer, which opts out of the ALL APPLICATION
PACKAGES group and then needs named capabilities for
things a regular AppContainer reaches by default, the
registry read capability and the COM capability being its
examples. An arbitrary job interpreter and the programs a
job is likely to be have not been measured against that
form. The regular form already gives this design its two
goals, read isolation by grant and no network, so the
regular form is the design. The narrower form is future
work and no record names it.

## The container identity

### The name

The container name is one fixed string for the runner:

```
pigeon-home.homing-pigeon.runner
```

The rules Microsoft states for the name, and how this
name meets them:

1. `CreateAppContainerProfile` takes a name of at most 64
   characters fitting the pattern `[-_. A-Za-z0-9]+`. The
   name above is 32 characters and uses only letters, dots
   and one technical hyphen inside an identifier, which
   the pattern allows.
2. Microsoft advises that the string should ideally
   contain the app name as well as the publisher, to
   ensure uniqueness. The name carries the publisher
   `pigeon-home` and the app `homing-pigeon`, with
   `runner` naming the component that holds the jobs.
3. The name is not per job and not per machine. It is per
   runner account, because a profile is per user: the same
   name under a second account is a second profile with,
   by the derivation below, the same SID string. Grants
   are therefore always made by the account that runs the
   jobs, for its own jobs, and section "The profile
   lifecycle" states what that leaves open between jobs.

### The SID

The package SID is derived from the name, never invented
and never stored as a secret:

1. `CreateAppContainerProfile` returns the SID when it
   creates the profile.
2. Where the profile already exists, the call returns
   `HRESULT_FROM_WIN32(ERROR_ALREADY_EXISTS)` and the SID
   is got again with
   `DeriveAppContainerSidFromAppContainerName`, which
   takes the profile name and returns the SID of that
   profile, to be freed with `FreeSid`.
3. The SID is of the form `S-1-15-2-` followed by seven
   numbers. Every grant, every trial check and every audit
   detail in this design names that SID as the principal.
   Access for a container is the intersection of what the
   runner account may do and what the container SID is
   granted, as Microsoft states the dual principal model:
   a grant to the container alone is never wider than the
   account's own access, and the account's access alone
   gives the container nothing.

Deriving the SID is a pure question. It answers the same
on any host and proves nothing about whether a container
can run there. Only the trial of section "The probe"
proves that, and only the trial lets a record name
`appcontainer`.

## Capabilities

A capability is an unforgeable token of authority in the
container's token, named by a capability SID. Microsoft
derives one from a capability name with
`DeriveCapabilitySidsFromName`, which returns a group SID
array and a capability SID array; the launch guidance
wraps it in a helper that keeps the single capability SID
and frees the group side, and marks each kept SID
`SE_GROUP_ENABLED` in the `SECURITY_CAPABILITIES` list.

The well known capabilities Microsoft lists include, in
the `APPX_CAPABILITIES` enumeration and the capability
declarations page:

1. Network: `internetClient` (outgoing Internet),
   `internetClientServer` (outgoing and incoming
   Internet) and `privateNetworkClientServer` (a home or
   work network, incoming and outgoing).
2. Libraries and storage: `documentsLibrary`,
   `picturesLibrary`, `videosLibrary`, `musicLibrary`
   and `removableStorage`.
3. Identity and enterprise: `enterpriseAuthentication`
   and `sharedUserCertificates`.
4. Devices and data a job never needs here, such as
   appointments and contacts, and the device capabilities
   for a camera, a microphone and location that the launch
   guidance uses as examples.

This design grants none of them. The capability list in
every spawn and in the trial is empty, the count is zero,
and that emptiness is the load bearing fact of the whole
backend:

**A container with no network capability has no network
access at all.**

Microsoft states it in one line: without the network
capability, an AppContainer cannot access the network.
That is the AppContainer analogue of the `no_network`
control the other backends name. It needs no firewall
rule, no namespace and no route removal. It also means
there is no network switch in this backend's first shape:
a job that needs the network is not a confined job on
Windows, exactly as a job that needs the network is not
confined by the macOS profile, which names no network
allow rule either. A future capability grant, if the
owner ever directs one, would be a config named list
like the macOS backend's list of session services, would
change the record string by dropping `no_network`, and
is not designed here.

## The spawn

### How it differs from the floor spawn

The floor spawn calls `CreateProcessAsUserW` with a
restricted token handle the backend built itself. The
AppContainer spawn calls `CreateProcessW` with no token
handle at all, and instead hands the creation call a
`STARTUPINFOEX` whose attribute list carries a
`SECURITY_CAPABILITIES` structure. The system builds the
new process's token from the caller's token together
with the package SID and the capability list. Setting
the `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`
attribute is, in Microsoft's words for
`UpdateProcThreadAttribute`, what makes the new process
an AppContainer process.

So for a process this spawn covers, the AppContainer
spawn replaces the token control. It does not compose
with it: there is no documented creation call that takes
both a backend built restricted token and a security
capabilities attribute and promises both in the result.
Microsoft's own launch guidance uses plain
`CreateProcess` with `EXTENDED_STARTUPINFO_PRESENT` for
exactly this launch, and this design follows it and says
so, rather than claiming a composition no page promises.
What does compose, unchanged, is the Job Object, because
assignment is a separate call on the created process
handle and knows nothing of how the token was built.

### The sequence, step by step

One spawn, in order. Every failure refuses the job with
the call that failed and its error, closes every handle
the attempt made, and terminates a created process that
could not be assigned, exactly as the floor's shared
suspended spawn helper already behaves. The backend
keeps that one helper shape so the two Windows spawns
cannot drift apart on the order that matters.

1. The Job Object is created with its limits, as the
   floor does: the per process memory ceiling, the job
   memory limit at the same value, and
   `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
2. The container SID stands ready: derived at startup by
   the probe, and derived again here if the spawn runs
   first, with `CreateAppContainerProfile` and the
   already exists fallback of section "The container
   identity". A spawn never creates a second profile.
3. The grants of section "Filesystem access" are made for
   this job: the work directory, the staged tree of this
   job and, where the rule there requires it, the
   interpreter prefix. A grant that fails refuses the
   job before any process exists.
4. The capability list is built: empty. The
   `SECURITY_CAPABILITIES` structure is filled with the
   package SID, a capability count of zero, a null
   capability pointer and a reserved field of zero.
5. The attribute list is sized and built the way
   Microsoft's guidance builds it: a first
   `InitializeProcThreadAttributeList` call with a null
   list answers `ERROR_INSUFFICIENT_BUFFER` and gives the
   size; the storage is allocated; a second call
   initialises it for one attribute; and
   `UpdateProcThreadAttribute` sets
   `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES` to the
   structure of step 4.
6. The standard handles are prepared as the floor
   prepares them: anonymous pipes for output and error,
   the null device for input, the read ends kept
   uninheritable. Anonymous pipes are unnamed objects and
   travel by handle inheritance alone; section "Named
   objects and the session" states the rest.
7. The process is created suspended:
   `CreateProcessW` with `CREATE_SUSPENDED`,
   `EXTENDED_STARTUPINFO_PRESENT` and, where an
   environment is handed in, `CREATE_UNICODE_ENVIRONMENT`,
   with the `STARTUPINFOEX` of step 5 as the startup
   information. The environment is the job's environment
   with `TEMP` and `TMP` set as section "Filesystem
   access" requires.
8. The suspended process is assigned to the Job Object
   with `AssignProcessToJobObject`. This is the existing
   no race discipline, carried over word for word: the
   process has not run a line when the assignment is
   made, so it cannot have exited before it, the failure
   the floor's own record names. A failed assignment
   terminates the process and refuses the job.
9. The main thread is resumed. Only now has the job run.
10. The attribute list is deleted with
    `DeleteProcThreadAttributeList`, the SID and grant
    bookkeeping are released in the process object's
    close, and the returned process object carries
    `confinement_status` as the new record string. Its
    close closes the Job Object last, as the floor's
    does, so anything the job left inside the job ends
    with the handle.

A spawn that cannot complete any step raises. There is
no step at which a job of this spawn runs outside the
container and is confined later, and no fallback inside
the spawn to the floor spawn: the choice of shape is
made once, by the probe, before the job is accepted.

## Filesystem access

An AppContainer reaches only what its SID is granted.
Microsoft states the model in two parts: the permitted
access is the intersection of the access granted to the
user and group SIDs and the access granted to the
AppContainer SIDs, and an AppContainer must be explicitly
granted access to a given resource. The system trees are
the one standing exception the launch guidance names: a
regular AppContainer is granted access to certain system
files and directories and common registry keys by
default. Everything else in this design is a grant the
backend makes, names in the audit detail, and removes.

### The grant set

Grants are access allowed entries added to the existing
discretionary access control list of a path, naming the
package SID as trustee. They are added, never written
over the path's own list. The field test's trial could replace
the list of its throwaway tree because the tree was its
own and about to be removed; a job's work directory and
an interpreter prefix are the operator's trees and keep
every entry they had.

| Path | Grant to the package SID | Inheritance | Removed |
|---|---|---|---|
| The job's work directory | Read, write and execute | To objects and containers inside it, so files the job stages inside it carry the grant as they are created | At the job's end, by the process object's close |
| The staged tree of the job, where it stands outside the work directory | Read and execute | To objects and containers inside it | At the job's end |
| The interpreter's install prefix, where it stands outside the system trees and outside any path already granted | Read and execute | To objects and containers inside it | At the job's end |
| The ancestors of the work directory and of each read path (as built) | Read and execute | None: the entry stands on the ancestor alone, so it cannot widen into the ancestor's other children | At the job's end |
| The target program's own directory (as built) | Read and execute | To objects and containers inside it | At the job's end |
| The container's own profile folders | None: the system ACLs them for the container when the profile is created | Not applicable | Never by the backend; see the profile lifecycle |

The session objects stand beside the path grants, as
built: the creating process's window station at read
attributes and enumerate desktops, and its desktop at
read objects, granted and revoked in the same recorded
shape, so a program whose load set initializes against
them can start. Neither mask carries a create, write,
switch, screen or clipboard right. Section "Named
objects and the session" states what this does not give
the job.

Three rules bound the set.

1. The interpreter rule is the Linux sandbox's and the
   FreeBSD jail's rule, restated for grants: an
   interpreter under the system trees needs nothing; one
   that lives elsewhere gets its install prefix granted
   read and execute at the same path, and the grant is
   written into the audit record's detail. Never a home
   directory and never a tree shallower than two
   components: an interpreter no grant can show, or one
   under the profile folders of another container,
   refuses the job.
2. No grant is ever made on a home directory, on the
   runner's install directory, on the directory holding
   `config.json`, or on any path a job is only expected
   to be refused. The secret's directory in particular
   gets no grant: under the floor a job could read it if
   the account could; under this backend it cannot, and
   that difference is the point of the backend.
3. A grant removal that fails is recorded in the audit
   detail for that job and leaves the entry for the
   posture report to name. It never fails the job that
   already ran. The sweep of section "The profile
   lifecycle" retries removals a dead runner left.

### Staged files and the field test's lesson

That lesson applies differently here, in two ways.

1. No staged file is labelled. The floor labels its work
   directory Low so a Low process may write it, and the
   field test found a Low labelled staged script refused
   by PowerShell as untrusted. This backend sets no
   integrity label on the work directory, on the staged
   tree or on any file in either. The container token is
   Low by its own construction and the write it needs is
   given by the grant, not by a label. Whether PowerShell
   reads a granted and unlabelled staged script cleanly
   is supposition 3 for the rig.
2. What the staged tree needs is a grant, not the trial's
   group trick. The floor's trial grants `BUILTIN\Users`
   because its confined token holds that group enabled
   and holds neither Administrators nor SYSTEM. A
   container token is checked against its package SID,
   so the trial and the job grant the package SID itself,
   by name, and the verdict no longer depends on which
   groups a host's staging happens to name.

### Temporary files

Microsoft's launch guidance states that a container's
`TEMP` and `TMP` are rerouted to a directory under the
profile, in its example under the profile's `AC` folder
as `Temp`, and its `LOCALAPPDATA` likewise points into
the profile. A job handed the runner's own environment
unchanged would carry `TEMP` values naming trees it has
no grant on, and its temporary writes would be refused
for a reason that is the backend's fault, not the host's.
The spawn therefore sets `TEMP` and `TMP` in the child's
environment to the work directory, the one tree the job
may always write, and leaves the rest of the environment
as the job's policy shaped it. The profile's own temp
tree stays available to programs that ask the system for
the container's folders rather than reading the
environment.

## Named objects and the session

A container lives in its own named object namespace.
Microsoft's page on sharing named objects states the
shape: by default a packaged application can only access
named objects it has created; an object created outside
can be shared with it only by granting its SID in the
object's access control list at creation, and a caller
outside qualifies the object's name with the container's
named object path, which `GetAppContainerNamedObjectPath`
returns for a token and a container SID.

For this runner the consequences are three, and all are
stated rather than discovered per job.

1. The runner talks to its jobs through anonymous pipes
   and files in the work directory, never through a named
   object, so the ordinary job needs no named object
   grant at all. That is a property of the existing spawn
   seams and this design keeps it as a rule: no backend
   seam may move job control onto a named pipe or a named
   mapping without revisiting this section.
2. A job that itself creates named objects creates them
   inside its own namespace, where no other job and no
   outside process finds them by their bare name. Jobs
   that expect to share a named object with the host, or
   with each other, will not work confined in this shape,
   and the trial does not pretend otherwise.
3. A job has no desktop of the session to use, and no
   other application's processes or windows to reach:
   Microsoft lists processes and windows belonging to
   other applications among what an AppContainer is
   isolated from. The build does grant the container SID
   read only access to the creating process's window
   station and desktop, at the masks section "Filesystem
   access" records, because a program whose load set
   initializes against them dies at DLL initialization
   without it (the Lane 7 measurement in the backend's
   header); that grant lets a program start, and gives
   it no window, no clipboard and no screen to read. A
   job that needs a desktop is not a job for this
   backend.

## The profile lifecycle

`CreateAppContainerProfile` creates a per user, per app
profile: folders and registry storage that are per user
and per app, with access control lists that keep other
users and other apps out, reached through
`SHGetKnownFolderPath` and, for the local app data
folder, `GetAppContainerFolderPath`. In Microsoft's
example layout the folders stand under the user's
`AppData\Local\Packages` tree, in a folder named for the
container.

The lifecycle this design runs is:

1. **Create once, at the probe.** The first probe on a
   host creates the profile for the account the runner
   runs as, with an empty capability list, a display name
   of "Homing Pigeon runner" and the same words as its
   description, as built. `S_OK` means the store was created.
   `HRESULT_FROM_WIN32(ERROR_ALREADY_EXISTS)` is the
   ordinary second run answer and is success by the
   derivation path. `E_ACCESSDENIED` is a named refusal:
   the account may not create its own profile there.
2. **Never create per job.** Jobs share the one profile
   of their runner account. What separates one job from
   the next is the grant set, made and removed per job,
   not a new identity per job. The cost and the failure
   surface of profile creation are paid once, at startup,
   where a refusal can still refuse the start.
3. **Keep while the runner is installed.** The profile is
   the container's own scratch state, as a browser profile
   is an application's. Jobs are not promised that
   anything they write into the profile folders survives
   them, and the runner keeps nothing of its own there:
   its state stays in its install and base directories,
   which the container has no grant on.
4. **Delete only at uninstall, and only by name.**
   `DeleteAppContainerProfile` deletes the profile of the
   current user for the name given. Microsoft notes that
   deleting a profile that does not exist returns success,
   that all file handles in the profile storage should be
   closed first or the removal may be incomplete, and
   that where the call fails the profile's state is
   undetermined and the call should be made again. The
   uninstall path, not any job path and not the runner's
   exit path, is the one place that calls it. A runner
   that merely stops leaves the profile standing, as it
   leaves its install directory standing. Not built: no
   path in this build calls it, and no uninstall path in
   the runner deletes the profile today.
5. **A sweep for grants, not for profiles.** At startup,
   before the probe, the backend removes package SID
   entries its own audit log records as left by a runner
   that died before its close could remove them, on the
   paths those records name. It deletes no profile and
   touches no path the records do not name. Not built:
   this build removes a job's grants at the job's end
   and a failed spawn's grants at the failure, and runs
   no startup sweep; the sweep above is the design for
   the lane that builds it.

### What an unelevated standard user can and cannot do

The Germany rig field shape is an unelevated standard
user, and the design is built for exactly that shape.

A standard user, for its own account, can:

1. Create its own AppContainer profile. The documented
   denial is `E_ACCESSDENIED`, a host answer, not a
   class answer: the probe, not an assumption, is what
   the gate consults, as the floor already holds for its
   own token creation, which likewise needs no
   administrator rights.
2. Derive the container SID from the name, size and build
   an attribute list, and create a process in the
   container with `CreateProcessW`.
3. Grant its package SID access to files and directories
   it owns, which covers the work directory and the
   staged trees the runner itself stages under its own
   account.
4. Assign that process to a Job Object it created, as
   the floor already does unelevated.

A standard user cannot:

1. Create or delete a profile for another user. Microsoft
   states that creating a profile on behalf of another
   user requires impersonating that user, and deleting
   one likewise deletes the profile for the current user
   only. A runner installed to run as SYSTEM or as a
   dedicated service account therefore gets its profile
   under that account, made by a probe running as that
   account, and an operator running the probe as
   themselves proves nothing about that install. The
   probe must run in the runner's own account context,
   which the startup gate already is.
2. Grant access to a path it does not own and may not
   write the access control list of. A staged tree or an
   interpreter owned by another account and not already
   readable through a grant is a named refusal, not a
   prompt for elevation.
3. Call `DeleteAppContainerProfile` from inside a
   container: Microsoft names that answer
   `HRESULT_FROM_WIN32(ERROR_NOT_SUPPORTED)`. No cleanup
   step runs inside a job.

## Hosts: versions, editions and the probe shape

Every API this design uses carries the same documented
floor in Microsoft's requirements tables:

1. `CreateAppContainerProfile`,
   `DeriveAppContainerSidFromAppContainerName` and
   `DeleteAppContainerProfile`: minimum supported client
   Windows 8, desktop apps only; minimum supported server
   Windows Server 2012, desktop apps only; header
   `userenv.h`, library `Userenv.lib`, DLL `Userenv.dll`.
2. `UpdateProcThreadAttribute` for
   `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`:
   supported in Windows 8 and newer and Windows Server
   2012 and newer.
3. `DeriveCapabilitySidsFromName` is older still and is
   used here only if a future shape derives a capability;
   the empty list needs no derivation at all.

So the version gate is Windows 8 or Windows Server 2012
or newer, on a desktop app host. The Germany rig, at
Windows Server 2022, stands well above it, as does every
host in the support matrix's Windows rows.

What Microsoft's pages do not state is any edition line:
no page relied on here separates Home from Pro from
Enterprise, or a server edition from another, or a
desktop experience install from a core install beyond
the words desktop apps only. That silence is recorded as
a genuinely unanswered question at the end of this page.
The design therefore makes no edition promise and lets
the probe decide, host by host, exactly as the floor
lets its probe decide whether its token calls work.

A host that cannot engage looks like this at probe time,
and each shape is a named answer, never a silent
fallback inside a job:

1. The version is below the floor, or `Userenv.dll` does
   not carry the profile calls: the probe names the
   missing call.
2. Profile creation answers `E_ACCESSDENIED`: the probe
   names the account and the denial.
3. Profile creation answers a failure that is neither
   success nor already exists: the probe names the
   HRESULT.
4. The attribute list or the creation call fails: the
   probe names the call and its error.
5. The trial process runs but does not read as confined:
   the probe names which boundary the trial crossed, from
   the list in section "The probe". A trial that runs
   unconfined and is believed is the one failure this
   design treats as worse than a refusal.

Where any of those five stands, the AppContainer shape
does not engage on that host. The floor then stands or
falls by its own probe, and the startup record says
which shape engaged, so a reader of the log never has to
guess whether a quiet host fell back or was refused.

## The probe

At `enforce` the startup gate asks the backend, and a
job's own gate asks it again; the verdict is kept for
the life of the process, as the floor keeps its trial
verdict. The AppContainer probe runs before the floor's
verdict is consulted for the shape decision, and it is a
trial, not a creation check, for the field test's reason: a host
passed the floor's creation probe and failed every job,
so creation alone has never proved a confined process
can work here.

1. The container name derives a SID, and the profile
   stands: created, or already there.
2. `GetAppContainerFolderPath` answers a path for that
   SID. A profile the system cannot show a folder for is
   a named failure, since a container with nowhere of
   its own to stand is not a container a job can run in.
3. The grants are made on a staged trial tree of the
   trial's own, staged exactly as the floor's trial
   stages: made with `os.makedirs` at the default mode in
   a fresh random named directory under the temp tree,
   never `tempfile.mkdtemp`, for the reason the field
   test's addendum records. The grants name the
   package SID.
4. A trial process is spawned through the full spawn of
   this design, in that tree, running a staged program
   that must, from inside the container:
   1. read its staged data file and say so;
   2. write its work directory and say so;
   3. write its temporary directory, through the
      environment the spawn set, and say so;
   4. be refused a read of a file beside the staged tree
      that the runner's account can read, a file the
      trial stages with no grant to the package SID;
   5. be refused a write beside its work directory;
   6. be refused a network connection, to an address the
      trial names on the host itself and to one outside
      it, with no capability in its token;
   7. say which integrity level and which package SID its
      own token carries, so the trial reads the container
      from inside and not from the spawn's say so;
   8. allocate past the Job Object ceiling and be
      refused, as the floor's rig battery already reads
      the ceiling.
5. The trial's grants are removed and its tree is
   removed, pass or fail.

As built, the trial runs the staged read, the work
write, the outside read and write refusals and the
network refusal, and reads the token as an AppContainer
token; the temp write and the ceiling allocation are not
separate trial stages in the build, for the reasons in
"Where the build differs from this text", and the
verdict adds the job shape probe that section names.

Each stage that fails is named, in the floor's trial
style, so the startup gate refuses or falls back with
words that say what happened: the profile stage, the
folder stage, the grant stage, the spawn itself, the
staged read, the work write, the temp write, the outside
read that was not refused, the outside write that was
not refused, the network connection that was not
refused, the token the trial read, or the ceiling. A
spawn that confines nothing does not pass: the trial's
own program, run with no container, reads the outside
file, writes beside its work directory and reaches the
network, and is convicted by each of those.

The failure shapes decide the shape decision of section
"What the design is for", point 4, as follows. A failure
in stages 1 to 3 or in the spawn is a host that cannot
engage this backend: the floor is asked, and the record
says the AppContainer shape did not engage and why. A
failure in stage 4, where a spawned container crossed a
boundary the trial reads from inside, is different in
kind: something on that host presents as a container and
does not hold, and the startup gate refuses outright
rather than fall back, naming the crossed boundary,
until the rig has read that shape and this page is
amended to say otherwise. That asymmetry is deliberate
and is the one conservative choice in this design: a
missing mechanism falls back, a lying mechanism refuses.

The posture report asks the same probe and says what a
job carries here: which shape engaged, the container
name, that the capability count is zero, and, where the
floor engaged instead, the AppContainer reason beside
the floor's own string.

## The mode a fresh install states

Nothing in this design changes the Windows seed rule of
`docs/steady/security/windows.md`. A fresh Windows
install writes `confinement` at `audit`, stated in the
file, because the seed is written without running a
backend probe on that machine. The operator steps the
mode up to `enforce` deliberately, and the startup gate
then asks the probe of this design on that machine. A
future seed that asks the machine, as the FreeBSD and
macOS seeds ask theirs, is a separate change with its
own design, and would ask this probe exactly as written
here.

## Configuration

This backend reads no new configuration in its first
shape. The capability list is empty by design and is not
a setting; the container name is fixed and is not a
setting; the memory ceiling is the floor's existing
constant. A setting the operator could use to widen the
container, a capability name or an extra grant path, is
a widening of a security boundary by a config line, and
this design adds none. The `windows` block under
`security.confinement`, if a later shape earns one, is
checked on every platform as the other backends' blocks
are, so a config is right or wrong the same way wherever
it is read.

## Beside the other backends

| | Linux (bwrap) | FreeBSD (jail) | macOS (Seatbelt) | Windows floor | Windows (this design) |
|---|---|---|---|---|---|
| What a job reads | A root of its own, system trees read only | A root of its own, system trees read only | What the profile names | Any path its token can read | Only what the package SID is granted, plus the system trees a regular container reads by default |
| Trees that take a write | The work mount and a private temp tree | The work mount and a bounded temp tree | The work directory | The work directory, by its Low label | The work directory, by grant; the profile folders, by the system |
| Network | A loopback of its own | None by default | None | Not isolated | None, by an empty capability list |
| Host's processes | Visible | Not visible | Visible, not signalled | Visible | Not reachable, per Microsoft's isolation statement |
| Memory ceiling, per process | None | 512 MiB, not the job's to raise | 512 MiB above a bare process's map | 512 MiB, by Job Object | 512 MiB per process and for the job as a whole, by the same Job Object |
| Needs | An unprivileged user namespace | Root | Nothing beyond the runner's user | No administrator rights for its token calls | No administrator rights for its own account's profile, spawn or grants |
| Startup probe | Starts the sandbox once | Builds a jail and reads the boundary from inside | Runs a trial under the full controls | A trial that reads a staged file and writes its work directory | A trial that reads the boundary from inside the container, the network refusal included |

## What it does not do

1. It does not separate two jobs of the same runner
   account from each other by identity. They share one
   package SID. What separates them is the grant set of
   the moment: a job can read another running job's work
   directory only while both grants stand, and both do
   stand while both jobs run. An operator who needs jobs
   mutually blind runs one runner per trust class, as
   they already do per account. A per job container name
   would close this and is recorded as an open question
   for the rig's cost measurement, supposition 9.
2. It does not hide the host's path layout. A job learns
   that a path exists by the answer it gets, as under
   the macOS profile metadata is not the boundary, the
   grant is.
3. It does not give a job a loopback. No capability means
   no network, and Microsoft's pages do not offer a
   loopback only capability among the well known network
   capabilities: the three are Internet out, Internet
   both ways and private network both ways. A job that
   talks to itself over 127.0.0.1 does not work in this
   shape, where the Linux sandbox's loopback does work.
   Supposition 5 asks the rig to confirm the loopback is
   in fact refused, since the pages state the network
   rule generally and do not name loopback in it.
4. It is not Less Privileged AppContainer, and it does
   not claim that form's narrower default surface.
5. It does not bound the profile folders' growth. A job
   can write its container's profile temp tree without a
   size bound in this design, as the floor leaves the
   work directory unbounded. The work directory grant is
   where job outputs belong; the profile tree is scratch
   the job is not promised.
6. It does not make a job's named objects, registry
   state or profile state private from the runner's own
   account. The account owns the profile and the grants;
   the boundary faces outward from the job, as every
   backend's boundary here faces outward from the job
   toward the host, not toward the runner.
7. It does not engage on a host below Windows 8 or
   Windows Server 2012, and it does not engage from
   inside a container: profile creation and deletion
   from within one are not the runner's shape, and the
   deletion page names the not supported answer a
   container gets.

## Sources

Microsoft's own documentation only, all on Microsoft
Learn, read 2026-11-21.

1. Launch an AppContainer. The overview, the dual
   principal model, the Low integrity statement, the
   capability construction with `DeriveCapabilitySidsFromName`,
   the profile creation pattern with the already exists
   fallback, the rerouted `LOCALAPPDATA`, `TEMP` and
   `TMP`, the `SECURITY_CAPABILITIES` attribute list
   construction and the `CreateProcess` launch with
   `EXTENDED_STARTUPINFO_PRESENT`, and the Less
   Privileged AppContainer opt out attribute.
   https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer
2. DeriveAppContainerSidFromAppContainerName function
   (userenv.h). The SID of the specified profile, freed
   with `FreeSid`; Windows 8 and Windows Server 2012.
   https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deriveappcontainersidfromappcontainername
3. CreateAppContainerProfile function (userenv.h). A per
   user, per app profile; the name's length and pattern
   and the publisher advice; `S_OK`, `E_ACCESSDENIED` and
   the already exists HRESULT; impersonation for another
   user's profile.
   https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile
4. DeleteAppContainerProfile function (userenv.h).
   Deleting a profile that does not exist returns
   success; close handles first; a failed deletion leaves
   the state undetermined and should be retried; the not
   supported answer from within a container.
   https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile
5. DeriveCapabilitySidsFromName function
   (securitybaseapi.h). The group SID and capability SID
   arrays a capability name derives, and the caller's
   duty to free them.
   https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-derivecapabilitysidsfromname
6. UpdateProcThreadAttribute function
   (processthreadsapi.h).
   `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES` takes a
   `SECURITY_CAPABILITIES` structure and, if the attribute
   is set, the new process will be created as an
   AppContainer process; Windows 8 and Windows Server
   2012 and newer.
   https://learn.Microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute
7. APPX_CAPABILITIES enumeration (appxpackaging.h). The
   well known capability list this page's capability
   section rests on, and the rule that a capability not
   declared is no access to that capability.
   https://learn.microsoft.com/en-us/windows/win32/api/appxpackaging/ne-appxpackaging-appx_capabilities
8. Sharing named objects, UWP applications. A packaged
   application by default accesses only named objects it
   created; sharing one in takes a grant to its SID at
   creation and a qualified name at opening, with
   `GetAppContainerNamedObjectPath` giving the path.
   https://learn.microsoft.com/en-us/windows/uwp/communication/sharing-named-objects

## Suppositions for the Germany rig

Recorded 2026-11-21, before any AppContainer code in this
project has run anywhere. Each supposition states what
the Germany rig is expected to answer, as the unelevated
standard user of the 2026-11-10 field test unless a supposition
says otherwise, and the measurement that settles it. The
implementation lane builds the trial of section "The
probe" first, so most of these are answered by that trial
and by the rig battery beside it, and the conclusions are
written into this page in the open when they land, as
the sibling designs write theirs.

1. **Profile and spawn, unelevated.** Supposition: an
   unelevated standard user creates the profile for the
   container name above, or answers already exists, and
   spawns a process in the container, on the Germany rig.
   Measurement: the probe, run as that user, reaches its
   trial stage with no `E_ACCESSDENIED` at any stage.
2. **The token the system builds.** Supposition: the
   container token holds no privilege the floor's
   restricted token would have stripped, and its enabled
   groups give it no path the grant set did not give.
   Measurement: a trial process inside the container
   prints its own token's privileges, groups, integrity
   level and package SID, and the print is compared line
   by line with the floor token's print on the same rig.
   This settles what the absence of `restricted_token`
   from the record string costs, if anything.
3. **PowerShell and the staged script.** Supposition: a
   PowerShell `-File` job in the container reads and runs
   a staged script that carries a package SID read and
   execute grant and no integrity label, under the
   default execution policy, where the field test's Low
   labelled script was refused as not digitally signed.
   Measurement: the field test's staging shapes, both of them,
   run through the AppContainer spawn on the rig, and the
   exit codes and error text are compared with the 2026
   record.
4. **Pipes and the suspended assignment.** Supposition:
   anonymous pipe handles are inherited by a container
   process created suspended exactly as by the floor's
   spawns, its output is pumped whole, and
   `AssignProcessToJobObject` on the suspended process
   succeeds, with the 512 MiB ceiling then refusing a 700
   MiB allocation inside the container. Measurement: the
   floor's own rig battery steps for output and for the
   ceiling, run through the new spawn.
5. **No network means no loopback.** Supposition: with an
   empty capability list, a process in the container
   reaches neither an outside address nor a listener on
   the host's own 127.0.0.1, and a listener it opens
   itself is reached by nothing outside the container.
   Measurement: connection attempts from inside the trial
   to both, and an attempt from the host into a trial
   listener, each named pass or refusal.
6. **The interpreter in a profile.** Supposition: the
   Python the rig's jobs run stands under the system
   trees or under a prefix the grant rule can show, and
   runs in the container with no grant beyond the rule.
   Measurement: the trial program is the rig's own Python
   at its installed path, spawned confined, and any read
   refusal names the path that needs the prefix grant.
7. **The already exists path.** Supposition: a second
   runner start on the same account takes the already
   exists answer, derives the identical SID string, and
   passes the same trial, with no profile state carried
   between the runs changing any answer. Measurement: two
   probe runs in a row on the rig, SID strings and trial
   verdicts compared.
8. **Grant removal restores the boundary.** Supposition:
   when a job ends and its work directory grant is
   removed, a later container process with no grant on
   that directory is refused it, and the directory's
   access control list is otherwise the list it had
   before the job. Measurement: the list is read before
   a job, after its grant, and after its removal, and a
   second trial with no grant attempts the read.
9. **One identity, two jobs.** Supposition: profile
   creation is cheap enough to pay per runner start and
   far too stateful to pay per job, and two jobs running
   at once under the one package SID can in fact read
   each other's granted work directories while both
   grants stand, as section "What it does not do" states.
   Measurement: two confined jobs at once on the rig,
   each attempting the other's work directory, and the
   timing of one profile creation for the cost side.
   If the cross read surprises the owner, the per
   job container name is the amendment this measurement
   feeds.
10. **The SYSTEM account shape.** Supposition: a runner
    running as SYSTEM, the install default that
    `docs/steady/security/windows.md` describes, gets a
    profile under the SYSTEM account and passes the same
    trial there, with its grants made as SYSTEM on the
    job trees. Measurement: the probe run in that account
    context on the rig, beside supposition 1's run as the
    standard user. A failure here does not block the
    standard user shape; it bounds which installs may
    name the new string, and the posture report must say
    which account's shape engaged.
11. **Cleanup after a dead runner.** Supposition: a
    runner killed with a job in flight leaves its grants
    standing, and the next start's sweep removes exactly
    those entries and no others. Measurement: the rig
    kills a runner mid job, reads the lists, restarts,
    and reads them again.

## Conclusions from the rig (2026-11-21)

Written when this page landed, from the implementation
lanes' records in the backend's header and the rig
battery's runs of that day. Each supposition above is
answered as it stands, settled or not:

1. Settled for the account the rig runs as: the profile
   creates (or answers already exists), the SID derives
   and the trial passes, in the rig's Administrator
   context, across the day's batteries. The unelevated
   standard user shape is not separately measured for
   this control; the probe decides per host, as designed.
2. Settled in the part the record needs: the trial reads
   the spawned process's token as an AppContainer token
   (its own report from inside where the program gives
   one, the parent's `TokenIsAppContainer` answer
   otherwise), so no record names the container for a
   process that is not in one. The line by line privilege
   comparison against the floor token was not run as a
   separate measurement.
3. Settled: PowerShell runs contained, in the
   interactive shape once the session grants stood (the
   Lane 7 measurement) and in the job's own detached
   shape once the ancestor grants stood (the Lane 8
   measurement); the verdict requires the job shape.
4. Settled by the battery: output is pumped whole, and
   the ceiling refuses the battery's oversize allocation
   at the shape that engaged.
5. Settled in its loopback half: the trial's network
   check is a loopback attempt, and it is refused on
   every pass. An outside address from inside the trial,
   and a host attempt into a trial listener, were not
   run as separate measurements.
6. Settled, and it changed the build: the rig's
   interpreter tree is not reachable by default, so the
   spawn grants the target program's own directory (the
   Lane 6 re run's measurement).
7. Settled: repeat starts take the already exists answer
   and derive the same SID, and the derivation now reads
   the creation outcome by name first (the Lane 6 fix).
8. The revocation half is built and pinned (at job end,
   and at a failed spawn before the failure travels);
   the before and after access list comparison on the
   rig was not run as a separate measurement.
9. Not separately measured: two jobs at once, and the
   profile creation cost. The one identity shape stands
   as designed, and "What it does not do" states the
   cross read position.
10. Not separately measured: the rig's runs are the
    Administrator account's. A runner running as SYSTEM
    gets its profile under that account by the same
    probe, and no record here claims its trial.
11. Not built: no startup sweep stands in this build
    (see "Where the build differs from this text"). The
    measured half is the failed spawn's immediate
    revocation.

## What Microsoft's documentation left unanswered

Stated plainly, so the build does not invent answers.

1. **Composition of the two token shapes.** No page
   relied on here states whether a process created with
   `CreateProcessAsUserW` under a backend built
   restricted token and with a security capabilities
   attribute carries both, or which the system honours.
   This design does not attempt the composition, and
   supposition 2 measures what the documented spawn's
   token in fact holds.
2. **Editions.** No page relied on here separates
   editions, or a server core install from a desktop
   experience install, beyond the words desktop apps
   only. The probe is the only edition test this design
   trusts.
3. **Loopback.** The network statement is general: no
   network capability, no network access. No page relied
   on here names loopback inside that rule. Supposition
   5 measures it rather than assume it in either
   direction.
4. **A non mutating profile existence check.** The
   documented pattern is to call
   `CreateAppContainerProfile` and read the already
   exists answer. No page relied on here offers a call
   that only asks whether a profile stands. The probe
   therefore treats creation as its existence check and
   pays that cost once per start.
5. **The standing system grants, enumerated.** The launch
   guidance says a regular AppContainer is granted
   access to certain system files and directories and
   common registry keys, and does not enumerate them in
   the pages relied on here. Which interpreter paths
   stand inside that set on a given host is therefore a
   rig measurement, supposition 6, and never a list this
   page asserts.
6. **Cost of profile creation.** No page relied on here
   states a time, a size or a quota for a profile. The
   per start, never per job, lifecycle rests on
   supposition 9's measurement, not on a documented
   figure.
