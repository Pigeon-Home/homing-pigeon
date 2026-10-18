# Future

Ideas...

## The message

- Encrypted credentials at rest
- Ack messages
- Per-job encryption & transport enc

## The pipe

- Cloudflare Queues: The design notes are TRANSPORTS.md

## Before a job runs

- An approval gate: the owner says yes before the job runs.
  `docs/approval-gate-design.md`
- A discussion with the Oracle before the job runs. The Oracle
  can suggest a change, or apply one. A small protocol field
  carries the suggestion or the revised job. Nothing else in
  the message changes.
- The job still runs as sent. The Oracle has local context the
  sender does not, and files a suggestion on the result. Or a
  "help me, local agent Kenobi..." job kind, where the Oracle is
  allowed to modify the job before it runs.
- A remote agent rarely knows the box: the OS, the tools on
  PATH, the versions, what is installed. An Oracle option
  attaches full platform metadata to every result, so the
  sender stops guessing.

## Who signs

- Ed25519 signatures instead of the shared HMAC secret.
  `docs/asymmetric-signing-design.md`

## What you see

- A loopback dashboard for the Oracle. ORACLE_DASHBOARD.md.
  `--oracle` and `--oracle-cli` are the current.

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

## Misc

- NATS, MQTT, Redis, Postgres, Durable Objects, and the local
  socket. Cut. TRANSPORTS.md.
- SMS paging. `docs/dri-playbook.md`.
- TLS inspection and a WAF. `docs/networking.md`.
- Line-rate network detection, a 24/7 ML pipeline, and adopting
  MCP. `docs/industry-map.md`.
- Statistical anomaly baselining. `docs/industry-map.md`.
- Turning the default hardening on. It stays opt-in.
  `docs/security-gaps.md`.
- The security of the mailbox provider, and a secret that has already leaked.
  SECURITY.md.
