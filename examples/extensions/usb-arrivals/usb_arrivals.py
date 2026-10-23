#!/usr/bin/env python3
"""USB Arrivals: a Homing Pigeon user extension (example sense).

Notices devices arriving on the machine's buses -- the plug-
and-check habit from the hardware lab testbed years, where a
bench of GPIB instruments and serial gear changed shape every
time someone swapped a cable. It watches the USB bus and the
serial ports, learns what is plugged in on its first pass, and
files each later arrival as a sensor alert for the Oracle.

Each alert names one of the signals declared in extension.json:

- device_arrived   a device id not seen before arrived on a
                   watched bus
- storage_arrived  a NEW device whose USB device class is 08
                   (mass storage) -- the stronger statement,
                   filed INSTEAD of device_arrived

Departures file nothing: no departure signal is declared, so
a device leaving drops out of the state silently, and if it
is plugged back in later that is a fresh arrival.

The machinery is deliberately boring, in the Pi Health
example's shape. read_live() is the only function that touches
the machine; it returns one readings dict, and decide() --
readings plus manifest plus last pass's state, out come alerts
and the new state -- is pure, so the whole decision surface is
testable on a machine with nothing plugged in at all. The
current time arrives as readings["now"]; decide() never reads
a clock.

Live reads are Linux-only and capability-based -- a source
the machine does not expose yields absent data, never an
error:

- USB: /sys/bus/usb/devices/*/ -- idVendor, idProduct,
  product (the description) and bDeviceClass. A device's id
  is "<vendor>:<product>"; identical twin devices share that
  id and are indistinguishable at this level, so two of them
  are one entry.
- Serial: /dev/serial/by-id names when present (the id is
  the by-id name), else serial tty names from /sys/class/tty
  (ttyUSB*, ttyACM*, ttyAMA*, ttyS*). The device_class is
  "serial".

Windows and macOS expose no stdlib-reachable equivalent of
that sysfs walk, so read_live() returns an empty device list
there -- a quiet no-op pass, never an error. Fixture mode
(--readings) is the path on those platforms.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extensions.md, "Local delivery").

--readings FILE reads a readings dict from a JSON file instead
of the machine: the way to try the sense (and test it) against
known readings, on any box at all.
"""
import argparse
import glob
import json
import os
import sys
import time


def _is_number(value):
    """A finite int or float, never a bool.

    Infinity and NaN are floats, and an integer too large for a float
    is an int, but none of them is a usable tunable: inf once made a
    threshold that never trips (or always trips), and int(inf) is an
    OverflowError. Each reads as "not a number" so the documented
    default applies.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        f = float(value)
    except (OverflowError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf"))


def _tunables(manifest):
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    return tunables if isinstance(tunables, dict) else {}


def _sensor_name(manifest):
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "usb_arrivals"
    return sensor


def _kinds(manifest):
    kinds = _tunables(manifest).get("kinds")
    if isinstance(kinds, list):
        cleaned = [k for k in kinds if isinstance(k, str) and k]
        if cleaned:
            return cleaned
    return ["usb", "serial"]


def _learn_first_pass(manifest):
    value = _tunables(manifest).get("learn_first_pass")
    return value if isinstance(value, bool) else True


# --- the live reads: the only platform-touching code -----------------

def _read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _read_usb_devices():
    devices = []
    seen_ids = set()
    try:
        dirs = sorted(glob.glob("/sys/bus/usb/devices/*/"))
    except OSError:
        return devices
    for dev_dir in dirs:
        vendor = _read_text(os.path.join(dev_dir, "idVendor"))
        product_id = _read_text(os.path.join(dev_dir, "idProduct"))
        if not vendor or not product_id:
            continue
        dev_id = f"{vendor}:{product_id}"
        if dev_id in seen_ids:
            # Identical twin devices share vendor:product and
            # are indistinguishable at this level: one entry.
            continue
        seen_ids.add(dev_id)
        devices.append({
            "id": dev_id,
            "kind": "usb",
            "description": _read_text(os.path.join(dev_dir, "product")),
            "device_class": _read_text(
                os.path.join(dev_dir, "bDeviceClass")),
        })
    return devices


def _read_serial_devices():
    devices = []
    seen_ids = set()
    covered_ttys = set()
    by_id_dir = "/dev/serial/by-id"
    try:
        names = sorted(os.listdir(by_id_dir))
    except OSError:
        names = []
    for name in names:
        if not name or name in seen_ids:
            continue
        seen_ids.add(name)
        try:
            target = os.path.basename(
                os.path.realpath(os.path.join(by_id_dir, name)))
        except OSError:
            target = ""
        if target:
            covered_ttys.add(target)
        devices.append({
            "id": name,
            "kind": "serial",
            "description": name,
            "device_class": "serial",
        })
    try:
        tty_names = sorted(os.listdir("/sys/class/tty"))
    except OSError:
        tty_names = []
    for name in tty_names:
        if not (name.startswith("ttyUSB") or name.startswith("ttyACM")
                or name.startswith("ttyAMA") or name.startswith("ttyS")):
            continue
        if name in seen_ids or name in covered_ttys:
            continue
        seen_ids.add(name)
        devices.append({
            "id": name,
            "kind": "serial",
            "description": name,
            "device_class": "serial",
        })
    return devices


def read_live(manifest):
    """One live snapshot of the machine's buses, as a readings dict.

    readings = {"now": epoch float, "devices": [{"id", "kind",
    "description", "device_class"}]}. Capability-based: a bus,
    tool or file the machine does not expose contributes no
    entries, and no read here ever raises. Live reads are
    Linux-only; everywhere else the device list is empty.
    """
    readings = {"now": time.time(), "devices": []}
    if not sys.platform.startswith("linux"):
        return readings
    kinds = _kinds(manifest)
    devices = []
    if "usb" in kinds:
        devices.extend(_read_usb_devices())
    if "serial" in kinds:
        devices.extend(_read_serial_devices())
    readings["devices"] = devices
    return readings


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"learned": False, "seen": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    learned = state.get("learned")
    if not isinstance(learned, bool):
        learned = False
    seen = state.get("seen")
    if not isinstance(seen, dict):
        seen = {}
    cleaned = {}
    for dev_id, info in seen.items():
        if not isinstance(dev_id, str) or not dev_id:
            continue
        if not isinstance(info, dict):
            info = {}
        cleaned[dev_id] = {
            "kind": info.get("kind") if isinstance(
                info.get("kind"), str) else "",
            "device_class": info.get("device_class") if isinstance(
                info.get("device_class"), str) else "",
            "description": info.get("description") if isinstance(
                info.get("description"), str) else "",
        }
    return {"learned": learned, "seen": cleaned}


def _clean_devices(readings):
    if not isinstance(readings, dict):
        return []
    raw = readings.get("devices")
    if not isinstance(raw, list):
        return []
    devices = []
    seen_ids = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        dev_id = entry.get("id")
        if not isinstance(dev_id, str) or not dev_id or dev_id in seen_ids:
            continue
        seen_ids.add(dev_id)
        devices.append({
            "id": dev_id,
            "kind": entry.get("kind") if isinstance(
                entry.get("kind"), str) and entry.get("kind") else "",
            "description": entry.get("description") if isinstance(
                entry.get("description"), str) else "",
            "device_class": entry.get("device_class") if isinstance(
                entry.get("device_class"), str) else "",
        })
    return devices


def _is_storage(device):
    return device.get("device_class", "").strip() == "08"


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"] (and this sense's decisions do not even
    need it; it is carried for the uniform readings shape).

    The learn pass (learn_first_pass, the default) absorbs the
    devices present quietly and files nothing: what was already
    plugged in when the sense started is the baseline, not
    news. After that, a device id not in the state files
    device_arrived -- or storage_arrived instead when its
    device class is 08. Departures drop out of the state
    silently, so a device that leaves and returns files again.
    """
    state = _clean_state(state)
    sensor = _sensor_name(manifest)
    devices = _clean_devices(readings)
    current = {
        d["id"]: {"kind": d["kind"], "device_class": d["device_class"],
                  "description": d["description"]}
        for d in devices
    }
    if not state["learned"]:
        if _learn_first_pass(manifest):
            return [], {"learned": True, "seen": current}
        # No learn pass: fall through and evaluate every present
        # device against the (empty) baseline.
        state = {"learned": True, "seen": {}}
    alerts = []
    for device in sorted(devices, key=lambda d: d["id"]):
        if device["id"] in state["seen"]:
            continue
        if _is_storage(device):
            detail = {"id": device["id"], "kind": device["kind"],
                      "description": device["description"],
                      "device_class": device["device_class"]}
            alerts.append({
                "sensor": sensor, "signal": "storage_arrived",
                "severity": "medium",
                "title": f"USB storage device {device['id']} arrived"
                         + (f": {device['description']}"
                            if device["description"] else ""),
                "detail": detail})
        else:
            detail = {"id": device["id"], "kind": device["kind"],
                      "description": device["description"]}
            alerts.append({
                "sensor": sensor, "signal": "device_arrived",
                "severity": "info",
                "title": f"device {device['id']} arrived"
                         + (f": {device['description']}"
                            if device["description"] else ""),
                "detail": detail})
    return alerts, {"learned": True, "seen": current}


# --- delivery and the main loop, in the Lab Results shape -------------

def _deliver_local(alerts, args):
    """Sign and deliver each alert to a runner on this machine.

    Returns how many alerts were delivered, or None when local
    delivery is not set up (the reason is printed). Uses the
    runner's own producer helpers, so the envelope and signature
    are the contract's, not a re-implementation.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(
        os.path.join(here, "..", "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from runner import extensions as hp_extensions
    except ImportError as e:
        print(f"usb-arrivals: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"usb-arrivals: no signing secret in ${args.secret_env}; "
              f"set it to this sense's key secret", file=sys.stderr)
        return None
    delivered = 0
    for alert in alerts:
        payload = hp_extensions.build_sensor_alert(
            alert["sensor"], alert["severity"], alert["title"],
            key_id=args.key_id, signal=alert.get("signal"),
            detail=alert.get("detail"))
        try:
            if args.local_port:
                hp_extensions.send_local_signal(
                    payload, secret, port=args.local_port)
                where = f"127.0.0.1:{args.local_port}"
            else:
                where = hp_extensions.drop_local_signal(
                    args.local_dir, payload, secret)
        except (OSError, ValueError) as e:
            print(f"usb-arrivals: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"usb-arrivals: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="USB Arrivals extension watcher: read the "
                    "machine's buses once and file sensor alert "
                    "payloads for devices that newly arrived.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".usb-arrivals-state.json"),
                    help="state file (default: .usb-arrivals-state.json "
                         "next to this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the machine (trying the sense "
                         "against known readings, on any box)")
    ap.add_argument("--local-dir", default=None,
                    help="runner base dir: deliver alerts locally "
                         "(signed, into its local inbox) instead of "
                         "printing payloads")
    ap.add_argument("--local-port", type=int, default=None,
                    help="with --local-dir: push to the runner's "
                         "loopback listener on this port instead of "
                         "dropping files")
    ap.add_argument("--key-id", default="",
                    help="key id this sense signs as (its "
                         "sensors.<name>.key_id in the runner config)")
    ap.add_argument("--secret-env", default="HOMING_PIGEON_SENSOR_SECRET",
                    help="environment variable holding the signing "
                         "secret (default: HOMING_PIGEON_SENSOR_SECRET)")
    args = ap.parse_args(argv)
    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"usb-arrivals: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"usb-arrivals: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    else:
        readings = read_live(manifest)
    state = _fresh_state()
    try:
        with open(args.state, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        pass
    alerts, state = decide(readings, manifest, state)
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so the
            # next pass reports these arrivals again.
            print(f"usb-arrivals: {len(alerts) - delivered} of "
                  f"{len(alerts)} alert(s) not delivered; state not "
                  f"saved, will retry next pass", file=sys.stderr)
            return 2
    else:
        for alert in alerts:
            print(json.dumps(alert, sort_keys=True))
    try:
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(state, fh, sort_keys=True)
    except OSError as e:
        print(f"usb-arrivals: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
