# AIDE Feed — an example Homing Pigeon extension

A sense for the oldest question in host integrity: what
changed since the database was built? AIDE (Advanced
Intrusion Detection Environment) answers it in batch —
it walks the tree its config watches, compares hashes
and attributes against its recorded database, and writes
a plain-text report of what was added, removed, and
changed. This sense reads the report the owner's schedule
produced and files what it says, one alert per entry
class per report — never one per file.

The plumbing differs from a tailer, and that is correct
here: there is no event stream to tail, only a report
file that a scheduled scan replaces. The producer polls
the `report_paths` tunable; a report is NEW when the
file's `(inode, size, mtime)` fingerprint differs from
the reader state, and only a new report is read and
parsed. `parse_report()` reads the `Added entries:` /
`Removed entries:` / `Changed entries:` sections — entry
lines are an attribute mask ending in `: /path`
(`f+++++++++++++++++: /etc/probe-aide.txt`), with `f`,
`d`, and `l` prefixes for files, directories, and links.
No new report means the readings carry nothing and
nothing files; the same report twice files once — the
reader fingerprint is the first gate, and the fingerprint
`decide()` records in its state is the second. A report
with zero differences files nothing.

The report fixture under `fixtures/` (`aide-check.txt`)
is a trimmed copy of a real captured check — one added
entry, one changed entry — with its provenance stated in
`fixtures/README.md`.

## Signals

| Signal | Fires when |
|--------|------------|
| `aide_changed` | A new AIDE report lists at least one changed entry (medium severity) |
| `aide_removed` | A new AIDE report lists at least one removed entry (medium severity) |
| `aide_added` | A new AIDE report lists at least one added entry (info severity) |

Alerts fire in that order — changed, removed, added —
and each alert's detail is the same shape: the class
`count`, the first 20 `paths`, and the report
fingerprint. A class with no entries files nothing.

## Tunables

| Tunable | Default | What it does |
|---------|---------|--------------|
| `report_paths` | `["/var/log/aide/aide.log"]` | The AIDE report file(s) the owner's schedule produces; the first new report per pass is read |
| `poll_interval_sec` | 3600 | How often the producer checks for a new report; checking is a stat per path, so this is cheap at any cadence — the scan schedule, not this poll, is the real cadence |

Run one pass:

```bash
python3 aide_feed.py
# one alert payload per line on stdout; state (including
# the reader fingerprints) in .aide-feed-state.json next
# to the script
```

Or try it anywhere against fixtures, with no live AIDE
at all: a readings file (`{"now": ..., "report": {...},
"fingerprint": "..."}`, the report in the
`parse_report()` shape), or a whole fixture report:

```bash
python3 aide_feed.py --readings readings.json
python3 aide_feed.py --report-file fixtures/aide-check.txt
```

Footprint: AIDE has no daemon — 0 MB between scans,
~21 MB in a scoped scan burst (measured on a 2,489-entry
scoped config watching `/etc`, `/bin`, `/sbin`,
`/usr/bin`, `/usr/sbin`, `/boot`). The vendor whole-tree
default did not finish in 9 minutes on the measurement
box, so the installer ships a scoped config — AIDE's cost
is proportional to the watched tree, and nobody should
run the whole-tree default on a home box. The structural
limit rides along: AIDE tells you at the next scheduled
scan, not when it happens.

Alert payloads are unsigned sense alerts; signing and
delivery follow the standard senses flow. The full
extension walkthrough — manifest fields, the versioning
contract, sensor binding, and how to turn this example
into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Light mode

This sense is already the light shape: between passes it
does not exist, and a pass is one stat per report path
plus, when a report is new, one read of a small text
file. Tune it with its knobs: raise `poll_interval_sec` if hourly checks
are more often than the owner's scan schedule produces
reports, and keep `report_paths` to the one report the
schedule writes. The real light-mode decision is not
this producer's — it is the AIDE config's: ship the
scoped config (see the footprint note), because a
whole-tree scan is the only expensive thing in the
whole arrangement.
