# Findings — docs/steady/reports/rig-2026-10-27.md

Source: docs/steady/reports/rig-2026-10-27.md, reviewed at main a98f1738.
Sentence units: 112. Flagged: 2. Categories: pre-release 112, post-release 0.

A dated rig dossier: who operates the box, a headerless spec table, the grow discipline, and the status vocabulary. The table's empty header row and separator are structure standing where sentences should be; the spec rows flow as entries. All pre-release, a record of its date.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Muse operates this box." | pre-release | flows |  |
| 2 | "Grok set it up and does not." | pre-release | flows |  |
| 3 | "It is a Hetzner Cloud virtual machine in…" | pre-release | flows |  |
| 4 | "The address is not in this file." | pre-release | flows |  |
| 5 | "The root password is not either." | pre-release | flows |  |
| 6 | "The account name on the Worker hostname is…" | pre-release | flows |  |
| 7 | "The conductor gives Muse those out of band." | pre-release | flows |  |
| 8 | "| | |" | pre-release | flagged | An empty table header row ("| | |") — structure with no words at all where a sentence should be |
| 9 | "|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 10 | "| Provider | Hetzner Cloud |" | pre-release | flows |  |
| 11 | "| Location | Nuremberg, `nbg1` |" | pre-release | flows |  |
| 12 | "| Hypervisor | KVM, full virtualization |" | pre-release | flows |  |
| 13 | "| CPU | 1 vCPU, AMD EPYC-Genoa, 1…" | pre-release | flows |  |
| 14 | "| Memory | 917 MiB |" | pre-release | flows |  |
| 15 | "| Disk | 19 GB, 1.3 GB used,…" | pre-release | flows |  |
| 16 | "| OS | Fedora Linux 44, x86_64 |" | pre-release | flows |  |
| 17 | "| Python | 3.14.7 |" | pre-release | flows |  |
| 18 | "| Tree on the box | `main`, fetched…" | pre-release | flows |  |
| 19 | "Two long-running processes share it, and they do…" | pre-release | flows |  |
| 20 | "The hosted runner is `homing-pigeon.service`." | pre-release | flows |  |
| 21 | "It starts `/root/.homing-pigeon/runner.py` with the config beside it." | pre-release | flows |  |
| 22 | "`hosted` profile, poll 20 s, outbound only." | pre-release | flows |  |
| 23 | "Updating the fuzzer does not touch this copy." | pre-release | flows |  |
| 24 | "The campaign process is `hp-dedust.service`." | pre-release | flows |  |
| 25 | "It runs `/opt/hp-rig/grow.sh` with its working directory `/opt/hp-rig/homing-pigeon`,…" | pre-release | flows |  |
| 26 | "`Nice=5`." | pre-release | flows |  |
| 27 | "`MemoryHigh=480M`." | pre-release | flows |  |
| 28 | "`MemoryMax=640M`, so a runaway grow is killed before…" | pre-release | flows |  |
| 29 | "The log is `/var/lib/hp-dedust/grow.log`, cut back at 50…" | pre-release | flows |  |
| 30 | "Each start fetches `origin/main`." | pre-release | flows |  |
| 31 | "If the copy is behind, it resets to…" | pre-release | flows |  |
| 32 | "If the fetch fails, it grows whatever is…" | pre-release | flows |  |
| 33 | "Then one target, `--jobs 1`, for 30 minutes,…" | pre-release | flows |  |
| 34 | "The archive stays in `/var/lib/hp-dedust`, capped at 8…" | pre-release | flows |  |
| 35 | "The box does not push and it does…" | pre-release | flows |  |
| 36 | "`/opt/hp-rig/run` is a one-off test, and its result…" | pre-release | flows |  |
| 37 | "The box has one core, so one target." | pre-release | flows |  |
| 38 | "Do not stop the grow to leave the…" | pre-release | flows |  |
| 39 | "Do not add a second writer." | pre-release | flows |  |
| 40 | "The samples below are from earlier the same…" | pre-release | flows |  |
| 41 | "They are the record of that stretch." | pre-release | flows |  |
| 42 | "They are not the current order." | pre-release | flows |  |
| 43 | "Sampled for 60 seconds while the grow was…" | pre-release | flows |  |
| 44 | "The tool is `runner/tools/rig_resources.py --interval 60`." | pre-release | flows |  |
| 45 | "The target in the standing orders is about…" | pre-release | flows |  |
| 46 | "`over` means the box was above the 90%…" | pre-release | flows |  |
| 47 | "Memory at 48% is the runner, the grow,…" | pre-release | flows |  |
| 48 | "The earlier finished cycle (de_dust 20) measured the…" | pre-release | flows |  |
| 49 | "Seed `3180357378`, started 21:28 UTC, set for 55…" | pre-release | flows |  |
| 50 | "At the sample it had been up about…" | pre-release | flows |  |
| 51 | "No crash on any target that had finished:" | pre-release | flows |  |
| 52 | "| Target | Entries | Arcs |" | pre-release | flows |  |
| 53 | "|---|---|---|" | pre-release | flows |  |
| 54 | "| `local` | 98 → 99 | 121…" | pre-release | flows |  |
| 55 | "| `stash` | 26 → 31 | unchanged…" | pre-release | flows |  |
| 56 | "| `query` | 146 → 149 | unchanged…" | pre-release | flows |  |
| 57 | "| `wire`, `cloud`, `v2`, `crypto`, `mail`, `dtls`, `board`,…" | pre-release | flows |  |
| 58 | "`local` is the one that kept a new…" | pre-release | flows |  |
| 59 | "`stash` and `query` kept entries and no new…" | pre-release | flows |  |
| 60 | "The corpus is banked when the cycle ends,…" | pre-release | flows |  |
| 61 | "The pipe is the Worker's own Durable Object,…" | pre-release | flows |  |
| 62 | "One Worker, one tenant, one SQLite-backed Durable Object…" | pre-release | flows |  |
| 63 | "The migration uses `new_sqlite_classes`." | pre-release | flows |  |
| 64 | "A free-plan account rejects `new_classes` (error 10097), which…" | pre-release | flows |  |
| 65 | "`compatibility_date` is `2026-10-25`." | pre-release | flows |  |
| 66 | "`keep_vars` is on, so a deploy does not…" | pre-release | flows |  |
| 67 | "There is no `TENANTS` KV namespace." | pre-release | flows |  |
| 68 | "The tenant record is the four secrets `TENANT`,…" | pre-release | flows |  |
| 69 | "The slug those secrets name is `homingpigeon02`." | pre-release | flows |  |
| 70 | "The values are not in this file." | pre-release | flows |  |
| 71 | "The runner's copy of the HMAC is the…" | pre-release | flows |  |
| 72 | "`GET /health` returns `200 {"ok": true}` and does…" | pre-release | flows |  |
| 73 | "Every other call is under `/t/<tenant>/`:" | pre-release | flows |  |
| 74 | "| Who | Call | Gate |" | pre-release | flows |  |
| 75 | "|---|---|---|" | pre-release | flows |  |
| 76 | "| SI | `POST /jobs` | SI bearer,…" | pre-release | flows |  |
| 77 | "202, or 200 if that id is already…" | pre-release | flows |  |
| 78 | "| SI | `GET /results`, `POST /results/<id>/ack` |…" | pre-release | flows |  |
| 79 | "| runner | `GET /jobs`, `POST /jobs/<id>/ack`, `POST…" | pre-release | flows |  |
| 80 | "| anyone | a slug that is not…" | pre-release | flows |  |
| 81 | "| anyone | the right slug, wrong or…" | pre-release | flows |  |
| 82 | "The default quota, because no KV record overrides…" | pre-release | flows |  |
| 83 | "Over that the Worker answers 429 with `Retry-After`." | pre-release | flows |  |
| 84 | "A job body over 4 MiB is 413." | pre-release | flows |  |
| 85 | "A bad signature is 403." | pre-release | flows |  |
| 86 | "A lease lasts `LEASE_MS`, default 300 seconds." | pre-release | flows |  |
| 87 | "Five failed attempts and the job moves to…" | pre-release | flows |  |
| 88 | "The runner does not ack a job until…" | pre-release | flows |  |
| 89 | "The runner dials the tenant base, leases, and…" | pre-release | flows |  |
| 90 | "Its systemd unit has no `Environment=` line, so…" | pre-release | flows |  |
| 91 | "The profile is `hosted`: advisory judge, attested results,…" | pre-release | flows |  |
| 92 | "One ping has been through it." | pre-release | flows |  |
| 93 | "The SI posted `67afed13-2d34-4065-8f9e-8571b433d7c3` at 21:03:36 UTC." | pre-release | flows |  |
| 94 | "The Worker returned 202." | pre-release | flows |  |
| 95 | "The runner logged `kind=ping`, `exit=0`, and `delivered (attempt…" | pre-release | flows |  |
| 96 | "The SI read the result back: one encrypted…" | pre-release | flows |  |
| 97 | "The longer record of that exchange is `docs/reports/queues-2026-10-27.md`." | pre-release | flows |  |
| 98 | "At the CPU sample above, the same runner…" | pre-release | flows |  |
| 99 | "Checked again at 23:39 UTC." | pre-release | flows |  |
| 100 | "The machine had been up 2 hours 43…" | pre-release | flows |  |
| 101 | "The runner was still the process that started…" | pre-release | flows |  |
| 102 | "The queues extension was beside it, about 33…" | pre-release | flows |  |
| 103 | "No grow was running." | pre-release | flows |  |
| 104 | "The one that had the core at 100%…" | pre-release | flows |  |
| 105 | "Q99 is the bank contract, and this seat…" | pre-release | flows |  |
| 106 | "Nothing has followed the ping." | pre-release | flows |  |
| 107 | "Empty polls are silent, and the log has…" | pre-release | flows |  |
| 108 | "While the grow was on, the runner logged…" | pre-release | flows |  |
| 109 | "`under-driven` is the idle box." | pre-release | flows |  |
| 110 | "Memory in use was 40%, with about 554…" | pre-release | flows |  |
| 111 | "One warning from the hosted profile, once, at…" | pre-release | flows |  |
| 112 | "The address is still not in this file." | pre-release | flows |  |
