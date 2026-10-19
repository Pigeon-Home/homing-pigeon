# Release Drop — an example Homing Pigeon extension

A sense for a release drop folder. Point it at the folder
where release artifacts land, and the Oracle learns what
dropped — attested, not just announced: every arrival is
filed with the full SHA-384 digest (the project's digest)
of the bytes that actually landed, computed by this sense,
streamed in chunks so a large artifact never sits whole in
memory. And if a name that already dropped shows up again
carrying different bytes, that is filed loud, because an
artifact that changes under its own name is either a re-spin
nobody announced or a problem.

The watcher files two declared signals:

| Signal | Fires when |
|--------|------------|
| `artifact_arrived` | An artifact name never seen before lands in the drop folder; the detail carries the name, the size, and the full hex SHA-384 |
| `artifact_changed` | A known artifact name reappears with a different SHA-384; the detail carries the old and new digests side by side |

A file larger than `max_hash_mb` (default 512) is skipped
entirely for the pass — counted, named on stderr, and never
watched until it fits under the cap or the cap rises. An
artifact's arrival is only ever attested by a digest this
sense actually computed. A name that vanishes from the drop
is dropped from the state silently: no signal is declared
for departures, so none is filed.

Run one pass:

```bash
python3 release_drop.py --watch-dir path/to/drop --local-dir <runner base dir> --key-id <its key id>
# HOMING_PIGEON_SENSOR_SECRET holds the release_drop sense's key
```

Without `--local-dir` it prints one alert payload per line;
signing and delivery then follow the standard senses flow.
State lives in `.release-drop-state.json` next to the script;
delete it and the next pass starts fresh.

Or try its decisions anywhere by feeding it a readings file
instead of a live folder:

```bash
python3 release_drop.py --readings readings.json
# one alert payload per line on stdout
```

A readings file is one JSON object:

```json
{"now": 1792375113.0, "skipped_oversize": 0,
 "files": [{"name": "homing-pigeon-3.8.0.tar.gz", "size": 1048576,
            "sha384": "<full hex SHA-384 of the artifact>"}]}
```

(The hashing path itself is exercised live, through
`--watch-dir`; a readings file carries digests already
computed.)

## Light mode

On a Pi Light install, tune the manifest's tunables down:
raise `poll_interval_sec` (a drop folder rarely needs a
one-minute cadence), lower `max_hash_mb` so a pass never
spends Pi CPU hashing a very large artifact — oversize
artifacts then simply wait — counted as skipped, never as
arrivals — until the cap rises — and keep the sense on the
single `watch_dir` that releases actually land in.

The full extension walkthrough — manifest fields, the
versioning contract, sensor binding, and how to turn this
example into your own package — is in
[docs/extensions.md](../../../docs/extensions.md).
