# Homing Pigeon in Docker

> **Archived — not current guidance.** This page is a historical
> record of an earlier Docker setup, kept for reference only.
> For the install paths that ship today, see
> [INSTALL.md](../../INSTALL.md).

The fastest way to run the runner. No Python to install, no git clone,
no service configuration — one `docker run` and your inbox becomes a
job queue.

## Quick start

```bash
docker run -d --name pigeon --restart unless-stopped \
  -e PIGEON_MAILBOX_USER="your-runner@gmail.com" \
  -e PIGEON_MAILBOX_PASSWORD="your-app-password" \
  -e PIGEON_SHARED_SECRET="your-256-bit-shared-secret" \
  -v pigeon-data:/data \
  ghcr.io/pigeon-home/homing-pigeon:latest
```

That's the whole install. The container polls your inbox every 20
seconds and executes signed jobs. State (`seen.json`, job workdirs)
lives in the `pigeon-data` volume, so restarts and updates don't
re-run jobs.

## Try it before you commit

```bash
docker run --rm \
  -e PIGEON_MAILBOX_USER="your-runner@gmail.com" \
  -e PIGEON_MAILBOX_PASSWORD="your-app-password" \
  -e PIGEON_SHARED_SECRET="your-256-bit-shared-secret" \
  ghcr.io/pigeon-home/homing-pigeon:latest --once --dry-run --verbose
```

`--dry-run` polls the inbox and logs what it finds without executing
anything or marking mail seen. Nothing changes. Safe first run.

## Send it a job

From anywhere — your laptop, your phone, your cloud SI:

```bash
# On your machine (needs the repo):
python3 cloud/send_job.py new --kind ping --secret "your-shared-secret"
```

Copy the subject + body it prints, email it to `your-runner@gmail.com`.
A reply with `stdout: "pong"` arrives within a poll interval.

Or skip the script entirely — paste the RUNBOOK Job 7 prompt to your
cloud SI and let it do the whole thing.

## Configuration

**Environment variables** (recommended). The entrypoint writes
`/data/config.json` from them on first start:

| Variable | Required | Default |
|---|---|---|
| `PIGEON_MAILBOX_USER` | yes | — |
| `PIGEON_MAILBOX_PASSWORD` | yes | — |
| `PIGEON_SHARED_SECRET` | yes | — |
| `PIGEON_IMAP_HOST` | no | `imap.gmail.com` |
| `PIGEON_IMAP_PORT` | no | `993` |
| `PIGEON_SMTP_HOST` | no | `smtp.gmail.com` |
| `PIGEON_SMTP_PORT` | no | `587` |
| `PIGEON_POLL_INTERVAL` | no | `20` |
| `PIGEON_WORKERS` | no | `1` |
| `PIGEON_TIMEOUT` | no | `300` |
| `PIGEON_MAX_OUTPUT` | no | `100000` |

The HMAC shared secret is a separate `shared_secret` value (same as the bare-metal
install) — set it via `PIGEON_SHARED_SECRET`. Throwaway account, nothing personal — see SECURITY.md.

**Mounted config file.** If you already have a `config.json`, mount it
instead. Env vars are ignored when the file exists:

```bash
docker run -d --name pigeon --restart unless-stopped \
  -v /path/to/config.json:/data/config.json:ro \
  -v pigeon-data:/data \
  ghcr.io/pigeon-home/homing-pigeon:latest
```

## Logs

```bash
docker logs pigeon      # recent output
docker logs -f pigeon   # follow live
```

## Updating

```bash
docker pull ghcr.io/pigeon-home/homing-pigeon:latest
docker stop pigeon && docker rm pigeon
# re-run the same docker run command from Quick start
```

Your `pigeon-data` volume survives — no jobs re-run after update.

## Build it yourself

Don't want the published image? Build from source:

```bash
git clone https://github.com/Pigeon-Home/homing-pigeon.git
cd homing-pigeon
docker build -t homing-pigeon .
```

Then replace `ghcr.io/pigeon-home/homing-pigeon:latest` with
`homing-pigeon` in any command above.

## Security notes

- Runs as a **non-root** user inside the container. Never needs root.
- **No inbound network.** The runner polls IMAP outbound and sends SMTP
  outbound. No ports exposed, no ports published, nothing listens.
- Published images are signed with Sigstore. Verify:
  ```bash
  cosign verify ghcr.io/pigeon-home/homing-pigeon:latest \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com
  ```
