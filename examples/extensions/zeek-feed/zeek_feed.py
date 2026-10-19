#!/usr/bin/env python3
"""Zeek Feed: a Homing Pigeon user extension (example sense).

Tails the Zeek logs named in the log_paths tunable -- by
default conn.log and dns.log under the zeekctl "current"
directory -- and files the two signals declared in
extension.json:

- zeek_new_external_peers  at least new_peer_threshold
                           DISTINCT external responders
                           (id.resp_h) were first seen inside
                           the trailing window_sec
- zeek_dns_anomaly         one DNS query was anomalous: at
                           least query_length_threshold
                           characters long, six or more
                           labels, or a TXT / NULL / KEY /
                           ANY qtype; filed once per
                           (query, responder) episode

"External" is the stdlib ipaddress module's word, not this
file's: a responder that parses as private, loopback,
link-local or multicast is not external, and neither is one
on the allowlist tunable (exact addresses or CIDR networks).
Connection rows with odd services or protocols are NOT a
signal -- Zeek sees plenty of oddity that means nothing, and
this sense keeps its set honest by not filing it.

Zeek's default log shape is TSV whose column order is stated
in the file itself: "#fields" header lines name the columns
in force, and headers can reappear mid-file when Zeek rotates
or restarts, so the parser is header-driven -- a data line is
parsed against the field list in force at that point in the
file, never against an assumed layout. Lines starting with
"{" are Zeek's JSON output (Ascii::use_json) and are parsed
with the same field names. Other "#" lines (#types, #open,
...) carry no event and are ignored, as is anything that
does not parse: a Zeek log is mostly rows this sense files
nothing for, and malformed rows answer None, quietly.

The machinery is the log-tailer shape of failed-login-watch,
with one addition the header-driven parser forces: the state
dict carries a "_reader" sub-dict, {path: {"inode", "offset",
"fields"}}, which main() owns, decide() preserves opaquely
and ignores, and read_new_events() threads through a pass --
each file's current field list rides with its offset, because
an offset without the headers in force at it is meaningless.
read_new_events() tails from those offsets (a missing file
yields no events and keeps its offset; an inode change or a
file that shrank restarts it from 0, headers included), and
parse_event() turns one line into one event. The decision
itself is the pure shape the other examples use: decide() --
readings plus manifest plus last pass's state, out come
alerts and the new state -- consumes readings only, and
events are processed in timestamp order. Current time
arrives as readings["now"]; decide() never reads a clock.

State remembers the external peers already seen (bounded by
the seen_peers_cap tunable, oldest evicted first -- an
LRU-ish cap: a peer whose entry was evicted and which shows
up again counts as first-seen again, which is the honest
consequence of a bounded memory) and the (query, responder)
pairs already filed, bounded by the same cap.

Two fixture modes feed decide() without touching a live log:
--readings FILE reads a readings dict ({"now", "events"})
from JSON, and --log-file FILE parses a whole fixture log
from offset 0, ignoring the reader offsets.

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
import ipaddress
import json
import os
import sys
import time

_SUSPICIOUS_QTYPES = frozenset(("TXT", "NULL", "KEY", "ANY"))
_DNS_MIN_LABELS = 6


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clean(value):
    """One Zeek field value as a string; "-" / "(empty)" -> ""."""
    if not isinstance(value, str):
        return ""
    if value in ("-", "(empty)"):
        return ""
    return value


def _parse_ts(value):
    if _is_number(value):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


# --- log reading: parse one line, tail from saved offsets ------------


def _event_from_row(row):
    """One Zeek row (field name -> raw value) -> one event, or None.

    A row with a query or qtype_name field is a DNS row; a row
    with id.resp_h and no DNS fields is a connection row.
    Anything else -- and any row whose ts does not parse --
    answers None.
    """
    if not isinstance(row, dict):
        return None
    ts = _parse_ts(row.get("ts"))
    if ts is None:
        return None
    resp_h = _clean(row.get("id.resp_h"))
    orig_h = _clean(row.get("id.orig_h"))
    if "query" in row or "qtype_name" in row:
        return {
            "ts": ts,
            "kind": "dns",
            "query": _clean(row.get("query")),
            "qtype_name": _clean(row.get("qtype_name")),
            "resp_h": resp_h,
            "orig_h": orig_h,
        }
    if "id.resp_h" in row:
        return {
            "ts": ts,
            "kind": "conn",
            "resp_h": resp_h,
            "orig_h": orig_h,
            "resp_p": _clean(row.get("id.resp_p")),
            "proto": _clean(row.get("proto")),
            "service": _clean(row.get("service")),
        }
    return None


def parse_event(line, fields=None):
    """One log line -> one event dict, or None.

    `fields` is the field list in force for this file -- the
    names from its most recent "#fields" header line. A
    "#fields" line itself answers {"kind": "_fields",
    "fields": [...]}: not an event, but the reader's cue to
    replace the list in force, because rotation can restate
    the headers (in a different order) mid-file. A line
    starting with "{" is parsed as Zeek JSON output, which
    carries its field names per line and needs no `fields`.
    A TSV data line whose column count does not match the
    fields in force -- or that arrives before any header --
    answers None; malformed lines are quiet here by design.
    """
    if not isinstance(line, str):
        return None
    text = line.strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            row = json.loads(text)
        except ValueError:
            return None
        return _event_from_row(row)
    if text.startswith("#"):
        if text.startswith("#fields"):
            names = text.split("\t")
            if len(names) == 1:
                names = text.split()
            names = [n for n in names[1:] if n]
            if names:
                return {"kind": "_fields", "fields": names}
        return None
    if not isinstance(fields, (list, tuple)) or not fields:
        return None
    values = line.rstrip("\r\n").split("\t")
    if len(values) != len(fields):
        return None
    return _event_from_row(dict(zip(fields, values)))


def read_new_events(paths, reader_state):
    """Tail each path from its saved offset.

    Returns (events, new_reader_state). Each reader entry is
    {"inode", "offset", "fields"}: the file's position plus
    the header field list in force at it. A missing or
    unreadable file yields no events and keeps its previous
    entry; an inode change or a file smaller than its saved
    offset (rotation, truncation) restarts that file from 0
    with no fields in force, so its headers are re-read.
    Events come back in timestamp order.
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
                new_reader[path] = dict(prev)
            continue
        continuing = have_prev and prev_inode == st.st_ino and prev_offset <= st.st_size
        offset = prev_offset if continuing else 0
        fields = []
        if continuing:
            saved = prev.get("fields")
            if isinstance(saved, list):
                fields = [f for f in saved if isinstance(f, str)]
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                lines = fh.readlines()
                new_offset = fh.tell()
        except OSError:
            if have_prev:
                new_reader[path] = dict(prev)
            continue
        for line in lines:
            event = parse_event(line, fields)
            if event is None:
                continue
            if event.get("kind") == "_fields":
                fields = event["fields"]
                continue
            events.append(event)
        new_reader[path] = {"inode": st.st_ino, "offset": new_offset, "fields": fields}
    events.sort(key=lambda e: e["ts"])
    return events, new_reader


# --- the decision: readings in, signals out (pure) --------------------


def _fresh_state():
    return {"seen_peers": [], "new_peers": [], "dns_filed": []}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    seen = state.get("seen_peers")
    seen = (
        [p for p in seen if isinstance(p, str) and p] if isinstance(seen, list) else []
    )
    new_peers = []
    raw_new = state.get("new_peers")
    if isinstance(raw_new, list):
        for entry in raw_new:
            if (
                isinstance(entry, dict)
                and _is_number(entry.get("ts"))
                and isinstance(entry.get("peer"), str)
                and entry.get("peer")
            ):
                new_peers.append({"peer": entry["peer"], "ts": float(entry["ts"])})
    dns_filed = []
    raw_filed = state.get("dns_filed")
    if isinstance(raw_filed, list):
        for entry in raw_filed:
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("query"), str)
                and isinstance(entry.get("resp_h"), str)
            ):
                dns_filed.append({"query": entry["query"], "resp_h": entry["resp_h"]})
    out = {"seen_peers": seen, "new_peers": new_peers, "dns_filed": dns_filed}
    # The reader offsets ride along opaquely: main() owns them,
    # decide() preserves and ignores them.
    reader = state.get("_reader")
    if isinstance(reader, dict):
        out["_reader"] = reader
    return out


def _allowlist_networks(tunables):
    """The allowlist tunable as ipaddress networks (bad entries skipped)."""
    nets = []
    raw = tunables.get("allowlist")
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, str) or not entry:
                continue
            try:
                nets.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                continue
    return nets


def _is_external(host, nets):
    """True when `host` is a public address and not allowlisted.

    Private, loopback, link-local and multicast are the
    ipaddress module's own verdicts; an address that does not
    parse at all is not external either.
    """
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast:
        return False
    for net in nets:
        if addr.version == net.version and addr in net:
            return False
    return True


def _dns_reason(query, qtype_name, length_threshold):
    """Why a DNS query is anomalous, or None when it is ordinary."""
    if len(query) >= length_threshold:
        return "long_query"
    if qtype_name.upper() in _SUSPICIOUS_QTYPES:
        return "suspicious_qtype"
    labels = [part for part in query.rstrip(".").split(".") if part]
    if len(labels) >= _DNS_MIN_LABELS:
        return "many_labels"
    return None


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"]. The new-peer episode discipline: first
    sightings inside the trailing window accumulate until they
    reach new_peer_threshold, the alert files once, and the
    accumulation is consumed -- later first sightings build
    the next episode, so a refile always means new peers, not
    a repeat of the last batch. A DNS anomaly files once per
    (query, responder) pair; the pair stays filed until the
    bounded state cap evicts it.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "zeek_feed"
    threshold = tunables.get("new_peer_threshold")
    threshold = int(threshold) if _is_number(threshold) and threshold >= 1 else 10
    window = tunables.get("window_sec")
    window_out = window if _is_number(window) and window > 0 else 600
    window_sec = float(window_out)
    length_threshold = tunables.get("query_length_threshold")
    length_threshold = (
        int(length_threshold)
        if _is_number(length_threshold) and length_threshold >= 1
        else 50
    )
    cap = tunables.get("seen_peers_cap")
    cap = int(cap) if _is_number(cap) and cap >= 1 else 10000
    nets = _allowlist_networks(tunables)

    events = []
    raw_events = readings.get("events")
    if isinstance(raw_events, list):
        for entry in raw_events:
            if not isinstance(entry, dict):
                continue
            ts = entry.get("ts")
            kind = entry.get("kind")
            if not _is_number(ts) or kind not in ("conn", "dns"):
                continue
            clean = {"ts": float(ts), "kind": kind}
            for key in ("resp_h", "orig_h", "query", "qtype_name"):
                value = entry.get(key)
                clean[key] = value if isinstance(value, str) else ""
            events.append(clean)
    events.sort(key=lambda e: e["ts"])
    now = readings.get("now")
    now = float(now) if _is_number(now) else (events[-1]["ts"] if events else 0.0)

    seen = list(state["seen_peers"])
    seen_set = set(seen)
    pending = list(state["new_peers"])
    dns_filed = list(state["dns_filed"])
    dns_keys = {(d["query"], d["resp_h"]) for d in dns_filed}
    alerts = []
    for event in events:
        if event["kind"] == "conn":
            peer = event["resp_h"]
            if not peer or not _is_external(peer, nets):
                continue
            if peer in seen_set:
                # LRU-ish: a live peer refreshes its place, so
                # the cap evicts the stalest peers first.
                seen.remove(peer)
                seen.append(peer)
                continue
            seen.append(peer)
            seen_set.add(peer)
            while len(seen) > cap:
                seen_set.discard(seen.pop(0))
            pending.append({"peer": peer, "ts": event["ts"]})
            floor = event["ts"] - window_sec
            pending = [p for p in pending if floor <= p["ts"] <= event["ts"]]
            peers = sorted({p["peer"] for p in pending})
            if len(peers) >= threshold:
                alerts.append(
                    {
                        "sensor": sensor,
                        "signal": "zeek_new_external_peers",
                        "severity": "medium",
                        "title": f"{len(peers)} new external peers first "
                        f"seen within {window_out:g}s",
                        "detail": {
                            "count": len(peers),
                            "peers": peers,
                            "threshold": threshold,
                            "window_sec": window_out,
                        },
                    }
                )
                # The episode is filed; its sightings are consumed.
                pending = []
        else:  # dns
            query = event["query"]
            if not query:
                continue
            reason = _dns_reason(query, event["qtype_name"], length_threshold)
            if reason is None:
                continue
            key = (query, event["resp_h"])
            if key in dns_keys:
                continue
            alerts.append(
                {
                    "sensor": sensor,
                    "signal": "zeek_dns_anomaly",
                    "severity": "medium",
                    "title": f"DNS anomaly ({reason}): {query} via "
                    f"{event['resp_h'] or '?'}",
                    "detail": {
                        "query": query,
                        "resp_h": event["resp_h"],
                        "qtype_name": event["qtype_name"],
                        "reason": reason,
                    },
                }
            )
            dns_filed.append({"query": query, "resp_h": event["resp_h"]})
            dns_keys.add(key)
            while len(dns_filed) > cap:
                old = dns_filed.pop(0)
                dns_keys.discard((old["query"], old["resp_h"]))
    floor = now - window_sec
    state["seen_peers"] = seen
    state["new_peers"] = [p for p in pending if floor <= p["ts"] <= now]
    state["dns_filed"] = dns_filed
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
            f"zeek-feed: local delivery needs the homing-pigeon "
            f"repo importable ({e}); run me from a clone",
            file=sys.stderr,
        )
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(
            f"zeek-feed: no signing secret in ${args.secret_env}; "
            f"set it to this sense's key secret",
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
                f"zeek-feed: delivery failed for {alert.get('signal')}: {e}",
                file=sys.stderr,
            )
            continue
        delivered += 1
        print(f"zeek-feed: filed {alert.get('signal')} via {where}", file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Zeek Feed extension watcher: tail Zeek's "
        "conn.log and dns.log once and file sensor "
        "alert payloads for first-seen external "
        "peers and anomalous DNS queries."
    )
    ap.add_argument(
        "--manifest",
        default=os.path.join(here, "extension.json"),
        help="extension.json to read tunables from",
    )
    ap.add_argument(
        "--state",
        default=os.path.join(here, ".zeek-feed-state.json"),
        help="state file (default: .zeek-feed-state.json next to this script)",
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
        help="parse this whole Zeek log file from offset 0 "
        "as a fixture, ignoring the reader offsets",
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
        print(f"zeek-feed: cannot read manifest {args.manifest}: {e}", file=sys.stderr)
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
                f"zeek-feed: cannot read readings {args.readings}: {e}", file=sys.stderr
            )
            return 2
    elif args.log_file:
        if not os.path.isfile(args.log_file):
            print(
                f"zeek-feed: cannot read log file {args.log_file}: no such file",
                file=sys.stderr,
            )
            return 2
        events, _fixture_reader = read_new_events([args.log_file], {})
        now = events[-1]["ts"] if events else time.time()
        readings = {"now": now, "events": events}
    else:
        paths = tunables.get("log_paths")
        if not isinstance(paths, list) or not paths:
            paths = [
                "/opt/zeek/logs/current/conn.log",
                "/opt/zeek/logs/current/dns.log",
            ]
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
                f"zeek-feed: {len(alerts) - delivered} of "
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
        print(f"zeek-feed: cannot write state {args.state}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
