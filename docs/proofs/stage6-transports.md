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
