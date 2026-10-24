#!/usr/bin/env python3
"""Tripwire: a Homing Pigeon user extension (example sense).

Hashes a watched tree with SHA-384 -- the project's digest --
and diffs it against the recorded baseline, turning file
integrity into sensor alerts for the Oracle. It is the sense
shape of a black-box tester's oldest habit: know exactly what
was there, and notice the moment it is not that any more.
Each alert names one of the signals declared in extension.json:

- file_appeared  a file is present that the baseline never saw
- file_vanished  a baseline file is no longer present
- file_changed   a file's digest differs from the baseline (a
                 file over the max_file_mb cap carries no
                 digest, so it compares by size only)

The machinery is deliberately boring, in the Lab Results and
Pi Health examples' shape. read_live() is the only function
that touches the tree; it returns one readings dict, and
decide() -- readings plus manifest plus last pass's state,
out come alerts and the new state -- is pure, so the whole
decision surface is testable against fixture readings on any
box. The first pass learns: with learn_first_pass set (the
default), it absorbs the tree as the baseline and files
nothing, because a tripwire that alarms on its own install
teaches its operator to ignore it. After that a pass files
each difference once; the new baseline is always absorbed in
full, even for differences past the max_alerts_per_pass cap.

A file over max_file_mb is recorded as
{"sha384": null, "size": n, "oversize": true}: its bytes are
never read, and decide() compares such entries by size only.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extend/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and signing
and delivery follow the standard senses flow.

--readings FILE reads a readings dict from a JSON file instead
of the tree: the way to try the sense (and test it) against
known readings, on any box at all.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import stat
import sys
import time

_CHUNK = 65536

_DEFAULT_EXCLUDES = ["*.pyc", "__pycache__", ".git",
                     ".tripwire-state.json"]


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
    return sensor if isinstance(sensor, str) and sensor else "tripwire"


def _int_tunable(tunables, key, default, minimum=0):
    value = tunables.get(key)
    if _is_number(value) and value >= minimum:
        return int(value)
    return default


# --- the live read: the only platform-touching code ------------------

def _excluded(relpath, excludes):
    parts = relpath.replace(os.sep, "/").split("/")
    for pattern in excludes:
        if not isinstance(pattern, str) or not pattern:
            continue
        if fnmatch.fnmatch(relpath, pattern):
            return True
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def _hash_file(path):
    digest = hashlib.sha384()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_live(manifest):
    """One live snapshot of the watched tree, as a readings dict.

    Capability-based and total: a missing root, an unreadable
    file, or a file that vanishes mid-pass yields empty or
    partial data, never an exception. Files are walked in
    sorted order for determinism; only regular files count.
    At most max_files files are recorded -- readings then
    carries "truncated", the count of files skipped past the
    cap. Unrecorded files are not in the readings, so they are
    not in the state decide() absorbs either, and they diff
    again on the next pass.
    """
    tunables = _tunables(manifest)
    root = tunables.get("root")
    if not isinstance(root, str) or not root:
        root = "."
    excludes = tunables.get("excludes")
    if not isinstance(excludes, list):
        excludes = list(_DEFAULT_EXCLUDES)
    max_files = _int_tunable(tunables, "max_files", 10000, minimum=0)
    max_file_mb = tunables.get("max_file_mb")
    max_bytes = float(max_file_mb) * 1024 * 1024 \
        if _is_number(max_file_mb) and max_file_mb >= 0 \
        else 64 * 1024 * 1024
    readings = {"now": time.time(), "files": {}, "truncated": 0}
    try:
        if not os.path.isdir(root):
            return readings
    except OSError:
        return readings
    files = readings["files"]
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        # Prune excluded directories in place (never descended).
        dirnames[:] = [
            d for d in dirnames
            if not _excluded(os.path.relpath(
                os.path.join(dirpath, d), root), excludes)]
        for fname in sorted(filenames):
            path = os.path.join(dirpath, fname)
            relpath = os.path.relpath(path, root).replace(os.sep, "/")
            if _excluded(relpath, excludes):
                continue
            try:
                info = os.lstat(path)
            except OSError:
                continue  # vanished mid-pass; next pass sees it
            if not stat.S_ISREG(info.st_mode):
                continue
            if len(files) >= max_files:
                # Past the cap: counted, not recorded (see the
                # docstring -- it diffs again next pass).
                readings["truncated"] += 1
                continue
            size = int(info.st_size)
            if size > max_bytes:
                files[relpath] = {"sha384": None, "size": size,
                                  "oversize": True}
                continue
            try:
                hexdigest = _hash_file(path)
            except OSError:
                continue  # unreadable; never an error, never a file
            files[relpath] = {"sha384": hexdigest, "size": size}
    return readings


# --- the decision: readings in, signals out (pure) -------------------

def _clean_files(raw):
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for path, entry in raw.items():
        if not isinstance(path, str) or not isinstance(entry, dict):
            continue
        sha = entry.get("sha384")
        if sha is not None and not isinstance(sha, str):
            continue
        size = entry.get("size")
        if not _is_number(size) or size < 0:
            continue
        cleaned = {"sha384": sha, "size": int(size)}
        if entry.get("oversize"):
            cleaned["oversize"] = True
        clean[path] = cleaned
    return clean


def _fresh_state():
    return {"learned": False, "files": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    return {"learned": bool(state.get("learned")),
            "files": _clean_files(state.get("files"))}


def _is_oversize(entry):
    return bool(entry.get("oversize")) or entry.get("sha384") is None


def _changed(old, new):
    if _is_oversize(old) or _is_oversize(new):
        return old.get("size") != new.get("size")
    return old.get("sha384") != new.get("sha384")


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time, when a caller
    wants it, arrives as readings["now"]. Paths are processed
    in sorted order. At most max_alerts_per_pass alerts are
    filed, but the full new baseline is ALWAYS absorbed:
    differences past the cap are recorded, not re-filed.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = _tunables(manifest)
    sensor = _sensor(manifest)
    learn = tunables.get("learn_first_pass")
    learn = learn if isinstance(learn, bool) else True
    max_alerts = _int_tunable(tunables, "max_alerts_per_pass", 100,
                              minimum=0)
    current = _clean_files(readings.get("files"))
    new_state = {"learned": True, "files": current}
    if not state["learned"] and learn:
        return [], new_state
    previous = state["files"]
    alerts = []
    for path in sorted(set(previous) | set(current)):
        if len(alerts) >= max_alerts:
            break  # state above already absorbed the rest
        if path not in previous:
            entry = current[path]
            alerts.append({
                "sensor": sensor, "signal": "file_appeared",
                "severity": "medium",
                "title": f"file appeared: {path}",
                "detail": {"path": path, "size": entry["size"]},
            })
        elif path not in current:
            alerts.append({
                "sensor": sensor, "signal": "file_vanished",
                "severity": "medium",
                "title": f"file vanished: {path}",
                "detail": {"path": path},
            })
        elif _changed(previous[path], current[path]):
            old, new = previous[path], current[path]
            alerts.append({
                "sensor": sensor, "signal": "file_changed",
                "severity": "high",
                "title": f"file changed: {path}",
                "detail": {"path": path,
                           "old_sha384": old.get("sha384"),
                           "new_sha384": new.get("sha384"),
                           "size": new["size"]},
            })
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
        print(f"tripwire: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"tripwire: no signing secret in ${args.secret_env}; "
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
            print(f"tripwire: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"tripwire: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Tripwire extension watcher: hash the watched "
                    "tree once and file sensor alert payloads for "
                    "what differs from the baseline.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".tripwire-state.json"),
                    help="state file (default: .tripwire-state.json "
                         "next to this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the tree (trying the sense "
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
        print(f"tripwire: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"tripwire: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
        if not isinstance(readings, dict):
            print(f"tripwire: readings {args.readings} is not a "
                  f"JSON object", file=sys.stderr)
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
            # next pass reports these differences again.
            print(f"tripwire: {len(alerts) - delivered} of "
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
        print(f"tripwire: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
