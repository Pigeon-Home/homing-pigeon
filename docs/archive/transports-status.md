# Transport implementation status

> **Archived 2026-10-22.** A short status table superseded by
> [docs/TRANSPORTS.md](../TRANSPORTS.md), which is current.

Transports are extensions in full. The runner core is
transport-blind: `runner/transports.py` is the contract,
discovery, and supervision module (TRANSPORT_API_VERSION = 1),
and every transport — email included — is a standalone
extension program under `runner/transport_extensions/` with an
`extension.json` manifest. The runner never imports extension
code; it supervises each extension as a child process and
talks to it through a file channel. The contract is described
in TRANSPORTS.md. Ack is consumption: the runner moves a
processed job file into the channel's `inbox/done/`.

| Transport | State |
|-----------|-------|
| email | implemented (extension over `runner/mailbox.py`: IMAP poll, SMTP send, seen-marking ack); the default-enabled transport, and the test transport |
| file | implemented (watched folder) |
| nats | implemented (core NATS pub/sub; broker authentication required by default) |
| dtls | implemented (DTLS session listener; off unless enabled) |
| cloudflare | design notes in TRANSPORTS.md only; not built |

MQTT, Redis, Postgres, and Durable Objects were cut on purpose
(FUTURE.md). Do not add transports unless asked.
