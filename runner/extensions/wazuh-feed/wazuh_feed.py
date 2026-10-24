#!/usr/bin/env python3
"""Wazuh Feed: a Homing Pigeon user extension (example sense).

Wazuh evaluates its rules on the manager, and its alerts
live there too, in the manager's alerts.json. There is no
on-box artifact: a standalone Wazuh agent on this machine
produces nothing consumable at all. This adapter therefore
consumes an alerts.json file WHERE THE OWNER PLACES ONE --
a manager export, an API pull that lands on this box, a
mounted share, or the manager's own file when this box is
co-located with a manager. The log_paths tunable defaults
to the manager's own path, /var/ossec/logs/alerts/alerts.json,
so it works out of the box exactly in that co-located case.

It tails that file incrementally, in the Failed Login Watch
shape: main() owns the offsets -- the state dict carries a
"_reader" sub-dict, {path: {"inode", "offset"}}, which the
decision code preserves opaquely and ignores -- and two
testable functions do the reading: read_new_events() tails
from those offsets (an inode change or a file that shrank
restarts it from 0), and parse_event() turns one alerts.json
line into one event. A missing file is a quiet no-op,
forever: it yields no events, keeps its offset, and is never
an error and never a state complaint -- on a box with a
standalone agent and no manager, that absence is the normal
case, not a fault.

An alerts.json line (the manager's documented shape) is one
JSON object:

    {"timestamp": "2026-10-18T12:00:00.000+0000",
     "rule": {"id": "5710", "level": 5,
              "description": "...", "groups": ["..."]},
     "agent": {"id": "001", "name": "..."},
     "decoder": {"name": "..."}, "data": {...},
     "full_log": "...", "location": "..."}

parse_event() keeps the fields the signals are decided over
-- rule id, level, description, and groups, the agent's id
and name, and the timestamp as an epoch float -- and answers
None for anything that is not that shape. Everything else
in the line is the manager's business, not this sense's.

The decision is the pure shape the other examples use:
decide() -- readings plus manifest plus last pass's state,
out come alerts and the new state -- consumes readings only,
and events are processed in timestamp order. It files the
two signals declared in extension.json:

- wazuh_alert_high  rule.level at least 10 (high severity)
- wazuh_alert       rule.level from 5 to 9 (medium severity)

Levels below 5 are parsed and never filed: at manager
volume they are the background hum, and a sense that filed
them would train the operator to ignore it. An episode is
one (rule.id, agent.name) pair: the first alert of an
episode files, repeats are suppressed while the episode is
active, and the episode re-arms once episode_quiet_sec has
passed with no further alert for that pair -- so a rule
that fires again next week files again, and a rule firing
every minute files once an hour, not sixty times.

One fixture mode feeds decide() without touching a live
file: --readings FILE reads a readings dict ({"now",
"events"}) from JSON.

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
from datetime import datetime, timezone

_TZ_TAIL_RE = re.compile(r"([+-]\d{2})(\d{2})$")


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


# --- log reading: parse one line, tail from saved offsets ------------

def _parse_timestamp(value):
    """An alerts.json timestamp -> an epoch float, or None.

    The manager writes ISO 8601, usually with a colon-less
    offset ("2026-10-18T12:00:00.000+0000"); a "Z" suffix and
    a colon offset are accepted too, and a timestamp with no
    offset is read as UTC, which is the manager's own clock
    convention. A plain number is already an epoch.
    """
    if _is_number(value):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    else:
        text = _TZ_TAIL_RE.sub(r"\1:\2", text)
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def parse_event(line):
    """One alerts.json line -> one event dict, or None.

    Events are {"ts", "level", "rule_id", "description",
    "groups", "agent_name", "agent_id"}; "ts" is an epoch
    float, or None when the line's timestamp does not parse
    (the alert is still an alert -- it is ordered last and
    timed by the pass's "now"). Lines that are not JSON, or
    whose rule carries no usable id or level, answer None: an
    alerts file is mostly lines this sense can use, but
    nothing in it is trusted until it parses.
    """
    if not isinstance(line, str):
        return None
    try:
        record = json.loads(line)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    rule = record.get("rule")
    if not isinstance(rule, dict):
        return None
    rule_id = rule.get("id")
    if isinstance(rule_id, int) and not isinstance(rule_id, bool):
        rule_id = str(rule_id)
    if not isinstance(rule_id, str) or not rule_id:
        return None
    level = rule.get("level")
    if isinstance(level, str) and level.strip().isdigit():
        level = int(level.strip())
    if not _is_number(level):
        return None
    description = rule.get("description")
    groups = rule.get("groups")
    agent = record.get("agent")
    if not isinstance(agent, dict):
        agent = {}
    agent_name = agent.get("name")
    agent_id = agent.get("id")
    return {
        "ts": _parse_timestamp(record.get("timestamp")),
        "level": int(level),
        "rule_id": rule_id,
        "description": description if isinstance(description, str) else "",
        "groups": [g for g in groups if isinstance(g, str)]
                  if isinstance(groups, list) else [],
        "agent_name": agent_name if isinstance(agent_name, str) else "",
        "agent_id": agent_id if isinstance(agent_id, str) else "",
    }


def _event_sort_key(event):
    ts = event.get("ts")
    return (ts is None, float(ts) if _is_number(ts) else 0.0)


def read_new_events(paths, reader_state):
    """Tail each path from its saved offset.

    Returns (events, new_reader_state). A missing or unreadable
    file yields no events and keeps its previous offset entry
    -- quietly, and forever: for this sense a missing file is
    the normal standalone-agent case, not an error. An inode
    change or a file smaller than its saved offset (rotation,
    truncation) restarts that file from 0. Events come back
    in timestamp order (untimestamped events last).
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
    events.sort(key=_event_sort_key)
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
        last_seen = entry.get("last_seen")
        if not _is_number(last_seen):
            continue
        filed_at = entry.get("filed_at")
        clean[key] = {
            "last_seen": float(last_seen),
            "filed_at": float(filed_at) if _is_number(filed_at) else None,
            "signal": entry.get("signal")
            if isinstance(entry.get("signal"), str) else "",
        }
    out = {"episodes": clean}
    # The reader offsets ride along opaquely: main() owns them,
    # decide() preserves and ignores them.
    reader = state.get("_reader")
    if isinstance(reader, dict):
        out["_reader"] = reader
    return out


def _clean_event(value):
    if not isinstance(value, dict):
        return None
    level = value.get("level")
    rule_id = value.get("rule_id")
    if not _is_number(level) or not isinstance(rule_id, str) \
            or not rule_id:
        return None
    ts = value.get("ts")
    description = value.get("description")
    groups = value.get("groups")
    agent_name = value.get("agent_name")
    return {
        "ts": float(ts) if _is_number(ts) else None,
        "level": int(level),
        "rule_id": rule_id,
        "description": description if isinstance(description, str) else "",
        "groups": [g for g in groups if isinstance(g, str)]
                  if isinstance(groups, list) else [],
        "agent_name": agent_name if isinstance(agent_name, str) else "",
        "agent_id": value.get("agent_id")
                   if isinstance(value.get("agent_id"), str) else "",
    }


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"], and an event with no usable timestamp is
    timed by it. The first alert of a (rule.id, agent.name)
    episode files; repeats inside the episode are suppressed
    and refresh it; an episode whose last alert is at least
    episode_quiet_sec old -- against the event's own time as
    it is processed, and against "now" at the end -- is over,
    so the next alert for that pair files as a new episode.
    Levels below 5 never file and never touch an episode.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "wazuh_feed"
    quiet = tunables.get("episode_quiet_sec")
    quiet_sec = float(quiet) if _is_number(quiet) and quiet > 0 else 3600.0

    events = []
    raw_events = readings.get("events")
    if isinstance(raw_events, list):
        for entry in raw_events:
            event = _clean_event(entry)
            if event is not None:
                events.append(event)
    events.sort(key=_event_sort_key)
    now = readings.get("now")
    if not _is_number(now):
        stamped = [e["ts"] for e in events if e["ts"] is not None]
        now = stamped[-1] if stamped else 0.0
    now = float(now)

    alerts = []
    episodes = state["episodes"]
    for event in events:
        level = event["level"]
        if level < 5:
            continue  # parsed, never filed -- the background hum
        when = event["ts"] if event["ts"] is not None else now
        key = f"{event['rule_id']}|{event['agent_name']}"
        episode = episodes.get(key)
        if episode is not None \
                and when - episode["last_seen"] < quiet_sec:
            episode["last_seen"] = max(episode["last_seen"], when)
            continue
        if level >= 10:
            signal, severity = "wazuh_alert_high", "high"
        else:
            signal, severity = "wazuh_alert", "medium"
        alerts.append({
            "sensor": sensor, "signal": signal, "severity": severity,
            "title": f"Wazuh rule {event['rule_id']} (level {level}) "
                     f"on {event['agent_name'] or '?'}: "
                     f"{event['description'] or 'no description'}",
            "detail": {"rule_id": event["rule_id"], "level": level,
                       "description": event["description"],
                       "groups": event["groups"],
                       "agent": event["agent_name"],
                       "agent_id": event["agent_id"]}})
        episodes[key] = {"last_seen": when, "filed_at": when,
                         "signal": signal}
    state["episodes"] = {
        key: ep for key, ep in episodes.items()
        if now - ep["last_seen"] < quiet_sec}
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
        print(f"wazuh-feed: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"wazuh-feed: no signing secret in "
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
            print(f"wazuh-feed: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"wazuh-feed: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Wazuh Feed extension watcher: tail the "
                    "alerts.json the owner placed on this box "
                    "once and file sensor alert payloads for "
                    "its high and medium alerts.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".wazuh-feed-state.json"),
                    help="state file (default: "
                         ".wazuh-feed-state.json next to "
                         "this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the alerts file (trying the "
                         "sense against known readings, on any box)")
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
        print(f"wazuh-feed: cannot read manifest "
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
            print(f"wazuh-feed: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    else:
        paths = tunables.get("log_paths")
        if not isinstance(paths, list) or not paths:
            paths = ["/var/ossec/logs/alerts/alerts.json"]
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
            # re-reads these alert lines.
            print(f"wazuh-feed: {len(alerts) - delivered} of "
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
        print(f"wazuh-feed: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
