# Fuzzing the intake

The Oracle takes input from sensors, extensions, the model, and
the transports. A refusal is a string. A crash is a bug. The
tests that hold that rule are in-memory. They open no socket
and they load no model.

## What the first passes found

One shape of crash, over and over: a value used as a dict key
before anyone checked it was a string.

- `check_key_policy` raised `TypeError` on a key id that was a
  list. A key id that is not a string is now a refusal.
- `parse_sensors` raised `TypeError` when `severity_floor` was
  not a string. A config file can carry that. It is now a
  config error, the same as any other bad floor.
- `validate_sensor_alert` raised `TypeError` when `severity`
  was a list. A signed alert can carry that. It is now a
  refusal, same as any other bad severity.
- `parse_manifest` raised `TypeError` when `kind` was not a
  string, and `load_extensions` only catches `ValueError`, so
  one bad `extension.json` aborted discovery. A non-string
  kind is now a refusal.
- The same check was open in three more lookups: a model tool
  name, a `security.modes` value, and `dtls_greeting`. A
  non-string is a refusal or a config error, not a crash.
- `baseline_anomaly` summed `kinds` with `sum()` and then
  used the job's `kind` as a dict key. A stored baseline
  whose counts are not numbers, or a `kind` that is a list,
  raised `TypeError`. Counts that are not finite numbers are
  skipped, and a non-string kind is treated as unknown.
- `feature_keys` and `touched_keys` called `.items()` on
  `tools` and `paths`, and indexed `interpreter[0]`. A probe
  that handed back a string or a number raised
  `AttributeError` or `TypeError`, and a string interpreter
  was read as its first character. Those fields are used
  only when they have the shape a probe is supposed to
  return.

Ring 2 has started for sensor alerts. A flipped signature
stores no alert. A signed alert whose severity is a list
stores no alert. The next good alert, in the same directory,
still files. The same rule holds for a job: a flipped
envelope does not run, and the next good job does. A
second wrap around an envelope does not run the script
inside it, and a job_id of `..` does not run either. A key
bound to sensor alerts only cannot run a script, and the
owner's key still can. A script over `max_script_bytes`
does not run, and the next script that fits still does. A
flipped query learns nothing from retained output. The next
good query of the same output still gets the answer.

That gap is closed. A query and a board message now go
through the same gate as a job. Cleartext is refused unless
the process was started with `--allow-cleartext`. An
encrypted query is answered, and the answer is encrypted
too, so a canary in retained output is not in the raw reply.
An encrypted submit opens the task. A cleartext submit does
not.

A job stamped two hours ago, or an hour ahead, does not
run. The window is `max_job_age_sec`, with five minutes of
slack into the future. The next job stamped now still runs.
A file named `../escaped.txt` is not staged and the script
does not run. The next ordinary job still does. A body
whose `job_id` is not the id in the subject does not run
either. The envelope still decrypts. The ids are what fail.

A short DTLS record raised `IndexError` inside the record
opener. It now raises `DtlsError`, which the session already
treats as a dropped record.

The crashes were easy because the generator was allowed to
hand the function a Python value that JSON on the wire cannot
carry. That pass is still worth finishing. It is not the
whole surface.

## Three rings

Ring 1 is anything already inside the process. The generator
builds messy Python values, not just JSON. The property is:
return a reason or `None`, and never raise. This is where
those `TypeError`s came from. The functions whose docstring says
"never raises" are the list. About fifty of them live under
`runner/`.

Ring 2 starts from a message the runner would accept and
changes one thing: a flipped byte in `sig`, a swapped
`key_id`, a nested `hp_enc`, a huge `script`, a `job_id` of
`.` or `..`, a duplicate key, a truncated length, an
`issued_at` outside the window. The families are a job, a
sensor alert, a query, a board message, an `hp_enc` envelope,
and a DTLS flight that already passed the cookie. The
property is stricter than "it returned." A bad signature
stores nothing. A rejected job does not run. A good neighbor
in the same poll still runs. One poison file does not stick
the channel.

Ring 3 is the parsers the coverage report already named.
`dtlsproto.py` wants mutated valid flights, not only random
datagrams. Then the email, file, and NATS extension programs,
one bad frame at a time. Still in memory. A live socket is
only worth it after the core stops crashing on bytes.

`learning.py`, the posture collectors, and the model are not
this campaign. Judgment is downstream of admission, and
admission is the part a sensor can reach.

## Where the tests are

- `tests/test_oracle_intake_fuzz.py` — ring 1 for alerts,
  manifests, key policy, the local envelope, review, the
  Oracle's tools, sensor config, a poisoned senses store, and
  the loopback socket reader. The tool named `run` is stubbed.
  The fuzzer must not grow a shell.
- `tests/test_dtls_fuzz.py` — ring 3, started: random
  datagrams and the fragment buffer.
- `tests/test_properties.py` — the older property tests on
  the signed-object core.

Hypothesis is a test-only dependency. CI installs it. A run
without it skips nothing in the example tests and fails these
on import.
