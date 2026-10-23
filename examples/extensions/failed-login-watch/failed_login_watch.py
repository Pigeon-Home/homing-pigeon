#!/usr/bin/env python3
"""Failed Login Watch: a Homing Pigeon user extension (example sense).

Watches the authentication logs for the shape a brute-force
run leaves behind -- and, more importantly, for the shape of
one succeeding. It tails the log files named in the log_paths
tunable and files, per source, the two signals declared in
extension.json:

- login_failure_burst      one source accumulated at least
                           burst_count failures inside the
                           trailing window_sec
- login_success_after_burst a successful login from a source
                           whose burst is active (or which has
                           at least burst_count failures inside
                           the trailing window at that moment);
                           filing closes the episode

The patterns it understands are the sshd and PAM lines of the
usual Linux auth logs (/var/log/auth.log, /var/log/secure):

- "Failed password for [invalid user] USER from IP port N ssh2"
- "Accepted password|publickey for USER from IP ..."
- pam_unix(sshd:auth) "authentication failure" lines, whose
  source is reported as "local" (PAM does not vouch for a
  network peer in that line) and whose user comes from the
  user= field when one is present, else ""

Anything else in the log parses to nothing and is ignored.

The machinery differs from the other examples in exactly one
place, because a log is not a snapshot: the files are tailed
incrementally. main() owns the offsets -- the state dict
carries a "_reader" sub-dict, {path: {"inode", "offset"}},
which the decision code preserves opaquely and ignores -- and
two testable functions do the reading: read_new_events() tails
from those offsets (a missing file yields no events and keeps
its offset; an inode change or a file that shrank restarts it
from 0), and parse_event() turns one line into one event. The
decision itself is the pure shape the other examples use:
decide() -- readings plus manifest plus last pass's state,
out come alerts and the new state -- consumes readings only,
and events are processed in timestamp order. Current time
arrives as readings["now"]; decide() never reads a clock.
auth.log timestamps carry no year ("Mon D HH:MM:SS"), so
parse_event() takes the year from its `now` argument.

Two fixture modes feed decide() without touching a live log:
--readings FILE reads a readings dict ({"now", "events"}) from
JSON, and --log-file FILE parses a whole fixture log from
offset 0, ignoring the reader offsets.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extensions.md, "Local delivery"). Without
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

_MONTHS = {name: i + 1 for i, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))}

_TS_RE = re.compile(
    r"^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\b")
_ISO_TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})")
_FAILED_RE = re.compile(
    r"Failed password for (?:invalid user\s+)?(\S+) from (\S+)")
_ACCEPTED_RE = re.compile(
    r"Accepted (?:password|publickey) for (\S+) from (\S+)")
_PAM_RE = re.compile(r"pam_unix\(sshd:auth\): authentication failure")
_USER_FIELD_RE = re.compile(r"(?:^|\s)user=(\S*)")


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

def parse_event(line, now):
    """One log line -> one event dict, or None.

    Events are {"ts": epoch float, "kind": "fail"|"success",
    "source": str, "user": str}. `now` (epoch float) supplies
    the year the syslog timestamp omits. Unparseable lines --
    including lines whose timestamp does not parse -- answer
    None; an auth log is mostly lines this sense ignores.
    """
    if not isinstance(line, str) or not _is_number(now):
        return None
    ts = None
    m = _TS_RE.match(line)
    if m and m.group(1) in _MONTHS:
        try:
            year = datetime.fromtimestamp(float(now)).year
            ts = datetime(year, _MONTHS[m.group(1)], int(m.group(2)),
                          int(m.group(3)), int(m.group(4)),
                          int(m.group(5))).timestamp()
        except (ValueError, OverflowError, OSError):
            return None
    else:
        m = _ISO_TS_RE.match(line)
        if not m:
            return None
        try:
            ts = datetime(*[int(g) for g in m.groups()]).timestamp()
        except ValueError:
            return None
    m = _FAILED_RE.search(line)
    if m:
        return {"ts": float(ts), "kind": "fail",
                "source": m.group(2), "user": m.group(1)}
    m = _ACCEPTED_RE.search(line)
    if m:
        return {"ts": float(ts), "kind": "success",
                "source": m.group(2), "user": m.group(1)}
    if _PAM_RE.search(line):
        user = ""
        um = _USER_FIELD_RE.search(line)
        if um:
            user = um.group(1)
        return {"ts": float(ts), "kind": "fail",
                "source": "local", "user": user}
    return None


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
    now = time.time()
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
            event = parse_event(line, now)
            if event is not None:
                events.append(event)
        new_reader[path] = {"inode": st.st_ino, "offset": new_offset}
    events.sort(key=lambda e: e["ts"])
    return events, new_reader


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"sources": {}}


def _fresh_source():
    return {"fails": [], "burst_active": False, "burst_filed_at": None}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    sources = state.get("sources")
    if not isinstance(sources, dict):
        sources = {}
    clean = {}
    for key, entry in sources.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            continue
        fails = entry.get("fails")
        if not isinstance(fails, list):
            fails = []
        filed = entry.get("burst_filed_at")
        clean[key] = {
            "fails": sorted(float(v) for v in fails if _is_number(v)),
            "burst_active": bool(entry.get("burst_active")),
            "burst_filed_at": float(filed) if _is_number(filed) else None,
        }
    out = {"sources": clean}
    # The reader offsets ride along opaquely: main() owns them,
    # decide() preserves and ignores them.
    reader = state.get("_reader")
    if isinstance(reader, dict):
        out["_reader"] = reader
    return out


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"], and failure timestamps are pruned to the
    trailing window_sec against each event as it is processed
    (in timestamp order) and once more against "now" at the
    end, which is what clears a burst flag whose failures have
    all aged out of the window.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "failed_login_watch"
    burst_count = tunables.get("burst_count")
    burst_count = int(burst_count) \
        if _is_number(burst_count) and burst_count >= 1 else 5
    window = tunables.get("window_sec")
    window_out = window if _is_number(window) and window > 0 else 600
    window_sec = float(window_out)

    events = []
    raw_events = readings.get("events")
    if isinstance(raw_events, list):
        for entry in raw_events:
            if not isinstance(entry, dict):
                continue
            ts = entry.get("ts")
            kind = entry.get("kind")
            source = entry.get("source")
            if not _is_number(ts) or kind not in ("fail", "success"):
                continue
            if not isinstance(source, str) or not source:
                continue
            user = entry.get("user")
            events.append({"ts": float(ts), "kind": kind,
                           "source": source,
                           "user": user if isinstance(user, str) else ""})
    events.sort(key=lambda e: e["ts"])
    now = readings.get("now")
    now = float(now) if _is_number(now) else (
        events[-1]["ts"] if events else 0.0)

    alerts = []
    for event in events:
        src = state["sources"].setdefault(event["source"], _fresh_source())
        floor = event["ts"] - window_sec
        src["fails"] = [f for f in src["fails"] if floor <= f <= event["ts"]]
        if event["kind"] == "fail":
            src["fails"].append(event["ts"])
            src["fails"].sort()
            if len(src["fails"]) >= burst_count \
                    and not src["burst_active"]:
                alerts.append({
                    "sensor": sensor, "signal": "login_failure_burst",
                    "severity": "medium",
                    "title": f"{len(src['fails'])} failed logins from "
                             f"{event['source']} within "
                             f"{window_out:g}s",
                    "detail": {"source": event["source"],
                               "count": len(src["fails"]),
                               "window_sec": window_out}})
                src["burst_active"] = True
                src["burst_filed_at"] = event["ts"]
        else:  # success
            recent = len(src["fails"])
            if src["burst_active"] or recent >= burst_count:
                alerts.append({
                    "sensor": sensor,
                    "signal": "login_success_after_burst",
                    "severity": "high",
                    "title": f"successful login for "
                             f"{event['user'] or '?'} from "
                             f"{event['source']} after "
                             f"{recent} recent failure(s)",
                    "detail": {"source": event["source"],
                               "user": event["user"],
                               "recent_failures": recent}})
                # The episode is closed.
                src["fails"] = []
                src["burst_active"] = False
                src["burst_filed_at"] = None
    floor = now - window_sec
    for src in state["sources"].values():
        src["fails"] = [f for f in src["fails"] if floor <= f <= now]
        if not src["fails"]:
            src["burst_active"] = False
            src["burst_filed_at"] = None
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
        print(f"failed-login-watch: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"failed-login-watch: no signing secret in "
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
            print(f"failed-login-watch: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"failed-login-watch: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Failed Login Watch extension watcher: tail "
                    "the auth logs once and file sensor alert "
                    "payloads for failure bursts and the success "
                    "that follows one.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".failed-login-watch-state.json"),
                    help="state file (default: "
                         ".failed-login-watch-state.json next to "
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
        print(f"failed-login-watch: cannot read manifest "
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
            print(f"failed-login-watch: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    elif args.log_file:
        now = time.time()
        try:
            with open(args.log_file, encoding="utf-8",
                      errors="replace") as fh:
                lines = fh.readlines()
        except OSError as e:
            print(f"failed-login-watch: cannot read log file "
                  f"{args.log_file}: {e}", file=sys.stderr)
            return 2
        events = [ev for ev in (parse_event(ln, now) for ln in lines)
                  if ev is not None]
        readings = {"now": now, "events": events}
    else:
        paths = tunables.get("log_paths")
        if not isinstance(paths, list) or not paths:
            paths = ["/var/log/auth.log", "/var/log/secure"]
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
            print(f"failed-login-watch: {len(alerts) - delivered} of "
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
        print(f"failed-login-watch: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
