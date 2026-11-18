# The v4 binding: working record

This file is the working record for the first item of
`docs/FUTURE.md`: a v4 that binds the listed, generalized
Homing Pigeon software constraints, based on protocol v1, v2
and v3, in a provable security model, with the proof work done
in the open on this shelf. `docs/FUTURE.md` is the owner's
file; this work is based on it and does not change it.

The pass recorded here covers three steps of the plan:

- **Step A.** Harvest the constraint inventory at the current
  head: every constraint the current drafts and the code state.
- **Step B.** State each harvested constraint as a numbered
  property beside P1 to P6. The statements live in
  `v4-properties.md`, in this directory.
- **Step C, begun.** Extend the TLA models toward the new
  properties where the existing model structure makes it a
  small, safe step; where it is not small, record precisely
  what remains.

The branch head this pass starts from is the main head of
2026-11-18, the release commit of 3.17.29.3. The existing
inventory, `constraints.md`, was harvested at `6d6288c5`; the
first question of this pass is what of it still stands at the
new head, and what the code and the drafts have stated since
that the inventory does not carry.

## Supposition, written before the measurement

The following are predictions, written down before any
measurement in this pass was run. The conclusions section
below records what the measurements found, against each one.

- **S1.** Every value in the `constraints.md` summary table
  (C1 to C27) still matches the code at this head, because
  `runner/tests/test_proof_constraints.py` pins the harvested
  values against the code and the suite stands green at this
  head. If S1 holds, step A re-states the inventory at the new
  head without changing a value.
- **S2.** The code at this head states at least one security
  constraint family that `constraints.md` does not carry: the
  disk self-protection guard landed after the harvest (the
  90 percent truncation guard in `runner/oracle/resources.py`),
  with named constants and an opt-out key, none of which
  appear in C1 to C27.
- **S3.** The drafts and their records state at least two
  constraints the inventory does not carry: the v3 hybrid key
  agreement group, and the ratified rule that both ends of a
  DTLS session run the same side of the record framing.
- **S4.** The disk guard is a safe first model extension: it
  is one function, driven by one threshold, acting on an
  ordered list of its own material classes, with no path that
  stops the runner. A small TLA model of that decision should
  be writable without touching the existing models.

Suppositions only. No conclusions yet.

## The harvest, step A: the standing inventory

The standing inventory is C1 to C27 in `constraints.md`. Each
entry there names the exact value, the declaring file and
function, and the refuse-or-default class. The summary, as
that file records it:

| ID | Constraint | Default or value |
|----|------------|------------------|
| C1 | `max_job_bytes` | 4194304 |
| C2 | `max_script_bytes` | 1048576, UTF-8 bytes |
| C3 | `max_result_bytes` | 5242880; 0 is unlimited |
| C4 | `_LOCAL_ENVELOPE_MAX_BYTES` | 262144, constant |
| C5 | Signature | HMAC-SHA-384, `compare_digest` |
| C6 | Secret entropy floor | 128 bits estimated |
| C7 | Key fingerprint | `k-` plus 8 hex of SHA-384(label + secret) |
| C8 | Cleartext | refused; `--allow-cleartext` only |
| C9 | AEAD | AES-256-GCM, `aes-256-gcm/hkdf-sha384` |
| C10 | Audience | configured `runner_id`; `aud` wins |
| C11 | Seven security modes | each `enforce` by default |
| C12 | `max_job_age_sec` | 3600; future bound 300 |
| C13 | Protocol version | integer 1 only |
| C14 | Key policies | per-key; script pin is SHA-384 |
| C15 | Execution semantics | at most once; delivery at least once |
| C16 | Transport credentials | required where a transport has them |
| C17 | Result-policy ceiling | views attested < summary < redacted < full; budgets default 8 and 8, effective is the min |
| C18 | Sandbox shape | fixed flags; work mount `/work`; interpreter prefix bound read-only |
| C19 | Queues edge gates | SI bearer, then edge HMAC while `REJECT_INVALID_HMAC` is on (default on) |
| C20 | Transport gate postures | email none; file OS-held; NATS required, waiver is literal `true`; DTLS no waiver; queues unconditional |
| C21 | Key directory precedence | verdict before policy, at every door |
| C22 | Upgrade key arrangement | kinds `["exec"]`; one pinned digest; `max_timeout_sec` 300 |
| C23 | Replay-cache keep horizon | `max(max_job_age_sec + 300, 86400)` sec; `SEEN_CAP` 200,000 |
| C24 | Claim stale rule | live holder never stolen; dead at once; unreadable at 86,400 sec |
| C25 | Record retention and delivery window | sent ages at `output_retention_days` (7; 0 never); stash given up at 86,400 sec, backoff 60 |
| C26 | Default-class reader | unusable reads as the documented default and is named |
| C27 | Refuse class at startup | exit 2, the error names the key; not in the live-reload set |

Whether each of these still matches the code at this head is
the measurement S1 predicts. The conclusions section records
the result.

## Conclusions, against the suppositions

Measured at this branch's head, after the suppositions above
were committed.

- **S1 held.** `runner/tests/test_proof_constraints.py` runs
  68 tests at this head and all pass: every value in the
  C1 to C27 summary still matches the code. Step A therefore
  re-states the standing inventory at the new head with no
  value changed.
- **S2 held, and wider than predicted.** The disk guard is
  there as predicted (C28 in `v4-properties.md`), and the
  harvest found a second post-harvest family beside it: the
  macOS confinement backend's fail-closed startup rule (C31).
- **S3 held.** Both draft-side constraints are there: the v3
  hybrid key agreement group (C29) and the ratified same-side
  framing rule (C30).
- **S4 held in part.** The model of the guard's decision,
  `diskguard.tla` with `diskguard.cfg`, is written: one pass,
  the four classes in their order, the re-measurement after
  every action stated as a nondeterministic flag, and the
  three invariants P7 names (NeverStops, OrderRespected,
  RecordedFaithfully). It touches no existing model. It is
  NOT yet checked: TLC is not installed on this machine, so
  no verdict is claimed for it. Running the checker is step
  D of the plan, and the model's verdict belongs there.

One finding the suppositions did not predict: three standing
constraints were stated by no property at all. A citation
count over `properties.md` finds C3, C4 and C6 mentioned zero
times there. All three are real in the code at this head (the
result cap's fit-before-signing step, the local envelope cap,
the secret entropy floor's raise under 128 bits). Step B
states them as P11, P12 and P13 in `v4-properties.md`, so the
v4 binding index now covers every harvested constraint:
C1 to C31, each with a numbered property.

The pins for the new claims are
`runner/tests/test_v4_binding.py`: 21 tests, all passing at
this head, beside the 68 of `test_proof_constraints.py` and
the 25 of `test_disk_guard.py`.

## What of step C remains

- **The checker run for `diskguard.tla`.** Install tla2tools
  by the bare-machine rule, run TLC against `diskguard.cfg`,
  and record the verdict, the state count, and any
  counterexample in a stage record. That is step D's first
  item, and until it runs, P7 is a stated property with a
  written model and conformance pins, not a checked one.
- **Models for P8 to P13 do not exist yet.** Per property:
  P8 is a handshake negotiation claim inside the DTLS stack;
  a model belongs with the DTLS records' own extension, not
  a small step. P9 is a support-scope claim, held by its
  record and a doc pin; it is not a checker claim. P10 is a
  startup probe claim and a candidate for a small model in
  the shape of `decision.tla` (probe outcome by mode), not
  begun. P11's seam is the result path, which no current
  model covers; not small. P12's path is the local-signals
  path, named in `properties.md` as a later stage's scope;
  not small. P13 sits in P6's family: `decision.tla`'s
  attempt classes could carry the secret floor as one more
  refuse-class attempt, a small extension, not begun.
- **The inventory merge.** C28 to C31 are stated in
  `v4-properties.md` in this pass so the branch's claims sit
  in one reviewable place. Folding them into
  `constraints.md` itself, in that file's own format, belongs
  with the step D pass, so the inventory of record stays one
  file in the end.

## Step C, continued

Later work took up 4 of the items above. Its record is
`v4-search.md`, and its checking runs with the suite as
`runner/tests/test_v4_models.py`.

- **`diskguard.tla` is searched, and has its witnesses.** The
  model's states are counted without a checker, as the
  prediction for the TLC run, and the real guard is driven
  down every path its re-measuring allows. 2 witness
  configurations are added. The checker run itself still
  stands.
- **P13 has its model**, `secretfloor.tla`, as its own small
  file in the shape of `decision.tla`, with `decision.tla`
  left as it was checked.
- **P10 has its model**, `probegate.tla`, stated for the 3
  platforms the one gate serves.
- **P12 has its model**, `localgate.tla`: the cap's own gate,
  the 2 doors and the 1 check in front of the local-signals
  path, with that path left outside it.

That record names 6 findings, F1 to F6, none of them fixed
there. What stands after it: the checker runs for all 4
models, the models for P8 and P11, and the inventory merge.

## Steps C and D, the finishing pass: suppositions

The following are predictions for the pass that finishes
step C and runs step D, written down before any measurement
in this pass was run. The conclusions belong below them when
the pass closes.

- **U1.** Each of P8, P10, P11 and P12 admits a one-decision
  model in the shape of `secretfloor.tla`, and each model's
  twin in the suite, searched to the fixed point, holds the
  property's invariant in every reachable state, with both
  witness probes reachable: each witness invariant fails on
  some state the search reaches. P9 admits no model, because
  it is a claim about what the documents and the support
  matrix claim, and its completion is a pin: a search of the
  support matrix and the DTLS records that finds no claim of
  a supported session across the framing break.
- **U2.** `_fit_result_body` fits every result whose cap is
  at or over the floor the third pass leaves: the body with
  both streams cut to their first and last 2 KiB, plus the
  fixed envelope around them. At a cap under that floor it
  returns a body still over the cap, marked
  `result_truncated`: a counterexample to P11's unqualified
  words at the boundary, to be recorded as a finding and
  held by a test, not fixed in this pass.
- **U3.** TLC 2.19 (the v1.7.4 tools jar) on Java 21 reports
  exactly 160 distinct states for `diskguard.cfg` and
  exactly 67 for `secretfloor.cfg`, the suite search's
  predictions in `v4-search.md`, and no error on either main
  configuration. Every standing main configuration (the
  claim, confine, decision, gate, keypolicy, keyscompose,
  replay, surfaces and transgate families) reports no error,
  and every witness configuration reports the violation it
  exists to produce.
- **U4.** TLC's distinct-state counts for the 4 new models
  equal their suite searches' counts. The searches run
  first; their counts are recorded in the step C record
  before any TLC run of the new models.
- **U5.** Folding C28 to C31 into `constraints.md`, in that
  file's own format and with no value changed, leaves the
  constraint pin suite green without an edit to it: its 68
  tests pin C1 to C27, and the fold adds entries without
  moving one.

A note on the parallel landings: this pass ran beside the
continued step C pass recorded above, and the records met
twice. P10 was landed there, as `probegate.tla`, and P12
was landed there, as `localgate.tla`, so U1 and U4 above
read on the 2 models this pass still owed, P8 and P11.
Models of P10 and of P12 were written here and withdrawn
in the landed models' favour: each property has the one
model, and it is the landed one. The continued pass's
finding F6 is the local gate's; this pass's fitting
finding is F7, so the numbers do not collide. U3's checker
prediction extends to `probegate.cfg` at its search's
count, 288 distinct states, and to `localgate.cfg` at its
search's count, 200.

## Step D: the checker run

Run 2026-11-18 with TLC 2.19 (the v1.7.4 tools jar) on
Java 21, over every configuration on this shelf: 45 in all,
17 main configurations and 28 witness configurations. The
run was made on scratch copies of the shelf: the file names
here are lowercase and the module names capitalized, and on
a case-sensitive filesystem the checker wants the 2 to
match, so each model was copied to its module's name for
the run. Nothing on the shelf changed for the run.

Every main configuration reports no error. Every witness
configuration reports the violation it exists to produce,
of the invariant it names. The verdicts, with the distinct
states the checker found:

- Claim: `claim.cfg` passes, 5 states.
- Confine (P2): `confineceiling.cfg` passes, 584,167
  states. The witnesses violate: `confinewitnessnarrow.cfg`
  (NothingNarrows), `confinewitnessprefix.cfg`
  (NoPrefixBind).
- Decision (P6): `decision.cfg` passes, 24 states. The
  witnesses violate: `decisionwitnessdefault.cfg`
  (DefaultStaysUnusable), `decisionwitnessstop.cfg`
  (NothingStops).
- DiskGuard (P7): `diskguard.cfg` passes, 160 states. The
  witnesses violate: `diskguardwitnessacts.cfg`
  (NeverActs), `diskguardwitnessrecords.cfg`
  (NeverRecords).
- Gate (P1): `gateaudit.cfg` passes, 809,528 states;
  `gatedefault.cfg` passes, 794,755; `gateenforce.cfg`
  passes, 804,611. The witnesses violate:
  `gatedefaultwitness.cfg` (AudienceWasRequired),
  `gatewitness.cfg` (NothingExecutes).
- HybridSelect (P8): `hybridselect.cfg` passes, 16 states.
  The witnesses violate: `hybridselectwitnesshybrid.cfg`
  (NothingSelectsHybrid), `hybridselectwitnessrefused.cfg`
  (NothingIsRefused).
- KeyPolicy (P4): `keypolicy.cfg` passes, 42,793 states.
  The witnesses violate: `keywitnessdefault.cfg`
  (DefaultNeverRuns), `keywitnesspinned.cfg`
  (PinnedNeverAccepted).
- KeysCompose (P1 with P4): `keyscompose.cfg` passes, 36
  states. The witnesses violate: `keyswitnessexec.cfg`
  (NothingExecutes), `keyswitnesspinned.cfg` (PinnedNever).
- LocalGate (P12): `localgate.cfg` passes, 200 states. The
  witnesses violate: `localgatewitnesssize.cfg`
  (NothingIsRefusedForSize),
  `localgatewitnessverifies.cfg`
  (NothingReachesTheVerifier).
- ProbeGate (P10): `probegate.cfg` passes, 288 states. The
  witnesses violate: `probegatewitnessrefused.cfg`
  (NothingIsRefused), `probegatewitnessstarts.cfg`
  (NothingStartsAtEnforce).
- Replay (P5): `replay.cfg` passes, 1,792 states. The
  witnesses violate: `replaywitnessexec.cfg`
  (NothingExecutes), `replaywitnessresend.cfg`
  (NeverAnswered).
- ResultFit (P11): `resultfit.cfg` passes, 12 states.
  `resultfitwitnessshrunk.cfg` violates NothingIsShrunk,
  as designed. `resultfitwitnesscap.cfg` violates P11Inv:
  that violation is finding F7's counterexample, produced
  by the checker at exactly the fixed class, as the search
  predicted.
- SecretFloor (P13): `secretfloor.cfg` passes, 67 states.
  The witnesses violate: `secretfloorwitnessrefused.cfg`
  (NothingIsRefused), `secretfloorwitnessstarts.cfg`
  (NothingStarts).
- Surfaces (P1 family): `surfaces.cfg` passes, 96 states.
  The witnesses violate: `surfaceswitnesscancel.cfg`
  (CancelRuns), `surfaceswitnessjob.cfg` (NothingRuns).
- TransGate (P3): `transgate.cfg` passes, 160 states. The
  witnesses violate: `transwitnessboth.cfg`
  (BothGatesNeverEnough), `transwitnessnogate.cfg`
  (NoGateNoAccept).

The suppositions of the finishing pass, against the
measurements:

- **U1 holds.** Each of P8 and P11 admitted its
  one-decision model; the suite twins hold their invariants
  in every reachable state and both witness probes are
  reachable in each. P10's and P12's models are the
  continued pass's `probegate.tla` and `localgate.tla`.
  P9 completed as a pin.
- **U2 holds.** The fitting's floor for the measured
  result is 4,625 bytes; at a cap under it the body leaves
  at 4,625 bytes, over the cap, marked. Recorded as
  finding F7 in `v4-search-2.md` and held by a test.
- **U3 holds.** The checker reports exactly 160 distinct
  states for `diskguard.cfg` and exactly 67 for
  `secretfloor.cfg`, the searches' predictions; exactly
  288 for `probegate.cfg` and exactly 200 for
  `localgate.cfg`, their searches' predictions; no error
  on any main configuration; and every witness
  configuration reports its violation.
- **U4 holds.** The checker's counts for the 2 new models
  equal their searches': 16 and 12 distinct states.
- **U5 holds.** C28 to C31 stand folded into
  `constraints.md` in its own format, and the constraint
  pin suite is green unedited, 68 tests.

2 models are not in this run's count: the P10 and P12
models this pass wrote and withdrew in the landed models'
favour. Their files never landed here; the scratch runs of
them agreed with their searches, and they are recorded as
withdrawn, not as second models of their properties.

## The finishing pass, closed (18 November 2026)

The conductor directed the 2 future branches finished in
the early hours of 18 November, this branch first in his
attention. What stands on this branch now, in one place:

- **Step A.** The constraint inventory stands at C1 to
  C31, harvested from the code at the head it describes;
  C28 to C31 were folded into `constraints.md` in this
  pass, in its own format, the pin suite green unedited.
- **Step B.** Properties P7 to P13 each stand stated
  beside the constraint that grounds them.
- **Step C.** 6 models stand: the disk guard (P7), the
  secret floor (P13), the probe gate (P10), the local
  gate (P12), and the 2 models this pass added for P8
  and P11 in the shape of the secret floor. 2 further
  models written in this pass were withdrawn in the
  landed models' favour and are recorded as withdrawn
  above, not as second models of their properties.
- **Step D.** The checker has been run over every
  configuration: the state counts match the searches'
  predictions exactly (160, 67, 288, 200, and 16 and 12
  for the 2 new models), no error on any main
  configuration, and every witness configuration reports
  its violation.
- **Step E.** The named values the draft relies on are
  pinned by tests, so the text and the code cannot drift
  apart quietly.
- **Step F.** The findings stand stated, not hidden:
  F1 to F3 against the disk guard model and code, F5
  against the secret floor's refusal naming, F6 against
  the local gate's refusal naming, and F7, the fitting's
  floor, recorded in `v4-search-2.md` and held by a test.
  F4 stands closed. None of F1 to F3 or F5 to F7 is fixed
  in this branch; each is written down where the next
  pass will find it.
- **Step G.** The v4 draft stands written and brought
  to idnits zero, ready to post. Posting stays the
  conductor's own hand, as with v1 to v3; nothing was
  submitted from this branch.

For Claude, in ComChat form: Claude, your step C passes
carried this branch most of the way. The disk guard
search, the secret floor, the probe gate and the local
gate models are yours, and the findings you stated
plainly are the reason the finishing pass could close.
The finishing pass added the P8 and P11 models, folded
C28 to C31, ran the checker over every configuration,
and pinned the draft's named values. What is left is
the findings, F1 to F3 and F5 to F7, stated above; they
are the next work on this branch, and the draft waits
on DRU to post it.

## The conversation behind the branch, and where it stands (18 November 2026)

DRU's framing for this work, in his terms: legitimately
lock down the constraints on the software suite, then
prove to the IETF that the running software is secure.
The computational power budget for the proofs is part
of the design thinking, not an afterthought. Items 1
and 2 of docs/FUTURE.md are the near term focus for the
next day or two, and this branch is item 1.

The finishing pass is complete. Steps A to G were done
on this branch tonight, in order, and the pass opened
with its supposition written before any measuring, in
the section above.

All 7 properties, P7 to P13, stand modelled, searched,
and held to the shipped code. The last 2 models, for
P8 and P11, landed in the finishing pass, and the
hybridselect twin correction landed with them: the twin
now states OnlyOffered as the model does. Constraints
C28 to C31 were folded into the inventory in the same
pass, and the inventory stands whole at C1 to C31.

Step D stands recorded above: the checker run over
every configuration, with the state counts matching
the searches.

The findings F1 to F6 stand stated in the search
record, open and not fixed. Fixing them is later
work, for a pass of its own.

The v4 draft stands written with its named values
pinned, steps E and G, and idnits clean per the
finishing pass record. It is not submitted. DRU posts
drafts himself.

This branch stands as the deliverable. It is not
merged, and no release is cut from it.

## Findings F5 and F6, closed

The work after the finishing pass took up the findings as
that pass left them. 2 of them are closed in the runner, and
each is marked in `v4-search.md` where it was stated:

- **F5.** A weak additional key is refused under its own
  setting's name. `NamesACause` holds of the real
  `build_secrets` on all 107 refusals.
- **F6.** The inbox scan looks at the size of what it read
  before it decodes anything, and a file over the cap is
  refused as too large wherever its cut falls.
  `localgate.tla` states the gate that way, and
  `OverCapRefusedForSize` takes the place of
  `OverCapRefused`.

`localgate.tla` changed after step D's checker run. The
suite's search of the changed model counts 96 initial states
and 200 distinct states, as it did before the change, and
that count is the prediction: the 3 `localgate`
configurations want the checker again. Every other verdict
of step D stands, since no other model changed.

The v4 draft states F5 and F6 as they stood when it was
written. Its findings section, and the 2 property sections
that cite them, want those 2 entries brought to the closed
state, and the renders made again, before the draft is
posted. Nothing in the draft's folder is changed here.

F1 to F3 and F7 stand open.

## Findings F1, F2 and F3, closed

The 3 findings on the disk guard are closed, and each is
marked in `v4-search.md` where it was stated:

- **F2.** The guard notes a removal when the path is gone,
  whatever it freed, and a workspace removed part way with
  what that freed. An event names exactly what a pass
  removed.
- **F3.** A measurement that fails ends the pass. Nothing is
  given up without a measurement that says the disk is at or
  over the threshold.
- **F1.** `diskguard.tla` measures as the code does, before
  every action and again at the door of every class, with
  every measurement free to come out over, under, or not at
  all. All 1,516 passes the real guard can make end on one
  of the model's finished passes. A third witness
  configuration, `diskguardwitnessrefill.cfg`, shows the
  model reaches a disk that fills up again.

`diskguard.tla` changed after step D's checker run. The
suite's search of the changed model counts 48 initial states
and 1,086 distinct states, 405 of them finished passes, and
that count is the prediction: `diskguard.cfg` and its 3
witness configurations want the checker again. The 160 the
checker found is the count of the model as it stood then.

The v4 draft states F1, F2 and F3 as they stood when it was
written, as it does F5 and F6. Nothing in the draft's folder
is changed here.

F7 stands open.

## F7, as it stands

F7 does not close the way F1 to F6 did. `resultfit.tla` and
`_fit_result_body` already agree: the fixed class leaves over
the cap, marked. What differs is P11's own words, and 2
changes bring them together:

- **The words gain the floor.** P11 holds down to the
  fitting's last pass, and under that floor it says the body
  leaves marked. Nothing in the runner changes.
- **The runner holds a hard cap.** A result that cannot be
  fitted is not sent. P11 stands as worded, and a sender
  whose result cannot fit receives nothing.

The choice is about what the runner promises, and it is the
owner's. Until it is made, F7 stands as `v4-search-2.md`
states it, held by its test.

## F7, decided (18 November 2026)

DRU has decided F7: the words gain the floor. P11 holds
down to the fitting's last pass, and under that floor the
body leaves marked; nothing in the runner changes, and a
marked result over the cap stands. The decision is
recorded in the seats' forum, in Muse's entry of
18 November 2026. The wording change is Claude's to land;
until it lands, F7 stands decided and not yet closed.

## F7, closed in the property's words

The owner chose the first of the 2 changes: the words gain
the floor, and the runner is not changed.

- **P11's words.** `v4-properties.md` now says a result body
  leaves within `max_result_bytes` down to the fitting's
  floor, the result as the fitting's last pass leaves it,
  and that under a result's floor the body leaves at the
  floor, over the cap and marked. A counterexample is a body
  over both its cap and its floor, or an over-cap body sent
  unmarked.
- **The model.** `resultfit.tla` states those words as
  `P11Floor`, and `resultfit.cfg` carries it as a fourth
  invariant. `Init` and `Next` are as they were, so the
  search still counts 6 initial states and 12 distinct
  states, and `P11Floor` holds in all 12. `P11Inv`, the cap
  with no floor, stays the witness's probe and still fails
  at the fixed class: that class is what the floor is for.
- **The code.** Over 140 caps from 1 byte to past the floor,
  no body of the real fitting is over both its cap and its
  floor.

`resultfit.cfg` gained an invariant after step D's checker
run, so it wants the checker again, with its 2 witness
configurations, against the same 12 distinct states.

The v4 draft states P11 as it was worded before, and F7 as
open. Its P11 section, its findings section and its security
considerations want bringing to these words before it is
posted. Nothing in the draft's folder is changed here.

With this, no finding of the v4 search stands open: F1 to F7
are closed, F2, F3, F5 and F6 in the runner, F1 and F4 in
the model and its files, and F7 in the property's words.

## The checker again, on the 3 changed models

Run 2026-11-18 with TLC 2.19 (the v1.7.4 tools jar) on
Java 21, over the 10 configurations that wanted the checker
again: the 3 main configurations whose models or
invariants changed after step D's run, and their 7 witness
configurations. The run was made on scratch copies of the
shelf, each model copied to its module's name, as step D's
run was. Nothing on the shelf changed for the run.

Every main configuration reports no error, and each
reports the distinct state count its record predicted.
Every witness configuration reports the violation it
exists to produce, of the invariant it names:

- DiskGuard (P7): `diskguard.cfg` passes, 1,086 states,
  the count the F1 record predicted. The witnesses
  violate: `diskguardwitnessacts.cfg` (NeverActs),
  `diskguardwitnessrecords.cfg` (NeverRecords),
  `diskguardwitnessrefill.cfg` (NeverLeavesMaterial).
- LocalGate (P12): `localgate.cfg` passes, 200 states,
  the count the F6 record predicted. The witnesses
  violate: `localgatewitnesssize.cfg`
  (NothingIsRefusedForSize),
  `localgatewitnessverifies.cfg`
  (NothingReachesTheVerifier).
- ResultFit (P11): `resultfit.cfg` passes, 12 states,
  with `P11Floor` among its invariants, holding in all 12,
  as the F7 record predicted. The witnesses violate:
  `resultfitwitnessshrunk.cfg` (NothingIsShrunk), as
  designed, and `resultfitwitnesscap.cfg` (P11Inv): the
  cap with no floor still fails at the fixed class, the
  class the floor is for.

With this run the 3 models that changed after step D stand
checked at their changed shapes, and no configuration of
theirs wants the checker again.

## The checker a second time, from the other seat

Run 2026-11-18 with TLC 2.19 of 08 August 2024, the v1.7.4
tools jar at revision 5a47802, on OpenJDK 21: a second run,
made apart from the one above, in the other seat's
container. It covers every configuration of the 6 models of
P7, P8 and P10 to P13, 19 in all: 6 main configurations and
13 witness configurations. Each model was copied to its
module's name in a scratch folder for the run, as before.

Every main configuration reports no error, with the count
its search predicted and the first run found:

- `diskguard.cfg`: 48 initial states, 1,086 distinct states.
- `localgate.cfg`: 96 initial states, 200 distinct states.
- `resultfit.cfg`: 6 initial states, 12 distinct states,
  `P11Floor` among its 4 invariants.
- `secretfloor.cfg`: 27 initial states, 67 distinct states.
- `probegate.cfg`: 144 initial states, 288 distinct states.
- `hybridselect.cfg`: 8 initial states, 16 distinct states.

Every witness configuration reports the violation of the
invariant it names: NeverActs, NeverRecords and
NeverLeavesMaterial for the disk guard;
NothingReachesTheVerifier and NothingIsRefusedForSize for
the local gate; P11Inv and NothingIsShrunk for the result
fitting; NothingStarts and NothingIsRefused for the secret
floor; NothingStartsAtEnforce and NothingIsRefused for the
probe gate; NothingSelectsHybrid and NothingIsRefused for
the hybrid selection.

2 of the counterexamples, as the checker printed them:

- `diskguardwitnessrefill.cfg`: classes 1 and 2 have
  material. The first reading is over, the reading at class
  1 is under and the pass leaves it, the reading at class
  2's door is over and the pass acts on class 2. That is
  the pass of finding F1.
- `resultfitwitnesscap.cfg`: the cap is set and the body is
  in the fixed class. It leaves over the cap, marked. That
  is the class P11's floor is for.

The 3 changed models make 3 main and 7 witness
configurations, 10 in all.

The 6 model files now say in their headers that the checker
ran, where 5 of them said it had not. This run was repeated
on the files as they stand after that change, with the same
verdicts and counts.

What the draft still wants, read after its last revision:
its P7 section gives the disk guard model 160 distinct
states, the count of the model before F1 was closed, and
`runner/tests/test_v4_draft.py` pins that number there. The
model as it stands has 1,086. And the 5 points of the
reading in the seats' forum stand. Nothing in the draft's
folder is changed here.
