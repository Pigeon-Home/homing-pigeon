# Tripwire — an example Homing Pigeon extension

A sense for people who test other people's systems and want to
know when the ground moved. Point it at a tree — a release
directory, a web root, a test fixture tree, `/etc` — and it
hashes every regular file with SHA-384 (the project's digest)
and diffs the result against the baseline it recorded on its
first pass. What appeared, what vanished, and what changed is
exactly what the Oracle hears about; a tree that did not move
files nothing.

The first pass learns. With `learn_first_pass` set (the
default) pass one absorbs the tree as the baseline and files
nothing, because a tripwire that alarms on its own install
teaches its operator to ignore it. Set it false and the first
pass instead reports every file as appeared.

The watcher files three declared signals:

| Signal | Fires when |
|--------|------------|
| `file_appeared` | A file is present in the watched tree that was not in the recorded baseline (medium) |
| `file_vanished` | A file in the recorded baseline is no longer present in the watched tree (medium) |
| `file_changed` | A file's SHA-384 digest differs from the baseline (high); oversize files (over `max_file_mb`) carry no digest and compare by size only — a same-size rewrite of an oversize file is not detected, and a size change is |

Files are walked in sorted order and paths are processed in
sorted order. At most `max_files` files (default 10000) are
recorded per pass; files past the cap are counted in the
readings' `truncated` field, are not in the state, and so diff
again on the next pass. Files matching `excludes` (default
`*.pyc`, `__pycache__`, `.git`, `.tripwire-state.json`) are
skipped, as is the state file itself. At most
`max_alerts_per_pass` alerts (default 100) are filed per pass,
but the full new baseline is always absorbed: differences past
the cap are recorded, not re-filed.

Run one pass:

```bash
python3 tripwire.py
# watches the manifest's root tunable (default ".");
# one alert payload per line on stdout; state in
# .tripwire-state.json next to the script
```

Or try it anywhere by feeding it a readings file instead of
a live tree:

```bash
python3 tripwire.py --readings readings.json
```

A readings file is one JSON object:

```json
{"now": 1792375113.0, "truncated": 0,
 "files": {"app.py": {"sha384": "9f86d0…", "size": 412},
           "big.iso": {"sha384": null, "size": 90000000,
                        "oversize": true}}}
```

Platform coverage: the walk, the hashing, and the diff are
plain standard-library file I/O and run anywhere Python runs
— Linux, macOS, and Windows. There is no platform-specific
source to go missing; a root that does not exist reads as an
empty tree, never an error.

## Light mode

For a low-power install (a Pi, a small VPS, a box doing other
work), turn the knobs the manifest actually implements:

- `poll_interval_sec` up — 300 by default, 3600 for a tree
  that should only be checked hourly. This is the biggest
  lever: the cost is per pass, so cadence is cost.
- `root` narrower — watch the directory that matters
  (`/etc`, one release tree) instead of a whole filesystem.
- `excludes` up — add build output, caches, logs, and anything
  else whose churn is not news.
- `max_file_mb` down — files over the cap are recorded by
  size only and their bytes are never read.
- `max_alerts_per_pass` down — fewer alerts per pass, but
  remember the trade-off owned above: the baseline is still
  absorbed in full, so differences past the cap are recorded,
  not re-filed later.

The honest limit: hashing costs the bytes it reads. A pass
over N bytes of in-cap files reads N bytes and hashes them,
and no knob changes that arithmetic — a huge tree cannot be
made cheap, only narrower (smaller `root`, more `excludes`,
lower `max_file_mb`) or less frequent (higher
`poll_interval_sec`). As a practical sizing note, keep the
in-cap total under a few hundred megabytes for a Pi-class
box at an hourly cadence; a multi-gigabyte tree belongs at
a daily cadence, watched narrowly, or not on a Pi at all.

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and how
to turn this example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).
