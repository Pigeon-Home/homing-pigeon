#!/usr/bin/env python3
"""AIDE Feed: a Homing Pigeon user extension (example sense).

Feeds AIDE check reports to the Oracle. AIDE (Advanced
Intrusion Detection Environment) compares the filesystem
against a recorded database -- hashes, permissions, the
attribute set its config names -- and writes a plain-text
report saying what was added, what was removed, and what
changed since the database was built. This sense reads the
report the owner's schedule produced and files, per new
report:

- aide_changed  entries listed under "Changed entries:"
- aide_removed  entries listed under "Removed entries:"
- aide_added    entries listed under "Added entries:"

One alert per class per new report, never one per file:
the detail carries the count, the first 20 paths, and the
report fingerprint. A report with zero differences files
nothing.

AIDE is batch, and the plumbing says so. There is no
daemon and nothing to tail: the producer polls the report
paths (the report_paths tunable, by default
/var/log/aide/aide.log, where the owner's cron or timer
leaves the latest check). read_report_file() answers the
report text only when a report is NEW -- when the file's
(inode, size, mtime) fingerprint differs from the one the
reader state carries -- and (None, state) otherwise.
parse_report() turns one report's text into
{"added": [...], "removed": [...], "changed": [...],
"differences": bool}, from the "Added entries:" /
"Removed entries:" / "Changed entries:" sections. Entry
lines are an attribute mask and a path, "f...: /path";
the prefix letter is f (file), d (directory), or l
(link), and the mask itself may contain spaces.

decide() is the pure shape the other examples use:
readings plus manifest plus last pass's state, out come
alerts and the new state. The state carries the last
report fingerprint it filed for, so the same report handed
to decide() twice files once -- the reader fingerprint is
the first gate, this is the second. With no new report the
readings carry nothing and decide() files nothing.
Current time arrives as readings["now"]; decide() never
reads a clock. The reader state rides in the state dict
under "_reader", preserved opaquely by decide() and owned
by main().

Two fixture modes feed decide() without a live AIDE:
--readings FILE reads a readings dict ({"now", "report",
"fingerprint"}) from JSON, and --report-file FILE parses a
whole fixture report, ignoring the reader state. The
report fixture under fixtures/ is a trimmed copy of a real
captured AIDE check (see fixtures/README.md).

Run on the same machine as the runner, it can also deliver
locally: --local-dir <runner base dir> signs each payload
with this sense's key (read from the environment variable
named by --secret-env) and drops it into the runner's local
inbox, or pushes it to the runner's loopback listener when
--local-port is given. Without --local-dir it prints one
alert payload per line, and signing and delivery follow
the standard senses flow.
"""
import argparse
import json
import os
import re
import sys
import time

_ENTRY_RE = re.compile(r"^([fdl])[^:]*:\s+(/\S.*)$")
_SECTIONS = {"Added entries:": "added",
             "Removed entries:": "removed",
             "Changed entries:": "changed"}
_SECTION_ENDS = ("Detailed information", "The attributes",
                 "Summary:", "End timestamp")
_MAX_PATHS_IN_DETAIL = 20
_CLASSES = (("changed", "aide_changed", "medium"),
            ("removed", "aide_removed", "medium"),
            ("added", "aide_added", "info"))


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


# --- report parsing and the batch reader -------------------------------

def parse_report(text):
    """One AIDE report's text -> its entry classes.

    Returns {"added": [paths], "removed": [paths],
    "changed": [paths], "differences": bool}. Paths come
    from the entry lines of the "Added entries:" /
    "Removed entries:" / "Changed entries:" sections, in
    file order. "differences" is what the report's own
    summary claims ("AIDE found differences ..." vs "AIDE
    found no differences ..."); a report with no summary
    line answers True exactly when it lists an entry.
    Non-string input answers the empty report.
    """
    report = {"added": [], "removed": [], "changed": [],
              "differences": False}
    if not isinstance(text, str):
        return report
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in _SECTIONS:
            current = _SECTIONS[stripped]
            continue
        if any(stripped.startswith(end) for end in _SECTION_ENDS):
            current = None
            continue
        if current is None:
            continue
        m = _ENTRY_RE.match(line.strip())
        if m:
            report[current].append(m.group(2).strip())
    low = text.lower()
    if "found no differences" in low:
        report["differences"] = False
    elif "found differences" in low:
        report["differences"] = True
    else:
        report["differences"] = bool(
            report["added"] or report["removed"] or report["changed"])
    return report


def _fingerprint(path):
    st = os.stat(path)
    return {"inode": st.st_ino, "size": st.st_size,
            "mtime": st.st_mtime}


def _same_fingerprint(prev, fingerprint):
    return isinstance(prev, dict) \
        and prev.get("inode") == fingerprint["inode"] \
        and prev.get("size") == fingerprint["size"] \
        and prev.get("mtime") == fingerprint["mtime"]


def _fingerprint_text(fingerprint):
    if isinstance(fingerprint, str):
        return fingerprint
    if isinstance(fingerprint, dict):
        return (f"{fingerprint.get('inode')}:"
                f"{fingerprint.get('size')}:"
                f"{fingerprint.get('mtime')}")
    return None


def read_report_file(paths, reader_state):
    """Read the first NEW report among paths.

    Returns (report_text_or_None, new_reader_state). A
    report is new when its file's (inode, size, mtime)
    fingerprint differs from reader_state's entry for that
    path. The returned state advances the fingerprint of
    the report that was read -- and only that one, when
    several paths are new at once, so the next pass reads
    the next. A missing or unreadable file yields no report
    and keeps its previous fingerprint entry.
    """
    if not isinstance(reader_state, dict):
        reader_state = {}
    new_reader = {}
    report_text = None
    if not isinstance(paths, (list, tuple)):
        paths = []
    for path in paths:
        if not isinstance(path, str) or not path:
            continue
        prev = reader_state.get(path)
        try:
            fingerprint = _fingerprint(path)
        except OSError:
            if isinstance(prev, dict):
                new_reader[path] = dict(prev)
            continue
        if report_text is not None or _same_fingerprint(prev, fingerprint):
            # Already have this pass's report, or this one is
            # not new: carry the previous fingerprint, so an
            # unread new report stays new for the next pass.
            if isinstance(prev, dict) \
                    and not _same_fingerprint(prev, fingerprint):
                new_reader[path] = dict(prev)
            else:
                new_reader[path] = fingerprint
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                report_text = fh.read()
        except OSError:
            if isinstance(prev, dict):
                new_reader[path] = dict(prev)
            continue
        new_reader[path] = fingerprint
    return report_text, new_reader


# --- the decision: readings in, signals out (pure) --------------------

def _fresh_state():
    return {"last_fingerprint": None}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    last = state.get("last_fingerprint")
    out = {"last_fingerprint": last if isinstance(last, str) else None}
    reader = state.get("_reader")
    if isinstance(reader, dict):
        out["_reader"] = reader
    return out


def _clean_report(report):
    clean = {"added": [], "removed": [], "changed": []}
    if not isinstance(report, dict):
        return clean
    for key in clean:
        entries = report.get(key)
        if isinstance(entries, list):
            clean[key] = [p for p in entries if isinstance(p, str) and p]
    return clean


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock. readings carry one parsed
    report (readings["report"], the parse_report() shape)
    and its fingerprint (readings["fingerprint"], or
    readings["report_fingerprint"]). No report, a report
    whose fingerprint is the one the state last filed for,
    and a report with zero differences all file nothing.
    Otherwise one alert per non-empty class, in the
    manifest's order -- changed, removed, added -- each
    detail carrying the class count, the first 20 paths,
    and the report fingerprint; filing records the
    fingerprint in the state.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "aide_feed"
    report = readings.get("report")
    if report is None:
        return [], state
    report = _clean_report(report)
    fingerprint = _fingerprint_text(readings.get("fingerprint"))
    if fingerprint is None:
        fingerprint = _fingerprint_text(
            readings.get("report_fingerprint"))
    if fingerprint is not None \
            and fingerprint == state["last_fingerprint"]:
        return [], state
    alerts = []
    for key, signal, severity in _CLASSES:
        paths = report[key]
        if not paths:
            continue
        alerts.append({
            "sensor": sensor, "signal": signal,
            "severity": severity,
            "title": f"{len(paths)} {key} "
                     f"{'entry' if len(paths) == 1 else 'entries'} "
                     f"in AIDE report",
            "detail": {"count": len(paths),
                       "paths": paths[:_MAX_PATHS_IN_DETAIL],
                       "fingerprint": fingerprint,
                       "report_fingerprint": fingerprint}})
    if fingerprint is not None:
        state["last_fingerprint"] = fingerprint
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
        print(f"aide-feed: local delivery needs the "
              f"homing-pigeon repo importable ({e}); run me from "
              f"a clone", file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"aide-feed: no signing secret in "
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
            print(f"aide-feed: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"aide-feed: filed {alert.get('signal')} "
              f"via {where}", file=sys.stderr)
    return delivered


def _changed_fingerprint(paths, old_reader, new_reader):
    """The fingerprint text of the first path whose entry changed."""
    if not isinstance(old_reader, dict):
        old_reader = {}
    for path in paths:
        new = new_reader.get(path) if isinstance(new_reader, dict) else None
        if isinstance(new, dict) and new != old_reader.get(path):
            return _fingerprint_text(new)
    return None


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="AIDE Feed extension watcher: read the "
                    "newest AIDE check report once and file "
                    "one sensor alert per entry class it "
                    "reports (changed, removed, added).")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".aide-feed-state.json"),
                    help="state file (default: "
                         ".aide-feed-state.json next to "
                         "this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of a report file (trying the sense "
                         "against known readings, on any box)")
    ap.add_argument("--report-file", default=None,
                    help="parse this whole report file as a fixture, "
                         "ignoring the reader state")
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
        print(f"aide-feed: cannot read manifest "
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
            print(f"aide-feed: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    elif args.report_file:
        try:
            with open(args.report_file, encoding="utf-8",
                      errors="replace") as fh:
                content = fh.read()
            fingerprint = _fingerprint_text(_fingerprint(args.report_file))
        except OSError as e:
            print(f"aide-feed: cannot read report file "
                  f"{args.report_file}: {e}", file=sys.stderr)
            return 2
        readings = {"now": time.time(), "report": parse_report(content),
                    "fingerprint": fingerprint}
    else:
        paths = tunables.get("report_paths")
        if not isinstance(paths, list) or not paths:
            paths = ["/var/log/aide/aide.log"]
        reader = state.get("_reader") if isinstance(state, dict) else None
        text, new_reader = read_report_file(paths, reader or {})
        if text is None:
            readings = {"now": time.time(), "report": None}
        else:
            readings = {
                "now": time.time(), "report": parse_report(text),
                "fingerprint": _changed_fingerprint(
                    paths, reader or {}, new_reader)}
    alerts, state = decide(readings, manifest, state)
    if new_reader is not None:
        state["_reader"] = new_reader
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so
            # the fingerprint does not advance and the next
            # pass re-reads this report.
            print(f"aide-feed: {len(alerts) - delivered} of "
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
        print(f"aide-feed: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
