# Findings — docs/steady/networking.md

Source: docs/steady/networking.md, reviewed at main cbb52068.
Sentence units: 37. Flagged: 3. Categories: pre-release 37, post-release 0.

Units 3, 6 and 10 are the bold numbered lead-ins of the document's 3 trust-boundary items, split from their sentences by the source formatting; each is recorded as extracted and flagged, and its sentence completes in the following unit.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "What talks to what in a Homing Pigeon…" | pre-release | flows |  |
| 2 | "The protocol's transport is a mailbox; the network…" | pre-release | flows |  |
| 3 | "**1." | pre-release | flagged | Lead-in split from its sentence by the formatting; the sentence completes in the next unit |
| 4 | "The mailbox is untrusted transport.** The HMAC crosses…" | pre-release | flows |  |
| 5 | "A job sent `--cleartext` is the exception: the…" | pre-release | flows |  |
| 6 | "**2." | pre-release | flagged | Lead-in split from its sentence by the formatting; the sentence completes in the next unit |
| 7 | "Loopback is the perimeter for local services.** Inference…" | pre-release | flows |  |
| 8 | "The Oracle page has no login because there…" | pre-release | flows |  |
| 9 | "A host firewall rule pinning :11434/:11436 to loopback…" | pre-release | flows |  |
| 10 | "**3." | pre-release | flagged | Lead-in split from its sentence by the formatting; the sentence completes in the next unit |
| 11 | "The job is the untrusted principal.** A signed…" | pre-release | flows |  |
| 12 | "Its network edge is currently unrestricted: a job…" | pre-release | flows |  |
| 13 | "This is the edge all firewall work is…" | pre-release | flows |  |
| 14 | "Three slots, deliberately separate:" | pre-release | flows |  |
| 15 | "**Sense (read-only).** The `firewall` sense (`docs/extend/senses.md`) watches host…" | pre-release | flows |  |
| 16 | "Neither blocks anything." | pre-release | flows |  |
| 17 | "Safe to leave on everywhere." | pre-release | flows |  |
| 18 | "**Cage (opt-in enforcement).** Linux: bwrap with `--unshare-net` (loopback-only…" | pre-release | flows |  |
| 19 | "Windows: per-user WFP rules tied to the job…" | pre-release | flows |  |
| 20 | "The firewall *sense* verifies the cage held —…" | pre-release | flows |  |
| 21 | "**Egress policy (opt-in enforcement).** Per-job-identity allowlists." | pre-release | flows |  |
| 22 | "This closes the phone-home shape: a job that…" | pre-release | flows |  |
| 23 | "Named as a gap in `docs/security/security-gaps.md`; designed here…" | pre-release | flows |  |
| 24 | "Enforcement never rides the sense path." | pre-release | flows |  |
| 25 | "Senses file alerts; the runner enforces; the Oracle…" | pre-release | flows |  |
| 26 | "That split is load-bearing — see `docs/extend/senses.md` ("why…" | pre-release | flows |  |
| 27 | "What ships and what does not, item by…" | pre-release | flows |  |
| 28 | "**NIDS** — Zeek/Suricata as a network-side sense next…" | pre-release | flows |  |
| 29 | "This ships: the `suricata-feed` and `zeek-feed` adapters in…" | pre-release | flows |  |
| 30 | "**DNS monitoring** — the exfiltration channel." | pre-release | flows |  |
| 31 | "A per-job DNS log correlated by `job_id_hint` is…" | pre-release | flows |  |
| 32 | "**Canary tokens** — the runner plants three tripwire…" | pre-release | flows |  |
| 33 | "A read that changes one, or a delete,…" | pre-release | flows |  |
| 34 | "Canary credentials (a token that phones home when…" | pre-release | flows |  |
| 35 | "**FIM proper** — file integrity monitoring ships as…" | pre-release | flows |  |
| 36 | "**TLS inspection and a WAF** — not built;…" | pre-release | flows |  |
| 37 | "There is no inbound HTTP service today (the…" | pre-release | flows |  |
