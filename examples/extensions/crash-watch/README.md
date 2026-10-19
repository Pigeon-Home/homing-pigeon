# Crash Watch — an example Homing Pigeon extension

A sense for crash and core dump directories. Point it at the
folder (or folders) where programs leave their dumps — a
fuzzer's output directory, a test fleet's core folder — and
the Oracle learns which binary died, and whether it keeps
dying. It is built for the triage question fuzzing and test
work always asks first: is this one crash, or is the same
binary crashing again and again?

The watcher files two declared signals:

| Signal | Fires when |
|--------|------------|
| `crash_dumped` | A crash file never seen before lands in a watched directory — a new path, or the same path with a changed size or mtime (a fresh dump overwrote the old one) |
| `crash_repeated` | The same binary crashes again within `repeat_window_sec` (default 3600) — filed instead of `crash_dumped`, with the count of that binary's crashes inside the window |

Which binary a dump belongs to is read off its filename: a
known dump suffix (`.mdmp`, `.dmp`, `.core`, `.crash`) is
stripped when present, and otherwise the binary is the stem
before the first `.` in the name — so `app.mdmp` belongs to
`app` and `notes.txt` to `notes`.

Run one pass:

```bash
python3 crash_watch.py --local-dir <runner base dir> --key-id <its key id>
# HOMING_PIGEON_SENSOR_SECRET holds the crash_watch sense's key
```

Without `--local-dir` it prints one alert payload per line;
signing and delivery then follow the standard senses flow.
State lives in `.crash-watch-state.json` next to the script;
delete it and the next pass starts fresh. A pass scans at
most `max_files_per_pass` files (default 1000); files beyond
the cap are counted, not silently dropped, and are not marked
seen — they file on the next pass.

Or try it anywhere by feeding it a readings file instead of
live directories:

```bash
python3 crash_watch.py --readings readings.json
# one alert payload per line on stdout
```

A readings file is one JSON object:

```json
{"now": 1792375113.0, "truncated": 0,
 "files": [{"name": "app.dmp", "dir": "./crashes", "size": 4096,
            "mtime": 1792375000.0, "binary": "app"}]}
```

## Light mode

On a Pi Light install, tune the manifest's tunables down:
raise `poll_interval_sec` (600 is a calm cadence for a dump
folder), keep `watch_dirs` to the one directory that matters,
and lower `max_files_per_pass` so a single pass never walks a
huge backlog at once — the files past the cap are counted and
file on later passes, so nothing is lost, it just arrives
more slowly.

The full extension walkthrough — manifest fields, the
versioning contract, sensor binding, and how to turn this
example into your own package — is in
[docs/extensions.md](../../../docs/extensions.md).
