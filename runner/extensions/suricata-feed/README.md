# Suricata Feed — an example Homing Pigeon extension

A sense that feeds the Oracle the detections in Suricata's
eve.json. Suricata is a network IDS: it watches traffic on an
interface and appends one JSON object per event to `eve.json`
— the `log_paths` tunable, default
`/var/log/suricata/eve.json`. Most of eve.json is traffic,
not detection, so this sense files only the two event types
that are Suricata saying something is wrong, one filing per
distinct episode, and parses everything else to nothing.

That last part is a deliberate choice, not an omission. The
`http`, `tls`, `dns`, `flow`, `fileinfo`, and `stats` events
are a flow record, in volume; filing them would hand the
Oracle a transcript instead of a detection. A sense that
wants flows should declare so in its own manifest, not
borrow this one's.

An alert episode is one `signature_id` from one `src_ip` to
one `dest_ip`. An anomaly episode is one distinct
`anomaly.event`. One episode files once, stays quiet while
it keeps firing, and files again only when a new distinct
episode appears, when `episode_cooldown_sec` has passed
since it filed, or after it has cleared — gone quiet for
`episode_cooldown_sec` — and returned.

The log file is tailed incrementally, not re-read: the state
carries reader offsets per path (`{"inode", "offset"}`), a
missing file yields no events and keeps its offset, and an
inode change or a file that shrank (rotation, truncation)
restarts that file from 0.

**Measured footprint (environment-bound):** on this
project's measurement VM, Suricata idled at ~52 MB RSS and
~0.5% CPU — **with the distro's minimal ruleset only** (the
protocol-event rules Ubuntu ships, no signature set). A
production ET Open ruleset takes Suricata to several times
that; the production figure was not measured, and the 52 MB
number must not be quoted without its ruleset attached.
Budget several × 52 MB on a box that runs real signatures.

The fixture under `fixtures/` is a trimmed copy of a real
captured eve.json sample from that measurement run — one
`http` event (traffic; parses to nothing) and one `anomaly`
event (files `suricata_anomaly`). The capture contained no
`alert` event, so no alert line was invented for it; alert
coverage lives in the tests, built to the documented
eve.json alert shape.

## Signals

| Signal | Fires when |
|--------|------------|
| `suricata_alert` | An `alert` event arrives (a signature matched), once per episode. Severity is Suricata's own: 1 → high, 2 → medium, 3 → info |
| `suricata_anomaly` | An `anomaly` event arrives (decoder or protocol-parser trouble), once per distinct `anomaly.event` per cooldown window (medium severity) |

The alert detail carries the `signature`, `category`,
`signature_id`, Suricata's numeric `severity`, both IPs,
both ports, and the protocol, so the Oracle sees the match
Suricata saw, not a paraphrase of it.

## Tunables

| Tunable | Default | Meaning |
|---------|---------|---------|
| `log_paths` | `["/var/log/suricata/eve.json"]` | eve.json files to tail |
| `poll_interval_sec` | `60` | The cadence to run the pass on; advisory, the runner never runs sense code |
| `episode_cooldown_sec` | `3600` | An episode refiles after this long, and clears after this long quiet; also the anomaly dedup window |

Run one pass:

```bash
python3 suricata_feed.py
# one alert payload per line on stdout; state (including the
# reader offsets) in .suricata-feed-state.json next to the
# script
```

Or try it anywhere against fixtures, with no live Suricata
at all: a readings file (`{"now": ..., "events": [...]}`),
or the whole fixture log parsed from offset 0:

```bash
python3 suricata_feed.py --readings readings.json
python3 suricata_feed.py --log-file fixtures/suricata-eve.json
```

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and how
to turn this example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Light mode

For a Pi Light install, tune it down with its tunables: raise `poll_interval_sec` from 60
to 600, and raise `episode_cooldown_sec` — at 86400, an
episode that keeps firing files at most once a day. The
sense itself is a file tailer and a JSON parser; its own
cost is the poll cadence. Suricata's cost is the ruleset's
(see the footprint note above): ship a trimmed ruleset on a
small box, not the full ET Open set.
