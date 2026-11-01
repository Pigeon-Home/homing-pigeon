# The security model, and the proof testing behind it

Homing Pigeon is a remote code execution tool by design: a signed
message arrives, and code runs on the host. The security model is
everything that stands between those two events — the checks a job
must pass before anything executes, the fences on what a key may
ask for, the ceilings on what a running job and its result can do,
and the rules for what happens when the owner's own configuration
is wrong. This page states that model in one account, then
describes the formal testing program that checks it. The full
records live in `docs/proofs/`; this page is the map, not a second
copy of them.

## The gate

Every job, on every transport, passes one ordered acceptance gate
in the runner's core before anything executes. The order is part
of the model: a check that ran after execution would be no check
at all.

- The raw message is bounded first: a message over
  `max_job_bytes` (default 4 MiB) is refused before any signature
  work. Locally submitted envelopes face their own constant cap of
  256 KiB.
- A signature must verify: HMAC-SHA-384 over the body, under the
  secret the body's key id selects. A key id that names nothing
  the runner holds is refused before any MAC work.
- If the body is an encryption envelope, it uses the one AEAD,
  AES-256-GCM; it must decrypt, and the inner body must verify
  under the same key. Encryption is on by default. A cleartext
  job executes only in a process started with
  `--allow-cleartext`; cleartext is refused by default.
- Where the audience feature is in `enforce` mode, the job's
  claimed audience must equal the configured runner id. In
  `audit` mode a mismatch is recorded; with the feature `off` —
  the fresh-install default — there is no binding to check, and
  the model says so rather than claiming otherwise.
- The script must fit `max_script_bytes` (default 1 MiB, measured
  in UTF-8 bytes), checked after the signature. The body's
  version, type, and job id must match the message's, and the job
  must be fresh: issued inside the accepted age window.
- The signing key's policy must allow the job (below).
- The job id must not already be claimed. Only a handling that
  takes the claim proceeds, and execution is reachable only at
  the end of this order.

A result is fitted to `max_result_bytes` before it is delivered
(default 5 MiB; a configured 0 means unlimited).

## Keys and their fences

The owner holds the default key. Additional named keys each carry
a policy entry that narrows what that key may do: the job kinds
it may run, the recipes and interpreters it may name, a timeout
cap, file and environment constraints, and — sharpest — a pinning
list of exact scripts by SHA-384 digest. Under a pinning policy a
`script_url` job is refused outright, because its content cannot
be checked before download. Where a key directory is configured,
its verdict is taken before the policy is read: a key it refuses
is refused whatever its policy allows. The same fence stands at
the query, board, and version 2 doors, not only at the job's
door.

The upgrade key is the worked example: a named key whose policy
admits one shape only — an execution job carrying the one pinned
staging script, inside a 300-second timeout cap. Every other
shape signed with that key is refused at the policy step.

## Transports: a second gate where there is one

The core is transport-blind; it performs no transport-credential
check of its own. Where a transport has credentials of its own,
they are a gate in front of the signature: a message that has not
passed them is never presented to the core at all, and a message
that has passed them still faces the signature in full.

- **Email has no sender gate, and none is claimed.** The mailbox
  login is the runner's credential to its own mail server; it
  authenticates no sender. Anyone who can route a message into
  the mailbox reaches the signature check. Email stands on the
  signature alone, by design.
- **File** has no credential of its own; who may present a file
  is decided by the operating system's access control on the
  inbox directory, outside the code.
- **NATS** refuses to start without broker credentials unless
  `allow_unauthenticated` is set to literally `true`; with
  credentials configured, the broker enforces them at connect.
- **DTLS** checks the shared secret itself as the handshake key
  before any application message moves — two checks, one secret,
  stated in those words.
- **Queues** checks bearer tokens at the hosted edge, compared by
  hash and failing closed, before anything is enqueued or leased.

A deployment that waives a transport's gate — the NATS waiver, a
broker run without authentication, an inbox opened to every local
principal — does not carry the second-gate property for that
transport, and must not be described as carrying it.

## Ceilings a job cannot raise

A job that has passed the gate may still be a compartmentalised
worker's job, and what it can touch is the owner's decision, not
the job's.

- Whether the job runs inside the sandbox is a function of the
  configured confinement mode and of whether the mechanism works
  on the machine — of nothing else. No field in the job is read
  by that decision. Inside the sandbox, the job's writable set is
  its work directory alone.
- The visible set grows by one bounded rule only: when the
  interpreter a job names resolves outside `/usr`, that
  interpreter's own install prefix is bound read-only, by a
  uniform rule, so the interpreter can run — and every such bind
  is written into the audit record. The job names no path to
  bind.
- The result view a job receives is the narrower of the view it
  requested and the owner's `max_result_view` ceiling. The query
  budget is the smaller of the job's `query_budget` and the
  owner's `max_query_budget`, each defaulting to 8. The redaction
  patterns that scan a result are the runner's built-in set plus
  the owner's extras.
- Job members named `security`, `confinement`, `workspace_root`,
  `protected_paths`, `max_result_view`, or `sandbox` are read
  nowhere in the runner. They are inert text, not requests the
  code contains: job fields can only narrow what a job gets,
  never widen it.

## Once, and only once

Execution is at most once per job, where a job is its id together
with the digest of the job as received; delivery of the result is
at least once, inside the delivery window. Three layers of disk
state carry the guarantee, so a restart by itself neither grants
nor loses an execution: the replay cache turns a duplicate away;
the claim — in-process and on disk, with a stale rule for a dead
holder — keeps two handlings from running the same job; and the
recorded result answers a redelivery that outlives the cache,
only when the digest matches.

The edges are priced, not hidden. A crash between a run and its
result being recorded buys at most one further run. A delivered
record ages out after `output_retention_days` (default 7 days),
and its expiry buys at most one further run of a fresh job under
the id. Outside those windows, replay is answered, never re-run.

## Configuration: refuse or default

The owner's configuration is trusted as a statement of intent,
and Decision 1 governs what happens when a value in it is present
but unusable. The split is by what a wrong value changes.

- A present-but-invalid value that changes who can reach the box,
  what it will execute, or what it protects — ports and bind
  addresses, size caps, key policies, secrets, security modes —
  refuses startup: the runner does not start, and the error names
  the setting.
- Every other present-but-invalid value reads as its documented
  default, and the key is named in the startup warning.
- Live reload follows the same split. A bad default-class value
  is replaced by the default and named in the log. Refuse-class
  keys are not in the live-reload set: a later write changes
  nothing in the running process and takes effect only at the
  next start, where the refusal rule applies.

## The proof testing

The model above is a design account. The proof work — on the
`testing` branch, recorded in `docs/proofs/` — checks it,
property by property, against the code as it stands.

The method is fixed. First, every value the model depends on is
harvested from the code itself into a constraint inventory
(`docs/proofs/constraints.md`), and a pinning test
(`runner/tests/test_proof_constraints.py`) fails if a declared
value in the code drifts from the documented one. Each property
is then stated in plain language precise enough to model
(`docs/proofs/properties.md`), modelled in TLA+, and
machine-checked with the TLC model checker, which searches the
model exhaustively inside its stated bound for a counterexample.
Witness configurations — cases that must be reachable — are
checked alongside each property, so a pass cannot be vacuous.
The model is then reconciled against the real code line by line,
and conformance tests drive the real gate code along the model's
paths.

Six properties are stated and checked:

- **P1, the acceptance gate.** Checked at the first rung, scripts
  of under 50 characters — character count, not lines, because a
  one-liner can be arbitrarily long and obfuscation packs
  characters onto few lines. P1 is a family over the bound,
  P1(B), re-proven at rising rungs: 500, 5,000, 50,000, 500,000
  characters, and finally the production cap itself. The claim
  race — two handlers, one job id — is checked at most once.
- **P2, confinement ceilings.** No job field widens what
  execution may touch or what a result may disclose, checked over
  the full field space, including the bounded interpreter-prefix
  rule stated inside the property.
- **P3, transport gates.** The composition of each transport's
  credential gate with the core signature check, stated per
  transport where the transports genuinely differ.
- **P4, key pinning.** A named key can do only what its policy
  allows, checked over the full policy space — the upgrade key's
  one admitted shape included.
- **P5, replay resistance.** At most one execution per job across
  the cache, the claim, and the record, with the priced windows
  modelled as window events, each buying at most one further run.
- **P6, refuse or default.** The Decision 1 split, checked over
  every combination of class, presence, and moment — startup and
  live reload.

Stage 5, the conformance tests, is in progress: the first tests
drive the real gate — a refused cleartext job does not consume
its id, an unsigned body does not execute, a recorded result is
resent rather than re-run, and a repaired job the key forbids
does not execute. The clause-by-clause family and the mutation
check that proves the family can catch a change are still open.

## Honest limits

- **The cryptography is assumed, not proven.** The model rests on
  one assumption stated once and carried through every property:
  a valid HMAC-SHA-384 signature cannot be forged without the
  shared secret (and, alongside it, that the AES-256-GCM
  construction holds under a key the attacker does not hold, the
  secret has the entropy the startup check demands, the box is
  not already compromised, and the operating system, runtime, and
  hardware do what their own specifications say). The model
  checks what the runner does with a signature that verifies;
  proving the primitives is cryptography's work, not this
  branch's.
- **The findings are on the record, not smoothed over.** Stage 3
  found that the code can execute a job the Oracle repaired — an
  interpreter substituted after the claim — instead of the job
  byte-for-byte as checked; the repaired job is re-run through
  the judge and the key policy before it executes, a conformance
  test now pins that shape on the real path, and the rest of the
  stage 5 family remains the debt that finding is owed. P2
  records the interpreter-prefix bind inside the property itself:
  bounded and audited, but a widening, stated as one. P6 records
  a naming gap: live reload never reads refuse-class keys, so a
  bad refuse-class value written while the runner is up is not
  named in the log, though it changes nothing until the next
  start refuses on it.
- **The scope starts small and rises.** Each checked claim names
  its property, its bound, and its assumptions. The proof scope
  starts at the 50-character rung; it is not yet a claim about
  the whole system, and the sum of the claims is exactly the
  properties checked — nothing more.

## The records

- `docs/proofs/README.md` — the goal, the assumptions, and how
  the work is reviewed.
- `docs/proofs/GOALS.md` — the staged plan and what done means at
  each stage.
- `docs/proofs/properties.md` — the six properties in full, with
  the code's check order and the shape of a counterexample to
  each.
- `docs/proofs/constraints.md` — the constraint inventory, every
  value named with the file and function it was read from.
- `docs/proofs/stage2.md`, `stage3.md`, `stage4-p2.md` through
  `stage4-p6.md`, `stage5.md` — the stage records: the checks,
  the state counts, the witnesses, and the findings.
