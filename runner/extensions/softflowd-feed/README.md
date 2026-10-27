# Softflowd Feed — an example Homing Pigeon extension

A sense from the network side of the house, and the one
example here that is not a file tailer. softflowd watches an
interface and exports flow records as NetFlow over UDP;
there is no file on the box to read. So this producer *is*
the collector: each pass it binds a UDP socket, listens for
one short window, decodes what arrived into flow records,
and decides over them. Flows are all it knows — no
processes, no files, no host truth — and no alert it files
claims any.

Point softflowd at the collector with its `-n` option; the
producer's `listen_addr` tunable defaults to
`127.0.0.1:2055`:

```bash
softflowd -i eth0 -n 127.0.0.1:2055 -v 9
python3 softflowd_feed.py
# one alert payload per line on stdout; state in
# .softflowd-feed-state.json next to the script
```

The default is deliberately a loopback high port. A high
port (1024 and up) needs no privilege to bind, so the
producer runs as the ordinary user the runner runs as. The
alternatives are the operator's choice, in the open:
`listen_addr` can name any other high port (a `127.0.0.1:8888`
style address, when 2055 is already taken by another
collector), or the producer can be run as root — or with
`CAP_NET_BIND_SERVICE` — to bind a low port such as 514 if a
site's exporters are already configured to send there. What
the default will not do is require that privilege silently.

## Signals

| Signal | Fires when |
|--------|------------|
| `flow_new_external_peer` | A flow's destination is an external address — not private, loopback, link-local, or multicast per the `ipaddress` module, and not covered by the `allowlist` tunable — that the state has never seen before (info severity; files once per peer, and the peer list is bounded by `max_known_peers`, oldest evicted first) |
| `flow_high_volume` | A single flow carried at least `high_volume_bytes` bytes (medium severity; files once per flow) |
| `flow_long_lived` | A single flow lasted at least `long_lived_sec` seconds from first packet to last (info severity; files once per flow) |

A flow's episode identity is its source, destination,
ports, protocol, and first-packet time; replaying the same
flow against the returned state files nothing twice. The
filed-flow memory is bounded by `max_filed_flows` the same
way the peer memory is.

## Tunables

| Tunable | Default | What it does |
|---------|---------|--------------|
| `listen_addr` | `127.0.0.1:2055` | The `host:port` the collector binds for one window per pass |
| `collect_window_sec` | 10 | How long each pass listens before deciding over what arrived |
| `max_datagrams` | 1000 | Hard cap on datagrams decoded in one pass, however busy the exporter |
| `poll_interval_sec` | 60 | The cost knob: how often a pass runs |
| `high_volume_bytes` | 50000000 | The `flow_high_volume` threshold, in bytes on one flow |
| `long_lived_sec` | 3600 | The `flow_long_lived` threshold, first packet to last |
| `allowlist` | `[]` | Destination addresses or CIDRs (for example `["8.8.8.0/24"]`) that never file as new external peers |
| `max_known_peers` | 1024 | Bound on remembered external peers |
| `max_filed_flows` | 1024 | Bound on remembered filed flows |

`high_volume_bytes` defaults to 50 MB rather than 100 MB on
purpose: on a home connection a single 50 MB flow is already
the interesting shape — a backup leaving, a big upload, a
bulk download by something new — while 100 MB would let most
of those pass unremarked on the theory that they might be
video. They might be; the threshold is a tunable, and an
operator who wants only the truly large can raise it.

## What is decoded, and what is not

The decoder is a subset, and its boundary is stated here
rather than implied. NetFlow **v5 is decoded complete**:
the header and its fixed 48-byte records, timestamps
converted from the header's `unix_secs` and `sysUpTime`.
NetFlow **v9** is decoded from the header, template
flowsets, and data flowsets — but a data record is decoded
only when every field it uses is in the known set
(`IN_BYTES`, `IN_PKTS`, `PROTOCOL`, `TCP_FLAGS`,
`L4_SRC_PORT`, `IPV4_SRC_ADDR`, `L4_DST_PORT`,
`IPV4_DST_ADDR`, `LAST_SWITCHED`, `FIRST_SWITCHED`,
`IPV6_SRC_ADDR`, `IPV6_DST_ADDR`). A record with any other
field is skipped and counted in the readings'
`skipped_records`; fields are positional, so decoding the
rest anyway would misread every following byte. **IPFIX**
(version 10) gets the same treatment, with one addition: a
template field carrying the enterprise bit (and its private
enterprise number) marks that template's records
skipped-and-counted, never misdecoded. Templates live for
one pass only — a data flowset can precede its template
within the pass, and across passes softflowd re-sends
templates periodically, so re-learning is correct.

What is **not** decoded, by design: option templates (v9 and
IPFIX), sampling metadata, SCTP associations, and the long
tail of IPFIX information elements outside the known set —
records using them are the skipped-and-counted ones above.
Where a format carries switched times (v5, v9) they are
converted with the header's `unix_secs` and `sysUpTime`;
IPFIX carries no such anchor, so its flows take the collect
time for both first and last and never report a fabricated
duration. Malformed or truncated datagrams never raise: an
incomplete record decodes to nothing.

Or try it anywhere against fixtures, with no collector at
all — a readings file is `{"now": ..., "flows": [...],
"skipped_records": 0}`:

```bash
python3 softflowd_feed.py --readings readings.json
{"detail": {"dst": "8.8.8.8", "dst_port": 443, "proto": 6, "src": "192.168.1.20"}, "sensor": "softflowd_feed", "severity": "info", "signal": "flow_new_external_peer", "title": "first flow to new external peer 8.8.8.8 (proto 6, port 443)"}
```

Alert payloads are unsigned sense alerts; signing and
delivery follow the standard senses flow. The full extension
walkthrough — manifest fields, the versioning contract,
sensor binding, and how to turn this example into your own
package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

Footprint: softflowd itself measured ~7 MB RSS at ~0% CPU
in the collector comparison — the lightest always-on
collector measured. The feed's own cost is one bound socket
and a 10-second listen per pass.

## Light mode

This feed is already the light option — it is the Pi Light
network sense's natural supplier. For a Pi Light install,
tune it down with its tunables:
raise `poll_interval_sec` from 60 to 600 and lengthen
`collect_window_sec` only if the Pi's exporter is chatty
enough to need it, and raise `high_volume_bytes` so only
genuinely bulk flows wake anyone on a small pipe.
