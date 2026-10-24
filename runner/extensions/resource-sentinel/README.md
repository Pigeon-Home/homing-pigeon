# Resource Sentinel — an example Homing Pigeon extension

A sense that watches the machine's resources the way an
intrusion analyst would. The runner's built-in resource
monitor (`runner/oracle/resources.py`) already files threshold
crossings — CPU, memory, or disk pressure at an instant —
into the security event log that feeds the DRI paging path.
This sense is the deliberate other half: it keeps a rolling
window of its own samples and fires only on **rates and
trends**, the shapes hostile software leaves behind. A
compile pegs the CPU for a minute; it does not hold it at
97% for half an hour. Nothing here ever fires on one sample.

The watcher files four declared signals:

| Signal | Fires when |
|--------|------------|
| `cpu_saturation_sustained` | Total CPU busy stays at or over `cpu_high_pct` (default 95) between the first and last samples of the window — miner or spin-loop shape |
| `disk_fill_velocity` | Free space on the watched mount shrinks at or faster than `disk_fill_gb_per_hour` (default 10) across the window — log bombing, evidence flooding, a runaway writer |
| `process_storm` | The process count grows by at least `process_growth` (default 200) from the window's low point to its end — fork-bomb or runaway-spawn shape |
| `memory_exhaustion_trend` | Available memory falls steadily (at most one small rise) to or under `mem_floor_pct` (default 15), dropping at least `mem_drop_points` (default 25) across the window — a leak or memory bomb, where pi-health's static threshold would only say "low" |

A signal files when its condition first holds, again when
its headline metric moves to a coarser bucket (the situation
worsened), and goes quiet while it holds steady. Sources
are capability-based — `/proc/stat`, the `/proc` process
count, `/proc/meminfo`, `shutil.disk_usage` — so a machine
that exposes nothing yields nothing, and on a box without
`/proc` only the disk velocity still speaks. A signal needs
at least `min_samples` samples spanning `min_span_sec`
inside `window_sec` before it can fire at all: a young
window is evidence of nothing.

Run one pass:

```bash
python3 resource_sentinel.py --local-dir <runner base dir> --key-id <its key id>
# HOMING_PIGEON_SENSOR_SECRET holds the resource_sentinel sense's key
```

Without `--local-dir` it prints one alert payload per line;
signing and delivery then follow the standard senses flow.
State lives in `.resource-sentinel-state.json` next to the
script — the rolling sample window lives there, so deleting
it restarts every trend from zero evidence.

Or try it anywhere by feeding it a readings file instead of
live counters:

```bash
python3 resource_sentinel.py --readings readings.json
# one alert payload per line on stdout
```

A readings file is one JSON object of raw counters (any of
them may be `null`; a null source simply has no vote):

```json
{"now": 1792375113.0, "cpu_total": 812345, "cpu_idle": 701122,
 "disk_free_bytes": 412316860416, "processes": 231,
 "mem_avail_pct": 61.5}
```

### Other tunables

`disk_mount` (default `/`) is the mount point whose free space `disk_fill_velocity` watches; `max_samples` (default 240) bounds how many samples the rolling window keeps, and is raised to the window's minimum if set lower.

## Light mode

The cost of this sense is the sampling itself, and it is
already small; Light mode is cadence and window discipline.
Raise `poll_interval_sec` to 300 — the trends it hunts play
out over minutes to hours, so a five-minute cadence loses
nothing — and shorten `window_sec` toward 900 with
`min_span_sec` toward 300, which also caps the state file's
sample list. A Pi that samples five counters every five
minutes will not notice this sense is there.

The full extension walkthrough — manifest fields, the
versioning contract, sensor binding, and how to turn this
example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).
