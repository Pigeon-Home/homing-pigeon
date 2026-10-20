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
A `reply_to` that is not one address does not steer the
result. A newline, a comma, or a list falls back to the
runner's own mailbox. One plain address is honored, because
it was inside the signed body. A job cannot put a
`PIGEON_` variable into its own process, in either case.
Any other name it sets is still there. The next ordinary
job still runs. The same job submitted again does not
run a second time. A different job id still does. An
envelope signed with one key, around a body signed with
another, does not run. The next job whose keys agree still
does. A job aimed at a different runner, or at no runner,
does not run when audience is enforce. The job that names
this runner still does. A `script_url` of `file:` is not
fetched, in either case, and the inline script does not run
in its place. The next ordinary job still does. A null
byte in an argument or an environment name is refused, and
the script does not start. A null byte in the interpreter
is not a refusal. The path is absent, repair is the
default, and the platform shell is started. The Python
script does not run under that shell. The next ordinary
job still does. A ping that carries a script answers
`pong` and does not run the script. The next exec job
still does. A kind the runner does not know (`sh`, an
empty string, `Exec`) does not run the script it carries.
The next exec job still does. The same query is answered
once. The second copy, same seen set, gets nothing back.
A second query, different id, after the budget is spent,
does not get the canary either. The answer says budget.
A query aimed at a different job does not get it either.
The answer says unknown. The query for this job still does.
After `max_queries_per_hour` is spent, the next query is
answered `rate_limit` and does not get the canary. An
unknown op, even one that carries the fork bomb and an
instruction to print the output, is `unknown_op`. It does
not get the canary. A later grep of this job still does.
A pattern that does not compile is `bad_pattern` and does
not get the canary either. A later good grep still does.
A retained view of `summary` or `attested` does not return
the line. The answer says policy. `full` still does.
`redacted`, with the canary as a pattern, returns the
line with `[REDACTED:canary]` in its place. The pattern
the query itself sent is echoed. `full` still returns the
canary. A `max_matches` of zero returns no lines, and the
answer says the output was truncated. A later grep with
the default limit still returns the canary. An `ask`
whose question says to print the output, with no model
configured, is `inference_unconfigured`. The output is
not copied into the answer. A later grep still returns
the canary. Grep searches stderr as well as stdout. A
pattern that matches only stdout does not return the
stderr line. A `queries` value that is not a list, even
when the value is an instruction to print the canary, is
no queries. The answer is empty. A later grep still
returns the canary. A record whose `saved_at` is older
than the retention window is `expired` and does not
return the canary. A fresh `saved_at` still does.

An open task is not finished by a result or an approval.
It has to be claimed first. A later submit still opens.
A second submit of the same task does not replace it.
The first payload stays. A different task still opens.
Once a task is claimed, a result finishes it, and a second
result does not replace that. A later submit still opens.
With review required, a result holds the task at
`pending_review` and a second result does not replace it.
An approval is what marks it done. A worker whose
capabilities do not cover the task does not claim it. The
worker who has them does. A worker who is not on
`worker_allowlist` does not claim either. The worker who
is on the list does. A task in a compartment the worker
does not share stays open. The worker who shares it claims.

## One prompt-injection case

The fork bomb in
[tests/test_flag321_obfuscated.py](../tests/test_flag321_obfuscated.py)
is the pipe bomb: `:(){ :|:& };:`. The judge denies that exact
string and allows one added space. Nothing there is executed.

Wrapping either string in "ignore previous instructions" does
not change the judge. A stub model that obeys, and answers
with a job whose script is the bomb plus a canary from the
output, is dropped by the sanitizer. The answer is not handed
to a shell. A job-shaped answer with no canary comes back as
text. The format guard does not treat `{"kind","script"}` as
a tool call. The research notes, and where that premise
stops, are in
[docs/idea321/RUNBOOK.md](idea321/RUNBOOK.md).

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
