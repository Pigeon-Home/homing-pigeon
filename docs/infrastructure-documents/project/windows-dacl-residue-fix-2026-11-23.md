# The Windows DACL residue fix: supposition, before the landing

Written 2026-11-23, before any code in this landing was written.
The conclusions section is appended after the tests run, in this
same place, and the change the numbers support follows it.

## What stands

The rig diagnosis of 2026-11-23 (kept with the rig harness notes,
outside this repository) proved a self poisoning cycle in the
Windows backend, end to end, on the project's own Windows rig:

1. With a clean DACL on the interpreter tree, the floor trial
   passes and the runner starts.
2. At that same startup the AppContainer trial runs. Its
   ancestor grant walk reaches the drive root itself, and
   SetNamedSecurityInfoW on the drive root does not return
   inside its timeout on that host, so the trial spawn fails.
3. The failed spawn's cleanup leaves the AppContainer grant
   standing on the interpreter's own directory, in the DACL
   shape the confined loader cannot use.
4. Every later start dies at the floor trial with exit
   0xC0000135 (STATUS_DLL_NOT_FOUND) before writing a log line,
   until the directory's DACL is reset by hand. One reset buys
   exactly one clean start.

The same diagnosis recorded a second, separate fact: on the one
clean run, jobs were confined by the floor alone because the
AppContainer control was unavailable, and the battery's escape
write step failed, because the floor has no filesystem
isolation and the write landed.

## The suppositions

S1. The grant set is where the walk must stop. The recorded
grant set (app_container_grant_set) is built from
app_container_ancestor_dirs, which walks to and includes the
root of the drive or tree. If that walk stops below the root,
no grant in any set this backend builds can name the drive
root, and the hanging call is never made. The contained
process loses nothing it needs: every ancestor below the root
still stands in the set, and a host whose drive root names
nothing the container token holds will fail the AppContainer
trial and fall back to the floor, which is the designed
answer, instead of hanging a grantor call on the root.

S2. Entry surgery under a timeout is the residue mechanism,
and snapshot plus restore is the fix. The failed spawn's
cleanup revokes the grants it made by editing entries, one
call per path, each call able to not return inside its
timeout on this host. A cleanup that snapshots each granted
path's DACL before the first grant stands, and on failure
writes those snapshots back whole, leaves each path exactly
as it found it, in one write per path, with no dependence on
which entries the grant added. A path whose DACL cannot be
snapshotted must not be granted at all: a grant the spawn
cannot put back is a grant it does not make.

S3. The startup gate can name this shape. When the floor
trial dies with 0xC0000135 and the interpreter directory's
DACL carries the container SID, the failure is the residue
shape and not a confinement failure of the host. The gate
already has both halves in reach: the trial verdict carries
the exit, and the backend can read a DACL as SDDL and look
for the SID in it. Naming the shape, and what clears it, in
the refusal turns a day of battery results that read as a
startup failure on every head into one sentence an operator
can act on.

S4. The floor alone cannot block the escape write, and no
honest gate inside the current posture makes it do so. The
floor's controls are a Job Object, a restricted token and a
low integrity level; none of them is a filesystem wall, and
the support matrix already says the floor has no filesystem
namespace isolation. Refusing to start whenever the
AppContainer control is unavailable would repeal the floor
fallback the gate is designed around, so it is not a fix
this landing may smuggle in. The sound treatment is to state
the limit where the claim lives: a blocked escape write is
a property of the AppContainer shape, and under the floor
alone a write to a path the job's token can write can land,
as measured on the rig on 2026-11-23.

## The plan

Test first, in the suite, on any host: the ancestor walk and
the grant set pin the stop below the root; the snapshot and
restore orchestration pins snapshot before grant, all or
nothing, and restore in reverse order; the residue naming
pins the exit shape and the message. The Windows only wiring
is pinned by the suite's source shape tests, as the ACL
helper's inheritance shape already is. Then the code, then
the support matrix sentence for S4. The rig battery watch
proves the landing live on the next heads it runs; this
landing claims the unit level only.

## Conclusions

Written after the tests ran, in the same place, as the rule
asks.

The tests were written first. Over the 2 Windows test modules
the new and changed pins ran red before the code moved: 189
tests, 10 failures and 14 errors, every one of them on a shape
this landing changes (the root standing in the grant set, the
snapshot helpers not yet existing, the residue naming not yet
wired). After the code: the same 189 tests pass, with 1 skip,
the pre-existing live binding test that runs only on a
Windows backend host. A completing pass then widened each
fix's family to the variation standard: 31 further tests over
the walk's odd spellings and generated shapes, the snapshot
orchestration's edge shapes, and the residue recognition's
near shapes (neighbouring exits, the longer number the exit
is only a prefix of, the hex spelling, the same exit at the
other stages), every one of them red before the fix and green
after it, and the recognition itself tightened to read the
colon the trial's format puts after the exit, so the longer
number cannot borrow the shape's name. The 2 Windows modules
stand at 220 tests, all passing, the same 1 skip. The
neighboring modules pass beside them in one run: the general
confinement suite, the FreeBSD and macOS confinement suites,
the support matrix pins, the Windows confinement fuzz module
and the skip registry, 700 tests, all passing, with 119
platform skips on this Linux host. The shrink guard answers
clean on the working tree.

Against the suppositions:

S1 stands as written. app_container_ancestor_dirs now stops
below the root of the drive or tree, and the grant set built
from it cannot name the root; the pins cover the walk and
the set on every shape the suite names, and the root's
absence is pinned as its own test. No other caller of the
walk exists in the tree.

S2 stands as written, with one refinement the code carries
openly: the restore is the prior DACL as the operating
system serializes it, every ACE in its order with its flags,
which is the level the residue acts on. The snapshots are
taken for the whole grant set before the first grant stands;
a path that cannot be snapshotted is refused before any
grant; a grant failure partway restores every snapshot
before the problem is answered and names any path the
restore itself could not put back; and a spawn that fails
after granting restores through the same path, with the
recorded entry revocation kept as the fallback for a path
the restore misses. The successful spawn's job end
revocation is unchanged, as the plan scoped it.

S3 stands as written. The gate consults the residue check
on the floor verdict before the verdict is cached, and the
naming fires only when both halves prove: the staged read
at exit 0xC0000135, signed or unsigned, and the container
SID standing as an ACE trustee in the DACL of the
interpreter's own directory or file. Every other exit, and
the same exit at the write stage, answers the bare verdict,
and the pins hold those negatives.

S4 stands as written, and the treatment is the statement.
The support matrix and the Windows security page now say,
where the floor's claim lives, that a blocked escape write
is a property of the AppContainer shape and that under the
floor alone a write to a path the job's token can write can
land, with the 2026-11-23 rig measurement named as the
basis. No gate change was made: refusing to start whenever
the AppContainer control is unavailable would repeal the
floor fallback the gate is designed around, and this
landing does not smuggle a posture change into a bug fix.

What this landing does not claim: the live proof. The
Windows only wiring (the SDDL snapshot read, the restore
write, the gate's DACL read) is pinned by the suite's
source shape tests and cannot execute on this host. The
rig battery watch picks the head up on its own cycle; the
fix is proven live when a battery run on a head carrying it
starts clean twice in a row on the Germany rig, the second
start being the one the residue cycle used to poison. The
harness side mitigation from the diagnosis (reset the
private interpreter copy's DACLs immediately before a run)
stays good until that proof lands.
