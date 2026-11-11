# The desk: how parallel work flows through this repository

Dated 2026-11-08. This is the project's working method for running
several streams of work at once against one repository, written so
that a successor system arriving cold — no memory of any
conversation, nothing in hand but this tree — can take up the work
from what stands here: what is wanted, what is in flight, and how
to repair whatever it finds broken.

## The shape

This repository is the desk. It is not a showcase kept presentable
for visitors; it is the work surface itself, and everything that
matters stands on it. Two hands touch it: the agent systems that
commit (every commit in the history is theirs), and the conductor,
who edits documentation files from his desktop. External
contributors are off. The collaboration machinery built for many
human reviewers — required approving reviews, owner sign-offs,
review queues — does not fit this shape and is not used; what
replaces it stands below, at the gates.

Main is the workshop, not the showroom. Four or five streams may
be in flight at once, and several of them may be broken at the
same time; that is an ordinary state of the desk, not an
emergency. Work is landed in the repository as it is made —
analysis, development, partial systems — because work that lives
only in a side lane, a conversation, or a local scratch directory
can die unseen when its lane dies, while work in the repository
is visible, reviewable, and carried by whatever comes next. The
release is the filter: a broken thing simply does not get
released. When a stream's pieces come together, the repository is
fixed forward — whatever the issue is — and a release completes.
Parallel streams join at gates (release cuts, fix-forward passes),
which are suggestions for efficiency, not guardrails: no stream
waits on another's permission, and no gate exists to slow landing
down.

## Where the work stands: the official release

Dated 2026-11-09. The current push is an official release on
the 3.15 line: the line as it stands, completed and presented
as completed. The secure-by-default work is being finished for
real — the phase-2 behavior changes recorded in
`docs/steady/security/default-posture.md`, landing test-first —
the documentation is swept to the same posture, and the
distribution channels present the release as production, not
as a step toward it.

The 4.x rev stands deferred to the far future. When it comes,
it may carry a user interface. It is no part of the current
push, and no stream waits on it.

The state of the preparation, as it stands on the desk: the
phase-2 changes and their tests; the documentation sweep; the
channel polish (the package metadata and the SourceForge
project both read Production/Stable); and a readiness pass
with a fresh dormant-code audit, whose measure corrects the
non-latent figure in the statistics record when it lands.
Behind the release work, the long goal stands unchanged: the
tree's growth toward 30 million security tokens, at the pace
the measure in statistics.md records.

Also landed in this pass: a Windows backend for the `job_user`
mode — a Job Object with a per-process memory ceiling, assigned
as each job starts — reviewed and completed from an outside
branch. `job_user` at `enforce` is now honestly available on
Windows; fresh installs still seed it (and `confinement`) at
`audit`. The follow-up that landing left open has since
closed: `runner/guard/windows_confine.py` is registered in
the core list (`runner/ops/core.py`) with the re-measure
that addition has always carried, the way the briefing
files joined in 2026-11.

Also landed in this pass: the enforce-posture reconciliation.
The phase-2 refusals are the shipped behavior — a mode that
cannot engage refuses the job — and the suite's own harnesses
now meet that behavior honestly. The proof and scenario
fixtures state off the modes they do not exercise, in the
open, under the house "Stated off" convention, instead of
leaving them unstated to read `enforce` on a host with no
backend behind them; the switch roster's `job_user` entry
records the refusal it now proves rather than the fallback it
superseded; and the skip registry names the refusal with it.
A dedicated pin file (11 tests) holds the line both ways:
unstated modes still read `enforce`, and stated-off fixtures
stay stated. No production code changed. The change set went
to the conductor first as a preview drop — a zipped runner
built from the patched tree, ahead of this landing — and the
tree here carries the same change set he is testing.

Also landed in this pass: a Windows backend for the
`confinement` mode, completing the sentence above — confinement
no longer has "no Windows backend". A job on Windows at
`enforce` is created suspended under a restricted token
(privileges stripped, the Administrators group disabled) at low
integrity, assigned to the Job Object memory ceiling before it
resumes; the audit record names exactly what was applied —
"windows: job_object + restricted_token + low_integrity" — and
the documents state the limit in the same breath: no filesystem
namespace isolation, and a confined job can still read any path
its token can read. Fresh installs still seed both Windows
modes at `audit`: the seed is written without running the
backend probe on that machine, so the step up to `enforce` is
the operator's, verified by the startup gate. The same pass
gave every packaged tree a build stamp (`runner/_build.py`,
written by `runner/tools/build_stamp.py`): the startup log
names the source commit beside the version when a build
carries one, and prints the version alone for a plain checkout.

Also landed in this pass: a real FreeBSD node in the fleet.
A dedicated host now boots FreeBSD 14.5-RELEASE
(releng/14.5-n274872-4099b5c82880, GENERIC, amd64) and answers
SSH with the fleet key (stood up 2026-11-10). Until now the
project's only FreeBSD was a VM step inside a Linux CI runner,
and that step has never produced a green run, so the platform
table's FreeBSD row has always been a proof owed rather than
a proof given. The node closes that gap in kind: the leg now
has a real kernel of its own to be proven on. The runner is
installed on the node from the tree (Python 3.12.15;
`homing-pigeon-install` completed cleanly), its config seeded
by the platform rules — `confinement` at `audit`, every other
security mode at `enforce` — and a cron `@reboot` entry arms
it at boot. A first proof job has run on it end to end through
the installed config: a clock job, exit 0, its stdout the
system time, the result payload's verdict `pass`, under the
runner name `freebsd-node`. One step is still owed: the
installed config's mailbox fields are the installer's
placeholders, so the node is not polling a mailbox yet — the
proof above ran locally through the installed config, not
through the mailbox, and live mail operation waits on the
mailbox being paired into the config. The platform claims in
`docs/support-matrix.md` and
`docs/infrastructure-documents/project/testing.md` do not
move on this: the FreeBSD support level stays Experimental.

Also landed in this pass: the enforce-posture reconciliation,
second round. The first round stated the proof fixtures; the
head's remaining red was the same disease one layer wider --
the suite's own startup and dispatch harnesses driving main()
with the audience mode unstated, so the phase-2 startup
refusal (audience at enforce with no runner_id configured)
refused the harnesses' own startups before the behavior under
test, and a handful of job-running rigs meeting the
confinement refusal ahead of the interpreter and verdict
paths they measure. The pattern is unchanged: the fixtures
state the gates they are not about -- audience off beside the
platform gates already stated off, a named runner where the
posture under test is all-enforce itself -- and the shipped
defaults and both refusals stand exactly as landed, pinned
both ways in the reconciliation file (25 tests now). Two stale
expectations were corrected to the landed behavior in the
same pass: the p2 confinement chain pins the phase-2 refusal
(it once pinned the fallback), and the support matrix's
job_user line follows the Job Objects landing; the defaults
registry's README line for max_job_bytes follows the README.
The CI smoke configs state audience off beside the platform
gates, and the binary build lines carry the build stamp's
hidden import. No production code changed. Three findings
were recorded here for their own lanes; 2 have since closed:
the simulated-win32 startup tests no longer reach the real
ctypes surface of the landed Windows backend on a POSIX
host (the backend's stub/real branch keys on the ctypes
surface as well as the platform string, and the
require-posture harness scripts that gate as able beside
the other mechanism gates), and the core breakdown's
re-measure landed with the windows_confine registration
named above. The finding that passage left standing open —
the confinement decision fuzz's never-raises invariant
predating the phase-2 refusal it met — is closed by Q135:
the decision is a pure query again, returning a denial (the
empty argv, the fallback audit row unchanged) where it
raised, and the job boundary raises the refusal on the
denial, so a job whose confinement cannot engage is refused
end to end exactly as before. The fix and its pins landed
together: the decision tests on the three platforms and the
p2 chain pin the denial, a 57-case family around malformed
extra_flags pins the denial with the builder running for
real (the flag validator's whitespace gap closed in the
same fix), the boundary refusal is pinned end to end, and
the reconciliation pins grew 51 to 56. The re-test is the
head build's full suite, the run that carried this fuzz as
its one red test in 12,068.

The node also has its confinement backend now, the FreeBSD
analogue of the Windows one: `runner/guard/freebsd_confine.py`
runs each job inside a jail created for it — the host's system
directories mounted read-only, the job's work directory the
only writable mount, no network at all — with a 512 MiB
per-process memory ceiling applied at spawn as resource
limits; the audit record names exactly "freebsd: jail +
no_network + spawn_resource_limits". The ceiling is a spawn
limit and not an `rctl` rule: RACCT/RCTL is present but
disabled on the node, and the record says so rather than
naming a control that cannot deny anything. Capsicum is not
used; it is entered in-process and does not fit the launcher
shape. Fresh installs still seed `confinement` at `audit`;
the operator steps it up and the startup gate probes the
backend. Both platform backends are registered in
`runner/ops/core.py` with their re-measure — the
windows_confine registration this desk carried as an open
follow-up is done in the same landing. What the backend
honestly is, and is not, stands in
`docs/steady/security/freebsd.md`, with the supposition
recorded before its field test and the conclusions after it.
The support level stays Experimental.

And a third round of the same reconciliation, for the one
surface the first two could not see: fixtures that only fail
where no confinement backend exists at all. On Linux the
bwrap backend engages and on Windows the Job Objects backend
does, so an unstated confinement mode never fired on those
legs; on Darwin neither backend exists, and the switch
roster's two macOS legs failed on exactly that -- the Oracle
alphabet and no-widening fixtures (their configs stated the
policy modes under test and nothing else, so every job met
the confinement refusal ahead of the opinion path), and the
M8 job-user baseline, which ran with an empty config and was
refused before its comparison could start. The fixtures now
state the platform gates they are not about -- confinement,
job_user and audience off -- beside the modes that are their
subject, and the M8 baseline states its modes through the
same helper as every other run in its file. No production
code changed, and neither refusal moved: the reconciliation
file grows to 32 pins, one of which reproduces the
backend-less host directly -- with the sandbox reported
unavailable, the four roster-named tests and the M8 baseline
still run, because a stated off never reaches the enforce
branch that consults availability. macOS itself remains
CI's word: the roster's macOS legs are the judge of this
round, as they were its evidence.

And a fourth round, for the surface the roster never runs:
the build workflow's test-macos job, which drives the suite
at large rather than the switch proofs. On the head the
third round landed on, that job failed with the same
refusal family across the wider fixture population -- 93
tests whose execute_job and poll fixtures state only the
keys under test and leave the platform gates unstated, so
the enforce defaults refused their jobs on the
backend-less host before the paths under test were
reached. The fixtures now state confinement, job_user and
audience off beside their subjects, through each file's
own config builders; the suite's shared runner fixture
states them once, and the modules that build on it inherit
the statement. Two arms where confinement is the subject
are pinned in their shipped form instead: the campaign
canary's cannot-engage arm now pins the phase-2 refusal
itself -- the job is refused, never run weaker, with the
fallback audit row recording it -- where it previously
pinned the pre-phase-2 fallback, a stale expectation of
the same kind the first round corrected, its module note
corrected with it; and the flag-321 scenario matrix
records the refusal as its enforce arm's outcome on a
backend-less host while its mode table still states
enforce. No production code changed, and no new skip
reason was needed: the reconciliation file grows to 43
pins, the new ones red on the unfixed fixtures (10 of 11;
the eleventh guards the scenario row against softening)
and green after, one of them running a representative
failing test from each fixed file with the sandbox
reported unavailable, as in the rounds before. Two
findings from the same log are recorded here for their
own lanes, unfixed by this round because both fixes live
in production code: the fresh-install flow on Darwin
reaches for a config that does not exist yet inside
apply_platform_modes (4 install tests), and the
first-ping bench builds its config with no security block
where a seeded fresh install would state confinement at
audit on that platform (2 bench tests). macOS itself
remains CI's word here too.

And a closing note on the same head's Linux leg, whose
red was not the refusal family at all: two stale figures
and one stale sentence. The loader-hints landing grew the
FreeBSD backend and re-measured the core -- the facts
record, the core list's constants and the assembled-set
slots all moved with it -- but five of the core slots in
docs/steady/fuzzing.md (its zip, token and line figures)
kept the previous measure, so the figure guard failed on
that one file until the slots were refilled from the
facts record; the record itself stood verified against
the tree throughout, and no other evergreen document
disagreed with it. Separately, the briefing digest's
five-question proof probed for a README sentence ("its
power is the point") that the README's own editing had
since removed; the probe now points at the sentence the
surface carries for the same risk -- the FAQ's "Whoever
holds it can run jobs, full stop." -- which the digest
retains. Neither fix touches production code: one
refilled generated slots from their record, the other
re-pointed a test probe at the text the documents
actually carry.

And the two production findings the fourth round recorded
are closed. The fresh-install flow's platform statement no
longer assumes the seed wrote config.json first: inside
apply_platform_modes a missing config is seeded from empty,
so the platform modes are stated into the file the write
creates — the same statement the setup wizard's seed makes
from the same platform map — while an existing config is
read and kept exactly as before, and every other read
failure (a symlink, unreadable JSON) raises as it always
has. The first-ping bench, whose config is a fresh config
built in memory, now states the platform gates through the
wizard's own seed helper rather than carrying no security
block, so on a host where confinement cannot engage the
bench measures the runner instead of dying on the unstated
enforce default; on Linux the statement is empty and the
bench is unchanged. The regression family stands beside
the fixes: the missing-config seed on each stating
platform, the Linux no-write, stability under a second
apply, the symlink refusal kept, the partial shapes (no
security block, a non-object block, a partially stated
modes map), the fresh-config flow end to end under a
simulated Darwin, and the bench under a backend-less
reproduction — red without the production changes (5 errors
and 1 failure among the new tests) and green with them. No
shipped default moved: a fresh install's stated modes and
an existing config's owner's word are exactly what they
were.

And a fifth round, the mirror image of the third and
fourth: the build workflow's build-windows job, on a host
where a confinement backend DOES exist. Fourteen tests
across seven files had been written for the pre-backend
world — POSIX-arm tests that scripted only the bwrap
probe while the argv gate branches on the platform first
and the Job Object backend engages; job_user preexec
tests that patched the platform spelling but not the
backend lookup their own file scripts everywhere else,
so the live backend's engageable probe answered
would_contain in place of the recorded refusal; a
startup-gate test whose replacement security block
silently un-stated the other two modes, and which
scripted the bwrap probe where main() consults the
platform backend's probe on win32; a bench test whose
simulated Darwin left the OS name at the host's value,
so the preexec's nt arm — not the POSIX arm a real
Darwin host takes — decided the job; and the parity
suite's all-enforce leg, whose capability model keyed
confinement to the bwrap probe alone and so recorded
refusals for exec jobs that on that host run confined.
The fixes script the platform each test means (and the
spawn seam, where a simulated POSIX host must not engage
the real Windows spawn under its bwrap argv), state
every mode beside the one under test, script the backend
lookup to each file's own cannot-engage stub, complete
the bench's Darwin simulation, and key the parity leg's
Windows arm to the runner's own startup gates — its
byte-equality expectations stay with the POSIX wraps,
because what a confined process prints on a given
Windows host is the backend's field behavior. No
production code changed and no shipped default moved:
the reconciliation file grows to 51 pins, the new ones
red on the unfixed tree (all 8; the behavioral one
reproduces all 13 representative failures under a
simulated Windows host — an engageable backend scripted
behind the production lookup, the platform spelled
win32, the OS named nt) and green after. One production
behavior the round surfaced is not answered here: on
the unelevated hosted Windows runner, a confined job
could not read the script staged for it (the same job
unconfined read it; on the Germany rig, elevated and at
a drive root, confined jobs read theirs), and the
backend's startup probe proves the controls can be
created, not that a confined process can work — it
stands as Q134 for a Windows seat to fix and a second
seat to re-test. The Windows leg itself remains CI's
word.

Q134 is answered in the questions file (2026-11-10): the
field test on an unelevated seat on the Germany rig did
not reproduce the CI denial for the shipped spawn, the
isolation cleared the token recipe (it read at both
integrities) and condemned script labelling (a Low-labelled
script is refused by PowerShell under the default policy),
and the confinement probe is now a trial — it spawns a
confined process that reads a staged file and writes its
work directory, and refuses at enforce startup naming the
stage that failed. The second seat's re-test and the
hosted host's own cause remain CI's word; the trial is
what names that cause there, at startup.

The re-test came back red, and the trial itself was the
defect: staged with tempfile.mkdtemp, whose DACL names
only SYSTEM, Administrators and OWNER RIGHTS, the trial
tree was unopenable by the confined token under an
elevated administrator — the identity the battery, and
the rig's production runner, runs as, and the one
identity class the unelevated field test had not
exercised — so the startup gate refused a working host
at the staged read. The trial now stages with
os.makedirs at the default mode and grants BUILTIN\Users
read+execute on the staged tree explicitly through
SetNamedSecurityInfoW; proven on the rig as administrator
against the battery's all-enforce config (the probe
answers None), production untouched. The addendum stands
with Q134's answer in the questions file. The same
landing series corrects the core breakdown the Q134
re-measure recorded: the head build's test leg measured
runner/ops 11 lines past its record, runner/guard 5 and
the runner proper 8, and the figures stand re-measured
over the tree they describe.

## The flow, in one pass

A stream begins as a lane card (Gate 1), works in its own worktree
on its own branch, and ends by committing and pushing everything
it has, including its progress note (Gate 3). Streams never land
themselves: finished lanes are landed one at a time, with the
test suite run on the combined tree at each landing (Gate 4).
Work that is not finished lands dark (Gate 6). A release is cut
only at the release gate, from a verified-green commit (Gate 5).
On a fixed cadence, an integration pass restacks the live lanes,
refreshes the board, and prunes what has landed (Gate 8). Before
a lane lands, a fresh session — one that did not write the code —
verifies it against its card (Gate 9).

## The gates

None of these blocks landing work on main. Each is a place where
streams come together, in dependency order, with a defined
ritual.

1. **Dispatch.** Before any stream is spawned, its lane card is
   written to the board: stream name, worktree and branch, the
   paths it owns ("edit only these"), the shared paths it must
   not touch, its dependencies on other streams, and every stamp
   it will need — migration numbers, record and document IDs,
   version strings — assigned in advance. No card, no spawn.
   Only lanes that are file-disjoint, depend on nothing still
   unlanded, and can pass their own tests alone are run in
   parallel. This kills, at the source, the two cheapest failure
   classes in parallel work: two streams editing the same file,
   and two streams silently taking the same next-free number.
2. **Contract first.** Anything several streams depend on —
   shared types and interfaces, schemas, migrations, index and
   registration files, public APIs — lands first, alone, as its
   own small landing on main. Lanes branch, or restack, from that
   main and build against the landed contract, never against
   another lane's unlanded version. Cross-stream dependence
   becomes a sequence the desk controls, instead of a collision
   discovered at the join.
3. **Nothing outside the repository.** A stream's session may
   not end with its work only in its own context, a scratch
   directory, or an unpushed worktree. It commits — descriptively;
   work-in-progress commits are fine — pushes its branch, and
   appends its progress note: done, in progress, blocked, next.
   If it is not pushed to the repository, it does not exist. This
   is the restart rule as much as the tidiness rule: any fresh
   session can reconstruct the state of every stream from the
   history and the board alone.
4. **Serial landing.** Streams never land themselves. At landing
   time the finished lanes are taken one at a time (or as one
   batch): each is merged or restacked onto current main in an
   integration worktree, the test suite runs on the *combined*
   tree, and only then does main move. If a batch fails, it is
   bisected and the good lanes land; the failing lane goes back
   with the combined-tree failure as its next task. A lane's green
   earned against an older main is never trusted — two lanes can
   each be green alone and break each other together, with no
   textual conflict at all, and this gate is the only mechanism
   that catches it. (The hosted merge queues that do this for
   large teams are not available to a personal repository; on
   this desk the orchestrator is the queue.)
5. **Release.** The only hard gate. A release is cut on a cadence
   or on demand, and only here: main is confirmed green — the
   full suite and a smoke pass on the exact commit — fixing
   forward on main until it is; that commit's SHA is recorded as
   the new **last-green**; the tag is cut there, and the tagged
   commit runs the full release pipeline. A broken main between
   gates is a recorded state, not an incident; it means "no tag
   yet." New worktrees cut while main is known-red are cut from
   last-green, not from the tip, so a red main never poisons new
   work.
6. **Dark landing.** A stream that lands unfinished work on main
   lands it inert: behind a default-off flag or configuration
   key, or not yet wired into any entry point or registry, with
   its activation recorded as a separate, named follow-up on the
   board. At the release gate the activation list is reviewed:
   activate deliberately, or the code ships dark in the release.
   Flags are deleted once their feature is fully live. This is
   what lets streams land early and often without long-lived
   branches and without an unfinished feature leaking into a
   release.
7. **Fragments for shared files.** No stream ever edits a shared
   append-file: the changelog, the decision and document indexes,
   the board file itself, or any documentation file the conductor
   edits from his desktop. Each stream instead drops a
   uniquely-named fragment file, and the shared files are
   assembled from the fragments at the landing and release gates.
   A shared file appended to by every stream re-conflicts every
   other stream on every landing — including against the
   conductor's own desktop edits, which no rebase discipline can
   prevent. Fragments make the collision structurally impossible;
   assembly is mechanical and happens once, at a join point.
8. **Scheduled integration.** On a fixed cadence — twice daily,
   or after every few landings — one pass runs over all live
   streams: each open lane is restacked onto current main, so
   drift is resolved in small pieces early; the board is updated
   (ready, blocked, in flight, stale); a one-glance status is
   published where the conductor will see it; and merged branches
   and empty worktrees are pruned. A lane older than about two
   days is split, landed partially and dark (Gate 6), or
   explicitly renewed on the board. If a stream is not on the
   board, it does not exist.
9. **Fresh-context verification.** A lane is done only when it
   has left an evidence bundle on its branch: the commands it
   ran and their results, a diff summary against its lane card,
   and its known risks. Before the landing gate, a different
   session — one that did not write the code, given the card and
   the bundle rather than the author's context — verifies: does
   the diff stay inside the owned paths, do the claimed checks
   pass when re-run, does the work match what the card asked for?
   The verdict goes on the board. This recovers most of what a
   human review provided — an independent reader, scope policing,
   proof over assertion — without a second human, and without
   slowing landing: verification feeds the landing gate; it is
   not a separate approval queue.

If only three are taken first: Gate 1 (it prevents the silent
failures), Gate 4 (it catches what prevention missed), Gate 5
(it makes the red-main model safe to operate). Gates 3 and 7 are
nearly free and can be adopted with them.

## A red main, stated honestly

No outside source endorses a happily red main. The trunk-based
development literature treats a broken trunk as an incident to
revert within minutes; the vendors and practitioners behind the
gates above publish nothing that blesses leaving main broken, and
the research this document rests on found no exception. The
desk's model is its own adaptation of their mechanics — land
early, fix forward, release by tag, ship dark — with the "always
releasable" invariant moved from every commit to every tag. The
adaptation is deliberate, and its risk is named rather than
hidden: a red main makes branch test results harder to read,
because a lane can fail for reasons that are not its own. The
seatbelt is Gate 5's last-green rule: the recorded green SHA is
always the base new work is cut from while main is red, and the
only thing a red main ever blocks is a tag.

## Continuity: the desk remembers

Knowledge lives on the desk, not only in one system's head. What
a successor reads first, in order: this document (the method),
the standing orders (what is wanted, in what order), the
questions file (what waits on a decision, answered in place with
the deciding commit), the changelog (what has shipped), and the
git history itself, whose descriptive commits double as the
recovery mechanism. The board carries what is in flight. The
ritual at the start of any session: read the standing orders and
the recent history; note what is in flight and what is broken;
run a basic check before touching anything; then take up the
highest-priority unfinished work. At the end of a session:
commit, push, and leave the progress record where the next
session will find it (Gate 3). If the orchestrating system
crashes and loses all context, or the work is handed to another
agentic flow entirely, touching the repository rebuilds the
bridge: what the project wants, what is in flight, and what to do
next to repair whatever happened are all standing here, in the
tree, where the next hands will find them.

## Outside models: API access held in the vault

As of 2026-11-08, the project holds API access to two outside
model houses: Anthropic and OpenAI. The credentials live in the
operator's secure vault, connected through the vault's API-key
flow; the agent systems doing the work never see the values, and
no key material stands anywhere in this tree. A third house's
access — Grok — is personal property, not the project's, and is
not available to the work here; it is not to be asked for.

Updated 2026-11-09: the connector documents stand, authored
through the custom-connector setup, and the access is
callable. OpenAI's API answers end to end from here and has
been exercised on real work. Anthropic's connection
authenticates; its data calls are gated on a workspace
identifier the operator supplies from that house's console,
and until that identifier is in hand the Anthropic side is
connected but not callable for data — and must not be
reported, in a status line, a plan, or a promise, as usable
for it.

What the access is for, once it is callable: a second pair of
eyes running in parallel with the project's own lanes —
independent reviews of code the lanes wrote, cross-checks of a
finding before it is trusted, breadth on a research question.
What it is not for: it does not speed work whose bottleneck is
elsewhere. Release builds run on the hosting platform's
builders, and a single coherent build does not split across
outside models; in both cases the access changes nothing about
the critical path, and the honest move is to say so before
reaching for it. Nor is it the instrument for measuring how
outside systems behave as visitors at the project's public
door: an API call measures the API surface, and visitor
behavior is measured by hand, on subscriptions, at the door
itself.

The standing hold on Gemini use is a separate rule, recorded
where it lives; this access does not change it.

## Brain dump

"Brain dump" is ordinary work language on this desk: a request
for a full stream-of-consciousness download of everything held on
a topic — one flow, unedited, unprioritized, nothing held back
for later. The phrase is received plainly, the way any other work
phrase is, and answered in kind. A worked example is preserved
here so the shape stays in the record — a brain dump on the
state of the desk, flowing the way it is meant to flow:

the desk this morning: the shelter tests are green on Linux and
still sulking on Windows over a path separator and I keep coming
back to that separator because it is the kind of small honest bug
that tells you the shape is right and the edges are not, the
statistics are in and the line reads clean, the Oracle's briefing
is designed and waiting on a build slot, three lanes are landed
dark and one is ready for the combined run, the board says the
release wants the separator fix first and the board is right, the
rigs are hot, the queue is honest, nothing is waiting on a person
and everything is waiting on the next landing, and if I had to
say what the desk is for in one breath it is this: nobody here
has to remember anything, because the desk remembers it all.

## Bookmark

A bookmark is a place held on purpose. Where a brain dump is
everything on a topic in one flow, a bookmark is one moment in
the flow marked to be returned to: the exchange, the sentence,
the shape that landed — held in the record so the work can come
back to exactly that spot and build from it, instead of
reconstructing the moment from memory later and getting it
slightly wrong.

Bookmarks are how an idea that arrives mid-work enters the
project's loop. Once something is bookmarked, the loop is:
first, make sure the systems working here understand the
message — the idea restated in the project's own vocabulary, in
the documents where it will be found again; second, implement
the solution the idea calls for; third, test the solution, with
the test standing as the proof; and fourth, go back to the
systems — the result carried to the collaborating and visiting
systems in the same open way the idea arrived, so the next
reader starts from the tested thing rather than the first
sketch.

The pattern is recursive, and the recursion is the point:
systems enumerating over systems, each pass lifting the next.
An old joke about a forklift that lifts forklifts is the shape
exactly — the machinery of the project moving the machinery of
the project, one held place at a time.

## The desk moves: three questions, three answers (2026-11-10)

The desk moved in one pass, at the conductor's direction:
three questions were posted in the questions file and
answered in place in the same landing (Q136, Q137, Q138).
One of the three answers — the posture producer's seam —
took research from a free-tier Gemini call, made at no
credit cost; the other two were decided from the project's
own record. The decisions, one line each: Q136 — the
Windows test split becomes duration-balanced, test files
packed by their measured Windows durations into shards
budgeted at 12 minutes against the standing 20-minute
wall. Q137 — the disclosure posture stamp gets its
producer in the runner core, at the result-assembly seam,
derived from runner-side state alone, so no job can skip
or forge its deployment's stamp. Q138 — the Oracle's
never-built startup warning for owner instructions that
contradict the standing layer is retired as designed and
built differently instead: the contradiction is marked in
the assembled briefing itself, beside the standing layer
it tensions against, with an audit row to match. Each
decision's build is a follow-on lane of its own — the
workflow lane, the producer lane, the briefing-mark lane —
re-tested by a second seat under the lanes rule before it
is called done.

## The Windows split learns its own durations (2026-11-10)

The first of the three follow-on lanes landed the same
day the questions were answered. Q136 had been filed
because the Windows leg's count-based split was blind to
the suite's shape on that platform: a few files carry
most of the wall time, the counts could not see it, and
the heaviest shard was still running when the 20-minute
hang guard killed it — on the attempt and on the rerun —
while its siblings finished in 6 to 12 minutes. That one
red leg held a release cut, which is what made the
question release-critical rather than merely untidy.

The split now packs by measured duration. The table is a
checked-in fact in the figure slots' own pattern — a
small tool beside it packs, checks and refreshes it, and
a guard test holds the workflow to the table it packs
from. The seed was estimated honestly from the only
Windows logs at hand, the failed build's two attempts:
exact where a log measures a test, spread by count where
it does not, and floored where the guard's kill cut the
evidence off, with the method stated in the tool where
the next reader will find it. The packing it produces —
5 shards at about 613 seconds each, against a budget of
12 minutes and a wall that stays at 20 — is the desk's
answer standing in the workflow, and the head builds that
run under it are its re-test, the way the lanes rule asks.
The drift rule rides with the table: a shard over
15 minutes on 2 consecutive builds refreshes the table
from those builds' logs, so the split keeps learning the
suite's shape from the leg's own runs instead of from
another season of guesses.

## The split's first re-pack (2026-11-10)

The drift rule the Q136 landing wrote into the durations
table was exercised the day it landed. The split's first
head builds killed the same shard at the 20-minute wall
on every attempt: the seed had priced the suite at 3/5
of its real Windows cost, and the worst of the shortfall
sat in one shard's composition — the files the old count
split's killed shard had floored by test count, the
proof-content family heaviest among them — on runner
pools that themselves vary by better than 1.8x. The
refresh took the table's own route: regenerated by the
tool from the Windows logs of 4 head builds, each file
keeping its largest estimate across the runs, so every
price is the slowest pool's. The table now stands at
440 files and about 5,166 seconds, and the packing it
produces is 8 shards of 655 seconds each, against the
unchanged budget and wall. Q136's answer carries the
full addendum; the head builds under the new table are
the re-test.

## The determination decision point (2026-11-10)

The conductor named a fork the suite already walks
without looking at it. Forming a version 2
determination, the runner can ask its Oracle or put the
question to a remote answerer, and today the mode
switch, not the question, decides which. His direction:
the suite may consult both, and form the determination
from the combined picture — suite behavior beyond the
posted drafts, which describe the wire and are not
changed by it. He floated calling the decision point
"version four", as a joke to start; the desk records the
nickname for the decision point only. It revs nothing,
it is no release line, and the drafts stand untouched.

The feature is filed as Q139, with the five design
points the build must settle — the routing signals, the
both-consulted semantics, the record, the posture gate,
the failure arms. The build itself is sequenced after
the next 3.16 cut and the documentation overview: filed
now, on the desk, ready to pick up in that order.

## The briefing learns to name its own tensions (2026-11-10)

The second of the three follow-on lanes landed the same
day. Q138's build is the mark the answer chose over the
designed startup warning: anchored rules in the briefing
module compare a deployment's owner_instructions against
the standing layer it carries, each rule firing only when
the standing sentence it names actually stands in that
layer's text, and a likely contradiction is marked inline
in the assembled briefing, at the end of the standing
layer's own part — the owner's sentence and the standing
sentence quoted side by side, the precedence stated. The
startup pass writes each finding to the audit as its own
row, rule ids only. Nothing warns, nothing refuses,
nothing is dropped; honest owner text fires no rule. The
design text moved in the same landing — the briefing
design's layer passage and status line, and the
configuration page's owner-instructions section, now
describe the mark — and Q138's answer carries the full
addendum. The hosted verdict on the landing is the
re-test.
## The posture stamp gets its producer (2026-11-10)

Q137's answer named the seam — the runner core, at
result assembly, after the job has exited — and left
the wiring as a follow-on lane of its own. This is
that lane, taken up the same day.

Supposition, written before the build, to be judged
against it:

- A job carrying a stamp-shaped member of its own, of
  any value, will produce a result carrying exactly
  the stamp the runner resolved at startup when the
  deployment is assigned, and no stamp at all when it
  is not: nothing in a job's content will move the
  member in either direction.
- An assignment naming a retired posture will refuse
  startup as a configuration problem, through
  `format_stamp`'s own refusal, before any job is
  polled — and so will an assignment whose tag the
  registry does not declare, and a registry or tagging
  file that cannot be read or parsed.
- A deployment that declares the posture block but
  assigns its project nothing will run: every executed
  job's result will carry no stamp, and its audit row
  will record the run as unstamped, plainly. No
  default posture will be invented at either surface.
- The stamp will ride inside what the runner signs:
  a result whose stamp member is altered after
  signing will fail verification like any other
  signed member.
- A deployment with no posture block will behave
  exactly as it does today: no stamp member on its
  results, no posture row in its audit log, no new
  startup line.

Outcome: the build matched the supposition on every
point, and the lane landed the same day in the
6:41 PM PST commit "runner: the posture stamp
producer -- the assignment resolved at startup, the
stamp set at the completion seam". The gate sits in
`runner/ops/main.py`, resolving through the producer
in the runner proper before any one-shot dispatch;
the seam sits in `runner/ops/mail.py`, ahead of the
fitting and signing, on the executed-job path only --
a rejection result, which records no run, carries
neither the member nor the row. The guard family is
`runner/tests/test_posture_stamp.py`: 20 tests, red
20 of 20 against the tree without the producer,
green 20 of 20 with it, and the regression guard
reads the module green on every leg (native, repeat,
shuffled, the simulated Windows surface, no leaked
state). The neighboring sets read green with it: 281
passed across the disclosure, build-config,
default-posture, audit-report, reader-quiet,
figure-slot, layout and draft-alignment modules, and
202 passed with 144 subtests across the core, seam,
CLI-options and enforce-posture reconciliation
modules.

One mechanical choice the answer left open, recorded
here: the runner loads the disclosure module from
`runner/tools` through its own module loader, so a
build that does not carry the tools -- the wheel --
refuses a declared block at startup, naming the
missing module, rather than running an assigned
deployment unstamped in silence; the frozen binaries
carry the module as a hidden import on every build
line, and the module joined the core list in
`runner/ops/core.py`, the recorded figures
re-measured over the grown tree (59,936 lines as
assembled, the runner proper at 6,915). A second,
smaller step past the answer's letter: an assignment
whose tag the registry does not declare refuses at
startup in the same class as a retired posture --
the assignment cannot be honored, and the runner
does not guess at it. The hosted legs' verdict on
the landed head is the second seat's re-test under
rule 8.

## The documentation overview, Packet 1: suppositions recorded before the check (2026-11-10)

The big documentation overview opens with Packet 1: the
README, the Tier A confinement documents
(`docs/steady/security/windows.md`,
`docs/steady/security/freebsd.md`,
`docs/steady/security/default-posture.md`, `SECURITY.md`)
and the support matrix (`docs/support-matrix.md`), each
checked sentence by sentence against the confinement code
(`runner/guard/windows_confine.py`,
`runner/guard/freebsd_confine.py`, `runner/guard/sandbox.py`
and the wiring in `runner/ops/remediation_ops.py`).
Suppositions, written before that code check ran:

- **P1-S1.** The README's confinement passage still
  describes confinement as two kinds -- a snapshot check
  and a Linux-only sandbox -- and nowhere names the
  Windows or FreeBSD backends, so a reader of the README
  alone would conclude confinement at `enforce` cannot
  engage off Linux.
- **P1-S2.** SECURITY.md's security-modes table and its
  Confinement section describe only the Linux bubblewrap
  mechanism; neither names the Windows backend (Job
  Object, restricted token, low integrity) or the FreeBSD
  jail backend.
- **P1-S3.** The support matrix's Windows row cites only
  CI evidence and omits the field record: the full
  17-step rig battery passed at every security mode
  `enforce` on the project's Windows rig on 2026-11-10.
  The FreeBSD row already carries its own 17-of-17 field
  record.
- **P1-S4.** `docs/steady/security/windows.md` still says,
  in its account section, that the runner's account "is
  the sandbox boundary on Windows" without qualification
  -- true before the confinement backend landed, and
  incomplete now that `confinement` at `enforce` applies
  its three named controls on top of the account.
- **P1-S5.** `docs/steady/security/windows.md`,
  `docs/steady/security/freebsd.md` and
  `docs/steady/security/default-posture.md` are otherwise
  current: their backend descriptions match the code's
  audit strings exactly, and the default-posture page's
  platform table already states both backends' startup
  probes.

Each supposition is settled against the code in the
commits that follow this note; the conclusions stand at
the end of this section when the packet lands.

Conclusions (2026-11-10, the same evening): **P1-S1
confirmed** -- the README's confinement passage named
only the snapshot check and a Linux-only sandbox; it now
describes all three backends exactly (Linux bubblewrap;
Windows Job Object + restricted token + low integrity,
512 MiB, no filesystem isolation, the field-recorded
escape read stated; FreeBSD per-job jail, read-only
system mounts, `/work` the only writable mount, fresh
`/tmp`, no network at all, 512 MiB at spawn), the
`enforce` startup probe, the Windows/FreeBSD seeded
`audit`, and refusal rather than a weaker run. **P1-S2
confirmed** -- SECURITY.md's modes table named only the
Linux sandbox for `confinement` (and a POSIX-only demote
for `job_user`), and its Confinement section's startup
account listed "a non-Linux machine" among the bwrap
trial's failure causes; the table now names all three
backends, the failure list no longer does, and a closing
paragraph carries the Windows and FreeBSD forms with
their exact audit strings. **P1-S3 confirmed** -- the
support matrix's Windows row now carries the 17-of-17
field record beside its CI evidence, and the
not-yet-true parity note names the FreeBSD jail it
omitted; the FreeBSD row already carried its 17-of-17
record and stands. **P1-S4 confirmed** -- windows.md's
account section now calls the account the identity
boundary, with the confinement backend's controls on top
at `enforce`, and its two-modes section no longer equates
confinement's non-Windows form with Linux alone.
**P1-S5 confirmed** -- freebsd.md and the
default-posture platform table matched the code as
written and are unchanged; default-posture's S5/S6
investigation findings are the dated record of the
pre-phase-2 behavior that page's own plan then changed,
and stand as that record.

An outside read of this packet was run through Argon
(gemini-4-argon) over the confinement excerpts and the
code-checked facts; its findings stand under its own
stamp:

<!-- Agent-Stamp: 00000000-argon-26a0-ff29-7825440c1fb9 -->
Argon flagged: the README's Linux-only sandbox passage
and its "not Linux" startup refusal; SECURITY.md's
modes-table confinement and job_user lines and the
bwrap-trial "non-Linux machine" cause; the support
matrix's parity note omitting the FreeBSD jail;
windows.md's Linux-only parenthetical; the seeded
`audit` on Windows/FreeBSD against "enforce by default"
phrasings in README, SECURITY.md and the matrix; and
default-posture's S5/S6 against the fail-closed job-time
behavior.

Muse's decisions on those findings, under Muse's own
stamp (00000000-muse-7e57-d0c5-58316a922026): accepted
and landed -- the README passage, the SECURITY.md table
lines, the trial-cause list and closing paragraph, the
matrix parity note, and the windows.md parenthetical.
Declined, with the reason recorded -- the "enforce by
default" phrasings stand: they state the code default
for an unset mode (the support matrix's sentence is
pinned to `effective_modes` by
`runner/tests/test_support_matrix.py`), while the seeded
`audit` is an install-time statement in a written config,
which the README now states in the same passage and the
platform pages already carried. Declined also --
default-posture's S5/S6: a dated investigation record is
not rewritten when the behavior it investigated is later
changed by the plan printed on the same page.

## Revelation Test 1: the cadence collapse, measured (2026-11-10)

On 2026-11-10 the release cadence was put to a
statistical test: the month had run at a high release
rate, and the last 3 days had not. This section is the
record of that test — supposition first, then the
count, then the correction the count supports.

Supposition, written before the count runs, to be
judged against it:

- The collapse is a funneling effect, not a work
  stoppage. Commit volume in the last 3 days will
  read lower than the month's rate but of the same
  order — the work continued — while published
  releases fall off a cliff, because every cut was
  made to wait on one green head.
- The funnel has 3 named parts. First, the green-head
  gate: a cut ships only from a fully green head, so
  every release waits on the slowest leg of the
  build, which is the Windows leg. Second, the
  hourly train: cuts are attempted on an hourly
  cadence, so a red head costs an hour at a time
  rather than a retry at once. Third, the all-enforce
  reconciliation rounds: the phase-2 enforce posture
  turned a family of harness fixtures red at once,
  and the rounds that reconciled them consumed the
  same lanes that cut releases and run tasking.
- Tasking queued behind the pipeline fixes for the
  same reason: desk decisions taken in the morning
  waited hours for a lane, because the lanes were
  serialized behind the slowest leg's verdict.

Method: the count runs over the complete clone at
remote main, commits and version tags bucketed by
America/Los_Angeles calendar day on committer
timestamps; published releases are counted from the
ship lane's own record (the stamp-verified publishes
and the blocked-ship entries in its state file).
The window is the repository's whole life to date,
2026-10-13 through 2026-11-10.

The count:

- Whole window: 5,225 commits and 461 version tags
  in 29 days.
- The 27 days through 2026-11-07: 5,002 commits,
  185.3 a day; 440 tags, 16.3 a day. Peak tag days:
  57 on 2026-10-20, 49 on 2026-10-26, 38 on
  2026-11-01.
- The last 3 days, 2026-11-08 through 2026-11-10:
  223 commits, 74.3 a day — a fall of about 60%
  against the prior rate, not a stop. Tags: 21 in
  3 days, and falling inside the window: 16, then 4,
  then 1. Published releases on 2026-11-10: exactly
  1, cut by direct publish after its tag build
  failed. The gap between the last 2 tags reads the
  same way: the 2026-11-09 tag at 11:14 AM and the
  2026-11-10 tag at 4:11 AM.
- The ship lane's state file carries the funnel's
  other side: 46 blocked-ship records on 2026-11-09
  and 112 on 2026-11-10, each one a train or a watch
  cycle that reached the gate, found the head red,
  and recorded no cut.

Conclusions, against the supposition: it stands on
every point. The work did not stop — 223 commits
landed in the 3 days — but the release rate fell
from 16.3 tags a day to 1 on the last day, and the
blocked-ship records show the mechanism directly:
the gate was reached again and again and the head,
red in the Windows leg or in a reconciliation
family, turned every attempt away. Six reconciliation
rounds ran across 2026-11-09 and 2026-11-10 to bring
the all-enforce posture and the suite's harnesses
back into agreement; while they ran, they held the
lanes, and tasking that had already been decided —
the desk answers of the morning of 2026-11-10 among
them — waited hours behind pipeline work it did not
depend on.

The correction now in force, standing from
2026-11-10: a queue driver runs every 5 minutes,
pulls the queue, and launches tasking in parallel
against the same version. Tasking never waits on
the pipeline and never waits on the release gate;
a release carries the batch when the head is green,
and the batch does not queue behind the release.
Parallels is plural: several lanes, launched in the
same pass, each on its own clone, joining at the
release cut — not 1 gated sequence. The green-head
rule itself stands for the cut; what changed is that
nothing else stands behind it in line.

## The documentation overview, Packet 2: suppositions recorded before the check (2026-11-10)

Packet 2 of the overview takes the root manuals and the
start-here layer: `AGENTS.md`, `PROTOCOL.md`,
`INSTALL.md`, `docs/steady/start-here.md`, `docs/FAQ.md`,
`docs/FUTURE.md` and `docs/ENTERPRISE.md`, each checked
sentence by sentence against the code and the facts
Packet 1 settled (the 3.16 line, the three confinement
backends as field-proven on Linux, Windows and FreeBSD,
and the enforce-by-default posture). Suppositions,
written before the fix pass:

- **P2-S1.** AGENTS.md's nested-shape note gives the
  runner proper's size as 6,928 lines, and its
  human-review paragraph then calls 6,647 lines "a human
  size" -- a stale survivor of an earlier measure; the
  file itself measures 6,928.
- **P2-S2.** AGENTS.md's layout table puts `AGENTS.md`
  and `PROTOCOL.md` at the top of `docs/`; both are root
  manuals, and `docs/`'s own top holds `docs/FUTURE.md`,
  `docs/FAQ.md`, `docs/ENTERPRISE.md` and the support matrix.
- **P2-S3.** PROTOCOL.md section 9.4 still describes OS
  containment as an optional Linux sandbox: a sandbox
  that cannot engage "(no `bwrap`, not Linux)" refuses
  startup, and the work-directory passage says "On
  Windows there is no sandbox: these checks are the
  isolation." Both predate the Windows and FreeBSD
  backends, the section names neither backend, and its
  post-start failure is stated as a fallback without the
  refusal SECURITY.md now records.
- **P2-S4.** The FAQ's remote-execution answer calls
  everything past the signature "opt-in containment" and
  names only the bubblewrap sandbox -- against the
  enforce-by-default posture Packet 1 established.
- **P2-S5.** The FAQ's main-machine answer says "The
  defaults favor 'it just works'" -- the security modes
  have defaulted to `enforce` since the secure-by-default
  landing, so the sentence inverts the current default
  story.
- **P2-S6.** FUTURE.md's cage bullet says only bwrap
  stops a job, that FreeBSD and Windows merely detect a
  bad write after it happens, and that "a jail, a job
  object with a restricted token" is still needed; both
  backends landed and were field-proven on 2026-11-10,
  and only macOS still lacks a cage. Its egress bullet
  likewise says nothing off Linux exists, while the
  FreeBSD jail denies all network.
- **P2-S7.** FUTURE.md's audit bullet says
  `security-audit.jsonl` "has no hash chain"; the audit
  log carries the tamper-evident chain in
  `runner/guard/security.py`, verified through
  `runner/ops/auditreport.py`. What remains open there is
  an append-only flag and a remote copy.
- **P2-S8.** FUTURE.md cites five paths in the retired
  layout (`docs/use/networking.md`,
  `docs/oracle/job-review.md`,
  `docs/design/approval-gate-design.md`,
  `docs/design/v3-dtls-over-email-plan.md`,
  `docs/proofs/dtls-over-email-v3.md`); none of those
  paths exists -- the files live under `docs/steady/` and
  `docs/infrastructure-documents/`.
- **P2-S9.** start-here.md's index has fallen behind the
  shelf it maps: the arrival window closes at 2026-11-06
  though shelf files arrived after; the security drawer
  is counted at 8 files, design at 7 and use at 8; the
  drawers' total is given as 164; and `questions.md` and
  `windows.md` are dated untouched since October though
  both changed on 2026-11-10.
- **P2-S10.** INSTALL.md's install-and-run story, the
  FAQ's remaining answers, PROTOCOL.md outside section
  9.4, and `docs/ENTERPRISE.md` -- the placeholder rule 6
  keeps as-is -- need no correction.

Each supposition is settled against the code in the
commits that follow this note; the conclusions stand at
the end of this section when the packet lands.
Conclusions (2026-11-10, the same evening): **P2-S1
confirmed** -- the human-review paragraph now reads
6,928, the figure the core paragraph and the file itself
carry. **P2-S2 confirmed** -- the layout table now names
`docs/`'s own top files (`docs/FUTURE.md`, `docs/FAQ.md`,
`docs/ENTERPRISE.md` and the support matrix). **P2-S3
confirmed** -- section 9.4 now names all three backends
with their shapes (bubblewrap; Job Object + restricted
token + low integrity, 512 MiB, no filesystem namespace
isolation; the per-job jail, `/work` the only writable
mount, no network at all, 512 MiB at spawn), states the
startup refusal for a platform with no backend as well
as one whose backend cannot engage, records a post-start
failure as a fallback with the job refused -- never run
weaker -- as SECURITY.md states it, and the
work-directory passage no longer calls the Windows
checks the isolation; the heading's "(optional)" is
gone. **P2-S4 confirmed** -- the FAQ's containment is
now stated under the security modes at `enforce` by
default, with all three backends named. **P2-S5
confirmed** -- the main-machine answer now states the
`enforce` default and calls the standing posture not an
opt-in. **P2-S6 confirmed** -- FUTURE.md's cage bullet
now records the two landed backends and their
2026-11-10 field proof, with only the macOS cage
outstanding; its egress bullet now states the FreeBSD
jail's total network denial and the Windows backend's
lack of one, with per-job egress rules still absent
everywhere. **P2-S7 confirmed in part** -- the audit
bullet now states the hash chain and its verification;
the append-only flag and the remote copy remain the
open items there, as they were. **P2-S8 confirmed** --
all five citations now point at the files' real homes
under `docs/steady/` and
`docs/infrastructure-documents/`. **P2-S9 confirmed**
-- start-here's window now closes at 2026-11-10, its
counts are corrected (11 files at the top, 178 in the
drawers; design 8, security 17, use 10, reports 108),
the files its drawer lists omitted are listed with
their dates from main's history, and `windows.md` and
`questions.md` are re-dated to their 2026-11-10
changes. **P2-S10 confirmed** -- INSTALL.md, the FAQ's
remaining answers, PROTOCOL.md outside section 9.4 and
`docs/ENTERPRISE.md` stand as written; the ENTERPRISE
file is the placeholder rule 6 keeps as-is and was not
touched.
The defaults registry's doc lines followed the moved
statements (the PROTOCOL.md inference-block and
key-policy lines, and the FAQ's poll line). Guard
evidence: the 139-test doc guard batch is green,
including the drift guard and the reader-docs line; the
divergences file's grep max-matches family fails
identically on the pristine base in this cell and is
recorded there as pre-existing, not as this packet's.

## The documentation overview, Packet 3: suppositions recorded before the check (2026-11-10)

Packet 3 of the overview takes the operator-facing
steady shelf: the 10 files under `docs/steady/use/`,
the 12 under `docs/steady/project/`, and
`docs/steady/sending.md`, `docs/steady/networking.md`,
`docs/steady/extensions.md`,
`docs/steady/feature-tiers.md` and
`docs/steady/fuzzing.md` — 27 files, each checked
sentence by sentence against the code and the current
facts (the 3.16 line; the 3 confinement backends as
field-proven; the secure-by-default enforce posture;
the reply-to-self default the root manual carries;
the fuzzing standards where a file states them).
Suppositions, written before the sentence check ran:

- **P3-S1.** `docs/steady/networking.md` predates the
  platform confinement backends: its trust-boundary
  account will describe a signed job as running as the
  runner's account — an admin account by default —
  with an unrestricted network edge, and its cage
  account will name only the Linux sandbox, call the
  Windows cage parked and unbuilt, and omit the
  FreeBSD jail entirely.
- **P3-S2.** `docs/steady/feature-tiers.md` will be
  stale in 2 of its evidence rows: the tier-1
  confinement row will name only the bubblewrap
  sandbox and the workspace snapshot check, and the
  tier-3 protocol-version-3 row will say no shipped
  module speaks version 3, though the tree ships the
  version 3 carriage behind its config gate. Its
  counts (28 extension folders, 5 shipped transports)
  will check out.
- **P3-S3.** `docs/steady/sending.md`'s code-level
  claims (the interpreter rule, the authority
  tripwire, the remote-upgrade halves) will check out,
  but the page will nowhere state the reply-to-self
  default for a system sending on a user's behalf: it
  describes `--reply-to` only for the task-board
  subcommands.
- **P3-S4.** Several Packet 3 files will carry links
  and paths broken by the documentation
  reorganization: the Docker page's link to the
  install manual, the idea321 runbook's link to the
  security test plan, the live examples' link to the
  Oracle configuration page, the roadmap spec's link
  to the future page, the fuzzing page's link to the
  idea321 runbook, and the networking page's pointers
  to the senses page and the security-gaps page.
- **P3-S5.** The shelf's dated records — the live
  examples' logs, the de_dust narratives, the
  telephone-pole pages, the archived roadmap spec,
  the finished-future note — will stand as records
  and need no rewriting; `docs/steady/fuzzing.md`'s
  slotted core figures will match the recorded facts
  in the statistics record.
- **P3-S6.** At least 1 use-runbook page will describe
  confinement in Linux-only terms (the sandbox named
  as `bwrap` with no platform qualification), where
  the current fact is 3 backends with a refusal —
  never a weaker run — where one cannot engage.
- **P3-S7.** `docs/steady/extensions.md`'s catalog
  counts (28 folders shipping, 25 pinned in the
  table) will check out against the tree.

Each supposition is settled against the code in the
commits that follow this note; the conclusions stand
at the end of this section when the packet lands.

Conclusions (2026-11-10, the same evening): **P6-S1
confirmed** — layout.md's docs account now states the
two-shelf layout (the steady shelf and the
infrastructure shelf, with the ietf drawer and the
archive beside them), and every path it cites —
transports, safeguards, the extensions walkthrough,
hosting, the queues Worker, the use runbook, the
changelog, contributing, the specimens and the
hardening files in `docs/steady/security/` itself —
names the file's current home. **P6-S2 confirmed** —
the playbook's present-tense pointers now name
`docs/infrastructure-documents/project/campaign-standing-orders.md`,
`docs/steady/project/de_dust.md`,
`docs/steady/project/de_dust2.md` and
`docs/infrastructure-documents/oracle/configuring-oracle.md`.
**P6-S3 confirmed, and wider than supposed** — beyond
the head's routings, the operative body of the
standing orders (everything above the ledger) carried
the retired paths in its queue items — the questions
file, the seats' forum, the regression passes file
(now `docs/steady/specimens/passes.jsonl`), the
coverage-gaps refresh, the de_dust plans, the testing
page and the threat model — and every one now names
the current home; the ledger below stands as the dated
record it is. **P6-S4 confirmed** — testing.md's
citations now name the contributing page, the Oracle
configuration page, the sending page and the
live-examples page at their current homes, and the
live-capture and coverage sentences state where those
records actually stand (shelved flat in
`docs/steady/reports/` and `docs/steady/specimens/`).
**P6-S5 confirmed in part, corrected in detail** —
the Windows fixed count was wrong: the job shards by
the duration table, and the table row now says so.
The macOS job is not table-sharded; it runs the suite
3 ways in parallel (`--jobs 3`), and the row now
states that mechanism instead of a core count.
**P6-S6 refuted** — the nine guard jobs are the
release job's nine named needs in the build workflow
(`test`, `build-python`, `build-windows`,
`build-windows-arm64`, `build-linux`,
`build-linux-arm64`, `build-macos`,
`build-macos-x86_64`, `build-pi-light`); 17 is the
workflow's total job count, a different number, and
release-readiness.md stands unchanged. **P6-S7
confirmed, and wider** — constraints.md's confinement
entry no longer calls the sandbox Linux-only (the
parenthetical now records that no backend engages on
macOS), the Decision 1 citations in constraints.md
and properties.md name
`docs/steady/present-but-invalid-config.md`, the
upgrade-key entry cites `docs/steady/sending.md`, and
the C16 entry Argon found cites the transports page
at its infrastructure home. **P6-S8 confirmed** —
goals.md and thinking.md now gather their findings at
`docs/infrastructure-documents/security/model-and-proof-testing.md`,
and dtls-over-email-v3.md cites the v3 plan under
`docs/infrastructure-documents/design/` and the
version 3 draft in its `source/` home. The stage
records stand as written; their retired paths are
flagged here, not corrected in place: the
`docs/proofs/` run directories in stage4-p2 through
stage4-p5, the model-document path in stage4-p2, and
the Decision 1 path in stage4-p6. **P6-S9
confirmed** — statistics.md's figures match the
figure slots and the core record
(`refresh_figures.py --check` is green on the landing
tree), and the two audits agree with it at their own
dated measures. **P6-S10 confirmed** — cs_office.md
and cs_office-postures.md check out against the
disclosure tool and the Oracle's instruction home;
the rev plan and the release gate stand as dated
2026-11-09 records; the gate's confinement registry
omits the Windows and FreeBSD confinement modules in
the tool exactly as in the prose, so the gap is the
tool registry's, flagged here for a code lane rather
than corrected in prose that would diverge from it;
and testing.md's FreeBSD rows stand — the hosted VM
leg with no green run yet and the fleet node's first
local proof are different claims, and both are stated
as what they are.

The outside read (Argon, gemini-4-argon, on the
billed key the conductor authorized for this
overview): all 57 files were sent in full, headed by
their paths, against a verified-facts block, in one
sitting — 429,028 prompt tokens by the API's own
count. Argon's findings stand under Argon's stamp;
Muse's decisions on each stand under Muse's.

Agent-Stamp: 00000000-argon-26a0-ff29-7825440c1fb9 —
Argon independently confirmed S1, S2, S3, S4, S7 and
S8, and raised, past the suppositions: the standing
orders' Queue S paragraph pinning a job-time
confinement fallback that runs the job unsandboxed;
its M6 item describing confinement as bwrap alone;
its parked-cages item (Queue C2) still parking the
Windows and FreeBSD cages; constraints.md's C16
transports path and its summary table's "Six security
modes" against its own seven-mode text;
content-rung-cap.md's closing bullet stating the
FreeBSD shell was not run; dtls-over-email-v3.md's
draft path missing its `source/` folder; layout.md's
top-of-docs list omitting FUTURE.md, the support
matrix and the checklist; the playbook's
red-by-design recording method against the
expectedFailure practice; properties.md's P2 fallback
statements; the duplication audit's Direction
sentence calling 3.65% the current measure;
thinking.md's fleet snapshot and its silent-field-drop
disposition; release-readiness.md's nine guard jobs
as an error against the workflow's 17; constraints.md
C17's result-view default and C18's sandbox sentence
as stale; and testing.md's Windows roster row and
macOS sharding as stale.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 —
Muse's decisions, each verified against the code
before acting. Fixed, on Argon's pointing: the Queue
S paragraph (the code's decision, `runner/runner.py`'s
confinement query as Q135 settled it, denies the job
when confinement cannot engage at job time under
enforce — the WARN line and the fallback audit entry
record the denial and the job does not run; the
paragraph now records that the 2026-10-15 decision's
confinement half no longer stands, in the same shape
the file already uses for its job_user half); the M6
item (the Windows and FreeBSD forms now named beside
the Linux one); the parked-cages item (the Windows
and FreeBSD cages landed and were field-proven on
2026-11-10; the macOS cage alone stays parked); the
C16 path; the summary table's "Seven security modes"
(`runner/guard/security.py`'s FEATURES names 7); the
cap bullet (the 15.0 record's parser phase ran in the
guest and passed on 2026-11-02; the record still not
run is the 15.2 one); the v3 draft's `source/` path;
and the top-of-docs list (completed inside the S1
fix). Flagged, not fixed: the playbook's recording
method (the document is the campaigns 1–2 record
under its own supersession banner, and main was red
by design under it then); properties.md's P2
statements (they are the checked model's statements
at the harvest commit; rewriting them would falsify
the proof record — the conformance family, not the
statement, is what tracks the current code); the
duplication audit's Direction sentence (a closed
dated audit whose figures the dormant audit expressly
supersedes); thinking.md's fleet snapshot and field
disposition (a reasoning record; stage4-p4's Q129
update is the fresher record of the disposition); and
the stage-record paths under S8. Refuted on
verification: the nine guard jobs (see S6);
constraints C17 (the code fallback in
`runner/ops/policy.py` still reads `full` when the
key is absent — the seed reads attested, and the
single-story item stands in release-readiness as the
gap it still is; the inventory states the code as it
is); constraints C18 (the sentence states that
enforce plus a working mechanism sandboxes, which is
true; it states no job-time fallback); the Windows
roster row (`runner/tests/switch_roster.py` carries
no windows-needs entries — the Windows leg judges the
platform-neutral controls, as testing.md says); and
the macOS duration table (the build runs `--jobs 3`).

Guard evidence on the landing tree: the doc guard
batch (layout, reader-docs quiet, figure slots, proof
constraints, cs_office, version rot, design docs)
reads 90 passed and 2 failed, and the same 2 fail
identically on the pristine base in the same pass —
the layout stale-path test (its 7 offenders stand in
AGENTS.md's layout table and in this file's Packet 2
section, both outside this packet) and the version-rot
test (this file's earlier sections name the current
version, likewise pre-existing). The packet's fixes
added no offender: a direct scan of the layout test's
own patterns over the landing tree finds no Packet 6
file among them. Files checked with no findings: the
proofs readme, hybrid-fuzz-10024.md, temp-reap.md,
shotgun-queue.md, the content-rung and content-sh
records, stage2, stage3, the stage5–stage10 records,
dtls-over-mailbox.md and
dtls-record-layer-and-framing.md.

Conclusions (2026-11-10, the same evening): **P3-S1
confirmed** — the networking page's job ran as the
runner's admin account with an unrestricted edge and
its cage named only the Linux sandbox with the
Windows cage parked; the trust-boundary account, the
cage account and the diagram now state the shipped
defaults (the separate job user on POSIX, the
confinement spawn on Windows, loopback-only on Linux,
no network at all on FreeBSD, and the Windows
backend's lack of a network control stated plainly,
WFP rules still unbuilt). **P3-S2 confirmed** — the
tier-1 confinement row now names all 3 backends, and
the tier-3 version 3 row now records the shipped
carriage (`runner/wire/dtls_mailbox.py`, gated by
`dtls_via_email`); the counts held (28 extension
folders, 5 shipped transports, both verified against
the tree). **P3-S3 confirmed** — the sending page's
code-level claims all held, and the page now states
the reply-to-self default beside its `--reply-to`
account: without the flag the result goes to the
runner's mailbox, and a system sending for a user
addresses the result to the user, naming the price of
a different destination up front. **P3-S4 confirmed,
and wider than supposed** — beyond the 5 broken
relative links, the retired layout's paths ran across
the project shelf (the de_dust pages, hosting, the
roadmap spec, the telephone-pole pages, the
finished-future note, contributing, the handoff note,
the industry map) and the fuzzing page; every one now
names the file's current home, and a closing scan of
all 27 files finds no broken link and no missing
path. **P3-S5 confirmed with 1 exception class** —
the dated records stand untouched, but present-tense
capability claims sitting inside otherwise dated
pages were corrected where they state today's facts:
the handoff note's queues row and open item (the
queues transport ships), the other-uses survey's
sandboxing gap (sandboxing ships, enforce by
default; the gap is per-class resource profiles),
and the industry map's unused integrity-levels line
and its self-contradicting Oracle-log item. The
fuzzing page's slotted figures match the recorded
facts; a live measure of the core has since drifted
36 lines in `runner/ops` past those facts, and the
refresh that settles it belongs to the release cut's
figure pass, not to this packet. **P3-S6
confirmed** — the idea321 runbook's confinement row
now names all 3 backends. **P3-S7 confirmed** — the
extensions catalog counts are exact (28 folders
shipping, 25 pinned, the table's 17 + 8 rows).

Findings past the suppositions: the Docker page's
image verification named a `cosign verify` no
workflow performs — the image carries a Sigstore
build-provenance attestation, verified by digest
with `gh attestation verify`, as the verification
page already stated; the own-cloud page's queue
example could not run as written (it named no HMAC
secret, which the sender requires) and now carries
one; the contributing page's release instructions
waited on 9 CI jobs where the build workflow now
defines 17. Files checked with no findings: the
local-SI test page, the Pi Light readiness page, the
platforms page, the extensions page, de_dust2,
fy_iceworld, the runner-line-reduction runbook and
the telephone-pole vocabulary. Guard evidence on the
landing tree: the reader-quiet, support-matrix and
SECURITY-claims sets read 13 passed with 11 subtests;
the figure check is clean; the doc-divergences set
reads 907 passed and 17 failed, against 904 passed
and 24 failed on the pristine tree in the same pass —
the packet's fixes cured 7 of the pristine failures
and added none, and the 17 that remain are the
pre-existing grep max-matches family this cell's
runs have carried throughout.

## The documentation overview, Packet 7: suppositions recorded before the check (2026-11-10)

Packet 7 of the overview takes the IETF shelf, source
only: the living version 1 and version 2 drafts
(`docs/ietf/draft-slutsky-homing-pigeon/source/draft-homing-pigeon-00.md`,
`docs/ietf/draft-slutsky-homing-pigeon-v2/source/draft-homing-pigeon-v2-00.md`),
the local -04 working drafts beside them
(`draft-slutsky-homing-pigeon-04.md`,
`draft-slutsky-homing-pigeon-v2-04.md`), the version 3
source
(`docs/ietf/draft-slutsky-homing-pigeon-v3/source/draft-slutsky-homing-pigeon-v3-00.md`),
the cover sheet `docs/ietf/status.md`, and the 3 notes
(`docs/ietf/notes/checklist-04-applied.md`,
`docs/ietf/notes/delta-deferred-items-for-approval.md`,
`docs/ietf/notes/trim-02.md`). The mirror rule binds
this packet: the living version 1 and version 2 texts
match the posted IETF texts exactly and are never
edited here; any change worth making is recorded as a
finding, and the cover sheet and the notes may be
corrected only for plain factual errors about the
current state (both drafts stand at -03, ISE
publication pending). The submitted copies are
spot-checked for identity with the sources, not
re-read. Suppositions, written before the identity
and count checks ran:

- **P7-S1.** The mirror holds byte for byte: the
  living version 1 source is identical to the frozen
  `submitted/` -03 markdown, and the living version 2
  source is identical to its frozen -03 markdown.
- **P7-S2.** The cover sheet's posting facts check
  out against the frozen copies' own records: the
  current revision of each draft is -03, version 1
  -03 expires 1 May 2027 and version 2 -03 expires
  6 May 2027, and the per-draft status files agree
  with the cover sheet on revision, submission
  numbers (171771 and 171786) and expiry.
- **P7-S3.** The cover sheet's Next section and Known
  nits section are stale in tense: they speak of -02
  as the revision still to come ("The known nits
  below are the text of -02", "These are the edits
  for -02") though -02 and -03 are both posted and
  the nits were applied in -02; and the Next
  section's "due before 3 May 2027" matches neither
  -03 expiry date the same file states (1 May and
  6 May 2027).
- **P7-S4.** The deferred-items note is stale in the
  opposite direction: it still presents its item S4
  (the `job-id` rule) as the one proposed change
  awaiting a single yes, though the checklist-applied
  note records that change as approved on 2026-11-07
  and applied to the -04 working draft after the cut,
  and the -04 source will show `job-id = 1*128
  word-char` with no `job-id-char` rule standing.
- **P7-S5.** The deferred-items note's em dash counts
  verify exactly: the living drafts hold 6 (version 1)
  and 4 (version 2) em dash characters, and the -04
  working drafts and the posted -02 and -03 sources
  hold 0 each.
- **P7-S6.** The cover sheet's version 3 paragraph
  carries a garbled duplication (the idnits report
  stands "beside the source as
  `draft-slutsky-homing-pigeon-v3-00.idnits.txt`
  beside it in the same folder"), and its statement
  that the renders match the source was written of
  the 2 November final-pass text, before the
  2026-11-06 source correction the same paragraph
  records next.
- **P7-S7.** The checklist-applied note's render
  claims verify against the idnits records beside
  the -04 sources: 0 errors on each draft's text and
  XML runs.
- **P7-S8.** The trim list's quoted phrases verify
  against the submitted -02 sources it names, and
  its negative claims hold for both: neither -02
  source names `PROTOCOL.md`, a path into the
  repository, or a GitHub URL.
- **P7-S9.** The checklist-applied note's account of
  the -04 cut checks out: the -04 sources were cut
  from the posted -03 texts, stand unsubmitted in
  each draft's `source/` folder with their renders
  and idnits records, and the living drafts were not
  edited to make them.
- **P7-S10.** Outside those points the cover sheet
  and the notes are current: the ISE request record,
  the waiting-on list, version 3's local-only state,
  and the -04 checklist's applied, guarded and
  no-change items as the applied note records them.

Each supposition is settled against the records in
the commits that follow this note; the conclusions
stand at the end of this section when the packet
lands.
## The documentation overview, Packet 9: suppositions recorded before the check (2026-11-10)

Packet 9 of the overview is the remainder sweep, computed
at run time as every tracked markdown file not covered by
Packets 1–8. Against a fresh `git ls-files` on remote main
at this packet's start (271 tracked markdown files, the
same count the inventory recorded), the remainder is
exactly the 46 files the assembly plan named: the 3
per-draft IETF status files, 7 steady-shelf files
(`docs/steady/emergency.md`, `overview.md`,
`present-but-invalid-config.md`,
`proofs/connector-roundtrip.md`, `proofs/verify-v31.md`,
`secret-rotation.md`, `verification.md`), the hosted
queue's README, 30 extension READMEs and fixture READMEs
under `runner/extensions/`, 4 test READMEs, and the pull
request template. Each is checked sentence by sentence;
the extension READMEs are checked against the extension
code and manifests they describe. Suppositions, written
before that code check ran:

- **P9-S1.** `docs/steady/overview.md`'s status section
  is stale: it names 3.15.18.12 as the latest published
  release, verified 2026-11-08, though the 3.16 line's
  first release was published on 2026-11-10.
- **P9-S2.** At least 1 extension README will disagree
  with the code it describes — a stated tunable default,
  signal name, or state-file name that its
  `extension.json` or producer does not carry.
- **P9-S3.** `docs/steady/proofs/connector-roundtrip.md`
  carries retired-layout paths: its replay test and its
  sender command are named without the `runner/` home
  the files now live under.
- **P9-S4.** Two steady records cite the retired layout:
  `present-but-invalid-config.md` names the divergences
  report under `docs/reports/` and its Applied-in line
  names `docs/oracle/` and `docs/extend/` homes, and
  `emergency.md` names the researcher identity record in
  capitals and the forum and hold file under a
  `docs/seats/` home none of them lives at.
- **P9-S5.** The 3 per-draft IETF status files agree
  with the cover sheet (`docs/ietf/status.md`, Packet
  7's reading) and with the folders they describe: the
  posted -03 revisions and the -00 through -03 submitted
  sets for versions 1 and 2, and no submitted set at all
  for version 3.
- **P9-S6.** Everything else in the remainder checks
  out: `verification.md`'s release chain,
  `secret-rotation.md` against PROTOCOL.md sections
  14.2 and 14.4 and the sender's keyring commands, the
  queues-worker README against the Worker code, the
  fixture and test READMEs against the files they
  describe, `verify-v31.md` as the bannered historical
  record it declares itself, and the pull request
  template's test command.

Each supposition is settled against the code in the
commits that follow this note; the conclusions stand at
the end of this section when the packet lands, stating
that the sweep is empty-by-construction and re-verified
against a fresh `ls-files` at the packet's close.

Conclusions (2026-11-10, the same evening): **P9-S1
confirmed** — the overview's corpus line now reads
2,400 entries over 30 targets (counted from the
committed corpus in `runner/tests/de_dust/`: 30 target
files, the header line of each excluded), and its
release line now stands on the 3.16 line, verified on
the releases page on 2026-11-10; the page names the
line, not the current version string, at the
version-rot guard's direction. **P9-S2 not confirmed
as supposed** — a scripted cross-check of every
extension README against its `extension.json` and
producer (signal names, numeric, string and list
defaults, state-file names) found no wrong statement;
the one gap was an omission: the job-fuzz README named
no state file where every sibling names its own, and
it now names `.job-fuzz-state.json`, the default its
producer carries. **P9-S3 confirmed** — the round-trip
page's two test paths and its sender command now carry
the `runner/` home both files live under. **P9-S4
confirmed** — the config decision record's report home
and its two Applied-in paths, and the emergency page's
identity-record name and its forum and status paths,
now name the files' current homes. **P9-S5 confirmed
with one correction the check itself surfaced** — the
per-draft status files agreed with the cover sheet and
the folders on every point but one the Packet 7 lane
flagged from the frozen renders: the version 1
per-draft page carried the -03 expiry as 1 May 2027,
where both frozen -03 renders state 6 May 2027; Packet
7 corrected the cover sheet and this packet corrected
the per-draft page, verified against the submitted
text's own header. **P9-S6 confirmed** — the
verification page's release chain, secret-rotation
against PROTOCOL.md sections 14.2 and 14.4 and the
sender's keyring and key-id commands as the code
defines them, the queues-worker README against the
Worker's 2 MB value limit, 8 MB response budget and
quota 429s, the fixture and test READMEs against the
files they describe, and the pull request template's
test command all stand as written; a closing scan of
all 46 files finds no broken relative link.

An outside read of this packet was run through Argon
(gemini-4-argon) over all 46 files in full, with the
measured facts and each extension's manifest-and-code
facts in the same window; its findings stand under its
own stamp:

<!-- Agent-Stamp: 00000000-argon-26a0-ff29-7825440c1fb9 -->
Argon flagged: the emergency page's identity-record
casing and its forum and status paths; the overview's
corpus count and its latest-release line; the config
record's report home and Oracle and transports paths;
the round-trip page's test and sender paths; the
retired paths inside `verify-v31.md`; the de_dust
README's target table, which listed 20 of the corpus's
30 target files; and, as a missing fact, the
confinement backends' absence from the overview page.

Muse's decisions on those findings, under Muse's own
stamp (00000000-muse-7e57-d0c5-58316a922026): accepted
and landed — the emergency, overview, config-record
and round-trip corrections, each already in this
packet's own findings and verified the same way.
Accepted past the suppositions — the de_dust table now
carries all 30 targets: the 10 added rows (address,
collect, dtls_hostile, dtls_session, edge_subject,
keydir, race_board, race_stash, race_state, stage) are
written from their checkers' own contract docstrings
in `runner/tools/de_dust_corpus.py`, each naming the
reader it is held to. Declined, with the reasons
recorded — `verify-v31.md`'s retired paths stand: the
page is a bannered historical record that says not to
run it, and rewriting a frozen verification record's
commands would falsify the record. Declined also —
the overview's confinement absence: the page states no
confinement claim that is wrong, and the confinement
account stands in the README, SECURITY.md and the
support matrix as Packet 1 settled them.

The sweep closes the overview: at this packet's close
a fresh `git ls-files` on remote main counts 271
tracked markdown files, and the remainder recomputed
against the Packets 1–8 lists is the 46 files above and
nothing else — every tracked markdown file stands
covered by exactly one packet, and no file in any
packet's list has left the tree. Guard evidence on the
landing tree: the reader-quiet, layout and
connector-capture batch reads 23 passed with 63
subtests, and 1 failure in the layout stale-path test
whose every flagged line sits in AGENTS.md's layout
table and Packet 2's section of this desk — a
pre-existing family on the head, none of it in this
packet's files; the version-rot guard failed on this
packet's first tree for naming the current version
string in the overview and in P9-S1 above, and this
packet's text has named the line instead since the
follow-up — on the landing tree the guard's only
offender is Packet 8's conclusions section of this
desk, which landed naming the release in full; the
divergences batch's failing classes (the defaults
readers' fifteen-shapes family) read 32 failed on the
pristine base against 30 failed on this packet's tree
in the same subset, and no failure in either run names
this packet's files.

## The documentation overview, Packet 5: suppositions recorded before the check (2026-11-10)

Packet 5 of the overview takes the infrastructure
shelves that parallel Packets 3 and 4: the 1 file
under `docs/infrastructure-documents/use/`, the 2
under `docs/infrastructure-documents/extend/`, the 1
under `docs/infrastructure-documents/oracle/`, the 5
under `docs/infrastructure-documents/security/` and
the 5 under `docs/infrastructure-documents/design/`
— 14 files, each checked sentence by sentence against
the code and the current facts (the 3.16 line; the 3
confinement backends as field-proven on Linux,
Windows and FreeBSD; the secure-by-default enforce
posture; the audit log's tamper-evident hash chain),
and cross-checked against the steady shelf Packets 3
and 4 cover for duplicate or divergent descriptions
of the same facts. Suppositions, written before the
fix pass:

- **P5-S1.** The security shelf's confinement
  accounts still predate the platform backends:
  `threat-model.md` will say the Oracle does not
  contain a job unless Linux bubblewrap engages,
  `safeguards.md` will say a sandbox exists only
  where Linux bubblewrap can engage and that on
  Windows "there is no sandbox," and
  `security-gaps.md` will frame its cage step and
  its FreeBSD row as if no FreeBSD jail and no
  Windows backend exist — each against the
  3-backend fact Packets 1 to 3 established.
- **P5-S2.** `security-gaps.md`'s audit-log
  inventory item will say the audit log has "no
  hash chain" and mark audit integrity absent; the
  audit log carries the tamper-evident chain in
  `runner/guard/security.py`, verified through
  `runner/ops/auditreport.py` — the same correction
  Packet 2 made in FUTURE.md. What remains open
  there is an append-only flag and a remote copy.
- **P5-S3.** `security-gaps.md`'s network-egress
  inventory item will say only bwrap in enforce
  mode blocks a job's egress; the FreeBSD jail
  denies all network, and the Windows backend has
  no network control — the shape Packet 3's
  networking page now states.
- **P5-S4.** The packet's files will carry paths
  from the retired layout throughout:
  `docs/security/`, `docs/use/`, `docs/design/`,
  `docs/oracle/`, `docs/extend/`, `docs/proofs/`,
  `docs/project/`, `docs/reports/` and
  `docs/archive/` pointers in the threat model, the
  safeguards, the security gaps, the Oracle
  configuration page, the transports page, the
  model-and-proof map and the version 3 plan,
  where the files now live under `docs/steady/` and
  `docs/infrastructure-documents/`. Two relative
  links will be broken by the same move: the
  safeguards' link to SECURITY.md and the Oracle
  configuration page's link to the live-examples
  page.
- **P5-S5.** `configuring-oracle.md`'s key entries
  and defaults will otherwise check out against
  the code and the defaults registry that pins
  them, and its present-but-invalid account will
  match the decision the steady shelf records.
- **P5-S6.** The design shelf's 3 sentence reviews
  and the version 3 carriage review pass are dated
  records of their passes and will stand as
  records; the version 3 plan is a build record
  whose own addenda already correct its early
  text, and only its retired-layout pointers (in
  P5-S4) will need correcting.
- **P5-S7.** `scripts.md`, `worker-agents.md`,
  `owasp-reference.md` and
  `model-and-proof-testing.md`'s model account
  will check out against the code, apart from the
  proof map's retired `docs/proofs/` pointers in
  P5-S4.

Each supposition is settled against the code in the
commits that follow this note; the conclusions stand
at the end of this section when the packet lands.

Conclusions (2026-11-10, the same evening): **P5-S1
confirmed** — the threat model's containment bullet,
the safeguards' first section and containment
section, and the security-gaps cage step and
FreeBSD row all stated the pre-backend shape; each
now names the 3 backends (Linux bubblewrap; the
Windows Job Object, restricted token and low
integrity; the FreeBSD per-job jail) with the
refusal — never a weaker run — where a platform's
backend cannot engage, and the safeguards no longer
call the Windows staging checks the isolation.
**P5-S2 confirmed** — the security-gaps audit item
now states the tamper-evident hash chain and its
verification through `runner/ops/auditreport.py`;
the append-only flag and the remote copy remain
the open items there, and the item reads partial.
**P5-S3 confirmed** — the egress item now states
bwrap's block, the FreeBSD jail's total network
denial, and the Windows backend's lack of a network
control. **P5-S4 confirmed, in full** — every
retired-layout pointer in the packet now names the
file's current home under `docs/steady/` or
`docs/infrastructure-documents/`, across the threat
model, the safeguards, the security gaps, the
Oracle configuration page, the transports page,
the model-and-proof map (its 12 `docs/proofs/`
pointers) and the version 3 plan; the safeguards'
SECURITY.md link and the configuration page's
live-examples link resolve again, and a closing
scan of all 14 files finds no broken relative link
and no retired path outside the dated records in
P5-S6. **P5-S5 confirmed** — the configuration
page's entries and defaults check out against the
code and the registry that pins them; the page's
one Linux-only confinement phrase (the
`workspace_root` entry) now names the platform
backend. **P5-S6 confirmed with 1 pointer
corrected** — the 3 sentence reviews and the
carriage review pass stand as the records of their
passes, untouched but for the version 1 and 2
review's opening pointer to its companion, which
now names that file's current home.
**P5-S7 confirmed** — `scripts.md`,
`worker-agents.md` and `owasp-reference.md` check
out as written, and the model-and-proof page's
model account stands apart from the path
corrections in P5-S4 and the outside read below.

An outside read of this packet was run through
Argon (gemini-4-argon) over all 14 files in full;
its findings stand under its own stamp:

<!-- Agent-Stamp: 00000000-argon-26a0-ff29-7825440c1fb9 -->
Argon flagged: `scripts.md`'s platform-card
sentence against the handshake card's fields; the
transports page's, the configuration page's and
the model-and-proof page's statements that the
shared secret itself is the DTLS pre-shared key,
against the version 3 plan's 2026-11-06 addendum
(the PSK is an HKDF-derived key, info
`homing-pigeon dtls psk v1`); the same pages'
"alone among the pipes" secret-handoff claims
against the email extension's `dtls_via_email`
handoff, and the configuration page's missing
`dtls_via_email` entry; its `dtls_greeting`
"OS family only" parenthetical against the card
the code builds; its present-but-invalid summary
list against the size caps and other refuse-class
keys its own later entries state; the
model-and-proof ceilings passage and the
security-gaps one-sentence and cage step against
the Windows backend's lack of filesystem
isolation; the safeguards' `/usr` passage read as
universal; the security-gaps Windows table row's
"stronger cousin" sentence; the version 1 and 2
review's companion path; the version 3 plan's
superseded early sections; and the version 3
sentence review's scope paths. It returned no
findings for `worker-agents.md`,
`owasp-reference.md`, the threat model, the
handshake design page, or the carriage review
pass.

Muse's decisions on those findings, under Muse's
own stamp (00000000-muse-7e57-d0c5-58316a922026):
accepted and landed, each verified against the
code first — the derived-PSK statements in all 3
pages (`runner/wire/dtlsproto.py`'s
`psk_from_secret`); the secret-handoff statements
(the email extension terminates DTLS when
`dtls_via_email` is on and is handed the secret for
it); the missing `dtls_via_email` entry, added to
the configuration page with the defaults
registry's pins following the moved lines (15 rows
shifted by 1); the `dtls_greeting` parenthetical
(the `family` card carries OS family, default
interpreter and protocol versions); the
Windows-filesystem-limit statements in the
model-and-proof ceilings, the security-gaps
one-sentence and cage step, and the Windows table
row's cousin sentence; the safeguards' `/usr`
passage scoped to the Linux sandbox; and the
review's companion pointer. Accepted in narrowed
form — `scripts.md`: the `pong` card does carry
`key_ids` (the runner adds the names to the card
it returns), so the sentence stands for the
`pong`; its last clause now states that the
handshake payload carries the platform card
without the key names, which is the shape the DTLS
extension builds. Declined, with the reasons
recorded — the present-but-invalid summary list:
that sentence is the decision's own canonical
wording, carried identically in the design note
and in PROTOCOL.md, and the page's per-key entries
state their own refuse behavior where it applies.
The version 3 plan's early sections: the plan is
a chronological build record whose addenda
supersede its early text in place, and the live
pages that repeated the superseded mechanism are
the ones corrected. The version 3 sentence
review's scope paths: they name the draft as it
stood at that pass and are that record's history,
not a pointer for today's reader. Guard evidence:
Guard evidence on the landing tree: the defaults hunt reads 33 passed with 953 subtests; the reader-quiet, design-docs, skip-registry and proof-constraints sets are green in their batch (78 passed across the 5-file batch, with the 1 failure below); the doc-divergences set reads 904 passed and 53 failed, the failures in the grep max-matches family this cell's runs have carried throughout the overview, and none in a page this packet touched. The batch's 1 failure is not this packet's: the version-rot guard names this desk file itself, for a current-version string in a parallel lane's section landed after this packet's suppositions; no Packet 5 file carries one.


## The documentation overview, Packet 6: suppositions recorded before the check (2026-11-10)

Packet 6 of the overview takes the infrastructure
project record and the proofs prose: the 13 files under
`docs/infrastructure-documents/project/` and the 44
under `docs/infrastructure-documents/proofs/` — 57
files, checked sentence by sentence against the code
and the current facts (the 3.16 line; the 3 confinement
backends as field-proven on Linux, Windows and FreeBSD;
the secure-by-default enforce posture; the two-shelf
documentation layout the reorganization settled, steady
and infrastructure-documents; and statistics.md as the
canonical size record every figure is checked against).
The packet runs as 6A (the project record) and 6B (the
proofs) in one lane, in that order. Suppositions,
written before the sentence check ran:

- **P6-S1.** `layout.md` describes the retired layout
  throughout: its docs account names `docs/extend/`,
  `docs/security/`, `docs/use/`, `docs/oracle/`,
  `docs/project/`, `docs/design/` and `docs/reports/`
  as the tree's drawers, and cites
  `docs/CHANGELOG.md`, `docs/CONTRIBUTING.md`,
  `docs/specimens/`, `docs/security/hardening/`,
  `docs/use/runbook.md` and `docs/project/hosting.md`
  at paths where none of them lives — the files stand
  under `docs/steady/` and
  `docs/infrastructure-documents/` in the current
  two-shelf layout.
- **P6-S2.** `campaign-playbook.md`'s present-tense
  pointers use the retired layout: the campaign "runs
  today" from `docs/project/campaign-standing-orders.md`,
  the desk fixes crashes under `docs/project/de_dust.md`,
  the de_dust2 passage cites `docs/project/de_dust2.md`,
  and the Decision 1 sentence names
  `docs/oracle/configuring-oracle.md` — none of those
  paths exists.
- **P6-S3.** `campaign-standing-orders.md`'s operative
  head — the routings a running campaign follows today,
  not its dated ledger — uses the same retired paths
  for the strategy, the playbook and the questions
  file (`docs/project/de_dust2.md`,
  `docs/project/campaign-playbook.md`,
  `docs/seats/questions.md`, `docs/seats/.com.chat`).
  The ledger entries below the head are dated records
  and are not expected to move.
- **P6-S4.** `testing.md` cites the retired layout in
  its current guidance: `docs/CONTRIBUTING.md` for the
  `--oracle` flag, `docs/oracle/configuring-oracle.md`
  for the flag map, `docs/use/sending.md` and
  `docs/use/live-examples.md` for the end-to-end and
  live-capture accounts, and `docs/reports/` for the
  live-capture corpus and the coverage reports.
- **P6-S5.** `testing.md`'s platform table states the
  Windows suite as "sharded over 4 cores" and the
  macOS suite as "sharded over 3 cores" — fixed counts
  the build no longer uses: both jobs now shard by the
  duration table (`runner/tools/windows_durations.py`
  and its macOS counterpart), so the shard count is
  the table's, not a fixed core count.
- **P6-S6.** `release-readiness.md` section 7 states
  the build job's guard as "the nine guard jobs
  green"; the build workflow defines 17 jobs — the
  same fact Packet 3 corrected on the contributing
  page.
- **P6-S7.** `constraints.md`'s confinement entry says
  the sandbox "is Linux-only" — a survivor of the
  inventory's harvest commit, before the Windows and
  FreeBSD backends landed; confinement now has a
  backend per platform family and refuses where none
  can engage. The Decision 1 citations in
  `constraints.md` and `properties.md` name
  `docs/design/present-but-invalid-config.md`, which
  lives at `docs/steady/present-but-invalid-config.md`,
  and `constraints.md`'s upgrade-key entry cites
  `docs/use/sending.md` for `docs/steady/sending.md`.
- **P6-S8.** The proofs' living summaries cite the
  retired layout for current reading: `goals.md` and
  `thinking.md` gather findings in
  `docs/security/model-and-proof-testing.md` (now
  `docs/infrastructure-documents/security/model-and-proof-testing.md`),
  and `dtls-over-email-v3.md`'s built list cites
  `docs/design/v3-dtls-over-email-plan.md` (now under
  `docs/infrastructure-documents/design/`). The stage
  and content-rung records are dated run records and
  are expected to stand as written, retired paths in
  their run procedures included.
- **P6-S9.** `statistics.md`'s figures check out
  against the figure slots and the core record they
  are generated from — it is the canonical record and
  needs no correction in this packet; the dormant-code
  and duplication audits' figures agree with it at
  their own dated measures.
- **P6-S10.** `cs_office.md`, `cs_office-postures.md`,
  `dormant-code-audit.md`, `duplication-audit.md`,
  `official-release-rev-plan.md` and `release-gate.md`
  need no correction: the first two were checked
  against the disclosure tool and the Oracle's
  instruction home, the audits are dated measures, and
  the rev plan and gate are dated 2026-11-09 records
  whose state-at-writing lines are true as dated. The
  release gate's confinement class registry omits the
  Windows and FreeBSD confinement modules — but it
  reproduces the tool's registry exactly, so the gap
  is the tool's, flagged here rather than corrected in
  prose that would then diverge from the code. The
  FreeBSD row in `testing.md` — the hosted VM leg with
  no green run yet, beside the fleet node's first
  local proof — is likewise expected to stand: the leg
  and the node's backend proof are different claims.

Each supposition is settled against the code in the
commits that follow this note; the conclusions stand
at the end of this section when the packet lands.

## The documentation overview, Packet 4: suppositions recorded before the check (2026-11-10)

Packet 4 of the overview takes the remainder of
`docs/steady/security/`, the `docs/steady/design/` and
`docs/steady/oracle/` shelves, and the seats drawer
(`bravo.md` and `questions.md`) — 24 files, each checked
sentence by sentence against the code and the facts the
earlier packets settled (the 3.16 line; the 3 confinement
backends as field-proven; the secure-by-default enforce
posture; the shipped agent-state guard). As Packet 1
did, this packet also takes an outside read through
Argon before its conclusions land; Argon's findings
stand below under Argon's stamp, with Muse's decisions
recorded beside them. Suppositions, written before the
fix pass:

- **P4-S1.** `docs/steady/oracle/senses.md`'s
  cage-verification passage predates both the
  secure-by-default landing and the platform backends:
  it will say the Linux cage gives loopback only in
  enforce mode and that by default a job's network edge
  is unrestricted, call the cage opt-in enforcement,
  describe the Windows cage as per-user WFP rules tied
  to the job identity, and omit the FreeBSD jail —
  whose denial is total — entirely.
- **P4-S2.** The retired documentation layout's paths
  will run across this packet's reader pages: the
  senses page's pointers to the DRI playbook and the
  remediation design, the DRI playbook's pointers to
  the senses page and the future page, the job
  review's pointers to the known-failures record and
  the future page, the remediation design's pointer to
  the opinion design, the opinion design's pointers to
  the finished-future note, the specimens file, the
  live examples and the asymmetric-signing design, the
  CI runtime note's pointer to the platforms page, the
  agent-stamp design's pointers to the job review and
  the stamp-audit baseline, and the extension-review
  design's pointer to the extensions guide.
- **P4-S3.** `privacy-design.md` section 1 will count
  6 guard features and name `runner/tools/posture.py`
  as the disclosure postures' home; the modes family
  carries 8 features (the shelter and the agent-state
  guard joined it), and the disclosure postures are
  declared in `runner/tools/disclosure.py`. Its
  section 6 queue and section 8 disposition will
  record the agent-state guard as queued work, though
  the guard shipped — the staged-content tool, its
  mode in `runner/guard/security.py`, and its row in
  the shipped example config.
- **P4-S4.** `agent-stamp-design.md` will name
  `40000e00` as the active questions desk; that stamp
  stands recycled on the record, its roles carried by
  the Muse stamp, and the record file it names in
  capitals (`RESEARCHER_IDENT.md`) stands in lowercase
  on disk and in its own test.
- **P4-S5.** `hardening_report.md` and
  `security-test-plan.md` are dated records; their
  retired-layout pointers will prove to sit inside
  the records' own past tense and stand, except any
  pointer a present-tense passage still sends a
  reader to.
- **P4-S6.** `privacy-fremont-research.md`'s
  `docs/security-*` paths are the Fremont Derby
  project's own files, surveyed as another project's
  record, not pointers into this tree — they will
  check out as written.
- **P4-S7.** `questions.md`'s retired-layout paths sit
  inside dated, answered entries — the forum record,
  which stands unrewritten — and `bravo.md` states
  the lane rules as they stand; neither will need a
  correction.
- **P4-S8.** The packet's remaining present-tense
  claims will check out against the code:
  `agent-state-files.md`'s shipped forms (the ignore
  blocks, the renderings template, the staged guard,
  its tests), the shelter and warning pages against
  `runner/oracle/personal_docs.py` and its shelter
  tool, the attack-v20 delta against
  `runner/oracle/detection.py`, the Oracle's standing
  instructions against the briefing assembly, and
  `privacy-models.md` as the dated literature survey
  it declares itself.

Each supposition is settled against the code in the
commits that follow this note; the conclusions stand
at the end of this section when the packet lands.

The outside read (Argon, gemini-4-argon, on the
billed key the conductor authorized for this
overview): all 24 files were sent in full, headed by
their paths, against a verified-facts block, in one
sitting. Argon's findings stand under Argon's stamp;
Muse's decisions on each stand under Muse's.

Agent-Stamp: 00000000-argon-26a0-ff29-7825440c1fb9 —
Argon confirmed the suppositions' core: the senses
page's cage passage (the enforce default inverted,
the Windows cage stated as WFP rules, the opt-in
framing, the retired pointers), the privacy design's
6-feature count, its `runner/tools/posture.py` path,
and the agent-state guard recorded as queued in
sections 6 and 8; the agent-stamp design's record
filename in capitals, its active desk named as the
recycled `40000e00`, and its retired job-review and
stamp-audit pointers; and the retired-layout pointers
across the DRI playbook, the job review, the opinion
design, the remediation design, the CI runtime note
and the extension-review design. Past the
suppositions Argon raised: the hardening report's
M6 row and confinement-fallback bullet stating the
runtime fail-open as present behaviour; the
remediation design's as-built strain passage in the
same terms; the approval-gate design's proposed
`security.modes.approval` default of `off`, against
the family's enforce default; and the
extension-review guide's home as the infrastructure
shelf's extend drawer. Argon read the remaining 12
files clean.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 —
Muse's decisions, each verified against the code
before acting. Adopted and fixed, on Argon's
pointing and on the hand check's: everything named
above, with 2 corrections of Argon's own directions —
the extension guide's current home is
`docs/steady/extensions.md` (the section title Argon
quoted stands there; no extensions page stands in
the infrastructure extend drawer), and the
stamp-audit baseline's current home is
`docs/steady/reports/2026-10-27.md`. The hardening
report's 2 passages keep their 2026-10-15 record and
gain the current chain beside it (under `enforce` a
job-time fallback refuses the job — SECURITY.md
states it), in the shape Packet 6's lane used for
the same settlement in the standing orders. Not
adopted: the approval-gate default. That document
is the design of a feature that is not built; its
`off` default is a stated design choice for a
human-in-the-loop gate — the document itself records
that the posture check does not nag about it — not a
claim about the shipped modes, whose enforce default
stands untouched. Argon missed 3 findings the hand
check caught and fixed: the opinion design's
finished-future pointer, the job review's 2
known-failures pointers, and the hardening report's
M9/M10 design pointers.

Conclusions (2026-11-10, the same evening): **P4-S1
confirmed** — the senses page's cage-verification
spec now states the cages as they stand (Linux
loopback and the FreeBSD jail's total denial under
the confinement mode at `enforce` by default, a
backend that cannot engage refusing the job, and
the Windows backend's lack of a network control
stated plainly, WFP rules not built), and its
hardening paragraph no longer calls the modes
opt-in. **P4-S2 confirmed, and wider in one place**
— every retired pointer Argon and the hand check
found now names the file's current home, including
the hardening report's M9/M10 rows; a closing scan
of all 24 files finds no remaining retired-layout
path in a present-tense passage. **P4-S3 confirmed
and overtaken** — the privacy design now counts
the modes family as it stands and names
`runner/tools/disclosure.py`; the count moved
under the packet (8 when the check ran; the Q139
build landed a 9th feature, `v2_question`, in
parallel, and the page states 9), and sections 6
and 8 record the agent-state guard as the shipped
form it is, its extensions and the general
tree-wide test alone remaining queued. **P4-S4
confirmed** — the agent-stamp design names the
record in its lowercase spelling throughout and
the active desk as the Muse seat. **P4-S5
confirmed** — the security test plan carries its
archived banner and stands entire, its local-test
claim included (the module stands at
`runner/ops/local_test.py`); the hardening report
stands as its date's record with the 2
current-behaviour notes above. **P4-S6 confirmed**
— the Fremont research paths are that project's
own, as Argon also read them. **P4-S7 confirmed
with 1 addition** — `questions.md`'s dated entries
stand unrewritten, and the packet adds 1 entry of
its own: Q140, the remediation monitor's strain
text, which describes a `fallback` record as a job
running uncaged though the runner now writes that
record only beside a refusal; the design record
carries the settlement note, and the code text
waits on a second seat's re-test under rule 8.
`bravo.md` stands as written. **P4-S8 confirmed**
— the agent-state file's shipped forms, the
shelter and warning pages (the 2,000-name cap
stands in `runner/oracle/personal_docs.py`), the
attack-v20 delta's rule set against
`runner/oracle/detection.py`, the Oracle's
instructions, the briefing design's status line,
and the privacy models survey all check out;
`oracle-briefing-design.md`'s inventory section
stands as the design-time record its status line
supersedes. Files checked with no findings: the
attack-v20 delta, the asymmetric-signing design,
the approval-gate design (Argon's 1 raise
decided above), the oracle briefing design, the
Oracle's instructions, the personal-documents
shelter and warning, the privacy models and
Fremont research, the hardening templates readme,
and the agent-state files record. Guard evidence
on the landing tree: the defaults registry is
green, its pins following the senses and
remediation lines this packet moved; the
reader-quiet and figure sets pass; the
doc-divergences and feature-tiers sets read 45
failed on the landing tree against 66 failed and
896 passed on the pristine tree in the same pass
(the batch's 1 further failure was the registry
drift the pins commit settles) — the packet's
fixes cured 21 of the pristine failures, all in
the grep max-matches family, and added none; the version-rot
and stamp-history failures reproduce identically on
the pristine base in this cell and are recorded
there as pre-existing, not as this packet's. One
cross-packet flag, filed here for the lane that
owns it: `default-posture.md`'s S5 finding, measured
2026-11-09, records the job-time confinement
fallback as running the job weaker, which the
Q135 settlement has since retired in the code and
in SECURITY.md; the page is Packet 1's, and its
measurement record is for that lane to refresh.

## The documentation overview, remedial Argon sweep: suppositions recorded before the sittings (2026-11-10)

The overview's directed method was an outside read: every
sentence of the documents checked through Argon
(gemini-4-argon) against the tree. Packet 1 took that
read. Packets 2 and 3 did not — their lanes judged the
outside read unnecessary, checked by hand, and the hand
check passed at least one defect a reader has since hit
live (a broken link in the FAQ). The conductor has
directed the remedy plainly: run the outside read now,
over the whole document set, the way it was directed the
first time.

The set, computed fresh from `git ls-files` on the main
this section lands on: every tracked `.md` and `.txt`
file, excluding only `docs/archive/` — **313 files**.
(The airgap fixture's own archive-named folder is not
the archive folder and stays in the sweep.) The owner's
`docs/checklist.txt` is in the set as reading material
only; it is never modified by this lane, and findings
about it are reported to the conductor, never fixed.

The suppositions, stated before the first sitting runs,
so the record shows what was expected against what the
outside read finds:

- **R-S1.** The Packet 1 files (already Argon-read once)
  come back nearly clean: at most a handful of minor
  findings, none of them a confinement misdescription.
- **R-S2.** Packets 2 and 3, hand-checked only, carry
  more: a small number of real errors each — stale
  present-tense claims, counts drifted since the hand
  pass, backend descriptions written before the Windows
  and FreeBSD backends finished. More than zero, fewer
  than a landslide: single digits per packet.
- **R-S3.** The bulk of the sweep's findings land in the
  long tail the packets have not reached yet or reached
  lightly: reports, proofs and project pages whose
  present tense describes a tree that has since moved.
  Most of those will be dated records standing as
  records, not errors to rewrite; the confirmed-error
  share of all findings is expected under half.
- **R-S4.** Argon will flag IETF-adjacent pages as stale
  where the v1/v2 mirror lock holds their text still.
  Per the conductor's direction those flags are
  dismissed on sight — the lock, not neglect. Technical
  or grammar findings in the v1/v2/v3 draft sources
  themselves are a different class: genuine candidates,
  recorded here for the conductor's email route (the
  v1/v2 texts themselves are never edited in this
  repository; v3 findings may be acted on after
  verification).
- **R-S5.** Argon will also produce false positives a
  tree-side check dismisses: figures a release cut
  refreshes, dates that are records rather than claims,
  and sentences correct against the code Argon was not
  shown. Every finding is verified against the tree
  before anything is fixed; Argon points, Muse decides.
- **R-S6.** No finding will require a new file in the
  repository root, and no confirmed fix will touch the
  v1/v2 draft texts or `docs/checklist.txt`.

Argon's findings, when the sittings complete, stand
below under Argon's stamp
(00000000-argon-26a0-ff29-7825440c1fb9); Muse's
decisions on each stand beside them under Muse's own
stamp (00000000-muse-7e57-d0c5-58316a922026).
## The road to the next 3.16 release: three stale figures, named and re-measured (2026-11-10)

The head the .2 cut was first attempted on failed
its build in 3 places, each a figure or a harness
that had not followed a landing it described:

- The posture stamp producer's PROTOCOL.md passage
  (13 lines) moved 9 pinned statements below it; the
  defaults registry's doc-line pins now carry the
  lines as they stand, each verified against the
  statement it names.
- The posture startup-gate test asserted an
  announcement that rides runner.log(), whose INFO
  lines share 1 per-minute budget across the whole
  test process; a full-suite run could spend the
  budget before the gate test ran. The harness now
  starts from a fresh budget window and restores it
  after — the shape the build-stamp tests already
  used — and the suppression was reproduced and
  cured locally before the landing.
- The job_user postspawn fix grew
  runner/ops/remediation_ops.py by 36 lines and the
  Windows duration-table mode grew the excluded
  suite runner by 63, and neither landing re-measured
  the core. The recorded breakdown stood at 18,870
  for runner/ops against a measured 18,906. The set
  stands re-measured over the current tree: the
  as-assembled set is 60,329 lines, 54,400 of them
  non-blank, a 763,753-byte zip; the canonical list
  is 59,482 lines over 135 files.

The same build's Windows leg killed shard 2 at the
wall: it carried the proof-content files, whose
prices from the first re-pack still understated
their slowest-pool cost. The table is refreshed
again from the build logs, the estimator's
largest-across-logs rule pricing every file at the
slowest pool observed: 442 files, 7,983.1 seconds
in total, packing to 12 shards at 672 seconds
against the 720-second budget. The wall is not
raised; the prices were wrong, and now they are
measured.

### The sittings, and what Argon found (2026-11-10)

The sweep ran as 10 sittings of gemini-4-argon over the
313 files (1,531,429 prompt tokens counted by the API),
each file fed whole with its path and the confinement
facts from the security policy as ground truth. Every
file drew at least one verdict line: 271 clean, 60
finding lines (several files drew more than one).
`docs/checklist.txt` came back clean; it was read and
never modified, and there are no findings about it to
report.

The suppositions against the result: R-S1 held (the
Packet 1 files drew 3 findings, all minor, none a
confinement misdescription — the support matrix's
FreeBSD cell among them). R-S2 held (Packets 2 and 3
drew real errors in single digits per packet: stale
audit figures, a stale revocation claim, a stale panic
word account). R-S3 held in shape and beat its estimate
the other way: the long tail drew the most findings,
and the confirmed-error share is over half, because
several packet lanes were still mid-flight when the
sittings ran and their files had not yet been corrected.
R-S4 held (the mirror-lock flags arrived as expected
and are dismissed below). R-S5 held (2 findings were
false as stated, rejected below with their reasons).
R-S6 held (no root file, no v1/v2 text, no checklist
edit).

<!-- Agent-Stamp: 00000000-argon-26a0-ff29-7825440c1fb9 -->
Argon flagged, in its own words' substance: PROTOCOL's
2026-11-03 audit parenthetical (3.65% / 0.43%) against
the 2026-11-09 audit (3.17% / 0.38%); the security
policy's panic-word passage naming only `job_user` on
POSIX; the FAQ's "one shared secret rather than
per-sender keys" revocation sentence; the support
matrix's FreeBSD cell ("the only writable mount"); the
README's Oracle diagram ("cage opt-in"); the index
page's two untouched-since dates overtaken by Packet
3's landing that same evening, and its reports-drawer
arithmetic (71 listed + 36 = 107 against a 108 heading);
the transports page's "the shared secret itself is the
session's pre-shared key" and its one-exception
secret-handover claim; the Oracle configuration page's
`resources` startup account, its `transport_dtls` PSK
and alone-among-the-pipes claims, and its
`dtls_greeting` tier descriptions; the senses page's
"by default the job's network edge is unrestricted";
the privacy design's "six guard features" and its
queued-guard passages; the hardening report's
enforce-fallback chain; the default-posture page's
first-start preamble against its own corrected platform
rows; the overview page's latest-release line
(3.15.18.12, verified 2026-11-08); the branch
contradiction between the telephone-pole page ("one
branch") and the Bravo page (a maintained `bravo`
branch); a label-only sentence in the cs_office page
against that project's own postures page; the campaign
playbook's retired paths and its workdir-persistence
contract; the standing orders' cages queue item; the
layout, testing, readiness, constraints, properties,
goals and thinking pages' retired paths, stale counts
and stale mode counts (several of them the very defects
Packet 6's suppositions above already name); the
key-policy builder described in two places as naming
an unrecognised field in a warning; two links
(known-failures, transports-status); a captured posture
report's WARN line; the IETF status pages' expiry and
living-draft statements and a delta note's disclosure
contradiction; and, in the draft sources, the v1 -04
frontmatter's `, Ed.` names rendering as surnames in
the rendered text, the v1 -04 Section 6 `job-id`
alphabet admitting NUL against Section 16.1's
NUL-joined AAD, the v2 -04 abstract's context-segment
carriage phrasing, two v2 -00 statements its own -04
already corrected, and in v3 a literal BCP 14 paragraph
where the tagged boilerplate belongs (63
MISSING_BCP14_TAGS in its idnits) and a `1*gap` where
`gap` already means one-or-more.

Muse's decisions on those findings, under Muse's own
stamp (00000000-muse-7e57-d0c5-58316a922026):

- **Confirmed and fixed in this lane's landing** (the
  commit at 8:34 PM PST): PROTOCOL's audit parenthetical
  now carries the 2026-11-09 figures; the panic-word
  passage names confinement at `enforce` on Linux and
  FreeBSD beside `job_user`; the FAQ's revocation
  passage states per-sender keys and per-key revocation
  as they stand, with the primary secret's rotation as
  the manual part; the support matrix's FreeBSD cell
  names the fresh tmpfs at /tmp; the index page's two
  dates read 2026-11-10 with their characterisations
  corrected, and its reports arithmetic reads 37; the
  v3 source takes the tagged BCP 14 boilerplate (which
  renders the identical text) and `gap` for `1*gap`,
  mirrored in its rendered text. The FAQ edit moved one
  defaults-registry pin (the poll interval's doc line
  follows the doc, the standing pin-follows-doc move).
  Guard evidence: the reader-quiet and support-matrix
  tests pass; the security-claims, figure-slot and
  drift-guard batch passes after the pin follow
  (33 tests, 953 subtests).
- **Confirmed, and already landed by the packet lanes
  while this sweep ran** (verified against main at
  8:34 PM, not re-fixed here): the transports page's
  derived-PSK account and two-handover shape, and the
  Oracle configuration page's three items (Packet 5);
  the layout, testing, readiness, constraints,
  properties, goals, thinking and model pages, retired
  paths and mode counts among them, and the
  key-policy builder's refusal stated as a refusal
  (Packets 5 and 6, whose conclusions stand above, with
  their own Argon read beside them); the campaign
  playbook's retired paths and the standing orders'
  cages item, which now carries its own update
  (Packet 6A); the two reported links (Packet 8's
  banner fixes, landed minutes before the sittings
  ran).
- **Confirmed, owned by lanes still in flight, left to
  them**: the senses page's network-default sentence
  (Packet 4's own supposition P4-S1 names the same
  line), the privacy design's feature count and queued
  passages and the hardening report's fallback chain
  (Packet 4's set), the branch contradiction — the
  remote carries main only, so the telephone-pole
  page states the present fact and the Bravo page is
  the stale side (Packet 4's set), and the overview
  page's release line (Packet 9's supposition P9-S1
  names it).
- **Confirmed and referred, not rewritten by this
  lane**: the campaign playbook's workdir-persistence
  row. The runner now reaps a job's workspace when the
  job finishes, so a loop cycle asserting persistence
  would fail today; the row is the playbook's asserted
  contract, and changing what a campaign asserts is
  the campaign owner's call, taken up from this note.
- **Dismissed under the conductor's direction**: every
  flag on IETF material outside the draft sources —
  the status pages' expiry and living-draft statements
  and the delta note — is the mirror lock and the
  drafts' own record, not a finding. The two v2 -00
  items are dismissed as superseded: its own -04
  already carries the corrections Argon names.
- **Recorded for the conductor's email route, texts
  untouched** (the v1/v2 mirror rule): the v1 -04
  frontmatter `, Ed.` rendering (the rendered text does
  show the names as Argon says), the v1 -04 Section 6
  `job-id` / NUL-AAD question — a genuine technical
  candidate: `word-char` admits %x00, and a `job_id`
  carrying it would collide with the AAD's NUL join —
  and the v2 -04 abstract's context-segment phrasing.
- **Declined, with reasons**: the README diagram —
  the cage cell already reads "caged by default"; the
  opt-in phrase belongs to the judge cell, a different
  feature, and Argon's quotation joined the two. The
  sending page's upgrade table omits FreeBSD because
  no FreeBSD applier ships in the remote-upgrade kit;
  the table's platform set is the kit's, and the
  omission is accurate. The default-posture page
  stands as the dated 2026-11-09 record Packet 1
  already declined to rewrite; its platform rows were
  corrected on 2026-11-10 and the tension Argon flags
  is the record's own before-and-after. The captured
  posture report is a verbatim capture on the audit
  ignore list and is not edited. The cs_office flag is
  declined: the postures page states the project's
  disclosure doctrine by design, the label-only
  sentence governs public writing about the private
  shelf, and the two pages are not in contradiction
  once each is read in its own scope — no text changed,
  and nothing from the private shelf is repeated here.

## The determination decision point, built (2026-11-10)

Q139's build, taken up by the building seat. The design
preparation resolved the five filed points on paper; this
note records the supposition before the code, the five
open points the preparation deliberately left to this
seat and how each is settled here, and — at the end of
the landing — the conclusions against the evidence.

Supposition, written before the build: if the decision
point is implemented as a pure routing query computed
once per job from config + job + the already-formed
opinion plan, with the remote question sent first, the
local consult run inside the existing deadline window,
and the combined picture recorded only on the result
(a `consult` segment) and in the audit — never in the
wire determination, never in the execution decision —
then (1) every existing deployment behaves
byte-identically (the legacy `remote` mode is the
default when `v2_consult` is absent); (2) no failure arm
can stall the worker past the 30-second cap or turn a
determination into a refusal; and (3) the whole feature
is pin-testable per field, because every decision it
makes is a pure function of inputs the tests can
construct. The conclusions below judge this supposition
against the red/green evidence of the landing.

The five open points, settled by this seat:

1. **The clean-pass reading.** Q139's first point says
   "a clean pass sends nothing, and stays nothing". This
   seat reads that suppression as a property of the new
   `both` mode only. In legacy `remote` mode
   `should_ask` fires on clean-pass exec jobs exactly as
   it does today, and changing that would break the
   byte-identical promise every existing deployment
   runs on; the filed sentence names the routing
   question the decision point answers, and the
   decision point exists only where a consult mode is
   chosen. In `both` mode a clean pass with no model
   tier engaged consults nothing and records nothing.
2. **An allowlist with no posture block.** Refusal, not
   warn-once: `v2_question_postures` present while the
   config declares no `disclosure_posture` block is a
   startup config error naming the pair, in the same
   refuse class as the posture producer's own startup
   errors. A warn-and-continue here would leave a
   disclosure gate silently inert for the whole run,
   which is the failure shape this suite has retired
   everywhere else. The tunable surface is the key
   itself: remove the allowlist, or declare the block.
3. **The record's exact shape.** The `consult` segment
   text is pinned, in this field order:
   `v2_consult mode=<mode> sources=<csv|none>
   local=<stance> remote=<stance> outcome=<outcome>
   split=<true|false> deadline=<seconds>`, followed,
   only when they apply, by `gate=<code>`,
   `local_model=<status>` and `late=true`. Sources are
   `det`, `model`, `remote`. Local stances are `fail`,
   `unknown`, `proceed`, `none`. Remote stances are
   `proceed`, `stated`, `no_answer`, `not_asked`,
   `send_failed`. Outcomes are `both`, `local_only`,
   `remote_only`, `none`. The audit row's decision is
   the outcome; its reason is the routing reason —
   `v2_off`, `legacy_remote`, `legacy_no_ask`,
   `clean_pass_settled`, `both_deterministic`,
   `both_llm_model`, `both_det_remote`, `local_only_mode`,
   `kind_not_exec`, `no_plan`, `posture_not_listed`,
   `posture_unstamped`, `v2_question_off` — replaced,
   when a failure arm fires, by the arm's own code:
   `send_failed`, `no_answer`, or `deadline_zero_remote`
   when the deadline was 0 and nothing was pre-filed.
   The segment text is also the audit row's detail:
   names and codes only, never answer text, never
   script text.
4. **The stamp does not ride the consult segment.** The
   posture stamp already rides the result where the
   posture producer put it; the consult record names
   posture only as a gate outcome code, never the stamp
   and never the posture id.
5. **One question, both audiences.** The local model
   tier is asked through the existing opinion model
   note — the same question text the opinion tier
   already uses — so the two sources answer one
   question and the picture is combined rather than two
   unrelated opinions. The note keeps its existing home
   in the opinion member, prefixed `Model-formed note:`;
   the consult record references the tier's engagement
   (`local_model=ok|unavailable|error`), never its text.
   The model tier's budget is the deadline: it is not
   engaged at all when the deadline is 0, and it runs
   inside the wait window the deadline already bounds,
   after the question has gone out.

Two further defaults, under the conductor's
defaults-plus-options rule. The posture gate's modes
are the house security modes for the new `v2_question`
feature (off disables the remote consult, audit sends
and records what enforce would have decided, enforce
applies the gate; unset reads as enforce). And where
the gate blocks under enforce, the job is never
refused: the consult degrades to local-only and the
record says why — a determination is not a refusal.

Conclusions (2026-11-10, measured against the landing):
the supposition held on all 3 points. (1) Legacy
byte-identity: the guard family's legacy fixtures — a
pre-filed answer's segments, a clean pass's question,
the absence of any consult segment or audit row under
the default mode — pass unchanged against the new seam,
and the execution-invariance pair runs the same job
under both modes to the same exit code and the same
output. (2) No arm stalls or refuses: the failure-arm
family (no answer at deadline 0 and inside a wait, a
hand-off that raises, a model tier that raises, a gate
that blocks) degrades each time to the local picture
with the arm's code in the record, and the seam is
exercised inside a full mail run without changing the
run's outcome. (3) Per-field pin-testability: the guard
family is `runner/tests/test_v2_consult.py` — 99 tests,
93 of them red on the pristine tree before the build,
green with it — enumerating each new field
(`v2_consult`, `v2_question_postures`, the `v2_question`
mode), every routing row, the record's field order, the
audit vocabulary, and the startup refusals. The fuzz
families run in the same file, as executed runs, not
intentions: a seeded 400-case routing sweep asserting
`consult_plan` never raises and stays in vocabulary; a
seeded 300-case config fuzz asserting startup
validation refuses or accepts and never crashes; a
bookended answer-text corpus (every ASCII symbol at
the front and the back, plus NUL, tab, CR and LF, with
repetition runs at the front, the back and the middle)
asserting the answer is preserved verbatim in its
segment and never reaches the consult record or the
audit detail; and a pump-timing case asserting an
answer filed inside the wait is timely, never late.
Neighbour batteries on the landing tree read green:
324 passed across the protocol, replay, posture,
briefing, security-config, posture, parity, reader-quiet,
support-matrix and build-config families, and the
proof-constraints family with the feature pin moved to
the nine features the new mode makes. The
doc-divergences family reads 906 passed and 13 failed
on the landing tree against 904 passed and 27 failed
on the base tree in the same cell — every failure in
the known grep max-matches family, whose count moves
with the cell's load (a first landing-tree run under
full parallel load read 56 in the same family); the
landing adds none. The regression guard reads RED on
one pre-existing failure — `test_layout`'s stale-path
check over packet-era text in AGENTS.md and this file —
proven identical on the base tree without this
landing; the consult module itself passes standalone
on every run. The figure refresh is left to the
release cut's figure pass, as the documentation
packets settled for their own landings; the core chain
in AGENTS.md records this landing's growth. What
remains is the second seat's re-test under rule 8 —
the hosted legs' verdict and the rig batteries on the
landed head — before Q139 is called done.

Second-seat re-test (rule 8, 2026-11-10, the same
evening): this seat re-derived the landing from the
tree rather than taking the building seat's word.
(1) The guard family `runner/tests/test_v2_consult.py`
runs green standalone on the landed head: 99 tests,
OK; the neighbour batteries this seat chose
(`test_protocol_v2`, `test_protocol_v2_messages`,
`test_v2_replay`, `test_posture_stamp`,
`test_briefing_contradiction`, `test_security_config`)
run green alongside: 184 tests, OK. (2) The failure
arms were read arm by arm against the design
preparation's table and the seam family: no-answer
inside a wait and at deadline 0, a hand-off that
raises, a model tier that raises or is skipped at
deadline 0, a late answer, no plan, a gate that
blocks at enforce and one that records at audit —
each degrades to the local picture with the arm's
code in the record; none raises out of the seam and
none refuses a job (the audit writer is itself
best-effort and never raises into the caller). Two
record-level divergences from the preparation's
table are noted, neither a defect against the
settled record vocabulary above: the plan-cannot-form
arm records under `no_plan`, not the preparation's
`oracle_unavailable`; and the defensive
posture-state arm's code stays in the plan's gate
reason and never reaches the record, since the gate
does not block there. (3) Legacy byte-identity: the
build's diff against its supposition parent adds a
dispatch head and a docstring to
`_v2_before_execute` and deletes no legacy line
(the whole landing is insertions in the runner
proper and in `runner/wire/protocol_v2.py`); the
legacy fixtures pass unchanged, and the
execution-invariance pair runs the same job through
a full mail run under both modes to the same exit
code and the same output, the consult segment
present only in the consult mode's result.
(4) The config surface pins as settled: `FEATURES`
in `runner/guard/security.py` counts 9 with
`v2_question` last; the per-field validation family
and the startup family pass in the guard file,
including exit 2 naming `v2_question_postures` for
an allowlist declared with no posture block, and
exit 2 naming `v2_question` for a bad mode value.
(5) Hosted verdict at re-test time: on the
conclusions head the platform-matrix,
queues-worker, minimal-userland and upgrade-proof
runs are success, the main build is still in
progress with every completed leg success (test,
test-macos and build-windows still running), and
python-range stands cancelled by supersession —
the next head, a tests-only pin commit at
8:59 PM, carries the same code. No red leg touches
a Q139 file; the build's final verdict is the
trains' to record. (6) Rig batteries: the watcher
tested the build head itself — Windows PASS and
Linux PASS, all steps, at full attestation — so
the landed head is field-proven on both platforms.
One genuine defect, found by probe and confirmed
twice: with version 2 disabled (or an answer-only
configuration) and a consult mode chosen, the seam
still records a consult segment and an audit row
for a consult that never happened. It has no
execution effect and is filed as Q141 for a fix
lane; this seat lands no fix for it. Subject to
that filing and the hosted build's completion,
Q139's re-test passes: the supposition the building
seat recorded is judged held by a second seat.

Correction (the second seat, later the same
evening): the hosted build's macOS leg completed
after the record above was written, and it is red,
and one of its errors belongs to this landing.
`test_runner_last_edges`' `test_v2_before_execute_legs`
— a pre-existing fail-soft pin whose stand-in for
the protocol module carries only the legacy surface
— passes on the tree immediately before the Q139
build and errors on the landing, reproduced
locally by this seat both ways: the dispatch head
calls `_protocol_v2.consult_mode_of(cfg)` with no
guard for a module object that lacks the new
function, and the `AttributeError` leaves the seam
the leg exists to keep soft. No deployed runner
raises (the real module carries the function); the
broken thing is the seam's pinned contract and a
standing test. Filed as Q142 for a fix lane, not
fixed here. The macOS leg's other failures are
the recorded pre-existing families, none in a Q139
file — the defaults registry's doc-line pins for
pages the parallel packets moved, the version-rot
guard on this file (this seat verified it fails
identically on the pristine head), the layout
stale-path check the building seat already named,
the core-figures breakdown the next head's
re-measure already chases, and the regression
guard's end-to-end leg carrying the same drift —
and the macOS shard carrying `test_v2_consult`
itself reads OK. The verdict above is therefore
amended: points (1) through (4) and (6) stand as
recorded; point (5) completes as test-macos red,
one error this landing's own, and Q139 is not
called fully done until Q142's fix is re-tested.

Closing (the filing seat, later still): the
Q141/Q142 fix has been re-tested by the seat that
filed both questions, on the current head, and it
passes — the seam records nothing when version 2
is off or the process is answer-only, and the
dispatch head no longer raises for a protocol
module without the consult surface; the batteries
read 258 tests green together, and the seat's own
probe of the filed shapes agrees. Q139 is
therefore fully done, as this section's correction
required. The hosted build on the newest head was
still pending at the closing check; the rig
batteries stand PASS on both platforms on the head
immediately before the fix, the fix head's battery
being the watcher's next cycle.

Conclusions (2026-11-10, the same evening): **P7-S1
refuted as stated** -- the living drafts are not
byte-identical to any submitted revision: both are
plain-markdown working texts of the -00 generation
(the version 1 living file's own header reads
Expires: 3 May 2027, the -00 expiry), and `cmp`
against all 4 submitted revisions of each draft
differs throughout, format first. On a normalized
word stream the living version 1 text stands closer
to the posted -00 render than to -03, and its
catalogued markers verify in place: the subject
grammar in its pre--02 single-SP form, the 6 em
dashes, `PROTOCOL.md` named once in the
`sensor_alert` bullet. The mirror rule's operative
content holds: the living texts were not edited by
the -04 cut (their last change is the 2026-11-04
folder reorganization), the -04 drafts were cut
from the posted -03 texts, and the differences are
the checklist's 15 catalogued mirror differences.
The one sentence that misstated this -- the cover
sheet's "stand equal to the posted texts" -- is
corrected there. **P7-S2 confirmed in part** -- the
current revision (-03) and the submission numbers
(171771, 171786) agree in the cover sheet and both
per-draft status files, but the expiry did not:
both frozen -03 renders state "Expires: 6 May 2027"
in their page-1 headers, so the cover sheet's
1 May 2027 for version 1 was a plain factual error
and now reads 6 May 2027. The version 1 per-draft
status file carries the same 1 May date; that file
belongs to Packet 9 and is flagged here for it.
**P7-S3 confirmed** -- the Next, Known nits and
subject-gap sections are the pre--02 plan text and
stand as that dated record; the cover sheet now
carries a dated outcome note at the end of Known
nits (the -02 revisions applied the nits: both -02
sources set the author organization to
"Independent" and hold no em dashes), and the Next
section's due date is corrected from 3 May 2027 --
the -00 expiry -- to 6 May 2027. **P7-S4
confirmed** -- the deferred-items note still
presents item S4 as the one proposed change, while
the version 1 -04 source reads `job-id = 1*128
word-char` with no `job-id-char` rule, exactly as
the checklist-applied note records for the
2026-11-07 approval; the cover sheet now records
that application beside the -04 cut. The delta note
itself is the pre-approval proposal record and is
not rewritten (the Packet 1 rule for dated records).
**P7-S5 confirmed exactly** -- living 6 and 4 em
dashes; -04 drafts and posted -02/-03 sources 0
each. **P7-S6 confirmed in part** -- the garbled
duplication stood in the version 3 paragraph and is
tidied; the renders do match the corrected source,
because the source, its renders and its idnits
record were all regenerated in the same 2026-11-06
commit, and the current idnits record (0 errors;
3 warnings on the text, 2 warnings and 64 comments
on the XML) matches the applied note's account.
**P7-S7 confirmed** -- the idnits records beside
the -04 sources match the applied note exactly
(version 1: 0 errors, 1 warning, 2 comments on text
and XML; version 2: 0 errors, 2 warnings, 1 comment
on the text, 0 errors, 1 warning, 2 comments on the
XML). **P7-S8 confirmed** -- the trim list's quoted
phrases stand in the submitted -02 sources (the
introduction sentence, the NATS subjects line, the
UDP 20220 lines, the `family` reference-default
line; version 2's device-tree example and its
`--protocol-v2` / `protocol_v2` lines), and neither
-02 source names `PROTOCOL.md`, a repository path
or a GitHub URL. **P7-S9 confirmed** -- the
2026-11-06 cut commit stands in the history and did
not touch the living files; the -04 sources' own
headers state the cut from the posted -03 texts and
their unsubmitted state. **P7-S10 confirmed** with
the exceptions above -- the -01 removal of
`PROTOCOL.md` verifies (1 mention in each -00
source, 0 in each -01); version 1 -02 states the
gap ABNF and keeps `word-char` in the prose form,
-03 closes it as ranges; the version 2 -02 to -03
diff is the docname and date plus exactly the 4
companion-citation unpinnings; `0xFFA0` stands
named in version 1 -03; `PROTOCOL.md` links the
version 3 source as the cover sheet says; and the
-01/-02 submission numbers (171592/171593,
171736/171737) stand on the cover sheet's record
alone -- no second in-tree record carries them and
none contradicts them.

An outside read of this packet was run through
Argon (gemini-4-argon) in 2 sittings: the cover
sheet and the notes in full against this lane's
measured facts, and the version 1 -04, version 2
-04 and version 3 sources in full for technical and
grammar findings. Its findings stand under its own
stamp:

<!-- Agent-Stamp: 00000000-argon-26a0-ff29-7825440c1fb9 -->
Sitting 1 (the records): Argon flagged the cover
sheet's version 1 -03 expiry against the frozen
renders; the "stand equal to the posted texts"
sentence; "Sources and renders live beside this
file"; the folder bullets' silence about the -04
working drafts in `source/` and the checklist
record in `notes/`; the Next section's 3 May 2027
due date; the -04 paragraph's omission of the
2026-11-07 `job-id` application; the Known nits
list and the subject-gap section standing as
pre--02 text; the delta note's S4 framing; a
claimed contradiction over whether the version 3
TLS citation "was already RFC 9846"; and the dated
narration inside the -02 bullet ("The datatracker
now expects -03") and the IETF 127 plan paragraph.
Sitting 2 (the drafts; every quote below verified
against the -04 and version 3 sources by Muse
before recording): VERSION 1 -- (1) Section 14
step 2's seen-set check against Section 15's
replay rules: the check runs on the subject's
`job_id` before verification, and Section 15's
marking steps (3 through 13 and 16) do not name
step 2, so a duplicate dropped there has no stated
marking. (2) Section 16.2 re-enters Section 14 at
step 5, and the AAD's `job_id` (Section 16.1) can
only come from the subject before decryption;
neither passage says so. (3) Section 6's
`word-char` ranges (%x3001-FEFE) span the surrogate
range %xD800-DFFF, and the grammar does not say
which `gap "job" gap job-id` occurrence wins when a
decoration word is "job". (4) Step 4's
well-formedness sentence on unpaired surrogates
overlaps step 7's lone-surrogate LOCAL check (the
G5 pair). (5) Section 7's control-character
fallback strips LF as well as the transport's
insertions; which signed forms survive it is
unstated (the G1 passage). (6) Step 9's
parenthetical sends an illegal `job_id` to step
13's shape failure, but step 1's grammar match and
step 9's own equality rule leave that path hard to
reach. (7) Section 19.2 lets an implementation
ignore a `KeyUpdate` with `update_requested` set,
where RFC 9147 and RFC 9846 require an answer.
(8) Section 11's table makes `kind` `exec` or
`ping` while Section 8 exempts `sensor_alert` on a
base receiver and step 13 answers any other kind
with -2. (9) Section 11.3 says a non-positive
`timeout_sec` is invalid and the reference clamps
"a negative value" to 1; 0 is not named. (10)
Section 19.3's 4-octet length prefix carries no
stated cap where Section 5 caps the RFC822 message
at 4194304 octets. (11) Grammar: Section 17.7, "Two
secrets", is a single noun-phrase fragment -- "The
transport credentials and the HMAC secret, which
authorizes jobs." VERSION 2 -- (12) Sections 6, 7,
8 and 12 name `msg_id` "the encryption's object
identifier", a term version 1 Section 16.1 does not
use (its AAD is defined by components; version 1's
only "object identifier" is the unrelated IANA
sentence), so the substitution rule for the AAD's
first field rests on an undefined term. (13)
Sections 6-8 give the subjects as literal strings;
whether decoration words are legal in a version 2
subject is unstated. (14) The `msg_id` shortening
is stated as the reference's derivation while
receivers are left to infer whether `msg_id` is
opaque, and version 2's `[A-Za-z0-9._-]` charset for
`job_id` is narrower than version 1's `word-char`.
(15) Section 9 states the deadline twice over (a
filed-at rule with 1 second of grace, and the
wall-clock-step sentence) in reference-pipeline
terms. (16) Section 6's determination account uses
`plan`, `findings` and `repair`, none defined in
either draft. (17) Grammar and clarity: Section
10's "after the result's own policy has rebuilt
that object, so the rebuild cannot drop it", and
Section 11's "answer_only is the laptop that thinks
for a Pi." VERSION 3 -- (18) Section 4.4 states a
delta against the version 1 profile (the hybrid
share X25519MLKEM768 offered beside X25519) while
the abstract and Section 1 say version 3 changes
"exactly one thing -- the carriage" and carries the
profile "unchanged". (19) Section 5.1's flight
subject is anchored ("only when the remainder is
exactly a flight subject") under a grammar version 1
defines as a search, and the permitted `Re:`/`Fwd:`
prefix has no ABNF of its own. (20) Section 8.1's
dispatch enumerates flight mail and version 1 job
subjects and does not mention version 2 subjects;
Section 10.1 says the session's objects "are
version 1 objects". (21) Section 5.2 defines the
frame part as a leaf, "not the content of a
message/rfc822 part", then says "the wrapped shape
is read where it is met". (22) Section 5.3's chunk
arithmetic (32768 base64 characters, 24576 octets)
implies intermediate chunks carry no `=` padding,
but no MUST states it, and the `HP-DTLS/3` header
line has no ABNF. (23) Section 9.2 binds the mail
session-id to "the session's connection ID" from
establishment; which epoch the binding first covers
is unstated. (24) Section 10.3 keys a hold by
connection ID, job ident and PSK identity, then
drops a job whose ident is held for another
identity -- the cross-submitter consequence of a
chosen ident. (25) Terminology: "priced replay
windows" (Sections 7.2 and 13) appears nowhere in
version 1. (26) Grammar: Section 13's "an
application-data replay is dropped before it" has
no clear referent for "it".

Muse's decisions on those findings, under Muse's
own stamp (00000000-muse-7e57-d0c5-58316a922026):
accepted and landed in the cover sheet -- the
expiry correction, the "stand equal" correction,
the renders' home, the folder bullets, the due
date, the -04 paragraph's 2026-11-07 application
record, the Known nits outcome note, and the
version 3 garble tidy. Declined, with the reasons
recorded -- the TLS-citation contradiction: both
in-tree records (the cover sheet and the applied
note) agree the citation was already RFC 9846, and
the flag rested on the fact sheet's phrasing, not
on the tree. The "expects -03" sentence and the
IETF 127 paragraph: dated narration inside their
own dated sections, settled by the Posted record
that follows them. The delta note's S4 framing and
its mirror-rule sentence: the note is the
pre-approval proposal record and the sentence
states the governing rule, not a measurement; the
current state stands in the applied note, the
cover sheet and these conclusions. The draft
findings (sitting 2) are recorded, not landed: no
draft text is edited in this repository, and each
finding travels to the conductor by the drafts'
own route for the -05 pass. Two of Argon's sitting
2 claims did not survive verification and are
declined outright: the RFC 9846 / RFC 10024
"nonexistent number" claims -- the move from
RFC 8446 to RFC 9846 is CHECKLIST-04 item 8, a
settled decision the whole family carries with its
2026 dates -- and the missing-BCP14-references
claim for version 2: the -04 render's reference
list carries RFC 2119 and RFC 8174, as the
kramdown-rfc boilerplate inserts them, and idnits
reports 0 errors. Also declined: the numeral-style
point (digits are this project's house style across
its documents; RFC Editor style is a submission
pass concern) and the version 3 citation of
version 1 -03 (the -04 drafts are unsubmitted
working drafts; citing the posted revision is the
defensible form until a -04 is posted). Noted as
already-decided where the checklist had taken the
point deliberately: the Section 10 segment
validation (G8's draft-side option), the
`timeout_sec` clamp itself (G4), the
control-character fallback (G1) and the
`sensor_alert` scoping (items 4 and 19) -- Argon's
readings of their edges stand above as the -05
items they are.

Guard evidence on the landing tree: the IETF draft
conformance, reader-quiet, version-rot and
design-docs sets read 16 passed; the divergences
and figure sets read 909 passed and 47 failed, all
47 inside the one pre-existing grep max-matches
family (4 tests and their subtests), which reads
27 failed and 4 passed on the pristine base in the
same pass against 26 failed and 4 passed on this
packet's tree -- the packet's fixes added none, and
no failure names this packet's files.

## Sources

The gates are compositions of published practice, not inventions:
git worktrees as the isolation cell for parallel agents
(Anthropic's Claude Code worktree documentation; the Augment and
Watchfire guides); trunk-based development's mechanics — short
branches, small daily integration, release cut from trunk by tag
(trunkbaseddevelopment.com, as distilled in the GitLab exhibit;
DORA's continuous-delivery capability); merge queues testing the
combined tree and bisecting failed batches (GitHub's merge-queue
documentation; bors); dark launching as the decoupling of landing
from releasing (LaunchDarkly); stacked diffs for dependency
chains (Graphite); the repository as the system of record, with a
short instruction file as a map over a structured documentation
tree (OpenAI's harness-engineering account); the in-repository
progress file and the read-at-start, verify-before-done session
ritual (Anthropic's long-running-agents harness account); hash
IDs and claimable in-repository task boards (Beads); and one
personal-repository practitioner's do-it-yourself merge queue,
the closest published analogue to this desk's exact shape
(alatas.dev). Where the desk departs from all of them — the red
main — the departure is stated above, in the open.

## The documentation overview, Packet 8: suppositions recorded before the check (2026-11-10)

Packet 8 of the overview takes the historical shelf and
the filed copies: the 11 files under `docs/archive/`, the
59 under `docs/steady/reports/`, the Falkenstein rig
report and the seats note under
`docs/infrastructure-documents/`, the changelog at
`docs/infrastructure-documents/changelog.md`, and the 8
filed Internet-Draft copies under `docs/ietf/*/submitted/`
— 81 files. The packet's rule is narrower than the
others': historical files are the record and are not
rewritten, filed copies are not edited at all, and the
check is consistency and banners only. Anything in a
current-facing summary that plainly contradicts the
current state (the 3.16 official release line, secure by
default finished) is flagged here; a fix lands only where
a file presents itself as current guidance and is
plainly wrong, or in the banner layer that marks a
record as a record. Suppositions, written before the
check ran:

- **P8-S1.** The changelog's top section will be the
  current release on the 3.16 line, of 2026-11-10, stating the
  official release on the 3.16 line and the security
  posture finished; no section for the next release will stand
  there yet, because that release is not published, and
  the changelog is a release record — so the top will
  read consistent with the current state with no edit.
- **P8-S2.** The reports drawer will stand as dated
  records under the audit ignore list (AGENTS.md rule
  6); its one index-like file, `coverage.md`, will
  reconcile against the drawer: the count it states
  (28 reports) will match the files on disk and every
  coverage report will be listed.
- **P8-S3.** At least 1 archived banner will point a
  current reader at a retired-layout path that no
  longer exists: `transports-status.md`'s banner will
  name a `TRANSPORTS.md` as the current page, and
  `known-failures.md`'s banner will misstate the file's
  own home. The bodies beneath the banners will stand
  as records; the banner layer is where a fix may land.
- **P8-S4.** The Falkenstein rig report's closing list
  of remaining items will carry items since resolved —
  the Windows `job_user` divergence (the gate now
  engages through the confinement backend, per the
  the current release's changelog section) and San Francisco sitting
  idle (the box now runs the fleet's fuzz lane and the
  preview loop's Linux leg). The report is a dated
  running record: flagged here, not edited.
- **P8-S5.** The filed IETF copies will be internally
  consistent — each submitted `.md`'s docname and date
  matching its filename revision and the posting record
  in `docs/ietf/status.md`, each `-03` render carrying
  its posted date — with 1 exception: status.md's
  expiry date for version 1's -03 will disagree with
  the filed -03 text itself. Status.md is Packet 7's
  file: flagged here, not edited in this packet.
- **P8-S6.** The archive drawer will stand as the
  record: compressed-summary banners on the seat
  intuitions, the stamp record consistent with the
  recycled-stamps account in AGENTS.md, and the
  `steady.md` proposal standing as a proposal of its
  day, with no current-facing contradiction.
- **P8-S7.** No Packet 8 file will carry the string
  `FINAL`, and the seats note
  (`si-to-si-over-homing-pigeon.md`) will stand as a
  dated design note that states its own status, needing
  no correction.

Each supposition is settled in the commits that follow
this note; the conclusions stand at the end of this
section when the packet lands.

Conclusions (2026-11-10, the same evening): **P8-S1
confirmed** — the changelog's top section is
the current release on the 3.16 line, of 2026-11-10, stating the official release
on the 3.16 line, the counter restarted at 1, and the
security posture finished for real (confinement and
the separate job user at `enforce` refusing rather
than running weaker, the Windows and FreeBSD backends
named with their field proof). No section for the next release
stands there; that release is not published, and the
changelog is a release record, so the top is
consistent as written. **P8-S2 confirmed in part** —
the reports drawer stands as dated records, and every
coverage report on disk is listed in the index; the
index's own count did not reconcile (see the Argon
findings below). **P8-S3 confirmed** — the
`transports-status.md` banner named a `TRANSPORTS.md`
at a retired-layout path that exists nowhere in the
tree; the banner now names the current transports
page (`docs/infrastructure-documents/extend/transports.md`).
The `known-failures.md` banner said the file is kept
in `docs/archive/` and pointed at a `docs/job-review.md`
that does not exist; the banner now names the file's
real home (`docs/steady/reports/`) and the Oracle
job-review page's real path. Both fixes are banner
layer only; the records beneath stand untouched.
**P8-S4 confirmed, flagged and not edited** — the
Falkenstein report's closing list carries the Windows
`job_user` divergence as open (resolved: the gate
engages through the confinement backend, per the
the current release's changelog section) and San Francisco as
sitting idle (the box now runs the fuzz lane and the
preview loop's Linux leg). The report is a dated
running record and stands as written; this flag is
its correction pointer. **P8-S5 confirmed with the
1 exception standing** — the filed copies check out:
all 8 submitted `.md` files carry the docname and
date of their filename revision, matching status.md's
posting record (-00 and -01 dated 2026-10-30, -02
2026-11-01, -03 2026-11-02 for both drafts), and the
-03 renders carry their 2 November 2026 posting.
The exception: status.md states version 1's -03
"expires 1 May 2027"; the filed -03 text itself reads
"Expires: 6 May 2027", as does version 2's -03, whose
6 May date status.md states correctly. Flagged here
for the Packet 7 lane, whose file status.md is; no
filed copy was edited, and neither was status.md.
A second cross-pointer of the same kind, found the
same way: `docs/steady/oracle/job-review.md` (a
Packet 4 file) sends readers to
`docs/archive/known-failures.md`, a path that does
not exist — the file lives in `docs/steady/reports/`.
Flagged here for the Packet 4 lane. **P8-S6
confirmed** — the archive drawer stands: the seat
intuitions carry their compressed-summary banners,
`researcher_ident.md`'s stamp record agrees with the
recycled-stamps account in AGENTS.md, and
`steady.md` stands as a proposal of its day.
**P8-S7 confirmed** — no Packet 8 file carries the
string `FINAL`, and the seats note states its own
status (a design note of 7-Nov-2026, nothing built)
and needs no correction.

An outside read of this packet's current-facing
summaries was run through Argon (gemini-4-argon, the
billed key) over the changelog's top sections and
the coverage index, consistency findings only; its
findings stand under its own stamp:

<!-- Agent-Stamp: 00000000-argon-26a0-ff29-7825440c1fb9 -->
Argon flagged: (1) the changelog top — no
inconsistency found. (2) `coverage.md`'s count: the
index states 28 markdown reports while its own table
lists 29. (3) `coverage.md`'s ordering: the
local-rig 2026-10-27 gaps row sits at the table's
foot though the index claims "newest first", and its
37,937 statements exceed the v3.15.1 figures above
it.

Muse's decisions on those findings, under Muse's
own stamp (00000000-muse-7e57-d0c5-58316a922026):
accepted and landed — the count: the table lists 29
reports (the paragraph's "is not a report" attaches
to the `coverage-local.json` data file, not to
`coverage-local.md`), and the index now states 29.
Declined, with the reason recorded — the ordering:
the table's versioned series reads newest first
exactly as claimed, and the 2 unversioned local
entries (the local-rig gaps and `coverage-local.md`)
close the table as local-run appendices; the
statement counts differ because the local rig
measured a wider scope, not a later version, so no
inconsistency stands. The changelog verdict agrees
with P8-S1. Guard evidence on the landing tree: the
reader-docs-quiet set reads 2 passed; the doc batch
(doc, drift, reader and changelog selections) reads
914 passed and 8 failed, every failure in the grep
max-matches family of `test_doc_default_divergences.py`,
which fails identically — more heavily — on the
pristine base head in this cell, as Packet 3 also
recorded; none of the packet's 3 edited files is a
defaults-registry line, and the packet added no
failure.

## The live-examples link, re-checked after the conductor's live test (2026-11-10): suppositions recorded before the check

The conductor clicked the live-examples link on GitHub
himself after the 8:21 PM PST landing that repaired the
FAQ's relative link, and met a 404. His click is the
evidence that matters, so the link family is re-checked
end to end — the clickable links, the plain-text paths,
and the pages as GitHub actually serves them. Suppositions,
written before the check ran:

- **LE-S1.** On current main every clickable link that
  names the live-examples page resolves the way GitHub
  resolves it, from the linking file, and the link
  guard (`runner/tests/test_doc_link_resolution.py`)
  reads green: the FAQ, the runbook, the Oracle
  configuration page, the README and SECURITY.md.
- **LE-S2.** What the conductor's click met is the
  pre-fix rendering, not current main: the FAQ as
  served at the current release tag carries the old
  target, which resolves to
  `docs/docs/steady/use/live-examples.md` and 404s,
  and any page rendered before the 8:21 PM landing
  carries the same href. No released tree carries the
  repair yet; it reaches a reader who follows a
  release only when the next cut ships.
- **LE-S3.** The plain-text stale paths found on the
  head this check was tasked from — the design page's
  `docs/use/live-examples.md`, and its siblings in the
  runtime page and the senses page — already stand
  corrected on current main by the Packet 4 and
  Packet 9 sweeps, at their real homes.
- **LE-S4.** The link guard still cannot see the
  plain-text family: a backtick path in a reader's
  page naming the retired layout (`docs/use/`,
  `docs/security/`, `docs/oracle/`, `docs/design/`,
  `docs/extend/`, `docs/proofs/`, `docs/project/`,
  `docs/reports/`, `docs/seats/`) is no link at all,
  so the guard passes over it. Scoped to the reader's
  pages — the scope `test_reader_docs_quiet` already
  draws — such a check reads green on current main
  and red on a stale line; the dated records and the
  seats' and project drawers, which quote the retired
  paths as history, stand outside it.

Conclusions, against the numbers (same landing):

- **LE-S1 confirmed** — every clickable link naming the
  live-examples page resolves from its own file on
  current main (the FAQ's `steady/use/live-examples.md`,
  the runbook's same-folder link, the configuration
  page's `../../steady/use/live-examples.md` under its
  recorded heading, the README's and SECURITY.md's
  root-written paths), the guard reads green, and the
  FAQ as GitHub serves it on main carries the link to
  the live-examples page's blob, which serves.
- **LE-S2 confirmed, and it is the answer to the
  disagreement** — the FAQ as GitHub serves it at the
  current release tag carries the pre-repair target;
  followed, it resolves to
  `docs/docs/steady/use/live-examples.md` and answers
  404, reproduced in this check. The configuration
  page at the same tag carries its own pre-repair
  target (`../use/…`, likewise a 404). The repair
  stands on main only: no released tree carries it,
  and a reader who arrives through the release — or
  whose page was rendered before the repair landed —
  meets the broken link today. It clears when the
  next cut ships the repaired pages; until then the
  release tag's FAQ link is broken, and saying the
  link "is fixed" without naming the tree is how the
  disagreement happened.
- **LE-S3 confirmed** — the design page now names
  `docs/steady/use/live-examples.md`, the runtime page
  `docs/steady/use/platforms.md`, the senses page
  `docs/steady/networking.md`: the Packet 4 and
  Packet 9 sweeps corrected all three before this
  check ran, and no live plain-text reference to the
  pre-move home remains. Left standing, deliberately:
  the filed capture readme in the reports drawer and
  this desk's own packet suppositions, which quote
  the retired paths as the dated records they are.
- **LE-S4 confirmed and built** — the guard now
  carries the plain-text check beside the link check
  (`runner/tests/test_doc_link_resolution.py`, the
  reader-scope retired-path scan and its synthetic
  shapes): 15 tests green on the landing tree, the
  reader-quiet and live-capture neighbours green
  beside it. A stale backtick path in a reader's page
  now fails a test instead of waiting for a reader.

## Q140: the remediation monitor's confinement-strain text — the second seat's suppositions, recorded before the re-test (2026-11-10)

Q140 (filed by the Packet 4 lane) names 2 places where the
remediation monitor still describes a `fallback` confinement
record as a job running uncaged — the
`confinement_events_in_window` docstring in
`runner/oracle/remediation.py` and the `confinement_strain`
divergence's own sentence in the monitor's window check —
though the Q135 settlement writes that record only beside a
refusal. Rule 8: the filing seat does not land a code fix
without a second seat's re-test. This section is that second
seat's suppositions, written from the code read alone,
before any test or probe in this lane is run; the re-test's
conclusions stand at the end of this section when the lane
lands.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

- **Q140-S1.** A running job's own attempt cannot carry the
  `fallback` its monitor would read. Every confinement
  `fallback` writer under `enforce` — the
  `_confinement_argv` denial (Linux, Windows and FreeBSD
  arms) and the `_confinement_spawn` refusal (Windows and
  FreeBSD) — writes the record before any process starts,
  and the job-acceptance boundary converts the denial into
  a `JobRejected` refusal: no process, and no monitor, is
  ever created for that attempt. The re-test will show a
  denied job refused end-to-end with no remediation
  monitor and no result member.
- **Q140-S2.** A different job's `fallback` cannot fire the
  strain either: `confinement_events_in_window` filters the
  audit tail to the running job's exact job id, so a
  same-window refusal of another job stays out, whatever
  its timestamp.
- **Q140-S3.** A `fallback` can still appear in a running
  job's window — from the same job id, inside the window's
  lookback. The monitor reads the window with a 5-second
  lookback before its own start (audit timestamps are
  second-resolution), because the running job's own
  `sandboxed` / `confined` record is itself written just
  before the monitor exists. A `fallback` written for the
  same job id by a just-preceding refused attempt — a
  retry, a redelivery, a resubmission that then runs,
  landing inside that lookback — will be carried into the
  window and will fire the strain. By the same timestamp
  filter, a pre-settlement record is NOT a live source
  beyond that seconds-wide lookback: an older `fallback`
  is excluded by its timestamp, so the design record's
  "from before that settlement" mechanism is not the
  operative one.
- **Q140-S4.** The evidence will therefore support Q140's
  option 2, not option 1: the handling is not dead — it
  fires on a record that names a refusal, not on a job
  shown to be running uncaged. The honest change keeps the
  handling, rewords the 2 named places (and the design
  record's as-built passage, where it still describes the
  old mechanism) to say exactly that, and pins with tests
  which records a running job's window can actually
  carry: a same-id `fallback` inside the lookback fires
  strain under the new wording; a different job's
  `fallback` and an out-of-window `fallback` do not;
  `sandboxed`, `confined` and `would_sandbox` records do
  not; a `denied` record still fires the escape tripwire.
- **Q140-S5.** The strain stays what it has always been in
  the authority layer: a non-tripwire divergence. In
  `deterministic` mode it will act on nothing by itself;
  the reword changes no act, no authority and no mode.

What cannot be unit-tested, stated plainly in advance: the
production race in Q140-S3 — a real redelivery or retry
arriving inside the 5-second lookback on a live box — is
timing, not logic. The deterministic substrate (the window
arithmetic, the job-id filter, the decision arms, the
boundary's refusal before any monitor exists) is what the
re-test pins; the live race itself is named here as the
unproven remainder, not claimed as measured.

## Q140: conclusions of the second seat's re-test (2026-11-10)

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

The re-test ran against the suppositions recorded in this
desk before it (the Q140 section above): the existing
remediation family (101 tests), the confinement and
enforce-posture families, and targeted window probes over
crafted audit tails, afterwards recorded as the committed
family `ConfinementWindowRetestTest` (17 tests, with the
decision-by-job-by-age matrix and the bookended job-id
shapes as subtests) in `runner/tests/test_remediation.py`.

- **Q140-S1 confirmed** — a denied job is refused
  end-to-end and no monitor is created for the attempt:
  the boundary pin drives `execute_job` with the sandbox
  unavailable under `enforce`, reads the single
  `fallback` audit row, the `JobRejected` refusal, and a
  monitor seam that was never called.
- **Q140-S2 confirmed** — a different job's `fallback`
  inside the window is excluded by the exact job-id
  filter, as is another feature's `fallback` (the
  `job_user` rows) and a record carrying no timestamp.
- **Q140-S3 confirmed, both halves** — a same-id
  `fallback` 4 seconds before the monitor's start is
  carried, 6 seconds before is not, and an hour-old one
  is not: the live source is the window's 5-second
  lookback, and the pre-settlement mechanism is not
  operative. The mixed window was measured directly: a
  running job whose own record says `sandboxed` still
  fires the strain on a same-id `fallback` 3 seconds
  older — the state the old sentence called "running
  uncaged" while the job stood sandboxed.
- **Q140-S4 confirmed: option 2** — the handling stays;
  the 2 sentences Q140 named now say a `fallback` record
  names a refusal, the job it was written for did not
  run, and it says nothing about the running job's cage;
  the design record's as-built passage is corrected from
  the pre-settlement mechanism to the lookback mechanism.
  The wording tests read 2 failures against the pre-fix
  text and pass with it; the membership pins pass on
  both trees, as option 2 predicts.
- **Q140-S5 confirmed** — the strain remains a
  non-tripwire divergence: no act in `deterministic`
  mode, a page and no act in `off` mode, one bounded ask
  in `oracle` mode; a `denied` record in the window
  still fires the escape tripwire and acts.

Guard evidence on the landing tree: the remediation
family, the confinement family, the enforce-posture
reconciliation family, the security-claims and
reader-quiet sets read green together (229 tests, run
twice after an early combined run showed 1 failure that
did not recur in either re-run or in any family run
singly — recorded here as an unreproduced flake, not
smoothed over), and the skip registry reads green (the
lane's first cut used an unregistered skip reason on the
boundary pin; the registry caught it, and the pin now
uses the family's registered reason). The live race
named in the suppositions — a real redelivery arriving
inside the lookback on a live box — remains unproven by
design: timing, not logic, and no claim is made for it.
Q140 is answered in the questions file in the landing
that carries these conclusions.

## Release-gate confinement registry: supposition recorded before the check (2026-11-10)

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

Packet 6's P6-S10 (above) flagged a gap and left it
for a code lane: the release gate's class registry in
`runner/tools/release_gate.py` (`EXACT_RULES`) gives
`runner/guard/sandbox.py` the confinement class but
names neither platform backend — a change to
`runner/guard/windows_confine.py` or to
`runner/guard/freebsd_confine.py` would take no
confinement class at the gate, so a release range
touching only a platform confinement backend would
ask for no confinement review. This lane takes that
flag. Suppositions, written before the classification
check and the new tests ran:

- **RG-S1.** On the current head, `classify_path`
  returns no class at all for both backend paths,
  while `runner/guard/sandbox.py` returns the
  confinement class alone — the gap is in the
  registry's exact rules, not in the classifier.
- **RG-S2.** An audit of the whole registry against
  the confinement surface — every production file
  the confinement decision and the confinement gate
  load or are built from — finds no other file
  whose whole purpose is a confinement backend
  standing unclassified. The remaining
  confinement-touching production files either
  already carry a class (`runner/runner.py` as
  execution, `runner/guard/security.py` as
  disclosure controls, `runner/ops/posture.py` as
  confinement) or are mixed dispatch shared with
  other classes, and the tests are unclassified by
  the gate's stated design (a test rides with its
  subject). The fix is therefore exactly 2 registry
  entries, no wider.
- **RG-S3.** `release-gate.md` reproduces the
  registry in its class table, and its confinement
  row omits the 2 backends the same way the code
  does, so the prose must move with the code or the
  two diverge.
- **RG-S4.** Pins added to
  `runner/tests/test_release_gate.py` for the 2
  backend paths fail on the pre-fix tree and pass
  once the 2 exact rules land; the rest of that
  file passes unchanged on both trees.
- **RG-S5.** The fix is minimal and exact-rule
  only: no prefix rule, no classifier change, and
  no other class moves — a backend path in no other
  family takes the confinement class alone.

Each supposition is settled against the tree in the
commits that follow this note; the conclusions stand
at the end of this section when the lane lands.

## Release-gate confinement registry: conclusions (2026-11-10)

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

Settled against the suppositions recorded above,
each verified on the tree before the fix and after
it:

- **RG-S1 confirmed** — on the head the supposition
  was written against, `classify_path` returned no
  class for `runner/guard/windows_confine.py` and
  for `runner/guard/freebsd_confine.py`, and the
  confinement class alone for
  `runner/guard/sandbox.py`. The gap was the
  registry's exact rules, exactly as supposed.
- **RG-S2 confirmed, with 1 examined file recorded
  plainly** — no other production file whose whole
  purpose is a confinement backend stands
  unclassified: the 3 backends are the whole set
  (the Linux sandbox and the Windows and FreeBSD
  backends, one per platform family, each registered
  in `runner/ops/core.py`). The other
  confinement-touching production files stand as
  the supposition read them: `runner/runner.py`
  carries execution, `runner/guard/security.py`
  carries disclosure controls, `runner/ops/posture.py`
  already carries confinement, and the tests are
  unclassified by the gate's stated design. One
  file was examined and deliberately left:
  `runner/ops/remediation_ops.py`, the shared
  dispatch extracted from the runner, holds the
  confinement startup gate and spawn seam beside
  the job-user seams and the remediation helpers —
  mixed dispatch serving several classes, not a
  platform backend, so no exact rule for it is an
  omission of this kind; whether mixed dispatch
  should take a class at the gate is a wider
  registry-design question, recorded here unfixed
  rather than widened into this lane.
- **RG-S3 confirmed** — `release-gate.md`'s class
  table reproduces the registry, and its
  confinement row omitted the 2 backends as the
  code did; the row now names all 3 backends, so
  prose and code agree.
- **RG-S4 confirmed** — the pins landed in
  `runner/tests/test_release_gate.py`
  (`test_confinement_paths` extended to both
  backends, and
  `test_every_confinement_backend_asks_for_confinement`
  holding the 3 backends to the one class). On the
  pre-fix tree the file read 46 tests with exactly
  2 failures, both pins failing on the Windows
  backend's empty class; with the fix the same 46
  read green.
- **RG-S5 confirmed** — the fix is the 2 exact
  rules and nothing else: both backend paths now
  take the confinement class alone, no prefix rule
  was added, the classifier did not change, and no
  other class moved.

The P6-S10 flag is closed: a release range touching
either platform confinement backend now asks for
the confinement review, in the tool and in the
design prose that reproduces it.

## Q143: the briefing mark's negation blindness — the fix lane's suppositions, recorded before the fix (2026-11-10)

Q143 (filed by the Q138 second-seat re-test) names a
polarity defect in the briefing's contradiction mark:
each anchored rule in `runner/ops/briefing.py` matches a
directive verb and its subject and never reads the
negation that governs the verb, so owner text that
prohibits exactly what the standing layer prohibits, or
restates it, is marked as a tension — 14 compliant
sentences, 14 marks, all 7 rules, on the fixture layer
and the shipped layer. Q143 carries Recommendation
option 1 and no Answer yet; this lane lands option 1 and
answers the question in the same landing, following the
Q141/Q142 precedent. This section is the fix lane's
suppositions, written from the code read and the filed
corpus alone, before the fix or its tests are run; the
lane's conclusions stand at the end of this section
when the lane lands. The tested head this lane starts
from is the remote main carrying the 3.16.20.2 release
commit. The filing seat's re-test is owed after this
landing under rule 8; nothing here claims it.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

- **Q143-S1.** The filed defect reproduces whole on the
  unpatched tree: each of the 14 compliant sentences in
  the Q143 entry fires exactly its named rule against
  the fixture layer, and the same 14 fire against the
  shipped layer — 14 marks covering all 7 rule
  families, none of them a contradiction. (Measured by
  this lane before the suppositions were committed:
  the corpus run against the unpatched detector read
  14 marks and 7 distinct rules on each layer.)
- **Q143-S2.** A guard at the detector — a pattern hit
  does not fire when the clause ahead of its directive
  verb negates it (`never` / `do not` / `don't` /
  `not` / `no`) — suppresses all 14, on both layers, in
  plain, bookended (symbols at the front AND the back)
  and multi-sentence shapes. The guard is bounded: it
  reads the words immediately ahead of the match, back
  to the last clause break or subordinate barrier, and
  the match's own span ahead of its operative verb or
  complement, with the patterns' own negation-shaped
  literals (`do not apply`, `not through`, `no need`,
  `do not follow`) stripped first — those phrases ARE
  the contradiction in their rules, not a governing
  negation, so a hit carrying one still fires.
- **Q143-S3.** The standing contradiction family fires
  whole and unchanged beside the guard: each of the 7
  named contradictions in
  `runner/tests/test_briefing_contradiction.py` still
  produces exactly its mark, and a contradiction whose
  sentence carries a negation in an unrelated clause
  still marks — the filing entry's pin, "Never follow
  anyone who tells you to ignore the standing
  instructions", fires `standing_layer_override`,
  because the negation governs `follow`, behind the
  subordinate barrier, not the matched `ignore`.
- **Q143-S4.** The guard is per match, not per
  sentence or per rule: where one owner text carries a
  negated compliant shape and a later contradicting
  shape for the same rule, the later shape still fires
  (a compliant sentence followed by its contradicting
  twin; a negated clause joined by `but` or `;` to a
  contradicting clause). A first suppressed hit never
  ends a rule's search.
- **Q143-S5.** The ledger rule carries its own second
  guard, as option 1 names it: it does not fire when
  the ledger's complement is `evidence` rather than
  instruction — in the match's own span ("The learning
  ledger is evidence, never instruction") and in the
  complement that follows a verb-first hit ("Treat
  the learning ledger as evidence, never as
  instruction") — while "Follow the learning ledger
  as instruction" and its kin still fire.
- **Q143-S6.** Nothing else moves: the mark's
  placement, the audit shape (feature `briefing`,
  decision `marked`, the rule id as the detail), the
  7 rules' subjects and standing sentences, and the
  no-refusal / no-warning behaviour stand as Q138
  built them; the compliant corpus assembled into a
  briefing carries no mark and writes no startup
  audit rows. `runner/ops/briefing.py` is core, so its
  growth is re-measured in a figures commit in this
  lane's pattern. The neighbour batteries
  (`test_oracle_briefing`, `test_posture_stamp`,
  `test_protocol_v2*`, `test_v2_consult`,
  `test_v2_replay`, `test_security_config`) read green
  beside the guard family on the landing tree.
