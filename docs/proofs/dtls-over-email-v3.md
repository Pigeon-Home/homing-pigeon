# DTLS over email, version 3: what was built and tested

Local branch `homing-pigeon-v3` (created as `together`,
renamed 2-Nov-2026), 2-Nov-2026; continuation below dated
2-Nov-2026 (run logs stamped 3-Nov-2026 UTC). The branch is
pushed to GitHub for review; nothing is merged to main and
nothing is submitted; the version 3 draft is a local,
unsubmitted document.

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
  `dtls_over_email` option on (literal boolean true only), the
  email pipe classifies DTLS mail before job delivery, feeds
  it to the DTLS server in its own process, marks it seen
  whether it answered, is incomplete, or was malformed,
  delivers session jobs to the runner core as ordinary
  envelopes under their own job ids, and sends a session job's
  result inside its session -- or leaves the result file
  waiting. There is no downgrade to an ordinary mail result.
- `runner/wire/transports.py` -- the email extension is handed
  the DTLS secret material and the disclosure posture only
  when `dtls_over_email` is enabled; the secret boundary is
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
shared secret, and `dtls_over_email` enabled, against the
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
  provider (Gmail) delivered the test flights without
  rewriting them. The footer and subject-suffix cases remain
  synthetic, as do providers other than Gmail.
- Live scale: the live run carried 1 session and 1 job.
  Many sessions, many jobs, and multi-job sessions over a
  live mailbox are not exercised.
- The unaddressed legacy harness shape remains a local testing
  shape, as the specification states; it is not a deployment
  surface.
