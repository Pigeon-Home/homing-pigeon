# Stage 6 — more keys

Item 2 of the raise. The gate's policy step was one
boolean, `policyOk`. `KeysCompose.tla` opens it into three
keys.

- `owner` — no policy restriction. Any of the three shapes
  may run, once the rest of the gate has passed.
- `pinned` — one script shape, and nothing else. This is
  the upgrade key's arrangement, reduced to the shape the
  pin distinguishes. The fences are `KeyPolicy.tla`.
- `other` — a ping, or a script that is not the pinned
  one. Not the pinned script.

`otherOk` stands for the other eight clauses of P1. A
script runs only when those passed and this key's policy
allows the shape.

## What was checked

TLC 2.19 on Java 17. Eighteen attempts: three keys, three
shapes, the rest of the gate pass or not.

| Configuration | Invariant | Result | Generated | Distinct |
|---|---|---|---:|---:|
| The map | `KeysInv` | holds | 54 | 36 |
| A run exists | `NothingExecutes` | fails, as expected | 20 | 20 |
| The pin admits its script | `PinnedNever` | fails, as expected | 26 | 26 |

The first witness is a run, so the model is not the model
that refuses everything. The second is the pinned key
running its own script after the rest of the gate passed.
A pinned key with any other shape does not run, and
neither does a key whose other clauses failed.

This is the composition, not a second copy of the fence
logic. A misspelled policy field is still the finding in
`stage4-p4.md`. This model speaks about the policy the
runner holds, which is the built one.
