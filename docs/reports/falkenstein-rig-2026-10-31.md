# The Falkenstein rig: a Windows seat for the fleet

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

A new fleet machine, created 31 Oct 2026: what it is, where it
is, what it costs, what it is for, and the order its setup
follows. Facts are read from the provider's API at creation;
costs are converted at the day's rate and named as such.

## What and where

- Provider: **Hetzner Cloud**.
- Data center: **Falkenstein, Germany** (location `fsn1`).
- Server name: `falkenstein-win-1`; server id **173844715**;
  created 2026-10-31.
- Public IPv4: **2.28.30.118**.
- Type: **CX43** — 8 vCPU (shared), 16 GB memory, 160 GB disk.
  The size was chosen for cores and memory, for fuzzing work;
  the disk is larger than the job needs and comes with the type.
- Cost: **$20.63 per month** — the EUR 18.49 list price at
  `fsn1`, gross, read from the provider's API at creation and
  converted at 1.116 dollars to the euro (31 Oct 2026). Billed
  hourly up to the monthly cap, so a machine deleted mid-month
  costs only its hours.
- Bootstrap image: Debian 12, present only so the machine has
  something to boot while Windows is installed. The root
  password was reset through the API at creation and is filed
  with the fleet's other credentials, never in this repository.

## What it is for

The fleet's Windows seat. Two jobs:

1. Prove the Windows half of the suite live — the runner on
   Windows, and the remote-upgrade procedure's Windows applier
   (`runner/tools/remote-upgrade/hp-remote-upgrade-apply.ps1`),
   which is kitted and test-pinned but unproven until it runs
   here.
2. Fuzzing capacity on the platform the other rigs do not cover:
   8 cores and 16 GB against the de_aztec corpus tooling.

The San Francisco droplet retires once this seat is proven,
and its $12 a month folds into this machine's cost. Until then
both run.

## The setup order

A standing order for every new system, first applied here:

1. **The runner is installed first.** Nothing else is set up
   before it.
2. **Every step after that is a job.** Configuration, the
   upgrade key, credentials the machine needs (a GitHub
   credential, for one) — all of it is delivered as signed jobs
   through the protocol, and the job/result record is the
   setup's documentation. Nothing is placed by hand.
3. **This machine stays off email.** No mailbox, no email
   transport. Jobs are submitted locally: an operator connects
   by SSH only to hand the local runner its signed jobs, the
   Pi Light pattern — signing kept, mailbox dropped.

Windows itself is installed from Hetzner's own ISO library
(Windows Server 2022 English and the VirtIO driver disc are
both in it, verified against the API on the day). Windows
Server runs under its evaluation terms until a license key is
added; desktop Windows is not licensed for server hardware
and is not used.

## State at writing

Created and booting on the bootstrap image. Windows install,
then the runner, then the proof jobs, in that order — each
recorded here as it lands.
