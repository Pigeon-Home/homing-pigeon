# Homing Pigeon

**Works with Muse, Grok, ChatGPT, Claude, Gemini, Copilot, etc.**

Your cloud SI is smart, but it can't touch your computer. Homing Pigeon
fixes that: tell your SI to complete a task and it will do it on your
machine (Linux/macOS/FreeBSD/Windows). The results return so that your
SI can iterate — run the tests, read the failure, fix, repeat. From your
phone, so from anywhere.

Think "GitHub self-hosted runner, but the control plane is email." Python
3.9+, standard library only, no dependencies. (Email is just the first
transport — the protocol doesn't care about the pipe. See TRANSPORTS.md.)

> ⚠️ **USE AT YOUR OWN RISK.** This tool hands **full administrative control**
> of the machine to whoever holds the shared secret. It reads email
> and executes what it finds — blindly, as a privileged user. Anyone who can
> produce a correctly-signed email owns the box: install software, read
> files, add users, pivot to your network. Only run this with a dedicated
> throwaway account on a machine you can afford to lose, and read
> PROTOCOL.md before you deploy it.

## What this is for

Homing Pigeon is a personal remote-development agent. The point is not
that the SI becomes smarter. It is that the SI gets a way to delegate
work to a computer it could not otherwise reach. The most powerful
computer you have access to should not stop being useful the moment you
walk away from your desk, and neither should your SI assistant.

Concrete uses:

- **Remote test runs.** Ask your SI to run the suite, read the
  failures, patch the code, rerun, and report back, all while you are
  away from the machine.
- **Your hardware as a worker.** Long builds, data crunching, batch
  jobs, on the workstation you own, without a remote-desktop session
  open.
- **Scheduled-style automation.** Maintenance scripts, reports, and
  repetitive technical tasks, dispatched from your phone.
- **Cloud SI, local resources.** Your files, your dev environment,
  your GPU, reachable by an assistant that lives in the cloud.
- **Physical peripherals.** Plug a sensor or servo board into a
  Raspberry Pi, point your SI at it, and let it write the control
  code and debug the hardware into motion. You do the soldering,
  it does the head-scratching. Let SI build a robot.

Send a job from your phone, let the big machine run the tests, crunch
the data, or grind through the refactor, and read the results when they
land in your inbox.

The SI systems are brilliant, but they are kept fenced off from our
real machines. So instead we will point one at a disposable box, give
it a signed channel, and let it do tasks from start to finish. The
upside is an assistant that operates, not just advises. If the
capability is real, there is very little downside to exercising it.

A new model claims to be good at something — robotics, automation,
data work? Point it at a box and find out. The clock check in the
RUNBOOK is the hello world; the ceiling is wherever your hardware
goes. See Job 7.

It belongs to the same family as GitHub self-hosted runners, VS Code
Remote tunnels, and Tailscale — legitimate tools for administering your
own hardware remotely. And like all of those, its power is the point,
not an accident: whoever holds the shared secret has full control of
the machine. That's exactly why this project states its threat model
plainly instead of burying it. Keep the secret like a password, use a
throwaway account, and only ever install the agent on machines you own
and operate.

```
  SI (cloud)                        Your machine
  ────────────                      ──────────────────
  send_job.py ──sign──▶ job email ──▶  runner.py
       │                  │              │  poll IMAP
       │                  │              │  verify HMAC
       │                  │              ▼
       │                  │           run script
       │                  │              │
       │               result email ◀──┘ sign
       ▼                  │
  verify result ◀──────────┘
```

Large inputs don't go through email: your SI uploads them to file hosting
and the job email carries download URLs (with optional SHA-384).

**Why email?** Because it's the only transport with all five properties
on day one: reachable from anywhere, outbound-only polling (no inbound
ports — NAT-proof), at-least-once delivery, and
zero infrastructure to operate. And because the protocol doesn't care
about the pipe: Cloudflare Queues, NATS, MQTT, Redis Streams and friends
all satisfy the same contract. Email is just Transport #1 —
see TRANSPORTS.md.

**Runbooks, not prompts.** The SI doesn't chat about the task — it ships
a runbook: deterministic steps, each with a check that proves the step
worked. The runner executes it and reports back what actually happened,
and that feedback goes into the next runbook. Each cycle is a little
smarter than the last, because the failures are data. If you've ever
debugged something by running it, reading the output, and trying again
with what you learned — that's the whole product. The SI is just the
part that writes the next attempt.

## The Oracle: answers, not output

v1 sends full job output back to the SI. The v2 proposal (spec'd in
PROTOCOL.md, not yet implemented) flips this: your machine becomes
**the Oracle** — a black box the SI can question but never inspect.

The SI asks "did the tests pass?" or "does the output contain secrets?"
and gets back HMAC-signed *attestations*: proofs about the output that
reveal nothing else. It's the zero-knowledge shape applied at the trust
boundary — prove things about your data without showing your data. The
raw output never leaves your disk.

```
  Cloud SI                                Your machine
  ────────                                ────────────────────
  "Did the tests pass?" ──signed──────▶ ┌─────────────┐
                                        │  The Oracle │
  "Any secrets in there?" ────────────▶ │             │
                                        │ output stays│
   ┌─────────────────────┐             │ on your disk│
   │ signed attestation   │ ◀──signed── │             │
   │ { exit_zero: true,   │             │ answers only│
   │   no_secrets: true } │             │ what policy │
   └─────────────────────┘             │ allows      │
                                        └────────────┘
   The SI learns answers. Never the raw output.
```

Queries are declared upfront (no adaptive probing), each job gets a
privacy budget bounding total leakage, and the disclosure ceiling is
set by *you* in config — never by the SI. For debugging,
`oracle_enabled: false` drops back to the plain v1 pipe.

The Oracle also grows two optional capabilities (spec'd, not yet built):

- **Local inference.** Point it at a model running on your own box and
  the SI can `ask` questions in plain English — *"why did the tests
  fail?"* — answered locally, with only the answer crossing the
  boundary. The endpoint must be loopback (fail closed), and every
  answer is truncated, redacted, and secret-scanned before it's sent.
  The SI gets useful answers, and your raw data never leaves the machine.
- **Execution confinement.** Tell the Oracle the one folder jobs may
  touch (`workspace_root`) and it *attests* the job stayed inside —
  `confined_to_workspace`, signed like everything else. Today's
  enforcement is attested; OS-level sandboxing is the stronger future.

Full spec in PROTOCOL.md (sections 9–12).

## Layout

- `PROTOCOL.md` — the full wire protocol (message formats, signatures,
  verification rules, security model).
- `TRANSPORTS.md` — email is just Transport #1. Alternatives that satisfy
  the transport contract: Cloudflare Queues (the pick), NATS, MQTT,
  Redis Streams, Postgres, Durable Objects.
- `SAFEGUARDS.md` — how to run this without getting burned: the
  non-negotiables, containment, the Oracle as a safeguard, and what
  to do when something goes wrong.
- `runner/runner.py` — the agent. Polls IMAP, verifies, executes,
  replies via SMTP. No dependencies beyond Python 3.9 stdlib.
- `runner/install.py` — installs it as a boot-start service: systemd
  (Linux), launchd (macOS), cron @reboot (FreeBSD), Scheduled Task
  (Windows).
- `runner/config.example.json` — copy to `config.json` and fill in.
- `cloud/send_job.py` — cloud-side helper: builds signed job emails,
  verifies result emails. (Your SI uses this logic when dispatching jobs.)
- `tests/test_runner.py` — end-to-end tests with fake IMAP/SMTP servers.
- `RUNBOOK.md` — step-by-step instructions (written for a 5-year-old):
  cloning, pushing, cutting a release, installing, sending a job.
- `examples/hello-world.json` — unsigned example job payload.

## Setup

**Easiest: download a release.** No Python needed — each release ships
standalone binaries built by GitHub Actions:

| Platform | Download |
|----------|----------|
| Windows (x64) | `homing-pigeon-windows-amd64.zip` → `homing-pigeon.exe` + `install.exe` |
| Linux (x64, Debian/RHEL/Ubuntu/…) | `homing-pigeon-linux-amd64.tar.gz` → `homing-pigeon` + `install` |
| macOS (ARM64) | `homing-pigeon-macos-arm64.tar.gz` → `homing-pigeon` + `install` |

The Linux binary is built on ubuntu-22.04 (glibc ~2.35). It runs on
Ubuntu 22.04+, recent Debian, and most current distros. Older systems
(Debian 11, Ubuntu 20.04, RHEL 8) are not supported.

1. Extract the archive on the target machine.
2. Run `install` (or `install.exe` on Windows). It copies the runner
   binary, writes a default `config.json`, and registers the boot-start
   service (systemd / launchd / cron @reboot / Scheduled Task).
3. Edit `config.json`. Two ways to sign in:
   - **Password** (default): `mailbox_user` + `mailbox_password` (Gmail app
     password, plaintext, on purpose). The HMAC secret is that password.
   - **Browser, like Thunderbird**: no Google password anywhere. Create a
     Desktop OAuth client in [Google Cloud
     Console](https://console.cloud.google.com/) (APIs & Services →
     Credentials → Create OAuth client ID → Desktop app), then in
     `config.json` set `"auth": "oauth"`, put the client id in
     `oauth_client_id` (and `oauth_client_secret` if Google gave you one),
     and set `shared_secret` to a random string — that's the HMAC key your
     SI uses to sign jobs. Then run `homing-pigeon-auth` (or
     `python runner/oauth.py --config config.json` from source): a browser
     opens, you sign in and grant access, and the refresh token is stored.
     IMAP and SMTP then use XOAUTH2. Tested end to end on Windows 11.
   (your explicit choice for this throwaway account).
4. When you want an SI to send jobs, paste that same app-password string
   to it in chat. It doubles as the HMAC shared secret.

**From Docker** — the fastest path, no Python or git needed:

```sh
docker run -d --name pigeon --restart unless-stopped \
  -e PIGEON_MAILBOX_USER="your-runner@gmail.com" \
  -e PIGEON_MAILBOX_PASSWORD="your-app-password" \
  -v pigeon-data:/data \
  ghcr.io/pigeon-home/homing-pigeon:latest
```

See [DOCKER.md](DOCKER.md) for the full guide — dry-run mode, config
file mounting, updating, and security notes.

**From PyPI** (needs Python 3.9+) — the easiest path on machines where
Python is preinstalled, like a Raspberry Pi. A Pi is the ideal box
for this: always on, sips power, and a machine you can afford to lose
— which is this project's whole security posture:

```sh
pip install pigeon-home-runner
```

This installs three commands: `homing-pigeon`, `homing-pigeon-install`,
and `homing-pigeon-send-job` (the cloud-side helper). Then:

1. `homing-pigeon-install` copies the runner, writes a default
   `config.json`, and registers the boot-start service.
2. Edit `config.json` and share the app-password string with your SI,
   same as above.

**From the release files** (same Python requirement): each GitHub
release also ships an sdist (`.tar.gz`) and a universal wheel (`.whl`),
plus standalone binaries (below) and a `SHA384SUMS` file so you can
verify your download:

1. Download the `.whl` from the release.
2. `pip install pigeon_home-1.4.4-py3-none-any.whl` — same three
   commands as above.
3. `homing-pigeon-install` copies the runner, writes a default
   `config.json`, and registers the boot-start service.
4. Edit `config.json` and share the app-password string with your SI,
   same as above.

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
Linux VM on your own hardware rather than directly on the host:

- **Snapshots beat regret.** About to hand an SI the keys to a machine?
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

## Sending a job (any SI)

The runner is SI-agnostic: anything that can send email *as* the runner's
Gmail account and sign the body can drive it — your SI of choice, a cron
script, whatever. The SI needs the shared secret string from step 5 (which
is the app password itself, your choice). Then:

```bash
python3 cloud/send_job.py new --kind ping --secret <the-string>
# prints: subject line, blank line, signed body -> send as email to the runner mailbox

python3 cloud/send_job.py new --kind exec --script-file job.sh \
  --interpreter '["bash"]' --file data.csv=https://... --timeout 300 \
  --secret <the-string>
```

Or just paste the string to your SI in chat — it composes, signs, and sends
the job email itself, and reads the result email when it arrives. Large files
are uploaded to cloud storage first; the job email carries the URLs.

Verify a result body:

```bash
python3 cloud/send_job.py verify --secret <the-string> result.txt
```

## Testing

**Watch before you trust.** The runner is fully inspectable — these flags
exist so you can audit everything it would do before it does it:

```bash
python3 runner/runner.py --config config.json --once --dry-run --verbose
# verifies signatures, prints what each job WOULD do, executes nothing,
# sends nothing, changes nothing (mail stays unseen)
```

| Flag | What it does |
|------|--------------|
| `--dry-run` | Verify and describe; execute nothing, send nothing |
| `--workers N` | Concurrent job executions (default 1) |
| `--verbose` | Debug logging: every accept/reject decision |
| `--pdb` | Drop into pdb on unhandled exceptions |
| `--no-send` | Execute, but log results instead of emailing them |
| `--once` | Single poll cycle, then exit |
| `--poll-interval SEC`, `--timeout SEC`, `--max-output-bytes N` | Override config |
| `--no-oracle` | Disable the Oracle safety layer (v2) |

`install.py` accepts the same flags and bakes them into the installed
service, so the agent on boot runs exactly what you tested:
`python3 runner/install.py --verbose --poll-interval 30`.

```bash
python3 -m pytest tests/   # or: python3 tests/test_runner.py
```

The suite drives the real runner code against fake IMAP/SMTP servers:
ping roundtrip, script execution, timeout kill, poison-job rejection,
signature/tamper rejection, any-sender acceptance.

End-to-end without your SI:

1. `python3 cloud/send_job.py new --kind ping --secret <the-string>` → copy the
   subject + body.
2. From any email account, send it to the
   runner mailbox.
3. On the target machine: `python3 runner.py --config config.json --once`.
4. A result email with `stdout: "pong"` should arrive in the mailbox.

## Security notes

- The runner is a **full-trust execution environment**: a valid signed
  job email means arbitrary code as a privileged user. The app password sits in
  **plaintext** in config.json and doubles as the HMAC secret (your explicit
  choice: throwaway account, fresh box). Anyone holding it gets Gmail access
  and job-signing ability. Don't use this setup with an account you care about.
- Every job is HMAC-SHA-384 signed; the signature is the sole
  authentication gate. Timestamp window and
  replay protection (seen-set) are enforced before anything runs; the
  sender address is logged but never trusted.
- Delivery is at-least-once: if a result email fails to send, the job
  stays unseen and will be re-executed next cycle. Make jobs idempotent
  or check the seen behavior accordingly.
- Hardening ideas for v2: encrypted credentials at rest,
  per-job encryption, result file upload for large outputs — plus the
  Oracle (spec'd in PROTOCOL.md): result policies, signed attestations,
  and a query budget, so a cloud SI learns *answers* about your output
  without ever seeing it. `oracle_enabled: false` disables it anytime.

## Status

v1.4.4. Grok hardened the config hot-reload: bad files don't poison
retries, CLI flags can't be undone by later edits, and invalid values
(negative intervals, non-numbers) are rejected instead of crashing the
loop. v1.4.3. The runner now hot-reloads `config.json` — edit poll
interval,
workers, timeouts, or output limits and they take effect within one
poll cycle, no restart needed. Includes Grok's doc fix dropping the
last leftover "From hard rule" references. v1.4.1. Release binaries now
carry Sigstore build provenance attestations
— verifiable proof they were built by this repo's CI. v1.4.0. The sender
address is no longer validated — any sender may submit
jobs, and the HMAC signature is the sole authentication gate. The sender
is logged for audit but never trusted. v1.3.1. PowerShell jobs stage as
`script.ps1` (Windows `-File` requires the
extension — every exec job failed without it); dead OAuth refresh tokens
now raise a distinct error and log once to the Windows Event Log instead
of failing silently. v1.3.0: Thunderbird-style Google sign-in: the runner opens your browser,
you sign in like adding Gmail on your phone, and IMAP/SMTP use XOAUTH2
from then on — no app password. Tested end to end on Windows 11: browser
login, job sent, runner polled and executed it, result emailed back, all
over OAuth. Password auth stays the default and is untouched. Runner
rewritten in cross-platform Python; crypto tested (sign/verify roundtrip,
tamper rejection, CRLF tolerance); end-to-end suite passes against fake
mail servers (103 tests). Debug/audit flags (`--dry-run`, `--verbose`,
`--pdb`, `--no-send`), concurrent job execution (`--workers`), SHA-384
release hashes, and PyPI distribution (`pip install pigeon-home-runner`).
Releases ship standalone binaries (Windows/macOS/Linux) plus a Python
wheel and sdist. The v2 protocol — the Oracle, privacy-preserving
results via signed
attestations — is spec'd in PROTOCOL.md and awaiting implementation.
