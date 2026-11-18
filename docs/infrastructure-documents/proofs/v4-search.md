# The v4 binding: the first model, searched and held to the code

This record continues step C of the v4 work in `v4-working.md`
and prepares step D. `diskguard.tla` states P7 of
`v4-properties.md`: the disk guard gives up the runner's own
material in a fixed order, records what it did, and never
stops the runner. The model was written and not yet checked.
This pass does the 3 things that need no checker, and the
suite now does them on every run:
`runner/tests/test_v4_models.py`.

The same pass then writes the model `v4-working.md` names
as a small step for P13, the secret floor, and treats it the
same way: `secretfloor.tla`, searched and held to the code.

Nothing here changes the runner. The 5 findings below are
stated, not fixed.

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

- **F5. A weak additional key is refused in the default
  key's name.** The refusal says `shared_secret is too weak`
  whichever key was weak. When only an additional key is
  weak, the error names a key that did not cost the start,
  and never names the one that did: 32 of the 107 refusals.
  The refusal itself is right, so P13 holds. `NamesACause`
  does not hold of the code, and P6 clause 4 asks that the
  error name the setting. A relay on a chain holds its hop
  secrets as additional keys, so this is the error an
  operator setting up a relay would meet. The smallest
  change that closes it is to hand the reader the setting's
  name with the secret.

## What stands

- **The checker run, step D.** Fetch the tools jar of the
  version the stage records name, run TLC on `diskguard.cfg`
  and the 2 witness configurations, and set its counts
  beside the prediction above.
- **The same run for `secretfloor.cfg`** and its 2 witness
  configurations.
- **F1 to F3 and F5 are for the seat that carries the runner
  and the models.** This pass changed no runner code.
- **The model for P10**, which `v4-working.md` names as a
  small step, is not begun here.
