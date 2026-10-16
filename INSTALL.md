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
  -e PIGEON_MAILBOX_USER="your-runner@gmail.com" \
  -e PIGEON_MAILBOX_PASSWORD="your-app-password" \
  -e PIGEON_SHARED_SECRET="your-256-bit-shared-secret" \
  -v pigeon-data:/data \
  ghcr.io/pigeon-home/homing-pigeon:latest
```

No Python, no git, nothing else. See [DOCKER.md](DOCKER.md) for
dry-run mode, config options, and updating.

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
# edit ~/.homing-pigeon/config.json — add your Gmail + app password
# (the installer generates a shared_secret for you; give that string to your SI)
homing-pigeon --config ~/.homing-pigeon/config.json --once
```

## 3. Release binary

**Install:** download and extract. Every default OS ships a
downloader — no extra tools needed.

Linux (curl is always there):
```bash
curl -sL -o pigeon.tar.gz https://github.com/Pigeon-Home/homing-pigeon/releases/latest/download/homing-pigeon-linux-x86_64.tar.gz
tar xzf pigeon.tar.gz
```

macOS (same):
```bash
curl -sL -o pigeon.tar.gz https://github.com/Pigeon-Home/homing-pigeon/releases/latest/download/homing-pigeon-macos-arm64.tar.gz
tar xzf pigeon.tar.gz
```

Windows 11 (PowerShell has Invoke-WebRequest built in):
```powershell
Invoke-WebRequest -Uri https://github.com/Pigeon-Home/homing-pigeon/releases/latest/download/homing-pigeon-windows-x86_64.zip -OutFile pigeon.zip
Expand-Archive pigeon.zip .
```

**Run:** start the service.

- **Windows:** run `install.exe` — registers a Scheduled Task that
  starts at boot. By default it runs as SYSTEM; for least privilege,
  create a dedicated local account first and install with
  `install.exe --run-as pigeon` (schtasks will prompt for the
  account's password; service accounts like `NT AUTHORITY\Network
  Service` and gMSA names ending in `$` need none). A named account
  runs at `LIMITED` run level instead of `HIGHEST`. Give the account
  read access to the install dir and config, and full control of the
  base dir (state, audit log, job workdirs) — and nothing else.
- **Linux:** run `python3 install.py` — registers a systemd service
  (or cron `@reboot` fallback).
- **macOS:** run `python3 install.py` — registers a launchd agent.

Then sign in: run the app once with `homing-pigeon --setup` (or let
`install.py` offer it) — Thunderbird-style browser sign-in, a fresh
shared secret shown once for you to give to your cloud SI, config
written. No hand-edited JSON needed. If you'd rather wire it by hand,
edit `config.json` (add your Gmail + app password) instead, then send
the clock check below.

### Working scenario

Checked against a working simulation (Windows-shaped profile, no live
Gmail, no live model). The same steps are locked in
`tests/test_first_run_scenario.py`. The strings there are the ones
the simulation used.

1. First launch with no `config.json`, and no console, exits 2 and
   tells you to run `--setup`. There is no traceback.
2. `homing-pigeon --setup`. Choice `[1]` opens the browser sign-in.
   Choice `[2]` asks for a Gmail app password. Either way the written
   config has `imap.gmail.com:993` and `smtp.gmail.com:587`, even
   when the example file was not next to the binary. A failed mailbox
   probe prints a warning and still saves the file. Closing the
   window mid-prompt exits with "setup needs a console".
3. Put `flag.txt` on the Desktop. Tell the Oracle it is a password:
   `owner_instructions`, `protected_paths` pointing at that Desktop,
   and a `redact_patterns_extra` entry for the flag text. Set
   `max_result_view` to `redacted`.
4. `homing-pigeon --config config.json --inspect redact` with the
   flag on stdin prints `[REDACTED:flag]` and not the flag.
   `--once --dry-run` exits 0. A closed mail port is a logged poll
   failure, not a traceback, and the shared secret is not printed.

---

Whichever path you pick, **verify** with the clock check from
[RUNBOOK.md](RUNBOOK.md) Job 7. If the runner replies with the time,
you're live.

> **Note:** the runner re-reads `config.json` every poll cycle and
> picks up changes to `poll_interval_sec`, `workers`,
> `default_timeout_sec`, `max_output_bytes`, and `max_job_age_sec`
> automatically — no restart needed. Changing the mailbox credentials
> or the shared secret still requires a restart.
