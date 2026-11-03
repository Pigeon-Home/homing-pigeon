# Recorded live mail: version 3 (DTLS via email)

The exact flight mail of the 2 live mailbox runs of the
version 3 carriage, kept as fixtures so the live runs replay
offline forever. The tests that replay them are in
`runner/tests/test_dtls_email_v3_live.py`.

## The runs

- **run1** — mail session `v3-live-4`, job `v3-live-job-4`.
  The live mailbox run recorded in
  `docs/proofs/dtls-over-email-v3.md`: a full handshake with
  a HelloRetryRequest, the family platform card carried
  in-handshake, a signed and encrypted ping executed once,
  and the result returned inside the session. 18 mails.
- **run4** — mail session
  `7f57fb2802395abcd64eff696769e813`, job
  `76afac0d-f002-4532-8b22-9444233b5700`. A second live run
  over the same mailbox path with a sole poller: handshake
  with HelloRetryRequest, the job sent inside the session
  once the session stood established, the result received
  inside the session and verified. 38 mails.

In both runs the job and the result crossed inside the
session, as protected flight mail — never as ordinary job
or result mail. The `job-flight` and `result-flight` roles
in the manifest name the mails that carried them.

## The files

Files are named `<run>-<order>-<mailbox id>.eml`, in the
order the mailbox recorded them (arrival time ascending).
`manifest.json` lists every file with the run's session id
and job id, the direction (client or server side), a role,
and the SHA-384 of the fixture file's bytes. Roles for the
plaintext handshake mails name the message (client-hello,
hello-retry-request, cookied-client-hello, server-hello);
protected datagrams are named by their place in the run
(server-flight, client-flight, job-flight, result-flight,
protected-record), since their contents are encrypted
under the session's keys.

## Recording fidelity

Each fixture carries every header of the stored message in
its stored order and the exact decoded body. The stored
messages carry the body in quoted-printable form; the
mailbox connector returns the decoded body, and the decoded
body is what the receiver path consumes — the mail parser
decodes the transfer encoding before the carriage ever
sees the frame. The one header that describes the body's
form in the file, Content-Transfer-Encoding, is therefore
written as 8bit to match the decoded body the file holds.
Nothing else is altered: subjects, frame headers, digests,
and datagrams are exactly as recorded, and the frame
digests inside the mail check out against the datagrams
under the carriage's own parser.

The runs' shared secrets are not recorded here and are not
needed: the replay works at the carriage layer — the
flights classify and parse, the handshake sequence
assembles in order (the HelloRetryRequest cookie is
checked against the first ClientHello by its SHA-384, the
way the stateless cookie binds the 2 hellos), and the job
and result flights are pinned to their session by subject,
order, and size.
