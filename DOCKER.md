# Homing Pigeon in Docker

Run the runner as a container. No Python, no git, no local install —
just Docker and a Gmail account.

## Build it

```bash
git clone https://github.com/Pigeon-Home/homing-pigeon.git
cd homing-pigeon
docker build -t homing-pigeon .
```

## Quick start

```bash
docker run -d --name pigeon --restart unless-stopped \
  -e PIGEON_MAILBOX_USER="your-runner@gmail.com" \
  -e PIGEON_MAILBOX_PASSWORD="your-app-password" \
  -v pigeon-data:/data \
  homing-pigeon
```

That's it. The container polls your inbox every 20 seconds and executes
signed jobs. State (`seen.json`, job workdirs) lives in the `pigeon-data`
volume, so restarts don't re-run jobs.

## Configuration

Two ways, pick one:

**Environment variables** (shown above). The entrypoint writes
`/data/config.json` from them on first start:

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `PIGEON_MAILBOX_USER` | yes | — | Runner's Gmail address |
| `PIGEON_MAILBOX_PASSWORD` | yes | — | Gmail app password (this is also the HMAC secret) |
| `PIGEON_IMAP_HOST` | no | `imap.gmail.com` | IMAP server |
| `PIGEON_IMAP_PORT` | no | `993` | IMAP port |
| `PIGEON_SMTP_HOST` | no | `smtp.gmail.com` | SMTP server |
| `PIGEON_SMTP_PORT` | no | `587` | SMTP port |
| `PIGEON_POLL_INTERVAL` | no | `20` | Seconds between inbox polls |
| `PIGEON_WORKERS` | no | `1` | Parallel job workers |
| `PIGEON_TIMEOUT` | no | `300` | Default job timeout (seconds) |
| `PIGEON_MAX_OUTPUT` | no | `100000` | Max captured output bytes |

**Mounted config file.** If you already have a `config.json`, mount it
instead — env vars are ignored when the file exists:

```bash
docker run -d --name pigeon --restart unless-stopped \
  -v /path/to/config.json:/data/config.json:ro \
  -v pigeon-data:/data \
  homing-pigeon
```

## Trying it without committing

```bash
# Run once, print what it would do, change nothing:
docker run --rm \
  -e PIGEON_MAILBOX_USER="your-runner@gmail.com" \
  -e PIGEON_MAILBOX_PASSWORD="your-app-password" \
  homing-pigeon --once --dry-run --verbose
```

`--dry-run` polls the inbox and logs what it finds without executing
anything or marking mail seen. Safe first run.

## Send it a job

From anywhere — your laptop, your phone, your SI:

```bash
# On your machine (needs the repo):
python3 cloud/send_job.py new --kind ping --secret "your-app-password"
# Copy the subject + body it prints, email it to your-runner@gmail.com.
# A reply with stdout: "pong" arrives within a poll interval.
```

Or paste the RUNBOOK Job 7 prompt to your cloud SI and let it do the
whole thing.

## Logs

```bash
docker logs pigeon         # recent logs
docker logs -f pigeon      # follow
```

## Updating

```bash
docker pull homing-pigeon
docker stop pigeon && docker rm pigeon
# re-run the same docker run command as before
```

The `pigeon-data` volume keeps your state — no jobs re-run after update.

## Security notes

- The container runs as a **non-root** user. It never needs root.
- It makes **no inbound network connections** — it polls IMAP outbound
  and sends SMTP outbound. No ports are exposed or published.
- The app password sits in `/data/config.json` inside the volume (or in
  env vars you passed). Same plaintext tradeoff as the bare-metal
  install: throwaway account, nothing personal. See SECURITY.md.
- Images are signed with Sigstore/cosign. Verify:
  ```bash
  cosign verify homing-pigeon \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com
  ```
  (Signing applies to registry-published images; a locally built image
  is trusted because you built it.)
