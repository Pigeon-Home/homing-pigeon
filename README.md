# Homing Pigeon

**Works with Muse, Grok, ChatGPT, Claude, Gemini, Copilot, etc.**

> ⚠️ **USE AT YOUR OWN RISK.** This tool hands **full administrative control**
> of the machine to whoever holds the shared secret. It reads email
> and executes what it finds — blindly, as a privileged user. Anyone who can
> produce a correctly-signed email owns the box: install software, read
> files, add users, pivot to your network. Only run this with a dedicated
> throwaway account on a machine you can afford to lose, and read
> PROTOCOL.md before you deploy it.

Your cloud SI is smart, but it can't touch your computer. Homing Pigeon
fixes that: tell your SI to complete a task and it will do it on your
machine. The results return so that your SI can iterate — run the tests,
read the failure, fix, repeat. From your phone or anywhere.

Install the Homing Pigeon agent/runner on your system. It will prompt
for login credentials to an email address, the default. The agent bares
similarity to GitHub self-hosted runners.

Then try this prompt in your cloud SI, it should return in less than 30 seconds.

```
Send an email to YOUR_RUNNER_EMAIL@gmail.com
Use this protocol: https://github.com/Pigeon-Home/homing-pigeon/blob/main/PROTOCOL.md
Shared Secret: "YOUR_SECRET_STRING"
Get the system clock and display it here.
```
IETF Homing Pigeon Draft: https://github.com/Pigeon-Home/homing-pigeon/blob/main/docs/ietf/draft-homing-pigeon-00.md

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
data work? Point it at a box and find out.

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
  ------------                      ------------------
  send_job.py --sign--> job message -->  runner.py
       |                  |              |  poll IMAP
       |                  |              |  verify HMAC
       |                  |              v
       |                  |           run script
       |                  |              |
       |             result message <--+ sign
       v                  |
  verify result <----------+
```

Large inputs don't go through email: your SI uploads them to file hosting
and the job message carries download URLs (with optional SHA-384).

**Why email?** Because it's the only transport with all five properties
on day one: reachable from anywhere, outbound-only polling (no inbound
ports — NAT-proof), at-least-once delivery, and
zero infrastructure to operate. The protocol does not care about the
pipe, but email is the only transport wired in today. Cloudflare Queues
is the planned second one. The other pipes in TRANSPORTS.md are design
notes, not code.

**Runbooks, not prompts.** The SI doesn't chat about the task — it ships
a runbook: deterministic steps, each with a check that proves the step
worked. The runner executes it and reports back what actually happened,
and that feedback goes into the next runbook. Each cycle is a little
smarter than the last, because the failures are data. If you've ever
debugged something by running it, reading the output, and trying again
with what you learned — that's the whole product. The SI is just the
part that writes the next attempt.

## The Oracle: answers, not output

**the Oracle** is a black box the SI can question but never inspect.

The SI asks "did the tests pass?" or "does the output contain secrets?"
and gets back HMAC-signed *attestations*: proofs about the output that
reveal nothing else. It's the zero-knowledge shape applied at the trust
boundary — prove things about your data without showing your data. The
raw output never leaves your disk.

```
  Cloud SI                                Your machine
  --------                                --------------------
  "Did the tests pass?" --signed------> +-------------+
                                        |  The Oracle |
  "Any secrets in there?" ------------> |             |
                                        | output stays|
   +---------------------+             | on your disk|
   | signed attestation   | <--signed-- |             |
   | { exit_zero: true,   |             | answers only|
   |   no_secrets: true } |             | what policy |
   +---------------------+             | allows      |
                                        +------------+
   The SI learns answers. Never the raw output.
```

Queries are declared upfront (no adaptive probing), each job gets a
privacy budget bounding total leakage, and the disclosure ceiling is
set by *you* in config — never by the SI.

Your machine runs two roles in one box:

```
+-----------------------------+-----------------------------+
| RUNNER (faces the SI)        | ORACLE (faces you)           |
+-----------------------------+-----------------------------+
| polls the mailbox            | reviews every job            |
| verifies HMAC + key policy   | before it runs               |
| judge: the policy gate      | fuses sensor alerts          |
| executes jobs, confined     | watches resources            |
| answers queries with        | pages you when a             |
| attestations -- never       | threshold trips              |
| raw output                  | never remediates             |
+-----------------------------+-----------------------------+
```

The runner does what the SI asks. The Oracle watches what happens
and tells you about it.

### Operating modes

Five knobs set the posture. They are independent — these are three
coherent postures, not the only combinations.

```
  knob                  just run it  eyes open    lockdown
  ------------------    -----------  ---------    --------
  judge                 off          advisory     enforce
  sensors               off          on           on
  resources             on           on           on
  dri                   off          on           on
  max_result_view       full         attested     attested
```

**just run it** (the defaults). Runner: executes any signed job,
answers queries with full output. Oracle: reviews every job anyway
(notes ride in the result), logs resource pressure. Quiet — nothing
pages, nothing blocks.

**eyes open** (recommended). Runner: executes, attaches the policy
verdict to each result, answers queries with attestations only.
Oracle: reviews, fuses sensor alerts, pages you when a trigger
trips. Still takes no action itself.

**lockdown**. Runner: refuses anything the policy rejects; the SI
gets attestations. Oracle: same as eyes-open, and every refusal is
page-worthy. Nothing moves unless the policy allows it.

The Oracle ships two confinement capabilities:

- **Local inference.** Point it at a model running on your own box and
  the SI can `ask` questions in plain English — *"why did the tests
  fail?"* — answered locally, with only the answer crossing the
  boundary. The endpoint must be loopback (fail closed), and every
  answer is truncated, redacted, and secret-scanned before it's sent.
  The SI gets useful answers, and your raw data never leaves the machine.
- **Execution confinement.** Two different checks, both shipped.
  Set `workspace_root` and the Oracle snapshots file metadata outside
  that folder before and after the job, then attests
  `confined_to_workspace`. That one is a snapshot, not a sandbox. The
  walk stops at 50000 files. Separately, on Linux, set
  `security.modes.confinement` to `enforce` and the job runs inside
  bubblewrap (`bwrap`): `/usr` read-only, no network, and only the job
  workdir writable. It is off by default. If `bwrap` is missing, or the
  machine is not Linux, the job runs normally and the audit log records
  the fallback. See SECURITY.md.

Full spec in PROTOCOL.md (sections 9–12). Note the doc's "Protocol v1"
is the *message* version, not the product release — v3.x features ride
on v1 messages as optional fields.

## Layout

- `PROTOCOL.md` — the full wire protocol (message formats, signatures,
  verification rules, security model).
- `TRANSPORTS.md` — email is the only transport in the runner.
  Cloudflare Queues is the planned next one. The rest of that file is
  design notes, not code.
- `SAFEGUARDS.md` — how to run this without getting burned: the
  non-negotiables, containment, the Oracle as a safeguard, and what
  to do when something goes wrong.
- `runner/runner.py` — the agent. Polls IMAP, verifies, executes,
  replies via SMTP. No dependencies beyond Python 3.9 stdlib.
- `runner/install.py` — installs it as a boot-start service: systemd
  (Linux), launchd (macOS), cron @reboot (FreeBSD), Scheduled Task
  (Windows).
- `runner/config.example.json` — copy to `config.json` and fill in.
- `cloud/send_job.py` — cloud-side helper: builds signed job messages,
  verifies result messages. (Your SI uses this logic when dispatching jobs.)
- `tests/test_runner.py` — end-to-end tests with fake IMAP/SMTP servers.
- `RUNBOOK.md` — step-by-step instructions (written for a 5-year-old):
  cloning, pushing, cutting a release, installing, sending a job.
- `examples/hello-world.json` — unsigned example job payload.

## Setup

By default the installer also sets up local inference for the Oracle `ask` op: it installs Ollama (if missing) and pulls a model (`llama3.2:3b` by default). A Raspberry Pi install, detected automatically or selected with `--profile raspberry-pi-home`, pulls the lighter `llama3.2:1b` instead. `--faster` pulls `qwen2.5:1.5b`, a smaller faster model, on any machine. Pass `--inference-model` to choose a tag yourself, or `--no-inference` to skip the model entirely. The runner itself never bundles the model; Ollama runs separately on loopback. `homing-pigeon --faster` uses `qwen2.5:1.5b` for that process only and leaves `config.json` unchanged.

**Easiest: download a release.** No Python needed — each release ships
standalone binaries built by GitHub Actions:

| Platform | Download |
|----------|----------|
| Windows (x64) | `homing-pigeon-windows-x86_64-<version>.zip` → `homing-pigeon.exe` + `install.exe` |
| Linux (x64, Debian/RHEL/Ubuntu/…) | `homing-pigeon-linux-x86_64-<version>.tar.gz` → `homing-pigeon` + `install` |
| macOS (ARM64) | `homing-pigeon-macos-arm64-<version>.tar.gz` → `homing-pigeon` + `install` |

Every archive carries the version in its file name, and extracting it
creates a folder with the same name — so several releases can sit side
by side without overwriting each other. `homing-pigeon --version` (or
`install --version`) reports the build's version.

The Linux binary is built on ubuntu-22.04 (glibc ~2.35). It runs on
Ubuntu 22.04+, recent Debian, and most current distros. We don't ship
binaries for older systems (Debian 11, Ubuntu 20.04, RHEL 8) because of
their older glibc, but the runner itself is stdlib-only Python and runs
fine there: use `pip install pigeon-home-runner` or build from source.

1. Extract the archive on the target machine.
2. Run `install` (or `install.exe` on Windows, from an elevated
   PowerShell). It copies the runner binary, registers the boot-start
   service (systemd / launchd / cron @reboot / Scheduled Task), and —
   on a console — offers the Thunderbird-style setup: browser sign-in,
   a fresh shared secret shown once for you to give your SI, config
   written. No hand-edited JSON needed. On Windows everything lives in
   one home, `C:\homing-pigeon` (`bin/`, `config.json`, `state/`,
   `install-receipt.json`); re-running `install.exe` upgrades the
   binaries in place without touching your config or state. The
   day-to-day commands live there too: `install.exe --check` (doctor),
   `install.exe --console` (run the agent in your terminal),
   `install.exe --oracle` (the chat), `install.exe --logs` (the log).
3. If you skipped it (or run headless), do it later with
   `homing-pigeon --setup`. On an existing config `--setup` offers
   re-login and shared-secret rotation.
4. Prefer to wire it by hand? Edit `config.json` instead. Two ways to
   sign in:
   - **Password** (default): `mailbox_user` + `mailbox_password` (Gmail app
     password, plaintext, on purpose). The HMAC shared secret is a separate
     `shared_secret` value — generate one with `openssl rand -hex 32`.
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
     One gotcha: in the Cloud Console, set the OAuth consent screen to
     "Publish app" (status "In production"). Left in "Testing", Google
     expires the refresh token after 7 days and the runner dies weekly.
     No verification needed — the app stays unverified with the usual
     first-consent warning.
   (your explicit choice for this throwaway account).
5. When you want an SI to send jobs, make sure `shared_secret` in
   config.json matches the string you pasted to the SI in chat
   (the wizard shows you a fresh one; `openssl rand -hex 32` works too).

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
2. The installer generates a random `shared_secret` and stores it in
   `config.json` (or pass your own with `--shared-secret`). Copy that
   string out of `config.json` and give it to your SI — it is the HMAC
   key the SI signs jobs with, and it is separate from the Gmail app
   password.

**From the release files** (same Python requirement): each GitHub
release also ships an sdist (`.tar.gz`) and a universal wheel (`.whl`),
plus standalone binaries (below) and a `SHA384SUMS` file so you can
verify your download:

1. Download the `.whl` from the release.
2. `pip install pigeon_home_runner-*-py3-none-any.whl` — same three
   commands as above.
3. `homing-pigeon-install` copies the runner, writes a default
   `config.json`, and registers the boot-start service.
4. The installer generates a random `shared_secret` and stores it in
   `config.json` (or pass your own with `--shared-secret`). Copy that
   string out of `config.json` and give it to your SI — it is the HMAC
   key the SI signs jobs with, and it is separate from the Gmail app
   password.

**From source** (needs Python 3.9+):

1. Create a **dedicated** Gmail account for the runner, e.g.
   `myname-runner@gmail.com`. Never use a personal inbox.
2. Enable 2-Step Verification, then create an **app password**
   (Google Account → Security → 2-Step Verification → App passwords).
3. Copy `runner/` to the target machine.
4. Copy `config.example.json` to `config.json` and fill in `mailbox_user`
   and `mailbox_password` as above. Replace the `shared_secret`
   placeholder with a generated secret (`openssl rand -hex 32`) — this is
   the HMAC key your SI signs jobs with, separate from the mailbox
   password. (`python3 install.py` generates one for you if the
   placeholder is still there.)
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
script, whatever. The SI needs the `shared_secret` string from your
`config.json` — the random value the installer generated, not the
mailbox password. Then:

```bash
python3 cloud/send_job.py new --kind ping --secret <the-string>
# prints: subject line, blank line, signed body -> send as email to the runner mailbox

python3 cloud/send_job.py new --kind exec --script-file job.sh \
  --interpreter '["bash"]' --file data.csv=https://... --timeout 300 \
  --secret <the-string>
```

Or just paste the string to your SI in chat — it composes, signs, and sends
the job message itself, and reads the result message when it arrives. Large files
are uploaded to cloud storage first; the job message carries the URLs.

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
| `--inspect {board,budget,job,redact}` | Read local Oracle state and exit; no mailbox |
| `--audit-report [--since 14d|48h]` | Summarize the security audit log and exit; no mailbox, read-only |
| `--posture` | Report the runner's security posture (exit 0/1/2) and exit; no mailbox |
| `--oracle` | Open a loopback chat with the Oracle in your browser. Does not poll mail. Turns are appended to `oracle-chat.jsonl` in the base dir (1 MiB, then one backup). See `CONTRIBUTING.md` (maintainer notes: the `--oracle` flag). |
| `--poll-interval SEC`, `--timeout SEC`, `--max-output-bytes N` | Override config |

`install.py` accepts the same flags and bakes them into the installed
service, so the agent on boot runs exactly what you tested:
`python3 runner/install.py --verbose --poll-interval 30`.

```bash
python3 -m unittest discover -s tests -t .
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
4. A result message with `stdout: "pong"` should arrive in the mailbox
   (or at the job's `reply_to` address, if you set one).

## Security notes

- Honest threat model: [docs/threat-model.md](docs/threat-model.md) —
  what this is, what it isn't, and what "anyone holding the shared
  secret effectively owns the box" means for how you deploy it. Its
  companion [docs/security-gaps.md](docs/security-gaps.md) covers
  what the defaults don't protect you from, and the order to turn
  things on.
- Industry map: [docs/industry-map.md](docs/industry-map.md) — five years
  of commercial detection (2021–2026) read honestly against this project,
  sorted by local footprint cost.
- The runner is a **full-trust execution environment**: a valid signed
  job message means arbitrary code as a privileged user. The app password sits in
  **plaintext** in config.json (your explicit
  choice: throwaway account, fresh box). Anyone holding it gets Gmail access.
  The HMAC shared secret is a separate value — anyone holding *it* can sign jobs.
  Don't use this setup with an account you care about.
- Every job is HMAC-SHA-384 signed; the signature is the sole
  authentication gate. Timestamp window and
  replay protection (seen-set) are enforced before anything runs; the
  sender address is logged but never trusted.
- Delivery is at-least-once: if a result email fails to send, the job
  stays unseen and will be re-executed next cycle. Make jobs idempotent
  or check the seen behavior accordingly.
- Size caps: `max_job_bytes` (default 4 MiB) bounds the raw mail before
  the signature is even checked; `max_script_bytes` (default 1 MiB)
  bounds the script after verification. Either rejects through the
  normal reject path; `0` means unlimited. A negative or non-integer
  value is a startup config error.
- Optional hardening controls (all off by default): see [SECURITY.md](SECURITY.md).
- Hardening ideas still open: encrypted credentials at rest,
  per-job encryption, result file upload for large outputs. The
  Oracle is implemented: result policies, signed attestations,
  and a query budget, so a cloud SI learns *answers* about your output
  without ever seeing it.

## Roadmap

- 2.0 = who signs (shipped)
- 3.0 = what comes back — the Oracle: result policies, attestations, task dispatch, multi-secret, and the ask op (shipped as 3.0.0). The ask endpoint must be loopback or the op stays off.
- v9 = watch the Oracle think — the loopback dashboard, and confidentiality for transport messages (spec in ORACLE_DASHBOARD.md, not started)
- v9 = the VR Oracle — walk through your jobs in 3D (ahead of schedule, expected before the other v9)

Product and protocol versions are separate numbers: the product is
at 3.7.x; the wire protocol implemented is v2, with PROTOCOL.md
keeping the v1 specification of record. Unwritten future work
takes the single placeholder label v9.

Later:
- Cloudflare Queues as Transport #2

## Status

v3.7.2. The runner's state dir now follows the config file, not the
user running it: the installed service (often SYSTEM) and a manual
`--oracle` chat on the same `--config` finally see the same jobs.
Also: `--oracle` prints which config it loaded and whether a model is
set, and Ctrl+C on the frozen exe exits quietly.

v3.7.1. Test attribution cleanup; no functional changes since v3.7.0.

v3.7.0. Jobs can now ask for their result to be emailed back to the
requester: set `reply_to` in the signed job body (or
`send_job.py new --reply-to you@example.com`) and the result skips
the runner mailbox and lands in your inbox. The address must come
from inside the signed body — the email's `From` header is never
trusted — so a spoofed sender can't steer results at anyone. Omit
it and results behave as before.

v3.6.1. Optional hardening controls, all off unless you turn them on:
key policy for env, files, and args (including the dangerous-env
gate and `allow_file_urls`/`max_args`); audience binding
(`runner_id`, 128-bit, `--aud` on send_job.py); a security audit log
with per-key `key_policies` fragments via `--audit-report`;
Linux bubblewrap confinement; running a job as another POSIX user;
and `secret_files`. See SECURITY.md. `--posture` and
`--audit-report` read that state without opening the mailbox.

v3.6.0 shipped the M0–M11 hardening pass this builds on. v3.0.0
shipped the Oracle: result policies, signed attestations, task
dispatch, multi-secret installs, and the `ask` op. Later 3.x releases
added the loopback Oracle chat (`--oracle`), the Raspberry Pi
inference profile (`llama3.2:1b`), and the hardening above. The
package version lives in `pyproject.toml`.

Still true from earlier releases. Any sender may submit a job, and the
HMAC is the only gate. `config.json` hot-reloads poll interval,
workers, timeouts, output limits, and max job age. A `security` mode
change still needs a restart. Thunderbird-style Google sign-in is
shipped. PowerShell jobs stage as `script.ps1`. Release binaries carry
Sigstore build provenance. The suite is
`python3 -m unittest discover -s tests -t .`.

## Mirrors

- GitLab: https://gitlab.com/pigeon-home/homing-pigeon
- SourceForge: https://sourceforge.net/projects/homing-pigeon/
- Randall Munroe: [xkcd 568](https://xkcd.com/568/) "You'll never find a programming language that frees you from the burden of clarifying your ideas." (Except with English + SI + a long context paragraph clarifying your ideas => the cycle begins again)
