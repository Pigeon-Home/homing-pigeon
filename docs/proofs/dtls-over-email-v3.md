# DTLS over email, version 3: what was built and tested

Local branch `homing-pigeon-v3` (created as `together`,
renamed 2-Nov-2026), 2-Nov-2026; continuation below dated
2-Nov-2026 (run logs stamped 3-Nov-2026 UTC). The branch was
pushed to GitHub for review, then merged to main
(4a61c5ba) and released in 3.15.125; the branch is deleted.
Nothing is submitted; the version 3 draft is a local,
unsubmitted document. Read the continuation and the review
pass sections for the current claims: the first-build
section below is the record of the first 5 commits, and its
26-test count and its unproven list are superseded there.

## What was built

- `docs/design/v3-dtls-over-email-plan.md` -- the plan: 6
  goals, design decisions D1 to D9, and the open questions.
  Its addendum records the resolution of the seed line's
  truncated "SS": the Shared Secret, the handshake's existing
  PSK.
- `docs/ietf/draft-slutsky-homing-pigeon-v3-00.md` -- the
  version 3 specification, 930 lines: a transport extension to
  version 1 carrying its DTLS 1.3 profile over the email
  binding.
- `runner/wire/dtls_mailbox.py` -- grown from the 110-line
  local harness into the carriage: the `HP-DTLS/3` framed
  flight body, segmentation and bounded, expiring reassembly,
  parser classification (`dtls-init`, `dtls`, `dtls-part`,
  `dtls-invalid`, `job`, `other`) that recognizes a DTLS
  initialization flight by its bytes and fails closed on
  DTLS-shaped garbage, exact-duplicate suppression by datagram
  digest, and binding of each mail session-id to the DTLS
  connection ID it establishes. `DtlsMailServer` and
  `DtlsMailClient` wrap the unchanged engine in
  `runner/wire/dtlsproto.py`.
- `runner/transport_extensions/email/__main__.py` -- with the
  `dtls_via_email` option on (literal boolean true only), the
  email pipe classifies DTLS mail before job delivery, feeds
  it to the DTLS server in its own process, marks it seen
  whether it answered, is incomplete, or was malformed,
  delivers session jobs to the runner core as ordinary
  envelopes under their own job ids, and sends a session job's
  result inside its session -- or leaves the result file
  waiting. There is no downgrade to an ordinary mail result.
- `runner/wire/transports.py` -- the email extension is handed
  the DTLS secret material and the disclosure posture only
  when `dtls_via_email` is enabled; the secret boundary is
  unchanged otherwise.

The security integration is structural: the core's acceptance
gate (`runner/ops/mail.py`, reached unchanged through the
channel) is the only path from a session's application data to
execution, so a job inside a session still needs its valid
HMAC signature, correct audience, and the size caps; a
cleartext job inside a session is refused by the gate on the
usual terms.

## What was tested

`runner/tests/test_dtls_email_v3.py`, 26 tests, written before
the carriage existed (its 1st run failed at import, as a
test-first file should):

- Parser routing: a ClientHello mail is `dtls-init`; a
  protected-record mail is `dtls`, not initialization; an
  ordinary job mail is a job; a result mail is other; a v3
  subject with a bad body, a garbage datagram, or a bad
  session id is `dtls-invalid`; the legacy harness shape still
  parses.
- Segmentation: parts reassemble exactly out of order with
  duplicates offered; a bit-flipped part never reassembles;
  reassembly state expires.
- Carriage round trips over mail tuples only: a full handshake
  with the platform payload delivered as the greeting, and a
  ping delivered as application data.
- The production path: over `EmailPipe` with a fake mailbox
  shaped like the production intake, a handshake completes, a
  real signed and encrypted ping job crosses inside the
  session, lands in the channel as `v3-job-1.job.txt`, is
  executed once by the core (execution stubbed and counted),
  and its result returns inside the session and verifies and
  decrypts to a result with exit code 0.
- The negative family: a wrong-secret handshake never
  establishes and yields no application data; a tampered
  server flight is refused; a replayed initialization mail and
  a replayed application-record mail are each suppressed; a
  record from 1 session relabeled under another session's mail
  is dropped, and the same record under its own session is
  accepted; a job envelope wearing DTLS clothing, in both the
  v3 and legacy shapes, goes nowhere; a cleartext job inside a
  session is refused by the gate and nothing executes; a
  session result whose session is gone stays in the outbox and
  is never sent as plain mail.
- The fuzz family, on the bookend doctrine: the subject, the
  body, and the whole raw mail wrapped front and back with
  every ASCII punctuation symbol plus NUL, tab, CR, and LF --
  each symbol alone, in runs of 10 at the front, at the back,
  and in the middle, and as symbol-only strings. Over 300
  wrapped cases in the subject/body test alone. The parser
  never raised, every answer was a known kind, and no wrapped
  input established a session or produced an application
  message.

## Results, as read from the runs

- `runner.tests.test_dtls_email_v3`: 26 tests, OK.
- Final combined run over every touched suite --
  `test_dtls_email_v3`, `test_dtls_mailbox`, `test_dtls`,
  `test_email_pipe_coverage`, `test_transports`,
  `test_skip_registry`, `test_reader_docs_quiet`: 450 tests,
  OK, 1 skip. The skip is pre-existing and registered; this
  build added no skip reasons and did not touch the skip
  registry.
- Commits at that point, on `together`: 714ab9e5 (plan),
  0c763bfa (implementation and tests), 2b3fa4c0
  (specification, future entry, plan addendum), 99551763
  (this note), 29364dfe (the SS answer folded into the plan).

## Continuation: resumption, provider shapes, a live mailbox

Commit 4cc16fe0, tests only -- no carriage code change was
needed:

- Resumption over mail (5 tests): a resumed handshake under a
  fresh mail session-id with a fresh ephemeral share (the
  resumed offer's share differs from the first handshake's),
  psk modes exactly psk_dhe_ke, the platform payload
  re-disclosed, and application data crossing on the resumed
  session; a ticket resumes only once; a ticket with a
  corrupted PSK is refused; an expired ticket is refused; a
  psk_ke-only offer over mail is refused with a fatal
  illegal_parameter alert. Resumption is also exercised end
  to end through `EmailPipe`: a real signed job crosses
  inside the resumed session and its result returns inside
  it, exit code 0.
- Loss and provider shapes (12 tests): a lost first hello, a
  lost cookied hello, a lost server flight, and a lost client
  Finished each recover through endpoint retransmission; a
  lost ticket mail costs the ticket, not the session; parts
  of 1 flight arriving reversed answer nothing until the last
  part lands; a whole handshake with every flight segmented
  at 48 characters and reversed still establishes and carries
  data; a "Re: "-prefixed subject still routes; a body
  line-wrapped every 76 characters parses byte-exact; a
  provider footer appended to the body breaks the flight
  closed (`dtls-invalid`, no session, no application data),
  as does a subject suffix. Through the pipe, a
  footer-rewritten DTLS mail is consumed and delivers no job.
- 1 finding the tests forced: an early version of the
  lost-HelloRetryRequest test expected the attempt to fail
  closed, on the theory that exact-duplicate suppression
  would not re-answer a replayed hello. That is wrong: a
  retransmitted hello is not bit-exact -- its record sequence
  bytes advance -- so duplicate suppression (which stops the
  same mail delivered twice, bit for bit) does not eat it,
  and the stateless cookie issuer answers again. The case
  recovers, and the test pins the true behavior.
- Results, as read from the runs:
  `runner.tests.test_dtls_email_v3`: 45 tests, OK, 0 skips.
  Combined touched suites (the same 7 modules as above):
  469 tests, OK, skipped=1 -- the same pre-existing,
  registered skip ("unconnected UDP sends are blocked in
  this environment; a DTLS server cannot run here (the
  pipe-level tests cover the same code over a connected
  socket)"). No new skip reasons; the skip registry was not
  touched.

## The live mailbox run

A separate throwaway runner instance was stood up from this
branch's tree in its own directory (`~/workspace/hp-v3-live`,
never the standing runner), with its own config, a fresh
shared secret, and `dtls_via_email` enabled, against the
dedicated runner mailbox over real IMAP and SMTP (OAuth
credentials already on file; the preflight connected,
authenticated, and selected the inbox). A client driver on
this VM ran 1 real session end to end over that mailbox:

- The handshake completed over real mail: ClientHello,
  HelloRetryRequest, second ClientHello, server flight,
  Finished. The platform disclosure arrived in the handshake:
  the family-tier card for the runner's machine (linux, sh,
  protocol versions [1]).
- 1 real signed and encrypted ping job (`v3-live-job-4`)
  crossed inside the session. The runner's log shows it
  delivered from a DTLS session to the runner core, executed
  once (exit 0), and its result sent inside its session; the
  client verified the in-session result (type result,
  exit code 0).
- The throwaway instance was stopped afterwards. The
  standing runner was never touched.

3 earlier attempts failed, and what stopped them is part of
the record:

- Attempts 1 and 2 drove the client with a harness that fed
  any DTLS mail it fetched, regardless of mail session-id.
  Stale flight mail from earlier sessions in the same mailbox
  poisoned the client's transcript: the server refused 1
  handshake on a PSK binder mismatch, and records offered to
  a live session under keys from a stale flight did not
  decrypt and were dropped; the unanswered session was
  abandoned after 60 seconds. The server failed closed in
  every case; nothing was misrouted into the job path.
- Attempt 3 filtered by mail session-id but fetched with
  plain RFC822 fetches. An RFC822 fetch sets the \Seen flag,
  so the harness marked its own second ClientHello seen
  before the runner's pass could fetch it, and the runner
  never received it: no session, no flight, no refusal -- the
  mail was simply gone from every later UNSEEN search.
- The working discipline, used by the successful run: the
  client fetches with BODY.PEEK[] (no \Seen side effect),
  binds fetched mail to its own mail session-id, and marks
  seen only the replies it actually consumes.
- Finding: on a shared mailbox, fetch semantics are part of
  the carriage's correctness surface. A consumer that fetches
  DTLS mail with side effects starves the other consumers,
  and a sender-side harness that does not bind mail to its
  own session-id can be poisoned by stale flights. Both
  failure modes fail closed; neither reaches the job path.

## What is not proven here

- Resumption over a live mailbox: resumption is proven at
  the carriage layer and through the production pipe, but
  the live run exercised 1 fresh session only.
- Provider rewriting beyond the tested shapes: the live
  provider delivered the test flights without
  rewriting them. The footer and subject-suffix cases remain
  synthetic, as do other providers.
- Live scale: the live run carried 1 session and 1 job.
  Many sessions, many jobs, and multi-job sessions over a
  live mailbox are not exercised.
- The unaddressed legacy harness shape remains a local testing
  shape, as the specification states; it is not a deployment
  surface.

## Release-gate repair for 3.15.125 (2-Nov-2026)

The 3.15.125 tag build failed on 2 assertions. Both were
checked first-hand; the determinations are recorded here
because one of the 2 fixes moves a proof pin.

1. Provider name in live docs. The plan and this record named
   the mail provider of the live run. Live docs name no
   provider; both files now say "the provider" / "other
   providers". The record is unchanged in substance: 1 live
   provider, which delivered the flights unrewritten, and no
   other provider tried.
2. C20's transports pin (`test_c20_channel_envelopes_face_the
   _core_gate`). The pin asserted that the first
   `_dtls_secret_material` hand-over in
   `runner/wire/transports.py` sits after the
   `if name == "dtls":` branch head. The carriage added a
   second hand-over site inside the email branch, above the
   dtls branch, so the measured offsets inverted (28356 not
   less than 28118). Determination: a structural pin, not an
   ordering regression. The email site is guarded by
   `if cfg.get("dtls_via_email") is True:` -- the email pipe
   receives the secret material only under the owner's
   literal-true opt-in, when it terminates DTLS itself, which
   is the dtls pipe's exception under the same rule, and the
   carriage is off otherwise with the secret boundary
   unchanged. No session envelope reaches the core gate by a
   new path: session application data still becomes an
   ordinary envelope delivered to the core, and the pipe-level
   tests (a signed job round trip inside a session, a
   cleartext job inside a session refused, a session result
   never downgraded) pass unchanged. The pin now counts the
   hand-over sites (exactly 2) and orders each against its
   branch and the guard, which is the invariant C20 states.

## Review pass over the 2 peer reviews (2-Nov-2026)

2 peer reviews of this build were posted in the forum on
2-Nov-2026 (5:38pm, a read of branch commit `4cc16fe0`;
6:10pm, a full review of the merged draft with an RFC
companion). Every item was verified first-hand against the
merged tree or a primary source; what held landed on main.
The forum entry of this date carries the full decision
record with justifications; this section records the
dispositions and the code evidence.

Short review (5:38pm):

- Section 9.2 / plan D6 overclaim: HELD. `_addr_for` builds
  `"email:" + (session_id or "legacy")`; no configured peer
  identity exists in the code. Section 9.2 and D6 rewritten
  to the code (cookie key is the responder's own secret;
  the handshake's PSK identity selects the key).
- Duplicate split: HELD. The digest cache dropped every
  repeat in both wrappers; the engine escaped only because
  retransmits advance record sequence numbers. Implemented:
  a handshake-phase digest hit re-posts the saved last
  flight under a fresh transfer id; application data drops.
  The connection-ID binding check already ran before the
  digest cache and is now stated in Section 7.2.
- Absolute reassembly deadline: HELD. `offer` refreshed the
  idle stamp on every part. `created` + deadline added; a
  drip test pins it.
- Pending-result expiry: HELD, and the keying was weaker
  than the review's minimum: results were held by job ident
  alone. Keyed by (connection ID, job ident); expiry by age
  (7 days default), count (64), and total bytes (16 MiB);
  expiry drops and logs, never sends.
- MIME frame: JUDGMENT CALL, taken as the review proposed:
  the frame now rides in a dedicated
  `application/hp-dtls3` part, base64; a present typed part
  is the only frame source and quoted-printable is refused;
  the naked shape is still read when no typed part exists.
  Justification: fail-closed was a reaction to a broken
  frame, and the failure it guarded (garbage reaching the
  engine) is still closed -- the typed part is the frame,
  garbage in it still classifies `dtls-invalid`, and the
  naked-shape footer test still delivers no job. The
  full-handshake-over-MIME test carries a signed job end to
  end.
- Section 16.1 harvest limit and hybrid slot: HELD. The
  limit is stated; RFC 7748 is cited; the slot is named
  (X25519MLKEM768, RFC 10024) after verification against
  the primary source: Standards Track, August 2026, IANA
  value 4588 (0x11EC), DTLS-OK Y, Recommended Y.
- Proof staleness: PARTLY SUPERSEDED at the review's read
  (the continuation commit already covered resumption and
  updated counts); the residue -- the plan's false status
  sentence and this record's header -- is fixed in this
  pass. The suggested rebase was not followed: the build
  was merged at the owner's word instead.

Full review (6:10pm), in its order:

1. Version 1 objects text: ACCEPTED (abstract, Section
   10.1). Title/docname rename: NOT LANDED -- the owner's
   call, recorded open in the forum entry. The review's
   worry about `v: 3` does not hold: that field is the
   drafting toolchain's XML vocabulary version and version
   1's -03 source carries the same value.
2. Section 9.2 replacement: ACCEPTED; verified clause by
   clause against `dtlsproto.py` and `dtls_mailbox.py`.
3. MIME part: ACCEPTED (see the judgment call above).
4. Retransmission/duplicates: ACCEPTED. "Carrying the
   same datagram" deleted (RFC 9147 Section 5.2); the
   split implemented (item above); timer floor in Section
   7.1 under Section 5.8.2 of RFC 9147.
5. Section 16.1, the slogan, "2 ways", the firewall
   sentence: ACCEPTED; specifics verified as above.
6. Minors: session-id ABNF ACCEPTED (the code already
   enforced it: `_SESSION_ID_RE`, `valid_session_id`);
   0-RTT rejection ACCEPTED WITH A CODE CHANGE (the engine
   previously ignored the extension; `_on_hello_bytes` now
   drops an early-data ClientHello before cookie handling);
   ticket single-use MUST ACCEPTED (code already one-shot:
   `del self.core.tickets[identity]`); Re:/Fwd: rule
   ACCEPTED WITH A CODE CHANGE (the subject regex was used
   with `search()`; routing now strips at most 1 prefix and
   full-matches); IMAP BODY.PEEK ACCEPTED WITH A CODE
   CHANGE (`fetch_job_mails` fetched `(RFC822)`, which
   sets \Seen); bounds ACCEPTED (items above); Section 11
   precondition ACCEPTED (verified in `begin`: the binder
   comparison precedes key derivation, and the platform
   payload is consulted only after it).
7. Bounds: ACCEPTED (reassembly deadline, result expiry,
   digest cache named as an optimization, `bytes=` 1
   sentence).
8. References and rendering: ACCEPTED. RFC 5234, RFC
   4648, RFC 7748, RFC 5322, RFC 8551, RFC 9051, RFC 10024
   added; RFC 9146 kept, following version 1 -03's own
   citation of it; the version 1 reference is pinned to
   -03. `dtls_over_email` corrected to `dtls_via_email`
   (3 strings). Rendered with kramdown-rfc 1.7.43 and
   xml2rfc 3.35.0: `.xml`, `.txt`, `.html`, 0 warnings.
   idnits was NOT run: it is not installed on this machine
   and the npm registry has no package under that name
   (404) -- recorded as not run rather than claimed.
   Discovery hint: PREPARED, NOT LANDED (forum entry
   carries the text; the owner's call).

Tests: `runner/tests/test_dtls_email_v3.py` grew from 45 to
62 tests; the 13 new-behavior assertions failed before the
implementation and pass after (2 test bugs of this pass's
own were caught by running and fixed). The release-gate
batch (this record's constraints module, the provider-name
discipline, the skip registry, the version 3 module) runs
121 tests green, 0 skips, and every touched-surface suite
(mailbox, transports, the email pipe, the TLS 1.3 and DTLS
protocol suites) is green unfiltered.
Still unproven, unchanged from the continuation: resumption
over a live mailbox, providers other than the 1 live
provider, and live scale beyond 1 session carrying 1 job.

## Final pass (2-Nov-2026)

A final adversarial review of the draft (protocol
correctness, sending-side implementability, scope and
upstream inheritance), the read-back items on the revision
(re-post budget, cookie key across restarts, held results
bound to the PSK identity), a review-pass document reporting
2 defects in the held-result path, and an audit of every
decision in this arc were each verified first-hand. The
forum entry of this date carries the decision ledger; this
section records the behavior changes and the corrections to
this record.

Corrections to the record above:

- The discovery hint is LANDED, not prepared: the sentence
  stands in the draft's Section 4.3 (a platform card may
  state, as an unauthenticated fact, that the runner offers
  this carriage; the fact is trusted for nothing except
  whether an attempt is worth making), and `PROTOCOL.md`
  links the draft as local and unsubmitted. The review-pass
  section's "PREPARED, NOT LANDED" line is superseded.
- Test counts: the module stood at 62 at the review pass,
  74 after the held-result fixes released in 3.15.130, and
  82 after this pass, each count from a full unfiltered run
  of `runner/tests/test_dtls_email_v3.py`, 0 skips.

Behavior changes in this pass:

- The production sender's frame part is a leaf part.
  `build_flight_message` attached the frame as a whole
  message object, which wrapped it in a `message/rfc822`
  container one level below where Section 5.2 puts it; it
  now attaches the frame as bytes, a direct leaf part. The
  receiver is unchanged and reads the wrapped shape where
  it is met. Tests pin the leaf shape and a full handshake
  carried entirely over the sender's own serialization.
- A fragmented first ClientHello is refused by the carriage
  itself: the classifier no longer calls it an
  initialization, and the datagram classifies `dtls-invalid`
  (no answer, no state), where before it was fed to the
  engine and refused there. The outcome is unchanged; the
  refusal now sits where Sections 8.2 and 16.4 put it. A
  test pins the parse kind and the silent pipe.
- The session-hold sidecar writes through the tree's one
  atomic writer (`runner/guard/atomicio.py`), not a
  hand-rolled temp name.

Verified, not changed:

- The held-result fixes of 3.15.130 (a `<ident>.session.txt`
  sidecar restores the hold across a restart; an expiry
  drops only the holds whose results it dropped) were
  probed independently of their landed tests: the sidecar
  survives the runner core's own inbox fetch (it is acked
  to the inbox's done folder with the job file and restored
  from there), a restored hold still expires and is never
  sent, and a later session under the same key receives the
  held result after the restart.
- The re-post budget and the cookie key kept in the channel
  (both landed with the read-back fixes) hold under an
  independent duplication probe -- every mail in both
  directions delivered twice: 32 mail movements, exactly 1
  established session, the application message delivered
  exactly once -- and under cookie-key corruption cases
  (garbage, short, and empty key files each draw a fresh
  owner-only key with a warning, and the server builds).
- Combination cells landed as tests: a gateway-shaped
  flight (segmented, text-part footer, parts reversed, 1
  part delivered twice) frames 1 datagram; early data
  spliced into a segmented, prefixed hello is rejected as a
  property of the reassembled datagram; 1 `Re:` prefix on a
  quoted-printable typed part classifies `dtls-invalid`;
  2 keys carrying 1 job ident with both sessions live run
  the job once and answer only the carrying session.

Still unproven, updated: resumption over a live mailbox,
providers other than the 1 live provider, live scale
beyond 1 session carrying 1 job, the production MIME
sender on a live mailbox (this pass's sender experiments
are local serialization round trips), and a restart in the
middle of a live handshake. Resumption across a responder
restart is not possible by design -- the ticket table is
process memory -- and is recorded here so the unproven
list is not read as awaiting that run.
