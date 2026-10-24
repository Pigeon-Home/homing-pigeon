#!/usr/bin/env python3
"""Backup Freshness: a Homing Pigeon user extension (example sense).

Watches a backup directory -- is the newest backup still
fresh, and did a new one land? -- and turns what it finds
into sensor alerts for the Oracle. Backups fail quietly more
often than loudly: the job stops running, the disk fills, the
cron entry rots, and nothing complains until the day the
backup is needed. This sense is the complaint. Each alert
names one of the signals declared in extension.json:

- backup_arrived   a newer backup artifact landed (info)
- backup_stale     the newest backup is older than the
                   stale_after_sec tunable (medium)
- backup_critical  the newest backup is older than twice
                   that tunable (high)

The machinery is deliberately boring, in the Lab Results
example's shape. read_live() is the only function that
touches the filesystem; it returns one readings dict, and
decide() -- readings plus manifest plus last pass's state,
out come alerts and the new state -- is pure, so the whole
decision surface is testable on any box. Current time
arrives as readings["now"] (epoch seconds); decide() never
reads a clock itself.

The age clock is honest about an empty directory. While a
newest artifact exists, its age is now minus its mtime. If
the directory goes empty after backups were seen, the clock
keeps running on the last backup ever seen -- an emptied
directory does not reset the sense to "fine". If no backup
has ever been seen at all, the sense stays quiet: that
nothing has ever been backed up is a configuration fact,
not this sense's alert.

Staleness is tiered, and each tier files once. Crossing
stale_after_sec from the ok tier files backup_stale;
crossing twice that files backup_critical. A jump straight
from ok past the critical line files backup_critical only --
the stronger statement wins, not stale-then-critical in the
same pass. A fresh arrival resets the tier to ok and files
backup_arrived; a just-landed artifact has age near zero,
so the arrival pass does not also re-evaluate staleness.

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload with
this sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extensions.md, "Local delivery").

--readings FILE reads a readings dict from a JSON file instead
of the directory: the way to try the sense (and test it)
against known readings, on any box at all.
"""
import argparse
import fnmatch
import json
import os
import sys
import time


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


# --- the live reads: the only platform-touching code -----------------

def read_live(manifest):
    """One live snapshot of the backup directory, as a readings dict.

    Returns {"now": epoch float, "newest": {"name", "mtime",
    "size"} or None}. The directory named by the watch_dir
    tunable is listed for regular files matching the glob
    tunable; the newest by mtime wins. A missing directory --
    or one with no matching file -- yields newest None: no
    data, never an error.
    """
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    watch_dir = tunables.get("watch_dir")
    if not isinstance(watch_dir, str) or not watch_dir:
        watch_dir = "./backups"
    pattern = tunables.get("glob")
    if not isinstance(pattern, str) or not pattern:
        pattern = "*"
    newest = None
    try:
        names = os.listdir(watch_dir)
    except OSError:
        return {"now": time.time(), "newest": None}
    for name in names:
        if not fnmatch.fnmatch(name, pattern):
            continue
        path = os.path.join(watch_dir, name)
        try:
            if not os.path.isfile(path):
                continue
            st = os.stat(path)
        except OSError:
            continue
        candidate = {"name": name, "mtime": float(st.st_mtime),
                     "size": int(st.st_size)}
        if newest is None or candidate["mtime"] > newest["mtime"]:
            newest = candidate
    return {"now": time.time(), "newest": newest}


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"last_seen_name": None, "last_seen_mtime": None,
            "tier": "ok"}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    name = state.get("last_seen_name")
    if not isinstance(name, str):
        name = None
    mtime = state.get("last_seen_mtime")
    mtime = float(mtime) if _is_number(mtime) else None
    tier = state.get("tier")
    if tier not in ("ok", "stale", "critical"):
        tier = "ok"
    return {"last_seen_name": name, "last_seen_mtime": mtime,
            "tier": tier}


def _clean_newest(raw):
    if not isinstance(raw, dict):
        return None
    name = raw.get("name")
    mtime = raw.get("mtime")
    if not isinstance(name, str) or not name or not _is_number(mtime):
        return None
    out = {"name": name, "mtime": float(mtime)}
    size = raw.get("size")
    if _is_number(size):
        out["size"] = size
    return out


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time is readings["now"].
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "backup_freshness"
    now = readings.get("now")
    now = float(now) if _is_number(now) else 0.0
    stale_after = tunables.get("stale_after_sec")
    stale_after = float(stale_after) if _is_number(stale_after) \
        and stale_after > 0 else 90000.0
    newest = _clean_newest(readings.get("newest"))

    alerts = []

    # Arrival: a strictly newer artifact, or the first one ever.
    arrived = False
    if newest is not None:
        if state["last_seen_mtime"] is None \
                or newest["mtime"] > state["last_seen_mtime"]:
            arrived = True
    if arrived:
        detail = {"name": newest["name"], "mtime": newest["mtime"]}
        if "size" in newest:
            detail["size"] = newest["size"]
        alerts.append({
            "sensor": sensor, "signal": "backup_arrived",
            "severity": "info",
            "title": f"new backup {newest['name']} landed",
            "detail": detail,
        })
        state["last_seen_name"] = newest["name"]
        state["last_seen_mtime"] = newest["mtime"]
        state["tier"] = "ok"
        # A just-landed artifact has age ~0; skip staleness
        # re-evaluation on the arrival pass.
        return alerts, state

    # Age basis: the newest artifact when one exists, else the
    # last backup ever seen (the directory went empty -- the
    # clock keeps running on it).
    if newest is not None:
        age_basis_mtime = newest["mtime"]
        age_name = newest["name"]
    elif state["last_seen_mtime"] is not None:
        age_basis_mtime = state["last_seen_mtime"]
        age_name = state["last_seen_name"]
    else:
        # Nothing has ever been backed up: a configuration
        # fact, not this sense's alert.
        return alerts, state
    age = now - age_basis_mtime
    if age < 0:
        age = 0.0
    detail = {"age_sec": age, "threshold_sec": stale_after,
              "last_seen_name": age_name}
    if age > 2 * stale_after and state["tier"] != "critical":
        # The stronger statement wins: a jump straight from ok
        # files critical only, not stale-then-critical.
        alerts.append({
            "sensor": sensor, "signal": "backup_critical",
            "severity": "high",
            "title": f"newest backup is {int(age)}s old "
                     f"(critical at {int(2 * stale_after)}s)",
            "detail": dict(detail),
        })
        state["tier"] = "critical"
    elif age > stale_after and state["tier"] == "ok":
        alerts.append({
            "sensor": sensor, "signal": "backup_stale",
            "severity": "medium",
            "title": f"newest backup is {int(age)}s old "
                     f"(stale after {int(stale_after)}s)",
            "detail": dict(detail),
        })
        state["tier"] = "stale"
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
        print(f"backup-freshness: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"backup-freshness: no signing secret in ${args.secret_env}; "
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
            print(f"backup-freshness: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"backup-freshness: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Backup Freshness extension watcher: check the "
                    "newest backup in the watched directory and file "
                    "sensor alert payloads for arrivals and staleness.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".backup-freshness-state.json"),
                    help="state file (default: .backup-freshness-state.json "
                         "next to this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the directory (trying the sense "
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
        print(f"backup-freshness: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"backup-freshness: cannot read readings "
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
            # next pass reports this condition again.
            print(f"backup-freshness: {len(alerts) - delivered} of "
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
        print(f"backup-freshness: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
