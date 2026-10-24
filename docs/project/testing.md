# Testing

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
| `--workers COUNT` | Concurrent job executions (default 1) |
| `-v`, `--verbose` | Decision lines: every poll, ingest, wake-gate, judge and board call, with reasons. `-vv` adds more; `--quiet` turns them off. Also a config key: `"verbose": true` |
| `--pdb` | Drop into pdb on unhandled exceptions |
| `--no-send` | Execute, but log results instead of emailing them |
| `--once` | Single poll cycle, then exit |
| `--inspect {board,budget,job,redact,sources}` | Read local Oracle state and exit; no mailbox |
| `--audit-report [--since 14d|48h] [--feature NAME]` | Summarize the security audit log and exit; no mailbox, read-only. `--feature` narrows it to one control's entries |
| `--posture` | Report the runner's security posture (exit 0/1/2) and exit; no mailbox |
| `--run-variant FILE` | Run one locally supplied fuzz variant job from FILE through validation and confined execution, print its outcome as JSON, and exit; no mailbox. The job-fuzz sense's execution door: variants are unsigned local artifacts, admitted only here, never through the job path |
| `--oracle` | Open a loopback chat with the Oracle in your browser. Does not poll mail. Turns are appended to `oracle-chat.jsonl` in the base dir (1 MiB, then one backup). See `docs/CONTRIBUTING.md` (maintainer notes: the `--oracle` flag). |
| `--poll-interval SECONDS`, `--timeout SECONDS`, `--judge MODE`, `--dag-mode MODE`, `--oracle-mode MODE`, … | One-process config overrides: one flag per key, `config.json` untouched, and a flag beats a later config edit. The full map is in `--help` and `docs/oracle/configuring-oracle.md` |

`install.py` accepts the common run flags — `--poll-interval`,
`--timeout`, `--workers`, `--max-output-bytes`, `--dry-run`,
`--verbose` — and bakes them into the installed
service, so the agent on boot runs exactly what you tested:
`python3 runner/ops/install.py --verbose --poll-interval 30`.

```bash
python3 -m unittest discover -s runner/tests -t .
```

The suite drives the real runner code against fake IMAP/SMTP servers:
ping roundtrip, script execution, timeout kill, poison-job rejection,
signature/tamper rejection, any-sender acceptance.

End-to-end without your SI:

1. `python3 runner/cloud/send_job.py new --kind ping --secret <the-string>` → copy the
   subject + body.
2. From any email account, send it to the
   runner mailbox.
3. On the target machine: `python3 runner/runner.py --config config.json --once`.
4. A result message should arrive in the mailbox (or at the job's
   `reply_to` address, if you set one). It arrives as an encrypted
   envelope; decrypt it with `verify --job-id` (above) and the
   result inside says `stdout: "pong"`.
