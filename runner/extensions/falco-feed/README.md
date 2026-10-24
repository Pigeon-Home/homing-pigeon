# Falco Feed — an example Homing Pigeon extension

A sense that feeds the Oracle the alerts Falco already
decided were worth writing. Falco is a runtime security
monitor: its rules watch syscalls, containers, and kernel
behaviour, and with its file output enabled it appends one
JSON object per alert to a file. This sense tails that file —
point Falco's `file_output` at the `log_paths` tunable
(default `/var/log/falco/falco.json`) — and files the
high-priority end of what Falco saw, one filing per distinct
episode.

An episode is one rule plus a digest of the alert's
`output_fields`: the same rule firing against a different
process, file, or container digests differently, so it is a
different episode and files on its own. One episode files
once, stays quiet while it keeps firing, and files again
only when a new distinct episode appears, when
`episode_cooldown_sec` has passed since it filed, or after
it has cleared — gone quiet for `episode_cooldown_sec` —
and returned.

The log file is tailed incrementally, not re-read: the state
carries reader offsets per path (`{"inode", "offset"}`), a
missing file yields no events and keeps its offset, and an
inode change or a file that shrank (rotation, truncation)
restarts that file from 0.

The fixtures under `fixtures/` are **synthetic**: Falco never
ran in this project's measurement environment (see the
footprint note below), so no captured sample exists. The
fixture lines are built from Falco's documented JSON alert
shape — `time`, `rule`, `priority`, `output`,
`output_fields`, `tags`, `hostname` — and are labelled
synthetic here rather than passed off as captures.

Two facts about Falco belong in plain sight:

- **No footprint is claimed.** Falco did not run in the
  measurement environment — the sandbox kernel denied its
  drivers and its BPF programs — so there is no measured
  RSS or CPU figure for it, and this README does not
  invent one.
- **A successful install is not a working Falco.** Falco is
  the one collector in its class whose function depends on
  kernel privileges an installer cannot guarantee:
  containers, locked-down kernels, and managed cloud images
  can all say no to the driver *after* a successful install,
  leaving Falco present and silently non-functional. Where
  that happens this sense tails a file that never grows,
  which is quiet, not an error it can see. Check that Falco
  itself reports a healthy driver before expecting signals.

## Signals

| Signal | Fires when |
|--------|------------|
| `falco_critical` | A rule fires at `Emergency`, `Alert`, `Critical`, or `Error` priority (high severity), once per episode |
| `falco_warning` | A rule fires at `Warning` or `Notice` priority (medium severity), once per episode |

`Informational` and `Debug` alerts are parsed but never
filed: at those priorities Falco is a firehose, and a sense
that files them all teaches the Oracle to ignore the sense.
A priority outside Falco's eight documented names makes the
line malformed, and malformed lines are ignored.

## Tunables

| Tunable | Default | Meaning |
|---------|---------|---------|
| `log_paths` | `["/var/log/falco/falco.json"]` | Falco JSON alert files to tail; point Falco's `file_output` at the first |
| `poll_interval_sec` | `60` | How often the runner wakes the sense |
| `episode_cooldown_sec` | `3600` | An episode refiles after this long, and clears after this long quiet |

Run one pass:

```bash
python3 falco_feed.py
# one alert payload per line on stdout; state (including the
# reader offsets) in .falco-feed-state.json next to the
# script
```

Or try it anywhere against fixtures, with no live Falco at
all: a readings file (`{"now": ..., "events": [...]}`), or
the whole synthetic fixture log parsed from offset 0:

```bash
python3 falco_feed.py --readings readings.json
python3 falco_feed.py --log-file fixtures/falco-alerts.jsonl
```

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and how
to turn this example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Light mode

For a Pi Light install, tune it down with the tunables the
code actually implements: raise `poll_interval_sec` from 60
to 600, and raise `episode_cooldown_sec` — at 86400, an
episode that keeps firing files at most once a day. The
sense itself is a file tailer and a JSON parser; its own
cost is the poll cadence, and Falco's cost is Falco's (see
the capability note above: on a Pi, confirm the driver loads
before counting on either).
