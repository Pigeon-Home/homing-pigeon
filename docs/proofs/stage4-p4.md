# Stage 4, third property — P4, checked

This is the record of P4's pass through stage 4's cycle: the
full statement, the model, the check, and what the check does
not say. P4 is the third of stage 4's five properties; P5 and
P6 remain placeholders in `properties.md`, each to be taken up
in turn. The statement is in `properties.md` (P4, twelve
clauses); the constraints it uses are C14 from stage 1 and
C21 and C22, harvested from the code for this stage, in
`constraints.md`; the model is `KeyPolicy.tla` in this
directory.

The code read for this stage is the code at the `testing`
branch tip this stage started from, which is the code at
`6d6288c5` for every file named below.

## The property, in one paragraph

A key with a policy entry can do only what the entry allows.
The fences — kinds, recipes, interpreters, timeout, and the
script pinning — are applied at one step of the gate, after
the signature has verified, by the key that verified, under
an entry read by the key's value rather than by the name it
was presented under; and the key directory's refusal stands
in front of the step at every door. The upgrade key is the
arrangement that gives the property its edge: an additional
secret fenced to execution only, one pinned script by
SHA-384, and a 300-second cap, so the key that stages an
upgrade can run that one staging script and nothing else.

## Where the policy is enforced — the code sites

**Construction.** `build_key_policies`
(`runner/wire/verify.py`, line 485) builds the policy map
from `key_policies` and validates as it builds: every field
it carries is shape-checked (a non-object entry, an empty or
mistyped list, a boolean or sub-1 `max_timeout_sec`, an
uncompilable or backtracking `args_pattern` are startup
configuration errors), the pinning list's entries are
lowercased (line 553), and a key entered under two of its
names is refused (lines 630 to 640: the policy is a property
of the key, so the map must not make it depend on the name).
The builder runs at startup (`runner/ops/main.py`, line 140,
where a `RuntimeError` returns exit 2 — the refuse path) and
per poll cycle
(`runner/ops/poll.py`, line 41), and the map it returns is
what the doors read. Observation F1 below records the one
silence in this construction.

**The step, and its order.** `check_key_policy`
(`runner/wire/verify.py`, line 878) computes the verdict in a
fixed order:

0. **The key directory first.** Lines 904 to 910 load the
   directory and take its verdict (`key_directory_verdict`,
   line 762) before any policy is read: a refused key is
   refused whatever its policy says, and a directory that
   cannot be loaded returns a refusal, not an admission
   (C21).
1. **The entry.** `policy_for` (line 380) finds the key's
   entry under any of its names. No entry: the step returns
   approval, unless `key_policies_default_deny` is set and
   the key is not the owner's — the owner test is `""` among
   the key's names, read by value, so the default key is
   exempt under its fingerprint and its stored names exactly
   as under the empty id.
2. **Kinds** (lines 924 to 929): where `allowed_kinds` is
   present, the job's `kind` must be listed — a missing kind
   is not listed, and is refused.
3. **Recipes** (lines 930 to 936): for `recipe` and `change`
   jobs, the recipe must be in `allowed_recipes` where
   present.
4. **Interpreters** (lines 938 to 944): the effective
   interpreter — the job's own, else the configured default,
   else the platform's — must exactly match a listed list.
   Recipe and change jobs are skipped: their interpreter is
   the owner's.
5. **Timeout** (lines 945 to 962): the effective timeout —
   the job's `timeout_sec`, else the documented default of
   300 — must not exceed `max_timeout_sec` where present.
6. **Script pinning** (lines 963 to 982): where
   `allowed_script_sha384` is present and the kind is `exec`,
   a `script_url` (present at all, alone or beside an inline
   script) is refused, a missing or non-string script is
   refused, and the inline script's SHA-384 — over its UTF-8
   bytes — must be in the list. The branch does not run for
   other kinds.

Nothing in the step is mode-gated: these fences refuse in
every posture of the security modes. What is mode-gated sits
behind the step (the surround, below).

**The job's door, and the doors around it.** At the job's
door the step runs in `handle_mail` (`runner/ops/mail.py`,
line 178) — step 10 of P1's check order, after signature
verification (`verify_body_keyed` selected the key and
refused unknown ids before any MAC, so the step always
speaks for the key whose secret verified) and after
freshness; a violation is a rejection with reason
`key policy: <reason>` and an `auth_rejection` event. It
runs again on the Oracle-repaired job (line 382) before that
job can execute: the repair rewrites the interpreter only,
and the re-judged job faces the pinning branch with the
script it arrived with. The local-signals path runs it too
(`runner/runner.py`, line 3990), on the sensor-alert jobs
that path admits, so a pinning key's alert from that door
faces the kinds fence. The other doors apply the same entry
through `check_door_policy` (`runner/wire/verify.py`,
line 826 — directory verdict at lines 854 to 858, then the
deny flag, then the kinds list read as a door list): the
query door (`runner/ops/queries.py`, line 113), the board
door (`runner/ops/startup.py`, line 169), the version 2 door
(`runner/ops/handlers.py`, line 200), and the cancel door
(`runner/ops/cancel.py`, line 194), which is exempt from the
kinds list and from nothing else. The DTLS extension's PSK
lookup applies the directory verdict (`directory_lookup`),
so a directory-refused key opens no session.

**The recorded negative case, traced.** The live test of
this machinery is the clock job signed with the upgrade key,
refused with the reason the sending guide records (C22). Its
path is the one above: the signature verifies under the
upgrade secret; freshness passes; at line 178 the kinds
fence passes (`exec` is the one listed kind); the pinning
branch computes the clock script's digest, finds it absent
from the one-entry list, and the step returns "script is not
in this key's allowlist". No other step in the gate could
have produced that refusal, and no step after it ran.

**The mode-gated surround.** Behind the step,
`check_policy_constraints` (`runner/wire/verify.py`,
line 1022) computes the entry's env, file, and argument
findings — including the pinned-script rules (a pinned
script whose env or staged files are not explicitly allowed
is a finding) and the dangerous-env rule (a subverting env
name is a finding for a key with an entry even when listed
in `allowed_env`, unless the entry sets
`allow_dangerous_env` to boolean `true`) — and
`handle_mail` (lines 186 to 218) puts each finding through
`sec_decide` under `policy_env`, `policy_files`, and
`policy_args`: `enforce` refuses, `audit` records and runs,
and with every mode `off` the findings are not computed at
all. Clause 11 of the statement carries this in the open:
the upgrade arrangement's `allowed_files` fence binds
exactly when `policy_files` is not `off`. The fences the
model checks are the unconditional ones, which are the ones
the arrangement's weight rests on — above all the digest.

## The model

`KeyPolicy.tla` is a single-decision model, in the shape
`Confine.tla` and `TransGate.tla` set: the initial state
picks an attempt record and a deployment record; one step
computes the verdict exactly as `check_key_policy` computes
it; the invariants state the claim in closed form over that
verdict.

The attempt record carries the key (the owner's, the upgrade
key, or a second additional key — the machinery is one code
path for every additional key, and the claim is not stated
about one string), the job's shape (the four execution shapes
the pinning branch distinguishes — pinned digest, any other
digest, a `script_url`, no usable inline script — plus ping,
sensor_alert, recipe, and any other kind), and the three
per-field outcomes the remaining fences read (interpreter
listed, timeout within cap, recipe listed), each read only
on the branch the code reads it on. The deployment record
carries the policy as the builder builds it: whether an
entry governs the additional keys at all, and for each fence
whether the entry carries it — an absent fence constrains
nothing — plus the default-deny flag. The upgrade
arrangement is one point of that space (entry, kinds, pin,
and timeout cap present), not the space itself.

The counts multiply out and match the checker's own count,
which is the cross-check that the space searched is the space
described: 192 attempts (3 keys × 8 shapes × 2 × 2 × 2) times
128 deployments (2 entries × 2 × 2 × 2 × 2 × 2 fences × 2
deny flags) is 24,576 initial states, exactly the number TLC
reports computing.

## What was checked

TLC 2.19 (the `v1.7.4` tools jar) on Java 21, the same
tooling `stage2.md`, `stage4-p2.md`, and `stage4-p3.md`
record. Each run is exhaustive. Trace output TLC writes
beside the model (`*_TTrace_*`, `states/`) is run debris and
is removed, not committed.

| Configuration | File | Invariants | Result | Generated | Distinct |
|---|---|---|---|---:|---:|
| Full policy space | `KeyPolicy.cfg` | `P4Inv`, `PinBinds`, `PolicyExact` | holds | 73,728 | 49,152 |
| Pinned-shape witness | `KeyWitnessPinned.cfg` | `PinnedNeverAccepted` | fails, as expected | 34,057 | 34,057 |
| Owner-key witness | `KeyWitnessDefault.cfg` | `DefaultNeverRuns` | fails, as expected | 26,625 | 26,625 |

The depth of the policy search is 2: the initial records and
the decided verdict. The fingerprint collision estimate TLC
printed for the main run was 6.5E-11 optimistic, the ordinary
bound for a run of this size. The witness runs stop at their
counterexamples, so their generated counts are the states
searched up to the exhibited handling.

`P4Inv` is the security claim over the whole space: a job
accepted under a governing entry passed every fence that
entry carries. `PinBinds` is the pinning core isolated: under
a pinning entry, an accepted execution job is the pinned
shape — no other digest, no `script_url`, no missing script.
`PolicyExact` is the fidelity half: the verdict is exactly
the rule, not merely bounded by it — a step that refused
everything would satisfy the first two and fail this one.

To re-run from a bare machine: install a Java runtime
(Java 17 or later; `apt install openjdk-21-jre-headless` on
this distribution), fetch the TLA+ tools jar for `v1.7.4`
(`tla2tools.jar` from the tlaplus project's release of that
tag) into a tools directory, and from `docs/proofs/` run
`java -cp <tools>/tla2tools.jar tlc2.TLC -config <file>.cfg
KeyPolicy.tla` for each of the three configuration files.

## The two counterexamples that are supposed to exist

`KeyWitnessPinned.cfg` checks `PinnedNeverAccepted` — the
claim that the pinned key's one permitted shape is never
accepted. TLC's counterexample is the upgrade key under its
recorded arrangement (entry, kinds, pin, and timeout cap
present) carrying the pinned script, its timeout within the
cap: the verdict is accepted. The fence has a gate, and the
gate is exactly the pinned script — a model that refused
everything would have satisfied `P4Inv` and shown nothing.

`KeyWitnessDefault.cfg` checks `DefaultNeverRuns` — the
claim that the owner's key never runs an ordinary job in a
pinned deployment. TLC's counterexample is the default key
running an unpinned execution script while the additional
keys' entry carries every fence: the verdict is accepted,
and the entry did not speak to it. One key's fence fences
that key; the owner's key is bound by the owner's own entry
or by none, and the deny flag never reaches it.

## Finding

No path was found by which a job signed with a
policy-restricted key executes outside the policy the builder
built: the digest is computed over the verified job's own
script member; the kinds fence is read for every kind, so
the pinning branch's exec-only scope leaves no kind
unfenced where `allowed_kinds` is present; the entry is
resolved by the key's value under any of its names, and the
two-names configuration is refused at build; a directory
that cannot be loaded and a policy map of the wrong shape
return refusals, not admissions; and the one repair path
re-judges the repaired job through the same step. The
behaviour pins in `runner/tests/test_proof_constraints.py`
(stage 4's additions) hold each of these against the real
functions.

One construction-side observation is recorded, in the open:

- **F1. The policy builder carries only the fields it knows,
  and says nothing about the rest.** `build_key_policies`
  copies the fields it recognises into the built entry; a
  field name it does not recognise — above all a misspelled
  fence, such as the pinning field under a near-miss name —
  is absent from the built policy, with no error and no
  warning. The step then enforces the built policy exactly,
  and the built policy is narrower than the entry as written:
  a key the owner meant to pin can be left fenced by kinds
  alone. Classification: not a counterexample to P4 as
  stated, because the property speaks about the policy the
  runner holds, and the runner holds the built one; the gap
  is between the entry as written and the policy as built,
  and it is recorded here because it sits exactly on the
  fence this property exists to check. The startup warning
  the runner does have covers the neighbouring case — a key
  with no entry at all is named at startup
  (`unrestricted_extra_keys`) — but an entry whose fields
  were partly dropped is not named anywhere. No code was
  changed in this pass.

## What this does not say

- Acceptance in this model is the policy step's verdict.
  Whether the job then executes is P1: the signature,
  freshness, and the caps stand in front of this step, the
  claim and the record behind it. The properties compose by
  position, as P3 composes with P1.
- The env, file, and argument surround is mode-gated
  (clause 11), and the model does not carry it: its fences
  are the unconditional ones. Under `audit`, a pinned script
  carrying a subverting env name is recorded and runs; under
  `off`, the findings are not computed. The upgrade
  arrangement's files fence therefore binds exactly when
  `policy_files` is not `off` — a deployment that wants the
  two staged names enforced must set the mode, and the
  statement says so rather than claiming the arrangement's
  whole shape unconditionally. The digest fence, which is
  what keeps the key to the one script, binds in every
  posture.
- A pinning entry without `allowed_kinds` fences scripts and
  nothing else: a ping from such a key runs, governed by
  nothing, exactly as PROTOCOL.md section 14.1 describes
  (a ping has no script and kind governance is the kinds
  field's). The sharp claim for the upgrade key rests on its
  entry carrying both fields, as C22 records; the model's
  space includes the pin-only entries, and `PinBinds` is
  stated over execution shapes for precisely this reason.
- The owner's own entry — a policy written for the default
  key under the empty id — is real, is honoured by the same
  step, and is pinned behaviourally in the test. It is not in
  the model's space: the model's default key stands for the
  owner against other keys' entries and against the deny
  flag, which is where a name-confusion counterexample would
  live. A deployment that fences its owner key is a further
  point of the same rule, not a different rule.
- The key directory's verdict is a constant across this
  model's space, not a variable: it stands in front of the
  step (clause 2), it is pinned behaviourally in the test,
  and its own states and windows are the directory's surface,
  not the policy's. A model of the directory would vary the
  state, the entry's window, and the name presented; nothing
  in P4 turns on which refusal the directory returns, only
  that it returns one first.
- Script identity is pinned-or-not. The model does not
  evaluate SHA-384; that a digest cannot be produced for a
  script the attacker does not hold byte-for-byte is the
  standing cryptographic assumption (`readme.md`), and two
  scripts with one digest would be one shape here and a
  break of that assumption, not of this step.
- The effective interpreter and the effective timeout are
  inputs to the model, as bits. How they are computed — the
  job's own value, else the configured default, else the
  platform's or the documented 300 — is the code's, is stated
  in clauses 6 and 7, and is exercised against the real
  function in the pinning test; the model checks what the
  step does with the values, not how they were derived.
- Cancellation is not a shape in the model. A cancel executes
  nothing; its door is exempt from the kinds list by design
  and subject to the directory and the deny flag, which is
  stated in clause 9 and pinned in the test.
