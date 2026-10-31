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

## The first live check: the clock job

The standard first job to a new runner is the clock check from the
campaign's job set (`runner/tools/soak.py`): the script `date;
date +%s`, sent with no interpreter field at all. The runner runs it
on its platform default, and the result's stdout reads back the
runner's date and epoch. Compare the epoch with your own clock: a
healthy runner agrees within a second or two, plus the mailbox poll
interval (the runner polls every 20 seconds by default, so the result
arrives a little after the send).

Do not name the interpreter by an absolute path. `--interpreter
'["/bin/sh"]'` looks harmless and is not: the runner's sandbox binds
the interpreter's install prefix read-only, so an absolute path makes
it bind `/bin` itself, and on a usr-merged system (Fedora, Ubuntu)
the job dies at once — exit 1 in a few milliseconds, no output at
all. Omit `--interpreter` and let the runner use its default, or use
a bare name (`["bash"]`, `["sh"]`) that resolves under `/usr`. This
was learned live on 31 Oct 2026: the same clock job failed with
`/bin/sh` named and ran clean with the field left out.

## Remote upgrade

A runner can be upgraded remotely by anyone who holds its shared
secret. The procedure is a part of the software suite — an operating
procedure built from the job machinery — and deliberately not a part
of the protocol specification: the wire carries an ordinary signed
job, nothing more. It was first run end to end on 31 Oct 2026,
taking a hosted runner from 3.14.2 to 3.15.0.

It has two halves, because a confined job cannot do the whole thing
and is not allowed to: PROTOCOL.md section 9.4 — no job field can
widen or disable confinement, the sandbox has no network, and the
runner's own tree is outside a job's reach.

**The job half (the secret-holder's side).** Send one signed exec
job that names the release tarball and the release's SHA384SUMS as
URL input files (`--file` in send_job.py). The runner itself
downloads its input files before the job starts, outside the
sandbox — that is how the bytes cross a wall the job cannot. The
tarball is about 91 MB; the runner's download cap is 100 MiB. The
job's script then checks the tarball against the sums inside its own
work directory — the one place a job can write that is still there
after it exits — moves the tarball into a `remote-upgrade` folder in
that work directory, and leaves a `trigger` file beside it:

```sh
set -eu
grep homing-pigeon-linux-x86_64-<version>.tar.gz SHA384SUMS > hp.sum
sha384sum -c hp.sum
mkdir -p remote-upgrade
mv homing-pigeon-linux-x86_64-<version>.tar.gz remote-upgrade/
touch remote-upgrade/trigger
echo remote-upgrade: staged and triggered
```

`set -eu` matters: without it a failed download or a failed digest
check still prints the success line and exits 0, and the sender
reads a staging that never happened. (Learned on the first attempt,
which tried to fetch with curl from inside the sandbox: no network,
nothing staged, and an unconditional "staged" line that said
otherwise.)

**The host half (installed once by the owner).** The kit in
`runner/tools/remote-upgrade/` — the applier
`hp-remote-upgrade-apply` plus its systemd service, path and timer
units — is installed on the box once. The timer runs the applier
every minute (the path unit is a fast path only: a PathExistsGlob
two directories deep did not fire when the trigger appeared). The
applier finds the newest triggered payload, fetches a FRESH
SHA384SUMS for the staged version and checks the tarball against it
a second time, then runs the release's own installer and restarts
the runner. The outcome is written to `outcome.txt` in the payload
folder; the full log is `/root/.homing-pigeon/remote-upgrade-applier.log`.

Four things the first run earned, all handled inside the applier:

- The installer for a box that runs the runner as a system service
  needs `--system`; without it, it installs a user unit and dies at
  `systemctl --user daemon-reload`, which has no session to talk to
  from a service.
- The frozen installer leaks its bundled OpenSSL into every program
  it shells out to, and a current Fedora's `systemctl` and `curl`
  need newer OpenSSL symbols than the bundle carries — they die on
  the mismatch. The applier puts small wrapper scripts for
  `systemctl` and `curl` first on the installer's PATH; each wrapper
  drops the leaked library path and runs the real tool.
- Give the installer a disk-backed TMPDIR (the applier uses
  `/root/.homing-pigeon/tmp`). A small or full /tmp breaks it twice:
  the release extract does not fit, and later the frozen runner
  itself extracts into TMPDIR at every start and crash-loops when
  there is no room. A /tmp full of old rig debris (450 MB of bank
  temp folders) was the last wall on the first run.
- The installer re-stamps the config's profile (it applied
  `password-only` to a `hosted` box). The applier records the profile
  before the install and restores it if it changed; the rest of the
  config the installer leaves alone, as documented. A remote upgrade
  also re-arms the box's panic word; the install log on the box is
  where that is recorded.

One thing the applier leaves in place after the swap: the frozen
runner cannot find this platform's CA bundle by itself and every
transport then fails TLS ("unable to get local issuer
certificate"). The applier writes a systemd drop-in naming the
bundle (`SSL_CERT_FILE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`
on Fedora) and restarts the runner with it.

Proof it worked, in order: the applier's `outcome.txt` names the
new version, `homing-pigeon --version` on the box agrees, both
transports pass clean, and the clock job above, sent again, comes
back signed by the upgraded runner with its clock still true.

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
