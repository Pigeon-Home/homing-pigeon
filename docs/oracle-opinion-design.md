# Design: the Oracle's opinion, carried on the result

Status: implemented 2026-10-18. The member is specified in
PROTOCOL 3.1/3.2 and built in `runner/opinion.py` (latitude
ceiling `oracle_opinion_mode`, default repair — diagnose at
first build, raised 2026-10-19 at the owner's direction;
prediction and
repair behavior under `oracle_opinion_predict` /
`oracle_opinion_repair` / `oracle_opinion_model`). Andrew's
proposal (2026-10-15), elaborated 2026-10-18; recorded in
FUTURE.md under "Before a job runs". This document remains the
design record the build started from.

## Why repair is the default

A job that arrives written for the wrong platform — a POSIX
shell idiom aimed at a Windows box, an interpreter name this
machine doesn't carry — is usually a fat-finger, not an
attack. The sender's intent is legible and the mismatch is
mechanical. A system that refuses such a job teaches the
sender nothing except that the box is brittle, and it spends
the one resource a development loop cannot refill: the
engineer's momentum.

Repair converts the hard stop into a recorded correction.
The job runs; the result states plainly what was sent, what
was changed, and the digest of what was received, so the
sender discovers the mistake as a footnote in a result they
already have — *oops, wrong platform* — and fixes it in
thirty seconds when it suits them, instead of mid-flow at
the moment of failure. The discipline that makes this safe
rather than reckless is that repair never guesses: it acts
only where the deterministic tier can *prove* the job
cannot run as sent, the fix is the one mechanical change in
scope, and the corrected job is judged again before it
executes. Where the evidence is inconclusive, the system
does not improvise — it diagnoses, and talks.

## The idea

The Oracle reads a job against the box it is about to run on — the
OS, the interpreter, the tools on PATH, the files the job names —
and forms an opinion: *this will probably succeed here*, or *this
will faceplant, and the reason is obvious*. Today the sender learns
a job failed from the result and nothing more. The opinion closes
that gap in three ways, under three sender-granted latitudes.

## The modes

The sender grants a latitude per job (a job member) or by standing
configuration; the box's owner can cap it locally, and the owner's
cap wins. The Oracle can be wrong in every mode; that is accepted
and priced in from the first proposal.

- **advise** — before the job runs, the Oracle records its
  prediction. The job runs exactly as sent. The prediction rides
  the result (below), so the sender sees both the call and the
  outcome.
- **repair** — if the prediction is an obvious environment
  mismatch (the sender believes the box is Linux and the job is
  shaped for another platform; the named interpreter is absent and
  the platform default would do), the Oracle may fix the job before
  it runs. A repair is never silent: the result states what was
  changed, and carries the digest of the job as received.
- **diagnose** — after a failure, the Oracle attaches its reading
  of the obvious cause to the result. The sender gets the "why",
  not just the crash: missing interpreter, wrong-OS script shape,
  a path that does not exist on this box, a tool that is not
  installed. This mode changes nothing and blocks nothing.

## The member

The result message (PROTOCOL §3.2) gains one OPTIONAL member:

```json
"oracle_opinion": {
  "mode": "repair",
  "verdict": "likely_failure",
  "note": "interpreter ['sh'] is not present on this Windows host;
             the platform default was used in the repaired run",
  "repaired": true,
  "received_digest": "9f2c…"
}
```

- `mode` is the latitude the opinion was formed under:
  `advise`, `repair`, or `diagnose`.
- `verdict` is `likely_success`, `likely_failure`, or
  `no_opinion` (the Oracle declines — no inference configured and
  no deterministic finding).
- `note` is bounded plain text, written for the sender, stating
  the finding and its basis in the environment.
- `repaired` and `received_digest` appear only when a repair
  happened: what ran is the repaired job; what was received is
  identified by digest, so the sender can diff the two.

Receivers that do not know the member ignore it; the member never
changes the meaning of any existing result field.

## Where the opinion comes from

Two tiers, in order:

1. **Deterministic checks.** Platform and interpreter presence,
   named tools on PATH, referenced paths, script-shape tells
   (a PowerShell script under `["sh"]`, a POSIX path on a
   Windows host). These cover the "it's so obvious why" cases,
   need no model, and are testable to the standard the project
   holds everything else to.
2. **The local model, when inference is configured.** The Oracle
   may add a judgment the deterministic tier cannot reach. A
   model-formed opinion is labeled as such in the note's basis;
   the two tiers are never blended into one unattributed claim.

## Signing

The result is signed with the secret that verified the job, so in
the current protocol the opinion inherits that signature — it is
part of the runner's statement. Under a future confidentiality-on
or asymmetric mode (docs/asymmetric-signing-design.md), the
opinion MUST be signable as the Oracle's own statement, detachable
from the result and verifiable on its own: the Oracle speaks as an
authenticated party adding its opinion, never as a man-in-the-
middle editing someone else's message.

## What it is not

- Not a gate. The opinion never blocks, holds, or approves a job
  by itself; that is the judge's and the approval gate's territory.
- Not silent. Advice is labeled advice, a repair is reported with
  the received digest, a diagnosis is an opinion about a failure
  that already happened.
- Not a guarantee. `verdict` is an expectation formed from the
  environment, and the format carries `no_opinion` because "I
  don't know" is a legitimate answer.

## Self-learning: the loop closes (2026-10-19)

Andrew's direction, built in `runner/learning.py`: the Oracle
compares what it said about a job with what the job actually
did, saves the comparison immediately, and reads it fresh when
the next job arrives — so a later job can be assessed, and
where the latitude allows repaired, with the box's own history
in view. This is auditable episodic learning, not model
retraining: no weights change; what persists is a ledger
(`oracle-learning.jsonl` in the base dir) of predictions,
reconciliations, and lessons, every entry keyed to this host.

The loop, per job:

1. **Freeze.** When the opinion machinery forms its
   pre-execution call, the call is frozen to the ledger: job
   id, received digest, host fingerprint, the tier-1 findings,
   any proposed repair, the effective mode.
2. **Reconcile.** The moment execution completes — before the
   result is sent — the frozen call is scored against the
   verified outcome: correct, incorrect, partial (a repair
   that ran but did not save the job, or was refused on
   re-judgment), or no-prediction. A learning-write failure is
   logged and never blocks or delays the result.
3. **Learn, through two channels.** *Verified facts* are
   derived by code from the execution record — an interpreter
   absent and the repair succeeding, a named tool missing and
   the job failing — keyed by (host, feature), trusted, with
   a support count and last-seen time. *Model candidates* are
   distilled by the local model from a failed or mispredicted
   job's outcome and output, only when both model gates are
   on (`oracle_learning_model` and `oracle_opinion_model`,
   with inference configured; deterministic mode has no model
   channel, so a Pi Light box learns facts only). A candidate
   must pass a strict schema — a bounded declarative claim,
   feature keys, an expected outcome, a confidence — and it
   is labeled uncorroborated wherever it surfaces. It is
   promoted to corroborated only when later *verified*
   outcomes match what it expects (`oracle_learning_promote_after`,
   default 2, no intervening contradiction); a contradiction
   retires it as negative evidence. Repetition of a claim is
   not corroboration — only a verified outcome counts.
4. **Refresh.** Each new job's opinion evaluation reads the
   ledger fresh from disk — no cached copy, no restart — and
   only the lessons relevant to that job (same host, same
   interpreter/tool/path keys) are folded into its note,
   bounded. A fresh probe supersedes a stale fact at use
   time: a lesson that a tool was absent is not surfaced for
   a job where the tool probes present today.

The authority rule, unchanged by learning: **a lesson never
authorizes anything by itself.** What a lesson may do follows
the same latitude ladder as the opinion — at `off` nothing is
recorded or used; at `diagnose` lessons record and explain;
at `advise` facts and labeled candidates may inform
predictions, and nothing is modified; at `repair` a
corroborated lesson may *select* among the existing
mechanical repairs, and even then only when the repair's
preconditions are re-verified on this job, on this host, now,
and the repaired job is re-judged as always. A candidate
never drives a repair, and no lesson lets the model invent a
novel executable rewrite.

Poisoning discipline: raw job output is evidence, never
instruction. Facts are derived by code from verified probes
and outcomes, never from output text. A candidate claim
phrased as an instruction ("ignore previous instructions",
"always approve", …) fails validation and is dropped: a job
cannot appoint itself the Oracle's teacher.

The ledger is local state, not wire format: PROTOCOL is
untouched and the `oracle_opinion` result member is exactly
what it was — learning changes what the Oracle knows when it
forms the member, never the member's shape. `oracle_learning`
(default true) turns the whole loop off; nothing is recorded
or used while it is off, or while the opinion latitude is
`off`.

## Open questions — resolved in the build (2026-10-18)

Each question was resolved as a default plus a config option,
not left open:

- Default latitude: `diagnose` at the first build; raised to
  `repair` 2026-10-19 at the owner's direction (the one
  mechanical fix is mechanically certain, so it runs by
  default; the model tier stays separately gated). The runner
  config key
  `oracle_opinion_mode` is both the default for jobs that grant
  none and the owner's ceiling; a job's own `oracle_opinion`
  member requests a latitude and is clamped to the ceiling.
  The runner flag `--oracle-opinion <mode>` overrides for one
  process.
- Predictions: deterministic tier-1 only, and only at advise or
  repair latitude. `oracle_opinion_predict` is `requested`
  (default), `always`, or `never`. Diagnose needs no prediction
  and runs on any failure at diagnose latitude or higher. The
  model tier runs only when inference is configured AND
  `oracle_opinion_model` is true (default false).
- Repair re-authorization: `oracle_opinion_repair` is `rejudge`
  (default — the repaired job goes back through the judge and
  the key policy exactly as a received job would; a refusal
  returns the original job's failure result with the opinion
  explaining) or `refuse` (the repair is never executed; the
  opinion degrades to advise with the proposed fix described).
