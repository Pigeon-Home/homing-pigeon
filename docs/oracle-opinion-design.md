# Design: the Oracle's opinion, carried on the result

Status: design only. Not built, not scheduled. Andrew's proposal
(2026-10-15), elaborated 2026-10-18; recorded in FUTURE.md under
"Before a job runs". This document gives the idea its full shape so
the build, when it comes, starts from decisions rather than vibes.

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

The result message (PROTOCOL §13) gains one OPTIONAL member:

```json
"oracle_opinion": {
  "mode": "diagnose",
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

## Open questions

- The default latitude when the sender grants none: diagnose-only
  is the natural floor (it changes nothing and speaks only after
  a failure), but the default is a protocol decision, not an
  implementation detail.
- Whether `advise` predictions are computed for every job or only
  when the sender asks — the cost is one environment read per job
  for the deterministic tier, one model call for the second.
- How a repaired job is re-authorized: the repair changes what
  runs, so whether the judge sees the received job, the repaired
  job, or both is a security decision to make explicitly.
