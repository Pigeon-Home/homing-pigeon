# INSTALL.md — Get the runner going

Three ways, simplest first. All of them end with the same thing: a
machine polling your inbox for signed jobs.

## 1. Docker (fastest)

```bash
docker run -d --name pigeon --restart unless-stopped \
  -e PIGEON_MAILBOX_USER="your-runner@gmail.com" \
  -e PIGEON_MAILBOX_PASSWORD="your-app-password" \
  -v pigeon-data:/data \
  ghcr.io/pigeon-home/homing-pigeon:latest
```

No Python, no git, no service setup. See [DOCKER.md](DOCKER.md) for
dry-run mode, config options, and updating.

## 2. pip (best for Raspberry Pi)

```bash
pip install pigeon-home
homing-pigeon-install
```

Edit the `config.json` it writes (add your Gmail + app password),
then test one cycle:

```bash
homing-pigeon --config ~/.homing-pigeon/config.json --once
```

## 3. Release binary (Windows / macOS / Linux)

Grab the zip/tarball from
[releases](https://github.com/Pigeon-Home/homing-pigeon/releases),
extract it, and run the installer:

- **Windows:** `install.exe` (installs a Scheduled Task)
- **Linux/macOS:** `python3 install.py` (systemd / launchd / cron)

Then edit `config.json` the same way.

---

Whichever path you pick, the next step is the same: send it the
clock-check from [RUNBOOK.md](RUNBOOK.md) Job 7. If it replies with
the time, you're live.
