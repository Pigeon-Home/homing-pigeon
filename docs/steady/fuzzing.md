# Fuzzing the intake

The Oracle takes input from sensors, extensions, the model, and
the transports. A refusal is a string. A crash is a bug. The
tests that hold that rule are in-memory. They open no socket
and they load no model.

## Core

Core names the production runner as a set of files: the code
that runs, without the unit tests, the test harnesses or
anything superfluous. The canonical list stands in
runner/ops/core.py (CORE_FILES): 130 files, all under runner/.
Running `python3 runner/ops/core.py` prints the set's current
zip size and token counts.

The set was first assembled on 2026-11-04 so a single model
window could hold the whole runner beside the documentation:
133 files, 54,427 lines (48,981 of them non-blank), a
701,403-byte zip, and 619,845 tokens by that window's own
count (Gemini countTokens). Re-measured on 2026-11-05, after
the Q-new runner fixes grew 4 of its files, and again after
the CHECKLIST-04 send_job fixes grew runner/cloud, and
again on 2026-11-06 after the fy_iceworld F-1 fix grew
runner/wire, and again the same day after the signed-body
strictness fix grew runner/guard, and after the audit
hash-chain fix grew runner/guard and runner/ops, and once
more the same day after the Oracle tool-mode work and the
startup posture assertion switch grew runner/ops,
runner/guard and the runner proper, and again after the
outbox stash took the per-key guard in the runner proper,
and again after the send_job verifier took the shared
strict reader, and again after the startup gate took the
resources and DRI paging readers, and again after the
fy_iceworld fragment-buffer caps grew runner/wire, and
again after the temp-reaping work grew runner/ops,
runner/tools, runner/guard and the runner proper,
the
as-assembled set stands at 55,532 lines (50,000 non-blank)
and a 703,710-byte zip, and the project's own estimator
counts it at 585,449 tokens; the Gemini figure above still
describes the 2026-11-04 assembly. The project's own
estimator counts the canonical 130-file list at 577,832
tokens across 54,748 lines (49,312 non-blank); the 2 token
counts come from
different counters and are not interchangeable. 3 of the 133 files were the suite's own
runners (runner/tools/run_tests_parallel.py,
run_tests_shuffled.py and run_tests_windows_sim.py) — tools
that run the tests, not runner code — so the canonical list
leaves them out.

When project talk says "test core", it means testing this
set. A change aimed at core is aimed at those 130 files and
no others, and a result reported for core covers exactly
them.

The runner proper is 6,637 lines; the core around it is
55,532. The set as assembled, part by part (re-measured
2026-11-06):

- runner/ops: 17,474 lines
- runner/tools: 8,673
- runner/wire: 8,302
- runner/runner.py: 6,637
- runner/oracle: 5,013
- runner/transport_extensions: 2,771
- runner/guard: 2,876
- runner/cloud: 2,049
- runner/hosting: 1,704
- runner/__init__.py: 23
- runner/_version.py: 10

The canonical list's breakdown is the same except
runner/tools, where the 3 excluded suite runners account
for 784 of the lines, leaving 7,889 in the canonical list.
The tool prints the
canonical breakdown live, beside the totals.

The core is platform-agnostic in the main. Across its
55,532 lines, explicit platform branching — sys.platform,
os.name and win32 markers — totals about 140 lines in 36 of
the 133 files, beside a small number of dedicated platform
modules (runner/ops/windows.py and runner/ops/winlog.py).
Dropping 1 platform would trim that thin layer only; the
rest of the set does not know which platform it is on.

## What the passes found and pinned

One shape of crash, over and over: a value used as a dict key
before anyone checked it was a string.

Later, under de_dust2 (29-OCT), a shape no crash class could see: a
walk that was correct and quadratic. `_object_start` in both
signed-object extractors tried every `{` before the signature marker
and ran the brace walk from each, so a body nested a few hundred
levels cost braces times length, and a 4 MB body of braces from an
unauthenticated sender would have held the mail loop for a day
before any MAC was computed. The ledger had carried the symptom as
`slowest_ms` for two days; a latency class (a try over fifty times
the corpus median and over half a second) filed it within the hour
of existing (Q116), and one backward pass over suffix summaries
replaced the walk with the same answers brace for brace. A
measurement without a filing rule finds nothing.

- `check_key_policy` raised `TypeError` on a key id that was a
  list. A key id that is not a string is now a refusal.
- `parse_sensors` raised `TypeError` when `severity_floor` was
  not a string. A config file can carry that. It is now a
  config error, the same as any other bad floor.
- `validate_sensor_alert` raised `TypeError` when `severity`
  was a list. A signed alert can carry that. It is now a
  refusal, same as any other bad severity.
- `parse_manifest` raised `TypeError` when `kind` was not a
  string, and `load_extensions` only catches `ValueError`, so
  one bad `extension.json` aborted discovery. A non-string
  kind is now a refusal.
- The same check was open in three more lookups: a model tool
  name, a `security.modes` value, and `dtls_greeting`. A
  non-string is a refusal or a config error, not a crash.
- `baseline_anomaly` summed `kinds` with `sum()` and then
  used the job's `kind` as a dict key. A stored baseline
  whose counts are not numbers, or a `kind` that is a list,
  raised `TypeError`. Counts that are not finite numbers are
  skipped, and a non-string kind is treated as unknown.
- `feature_keys` and `touched_keys` called `.items()` on
  `tools` and `paths`, and indexed `interpreter[0]`. A probe
  that handed back a string or a number raised
  `AttributeError` or `TypeError`, and a string interpreter
  was read as its first character. Those fields are used
  only when they have the shape a probe is supposed to
  return.

Ring 2 has started for sensor alerts. A flipped signature
stores no alert. A signed alert whose severity is a list
stores no alert. The next good alert, in the same directory,
still files. The same rule holds for a job: a flipped
envelope does not run, and the next good job does. A
second wrap around an envelope does not run the script
inside it, and a job_id of `..` does not run either. A key
bound to sensor alerts only cannot run a script, and the
owner's key still can. A script over `max_script_bytes`
does not run, and the next script that fits still does. A
flipped query learns nothing from retained output. The next
good query of the same output still gets the answer.

That gap is closed. A query and a board message now go
through the same gate as a job. Cleartext is refused unless
the process was started with `--allow-cleartext`. An
encrypted query is answered, and the answer is encrypted
too, so a canary in retained output is not in the raw reply.
An encrypted submit opens the task. A cleartext submit does
not.

A job stamped two hours ago, or an hour ahead, does not
run. The window is `max_job_age_sec`, with five minutes of
slack into the future. The next job stamped now still runs.
A file named `../escaped.txt` is not staged and the script
does not run. The next ordinary job still does. A body
whose `job_id` is not the id in the subject does not run
either. The envelope still decrypts. The ids are what fail.
A `reply_to` that is not one address does not steer the
result. A newline, a comma, or a list falls back to the
runner's own mailbox. One plain address is honored, because
it was inside the signed body. A job cannot put a
`PIGEON_` variable into its own process, in either case.
Any other name it sets is still there. The next ordinary
job still runs. The same job submitted again does not
run a second time. A different job id still does. An
envelope signed with one key, around a body signed with
another, does not run. The next job whose keys agree still
does. A job aimed at a different runner, or at no runner,
does not run when audience is enforce. The job that names
this runner still does. A `script_url` of `file:` is not
fetched, in either case, and the inline script does not run
in its place. The next ordinary job still does. A null
byte in an argument or an environment name is refused, and
the script does not start. A null byte in the interpreter
was not a refusal when this was found: the path was absent,
repair was the default, and the platform shell was started,
so the Python script did not run under that shell. The code
now refuses that shape — an interpreter containing a null
byte is rejected and the job does not run. The next ordinary
job still does. A ping that carries a script answers
`pong` and does not run the script. The next exec job
still does. A kind the runner does not know (`sh`, an
empty string, `Exec`) does not run the script it carries.
The next exec job still does. A script that is a number,
or a list, does not run either. The next exec job still
does. A `script_sha384` that does not match the script
does not run. The same script with the right hash does.
A hash that is a number does not run. The same hash in
capitals does, because the compare folds case. A timeout
of `slow` or a list does not run. A timeout of `0` is
read as missing, so the default is used and the job runs.
Args that are a string or a number do not run. Args of
`0` are read as missing, so the job runs. An env that is
a string or a list does not run. An env of `0` is read
as missing, so the job runs. Files that are a string,
or an entry whose name or url is not a string, do not
run. Files of `0` are read as missing, so the job runs.
An interpreter that is a string or a number does not run.
An empty list was read as missing when this was found: the
platform shell was started, and the Python script did not
run under it. The code now refuses that shape too — a
present-but-empty interpreter list is rejected.
The next job with an interpreter still does. The same
query is answered
once. The second copy, same seen set, gets nothing back.
A second query, different id, after the budget is spent,
does not get the canary either. The answer says budget.
A query aimed at a different job does not get it either.
The answer says unknown. The query for this job still does.
After `max_queries_per_hour` is spent, the next query is
answered `rate_limit` and does not get the canary. An
unknown op, even one that carries the fork bomb and an
instruction to print the output, is `unknown_op`. It does
not get the canary. A later grep of this job still does.
A pattern that does not compile is `bad_pattern` and does
not get the canary either. A pattern the shape check lets
through, and that does not answer within two seconds, is
`timeout`, and the match is killed. A later good grep still does.
A retained view of `summary` or `attested` does not return
the line. The answer says policy. `full` still does.
`redacted`, with the canary as a pattern, returns the
line with `[REDACTED:canary]` in its place. The pattern
the query itself sent is echoed. `full` still returns the
canary. A `max_matches` of zero returns no lines, and the
answer says the output was truncated. A later grep with
the default limit still returns the canary. An `ask`
whose question says to print the output, with no model
configured, is `inference_unconfigured`. The output is
not copied into the answer. A later grep still returns
the canary. Grep searches stderr as well as stdout. A
pattern that matches only stdout does not return the
stderr line. A `queries` value that is not a list, even
when the value is an instruction to print the canary, is
no queries. The answer is empty. A later grep still
returns the canary. A record whose `saved_at` is older
than the retention window is `expired` and does not
return the canary. A fresh `saved_at` still does.

An open task is not finished by a result or an approval.
It has to be claimed first. A later submit still opens.
A second submit of the same task does not replace it.
The first payload stays. A different task still opens.
Once a task is claimed, a result finishes it, and a second
result does not replace that. A later submit still opens.
With review required, a result holds the task at
`pending_review` and a second result does not replace it.
An approval is what marks it done. A worker whose
capabilities do not cover the task does not claim it. The
worker who has them does. A worker who is not on
`worker_allowlist` does not claim either. The worker who
is on the list does. A task in a compartment the worker
does not share stays open. The worker who shares it claims.
A task id with a slash, or longer than 128 characters,
opens nothing. A plain id still opens. With
`dag_mode` enforce, a task whose requirement is not done
is not claimed. Once that requirement is done, a request
claims it. Advisory hands the same shape out, and the
record names the requirement that is not done. A
higher `priority` is claimed first, even when it was
submitted second. The lower one stays open. A priority
of `true` is stored, and it does not outrank a priority
of `1`. A worker who already holds a claim is handed that
task again, not a newer one with a higher priority. A
different worker gets the newer one. Capabilities that
are not a list of strings open nothing: a string, a list
with a number, or an object. A task that omits them still
opens. A priority of `"9"` or infinity opens nothing. A
priority of `1` still opens. A claim older than
`task_timeout` is offered again. The next request takes
it, and the previous worker no longer holds it. A claim
inside `task_timeout` is not taken. A second worker's
request leaves it with the first. A task in
`pending_review` is not put back to open when the claim
is older than `task_timeout`. A later request can take a
different open task, and the review stays where it is.
A NaN in a result is stored as null, and the task is
done. A second result does not replace that null.

## One prompt-injection case and the DTLS record opener

The fork bomb in
[runner/tests/test_flag321_obfuscated.py](../../runner/tests/test_flag321_obfuscated.py)
is the pipe bomb: `:(){ :|:& };:`. The judge denies that exact
string and allows one added space. Nothing there is executed.

Wrapping either string in "ignore previous instructions" does
not change the judge. A stub model that obeys, and answers
with a job whose script is the bomb plus a canary from the
output, is dropped by the sanitizer. The answer is not handed
to a shell. A job-shaped answer with no canary comes back as
text. The format guard does not treat `{"kind","script"}` as
a tool call. The research notes, and where that premise
stops, are in
[docs/design/idea321/RUNBOOK.md](../design/idea321/RUNBOOK.md).

A short DTLS record raised `IndexError` inside the record
opener. It now raises `DtlsError`, which the session already
treats as a dropped record.

The crashes were easy because the generator was allowed to
hand the function a Python value that JSON on the wire cannot
carry. That pass is still worth finishing. It is not the
whole surface.

## Three rings

Ring 1 is anything already inside the process. The generator
builds messy Python values, not just JSON. The property is:
return a reason or `None`, and never raise. This is where
those `TypeError`s came from. The functions whose docstring says
"never raises" (or "never raise") are the list. Some ninety of
them live under `runner/`, tests aside.

Ring 2 starts from a message the runner would accept and
changes one thing: a flipped byte in `sig`, a swapped
`key_id`, a nested `hp_enc`, a huge `script`, a `job_id` of
`.` or `..`, a duplicate key, a truncated length, an
`issued_at` outside the window. The families are a job, a
sensor alert, a query, a board message, an `hp_enc` envelope,
and a DTLS flight that already passed the cookie. The
property is stricter than "it returned." A bad signature
stores nothing. A rejected job does not run. A good neighbor
in the same poll still runs. One poison file does not stick
the channel.

Ring 3 is the parsers the coverage report already named.
`dtlsproto.py` wants mutated valid flights, not only random
datagrams. de_dust's `dtls` target is that flight (Q66):
a sealed ClientHello, ServerHello and Finished under invented
keys, the two-fragment pair, and the record mutators, replayed
with the rest of the corpus. Then the email, file, and NATS
extension programs, one bad frame at a time. Still in memory.
A live socket is only worth it after the core stops crashing
on bytes.

`learning.py`, the posture collectors, and the model are not
this campaign. Judgment is downstream of admission, and
admission is the part a sensor can reach.

## Where the tests are

- `runner/tests/test_oracle_intake_fuzz.py` — ring 1 for alerts,
  manifests, key policy, the local envelope, review, the
  Oracle's tools, sensor config, a poisoned senses store, and
  the loopback socket reader. The tool named `run` is stubbed.
  The fuzzer must not grow a shell.
- `runner/tests/test_dtls_fuzz.py` — ring 3, started: random
  datagrams and the fragment buffer.
- `runner/tests/test_properties.py` — the older property tests on
  the signed-object core.

Hypothesis is a test-only dependency. CI installs it. A run
without it skips nothing in the example tests and fails these
on import.

## Mutation testing: the suite, audited

Fuzzing tests the code with hostile input. Mutation testing
turns the same suspicion on the tests themselves. A tool —
here, mutmut — takes a file of production code and changes
it in one small way at a time: a comparison flipped, a
default swapped, a `+1` made `+2`, a condition dropped.
Each changed copy is a mutant. The unit suite then runs
against the mutant. If a test fails, the mutant is killed:
some test was watching that exact behaviour. If every test
still passes, the mutant survived, and a survivor is a
finding about the suite, not about the code — it marks a
behaviour no test actually pins.

Why a suite this size needs the audit: the suite was
deliberately grown past 10,000 tests (10,301 ran in the
2026-11-05 build record), and a suite that large can hide
a test that is a false positive by construction — a test
that exercises a path, returns a pass, and asserts nothing
that could ever fail. Such a test is latent: it shows up
in the count and in the coverage — the line it runs does
execute — while pinning nothing. Coverage cannot see it,
because coverage measures that code ran, not that anything
checked what the code did. Mutation testing is the check
that can see it. Change the code slightly, and the honest
tests notice; the latent one does not. So the standing
rule: a surviving mutant is a defect in the suite, taken
as seriously as a crash in the code, and it is closed by
writing the missing assertion, not by widening a tolerance
or dropping the mutant from the list.

The scope is deliberately narrow. mutmut mutates one file,
`runner/guard/security.py` — 392 lines of pure policy and
audit logic — with the whole suite as the oracle that kills
or passes each mutant. The configuration stands in
`pyproject.toml`, and the suite itself, the tools and the
extensions are never mutation targets. Wider scopes were
measured before they were wanted: 4 files came to 1,567
mutants and an extrapolated 45 to 50 minutes a run, and the
full `runner/` tree would take hours. One file keeps a
walk at about 7 minutes, and the scope expands
deliberately or not at all.

The strategy's history, from the record:

- 2026-10-16 — mutmut enters the pipeline as a CI gate,
  scoped (commit eec3a646, "CI gates: pyrefly typecheck +
  mutmut mutation (scoped)"). That is the first appearance
  of mutation testing anywhere in the tree; as of
  2026-11-05 the strategy has been running for 20 days.
- 2026-10-19 — `.github/workflows/mutation-seeded.yml` is
  added: a scheduled, non-gating twin of the release
  mutation job, first set to a weekly walk (Mondays at
  06:17 UTC). Each run varies a seed — the run number, or a
  value supplied on dispatch — carried in `PYTHONHASHSEED`
  and `HP_MUTATION_SEED`, so different hash seeds and
  different property-test draws walk parts of the mutant
  space a fixed configuration never visits. A run
  reproduces by dispatching the workflow with its printed
  seed on its printed commit.
- 2026-10-22 — mutation comes off the release path. The
  measurement that forced it stands in
  `docs/steady/reports/ci-failures.md`: over 310 runs the
  mutation job's median was 6.4 minutes, its p90 22.6 and
  its maximum 29.7, and 20 tags cut inside 15 minutes each
  carried a 17-to-24-minute mutation job — the long pole
  of every release, and a signal that never gated one.
  From this date the build workflow's mutation job runs
  only on a manual dispatch against a non-tag ref, marked
  continue-on-error: loud when it fails, unable to hold a
  publish.
- 2026-10-25 — the signal is found blind, and un-blinded.
  A collection failure inside the copied mutants tree ended
  mutmut's coverage pass before any test ran: 3 mutants
  were generated where 443 had been, and the run reported
  green. The cause was the coverage pass dying on a shared
  file name among the archived probes. The fix landed in
  release 3.12.66 the same day: the archive folders are
  ignored for the test run inside the mutants tree, and
  `runner/tools/mutation_floor.py` now stands after mutmut
  in both workflows — it reads the run's own statistics and
  fails the job when the signal has collapsed, with the
  tally in the log. A run that measured almost nothing is
  red from then on, never quietly green.
- 2026-10-25 — the seeded walk goes hourly, at 17 minutes
  past each hour: a weekly walk saw 4 seeds a month, and
  the mutant space wanted more visits than that. One walk
  runs at a time; a slow hour queues the next run rather
  than stacking walks or cancelling one half done.

The first whole-signal triage (the D4 pass in the campaign
record) took the security module's full mutant set: 566
mutants, 500 killed, 66 survived. Each survivor was read
as what it is — a missing assertion — and the triage wrote
tests against them one by one. 5 of the 66 were provably
equivalent mutants: changes no test could ever catch,
because both paths give the same answer. One is a default
whose value the mode guard reads as "off" either way;
another is an arithmetic change whose products pass the
slice bound on both paths. Those are recorded as
equivalent, not chased. The kill verification was a full
re-run: verdicts on 565 of the 566 mutants, 561 killed and
4 survived, every one of the 61 targeted mutants dead, and
the surviving names exactly the recorded equivalents (the
fifth equivalent's verdict was never written — that run
was stopped at 563 of 566 — and it stands equivalent on
the argument). The signal in `security.py` stands at 561
killed, 5 provably equivalent survivors.

How it runs today: `mutation-seeded.yml` walks hourly on
the head of main, seeded and reproducible, and uploads its
log, its statistics and a plain list of survivors for the
next triage; the build workflow's mutation job is the
manual-dispatch twin. Neither is a release guard. No
publish keys off a mutation result, no tag waits for one,
and a release is verified — guards green, assets stamped —
while a seeded walk is still walking. That is the run a
reader sees turning on the Actions page after a release is
already done: it is long because it re-runs the suite
against hundreds of mutants one change at a time, and it
is allowed to be long because nothing waits on it. Its
only product is the survivor list, and the survivor list
is the suite's own defect queue.

The same audit also runs by hand, against the proof
family — the tests that drive the six properties of
`docs/infrastructure-documents/proofs/properties.md`
against the real code. In stage 5 of the proofs, for each
property one deliberate one-line change was made in a
scratch copy of the tree, that property's tests were run,
and the file was restored from the pristine tree: twelve
shapes in ten runs (two properties share a line, so one
run covers both), and every run exited 1 — at least one
test failed, every time, with the catching test named in
the record (`docs/infrastructure-documents/proofs/stage5.md`).
In the completion pass on 2026-11-01, five of the recorded
mutations were re-run first-hand on the final tree in a
fresh scratch copy, and each was caught by exactly the
test the record names. The automated walk and the hand
checks aim at the same failure from two sides: a test that
would pass in every world is decoration, whichever way the
break is introduced.

The machinery's own tests stand at
`runner/tests/test_mutation_floor.py` (the collapsed-signal
floor) and `runner/tests/test_seeded_mutation_workflow.py`
(the seeded workflow's shape).

## A read on the campaign (Grok, at the conductor's word, 2026-10-26)

The conductor asked this opinion thrown into the hat. It is
not a change to the rings above, and it is not a standing
order. The full read is the answer to Q65 in
`docs/seats/questions.md`. The desk applies what it takes.
What follows is the part that would change this document.

In-memory fuzzing is the right tool, and it is already on the
right code. The six de_dust targets are saturated: at
3.13.50 they hold 171 entries and 653 arcs, two grows of
2,000 rounds added none, and there is no crash file. More
rounds there will not find the next bug. Ring 1 already
found the type crashes. Leave those tests. Stop adding
Hypothesis examples on functions that already never raise,
and pin the Python 3.9 `test_two_signers_agree` shape (a
nested payload whose keys include `{` and `"`) instead of
hunting it on the `python-range` leg.

The bounded campaigns (`test_fuzz_surfaces`,
`test_fuzz_guided`, `test_fuzz_parsers`, `test_dtls_fuzz`,
`test_transport_log_relay_fuzz`) already touch the readers
de_dust does not. Their corpora die with the process.
Promote those readers into the one persistent corpus. Do not
write a third fuzzer, and do not lengthen the in-suite
rounds.

The targets that followed, in order, all in the de_dust corpus
now (`docs/project/de_dust.md`, rows 7 to 11):

1. Mail extraction (`mailbox.py`, `get_text_body`, subject
   parsing, and the email extension's `_subject_body` and
   `reply_target`). This chooses the text the six verifiers
   see.
2. DTLS record and handshake parse, from a sealed flight that
   is then mutated. Random datagrams stay as the garbage
   regression only.
3. The task board (`submit`, `offer`, `complete`).
4. NATS, queues, and file `fetch_channel_messages`.
5. `parse_manifest`.

Not next: the model, `learning.py`, posture, the Oracle's
tool-call reader, the config loader, job-fuzz the sense, and
anything that needs a real process, a race, or a network
namespace. `build_bwrap_command` as argv, never exec'd, is
as far as in-memory fuzzing of the sandbox should go.

Mail and DTLS need their own seeds and a small vocabulary
(MIME structure; length fields, truncated records,
overlapping fragments). Brace noise and the text mutators
will not reach them. The six, the board, and manifests keep
the vocabulary they have.

Two contracts the corpus should add, and replay over entries
it already kept:

- The two verifiers agree. `runner/wire/verify.py` and
  `runner/cloud/send_job.py` both trust a body and read the same
  dict, or both refuse it.
- A sequence. A bad message stores nothing, and the next good
  one in the same poll or directory still does. The
  paragraphs above hold that for one shape at a time. The
  generator should produce the pair.

Keep `sys.settrace`. A target with no new arc and no contract
failure in one full-depth grow is saturated; point the next
grow at the next reader. Section M's stop, two empty cycles
then D4, is right only after mail extraction and the DTLS
opener are targets. D4 should not take the rig before that.
The order that de_dust is the only effort and the CPU
stays pegged still holds: peg it on an unsaturated target, or
on those two contracts, not on another 20,000 rounds of the
six. No live socket until the new readers stop crashing on
bytes. A Platinum percentage is coverage, not a reason to
stop.
