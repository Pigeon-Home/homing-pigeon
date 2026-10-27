# Run your runner on a $2 machine you own

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

One command puts a Homing Pigeon runner on a small machine in your
own cloud account: Fly.io, Hetzner Cloud or DigitalOcean. Your
account, your bill (a few dollars a month), your terms. The runner
is installed with the `hosted` profile (attested results, advisory
judge, sandbox enforced, no local signals) and polls outward, so
nothing listens. Nobody but you ever holds your cloud token or your
shared secret.

The pieces are `runner/hosting/` and the `homing-pigeon-host`
command; the design is `docs/project/hosting.md`.

## Before you start

- A provider account with an API token: Fly (`fly tokens create
  deploy`), Hetzner (Cloud Console, Security, API tokens, read and
  write) or DigitalOcean (API, Personal access token, write scope).
- The token in an environment variable. It is read from there and
  never written anywhere: `export FLY_API_TOKEN=...`.
- A blob file: the runner's configuration in one JSON object. The
  minimum is a transport. With a mailbox:

  ```json
  {"mailbox_user": "runner@example.test",
   "mailbox_password": "app password",
   "imap_host": "imap.example.test", "smtp_host": "smtp.example.test",
   "workspace_root": "/data/work"}
  ```

  With the hosted queue (`docs/extend/transports.md`, "Queues"):

  ```json
  {"transports": ["queues"],
   "transport_queues": {"url": "https://hp.example.workers.dev/t/you",
                        "token": "the runner token"},
   "workspace_root": "/data/work"}
  ```

  The runner token goes in the blob as `token`. The machine runs
  the runner as a system service, which sets no environment of
  its own, so `token_env` would name a variable that is empty
  there. The blob is written 0600 and already carries the shared
  secret, so the token sits with the other secret it travels with.

  Leave `shared_secret` out and one is generated and printed once.
  A blob may carry only the keys in `install.CONFIG_BLOB_KEYS`:
  secrets, the transport, `runner_id`, `workspace_root`,
  `owner_instructions`, `base_dir`, `poll_interval_sec`,
  `inference`, `oracle_mode` and `pong_platform`. Security modes
  and the result view are the profile's and are refused in a blob.

## The command

```bash
homing-pigeon-host up --provider fly --token-env FLY_API_TOKEN \
    --tenant you --region iad --version <release> --blob @blob.json
```

Fly makes an app named `hp-<tenant>` and one shared-cpu-1x machine
(256 MB, about $2.19 a month) from the release image. Hetzner and
DigitalOcean make one small VM (`cx23`, `s-1vcpu-512mb-10gb`) and
install the pinned release through cloud-init:

```bash
homing-pigeon-host up --provider hetzner --token-env HCLOUD_TOKEN \
    --tenant you --region nbg1 --version <release> --blob @blob.json
homing-pigeon-host up --provider digitalocean --token-env DO_TOKEN \
    --tenant you --region nyc3 --version <release> --blob @blob.json
```

`up` waits until the machine reports running (`--wait 300`, or
`--no-wait`), records it in `~/.homing-pigeon/hosting.json`, and
prints the machine key, its address and the shared secret. Hand the
secret to your SI the way you always have.

With the hosted queue, the SI sends and reads through it:

```bash
export HP_SI_TOKEN=...   # the SI token, never on the command line
python3 runner/cloud/send_job.py new --kind ping --to-queue https://hp.example.workers.dev/t/you
python3 runner/cloud/send_job.py results --from-queue https://hp.example.workers.dev/t/you --ack
```

## Afterwards

```bash
homing-pigeon-host status                              # the inventory
homing-pigeon-host redeploy fly:<id> --version <new> --blob @blob.json --token-env FLY_API_TOKEN
homing-pigeon-host rotate   fly:<id> --blob @blob.json --token-env FLY_API_TOKEN  # new secret, printed once
homing-pigeon-host destroy  fly:<id> --token-env FLY_API_TOKEN
```

`redeploy` creates the replacement first and destroys the old
machine only once the new one is running, so your result stream has
a short gap and not a hole. `rotate` is a redeploy with a fresh
shared secret; the secret is printed once and stored nowhere.

One resident machine per tenant per provider: `up` refuses a second
and tells you to redeploy or destroy instead.

`up` and `redeploy` also take `--size` (the provider's machine size;
the defaults above when left off) and, on Fly, `--image` (a container
image other than the release image). `--inventory PATH` before the
subcommand points every command at an inventory file other than
`~/.homing-pigeon/hosting.json`.

## Ephemeral Mac and Windows, on your own GitHub account

`runner/hosting/workflows/hp-ephemeral.yml` is a template for your
own repository. Read GitHub's Actions usage policy first; whether
your jobs fit it is your call to make for your own account. Put your
blob in a repository secret, copy the workflow in, and:

```bash
homing-pigeon-host dispatch --target macos-ephemeral --tenant you \
    --token-env GITHUB_TOKEN --repo you/your-repo \
    --version <release> --blob-ref HP_BLOB_YOU
```

A fresh runner VM boots, installs the release, drains your queue
for one job or fifteen minutes, and exits. The billable minutes your
account paid are recorded in the inventory.

`--drain N` and `--drain-seconds T` change the one job and fifteen
minutes. `--workflow` names the workflow file if you renamed the copy
(default `hp-ephemeral.yml`), `--ref` the branch it runs from (default
`main`), and `--ticket` sets the run ticket instead of a fresh one; the
workflow's `run-name` must stay `hp <ticket>`, since that is how the
dispatcher finds its run.

## What it costs, and who pays

You do, to your provider, on their terms: about $2 a month for a Fly
machine, about €6 for the smallest Hetzner server, $4 for the
smallest Droplet, and your GitHub Actions minutes for ephemeral
runs. This project runs nothing for you and bills nothing.
