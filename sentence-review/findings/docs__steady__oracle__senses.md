# Findings — docs/steady/oracle/senses.md

Source: docs/steady/oracle/senses.md, reviewed at main bc86d6f0.
Sentence units: 142. Flagged: 4. Categories: pre-release 110, post-release 32.

The senses catalog and framework: what a sense is, the 3 advanced senses with their collectors and shipped adapters, the installer rules, then the designs that are not built — the parked AV detections sense (units 33 to 42), the firewall sense's future rule-change collector (units 70 to 80) and cage verification (units 81 to 86), and the future hygiene senses in the boring-tier list (patch_level, persistence, disk_encryption). Those unbuilt designs are the document's post-release blocks; each is fenced by its own 'not built' or 'future' marker, and the shipped framework around them — config, signing, ingest, the query — is pre-release. The firewall spec's step numerals stand as their own units (60, 70, 81, 87), the heading sentence completing in the unit after, and are flagged on that ground.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "Senses are inbound signal extensions: external daemons (a…" | pre-release | flows |  |
| 2 | "The Oracle never trusts an alert on its…" | pre-release | flows |  |
| 3 | "Ingest is advisory: filing an alert executes nothing,…" | pre-release | flows |  |
| 4 | "What consumes the filed alerts can act on…" | pre-release | flows |  |
| 5 | "The behavioral models for these tools do not…" | pre-release | flows |  |
| 6 | "There are no good heuristics for "what does…" | pre-release | flows |  |
| 7 | "So everything is adjustable from the beginning:" | pre-release | flows |  |
| 8 | "each sense has an **enable flag**," | pre-release | flows |  |
| 9 | "each sense has a **weight** — how much…" | pre-release | flows |  |
| 10 | "each sense has a **profile**: a free-form bag…" | pre-release | flows |  |
| 11 | "The runner enforces three known knobs today; unknown…" | pre-release | flows |  |
| 12 | "`host_ids` — host intrusion detection (file integrity, suspicious…" | pre-release | flows |  |
| 13 | "Collector: Falco, Wazuh agent, AIDE." | pre-release | flows |  |
| 14 | "Shipped adapters: `falco-feed` (Falco's JSON alert file), `aide-feed`…" | pre-release | flows |  |
| 15 | "`netmon` — network monitoring (flows, DNS, anomalous outbound)." | pre-release | flows |  |
| 16 | "Collector: Suricata, Zeek, softflowd." | pre-release | flows |  |
| 17 | "Shipped adapters: `suricata-feed` (Suricata's eve.json), `zeek-feed` (Zeek's conn.log…" | pre-release | flows |  |
| 18 | "`sysmon` — system internals telemetry (process tree, CPU/memory,…" | pre-release | flows |  |
| 19 | "This is the signal that lets the Oracle…" | pre-release | flows |  |
| 20 | "Collector: osquery (cross-platform), Sysmon (Windows), `/proc` + `lsof`/`ss`…" | pre-release | flows |  |
| 21 | "Shipped adapters: `osquery-feed` (osqueryd's results log for the…" | pre-release | flows |  |
| 22 | "The adapters above are examples in `runner/extensions/`; the…" | pre-release | flows |  |
| 23 | "`install.py --collector NAME` (repeatable) installs one where the…" | pre-release | flows |  |
| 24 | "A fresh install sets up **osquery** by default…" | pre-release | flows |  |
| 25 | "Pi Light installs no collector by default; `--collector`…" | pre-release | flows |  |
| 26 | "The Wazuh agent installs only when a manager…" | pre-release | flows |  |
| 27 | "Falco and Sysmon carry a capability warning the…" | pre-release | flows |  |
| 28 | "The installer's `--check` therefore capability-probes every collector it…" | pre-release | flows |  |
| 29 | "Absence is a legitimate state, not a fault;…" | pre-release | flows |  |
| 30 | "The three above are the advanced tier." | pre-release | flows |  |
| 31 | "The boring tier matters just as much and…" | pre-release | flows |  |
| 32 | "Each of these is a sense in the…" | pre-release | flows |  |
| 33 | "**Not built — parked.** No `av` collector ships…" | post-release | flows |  |
| 34 | "What ships is the posture stat — `av_posture`,…" | post-release | flows |  |
| 35 | "This section is the design for the detections…" | post-release | flows |  |
| 36 | "The sense does not replace the antivirus; it…" | post-release | flows |  |
| 37 | "**Windows:** Microsoft Defender." | post-release | flows |  |
| 38 | "Collector reads detections via `MpCmdRun -Scan` result parsing…" | post-release | flows |  |
| 39 | "**Linux:** ClamAV (`clamdscan`) on a schedule, plus the…" | post-release | flows |  |
| 40 | "Sysmon for Linux (measured current: 1.5.3) feeds the…" | post-release | flows |  |
| 41 | "**macOS:** XProtect/MRT run automatically with no stable API,…" | post-release | flows |  |
| 42 | "Profile knobs: `severity_floor` (Defender "severe" maps to critical)…" | post-release | flows |  |
| 43 | "(Scheduled on-demand sweeps are not wired: there is…" | pre-release | flows |  |
| 44 | "One sense per check, all cheap, all per-platform." | pre-release | flows |  |
| 45 | "They answer the question "is the boring stuff…" | pre-release | flows |  |
| 46 | "`av_posture` — is real-time protection enabled, and are…" | pre-release | flows |  |
| 47 | "Shipped as one stat, not a scan." | pre-release | flows |  |
| 48 | "Linux reads the mtime of the ClamAV daily…" | pre-release | flows |  |
| 49 | "Windows asks `sc query WinDefend`." | pre-release | flows |  |
| 50 | "macOS has no stable XProtect read, so the…" | pre-release | flows |  |
| 51 | "A stale or stopped tool is labeled T1562.001." | pre-release | flows |  |
| 52 | "The line is diffed, and a flip is…" | pre-release | flows |  |
| 53 | "Unreadable does not overwrite the last good reading." | pre-release | flows |  |
| 54 | "`firewall` — host firewall state per platform (Windows…" | pre-release | flows |  |
| 55 | "Reports profile changes, not every dropped packet." | pre-release | flows |  |
| 56 | "Full spec below; the cage-verification job in that…" | pre-release | flows |  |
| 57 | "The hygiene list above treats this sense as…" | pre-release | flows |  |
| 58 | "The full spec has three jobs, in increasing…" | pre-release | flows |  |
| 59 | "The first two are sensing; the third is…" | pre-release | flows |  |
| 60 | "**1." | pre-release | flagged | A bare step numeral standing as its own unit; the step's heading sentence completes in the next unit |
| 61 | "Posture: is the firewall on, and did that…" | pre-release | flows |  |
| 62 | "Shipped, as one line in the Oracle context,…" | pre-release | flows |  |
| 63 | "Windows reads `netsh advfirewall show allprofiles` (profile state…" | pre-release | flows |  |
| 64 | "Linux reads `ufw status` when ufw is installed,…" | pre-release | flows |  |
| 65 | "macOS reads `socketfilterfw --getglobalstate` and does not call…" | pre-release | flows |  |
| 66 | "A profile or policy that is off is…" | pre-release | flows |  |
| 67 | "The line is diffed against the previous reading,…" | pre-release | flows |  |
| 68 | "Unreadable stays unreadable and does not overwrite the…" | pre-release | flows |  |
| 69 | "The rule-hash diff and the cage check below…" | pre-release | flows |  |
| 70 | "**1b." | pre-release | flagged | A bare step numeral standing as its own unit; the step's heading sentence completes in the next unit |
| 71 | "Rule changes (future).** Listed in docs/future.md." | post-release | flows |  |
| 72 | "This is the ruleset hash, not the posture…" | post-release | flows |  |
| 73 | "The collector would snapshot the rule set and…" | post-release | flows |  |
| 74 | "**Windows:** `Get-NetFirewallProfile` (Domain/Private/Public enabled flags) plus a hash…" | post-release | flows |  |
| 75 | "A profile flip is medium; a new inbound…" | post-release | flows |  |
| 76 | "**Linux:** `nft list ruleset` (or `iptables-save` / `ufw…" | post-release | flows |  |
| 77 | "Read-only; runs with whatever privilege the ruleset needs." | post-release | flows |  |
| 78 | "**macOS:** `pfctl -sr` plus the Application Firewall state…" | post-release | flows |  |
| 79 | "Profile knobs (future, arriving with the collector): `watch_rules`…" | post-release | flows |  |
| 80 | "None of these names exists in the profile…" | post-release | flows |  |
| 81 | "**2." | pre-release | flagged | A bare step numeral standing as its own unit; the step's heading sentence completes in the next unit |
| 82 | "Cage verification: did the job's network cage hold?**…" | post-release | flows |  |
| 83 | "The runner can already cage a job's network…" | post-release | flows |  |
| 84 | "The firewall sense is how the Oracle *would…" | post-release | flows |  |
| 85 | "On Windows the cage is per-user WFP rules…" | post-release | flows |  |
| 86 | "This keeps the architecture's split clean: the *cage*…" | post-release | flows |  |
| 87 | "**3." | pre-release | flagged | A bare step numeral standing as its own unit; the step's heading sentence completes in the next unit |
| 88 | "Egress policy (opt-in enforcement, not a sense).** Per-job-identity…" | post-release | flows |  |
| 89 | "This is deliberately not part of the sense." | pre-release | flows |  |
| 90 | "Senses never enforce." | pre-release | flows |  |
| 91 | "The design lives in `docs/use/networking.md`." | pre-release | flows |  |
| 92 | "`patch_level` — *(future sense, listed in docs/future.md)* pending…" | post-release | flows |  |
| 93 | "Info-level; the Oracle correlates "unpatched for 90 days"…" | post-release | flows |  |
| 94 | "`listening_sockets` — *(ships as the `port_watch` sense extension,…" | pre-release | flows |  |
| 95 | "A new listener is medium by default; the…" | pre-release | flows |  |
| 96 | "`persistence` — *(not built)* autorun/persistence locations: Windows autoruns…" | post-release | flows |  |
| 97 | "A new entry outside a job window is…" | post-release | flows |  |
| 98 | "`disk_encryption` — *(future sense, listed in docs/future.md)* BitLocker…" | post-release | flows |  |
| 99 | "Info-level posture, mostly for the "is this box…" | post-release | flows |  |
| 100 | "None of these remediate." | pre-release | flows |  |
| 101 | "They file alerts; the Oracle fuses them with…" | pre-release | flows |  |
| 102 | "A disabled Defender *during* a job run is…" | pre-release | flows |  |
| 103 | "`enabled` (bool, default false): the sense files alerts…" | pre-release | flows |  |
| 104 | "`key_id` (string, required): the restricted key the daemon…" | pre-release | flows |  |
| 105 | "Two senses may not share a key —…" | pre-release | flows |  |
| 106 | "`weight` (number >= 0, default 1.0): the Oracle's…" | pre-release | flows |  |
| 107 | "Turn a noisy sensor down, a trusted one…" | pre-release | flows |  |
| 108 | "`profile` (object): tunables." | pre-release | flows |  |
| 109 | "Known knobs:" | pre-release | flows |  |
| 110 | "`severity_floor`: drop alerts below this severity at ingest." | pre-release | flows |  |
| 111 | "One of critical/high/medium/low/info." | pre-release | flows |  |
| 112 | "Default info (keep all)." | pre-release | flows |  |
| 113 | "`cooldown_sec`: drop repeats of the same sensor+title within…" | pre-release | flows |  |
| 114 | "Default 0 (no dedup)." | pre-release | flows |  |
| 115 | "`max_per_hour`: sliding-window cap per sense; over-cap alerts are…" | pre-release | flows |  |
| 116 | "Default 0 (unlimited)." | pre-release | flows |  |
| 117 | "Pair each sense key with a least-privilege entry…" | pre-release | flows |  |
| 118 | "Keys without a policy entry are unrestricted (unless…" | pre-release | flows |  |
| 119 | "Alerts are signed jobs, same envelope as everything…" | pre-release | flows |  |
| 120 | "The daemon signs with its restricted key and…" | pre-release | flows |  |
| 121 | "`severity`: critical/high/medium/low/info." | pre-release | flows |  |
| 122 | "Missing defaults to info." | pre-release | flows |  |
| 123 | "`title`: required, non-empty." | pre-release | flows |  |
| 124 | "Used for cooldown dedup." | pre-release | flows |  |
| 125 | "`detail`: optional object." | pre-release | flows |  |
| 126 | "String values are redacted with the Oracle's standard…" | pre-release | flows |  |
| 127 | "`job_id_hint`: if the sensor knows which runner job…" | pre-release | flows |  |
| 128 | "In `handle_mail`, after the signature and key-policy checks,…" | pre-release | flows |  |
| 129 | "shape validation (rejects are poison: marked seen, logged)," | pre-release | flows |  |
| 130 | "the sensor must be configured and enabled," | pre-release | flows |  |
| 131 | "the signing key must be bound to that…" | pre-release | flows |  |
| 132 | "profile gates (severity floor, cooldown, hourly cap) —…" | pre-release | flows |  |
| 133 | "the alert is appended to `senses.jsonl` in the…" | pre-release | flows |  |
| 134 | "No result message is sent." | pre-release | flows |  |
| 135 | "Dry-run mode describes the alert and stores nothing." | pre-release | flows |  |
| 136 | "A `sensor` given reads that sensor alone, and…" | pre-release | flows |  |
| 137 | "Returns matching alerts ranked by **score = weight…" | pre-release | flows |  |
| 138 | "Titles and string details are redacted before the…" | pre-release | flows |  |
| 139 | "This is the correlation primitive: "what did the…" | pre-release | flows |  |
| 140 | "Start wide (floor info, no cooldown, generous caps,…" | pre-release | flows |  |
| 141 | "The weight is the fast knob: a chatty-but-useful…" | pre-release | flows |  |
| 142 | "The profile gates are the slow knobs: they…" | pre-release | flows |  |
