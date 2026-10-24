#!/usr/bin/env python3
"""Falco Feed: a Homing Pigeon user extension (example sense).

Feeds the Oracle the alerts Falco already decided were worth
writing. Falco is a runtime security monitor: its rules watch
syscalls, containers, and the kernel's behaviour, and with its
file output enabled it appends one JSON object per alert to a
file. This sense tails the file named in the log_paths tunable
(default /var/log/falco/falco.json, where a deploy points
Falco's file_output) and files, per distinct episode, the two
signals declared in extension.json:

- falco_critical a rule fired at Emergency, Alert, Critical,
                  or Error priority (severity high)
- falco_warning  a rule fired at Warning or Notice priority
                  (severity medium)

An episode is one rule plus a digest of the alert's
output_fields: the same rule firing against a different
process, file, or container digests differently, so it is a
different episode and files on its own. One episode files
once, stays quiet while it keeps firing, and files again only
when a new distinct episode appears, when
episode_cooldown_sec has passed since it filed, or after it
has cleared -- gone quiet for episode_cooldown_sec -- and
returned.

Informational and Debug alerts are parsed (they reach the
event stream, so a fixture can prove they were seen) but never
file: at those priorities Falco is a firehose, and a sense
that files them all teaches the Oracle to ignore the sense.
A priority outside Falco's eight documented names makes the
line malformed, and malformed lines -- non-JSON, missing or
unparseable fields -- parse to nothing and are ignored.

One honest caveat, stated in the README as well: Falco's
function depends on kernel privileges an installer cannot
guarantee. An install can succeed while the kernel denies the
driver or the BPF program, leaving Falco present and silently
non-functional; this sense then tails a file that never
grows, which is quiet, not an error it can see.

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
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime

# Priority -> (signal, severity). Informational and Debug are
# deliberately absent: parsed, never filed (see the docstring).
_PRIORITY_SIGNALS = {
    "Emergency": ("falco_critical", "high"),
    "Alert": ("falco_critical", "high"),
    "Critical": ("falco_critical", "high"),
    "Error": ("falco_critical", "high"),
    "Warning": ("falco_warning", "medium"),
    "Notice": ("falco_warning", "medium"),
}
_PARSED_ONLY = ("Informational", "Debug")

_FRACTION_RE = re.compile(r"(\.\d{6})\d+")
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


def _parse_ts(value):
    """ISO-8601 text -> epoch float, or None.

    Falco writes nanosecond fractions and offsets in either
    form ("-07:00", "+0000", "Z"); all are normalized before
    fromisoformat sees them, so the parse does not depend on
    the running Python's grammar extensions. A timestamp with
    no offset is read as local time.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    text = _FRACTION_RE.sub(r"\1", text, count=1)
    text = _OFFSET_TAIL_RE.sub(r"\1\2:\3", text)
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _fields_digest(output_fields):
    """Stable digest of one alert's output_fields.

    The episode key's second half. JSON with sorted keys makes
    the digest a function of the fields' content, not of the
    order Falco happened to serialize them in.
    """
    text = json.dumps(output_fields, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False,
                      default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- log reading: parse one line, tail from saved offsets ------------

def parse_event(line):
    """One Falco JSON line -> one event dict, or None.

    Events are {"ts": epoch float, "rule": str, "priority":
    str, "signal": the declared signal name or None for the
    parsed-only priorities, "output": str, "output_fields":
    dict, "fields_digest": str, "hostname": str}. A line that
    is not a JSON object, has no usable timestamp or rule, or
    names a priority outside Falco's eight answers None; a
    Falco file can carry lines this sense must not invent
    meaning for.
    """
    if not isinstance(line, str) or not line.strip():
        return None
    try:
        data = json.loads(line)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    ts = _parse_ts(data.get("time"))
    rule = data.get("rule")
    priority = data.get("priority")
    if ts is None or not isinstance(rule, str) or not rule:
        return None
    if priority in _PRIORITY_SIGNALS:
        signal = _PRIORITY_SIGNALS[priority][0]
    elif priority in _PARSED_ONLY:
        signal = None
    else:
        return None
    output_fields = data.get("output_fields")
    if not isinstance(output_fields, dict):
        output_fields = {}
    output = data.get("output")
    hostname = data.get("hostname")
    return {"ts": ts, "rule": rule, "priority": priority,
            "signal": signal,
            "output": output if isinstance(output, str) else "",
            "output_fields": output_fields,
            "fields_digest": _fields_digest(output_fields),
            "hostname": hostname if isinstance(hostname, str) else ""}


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
    rule = entry.get("rule")
    priority = entry.get("priority")
    if not _is_number(ts) or not isinstance(rule, str) or not rule:
        return None
    if priority not in _PRIORITY_SIGNALS and priority not in _PARSED_ONLY:
        return None
    output_fields = entry.get("output_fields")
    if not isinstance(output_fields, dict):
        output_fields = {}
    digest = entry.get("fields_digest")
    if not isinstance(digest, str) or not digest:
        digest = _fields_digest(output_fields)
    output = entry.get("output")
    hostname = entry.get("hostname")
    return {"ts": float(ts), "rule": rule, "priority": priority,
            "output": output if isinstance(output, str) else "",
            "output_fields": output_fields,
            "fields_digest": digest,
            "hostname": hostname if isinstance(hostname, str) else ""}


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"]. An event files when its episode (rule +
    output_fields digest) is new, or when episode_cooldown_sec
    has passed since the episode last filed; an episode whose
    last sighting is episode_cooldown_sec or more behind "now"
    is cleared from the state, so its return files as a new
    episode. Parsed-only priorities are consumed and dropped.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "falco_feed"
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
        found = _PRIORITY_SIGNALS.get(event["priority"])
        if found is None:
            continue  # parsed-only priority: seen, never filed
        signal, severity = found
        key = event["rule"] + "|" + event["fields_digest"]
        entry = episodes.get(key)
        if entry is not None and event["ts"] - entry["filed_at"] < cooldown:
            entry["last_seen"] = event["ts"]
            continue
        alerts.append({
            "sensor": sensor, "signal": signal, "severity": severity,
            "title": f"Falco {event['priority']}: {event['rule']} on "
                     f"{event['hostname'] or 'unknown host'}",
            "detail": {"rule": event["rule"],
                       "priority": event["priority"],
                       "hostname": event["hostname"],
                       "output": event["output"],
                       "output_fields": event["output_fields"],
                       "output_fields_digest": event["fields_digest"]}})
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
        print(f"falco-feed: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"falco-feed: no signing secret in "
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
            print(f"falco-feed: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"falco-feed: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Falco Feed extension watcher: tail Falco's "
                    "JSON alert file once and file sensor alert "
                    "payloads for critical and warning rules.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".falco-feed-state.json"),
                    help="state file (default: "
                         ".falco-feed-state.json next to "
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
        print(f"falco-feed: cannot read manifest "
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
            print(f"falco-feed: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    elif args.log_file:
        now = time.time()
        try:
            with open(args.log_file, encoding="utf-8",
                      errors="replace") as fh:
                lines = fh.readlines()
        except OSError as e:
            print(f"falco-feed: cannot read log file "
                  f"{args.log_file}: {e}", file=sys.stderr)
            return 2
        events = [ev for ev in (parse_event(ln) for ln in lines)
                  if ev is not None]
        readings = {"now": now, "events": events}
    else:
        paths = tunables.get("log_paths")
        if not isinstance(paths, list) or not paths:
            paths = ["/var/log/falco/falco.json"]
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
            print(f"falco-feed: {len(alerts) - delivered} of "
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
        print(f"falco-feed: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
