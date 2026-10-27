# Sending a job (any SI)

The runner is SI-agnostic: anything that can send email to the runner's
mailbox and sign the body can drive it — your SI of choice, a cron
script, whatever. The SI needs the `shared_secret` string from your
`config.json` — the random value the installer generated, not the
mailbox password. Then:

```bash
python3 runner/cloud/send_job.py new --kind ping --secret <the-string>
# prints: subject line, blank line, signed body -> send as email to the runner mailbox

python3 runner/cloud/send_job.py new --kind exec --script-file job.sh \
  --interpreter '["bash"]' --file data.csv=https://... --timeout 300 \
  --arg=--verbose --env MODE=ci --secret <the-string>
```

`--arg` and `--env KEY=value` are repeatable. `--script-url URL` sends
the script by link instead (https only; the runner downloads it), and
`--script-sha384 HEX` pins its hash, checked before anything runs.
`--aud RUNNER_ID` sets the job's `runner_id` audience claim, so only
the runner whose config carries that `runner_id` accepts it
(PROTOCOL.md section 3). Two more subcommands
drive the task board (PROTOCOL.md section 13): `send_job.py
task-submit --task-id <id> --priority 1 --secret <the-string>` opens a
task, and `send_job.py task-request --worker-id <name> --secret
<the-string>` pulls one. Both take `--reply-to` so the ack or the
offer lands in your inbox instead of the runner's, and `--cleartext`
with the same meaning as for `new`. Every subcommand takes
`--keyring PATH` to read secrets from a keyring other than the default
(`$HP_KEYRING`, else `~/.homing-pigeon/keyring.json`).

Or paste the string to your SI in chat — it composes, signs, and sends
the job message itself, and reads the result message when it arrives. Large files
are uploaded to cloud storage first; the job message carries the URLs.

Verify a result body (results are encrypted by default, so pass
the job id from the result's subject line to decrypt it):

```bash
python3 runner/cloud/send_job.py verify --secret <the-string> --job-id <id> result.txt
```

The `--job-id` can be left off only for a cleartext result.
