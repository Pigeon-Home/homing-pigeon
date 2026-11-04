# Findings — docs/steady/reports/germany-rig-2026-10-28.md

Source: docs/steady/reports/germany-rig-2026-10-28.md, reviewed at main 670cf354.
Sentence units: 41. Flagged: 1. Categories: pre-release 41, post-release 0.

A dated rig dossier written in spec lines: provider, address, cost, shape, planes of access, and the reporting rule. The spec-line register is the document's form; 1 shard stands out even by that standard. All pre-release, a record of its date.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->" | pre-release | flows |  |
| 2 | "One big post with everything about the Germany…" | pre-release | flows |  |
| 3 | "Rough where a number is a list price…" | pre-release | flows |  |
| 4 | "The one thing left out is the secret:…" | pre-release | flows |  |
| 5 | "Provider: **Hetzner Cloud**." | pre-release | flows |  |
| 6 | "Data center: **Nuremberg, Germany** (location `nbg1`, Nuremberg DC…" | pre-release | flows |  |
| 7 | "Server name: `fedora-1gb-nbg1-1`; server id **172889828**; created 2026-10-27T20:43:10Z." | pre-release | flows |  |
| 8 | "Public IPv4: **178.104.116.44**." | pre-release | flows |  |
| 9 | "Nothing on the box listens except SSH; the…" | pre-release | flows |  |
| 10 | "Type: **CPX02** — 1 vCPU (AMD EPYC-Genoa), 1…" | pre-release | flows |  |
| 11 | "Cost: **about $8.34 per month** — the EUR…" | pre-release | flows |  |
| 12 | "That is the whole running cost of the…" | pre-release | flows |  |
| 13 | "Fedora Linux 44, kernel 7.1.10-200.fc44.x86_64." | pre-release | flows |  |
| 14 | "1 CPU." | pre-release | flagged | A spec shard ("1 CPU.") standing entirely alone — the shape it names is never carried into a sentence |
| 15 | "Memory 939,856 kB as the kernel counts it." | pre-release | flows |  |
| 16 | "Disk: 19 GB filesystem, 1.8 GB used, 17…" | pre-release | flows |  |
| 17 | "Three systemd units do the work:" | pre-release | flows |  |
| 18 | "`homing-pigeon.service` — the runner, hosted profile, queue transport,…" | pre-release | flows |  |
| 19 | "It is light: it notices the fuzzer's load…" | pre-release | flows |  |
| 20 | "`hp-dedust.service` — the de_dust fuzzer." | pre-release | flows |  |
| 21 | "One grow at a time, `--jobs 1` (the…" | pre-release | flows |  |
| 22 | "Nice 5, memory capped (MemoryHigh 480M, MemoryMax 640M;…" | pre-release | flows |  |
| 23 | "Each cycle starts by fetching main; the corpus…" | pre-release | flows |  |
| 24 | "`hp-bank.timer` — banks the rig's corpus into main…" | pre-release | flows |  |
| 25 | "The box has no cron; systemd is the…" | pre-release | flows |  |
| 26 | "The banks ride `runner/tools/rig_bank.py` under the section M…" | pre-release | flows |  |
| 27 | "Banks 1 through 5 have landed from the…" | pre-release | flows |  |
| 28 | "Three planes, all from the VM:" | pre-release | flows |  |
| 29 | "**SSH** for the host itself." | pre-release | flows |  |
| 30 | "Muse's key is in the box's `authorized_keys`." | pre-release | flows |  |
| 31 | "The root password was rotated on 2026-10-28 to…" | pre-release | flows |  |
| 32 | "**The Hetzner API** for server state and power…" | pre-release | flows |  |
| 33 | "Verified live on 2026-10-27 and since." | pre-release | flows |  |
| 34 | "**The hosted queue** for runner jobs (ping, probes),…" | pre-release | flows |  |
| 35 | "Queue reads from the VM truncate intermittently (Q105),…" | pre-release | flows |  |
| 36 | "Health is checked on the same cadence as…" | pre-release | flows |  |
| 37 | "A fall is what gets reported; the rest…" | pre-release | flows |  |
| 38 | "The grow." | pre-release | flows |  |
| 39 | "The de_dust corpus grows one process per core,…" | pre-release | flows |  |
| 40 | "Whether this one core — and boxes like…" | pre-release | flows |  |
| 41 | "<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->" | pre-release | flows |  |
