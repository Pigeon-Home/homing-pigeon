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

On a runner whose owner caps the view (`max_result_view`), ask for
the view and declare the questions the result should answer, so the
answers come back even where no output may (PROTOCOL.md sections 9
and 10): `--view attested --query attest:exit_zero --query
attest:no_secrets`. A query is `attest:PREDICATE`, `tail` or `tail:N`,
`grep:PATTERN`, or a JSON object; `--query-budget N` and
`--result-policy JSON|@FILE` (a whole object the flags add to) round it
out. Under `summary` and `attested` the runner refuses `grep` and
`tail`, and the sender says so before it signs.

A job can carry its files in its own signed body and bring files
home (PROTOCOL.md section 6). `--inline-file NAME=PATH` puts a local
file in the job, and `--output NAME` names a file under the job's
workdir to come back in the result. Both are repeatable, with at most
8 outputs, and the bytes come back only under the `full` view.

Three kinds run work the runner owner has written, so a key handed to
an SI can be kept narrow (PROTOCOL.md sections 3.3 to 3.5):

```bash
# a named recipe from the owner's config, with arguments it allows
python3 runner/cloud/send_job.py new --kind recipe --recipe tests \
  --arg test_app.py --secret <the-string>

# check out the owner's repository, apply a diff, run a recipe in it;
# the tree's resulting diff comes home as the output change.diff
python3 runner/cloud/send_job.py new --kind change --repo app \
  --commit main --diff-file fix.diff --recipe tests --secret <the-string>

# stop a job this key sent: killed if running, refused if not yet run
python3 runner/cloud/send_job.py cancel --job-id <id> --secret <the-string>
```

A recipe or change job brings no script, interpreter or environment.
A cancel is answered with a signed `cancel_ack` saying `killed`,
`will_refuse` or `finished`.

Or paste the string to your SI in chat — it composes, signs, and sends
the job message itself, and reads the result message when it arrives. Large files
are uploaded to cloud storage first; the job message carries the URLs.

Verify a result body (results are encrypted by default, so pass
the job id from the result's subject line to decrypt it):

```bash
python3 runner/cloud/send_job.py verify --secret <the-string> --job-id <id> result.txt
```

The `--job-id` can be left off only for a cleartext result.
`--outputs-dir DIR` writes the result's output files there, each one
checked against its SHA-384. `--chain FILE` holds each result against
the ones this sender has already seen. Every result carries
`result_seq` and the digest of the previous result signed under the
same key (PROTOCOL.md section 3.2), so the verifier exits 3 on a gap
(a result that never arrived), a break or a replay. On a runner whose
`pong_platform` is `standard` or `full`, every result also carries
`env_fingerprint`. Two results with the same value ran on the same
environment.
