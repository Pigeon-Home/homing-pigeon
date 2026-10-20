# Networking picture

What talks to what in a Homing Pigeon deployment, drawn as trust
boundaries. The protocol's transport is a mailbox; the network
story is which edges exist, which are loopback-pinned, and where
a firewall — as sense or as enforcement — watches or bites.

## The edges

```
  submitter ──(internet)──► mailbox (IMAP/SMTP over TLS) ◄──(poll)── runner
  (anywhere)                 provider sees everything         (the box)
                                    │
                    result ─────────┘  (same mailbox, or signed reply_to)

  On the box itself:

  runner ──loopback──► Ollama 127.0.0.1:11434   (inference)
  owner  ──loopback──► Oracle page 127.0.0.1:11436 (chat UI)
  job    ── ??? ────►  anywhere                  (the open edge)
  sensor daemons ──local──► Oracle ingest (signed sensor_alert jobs)
```

## Trust boundaries

**1. The mailbox is untrusted transport.** The HMAC crosses
it safely, and per-job encryption — the default — means the
provider holds ciphertext for job and result bodies; it can
still read subjects, timing, and sizes (IETF draft §16,
§17.2). Nothing in the design needs the transport to be
honest — and nothing secret should assume otherwise. A job
sent `--cleartext` is the exception: the provider can read
that one end to end.

**2. Loopback is the perimeter for local services.** Inference
and the Oracle page bind 127.0.0.1 and the runner refuses
non-loopback inference endpoints in code
(`_endpoint_is_loopback`). The Oracle page has no login
because there is no route to it from off the box; loopback
*is* the authentication. A host firewall rule pinning
:11434/:11436 to loopback is defense in depth, not the
mechanism — the bind address is.

**3. The job is the untrusted principal.** A signed job runs
as the runner's account — by the owner's explicit call, that
is an admin account by default. Its network edge is currently
unrestricted: a job can open any outbound connection the
account can. This is the edge all firewall work is about, and
it is the one edge the project had never drawn until now.

## Where the firewall fits

Three slots, deliberately separate:

- **Sense (read-only).** The `firewall` sense
  (`docs/senses.md`) watches host firewall state, rule diffs,
  and new listeners; the `netmon` sense watches flows and
  DNS. Neither blocks anything. Safe to leave on everywhere.
- **Cage (opt-in enforcement).** Linux: bwrap with
  `--unshare-net` (loopback-only jobs) in enforce mode (M6).
  Windows: per-user WFP rules tied to the job identity
  (M8 `--run-as`) — **not built; the Windows cage is parked**
  and no WFP rules are written today. The firewall *sense*
  verifies the cage held — check, don't trust.
- **Egress policy (opt-in enforcement).** Per-job-identity
  allowlists. This closes the phone-home shape: a job that
  exfiltrates over its own connection prints nothing, so the
  Oracle's secret-scanner never sees it. Named as a gap in
  `docs/security-gaps.md`; designed here when the owner
  wants it.

Enforcement never rides the sense path. Senses file alerts;
the runner enforces; the Oracle fuses and decides. That split
is load-bearing — see `docs/senses.md` ("why this shape").

## What the picture still lacks

Listed in FUTURE.md.

- **NIDS** — Zeek/Suricata as a network-side sense next to the
  host IDS. The `netmon` sense slot exists; a real collector
  does not yet.
- **DNS monitoring** — the exfiltration channel. A per-job
  DNS log correlated by `job_id_hint` is the sharpest
  available signal for "job talking where it shouldn't."
- **Canary tokens** — the runner plants three tripwire files
  under its state directory (`passwords.txt`, `backup-codes.txt`,
  `api-keys.txt`). A read that changes one, or a delete, is filed
  once and stays reported until the file is restored. Canary
  credentials (a token that phones home when used) are listed in
  FUTURE.md.
- **FIM proper** — file integrity monitoring. The roadmap's
  "snapshot eyes" gestures at it; no design yet.
- **Out of scope:** TLS inspection, WAF (there is no inbound
  HTTP service to protect — the Oracle page is loopback-only).
