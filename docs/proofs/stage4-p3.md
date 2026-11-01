# Stage 4, second property — P3, checked

This is the record of P3's pass through stage 4's cycle: the
full statement, the model, the check, and what the check does
not say. P3 is the second of stage 4's five properties; P4 to
P6 remain placeholders in `properties.md`, each to be taken up
in turn. The statement is in `properties.md` (P3, nine
clauses); the constraints it uses are C16 from stage 1 and C19
and C20, harvested from the code for this stage, in
`constraints.md`; the model is `TransGate.tla` in this
directory.

The code read for this stage is the code at the `testing`
branch tip this stage started from, which is the code at
`6d6288c5` for every file named below.

## The property, in one paragraph

A message reaches the signature check only by crossing its
transport. Where a transport has credentials of its own, they
are checked first — by the extension at startup and connect,
by the far end before anything is stored, by the handshake
before any application data, or by the operating system
before a file can be presented — and a message that has not
passed them is never presented to the core, whatever its
signature says. A message that has passed them still faces
the signature in full. Where a transport has no credentials —
email — the signature stands alone, and the statement says so
rather than claiming a uniformity the code does not have.

## Where each transport's gate stands — the code sites

**The composition point, common to all five.** The core is
transport-blind. `_service_transports` (`runner/runner.py`,
line 5300) services each enabled transport's channel through
`service_channel` (`runner/wire/transports.py`, line 535);
every envelope found there goes to `process_transport_message`
(`runner/runner.py`, line 5238), which wraps it as a synthetic
message and calls `handle_mail` (line 5266) — the whole of
P1, signature included. The core performs no
transport-credential check and is handed no attestation that
one happened. An envelope exists in a channel only because a
pipe wrote it (`deliver_job`,
`runner/transport_extensions/channel.py`, line 125), so each
gate below stands in front of that write, in the pipe. The
core also decides what each pipe may hold:
`_runtime_config` (`runner/wire/transports.py`, line 671)
hands an extension its own block, the mailbox keys to email
alone, and the secret material to DTLS alone
(`_dtls_secret_material`, line 635), because those two
terminate something themselves. No other pipe ever holds the
shared secret, so no other pipe can check the signature
itself.

**Email — no sender gate.** The email extension
(`runner/transport_extensions/email/__main__.py`,
`EmailPipe.pass_once`, line 115) fetches through
`connect_imap` (`runner/wire/mailbox.py`, line 199; the login
at line 219, or XOAUTH2 where configured). That login is the
runner's credential to its own mail server: a failed login
fails the pass, the loop logs and retries, and nothing is
fetched — but it authenticates no sender, and anyone who can
route mail into the mailbox presents an envelope to the
signature check. `mail_tls_required` (line 121) is the pipe's
certificate posture, not an acceptance gate. P3 claims
nothing for email beyond the signature, and the model carries
email as the gateless branch.

**File — the gate is the operating system's.** The extension
(`runner/transport_extensions/file/__main__.py`) has no
credential anywhere in its code — a search for one returns
nothing, and the pinning test now holds that absence.
`FilePipe.scan_jobs` (line 90) applies shape discipline only:
symlinks refused unread, files over the channel cap refused
unread, malformed envelopes refused with the reason left in a
`.refused.txt`. Who may present a file at all is decided by
write access to the inbox directory, enforced by the OS
before the extension opens anything. The claim for file is
therefore conditional on the deployment's access control,
stated as an assumption wherever the claim is made.

**NATS — broker authentication, required by default.**
`NatsPipe.__init__` (`runner/transport_extensions/nats/
__main__.py`, lines 351 to 361) computes whether any
credential is configured — token, user, or URL userinfo —
and refuses to start when none is and
`allow_unauthenticated` is not the literal value `True`;
`main` returns exit 2. With credentials, the broker enforces
them at CONNECT: `NatsClient.connect` (line 190) sends
CONNECT and PING, an `-ERR` reply raises `TransportError`,
and the pipe's loop reconnects with backoff having delivered
nothing; `deliver_job` is called only on MSG frames of an
established connection. The publisher side faces the same
broker rule. The waiver, when taken, is loud: the pipe logs
at WARN that the HMAC signature is the only authorization
gate on the transport.

**DTLS — the secret itself, in a second role.** The
extension refuses to start when no secret was handed over
(`runner/transport_extensions/dtls/__main__.py`, `main`,
line 346) and re-checks the entropy floor of every PSK it
would terminate with (`_psk_floor_problem`, line 139). The
gate is the handshake: `_ServerSession`
(`runner/wire/dtlsproto.py`, line 1209) resolves the peer's
PSK identity through the secret lookup — the extension wraps
it with the key directory, which can refuse a key
(`directory_lookup`, extension line 100) — refuses an unknown
identity (line 1303) and a binder mismatch (line 1315), and
in `feed_authenticated` (line 1372) drops application data
that arrives before the session is established (line 1412).
The extension delivers only on the session core's
application-message events, which exist only past that point.
A resumption PSK is minted only inside an established
session and records the key that authenticated it.

**Queues — two bearer tokens at the hosted edge.** In the
Worker (`runner/cloud/queues-worker/src/index.js`), every
route compares the presented bearer token's SHA-256 with the
role's stored hash in constant time (`bearerMatches`, line
368; no stored hash, no match). Submission (POST jobs)
checks the SI token first (line 464) and then, while
`REJECT_INVALID_HMAC` is on — the default, `rejectOn`, line
413 — the edge HMAC verdict (lines 475 to 478: 400 for no
signature member, 403 for an invalid one); only then is the
job forwarded to enqueue. The runner direction is gated by
the runner token throughout (lease renewal line 459, pull
line 488, ack line 493, result post line 497), the extension
refuses to start without a token
(`runner/transport_extensions/queues/__main__.py`, `main`,
lines 466 to 471), and a wrong token makes the pull raise on
its HTTP status so the pass delivers nothing
(`QueueClient.pull`). The edge signature check is a second
copy of the core's check, ordered after the bearer check; it
is not one of the two gates, and clause 8 of the statement
says what the claim is with it off.

## The model

`TransGate.tla` is a single-decision model, in the shape
`Confine.tla` set: the initial state picks an attempt record
and a deployment record; one step computes the outcome
exactly as the composition above computes it; the invariants
state the claim in closed form over that outcome.

The attempt record carries the transport (all five), whether
the signature verifies, and whether the transport's own
credential check passed — the last read by nothing on a
transport with no gate in force, as an unread field is. The
deployment record carries the two posture switches the code
has: the NATS waiver, read only on the NATS branch, and the
queues edge signature check, read only on the queues branch,
where it enters the outcome only through presentation (a job
the edge refuses is never enqueued, hence never presented;
acceptance still requires the core's signature outcome, which
is the model's `sigValid`).

The counts multiply out and match the checker's own count,
which is the cross-check that the space searched is the space
described: 20 attempts (5 transports × 2 signature outcomes ×
2 credential outcomes) times 4 deployments (2 × 2) is 80
initial states, exactly the number TLC reports computing.

## What was checked

TLC 2.19 (the `v1.7.4` tools jar) on Java 21, the same tooling
`stage2.md` and `stage4-p2.md` record. Each run is
exhaustive. Trace output TLC writes beside the model
(`*_TTrace_*`, `states/`) is run debris and is removed, not
committed.

| Configuration | File | Invariants | Result | Generated | Distinct |
|---|---|---|---|---:|---:|
| Full composition space | `TransGate.cfg` | `P3Inv`, `GateBlocks`, `PresentedExact`, `AcceptedExact` | holds | 240 | 160 |
| Both-gates witness | `TransWitnessBoth.cfg` | `BothGatesNeverEnough` | fails, as expected | 109 | 109 |
| No-gate witness | `TransWitnessNoGate.cfg` | `NoGateNoAccept` | fails, as expected | 89 | 89 |

The depth of the composition search is 2: the initial records
and the decided outcome. The fingerprint collision estimate
TLC printed for the main run was 6.9E-16 optimistic, the
ordinary bound for a run of this size. The witness runs stop
at their counterexamples, so their generated counts are the
states searched up to the exhibited handling.

`P3Inv` is the security half: an accepted job carried a valid
signature, and where a gate was in force its credential check
passed. `GateBlocks` places the block at presentation, not at
execution: a failed credential check on a gated transport
means the core never sees the message. `PresentedExact` and
`AcceptedExact` are the fidelity half: presentation and
acceptance are exactly the composition rule — gate, then
edge, then signature — not merely bounded by it, so a model
that presented nothing, or accepted on the credential alone,
would fail them.

To re-run from a bare machine: install a Java runtime
(Java 17 or later; `apt install openjdk-21-jre-headless` on
this distribution), fetch the TLA+ tools jar for `v1.7.4`
(`tla2tools.jar` from the tlaplus project's release of that
tag) into a tools directory, and from `docs/proofs/` run
`java -cp <tools>/tla2tools.jar tlc2.TLC -config <file>.cfg
TransGate.tla` for each of the three configuration files.

## The two counterexamples that are supposed to exist

`TransWitnessBoth.cfg` checks `BothGatesNeverEnough` — the
claim that even a job passing both gates is never accepted.
TLC's counterexample is a file-transport arrival whose
credential check passed (the presenting principal was
admitted by the inbox's access control) and whose signature
is valid: the outcome is presented and accepted, with the
gate recorded as in force. Both gates passing lets a job
through; a model that accepted nothing would have satisfied
`P3Inv` and shown nothing.

`TransWitnessNoGate.cfg` checks `NoGateNoAccept` — the claim
that nothing is accepted where no gate is in force. TLC's
counterexample is an email arrival with a valid signature:
the outcome is presented and accepted, with the gate recorded
as not in force. That is clause 4 exhibited rather than
asserted: on the transport with no sender gate, the signature
alone admits, by design — and the waived NATS deployment
stands in the same part of the space for the same reason.

## Finding

No finding came out of the code read. In particular, no
transport was found where a job can be presented with its
credential check failed, bypassed, or silently skipped: each
extension's `deliver_job` call sits behind its pipe's
authentication (an established broker connection, an
established DTLS session, a fetched mailbox, a leased queue
pull, a file the OS let the extension read), every Worker
route that stores or leases is bearer-checked before any
other work, and the three extension refusals to start
(credential-less NATS, secret-less DTLS, token-less queues)
are unconditional in the code paths that carry them.

Two near-things were found and are recorded as clauses of
the statement rather than as findings, because the code is
honest about both and the property is stated around them:
DTLS's gate is the signature's own secret in a second role
(clause 7), so its two gates fall together to anyone who
holds the secret — which P1's attacker model already
assumes; and file's gate is held by the operating system
(clause 5), so the claim for that transport is exactly as
strong as the deployment's directory access control, which
no code here can check.

## What this does not say

- The model composes the transport gate with the signature
  outcome. Whether a presented job executes is P1: the
  model's `Accepted` is presentation plus a valid signature,
  and every clause behind the signature is the gate model's
  claim, not restated here.
- The credential and signature outcomes are independent bits.
  For DTLS they draw on one secret in two checks, and the
  states where they differ have real meanings — a key-holder's
  badly signed job is presented and refused under P1; a signed
  job offered by a peer that cannot complete the handshake is
  never presented — but the model does not represent the
  shared-secret link itself. Clause 7 carries it in words.
- File's refused attempts are enumerated by the model, but
  the mechanism that refuses them is the operating system's,
  outside the checked code. The model's claim for file is the
  composition claim — if the OS admits only intended
  principals, the gate composes as stated — and the condition
  is an assumption of the deployment, recorded in clause 5.
- The NATS claim is likewise conditional on the broker
  actually requiring authentication. The extension's half —
  refuse to start unauthenticated, deliver only on an
  established connection — is code; the broker's half is the
  deployment the extension is built for, and a broker run
  open waives the gate there exactly as
  `allow_unauthenticated` waives it here.
- The model's credential bit for queues is the
  submission-side gate, the one a job's arrival stands on.
  The runner-side token (lease, ack, result posts) is the
  same shape in the other direction and is stated in clause 8
  and pinned in the test, but it is not a second variable:
  a job the runner cannot lease is a job that was already
  gated at submission, and its non-delivery changes no
  acceptance outcome.
- The composition rests on the channel boundary: the core
  trusts that an envelope in a channel inbox arrived through
  the extension that owns the channel. The channel
  directories live under the runner's base directory, inside
  the same local trust boundary as the runner's configuration
  and seen set; a local principal who can write a channel
  inbox directly is not an arrival on any transport, and this
  property — like the file transport's gate, which is the
  same boundary wearing its own name — does not speak to
  them.
- Results travel the other direction over the same pipes and
  face their own rules (a result post refused for good, a
  session-bound result that waits for its session). Nothing
  here claims anything about results; P3 is about what gets
  in.
