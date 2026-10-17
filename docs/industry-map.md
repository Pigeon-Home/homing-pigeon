# Industry map: five years of detection, read against Homing Pigeon

How the commercial security world moved from 2021 to 2026, and where this
project honestly stands against it. Not flattering on purpose.

## The footprint rule

The design goal: stuff in every security technology that doesn't cost much
CPU or compute on a local box. Target: runs on a laptop with a few gigabytes
of RAM — potentially slow, but workable. Stripped-down installs skip the
extras.

Corollary: **if the kernel gives it to you, take it.** ACLs, capabilities,
seccomp, namespaces, audit, integrity levels — these are nearly free because
the OS does the work. Anything that needs a resident daemon, line-rate
processing, or a second model running 24/7 has to justify itself.

## The five-year arc, in plain terms

- **2021–22: the land-grab.** CrowdStrike buys Humio (~$400M) for the data
  pipe; Microsoft buys RiskIQ (>$500M) and Mandiant ($5.4B); Palo Alto ships
  XSIAM (Feb 2022) selling "autonomous SOC" *before* LLMs existed.
- **Spring 2023: the copilot wave.** Security Copilot (Mar 2023, billed at
  $4/hr per compute unit — pricing analysts called unreasonable, and adoption
  showed it), SentinelOne Purple AI, CrowdStrike Charlotte AI. Chat assistants
  bolted onto existing platforms.
- **2023–24: consolidation at scale.** Cisco buys Splunk ($28B). Thoma Bravo
  takes Darktrace private ($5.3B) — after a short-seller report dented its
  "self-learning AI" story. Exabeam merges with LogRhythm: the end of
  standalone UEBA as a product category.
- **2025: copilot becomes agent.** Agentic triage and investigation with
  bounded autonomy — Charlotte Agentic Response, Purple AI Athena, Security
  Copilot's six-agent fleet. The vocabulary flips; the products start acting
  without being asked.
- **2026: everyone ships agents; the evidence layer gets reframed.**
  Detection telemetry is repositioned as machine-readable context for agents
  (ExtraHop's "context layer" NDR, MCP-native agent platforms). The newest
  turn: **baselining the agents themselves** — Securonix watches AI-agent
  behavior, Exabeam detects rogue agents, ClawArmor puts guardrails in the
  kernel *below* the agent so a compromised agent can't override them.
  Google's $32B Wiz acquisition closes: the largest security deal ever.
- **Underneath it all: the backbone never moved.** Suricata, Zeek, MITRE
  ATT&CK (which now catalogs AI-agent attacks), Sigma, YARA-X. Every AI SOC
  still reasons in ATT&CK IDs and emits Sigma/YARA-shaped output. Primitives
  beat platforms.

## What stuck vs. what fizzled

**Stuck:** agentic triage/investigation; behavioral analytics as an embedded
feature; eBPF runtime detection (Falco graduated CNCF, the de-facto standard);
canary tokens (free, 30-second tripwires, near-zero false positives);
ATT&CK/Sigma/YARA as the interop layer.

**Fizzled:** standalone UEBA; standalone deception vendors (Attivo was bought
"for its identity security, not its deception tech"); "XDR" as a distinct
product; standalone NDR as a growth story; chat-only copilots; pre-LLM
"autonomous SOC" claims; "AI magic" marketing.

## Read against this project, honestly — sorted by footprint

### Nearly free: take it, the kernel does the work

- **ACLs** — the example. Already in place; keep extending per the gaps doc.
- **Linux capabilities** — drop everything a job doesn't need. A few lines,
  zero runtime cost. Partly there via bwrap; make it explicit per profile.
- **seccomp-bpf** — syscall filter per job profile. Cheap, set once.
- **Windows integrity levels + job objects** — free, per-job. Unused today;
  candidate.
- **Kernel audit (auditd / SACLs / ETW)** — the OS logs, we just read. An
  audit-log sense costs almost nothing.
- **eBPF observability** — ~1–3% overhead for syscall visibility a rootkit
  can't dodge (the Falco/Tetragon lineage, now the respected standard).
  Optional sense on Linux; integrate, don't build.
- **Canary tokens and files** — zero cost until touched; the cheapest
  high-signal item on this entire list. The runner plants three
  tripwire files in its state directory and reports a change or a
  deletion until the file is restored.
- **Firewall posture reads** — one line in the Oracle context (on or
  off). Not a packet capture. The ruleset-diff daemon in the senses
  doc is still not built.
- **YARA on job artifacts** — only files that job just wrote, only if
  `yr` or `yara` is installed, size-capped. ClamAV the same way, and
  only through `clamdscan`.
- **ATT&CK IDs on sense output** — on the watch lines now (audit
  events, persistence changes, canary trips, a firewall that is off).
  Zero runtime cost. A label, not a verdict.

### Moderate: optional, off by default

- **Zeek/Suricata as a collector** — real CPU on a busy network. Optional
  netmon sense, off unless enabled.
- **Full AV scan hooks** — on demand, never resident.
- **Guard-model triage (Llama Guard shape)** — only when a model is already
  loaded. Costs RAM/VRAM otherwise.
- **Statistical anomaly baselining** — Microsoft retired its own low-quality
  ML detections in 2026. Don't ship this until it's good. Honestly not built.

### Heavy / out of scope

Line-rate NDR, 24/7 ML pipelines, cloud-scale telemetry economics. We're a
personal runner, not a platform.

## Honest gaps the industry just named

1. **Nobody watches the Oracle.** The industry's newest category is
   agent-behavior baselining — watching the watchers. Our Oracle calls tools
   with no record beyond chat history. Candidate: an Oracle action log as a
   sense. The calls already flow through one place; recording them is small.
2. **No guardrail below the Oracle.** ClawArmor's whole pitch is policy a
   compromised agent cannot override. Our cage protects the host *from jobs*;
   nothing constrains a misbehaving Oracle. Candidate: an Oracle tool-call
   policy. Option for later.
3. **Bespoke tool protocol.** The industry is standardizing agent tools on
   MCP; ours are hand-rolled JSON. Out of scope for now — noted, not chased.
4. **The Oracle inventing log events** is exactly the "AI magic" failure mode
   the Darktrace episode warns about. The fix is the same in both cases:
   never let the model or the docs overclaim. The anti-fabrication rule in
   the Oracle's instructions is the right shape; keep it sharp.

## What we will not become

Not an XDR, not a UEBA product, not a deception vendor. Standalone categories
fizzle; features win. The architecture — thin senses, Oracle fusion, DRI
playbook — is the right shape precisely because it's a pipeline, not a suite.
