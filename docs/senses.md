# Oracle senses

Senses are inbound signal extensions: external daemons (a host
intrusion-detection tool, a network monitor, later anything else)
that file signed alerts with the Oracle. The Oracle never trusts an
alert on its own; it fuses the alert with what it already knows —
which job was running, what the job was supposed to do, whether it
stayed confined — and that fusion is what makes the signal useful.

Alerts are advisory. Nothing in this path executes, pages, or
blocks. (Outbound reach to the owner is a separate, spec-only
extension: `docs/dri-playbook.md`.)

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
