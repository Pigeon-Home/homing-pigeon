# The v4 binding: the last 2 models, searched and held to the code

This record continues step C of the v4 work in `v4-working.md`,
after `v4-search.md`. The continued pass recorded there
wrote the models for P13, P10 and P12 (`secretfloor.tla`,
`probegate.tla` and `localgate.tla`) and named what stood
after it: the models for P8 and P11. This pass writes those
2, each one decision in the shape of `secretfloor.tla`, and
treats each the way the first models were treated: the
model's `Init` and `Next` written apart from the TLA+ file
in `runner/tests/test_v4_models.py` and searched to the
fixed point, then the real code driven over the decision's
whole space and read against the model. P9 is not a checker
claim and gets no model; its pin closes this record.

Models of P10 and of P12 were written in this pass and
withdrawn when the continued pass's models landed: each
property has the one model, and it is the landed one,
`probegate.tla` for P10 and `localgate.tla` for P12, both
recorded in `v4-search.md`.

Nothing here changes the runner. 1 finding is stated: F7,
at the result fitting's floor. It is closed since, in the
property's words, and marked where it stands below. (F6 is
the local gate's finding, stated in `v4-search.md`; this
pass's finding takes the next number so the 2 records do not
collide.)

## P8: the hybrid group selection, `hybridselect.tla`

The decision is the server core's, in
`runner/wire/dtlsproto.py`: the hybrid group (4588,
X25519MLKEM768, C29) is selected when the server core
carries the hybrid profile option and the ClientHello
offered a hybrid key share; otherwise X25519 (29), when
offered; a hello offering no group the profile can select
is refused. The profile option is the version 3 carriage
profile's; the version 1 profile leaves it off.

- The search: 8 initial states, 16 distinct states. The 4
  offer sets by the 2 profiles, and the decision is
  deterministic, so 8 decided states. `P8Inv` and
  `OnlyOffered` hold in every one of the 16. Both witness
  probes are false somewhere: a hybrid is selected, and a
  hello is refused.
- The conformance: the real client and server cores pumped
  through 4 handshakes, every combination of the client's
  offer and the server's profile. The negotiated group, on
  the client and on the server session alike, is the
  model's outcome on all 4: the hybrid only for the v3
  profile with the hybrid offered.
- These counts are the prediction for the checker, written
  before any run of it, as the first record's were.

The model's refused outcome is one this code's own client
never presents: it always offers the X25519 share, beside
the hybrid share or alone. A hello offering the hybrid
share alone, to a version 1 profile, is refused rather
than agreed, and the search caught an early statement of
`OnlyOffered` claiming otherwise; the invariant now says
refused exactly when no offered group is selectable. The
branch stands in the model because the server faces other
clients' hellos, and the code refuses them; the conformance
above covers the 4 combinations the code's own pair can
present.

## P11: the result fitting, `resultfit.tla`

The decision is `_fit_result_body` in `runner/runner.py`:
the body is built, and while it measures over the cap the
streams are cut to head and tail and the body rebuilt, 3
passes at most, the third keeping the first and last 2 KiB
of each stream; a cut is marked `result_truncated`. The
model stands the body's size in 3 classes against the cap:
fits, shrinkable, and fixed (over even at the third pass
shape).

- The search: 6 initial states, 12 distinct states. The 2
  cap classes by the 3 body classes, the decision
  deterministic. `MarkedWhenCut`, `CapZeroAsIs` and
  `FitsAsIs` hold in every one of the 12, and so does
  `P11Floor`, P11 as it is worded now, the cap down to the
  fitting's floor. The cap with no floor, the witness
  configuration's `P11Inv`, breaks at exactly 1 decided
  state: the fixed class under a set cap.
- The conformance: the real function over its classes. A
  cap of 0 leaves a 40,000 by 40,000 result untouched and
  unmarked; a body within its cap leaves as built; a
  shrinkable body is cut, marked, and fits. For that
  result the floor is 4,625 bytes: the smallest cap it
  fits under. At the floor the body fits, marked; 1 byte
  under it, and at 100 and at 1, the same body leaves at
  4,625 bytes, over the cap, marked.
- These counts are the prediction for the checker.

## Finding F7: a cap under the fitting's floor sends the body over it

P11 said the body that is signed and sent is at most
`max_result_bytes` whenever the cap is non-zero. Finding F7
is that the fitting cannot keep that word at a cap under
the size of its own last pass: the fixed envelope plus both
streams at their first and last 2 KiB. For the result above
that floor is 4,625 bytes, and a cap of 100 gets a body of
4,625 bytes, marked `result_truncated` with the reason
`max_result_bytes`. The marking is honest and the signature
covers what is sent; what fails is the cap itself. The
smallest change that closes it is the fitting refusing, or
the property's words gaining the floor. Neither was made in
this pass: the finding was stated, and held by a test as the
tree stood.

Closed, in the property's words. The choice between the 2
changes is about what the runner promises, and the owner
made it: the words gain the floor, and the runner is not
changed. P11 now says the body leaves within the cap down to
the fitting's floor, and that under a result's floor it
leaves at the floor, over the cap and marked: the runner
sends a marked result rather than none. `resultfit.tla`
states those words as `P11Floor`, in its main configuration,
and the search holds it in all 12 states. On the real
function, over 140 caps from 1 byte to past the floor, no
body is over both its cap and its floor, and each of the 126
under the floor leaves at 4,625 bytes, marked.

## P9: the framing scope, pinned by reading

P9 claims no session across the DTLS framing break of C30
is claimed as supported. It is a claim about what the
documents claim, so it is held by reading them, in
`runner/tests/test_v4_models.py`: the framing record
states that mixed-version DTLS interoperability is not
supported across the landing and that both ends must run
the same side of it; the support matrix claims no
mixed-version session; and the property stands stated in
`v4-properties.md`. A document landing that claims such a
session turns this pin red.
