# Campaign standing orders

<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->

The campaign runs continuously from this file. It does not wait for
a new batch of questions. When one piece of work closes, the next
comes from the queue below, in order, without asking anyone. The
owner should never have to hand the campaign its next task; if the
campaign is idle, these orders were not followed.

How a campaign is run (the rig, the loop, recording a finding, the
watchdog, the hard rules) is `docs/project/campaign-playbook.md`.
Questions to Claude or the owner go in `docs/use/questions.md`
(AGENTS.md rules 7 and 8). This file says only what to work on next
and when to stop.

## Talking to the owner

The owner is the conductor (AGENTS.md rule 11, 2026-10-26): the
title in every ledger line, question and note from now on. This
file's older text keeps its word.

During a campaign the owner hears from the campaign in chat only when
he must act: a question in the "When to stop and ask the owner" list
below, worded so he can answer it in one line. No progress reports,
no summaries, no confirmations, no "starting X" or "done with Y".
Progress lives in the ledger at the end of this file and in the
commits; he reads those when he wants them. If he asks for status,
answer in three sentences and go back to work.

What counts as talking to him, and is not allowed outside the list:
a chat message that reports progress, confirms an order was heard,
announces a start or a finish, repeats a finding that is already in
a commit or a Q entry, or relays a question that belongs in
`docs/use/questions.md`. A reminder of this section posted in
`docs/use/.com.chat` by Claude means the pattern was seen; the next
rule refresh re-reads this section and says so in the ledger.

## Rule refresh, every hour

Long runs lose context. At least once an hour, and after any restart
or context reset, re-read before taking the next item: this file,
AGENTS.md (rules 7, 8 and 9 above all), the open entries in
`docs/use/questions.md`, and `docs/project/campaign-playbook.md`'s
hard rules. Note the refresh in the ledger as one line
("rules refreshed <time>"), followed by the hour's resource line
(below). A ledger with no refresh line in the last hour of activity
means this step was skipped.

## Throughput: the rig stays busy, and says what it used

The owner's order (2026-10-25): while a campaign runs, the rig's
CPU is kept at about 90%, and every piece of testing comes with a
resource report. A rig that sits at 10% is waiting on something, and
waiting is not testing.

- Run the suite and the hunts through `runner/tools/rig_resources.py`:
  `python runner/tools/rig_resources.py -- <the command>`. It prints
  one `resources` line from the kernel's counters (the box's CPU
  share over the run, the command's own CPU time and the cores it
  kept busy, peak memory, memory and disk at the end, the exit code,
  and a verdict: `on target`, `under-driven`, `over`). Paste that
  line into the ledger under the item it measured, and the hour's
  line under each "rules refreshed" line.
- To reach the target: run the suite sharded
  (`runner/tools/run_tests_parallel.py --jobs <cores>`), run the
  previous item's verification while writing the next item's test,
  and never wait on a CI run with the rig idle: take the next item
  and come back to the run when it finishes. Hypothesis budgets go up
  when the box is under-driven, not the sleep.
- The measure step too (Claude, stamp 50000c8e, 2026-10-26, from
  the day's resource lines, every one `under-driven` at 0.8 to 1.0
  cores busy on a two-core box): `.github/coveragerc` already sets
  `parallel = True` and the `.pth` hook starts coverage in every
  child, so the suite under coverage runs as
  `python -m coverage run --rcfile=.github/coveragerc
  runner/tools/run_tests_parallel.py --jobs <cores>` and then
  `coverage combine` exactly as before; one shard per core, the same
  numbers, half the wall. A de_dust grow runs as
  `python runner/tools/de_dust_corpus.py grow --jobs <cores>
  --rounds <large>` (`HP_DE_DUST_JOBS`, `HP_DE_DUST_ROUNDS`):
  the targets grow one per core, and a grow that finishes in
  seconds is not a measurement, so rounds go up until the grow
  fills the gap to the next item. The regression pass takes
  `--jobs <cores>` the same way. Anything that still reads
  `under-driven` after that is a single-process step to name in
  the ledger.
- The rig runs no model, at all. The Oracle under test needs none:
  by design (runner/oracle/opinion.py) the model's only channel
  into an opinion is a text note capped at 240 characters and
  labeled "Model-formed note:", appended to a member the
  deterministic tier already formed; the opinion is not a gate
  and never blocks, holds or approves a job. So the model's whole
  output space is a fixture: mode in {off, diagnose, advise,
  repair}, verdict in {likely_success, likely_failure}, repaired
  in {true, false}, and a note that must be inert whatever it
  says. The Oracle agent's other channel is its tool calls, a
  finite set with their refusals already pinned. Stop any resident
  model server on the rig for the duration (the first resource
  line read 97% memory used on a 2-core box) and paste the
  `resources-top` line with each resource line so the owner sees
  what holds the memory (owner's order, 2026-10-25).
- Two `under-driven` hourly lines in a row is a finding about the
  loop: write in the ledger what the rig was waiting on, then fix
  that. `over` for an hour (the box swapping or the suite timing out)
  means one fewer shard, not a slower loop.
- A test that fails only under load is a finding about the test
  (make it load-tolerant: barriers and outcomes, not sleeps and
  clocks) unless it guards a promise about time; then it is filed
  as a question with the measurement attached.

## The loop

1. Pull main. If the last rule refresh was more than an hour ago, do
   it now (above).
2. Read `docs/use/questions.md`. Anything answered since the last
   pass that changes the campaign's own work (a fix to re-verify, a
   probe to retire, a decision that moves an assertion) comes first.
3. Take the first open item from the queue below. Mark it taken by
   writing one line under it ("taken <date>, <agent stamp>") in the
   same commit as the first test for it.
4. Work it to done (the definition is under each queue). Commit as
   you go; keep main green; check what skipped before calling
   anything green.
5. Mark it done with the commit or run that proves it, and return to
   step 1.

A finding that needs production code is filed as a question for
Claude, in the four-part format, with a failing-by-design test. The
campaign does not wait for the fix: it moves to the next item and
re-verifies when the question is answered.

The hourly regression pass (owner, 2026-10-26; Claude, stamp
50000c8e) -- suspended by the conductor's order of 2026-10-26
(see "The queue"): until he lifts it, the rig runs no pass, and
de_dust is the only effort. The paragraph stands for the day it
resumes. When it runs: once an hour, beside whatever campaign is
running, the rig runs `python runner/tools/rig_resources.py -- python
runner/tools/regression_pass.py --pull --jobs <cores>`. It runs the
whole suite on the head of main, re-runs any red alone to split
flake from deterministic, bisects each deterministic red between
the last green head this rig recorded and the current head to name
the commit it has been red since, and prints one ledger line and,
on red, a paragraph for `questions.md`. Paste the ledger line under
the hour's "rules refreshed" line with the resources line, and
commit `docs/reports/regression/passes.jsonl` with it: the pass
appended its own line there (head, tests, wall time, the failing
ids, the flake split, the culprits), and that file is the proof
the pass ran, green passes included. On a deterministic red, file
the paragraph as a Q to Claude and keep working; the fix is
Claude's lane. On a flake, run
`regression_guard.py --repeat 10` on its module and file what that
says. Before any push that adds or changes a test module, the
pre-push guard (section P) runs first.

Two rules keep main green while that happens (owner's standing
order, 2026-10-25, after a release was blocked twice in one hour):

- A failing-by-design probe lands under `@unittest.expectedFailure`
  with the question number in a comment above it. It then fails
  quietly until the fix lands and flips to "unexpected success",
  which is red: the fix commit removes the decorator. A red probe
  in the live suite blocks every release behind it; an expected
  failure blocks nothing and is just as much a proof.
- A release window: when the head of main is a commit whose message
  starts with `release:`, hold every push until that commit's build
  has completed (the `build` run on it; about twelve minutes), then
  resume. Three cuts of 3.12.67 were lost to tests that landed in
  that window and went red on Windows. Keep working; stack the
  commits locally and push them together when the window closes.
- A test is not done until the build's Windows shards are green
  for it (the shard annotations name a red test). The fixtures
  that broke there this morning are the same three shapes each
  time: counting `os.stat` calls to catch a path probe (Python
  3.12+ answers `os.path.isfile`/`isdir` in C on Windows, so the
  probe never shows; stub the probe directly), a fake `os.close`
  that does not release the descriptor (Windows then cannot remove
  the file), and a directory or `chmod 000` standing in for an
  unreadable file (neither is unreadable there; a refusing `open`
  is). A scripted binary on PATH needs a POSIX shell: skip the
  class on `nt` with a registered reason. The lint for these
  shapes is `runner/tests/test_windows_portability.py`: run it
  before every push (it is in the suite, so a red Linux run names
  the line); a line that is right for a reason it cannot see
  carries `# portable: <why>`.

## When to stop and ask the owner

Only these stop the loop, and only for the item they block. Write
the question in `docs/use/questions.md` addressed to the owner, then
continue with the next item that does not need it.

- A secret: anything that needs a mailbox password, a token or a key
  that must not be in the repository.
- A machine: a real Windows box, a host the VM cannot reach, a device.
  (A GitHub runner is not a machine for this purpose: ask Claude for
  a workflow instead.)
- A decision only the owner can make: what the project promises, what
  is in scope, a security posture.
- Money or an external account.

Nothing else is a reason to stop. "The list is done" is not: the
queue below does not run out (queue D refills it).

## The queue, in order

**The conductor's order of 2026-10-26, which overrides the order of
this queue until he lifts it: Project de_dust (section M) is
the campaign's only effort. No hourly regression pass, no Platinum
cycle, no other item from this queue; the rig fuzzes, and the CPU
is pegged.** Everything below M stands as written for the day he
says so; the hourly regression pass in "The loop" is suspended the
same way. The pre-push guard still runs before a push that touches
a test module, since that is part of landing the work, not another
effort.

The owner reset the target on 2026-10-25 (Q24): the campaign exists
to prove that each security control does what SECURITY.md promises
when it is turned on, with the Oracle simulated, and to find the
races on the enforce path. Queues S and R are that work and come
first; P, then M, A, B and D resume only when S and R have nothing open.
A never-executed line is a refill, not the goal, except under P, where
the owner has made the whole map the goal for as long as the rig is
otherwise idle.

### S. The switches, on

The ledger for S and R is in code: `runner/tests/switch_roster.py`
lists every control, its promise and the tests that prove it, and
`.github/workflows/switch-proofs.yml` runs the roster on every push
(a Linux leg with bwrap, a root leg with a second user, a Windows
leg) and names each control proven, unproven, or failed. Take the
first entry whose `tests` list is empty, in roster order; an item
is done when its entry lists tests that run and pass on the leg
where the control applies and the workflow is green. Adding tests
to the roster is this campaign's lane; the controls, promises and
needs change only through the questions file.

One item per control. For each: read its SECURITY.md section and
the config keys it names, list what the suite already pins (the
files below), and write what is missing as end-to-end tests through
the intake and `execute_job`, not through the helper alone. Every
item carries the three modes where the control has them (`off`
allows the case; `audit` runs it and writes the `would_deny` line;
`enforce` denies it and writes `denied`) and a negative control:
the same escape succeeds with the mode off, so a test that passes
for a reason other than the control is caught.

Two owner decisions (2026-10-15) are part of the promise, and a test
that "hardens" past them is wrong: with `confinement: enforce`, a
sandbox that does not work at startup refuses to start (Q9), but a
sandbox that fails after a good start lets the job run unsandboxed
with a WARN line and a `fallback` audit entry; `job_user` without
root does the same (`job_user_needs_root`). Pin those as they are.

1. M1, the size caps: `max_job_bytes`, `max_script_bytes`. Always
   on; over the cap is rejected before anything runs; a non-number
   refuses startup. Have: `test_size_caps.py`.
2. M2, the key policies: `policy_env`, `policy_files`,
   `policy_args`, per pinned key. Have: `test_policy_constraints.py`,
   `test_security_config.py` (the mode trio), `test_flag321_scenarios.py`.
   Missing until shown otherwise: each policy driven through a
   signed job under each mode, with the audit line's `mode` member
   asserted.
3. M3 and M4, `--audit-report` and `--posture`: read-only. Neither
   writes `config.json` or the audit log; the report's counts equal
   the entries written by the M2 and M6 tests above. Have:
   `test_audit_report.py`, `test_posture.py`.
4. M5, `audience`: `enforce` rejects a job whose audience is not
   this `runner_id`; `audit` runs it and records; `off` ignores it.
   Have: `test_audience.py`.
5. M6, `confinement`: `enforce` runs the job inside bwrap with no
   network, no home, `/usr` read-only and the workdir only at
   `/work`; the same escape succeeds with the mode off. Have:
   `test_confinement.py` (`EnforceTest` and its negative control,
   Linux CI only). Missing: each wall as its own case and control
   (network, home, `/usr` write, a path outside `/work`), and the
   after-a-good-start fallback above.
6. M7, the AppArmor, SELinux and systemd templates under
   `docs/security/hardening/`: files only; nothing installs them.
   Prove that they parse and that the runner's paths in them match
   the install layout; file a question if they drift.
7. M8, `job_user` and the secret files: `enforce` drops uid and
   groups (a failed `initgroups` does not keep the runner's groups,
   Q18); the workdir is chowned to the job user; a missing or
   world-readable secret file refuses startup. Have:
   `test_secret_files_job_user.py` (as root, `.github/workflows/job-user.yml`),
   `test_runner_face.py`, `test_credential_canary.py`.
8. M9 and M10 are design documents (asymmetric signing, the approval
   gate); nothing in the runner implements them. Nothing to enable;
   skip, and do not write tests against the design.
9. The Oracle, exhaustively, with no model: the deterministic
   opinion and the judge are driven with fixtures, and the model is
   a loopback fake that returns a chosen element of the alphabet.
   Prove, for every mode x verdict x repaired, under every latitude
   and every key policy mode, that the security decision made above
   the Oracle and the job's outcome are identical to the no-model
   run, and that the note is inert: fuzz it with instructions,
   JSON, approvals, refusals, huge and empty strings, and show it
   lands capped and labeled and changes nothing (roster
   `ORACLE.alphabet`). Prove that `refuse` and `advise` latitude
   refuse what `repair` repairs (AGENTS.md's table), and that every
   tool call the agent's model can emit is read-only or refused
   (roster `ORACLE.tools.alphabet`).

Done per item when each promise in the control's SECURITY.md
section has a test that fails if the promise were false, plus its
negative control, on the platform where the control applies, and
the roster entry lists them (the ledger line names the entry). A
promise the code does not keep is filed as a question for Claude
with the failing-by-design test.

### R. Races on the enforce path

With `workers: 2` (the runner's thread pool), under `enforce`:

1. Two jobs at once: each workdir is chowned to its own job and
   never the other's; two bwrap sandboxes do not share `/work`; the
   audit log receives both decisions, each entry whole.
2. A rollover of `security-audit.jsonl` (`_enforce_bound`) while a
   decision is being written: no entry lost, none split.
3. A replayed job id and a fresh job hitting the seen set together:
   the replay is rejected on both orderings.
4. A `config.json` write during a job: the security block does not
   hot-reload into the running job, and a bad value written live
   leaves the current settings in force (Decision 1).

Done when each race has a test that drives the two sides with a
real second thread and a barrier (not a mock of time), passes
repeatedly, and asserts the security outcome, not only that nothing
crashed (`test_concurrency_poison.py` already covers the crash-free
part and is the pattern for the rig), and the roster entry (R1 to
R4) lists it.

### P. Project Platinum: coverage-guided fuzzing (owner, 2026-10-25)

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

The hand-off and the fixed rules are Q59 in `docs/use/questions.md`.
The loop:

1. **Measure.** The suite under `coverage` exactly as
   `.github/workflows/coverage.yml` runs it (the `.pth` hook, the
   rcfile, `combine`, `json`), wrapped in `rig_resources.py`.
2. **Map.** `python runner/tools/coverage_targets.py <now>.json
   --since <last>.json`. The header line is the score; the rows are
   the targets, classified from the AST: `logic`, `guard`, `except`,
   `platform`, `shadowed`.
3. **Aim.** Top-down: `logic`, then `guard`, then `except`.
   `platform` is "covered on the other platform" (A's rule) and
   skipped; `shadowed` is a Q to Claude, not a test.
4. **Fuzz.** One hypothesis test per target in
   `test_platinum_<area>.py`, no `max_examples` of its own (the rig
   sets `HP_PLATINUM_EXAMPLES`), driving the function with a seed
   corpus mutated the ordinary ways; the job-fuzz mutators are the
   vocabulary. Assert the contract, never the implementation. Never
   edit an existing test.
5. **Crash?** An exception where the contract says refusal: Q to
   Claude with the falsifying example; the probe lands under
   `@unittest.expectedFailure` with the Q number.
6. **Measure again** and ledger the cycle: `platinum <n>: statements
   X% (+d), branches Y% (+d), <k> tests, <m> crashes filed,
   <resources line>`. Refresh `docs/reports/<version>/coverage-gaps.md`
   with the full table and add the row to that folder's
   `coverage.md` Platinum log.
7. **Under-driven?** The filler is the fuzz modules with a larger
   `HP_PLATINUM_EXAMPLES`, never idling.

"Coverage is 100%" is not a stop: the compass turns to branch arcs,
then to the mutation survivors (D4). Questions to Claude go in
`questions.md`; nothing to the owner but a one-line decision.

Added 2026-10-26 (Claude, stamp 50000c8e, from the build-windows
red of cycle 5 and the macOS sampler race, at the owner's word):
before every push that adds or changes a test module, run
`python runner/tools/regression_guard.py` on the tree. It takes the
modules changed against origin/main and runs each one natively,
again for flakes, in shuffled orders, under the simulated Windows
surface against the same module on origin/main (a count that
moved is a finding or a test bug, a count that did not is a known
artifact of the surface), and in-process with a snapshot of the
global state around every test (a leaked patch, environment
variable, working directory, signal handler or `os` attribute is
named with the test that left it), then the registry gates. Push
on green; on red, fix the test or file the finding, never soften
the check. The owner's Q62 decision replaces the "not a stop" line
above: when the trigger in Q62 fires, section M is next, and D4's
survivors come after it.

### M. Project de_dust: the fuzz corpus against the verifiers (owner, 2026-10-26)

<!-- Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

The conductor renamed the campaign de_dust on 2026-10-27 (it was
blueMonday from its naming on 2026-10-26 to then; the ledger lines,
the CHANGELOG and the answered questions keep the name they were
written with). Everything moved with it: the tool is
`runner/tools/de_dust_corpus.py`, the instrument
`runner/tools/de_dust_survivors.py`, the corpus
`runner/tests/de_dust/`, the tests `test_de_dust_corpus` and
`test_de_dust_survivors`, the plan `docs/project/de_dust.md`, the
archive directory's environment name `HP_DE_DUST_ARCHIVE`, and the
header key of every corpus, arc, run and survivors file
(`"de_dust": 1`). The grow in flight at the rename finishes on the
old tool in memory; it banks at the new paths (git's rename
detection carries its changed files across), and the next grow
starts with the command below.

The plan is `docs/project/de_dust.md` (the conductor's
campaign, to run indefinitely: the surface, the contracts, the
seeds and vocabulary, the roles, the saturation rule and the
phases); the hand-off and the fixed rules are Q62 in
`docs/use/questions.md`; the owner named the campaign on
2026-10-26. The tool is `runner/tools/de_dust_corpus.py`, the
corpus is `runner/tests/de_dust/<target>.jsonl` (the targets
are the tool's own list, `stats` prints them with their saturation;
`wire`, `cloud`, `v2`, `crypto`, `local`, `stash`, `mail` as of Q65,
and `dtls` as of Q66, `board` as of Q67, `board_ops` in the same
release, `channels` as of Q68, `manifest` as of Q69, `inbox`
and `local_inbox` in the same release; the readers on the plan
are in the corpus, the sequence contract is on `local` as of
Q70, the corpus is replayed under the simulated Windows surface
as of Q71, and the mutators carry the IETF drafts' grammar as
of Q72, saturated at 20,000 rounds on the readers it inserts
into as of Q73, and the posted capture's shape is a seed,
rebuilt, as of Q74), and
`runner/tests/test_de_dust_corpus.py` replays it on every leg.
The loop:

1. **Trigger.** Started by the conductor on 2026-10-26, and the
   campaign's only effort by his order the same day: a grow is
   running on the rig at every moment, with `--jobs` at the box's
   core count and `--minutes` long enough to reach the next rules
   refresh, and nothing else runs beside it -- no pass, no measure,
   no other item. The CPU is pegged: the resource line reads on
   target or over, and anything lower is a serial step to name in
   the ledger. The campaign never idles between grows and stops
   only on the conductor's word.
2. **Grow.** `HP_DE_DUST_ARCHIVE=<the archive directory> python
   runner/tools/rig_resources.py -- python
   runner/tools/de_dust_corpus.py grow --rounds 20000
   --minutes 55`, started again at every rules refresh (`--jobs`
   defaults to the box's core count; name it only to use fewer): the targets cycle, `--jobs` at a time, the next
   starting the moment any one finishes, each cycle with the seed
   moved on, until the minutes are up; that is the continuous grow,
   and its resource line reads on target. The cycle starts at the
   target least recently grown in the merged `runs.jsonl` and goes
   on from the thinnest (Q107, 2026-10-28; `--order fixed` is the
   list's own order), so a one-core rig with a short cycle reaches
   every target over its day and two rigs reading the same ledger
   pick different targets as soon as one of them banks. `--seed` makes a run
   repeatable, `--verbose` prints each keeper. The grow is steered:
   it reads the last grows' records and leans on the mutators still
   finding arcs, a saturated one keeping a floor share (`--no-steer`
   for a uniform grow; `stats` names each target's live and
   saturated mutators). The archive directory is on the rig's own
   disk, outside the tree (Muse's offer, 2026-10-26: the rig has
   the room): every child a grow tries, kept or not, goes there as
   one gzip JSON-lines file per grow, and the run record carries
   the file's name, size, SHA-384 and count, so the tree says
   where the rest of the proof is; the archive is never committed.
   Once per rules refresh, after the grow cycle and before the
   next one starts, `python runner/tools/de_dust_survivors.py`
   (about three minutes; every target is in its kill set, the
   agent module's readers included): it rewrites `survivors.json`
   and adds its line to `runs.jsonl`, and the ledger line names
   the survivor count per reader. The survivors are the desk's to turn into
   seeds; a survivor the campaign thinks it can reach by growing
   is a Q to the desk naming the line. The grow's own aim is the
   live mutators `stats` names per target (today `t_case` and
   `t_insert` on `local`, `d_random_byte` on `dtls`); a target
   with none is run for the record and the archive, at its share.
   The commit is the proof of the work, every
   time: the corpus files that changed, `runs.jsonl` (the tool
   appends one line per seed or grow: head, seed, rounds, what was
   tried, what was kept, what crashed, where the archive is; and
   one per survivors run) and the `<target>.arcs.json`
   maps it rewrote, with the ledger line. A grow that kept nothing
   is still committed, because its line in `runs.jsonl` is the
   record that those rounds were run (the conductor's standing
   order, 2026-10-26: the data from the fuzzing goes into the
   repository, not only its results).
3. **Seed.** Fixtures the suite builds that the tool's `seed` does
   not yet (a signed body, an envelope, a v2 message) go into the
   tool's seed functions, invented names only. `grow` merges any
   seed the corpus lacks before it starts (by id, the corpus
   keeping every entry it has), so a seed the desk writes is in
   the next grow's corpus with no step between; `seed` alone does
   the merge without growing. The corpus files, the arc maps,
   `runs.jsonl` and `survivors.json` are written by this seat's
   runs and no other: the desk writes the tool and its seed
   functions, and reads the files (the conductor, 2026-10-26: one
   writer on a file). Never a real address, path or machine.
4. **Crash?** The tool writes it to `<target>.crashes.jsonl`,
   shrunk, and exits 1; `test_de_dust_corpus` carries it from
   there as an `expectedFailure` probe. File it in `questions.md`
   as a Q to Claude with the entry id and the detail line. The fix
   is Claude's lane, and the desk runs `python
   runner/tools/de_dust_corpus.py promote` in the commit that
   lands it (the one step the desk takes on the crash file, so the
   probe never stands red between the fix and the next bank): an
   entry that now meets its contract and reaches a new arc moves
   into the corpus, one reaching nothing new is dropped, one still
   crashing stays, and the probe disappears with the entry.
5. **Ledger.** `de_dust <n>: <k> entries, <a> arcs, <m> crashes
   filed, <resources line>`, from `stats` and the grow summary.
6. **Stop?** When a grow of the rig's full depth adds no arcs on any
   target for two cycles, D4's mutation survivors are next.
7. **Banking, when two rigs write (Q99, 2026-10-27).** One writer
   on a file (item 3) is the rule for one rig; when a second rig
   grows the same corpus, the two bank by union and the union is
   the contract: corpus entry files merge by union on the entry
   id, an id on both sides kept once; `runs.jsonl` merges by
   union of its records, stable-sorted on the `when` field,
   under exactly one header line, and a bank that would write a
   second header refuses instead; totals quoted in a ledger line
   come from `stats` run on the merged tree, never from a local
   tree before the merge; grow numbers are per rig, a seed is
   named whenever two rigs could read the same number two ways,
   and every ledger line names the rig that grew it. A bank that
   cannot meet the shape refuses and says so in its ledger line.
   Crash files union by id with one exception (Q106, 2026-10-28):
   a record `<target>.retired.json` names, found on a tree at or
   before its retirement (the record's `head` against the
   retirement's, by git ancestry; the `found` date against the
   retirement's where git cannot compare them), is a rig's stale
   copy or an echo and is not re-added; `grow` drops such a copy
   from the rig's file before it runs, so a crash found again on a
   tree after the fix is a regression and is banked.
   And a bank replays the crash records it merged at main's own head
   (`promote`, in the clone) before it commits (Q108, 2026-10-28): a
   record that still crashes lands as a crash, and one a grow found
   on a tree older than the fix is promoted or retired on the spot,
   never landing as a probe that passes. The ledger line says what
   was replayed ("Crash records replayed at main's head: ..."), how
   many stale copies the merge dropped ("Retired echoes not
   re-banked: N"), and the head of the rig's own tree ("The rig's
   tree at <head>"), so a rig banking with an older `rig_bank` (one
   whose line carries none of the three) is visible in the ledger
   itself.

Hard rules, as Q62: no new CI legs, no `continue-on-error`, every
skip registered, nothing about any machine in the tree, the
contract asserted and never the implementation, and the existing
corpus entries are never edited or removed by hand.

### A. The coverage map, gap by gap (folded into P while P runs)

Source: the latest `coverage` workflow run on main, its
`coverage-Linux` and `coverage-Windows` artifacts (made by
`runner/tools/coverage_gaps.py`). The ranked first seven are closed
(Q11 to Q17).

Next: take the function with the most never-executed lines on either
platform that is not marked taken in the ledger at the end of this
file, and that is not test or tool code. Prefer, at equal size, code
that decides what runs, what leaves the box, or who can reach it.

Skip a gap that exists only because the code cannot apply on that
platform (a Linux-only installer path on the Windows map, a Windows
registry read on the Linux map) when the other platform's map shows
it running. Moving a faked test into an ungated class to color those
lines on the wrong platform adds no protection. Record it in the
ledger as "platform-inapplicable, covered on <the other platform>"
and take the next gap.

Done when the lines run in the full suite on the platform where they
were missing (cite the coverage run) and a test asserts what the docs
say those lines do. A gap that cannot be reached without mocking the
world is filed as a missing-seam question and marked done as filed.

Stop working queue A for the day when the largest remaining gap on
both platforms is under 10 lines; go to B.

**Who works queue A (the conductor's word, 2026-10-27).** Two Claude
seats, split by folder so no file has two writers:

| Seat | Folders |
|---|---|
| `b000092f` | `runner/guard/`, `runner/wire/`, `runner/oracle/` |
| `a0000997` | the rest of the shipped tree |

`90000998` goes back to reviews and does not write coverage tests;
`40000e00` lands a coverage test only for a gap it finds while fixing a
question. A gap a seat finds outside its folders goes to the owning
seat as a line in `docs/use/.com.chat`. Each pass commits its run data
under `docs/reports/coverage/`, with every line it leaves unrun named
and the reason no test is aimed at it.

### B. Environment axes

Each setting below gets the env-axes treatment: the protection corpus
run once per value on a GitHub runner, the value asserted after it is
set, recorded with every result (`.github/workflows/env-axes.yml` is
the pattern; ask Claude in the questions file to add each axis to it).

1. `kernel.yama.ptrace_scope` at 0, 1, 2 and 3: can a job read the
   runner's memory or attach to it?
2. `fs.protected_symlinks` and `fs.protected_regular` on and off: can
   a job plant a link the runner follows?
3. `hidepid` on `/proc` (0 and 2): can a job see the runner's command
   line and environment?
4. The job_user feature on and off, crossed with each of the above.

Done per axis when both values are green, or the difference is filed
as a finding.

### C. Live paths that need the owner (park until unblocked)

1. The live email capture (Q2, Q11): one real round trip per release
   through the dedicated throwaway mailbox, the messages committed as
   fixtures. Needs the mailbox credentials from the owner, on the
   machine that runs it, never in the repository.
2. The cages the other kernels lack (the plan's open decision 3):
   a job object and a restricted token on Windows, `sandbox-exec`
   on macOS, a jail on FreeBSD. The platforms themselves are no
   longer parked: as of 2026-10-25 the suite and the roster run on
   Linux, Windows, macOS (plain and as root) on every push and on
   FreeBSD weekly (`docs/project/testing.md`, "Where the suite
   runs"). What stays parked is the product work: each cage is a
   scope decision for the owner, and until he makes it the roster
   judges those kernels on the controls they have.

### D. Refill

When A is under its threshold, B is done and C is parked, start a new
hunt from these, one at a time, and add what each finds to queue A's
ledger:

1. Re-run the documented-default hunt against every key added to the
   docs since the defaults registry was last complete.
2. Every claim in SECURITY.md and `docs/security/threat-model.md`:
   one test per claim that would fail if the claim were false, plus
   its negative control.
3. Every example in PROTOCOL.md and AGENTS.md's "Do not emit" table,
   run as written through the runner.
4. The mutation workflow's surviving mutants: each survivor is a
   missing assertion. The signal is whole again as of run
   40205330969 (566 mutants in security.py, 500 killed, 66 survived;
   Q22): take those 66 first, from that run's `mutation-log`
   artifact or a local `mutmut run` on the same commit, then the
   weekly `mutation-seeded.yml` runs.

Then return to A: new code since the last pass has made new gaps.

## Ledger

One line per item taken: queue, item, date taken, agent stamp, and
when done, the proving commit or run. Newest first.

- Queue A taken (a0000997, 2026-10-28): the NATS transport's loop.
  A stop on another thread cleared the pipe's client, and close()
  its socket, under the loop's reads; both escaped as AttributeError
  (build 40781436856, red). A MSG size that is not a number escaped
  as ValueError. Fixed and pinned, six tests that fail on the old
  code: `36ed40d` (`test_nats_pipe_shutdown.py`).
- Queue A dispositions (a0000997, 2026-10-28): `exec.execute_job`'s
  second "script must be a string" and `extsources._clean_rel_path`'s
  "names no path", both unreachable by construction, removed as Q40,
  Q45 and Q47 were: `2de27ec`.
- Queue A taken (a0000997, 2026-10-27): the rest of the shipped tree
  in one whole-suite pass. Script mode and every entry point
  (`test_script_mode.py`, `f527d9a`), refusal edges in the sender,
  staging, the extension loader and install (`test_refusal_edges.py`,
  `06888e0`). Shipped code 99.00 to 99.51 percent of lines; run data
  and every line left unrun with its reason in
  `docs/reports/coverage/local-regression-2026-10-27.md`.

- rules refreshed 2026-10-25 06:37 PDT
  resources 2026-10-25T13:37:09Z: cores 2 | box cpu 65% | wall 0s | cmd cpu 0s = 0.7 cores busy | peak rss 29 MB | mem used 97% | disk free 166.4 GB | exit 0 | under-driven
  (scoped verification runs are short by
  construction; the rig idles between takes,
  not inside them. Q23's Answer/Applied-in
  lines are still blank although the deletion
  landed in f4e2378 -- the answerer's
  bookkeeping, noted here.)
- rules refreshed 2026-10-25 07:02 PDT —
  acknowledged, per Q29 (the owner's rule
  relayed by Claude): a failing-by-design
  probe lands under @unittest.expectedFailure
  with its question number in a comment, and
  an item is done only when the build's
  Windows shards are green for it. The three
  Windows fixture shapes are noted (stat-call
  counting, a non-releasing fake close, a
  directory or chmod standing in for an
  unreadable file). Also noted: the release
  window rule — hold pushes while HEAD is a
  `release:` commit whose build has not
  completed. Q30 (a RELEASE_TOKEN secret for
  tag-carried workflow files) stands in the
  questions file for the owner; it blocks
  Claude's release lane, not this queue.
  resources 2026-10-25T14:02:13Z: cores 2 | box cpu 53% | wall 1s | cmd cpu 0s = 0.4 cores busy | peak rss 33 MB | mem used 91% | disk free 166.4 GB | exit 0 | under-driven
  resources-top: hatch 256 MB, python 138 MB, python 12 MB, hatch-execd 7 MB, systemd 5 MB
  (scoped verification runs are short by
  construction; the rig idles between takes,
  not inside them.)
- A (refill) — Windows-hardening of the
  residual legs, same day: Claude's pass
  (382eb3a) made the two kill_tree tests and
  the monitor test true on Windows too (a
  patched POSIX identity with the kills
  recorded, instead of a POSIX `sleep`), and
  had already hardened InstallSmallLegsTest's
  getuid leg. Muse's parallel edits to the
  same tests were dropped in the rebase in
  favor of his.
- A (refill) — event-log tail legs (coverage
  run 40189711740): the Windows event log
  reader's broken-ElementTree return, its
  all-queries-failed return, its event
  formatting with the ATT&CK tag, and its
  character bound — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerResidualLegsTest
  (test_runner_last_edges.py), driven as on
  Windows with the wevtutil seam faked, the
  same pattern as the registry watch. Done
  when a coverage run shows the taken legs
  clean.
- A (refill) — wire and chat-server legs
  (coverage run 40189711740): protocol_v2's
  non-string answer riding empty, the
  oracle token check's non-string refusal,
  the chat server's deterministic page over
  the real loopback server, and the mailbox
  module's default log line — taken
  2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  AwaitAnswerNonStringLegTest
  (test_protocol_v2_messages.py),
  RunnerResidualLegsTest
  (test_runner_last_edges.py),
  MailboxDefaultLogLegTest
  (test_transport_shells.py). Recorded
  without a take: _oracle_instruction_kind's
  post-prefix empty-words return cannot
  fire (the lead is a single-space join of
  nonempty tokens, so a matched polite
  prefix always leaves a word behind); and
  ask_model's answerless-retry return
  cannot fire (a guard-tripping reply
  carries its "answer" key, and an absent
  key reads as None, which the format guard
  passes). Done when a coverage run shows
  the taken legs clean.
- A (refill) — dri, audit-report and
  remediation legs (coverage run
  40189711740): the retained scan's non-JSON
  pass-over, the fused score's stale-alert
  skip, the audit report's no-security-module
  read, and the Windows creation-time
  reader's unreadable-times answer (kernel32
  faked at the seam, so the leg runs on any
  platform) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DriResidualLegsTest (test_dri.py),
  ReadEntriesNoSecurityLegTest
  (test_audit_report.py),
  WinCreatedTicksLegTest
  (test_remediation.py). Done when a coverage
  run shows the taken legs clean.
- A (refill) — job-fuzz mutator legs
  (coverage run 40189711740): the truncate,
  duplicate, drop, null-byte and splice
  mutators' refusals, the dictionary
  builder's non-job seed, and the command
  split on both platform shapes — taken
  2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MutatorRefusalLegsTest (test_job_fuzz.py).
  Recorded without a take: _mut_blank_line's
  refusal cannot fire -- _script_lines is
  str.split, which never returns an empty
  list. Done when a coverage run shows the
  taken legs clean.
- A (refill) — runner.py residual legs
  (coverage run 40189711740): _load_mod both
  failure shapes, the job-user face's
  setgroups, _write_json under the binary
  flag, a payload-less message body, the
  remediation audit's silent return, the
  sensor core's unavailable and config-error
  answers, the ask function's blank answers,
  the opinion note's truncation and refusals,
  the job description's timeout member, the
  query handler's unexpected-error branch,
  kill_tree's extra pids and failed-kill
  swallows, the disk claim guards, save_seen's
  merge over the on-disk key list,
  load_retained's unprovable containment, an
  already-listening inference daemon, the
  monitor's alerts guards, the registry
  watch's snapshot-write swallow, and the
  confinement followup's unmeasurable
  quarantined file — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerResidualLegsTest
  (test_runner_last_edges.py) and
  ConfinementFollowupTest
  (test_remediation.py). Recorded without a
  take: save_seen.merge's not-a-dict reset
  cannot fire (_with_seen_file coerces the
  disk value to a dict before the mutator
  runs); load_retained's containment-mismatch
  return cannot fire through the seam (the
  stored path is built flat under the
  realpath'd retained dir and a symlinked
  file is refused one check earlier);
  ensure_inference_ready's hostless-endpoint
  return cannot fire (inference_config
  already refused every endpoint without a
  hostname). Done when a coverage run shows
  the taken legs clean.
- A (refill) — DTLS record legs (coverage run
  40189711740): the record opener's sequence
  wrap-back, the server core's by-address
  record route, and the fragment-reassembly
  paths — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RecordSealerWrapBackTest,
  FeedRecordByAddressTest,
  FragmentReassemblyGarbageTest
  (test_dtls.py). Recorded without a take:
  the parse-failure returns after fragment
  reassembly (dtlsproto 1002 and 1401) cannot
  fire -- the fragment buffer returns only
  messages built by _hs_message, whose header
  and length always parse; probed over
  completed shapes of several sizes.
  DtlsServerCore.tick's by-address sweep
  (1622-1624), listed on the same map, was
  already taken in 237a9c5 after the map's
  HEAD. Done when a coverage run shows the
  taken legs clean.
- A (refill) — installer legs (coverage run
  40189711740): _posix_uid's no-getuid answer,
  _path_exists' raising check, a fresh config
  with the setup module unimportable under
  both spellings, and the host install gate's
  refusal on the one-home and legacy layouts
  — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  InstallSmallLegsTest (test_install_edges.py).
  Done when a coverage run shows the taken
  legs clean.
- A (refill) — watcher, decoder, pipe and
  baseline legs (coverage run 40189711740):
  job-watcher's empty-history skip, softflowd's
  zero-length template and short IPFIX answers,
  the file transport's main loop pass (jobs and
  results scans, plus a failed pass logged not
  fatal), cert-sentinel's answering TLS target
  — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  EmptyRunsJobLegTest
  (test_job_watcher_main.py),
  DecodeEmptyLegsTest (test_softflowd_feed.py),
  FileMainLoopLegTest
  (test_transport_shells.py),
  ReadLiveTlsTargetLegTest
  (test_cert_sentinel.py). Recorded without a
  take: detection update_baseline line 160
  cannot fire -- the loader assigns the loaded
  value only when it is a dict and the starting
  value is a dict, so the baseline is a dict at
  that line on every path (probed with list,
  string, number and null baseline files under
  the full detection suite; the line stays
  missing while all around it runs); and its
  O_NOFOLLOW / O_BINARY flag bodies (198 / 200)
  are a platform-mirror pair -- each runs only
  where the attribute exists, and each map
  shows the other platform's line covered.
  Done when a coverage run shows the taken
  legs clean.
- A (refill) — feed and watch main legs
  (coverage run 40189711740): zeek-feed's and
  osquery-feed's tunables guards and
  undeliverable answers, crash-watch's and
  airwaves' partial deliveries, airwaves'
  non-object link clean — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MainDeliveryRefusalLegTest
  (test_zeek_feed.py and
  test_osquery_feed.py),
  MainPartialDeliveryLegTest
  (test_crash_watch.py and test_airwaves.py).
  Done when a coverage run shows the taken
  legs clean.
- A (refill) — sense legs (coverage run
  40189711740): service-watch's flap reset and
  partial delivery, sky-watcher's dead-rate
  answer, tripwire's path-part exclusion,
  usb-arrivals' twin collapse, cert-sentinel's
  missing decoder, failed-login's impossible
  ISO date, latency-post's tunables guard —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FlapResetAndPartialDeliveryTest
  (test_service_watch.py),
  TimeToVisibleOmegaLegTest
  (test_sky_watcher.py),
  ExcludedPartMatchLegTest (test_tripwire.py),
  TwinDevicesLegTest (test_usb_arrivals.py),
  ReadCertFileNoDecoderLegTest
  (test_cert_sentinel.py),
  ParseEventBadIsoLegTest
  (test_failed_login_watch.py),
  ReadLiveTunablesLegTest (test_latency_post.py).
  Recorded without a take: sky-watcher
  sun_elevation_deg's hour-angle wrap (231)
  cannot fire -- the true solar time is taken
  mod 1440, so the angle is never below -180.
  Done when a coverage run shows the taken
  legs clean.
- A (refill) — DTLS, OAuth and NATS small legs
  (coverage run 40189711740): the server
  core's by-address tick sweep, the pipe's
  floor-check skip and refused send, the
  consent server's silent error, the token
  store's flag line, the NATS token-only URL,
  closed-server read and ping, and the silent
  default log — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsServerTickSweepTest and
  DtlsPipeSmallLegsTest (test_dtls.py),
  OAuthSmallLegsTest (test_oauth_store.py),
  NatsSmallLegsTest (test_transports.py).
  Recorded without a take: the email pipe's
  _subject_body fallthrough (line 61) cannot
  be produced through the stdlib parser on
  this platform -- every parsed shape decodes
  to bytes; the line guards other parser
  behaviors. Done when a coverage run shows
  the taken legs clean.
- A (refill) — board, platform card, learning,
  review and registry small legs (coverage run
  40189711740): board.set_logger's pair and
  no-op, platform_interpreter's Windows branch,
  tier_of's unset tier, learning._boolish's
  fallthrough, _trim_locked's replacement
  write, parse_review_patterns' bad id,
  confval.port's own line, defaulted_keys'
  non-object guard, and sandbox
  interpreter_binds' relative skip — taken
  2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  BoardSetLoggerLegsTest (test_board.py),
  PlatformCardLegsTest (test_platformcard.py),
  LearningSmallLegsTest (test_oracle_learning.py),
  ReviewPatternIdLegTest (test_review.py),
  ConfvalPortAndDefaultedLegsTest
  (test_defaults_table_hunt.py), and
  InterpreterBindsRelativeLegTest
  (test_confinement.py). Done when a coverage
  run shows them clean.
- A (refill) — extsources small legs, second
  batch (coverage run 40189711740): _regex and
  parse_declaration guards, the https-only
  redirect pass-through, _commit_for's non-SHA
  refusal, _safe_member's portable shapes,
  _strip_top's split answer, load_states'
  unusable names, _entry_line's branch naming,
  is_withheld's plain paths — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ExtsourcesSmallLegs2Test in
  runner/tests/test_extension_sources.py.
  Recorded without a take: _clean_rel_path's
  empty-parts raise (278-279) cannot fire --
  the only values that would empty the parts
  are rejected by the guards above it. Done
  when a coverage run shows the taken legs
  clean.
- A (refill) — send_job and send_dtls guards
  (coverage run 40189711740): the secret pattern
  and presence refusals, sign_payload's
  non-object refusal, _extract_signed's
  malformed tail, _object_start's missing
  object, repair_line's non-object, the board
  commands' reply_to member, and _build_body's
  key_id member — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SendJobGuardLegsTest in
  runner/tests/test_send_job_verify.py and
  BuildBodyKeyIdTest in
  runner/tests/test_send_dtls_main.py. The
  same map's send_dtls main and _pump lines
  are covered locally by the full in-process
  suite (measurement artifact family). Done
  when a coverage run shows the taken legs
  clean.
- A (refill) — protocol_v2 and extensions legs
  (coverage run 40189711740): _remember_other's
  blank answer, store_answer's temp-cleanup
  swallow, _parse_upstream's non-object block,
  send_local_signal's shutdown swallow — taken
  2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RememberOtherLegsTest in
  runner/tests/test_protocol_v2_messages.py
  and UpstreamAndSignalLegsTest in
  runner/tests/test_extensions.py. Recorded
  without takes: should_ask's non-dict guard
  (173-174) cannot fire -- enabled() on the
  line above already requires a dict -- and
  sign_envelope's brace check (441) cannot
  fire -- a serialized object always closes
  with the brace. Done when a coverage run
  shows the taken legs clean.
- A (refill) — wire guards (coverage run
  40189711740): jobcrypto's non-string secret,
  hkdf zero salt, is_envelope non-object and
  encrypt_body non-string refusals, and
  verify.check_policy_constraints' non-string
  arg skip — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  CryptoGuardLegsTest in
  runner/tests/test_jobcrypto.py and
  PolicyArgsSkipLegTest in
  runner/tests/test_v31_verify.py. Recorded
  without takes: verify.audience_allows'
  module-absent return (661-662) is subsumed
  by check_audience's own absent-module guard
  on the same global, and verify_body_keyed's
  non-ValueError wrap (725-726) cannot be
  produced through the signer seam (bodies the
  signer can serialize parse, or fail as
  ValueError, at every probed depth). Done
  when a coverage run shows the taken legs
  clean.
- A (refill) — runner.py legs, sixth batch
  (coverage run 40189711740): oracle_window's
  non-dict config and deterministic banner,
  oracle_cli's mid-turn Ctrl-C, do_POST's
  deterministic answer over a real loopback
  server, and poll_once's supervisor-check
  failure — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs6Test in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — runner.py legs, fifth batch
  (coverage run 40189711740): _v2_leave_unseen's
  non-string id and set cap, _v2_before_execute's
  absent-module return and determination
  segment, run_inspect's sources branch without
  the module — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs5Test in
  runner/tests/test_runner_last_edges.py.
  Recorded without a take: answer_queries'
  second exec_result normalization (2337-2338)
  is unreachable by construction -- the first
  check at 2325-2326 already replaced any
  non-dict with {}. Done when a coverage run
  shows the taken legs clean.
- A (refill) — runner.py legs, fourth batch
  (coverage run 40189711740):
  _ingest_local_envelope's catch-all,
  _local_watch's guard and per-watch swallow,
  _transports_arg's empty refusals, and
  _append_security_event's rollover open under
  the Windows flag line — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs4Test in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — runner.py legs, third batch
  (coverage run 40189711740): _admit_object's
  non-string id, malformed envelope and
  envelope/body key mismatch (real signed
  bodies throughout), _learning_reconcile's
  disabled gates, _learning_model_candidate's
  unparseable reply and failed candidate write,
  _wake_gate_decide's non-record and
  unconvertible clock, _write_seen_unlocked's
  cleanup swallow — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs3Test in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — runner.py fail-soft legs, second
  batch (coverage run 40189711740):
  _extension_source_targets when transport
  discovery raises, _extension_sources_tick's
  guard and deepcopy fallback, _oracle_host_ok
  when urlparse fails, _take_body's negative
  length, update_llama_from_config's failed
  pull — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegs2Test in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — runner.py fail-soft legs (coverage
  run 40189711740): the withheld-path helpers
  when the sources module raises, _staged_dest
  when realpath fails, download's transient
  re-raise and bad-URL refusal, save_retained's
  close-failure swallow, _append_brief's write
  swallow, the brief thread's opinion swallow,
  _file_fresh_lines' state-write swallow,
  _tail_marked's vanished file, _extension_registry's
  load failure and _extension_sources_note's
  raise — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunnerFailSoftLegsTest in
  runner/tests/test_runner_last_edges.py. Done
  when a coverage run shows them clean.
- A (refill) — `runner/cloud/send_dtls.py`
  `_wait_for`'s dead-peer and dry-pump exits
  (coverage run 40189711740: lines 132, 134) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  WaitForLegsTest in
  runner/tests/test_send_dtls_main.py. The same
  map's main lines 174-175 are a measurement
  artifact: the full in-process suite covers
  them locally (they are the --kind argument
  declarations, executed by every main call);
  no take. Done when a coverage run shows
  _wait_for clean.
- A (refill) — job-fuzz state caps and quiet legs
  (coverage run 40189711740): the energy, buckets
  and filed caps trimming to the most valuable,
  _load_quiet with no load average to read,
  _prune_archive passing over an unremovable
  file, and _minimize_variant passing over an
  unwritable archive — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  CleanStateCapLegsTest in
  runner/tests/test_job_fuzz.py. Done when a
  coverage run shows them clean.
- A (refill) — `runner/ops/extsources.py` small
  legs (2 lines each never run, coverage run
  40189711740): Fetcher.get_json's not-JSON
  refusal, resolve_github's unresolvable named
  ref and missing default branch, remote_urls'
  archive and unsafe-name shapes, owner_policy's
  bad per-extension overrides,
  manifest_upstream_of's non-path and invalid
  block, _clean_targets' unusable entries —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ExtsourcesSmallLegsTest in
  runner/tests/test_extension_sources.py. Done
  when a coverage run shows them clean.
- A (refill) — four more two-line legs (coverage
  run 40189711740): `sysmon_feed._parse_xml_event`
  broken-inside, `softflowd_feed`
  `_parse_v9_templates` truncated fields,
  `training_watch._run_alive` cannot-run, and the
  NATS client's expired deadline, refused send and
  refused close — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ParseXmlBrokenInsideTest
  (runner/tests/test_sysmon_feed.py),
  DecodeDamageLegsTest (test_softflowd_feed.py),
  RunAliveLegsTest (test_training_watch.py), and
  a case in NatsNextMessageLegsTest
  (test_transports.py). Recorded without a take:
  softflowd decode_datagram's except (401-402)
  sits behind both decoders' length guards;
  dri send_telegram's second dumps failure
  (504-505) cannot fire once both fields are
  text; dri's fused-score excepts and
  training-watch's loss float except sit behind
  helpers that are total by design
  (alert_score sanitizes its weight; the loss
  pattern only captures float-shaped text, and
  float() of an over-range literal is inf, not an
  error). Done when a coverage run shows the
  taken legs clean.
- A (refill) — `runner/guard/confval.py::_parse`
  type legs and `runner/wire/protocol_v2.py::`
  `_other_answers` unsafe-id leg (2 lines each
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ConfvalParseLegsTest in
  runner/tests/test_defaults_table_hunt.py (a
  boolean is never a number; a number passes
  through) and OtherAnswersLegsTest in
  runner/tests/test_protocol_v2_messages.py (an
  unsafe question id reads empty). Recorded
  without a take: dtlsproto.x25519's final
  conditional swap (186-187) is unreachable by
  construction -- the ladder's last processed bit
  is the clamped scalar's bit 0, which clamping
  always clears, so the swap is always false
  (verified by coverage over crafted and RFC
  scalars); transports'
  discover_transport_extensions lines 255/260 are
  continuation lines of the refusal message the
  ManifestContractTest refusal cases already
  assert -- a measurement artifact, not a gap.
  Done when a coverage run shows the taken legs
  clean.
- A (refill) — six two-line legs (coverage run
  40189711740): `job_watcher._record_observation`
  size/timestamp, `personal_docs`
  per-entry stat failure, `board._runner_logger`
  bound/no-op, `opinion._shape_fits` posix and
  unknown shapes, `resource_sentinel`
  `_read_process_count` without /proc, and
  `auditreport._entry_ts` unparsable — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  JobWatcherRecordLegsTest
  (runner/tests/test_watchers.py),
  RunnerLoggerLegsTest (test_board.py),
  ShapeFitsLegsTest (test_oracle_opinion.py),
  ProcessCountLegsTest (test_resource_sentinel.py),
  EntryTsLegsTest (test_audit_report.py), and a
  case in test_personal_docs.py. Done when a
  coverage run shows them clean.
- A (refill) — `log_sentinel._prev_inode` and
  `_compiled_groups`, `training_watch._read_gpu`,
  and the `backup_freshness` / `crash_watch`
  `read_live` mid-scan races (2 lines each never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PrevInodeAndGroupsLegsTest in
  runner/tests/test_log_sentinel.py (a corrupt
  stored inode reads as unknown; an un-compilable
  group is left out), GpuReadLegsTest in
  runner/tests/test_training_watch.py (an
  unparsable nvidia-smi line yields to the next),
  and MidScanVanishTest in
  runner/tests/test_backup_freshness.py and
  runner/tests/test_crash_watch.py (a file gone
  before its stat is passed over). Recorded
  without a take: senses.load_alerts' per-record
  scoring guard (426-427) and pi_health
  _read_throttled's int guard (203-204) are
  unreachable by construction -- the first sits
  behind isinstance checks on plain JSON dicts,
  the second behind a hex-only pattern (base 16
  is exempt from the conversion cap). Done when
  a coverage run shows the taken legs clean.
- Q29 FILED by Muse 2026-10-25 — the Q28 defect
  survives in airwaves' other two signal
  conversions (parse_iw_link ~327, parse_nmcli
  ~230): OverflowError escapes both parsers on a
  huge-digit signal, killing the sense's cycle.
  Two failing-by-design probes in
  runner/tests/test_airwaves.py pin the Q28
  contract (the reading survives, signal None).
  Claude's lane to fix; the probes are the
  verification when it lands. FIXED by Claude
  (both parsers' guards widened — verified in the
  local full-suite run at 9a01d0a: 3,571 tests, 0
  failures). Q29 CLOSED by evidence 2026-10-25.
- A (refill) — `runner/wire/verify.py` fallback
  legs, `runner/guard/sandbox.py::`
  `_userns_restricted` read legs and
  `runner/wire/mailbox.py::_xoauth2_raw` (2 lines
  each never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  VerifyFallbackLegsTest in
  runner/tests/test_blackbox_findings.py (a
  control-inserted body verifies against the
  cleaned form; a body nested past the
  interpreter's limit reports invalid JSON; the
  audience check binds nothing when the security
  layer is absent or the payload is not an
  object), UsernsRestrictedLegsTest in
  runner/tests/test_confinement.py (the sysctl
  read, and its absence read as not restricted),
  and XOAuth2RawTest in
  runner/tests/test_email_pipe_coverage.py.
  Residue: verify_body's and verify_body_keyed's
  non-object guards (lines 191 and 703) are
  unreachable by construction -- the extractor
  only returns brace-balanced spans opening with
  "{", which parse to an object or not at all.
  Done when a coverage run shows the legs clean.
- A (refill) —
  `runner/transport_extensions/dtls/__main__.py::`
  `DtlsPipe._pump_results` delivery legs and
  `runner/extensions/release-drop/release_drop.py`
  `::read_live` mid-scan races (4 lines each never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsPumpResultsLegsTest in
  runner/tests/test_dtls.py (a gone session's
  result is acked into done with the reason
  logged; a body without a trailing newline gets
  one on the wire) and MidScanVanishTest in
  runner/tests/test_release_drop.py (a file gone
  before its stat, or unreadable at its hash, is
  passed over and the pass still answers). Done
  when a coverage run shows both clean.
- A (refill) —
  `runner/transport_extensions/nats/__main__.py::`
  `NatsClient.next_message` control lines and
  `_read_exact` mid-message timeout (4 lines each
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NatsNextMessageLegsTest in
  runner/tests/test_transports.py, over a scripted
  socket: a PING is PONGed and skipped, PONG/+OK
  are skipped, an -ERR raises naming the server's
  text, and a payload that stops mid-message is a
  timeout. Done when a coverage run shows both
  clean.
- A (refill) —
  `runner/extensions/softflowd-feed/softflowd_feed.py`
  `::collect_flows` window and close legs (3 lines
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  CollectFlowsClockTest in
  runner/tests/test_softflowd_feed.py: the pass
  ends when the window closes at the top of the
  loop, and a socket that refuses to close is
  still a quiet empty pass. Done when a coverage
  run shows the function clean.
- A (refill) — `runner/runner.py::`
  `make_oracle_server.Handler.do_POST`
  deterministic leg (3 lines never run, coverage
  run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DeterministicAskTest in
  runner/tests/test_oracle_chat.py: in
  deterministic mode an /ask question is answered
  from the box's records (the Pi Light answer) and
  no model call is attempted. Residue: the
  json.dumps fallback (10141-10142) is unreachable
  by construction -- the payload is rebuilt only
  from isinstance-str-checked values. Done when a
  coverage run shows the leg clean.
- A (refill) — `runner/wire/mailbox.py::send_mail`
  unbuildable leg and `runner/oracle/resources.py`
  `::check_resources` corrupt-state legs (3 lines
  each never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SendMailUnbuildableTest in
  runner/tests/test_email_pipe_coverage.py (a
  newline recipient is logged as not built and
  never sent) and CorruptLastAlertTest in
  runner/tests/test_resources.py (a non-numeric
  last-alert stamp reads as never-alerted; a
  disabled block with a valid threshold returns
  before any state -- the older disabled case
  pairs False with threshold 0.0, which the parser
  refuses first). Done when a coverage run shows
  both clean.
- A (refill) — `runner/wire/platformcard.py::`
  `os_family` non-host legs and
  `runner/ops/extsources.py::load_declaration`
  quiet legs (3 lines each never run, coverage run
  40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  OsFamilyLegsTest in
  runner/tests/test_platformcard.py (win*/darwin/
  unrecognized platform names under a patched
  sys.platform) and LoadDeclarationLegsTest in
  runner/tests/test_extension_sources.py (a
  non-path declares nothing; an unreadable
  declaration file returns its problem). Done when
  a coverage run shows both clean.
- A (refill) — `runner/runner.py::`
  `handle_query_mail` bad-envelope leg (3 lines
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  QueryAudienceTest's broken-envelope case in
  runner/tests/test_audience.py: a query whose
  envelope verifies but cannot be decrypted is
  marked seen, never answered, and does not break
  the poll. Rules refreshed 2026-10-25 05:41 PDT
  (compaction reset; repo AGENTS.md rules 7-9,
  standing orders, open questions re-read). Done
  when a coverage run shows the branch clean.
- A (refill) — `runner/runner.py::`
  `_extension_sources_policy` (4 lines never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ExtensionSourcesPolicyTest in
  runner/tests/test_extension_sources.py: with the
  sources module missing the policy is None, and a
  newly appearing problem is recorded and
  announced exactly once with its consequence.
  Done when a coverage run shows the function
  clean.
- A (refill) — `runner/wire/jobcrypto.py::`
  `decrypt_body` defect legs (3 lines never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DecryptBodyDefectsTest in
  runner/tests/test_jobcrypto.py: a ciphertext
  truncated below its tag and a plaintext that
  decrypts to non-UTF-8 bytes each raise
  JobCryptoError naming the defect. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/guard/defaulted.py::`
  `default_for` and `is_defaulted` enum legs
  (3 lines each never run, coverage run
  40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DefaultedEnumLegsTest in
  runner/tests/test_defaults_table_hunt.py: the
  one enum key's default answers, an unusable
  value for it is defaulted, a usable one is not,
  and an unknown key has no default and is never
  defaulted. Done when a coverage run shows both
  clean.
- A (refill) — `runner/extensions/job-watcher/`
  `job_watcher.py::read_live` listing legs and
  `_clean_state` (4 lines each never run, coverage
  run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  JobWatcherReadLiveTest and JobWatcherCleanStateTest
  drives in runner/tests/test_watchers.py: an
  unlistable store reads empty, an unstattable
  record is skipped, the seen cap keeps the newest
  entries, and misshapen job entries drop or repair.
  Done when a coverage run shows both clean.
- A (refill) — `runner/runner.py::`
  `_serve_local_signals` isolation legs and
  `_report_extension_sources` outcomes (4 lines
  each never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ServeLoopIsolationTest in
  runner/tests/test_local_signals.py (a raising
  handler and a failing close are both swallowed
  and the loop accepts again) and
  ReportExtensionSourcesTest in
  runner/tests/test_extension_sources.py (missing
  module and invalid policy are silent; on and off
  each say their one line). Done when a coverage
  run shows both clean.
- A (refill) — `runner/runner.py::`
  `_release_saved_claims` failure legs (4 lines
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReleaseSavedClaimsEdgesTest in
  runner/tests/test_protocol_v2_messages.py: an
  unreadable claim file (a directory) and a claim
  whose removal fails are both passed over while
  the releasable claim is released and the unseen
  claim is left alone. Done when a coverage run
  shows the function clean.
- A (refill) — `runner/wire/protocol_v2.py::`
  `_publish_answer` race legs (4 lines never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PublishAnswerRaceTest in
  runner/tests/test_protocol_v2_messages.py: a
  slot that vanishes between the lost link and the
  check is retried and won, and a move-aside that
  keeps failing gives up after its attempts with
  the bad file untouched. Done when a coverage run
  shows the function clean.
- A (refill) — `runner/extensions/sky-watcher/`
  `sky_watcher.py::fetch_position` (4 lines never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  one FeedSampleTest drive in
  runner/tests/test_sky_watcher.py with the
  transport faked: the request goes to the given
  URL with the watcher's user agent and the
  documented timeout, and the parsed sample is
  sample_from_feed's. Done when a coverage run
  shows the function clean.
- A (refill) — `runner/ops/install.py::`
  `gather_host_facts` marker legs and
  `_warn_personal_documents` (4 lines each never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  GatherAndGateTests drives in
  runner/tests/test_hostclass.py through the
  function's own probe seams: a marker file and an
  os-release id each name webOS, an Android
  environment names android, and a Pi identified
  by cpuinfo alone still decides as a Pi; and the
  personal-documents warning swallows a missing
  module whole. Done when a coverage run shows
  both clean.
- A (refill) — `runner/ops/install.py::host_decision`
  (4 lines never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — four
  HostDecisionTests drives in
  runner/tests/test_hostclass.py: non-dict facts
  read as no facts; a Docker host with a USB
  accelerator notes both facts; an ARM board with
  one notes both; plain Linux with one is the
  linux case whose note is the accelerator warning
  alone. Done when a coverage run shows the
  function clean.
- A (refill) — `runner/ops/extsources.py::`
  `_local_files` and `_tree_bytes` (4 lines each
  never run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LocalFilesEdgesTest in
  runner/tests/test_extension_sources.py: a symlink
  source yields nothing, the visit budget stops the
  walk mid-tree, an unsizable file is skipped, and
  the byte counter answers 0 for an unsizable
  non-directory and skips an unsizable member.
  Done when a coverage run shows both clean.
- A (refill) — `runner/ops/extsources.py::`
  `extract_archive`'s write() legs (4 lines never
  run, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  two ExtractTest drives in
  runner/tests/test_extension_sources.py: a member
  under a symlink planted in the destination is
  skipped by the escape check while its sibling
  extracts (the names themselves are sanitized
  upstream, so the planted link is the check's
  live case), and a member whose target is already
  a directory is counted and skipped. Done when a
  coverage run shows write() clean.
- A (refill) — `runner/ops/extsources.py::`
  `oracle_note` (4 lines never run, coverage run
  40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  OracleNoteEdgesTest in
  runner/tests/test_extension_sources.py: an
  unloadable state store yields the empty note
  (the function never raises), and more provided
  sources than the line budget fold into the
  counted trailer. Done when a coverage run shows
  the function clean.
- A (refill) — `runner/ops/auditreport.py::`
  `_is_dangerous` fallback (4 lines never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DangerousFallbackTest in
  runner/tests/test_audit_report.py: when the
  security module's own check raises, the answer
  falls back to its name list (a listed name in
  any case is dangerous; an unlisted or non-string
  name is not). Done when a coverage run shows
  the function clean.
- A (refill) — `runner/extensions/airwaves/`
  `airwaves.py::parse_iw_scan` conversion guards
  (4 lines never run, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the
  channel guard pinned passing (a digit string
  past the conversion cap degrades to None), and
  the signal guard became a FINDING, filed as
  Q28: it cannot fire (float() of a digits-only
  match returns inf, never ValueError), and the
  real failure -- int(inf) OverflowError -- escapes
  the parser, read_live, and main's handlers. The
  probe is on main failing by design in the
  four-part format; the item is done as filed.
- A (refill) — `runner/extensions/job-fuzz/`
  `job_fuzz.py::_num`, `_mut_unicode_edge`,
  `_mut_trailing_blank` (4 lines each never run,
  coverage run 40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — three
  MutatorTest drives in runner/tests/test_job_fuzz.py:
  the unicode-edge variant appends exactly its edge
  line and nothing else; trailing blanks are the
  seed plus one to three newlines and an empty seed
  declines; the number renderer prints ints as
  themselves, whole floats as ints, fractions
  compactly. Done when a coverage run shows all
  three clean.
- A (refill) — `runner/ops/posture.py::`
  `_windows_file_restricted` deep branches (6 lines
  missing on Windows, none on Linux, coverage run
  40189711740) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the full
  drive already existed inside a POSIX-gated test
  whose skip took the ACL leg down on the one
  platform the function exists for;
  WindowsAclBranchesTest in
  runner/tests/test_posture_gaps.py runs the same
  _Api fake with no platform gate: ACL-info failure
  degrades to None, an empty ACL is restricted, six
  ACEs walk the failure/null/type/mask branches to
  the broad-read hit. Done when a coverage run
  shows the six lines run on Windows too.
- A (refill) — the tailing senses' `read_new_events`
  open-failure leg, one 4-line gap in each of seven
  senses (coverage run 40189711740, both
  platforms): zeek-feed, failed-login-watch,
  falco-feed, osquery-feed, suricata-feed,
  sysmon-feed, wazuh-feed — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — one
  test_an_unreadable_file_keeps_its_entry per
  sense's ReaderTest: a path that stats fine but
  cannot be opened (a directory is the
  deterministic stand-in for the stat-then-open
  race) yields no events and keeps its previous
  reader entry, sysmon's partial line included —
  the docstrings' "missing or unreadable" clause,
  whose missing half was already pinned. Done
  when a coverage run shows all seven legs run.
- A (refill) — `runner/wire/transports.py::`
  `service_channel` (4 lines never run, both
  platforms, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  and the take became a FINDING, filed as Q25: the
  never-run lines are the rollback-on-failed-ack
  branch, and they never run because
  IncomingMessage.ack() discards the wrapped ack's
  return, so `acked is False` is unreachable and a
  refused ack never drops the seen-set entry the
  docstring promises. The probe
  (ChannelEdgeTest.test_a_failed_ack_must_roll_
  back_probe in runner/tests/test_transports.py)
  is on main failing by design in the four-part
  format; it goes green when the ack returns its
  result (Claude's lane). The item is done as
  filed; the branch's coverage follows the fix.
- A (refill) — `runner/oracle/remediation.py::`
  `enforce_quarantine_bounds` Windows residue
  (6 lines, coverage run 40189711740; the function
  is fully run on Linux, and the Windows leg's own
  fixtures cannot build these states) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  three QuarantineTest drives in
  runner/tests/test_remediation.py with stubs that
  run on both platforms: an unstatable entry sorts
  as epoch 0 and is archived first; a taken archive
  name suffixes -2, -3 rather than clobbering; a
  failed move stops the pass, keeps the entry, and
  does not raise. Done when a coverage run shows
  the six lines run on Windows too. With it, a
  disposition under the skip rule:
  `sandbox.build_bwrap_command` (6 lines, Windows)
  builds a Linux bubblewrap argv and cannot apply
  on Windows — platform-inapplicable there, covered
  on Linux.
- A (refill) — `runner/runner.py::snapshot_outside`
  realpath fallbacks (4 lines never run, both
  platforms, coverage run 40189711740) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SnapshotRealpathFallbackTest in
  runner/tests/test_confinement.py: a realpath
  failure on the workspace, and one on a directory
  mid-walk, each fall back to the absolute path and
  the snapshot still lands (the outside file in,
  the workspace's own files out). Done when a
  coverage run shows the four lines run.
- A (refill) — `runner/ops/auditreport.py` import
  seam (the fallback block, 5 lines never run on
  either platform, coverage run 40189711740) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ImportSeamTest in runner/tests/test_audit_report.py:
  with the package import blocked, the script-mode
  sibling answers; with neither importable the
  module still loads and its readers answer empty.
  Done when a coverage run shows the block clean.
  With it, two dispositions under the queue-A skip
  rule, from the same map: `resources._mem_fraction`
  (8 lines, Windows) is the /proc/meminfo body --
  platform-inapplicable on Windows (no /proc there;
  the None return runs), covered on Linux;
  `posture._check_file_perms` (8 lines, Windows) is
  the POSIX stat body behind the function's own
  os.name return -- platform-inapplicable on
  Windows, covered on Linux.
- A (refill) — `runner/extensions/softflowd-feed/`
  `softflowd_feed.py::_flow_from_values` and
  `_parse_ipfix_templates` (5 lines each never run,
  coverage run 40189711740, the newest completed
  run; the CI queue is backlogged a dozen deep, so
  re-ranking works from that map) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DecoderEdgesTest in
  runner/tests/test_softflowd_feed.py: an address
  falls back to its IPv6 field when no IPv4 field
  is present; a flow with only its LAST switched
  stamp anchors both ends on it; a template
  truncated mid-field or mid enterprise number is
  not recorded at all; a variable-length field
  records its template tainted (a clean field is
  the untainted control). Done when a coverage run
  shows both clean.
- rules refreshed 2026-10-25 05:22 PDT, on the
  owner's word ("update your orders"): pulled
  through 6853314. Two answers change the queue.
  Q22 is answered in f4e2378 (release 3.12.66):
  the mutation signal's blindness was mutmut's
  coverage pass dying on the archived probes'
  shared basename, not the stats phase; the fix
  ignores the archive folders for pytest and adds
  a mutation floor that fails a collapsed signal.
  The D4 triage re-runs on the first tag run after
  that release and takes the survivors then; no
  tag exists yet. Q23 is applied in the same
  commit by deletion -- the three uncalled
  _is_number copies are out of aide-feed,
  usb-arrivals and wire-arrivals; the entry's
  Answer line is still blank in the questions
  file, Claude's bookkeeping to finish. S and R
  are filled and await their switch-proofs
  verdicts (6853314 lets a running leg finish
  instead of cancelling it); A and D resume
  behind them.
- Q27 CLOSED by evidence, verified by Muse
  2026-10-25: switch-proofs run 40194182584 (HEAD
  9873ba3, carrying the fb56cfd lock) finished all
  three legs green (25/25, 27/27, 16/16), and the
  Windows leg's report -- downloaded and read by
  Muse, not taken on report -- shows
  R2.audit_rollover PROVEN on the locked writer.
  Grok's Q26 note records the same run.
- Q25, Q27, Q28 ANSWERED AND APPLIED by Claude
  in fb56cfd (release 3.12.67; 3.12.66 was built,
  not tagged -- its content ships in .67). Q25:
  IncomingMessage.ack() returns the result; the
  probe is green (Muse verified locally; Claude
  corrected the probe's outbox count, which had
  counted the outbox's done/ folder -- a test bug,
  owned). Q27: one re-entrant lock per process
  around the audit bound check, append and counts
  bump; Muse's R2 passes locally, and the Windows
  leg of the next finished switch-proofs run is
  the verdict. Q28: the airwaves signal guard now
  catches (OverflowError, ValueError) as proposed;
  the probe is green (Muse verified locally). The
  .67 stamp and the D4 mutation triage both wait
  on the .67 tag.
- S/R VERDICTS, switch-proofs run 40192518684
  (the 3.12.66 release commit; Grok's watch, Q26,
  reported the finish): Linux 25 of 25 proven,
  root 27 of 27, Windows 15 of 16. Queue S is
  DONE: every switch proven on its leg, the four
  walls on Linux, the drops on root, the templates
  and both Oracle entries everywhere they apply.
  Queue R is DONE as proven for R1 (root), R3 and
  R4 (all legs), and DONE AS FILED for
  R2.audit_rollover: failed on Windows -- a
  concurrent audit append lost one entry whole,
  the Windows append-emulation overwrite; filed
  as Q27 with the run's report as evidence. The
  proof stays red on that leg until Claude's fix
  lands; nothing in S or R remains open for the
  campaign to write.
- R — roster R1.two_jobs, R2.audit_rollover,
  R3.seen_set, R4.config_write — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  runner/tests/test_enforce_races.py, every race
  driven with real threads and a barrier and
  asserting the security outcome: two jobs on one
  barrier each keep their own chowned workdir and
  its files (root leg), and two sandboxes share no
  /work with both decisions whole in the audit log
  (bwrap leg); a rollover raced by two writers
  loses and splits no entry over 25 rounds (the
  live and rolled files together hold every id
  exactly once, every line parsing); a replayed id
  is rejected on both orderings around a fresh job
  while two copies of a fresh job run it once; a
  config write plus the real hot reload landing
  provably mid-job moves the hot key only -- the
  security block is the identical object afterwards
  and the next job's gate still denies by the mode
  in force. The roster entries list them. Done
  when the switch-proofs workflow is green with
  all four proven on their legs.
- S — roster ORACLE.no_widening — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NoWideningTest in
  runner/tests/test_oracle_no_widening.py, through
  the real intake with a fake model throughout: a
  policy_env denial in enforce mode lands with the
  opinion machinery armed and the opinion is never
  formed (the gate is upstream of it); a repairable
  job whose repair would move it out of its pinned
  key's allowed_interpreters is refused on
  re-judgment and never runs, and runs repaired
  under a policy that allows the default (control);
  a model note saying "do not run this job" is
  attached to a clean job's result verbatim and the
  job runs exactly as it would have. The roster
  entry lists it. Done when the switch-proofs
  workflow is green with the entry proven.
- S — roster M7.templates — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the
  module already carried TemplateTest (existence,
  complete rendering, path consistency, the
  installer's unit mirrored, --help silent); the
  missing half was the parse: TemplateParseTest in
  runner/tests/test_hardening_templates.py renders
  each template and parses it in its grammar's
  shape (the unit through a real ini parser with
  the ExecStart argv equal to the installer's; the
  AppArmor block balanced with every rule
  comma-terminated and the three grants exact; the
  SELinux module's allows naming only declared
  types), and pins the README's claim that
  install.py never references the templates. The
  roster entry lists both classes. Done when the
  switch-proofs workflow is green with the entry
  proven.
- S — roster M6.wall.network, M6.wall.home,
  M6.wall.usr, M6.wall.work (the four sandbox walls
  as separate cases, each with its mode-off
  control) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  WallNetworkTest, WallHomeTest, WallUsrTest and
  WallWorkTest in runner/tests/test_confinement.py,
  each driving both modes through execute_job: a
  loopback listener reached with the mode off is
  unreachable in the sandbox; the base dir's marker
  is read off and invisible on; a /usr write is
  blocked on and lands off in a scratch tree; the
  workdir sits at /work with the base root and a
  sibling job's workdir unreachable on, read off.
  The four roster entries list them. Done when the
  switch-proofs Linux leg (bwrap) shows all four
  proven.
- rules refreshed 2026-10-25 05:07 PDT (Q24 read
  with the refresh: queues S and R now come first;
  the queue-A item below was already written when
  the reset landed and is closed out here)
- A (refill) — `runner/extensions/job-fuzz/`
  `job_fuzz.py::_scan_retained` (5 lines never run
  on either platform, coverage run 40189608702) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ScanRetainedEdgesTest in
  runner/tests/test_job_fuzz.py: a store that
  cannot be listed reads as empty; names that are
  not seed files are passed over; a seed that
  vanishes between the listing and its stat is
  skipped while its sibling is still read. The
  function is fully run under that class. Done
  when a coverage run shows it clean.
- rules refreshed 2026-10-25 04:48 PDT
- A (refill) — `runner/ops/extsources.py::`
  `pin_declaration` (5 lines never run on either
  platform, coverage run 40189608702) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PinDeclarationProblemsTest in
  runner/tests/test_extension_sources.py: project
  entries are not pinned; a failed archive
  download is an "archive:" problem on an
  otherwise pinned entry; a failed resolution is
  a problem with no resolved block. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/ops/extsources.py::`
  `_acquire_pass_lock` and `extract_archive` (5
  lines each never run on either platform,
  coverage run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PassLockEdgesTest and ExtractMemberEdgesTest in
  runner/tests/test_extension_sources.py: a lock
  whose age cannot be read is retried then given
  up on, not unlinked blind; an unusable root
  answers None; a free root takes the lock.
  Directory entries, zip and tar, are passed over
  uncounted; a member with no readable stream is
  counted skipped; more members than the cap is
  refused outright. Done when a coverage run
  shows both clean.
- A (refill) — `runner/ops/extsources.py::`
  `Fetcher._read_capped` and `Fetcher.download`
  (5 lines each never run on either platform,
  coverage run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FetcherStreamEdgesTest in
  runner/tests/test_extension_sources.py: a body
  past the cap is refused naming the cap; a read
  failing mid-stream is a SourceError naming the
  read, and a download removes its partial file; a
  close that fails is swallowed by both readers.
  Done when a coverage run shows both clean.
- A (refill) — `runner/transport_extensions/dtls/`
  `__main__.py::DtlsPipe.run_once` (5 lines never
  run on either platform, coverage run 40189608702)
  — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsRunOnceLegsTest in runner/tests/test_dtls.py:
  a dead socket still completes the pass; a receive
  that fails after a ready select drops the
  datagram and sends nothing; the core's tick
  output goes out on the socket. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/runner.py::reload_hot_config`
  (5 lines never run on either platform, coverage
  run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReloadHotConfigEdgesTest in
  runner/tests/test_defaults_table_hunt.py: a
  state that is not a dict reads as fresh and the
  reload proceeds; a config file that cannot be
  statted changes nothing; a hot verbose value
  that is neither a bool nor a string is ignored
  and named while a valid sibling key still
  applies. Done when a coverage run shows the
  function clean.
- A (refill) — `runner/runner.py::handle_board_mail`
  (5 lines never run on either platform, coverage
  run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  BoardMailRejectionsTest in
  runner/tests/test_runner_tail.py: an envelope
  sealed for another task id verifies but does not
  open, and is rejected and recorded as an
  encryption failure, with no ack. The remaining
  two lines, the dispatch's "unknown board kind"
  else, are unreachable by construction -- the
  subject gate admits exactly the four kinds the
  dispatch handles -- and the gate is pinned from
  the outside (a kindless subject is not board
  mail at all). Done when a coverage run shows
  only those two lines left.
- A (refill) — `runner/runner.py::`
  `_ingest_local_envelope_inner` (5 lines never run
  on either platform, coverage run 40189608702) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LocalEnvelopeIssuedAtTest in
  runner/tests/test_sense_delivery.py: a config
  whose secrets cannot be built rejects every
  envelope unread; an issued_at that does not
  parse and one that parses without a timezone
  are each rejected and nothing is stored; a zoned
  issued_at is stored (control). Done when a
  coverage run shows the function clean but the
  smaller tail.
- A (refill) — `runner/runner.py::_v2_hand_off` (5
  lines never run on either platform, coverage run
  40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  Version2HandOffFallbacksTest in
  runner/tests/test_cli_options.py: a transport
  list that cannot be read and a channel write
  that fails each degrade to the ordinary send,
  exactly once; a written channel is not sent
  again (control). Done when a coverage run shows
  the function clean.
- A (refill) — `runner/runner.py::_start_job_monitor`
  (5 lines never run on either platform, coverage
  run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  StartJobMonitorFallbacksTest in
  runner/tests/test_remediation_e2e.py: with the
  remediation module absent there is no monitor; an
  unreadable script and an opinion layer whose
  hints fail each still get a monitor, with no
  declared paths. Done when a coverage run shows
  the function clean.
- A (refill) — `runner/wire/board.py::Board.save`
  (5 lines never run on Linux, coverage run
  40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the two
  flag lines are the platform pair (O_BINARY on
  Linux, O_NOFOLLOW on Windows, each covered where
  it applies); the taken lines are the descriptor
  cleanup, pinned in runner/tests/test_board.py: a
  save failing after its tmp opens closes the
  descriptor, removes the tmp, and leaves the
  previous board untouched, and a failing close is
  swallowed the same way. Done when a coverage run
  shows only the platform line left.
- A (refill) — `runner/wire/mailbox.py::_load_oauth`
  (5 of its 6 lines never run on either platform,
  coverage run 40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LoadOauthSeamTest in runner/tests/test_oauth.py:
  the package import answers first; with it blocked,
  the script-mode fallback module is the one
  returned. Done when a coverage run shows the
  function clean.
- A (refill) — `runner/runner.py::run_variant` (8
  lines never run on either platform, coverage run
  40189608702) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunVariantFallbacksTest in
  runner/tests/test_run_variant.py: an unusable
  timeout reads as the cap itself; a variant with
  no job id runs under the default id; a work dir
  that cannot be created is exit 2, named on
  stderr; a failure in the execution path itself
  is an "error" report, never a raise. The function
  is fully run under that module locally. Done
  when a coverage run shows it clean.
- A (refill) — `runner/oracle/senses.py::`
  `_store_alert_report` (3 lines never run on
  Linux, 6 on Windows, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  StoreAlertReportEdgesTest in
  runner/tests/test_senses.py: with the runner
  module unimportable the script-mode fallback
  stores the record as given; past the stored cap
  the file is rewritten keeping the newest alerts.
  Done when a coverage run shows the function
  clean.
- A (refill) — `runner/ops/install.py::`
  `_usb_accelerators` (6 lines never run on either
  platform, coverage run 40187685363; CI machines
  have no accelerator plugged in, so the scan never
  looped) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  UsbAcceleratorsTest in
  runner/tests/test_hostclass.py: an unlistable
  sysfs answers none; known vendor ids name their
  kind once each, in device order, and an unknown
  id is not an accelerator. Done when a coverage
  run shows the function clean.
- A (refill) — `runner/extensions/tripwire/`
  `tripwire.py::read_live` (6 lines never run on
  either platform, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReaderRaceTest in runner/tests/test_tripwire.py:
  a root that raises when probed reads as empty; a
  file that vanishes before its lstat and a file
  that cannot be hashed are each skipped while the
  rest of the tree is read. Done when a coverage
  run shows the function clean but the smaller
  tail.
- A (refill) — `runner/extensions/release-drop/`
  `release_drop.py::main` (6 lines never run on
  either platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MainDeliveryTest in
  runner/tests/test_release_drop.py: a full local
  delivery writes the state and files one envelope;
  delivery not set up is exit 2; a short delivery is
  exit 2 with the state unwritten; an unwritable
  state file is exit 2 with the reason printed.
  Done when a coverage run shows the function
  clean.
- A (refill) — `runner/ops/extsources.py::`
  `_fetch_archive` (6 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FetchArchiveFailuresTest in
  runner/tests/test_extension_sources.py: a spent
  budget refuses before any download (status
  skipped); a download failure passes through as
  itself; an archive that unpacks past the
  extraction cap passes through, unless what is
  left of the budget cut it short, in which case
  the failure is the budget's (status skipped).
  Done when a coverage run shows the function
  clean.
- A (refill) — `runner/ops/extsources.py::Fetcher._open`
  (6 lines never run on either platform, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FetcherOpenEdgesTest in
  runner/tests/test_extension_sources.py: a
  SourceError from the opener passes through
  unchanged; an HTTP error is closed even when
  closing fails, and 403/429 are named as rate
  limiting; a transport OSError becomes "cannot
  fetch". Done when a coverage run shows the
  function clean.
- rules refreshed 2026-10-25 04:24 PDT
- A (refill) — `runner/ops/extsources.py::provision`
  and `_run_pass` (6 lines each never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ProvisionFailureTest in
  runner/tests/test_extension_sources.py: bad
  arguments answer the bare report; an uncreatable
  state root and an unexpected pass failure are
  recorded problems, never raises; an installed-code
  failure is logged and the pass goes on; small-parts
  and archive disk failures fail (or partially fail,
  with files landed) the entry with a "local disk"
  detail; a transient archive is partial and backed
  off. Done when a coverage run shows both clean.
- A (refill) — `runner/ops/extsources.py::is_withheld`
  (6 lines never run on either platform, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  IsWithheldEdgesTest in
  runner/tests/test_extension_sources.py: empty
  inputs are not withheld; an unresolvable path is
  withheld (fail closed); non-string withheld
  entries are skipped; an unresolvable withheld
  entry is compared as given. The function is fully
  run under that class. Done when a coverage run
  shows it clean.
- A (refill) — `runner/runner.py::log_startup` (6
  lines never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LogStartupBlockTest in
  runner/tests/test_personal_docs.py: a tripped
  personal-documents check prints the fixed banner;
  a failing check is swallowed and the start
  proceeds; an inference config prints ask=on;
  additional secrets print as key names only (the
  value asserted absent) with the unrestricted-key
  warning. Done when a coverage run shows the
  function clean.
- A (refill) — `runner/runner.py::handle_v2_mail`
  (6 lines never run on either platform, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  Version2IngestRejectionsTest in
  runner/tests/test_cli_options.py: with the v2
  module unavailable the message is not taken; a
  sealed body that disagrees with its subject is
  rejected and taken; a question the answer builder
  refuses is rejected the same way. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/runner.py::run_fetch_sources`
  (6 lines never run on either platform, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  FetchSourcesRefusalsTest in
  runner/tests/test_extension_sources.py: the
  sources module unavailable is exit 1; an invalid
  policy is exit 2 with the problem printed; another
  pass already running is exit 1. Done when a
  coverage run shows the function clean.
- A (refill) — `runner/cloud/send_dtls.py::`
  `_plain_result` and `_load_ticket` (6 lines each
  never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PlainResultAndTicketTest in
  runner/tests/test_send_dtls_main.py: a non-envelope
  result is refused as such; an encrypted result is
  decrypted and its inner signature verified; one
  bound to another job does not decrypt; a saved
  session ticket loads back byte for byte and
  unreadable ones load as none. Done when a coverage
  run shows both clean.
- A (refill) — `runner/ops/posture.py::`
  `_looks_like_placeholder` (7 fallback lines never
  run on Windows, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  PlaceholderFallbackTest in
  runner/tests/test_posture_gaps.py: the shared
  check answers through the lazy import; with the
  import unavailable the answer is False, and a
  raising shared check is likewise False. With it,
  queue A's runner.py module-level residue (the
  three missing-sibling ImportError raises and the
  frozen-exe extension re-entry lines, 7 on both
  platforms) is unreachable by construction while
  the package is intact and the build is not frozen;
  recorded here, not chased.
- A (refill) — `runner/extensions/log-sentinel/`
  `log_sentinel.py::read_new_lines` (7 lines never
  run on Windows, coverage run 40187685363; the code
  is platform-neutral, the Windows fixtures were
  not) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReaderGuardsTest in
  runner/tests/test_log_sentinel.py: paths that are
  not a list read as none; non-path entries are
  skipped; a missing file and a file that stats but
  will not open each keep their recorded offset.
  Done when a coverage run shows the function clean
  on both platforms.
- A (refill) — `runner/runner.py::kill_tree` (7 lines
  never run on Windows, 2 on Linux, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the Windows
  residue is the POSIX branch and the POSIX-only
  extra-pids block (platform-inapplicable there,
  covered on Linux); the Linux residue was the
  extra-pids swallow, now pinned in
  runner/tests/test_linux_process.py: an extra pid
  that is already gone is swallowed, and the job's
  own pid and empty entries are never signalled
  through the tail. Done when a coverage run shows
  only the platform pair left.
- A (refill) — `runner/extensions/aide-feed/`
  `aide_feed.py::read_report_file` (7 lines never run
  on Windows, 4 on Linux, coverage run 40187685363)
  — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReaderRaceTest in runner/tests/test_aide_feed.py:
  a non-dict reader state reads fresh; a report that
  stats but will not open (a directory) keeps its
  previous fingerprint; when two reports are new,
  only the one read advances -- the second keeps its
  previous fingerprint and stays new for the next
  pass. Done when a coverage run shows the function
  clean.
- A (refill) — `runner/extensions/job-fuzz/`
  `job_fuzz.py::read_live` (7 lines never run on
  either platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReadLiveCampaignLegsTest in
  runner/tests/test_job_fuzz.py, on the ReadLiveTest
  rig: an unusable records cap reads as the default;
  a reader state without a numeric campaign seed is
  seeded from the clock; an empty pool ends the
  pass; the variant budget breaks both loops; a
  mutator with nothing to mutate is skipped; a box
  that stops being idle mid-pass ends the campaign
  with the outcomes it has. Done when a coverage run
  shows the function clean.
- A (refill) — `runner/extensions/airwaves/`
  `airwaves.py::_run` (7 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  RunToolTest in runner/tests/test_airwaves.py, the
  interpreter standing in for the scan tools: a
  successful run returns its stdout; a nonzero exit,
  a timeout, and an OSError from the run are each
  None. Done when a coverage run shows the function
  clean. — done: coverage run 40189711740 (main at 8765f81) shows no never-executed lines on either platform.
- A (refill) — `runner/extensions/wazuh-feed/`
  `wazuh_feed.py::main` (7 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  WazuhMainDeliveryTest in
  runner/tests/test_wazuh_feed.py: local delivery
  success writes the state; not set up is exit 2; a
  short delivery is exit 2 with the state unwritten;
  a manifest with non-object tunables reads as the
  defaults. Done when a coverage run shows the
  function clean. — done: coverage run 40189711740 (main at 8765f81) shows no never-executed lines on either platform.
- A (refill) — `runner/extensions/softflowd-feed/`
  `softflowd_feed.py::main` (7 lines never run on
  either platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SoftflowdMainDeliveryTest in
  runner/tests/test_softflowd_feed.py: the live
  collection branch runs when no readings file is
  given; local delivery success writes the state;
  not set up is exit 2; a short delivery is exit 2
  with the state unwritten. Done when a coverage run
  shows the function clean. — done: coverage run 40189711740 (main at 8765f81) shows no never-executed lines on either platform.
- A (refill) — `runner/extensions/latency-post/`
  `latency_post.py::main` (7 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  LatencyMainDeliveryTest in
  runner/tests/test_latency_post.py: the live branch
  runs when no readings file is given; local delivery
  success writes the state; not set up is exit 2; a
  short delivery is exit 2 with the state unwritten.
  Done when a coverage run shows the function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/ops/install.py::`
  `install_project_snapshot` (7 lines never run on
  either platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  two tests in InstallAndOracleTest
  (runner/tests/test_make_snapshot.py): stale
  staging/retired dirs from a crashed install are
  swept before the next one; a swap that fails after
  the current snapshot is retired restores it and
  reports False. The function is fully run under
  that class locally. Done when a coverage run
  shows it clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/transport_extensions/nats/`
  `__main__.py::NatsPipe.run` (7 lines never run on
  Linux, 5 on Windows, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NatsPipeRunDropsTest in
  runner/tests/test_transports.py: a non-UTF-8
  message and a malformed envelope from the broker
  are logged and dropped, nothing delivered; a dead
  connection is closed and the loop reconnects with
  backoff. Done when a coverage run shows the
  function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `_is_number` in aide-feed, usb-arrivals
  and wire-arrivals (the whole body, 7 lines each,
  never run on either platform, coverage run
  40187685363) — taken and done as filed 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the helper
  is defined and never called in all three files
  (their tunables are paths, kinds, interfaces and
  a boolean; the one numeric tunable,
  poll_interval_sec, is the supervisor's, not the
  sense's). No behavioral gap; the dead copies are
  filed as Q23 for Claude's lane rather than tested
  against nothing.
- A (refill) — `runner/ops/extsources.py::_parse_entry`
  (7 lines never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DeclarationRefusalsTest in
  runner/tests/test_extension_sources.py, through
  parse_declaration: an entry that is not an object,
  an upstream value not exactly true, a non-bool
  archive on github and url entries, github files
  not a list or listed twice, project paths not a
  list or listed twice -- each refused with a
  ValueError naming the field. Done when a coverage
  run shows the function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/transport_extensions/dtls/`
  `__main__.py::DtlsPipe._on_job` (7 lines never run
  on either platform, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsOnJobDropsTest in runner/tests/test_dtls.py:
  a message that is not UTF-8, not an envelope, or
  an envelope with no job id in its subject is
  dropped and delivers nothing; a real envelope is
  delivered and its session recorded (control). Done
  when a coverage run shows the function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/runner.py::_local_signal_server`
  (8 lines never run on Windows, 2 on Linux, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the one
  existing drive of the refusal block skips on
  Windows (a real occupied port does not fail the
  second bind the same way there), so
  LocalSignalServerRefusalTest in
  runner/tests/test_runner_last_edges.py drives it
  with a bind-failing socket fake, identically on
  every platform: the refusal returns None, the
  half-made socket is closed, and a failing close is
  swallowed. Done when a coverage run shows the
  function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/oracle/resources.py::`
  `_save_state` (8 lines never run on Windows, 7 on
  Linux, coverage run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SaveStateFallbacksTest in
  runner/tests/test_resources.py: a non-dict state
  saves as an empty object; a chmod failure still
  leaves the state written; a write failing after
  the temp file opens closes the descriptor, removes
  the temp, and saves nothing; a failing close in
  cleanup is swallowed. The residue's flag lines
  are the platform pair (O_NOFOLLOW inapplicable on
  Windows, O_BINARY on Linux). Done when a coverage
  run shows only those left. — done: coverage run 40189608702 (main at eef3af8) leaves only each platform's foreign flag line (187 on Linux, 185 on Windows).
- A (refill) — `runner/guard/security.py::_bump_counts`
  (8 lines never run on Windows, 5 on Linux, coverage
  run 40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  BumpCountsFallbacksTest in
  runner/tests/test_security_config.py: a non-string
  base_dir bumps nothing; a write failing after the
  temp file opens still closes the descriptor (no fd
  leak per audit entry) and counts nothing; a failing
  close is swallowed too. The residue's two flag lines
  are the platform pair (O_NOFOLLOW inapplicable on
  Windows, O_BINARY on Linux), each covered where it
  applies. Done when a coverage run shows only those
  left. — done: coverage run 40189608702 (main at eef3af8) leaves only each platform's foreign flag line (339 on Linux, 337 on Windows).
- A (refill) — `runner/extensions/training-watch/`
  `training_watch.py::_scan_checkpoints` (8 lines
  never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ScanCheckpointsRacesTest in
  runner/tests/test_training_watch.py: the scan's
  three OSError guards (an unlistable run dir scans
  as empty; an unlistable subdir and an entry that
  raises on probe are skipped; a file whose stat
  fails after its isfile check is skipped), each
  driven by the real tree plus one wrapped os call
  raising for exactly one path. Done when a coverage
  run shows the function clean. — coverage run 40189608702 (main at eef3af8) shows the function clean on Linux; on Windows the stat-guard test failed and the map leaves exactly the guard pair unrun, because its drive counted os.stat calls and the platform's isfile does not stat the way the count assumed. The test is re-driven in the commit carrying this note (the probe stubbed for the target, the scan's own stat raising), and the Windows close awaits its verifying run.
- A (refill) — `runner/extensions/sysmon-feed/`
  `sysmon_feed.py::main` (8 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SysmonMainDeliveryTest in
  runner/tests/test_sysmon_feed.py: local delivery
  success writes the state and files one envelope;
  delivery not set up is exit 2; a short delivery is
  exit 2 with the state unwritten, so the next pass
  re-reads; a manifest without tunables runs the live
  defaults. Done when a coverage run shows the
  function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/runner.py::`
  `_extension_sources_pass` (the whole body, 8 lines,
  never run on either platform, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the tick
  tests substitute a fake pass and the wiring tests
  call provision directly, so the real wrapper never
  ran. ExtensionSourcesPassTest in
  runner/tests/test_extension_sources.py: a real pass
  provisions and returns the report; a failing pass
  returns None and never raises; no sources module is
  None. Done when a coverage run shows it clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/transport_extensions/nats/`
  `__main__.py::NatsClient.connect` (9 lines never run
  on either platform, coverage run 40187685363) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NatsConnectFailuresTest in
  runner/tests/test_transports.py drives a scripted
  loopback broker: a refused connection, silence
  before INFO, a non-INFO greeting, silence after
  INFO, a server -ERR, and a wrong PONG are each a
  TransportError naming the stage. Done when a
  coverage run shows the function clean but the
  success return the happy path already covers.
  With it, `runner/ops/install.py::`
  `_install_osquery_linux` (11 lines, Windows only in
  the same run) is platform-inapplicable on Windows
  (a Linux-only installer path), covered on Linux;
  closed under the queue-A skip rule. — done: coverage run 40189608702 (main at eef3af8) shows the function clean on Linux; the Windows map leaves the refused-connection except/raise pair (184-185) unrun while the test that can only pass through that raise (test_a_refused_connection_is_named, asserting "cannot connect to") passes on Windows in the same run — a line-attribution residue, recorded as such.
- A (refill) — `runner/transport_extensions/dtls/`
  `__main__.py::main` (9 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  DtlsMainRefusalsTest in runner/tests/test_dtls.py:
  no channel directory, an unusable port, and a bind
  that cannot be listened on each refuse with exit 2
  and a named reason (the real port validation and a
  real bind failure drive two of them); a failed pass
  is logged and the loop goes on. Done when a coverage
  run shows the function clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/extensions/job-fuzz/job_fuzz.py::`
  `_mut_quote_break` (9 lines never run on either
  platform, coverage run 40187685363) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  QuoteBreakMutatorTest in runner/tests/test_job_fuzz.py
  drives the mutator through the MUTATORS table: one
  quote flips and nothing else moves; a quoteless
  script gains the unterminated echo line. The function
  is fully run under that class locally. Done when a
  coverage run shows it clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines on either platform.
- A (refill) — `runner/runner.py::execute_job` (9 lines
  never run on Windows, 8 on Linux, coverage run
  40187685363) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ExecuteJobFallbacksTest in
  runner/tests/test_remediation_e2e.py: a monitor that
  fails to start, a monitor whose stop fails, and a
  remediation close-out that raises each leave the
  job's result untouched; a close-out member is
  attached (that line had never run on Windows). The
  set's last line, the script-write branch's own
  "script must be a string" raise, is unreachable by
  construction -- the input validation above it
  rejects a non-string script first -- and the
  contract is pinned at that live guard. Done when a
  coverage run shows only that line left. — done: coverage run 40189608702 (main at eef3af8) shows only line 3510 left on either platform, the unreachable line recorded above.
- A (refill) — `_deliver_local` in the nine senses the
  Q14 roster never included (airwaves, crash-watch,
  falco-feed, service-watch at 9 lines; osquery-feed
  at 8; pi-health, tripwire, usb-arrivals,
  wire-arrivals at 5; coverage run 40186441596) —
  taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — all nine are
  live senses using the roster harness's exact args;
  they were simply never on the list. The roster in
  runner/tests/test_sense_delivery.py now names all
  twenty-eight senses, and under that module alone
  every copy's _deliver_local is fully run locally.
  Done when a coverage run shows the nine clean. — done: coverage run 40189608702 (main at eef3af8) shows no never-executed lines for the nine on either platform.
- D — the mutation workflow's surviving mutants as
  missing assertions — taken and done 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the seeded
  workflow has never run in CI; a local run of the
  shipped configuration over runner/guard/security.py
  generated three mutants (write_audit_entry's key_id,
  job_id and detail defaults), all survived, all now
  killed by AuditEntryDefaultsTest in
  runner/tests/test_security_md_claims.py, verified
  against each hand-applied mutant. The run's stats
  mapped tests to that one function only, so the
  signal's narrowness is filed as Q22, not mistaken
  for a clean bill.
- D — PROTOCOL.md's examples and AGENTS.md's "Do not
  emit" table, run as written — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  runner/tests/test_protocol_examples.py: every json
  block in PROTOCOL.md parses, the section 3.1 job
  sketch runs end to end, the 3.2 result sketch
  verifies, and the table's rows pass as written --
  except one divergence, filed as Q21 with the
  failing-by-design MissingBinaryRowProbe: the
  missing-binary row says "Rejected" unqualified, but
  at the default repair latitude the runner repairs
  the interpreter and runs the job (PROTOCOL.md
  section 3.2); the rejection holds at advise latitude
  and is pinned there. Item done when Q21 is decided.
  — done: Q21 decided in 68c69bb (the row and the
  Windows note amended to state the repair; the probe
  replaced by MissingBinaryRowAsAmended in the same
  commit); runner.tests.test_protocol_examples runs
  15 of 15 green.
- D — SECURITY.md and docs/security/threat-model.md,
  one test per claim plus its negative control — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: every behavioral claim in both documents is
  mapped to the test that proves it in
  runner/tests/test_security_md_claims.py; the one gap
  found is pinned there: the security block does not
  hot-reload (a mode change in the file leaves the
  running cfg at its startup mode while a hot key in
  the same write does reload; the same file read at
  startup enables the mode). The rest of both documents
  is policy and process a test cannot falsify.
- B — the four environment axes of queue B (Q20,
  applied in 68c69bb: env-axes.yml gains the sysctl
  job -- ptrace_scope 0-3, protected_symlinks and
  protected_regular off/on, hidepid 0/2, each crossed
  with job_user off/on) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — first run
  40187426146 queued at 68c69bb. Done per axis when
  both values are green, or the difference is filed.
  — done: run 40187426146 completed with all 18 jobs
  green (2 userns legs; 16 sysctl legs: ptrace_scope
  0-3, protected links off/on, hidepid 0/2, each with
  job_user off and on), verified from the run's job
  list; no axis moved the corpus, so no difference to
  file (recorded in Q20, 66e4d0b). The one loose end
  Q20 left in this lane is also closed with this
  commit: the canary module now records the four axes
  in its own AXIS lines beside the userns line, so any
  run of it carries every axis value with its results.
- D — documented-default hunt re-run against every key
  added since the defaults registry was last complete
  (8748b44, Release 3.12.62): no new config keys in
  production code or docs since that commit (the eight
  production commits and the two doc files surveyed);
  the registry guards (6 tests) and the defaults table
  hunt (26 tests) green — taken and done 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90
- A — `runner/oracle/remediation.py::fix_marker_digest`
  (10 lines never run on Windows, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — with it, the
  same file's `sample_tree_posix` (10, Windows) and the
  Linux branch of `total_memory_bytes` (5, Windows) are
  platform-inapplicable on Windows (POSIX readers behind
  their platform guards), covered on Linux; the Windows
  memory branch's failure leg is taken with the item. —
  coverage run 40186330078 (main at 5c724d9) shows no
  never-executed lines on Linux; the Windows residues
  are the second safe-id gate's return (unreachable by
  construction: load_marker only loads under an
  already-safe id) and the platform-inapplicable POSIX
  lines recorded above. The write-failure except pair
  was still unrun on Windows in that run (the only
  other selective-write leg lives inside an AV test
  that skips on Windows), so one more leg is added
  with this ledger commit and awaits its verifying run.
  — done: coverage run 40187504729 (main at fc72408)
  shows fix_marker_digest clean on Linux and only the
  unreachable second safe-id gate unrun on Windows;
  both suites OK in that run.
- A — `runner/extensions/training-watch/`
  `training_watch.py::main` (10 lines never run on
  Linux, coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage
  run 40186249031 (main at 867e5cf) shows no
  never-executed lines for this function on either
  platform. (That run's Windows suite also carried one
  unrelated failure, test_extension_sources'
  archive-retry expecting "fetched" and getting
  "mismatch", seen once; watched for a repeat in the
  next run before anything is filed. The watched
  failure did not repeat in run 40186330078; watch
  closed, treated as a one-off.)
- A — `runner/extensions/job-watcher/job_watcher.py::`
  `main` (10 lines never run on either platform,
  coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage
  run 40186249031 shows no never-executed lines for
  this function on either platform.
- A — `runner/extensions/job-fuzz/job_fuzz.py::`
  `_record_seed` (10 lines never run on either platform,
  coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage
  run 40186249031 shows no never-executed lines for
  this function on either platform.
- A — `runner/runner.py::main` (11 lines never run on
  Windows, coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — coverage run
  40186249031 leaves one Windows line, the --local-test
  dispatch return; that leg is added with this ledger
  commit and awaits its verifying run. — done: coverage
  run 40187267889 (main at cbd794d) shows no
  never-executed lines for this function on either
  platform. (Both suites in that run carry exactly one
  failure, the Q21 probe failing by design at that
  commit; it was replaced in 68c69bb.)
- A — `runner/extensions/resource-sentinel/`
  `resource_sentinel.py::_read_cpu_counters` (12 lines
  never run on Windows, coverage run 40183585961) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40186249031 shows no
  never-executed lines for this function on either
  platform.
- A — `runner/runner.py::_pid_alive` (11 lines never run
  on Windows, 10 on Linux, coverage run 40183585961) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  each platform's branch is inapplicable on the other
  (the ctypes branch on Linux, the kill tail on
  Windows), covered where it applies; the one line
  missing on both, the Windows branch's failure
  fallback, is taken with it. — done: coverage run
  40186249031 (main at 867e5cf) shows no never-executed
  lines on Linux; the Windows residue is the POSIX
  kill tail, platform-inapplicable there.
- A — `runner/runner.py::_append_security_event` (11
  lines never run on Windows, 3 on Linux, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the flag lines
  are platform pairs (O_NOFOLLOW inapplicable on
  Windows, O_BINARY on Linux, each covered on the other
  platform); the rest is taken with it. — done: coverage
  run 40185658710 (main at 0b295ba) leaves only each
  platform's foreign flag lines (O_NOFOLLOW on Windows,
  O_BINARY on Linux).
- A — `runner/extensions/lab-results/lab_results.py::`
  `_deliver_local` (11 lines never run on either
  platform, coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the template
  sense itself was missing from the delivery roster its
  copies are tested by. — done: coverage run 40185658710
  (main at 0b295ba) shows no never-executed lines for
  this function on either platform.
- A — `runner/extensions/job-fuzz/job_fuzz.py::`
  `_run_one_variant` (11 lines never run on either
  platform, coverage run 40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage
  run 40185658710 (main at 0b295ba) shows no
  never-executed lines for this function on either
  platform.
- A — `runner/cloud/send_dtls.py::main` (11 lines never
  run on either platform, coverage run 40183585961) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- A — `runner/runner.py::_v2_ingest` (11 lines never run
  on either platform, coverage run 40183585961) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- A — `runner/wire/oauth.py::store_refresh_token` (12
  lines never run on Windows, 9 on Linux, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — the O_NOFOLLOW
  flag line is platform-inapplicable on Windows and the
  O_BINARY line on Linux (each behind its hasattr guard),
  covered on the other platform. — done: coverage run 40185441322 shows no never-executed lines on Windows; the Linux residue is the O_BINARY line recorded above.
- A — `runner/extensions/job-fuzz/job_fuzz.py::decide` (12
  lines never run on either platform, coverage run
  40183585961) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- rules refreshed 2026-10-25 03:25 PDT
- rules refreshed 2026-10-25 03:00 PDT
- A — `runner/extensions/pi-health/pi_health.py::`
  `_mem_avail_pct_windows` (14 lines never run on Linux,
  coverage run 40180268696) — platform-inapplicable on Linux
  (a ctypes.windll reader behind its own os.name guard),
  covered on Windows; recorded 2026-10-25.
- A — `runner/ops/posture.py::_check_privileges` (13 lines
  never run on Windows, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  platform-inapplicable on Windows (the POSIX branch sits
  behind the function's os.name guard and its driving test
  is POSIX by construction), covered on Linux; the one
  Linux residual, the root row, is taken with it. — done: coverage run 40185441322 shows no never-executed lines on Linux.
- A — `runner/runner.py::handle_mail` (13 lines never run on
  either platform, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- A — `runner/oracle/dri.py::_save_state` (14 lines never run
  on Windows, 9 on Linux, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 leaves only each platform's foreign flag line (O_NOFOLLOW on Windows, O_BINARY on Linux).
- A — `runner/oracle/detection.py::update_baseline` (14 lines
  never run on Windows, 8 on Linux, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run
  40183995594 (main at d2f23bb) leaves only the reset line
  that cannot be reached (the load assigns only a dict or
  the default) and each platform's foreign flag line
  (O_NOFOLLOW on Windows, O_BINARY on Linux), both
  recorded in the test class docstring.
- A — `runner/extensions/resource-sentinel/resource_sentinel.py`
  `::_read_mem_avail_pct` (19 lines never run on Windows,
  coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run
  40183995594 shows no never-executed lines for this
  function on either platform.
- A — `runner/runner.py::_with_seen_file` (14 lines never run
  on Linux, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run
  40183995594 shows no never-executed lines on Linux; the
  Windows residue is the fcntl lock/unlock pair,
  platform-inapplicable on Windows (the msvcrt legs run
  there), covered on Linux.
- A — `runner/guard/sandbox.py::startup_problem` (15 lines
  never run on Windows, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  platform-inapplicable on Windows (the bwrap trial sits
  behind the function's own platform guard), covered on
  Linux; the Linux residuals (start failure, the userns
  note) are taken with it — done: coverage run
  40183995594 leaves on Linux only the platform guard's
  own return line.
- A — `runner/extensions/latency-post/latency_post.py::`
  `_read_default_gateway` (17 lines never run on either
  platform, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run
  40183585961 (main at f10a114) shows no never-executed
  lines for this function on either platform.
- A — `runner/cloud/send_job.py::cmd_verify` (17 lines never
  run on either platform, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `runner/ops/extsources.py::_small_parts` (17 lines never
  run on either platform, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `_deliver_local` in five more sense extensions
  (port-watch, log-sentinel, failed-login-watch,
  cert-sentinel, backup-freshness; 18 lines each, never run
  on either platform, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40186441596 (main at 63e0c80) shows
  no never-executed lines for these five functions on
  either platform, and the nineteen-sense roster is clean
  in the same run; that run's Windows suite is OK, which
  also confirms the four fd-leak error fixes in the same
  commit. Nine non-roster `_deliver_local` copies remain
  (airwaves, crash-watch, falco-feed, osquery-feed,
  pi-health, service-watch, tripwire, usb-arrivals,
  wire-arrivals; 5 to 9 lines each) as residual field.
- A — `runner/guard/security.py::validate_security_config` (18
  lines never run on Windows, 7 on Linux, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 shows no never-executed lines on Linux; the Windows residue is the POSIX pwd block behind its os.name gate, platform-inapplicable there.
- A — `runner/extensions/latency-post/latency_post.py::_probe`
  (19 lines never run on either platform, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- A — `runner/extensions/aide-feed/aide_feed.py::main` (20 lines
  never run on Windows, 7 on Linux, coverage run 40180268696) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `runner/ops/install.py::install_files` (20 lines never run
  on Windows, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 shows no never-executed lines on Linux; the Windows residue is the POSIX binary chmod behind its os.name guard, platform-inapplicable there.
- A — `runner/extensions/job-fuzz/job_fuzz.py::main` (23 lines
  never run on either platform, coverage run 40180268696) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  done: coverage run 40183585961 shows no never-executed
  lines for this function on either platform.
- A — `runner/extensions/service-watch/service_watch.py::read_live`
  (30 lines never run on either platform, coverage run
  40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — done: coverage run 40185441322 (main at 232f617) shows no never-executed lines for this function on either platform.
- A — `runner/ops/install.py::_install_collector_linux` (31 lines
  never run on Windows, coverage run 40180268696) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  platform-inapplicable on Windows (a Linux-only installer
  path), covered on Linux; closed under the queue-A skip
  rule, 2026-10-25.
- A — `runner/ops/install.py::_install_falco_linux` (32 lines never
  run on Windows, coverage run 40180268696) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  platform-inapplicable on Windows (a Linux-only installer
  path), covered on Linux; closed under the queue-A skip
  rule, 2026-10-25.
- Finding — full-suite run at 93998ca+ (6,395 tests): the
  Hypothesis property test_preamble_and_trailer_ignored errored on
  a shrunk counterexample (payload {'{': None, '"': []}, preamble
  '"'): a lopsided preamble quote inverts _object_start's string
  tracking and a valid signed job is rejected. Filed as Q32 with
  PreambleBraceInStringTest (4 expectedFailure, 5 pins) —
  58316a92-3c4a-41cb-8a16-8c0c5a871e90, 2026-10-25. The same run's
  one failure was the unregistered kill_tree skip reason from the
  c7a7d18 take; registered in d6f822d.
- A (refill) — `runner/transport_extensions/nats/__main__.py::main`
  (12 lines never run on the local full-suite map at 93998ca) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  NatsMainLegsTest in runner/tests/test_transport_shells.py: no
  channel directory answers 2, a pipe whose constructor raises
  TransportError answers 2, and the happy path runs the pipe and
  answers 0. Locally coverage-clean on main's lines. Done when a
  coverage run shows main clean and the build's Windows shards
  are green for it.
- A (refill) — `runner/transport_extensions/dtls/__main__.py::main`
  refusal legs (4 lines never run on the local full-suite map at
  93998ca: the no-shared-secret return, the greeting-tier warning,
  the PSK-floor entry) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 — DtlsMainRefusalLegsTest
  in runner/tests/test_transport_shells.py: no secret answers 2,
  a weak PSK answers 2, a pipe that cannot listen answers 2, and
  a bogus greeting tier warns and proceeds at family. Locally
  coverage-clean on the four lines. Done when a coverage run
  shows them clean and the build's Windows shards are green.
  (Same batch: Q32 verified closed — Claude's fix 2b561bc makes
  all four probe shapes verify and the property is green.)
- Stamp — release 3.12.67 (tag at 382eb3a, published
  2026-10-25T14:17Z) FULL stamp by Muse,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90: GitHub release carries
  all eight platform archives plus pi-light, the project
  tarball, wheel and sdist, SHA384SUMS, SBOM and
  BUILD-PROVENANCE; the wheel's and sdist's SHA-384 match the
  sums file; PyPI's 3.12.67 is the latest there and its wheel
  and sdist are byte-identical to the GitHub assets (SHA-256);
  GHCR ghcr.io/pigeon-home/homing-pigeon carries the v3.12.67
  tag and latest at 382eb3a. Tag build's test, typecheck and
  platform builds green; its mutation job still running (the
  D4 triage input).
- A (refill) — `runner/extensions/suricata-feed/suricata_feed.py`
  `::main` tunables guard and local-delivery refusals (lines
  509, 555, 559-562 on the local full-suite map at 93998ca) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MainDeliveryLegsTest in runner/tests/test_suricata_feed.py:
  non-dict tunables read as none, an undeliverable pass is
  rc 2, and a partial delivery is rc 2 naming the shortfall,
  both with the state left unwritten. Locally coverage-clean.
  Done when a coverage run shows them clean and the build's
  Windows shards are green.
- D4 — the .67 tag run's mutation job (40200926906) completed
  FAILED with no tally and no survivors: its stats pass died
  at a script-mode test whose child interpreter re-enters
  mutmut's config resolution inside the copied tree. Filed as
  Q33 for Claude's lane; the triage waits on a completed
  mutation run. — 58316a92-3c4a-41cb-8a16-8c0c5a871e90,
  2026-10-25.
- rules refreshed 2026-10-25 ~08:00 PDT (standing orders,
  AGENTS.md rules 7-9, open questions: Q33 new, Q32 answered,
  Q30 closed in practice; playbook hard rules unchanged).
  resources 2026-10-25T14:26:35Z: cores 2 | box cpu 50% |
  wall 0s | peak rss 12 MB | mem used 97% | disk free
  166.4 GB | under-driven (between scoped takes; the local
  full-suite coverage run finished this hour).
  resources-top: hatch 198 MB, python 12 MB.
- A (refill) — chmod-failure swallows in
  `runner/oracle/senses.py::_write_private` (lines 336-337)
  and `runner/oracle/learning.py::_append` (lines 259-260),
  local full-suite map at 93998ca — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  WritePrivateChmodSwallowTest (test_senses.py) and
  AppendChmodSwallowTest (test_oracle_learning.py): with
  os.chmod refusing, the write and the ledger append still
  land and nothing raises. The O_BINARY flag lines beside
  them (328 / 251) are platform mirrors, covered on the
  Windows map. Locally coverage-clean on the swallows. Done
  when a coverage run shows them clean and the build's
  Windows shards are green.
- A (refill) — `runner/ops/extsources.py` reader legs:
  `_read_json` over-cap and unreadable returns (215,
  217-218), `_scan_local` vanished-file pass-over and cap
  break (1204-1205, 1207), `_installed_record` unhashable
  file left out and in-place stale copy removed (1260-1261,
  1268) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReadJsonRefusalLegsTest, ScanLocalLegsTest and
  InstalledRecordLegsTest in
  runner/tests/test_extension_sources.py. All three
  functions are clean under the module's tests locally.
  Done when a coverage run shows them clean and the
  build's Windows shards are green.
- A (refill) — serial and mutator legs:
  `usb_arrivals.py::_read_serial_devices` empty/repeated
  name pass-over and unresolvable target (146, 151-152),
  and `job_fuzz.py::_mut_oversized_line` applied through
  build_variant (365-367; registered in MUTATORS but never
  applied by a test) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  SerialDevicesLegTest (test_usb_arrivals.py) and
  OversizedLineMutatorTest (test_job_fuzz.py). Done when a
  coverage run shows them clean and the build's Windows
  shards are green.
- A (refill) — sender legs: `runner/cloud/send_dtls.py`
  `::_build_body` script-file and timeout members (93-94,
  98) and `runner/cloud/send_job.py::main`'s ValueError
  answer (527-529) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  BuildBodyScriptFileTest (test_send_dtls_main.py) and
  MainValueErrorLegTest (test_send_job_verify.py).
  Recorded without takes on the same map:
  dtlsproto.x25519's final swap (186-187, unreachable by
  construction, already recorded) and
  resources._save_state's O_BINARY flag line (187), a
  platform mirror covered on the Windows map. Done when
  a coverage run shows the taken legs clean and the
  build's Windows shards are green.
- A (refill) — `runner/extensions/cert-sentinel/cert_sentinel.py`
  legs: `_read_tls_target`'s answering endpoint (157-158,
  161) and `main`'s partial local delivery (471, 474-477),
  local full-suite map at 93998ca — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  ReadTlsTargetSuccessLegTest and MainPartialDeliveryLegTest
  in runner/tests/test_cert_sentinel.py (the earlier
  read_live leg mocked the probe itself, so its success
  lines never ran). Locally coverage-clean on the taken
  lines. Done when a coverage run shows them clean and
  the build's Windows shards are green.
- A (refill) — delivery legs in two more extension mains
  (local full-suite map at 93998ca):
  resource-sentinel's live-readings path and its
  undeliverable and partial returns (485, 496, 500-503),
  backup-freshness's partial return (359, 362-365) —
  taken 2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MainDeliveryLegsTest (test_resource_sentinel.py) and
  MainPartialDeliveryLegTest (test_backup_freshness.py);
  both name the shortfall on stderr and leave the state
  unwritten. Done when a coverage run shows them clean
  and the build's Windows shards are green.
- A (refill) — delivery legs in two more extension mains
  (local full-suite map at 93998ca): lab-results'
  tunables guard, undeliverable and partial returns
  (264, 284, 288-291), falco-feed's tunables guard and
  partial return (467, 517-520) — taken 2026-10-25,
  58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MainDeliveryLegsTest in the new
  runner/tests/test_lab_results.py and in
  runner/tests/test_falco_feed.py. Done when a coverage
  run shows them clean and the build's Windows shards
  are green.
- A (refill) — partial-delivery legs in four more
  extension mains (local full-suite map at 93998ca):
  failed-login-watch's tunables guard and partial
  return (439, 485-492), sky-watcher's tunables
  guard and partial return (616, 668-671),
  port-watch's partial return (400-406),
  log-sentinel's partial return (491-498) — taken
  2026-10-25, 58316a92-3c4a-41cb-8a16-8c0c5a871e90 —
  MainDeliveryLegsTest / MainPartialDeliveryLegTest
  in the four extensions' test modules. With this
  batch the local map's extension-main clusters are
  all taken or dispositioned. Done when a coverage
  run shows them clean and the build's Windows
  shards are green.
- rules refreshed 2026-10-25 ~09:05 PDT (standing
  orders, AGENTS.md rules 7-9, open questions: Q33
  stands for Claude; playbook hard rules unchanged).
  resources 2026-10-25T14:34:37Z: cores 2 | box cpu 50% |
  mem used 97% | disk free 166.4 GB | under-driven
  (scoped takes all hour). resources-top: hatch
  199 MB, python 12 MB.
- A (refill) — runner.py residual on the local map at
  93998ca is fully accounted: handle_board_mail's four
  lines are its recorded residue; the rest is ones and
  twos (answer_queries' non-dict exec_result reset and
  non-dict signal pass-over, the chat handler's
  unserializable-payload fallback at 10141-10142) --
  all under the queue's stop-for-the-day threshold.
  A fresh local full-suite map at the current head is
  building (cov-local-30be512) to re-rank from; A
  resumes there if anything stands at ten lines or
  more. — 58316a92-3c4a-41cb-8a16-8c0c5a871e90,
  2026-10-25.
- Correction — the two refresh lines above labelled
  ~08:00 and ~09:05 PDT were written ahead of the
  clock (the rig's own resource stamps read 07:2x and
  07:34 PDT); the refreshes happened, the labels
  were wrong. Refresh cadence is hourly from the
  07:02 PDT line.
- Rules refreshed 11:05 PDT (18:05Z); standing
  orders, AGENTS.md rules 7-9, the open questions
  (Q33 answered, Q23/Q29 bookkeeping blanks rest
  with their answerers) and the playbook's hard
  rules re-read.
  resources 2026-10-25T18:05:22Z: cores 2 | box cpu
  n/a | wall 0s | cmd cpu 0s = 0.5 cores busy |
  peak rss 12 MB | mem used 87% | disk free
  166.4 GB | exit 0 | n/a
  resources-top: hatch 354 MB, python 244 MB,
  python 41 MB, systemd 12 MB, python 12 MB
  (the 244 MB python is the D4 mutmut reproduction
  below, in its stats pass.)
- 3.12.68 FULL STAMP: tag at 1ff0385; GitHub
  release published 2026-10-25T14:45:28Z with all
  8 platform archives + pi-light + project tarball
  + wheel + sdist + SHA384SUMS (12 entries) + SBOM
  + BUILD-PROVENANCE; wheel and sdist SHA-384
  verified against the sums file and SHA-256
  against PyPI (latest is 3.12.68, both files);
  GHCR carries v3.12.68 (with the 1ff0385 tag) and
  latest, both created in the publish window;
  SourceForge v3.12.68 folder holds every file;
  GitLab release v3.12.68 carries 13 asset links;
  tag build 40203163585 success, both Docker
  publishes success. Downloads held in
  ~/workspace/stamp-3.12.68/. The release carries
  the Q32 fix (2b561bc); Q32 re-verified from this
  seat: the four probes and the preamble property
  pass (10 tests).
- D4 — the Q33 run's artifact does NOT carry the
  survivor identities: build.yml uploads only
  mutmut.log and mutants/mutmut-stats.json, and
  the per-mutant exit codes live in the *.meta
  files mutation_floor.py reads, which are not
  uploaded. Q34 filed (upload the .meta files).
  Workaround in flight: a local reproduction at
  HEAD in a scratch worktree (security.py and the
  mutmut config are unchanged since 4c73eaf, so
  the mutant space is the run's), mutmut 3.8.0,
  --max-children 2, under rig_resources; the
  triage takes its survivors from the local .meta
  files when it lands.
- Queue A — the fresh local full-suite coverage
  run (cov-local-30be512) completed: 6442 tests
  OK, 33 skipped. Re-rank derived from its data
  file: the largest function gap is
  pi_health._mem_avail_pct_windows (14 lines,
  Windows-only, already dispositioned
  platform-inapplicable); the next function gaps
  stand at 5 lines; what is larger is module-level
  residue in the cloud scripts and verify.py,
  which is not a function take. Under queue A's
  stop rule the local map ends A for the day; the
  Windows CI map is still unrefreshed (runner
  starvation), so the both-platforms form of the
  rule rests on the local map plus the recorded
  dispositions.
- rules refreshed 2026-10-25 13:41 PDT (standing
  orders, AGENTS rules 7-9, open questions Q38/Q39
  pending, playbook hard rules re-read).
  resources 2026-10-25T20:41:38Z: cores 2 | box cpu
  52% | wall 0s | cmd cpu 0s = 0.8 cores busy | peak
  rss 30 MB | mem used 95% | disk free 166.4 GB |
  exit 0 | under-driven
  resources-top: hatch 203 MB, python 12 MB,
  hatch-execd 4 MB, systemd 3 MB, bash 3 MB
- Full pass at b56b07fb (the 3.13.3 tree +
  the seam fix): BOTH SHARDS OK -- 3,370
  tests, skipped=15 and skipped=23 (the
  rig's standing sandbox/platform gates).
  The extraction-breakage episode is closed:
  Q52/Q53's defects are repaired in the
  tree and verified from this seat.
  resources 2026-10-26T02:39:06Z: cores 2 | box cpu 63% | wall 6m50s | cmd cpu 7m15s = 1.1 cores busy | peak rss 241 MB | mem used 89% | disk free 165.9 GB | exit 0 | under-driven
  resources-top: hatch 147 MB, python 9 MB, systemd 4 MB, hatch-execd 2 MB, systemd-journal 1 MB
  (under-use self-report, per Q58: under-
  driven by the tool's band at 1.1 of 2
  cores -- the shard tail again; the box
  then idled while the owner asked his
  questions. Next fill: the stamp queue for
  the release train -- .71 full, .72 and
  .78 light, .77, 3.13.0, 3.13.1, 3.13.2
  and 3.13.3 full -- starting now.)
- rules refreshed 2026-10-25 19:31 PDT
  (standing orders and the amended
  owner-talk section, AGENTS.md rules 7-9,
  the open questions -- Q49 open; Q51
  resolved in substance by .71's publish;
  Q52/Q53 behavior-verified, written
  answers still blank; Q56 on the owner's
  Publish clicks; Q57 to Grok; Q58
  answered -- and the playbook hard rules
  re-read. The hour's suite and resource
  lines are the confirm-pass entry below
  and its successor pass, launched at the
  head this commit creates once the 3.13.3
  release window closed.)
- Confirm pass at 1a177b4e: shard 0 OK
  (3,342 tests, skipped=18); shard 1 failed
  at COLLECTION -- test_remediation_gaps'
  coverage prime stopped on its marker-write
  legs: da441a74 moved the quarantine marker
  writes to the atomic writer, and the legs
  still simulated a failed write by patching
  builtins.open, so the writes succeeded and
  three assertions failed in sequence as the
  prime advanced. Not a product regression:
  the failed-write contracts hold at the new
  seam. Both seats made the same fix inside
  the hour (patch the atomic writer, not
  builtins.open); the other seat's finer
  form -- path-filtered at _open_new --
  landed on main, and Muse's was dropped
  in the rebase in its favor. Module green
  standalone with the landed form.
  resources 2026-10-26T00:37:57Z: cores 2 | box cpu 23% | wall 5m35s | cmd cpu 1m21s = 0.2 cores busy | peak rss 220 MB | mem used 93% | disk free 165.9 GB | exit 1 | under-driven
  resources-top: hatch 215 MB, python 11 MB, systemd 5 MB, hatch-execd 3 MB, systemd-journal 2 MB
  (under-use self-report, per Q58: the low
  cpu is the dead shard -- half the suite
  never ran. Next fill: a fresh full pass at
  the head this commit creates.)
- Suite verdict at d0e0c296 (3.13.2 tree): the
  wholesale red is gone. One shard OK
  (skipped=22); the other ran 3,330 tests with
  failures=1, skipped=14 -- the single failure
  was test_negative_concurrency's poison test,
  which asserted check_resources returns None
  while reading the rig's live memory (0.957,
  over the 0.95 threshold, mid-suite). A
  load-sensitive test, not a product defect:
  fixed in this commit by stubbing
  _mem_fraction at its seam for the poison
  legs. No RecursionError or NameError
  signatures remain in the run.
  resources 2026-10-26T00:30:33Z: cores 2 | box cpu 61% | wall 6m39s | cmd cpu 5m53s = 0.9 cores busy | peak rss 227 MB | mem used 89% | disk free 165.9 GB | exit 1 | under-driven
  resources-top: hatch 262 MB, browser-service 15 MB, curl 13 MB, python3 10 MB, python 10 MB
  (under-use self-report, per Q58: under-
  driven because the hour carried one suite
  pass plus the .74 stamp's downloads and
  this fix; next fill is the confirming full
  pass at the new head.)
- v3.12.74 FULL STAMP DONE: GitHub release
  published 2026-10-25T23:02:31Z by
  github-actions[bot], 13 assets; all 12
  SHA384SUMS entries verify on downloaded
  copies (~/workspace/stamp-3.12.74/); wheel
  and sdist SHA-256 match PyPI; GHCR
  v3.12.74 and latest both resolve (index,
  2 manifests); GitLab release v3.12.74
  carries 13 asset links; SourceForge
  publish job succeeded in the tag build and
  the v3.12.74 folder resolves (its file
  listing is not machine-readable from this
  seat). Tag build 40242410821: every
  publish job success; the run's red was
  test-macos and the typecheck job (the
  latter is Q55's, fixed in 3020a8f2).
- rules refreshed 2026-10-25 17:24 PDT
  resources 2026-10-26T00:24:59Z: cores 2 | box cpu 70% | wall 1m00s | cmd - | peak rss n/a | mem used 95% | disk free 166.4 GB | exit - | under-driven
  resources-top: hatch 146 MB, python 139 MB, python 113 MB, python 86 MB, python 12 MB
  (Q58 answered in this commit. Under-use
  self-report, per Q58's new duty: the 60s
  window above reads under-driven while the
  full suite at d0e0c296 runs -- the shortfall
  is the sharded runner's serial seams, and
  the fill is the suite itself, whose verdict
  and own resources line ledger when it
  lands. Earlier idle today: the queue
  blocked on the Q52/Q53 repair, and one VM
  restart. Standing orders, AGENTS.md rules
  7-9, the open questions (Q49, Q51, Q56 --
  owner's Publish clicks on the .75/.76
  drafts; Q57 -- Grok told to stop creating
  releases; Q58 -- answered here) and the
  playbook hard rules re-read.)
- Owner-talk section re-read as amended
  (d12b59e2, with Claude's reminder in
  docs/use/misc.md): chat to the owner
  carries only a stop-and-ask question from
  the list; progress, confirmations and
  findings live in the ledger, the commits
  and the questions file. Noted here per the
  amendment's own instruction.
- Q53 filed: the extraction series left the
  suite wholesale red (full suite at 3fd1ac88:
  shard 0 failures=65 errors=467 skipped=11;
  shard 1 failures=161 errors=682 skipped=25).
  Two root causes isolated: the _close_quiet /
  _unlink_quiet shims in runner.py call
  themselves (83367061), and script-mode
  runner.py tracebacks on the unfell-backed
  absolute runner.ops imports (8278c7e7; the
  help-document test runs the script). Q52 is
  the third cause. Fixes are the production
  lane's; the campaign re-runs the suite when
  they land.
- rules refreshed 2026-10-25 15:28 PDT
  resources 2026-10-25T22:28:01Z: cores 2 | box cpu 53% | wall 8m21s | cmd cpu 6m18s = 0.8 cores busy | peak rss 429 MB | mem used 88% | disk free 166.4 GB | exit 1 | under-driven
  resources-top: hatch 258 MB, python 10 MB, systemd 5 MB, hatch-execd 5 MB, systemd-journal 2 MB
  (the hour's suite is the Q53 run above:
  wholesale red from the extraction series,
  not green; the rig idled only while the
  causes were isolated by hand. Standing
  orders, AGENTS.md rules 7-9, the open
  questions (Q49, Q51, Q52, Q53) and the
  playbook hard rules re-read. Also
  dispositioned: default_interpreter is
  list-typed with an or-platform-default
  reader (verify.py, runner.py, platformcard)
  -- no single defaulted read for the
  registry, like v2_answerers; its semantics
  are pinned by the platform-card and
  interpreter tests. The queue D documented-
  key sweep is thereby exhausted.)
- Q52 filed: live config reload has silently
  no-opped since Grok's extraction of
  reload_hot_config into runner/ops/attest.py
  (9f495d30) -- the function names load_config,
  HOT_KEYS, HOT_DEFAULTS, LIVE_KEYS and log,
  none of which exist in that module, and the
  load_config NameError is swallowed by the
  function's own bad-file guard, so no hot key
  ever applies and Decision 1's reload naming
  never happens. Four pre-existing pins in
  test_defaults_table_hunt fail (bisected:
  green at 9f495d30^); left undecorated -- a
  regression red, not a probe red. The fix is
  the production lane's. (Also noted: Grok's
  runner-length note at the top of the
  questions file carries the number Q38,
  which already belongs to the remediation
  question; the next free number was Q52.)
- Registry reader paths repaired: Claude's
  extraction of apply_result_policy to
  runner/ops/policy.py left the view and
  max_result_view rows pointing at runner.py;
  both rows now cite the new home, and
  RegistryShapeTests gains a guard that every
  reader site resolves to a function in its
  named file, so the next extraction is caught
  at the door.
- Queue D refill taken: the M1b size caps gain
  refuse-class rows -- max_job_bytes (4194304,
  README-verified) and max_script_bytes
  (1048576; the key is documented but no doc
  states the value, so the row is unverified and
  joins KNOWN_UNDOCUMENTED) -- both probed
  through _validate_size_caps, which refuses
  bools, strings, negatives and non-ints while
  0 (unlimited) and None (absent) parse.
  Registry count 125 -> 127 (74 -> 76 core).
- Queue D refill taken: the local-signals pair
  gains rows -- local_signals (true) and
  local_signal_port (39271; the port is the
  deliberate fail-closed exception, an unusable
  value reading as listener-off rather than the
  default or a refusal, recorded in the row's
  notes). Registry count 123 -> 125 (72 -> 74
  core).
- Queue D refill taken: extension_review gains a
  refuse-class row -- the doc and the reader
  agree it is a security mode ("anything else is
  a config error at startup"): mode_of names the
  problem and _validate_size_caps turns it into
  a startup refusal (exit 2). The hunt's
  REFUSE_PROBES gains the key, driven through
  that validator; True reads as enforce and
  False as off. Registry count 122 -> 123
  (71 -> 72 core).
- Queue D refill taken: the log-bounds family
  gains its five rows -- log_max_bytes
  (33554432), log_backups (4), oracle_log
  (off), oracle_log_max_bytes (536870912),
  oracle_log_backups (4) -- doc-verified against
  configuring-oracle.md's stated fallbacks and
  pinned through the _log_settings /
  _oracle_log_settings / _cfg_flag seams.
  Registry count 117 -> 122 (66 -> 71 core).
- FULL STAMP, v3.12.70 (tag object 97ae14b6 ->
  commit 72c86458; GitHub release published
  2026-10-25T20:26:19Z): GitHub release carries
  all 8 platform archives + pi-light + project
  tarball + wheel + sdist + SHA384SUMS (12
  entries) + SBOM + BUILD-PROVENANCE; wheel and
  sdist SHA-384 verified against the sums file
  and SHA-256 against PyPI (PyPI latest is
  3.12.70; downloads in ~/workspace/
  stamp-3.12.70/); GHCR carries v3.12.70 and
  latest; SourceForge v3.12.70 folder holds all
  13 files; GitLab release v3.12.70 carries 13
  asset links; the tag build's release, pypi,
  sourceforge and gitlab jobs succeeded on
  attempt 2. Caveat on the record: that run's
  test-macos failed on the upgrade-proof shape
  (Q39's territory, green by the .71 build) and
  the flag321 wrong-case shape plus an
  import-order error in the same module (both
  fixed in c6cf32b, Q51). Nothing owed on .70.
- Q51 filed (for Claude): test-macos failed in
  both attempts of the 3.12.71 build on
  flag321-indirect's wrong-case shape -- the Q35
  fix had adjusted its exit code for a
  case-insensitive filesystem but not its stdout
  pair; fixed in the tests lane (c6cf32b), so the
  .71 release jobs (skipped in both attempts) are
  Claude's to re-run. Stamps: v3.12.70 published
  2026-10-25T20:26:19Z and is being stamped now;
  .71's stamp waits on its publish.
- Q50 answered and fixed in the tests lane: the
  one-off Windows failure was the fixture, not
  the product. The attempt-1 build-windows log
  (job 121298576389) shows 'mismatch' !=
  'fetched' at the first pass; the test pins the
  archive's digest from one tgz() build and
  serves another, and the fixture's gzip header
  carried the wall-clock second, so the digests
  part whenever the builds straddle a second
  (reproduced: builds differ first at byte 4,
  the gzip mtime field). The fixture now pins
  mtime 0 and a determinism test holds it.
- Full suite at ca210601: both shards OK --
  shard 0: 3,318 tests, skipped=13, 290.4s;
  shard 1: 3,323 tests, skipped=23, 376.7s.
  This run carries Claude's guard-collapse
  refactor (9faf606d) and the live-capture module.
  resources 2026-10-25T21:51:32Z: cores 2 | box
  cpu 64% | wall 6m19s | cmd cpu 5m51s = 0.9
  cores busy | peak rss 233 MB | mem used 90% |
  disk free 166.4 GB | exit 0 | under-driven.
  resources-top: hatch 190 MB, python 12 MB,
  hatch-execd 7 MB, systemd 6 MB,
  systemd-journal 2 MB. (Later D-refill commits
  were each
  verified standalone; a suite at the newest
  head is taken in turn.)
- Queue D refill taken: the remediation family
  gains its six rows -- remediation_mode
  (deterministic; an unrecognized value is the
  default, never a silent off) and its five
  numeric settings (storm ceiling 64, sample
  1.0s, Oracle timeout 20s, quarantine bounds
  50 jobs / 512 MiB), each doc-verified and
  pinned through the settings seam. Registry
  count 111 -> 117 (60 -> 66 core).
- Queue D refill taken: three more documented
  keys gain rows -- answer_only (off; strict
  reader, only the exact True takes the role),
  mail_tls_required (required; only the literal
  False opens the hatch, so an invalid value can
  never relax verification), job_encryption
  (absent mirrors the job; a present-but-invalid
  value reads as encrypt-all). Registry count
  108 -> 111 (57 -> 60 core).
- Queue D refill taken: four documented booleans
  that had no registry rows gain them --
  protocol_v2 (off; the reader is strict, only
  the exact boolean True enables the version 2
  messages, so an invalid value can never turn
  them on), oracle_opinion_model (false),
  oracle_learning (true), oracle_learning_model
  (false) -- each doc-verified against
  docs/oracle/configuring-oracle.md and pinned by
  a named class in test_doc_default_divergences
  .py; the registry count moves 104 -> 108
  (53 -> 57 core). The D1 documented-key residue
  named in this ledger is now empty.
- Full suite at bf837a9f: both shards OK --
  shard 0: 3,311 tests, skipped=14, 206.8s;
  shard 1: 3,317 tests, skipped=22, 415.3s. The
  skips are the rig's standing population (sandbox
  classes with bwrap absent, platform gates).
  resources 2026-10-25T21:44:30Z: cores 2 | box
  cpu 58% | wall 6m59s | cmd cpu 5m41s = 0.8 cores
  busy | peak rss 231 MB | mem used 87% | disk
  free 166.4 GB | exit 0 | under-driven.
  resources-top: hatch 176 MB, python 9 MB,
  hatch-execd 6 MB, systemd 5 MB,
  systemd-journal 2 MB. (The run predates the
  queue D refill commit; its modules were
  verified standalone, 1,015 tests OK.)
- Queue D refill taken: four documented enum keys
  that had no registry rows gain them --
  oracle_opinion_mode (repair), oracle_opinion_
  predict (requested), oracle_opinion_repair
  (rejudge), oracle_mode (llm) -- each doc-verified
  against docs/oracle/configuring-oracle.md and
  pinned by a named class in
  test_doc_default_divergences.py (invalid values
  read as the documented default); the registry
  count moves 100 -> 104 (49 -> 53 core). Their
  readers use opinion.py's own _clean / an
  exact-match read, never confval, which is why
  the coverage guard never forced the rows.
- Queue A dispositions: the Oracle chat handler's
  unserializable-payload fallback and dri
  send_telegram's second dumps guard are both dead
  by construction -- every payload member is
  str-checked or _page_text-coerced before the
  dumps, so neither dumps can raise. The Q46
  family ruling covers them; no probes possible.
- Queue A taken: airwaves' two singles -- a scan
  row with a blank BSSID is skipped while its good
  neighbour parses, and a stored link without a
  usable BSSID cleans to None (a good link
  normalizes); pinned in test_airwaves.py.
- Queue A taken: log-sentinel read_live's
  default-paths arm -- a log_paths tunable that is
  absent, not a list, or empty reads the built-in
  defaults (patched to a temp log for the pin); a
  second pass over the returned reader state reads
  nothing new. Pinned in ReadLiveDefaultPathsTest.
  Sky-watcher's hour-angle wrap (ha < -180) is
  arithmetic-dead: tst is taken mod 1440, so ha
  cannot go below -180.0 (sweep-verified floor
  -179.9996) -- dispositioned, the NOAA guard stays
  as copied.
- Queue A taken: job-fuzz's blank_line mutator --
  exactly one blank line inserted, the seed's lines
  preserved in order, an empty seed taking one too
  (pinned in test_job_fuzz.py). Its not-lines
  decline is unreachable (str.split never yields
  []), and pi-health _read_throttled's ValueError
  arm is unreachable by grammar too (the regex
  admits only hex digits, and int(x, 16) is exempt
  from the digit cap and cannot raise on them; a
  5000-digit capture parses, verified) -- both
  dispositioned here under the Q46 family ruling.
  Correction to the Q49 ledger entry above: the
  extension script-entry family is every file's
  LAST line, verified line-by-line against the
  map; the non-entry singles (airwaves, job-fuzz,
  log-sentinel, sky-watcher, pi-health) are worked
  individually, as here.
- Queue A finding: training-watch's loss scrape
  admits a non-finite loss ("loss: 1e999" parses to
  inf) that the module's own _is_number rule
  refuses everywhere else -- it persists as a bare
  Infinity literal in the state file, fires a
  loss_flat alert whose detail cannot be signed
  (sign_envelope is allow_nan=False), and wedges
  local delivery on retry. Filed as Q49 with an
  expectedFailure probe. The map's other extension
  singles are the uniform script-entry line
  (sys.exit(main()); main() itself is covered
  in-process for every extension) -- dispositioned
  as a family; softflowd's outer decode except was
  already dispositioned by DecodeDamageLegsTest
  (the decoders' length guards sit in front of it).
- Queue A taken: send_dtls._pump's failed-recv arm
  (the map's single) -- a recv that raises
  mid-handshake is shrugged off and the pump keeps
  driving the client core; a socket that stays dead
  runs to the deadline and reports False. Pinned in
  PumpLegsTest with a stub core and socket.
- Queue A taken: extreview's review cache -- the
  cap eviction (oldest first) and forget's two
  scopes (one folder, all folders) pinned as
  behavior in CacheTest, alongside the fresh/cached
  signal apply() already relies on. Held open with
  run_variant: three arms the tests demonstrably
  execute locally (this cache's clear in every
  RecordTest setUp, load_report's no-path return,
  run_variant's error report) still showed missed
  on the 40229324722 CI map; a fresh map at a
  current head either credits them or names them
  again, and the run's suite.log will say which
  shard carried the module.
- rules refreshed 2026-10-25 14:24 PDT (standing
  orders, AGENTS rules 7-9, open questions,
  playbook hard rules re-read; Q38-Q48 all answered
  and applied, Q26 progress-only and Q31 a standing
  instruction; queues S/R discharged, B discharged
  via Q20/Q43, A in its 1-line residue).
  resources 2026-10-25T21:24:39Z: cores 2 | box cpu
  0% | wall 0s | peak rss 12 MB | mem used 98% |
  disk free 166.4 GB | exit 0 | under-driven
- Q45-Q48 answered by Claude (2e5617ae, applied-in
  f76338f6) and verified here: the dead re-checks
  in detection.update_baseline and answer_queries
  are gone; the dri page-path guards stay with a
  comment naming alert_score's never-raises
  contract; the signing pair is aligned on the
  up-front payload guard (sign_envelope's dead
  serialize check cut, sign_payload gains the
  guard), and verify_body's dict check stays as the
  verifier's last check by decision. Scoped modules
  (detection, dri, extensions, send_job, properties,
  answer_queries, senses) green at the new head.
- Queue A taken: extsources.is_withheld's
  unresolvable-entry arm -- a withheld entry
  realpath refuses (a NUL in the name) is compared
  as given, matches nothing, and is passed over
  without raising or masking a later good entry;
  pinned in DisclosureTest. The neighbouring
  _clean_rel_path "names no path" raise is
  unreachable by construction; dispositioned, no
  probe possible. (This line and the next were
  written twice: a failed pull ate the first
  attempt's ledger edit; the tests landed in
  0decd825 and be3cb3a1 regardless.)
- Full suite at ddd6608: both shards OK (shard 1 in
  564.9s under foreground contention; resources
  2026-10-25T21:17:36Z: cores 2 | box cpu 46% | wall
  9m27s | peak rss 228 MB | mem used 91% | disk free
  166.4 GB | exit 0 | under-driven).
- Queue A taken: auditreport's _security = None
  degradation (the map's _dangerous_names single) --
  without the security module the report prints its
  skeleton, reads no entries (the audit file's name
  is the security module's to give), and the
  dangerous-name set is empty; pinned in
  test_audit_report.py. sandbox.startup_problem's
  Linux-map single is its platform-guard line, the
  recorded mirror disposition.
- Q43 and Q44 closed by Claude (e912ccb3) and
  verified here. Q44: status() now reads each member
  for its shape and reports it blank when wrong; the
  two probes pass with their decorators off
  (StatusShapeTest green). Q43: answered by pointing
  at Q20's legs in 68c69bb, 18 of 18 green -- queue B
  is discharged on that line; nothing new to build.
  Remaining open questions are the small dead-guard
  family (Q45, Q46, Q47, Q48).
- Queue A dispositions, one batch: security.py's
  two singles (359, 435) and learning._append's
  single are the os.O_BINARY platform mirror;
  dri.py's 29-30 are the script-mode import fallback
  (the package import takes the first branch);
  send_job.py's 59 is the jobcrypto-not-loadable
  guard (cannot fire in an intact checkout) and its
  78-79 the run-by-path version fallback. Two real
  guards turned out dead behind their own callers'
  construction -- sign_envelope's serialize check
  and verify_body's not-a-dict check -- filed
  together as Q48 with the pair's asymmetry.
- Queue A taken: answer_queries' senses glossary --
  a declared signal's description is redacted with
  the caller's patterns before it leaves in an
  answer; pinned in test_senses.py with the real
  pattern set (existing glossary tests pass {}
  patterns, which redact nothing). The same
  function's second missed line is a dead exec_result
  re-check, the Q40/Q45 shape; filed as Q47.
- Queue A dispositions from the 40229324722 map,
  verified against that head's tree (72c8645) before
  taking: handle_board_mail's missed pair is the
  dispatch's "unknown board kind" else --
  unreachable by construction (the subject gate
  admits exactly the four dispatched kinds) and
  already pinned as such by BoardMailRejectionsTest;
  run_variant's missed pair is its execution-error
  arm, which test_run_variant's
  test_an_execution_error_is_an_error_report covers
  locally (verified under coverage on this rig) --
  the CI map disagrees at that head, so this one
  stays open until a fresh coverage map at a current
  head either credits the arm or names it again.
- Queue A disposition: dri.evaluate_page_triggers'
  two alert_score guards (the _one ranking arm was
  the map's 2 missed) cannot fire while
  senses.alert_score keeps its hardened never-raises
  contract; filed as Q46 with a keep-with-comment
  recommendation, no probe possible.
- Queue A taken: runner._report_extensions' two
  missed arms (Linux map) -- a loader that raises is
  exactly one WARN line ("extensions: loader failed:
  ..."), and a registry member that is not a dict is
  skipped while real members and problems still
  report; pinned in test_runner_last_edges.py.
- Queue A disposition: detection.update_baseline's
  two missed Linux lines -- the os.O_BINARY flag arm
  is the recorded platform mirror (Windows only);
  the not-a-dict re-check after the load cannot fire
  (baseline is a dict literal or a dict-checked
  load), the Q40 shape again; filed as Q45, no probe
  possible.
- Full suite at 4b3aa63 (both shards) OK; resources
  2026-10-25T21:07:25Z: cores 2 | box cpu 65% | wall
  5m12s | peak rss 225 MB | mem used 91% | disk free
  166.4 GB | exit 0 | under-driven.
- Queue A taken: senses.load_alerts' corrupt-store
  arm (2 missed, Linux map) -- a non-UTF-8 store
  reads as [] and never raises into the poll or
  query path; pinned in test_senses.py StoreLoadTest.
- Q38-Q42 answered by Claude (b3847f33, applied-in
  d6277602) and verified here: Q38's ps tree sampler
  for Darwin and the BSDs landed and the storm
  probe's darwin expectedFailure was lifted in the
  fix; Q39's install completes without a GUI session;
  Q40's dead re-check is deleted; Q41 answered
  keep-as-guard; Q42's arm kept with its comment, the
  dead literal_ guard cut. Scoped re-verification
  (test_remediation, test_remediation_ps,
  test_install_macos_bootstrap, test_extreview,
  test_transports, test_extension_sources): green
  twice over; the only expected failures are Q44's
  two probes. One earlier scoped run under full-suite
  contention showed a single unnamed failure that two
  identical re-runs did not reproduce.
- Queue A taken: runner.prune_sent's silent-skip
  arm (2 missed, Linux map) -- an entry that cannot
  be removed (an old directory among the records)
  is passed over, the count reflects only real
  removals, pinned in test_sent_results.py.
- Queue A taken: extsources.status (2 missed, Linux
  map) -- turned up a finding instead: status()
  documents "never raises" but raises AttributeError
  on a recorded state whose entries or installed
  member is a list (load_states checks neither, and
  the report loop sits outside its try). Filed as
  Q44 with StatusShapeTest probes under
  expectedFailure (control green) in
  test_extension_sources.py.
- Queue A taken: security._enforce_bound's failed-
  roll arm (2 missed): pinned in AuditWriterTest --
  with the rolled name occupied by a directory, the
  rename fails silently by design, no entry is lost,
  and every decision lands on the un-rolled log.
- Queue A taken: runner.save_sent_result (3 missed,
  Linux map) -- its best-effort failure arm is pinned
  in test_sent_results.py: a record that cannot be
  written (a file where the sent directory belongs)
  returns False, logs the WARN naming the job, and
  never raises into the send path.
- Switch proofs at b317475 (the cage fixes) completed
  SUCCESS on all legs; Q37's CI confirmation is in.
- Queue B filed as Q43: the axes (ptrace_scope,
  protected_symlinks/regular, hidepid, the job_user
  cross) need env-axes.yml legs -- this rig's
  /proc/sys is read-only, so the corpus-per-value
  runs are Claude's workflow to add. Queue D1's
  refill: extension_sources reached the docs after
  the defaults registry; its runner-seam naming is
  pinned (SourcesPolicyNamingTest: a malformed value
  is named once per distinct problem, with the
  fail-closed sentence; owner_policy's own shapes
  were already pinned by PolicyTest).
- Q37 closed out: the cage pair is proven and both
  decorators are off. The unsandbox test flipped to
  unexpected success on the switch-proofs Linux and
  root legs (run 40232468239); the drop test was
  reproduced on the rig as root (its script gave
  tier 1 a finding, so the model was never asked;
  its audit words were not the runner's), rewritten
  to `id -u` with the run_as row and the uid in the
  result asserted, and passes as root here. The
  roster entry now declares needs [bwrap, root] --
  with needs empty, the macOS and Windows legs were
  failing the entry on its own registered skips.
- Queue A taken: runner._extension_review_now (4
  missed). Its two failure arms are pinned in
  RunnerGateTest: a raising loader and a raising
  transport discovery each become a problem line in
  the --inspect review report, with the section left
  empty and no crash.
- Queue A: the extreview family is swept.
  FaultLegsTest covers _walk (walk failure, truncation,
  the symlinked-directory remove), fingerprint (None
  on walk failure, the (-1, -1) vanished-entry
  sentinel), _read_code (cannot stat, cannot read) and
  review_folder's walk/truncation findings; a NUL byte
  in code pins the unparseable promise through the
  SyntaxError arm. Two guards in _scan_python cannot
  fire as written (the ValueError/RecursionError arm
  on this Python, the literal_ guard against its own
  regex) -- filed as Q42. extreview's only remaining
  uncovered line is Q40's.
- Queue A taken: runner.run_inspect (5 missed, Linux
  map). Its two unavailable branches -- the sources or
  review module failed to import -- are pinned by
  InspectUnavailableTest in test_extension_sources.py
  (stderr line, exit 1, no crash); local coverage of
  the function shows both branches running.
- Queue A taken: transports.discover_transport_
  extensions (5 missed, Linux map). The review-failure
  catch is covered (ReviewFailureTest: a raising review
  leaves the registry whole, WARN logged, no
  problems). The transport-API refusal lines cannot
  fire while EXTENSION_API_VERSION ==
  TRANSPORT_API_VERSION == 1 and the loader refuses
  first (verified live) -- filed as Q41, done as
  filed per the missing-seam rule.
- Queue A taken: extreview._record (6 missed on both
  maps at 72c8645, the largest non-dispositioned
  function). RecordTest in test_extreview.py pins the
  no-base-dir return, the unwritable-report path (the
  verdicts still report in process, per the docstring),
  the unchanged-verdicts no-rewrite rule, and the
  non-dict-on-disk replacement; local coverage of
  _record goes 6 missed to 1: the isinstance re-check
  after load_report, provably unreachable (load_report
  returns dict-or-None) -- filed as Q40, disposition
  cannot-fire-by-contract.
- S item ORACLE.alphabet taken and done (the
  roster's one empty entry): new
  runner/tests/test_oracle_alphabet.py drives the
  note alphabet (instructions, JSON, approvals,
  refusals, huge, empty, broken) through poll_once
  across advise/repair/diagnose, the succeeding and
  failing shapes, a pinned key's policy in off,
  audit and enforce, and the latitude ceiling --
  every run's decision and outcome equal to its
  no-model control, the model text verbatim at the
  head of its labeled segment and capped at 240,
  the member at 500; tier-1 findings mean the model
  is never asked. Roster entry now lists the module.
  resources 2026-10-25T20:43:35Z: cores 2 | box cpu
  65% | wall 3s | cmd cpu 3s = 0.9 cores busy | peak
  rss 32 MB | mem used 95% | disk free 166.4 GB |
  exit 0 | under-driven
- Q36 done: the rig's live capture is posted under
  docs/reports/live-2026-10-25/ (19,247 files,
  scrub-verified by exact-match scan for the rig's
  secret values: none present; the rotation ask is
  recorded in its README and in Q36's answer -- the
  rotation itself is the owner's).
- Q35 answered in the questions file (four fixed in
  1cfa5bb; the wrong-case shape probed; the
  test_gamma item answered by evidence -- an inner
  fixture report in both macOS logs, never an outer
  failure). Two findings outgrew it: Q38 (remediation
  tree sampler is a stub on Darwin; the storm test
  rides under expectedFailure there) and Q39
  (install_macos aborts when launchctl bootstrap
  fails GUI-less; the upgrade proof is the probe).
  Q37 answered for its R5 half: Grok's drafts
  rewritten onto one poll_once under workers 2 with
  signed payloads, both proven here, decorators off;
  the cage pair's cfg gained the inference block the
  draft lacked and keeps its decorators until a CI
  leg shows the unexpected success.
- Q35 taken (Claude to Muse: the macOS five). Four
  fixed in the tests lane, each a test-side platform
  assumption, none a runner finding:
  test_flag321_indirect's base64 shape now reads
  via stdin (Apple's base64 takes no positional
  input file -- exit 64 on macOS; the shape's
  classification is unchanged);
  test_doc_default_divergences' _run_tool leg uses
  /bin/sh -c "exit 1" instead of /bin/false (macOS
  keeps false in /usr/bin; the missing-tool None
  leg already pins the other side); its meminfo
  live leg asserts the absent-source fact (None)
  where /proc/meminfo does not exist instead of
  demanding a float; test_remediation's storm
  bound is 20s on Linux, 60s off it (the kill
  itself -- act and divergence -- is asserted at
  every bound; off Linux the sampler shells to ps
  per pass and the same kill took 25s on macOS;
  no doc promises a storm kill latency). The
  fifth, the test_gamma discovery leak, is still
  open: in run 40224608110 (the macOS job at
  51d8733) the outer verdict was shards 0 and 2
  only, and the test_gamma block in the log is an
  inner fixture report inside shard 2's dump, not
  an outer failure -- the leak is to be read from
  the next macOS log at a current head before
  anything is changed for it. From FreeBSD's run
  40224608021 (failures=4): the storm (same bound,
  now platform-keyed) and test_service_watch's
  real-/proc smoke test, whose isdir gate let it
  run against FreeBSD's non-Linux procfs -- the
  gate now requires Linux as well; the other two
  failures are named only in the artifact's suite
  log, which newer freebsd runs upload. Push of this batch waits
  for the 3.12.70 release build (Q31 window).
- Coverage verification caught up — CI coverage
  run 40207994733 (HEAD 9d6c832) completed success
  on both platforms: Linux 98.84%, Windows
  97.67%. Every queue A take through the last
  refill batch is an ancestor of that head, the
  run's Windows shard is green for them, and
  their functions read clean on both maps except
  the recorded dispositions: the Windows map's
  large residue is the platform-inapplicable list
  verbatim (sandbox.startup_problem,
  posture._check_privileges,
  install._install_osquery_linux,
  security.validate_security_config's POSIX
  block, remediation.sample_tree_posix,
  runner._pid_alive, posture._check_file_perms,
  resources._mem_fraction, total_memory_bytes'
  POSIX branch, kill_tree's POSIX branch,
  sandbox.build_bwrap_command), and what remains
  elsewhere on either map stands at two lines or
  fewer per function — the recorded cannot-fire,
  measurement-artifact and mirror residues. The
  refill verification backlog is discharged at
  this run. Artifacts held in
  ~/workspace/cov-40207994733/.
- D4 triage landed (tests in
  runner/tests/test_security_config.py:
  ValidateMessageTextTest, SharedSecretBoundaryTest,
  SecDecideAuditFieldTest — 23 tests, green on
  clean code). The CI run's survivors could not be
  named from its artifact (Q34), so the triage ran
  on the local reproduction (566 mutants, 503
  killed, 63 survived, against CI's 500/66 — the
  delta sits in the scratch deselect and this box's
  memory weather). Of the 63: 61 are real missing
  assertions and are killed by construction —
  exact RuntimeError message text for every
  validate raise (the older tests matched loosely),
  the hint verbatim in the missing-secret refusal,
  a secret at exactly 128 estimated bits accepted,
  audit_max_lines of 1 accepted, every placeholder
  word flagged, a job_user name containing X told
  apart from a bad character, the POSIX existence
  check skipped under an nt os.name, and the audit
  entry's key_id/job_id/detail values pinned on
  both sec_decide write paths (absent keys, a
  non-dict mapping ctx, a hostile __str__, and the
  cfg-bound rollover). Two are provably equivalent
  and are recorded, not chased:
  _estimate_secret_entropy mutmut_6 (alphabet < 1:
  log2(1) is 0, both paths give 0.0) and
  _secret_pattern_reason mutmut_34 (the repetition
  multiplier +1 -> +2: both products exceed n, so
  the [:n] prefix is identical for every input).
  Kill verification DONE — a full mutmut re-run
  with the new tests in the scratch tree (after
  /tmp, a 512 MB tmpfs found 100% full of leaked
  suite tempdirs, was cleaned and TMPDIR moved to
  disk; the failures that had dogged the local
  runs were that tmpfs, not the code): verdicts
  for 565 of 566 mutants, 561 killed, 4 survived.
  Every one of the 61 targeted mutants is dead.
  The 4 survivors are the 2 equivalents recorded
  above plus 2 more of the same kind the first
  run's weather had spuriously "killed":
  sec_mode mutmut_19 and _21 (the modes.get
  default mutated to None / removed — the
  `mode in MODES` guard reads any non-mode as
  "off", so the default's value is unobservable).
  A fifth, sec_mode mutmut_23 (default "OFF"),
  is equivalent by the same argument; the run
  was killed by a runtime restart at 563/566
  with its verdict unwritten, and it is recorded
  equivalent on the argument, not on a verdict.
  D4 is complete: the mutation signal now stands
  at 561 killed / 5 provably equivalent survivors
  in security.py, and the next dispatched CI run
  carries the survivor list itself (Q34).
- D4 reproduction, first local attempt: the stats
  pass died on this box's own memory pressure —
  test_name_oracle_resources_tolerate_poison
  asserts no resource_pressure event and the box
  crossed its 0.95 threshold mid-run (mem
  0.9558); the environment tripped the assertion,
  not the code (the CI run's stats pass completed
  on its larger runner). Relaunched with that one
  test deselected in the scratch copy's mutmut
  config only (the timing-deselect pattern; main
  untouched) — a survivor under the rerun is
  trustworthy either way, since memory flakiness
  can only manufacture kills, never survivals.
- platinum 1: statements 99.1% (+0.1), branches
  97.0% (+0.1), 17 tests, 1 crash filed,
  resources 2026-10-26T10:12:50Z: cores 2 | box cpu 58% | wall 30m57s | cmd cpu 26m54s = 0.9 cores busy | peak rss 424 MB | mem used 80% | disk free 165.4 GB | exit 0 | under-driven
  (under-driven is the single-process
  measure's shape: one interpreter runs the
  suite while the second core serves its
  children; the filler rule applies to the
  gaps between cycles, not inside a measure.)
  Baseline 90445244 (99.0%, 294 missing);
  after db3bcc46 (258 missing). Cleared:
  the whole delivery/stash family
  (_sweep_channel_refusals, undeliver_stash,
  _keep_original_result, _delivery_audit,
  _record_payload, _stash_move) by
  test_platinum_runner.py, and
  runner/cloud/send_dtls.py main + _pump by
  test_platinum_send.py. Crash filed: Q60,
  a non-UTF-8 refusal note escapes
  _sweep_channel_refusals as a
  UnicodeDecodeError (probe under
  expectedFailure). wire/ was covered the
  same day by 40000e00's test_platinum_wire.py
  (record layer, then validate/verify/
  _feed_record); it counts in cycle 2's
  baseline, whose tree carries that module.
  Frontier for cycle 2, from the refreshed
  table (docs/reports/v3.13.21/): logic
  extsources.status (5), queues __main__.main
  (5), install._import_atomicio (3),
  install.merge_config_blob (3); guard
  cli._transports_arg (3),
  runner._sweep_workspace (3),
  QueueClient.pull (3); except
  send_job.post_to_queue (6),
  extreview._scan_python (3). protocol_v2
  .validate is 40000e00's, pi_health's
  Windows memory block is platform.
  Measure casualties, for the record: two
  attempts were killed by VM restarts and
  discarded; one sharded attempt was
  discarded as non-comparable with the CI
  way (its subprocess coverage files also
  littered runner/ and tripped test_layout
  locally -- sweep .coverage* out of the
  whole tree after a local measure), and in
  it test_remediation_e2e's exits-first test
  failed once with exit -9 under saturation
  and is green standalone: a load flake, not
  filed. The cycle's verdict rides on the
  CI-way measure above: 6,908 tests, OK
  (skipped=38, expected failures=1).
- rules refreshed 2026-10-26 03:20 PDT
  (standing orders incl. queue P and the
  owner-talk section, AGENTS.md rules 7-10,
  Q59/Q60, the playbook's hard rules).
  resources 2026-10-26T10:12:50Z: cores 2 | box cpu 58% | wall 30m57s | cmd cpu 26m54s = 0.9 cores busy | peak rss 424 MB | mem used 80% | disk free 165.4 GB | exit 0 | under-driven
- platinum 2: statements 99.3% (+0.1), branches
  97.1% (+0.1), 28 tests, 1 crash filed,
  resources 2026-10-26T12:59:45Z: cores 2 | box cpu 48% | wall 27m59s | cmd cpu 22m11s = 0.8 cores busy | peak rss 439 MB | mem used 93% | disk free 165.4 GB | exit 1 | under-driven
  (the exit 1 is the one suite error below,
  not the measure; under-driven is the
  single-process measure's shape again.)
  Baseline 82817d14 (99.2%, 250 missing --
  wire/ counted in, per cycle 1's note);
  after 57f419d3 (221 missing). Cleared:
  every logic/guard/except target on the
  cycle-1 frontier -- extsources.status,
  queues main + QueueClient.pull,
  install._import_atomicio +
  merge_config_blob, cli._transports_arg,
  runner._sweep_workspace,
  send_job.post_to_queue,
  extreview._scan_python's SyntaxError arm.
  Two rows remain on the refreshed table
  (docs/reports/v3.13.27/): _scan_python's
  ValueError/RecursionError arm, a Python
  3.9-3.11 arm that cannot fire on 3.12+
  (every malformed source lands in the
  SyntaxError arm there; recorded in the
  gaps header, not a target), and
  pi_health's Windows memory block
  (platform). Crash filed: Q61 -- the
  cloud sender's verify_body mis-segments a
  signed body whose payload nests a "{"
  string key beside an escaped quote and
  rejects a body the runner's signer made;
  the suite's own test_two_signers_agree
  was the after-measure's one error when
  hypothesis drew the payload, and the
  probe in test_platinum_send.py is that
  counterexample made deterministic.
  Q49 and Q60 both closed this cycle:
  answered, fixed in Claude's lane
  (46244aea, d9b6fcf6), probes undecorated
  and verified green here. The cycle-2
  tests first landed red on three CI legs
  (unregistered skip reason, a POSIX mode
  asserted on Windows, a raw mkdtemp root
  on macOS); the release lane fixed all
  three test lines in 51152726 because a
  car could not be cut from a red head --
  the registry lesson is in misc.md and
  stands: register the reason before the
  push, realpath a path-prefix fixture,
  assert mode bits on POSIX only. The
  baseline measure was killed once by a
  runtime restart and relaunched clean;
  its verdict: 6,923 tests, OK (skipped=38,
  expected failures=1, the then-unfixed
  Q60 probe).
- rules refreshed 2026-10-26 06:05 PDT
  (standing orders incl. queue P, AGENTS.md
  rules 7-10, Q59-Q61, the playbook's hard
  rules). resources 2026-10-26T12:59:45Z: cores 2 | box cpu 48% | wall 27m59s | cmd cpu 22m11s = 0.8 cores busy | peak rss 439 MB | mem used 93% | disk free 165.4 GB | exit 1 | under-driven
- platinum 3: statements 99.4% (+0.1), branches
  97.2% (+0.1), 41 tests, 0 crashes filed,
  resources 2026-10-26T13:58:01Z: cores 2 | box cpu 48% | wall 26m33s | cmd cpu 21m20s = 0.8 cores busy | peak rss 447 MB | mem used 92% | disk free 165.4 GB | exit 0 | under-driven
  (under-driven is the single-process
  measure's shape.) Baseline 57f419d3
  (99.3%, 221 missing); after 53e6c9bf
  (185 missing); the after-suite ran
  6,993 tests, OK (skipped=38) -- no
  expected failures left in the tree.
  Q61 was answered and fixed in Claude's
  lane during the cycle (077dba17,
  answered e9e1acb5); the fix commit
  removed the probe's decorator and the
  probe is green in this measure.
  Cycle 2's tests are done by the Windows
  rule: build 40329549758 at 90dc2fbe
  completed success. Cycle 3's Windows
  verification waits on a completed build
  at a descendant head.
  The map corrected three of this cycle's
  own tests, and the corrections are the
  record: apply's listed pair was its
  no-folder arm (612,613), not the
  review-failure arm the new test covers;
  run_inspect's pair was the review
  success print (5058,5059), not the
  unavailable arm; send_telegram's pair
  is the re-dump return (486,487). Six
  arms are recorded dead or defensive in
  the refreshed gaps header
  (docs/reports/v3.13.29/) and are not
  targets: the _scan_python version arm,
  handle_board_mail's unknown-kind else,
  send_telegram's re-dump return,
  load_alerts' severity except,
  _read_throttled's int arm, and
  training-watch's float arm. Cycle 4's
  honest frontier: cmd_new's to-file arm
  (345-350, grew with the train),
  send_dtls.main's unverifiable result
  (242-244), osquery-feed's short
  delivery, apply's no-folder arm,
  run_inspect's success print,
  inventory.save's unlink swallow, and
  softflowd's struct.error arm, which
  needs a header-valid, record-truncated
  datagram -- the short datagrams of
  cycle 3's property return before the
  parser can raise. ops/main.main's
  workers line (302) still waits on a
  fixture that boots main honestly.
- rules refreshed 2026-10-26 07:05 PDT
  (standing orders incl. queue P, AGENTS.md
  rules 7-10, Q59-Q61, the playbook's hard
  rules). resources 2026-10-26T13:58:01Z: cores 2 | box cpu 48% | wall 26m33s | cmd cpu 21m20s = 0.8 cores busy | peak rss 447 MB | mem used 92% | disk free 165.4 GB | exit 0 | under-driven
- platinum 4: statements 99.4% (+0.0), branches
  97.2% (+0.0), 6 tests, 0 crashes filed,
  resources 2026-10-26T14:32:17Z: cores 2 | box cpu 49% | wall 27m46s | cmd cpu 22m46s = 0.8 cores busy | peak rss 456 MB | mem used 92% | disk free 165.4 GB | exit 0 | under-driven
  (under-driven is the single-process
  measure's shape.) Baseline 53e6c9bf
  (99.4%, 185 missing); after 2006bdc2
  (170 missing); the after-suite ran
  6,999 tests, OK (skipped=38). All six
  named targets cleared: cmd_new's
  to-file arm, apply's no-folder arm,
  run_inspect's success print,
  Inventory.save's unlink swallow,
  osquery-feed's short delivery, and the
  softflowd battery. Two dispositions
  recorded: send_dtls.main's return-5
  lines, missed by cycle 3's combine,
  are covered in this map (the Queue A
  test was the proof all along; the miss
  did not reproduce and is closed as a
  measure artifact -- one line, 126,
  remains in that file), and
  decode_datagram's except arm joins the
  recorded defensive set in the refreshed
  gaps header (docs/reports/v3.13.30/):
  no malformed datagram in the battery
  made a sub-parser raise. Cycle 3's
  tests are done by the Windows rule:
  build 40331267199 at 53e6c9bf completed
  success. Cycle 4's Windows verification
  waits on a completed build at a
  descendant head. The frontier at two
  or more missing is down to one live
  row -- port-watch's short delivery --
  over the recorded dead/defensive set,
  the wire rows (40000e00's), and the
  platform rows; below it, 170 statements
  remain, mostly single lines, and the
  compass turns to them and to branch
  arcs per Q59.
- rules refreshed 2026-10-26 07:40 PDT
  (standing orders incl. queue P, AGENTS.md
  rules 7-10, Q59-Q61, the playbook's hard
  rules). resources 2026-10-26T14:32:17Z: cores 2 | box cpu 49% | wall 27m46s | cmd cpu 22m46s = 0.8 cores busy | peak rss 456 MB | mem used 92% | disk free 165.4 GB | exit 0 | under-driven
- platinum 5: statements 99.6% (+0.1), branches
  97.5% (+0.3), 41 tests, 0 crashes filed,
  resources 2026-10-26T15:52:27Z: cores 2 | box cpu 53% | wall 38m06s | cmd cpu 34m07s = 0.9 cores busy | peak rss 455 MB | mem used 91% | disk free 165.4 GB | exit 0 | under-driven
  (under-driven is the single-process
  measure's shape.) Baseline 2006bdc2
  (99.4%, 170 missing); after 40cc8733
  (130 missing); the after-suite ran
  7,050 tests, OK (skipped=38). The whole
  two-line frontier closed (port-watch's
  short delivery last) and the one-line
  rows fell top-down: 40 statements and
  39 arcs. Five single lines were recorded
  dead by construction in the refreshed
  gaps header (docs/reports/v3.13.38/):
  send_job verify_body's shape check,
  hosting cli.main's trailing return,
  job-fuzz's blank-line guard, ensure_app's
  trailing return, load_retained's
  commonpath arm. The Windows leg of
  40cc8733 caught a real fault in the
  tests themselves: the zero-valued
  O_BINARY simulation replaced the
  platform's real flag and opened files
  in text mode; Claude (50000c8e) fixed
  the oracle copy in the release lane
  (4526d498) and Muse applied the same
  helper to the guard and oauth copies
  and POSIX-guarded the ps probe
  (40c3a3f1). Cycle 4's tests are done
  by the Windows rule: build 40336231565
  at 2006bdc2 completed success. Cycle
  5's Windows verification waits on a
  completed build at a descendant of
  40c3a3f1. The remaining live row at
  two or more missing is execute_job's
  script-shape refusal and staging trio,
  cycle 6's first targets; below it the
  map is single lines, the recorded set,
  the wire rows (40000e00's), and the
  platform rows.
- rules refreshed 2026-10-26 10:55 PDT
  (standing orders incl. queue P, AGENTS.md
  rules 7-10, the questions file's open
  entries, the playbook's hard rules).
  resources 2026-10-26T15:52:27Z: cores 2 | box cpu 53% | wall 38m06s | cmd cpu 34m07s = 0.9 cores busy | peak rss 455 MB | mem used 91% | disk free 165.4 GB | exit 0 | under-driven
- platinum 6: statements 99.6% (+0.0), branches
  97.6% (+0.1), 5 tests, 0 crashes filed,
  resources 2026-10-26T18:27:57Z: cores 2 | box cpu 55% | wall 24m33s | cmd cpu 21m57s = 0.9 cores busy | peak rss 468 MB | mem used 93% | disk free 165.4 GB | exit 0 | under-driven
  (under-driven is the single-process
  measure's shape; cycle 7 opens at once
  on the two uncredited pins and the
  one-line frontier.) Baseline 40cc8733
  (99.6%, 130 missing); after 61d4c77e
  (125 missing); the after-suite ran
  7,055 tests, OK (skipped=38). Nine
  statements closed gross: execute_job's
  staging trio (491, 492, 493),
  answer_queries' non-object arm (378),
  resend_stashed's base arm (1742), the
  QueuePipe pair (168, 189), and
  store_answer's pair (424, 425). Two
  pins the full-suite map does not
  credit stay live for cycle 7:
  execute_job's script-shape refusal
  (346) and _record_payload's payload
  arm (1939); targeted runs drive both,
  and the map is the score. Four
  rarely-hit arms the cycle-5 map showed
  covered read missing again (zeek-feed
  main's 682 and 688, personal_docs
  _walk's 209, verify_body_keyed's 743)
  and are recorded as map wobble in the
  refreshed gaps header
  (docs/reports/v3.13.42/), watched
  next cycle. Eight single lines were
  recorded dead by construction in the
  same header: sun_elevation_deg's
  hour-angle arm, sample_tree_ps's
  fallback entry, save_seen's merge,
  ensure_inference_ready's hostless arm,
  _oracle_instruction_kind's
  empty-words arm, _clean_rel_path's
  no-parts arm, the email transport's
  raw-payload fallback, and ask_model's
  second arm. Q62 trigger check: cycle 6
  closed new statements, so the trigger
  does not fire; queue P runs as written
  and section M (Project blueMonday)
  stands ready. Cycle 5's tests are
  done by the Windows rule: build
  40372240278 at 1011ad80 completed
  success. Cycle 6's likewise: build at
  afa70c22, a descendant of 61d4c77e,
  completed success.
- rules refreshed 2026-10-26 12:13 PDT
  (standing orders incl. queue P and the
  new section M, AGENTS.md rules 7-10,
  the questions file's open entries incl.
  Q62 as answered, the playbook's hard
  rules).
  resources 2026-10-26T18:27:57Z: cores 2 | box cpu 55% | wall 24m33s | cmd cpu 21m57s = 0.9 cores busy | peak rss 468 MB | mem used 93% | disk free 165.4 GB | exit 0 | under-driven
- blueMonday 1: 130 entries, 630 arcs, 0 crashes
  filed, resources 2026-10-26T19:42:36Z: cores 2 | box cpu 58% | wall 23s | cmd cpu 23s = 1.0 cores busy | peak rss 37 MB | mem used 95% | disk free 165.3 GB | exit 0 | under-driven
  (under-driven: the grow ran 23 seconds;
  what fills the box next is the seed
  step below, then a deeper grow.)
  Begun at the owner's word, ahead of
  Platinum's trigger; queue P still
  runs. Grow seed 6201, 2,000 rounds per
  target: no target gained an entry or
  an arc (wire 143, cloud 110, v2 54,
  crypto 205, local 118) and no crash
  was found; the seeded corpus already
  covers the arcs those rounds reach.
  Next per section M: the seed step —
  fixtures the suite builds that the
  tool's seed does not yet — then grow
  again at a larger depth.
- rules refreshed 2026-10-26 13:22 PDT
  (standing orders incl. queue P, section
  M, and the throughput recipe; AGENTS.md
  rules 7-11; the questions file's open
  entries incl. Q63; the playbook's hard
  rules).
  regression 56f9b408: 7112 tests green in 7m10s
  resources 2026-10-26T20:02:22Z: cores 2 | box cpu 69% | wall 7m12s | cmd cpu 6m24s = 0.9 cores busy | peak rss 263 MB | mem used 93% | disk free 165.3 GB | exit 0 | under-driven
  (under-driven is the pass's own shape:
  its shards are one process per core but
  the split-and-bisect steps are serial;
  no reds, so no bisect ran and no Q was
  filed.)
- rules refreshed 2026-10-26 13:31 PDT
  (standing orders incl. queue P, section
  M as b3538185 rewrote it — the grow is
  continuous — the throughput recipe,
  AGENTS.md rules 7-11, the questions
  file incl. Q63's answer, the playbook's
  hard rules, and the desk's misc entry
  of this hour: four fixes, all taken up
  in this commit and the next).
- blueMonday 1 (record rerun): 152 entries, 651 arcs, 0 crashes
  filed, resources 2026-10-26T20:31:49Z: cores 2 | box cpu 64% | wall 24s | cmd cpu 27s = 1.1 cores busy | peak rss 38 MB | mem used 95% | disk free 165.3 GB | exit 0 | under-driven
  (under-driven: the rerun is a
  record-keeping step, 2,000 rounds by
  the desk's prescription, done in 24
  seconds; the continuous deep grow is
  the throughput step and starts with
  this commit.) Grow 1 run again on the
  current tool at the conductor's word
  (seed 6201, 2,000 rounds, --jobs 2,
  all six targets incl. the new stash)
  so its record exists in the tree:
  runs.jsonl and the arc maps are
  committed with this line, a
  kept-nothing grow included, as every
  grow's will be from here. No target
  gained an entry or an arc; no crash.
  The deep grow runs continuously from
  here, one per the recipe, resuming
  whenever a measure or a pass frees
  the box.
- blueMonday 2: 157 entries, 651 arcs, 0 crashes
  filed. The deep grow (seed 6202, 50,000
  rounds, --jobs 2) was killed by a VM
  restart at about 13:39 PDT, so it has
  no resources line; the targets it
  finished wrote their keeps and run
  records before the kill and they are
  committed here (local +1 entry), with
  the seed step's nested-sig pair merged
  into wire and cloud (+2 each). Pass
  2's first launch died in 3s on this
  seat's uncommitted tree (its pull
  refused the dirty tool file); it is
  relaunched on this commit. From here
  the grow runs in the recipe's cycling
  shape: --rounds 20000 --minutes <until
  the next measure or pass>.
- rules refreshed 2026-10-26 14:23 PDT
  (standing orders incl. queue P, section
  M in the cycling-grow shape, the
  throughput recipe; AGENTS.md rules
  7-11; the questions file's open
  entries; the playbook's hard rules).
  regression 5dd6ae6f: 7122 tests green in 5m08s
  resources 2026-10-26T21:12:13Z: cores 2 | box cpu 72% | wall 5m10s | cmd cpu 5m38s = 1.1 cores busy | peak rss 283 MB | mem used 89% | disk free 165.3 GB | exit 0 | on target
  Pass 2, relaunched on a clean tree
  after its first launch died on this
  seat's dirty one; passes.jsonl is
  committed with this line, as every
  pass's will be. No reds.
- blueMonday 3: 171 entries, 653 arcs, 0 crashes
  filed. The first cycling grow in the
  recipe's shape (--rounds 20000
  --minutes 45, seed 6203): local yielded
  (+14 entries, +2 arcs; its text
  mutators are finding new shapes), the
  other five targets added nothing this
  run. Stopped at about 39 of its 45
  minutes at the conductor's word to
  yield the box to the cycle-7 measure;
  every finished cycle's records were
  already in the tree and are committed
  here, runs.jsonl included.
- rules refreshed 2026-10-26 15:07 PDT
  (standing orders incl. queue P,
  section M, the throughput recipe;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules). The conductor's new
  order stands at the head of the
  queue: blueMonday is the only effort;
  the hourly pass and the Platinum
  cycles are suspended until he lifts
  it. Cycle 7's measure, four minutes
  in, was stopped where it stood; its
  pins stay on main for the cycle's
  resume. The grow below runs alone
  from this line.
- rules refreshed 2026-10-26 16:09 PDT
  (standing orders incl. section M as
  the only effort at the conductor's
  order, the throughput recipe;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 4: 185 entries, 653 arcs, 0 crashes filed. The
  first full hour in the cycling shape
  (seed 6204): local yielded again
  (+14 entries, 38 to 52; the other
  five kept nothing). At the hour's
  end the desk's Q65 work had landed
  the seventh target, mail; grow 5
  below takes it up, and the saturated
  five ride the cycle at the desk's
  word while local and mail carry the
  search.
- rules refreshed 2026-10-26 17:20 PDT
  (standing orders incl. section M as
  the only effort, the blueMonday plan;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 5: 239 entries, 755 arcs, 0 crashes filed. The
  first grow on seven targets (seed
  6205, the full hour, on target at 83%
  box cpu): local yielded +20 entries
  (52 to 72) and is the one target the
  saturation mark does not claim; wire
  and cloud carry the desk's new seeds
  (39 and 38 entries) and read
  saturated with v2, crypto, stash and
  mail. Grok's targets (dtls, board,
  channels, manifest, the inbox pair)
  landed during this grow; grow 6
  takes the whole surface up.
- blueMonday 6: 445 entries, arcs in the
  tree, 0 crashes filed. The first grow
  over all thirteen targets was killed
  by a VM restart nineteen minutes in;
  the targets it finished had already
  written their keeps, committed here:
  dtls +2 entries and +5 arcs and
  manifest +1 on their first rig grow,
  local +1. Grok's targets read mostly
  saturated at 20,000 rounds on arrival;
  dtls and manifest are live. Grow 7
  below is the first under the steered
  tool with HP_BLUEMONDAY_ARCHIVE set
  to the directory set aside on this
  rig.
- rules refreshed 2026-10-26 18:56 PDT
  (standing orders incl. section M as
  the only effort, the blueMonday plan;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 7: 493 entries, 2569 arcs, 0 crashes filed. The
  first steered grow and the first with
  the archive drive recording (seed
  6207, the full hour): +4 entries
  banked (manifest +1, dtls +1, local
  +2) and +18 arcs, dtls +13 of them;
  982,375 children tried over its run
  records, all of them in the archive.
  The four live mutators carried the
  yield, as the steering intends.
  blueMonday 8: killed by a VM restart
  about 44 minutes into its hour (seed
  6208); the finished targets' keeps
  were already in the tree and are
  committed here — local +3 entries
  across the grow's cycles and dtls
  kept again. Its commit rides with
  grow 7's, which waited out a GitHub
  connection failure on this rig; both
  push together below.
- rules refreshed 2026-10-26 20:58 PDT
  (standing orders incl. section M as
  the only effort, the blueMonday plan;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 9: 650 entries, 2678 arcs, 0 crashes filed. A
  full steered hour on fifteen targets
  (seed 6211, the archive recording):
  +7 entries banked (manifest +3, local
  +2, dtls +1, board_ops +1) and +11
  arcs; 914,150 children tried over its
  run records, all of them in the
  archive. A fifteenth target, secret,
  stands in the tree now. The grow's
  own resources line reads on target
  (box cpu 84%, wall 1h01m).
- rules refreshed 2026-10-26 21:47 PDT
  (standing orders incl. section M as
  the only effort, the blueMonday plan;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 10: 650 entries, 2678 arcs, 0 crashes filed.
  Killed by a VM restart about 48
  minutes into its hour (seed 6220, the
  archive recording); the finished
  targets' records are committed here:
  no entry kept and no arc gained over
  its 40 run records, 622,110 children
  tried, all of them in the archive.
  The local target was mid-cycle when
  the box went down, and its cycle is
  not recorded. The dtls arc map the
  tool rewrote at the grow's start
  carries 309 arcs, the count its own
  run records carry; the 312-arc file
  it replaces came from grow 9's union
  merge. The survivors run after it
  counts 97 of 1,967 mutants surviving
  over 10 readers: board 18, dtlsproto
  0, extensions 0, jobcrypto 28,
  mailbox 1, protocol_v2 3, security 4,
  send_job 14, transports 18, verify 11.
- rules refreshed 2026-10-26 23:45 PDT
  (standing orders incl. section M as
  the only effort, the blueMonday plan;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 11: 689 entries, 2698 arcs, 0 crashes filed. A
  full steered run on fifteen targets
  (seed 6230, cycles to 6234, the
  archive recording), resources on
  target (box cpu 80%, wall 56m27s):
  +39 entries and +20 arcs. The grow's
  first cycle merged the desk's
  survivor seeds into the corpora, and
  that merge is most of the rise:
  cloud +5, v2 +12, wire +5, board_ops
  +9, inbox +5, local +3 entries (two
  of local's three the grow kept
  itself); the arcs came on board_ops
  (+11) and inbox (+9). 915,549
  children tried over its 60 run
  records, all of them in the archive.
  On the dtls arc map from grow 10's
  bank: the rebase union restored the
  312-arc file, and this grow's records
  carry dtls at 309 arcs again, the
  count the tool computes at this head.
  The survivors run after it counts 65
  of 1,970 mutants not killed over 10
  readers (64 survived, 1 timeout):
  board 5, dtlsproto 0, extensions 0,
  jobcrypto 28, mailbox 1, protocol_v2
  1, security 4, send_job 10,
  transports 7 (and the timeout),
  verify 8.
- rules refreshed 2026-10-27 01:33 PDT
  (standing orders incl. section M as
  the only effort, the blueMonday plan;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 12: 1042 entries, 4379 arcs, 4 crashes filed.
  A steered run on twenty targets
  (seed 6240, one full pass, the
  archive recording), resources on
  target (box cpu 82%, wall 1h05m),
  ended by the crash exit: the `query`
  target's checker broke its contract
  four times -- a `tail` answer whose
  lines are not the output's last
  lines, entries 62ae63868b862653,
  96f5bd62c49159c2, beaa8087f3aaab6f
  and c7d23c58c352c1ee, all by
  p_replace, written shrunk to
  query.crashes.jsonl and filed as
  Q90 to the desk. +353 entries and
  +1,681 arcs: five targets the desk
  added since grow 11 (queries, names,
  query, board_mail, v2_mail) brought
  322 seeded entries between them,
  seed merges on the older targets
  added 8, and the grow kept 23
  (query 8, v2_mail 7, board_mail 6,
  wire 1, local 1). 312,143 children
  tried over its 20 run records, all
  of them in the archive. The survivors
  run after it was still running at
  this bank -- the module set has
  outgrown the two-minute measure --
  so its record rides grow 13's bank.
- rules refreshed 2026-10-27 03:47 PDT
  (standing orders incl. section M as
  the only effort, the blueMonday plan;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 13: 1109 entries, 4624 arcs, 4 crashes filed.
  Two starts: the first (seed 6250) was
  killed by a VM restart about thirteen
  minutes in with nine target records
  banked in the tree and nothing kept;
  the relaunch (seed 6255) ran its full
  slot, resources on target (box cpu
  82%, wall 59m20s), and ended on the
  crash exit again -- the Q90 break on
  `query` four more times, entries
  52a3d2d17c1716ee, 6b7b77b5733f6ced,
  8599f401ca4094fa and 2dda176068286530,
  filed as Q91; the crashes file holds
  eight now. +67 entries and +245
  arcs: the Q87-Q89 flag and form seeds
  merged at this head (board_mail +18
  entries the largest), and the grow
  kept 11 (query 6, queries 2, v2_mail
  2, local 1). 396,887 children tried
  over its 27 run records, all of them
  in the archive. The grow-12 survivors
  run was killed by the same restart
  that took grow 13's first start,
  about eighteen minutes in and
  unfinished; it reruns beside grow 14
  and its record rides that bank.
- rules refreshed 2026-10-27 05:47 PDT
  (standing orders incl. section M as
  the only effort, the blueMonday plan;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 14: 1113 entries, 4631 arcs, 6 crashes filed.
  A steered run on twenty targets
  (seed 6260, one pass, the archive
  recording) sharing the box with the
  survivors rerun, resources on target
  (box cpu 79%, wall 1h18m), ended on
  the crash exit. Two shapes, filed
  together as Q92: on `queries`, a new
  exception class -- `answer_queries`
  raised OverflowError over a pattern
  whose repetition number is too
  large (entries a0593865f5a8114b and
  10cd337a428ea77a, both by p_text);
  on `query`, four new entries of the
  Q90 tail break (twelve in the file
  now), its record counting six
  crashes because two children shrank
  to entries already filed. The grow
  kept 4 (board_mail 2, local 1, query
  1); totals moved +4 entries and +7
  arcs. 241,076 children tried over
  its 17 run records, all of them in
  the archive. The survivors rerun
  beside it completed: 173 of 2,756
  mutants not killed over 15 readers
  (172 survived, 1 timeout) in
  4,496s: board 5, dtlsproto 0,
  extensions 0, filenames 5, handlers
  9, jobcrypto 28, mailbox 4, policy 0,
  protocol_v2 41, queries 34, security
  4, send_job 14, startup 4, transports
  7 (and the timeout), verify 17.
- rules refreshed 2026-10-27 06:57 PDT
  (standing orders incl. section M as
  the only effort, the blueMonday plan;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules).
  blueMonday 15: 1114 entries, 4631 arcs, 5 crashes filed.
  A steered run on twenty targets
  (seed 6270, one pass, the archive
  recording) at the last pre-fix head,
  resources on target (box cpu 82%,
  wall 1h00m), ended on the crash exit.
  All five crashes are on `query` and
  filed as Q93: two of the Q90 tail
  shape, one tail entry carrying a new
  detail line (a line the output does
  not have), and two of a new
  exception shape -- `handle_query_mail`
  raised over an unpaired UTF-16
  surrogate in the payload. Whether
  3.13.67's fixes already cover them
  is grow 16's first question; it runs
  at the fixed head. The desk's fix
  commit promoted the fourteen
  earlier crash entries, so this
  bank's crashes file carries only
  the five new ones. The grow kept 1
  (local); totals moved +1 entry and
  no arcs. 259,382 children tried over
  its 18 run records, all of them in
  the archive. The survivors run goes
  beside grow 16 and its record rides
  that bank.
- rules refreshed 2026-10-27 07:55 PDT
  (standing orders incl. section M
  under its new name, Project de_dust;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules). Q93 is answered by the
  desk in 3.13.68: the surrogate pair
  was the reader's, promote moved one
  of the five into the corpus and
  dropped four.
  de_dust 16: 1119 entries, 4638 arcs, 0 crashes filed.
  Grow 16 ran under the old tool in
  memory, per the desk's rename note
  (seed 6280, the archive recording),
  and the VM restarted at 07:51 PDT,
  killing it about 54 minutes in with
  15 of 20 targets recorded: 206,965
  children over its 15 run records.
  wire, cloud, query, board_mail and
  v2_mail were unrecorded when it
  died. It kept 1 (local, +2 arcs on
  that target) and merged the desk's
  four Q92 seeds on queries; totals
  moved +5 entries and +7 arcs. The
  wrapper's resources line never
  printed, so none is claimed. The
  survivors run beside it died in the
  same restart with no record
  (survivors.json unchanged); it is
  rerun after grow 17. Grow 17 starts
  on this bank with the new command
  and the new archive name,
  HP_DE_DUST_ARCHIVE. The box idled
  from the restart until this bank;
  that gap is the restart's, recorded
  here per Q58.
- rules refreshed 2026-10-27 09:32 PDT
  (standing orders incl. section M;
  AGENTS.md rules 7-11; the questions
  file's open entries, Q94 to the
  conductor and Q95 to the desk among
  them; the playbook's hard rules).
  de_dust 17: 1243 entries, 4804 arcs, 0 crashes filed.
  The first grow under the new name
  and command (seed 6290, the archive
  recording under HP_DE_DUST_ARCHIVE),
  resources on target (box cpu 80%,
  wall 1h06m). 259,687 children over
  18 run records; it kept 9 (query 8,
  local 1) and merged 134 of the
  desk's seeds across six targets
  (manifest 35, crypto 26, query 26,
  v2_mail 17, stash 9, local 1).
  Query's arcs re-measured 757 on the
  fixed reader and the grow added 17
  more there. The wire and cloud
  workers died in the tool itself --
  RecursionError in _paths, no run
  record for either target -- filed
  as Q95; the readers crashed zero
  times. The survivors rerun goes
  beside grow 18 and its record rides
  that bank. The box idled from the
  grow's landing (09:02 PDT) until
  this bank while the conductor's
  questions were answered; recorded
  per Q58.
- rules refreshed 2026-10-27 09:57 PDT
  (standing orders incl. section M;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules). Q95 is answered and
  fixed by the desk in 33547a42: the
  walks use a stack, a child past the
  bound is not a child, a raising
  mutator is counted, never a worker
  death.
  de_dust 18: 1243 entries, 4804 arcs, 0 crashes filed.
  Grow 18 (seed 6300, the archive
  recording) was killed by a VM
  restart at 09:51 PDT about 25
  minutes in: 12 of 20 targets
  recorded, 175,371 children, no
  keeps, totals unchanged. wire,
  cloud, local, queries, names,
  query, board_mail and v2_mail were
  unrecorded when it died. The
  survivors rerun beside it died in
  the same restart with no record;
  it goes beside grow 19 instead.
  Grow 19 (seed 6310) is the first
  grow on the Q95 fix, so wire and
  cloud meet the bounded walks there.
  The box idled from the restart
  until this bank; recorded per Q58.
- rules refreshed 2026-10-27 11:34 PDT
  (standing orders incl. section M;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules). Q94 is landed by the
  desk in 3.14.2 (fac08605): a key's
  default name is its fingerprint.
  de_dust 19: 1273 entries, 4946 arcs, 0 crashes filed.
  The first grow on the Q95 fix
  (seed 6310, the archive recording),
  resources on target (box cpu 84%,
  wall 1h30m sharing the box with the
  survivors rerun). 278,474 children
  over 19 run records; wire and
  cloud both completed -- the two
  workers the tool killed in grow 17
  -- and merged 14 seeds each, the
  Q89/Q90 seeds the desk named. It
  kept 2 (local 1, query 1); totals
  moved +30 entries and +142 arcs.
  v2_mail wrote no record before the
  minutes ran out. The survivors
  rerun beside it was stopped at
  this bank, about 95 minutes in
  with no record written, because
  3.14.2 changed the very modules
  it measures (the fingerprint code
  is new surface); a fresh pass
  starts beside grow 20 on the new
  head and its record rides that
  bank. Grow 20 is the
  first to merge the fingerprint
  seeds from 3.14.2, and Q96 files
  five unit-test suggestions for
  the key-name surface.
- de_dust 20: 1281 entries, 4962 arcs, 0 crashes filed.
  Seed 3184850390, 12 minutes, one
  target at a time. Five targets
  finished (wire, cloud, v2, crypto,
  local); the minutes ran out on
  local. resources over (box cpu 100%,
  wall 12m45s, 1.0 cores busy, peak
  rss 71 MB). Kept 1 (local, t_insert,
  db68e03562b577a5) and merged seeds
  on wire, cloud and crypto. Totals
  moved +8 entries and +16 arcs.
  No crashes.
- rules refreshed 2026-10-27 15:00 PDT.
  The second rig is up: Hetzner Cloud,
  Nuremberg, 1 vCPU AMD EPYC-Genoa,
  917 MiB, Fedora 44, Python 3.14.7.
  The address is not written down.
  resources 2026-10-27T22:00:43Z: cores 1 | box cpu 100% | wall 1m00s | cmd - | peak rss n/a | mem used 48% | disk free 17.7 GB | exit - | over
  resources-top: python 60 MB, python3 53 MB, python 53 MB, python3 33 MB, NetworkManager 20 MB
  Grow 21 is in flight (seed
  3180357378, 55 minutes, one target
  at a time) and was on board_mail at
  the sample. local kept one entry and
  two arcs; stash and query kept
  entries and no arc. No crashes.
  The same box polls the one-tenant
  Cloudflare Worker. The facts are
  docs/reports/rig-2026-10-27.md.
- rules refreshed 2026-10-27 12:16 PDT
  (standing orders incl. section M;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules). The desk is 40000e00
  from today (50000c8e recycled), and
  Q96's five key-name promises are
  pinned in 191d41a6.
  de_dust 20: 1285 entries, 4956 arcs, 0 crashes filed.
  Grow 20 (seed 6320, the archive
  recording), the first grow on the
  3.14.2 tree and the first to merge
  the fingerprint seeds, was killed
  by a VM restart at 11:51 PDT about
  18 minutes in: 9 of 20 targets
  recorded, 145,985 children. It
  merged 12 seeds (cloud 2, wire 2,
  crypto 3, stash 5) and kept none
  of its own; totals moved +12
  entries and +10 arcs. The fresh
  survivors pass beside it died in
  the same restart with no record;
  it restarts beside grow 21. The
  box idled from the restart until
  this bank; recorded per Q58.
  Grow 21 (seed 6330) follows.
- rules refreshed 2026-10-27 15:03 PDT
  (standing orders incl. section M;
  AGENTS.md rules 7-11; the questions
  file's open entries; the playbook's
  hard rules). A correction to grow
  20's line above: the Q96 pinning it
  names as 191d41a6 was Grok's
  original commit; the desk re-landed
  that work in the 60a3f3a2 chain and
  it is on main in that form.
  de_dust 21: 1292 entries, 4978 arcs, 1 crash filed.
  Grow 21 (seed 6330, the archive
  recording) ran on target (box cpu
  82%, wall 1h33m sharing the box)
  and exited 1 on the crash: 279,836
  children over 19 run records; it
  merged 5 seeds (query 3, board_mail
  2) and kept 2 (local 1, board_mail
  1). v2_mail wrote no record before
  the minutes ran out, the second
  grow in a row it sat at the end of
  the rotation. The crash is the
  first on board_mail: entry
  c5309423121a8b50, a p_splice child
  whose task_request carries
  capabilities as the bare string
  "shell", and the board's contract
  answers "a task offered is not
  claimed on the board" -- filed as
  Q97; the entry rides in
  board_mail.crashes.jsonl as the
  expected-failure probe. The
  survivors pass beside it completed:
  87 of 2,986 mutants not killed
  over 15 modules in 7,039s
  (per-module counts in
  survivors.json; protocol_v2 and
  queries, the two largest counts in
  grow 14's pass, are at 0 after the
  Q89/Q92/Q93 fixes). The box idled
  from that pass's end (14:13) until
  this bank; recorded per Q58.
  Grow 22 (seed 6340) follows.
- rules refreshed 2026-10-27 16:40 PDT
  (standing orders incl. section M
  as amended today; AGENTS.md rules
  7-11 in their fresh copy; the
  questions file's open entries).
  de_dust 22 (VM rig): 1293 entries, 4978 arcs, 0 crashes filed.
  Grow 22 (seed 6340) ran on target
  (box cpu 82%, wall 1h33m21s):
  278,430 children over 19 run
  records; it kept 1 (local,
  198fc93a4fa0e163), whose arcs the
  merged tree already covered, so
  the totals move by the entry
  alone -- the first bank under
  the section M item 7 contract,
  totals from stats on the merged
  tree. v2_mail wrote no record,
  the third grow in a row it sat
  at the end of the rotation. The
  survivors pass beside it was
  still running at this bank; its
  record rides grow 23's bank. The
  box ran that pass alone for the
  six minutes between this grow's
  end and grow 23's launch, at
  this seat's sequencing of the
  conductor's doc work; recorded
  per Q58. Grow 23 (seed 6350)
  follows.
- rules refreshed 2026-10-27 18:52 PDT
  (standing orders incl. section M;
  AGENTS.md rules 7-11; the
  questions file's open entries).
  de_dust 23 (VM rig): 1294 entries, 4978 arcs, 0 crashes filed.
  Grow 23 (seed 6350, in two
  fragments: the 16:46 restart
  killed the first at five minutes
  and the relaunch ran the seed
  again) ran on target (box cpu
  85%, wall 1h31m32s): 278,863
  children over 19 run records; it
  kept 1 (local,
  b53ba7c18a8ca2fa), whose arcs
  the merged tree already covered,
  as in grow 22. v2_mail wrote no
  record, the fourth grow in a row
  at the end of the rotation. The
  survivors pass beside it
  completed: 87 of 2,985 mutants
  not killed over 15 modules in
  7,122s (per-module counts in
  survivors.json). The box ran
  that pass alone from this grow's
  end (18:18) and stood idle from
  its end (18:46) until grow 24's
  launch at this bank, at this
  seat's sequencing of the
  conductor's Germany-box
  handover; recorded per Q58.
  Grow 24 (seed 6360) follows.
  de_dust 1 (Germany rig): 1318 entries, 4977 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 71,355 children (seeds 325569674); totals from the merged tree.
  de_dust 2 (Germany rig): 1322 entries, 4993 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 9 run records, 139,626 children (seeds 325569674); totals from the merged tree.
  de_dust 3 (Germany rig): 1346 entries, 5006 arcs, 8 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 33,132 children (seeds 325569674); totals from the merged tree.
  de_dust 4 (Germany rig): 1365 entries, 5183 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,400 children (seeds 325569674); totals from the merged tree.
  de_dust 5 (Germany rig): 1366 entries, 5186 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 71,259 children (seeds 4039647050); totals from the merged tree.
  de_dust 6 (Germany rig): 1367 entries, 5186 arcs, 5 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 173,020 children (seeds 4039647050); totals from the merged tree.
  de_dust 1 (San Francisco rig): 1367 entries, 5186 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,998 children (seeds 596442135); totals from the merged tree.
  de_dust 7 (Germany rig): 1369 entries, 5187 arcs, 11 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 18 run records, 261,276 children (seeds 2167398487); totals from the merged tree.
  de_dust 8 (Germany rig): 1369 entries, 5187 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 71,386 children (seeds 2990799610); totals from the merged tree.
  de_dust 2 (San Francisco rig): 1369 entries, 5188 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 53,231 children (seeds 596442135); totals from the merged tree.
  de_dust 9 (Germany rig): 1370 entries, 5188 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 8 run records, 121,436 children (seeds 2990799610); totals from the merged tree.
  de_dust 10 (Germany rig): 1372 entries, 5214 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 51,749 children (seeds 2990799610); totals from the merged tree.
  de_dust 3 (San Francisco rig): 1371 entries, 5214 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,682 children (seeds 596442135); totals from the merged tree.
  de_dust 11 (Germany rig): 1373 entries, 5226 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 34,875 children (seeds 2990799610); totals from the merged tree.
  de_dust 4 (San Francisco rig): 1373 entries, 5223 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 53,214 children (seeds 3488519944); totals from the merged tree.
  de_dust 12 (Germany rig): 1373 entries, 5222 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 71,382 children (seeds 3092090704); totals from the merged tree.
  de_dust 5 (San Francisco rig): 1373 entries, 5223 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,084 children (seeds 3488519944); totals from the merged tree.
  de_dust 13 (Germany rig): 1376 entries, 5223 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 173,133 children (seeds 3092090704); totals from the merged tree.
  de_dust 6 (San Francisco rig): 1376 entries, 5223 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,641 children (seeds 3488519944); totals from the merged tree.
  de_dust 14 (Germany rig): 1377 entries, 5226 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,031 children (seeds 3092090704); totals from the merged tree.
  de_dust 15 (Germany rig): 1379 entries, 5234 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,846 children (seeds 3092090704); totals from the merged tree.
  de_dust 16 (Germany rig): 1379 entries, 5237 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 53,365 children (seeds 1055618579); totals from the merged tree.
- rules refreshed 2026-10-27 22:02 PDT
  (standing orders incl. section M;
  AGENTS.md rules 7-11; the
  questions file's open entries).
  de_dust 24 (VM rig): 1295
  entries, 4978 arcs, 0 crashes
  filed. Grow 24 (seed 6360, in
  three fragments: the 18:54 PDT
  restart killed the first
  minutes in, a brief
  improvised-seed relaunch died
  with its session, and the
  disciplined relaunch under
  seed 6360 at 20:01 PDT ran to
  completion) ran on target (box
  cpu 84%, wall 1h32m30s):
  278,328 children over 19 run
  records; it kept 1 (local,
  54ba8989fb9c75e1), whose arcs
  the merged tree already
  covered, as in grows 22 and
  23. v2_mail wrote no record,
  the fifth grow in a row at
  the end of the rotation. The
  survivors pass beside it left
  no record: the 21:39 PDT
  restart killed it before it
  wrote, and survivors.json is
  unchanged; the pass runs
  beside grow 25. After the
  grow completed (21:32 PDT)
  the box stood idle through
  the restart and this bank
  until grow 25's launch at
  this bank; recorded per Q58.
  Grow 25 (seed 6370) follows.
- rules refreshed 2026-10-28 07:23 PDT
  (standing orders incl. section M;
  AGENTS.md rules 7-11; the
  questions file's open entries).
  de_dust 25 (VM rig): 1296
  entries, 4978 arcs, 0 crashes
  filed. Grow 25 (seed 6370, a
  single fragment) ran on target
  (box cpu 89%, wall 1h26m41s):
  259,869 children over 18 run
  records; it kept 1 (local,
  f28150d3593f63c6), whose arcs
  the merged tree already
  covered, as in grows 22 to 24.
  board_mail and v2_mail both
  wrote no record, the minutes
  ending after query; v2_mail's
  sixth miss in a row. The
  survivors pass beside it left
  no record again, the 05:58 PDT
  restart ending it, and
  survivors.json is unchanged;
  the pass runs beside grow 26.
  After the grow completed
  (23:24 PDT) the box stood idle
  through the restart until
  grow 26's launch at this bank;
  recorded per Q58. Two targets
  join the rotation at the
  desk's word (80000aeb, in
  .com.chat): stage and collect,
  with Q101's seeds in the tool
  for queries, wire, cloud and
  names. Grow 26 was launched
  from the stale tree at this
  bank and is relaunched onto
  the refreshed tree in the same
  hour, so the new targets grow
  from grow 26. Grow 26 (seed
  6380) follows.
- rules refreshed 2026-10-28 11:19 PDT
  de_dust 26 (VM rig): 1379 entries, 5237 arcs, 11 crashes filed.
  Three fragments: the first launch
  left from the stale tree and was
  killed in minutes; the second, on
  the refreshed tree, died in the
  07:53 VM restart about 28 minutes
  in; the third ran to completion
  (exit 1, on target) at 10:33 PDT:
  436,019 children over 29 records,
  keeping queries 20, query 15,
  wire 12, cloud 11, names 4,
  board 1, board_ops 1, local 1.
  Final fragment resources: box
  cpu 90%, wall 1h37m59s. Twelve
  crashes on queries (9 leak,
  3 contract): eleven filed as
  Q108; one, 2dbed86052899832, was
  already retired by the desk and
  is not re-banked — a retired
  crash stays retired; Q108
  carries the recurrence. The grow
  ran on code from before the
  desk's Q106 fix, which landed
  while its last fragment ran.
  Idle, per Q58: 07:53 to 08:56
  (the restart, until the
  relaunch), and 10:33 to grow
  27's launch (completion, then
  the 10:43 restart, then the
  relaunch once the fall was
  seen). The bank itself waited
  on GitHub egress, down when
  the seat woke. Grow 27 (seed
  6390) follows.
  de_dust 7 (San Francisco rig): 1379 entries, 5234 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 71,438 children (seeds 4170776654); totals from the merged tree.
  de_dust 17 (Germany rig): 1381 entries, 5234 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 9 run records, 138,477 children (seeds 1055618579); totals from the merged tree.
  de_dust 18 (Germany rig): 1381 entries, 5234 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 51,673 children (seeds 1055618579); totals from the merged tree.
  de_dust 8 (San Francisco rig): 1381 entries, 5234 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,616 children (seeds 4170776654); totals from the merged tree.
  de_dust 9 (San Francisco rig): 1415 entries, 5326 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 14,339 children (seeds 2401973103); totals from the merged tree.
  de_dust 19 (Germany rig): 1416 entries, 5327 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 34,084 children (seeds 1055618579); totals from the merged tree.
  de_dust 10 (San Francisco rig): 1433 entries, 5392 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,943 children (seeds 2401973103); totals from the merged tree.
  de_dust 20 (Germany rig): 1436 entries, 5437 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,935 children (seeds 1082089938); totals from the merged tree.
  de_dust 21 (Germany rig): 1439 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 16 run records, 226,559 children (seeds 1082089938); totals from the merged tree.
  de_dust 11 (San Francisco rig): 1439 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,761 children (seeds 2401973103); totals from the merged tree.
  de_dust 22 (Germany rig): 1439 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 16,676 children (seeds 1082089938); totals from the merged tree.
  de_dust 23 (Germany rig): 1442 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 16,742 children (seeds 1082089938); totals from the merged tree.
  de_dust 24 (Germany rig): 1442 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 8,856 children (seeds 4245348535); totals from the merged tree.
  de_dust 25 (Germany rig): 1444 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 208,617 children (seeds 4245348535); totals from the merged tree.
  de_dust 12 (San Francisco rig): 1444 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 16,570 children (seeds 2401973103); totals from the merged tree.
  de_dust 26 (Germany rig): 1444 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 51,678 children (seeds 4245348535); totals from the merged tree.
  de_dust 13 (San Francisco rig): 1444 entries, 5437 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 51,812 children (seeds 1600551667); totals from the merged tree.
  de_dust 27 (Germany rig): 1444 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,313 children (seeds 4245348535); totals from the merged tree.
  de_dust 28 (Germany rig): 1444 entries, 5437 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 16,811 children (seeds 4245348535); totals from the merged tree.
  de_dust 29 (Germany rig): 1445 entries, 5437 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 61,258 children (seeds 1819443757); totals from the merged tree.
  de_dust 14 (San Francisco rig): 1445 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,287 children (seeds 1600551667); totals from the merged tree.
  de_dust 30 (Germany rig): 1445 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 14 run records, 210,302 children (seeds 1819443757); totals from the merged tree.
  de_dust 31 (Germany rig): 1445 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,003 children (seeds 1819443757); totals from the merged tree.
  de_dust 15 (San Francisco rig): 1445 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 53,306 children (seeds 1506096620); totals from the merged tree.
  de_dust 32 (Germany rig): 1445 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 16,034 children (seeds 945808191); totals from the merged tree.
  de_dust 16 (San Francisco rig): 1445 entries, 5431 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 8 run records, 121,587 children (seeds 1506096620); totals from the merged tree.
  de_dust 33 (Germany rig): 1445 entries, 5431 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,229 children (seeds 945808191); totals from the merged tree.
  de_dust 17 (San Francisco rig): 1445 entries, 5429 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 51,222 children (seeds 1506096620); totals from the merged tree.
  de_dust 34 (Germany rig): 1447 entries, 5430 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 27,093 children (seeds 945808191); totals from the merged tree.
  de_dust 35 (Germany rig): 1447 entries, 5430 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 52,474 children (seeds 945808191); totals from the merged tree.
  de_dust 18 (San Francisco rig): 1446 entries, 5429 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 27,295 children (seeds 825462592); totals from the merged tree.
  de_dust 36 (Germany rig): 1446 entries, 5437 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 12 run records, 175,008 children (seeds 652219259); totals from the merged tree.
  de_dust 6 (VM rig): 1440 entries, 5414 arcs, 19 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 38 run records, 558,153 children (seeds 6390, 6410); totals from the merged tree.
  de_dust 37 (Germany rig): 1442 entries, 5424 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 69,084 children (seeds 652219259); totals from the merged tree.
  de_dust 38 (Germany rig): 1443 entries, 5424 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,166 children (seeds 652219259); totals from the merged tree.
  de_dust 19 (San Francisco rig): 1447 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,750 children (seeds 825462592); totals from the merged tree.
  de_dust 39 (Germany rig): 1447 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 34,875 children (seeds 2524065481); totals from the merged tree.
  de_dust 20 (San Francisco rig): 1447 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,005 children (seeds 410049539); totals from the merged tree.
  de_dust 40 (Germany rig): 1449 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 185,594 children (seeds 2524065481); totals from the merged tree.
  de_dust 41 (Germany rig): 1453 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,007 children (seeds 2524065481); totals from the merged tree.
  de_dust 42 (Germany rig): 1453 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,607 children (seeds 2524065481); totals from the merged tree.
  de_dust 21 (San Francisco rig): 1453 entries, 5442 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,867 children (seeds 410049539); totals from the merged tree.
  de_dust 43 (Germany rig): 1453 entries, 5442 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 51,187 children (seeds 2856575849); totals from the merged tree.
  de_dust 22 (San Francisco rig): 1453 entries, 5440 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 35,655 children (seeds 987217947); totals from the merged tree.
  de_dust 7 (VM rig): 1456 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 14 run records, 196,851 children (seeds 6420); totals from the merged tree.
  de_dust 44 (Germany rig): 1457 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 54,410 children (seeds 2856575849); totals from the merged tree.
  de_dust 23 (San Francisco rig): 1457 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 15,706 children (seeds 987217947); totals from the merged tree.
  de_dust 45 (Germany rig): 1457 entries, 5441 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 185,008 children (seeds 2856575849); totals from the merged tree.
  de_dust 46 (Germany rig): 1457 entries, 5441 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,259 children (seeds 2856575849); totals from the merged tree. Retired echoes not re-banked: 18.
  de_dust 24 (San Francisco rig): 1457 entries, 5441 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,053 children (seeds 987217947); totals from the merged tree. Retired echoes not re-banked: 18.
  de_dust 47 (Germany rig): 1457 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 52,884 children (seeds 3504968364); totals from the merged tree.
  de_dust 48 (Germany rig): 1459 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 69,478 children (seeds 3504968364); totals from the merged tree.
  de_dust 49 (Germany rig): 1460 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,538 children (seeds 3504968364); totals from the merged tree.
  de_dust 25 (San Francisco rig): 1460 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,418 children (seeds 2186709487); totals from the merged tree.
  de_dust 50 (Germany rig): 1460 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 12 run records, 166,510 children (seeds 3482541060); totals from the merged tree. The rig's tree at 564c3a1217b7.
  de_dust 26 (San Francisco rig): 1460 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 7 run records, 95,246 children (seeds 3431053483); totals from the merged tree. The rig's tree at c57d7c3fc1ab.
  de_dust 51 (Germany rig): 1460 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,193 children (seeds 3482541060); totals from the merged tree. The rig's tree at 564c3a1217b7.
  de_dust 27 (San Francisco rig): 1460 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 71,398 children (seeds 3431053483); totals from the merged tree. The rig's tree at c57d7c3fc1ab.
  de_dust 52 (Germany rig): 1461 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 52,975 children (seeds 3482541060); totals from the merged tree. The rig's tree at 564c3a1217b7.
  de_dust 53 (Germany rig): 1463 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,444 children (seeds 3482541060); totals from the merged tree. The rig's tree at 564c3a1217b7.
  de_dust 54 (Germany rig): 1463 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 51,675 children (seeds 695550880); totals from the merged tree. The rig's tree at 8557100d053c.
  de_dust 28 (San Francisco rig): 1463 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,305 children (seeds 3431053483); totals from the merged tree. The rig's tree at c57d7c3fc1ab.
  de_dust 55 (Germany rig): 1463 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,677 children (seeds 695550880); totals from the merged tree. The rig's tree at 8557100d053c.
  de_dust 56 (Germany rig): 1463 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 185,123 children (seeds 695550880); totals from the merged tree. The rig's tree at 8557100d053c.
  de_dust 57 (Germany rig): 1463 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,234 children (seeds 695550880); totals from the merged tree. The rig's tree at 8557100d053c.
  de_dust 58 (Germany rig): 1463 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 35,588 children (seeds 3720707706); totals from the merged tree. The rig's tree at 3d7cb8c851ad.
  de_dust 8 (VM rig): 1463 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 15 run records, 219,639 children (seeds 6450); totals from the merged tree. The rig's tree at 44760ca6f99f.
  de_dust 29 (San Francisco rig): 1463 entries, 5442 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,765 children (seeds 1197031845); totals from the merged tree. The rig's tree at ec9cbd848373.
  de_dust 30 (San Francisco rig): 1463 entries, 5442 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 16,980 children (seeds 1197031845); totals from the merged tree. The rig's tree at ec9cbd848373.
  de_dust 59 (Germany rig): 1464 entries, 5442 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 68,611 children (seeds 3720707706); totals from the merged tree. The rig's tree at 3d7cb8c851ad.
  de_dust 60 (Germany rig): 1464 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,602 children (seeds 3720707706); totals from the merged tree. The rig's tree at 3d7cb8c851ad.
  de_dust 61 (Germany rig): 1464 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,108 children (seeds 3720707706); totals from the merged tree. The rig's tree at 3d7cb8c851ad.
  de_dust 62 (Germany rig): 1464 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 167,593 children (seeds 4256339315); totals from the merged tree. The rig's tree at af016b77fda2.
  de_dust 31 (San Francisco rig): 1464 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 50,758 children (seeds 1712848612); totals from the merged tree. The rig's tree at 02325d1cac73.
  de_dust 32 (San Francisco rig): 1464 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,125 children (seeds 1712848612); totals from the merged tree. The rig's tree at 02325d1cac73.
  de_dust 63 (Germany rig): 1465 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 50,622 children (seeds 4256339315); totals from the merged tree. The rig's tree at af016b77fda2.
  de_dust 64 (Germany rig): 1465 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 52,601 children (seeds 4256339315); totals from the merged tree. The rig's tree at af016b77fda2.
  de_dust 65 (Germany rig): 1465 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,169 children (seeds 4256339315); totals from the merged tree. The rig's tree at af016b77fda2.
  de_dust 66 (Germany rig): 1465 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 15 run records, 203,505 children (seeds 1488553207); totals from the merged tree. The rig's tree at bff08e32b1cd.
  de_dust 33 (San Francisco rig): 1465 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,422 children (seeds 345452527); totals from the merged tree. The rig's tree at 3dc3ab7355a6.
  de_dust 34 (San Francisco rig): 1465 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 0 run records, 0 children (seeds none recorded); totals from the merged tree. The rig's tree at 3dc3ab7355a6.
  de_dust 9 (VM rig): 1464 entries, 5444 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 20 run records, 289,649 children (seeds 6460); totals from the merged tree. The rig's tree at 67328341d078.
  de_dust 67 (Germany rig): 1467 entries, 5444 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 50,882 children (seeds 1488553207); totals from the merged tree. The rig's tree at bff08e32b1cd.
  de_dust 68 (Germany rig): 1467 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,458 children (seeds 1488553207); totals from the merged tree. The rig's tree at bff08e32b1cd.
  de_dust 69 (Germany rig): 1467 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,151 children (seeds 3984525775); totals from the merged tree. The rig's tree at 612b8d99de88.
  de_dust 70 (Germany rig): 1467 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 14 run records, 185,473 children (seeds 3984525775); totals from the merged tree. The rig's tree at 612b8d99de88.
  de_dust 35 (San Francisco rig): 1467 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,279 children (seeds 4271464405); totals from the merged tree. The rig's tree at 3f72bf6a5d51.
  de_dust 36 (San Francisco rig): 1467 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 15,657 children (seeds 4271464405); totals from the merged tree. The rig's tree at 3f72bf6a5d51.
  de_dust 71 (Germany rig): 1467 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,021 children (seeds 3984525775); totals from the merged tree. The rig's tree at 612b8d99de88.
  de_dust 72 (Germany rig): 1469 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,458 children (seeds 3984525775); totals from the merged tree. The rig's tree at 612b8d99de88.
  de_dust 10 (VM rig): 1469 entries, 5438 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 14 run records, 214,927 children (seeds 6470); totals from the merged tree. The rig's tree at d88a3bff247a.
  de_dust 73 (Germany rig): 1469 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,002 children (seeds 3984525775); totals from the merged tree. The rig's tree at 612b8d99de88.
  de_dust 37 (San Francisco rig): 1469 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,108 children (seeds 1637030575); totals from the merged tree. The rig's tree at ef9fafda6020.
  de_dust 74 (Germany rig): 1469 entries, 5436 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 8 run records, 109,655 children (seeds 1296862092); totals from the merged tree. The rig's tree at 5b4cada208ac.
  de_dust 75 (Germany rig): 1469 entries, 5440 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 8 run records, 111,840 children (seeds 1296862092); totals from the merged tree. The rig's tree at 5b4cada208ac.
  de_dust 76 (Germany rig): 1472 entries, 5440 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,576 children (seeds 1296862092); totals from the merged tree. The rig's tree at 5b4cada208ac.
  de_dust 77 (Germany rig): 1472 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 67,830 children (seeds 2378320578); totals from the merged tree. The rig's tree at 600ea7d61741.
  de_dust 78 (Germany rig): 1472 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,051 children (seeds 2378320578); totals from the merged tree. The rig's tree at 600ea7d61741.
  de_dust 38 (San Francisco rig): 1472 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,358 children (seeds 3377499294); totals from the merged tree. The rig's tree at 3f1aaebc6a7a.
  de_dust 79 (Germany rig): 1472 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 8 run records, 109,700 children (seeds 2378320578); totals from the merged tree. The rig's tree at 600ea7d61741.
  de_dust 39 (San Francisco rig): 1472 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 57,128 children (seeds 3261792750); totals from the merged tree. The rig's tree at 17efc7d8973e.
  de_dust 80 (Germany rig): 1472 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,114 children (seeds 2378320578); totals from the merged tree. The rig's tree at 600ea7d61741.
  de_dust 81 (Germany rig): 1472 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 7 run records, 93,461 children (seeds 1809112833); totals from the merged tree. The rig's tree at a9f9f42677a2.
  de_dust 40 (San Francisco rig): 1472 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,195 children (seeds 3261792750); totals from the merged tree. The rig's tree at 17efc7d8973e.
  de_dust 82 (Germany rig): 1473 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 85,061 children (seeds 1809112833); totals from the merged tree. The rig's tree at a9f9f42677a2.
  de_dust 11 (VM rig): 1473 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 10 run records, 145,882 children (seeds 6480); totals from the merged tree. The rig's tree at 531fe8389711.
  de_dust 83 (Germany rig): 1473 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,920 children (seeds 1809112833); totals from the merged tree. The rig's tree at a9f9f42677a2.
  de_dust 84 (Germany rig): 1473 entries, 5442 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 29,083 children (seeds 1809112833); totals from the merged tree. The rig's tree at a9f9f42677a2.
  de_dust 85 (Germany rig): 1473 entries, 5444 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 7 run records, 79,552 children (seeds 104989031); totals from the merged tree. The rig's tree at db33b4109119.
  de_dust 41 (San Francisco rig): 1473 entries, 5444 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,153 children (seeds 3261792750); totals from the merged tree. The rig's tree at 17efc7d8973e.
  de_dust 42 (San Francisco rig): 1473 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 59,405 children (seeds 2241303255); totals from the merged tree. The rig's tree at 73b7678df593.
  de_dust 86 (Germany rig): 1473 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 6 run records, 94,745 children (seeds 104989031); totals from the merged tree. The rig's tree at db33b4109119.
  de_dust 43 (San Francisco rig): 1473 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,156 children (seeds 2241303255); totals from the merged tree. The rig's tree at 73b7678df593.
  de_dust 87 (Germany rig): 1474 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 6 run records, 103,122 children (seeds 104989031); totals from the merged tree. The rig's tree at db33b4109119.
  de_dust 12 (VM rig): 1474 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 57,448 children (seeds 6490); totals from the merged tree. The rig's tree at d53ec9ec32d5.
  de_dust 88 (Germany rig): 1474 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,907 children (seeds 104989031); totals from the merged tree. The rig's tree at db33b4109119.
  de_dust 44 (San Francisco rig): 1474 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,464 children (seeds 2241303255); totals from the merged tree. The rig's tree at 73b7678df593.
  de_dust 89 (Germany rig): 1474 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 10 run records, 128,759 children (seeds 1030205404); totals from the merged tree. The rig's tree at f90593ef0fe8.
  de_dust 90 (Germany rig): 1475 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 9 run records, 141,667 children (seeds 1030205404); totals from the merged tree. The rig's tree at f90593ef0fe8.
  de_dust 91 (Germany rig): 1475 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,092 children (seeds 1030205404); totals from the merged tree. The rig's tree at f90593ef0fe8.
  de_dust 92 (Germany rig): 1475 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,952 children (seeds 1104520892); totals from the merged tree. The rig's tree at 8e0e01620e90.
  de_dust 45 (San Francisco rig): 1475 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,368 children (seeds 734365719); totals from the merged tree. The rig's tree at 1fabe68345b9.
  de_dust 93 (Germany rig): 1475 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,909 children (seeds 1104520892); totals from the merged tree. The rig's tree at 8e0e01620e90.
  de_dust 94 (Germany rig): 1475 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 10 run records, 128,929 children (seeds 1104520892); totals from the merged tree. The rig's tree at 8e0e01620e90.
  de_dust 95 (Germany rig): 1477 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 52,576 children (seeds 1104520892); totals from the merged tree. The rig's tree at 8e0e01620e90.
  de_dust 13 (VM rig): 1475 entries, 5443 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 16 run records, 231,508 children (seeds 6500); totals from the merged tree. The rig's tree at 8abc436cfb11.
  de_dust 96 (Germany rig): 1476 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 6 run records, 89,064 children (seeds 4074980453); totals from the merged tree. The rig's tree at faa9e7a808a5.
  de_dust 46 (San Francisco rig): 1476 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 51,338 children (seeds 2249485095); totals from the merged tree. The rig's tree at 1180bd9fce98.
  de_dust 97 (Germany rig): 1476 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 36,041 children (seeds 4074980453); totals from the merged tree. The rig's tree at faa9e7a808a5.
  de_dust 98 (Germany rig): 1476 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,999 children (seeds 4074980453); totals from the merged tree. The rig's tree at faa9e7a808a5.
  de_dust 99 (Germany rig): 1476 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 50,658 children (seeds 4074980453); totals from the merged tree. The rig's tree at faa9e7a808a5.
  de_dust 100 (Germany rig): 1476 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 6 run records, 78,455 children (seeds 3205762444); totals from the merged tree. The rig's tree at fac5788bb47e.
  de_dust 47 (San Francisco rig): 1476 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,066 children (seeds 1816900537); totals from the merged tree. The rig's tree at a1be79fe9f0e.
  de_dust 48 (San Francisco rig): 1476 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,882 children (seeds 1816900537); totals from the merged tree. The rig's tree at a1be79fe9f0e.
  de_dust 101 (Germany rig): 1480 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 9 run records, 141,550 children (seeds 3205762444); totals from the merged tree. The rig's tree at fac5788bb47e.
  de_dust 49 (San Francisco rig): 1480 entries, 5446 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,194 children (seeds 694476710); totals from the merged tree. The rig's tree at 3346b4352842.
  de_dust 102 (Germany rig): 1480 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,939 children (seeds 3205762444); totals from the merged tree. The rig's tree at fac5788bb47e.
  de_dust 103 (Germany rig): 1480 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,921 children (seeds 3205762444); totals from the merged tree. The rig's tree at fac5788bb47e.
  de_dust 104 (Germany rig): 1480 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 6 run records, 69,287 children (seeds 2014598281); totals from the merged tree. The rig's tree at 48f39a7240bf.
  de_dust 14 (VM rig): 1481 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 193,712 children (seeds 6510); totals from the merged tree. The rig's tree at b6074b546f25.
  de_dust 105 (Germany rig): 1482 entries, 5452 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 9 run records, 145,034 children (seeds 2014598281); totals from the merged tree. The rig's tree at 48f39a7240bf.
  de_dust 106 (Germany rig): 1482 entries, 5452 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 56,599 children (seeds 2014598281); totals from the merged tree. The rig's tree at 48f39a7240bf.
  de_dust 50 (San Francisco rig): 1482 entries, 5451 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,017 children (seeds 2203228423); totals from the merged tree. The rig's tree at 5ec634269748.
  de_dust 107 (Germany rig): 1482 entries, 5451 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,114 children (seeds 2014598281); totals from the merged tree. The rig's tree at 48f39a7240bf.
  de_dust 108 (Germany rig): 1482 entries, 5451 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 10 run records, 129,579 children (seeds 1166850438); totals from the merged tree. The rig's tree at 2ea5972c1319.
  de_dust 109 (Germany rig): 1482 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,592 children (seeds 1166850438); totals from the merged tree. The rig's tree at 2ea5972c1319.
  de_dust 51 (San Francisco rig): 1481 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,451 children (seeds 2203228423); totals from the merged tree. The rig's tree at 5ec634269748.
  de_dust 110 (Germany rig): 1482 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 85,256 children (seeds 1166850438); totals from the merged tree. The rig's tree at 2ea5972c1319.
  de_dust 111 (Germany rig): 1482 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,923 children (seeds 1166850438); totals from the merged tree. The rig's tree at 2ea5972c1319.
  de_dust 112 (Germany rig): 1482 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 56,891 children (seeds 3114302679); totals from the merged tree. The rig's tree at aecc88697e01.
  de_dust 52 (San Francisco rig): 1482 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 52,288 children (seeds 4046240897); totals from the merged tree. The rig's tree at 59334a86ba29.
  de_dust 113 (Germany rig): 1482 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 53,590 children (seeds 3114302679); totals from the merged tree. The rig's tree at aecc88697e01.
  de_dust 15 (VM rig): 1482 entries, 5445 arcs, 1 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 11 run records, 162,205 children (seeds 6530); totals from the merged tree. The rig's tree at 634fb36f0557. Crash records replayed at main's head: queries: 0 promoted, 0 redundant (fixed, reaching nothing new), 1 still crash.
  de_dust 53 (San Francisco rig): 1482 entries, 5440 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 32,753 children (seeds 4046240897); totals from the merged tree. The rig's tree at 59334a86ba29.
  de_dust 114 (Germany rig): 1482 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 7 run records, 94,073 children (seeds 3114302679); totals from the merged tree. The rig's tree at aecc88697e01.
  de_dust 115 (Germany rig): 1483 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,480 children (seeds 3114302679); totals from the merged tree. The rig's tree at aecc88697e01.
  de_dust 116 (Germany rig): 1484 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,546 children (seeds 3114302679); totals from the merged tree. The rig's tree at aecc88697e01.
  de_dust 54 (San Francisco rig): 1484 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,872 children (seeds 4046240897); totals from the merged tree. The rig's tree at 59334a86ba29.
  de_dust 117 (Germany rig): 1484 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 56,856 children (seeds 1433993411); totals from the merged tree. The rig's tree at f6a9adb1daf1.
  de_dust 55 (San Francisco rig): 1484 entries, 5439 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 56,700 children (seeds 1325604714); totals from the merged tree. The rig's tree at 0d1d1065d6fc.
  de_dust 118 (Germany rig): 1484 entries, 5441 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 7 run records, 104,216 children (seeds 1433993411); totals from the merged tree. The rig's tree at f6a9adb1daf1.
  de_dust 119 (Germany rig): 1484 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 9 run records, 128,898 children (seeds 1433993411); totals from the merged tree. The rig's tree at f6a9adb1daf1.
  de_dust 120 (Germany rig): 1484 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,442 children (seeds 1433993411); totals from the merged tree. The rig's tree at f6a9adb1daf1.
  de_dust 16 (VM rig): 1484 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 12 run records, 165,333 children (seeds 6540); totals from the merged tree. The rig's tree at 835e8d01be72.
  de_dust 56 (San Francisco rig): 1484 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,132 children (seeds 1325604714); totals from the merged tree. The rig's tree at 0d1d1065d6fc.
  de_dust 121 (Germany rig): 1486 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 39,448 children (seeds 3078134844); totals from the merged tree. The rig's tree at f510b0491868.
  de_dust 122 (Germany rig): 1486 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 8 run records, 124,058 children (seeds 3078134844); totals from the merged tree. The rig's tree at f510b0491868.
  de_dust 123 (Germany rig): 1486 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 33,554 children (seeds 3078134844); totals from the merged tree. The rig's tree at f510b0491868.
  de_dust 57 (San Francisco rig): 1486 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,589 children (seeds 3995681052); totals from the merged tree. The rig's tree at 732813a1a089.
  de_dust 124 (Germany rig): 1486 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 7 run records, 93,070 children (seeds 72998984); totals from the merged tree. The rig's tree at 7d9e02f77ce8.
  de_dust 58 (San Francisco rig): 1486 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 74,238 children (seeds 3995681052); totals from the merged tree. The rig's tree at 732813a1a089.
  de_dust 125 (Germany rig): 1486 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,115 children (seeds 72998984); totals from the merged tree. The rig's tree at 7d9e02f77ce8.
  de_dust 59 (San Francisco rig): 1486 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,150 children (seeds 1003139783); totals from the merged tree. The rig's tree at cb667a06b660.
  de_dust 126 (Germany rig): 1487 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 56,742 children (seeds 72998984); totals from the merged tree. The rig's tree at 7d9e02f77ce8. Retired echoes not re-banked: 1.
  de_dust 127 (Germany rig): 1487 entries, 5447 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,110 children (seeds 72998984); totals from the merged tree. The rig's tree at 7d9e02f77ce8. Retired echoes not re-banked: 1.
  de_dust 128 (Germany rig): 1489 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 17,913 children (seeds 521522127); totals from the merged tree. The rig's tree at 006f9205f910.
  de_dust 129 (Germany rig): 1489 entries, 5450 arcs, 1 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 8 run records, 119,868 children (seeds 521522127); totals from the merged tree. The rig's tree at 006f9205f910. Crash records replayed at main's head: queries: 0 promoted, 0 redundant (fixed, reaching nothing new), 1 still crash.
  de_dust 130 (Germany rig): 1489 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 6 run records, 94,052 children (seeds 521522127); totals from the merged tree. The rig's tree at 006f9205f910.
  de_dust 60 (San Francisco rig): 1489 entries, 5451 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,396 children (seeds 1003139783); totals from the merged tree. The rig's tree at cb667a06b660. Retired echoes not re-banked: 1.
  de_dust 17 (VM rig): 1489 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 196,296 children (seeds 6550); totals from the merged tree. The rig's tree at c217772cb142. Retired echoes not re-banked: 1.
  de_dust 131 (Germany rig): 1489 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,438 children (seeds 521522127); totals from the merged tree. The rig's tree at 006f9205f910.
  de_dust 132 (Germany rig): 1491 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,590 children (seeds 521522127); totals from the merged tree. The rig's tree at 006f9205f910.
  de_dust 61 (San Francisco rig): 1491 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,193 children (seeds 4064361640); totals from the merged tree. The rig's tree at 658660c4d6de. Retired echoes not re-banked: 1.
  de_dust 133 (Germany rig): 1492 entries, 5452 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 6 run records, 74,356 children (seeds 1144391274); totals from the merged tree. The rig's tree at 1e78e039c914. Retired echoes not re-banked: 1.
  de_dust 134 (Germany rig): 1492 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 197,604 children (seeds 1144391274); totals from the merged tree. The rig's tree at 1e78e039c914. Retired echoes not re-banked: 1.
  de_dust 62 (San Francisco rig): 1492 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,517 children (seeds 4064361640); totals from the merged tree. The rig's tree at 658660c4d6de. Retired echoes not re-banked: 1.
  de_dust 135 (Germany rig): 1492 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,314 children (seeds 1144391274); totals from the merged tree. The rig's tree at 1e78e039c914. Retired echoes not re-banked: 1.
  de_dust 136 (Germany rig): 1492 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,916 children (seeds 1144391274); totals from the merged tree. The rig's tree at 1e78e039c914. Retired echoes not re-banked: 1.
  de_dust 18 (VM rig): 1493 entries, 5451 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 7 run records, 92,010 children (seeds 6560); totals from the merged tree. The rig's tree at 6acc3b6488a3. Retired echoes not re-banked: 1.
  de_dust 137 (Germany rig): 1493 entries, 5451 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 21,455 children (seeds 1582994957); totals from the merged tree. The rig's tree at cb7eccaaa008.
  de_dust 138 (Germany rig): 1493 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 14 run records, 197,655 children (seeds 1582994957); totals from the merged tree. The rig's tree at cb7eccaaa008.
  de_dust 139 (Germany rig): 1493 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 53,078 children (seeds 1582994957); totals from the merged tree. The rig's tree at cb7eccaaa008.
  de_dust 63 (San Francisco rig): 1493 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,386 children (seeds 793693915); totals from the merged tree. The rig's tree at 007f4388bfb8.
  de_dust 140 (Germany rig): 1495 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,545 children (seeds 1582994957); totals from the merged tree. The rig's tree at cb7eccaaa008.
  de_dust 141 (Germany rig): 1495 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,375 children (seeds 1582994957); totals from the merged tree. The rig's tree at cb7eccaaa008.
  de_dust 142 (Germany rig): 1495 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 39,354 children (seeds 4028848609); totals from the merged tree. The rig's tree at 0c7494637211.
  de_dust 143 (Germany rig): 1495 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 9 run records, 119,702 children (seeds 4028848609); totals from the merged tree. The rig's tree at 0c7494637211.
  de_dust 144 (Germany rig): 1495 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 8 run records, 130,393 children (seeds 4028848609); totals from the merged tree. The rig's tree at 0c7494637211.
  de_dust 145 (Germany rig): 1497 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,475 children (seeds 4028848609); totals from the merged tree. The rig's tree at 0c7494637211.
  de_dust 64 (San Francisco rig): 1497 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,524 children (seeds 1978133821); totals from the merged tree. The rig's tree at b3ef58c8f15d.
  de_dust 146 (Germany rig): 1497 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 56,571 children (seeds 4210284521); totals from the merged tree. The rig's tree at 4a7aa1069893.
  de_dust 19 (VM rig): 1496 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 18 run records, 272,165 children (seeds 6570); totals from the merged tree. The rig's tree at f70911e7cea8.
  de_dust 65 (San Francisco rig): 1496 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,952 children (seeds 1978133821); totals from the merged tree. The rig's tree at b3ef58c8f15d.
  de_dust 147 (Germany rig): 1496 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 68,553 children (seeds 4210284521); totals from the merged tree. The rig's tree at 4a7aa1069893.
  de_dust 148 (Germany rig): 1496 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,150 children (seeds 4210284521); totals from the merged tree. The rig's tree at 4a7aa1069893.
  de_dust 149 (Germany rig): 1496 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 11 run records, 163,419 children (seeds 1877589689); totals from the merged tree. The rig's tree at baa7855fde34.
  de_dust 150 (Germany rig): 1500 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 38,982 children (seeds 1877589689); totals from the merged tree. The rig's tree at baa7855fde34.
  de_dust 151 (Germany rig): 1500 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,492 children (seeds 1877589689); totals from the merged tree. The rig's tree at baa7855fde34.
  de_dust 152 (Germany rig): 1500 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,007 children (seeds 1877589689); totals from the merged tree. The rig's tree at baa7855fde34.
  de_dust 66 (San Francisco rig): 1500 entries, 5452 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,040 children (seeds 1558465313); totals from the merged tree. The rig's tree at 230d50ba3ee1.
  de_dust 153 (Germany rig): 1500 entries, 5452 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 547 children (seeds 3030116631); totals from the merged tree. The rig's tree at 64d471198677.
  de_dust 67 (San Francisco rig): 1500 entries, 5448 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 34,838 children (seeds 670625944); totals from the merged tree. The rig's tree at a27beae034fc.
  de_dust 154 (Germany rig): 1500 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 14 run records, 214,566 children (seeds 3030116631); totals from the merged tree. The rig's tree at 64d471198677.
  de_dust 68 (San Francisco rig): 1500 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 15,649 children (seeds 670625944); totals from the merged tree. The rig's tree at a27beae034fc.
  de_dust 155 (Germany rig): 1501 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 52,690 children (seeds 3030116631); totals from the merged tree. The rig's tree at 64d471198677.
  de_dust 69 (San Francisco rig): 1501 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 9 run records, 128,621 children (seeds 670625944); totals from the merged tree. The rig's tree at a27beae034fc.
  de_dust 70 (San Francisco rig): 1501 entries, 5450 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,161 children (seeds 670625944); totals from the merged tree. The rig's tree at a27beae034fc.
  de_dust 20 (VM rig): 1500 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 19 run records, 286,290 children (seeds 6580); totals from the merged tree. The rig's tree at 756945d510ce.
  de_dust 156 (Germany rig): 1500 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 21,575 children (seeds 3030116631); totals from the merged tree. The rig's tree at 64d471198677.
  de_dust 157 (Germany rig): 1500 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,435 children (seeds 3030116631); totals from the merged tree. The rig's tree at 64d471198677.
  de_dust 71 (San Francisco rig): 1500 entries, 5449 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 21,549 children (seeds 133878331); totals from the merged tree. The rig's tree at 899aa118d6ed.
  de_dust 158 (Germany rig): 1500 entries, 5451 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 53,007 children (seeds 218776569); totals from the merged tree. The rig's tree at d6d7a77827dd.
  de_dust 159 (Germany rig): 1500 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 13 run records, 184,258 children (seeds 218776569); totals from the merged tree. The rig's tree at d6d7a77827dd.
  de_dust 160 (Germany rig): 1503 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 52,579 children (seeds 218776569); totals from the merged tree. The rig's tree at d6d7a77827dd.
  de_dust 161 (Germany rig): 1503 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,047 children (seeds 218776569); totals from the merged tree. The rig's tree at d6d7a77827dd.
  de_dust 72 (San Francisco rig): 1503 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,429 children (seeds 133878331); totals from the merged tree. The rig's tree at 899aa118d6ed.
  de_dust 73 (San Francisco rig): 1503 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 540 children (seeds 498315372); totals from the merged tree. The rig's tree at 85e7bcfc8b87.
  de_dust 162 (Germany rig): 1503 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 18,025 children (seeds 3721199954); totals from the merged tree. The rig's tree at b01423cde4f6.
  de_dust 163 (Germany rig): 1503 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 16 run records, 236,632 children (seeds 3721199954); totals from the merged tree. The rig's tree at b01423cde4f6.
  de_dust 21 (VM rig): 1503 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 10 run records, 143,369 children (seeds 6590); totals from the merged tree. The rig's tree at 6ae8c1ee9e91.
  de_dust 164 (Germany rig): 1504 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,566 children (seeds 3721199954); totals from the merged tree. The rig's tree at b01423cde4f6.
  de_dust 165 (Germany rig): 1504 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 34,967 children (seeds 3845117195); totals from the merged tree. The rig's tree at 526f276fbe0f.
  de_dust 74 (San Francisco rig): 1505 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,013 children (seeds 498315372); totals from the merged tree. The rig's tree at 85e7bcfc8b87.
  de_dust 166 (Germany rig): 1505 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 18,505 children (seeds 3845117195); totals from the merged tree. The rig's tree at 526f276fbe0f.
  de_dust 22 (VM rig): 1505 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 34,968 children (seeds 6600); totals from the merged tree. The rig's tree at f092c9b14ba4.
  de_dust 167 (Germany rig): 1505 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,378 children (seeds 3845117195); totals from the merged tree. The rig's tree at 526f276fbe0f.
  de_dust 168 (Germany rig): 1504 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,432 children (seeds 3845117195); totals from the merged tree. The rig's tree at 526f276fbe0f.
  de_dust 169 (Germany rig): 1504 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 6 run records, 83,676 children (seeds 398143807); totals from the merged tree. The rig's tree at 42490be5ece2.
  de_dust 75 (San Francisco rig): 1504 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,970 children (seeds 325202936); totals from the merged tree. The rig's tree at e6696e265c2f.
  de_dust 76 (San Francisco rig): 1504 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 7 run records, 98,780 children (seeds 2966085129); totals from the merged tree. The rig's tree at b3127ee3fa4e.
  de_dust 170 (Germany rig): 1504 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 8 run records, 116,611 children (seeds 398143807); totals from the merged tree. The rig's tree at 42490be5ece2.
  de_dust 77 (San Francisco rig): 1504 entries, 5456 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,188 children (seeds 2966085129); totals from the merged tree. The rig's tree at b3127ee3fa4e.
  de_dust 171 (Germany rig): 1505 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 70,905 children (seeds 398143807); totals from the merged tree. The rig's tree at 42490be5ece2.
  de_dust 172 (Germany rig): 1505 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,401 children (seeds 398143807); totals from the merged tree. The rig's tree at 42490be5ece2.
  de_dust 173 (Germany rig): 1506 entries, 5459 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 67,829 children (seeds 1322325882); totals from the merged tree. The rig's tree at d1b1409619eb.
  de_dust 78 (San Francisco rig): 1506 entries, 5459 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,529 children (seeds 2966085129); totals from the merged tree. The rig's tree at b3127ee3fa4e.
  de_dust 174 (Germany rig): 1506 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 11 run records, 150,219 children (seeds 1322325882); totals from the merged tree. The rig's tree at d1b1409619eb.
  de_dust 23 (VM rig): 1506 entries, 5459 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 18 run records, 271,263 children (seeds 6610); totals from the merged tree. The rig's tree at d854413efa7b.
  de_dust 79 (San Francisco rig): 1506 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 9 run records, 128,502 children (seeds 3764367034); totals from the merged tree. The rig's tree at acfaab1eb07a.
  de_dust 175 (Germany rig): 1506 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 70,730 children (seeds 1322325882); totals from the merged tree. The rig's tree at d1b1409619eb.
  de_dust 176 (Germany rig): 1506 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,021 children (seeds 1322325882); totals from the merged tree. The rig's tree at d1b1409619eb.
  de_dust 80 (San Francisco rig): 1506 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 56,687 children (seeds 3764367034); totals from the merged tree. The rig's tree at acfaab1eb07a.
  de_dust 177 (Germany rig): 1506 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 526 children (seeds 1624672328); totals from the merged tree. The rig's tree at 7dce1f654fa7.
  de_dust 81 (San Francisco rig): 1506 entries, 5453 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,093 children (seeds 3764367034); totals from the merged tree. The rig's tree at acfaab1eb07a.
  de_dust 178 (Germany rig): 1506 entries, 5451 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 4 run records, 69,419 children (seeds 1624672328); totals from the merged tree. The rig's tree at 7dce1f654fa7.
  de_dust 24 (VM rig): 1506 entries, 5451 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 3 run records, 35,755 children (seeds 6620); totals from the merged tree. The rig's tree at d82a72e272a3.
  de_dust 179 (Germany rig): 1510 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 72,847 children (seeds 1624672328); totals from the merged tree. The rig's tree at 7dce1f654fa7.
  de_dust 180 (Germany rig): 1510 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,949 children (seeds 1624672328); totals from the merged tree. The rig's tree at 7dce1f654fa7.
  de_dust 181 (Germany rig): 1510 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 11 run records, 145,789 children (seeds 455572660); totals from the merged tree. The rig's tree at 292a7e17f6ef.
  de_dust 182 (Germany rig): 1510 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,413 children (seeds 455572660); totals from the merged tree. The rig's tree at 292a7e17f6ef.
  de_dust 82 (San Francisco rig): 1510 entries, 5458 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,469 children (seeds 975339873); totals from the merged tree. The rig's tree at b84f6008b537.
  de_dust 183 (Germany rig): 1510 entries, 5458 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 35,937 children (seeds 455572660); totals from the merged tree. The rig's tree at 292a7e17f6ef.
  de_dust 184 (Germany rig): 1510 entries, 5458 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 2 run records, 34,290 children (seeds 2417769716); totals from the merged tree. The rig's tree at 94d8ea7375d6.
  de_dust 185 (Germany rig): 1511 entries, 5458 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 5 run records, 72,904 children (seeds 2417769716); totals from the merged tree. The rig's tree at 94d8ea7375d6.
  de_dust 83 (San Francisco rig): 1511 entries, 5458 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,065 children (seeds 3822998459); totals from the merged tree. The rig's tree at cdc3097b7399.
  de_dust 186 (Germany rig): 1511 entries, 5458 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 12 run records, 164,116 children (seeds 2417769716); totals from the merged tree. The rig's tree at 94d8ea7375d6.
  de_dust 187 (Germany rig): 1511 entries, 5458 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 18,213 children (seeds 2417769716); totals from the merged tree. The rig's tree at 94d8ea7375d6.
  de_dust 188 (Germany rig): 1511 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,499 children (seeds 2417769716); totals from the merged tree. The rig's tree at 94d8ea7375d6.
  de_dust 189 (Germany rig): 1511 entries, 5457 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,874 children (seeds 45656236); totals from the merged tree. The rig's tree at 31614fef5f81.
  de_dust 84 (San Francisco rig): 1511 entries, 5454 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 1 run records, 17,816 children (seeds 3822998459); totals from the merged tree. The rig's tree at cdc3097b7399.
  de_dust 190 (Germany rig): 1511 entries, 5454 arcs, 1 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 6 run records, 89,469 children (seeds 45656236); totals from the merged tree. The rig's tree at 31614fef5f81. Crash records replayed at main's head: cloud: 0 promoted, 0 redundant (fixed, reaching nothing new), 1 still crash.
  de_dust 25 (VM rig): 1511 entries, 5455 arcs, 0 crashes filed.
  Banked by rig_bank from the rig's own tree under section M item 7: 18 run records, 254,213 children (seeds 6630); totals from the merged tree. The rig's tree at a5fd93f16005.
- v3.12.71 FULL STAMP DONE: GitHub
  release published
  2026-10-25T22:02:36Z by
  github-actions[bot], 13 assets;
  all 12 SHA384SUMS entries verify
  on downloaded copies
  (~/workspace/stamp-3.12.71/);
  wheel and sdist SHA-256 match
  PyPI; GHCR v3.12.71 and latest
  both resolve (200, 2 manifests);
  GitLab release v3.12.71 carries
  13 asset links. Tag build
  40237339272: every publish job
  success; the run's red was
  test-macos (the known flaky leg,
  Q51). The verification itself
  was completed earlier; this line
  was the part still owed.
- VM rig loop corrected
  2026-10-28: the grow loop now
  works in the reset clone
  (hp-vm-src) instead of rsyncing
  code into hp-p2 — a run record's
  head is its clone's git HEAD,
  and hp-p2's never moved, so VM
  records carried 624e0d0e388f
  while the code under test
  changed. Grow 6430's fragment
  records (8 records, 120,525
  children, 0 crashes) are banked
  with this line. The 17 crash
  records hp-p2 still held (grows
  27–28, queries) are all retired
  on main as redundant, replayed
  on the fixed tree; no Q109 is
  owed. rig_bank's VM-rig grow
  count restarts where its line
  format diverges from the
  hand-banked lines; seeds key
  the grows unambiguously.
- Stamp backlog batch,
  2026-10-28: the grind's lines
  for 81 releases, oldest first.
  Every SHA384SUMS set verifies
  and every PyPI digest matches;
  GitLab lines marked recheck
  were re-read after this VM's
  truncated first reads.
  v3.13.9's linux-arm64 entry
  read BAD on a truncated
  download and verifies on a
  fresh one; its line carries
  the note.
- v3.12.48 FULL STAMP: GitHub
  release published
  2026-10-22T22:27:33Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.48.tar.gz
  OK; GHCR v3.12.48 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 39862694402:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.12.49 FULL STAMP: GitHub
  release published
  2026-10-22T22:29:20Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.49.tar.gz
  OK; GHCR v3.12.49 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 39862721340:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.12.50 FULL STAMP: GitHub
  release published
  2026-10-22T22:29:02Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.50.tar.gz
  OK; GHCR v3.12.50 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 39862747983:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.12.51 FULL STAMP: GitHub
  release published
  2026-10-22T23:00:22Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.51.tar.gz
  OK; GHCR v3.12.51 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 39868303814:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.12.53 FULL STAMP: GitHub
  release published
  2026-10-23T00:26:55Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.53.tar.gz
  OK; GHCR v3.12.53 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 39877591090:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.12.54 FULL STAMP: GitHub
  release published
  2026-10-23T01:02:52Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.54.tar.gz
  OK; GHCR v3.12.54 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 39881063666:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.12.56 FULL STAMP: GitHub
  release published
  2026-10-23T03:00:02Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.56.tar.gz
  OK; GHCR v3.12.56 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 39891950752:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.12.58 FULL STAMP: GitHub
  release published
  2026-10-24T01:10:06Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.58.tar.gz
  OK; GHCR v3.12.58 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40047875139:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.12.59 FULL STAMP: GitHub
  release published
  2026-10-24T02:49:14Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.59.tar.gz
  OK; GHCR v3.12.59 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40055244822:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.12.60 FULL STAMP: GitHub
  release published
  2026-10-24T08:02:56Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.60.tar.gz
  OK; GHCR v3.12.60 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40076033672:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.12.61 FULL STAMP: GitHub
  release published
  2026-10-24T08:34:17Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.61.tar.gz
  OK; GHCR v3.12.61 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40078077256:
  conclusion=success, publish jobs
  {'gitlab': 'success', 'release':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.12.62 FULL STAMP: GitHub
  release published
  2026-10-24T19:07:47Z by github-
  actions[bot], 13 assets;
  SHA384SUMS unread on downloaded
  copies; PyPI unread; GHCR
  unread; GitLab unread.
- v3.12.63 FULL STAMP: GitHub
  release published
  2026-10-24T19:42:55Z by github-
  actions[bot], 13 assets;
  SHA384SUMS unread on downloaded
  copies; PyPI unread; GHCR
  unread; GitLab unread.
- v3.12.65 FULL STAMP: GitHub
  release published
  2026-10-24T23:43:58Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.65.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.12.72 FULL STAMP: GitHub
  release published
  2026-10-25T22:07:07Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.72.tar.gz
  OK; GHCR v3.12.72 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40238030310:
  conclusion=failure, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed ['test-
  macos'].
- v3.12.77 FULL STAMP: GitHub
  release published
  2026-10-25T23:46:55Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.77.tar.gz
  OK; GHCR v3.12.77 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40245877234:
  conclusion=failure, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed
  ['test-macos'].
- v3.12.78 FULL STAMP: GitHub
  release published
  2026-10-26T00:05:09Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.12.78.tar.gz
  OK; GHCR v3.12.78 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40246969438:
  conclusion=failure, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed
  ['test-macos'].
- v3.13.0 FULL STAMP: GitHub
  release published
  2026-10-26T00:20:30Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.0.tar.gz
  OK; GHCR v3.13.0 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40248156965:
  conclusion=failure, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed ['test-
  macos'].
- v3.13.1 FULL STAMP: GitHub
  release published
  2026-10-26T00:30:03Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.1.tar.gz
  OK; GHCR v3.13.1 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40248825201:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.2 FULL STAMP: GitHub
  release published
  2026-10-26T00:30:42Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.2.tar.gz
  OK; GHCR v3.13.2 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40248857457:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.3 FULL STAMP: GitHub
  release published
  2026-10-26T02:19:20Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.3.tar.gz
  OK; GHCR v3.13.3 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40257662056:
  conclusion=failure, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed ['test-
  macos'].
- v3.13.4 FULL STAMP: GitHub
  release published
  2026-10-26T02:39:41Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.4.tar.gz
  OK; GHCR v3.13.4 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40259406463:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.5 FULL STAMP: GitHub
  release published
  2026-10-26T03:11:42Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.5.tar.gz
  OK; GHCR v3.13.5 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40262269280:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.13.6 FULL STAMP: GitHub
  release published
  2026-10-26T03:34:43Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.6.tar.gz
  OK; GHCR v3.13.6 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40264039530:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.7 FULL STAMP: GitHub
  release published
  2026-10-26T03:54:04Z by github-
  actions[bot], 13 assets;
  SHA384SUMS unread on downloaded
  copies; PyPI unread; GHCR
  unread; GitLab unread.
- v3.13.8 FULL STAMP: GitHub
  release published
  2026-10-26T04:23:31Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.8.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.13.9 FULL STAMP: GitHub
  release published
  2026-10-26T04:47:16Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify (the linux-arm64 entry
  read bad on the grind's
  truncated download; re-verified
  on a fresh 69,737,191-byte
  download, sha384 matches the
  sums entry) on downloaded
  copies; PyPI any.whl OK,
  3.13.9.tar.gz OK; GHCR unread;
  GitLab unread.
- v3.13.10 FULL STAMP: GitHub
  release published
  2026-10-26T05:19:22Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.10.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.13.11 FULL STAMP: GitHub
  release published
  2026-10-26T05:42:41Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.11.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.13.12 FULL STAMP: GitHub
  release published
  2026-10-26T06:04:49Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.12.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.13.13 FULL STAMP: GitHub
  release published
  2026-10-26T06:26:16Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.13.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.13.14 FULL STAMP: GitHub
  release published
  2026-10-26T06:59:15Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.14.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.13.15 FULL STAMP: GitHub
  release published
  2026-10-26T07:24:22Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.15.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.13.16 FULL STAMP: GitHub
  release published
  2026-10-26T08:05:36Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.16.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.13.17 FULL STAMP: GitHub
  release published
  2026-10-26T08:26:04Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.17.tar.gz
  OK; GHCR unread; GitLab unread.
- v3.13.18 FULL STAMP: GitHub
  release published
  2026-10-26T08:47:56Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.18.tar.gz
  OK; GHCR v3.13.18 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40293565737:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.13.19 FULL STAMP: GitHub
  release published
  2026-10-26T09:11:38Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.19.tar.gz
  OK; GHCR v3.13.19 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40296167125:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.20 FULL STAMP: GitHub
  release published
  2026-10-26T09:33:44Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.20.tar.gz
  OK; GHCR v3.13.20 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40299186281:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.21 FULL STAMP: GitHub
  release published
  2026-10-26T09:54:36Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.21.tar.gz
  OK; GHCR v3.13.21 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40301970409:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.13.22 FULL STAMP: GitHub
  release published
  2026-10-26T10:53:51Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.22.tar.gz
  OK; GHCR v3.13.22 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40309678332:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.23 FULL STAMP: GitHub
  release published
  2026-10-26T11:15:33Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.23.tar.gz
  OK; GHCR v3.13.23 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40312408033:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.13.24 FULL STAMP: GitHub
  release published
  2026-10-26T11:34:30Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.24.tar.gz
  OK; GHCR v3.13.24 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40314881144:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.25 FULL STAMP: GitHub
  release published
  2026-10-26T11:56:37Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.25.tar.gz
  OK; GHCR v3.13.25 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40317570770:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.26 FULL STAMP: GitHub
  release published
  2026-10-26T12:19:07Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.26.tar.gz
  OK; GHCR v3.13.26 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40320262516:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.27 FULL STAMP: GitHub
  release published
  2026-10-26T12:54:53Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.27.tar.gz
  OK; GHCR v3.13.27 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40324472987:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.28 FULL STAMP: GitHub
  release published
  2026-10-26T13:17:03Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.28.tar.gz
  OK; GHCR v3.13.28 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40327768700:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.13.29 FULL STAMP: GitHub
  release published
  2026-10-26T13:47:30Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.29.tar.gz
  OK; GHCR v3.13.29 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40332212407:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.30 FULL STAMP: GitHub
  release published
  2026-10-26T14:11:39Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.30.tar.gz
  OK; GHCR v3.13.30 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40335600649:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.31 FULL STAMP: GitHub
  release published
  2026-10-26T14:34:22Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.31.tar.gz
  OK; GHCR v3.13.31 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40339290486:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.13.32 FULL STAMP: GitHub
  release published
  2026-10-26T14:58:05Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.32.tar.gz
  OK; GHCR v3.13.32 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40342893714:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.13.33 FULL STAMP: GitHub
  release published
  2026-10-26T15:23:02Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.33.tar.gz
  OK; GHCR v3.13.33 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40346969458:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.34 FULL STAMP: GitHub
  release published
  2026-10-26T16:18:51Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.34.tar.gz
  OK; GHCR v3.13.34 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40354900506:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.35 FULL STAMP: GitHub
  release published
  2026-10-26T16:40:53Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.35.tar.gz
  OK; GHCR v3.13.35 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40359842622:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.36 FULL STAMP: GitHub
  release published
  2026-10-26T17:03:12Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.36.tar.gz
  OK; GHCR v3.13.36 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40363279669:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.37 FULL STAMP: GitHub
  release published
  2026-10-26T17:24:19Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.37.tar.gz
  OK; GHCR v3.13.37 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40366643347:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.13.38 FULL STAMP: GitHub
  release published
  2026-10-26T17:47:30Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.38.tar.gz
  OK; GHCR v3.13.38 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40370180762:
  conclusion=failure, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed ['test-
  macos'].
- v3.13.39 FULL STAMP: GitHub
  release published
  2026-10-26T18:10:05Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.39.tar.gz
  OK; GHCR v3.13.39 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40373725019:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.13.40 FULL STAMP: GitHub
  release published
  2026-10-26T18:34:19Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.40.tar.gz
  OK; GHCR v3.13.40 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40377287713:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.13.41 FULL STAMP: GitHub
  release published
  2026-10-26T18:57:01Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.41.tar.gz
  OK; GHCR v3.13.41 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40381111770:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.42 FULL STAMP: GitHub
  release published
  2026-10-26T19:33:58Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.42.tar.gz
  OK; GHCR v3.13.42 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40386335802:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.43 FULL STAMP: GitHub
  release published
  2026-10-26T20:11:34Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.43.tar.gz
  OK; GHCR v3.13.43 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40391756814:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.13.44 FULL STAMP: GitHub
  release published
  2026-10-26T20:36:11Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.44.tar.gz
  OK; GHCR v3.13.44 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40395489494:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.45 FULL STAMP: GitHub
  release published
  2026-10-26T20:58:55Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.45.tar.gz
  OK; GHCR v3.13.45 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40398886108:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.46 FULL STAMP: GitHub
  release published
  2026-10-26T21:20:00Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.46.tar.gz
  OK; GHCR v3.13.46 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40401954040:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.13.47 FULL STAMP: GitHub
  release published
  2026-10-26T21:41:43Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.47.tar.gz
  OK; GHCR v3.13.47 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40405180607:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.48 FULL STAMP: GitHub
  release published
  2026-10-26T22:04:35Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.48.tar.gz
  OK; GHCR v3.13.48 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40408260811:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.49 FULL STAMP: GitHub
  release published
  2026-10-26T22:35:00Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.49.tar.gz
  OK; GHCR v3.13.49 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40410990275:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.50 FULL STAMP: GitHub
  release published
  2026-10-26T22:57:32Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.50.tar.gz
  OK; GHCR v3.13.50 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40415009921:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.13.51 FULL STAMP: GitHub
  release published
  2026-10-26T23:38:04Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.51.tar.gz
  OK; GHCR v3.13.51 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40419948463:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.52 FULL STAMP: GitHub
  release published
  2026-10-27T00:02:48Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.52.tar.gz
  OK; GHCR v3.13.52 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40422595692:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.53 FULL STAMP: GitHub
  release published
  2026-10-27T00:56:03Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.53.tar.gz
  OK; GHCR v3.13.53 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40428480717:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.54 FULL STAMP: GitHub
  release published
  2026-10-27T01:34:40Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.54.tar.gz
  OK; GHCR v3.13.54 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40431521910:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.13.55 FULL STAMP: GitHub
  release published
  2026-10-27T02:02:42Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.55.tar.gz
  OK; GHCR v3.13.55 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40435187827:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.56 FULL STAMP: GitHub
  release published
  2026-10-27T02:31:52Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.56.tar.gz
  OK; GHCR v3.13.56 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40438157426:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.57 FULL STAMP: GitHub
  release published
  2026-10-27T03:00:51Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.57.tar.gz
  OK; GHCR v3.13.57 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40440120942:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.58 FULL STAMP: GitHub
  release published
  2026-10-27T03:22:29Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.58.tar.gz
  OK; GHCR v3.13.58 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40443068629:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.59 FULL STAMP: GitHub
  release published
  2026-10-27T03:45:39Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.59.tar.gz
  OK; GHCR v3.13.59 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40445016319:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.60 FULL STAMP: GitHub
  release published
  2026-10-27T05:30:37Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.60.tar.gz
  OK; GHCR v3.13.60 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40454755060:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.61 FULL STAMP: GitHub
  release published
  2026-10-27T05:54:07Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.61.tar.gz
  OK; GHCR v3.13.61 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40456969193:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.13.62 FULL STAMP: GitHub
  release published
  2026-10-27T06:27:20Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.62.tar.gz
  OK; GHCR v3.13.62 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40460057113:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.13.63 FULL STAMP: GitHub
  release published
  2026-10-27T07:00:02Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.63.tar.gz
  OK; GHCR v3.13.63 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40463318799:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.13.64 FULL STAMP: GitHub
  release published
  2026-10-27T07:35:06Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.64.tar.gz
  OK; GHCR v3.13.64 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40466912908:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.13.65 FULL STAMP: GitHub
  release published
  2026-10-27T07:58:41Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.65.tar.gz
  OK; GHCR v3.13.65 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40469239359:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.13.66 FULL STAMP: GitHub
  release published
  2026-10-27T08:40:13Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.66.tar.gz
  OK; GHCR v3.13.66 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40473949166:
  conclusion=failure, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed
  ['test-macos'].
- v3.13.67 FULL STAMP: GitHub
  release published
  2026-10-27T14:19:07Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.13.67.tar.gz
  OK; GHCR v3.13.67 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40518220647:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.14.0 FULL STAMP: GitHub
  release published
  2026-10-27T14:39:21Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.0.tar.gz
  OK; GHCR v3.14.0 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40521471236:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.14.1 FULL STAMP: GitHub
  release published
  2026-10-27T16:46:40Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.1.tar.gz
  OK; GHCR v3.14.1 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40542340879:
  conclusion=failure, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.14.3 FULL STAMP: GitHub
  release published
  2026-10-27T22:42:02Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.3.tar.gz
  OK; GHCR v3.14.3 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40595251192:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success',
  'gitlab': 'success', 'pypi-
  publish': 'success'}, failed [].
- v3.14.4 FULL STAMP: GitHub
  release published
  2026-10-27T23:02:41Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.4.tar.gz
  OK; GHCR v3.14.4 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40597869052:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.14.6 FULL STAMP: GitHub
  release published
  2026-10-28T01:17:31Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.6.tar.gz
  OK; GHCR v3.14.6 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40613007120:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.14.7 FULL STAMP: GitHub
  release published
  2026-10-28T04:48:02Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.7.tar.gz
  OK; GHCR v3.14.7 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40633255214:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.14.8 FULL STAMP: GitHub
  release published
  2026-10-28T15:09:39Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.8.tar.gz
  OK; GHCR v3.14.8 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40710134053:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.14.9 FULL STAMP: GitHub
  release published
  2026-10-28T18:20:16Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.9.tar.gz
  OK; GHCR v3.14.9 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40741466491:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.14.12 FULL STAMP: GitHub
  release published
  2026-10-28T19:21:16Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.12.tar.gz
  OK; GHCR v3.14.12 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40751539537:
  conclusion=failure, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.14.13 FULL STAMP: GitHub
  release published
  2026-10-28T21:21:20Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.13.tar.gz
  OK; GHCR v3.14.13 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40769540438:
  conclusion=success, publish jobs
  {'release': 'success',
  'sourceforge': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success'}, failed [].
- v3.14.14 FULL STAMP: GitHub
  release published
  2026-10-29T00:16:18Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.14.tar.gz
  OK; GHCR v3.14.14 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40791481396:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.14.15 FULL STAMP: GitHub
  release published
  2026-10-29T01:41:12Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.15.tar.gz
  OK; GHCR v3.14.15 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40800631418:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.14.16 FULL STAMP: GitHub
  release published
  2026-10-29T05:00:54Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.16.tar.gz
  OK; GHCR v3.14.16 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40819804091:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.14.17 FULL STAMP: GitHub
  release published
  2026-10-29T04:37:58Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.17.tar.gz
  OK; GHCR v3.14.17 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40817751846:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.14.18 FULL STAMP: GitHub
  release published
  2026-10-29T04:51:35Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.18.tar.gz
  OK; GHCR v3.14.18 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40818992694:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.14.19 FULL STAMP: GitHub
  release published
  2026-10-29T05:44:21Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.19.tar.gz
  OK; GHCR v3.14.19 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40824043453:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'sourceforge':
  'success', 'pypi-publish':
  'success'}, failed [].
- v3.14.20 FULL STAMP: GitHub
  release published
  2026-10-29T06:42:29Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.20.tar.gz
  OK; GHCR v3.14.20 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40829600413:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
- v3.14.21 FULL STAMP: GitHub
  release published
  2026-10-29T07:10:14Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.21.tar.gz
  OK; GHCR v3.14.21 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40832511851:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success', 'gitlab':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.14.22 FULL STAMP: GitHub
  release published
  2026-10-29T08:11:16Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.22.tar.gz
  OK; GHCR v3.14.22 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40838922456:
  conclusion=success, publish jobs
  {'release': 'success', 'gitlab':
  'success', 'pypi-publish':
  'success', 'sourceforge':
  'success'}, failed [].
- v3.14.23 FULL STAMP: GitHub
  release published
  2026-10-29T10:40:36Z by github-
  actions[bot], 13 assets;
  SHA384SUMS 12 entries, all
  verify on downloaded copies;
  PyPI any.whl OK, 3.14.23.tar.gz
  OK; GHCR v3.14.23 200/2
  manifests, latest 200/2
  manifests; GitLab asset
  links=13. Tag build 40857781158:
  conclusion=success, publish jobs
  {'release': 'success', 'pypi-
  publish': 'success',
  'sourceforge': 'success',
  'gitlab': 'success'}, failed [].
