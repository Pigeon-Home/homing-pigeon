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
