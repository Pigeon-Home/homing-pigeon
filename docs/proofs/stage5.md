# Stage 5 — conformance: the clauses driven against the real code

Stage 5 is done on the terms `GOALS.md` sets. Every clause of
P1 through P6 names at least one test that drives the real
code — not the model — the family passes on this branch, and
the per-property mutation checks below were each caught by
the family in a scratch copy of the tree. Nothing in the
runner's behaviour changed in this stage; the one divergence
the work turned up is recorded as finding F1, with the test
that exhibits it.

The stage landed in two passes, and this record covers both.
The first pass named a test for every clause, leaning on the
stage 1 pinning file for the later properties and adding
gate-level tests for P1. The second pass added a behavioural
family in five sibling files — plus P1's clause classes in the
main conformance file — driving the clauses where they
actually live: the delivered result, the transport edges, the
job's door under a key policy, the replay layers over one
shared runner home, and the real startup path. Where the
first pass's pins read code at a site (part of its P3), the
second pass drives that site's behaviour instead; both sets
of tests are in the tree, and everything below was re-run
end to end on the final tree before this record was written.

## The family

| File | Tests | What it drives |
|---|---|---|
| `runner/tests/test_proof_constraints.py` | 67 | The stage 1 pinning file: values, readers, and fences at the function level |
| `runner/tests/test_proof_conformance.py` | 64 | P1's nine clauses and check order through `handle_mail`; the record resend; the NATS start |
| `runner/tests/test_proof_conformance_p2.py` | 27 | P2: the result view and query answers read out of delivered results; the confinement chain and the sandbox builder; the watched set on a real tree |
| `runner/tests/test_proof_conformance_p3.py` | 28 | P3: each transport at its own edge, and the file pipe end to end through the channel and the real core |
| `runner/tests/test_proof_conformance_p4.py` | 38 | P4: the key-policy step at the job's door, the other doors, and the repaired job's re-judgment |
| `runner/tests/test_proof_conformance_p5.py` | 12 | P5: the claim, the cache, the claim file, and the record, over one shared runner home |
| `runner/tests/test_proof_conformance_p6.py` | 13 | P6: Decision 1 through the real `main()` startup and the real reload |

249 proof tests in all. A few P1 refusal steps also have
older tests in `runner/tests/test_coverage_floor.py`; they
are named in the first pass's tables rather than copied.

### P1, the gate

The clause classes in `test_proof_conformance.py` drive each
of the nine clauses at and either side of its boundary:
`P1RawSizeTest` (raw size, at the cap and one byte over, a
cap of 0 as unlimited), `P1SignatureTest` (a bad signature
refused with the id unconsumed; an unknown key id; a null key
id; a body signed under one key and named as another; the
fingerprint name selecting the default key; a named
additional key), `P1EnvelopeTest` (a tampered envelope
refused as a bad envelope; an inner key id that differs from
the outer; cleartext executing only under the process flag,
with no config key able to turn it on), `P1AudienceTest`
(enforce refusing a mismatch and admitting a match; audit
admitting with a `would_deny` entry on the record; off
admitting; enforce with no runner id binding nothing — the
precondition of stage 3's F4), `P1ScriptBoundTest` (the
script cap in bytes, a multi-byte character counting as its
bytes, 0 as unlimited), `P1IdentityTest` (version, type, and
subject/body identity mismatches), `P1FreshnessTest` (stale,
past the future bound, just inside it, and naive, broken,
and missing timestamps), `P1CheckOrderTest` (eight adjacent
pairs of the check order, each shown by a job that fails
both steps and is refused for the earlier one; a job carrying
a lone surrogate refused at the signature and never
executed), and `P1HandlingShapeTest` (the panic word stopping
everything before the signature; a sensor alert leaving
through the gate to its own ingest and never executing; a
dry run verifying and recording nothing; the same delivery
twice executing once). The claim and record clauses are
driven at length in the P5 file.

### P2, confinement ceilings

`ResultViewCeilingTest` reads the result a real
`handle_mail` run commits and delivers, decrypted: the
owner's ceiling caps the job's ask (a `full` ask under a
`summary` ceiling arrives as a summary with byte counts and
no output), the job may narrow below the ceiling, a
ceiling-shaped member of the job itself widens nothing, and
an unrecognised ask reads as the documented default.
`RedactionTest`: the built-in patterns apply under the
redacted view, a pattern named by the job does not, and a
pattern named by the owner does. `QueryCeilingTest`: grep
answers under the full view and is refused `policy` under
the summary and attested views; tail lines under the
redacted view pass through the patterns; the budget is the
smaller of the job's ask and the owner's cap, both directions
driven; and a query refused on policy still spends its unit,
shown at the answering step itself. `ConfinementChainTest`
drives the runner's own `_confinement_argv`: off runs
normally; audit runs normally and records the `would_sandbox`
decision; enforce with no sandbox available falls back and
records the fallback; enforce with one wraps the job and
records `sandboxed`. `SandboxShapeTest` drives the builder:
the workdir is the only read-write bind; an interpreter
outside `/usr` brings its install prefix read-only, with the
bind named in the caller's notes; the prefix floor is pinned
where it holds — and exhibited where it does not (finding F1
below). `WatchedSetTest` runs the snapshot and verdict
functions over a real temp tree: a change outside is a
violation, no change is none, the workspace itself is not
watched, and a change under a protected path is named while
one outside it is not. The runner-computed attestation
(clause 8) is named by the pinning file's
`test_c17_confined_attestation_reports_the_runners_value`;
the attested view's query refusal above is its behavioural
half.

### P3, the transport gate

`FileChainTest` runs the whole chain: a watched inbox, the
file pipe, the channel, the real core through
`process_transport_message`, and back out to the watched
outbox. A valid envelope executes and its result lands as
`<job_id>.result.txt`; an envelope signed under the wrong key
is delivered the same way, is consumed, and never executes —
the pipe is a carrier, the core's gate is the gate (clauses
1–3). `FileRefusalTest` is the file pipe's own edge (clause
5): a symlink, an oversize file, and a malformed envelope are
each refused unread, with the reason left in
`done/<name>.refused.txt`. `NatsGateTest` and
`NatsBrokerTest` (clauses 6 and 9): the pipe refuses to
start with no broker credentials, a waiver written as the
string `"true"` does not waive, the literal `True` does, a
token is credentials, and credentials embedded in the URL
count; against a fake broker that answers the CONNECT with
`-ERR`, the client raises and nothing is delivered, and
against one that answers `PONG` the same client connects —
the refusal is the broker's verdict, not a dead socket.
`DtlsStartupTest`, `DtlsDirectoryLookupTest`, and
`DtlsPipeSocketTest` (clause 7): the extension's `main`
returns 2 with no secret handed over and 2 with a secret
under the entropy floor, and the floor names a weak
additional secret; the directory-wrapped PSK lookup answers
the secret with no directory configured and nothing when
the directory refuses the key or cannot be read; and a real
pipe on a real UDP socket establishes a session under the
right PSK and carries a job into the channel, while under a
wrong PSK no session ever establishes and no job reaches the
channel, and a directory refusal blocks even the right PSK.
`QueuesClientTest`, `QueuesStartupTest`, and
`QueuesWorkerTest` (clause 8, and the gate order of clauses
1–3 at the hosted edge): the client sends its bearer token
on the pull and a 401 is a failed pull, not an empty one;
the extension returns 2 with no URL and 2 with no runner
token; and the hosted Worker itself, driven under node with
a recording stub behind its tenant queue, answers 401 with
no bearer and 401 with the wrong SI token (the queue never
called), 400 for an unsigned body and 403 for a bad
signature under a good token, forwards a valid signed job to
`/enqueue` naming the job id, takes the runner token — not
the SI's — for the pull, and refuses every bearer for a
tenant with no stored SI hash: the edge fails closed.
`EmailGateTest` (clause 4): a job from an unrelated sender
address with a valid signature executes — the address is
not a gate, and the property claims none — and a mailbox
login the server rejects raises at connect, which is where
that transport's credential is enforced.

### P4, the key policy

`UpgradeKeyAtTheDoorTest` drives the step where the
property lives, through `handle_mail` under the upgrade
key's arrangement (C22): the one permitted shape executes;
any other script, a script URL alone, a script URL beside
the pinned script, and a missing script are refused; every
other kind is refused; a timeout at the cap executes, one
over it is refused, and the configured default is measured
against the cap. `DefaultDenyTest` (clause 3): an entry-less
key runs without the flag and is refused with it, and the
default key is exempt under both its names.
`PolicyIsTheKeysNotTheNamesTest` (clauses 1 and 4): the
fingerprint name carries the same fence as the key's given
name, both ways. `DirectoryFirstTest` (clause 2): a
compromised key is refused though its policy allows it, a
key with no directory entry is refused, and an unreadable
directory refuses the key. `DoorsTest` (clause 9): the same
entry binds the query, board, and version 2 doors; the
cancel door is exempt from the kinds list and not from the
directory or the deny flag. `RecipesAndInterpretersTest`
(clause 6) drives the step itself for the recipe fence and
the effective-interpreter rule. `ModeGatedConstraintsTest`
(clause 11): under one policy, an unlisted file is refused
with `policy_files` enforcing, recorded and run under audit,
and not computed under off; a dangerous env name and an
over-cap argument count are refused under their own modes.
`RepairedJobRejudgedTest` is clause 10 and closes the
conformance debt stage 3's finding F2 named: with the
opinion set to repair, a job naming a missing interpreter
executes after repair carrying the platform interpreter and
its script byte-for-byte as received; under a pinning policy
the same holds, the pinned script unchanged; and where the
policy allows the missing interpreter but not the platform
one, the repaired job is refused at the re-judgment and
nothing executes — the repair is re-checked through the key
policy before anything runs, and it never touches the
script. `MalformedPolicyTest` (clause 12) covers the
builder validations the pinning file does not: a non-object
entry, a sub-one timeout, kinds as a bare string,
interpreters as bare strings, an args pattern that does not
compile, and file URLs as a non-boolean.

### P5, replay

`ReplayDoorTest` drives the layers in the order
`handle_mail` meets them, over one shared runner home.
Clause 1 and 2: the same delivery twice over one seen set
executes once, sends nothing the second time, and marks the
copy seen; a fresh seen set reads the disk cache and skips
without the record being consulted (the lookup is patched
to raise if called). Clause 3, the record half: with the
cache deleted, the recorded result is resent byte-for-byte
and nothing runs. Clause 6: a different job under the same
id, after the same cache loss, is not answered from the
first job's record and runs on its own. Clauses 3 and 4,
the claim half: a claim file held by a live process defers
the job and leaves the message unseen — a crash there can
be stolen on a later poll — and a key already in the
in-flight set is skipped and marked; the dead-holder steal
itself is named by the pinning file's
`test_c24_disk_claim_live_dead_and_unreadable`. Clause 11:
a seen set rebuilt from `seen.json` by `load_seen` — the
restart shape — skips the duplicate. Clause 7, priced: with
the stash made to report failure, the first delivery runs
the job and commits nothing, the second runs it once more
and commits, and a third is skipped — the crash window buys
exactly one further run. `RecordStoreTest` drives the store
itself: clauses 5 and 10 — a failed delivery leaves the
record in the outbox with its attempt count and error
updated, a working sender then delivers it and the record
moves to the sent store, and the record answers only the
job whose digest it carries. Clause 9, priced: a record
past its retention is pruned (a zero retention prunes
nothing), and with it gone the lookup answers nothing.

### P6, the configuration split

`StartupTest` drives the real `main()` over a real config
file, returning through `--audit-report`, which exits right
after the configuration gauntlet: an absent key is not
named and startup proceeds (clause 1); a usable value is not
named (clause 2); an unusable default-class value is named
in the startup line and startup proceeds on the default
(clause 3); a refuse-class port and a refuse-class size cap
each stop startup at 2 with the setting named in the error
(clause 4); and the defaulted line is emitted before the
port refusal in the gauntlet's real order, so the naming
happens even when startup then refuses. `ReloadTest`
drives the real reload over a real file: an unusable hot
value is replaced by its default and named (clause 5, hot
half); a usable hot value applies as written; an unusable
value for a non-hot default-class key is replaced by the
documented default and named (clause 5, the rest of the
class); refuse-class values written live — a size cap and a
port — change nothing in the running binding (clause 6); a
pinned key is left alone; an unchanged file is not
re-applied; and an unreadable file changes nothing and does
not advance the state marker, so the fixed file applies on
the next cycle (clause 7). One sub-case is deliberately not
pinned: a boolean written live for a hot key, where stage
4's P6 record (finding F2 there) shows the code reading it
as 1 through `int(value)` where the property says the
default, named. That divergence is on record; this family
does not assert either reading of it.

## The mutation check

For each property, a deliberate one-line change was made in
a scratch copy of the tree, the property's tests were run,
and the file was restored from the pristine tree. Twelve
shapes were run in ten runs — the P3 and P5 shapes from the
two passes are the same line, so one run covers both. Every
run exited 1: at least one test failed, every time. A family
that stayed green would have been decoration. The scratch
copies were not committed.

| # | Property | The one line | Caught by |
|---|---|---|---|
| M1 | P1 | `runner/ops/mail.py`: the freshness future bound `-300` widened to `-300000` | `P1FreshnessTest::test_future_beyond_the_bound_refused` |
| M2 | P2 | `runner/ops/policy.py`: the view comparison `<=` flipped to `>=` | three `ResultViewCeilingTest` tests |
| M3 | P3 | `runner/transport_extensions/nats/__main__.py`: the missing-credential refusal replaced by `if False:` | `NatsGateTest` (both refusal tests) and `GateConformanceTest::test_nats_without_credentials_refuses_to_start` |
| M4 | P4 | `runner/wire/verify.py`: the pinning comparison `digest not in allow` inverted to `digest in allow` | three `UpgradeKeyAtTheDoorTest` tests |
| M5 | P5 | `runner/runner.py`: the record's digest comparison in `load_sent_result` replaced by `if False:` | `RecordStoreTest::test_the_record_answers_only_the_same_job` |
| M6 | P6 | `runner/ops/attest.py`: the reload fallback keeps the written value (`cfg.get(key)`) instead of the hot default | `ReloadTest::test_an_unusable_hot_value_reads_as_the_default_named` |
| G1 | P1 | `runner/ops/mail.py`: the cleartext refusal skipped (`if not job_was_encrypted:` → `if False:`) | four tests, including `test_cleartext_does_not_execute_or_consume_the_id` |
| G2 | P2 | `runner/ops/policy.py`: the ceiling ignored, the job's view always wins | `test_c17_a_job_cannot_widen_past_the_ceiling` and three `ResultViewCeilingTest` tests |
| G4 | P4 | `runner/wire/verify.py`: the kinds fence skipped | `test_c14_kinds_fence_refuses_every_other_kind` and `UpgradeKeyAtTheDoorTest::test_every_other_kind_is_refused` |
| G6 | P6 | `runner/guard/defaulted.py`: a boolean accepted as a number in `_parse` | `test_a_bool_is_not_a_number_and_an_absent_key_is_not_named` |

The first pass's own runs of its six shapes (its P3 and P5
shapes are M3 and M5 here) are consistent with these: run
again on the final tree, every shape was caught again.

## Findings

- **F1. The interpreter-prefix floor is not enforced on
  the parent fallback.** Stage 4's P2 finding F1 states the
  one job-influenced sandbox addition with a bound: the
  interpreter's install prefix, "never shallower than two
  components". That bound is enforced on the `bin`
  grandparent path of `_install_prefix`
  (`runner/guard/sandbox.py`), whose grandparent is checked
  for depth — and not on its parent fallback, which returns
  the parent directory unchecked. Measured on the real
  builder: an interpreter resolved at `/opt/x64/bin/python3`
  binds `/opt/x64`, and `/snap/bin/tool` binds `/snap/bin`,
  as stated; but an interpreter resolved directly in the
  filesystem root binds the whole root read-only
  (`interpreter_binds("/tool")` returns `[("/", "/")]`),
  and one in a top-level directory binds that whole tree
  (`"/x/tool"` → `[("/x", "/x")]`).
  `SandboxShapeTest::test_a_root_level_interpreter_binds_the_root`
  exhibits the current behaviour by name so it cannot drift
  silently. Classification: a widening past the bound F1
  discloses, reachable only by an interpreter that already
  exists at such a path on the host and resolves there; the
  mitigations F1 already records — the interpreter must
  exist and resolve, a key policy can pin the interpreters a
  key may name, and every bind is written to the audit
  record — still hold. What closes it is either the same
  depth check on the fallback, or F1's sentence amended to
  carry the exception. No production code changed in this
  stage; the choice belongs with the property's owner.
- **The P5 observation, now pinned as behaviour.** Stage
  4's P5 record observed that with the opinion module
  unloaded, `load_sent_result` skips its digest comparison
  and answers a different job under the same key.
  `RecordStoreTest::test_the_record_check_without_the_opinion_module`
  exhibits exactly that, by name. The module loads
  unconditionally in the shipped runner, and at-most-once is
  untouched either way — the claim, not this lookup, is what
  stops a second run.
- **Limits, stated plainly.** P5's clause 10 is driven at
  the record store with real failing and working senders,
  not over a live transport; no test here opens a mailbox
  and waits. The DTLS drives are loopback, and the queues
  Worker drives stub the tenant queue behind the Worker's
  own `fetch` — the Worker is the real code; its Durable
  Object has its own suite. The content-independence
  challenge in `thinking.md` (every script at a bound,
  generated from the atomic operations of the shell) remains
  open: this stage drives shapes and boundaries, not that
  enumeration.

## Verification

On the final tree: `test_proof_constraints.py` 67,
`test_proof_conformance.py` 64, and the sibling files 27,
28, 38, 12, and 13 — 249 tests, all passing under both
pytest and the suite's own unittest discovery. The mutation
runs above were made in a scratch copy (`cp` of the tree,
`.git` excluded), one file changed at a time and restored
after each run; the working tree carried no mutation at any
commit.
