# Homing Pigeon

**Works with Muse, Grok, ChatGPT, Claude, Gemini, Copilot, etc.**

Your cloud SI is smart, but it can't touch your computer. Homing Pigeon
fixes that: tell your SI to send a signed job, it executes on your machine
(Linux/macOS/FreeBSD/Windows), and the results come back so your SI can
iterate — run the tests, read the failure, fix, repeat. From your phone,
from anywhere.

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

Homing Pigeon is a personal remote-development agent. The idea is
simple: the most powerful computer you have access to shouldn't stop
being useful the moment you walk away from your desk — and neither
should your SI assistant. Send a job from
your phone, let the big machine run the tests, crunch the data, or
grind through the refactor, and read the results when they land in your
inbox.

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
ports — NAT-proof), authenticated sender, at-least-once delivery, and
zero infrastructure to operate. And because the protocol doesn't care
about the pipe: Cloudflare Queues, NATS, MQTT, Redis Streams and friends
all satisfy the same contract. Email is just Transport #1 —
see TRANSPORTS.md.

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

## Layout

- `PROTOCOL.md` — the full wire protocol (message formats, signatures,
  verification rules, security model).
- `TRANSPORTS.md` — email is just Transport #1. Alternatives that satisfy
  the transport contract: Cloudflare Queues (the pick), NATS, MQTT,
  Redis Streams, Postgres, Durable Objects.
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
| Windows (x64) | `homing-pigeon-windows-x86_64.zip` → `homing-pigeon.exe` + `install.exe` |
| Linux (x64, Debian/RHEL/Ubuntu/…) | `homing-pigeon-linux-x86_64.tar.gz` → `homing-pigeon` + `install` |
| macOS (ARM64) | `homing-pigeon-macos-arm64.tar.gz` → `homing-pigeon` + `install` |

The Linux binary is built on ubuntu-22.04 (glibc ~2.35). It runs on
Ubuntu 22.04+, recent Debian, and most current distros. Older systems
(Debian 11, Ubuntu 20.04, RHEL 8) are not supported.

1. Extract the archive on the target machine.
2. Run `install` (or `install.exe` on Windows). It copies the runner
   binary, writes a default `config.json`, and registers the boot-start
   service (systemd / launchd / cron @reboot / Scheduled Task).
3. Edit `config.json`: set `mailbox_user` and `mailbox_password` — your
   dedicated Gmail address + app password, **in plaintext, on purpose**
   (your explicit choice for this throwaway account). Leave
   `allowed_sender` empty — the runner then only accepts job mail from
   the account it is logged into (hard rule).
4. When you want an SI to send jobs, paste that same app-password string
   to it in chat. It doubles as the HMAC shared secret.

**From the Python packages** (needs Python 3.9+): each release also
ships an sdist (`.tar.gz`) and a universal wheel (`.whl`) — the easiest
path on machines where Python is preinstalled, like a Raspberry Pi:

1. Download the `.whl` from the release.
2. `pip install homing_pigeon-1.1.0-py3-none-any.whl` — this installs
   three commands: `homing-pigeon`, `homing-pigeon-install`, and
   `homing-pigeon-send-job` (the cloud-side helper).
3. `homing-pigeon-install` copies the runner, writes a default
   `config.json`, and registers the boot-start service.
4. Edit `config.json` and share the app-password string with your SI,
   same as above.

See [The $35 pigeon coop](#the-35-pigeon-coop-raspberry-pi) for the full
Raspberry Pi walkthrough.

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

## The $35 pigeon coop (Raspberry Pi)

Every homing pigeon needs a coop — a cheap, always-on box to come home
to. A Raspberry Pi is the perfect one:

- **Always on, barely sipping power.** The runner just polls Gmail on a
  loop; a Pi idles at a few watts while your laptop sleeps.
- **A machine you can afford to lose.** This project's whole security
  posture is "dedicated throwaway account on a box you don't care
  about." A $35 Pi *is* that box.
- **Python's already there.** Skip the frozen binaries entirely:

```sh
pip install homing_pigeon-1.1.0-py3-none-any.whl
homing-pigeon-install          # registers the boot-start service
# edit ~/.homing-pigeon/config.json, then test one cycle:
homing-pigeon --config ~/.homing-pigeon/config.json --once
```

Grab the `.whl` (or the `.tar.gz` sdist) from any
[release](https://github.com/Pigeon-Home/homing-pigeon/releases).
Your SI sends jobs from the cloud; the Pi in the corner executes them.
That's the whole trick.

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

```bash
python3 -m pytest tests/   # or: python3 tests/test_runner.py
```

The suite drives the real runner code against fake IMAP/SMTP servers:
ping roundtrip, script execution, timeout kill, poison-job rejection,
sender/signature/tamper rejection.

End-to-end without your SI:

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
  per-job encryption, result file upload for large outputs — plus the
  Oracle (spec'd in PROTOCOL.md): result policies, signed attestations,
  and a query budget, so a cloud SI learns *answers* about your output
  without ever seeing it. `oracle_enabled: false` disables it anytime.

## Status

v1.1.0. Install hardened across all platforms; runner rejects malformed jobs (naive issued_at, string interpreter, path-escaping job_id) and caps downloads; 68 unit tests. Runner rewritten in cross-platform Python; crypto tested
(sign/verify roundtrip, tamper rejection, CRLF tolerance); end-to-end
suite passes against fake mail servers. Releases ship standalone
binaries (Windows/macOS/Linux) plus a Python wheel and sdist. The v2
protocol — the Oracle, privacy-preserving results via signed
attestations — is spec'd in PROTOCOL.md and awaiting implementation.
Not yet proven against a live Gmail mailbox on all four platforms —
that's the next proving ground.
