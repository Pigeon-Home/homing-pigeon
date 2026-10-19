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
- A remote agent rarely knows the box: the OS, the tools on
  PATH, the versions, what is installed. An Oracle option
  attaches full platform metadata to every result, so the
  sender stops guessing.
- The Oracle's opinion, as a result member — BUILT 2026-10-18
  (Andrew, 2026-10-15, elaborated 2026-10-18). The design is
  `docs/oracle-opinion-design.md`; the member is specified in
  PROTOCOL 3.1/3.2 and implemented in `runner/opinion.py`:
  diagnose / advise / repair latitudes under the
  `oracle_opinion_mode` ceiling, deterministic tier-1 checks,
  an optional labeled model note, and the one mechanical
  repair (absent interpreter to platform default) re-judged
  before it runs. What remains future here: richer repairs
  beyond the mechanical one, and the opinion as a signed
  statement by the Oracle as an authenticated party in a
  confidentiality-on mode.

## Who signs

- Ed25519 signatures instead of the shared HMAC secret.
  `docs/asymmetric-signing-design.md`

## What you see

- A loopback dashboard for the Oracle (its spec was removed
  from the tree 2026-10-18; the idea stands).
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

## The hardware

- Accelerator Pis. Pi Light ships the deterministic Oracle
  because current Pis have no neural accelerator worth loading
  a model on, so the install downloads nothing. When a Pi
  generation ships an integrated NPU — or an AI-HAT-class
  board is on the box — the same install flips `oracle_mode`
  to `llm` and pulls a model. The mode is config, not
  architecture: the runner, the protocol, the briefs, and the
  records do not change.

## Misc

- NATS, MQTT, Redis, Postgres, and Durable Objects. Cut.
  (The local-signal socket shipped — signed `sensor_alert`
  envelopes only, not a job transport.) TRANSPORTS.md.
- SMS paging. `docs/dri-playbook.md`.
- TLS inspection and a WAF. `docs/networking.md`.
- Line-rate network detection, a 24/7 ML pipeline, and adopting
  MCP. `docs/industry-map.md`.
- Statistical anomaly baselining. `docs/industry-map.md`.
- Turning the default hardening on. It stays opt-in.
  `docs/security-gaps.md`.
- The security of the mailbox provider, and a secret that has already leaked.
  SECURITY.md.
