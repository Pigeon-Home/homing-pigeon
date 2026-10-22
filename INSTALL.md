# INSTALL.md — Get the runner going

Three ways, simplest first. Each has two phases: **install** (get the
files on the box) and **run** (start the runner). Don't mix them.

## 1. Docker

**Install:** pull the image.

```bash
docker pull ghcr.io/pigeon-home/homing-pigeon:latest
```

**Run:**

```bash
docker run -d --name pigeon --restart unless-stopped \
  -e PIGEON_MAILBOX_USER="your-runner@example.com" \
  -e PIGEON_MAILBOX_PASSWORD="your-app-password" \
  -e PIGEON_SHARED_SECRET="your-256-bit-shared-secret" \
  -v pigeon-data:/data \
  ghcr.io/pigeon-home/homing-pigeon:latest
```

No Python, no git, nothing else. See [DOCKER.md](docs/archive/DOCKER.md) for
dry-run mode, config options, and updating.

### The Python floor on older enterprise distributions

The runner needs Python 3.9 or newer (`requires-python` in
`pyproject.toml`). openSUSE Leap 15 and RHEL/AlmaLinux/Rocky 8
ship a system `python3` of 3.6 and carry a supported interpreter as
a separate package -- `zypper install python311` or `dnf install
python3.11` -- so run the installer with that interpreter
(`python3.11 install.py`). Rocky/Alma 9, Debian 11+, Ubuntu 22.04+,
Fedora, Amazon Linux 2023 and Alpine 3 ship 3.9 or newer already.
The platform matrix proves each of these.

## 2. pip (best for Raspberry Pi)

**Install:**

```bash
pip install pigeon-home-runner
```

On RHEL, CentOS, Rocky, or AlmaLinux, install Python 3.9+ first:

```bash
# RHEL 8 / Rocky 8 / AlmaLinux 8
sudo dnf install -y python39
python3.9 -m pip install pigeon-home-runner

# RHEL 9 / Rocky 9 / AlmaLinux 9 (Python 3.9 is default)
sudo dnf install -y python3-pip
pip3 install pigeon-home-runner
```

On Debian and Ubuntu, install Python 3.9+ first:

```bash
# Debian 11+ (Python 3.9+ is default)
sudo apt install -y python3-pip
pip3 install pigeon-home-runner

# Ubuntu 20.04 (default Python is 3.8, too old)
sudo apt update && sudo apt install -y python3.9 python3.9-venv
python3.9 -m pip install pigeon-home-runner

# Ubuntu 22.04+ (Python 3.10+ is default)
sudo apt install -y python3-pip
pip3 install pigeon-home-runner
```

**Run:** register the boot service, configure, test.

```bash
homing-pigeon-install
# edit ~/.homing-pigeon/config.json — add your mailbox address + app password
# (the installer generates a shared_secret for you; give that string to your SI)
homing-pigeon --config ~/.homing-pigeon/config.json --once
```

### Raspberry Pi: Pi Light

A Pi install — detected automatically from the device tree, or
chosen anywhere with `--profile pi-light` — is the light package.
You get the full runner and the full protocol: your cloud SI
pings signed jobs in, jobs run, results and attestations go back,
the senses and local signals work, and the Oracle still watches,
wakes on a serious signal, and files its briefs.

What the Pi does **not** get is a local model. The installer
installs no Ollama and downloads no model — nothing for
inference touches the box. The Oracle runs in deterministic mode
(`oracle_mode: "deterministic"` in `config.json`): briefs and
answers are assembled from the box's own records — the job
index, retained jobs and their notable lines, the log tail —
instead of a model's narration. The diagnosis is the
deterministic kind: what ran, what failed, what the records say.

When Pis ship with neural accelerator chips worth using, the
same install upgrades in place: set `oracle_mode` to `llm` in
`config.json` and re-run the installer with `--inference-only` to
pull a model. Nothing reinstalls and nothing else changes.
A USB accelerator (Coral, Intel NCS, Hailo) is not that Pi and
is not a computer. Seeing one does not change the install. The
installer says so and still installs no model.

### What is not a runner

The Pi archive and the Docker image are both Linux. A
television is not. The installer refuses these, and does not
copy files onto them:

- Samsung Tizen, LG webOS, Roku, Apple TV
- a USB accelerator with no Linux host under it
- any environment that cannot execute a shell

Android -- Android TV, Google TV, Fire TV, Shield -- is the one
television family where a shell is obtainable: a sideloaded
terminal environment gives this program a real Python, and the
runner only needs outbound mail. There the installer proceeds
and states the limits before copying files: no service is
registered (keep the terminal environment running, or use its
boot hook), no model is installed, and there is no sandbox, so
jobs run unsandboxed as the terminal app's user. An Android
environment with no shell (a signed TV app) is refused like any
other set.

Code signing can put an app on the screen. It cannot give this
program a shell, and a job runs by executing a shell. The
repair proofs (Alpine with no bash, the arm64 Pi archive) do
not apply there, and CI does not pretend to boot those
systems.

A Linux board behind the television is a normal install. If
the board is dedicated and the screen is only a screen, use
`--profile display-board`. That is Pi Light's stance — full
runner, deterministic Oracle, no model — without claiming the
board is a Raspberry Pi. Docker is the published Linux image,
not a third kind of machine; the installer says that and
continues.

## 3. Release binary

**Install:** download and extract. Every default OS ships a
downloader — no extra tools needed. Release file names carry the
version (for example `homing-pigeon-linux-x86_64-<version>.tar.gz`), and
extracting creates a folder with the same name, so several releases
can live side by side.

Linux (curl is always there):
```bash
ver=$(curl -s https://api.github.com/repos/Pigeon-Home/homing-pigeon/releases/latest | python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'].lstrip('v'))")
curl -sL -o pigeon.tar.gz "https://github.com/Pigeon-Home/homing-pigeon/releases/latest/download/homing-pigeon-linux-x86_64-$ver.tar.gz"
tar xzf pigeon.tar.gz
cd "homing-pigeon-linux-x86_64-$ver"
```

Raspberry Pi (Pi Light — its own archive, ARM64 like the Pi, with
the light profile as its baked-in default):
```bash
ver=$(curl -s https://api.github.com/repos/Pigeon-Home/homing-pigeon/releases/latest | python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'].lstrip('v'))")
curl -sL -o pigeon.tar.gz "https://github.com/Pigeon-Home/homing-pigeon/releases/latest/download/homing-pigeon-pi-light-arm64-$ver.tar.gz"
tar xzf pigeon.tar.gz
cd "homing-pigeon-pi-light-arm64-$ver"
```
Then run `install` in the folder. The archive carries a
`default_profile` marker naming `pi-light`, so the install
selects Pi Light by itself — no `--profile` flag to remember,
and no model is installed or downloaded (see "Raspberry Pi:
Pi Light" in §2). The other archives carry no marker and keep
the ordinary defaults.

macOS (same):
```bash
ver=$(curl -s https://api.github.com/repos/Pigeon-Home/homing-pigeon/releases/latest | python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'].lstrip('v'))")
curl -sL -o pigeon.tar.gz "https://github.com/Pigeon-Home/homing-pigeon/releases/latest/download/homing-pigeon-macos-arm64-$ver.tar.gz"
tar xzf pigeon.tar.gz
cd "homing-pigeon-macos-arm64-$ver"
```

Windows 11 (PowerShell has Invoke-WebRequest built in):
```powershell
$ver = (Invoke-RestMethod https://api.github.com/repos/Pigeon-Home/homing-pigeon/releases/latest).tag_name.TrimStart('v')
Invoke-WebRequest -Uri "https://github.com/Pigeon-Home/homing-pigeon/releases/latest/download/homing-pigeon-windows-x86_64-$ver.zip" -OutFile pigeon.zip
Expand-Archive pigeon.zip .
cd "homing-pigeon-windows-x86_64-$ver"
```

**Run:** start the service.

- **Windows:** run `install.exe` from an elevated PowerShell. It creates
  the one home at `C:\homing-pigeon` — `bin/` (the exes, including a
  copy of the installer itself), `config.json`, `state/`, and
  `install-receipt.json` — locks it down to SYSTEM + Administrators
  (a named `--run-as` account is granted access too), and registers a
  Scheduled Task that starts at boot. By default the task runs as
  SYSTEM; for least privilege, create a dedicated local account first
  and install with `install.exe --run-as pigeon` (schtasks will prompt
  for the account's password; service accounts like
  `NT AUTHORITY\Network Service` and gMSA names ending in `$` need
  none). A named account runs at `LIMITED` run level instead of
  `HIGHEST`. The service, a terminal run, and `--oracle` all use the
  same `C:\homing-pigeon\config.json`, so there is one state dir and
  no more SYSTEM-vs-user split. Re-running `install.exe` is safe: it
  upgrades the binaries in place and never touches `config.json` or
  `state/`. Five commands to learn (from `C:\homing-pigeon\bin`):
  `install.exe --check` (doctor: verifies the home, the receipt, the
  task, the config, and the inference endpoint, and says what's wrong
  in plain language), `install.exe --console` (stops the task, runs
  the agent in your terminal with live logs, restarts the task on
  Ctrl+C), `install.exe --oracle` (the Oracle chat), `install.exe
  --logs [--follow]` (tail or watch the runner log), and `install.exe
  --wipe` (backs everything up into one zip, then removes the home,
  the task, and every scattered state dir). The less common flags:
  `--home DIR` picks a different one-home root; `--migrate` copies
  state found in older install locations into the one home;
  `--backup-dir DIR` and `--no-backup` steer or skip the zip that
  `--wipe` writes; `--lines N` sets how much `--logs` prints; and
  `--shared-secret SECRET` writes that secret into `config.json`
  (replacing whatever is there) instead of generating one; it must
  pass the same 128-bit entropy gate the runner applies at startup.
- **Linux:** run `./install` — registers a systemd service.
- **macOS:** run `./install` — registers a launchd agent.

Then sign in: run the app once with `homing-pigeon --setup` (or let
`install` offer it) — Thunderbird-style browser sign-in, a fresh
shared secret shown once for you to give to your cloud SI, config
written. No hand-edited JSON needed. If you'd rather wire it by hand,
edit `config.json` (add your mailbox address + app password) instead, then send
the clock check below.

The installer also sets up the Oracle's local model: it installs
Ollama and pulls a small local model, then points `config.json` at it, so
the `--oracle` chat answers on the box with nothing leaving it. If
that step doesn't finish (it downloads a couple of gigabytes), the
Oracle chat says so and tells you how to fix it — re-running
`install.exe --inference-only` is safe and only retries the model
setup, leaving the rest of your install alone. Pass
`--no-inference` to skip it entirely.

## 4. The full walkthrough

By default the installer also sets up local inference for the Oracle `ask` op: it installs Ollama (if missing) and pulls a model (`qwen3:1.7b` by default). A Raspberry Pi install, detected automatically or selected with `--profile pi-light`, is Pi Light instead: no model is installed or downloaded, and the Oracle runs deterministically (see "Raspberry Pi: Pi Light" in §2). `--faster` pulls `qwen2.5:3b`, a faster model, on any machine. Pass `--inference-model` to choose a tag yourself, or `--no-inference` to skip the model entirely. The runner itself never bundles the model; Ollama runs separately on loopback. `homing-pigeon --faster` uses `qwen2.5:3b` for that process only and leaves `config.json` unchanged.

**Easiest: download a release.** No Python needed — each release ships
standalone binaries built by GitHub Actions. The common computer
that does not ship with Python is a Windows PC. Download the
Windows zip. Do not install Python. `homing-pigeon.exe` carries
its own interpreter, and so do the Linux and macOS binaries. The
release build proves the drop: the Linux binary is started in a
Debian image that has no `python3`, and the Windows binary is
started with Python taken off `PATH`.

| Platform | Download |
|----------|----------|
| Windows (x64) | `homing-pigeon-windows-x86_64-<version>.zip` → `homing-pigeon.exe` + `install.exe` |
| Windows (ARM64) | `homing-pigeon-windows-arm64-<version>.zip` → `homing-pigeon.exe` + `install.exe` |
| Linux (x64, Debian/RHEL/Ubuntu/…) | `homing-pigeon-linux-x86_64-<version>.tar.gz` → `homing-pigeon` + `install` |
| Linux (ARM64, a board that is not asking for Pi Light) | `homing-pigeon-linux-arm64-<version>.tar.gz` → `homing-pigeon` + `install` |
| macOS (ARM64) | `homing-pigeon-macos-arm64-<version>.tar.gz` → `homing-pigeon` + `install` |
| macOS (Intel) | `homing-pigeon-macos-x86_64-<version>.tar.gz` → `homing-pigeon` + `install` |
| Raspberry Pi (ARM64, Pi Light) | `homing-pigeon-pi-light-arm64-<version>.tar.gz` → `homing-pigeon` + `install` |

Every archive carries the version in its file name, and extracting it
creates a folder with the same name — so several releases can sit side
by side without overwriting each other. `homing-pigeon --version` (or
`install --version`) reports the build's version.

The Linux binary is built on ubuntu-22.04 (glibc ~2.35). It runs on
Ubuntu 22.04+, recent Debian, and most current distros. We don't ship
binaries for older systems (Debian 11, Ubuntu 20.04, RHEL 8) because of
their older glibc, but the runner itself is stdlib-only Python and runs
fine there: use `pip install pigeon-home-runner` or build from source.

The frozen binaries are built on the architecture they run on.
PyInstaller freezes the interpreter it was built with, so there is
no cross-compile. x86_64 and ARM64 are the ones with a native
runner, for Linux, Windows, and macOS. The other architectures in
the platform matrix (armv7, i386, ppc64le, s390x, riscv64, the
BSDs) run from source; they are proved there, and they do not get
a frozen binary. A television still does not. Tizen, webOS, Roku,
and Apple TV cannot exec a shell. The computer behind that screen,
if it is a Linux board you control, is the Linux archive above,
and that board does not need Python either.

1. Extract the archive on the target machine. Beside the binaries
   is `project/`: the whole Homing Pigeon project that built this
   release (source, tests, docs, the CI workflows, the full git
   history as `project/.history/homing-pigeon.bundle`, and the
   build's CI results). `project/PROJECT-SNAPSHOT.md` is its index.
   The installer copies it into the state dir, where the Oracle
   reads it with no network.
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
   - **Password** (default): `mailbox_user` + `mailbox_password` (the
     mailbox's app password, plaintext, on purpose). The HMAC shared secret is a separate
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
6. **More than one signer?** Give each its own key instead of sharing
   the one secret: `python3 runner/install.py --additional-secret
   grok-4` generates a 256-bit secret under `additional_secrets`
   with that key ID (on a fresh install; on an existing Windows
   one-home install edit `config.json` by hand), and a matching
   `key_policies` entry limits what that key may do. The signer then
   passes `--key-id grok-4` to `send_job.py`. Rotation and the policy
   details: `docs/secret-rotation.md`, PROTOCOL.md section 14.

**From source** (needs Python 3.9+):

1. Create a **dedicated** mail account for the runner, e.g.
   `myname-runner@example.com`. Never use a personal inbox.
2. Enable two-step verification on the account, then create an
   **app password** for the runner in the provider's security
   settings.
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
`~/.homing-pigeon`; on Windows the one-home default is
`C:\homing-pigeon`); `install.py --uninstall` removes the service.

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
VM internet access (NAT is fine) so it can reach the mailbox's IMAP/SMTP
servers, install the Linux release binary inside the guest, and point your jobs
at it. The host never needs to know.

### Working scenario

Checked against a working simulation (Windows-shaped profile, no live
mailbox, no live model). The same steps are locked in
`tests/test_first_run_scenario.py`. The strings there are the ones
the simulation used.

1. First launch with no `config.json`, and no console, exits 2 and
   tells you to run `--setup`. There is no traceback.
2. `homing-pigeon --setup`. Choice `[1]` opens the browser sign-in.
   Choice `[2]` asks for an app password for the mailbox. Either
   way the written config pre-fills the recommended provider's
   IMAP and SMTP hosts (ports 993 and 587), even when the example
   file was not next to the binary. A failed mailbox
   probe prints a warning and still saves the file. Closing the
   window mid-prompt exits with "setup needs a console".
3. Put `flag.txt` on the Desktop. Tell the Oracle it is a password:
   `owner_instructions`, `protected_paths` pointing at that Desktop,
   and a `redact_patterns_extra` entry for the flag text. Set
   `max_result_view` to `redacted`.
4. `homing-pigeon --config config.json --inspect redact` with the
   flag on stdin prints `[REDACTED:flag]` and not the flag.
   `--once --dry-run` exits 0. A dry run starts no transport
   extensions and never opens the mailbox, and the shared secret
   is not printed.

---

Whichever path you pick, **verify** with the clock check from
[docs/RUNBOOK.md](docs/RUNBOOK.md) Job 7. If the runner replies with the time,
you're live.

> **Note:** the runner re-reads `config.json` every poll cycle and
> picks up changes to `poll_interval_sec`, `workers`,
> `default_timeout_sec`, `max_output_bytes`, and `max_job_age_sec`
> automatically — no restart needed. Changing the mailbox credentials
> or the shared secret still requires a restart.
