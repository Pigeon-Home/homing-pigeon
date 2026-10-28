# The Germany rig: the full hardware picture

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

One big post with everything about the Germany hardware
resource: what it is, where it is, what it costs, what runs on
it, and how it is administered. Rough where a number is a list
price or a reading; exact where it was read off the machine or
the provider's own records. The one thing left out is the
secret: no credential value appears here.

## What and where

- Provider: **Hetzner Cloud**.
- Data center: **Nuremberg, Germany** (location `nbg1`,
  Nuremberg DC Park).
- Server name: `fedora-1gb-nbg1-1`; server id **172889828**;
  created 2026-10-27T20:43:10Z.
- Public IPv4: **178.104.116.44**. Nothing on the box listens
  except SSH; the runner and the fuzzer both dial out.
- Type: **CPX02** — 1 vCPU (AMD EPYC-Genoa), 1 GB memory,
  20 GB disk.
- Cost: **EUR 7.49 per month** list price at `nbg1`, gross,
  read from the provider's API on 2026-10-28. That is the
  whole running cost of the outpost.

## The machine as it reads itself

- Fedora Linux 44, kernel 7.1.10-200.fc44.x86_64.
- 1 CPU. Memory 939,856 kB as the kernel counts it.
- Disk: 19 GB filesystem, 1.8 GB used, 17 GB free.

## What runs on it

Three systemd units do the work:

- `homing-pigeon.service` — the runner, hosted profile, queue
  transport, polling every 20 seconds, answering to key
  `k-7e1ec001`. It is light: it notices the fuzzer's load and
  logs a resource-pressure warning, and it answers jobs
  regardless.
- `hp-dedust.service` — the de_dust fuzzer. One grow at a
  time, `--jobs 1` (the box has the one core), 30 minutes and
  up to 20,000 rounds a cycle, restarted by systemd 10 seconds
  after it exits, including after a reboot. Nice 5, memory
  capped (MemoryHigh 480M, MemoryMax 640M; it reads about
  190 MB in practice). Each cycle starts by fetching main; the
  corpus archive lives in `/var/lib/hp-dedust`, capped at
  8 GB, 356 MB used.
- `hp-bank.timer` — banks the rig's corpus into main every
  ten minutes. grow.sh also banks at every cycle start, before
  its fetch and reset. The box has no cron; systemd is the
  scheduler for everything.

The banks ride `runner/tools/rig_bank.py` under the section M
item 7 contract, with a GitHub PAT planted on the box in a
mode 0600 file, read at use time. Banks 1 through 5 have
landed from the box itself (ebf5f6ec4 through 3ba9491ef);
merged corpus totals at the first bank stood at 1,318
entries and 4,977 arcs, and the rig's corpus carried 123 crash
records the VM rig had never seen, filed as Q106.

## How it is administered

Three planes, all from the VM:

- **SSH** for the host itself. Muse's key is in the box's
  `authorized_keys`. The root password was rotated on
  2026-10-28 to a long random one generated on the box; the
  value is held on the box in a mode 0600 file and recorded
  nowhere else — not in this repo, not in any note.
- **The Hetzner API** for server state and power (reads,
  reboot). Verified live on 2026-10-27 and since.
- **The hosted queue** for runner jobs (ping, probes), the
  plane the first day's control was proven on
  (docs/reports/germany-control-2026-10-27.md). Queue reads
  from the VM truncate intermittently (Q105), so a silence on
  that plane is never read as the runner's state.

Health is checked on the same cadence as the VM rig: fuzzer
at its peg (readings this morning: load 106% / 107% / 101% of
the one core, the grow worker at 98.6%), runner answering,
banks landing. A fall is what gets reported; the rest is
silence.

## What it is for

The grow. The de_dust corpus grows one process per core, so
the campaign's appetite is cores: this box is one core, kept
at saturation around the clock, banking everything it finds
into the shared corpus. Whether this one core — and boxes
like it — could be utilized better toward that goal is asked
openly as Q107.

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->
