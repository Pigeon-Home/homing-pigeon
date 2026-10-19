#!/usr/bin/env python3
"""Crash Watch: a Homing Pigeon user extension (example sense).

Watches one or more directories where crashed programs leave
their dumps -- the watch_dirs tunable -- and files what lands
there as sensor alerts for the Oracle. It is the sense a
fuzzing or test rig wants: a fuzzer's output folder, a test
fleet's core directory, any place a dump appearing means a
program died and somebody should know which one, and whether
it keeps dying.

Each alert names one of the signals declared in extension.json:

- crash_dumped   a crash file never seen before: a new path,
                 or the same path with a changed size or
                 mtime (a fresh dump overwrote the old one)
- crash_repeated the same binary crashed again within the
                 repeat_window_sec tunable (default one
                 hour); filed INSTEAD of crash_dumped, with
                 the count of that binary's crashes inside
                 the window in the detail

Which binary a dump belongs to is read off its filename: a
known dump suffix (.mdmp, .dmp, .core, .crash -- longest
first, so ".mdmp" is not half-stripped by the ".dmp" rule)
is stripped when present, and otherwise the binary is the
stem before the first "." in the name. So "notes.txt" belongs
to "notes", "app.mdmp" to "app", and "app.exe.dmp" to
"app.exe".

The machinery is deliberately boring, in the Lab Results
example's shape. read_live() is the only function that
touches the machine; it returns one readings dict, and
decide() -- readings plus manifest plus last pass's state,
out come alerts and the new state -- is pure, so the whole
decision surface is testable on a machine with no crashes at
all. Current time arrives as readings["now"], never from a
clock inside decide(). A pass scans at most
max_files_per_pass files; files beyond the cap are counted
in readings["truncated"], never silently dropped, and are
not marked seen -- they file on the next pass instead.

Run on the same machine as the runner, it delivers locally:
--local-dir <runner base dir> signs each payload with this
sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and signing
and delivery follow the standard senses flow.

--readings FILE reads a readings dict from a JSON file instead
of the directories: the way to try the sense (and test it)
against known dumps, on any box at all.
"""
import argparse
import json
import os
import sys
import time

# Known dump suffixes, longest first: ".mdmp" must be tried
# before ".dmp", or a minidump's name would lose only its
# last three letters and keep a stray ".m".
_DUMP_SUFFIXES = (".mdmp", ".dmp", ".core", ".crash")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _binary_for(name):
    """The binary a dump filename belongs to.

    A known dump suffix is stripped when present; otherwise
    the binary is the stem before the first "." -- see the
    module docstring for the full rule.
    """
    lower = name.lower()
    for suffix in _DUMP_SUFFIXES:
        if lower.endswith(suffix):
            stem = name[:-len(suffix)]
            return stem if stem else name
    if "." in name:
        stem = name.split(".", 1)[0]
        return stem if stem else name
    return name


def _tunables(manifest):
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    return tunables if isinstance(tunables, dict) else {}


def _watch_dirs(tunables):
    dirs = tunables.get("watch_dirs")
    if isinstance(dirs, str) and dirs:
        return [dirs]
    if isinstance(dirs, list):
        clean = [d for d in dirs if isinstance(d, str) and d]
        if clean:
            return clean
    return ["./crashes"]


def _max_files_per_pass(tunables):
    value = tunables.get("max_files_per_pass")
    return int(value) if _is_number(value) and value >= 1 else 1000


# --- the live reads: the only platform-touching code -----------------

def read_live(manifest):
    """One live snapshot of the watched directories.

    Returns {"now", "files", "truncated"}: every regular file
    in each watch dir (dotfiles and *.json state files are
    skipped), up to max_files_per_pass of them; the rest are
    counted in "truncated". Capability-based throughout: a
    watch dir that does not exist (or cannot be listed) simply
    contributes nothing, and this function never raises.
    """
    tunables = _tunables(manifest)
    cap = _max_files_per_pass(tunables)
    files = []
    truncated = 0
    for watch_dir in _watch_dirs(tunables):
        try:
            names = sorted(os.listdir(watch_dir))
        except OSError:
            continue  # no such directory yet; nothing to watch
        for name in names:
            if name.startswith("."):
                continue
            if name.lower().endswith(".json"):
                continue  # state files are not dumps
            path = os.path.join(watch_dir, name)
            try:
                if not os.path.isfile(path):
                    continue
                st = os.stat(path)
            except OSError:
                continue  # vanished mid-scan; next pass retries
            if len(files) >= cap:
                truncated += 1
                continue
            files.append({
                "name": name, "dir": watch_dir, "size": st.st_size,
                "mtime": st.st_mtime, "binary": _binary_for(name),
            })
    return {"now": time.time(), "files": files, "truncated": truncated}


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"seen": {}, "events": []}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    seen = state.get("seen")
    if not isinstance(seen, dict):
        seen = {}
    clean_seen = {}
    for path, mark in seen.items():
        if not isinstance(path, str):
            continue
        if isinstance(mark, (list, tuple)) and len(mark) == 2 \
                and _is_number(mark[0]) and _is_number(mark[1]):
            clean_seen[path] = [mark[0], mark[1]]
    events = state.get("events")
    if not isinstance(events, list):
        events = []
    clean_events = []
    for entry in events:
        if isinstance(entry, (list, tuple)) and len(entry) == 2 \
                and isinstance(entry[0], str) and entry[0] \
                and _is_number(entry[1]):
            clean_events.append([entry[0], entry[1]])
    return {"seen": clean_seen, "events": clean_events}


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time is
    readings["now"]. State is {"seen": {path: [size, mtime]},
    "events": [[binary, ts], ...]}; events are pruned to the
    trailing repeat_window_sec on every pass. A file whose
    path is new to "seen", or whose size/mtime moved, is a
    fresh dump and counts as a new crash event; when that
    binary already has a crash event inside the window the
    alert is crash_repeated instead of crash_dumped.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = _tunables(manifest)
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "crash_watch"
    window = tunables.get("repeat_window_sec")
    window = float(window) if _is_number(window) and window > 0 else 3600.0
    now = readings.get("now")
    now = float(now) if _is_number(now) else 0.0

    events = [[b, ts] for b, ts in state["events"]
              if ts >= now - window]
    seen = dict(state["seen"])
    alerts = []
    files = readings.get("files")
    if not isinstance(files, list):
        files = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        watch_dir = entry.get("dir")
        if not isinstance(watch_dir, str):
            watch_dir = ""
        size = entry.get("size")
        mtime = entry.get("mtime")
        if not _is_number(size) or not _is_number(mtime):
            continue
        binary = entry.get("binary")
        if not isinstance(binary, str) or not binary:
            binary = _binary_for(name)
        path = os.path.join(watch_dir, name) if watch_dir else name
        # Files beyond max_files_per_pass never appear in
        # readings["files"] at all, so they are not marked seen
        # here -- the next pass sees them as new and files them.
        if seen.get(path) == [size, mtime]:
            continue  # this exact dump was already filed
        prior = sum(1 for b, _ts in events if b == binary)
        detail = {"binary": binary, "file": name, "dir": watch_dir,
                  "size": size}
        if prior:
            count = prior + 1
            alerts.append({
                "sensor": sensor, "signal": "crash_repeated",
                "severity": "high",
                "title": f"{binary} crashed again: {count} crashes "
                         f"inside the repeat window ({name})",
                "detail": dict(detail, count=count),
            })
        else:
            alerts.append({
                "sensor": sensor, "signal": "crash_dumped",
                "severity": "medium",
                "title": f"new crash dump from {binary} ({name})",
                "detail": detail,
            })
        seen[path] = [size, mtime]
        events.append([binary, now])
    return alerts, {"seen": seen, "events": events}


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
        print(f"crash-watch: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"crash-watch: no signing secret in ${args.secret_env}; "
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
            print(f"crash-watch: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"crash-watch: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Crash Watch extension watcher: scan the crash "
                    "directories once and file sensor alert payloads "
                    "for dumps that landed since the last pass.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".crash-watch-state.json"),
                    help="state file (default: .crash-watch-state.json "
                         "next to this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the watched directories (trying "
                         "the sense against known readings, on any box)")
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
        print(f"crash-watch: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"crash-watch: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    else:
        readings = read_live(manifest)
    if isinstance(readings, dict) and readings.get("truncated"):
        print(f"crash-watch: {readings['truncated']} file(s) beyond "
              f"max_files_per_pass were not scanned this pass; they "
              f"are not marked seen and will file next pass",
              file=sys.stderr)
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
            # next pass reports these dumps again.
            print(f"crash-watch: {len(alerts) - delivered} of "
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
        print(f"crash-watch: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
