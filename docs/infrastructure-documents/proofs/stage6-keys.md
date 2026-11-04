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

## Verification

This record was re-checked first-hand after it landed, the
same standard stage 3 applied to stage 2: nothing in the
record above was taken on the author's word.

- **The check was re-run.** TLC 2.19 (the `v1.7.4` tools
  jar) reproduced every number in the table above,
  exactly: the map holds at 54 generated, 36 distinct,
  from 18 initial states — the eighteen attempts the
  record counts; `NothingExecutes` fails at 20 / 20;
  `PinnedNever` fails at 26 / 26.
- **The code was re-read.** `check_key_policy`
  (`runner/wire/verify.py`) is the gate's policy step, and
  a job executes only when it returns no violation and
  every other clause of the gate has passed — the
  conjunction the model states, in the code's shape. The
  three keys are shapes of the built policy: a key with
  no entry is unrestricted, and the default key is the
  owner the record names; `allowed_script_sha384` pins
  one script by the digest of the job as received, for
  kind `exec`, with `script_url` refused beside it.
  `build_key_policies` copies only the fields it
  recognizes into the built policy, which is what the
  record means by speaking of the built policy — and is
  `stage4-p4.md`'s finding F1, confirmed again here.
- **One nuance the model folds away.** Two further layers
  can refuse before the per-key policy is consulted: the
  key directory's verdict, and `key_policies_default_deny`
  for an additional key with no entry. Both sit inside
  what the model calls the policy the runner holds, and
  both can only refuse — neither can admit a shape the
  map forbids — so the composition's claim is untouched.
  They are named here so the fold is on the record.
