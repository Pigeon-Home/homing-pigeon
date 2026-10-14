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
  -v pigeon-data:/data \
  ghcr.io/pigeon-home/homing-pigeon:latest
```

No Python, no git, nothing else. See [DOCKER.md](DOCKER.md) for
dry-run mode, config options, and updating.

## 2. pip (best for Raspberry Pi)

**Install:**

```bash
pip install pigeon-home
```

**Run:** register the boot service, configure, test.

```bash
homing-pigeon-install
# edit ~/.homing-pigeon/config.json — add your Gmail + app password
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
  starts at boot.
- **Linux:** run `python3 install.py` — registers a systemd service
  (or cron `@reboot` fallback).
- **macOS:** run `python3 install.py` — registers a launchd agent.

Then edit `config.json` (add your Gmail + app password) and send the
clock check below.

---

Whichever path you pick, **verify** with the clock check from
[RUNBOOK.md](RUNBOOK.md) Job 7. If the runner replies with the time,
you're live.

> **Note:** the runner re-reads `config.json` every poll cycle and
> picks up changes to `poll_interval_sec`, `workers`,
> `default_timeout_sec`, `max_output_bytes`, and `max_job_age_sec`
> automatically — no restart needed. Changing the mailbox credentials
> still requires a restart.
