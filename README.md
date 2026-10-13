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

1. Create a **dedicated** Gmail account for the runner, e.g.
   `myname-runner@gmail.com`. Never use a personal inbox.
2. Enable 2-Step Verification, then create an **app password**
   (Google Account → Security → 2-Step Verification → App passwords).
3. Copy `runner/` to the target machine and make sure Python 3.9+ is
   installed.
4. Copy `config.example.json` to `config.json` and fill in `mailbox_user`
   and `mailbox_password` — your Gmail address + app password, **in
   plaintext, on purpose** (your explicit choice for this throwaway
   account). Leave `allowed_sender` empty — the runner then only accepts
   job mail from the account it is logged into (hard rule).
5. When you want an AI to send jobs, paste that same app-password string
   to it in chat. It doubles as the HMAC shared secret.
6. Test one cycle: `python3 runner.py --config config.json --once`.
7. `python3 install.py` registers the boot-start service for your
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
