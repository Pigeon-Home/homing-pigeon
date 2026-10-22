# Threat model — an honest review

*Adapted from an external "review" by Claude.*

Homing Pigeon lets a cloud SI run code on your machine easily, which
is both its whole appeal and its whole problem. Anyone holding the
shared secret effectively owns the box the agent runner is installed
on, and since a cloud system can't be trusted never to send a
destructive job, the project assumes every job could be one.

For anything serious, existing tools already do this better: SSH with
scoped keys, CI runners, containers, or a proper agent sandbox. Still,
configuring those repeatedly for every provider and chat interface is
cumbersome, and this cuts through that noise.

Jobs are checked before they run by deterministic code — the
opinion's tier-1 checks, which run by default. The opinion is
advisory, not a gate: it never blocks, holds, or approves a job
by itself (the judge does gate, when the owner sets it to
enforce). The Oracle reviews the results after the fact; by
default that review is the same deterministic tier-1 machinery —
a local model joins the opinion only when the owner opts in
(`oracle_opinion_model`; the installer's default model is
qwen3:1.7b). The operating system can carry the rest of the load,
with SELinux or AppArmor, locked-down users, containers, filesystem
ACLs, and role-based keys that could feed back into the Oracle and
limit what a bad or even malicious job can touch.

It could even work as a marketable service.

## What this means in practice

- The signature is the authentication gate for jobs (a transport's
  own credentials, where it has them, gate the pipe in front of
  it). Guard the shared secret like a root password, because that
  is what it is.
- Run the agent as a locked-down user, on a throwaway account, on a
  box you can wipe. The README's security notes are not boilerplate.
- The Oracle reviews and attests. It does not contain a job unless
  you turn on Linux bubblewrap (`security.modes.confinement` set to
  `enforce`, and `bwrap` installed). That switch is off by default.
  A VM, a locked-down user, and the OS policy still do the real
  containment. AppArmor and SELinux profiles live under `hardening/`
  and are opt-in. They are not installed for you.
- Every new sense, transport, and job kind added to this project
  widens the blast radius. `docs/archive/roadmap-spec.md` is exciting and
  dangerous in exactly equal measure; build the gates (§3) before
  the hands (§1.3).

## What the defaults don't cover

`docs/security-gaps.md` is the companion to this file: the ordered
story (split identities, then ACL the secrets, then cage the
workspace), the per-platform ACL gaps, and the inventory of basic
technologies still missing or default-off — runner code integrity,
egress control, audit log integrity, supply chain, revocation, the
Windows SYSTEM default. Read it before deciding the defaults are fine
for your box.

## Appendix: an outside take (Gemini, flattery mode)

*Adapted from an external "review" by Gemini, produced 2026-10-16 after being explicitly asked to be flattering. Read with that discount applied.*

Gemini's pitch: Homing Pigeon should pivot from "secure runner" into an "Autonomous Agent Security and Governance Fabric" aimed at a $100M+ acquisition. Four pivots proposed:

1. **AI Agent Firewall & Runtime Gateway** — route all LLM agent execution through the runner as a sidecar sandbox (prompt injection, exfiltration, runaway code).
2. **Continuous Automated FedRAMP/SOC2 Auditor** — turn the audit/hardening modules into an always-on compliance enforcement daemon with auto-remediation.
3. **Zero-Trust Confidential Micro-Orchestrator** — ephemeral, cryptographically verified workload mesh for sensitive micro-jobs.
4. **"Datadog for Autonomous Ops"** — centralized SaaS telemetry/forensics stream for background task execution.

Playbook: wedge (today's runner) → Year 1 productize as Agentic Security Gateway → Year 2 add continuous compliance upsell → exit to a security incumbent.
