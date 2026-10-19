# Wire Arrivals — an example Homing Pigeon extension

A sense for people who watch a wire. It reads the machine's
ARP/neighbor table — the small, honest census of who is on
this LAN, by IP and by hardware address — and the Oracle
learns when a stranger shows up and when a known address
suddenly answers from different hardware, which is the
classic ARP-spoofing tell.

The table comes from `/proc/net/arp` on Linux; when that file
is absent the watcher falls back to `ip neigh show`, or to
`arp -a` when `ip` is not installed. Honest coverage: on a
platform with none of those files or tools the table reads
empty and the sense files nothing — it never guesses. The
table is also only the neighbors this machine has recently
talked to or heard from, not a scan of the subnet: a device
that has been silent may not be in it, and this sense reports
the table, not the wire.

The watcher files two declared signals:

| Signal | Fires when |
|--------|------------|
| `new_neighbor` | A MAC address not in state appears in the neighbor table (medium) |
| `mac_moved` | An IP address in state now answers from a different MAC address (high) |

With the `learn_first_pass` tunable on (the default), the
very first pass is a baseline: the whole table is absorbed
and nothing files, so installing the sense on a busy LAN
does not open by reporting the entire LAN. After that, state
absorbs every reading — a new IP under a MAC already known
is recorded silently, because no signal exists for it — and
a table that matches state files nothing. When one entry
triggers `mac_moved` it files only `mac_moved`, not also
`new_neighbor` for the new MAC: the stronger tell wins, and
the new MAC is still absorbed into state. The pass's state
lives in `.wire-arrivals-state.json` next to the script.

Run one pass:

```bash
python3 wire_arrivals.py --local-dir ~/.homing-pigeon --key-id wire-key
# HOMING_PIGEON_SENSOR_SECRET holds the wire_arrivals sense's key
```

Or try it anywhere by feeding it a readings file instead of
the live table:

```bash
python3 wire_arrivals.py --readings readings.json
# one alert payload per line on stdout
```

A readings file is one JSON object with `now` as epoch
seconds and one record per neighbor:

```json
{"now": 1792375113.0,
 "neighbors": [{"ip": "192.168.1.1", "mac": "aa:bb:cc:dd:ee:ff",
                "iface": "eth0"}]}
```

Alert payloads are unsigned sense alerts when printed;
signing and delivery follow the standard senses flow. The
full extension walkthrough — manifest fields, the versioning
contract, sensor binding, and how to turn this example into
your own package — is in
[docs/extensions.md](../../../docs/extensions.md).

## Light mode

Two knobs tune this sense down for a Pi Light install, and
both are ones the code actually reads:

- `poll_interval_sec`: raise it from the default 120 to 900 —
  a home LAN's census changes slowly, and fifteen minutes is
  still fast enough to catch a stranger settling in.
- `ifaces`: name just the one LAN interface that matters
  (for example `["eth0"]`) instead of watching every
  interface the box has, so the table each pass absorbs and
  diffs stays small.
