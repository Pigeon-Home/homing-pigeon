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
`audit`. One follow-up stands open:
registering `runner/guard/windows_confine.py` in the core list
(`runner/ops/core.py`) with the re-measure that addition has
always carried, the way the briefing files joined in 2026-11.

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
