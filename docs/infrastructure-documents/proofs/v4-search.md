# The v4 binding: the first 4 models, searched and held to the code

This record continues step C of the v4 work in `v4-working.md`
and prepares step D. `diskguard.tla` states P7 of
`v4-properties.md`: the disk guard gives up the runner's own
material in a fixed order, records what it did, and never
stops the runner. The model was written and not yet checked.
This pass does the 3 things that need no checker, and the
suite now does them on every run:
`runner/tests/test_v4_models.py`.

The same pass then writes the 2 models `v4-working.md` names
as small steps, for P13, the secret floor, and for P10, the
confinement probe, and treats each the same way:
`secretfloor.tla` and `probegate.tla`, searched and held to
the code.

A later pass adds a fourth, for P12, the local envelope cap:
`localgate.tla`, treated the same way.

The passes recorded here changed nothing in the runner, and
stated 6 findings. A later change closes 2 of them in the
runner, F5 and F6, and each is marked where it stands below.

## The search

The model's `Init` and `Next` are written in the test apart
from the TLA+ file and searched to the fixed point, with the
path to every state kept so a counterexample would come with
its trace.

- 32 initial states, 160 distinct states, 64 of them finished
  passes. Over a combination of n classes with material, a
  running pass stands at any of n + 1 points with the disk
  over or under, and a finished one at any of those points
  with the disk under, or at the last with the disk still
  over: 3n + 4 states, summed over the 16 combinations.
- `NeverStops`, `OrderRespected` and `RecordedFaithfully` hold
  in every one of the 160.
- The model moves: a pass that gives up all 4 classes in
  order and records it is reached in 5 steps, a pass that
  stops at the first reading of under is reached, and a pass
  under the threshold acts on nothing and records nothing.

These counts are the prediction for the checker, written
before any run of it. A TLC run of `diskguard.cfg` that
reports another number of distinct states is a finding
against this record or against the model.

The model had no witness configurations. It has 2 now, each
expected to fail: `diskguardwitnessacts.cfg` (the probe
`NeverActs`) and `diskguardwitnessrecords.cfg` (the probe
`NeverRecords`). The 2 probes are added at the foot of
`diskguard.tla`, and nothing else in that file is changed.

## The conformance

The real `guard_disk` is run on a real state directory, with
the disk's readings scripted and every action traced. The
directory holds material in the classes under test, the
protected files beside it (the configuration, the seen
records, the security event log, the pending outbox), and 2
symlinks that lead outside it. The scripts are grown 1
reading at a time, each way, until the pass reads no further
than its script: that is every path the guard's own
re-measuring allows.

Over the 16 combinations of classes that is 1,516 passes in
all, 168 of them steady, where steady means the disk did not
fill up again on its own between 2 measurements with no
action between them. On every one of the 1,516:

- **P7 clause 1.** The pass returns. It raises nothing.
- **P7 clause 2.** Only paths in the 4 classes change, the
  classes are acted on in their order, and every action
  follows a reading of over.
- **P7 clause 3.** No protected file changes, neither symlink
  is removed or followed, and nothing outside the state
  directory changes.
- **P7 clause 4.** An event is returned exactly when the
  disk changed, it names exactly the paths that changed, and
  its `still_over` is the last reading.

And on a steady disk the code's finished passes are exactly
the model's: for each of the 16 combinations, the sets of
classes the code can end on are the prefixes of that
combination in order, all of them and no others.

## Findings

- **F1. The model ends a pass sooner than the code does.**
  Before an action the code measures at the head of a
  class's loop, and it measures again at the door of the next
  class. If the first reads under and the second reads over,
  the pass moves on to the later class with the earlier
  class's material still on the disk. The model ends the pass
  at the first reading of under. Of the 1,516 passes, 412 of
  them end outside the model's finished passes, and none of
  those is steady. Every one still keeps the order and
  follows a reading of over, so P7 as worded holds. The gap
  is in the model's reach: either the model gains the second
  measurement, or its header says it assumes a steady disk.
- **F2. Material of 0 bytes is removed with no record.** An
  action is noted in the event only when it freed bytes. A
  pass that removes only empty files or an empty workspace
  changes the disk and returns no event. P7 clause 4 says
  every pass that acts leaves 1 event. The smallest change
  that closes it is to note an action when the path is gone,
  whatever it freed.
- **F3. A reading that fails in the middle of a pass is taken
  as over.** A first reading that fails means no pass. A
  later one that fails does not end the pass: it goes on
  giving up material with no measurement that says the disk
  is full, through all 4 classes if every later reading
  fails too. P7 clause 2 says a later class is touched only
  while the disk still measures at or over the threshold.
- **F4. The model has no witnesses in its own files.** Closed
  in this pass by the 2 configurations named above.

F2 and F3 are differences between the code and P7's own
words, each held by a test as the tree stands today, so a
change on either side shows as a change to that test.

## The second model: the secret floor, P13

`secretfloor.tla` is one decision, in the shape of
`decision.tla`: a key map with a default key and 2 additional
keys, each absent, strong, or weak, and the start that
follows. The runner starts when nothing costs the start, and
a start that is refused names a key that cost it. 2
invariants: `P13Inv`, a runner that started holds its default
key and no weak key, and `NamesACause`, which is P6 clause 4
for this refusal. 2 witness configurations, each expected to
fail.

The search: 27 initial states, 67 distinct states. 4 key maps
start, and the other 23 are refused once for every key that
could be named, 36 refusals in all. Both invariants hold in
every state. These counts are the prediction for the checker,
as above.

The conformance: the real `build_secrets` in
`runner/wire/verify.py`, on every standing of the 3 keys and
every way of giving each present key, inline or from a file
of its own. That is 125 configurations, 18 of them start and
107 are refused, and the start is the model's on every one. A
key map that was built holds nothing under 128 estimated
bits.

P13 as written speaks of the shared secret. The code is
stronger than the words: the floor is applied to every key in
the map, the additional keys as much as the default, every
time the map is built. The model states it that way.

- **F5. A weak additional key was refused in the default
  key's name.** The refusal said `shared_secret is too weak`
  whichever key was weak. When only an additional key was
  weak, the error named a key that did not cost the start,
  and never named the one that did: 32 of the 107 refusals.
  The refusal itself was right, so P13 held. `NamesACause`
  did not hold of the code, and P6 clause 4 asks that the
  error name the setting. A relay on a chain holds its hop
  secrets as additional keys, so this was the error an
  operator setting up a relay would meet.

  Closed. `build_secrets` puts each additional secret
  through the floor under its own setting's name, and the
  refusal carries it: `additional_secrets['hop1'] is too
  weak`, or `additional_secrets_files['hop1']` for a key
  given from a file. The default key is named as before.
  `NamesACause` holds of the code on all 107 refusals.

## The third model: the probe gate, P10

`probegate.tla` is one decision again: a mode, a platform,
what stands in the place of that platform's confinement
backend (nothing, a stub that says it is not the backend, the
backend with no probe, the backend with its probe), and what
the probe answers (it passes, it names a problem, it raises).
The gate is `confinement_startup_problem` in
`runner/ops/remediation_ops.py`, asked by the startup, which
refuses the start with exit 2 when the gate names a problem.
2 invariants: `P10Inv`, a start at enforce on a platform with
a backend of its own means that backend stood there and its
probe passed, and `RefusesOnlyItsOwn`, the gate refuses
nothing below enforce and nothing on another platform. 2
witness configurations, each expected to fail.

The search: 144 initial states, 288 distinct states. 36
starts stand at the gate. 3 of them go ahead, 1 a platform,
and 33 are refused. Both invariants hold in every state.

The conformance: the real gate on all 144 starts, 33 of them
refused, and the gate's answer is the model's on every one.
The backend is stood in for through the gate's own injection
point. The probe is asked exactly once where the gate
decides and never anywhere else. A refusal names the
platform, and carries the probe's own words when the probe
spoke. A probe that raises costs the start, the same as a
probe that names a problem: there is no weaker run. The
startup's 3 calls to the gate, 1 a platform, and its exit 2
are held by a pin on `runner/ops/main.py`.

No finding against the code. 1 observation for the index:
P10 is written for macOS, and the gate makes the same claim,
by the same code, for FreeBSD and for Windows. The model
states all 3. The index states 1.

What the model does not reach: the probe itself. What the
trial process does on a real Mac is the backend's, and no
macOS host ran here. The model starts from the probe's
answer.

## The fourth model: the local gate, P12

`v4-working.md` names P12 as more than a small step, since
its path is the local-signals path. The cap itself is a gate
in front of that path, and the gate is what P12 states: 2
doors and 1 check. `localgate.tla` models that gate and stops
at the verifier.

It is one decision again. An arrival is its form (a file in
the inbox, a symlink there, a directory there, or a stream on
the loopback listener), its size, whether its bytes decode as
UTF-8 when read whole, and whether a cut at 1 byte past the
cap falls inside a character. The model's cap is 2 and its
chunk is 2, so the sizes 0 to 5 stand on both sides of every
comparison the 2 doors make. The doors are
`_scan_local_inbox` and `_handle_local_signal_conn` in
`runner/runner.py`, and the check behind both is
`_ingest_local_envelope_inner`. 4 invariants: `P12Inv`, what
reaches the verifier is at most the cap and is the whole
envelope, never the head of a longer one; `SymlinkUnread`,
nothing of a symlink's target is read; `ReadBounded`, the
scan reads at most 1 byte past the cap and the listener at
most 1 chunk past it; and `OverCapRefusedForSize`, an
envelope over the cap is refused for its size, whatever its
bytes are and wherever the cut falls. 2 witness
configurations, each expected to fail.

The search: 96 initial states, 200 distinct states. A stream
2 or more over the cap can stop on 2 totals, so 8 arrivals
decide 2 ways: 104 decisions, 8 of them at the verifier and
32 refused for size. All 4 invariants hold in every state.

The conformance: the real doors at the real cap of 262,144
bytes. 112 arrivals, 140 runs: 7 sizes from nothing to 1
byte more than a chunk over the cap, in each form, decoding
and cut, and every stream in 2 chunkings. The verifier is
stood in for, and the bytes read are counted at the door
itself. The gate's answer and its read are the model's on
every run. On the code:

- **Nothing over the cap reaches the verifier.** 48 runs of
  a file or a stream over the cap, none at the verifier. The
  12 runs that reach it carry the whole envelope. An
  envelope of exactly the cap goes through, and 1 byte more
  does not.
- **The read is bounded.** The scan opens a file once and
  reads the file or 1 byte past the cap, whichever is less.
  The listener's largest read is 327,680 bytes, the cap and
  1 chunk.
- **A symlink is refused unread.** Nothing is opened at the
  link, the target is as it was, the link is removed, and
  the refusal is logged. All 28, whatever the target's size.
- **Every refusal over the cap is recorded as its size**, 1
  line at WARN naming the door, on all 48 runs.
- **The comparison has teeth.** The same doors run with the
  cap 1 byte higher part from the model on 24 runs, every
  one of them over the true cap.

The reason recorded is where the code and P12's words parted
ways when the model was first held to the scan:

- **F6. A file cut inside a character was refused as not
  UTF-8.** The scan read 1 byte past the cap and decoded
  what it read before the size was checked. When the cut
  fell inside a character, the file was dropped as
  `envelope is not UTF-8`, though it was UTF-8 when read
  whole and its fault was its size. The same bytes at the
  listener were refused as too large. The refusal itself
  was right, so the safety P12 states held. The reason
  recorded was true of what was read and not of the
  envelope, and P12 says an over-cap envelope is rejected
  with the reason recorded.

  Closed. The scan looks at the size of what it read before
  it decodes anything, as the listener does, and says
  `envelope too large`. The model states the gate that way.
  The 3 files with a character astride the cut are refused
  for their size, and `OverCapRefusedForSize` holds of the
  model and of the code. P12's words name the ingest check.
  The scan now refuses first, and the ingest check stands
  behind both doors as before.

1 observation for the index. P12 gives the scan's bound, 1
byte past the cap. The listener's bound is 1 chunk past the
cap, 65,536 bytes, and P12 does not state it.

What the model does not reach: an envelope that is only
white space, the `local_signals` switch, and everything from
the verifier on.

## What stands

- **The checker run, step D.** Fetch the tools jar of the
  version the stage records name, run TLC on `diskguard.cfg`
  and the 2 witness configurations, and set its counts
  beside the prediction above.
- **The same run for `secretfloor.cfg`, `probegate.cfg` and
  `localgate.cfg`** and their witness configurations.
- **F1 to F3 stand.** F2 and F3 are differences between the
  disk guard and P7's words, and F1 is in the model's reach.
  F4, F5 and F6 are closed.
- **P8 and P11 have no model.** `v4-working.md` names each as
  more than a small step, and this record leaves them there.
