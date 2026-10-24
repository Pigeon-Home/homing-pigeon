#!/usr/bin/env python3
"""Port Watch: a Homing Pigeon user extension (example sense).

Watches the machine's listening sockets the way a penetration
tester doing a sweep would ask the question: what new doors
opened since last pass, and are any of them facing the street?
It diffs the listeners it finds against a learned baseline and
files what is new. Each alert names one of the signals
declared in extension.json:

- exposed_listener  a new listener bound to a wildcard address
                    (0.0.0.0 or ::), or to a port below 1024 --
                    the two shapes that mean other machines can
                    likely reach it, or that it needed privilege
                    to open
- new_listener      any other new listener: a specific address
                    and a port at or above 1024

There is no process attribution. /proc reports sockets, not
their owners; mapping a socket to a process takes an
inode-to-fd walk over every process on the box, which this
example deliberately does not do. The alert says a door
opened, not who opened it -- attribution is a job for the
operator (or a heavier sense) once the door is known.

The machinery is deliberately boring, in the Pi Health
example's shape. read_live() is the only function that touches
the machine; it returns one readings dict, and decide() --
readings plus manifest plus last pass's state, out come alerts
and the new state -- is pure, so the whole decision surface is
testable on any machine. Current time arrives as
readings["now"]; decide() never reads a clock. With the
learn_first_pass tunable on (the default), the first pass
absorbs whatever is already listening as the baseline and
files nothing: a sense that cried about every pre-existing
service on its first run would teach the operator to ignore
it. Listeners that vanish leave the state silently, so one
that returns files again.

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
import ipaddress
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

def _ipv4_from_hex(text):
    """An IPv4 address from /proc's little-endian hex, or None."""
    try:
        raw = bytes.fromhex(text)
        if len(raw) != 4:
            return None
        return str(ipaddress.IPv4Address(bytes(reversed(raw))))
    except ValueError:
        return None


def _ipv6_from_hex(text):
    """An IPv6 address from /proc's hex, or None.

    /proc/net/tcp6 and udp6 print the address as four 32-bit
    words, each little-endian; reversing each word's bytes
    recovers the address. The all-zero wildcard normalizes to
    "::" through the ipaddress module's compressed form, as
    every address here does.
    """
    try:
        raw = bytes.fromhex(text)
        if len(raw) != 16:
            return None
        fixed = b"".join(raw[i:i + 4][::-1] for i in range(0, 16, 4))
        return str(ipaddress.IPv6Address(fixed))
    except ValueError:
        return None


def _parse_proc_net(path, proto, v6):
    """Listeners from one /proc/net file. Missing file: none.

    TCP counts state 0A (LISTEN). UDP has no LISTEN state, so
    the approximation -- stated plainly, because it is one --
    is that an entry with no remote address (an unconnected
    socket), or in state 07, counts as a listener.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    found = []
    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 4:
            continue
        local = fields[1]
        remote = fields[2]
        state = fields[3].upper()
        if proto == "tcp":
            if state != "0A":
                continue
        else:  # udp
            remote_addr, _, remote_port = remote.partition(":")
            no_remote = remote_port == "0000" and set(remote_addr) <= {"0"}
            if not (no_remote or state == "07"):
                continue
        addr_hex, _, port_hex = local.partition(":")
        addr = _ipv6_from_hex(addr_hex) if v6 else _ipv4_from_hex(addr_hex)
        if addr is None:
            continue
        try:
            port = int(port_hex, 16)
        except ValueError:
            continue
        found.append({"proto": proto, "addr": addr, "port": port})
    return found


def read_live(manifest):
    """One live snapshot of the listening sockets, as readings.

    Linux only by nature: the sources are /proc/net/tcp,
    tcp6, udp and udp6, and each missing file is simply
    skipped -- on a machine without /proc the readings carry
    no listeners at all, which is absence of evidence, never
    an error. `manifest` is accepted for the uniform producer
    contract; no tunable steers the read itself.
    """
    listeners = []
    listeners += _parse_proc_net("/proc/net/tcp", "tcp", v6=False)
    listeners += _parse_proc_net("/proc/net/tcp6", "tcp", v6=True)
    listeners += _parse_proc_net("/proc/net/udp", "udp", v6=False)
    listeners += _parse_proc_net("/proc/net/udp6", "udp", v6=True)
    unique = {}
    for entry in listeners:
        unique[(entry["proto"], entry["addr"], entry["port"])] = entry
    return {"now": time.time(),
            "listeners": [unique[k] for k in sorted(unique)]}


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"learned": False, "seen": {}}


def _key(listener):
    return f"{listener['proto']}/{listener['addr']}/{listener['port']}"


def _clean_listener(value):
    if not isinstance(value, dict):
        return None
    proto = value.get("proto")
    addr = value.get("addr")
    port = value.get("port")
    if proto not in ("tcp", "udp"):
        return None
    if not isinstance(addr, str) or not addr:
        return None
    if not _is_number(port) or not 0 <= int(port) <= 65535:
        return None
    return {"proto": proto, "addr": addr, "port": int(port)}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    seen = state.get("seen")
    if not isinstance(seen, dict):
        seen = {}
    clean = {}
    for key, entry in seen.items():
        if not isinstance(key, str):
            continue
        listener = _clean_listener(entry)
        if listener is not None:
            clean[_key(listener)] = listener
    return {"learned": bool(state.get("learned")), "seen": clean}


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"] (the decision itself is time-free; the
    diff against the learned baseline drives it). The first
    pass learns quietly when learn_first_pass allows; after
    that, a listener key not in the baseline files exactly
    once and is absorbed, whether or not high_only suppressed
    its (medium) alert. Vanished listeners leave the state
    silently, so a listener that returns files again.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "port_watch"
    learn_first = tunables.get("learn_first_pass")
    learn_first = True if learn_first is None else bool(learn_first)
    high_only = bool(tunables.get("high_only"))

    current = {}
    listeners = readings.get("listeners")
    if isinstance(listeners, list):
        for entry in listeners:
            listener = _clean_listener(entry)
            if listener is not None:
                current[_key(listener)] = listener

    if not state["learned"]:
        state["learned"] = True
        state["seen"] = dict(current)
        if learn_first:
            return [], state
        # Not learning quietly: fall through and file everything
        # current against the (empty) baseline.
        state["seen"] = {}

    alerts = []
    seen = dict(state["seen"])
    # Vanished listeners leave the state silently.
    seen = {k: v for k, v in seen.items() if k in current}
    for key in sorted(current):
        if key in seen:
            continue
        listener = current[key]
        exposed = listener["addr"] in ("0.0.0.0", "::") \
            or listener["port"] < 1024
        detail = {"proto": listener["proto"], "addr": listener["addr"],
                  "port": listener["port"]}
        if exposed:
            alerts.append({
                "sensor": sensor, "signal": "exposed_listener",
                "severity": "high",
                "title": f"new exposed listener "
                         f"{listener['proto']} {listener['addr']}:"
                         f"{listener['port']}",
                "detail": detail})
        elif not high_only:
            alerts.append({
                "sensor": sensor, "signal": "new_listener",
                "severity": "medium",
                "title": f"new listener {listener['proto']} "
                         f"{listener['addr']}:{listener['port']}",
                "detail": detail})
        seen[key] = listener  # absorbed even when high_only hid it
    state["seen"] = seen
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
        print(f"port-watch: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"port-watch: no signing secret in ${args.secret_env}; "
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
            print(f"port-watch: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"port-watch: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Port Watch extension watcher: diff the "
                    "machine's listening sockets once and file "
                    "sensor alert payloads for new listeners.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".port-watch-state.json"),
                    help="state file (default: .port-watch-state.json "
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
        print(f"port-watch: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"port-watch: cannot read readings "
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
            # next pass reports these listeners again.
            print(f"port-watch: {len(alerts) - delivered} of "
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
        print(f"port-watch: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
