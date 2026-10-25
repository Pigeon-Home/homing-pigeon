#!/usr/bin/env python3
"""Suricata Feed: a Homing Pigeon user extension (example sense).

Feeds the Oracle the detections in Suricata's eve.json.
Suricata is a network IDS: it watches traffic on an interface
and appends one JSON object per event to eve.json -- the
log_paths tunable, default /var/log/suricata/eve.json. Most of
eve.json is traffic, not detection: http, tls, dns, flow,
fileinfo, and stats events describe what passed, in volume.
This sense tails the file and files only the two event types
that are Suricata saying something is wrong, per distinct
episode, as the two signals declared in extension.json:

- suricata_alert   an "alert" event: a signature matched.
                   Suricata's own severity drives the signal's
                   -- 1 is high, 2 is medium, 3 is info. An
                   episode is one signature_id from one
                   src_ip to one dest_ip.
- suricata_anomaly an "anomaly" event: the decoder or a
                   protocol parser reported malformed or
                   unexpected traffic (severity medium). An
                   episode is one distinct anomaly.event.

Every other event_type parses to nothing and is ignored.
That is a deliberate choice, not an omission: the traffic
types are a flow record, and filing them would hand the
Oracle a transcript instead of a detection. A sense that
wants flows should say so in its own manifest, not borrow
this one's.

One episode files once, stays quiet while it keeps firing,
and files again only when a new distinct episode appears,
when episode_cooldown_sec has passed since it filed, or
after it has cleared -- gone quiet for episode_cooldown_sec
-- and returned. Malformed lines -- non-JSON, an alert
without a usable signature_id or a severity outside 1..3, an
anomaly without an event name -- parse to nothing.

The machinery is the log tailer's, like Failed Login Watch:
main() owns the offsets -- the state dict carries a "_reader"
sub-dict, {path: {"inode", "offset"}}, which the decision
code preserves opaquely and ignores -- and two testable
functions do the reading: read_new_events() tails from those
offsets (a missing file yields no events and keeps its
offset; an inode change or a file that shrank restarts it
from 0), and parse_event() turns one line into one event.
The decision itself is pure: decide() -- readings plus
manifest plus last pass's state, out come alerts and the new
state -- consumes readings only, and events are processed in
timestamp order. Current time arrives as readings["now"];
decide() never reads a clock.

Two fixture modes feed decide() without touching a live log:
--readings FILE reads a readings dict ({"now", "events"})
from JSON, and --log-file FILE parses a whole fixture log
from offset 0, ignoring the reader offsets.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extend/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and signing
and delivery follow the standard senses flow.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

# Suricata's alert severity is inverted against intuition --
# 1 is the most severe -- and the table, not a formula, is
# what keeps that straight at the read site.
_ALERT_SEVERITIES = {1: "high", 2: "medium", 3: "info"}

# Pad or trim to six digits: before 3.11 fromisoformat takes 3 or 6.
_FRACTION_RE = re.compile(r"(:\d{2})\.(\d+)")
_OFFSET_TAIL_RE = re.compile(r"([+-])(\d{2})(\d{2})$")


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


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_ts(value):
    """ISO-8601 text -> epoch float, or None.

    eve.json writes microsecond fractions and offsets in the
    "+0000" form; "Z" and colon offsets are normalized too, so
    the parse does not depend on the running Python's grammar
    extensions. A timestamp with no offset is read as local
    time.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    text = _FRACTION_RE.sub(
        lambda m: m.group(1) + "." + (m.group(2) + "000000")[:6],
        text, count=1)
    text = _OFFSET_TAIL_RE.sub(r"\1\2:\3", text)
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _text(value):
    return value if isinstance(value, str) else ""


def _port(value):
    return value if _is_int(value) and 0 <= value <= 65535 else None


# --- log reading: parse one line, tail from saved offsets ------------

def parse_event(line):
    """One eve.json line -> one event dict, or None.

    Alert events are {"ts": epoch float, "kind": "alert",
    "signature": str, "signature_id": int, "category": str,
    "alert_severity": 1|2|3, "src_ip": str, "src_port":
    int|None, "dest_ip": str, "dest_port": int|None, "proto":
    str}. Anomaly events are {"ts", "kind": "anomaly",
    "anomaly_type": str, "event": str, "layer": str, plus the
    same address fields}. Every other event_type -- the
    traffic that makes up most of eve.json -- answers None by
    design, as do malformed lines.
    """
    if not isinstance(line, str) or not line.strip():
        return None
    try:
        data = json.loads(line)
    except (ValueError, RecursionError):  # nesting deeper than the C stack
        return None
    if not isinstance(data, dict):
        return None
    kind = data.get("event_type")
    if kind not in ("alert", "anomaly"):
        return None
    ts = _parse_ts(data.get("timestamp"))
    if ts is None:
        return None
    event = {"ts": ts, "kind": kind,
             "src_ip": _text(data.get("src_ip")),
             "src_port": _port(data.get("src_port")),
             "dest_ip": _text(data.get("dest_ip")),
             "dest_port": _port(data.get("dest_port")),
             "proto": _text(data.get("proto"))}
    if kind == "alert":
        alert = data.get("alert")
        if not isinstance(alert, dict):
            return None
        signature_id = alert.get("signature_id")
        severity = alert.get("severity")
        if not _is_int(signature_id) or not _is_int(severity) \
                or severity not in _ALERT_SEVERITIES:
            return None
        event.update({
            "signature": _text(alert.get("signature")),
            "signature_id": signature_id,
            "category": _text(alert.get("category")),
            "alert_severity": severity})
    else:
        anomaly = data.get("anomaly")
        if not isinstance(anomaly, dict):
            return None
        name = anomaly.get("event")
        if not isinstance(name, str) or not name:
            return None
        event.update({
            "anomaly_type": _text(anomaly.get("type")),
            "event": name,
            "layer": _text(anomaly.get("layer"))})
    return event


def read_new_events(paths, reader_state):
    """Tail each path from its saved offset.

    Returns (events, new_reader_state). A missing or unreadable
    file yields no events and keeps its previous offset entry;
    an inode change or a file smaller than its saved offset
    (rotation, truncation) restarts that file from 0. Events
    come back in timestamp order.
    """
    if not isinstance(reader_state, dict):
        reader_state = {}
    events = []
    new_reader = {}
    if not isinstance(paths, (list, tuple)):
        paths = []
    for path in paths:
        if not isinstance(path, str) or not path:
            continue
        prev = reader_state.get(path)
        prev_inode = prev.get("inode") if isinstance(prev, dict) else None
        prev_offset = prev.get("offset") if isinstance(prev, dict) else None
        have_prev = isinstance(prev_inode, int) \
            and not isinstance(prev_inode, bool) \
            and isinstance(prev_offset, int) \
            and not isinstance(prev_offset, bool) and prev_offset >= 0
        try:
            st = os.stat(path)
        except OSError:
            if have_prev:
                new_reader[path] = {"inode": prev_inode,
                                    "offset": prev_offset}
            continue
        offset = prev_offset if have_prev and prev_inode == st.st_ino \
            and prev_offset <= st.st_size else 0
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                lines = fh.readlines()
                new_offset = fh.tell()
        except OSError:
            if have_prev:
                new_reader[path] = {"inode": prev_inode,
                                    "offset": prev_offset}
            continue
        for line in lines:
            event = parse_event(line)
            if event is not None:
                events.append(event)
        new_reader[path] = {"inode": st.st_ino, "offset": new_offset}
    events.sort(key=lambda e: e["ts"])
    return events, new_reader


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"episodes": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    episodes = state.get("episodes")
    if not isinstance(episodes, dict):
        episodes = {}
    clean = {}
    for key, entry in episodes.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            continue
        filed = entry.get("filed_at")
        seen = entry.get("last_seen")
        if not _is_number(filed) or not _is_number(seen):
            continue
        clean[key] = {"filed_at": float(filed),
                      "last_seen": float(seen)}
    out = {"episodes": clean}
    # The reader offsets ride along opaquely: main() owns them,
    # decide() preserves and ignores them.
    reader = state.get("_reader")
    if isinstance(reader, dict):
        out["_reader"] = reader
    return out


def _clean_event(entry):
    if not isinstance(entry, dict):
        return None
    ts = entry.get("ts")
    kind = entry.get("kind")
    if not _is_number(ts) or kind not in ("alert", "anomaly"):
        return None
    event = {"ts": float(ts), "kind": kind,
             "src_ip": _text(entry.get("src_ip")),
             "src_port": _port(entry.get("src_port")),
             "dest_ip": _text(entry.get("dest_ip")),
             "dest_port": _port(entry.get("dest_port")),
             "proto": _text(entry.get("proto"))}
    if kind == "alert":
        signature_id = entry.get("signature_id")
        severity = entry.get("alert_severity")
        if not _is_int(signature_id) or not _is_int(severity) \
                or severity not in _ALERT_SEVERITIES:
            return None
        event.update({
            "signature": _text(entry.get("signature")),
            "signature_id": signature_id,
            "category": _text(entry.get("category")),
            "alert_severity": severity})
    else:
        name = entry.get("event")
        if not isinstance(name, str) or not name:
            return None
        event.update({
            "anomaly_type": _text(entry.get("anomaly_type")),
            "event": name,
            "layer": _text(entry.get("layer"))})
    return event


def _episode_key(event):
    if event["kind"] == "alert":
        return "alert|%d|%s|%s" % (event["signature_id"],
                                   event["src_ip"], event["dest_ip"])
    return "anomaly|" + event["event"]


def _alert_for(event, sensor):
    if event["kind"] == "alert":
        title = (f"Suricata alert {event['signature'] or '?'} "
                 f"({event['src_ip']} -> {event['dest_ip']}:"
                 f"{event['dest_port']})")
        return {"sensor": sensor, "signal": "suricata_alert",
                "severity": _ALERT_SEVERITIES[event["alert_severity"]],
                "title": title,
                "detail": {"signature": event["signature"],
                           "signature_id": event["signature_id"],
                           "category": event["category"],
                           "severity": event["alert_severity"],
                           "src_ip": event["src_ip"],
                           "src_port": event["src_port"],
                           "dest_ip": event["dest_ip"],
                           "dest_port": event["dest_port"],
                           "proto": event["proto"]}}
    title = (f"Suricata anomaly {event['event']} "
             f"({event['src_ip']} -> {event['dest_ip']}:"
             f"{event['dest_port']})")
    return {"sensor": sensor, "signal": "suricata_anomaly",
            "severity": "medium",
            "title": title,
            "detail": {"event": event["event"],
                       "type": event["anomaly_type"],
                       "layer": event["layer"],
                       "src_ip": event["src_ip"],
                       "src_port": event["src_port"],
                       "dest_ip": event["dest_ip"],
                       "dest_port": event["dest_port"],
                       "proto": event["proto"]}}


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"]. An event files when its episode is new
    (alert: signature_id + src_ip + dest_ip; anomaly: the
    distinct anomaly.event), or when episode_cooldown_sec has
    passed since the episode last filed; an episode whose last
    sighting is episode_cooldown_sec or more behind "now" is
    cleared from the state, so its return files as a new
    episode.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "suricata_feed"
    cooldown = tunables.get("episode_cooldown_sec")
    cooldown = float(cooldown) if _is_number(cooldown) and cooldown > 0 \
        else 3600.0

    events = []
    raw_events = readings.get("events")
    if isinstance(raw_events, list):
        for entry in raw_events:
            event = _clean_event(entry)
            if event is not None:
                events.append(event)
    events.sort(key=lambda e: e["ts"])
    now = readings.get("now")
    now = float(now) if _is_number(now) else (
        events[-1]["ts"] if events else 0.0)

    alerts = []
    episodes = state["episodes"]
    for event in events:
        key = _episode_key(event)
        entry = episodes.get(key)
        if entry is not None and event["ts"] - entry["filed_at"] < cooldown:
            entry["last_seen"] = event["ts"]
            continue
        alerts.append(_alert_for(event, sensor))
        episodes[key] = {"filed_at": event["ts"],
                         "last_seen": event["ts"]}
    for key in list(episodes):
        if now - episodes[key]["last_seen"] >= cooldown:
            del episodes[key]
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
        print(f"suricata-feed: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"suricata-feed: no signing secret in "
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
            print(f"suricata-feed: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"suricata-feed: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Suricata Feed extension watcher: tail "
                    "Suricata's eve.json once and file sensor "
                    "alert payloads for alert and anomaly events.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".suricata-feed-state.json"),
                    help="state file (default: "
                         ".suricata-feed-state.json next to "
                         "this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the logs (trying the sense "
                         "against known readings, on any box)")
    ap.add_argument("--log-file", default=None,
                    help="parse this whole log file from offset 0 "
                         "as a fixture, ignoring the reader offsets")
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
        print(f"suricata-feed: cannot read manifest "
              f"{args.manifest}: {e}", file=sys.stderr)
        return 2
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    state = _fresh_state()
    try:
        with open(args.state, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        pass
    new_reader = None
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"suricata-feed: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    elif args.log_file:
        now = time.time()
        try:
            with open(args.log_file, encoding="utf-8",
                      errors="replace") as fh:
                lines = fh.readlines()
        except OSError as e:
            print(f"suricata-feed: cannot read log file "
                  f"{args.log_file}: {e}", file=sys.stderr)
            return 2
        events = [ev for ev in (parse_event(ln) for ln in lines)
                  if ev is not None]
        readings = {"now": now, "events": events}
    else:
        paths = tunables.get("log_paths")
        if not isinstance(paths, list) or not paths:
            paths = ["/var/log/suricata/eve.json"]
        reader = state.get("_reader") if isinstance(state, dict) else None
        events, new_reader = read_new_events(paths, reader or {})
        readings = {"now": time.time(), "events": events}
    alerts, state = decide(readings, manifest, state)
    if new_reader is not None:
        # main() owns the offsets; decide() only preserved the
        # old ones. They advance only when the state is saved
        # below, after successful delivery.
        state["_reader"] = new_reader
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so
            # the offsets do not advance and the next pass
            # re-reads these log lines.
            print(f"suricata-feed: {len(alerts) - delivered} of "
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
        print(f"suricata-feed: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
