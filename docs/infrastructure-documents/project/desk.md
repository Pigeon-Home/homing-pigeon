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
  manuals, and `docs/`'s own top holds `FUTURE.md`,
  `FAQ.md`, `ENTERPRISE.md` and the support matrix.
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
`docs/`'s own top files (`FUTURE.md`, `FAQ.md`,
`ENTERPRISE.md` and the support matrix). **P2-S3
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
`docs/ENTERPRISE.md` stand as written; ENTERPRISE.md is
the placeholder rule 6 keeps as-is and was not touched.
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
  release, verified 2026-11-08, though 3.16.20.1 was
  published on 2026-11-10.
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
  current release, 3.16.20.1 of 2026-11-10, stating the
  official release on the 3.16 line and the security
  posture finished; no section for 3.16.20.2 will stand
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
  3.16.20.1 changelog section) and San Francisco sitting
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
3.16.20.1 of 2026-11-10, stating the official release
on the 3.16 line, the counter restarted at 1, and the
security posture finished for real (confinement and
the separate job user at `enforce` refusing rather
than running weaker, the Windows and FreeBSD backends
named with their field proof). No 3.16.20.2 section
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
3.16.20.1 changelog section) and San Francisco as
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
