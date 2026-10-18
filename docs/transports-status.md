# Transport implementation status

Email is implemented directly in `runner/runner.py` (SMTP send, IMAP
poll, seen-marking ack). There is no transport adapter module: the
`runner/transports.py` experiment was removed as dead code — the
runner was never wired to it, and its Cloudflare Queues sketch
targeted an API we have not tried yet.

| Transport | State |
|-----------|-------|
| email | implemented, this is what we test |
| cloudflare | listed in FUTURE.md |

The send/poll/ack contract is described in TRANSPORTS.md. Do not add
transports unless asked; NATS/MQTT/Redis/etc. were cut on purpose.
