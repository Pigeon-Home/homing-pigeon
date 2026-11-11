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
the 3.16.20.2 cut and the documentation overview: filed
now, on the desk, ready to pick up in that order.

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
