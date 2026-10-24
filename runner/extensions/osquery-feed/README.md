# Osquery Feed — an example Homing Pigeon extension

A sense fed by [osquery](https://osquery.io/), the host
telemetry daemon. osquery answers scheduled SQL queries
about the machine — processes, users, listening ports —
and its differential mode writes only what *changed* since
the last run into the results log as JSON lines. This sense
tails that log (`osqueryd.results.log`) and files each
change the installer's light pack reports, so the Oracle
hears "a new user appeared" or "something is now listening
on 8080" as a declared signal instead of as raw telemetry.

The feed serves the light pack, not arbitrary packs. A
query name belongs to a kind by containment: it is a
"process" query if it contains `processes`, a "user" query
if it contains `users`, and a "listener" query if it
contains `listening_ports` — so the pack's `hp_processes`,
`hp_users` and `hp_listening_ports` map, and so do the bare
stock names `processes`, `users` and `listening_ports`.
Results lines from any other query are parsed and ignored,
deliberately: their rows have no declared meaning here.

An event's identity is its identifying columns — process:
`name`/`pid`/`path`; user: `username`/`uid`/`gid`;
listener: `port`/`protocol`/`address`/`pid` — and the
alert detail carries exactly the kind plus those columns.

osquery ships no config and no service unit; the installer
supplies both, and this feed expects the results log the
installer configures (the `log_paths` tunable, default
`/var/log/osquery/osqueryd.results.log`).

## Signals

| Signal | Fires when |
|--------|------------|
| `osquery_added` | A light-pack query reports a row as `added`. Medium severity for users and listening ports — a new account or a new open door matters — and info for processes, which come and go all day. Files once per `(kind, added, identity)` episode: repeats of the same add are quiet until the matching remove arrives |
| `osquery_removed` | A light-pack query reports a row as `removed`. Info severity. A remove after an add of the same identity is a new episode fact and files — and it re-arms the add, so a thing that leaves and returns files both times |

## Tunables

| Tunable | Default | Means |
|---------|---------|-------|
| `log_paths` | `/var/log/osquery/osqueryd.results.log` | The osqueryd results log to tail |
| `poll_interval_sec` | 60 | How often the runner wakes this sense; there is little point polling faster than the pack's query schedule |
| `filed_cap` | 10000 | Bound on remembered filed episodes; the oldest entries are evicted first |

Run one pass:

```bash
python3 osquery_feed.py
# one alert payload per line on stdout; state (including the
# reader offsets) in .osquery-feed-state.json next to the
# script
```

Or try it anywhere against fixtures, with no live osquery
at all: a readings file (`{"now": ..., "events": [...]}`),
or a whole fixture results log parsed from offset 0:

```bash
python3 osquery_feed.py --readings readings.json
python3 osquery_feed.py --log-file fixtures/light-pack.jsonl
```

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and how
to turn this example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Footprint

Measured ~27 MB RSS / ~0.1% CPU in scheduled-query mode on
the project's test VM (see the collector comparison in the
research notes) — the lightest host-telemetry daemon
measured, and the project's default collector. This
producer is a file tailer on top of that and costs almost
nothing of its own.

## Light mode

This feed is already the light mode story: osquery is the
default collector a Pi Light install ships, and its
scheduled-query mode needs no kernel privileges and no
local model. To tune it down further with the knobs the
code actually implements, raise `poll_interval_sec` from
60 to 300 — the pack's queries run on their own schedule
regardless, and the results log keeps every change until
the next pass reads it, so a slower poll loses nothing.
