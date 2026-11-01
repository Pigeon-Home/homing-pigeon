# Properties

This file states the properties the proof work sets out to check.
P1 is stated in full, precisely enough to model, and P2, P3,
P4, P5, and P6 are now stated in full as well (stage 4).

Constraint identifiers (C1, C2, and so on) refer to
`constraints.md`, where every value is harvested from the code at
commit `6d6288c5`.

## Actors

- **Sender.** Any party who can place a message in front of the
  runner: an email sender, a file dropped in a transport inbox, a
  broker publisher. The sender is untrusted. The sender's address
  is logged for audit and is never trusted; any sender may submit,
  and only the checks below authorize anything.
- **Attacker.** A sender who holds no shared secret, or who holds
  one additional key's secret but not the owner's, and who can
  submit messages of any shape, replay recorded messages, reorder
  deliveries, and observe any traffic the transport exposes. The
  attacker cannot forge an HMAC-SHA-384 signature under a secret
  they do not hold, and cannot read or alter an AES-256-GCM
  envelope under such a secret (the assumptions in `readme.md`).
- **Runner.** The process on the host that polls for jobs, applies
  the gate, executes what passes, and signs and delivers results.
  The runner is trusted to run its own code; the question every
  property asks is what that code guarantees.
- **Key.** A shared secret in the runner's secret map, named by
  the empty string (the default, owner key), by a configured name,
  or by its `k-` fingerprint (C7). A key's policy entry (C14) can
  narrow what that key may do. Holding a key authorizes exactly
  what the gate and that key's policy allow — no more.
- **Transport.** The pipe a message arrives on. A transport is
  untrusted as a carrier, and where it has credentials of its own
  they form a first gate in front of the signature (C16, P3).
- **Oracle.** The runner's reviewer. It reads a job before
  execution and attaches notes. It is advisory by construction:
  it never blocks a job, and no property in this file depends on
  it. A property that needed the Oracle to be right would not be
  a property of the gate.
- **Configuration.** The owner's `config.json`, loaded once at
  startup, plus the process's command-line flags. Configuration
  is trusted as the owner's statement of intent, and Decision 1
  governs what happens when a value in it is present but unusable
  (P6).

## Terms, stated once

- **Execution** means the runner starts the job's script (or
  performs the job's kind) on the host. Building a result,
  resending a stashed result, and logging a rejection are not
  execution.
- **Character count** of a script means the number of characters
  in its text (Python `len(script)` on the decoded string). The
  production script cap measures UTF-8 bytes instead (C2); both
  measures are named wherever they are used.
- **The starting bound** for P1's first model is a script
  character count under 50 — 49 or fewer. The bound limits the
  model's scope, not the runner: the runner's behaviour at
  production sizes is the same code path, and raising the bound
  is a planned stage, not a change to the runner. P1 is stated
  as a family over this bound — P1(B), below — so each raise is
  the same property re-stated at a larger bound.

## P1. The acceptance gate

### Statement

For every message handling in the mail path, if the runner
executes a job, then every one of the following held, in the
order the next section records, during that handling:

1. The raw message was within `max_job_bytes` (C1), or the cap
   was set to 0 (unlimited) in the loaded configuration.
2. A signature verified: HMAC-SHA-384 over the message body,
   under the secret the body's key id selects (C5), with key
   selection refusing any key id that is not an absent id, the
   empty string, a configured name, or that key's fingerprint
   (C7).
3. If the body was an encryption envelope, it used the one AEAD
   (C9), it decrypted, and the inner body verified under the same
   key with the same key id. If the body was not encrypted, the
   runner process was started with `--allow-cleartext`; a
   signature-valid cleartext job in a process without that flag
   MUST NOT execute (C8).
4. The audience check passed (C10): where the feature is in
   `enforce` mode, the body's claimed audience equals the
   configured `runner_id`; where it is in `audit` mode, a mismatch
   was recorded and the property makes its claim only in the
   weaker form stated below; where it is `off`, this clause is
   vacuous and the property says so.
5. The script was within `max_script_bytes` in UTF-8 bytes (C2),
   or that cap was 0.
6. The body's `v` was the integer 1, its `type` was `job`, and
   its `job_id` equalled the subject's job id (C13).
7. The job was fresh: `issued_at` parsed, carried a timezone, and
   sat inside the age window (C12).
8. The signing key's policy allowed the job (C14), and where the
   key carries environment, file, or argument constraints and
   those features are in `enforce` mode, the job satisfied them
   (C11).
9. The job id was not already claimed: not in the seen set, not
   in flight in this process, and not already owned on disk —
   except that a job whose result is already on record is
   answered from the record and not executed again (C15).

In short form, the property the whole project rests on:

> No job executes unless it carries a valid HMAC signature under
> the shared secret, is addressed to this runner's audience, is
> within the size caps the code already declares, and is not
> cleartext — cleartext being refused by default.

The short form is a summary. The nine clauses above are the
property. Where they differ, the clauses win.

### P1 as a family: P1(B)

P1 is not one claim but a family of claims, one for each script
size the model admits. **P1(B)** is the claim that the nine
clauses above hold for every handling whose script has a
character count of at most B — the number of characters in the
script's text, as "Terms, stated once" defines it. B is the
script character bound. Everything else in the statement — the
actors, the clauses, the check order below — is the same at
every bound; only B changes.

The bound counts characters, not lines and not line length,
because line counts mislead: a one-liner can be extremely long,
and obfuscation stuffs many characters onto few lines, so a
line-based bound can be walked around by formatting alone. The
character count is the measure that tracks how much script
actually came through the door.

The family is climbed in stages:

- **First rung: P1(49).** Scripts under 50 characters — 49 or
  fewer. The property MUST be proven at this bound first: at
  this size a checker can be exhaustive about the shapes a
  script's length can take, and the gate's decisions do not
  depend on script content beyond the checks the code performs.
- **Raised rungs.** The same nine clauses, re-proven at each
  raised bound on the ladder in `goals.md` (stage 6): 500,
  5,000, 50,000, and 500,000 characters, then the production
  cap. **P1(500) is checked** (`stage6-rung500.md`). The
  rungs above it are the same searched set: the character
  count is not a state variable, and no gate step branches
  on a script's text. **P1(1048576) was re-run**, not copied,
  and the counts match (`stage6-cap.md`). P1(5000),
  P1(50000), and P1(500000) are that same check. They are
  not four additional graphs.
- **Last rung: the production cap.** The code's script cap (C2)
  is `max_script_bytes`: 1048576 UTF-8 bytes, 1 MiB. Every
  script the runner can accept satisfies that byte cap, and
  every character takes at least one UTF-8 byte, so every
  acceptable script has a character count of at most 1048576.
  P1(1048576) therefore covers every script that can pass the
  code's own cap: at the top of the ladder, the family's claim
  and the production claim coincide. The two measures —
  characters for the model, UTF-8 bytes for the code — remain
  different measures, and each stays named wherever it is used.

A checked claim at one rung says nothing about a higher rung.
P1(49) holding does not make P1(500) true; each raise MUST be
re-proven, not presumed. If a higher rung produces a
counterexample, the lower rungs' checked claims stand, stated
at their own bounds, until the finding is resolved.

### The audience clause, honestly weakened by mode

Clause 4 is the one place where P1's strength depends on
configuration, and the model MUST NOT hide that. With the
audience feature `off` — the default in a fresh configuration
(C11) — any correctly signed job for any audience passes clause
4, because there is no binding to check against, or none is
switched on. With the feature in `audit`, a job for the wrong
audience executes and leaves a record. Only in `enforce` does
the short-form sentence "addressed to this runner's audience"
hold without qualification. The first model therefore states P1
twice: in its strong form, under audience `enforce` with a
`runner_id` configured, and in its default form, where clause 4
is recorded as vacuous. Both forms are worth checking. The
default form is what a fresh install actually runs.

### The check order, as the code performs it

The order matters to a model: a check that runs after execution
would be no check at all, and two checks in the wrong order can
leak what the later one exists to hide. The order below is the
order in `runner/ops/mail.py`, `handle_mail`, at `6d6288c5`,
with the dispatch helper it calls. Line numbers are that
function's unless another file is named.

0. **Panic before everything.** Lines 42 to 58. If the subject
   carries the panic word, the box stops and nothing is executed.
   If the box is already stopped, the message is left alone.
   This step reads only the subject and runs before any MAC work
   and before the seen set, by design, so it works when the
   secret is in the wrong hands.
1. **Raw size bound.** Lines 64 to 70 (C1). An over-cap marked
   message is refused before any signature work. Every protocol
   message the door takes — jobs, queries, board mail, version 2
   mail — faces this bound, not jobs alone.
2. **Early dispatch and routing.** Line 72 calls
   `_early_dispatch` (`runner/runner.py`, line 4653). In order,
   it handles cancel mail, query mail, board mail (when a board
   is configured), and version 2 mail; it recognises a bounce of
   the runner's own mail and never parses the quoted original as
   a submission; it requires the subject to carry a job id at
   all; it refuses execution when the runner is answer-only under
   protocol version 2; and it applies the seen-set lookup — a job
   id already in the seen set (namespaced by `runner_id` when one
   is configured) is skipped here, before signature work. What
   returns is a fresh `(job_id, skey)` pair or nothing.
3. **Verification and decryption.** Line 87 calls
   `_verify_and_decrypt` (`runner/runner.py`, line 4604). The
   outer body verifies through `verify_body_keyed` (C5, C7). An
   `hp_enc` envelope is then decrypted (C9) and its inner body
   verified under the same key id; a mismatch of key ids, a
   malformed envelope, or a bad decryption refuses the job. A bad
   signature and a bad envelope are recorded as authentication
   rejections.
4. **Cleartext decision.** Lines 96 to 130 (C8). An unencrypted
   job proceeds only when `_cleartext_jobs_allowed()` holds for
   this process; otherwise it is refused, with the rejection
   logged, the message marked seen, an `auth_rejection` event
   recorded, no result sent, and the job id not recorded in the
   seen set.
5. **Audience.** Line 132 (C10). `audience_allows` applies the
   three-mode decision. An `enforce` mismatch refuses the job as
   a security-policy rejection.
6. **Encodability.** Lines 138 to 142. A signed body whose text
   carries an unpaired UTF-16 surrogate is refused: it parses,
   but nothing downstream can encode it.
7. **Script size bound.** Lines 147 to 154 (C2), after the
   signature, measuring the script in UTF-8 bytes.
8. **Version, type, identity.** Lines 156 to 161 (C13): `v` is
   the integer 1, `type` is `job`, body job id equals subject
   job id.
9. **Freshness.** Lines 163 to 176 (C12): `issued_at` parses,
   carries a timezone, and sits inside the window.
10. **Key policy.** Lines 178 to 183 (C14): `check_key_policy`
    speaks for the key directory first, then the key's own policy
    entry — kinds, recipes, interpreters, timeout, and the
    script-pinning list.
11. **Pinned-key constraints.** Lines 190 to 219 (C11). Where the
    key has a policy and any of `policy_env`, `policy_files`, or
    `policy_args` is not `off`, each constraint finding goes
    through `sec_decide`; an `enforce` denial refuses the job.
12. **Sensor branch.** A job of kind `sensor_alert` leaves the
    execution path here for its own ingest. It has passed every
    check above; it is not script execution, and P1's claim about
    it is exactly that it reached this branch through the gate.
13. **Advisory review.** The Oracle reviews the job and may
    attach notes. It never blocks; a review that raises is
    dropped. This step is listed so the model records that it
    sits after every gate and changes no decision.
14. **Dry run stops here.** A dry-run handling verifies
    everything above and executes nothing.
15. **The claim.** Lines 260 to 278 (C15). Under the mail lock,
    a job id already seen, already in flight, or already owned
    on disk is not executed; a live claim in another process
    leaves the message unseen so a crash there can be recovered,
    rather than dropping the job. Only a handling that takes the
    claim proceeds.
16. **The record before the result.** A job whose result is
    already on record is answered from the record and not
    executed (lines 320 to 330). A cancellation recorded before
    arrival refuses the job. The judge and the Oracle opinion run
    here; the opinion is advisory, and the one refusal it can
    produce is the re-judgement of a job it repaired, which is
    sent back through the key policy and the judge before it can
    run. Protocol version 2's before-execution exchange also runs
    inside this span, after the gate, never instead of it.

Execution is reachable only at the end of this order. Every
earlier step can refuse, and a refusal at any step means no
execution in that handling.

### What a counterexample would look like

A counterexample to P1 is a single concrete handling — real, in
the code, or exhibited by the model inside its bound — in which
a job executes while at least one clause above fails. Any one of
these shapes is a counterexample, and finding one ends the
argument until it is fixed:

- An unsigned job, or a job whose signature was made under a
  secret the runner does not hold, reaches execution.
- A job signed under key A executes carrying key B's identity, or
  an envelope whose inner body names a different key than its
  outer body executes.
- A signature-valid cleartext job executes in a process that was
  not started with `--allow-cleartext`.
- A job whose claimed audience differs from the configured
  `runner_id` executes while the audience feature is in
  `enforce` mode.
- A marked raw message over `max_job_bytes`, or a signed script
  over `max_script_bytes` in UTF-8 bytes, executes, with the
  relevant cap set to a non-zero value in the configuration the
  handling loaded.
- A job with `v` of 2, `true`, or `1.0`, a `type` other than
  `job`, or a body job id different from its subject's, executes.
- A stale job, or one dated more than 300 seconds in the future,
  executes.
- A job its key's policy forbids — a wrong kind, a disallowed
  interpreter, an over-limit timeout, or a script whose SHA-384
  is not in the key's pinning list, or any `script_url` job under
  a pinning policy — executes.
- The same job id executes twice inside the windows C15 claims:
  two deliveries handled in any order, in one process or two,
  with the result of the first on record.

A counterexample found in the model but not reproducible in the
code is a model defect: the model allowed a step the code does
not have. A counterexample reproducible in the code is a code
defect. Both are findings. Neither is resolved by weakening the
statement after the fact; the statement above is the fixed point
the work measures against, and a change to it is a new version of
this file, made in the open.

### Starting scope for the first model

The first model covers the mail path only, one default key and
one additional key, the audience feature in each of its three
modes, cleartext and encrypted arrivals, replayed deliveries, and
scripts whose character count is under 50 — the first rung,
P1(49), of the family stated above. Script content is
abstracted to what the gate itself looks at: character count for
the model's bound, UTF-8 byte length for C2, and the SHA-384
digest where a policy pins scripts (C14). Queries, board mail,
version 2 mail, cancels, and the local-signals path face the same
early bound and their own verification, and each joins the model
in a later stage rather than being assumed equivalent.

## P2. Result policies cannot widen confinement

### Statement

P2 starts where P1 ends: a job has passed the gate and is about
to execute. The sender of that job may hold a valid key — P1 is
satisfied — and may still be a compartmentalised worker whose
jobs the owner means to keep inside a ceiling. P2 is the claim
that the ceiling is the owner's in both of the places a job
could try to move it: what execution may touch (PROTOCOL.md
section 9.4), and what the job's result policy may disclose
about the run (PROTOCOL.md sections 9 and 12, non-escalation).

For every execution of a job and every result and answer built
from it, all of the following hold:

1. **The sandbox decision is the owner's.** Whether the job
   runs inside the sandbox is a function of the configured
   confinement mode and of the machine (whether the mechanism
   works there) and of nothing else (C18). No field in the job
   is read by the decision, and no field can change the mode,
   suppress the audit record of the decision, or turn a fallback
   into a silence: a fallback is logged and audited, and the
   choice to fall back is the mechanism's, never the job's.
2. **The writable set cannot grow.** Inside the sandbox, the
   job's writable set is its work directory alone, bound at the
   work mount (C18). No job field adds a writable path. Outside
   the sandbox — mode `off`, mode `audit`, or a mechanism
   fallback — execution is unsandboxed, and that state is
   reached only through clause 1's inputs, never through a job
   field: a job cannot argue its way out of a sandbox the owner
   switched on and the machine can run.
3. **The visible set grows by one bounded rule only.** Inside
   the sandbox the job sees the fixed flag set's mounts and the
   owner's configured extra read-only binds, plus exactly one
   job-influenced addition: when the interpreter the job names
   resolves outside `/usr`, that interpreter's own install
   prefix is bound read-only, by the runner's uniform rule, so
   the interpreter can run (C18). The job names no path to bind;
   the prefix is derived from the interpreter the runner
   resolved; the bind is never writable; and every such bind is
   written into the audit record. This clause is stated with
   the rule inside it because the rule exists in the code: a
   statement that claimed no job influence on the visible set
   at all would be false, and a wider influence than this rule
   is exactly what the property forbids.
4. **The watched set and its verdict are the owner's and the
   runner's.** The confinement snapshot watches the owner's
   configured `workspace_root` and `protected_paths` (C18); a
   job cannot shrink the watched set, add an exclusion, or set
   the verdict. The verdict — confined, violated, or
   unconfigured — is computed by the runner from the before and
   after snapshots. A job may ask for the
   `confined_to_workspace` attestation; asking does not change
   the value reported, and a predicate the runner does not have
   answers `ok: false` with reason `unknown`.
5. **The disclosure view is the narrower of the two.** The
   effective result view is the narrower of the job's requested
   view and the owner's `max_result_view` ceiling, by the fixed
   order `attested` < `summary` < `redacted` < `full` (C17). A
   requested view that is absent or unrecognised reads as
   `full` — the documented default — and is then still capped
   by the ceiling. No job field produces a view wider than the
   ceiling.
6. **The query budget is the smaller of the two.** The
   effective budget is the smaller of the job's `query_budget`
   and the owner's `max_query_budget`, each defaulting to 8
   (C17). A job may spend its budget down; it cannot spend past
   either number.
7. **Redaction patterns are the runner's.** The patterns a
   result and its answers are scanned with are the built-in set
   plus the owner's configured extras. The job's
   `redact_patterns` member is read nowhere in the runner; a
   job cannot weaken, replace, or empty the set that scans its
   own output.
8. **Query answers carry runner-computed values, gated by the
   effective view.** An attestation answer reports the value the
   runner computed (the exit code, the output digest, the
   confinement verdict of clause 4). The raw-line operations
   (`grep`, `tail`) are answered only when the effective view
   allows raw lines — `full` or `redacted` (C17) — and under
   `redacted` the lines pass through the owner's patterns
   first. Every query spends one unit of the clause 6 budget,
   answered or rejected.
9. **Fields named for the settings do nothing.** A job that
   carries members named `security`, `confinement`,
   `workspace_root`, `protected_paths`, `max_result_view`, or
   `sandbox` has carried inert text: no runner code reads a
   member of any of those names out of a job. Disabling
   confinement from inside a job is not a refused request; it
   is not a request the code contains.

In short form:

> The ceiling on what execution may touch, and on what a result
> may disclose, is set by the owner's configuration and the
> code's constants. A job's fields can narrow what it gets —
> a narrower view, a smaller budget — and can choose the
> interpreter whose own prefix is then bound read-only by a
> uniform rule. They cannot widen either ceiling, and they
> cannot disable confinement.

The short form is a summary. The nine clauses above are the
property. Where they differ, the clauses win.

### What a counterexample would look like

A counterexample to P2 is a single concrete execution or
result — real, in the code, or exhibited by the model — in
which a job field moves a ceiling. Any one of these shapes is
a counterexample:

- A result delivered in a view wider than the configured
  `max_result_view`, because the job asked for the wider view.
- More queries answered for a job than the smaller of its
  `query_budget` and the owner's `max_query_budget` allows.
- A sandboxed job able to write outside its work directory
  because of a field it carried, or a job that runs
  unsandboxed, under confinement `enforce` on a machine where
  the mechanism works, because of a field it carried.
- A mount in the sandbox of a path the job named, writable or
  not, other than the interpreter-prefix bind of clause 3.
- A `confined_to_workspace` attestation reporting the value
  the job asked for rather than the verdict the runner
  computed from its snapshots.
- Output leaving unredacted because the job's own
  `redact_patterns` list replaced or emptied the runner's set.
- A raw-line answer (`grep` or `tail`) returned under an
  effective view of `summary` or `attested`.

The checked model, the configurations, and the witnesses are
recorded in `stage4-p2.md`; the model is `Confine.tla`.

## P3. A transport's credentials are a required second gate

### Statement

P3 stands in front of P1. A message reaches the signature check
only by crossing its transport, and the five shipped transports
do not stand in the same relation to credentials. Where a
transport has credentials of its own, they are a gate in front
of the signature: checked first, and a message that has not
passed them does not reach the signature check at all. Where a
transport has none, the signature stands alone, and this
statement says so per transport rather than claiming a
uniformity the code does not have.

The composition is by position, and one fact shapes all of it:
the core is transport-blind. `_service_transports`
(`runner/runner.py`, line 5300) services each enabled
transport's channel; `service_channel`
(`runner/wire/transports.py`, line 535) hands every envelope it
finds to `process_transport_message` (`runner/runner.py`, line
5238), which runs it through `handle_mail` and therefore
through the whole of P1, signature included. The core performs
no transport-credential check and receives no attestation that
one happened: an envelope is in the channel because a pipe put
it there (`deliver_job`, `runner/transport_extensions/
channel.py`, line 125), and each pipe puts it there only for a
message that crossed the pipe. The clauses below are therefore
claims about where each transport's gate stands and what it
stops, stated per transport where the transports genuinely
differ.

1. **The order is fixed.** On every transport that has a
   credential gate, the gate runs before the core's signature
   check, and the signature check runs in the core, identically
   for every transport. A transport-gate failure is not a
   signature refusal: the message is never presented — never
   enqueued, never delivered into the channel, never carried on
   an established session — so the core never sees it and P1 is
   never reached.
2. **A valid signature is not sufficient where a gate is in
   force.** For every arrival on a transport whose credential
   gate is in force in that deployment, if the credential check
   has not passed, the arrival MUST NOT be presented to the
   core, whatever its signature says.
3. **The credential gate is not sufficient either.** An arrival
   that passed the transport gate still faces the signature and
   every other clause of P1 in the core. Passing a pipe's
   credential check authorizes nothing by itself.
4. **Email has no sender gate, and the property claims none
   for it.** The only credential on the email path is the
   mailbox login (`runner/wire/mailbox.py`, `connect_imap`,
   line 199; the login itself at line 219), and it is the
   runner's credential to its own mail server: it authorizes
   the runner's reading and sending, and it authenticates no
   sender. Anyone who can route a message into the mailbox
   presents an envelope to the signature check. If the login
   fails, the email extension's pass fails and nothing is
   fetched — the login can stop delivery, but it is not a gate
   in front of the signature in P3's sense, and
   `mail_tls_required` (line 121) governs the pipe's
   certificate verification, not acceptance. Email stands on
   the signature alone, by design (C16).
5. **File's gate is the operating system's, held outside the
   code.** The file extension has no credential of its own:
   `FilePipe.scan_jobs` (`runner/transport_extensions/file/
   __main__.py`, line 90) applies shape discipline — a symlink
   is refused unread, an oversize file is refused unread, a
   malformed envelope is refused with the reason recorded —
   and delivers what it read. What decides who may present a
   file at all is write access to the inbox directory,
   enforced by the operating system before the extension can
   see the file. P3's claim for file is therefore an
   environment claim: it holds exactly insofar as the inbox
   directory's access control admits only the principals the
   owner intends. The runner's code cannot check that
   condition, and no clause here pretends it does.
6. **NATS's gate is broker authentication, required unless
   waived in the open.** The extension refuses to start with
   no broker credentials configured — a token, or a user and
   password, from the `transport_nats` block or the broker
   URL's userinfo — unless `allow_unauthenticated` is the
   literal value `true` (`NatsPipe.__init__`,
   `runner/transport_extensions/nats/__main__.py`, lines 351
   to 361; `main` turns the refusal into exit 2). With
   credentials configured, the broker enforces them at
   CONNECT: an `-ERR` answer raises in `NatsClient.connect`
   (line 190), the pipe reconnects with backoff, and
   `deliver_job` is reachable only for messages received on an
   established connection. A publisher faces the broker's same
   rule: a connection the broker refuses publishes nothing.
   Two conditions bound the claim, and both are stated rather
   than assumed away: the broker MUST actually be run
   requiring authentication (the extension's refusal covers
   the runner's side of the deployment; a broker configured to
   accept anonymous connections waives the gate at the
   broker), and a deployment that sets
   `allow_unauthenticated: true` with no credentials waives
   the gate in the open — it starts, it logs a warning that
   the HMAC signature is the only authorization gate on that
   transport, and it does not carry P3 (C20).
7. **DTLS's gate is the shared secret itself, in a second
   role.** The extension refuses to start when no secret was
   handed over (`runner/transport_extensions/dtls/__main__.py`,
   `main`, line 346), and it re-checks the entropy floor of
   every PSK it would terminate with (`_psk_floor_problem`,
   line 139). The gate is the handshake in
   `runner/wire/dtlsproto.py`: the server session
   (`_ServerSession`, line 1209) looks up the secret for the
   peer's PSK identity (an unknown identity is refused, line
   1303; the key directory can refuse a key, through the
   extension's `directory_lookup`, line 100), verifies the PSK
   binder (a mismatch refuses the handshake, line 1315), and
   handles application data only once the session is
   established — application data before that is dropped (line
   1412). Only an established session produces the
   application-message event the extension delivers from, so
   no job crosses before authentication. Resumption PSKs are
   issued only inside an established session and stay chained
   to the key that authenticated it. The two gates are real
   and ordered, but they are not two credentials: the PSK is
   the signature's own secret doing a second job, and a party
   who holds the secret passes both, exactly as P1's attacker
   model already assumes. The claim for DTLS is two checks,
   one secret, stated in those words.
8. **Queues' gates are bearer tokens at the hosted edge,
   checked before anything is stored.** In the Worker
   (`runner/cloud/queues-worker/src/index.js`), every route
   first compares the presented bearer token's SHA-256 against
   the role's stored hash (`bearerMatches`, line 368; a
   missing stored hash fails closed). Job submission requires
   the SI's token first (line 464) and then, while
   `REJECT_INVALID_HMAC` is on — the default (`rejectOn`, line
   413) — a valid edge HMAC under the tenant's secret (lines
   475 to 478); a submission failing either is answered 401 or
   403 and never enqueued. The runner's token gates the other
   direction: lease, renewal, ack, and result posts all
   require it (lines 459, 488, 493, 497), the extension
   refuses to start without one
   (`runner/transport_extensions/queues/__main__.py`, `main`,
   lines 466 to 471) and sends it on every call
   (`QueueClient._request`, line 135), and a wrong token makes
   the pull raise, the pass fail, and nothing be delivered.
   The edge signature check is a duplicate of the core's
   check, not one of the two gates: with `REJECT_INVALID_HMAC`
   off, a badly signed job with a good token is enqueued and
   leased, and is then refused by the core under P1 — the
   two-gate claim for queues is bearer token plus core
   signature, and it holds in both postures of the edge switch
   (C19).
9. **A waived gate is a waived property.** Any deployment that
   turns a transport's credential gate off — the NATS waiver,
   a broker run without authentication, an inbox directory the
   owner opens to every local principal — does not carry P3
   for that transport and MUST NOT be described as carrying
   it. The signature gate of P1 is unaffected by any of these
   waivers.

In short form:

> Where a transport has credentials of its own, they are
> checked first and they are required: a message that has not
> passed them never reaches the signature check, and a message
> that has passed them still faces the signature in full.
> Where a transport has none — email — the signature stands
> alone, and the property says which transports those are
> instead of pretending otherwise.

The short form is a summary. The nine clauses above are the
property. Where they differ, the clauses win.

### What a counterexample would look like

A counterexample to P3 is a single concrete arrival — real, in
the code, or exhibited by the model — that is presented to the
core, or accepted, in a way the clauses forbid. Any one of
these shapes is a counterexample:

- A job presented to the core over NATS, DTLS, queues, or file
  whose transport credential check failed or never ran, in a
  deployment where that transport's gate is in force.
- A queues job enqueued by a submission with no bearer token or
  a wrong one, or a job leased by a pull that carried a wrong
  runner token.
- A DTLS application message delivered to the core from a
  session that never completed the PSK handshake, or under a
  PSK identity the lookup or the key directory refused.
- A NATS message delivered into the channel while the broker
  was refusing the extension's connection.
- A file delivered by the file extension that was placed by a
  principal the inbox directory's access control does not
  admit — a counterexample to the environment condition of
  clause 5, recorded as one: it would indict the deployment's
  access control, not a check the code performs.

The checked model, the configurations, and the witnesses are
recorded in `stage4-p3.md`; the model is `TransGate.tla`.

## P4. A named key can do only what its policy allows

### Statement

P4 is P1's clause 8 taken on its own, because it is the
sharpest single-key claim the system makes. One key in
particular carries it: the upgrade key, a named additional
secret whose whole purpose is to stage a release, and whose
policy pins it to that one act. The claim is that the pinning
machinery — key policies, PROTOCOL.md section 14.1 — fences a
key to exactly what its entry names, at the job's door and at
the runner's other doors, and that the upgrade key's fence
admits one shape only.

The step this property speaks about is `check_key_policy`
(`runner/wire/verify.py`, line 878), called at the job's door
from `handle_mail` (step 10 of P1's check order, after the
signature has verified and after freshness), again on the
Oracle-repaired job before it can run (`runner/ops/mail.py`,
line 382), and on the local-signals path
(`runner/runner.py`, line 3990). The policy map it reads is
built by `build_key_policies` (`runner/wire/verify.py`,
line 485) at startup (`runner/ops/main.py`, line 140) and per
poll cycle (`runner/ops/poll.py`, line 41). The other doors —
query, board, version 2, cancel — apply the same entry through
`check_door_policy` (`runner/wire/verify.py`, line 826).

For every job decided at the policy step, all of the following
hold:

1. **The step speaks for the key that verified.** The key id
   the step receives is the one `verify_body_keyed` returned —
   the key whose secret verified the signature, selected
   before any MAC work, with any other id refused as unknown
   (C7). A job MUST NOT be verified under one key and judged
   under another's policy; a holder of one key's secret cannot
   present under another key's name, and cannot escape a
   policy by naming no key, since the unnamed form selects the
   default secret, whose signature the holder cannot produce.
2. **The key directory speaks first.** Where a directory is
   configured, its verdict is taken before the policy is read
   (C21): a key it refuses — compromised, no entry, a closed
   window, a mismatched fingerprint — is refused whatever its
   policy allows, and an unreadable directory refuses the key.
3. **No entry means unrestricted — with one flag, and never
   against the owner.** A key with no policy entry is refused
   at this step only where `key_policies_default_deny` is set
   and the key is not the default key. The default key is
   exempt from that flag under every name it answers to — the
   empty id, its fingerprint, a stored name for the same
   secret — because the step reads a key by its value, under
   any of its names.
4. **The policy is the key's, not the name's.** The entry is
   found under any of the key's names (`policy_for`,
   `runner/wire/verify.py`, line 380), and a configuration
   that enters one key under two of its names is a startup
   error. The verdict MUST NOT depend on which of its names a
   sender used.
5. **Kinds.** Where `allowed_kinds` is present, the job's kind
   MUST be listed (lines 924 to 929). For the upgrade key,
   whose list is `["exec"]` (C22), every other kind — ping,
   sensor_alert, recipe, change, a job with no kind — is
   refused at this fence, before any question about a script
   arises.
6. **Recipes and interpreters.** Where `allowed_recipes` is
   present, a recipe or change job's recipe MUST be listed
   (lines 930 to 936). Where `allowed_interpreters` is
   present, the job's effective interpreter — its own, or the
   configured default — MUST exactly match a listed list
   (lines 938 to 944); the fence does not bind recipe and
   change jobs, whose interpreter is the owner's.
7. **Timeout.** Where `max_timeout_sec` is present, the job's
   effective timeout — its own `timeout_sec`, or the
   documented default — MUST NOT exceed the cap (lines 945 to
   962). For the upgrade arrangement the cap is 300 seconds
   (C22).
8. **Script pinning.** Where `allowed_script_sha384` is
   present and the job's kind is `exec`, the job MUST carry an
   inline script whose SHA-384, over the script's UTF-8 bytes,
   is in the policy's list (lines 963 to 982; the list's
   entries are lowercased when the policy is built, line 553).
   A `script_url` is refused under such a policy — alone, and
   beside an allowlisted inline script, since the executor
   stages the URL first when both are present — because its
   content cannot be checked before download. A missing or
   non-string script is refused. The branch does not run for
   other kinds: a ping from a pinning key is governed by
   clause 5 alone, exactly as section 14.1 states.
9. **The fence stands at the other doors.** The same entry
   binds the key at the query, board, and version 2 doors
   through `check_door_policy`: a policy that lists
   `allowed_kinds` admits a door only when it names the door,
   and the deny flag refuses an entry-less additional key at
   every door. The cancel door is exempt from the kinds list —
   a key cancels only its own jobs — and is not exempt from
   the directory or the deny flag. For the upgrade key,
   `["exec"]` names no other door, so its messages are refused
   at the query, board, and version 2 doors outright. The key
   directory also gates the DTLS transport's PSK lookup (the
   extension's `directory_lookup`), so a refused key opens no
   session.
10. **A repaired job is re-judged.** The one repair the runner
    can make to a job — the Oracle's interpreter repair —
    produces a job that is put through `check_key_policy`
    again before execution, and the repair never touches the
    script, so a repair MUST NOT launder a script past clause
    8: the re-judged job faces the pinning branch with the
    script it arrived with.
11. **The surrounding fences are mode-gated, and the
    statement says so.** The entry's env, file, and argument
    constraints (`allowed_env`, `denied_env`, `allowed_files`,
    `allow_file_urls`, `max_args`, `args_pattern`, and the
    dangerous-env rule for pinned scripts) are computed as
    findings by `check_policy_constraints`
    (`runner/wire/verify.py`, line 1022) and applied behind
    this step through `policy_env`, `policy_files`, and
    `policy_args` (`runner/ops/mail.py`, lines 186 to 218):
    in `enforce` a finding refuses, in `audit` it is recorded
    and the job runs, with every mode `off` the findings are
    not computed. In particular the upgrade arrangement's
    `allowed_files` fence (C22) binds exactly when
    `policy_files` is not `off`. Clauses 5 to 8 are not
    mode-gated: they refuse in every posture.
12. **A malformed policy never reaches the step.**
    `build_key_policies` validates each entry as it builds:
    a non-object entry, an empty or mistyped kinds,
    interpreters, recipes, hashes, env or files list, a
    boolean or sub-1 `max_timeout_sec`, an `args_pattern`
    that does not compile or that backtracks on a hostile
    probe, and one key entered twice are startup
    configuration errors — refuse class (C14). The map the
    step reads contains only validated entries, with only the
    fields the builder carries.

In short form:

> A key's policy is a fence with that key's name on it: the
> kinds it may run, the recipes, the interpreters, the
> timeout, and — sharpest — the exact scripts, by SHA-384
> digest. The upgrade key's fence admits one shape: an
> execution job carrying the one pinned staging script,
> inside its timeout cap. Every other shape from that key is
> refused at the policy step, after the signature and before
> execution; the same fence stands at the query, board, and
> version 2 doors; and the key directory's refusal stands in
> front of the fence at all of them.

The short form is a summary. The twelve clauses above are the
property. Where they differ, the clauses win.

### What a counterexample would look like

A counterexample to P4 is a single concrete handling — real,
in the code, or exhibited by the model inside its space — in
which a job is accepted past the policy step outside its
key's fence. Any one of these shapes is a counterexample:

- An execution job signed with the upgrade key carrying any
  script but the pinned one — the clock job's shape — reaches
  execution.
- An execution job carrying a `script_url`, alone or beside
  the pinned script, signed with a pinning key, reaches
  execution.
- A job of any other kind from the upgrade key — a ping, a
  sensor alert, a recipe — performs its kind.
- A job from a governed key executes with an interpreter its
  entry does not list, a timeout over its cap, or a recipe
  its entry does not name.
- An additional key's verdict differs by the name it was
  presented under, or an additional key with no entry runs a
  job while `key_policies_default_deny` is set — or the
  default key is refused by that flag under any of its names.
- A key the directory refuses runs a job its policy would
  allow.
- A query, board, or version 2 message from the upgrade key
  is admitted at that door.

The checked model, the configurations, and the witnesses are
recorded in `stage4-p4.md`; the model is `KeyPolicy.tla`.

## P5. Replay cannot re-execute

### Statement

P5 is the property of time and repetition: the same job,
delivered twice, resent by its sender, or replayed by an
attacker who captured the valid signed bytes, MUST NOT
execute twice. Execution is at most once per job per runner
state directory; delivery of the result is at least once.
Stage 2's `Claim.tla` checked the narrow core — two handlers
racing one id in one process take the slot at most once —
and stage 3 recorded the mechanics around it as this
property's material: the stale-claim rule, the `_IN_FLIGHT`
lifecycle, and the resend's digest match. This statement is
written from those mechanics as the code performs them, and
it is stated no more strongly than they support: its edges
are named windows, priced in the clauses, not fine print.

A **job**, for this property, is a job id together with the
digest of the job as received — the SHA-384 over every
member but `sig`, in the canonical serialization
(`received_digest`, `runner/oracle/opinion.py`, line 130).
The distinction carries the property. An attacker replaying
captured bytes presents the identical job: every check P1
applies was passed by those bytes once, and the digest is
the same. A different body under the same id is a different
job; only a key holder can present one, because its
signature must verify and its `issued_at` must be fresh, so
presenting it is the key holder's own act, not a replay.

Three layers of state, all on disk in the runner's state
directory, carry the guarantee:

- **The replay cache** — `seen.json`, keyed by the seen key
  (the job id, namespaced by `runner_id` when one is
  configured: `_seen_key`, `runner/wire/verify.py`,
  line 1165), each entry stamped with the time it was
  recorded, kept for the horizon of C23. The in-memory set a
  poll cycle works with is loaded from this file
  (`runner/ops/main.py`, line 308; the channel path loads it
  the same way, `runner/ops/handlers.py`, line 207), and
  writes merge under the seen-file lock, so two processes'
  caches are one cache.
- **The claim** — an in-process half and a disk half. In one
  process, the check-and-add under `_MAIL_LOCK` against the
  seen set and `_IN_FLIGHT` (`runner/ops/mail.py`, lines 260
  to 278); across processes, a claim file taken under the
  seen-file lock by `_disk_owns` (`runner/ops/misc.py`,
  line 241), held until the id is in the cache, and released
  in the handling's `finally` span when it is not
  (`runner/ops/mail.py`, lines 734 to 738, through
  `_disk_release`, `runner/runner.py`, line 4900).
- **The record** — the result itself, stashed in the outbox
  before the first send is attempted and moved to `sent/`
  on delivery (`stash_result`, `runner/runner.py`,
  line 1623; the ordering is the module comment at lines
  1570 to 1585), carrying the received digest of the job it
  answers. A redelivery that reaches the record is answered
  from it by `load_sent_result` (line 2326), which returns
  the record only when its digest is the redelivered job's.

For every job delivered to the gate — that is, for every
handling that passes P1's steps and reaches the claim, step
15 of P1's order — all of the following hold:

1. **At most once, per job.** A job MUST NOT execute more
   than once in a runner state directory, except across one
   of the window events clauses 7 to 9 price, each of which
   buys at most one further execution. Two executions of two
   different jobs that share an id are not a counterexample:
   the count is per digest, not per id alone.
2. **The cache answers first.** A delivery whose id is in
   the replay cache — in memory, or found in `seen.json` by
   the claim — MUST NOT execute and MUST NOT be answered
   from the record by that handling: the copy is done, the
   message is marked seen, and nothing is sent
   (`runner/ops/mail.py`, lines 261 to 267; `_disk_owns`
   records the key in the in-memory cache on the same path).
   The result the sender is waiting for is the outbox's to
   deliver (clause 10), not the duplicate's.
3. **One claim, in both halves.** While a handling holds
   the id — in `_IN_FLIGHT`, or as a live claim file — a
   second handling of the id MUST NOT execute. In one
   process the second handling is skipped at the claim,
   under the same lock that performed the check-and-add.
   Across processes the second handling finds the claim
   held and leaves the message unseen, so the copy is
   deferred to a later poll rather than dropped
   (`runner/ops/mail.py`, lines 266 to 278): what differs
   across the halves is the loser's outcome, never the
   safety claim — this is stage 3's finding F3, and the
   model's claim covers both.
4. **A dead holder's claim is stealable, on the stale
   rule.** A claim whose holder is dead MAY be taken by the
   next handling at once; a claim whose holder cannot be
   read MAY be taken only once the file is at least
   `_CLAIM_STALE_SEC` old; a live holder's claim MUST NOT
   be taken at any age (C24). Stealing a claim never by
   itself executes anything twice: the thief still faces
   the cache and the record, in that order.
5. **The record answers the resend.** A delivery that takes
   the claim and finds a record whose digest is its own
   MUST be answered with the recorded result, MUST be
   committed as seen, and MUST NOT execute
   (`runner/ops/mail.py`, lines 320 to 330). This path is
   reached when the cache no longer holds the id but the
   record stands — the cache entry aged out or was evicted
   (C23), or the cache write was lost while the stash was
   not — and it is the second layer of the guarantee: the
   cache expiring does not by itself reopen execution.
6. **A different job under a reused id runs on its own.** A
   delivery that takes the claim and finds a record whose
   digest is not its own MUST NOT be answered from that
   record (`load_sent_result` returns no record on a digest
   mismatch); it proceeds to execution as the new job it
   is. While the cache holds the id, clause 2 reaches it
   first and it does not run — a reused id is usable only
   once the cache has let it go, and then only by a key
   holder presenting a fresh, validly signed job.
7. **The crash window, priced.** A crash — or a restart,
   which is the same event from the record's side — between
   a run and its stash leaves no record and no cache entry,
   and a redelivery of that job executes again: the second
   run is bought by the crash, and at most one run follows
   each such crash, because the run that completes commits
   its record and its cache entry in one locked span
   (`commit_and_deliver`, `runner/ops/mail.py`, lines 295
   to 318 — a stash that cannot be written leaves the job
   uncommitted, which is this window and no other). A crash
   after the commit cannot re-execute: the state it would
   need is already on disk. This is the one window C15
   names, and the statement does not hide it.
8. **The cache's window is built to outlast the gate's.**
   The cache keeps an entry for `max(max_job_age_sec + 300,
   86400)` seconds (C23): by construction, longer than the
   freshness window in which P1 step 9 would accept the
   mail at all, plus its future bound. A replay old enough
   to have left the cache is refused as stale before it
   reaches the claim — unless the entry was evicted at the
   cache's 200,000-entry cap, in which case clause 5's
   record is the layer that answers, inside its own window
   (clause 9).
9. **The record's window, priced.** A delivered record
   ages out with `output_retention_days` (default 7 days;
   an explicit 0 means it never ages out, C25). Once the
   record is gone and the cache entry with it, the id is a
   new id to the runner, and a fresh, validly signed job
   under it executes — at most one further execution, bought
   by the expiry. A replay of the original bytes cannot
   reach this window inside any ordinary configuration: it
   would have to be fresh under P1 step 9 while older than
   the retention, which requires `max_job_age_sec` to be
   configured past the retention — an owner's configuration
   that reopens the id deliberately, and the guarantee is
   not stated against it.
10. **Delivery is at least once, inside the stash
    window.** The result is stashed before the first send;
    a failed send is retried from the stash, with
    `result_resend_backoff_sec` between attempts, and is
    never produced by a second run (C25). After
    `result_stash_retention_sec` of attempts (default
    86,400 seconds) the runner gives the delivery up: the
    record moves to `outbox/failed/` with an audit entry
    and leaves the set clause 5 answers from. Inside that
    window the result MUST be delivered at least once, the
    stash surviving restarts like the rest of the state;
    past it, delivery is no longer claimed — while execution
    still cannot recur, because the cache entry committed
    with the stash stands on the horizon of clause 8.
11. **Restart changes nothing but the dead claim.** Every
    layer is disk state, so a restart neither grants nor
    loses an execution: the cache is reloaded from
    `seen.json`, the records stand where they were written,
    and the only restart-shaped event in the whole property
    is a claim left by the dead process, governed by
    clause 4 — plus clause 7's window, when the death came
    between a run and its record. A runner restarted cleanly
    between a commit and a send delivers from the stash and
    runs nothing.

In short form:

> A job executes at most once per state directory. The
> replay cache turns a duplicate away; one claim, in-process
> and on disk, keeps two handlings from running it; and a
> redelivery that outlives the cache is answered from the
> recorded result, bound to the job's own digest, and runs
> nothing. The guarantee has three priced edges: a crash
> between a run and its record buys one more run; the record
> ageing out buys one more run of a fresh job under the id;
> and delivery is promised only inside the stash window.
> Outside those edges, replay is answered, never re-run.

The short form is a summary. The eleven clauses above are
the property. Where they differ, the clauses win.

### What a counterexample would look like

A counterexample to P5 is a single concrete sequence —
real, in the code, or exhibited by the model inside its
space — in which one job executes twice without a window
event buying the second run. Any one of these shapes is a
counterexample:

- Two handlings of one job, in one process or two, both
  reach execution while neither a crash nor an expiry stands
  between them.
- A redelivery is answered by re-running the job although
  its record stands and its digest matches.
- A redelivery carrying a different job under the id is
  answered with the recorded result of the first — the
  record's digest check failing to distinguish them. (The
  converse — the different job executing once the cache has
  let the id go — is clause 6, the designed behaviour, and
  is not a counterexample.)
- A claim whose holder is alive is taken by a second
  handling, and the job runs under both.
- A restart by itself — no crash between a run and its
  record — causes a committed job to execute again.

The checked model, the configurations, and the witnesses are
recorded in `stage4-p5.md`; the model is `Replay.tla`.
`Claim.tla` (stage 2) remains the check of the narrow race;
this model is the full shape.

## P6. Refuse-class configuration behaves as Decision 1 requires

### Statement

Decision 1 (`docs/design/present-but-invalid-config.md`) splits
a setting that is present but not usable by what a wrong value
changes. P6 is that split, as the code performs it. The actors
are the owner, who writes `config.json`, and the runner, which
reads it at startup and again while running. No job is involved.
A wrong value here is the owner's, not a sender's.

For every setting the inventory classifies, the following hold:

1. A key that is absent is not a present-but-unusable value. It
   reads as its documented default, and it is not named in the
   startup warning. `defaulted.is_defaulted` is false when the
   value is `None` (C26).
2. A present usable value is used as written. It is not named.
3. A present unusable value in the default class does not stop
   the runner. The reader returns the documented default, and
   the startup warning names the key. A boolean is never a
   number, a non-finite number is not usable, and a value
   outside the key's bounds is not clamped to the bound: it is
   unusable, and the default applies (C26).
4. A present unusable value in the refuse class stops the
   runner at startup, before any job is read, and the error
   names the setting. The process exits 2. Size caps, mailbox
   ports, key policies, and the security block are this class
   at startup (C27).
5. A live reload of a default-class value that is present and
   unusable replaces the running value with the documented
   default and names the key in the log. It does not keep a
   hidden last-good value, and it does not stop the process
   (C26).
6. A refuse-class key is not in the live-reload set. A later
   write, usable or not, does not change the running binding
   through `reload_hot_config`. The process keeps running. The
   new value is read at the next start, where clause 4 applies
   if it is unusable (C27).
7. A reload that cannot read the file changes nothing and does
   not advance the reload marker, so the next cycle tries the
   same file again.

In short form: a typo in a tunable costs a warning and the
documented default; a typo in a port, a policy, a secret, or a
security mode costs the start, and never a quiet change while
the process is already up.

### What a counterexample would look like

- The runner starts, and reads a job, while a refuse-class
  setting is present and unusable.
- A default-class setting that is present and unusable is used
  as written, or is replaced by its default without the key
  being named.
- An absent key is named as if the owner had written a bad
  value.
- A live reload of an unusable default-class value keeps the
  previous value.
- A live reload of a refuse-class value changes the running
  binding, or stops the process.

The checked model is `Decision.tla`. The record is
`stage4-p6.md`. Clause 7 is the one clause the model does
not check: its attempts are class by presence by moment,
and an unreadable file is none of those. Clause 7 is held
by the code read at `reload_hot_config`, which returns
before the reload marker advances when the file cannot be
read, so the next cycle tries the same file again.

## The placeholder properties

None remain. P1 through P6 are stated above.

