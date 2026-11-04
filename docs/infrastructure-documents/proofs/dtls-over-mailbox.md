# DTLS datagrams through the mailbox

The carriage is `runner/wire/dtls_mailbox.py`. The tests are
`runner/tests/test_dtls_mailbox.py`. Both passed here: a job
in the box is not a flight, and a handshake finishes, and a
ping inside the session arrives as the bytes `ping`.

## What was proven

Two cores, `DtlsClientCore` and `DtlsServerCore`, never handed
each other a datagram in memory. Each flight was one email
built by `send_mail`: subject `[HOMING-PIGEON] dtls`, body the
base64 of one datagram. The peer read it back with
`fetch_job_mails`, which is the same function the job poll
uses. A flight was marked seen. A job object in the same box,
subject `[HOMING-PIGEON] job ...`, was left unseen and was not
returned as a datagram.

The handshake ran to `established` on both sides. The client
then sent the application message `ping`. The server recorded
that payload.

## What was not proven

The box is in-process. It answers the UID commands
`fetch_job_mails` calls. It is not an IMAP server, and no
message crossed a network. There is no loss, no reorder, and
no second poller racing the first. The ping is three bytes,
not a job, and nothing was executed. A real mailbox that
rejects a long line, or a server that does not offer UID
commands, was not in the test.
