# Zeek Feed — an example Homing Pigeon extension

A sense fed by [Zeek](https://zeek.org/), the network
traffic analyzer. Zeek watches the wire so this sense does
not have to: it tails the `conn.log` and `dns.log` files
Zeek writes and files the two shapes in them that are worth
waking the Oracle for — a crowd of external responders the
box has never talked to before, and DNS queries shaped like
tunneling or exfiltration. Everything else Zeek records,
including connection rows with odd services or protocols,
files nothing: oddity is normal on a real network, and a
sense that files it trains its operator to ignore it.

Zeek's default log shape is TSV whose column order is
stated in the file itself. `#fields` header lines name the
columns in force and can reappear mid-file when Zeek
rotates or restarts — so the parser is header-driven: each
data line is parsed against the field list in force at that
point, and the reader state carries each file's current
field list beside its inode and offset. Lines starting with
`{` are Zeek's JSON output (the `Ascii::use_json` policy)
and are parsed with the same field names; the two shapes
can even mix across files. The `fixtures/` directory
carries a trimmed real `conn.log` capture, a crafted
`dns.log` built from the documented `dns.log` field set,
and a small JSON-lines sample.

"External" is the stdlib `ipaddress` module's word: a
responder that is private, loopback, link-local or
multicast is not external, and neither is one covered by
the `allowlist` tunable (exact addresses or CIDR networks).

## Signals

| Signal | Fires when |
|--------|------------|
| `zeek_new_external_peers` | At least the `new_peer_threshold` tunable (default 10) distinct external responders (`id.resp_h` from `conn.log`) are first seen inside the trailing `window_sec` (default 600). Medium severity. State remembers peers already seen, so a familiar responder never counts again; filing consumes the accumulation, so a refile means a fresh batch of new peers |
| `zeek_dns_anomaly` | A `dns.log` query is at least `query_length_threshold` characters (default 50), has six or more labels, or uses a TXT, NULL, KEY or ANY qtype. Medium severity. Files once per `(query, responder)` episode |

## Tunables

| Tunable | Default | Means |
|---------|---------|-------|
| `log_paths` | `/opt/zeek/logs/current/conn.log`, `/opt/zeek/logs/current/dns.log` | The Zeek logs to tail; point it at wherever this install actually writes them |
| `poll_interval_sec` | 60 | The cadence to run the pass on; advisory, the runner never runs sense code |
| `window_sec` | 600 | The trailing window first sightings accumulate in |
| `new_peer_threshold` | 10 | Distinct first-seen external responders inside the window that file |
| `query_length_threshold` | 50 | DNS query length that counts as anomalous |
| `allowlist` | `[]` | Addresses or CIDR networks never counted as external peers |
| `seen_peers_cap` | 10000 | Bound on remembered peers (and filed DNS pairs); the oldest entries are evicted first |

Run one pass:

```bash
python3 zeek_feed.py
# one alert payload per line on stdout; state (including the
# reader offsets and per-file field lists) in
# .zeek-feed-state.json next to the script
```

Or try it anywhere against fixtures, with no live Zeek at
all: a readings file (`{"now": ..., "events": [...]}`), or a
whole fixture log parsed from offset 0:

```bash
python3 zeek_feed.py --readings readings.json
python3 zeek_feed.py --log-file fixtures/dns.log
```

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and how
to turn this example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Footprint

Zeek itself is the collector, and Zeek is heavy: measured
~230 MB RSS idle-with-light-traffic on the project's test
VM (see the collector comparison in the research notes) —
the heavyweight of the slate. This producer is a file
tailer and costs almost nothing; the footprint line belongs
to the daemon feeding it. Budget for Zeek as an
environment-bound choice: a busy or unusual network is
exactly where its record is worth the RAM, and a quiet box
is where it is not.

## Light mode

For a Pi Light install: leave this feed **off**. It is
opt-in and NEVER a default — ~230 MB next to the local
model on a small Pi is the difference between headroom and
swap, and no producer tunable shrinks the Zeek daemon
itself. If an operator deliberately runs Zeek beside a Pi
anyway, its knobs still trim the
producer's own wakefulness: raise `poll_interval_sec` from
60 to 600, point `log_paths` at the single log actually
kept (for example just `conn.log`), and raise
`new_peer_threshold` — at 25, only a real crowd of new
external peers files.
