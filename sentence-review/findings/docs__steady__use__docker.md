# Findings — docs/steady/use/docker.md

Source: docs/steady/use/docker.md, reviewed at main c25c86d6.
Sentence units: 45. Flagged: 3. Categories: pre-release 45, post-release 0.

A reference page for the Docker image, written in landing-page rhythm: a pointer banner, the 1-command install, dry-run, how a job is sent, the environment table, the mounted-config alternative, updating, and the safety properties. The short units are the page's deliberate staccato and they chain — claim, consequence, reassurance. 3 units are flagged: 2 verbless lines doing a heading's job (units 3 and 15) and the environment table's header row (unit 17); the table's data rows are counted as units and flow as records.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "**Reference page for the Docker image.** It documents…" | pre-release | flows |  |
| 2 | "The install paths that ship today, Docker included,…" | pre-release | flows |  |
| 3 | "The fastest way to run the runner." | pre-release | flagged | Fragment with no verb; it does a heading's job between the banner and the install prose |
| 4 | "No Python to install, no git clone, no…" | pre-release | flows |  |
| 5 | "That's the whole install." | pre-release | flows |  |
| 6 | "The container polls your inbox every 20 seconds…" | pre-release | flows |  |
| 7 | "State (`seen.json`, job workdirs) lives in the `pigeon-data`…" | pre-release | flows |  |
| 8 | "`--dry-run` polls the inbox and logs what it…" | pre-release | flows |  |
| 9 | "Nothing changes." | pre-release | flows |  |
| 10 | "Safe first run." | pre-release | flows |  |
| 11 | "From anywhere — your laptop, your phone, your…" | pre-release | flows |  |
| 12 | "Copy the subject + body it prints, email…" | pre-release | flows |  |
| 13 | "A reply with `stdout: "pong"` arrives within a…" | pre-release | flows |  |
| 14 | "Or skip the script entirely — paste the…" | pre-release | flows |  |
| 15 | "**Environment variables** (recommended)." | pre-release | flagged | A bolded label, not a sentence; it names the table that follows |
| 16 | "The entrypoint writes `/data/config.json` from them on first…" | pre-release | flows |  |
| 17 | "Variable \| Required \| Default" | pre-release | flagged | Table header row, structure rather than a sentence |
| 18 | "`PIGEON_MAILBOX_USER` \| yes \| —" | pre-release | flows |  |
| 19 | "`PIGEON_MAILBOX_PASSWORD` \| yes \| —" | pre-release | flows |  |
| 20 | "`PIGEON_SHARED_SECRET` \| yes \| —" | pre-release | flows |  |
| 21 | "`PIGEON_IMAP_HOST` \| no \| `imap.gmail.com`" | pre-release | flows |  |
| 22 | "`PIGEON_IMAP_PORT` \| no \| `993`" | pre-release | flows |  |
| 23 | "`PIGEON_SMTP_HOST` \| no \| `smtp.gmail.com`" | pre-release | flows |  |
| 24 | "`PIGEON_SMTP_PORT` \| no \| `587`" | pre-release | flows |  |
| 25 | "`PIGEON_POLL_INTERVAL` \| no \| `20`" | pre-release | flows |  |
| 26 | "`PIGEON_WORKERS` \| no \| `1`" | pre-release | flows |  |
| 27 | "`PIGEON_TIMEOUT` \| no \| `300`" | pre-release | flows |  |
| 28 | "`PIGEON_MAX_OUTPUT` \| no \| `100000`" | pre-release | flows |  |
| 29 | "`PIGEON_MAX_JOB_AGE` \| no \| `3600` (seconds; `max_job_age_sec`)" | pre-release | flows |  |
| 30 | "`PIGEON_BASE_DIR` \| no \| `/data/work` (`base_dir`)" | pre-release | flows |  |
| 31 | "`PIGEON_AUTH` \| no \| `password` (`auth`; `oauth` for…" | pre-release | flows |  |
| 32 | "The HMAC shared secret is a separate `shared_secret`…" | pre-release | flows |  |
| 33 | "Throwaway account, nothing personal — see SECURITY.md." | pre-release | flows |  |
| 34 | "**Mounted config file.** If you already have a…" | pre-release | flows |  |
| 35 | "Env vars are ignored when the file exists:" | pre-release | flows |  |
| 36 | "Your `pigeon-data` volume survives — no jobs re-run…" | pre-release | flows |  |
| 37 | "Don't want the published image?" | pre-release | flows |  |
| 38 | "Build from source:" | pre-release | flows |  |
| 39 | "Then replace `ghcr.io/pigeon-home/homing-pigeon:latest` with `homing-pigeon` in any command…" | pre-release | flows |  |
| 40 | "Runs as a **non-root** user inside the container." | pre-release | flows |  |
| 41 | "Never needs root." | pre-release | flows |  |
| 42 | "**No inbound network.** The runner polls IMAP outbound…" | pre-release | flows |  |
| 43 | "No ports exposed, no ports published, nothing listens." | pre-release | flows |  |
| 44 | "Published images are signed with Sigstore." | pre-release | flows |  |
| 45 | "Verify:" | pre-release | flows |  |
