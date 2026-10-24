#!/usr/bin/env python3
"""Release Drop: a Homing Pigeon user extension (example sense).

Watches a drop folder -- the watch_dir tunable -- where
release artifacts land, and files every arrival as a sensor
alert for the Oracle, attested with the artifact's SHA-384
digest (the project's digest). It is the sense release duty
wants: when a build, a signed package, or a hotfix drops, the
Oracle learns not just that something arrived, but exactly
which bytes arrived -- and if a name that already dropped
shows up again carrying different bytes, that is the loud
signal, because a release artifact that changes under its
own name is either a re-spin nobody announced or a problem.

Each alert names one of the signals declared in extension.json:

- artifact_arrived  a name never seen before; the detail
                    carries the name, the size, and the full
                    hex SHA-384 of the artifact
- artifact_changed  a known name reappeared with a DIFFERENT
                    SHA-384; the detail carries the old and
                    new digests side by side

Files are hashed with SHA-384, streamed in chunks so a large
artifact never sits whole in memory. A file larger than the
max_hash_mb tunable (default 512 MB) is SKIPPED entirely for
the pass: it is counted in readings["skipped_oversize"],
named on stderr by main(), and is never watched -- it files
nothing and enters no state -- until it fits under the cap
or the cap rises. An artifact's arrival is only ever attested
by a digest this sense actually computed.

The machinery is deliberately boring, in the Lab Results
example's shape. read_live() is the only function that
touches the machine; it returns one readings dict, and
decide() -- readings plus manifest plus last pass's state,
out come alerts and the new state -- is pure, so the whole
decision surface is testable with fixture readings alone.
Current time arrives as readings["now"], never from a clock
inside decide(). A name that vanishes from the drop is
dropped from the state silently: no signal is declared for
departures, so none is filed.

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
of the folder: the way to try the sense (and test its
decisions) against known artifacts, on any box at all. The
hashing path itself is exercised live, through --watch-dir.
"""
import argparse
import hashlib
import json
import os
import sys
import time

# Hashing streams in chunks of this size: an artifact is
# attested without ever sitting whole in memory.
_HASH_CHUNK = 256 * 1024


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


def _watch_dir(tunables):
    watch_dir = tunables.get("watch_dir")
    return watch_dir if isinstance(watch_dir, str) and watch_dir else "./drop"


def _max_hash_bytes(tunables):
    mb = tunables.get("max_hash_mb")
    if _is_number(mb) and mb > 0:
        return int(mb * 1024 * 1024)
    return 512 * 1024 * 1024


def _sha384_file(path):
    """The full hex SHA-384 of a file, streamed in chunks."""
    digest = hashlib.sha384()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


# --- the live reads: the only platform-touching code -----------------

def read_live(manifest):
    """One live snapshot of the drop folder, as a readings dict.

    Returns {"now", "files", "skipped_oversize"}: every regular
    file in watch_dir (dotfiles skipped) with its size and the
    SHA-384 this sense computed for it. A file larger than
    max_hash_mb is skipped entirely and counted in
    "skipped_oversize" -- never hashed, never watched, until
    it fits or the cap rises. Capability-based throughout: a
    watch dir that does not exist contributes nothing, a file
    that vanishes mid-pass is passed over, and this function
    never raises.
    """
    tunables = _tunables(manifest)
    watch_dir = _watch_dir(tunables)
    cap = _max_hash_bytes(tunables)
    files = []
    skipped_oversize = 0
    try:
        names = sorted(os.listdir(watch_dir))
    except OSError:
        names = []  # no drop folder yet; nothing has landed
    for name in names:
        if name.startswith("."):
            continue
        path = os.path.join(watch_dir, name)
        try:
            if not os.path.isfile(path):
                continue
            st = os.stat(path)
        except OSError:
            continue  # vanished mid-scan; next pass retries
        if st.st_size > cap:
            skipped_oversize += 1
            continue
        try:
            sha384 = _sha384_file(path)
        except OSError:
            continue  # unreadable or vanished; next pass retries
        files.append({"name": name, "size": st.st_size,
                      "sha384": sha384})
    return {"now": time.time(), "files": files,
            "skipped_oversize": skipped_oversize}


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"seen": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    seen = state.get("seen")
    if not isinstance(seen, dict):
        seen = {}
    clean = {}
    for name, entry in seen.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        sha384 = entry.get("sha384")
        if not isinstance(sha384, str) or not sha384:
            continue
        size = entry.get("size")
        clean[name] = {"sha384": sha384,
                       "size": size if _is_number(size) else 0}
    return {"seen": clean}


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time is
    readings["now"]. State is {"seen": {name: {"sha384",
    "size"}}}. A name the state has never held files
    artifact_arrived; a known name whose digest moved files
    artifact_changed; a name absent from this pass's readings
    is dropped from the new state silently -- no signal is
    declared for departures, so none is filed.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "release_drop"
    working = {name: dict(entry)
               for name, entry in state["seen"].items()}
    present = set()
    alerts = []
    files = readings.get("files")
    if not isinstance(files, list):
        files = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        sha384 = entry.get("sha384")
        size = entry.get("size")
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(sha384, str) or not sha384:
            continue
        if not _is_number(size):
            continue
        present.add(name)
        # Detection is against `working`, which starts as a copy
        # of the old state and is updated as the pass goes: a
        # first sighting compares against the digest the state
        # already held, and a name listed twice in one readings
        # dict compares its second digest against the one just
        # recorded.
        known = working.get(name)
        if known is None:
            alerts.append({
                "sensor": sensor, "signal": "artifact_arrived",
                "severity": "info",
                "title": f"release artifact arrived: {name}",
                "detail": {"name": name, "size": size,
                           "sha384": sha384},
            })
        elif known["sha384"] != sha384:
            alerts.append({
                "sensor": sensor, "signal": "artifact_changed",
                "severity": "high",
                "title": f"release artifact changed under its "
                         f"name: {name}",
                "detail": {"name": name, "old_sha384": known["sha384"],
                           "new_sha384": sha384, "size": size},
            })
        working[name] = {"sha384": sha384, "size": size}
    new_seen = {name: working[name] for name in working
                if name in present}
    return alerts, {"seen": new_seen}


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
        print(f"release-drop: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"release-drop: no signing secret in ${args.secret_env}; "
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
            print(f"release-drop: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"release-drop: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Release Drop extension watcher: hash the drop "
                    "folder once and file sensor alert payloads for "
                    "artifacts that landed since the last pass.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--watch-dir", default=None,
                    help="drop folder (default: the manifest's "
                         "watch_dir tunable, else ./drop)")
    ap.add_argument("--state", default=os.path.join(
                        here, ".release-drop-state.json"),
                    help="state file (default: .release-drop-state.json "
                         "next to this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the drop folder (trying the "
                         "sense's decisions against known readings, "
                         "on any box)")
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
        print(f"release-drop: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.watch_dir and isinstance(manifest, dict):
        # The override steers read_live only: a copy of the
        # manifest carries it, the file on disk is untouched.
        manifest = dict(manifest)
        tunables = _tunables(manifest)
        manifest["tunables"] = dict(tunables, watch_dir=args.watch_dir)
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"release-drop: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    else:
        readings = read_live(manifest)
    if isinstance(readings, dict) and readings.get("skipped_oversize"):
        tunables = _tunables(manifest)
        mb = tunables.get("max_hash_mb")
        cap = f"{mb} MB" if _is_number(mb) else "the max_hash_mb cap"
        print(f"release-drop: {readings['skipped_oversize']} file(s) "
              f"over {cap} skipped this pass; they are not watched "
              f"until they fit or the cap rises", file=sys.stderr)
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
            # next pass reports these artifacts again.
            print(f"release-drop: {len(alerts) - delivered} of "
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
        print(f"release-drop: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
