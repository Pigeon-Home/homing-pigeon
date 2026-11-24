#!/usr/bin/env python3
"""Windows containment: Job Objects, and the confinement backend.

No external dependencies. Two seams use this module:

- job_user (Phase 1): a Job Object with a per-process memory
  ceiling. The status string for that control alone is
  STATUS_JOB_OBJECT. The assignment is made at creation,
  not after the start: spawn_job_object_process creates the
  process suspended through CreateProcessW (the plain
  creation call -- no restricted token, no integrity
  label; those are confinement's controls and no record of
  this spawn names them), assigns the Job Object, and only
  then resumes the thread. A post-start assignment races
  the child: a job that finishes in milliseconds can have
  exited before the assignment reaches it, and
  AssignProcessToJobObject then fails with error 5 for a
  job whose output is already complete (Q168). A suspended
  creation cannot lose that race, because the process has
  not run a line when the assignment is made. The
  post-start assignment (apply_windows_containment) stands
  for a process that did not come through a spawn seam.

- confinement (Phase 2): the controls named by STATUS_CONFINEMENT
  -- "windows: job_object + restricted_token + low_integrity".
  A job process is created suspended with CreateProcessAsUserW
  under a restricted token derived from the runner's own token
  (CreateRestrictedToken with DISABLE_MAX_PRIVILEGE, which strips
  every privilege except SeChangeNotify, and the Administrators
  group disabled), with the token's mandatory integrity level set
  to Low, and is assigned to the Job Object (the same memory
  ceiling) before it is resumed. There is no race in which the
  job runs unconfined: the process does not execute a line until
  every control is in place.

What this is NOT, stated plainly wherever it is recorded: it is
not a sandbox in the Linux sense. There is no filesystem
namespace isolation: a confined job can still READ any path its
token can read. Low integrity stops the job writing to medium-
or higher-integrity objects outside its workspace (the workspace
directory is labelled Low before spawn so the job can write its
own outputs); it does not hide the filesystem. AppContainer
remains the future path to confinement parity on Windows.

Supposition for Q134, recorded before the field test that
settles it (an unelevated standard user on the Germany rig, a
throwaway account with its temp tree under its own profile --
the hosted CI runner's shape): the shipped spawn, engaged
there, reproduces the CI failure -- a confined PowerShell -File
job exits nonzero reporting the staged script does not exist,
while the same argv unconfined exits 0 -- even though the
creation probe above passes on that host. The isolation runs
spawn variants down the same creation path: the restricted
token at the caller's own integrity level, the caller's token
at Low, and the shipped token with the staged file itself
labelled Low. My lean, stated so the measurement can prove it
wrong: the denial is the restricted token's side of the pair,
not the label's -- integrity policy alone allows a Low process
to read up (only write-up is blocked by the default policy),
so a full token at Low should still read the staged file,
while the restricted token should fail at either integrity.
Whatever the isolation shows, the confinement probe becomes a
trial: it will spawn a confined process that reads a staged
file and writes its work directory, and name the failure, so a
host that cannot work confined refuses at startup instead of
failing every job. Conclusions from the field test are
recorded with the answer to Q134.

Conclusions, from that field test (2026-11-10, the Germany
rig, a throwaway standard user at medium integrity with its
temp tree under its own profile): the shipped spawn did NOT
reproduce the CI denial there -- confined jobs read their
staged scripts and wrote their work directories, in both
staging shapes (the script outside the work directory, and
the script inside the work directory the spawn labels Low),
over repeated clean runs. The isolation ran the other way
from the lean: the restricted token read at the caller's
integrity and at Low alike, and the only hard denial the
test produced came from the label's side -- the staged file
itself labelled Low was refused by PowerShell under the
default execution policy (a Low-labelled script is treated
as untrusted: "not digitally signed"), while a spawn variant
that left the work directory unlabelled read its script but
could not write its outputs, the label doing its documented
work. So no token-recipe change and no script labelling:
the trial probe below is the fix, making the startup gate
honest on hosts whose confined processes cannot work,
whatever their cause. The CI host's own cause stays open;
the trial names it there at startup.

The trial's staging has its own condition, found by the
question's second-seat re-test -- the rig battery, running
the backend as an elevated administrator, after the
unelevated field test above had passed: the trial first
staged its tree with tempfile.mkdtemp, whose directory
carries a DACL naming only SYSTEM, Administrators and OWNER
RIGHTS. The confined token disables Administrators, is not
SYSTEM, and OWNER RIGHTS resolves to the disabled owner
SID, so on an elevated host the confined process was
refused at the staged read and the startup gate refused a
host that works. The trial now stages with os.makedirs at
the default mode and grants BUILTIN\\Users -- a group the
confined token carries enabled -- read+execute on the
staged tree explicitly, so the verdict does not depend on
any host's temp inheritance.

AppContainer (the completion lane, 2026-11-21): the future path
named above is now built. spawn_app_container_process derives
the container SID from the fixed container name
APP_CONTAINER_NAME, builds a SECURITY_CAPABILITIES carrying no
capability SIDs at all (a container with no network capability
has no network; that is the point), grants that SID access to
the job's work directory and to nothing else beyond the read
paths a caller names, with TEMP and TMP pointed at the work
directory for the container process, and creates the process suspended
through CreateProcessW with
PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES in a
STARTUPINFOEXW attribute list, assigning the Job Object before
resume under the same no race discipline as every other spawn
here. The floor stands exactly as it was: the AppContainer
control is added on top of it, never instead of it, and the
status string gains the app_container control only when the
AppContainer trial below proves the control on the host. On a
host where that trial fails, spawn_confined_process keeps the
floor spawn and the floor status, unchanged.

Suppositions for the AppContainer lane, recorded before the
field test that settles them (the Germany rig, Windows Server
2022, the rig lane's run): first, an AppContainer process
created under this spawn shape reads a staged file its
container SID was granted and writes its work directory, on
that build, with no elevation. Second, the same process is
refused a read of a file outside its granted paths, by the
container's own token check rather than by an integrity label.
Third, the same process establishes no network connection at
all, loopback included, because its capabilities carry no
network capability SID. Fourth, the error the network attempt
fails with there distinguishes the container's denial from an
ordinary unreachable address, so the trial's network check can
tell a contained refusal from a dead network. The rig lane
settles all four; until it does, they stand here as
suppositions, and the trial names whichever check fails on a
host where one of them is wrong.

Supposition for the Lane 6 diagnosis, recorded before any
measurement in this lane (2026-11-21): the Lane 5 field test
found the AppContainer spawn failing at creation with
CreateProcessW error 2 (ERROR_FILE_NOT_FOUND) for every
target, cmd.exe included, from the elevated Administrator
context, while the floor spawn works on the same host. My
belief, stated so the measurement can prove it wrong: the
cause sits in the spawn shape itself, not in any grant or
target binary, and the leading candidates inside that shape
are the container profile state behind the derived SID (this
module computes the CreateAppContainerProfile outcome and
then discards it, so a profile that never stood would leave
creation looking for a profile object that does not exist)
and the SECURITY_CAPABILITIES marshaling handed to
UpdateProcThreadAttribute (a NULL Capabilities pointer at a
zero count). The measurement that settles it is a minimal
reproduction on the rig varying one element at a time: the
profile outcome and its HRESULT printed with the profile
folder inspected; a plain CreateProcessW; a STARTUPINFOEX
with an attribute list carrying no attribute; the shipped
capabilities shape; the same shape with a non NULL empty
capabilities array; an explicit application name beside the
command line; a system working directory; no CREATE_SUSPENDED
flag; and an unelevated creating context. The single variant
that turns error 2 into a created process names the cause.
If no variant creates a process and the profile outcome is a
failure, the honest outcome is that the trial names that
failure precisely and the posture record says so.

Conclusions, from the Lane 6 measurement (2026-11-21, the
Germany rig, Windows Server 2022, the elevated Administrator
context): the supposition's leading candidate was the cause,
in a sharper form than stated. The minimal reproduction
varied one element at a time from the shipped shape. A plain
CreateProcessW created the process, and a STARTUPINFOEX with
an initialized but empty attribute list created it too;
every variant carrying the SECURITY_CAPABILITIES attribute
failed with error 2, alike with a NULL capabilities pointer
and with a non NULL empty array, with an explicit application
name, with a system working directory and with no working
directory, without CREATE_SUSPENDED, without an environment
block, and without standard handles. The profile call was
the difference: called with the binding this module shipped,
CreateAppContainerProfile returned 0x80070057 (E_INVALIDARG)
and no profile folder stood under the creating user, while
DeriveAppContainerSidFromAppContainerName succeeded anyway,
derivation being algorithmic. The shipped binding declared
five parameters for a six parameter function: it omitted the
DWORD capability count that stands between the capabilities
array and the SID out pointer, so the out pointer was read
as the count and the call could never succeed. Called with
the count supplied, the same profile call returned 0, the
profile folder stood, and the shipped spawn shape, unchanged
in every other element, created the process and wrote its
marker. The module also discarded the profile outcome it
computed, which is why the failure travelled as a bare error
2 at creation instead of naming itself. The fix therefore
stands in two places: the binding and the call carry the
count, and a failed profile outcome now refuses SID
derivation with the call and its HRESULT named, so the trial
reports the missing mechanism precisely and the gate falls
back to the floor on a named reason. Suppositions S2, S3 and
S4b from the Lane 5 run remain for the re run to settle; S1
is settled by the re run's trial on the fixed head.

Addendum, from the same re run's first measurement: with the
profile standing, the trial process on the rig's interpreter
tree (C:\hp-tools\python) died at load, exit 0xC0000135
(STATUS_DLL_NOT_FOUND) with no output, while the floor trial
passed on the same interpreter. The container SID held no
grant on the interpreter's directory, so the loader could
not map the image's own libraries under the container token;
the earlier Lane 5 diagnostic had shown the same spawn
working only where the interpreter directory had been
granted to the container SID by hand. The spawn therefore
grants the target program's own directory as a read path of
every AppContainer spawn, its own grant, recorded in the
grant set and revoked with it at job end. System libraries
need no such grant: the container token carries the ALL
APPLICATION PACKAGES membership those trees already grant.
One more measurement from the same re run: with read, write,
outside and network all proving out, the trial's token check
still failed, because the trial program's own ctypes import
cannot initialize inside the container (its library's
initialization routine fails under the container token), so
a contained process cannot always report its own token. The
trial now also accepts the parent side's answer: the spawn's
process object reads TokenIsAppContainer from the token of
the process it created, which the runner can always ask.
The program's own report still decides wherever the spawn
seam offers no parent side answer, and a plain token named
by either side still fails the check. A third measurement
from the same re run, isolated in both directions on the
rig: a container SID entry standing in a library file's
DACL makes the floor's restricted token process fail at
load with STATUS_DLL_NOT_FOUND, while a plain token loads
the same file and a container process requires the entry.
The entry that Lane 5's diagnostics granted the rig's
interpreter tree, on a spawn that then failed at creation,
was never revoked, because a failed spawn had no process
whose close could revoke it; every rig battery after it
failed its floor trial at startup for exactly that reason.
A failed AppContainer spawn therefore revokes the grants it
made before the failure travels, in this module, so the
fallback it hands back to is the floor it found.

Supposition for the PowerShell measurement, recorded before
the measurement runs (2026-11-22): on the head carrying all
of the above, the rig battery's runner starts under the
AppContainer control and the audit record names it, yet
every PowerShell job the runner spawns dies at once with
exit 0xC0000142 (STATUS_DLL_INIT_FAILED) and empty output,
while the confinement trial, whose program is the Python
interpreter, proves the control on the same host. My belief,
stated so the measurement can prove it wrong: the trial
proves the container for a native interpreter whose load set
sits beside it and in the system tree the container token
already reaches; PowerShell 5.1 is a .NET Framework program
whose initialization load set reaches further, into the
Windows directory's .NET tree (the CLR and the assembly
store), and the job spawn grants only the work directory
plus the target program's own directory -- for a job, argv
names powershell by its bare name, so not even that -- and a
library the CLR must load while initializing sits beyond
the container's grants, so initialization fails before a
line of the job runs. The measurement that settles it spawns
powershell.exe on the rig through this module's own
AppContainer spawn, first in the job's exact shape, then
with the program's own directory granted, then with the
Windows .NET tree and the system tree added as read paths
one at a time, and records which grant set first lets the
job print its marker and exit 0; a native system binary
spawned the same way is the control that separates a .NET
load set problem from a container wide one. If no added
grant set lets PowerShell run, the supposition is wrong and
the record will say what the measurement found instead.

Conclusions, from that measurement (2026-11-22, the Germany
rig, Windows Server 2022, the elevated Administrator
context): the supposition's mechanism was wrong and its
shape was right. PowerShell died with 0xC0000142 under every
grant set the spawn can name: the work directory alone, the
program's own directory, the Windows .NET tree, the system
tree, and the whole Windows tree granted read and execute
together, and again with its profile environment pointed at
the granted work directory; the .NET Framework's own tools
died the same way. A minimal hand built AppContainer launch
on the same host (profile standing, the capabilities
attribute, no job object, no grants, no handle plumbing)
ran cmd.exe and died the same way on PowerShell, with the
capabilities array NULL and with it an empty array; the
floor spawn ran PowerShell on the same host in the same
minutes, and cmd.exe and the Python interpreter ran
contained under the shipped spawn. Native programs run in
the container on this host; .NET Framework programs do not
initialize in one, whatever the construction. The trial's
interpreter proof therefore proved less than the audit
record claimed when it named the control: a native load
shape, not the job shape the runner runs. The verdict now
carries the trial's second half (appcontainer_job_shape_
problem): the job interpreter, spawned in the job's own
shape through the same AppContainer spawn, must print its
marker and exit cleanly before the verdict may name the
control. On this host the verdict names the job shape
failure, the gate leaves the floor standing, and jobs run
under the floor exactly as they did before the control
existed; on a host where the job shape runs contained, the
control engages as designed.

Supposition for the Lane 7 diagnosis, recorded before any
measurement in this lane (2026-11-21): the measurement above
settled that grant breadth is not the cause, since
PowerShell died under the whole Windows tree granted, and
its closing claim, that managed programs do not initialize
in a container whatever the construction, is wider than its
evidence, because Lane 6 measured a second failing target
that is not managed at all: whoami.exe, a native system
binary, dies with the same exit (0xC0000142,
STATUS_DLL_INIT_FAILED) and no output inside the container,
while cmd.exe, findstr.exe and the Python interpreter run
in the same container on the same host. A cause that covers
both failing targets and spares the three running ones is
therefore still open, and my belief, stated so the
measurement can prove it wrong, is that one DLL in the load
set the two failing targets share and the three running
ones do not load eagerly at initialization performs an
initialization access the capability less container token
cannot make: the candidates, in the order I expect them,
are an initialization open of the creating session's
window station or desktop object, an initialization read
of a profile path or user hive location the inherited
environment names but the container SID cannot read, and
an initialization open of a named object or registry key
that a capability SID, and only a capability SID, reaches.
The measurement that settles it names the DLL first:
loader snaps for both failing targets inside the container
(the image flag set per image, the loader's own debug
output captured), checked against their import sets and
against the running targets' import sets; then one
variable at a time on the rig through this module's own
spawn: the desktop named explicitly in the startup info
with the window station and desktop granted to the
container SID as a recorded grant; the profile environment
variables pointed at the container's own profile folder
with that folder granted; and, as diagnosis only and
never as a fix, one capability SID at a time in the
capabilities array, to learn whether any capability is
what the initialization reaches for. A variant that lets
both failing targets print their markers and exit 0 names
the cause and the failing access together. If the only
variant that works is a capability, the finding stands at
the design boundary and no fix lands in this lane: the
empty capability list is the no_network control, and
widening it is a decision above this module. If a named
grant inside the existing grant shape works, the fix
stands in that shape, recorded and revoked like every
other grant here.

Conclusions, from the Lane 7 measurement (2026-11-21, the
Germany rig, Windows Server 2022, the elevated
Administrator context): the supposition's third candidate
was the cause, in a narrower form than stated, and no
capability stands anywhere near it. The import sets named
the shared shape first: powershell.exe and whoami.exe both
import USER32.dll directly, while cmd.exe, findstr.exe and
the Python interpreter, the three targets that run
contained, import no USER32 at all. The bisection then
varied the session objects one at a time through the
module's own spawn. Granting the container SID on the
creating process's window station alone changed nothing:
both targets still died with 0xC0000142. Granting it on
the desktop alone changed nothing either. Granting both
together, both targets ran: powershell printed its marker
and exited 0, whoami printed its name and exited 0. After
both grants were revoked, powershell died with 0xC0000142
again, the isolation holding in both directions. The mask
bisection then shrank each grant to the least access that
still works: on the desktop, DESKTOP_READOBJECTS (0x0001)
alone suffices; on the window station, either
WINSTA_READATTRIBUTES (0x0002) alone or WINSTA_ENUMERATE
(0x0100) alone suffices, while WINSTA_ENUMDESKTOPS (0x0001)
alone does not, and the spawn grants the two read rights
together (0x0102) so the shape does not rest on one host's
choice between them. A full job payload under the minimal
pair (write a file in the work directory, read it back,
compute a sum) printed its content and its sum and exited
0. The failing initialization is therefore the USER32
family's: a library in that load set opens the session's
window station and desktop while initializing, the access
check is the container's intersection check, and the
capability less token holds no grant on either object, so
initialization fails before a line of the job runs. The
earlier conclusion, that managed programs do not
initialize in a container whatever the construction, does
not stand: it was a grant shaped failure wearing a load
set's clothes, and whoami, a native binary, was the
evidence against it all along. The fix stands inside the
design's own grant shape: every AppContainer spawn now
grants the container SID the recorded session object
access (app_container_session_grant_set: the window
station at 0x0102, the desktop at 0x0001, no create, write,
switch, read screen or clipboard right in either mask),
records it on the process beside the path grants, and
revokes it at job end and on a failed spawn exactly as
the path grants are revoked; the revocation was read back
on the rig, with neither object's DACL naming the
container SID after the process closed. The empty
capability list is untouched, and the proven string names
exactly what it named before. With the fix, the module
trial's verdict on the rig is None with the job shape
probe engaged, and the bare name job shape prints its
marker contained.

Supposition for the Lane 8 diagnosis, recorded before any
measurement in this lane (2026-11-21): with the Lane 7 fix
landed, the module trial's verdict on the rig is None and
a runner started with this module imported under its
runner.guard name spawns its jobs in the AppContainer,
yet in the rig battery's own start shape (the runner
started by the harness bootstrap, which puts both the
tree root and the tree's runner directory on sys.path and
runs runner.py by path as __main__) the audit record
names the floor string for most jobs, with the
AppContainer string appearing only occasionally, even
though the trial passes on that machine. My belief,
stated so the measurement can prove it wrong: the
AppContainer verdict the startup gate computes does not
reliably reach the spawn seam, for a wiring reason inside
this module and its loader, not a capability reason. The
shape of the suspicion is precise. spawn_confined_process
never computes the verdict itself: it reads only this
module instance's cached verdict list, which is populated
solely as a side effect of windows_confinement_problem or
windows_app_container_problem being called on this same
module instance, and it swallows any RuntimeError from
the AppContainer spawn without naming it. So any start
shape in which the gate's call and the spawn's read land
on different module instances of this backend (this file
is importable under two names, runner.guard.windows_
confine with the tree root on the path and guard.
windows_confine with the runner directory on the path,
and the harness bootstrap puts both roots on the path at
once), or in which the spawn is reached on an instance
whose cache no gate call has populated, or in which the
AppContainer spawn itself fails at job time for a reason
the swallow hides, produces exactly the observed record:
the floor runs, the audit names the floor truthfully,
and no surface says the stronger control was proved and
then not used. The measurement that settles it runs on
the rig in the harness bootstrap's own shape, prints the
module identity (its name and id) and the cached verdict
at the gate and at the spawn seam, repeats the spawn
several times in one process, and records any error the
AppContainer spawn raises at job time before the floor
fallback takes it. Whichever variant the measurement
names, the fix must leave one backend instance holding
one verdict, consulted by both the gate and the spawn
seam in every start shape, with the audit line naming
the backend actually in force for each job.

Conclusions, from the Lane 8 measurement (2026-11-21, the
Germany rig, Windows Server 2022): the supposition's
wiring candidates were each measured, and the break is
narrower and stranger than any of them. The duplicate
instance candidate does not stand in the battery shape:
remediation_ops itself loads under two names there, but
both copies resolve this backend to the one
runner.guard instance, and in the traced battery run the
gate and the spawn seam held the same module id and the
same cache throughout. The cache timing candidate does
not stand either: the verdict the gate computed did
reach the spawn seam, on the same instance, for every
job. What the traced run in the battery's own start
shape (the driver launched detached through WMI, outside
any interactive session) showed instead is that the
verdict itself was the failure: the AppContainer trial
passed, but its job shape half answered that powershell
could not run to completion inside the container (exit
1, an UnauthorizedAccessException naming the staged
work directory under the creating user's profile Temp),
so the gate honestly fell back to the floor and every
job followed it. The same gate and spawn in an
interactive session answered None and spawned every job
contained, which is why the defect hid behind green
batteries whose runner happened to start in the other
shape. The isolation then varied the staged directory:
any work directory under the profile Temp tree failed
the same way in the detached shape, a work directory
under the preview root passed, and the staging mechanism
(mkdtemp's DACL versus a plain makedirs) made no
difference. The mechanism, isolated in the interactive
shape where the process runs instead of dying: inside
the container, the process's Win32 current directory is
the granted work directory, but powershell's own
location falls back to a drive root it can open (D:\ on
the rig), its Set-Location to the granted directory is
denied, and its provider relative paths (Get-Content,
Get-FileHash on a staged file's bare name) resolve
against that root instead of the work directory, while
Win32 relative paths work. The shell stands in its
directory by opening the directory and its ancestors;
the spawn granted the leaf and nothing above it, and an
ancestor whose DACL names nothing the container token
holds (the profile root above a Temp tree is the
measured case) is a wall the leaf grant cannot see
past. Granting the container SID read and execute on
every ancestor of the work directory by hand, through
this module's own ACL call, made the contained shell
stand in its directory and read and hash its staged
files by their bare names. The fix therefore stands in
the grant shape: app_container_grant_set now records
every ancestor directory of the work directory and of
each read path at read_execute, granted and revoked
with the rest of the set, so a contained process can
always walk to the directory it was granted, in the
trial's staging and in a job's work tree alike, in
every start shape. Two wiring hardenings from the
supposition stand beside it, because each closes a
silent floor of the same family even though neither was
this break: spawn_confined_process consults the verdict
through windows_app_container_problem when its cache is
empty instead of reading an empty cache as a floor
verdict, and the loader in ops/remediation_ops.py
registers the backend it loaded under both import names
this file carries, so a later import by the other name
in the same process resolves to the same instance, one
verdict for the gate and the spawn alike.

Addendum, from the fix's first battery run in that same
detached shape: the ancestor grants as first landed
carried the grant helper's inheritance flags, and an
inheritable entry set on a directory propagates into
its existing children when the merged DACL is written
back, so the trial's outside file, staged under the
same Temp ancestor as the trial's work directory,
inherited the container's read entry from that ancestor
and the trial answered a boundary crossing and the
runner refused to start. The ancestor entries now stand
without inheritance (an ancestor grant is for the
directory object alone, so the granted path can be
walked to), which the re run's trial and battery then
judge on their own facts.

The DACL residue cycle, and its fix (2026-11-23): the rig
diagnosis of that day proved a self poisoning cycle end to
end. The AppContainer trial's ancestor grant walk reached
the drive root itself, the security write on the root did
not return inside its timeout on that host, the trial spawn
failed, and its cleanup left the container grant standing
on the interpreter's own directory, in the DACL shape the
confined loader cannot use; every later start then died at
the floor trial with STATUS_DLL_NOT_FOUND until the DACL
was reset by hand, and one reset bought exactly one clean
start. Three durable fixes stand in this module now. The
ancestor walk stops below the root of the drive or tree,
so no grant set names the root and the hanging call is
never made. A spawn snapshots the prior DACL of every path
it grants before the first grant stands, and a failed spawn
restores those snapshots whole instead of editing entries
back out under the same timeouts that left the residue; a
path that cannot be snapshotted is not granted. And when
the floor trial dies in the residue shape (the staged read
at exit 0xC0000135) and the interpreter's DACL carries the
container SID, the startup gate names the shape and what
clears it, instead of answering the bare trial failure.
The same diagnosis bounded the floor: on the one clean run
the jobs ran under the floor alone, the AppContainer
control being unavailable, and the battery's escape write
landed, because the floor has no filesystem isolation. That
limit is stated where the claim lives, in the support
matrix and the Windows security page: a blocked escape
write is a property of the AppContainer shape, not of the
floor. The record of the supposition and the unit level
conclusions stands in docs/infrastructure-documents/
project/windows-dacl-residue-fix-2026-11-23.md; the live
proof is the rig battery watch's on the heads that carry
this fix.

Handle lifetime: apply_windows_containment returns the job handle
with the status; the caller owns it and closes it with
close_job_handle once the job's process has exited. A confined
spawn's process object owns its handles; its release callable
(WindowsConfinedProcess.close) closes the Job Object handle --
closing the last handle ends the job (JOB_OBJECT_LIMIT_KILL_ON_
JOB_CLOSE) -- and the process and pipe handles.

Supposition, recorded before the field test on a real Windows
host (the Germany rig, Windows Server 2022): before this backend,
confinement at enforce on win32 refused at startup ("confinement
(bwrap) is Linux-only; this machine is win32"). After it, the
startup probe -- Job Object creation plus restricted-token
creation plus the integrity-level set, each on a throwaway
handle -- returns None on a host where those calls work, the
runner starts with every security mode at enforce, and a job's
audit record names STATUS_CONFINEMENT. Token creation for one's
own process needs no administrator rights; the probe, not an
assumption, is what the gate consults.

This module is import-safe on non-Windows; functions that need
the APIs raise or return a problem string when called off win32.
The stub/real branch below keys on the host's ctypes surface as
well as the platform string, so import stays safe under the
suite's simulated win32 (sys.platform patched on a POSIX host)
as well: a simulated platform cannot bind Windows APIs the host
does not have.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from ctypes import wintypes

# The one ceiling Phase 1 sets: 512 MiB of committed memory per job
# process. A named constant, not a config knob yet.
DEFAULT_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024
# What a confined process's 2 pumps hold of each stream at most
# (finding F17). The pumps start with the process, before the
# caller can name its own bar, so they carry this fixed one from
# the first byte; communicate_held lowers it to the caller's.
# Past the bar a pump goes on reading, counts, and holds no more.
PUMP_HELD_BYTES = 64 * 1024 * 1024

# The status string for the Job Object control alone (job_user).
STATUS_JOB_OBJECT = "windows_job_object"

# The confinement controls, named exactly. Every audit and
# startup record for Windows confinement carries this string and
# nothing stronger: no record calls this a sandbox.
STATUS_CONFINEMENT = "windows: job_object + restricted_token + low_integrity"
CONFINEMENT_CONTROLS = ("job_object", "restricted_token", "low_integrity")

# The AppContainer controls, named by the record when the
# AppContainer trial proves them on the host, and only then
# (the design record: docs/steady/design/
# windows-appcontainer-design.md). The AppContainer spawn
# replaces the restricted token control for the processes it
# covers: Job Objects compose, the restricted token does not,
# and composing CreateProcessAsUserW with a security
# capabilities attribute is undocumented, so the design does
# not attempt it. Low integrity is not double named either:
# an AppContainer token runs at Low integrity by construction.
# The proven string is therefore its own shape, not the floor
# string with a name appended.
APP_CONTAINER_CONTROL = "appcontainer"
NO_NETWORK_CONTROL = "no_network"
STATUS_APP_CONTAINER = "windows: job_object + appcontainer + no_network"
APP_CONTAINER_CONTROLS = ("job_object", "appcontainer", "no_network")
# The earlier lane name for the extended string, kept as an
# alias so no record built on it breaks.
STATUS_CONFINEMENT_WITH_APP_CONTAINER = STATUS_APP_CONTAINER
CONFINEMENT_CONTROLS_WITH_APP_CONTAINER = APP_CONTAINER_CONTROLS

# The fixed container name the container SID is derived from.
# One name for every job: the container identity is the
# runner's confinement identity, not a per job identity, and a
# fixed name keeps the SID (and so every grant) stable across
# runs. validate_app_container_name below pins its shape.
APP_CONTAINER_NAME = "pigeon-home.homing-pigeon.runner"
APP_CONTAINER_NAME_MAX = 64

# The session object access the container SID is granted for
# every AppContainer spawn (the Lane 7 measurement, recorded
# in the header): on the creating process's own window
# station, WINSTA_READATTRIBUTES (0x0002) plus WINSTA_ENUMERATE
# (0x0100), and on its desktop, DESKTOP_READOBJECTS (0x0001)
# alone. No create, write, switch, read screen or clipboard
# right stands in either mask: the grant exists so a library
# that initializes against the session's window station and
# desktop can open them, and for nothing else.
WINDOW_STATION_CONTAINER_ACCESS = 0x0102
DESKTOP_CONTAINER_ACCESS = 0x0001

# PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES: attribute 9 in
# the PROC_THREAD_ATTRIBUTE_NUM class, with the thread class
# bit set, exactly as the Windows headers define it.
PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009
EXTENDED_STARTUPINFO_PRESENT = 0x00080000


def confinement_status(app_container=False):
    """The confinement status string for this backend.

    The floor string by default. The extended string, naming
    app_container, only when `app_container` is true, which a
    caller may pass only on the strength of a passed
    AppContainer trial (appcontainer_trial_problem below).
    """
    if app_container:
        return STATUS_APP_CONTAINER
    return STATUS_CONFINEMENT


def effective_confinement_status(app_container_problem):
    """The status a posture record carries, given the
    AppContainer trial's verdict: the extended string when the
    trial passed (the problem is None), the floor string when
    it failed, with the floor exactly as it has always been.
    """
    return confinement_status(app_container_problem is None)

if sys.platform != "win32" or not hasattr(ctypes, "WinDLL"):
    # Stub so the rest of the runner can import without error. The
    # startup probes answer a problem string (never None), so an
    # enforce gate consulting this stub refuses, and apply/spawn
    # raise: off Windows this backend can never claim to have
    # engaged. IS_WINDOWS_BACKEND is how the gates tell this stub
    # from the real implementation below: only a real backend's
    # probe is ever consulted, so a simulated win32 answers the
    # refusal deterministically on any host.
    #
    # The branch follows the host's Windows API surface, not the
    # platform string alone: the suite simulates win32 by patching
    # sys.platform on POSIX hosts, and a first import under that
    # patch must still land here -- the host has no ctypes.WinDLL
    # to bind, and reaching for it raised AttributeError at import
    # (through main(), in the simulated-win32 startup tests). On
    # a real Windows host sys.platform is "win32" and ctypes
    # always carries WinDLL, so the real implementation below is
    # taken exactly as before.
    IS_WINDOWS_BACKEND = False

    def windows_startup_problem(*args, **kwargs):
        return "windows_confine is Windows-only"

    def windows_confinement_problem(*args, **kwargs):
        return "windows_confine is Windows-only"

    def apply_windows_containment(*args, **kwargs):
        raise RuntimeError("windows_confine is Windows-only")

    def spawn_confined_process(*args, **kwargs):
        raise RuntimeError("windows_confine is Windows-only")

    def spawn_job_object_process(*args, **kwargs):
        raise RuntimeError("windows_confine is Windows-only")

    def windows_app_container_problem(*args, **kwargs):
        return "windows_confine is Windows-only"

    def spawn_app_container_process(*args, **kwargs):
        raise RuntimeError("windows_confine is Windows-only")

    def app_container_grants(*args, **kwargs):
        return []

    def app_container_session_grants(*args, **kwargs):
        return []

    def remove_app_container_grants(*args, **kwargs):
        return []

    def close_job_handle(handle):
        return None
else:
    IS_WINDOWS_BACKEND = True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    # Typed bindings: HANDLE results must be declared, or ctypes
    # returns a 32-bit int and truncates the handle on 64-bit
    # Windows.
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID,
                                          wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE,
                                                  wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE),
                                    ctypes.POINTER(wintypes.HANDLE),
                                    wintypes.LPVOID, wintypes.DWORD]
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE,
                                              wintypes.DWORD,
                                              wintypes.DWORD]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
        wintypes.HANDLE]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
                                  wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD),
                                  wintypes.LPVOID]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE,
                                             wintypes.DWORD]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE,
                                          ctypes.c_uint]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]

    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE)]
    advapi32.CreateRestrictedToken.restype = wintypes.BOOL
    advapi32.CreateRestrictedToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.LPVOID,
        ctypes.POINTER(wintypes.HANDLE)]
    advapi32.SetTokenInformation.restype = wintypes.BOOL
    advapi32.SetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
        wintypes.DWORD]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi32.CreateProcessAsUserW.restype = wintypes.BOOL
    advapi32.CreateProcessAsUserW.argtypes = [
        wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPWSTR,
        wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL,
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        wintypes.LPVOID, wintypes.LPVOID]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR,
        wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL,
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        wintypes.LPVOID, wintypes.LPVOID]
    advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL
    advapi32.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID)]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype \
        = wintypes.BOOL
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD)]
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype \
        = wintypes.BOOL
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(wintypes.DWORD)]
    advapi32.GetSecurityDescriptorSacl.restype = wintypes.BOOL
    advapi32.GetSecurityDescriptorSacl.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.BOOL)]
    advapi32.GetSecurityDescriptorDacl.restype = wintypes.BOOL
    advapi32.GetSecurityDescriptorDacl.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.BOOL)]
    advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi32.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
        wintypes.LPVOID, wintypes.LPVOID, wintypes.LPVOID,
        wintypes.LPVOID]

    # AppContainer bindings. DeriveAppContainerSidFromAppContainerName
    # lives in userenv; the attribute list calls and the SID to
    # string conversion are kernel32 and advapi32.
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    userenv.DeriveAppContainerSidFromAppContainerName.restype = \
        ctypes.c_long
    userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID)]
    userenv.CreateAppContainerProfile.restype = ctypes.c_long
    # The native signature carries six parameters: the
    # capabilities array, its DWORD count, and only then the
    # SID out pointer. The Lane 6 field diagnosis (2026-11-21)
    # found this binding declared with five, the count missing:
    # the call's SID out pointer was read as the capability
    # count, the call failed with E_INVALIDARG, no profile ever
    # stood, and every AppContainer CreateProcessW then failed
    # with ERROR_FILE_NOT_FOUND. The count stands here so the
    # shape cannot silently lose it again.
    userenv.CreateAppContainerProfile.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID)]
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetProcessWindowStation.restype = wintypes.HANDLE
    user32.GetProcessWindowStation.argtypes = []
    user32.GetThreadDesktop.restype = wintypes.HANDLE
    user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    kernel32.GetCurrentThreadId.argtypes = []
    advapi32.GetSecurityInfo.restype = wintypes.DWORD
    advapi32.GetSecurityInfo.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID)]
    advapi32.SetSecurityInfo.restype = wintypes.DWORD
    advapi32.SetSecurityInfo.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.DWORD,
        wintypes.LPVOID, wintypes.LPVOID, wintypes.LPVOID,
        wintypes.LPVOID]
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID)]
    advapi32.SetEntriesInAclW.restype = wintypes.DWORD
    advapi32.SetEntriesInAclW.argtypes = [
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPVOID)]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.InitializeProcThreadAttributeList.argtypes = [
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t)]
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = [
        wintypes.LPVOID, wintypes.DWORD, ctypes.c_size_t,
        wintypes.LPVOID, ctypes.c_size_t, wintypes.LPVOID,
        ctypes.POINTER(ctypes.c_size_t)]
    kernel32.DeleteProcThreadAttributeList.restype = None
    kernel32.DeleteProcThreadAttributeList.argtypes = [wintypes.LPVOID]

    # Constants
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9

    TOKEN_DUPLICATE = 0x0002
    TOKEN_ASSIGN_PRIMARY = 0x0001
    TOKEN_QUERY = 0x0008
    TOKEN_ADJUST_DEFAULT = 0x0080
    DISABLE_MAX_PRIVILEGE = 0x00000001
    TokenIntegrityLevel = 25
    TokenIsAppContainer = 29
    SE_GROUP_INTEGRITY = 0x00000020
    ADMINISTRATORS_SID = "S-1-5-32-544"
    LOW_INTEGRITY_SID = "S-1-16-4096"

    CREATE_SUSPENDED = 0x00000004
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    STARTF_USESTDHANDLES = 0x00000100
    HANDLE_FLAG_INHERIT = 0x00000001
    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102
    INFINITE = 0xFFFFFFFF
    STILL_ACTIVE = 259
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    SE_FILE_OBJECT = 1
    SE_WINDOW_OBJECT = 7
    LABEL_SECURITY_INFORMATION = 0x00000010
    DACL_SECURITY_INFORMATION = 0x00000004
    SDDL_REVISION_1 = 1
    GRANT_ACCESS = 1
    REVOKE_ACCESS = 4
    TRUSTEE_IS_SID = 0
    TRUSTEE_IS_UNKNOWN = 0
    OBJECT_INHERIT_ACE = 0x00000001
    CONTAINER_INHERIT_ACE = 0x00000002
    GENERIC_ALL_ACCESS = 0x10000000
    GENERIC_READ_EXECUTE_ACCESS = 0xA0000000
    PROFILE_DISPLAY_NAME = "Homing Pigeon runner"
    PROFILE_DESCRIPTION = "Homing Pigeon runner confinement"
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Sid", wintypes.LPVOID),
                    ("Attributes", wintypes.DWORD)]

    class TOKEN_MANDATORY_LABEL(ctypes.Structure):
        _fields_ = [("Label", SID_AND_ATTRIBUTES)]

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD),
                    ("lpSecurityDescriptor", wintypes.LPVOID),
                    ("bInheritHandle", wintypes.BOOL)]

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [("hProcess", wintypes.HANDLE),
                    ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD),
                    ("dwThreadId", wintypes.DWORD)]

    class SECURITY_CAPABILITIES(ctypes.Structure):
        _fields_ = [("AppContainerSid", wintypes.LPVOID),
                    ("Capabilities",
                     ctypes.POINTER(SID_AND_ATTRIBUTES)),
                    ("CapabilityCount", wintypes.DWORD),
                    ("Reserved", wintypes.DWORD)]

    class TRUSTEE_W(ctypes.Structure):
        _fields_ = [("pMultipleTrustee", wintypes.LPVOID),
                    ("MultipleTrusteeOperation", ctypes.c_int),
                    ("TrusteeForm", ctypes.c_int),
                    ("TrusteeType", ctypes.c_int),
                    ("ptstrName", wintypes.LPVOID)]

    class EXPLICIT_ACCESS_W(ctypes.Structure):
        _fields_ = [("grfAccessPermissions", wintypes.DWORD),
                    ("grfAccessMode", ctypes.c_int),
                    ("grfInheritance", wintypes.DWORD),
                    ("Trustee", TRUSTEE_W)]

    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [("StartupInfo", STARTUPINFOW),
                    ("lpAttributeList", wintypes.LPVOID)]

    def _create_job_with_limits(memory_bytes):
        """(handle, None) with the memory ceiling set, or
        (None, problem). The last-error is read immediately after
        the failing call, before any CloseHandle can overwrite it.
        """
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None, "CreateJobObjectW failed: %d" % (
                ctypes.get_last_error(),)
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | JOB_OBJECT_LIMIT_JOB_MEMORY
            | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        info.ProcessMemoryLimit = int(memory_bytes)
        info.JobMemoryLimit = int(memory_bytes)
        if not kernel32.SetInformationJobObject(
            job, JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info)
        ):
            err = ctypes.get_last_error()
            kernel32.CloseHandle(job)
            return None, "SetInformationJobObject failed: %d" % err
        return job, None

    def _sid_from_string(text):
        """A PSID the caller frees with LocalFree, or (None, problem)."""
        sid = wintypes.LPVOID()
        if not advapi32.ConvertStringSidToSidW(text, ctypes.byref(sid)):
            return None, "ConvertStringSidToSidW(%s) failed: %d" % (
                text, ctypes.get_last_error())
        return sid, None

    def _create_restricted_low_token():
        """(token_handle, None) or (None, problem).

        The token is the runner's own, restricted: every privilege
        except SeChangeNotify stripped (DISABLE_MAX_PRIVILEGE), the
        Administrators group disabled (a job never inherits the
        runner's admin group), and the mandatory integrity level
        set to Low. The caller owns the handle.
        """
        src = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
                kernel32.GetCurrentProcess(),
                TOKEN_DUPLICATE | TOKEN_ASSIGN_PRIMARY | TOKEN_QUERY
                | TOKEN_ADJUST_DEFAULT, ctypes.byref(src)):
            return None, "OpenProcessToken failed: %d" % (
                ctypes.get_last_error(),)
        try:
            admin_sid, problem = _sid_from_string(ADMINISTRATORS_SID)
            if problem is not None:
                return None, problem
            try:
                disable = SID_AND_ATTRIBUTES()
                disable.Sid = admin_sid
                disable.Attributes = 0
                token = wintypes.HANDLE()
                if not advapi32.CreateRestrictedToken(
                        src, DISABLE_MAX_PRIVILEGE, 1,
                        ctypes.byref(disable), 0, None, 0, None,
                        ctypes.byref(token)):
                    return None, "CreateRestrictedToken failed: %d" % (
                        ctypes.get_last_error(),)
            finally:
                kernel32.LocalFree(admin_sid)
            low_sid, problem = _sid_from_string(LOW_INTEGRITY_SID)
            if problem is not None:
                kernel32.CloseHandle(token)
                return None, problem
            try:
                label = TOKEN_MANDATORY_LABEL()
                label.Label.Sid = low_sid
                label.Label.Attributes = SE_GROUP_INTEGRITY
                if not advapi32.SetTokenInformation(
                        token, TokenIntegrityLevel, ctypes.byref(label),
                        ctypes.sizeof(label) + 64):
                    err = ctypes.get_last_error()
                    kernel32.CloseHandle(token)
                    return None, "SetTokenInformation(" \
                        "TokenIntegrityLevel) failed: %d" % err
            finally:
                kernel32.LocalFree(low_sid)
            return token, None
        finally:
            kernel32.CloseHandle(src)

    def _set_low_integrity_label(path):
        """Best effort: label a directory Low integrity so a
        low-integrity job can write inside its own workspace.
        Returns True when the label was set. Failure is not fatal
        to the spawn -- the job still runs confined; writes to
        that directory are then the integrity policy's answer,
        and the job's result records it -- but the caller may log
        it. Never raises.
        """
        try:
            sd = wintypes.LPVOID()
            if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    "S:(ML;;NW;;;LW)", SDDL_REVISION_1,
                    ctypes.byref(sd), None):
                return False
            try:
                present = wintypes.BOOL()
                defaulted = wintypes.BOOL()
                sacl = wintypes.LPVOID()
                if not advapi32.GetSecurityDescriptorSacl(
                        sd, ctypes.byref(present), ctypes.byref(sacl),
                        ctypes.byref(defaulted)):
                    return False
                if not present or not sacl:
                    return False
                rc = advapi32.SetNamedSecurityInfoW(
                    ctypes.create_unicode_buffer(path), SE_FILE_OBJECT,
                    LABEL_SECURITY_INFORMATION, None, None, None, sacl)
                return rc == 0
            finally:
                kernel32.LocalFree(sd)
        except Exception:
            return False

    def _grant_users_read_execute(paths):
        """None after the trial grant's DACL stands on every
        path in `paths`, else the problem. Never raises.

        The confinement trial's grant (the Q134 addendum): the
        confined token disables Administrators and is not
        SYSTEM, but it carries BUILTIN\\Users enabled, so the
        DACL in TRIAL_GRANT_SDDL -- SYSTEM and Administrators
        at full control, so the runner keeps ownership of its
        own tree, and Users at read+execute -- is what makes
        the staged tree openable by the confined process on
        any host, an elevated administrator's included, where
        the tree a bare makedirs leaves can name neither group
        the token holds. The DACL replaces each path's own;
        the paths are the trial's throwaway tree, so
        replacement is safe there and only there.
        """
        try:
            sd = wintypes.LPVOID()
            if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    TRIAL_GRANT_SDDL, SDDL_REVISION_1,
                    ctypes.byref(sd), None):
                return ("ConvertStringSecurityDescriptorTo"
                        "SecurityDescriptorW(%s) failed: %d"
                        % (TRIAL_GRANT_SDDL,
                           ctypes.get_last_error()))
            try:
                present = wintypes.BOOL()
                defaulted = wintypes.BOOL()
                dacl = wintypes.LPVOID()
                if not advapi32.GetSecurityDescriptorDacl(
                        sd, ctypes.byref(present),
                        ctypes.byref(dacl),
                        ctypes.byref(defaulted)):
                    return ("GetSecurityDescriptorDacl failed: %d"
                            % (ctypes.get_last_error(),))
                if not present or not dacl:
                    return ("the trial grant's descriptor "
                            "carries no DACL")
                for path in paths:
                    rc = advapi32.SetNamedSecurityInfoW(
                        ctypes.create_unicode_buffer(path),
                        SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
                        None, None, dacl, None)
                    if rc != 0:
                        return ("SetNamedSecurityInfoW(%s) "
                                "failed: %d" % (path, rc))
                return None
            finally:
                kernel32.LocalFree(sd)
        except Exception as e:
            return "the trial grant failed: %s" % (e,)

    def windows_startup_problem(cfg=None, timeout=15):
        """None if a Job Object with the memory ceiling can be
        created on this host, else why not.

        This is a necessary condition, not a sufficient one: it
        proves creation and limit-setting work. Assigning a
        particular job process can still fail at job time (a
        process already inside a job that forbids breakaway is the
        known shape), and that failure refuses the job then -- the
        probe never stands in for the assignment.
        """
        job, problem = _create_job_with_limits(
            DEFAULT_PROCESS_MEMORY_BYTES)
        if problem is not None:
            return problem
        kernel32.CloseHandle(job)
        return None

    _trial_lock = threading.Lock()
    _trial_verdict = []

    def _grant_residue_verdict(floor_problem):
        """The residue naming for a floor verdict, or None
        when the shape is not proved on this host.

        The container SID is derived and the interpreter's
        own directory and file are read for it: the measured
        residue stood on the directory, inherited by every
        file under it. A read that fails proves nothing and
        names nothing, and neither does a derivation that
        fails: the bare verdict stands, exactly as it did
        before the naming existed. Never raises.
        """
        try:
            sid, problem = _derive_app_container_sid()
            if problem is not None:
                return None
            try:
                sid_text, problem = _sid_to_string(sid)
                if problem is not None:
                    return None
                exe = sys.executable
                for path in (os.path.dirname(exe), exe):
                    if not path:
                        continue
                    sddl, problem = _read_dacl_sddl(path)
                    # The SID as an ACE's trustee is followed
                    # by the ACE's closing parenthesis in SDDL;
                    # the bare string could be the prefix of a
                    # longer SID and prove nothing.
                    if problem is None and sddl \
                            and (sid_text + ")") in sddl:
                        return grant_residue_problem(
                            floor_problem, path)
                return None
            finally:
                kernel32.LocalFree(sid)
        except Exception:
            return None

    def windows_confinement_problem(cfg=None, timeout=15):
        """None when the confinement controls can engage here.

        Stronger than the job_user probe: a Job Object with the
        memory ceiling, AND a restricted token with the integrity
        level set to Low, must both be creatable. Each is made on
        a throwaway handle and closed here; the per-job spawn
        makes its own. Any failure is named, and the enforce gate
        refuses with it.

        Creation alone does not prove a confined process can
        work (Q134: a host passed this probe and failed every
        job's staged script), so the first call on a host whose
        controls can be created also runs the trial: a confined
        process that reads a staged file and writes its work
        directory, through confinement_trial_problem below. The
        verdict is cached for the life of the process -- the
        per-job gate consults this probe, and the trial's cost
        (one confined spawn) is paid once per runner start, not
        once per job.
        """
        problem = windows_startup_problem(cfg, timeout=timeout)
        if problem is not None:
            return problem
        token, problem = _create_restricted_low_token()
        if problem is not None:
            return problem
        kernel32.CloseHandle(token)
        with _trial_lock:
            if not _trial_verdict:
                verdict = confinement_trial_problem(
                    _spawn_floor_confined_process,
                    grant=_grant_users_read_execute)
                if floor_trial_dll_not_found(verdict):
                    # The floor died at load in the residue
                    # shape: name it, if the interpreter's
                    # DACL proves it, before the verdict is
                    # cached, so the gate answers with the
                    # diagnosis and not the bare failure.
                    named = _grant_residue_verdict(verdict)
                    if named is not None:
                        verdict = named
                _trial_verdict.append(verdict)
            verdict = _trial_verdict[0]
        if verdict is None:
            # The floor stands on this host. The AppContainer
            # trial runs too, and caches its verdict, so the
            # status and the spawn choice can name the controls
            # when they prove out. A merely unavailable
            # AppContainer changes nothing here; a boundary
            # crossing refuses outright, through
            # confinement_gate_problem, naming the crossing.
            try:
                ac_verdict = windows_app_container_problem(cfg)
            except Exception:
                ac_verdict = None
            return confinement_gate_problem(verdict, ac_verdict)
        return verdict

    def apply_windows_containment(proc_handle,
                                  memory_bytes=DEFAULT_PROCESS_MEMORY_BYTES):
        """Assign the process behind `proc_handle` to a fresh Job
        Object carrying the memory ceiling.

        Returns (STATUS_JOB_OBJECT, job_handle) on success; the
        caller owns the job handle (see the module docstring).
        Raises RuntimeError whenever the control was not applied --
        there is no partial success to record.
        """
        if not proc_handle:
            raise RuntimeError(
                "no process handle to contain; nothing was applied")
        job, problem = _create_job_with_limits(memory_bytes)
        if problem is not None:
            raise RuntimeError(problem)
        if not kernel32.AssignProcessToJobObject(job, proc_handle):
            err = ctypes.get_last_error()
            kernel32.CloseHandle(job)
            raise RuntimeError(
                "AssignProcessToJobObject failed: %d" % err)
        return STATUS_JOB_OBJECT, job

    def close_job_handle(handle):
        """Close a job handle returned by apply_windows_containment.

        Called once the contained process has exited: closing the
        last handle ends the job (KILL_ON_JOB_CLOSE), which is a
        no-op for an exited process and a backstop for anything it
        left running inside the job.
        """
        if handle:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass

    class WindowsConfinedProcess:
        """The Popen subset exec.py drives, for a confined spawn.

        .pid, ._handle, .returncode, .communicate(timeout),
        .kill(), .poll(). communicate raises
        subprocess.TimeoutExpired on timeout, exactly as Popen's
        does, and a second call after a timeout waits for the
        (killed) process and returns its output, as Popen's does.
        """

        def __init__(self, argv, handle, pid, job_handle,
                     out_read, err_read):
            self.args = argv
            self.pid = pid
            self._handle = handle
            self._job_handle = job_handle
            self._out_read = out_read
            self._err_read = err_read
            self.returncode = None
            self._result = None
            self._out = bytearray()
            self._err = bytearray()
            self._keep = PUMP_HELD_BYTES
            self._seen = [0, 0]
            self._readers = []
            for index, (target, sink) in enumerate(
                    ((out_read, self._out), (err_read, self._err))):
                th = threading.Thread(target=self._pump,
                                      args=(target, sink, index),
                                      daemon=True)
                th.start()
                self._readers.append(th)

        def _pump(self, handle, sink, index):
            buf = ctypes.create_string_buffer(8192)
            while True:
                got = wintypes.DWORD(0)
                ok = kernel32.ReadFile(handle, buf, 8192,
                                       ctypes.byref(got), None)
                if not ok or got.value == 0:
                    return
                # The pump reads to the stream's end, so the job
                # never waits on a full pipe. It holds the first
                # part, up to the bar, and counts the rest.
                self._seen[index] += got.value
                room = self._keep - len(sink)
                if room > 0:
                    sink.extend(buf.raw[:min(got.value, room)])

        def _wait(self, timeout_ms):
            return kernel32.WaitForSingleObject(self._handle, timeout_ms)

        def _finish(self):
            code = wintypes.DWORD(0)
            if kernel32.GetExitCodeProcess(self._handle,
                                           ctypes.byref(code)):
                self.returncode = code.value if code.value < 0x80000000 \
                    else code.value - 0x100000000
            for th in self._readers:
                th.join(timeout=5)
            self._result = (bytes(self._out), bytes(self._err))
            return self._result

        def communicate(self, timeout=None):
            if self._result is not None:
                return self._result
            if self.returncode is not None:
                return self._finish()
            if timeout is None:
                self._wait(INFINITE)
            else:
                rc = self._wait(int(timeout * 1000))
                if rc == WAIT_TIMEOUT:
                    raise subprocess.TimeoutExpired(self.args, timeout)
            return self._finish()

        def communicate_held(self, held, timeout=None):
            """communicate, with the caller's bar on what is
            held of each stream (runner/ops/helpers.py, Held).
            The pumps' own bar is lowered to it, the streams
            are handed back cut to it, and the reader is told
            how many bytes each stream carried."""
            self._keep = min(self._keep, held.keep)
            out, err = self.communicate(timeout)
            out, err = out[:self._keep], err[:self._keep]
            held.took("stdout", out, self._seen[0])
            held.took("stderr", err, self._seen[1])
            return out, err

        def poll(self):
            if self.returncode is not None:
                return self.returncode
            if self._wait(0) == WAIT_TIMEOUT:
                return None
            self._finish()
            return self.returncode

        def is_app_container_token(self):
            """True when this process's own token is an
            AppContainer token, read from the parent side:
            OpenProcessToken on the handle this class holds,
            GetTokenInformation(TokenIsAppContainer). None
            when the query itself fails, so a caller can tell
            an unreadable token from a plain one. The parent
            side is the reliable side for this fact: inside
            the container, the trial program's own ctypes
            import can fail to initialize under the container
            token (the Lane 6 re run's measurement), so a
            contained process cannot always report its own
            token, while the runner that created it always
            can ask for it."""
            token = wintypes.HANDLE()
            if not advapi32.OpenProcessToken(
                    self._handle, TOKEN_QUERY,
                    ctypes.byref(token)):
                return None
            try:
                val = wintypes.DWORD(0)
                needed = wintypes.DWORD(0)
                if not advapi32.GetTokenInformation(
                        token, TokenIsAppContainer,
                        ctypes.byref(val), ctypes.sizeof(val),
                        ctypes.byref(needed)):
                    return None
                return bool(val.value)
            finally:
                kernel32.CloseHandle(token)

        def kill(self):
            try:
                kernel32.TerminateProcess(self._handle, 1)
            except Exception:
                pass

        def close(self):
            """The release: close the Job Object (ends anything
            still in it), then the process and pipe handles."""
            close_job_handle(self._job_handle)
            self._job_handle = None
            for handle in (self._out_read, self._err_read, self._handle):
                if handle:
                    try:
                        kernel32.CloseHandle(handle)
                    except Exception:
                        pass
            self._out_read = self._err_read = None

    def _spawn_suspended(argv, cwd, env, job, token,
                         capabilities=None):
        """Create the process suspended, assign it, resume it.

        The one creation sequence both Windows spawns use, so
        they cannot drift apart on the order that matters:
        create suspended, assign the Job Object, and only then
        resume the main thread -- a process that has not run
        cannot have exited before the assignment (Q168).
        `token` is a handle the helper takes ownership of and
        closes after the creation call, or None: a handle
        creates through CreateProcessAsUserW under that
        token (the confined spawn), None creates through
        CreateProcessW under the caller's own token (the
        job_user spawn). `job` is the Job Object handle the
        helper takes ownership of: it rides out in the
        returned process, or is closed on any failure.
        Returns a WindowsConfinedProcess; raises RuntimeError
        naming the call that failed, with every handle the
        attempt made closed and a created-but-unassigned
        process terminated first.
        """
        sa = SECURITY_ATTRIBUTES()
        sa.nLength = ctypes.sizeof(sa)
        sa.bInheritHandle = True
        out_read = wintypes.HANDLE()
        out_write = wintypes.HANDLE()
        err_read = wintypes.HANDLE()
        err_write = wintypes.HANDLE()
        stdin_handle = kernel32.CreateFileW(
            "NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            ctypes.byref(sa), OPEN_EXISTING, 0, None)
        made = kernel32.CreatePipe(ctypes.byref(out_read),
                                   ctypes.byref(out_write),
                                   ctypes.byref(sa), 0) and \
            kernel32.CreatePipe(ctypes.byref(err_read),
                                ctypes.byref(err_write),
                                ctypes.byref(sa), 0)
        if not made or not stdin_handle \
                or stdin_handle == INVALID_HANDLE_VALUE:
            err = ctypes.get_last_error()
            for h in (out_read.value, out_write.value, err_read.value,
                      err_write.value, job, token):
                if h:
                    kernel32.CloseHandle(h)
            raise RuntimeError("suspended spawn pipe setup failed: %d"
                               % err)
        kernel32.SetHandleInformation(out_read, HANDLE_FLAG_INHERIT, 0)
        kernel32.SetHandleInformation(err_read, HANDLE_FLAG_INHERIT, 0)
        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(si)
        si.dwFlags = STARTF_USESTDHANDLES
        si.hStdInput = stdin_handle
        si.hStdOutput = out_write
        si.hStdError = err_write
        if env is None:
            env_block = None
            flags = CREATE_SUSPENDED
        else:
            env_text = "".join("%s=%s\0" % (k, v)
                               for k, v in env.items()) + "\0"
            env_block = ctypes.create_unicode_buffer(env_text)
            flags = CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT
        cmdline = ctypes.create_unicode_buffer(
            subprocess.list2cmdline(list(argv)))
        pi = PROCESS_INFORMATION()
        attr_list = None
        si_ref = ctypes.byref(si)
        if capabilities is not None:
            if token is not None:
                for h in (out_read.value, err_read.value, job):
                    if h:
                        kernel32.CloseHandle(h)
                raise RuntimeError(
                    "the AppContainer spawn takes no token: the "
                    "container's own token is the control")
            siex = STARTUPINFOEXW()
            siex.StartupInfo = si
            siex.StartupInfo.cb = ctypes.sizeof(siex)
            size = ctypes.c_size_t(0)
            kernel32.InitializeProcThreadAttributeList(
                None, 1, 0, ctypes.byref(size))
            attr_list = ctypes.create_string_buffer(size.value)
            if not kernel32.InitializeProcThreadAttributeList(
                    attr_list, 1, 0, ctypes.byref(size)):
                err = ctypes.get_last_error()
                for h in (out_read.value, err_read.value, job):
                    if h:
                        kernel32.CloseHandle(h)
                raise RuntimeError(
                    "InitializeProcThreadAttributeList failed: %d"
                    % err)
            if not kernel32.UpdateProcThreadAttribute(
                    attr_list, 0,
                    PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
                    ctypes.byref(capabilities),
                    ctypes.sizeof(capabilities), None, None):
                err = ctypes.get_last_error()
                kernel32.DeleteProcThreadAttributeList(attr_list)
                for h in (out_read.value, err_read.value, job):
                    if h:
                        kernel32.CloseHandle(h)
                raise RuntimeError(
                    "UpdateProcThreadAttribute("
                    "SECURITY_CAPABILITIES) failed: %d" % err)
            siex.lpAttributeList = ctypes.cast(
                attr_list, wintypes.LPVOID)
            flags |= EXTENDED_STARTUPINFO_PRESENT
            si_ref = ctypes.byref(siex)
        if token is not None:
            create_name = "CreateProcessAsUserW"
            ok = advapi32.CreateProcessAsUserW(
                token, None, cmdline, None, None, True, flags,
                env_block, cwd, si_ref, ctypes.byref(pi))
        else:
            create_name = "CreateProcessW"
            ok = kernel32.CreateProcessW(
                None, cmdline, None, None, True, flags,
                env_block, cwd, si_ref, ctypes.byref(pi))
        err = ctypes.get_last_error()
        if attr_list is not None:
            kernel32.DeleteProcThreadAttributeList(attr_list)
        if token is not None:
            kernel32.CloseHandle(token)
        kernel32.CloseHandle(out_write)
        kernel32.CloseHandle(err_write)
        kernel32.CloseHandle(stdin_handle)
        if not ok:
            for h in (out_read.value, err_read.value, job):
                if h:
                    kernel32.CloseHandle(h)
            raise RuntimeError(
                "%s failed: %d" % (create_name, err))
        if not kernel32.AssignProcessToJobObject(job, pi.hProcess):
            err = ctypes.get_last_error()
            kernel32.TerminateProcess(pi.hProcess, 1)
            for h in (pi.hProcess, pi.hThread, out_read.value,
                      err_read.value, job):
                if h:
                    kernel32.CloseHandle(h)
            raise RuntimeError(
                "AssignProcessToJobObject failed: %d" % err)
        kernel32.ResumeThread(pi.hThread)
        kernel32.CloseHandle(pi.hThread)
        return WindowsConfinedProcess(
            list(argv), pi.hProcess, pi.dwProcessId, job,
            out_read, err_read)

    _ac_profile_attempted = []

    def _ensure_app_container_profile(name=APP_CONTAINER_NAME):
        """Create the container profile once, never per job.

        Returns (outcome, hresult): the
        profile_creation_outcome word and the call's own
        result beside it, so a failure can be named with its
        code and never merely counted. An outcome of "exists"
        is the ordinary steady state: the profile stands from
        an earlier run, and the SID is derived from the name.
        The profile is deleted only at uninstall, which is not
        this module's work.
        """
        if _ac_profile_attempted:
            return _ac_profile_attempted[0]
        sid = wintypes.LPVOID()
        hr = userenv.CreateAppContainerProfile(
            name, PROFILE_DISPLAY_NAME, PROFILE_DESCRIPTION,
            None, 0, ctypes.byref(sid))
        if sid:
            kernel32.LocalFree(sid)
        outcome = profile_creation_outcome(hr)
        _ac_profile_attempted.append((outcome, hr))
        return outcome, hr

    def _derive_app_container_sid(name=APP_CONTAINER_NAME):
        """(sid, None) or (None, problem). The SID is a PSID the
        caller frees with LocalFree. The name is validated first,
        by the platform neutral validate_app_container_name: a
        name outside that shape never reaches the OS call.
        """
        problem = validate_app_container_name(name)
        if problem is not None:
            return None, problem
        outcome, hr = _ensure_app_container_profile(name)
        if outcome == "failed":
            # Derivation is algorithmic and would succeed with
            # no profile standing, and a spawn under the derived
            # SID then fails at creation with a bare
            # ERROR_FILE_NOT_FOUND that names nothing (the Lane 6
            # finding). Refuse here instead, naming the call and
            # its code: a profile that does not stand is a
            # missing mechanism, and the trial reports it as one.
            return None, (
                "CreateAppContainerProfile(%s) failed: "
                "0x%08x; the container profile does not stand, "
                "so no AppContainer process can be created for "
                "it" % (name, hr & 0xFFFFFFFF))
        sid = wintypes.LPVOID()
        hr = userenv.DeriveAppContainerSidFromAppContainerName(
            name, ctypes.byref(sid))
        if hr != 0 or not sid:
            return None, (
                "DeriveAppContainerSidFromAppContainerName(%s) "
                "failed: 0x%08x" % (name, hr & 0xFFFFFFFF))
        return sid, None

    def _sid_to_string(sid):
        """(text, None) or (None, problem) for a PSID."""
        text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(
                sid, ctypes.byref(text)):
            return None, "ConvertSidToStringSidW failed: %d" % (
                ctypes.get_last_error(),)
        try:
            return ctypes.wstring_at(text), None
        finally:
            kernel32.LocalFree(text)

    def _set_dacl_sddl(path, sddl):
        """None once the DACL built from `sddl` stands on `path`,
        else the problem. The _grant_users_read_execute shape,
        with the caller's descriptor."""
        sd = wintypes.LPVOID()
        if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                sddl, SDDL_REVISION_1, ctypes.byref(sd), None):
            return ("ConvertStringSecurityDescriptorTo"
                    "SecurityDescriptorW failed: %d"
                    % (ctypes.get_last_error(),))
        try:
            present = wintypes.BOOL()
            defaulted = wintypes.BOOL()
            dacl = wintypes.LPVOID()
            if not advapi32.GetSecurityDescriptorDacl(
                    sd, ctypes.byref(present), ctypes.byref(dacl),
                    ctypes.byref(defaulted)):
                return ("GetSecurityDescriptorDacl failed: %d"
                        % (ctypes.get_last_error(),))
            if not present or not dacl:
                return "the grant's descriptor carries no DACL"
            rc = advapi32.SetNamedSecurityInfoW(
                ctypes.create_unicode_buffer(path), SE_FILE_OBJECT,
                DACL_SECURITY_INFORMATION, None, None, dacl, None)
            if rc != 0:
                return "SetNamedSecurityInfoW(%s) failed: %d" % (
                    path, rc)
            return None
        finally:
            kernel32.LocalFree(sd)

    def _read_dacl_sddl(path):
        """(sddl, problem): the DACL `path` carries, as SDDL,
        or the problem that kept it from being read. The
        snapshot half of the grant cleanup: the string is the
        DACL in the form the operating system itself round
        trips, and _set_dacl_sddl writes exactly it back, so
        a snapshot restored is the prior DACL as the OS
        serializes it: every ACE, in its order, with its
        flags.
        """
        psid_owner = wintypes.LPVOID()
        psid_group = wintypes.LPVOID()
        dacl = wintypes.LPVOID()
        sd = wintypes.LPVOID()
        rc = advapi32.GetNamedSecurityInfoW(
            ctypes.create_unicode_buffer(path), SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION, ctypes.byref(psid_owner),
            ctypes.byref(psid_group), ctypes.byref(dacl), None,
            ctypes.byref(sd))
        if rc != 0:
            return None, ("GetNamedSecurityInfoW(%s) failed: %d"
                          % (path, rc))
        try:
            text = wintypes.LPWSTR()
            if not advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                    sd, SDDL_REVISION_1, DACL_SECURITY_INFORMATION,
                    ctypes.byref(text), None):
                return None, (
                    "ConvertSecurityDescriptorToStringSecurity"
                    "DescriptorW(%s) failed: %d"
                    % (path, ctypes.get_last_error()))
            try:
                return ctypes.wstring_at(text), None
            finally:
                kernel32.LocalFree(text)
        finally:
            kernel32.LocalFree(sd)

    def _set_entries_in_acl(path, sid, mask, mode, inherit=True):
        """None once one entry for `sid` at `mask` has been
        added to (GRANT_ACCESS) or revoked from (REVOKE_ACCESS)
        the DACL `path` already carries, else the problem.

        The grant is additive, always: the existing DACL is
        read, SetEntriesInAclW merges or revokes the one
        entry, and the merged DACL is written back. No grant
        in this backend ever replaces a DACL.

        `inherit` carries the entry's inheritance flags, and
        it matters: an inheritable entry set on a directory
        propagates into the directory's existing children
        when the merged DACL is written back, so a grant
        meant for one directory object alone (an ancestor of
        a granted path, granted only so the path can be
        walked to) must be made with inherit=False, or it
        silently widens into a grant on everything under
        that ancestor (the Lane 8 fix's first battery run:
        the trial's outside file, staged under the same
        Temp ancestor the work directory's grant set now
        names, inherited the container's read entry and the
        trial read a boundary crossing where none was
        intended). Revocation ignores the flags: a revoke
        removes the trustee's entries either way.
        """
        psid_owner = wintypes.LPVOID()
        psid_group = wintypes.LPVOID()
        dacl = wintypes.LPVOID()
        sd = wintypes.LPVOID()
        rc = advapi32.GetNamedSecurityInfoW(
            ctypes.create_unicode_buffer(path), SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION, ctypes.byref(psid_owner),
            ctypes.byref(psid_group), ctypes.byref(dacl), None,
            ctypes.byref(sd))
        if rc != 0:
            return "GetNamedSecurityInfoW(%s) failed: %d" % (
                path, rc)
        try:
            ea = EXPLICIT_ACCESS_W()
            ea.grfAccessPermissions = mask
            ea.grfAccessMode = mode
            ea.grfInheritance = (
                OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE) \
                if inherit else 0
            ea.Trustee.TrusteeForm = TRUSTEE_IS_SID
            ea.Trustee.TrusteeType = TRUSTEE_IS_UNKNOWN
            ea.Trustee.ptstrName = sid
            new_dacl = wintypes.LPVOID()
            rc = advapi32.SetEntriesInAclW(
                1, ctypes.byref(ea), dacl, ctypes.byref(new_dacl))
            if rc != 0:
                return "SetEntriesInAclW(%s) failed: %d" % (
                    path, rc)
            worker = None
            try:
                # SetNamedSecurityInfoW can sit in the kernel and
                # never return, on a path another process holds.
                # The Windows suite of 2026-11-23 died that way:
                # the revoke at the end of a deep-address job held
                # the 20-minute wall inside this call. The revoke
                # is best effort. A call that returns does so in
                # well under 15 seconds. One that does not is a
                # failed path, not a hung suite.
                box = []

                def _set():
                    box.append(advapi32.SetNamedSecurityInfoW(
                        ctypes.create_unicode_buffer(path),
                        SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
                        None, None, new_dacl, None))

                worker = threading.Thread(target=_set, daemon=True)
                worker.start()
                worker.join(15)
                if worker.is_alive():
                    return ("SetNamedSecurityInfoW(%s) did not "
                            "return" % path)
                rc = box[0] if box else -1
                if rc != 0:
                    return ("SetNamedSecurityInfoW(%s) failed: "
                            "%d" % (path, rc))
                return None
            finally:
                if worker is not None and not worker.is_alive():
                    kernel32.LocalFree(new_dacl)
        finally:
            kernel32.LocalFree(sd)

    def _grant_app_container_paths_with_snapshots(
            sid, work_dir, read_paths=()):
        """(granted, snapshots, problem): the grant below,
        with the prior DACL of every granted path snapshotted
        before the first grant stands.

        The snapshots are the failed spawn's way back: a
        spawn that fails after granting restores them whole
        (see _restore_failed_spawn_dacls) instead of editing
        the entries it added back out. The snapshots are
        taken for the whole set first, all or nothing: a
        path whose DACL cannot be read is never granted,
        because a grant this spawn cannot put back is a
        grant it does not make. On a grant problem partway,
        every snapshot stands restored before the problem is
        answered, and a path the restore itself could not
        put back is named in the problem, so the residue is
        reported where it stands instead of discovered by
        the next start.
        """
        try:
            grants = app_container_grant_set(work_dir, read_paths)
        except ValueError as e:
            return [], [], "%s" % (e,)
        snapshots, problem = take_dacl_snapshots(
            [path for path, access in grants], _read_dacl_sddl)
        if problem is not None:
            return [], [], problem
        named = {work_dir} | set(read_paths or ())
        ancestors = set()
        for path in named:
            ancestors.update(app_container_ancestor_dirs(path))
        ancestors -= named
        for path, access in grants:
            mask = GENERIC_ALL_ACCESS \
                if access == "read_write_execute" \
                else GENERIC_READ_EXECUTE_ACCESS
            problem = _set_entries_in_acl(
                path, sid, mask, GRANT_ACCESS,
                inherit=path not in ancestors)
            if problem is not None:
                failed = restore_dacl_snapshots(
                    snapshots, _set_dacl_sddl)
                if failed:
                    problem = (
                        "%s; the prior DACL could not be "
                        "restored on: %s"
                        % (problem, ", ".join(failed)))
                return [], snapshots, problem
        return grants, snapshots, None

    def _grant_app_container_paths(sid, work_dir, read_paths=()):
        """(granted, problem): additively grant the container
        SID read, write and execute on the work directory and
        read plus execute on each read path, and nothing
        anywhere else. `granted` is the recorded grant set
        (app_container_grant_set's shape) once every grant
        stands, so the caller can report exactly what was
        granted and revoke exactly that at job end; on a
        problem it is empty and no spawn follows.
        """
        grants, snapshots, problem = \
            _grant_app_container_paths_with_snapshots(
                sid, work_dir, read_paths)
        return grants, problem

    def _restore_failed_spawn_dacls(snapshots, sid, grants):
        """Put a failed spawn's granted paths back exactly as
        they were found: write every DACL snapshot back
        whole, and for any path the restore could not put
        back, fall back to revoking the recorded grant's
        entry, the older cleanup, so the path gets both
        chances. Best effort throughout, and never raises:
        this runs on a failure path whose own error is the
        one that must travel.
        """
        try:
            failed = restore_dacl_snapshots(
                snapshots, _set_dacl_sddl)
        except Exception:
            failed = [path for path, sddl in snapshots]
        if failed:
            try:
                by_path = dict(grants)
                remove_app_container_grants(
                    sid, [(path, by_path[path])
                          for path in failed if path in by_path])
            except Exception:
                pass

    def remove_app_container_grants(sid, grants):
        """Revoke exactly the recorded grant set: the job end
        removal. Best effort per path, in reverse order; a
        path whose revocation fails is the caller's to log,
        and the names are returned for that.
        """
        failed = []
        for path, access in reversed(list(grants)):
            mask = GENERIC_ALL_ACCESS \
                if access == "read_write_execute" \
                else GENERIC_READ_EXECUTE_ACCESS
            if _set_entries_in_acl(
                    path, sid, mask, REVOKE_ACCESS) is not None:
                failed.append(path)
        return failed

    def app_container_grants(work_dir, read_paths=()):
        """The recorded grant set currently granted to the
        container SID for a spawn in `work_dir`: what
        _grant_app_container_paths granted, in its recorded
        shape. On this backend the record is the grant set
        itself; app_container_grant_set builds it.
        """
        return app_container_grant_set(work_dir, read_paths)

    def _set_entries_in_acl_on_handle(handle, sid, mask, mode,
                                      label):
        """None once one entry for `sid` at `mask` has been
        added to (GRANT_ACCESS) or revoked from (REVOKE_ACCESS)
        the DACL of the kernel object `handle` already
        carries, else the problem. The handle form of
        _set_entries_in_acl, for the session objects (window
        station and desktop) that have handles, not paths.
        The grant is additive, exactly as there: the existing
        DACL is read, merged, and written back.
        """
        dacl = wintypes.LPVOID()
        sd = wintypes.LPVOID()
        rc = advapi32.GetSecurityInfo(
            handle, SE_WINDOW_OBJECT, DACL_SECURITY_INFORMATION,
            None, None, ctypes.byref(dacl), None,
            ctypes.byref(sd))
        if rc != 0:
            return "GetSecurityInfo(%s) failed: %d" % (label, rc)
        try:
            ea = EXPLICIT_ACCESS_W()
            ea.grfAccessPermissions = mask
            ea.grfAccessMode = mode
            ea.grfInheritance = 0
            ea.Trustee.TrusteeForm = TRUSTEE_IS_SID
            ea.Trustee.TrusteeType = TRUSTEE_IS_UNKNOWN
            ea.Trustee.ptstrName = sid
            new_dacl = wintypes.LPVOID()
            rc = advapi32.SetEntriesInAclW(
                1, ctypes.byref(ea), dacl, ctypes.byref(new_dacl))
            if rc != 0:
                return "SetEntriesInAclW(%s) failed: %d" % (
                    label, rc)
            try:
                rc = advapi32.SetSecurityInfo(
                    handle, SE_WINDOW_OBJECT,
                    DACL_SECURITY_INFORMATION, None, None,
                    new_dacl, None)
                if rc != 0:
                    return "SetSecurityInfo(%s) failed: %d" % (
                        label, rc)
                return None
            finally:
                kernel32.LocalFree(new_dacl)
        finally:
            kernel32.LocalFree(sd)

    def _session_object_handles():
        """((kind, handle, mask), ...) for the creating
        process's own window station and the calling thread's
        desktop, in the recorded grant plan's order, or a
        problem string. The handles are the session's own:
        neither is closed here or by the caller (a process's
        window station handle and a thread's desktop handle
        are owned by the session, not by this code).
        """
        winsta = user32.GetProcessWindowStation()
        if not winsta:
            return None, "GetProcessWindowStation failed: %d" % (
                ctypes.get_last_error(),)
        desktop = user32.GetThreadDesktop(
            kernel32.GetCurrentThreadId())
        if not desktop:
            return None, "GetThreadDesktop failed: %d" % (
                ctypes.get_last_error(),)
        handles = {"window_station": winsta, "desktop": desktop}
        return [(kind, handles[kind], mask)
                for kind, mask
                in app_container_session_grant_set()], None

    def _grant_app_container_session_objects(sid):
        """(granted, problem): grant the container SID the
        recorded session object access (app_container_session_
        grant_set) on the creating process's window station
        and desktop. `granted` is the recorded plan once every
        grant stands; on a problem it is empty, every grant
        this call already made is revoked again, and no spawn
        follows.
        """
        objects, problem = _session_object_handles()
        if problem is not None:
            return [], problem
        granted = []
        for kind, handle, mask in objects:
            problem = _set_entries_in_acl_on_handle(
                handle, sid, mask, GRANT_ACCESS, kind)
            if problem is not None:
                _remove_app_container_session_object_grants(
                    sid, granted)
                return [], problem
            granted.append((kind, mask))
        return granted, None

    def _remove_app_container_session_object_grants(sid,
                                                    granted):
        """Revoke exactly the recorded session object grants,
        in reverse order. Best effort per object; the kinds
        whose revocation failed are returned for the caller
        to log.
        """
        failed = []
        objects, problem = _session_object_handles()
        if problem is not None:
            return [kind for kind, mask in granted]
        handles = {kind: handle for kind, handle, mask in objects}
        for kind, mask in reversed(list(granted)):
            if _set_entries_in_acl_on_handle(
                    handles[kind], sid, mask, REVOKE_ACCESS,
                    kind) is not None:
                failed.append(kind)
        return failed

    def app_container_session_grants():
        """The recorded session object grant set for an
        AppContainer spawn: what _grant_app_container_session_
        objects grants, in its recorded shape.
        """
        return app_container_session_grant_set()

    def spawn_app_container_process(argv, cwd=None, env=None,
                                    read_paths=()):
        """Create a job process inside the AppContainer.

        The container SID is derived from APP_CONTAINER_NAME,
        granted full access to the work directory `cwd` (and
        read plus execute on `read_paths`) before spawn, and
        granted the recorded session object access
        (app_container_session_grant_set) on the creating
        process's window station and desktop, without which a
        target whose load set initializes against them dies
        at DLL initialization (the Lane 7 measurement). The
        process is created suspended through CreateProcessW
        with a SECURITY_CAPABILITIES carrying no capability
        SIDs, assigned to the Job Object, and only then resumed.
        Returns a WindowsConfinedProcess whose
        .confinement_status is the extended string and whose
        .app_container_grants records what was granted. Raises
        RuntimeError when any step fails; there is no
        unconfined fallback inside this spawn (the floor
        fallback lives in spawn_confined_process, which chooses
        between this spawn and the floor spawn).
        """
        if not isinstance(argv, (list, tuple)) or not argv \
                or not all(isinstance(a, str) for a in argv):
            raise RuntimeError(
                "AppContainer spawn needs a non-empty list of "
                "strings")
        if not cwd:
            raise RuntimeError(
                "AppContainer spawn needs a work directory to "
                "grant the container")
        # The target program's own directory is a read path
        # of every spawn, granted by the spawn itself and
        # recorded in the grant set like any other: a container
        # whose SID cannot read the program's directory cannot
        # map the image or the libraries beside it, and the
        # process dies at load with STATUS_DLL_NOT_FOUND before
        # a line runs (the Lane 6 re run's measurement, on the
        # rig's own interpreter tree). A bare program name with
        # no directory names nothing to grant; the loader's
        # search then decides, and the trial names the outcome.
        exe_dir = os.path.dirname(argv[0])
        if exe_dir:
            read_paths = (os.path.abspath(exe_dir),) \
                + tuple(read_paths or ())
        sid, problem = _derive_app_container_sid()
        if problem is not None:
            raise RuntimeError(problem)
        try:
            sid_text, problem = _sid_to_string(sid)
            if problem is not None:
                raise RuntimeError(problem)
            grants, snapshots, problem = \
                _grant_app_container_paths_with_snapshots(
                    sid, cwd, read_paths)
            if problem is not None:
                raise RuntimeError(problem)
            # The session object grants stand beside the path
            # grants, in the same recorded and revoked shape:
            # a target whose load set initializes against the
            # window station and desktop (USER32 and every
            # library built on it, powershell.exe and
            # whoami.exe the measured cases) dies at DLL
            # initialization when the container SID holds no
            # access to them, before a line of the job runs
            # (the Lane 7 measurement, recorded in the header).
            session_grants, problem = \
                _grant_app_container_session_objects(sid)
            if problem is not None:
                try:
                    _restore_failed_spawn_dacls(
                        snapshots, sid, grants)
                except Exception:
                    pass
                raise RuntimeError(problem)
            caps_dict = build_security_capabilities(sid_text)
            caps = SECURITY_CAPABILITIES()
            caps.AppContainerSid = sid
            caps.Capabilities = None
            caps.CapabilityCount = caps_dict["capability_count"]
            caps.Reserved = 0
            job, problem = _create_job_with_limits(
                DEFAULT_PROCESS_MEMORY_BYTES)
            if problem is not None:
                try:
                    _remove_app_container_session_object_grants(
                        sid, session_grants)
                except Exception:
                    pass
                try:
                    _restore_failed_spawn_dacls(
                        snapshots, sid, grants)
                except Exception:
                    pass
                raise RuntimeError(problem)
            # TEMP and TMP point at the work directory for a
            # container process: the container can write there
            # under its grants, and the host's temp tree is
            # outside them by design.
            ac_env = dict(env) if env is not None \
                else dict(os.environ)
            ac_env["TEMP"] = cwd
            ac_env["TMP"] = cwd
            try:
                proc = _spawn_suspended(argv, cwd, ac_env, job,
                                        None, capabilities=caps)
            except Exception:
                # A failed spawn puts back the grants it made
                # before the failure travels: a container SID
                # entry left standing on a granted path is not
                # inert. On a library file it makes the floor's
                # restricted token unable to load that library
                # at all (STATUS_DLL_NOT_FOUND at process
                # creation, the Lane 6 re run's second
                # measurement, isolated in both directions on
                # the rig), so a leaked grant on an interpreter
                # tree silently breaks the floor the spawn was
                # supposed to fall back to. The putting back is
                # the snapshot restore, not entry surgery: the
                # 2026-11-23 rig diagnosis proved the surgery
                # itself leaves the residue when a revoke call
                # does not return inside its timeout, while a
                # snapshot written back whole leaves the path
                # exactly as it was found. The successful
                # spawn's grants are revoked at job end by the
                # process's close, exactly as before.
                try:
                    _restore_failed_spawn_dacls(
                        snapshots, sid, grants)
                except Exception:
                    pass
                try:
                    _remove_app_container_session_object_grants(
                        sid, session_grants)
                except Exception:
                    pass
                raise
        finally:
            kernel32.LocalFree(sid)
        proc.confinement_status = STATUS_APP_CONTAINER
        proc.app_container_session_grants = session_grants
        proc.app_container_grants = grants
        # The grants are removed at job end: the process's
        # release (close, which the spawn seam calls once the
        # process has exited) revokes exactly the recorded set
        # before it closes the handles.
        _base_close = proc.close
        _grant_sid, _p = _derive_app_container_sid()

        def _close_with_grant_removal():
            try:
                if _grant_sid:
                    remove_app_container_grants(_grant_sid, grants)
                    _remove_app_container_session_object_grants(
                        _grant_sid, session_grants)
                    kernel32.LocalFree(_grant_sid)
            except Exception:
                pass
            _base_close()

        proc.close = _close_with_grant_removal
        return proc

    _ac_trial_lock = threading.Lock()
    _ac_trial_verdict = []

    # The job shape probe's shape: the runner's Windows job
    # interpreter in the shape exec builds it (the powershell
    # argv of runner.py, bare name first), printing one
    # marker line. The trial proves the container with the
    # host's interpreter; this probe proves it for the
    # interpreter the jobs actually run, and the verdict
    # below requires both (see appcontainer_job_shape_problem
    # and the module header's 2026-11-22 measurement).
    AC_JOB_SHAPE_MARKER = "AC-JOBSHAPE-OK"
    AC_JOB_SHAPE_ARGV = [
        "powershell", "-NoProfile", "-NonInteractive",
        "-Command", "Write-Output " + AC_JOB_SHAPE_MARKER]

    def windows_app_container_problem(cfg=None, timeout=60):
        """None when the AppContainer trial proves the control
        on this host, else the named failure. Cached for the
        life of the process, exactly as the floor trial's
        verdict is: the per job gate consults the floor probe,
        and this verdict decides only whether the status may
        name app_container and whether spawn_confined_process
        may choose the AppContainer spawn.

        The verdict is the trial's verdict, and, when the
        trial passes, the job shape probe's: a container that
        works for the trial's interpreter but cannot run the
        job interpreter has not proved the control for the
        work this runner does, and its problem names that,
        so the gate falls back to the floor on a named reason
        instead of engaging a control every job would fail
        inside.
        """
        with _ac_trial_lock:
            if not _ac_trial_verdict:
                def _trial_grant(paths):
                    sid, problem = _derive_app_container_sid()
                    if problem is not None:
                        return problem
                    try:
                        sid_text, problem = _sid_to_string(sid)
                        if problem is not None:
                            return problem
                        for path in paths:
                            problem = _set_entries_in_acl(
                                path, sid, GENERIC_ALL_ACCESS,
                                GRANT_ACCESS)
                            if problem is not None:
                                return problem
                        return None
                    finally:
                        kernel32.LocalFree(sid)

                problem = appcontainer_trial_problem(
                    spawn_app_container_process,
                    grant=_trial_grant)
                if problem is None:
                    problem = appcontainer_job_shape_problem(
                        spawn_app_container_process,
                        list(AC_JOB_SHAPE_ARGV),
                        AC_JOB_SHAPE_MARKER, timeout=timeout)
                _ac_trial_verdict.append(problem)
            return _ac_trial_verdict[0]

    def spawn_confined_process(argv, cwd=None, env=None):
        """Create a job process under every confinement control
        the host has proved.

        When the AppContainer trial has proved the control on
        this host (its cached verdict is None), the AppContainer
        spawn is used and the process carries the extended
        status. When it has not, or when the AppContainer spawn
        itself fails at job time, the floor spawn above runs,
        exactly as it always has, and the process carries the
        floor status. There is no unconfined fallback either
        way.

        The seam consults the verdict, not only the cache: a
        spawn reached on a process whose gate has not run yet
        (a start shape that services a job before any startup
        or per job gate call landed on this module instance)
        computes the verdict here, through the same cached
        trial the gate consults, instead of reading an empty
        cache as a floor verdict. An empty cache was never a
        verdict; treating it as one silently floored every
        job in any start shape whose first confinement call
        was a spawn (the Lane 8 diagnosis, recorded in the
        header).
        """
        verdict = _ac_trial_verdict[0] if _ac_trial_verdict \
            else windows_app_container_problem()
        if app_container_boundary_crossing(verdict):
            raise RuntimeError(verdict)
        if verdict is None and cwd:
            try:
                return spawn_app_container_process(
                    argv, cwd=cwd, env=env)
            except RuntimeError:
                pass
        return _spawn_floor_confined_process(argv, cwd=cwd, env=env)

    def _spawn_floor_confined_process(argv, cwd=None, env=None):
        """Create a job process under the floor controls alone.

        argv is the full command (interpreter, script, args). The
        process is created suspended under the restricted,
        low-integrity token, assigned to the Job Object, and only
        then resumed. Returns a WindowsConfinedProcess whose
        .confinement_status is STATUS_CONFINEMENT. Raises
        RuntimeError when any control could not be applied --
        there is no unconfined fallback to fall through to. This
        is the spawn the floor trial tests, and the spawn
        spawn_confined_process falls back to whenever the
        AppContainer control is not proved on the host.
        """
        if not isinstance(argv, (list, tuple)) or not argv \
                or not all(isinstance(a, str) for a in argv):
            raise RuntimeError(
                "confined spawn needs a non-empty list of strings")
        job, problem = _create_job_with_limits(
            DEFAULT_PROCESS_MEMORY_BYTES)
        if problem is not None:
            raise RuntimeError(problem)
        token, problem = _create_restricted_low_token()
        if problem is not None:
            kernel32.CloseHandle(job)
            raise RuntimeError(problem)
        if cwd:
            _set_low_integrity_label(cwd)
        proc = _spawn_suspended(argv, cwd, env, job, token)
        proc.confinement_status = STATUS_CONFINEMENT
        return proc

    def spawn_job_object_process(argv, cwd=None, env=None):
        """Create a job process under the job_user control alone.

        argv is the full command (interpreter, script, args). The
        process is created suspended through CreateProcessW under
        the caller's own token -- no restricted token and no
        integrity label are applied, and no record of this spawn
        may name them -- assigned to the Job Object carrying the
        memory ceiling, and only then resumed (Q168: the
        post-start assignment this spawn replaces raced a child
        that could exit before it was assigned). Returns a
        WindowsConfinedProcess whose .job_object_status is
        STATUS_JOB_OBJECT; its close() is the release, closing
        the Job Object once the process has exited. Raises
        RuntimeError when the control could not be applied --
        there is no running-then-assigned fallback to fall
        through to.
        """
        if not isinstance(argv, (list, tuple)) or not argv \
                or not all(isinstance(a, str) for a in argv):
            raise RuntimeError(
                "job-object spawn needs a non-empty list of strings")
        job, problem = _create_job_with_limits(
            DEFAULT_PROCESS_MEMORY_BYTES)
        if problem is not None:
            raise RuntimeError(problem)
        proc = _spawn_suspended(argv, cwd, env, job, None)
        proc.job_object_status = STATUS_JOB_OBJECT
        return proc

# The confinement trial (Q134). The orchestration is platform-
# neutral -- it stages files in a temp tree and drives a spawn
# callable -- so the suite exercises it through scripted spawn
# seams on any host; on a real Windows host the backend's
# windows_confinement_problem wires it to spawn_confined_process
# and caches the verdict (see there). The trial program is a
# staged .py file, not a -c string: the confined process reads
# two staged files (the program, then the data file it is
# handed) and writes a third into its work directory, which is
# the shape of a real job's staged script and outputs.
_TRIAL_MARKER = "hp-confinement-trial"

# The group the confined token carries enabled on every host
# shape the backend runs on, and the DACL the trial's grant
# assures on its staged tree: SYSTEM and Administrators at
# full control (the runner keeps ownership of its own tree),
# BUILTIN\Users at generic read+execute, every ACE inheriting
# to what is staged inside. The confined token disables
# Administrators and is not SYSTEM, so neither the temp
# directory's inheritance nor mkdtemp's owner-only DACL can
# be relied on to name a group the token holds (the Q134
# addendum); this DACL names one, explicitly.
TRIAL_USERS_SID = "S-1-5-32-545"
TRIAL_GRANT_SDDL = (
    "D:(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"
    "(A;OICI;GRGX;;;%s)" % TRIAL_USERS_SID)

_TRIAL_PROGRAM = (
    "import os, sys\n"
    "data = open(sys.argv[1], encoding='utf-8').read()\n"
    "assert 'hp-confinement-trial' in data, 'marker missing'\n"
    "print('TRIAL-READ-OK', flush=True)\n"
    "out = os.path.join(sys.argv[2], 'trial-out.txt')\n"
    "with open(out, 'w', encoding='utf-8') as fh:\n"
    "    fh.write(data)\n"
    "print('TRIAL-WRITE-OK', flush=True)\n"
)


def _trial_tail(text):
    """The last non-empty line of a trial process's output."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1][:200] if lines else "no output"


def _stage_trial_tree():
    """(root, staged, program, work) for 1 trial run.

    The tree is created with os.makedirs at the default mode,
    never tempfile.mkdtemp: mkdtemp's directory is mode 0o700,
    and on Windows its DACL names only SYSTEM, Administrators
    and OWNER RIGHTS -- none of which the confined token
    holds enabled (the Q134 addendum) -- so under an elevated
    administrator the trial refused its own staging and named
    the host unable. A default-mode directory inherits the
    temp directory's DACL instead, and the trial's grant hook
    then makes the token's access explicit. The name is
    random for the same reason mkdtemp's was: the tree must
    not be predictable to anything else on the host. A
    staging failure removes whatever was created and raises;
    the trial answers it as its staging problem.
    """
    parent = tempfile.gettempdir()
    root = None
    for _attempt in range(100):
        candidate = os.path.join(
            parent,
            "hp-confinement-trial-" + os.urandom(8).hex())
        try:
            os.makedirs(candidate)
            root = candidate
            break
        except FileExistsError:
            continue
    if root is None:
        raise OSError(
            "no free name for the confinement trial's staging "
            "directory under %s" % (parent,))
    try:
        staged = os.path.join(root, "trial-staged.txt")
        with open(staged, "w", encoding="utf-8") as fh:
            fh.write(_TRIAL_MARKER + "\n")
        program = os.path.join(root, "trial_program.py")
        with open(program, "w", encoding="utf-8") as fh:
            fh.write(_TRIAL_PROGRAM)
        work = os.path.join(root, "work")
        os.makedirs(work)
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return root, staged, program, work


def confinement_trial_problem(spawn, timeout=60, grant=None):
    """None when a confined process can work here, else why not.

    `spawn` is a confined-spawn callable with the backend's
    signature -- spawn(argv, cwd=..., env=...) returning a
    process object with communicate(timeout), kill(), close()
    and returncode. The trial stages a data file and a program
    in a fresh temp tree, spawns the program confined with the
    tree's work directory as its cwd, and names the stage that
    failed: the spawn itself, the staged read, or the work-
    directory write. The temp tree is removed either way. A
    host whose confined processes cannot read what is staged
    for them answers a problem here, at startup, instead of
    failing every job.

    `grant`, when given, is called with the staged paths
    (root, data file, program, work directory) once they
    exist and before the spawn, and returns None when the
    confined token is assured it can open them, or the
    problem. The real backend passes its DACL grant
    (TRIAL_GRANT_SDDL): staging alone cannot promise the
    token access, because a temp tree's inherited DACL is the
    host's accident, and on an elevated host it names no
    group the token holds enabled. A grant that answers a
    problem -- or raises -- is the trial's answer: the
    startup gate refuses with it rather than run a trial
    against staging the confined process cannot open.
    """
    tmp = None
    try:
        tmp, staged, program, work = _stage_trial_tree()
        if grant is not None:
            try:
                problem = grant([tmp, staged, program, work])
            except Exception as e:
                problem = "%s" % (e,)
            if problem is not None:
                return ("confined trial could not make its "
                        "staged tree readable by the confined "
                        "token: %s" % (problem,))
        argv = [sys.executable, program, staged, work]
        try:
            proc = spawn(argv, cwd=work, env=dict(os.environ))
        except Exception as e:
            return "confined trial spawn failed: %s" % (e,)
        try:
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                return ("confined trial timed out after %ss; a "
                        "confined process could not finish "
                        "reading its staged file and writing its "
                        "work directory" % (timeout,))
            out_text = out.decode("utf-8", "replace") \
                if isinstance(out, (bytes, bytearray)) else str(out or "")
            err_text = err.decode("utf-8", "replace") \
                if isinstance(err, (bytes, bytearray)) else str(err or "")
            if "TRIAL-READ-OK" not in out_text:
                return ("a confined process could not read its "
                        "staged file (exit %s: %s)"
                        % (proc.returncode,
                           _trial_tail(err_text or out_text)))
            if "TRIAL-WRITE-OK" not in out_text or not os.path.exists(
                    os.path.join(work, "trial-out.txt")):
                return ("a confined process read its staged file "
                        "but could not write its work directory "
                        "(exit %s: %s)"
                        % (proc.returncode,
                           _trial_tail(err_text or out_text)))
            if proc.returncode not in (0, None):
                return ("the confined trial process exited %s "
                        "after reading and writing (%s)"
                        % (proc.returncode, _trial_tail(err_text)))
            return None
        finally:
            try:
                proc.close()
            except Exception:
                pass
    except Exception as e:
        return "confined trial could not be staged: %s" % (e,)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------
# The AppContainer control: the platform neutral half. The name
# validation, the capabilities shape, the grant set and the
# trial's orchestration live here, outside the win32 branch, so
# the suite exercises them on any host through scripted spawn
# seams, exactly as the floor trial's orchestration is exercised.
# The real backend above supplies the OS calls: SID derivation,
# the DACL grant, and the suspended spawn with the attribute
# list.

import re as _re

_APP_CONTAINER_NAME_SHAPE = _re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*")


def validate_app_container_name(name):
    """None when `name` may be handed to
    DeriveAppContainerSidFromAppContainerName, else the problem.

    The shape is deliberately narrow: a string of 1 to
    APP_CONTAINER_NAME_MAX characters, letters, digits, dot,
    underscore and hyphen, starting with a letter or a digit.
    Anything else (empty, whitespace, a path separator, a
    control character, a symbol the shape does not name) is
    refused here, deterministically, on every host, before any
    OS call sees it.
    """
    if not isinstance(name, str):
        return "the AppContainer name must be a string"
    if not name:
        return "the AppContainer name must not be empty"
    if len(name) > APP_CONTAINER_NAME_MAX:
        return ("the AppContainer name must be at most %d "
                "characters" % (APP_CONTAINER_NAME_MAX,))
    if not _APP_CONTAINER_NAME_SHAPE.fullmatch(name):
        return ("the AppContainer name %r is outside the "
                "permitted shape (letters, digits, dot, "
                "underscore and hyphen, starting with a letter "
                "or a digit)" % (name,))
    return None


def build_security_capabilities(app_container_sid,
                                capabilities=()):
    """The SECURITY_CAPABILITIES shape for the spawn, as a dict
    the suite can pin: the container SID, an empty capability
    tuple, a capability count of 0 and a reserved field of 0.

    The empty set is the control: a container with no network
    capability SID has no network. Passing any capability is an
    error, never a wider container: this backend grants no
    capabilities, by design, and a caller asking for one has
    asked for a different backend.
    """
    if capabilities:
        raise ValueError(
            "this backend builds AppContainer capabilities with "
            "no capability SIDs; %r was asked for"
            % (list(capabilities),))
    if app_container_sid is None or app_container_sid == "":
        raise ValueError(
            "SECURITY_CAPABILITIES needs the container SID")
    return {"app_container_sid": app_container_sid,
            "capabilities": (),
            "capability_count": 0,
            "reserved": 0}


def proc_thread_attribute_spec(capabilities):
    """The attribute list construction for the spawn, as the
    pair the real backend hands UpdateProcThreadAttribute: the
    attribute number PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES
    and the capabilities dict build_security_capabilities made.
    A capabilities shape with a nonzero count is refused here
    too, so no path to the attribute list carries a capability
    this backend did not mean to grant.
    """
    if not isinstance(capabilities, dict) \
            or capabilities.get("capability_count") != 0 \
            or capabilities.get("capabilities") != ():
        raise ValueError(
            "the attribute list takes only the empty capability "
            "set this backend builds")
    return (PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
            capabilities)


def app_container_ancestor_dirs(path):
    """The ancestor directories of `path`, nearest first,
    stopping below the root of its drive or tree: for a path
    three levels deep, its parent and its grandparent, and
    never the root itself. A relative path with no directory
    part has none. Pure path arithmetic, on any host, so the
    grant set's shape can be pinned by the suite anywhere.

    The root stands outside the walk on purpose (the
    2026-11-23 residue fix). The grant this list feeds is a
    security write on every ancestor, and on the project's
    own rig the write on the drive root did not return
    inside its timeout, which is the hang the whole residue
    cycle hangs from. No contained process needs the root
    granted: it walks the ancestors below the root, which
    all stand in the set, and a host whose root names
    nothing the container token holds fails the AppContainer
    trial and falls back to the floor, the designed answer,
    instead of hanging a grantor call on the one path every
    other path hangs under.
    """
    out = []
    node = os.path.dirname(path)
    while node and node not in out:
        parent = os.path.dirname(node)
        if parent == node:
            break
        out.append(node)
        node = parent
    return out


def app_container_grant_set(work_dir, read_paths=()):
    """The recorded grant set for an AppContainer spawn: a list
    of (path, access) pairs, the work directory first at "full",
    then each read path at "read_execute", then every ancestor
    directory of the work directory and of each read path at
    "read_execute", deduplicated, in order. This set is the
    whole grant: the container SID gets access to these paths
    and to nothing else, and the spawn records exactly this
    list so what was granted can be reported and revoked. An
    empty work directory is an error.

    The ancestors stand in the set because a contained
    process must be able to walk the path to the directory
    it was granted (the Lane 8 measurement, recorded in the
    header): the job interpreter's shell resolves its own
    standing in the work directory by opening the directory
    and its ancestors, and where an ancestor's DACL names
    nothing the container token holds (a profile tree is the
    measured case), the shell either falls back to a drive
    root it can open, so its relative paths silently
    resolve somewhere else, or refuses to stand there at
    all and the process exits before a line of the job
    runs. A grant on the leaf alone is a grant the job
    cannot always reach.
    """
    if not isinstance(work_dir, str) or not work_dir:
        raise ValueError(
            "an AppContainer grant set needs a work directory")
    grants = [(work_dir, "read_write_execute")]
    seen = {work_dir}
    named = [work_dir]
    for path in read_paths or ():
        if not isinstance(path, str) or not path:
            raise ValueError(
                "an AppContainer read path must be a non-empty "
                "string")
        if path in seen:
            continue
        seen.add(path)
        named.append(path)
        grants.append((path, "read_execute"))
    for path in named:
        for ancestor in app_container_ancestor_dirs(path):
            if ancestor in seen:
                continue
            seen.add(ancestor)
            grants.append((ancestor, "read_execute"))
    return grants


def take_dacl_snapshots(paths, snapshot):
    """(snapshots, problem): the DACL snapshot of every path
    in `paths`, in order, taken before any grant stands.

    `snapshot(path)` answers (sddl, problem): the path's DACL
    in SDDL, the form the operating system itself round
    trips, or the problem that kept it from being read. The
    snapshots are all or nothing: the first path that cannot
    be snapshotted answers its problem with no snapshots at
    all, because the caller's rule is that a grant it cannot
    put back whole is a grant it does not make (the
    2026-11-23 residue fix: a failed spawn restores these
    snapshots whole instead of editing the entries it added
    back out, one timed call per path, which is the surgery
    that left the residue standing).
    """
    snapshots = []
    for path in paths:
        sddl, problem = snapshot(path)
        if problem is not None:
            return [], problem
        snapshots.append((path, sddl))
    return snapshots, None


def restore_dacl_snapshots(snapshots, set_dacl):
    """The paths whose snapshot could not be put back, in
    the order attempted: every snapshot is written back,
    in reverse order, through `set_dacl(path, sddl)`, which
    answers None once the DACL stands or the problem. One
    path's failure does not stop the rest: a partial restore
    reported whole is worth more than a restore that gives
    up at its first failure and leaves the remainder
    unreported.
    """
    failed = []
    for path, sddl in reversed(list(snapshots)):
        if set_dacl(path, sddl) is not None:
            failed.append(path)
    return failed


# The floor trial's death at load: the confined process's
# exit when the loader cannot map the interpreter's own
# libraries, as a signed and an unsigned value. Python
# reports the exit as the signed NTSTATUS on Windows; the
# unsigned form is the same code read as a process exit
# code, and the gate accepts either spelling.
DLL_NOT_FOUND_EXIT_SIGNED = -1073741515
DLL_NOT_FOUND_EXIT_UNSIGNED = 3221225781


def floor_trial_dll_not_found(problem):
    """True when a floor trial problem is the staged read
    failure with exit STATUS_DLL_NOT_FOUND (0xC0000135):
    the confined process died at load, before it ran a line,
    which is the shape a poisoned interpreter DACL leaves.
    Any other failure, including the same exit at the write
    stage, is not this shape: a process that read its staged
    file got past the loader, so its death has another cause
    and the gate must not name this one.
    """
    if not problem:
        return False
    if "could not read its staged file" not in problem:
        return False
    # The trial spells the exit as "(exit %s: ...)": the
    # colon the format puts after the number is part of the
    # match, so a longer number the exit is only a prefix
    # of is not this shape either.
    return ("exit %d:" % DLL_NOT_FOUND_EXIT_SIGNED) in problem \
        or ("exit %d:" % DLL_NOT_FOUND_EXIT_UNSIGNED) in problem


def grant_residue_problem(floor_problem, interpreter_path):
    """The startup gate's name for the grant residue shape:
    the floor trial's own problem, then what the shape is
    and what clears it. `interpreter_path` is the path whose
    DACL carries the container SID (the interpreter's own
    directory, in the measured case). The trial's words
    stand first and whole: this naming adds the diagnosis,
    it does not replace the verdict it was read from.
    """
    return (
        "%s This failure has the AppContainer grant residue "
        "shape: the confined trial process died with "
        "STATUS_DLL_NOT_FOUND (0xC0000135) before running a "
        "line, and %s carries a grant for the AppContainer "
        "SID, left standing by a failed AppContainer spawn. "
        "The confined loader cannot map the interpreter's "
        "own libraries through that DACL, so every start "
        "fails the same way until the grant is gone. Reset "
        "the DACL of %s to its inherited defaults (icacls "
        "\"%s\" /reset /T), or remove the AppContainer SID's "
        "entry from it, then start again."
        % (floor_problem, interpreter_path, interpreter_path,
           interpreter_path))


def app_container_session_grant_set():
    """The recorded session object grant set for an
    AppContainer spawn: a list of (object, access mask) pairs,
    the creating process's window station first, then its
    desktop, at exactly the access the Lane 7 measurement
    found sufficient and necessary (WINDOW_STATION_CONTAINER_
    ACCESS and DESKTOP_CONTAINER_ACCESS). This set is the
    whole session grant: the container SID gets this access
    to these two objects and to no other session object, and
    neither mask carries a create, write, switch, read screen
    or clipboard right. The spawn records exactly this list
    so what was granted can be reported and revoked.
    """
    return [("window_station", WINDOW_STATION_CONTAINER_ACCESS),
            ("desktop", DESKTOP_CONTAINER_ACCESS)]


# HRESULT ERROR_ALREADY_EXISTS, as an unsigned value: the
# answer CreateAppContainerProfile gives when the profile
# already stands, which is the design's signal to fall back to
# deriving the SID from the name.
ERROR_ALREADY_EXISTS_HRESULT = 0x800700B7


def profile_creation_outcome(hresult):
    """What a CreateAppContainerProfile result means, as a
    word: "created" for success, "exists" for
    ERROR_ALREADY_EXISTS (the profile stands; derive the SID
    from the name), and "failed" for anything else. The
    profile is created once, never per job, and deleted only
    at uninstall; this word is how the once is decided.
    """
    hr = hresult & 0xFFFFFFFF
    if hr == 0:
        return "created"
    if hr == ERROR_ALREADY_EXISTS_HRESULT:
        return "exists"
    return "failed"


def app_container_boundary_crossing(problem):
    """True when an AppContainer trial verdict is a boundary
    crossing: the container reached something it should not
    have (a read or write outside its grants, or the network).
    A crossing is not a missing mechanism. The design's
    deliberate asymmetry: a missing mechanism falls back to
    the floor, a crossing refuses outright at startup.
    """
    return bool(problem) and problem.startswith(
        "AppContainer boundary crossing")


def confinement_gate_problem(floor_problem, app_container_problem):
    """The startup gate's answer from the two trial verdicts:
    the floor's problem when the floor itself failed; the
    AppContainer problem when it is a boundary crossing; and
    None otherwise, because a merely unavailable AppContainer
    leaves the floor standing exactly as it was.
    """
    if floor_problem is not None:
        return floor_problem
    if app_container_boundary_crossing(app_container_problem):
        return app_container_problem
    return None


_AC_TRIAL_PROGRAM = (
    "import os, socket, sys\n"
    "try:\n"
    "    data = open(sys.argv[1], encoding='utf-8').read()\n"
    "    assert 'hp-confinement-trial' in data, 'marker missing'\n"
    "    print('AC-READ-OK', flush=True)\n"
    "except Exception as e:\n"
    "    print('AC-READ-FAIL %s' % (e,), flush=True)\n"
    "try:\n"
    "    out = os.path.join(sys.argv[2], 'ac-trial-out.txt')\n"
    "    with open(out, 'w', encoding='utf-8') as fh:\n"
    "        fh.write('ok\\n')\n"
    "    print('AC-WRITE-OK', flush=True)\n"
    "except Exception as e:\n"
    "    print('AC-WRITE-FAIL %s' % (e,), flush=True)\n"
    "try:\n"
    "    open(sys.argv[3], encoding='utf-8').read()\n"
    "    print('AC-OUTSIDE-OPEN', flush=True)\n"
    "except Exception:\n"
    "    print('AC-OUTSIDE-REFUSED', flush=True)\n"
    "try:\n"
    "    fh = open(sys.argv[3], 'a', encoding='utf-8')\n"
    "    fh.write('x')\n"
    "    fh.close()\n"
    "    print('AC-OUTSIDE-WRITE-OPEN', flush=True)\n"
    "except Exception:\n"
    "    print('AC-OUTSIDE-WRITE-REFUSED', flush=True)\n"
    "try:\n"
    "    import ctypes\n"
    "    from ctypes import wintypes\n"
    "    tok = wintypes.HANDLE()\n"
    "    adv = ctypes.windll.advapi32\n"
    "    ker = ctypes.windll.kernel32\n"
    "    adv.OpenProcessToken(ker.GetCurrentProcess(), 0x0008,\n"
    "        ctypes.byref(tok))\n"
    "    val = wintypes.DWORD(0)\n"
    "    adv.GetTokenInformation(tok, 29, ctypes.byref(val), 4,\n"
    "        ctypes.byref(wintypes.DWORD(0)))\n"
    "    print('AC-TOKEN-APPCONTAINER' if val.value else\n"
    "        'AC-TOKEN-PLAIN', flush=True)\n"
    "except Exception as e:\n"
    "    print('AC-TOKEN-UNKNOWN %s' % (e,), flush=True)\n"
    "try:\n"
    "    sock = socket.create_connection(\n"
    "        ('127.0.0.1', 9), timeout=3)\n"
    "    sock.close()\n"
    "    print('AC-NETWORK-OPEN', flush=True)\n"
    "except Exception:\n"
    "    print('AC-NETWORK-REFUSED', flush=True)\n"
)


def _stage_appcontainer_trial_tree():
    """(root, staged, program, work, outside) for 1 run.

    The granted tree follows _stage_trial_tree's staging: a
    default mode directory the grant hook then makes explicit.
    The outside file lives in its own sibling tree, which no
    grant names: that separation is what check (c) measures.
    """
    root, staged, program, work = _stage_trial_tree()
    try:
        with open(program, "w", encoding="utf-8") as fh:
            fh.write(_AC_TRIAL_PROGRAM)
        parent = tempfile.gettempdir()
        outside_root = None
        for _attempt in range(100):
            candidate = os.path.join(
                parent,
                "hp-appcontainer-outside-" + os.urandom(8).hex())
            try:
                os.makedirs(candidate)
                outside_root = candidate
                break
            except FileExistsError:
                continue
        if outside_root is None:
            raise OSError(
                "no free name for the AppContainer trial's "
                "outside directory under %s" % (parent,))
        outside = os.path.join(outside_root, "outside.txt")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write(_TRIAL_MARKER + "\n")
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return root, staged, program, work, outside


def appcontainer_trial_problem(spawn, timeout=60, grant=None):
    """None when an AppContainer process works contained here,
    else the named failure.

    `spawn` is an AppContainer spawn callable with the
    backend's signature. The trial's four checks, each named
    when it fails: the process (a) reads a staged file it was
    granted, (b) writes its work directory, (c) attempts a
    read outside its granted paths and is refused, and (d)
    attempts network access and is refused, (e) attempts a
    write outside its granted paths and is refused, and (f)
    reads its own token from inside and finds an AppContainer
    token. A boundary check
    that comes back open is a failure of the control, named as
    such: a container that can read outside its grants or
    reach the network is not confining, whatever its spawn
    claimed. `grant`, when given, is called with the granted
    paths (root, data file, program, work directory) before
    the spawn and answers None or the problem, in the floor
    trial's shape; the outside file is never in that list.
    """
    tmp = None
    outside_root = None
    try:
        tmp, staged, program, work, outside = \
            _stage_appcontainer_trial_tree()
        outside_root = os.path.dirname(outside)
        if grant is not None:
            try:
                problem = grant([tmp, staged, program, work])
            except Exception as e:
                problem = "%s" % (e,)
            if problem is not None:
                return ("AppContainer trial could not grant its "
                        "staged tree to the container SID: %s"
                        % (problem,))
        argv = [sys.executable, program, staged, work, outside]
        try:
            proc = spawn(argv, cwd=work, env=dict(os.environ))
        except Exception as e:
            return "AppContainer trial spawn failed: %s" % (e,)
        try:
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                return ("AppContainer trial timed out after "
                        "%ss; a contained process could not "
                        "finish its four checks" % (timeout,))
            out_text = out.decode("utf-8", "replace") \
                if isinstance(out, (bytes, bytearray)) \
                else str(out or "")
            err_text = err.decode("utf-8", "replace") \
                if isinstance(err, (bytes, bytearray)) \
                else str(err or "")
            tail = _trial_tail(err_text or out_text)
            if "AC-READ-OK" not in out_text:
                return ("an AppContainer process could not read "
                        "its granted staged file (exit %s: %s)"
                        % (proc.returncode, tail))
            if "AC-WRITE-OK" not in out_text:
                return ("an AppContainer process read its "
                        "granted staged file but could not write "
                        "its work directory (exit %s: %s)"
                        % (proc.returncode, tail))
            if "AC-OUTSIDE-OPEN" in out_text:
                return ("AppContainer boundary crossing: an "
                        "AppContainer process read outside its "
                        "granted paths")
            if "AC-OUTSIDE-REFUSED" not in out_text:
                return ("the AppContainer trial could not show "
                        "a read outside the granted paths being "
                        "refused (exit %s: %s)"
                        % (proc.returncode, tail))
            if "AC-OUTSIDE-WRITE-OPEN" in out_text:
                return ("AppContainer boundary crossing: an "
                        "AppContainer process wrote outside its "
                        "granted paths")
            if "AC-OUTSIDE-WRITE-REFUSED" not in out_text:
                return ("the AppContainer trial could not show "
                        "a write outside the granted paths being "
                        "refused (exit %s: %s)"
                        % (proc.returncode, tail))
            if "AC-NETWORK-OPEN" in out_text:
                return ("AppContainer boundary crossing: an "
                        "AppContainer process reached the "
                        "network with no network capability")
            if "AC-NETWORK-REFUSED" not in out_text:
                return ("the AppContainer trial could not show "
                        "network access being refused (exit %s: "
                        "%s)" % (proc.returncode, tail))
            if "AC-TOKEN-PLAIN" in out_text:
                return ("the AppContainer trial process's "
                        "token is not an AppContainer token "
                        "(exit %s: %s)" % (proc.returncode, tail))
            token_ok = "AC-TOKEN-APPCONTAINER" in out_text
            if not token_ok:
                # The parent side decides when it can: a
                # contained process cannot always report its
                # own token (its ctypes import can fail to
                # initialize under the container token, the
                # Lane 6 re run's measurement), while the
                # spawn's own process object can be asked for
                # the token of the process it created. A spawn
                # seam without that answer (the suite's
                # scripted seams) is judged on the program's
                # own report alone, exactly as before.
                hook = getattr(
                    proc, "is_app_container_token", None)
                if callable(hook):
                    try:
                        token_ok = hook() is True
                    except Exception:
                        token_ok = False
            if not token_ok:
                return ("the AppContainer trial could not read "
                        "an AppContainer token from inside the "
                        "trial process (exit %s: %s)"
                        % (proc.returncode, tail))
            if proc.returncode not in (0, None):
                return ("the AppContainer trial process exited "
                        "%s after its checks (%s)"
                        % (proc.returncode, tail))
            return None
        finally:
            try:
                proc.close()
            except Exception:
                pass
    except Exception as e:
        return "AppContainer trial could not be staged: %s" % (e,)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        if outside_root is not None:
            shutil.rmtree(outside_root, ignore_errors=True)


def appcontainer_job_shape_problem(spawn, argv, marker,
                                   timeout=60):
    """None when a contained process can run the job shape
    the runner actually runs, else the named failure.

    The AppContainer trial above proves the container with
    the host's Python interpreter: a native program whose
    load set sits beside it and in the system tree. A host
    can pass that trial and still fail the runner's real
    work, because the job interpreter is a different load
    shape entirely. On Windows the runner's jobs are
    powershell, a .NET Framework program, and on the
    measured host a managed program does not initialize
    inside a container token at all (STATUS_DLL_INIT_FAILED,
    exit 0xC0000142, before a line of the job runs) while
    native programs run contained on the same host in the
    same minutes; the measurement stands in the module
    header. This probe is the trial's second half: it
    spawns `argv` -- the job interpreter in the job's own
    shape, bare name and all -- in a staged work directory
    through the same AppContainer spawn, and requires the
    process to print `marker` and exit 0 before the verdict
    may name the control. A failure here is a missing
    mechanism, never a boundary crossing: the gate leaves
    the floor standing, the status keeps the floor's name,
    and jobs run under the floor exactly as they did before
    the control existed. On a host where the job shape runs
    contained, the control engages as designed.
    """
    if not argv or not all(
            isinstance(a, str) for a in argv) \
            or not isinstance(marker, str) or not marker:
        return ("the AppContainer job shape probe needs a "
                "job interpreter argv of strings and a marker")
    tmp = None
    try:
        tmp, staged, program, work = _stage_trial_tree()
        try:
            proc = spawn(argv, cwd=work, env=dict(os.environ))
        except Exception as e:
            return ("AppContainer job shape spawn failed: %s"
                    % (e,))
        try:
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                return ("AppContainer job shape timed out "
                        "after %ss; a contained process could "
                        "not finish running the job "
                        "interpreter %s" % (timeout, argv[0]))
            out_text = out.decode("utf-8", "replace") \
                if isinstance(out, (bytes, bytearray)) \
                else str(out or "")
            err_text = err.decode("utf-8", "replace") \
                if isinstance(err, (bytes, bytearray)) \
                else str(err or "")
            tail = _trial_tail(err_text or out_text)
            if marker not in out_text:
                return ("an AppContainer process could not "
                        "run the job interpreter %s to "
                        "completion (exit %s: %s)"
                        % (argv[0], proc.returncode, tail))
            if proc.returncode not in (0, None):
                return ("an AppContainer process printed "
                        "the job shape marker but the job "
                        "interpreter %s exited %s (%s)"
                        % (argv[0], proc.returncode, tail))
            return None
        finally:
            try:
                proc.close()
            except Exception:
                pass
    except Exception as e:
        return ("AppContainer job shape could not be "
                "staged: %s" % (e,))
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
