# Stage 4, fifth property — P6, checked

This is the record of P6's pass through stage 4's cycle: the
full statement, the model, the check, and what the check does
not say. P6 is the last of stage 4's five properties. The
statement is in `properties.md` (P6, seven clauses); the
constraints it uses are C26 and C27 in `constraints.md`,
harvested from the code for this stage; the model is
`Decision.tla` in this directory.

The code read for this stage is the code at the `testing`
branch tip this stage started from. The runner files named
below are unchanged from `6d6288c5`.

## The property, in one paragraph

A setting the owner wrote, which is present and not usable,
does one of two things, and which one depends on what a wrong
value would change. If it would change who can reach the box,
what the box will execute, or what it protects, the runner
does not start, and the error names the setting. Everything
else reads as its documented default, and the startup warning
names the key. An absent key is the default too, and is not
named: the owner wrote nothing unusable. While the process is
running, a bad default-class value becomes the documented
default and is named, with no hidden last-good value. A
refuse-class key is not in the live-reload set at all, so a
later write does not change the running binding and does not
stop the process. It is read again at the next start.

## Where the split is performed — the code sites

**Usable, for a number.** `runner/guard/confval.py`,
`is_number` (line 40) and `number` (line 78). A boolean is
never a number, because `bool` is an `int` in Python and
`int(True)` is 1. A non-finite float is not a number. A value
outside `[lo, hi]` is unusable, not clamped. `integer`
(line 94) is that result toward zero. `port` (line 102) is an
integer in `1..65535`; port 0 is unusable. `choice`
(line 112) is an exact string match.

**Named, for the default class.** `runner/guard/defaulted.py`.
`NUMERIC` and `ENUM` are the table. `is_defaulted` (line 81)
is false when the value is `None`: absent is not defaulted.
`defaulted_keys` (line 97) lists the present unusable keys.
`summary_line` (line 105) is the startup line,
`config: N settings read as their default: <keys>`.
`runner/ops/main.py` lines 131 to 136 log that line at startup
and do not exit on it.

**Stopped, for the refuse class.** `runner/ops/main.py`
returns 2. A bad size cap comes from `_validate_size_caps`
(`runner/runner.py` line 4707): for `max_job_bytes`,
`max_script_bytes`, and `max_result_bytes`, a boolean, a
non-int, or a negative is an error string naming the key, and
a missing key is fine. A present `imap_port` or `smtp_port`
goes through `runner/wire/mailbox.py` `_port` (line 80), which
raises `RuntimeError` naming the key when the value is a
boolean or not a number, and uses the default when the key is
absent. `build_key_policies` raises the same way for a
malformed policy. The security block is checked just above,
lines 81 to 118, including confinement or `job_user` set to
`enforce` when the mechanism cannot engage.

**Live reload.** `runner/ops/attest.py`, `reload_hot_config`
(line 87). For each key in `HOT_KEYS` (`runner/runner.py`
line 5045), an unusable value is replaced by `HOT_DEFAULTS`
and the log names the key and the default. The rest of
`defaulted_keys` is handled the same way, lines 125 to 136.
A file that cannot be parsed returns without advancing
`state["mtime"]`, so the next cycle retries it. The keys this
function reads are `HOT_KEYS`, `LIVE_KEYS`, and the defaulted
table. Ports, secrets, key policies, and security modes are
not among them.

## The model

`Decision.tla` is one decision. An attempt is a class
(`refuse` or `default`), a presence (`absent`, `usable`, or
`unusable`), and a moment (`startup` or `reload`). Twelve
attempts, which is the whole space. The outcome says whether
the process is running, which value a reader that continues
will use (`written`, `documented`, `prior`, or `none`),
whether the key is named, and whether the running binding was
left as it was.

The invariant `P6Inv` is the seven clauses, in that shape. The
process is stopped exactly when the class is refuse, the value
is present and unusable, and the moment is startup, and that
stop names the key. A reload never stops it. An unusable
default-class value, at either moment, is the documented
default and is named. An unusable or absent refuse-class value
at reload leaves the prior binding in place.

## What was checked

TLC 2.19 (the `v1.7.4` tools jar) on Java 17. The run is
exhaustive. Twelve initial states, one per attempt.

| Configuration | File | Invariant | Result | Generated | Distinct |
|---|---|---|---|---:|---:|
| Every class, presence, and moment | `Decision.cfg` | `P6Inv` | holds | 36 | 24 |
| A stop exists | `DecisionWitnessStop.cfg` | `NothingStops` | fails, as expected | 17 | 17 |
| A named default exists | `DecisionWitnessDefault.cfg` | `DefaultStaysUnusable` | fails, as expected | 23 | 23 |

The depth of the main search is 2: the attempt, then the
decision. The stop witness ends at `running = FALSE`,
`named = TRUE`, for class refuse, presence unusable, moment
startup. The default witness ends at `running = TRUE`,
`value = "documented"`, `named = TRUE`, for class default,
presence unusable, moment startup.

## Findings

No path was found by which a refuse-class value that is
present and unusable lets the runner start, or by which a
live reload changes a refuse-class binding or stops the
process. The default class names its fallback, and an absent
key is not reported as one.

One gap between the decision's sentence and the function is
recorded, in the open:

- **F1. A bad refuse-class value written while running is not
  named.** Decision 1 says a bad port written live keeps the
  current binding, logs an error, and takes effect only at
  the next start. `reload_hot_config` keeps the binding, and
  the value takes effect only at the next start, because the
  function never reads the key. It also never logs it. The
  safety half holds: the running binding does not move, and
  the process does not stop. The log half does not happen in
  this function. Classification: not a counterexample to P6
  as stated, because clause 6 claims the binding is unchanged
  and the process keeps running, and it does not claim a log
  line the code does not emit. It is recorded because the
  decision's own sentence asks for the line, and a reader of
  that sentence alone would expect one. No code was changed
  in this pass.

## What this does not say

- The model has one "unusable" bit. Each reader has its own
  rule for what that bit means. `confval.port` rejects 0 and
  anything outside `1..65535`. Mailbox `_port` rejects a
  boolean and a non-number, and it accepts any other int,
  including 0 and a negative. The startup check is whichever
  reader `main` calls for that key. The model checks the
  class, not each reader's bound.
- Job-supplied numbers are not this property. A query's
  `max_matches` comes from an untrusted sender, and an
  unusable one reads as the default and must not raise. That
  is the same `confval` reader and a different rule, settled
  in the decision record, and it is not a configuration key.
- The startup checks that are not a single present-but-
  unusable value — a missing secret, a symlink config path,
  confinement set to `enforce` when the sandbox cannot
  engage — stop the runner and name the reason. They are
  refuse-class in the same exit path. The model does not
  enumerate them; the pins call the size-cap and port
  readers, which are the shape the clauses describe.
- A usable refuse-class change written while running is also
  not applied. Clause 6 says the whole class is outside the
  reload set, not only the unusable values. A good new port
  waits for the next start too.
- Whether the missing log line in F1 should be added is a
  code change. This stage does not make it.
