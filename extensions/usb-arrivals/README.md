# USB Arrivals — an example Homing Pigeon extension

A sense for the plug-and-check habit: the hardware lab testbed
years, when a bench of GPIB instruments and serial gear changed
shape every time someone swapped a cable. It watches the
machine's USB bus and serial ports, learns what is plugged in
on its first pass, and tells the Oracle when something new
arrives.

The watcher files two declared signals:

| Signal | Fires when |
|--------|------------|
| `device_arrived` | A device id not in the learned baseline appears on a watched bus (`info`) |
| `storage_arrived` | A new device whose USB device class is `08` (mass storage) appears — filed instead of `device_arrived` (`medium`) |

Departures file nothing — no departure signal is declared.
A device that leaves drops out of the state silently, so
plugging it back in files a fresh arrival.

Live reads are Linux-only. USB devices come from
`/sys/bus/usb/devices/*/` (`idVendor`, `idProduct`,
`product`, `bDeviceClass`); a device's id is
`<vendor>:<product>`, and identical twin devices share that
id and are indistinguishable at this level — two of them are
one entry. Serial devices come from `/dev/serial/by-id`
names when present (the id is the by-id name), else serial
tty names from `/sys/class/tty` (`ttyUSB*`, `ttyACM*`,
`ttyAMA*`, `ttyS*`), with `device_class` `"serial"`. Every
read is guarded: a bus or file the machine does not expose
contributes nothing and is never an error. On Windows and
macOS there is no live source — `read_live` returns an empty
device list and the pass is a quiet no-op; fixture mode
(`--readings`) is the path on those platforms, and works
everywhere.

Run one pass:

```bash
python3 usb_arrivals.py
# one alert payload per line on stdout; state in
# .usb-arrivals-state.json next to the script
```

Or try it anywhere by feeding it a readings file instead of
live reads:

```bash
python3 usb_arrivals.py --readings readings.json
```

A readings file is one JSON object:

```json
{"now": 1792375113.0,
 "devices": [{"id": "0781:5567", "kind": "usb",
              "description": "Cruzer Blade",
              "device_class": "08"}]}
```

Alert payloads are unsigned sense alerts on stdout; signing
and delivery follow the standard senses flow. With
`--local-dir <runner base dir> --key-id <its key id>` (and
`HOMING_PIGEON_SENSOR_SECRET` set to this sense's key) it
delivers locally instead. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and
how to turn this example into your own package — is in
[docs/extensions.md](../../../docs/extensions.md).

### Other tunables

`learn_first_pass` (default true) makes the first pass absorb everything currently plugged in as the baseline without filing; set it false to file every present device as an arrival on the first pass.

## Light mode

Two tunables in `extension.json` are the whole cost of this
sense, and Light mode is just those knobs turned down:

- `poll_interval_sec`: `300` by default; `1800` in Light
  mode. Arrivals on a lab bench are not urgent to the second,
  and a bus walk every half hour costs almost nothing.
- `kinds`: `["usb", "serial"]` by default; `["usb"]` in
  Light mode, dropping the serial walk entirely and watching
  only the USB bus.

Nothing else changes: same signals, same state file, same
delivery. On a Pi Light install this sense runs
deterministically with no model in the loop.
