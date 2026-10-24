# Sky Watcher — an example Homing Pigeon extension

A sense for people who like looking up. It polls the
International Space Station's position — the free feed at
[wheretheiss.at](https://wheretheiss.at), no API key — and
files the passes over your house that are worth stepping
outside for.

One honesty note: this example reaches out to the internet —
that is what an example sense is for. The runner itself never
phones home; it only ever polls its mailbox and reads its
local inbox. The reaching-out lives here, in the producer you
choose to run.

Most ISS passes are invisible: broad daylight, or the station
in Earth's shadow, or a track that never climbs out of the
haze. The watcher does the geometry — where the station is,
where its ground track is taking it, whether it is sunlit,
whether your sky is dark — and files three declared signals:

| Signal | Severity | Fires when |
|--------|----------|------------|
| `station_approaching` | info | The station enters the approach corridor (`approach_radius_km`, default 5000 km) around the observer |
| `visible_pass_starting` | medium | A sunlit pass over a dark sky begins within `visible_lead_sec` (default 600), culminating above `visible_min_elevation_deg` (default 10°) |
| `bright_pass` | high | That pass culminates at or above `bright_min_elevation_deg` (default 65°) — near zenith, the wake-the-house one |

Set your sky first: put `observer_lat` and `observer_lon` in
the manifest's tunables. With no observer set the watcher
files nothing and says so.

One pass of the watcher is one position sample. Run it on a
one-minute timer:

```bash
# crontab: every minute
* * * * * python3 sky_watcher.py --local-dir <runner base dir> --key-id <its key id>
```

Without `--local-dir` it prints one alert payload per line;
signing and delivery then follow the standard senses flow.
State lives in `.sky-watcher-state.json` next to the script;
delete it and the next pass starts fresh.

Replay a recorded feed instead of the live one — one
wheretheiss.at response object, or a JSON list of them:

```bash
python3 sky_watcher.py --samples recorded-passes.json
```

That is also how the sense is demoed and tested: no network,
a scripted pass, and every stage firing in order. A feed
outage on the live path is a quiet no-op — nothing files, the
state is untouched, and the next minute tries again.

### Other tunables

`dark_sun_elevation_deg` (default -6) is the sun elevation at the observer below which the sky counts as dark for `visible_pass_starting`.

## Light mode

The whole cost of this sense is the feed poll: one small HTTPS
request to wheretheiss.at per pass, at the `poll_interval_sec`
cadence (60 by default), plus geometry that amounts to nothing
on the Pi's CPU. That is already the whole footprint on a Pi
Light install — but if the box's uplink is precious, raise
`poll_interval_sec` toward 300: a pass unfolds over minutes
and `visible_lead_sec` (600) still leaves warning time, at the
price of a coarser approach track. A feed outage is a quiet
no-op either way, and replaying `--samples` costs no network
at all.

Attribution: ISS position data from
[wheretheiss.at](https://wheretheiss.at)
(`api.wheretheiss.at/v1/satellites/25544`), polled at the
60-second default cadence. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and
how to turn this example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).
