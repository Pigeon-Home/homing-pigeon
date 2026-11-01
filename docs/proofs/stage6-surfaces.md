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
| An admitted job runs | `NothingRuns` | fails, as expected | — | — |
| An admitted cancel runs nothing | `CancelRuns` | fails, as expected | — | — |

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
