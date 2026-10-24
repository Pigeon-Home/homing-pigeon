#!/usr/bin/env python3
"""Log Sentinel: a Homing Pigeon user extension (example sense).

Tails kernel and system logs for the lines that mean the
machine is hurting -- an OOM kill, a panic, a BUG, a segfault,
a filesystem error -- and files them as sensor alerts for the
Oracle. It is the sense shape of years spent reading a sick
machine's own account of itself: the kernel usually says what
is wrong, in the log, before anything else notices. Each
alert names one of the signals declared in extension.json:

- kernel_distress  a built-in distress group matched a log
                   line; all built-ins are high severity
- log_pattern_hit  a pattern configured in the patterns
                   tunable matched a log line; the severity
                   comes from the pattern entry (medium unless
                   it declares high)

The machinery is deliberately boring, in the Lab Results and
Pi Health examples' shape. Classification is pure:
classify() turns lines into events, and decide() -- readings
plus manifest plus last pass's state, out come alerts and the
new state -- applies a per-subject cooldown and the per-pass
cap, so the whole decision surface is testable against fixture
lines on any box. The subject a cooldown keys on is deliberately
coarse -- the group name for built-ins, the pattern name for
configured patterns -- so one distress call per group (or
pattern) per cooldown is all a flooded log can file: the first
line of an OOM storm is the news, the next thousand are not.

The reader plumbing is main()'s: it owns incremental offsets
the way tail -f does, in a "_reader" sub-dict of the state
({path: {"inode", "offset"}}) which _clean_state preserves
opaquely and decide() ignores. read_new_lines() does one
incremental read: a file at first sight starts at the end
minus tail_bytes, so a huge log's ancient history never floods
the first pass; afterwards it reads from the recorded offset,
never more than tail_bytes per pass per file, advancing only
past what was read. An inode change or a shrink restarts a
file from the beginning.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extend/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and signing
and delivery follow the standard senses flow.

--readings FILE reads a readings dict ({"now", "lines"}) from
a JSON file, and --log-file FILE reads a whole fixture log as
the lines; neither touches the _reader offsets.
"""
import argparse
import json
import os
import re
import sys
import time

# The built-in distress groups: case-insensitive regexes over
# one log line, all high severity, all filing kernel_distress.
BUILTIN_GROUPS = {
    "oom": r"out of memory|oom-kill|killed process",
    "panic": r"kernel panic|panic - not syncing",
    "bug": r"BUG:|kernel BUG at",
    "segfault": r"segfault at|segfault error",
    "fs": r"ext4-fs error|xfs.*corrupt|buffer i/o error|"
          r"blk_update_request.*error",
}

_DEFAULT_GROUPS = ["oom", "panic", "fs", "segfault", "bug"]
_DEFAULT_LOG_PATHS = ["/var/log/kern.log", "/var/log/syslog"]


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


def _tunables(manifest):
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    return tunables if isinstance(tunables, dict) else {}


def _sensor(manifest):
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    return sensor if isinstance(sensor, str) and sensor else "log_sentinel"


def _int_tunable(tunables, key, default, minimum=0):
    value = tunables.get(key)
    if _is_number(value) and value >= minimum:
        return int(value)
    return default


# --- the reader: incremental, offset-owning, total ------------

def read_new_lines(paths, reader_state, tail_bytes):
    """Read what is new in each of `paths`, tail -f style.

    Returns (lines, new_reader_state). Pure-ish: it reads files
    but holds no state of its own -- the caller (main) owns the
    reader_state dict it hands back next pass. A missing or
    unreadable file yields no lines and never raises. See the
    module docstring for the offset rules.
    """
    if not _is_number(tail_bytes) or tail_bytes <= 0:
        tail_bytes = 65536
    tail_bytes = int(tail_bytes)
    if not isinstance(reader_state, dict):
        reader_state = {}
    lines = []
    new_state = {}
    if not isinstance(paths, list):
        paths = []
    for path in paths:
        if not isinstance(path, str) or not path:
            continue
        prev = reader_state.get(path)
        if not isinstance(prev, dict):
            prev = None
        try:
            info = os.stat(path)
        except OSError:
            # Missing for now: keep any recorded offset, so a
            # file that comes back is not re-read from scratch.
            if prev is not None:
                new_state[path] = dict(prev)
            continue
        inode, size = int(info.st_ino), int(info.st_size)
        offset = prev.get("offset") if prev else None
        if prev is None or not _is_number(offset):
            start = max(0, size - tail_bytes)
        elif int(prev.get("inode") or -1) != inode or size < offset:
            start = 0  # rotated (new inode) or truncated: restart
        else:
            start = int(offset)
        end = min(size, start + tail_bytes)
        entry = {"inode": inode, "offset": start}
        if end > start:
            try:
                with open(path, "rb") as fh:
                    fh.seek(start)
                    raw = fh.read(end - start)
            except OSError:
                if prev is not None:
                    new_state[path] = dict(prev)
                continue
            lines.extend(raw.decode("utf-8", errors="replace")
                         .splitlines())
            entry["offset"] = start + len(raw)
        else:
            entry["offset"] = end
        new_state[path] = entry
    return lines, new_state


def read_live(manifest, reader_state=None):
    """One live snapshot of the configured logs, as a readings dict.

    The new reader state rides along under "_reader" (internal
    plumbing, not a reading): main() lifts it out before decide()
    and stores it in the state file. Capability-based and
    total: a machine with neither log yields empty lines, never
    an exception.
    """
    tunables = _tunables(manifest)
    paths = tunables.get("log_paths")
    if not isinstance(paths, list) or not paths:
        paths = list(_DEFAULT_LOG_PATHS)
    tail_bytes = _int_tunable(tunables, "tail_bytes", 65536, minimum=1)
    lines, new_reader = read_new_lines(paths, reader_state, tail_bytes)
    return {"now": time.time(), "lines": lines, "_reader": new_reader}


# --- classification and the decision (pure) --------------------

def _compiled_groups(tunables):
    enabled = tunables.get("groups")
    if not isinstance(enabled, list):
        enabled = list(_DEFAULT_GROUPS)
    groups = []
    for name in enabled:
        pattern = BUILTIN_GROUPS.get(name) if isinstance(name, str) \
            else None
        if pattern is None:
            continue
        try:
            groups.append((name, re.compile(pattern, re.IGNORECASE)))
        except re.error:
            continue
    return groups


def _compiled_patterns(tunables):
    raw = tunables.get("patterns")
    if not isinstance(raw, list):
        return []
    patterns = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        regex = entry.get("regex")
        if not isinstance(name, str) or not name \
                or not isinstance(regex, str) or not regex:
            continue
        try:
            compiled = re.compile(regex, re.IGNORECASE)
        except re.error:
            continue  # a bad configured pattern never breaks a pass
        severity = "high" if entry.get("severity") == "high" \
            else "medium"
        patterns.append((name, compiled, severity))
    return patterns


def classify(lines, manifest):
    """Classify log lines into events. Pure: no I/O, no clock.

    Each event is {"line", "group", "severity", "subject"} for a
    built-in match (subject is the group name) or {"line",
    "pattern", "severity", "subject"} for a configured pattern
    (subject is the pattern name). A line yields at most one
    built-in event -- the first enabled group it matches --
    plus one event per configured pattern it matches.
    """
    tunables = _tunables(manifest)
    groups = _compiled_groups(tunables)
    patterns = _compiled_patterns(tunables)
    events = []
    if not isinstance(lines, list):
        return events
    for line in lines:
        if not isinstance(line, str):
            continue
        for name, compiled in groups:
            if compiled.search(line):
                events.append({"line": line, "group": name,
                               "severity": "high", "subject": name})
                break
        for name, compiled, severity in patterns:
            if compiled.search(line):
                events.append({"line": line, "pattern": name,
                               "severity": severity, "subject": name})
    return events


def _fresh_state():
    return {"last_fired": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    last_fired = state.get("last_fired")
    if not isinstance(last_fired, dict):
        last_fired = {}
    clean = {"last_fired": {k: float(v) for k, v in last_fired.items()
                            if isinstance(k, str) and _is_number(v)}}
    reader = state.get("_reader")
    if isinstance(reader, dict):
        # Preserved opaquely: main()'s plumbing, decide() ignores it.
        clean["_reader"] = dict(reader)
    return clean


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"]. Identical (signal, subject) hits are
    deduped within the pass; a hit inside its cooldown is
    suppressed and does NOT refresh the timestamp; at most
    max_alerts_per_pass alerts are filed, and hits past the
    cap are dropped without being marked fired, so they can
    file on a later pass.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = _tunables(manifest)
    sensor = _sensor(manifest)
    now = readings.get("now")
    now = float(now) if _is_number(now) else 0.0
    cooldown = _int_tunable(tunables, "cooldown_sec", 3600, minimum=0)
    max_alerts = _int_tunable(tunables, "max_alerts_per_pass", 10,
                               minimum=0)
    events = classify(readings.get("lines"), manifest)
    last_fired = dict(state["last_fired"])
    alerts = []
    seen = set()
    for event in events:
        if "group" in event:
            signal = "kernel_distress"
            label = event["group"]
        else:
            signal = "log_pattern_hit"
            label = event["pattern"]
        key = f"{signal}:{event['subject']}"
        if key in seen:
            continue
        seen.add(key)
        fired_at = last_fired.get(key)
        if fired_at is not None and now - fired_at < cooldown:
            continue  # suppressed; the timestamp is not refreshed
        if len(alerts) >= max_alerts:
            continue  # dropped, and deliberately not marked fired
        line = event["line"]
        trimmed = line.strip()[:120]
        if signal == "kernel_distress":
            detail = {"group": label, "line": line}
            title = f"kernel distress ({label}): {trimmed}"
        else:
            detail = {"pattern": label, "line": line}
            title = f"log pattern {label}: {trimmed}"
        alerts.append({"sensor": sensor, "signal": signal,
                       "severity": event["severity"],
                       "title": title, "detail": detail})
        last_fired[key] = now
    new_state = {"last_fired": last_fired}
    if "_reader" in state:
        new_state["_reader"] = state["_reader"]
    return alerts, new_state


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
        print(f"log-sentinel: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"log-sentinel: no signing secret in "
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
            print(f"log-sentinel: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"log-sentinel: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Log Sentinel extension watcher: read what is "
                    "new in the configured logs once and file sensor "
                    "alert payloads for the distress lines.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".log-sentinel-state.json"),
                    help="state file (default: "
                         ".log-sentinel-state.json next to this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the logs (trying the sense "
                         "against known lines, on any box)")
    ap.add_argument("--log-file", default=None,
                    help="read this whole file as the pass's log "
                         "lines (a fixture log; no _reader offsets "
                         "are touched)")
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
        print(f"log-sentinel: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
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
            print(f"log-sentinel: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
        if not isinstance(readings, dict):
            print(f"log-sentinel: readings {args.readings} is not a "
                  f"JSON object", file=sys.stderr)
            return 2
    elif args.log_file:
        try:
            with open(args.log_file, encoding="utf-8") as fh:
                fixture_lines = fh.read().splitlines()
        except (OSError, UnicodeDecodeError, ValueError) as e:
            print(f"log-sentinel: cannot read log file "
                  f"{args.log_file}: {e}", file=sys.stderr)
            return 2
        readings = {"now": time.time(), "lines": fixture_lines}
    else:
        reader_state = state.get("_reader") if isinstance(state, dict) \
            else None
        readings = read_live(manifest, reader_state)
        new_reader = readings.pop("_reader", None)
    alerts, state = decide(readings, manifest, state)
    if new_reader is not None:
        state["_reader"] = new_reader
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten (the
            # _reader offsets included), so the next pass
            # reports these lines again.
            print(f"log-sentinel: {len(alerts) - delivered} of "
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
        print(f"log-sentinel: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
