# Hosting: a runner on a machine the tenant pays for

<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->

A provisioner, not a dispatcher. The hosting code puts a configured
runner into a machine the tenant pays for, keeps it updated, and
never sits in the job path: jobs keep flowing SI to transport to
runner exactly as today. For Windows and macOS nothing runs until a
job exists; a fresh VM boots, drains the tenant's queue once, and
exits. This page is the part the code points at: what exists, where,
and how it fits. Pricing, providers and the business plan live
outside the repository.

The seat that owns this code (stamp `70000a51`) keeps its working
intuitions, each from a failure, in `docs/project/hosting-seat-intuitions.md`.

## What is built

| Phase | What | Where | Proof |
| --- | --- | --- | --- |
| 0 | the `hosted` install profile; the one-blob config (`homing-pigeon-install --config-json`); `--once --drain N --drain-seconds T` | `runner/ops/install.py`, `runner/ops/cli.py`, `runner/runner.py` (`DrainPlan`) | `runner/tests/test_hosting_phase0.py` |
| 1 | the provider interface and adapters (Fly Machines, Hetzner Cloud, DigitalOcean), the machine bootstrap, the inventory, `homing-pigeon-host up / status / redeploy / rotate / destroy` | `runner/hosting/` | `runner/tests/test_hosting_providers.py`, `test_hosting_control_plane.py` against `runner/tests/hosting_fixtures/` |
| 2 | the hosted queue: Worker plus one Durable Object per tenant (token gate, HMAC gate, quota, lease renewal, the dead-letter list), the runner's `queues` transport, `send_job.py --to-queue`, `results` and `dlq`, `homing-pigeon-host queue-tenant` and `up --queue` | `runner/cloud/queues-worker/`, `runner/transport_extensions/queues/`, `runner/cloud/send_job.py`, `runner/hosting/cli.py` | `node --test runner/cloud/queues-worker/test/worker.test.mjs runner/cloud/queues-worker/test/fuzz.test.mjs`, `runner/tests/test_transport_queues.py`, `test_hosting_queue_edges.py`, `test_queue_weather.py` |
| 3 | ephemeral targets on GitHub Actions: `homing-pigeon-host dispatch`, the workflow template, billable minutes | `runner/hosting/github_actions.py`, `runner/hosting/workflows/hp-ephemeral.yml` | `test_hosting_providers.py` (GitHubActionsTest) |
| 4 | metering and prepaid billing: the price table, the ledger, the Stripe webhook that only adds credit | `runner/hosting/billing.py` | `test_hosting_control_plane.py` (Ledger, StripeWebhook) |

Nothing in the runner core, the protocol or the signing changed.

## What has run for real

- **The hosted queue** since 2026-10-27: a one-tenant Worker on the
  operator's own Cloudflare account. Its first ping is
  `docs/reports/queues-2026-10-27.md`; since then it is the control
  plane for the Germany rig (`docs/reports/germany-control-2026-10-27.md`).
- **The `hosted` profile** on that rig, a one-core Hetzner VM: the
  runner polls the queue, answers at the `attested` ceiling, and runs
  jobs confined (a signed job could not write `/etc` or move the root
  password). `docs/reports/germany-rig-2026-10-28.md`.
- **Not yet live:** `homing-pigeon-host` itself. The Germany runner was
  installed by hand, so every provider adapter is still proven against
  recorded exchanges only.

## The pieces, in the order a tenant meets them

**The blob.** One JSON object carries everything a hosted runner
needs that the profile cannot know: `shared_secret`, `runner_id`,
`workspace_root`, the transport block (`transport_queues` or a
mailbox), `owner_instructions`. `homing-pigeon-install --config-json
JSON|@file|env:NAME` writes it before the profile; keys outside
`install.CONFIG_BLOB_KEYS` are refused, so a blob cannot flip a
security mode or widen the result view. The profile owns those.

**The `hosted` profile.** `password-only` (attested results, advisory
judge, the shadow and password redactions) plus
`security.modes.confinement: enforce`, `audience: audit` and
`local_signals: false`. `apply_profile` merges `security.modes` one
mode at a time, so a profile never wipes a mode the owner set.

**The bootstrap.** `runner/hosting/bootstrap.py` renders the same
install three ways: a cloud-init script for plain VMs (Hetzner,
DigitalOcean) that pins `pigeon-home-runner==<version>`, writes the
blob root-only to `/etc/homing-pigeon/blob.json` and runs the
installer with `--profile hosted --no-inference`; an environment
block for image-based machines (Fly); and the three commands an
ephemeral VM runs (install, configure, drain). No provider token is
ever embedded.

**The provisioner.** `homing-pigeon-host up --provider fly
--token-env FLY_API_TOKEN --tenant alice --region iad --version
<release> --blob @blob.json` creates one machine, records it, waits for
`running`, and prints the machine key and the shared secret once.
The token is read from the named environment variable and never
written. `redeploy` creates the replacement first and destroys the
old machine only once the new one is running; `rotate` is a
redeploy with a fresh shared secret, printed once and stored
nowhere. The inventory (`~/.homing-pigeon/hosting.json`, mode 0600)
refuses a second resident machine for a tenant on a provider and
never lets a machine change tenant.

**The hosted queue.** `docs/extend/transports.md`, "Queues". The
Worker is where the per-tenant quota lives, because Cloudflare's
budget alerts are informational only; an exceeded tenant gets 429
and nothing past it is stored or billed.

**Ephemeral targets.** `homing-pigeon-host dispatch --target
macos-ephemeral ...` fires the `hp-ephemeral.yml` workflow with the
ticket, platform label, version and the name of the repository
secret holding the tenant's blob. The run boots a fresh GitHub-hosted
VM, installs the pinned release, drains the queue for the window,
and exits; the dispatcher finds the run by its `run-name`
(`hp <ticket>`), waits for completion, and records the billable
minutes GitHub reports, rounded up the way GitHub bills.

**Billing.** Cents, prepaid only. `PRICES` carries the per-target
unit rates (the values are placeholders until the operator sets
them); `Ledger.can_cover`
refuses a job whose target reserve the balance cannot meet, and a
tenant with an open dispute is frozen. `handle_stripe_event`
verifies `Stripe-Signature` (HMAC-SHA-256, 300 s tolerance), applies
`checkout.session.completed` and `payment_intent.succeeded` as
top-ups, `charge.refunded` as a debit, `charge.dispute.created` as a
freeze, and ignores everything else; a repeated event id is a no-op.
Nothing here charges a card after the fact.

## Decisions settled in the code

1. **Token custody.** The provisioner runs where the token is: the
   tenant (or the operator) runs `homing-pigeon-host` with the
   token in their own environment. The service holds inventory
   state and never a cloud credential.
2. **Isolation unit.** One VM or microVM per tenant, enforced by the
   inventory. Tenants never share a kernel; a shared Docker host is
   out.
3. **Hosted defaults.** The `hosted` profile above. A tenant may
   loosen it in their own config, and the posture card will say so.

## How it ships

As a feature, not a service. `docs/use/own-cloud.md` is the user's
page: one command puts a runner on their own $2 machine, on their own
account, under their own terms. The hosted queue runs on an
operator's own Cloudflare account first. The ephemeral workflow is a
template for a user's own repository. Billing stays dormant until
someone asks to pay.

## Not yet

- A live `up`. Every provider adapter is tested against recorded
  exchanges only; the first live `up` against each provider will
  re-record its fixtures. Hetzner is the natural first, since the
  operator's account already runs a rig there.
- Accounts and a usage page. The inventory and the ledger are JSON
  files for one operator; a database arrives with accounts.
- Heartbeat over the transport. `host status` reads the inventory;
  the runner's posture card is not yet posted on start.
- Per-minute Mac and Windows runners sold as a product (Cirrus
  Runners, Namespace) behind the same `dispatch` interface, if a
  real need appears. GitHub-hosted runners are a user's own call on
  their own account, never resold.
