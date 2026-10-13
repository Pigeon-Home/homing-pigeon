# Homing Pigeon

A self-hosted, cross-platform agent for Muse. Muse emails it
cryptographically signed jobs; it runs them and emails back signed
results. Think "GitHub self-hosted runner, but the control plane is
email." Runs on Linux, macOS, FreeBSD, and Windows — Python 3.9+,
standard library only, no dependencies.

> ⚠️ **USE AT YOUR OWN RISK.** This tool hands **full administrative control**
> of the machine to whoever holds the shared secret. It reads email
> and executes what it finds — blindly, as a privileged user. Anyone who can
> produce a correctly-signed email owns the box: install software, read
> files, add users, pivot to your network. Only run this with a dedicated
> throwaway account on a machine you can afford to lose, and read
> PROTOCOL.md before you deploy it.

## What this is for

Homing Pigeon is a personal remote-development agent. The idea is
simple: the most powerful computer you own sits at home, and there's no
reason your AI assistant should stop being useful the moment you walk
away from your desk. Send a job from your phone, let the big machine run
the tests, crunch the data, or grind through the refactor, and read the
results when they land in your inbox.

It belongs to the same family as GitHub self-hosted runners, VS Code
Remote tunnels, and Tailscale — legitimate tools for administering your
own hardware remotely. And like all of those, its power is the point,
not an accident: whoever holds the shared secret has full control of
the machine. That's exactly why this project states its threat model
plainly instead of burying it. Keep the secret like a password, use a
throwaway account, and only ever install the agent on machines you own
and operate.

```
  Muse (cloud)                      Your machine
  ────────────                      ──────────────────
  send_job.py ──sign──▶ job email ──▶  runner.py
       │                  │              │  poll IMAP
       │                  │              │  verify HMAC
       │                  │              ▼
       │                  │           run script
       │                  │              │
       │               result email ◀──┘ sign
       ▼                  │
  verify result ◀─────────┘
```

Large inputs don't go through email: Muse uploads them to file hosting
and the job email carries download URLs (with optional SHA-384).

## Layout

- `PROTOCOL.md` — the full wire protocol (message formats, signatures,
  verification rules, security model).
- `runner/runner.py` — the agent. Polls IMAP, verifies, executes,
  replies via SMTP. No dependencies beyond Python 3.9 stdlib.
- `runner/install.py` — installs it as a boot-start service: systemd
  (Linux), launchd (macOS), cron @reboot (FreeBSD), Scheduled Task
  (Windows).
- `runner/config.example.json` — copy to `config.json` and fill in.
- `cloud/send_job.py` — cloud-side helper: builds signed job emails,
  verifies result emails. (Muse uses this logic when dispatching jobs.)
- `tests/test_runner.py` — end-to-end tests with fake IMAP/SMTP servers.
- `examples/hello-world.json` — unsigned example job payload.

## Setup

**Easiest: download a release.** No Python needed — each release ships
standalone binaries built by GitHub Actions:

| Platform | Download |
|----------|----------|
| Windows (x64) | `homing-pigeon-windows-amd64.zip` → `homing-pigeon.exe` + `install.exe` |
| Linux (x64, Debian/RHEL/Ubuntu/…) | `homing-pigeon-linux-amd64.tar.gz` → `homing-pigeon` + `install` |
| macOS (ARM64) | `homing-pigeon-macos-arm64.tar.gz` → `homing-pigeon` + `install` |

The Linux binary is built against glibc 2.28, so it runs on Debian 11+,
RHEL 8/9+, Ubuntu 20.04+, and most other modern distros.

1. Extract the archive on the target machine.
2. Run `install` (or `install.exe` on Windows). It copies the runner
   binary, writes a default `config.json`, and registers the boot-start
   service (systemd / launchd / cron @reboot / Scheduled Task).
3. Edit `config.json`: set `mailbox_user` and `mailbox_password` — your
   dedicated Gmail address + app password, **in plaintext, on purpose**
   (your explicit choice for this throwaway account). Leave
   `allowed_sender` empty — the runner then only accepts job mail from
   the account it is logged into (hard rule).
4. When you want an AI to send jobs, paste that same app-password string
   to it in chat. It doubles as the HMAC shared secret.

**From source** (needs Python 3.9+):

1. Create a **dedicated** Gmail account for the runner, e.g.
   `myname-runner@gmail.com`. Never use a personal inbox.
2. Enable 2-Step Verification, then create an **app password**
   (Google Account → Security → 2-Step Verification → App passwords).
3. Copy `runner/` to the target machine.
4. Copy `config.example.json` to `config.json` and fill in `mailbox_user`
   and `mailbox_password` as above.
5. Test one cycle: `python3 runner.py --config config.json --once`.
6. `python3 install.py` registers the boot-start service for your
   platform (see below).

### Per-platform install

| Platform | Mechanism | Notes |
|----------|-----------|-------|
| Linux | systemd user unit (`--system` for system-wide) | `systemctl --user enable --now homing-pigeon` |
| macOS | launchd agent | `~/Library/LaunchAgents/com.homing-pigeon.runner.plist` |
| FreeBSD | cron `@reboot` | simple; wrap in rc.d if you prefer |
| Windows | Scheduled Task | runs at startup as SYSTEM |

`install.py --dir DIR` chooses the install location (default
`~/.homing-pigeon`); `install.py --uninstall` removes the service.

## Run it in a VM

For testing — and honestly for everyday use — run the agent inside a
Linux VM on your home machine rather than directly on the host:

- **Snapshots beat regret.** About to hand an AI the keys to a machine?
  Snapshot first. If a job goes sideways, roll back in seconds.
- **Containment.** The agent only sees what the VM sees. Your host, your
  files, and your other projects stay out of reach of anything a job does.
- **Disposability.** Experiment freely: spin up a fresh VM for a new
  idea, tear it down when you're done. Nothing lingers on the host.

Any hypervisor works — KVM/QEMU, VirtualBox, Hyper-V, VMware. Give the
VM internet access (NAT is fine) so it can reach Gmail's IMAP/SMTP,
install the Linux release binary inside the guest, and point your jobs
at it. The host never needs to know.

## How scripts run

Jobs carry a `script` (or `script_url`) plus an optional `interpreter`
list, e.g. `["bash"]` or `["pwsh", "-File"]`. The runner writes the
script to the job's work dir and runs `<interpreter...> script <args...>`.
Defaults: PowerShell on Windows, `sh` elsewhere; override per-install
with `default_interpreter` in config.json, per-job with `interpreter`
in the job (`send_job.py new --interpreter '["bash"]'`).

## Sending a job (any AI)

The runner is AI-agnostic: anything that can send email *as* the runner's
Gmail account and sign the body can drive it — Muse, ChatGPT, Grok, a cron
script, whatever. The AI needs the shared secret string from step 5 (which
is the app password itself, your choice). Then:

```bash
python3 cloud/send_job.py new --kind ping --secret <the-string>
# prints: subject line, blank line, signed body -> send as email to the runner mailbox

python3 cloud/send_job.py new --kind exec --script-file job.sh \
  --interpreter '["bash"]' --file data.csv=https://... --timeout 300 \
  --secret <the-string>
```

Or just paste the string to your AI in chat — it composes, signs, and sends
the job email itself, and reads the result email when it arrives. Large files
are uploaded to cloud storage first; the job email carries the URLs.

Verify a result body:

```bash
python3 cloud/send_job.py verify --secret <the-string> result.txt
```

## Testing

```bash
python3 -m pytest tests/   # or: python3 tests/test_runner.py
```

The suite drives the real runner code against fake IMAP/SMTP servers:
ping roundtrip, script execution, timeout kill, poison-job rejection,
sender/signature/tamper rejection.

End-to-end without Muse:

1. `python3 cloud/send_job.py new --kind ping --secret <the-string>` → copy the
   subject + body.
2. From your own Gmail (matching `allowed_sender`), send it to the
   runner mailbox.
3. On the target machine: `python3 runner.py --config config.json --once`.
4. A result email with `stdout: "pong"` should arrive in the mailbox.

## Security notes

- The runner is a **full-trust execution environment**: a valid signed
  job email means arbitrary code as a privileged user. The app password sits in
  **plaintext** in config.json and doubles as the HMAC secret (your explicit
  choice: throwaway account, fresh box). Anyone holding it gets Gmail access
  and job-signing ability. Don't use this setup with an account you care about.
- Every job is HMAC-SHA-384 signed; sender address, timestamp window, and
  replay protection (seen-set) are all enforced before anything runs.
- Delivery is at-least-once: if a result email fails to send, the job
  stays unseen and will be re-executed next cycle. Make jobs idempotent
  or check the seen behavior accordingly.
- Hardening ideas for v2: encrypted credentials at rest,
  per-job encryption, result file upload for large outputs.

## Status

v1. Runner rewritten in cross-platform Python; crypto tested
(sign/verify roundtrip, tamper rejection, CRLF tolerance); end-to-end
suite passes against fake mail servers on Linux. Not yet run against a
live Gmail mailbox on all four platforms — that's the next step.
