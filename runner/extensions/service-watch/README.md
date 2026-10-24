# Service Watch — an example Homing Pigeon extension

A sense for operations and DRI duty: the box exists to run
certain things, and this watcher checks they are actually
running. Point it at the services that matter — a daemon, a
worker, a helper process — and the Oracle learns the moment
one disappears, the moment it comes back, and when one cannot
decide whether it is up or down.

Configure the watched services in the manifest's `services`
tunable. Each entry is `{"name": ..., "match": ...}`:
`"exact"` compares the process name, `"substring"` looks for
the name inside the full command line.

```json
{"services": [{"name": "sshd", "match": "exact"},
              {"name": "oracle-helper", "match": "exact"}],
 "flap_window_sec": 600, "flap_count": 4,
 "poll_interval_sec": 30, "learn_first_pass": true}
```

The watcher files three declared signals:

| Signal | Fires when |
|--------|------------|
| `service_down` | A service that was up is no longer present (high) |
| `service_recovered` | A service returns after a filed outage (info) |
| `service_flapping` | A service's transitions inside `flap_window_sec` reach `flap_count` (medium) |

The first pass is a learn pass by default (`learn_first_pass`):
it records which services start up and which start down and
files nothing, so there is no false outage for a service that
was already down, and no filed recovery when it later starts.
A `service_down` records when the service fell; the matching
`service_recovered` reports the downtime from that moment.
Flapping files once per burst — it rearms only after a full
`flap_window_sec` with no transitions.

Live reads are Linux-only: the process list comes from
`/proc` (`comm` for the name, `cmdline` for the command line),
and a process that exits mid-scan is skipped quietly. On
Windows and macOS there is no `/proc`, so the live read yields
an empty process list — fixture mode is the path there. Feed
the sense a readings file on any box:

```bash
python3 service_watch.py --readings readings.json
# one alert payload per line on stdout
```

A readings file is one JSON object:

```json
{"now": 1700000000.0,
 "processes": [{"name": "sshd", "pid": 412, "cmdline": "/usr/sbin/sshd"}]}
```

Run one pass on the machine:

```bash
python3 service_watch.py --local-dir ~/.homing-pigeon --key-id svc-key
# HOMING_PIGEON_SENSOR_SECRET holds the service_watch sense's key
# state in .service-watch-state.json next to the script
```

Alert payloads printed to stdout are unsigned sense alerts;
signing and delivery follow the standard senses flow. The full
extension walkthrough — manifest fields, the versioning
contract, sensor binding, and how to turn this example into
your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Light mode

On a Pi Light install this sense should cost almost nothing:
raise `poll_interval_sec` from 30 to 300, watch fewer services
(keep the `services` list to the one or two processes the box
truly exists to run), and raise the flap thresholds —
`flap_window_sec` and `flap_count` — so only sustained churn
files. The live read is a single `/proc` scan per pass; at a
five-minute cadence it is negligible even on a Pi.
