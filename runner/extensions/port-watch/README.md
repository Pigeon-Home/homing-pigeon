# Port Watch — an example Homing Pigeon extension

A sense from the penetration-testing side of the house. It
diffs the machine's listening sockets on every pass and asks
the sweep question: what new doors opened, and are any of
them facing the street? The first pass learns the baseline
quietly (with the `learn_first_pass` tunable on, the default),
so the services that were always there never file; after that,
only genuinely new listeners do.

There is no process attribution, and the README should say so
as plainly as the code does: `/proc` reports sockets, not
their owners. Mapping a socket to a process takes an
inode-to-fd walk over every process on the box, which this
example deliberately does not do — the alert says a door
opened, not who opened it.

Platform coverage is Linux only: the sources are
`/proc/net/tcp`, `/proc/net/tcp6`, `/proc/net/udp`, and
`/proc/net/udp6`, and each missing file is skipped. TCP counts
state `0A` (LISTEN). UDP has no LISTEN state, so the
approximation — an approximation, stated as one — is that an
entry with no remote address (an unconnected socket), or in
state `07`, counts as a listener. IPv6 addresses are rendered
in compressed form via the `ipaddress` module; the wildcards
normalize to `0.0.0.0` and `::`.

The watcher files two declared signals:

| Signal | Fires when |
|--------|------------|
| `exposed_listener` | A new listener is bound to a wildcard address (`0.0.0.0` or `::`) or to a port below 1024 (high severity) |
| `new_listener` | Any other new listener appears — a specific address and a port at or above 1024 (medium severity) |

A new listener files once and is absorbed into the baseline,
even when the `high_only` tunable suppressed its medium alert.
Listeners that vanish leave the state silently, so a listener
that comes back files again.

Run one pass:

```bash
python3 port_watch.py
# one alert payload per line on stdout; state in
# .port-watch-state.json next to the script
```

Or try it anywhere by feeding it a readings file instead of
live sockets:

```bash
python3 port_watch.py --readings readings.json
{"detail": {"addr": "0.0.0.0", "port": 8080, "proto": "tcp"}, "sensor": "port_watch", "severity": "high", "signal": "exposed_listener", "title": "new exposed listener tcp 0.0.0.0:8080"}
```

A readings file is one JSON object:

```json
{"now": 1792375113.0,
 "listeners": [{"proto": "tcp", "addr": "127.0.0.1", "port": 22},
               {"proto": "udp", "addr": "0.0.0.0", "port": 53}]}
```

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and how
to turn this example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Light mode

For a Pi Light install, tune it down with the tunables the code
actually implements: raise `poll_interval_sec` from 120 to
600, and set `high_only` to true. On a quiet Pi only the
street-facing doors then file — wildcard and low-port
listeners — and the medium chatter is absorbed into the
baseline without ever waking anyone.
