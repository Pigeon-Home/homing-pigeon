# Airwaves — an example Homing Pigeon extension

A sense for the wireless neighborhood — the Pi's wireless
neighborhood watch. It reads the Wi-Fi neighborhood the
platform already sees, and the box's own link, and files the
wireless analogs of the wired spoofing tells: a familiar SSID
radiating from a new radio, a known access point suddenly
offering weaker security, a neighbor vanishing, your own link
quietly roaming or fading.

The watcher files four declared signals:

| Signal | Fires when |
|--------|------------|
| `new_access_point` | A BSSID never seen before appears, broadcasting an SSID the neighborhood has not known (`medium`) |
| `evil_twin_suspect` | A known SSID appears from a new BSSID, or a known BSSID/SSID drops to a lower security rank than its baseline (`high`) |
| `access_point_gone` | A known AP stays absent for `gone_after_scans` (default 3) successful scans (`info`) |
| `link_degraded` | The box's own link roams to a different BSSID, or its signal falls by `link_drop_db` (default 10) or more from its reference (`medium`) |

The first pass learns the neighborhood quietly
(`learn_first_pass`, default true). A pass with no scan data
(`scan_ok` false) files nothing and changes nothing — no data
is not an absence, so missed-scan counters do not advance.
Every successful scan is evaluated before it is absorbed, so
a security downgrade fires before the baseline learns to
expect it.

Scan sources, in order, all guarded — a missing tool is a
quiet no-op pass, never an error: NetworkManager's cached
results via `nmcli device wifi list` (never `--rescan`; its
percentage signal is converted to approximate dBm as
`pct / 2 - 100`), then a cached `iw dev <iface> scan dump`
when one exists; the box's own link comes from
`iw dev <iface> link`. The `iface` tunable names the Wi-Fi
interface; empty means the first interface `iw dev` names.
Live reads are therefore a Linux story (a box with neither
`nmcli` nor `iw` simply has nothing to report); fixture mode
(`--readings`) works on any platform, including Windows and
macOS. Security strings are ranked by `security_rank`:
open 0, WEP 1, WPA/PSK 2, WPA2 3, WPA3/SAE 4.

BLE is out of scope. There is no clean stdlib-reachable BLE
advertisement source, so this sense says nothing about
Bluetooth at all.

Run one pass:

```bash
python3 airwaves.py
# one alert payload per line on stdout; state in
# .airwaves-state.json next to the script
```

Or try it anywhere by feeding it a readings file instead of
live reads:

```bash
python3 airwaves.py --readings readings.json
```

A readings file is one JSON object:

```json
{"now": 1792375113.0, "scan_ok": true,
 "scan": [{"bssid": "AA:BB:CC:DD:EE:01", "ssid": "HomeNet",
           "channel": 6, "signal_dbm": -55, "security": "WPA2"}],
 "link": {"bssid": "AA:BB:CC:DD:EE:01", "ssid": "HomeNet",
          "signal_dbm": -55}}
```

Alert payloads are unsigned sense alerts on stdout; signing
and delivery follow the standard senses flow. With
`--local-dir <runner base dir> --key-id <its key id>` (and
`HOMING_PIGEON_SENSOR_SECRET` set to this sense's key) it
delivers locally instead. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and
how to turn this example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Light mode

Scan cadence is the cost knob, and it leads the Light mode:
`poll_interval_sec` is `300` by default and `1800` in Light
mode — the neighborhood changes slowly, and reading the
platform's cached results every half hour is enough to catch
a new radio, a vanished one, and a fading link. That is the
only knob Light mode turns; `gone_after_scans` (3) and
`link_drop_db` (10) keep their defaults, since at a slower
cadence three missed scans already mean a long absence.

The boundary, stated plainly: this sense is a read-only
consumer of the platform's own scan results — it never
associates to a network, never deauthenticates anyone, and
never injects frames. On a Pi Light install it runs
deterministically with no model in the loop; the `high`
evil-twin signal is the one that wakes the Oracle's brief.
