#!/usr/bin/env python3
"""Pi Health: a Homing Pigeon user extension (example sense).

Watches the health of the machine it runs on -- CPU/SoC
temperature, undervoltage and throttling state, disk usage,
memory pressure -- and files what it finds as sensor alerts
for the Oracle. Born as the Pi Light showcase sense, it runs
on any machine: a Raspberry Pi exposes the fullest picture
(it alone reports undervoltage), a laptop exposes temperature,
disk and memory where its OS offers them, and a machine that
exposes almost nothing still gets its disk watched. It runs
happily on a box with no local model anywhere in the loop.
Its two serious signals are high severity, so on a Pi Light
install a hot or starving board wakes the (deterministic)
Oracle, which files its brief from the alert alone -- and the
same extension on a laptop with a model-backed Oracle yields
the same signals, which is what makes the pair useful for
A/B testing across platforms and Oracle configurations.

Each alert names one of the signals declared in extension.json:

- board_overheating      the SoC is at or over the temp_high_c
                         tunable (default 80C)
- undervoltage_detected  the board's throttled bitmask shows
                         undervoltage or throttling, now or
                         earlier this boot -- the classic
                         too-weak power supply signature
- disk_pressure          a watched mount is at or over the
                         disk_high_pct tunable (default 90%)
- memory_pressure        available memory is at or under the
                         mem_avail_low_pct tunable (default 10%)

The machinery is deliberately boring, in the Lab Results
example's shape. read_board() is the only function that touches
the machine; it returns one readings dict, and decide() --
readings plus manifest plus last pass's state, out come alerts
and the new state -- is pure, so the whole decision surface is
testable on a machine that is not a Pi. A signal fires once
when its condition appears (or its reading changes), not on
every pass: a board that stays hot files one alert, and files
again when the reading moves.

Sources, all optional and capability-based -- a source the
machine does not expose reports None, which never yields a
signal and is never an error:

- temperature: the Linux thermal sysfs
  (/sys/class/thermal/thermal_zone*/temp, millidegrees
  Celsius). A machine can expose several zones; the read
  prefers the zone whose type names the SoC or the CPU
  package ("cpu-thermal" on a Pi, "x86_pkg_temp" on Intel
  laptops), then any cpu/soc/pkg-flavoured type, then the
  first readable zone.
- throttled: `vcgencmd get_throttled` (the Pi firmware tool;
  Pi-only by nature -- absent everywhere else, where power
  simply has nothing to say)
- disk: the disk_mount tunable (default "/"), via
  shutil.disk_usage (portable)
- memory: available memory as a percent of the total --
  /proc/meminfo (MemAvailable over MemTotal) on Linux,
  os.sysconf physical/available pages on other POSIX
  systems, GlobalMemoryStatusEx on Windows

Run on the same machine as the runner, it delivers locally:
--local-dir <runner base dir> signs each payload with this
sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and signing
and delivery follow the standard senses flow.

--readings FILE reads a readings dict from a JSON file instead
of the machine: the way to try the sense (and test it) against
known readings, on any box at all.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

# The firmware's throttled bitmask (vcgencmd get_throttled):
# bits 0-3 are the state right now, bits 16-19 the same states
# latched since boot.
_UNDERVOLTAGE_NOW = 0x1
_THROTTLED_NOW = 0x4 | 0x8          # throttled, or frequency capped
_UNDERVOLTAGE_SINCE_BOOT = 0x10000
_THROTTLED_SINCE_BOOT = 0x40000 | 0x80000
_UNDERVOLTAGE_MASK = _UNDERVOLTAGE_NOW | _UNDERVOLTAGE_SINCE_BOOT
_THROTTLE_MASK = (_THROTTLED_NOW | _THROTTLED_SINCE_BOOT)


def _num(value):
    return "%g" % value


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# --- the live reads: the only platform-touching code -----------------

# Thermal zone types that name the SoC or the CPU package, in
# preference order: the Pi's SoC zone first, then Intel's
# package zone, then other SoC-flavoured names. A machine with
# several zones (most laptops) also exposes sensors for the
# motherboard, the wifi card, and so on; the package temperature
# is the one this sense means by "the board's temperature".
_TEMP_TYPE_PREFERENCE = (
    "cpu-thermal", "cpu_thermal",       # Raspberry Pi SoC
    "x86_pkg_temp",                     # Intel CPU package
    "soc_thermal", "soc-thermal",
)


def _read_temp_c():
    """SoC/CPU temperature in Celsius from the thermal sysfs.

    Every readable zone is collected with its type; the zone
    this sense reports is chosen by _TEMP_TYPE_PREFERENCE,
    then any cpu/soc/pkg-flavoured type, then the first
    readable zone. None when the sysfs exposes no zone at
    all (most non-Linux machines, some VMs).
    """
    try:
        paths = sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp"))
    except OSError:
        return None
    zones = []  # (zone type, temperature C) in sysfs order
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                temp = int(fh.read().strip()) / 1000.0
        except (OSError, ValueError):
            continue
        ztype = ""
        try:
            with open(os.path.join(os.path.dirname(path), "type"),
                      encoding="utf-8") as fh:
                ztype = fh.read().strip()
        except OSError:
            pass
        zones.append((ztype, temp))
    if not zones:
        return None
    for wanted in _TEMP_TYPE_PREFERENCE:
        for ztype, temp in zones:
            if ztype == wanted:
                return temp
    for ztype, temp in zones:
        low = ztype.lower()
        if "cpu" in low or "soc" in low or "pkg" in low:
            return temp
    return zones[0][1]


def _read_throttled():
    """The board's throttled bitmask as an int, or None.

    vcgencmd is the Pi firmware tool, so this source is
    Pi-only by nature. Its absence -- every other machine, or
    a Pi without the package -- is a normal case: the sense
    simply has nothing to say about power on that pass, and
    the undervoltage signal never fires there.
    """
    exe = shutil.which("vcgencmd")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "get_throttled"], capture_output=True,
                             text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"throttled=0x([0-9a-fA-F]+)", out.stdout or "")
    if not m:
        return None
    try:
        return int(m.group(1), 16)
    except ValueError:
        return None


def _read_disk_pct(mount):
    """Percent of `mount` in use, or None when unmeasurable."""
    try:
        usage = shutil.disk_usage(mount)
    except OSError:
        return None
    if usage.total <= 0:
        return None
    return round(100.0 * usage.used / usage.total, 1)


def _mem_avail_pct_meminfo():
    """MemAvailable as a percent of MemTotal from /proc/meminfo."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    found = {}
    for key in ("MemTotal", "MemAvailable"):
        m = re.search(rf"^{key}:\s+(\d+)", text, re.MULTILINE)
        if m:
            found[key] = int(m.group(1))
    total = found.get("MemTotal") or 0
    avail = found.get("MemAvailable")
    if avail is None or total <= 0:
        return None
    return round(100.0 * avail / total, 1)


def _mem_avail_pct_sysconf():
    """Available memory as a percent of the total, via os.sysconf.

    The fallback for POSIX systems without /proc/meminfo
    (macOS, the BSDs): physical pages against available pages.
    On those systems "available pages" counts free pages
    rather than Linux's cache-aware MemAvailable -- a blunter
    number, but a real one.
    """
    try:
        names = os.sysconf_names
        if "SC_PHYS_PAGES" not in names or "SC_AVPHYS_PAGES" not in names:
            return None
        total = os.sysconf("SC_PHYS_PAGES")
        avail = os.sysconf("SC_AVPHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return None
    if not _is_number(total) or not _is_number(avail) or total <= 0:
        return None
    return round(100.0 * avail / total, 1)


def _mem_avail_pct_windows():
    """Available memory as a percent of the total, on Windows.

    GlobalMemoryStatusEx via ctypes -- the standard library's
    way to ask Windows itself. None everywhere else.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes

        class _MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(status)):
            return None
        total = status.ullTotalPhys
        if total <= 0:
            return None
        return round(100.0 * status.ullAvailPhys / total, 1)
    except Exception:
        return None


def _read_mem_avail_pct():
    """Available memory as a percent of the total, or None.

    /proc/meminfo where it exists (Linux, with the best
    semantics), then Windows' own report, then the POSIX
    sysconf page counts (macOS, the BSDs).
    """
    pct = _mem_avail_pct_meminfo()
    if pct is not None:
        return pct
    pct = _mem_avail_pct_windows()
    if pct is not None:
        return pct
    return _mem_avail_pct_sysconf()


def read_board(disk_mount="/"):
    """One live snapshot of this machine, as a readings dict.

    Every value may be None (source not exposed by this
    machine); decide() treats None as "no evidence", never
    as a fault.
    """
    pct = _read_disk_pct(disk_mount)
    return {
        "temp_c": _read_temp_c(),
        "throttled": _read_throttled(),
        "disk_pct": {disk_mount: pct} if pct is not None else {},
        "mem_avail_pct": _read_mem_avail_pct(),
    }


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"active": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    active = state.get("active")
    if not isinstance(active, dict):
        active = {}
    return {"active": {k: v for k, v in active.items()
                       if isinstance(k, str) and isinstance(v, str)}}


def _tunable(tunables, key, default):
    value = tunables.get(key)
    return float(value) if _is_number(value) else default


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock. A signal files when its condition
    holds and its reading differs from the one the state already
    holds for it, so a condition that persists files once, a
    reading that moves files again, and a condition that clears
    resets -- the next occurrence files fresh.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "pi_health"
    temp_high = _tunable(tunables, "temp_high_c", 80.0)
    disk_high = _tunable(tunables, "disk_high_pct", 90.0)
    mem_low = _tunable(tunables, "mem_avail_low_pct", 10.0)

    firing = {}  # state key -> (fingerprint, alert)

    temp = readings.get("temp_c")
    if _is_number(temp) and temp >= temp_high:
        detail = {"temp_c": temp, "threshold_c": temp_high}
        firing["board_overheating"] = (
            json.dumps(detail, sort_keys=True),
            {"sensor": sensor, "signal": "board_overheating",
             "severity": "high",
             "title": f"SoC temperature {_num(temp)}C reached the "
                      f"{_num(temp_high)}C limit",
             "detail": detail})

    throttled = readings.get("throttled")
    if isinstance(throttled, int) and not isinstance(throttled, bool) \
            and throttled & (_UNDERVOLTAGE_MASK | _THROTTLE_MASK):
        detail = {
            "throttled": "0x%x" % throttled,
            "undervoltage_now": bool(throttled & _UNDERVOLTAGE_NOW),
            "undervoltage_since_boot": bool(
                throttled & _UNDERVOLTAGE_SINCE_BOOT),
            "throttled_now": bool(throttled & _THROTTLED_NOW),
            "throttled_since_boot": bool(
                throttled & _THROTTLED_SINCE_BOOT),
        }
        firing["undervoltage_detected"] = (
            json.dumps(detail, sort_keys=True),
            {"sensor": sensor, "signal": "undervoltage_detected",
             "severity": "high",
             "title": f"board reports undervoltage/throttling "
                      f"(throttled=0x{throttled:x})",
             "detail": detail})

    disk = readings.get("disk_pct")
    if isinstance(disk, dict):
        for mount in sorted(disk, key=str):
            pct = disk[mount]
            if not _is_number(pct) or pct < disk_high:
                continue
            detail = {"mount": str(mount), "used_pct": pct,
                      "threshold_pct": disk_high}
            firing[f"disk_pressure:{mount}"] = (
                json.dumps(detail, sort_keys=True),
                {"sensor": sensor, "signal": "disk_pressure",
                 "severity": "medium",
                 "title": f"disk {mount} is {_num(pct)}% full "
                          f"(limit {_num(disk_high)}%)",
                 "detail": detail})

    mem = readings.get("mem_avail_pct")
    if _is_number(mem) and mem <= mem_low:
        detail = {"mem_avail_pct": mem, "threshold_pct": mem_low}
        firing["memory_pressure"] = (
            json.dumps(detail, sort_keys=True),
            {"sensor": sensor, "signal": "memory_pressure",
             "severity": "medium",
             "title": f"available memory down to {_num(mem)}% "
                      f"(floor {_num(mem_low)}%)",
             "detail": detail})

    alerts = []
    active = {}
    for key in sorted(firing):
        fingerprint, alert = firing[key]
        active[key] = fingerprint
        if state["active"].get(key) != fingerprint:
            alerts.append(alert)
    return alerts, {"active": active}


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
        print(f"pi-health: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"pi-health: no signing secret in ${args.secret_env}; "
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
            print(f"pi-health: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"pi-health: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Pi Health extension watcher: read the machine's "
                    "vitals once and file sensor alert payloads for "
                    "what needs attention.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".pi-health-state.json"),
                    help="state file (default: .pi-health-state.json "
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
        print(f"pi-health: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    mount = tunables.get("disk_mount")
    if not isinstance(mount, str) or not mount:
        mount = "/"
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"pi-health: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    else:
        readings = read_board(mount)
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
            # next pass reports these conditions again.
            print(f"pi-health: {len(alerts) - delivered} of "
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
        print(f"pi-health: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
