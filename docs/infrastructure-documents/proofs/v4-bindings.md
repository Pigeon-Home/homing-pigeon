# The v4 binding: the constraint spec

`v4-properties.md` gives every constraint its property.
`v4-general.md` states the 13 properties as 1 statement. This
file is the next step: every constraint tied, in 1 table, to
everything that keeps it. A constraint here is bound to the
properties that state it, the code that enforces it, the
tests that pin its value, the model that proves its property,
and the fuzz data that has reached its code. Each tie is held
by a test, so a tie that breaks fails by name.

The table is `v4-bindings.json` on this shelf, the registry.
This file is the registry as a page, with the record of the
pass that built it. `runner/tests/test_v4_bindings.py` holds
the registry to the tree and this page to the registry.

## What a tie is, and what holds it

1. **Constraint to property.** The properties that state the
   constraint, with the clauses, as Part 1 of
   `v4-properties.md` gives them. Held by reading that table
   again: the registry and the index must agree, constraint
   by constraint.
2. **Constraint to code.** The functions that enforce it, as
   `path:function`. Held by parsing each file: the function
   must be there.
3. **Constraint to pins.** The tests that pin its value or
   its behaviour, by name. Held by parsing each test file:
   the test must be there, and a test named for a constraint
   (`test_c14_...`) must be bound to it.
4. **Property to model.** The model file, its
   configurations, and the invariants they check. Held by
   reading each configuration: the invariants listed here
   are the ones the checker is asked for, and each is
   defined in the model.
5. **Property to conformance.** The suite that drives the
   real code against the property. Held by parsing: the
   suite is there and has tests.
6. **Property to the general model.** The steps of
   `general.tla` that mark the property in the ledger, and
   the seams that carry it: the constants of `general.tla`
   that, set the other way, make the checker break the
   property. Held by reading `general.tla` for the steps,
   and by the search in `runner/tests/test_v4_general.py`
   for the seams: the registry lists for each property the
   seams whose turning breaks its mark, and no other.
7. **Constraint to fuzz data.** The fuzz targets whose
   corpus enters the constraint's code, with the number of
   entries that do, the sizes of those entries, and 1 entry
   named as witness. This tie is measured, not written: see
   the 2 sections on the fuzz data below. Held by replaying
   the witness under a profiler on every suite run, and by
   sizing it again.
8. **Binding to evidence.** The provenance classes of the
   evidence that stands behind each property and each
   constraint, in the registry's Evidence column, stated in
   the terms the section on evidence provenance below
   defines. Held by the provenance tests in
   `runner/tests/test_v4_bindings.py`: a binding that
   carries no class, a class the registry's record does not
   define, or a class its own ties contradict fails there
   by name.

## The counts

The registry binds 31 constraints and 13 properties. It
names 60 code sites and 84 named pins, and it carries 77
fuzz ties. The fuzz part was counted on 2026-11-20.

## Every constraint, tied

The Pins column is the number of tests bound by name. The
Fuzz data column names each target bound to the constraint
and the largest number of its corpus entries that enter 1 of
the constraint's functions. The Evidence column names the
provenance classes of the evidence behind the constraint,
as the section on evidence provenance below defines them;
the properties table carries the same column for each
property.

| ID | Constraint | Stated by | Code | Pins | Fuzz data | Evidence |
|----|------------|-----------|------|------|-----------|----------|
| C1 | `max_job_bytes` | P1 clause 1 | `handle_mail` in `runner/ops/mail.py` | 4 | `gate` 15 | observed execution, model check |
| C2 | `max_script_bytes` | P1 clause 5 | `handle_mail` in `runner/ops/mail.py` | 4 | `gate` 15 | observed execution, model check |
| C3 | `max_result_bytes` | P11, the whole property | `_max_result_bytes` in `runner/runner.py`; `_fit_result_body` in `runner/runner.py` | 2 | `gate` 2 | observed execution, model check |
| C4 | `_LOCAL_ENVELOPE_MAX_BYTES` | P12, the whole property | `_ingest_local_envelope_inner` in `runner/runner.py`; `_scan_local_inbox` in `runner/runner.py` | 3 | `local` 518, `query` 32, `local_inbox` 23 | observed execution, model check |
| C5 | Signature | P1 clause 2 | `sign_payload` in `runner/wire/verify.py`; `verify_body_keyed` in `runner/wire/verify.py`; `_verify_and_decrypt` in `runner/runner.py` | 3 | `wire` 116, `gate` 9 | observed execution, model check |
| C6 | Secret entropy floor | P13, the whole property | `validate_shared_secret` in `runner/guard/security.py`; `build_secrets` in `runner/wire/verify.py` | 3 | `secret` 26, `local` 518, `query` 183 | observed execution, model check |
| C7 | Key fingerprint | P1 clause 2; P4 clause 1 | `key_fingerprint` in `runner/guard/security.py` | 1 | `local` 518, `query` 183 | observed execution, model check |
| C8 | Cleartext | P1 clause 3 | `_cleartext_jobs_allowed` in `runner/runner.py` | 2 | `query` 3, `v2_mail` 3, `board_mail` 2, `gate` 1 | observed execution, model check |
| C9 | AEAD | P1 clause 3 | `decrypt_body` in `runner/wire/jobcrypto.py` | 2 | `crypto` 73 | observed execution, model check |
| C10 | Audience | P1 clause 4 | `check_audience` in `runner/wire/verify.py`; `audience_allows` in `runner/wire/verify.py` | 1 | `query` 176, `board_mail` 95 | observed execution, model check |
| C11 | Nine security modes | P1 clauses 4 and 8; P4 clause 11 | `sec_mode` in `runner/guard/security.py`; `sec_decide` in `runner/guard/security.py`; `validate_security_config` in `runner/guard/security.py` | 2 | `query` 176, `board_mail` 95 | observed execution, model check |
| C12 | `max_job_age_sec` | P1 clause 7 | `handle_mail` in `runner/ops/mail.py` | 2 | `gate` 15 | observed execution, model check |
| C13 | Protocol version | P1 clause 6 | `_version_ok` in `runner/runner.py`; `handle_mail` in `runner/ops/mail.py` | 4 | `local` 518, `query` 176, `board_mail` 95, `local_inbox` 23, `gate` 15 | observed execution, model check |
| C14 | Key policies | P1 clause 8; P4, the whole property | `check_key_policy` in `runner/wire/verify.py`; `_build_key_policies` in `runner/wire/verify.py` | 9 | `keydir` 35, `local` 518, `query` 163 | observed execution, model check |
| C15 | Execution semantics | P1 clause 9; P5, the whole property | `handle_mail` in `runner/ops/mail.py`; `stash_result` in `runner/runner.py`; `load_sent_result` in `runner/runner.py` | 2 | `gate` 15, `race_stash` 180 | observed execution, model check |
| C16 | Transport credentials | P3, the whole property | `__init__` in `runner/transport_extensions/nats/__main__.py`; `fetch_channel_messages` in `runner/wire/transports.py` | 2 | `inbox` 29, `channels` 11 | observed execution, model check |
| C17 | Result-policy ceiling | P2 clauses 5, 6 and 8 | `apply_result_policy` in `runner/ops/policy.py` | 7 | `queries` 134 | observed execution, model check |
| C18 | Sandbox shape | P2 clauses 1 to 4 | `build_bwrap_command` in `runner/guard/sandbox.py`; `_confinement_cfg` in `runner/guard/sandbox.py` | 3 | none | observed execution, model check |
| C19 | Queues edge gates | P3 clause 8 | `bearerMatches` in `runner/cloud/queues-worker/src/index.js` | 2 | none | observed execution, model check |
| C20 | Transport gate postures | P3 clauses 4 to 8 | `scan_jobs` in `runner/transport_extensions/file/__main__.py`; `feed_authenticated` in `runner/wire/dtlsproto.py`; `service_channel` in `runner/wire/transports.py` | 4 | `dtls` 7, `dtls_session` 7, `inbox` 29 | observed execution, model check |
| C21 | Key directory precedence | P4 clauses 2 and 9 | `key_directory_verdict` in `runner/wire/verify.py`; `load_key_directory` in `runner/wire/verify.py` | 1 | `keydir` 38 | observed execution, model check |
| C22 | Upgrade key arrangement | P4 clauses 5, 7, 8 and 11 | `check_key_policy` in `runner/wire/verify.py` | 1 | `keydir` 35 | observed execution, model check |
| C23 | Replay-cache keep horizon | P5 clauses 5 and 8 | `seen_keep_sec` in `runner/runner.py`; `_write_seen_kept` in `runner/runner.py`; `save_seen` in `runner/runner.py` | 3 | `race_state` 217, `board_mail` 78, `v2_mail` 32, `gate` 2 | observed execution, model check |
| C24 | Claim stale rule | P5 clause 4 | `_disk_owns` in `runner/ops/misc.py`; `_disk_release` in `runner/runner.py` | 2 | `gate` 2 | observed execution, model check |
| C25 | Record retention and delivery window | P5 clauses 9 and 10 | `prune_sent` in `runner/runner.py`; `deliver_stash` in `runner/runner.py`; `resend_stashed` in `runner/runner.py` | 1 | `race_stash` 179, `gate` 2 | observed execution, model check |
| C26 | Default-class reader | P6 clauses 1, 2, 3 and 5 | `integer` in `runner/guard/confval.py`; `number` in `runner/guard/confval.py`; `reload_hot_config` in `runner/ops/attest.py` | 3 | `local` 518, `race_state` 217 | observed execution, model check |
| C27 | Refuse class at startup | P6 clauses 4 and 6 | `_validate_size_caps` in `runner/runner.py`; `_port` in `runner/wire/mailbox.py` | 2 | none | observed execution, model check |
| C28 | Disk guard | P7, the whole property | `guard_disk` in `runner/oracle/resources.py`; `disk_guard_enabled` in `runner/oracle/resources.py` | 4 | none | observed execution, model check |
| C29 | v3 hybrid group | P8, the whole property | `begin` in `runner/wire/dtlsproto.py` | 1 | `dtls_session` 42, `dtls` 31, `dtls_hostile` 14 | observed execution, model check |
| C30 | DTLS framing | P9, the whole property | `_split_records` in `runner/wire/dtlsproto.py`; `_accept_seq` in `runner/wire/dtlsproto.py` | 2 | `dtls` 61, `dtls_session` 55, `dtls_hostile` 39 | observed execution |
| C31 | macOS confinement probe | P10, the whole property | `macos_confinement_problem` in `runner/guard/macos_confine.py`; `_confinement_argv` in `runner/runner.py`; `confinement_startup_problem` in `runner/ops/remediation_ops.py` | 2 | none | observed execution, model check |

## Every property, tied

| Property | Stated in | Model | Checked invariants | Conformance | Steps in `general.tla` | Seams that carry it | Evidence |
|----------|-----------|-------|--------------------|-------------|-------------------------|---------------------|----------|
| P1 | `properties.md` | `gate.tla` | `P1Inv`, `SensorInv`, `AudienceWasRequired`, `NamedByTheSignedId`, `OneVersionBeforeTheBody` | `test_proof_conformance.py`, `test_v4_behind_the_mac.py` | `Handle`, `Local` | `LocalFilesOnly`, `GateVerifies`, `GateFresh` | observed execution, model check |
| P2 | `properties.md` | `confine.tla` | `P2Inv`, `EffViewExact`, `EffBudgetExact` | `test_proof_conformance_p2.py` | `Handle` | `SpawnProbes` | observed execution, model check |
| P3 | `properties.md` | `transgate.tla` | `P3Inv`, `GateBlocks`, `PresentedExact`, `AcceptedExact` | `test_proof_conformance_p3.py` | `Handle` | `TransportGates` | observed execution, model check |
| P4 | `properties.md` | `keypolicy.tla` | `P4Inv`, `PinBinds`, `PolicyExact` | `test_proof_conformance_p4.py` | `Handle` | `GatePolicy` | observed execution, model check |
| P5 | `properties.md` | `replay.tla` | `P5Inv`, `SeenImpliesRecord`, `DeliveredImpliesRecord` | `test_proof_conformance_p5.py` | `Handle`, `Local` | `GuardSparesFresh`, `LocalFilesOnly`, `GateFresh` | observed execution, model check |
| P6 | `properties.md` | `decision.tla` | `P6Inv` | `test_proof_conformance_p6.py` | `Start` | `StartValidates` | observed execution, model check |
| P7 | `v4-properties.md` | `diskguard.tla` | `NeverStops`, `OrderRespected`, `RecordedFaithfully` | `test_v4_models.py::Conformance`, `test_disk_guard.py` | `Guard` | `GuardSparesCache` | observed execution, model check |
| P8 | `v4-properties.md` | `hybridselect.tla` | `P8Inv`, `OnlyOffered` | `test_v4_models.py::HybridSelectConformance` | `Agree` | `PrefersHybrid` | observed execution, model check |
| P9 | `v4-properties.md` | none | none | `test_v4_models.py::FramingScopePin` | `Agree` | `SameSideOnly` | observed execution |
| P10 | `v4-properties.md` | `probegate.tla` | `P10Inv`, `RefusesOnlyItsOwn` | `test_v4_models.py::ProbeGateConformance` | `Start`, `Handle` | `SpawnProbes` | observed execution, model check |
| P11 | `v4-properties.md` | `resultfit.tla` | `MarkedWhenCut`, `CapZeroAsIs`, `FitsAsIs`, `P11Floor` | `test_v4_models.py::ResultFitConformance` | `Commit` | `FitMarks` | observed execution, model check |
| P12 | `v4-properties.md` | `localgate.tla` | `P12Inv`, `SymlinkUnread`, `ReadBounded`, `OverCapRefusedForSize` | `test_v4_models.py::LocalGateConformance` | `Local` | `LocalBounds` | observed execution, model check |
| P13 | `v4-properties.md` | `secretfloor.tla` | `P13Inv`, `NamesACause` | `test_v4_models.py::SecretFloorConformance` | `Start`, `PollBegin`, `Local` | `PollRebuilds` | observed execution, model check |

P9 has no model. It is a statement of scope, held by its
pin, and `v4-working.md` records why it admits none.

Every property has at least 1 seam. With all 14 seams as the
code has them, every mark holds in every reachable state of
the general model. Each seam, set the other way, breaks the
properties listed against it, and its witness configuration
shows the checker doing so. `v4-general.md` has the counts,
the checker's run, and what holds each seam to the real
code.

## Evidence provenance

Every result this registry rests on is qualified by what
kind of evidence it is. The registry keeps a provenance
record: 5 classes, in the terms the ledger work of
23 November 2026 gives them, and every property and every
constraint in the tables above carries the classes of the
evidence that stands behind it, in an Evidence column.

The classes are these. A **candidate input** is an example
or a row produced to be tried; on its own it establishes
nothing about the runner, because nothing has run. An
**observed execution** is the real code running on an
input, with the result observed; it speaks for the build,
the configuration and the environment it ran under, and
for no other. A **model check** is a check of the abstract
model by the model checker, under the model's own
assumptions and bounds; it establishes the statement about
the model, and the step from the model to the code is a
separate obligation. An **independently checked
certificate** is a certificate produced by one party and
checked by another that does not share its workings; the
certificate carries its own bound, and the cost of finding
it is charged to the claim it supports. A **synthetic**
row is a row made to exercise the reporting pipeline; it
carries no observation of the runner, and it counts as
evidence of nothing about the runner until the execution
it stands for is performed.

What the registry carries today, read off the tables:
every property and every constraint stands on observed
executions, the suites and pins that run the real code
and, for the constraints that carry them, the corpus
replays. Every property with a model stands on a model
check as well, and so does every constraint a modelled
property states. P9 admits no model, so P9 stands on
observed executions alone, and C30, the 1 constraint P9
states alone, does the same. No binding in the registry
yet stands on a candidate input, on an independently
checked certificate, or on a synthetic row. Those classes
stand defined so that evidence of those kinds is labelled
with its class when it arrives, and never read as a
stronger class than it is.

Beside the classes, the registry records the witness
families the evidence is drawn from, recorded before the
examples they name are generated: **grammar productions**,
the productions of the bounded script grammar; **boundary
lengths**, lengths at and beside every bound the claims
use, in characters and in UTF-8 bytes; **observable
outcome classes**, the outcomes the specification allows
an arrival or a run to have; and **supported environment
profiles**, the environments the support matrix names. An
example generated for this registry names its family when
it is recorded, the way a result names its class.

## The fuzz data

The fuzz campaign's log (`runner/tests/de_dust/runs.jsonl`)
records 35,270 grow runs over 31 targets. Together they tried
651,086,719 inputs against the readers' contracts. The
corpus those runs kept stands at 2,664 corpus entries, and no
crash stands open in it. That last claim carries the
certificate the ledger's second honesty rule asks for
(`properties.md`, the corpus honesty rules): the space is
the inputs those recorded runs tried, the order is the
campaign's own order in the log, and the budget is the
runs themselves, with every child held at or under 16,384
bytes, as the sizes section below records. A crash on an
input outside that space, that order, or that budget is
not a crash this sentence speaks about.

A fuzz target is bound to a constraint when its corpus
enters a function the constraint names. The count is made by
replaying every corpus entry of every target under a
profiler, through the target's own check, and noting which of
the registry's functions the entry enters. Where a target's
own tracer follows the function's file, that target is
bound. Where none does, the 2 targets with the most entries
inside the function are bound, and the registry marks the
tie as not traced. 3 targets, `race_board`, `race_stash` and
`race_state`, interleave threads, so the number of their
entries that enter a function moves by a few from one count
to the next. The registry carries 1 count of them.

18 of the 31 targets are bound to at least 1 constraint.
208,556,359 of those inputs were tried by the bound targets.

| Target | Grow runs | Inputs tried | Refused | Accepted | Corpus entries | Constraints it reaches |
|--------|-----------|--------------|---------|----------|----------------|------------------------|
| `board_mail` | 924 | 1,937,096 | 1,588,998 | 439,695 | 100 | C8, C10, C11, C13, C23 |
| `channels` | 1,216 | 3,450,021 | 2,281,352 | 1,182,071 | 11 | C16 |
| `crypto` | 1,132 | 9,205,640 | 9,081,265 | 203,412 | 73 | C9 |
| `dtls` | 2,127 | 32,116,176 | 17,416,446 | 14,821,119 | 61 | C20, C29, C30 |
| `dtls_hostile` | 1,942 | 3,893,108 | 104,845 | 3,861,172 | 39 | C29, C30 |
| `dtls_session` | 1,815 | 2,159,718 | 1,556,483 | 694,169 | 58 | C20, C29, C30 |
| `gate` | 0 | 0 | 0 | 0 | 15 | C1, C2, C3, C5, C8, C12, C13, C15, C23, C24, C25 |
| `inbox` | 1,040 | 3,171,454 | 724,097 | 2,476,677 | 29 | C16, C20 |
| `keydir` | 2,018 | 91,662,364 | 63,194,578 | 28,544,435 | 38 | C14, C21, C22 |
| `local` | 832 | 18,066,031 | 18,281,866 | 84,890 | 518 | C4, C6, C7, C13, C14, C26 |
| `local_inbox` | 1,196 | 3,964,993 | 3,352,273 | 640,161 | 23 | C4, C13 |
| `queries` | 662 | 2,346,312 | 719,626 | 1,697,059 | 134 | C17 |
| `query` | 700 | 1,714,235 | 849,896 | 984,092 | 183 | C4, C6, C7, C8, C10, C11, C13, C14 |
| `race_stash` | 706 | 12,967,212 | 3,749,748 | 9,288,089 | 185 | C15, C25 |
| `race_state` | 817 | 12,608,745 | 2,045,106 | 10,630,018 | 229 | C23, C26 |
| `secret` | 1,066 | 3,268,013 | 1,845,998 | 1,449,729 | 26 | C6 |
| `v2_mail` | 916 | 1,958,927 | 1,803,414 | 232,325 | 84 | C8, C23 |
| `wire` | 1,111 | 4,066,314 | 2,091,537 | 2,100,192 | 118 | C5 |

A tie says that this target's inputs run through this
function, under a contract the target checks on every input.
It does not say the inputs prove the constraint. The log
counts inputs by target, not by function, so an input
counted for a target may have been refused before it reached
the function. What a tie gives is direction: which data
already presses on which constraint, and where none does.

Each bound target's corpus is replayed against its contract
on every suite run by `CorpusReplayTest` in
`runner/tests/test_de_dust_corpus.py`.

The controls for the claims of this section, under the
ledger's first honesty rule (`properties.md`, the corpus
honesty rules). The positive control is the replay itself:
every kept entry is run again through its target's check on
every suite run, and the check's answer on it is the answer
its contract requires, so the machinery is shown saying yes
and no on known inputs each time. The negative controls
stand at the doors, in the section below: arrivals turned 3
ways (1 digit of the signature changed, the body changed
under its signature, a key the runner does not hold) run
nothing, and a job 1 byte past a cap is refused. The
machinery is shown refusing what it must refuse, on inputs
built for that answer.

## The sizes beside the reach

A tie's count says how many corpus entries enter a function.
This section says how large those entries are, so the reach
and the sizes stand together beside each constraint.

The size of an entry is the campaign's own count of it: a
text entry's bytes as UTF-8, and a payload entry's bytes as
the JSON the tool writes. The tool tries no child past its
cap by that count, so a child is at most 16,384 bytes. The
`Sizes` class in the test module holds the 2 counts together
at the cap: a child of exactly the cap is tried, and a child
1 byte past it is not.

The sizes come from the same replay as the reach. For each
tie the registry carries the smallest entry inside the
function, the largest, and the number in each of 4 bands.
For each constraint it carries the same over all its ties,
and an entry that enters 2 of the constraint's functions is
counted once. 26 of the 31 constraints have entries to size.

| ID | Constraint | Entries inside | Smallest | Largest | Under 100 bytes | 100 to 999 | 1,000 to 9,999 | 10,000 and over |
|----|------------|----------------|----------|---------|-----------------|------------|----------------|-----------------|
| C1 | `max_job_bytes` | 15 | 0 | 11,642 | 2 | 11 | 0 | 2 |
| C2 | `max_script_bytes` | 15 | 0 | 11,642 | 2 | 11 | 0 | 2 |
| C3 | `max_result_bytes` | 2 | 708 | 743 | 0 | 2 | 0 | 0 |
| C4 | `_LOCAL_ENVELOPE_MAX_BYTES` | 573 | 0 | 4,280 | 54 | 487 | 32 | 0 |
| C5 | Signature | 127 | 0 | 11,642 | 5 | 118 | 2 | 2 |
| C6 | Secret entropy floor | 727 | 0 | 4,754 | 70 | 620 | 37 | 0 |
| C7 | Key fingerprint | 701 | 0 | 4,754 | 47 | 617 | 37 | 0 |
| C8 | Cleartext | 9 | 233 | 857 | 0 | 9 | 0 | 0 |
| C9 | AEAD | 73 | 50 | 4,427 | 2 | 70 | 1 | 0 |
| C10 | Audience | 271 | 71 | 8,583 | 2 | 229 | 40 | 0 |
| C11 | Nine security modes | 271 | 71 | 8,583 | 2 | 229 | 40 | 0 |
| C12 | `max_job_age_sec` | 15 | 0 | 11,642 | 2 | 11 | 0 | 2 |
| C13 | Protocol version | 827 | 0 | 11,642 | 58 | 725 | 42 | 2 |
| C14 | Key policies | 716 | 0 | 4,754 | 61 | 618 | 37 | 0 |
| C15 | Execution semantics | 195 | 0 | 12,288 | 2 | 186 | 4 | 3 |
| C16 | Transport credentials | 40 | 13 | 1,822 | 10 | 29 | 1 | 0 |
| C17 | Result-policy ceiling | 134 | 65 | 12,565 | 4 | 124 | 5 | 1 |
| C18 | Sandbox shape | none |  |  |  |  |  |  |
| C19 | Queues edge gates | none |  |  |  |  |  |  |
| C20 | Transport gate postures | 43 | 13 | 1,822 | 5 | 33 | 5 | 0 |
| C21 | Key directory precedence | 38 | 30 | 176 | 18 | 20 | 0 | 0 |
| C22 | Upgrade key arrangement | 35 | 31 | 176 | 15 | 20 | 0 | 0 |
| C23 | Replay-cache keep horizon | 329 | 63 | 8,577 | 2 | 317 | 10 | 0 |
| C24 | Claim stale rule | 2 | 708 | 743 | 0 | 2 | 0 | 0 |
| C25 | Record retention and delivery window | 184 | 130 | 12,288 | 0 | 179 | 4 | 1 |
| C26 | Default-class reader | 735 | 0 | 1,191 | 47 | 680 | 8 | 0 |
| C27 | Refuse class at startup | none |  |  |  |  |  |  |
| C28 | Disk guard | none |  |  |  |  |  |  |
| C29 | v3 hybrid group | 87 | 17 | 1,005 | 7 | 75 | 5 | 0 |
| C30 | DTLS framing | 155 | 0 | 12,550 | 17 | 132 | 5 | 1 |
| C31 | macOS confinement probe | none |  |  |  |  |  |  |

What the sizes say:

1. **The corpus is a corpus of small inputs.** Of the 2,664
   corpus entries, 361 are under 100 bytes, 2,208 are of 100
   to 999 bytes, 90 are of 1,000 to 9,999 bytes, and 5 are of
   10,000 bytes or more. The largest is 12,565 bytes.
2. **No fuzz input is the size of a size cap.** C1 to C4 are
   caps on size: 4,194,304 bytes for a job, 1,048,576 for a
   script, 5,242,880 for a result and 262,144 for a local
   envelope. A child of the campaign is at most 16,384
   bytes, which is under all 4. All 4 caps now have fuzz
   data at their code: the gate target's 15 entries enter
   the gate for C1 and C2, 2 of them reach the result
   fitting for C3, and C4 keeps 573 entries, and the
   largest of them is 4,280 bytes. The gate's largest entry
   is 11,642 bytes, far under every cap, so the campaign's
   data does not hold the edge of a cap, and with this cap
   on a child it cannot. The
   edge is held by pins, and by the corpus grown to the cap
   at the doors, in the section below: C1 and C2 at the gate,
   and C4 at the local door.
3. **F10 is what a missing size looks like.** The opener
   search's cost grew with the square of the body. The
   largest entry at the signature's code is 11,642 bytes. A
   body of 3,176 bytes in F10's shape cost the earlier search
   0.07 seconds here on 2026-11-19, under the half second
   from which the campaign files an input as slow. At 16,384
   bytes the same shape cost it 1.9 seconds. That size was
   inside the campaign's cap, and the corpus never grew
   there.
4. **An empty row is not a small row.** The 5 constraints
   with no fuzz data have nothing to size, and the table
   shows them empty.

The run log counts the inputs tried and not their sizes. So
the sizes here are those of the corpus the runs kept, and
for the 651,086,719 inputs the cap on a child is the bound.

Every entry counted in a band is replayed against its
target's contract on every suite run, as the section above
says. So a band's count is a count of inputs of that size
whose contract holds on the tree as it stands.

## What the fuzz data does not reach

26 of the 31 constraints have fuzz data at their code. 5
constraints have none: C18, C19, C27, C28 and C31. Across
all 31 there are 17 code sites that no corpus entry enters.

| ID | Constraint | Code no corpus entry enters |
|----|------------|-----------------------------|
| C11 | Nine security modes | `sec_decide` in `runner/guard/security.py`; `validate_security_config` in `runner/guard/security.py` |
| C16 | Transport credentials | `__init__` in `runner/transport_extensions/nats/__main__.py` |
| C18 | Sandbox shape | `build_bwrap_command` in `runner/guard/sandbox.py`; `_confinement_cfg` in `runner/guard/sandbox.py` |
| C19 | Queues edge gates | `bearerMatches` in `runner/cloud/queues-worker/src/index.js` |
| C20 | Transport gate postures | `scan_jobs` in `runner/transport_extensions/file/__main__.py` |
| C24 | Claim stale rule | `_disk_release` in `runner/runner.py` |
| C25 | Record retention and delivery window | `prune_sent` in `runner/runner.py` |
| C26 | Default-class reader | `reload_hot_config` in `runner/ops/attest.py` |
| C27 | Refuse class at startup | `_validate_size_caps` in `runner/runner.py`; `_port` in `runner/wire/mailbox.py` |
| C28 | Disk guard | `guard_disk` in `runner/oracle/resources.py`; `disk_guard_enabled` in `runner/oracle/resources.py` |
| C31 | macOS confinement probe | `macos_confinement_problem` in `runner/guard/macos_confine.py`; `_confinement_argv` in `runner/runner.py`; `confinement_startup_problem` in `runner/ops/remediation_ops.py` |

The gate itself is no longer the gap it was. The
campaign's `gate` target enters `handle_mail` on every
suite run, and reaches 11 constraints by that road: the 2
size caps, the freshness window, the signature, the
cleartext refusal, the execution semantics and the replay
cache among them, at the place where they are decided.
What stands in the table is narrower now: a site inside a
reached constraint (the claim's release, the retention
prune, the hot config reload), and the 5 constraints no
entry reaches at all, the disk guard, the sandbox shape,
the queues edge gates, the startup refuse class and the
macOS confinement probe, held by their models and their
conformance suites, with no fuzz target.

2 targets, `stage` and `collect`, are not bound to any
constraint, and `CorpusReplayTest` has no test named for
either.

## The corpus at the doors

The second half of `runner/tests/test_v4_bindings.py` takes
the corpus to the doors themselves. Nothing was added to the
corpus. The entries are read as they stand, and where a
door needs a fresh date the entry is given the present and
signed with the key it names. The counts below are from
2026-11-18.

**The mail gate (P1, P5).** The wire, crypto and mail corpora
make 215 arrivals at `handle_mail`: 116 wire, 73 crypto, 26
mail. Each was delivered twice with cleartext refused, and
twice with cleartext allowed. None ran and the gate never
raised.
81 of them got as far as the freshness window and stopped
there, since the corpus is dated 2026-10-26.

The wire corpus holds 55 job payloads. Given the present for
their `issued_at`, 54 can be signed. With cleartext allowed,
40 run, each exactly once: a second delivery runs nothing,
with the replay cache or without it. For each of the 40 the
test reads P1's clauses off the payload and the bytes with
its own hands (the key is held, its own HMAC verifies, the
version and type, the subject's id, the window, the script's
cap), and every clause holds. With cleartext refused, none
of the 54 runs. Sealed under the key they name, the same 40
run under the default and no other.

Each of the 40 was then turned 3 ways: 1 digit of its
signature changed, its body changed under its signature,
and signed by a key the runner does not hold. None of the
120 runs. Dated 3,700 seconds old or 400 seconds ahead, none
runs. Dated 3,500 seconds old or 200 seconds ahead, all run.
Sealed under a key the runner does not hold, none runs.

A 41st of the 54 runs when its mail is written out as plain
octets and not by the mail library. That is finding F11,
below.

**The size caps at the gate (C1, C2).** No fuzz target then
entered `handle_mail`, so the 2 caps decided there had no
entry to size. `CorpusUpTheSizes` takes the corpus's fresh jobs up the
sizes instead. The counts are from 2026-11-19. Written out as
plain octets, 41 of the jobs run, and 5 of the 41 carry a
script.

Each of the 41 mails was grown, by a note below its body, to
1,000, 10,000 and 100,000 bytes, and every 8th of them on to
1,000,000 bytes and to the cap itself, 4,194,304 bytes. At
every rung the job runs, and P1's clauses hold. 1 byte past
the cap, at 4,194,305 bytes, none of the 41 runs, and the
gate has asked for no signature and made no dispatch: the
refusal comes before any signature work, as C1 says. With
the cap set at each lower rung the same holds: the mail of
that size runs, and 1 byte more is refused.

Each of the 5 scripts was grown, by a comment line, up the
proof's own ladder for P1 in `goals.md`: 49, 500, 5,000 and
50,000 bytes, and 1 of them on to 500,000 bytes and to the
cap itself, 1,048,576 bytes. At every rung the job runs, and
P1's clauses hold. 1 byte past the cap the job does not run,
and the gate has verified its signature first, as C2 says.
With the cap set at each lower rung the same holds, and it
holds by bytes: a script grown with a 3 byte character is
refused 1 byte past a cap while it holds fewer characters
than the cap has bytes. With either cap set to 0, a mail or
a script 1 byte past the default runs.

So C1 and C2 have the corpus at their edges. The gate
target in the fuzz count above has since put a target of
the campaign at the same door. The registry binds these
tests to the 2 constraints as pins, and the local door's
test of its cap to C4.

**The local door (P12, and finding F9).** All 518 entries of
the local corpus went through the local door with a watch on
the run: 3 were filed as alerts, 515 were turned away, and
nothing ran. The 54 fresh jobs went to the local door as
well: the mail gate runs 40 of them and the local door runs
none. 433 text entries were grown to 1 byte over the cap,
and each was refused before a key map was built or a
signature was read.

**The floor (P13).** The 26 candidate secrets of the secret
corpus were given to the start's check and to the key map a
poll builds, as the default key and as an additional key.
18 are refused and 8 pass, and the 3 places agree on every
one.

**The result fitting (P11).** No fuzz target enters the
fitting, so corpus text was used as a result's streams: 6
corpora, 6 caps each, unsealed, and 2 more sealed. Of the
48 fits, 8 left the body as it was, 29 cut it to fit, and
11 left it at its floor, over the cap and marked. No body
left over its cap and over its floor, none left over its
cap unmarked, and every body sent verified as signed.

## Finding F10: the opener search read a body once for each brace

The fitting test was slow in a way the fitting could not
explain. The time went to the verifier, and it grew faster
than the text. That led to this finding.

A signed body is a JSON object whose last brace is replaced
by the signature. To find the object's first brace the
verifier tries every brace that passes a brace walk, newest
first, and takes the first whose text parses
(`_object_start` in `runner/wire/verify.py`, and its copy in
`runner/cloud/send_job.py`). The walk was made 1 pass on
2026-10-30. The parse was not: for each candidate the search
copied the text from that brace to the marker, cleaned it,
and parsed it.

A body made of `{\"` repeated makes every brace a candidate.
From any of its braces the walk reads the backslash as plain
text and the quote as the start of a string that runs to the
end, so every brace passes. Each candidate then fails the
parse at its second character, after the copy and the
cleaning. The cost is candidates times length, and it is paid
before any MAC, so the sender needs no key.

Measured on 2026-11-18, in this seat's container:

| Body | Before: time | Before: characters parsed | After: time | After: characters parsed |
|------|--------------|---------------------------|-------------|--------------------------|
| 3,107 bytes | 0.06 s | 3,007,000 (968 times the body) | 0.005 s | 31,865 (10 times) |
| 12,107 bytes | 1.1 s | 48,028,000 (3,967 times) | 0.013 s | 127,865 (11 times) |
| 48,107 bytes | 15.3 s | 768,112,000 (15,967 times) | 0.055 s | 511,865 (11 times) |
| 3,000,107 bytes | not run | not run | 3.5 s | not counted |

The time before grew 4 times for each doubling of the body.
By that law a body at the 4 MiB cap of `max_job_bytes` would
have held the verifier about 32 hours. That figure is a
projection from the 3 measurements, not a measurement.

The change: the search now looks at a candidate's first 32
characters before it reads the candidate whole
(`_opens_object`). A JSON parse reads left to right, so an
error well inside a look is the whole text's error too, and
the candidate is passed over for the cost of the look. A
look that ends in doubt, with the error within 16 characters
of its edge or a string running off its end, is made 4 times
longer and read again. What is never settled goes to the
full parse as before. Only parse errors that more text cannot
mend are taken as settled, by their wording, and any other
wording is left to the full parse: a parser that words an
error differently costs time and never an answer. A look
nested deeper than the parser will follow settles the
candidate too, since the full parse runs at the same depth
of calls and stops at the same place.

`runner/tests/test_opener_cost.py` holds the change:

- The answers are the old search's. The old search stands in
  the test as written before, and the 2 agree on 20,000
  random hostile texts with the look's size moved, on every
  corpus text that carries a marker, and on a signed job
  whose script is the hostile units.
- The reading is bounded by a count and not by a clock: a
  body in which every brace is a candidate is handed to the
  parser at most 16 times its length, at 3 sizes, in both
  Python homes of the search.
- A look never settles against a sound object, cut at every
  length, and never against a string that runs off its end.
- A body whose candidates each nest 30,000 arrays deep is
  read less than 2 times its length.

The same change stands on main from 2026-11-18, where the
desk carries it as Q203.

A third copy of the search is not changed. The hosted
queue's Worker has its own, `objectStart` in
`runner/cloud/queues-worker/src/index.js`. It walks from
every brace and reads each candidate whole, so it carries
both costs: on the same shape of body, 24,107 bytes took it
0.58 seconds under Node 22 in this seat's container. A
request reaches it only behind a tenant's bearer token, and
the platform bounds a request's time, so what it can cost is
that tenant's own request. It is named here so the count is
right: the search has 3 homes, and 2 are closed.

## Finding F11: a mail library's subject stops a job with a long id

**Found with the corpus at the gate, in 2 forms of mail.
Closed: the owner chose both ways (the desk's Q204), and both
stand below.**

The wire corpus holds a job whose id is 128 characters long,
the longest the protocol allows. Written out as plain octets
it runs. Written by Python's mail library it does not: the
gate refuses it with `job_id mismatch between subject and
body`, after its signature has verified, and no result is
sent to say why.

The library does this to the subject. A word too long for 1
header line is written as encoded words (`=?utf-8?q?...?=`)
over several lines. `handle_mail` reads a subject as it is
written and does not decode such words, so the id it reads
off the subject is not the id in the signed body.

Measured here on 2026-11-19, on Python 3.11, 3.12 and 3.13:
an id of up to 77 characters is written plain and the job
runs, and an id of 78 to 128 characters is written as encoded
words and the job is refused. The sender's helper names a job
by a UUID, 36 characters, so its own mails are not touched.
The runner's sender writes its subjects with the same
library, so a result for a job with a long id leaves under
an encoded subject too.

It fails closed: nothing runs that should not. What is lost
is a signed, fresh job that the protocol allows.
`CorpusUpTheSizes` holds the shape of it: as octets a job
runs at every length of id, and a job that the library's
mail does not run is stopped at its subject and nowhere
else. That test passes whichever way the finding is closed.

There are 2 ways to close it, and each changes what the
protocol says of a subject:

1. The gate decodes a subject's encoded words before it reads
   the id. That is 1 more reader in front of the MAC, with a
   cost and a surface of its own.
2. A subject is read as written, the protocol says so, and a
   sender keeps a long id on 1 plain line. The runner's own
   sender would then write its subjects that way.

What each way costs, measured here on 2026-11-19 on Python
3.13:

- **Where the subject is read.** The gate takes the id off
  the subject before it asks for the signature. The id names
  the job to the dispatcher and in the log, and a sealed
  body is bound to it. So a decoder for the first way reads
  a stranger's bytes in front of the MAC, on every mail that
  carries the marker. `CorpusUpTheSizes` holds the order.
- **What the library's decoders cost.** The standard library
  has 2. On a subject made of many small encoded words,
  `decode_header` took 0.04 seconds at 64,013 bytes, 0.49 at
  256,009 and 7.63 at 1,000,011. The default policy's
  reading took 0.17 seconds at 64,013 bytes and 2.05 at
  256,009. Both grow about with the square of the subject.
  C1 lets a mail be 4,194,304 bytes, and nothing holds a
  subject under that. So the first way, as the library gives
  it, would be a reader of F10's kind: in front of the MAC,
  and slow at a stranger's word.
- **The bound the first way needs.** An id of 128 characters
  is 188 bytes of subject as the library writes it, and
  1,811 bytes written 1 character to an encoded word, the
  longest way to spell it. At 2,063 bytes the 2 decoders
  took 0.0003 and 0.0012 seconds. So a subject refused past
  2,048 bytes, before it is decoded, keeps every honest
  spelling and bounds the cost.
- **What the second way costs.** Nothing at the gate. A
  sender that uses the library sets its lines to 998
  characters, and the library then writes a subject with a
  128 character id plain. The runner's own sender,
  `send_mail` in `runner/wire/mailbox.py`, would take that
  setting.

### Closing F11: both ways, as the owner decided

The owner decided both closings (the desk's Q204), and both
were landed together, tests first, by Muse's seat on
2026-11-19.

- **The gate decodes, bounded.** `handle_mail` in
  `runner/ops/mail.py` decodes a subject's encoded words
  after the panic step and the size cap, before the
  dispatcher reads the id off it. A subject past 2,048 bytes
  is never handed to the decoder and is read as written, so
  the decoder a stranger can reach is bounded exactly as
  F13's is. The panic step in front of it still reads the
  subject as written, under its own bound, unchanged.
- **The sender writes plain.** `send_mail` in
  `runner/wire/mailbox.py` builds its message with its lines
  set to 998, so a result for a job with a long id leaves
  under 1 plain subject line, the whole id on it, and the
  runner's own mail never needs the decoder.
- **The tests.** `FindingF11Closed` in
  `runner/tests/test_v4_bindings.py` holds both ways: the
  library's mail runs at every length of id from 1 to 128,
  the longest honest spelling of a 128 character id runs, a
  subject padded past 2,048 bytes is never handed to the
  decoder and runs nothing, and the sender's job and result
  subjects at 78 and 128 characters leave on 1 plain line.
  On the code as it was, 3 of the 4 fail; the bound test
  holds both ways.
- **What moved with the world.** F13's third supposition
  counted the decoder's callers and found 1, the panic
  step's. This closing adds the second its own analysis
  prescribed, at the same bound. The count is now 2, each
  bounded at 2,048, and
  `test_f13_the_decoder_s_callers_are_each_bounded` in
  `runner/tests/test_v4_before_the_mac.py` pins both. The
  as-assembled core measure was re-recorded in the same
  landing, as a core file grew.

## What this pass does not show

- A fuzz tie is reach, not proof. The proofs are the models
  and the conformance suites the property table names.
- The reach count follows calls into functions. A constraint
  kept by a line inside a larger function, as the 4 that
  name `handle_mail` are, is counted by that function.
- The corpus at the doors is the corpus as it stands, 215
  arrivals and 55 payloads. It is not a campaign: nothing
  grows it against the gate. Beside it, the campaign now
  has a gate target of its own, counted in the fuzz
  sections above.
- F10's bound is shown for the bodies tried and argued for
  the rest. The record gives no proof that no other body
  makes the search read more than 16 times its length.
- A size is the entry's own bytes. Where a target's check
  puts a signature or an envelope around an entry first,
  the function reads more bytes than the entry has.
- A seam is the general model's guard, set on or off whole.
  It shows a property rests on that guard being applied.
  The guard's inside is the small model's to prove, and the
  seam's hold on the code is in `v4-general.md`.

## For the next pass

- A search for cost in the readers that run before a MAC.
  F10 came to light through a slow test and not through a
  search, and a reader's cost is a property like any other.
- Size in the campaign. 2 corpus entries are now of 10,000
  bytes or more, both of them the gate target's, and a
  child is still held under every size cap. The mutators
  that grow an input toward a cap have landed in the
  campaign, and the gate target stands at the gate; what
  is left is to grow the other targets' inputs toward the
  sizes where a reader's cost shows.
- The result cap. C3 is the 1 size cap whose default, at
  5,242,880 bytes, no corpus text has been grown to. The
  fitting is held on corpus text at smaller caps.
- Finding F11 is closed, both ways, as the owner decided
  (the desk's Q204). Its record stands above.
- The 3 suppositions `v4-general.md` left stand as written
  there.
