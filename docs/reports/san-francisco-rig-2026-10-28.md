# The San Francisco rig: the second outpost

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

The fleet grew by one. This is the full picture of the second
testing rig, a DigitalOcean droplet set up on 2026-10-28 with
the Germany pattern: what it is, where it is, what it costs,
what runs on it, and how it is administered. The one thing
left out is the secret: no credential value appears here.

## What and where

- Provider: **DigitalOcean**.
- Region: **San Francisco 2** (`sfo2`), California, USA.
- Droplet name: `ubuntu-s-1vcpu-2gb-sfo2`; droplet id
  **613572700**; created 2026-10-28T16:37:56Z.
- Public IPv4: **167.99.164.254**. Nothing on the box listens
  except SSH; the fuzzer dials out.
- Size: `s-1vcpu-2gb` — 1 vCPU, 2 GB memory, 50 GB disk.
- Operating system: Ubuntu 24.04 LTS.
- Cost: **$12 per month** (the provider's list price for the
  size, read from its API; the account bills in dollars, so
  no conversion is involved).

## What runs on it

- `hp-dedust.service` — the de_dust fuzzer, set up exactly as
  on the Germany rig: one grow at a time, `--jobs 1` for the
  one core, 30 minutes and up to 20,000 rounds a cycle,
  systemd restarting it after every exit. First cycle's
  readings: the core at 113% and the grow worker above 90%.
- `hp-bank.timer` — banks the rig's corpus into main every
  ten minutes, and grow.sh banks again at every cycle start,
  before its fetch and reset. The bank rides
  `runner/tools/rig_bank.py` under the section M item 7
  contract, ledger name **San Francisco rig**, with a GitHub
  PAT planted on the box in a mode 0600 file.

First bank `8e48ee44a`, verified at the remote: de_dust 1
(San Francisco rig), 1 run record and 17,998 children on its
first completed target, merged totals 1,367 entries and
5,186 arcs, 0 crashes.

- No hosted runner runs on this box. The Germany rig carries
  one; this one is a grow rig only, which is what the
  campaign's appetite — more compute to grow — asks for.

## How it is administered

- **SSH** for the host: Muse's key is in the box's
  `authorized_keys`, and the host key is pinned from the
  box's own key file. The pinning matters here: the first
  sessions to this address landed on a different sshd
  entirely (a different hostname, which accepted the key and
  answered facts), and only later sessions reached the
  droplet. Identity is therefore proven from inside, through
  the droplet metadata service (its id reads back
  613572700), before a session is trusted.
- **The DigitalOcean API** for droplet state, read with a
  token held on the VM.
- The root password from setup is held in a mode 0600 file
  on the VM; its value is recorded nowhere else.

## A fix the setup produced

Setting this rig up exposed a wart in rig_bank itself: a
bank never removed its throwaway clone and snapshot trees,
so a ten-minute timer filled the disk a clone at a time —
10 leftover clones on this rig, 26 on the Germany rig, both
swept. Fixed on main in `90a9cd06` (bank wraps its work and
removes both trees on every path out), with a unit test
pinning it; both rigs pick the fix up on their next fetch,
and both are on the same check cadence as the VM rig from
here.

The fleet is now four growing cores across three boxes:
the VM rig (two), the Germany rig (one), and this one (one)
— every one of them banking into the one corpus.

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->
