#!/usr/bin/env python3
"""Airwaves: a Homing Pigeon user extension (example sense).

The Pi's wireless neighborhood watch -- the owner's WCNA /
network-engineering / pen-test heritage as a sense. It reads
the Wi-Fi neighborhood the platform already sees, and the
box's own link, and files the wireless analogs of the wired
spoofing tells: a familiar SSID suddenly radiating from a
new radio is the evil-twin version of a MAC that moved.

Each alert names one of the signals declared in extension.json:

- new_access_point    a BSSID never seen before, broadcasting
                      an SSID the neighborhood has not known
- evil_twin_suspect   a known SSID from a NEW BSSID, or a known
                      AP now advertising WEAKER security than
                      its baseline -- either is what an evil
                      twin looks like from the sidewalk
- access_point_gone   a known AP stayed absent for
                      gone_after_scans successful scans
- link_degraded       the box's own link roamed to a different
                      BSSID, or its signal fell by
                      link_drop_db or more from its reference

This sense is a read-only consumer of the platform's own scan
results. It never associates to a network, never
deauthenticates anyone, and never injects frames; it reads
what the platform has already seen and thinks about it.

The machinery is deliberately boring, in the Pi Health
example's shape. read_live() is the only function that touches
the machine; it returns one readings dict, and decide() --
readings plus manifest plus last pass's state, out come alerts
and the new state -- is pure, so the whole decision surface is
testable with recorded neighborhoods. The current time
arrives as readings["now"]; decide() never reads a clock. The
scan parsers (parse_nmcli, parse_iw_scan, parse_iw_link) and
security_rank() are pure too, and separately testable.

Scan sources, in order, all capability-based and guarded --
a missing binary, a nonzero exit or a timeout falls through
to the next source, and no source at all is a quiet no-op
pass (scan_ok False), never an error:

1. nmcli cached results: `nmcli -t -f
   BSSID,SSID,CHAN,SIGNAL,SECURITY device wifi list` -- no
   --rescan: this sense reads what the platform has, it does
   not ask the radio to go looking. nmcli's SIGNAL there is
   a percentage; parse_nmcli converts it to approximate dBm
   as signal_pct / 2 - 100, a rough rule of thumb (100% is
   about -50 dBm, 0% about -100 dBm), documented as an
   approximation, not a measurement. In -t mode nmcli
   escapes ":" as "\\:" (in BSSIDs and in SSIDs alike); the
   parser splits on unescaped colons only.
2. iw: `iw dev <iface> scan dump`, when it yields a cached
   dump; the box's own link from `iw dev <iface> link`
   (Connected to <bssid>, signal: -NN dBm, SSID line). The
   link is read via iw whichever scan source supplied the
   neighborhood. <iface> is the iface tunable; empty means
   the first interface `iw dev` names.

Security strings are normalized by security_rank(): open /
"--" / "" is 0, WEP is 1, WPA / PSK is 2, WPA2 is 3, WPA3 /
SAE is 4 -- case-insensitive substring matching, strongest
match wins, so "WPA2 WPA3" ranks 4 and "WPA1 WPA2" ranks 3.

BLE is out of scope: there is no clean stdlib-reachable BLE
advertisement source, so this sense says nothing about
Bluetooth at all.

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
import json
import os
import re
import shutil
import subprocess
import sys
import time


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _tunables(manifest):
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    return tunables if isinstance(tunables, dict) else {}


def _sensor_name(manifest):
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "airwaves"
    return sensor


def _learn_first_pass(manifest):
    value = _tunables(manifest).get("learn_first_pass")
    return value if isinstance(value, bool) else True


def _gone_after_scans(manifest):
    value = _tunables(manifest).get("gone_after_scans")
    if _is_number(value) and int(value) >= 1:
        return int(value)
    return 3


def _link_drop_db(manifest):
    value = _tunables(manifest).get("link_drop_db")
    return float(value) if _is_number(value) and value > 0 else 10.0


# --- security ranking (pure) -------------------------------------------

def security_rank(security_str):
    """Rank a security string: open 0, WEP 1, WPA 2, WPA2 3, WPA3 4.

    Case-insensitive substring matching, strongest match wins:
    WPA3 / SAE outranks WPA2, which outranks plain WPA / PSK;
    WEP is checked after the WPA family so a string naming
    both ranks by its WPA side. Open, "--", "" and anything
    unrecognized rank 0.
    """
    if not isinstance(security_str, str):
        return 0
    low = security_str.lower().strip()
    if not low or low == "--" or "open" in low:
        return 0
    if "wpa3" in low or "sae" in low:
        return 4
    if "wpa2" in low:
        return 3
    if "wep" in low:
        return 1
    if "wpa" in low or "psk" in low:
        return 2
    return 0


# --- scan parsers (pure) -------------------------------------------------

def _split_nmcli_line(line):
    """Split one nmcli -t line on unescaped colons.

    nmcli escapes a literal ":" inside a field as "\\:" and a
    literal backslash as "\\\\"; both are unescaped here.
    """
    fields = []
    buf = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            buf.append(line[i + 1])
            i += 2
            continue
        if ch == ":":
            fields.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    fields.append("".join(buf))
    return fields


def parse_nmcli(text):
    """Parse `nmcli -t -f BSSID,SSID,CHAN,SIGNAL,SECURITY` output.

    Returns a scan list: [{"bssid", "ssid", "channel",
    "signal_dbm", "security"}]. SIGNAL is a percentage in
    nmcli's output; it is converted to approximate dBm as
    signal_pct / 2 - 100 (see the module docstring -- an
    approximation, not a measurement). Malformed lines are
    skipped, never an error.
    """
    scan = []
    if not isinstance(text, str):
        return scan
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        fields = _split_nmcli_line(line)
        if len(fields) < 5:
            continue
        bssid, ssid, chan_s, signal_s, security = fields[:5]
        bssid = bssid.strip().upper()
        if not bssid:
            continue
        if ssid.strip() == "--":
            ssid = ""
        try:
            channel = int(chan_s.strip())
        except ValueError:
            channel = None
        try:
            pct = float(signal_s.strip())
            signal_dbm = pct / 2.0 - 100.0
            if signal_dbm == int(signal_dbm):
                signal_dbm = int(signal_dbm)
        except ValueError:
            signal_dbm = None
        scan.append({
            "bssid": bssid,
            "ssid": ssid,
            "channel": channel,
            "signal_dbm": signal_dbm,
            "security": security.strip(),
        })
    return scan


_BSS_RE = re.compile(r"^BSS\s+([0-9a-fA-F:]+)", re.MULTILINE)


def parse_iw_scan(text):
    """Parse `iw dev <iface> scan dump` output into a scan list.

    Same shape as parse_nmcli's, except iw reports signal in
    real dBm and security is inferred from the capability /
    RSN / WPA lines of each BSS block: RSN with SAE is WPA3,
    RSN is WPA2, a WPA block is WPA, Privacy with neither is
    WEP, and no Privacy is open ("--").
    """
    scan = []
    if not isinstance(text, str) or "BSS " not in text:
        return scan
    parts = _BSS_RE.split(text)
    # split yields [prefix, bssid, block, bssid, block, ...]
    for i in range(1, len(parts) - 1, 2):
        bssid = parts[i].strip().upper()
        block = parts[i + 1]
        ssid = ""
        m = re.search(r"^\s*SSID:\s*(.*)$", block, re.MULTILINE)
        if m:
            ssid = m.group(1).strip()
        channel = None
        m = re.search(r"DS Parameter set:\s*channel\s+(\d+)", block)
        if m is None:
            m = re.search(r"primary channel:\s*(\d+)", block)
        if m:
            try:
                channel = int(m.group(1))
            except ValueError:
                channel = None
        signal_dbm = None
        m = re.search(r"signal:\s*(-?\d+(?:\.\d+)?)\s*dBm", block)
        if m:
            try:
                value = float(m.group(1))
                signal_dbm = int(value) if value == int(value) else value
            except ValueError:
                signal_dbm = None
        if "RSN:" in block:
            security = "WPA3" if "SAE" in block else "WPA2"
        elif re.search(r"^\s*WPA:", block, re.MULTILINE):
            security = "WPA"
        elif "Privacy" in block:
            security = "WEP"
        else:
            security = "--"
        scan.append({
            "bssid": bssid,
            "ssid": ssid,
            "channel": channel,
            "signal_dbm": signal_dbm,
            "security": security,
        })
    return scan


def parse_iw_link(text):
    """Parse `iw dev <iface> link` output into a link dict or None.

    "Connected to <bssid>", an "SSID:" line and a "signal:
    -NN dBm" line make a link; "Not connected." (or anything
    without a Connected line) is None.
    """
    if not isinstance(text, str):
        return None
    m = re.search(r"Connected to\s+([0-9a-fA-F:]+)", text)
    if not m:
        return None
    bssid = m.group(1).upper()
    ssid = ""
    ms = re.search(r"^\s*SSID:\s*(.*)$", text, re.MULTILINE)
    if ms:
        ssid = ms.group(1).strip()
    signal_dbm = None
    mg = re.search(r"signal:\s*(-?\d+(?:\.\d+)?)\s*dBm", text)
    if mg:
        try:
            value = float(mg.group(1))
            signal_dbm = int(value) if value == int(value) else value
        except ValueError:
            signal_dbm = None
    return {"bssid": bssid, "ssid": ssid, "signal_dbm": signal_dbm}


# --- the live reads: the only platform-touching code -----------------

def _run(argv, timeout=10):
    """Run a scan tool; its stdout on success, else None.

    Missing binary, nonzero exit, timeout, any OSError: all
    are "this source has nothing to say", answered None.
    """
    exe = shutil.which(argv[0])
    if not exe:
        return None
    try:
        out = subprocess.run([exe] + argv[1:], capture_output=True,
                             text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout or ""


def _discover_iface(manifest):
    iface = _tunables(manifest).get("iface")
    if isinstance(iface, str) and iface.strip():
        return iface.strip()
    text = _run(["iw", "dev"], timeout=5)
    if text:
        m = re.search(r"Interface\s+(\S+)", text)
        if m:
            return m.group(1)
    return ""


def read_live(manifest):
    """One live snapshot of the wireless neighborhood.

    readings = {"now": epoch float, "scan_ok": bool, "scan":
    [{"bssid", "ssid", "channel", "signal_dbm", "security"}],
    "link": {"bssid", "ssid", "signal_dbm"} | None}.
    Capability-based: sources are tried in order (nmcli
    cached results, then a cached iw scan dump; the link via
    iw), and when no source is available the readings carry
    scan_ok False with an empty scan -- a quiet no-op pass,
    never an error.
    """
    readings = {"now": time.time(), "scan_ok": False, "scan": [],
                "link": None}
    text = _run(["nmcli", "-t", "-f", "BSSID,SSID,CHAN,SIGNAL,SECURITY",
                 "device", "wifi", "list"])
    if text is not None:
        readings["scan"] = parse_nmcli(text)
        readings["scan_ok"] = True
    iface = _discover_iface(manifest)
    if not readings["scan_ok"] and iface:
        dump = _run(["iw", "dev", iface, "scan", "dump"])
        if dump is not None and "BSS " in dump:
            readings["scan"] = parse_iw_scan(dump)
            readings["scan_ok"] = True
    if iface:
        link_text = _run(["iw", "dev", iface, "link"], timeout=5)
        if link_text is not None:
            readings["link"] = parse_iw_link(link_text)
    return readings


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"learned": False, "aps": {}, "ssids": {}, "link": None}


def _clean_link(link):
    if not isinstance(link, dict):
        return None
    bssid = link.get("bssid")
    if not isinstance(bssid, str) or not bssid:
        return None
    ref = link.get("signal_ref")
    if not _is_number(ref):
        ref = link.get("signal_dbm")
    return {"bssid": bssid.upper(),
            "signal_ref": float(ref) if _is_number(ref) else None}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    learned = state.get("learned")
    if not isinstance(learned, bool):
        learned = False
    aps = {}
    raw_aps = state.get("aps")
    if isinstance(raw_aps, dict):
        for bssid, info in raw_aps.items():
            if not isinstance(bssid, str) or not bssid \
                    or not isinstance(info, dict):
                continue
            rank = info.get("rank")
            misses = info.get("misses")
            aps[bssid.upper()] = {
                "ssid": info.get("ssid") if isinstance(
                    info.get("ssid"), str) else "",
                "security": info.get("security") if isinstance(
                    info.get("security"), str) else "",
                "rank": int(rank) if _is_number(rank) else 0,
                "misses": int(misses) if _is_number(misses)
                and int(misses) >= 0 else 0,
            }
    ssids = {}
    raw_ssids = state.get("ssids")
    if isinstance(raw_ssids, dict):
        for ssid, info in raw_ssids.items():
            if not isinstance(ssid, str) or not ssid \
                    or not isinstance(info, dict):
                continue
            bssids = info.get("bssids")
            if not isinstance(bssids, list):
                bssids = []
            rank = info.get("rank")
            ssids[ssid] = {
                "bssids": sorted({b.upper() for b in bssids
                                  if isinstance(b, str) and b}),
                "rank": int(rank) if _is_number(rank) else 0,
            }
    return {"learned": learned, "aps": aps, "ssids": ssids,
            "link": _clean_link(state.get("link"))}


def _clean_scan(readings):
    if not isinstance(readings, dict):
        return []
    raw = readings.get("scan")
    if not isinstance(raw, list):
        return []
    scan = []
    seen = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        bssid = entry.get("bssid")
        if not isinstance(bssid, str) or not bssid or bssid.upper() in seen:
            continue
        seen.add(bssid.upper())
        channel = entry.get("channel")
        signal = entry.get("signal_dbm")
        scan.append({
            "bssid": bssid.upper(),
            "ssid": entry.get("ssid") if isinstance(
                entry.get("ssid"), str) else "",
            "channel": int(channel) if _is_number(channel) else None,
            "signal_dbm": float(signal) if _is_number(signal) else None,
            "security": entry.get("security") if isinstance(
                entry.get("security"), str) else "",
        })
    return scan


def _clean_readings_link(readings):
    if not isinstance(readings, dict):
        return None
    link = readings.get("link")
    if not isinstance(link, dict):
        return None
    bssid = link.get("bssid")
    if not isinstance(bssid, str) or not bssid:
        return None
    signal = link.get("signal_dbm")
    return {"bssid": bssid.upper(),
            "ssid": link.get("ssid") if isinstance(
                link.get("ssid"), str) else "",
            "signal_dbm": float(signal) if _is_number(signal) else None}


def _absorb(state, scan, link):
    """Fold a scan + link into the state as the new baseline."""
    for ap in scan:
        state["aps"][ap["bssid"]] = {
            "ssid": ap["ssid"], "security": ap["security"],
            "rank": security_rank(ap["security"]), "misses": 0}
        if ap["ssid"]:
            entry = state["ssids"].setdefault(
                ap["ssid"], {"bssids": [], "rank": 0})
            if ap["bssid"] not in entry["bssids"]:
                entry["bssids"] = sorted(entry["bssids"] + [ap["bssid"]])
            entry["rank"] = max(entry["rank"],
                                security_rank(ap["security"]))
    if link is not None:
        state["link"] = {"bssid": link["bssid"],
                          "signal_ref": link["signal_dbm"]}
    return state


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"] (carried for the uniform readings shape).

    A pass with scan_ok False files nothing and changes
    nothing: no data is not an absence, so misses do NOT
    advance. The learn pass (learn_first_pass, the default)
    absorbs the neighborhood quietly. After that, every scan
    is evaluated FIRST -- new radios, evil-twin tells,
    security downgrades, disappearances, the own link's
    health -- and only then absorbed as the new baseline, so
    a downgrade fires before the baseline learns to expect it.
    """
    state = _clean_state(state)
    sensor = _sensor_name(manifest)
    if not isinstance(readings, dict) or not readings.get("scan_ok"):
        return [], state
    scan = _clean_scan(readings)
    link = _clean_readings_link(readings)
    if not state["learned"]:
        if _learn_first_pass(manifest):
            new_state = _absorb(
                {"learned": True, "aps": {}, "ssids": {},
                 "link": state["link"]}, scan, link)
            # A link seen before learning still seeds the ref.
            if link is None and state["link"] is not None:
                new_state["link"] = state["link"]
            return [], new_state
        state = {"learned": True, "aps": {}, "ssids": {}, "link": None}

    gone_after = _gone_after_scans(manifest)
    drop_db = _link_drop_db(manifest)
    alerts = []
    present = {ap["bssid"] for ap in scan}

    # -- the neighborhood: evaluate before absorbing -------------
    for ap in sorted(scan, key=lambda a: a["bssid"]):
        bssid, ssid = ap["bssid"], ap["ssid"]
        observed_rank = security_rank(ap["security"])
        known_ap = state["aps"].get(bssid)
        if known_ap is not None:
            if observed_rank < known_ap["rank"]:
                detail = {"ssid": ssid, "bssid": bssid,
                          "expected": known_ap["security"],
                          "observed": ap["security"],
                          "expected_rank": known_ap["rank"],
                          "observed_rank": observed_rank,
                          "security": ap["security"]}
                alerts.append({
                    "sensor": sensor, "signal": "evil_twin_suspect",
                    "severity": "high",
                    "title": f"AP {ssid or bssid} ({bssid}) now "
                             f"advertises weaker security "
                             f"{ap['security'] or 'open'} than its "
                             f"baseline {known_ap['security']}",
                    "detail": detail})
            continue
        if ssid and ssid in state["ssids"]:
            known_bssids = list(state["ssids"][ssid]["bssids"])
            detail = {"ssid": ssid, "bssid": bssid,
                      "expected": known_bssids,
                      "observed": ap["security"],
                      "security": ap["security"],
                      "channel": ap["channel"]}
            alerts.append({
                "sensor": sensor, "signal": "evil_twin_suspect",
                "severity": "high",
                "title": f"known SSID {ssid} appeared from new "
                         f"BSSID {bssid}",
                "detail": detail})
            continue
        detail = {"bssid": bssid, "ssid": ssid,
                  "channel": ap["channel"], "security": ap["security"]}
        alerts.append({
            "sensor": sensor, "signal": "new_access_point",
            "severity": "medium",
            "title": f"new access point {ssid or bssid} ({bssid}) "
                     f"on channel {ap['channel']}",
            "detail": detail})

    # -- disappearances -------------------------------------------
    gone = []
    for bssid in sorted(state["aps"]):
        if bssid in present:
            continue
        misses = state["aps"][bssid]["misses"] + 1
        if misses >= gone_after:
            gone.append(bssid)
            detail = {"bssid": bssid,
                      "ssid": state["aps"][bssid]["ssid"],
                      "scans_missed": misses}
            alerts.append({
                "sensor": sensor, "signal": "access_point_gone",
                "severity": "info",
                "title": f"access point "
                         f"{state['aps'][bssid]['ssid'] or bssid} "
                         f"({bssid}) gone after {misses} missed scans",
                "detail": detail})
        else:
            state["aps"][bssid]["misses"] = misses

    # -- the box's own link ----------------------------------------
    new_link = state["link"]
    if link is not None:
        if state["link"] is None:
            new_link = {"bssid": link["bssid"],
                        "signal_ref": link["signal_dbm"]}
        elif state["link"]["bssid"] != link["bssid"]:
            detail = {"old_bssid": state["link"]["bssid"],
                      "new_bssid": link["bssid"],
                      "ssid": link["ssid"],
                      "signal_dbm": link["signal_dbm"]}
            alerts.append({
                "sensor": sensor, "signal": "link_degraded",
                "severity": "medium",
                "title": f"Wi-Fi link roamed from "
                         f"{state['link']['bssid']} to {link['bssid']}",
                "detail": detail})
            new_link = {"bssid": link["bssid"],
                        "signal_ref": link["signal_dbm"]}
        else:
            ref = state["link"]["signal_ref"]
            current = link["signal_dbm"]
            if current is not None and ref is None:
                new_link = {"bssid": link["bssid"], "signal_ref": current}
            elif current is not None and ref is not None:
                if current > ref:
                    new_link = {"bssid": link["bssid"],
                                "signal_ref": current}
                elif current <= ref - drop_db:
                    detail = {"bssid": link["bssid"],
                              "ssid": link["ssid"],
                              "from_dbm": ref, "to_dbm": current}
                    alerts.append({
                        "sensor": sensor, "signal": "link_degraded",
                        "severity": "medium",
                        "title": f"Wi-Fi link signal fell from "
                                 f"{ref:g} dBm to {current:g} dBm",
                        "detail": detail})
                    new_link = {"bssid": link["bssid"],
                                "signal_ref": current}
                else:
                    new_link = state["link"]
            else:
                new_link = state["link"]
    # Link absent (not connected): no link signal, state kept.

    # -- absorb: present APs refresh, gone APs leave --------------
    for bssid in gone:
        ssid = state["aps"][bssid]["ssid"]
        del state["aps"][bssid]
        if ssid and ssid in state["ssids"]:
            entry = state["ssids"][ssid]
            entry["bssids"] = [b for b in entry["bssids"] if b != bssid]
            if not entry["bssids"]:
                del state["ssids"][ssid]
    state = _absorb(state, scan, None)
    state["link"] = new_link
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
        from runner import extensions as hp_extensions
    except ImportError as e:
        print(f"airwaves: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"airwaves: no signing secret in ${args.secret_env}; "
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
            print(f"airwaves: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"airwaves: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Airwaves extension watcher: read the Wi-Fi "
                    "neighborhood once and file sensor alert "
                    "payloads for what changed.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".airwaves-state.json"),
                    help="state file (default: .airwaves-state.json "
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
        print(f"airwaves: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"airwaves: cannot read readings "
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
            print(f"airwaves: {len(alerts) - delivered} of "
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
        print(f"airwaves: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
