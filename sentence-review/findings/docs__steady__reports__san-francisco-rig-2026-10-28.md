# Findings — docs/steady/reports/san-francisco-rig-2026-10-28.md

Source: docs/steady/reports/san-francisco-rig-2026-10-28.md, reviewed at main 720110b0.
Sentence units: 29. Flagged: 2. Categories: pre-release 29, post-release 0.

A rig setup report: the box's identity as a fact list, its first bank, how it is reached, and a defect the setup exposed and fixed. The fact list is a list, and the list is the connection; the prose paragraphs before and after it chain cleanly. 2 units are stamp comments rather than sentences, at the head (unit 1) and the tail (unit 29).

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "The fleet grew by one." | pre-release | flows |  |
| 3 | "This is the full picture of the second…" | pre-release | flows |  |
| 4 | "The one thing left out is the secret:…" | pre-release | flows |  |
| 5 | "Provider: **DigitalOcean**." | pre-release | flows |  |
| 6 | "Region: **San Francisco 2** (`sfo2`), California, USA." | pre-release | flows |  |
| 7 | "Droplet name: `ubuntu-s-1vcpu-2gb-sfo2`; droplet id **613572700**; created 2026-10-28T16:37:56Z." | pre-release | flows |  |
| 8 | "Public IPv4: **167.99.164.254**." | pre-release | flows |  |
| 9 | "Nothing on the box listens except SSH; the…" | pre-release | flows |  |
| 10 | "It is the account's only droplet, confirmed by…" | pre-release | flows |  |
| 11 | "Size: `s-1vcpu-2gb` — 1 vCPU, 2 GB memory,…" | pre-release | flows |  |
| 12 | "Operating system: Ubuntu 24.04 LTS." | pre-release | flows |  |
| 13 | "Cost: **$12 per month** (the provider's list price…" | pre-release | flows |  |
| 14 | "`hp-dedust.service` — the de_dust fuzzer, set up exactly…" | pre-release | flows |  |
| 15 | "First cycle's readings: the core at 113% and…" | pre-release | flows |  |
| 16 | "`hp-bank.timer` — banks the rig's corpus into main…" | pre-release | flows |  |
| 17 | "The bank rides `runner/tools/rig_bank.py` under the section M…" | pre-release | flows |  |
| 18 | "First bank `8e48ee44a`, verified at the remote: de_dust…" | pre-release | flows |  |
| 19 | "No hosted runner runs on this box." | pre-release | flows |  |
| 20 | "The Germany rig carries one; this one is…" | pre-release | flows |  |
| 21 | "**SSH** for the host: Muse's key is in…" | pre-release | flows |  |
| 22 | "The pinning matters here: the first sessions to…" | pre-release | flows |  |
| 23 | "Identity is therefore proven from inside, through the…" | pre-release | flows |  |
| 24 | "**The DigitalOcean API** for droplet state, read with…" | pre-release | flows |  |
| 25 | "The root password from setup is held in…" | pre-release | flows |  |
| 26 | "Setting this rig up exposed a wart in…" | pre-release | flows |  |
| 27 | "Fixed on main in `90a9cd06` (bank wraps its…" | pre-release | flows |  |
| 28 | "The fleet is now four growing cores across…" | pre-release | flows |  |
| 29 | "<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands after the document's last line |
