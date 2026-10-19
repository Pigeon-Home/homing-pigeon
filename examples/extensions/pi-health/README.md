# Pi Health — an example Homing Pigeon extension

A sense for the board itself, and the Pi Light showcase: it
runs on a Raspberry Pi with no local model anywhere in the
loop. The watcher reads the board's vitals — SoC temperature,
undervoltage and throttling, disk usage, memory pressure —
and files what needs attention as Oracle signals.

The declared signals:

| Signal | Fires when | Severity |
|--------|------------|----------|
| `board_overheating` | SoC temperature reaches the `temp_high_c` tunable (default 80) | high |
| `undervoltage_detected` | The firmware's throttled bitmask shows undervoltage or throttling, now or since boot | high |
| `disk_pressure` | The `disk_mount` mount (default `/`) reaches the `disk_high_pct` tunable (default 90) | medium |
| `memory_pressure` | Available memory falls to the `mem_avail_low_pct` tunable (default 10) | medium |

The two high signals cross the local wake gate: on a Pi Light
install, a hot or power-starved board wakes the deterministic
Oracle, which files its brief from the alert itself.

Sources are all optional. Temperature comes from
`/sys/class/thermal`, throttling from `vcgencmd get_throttled`
(its absence off a Pi is a normal case, not an error), disk
from the mount, memory from `/proc/meminfo`. A signal files
once when its condition appears, and again when the reading
moves; the pass's state lives in `.pi-health-state.json` next
to the script.

Run one pass on the board:

```bash
python3 pi_health.py --local-dir ~/.homing-pigeon --key-id pi-key
# HOMING_PIGEON_SENSOR_SECRET holds the pi_health sense's key
```

Or try it anywhere — no Pi required — by feeding it a readings
file instead of the board:

```bash
python3 pi_health.py --readings readings.json
# one alert payload per line on stdout
{"detail": {"temp_c": 84.1, "threshold_c": 80.0}, "sensor": "pi_health", "severity": "high", "signal": "board_overheating", "title": "SoC temperature 84.1C reached the 80C limit"}
```

A readings file is one JSON object:

```json
{"temp_c": 84.1, "throttled": 327685, "disk_pct": {"/": 72.0},
 "mem_avail_pct": 41.5}
```

(`throttled` is the raw bitmask as an integer; any field may be
`null` or absent when its source has nothing to say.)

The full extension walkthrough — manifest fields, the
versioning contract, sensor binding, and how to turn this
example into your own package — is in
[docs/extensions.md](../../../docs/extensions.md).
