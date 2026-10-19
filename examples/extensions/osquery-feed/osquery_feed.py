#!/usr/bin/env python3
"""Osquery Feed: a Homing Pigeon user extension (example sense).

Tails the osqueryd results log named in the log_paths
tunable -- by default /var/log/osquery/osqueryd.results.log
-- and files what the differential results say changed on
the host, as the two signals declared in extension.json:

- osquery_added    a query reported a row as "added"
                   (medium severity for users and listening
                   ports, info for processes)
- osquery_removed  a query reported a row as "removed"
                   (info severity)

Each results line is one JSON object: {"name": the query
name, "hostIdentifier": ..., "unixTime": epoch, "columns":
{... string values ...}, "action": "added"|"removed"}. The
feed serves the installer's light pack, not arbitrary
packs: a query name belongs to kind "process" if it contains
"processes", to kind "user" if it contains "users", and to
kind "listener" if it contains "listening_ports" -- so the
pack's hp_processes, hp_users and hp_listening_ports map,
and so do the bare stock names processes, users and
listening_ports. Lines from any other query are parsed and
ignored, deliberately: an arbitrary pack's rows have no
declared meaning here, and inventing one would file noise.

An event's identity is its identifying columns -- process:
name/pid/path; user: username/uid/gid; listener:
port/protocol/address/pid -- and the episode discipline is
keyed on (kind, action, identity): an add files once, no
matter how many results lines repeat it, until a remove of
the same identity arrives; that remove is a NEW episode
fact and files as osquery_removed, and it re-arms the add,
so a thing that leaves and comes back files both times.
The alert detail carries the kind and the identifying
columns, so the Oracle reads who or what changed, not just
that something did.

The machinery is the log-tailer shape of
failed-login-watch: the files are tailed incrementally. The
state dict carries a "_reader" sub-dict, {path: {"inode",
"offset"}}, which main() owns, decide() preserves opaquely
and ignores, read_new_events() tails from (a missing file
yields no events and keeps its offset; an inode change or a
file that shrank restarts it from 0), and parse_event()
turns one line into one event. The decision itself is the
pure shape the other examples use: decide() -- readings
plus manifest plus last pass's state, out come alerts and
the new state -- consumes readings only, and events are
processed in timestamp order. Current time arrives as
readings["now"]; this sense does not act on it beyond
carrying it, because differential facts do not age out.
Malformed lines -- not JSON, no usable query name, an
action other than added/removed, columns that are not an
object -- answer None, quietly.

Two fixture modes feed decide() without touching a live
log: --readings FILE reads a readings dict ({"now",
"events"}) from JSON, and --log-file FILE parses a whole
fixture results log from offset 0, ignoring the reader
offsets.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload
with this sense's key (read from the environment variable
named by --secret-env) and drops it into the runner's local
inbox, or pushes it to the runner's loopback listener when
--local-port is given. Same envelope, same signature -- only
the transport differs (docs/extensions.md, "Local
delivery"). Without --local-dir it prints one alert payload
per line, and signing and delivery follow the standard
senses flow.
"""

import argparse
import json
import os
import sys
import time

_IDENTITY_COLUMNS = {
    "process": ("name", "pid", "path"),
    "user": ("username", "uid", "gid"),
    "listener": ("port", "protocol", "address", "pid"),
}


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def query_kind(query_name):
    """The kind a query name belongs to, or None.

    Containment, not equality, so the light pack's hp_-
    prefixed names and the bare stock names map alike. Any
    other query is not this feed's business.
    """
    if not isinstance(query_name, str) or not query_name:
        return None
    if "listening_ports" in query_name:
        return "listener"
    if "processes" in query_name:
        return "process"
    if "users" in query_name:
        return "user"
    return None


def _identity_for(kind, columns):
    """The identifying columns for a kind, as a small dict.

    Only columns actually present are carried; a row with
    none of its kind's identifying columns falls back to its
    whole column set, so it still has a stable identity.
    """
    wanted = _IDENTITY_COLUMNS.get(kind) or ()
    identity = {k: columns[k] for k in wanted if k in columns}
    return identity if identity else dict(columns)


# --- log reading: parse one line, tail from saved offsets ------------


def parse_event(line):
    """One results line -> one event dict, or None.

    Events are {"ts": epoch float, "kind":
    "process"|"user"|"listener"|None, "action":
    "added"|"removed", "query": the query name, "host": the
    hostIdentifier or "", "columns": {...}, "identity":
    {...}}. A well-formed line from a query outside the
    light pack parses to an event whose kind is None --
    parsed, and ignored by read_new_events() and decide().
    A malformed line answers None.
    """
    if not isinstance(line, str):
        return None
    text = line.strip()
    if not text:
        return None
    try:
        row = json.loads(text)
    except ValueError:
        return None
    if not isinstance(row, dict):
        return None
    name = row.get("name")
    action = row.get("action")
    ts = row.get("unixTime")
    columns = row.get("columns")
    if not isinstance(name, str) or not name:
        return None
    if action not in ("added", "removed"):
        return None
    if not _is_number(ts) or not isinstance(columns, dict):
        return None
    clean_columns = {
        k: v for k, v in columns.items() if isinstance(k, str) and isinstance(v, str)
    }
    kind = query_kind(name)
    host = row.get("hostIdentifier")
    return {
        "ts": float(ts),
        "kind": kind,
        "action": action,
        "query": name,
        "host": host if isinstance(host, str) else "",
        "columns": clean_columns,
        "identity": _identity_for(kind, clean_columns) if kind else {},
    }


def read_new_events(paths, reader_state):
    """Tail each path from its saved offset.

    Returns (events, new_reader_state). A missing or unreadable
    file yields no events and keeps its previous offset entry;
    an inode change or a file smaller than its saved offset
    (rotation, truncation) restarts that file from 0. Events
    from queries outside the light pack are parsed and
    dropped here. Events come back in timestamp order.
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
        have_prev = (
            isinstance(prev_inode, int)
            and not isinstance(prev_inode, bool)
            and isinstance(prev_offset, int)
            and not isinstance(prev_offset, bool)
            and prev_offset >= 0
        )
        try:
            st = os.stat(path)
        except OSError:
            if have_prev:
                new_reader[path] = {"inode": prev_inode, "offset": prev_offset}
            continue
        offset = (
            prev_offset
            if have_prev and prev_inode == st.st_ino and prev_offset <= st.st_size
            else 0
        )
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                lines = fh.readlines()
                new_offset = fh.tell()
        except OSError:
            if have_prev:
                new_reader[path] = {"inode": prev_inode, "offset": prev_offset}
            continue
        for line in lines:
            event = parse_event(line)
            if event is not None and event["kind"] is not None:
                events.append(event)
        new_reader[path] = {"inode": st.st_ino, "offset": new_offset}
    events.sort(key=lambda e: e["ts"])
    return events, new_reader


# --- the decision: readings in, signals out (pure) --------------------


def _fresh_state():
    return {"filed": []}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    filed = state.get("filed")
    filed = [k for k in filed if isinstance(k, str)] if isinstance(filed, list) else []
    out = {"filed": filed}
    # The reader offsets ride along opaquely: main() owns them,
    # decide() preserves and ignores them.
    reader = state.get("_reader")
    if isinstance(reader, dict):
        out["_reader"] = reader
    return out


def _episode_key(kind, action, identity):
    return json.dumps(
        {"kind": kind, "action": action, "identity": identity}, sort_keys=True
    )


def _identity_label(kind, identity):
    """A short human label for an identity, for alert titles."""
    if kind == "process":
        label = identity.get("name") or "?"
        if identity.get("pid"):
            label += f" (pid {identity['pid']})"
        return label
    if kind == "user":
        return identity.get("username") or identity.get("uid") or "?"
    if kind == "listener":
        label = f"{identity.get('address') or '*'}:{identity.get('port') or '?'}"
        if identity.get("protocol"):
            label += f"/{identity['protocol']}"
        return label
    return "?"


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"] and is not acted on; a differential fact
    files when it is first seen, not when it is recent. Each
    (kind, action, identity) files once per episode: filing
    an add disarms the matching remove key and vice versa, so
    the opposite action of the same identity is always a new
    fact, and a repeat of the same action is not.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "osquery_feed"
    cap = tunables.get("filed_cap")
    cap = int(cap) if _is_number(cap) and cap >= 1 else 10000

    events = []
    raw_events = readings.get("events")
    if isinstance(raw_events, list):
        for entry in raw_events:
            if not isinstance(entry, dict):
                continue
            ts = entry.get("ts")
            action = entry.get("action")
            if not _is_number(ts) or action not in ("added", "removed"):
                continue
            kind = entry.get("kind")
            if kind not in _IDENTITY_COLUMNS:
                kind = query_kind(entry.get("query"))
            if kind is None:
                continue
            columns = entry.get("columns")
            columns = (
                {
                    k: v
                    for k, v in columns.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
                if isinstance(columns, dict)
                else {}
            )
            identity = entry.get("identity")
            if not isinstance(identity, dict) or not identity:
                identity = _identity_for(kind, columns)
            identity = {
                k: v
                for k, v in identity.items()
                if isinstance(k, str) and isinstance(v, str)
            }
            if not identity:
                identity = _identity_for(kind, columns)
            if not identity:
                continue
            query = entry.get("query")
            host = entry.get("host")
            events.append(
                {
                    "ts": float(ts),
                    "kind": kind,
                    "action": action,
                    "query": query if isinstance(query, str) else "",
                    "host": host if isinstance(host, str) else "",
                    "identity": identity,
                }
            )
    events.sort(key=lambda e: e["ts"])

    filed = list(state["filed"])
    filed_set = set(filed)
    alerts = []
    for event in events:
        kind = event["kind"]
        action = event["action"]
        identity = event["identity"]
        key = _episode_key(kind, action, identity)
        if key in filed_set:
            continue
        other = "removed" if action == "added" else "added"
        other_key = _episode_key(kind, other, identity)
        if action == "added":
            severity = "medium" if kind in ("user", "listener") else "info"
            signal = "osquery_added"
        else:
            severity = "info"
            signal = "osquery_removed"
        detail = {"kind": kind, "action": action}
        detail.update(identity)
        if event["query"]:
            detail["query"] = event["query"]
        if event["host"]:
            detail["host"] = event["host"]
        alerts.append(
            {
                "sensor": sensor,
                "signal": signal,
                "severity": severity,
                "title": f"osquery {kind} {action}: {_identity_label(kind, identity)}",
                "detail": detail,
            }
        )
        filed.append(key)
        filed_set.add(key)
        if other_key in filed_set:
            filed_set.discard(other_key)
            filed.remove(other_key)
        while len(filed) > cap:
            filed_set.discard(filed.pop(0))
    state["filed"] = filed
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
    repo_root = os.path.normpath(os.path.join(here, "..", "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from runner import extensions as hp_extensions
    except ImportError as e:
        print(
            f"osquery-feed: local delivery needs the "
            f"homing-pigeon repo importable ({e}); run me from "
            f"a clone",
            file=sys.stderr,
        )
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(
            f"osquery-feed: no signing secret in "
            f"${args.secret_env}; set it to this sense's key "
            f"secret",
            file=sys.stderr,
        )
        return None
    delivered = 0
    for alert in alerts:
        payload = hp_extensions.build_sensor_alert(
            alert["sensor"],
            alert["severity"],
            alert["title"],
            key_id=args.key_id,
            signal=alert.get("signal"),
            detail=alert.get("detail"),
        )
        try:
            if args.local_port:
                hp_extensions.send_local_signal(payload, secret, port=args.local_port)
                where = f"127.0.0.1:{args.local_port}"
            else:
                where = hp_extensions.drop_local_signal(args.local_dir, payload, secret)
        except (OSError, ValueError) as e:
            print(
                f"osquery-feed: delivery failed for {alert.get('signal')}: {e}",
                file=sys.stderr,
            )
            continue
        delivered += 1
        print(f"osquery-feed: filed {alert.get('signal')} via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Osquery Feed extension watcher: tail the "
        "osqueryd results log once and file sensor "
        "alert payloads for the processes, users "
        "and listening ports the light pack reports "
        "as added or removed."
    )
    ap.add_argument(
        "--manifest",
        default=os.path.join(here, "extension.json"),
        help="extension.json to read tunables from",
    )
    ap.add_argument(
        "--state",
        default=os.path.join(here, ".osquery-feed-state.json"),
        help="state file (default: .osquery-feed-state.json next to this script)",
    )
    ap.add_argument(
        "--readings",
        default=None,
        help="read the readings dict from this JSON file "
        "instead of the logs (trying the sense "
        "against known readings, on any box)",
    )
    ap.add_argument(
        "--log-file",
        default=None,
        help="parse this whole results log file from "
        "offset 0 as a fixture, ignoring the "
        "reader offsets",
    )
    ap.add_argument(
        "--local-dir",
        default=None,
        help="runner base dir: deliver alerts locally "
        "(signed, into its local inbox) instead of "
        "printing payloads",
    )
    ap.add_argument(
        "--local-port",
        type=int,
        default=None,
        help="with --local-dir: push to the runner's "
        "loopback listener on this port instead of "
        "dropping files",
    )
    ap.add_argument(
        "--key-id",
        default="",
        help="key id this sense signs as (its "
        "sensors.<name>.key_id in the runner config)",
    )
    ap.add_argument(
        "--secret-env",
        default="HOMING_PIGEON_SENSOR_SECRET",
        help="environment variable holding the signing "
        "secret (default: HOMING_PIGEON_SENSOR_SECRET)",
    )
    args = ap.parse_args(argv)
    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as e:
        print(
            f"osquery-feed: cannot read manifest {args.manifest}: {e}", file=sys.stderr
        )
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
            print(
                f"osquery-feed: cannot read readings {args.readings}: {e}",
                file=sys.stderr,
            )
            return 2
    elif args.log_file:
        if not os.path.isfile(args.log_file):
            print(
                f"osquery-feed: cannot read log file {args.log_file}: no such file",
                file=sys.stderr,
            )
            return 2
        events, _fixture_reader = read_new_events([args.log_file], {})
        now = events[-1]["ts"] if events else time.time()
        readings = {"now": now, "events": events}
    else:
        paths = tunables.get("log_paths")
        if not isinstance(paths, list) or not paths:
            paths = ["/var/log/osquery/osqueryd.results.log"]
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
            print(
                f"osquery-feed: {len(alerts) - delivered} of "
                f"{len(alerts)} alert(s) not delivered; state not "
                f"saved, will retry next pass",
                file=sys.stderr,
            )
            return 2
    else:
        for alert in alerts:
            print(json.dumps(alert, sort_keys=True))
    try:
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(state, fh, sort_keys=True)
    except OSError as e:
        print(f"osquery-feed: cannot write state {args.state}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
