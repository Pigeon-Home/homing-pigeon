# Stage 3 — the model checked against the code's order

This is the reconciliation stage 2 deferred: `Gate.tla` and
`Claim.tla` laid step by step beside the code they claim to
model, in both directions. Each model step is matched to the
code location that performs it, in order. Each code branch in
the gate that the model does not represent is named as a gap.
Each place where model and code genuinely differ is named as a
divergence, classified, and left standing as a finding — this
pass moves neither the model nor the code, and the statement in
`properties.md` does not move either.

The code read for this reconciliation is the code at the
`testing` branch tip this stage started from, which is the code
at `6d6288c5` for every file named below (the proof commits
since then touch only this directory and its pinning test). The
gate is `handle_mail` in `runner/ops/mail.py`; the helpers it
calls live in `runner/runner.py`, `runner/wire/verify.py`,
`runner/guard/security.py`, `runner/guard/textutil.py`, and
`runner/ops/misc.py`.

## The step-by-step match

Model steps are the numbered disjuncts of `Next` in `Gate.tla`.
Code locations are `handle_mail` unless another file is named.

| Model step | What it checks | Code location | Match |
|---|---|---|---|
| 0. Panic | `panic` stops the handling before everything | `mail.py` lines 42–58: `_panic.matches` on the subject, then `_panic.fired`, both before any MAC work and before the seen set | Matches, with an outcome-label difference (finding F3) |
| 1. Raw size | `rawOver` refuses before signature work | `mail.py` lines 64–70: `max_job_bytes` (C1) checked on the raw bytes before dispatch | Matches. The code applies the cap when the subject carries the `[HOMING-PIGEON]` marker; unmarked mail is not a job message and is refused later by having no job id, so no unmarked message executes either way |
| 2. Early dispatch | Anything that is not a fresh job (`isFreshJob` false) does not execute | `mail.py` line 72 calls `_early_dispatch` (`runner.py` line 4653): cancel mail, query mail, board mail, version 2 mail, a bounce of the runner's own mail, a subject with no job id, the version 2 answer-only refusal, and the in-memory seen-set lookup, in that order | Matches. The four non-job kinds and the bounce are folded into one model bit; their internal order among themselves cannot affect a job's execution, because none of them returns a job to execute. The seen-set part is the in-memory set only at this point in the code — the disk half of the seen check is step 15, in both the code and the model |
| 3. Verification and decryption | `signed` false, or `innerMismatch`, refuses | `mail.py` line 87 calls `_verify_and_decrypt` (`runner.py` line 4604): `verify_body_keyed` verifies the outer body, an `hp_enc` envelope is decrypted and its inner body verified under the same key, and an inner key id that differs from the outer one raises | Matches, with additional pre-signature refusals inside the code's verification that the model folds into `signed` (gap G1) and one check the code performs here as well as at step 6 (finding F1) |
| 4. Cleartext | An unencrypted arrival refuses unless the process flag allows it | `mail.py` lines 96–130: `job_was_encrypted` false and `_cleartext_jobs_allowed()` false refuses, after verification and before the audience check (C8) | Matches, including position |
| 5. Audience | `enforce` refuses a mismatch; `audit` records and continues (`noted`); `off` does not look | `mail.py` line 132 calls `audience_allows` (`verify.py` line 1149), which runs `check_audience` (line 1122) and puts a mismatch through `sec_decide`: enforce denies, audit logs a `would_deny` entry and proceeds, off never reaches the check | Matches, with a configuration precondition the model's bit folds away (finding F4) |
| 6. Encodability | `surrogate` refuses | `mail.py` lines 138–142: `_lone_surrogate(job)` refuses after the audience check | Matches in position for this check — and the code also performs the same check earlier, inside step 3 (finding F1) |
| 7. Script size | `scriptOver` (UTF-8 bytes over C2) refuses, after the signature | `mail.py` lines 147–154: `max_script_bytes` measured as `len(script.encode("utf-8"))` | Matches, including position and measure |
| 8. Version, type, identity | `versionOk`, `typeOk`, `idOk` all required | `mail.py` lines 156–161: `_version_ok(job.get("v"))` (integer 1 only, `runner.py` line 283), `type` is `job`, body `job_id` equals the subject's | Matches. The code splits this into two rejects (version/type, then id); the model combines them at the same position |
| 9. Freshness | `fresh` false refuses | `mail.py` lines 163–176: `issued_at` parses (`_fromiso`, `textutil.py` line 77), carries a timezone, and sits inside the window — not more than 300 seconds ahead, not older than `max_job_age_sec` (C12) | Matches |
| 10. Key policy | `policyOk` false refuses | `mail.py` lines 178–183 call `check_key_policy` (`verify.py` line 878): the key directory's verdict first, then the key's own entry — kinds, recipes, interpreters, timeout, and the script-pinning list (C14) | Matches |
| 11. Pinned-key constraints | An enforce denial (`constraintDenied`) refuses | `mail.py` lines 190–219: where the key has a policy and any of `policy_env`, `policy_files`, `policy_args` is not `off`, each finding from `check_policy_constraints` (`verify.py` line 1022) goes through `sec_decide` (`security.py` line 532); an enforce decision refuses, an audit decision logs and proceeds | Matches. The model's bit is the outcome — an enforce denial — which is exactly what `sec_decide` returns false for |
| 12. Sensor branch | `sensor` leaves the path with outcome `sensor`, through the gate | `mail.py` lines 221–224: `kind == "sensor_alert"` goes to `_ingest_sensor_alert` and returns | Matches. `SensorInv` in the model lists the checks through step 11, which is the code's position for this branch |
| 13. Advisory review | A pass step that changes no decision | `mail.py` lines 226–244: the Oracle review runs, a review that raises or is not JSON is dropped, and the job proceeds regardless | Matches |
| 14. Dry run | `dryRun` ends the handling with outcome `dry` | `mail.py` lines 250–254: after the review and before the claim, a dry run describes the job and returns, executing and recording nothing | Matches, including position |
| 15. The claim | `claim = "taken"` refuses; `"onRecord"` ends in a resend; `"free"` proceeds | `mail.py` lines 260–282 under `_MAIL_LOCK`: a `skey` in the seen set or in `_IN_FLIGHT` is skipped; `_disk_owns` (`misc.py` line 241) refuses a key already in `seen.json` or held by a live claim file in another process; the resend itself is `load_sent_result` at lines 320–330, reached after the claim is taken | Matches in what it guarantees (below, under `Claim.tla`), with the model's claim state an input where the code derives it, and two outcome differences (findings F3 and F5) |
| 16. Cancel, then execute | `cancelled` refuses; otherwise the handling executes | `mail.py` line 340: `_cancel.take_cancel` inside the execution span refuses a job its own key cancelled before arrival; `execute_job` is called at line 438 | Matches for the cancel and the execution. The span between them holds three code behaviours the model does not represent (gaps G2, G3, and finding F2) |

`Claim.tla` against the code: the model's one slot, taken
under an implicit lock by whichever of two handlers arrives
first, is two mechanisms in the code that compose to the same
shape. In one process, the check-and-add is atomic under
`_MAIL_LOCK` (`mail.py` lines 260–282, the `_IN_FLIGHT` add
inside the same locked span). Across processes, `_disk_owns`
takes the claim as a file under the seen-file lock in
`_with_seen_file` (`runner.py`), with a stale-claim rule (a
dead holder, or a claim older than `_CLAIM_STALE_SEC`) that
belongs to the replay property, P5. Two handlers racing one
job id in one process is the race `Claim.tla` checks, and the
code's in-process half is that race, faithfully. The
cross-process half differs in the loser's outcome, not in the
safety claim (finding F3).

## Gaps — code branches the model does not represent

Each gap below is a branch in the gate's code with no model
step. For each, the reason it does or does not matter for P1
is stated. A gap that only ever refuses more, or that runs
after execution and shapes the result rather than the
decision, cannot create an execution P1 forbids; it is still
recorded, because stage 5's conformance tests and later
properties need the full list.

- **G1. Verification's own early refusals.** Inside
  `verify_body_keyed`, before any MAC is computed, the code
  refuses a body that is not a string, does not parse, is not a
  JSON object, nests past `NESTING_LIMIT`, or uses literals and
  numbers JSON does not have; it also retries verification on a
  control-stripped form of the body when the received form
  fails, because a mail transport may insert control characters
  — the signature is over the cleaned form. The model folds all
  of this into `signed`: a body that fails any of it does not
  verify. Safe for P1: every one of these branches refuses, and
  the retry accepts only a signature that verifies over the
  cleaned text byte for byte.
- **G2. The judge.** Inside step 16's span (`mail.py` lines
  343–349), with `judge` in `enforce` mode, a job the judge
  gives reasons against is refused after the claim and before
  execution. There is no model bit for it. Safe for P1 in the
  refusing direction — the code refuses some jobs the model
  would execute, never the reverse — and recorded because a
  reader comparing counts of refusals would find the code
  stricter than the model here.
- **G3. The version 2 before-execution exchange.** Also inside
  step 16's span (`mail.py` lines 415–433): when protocol
  version 2 is enabled, a question-and-answer exchange runs
  before `execute_job`. A failure in it is logged and the
  exchange's segments are dropped; it never refuses the job.
  Not represented in the model. Safe for P1 as the code stands:
  it cannot block, so it cannot be a gate, and P1's claim does
  not rest on it — the same reasoning `properties.md` applies
  to the Oracle.
- **G4. The claim and record mechanics.** The stale-claim
  rule, the `_IN_FLIGHT` lifecycle and its release in the
  `finally` span, and the resend's digest condition
  (`load_sent_result`, `runner.py` line 2326, returns no record
  when the recorded result's digest is for a different job
  shape under the same id) are mechanics the model abstracts
  into the claim's three states. Safe for P1's claim — in the
  digest-mismatch case the no-re-execution guarantee rests on
  the disk seen claim at step 15 rather than on the record
  check, and it holds there — and squarely P5's material when
  the replay property is modelled in full.
- **G5. Everything after `execute_job`.** Result fitting to
  `max_result_bytes` (C3), the result chain, retention and the
  aging-out window in C15, and the contents of the result are
  not in the model. They shape what is delivered, never
  whether execution happens; they belong to P2 and P5.
- **G6. `execute_job`'s internals.** Kind dispatch and
  confinement inside execution are P2's surface. The model's
  claim ends where P1's does: at the start of execution,
  reached only through the steps above.

## Findings — where model and code genuinely differ

A finding is a place where the two do not merely differ in
detail but in what happens. None of the four below is a
counterexample to P1: in each, the set of handlings that
execute is the same in the model and the code, or smaller in
the code. Each is recorded plainly, with its classification,
and none is resolved in this pass.

- **F1. The encodability check runs twice in the code, once in
  the model — and the first run is earlier than the model's
  step 6.** `verify_body_keyed` refuses a body carrying an
  unpaired surrogate before any MAC is computed, as part of
  step 3; `handle_mail` then checks the (possibly inner)
  payload again at lines 138–142, the position the model
  gives it. A cleartext body with a surrogate is therefore
  refused by the code at verification, where the model refuses
  it three steps later. Classification: model simplification,
  not a code defect and not a model defect against P1 — both
  refuse, and no handling executes either way. The difference
  is observable only in which refusal a log records. When the
  model next moves, it moves to the code here: the surrogate
  belongs in step 3's refusal set as well as at step 6.
- **F2. The code can execute a repaired job; the model
  executes exactly the message it checked.** Inside step 16's
  span (`mail.py` lines 356–413), the Oracle opinion may
  repair a job whose interpreter cannot start by substituting
  the platform default interpreter, and the job that executes
  is the repaired one. Before it runs, the repaired job goes
  back through the judge and through `check_key_policy` — so
  the one gate clause the substitution can touch, the key
  policy's interpreter list, is re-checked on the job as
  repaired, and a refusal there refuses the job. Every other
  clause speaks of fields the substitution does not change:
  it signs nothing new, resizes nothing, and the signature
  still covers the job as received, with the repair disclosed
  in the result. Classification: a model gap with a bounded
  blast radius, not a counterexample — P1's clauses are stated
  over the job as received, and the re-check keeps the policy
  clause true of the job as run. It is recorded as the
  reconciliation's most substantive finding because "the job
  that passed the gate" and "the job that ran" are not
  byte-identical on this path, and stage 5's conformance family
  should pin the re-check: a repaired job whose new interpreter
  its key's policy forbids MUST NOT execute.
- **F3. Two outcomes the model calls finished, the code calls
  deferred.** When the panic has already fired, the code
  leaves the message unseen (`mail.py` lines 55–58) for a
  later poll, where the model's step 0 refuses it. When
  another process holds a live claim, the code leaves the
  message unseen (`mail.py` lines 266–278) so a crash there
  can be recovered, where `Gate.tla`'s step 15 refuses and
  `Claim.tla`'s losing handler finishes. Classification:
  outcome-label difference, working as the code intends —
  deferral is a delivery property (P5), and in neither case
  does anything execute. The model's labels are the coarser
  ones; nothing in P1 turns on the distinction.
- **F4. The audience clause has a configuration precondition
  the model's bit folds away.** `check_audience` returns no
  mismatch when no `runner_id` is configured, whatever the
  mode — with the feature in `enforce` and nothing to bind to,
  clause 4 is vacuous, exactly as it is when the feature is
  `off`. The model's `audienceOk` bit presumes a configured
  `runner_id`, which is how `properties.md` states the strong
  form ("under audience `enforce` with a `runner_id`
  configured"), so model and statement agree; the fold is
  recorded so a reader does not take the enforce configuration
  to claim a binding no deployment configured. Classification:
  assumption working as stated, in both the model and the
  code.

## The stage 2 counterexamples, classified

Stage 2 produced exactly two counterexample traces, both from
configurations that were expected to fail. Stage 3's done
criteria require each to be classified:

- **`GateWitness.cfg` — `NothingExecutes` fails under
  enforce.** The trace ends in execution for a message that is
  signed, encrypted, fresh, within both caps, addressed to
  this runner, with a free claim and no cancel. Read against
  the code above, that handling executes there too: it is the
  gate letting a good job through, which is the behaviour the
  witness exists to exhibit. Classification: assumption
  working as stated. Not a model defect (the model was built
  to contain this trace) and not a code defect (the code's
  path for it is steps 0–16 with every check passing).
- **`GateDefaultWitness.cfg` — `AudienceWasRequired` fails
  with the audience feature `off`.** The trace ends in
  execution with `audienceOk` false and every other clause
  holding. Read against the code: with the mode `off`,
  `check_audience` is never consulted and `audience_allows`
  returns true, so the code executes that job too. This is
  clause 4 in its default, vacuous form — the weakening
  `properties.md` requires not to be hidden — and the same
  invariant checked under `enforce` in `GateEnforce.cfg`
  holds. Classification: assumption working as stated.

No other counterexample exists from stage 2: the four
configurations in `stage2.md`'s table held. There is
therefore no trace left unclassified, and no trace in either
class that this reconciliation found to be a code defect.

## Verdict

Every model step in `Gate.tla` matches a code location that
performs it, in the same order; the one race in `Claim.tla`
matches the in-process half of the code's claim, with the
cross-process half recorded. Every code branch in
`handle_mail`'s gate is either matched, listed as a gap with
its reason, or recorded as a finding. The findings do not
include a counterexample to P1, and no unexplained divergence
remains. The model was not edited in this pass and no runner
code was changed; F1 names where the model moves when it next
moves, and F2 names the conformance test stage 5 owes.
