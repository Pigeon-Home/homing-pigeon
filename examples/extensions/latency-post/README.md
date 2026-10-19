# Latency Post — an example Homing Pigeon extension

A sense from the network-engineering side of the house. It
keeps post on reachability: periodic timed TCP probes to the
default gateway and to targets you configure, so the Oracle
learns when something stopped answering, and when something
that still answers has gone slow against its own recent
history.

The probes are TCP connections only. ICMP is deliberately not
used: raw ICMP needs privilege a sense should not require, and
a TCP handshake already proves the host answered and times it.
That produces one documented asymmetry. The gateway is probed
for reachability on the `gateway_port` tunable (default 53),
so a connection refused — an RST came back, the host is alive
— still counts as a successful gateway probe with a latency.
A configured target is probed for its service, so a refusal
there counts as down: `ok` is false and the reason is
`refused`. Timeouts and unreachable routes count as down for
both. Platform coverage: the gateway is read from
`/proc/net/route`, so it is Linux-only; configured targets are
plain TCP connects and work anywhere, and on a machine with no
`/proc/net/route` the gateway probe is simply absent.

The watcher files two declared signals:

| Signal | Fires when |
|--------|------------|
| `target_down` | A probe fails and the target was not already reported down (high severity; recovery clears the flag silently — there is no recovery signal) |
| `latency_spike` | A probe's latency rises above both the `spike_ms` tunable (default 250) and `spike_factor` (default 3) times the median of the target's last samples, with at least 3 prior samples (medium severity) |

A down target files once and stays quiet while it stays down.
A spike files once, and an in-band reading clears the spike
flag quietly so the next spike files fresh. Every successful
latency joins the target's sample history, capped at the last
20.

Run one pass:

```bash
python3 latency_post.py
# one alert payload per line on stdout; state in
# .latency-post-state.json next to the script
```

Or try it anywhere by feeding it a readings file instead of
live probes:

```bash
python3 latency_post.py --readings readings.json
{"detail": {"error": "timeout", "target": "192.0.2.10:443"}, "sensor": "latency_post", "severity": "high", "signal": "target_down", "title": "target 192.0.2.10:443 stopped answering"}
```

A readings file is one JSON object:

```json
{"now": 1792375113.0,
 "probes": [{"target": "192.0.2.10:443", "ok": true, "latency_ms": 18.4},
            {"target": "192.168.1.1:53", "ok": false, "latency_ms": null}]}
```

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and how
to turn this example into your own package — is in
[docs/extensions.md](../../../docs/extensions.md).

## Light mode

For a Pi Light install, tune it down with the tunables the code
actually implements: raise `poll_interval_sec` from 60 to 600
(a slower cadence also means fewer latency samples are taken),
and leave `targets` empty with `include_gateway` true, so the
only probe each pass is the gateway check — one small TCP
connect every ten minutes, and nothing else.
