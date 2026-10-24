#!/usr/bin/env python3
"""Service Watch: a Homing Pigeon user extension (example sense).

Watches that the processes a box exists to run are actually
running -- the services named in the manifest's tunables -- and
turns their state changes into sensor alerts for the Oracle.
Each alert names one of the signals declared in extension.json:

- service_down       a service that was up is now absent
                     (high)
- service_recovered  a service returned after a filed outage
                     (info)
- service_flapping   a service changed state repeatedly
                     inside the flap window (medium)

The machinery is deliberately boring, in the Lab Results
example's shape. read_live() is the only function that touches
the machine; it returns one readings dict, and decide() --
readings plus manifest plus last pass's state, out come alerts
and the new state -- is pure, so the whole decision surface is
testable on any box. Current time arrives as readings["now"]
(epoch seconds); decide() never reads a clock itself.

Matching is deliberately simple. A service is UP if any
process matches it: "exact" compares the process name, and
"substring" looks for the service name inside the full
command line. The first pass can be a learn pass (the
learn_first_pass tunable, on by default): it records which
services are up and which are down and files nothing, so a
service that was already down when the watcher started does
not file a false outage, and its later return is not a filed
recovery either.

Flapping is counted from state transitions. Every up/down
change is timestamped; when the transitions inside the
trailing flap_window_sec reach flap_count the sense files
once, and it does not file again until a full window passes
with no transitions at all.

Sources, capability-based: on Linux the process list comes
from /proc -- /proc/<pid>/comm for the name and
/proc/<pid>/cmdline for the command line. A process that
exits mid-scan is skipped quietly. On a machine with no
/proc (Windows, macOS) the live read yields an empty process
list; there the fixture path -- --readings -- is the way to
run the sense.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extend/extensions.md, "Local delivery").

--readings FILE reads a readings dict from a JSON file instead
of the machine: the way to try the sense (and test it) against
known readings, on any box at all.
"""
import argparse
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


# --- the live reads: the only platform-touching code -----------------

def read_live(manifest):
    """One live snapshot of the process table, as a readings dict.

    Returns {"now": epoch float, "processes": [{"name", "pid",
    "cmdline"}]}. Linux only in practice: it scans /proc. Where
    there is no /proc the process list is empty -- absent data,
    never an error.
    """
    readings = {"now": time.time(), "processes": []}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return readings
    processes = []
    for entry in entries:
        if not entry.isdigit():
            continue
        base = os.path.join("/proc", entry)
        try:
            with open(os.path.join(base, "comm"), encoding="utf-8",
                      errors="replace") as fh:
                name = fh.read().strip()
        except OSError:
            continue  # the process exited mid-scan; skip quietly
        cmdline = ""
        try:
            with open(os.path.join(base, "cmdline"), "rb") as fh:
                raw = fh.read()
            parts = [p.decode("utf-8", errors="replace")
                     for p in raw.split(b"\x00") if p]
            cmdline = " ".join(parts)
        except OSError:
            cmdline = ""
        try:
            pid = int(entry)
        except ValueError:
            continue
        processes.append({"name": name, "pid": pid,
                          "cmdline": cmdline})
    readings["processes"] = processes
    return readings


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"learned": False, "services": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    learned = state.get("learned")
    if not isinstance(learned, bool):
        learned = False
    raw_services = state.get("services")
    if not isinstance(raw_services, dict):
        raw_services = {}
    services = {}
    for name, entry in raw_services.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        up = entry.get("up")
        if not isinstance(up, bool):
            up = False
        transitions = entry.get("transitions")
        if not isinstance(transitions, list):
            transitions = []
        transitions = [float(v) for v in transitions if _is_number(v)]
        down_filed = entry.get("down_filed")
        if not isinstance(down_filed, bool):
            down_filed = False
        flap_fired = entry.get("flap_fired")
        if not isinstance(flap_fired, bool):
            flap_fired = False
        services[name] = {"up": up, "transitions": transitions,
                          "down_filed": down_filed,
                          "flap_fired": flap_fired}
    return {"learned": learned, "services": services}


def _services_from_tunables(tunables):
    raw = tunables.get("services")
    if not isinstance(raw, list):
        return []
    out = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        match = entry.get("match")
        if match not in ("exact", "substring"):
            match = "exact"
        out.append({"name": name, "match": match})
    return out


def _is_up(service, processes):
    name = service["name"]
    match = service["match"]
    for proc in processes:
        if not isinstance(proc, dict):
            continue
        if match == "exact":
            if proc.get("name") == name:
                return True
        else:  # substring against the full cmdline
            cmdline = proc.get("cmdline")
            if isinstance(cmdline, str) and name in cmdline:
                return True
    return False


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time is readings["now"].
    Signals file in service-tunables order for determinism.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "service_watch"
    now = readings.get("now")
    now = float(now) if _is_number(now) else 0.0
    processes = readings.get("processes")
    if not isinstance(processes, list):
        processes = []
    flap_window = tunables.get("flap_window_sec")
    flap_window = float(flap_window) if _is_number(flap_window) \
        and flap_window > 0 else 600.0
    flap_count = tunables.get("flap_count")
    flap_count = int(flap_count) if _is_number(flap_count) \
        and flap_count >= 1 else 4
    learn_first = tunables.get("learn_first_pass")
    if not isinstance(learn_first, bool):
        learn_first = True
    services = _services_from_tunables(tunables)

    # Learn pass: record the starting picture, file nothing.
    if not state["learned"] and learn_first:
        for svc in services:
            up = _is_up(svc, processes)
            prev = state["services"].get(svc["name"])
            if prev is None:
                state["services"][svc["name"]] = {
                    "up": up, "transitions": [],
                    "down_filed": False, "flap_fired": False}
            else:
                prev["up"] = up
        state["learned"] = True
        return [], state

    alerts = []
    for svc in services:
        name = svc["name"]
        up_now = _is_up(svc, processes)
        entry = state["services"].get(name)
        if entry is None:
            # First sight of this service (learn disabled, or the
            # service was added later): seed it, file nothing.
            state["services"][name] = {
                "up": up_now, "transitions": [],
                "down_filed": False, "flap_fired": False}
            continue
        was_up = entry["up"]
        transitioned = (was_up != up_now)
        if transitioned:
            # Downtime is measured from the previous transition
            # (the moment it went down) before recording this one.
            prev_ts = entry["transitions"][-1] \
                if entry["transitions"] else None
            if was_up and not up_now:
                alerts.append({
                    "sensor": sensor, "signal": "service_down",
                    "severity": "high",
                    "title": f"service {name} is down",
                    "detail": {"service": name},
                })
                entry["down_filed"] = True
            elif not was_up and up_now:
                if entry["down_filed"]:
                    downtime = (now - prev_ts) if prev_ts is not None else 0.0
                    if downtime < 0:
                        downtime = 0.0
                    alerts.append({
                        "sensor": sensor, "signal": "service_recovered",
                        "severity": "info",
                        "title": f"service {name} recovered",
                        "detail": {"service": name,
                                   "downtime_sec": downtime},
                    })
                    entry["down_filed"] = False
                # A down that was never filed recovers silently.
            entry["transitions"].append(now)
            entry["up"] = up_now
        # Flap bookkeeping: evaluated on any pass where the
        # transitions changed or simply aged.
        if entry["flap_fired"] and entry["transitions"]:
            if now - max(entry["transitions"]) >= flap_window:
                entry["flap_fired"] = False
        # Prune to the trailing window for counting.
        cutoff = now - flap_window
        entry["transitions"] = [t for t in entry["transitions"]
                                if t > cutoff]
        if entry["flap_fired"] and not entry["transitions"]:
            entry["flap_fired"] = False
        if not entry["flap_fired"] \
                and len(entry["transitions"]) >= flap_count:
            alerts.append({
                "sensor": sensor, "signal": "service_flapping",
                "severity": "medium",
                "title": f"service {name} is flapping "
                         f"({len(entry['transitions'])} transitions "
                         f"in {int(flap_window)}s)",
                "detail": {"service": name,
                           "transitions": len(entry["transitions"]),
                           "window_sec": flap_window},
            })
            entry["flap_fired"] = True
    state["learned"] = True
    return alerts, state


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
        print(f"service-watch: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"service-watch: no signing secret in ${args.secret_env}; "
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
            print(f"service-watch: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"service-watch: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Service Watch extension watcher: check that "
                    "configured services are running and file sensor "
                    "alert payloads for state changes.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".service-watch-state.json"),
                    help="state file (default: .service-watch-state.json "
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
        print(f"service-watch: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"service-watch: cannot read readings "
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
            # next pass reports these changes again.
            print(f"service-watch: {len(alerts) - delivered} of "
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
        print(f"service-watch: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
