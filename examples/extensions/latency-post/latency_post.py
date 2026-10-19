#!/usr/bin/env python3
"""Latency Post: a Homing Pigeon user extension (example sense).

Watches reachability and latency the way a network engineer on
watch would: periodic TCP probes to the default gateway and to
configured targets, with each probe timed. A target that stops
answering files once; a target whose latency jumps well above
its own recent median files a spike; everything else is quiet.
Each alert names one of the signals declared in extension.json:

- target_down   a probe failed and the target was not already
                reported down (recovery clears the flag
                silently -- there is no recovery signal)
- latency_spike a probe's latency rose above both the spike_ms
                floor and spike_factor times the median of the
                target's recent samples

The probes are TCP connections only. ICMP is deliberately NOT
used: raw ICMP needs privilege a sense should not require, and
a completed (or refused) TCP handshake already proves the host
answered and times how long it took. One asymmetry follows and
is intentional: the gateway is probed for reachability, so a
connection refused (an RST came back) still counts as ok for
the gateway -- the host is alive, it just does not serve that
port. A configured target is probed for its service, so a
refusal there means ok=False: the service is down.

The machinery is deliberately boring, in the Pi Health
example's shape. read_live() is the only function that touches
the machine; it returns one readings dict, and decide() --
readings plus manifest plus last pass's state, out come alerts
and the new state -- is pure, so the whole decision surface is
testable on any machine. Current time arrives as
readings["now"]; decide() never reads a clock and never
interprets a socket -- read_live() has already reduced each
probe to ok, latency_ms, and an error string.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
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
import json
import os
import socket
import statistics
import sys
import time


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# --- the live reads: the only platform-touching code -----------------

def _read_default_gateway():
    """The default route's gateway IPv4 address, or None.

    Parses /proc/net/route (Linux): the default route is the
    line whose Destination field is 00000000, and its Gateway
    field is the address as little-endian hex. Guarded like
    every other source here: no file, no default route, or an
    unparseable line all answer None, never an error.
    """
    try:
        with open("/proc/net/route", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 3 or fields[1] != "00000000":
            continue
        try:
            raw = bytes.fromhex(fields[2])
            if len(raw) != 4:
                return None
            return ".".join(str(b) for b in reversed(raw))
        except ValueError:
            return None
    return None


def _probe(host, port, timeout, is_gateway):
    """One timed TCP connect. Returns one probe readings entry.

    A completed connect yields ok=True and its latency. A
    refusal still proves the host answered: for the gateway
    (reachability) that is ok=True with a latency; for a
    configured target (a service) it is ok=False with error
    "refused". Timeouts and other socket errors are ok=False
    with no latency sample.
    """
    target = f"{host}:{port}"
    started = time.perf_counter()
    try:
        conn = socket.create_connection((host, port), timeout=timeout)
    except ConnectionRefusedError:
        latency_ms = (time.perf_counter() - started) * 1000.0
        if is_gateway:
            return {"target": target, "ok": True,
                    "latency_ms": round(latency_ms, 3), "error": None}
        return {"target": target, "ok": False,
                "latency_ms": None, "error": "refused"}
    except socket.timeout:
        return {"target": target, "ok": False,
                "latency_ms": None, "error": "timeout"}
    except OSError as e:
        return {"target": target, "ok": False,
                "latency_ms": None,
                "error": str(e) or type(e).__name__}
    latency_ms = (time.perf_counter() - started) * 1000.0
    try:
        conn.close()
    except OSError:
        pass
    return {"target": target, "ok": True,
            "latency_ms": round(latency_ms, 3), "error": None}


def read_live(manifest):
    """One live snapshot: timed TCP probes, as a readings dict.

    Every source is capability-based: no default route means
    no gateway probe, an unusable target entry is skipped,
    and nothing here raises. Probes the gateway (when the
    include_gateway tunable allows) on gateway_port, then each
    {"host", "port"} entry in the targets tunable.
    """
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    timeout = tunables.get("probe_timeout_sec")
    timeout = float(timeout) if _is_number(timeout) and timeout > 0 else 2.0
    probes = []
    include_gateway = tunables.get("include_gateway")
    if include_gateway is not False:
        gateway = _read_default_gateway()
        if gateway:
            port = tunables.get("gateway_port")
            port = int(port) if _is_number(port) and 0 < port < 65536 else 53
            probes.append(_probe(gateway, port, timeout, is_gateway=True))
    targets = tunables.get("targets")
    if isinstance(targets, list):
        for entry in targets:
            if not isinstance(entry, dict):
                continue
            host = entry.get("host")
            port = entry.get("port")
            if not isinstance(host, str) or not host:
                continue
            if not _is_number(port) or not 0 < int(port) < 65536:
                continue
            probes.append(
                _probe(host, int(port), timeout, is_gateway=False))
    return {"now": time.time(), "probes": probes}


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"targets": {}}


def _fresh_target():
    return {"samples": [], "down": False, "spike_active": False}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    targets = state.get("targets")
    if not isinstance(targets, dict):
        targets = {}
    clean = {}
    for key, entry in targets.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            continue
        samples = entry.get("samples")
        if not isinstance(samples, list):
            samples = []
        clean[key] = {
            "samples": [float(v) for v in samples if _is_number(v)][-20:],
            "down": bool(entry.get("down")),
            "spike_active": bool(entry.get("spike_active")),
        }
    return {"targets": clean}


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"] (the decision itself is time-free; latency
    history, not wall time, drives it). A down target files
    once and stays quiet until a probe succeeds; a spike files
    once, and an in-band reading clears the spike flag quietly
    so the next spike files fresh.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "latency_post"
    spike_ms = tunables.get("spike_ms")
    spike_ms = float(spike_ms) if _is_number(spike_ms) else 250.0
    spike_factor = tunables.get("spike_factor")
    spike_factor = float(spike_factor) \
        if _is_number(spike_factor) else 3.0

    alerts = []
    probes = readings.get("probes")
    if not isinstance(probes, list):
        probes = []
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        target = probe.get("target")
        if not isinstance(target, str) or not target:
            continue
        ok = probe.get("ok")
        if not isinstance(ok, bool):
            continue
        entry = state["targets"].setdefault(target, _fresh_target())
        if not ok:
            if not entry["down"]:
                detail = {"target": target}
                error = probe.get("error")
                if isinstance(error, str) and error:
                    detail["error"] = error
                alerts.append({
                    "sensor": sensor, "signal": "target_down",
                    "severity": "high",
                    "title": f"target {target} stopped answering",
                    "detail": detail})
            entry["down"] = True
            continue
        entry["down"] = False  # recovery is silent: no signal
        latency = probe.get("latency_ms")
        if not _is_number(latency):
            continue
        latency = float(latency)
        prior = entry["samples"]
        if len(prior) >= 3:
            median = float(statistics.median(prior))
            if latency > max(spike_ms, spike_factor * median):
                if not entry["spike_active"]:
                    alerts.append({
                        "sensor": sensor, "signal": "latency_spike",
                        "severity": "medium",
                        "title": f"target {target} latency "
                                 f"{latency:g}ms spiked above its "
                                 f"median {median:g}ms",
                        "detail": {"target": target,
                                   "latency_ms": latency,
                                   "median_ms": median}})
                entry["spike_active"] = True
            else:
                entry["spike_active"] = False
        entry["samples"] = (prior + [latency])[-20:]
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
        from runner import extensions as hp_extensions
    except ImportError as e:
        print(f"latency-post: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"latency-post: no signing secret in ${args.secret_env}; "
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
            print(f"latency-post: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"latency-post: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Latency Post extension watcher: probe the "
                    "gateway and configured targets once and file "
                    "sensor alert payloads for what needs attention.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".latency-post-state.json"),
                    help="state file (default: .latency-post-state.json "
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
        print(f"latency-post: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"latency-post: cannot read readings "
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
            print(f"latency-post: {len(alerts) - delivered} of "
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
        print(f"latency-post: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
