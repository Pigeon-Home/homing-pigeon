# Backup Freshness — an example Homing Pigeon extension

A sense for operations: backups fail quietly. The job stops
running, the disk fills, the schedule rots, and nothing says
anything until the day the backup is needed and turns out to
be a month old. This watcher watches a backup directory and
tells the Oracle two things — that a new backup landed, and
that the newest one is getting old.

Configure it with the manifest's tunables: `watch_dir` (the
directory backups land in, default `./backups`), `glob` (which
files count, default `*`), and `stale_after_sec` (how old is
too old, default 90000 — just over a day). The newest regular
file matching the glob, by modification time, is the backup
whose freshness matters.

The watcher files three declared signals:

| Signal | Fires when |
|--------|------------|
| `backup_arrived` | A backup artifact with a newer mtime than any seen before appears (info) |
| `backup_stale` | The newest backup's age passes `stale_after_sec` (medium) |
| `backup_critical` | The newest backup's age passes twice `stale_after_sec` (high) |

Each staleness tier files once. Crossing from fresh to stale
files `backup_stale`; continuing to twice the threshold
files `backup_critical`. A jump straight past the critical
line files `backup_critical` only — the stronger statement
wins, not stale-then-critical in the same pass. A fresh
arrival files `backup_arrived` and resets the tier, so the
cycle can file again if backups stall a second time.

The age clock does not forgive an emptied directory: while
an artifact exists its age is `now - mtime`, and if the
directory goes empty the clock keeps running on the last
backup ever seen. If no backup has ever been seen at all the
sense stays quiet — that nothing has ever been backed up is
a configuration fact, not this sense's alert. Live reads are
portable (a directory listing, any platform); a missing
directory reads as no data, never an error.

Run one pass:

```bash
python3 backup_freshness.py --local-dir ~/.homing-pigeon --key-id backup-key
# HOMING_PIGEON_SENSOR_SECRET holds the backup_freshness sense's key
# state in .backup-freshness-state.json next to the script
```

Or try it anywhere by feeding it a readings file instead of
a live directory:

```bash
python3 backup_freshness.py --readings readings.json
# one alert payload per line on stdout
```

A readings file is one JSON object:

```json
{"now": 1700100000.0,
 "newest": {"name": "backup-2026-10-18.tar", "mtime": 1700000000.0, "size": 4096}}
```

(`newest` is `null` when the directory holds no matching
file; `size` is carried through to the arrival detail when
present.)

Alert payloads printed to stdout are unsigned sense alerts;
signing and delivery follow the standard senses flow. The full
extension walkthrough — manifest fields, the versioning
contract, sensor binding, and how to turn this example into
your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Light mode

This sense is already nearly free; say so honestly: one
directory listing per pass is all it ever does. On a Pi Light
install just raise `poll_interval_sec` from 3600 to 21600
and keep it to one `watch_dir` and one `glob` — there is
nothing else to tune down.
