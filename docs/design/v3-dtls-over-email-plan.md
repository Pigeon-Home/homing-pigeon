# Version 3 plan — DTLS via email with perfect forward secrecy

*Local build plan. The specification produced under this plan is a
local, unsubmitted draft. Nothing in this plan authorizes submission
to the IETF datatracker or publication outside this repository.*

## Starting point

The seed is the owner-written entry in `docs/project/future.md`:

> **ietf homing pigeon perfect forward secrecy v3** defines transport
> extension for v1 doc: DTLS over email using SS

That sentence ends at `SS`. The question it raised is answered:
`SS` is the Shared Secret, the same secret the DTLS handshake
already uses as its key — see the addendum at the end of this
plan. No part of the design had to guess at it.

Version 1 already defines a direct DTLS 1.3 binding. Its profile is
narrow and remains the cryptographic basis for this build:

- DTLS 1.3 only.
- 1 cipher suite: `TLS_AES_256_GCM_SHA384`.
- The shared secret is the external pre-shared key.
- `psk_dhe_ke` only; `psk_ke` is prohibited.
- An ephemeral X25519 key share rides every full or resumed
  handshake.
- The `platform_info` extension is offered empty in ClientHello and
  may be answered only in EncryptedExtensions.
- Jobs inside a DTLS session still face the version 1 job acceptance
  gate.

The missing piece is carriage. The version 1 DTLS binding needs a
live UDP path. Version 3 carries the same DTLS records over the
store-and-forward email binding, so a mailbox is enough to establish
a forward-secret session and then carry jobs inside it.

## High-level goals

### Goal 1 — Specify version 3 as a transport extension to version 1

Produce `docs/ietf/draft-slutsky-homing-pigeon-v3-00.md`, modeled on
the version 2 companion document and written as deltas against
version 1. The document will define:

1. The email wire format for DTLS flights and protected records,
   using the existing `[HOMING-PIGEON]` subject grammar.
2. A session identifier and per-message sequence sufficient to
   correlate a store-and-forward flight sequence without trusting
   mail headers for authentication.
3. Segmentation of a DTLS datagram across email messages and
   duplicate-tolerant reassembly.
4. Retransmission behavior for a carrier that can delay, duplicate,
   reorder, or lose messages.
5. Recognition of the DTLS initialization flight by the receiver's
   mail parser, before and separately from job handling.
6. Session establishment using the unmodified version 1 DTLS
   profile.
7. Carriage of ordinary version 1 job and result envelopes as DTLS
   application data.
8. Platform disclosure in EncryptedExtensions on this carrier.
9. Binding to the version 1 acceptance gate: HMAC signature,
   audience, freshness, key policy, and size limits all remain in
   force for a job carried inside a session.
10. No-downgrade rules: no fallback from an email DTLS session to
    `psk_ke`, cleartext job carriage, or ordinary per-job crypto for
    that session.
11. Replay handling at the mail, handshake, record, and job layers.
12. IANA considerations stating that this local draft requests no
    assignment yet.
13. Security considerations that state the forward-secrecy property
    and its limits.

### Goal 2 — Complete the future-work entry

Expand the owner-written 1-line entry in `docs/project/future.md`
into a full entry in the style of its neighbours. It will keep the
owner's bold title words and point to this plan and to the version 3
specification.

### Goal 3 — Build deployable carriage over the production email path

Grow `runner/wire/dtls_mailbox.py` from a local proof harness into
the reusable carriage and routing layer used by the production email
transport extension.

The production mail flow is:

1. `runner/transport_extensions/email/__main__.py` owns the mailbox.
2. It fetches unseen messages through `runner/wire/mailbox.py`.
3. Ordinary jobs cross the transport channel as envelopes.
4. The runner core processes a channel envelope through the same
   `handle_mail` path used for mail, so the acceptance gate is not
   reimplemented or bypassed.
5. Results return through the channel and the email extension sends
   them.

Version 3 inserts DTLS recognition into step 2 and 3:

- A message whose subject matches the DTLS grammar is classified
  before ordinary job delivery.
- A valid DTLS initialization or continuation flight goes only to a
  `DtlsServerCore` owned by the email carriage.
- Outgoing DTLS datagrams are posted back through SMTP as DTLS mail.
- Application data from an established session is unwrapped only to
  recover the ordinary job envelope, which is then delivered through
  the existing channel into `handle_mail`.
- A result for a job known to have arrived inside a session is held
  for that session, protected as DTLS application data, and posted
  as DTLS mail. It is not sent as an ordinary email job result.

The client side will use the same carriage functions around
`DtlsClientCore`, so the suite's Python tools can open a session by
email, send a job inside it, and receive the protected result.

### Goal 4 — Integrate the security model without weakening the gate

The DTLS session is a second gate, never a substitute for the job
gate. The build will preserve these rules:

- A completed handshake authenticates possession of the shared
  secret for DTLS purposes; it does not authorize a job by itself.
- A job application message must contain the ordinary signed job
  envelope. It reaches the existing core path and must pass HMAC
  verification, audience binding, freshness, key policy, and the
  size caps before execution.
- A cleartext signed object inside a session remains subject to the
  existing cleartext rule. Session establishment does not turn it
  into an encrypted object and does not create a new cleartext
  allowance.
- Session keys derive from a fresh ephemeral X25519 exchange on
  every handshake, including resumption. Long-term secret compromise
  must not decrypt a completed recorded session.
- A DTLS-shaped message that is malformed, unauthenticated,
  replayed, out of session, or downgrade-shaped fails closed: it is
  consumed as DTLS input or dropped, and it is never reinterpreted
  as a job.
- Exact duplicate mail flights are suppressed by the carriage.
  Duplicate handshake messages are left to the DTLS core's existing
  retransmission rules. Duplicate application records do not create
  a second job delivery; any duplicate job envelope that does reach
  the core remains subject to the core seen-set.
- Session state is bounded and expires. Store-and-forward delay does
  not create unbounded reassembly or session memory.

### Goal 5 — Prove the build with tests and fuzzing

Tests come before claims and, wherever behavior changes, before or
with the implementation. The test family will cover:

1. Parser routing: DTLS initialization, DTLS continuation, ordinary
   job, ordinary result, other pigeon message, and garbage.
2. Mailbox round trips over a fake mailbox shaped like production
   intake: full handshake, a ping, and a real signed job carried in
   the session and processed by the production mail-handling path.
3. Result carriage back inside the same session.
4. Negative cases: forged initialization, wrong-secret handshake,
   tampered flight, replayed mail, replayed protected record,
   downgrade to `psk_ke`, cleartext fallback attempt, and a record
   from 1 session injected into another.
5. Segmentation and reassembly under loss, duplication, and
   reordering.
6. A fuzz family for the new mail parser surface. Inputs are wrapped
   at the front and back with every ASCII symbol, plus NUL, tab, CR,
   and LF; symbol-only inputs and repetition runs at the front,
   back, and middle are included.
7. Registration of any new skip reason in
   `runner/tests/test_skip_registry.py` before the commit that uses
   it. The default for this build is to add no skips.

### Goal 6 — Record the result

Add a proof note under `docs/proofs/` naming the modules, the
specification, the tests that were actually run, their unfiltered
results, what works end to end, and what remains unproven.

## Design decisions taken

### D1. Reuse the version 1 DTLS engine and profile

`runner/wire/dtlsproto.py` already implements the required profile,
including the cookie exchange, platform disclosure, resumption
rules, and `psk_dhe_ke`-only key exchange. Version 3 changes the
carriage, not the session cryptography. This avoids a second DTLS
implementation and keeps the security review surface small.

### D2. Classify by subject grammar, authenticate by DTLS bytes

Mail subjects and headers route work; they never authenticate it.
The DTLS subject line will carry the kind, a session-correlation
identifier, and a flight sequence. The datagram still has to parse
and authenticate under the DTLS engine. A spoofed subject can waste
bounded parser work, but it cannot create a trusted session or run
a job.

### D3. Keep mailbox ownership in the email extension

The email extension is the only production process that polls the
mailbox. Version 3 therefore belongs beside that poll, not in the
UDP-only DTLS extension. The DTLS-via-email server core runs in the
email carriage path when the owner enables it.

### D4. Keep the runner core as the only job gate

Established-session application data is converted back into the
ordinary subject/body envelope and delivered through the existing
channel. The core's `handle_mail` path remains the single place
that verifies and executes jobs. No DTLS module will parse job
authority or execute job content.

### D5. Make the feature opt-in, with a bounded default posture

The carriage will be controlled by a transport-email option,
`dtls_via_email`, whose default is off. A present but unusable
value follows the project's present-but-invalid rule for this kind
of switch: only the literal boolean `true` enables it; other values
leave it off and are named in a startup warning where the hosting
extension already reports configuration problems. Enabling it hands
the email extension the DTLS secret material, because that process
now terminates DTLS; leaving it off keeps the existing secret
boundary unchanged.

### D6. Use synthetic peer addresses inside the DTLS core

The DTLS core keys its stateless cookie and sessions to a peer
address. Email has no UDP address. The carriage will use a stable
synthetic address derived from the authenticated mailbox peer
identity configured for the session, not from a spoofable `From`
header. The cookie therefore still binds a handshake attempt to
the peer context that started it, while mail headers remain
untrusted routing data.

### D7. Segment at the carriage layer, not inside DTLS

A DTLS datagram remains the unit the engine produces and consumes.
If it exceeds the configured mail-body limit, the carriage splits
the base64 representation into numbered parts and reassembles the
exact datagram before feeding the engine. Reassembly is bounded by
count, total size, and age; incomplete state expires. Duplicate
parts are idempotent.

### D8. Suppress exact duplicate mail before the engine

A mailbox poll or a sender retry can deliver the same RFC822
message more than once. The carriage records a digest of each
accepted DTLS mail payload for the life of its session state and
drops an exact repeat. This is a carriage dedup rule, separate from
DTLS record protection and separate from the job seen-set. It stops
a replayed protected record from being presented to the engine as
a new application message.

### D9. Bind results to the session that carried the job

The email extension will remember, for each job ident delivered
from a session, which local session carried it. When the matching
result appears in the channel outbox, the extension seals it as
application data for that session and posts it as DTLS mail. If the
session is gone, the result remains pending for a fresh session;
it is not downgraded to an ordinary email result by this carriage.

### D10. The naming: DTLS, and DTLS via email

The suite supports 2 ways of reaching a runner with DTLS, and
the names keep them apart. The direct way is just DTLS, with
no other mnemonic attached: the submitter is told the runner's
IP address and port, DTLS already means UDP datagrams
underneath, the network needs a firewall rule letting that
traffic in, and the runner must be configured to accept it.
The way this plan builds is DTLS via email: under the version
3 protocol the datagrams ride email, so no inbound network
path is needed. The carriage's prose name is "DTLS via email"
and its option is `dtls_via_email`. The seed line quoted at
the top of this plan keeps the words it was written with; the
name everywhere else is the one this decision states.

## Sub-goal sequence

1. This plan.
2. Version 3 specification and the completed `future.md` entry.
3. Parser and wire-format tests.
4. Carriage state machine: classification, segmentation,
   reassembly, duplicate suppression, retransmission, and expiry.
5. Email-extension integration and client-side send path.
6. Core-gate round-trip tests using a real signed job.
7. Negative, downgrade, replay, and cross-session tests.
8. Parser fuzz family.
9. Full touched-suite runs and the proof note.

Each step lands as its own local commit on the `together` branch,
with author and committer `Muse <muse@localhost>` and the project
Agent-Stamp trailer. Nothing is pushed and nothing is submitted.

## Open questions

1. **What does `SS` mean in the seed line?** Answered: `SS` is
   the Shared Secret, the DTLS handshake's key in the existing
   design. See the addendum.
2. **Should resumption be allowed over email?** The default taken
   here is yes, under the version 1 rule that resumption still uses
   a fresh ephemeral key share. Disabling it is a configuration
   option if operational experience says otherwise; it is not a
   security-model change because `psk_ke` remains prohibited.
3. **What mail-size ceiling should a deployment use?** The default
   taken here is bounded by the existing job and envelope limits,
   with a lower carriage-specific part limit that is tunable. The
   exact operational default can be revisited after the round-trip
   tests measure real flight sizes.

## Addendum, 2-Nov-2026

Open question 1 is answered: `SS` is the Shared Secret. It is
the DTLS handshake's key in the existing design -- the version
1 profile's PSK -- so the resolution confirms the plan's
assumption-free posture rather than changing it: no new key
material, no second secret, and the specification says so in
its Section 4.1. Open questions 2 and 3 stand as defaults
taken (resumption allowed under the fresh-share rule; the
carriage datagram limit at 262144 octets with a 32768-character
default chunk, both tunable).

As built, the wire format of D7 is 1 header line per flight
mail -- `HP-DTLS/3 transfer=<16 hex> part=<n> parts=<m>
bytes=<total> sha384=<digest>` -- followed by 1 base64 chunk,
with chunk boundaries on base64 group boundaries so the
decoded chunks concatenate to the datagram exactly.

## Definition of done

The build is done when all of the following are true in this local
clone:

- The plan, specification, and completed future entry are present.
- An email can open a DTLS session, further emails can complete it,
  and a real signed job can cross inside it through the production
  mail-handling path.
- The result returns inside the session.
- The negative and fuzz families above pass.
- The proof note records only results read from full, unfiltered
  test output.
