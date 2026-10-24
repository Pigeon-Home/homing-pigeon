#!/usr/bin/env python3
"""Resource Sentinel: a Homing Pigeon user extension (example sense).

The security-focused resource monitor. The runner already
carries a built-in pressure monitor (runner/oracle/resources.py):
single thresholds on CPU, memory and disk that feed the DRI
paging path. This sense is the other half of that story --
it watches the same machine the way an intrusion analyst
would, and files what it finds as sensor alerts for the
Oracle. Nothing here fires on a single sample. Every signal
is a rate or a trend measured against this extension's own
rolling window of samples:

- cpu_saturation_sustained  total CPU busy at or over the
                    cpu_high_pct tunable (default 95) across
                    the whole window -- a miner or a spin
                    loop holds the machine like that; a
                    compile does not
- disk_fill_velocity free space on the watched mount
                    shrinking at or faster than the
                    disk_fill_gb_per_hour tunable
                    (default 10) -- log bombing, evidence
                    flooding, a runaway writer
- process_storm     the process count growing by at least
                    the process_growth tunable (default
                    200) inside the window -- fork-bomb and
                    runaway-spawn shape
- memory_exhaustion_trend available memory falling steadily
                    toward the mem_floor_pct tunable
                    (default 15 percent of total) across the
                    window -- a leak or a memory bomb, told
                    apart from pi-health's static low-memory
                    threshold by the trend itself

The machinery is deliberately boring, in the Lab Results
example's shape. read_live() is the only function that
touches the machine; it returns one readings dict of raw
counters, and decide() -- readings plus manifest plus last
pass's state, out come alerts and the new state -- is pure,
so the whole decision surface is testable off-hardware.
Current time arrives as readings["now"], never from a clock
inside decide(). Sources are capability-based: /proc/stat
for CPU counters, /proc entries for the process count,
/proc/meminfo for memory, shutil.disk_usage for the watched
mount. A source the machine does not expose reports None,
which never yields a signal and is never an error -- on a
machine without /proc only the disk velocity still speaks,
because its source is portable.

A signal fires when its condition first holds, and again
when its headline metric moves to a coarser bucket (the
situation is getting worse, or easing); while the condition
holds steady it stays quiet, and when it clears, the next
episode files fresh.

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
of the machine: the way to try the sense (and test it)
against known counters, on any box at all.
"""
import argparse
import json
import os
import shutil
import sys
import time

_GIB = 1024.0 ** 3


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


def _num(value):
    return "%g" % value


def _tunables(manifest):
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    return tunables if isinstance(tunables, dict) else {}


def _tunable(tunables, key, default):
    value = tunables.get(key)
    return float(value) if _is_number(value) else default


# --- the live reads: the only platform-touching code -----------------

def _read_cpu_counters():
    """(total, idle) jiffy counters from /proc/stat, or None.

    Counters are cumulative since boot; the busy share is a
    difference between two samples, which decide() computes
    against the previous sample in its own state.
    """
    try:
        with open("/proc/stat", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("cpu "):
                    fields = line.split()[1:]
                    values = [int(f) for f in fields]
                    total = sum(values)
                    idle = values[3] + (values[4] if len(values) > 4
                                        else 0)
                    return total, idle
    except (OSError, ValueError, IndexError):
        return None
    return None


def _read_process_count():
    """How many processes exist right now, or None.

    Counts the numeric entries in /proc. A box without /proc
    reports None and the storm signal simply never fires.
    """
    try:
        return sum(1 for name in os.listdir("/proc") if name.isdigit())
    except OSError:
        return None


def _read_mem_avail_pct():
    """MemAvailable as a percent of MemTotal, or None."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    found = {}
    for line in text.splitlines():
        for key in ("MemTotal", "MemAvailable"):
            if line.startswith(key + ":"):
                parts = line.split()
                try:
                    found[key] = int(parts[1])
                except (ValueError, IndexError):
                    pass
    total = found.get("MemTotal") or 0
    avail = found.get("MemAvailable")
    if avail is None or total <= 0:
        return None
    return round(100.0 * avail / total, 2)


def _read_disk_free(mount):
    """Free bytes on the watched mount, or None."""
    try:
        usage = shutil.disk_usage(mount)
    except OSError:
        return None
    return usage.free


def read_live(manifest):
    """One live snapshot of raw resource counters.

    Returns {"now", "cpu_total", "cpu_idle", "disk_free_bytes",
    "processes", "mem_avail_pct"}; every value but "now" may
    be None (source not exposed by this machine). Never raises.
    """
    tunables = _tunables(manifest)
    mount = tunables.get("disk_mount")
    if not isinstance(mount, str) or not mount:
        mount = "/"
    cpu = _read_cpu_counters()
    return {
        "now": time.time(),
        "cpu_total": cpu[0] if cpu else None,
        "cpu_idle": cpu[1] if cpu else None,
        "disk_free_bytes": _read_disk_free(mount),
        "processes": _read_process_count(),
        "mem_avail_pct": _read_mem_avail_pct(),
    }


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"samples": [], "fired": {}}


def _clean_sample(row):
    if not isinstance(row, (list, tuple)) or len(row) != 6:
        return None
    if not _is_number(row[0]):
        return None
    cleaned = [float(row[0])]
    for value in row[1:]:
        cleaned.append(float(value) if _is_number(value) else None)
    return cleaned


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    samples = []
    raw = state.get("samples")
    if isinstance(raw, list):
        for row in raw:
            cleaned = _clean_sample(row)
            if cleaned is not None:
                samples.append(cleaned)
    fired = state.get("fired")
    if not isinstance(fired, dict):
        fired = {}
    return {"samples": samples,
            "fired": {k: v for k, v in fired.items()
                      if isinstance(k, str) and isinstance(v, str)}}


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time is
    readings["now"]. The pass appends its sample (when the
    readings carry a time newer than the last sample's),
    prunes the rolling window, and judges each signal as a
    rate or a trend across the window. State is
    {"samples": [[ts, cpu_total, cpu_idle, disk_free_bytes,
    processes, mem_avail_pct], ...], "fired": {signal:
    fingerprint}}.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = _tunables(manifest)
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "resource_sentinel"
    window = _tunable(tunables, "window_sec", 1800.0)
    if window <= 0:
        window = 1800.0
    min_span = _tunable(tunables, "min_span_sec", 600.0)
    min_samples = int(_tunable(tunables, "min_samples", 4))
    if min_samples < 2:
        min_samples = 2
    max_samples = int(_tunable(tunables, "max_samples", 240))
    if max_samples < min_samples:
        max_samples = min_samples
    cpu_high = _tunable(tunables, "cpu_high_pct", 95.0)
    fill_rate = _tunable(tunables, "disk_fill_gb_per_hour", 10.0)
    proc_growth = _tunable(tunables, "process_growth", 200.0)
    mem_floor = _tunable(tunables, "mem_floor_pct", 15.0)
    mem_drop = _tunable(tunables, "mem_drop_points", 25.0)

    now = readings.get("now")
    now = float(now) if _is_number(now) else None
    samples = list(state["samples"])
    if now is not None and (not samples or now > samples[-1][0]):
        samples.append([now, readings.get("cpu_total"),
                        readings.get("cpu_idle"),
                        readings.get("disk_free_bytes"),
                        readings.get("processes"),
                        readings.get("mem_avail_pct")])
        samples = [[s[0]] + [float(v) if _is_number(v) else None
                              for v in s[1:]] for s in samples]
    if now is not None:
        samples = [s for s in samples if s[0] >= now - window]
    if len(samples) > max_samples:
        samples = samples[-max_samples:]

    firing = {}  # signal -> (fingerprint, alert)
    if now is not None and len(samples) >= min_samples:
        first, last = samples[0], samples[-1]
        span = last[0] - first[0]
        if span >= min_span:
            # Sustained CPU: the busy share between the first
            # and last samples of the window.
            if first[1] is not None and last[1] is not None \
                    and first[2] is not None and last[2] is not None:
                d_total = last[1] - first[1]
                d_idle = last[2] - first[2]
                if d_total > 0:
                    busy = 100.0 * (1.0 - d_idle / d_total)
                    if busy >= cpu_high:
                        detail = {"cpu_busy_pct": round(busy, 1),
                                  "threshold_pct": cpu_high,
                                  "window_sec": round(span)}
                        firing["cpu_saturation_sustained"] = (
                            f"cpu:{int(busy // 5 * 5)}",
                            {"sensor": sensor,
                             "signal": "cpu_saturation_sustained",
                             "severity": "high",
                             "title": f"CPU held at {_num(round(busy, 1))}% "
                                      f"busy for {int(span)}s "
                                      f"(limit {_num(cpu_high)}%)",
                             "detail": detail})
            # Disk fill velocity: free space lost per hour
            # across the window.
            if first[3] is not None and last[3] is not None \
                    and last[3] < first[3]:
                lost_gib = (first[3] - last[3]) / _GIB
                rate = lost_gib / (span / 3600.0)
                if rate >= fill_rate:
                    detail = {"gb_per_hour": round(rate, 1),
                              "threshold_gb_per_hour": fill_rate,
                              "free_gb_now": round(last[3] / _GIB, 1),
                              "window_sec": round(span)}
                    firing["disk_fill_velocity"] = (
                        f"disk:{int(rate // 5 * 5)}",
                        {"sensor": sensor, "signal": "disk_fill_velocity",
                         "severity": "high",
                         "title": f"disk free space shrinking at "
                                  f"{_num(round(rate, 1))} GB/hour "
                                  f"(limit {_num(fill_rate)})",
                         "detail": detail})
            # Process storm: growth from the window's low
            # point to its end.
            counts = [s[4] for s in samples if s[4] is not None]
            if len(counts) >= min_samples and last[4] is not None:
                growth = last[4] - min(counts)
                if growth >= proc_growth:
                    detail = {"growth": int(growth),
                              "threshold": int(proc_growth),
                              "processes_now": int(last[4]),
                              "window_sec": round(span)}
                    firing["process_storm"] = (
                        f"procs:{int(growth // 50 * 50)}",
                        {"sensor": sensor, "signal": "process_storm",
                         "severity": "medium",
                         "title": f"process count grew by {int(growth)} "
                                  f"inside the window "
                                  f"(limit {int(proc_growth)})",
                         "detail": detail})
            # Memory exhaustion trend: available memory fell
            # steadily toward the floor across the window.
            mems = [s[5] for s in samples if s[5] is not None]
            if len(mems) >= min_samples and last[5] is not None \
                    and last[5] <= mem_floor \
                    and (mems[0] - last[5]) >= mem_drop:
                rises = sum(1 for a, b in zip(mems, mems[1:])
                            if b > a + 0.5)
                if rises <= 1:
                    detail = {"mem_avail_pct": last[5],
                              "floor_pct": mem_floor,
                              "drop_points": round(mems[0] - last[5], 1),
                              "window_sec": round(span)}
                    firing["memory_exhaustion_trend"] = (
                        f"mem:{int(last[5] // 5 * 5)}",
                        {"sensor": sensor,
                         "signal": "memory_exhaustion_trend",
                         "severity": "medium",
                         "title": f"available memory fell to "
                                  f"{_num(last[5])}% and is still "
                                  f"falling (floor {_num(mem_floor)}%)",
                         "detail": detail})

    alerts = []
    fired = {}
    for signal in sorted(firing):
        fingerprint, alert = firing[signal]
        fired[signal] = fingerprint
        if state["fired"].get(signal) != fingerprint:
            alerts.append(alert)
    return alerts, {"samples": samples, "fired": fired}


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
        from runner.ops import extensions as hp_extensions
    except ImportError as e:
        print(f"resource-sentinel: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"resource-sentinel: no signing secret in "
              f"${args.secret_env}; set it to this sense's key "
              f"secret", file=sys.stderr)
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
            print(f"resource-sentinel: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"resource-sentinel: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Resource Sentinel extension watcher: sample "
                    "the machine's resource counters once and file "
                    "sensor alert payloads for hostile rates and "
                    "trends.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".resource-sentinel-state.json"),
                    help="state file (default: "
                         ".resource-sentinel-state.json next to "
                         "this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the machine (trying the sense "
                         "against known counters, on any box)")
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
        print(f"resource-sentinel: cannot read manifest "
              f"{args.manifest}: {e}", file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"resource-sentinel: cannot read readings "
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
            # next pass reports these conditions again.
            print(f"resource-sentinel: {len(alerts) - delivered} of "
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
        print(f"resource-sentinel: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
