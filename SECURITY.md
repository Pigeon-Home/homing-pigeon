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
