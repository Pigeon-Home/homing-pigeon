# Oracle senses

Senses are inbound signal extensions: external daemons (a host
intrusion-detection tool, a network monitor, later anything else)
that file signed alerts with the Oracle. The Oracle never trusts an
alert on its own; it fuses the alert with what it already knows —
which job was running, what the job was supposed to do, whether it
stayed confined — and that fusion is what makes the signal useful.

Ingest is advisory: filing an alert executes nothing, pages
no one, and blocks nothing by itself. What consumes the
filed alerts can act on them — the DRI evaluation pages the
owner when its triggers trip on the fused score
(`docs/dri-playbook.md`), and remediation counts some
alerts among the divergences it watches a running job
against (`docs/remediation-design.md`).

## Why this shape

The behavioral models for these tools do not exist yet. There are
no good heuristics for "what does suspicious look like" from a
host IDS watching agent jobs, versus a netmon watching the box's
traffic. So everything is adjustable from the beginning:

- each sense has an **enable flag**,
- each sense has a **weight** — how much the Oracle weighs its alerts,
- each sense has a **profile**: a free-form bag of tunables. The
  runner enforces three known knobs today; unknown keys are accepted
  and carried through, so tomorrow's heuristics get tuned in config,
  not in code.

## The three senses

- `host_ids` — host intrusion detection (file integrity, suspicious
  syscalls, privilege changes). Collector: Falco, Wazuh agent, AIDE.
  Shipped adapters: `falco-feed` (Falco's JSON alert file),
  `aide-feed` (AIDE's check reports), and `wazuh-feed` (a Wazuh
  `alerts.json` where one exists on the box — see the Wazuh note
  under Collector support below).
- `netmon` — network monitoring (flows, DNS, anomalous outbound).
  Collector: Suricata, Zeek, softflowd. Shipped adapters:
  `suricata-feed` (Suricata's eve.json), `zeek-feed` (Zeek's
  conn.log and dns.log), and `softflowd-feed` (softflowd emits
  NetFlow/IPFIX over UDP with no file, so the adapter is the
  listener: it collects the flow records itself).
- `sysmon` — system internals telemetry (process tree, CPU/memory,
  open sockets/handles, file-touch events). This is the signal that
  lets the Oracle spot *behavioral* anomalies: a new unknown process
  plus an anomalous outbound connection plus file touches outside
  the workspace, all inside one time window, is one incident, not
  three alerts. Collector: osquery (cross-platform), Sysmon
  (Windows), `/proc` + `lsof`/`ss` scraping (Linux). Shipped
  adapters: `osquery-feed` (osqueryd's results log for the light
  query pack: processes, users, listening ports) and
  `sysmon-feed` (Sysmon process-create events, Linux and Windows
  shapes).

## Collector support: installing the daemons behind the senses

The adapters above are examples in `examples/extensions/`; the
collectors themselves are third-party daemons the installer can
set up. `install.py --collector NAME` (repeatable) installs one
where the platform has an official channel, and reports the
outcome per collector; `--no-collector` opts out. A fresh install
sets up **osquery** by default on Linux, macOS, and Windows —
measured at ~27 MB resident and ~0.1% CPU idle, the lightest
host-telemetry daemon of the set — with a light query pack and,
on Linux, the systemd unit the package does not ship. Pi Light
installs no collector by default; `--collector` stays available
there explicitly. The Wazuh agent installs only when a manager
address is given (`--wazuh-manager`): Wazuh alerts live on the
manager, a standalone agent produces no on-box artifact, and
`wazuh-feed` consumes an `alerts.json` only where a manager
export or API pull lands one on the box.

Falco and Sysmon carry a capability warning the others do not:
both can install successfully and then silently not function
where the kernel denies BPF or the driver cannot load. The
installer's `--check` therefore capability-probes every
collector it knows and reports one row each — **WORKS**,
**INSTALLED-BUT-CANNOT-RUN** (with the reason: BPF denied, no
manager configured, daemon down), or **ABSENT**. Absence is a
legitimate state, not a fault; installed-but-cannot-run is the
one to act on.

## More senses: antivirus and basic hygiene

The three above are the advanced tier. The boring tier matters just
as much and is easier to overlook precisely because it is boring.
Each of these is a sense in the same framework — enable flag,
weight, profile, restricted key — so the Oracle can be told to
care about them per platform.

### `av` — antivirus / anti-malware detections

**Not built — parked.** No `av` collector ships today: there is
no adapter under `examples/extensions/`, and nothing files the
platform AV's detections as `sensor_alert`s. What ships is the
posture stat — `av_posture`, in the basic hygiene senses below.
This section is the design for the detections sense, kept for
when it is picked up.

The sense does not replace the antivirus; it is a collector that
files what the platform's AV already found as `sensor_alert`s.

- **Windows:** Microsoft Defender. Collector reads detections via
  `MpCmdRun -Scan` result parsing or the
  `MSFT_MpThreatDetection` WMI class; AMSI-backed script-block
  logging (PowerShell Operational log, event 4104) catches what
  file scanning misses.
- **Linux:** ClamAV (`clamdscan`) on a schedule, plus the
  freshness of its signatures as its own info-level alert.
  Sysmon for Linux (measured current: 1.5.3) feeds the `sysmon`
  sense on the same box.
- **macOS:** XProtect/MRT run automatically with no stable API,
  so the collector watches what the OS surfaces: XProtect
  detections in the unified log and Gatekeeper assessments.

Profile knobs: `severity_floor` (Defender "severe" maps to
critical) and the usual cooldown/cap gates — AV products love
to re-report the same quarantined file. (Scheduled on-demand
sweeps are not wired: there is no `scan_schedule` knob in the
profile today.)

### Basic hygiene senses

One sense per check, all cheap, all per-platform. They answer the
question "is the boring stuff actually on?"

- `av_posture` — is real-time protection enabled, and are
  signatures current? Shipped as one stat, not a scan. Linux
  reads the mtime of the ClamAV daily signature file and calls
  it stale after 7 days. Windows asks `sc query WinDefend`.
  macOS has no stable XProtect read, so the line stays
  unreadable. A stale or stopped tool is labeled T1562.001.
  The line is diffed, and a flip is filed. Unreadable does not
  overwrite the last good reading.
- `firewall` — host firewall state per platform (Windows
  Firewall profiles, `ufw`/nftables, macOS `pf`/Application
  Firewall). Reports profile changes, not every dropped packet.
  Full spec below; the cage-verification job in that spec is
  future work, listed in FUTURE.md.

### `firewall` — host firewall state, rule changes, and cage verification

The hygiene list above treats this sense as "is the host firewall
on." The full spec has three jobs, in increasing order of
ambition. The first two are sensing; the third is enforcement and
stays opt-in, like every hardening knob.

**1. Posture: is the firewall on, and did that change?**

Shipped, as one line in the Oracle context, not as a collector
daemon. Windows reads `netsh advfirewall show allprofiles` (profile
state only). Linux reads `ufw status` when ufw is installed, otherwise
the iptables `-P` policy lines. macOS reads
`socketfilterfw --getglobalstate` and does not call `pfctl`. A profile
or policy that is off is labeled T1562.004. The line is diffed
against the previous reading, so a flip says "changed" and is
filed once. Unreadable stays unreadable and does not overwrite
the last good reading. The rule-hash diff and the cage check
below are listed in FUTURE.md.

Listed in FUTURE.md. This is the ruleset hash, not the
posture line above. The collector would snapshot the rule set and
file an alert on a new allow rule, never on every dropped packet:

- **Windows:** `Get-NetFirewallProfile` (Domain/Private/Public
  enabled flags) plus a hash of the `Get-NetFirewallRule` set.
  A profile flip is medium; a new inbound allow rule is high.
- **Linux:** `nft list ruleset` (or `iptables-save` /
  `ufw status`), hashed the same way. Read-only; runs with
  whatever privilege the ruleset needs.
- **macOS:** `pfctl -sr` plus the Application Firewall state
  (`socketfilterfw --getglobalstate`).

Profile knobs (future, arriving with the collector):
`watch_rules` (bool, default true — diff the ruleset, not just
on/off), `severity_inbound_allow` (default high),
`poll_interval_sec` for the collector daemon. None of these
names exists in the profile today.

**2. Cage verification: did the job's network cage hold?**
Future work — listed in FUTURE.md; no collector performs this
check today. The runner can already cage a job's network on Linux: bwrap
runs with `--unshare-net`, so the job gets loopback only —
but only in enforce mode (M6); by default the job's network
edge is unrestricted. The firewall sense is how the Oracle
*would check* the cage claim instead of trusting it: the
collector would watch for what a caged job must never do — an
outbound connection from a job UID, a new listener inside a
job window — and file it with `job_id_hint` set, so the
Oracle correlates directly instead of by timestamp. On
Windows the cage is per-user WFP rules tied to the job
identity (M8 `--run-as`); the collector would read the
effective rules for that user the same way.

This keeps the architecture's split clean: the *cage* is
enforcement (runner, opt-in), the *verification* is sensing
(this sense — always safe to leave on).

**3. Egress policy (opt-in enforcement, not a sense).**
Per-job-identity egress rules — the job user may reach
loopback and nothing else, or an allowlist from profile —
are the answer to the exfiltration shape the secret-scanner
cannot see: a job that phones home prints nothing, so there
is no output to scan. This is deliberately not part of the
sense. Senses never enforce. The design lives in
`docs/networking.md`.
- `patch_level` — *(future sense, listed in FUTURE.md)*
  pending security updates (Windows Update status,
  unattended-upgrades/dnf-automatic state, macOS
  softwareupdate). Info-level; the Oracle correlates "unpatched
  for 90 days" with everything else.
- `listening_sockets` — *(future sense, listed in FUTURE.md)*
  listening ports vs the expected baseline in profile
  (`expected_ports`). A new listener is medium by default; the
  Oracle decides if it matters.
- `persistence` — *(future sense, listed in FUTURE.md)*
  autorun/persistence locations: Windows autoruns (Run keys,
  services, scheduled tasks), Linux systemd units + cron,
  macOS LaunchAgents/LaunchDaemons. A new entry outside a job
  window is the classic backdoor shape.
- `disk_encryption` — *(future sense, listed in FUTURE.md)*
  BitLocker / LUKS / FileVault status. Info-level posture,
  mostly for the "is this box actually hardened" question.

None of these remediate. They file alerts; the Oracle fuses
them with job activity the same way it fuses IDS alerts. A
disabled Defender *during* a job run is one incident, not two
alerts.

## Config

```json
"sensors": {
  "host_ids": {
    "enabled": true,
    "key_id": "ids-daemon",
    "weight": 1.0,
    "profile": {
      "severity_floor": "low",
      "cooldown_sec": 300,
      "max_per_hour": 60,
      "future_knob": "anything you need later"
    }
  }
}
```

- `enabled` (bool, default false): the sense files alerts only when true.
- `key_id` (string, required): the restricted key the daemon signs
  with. Two senses may not share a key — the key is the daemon's identity.
- `weight` (number >= 0, default 1.0): the Oracle's weighting for
  this source. Turn a noisy sensor down, a trusted one up, or to 0
  to mute it without disabling ingest.
- `profile` (object): tunables. Known knobs:
  - `severity_floor`: drop alerts below this severity at ingest.
    One of critical/high/medium/low/info. Default info (keep all).
  - `cooldown_sec`: drop repeats of the same sensor+title within
    this window. Default 0 (no dedup).
  - `max_per_hour`: sliding-window cap per sense; over-cap alerts
    are dropped. Default 0 (unlimited).

Pair each sense key with a least-privilege entry in `key_policies`:

```json
"key_policies": {
  "ids-daemon": {"allowed_kinds": ["sensor_alert"]}
}
```

Keys without a policy entry are unrestricted, so write the entry.

## Alert format

Alerts are signed jobs, same envelope as everything else. The
daemon signs with its restricted key and emails (or queues) the job:

```json
{
  "v": 1, "type": "job", "kind": "sensor_alert",
  "job_id": "<uuid>", "issued_at": "<UTC ISO>",
  "sensor": "host_ids",
  "severity": "high",
  "title": "unexpected outbound connection",
  "detail": {"dst": "203.0.113.7:443", "pid": 4123},
  "observed_at": "<UTC ISO, optional>",
  "job_id_hint": "<runner job_id, optional>"
}
```

- `severity`: critical/high/medium/low/info. Missing defaults to info.
- `title`: required, non-empty. Used for cooldown dedup.
- `detail`: optional object. String values are redacted with the
  Oracle's standard patterns before any answer leaves the box.
- `job_id_hint`: if the sensor knows which runner job was active,
  it says so; the Oracle correlates directly instead of by timestamp.

## Ingest path

In `handle_mail`, after the signature and key-policy checks, a job
with `kind: "sensor_alert"` is routed to ingest instead of execution:

1. shape validation (rejects are poison: marked seen, logged),
2. the sensor must be configured and enabled,
3. the signing key must be bound to that sensor
   (`sensors.<name>.key_id`) — a daemon cannot file for another sense,
4. profile gates (severity floor, cooldown, hourly cap) — drops are
   logged, not errors,
5. the alert is appended to `senses.jsonl` in the base dir (capped at
   5000 lines), with `received_at`, `key_id`, and the sense's weight
   at ingest time.

No result message is sent. Dry-run mode describes the alert and
stores nothing.

## Reading signals: the `senses` query op

```json
{"op": "senses", "sensor": "host_ids", "severity_floor": "medium",
 "since": "2026-10-15T12:00:00Z", "until": "...", "limit": 20}
```

Returns matching alerts ranked by **score = weight x severity**
(critical=4, high=3, medium=2, low=1, info=0.5), each carrying its
`weight` and `score` so the reader sees exactly how much the Oracle
weighed it. Titles and string details are redacted before the
answer leaves the box.

This is the correlation primitive: "what did the sensors see while
job X ran" is a `senses` query with `since`/`until` around the job's
window, or a direct hit via `job_id_hint`.

## Tuning notes

Start wide (floor info, no cooldown, generous caps, weight 1.0)
and tighten from the stored data. The weight is the fast knob:
a chatty-but-useful sensor stays at full ingest with a low weight,
so it informs without dominating. The profile gates are the slow
knobs: they decide what is worth storing at all.
