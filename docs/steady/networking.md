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
  job    ── confined ─► loopback only (Linux), nowhere (FreeBSD),
                        the account's reach (Windows: no net control)
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

**3. The job is the untrusted principal.** At the shipped
defaults a signed job does not run as the runner's account:
with `job_user` at `enforce` a POSIX job runs as the separate
job user, and with `confinement` at `enforce` it runs inside
the platform backend — on Windows under the confinement spawn
(a restricted token at low integrity, with the Job Object
ceiling; the POSIX demote itself does not exist there). Its
network edge is closed by confinement where the backend
carries a network control: loopback only on Linux, no network
at all on FreeBSD. The Windows backend carries no network
control, and a deployment that lowers confinement leaves the
edge at the account's reach: a job there can open any outbound
connection the account can. That open shape is the edge all
firewall work is about, and the edge this document draws.

## Where the firewall fits

Three slots, deliberately separate:

- **Sense (read-only).** The `firewall` sense
  (`docs/steady/oracle/senses.md`) watches host firewall state, rule diffs,
  and new listeners; the `netmon` sense watches flows and
  DNS. Neither blocks anything. Safe to leave on everywhere.
- **Cage (on by default: confinement defaults to enforce).** Linux: bwrap with
  `--unshare-net` (loopback-only jobs) in enforce mode.
  FreeBSD: a per-job jail with `ip4`/`ip6` disabled — no
  network at all. Windows: the confinement backend (Job
  Object, restricted token, low integrity) carries no
  network control, so a confined Windows job keeps the
  account's network reach; per-user WFP rules tied to the
  job identity are not built, and no WFP rules are written
  today. The firewall *sense* verifies the cage held —
  check, don't trust.
- **Egress policy (opt-in enforcement).** Per-job-identity
  allowlists. This closes the phone-home shape: a job that
  exfiltrates over its own connection prints nothing, so the
  Oracle's secret-scanner never sees it. Named as a gap in
  `docs/infrastructure-documents/security/security-gaps.md`; designed here when the owner
  wants it.

Enforcement never rides the sense path. Senses file alerts;
the runner enforces; the Oracle fuses and decides. That split
is load-bearing — see `docs/steady/oracle/senses.md` ("Why this shape").

## What ships and what the picture still lacks

What ships and what does not, item by item; the unbuilt ones that are
planned are in docs/FUTURE.md.

- **NIDS** — Zeek/Suricata as a network-side sense next to the
  host IDS. This ships: the `suricata-feed` and `zeek-feed`
  adapters in `runner/extensions/` fill the `netmon` sense,
  and the installer installs the collectors.
- **DNS monitoring** — the exfiltration channel. A per-job
  DNS log correlated by `job_id_hint` is the sharpest
  available signal for "job talking where it shouldn't."
- **Canary tokens** — the runner plants three tripwire files
  under its state directory (`passwords.txt`, `backup-codes.txt`,
  `api-keys.txt`). A read that changes one, or a delete, is filed
  once and stays reported until the file is restored. Canary
  credentials (a token that phones home when used) are not built
  and not planned.
- **FIM proper** — file integrity monitoring ships as two senses:
  `tripwire` (a tree's SHA-384 baseline) and `aide-feed` (AIDE's
  own report), both in `runner/extensions/`.
- **TLS inspection and a WAF** — not built; planned as sensor
  extensions. There is no inbound HTTP service today (the Oracle
  page is loopback-only), so they would watch the job's outbound
  traffic, not protect a listener.
