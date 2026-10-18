# Future

This is the only list of work that is not built. A design file
describes the work. It does not keep a second status.

## The message

- Encrypted credentials at rest.
- Ack messages.
- Per-job encryption.
- Uploading a large result as a file instead of a mail body.
- Encrypting the message body on the transport. The sketch is
  ORACLE_DASHBOARD.md, section 6.1.

## The pipe

- Cloudflare Queues. Email is the only transport in the runner.
  The design notes are TRANSPORTS.md.

## Before a job runs

- A human says yes before the job runs.
  `docs/approval-gate-design.md`.
- The semantic judge: ask the local model for a verdict before
  execution. The deterministic checks are already shipped.
  PROTOCOL.md, section 9.3.

## Who signs

- Ed25519 signatures instead of the shared HMAC secret.
  `docs/asymmetric-signing-design.md`.

## What you see

- A loopback dashboard for the Oracle. ORACLE_DASHBOARD.md.
  `--oracle` and `--oracle-cli` are the chat. They are not
  this dashboard.

## What the box notices

- A firewall ruleset hash, and a check that a job's network
  cage held. The on/off posture line is shipped.
  `docs/senses.md`.
- Per-job egress rules. `docs/senses.md`, `docs/networking.md`.
- Patch level, listening sockets, persistence, and disk
  encryption, as senses. `docs/senses.md`.
- A real netmon collector, a per-job DNS log, and canary
  credentials that phone home. `docs/networking.md`.
- File-integrity monitoring. No design yet.
  `docs/networking.md`.
- Signal and WhatsApp paging. Telegram is the channel that
  exists. `docs/dri-playbook.md`.
- An Oracle action log, and a policy on the Oracle's own tool
  calls. `docs/industry-map.md`.
- A check that the runner binary has not changed, a hash chain
  on the audit log, and checking SHA384SUMS during install.
  `docs/security-gaps.md`.
- Job review once message bodies are encrypted, and a separate
  Oracle signing key. `docs/job-review.md`.
- The local test chat waits for the result email.
  `docs/handoff-local-si.md`.

## Not a queue

These are written down so they are not mistaken for the list
above.

- NATS, MQTT, Redis, Postgres, Durable Objects, and the local
  socket. Cut. TRANSPORTS.md.
- SMS paging. `docs/dri-playbook.md`.
- TLS inspection and a WAF. `docs/networking.md`.
- Line-rate network detection, a 24/7 ML pipeline, and adopting
  MCP. `docs/industry-map.md`.
- Statistical anomaly baselining. `docs/industry-map.md`.
- Turning the default hardening on. It stays opt-in.
  `docs/security-gaps.md`.
- The security of Gmail, and a secret that has already leaked.
  SECURITY.md.
