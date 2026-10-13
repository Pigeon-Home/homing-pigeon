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
signature forgery, sender spoofing, a job executing without a valid
signature, sandbox/workdir escape, or secret leakage through logs,
emails, or error messages.
