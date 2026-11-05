# Homing Pigeon in Docker

> **Reference page for the Docker image.** It documents the
> environment variables `.github/docker/entrypoint.sh` reads, the dry-run
> invocation, and updating; those parts are checked against the
> live Dockerfile (last: 2026-10-21). The install paths that ship
> today, Docker included, are in [INSTALL.md](../../INSTALL.md),
> which points here for these three topics.

The fastest way to run the runner. No Python to install, no git clone,
no service configuration — write one config file, mount it, and one
`docker run` turns your inbox into a job queue.

## Quick start

Write a `config.json` first, and state the security gates you mean to
run in it explicitly:

```json
{
  "mailbox_user": "your-runner@gmail.com",
  "mailbox_password": "your-app-password",
  "shared_secret": "your-256-bit-shared-secret",
  "base_dir": "/data/work",
  "security": {"modes": {"confinement": "off",
                         "job_user": "off"}}
}
```

Then mount it into `/data`:

```bash
docker run -d --name pigeon --restart unless-stopped \
  -v /path/to/config.json:/data/config.json:ro \
  -v pigeon-data:/data \
  ghcr.io/pigeon-home/homing-pigeon:latest
```

Why a written config, and why the gates are stated in it: the config
the entrypoint builds from environment variables alone carries no
`security` block, and under the default an unstated confinement reads
`enforce`. A plain `docker run` cannot create the user namespace
bwrap needs, so a runner started that way refuses to start. The
written config above states the gates off — that is the route the
project's own Docker workflow smoke-tests before it publishes the
image, and it proves the image starts, not the gates. If you mean to
run a gate, state the mode you mean in the `security` block instead
of leaving it unstated.

That's the whole install. The container polls your inbox every 20
seconds and executes signed jobs. State (`seen.json`, job workdirs)
lives in the `pigeon-data` volume, so restarts and updates don't
re-run jobs.

## Try it before you commit

Use the same written `config.json` from Quick start:

```bash
docker run --rm \
  -v /path/to/config.json:/data/config.json:ro \
  -v pigeon-data:/data \
  ghcr.io/pigeon-home/homing-pigeon:latest --config /data/config.json --once --dry-run --verbose
```

`--dry-run` polls the inbox and logs what it finds without executing
anything or marking mail seen. Nothing changes. Safe first run.

## Send it a job

From anywhere — your laptop, your phone, your cloud SI:

```bash
# On your machine (needs the repo):
python3 runner/cloud/send_job.py new --kind ping --secret "your-shared-secret"
```

Copy the subject + body it prints, email it to `your-runner@gmail.com`.
A reply with `stdout: "pong"` arrives within a poll interval.

Or skip the script entirely — paste the RUNBOOK Job 7 prompt to your
cloud SI and let it do the whole thing.

## Configuration

**Environment variables.** The entrypoint writes
`/data/config.json` from them on first start. Note the env-built
config carries no `security` block, so it is not by itself a
starting route under a plain `docker run` — see Quick start
for why, and use a mounted config file with the gates stated.

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
| `PIGEON_MAX_JOB_AGE` | no | `3600` (seconds; `max_job_age_sec`) |
| `PIGEON_BASE_DIR` | no | `/data/work` (`base_dir`) |
| `PIGEON_AUTH` | no | `password` (`auth`; `oauth` for the browser sign-in) |

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
docker build -f .github/docker/Dockerfile -t homing-pigeon .
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
