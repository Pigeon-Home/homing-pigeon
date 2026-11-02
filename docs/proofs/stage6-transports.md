# Stage 6 — file and DTLS beside the mail path

Item 4 of the raise. `TransGate.tla` is already the
transport composition: every transport, the signature
outcome, and the credential outcome, against both
deployment postures. File and DTLS are in that space.
Pulling them into a second copy of the gate would
search the same composition twice.

This pass re-ran `TransGate.cfg` on TLC 2.19, Java 17,
rather than citing the stage 4 record alone.

| Configuration | Invariant | Result | Generated | Distinct |
|---|---|---|---:|---:|
| Full composition | `P3Inv`, `GateBlocks`, `PresentedExact`, `AcceptedExact` | holds | 240 | 160 |

The limits are the ones `stage4-p3.md` states, and they
are not removed by being re-run. File's gate is the
operating system's. DTLS's gate is the shared secret in
a second role, so the two gates fall together for
anyone who holds it. Neither fact changed.

## Verification

This record was re-checked first-hand after it landed, the
same standard stage 3 applied to stage 2: nothing in the
record above was taken on the author's word.

- **The check was re-run.** TLC 2.19 (the `v1.7.4` tools
  jar): the full composition holds at 240 generated, 160
  distinct, as the record says. The two witnesses the
  stage 4 record carries were re-run beside it:
  `BothGatesNeverEnough` fails at 109 / 109 and
  `NoGateNoAccept` at 89 / 89, matching `stage4-p3.md`
  exactly.
- **The code was re-read.** The composition the model
  stands on is unchanged on current main. The core is
  transport-blind (`_service_transports`,
  `service_channel`): an envelope is handled because a
  pipe put it in the channel. The NATS extension reads
  its waiver as `is True` and refuses to start
  credential-less otherwise. The DTLS pipe terminates
  with the shared secret as its PSK and refuses to start
  without one. The queues edge hash-compares the bearer
  token before anything is enqueued, with
  `REJECT_INVALID_HMAC` on by default. The file
  extension holds no credential at all, which is the
  operating-system gate the record names.
