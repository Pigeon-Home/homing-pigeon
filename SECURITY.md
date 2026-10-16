# Security Policy

Homing Pigeon is, by design, a remote code execution tool: anyone
holding the shared secret gets full control of the machine the runner
runs on. That makes its security posture load-bearing, not decorative.
This document explains how to report problems and what to expect.

## Reporting a vulnerability

**Do not open a public issue for security problems.** Public issues
get scraped, and a disclosed-but-unfixed hole in a tool like this
puts every deployment at risk.

Instead, use GitHub's **private vulnerability reporting**:

1. Go to the repo's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue: what you found, how to reproduce it, and what
   you think the impact is.

If private reporting isn't available to you, open a minimal public
issue that says you've found a security problem and ask for a contact —
no details.

### What happens next

- You'll get an acknowledgment as soon as the report is seen.
- The issue will be assessed for impact and reproducibility.
- A fix will be developed privately, then released with a clear
  description of what was wrong and which versions are affected.
- You'll be credited in the release notes unless you'd rather stay
  anonymous.

## Scope

In scope: the runner (`runner/runner.py`), the installer
(`runner/install.py`), the cloud helper (`cloud/send_job.py`), the
protocol itself (PROTOCOL.md), and the build/release pipeline
(`.github/workflows/`).

Out of scope: the security of Gmail itself, the secrecy of a
shared secret the user chose to share, and deployments that ignore
the documented threat model (e.g., running the agent on a machine
with irreplaceable data and no VM snapshot).

## A note on the threat model

This project is explicit that the runner is a **full-trust execution
environment**. Reports along the lines of "anyone with the secret can
run arbitrary code" describe the intended design, not a vulnerability.
A vulnerability is something that breaks the documented guarantees:
signature forgery, a job executing without a valid
signature, sandbox/workdir escape, or secret leakage through logs,
emails, or error messages. Sender spoofing is not in scope: the sender
address is not validated, so there is nothing to spoof — the signature
is the only thing the runner trusts.

**What the signature proves, and what it does not.** The HMAC signature
answers two questions: was this job sent by someone holding the shared
secret, and has it been tampered with in transit? It does not answer a
third question: is this job safe to execute? A compromised SI, a
prompt-injected SI, or a careless human with the secret can sign a
perfectly valid, perfectly destructive job, and the runner will run it.
Authentication is not authorization to be safe. That is why the
deployment model matters more than the cryptography: throwaway account,
disposable machine, secret kept like a password. The crypto keeps
strangers out. Only your own judgment keeps bad jobs out.

## Dual-use: yes, this looks like email-C2

Saying it plainly: a program that polls an inbox and executes signed
messages is the same *shape* as email-based command-and-control malware.
The difference is not the mechanism — it is consent, control, and
auditability:

- **Consent:** you install it on your own machine, on purpose, to run
  your own jobs. It does nothing you did not ask it to do.
- **Control:** the shared secret is yours, the mailbox is yours, and
  revoking the mailbox credential bricks the agent remotely in seconds —
  without mailbox access the runner can't receive jobs, so a leaked
  signing secret has no delivery channel. To rotate a compromised
  secret, generate a new one and update `shared_secret` in config.json
  on the runner (and hand the new string to your SI).
- **Auditability:** the runner is inspectable by design. `--dry-run`
  verifies signatures and prints exactly what a job *would* do without
  executing anything; `--verbose` logs every accept/reject decision;
  `--pdb` drops into the Python debugger on errors. Malware hides.
  This tool is built to be watched.

It belongs to the same family as GitHub self-hosted runners, VS Code
Remote tunnels, and Tailscale: legitimate remote-administration tools
whose power is the point. If your antivirus flags the prebuilt
binaries, that is a known PyInstaller false-positive pattern — verify
the `SHA384SUMS` file attached to the release, or build from source
(`pip install` the wheel, or run `runner/runner.py` directly).

---

## Optional security controls

Homing Pigeon ships with optional, off-by-default security controls.
With no `security` block in `config.json`, the runner behaves exactly
as it always has. Every control has three modes:

- `off` — the control does nothing. This is the default.
- `audit` — the job proceeds exactly as with `off`, but a line is
  written to `security-audit.jsonl` describing what `enforce` mode
  would have decided.
- `enforce` — violations are rejected through the existing reject
  path. Nothing else changes.

```json
"security": {
  "modes": {
    "policy_env": "off",
    "policy_files": "off",
    "policy_args": "off",
    "audience": "off",
    "confinement": "off",
    "job_user": "off"
  },
  "audit_max_lines": 20000
}
```

**Changing a mode requires a restart.** The config file is read once
at startup; it is not re-read each poll cycle.

**A malformed security block stops startup** with an error naming the
key and the bad value. It never silently falls back to `off`.

The audit log lives at `security-audit.jsonl` in the runner base
directory, created `0600` on POSIX, bounded by `audit_max_lines`
(default 20000) with rollover to one `.1` file. A small counter file,
`security-audit-counts.json`, tracks decisions per feature. Audit
entries carry identifiers only — never secret values, script text,
or file contents.

### Features

| Feature | Milestone | What it does |
|---|---|---|
| `policy_env` | M2 | Constrains env vars for keys with a policy entry |
| `policy_files` | M2 | Constrains staged files for keys with a policy entry |
| `policy_args` | M2 | Constrains job args for keys with a policy entry |
| `audience` | M5 | Binds signed jobs to this runner's id |
| `confinement` | M6 | Runs jobs inside a Linux sandbox (bwrap) |
| `job_user` | M8 | Runs jobs as a different POSIX user |

### Confinement (M6)

With `security.modes.confinement: enforce` on Linux and `bwrap`
installed, each `exec` job runs inside a bubblewrap sandbox: `/usr`
read-only, no network, no access to home, and only the job workdir
writable (mounted at `/work`). The job's scrubbed env arrives via
`--setenv`. When `bwrap` is missing, or on non-Linux, the runner warns
loudly, audits a `fallback` decision, and runs the job normally —
availability wins over confinement, and the fallback is always
visible. `audit` mode runs normally and records `would_run_sandboxed`.

Optional tuning under `security.confinement` (all optional):

```json
"confinement": {
  "extra_flags": ["--unshare-pid"],
  "extra_ro_binds": [["/opt/data", "/data"]],
  "work_mount": "/work"
}
```

See the hardening report (`HARDENING_REPORT.md`) for per-milestone
status, and the threat model (`docs/threat-model.md`) for the
overall posture: the Oracle reviews while the operating system
contains.
