# Findings — docs/steady/project/industry-map.md

Source: docs/steady/project/industry-map.md, reviewed at main cbb52068.
Sentence units: 72. Flagged: 0. Categories: pre-release 65, post-release 7.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "How the commercial security world moved from 2021…" | pre-release | flows |  |
| 2 | "The design goal: prefer security technologies that cost…" | pre-release | flows |  |
| 3 | "Target: runs on a laptop with a few…" | pre-release | flows |  |
| 4 | "Stripped-down installs skip the extras." | pre-release | flows |  |
| 5 | "Corollary: **where the kernel already does the work,…" | pre-release | flows |  |
| 6 | "Anything that needs a resident daemon, line-rate processing,…" | pre-release | flows |  |
| 7 | "**2021–22: the land-grab.** CrowdStrike buys Humio (~$400M) for…" | pre-release | flows |  |
| 8 | "**Spring 2023: the copilot wave.** Security Copilot (Mar…" | pre-release | flows |  |
| 9 | "Chat assistants bolted onto existing platforms." | pre-release | flows |  |
| 10 | "**2023–24: consolidation at scale.** Cisco buys Splunk ($28B)." | pre-release | flows |  |
| 11 | "Thoma Bravo takes Darktrace private ($5.3B) — after…" | pre-release | flows |  |
| 12 | "Exabeam merges with LogRhythm: the end of standalone…" | pre-release | flows |  |
| 13 | "**2025: copilot becomes agent.** Agentic triage and investigation…" | pre-release | flows |  |
| 14 | "The vocabulary flips; the products start acting without…" | pre-release | flows |  |
| 15 | "**2026: everyone ships agents; the evidence layer gets…" | pre-release | flows |  |
| 16 | "The newest turn: **baselining the agents themselves** —…" | pre-release | flows |  |
| 17 | "Google's $32B Wiz acquisition closes: the largest security…" | pre-release | flows |  |
| 18 | "**Underneath it all: the backbone never moved.** Suricata,…" | pre-release | flows |  |
| 19 | "Every AI SOC still reasons in ATT&CK IDs…" | pre-release | flows |  |
| 20 | "Primitives beat platforms." | pre-release | flows |  |
| 21 | "**Stuck:** agentic triage/investigation; behavioral analytics as an embedded…" | pre-release | flows |  |
| 22 | "**Fizzled:** standalone UEBA; standalone deception vendors (Attivo was…" | pre-release | flows |  |
| 23 | "**ACLs** — the example." | pre-release | flows |  |
| 24 | "Partly in place: the Windows one-home install sets…" | pre-release | flows |  |
| 25 | "Extend per `docs/security/security-gaps.md`." | post-release | flows |  |
| 26 | "**Linux capabilities** — drop everything a job doesn't…" | pre-release | flows |  |
| 27 | "A few lines, zero runtime cost." | pre-release | flows |  |
| 28 | "Partly there via bwrap; make it explicit per…" | post-release | flows |  |
| 29 | "**seccomp-bpf** — syscall filter per job profile." | pre-release | flows |  |
| 30 | "Cheap, set once." | pre-release | flows |  |
| 31 | "**Windows integrity levels + job objects** — free,…" | pre-release | flows |  |
| 32 | "Unused today; candidate." | pre-release | flows |  |
| 33 | "**Kernel audit (auditd / SACLs / ETW)** —…" | pre-release | flows |  |
| 34 | "An audit-log sense costs almost nothing." | pre-release | flows |  |
| 35 | "**eBPF observability** — ~1–3% overhead for syscall visibility…" | pre-release | flows |  |
| 36 | "Optional sense on Linux; integrate, don't build." | post-release | flows |  |
| 37 | "**Canary tokens and files** — zero cost until…" | pre-release | flows |  |
| 38 | "The runner plants three tripwire files in its…" | pre-release | flows |  |
| 39 | "**Firewall posture reads** — one line in the…" | pre-release | flows |  |
| 40 | "Not a packet capture." | pre-release | flows |  |
| 41 | "The ruleset-diff daemon in the senses doc is…" | pre-release | flows |  |
| 42 | "**YARA on job artifacts** — only files that…" | pre-release | flows |  |
| 43 | "ClamAV the same way, and only through `clamdscan`." | pre-release | flows |  |
| 44 | "**ATT&CK IDs on sense output** — on the…" | pre-release | flows |  |
| 45 | "Zero runtime cost." | pre-release | flows |  |
| 46 | "A label, not a verdict." | pre-release | flows |  |
| 47 | "**Zeek/Suricata as a collector** — real CPU on…" | pre-release | flows |  |
| 48 | "Optional netmon sense, off unless enabled." | pre-release | flows |  |
| 49 | "**Full AV scan hooks** — on demand, never…" | pre-release | flows |  |
| 50 | "**Guard-model triage (Llama Guard shape)** — only when…" | pre-release | flows |  |
| 51 | "Costs RAM/VRAM otherwise." | pre-release | flows |  |
| 52 | "**Statistical anomaly baselining** — even Microsoft has been…" | pre-release | flows |  |
| 53 | "Don't ship this until it's good." | post-release | flows |  |
| 54 | "Honestly not built." | pre-release | flows |  |
| 55 | "Line-rate NDR, 24/7 ML pipelines, cloud-scale telemetry economics." | pre-release | flows |  |
| 56 | "We're a personal runner, not a platform." | pre-release | flows |  |
| 57 | "Of the two candidates, the action log exists…" | pre-release | flows |  |
| 58 | "**Nobody watches the Oracle.** The industry's newest category…" | pre-release | flows |  |
| 59 | "Our Oracle calls tools with no record beyond…" | pre-release | flows |  |
| 60 | "Candidate: an Oracle action log as a sense." | post-release | flows |  |
| 61 | "The calls already flow through one place; recording…" | pre-release | flows |  |
| 62 | "**No guardrail below the Oracle.** ClawArmor's whole pitch…" | pre-release | flows |  |
| 63 | "Our cage protects the host *from jobs*; nothing…" | pre-release | flows |  |
| 64 | "Candidate: an Oracle tool-call policy." | post-release | flows |  |
| 65 | "Option for later." | post-release | flows |  |
| 66 | "**Bespoke tool protocol.** The industry is standardizing agent…" | pre-release | flows |  |
| 67 | "Out of scope for now — noted, not…" | pre-release | flows |  |
| 68 | "**The Oracle inventing log events** is exactly the…" | pre-release | flows |  |
| 69 | "The fix is the same in both cases:…" | pre-release | flows |  |
| 70 | "The anti-fabrication rule in the Oracle's instructions is…" | pre-release | flows |  |
| 71 | "Not an XDR, not a UEBA product, not…" | pre-release | flows |  |
| 72 | "The architecture — thin senses, Oracle fusion, DRI…" | pre-release | flows |  |
