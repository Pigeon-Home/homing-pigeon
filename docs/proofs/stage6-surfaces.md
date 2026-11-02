# Stage 6 — the other doors

Item 3 of the raise. Five doors stand beside the job
door. Each already applies an early bound in the code,
and `Surfaces.tla` is that bound, not a second copy of
each door's own rules.

| Door | Code | What the model claims |
|---|---|---|
| job | `handle_mail` | A script runs only when the message was signed, encrypted, and the shared bounds passed |
| cancel | `handle_cancel_mail` | Same admit. No script |
| query | `handle_query_mail` | Same admit, then an answer. No script |
| board | `handle_board_mail` | Same admit, then a task message. No script |
| v2 | `handle_v2_mail` | The handler's own line: never a job. No script |
| local | `_ingest_local_envelope` | A same-box alert. Every kind but `sensor_alert` is refused, so no script. The signature is required. The mail encryption envelope is not, because this path does not use one |

`boundsOk` folds version, type, identity, freshness,
audience, and the door's key policy into one bit. Those
checks are the per-door code. The model checks the
composition the raise asks for: a script runs on exactly
one door, and only after the early bound.

## What was checked

TLC 2.19 on Java 17. Forty-eight attempts.

| Configuration | Invariant | Result | Generated | Distinct |
|---|---|---|---:|---:|
| Every door | `SurfacesInv` | holds | 144 | 96 |
| An admitted job runs | `NothingRuns` | fails, as expected | 56 | 56 |
| An admitted cancel runs nothing | `CancelRuns` | fails, as expected | 64 | 64 |

The cancel witness is the useful one. The cancel is
admitted, and it still does not run a script. A model
that refused every non-job door would also satisfy
"no script", and would say nothing about the door
accepting the message. The witness shows the accept.

## What this does not say

The board's own at-most-once is still the board's, as
P5 left it. A query's answer is not re-checked here.
Version 2's question and answer are not modelled past
"this door runs no script". The local path's refusal of
every kind but `sensor_alert` is a line in the code
(`runner/runner.py`, `_ingest_local_envelope_inner`)
and a bit in this model, not a replay of the sensor
filing rules.

## Verification

This record was re-checked first-hand after it landed, the
same standard stage 3 applied to stage 2: nothing in the
record above was taken on the author's word.

- **The check was re-run.** TLC 2.19 (the `v1.7.4` tools
  jar): `SurfacesInv` holds at 144 generated, 96 distinct,
  from 48 initial states — the forty-eight attempts the
  record counts. Both witnesses fail as the record says.
  Their counts, which the table above left blank, are 56
  generated / 56 distinct for the job witness and 64 / 64
  for the cancel witness; the two blank cells are filled
  from this run. A completion, not a correction: no number
  in the record was wrong.
- **The code was re-read.** `_early_dispatch`
  (`runner/runner.py`) offers each message to the cancel,
  query, board, and version 2 handlers before any job
  handling. Each handler runs the admit chain the model
  folds into `boundsOk` — `_admit_object` (the signature
  and the decryption), the cleartext refusal, audience
  (the version 2 door: its answerer list in place of
  audience), version, type, identity, freshness, and
  `check_door_policy` for that door — and none of the
  four reaches `execute_job`. The one `execute_job` call
  in `runner/ops/handlers.py` belongs to `run_variant`,
  an owner-invoked local command, not a message door. The
  local path (`_ingest_local_envelope_inner`) requires
  the signature, uses no mail encryption envelope,
  refuses every kind but `sensor_alert` on its face,
  applies the key policy, and files the alert. An
  admitted cancel kills the job or records the refusal
  and sends the ack — the cancel witness's point, in the
  code.
