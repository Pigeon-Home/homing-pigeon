# Pi Health — an example Homing Pigeon extension

A sense for the health of the machine it runs on, and the Pi
Light showcase: on a Pi it runs with no local model anywhere
in the loop — but nothing about it is Pi-only. The watcher
reads the machine's vitals — CPU/SoC temperature, undervoltage
and throttling, disk usage, memory pressure — and files what
needs attention as Oracle signals. A Raspberry Pi exposes the
fullest picture (it alone reports undervoltage); a laptop
exposes temperature, disk and memory; a machine that exposes
almost nothing still gets its disk watched. Same extension,
same signals everywhere — which is the point: run it on a Pi
Light install and on a laptop install side by side, and any
difference is the platform and the Oracle configuration, not
the extension. That makes the pair a clean A/B for the two
architectures.

The declared signals:

| Signal | Fires when | Severity |
|--------|------------|----------|
| `board_overheating` | CPU/SoC temperature reaches the `temp_high_c` tunable (default 80) | high |
| `undervoltage_detected` | The Pi firmware's throttled bitmask shows undervoltage or throttling, now or since boot | high |
| `disk_pressure` | The `disk_mount` mount (default `/`) reaches the `disk_high_pct` tunable (default 90) | medium |
| `memory_pressure` | Available memory falls to the `mem_avail_low_pct` tunable (default 10) | medium |

The two high signals cross the local wake gate: on a Pi Light
install, a hot or power-starved board wakes the deterministic
Oracle, which files its brief from the alert itself.

Every source is optional and capability-based: a source the
machine doesn't expose reports nothing, which never yields a
signal and is never an error. Temperature comes from the
Linux thermal sysfs (`/sys/class/thermal`), preferring the
zone whose type names the SoC or CPU package (`cpu-thermal`
on a Pi, `x86_pkg_temp` on Intel laptops) over motherboard
and wifi zones. Throttling comes from `vcgencmd get_throttled`
— Pi-only by nature; everywhere else power simply has nothing
to say, and `undervoltage_detected` never fires. Disk comes
from the mount (portable). Memory is `/proc/meminfo` on
Linux, `GlobalMemoryStatusEx` on Windows, and `os.sysconf`
page counts on other POSIX systems. A signal files once when
its condition appears, and again when the reading moves; the
pass's state lives in `.pi-health-state.json` next to the
script.

Run one pass on the machine:

```bash
python3 pi_health.py --local-dir ~/.homing-pigeon --key-id pi-key
# HOMING_PIGEON_SENSOR_SECRET holds the pi_health sense's key
```

Or try it anywhere by feeding it a readings file instead of
live reads:

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

## Light mode

This sense is the Pi Light showcase, and there is nothing to
tune down: a pass is a handful of capability reads — the
thermal sysfs, one `vcgencmd get_throttled` call where the
firmware tool exists, a disk-usage read on `disk_mount`, and
the memory counters — with no network and no model anywhere
in it, and the state file stays a few lines of JSON. Leave
`disk_mount` on the one mount that matters and run it as
often as you like.

The full extension walkthrough — manifest fields, the
versioning contract, sensor binding, and how to turn this
example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).
