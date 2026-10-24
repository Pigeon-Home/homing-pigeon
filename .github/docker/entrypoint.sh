#!/bin/bash
# Entrypoint: build /data/config.json from environment variables if it
# doesn't already exist (e.g. not mounted in). Then exec the runner.
set -e

CONFIG="${CONFIG_PATH:-/data/config.json}"

if [ ! -f "$CONFIG" ]; then
  if [ -z "$PIGEON_MAILBOX_USER" ] || [ -z "$PIGEON_MAILBOX_PASSWORD" ]; then
    echo "error: $CONFIG not found and PIGEON_MAILBOX_USER / PIGEON_MAILBOX_PASSWORD not set" >&2
    echo "Mount a config.json at /data/config.json or set the env vars. See docs/archive/DOCKER.md." >&2
    exit 1
  fi
  python3 - "$CONFIG" <<'PYEOF'
import json, os, sys
cfg = {
    "mailbox_user": os.environ["PIGEON_MAILBOX_USER"],
    "mailbox_password": os.environ["PIGEON_MAILBOX_PASSWORD"],
    "imap_host": os.environ.get("PIGEON_IMAP_HOST", "imap.gmail.com"),
    "imap_port": int(os.environ.get("PIGEON_IMAP_PORT", "993")),
    "smtp_host": os.environ.get("PIGEON_SMTP_HOST", "smtp.gmail.com"),
    "smtp_port": int(os.environ.get("PIGEON_SMTP_PORT", "587")),
    "base_dir": os.environ.get("PIGEON_BASE_DIR", "/data/work"),
    "poll_interval_sec": int(os.environ.get("PIGEON_POLL_INTERVAL", "20")),
    "max_job_age_sec": int(os.environ.get("PIGEON_MAX_JOB_AGE", "3600")),
    "max_output_bytes": int(os.environ.get("PIGEON_MAX_OUTPUT", "100000")),
    "default_timeout_sec": int(os.environ.get("PIGEON_TIMEOUT", "300")),
    "workers": int(os.environ.get("PIGEON_WORKERS", "1")),
    "auth": os.environ.get("PIGEON_AUTH", "password"),
    "shared_secret": os.environ.get("PIGEON_SHARED_SECRET", ""),
}
with open(sys.argv[1], "w") as fh:
    json.dump(cfg, fh, indent=2)
print(f"wrote {sys.argv[1]} from environment", flush=True)
PYEOF
fi

mkdir -p /data/work
exec python3 /app/runner/runner.py "$@"
