# DTLS over email, version 3: what was built and tested

Local branch `together`, 2-Nov-2026. Nothing here is pushed
and nothing is submitted; the version 3 draft is a local,
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
- Commits on `together`: 714ab9e5 (plan), 0c763bfa
  (implementation and tests), 2b3fa4c0 (specification,
  future entry, plan addendum), and this note.

## What is not proven here

- A live mailbox: the round trips run over a fake shaped like
  the production intake, through the production pipe and the
  production core. No real IMAP or SMTP server, provider
  latency, or provider rewriting of messages is exercised.
- Loss and reordering against a live provider: reordering and
  duplication are exercised at the carriage layer with
  synthetic mail; a provider that rewrites bodies (wrapping,
  re-encoding) beyond what the parser already tolerates is
  not.
- Resumption over email end to end: the profile and the engine
  support it under the fresh-share rule, and the specification
  covers it, but no test in this family resumes a session over
  mail yet.
- The unaddressed legacy harness shape remains a local testing
  shape, as the specification states; it is not a deployment
  surface.
