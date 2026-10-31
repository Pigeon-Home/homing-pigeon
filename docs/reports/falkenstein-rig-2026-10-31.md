# The Germany rig: a Windows seat for the fleet

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

A new fleet machine, created 31 Oct 2026: what it is, where it
is, what it costs, what it is for, and the order its setup
follows. Facts are read from the provider's API at creation;
costs are converted at the day's rate and named as such. This
report is kept current as the seat is proven; each state below
was verified on the machine itself at the time named.

## What and where

- Provider: **Hetzner Cloud**.
- Data center: **Falkenstein, Germany** (location `fsn1`).
  The machine is referred to as **the Germany rig**.
- Server name: `falkenstein-win-1`; server id **173851141**;
  created 2026-10-31. (A first machine of the same name and
  address, id 173844715, was created and deleted the same day
  during a location comparison — Singapore and Tokyo could not
  offer the shape at the price, Helsinki had no capacity —
  and the replacement was placed in Falkenstein with the same
  public address reissued.)
- Public IPv4: **2.28.30.118**.
- Type: **CX43** — 8 vCPU (shared), 16 GB memory, 160 GB disk.
  The size was chosen for cores and memory, for fuzzing work;
  the disk is larger than the job needs and comes with the type.
- Cost: **$20.63 per month** — the EUR 18.49 list price at
  `fsn1`, gross, read from the provider's API at creation and
  converted at 1.116 dollars to the euro (31 Oct 2026). Billed
  hourly up to the monthly cap, so a machine deleted mid-month
  costs only its hours.
- Bootstrap image: Debian 12, present only so the machine had
  something to boot while Windows was installed; since removed
  by the Windows install. The bootstrap root password was reset
  through the API at creation and is filed with the fleet's
  other credentials, never in this repository.

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

**Assume a bare machine.** No procedure for this machine may
assume a tool is installed — not git, not Python, not anything
beyond Windows itself and the runner. Every step installs what
it needs, in the open, as part of the step. A procedure that
works only because something happened to be on the machine
already is a broken procedure; the failure will arrive on the
next fresh machine, in front of a different operator. The
first repository job below follows the rule: it carries its
own portable git.

## State at writing (31-Oct-2026 4:35pm-PST/PDT)

- **Windows installed.** Windows Server 2022 Standard (Server
  Core), computer name WIN-LONG208OI02, installed through the
  provider's web console with the VirtIO storage and network
  drivers loaded at setup. The install ISO has been detached,
  so a reboot cannot re-enter the installer.
- **Access is SSH.** The OpenSSH server is installed, set to
  start automatically, and takes the fleet's key as
  Administrator. PowerShell remoting (WinRM) does not work
  from the operating VM — direct connections are dropped and
  the VM's egress proxy rejects the request shape — so SSH is
  the management channel. The web console's typing drops shift
  states intermittently, so secrets are never typed into it
  directly; the Administrator password was set from character
  codes instead, and the filed value is verified working.
- **The runner is installed and running.** Homing Pigeon
  3.15.0 at `C:\homing-pigeon`, Pi Light profile (deterministic
  Oracle, no local model), as a boot-start Scheduled Task
  running as SYSTEM. The installer's doctor check passes:
  18 passed, 0 warnings, 0 failed.
- **Off email, as ordered.** The runner's transports are
  `["file"]`: signed jobs are handed to
  `C:\homing-pigeon\state\transport-file\inbox` and results
  land in the matching outbox. The install's default email
  transport was replaced before the runner's first poll. The
  machine's shared secret and full runner configuration are
  filed with the fleet's credentials on the operating VM,
  never in this repository.
- **First job proven end to end.** A signed clock job
  (e5e26777-1fd8-4e72-8b61-c596dd996af1) was delivered through
  the file transport, ran under PowerShell (the platform
  default interpreter), and returned exit 0 with a true clock —
  the machine's epoch read matched the operating VM's within
  the fetch time between the two reads. The result's signature
  verified on the operating VM. The local submission route of
  the setup order is therefore proven on Windows.
- **A bug found on the way, recorded here.** The runner's
  startup gate asks for mailbox authentication without
  checking whether the email transport is enabled
  (`runner/ops/setup.py`, `needs_setup`, reached from
  `runner/ops/main.py`). On this email-free machine the
  service waited forever at an interactive "Run setup now?"
  prompt: no log written, no channels created, no graceful
  stop. The machine carries an inert placeholder mailbox user
  and password in its configuration as a workaround — the
  email transport is not enabled, so the values are never
  used. The fix (the gate skips when email is not among the
  enabled transports) lands on main with its regression test;
  the placeholder comes out when a build carrying the fix is
  installed here.

## What remains

1. Python on the machine, delivered as a job — the fuzzing
   tooling and local submission helpers run on it.
2. The Windows remote-upgrade applier, proven live with a
   same-version reinstall under the upgrade key.
3. Fuzzing slices on the 8 cores.
4. San Francisco's retirement, now that the seat is proven.
