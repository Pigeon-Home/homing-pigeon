#!/usr/bin/env python3
"""Wire Arrivals: a Homing Pigeon user extension (example sense).

Watches the ARP/neighbor table of the machine it runs on --
who is on this LAN, by IP and by hardware address -- and files
what changes as sensor alerts for the Oracle. It comes from
network engineering: a neighbor table is a small, honest
census of a wire, and its two interesting events are a
stranger showing up and a known address suddenly answering
from different hardware, which is the classic ARP-spoofing
tell. Each alert names one of the signals declared in
extension.json:

- new_neighbor  a MAC address not seen before appeared in
                the neighbor table
- mac_moved     a known IP address now answers from a
                different MAC address than the one in state

The machinery is deliberately boring, in the Pi Health
example's shape. read_live() is the only function that touches
the platform; it returns one readings dict, and decide() --
readings plus manifest plus last pass's state, out come
alerts and the new state -- is pure, so the whole decision
surface is testable on any machine. State absorbs every
reading: a new IP under a MAC already known is recorded
silently (no signal exists for it), and the table matching
state files nothing at all.

With the learn_first_pass tunable on (the default), the very
first pass is a baseline: the whole table is absorbed, the
state learns, and nothing files -- a sense installed on a
busy LAN should not open by reporting the entire LAN. With
it off, the first pass files like any other.

When one entry triggers mac_moved, that entry files ONLY
mac_moved, not also new_neighbor for the new MAC -- the
stronger tell wins -- but the new MAC is still absorbed
into state.

Sources, capability-based -- a source the machine does not
expose yields no neighbors, which is never an error:

- Linux: /proc/net/arp (the header line and entries with an
  all-zero MAC are skipped).
- Fallback, when that file is absent: `ip neigh show`, or
  `arp -a` when `ip` is not installed -- whichever tool the
  machine offers, run guarded with a short timeout.
- Other platforms without those files or tools report an
  empty table. MACs are normalized to lowercase throughout,
  and when the ifaces tunable is non-empty a reading is kept
  only when its source names one of those interfaces.

Run on the same machine as the runner, it delivers locally:
--local-dir <runner base dir> signs each payload with this
sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extend/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and signing
and delivery follow the standard senses flow.

--readings FILE reads a readings dict from a JSON file instead
of the platform: the way to try the sense (and test it)
against a known neighbor table, on any box at all. A readings
file carries "now" (epoch seconds) and "neighbors", a list of
records {"ip", "mac", "iface"}.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

_ZERO_MAC = "00:00:00:00:00:00"
_MAC_RE = re.compile(r"\A[0-9a-f]{2}(:[0-9a-f]{2}){5}\Z")


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

def _iface_filter(manifest):
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        return []
    ifaces = tunables.get("ifaces")
    if not isinstance(ifaces, list):
        return []
    return [i for i in ifaces if isinstance(i, str) and i]


def _keep(iface, wanted):
    """True when a reading survives the iface filter.

    With no filter everything survives; with one, a reading
    survives when it names a wanted interface -- or names no
    interface at all (its source does not say, so the filter
    has nothing to judge it by).
    """
    if not wanted:
        return True
    if not iface:
        return True
    return iface in wanted


def _parse_proc_net_arp(text):
    neighbors = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 6 or parts[0] == "IP":
            continue  # header line, or a malformed row
        ip, mac, iface = parts[0], parts[3].lower(), parts[5]
        if mac == _ZERO_MAC or not _MAC_RE.match(mac):
            continue
        neighbors.append({"ip": ip, "mac": mac, "iface": iface})
    return neighbors


def _parse_ip_neigh(text):
    neighbors = []
    for line in (text or "").splitlines():
        # 192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
        m = re.match(r"(\S+)\s+dev\s+(\S+)\s+lladdr\s+(\S+)", line)
        if not m:
            continue
        mac = m.group(3).lower()
        if mac == _ZERO_MAC or not _MAC_RE.match(mac):
            continue
        neighbors.append({"ip": m.group(1), "mac": mac,
                          "iface": m.group(2)})
    return neighbors


def _parse_arp_a(text):
    neighbors = []
    for line in (text or "").splitlines():
        # host (192.168.1.1) at aa:bb:cc:dd:ee:ff [ether] on eth0
        # ? (192.168.1.1) at aa:bb:.. on en0 ifscope [ethernet]
        m = re.search(r"\(([^)]+)\)\s+at\s+(\S+)(?:\s+.*?\bon\s+(\S+))?",
                      line)
        if not m:
            continue
        mac = m.group(2).lower()
        if mac == _ZERO_MAC or not _MAC_RE.match(mac):
            continue
        neighbors.append({"ip": m.group(1), "mac": mac,
                          "iface": m.group(3) or ""})
    return neighbors


def _run_tool(argv):
    try:
        out = subprocess.run(argv, capture_output=True, text=True,
                             timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout or ""


def read_live(manifest):
    """One live snapshot of the neighbor table.

    Returns {"now": epoch float, "neighbors": [record, ...]}.
    A platform that exposes no table yields an empty list,
    never an exception.
    """
    wanted = _iface_filter(manifest)
    neighbors = None
    try:
        with open("/proc/net/arp", encoding="utf-8") as fh:
            neighbors = _parse_proc_net_arp(fh.read())
    except OSError:
        neighbors = None
    if neighbors is None:
        exe = shutil.which("ip")
        if exe:
            text = _run_tool([exe, "neigh", "show"])
            if text is not None:
                neighbors = _parse_ip_neigh(text)
        if neighbors is None:
            exe = shutil.which("arp")
            if exe:
                text = _run_tool([exe, "-a"])
                if text is not None:
                    neighbors = _parse_arp_a(text)
    if neighbors is None:
        neighbors = []
    return {"now": time.time(),
            "neighbors": [n for n in neighbors
                          if _keep(n.get("iface"), wanted)]}


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"learned": False, "macs": {}, "ips": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    learned = state.get("learned")
    macs_in = state.get("macs")
    if not isinstance(macs_in, dict):
        macs_in = {}
    macs = {}
    for mac, rec in macs_in.items():
        if not isinstance(mac, str):
            continue
        ips = rec.get("ips") if isinstance(rec, dict) else None
        if not isinstance(ips, list):
            ips = []
        macs[mac.lower()] = {
            "ips": sorted({i for i in ips if isinstance(i, str) and i})}
    ips_in = state.get("ips")
    if not isinstance(ips_in, dict):
        ips_in = {}
    ips = {ip: mac.lower() for ip, mac in ips_in.items()
           if isinstance(ip, str) and ip
           and isinstance(mac, str) and mac}
    return {"learned": bool(learned), "macs": macs, "ips": ips}


def _absorb(macs, ips, ip, mac):
    """Record ip -> mac in both indexes (idempotent)."""
    previous = ips.get(ip)
    if previous is not None and previous != mac:
        old = macs.get(previous)
        if old is not None and ip in old["ips"]:
            old["ips"] = [i for i in old["ips"] if i != ip]
    ips[ip] = mac
    entry = macs.setdefault(mac, {"ips": []})
    if ip not in entry["ips"]:
        entry["ips"] = sorted(entry["ips"] + [ip])


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"] (epoch seconds) and no signal depends on
    it. State absorbs every reading; only a MAC never seen
    before (new_neighbor) and an IP answering from new
    hardware (mac_moved) file.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "wire_arrivals"
    learn = tunables.get("learn_first_pass")
    learn_first_pass = learn if isinstance(learn, bool) else True
    baseline = not state["learned"] and learn_first_pass
    neighbors = readings.get("neighbors")
    if not isinstance(neighbors, list):
        neighbors = []

    records = []
    for entry in neighbors:
        if not isinstance(entry, dict):
            continue
        ip = entry.get("ip")
        mac = entry.get("mac")
        if not isinstance(ip, str) or not ip \
                or not isinstance(mac, str) or not mac:
            continue
        iface = entry.get("iface")
        records.append({"ip": ip, "mac": mac.lower(),
                        "iface": iface if isinstance(iface, str) else ""})
    records.sort(key=lambda r: (r["ip"], r["mac"]))

    macs = {mac: {"ips": list(rec["ips"])}
            for mac, rec in state["macs"].items()}
    ips = dict(state["ips"])
    alerts = []
    for rec in records:
        if baseline:
            _absorb(macs, ips, rec["ip"], rec["mac"])
            continue
        old_mac = ips.get(rec["ip"])
        if old_mac is not None and old_mac != rec["mac"]:
            alerts.append({
                "sensor": sensor, "signal": "mac_moved",
                "severity": "high",
                "title": f"{rec['ip']} now answers from "
                         f"{rec['mac']} (was {old_mac})",
                "detail": {"ip": rec["ip"], "old_mac": old_mac,
                           "new_mac": rec["mac"],
                           "iface": rec["iface"]},
            })
        elif rec["mac"] not in macs:
            alerts.append({
                "sensor": sensor, "signal": "new_neighbor",
                "severity": "medium",
                "title": f"new neighbor {rec['ip']} at {rec['mac']}",
                "detail": {"ip": rec["ip"], "mac": rec["mac"],
                           "iface": rec["iface"]},
            })
        _absorb(macs, ips, rec["ip"], rec["mac"])
    return alerts, {"learned": True, "macs": macs, "ips": ips}


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
        print(f"wire-arrivals: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"wire-arrivals: no signing secret in ${args.secret_env}; "
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
            print(f"wire-arrivals: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"wire-arrivals: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Wire Arrivals extension watcher: read the "
                    "neighbor table once and file sensor alert "
                    "payloads for new and moved hardware.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".wire-arrivals-state.json"),
                    help="state file (default: .wire-arrivals-state.json "
                         "next to this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the platform (trying the sense "
                         "against a known table, on any box)")
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
        print(f"wire-arrivals: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"wire-arrivals: cannot read readings "
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
            print(f"wire-arrivals: {len(alerts) - delivered} of "
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
        print(f"wire-arrivals: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
